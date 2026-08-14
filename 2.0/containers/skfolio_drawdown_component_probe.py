#!/usr/bin/env python3
"""Offline invariant probe for the bounded skfolio drawdown component."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from skfolio import RiskMeasure
from skfolio.optimization import MeanRisk, ObjectiveFunction


def fit_weights(returns: pd.DataFrame, risk_measure: RiskMeasure) -> np.ndarray:
    model = MeanRisk(
        objective_function=ObjectiveFunction.MINIMIZE_RISK,
        risk_measure=risk_measure,
        min_weights=0.0,
        max_weights=0.35,
        solver="CLARABEL",
    )
    model.fit(returns)
    return np.asarray(model.weights_, dtype=float)


def main() -> None:
    rng = np.random.default_rng(2026083801)
    common = rng.normal(0.0002, 0.006, size=(260, 1))
    noise = rng.normal(0.0, 0.009, size=(260, 8))
    returns = pd.DataFrame(common + noise, columns=[f"asset_{i}" for i in range(8)])
    training = returns.iloc[:200].copy()
    changed_future = returns.copy()
    changed_future.iloc[200:] = changed_future.iloc[200:] * -7.0 + 0.03
    results = {}
    all_pass = True
    for risk_measure in (
        RiskMeasure.CDAR,
        RiskMeasure.MAX_DRAWDOWN,
        RiskMeasure.EDAR,
        RiskMeasure.ULCER_INDEX,
    ):
        first = fit_weights(training, risk_measure)
        repeated = fit_weights(training, risk_measure)
        prior_from_changed = fit_weights(changed_future.iloc[:200], risk_measure)
        checks = {
            "finite": bool(np.isfinite(first).all()),
            "nonnegative": bool((first >= -1e-10).all()),
            "maximum_weight_at_most_0_35": bool(first.max() <= 0.35000001),
            "sum_to_one": bool(abs(first.sum() - 1.0) <= 1e-8),
            "repeat_max_abs_difference": float(np.max(np.abs(first - repeated))),
            "future_perturbation_prior_max_abs_difference": float(np.max(np.abs(first - prior_from_changed))),
        }
        checks["pass"] = bool(
            checks["finite"]
            and checks["nonnegative"]
            and checks["maximum_weight_at_most_0_35"]
            and checks["sum_to_one"]
            and checks["repeat_max_abs_difference"] <= 1e-8
            and checks["future_perturbation_prior_max_abs_difference"] <= 1e-8
        )
        all_pass = all_pass and checks["pass"]
        results[risk_measure.name] = {"weights": first.tolist(), **checks}
    print(json.dumps({"program": "skfolio_drawdown_component_qualification_v1", "risk_measures": results, "all_pass": all_pass}, indent=2, sort_keys=True))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
