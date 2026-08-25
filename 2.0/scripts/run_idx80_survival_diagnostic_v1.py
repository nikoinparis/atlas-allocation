#!/usr/bin/env python3
"""Run a data-gated preliminary IDX80 strategy survival diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.cross_sectional_factors import asset_features  # noqa: E402
from src.systematic_trader.indonesia_equity import (  # noqa: E402
    IndonesiaResearchSpec,
    build_research_target,
)


PRICE_ROOT = ROOT / "data" / "indonesia_idx80_history_price_vintages"
CONFIG = ROOT / "config" / "indonesia_survival_diagnostic_v1.json"
STRATEGY_CONFIG = ROOT / "config" / "indonesia_equity_research_v1.json"
OUTPUT_ROOT = ROOT / "evidence" / "indonesia_survival_diagnostic_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(returns: pd.Series) -> dict[str, float]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        raise ValueError("return series is empty")
    wealth = (1.0 + clean).cumprod()
    years = len(clean) / 252.0
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(clean.std(ddof=1) * math.sqrt(252.0))
    sharpe = float(clean.mean() / clean.std(ddof=1) * math.sqrt(252.0)) if clean.std(ddof=1) else 0.0
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "cumulative_return": float(wealth.iloc[-1] - 1.0),
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe_zero_rf": sharpe,
        "maximum_drawdown": float(drawdown.min()),
        "daily_observations": int(len(clean)),
    }


def historical_features(
    prices: pd.DataFrame, members: set[str], decision: pd.Timestamp
) -> pd.DataFrame:
    cutoff = decision.tz_localize(None)
    rows: list[dict[str, object]] = []
    for ticker in sorted(members):
        daily = prices[
            (prices["local_ticker"] == ticker) & (prices["observation_date"] < cutoff)
        ].sort_values("observation_date")
        daily = daily[
            (daily["close"] > 0)
            & (daily["adjusted_close"] > 0)
            & (daily["volume"] >= 0)
        ]
        if len(daily) < 63:
            continue
        weekly = daily.copy()
        weekly["week_end"] = weekly["observation_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
        weekly = weekly.groupby("week_end", sort=True, as_index=False).tail(1)
        if len(weekly) < 53:
            continue
        calculated = asset_features(
            weekly["adjusted_close"].astype(float).tolist(),
            asof_date=(decision - pd.Timedelta(nanoseconds=1)).isoformat(),
        )
        liquidity = (daily.tail(63)["close"] * daily.tail(63)["volume"]).median()
        rows.append(
            {
                "ticker": ticker,
                **calculated,
                "median_daily_value_idr": float(liquidity),
                "price_observation_date": daily["observation_date"].iloc[-1].date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def active_members(membership: pd.DataFrame, decision: pd.Timestamp) -> set[str]:
    day = decision.tz_localize(None)
    rows = membership[
        (membership["effective_from"] <= day)
        & (membership["effective_to"] > day)
        & (membership["available_at"] < decision)
    ]
    return set(rows["ticker"])


def turnover(old: dict[str, float], new: dict[str, float]) -> float:
    names = set(old) | set(new)
    return 0.5 * sum(abs(new.get(name, 0.0) - old.get(name, 0.0)) for name in names)


def portfolio_path(
    asset_returns: pd.DataFrame,
    decisions: list[tuple[pd.Timestamp, dict[str, float]]],
    *,
    cost_bps: float,
) -> tuple[pd.Series, pd.DataFrame]:
    result = pd.Series(index=asset_returns.index, dtype=float)
    ledger: list[dict[str, object]] = []
    old = {"CASH_IDR": 1.0}
    for index, (decision, weights) in enumerate(decisions):
        following = decisions[index + 1][0] if index + 1 < len(decisions) else None
        dates = asset_returns.index[asset_returns.index > decision.tz_localize(None)]
        if following is not None:
            dates = dates[dates <= following.tz_localize(None)]
        if len(dates) == 0:
            continue
        traded = turnover(old, weights)
        daily = asset_returns.reindex(index=dates, columns=[x for x in weights if x != "CASH_IDR"])
        weighted = daily.fillna(0.0).mul(
            pd.Series({name: value for name, value in weights.items() if name != "CASH_IDR"}), axis=1
        ).sum(axis=1)
        weighted.iloc[0] -= traded * cost_bps / 10_000.0
        result.loc[dates] = weighted
        ledger.append(
            {
                "decision_date": decision.date().isoformat(),
                "first_return_date": dates[0].date().isoformat(),
                "one_way_turnover": traded,
                "cost_bps": cost_bps,
                "selected_names": sum(name != "CASH_IDR" and value > 0 for name, value in weights.items()),
                "cash_weight": weights.get("CASH_IDR", 0.0),
            }
        )
        old = weights
    return result.dropna(), pd.DataFrame(ledger)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--price-root", type=Path, default=PRICE_ROOT)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--run-label", default="preliminary-v1")
    parser.add_argument("--supplemental-price-root", type=Path)
    args = parser.parse_args()
    price_root = args.price_root if args.price_root.is_absolute() else ROOT / args.price_root
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_root = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    diagnostic_config = json.loads(config_path.read_text(encoding="utf-8"))
    strategy_config = json.loads(STRATEGY_CONFIG.read_text(encoding="utf-8"))
    price_vintage = (price_root / "LATEST").read_text(encoding="utf-8").strip()
    source = price_root / price_vintage
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for name, metadata in source_manifest["files"].items():
        if sha256(source / name) != metadata["sha256"]:
            raise ValueError(f"source hash mismatch: {name}")

    prices = pd.read_csv(source / "prices.csv")
    supplemental_manifest = None
    supplemental_source = None
    if args.supplemental_price_root:
        supplemental_root = (
            args.supplemental_price_root
            if args.supplemental_price_root.is_absolute()
            else ROOT / args.supplemental_price_root
        )
        supplemental_vintage = (supplemental_root / "LATEST").read_text(encoding="utf-8").strip()
        supplemental_source = supplemental_root / supplemental_vintage
        supplemental_manifest = json.loads(
            (supplemental_source / "manifest.json").read_text(encoding="utf-8")
        )
        for name, metadata in supplemental_manifest["files"].items():
            if sha256(supplemental_source / name) != metadata["sha256"]:
                raise ValueError(f"supplemental source hash mismatch: {name}")
        supplement = pd.read_csv(supplemental_source / "prices.csv")
        replaced = set(supplement["ticker"])
        prices = pd.concat([prices[~prices["ticker"].isin(replaced)], supplement], ignore_index=True)
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
    strategy = strategy_config["strategy"]
    spec = IndonesiaResearchSpec(
        top_n=int(strategy["selection_count"]),
        minimum_eligible_names=int(strategy["minimum_eligible_names"]),
        maximum_name_weight=float(strategy["maximum_name_weight"]),
        minimum_median_daily_value_idr=float(strategy["minimum_median_daily_value_idr"]),
        momentum_weight=float(strategy["signal"]["momentum_52w_skip_4w_weight"]),
        low_volatility_weight=float(strategy["signal"]["low_volatility_26w_weight"]),
    )

    benchmark = prices[prices["ticker"] == "^JKSE"].sort_values("observation_date")
    start = pd.Timestamp(diagnostic_config["evaluation"]["start_date"])
    benchmark = benchmark[benchmark["observation_date"] >= start]
    decision_days = benchmark.groupby(benchmark["observation_date"].dt.to_period("M"))["observation_date"].min()
    strategy_decisions: list[tuple[pd.Timestamp, dict[str, float]]] = []
    equal_decisions: list[tuple[pd.Timestamp, dict[str, float]]] = []
    decision_rows: list[dict[str, object]] = []
    target_rows: list[pd.DataFrame] = []
    for raw_day in decision_days:
        decision = pd.Timestamp(raw_day).tz_localize("UTC")
        members = active_members(membership, decision)
        if len(members) != 80:
            continue
        features = historical_features(prices, members, decision)
        maximum_staleness = diagnostic_config["evaluation"].get(
            "maximum_price_staleness_calendar_days"
        )
        if maximum_staleness is not None and not features.empty:
            observed = pd.to_datetime(features["price_observation_date"])
            features = features[(decision.tz_localize(None).normalize() - observed).dt.days <= int(maximum_staleness)]
        target, diagnostics = build_research_target(
            features,
            membership,
            decision_at=decision,
            spec=spec,
        )
        weights = dict(zip(target["ticker"], target["research_weight"].astype(float)))
        eligible = features[
            features["median_daily_value_idr"] >= spec.minimum_median_daily_value_idr
        ]["ticker"].tolist()
        equal_weight = 1.0 / len(eligible) if eligible else 0.0
        equal_weights = {ticker: equal_weight for ticker in eligible}
        equal_weights["CASH_IDR"] = max(0.0, 1.0 - sum(equal_weights.values()))
        strategy_decisions.append((decision, weights))
        equal_decisions.append((decision, equal_weights))
        candidate = target.copy()
        candidate.insert(0, "decision_date", decision.date().isoformat())
        target_rows.append(candidate)
        decision_rows.append(
            {
                "decision_date": decision.date().isoformat(),
                "point_in_time_members": len(members),
                "feature_complete": len(features),
                "eligible_names": len(eligible),
                "selected_names": diagnostics["selected_names"],
                "status": diagnostics["status"],
            }
        )

    adjusted = prices.pivot(index="observation_date", columns="local_ticker", values="adjusted_close")
    asset_returns = adjusted.pct_change(fill_method=None)
    asset_returns = asset_returns.loc[asset_returns["^JKSE"].notna()].copy()
    costs = diagnostic_config["evaluation"]["cost_bps_one_way"]
    path_frame = pd.DataFrame(index=asset_returns.index)
    metric_rows: list[dict[str, object]] = []
    turnover_frame = pd.DataFrame()
    for cost in costs:
        path, ledger = portfolio_path(asset_returns, strategy_decisions, cost_bps=float(cost))
        name = f"strategy_net_{cost}bps"
        path_frame[name] = path
        metric_rows.append({"series": name, **metrics(path)})
        if int(cost) == int(diagnostic_config["evaluation"]["base_cost_bps_one_way"]):
            turnover_frame = ledger
    equal_path, _ = portfolio_path(asset_returns, equal_decisions, cost_bps=50.0)
    path_frame["equal_weight_eligible_net_50bps"] = equal_path
    metric_rows.append({"series": "equal_weight_eligible_net_50bps", **metrics(equal_path)})
    for ticker, name in (("^JKSE", "ihsg_price_index"), ("^JKLQ45", "lq45_price_index")):
        series = asset_returns[ticker].reindex(path_frame.index).dropna()
        series = series[series.index >= path_frame.dropna(how="all").index.min()]
        path_frame[name] = series
        metric_rows.append({"series": name, **metrics(series)})
    path_frame = path_frame.dropna(how="all")
    metrics_frame = pd.DataFrame(metric_rows)
    decisions_frame = pd.DataFrame(decision_rows)
    targets_frame = pd.concat(target_rows, ignore_index=True)

    base_name = f"strategy_net_{diagnostic_config['evaluation']['base_cost_bps_one_way']}bps"
    base = metrics_frame.set_index("series").loc[base_name]
    high_cost = metrics_frame.set_index("series").loc["strategy_net_150bps"]
    ihsg = metrics_frame.set_index("series").loc["ihsg_price_index"]
    lq45 = metrics_frame.set_index("series").loc["lq45_price_index"]
    equal = metrics_frame.set_index("series").loc["equal_weight_eligible_net_50bps"]
    gates = {
        "minimum_monthly_decisions": bool(len(decisions_frame) >= diagnostic_config["survival_gates"]["minimum_monthly_decisions"]),
        "positive_net_cagr_at_base_cost": bool(base["cagr"] > 0),
        "positive_net_cagr_at_150bps": bool(high_cost["cagr"] > 0),
        "minimum_net_sharpe_at_base_cost": bool(base["sharpe_zero_rf"] >= diagnostic_config["survival_gates"]["minimum_net_sharpe_at_base_cost"]),
        "maximum_drawdown_floor": bool(base["maximum_drawdown"] >= diagnostic_config["survival_gates"]["maximum_drawdown_floor"]),
        "no_single_calendar_year_dependency": False,
        "complete_point_in_time_membership_from_2019": bool(
            source_manifest.get("claims", {}).get("membership_complete_from_idx80_launch", False)
        ),
        "complete_delisting_and_inactive_security_history": False,
        "validated_local_cost_model": False,
        "licensed_price_and_benchmark_total_return_data": False,
    }
    better = {
        "net_cagr_above_ihsg": bool(base["cagr"] > ihsg["cagr"]),
        "net_cagr_above_lq45": bool(base["cagr"] > lq45["cagr"]),
        "net_cagr_above_equal_weight_eligible": bool(base["cagr"] > equal["cagr"]),
        "net_sharpe_above_ihsg": bool(base["sharpe_zero_rf"] > ihsg["sharpe_zero_rf"]),
        "net_sharpe_above_lq45": bool(base["sharpe_zero_rf"] > lq45["sharpe_zero_rf"]),
        "net_sharpe_above_equal_weight_eligible": bool(base["sharpe_zero_rf"] > equal["sharpe_zero_rf"]),
    }
    verdict = "INCONCLUSIVE_DATA_GATED"
    run_id = f"{pd.Timestamp(source_manifest['created_at_utc']).strftime('%Y%m%dT%H%M%SZ')}-{args.run_label}"
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    if destination.exists():
        raise FileExistsError(destination)
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=output_root))
    try:
        path_frame.to_csv(staging / "daily_paths.csv", index_label="observation_date")
        metrics_frame.to_csv(staging / "metrics.csv", index=False)
        decisions_frame.to_csv(staging / "decisions.csv", index=False)
        targets_frame.to_csv(staging / "targets.csv", index=False)
        turnover_frame.to_csv(staging / "turnover.csv", index=False)
        result = {
            "verdict": verdict,
            "notice": diagnostic_config["notice"],
            "price_vintage": price_vintage,
            "supplemental_price_vintage": supplemental_manifest["vintage_id"] if supplemental_manifest else None,
            "evaluation_start": str(path_frame.index.min().date()),
            "evaluation_end": str(path_frame.index.max().date()),
            "monthly_decisions": len(decisions_frame),
            "minimum_required_monthly_decisions": diagnostic_config["survival_gates"]["minimum_monthly_decisions"],
            "survival_gates": gates,
            "better_than_indonesia_gates": better,
            "performance_claim_authorized": False,
            "investment_recommendation": False,
            "execution_authorized": False,
        }
        (staging / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        def pct(value: float) -> str:
            return f"{value:.2%}"
        inactive_price_limitation = (
            "- SRIL and WSKT are supplemented from an independently archived university dataset and "
            "excluded after 10 stale calendar days; complete suspension exits and delisting returns remain unavailable."
            if supplemental_manifest
            else "- SRIL and WSKT lack usable historical observations in the Yahoo snapshot, creating survivor/data-availability bias."
        )
        report = f"""# Indonesia Strategy Survival Diagnostic

> **{diagnostic_config['notice']}**

## Verdict: {verdict}

The strategy has {len(decisions_frame)} monthly decisions versus the
predeclared minimum of {diagnostic_config['survival_gates']['minimum_monthly_decisions']}.
Point-in-time membership now spans the February 2019 launch, but pre-2024
records rely partly on archived official-document mirrors and contemporary reports.
The results below are useful for debugging and prioritizing
research, but they cannot establish that the strategy survives Indonesia.

| Series | CAGR | Volatility | Sharpe (0% RF) | Maximum drawdown |
|---|---:|---:|---:|---:|
| Strategy, net 50 bps one-way | {pct(base['cagr'])} | {pct(base['annualized_volatility'])} | {base['sharpe_zero_rf']:.2f} | {pct(base['maximum_drawdown'])} |
| Strategy, net 150 bps one-way | {pct(high_cost['cagr'])} | {pct(high_cost['annualized_volatility'])} | {high_cost['sharpe_zero_rf']:.2f} | {pct(high_cost['maximum_drawdown'])} |
| Equal-weight eligible IDX80, net 50 bps | {pct(equal['cagr'])} | {pct(equal['annualized_volatility'])} | {equal['sharpe_zero_rf']:.2f} | {pct(equal['maximum_drawdown'])} |
| IHSG price index | {pct(ihsg['cagr'])} | {pct(ihsg['annualized_volatility'])} | {ihsg['sharpe_zero_rf']:.2f} | {pct(ihsg['maximum_drawdown'])} |
| LQ45 price index | {pct(lq45['cagr'])} | {pct(lq45['annualized_volatility'])} | {lq45['sharpe_zero_rf']:.2f} | {pct(lq45['maximum_drawdown'])} |

The base-cost comparison gates currently read: CAGR above IHSG **{better['net_cagr_above_ihsg']}**,
CAGR above LQ45 **{better['net_cagr_above_lq45']}**, Sharpe above IHSG
**{better['net_sharpe_above_ihsg']}**, and Sharpe above LQ45
**{better['net_sharpe_above_lq45']}**. Against equal weight, the CAGR hurdle is
**{better['net_cagr_above_equal_weight_eligible']}** and the Sharpe hurdle is
**{better['net_sharpe_above_equal_weight_eligible']}**. These are diagnostic observations, not
a pass, recommendation, or expected return.

## Binding limitations

- Pre-2024 membership is reconstructed evidence, not a complete direct IDX download.
{inactive_price_limitation}
- Yahoo adjusted history is a 2026 vendor-revised snapshot, not vintage prices.
- Delistings and inactive securities are not complete.
- IHSG and LQ45 inputs are price indexes, not licensed total-return benchmarks.
- The 25–150 bps cost grid is provisional; Indonesian fees, taxes, spreads,
  market impact, and lot-size effects are not yet validated.
- The 2019–2026 period is still insufficient to establish independence from a
  particular market, commodity, sector, or macro regime; the formal
  single-calendar-year-dependency gate remains unassessed.

The immutable forward shadow decision remains the cleanest future evidence.
No historical rule or gate should be changed in response to this output.
"""
        (staging / "report.md").write_text(report, encoding="utf-8")
        output_names = ["daily_paths.csv", "metrics.csv", "decisions.csv", "targets.csv", "turnover.csv", "result.json", "report.md"]
        manifest = {
            "run_id": run_id,
            "purpose": "preliminary data-gated Indonesia strategy survival diagnostic",
            "config_sha256": sha256(config_path),
            "strategy_config_sha256": sha256(STRATEGY_CONFIG),
            "program_sha256": sha256(Path(__file__)),
            "price_vintage": price_vintage,
            "price_manifest_sha256": sha256(source / "manifest.json"),
            "supplemental_price_manifest_sha256": (
                sha256(supplemental_source / "manifest.json") if supplemental_source else None
            ),
            "claims": {
                "historical_diagnostic_calculated": True,
                "survival_established": False,
                "better_than_indonesia_established": False,
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
        staging.rename(destination)
        (output_root / "LATEST").write_text(run_id + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
