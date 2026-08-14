#!/usr/bin/env python3
"""Run the predeclared official-Treasury term-structure challenger."""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_covariance_portfolios_batch_06 as batch06
from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.term_structure_challenger import (
    ASSETS,
    correlation,
    latest_curve_with_full_week_lag,
    monthly_rebalance,
    target_weights,
)
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns

OUTPUT = ROOT / "evidence/treasury_term_structure_batch_14"
CURVE_STORE = ROOT / "data/official_treasury_vintages"
ETF_STORE = ROOT / "data/vintages"
PROGRAM = ROOT / "config/third_sleeve_program_v1.json"
METHODS = ("equal_weight", "carry_roll", "slope_regime")
COSTS = (10.0, 50.0, 100.0)
DEVELOPMENT_END = "2015-12-31"
OOS_START = "2016-01-01"
BLOCK_WEEKS = 13
BOOTSTRAP_SAMPLES = 10_000


def latest_manifest(root: Path, provider: str | None = None) -> dict[str, object]:
    manifests = []
    for path in root.glob("*/manifest.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        if provider is None or item.get("provider") == provider:
            manifests.append(item)
    if not manifests:
        raise RuntimeError(f"no matching manifest under {root}")
    return max(manifests, key=lambda item: str(item["observed_at_utc"]))


def read_curves(path: Path) -> list[dict[str, float | str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {"observation_date": row["observation_date"], **{key: float(row[key]) for key in ("1Y", "2Y", "7Y", "10Y", "20Y")}}
        for row in rows
    ]


def run_method(
    method: str, cost_bps: float, dates: list[str], prices: dict[str, dict[str, float | None]],
    curves: list[dict[str, float | str]],
) -> list[dict[str, float | str]]:
    current = {asset: 0.0 for asset in ASSETS}
    previous_decision = None
    periods: list[dict[str, float | str]] = []
    for index in range(len(dates) - 1):
        decision, realization = dates[index], dates[index + 1]
        turnover = 0.0
        curve = latest_curve_with_full_week_lag(curves, decision)
        if curve is None:
            previous_decision = decision
            continue
        if monthly_rebalance(decision, previous_decision):
            target = target_weights(method, curve)
            turnover = 1.0 if not any(current.values()) else 0.5 * sum(
                abs(target[asset] - current[asset]) for asset in ASSETS
            )
            current = target
        asset_returns = {}
        for asset in ASSETS:
            before, after = prices[decision][asset], prices[realization][asset]
            if before is None or after is None:
                raise RuntimeError(f"missing {asset} price for {decision} -> {realization}")
            asset_returns[asset] = float(after) / float(before) - 1.0
        gross = sum(current[asset] * asset_returns[asset] for asset in ASSETS)
        cost = turnover * cost_bps / 10_000.0
        periods.append({
            "decision_date": decision,
            "realization_date": realization,
            "curve_date_used": curve["observation_date"],
            "method": method,
            "cost_bps": cost_bps,
            "SHY_weight": current["SHY"],
            "IEF_weight": current["IEF"],
            "TLT_weight": current["TLT"],
            "turnover": turnover,
            "gross_return": gross,
            "cost": cost,
            "net_return": gross - cost,
        })
        previous_decision = decision
    return periods


def metrics(periods: list[dict[str, float | str]], start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    selected = [float(row["net_return"]) for row in periods if start <= str(row["realization_date"]) <= end]
    if not selected:
        return {"observations": 0}
    result = performance_metrics(selected).to_dict()
    result["annual_turnover"] = statistics.fmean(
        float(row["turnover"]) for row in periods if start <= str(row["realization_date"]) <= end
    ) * 52.0
    return result


def block_bootstrap_oos(periods: list[dict[str, float | str]]) -> dict[str, float | int | bool]:
    values = [float(row["net_return"]) for row in periods if str(row["realization_date"]) >= OOS_START]
    generator = random.Random(20260809)
    annual_returns = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        while len(sample) < len(values):
            start = generator.randrange(len(values))
            sample.extend(values[(start + offset) % len(values)] for offset in range(BLOCK_WEEKS))
        sample = sample[:len(values)]
        annual_returns.append(math.prod(1.0 + value for value in sample) ** (52.0 / len(sample)) - 1.0)
    ordered = sorted(annual_returns)
    # One-sided 95% familywise bound for the two actual challenger methods.
    lower_index = max(0, math.floor((0.05 / 2.0) * (len(ordered) - 1)))
    lower = ordered[lower_index]
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "block_weeks": BLOCK_WEEKS,
        "challenger_count": 2,
        "familywise_confidence": 0.95,
        "annual_return_lower_bound": lower,
        "pass": lower > 0.0,
    }


def frozen_winner_returns() -> dict[str, float]:
    frozen = json.loads((ROOT / "config/portfolios/covariance_minimum_variance_v1.json").read_text(encoding="utf-8"))
    snapshot_id = str(frozen["source_snapshot_id"])
    payload = ETF_STORE / snapshot_id / "payload"
    assets = sorted(json.loads(batch06.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    manifest = json.loads((ETF_STORE / snapshot_id / "manifest.json").read_text(encoding="utf-8"))
    dates, prices, _ = batch06.prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7), expected_symbols=assets,
    )
    logs = batch06.weekly_log_returns(dates, assets, prices)
    simple = {day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()} for day, row in logs.items()}
    registry = json.loads(batch06.REGISTRY_PATH.read_text(encoding="utf-8"))
    trend = next(item for item in registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421")
    defensive = next(item for item in registry["candidates"] if item.get("family") == "defensive")
    trend_signals, _ = batch06.reconstruct_five_signals(dates=dates, assets=assets, prices=prices, weekly_log_returns=logs)
    non_momentum, _, _ = batch06.reconstruct_non_momentum_signals(
        dates=dates, assets=assets, prices=prices, weekly_log_returns=logs,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    runs = {
        "trend_v4": batch06.run_experiment(spec=batch06.make_spec(trend), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=trend_signals, prices=prices, simple_returns=simple),
        "defensive": batch06.run_experiment(spec=batch06.make_spec(defensive), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=non_momentum, prices=prices, simple_returns=simple),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = batch06.sleeve_return_panel(runs)
    _, periods, _, _ = batch06.evaluate_method(
        dates, histories, sleeve_returns, simple, method="minimum_variance",
        lookback=batch06.PRIMARY_LOOKBACK, shrinkage=batch06.PRIMARY_SHRINKAGE, cost_bps=10.0,
    )
    return {str(row["realization_date"]): float(row["net_return"]) for row in periods}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    curve_manifest = latest_manifest(CURVE_STORE)
    curve_path = CURVE_STORE / str(curve_manifest["snapshot_id"]) / "curve.csv"
    if sha256(curve_path) != curve_manifest["normalized_curve_sha256"]:
        raise RuntimeError("official Treasury curve snapshot hash mismatch")
    curves = read_curves(curve_path)
    etf_manifest = latest_manifest(ETF_STORE, "free_yahoo_via_yfinance")
    payload = ETF_STORE / str(etf_manifest["snapshot_id"]) / "payload"
    dates, prices, audit = prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=parse_utc(str(etf_manifest["observed_at_utc"])).date(),
        start_date=date(2003, 1, 3), expected_symbols=list(ASSETS),
    )
    runs = {(method, cost): run_method(method, cost, dates, prices, curves) for method in METHODS for cost in COSTS}
    scoreboard = []
    for method in METHODS:
        for cost in COSTS:
            periods = runs[(method, cost)]
            scoreboard.append({
                "method": method, "cost_bps": cost,
                **{f"full_{key}": value for key, value in metrics(periods).items()},
                **{f"development_{key}": value for key, value in metrics(periods, end=DEVELOPMENT_END).items()},
                **{f"oos_2016_2020_{key}": value for key, value in metrics(periods, OOS_START, "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in metrics(periods, "2021-01-01").items()},
            })
    development_rows = [row for row in scoreboard if row["cost_bps"] == 10.0 and row["method"] != "equal_weight"]
    selected = max(development_rows, key=lambda row: (float(row["development_sharpe_zero_rf"]), str(row["method"])))
    selected_method = str(selected["method"])
    selected_100 = runs[(selected_method, 100.0)]
    bootstrap = block_bootstrap_oos(selected_100)
    later_positive = all(
        float(next(row for row in scoreboard if row["method"] == selected_method and row["cost_bps"] == 100.0)[key]) > 0.0
        for key in ("oos_2016_2020_annual_return", "oos_2021_present_annual_return")
    )
    winner = frozen_winner_returns()
    selected_10 = runs[(selected_method, 10.0)]
    common = [(float(row["net_return"]), winner[str(row["realization_date"])]) for row in selected_10 if str(row["realization_date"]) in winner]
    winner_correlation = correlation([row[0] for row in common], [row[1] for row in common])
    promoted = bool(later_positive and bootstrap["pass"] and abs(winner_correlation) <= 0.75)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 14,
        "track": "official_treasury_term_structure",
        "program_sha256": sha256(PROGRAM),
        "curve_snapshot_id": curve_manifest["snapshot_id"],
        "etf_snapshot_id": etf_manifest["snapshot_id"],
        "weekly_price_audit": audit,
        "methods_tested": list(METHODS),
        "costs_bps": list(COSTS),
        "development_selected_method": selected_method,
        "selection_rule": "highest 2003-2015 Sharpe at 10 bps among the two predeclared challengers",
        "multiple_testing_adjusted_oos_bootstrap_at_100bps": bootstrap,
        "both_later_windows_positive_at_100bps": later_positive,
        "correlation_to_frozen_winner_10bps": winner_correlation,
        "correlation_observations": len(common),
        "third_sleeve_promoted": promoted,
        "forward_clock_started": False,
        "limitations": [
            "ETF adjusted-price history comes from a current free snapshot and may contain later revisions.",
            "Treasury observations are publication-date lagged, but the official feed does not expose pre-acquisition revision vintages.",
            "The three ETFs were chosen with hindsight and do not constitute a survivorship-safe universe.",
            "A yield-plus-roll proxy is not a futures contract term-structure backtest.",
            "No result is approved for live trading or guaranteed to make money.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    write_csv(OUTPUT / "selected_returns_10bps.csv", selected_10)
    write_csv(OUTPUT / "selected_returns_100bps.csv", selected_100)
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in ("scoreboard.csv", "selected_returns_10bps.csv", "selected_returns_100bps.csv")}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    selected_row = next(row for row in scoreboard if row["method"] == selected_method and row["cost_bps"] == 10.0)
    report = "\n".join([
        "# Official Treasury Term-Structure Challenger — Batch 14", "",
        f"Development selection chose **{selected_method}**. At 10 bps it produced **{float(selected_row['full_annual_return']) * 100:.2f}%** annual return, **{float(selected_row['full_sharpe_zero_rf']):.3f}** Sharpe, and **{float(selected_row['full_max_drawdown']) * 100:.2f}%** maximum drawdown.", "",
        f"At 100 bps, both later windows positive: **{later_positive}**. Multiple-testing-adjusted OOS bootstrap passed: **{bootstrap['pass']}** (lower annual-return bound {float(bootstrap['annual_return_lower_bound']) * 100:.2f}%).", "",
        f"Correlation to the frozen winner: **{winner_correlation:.3f}** over **{len(common)}** common weeks.", "",
        f"Third-sleeve promotion: **{promoted}**. This is retrospective research with revision and universe limitations; it is not live-trading approval.", "",
    ])
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({
        "selected_method": selected_method,
        "annual_return_10bps": selected_row["full_annual_return"],
        "sharpe_10bps": selected_row["full_sharpe_zero_rf"],
        "max_drawdown_10bps": selected_row["full_max_drawdown"],
        "both_later_windows_positive_100bps": later_positive,
        "bootstrap_pass_100bps": bootstrap["pass"],
        "correlation_to_frozen_winner": winner_correlation,
        "third_sleeve_promoted": promoted,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
