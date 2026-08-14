#!/usr/bin/env python3
"""Rebuild and audit composite_trend_quality_refined from dated signal inputs."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.evaluation import (
    benchmark_regression,
    block_bootstrap_intervals,
    performance_metrics,
    rolling_window_summary,
)
from src.systematic_trader.point_in_time import (
    CASH_ASSET,
    SignalSpec,
    build_monthly_top_n_weights,
    combine_and_smooth,
    compute_path,
    read_signal_panel,
    read_wide_panel,
)

V1 = ROOT.parent / "1.0/data"
DATA_HUB = V1 / "01_data_hub"
SIGNAL_DIR = V1 / "02_layer1_signals"
STRATEGY_DIR = V1 / "03_layer2a_strategy_logic"
OUTPUT = ROOT / "evidence/strategy_rebuild_trend_quality"
ORIGINAL_NAME = "composite_trend_quality_refined"
COMPARATOR_NAME = "composite_selective_strength_weighted"
RECENT_START = date(2021, 1, 1)
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
SPECS = [
    SignalSpec("xsmom_global", "signal_xsmom.csv", "xsmom_score_observed", "xsmom_score_tradable"),
    SignalSpec("multi_mom_invvol", "signal_multi_horizon_mom.csv", "multi_mom_invvol_score_observed", "multi_mom_invvol_score_tradable"),
    SignalSpec("tsmom_vol_scaled", "signal_tsmom.csv", "tsmom_score_observed", "tsmom_score_tradable"),
    SignalSpec("trend_clarity_momentum", "signal_trend_quality.csv", "trend_clarity_momentum_score_observed", "trend_clarity_momentum_score_tradable"),
    SignalSpec("moving_average_distance", "signal_moving_average_distance.csv", "moving_average_distance_score_observed", "moving_average_distance_score_tradable"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics_bundle(periods: list[dict[str, float | str]], spy_by_date: dict[str, float]) -> dict[str, object]:
    returns = [float(row["net_return"]) for row in periods]
    spy = [spy_by_date[str(row["realization_date"])] for row in periods]
    recent_indices = [index for index, row in enumerate(periods) if date.fromisoformat(str(row["realization_date"])) >= RECENT_START]
    recent = [returns[index] for index in recent_indices]
    recent_spy = [spy[index] for index in recent_indices]
    return {
        "full_10bps": performance_metrics(returns).to_dict(),
        "recent_since_2021_10bps": performance_metrics(recent).to_dict(),
        "benchmark": benchmark_regression(returns, spy),
        "recent_benchmark": benchmark_regression(recent, recent_spy),
        "rolling_3y": rolling_window_summary(returns, spy),
        "block_bootstrap_95pct": block_bootstrap_intervals(returns, seed=20260808),
    }


def original_periods(name: str) -> list[dict[str, float | str]]:
    rows = read_csv(STRATEGY_DIR / f"strategy_returns_{name}.csv")
    result = []
    for index, row in enumerate(rows[:-1]):
        result.append({
            "decision_date": row["Date"],
            "realization_date": rows[index + 1]["Date"],
            "gross_return": float(row["gross_return"] or 0.0),
            "net_return": float(row["net_return"] or 0.0),
            "turnover": float(row["turnover"] or 0.0),
            "cost": float(row["cost"] or 0.0),
        })
    return result


def build(precomputed_panels: dict[str, dict[str, dict[str, float | None]]] | None = None) -> dict[str, object]:
    dates, _, prices = read_wide_panel(DATA_HUB / "weekly_prices.csv")
    return_dates, _, simple_returns = read_wide_panel(DATA_HUB / "weekly_returns.csv", log_returns=True)
    if dates[1:] != return_dates:
        raise ValueError("weekly price and return calendars do not align")

    manifest = {row["signal_name"]: row for row in json.loads((SIGNAL_DIR / "signal_manifest.json").read_text())}
    panels = []
    lag_audits: dict[str, dict[str, int | float | bool]] = {}
    for spec in SPECS:
        if int(manifest[spec.name]["lag_applied"]) != 1:
            raise ValueError(f"{spec.name} does not declare a one-week lag")
        panel, audit = read_signal_panel(SIGNAL_DIR / spec.file_name, spec)
        panels.append(precomputed_panels[spec.name] if precomputed_panels is not None else panel)
        lag_audits[spec.name] = audit

    scores = combine_and_smooth(dates, RISK_ASSETS, panels, window=4)
    weights, rebalance_dates = build_monthly_top_n_weights(
        dates=dates,
        assets=RISK_ASSETS,
        scores=scores,
        prices=prices,
        top_n=4,
        min_signal=0.05,
        defensive_asset="BIL",
    )
    periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=10.0)

    original_weights = {row["Date"]: row for row in read_csv(STRATEGY_DIR / f"strategy_positions_{ORIGINAL_NAME}.csv")}
    risky_errors = []
    allocation_errors = []
    after_bil_errors = []
    mismatch_dates: list[str] = []
    for decision in dates:
        old = original_weights[decision]
        decision_errors = [abs(weights[decision][asset] - float(old[asset])) for asset in RISK_ASSETS]
        risky_errors.extend(decision_errors)
        old_defensive = float(old["BIL"])
        rebuilt_defensive = weights[decision]["BIL"] + weights[decision][CASH_ASSET]
        defensive_error = abs(rebuilt_defensive - old_defensive)
        allocation_errors.append(defensive_error)
        if max(decision_errors + [defensive_error]) > 1e-12:
            mismatch_dates.append(decision)
        if prices[decision].get("BIL") is not None:
            after_bil_errors.append(abs(weights[decision]["BIL"] - old_defensive))

    spy_by_date = {day: values["SPY"] for day, values in simple_returns.items() if values["SPY"] is not None}
    rebuilt_metrics = metrics_bundle(periods, spy_by_date)
    original_metrics = metrics_bundle(original_periods(ORIGINAL_NAME), spy_by_date)
    comparator_metrics = metrics_bundle(original_periods(COMPARATOR_NAME), spy_by_date)
    spy_periods = [dict(row, net_return=spy_by_date[str(row["realization_date"])]) for row in periods]
    spy_metrics = metrics_bundle(spy_periods, spy_by_date)

    cost_stress = {}
    for bps in (10.0, 25.0, 50.0):
        stressed = [float(row["gross_return"]) - float(row["turnover"]) * bps / 10_000.0 for row in periods]
        cost_stress[f"{int(bps)}bps"] = performance_metrics(stressed).to_dict()

    cash_dates = [decision for decision in dates if weights[decision][CASH_ASSET] > 1e-12]
    audit = {
        **accounting,
        "declared_lags_all_one_week": all(int(manifest[spec.name]["lag_applied"]) == 1 for spec in SPECS),
        "independent_signal_lag_checks_pass": all(bool(item["lag_one_reconciliation_pass"]) for item in lag_audits.values()),
        "decision_precedes_realization_pass": all(str(row["decision_date"]) < str(row["realization_date"]) for row in periods),
        "rebalance_count": len(rebalance_dates),
        "cash_sleeve_weeks": len(cash_dates),
        "cash_sleeve_first_date": cash_dates[0] if cash_dates else None,
        "cash_sleeve_last_date": cash_dates[-1] if cash_dates else None,
        "first_observable_bil_price_date": next(day for day in dates if prices[day].get("BIL") is not None),
        "max_risky_weight_error_vs_original": max(risky_errors),
        "max_total_defensive_allocation_error_vs_original": max(allocation_errors),
        "max_bil_weight_error_after_bil_observable": max(after_bil_errors),
        "saved_position_mismatch_weeks": len(mismatch_dates),
        "saved_position_mismatch_rebalance_dates": sum(day in rebalance_dates for day in mismatch_dates),
        "saved_position_first_mismatch": mismatch_dates[0] if mismatch_dates else None,
        "saved_position_last_mismatch": mismatch_dates[-1] if mismatch_dates else None,
    }
    audit["current_signal_inputs_reproduce_saved_positions"] = (
        audit["max_risky_weight_error_vs_original"] <= 1e-12
        and audit["max_total_defensive_allocation_error_vs_original"] <= 1e-12
        and audit["max_bil_weight_error_after_bil_observable"] <= 1e-12
    )

    sources = [DATA_HUB / "weekly_prices.csv", DATA_HUB / "weekly_returns.csv", SIGNAL_DIR / "signal_manifest.json"]
    sources.extend(SIGNAL_DIR / spec.file_name for spec in SPECS)
    sources.extend([
        STRATEGY_DIR / f"strategy_positions_{ORIGINAL_NAME}.csv",
        STRATEGY_DIR / f"strategy_returns_{ORIGINAL_NAME}.csv",
        STRATEGY_DIR / f"strategy_returns_{COMPARATOR_NAME}.csv",
    ])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "composite_trend_quality_refined_rebuilt_v2",
        "status": "research_only_not_promoted",
        "evidence_grade": "B-rebuilt",
        "audit": audit,
        "signal_lag_audits": lag_audits,
        "metrics": {
            "rebuilt": rebuilt_metrics,
            "original_saved": original_metrics,
            "current_grade_b_comparator": comparator_metrics,
            "spy": spy_metrics,
            "cost_stress": cost_stress,
        },
        "limitations": [
            "The five signal formulas were not re-derived from raw daily vendor data; their observed-to-tradable one-week lag was independently reconciled.",
            "The current dated signal files do not exactly reproduce the older saved positions; this rebuilt candidate is versioned separately and uses newly computed returns.",
            "The ETF universe is the previously researched current universe and can contain survivorship-selection bias.",
            "This same history influenced strategy selection, so it is not an untouched holdout.",
            "Zero-yield USD cash is a conservative stand-in before BIL has a decision-date price.",
            "Taxes, market impact, and live execution uncertainty are not fully modeled.",
        ],
        "forward_lock": {"first_untouched_week_end": "2026-08-14", "minimum_weeks": 52},
        "provenance": {str(path.relative_to(V1)): {"sha256": sha256(path), "bytes": path.stat().st_size} for path in sources},
        "weights": weights,
        "periods": periods,
    }


def pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def report(result: dict[str, object]) -> str:
    metrics = result["metrics"]
    audit = result["audit"]
    assert isinstance(metrics, dict) and isinstance(audit, dict)
    rows = []
    labels = [("Rebuilt v2", "rebuilt"), ("Original saved", "original_saved"), ("Current Grade B", "current_grade_b_comparator"), ("SPY", "spy")]
    for label, key in labels:
        item = metrics[key]["full_10bps"]
        recent = metrics[key]["recent_since_2021_10bps"]
        rows.append(f"| {label} | {pct(item['annual_return'])} | {float(item['sharpe_zero_rf']):.3f} | {pct(item['max_drawdown'])} | {pct(recent['annual_return'])} | {float(recent['sharpe_zero_rf']):.3f} |")
    stress = metrics["cost_stress"]
    return "\n".join([
        "# Point-in-Time Rebuild: Trend Quality Strategy", "",
        "This is an independent portfolio re-execution from the five dated tradable signal files. It does not reuse the saved strategy returns. Before BIL has a price known on the decision date, the defensive allocation is explicitly recorded as zero-yield USD cash.", "",
        "## Result", "",
        f"- Current signal files reproduce the old saved positions: **{'yes' if audit['current_signal_inputs_reproduce_saved_positions'] else 'no'}**.",
        f"- The difference affects {audit['saved_position_mismatch_weeks']} weekly rows across {audit['saved_position_mismatch_rebalance_dates']} rebalance dates, from {audit['saved_position_first_mismatch']} to {audit['saved_position_last_mismatch']}.",
        f"- Five one-week signal-lag reconciliations passed: **{'yes' if audit['independent_signal_lag_checks_pass'] else 'no'}**.",
        f"- Unpriced nonzero exposures: **{audit['unpriced_exposure_events']}**.",
        f"- Cash is explicit for {audit['cash_sleeve_weeks']} weeks; BIL first becomes observable on {audit['first_observable_bil_price_date']}.",
        "- Evidence label: **B-rebuilt, research only**. It is not Grade A and is not approved for live money.", "",
        "## Performance comparison", "",
        "| Strategy | Annual return | Sharpe | Max drawdown | Since-2021 return | Since-2021 Sharpe |",
        "|---|---:|---:|---:|---:|---:|", *rows, "",
        "## Trading-cost stress", "",
        f"- 10 bps: {pct(stress['10bps']['annual_return'])} annual return, {float(stress['10bps']['sharpe_zero_rf']):.3f} Sharpe.",
        f"- 25 bps: {pct(stress['25bps']['annual_return'])} annual return, {float(stress['25bps']['sharpe_zero_rf']):.3f} Sharpe.",
        f"- 50 bps: {pct(stress['50bps']['annual_return'])} annual return, {float(stress['50bps']['sharpe_zero_rf']):.3f} Sharpe.", "",
        "## What this does and does not prove", "",
        "The return accounting, one-week execution timing, monthly portfolio construction, turnover costs, and missing-price handling are now reproducible. The current signal files do not exactly reproduce the older saved holdings, so the old headline result is not treated as validated; the lower rebuilt result is the candidate of record. The backtest remains selected on already-seen history and uses a previously researched ETF universe. Its numbers are stronger evidence than the saved artifact, but they are not a promise of future profit. The locked forward test beginning 2026-08-14 remains required.", "",
    ])


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    result = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    weights = result.pop("weights")
    periods = result.pop("periods")
    weight_rows = [{"Date": day, **row} for day, row in weights.items()]
    write_csv(OUTPUT / "positions.csv", weight_rows, list(weight_rows[0]))
    write_csv(OUTPUT / "returns.csv", periods, list(periods[0]))
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({"audit": result["audit"], "rebuilt": result["metrics"]["rebuilt"]["full_10bps"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
