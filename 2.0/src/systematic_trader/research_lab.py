"""Reproducible experiment and retrospective walk-forward research helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date

from .evaluation import performance_metrics
from .point_in_time import combine_and_smooth, compute_path
from .portfolio_construction import Panel, PortfolioSpec, build_portfolio_weights


@dataclass(frozen=True)
class StrategySpec:
    signals: tuple[str, ...]
    smoothing_weeks: int
    portfolio: PortfolioSpec
    cost_bps: float = 10.0
    rebalance_frequency: str = "monthly"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["signals"] = list(self.signals)
        if self.rebalance_frequency == "monthly":
            result.pop("rebalance_frequency")
        return result


def experiment_id(spec: StrategySpec, snapshot_id: str) -> str:
    payload = {"snapshot_id": snapshot_id, "strategy": spec.to_dict()}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return f"exp-{digest}"


def period_slice(periods: list[dict[str, float | str]], start: str, end: str) -> list[dict[str, float | str]]:
    return [row for row in periods if start <= str(row["realization_date"]) <= end]


def summarize_periods(periods: list[dict[str, float | str]]) -> dict[str, int | float]:
    if not periods:
        return {"observations": 0}
    values = [float(row["net_return"]) for row in periods]
    metrics = performance_metrics(values).to_dict()
    metrics["average_annual_turnover"] = (
        sum(float(row["turnover"]) for row in periods) / len(periods) * 52.0
    )
    metrics["total_cost"] = sum(float(row["cost"]) for row in periods)
    return metrics


def run_experiment(
    *,
    spec: StrategySpec,
    snapshot_id: str,
    dates: list[str],
    assets: list[str],
    strategy_panels: dict[str, Panel],
    prices: Panel,
    simple_returns: Panel,
) -> dict[str, object]:
    missing = [name for name in spec.signals if name not in strategy_panels]
    if missing:
        raise ValueError(f"unknown signal panels: {missing}")
    scores = combine_and_smooth(
        dates, assets, [strategy_panels[name] for name in spec.signals], spec.smoothing_weeks
    )
    weights, rebalance_dates, construction_audit = build_portfolio_weights(
        dates=dates,
        assets=assets,
        scores=scores,
        prices=prices,
        simple_returns=simple_returns,
        spec=spec.portfolio,
        include_sample_endpoint_rebalance=False,
        rebalance_frequency=spec.rebalance_frequency,
    )
    periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=spec.cost_bps)
    return {
        "experiment_id": experiment_id(spec, snapshot_id),
        "source_snapshot_id": snapshot_id,
        "strategy": spec.to_dict(),
        "metrics": {
            "full_history": summarize_periods(periods),
            "development_2006_2015": summarize_periods(period_slice(periods, "2006-01-01", "2015-12-31")),
            "retrospective_oos_2016_2020": summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31")),
            "retrospective_oos_2021_present": summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31")),
        },
        "accounting": accounting,
        "construction_audit": construction_audit,
        "rebalance_dates": len(rebalance_dates),
        "periods": periods,
        "weights": weights,
    }


def selection_score(metrics: dict[str, int | float]) -> float:
    if int(metrics.get("observations", 0)) < 104:
        return float("-inf")
    return float(metrics["sharpe_zero_rf"]) + 0.25 * float(metrics["calmar"])


def retrospective_walk_forward(
    experiments: list[dict[str, object]],
    folds: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, float | str]], dict[str, int | float]]:
    """Select on each past training window, then splice only its later evaluation rows."""
    selections: list[dict[str, object]] = []
    combined: list[dict[str, float | str]] = []
    for fold in folds:
        ranked: list[tuple[float, str, dict[str, object]]] = []
        for experiment in experiments:
            training = summarize_periods(period_slice(
                experiment["periods"], fold["train_start"], fold["train_end"]
            ))
            ranked.append((selection_score(training), str(experiment["experiment_id"]), experiment))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        score, _, selected = ranked[0]
        evaluation = period_slice(selected["periods"], fold["evaluation_start"], fold["evaluation_end"])
        combined.extend(evaluation)
        selections.append({
            **fold,
            "selected_experiment_id": selected["experiment_id"],
            "selection_score": score,
            "training_metrics": summarize_periods(period_slice(
                selected["periods"], fold["train_start"], fold["train_end"]
            )),
            "evaluation_metrics": summarize_periods(evaluation),
        })
    combined.sort(key=lambda row: str(row["realization_date"]))
    dates = [str(row["realization_date"]) for row in combined]
    if len(dates) != len(set(dates)):
        raise ValueError("walk-forward evaluation folds overlap")
    return selections, combined, summarize_periods(combined)
