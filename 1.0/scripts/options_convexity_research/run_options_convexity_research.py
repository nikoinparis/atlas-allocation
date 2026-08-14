"""Run the standalone Options Convexity Overlay research experiment.

This orchestrates the historical PROXY overlay backtest, computes baseline vs
baseline+overlay metrics, evaluates the validation gates, and writes all
research outputs plus a final markdown report.

It is a STANDALONE research experiment:
  * It is NOT Track A/B/C/D.
  * It does NOT modify or import production allocation logic.
  * It writes ONLY to ``data/research/options_convexity/`` and the report file.
  * It never promotes anything into the main ETF strategy.

Usage::

    python scripts/options_convexity_research/run_options_convexity_research.py

Outputs are deterministic given the input data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make ``src`` importable so we can load the standalone research package.
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from options_convexity import backtest_overlay, metrics  # noqa: E402

# --- Output locations (research only) --------------------------------------
DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
REPORT_PATH = DOCS_OUT / "options_convexity_research_report.md"

# Official holdout boundary used elsewhere in the project for time-ordered
# train/test validation (no random splits for time series).
OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")

# "Material" worsening tolerances for the validation gates. Small, fixed buffers
# so trivially-noisy moves do not flip a gate, but real damage still fails.
DD_TOLERANCE = 0.005  # 0.5 percentage points of extra drawdown allowed.
CVAR_TOLERANCE = 0.001  # 0.1 percentage points of extra weekly CVaR allowed.
MAX_ACTIVATIONS_PER_YEAR = 12.0  # "rare" guardrail.


def _fmt(x: float, pct: bool = False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x * 100:.2f}%" if pct else f"{x:.3f}"


def compute_window_metrics(equity: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Compute baseline vs overlay metrics over full / train / holdout windows."""

    windows = {
        "full": equity,
        "train": equity[equity.index < OFFICIAL_HOLDOUT_START],
        "holdout": equity[equity.index >= OFFICIAL_HOLDOUT_START],
    }
    out: dict[str, dict[str, float]] = {}
    for name, df in windows.items():
        out[name] = {
            "baseline": metrics.summarize(df["baseline_return"]),
            "overlay": metrics.summarize(df["overlay_return"]),
        }
    return out


def evaluate_gates(
    window_metrics: dict,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    activations_per_year: float,
) -> dict[str, dict]:
    """Evaluate the eight validation gates. Returns a dict gate -> result."""

    full_base = window_metrics["full"]["baseline"]
    full_over = window_metrics["full"]["overlay"]

    gates: dict[str, dict] = {}

    # Gate 1: net Sharpe improves vs baseline (full period).
    gates["sharpe_improves"] = {
        "pass": bool(full_over["sharpe"] > full_base["sharpe"]),
        "detail": f"overlay {full_over['sharpe']:.3f} vs baseline {full_base['sharpe']:.3f}",
    }

    # Gate 2: max drawdown does not materially worsen (drawdowns are negative).
    dd_gap = full_over["max_drawdown"] - full_base["max_drawdown"]
    gates["drawdown_ok"] = {
        "pass": bool(dd_gap >= -DD_TOLERANCE),
        "detail": f"overlay {full_over['max_drawdown']:.3f} vs baseline "
        f"{full_base['max_drawdown']:.3f} (Δ {dd_gap:+.4f})",
    }

    # Gate 3: CVaR 5% does not materially worsen (more negative = worse).
    cvar_gap = full_over["cvar_5"] - full_base["cvar_5"]
    gates["cvar_ok"] = {
        "pass": bool(cvar_gap >= -CVAR_TOLERANCE),
        "detail": f"overlay {full_over['cvar_5']:.4f} vs baseline "
        f"{full_base['cvar_5']:.4f} (Δ {cvar_gap:+.4f})",
    }

    # Gate 4: overlay does not activate too frequently.
    gates["activation_rare"] = {
        "pass": bool(np.isfinite(activations_per_year) and activations_per_year <= MAX_ACTIVATIONS_PER_YEAR),
        "detail": f"{activations_per_year:.2f} activations/yr (cap {MAX_ACTIVATIONS_PER_YEAR})",
    }

    # Gate 5: improvement is not driven by one lucky trade. Re-run the overlay
    # equity with the single best trade's incremental P&L removed and check the
    # Sharpe still beats baseline.
    incr = equity["overlay_equity"] - equity["baseline_equity"]
    sharpe_ex_best = full_over["sharpe"]
    if not trades.empty:
        best_idx = trades["incremental_return_vs_etf"].astype(float).idxmax()
        best = trades.loc[best_idx]
        # Remove that trade's settlement-day contribution from overlay equity.
        adj_equity = equity.copy()
        # Approximate removal: subtract the best trade's incremental dollar P&L
        # from overlay equity on and after its expiry date.
        expiry = pd.Timestamp(best["expiry_date"])
        base_at_open = float(equity.loc[: pd.Timestamp(best["open_date"])]["baseline_equity"].iloc[-1])
        incr_dollars = float(best["incremental_return_vs_etf"]) * base_at_open
        mask = adj_equity.index >= expiry
        adj_equity.loc[mask, "overlay_equity"] = adj_equity.loc[mask, "overlay_equity"] - incr_dollars
        adj_ret = adj_equity["overlay_equity"].pct_change().fillna(0.0)
        sharpe_ex_best = metrics.sharpe(adj_ret)
    gates["not_one_trade"] = {
        "pass": bool(sharpe_ex_best > full_base["sharpe"]),
        "detail": f"Sharpe ex-best-trade {sharpe_ex_best:.3f} vs baseline {full_base['sharpe']:.3f}",
    }

    # Gate 6: survives train/holdout split (overlay >= baseline Sharpe in BOTH,
    # allowing a tiny tolerance for the holdout which is short).
    train_ok = window_metrics["train"]["overlay"]["sharpe"] >= window_metrics["train"]["baseline"]["sharpe"]
    hold_b = window_metrics["holdout"]["baseline"]["sharpe"]
    hold_o = window_metrics["holdout"]["overlay"]["sharpe"]
    hold_ok = (not np.isfinite(hold_b)) or (hold_o >= hold_b - 0.05)
    gates["walk_forward_ok"] = {
        "pass": bool(train_ok and hold_ok),
        "detail": f"train Sharpe {window_metrics['train']['overlay']['sharpe']:.3f}"
        f"/{window_metrics['train']['baseline']['sharpe']:.3f}; "
        f"holdout {hold_o:.3f}/{hold_b:.3f}",
    }

    # Gate 7: costs / slippage included (always true by construction here).
    gates["costs_included"] = {
        "pass": True,
        "detail": "entry slippage (5%) + IV markup (x1.05) applied; baseline net of costs",
    }

    # Gate 8: proxy assumptions documented (the report section below).
    gates["proxy_documented"] = {
        "pass": True,
        "detail": "PROXY mode clearly labelled approximate in report and outputs",
    }

    return gates


def decide_verdict(gates: dict, n_trades: int) -> str:
    """Map gate results to a verdict. Default RESEARCH-ONLY unless all pass."""

    # Core gates whose failure means the idea does not work as posed.
    core = ["sharpe_improves", "drawdown_ok", "cvar_ok", "not_one_trade", "walk_forward_ok"]
    all_pass = all(g["pass"] for g in gates.values())
    core_fail = any(not gates[c]["pass"] for c in core)

    if n_trades == 0:
        return "RESEARCH-ONLY"
    if all_pass:
        return "CANDIDATE FOR FURTHER TESTING"
    if core_fail and sum(not gates[c]["pass"] for c in core) >= 3:
        return "REJECT"
    return "RESEARCH-ONLY"


def write_outputs(result, window_metrics, gates, verdict) -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)

    # 1) Trades log.
    trades_path = DATA_OUT / "options_overlay_trades.csv"
    result.trades.to_csv(trades_path, index=False)

    # 2) Equity curves.
    equity_path = DATA_OUT / "baseline_vs_options_equity.csv"
    result.equity.to_csv(equity_path)

    # 3) Metrics (long form: window x strategy x metric).
    rows = []
    for window, by_strat in window_metrics.items():
        for strat, m in by_strat.items():
            for k, v in m.items():
                rows.append({"window": window, "strategy": strat, "metric": k, "value": v})
    # Trade-level economics.
    trade_stats = metrics.summarize_option_trades(result.trades)
    for k, v in trade_stats.items():
        rows.append({"window": "full", "strategy": "options_sleeve", "metric": k, "value": v})
    rows.append({"window": "full", "strategy": "options_sleeve", "metric": "activations_per_year", "value": result.activations_per_year})
    rows.append({"window": "full", "strategy": "options_sleeve", "metric": "premium_spent_per_year", "value": result.premium_spent_per_year})
    # Incremental return / drawdown impact (full period).
    fb, fo = window_metrics["full"]["baseline"], window_metrics["full"]["overlay"]
    rows.append({"window": "full", "strategy": "incremental", "metric": "incremental_cagr", "value": fo["cagr"] - fb["cagr"]})
    rows.append({"window": "full", "strategy": "incremental", "metric": "incremental_max_drawdown", "value": fo["max_drawdown"] - fb["max_drawdown"]})
    rows.append({"window": "full", "strategy": "incremental", "metric": "incremental_sharpe", "value": fo["sharpe"] - fb["sharpe"]})
    metrics_path = DATA_OUT / "options_overlay_metrics.csv"
    pd.DataFrame(rows).to_csv(metrics_path, index=False)

    # 4) Config + gate snapshot (JSON, for the verifier and audit trail).
    snapshot = {
        "config": result.config,
        "verdict": verdict,
        "gates": gates,
        "activations_per_year": result.activations_per_year,
        "premium_spent_per_year": result.premium_spent_per_year,
        "n_trades": int(len(result.trades)),
    }
    (DATA_OUT / "options_overlay_run_snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str))

    # 5) Markdown report.
    write_report(result, window_metrics, gates, verdict, trade_stats)


def write_report(result, window_metrics, gates, verdict, trade_stats) -> None:
    fb = window_metrics["full"]["baseline"]
    fo = window_metrics["full"]["overlay"]

    def metric_row(label, base, over, pct=False):
        return f"| {label} | {_fmt(base, pct)} | {_fmt(over, pct)} |"

    lines = []
    lines.append("# Options Convexity Overlay — Research Report")
    lines.append("")
    lines.append("> **Standalone research experiment.** NOT Track A/B/C/D. Does NOT modify or")
    lines.append("> import production allocation logic. Not promoted into the main ETF strategy.")
    lines.append("")
    lines.append(f"**Final verdict: `{verdict}`**")
    lines.append("")
    lines.append("> ⚠️ **PROXY RESULTS — APPROXIMATE, NOT PRODUCTION-GRADE.** No real historical")
    lines.append("> option-chain data was available. Spreads are priced with Black-Scholes using a")
    lines.append("> realized-volatility proxy for implied volatility, with a conservative IV markup")
    lines.append("> and entry slippage that bias the model AGAINST the overlay. Treat all figures as")
    lines.append("> directional evidence only.")
    lines.append("")
    lines.append("## 1. Setup")
    lines.append("")
    cfg = result.config
    lines.append(f"- Baseline: production pin `improved_frontier_phase5_fragility_guard` (weekly net returns).")
    lines.append(f"- Underlyings: {', '.join(cfg['underlyings'])}.")
    lines.append(f"- Structure: bull call spread, ~{cfg['horizon_weeks']*7} DTE (~{cfg['horizon_weeks']} weeks), held to expiry, non-overlapping per underlying.")
    lines.append(f"- Premium budget: {cfg['premium_budget']*100:.0f}% default, hard cap {cfg['hard_cap_total_premium']*100:.0f}% total; self-funded by reducing the matching ETF.")
    lines.append(f"- Costs: entry slippage {cfg['entry_slippage_pct']*100:.0f}%, IV markup ×{cfg['iv_markup']}, r={cfg['risk_free_rate']}.")
    lines.append(f"- Mode: `{cfg['mode']}`.")
    lines.append("")
    lines.append("## 2. Activity")
    lines.append("")
    lines.append(f"- Option trades: **{int(len(result.trades))}** over {fb['n_weeks']} weeks.")
    lines.append(f"- Activations per year: **{result.activations_per_year:.2f}**.")
    lines.append(f"- Premium spent per year: **{result.premium_spent_per_year*100:.2f}%** of portfolio (sum of premium fractions).")
    if trade_stats["n_trades"]:
        lines.append(f"- Option hit rate: **{_fmt(trade_stats['option_hit_rate'], True)}**; "
                     f"avg trade return {_fmt(trade_stats['avg_trade_return'], True)}, "
                     f"median {_fmt(trade_stats['median_trade_return'], True)}, "
                     f"worst {_fmt(trade_stats['worst_trade_return'], True)}, "
                     f"best {_fmt(trade_stats['best_trade_return'], True)}.")
    lines.append("")
    lines.append("## 3. Baseline vs Baseline + Overlay (full period)")
    lines.append("")
    lines.append("| Metric | Baseline | + Overlay |")
    lines.append("|--------|----------|-----------|")
    lines.append(metric_row("CAGR", fb["cagr"], fo["cagr"], True))
    lines.append(metric_row("Ann. return (arith)", fb["ann_return"], fo["ann_return"], True))
    lines.append(metric_row("Ann. volatility", fb["ann_vol"], fo["ann_vol"], True))
    lines.append(metric_row("Net Sharpe", fb["sharpe"], fo["sharpe"]))
    lines.append(metric_row("Sortino", fb["sortino"], fo["sortino"]))
    lines.append(metric_row("Max drawdown", fb["max_drawdown"], fo["max_drawdown"], True))
    lines.append(metric_row("Calmar", fb["calmar"], fo["calmar"]))
    lines.append(metric_row("CVaR 5% (weekly)", fb["cvar_5"], fo["cvar_5"], True))
    lines.append(metric_row("Hit rate (weekly)", fb["hit_rate"], fo["hit_rate"], True))
    lines.append("")
    lines.append(f"Incremental: CAGR {_fmt(fo['cagr']-fb['cagr'], True)}, "
                 f"Sharpe {_fmt(fo['sharpe']-fb['sharpe'])}, "
                 f"max-drawdown impact {_fmt(fo['max_drawdown']-fb['max_drawdown'], True)}.")
    lines.append("")
    lines.append("Turnover/cost note: the overlay adds episodic option premium spend "
                 f"(~{result.premium_spent_per_year*100:.2f}%/yr) and reduces the matching ETF by the "
                 "same amount; it does not add leverage. ETF-leg turnover impact is second-order and "
                 "the dominant cost is the modelled option slippage/IV markup, already included.")
    lines.append("")
    lines.append("## 4. Train / Holdout split")
    lines.append("")
    lines.append(f"Holdout boundary: `{OFFICIAL_HOLDOUT_START.date()}` (time-ordered, no random split).")
    lines.append("")
    lines.append("| Window | Baseline Sharpe | Overlay Sharpe | Baseline CAGR | Overlay CAGR |")
    lines.append("|--------|-----------------|----------------|---------------|--------------|")
    for w in ("train", "holdout"):
        b, o = window_metrics[w]["baseline"], window_metrics[w]["overlay"]
        lines.append(f"| {w} | {_fmt(b['sharpe'])} | {_fmt(o['sharpe'])} | {_fmt(b['cagr'], True)} | {_fmt(o['cagr'], True)} |")
    lines.append("")
    lines.append("## 5. Validation gates")
    lines.append("")
    lines.append("| Gate | Result | Detail |")
    lines.append("|------|--------|--------|")
    gate_labels = {
        "sharpe_improves": "1. Net Sharpe improves",
        "drawdown_ok": "2. Max drawdown not materially worse",
        "cvar_ok": "3. CVaR not materially worse",
        "activation_rare": "4. Activates rarely",
        "not_one_trade": "5. Not driven by one lucky trade",
        "walk_forward_ok": "6. Survives train/holdout",
        "costs_included": "7. Costs/slippage included",
        "proxy_documented": "8. Proxy assumptions documented",
    }
    for key, label in gate_labels.items():
        g = gates[key]
        lines.append(f"| {label} | {'✅ PASS' if g['pass'] else '❌ FAIL'} | {g['detail']} |")
    lines.append("")
    lines.append("## 6. Interpretation & verdict")
    lines.append("")
    n_pass = sum(g["pass"] for g in gates.values())
    lines.append(f"{n_pass}/{len(gates)} gates passed. **Verdict: `{verdict}`.**")
    lines.append("")
    if verdict == "CANDIDATE FOR FURTHER TESTING":
        lines.append("All gates pass under the proxy. Before any further consideration this needs "
                     "real historical option-chain data (with actual bid/ask, IV surface, and skew), "
                     "live-chain execution checks, and sensitivity analysis on the activation thresholds. "
                     "**No promotion. No production change.**")
    elif verdict == "REJECT":
        lines.append("Core gates fail even under a proxy that is biased against options costs. The v0 "
                     "convexity overlay does not improve the risk-adjusted profile. Shelve unless a "
                     "materially different structure or activation logic is proposed.")
    else:
        lines.append("The overlay is, at best, neutral under the proxy and does not clear every gate. "
                     "Keep as research only. Do not promote. Revisit only with real option-chain data "
                     "and/or a refined (but not overfit) activation design.")
    lines.append("")
    lines.append("## 7. Proxy assumptions (read before trusting numbers)")
    lines.append("")
    lines.append("- **No real option data.** Implied vol is proxied by trailing 26-week realized vol "
                 "(annualized), lagged one week, then marked up ×1.05. Real IV has skew, term structure, "
                 "and a variance risk premium not modelled here.")
    lines.append("- **Pricing.** Black-Scholes European calls; ETF options are American and pay dividends — "
                 "ignored. Held to expiry, cash-settled at intrinsic.")
    lines.append("- **Execution.** 5% entry slippage on the net debit; no early exit; no commissions beyond "
                 "slippage. Liquidity assumed (the 5 ETFs are highly liquid); live mode applies real filters.")
    lines.append("- **Accounting.** The option is measured against a STATIC hold of the matching ETF slice "
                 "over the option's life (the self-funding source). The baseline itself rebalances weekly, "
                 "so the counterfactual ETF slice is an approximation.")
    lines.append("- **Determinism.** No randomness; identical inputs reproduce identical outputs.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    print("[options-convexity] running historical proxy overlay backtest...")
    result = backtest_overlay.run_proxy_overlay_backtest()
    print(f"[options-convexity] trades={len(result.trades)} "
          f"activations/yr={result.activations_per_year:.2f}")

    window_metrics = compute_window_metrics(result.equity)
    gates = evaluate_gates(window_metrics, result.trades, result.equity, result.activations_per_year)
    verdict = decide_verdict(gates, len(result.trades))

    write_outputs(result, window_metrics, gates, verdict)

    print(f"[options-convexity] verdict: {verdict}")
    print(f"[options-convexity] outputs written to {DATA_OUT}")
    print(f"[options-convexity] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
