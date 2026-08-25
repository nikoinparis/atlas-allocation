#!/usr/bin/env python3
"""Run a predeclared IDX80 multi-horizon momentum selection challenger."""

from __future__ import annotations

import argparse
import json
import math
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
from scripts.run_indonesia_dynamic_breadth_challenger_v1 import load_frozen_inputs  # noqa: E402
from src.systematic_trader.cross_sectional_factors import percentile_ranks  # noqa: E402
from src.systematic_trader.indonesia_equity import (  # noqa: E402
    CASH_ASSET,
    IndonesiaResearchSpec,
    _capped_inverse_volatility,
    build_research_target,
    normalize_idx_ticker,
    point_in_time_members,
)


CONFIG = ROOT / "config" / "indonesia_multihorizon_momentum_challenger_v1.json"
PRICE_ROOT = ROOT / "data" / "indonesia_idx80_extended_price_vintages"
SUPPLEMENT_ROOT = ROOT / "data" / "indonesia_idx80_inactive_price_supplement_vintages"
OUTPUT_ROOT = ROOT / "evidence" / "indonesia_multihorizon_momentum_challenger_v1"


def medium_momentum_26w_skip_4w(
    prices: pd.DataFrame, tickers: list[str], decision: pd.Timestamp
) -> dict[str, float]:
    """Calculate 26-week momentum ending four weeks before a decision."""
    cutoff = decision.tz_localize(None)
    result: dict[str, float] = {}
    for ticker in sorted(tickers):
        daily = prices[
            (prices["local_ticker"] == ticker)
            & (prices["observation_date"] < cutoff)
            & (prices["adjusted_close"] > 0)
        ].sort_values("observation_date")
        weekly = daily.assign(
            week_end=daily["observation_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
        ).groupby("week_end", sort=True, as_index=False).tail(1)
        if len(weekly) < 31:
            continue
        values = weekly["adjusted_close"].astype(float)
        result[ticker] = float(values.iloc[-5] / values.iloc[-31] - 1.0)
    return result


def build_multihorizon_target(
    features: pd.DataFrame,
    membership: pd.DataFrame,
    *,
    decision_at: pd.Timestamp,
    spec: IndonesiaResearchSpec,
    weights: dict[str, float],
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build the fixed 50/30/20 selection candidate from causal features."""
    required = {
        "ticker", "feature_asof_date", "momentum_52w_skip_4w",
        "momentum_26w_skip_4w", "volatility_26w", "median_daily_value_idr",
    }
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"feature data missing columns: {missing}")
    decision = pd.Timestamp(decision_at)
    decision = decision.tz_localize("UTC") if decision.tzinfo is None else decision.tz_convert("UTC")
    allowed = point_in_time_members(
        membership, decision_at=decision, universe=spec.universe, sharia_only=spec.sharia_only
    )
    rows = features.copy()
    rows["ticker"] = rows["ticker"].map(normalize_idx_ticker)
    rows["feature_asof_date"] = pd.to_datetime(rows["feature_asof_date"], utc=True, errors="coerce")
    if rows["feature_asof_date"].isna().any() or (rows["feature_asof_date"] >= decision).any():
        raise ValueError("candidate features must be valid and strictly before the decision")
    numeric = [
        "momentum_52w_skip_4w", "momentum_26w_skip_4w",
        "volatility_26w", "median_daily_value_idr",
    ]
    for column in numeric:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    finite = rows[numeric].apply(
        lambda column: column.map(lambda value: pd.notna(value) and math.isfinite(float(value)))
    ).all(axis=1)
    rows = rows[
        rows["ticker"].isin(allowed)
        & finite
        & (rows["volatility_26w"] > 0.0)
        & (rows["median_daily_value_idr"] >= spec.minimum_median_daily_value_idr)
    ].sort_values(["feature_asof_date", "ticker"]).drop_duplicates("ticker", keep="last")
    diagnostics: dict[str, object] = {
        "status": "candidate",
        "point_in_time_members": len(allowed),
        "eligible_feature_rows": len(rows),
        "selected_names": 0,
        "cash_weight": 1.0,
        "execution_authorized": False,
    }
    if len(rows) < spec.minimum_eligible_names:
        diagnostics["status"] = "blocked_insufficient_evidence"
        return pd.DataFrame([{"ticker": CASH_ASSET, "research_weight": 1.0, "research_score": pd.NA}]), diagnostics

    long_rank = percentile_ranks(dict(zip(rows["ticker"], rows["momentum_52w_skip_4w"])))
    medium_rank = percentile_ranks(dict(zip(rows["ticker"], rows["momentum_26w_skip_4w"])))
    low_vol_rank = percentile_ranks(dict(zip(rows["ticker"], -rows["volatility_26w"])))
    rows["research_score"] = rows["ticker"].map(
        lambda ticker: weights["momentum_52w_skip_4w"] * long_rank[ticker]
        + weights["momentum_26w_skip_4w"] * medium_rank[ticker]
        + weights["low_volatility_26w"] * low_vol_rank[ticker]
    )
    selected = rows.sort_values(["research_score", "ticker"], ascending=[False, True]).head(spec.top_n).copy()
    risk_budget = min(1.0, len(selected) / spec.top_n)
    allocated = _capped_inverse_volatility(
        dict(zip(selected["ticker"], selected["volatility_26w"])),
        target_weight=risk_budget,
        maximum_weight=spec.maximum_name_weight,
    )
    selected["research_weight"] = selected["ticker"].map(allocated)
    cash_weight = max(0.0, 1.0 - float(selected["research_weight"].sum()))
    target = selected[
        [
            "ticker", "research_weight", "research_score", "momentum_52w_skip_4w",
            "momentum_26w_skip_4w", "volatility_26w", "median_daily_value_idr",
            "feature_asof_date",
        ]
    ].reset_index(drop=True)
    target.loc[len(target), ["ticker", "research_weight"]] = [CASH_ASSET, cash_weight]
    diagnostics.update(
        {"selected_names": len(selected), "cash_weight": cash_weight,
         "maximum_observed_name_weight": max(allocated.values(), default=0.0)}
    )
    return target, diagnostics


def calendar_returns(returns: pd.Series) -> dict[str, float]:
    clean = returns.dropna().astype(float)
    return {str(year): float((1.0 + values).prod() - 1.0) for year, values in clean.groupby(clean.index.year)}


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
    baseline_path = ROOT / str(config["baseline_strategy"])
    baseline_config = json.loads(baseline_path.read_text(encoding="utf-8"))["strategy"]
    prices, membership, price_manifest, supplemental_manifest, source, supplemental_source = load_frozen_inputs(
        price_root, supplement_root
    )
    spec = IndonesiaResearchSpec(
        top_n=int(config["candidate"]["selection_count"]),
        minimum_eligible_names=int(config["candidate"]["minimum_eligible_names"]),
        maximum_name_weight=float(config["candidate"]["maximum_name_weight"]),
        minimum_median_daily_value_idr=float(config["candidate"]["minimum_median_daily_value_idr"]),
    )
    baseline_spec = IndonesiaResearchSpec(
        top_n=int(baseline_config["selection_count"]),
        minimum_eligible_names=int(baseline_config["minimum_eligible_names"]),
        maximum_name_weight=float(baseline_config["maximum_name_weight"]),
        minimum_median_daily_value_idr=float(baseline_config["minimum_median_daily_value_idr"]),
        momentum_weight=float(baseline_config["signal"]["momentum_52w_skip_4w_weight"]),
        low_volatility_weight=float(baseline_config["signal"]["low_volatility_26w_weight"]),
    )
    score_config = config["candidate"]["score"]
    score_weights = {
        "momentum_52w_skip_4w": float(score_config["momentum_52w_skip_4w_weight"]),
        "momentum_26w_skip_4w": float(score_config["momentum_26w_skip_4w_weight"]),
        "low_volatility_26w": float(score_config["low_volatility_26w_weight"]),
    }
    if not math.isclose(sum(score_weights.values()), 1.0, abs_tol=1e-12):
        raise ValueError("candidate score weights must sum to one")

    benchmark = prices[prices["ticker"] == "^JKSE"].sort_values("observation_date")
    benchmark = benchmark[benchmark["observation_date"] >= pd.Timestamp(config["evaluation"]["start_date"])]
    decision_days = benchmark.groupby(benchmark["observation_date"].dt.to_period("M"))["observation_date"].min()
    baseline_decisions: list[tuple[pd.Timestamp, dict[str, float]]] = []
    challenger_decisions: list[tuple[pd.Timestamp, dict[str, float]]] = []
    decision_rows: list[dict[str, object]] = []
    target_rows: list[pd.DataFrame] = []
    staleness = int(config["candidate"]["maximum_price_staleness_calendar_days"])
    for raw_day in decision_days:
        decision = pd.Timestamp(raw_day).tz_localize("UTC")
        members = active_members(membership, decision)
        if len(members) != 80:
            continue
        features = historical_features(prices, members, decision)
        if not features.empty:
            observed = pd.to_datetime(features["price_observation_date"])
            features = features[(decision.tz_localize(None).normalize() - observed).dt.days <= staleness]
        medium = medium_momentum_26w_skip_4w(prices, features["ticker"].tolist(), decision)
        candidate_features = features.copy()
        candidate_features["momentum_26w_skip_4w"] = candidate_features["ticker"].map(medium)
        baseline_target, baseline_diag = build_research_target(
            features, membership, decision_at=decision, spec=baseline_spec
        )
        challenger_target, challenger_diag = build_multihorizon_target(
            candidate_features, membership, decision_at=decision, spec=spec, weights=score_weights
        )
        baseline_weights = dict(zip(baseline_target["ticker"], baseline_target["research_weight"].astype(float)))
        challenger_weights = dict(zip(challenger_target["ticker"], challenger_target["research_weight"].astype(float)))
        baseline_decisions.append((decision, baseline_weights))
        challenger_decisions.append((decision, challenger_weights))
        base_names = {name for name in baseline_weights if name != CASH_ASSET}
        challenger_names = {name for name in challenger_weights if name != CASH_ASSET}
        decision_rows.append(
            {
                "decision_date": decision.date().isoformat(),
                "point_in_time_members": len(members),
                "baseline_selected_names": baseline_diag["selected_names"],
                "challenger_selected_names": challenger_diag["selected_names"],
                "selection_overlap": len(base_names & challenger_names),
                "selection_union": len(base_names | challenger_names),
                "challenger_status": challenger_diag["status"],
            }
        )
        candidate = challenger_target.copy()
        candidate.insert(0, "decision_date", decision.date().isoformat())
        target_rows.append(candidate)

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
    gates = {
        "minimum_monthly_decisions": bool(len(decisions_frame) >= int(config["challenger_gates"]["minimum_monthly_decisions"])),
        "cagr_above_baseline_at_base_cost": bool(challenger["cagr"] > baseline["cagr"]),
        "sharpe_above_baseline_at_base_cost": bool(challenger["sharpe_zero_rf"] > baseline["sharpe_zero_rf"]),
        "maximum_drawdown_no_more_than_5pp_worse_than_baseline": bool(
            challenger["maximum_drawdown"] >= baseline["maximum_drawdown"] - 0.05
        ),
        "positive_cagr_at_150bps": bool(high_cost["cagr"] > 0.0),
        "no_single_calendar_year_dependency": False,
        "complete_inactive_security_and_delisting_history": False,
        "validated_local_cost_model": False,
        "licensed_total_return_benchmarks": False,
        "untouched_forward_observations": False,
    }
    historical_pass = all(
        gates[name] for name in (
            "minimum_monthly_decisions", "cagr_above_baseline_at_base_cost",
            "sharpe_above_baseline_at_base_cost",
            "maximum_drawdown_no_more_than_5pp_worse_than_baseline", "positive_cagr_at_150bps",
        )
    )
    verdict = "HISTORICAL_SELECTION_PASS_DATA_GATED" if historical_pass else "HISTORICAL_SELECTION_FAIL"
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
            "baseline_calendar_returns": calendar_returns(paths[f"baseline_net_{base_cost}bps"]),
            "challenger_calendar_returns": calendar_returns(paths[f"challenger_net_{base_cost}bps"]),
            "average_selection_overlap": float(decisions_frame["selection_overlap"].mean()),
            "performance_claim_authorized": False,
            "investment_recommendation": False,
            "execution_authorized": False,
        }
        (staging / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report = f"""# Indonesia Multi-Horizon Momentum Challenger V1

> **{config['notice']}**

## Verdict: {verdict}

This single predeclared candidate changes only stock ranking: 50% 52-week
momentum skipping four weeks, 30% 26-week momentum skipping four weeks, and 20%
low 26-week volatility. Holdings count, inverse-volatility sizing, liquidity,
staleness, costs, and portfolio constraints are unchanged.

| Series | CAGR | Cumulative return | Sharpe (0% RF) | Maximum drawdown |
|---|---:|---:|---:|---:|
| Baseline, net {base_cost} bps one-way | {baseline['cagr']:.2%} | {baseline['cumulative_return']:.2%} | {baseline['sharpe_zero_rf']:.2f} | {baseline['maximum_drawdown']:.2%} |
| Selection challenger, net {base_cost} bps one-way | {challenger['cagr']:.2%} | {challenger['cumulative_return']:.2%} | {challenger['sharpe_zero_rf']:.2f} | {challenger['maximum_drawdown']:.2%} |
| Selection challenger, net 150 bps one-way | {high_cost['cagr']:.2%} | {high_cost['cumulative_return']:.2%} | {high_cost['sharpe_zero_rf']:.2f} | {high_cost['maximum_drawdown']:.2%} |

The run contains {len(decisions_frame)} monthly decisions from
{paths.index.min().date()} through {paths.index.max().date()}. Average overlap
with the baseline top 12 was {result['average_selection_overlap']:.2f} names.

## Predeclared gate results

{json.dumps(gates, indent=2, sort_keys=True)}

## Interpretation boundary

- This is a historical stock-screen diagnostic, not a recommendation.
- Historical prices are vendor-revised and inactive-security exits remain incomplete.
- Local costs and total-return benchmarks remain unvalidated.
- No historical result can authorize execution or commercialization.
"""
        (staging / "report.md").write_text(report, encoding="utf-8")
        names = ["daily_paths.csv", "metrics.csv", "decisions.csv", "targets.csv", "turnover.csv", "result.json", "report.md"]
        manifest = {
            "run_id": run_id,
            "purpose": "predeclared research-only Indonesia stock-selection challenger",
            "config_sha256": sha256(config_path),
            "baseline_strategy_sha256": sha256(baseline_path),
            "program_sha256": sha256(Path(__file__)),
            "price_vintage": price_manifest["vintage_id"],
            "price_manifest_sha256": sha256(source / "manifest.json"),
            "supplemental_price_vintage": supplemental_manifest["vintage_id"],
            "supplemental_price_manifest_sha256": sha256(supplemental_source / "manifest.json"),
            "claims": {
                "historical_diagnostic_calculated": True,
                "performance_claim_authorized": False,
                "investment_recommendation": False,
                "execution_authorized": False,
            },
            "outputs": {
                name: {"bytes": (staging / name).stat().st_size, "sha256": sha256(staging / name)}
                for name in names
            },
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.move(str(staging), destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    (output_root / "LATEST").write_text(run_id + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
