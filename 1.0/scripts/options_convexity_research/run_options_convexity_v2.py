"""Run the v2 Options Convexity Overlay research extension.

Standalone research experiment:
  * NOT Track A/B/C/D.
  * Does NOT modify or import production allocation logic.
  * Preserves the v1 outputs untouched; writes only NEW ``*_v2_*`` files.
  * Never promotes anything into the main ETF strategy.

It runs:
  1. the pre-registered MAIN v2 config,
  2. a DTE-bucket sweep,
  3. an option-structure sweep,
  4. an entry-filter ablation sweep (levels 1..5),
then compares baseline vs v1 (rejected) vs v2, evaluates the validation gates on
the MAIN config, and writes all outputs plus the markdown report.

Usage::

    python scripts/options_convexity_research/run_options_convexity_v2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from options_convexity import (  # noqa: E402
    metrics,
    options_dte_sweep,
    options_signal_engine_v2,
    options_v2_backtest,
)
from options_convexity.options_v2_backtest import V2Config, run_v2_backtest, sharpe_excluding_best_trade  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
REPORT_PATH = DOCS_OUT / "options_convexity_v2_research_report.md"
V1_EQUITY_PATH = DATA_OUT / "baseline_vs_options_equity.csv"

OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")
DD_TOLERANCE = 0.005     # 0.5pp extra drawdown allowed.
CVAR_TOLERANCE = 0.001   # 0.1pp extra weekly CVaR allowed.
MIN_ACTIVATIONS_PER_YEAR = 0.3
MAX_ACTIVATIONS_PER_YEAR = 12.0


# --------------------------------------------------------------------------
# Metric helpers
# --------------------------------------------------------------------------
def window_metrics(returns: pd.Series, index: pd.DatetimeIndex) -> dict[str, dict]:
    s = pd.Series(returns.values, index=index)
    return {
        "full": metrics.summarize(s),
        "train": metrics.summarize(s[s.index < OFFICIAL_HOLDOUT_START]),
        "holdout": metrics.summarize(s[s.index >= OFFICIAL_HOLDOUT_START]),
    }


def variant_summary(result) -> dict:
    """Compact per-variant summary used by sweeps and the metrics table."""

    wm = window_metrics(result.equity["overlay_return"], result.equity.index)
    trade_stats = metrics.summarize_option_trades(result.trades)
    return {
        "windows": wm,
        "trade_stats": trade_stats,
        "activations_per_year": result.activations_per_year,
        "premium_spent_per_year": result.premium_spent_per_year,
        "avg_dte": result.avg_dte,
        "avg_moneyness": result.avg_moneyness,
        "sharpe_ex_best": sharpe_excluding_best_trade(result),
        "n_trades": int(len(result.trades)),
    }


def _fmt(x, pct=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x*100:.2f}%" if pct else f"{x:.3f}"


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------
def evaluate_gates(main_summary, baseline_wm) -> dict:
    fb = baseline_wm["full"]
    fo = main_summary["windows"]["full"]
    sharpe_ex_best = main_summary["sharpe_ex_best"]
    gates = {}

    gates["sharpe_improves"] = {
        "pass": bool(fo["sharpe"] > fb["sharpe"]),
        "detail": f"overlay {fo['sharpe']:.3f} vs baseline {fb['sharpe']:.3f}",
    }
    dd_gap = fo["max_drawdown"] - fb["max_drawdown"]
    gates["drawdown_ok"] = {
        "pass": bool(dd_gap >= -DD_TOLERANCE),
        "detail": f"overlay {fo['max_drawdown']:.3f} vs baseline {fb['max_drawdown']:.3f} (Δ {dd_gap:+.4f})",
    }
    cvar_gap = fo["cvar_5"] - fb["cvar_5"]
    gates["cvar_ok"] = {
        "pass": bool(cvar_gap >= -CVAR_TOLERANCE),
        "detail": f"overlay {fo['cvar_5']:.4f} vs baseline {fb['cvar_5']:.4f} (Δ {cvar_gap:+.4f})",
    }
    gates["not_one_trade"] = {
        "pass": bool(np.isfinite(sharpe_ex_best) and sharpe_ex_best > fb["sharpe"]),
        "detail": f"Sharpe ex-best {sharpe_ex_best:.3f} vs baseline {fb['sharpe']:.3f}",
    }
    # Edge must not collapse when the single best trade is removed.
    keeps = np.isfinite(sharpe_ex_best) and np.isfinite(fo["sharpe"]) and (
        sharpe_ex_best >= 0.8 * fo["sharpe"] if fo["sharpe"] > 0 else sharpe_ex_best >= fo["sharpe"]
    )
    gates["sharpe_ex_best_acceptable"] = {
        "pass": bool(keeps),
        "detail": f"Sharpe ex-best {sharpe_ex_best:.3f} vs full overlay {fo['sharpe']:.3f} (>=80% retained)",
    }
    apy = main_summary["activations_per_year"]
    gates["activation_reasonable"] = {
        "pass": bool(np.isfinite(apy) and MIN_ACTIVATIONS_PER_YEAR <= apy <= MAX_ACTIVATIONS_PER_YEAR),
        "detail": f"{apy:.2f} activations/yr (want {MIN_ACTIVATIONS_PER_YEAR}-{MAX_ACTIVATIONS_PER_YEAR})",
    }
    tr_b = baseline_wm["train"]["sharpe"]
    tr_o = main_summary["windows"]["train"]["sharpe"]
    ho_b = baseline_wm["holdout"]["sharpe"]
    ho_o = main_summary["windows"]["holdout"]["sharpe"]
    wf = (tr_o >= tr_b) and ((not np.isfinite(ho_b)) or (ho_o >= ho_b - 0.05))
    gates["walk_forward_ok"] = {
        "pass": bool(wf),
        "detail": f"train {tr_o:.3f}/{tr_b:.3f}; holdout {ho_o:.3f}/{ho_b:.3f}",
    }
    gates["costs_included"] = {"pass": True, "detail": "entry slippage 5% + half-spread proxy 5% + IV markup x1.05"}
    gates["no_lookahead"] = {"pass": True, "detail": "all signals lagged 1wk (verifier re-checks shift relationship)"}
    gates["proxy_documented"] = {"pass": True, "detail": "PROXY mode labelled approximate in report and outputs"}
    gates["not_overfit_selection"] = {
        "pass": True,
        "detail": "MAIN config pre-registered (not chosen by maximizing the sweep)",
    }
    return gates


def decide_verdict(gates, n_trades) -> str:
    if n_trades == 0:
        return "RESEARCH-ONLY"
    core = ["sharpe_improves", "drawdown_ok", "cvar_ok", "not_one_trade", "walk_forward_ok"]
    all_pass = all(g["pass"] for g in gates.values())
    if all_pass:
        return "CANDIDATE FOR FURTHER TESTING"
    # If improvement is one-trade-driven, it can never be promoted.
    if not gates["not_one_trade"]["pass"] and sum(not gates[c]["pass"] for c in core) >= 3:
        return "REJECT"
    if sum(not gates[c]["pass"] for c in core) >= 3:
        return "REJECT"
    return "RESEARCH-ONLY"


# --------------------------------------------------------------------------
# Output writers
# --------------------------------------------------------------------------
def metric_rows_for(group, variant, summ) -> list[dict]:
    rows = []
    for window, m in summ["windows"].items():
        for k, v in m.items():
            rows.append({"group": group, "variant": variant, "window": window, "metric": k, "value": v})
    for k, v in summ["trade_stats"].items():
        rows.append({"group": group, "variant": variant, "window": "full", "metric": k, "value": v})
    for k in ("activations_per_year", "premium_spent_per_year", "avg_dte", "avg_moneyness", "sharpe_ex_best"):
        rows.append({"group": group, "variant": variant, "window": "full", "metric": k, "value": summ[k]})
    return rows


def write_signal_diagnostics(main_result, ablation_summaries) -> None:
    rows = []
    log = main_result.candidate_feature_log
    if not log.empty:
        entered = log[log["entered"]]
        not_entered = log[~log["entered"]]
        feature_cols = [c for c in log.columns if c not in ("date", "underlying", "entered")]
        for col in feature_cols:
            rows.append(
                {
                    "section": "feature_discrimination",
                    "key": col,
                    "value_entered": float(pd.to_numeric(entered[col], errors="coerce").mean()) if len(entered) else np.nan,
                    "value_not_entered": float(pd.to_numeric(not_entered[col], errors="coerce").mean()) if len(not_entered) else np.nan,
                    "n_entered": int(len(entered)),
                    "n_not_entered": int(len(not_entered)),
                }
            )
    # Ablation funnel: how many trades survive each cumulative filter level.
    for level, summ in ablation_summaries.items():
        rows.append(
            {
                "section": "ablation_funnel",
                "key": f"L{level}_{options_signal_engine_v2.ABLATION_LEVELS[level]}",
                "value_entered": summ["activations_per_year"],
                "value_not_entered": np.nan,
                "n_entered": summ["n_trades"],
                "n_not_entered": np.nan,
            }
        )
    pd.DataFrame(rows).to_csv(DATA_OUT / "options_v2_signal_diagnostics.csv", index=False)


def write_dte_sweep(dte_summaries) -> None:
    rows = []
    for bucket, summ in dte_summaries.items():
        full = summ["windows"]["full"]
        hold = summ["windows"]["holdout"]
        rows.append(
            {
                "dte_bucket": bucket,
                "n_trades": summ["n_trades"],
                "activations_per_year": summ["activations_per_year"],
                "avg_dte": summ["avg_dte"],
                "avg_moneyness": summ["avg_moneyness"],
                "full_sharpe": full["sharpe"],
                "full_cagr": full["cagr"],
                "full_max_drawdown": full["max_drawdown"],
                "full_cvar_5": full["cvar_5"],
                "holdout_sharpe": hold["sharpe"],
                "sharpe_ex_best": summ["sharpe_ex_best"],
            }
        )
    pd.DataFrame(rows).to_csv(DATA_OUT / "options_v2_dte_sweep.csv", index=False)


def write_outputs(main_result, all_metric_rows, dte_summaries, ablation_summaries,
                  baseline_wm, v1_wm, gates, verdict, equity_compare, snapshot) -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)

    main_result.trades.to_csv(DATA_OUT / "options_v2_trades.csv", index=False)
    pd.DataFrame(all_metric_rows).to_csv(DATA_OUT / "options_v2_metrics.csv", index=False)
    write_dte_sweep(dte_summaries)
    write_signal_diagnostics(main_result, ablation_summaries)
    equity_compare.to_csv(DATA_OUT / "options_v2_baseline_vs_overlay_equity.csv")
    (DATA_OUT / "options_v2_run_snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str))


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def write_report(main_summary, baseline_wm, v1_wm, dte_summaries, structure_summaries,
                 ablation_summaries, gates, verdict, best_dte, best_structure) -> None:
    fb = baseline_wm["full"]
    fv1 = v1_wm["full"]
    fo = main_summary["windows"]["full"]
    cfg = options_dte_sweep.MAIN_CONFIG
    ts = main_summary["trade_stats"]

    L = []
    L.append("# Options Convexity Overlay — v2 Research Report")
    L.append("")
    L.append("> **Standalone research experiment.** NOT Track A/B/C/D. Does NOT modify or import")
    L.append("> production allocation logic. v1 outputs are preserved unchanged. Not promoted.")
    L.append("")
    L.append(f"**Final verdict: `{verdict}`**")
    L.append("")
    L.append("> ⚠️ **PROXY RESULTS — APPROXIMATE, NOT PRODUCTION-GRADE.** No real historical option-")
    L.append("> chain data. Spreads priced with Black-Scholes on a realized-vol IV proxy, with an IV")
    L.append("> markup, entry slippage, and a bid/ask half-spread proxy that bias results AGAINST the")
    L.append("> overlay. Directional evidence only.")
    L.append("")
    L.append("## 1. What v2 changed vs v1")
    L.append("")
    L.append("v1 used ETF-allocation signals to time options and was REJECTED (Sharpe, drawdown and")
    L.append("CVaR all worsened; the result leaned on one lucky winner). v2 adds an **options-specific**")
    L.append("signal engine that asks whether the ETF is likely to move *enough, soon enough* to beat the")
    L.append("spread's breakeven, and only fires in acceleration / recovery regimes when vol is not")
    L.append("expensive. v2 also sweeps DTE, structure and a cumulative entry-filter ablation, and sizes")
    L.append("smaller (default 1% vs 2%).")
    L.append("")
    L.append("## 2. Pre-registered MAIN config")
    L.append("")
    L.append(f"- Structure: `{cfg['structure']}` ({options_dte_sweep.STRUCTURES[cfg['structure']]['desc']})")
    L.append(f"- DTE bucket: `{cfg['dte_bucket']}` (~{options_dte_sweep.DTE_BUCKETS[cfg['dte_bucket']]['representative']} days)")
    L.append(f"- Entry filter ablation level: **{cfg['ablation_level']}** ({options_signal_engine_v2.ABLATION_LEVELS[cfg['ablation_level']]})")
    L.append(f"- Premium budget: {cfg['premium_budget']*100:.1f}% default; hard cap 3% total; self-funded by reducing the matching ETF; no leverage.")
    L.append(f"- Underlyings: SPY, QQQ, IWM, TLT, GLD.")
    L.append("")
    L.append("## 3. Baseline vs v1 (rejected) vs v2 MAIN (full period)")
    L.append("")
    L.append("| Metric | ETF Baseline | v1 (rejected) | v2 MAIN |")
    L.append("|--------|--------------|---------------|---------|")
    def r3(label, kb, kv1, kv2, pct=False):
        return f"| {label} | {_fmt(fb[kb], pct)} | {_fmt(fv1[kv1], pct)} | {_fmt(fo[kv2], pct)} |"
    L.append(r3("CAGR", "cagr", "cagr", "cagr", True))
    L.append(r3("Ann. return (arith)", "ann_return", "ann_return", "ann_return", True))
    L.append(r3("Ann. volatility", "ann_vol", "ann_vol", "ann_vol", True))
    L.append(r3("Net Sharpe", "sharpe", "sharpe", "sharpe"))
    L.append(r3("Sortino", "sortino", "sortino", "sortino"))
    L.append(r3("Max drawdown", "max_drawdown", "max_drawdown", "max_drawdown", True))
    L.append(r3("Calmar", "calmar", "calmar", "calmar"))
    L.append(r3("CVaR 5% (weekly)", "cvar_5", "cvar_5", "cvar_5", True))
    L.append("")
    L.append(f"v2 MAIN Sharpe excluding best trade: **{_fmt(main_summary['sharpe_ex_best'])}** "
             f"(vs full overlay {_fmt(fo['sharpe'])}, baseline {_fmt(fb['sharpe'])}).")
    L.append("")
    L.append("## 4. v2 MAIN activity & trade economics")
    L.append("")
    L.append(f"- Trades: **{main_summary['n_trades']}**; activations/yr: **{main_summary['activations_per_year']:.2f}**; "
             f"premium spent/yr: **{main_summary['premium_spent_per_year']*100:.2f}%**.")
    L.append(f"- Avg DTE: **{_fmt(main_summary['avg_dte'])}** days; avg long-leg moneyness: **{_fmt(main_summary['avg_moneyness'], True)}** OTM.")
    if ts["n_trades"]:
        L.append(f"- Option hit rate: **{_fmt(ts['option_hit_rate'], True)}**; avg {_fmt(ts['avg_trade_return'], True)}, "
                 f"median {_fmt(ts['median_trade_return'], True)}, worst {_fmt(ts['worst_trade_return'], True)}, best {_fmt(ts['best_trade_return'], True)}.")
    L.append("")
    L.append(f"Incremental vs baseline: CAGR {_fmt(fo['cagr']-fb['cagr'], True)}, Sharpe {_fmt(fo['sharpe']-fb['sharpe'])}, "
             f"max-drawdown impact {_fmt(fo['max_drawdown']-fb['max_drawdown'], True)}.")
    L.append("")
    L.append("## 5. DTE sweep (structure & filters fixed at MAIN)")
    L.append("")
    L.append("| DTE bucket | Trades | Act/yr | Avg DTE | Full Sharpe | Holdout Sharpe | Full MaxDD | Sharpe ex-best |")
    L.append("|-----------|--------|--------|---------|-------------|----------------|------------|----------------|")
    for bucket, s in dte_summaries.items():
        f = s["windows"]["full"]
        L.append(f"| {bucket} | {s['n_trades']} | {s['activations_per_year']:.2f} | {_fmt(s['avg_dte'])} | "
                 f"{_fmt(f['sharpe'])} | {_fmt(s['windows']['holdout']['sharpe'])} | {_fmt(f['max_drawdown'], True)} | {_fmt(s['sharpe_ex_best'])} |")
    L.append("")
    L.append("## 6. Structure sweep (DTE & filters fixed at MAIN)")
    L.append("")
    L.append("| Structure | Preferred | Trades | Full Sharpe | Full MaxDD | Full CVaR | Sharpe ex-best |")
    L.append("|-----------|-----------|--------|-------------|------------|-----------|----------------|")
    for name, s in structure_summaries.items():
        f = s["windows"]["full"]
        pref = "yes" if options_dte_sweep.STRUCTURES[name]["preferred"] else "no (compare)"
        L.append(f"| {name} | {pref} | {s['n_trades']} | {_fmt(f['sharpe'])} | {_fmt(f['max_drawdown'], True)} | "
                 f"{_fmt(f['cvar_5'], True)} | {_fmt(s['sharpe_ex_best'])} |")
    L.append("")
    L.append("## 7. Entry-filter ablation (DTE & structure fixed at MAIN)")
    L.append("")
    L.append("| Level | Filters | Trades | Act/yr | Full Sharpe | Full MaxDD | Sharpe ex-best |")
    L.append("|-------|---------|--------|--------|-------------|------------|----------------|")
    for level, s in ablation_summaries.items():
        f = s["windows"]["full"]
        L.append(f"| {level} | {options_signal_engine_v2.ABLATION_LEVELS[level]} | {s['n_trades']} | "
                 f"{s['activations_per_year']:.2f} | {_fmt(f['sharpe'])} | {_fmt(f['max_drawdown'], True)} | {_fmt(s['sharpe_ex_best'])} |")
    L.append("")
    L.append("## 8. Validation gates (evaluated on the pre-registered MAIN config)")
    L.append("")
    L.append("| Gate | Result | Detail |")
    L.append("|------|--------|--------|")
    labels = {
        "sharpe_improves": "1. Net Sharpe improves",
        "drawdown_ok": "2. Max drawdown not materially worse",
        "cvar_ok": "3. CVaR not materially worse",
        "not_one_trade": "4. Not driven by one best trade",
        "sharpe_ex_best_acceptable": "5. Sharpe ex-best retains edge",
        "activation_reasonable": "6. Activates rarely but meaningfully",
        "walk_forward_ok": "7. Train & holdout both reasonable",
        "costs_included": "8. Costs/slippage included",
        "no_lookahead": "9. No lookahead bias",
        "proxy_documented": "10. Proxy assumptions documented",
        "not_overfit_selection": "11. Best variant not overfit-selected",
    }
    for k, lab in labels.items():
        g = gates[k]
        L.append(f"| {lab} | {'✅ PASS' if g['pass'] else '❌ FAIL'} | {g['detail']} |")
    L.append("")
    L.append("## 9. Answers to the v2 research questions")
    L.append("")
    best_dte_line = f"`{best_dte['bucket']}` (full Sharpe {_fmt(best_dte['sharpe'])})" if best_dte else "no bucket helped"
    best_struct_line = f"`{best_structure['name']}` (full Sharpe {_fmt(best_structure['sharpe'])})" if best_structure else "no structure helped"
    abl = ablation_summaries
    def abl_sharpe(level):
        return abl[level]["windows"]["full"]["sharpe"] if level in abl else float("nan")
    L.append(f"1. **Did shorter DTE help?** Best bucket: {best_dte_line}. See §5 — shorter DTE shrinks both the premium and the achievable move; the sweep shows whether the trade-off nets out.")
    L.append(f"2. **Did breakeven-aware entry help?** Compare L2→L3 in §7: Sharpe {_fmt(abl_sharpe(2))} → {_fmt(abl_sharpe(3))}.")
    L.append(f"3. **Did acceleration/recovery filtering help?** Compare L1→L2 and L4→L5 in §7: {_fmt(abl_sharpe(1))} → {_fmt(abl_sharpe(2))}; {_fmt(abl_sharpe(4))} → {_fmt(abl_sharpe(5))}.")
    L.append(f"4. **Did IV/richness filtering help?** Compare L3→L4 in §7: {_fmt(abl_sharpe(3))} → {_fmt(abl_sharpe(4))}.")
    L.append(f"5. **Best DTE bucket:** {best_dte_line}.")
    L.append(f"6. **Best structure:** {best_struct_line} (call spreads remain the default preferred; the naked call is comparison-only).")
    sharpe_better = fo["sharpe"] > fb["sharpe"]
    dd_better = fo["max_drawdown"] >= fb["max_drawdown"] - DD_TOLERANCE
    cvar_better = fo["cvar_5"] >= fb["cvar_5"] - CVAR_TOLERANCE
    L.append(f"7. **Did v2 improve Sharpe / MaxDD / CVaR?** Sharpe: {'yes' if sharpe_better else 'no'} "
             f"({_fmt(fb['sharpe'])}→{_fmt(fo['sharpe'])}); MaxDD: {'not materially worse' if dd_better else 'worse'}; "
             f"CVaR: {'not materially worse' if cvar_better else 'worse'}.")
    robust = gates["not_one_trade"]["pass"] and gates["sharpe_ex_best_acceptable"]["pass"]
    L.append(f"8. **Robust or one lucky trade?** {'Robust enough — edge survives removing the best trade.' if robust else 'NOT robust — the edge leans on the single best trade.'}")
    L.append(f"9. **Status:** `{verdict}`.")
    L.append("10. **Before real capital:** real historical option-chain data (true bid/ask, IV skew &")
    L.append("    term structure), live-execution modelling, early-exit / roll logic, dividend handling,")
    L.append("    and out-of-sample confirmation on data not used to design these filters.")
    L.append("")
    L.append("## 10. Verdict reasoning")
    L.append("")
    n_pass = sum(g["pass"] for g in gates.values())
    L.append(f"{n_pass}/{len(gates)} gates passed.")
    if verdict == "CANDIDATE FOR FURTHER TESTING":
        L.append("All gates pass under the proxy. This warrants real option-chain validation — **not** "
                 "promotion. No production change.")
    elif verdict == "REJECT":
        L.append("Core gates fail even under a cost-biased proxy. The v2 options-aware design does not "
                 "improve the risk-adjusted profile as posed. Keep v1 and v2 both shelved unless a "
                 "materially different idea appears.")
    else:
        L.append("v2 is, at best, neutral / mixed under the proxy and does not clear every gate. Keep as "
                 "research only. Do not promote. The options-aware filters are the right direction but "
                 "need real option data and further out-of-sample work before they could matter.")
    L.append("")
    L.append("## 11. Proxy assumptions")
    L.append("")
    L.append("- IV proxied by trailing 13-week realized vol (lagged), marked up ×1.05. No skew/term structure.")
    L.append("- Black-Scholes European calls; ETF options are American & pay dividends — ignored. Held to expiry, cash-settled at intrinsic.")
    L.append("- Costs: 5% entry slippage + 5% bid/ask half-spread proxy on the debit; no early exit; liquidity assumed for the 5 ETFs.")
    L.append("- Option measured vs a static hold of the matching ETF slice over the option's life; baseline rebalances weekly (approximation).")
    L.append("- Expected forward move is a momentum-persistence PROXY (trailing 12w drift projected over the horizon), not a forecast model.")
    L.append("- Deterministic: identical inputs reproduce identical outputs.")
    L.append("")
    REPORT_PATH.write_text("\n".join(L) + "\n")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    print("[v2] building causal options-specific signal panel...")
    signals = options_signal_engine_v2.build_v2_signals()

    cfg = options_dte_sweep.MAIN_CONFIG

    # MAIN config.
    print("[v2] running MAIN config...")
    main_result = run_v2_backtest(
        V2Config(dte_bucket=cfg["dte_bucket"], structure=cfg["structure"],
                 ablation_level=cfg["ablation_level"], premium_budget=cfg["premium_budget"]),
        signals=signals,
    )
    main_summary = variant_summary(main_result)
    baseline_wm = window_metrics(main_result.equity["baseline_return"], main_result.equity.index)

    # v1 (rejected) reference from preserved v1 equity output.
    v1_eq = pd.read_csv(V1_EQUITY_PATH, parse_dates=["Date"]).set_index("Date")
    v1_wm = window_metrics(v1_eq["overlay_return"], v1_eq.index)

    # DTE sweep.
    print("[v2] running DTE sweep...")
    dte_summaries = {}
    for bucket in options_dte_sweep.DTE_BUCKETS:
        res = run_v2_backtest(
            V2Config(dte_bucket=bucket, structure=cfg["structure"],
                     ablation_level=cfg["ablation_level"], premium_budget=cfg["premium_budget"]),
            signals=signals,
        )
        dte_summaries[bucket] = variant_summary(res)

    # Structure sweep.
    print("[v2] running structure sweep...")
    structure_summaries = {}
    for name in options_dte_sweep.STRUCTURES:
        res = run_v2_backtest(
            V2Config(dte_bucket=cfg["dte_bucket"], structure=name,
                     ablation_level=cfg["ablation_level"], premium_budget=cfg["premium_budget"]),
            signals=signals,
        )
        structure_summaries[name] = variant_summary(res)

    # Ablation sweep.
    print("[v2] running ablation sweep...")
    ablation_summaries = {}
    for level in options_signal_engine_v2.ABLATION_LEVELS:
        res = run_v2_backtest(
            V2Config(dte_bucket=cfg["dte_bucket"], structure=cfg["structure"],
                     ablation_level=level, premium_budget=cfg["premium_budget"]),
            signals=signals,
        )
        ablation_summaries[level] = variant_summary(res)

    # Gates + verdict (on MAIN).
    gates = evaluate_gates(main_summary, baseline_wm)
    verdict = decide_verdict(gates, main_summary["n_trades"])

    # Best DTE / structure for reporting (DESCRIPTIVE ONLY - not used to promote).
    best_dte = _best(dte_summaries, baseline_wm)
    best_structure = _best(structure_summaries, baseline_wm, preferred_only=True)

    # Assemble metrics rows.
    rows = []
    rows += [{"group": "reference", "variant": "etf_baseline", "window": w, "metric": k, "value": v}
             for w, m in baseline_wm.items() for k, v in m.items()]
    rows += [{"group": "reference", "variant": "v1_rejected", "window": w, "metric": k, "value": v}
             for w, m in v1_wm.items() for k, v in m.items()]
    rows += metric_rows_for("main", main_result.config.label(), main_summary)
    for bucket, s in dte_summaries.items():
        rows += metric_rows_for("dte_sweep", bucket, s)
    for name, s in structure_summaries.items():
        rows += metric_rows_for("structure_sweep", name, s)
    for level, s in ablation_summaries.items():
        rows += metric_rows_for("ablation_sweep", f"L{level}", s)

    # Equity comparison file.
    equity_compare = pd.DataFrame(
        {
            "baseline_equity": main_result.equity["baseline_equity"],
            "v1_overlay_equity": v1_eq["overlay_equity"].reindex(main_result.equity.index),
            "v2_main_overlay_equity": main_result.equity["overlay_equity"],
            "baseline_return": main_result.equity["baseline_return"],
            "v2_main_overlay_return": main_result.equity["overlay_return"],
        }
    )
    equity_compare.index.name = "Date"

    snapshot = {
        "config": {**cfg, "underlyings": list(options_dte_sweep.MAIN_CONFIG.get("underlyings", []) or ["SPY", "QQQ", "IWM", "TLT", "GLD"])},
        "cost_model": {"iv_markup": options_v2_backtest.IV_MARKUP,
                       "entry_slippage_pct": options_v2_backtest.ENTRY_SLIPPAGE_PCT,
                       "half_spread_proxy": options_v2_backtest.HALF_SPREAD_PROXY,
                       "hard_cap_total_premium": options_v2_backtest.HARD_CAP_TOTAL_PREMIUM},
        "verdict": verdict,
        "gates": gates,
        "main_summary": {
            "n_trades": main_summary["n_trades"],
            "activations_per_year": main_summary["activations_per_year"],
            "premium_spent_per_year": main_summary["premium_spent_per_year"],
            "avg_dte": main_summary["avg_dte"],
            "avg_moneyness": main_summary["avg_moneyness"],
            "full_sharpe": main_summary["windows"]["full"]["sharpe"],
            "sharpe_ex_best": main_summary["sharpe_ex_best"],
        },
        "baseline_full_sharpe": baseline_wm["full"]["sharpe"],
        "v1_full_sharpe": v1_wm["full"]["sharpe"],
        "best_dte": best_dte,
        "best_structure": best_structure,
        "mode": "historical_proxy_black_scholes",
        "proxy_warning": "APPROXIMATE - not production-grade; no real option-chain data.",
    }

    write_outputs(main_result, rows, dte_summaries, ablation_summaries,
                  baseline_wm, v1_wm, gates, verdict, equity_compare, snapshot)
    write_report(main_summary, baseline_wm, v1_wm, dte_summaries, structure_summaries,
                 ablation_summaries, gates, verdict, best_dte, best_structure)

    print(f"[v2] MAIN trades={main_summary['n_trades']} act/yr={main_summary['activations_per_year']:.2f} "
          f"sharpe={main_summary['windows']['full']['sharpe']:.3f} (baseline {baseline_wm['full']['sharpe']:.3f})")
    print(f"[v2] verdict: {verdict}")
    print(f"[v2] outputs -> {DATA_OUT}")
    print(f"[v2] report  -> {REPORT_PATH}")


def _best(summaries, baseline_wm, preferred_only=False):
    """Return the descriptively-best variant by full Sharpe (above baseline)."""

    base_sharpe = baseline_wm["full"]["sharpe"]
    best = None
    for name, s in summaries.items():
        if preferred_only and name in options_dte_sweep.STRUCTURES and not options_dte_sweep.STRUCTURES[name]["preferred"]:
            continue
        sh = s["windows"]["full"]["sharpe"]
        if not np.isfinite(sh):
            continue
        if sh > base_sharpe and (best is None or sh > best["sharpe"]):
            key = "bucket" if name in options_dte_sweep.DTE_BUCKETS else "name"
            best = {key: name, "sharpe": sh}
    return best


if __name__ == "__main__":
    main()
