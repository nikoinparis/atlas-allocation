"""Run the Options Convexity Recovery Research experiment.

Standalone research extension:
  * Not part of A/B/C/D workstreams.
  * Does not modify or import production allocation logic.
  * Preserves v1/v2 options outputs untouched.
  * Writes only recovery-specific files in data/research/options_convexity/.
  * Can honestly end in REJECT or RESEARCH-ONLY.

Usage:
    python scripts/options_convexity_research/run_options_convexity_recovery.py
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

from options_convexity import metrics, recovery_backtest as rbt, recovery_signal_engine as rse, recovery_validation as rv  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
PLAN_PATH = DOCS_OUT / "options_convexity_recovery_research_plan.md"
REPORT_PATH = DOCS_OUT / "options_convexity_recovery_report.md"

V1_EQUITY_PATH = DATA_OUT / "baseline_vs_options_equity.csv"
V1_METRICS_PATH = DATA_OUT / "options_overlay_metrics.csv"
V2_EQUITY_PATH = DATA_OUT / "options_v2_baseline_vs_overlay_equity.csv"
V2_METRICS_PATH = DATA_OUT / "options_v2_metrics.csv"

MAIN_CONFIG = rbt.RecoveryConfig(structure="outright_call", dte_bucket="60-120", profit_taking=True)


def _fmt(x, pct: bool = False) -> str:
    if x is None:
        return "n/a"
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(x):
        return "n/a"
    return f"{x * 100:.2f}%" if pct else f"{x:.3f}"


def _full(summary: dict, strategy: str) -> dict:
    return summary[strategy]["full"]


def _metric_rows_for_result(group: str, variant: str, summary: dict) -> list[dict]:
    rows: list[dict] = []
    for strategy in ("baseline", "options", "tilt"):
        for window, bundle in summary[strategy].items():
            for metric, value in bundle.items():
                rows.append(
                    {
                        "group": group,
                        "variant": variant,
                        "strategy": strategy,
                        "window": window,
                        "metric": metric,
                        "value": value,
                    }
                )

    for metric, value in summary["trade_stats"].items():
        rows.append(
            {
                "group": group,
                "variant": variant,
                "strategy": "options",
                "window": "full",
                "metric": metric,
                "value": value,
            }
        )

    extras = [
        "sharpe_ex_best",
        "sharpe_ex_top3",
        "activations_per_year",
        "premium_at_risk_per_year",
        "cash_premium_per_year",
        "max_concurrent_risk",
        "avg_dte",
        "avg_moneyness",
        "n_trades",
    ]
    for metric in extras:
        rows.append(
            {
                "group": group,
                "variant": variant,
                "strategy": "options",
                "window": "full",
                "metric": metric,
                "value": summary[metric],
            }
        )

    opt = _full(summary, "options")
    base = _full(summary, "baseline")
    tilt = _full(summary, "tilt")
    derived = {
        "incremental_cagr_vs_baseline": opt["cagr"] - base["cagr"],
        "incremental_sharpe_vs_baseline": opt["sharpe"] - base["sharpe"],
        "incremental_drawdown_impact": opt["max_drawdown"] - base["max_drawdown"],
        "incremental_cvar5_impact": opt["cvar_5"] - base["cvar_5"],
        "options_minus_tilt_sharpe": opt["sharpe"] - tilt["sharpe"],
        "options_minus_tilt_cagr": opt["cagr"] - tilt["cagr"],
    }
    for metric, value in derived.items():
        rows.append(
            {
                "group": group,
                "variant": variant,
                "strategy": "options",
                "window": "full",
                "metric": metric,
                "value": value,
            }
        )
    return rows


def _reference_metric_rows() -> list[dict]:
    rows: list[dict] = []
    if V1_METRICS_PATH.exists():
        v1 = pd.read_csv(V1_METRICS_PATH)
        for _, r in v1.iterrows():
            rows.append(
                {
                    "group": "reference",
                    "variant": "v1_rejected",
                    "strategy": str(r.get("strategy", "overlay")),
                    "window": str(r.get("window", "full")),
                    "metric": str(r["metric"]),
                    "value": pd.to_numeric(r["value"], errors="coerce"),
                }
            )
    if V2_METRICS_PATH.exists():
        v2 = pd.read_csv(V2_METRICS_PATH)
        main = v2[v2["group"].astype(str).eq("main")].copy()
        for _, r in main.iterrows():
            rows.append(
                {
                    "group": "reference",
                    "variant": "v2_rejected_main",
                    "strategy": "overlay",
                    "window": str(r["window"]),
                    "metric": str(r["metric"]),
                    "value": pd.to_numeric(r["value"], errors="coerce"),
                }
            )
    return rows


def _read_reference_full_metrics() -> tuple[dict, dict]:
    v1_full: dict[str, float] = {}
    if V1_METRICS_PATH.exists():
        v1 = pd.read_csv(V1_METRICS_PATH)
        sub = v1[(v1["window"] == "full") & (v1["strategy"] == "overlay")]
        v1_full = {str(r["metric"]): float(r["value"]) for _, r in sub.iterrows()}

    v2_full: dict[str, float] = {}
    if V2_METRICS_PATH.exists():
        v2 = pd.read_csv(V2_METRICS_PATH)
        sub = v2[(v2["group"] == "main") & (v2["window"] == "full")]
        v2_full = {str(r["metric"]): float(r["value"]) for _, r in sub.iterrows()}
    return v1_full, v2_full


def _variant_row(result: rbt.RecoveryResult, summary: dict, gates: dict | None = None, verdict: str | None = None) -> dict:
    opt = _full(summary, "options")
    base = _full(summary, "baseline")
    tilt = _full(summary, "tilt")
    cfg = result.config
    return {
        "variant": cfg.label(),
        "structure": cfg.structure,
        "dte_bucket": cfg.dte_bucket,
        "profit_taking": cfg.profit_taking,
        "n_trades": summary["n_trades"],
        "activations_per_year": summary["activations_per_year"],
        "premium_at_risk_per_year": summary["premium_at_risk_per_year"],
        "cash_premium_per_year": summary["cash_premium_per_year"],
        "max_concurrent_risk": summary["max_concurrent_risk"],
        "avg_dte": summary["avg_dte"],
        "avg_moneyness": summary["avg_moneyness"],
        "baseline_sharpe": base["sharpe"],
        "options_sharpe": opt["sharpe"],
        "tilt_sharpe": tilt["sharpe"],
        "options_minus_baseline_sharpe": opt["sharpe"] - base["sharpe"],
        "options_minus_tilt_sharpe": opt["sharpe"] - tilt["sharpe"],
        "baseline_cagr": base["cagr"],
        "options_cagr": opt["cagr"],
        "tilt_cagr": tilt["cagr"],
        "options_minus_baseline_cagr": opt["cagr"] - base["cagr"],
        "options_minus_tilt_cagr": opt["cagr"] - tilt["cagr"],
        "baseline_max_drawdown": base["max_drawdown"],
        "options_max_drawdown": opt["max_drawdown"],
        "tilt_max_drawdown": tilt["max_drawdown"],
        "baseline_cvar_5": base["cvar_5"],
        "options_cvar_5": opt["cvar_5"],
        "tilt_cvar_5": tilt["cvar_5"],
        "options_cvar_1": opt.get("cvar_1", np.nan),
        "tilt_cvar_1": tilt.get("cvar_1", np.nan),
        "upside_capture": opt.get("upside_capture", np.nan),
        "downside_capture": opt.get("downside_capture", np.nan),
        "sharpe_ex_best": summary["sharpe_ex_best"],
        "sharpe_ex_top3": summary["sharpe_ex_top3"],
        "hit_rate": summary["trade_stats"].get("option_hit_rate", np.nan),
        "avg_trade_return": summary["trade_stats"].get("avg_trade_return", np.nan),
        "median_trade_return": summary["trade_stats"].get("median_trade_return", np.nan),
        "worst_trade_return": summary["trade_stats"].get("worst_trade_return", np.nan),
        "best_trade_return": summary["trade_stats"].get("best_trade_return", np.nan),
        "gates_passed": sum(1 for g in (gates or {}).values() if g.get("pass")),
        "gates_total": len(gates or {}),
        "verdict": verdict or "",
    }


def _write_signal_diagnostics(main_result: rbt.RecoveryResult, main_summary: dict, gates: dict) -> None:
    rows: list[dict] = []
    log = main_result.candidate_log.copy()
    if not log.empty:
        entered = log[log["entered"]]
        not_entered = log[~log["entered"]]
        feature_cols = [c for c in log.columns if c not in ("date", "underlying", "entered")]
        for col in feature_cols:
            rows.append(
                {
                    "section": "feature_discrimination",
                    "variant": main_result.config.label(),
                    "key": col,
                    "value_entered": float(pd.to_numeric(entered[col], errors="coerce").mean()) if len(entered) else np.nan,
                    "value_not_entered": float(pd.to_numeric(not_entered[col], errors="coerce").mean()) if len(not_entered) else np.nan,
                    "n_entered": int(len(entered)),
                    "n_not_entered": int(len(not_entered)),
                    "detail": "",
                }
            )
        by_year = log.assign(year=pd.to_datetime(log["date"]).dt.year).groupby("year")["entered"].agg(["sum", "count"])
        for year, r in by_year.iterrows():
            rows.append(
                {
                    "section": "candidate_funnel_by_year",
                    "variant": main_result.config.label(),
                    "key": str(year),
                    "value_entered": float(r["sum"]),
                    "value_not_entered": float(r["count"] - r["sum"]),
                    "n_entered": int(r["sum"]),
                    "n_not_entered": int(r["count"] - r["sum"]),
                    "detail": "",
                }
            )

    for key, gate in gates.items():
        rows.append(
            {
                "section": "validation_gate",
                "variant": main_result.config.label(),
                "key": key,
                "value_entered": 1.0 if gate["pass"] else 0.0,
                "value_not_entered": np.nan,
                "n_entered": int(main_summary["n_trades"]),
                "n_not_entered": np.nan,
                "detail": gate["detail"],
            }
        )
    pd.DataFrame(rows).to_csv(DATA_OUT / "recovery_signal_diagnostics.csv", index=False)


def _write_equity(main_result: rbt.RecoveryResult) -> None:
    eq = main_result.equity.copy()
    out = pd.DataFrame(index=eq.index)
    out["baseline_equity"] = eq["baseline_equity"]
    out["recovery_options_equity"] = eq["options_equity"]
    out["recovery_tactical_tilt_equity"] = eq["tilt_equity"]
    out["baseline_return"] = eq["baseline_return"]
    out["recovery_options_return"] = eq["options_return"]
    out["recovery_tactical_tilt_return"] = eq["tilt_return"]

    if V1_EQUITY_PATH.exists():
        v1 = pd.read_csv(V1_EQUITY_PATH, parse_dates=["Date"]).set_index("Date")
        out["v1_rejected_overlay_equity"] = v1["overlay_equity"].reindex(out.index)
    if V2_EQUITY_PATH.exists():
        v2 = pd.read_csv(V2_EQUITY_PATH, parse_dates=["Date"]).set_index("Date")
        out["v2_rejected_overlay_equity"] = v2["v2_main_overlay_equity"].reindex(out.index)

    out.index.name = "Date"
    out.to_csv(DATA_OUT / "recovery_baseline_vs_overlay_equity.csv")


def _write_plan() -> None:
    lines = [
        "# Options Convexity Recovery Research Plan",
        "",
        "> Standalone research extension. This is not part of A/B/C/D workstreams, does not",
        "> modify production allocation logic, and does not promote anything into production.",
        "> v1/v2 options outputs are preserved and used only as rejected references.",
        "",
        "## Hypothesis",
        "",
        "Long-premium upside options may only be useful during rare defensive-to-risk-on",
        "recovery transitions, when price acceleration, volatility normalization, and",
        "expected-move surplus all support the trade. This experiment tests recovery",
        "convexity, not generic bullish drift.",
        "",
        "## Scope",
        "",
        "- Underlyings: SPY and QQQ only.",
        "- Structures: outright long calls and 1x2 call backspreads.",
        "- DTE buckets: 60-90, 90-120, and combined 60-120.",
        "- Sizing: 0.50% NAV premium-at-risk per trade, 1.00% concurrent cap, 2.00% annual cap.",
        "- Funding: option premium/risk is compared against reducing the matching ETF exposure; no leverage.",
        "- Exits: 21-30 DTE time stop, optional +100% profit target, thesis invalidation on panic or -8% underlying move.",
        "",
        "## Activation Logic",
        "",
        "Entries require positive SPY/QQQ baseline weight, recent defensive stress, an improving",
        "current regime, no confirmed panic state, trend re-acceleration, and expected move",
        "surplus above the structure breakeven. Soft confirmations include defensive-to-risk-on",
        "transition, recovery from recent low, positive MA slope, MA reclaim, VIX normalization,",
        "VIX term-structure normalization, realized-vol control, and HYG/LQD credit improvement.",
        "",
        "## Validation",
        "",
        "The main predeclared config is outright_call, combined 60-120 DTE, with profit-taking.",
        "Descriptive sweeps cover DTE bucket, structure, and profit-taking. Promotion decisions",
        "do not cherry-pick the sweep. The tactical ETF tilt benchmark runs the same signal dates",
        "using a small ETF overweight instead of options.",
        "",
        "## Proxy Caveat",
        "",
        "No real historical option chains are used. Pricing is Black-Scholes on a realized-vol",
        "proxy with IV markup and slippage. There is no real bid/ask, IV skew, term structure,",
        "historical chain selection, dividend handling, or fill model. Results are approximate",
        "and cannot establish production validity.",
    ]
    PLAN_PATH.write_text("\n".join(lines) + "\n")


def _write_report(
    main_result: rbt.RecoveryResult,
    main_summary: dict,
    gates: dict,
    verdict: str,
    structure_df: pd.DataFrame,
    tactical_df: pd.DataFrame,
    v1_full: dict,
    v2_full: dict,
) -> None:
    base = _full(main_summary, "baseline")
    opt = _full(main_summary, "options")
    tilt = _full(main_summary, "tilt")
    ts = main_summary["trade_stats"]
    best = tactical_df.sort_values("options_sharpe", ascending=False).head(1)
    best_row = best.iloc[0].to_dict() if len(best) else {}

    labels = {
        "sharpe_improves": "Sharpe improves materially",
        "drawdown_ok": "Max drawdown not materially worse",
        "cvar5_ok": "CVaR 5% not materially worse",
        "cvar1_ok": "CVaR 1% not materially worse",
        "not_one_trade": "Survives best-trade removal",
        "survive_top3_removal": "Survives top-3 removal",
        "competitive_vs_tilt": "Competitive vs tactical ETF tilt",
        "enough_trades": "Enough activations to study",
        "activation_rare": "Activations remain rare",
        "annual_premium_ok": "Annual premium-at-risk within cap",
        "concurrent_ok": "Concurrent premium-at-risk within cap",
        "train_holdout_ok": "Train/holdout consistency",
        "not_one_regime": "Not isolated to one period",
        "stress_not_harmful": "Not harmful in panic weeks",
        "costs_conservative": "Costs conservative",
        "no_lookahead": "No lookahead",
    }

    lines = [
        "# Options Convexity Recovery Research Report",
        "",
        "> Standalone research extension. Not production. v1/v2 options outputs are preserved.",
        "",
        f"**Final verdict: `{verdict}`**",
        "",
        "> PROXY RESULTS - APPROXIMATE, NOT PRODUCTION-GRADE. No historical option-chain",
        "> data, no real bid/ask, no true IV skew, no term structure, no real fill model.",
        "",
        "## 1. Research Question",
        "",
        "Earlier options work failed because it treated options as a normal bullish ETF overlay.",
        "This experiment asks a narrower question: can long-premium upside convexity help only",
        "during defensive-to-risk-on recoveries, when trend acceleration and volatility",
        "normalization create enough expected-move surplus to clear option breakevens?",
        "",
        "## 2. Main Predeclared Config",
        "",
        f"- Variant: `{main_result.config.label()}`.",
        "- Underlyings: SPY and QQQ.",
        f"- Per-trade premium-at-risk: {main_result.config.per_trade_risk * 100:.2f}% NAV.",
        f"- Concurrent cap: {rbt.MAX_CONCURRENT_RISK * 100:.2f}% NAV; annual cap: {rbt.MAX_ANNUAL_RISK * 100:.2f}% NAV.",
        f"- Trades: {main_summary['n_trades']}; activations/year: {_fmt(main_summary['activations_per_year'])}; premium-at-risk/year: {_fmt(main_summary['premium_at_risk_per_year'], True)}.",
        "",
        "## 3. Full-Period Comparison",
        "",
        "| Metric | ETF Baseline | v1 Rejected | v2 Rejected Main | Recovery Options | Tactical ETF Tilt |",
        "|---|---:|---:|---:|---:|---:|",
        f"| CAGR | {_fmt(base['cagr'], True)} | {_fmt(v1_full.get('cagr'), True)} | {_fmt(v2_full.get('cagr'), True)} | {_fmt(opt['cagr'], True)} | {_fmt(tilt['cagr'], True)} |",
        f"| Ann. vol | {_fmt(base['ann_vol'], True)} | {_fmt(v1_full.get('ann_vol'), True)} | {_fmt(v2_full.get('ann_vol'), True)} | {_fmt(opt['ann_vol'], True)} | {_fmt(tilt['ann_vol'], True)} |",
        f"| Net Sharpe | {_fmt(base['sharpe'])} | {_fmt(v1_full.get('sharpe'))} | {_fmt(v2_full.get('sharpe'))} | {_fmt(opt['sharpe'])} | {_fmt(tilt['sharpe'])} |",
        f"| Sortino | {_fmt(base['sortino'])} | {_fmt(v1_full.get('sortino'))} | {_fmt(v2_full.get('sortino'))} | {_fmt(opt['sortino'])} | {_fmt(tilt['sortino'])} |",
        f"| Max drawdown | {_fmt(base['max_drawdown'], True)} | {_fmt(v1_full.get('max_drawdown'), True)} | {_fmt(v2_full.get('max_drawdown'), True)} | {_fmt(opt['max_drawdown'], True)} | {_fmt(tilt['max_drawdown'], True)} |",
        f"| CVaR 5% weekly | {_fmt(base['cvar_5'], True)} | {_fmt(v1_full.get('cvar_5'), True)} | {_fmt(v2_full.get('cvar_5'), True)} | {_fmt(opt['cvar_5'], True)} | {_fmt(tilt['cvar_5'], True)} |",
        f"| CVaR 1% weekly | {_fmt(base.get('cvar_1'), True)} | n/a | n/a | {_fmt(opt.get('cvar_1'), True)} | {_fmt(tilt.get('cvar_1'), True)} |",
        "",
        "## 4. Trade Economics",
        "",
        f"- Option hit rate: {_fmt(ts.get('option_hit_rate'), True)}.",
        f"- Average / median trade return: {_fmt(ts.get('avg_trade_return'), True)} / {_fmt(ts.get('median_trade_return'), True)}.",
        f"- Worst / best trade return: {_fmt(ts.get('worst_trade_return'), True)} / {_fmt(ts.get('best_trade_return'), True)}.",
        f"- Sharpe excluding best trade: {_fmt(main_summary['sharpe_ex_best'])}; excluding top 3: {_fmt(main_summary['sharpe_ex_top3'])}.",
        f"- Upside capture: {_fmt(opt.get('upside_capture'))}; downside capture: {_fmt(opt.get('downside_capture'))}.",
        "",
        "## 5. Tactical ETF Tilt Test",
        "",
        "The same entry signals were also expressed as a small tactical ETF overweight. This",
        "checks whether options add value beyond simply leaning further into SPY/QQQ.",
        "",
        f"Main recovery options Sharpe is {_fmt(opt['sharpe'])} versus tactical tilt {_fmt(tilt['sharpe'])}.",
        f"Options minus tilt Sharpe: {_fmt(opt['sharpe'] - tilt['sharpe'])}; options minus tilt CAGR: {_fmt(opt['cagr'] - tilt['cagr'], True)}.",
        "",
        "## 6. Descriptive Sweep",
        "",
        f"Best descriptive recovery variant by full-period Sharpe: `{best_row.get('variant', 'n/a')}`",
        f" with Sharpe {_fmt(best_row.get('options_sharpe'))}. This is descriptive only and does not change the main verdict.",
        "",
        "| Variant | Trades | Options Sharpe | Tilt Sharpe | Options MaxDD | Sharpe ex Top 3 | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in structure_df.iterrows():
        lines.append(
            f"| `{row['variant']}` | {int(row['n_trades'])} | {_fmt(row['options_sharpe'])} | "
            f"{_fmt(row['tilt_sharpe'])} | {_fmt(row['options_max_drawdown'], True)} | "
            f"{_fmt(row['sharpe_ex_top3'])} | {row['verdict']} |"
        )

    lines += [
        "",
        "## 7. Validation Gates",
        "",
        "| Gate | Result | Detail |",
        "|---|---|---|",
    ]
    for key, gate in gates.items():
        lines.append(f"| {labels.get(key, key)} | {'PASS' if gate['pass'] else 'FAIL'} | {gate['detail']} |")

    lines += [
        "",
        "## 8. Verdict Reasoning",
        "",
        f"{sum(1 for g in gates.values() if g['pass'])}/{len(gates)} validation gates passed on the predeclared main config.",
    ]
    if verdict == "CANDIDATE FOR FURTHER TESTING":
        lines.append("The proxy result clears all gates. This would justify real chain validation only, not production promotion.")
    elif verdict == "REJECT":
        lines.append("Core risk-adjusted or robustness gates fail. The recovery options overlay should remain rejected under this proxy.")
    else:
        lines.append("The recovery framing improves the shape versus v1/v2, but it does not clear the material Sharpe and robustness bar. Keep as research-only.")

    lines += [
        "",
        "## 9. Proxy Assumptions",
        "",
        "- Historical option chains are unavailable, so this is a Black-Scholes proxy on lagged realized volatility.",
        "- IV is marked up by 1.05 and entry/exit slippage is charged at 5% of gross option notional.",
        "- No true bid/ask, skew, term structure, American exercise, dividends, or chain-selection constraints.",
        "- The 1x2 backspread is rejected when the modeled risk-zone loss is too large relative to strike width.",
        "- Results are directional research evidence only and cannot establish production validity.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)

    print("[recovery] building causal recovery signal panel...")
    signals = rse.build_recovery_signals()

    print("[recovery] running variants...")
    results: dict[str, tuple[rbt.RecoveryResult, dict, dict, str]] = {}
    structure_rows: list[dict] = []
    metric_rows: list[dict] = _reference_metric_rows()

    for structure in rbt.STRUCTURE_BUILDERS:
        for dte_bucket in rbt.DTE_BUCKETS:
            for profit_taking in (True, False):
                cfg = rbt.RecoveryConfig(structure=structure, dte_bucket=dte_bucket, profit_taking=profit_taking)
                res = rbt.run_recovery_backtest(cfg, signals=signals)
                summary = rv.extended_summary(res)
                gates = rv.evaluate_gates(summary, res)
                verdict = rv.decide_verdict(gates, summary)
                label = cfg.label()
                results[label] = (res, summary, gates, verdict)
                metric_rows += _metric_rows_for_result("recovery_variant", label, summary)
                structure_rows.append(_variant_row(res, summary, gates, verdict))
                print(
                    f"  {label}: trades={summary['n_trades']} "
                    f"sharpe={summary['options']['full']['sharpe']:.3f} "
                    f"tilt={summary['tilt']['full']['sharpe']:.3f} verdict={verdict}"
                )

    main_label = MAIN_CONFIG.label()
    main_result, main_summary, main_gates, main_verdict = results[main_label]

    trades = main_result.trades.copy()
    if not trades.empty:
        trades.insert(0, "variant", main_label)
    trades.to_csv(DATA_OUT / "recovery_options_trades.csv", index=False)

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(DATA_OUT / "recovery_options_metrics.csv", index=False)

    structure_df = pd.DataFrame(structure_rows)
    structure_df.to_csv(DATA_OUT / "recovery_structure_comparison.csv", index=False)
    structure_df.to_csv(DATA_OUT / "recovery_tactical_etf_comparison.csv", index=False)

    _write_signal_diagnostics(main_result, main_summary, main_gates)
    _write_equity(main_result)
    _write_plan()

    v1_full, v2_full = _read_reference_full_metrics()
    _write_report(main_result, main_summary, main_gates, main_verdict, structure_df, structure_df, v1_full, v2_full)

    snapshot = {
        "experiment": "options_convexity_recovery_research",
        "main_config": {
            "structure": MAIN_CONFIG.structure,
            "dte_bucket": MAIN_CONFIG.dte_bucket,
            "profit_taking": MAIN_CONFIG.profit_taking,
            "per_trade_risk": MAIN_CONFIG.per_trade_risk,
            "underlyings": MAIN_CONFIG.underlyings,
        },
        "cost_model": {
            "iv_markup": rbt.IV_MARKUP,
            "entry_slippage_frac": rbt.ENTRY_SLIPPAGE_FRAC,
            "exit_slippage_frac": rbt.EXIT_SLIPPAGE_FRAC,
            "per_trade_risk": rbt.PER_TRADE_RISK,
            "max_concurrent_risk": rbt.MAX_CONCURRENT_RISK,
            "max_annual_risk": rbt.MAX_ANNUAL_RISK,
            "exit_dte": rbt.EXIT_DTE,
            "profit_target": rbt.PROFIT_TARGET,
            "stop_loss_move": rbt.STOP_LOSS_MOVE,
        },
        "verdict": main_verdict,
        "gates": main_gates,
        "main_summary": {
            "n_trades": main_summary["n_trades"],
            "activations_per_year": main_summary["activations_per_year"],
            "premium_at_risk_per_year": main_summary["premium_at_risk_per_year"],
            "cash_premium_per_year": main_summary["cash_premium_per_year"],
            "max_concurrent_risk": main_summary["max_concurrent_risk"],
            "full_baseline_sharpe": main_summary["baseline"]["full"]["sharpe"],
            "full_options_sharpe": main_summary["options"]["full"]["sharpe"],
            "full_tilt_sharpe": main_summary["tilt"]["full"]["sharpe"],
            "sharpe_ex_best": main_summary["sharpe_ex_best"],
            "sharpe_ex_top3": main_summary["sharpe_ex_top3"],
        },
        "variant_count": len(results),
        "mode": "historical_proxy_black_scholes",
        "proxy_warning": "APPROXIMATE - no historical option-chain data, no real bid/ask, no IV skew, no term structure, no fill model.",
        "outputs": {
            "trades": str((DATA_OUT / "recovery_options_trades.csv").relative_to(ROOT)),
            "metrics": str((DATA_OUT / "recovery_options_metrics.csv").relative_to(ROOT)),
            "diagnostics": str((DATA_OUT / "recovery_signal_diagnostics.csv").relative_to(ROOT)),
            "structure_comparison": str((DATA_OUT / "recovery_structure_comparison.csv").relative_to(ROOT)),
            "equity": str((DATA_OUT / "recovery_baseline_vs_overlay_equity.csv").relative_to(ROOT)),
            "tactical_comparison": str((DATA_OUT / "recovery_tactical_etf_comparison.csv").relative_to(ROOT)),
            "report": str(REPORT_PATH.relative_to(ROOT)),
        },
    }
    (DATA_OUT / "recovery_run_snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")

    print(
        f"[recovery] MAIN {main_label}: trades={main_summary['n_trades']} "
        f"options Sharpe={main_summary['options']['full']['sharpe']:.3f} "
        f"baseline={main_summary['baseline']['full']['sharpe']:.3f} "
        f"tilt={main_summary['tilt']['full']['sharpe']:.3f}"
    )
    print(f"[recovery] verdict: {main_verdict}")
    print(f"[recovery] outputs -> {DATA_OUT}")
    print(f"[recovery] report  -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
