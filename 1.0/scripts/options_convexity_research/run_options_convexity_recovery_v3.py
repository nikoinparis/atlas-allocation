"""Run Recovery Options Overlay v3.

Standalone research extension only. This does not modify production allocation
logic and does not overwrite v1, v2, or prior recovery outputs.
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

from options_convexity import recovery_v3_backtest as bt, recovery_v3_signal_engine as sig, recovery_v3_validation as val  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
PLAN_PATH = DOCS_OUT / "options_convexity_recovery_v3_research_plan.md"
REPORT_PATH = DOCS_OUT / "options_convexity_recovery_v3_report.md"

PRIOR_RECOVERY_METRICS = DATA_OUT / "recovery_options_metrics.csv"
PRIOR_RECOVERY_EQUITY = DATA_OUT / "recovery_baseline_vs_overlay_equity.csv"
MAIN_CONFIG = bt.V3Config(dte_bucket="60-90", moneyness_bucket="atm_5otm", profit_variant="partial_runner")


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


def _variant_plan() -> list[bt.V3Config]:
    """Small, predeclared v3 study: 3 profit variants plus focused sensitivities."""

    configs = [
        bt.V3Config(dte_bucket="60-90", moneyness_bucket="atm_5otm", profit_variant="no_target"),
        bt.V3Config(dte_bucket="60-90", moneyness_bucket="atm_5otm", profit_variant="full_100"),
        MAIN_CONFIG,
        bt.V3Config(dte_bucket="90-120", moneyness_bucket="atm_5otm", profit_variant="partial_runner"),
        bt.V3Config(dte_bucket="60-90", moneyness_bucket="itm_atm", profit_variant="partial_runner"),
        bt.V3Config(dte_bucket="60-90", moneyness_bucket="otm_5_8", profit_variant="partial_runner"),
    ]
    return configs


def _metric_rows_for_result(group: str, variant: str, summary: dict) -> list[dict]:
    rows: list[dict] = []
    for strategy in ("baseline", "v3_options", "tactical_tilt", "vol_scaled_tilt"):
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
        rows.append({"group": group, "variant": variant, "strategy": "v3_options", "window": "full", "metric": metric, "value": value})
    for metric, value in summary["runner_stats"].items():
        rows.append({"group": group, "variant": variant, "strategy": "v3_options", "window": "full", "metric": metric, "value": value})

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
        "addon_success_rate",
        "partial_trigger_rate",
        "late_entry_block_rate",
    ]
    for metric in extras:
        rows.append({"group": group, "variant": variant, "strategy": "v3_options", "window": "full", "metric": metric, "value": summary[metric]})

    opt = summary["v3_options"]["full"]
    base = summary["baseline"]["full"]
    tilt = summary["tactical_tilt"]["full"]
    for metric, value in {
        "incremental_cagr_vs_baseline": opt["cagr"] - base["cagr"],
        "incremental_sharpe_vs_baseline": opt["sharpe"] - base["sharpe"],
        "incremental_drawdown_impact": opt["max_drawdown"] - base["max_drawdown"],
        "incremental_cvar5_impact": opt["cvar_5"] - base["cvar_5"],
        "options_minus_tilt_sharpe": opt["sharpe"] - tilt["sharpe"],
        "options_minus_tilt_cagr": opt["cagr"] - tilt["cagr"],
    }.items():
        rows.append({"group": group, "variant": variant, "strategy": "v3_options", "window": "full", "metric": metric, "value": value})
    return rows


def _prior_recovery_reference_rows() -> list[dict]:
    if not PRIOR_RECOVERY_METRICS.exists():
        return []
    df = pd.read_csv(PRIOR_RECOVERY_METRICS)
    main = df[
        (df["group"].astype(str) == "recovery_variant")
        & (df["variant"].astype(str) == "outright_call|dte=60-120|PT")
    ].copy()
    rows = []
    for _, r in main.iterrows():
        rows.append(
            {
                "group": "reference",
                "variant": "prior_recovery_main",
                "strategy": str(r["strategy"]),
                "window": str(r["window"]),
                "metric": str(r["metric"]),
                "value": pd.to_numeric(r["value"], errors="coerce"),
            }
        )
    return rows


def _prior_recovery_full() -> dict:
    if not PRIOR_RECOVERY_METRICS.exists():
        return {}
    df = pd.read_csv(PRIOR_RECOVERY_METRICS)
    sub = df[
        (df["group"].astype(str) == "recovery_variant")
        & (df["variant"].astype(str) == "outright_call|dte=60-120|PT")
        & (df["strategy"].astype(str) == "options")
        & (df["window"].astype(str) == "full")
    ]
    return {str(r["metric"]): float(r["value"]) for _, r in sub.iterrows()}


def _variant_row(result: bt.V3Result, summary: dict, gates: dict, verdict: str) -> dict:
    base = summary["baseline"]["full"]
    opt = summary["v3_options"]["full"]
    tilt = summary["tactical_tilt"]["full"]
    vol = summary["vol_scaled_tilt"]["full"]
    return {
        "variant": result.config.label(),
        "dte_bucket": result.config.dte_bucket,
        "moneyness_bucket": result.config.moneyness_bucket,
        "profit_variant": result.config.profit_variant,
        "n_trades": summary["n_trades"],
        "activations_per_year": summary["activations_per_year"],
        "premium_at_risk_per_year": summary["premium_at_risk_per_year"],
        "max_concurrent_risk": summary["max_concurrent_risk"],
        "addon_success_rate": summary["addon_success_rate"],
        "partial_trigger_rate": summary["partial_trigger_rate"],
        "late_entry_block_rate": summary["late_entry_block_rate"],
        "baseline_sharpe": base["sharpe"],
        "v3_options_sharpe": opt["sharpe"],
        "tactical_tilt_sharpe": tilt["sharpe"],
        "vol_scaled_tilt_sharpe": vol["sharpe"],
        "options_minus_baseline_sharpe": opt["sharpe"] - base["sharpe"],
        "options_minus_tilt_sharpe": opt["sharpe"] - tilt["sharpe"],
        "baseline_cagr": base["cagr"],
        "v3_options_cagr": opt["cagr"],
        "tactical_tilt_cagr": tilt["cagr"],
        "baseline_max_drawdown": base["max_drawdown"],
        "v3_options_max_drawdown": opt["max_drawdown"],
        "baseline_cvar_5": base["cvar_5"],
        "v3_options_cvar_5": opt["cvar_5"],
        "v3_options_cvar_1": opt.get("cvar_1", np.nan),
        "sharpe_ex_best": summary["sharpe_ex_best"],
        "sharpe_ex_top3": summary["sharpe_ex_top3"],
        "hit_rate": summary["trade_stats"].get("option_hit_rate", np.nan),
        "avg_trade_return": summary["trade_stats"].get("avg_trade_return", np.nan),
        "median_trade_return": summary["trade_stats"].get("median_trade_return", np.nan),
        "worst_trade_return": summary["trade_stats"].get("worst_trade_return", np.nan),
        "best_trade_return": summary["trade_stats"].get("best_trade_return", np.nan),
        "runner_avg_return": summary["runner_stats"].get("runner_avg_return", np.nan),
        "runner_best_return": summary["runner_stats"].get("runner_best_return", np.nan),
        "runner_worst_return": summary["runner_stats"].get("runner_worst_return", np.nan),
        "gates_passed": sum(1 for g in gates.values() if g["pass"]),
        "gates_total": len(gates),
        "verdict": verdict,
    }


def _write_signal_diagnostics(result: bt.V3Result, summary: dict, gates: dict) -> None:
    rows = []
    log = result.candidate_log.copy()
    if not log.empty:
        entered = log[log["entered"]]
        not_entered = log[~log["entered"]]
        for col in [
            "surplus",
            "breakeven_move",
            "recovery_from_8w_low",
            "transition_age_weeks",
            "dist_fast_ma",
            "vix_percentile",
            "realized_vol_pct",
            "soft_score",
        ]:
            rows.append(
                {
                    "section": "feature_discrimination",
                    "key": col,
                    "value_entered": float(pd.to_numeric(entered[col], errors="coerce").mean()) if len(entered) else np.nan,
                    "value_not_entered": float(pd.to_numeric(not_entered[col], errors="coerce").mean()) if len(not_entered) else np.nan,
                    "n_entered": int(len(entered)),
                    "n_not_entered": int(len(not_entered)),
                    "detail": "",
                }
            )
    for key, gate in gates.items():
        rows.append(
            {
                "section": "validation_gate",
                "key": key,
                "value_entered": 1.0 if gate["pass"] else 0.0,
                "value_not_entered": np.nan,
                "n_entered": int(summary["n_trades"]),
                "n_not_entered": np.nan,
                "detail": gate["detail"],
            }
        )
    pd.DataFrame(rows).to_csv(DATA_OUT / "recovery_v3_signal_diagnostics.csv", index=False)


def _write_entry_timing_diagnostics(result: bt.V3Result) -> None:
    log = result.candidate_log.copy()
    rows = []
    if not log.empty:
        rows.append({"section": "summary", "key": "candidate_rows", "value": len(log), "detail": ""})
        rows.append({"section": "summary", "key": "entered_rows", "value": int(log["entered"].sum()), "detail": ""})
        rows.append({"section": "summary", "key": "late_entry_block_rate", "value": float(log["late_entry_blocked"].mean()), "detail": ""})
        for stage, sub in log.groupby("stage"):
            rows.append({"section": "stage", "key": str(stage), "value": float(sub["entered"].mean()), "detail": f"entry rate over {len(sub)} candidates"})
        reason_counts = (
            log.loc[log["late_entry_reasons"].fillna("").astype(str).ne(""), "late_entry_reasons"]
            .astype(str)
            .str.get_dummies(sep="|")
            .sum()
            .sort_values(ascending=False)
        )
        for reason, count in reason_counts.items():
            rows.append({"section": "late_entry_reason", "key": reason, "value": int(count), "detail": ""})
    pd.DataFrame(rows).to_csv(DATA_OUT / "recovery_v3_entry_timing_diagnostics.csv", index=False)


def _write_equity(result: bt.V3Result) -> None:
    out = result.equity.copy()
    if PRIOR_RECOVERY_EQUITY.exists():
        prior = pd.read_csv(PRIOR_RECOVERY_EQUITY, parse_dates=["Date"]).set_index("Date")
        out["prior_recovery_options_equity"] = prior["recovery_options_equity"].reindex(out.index)
    out.index.name = "Date"
    out.to_csv(DATA_OUT / "recovery_v3_baseline_vs_overlay_equity.csv")


def _write_plan() -> None:
    lines = [
        "# Recovery Options Overlay v3 Research Plan",
        "",
        "> Standalone research extension. Not Track A/B/C/D. No production behavior is modified,",
        "> no existing production allocation logic is changed, and no result is promoted.",
        "",
        "## Hypothesis",
        "",
        "The prior recovery options design was research-only: it slightly improved the shape but",
        "barely beat tactical ETF tilt and did not clearly survive top-3 trade removal. v3 tests",
        "one focused improvement: smaller staged entries, late-entry blocking, and partial",
        "profit-taking with a runner.",
        "",
        "## Scope",
        "",
        "- Underlyings: SPY and QQQ only.",
        "- Structure: outright long calls only.",
        "- DTE: 60-90 primary and 90-120 secondary.",
        "- Moneyness: ATM to 5% OTM primary, with slightly ITM/ATM and 5-8% OTM sensitivities.",
        "- Sizing: 0.125% NAV pilot plus 0.125% add-on; 0.25% normal full position.",
        "- Caps: 0.75% concurrent premium-at-risk and 1.50% annual premium-at-risk.",
        "",
        "## Variants",
        "",
        "The primary DTE/moneyness setup compares exactly three profit-taking variants: no target,",
        "full exit at +100%, and 50% sale at +100% with a runner. Additional focused sensitivities",
        "use the partial-runner variant only.",
        "",
        "## Proxy Caveat",
        "",
        "Historical option chains are unavailable. Results use proxy Black-Scholes pricing on",
        "lagged realized volatility with IV markup and slippage. Real historical option-chain",
        "data is required before trusting any result.",
    ]
    PLAN_PATH.write_text("\n".join(lines) + "\n")


def _write_report(main_result: bt.V3Result, main_summary: dict, main_gates: dict, main_verdict: str, rows: pd.DataFrame, prior: dict) -> None:
    base = main_summary["baseline"]["full"]
    opt = main_summary["v3_options"]["full"]
    tilt = main_summary["tactical_tilt"]["full"]
    vol = main_summary["vol_scaled_tilt"]["full"]
    ts = main_summary["trade_stats"]

    profit_rows = rows[rows["profit_variant"].isin(["no_target", "full_100", "partial_runner"]) & rows["dte_bucket"].eq("60-90") & rows["moneyness_bucket"].eq("atm_5otm")]
    best_profit = profit_rows.sort_values("v3_options_sharpe", ascending=False).head(1)
    best_profit_name = best_profit.iloc[0]["profit_variant"] if len(best_profit) else "n/a"

    lines = [
        "# Recovery Options Overlay v3 Report",
        "",
        "> Standalone research extension. Not production. v1, v2, and prior recovery outputs are preserved.",
        "",
        f"**Final verdict: `{main_verdict}`**",
        "",
        "> PROXY RESULTS - APPROXIMATE, NOT PRODUCTION-GRADE.",
        "> Real historical option-chain data is required before trusting any result.",
        "",
        "## 1. Main Result",
        "",
        f"- Main variant: `{main_result.config.label()}`.",
        f"- Trades: {main_summary['n_trades']}; add-on success: {_fmt(main_summary['addon_success_rate'], True)}; partial-profit trigger rate: {_fmt(main_summary['partial_trigger_rate'], True)}.",
        f"- Late-entry block rate across diagnostics: {_fmt(main_summary['late_entry_block_rate'], True)}.",
        "",
        "| Metric | ETF Baseline | Prior Recovery Main | v3 Options | v3 Tactical Tilt | v3 Vol-Scaled Tilt |",
        "|---|---:|---:|---:|---:|---:|",
        f"| CAGR | {_fmt(base['cagr'], True)} | {_fmt(prior.get('cagr'), True)} | {_fmt(opt['cagr'], True)} | {_fmt(tilt['cagr'], True)} | {_fmt(vol['cagr'], True)} |",
        f"| Net Sharpe | {_fmt(base['sharpe'])} | {_fmt(prior.get('sharpe'))} | {_fmt(opt['sharpe'])} | {_fmt(tilt['sharpe'])} | {_fmt(vol['sharpe'])} |",
        f"| Max drawdown | {_fmt(base['max_drawdown'], True)} | {_fmt(prior.get('max_drawdown'), True)} | {_fmt(opt['max_drawdown'], True)} | {_fmt(tilt['max_drawdown'], True)} | {_fmt(vol['max_drawdown'], True)} |",
        f"| CVaR 5% weekly | {_fmt(base['cvar_5'], True)} | {_fmt(prior.get('cvar_5'), True)} | {_fmt(opt['cvar_5'], True)} | {_fmt(tilt['cvar_5'], True)} | {_fmt(vol['cvar_5'], True)} |",
        f"| CVaR 1% weekly | {_fmt(base.get('cvar_1'), True)} | n/a | {_fmt(opt.get('cvar_1'), True)} | {_fmt(tilt.get('cvar_1'), True)} | {_fmt(vol.get('cvar_1'), True)} |",
        "",
        "## 2. Profit-Taking Comparison",
        "",
        f"Best primary profit-taking variant by v3 options Sharpe: `{best_profit_name}`.",
        "",
        "| Profit Variant | Trades | Sharpe | CAGR | MaxDD | Sharpe ex Top 3 | Partial Trigger | Verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in profit_rows.iterrows():
        lines.append(
            f"| `{r['profit_variant']}` | {int(r['n_trades'])} | {_fmt(r['v3_options_sharpe'])} | "
            f"{_fmt(r['v3_options_cagr'], True)} | {_fmt(r['v3_options_max_drawdown'], True)} | "
            f"{_fmt(r['sharpe_ex_top3'])} | {_fmt(r['partial_trigger_rate'], True)} | {r['verdict']} |"
        )

    lines += [
        "",
        "## 3. Focused Sensitivities",
        "",
        "| Variant | Trades | Sharpe | Tilt Sharpe | MaxDD | Late Block Rate | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in rows.iterrows():
        lines.append(
            f"| `{r['variant']}` | {int(r['n_trades'])} | {_fmt(r['v3_options_sharpe'])} | "
            f"{_fmt(r['tactical_tilt_sharpe'])} | {_fmt(r['v3_options_max_drawdown'], True)} | "
            f"{_fmt(r['late_entry_block_rate'], True)} | {r['verdict']} |"
        )

    lines += [
        "",
        "## 4. Validation Gates",
        "",
        "| Gate | Result | Detail |",
        "|---|---|---|",
    ]
    for key, gate in main_gates.items():
        lines.append(f"| {key} | {'PASS' if gate['pass'] else 'FAIL'} | {gate['detail']} |")

    lines += [
        "",
        "## 5. Research Questions",
        "",
        f"1. Did staged entry improve results? Add-ons occurred in {_fmt(main_summary['addon_success_rate'], True)} of main trades, but the main variant did not clear material gates.",
        "2. Did smaller sizing preserve the defensive profile better? Yes mechanically: max drawdown stayed close to baseline, but the edge was also very small.",
        f"3. Did late-entry filtering improve trade quality? It blocked {_fmt(main_summary['late_entry_block_rate'], True)} of logged candidates; this preserved risk but also reduced opportunity.",
        f"4. Did partial profit-taking plus runner improve robustness? The best primary profit variant was `{best_profit_name}`; the main partial-runner variant still failed top-3 robustness.",
        f"5. Which profit-taking variant worked best? `{best_profit_name}` by full-period Sharpe in the primary setup.",
        f"6. Did v3 beat the ETF baseline? Sharpe was {_fmt(opt['sharpe'])} vs baseline {_fmt(base['sharpe'])}, but not by the required +0.05.",
        f"7. Did v3 beat tactical ETF tilt? Sharpe was {_fmt(opt['sharpe'])} vs tactical tilt {_fmt(tilt['sharpe'])}, below the required +0.03 edge.",
        f"8. Did v3 survive best-trade and top-3 removal? Ex-best {_fmt(main_summary['sharpe_ex_best'])}; ex-top3 {_fmt(main_summary['sharpe_ex_top3'])}.",
        f"9. Did max drawdown and CVaR remain acceptable? Drawdown stayed close; CVaR gates decide this strictly in the table above.",
        "10. Did the result depend on one subperiod? See the not_one_subperiod gate.",
        f"11. Were there enough trades? Main variant had {main_summary['n_trades']} trades.",
        f"12. Status: `{main_verdict}`.",
        "13. Next data required: real historical option chains with bid/ask, IV skew, term structure, expirations, dividends, and realistic fill modeling.",
        "",
        "## 6. Proxy Caveats",
        "",
        "- Pricing is Black-Scholes on lagged realized-vol proxies, marked up for IV and slippage.",
        "- No real historical chains, no bid/ask history, no skew, no term structure, no fill model.",
        "- This cannot establish production validity. Real chain testing is required before any trust decision.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)

    print("[v3] building causal v3 signal panel...")
    signals = sig.build_recovery_v3_signals()

    result_bundle = {}
    metric_rows = _prior_recovery_reference_rows()
    variant_rows = []
    all_trades = []
    print("[v3] running focused variants...")
    for cfg in _variant_plan():
        res = bt.run_v3_backtest(cfg, signals=signals)
        summary = val.extended_summary(res)
        gates = val.evaluate_gates(summary, res)
        verdict = val.decide_verdict(gates, summary)
        result_bundle[cfg.label()] = (res, summary, gates, verdict)
        metric_rows += _metric_rows_for_result("v3_variant", cfg.label(), summary)
        variant_rows.append(_variant_row(res, summary, gates, verdict))
        if not res.trades.empty and not res.trades.dropna(how="all", axis=1).empty:
            all_trades.append(res.trades)
        print(
            f"  {cfg.label()}: trades={summary['n_trades']} "
            f"sharpe={summary['v3_options']['full']['sharpe']:.3f} "
            f"tilt={summary['tactical_tilt']['full']['sharpe']:.3f} verdict={verdict}"
        )

    main_result, main_summary, main_gates, main_verdict = result_bundle[MAIN_CONFIG.label()]
    cleaned_trades = [df.dropna(how="all", axis=1) for df in all_trades]
    trades_df = pd.concat(cleaned_trades, ignore_index=True) if cleaned_trades else pd.DataFrame()
    trades_df.to_csv(DATA_OUT / "recovery_v3_trades.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(DATA_OUT / "recovery_v3_metrics.csv", index=False)
    variant_df = pd.DataFrame(variant_rows)
    variant_df.to_csv(DATA_OUT / "recovery_v3_tactical_etf_comparison.csv", index=False)
    profit_df = variant_df[
        variant_df["dte_bucket"].eq("60-90") & variant_df["moneyness_bucket"].eq("atm_5otm")
    ].copy()
    profit_df.to_csv(DATA_OUT / "recovery_v3_profit_taking_comparison.csv", index=False)

    _write_signal_diagnostics(main_result, main_summary, main_gates)
    _write_entry_timing_diagnostics(main_result)
    _write_equity(main_result)
    _write_plan()
    prior = _prior_recovery_full()
    _write_report(main_result, main_summary, main_gates, main_verdict, variant_df, prior)

    snapshot = {
        "experiment": "recovery_options_overlay_v3",
        "main_config": {
            "dte_bucket": MAIN_CONFIG.dte_bucket,
            "moneyness_bucket": MAIN_CONFIG.moneyness_bucket,
            "profit_variant": MAIN_CONFIG.profit_variant,
            "intended_risk": MAIN_CONFIG.intended_risk,
            "pilot_risk": MAIN_CONFIG.pilot_risk,
            "addon_risk": MAIN_CONFIG.addon_risk,
            "underlyings": MAIN_CONFIG.underlyings,
        },
        "cost_model": {
            "iv_markup": bt.IV_MARKUP,
            "entry_slippage_frac": bt.ENTRY_SLIPPAGE_FRAC,
            "exit_slippage_frac": bt.EXIT_SLIPPAGE_FRAC,
            "max_concurrent_risk": bt.MAX_CONCURRENT_RISK,
            "max_annual_risk": bt.MAX_ANNUAL_RISK,
            "exit_dte": bt.EXIT_DTE,
            "add_window_weeks": bt.ADD_WINDOW_WEEKS,
        },
        "verdict": main_verdict,
        "gates": main_gates,
        "main_summary": {
            "n_trades": main_summary["n_trades"],
            "activations_per_year": main_summary["activations_per_year"],
            "premium_at_risk_per_year": main_summary["premium_at_risk_per_year"],
            "max_concurrent_risk": main_summary["max_concurrent_risk"],
            "full_baseline_sharpe": main_summary["baseline"]["full"]["sharpe"],
            "full_v3_options_sharpe": main_summary["v3_options"]["full"]["sharpe"],
            "full_tactical_tilt_sharpe": main_summary["tactical_tilt"]["full"]["sharpe"],
            "sharpe_ex_best": main_summary["sharpe_ex_best"],
            "sharpe_ex_top3": main_summary["sharpe_ex_top3"],
            "addon_success_rate": main_summary["addon_success_rate"],
            "partial_trigger_rate": main_summary["partial_trigger_rate"],
            "late_entry_block_rate": main_summary["late_entry_block_rate"],
        },
        "variant_count": len(variant_df),
        "mode": "historical_proxy_black_scholes",
        "proxy_warning": "APPROXIMATE - real historical option-chain data required before trusting any result.",
    }
    (DATA_OUT / "recovery_v3_run_snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")

    print(
        f"[v3] MAIN {MAIN_CONFIG.label()}: trades={main_summary['n_trades']} "
        f"v3 Sharpe={main_summary['v3_options']['full']['sharpe']:.3f} "
        f"baseline={main_summary['baseline']['full']['sharpe']:.3f} "
        f"tilt={main_summary['tactical_tilt']['full']['sharpe']:.3f}"
    )
    print(f"[v3] verdict: {main_verdict}")
    print(f"[v3] outputs -> {DATA_OUT}")
    print(f"[v3] report  -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
