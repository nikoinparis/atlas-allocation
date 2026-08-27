"""Small, deterministic two-state Gaussian Markov model for defensive scaling."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TwoStateGaussianMarkov:
    initial: tuple[float, float]
    transition: tuple[tuple[float, float], tuple[float, float]]
    means: tuple[float, float]
    variances: tuple[float, float]
    stress_state: int


def _density(value: float, mean: float, variance: float) -> float:
    variance = max(float(variance), 1e-10)
    return math.exp(-0.5 * (value - mean) ** 2 / variance) / math.sqrt(2.0 * math.pi * variance)


def _normalize(values: Sequence[float]) -> list[float]:
    total = sum(values)
    if total <= 0.0 or not math.isfinite(total):
        return [1.0 / len(values)] * len(values)
    return [value / total for value in values]


def fit_two_state_gaussian_markov(
    observations: Sequence[float], *, iterations: int = 100, transition_persistence: float = 0.95
) -> TwoStateGaussianMarkov:
    """Fit a two-state model by scaled Baum-Welch on a development window only."""
    values = [float(value) for value in observations]
    if len(values) < 52 or any(not math.isfinite(value) for value in values):
        raise ValueError("at least 52 finite development observations are required")
    if not 0.5 < transition_persistence < 1.0 or iterations < 1:
        raise ValueError("valid persistence and positive iteration count required")
    ordered = sorted(values)
    means = [ordered[len(ordered) // 4], ordered[3 * len(ordered) // 4]]
    variance = max(statistics.pvariance(values), 1e-8)
    variances = [variance, variance]
    initial = [0.5, 0.5]
    transition = [
        [transition_persistence, 1.0 - transition_persistence],
        [1.0 - transition_persistence, transition_persistence],
    ]
    for _ in range(iterations):
        emissions = [[_density(value, means[state], variances[state]) for state in range(2)] for value in values]
        alpha: list[list[float]] = []
        alpha.append(_normalize([initial[state] * emissions[0][state] for state in range(2)]))
        for time in range(1, len(values)):
            alpha.append(_normalize([
                emissions[time][state] * sum(alpha[time - 1][prior] * transition[prior][state] for prior in range(2))
                for state in range(2)
            ]))
        beta = [[1.0, 1.0] for _ in values]
        for time in range(len(values) - 2, -1, -1):
            beta[time] = _normalize([
                sum(
                    transition[state][nxt] * emissions[time + 1][nxt] * beta[time + 1][nxt]
                    for nxt in range(2)
                )
                for state in range(2)
            ])
        gamma = [_normalize([alpha[time][state] * beta[time][state] for state in range(2)]) for time in range(len(values))]
        xi: list[list[list[float]]] = []
        for time in range(len(values) - 1):
            flat = [
                alpha[time][state] * transition[state][nxt] * emissions[time + 1][nxt] * beta[time + 1][nxt]
                for state in range(2) for nxt in range(2)
            ]
            normalized = _normalize(flat)
            xi.append([[normalized[state * 2 + nxt] for nxt in range(2)] for state in range(2)])
        initial = gamma[0]
        for state in range(2):
            denominator = max(sum(gamma[time][state] for time in range(len(values) - 1)), 1e-12)
            transition[state] = [
                sum(xi[time][state][nxt] for time in range(len(xi))) / denominator
                for nxt in range(2)
            ]
            transition[state] = _normalize(transition[state])
            weight = max(sum(row[state] for row in gamma), 1e-12)
            means[state] = sum(row[state] * value for row, value in zip(gamma, values)) / weight
            variances[state] = max(
                sum(row[state] * (value - means[state]) ** 2 for row, value in zip(gamma, values)) / weight,
                1e-8,
            )
    stress = 0 if means[0] < means[1] else 1
    return TwoStateGaussianMarkov(
        initial=(initial[0], initial[1]),
        transition=((transition[0][0], transition[0][1]), (transition[1][0], transition[1][1])),
        means=(means[0], means[1]),
        variances=(variances[0], variances[1]),
        stress_state=stress,
    )


def causal_stress_probabilities(
    observations: Sequence[float], model: TwoStateGaussianMarkov
) -> list[float]:
    """Probability used for period t, based only on observations through t-1."""
    probabilities = list(model.initial)
    result: list[float] = []
    for value in observations:
        result.append(probabilities[model.stress_state])
        posterior = _normalize([
            probabilities[state] * _density(float(value), model.means[state], model.variances[state])
            for state in range(2)
        ])
        probabilities = [
            sum(posterior[prior] * model.transition[prior][state] for prior in range(2))
            for state in range(2)
        ]
        probabilities = _normalize(probabilities)
    return result


def scaled_returns(
    gross_returns: Sequence[float],
    underlying_turnover: Sequence[float],
    stress_probabilities: Sequence[float],
    *,
    cost_bps: float,
    minimum_exposure: float = 0.5,
) -> tuple[list[float], list[float]]:
    if not (len(gross_returns) == len(underlying_turnover) == len(stress_probabilities)):
        raise ValueError("all regime-scaling inputs must have equal length")
    if not 0.0 <= minimum_exposure <= 1.0 or cost_bps < 0.0:
        raise ValueError("valid minimum exposure and nonnegative costs required")
    cost = float(cost_bps) / 10000.0
    exposures = [1.0 - (1.0 - minimum_exposure) * float(probability) for probability in stress_probabilities]
    returns: list[float] = []
    previous = 0.0
    for gross, turnover, exposure in zip(gross_returns, underlying_turnover, exposures):
        underlying_cost = exposure * float(turnover) * cost
        overlay_cost = abs(exposure - previous) * cost
        returns.append(exposure * float(gross) - underlying_cost - overlay_cost)
        previous = exposure
    return returns, exposures
