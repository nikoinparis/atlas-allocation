#!/usr/bin/env python3
"""Build the causal factor panel and run its fixed non-ML benchmark."""

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

from src.systematic_trader.cross_sectional_factors import (
    FEATURES,
    asset_features,
    capped_inverse_volatility_weights,
    fixed_composite_scores,
    minimum_allowed_asof,
    monthly_decision_dates,
    percentile_ranks,
)
from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.term_structure_challenger import correlation
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

PROGRAM = ROOT / "config/cross_sectional_factor_program_v1.json"
STORE = ROOT / "data/vintages"
UNIVERSE = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/cross_sectional_factor_baseline_batch_16"
START = "2006-01-01"
COSTS = (10.0, 50.0, 100.0)
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_BLOCK_MONTHS = 3


def latest_free_manifest() -> dict[str, object]:
    manifests = [item for item in SnapshotStore(STORE).manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    if not manifests:
        raise RuntimeError("no free ETF snapshot exists")
    return max(manifests, key=lambda item: str(item["observed_at_utc"]))


def build_dataset(
    dates: list[str], assets: list[str], prices: dict[str, dict[str, float | None]]
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]], dict[str, object]]:
    index_by_date = {day: index for index, day in enumerate(dates)}
    rows: list[dict[str, object]] = []
    by_decision: dict[str, list[dict[str, object]]] = {}
    maximum_feature_date = ""
    timing_violations = 0
    for decision in monthly_decision_dates(dates):
        index = index_by_date[decision]
        if index < 53 or index + 4 >= len(dates) or decision < START:
            continue
        asof_index = index - 1
        feature_asof = dates[asof_index]
        maximum_feature_date = max(maximum_feature_date, feature_asof)
        timing_violations += feature_asof > minimum_allowed_asof(decision)
        provisional = []
        for asset in assets:
            history = [prices[dates[offset]][asset] for offset in range(asof_index - 52, asof_index + 1)]
            decision_price, label_price = prices[decision][asset], prices[dates[index + 4]][asset]
            if any(value is None for value in history) or decision_price is None or label_price is None:
                continue
            features = asset_features([float(value) for value in history], asof_date=feature_asof)
            provisional.append({
                "decision_date": decision,
                "feature_asof_date": feature_asof,
                "label_end_date": dates[index + 4],
                "asset": asset,
                **{feature: features[feature] for feature in FEATURES},
                "forward_4w_return": float(label_price) / float(decision_price) - 1.0,
            })
        if len(provisional) < 5:
            continue
        mean_forward = statistics.fmean(float(row["forward_4w_return"]) for row in provisional)
        for row in provisional:
            row["forward_4w_relative_return"] = float(row["forward_4w_return"]) - mean_forward
        rows.extend(provisional)
        by_decision[decision] = provisional
    return rows, by_decision, {
        "rows": len(rows),
        "monthly_decisions": len(by_decision),
        "assets_configured": len(assets),
        "minimum_assets_per_decision": min(len(value) for value in by_decision.values()),
        "maximum_assets_per_decision": max(len(value) for value in by_decision.values()),
        "feature_timing_violations": timing_violations,
        "feature_information_lag_weeks": 1,
        "label_horizon_weeks": 4,
        "maximum_feature_asof_date": maximum_feature_date,
    }


def decision_weights(
    by_decision: dict[str, list[dict[str, object]]], program: dict[str, object]
) -> tuple[dict[str, dict[str, float]], list[dict[str, object]], list[dict[str, object]]]:
    fixed = program["fixed_baseline"]
    score_weights = {key: float(value) for key, value in fixed["weights"].items()}
    top_n = int(fixed["top_n"])
    maximum = float(fixed["maximum_asset_weight"])
    histories: dict[str, dict[str, float]] = {}
    rank_ic_rows = []
    holdings_rows = []
    for decision, rows in by_decision.items():
        scores = fixed_composite_scores(rows, score_weights)
        selected = sorted(scores, key=lambda asset: (scores[asset], asset), reverse=True)[:top_n]
        volatility = {str(row["asset"]): float(row["volatility_26w"]) for row in rows}
        weights = capped_inverse_volatility_weights(selected, volatility, maximum)
        histories[decision] = weights
        for asset, weight in sorted(weights.items()):
            holdings_rows.append({"decision_date": decision, "asset": asset, "score": scores[asset], "weight": weight})
        target_ranks = percentile_ranks({str(row["asset"]): float(row["forward_4w_relative_return"]) for row in rows})
        score_ranks = percentile_ranks(scores)
        assets = sorted(scores)
        rank_ic_rows.append({
            "decision_date": decision,
            "label_end_date": rows[0]["label_end_date"],
            "assets": len(assets),
            "rank_ic": correlation([score_ranks[asset] for asset in assets], [target_ranks[asset] for asset in assets]),
        })
    return histories, rank_ic_rows, holdings_rows


def simulate(
    dates: list[str], assets: list[str], prices: dict[str, dict[str, float | None]],
    histories: dict[str, dict[str, float]], cost_bps: float,
) -> list[dict[str, object]]:
    current: dict[str, float] = {}
    periods = []
    for index in range(len(dates) - 1):
        decision, realization = dates[index], dates[index + 1]
        if decision < START:
            continue
        turnover = 0.0
        if decision in histories:
            target = histories[decision]
            if not current:
                turnover = 1.0
            else:
                turnover = 0.5 * sum(abs(target.get(asset, 0.0) - current.get(asset, 0.0)) for asset in set(target) | set(current))
            current = target
        if not current:
            continue
        gross = 0.0
        for asset, weight in current.items():
            before, after = prices[decision][asset], prices[realization][asset]
            if before is None or after is None:
                raise RuntimeError(f"selected asset {asset} lacks a price for {decision} -> {realization}")
            gross += weight * (float(after) / float(before) - 1.0)
        cost = turnover * cost_bps / 10_000.0
        periods.append({
            "decision_date": decision,
            "realization_date": realization,
            "cost_bps": cost_bps,
            "gross_return": gross,
            "turnover": turnover,
            "cost": cost,
            "net_return": gross - cost,
        })
    return periods


def summarize(periods: list[dict[str, object]], start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    selected = [row for row in periods if start <= str(row["realization_date"]) <= end]
    metric = performance_metrics([float(row["net_return"]) for row in selected]).to_dict()
    metric["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in selected) * 52.0
    return metric


def rank_ic_bootstrap(rows: list[dict[str, object]]) -> dict[str, float | int | bool]:
    values = [float(row["rank_ic"]) for row in rows]
    generator = random.Random(20260809)
    means = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        while len(sample) < len(values):
            start = generator.randrange(len(values))
            sample.extend(values[(start + offset) % len(values)] for offset in range(BOOTSTRAP_BLOCK_MONTHS))
        means.append(statistics.fmean(sample[:len(values)]))
    ordered = sorted(means)
    lower = ordered[math.floor(0.05 * (len(ordered) - 1))]
    return {
        "months": len(values),
        "mean_rank_ic": statistics.fmean(values),
        "positive_month_share": sum(value > 0.0 for value in values) / len(values),
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "block_months": BOOTSTRAP_BLOCK_MONTHS,
        "one_sided_95pct_lower_mean_rank_ic": lower,
        "pass": lower > 0.0,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    manifest = latest_free_manifest()
    snapshot_id = str(manifest["snapshot_id"])
    assets = sorted(json.loads(UNIVERSE.read_text(encoding="utf-8"))["symbols"])
    dates, prices, weekly_audit = prepare_weekly_adjusted_prices(
        STORE / snapshot_id / "payload/prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2004, 1, 2), expected_symbols=assets,
    )
    dataset, by_decision, dataset_audit = build_dataset(dates, assets, prices)
    if dataset_audit["feature_timing_violations"]:
        raise RuntimeError("factor dataset contains a timing violation")
    histories, rank_ic_rows, holdings_rows = decision_weights(by_decision, program)
    bootstrap = rank_ic_bootstrap(rank_ic_rows)
    score_rows = []
    period_tables = {}
    for cost in COSTS:
        periods = simulate(dates, assets, prices, histories, cost)
        period_tables[cost] = periods
        score_rows.append({
            "variant": "fixed_cross_sectional_factor_rank",
            "cost_bps": cost,
            **{f"full_{key}": value for key, value in summarize(periods).items()},
            **{f"development_{key}": value for key, value in summarize(periods, "2006-01-01", "2015-12-31").items()},
            **{f"oos_2016_2020_{key}": value for key, value in summarize(periods, "2016-01-01", "2020-12-31").items()},
            **{f"oos_2021_present_{key}": value for key, value in summarize(periods, "2021-01-01").items()},
        })
    at_100 = next(row for row in score_rows if row["cost_bps"] == 100.0)
    later_positive = float(at_100["oos_2016_2020_annual_return"]) > 0.0 and float(at_100["oos_2021_present_annual_return"]) > 0.0
    # Read-only reconstruction of the frozen benchmark; it does not mutate its files or clock.
    from scripts.run_treasury_term_structure_batch_14 import frozen_winner_returns
    winner = frozen_winner_returns()
    common = [
        (float(row["net_return"]), winner[str(row["realization_date"])])
        for row in period_tables[10.0] if str(row["realization_date"]) in winner
    ]
    winner_correlation = correlation([row[0] for row in common], [row[1] for row in common])
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 16,
        "track": "cross_sectional_factor_fixed_baseline",
        "source_repositories": ["microsoft/qlib", "initial-d/ml-quant-trading"],
        "program_sha256": sha256(PROGRAM),
        "source_snapshot_id": snapshot_id,
        "weekly_data_audit": weekly_audit,
        "factor_dataset_audit": dataset_audit,
        "rank_ic_evidence": bootstrap,
        "both_later_windows_positive_at_100bps": later_positive,
        "correlation_to_frozen_winner_10bps": winner_correlation,
        "correlation_observations": len(common),
        "eligible_as_ml_common_baseline": True,
        "promoted_to_frozen_portfolio": False,
        "reason_not_promoted": "This establishes the common factor baseline for ML; the current-ETF universe is survivorship-prone and there is no untouched forward record.",
        "limitations": [
            "The configured ETF universe was selected with hindsight and excludes dead or replaced funds.",
            "Adjusted price history comes from a current free snapshot and can contain later revisions.",
            "The fixed recipe was designed after seeing the broad history, so later subperiods are retrospective diagnostics rather than untouched evidence.",
            "Factor rank IC measures cross-sectional ordering, not guaranteed portfolio profit.",
        ],
        "live_trading_approved": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "factor_dataset.csv", dataset)
    write_csv(OUTPUT / "monthly_rank_ic.csv", rank_ic_rows)
    write_csv(OUTPUT / "holdings.csv", holdings_rows)
    write_csv(OUTPUT / "scoreboard.csv", score_rows)
    write_csv(OUTPUT / "returns_10bps.csv", period_tables[10.0])
    for name in ("factor_dataset.csv", "monthly_rank_ic.csv", "holdings.csv", "scoreboard.csv", "returns_10bps.csv"):
        result.setdefault("artifacts", {})[name] = {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    at_10 = next(row for row in score_rows if row["cost_bps"] == 10.0)
    report = "\n".join([
        "# Cross-Sectional Factor Baseline — Batch 16", "",
        f"The causal panel contains **{dataset_audit['rows']:,} asset-month rows** across **{dataset_audit['monthly_decisions']} monthly decisions**. All features stop one completed week before their decision; timing violations: **0**.", "",
        f"At 10 bps the fixed, non-ML ranker produced **{float(at_10['full_annual_return']) * 100:.2f}%** annual return, **{float(at_10['full_sharpe_zero_rf']):.3f}** Sharpe, and **{float(at_10['full_max_drawdown']) * 100:.2f}%** maximum drawdown.", "",
        f"Mean monthly rank IC was **{float(bootstrap['mean_rank_ic']):.4f}**; its one-sided serial-block-bootstrap lower bound was **{float(bootstrap['one_sided_95pct_lower_mean_rank_ic']):.4f}**. Rank-IC gate passed: **{bootstrap['pass']}**.", "",
        f"Both later windows remained profitable at 100 bps: **{later_positive}**.", "",
        f"Correlation to the frozen winner was **{winner_correlation:.3f}** over **{len(common)}** common weeks.", "",
        "This is now the mandatory common baseline for cross-sectional ML. It is not promoted because the universe is survivorship-prone, the data are a current free vintage, and no untouched forward clock exists.", "",
    ])
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({
        "dataset_rows": dataset_audit["rows"],
        "monthly_decisions": dataset_audit["monthly_decisions"],
        "annual_return_10bps": at_10["full_annual_return"],
        "sharpe_10bps": at_10["full_sharpe_zero_rf"],
        "max_drawdown_10bps": at_10["full_max_drawdown"],
        "mean_rank_ic": bootstrap["mean_rank_ic"],
        "rank_ic_gate_pass": bootstrap["pass"],
        "both_later_windows_positive_100bps": later_positive,
        "correlation_to_frozen_winner": winner_correlation,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
