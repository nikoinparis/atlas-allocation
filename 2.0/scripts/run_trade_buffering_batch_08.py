#!/usr/bin/env python3
"""Evaluate predeclared causal no-trade bands around frozen portfolio v1."""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_covariance_portfolios_batch_06 as baseline
from src.systematic_trader.challenger_buffering import buffer_history
from src.systematic_trader.data_vintage import SnapshotStore, parse_utc
from src.systematic_trader.non_momentum_signals import reconstruct_non_momentum_signals
from src.systematic_trader.point_in_time import compute_path
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import period_slice, run_experiment, selection_score, summarize_periods
from src.systematic_trader.strategy_allocation import cap_non_cash_weights, combine_dynamic_weight_histories
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


OUTPUT = ROOT / "evidence/trade_buffering_batch_08"
LEDGER = ROOT / "evidence/challenger_program_v1/trial_ledger.csv"
SYMMETRIC_BANDS = (0.0, 0.01, 0.025, 0.05, 0.10)
COSTS_BPS = (10.0, 25.0, 50.0, 100.0)
ASYMMETRIC = ((0.05, 0.02),)


def build_inputs():
    portfolio = json.loads(baseline.PORTFOLIO_REGISTRY_PATH.read_text(encoding="utf-8"))["candidates"][0]
    snapshot_id = str(portfolio["source_snapshot_id"])
    store = SnapshotStore(baseline.STORE_ROOT)
    manifest = next(item for item in store.manifests() if item["snapshot_id"] == snapshot_id)
    payload = baseline.STORE_ROOT / snapshot_id / "payload"
    assets = sorted(json.loads(baseline.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, _ = prepare_weekly_adjusted_prices(
        payload / "prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7),
        expected_symbols=assets,
    )
    log_returns = weekly_log_returns(dates, assets, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    trend_signals, _ = reconstruct_five_signals(
        dates=dates, assets=assets, prices=prices, weekly_log_returns=log_returns
    )
    non_momentum, _, _ = reconstruct_non_momentum_signals(
        dates=dates, assets=assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    registry = json.loads(baseline.REGISTRY_PATH.read_text(encoding="utf-8"))
    trend = next(item for item in registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421")
    defensive = next(item for item in registry["candidates"] if item.get("family") == "defensive")
    runs = {
        "trend_v4": run_experiment(
            spec=baseline.make_spec(trend), snapshot_id=snapshot_id, dates=dates,
            assets=baseline.RISK_ASSETS, strategy_panels=trend_signals, prices=prices,
            simple_returns=simple_returns,
        ),
        "defensive": run_experiment(
            spec=baseline.make_spec(defensive), snapshot_id=snapshot_id, dates=dates,
            assets=baseline.RISK_ASSETS, strategy_panels=non_momentum, prices=prices,
            simple_returns=simple_returns,
        ),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = baseline.sleeve_return_panel(runs)
    coefficients, _ = baseline.build_coefficients(
        dates, sleeve_returns, method="minimum_variance",
        lookback=baseline.PRIMARY_LOOKBACK, shrinkage=baseline.PRIMARY_SHRINKAGE,
    )
    targets = cap_non_cash_weights(
        combine_dynamic_weight_histories(dates, histories, coefficients),
        maximum_asset_weight=baseline.MAXIMUM_UNDERLYING_ASSET_WEIGHT,
    )
    return snapshot_id, dates, targets, simple_returns, prices


def configurations():
    for band in SYMMETRIC_BANDS:
        yield f"symmetric_{band:.3f}", band, band, "symmetric"
    for entry, exit_ in ASYMMETRIC:
        yield f"asymmetric_{entry:.3f}_{exit_:.3f}", entry, exit_, "asymmetric"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    snapshot_id, dates, targets, simple_returns, _prices = build_inputs()
    scoreboard: list[dict[str, object]] = []
    audits: dict[str, list[dict[str, object]]] = {}
    periods_by_config: dict[tuple[str, float], list[dict[str, object]]] = {}
    for config_id, entry_band, exit_band, kind in configurations():
        buffered, audit = buffer_history(
            dates, targets, entry_band=entry_band, exit_band=exit_band
        )
        audits[config_id] = audit
        for cost_bps in COSTS_BPS:
            periods, accounting = compute_path(dates, buffered, simple_returns, cost_bps=cost_bps)
            summary = summarize_periods(periods)
            development = summarize_periods(period_slice(periods, "2006-01-01", "2015-12-31"))
            later_1 = summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31"))
            later_2 = summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31"))
            scoreboard.append({
                "configuration_id": config_id,
                "buffer_kind": kind,
                "entry_band": entry_band,
                "exit_band": exit_band,
                "cost_bps": cost_bps,
                **summary,
                "development_sharpe": development.get("sharpe_zero_rf", 0.0),
                "development_selection_score": selection_score(development),
                "oos_2016_2020_sharpe": later_1.get("sharpe_zero_rf", 0.0),
                "oos_2021_present_sharpe": later_2.get("sharpe_zero_rf", 0.0),
                "fully_invested_pass": accounting["fully_invested_pass"],
                "unpriced_exposure_events": accounting["unpriced_exposure_events"],
            })
            periods_by_config[(config_id, cost_bps)] = periods
    # A cost-aware rule is predeclared as band = min(10%, cost in bps / 1000).
    for cost_bps in COSTS_BPS:
        band = min(0.10, cost_bps / 1000.0)
        config_id = f"cost_aware_{cost_bps:.0f}bps"
        buffered, audit = buffer_history(dates, targets, entry_band=band)
        audits[config_id] = audit
        periods, accounting = compute_path(dates, buffered, simple_returns, cost_bps=cost_bps)
        summary = summarize_periods(periods)
        development = summarize_periods(period_slice(periods, "2006-01-01", "2015-12-31"))
        later_1 = summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31"))
        later_2 = summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31"))
        scoreboard.append({
            "configuration_id": config_id, "buffer_kind": "cost_aware",
            "entry_band": band, "exit_band": band, "cost_bps": cost_bps,
            **summary,
            "development_sharpe": development.get("sharpe_zero_rf", 0.0),
            "development_selection_score": selection_score(development),
            "oos_2016_2020_sharpe": later_1.get("sharpe_zero_rf", 0.0),
            "oos_2021_present_sharpe": later_2.get("sharpe_zero_rf", 0.0),
            "fully_invested_pass": accounting["fully_invested_pass"],
            "unpriced_exposure_events": accounting["unpriced_exposure_events"],
        })
        periods_by_config[(config_id, cost_bps)] = periods

    development_rows = [row for row in scoreboard if float(row["cost_bps"]) == 10.0]
    selected = max(development_rows, key=lambda row: (float(row["development_selection_score"]), str(row["configuration_id"])))
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 8,
        "track": "trade_buffering",
        "source_snapshot_id": snapshot_id,
        "external_reference": {
            "entry_id": "ast-0054", "repository": "robcarver17/pysystemtrade",
            "license": "GPL-3.0", "code_copied": False,
            "use": "high-level no-trade-band concept only"
        },
        "configuration_count": len(scoreboard),
        "unique_buffer_rules": len(audits),
        "selection_window": "2006-01-01 through 2015-12-31",
        "selected_at_10_bps": selected,
        "status": "challenger_not_final",
        "limitations": [
            "The historical ETF universe remains survivorship-prone.",
            "Later periods are retrospective diagnostics, not untouched forward evidence.",
            "The accounting model compares target weights and does not model intra-week drift before rebalance.",
            "All tried rules remain in the multiple-testing ledger."
        ]
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    selected_id = str(selected["configuration_id"])
    write_csv(OUTPUT / "selected_buffer_audit.csv", audits[selected_id])
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in scoreboard:
            writer.writerow([
                f"batch08-{row['configuration_id']}-{float(row['cost_bps']):.0f}", 8,
                "trade_buffering", "ast-0054", row["configuration_id"], "completed",
                "retain_for_comparison", "development-selected only after all rules ran",
                "evidence/trade_buffering_batch_08/scoreboard.csv",
            ])
    print(json.dumps({
        "trials": len(scoreboard),
        "selected_at_10_bps": selected,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
