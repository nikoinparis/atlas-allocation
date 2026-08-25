#!/usr/bin/env python3
"""Run the predeclared research-only Indonesia dynamic-breadth challenger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_idx80_survival_diagnostic_v1 import (  # noqa: E402
    active_members,
    historical_features,
    metrics,
    portfolio_path,
    sha256,
)
from src.systematic_trader.indonesia_equity import (  # noqa: E402
    IndonesiaResearchSpec,
    build_research_target,
)


CONFIG = ROOT / "config" / "indonesia_dynamic_breadth_challenger_v1.json"
PRICE_ROOT = ROOT / "data" / "indonesia_idx80_extended_price_vintages"
SUPPLEMENT_ROOT = ROOT / "data" / "indonesia_idx80_inactive_price_supplement_vintages"
OUTPUT_ROOT = ROOT / "evidence" / "indonesia_dynamic_breadth_challenger_v1"


def load_frozen_inputs(
    price_root: Path, supplemental_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, object], Path, Path]:
    price_vintage = (price_root / "LATEST").read_text(encoding="utf-8").strip()
    source = price_root / price_vintage
    price_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for name, metadata in price_manifest["files"].items():
        if sha256(source / name) != metadata["sha256"]:
            raise ValueError(f"source hash mismatch: {name}")

    supplemental_vintage = (supplemental_root / "LATEST").read_text(encoding="utf-8").strip()
    supplemental_source = supplemental_root / supplemental_vintage
    supplemental_manifest = json.loads(
        (supplemental_source / "manifest.json").read_text(encoding="utf-8")
    )
    for name, metadata in supplemental_manifest["files"].items():
        if sha256(supplemental_source / name) != metadata["sha256"]:
            raise ValueError(f"supplemental source hash mismatch: {name}")

    prices = pd.read_csv(source / "prices.csv")
    supplement = pd.read_csv(supplemental_source / "prices.csv")
    replaced = set(supplement["ticker"])
    prices = pd.concat(
        [prices[~prices["ticker"].isin(replaced)], supplement], ignore_index=True
    )
    prices["observation_date"] = pd.to_datetime(prices["observation_date"])
    prices["local_ticker"] = prices["ticker"].map(
        lambda value: value[:-3] if str(value).endswith(".JK") else value
    )
    for column in ("close", "adjusted_close", "volume"):
        prices[column] = pd.to_numeric(prices[column], errors="coerce")

    membership = pd.read_csv(source / "idx80_membership.csv")
    membership["effective_from"] = pd.to_datetime(membership["effective_from"])
    membership["effective_to"] = pd.to_datetime(membership["effective_to"])
    membership["available_at"] = pd.to_datetime(membership["available_at"], utc=True)
    return prices, membership, price_manifest, supplemental_manifest, source, supplemental_source


def breadth_state(
    prices: pd.DataFrame,
    eligible: list[str],
    decision: pd.Timestamp,
    tiers: list[dict[str, object]],
    minimum_names: int,
) -> tuple[float, float, str, int]:
    """Return causal 43-week breadth and its predeclared allocation tier."""
    cutoff = decision.tz_localize(None)
    above: list[bool] = []
    for ticker in sorted(eligible):
        daily = prices[
            (prices["local_ticker"] == ticker)
            & (prices["observation_date"] < cutoff)
            & (prices["adjusted_close"] > 0)
        ].sort_values("observation_date")
        if daily.empty:
            continue
        weekly = daily.assign(
            week_end=daily["observation_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
        ).groupby("week_end", sort=True, as_index=False).tail(1)
        if len(weekly) < 43:
            continue
        window = weekly.tail(43)["adjusted_close"].astype(float)
        above.append(bool(window.iloc[-1] > window.mean()))
    if len(above) < minimum_names:
        return 0.0, 0.0, "insufficient_breadth", len(above)
    breadth = float(sum(above) / len(above))
    ordered = sorted(tiers, key=lambda row: float(row["minimum_breadth_inclusive"]), reverse=True)
    for tier in ordered:
        if breadth >= float(tier["minimum_breadth_inclusive"]):
            return breadth, float(tier["stock_allocation"]), str(tier["state"]), len(above)
    raise ValueError("breadth tiers do not cover zero")


def scale_to_stock_allocation(weights: dict[str, float], stock_allocation: float) -> dict[str, float]:
    stocks = {name: value for name, value in weights.items() if name != "CASH_IDR"}
    scaled = {name: float(value) * stock_allocation for name, value in stocks.items()}
    scaled["CASH_IDR"] = max(0.0, 1.0 - sum(scaled.values()))
    return scaled


def calendar_returns(returns: pd.Series) -> dict[str, float]:
    clean = returns.dropna().astype(float)
    return {
        str(year): float((1.0 + values).prod() - 1.0)
        for year, values in clean.groupby(clean.index.year)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--price-root", type=Path, default=PRICE_ROOT)
    parser.add_argument("--supplemental-price-root", type=Path, default=SUPPLEMENT_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--run-label", default="predeclared-v1")
    args = parser.parse_args()
    resolve = lambda path: path if path.is_absolute() else ROOT / path
    config_path = resolve(args.config)
    price_root = resolve(args.price_root)
    supplement_root = resolve(args.supplemental_price_root)
    output_root = resolve(args.output_root)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    strategy_path = ROOT / str(config["strategy_config"])
    strategy = json.loads(strategy_path.read_text(encoding="utf-8"))["strategy"]
    prices, membership, price_manifest, supplemental_manifest, source, supplemental_source = load_frozen_inputs(
        price_root, supplement_root
    )
    spec = IndonesiaResearchSpec(
        top_n=int(strategy["selection_count"]),
        minimum_eligible_names=int(strategy["minimum_eligible_names"]),
        maximum_name_weight=float(strategy["maximum_name_weight"]),
        minimum_median_daily_value_idr=float(strategy["minimum_median_daily_value_idr"]),
        momentum_weight=float(strategy["signal"]["momentum_52w_skip_4w_weight"]),
        low_volatility_weight=float(strategy["signal"]["low_volatility_26w_weight"]),
    )

    benchmark = prices[prices["ticker"] == "^JKSE"].sort_values("observation_date")
    benchmark = benchmark[
        benchmark["observation_date"] >= pd.Timestamp(config["evaluation"]["start_date"])
    ]
    decision_days = benchmark.groupby(
        benchmark["observation_date"].dt.to_period("M")
    )["observation_date"].min()
    baseline_decisions: list[tuple[pd.Timestamp, dict[str, float]]] = []
    challenger_decisions: list[tuple[pd.Timestamp, dict[str, float]]] = []
    decision_rows: list[dict[str, object]] = []
    target_rows: list[pd.DataFrame] = []
    overlay = config["breadth_overlay"]
    maximum_staleness = int(overlay["maximum_price_staleness_calendar_days"])
    for raw_day in decision_days:
        decision = pd.Timestamp(raw_day).tz_localize("UTC")
        members = active_members(membership, decision)
        if len(members) != 80:
            continue
        features = historical_features(prices, members, decision)
        if not features.empty:
            observed = pd.to_datetime(features["price_observation_date"])
            features = features[
                (decision.tz_localize(None).normalize() - observed).dt.days <= maximum_staleness
            ]
        target, diagnostics = build_research_target(
            features, membership, decision_at=decision, spec=spec
        )
        base_weights = dict(zip(target["ticker"], target["research_weight"].astype(float)))
        eligible = features[
            features["median_daily_value_idr"] >= spec.minimum_median_daily_value_idr
        ]["ticker"].tolist()
        breadth, allocation, state, breadth_names = breadth_state(
            prices,
            eligible,
            decision,
            list(overlay["tiers"]),
            int(overlay["minimum_names"]),
        )
        challenger_weights = scale_to_stock_allocation(base_weights, allocation)
        baseline_decisions.append((decision, base_weights))
        challenger_decisions.append((decision, challenger_weights))
        candidate = target.copy()
        candidate.insert(0, "decision_date", decision.date().isoformat())
        candidate["baseline_weight"] = candidate["research_weight"]
        candidate["challenger_weight"] = candidate["research_weight"] * allocation
        candidate["breadth"] = breadth
        candidate["stock_allocation"] = allocation
        target_rows.append(candidate)
        decision_rows.append(
            {
                "decision_date": decision.date().isoformat(),
                "point_in_time_members": len(members),
                "eligible_names": len(eligible),
                "breadth_names": breadth_names,
                "breadth": breadth,
                "breadth_state": state,
                "stock_allocation": allocation,
                "selected_names": diagnostics["selected_names"],
                "status": diagnostics["status"],
            }
        )

    adjusted = prices.pivot(index="observation_date", columns="local_ticker", values="adjusted_close")
    asset_returns = adjusted.pct_change(fill_method=None)
    asset_returns = asset_returns.loc[asset_returns["^JKSE"].notna()].copy()
    paths = pd.DataFrame(index=asset_returns.index)
    metric_rows: list[dict[str, object]] = []
    turnover_rows: list[pd.DataFrame] = []
    for cost in config["evaluation"]["cost_bps_one_way"]:
        for label, decisions in (("baseline", baseline_decisions), ("challenger", challenger_decisions)):
            path, ledger = portfolio_path(asset_returns, decisions, cost_bps=float(cost))
            series = f"{label}_net_{cost}bps"
            paths[series] = path
            metric_rows.append({"series": series, **metrics(path)})
            if int(cost) == int(config["evaluation"]["base_cost_bps_one_way"]):
                ledger.insert(0, "portfolio", label)
                turnover_rows.append(ledger)
    paths = paths.dropna(how="all")
    metrics_frame = pd.DataFrame(metric_rows)
    decisions_frame = pd.DataFrame(decision_rows)
    targets_frame = pd.concat(target_rows, ignore_index=True)
    turnover_frame = pd.concat(turnover_rows, ignore_index=True)

    base_cost = int(config["evaluation"]["base_cost_bps_one_way"])
    indexed = metrics_frame.set_index("series")
    baseline = indexed.loc[f"baseline_net_{base_cost}bps"]
    challenger = indexed.loc[f"challenger_net_{base_cost}bps"]
    high_cost = indexed.loc["challenger_net_150bps"]
    base_years = calendar_returns(paths[f"baseline_net_{base_cost}bps"])
    challenger_years = calendar_returns(paths[f"challenger_net_{base_cost}bps"])
    gate = config["challenger_gates"]
    gates = {
        "minimum_monthly_decisions": bool(len(decisions_frame) >= int(gate["minimum_monthly_decisions"])),
        "cagr_at_least_baseline_at_base_cost": bool(challenger["cagr"] >= baseline["cagr"]),
        "sharpe_above_baseline_at_base_cost": bool(challenger["sharpe_zero_rf"] > baseline["sharpe_zero_rf"]),
        "maximum_drawdown_at_least_5pp_better_than_baseline": bool(
            challenger["maximum_drawdown"] >= baseline["maximum_drawdown"] + 0.05
        ),
        "positive_cagr_at_150bps": bool(high_cost["cagr"] > 0.0),
        "no_single_calendar_year_dependency": False,
        "complete_inactive_security_and_delisting_history": False,
        "validated_local_cost_model": False,
        "licensed_total_return_benchmarks": False,
        "untouched_forward_observations": False,
    }
    historical_challenger_pass = all(
        gates[name]
        for name in (
            "minimum_monthly_decisions",
            "cagr_at_least_baseline_at_base_cost",
            "sharpe_above_baseline_at_base_cost",
            "maximum_drawdown_at_least_5pp_better_than_baseline",
            "positive_cagr_at_150bps",
        )
    )
    verdict = "HISTORICAL_CHALLENGER_PASS_DATA_GATED" if historical_challenger_pass else "HISTORICAL_CHALLENGER_FAIL"
    run_id = f"{pd.Timestamp(price_manifest['created_at_utc']).strftime('%Y%m%dT%H%M%SZ')}-{args.run_label}"
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    if destination.exists():
        raise FileExistsError(destination)
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=output_root))
    try:
        paths.to_csv(staging / "daily_paths.csv", index_label="observation_date")
        metrics_frame.to_csv(staging / "metrics.csv", index=False)
        decisions_frame.to_csv(staging / "decisions.csv", index=False)
        targets_frame.to_csv(staging / "targets.csv", index=False)
        turnover_frame.to_csv(staging / "turnover.csv", index=False)
        result = {
            "verdict": verdict,
            "notice": config["notice"],
            "evaluation_start": str(paths.index.min().date()),
            "evaluation_end": str(paths.index.max().date()),
            "monthly_decisions": len(decisions_frame),
            "gates": gates,
            "baseline_50bps": baseline.to_dict(),
            "challenger_50bps": challenger.to_dict(),
            "challenger_150bps": high_cost.to_dict(),
            "baseline_calendar_returns": base_years,
            "challenger_calendar_returns": challenger_years,
            "breadth_state_counts": decisions_frame["breadth_state"].value_counts().to_dict(),
            "performance_claim_authorized": False,
            "investment_recommendation": False,
            "execution_authorized": False,
        }
        (staging / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report = f"""# Indonesia Dynamic Breadth Challenger V1

> **{config['notice']}**

## Verdict: {verdict}

This is a separately registered Indonesian architecture translation. The stock
ranking and sizing rules are identical to the baseline; only total stock versus
cash allocation changes with causal IDX80 breadth.

| Series | CAGR | Cumulative return | Sharpe (0% RF) | Maximum drawdown |
|---|---:|---:|---:|---:|
| Baseline, net {base_cost} bps one-way | {baseline['cagr']:.2%} | {baseline['cumulative_return']:.2%} | {baseline['sharpe_zero_rf']:.2f} | {baseline['maximum_drawdown']:.2%} |
| Breadth challenger, net {base_cost} bps one-way | {challenger['cagr']:.2%} | {challenger['cumulative_return']:.2%} | {challenger['sharpe_zero_rf']:.2f} | {challenger['maximum_drawdown']:.2%} |
| Breadth challenger, net 150 bps one-way | {high_cost['cagr']:.2%} | {high_cost['cumulative_return']:.2%} | {high_cost['sharpe_zero_rf']:.2f} | {high_cost['maximum_drawdown']:.2%} |

The run contains {len(decisions_frame)} monthly decisions from
{paths.index.min().date()} through {paths.index.max().date()}. Breadth states:
{json.dumps(result['breadth_state_counts'], sort_keys=True)}.

## Predeclared gate results

{json.dumps(gates, indent=2, sort_keys=True)}

## Interpretation boundary

- This is not the US Dynamic Breadth-20 strategy.
- Historical prices are vendor-revised research data and benchmarks remain price-only.
- Costs, suspension exits, delistings, and total-return benchmarks remain incomplete.
- No historical result can authorize execution or commercialization.
"""
        (staging / "report.md").write_text(report, encoding="utf-8")
        output_names = [
            "daily_paths.csv", "metrics.csv", "decisions.csv", "targets.csv",
            "turnover.csv", "result.json", "report.md"
        ]
        manifest = {
            "run_id": run_id,
            "purpose": "predeclared research-only Indonesia dynamic breadth challenger",
            "config_sha256": sha256(config_path),
            "strategy_config_sha256": sha256(strategy_path),
            "program_sha256": sha256(Path(__file__)),
            "price_vintage": price_manifest["vintage_id"],
            "price_manifest_sha256": sha256(source / "manifest.json"),
            "supplemental_price_vintage": supplemental_manifest["vintage_id"],
            "supplemental_price_manifest_sha256": sha256(supplemental_source / "manifest.json"),
            "claims": {
                "historical_diagnostic_calculated": True,
                "equivalent_to_us_dynamic_breadth_20": False,
                "performance_claim_authorized": False,
                "investment_recommendation": False,
                "execution_authorized": False,
            },
            "outputs": {
                name: {"bytes": (staging / name).stat().st_size, "sha256": sha256(staging / name)}
                for name in output_names
            },
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.move(str(staging), destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    (output_root / "LATEST").write_text(run_id + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
