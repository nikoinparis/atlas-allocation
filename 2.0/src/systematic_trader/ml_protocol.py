"""Dependency-free validation helpers for the robust ML protocol."""

from __future__ import annotations


def eligible_training_row(row: dict[str, object], test_start: str) -> bool:
    """Require both the decision and its full label to precede the test block."""
    return str(row["decision_date"]) < test_start and str(row["label_end_date"]) < test_start


def outer_test_years(rows: list[dict[str, object]], first_year: int) -> list[int]:
    return sorted({int(str(row["decision_date"])[:4]) for row in rows if int(str(row["decision_date"])[:4]) >= first_year})


def promotion_gates(
    *, rank_ic_pass: bool, beats_fixed: bool, beats_winner: bool,
    drawdown_pass: bool, later_cost_pass: bool, dependence_pass: bool, controls_pass: bool,
    fold_stability_pass: bool, survivorship_safe: bool, forward_weeks: int,
) -> dict[str, bool]:
    gates = {
        "rank_ic": rank_ic_pass,
        "beats_fixed": beats_fixed,
        "beats_winner": beats_winner,
        "maximum_drawdown": drawdown_pass,
        "later_cost": later_cost_pass,
        "dependence": dependence_pass,
        "negative_controls": controls_pass,
        "fold_stability": fold_stability_pass,
        "survivorship_safe": survivorship_safe,
        "untouched_forward_52w": forward_weeks >= 52,
    }
    gates["all"] = all(gates.values())
    return gates
