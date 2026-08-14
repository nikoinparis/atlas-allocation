#!/usr/bin/env python3
"""Prepare, signal, simulate, and emit a non-trading paper target from a free snapshot."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import calendar
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.evaluation import benchmark_regression, block_bootstrap_intervals, performance_metrics, rolling_window_summary
from src.systematic_trader.point_in_time import CASH_ASSET, build_monthly_top_n_weights, combine_and_smooth, compute_path
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns

STORE_ROOT = ROOT / "data/vintages"
OUTPUT = ROOT / "evidence/free_snapshot_research_pipeline"
DERIVED_ROOT = ROOT / "data/derived"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
LEGACY_PRICES = ROOT.parent / "1.0/data/01_data_hub/weekly_prices.csv"
PRIOR_RETURNS = ROOT / "evidence/strategy_raw_formula_rebuild/returns.csv"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
START = date(2005, 1, 7)
RECENT_START = date(2021, 1, 1)
RETROSPECTIVE_EXTENSION_START = date(2026, 4, 17)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_free_manifest(store: SnapshotStore) -> dict[str, object]:
    candidates = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    if not candidates:
        raise ValueError("no free provider snapshot exists")
    return max(candidates, key=lambda item: parse_utc(str(item["observed_at_utc"])))


def next_last_friday(day: date) -> date:
    year, month = day.year, day.month
    while True:
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        candidate = last_day
        while candidate.weekday() != 4:
            candidate = candidate.replace(day=candidate.day - 1)
        if candidate > day:
            return candidate
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1


def metrics_bundle(periods: list[dict[str, float | str]], spy_by_date: dict[str, float]) -> dict[str, object]:
    values = [float(row["net_return"]) for row in periods]
    spy = [spy_by_date[str(row["realization_date"])] for row in periods]
    recent_indices = [i for i, row in enumerate(periods) if date.fromisoformat(str(row["realization_date"])) >= RECENT_START]
    recent = [values[i] for i in recent_indices]
    recent_spy = [spy[i] for i in recent_indices]
    extension = [float(row["net_return"]) for row in periods if date.fromisoformat(str(row["realization_date"])) >= RETROSPECTIVE_EXTENSION_START]
    return {
        "full": performance_metrics(values).to_dict(),
        "recent_since_2021": performance_metrics(recent).to_dict(),
        "benchmark": benchmark_regression(values, spy),
        "recent_benchmark": benchmark_regression(recent, recent_spy),
        "rolling_3y": rolling_window_summary(values, spy),
        "bootstrap_95pct": block_bootstrap_intervals(values, seed=20260808),
        "retrospective_extension": performance_metrics(extension).to_dict(),
        "retrospective_extension_start": RETROSPECTIVE_EXTENSION_START.isoformat(),
        "retrospective_extension_is_untouched_holdout": False,
    }


def compare_legacy_prices(dates: list[str], assets: list[str], prices) -> dict[str, object]:
    legacy = {row["Date"]: row for row in read_csv(LEGACY_PRICES)}
    comparisons = 0
    changed = 0
    missingness = 0
    max_relative = 0.0
    for day in dates:
        if day not in legacy:
            continue
        for asset in assets:
            old_raw = legacy[day].get(asset, "")
            new = prices[day][asset]
            if not old_raw or new is None:
                missingness += (not old_raw) != (new is None)
                continue
            old = float(old_raw)
            comparisons += 1
            relative = abs(new - old) / max(abs(old), 1e-12)
            max_relative = max(max_relative, relative)
            changed += relative > 1e-8
    return {
        "numeric_comparisons": comparisons,
        "rows_changed_over_1e_8_relative": changed,
        "changed_share": changed / comparisons if comparisons else 0.0,
        "missingness_mismatches": missingness,
        "maximum_relative_difference": max_relative,
        "expected_reason": "Yahoo adjusted history and corrections can change between acquisition vintages",
    }


def compare_prior_strategy(periods: list[dict[str, float | str]]) -> dict[str, object]:
    old = {row["decision_date"]: row for row in read_csv(PRIOR_RETURNS)}
    differences = []
    for row in periods:
        decision = str(row["decision_date"])
        if decision in old:
            differences.append(abs(float(row["net_return"]) - float(old[decision]["net_return"])))
    return {
        "common_periods": len(differences),
        "changed_periods_over_1e_10": sum(value > 1e-10 for value in differences),
        "maximum_absolute_return_difference": max(differences) if differences else None,
    }


def build() -> dict[str, object]:
    store = SnapshotStore(STORE_ROOT)
    manifest = latest_free_manifest(store)
    snapshot_id = str(manifest["snapshot_id"])
    store.verify(snapshot_id)
    payload = STORE_ROOT / snapshot_id / "payload"
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    assets = sorted(universe["symbols"])
    observed_date = parse_utc(str(manifest["observed_at_utc"])).date()
    dates, prices, preparation = prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=observed_date, start_date=START, expected_symbols=assets
    )
    log_returns = weekly_log_returns(dates, assets, prices)
    strategy_panels, _ = reconstruct_five_signals(
        dates=dates, assets=assets, prices=prices, weekly_log_returns=log_returns
    )
    scores = combine_and_smooth(dates, RISK_ASSETS, list(strategy_panels.values()), window=4)
    weights, rebalance_dates = build_monthly_top_n_weights(
        dates=dates, assets=RISK_ASSETS, scores=scores, prices=prices,
        top_n=4, min_signal=0.05, defensive_asset="BIL",
        include_sample_endpoint_rebalance=False,
    )
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=10.0)
    spy_by_date = {day: row["SPY"] for day, row in simple_returns.items() if row["SPY"] is not None}
    metrics = metrics_bundle(periods, spy_by_date)
    cost_stress = {}
    for bps in (10.0, 25.0, 50.0):
        stressed = [float(row["gross_return"]) - float(row["turnover"]) * bps / 10_000.0 for row in periods]
        cost_stress[f"{int(bps)}bps"] = performance_metrics(stressed).to_dict()

    latest_day = dates[-1]
    latest_weights = {asset: weight for asset, weight in weights[latest_day].items() if weight > 1e-12}
    latest_scores = sorted(
        ((asset, value) for asset, value in scores[latest_day].items() if value is not None),
        key=lambda item: item[1], reverse=True,
    )
    last_rebalance = max(day for day in rebalance_dates if day <= latest_day)
    next_rebalance = next_last_friday(date.fromisoformat(latest_day)).isoformat()
    paper_target = {
        "strategy_version": "composite_trend_quality_refined_free_snapshot_v4",
        "source_snapshot_id": snapshot_id,
        "market_data_through": latest_day,
        "known_at_utc": manifest["observed_at_utc"],
        "decision_is_monthly_rebalance": latest_day in rebalance_dates,
        "last_reconstructed_rebalance_date": last_rebalance,
        "next_scheduled_rebalance_date": next_rebalance,
        "target_weights": latest_weights,
        "top_current_scores": [{"asset": asset, "score": value} for asset, value in latest_scores[:8]],
        "execution_enabled": False,
        "broker_connection": None,
        "activation_status": "waiting_for_next_scheduled_rebalance",
        "historical_target_was_not_live_known_on_rebalance_date": True,
        "purpose": "display and future paper-broker input only",
        "next_rebalance_note": "calendar-derived last Friday; exchange-holiday service not yet connected",
    }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_version": paper_target["strategy_version"],
        "source_snapshot_id": snapshot_id,
        "source_snapshot_observed_at_utc": manifest["observed_at_utc"],
        "historical_simulation_grade": "research_only_free_current_universe",
        "preparation": preparation,
        "accounting": accounting,
        "rebalance_dates": len(rebalance_dates),
        "metrics": metrics,
        "cost_stress": cost_stress,
        "legacy_price_revision_audit": compare_legacy_prices(dates, assets, prices),
        "prior_candidate_return_audit": compare_prior_strategy(periods),
        "paper_target": paper_target,
        "forward_validation": {
            "first_locked_untouched_week_end": "2026-08-14",
            "untouched_returns_available": 0,
            "minimum_required_weeks": 52,
        },
        "limitations": [
            "The free current ETF universe is not survivorship-safe historical membership.",
            "Yahoo adjusted history can be revised; the revision audit records differences from the earlier pull.",
            "The April-August extension was observable when this version was frozen and is not an untouched holdout.",
            "The paper target cannot submit orders and has no broker connection.",
        ],
        "weekly_prices": prices,
        "weekly_log_returns": log_returns,
        "positions": weights,
        "periods": periods,
    }


def pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def report(result: dict[str, object]) -> str:
    metrics = result["metrics"]
    full = metrics["full"]
    recent = metrics["recent_since_2021"]
    extension = metrics["retrospective_extension"]
    prices = result["legacy_price_revision_audit"]
    prior = result["prior_candidate_return_audit"]
    target = result["paper_target"]
    holdings = ", ".join(f"{asset} {weight * 100:.0f}%" for asset, weight in target["target_weights"].items())
    return "\n".join([
        "# Free Snapshot Research Pipeline", "",
        f"Source snapshot: `{result['source_snapshot_id']}`", "",
        "The newest immutable free snapshot has been converted from daily adjusted prices into completed Friday weeks, passed through the independently rebuilt five-signal engine, and simulated with the monthly portfolio rules. No order can leave this pipeline.", "",
        "## Extended research simulation", "",
        f"- Data through: **{result['preparation']['weekly_end']}**.",
        f"- Annual return: **{pct(full['annual_return'])}**.",
        f"- Sharpe (0% risk-free): **{float(full['sharpe_zero_rf']):.3f}**.",
        f"- Maximum drawdown: **{pct(full['max_drawdown'])}**.",
        f"- Since-2021 annual return / Sharpe: **{pct(recent['annual_return'])} / {float(recent['sharpe_zero_rf']):.3f}**.",
        f"- Retrospective April-August extension total return: **{pct(extension['total_return'])}**; this is not an untouched holdout.",
        f"- 50 bps cost-stress annual return: **{pct(result['cost_stress']['50bps']['annual_return'])}**.", "",
        "## Current non-trading paper target", "",
        f"- Market data through: **{target['market_data_through']}**.",
        f"- Holdings: **{holdings}**.",
        f"- Monthly rebalance row: **{'yes' if target['decision_is_monthly_rebalance'] else 'no'}**.",
        f"- Last reconstructed rebalance: **{target['last_reconstructed_rebalance_date']}**.",
        f"- Next scheduled paper observation: **{target['next_scheduled_rebalance_date']}**.",
        "- Activation status: **waiting for the next scheduled rebalance**; the July target was reconstructed after the fact.",
        "- Execution enabled: **no**. No broker is connected.", "",
        "## Revision audit", "",
        f"- Weekly adjusted-price comparisons with the prior 1.0 pull: **{prices['numeric_comparisons']:,}**.",
        f"- Price cells changed by more than 1e-8 relative: **{prices['rows_changed_over_1e_8_relative']:,} ({prices['changed_share'] * 100:.2f}%)**.",
        f"- Prior strategy return periods compared: **{prior['common_periods']:,}**.",
        f"- Prior return periods changed above 1e-10: **{prior['changed_periods_over_1e_10']:,}**.",
        f"- Maximum weekly return difference: **{float(prior['maximum_absolute_return_difference']) * 100:.6f}%**.", "",
        "## Forward-test status", "",
        "The first locked untouched week ends 2026-08-14. No untouched return exists yet; at least 52 weeks remain required before promotion.", "",
    ])


def write_panel(path: Path, dates: list[str], assets: list[str], panel) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", *assets])
        writer.writeheader()
        for day in dates:
            writer.writerow({"Date": day, **{asset: "" if panel[day][asset] is None else panel[day][asset] for asset in assets}})


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    result = build()
    prices = result.pop("weekly_prices")
    log_returns = result.pop("weekly_log_returns")
    positions = result.pop("positions")
    periods = result.pop("periods")
    dates = list(prices)
    assets = list(prices[dates[0]])
    derived = DERIVED_ROOT / str(result["source_snapshot_id"])
    derived.mkdir(parents=True, exist_ok=True)
    write_panel(derived / "weekly_prices.csv", dates, assets, prices)
    write_panel(derived / "weekly_log_returns.csv", dates, assets, log_returns)
    derived_files = [derived / "weekly_prices.csv", derived / "weekly_log_returns.csv"]
    derived_manifest = {
        "source_snapshot_id": result["source_snapshot_id"],
        "source_snapshot_observed_at_utc": result["source_snapshot_observed_at_utc"],
        "transformation": "last available daily adjusted close labeled to completed W-FRI; log return from consecutive weekly rows",
        "files": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in derived_files},
    }
    (derived / "manifest.json").write_text(json.dumps(derived_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_rows(OUTPUT / "positions.csv", [{"Date": day, **row} for day, row in positions.items()])
    write_rows(OUTPUT / "returns.csv", periods)
    (OUTPUT / "paper_target.json").write_text(json.dumps(result["paper_target"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["derived_manifest"] = str((derived / "manifest.json").resolve())
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({
        "metrics": result["metrics"], "paper_target": result["paper_target"],
        "legacy_price_revision_audit": result["legacy_price_revision_audit"],
        "prior_candidate_return_audit": result["prior_candidate_return_audit"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
