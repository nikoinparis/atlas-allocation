"""Stateful selection rules for factor-decay and turnover experiments."""

from __future__ import annotations

import math


def ranked_assets(scores: dict[str, float], *, inverted: bool = False) -> list[str]:
    rows = [(float(score), asset) for asset, score in scores.items() if math.isfinite(score)]
    rows.sort(key=lambda row: (row[0] if inverted else -row[0], row[1]))
    return [asset for _, asset in rows]


def buffered_membership(
    current: list[str], ages: dict[str, int], scores: dict[str, float], *,
    top_n: int, minimum_age: int, entry_buffer: float, inverted: bool = False,
) -> tuple[list[str], dict[str, int], bool]:
    """Replace at most one mature incumbent when an outsider clears a score buffer."""
    transformed = {asset: (-value if inverted else value) for asset, value in scores.items()}
    ranked = ranked_assets(transformed)
    surviving = [asset for asset in current if asset in transformed]
    changed = surviving != current
    selected = list(surviving)
    for asset in ranked:
        if len(selected) >= top_n:
            break
        if asset not in selected:
            selected.append(asset)
            changed = True
    if len(selected) == top_n:
        outsiders = [asset for asset in ranked if asset not in selected]
        replaceable = [asset for asset in selected if ages.get(asset, 0) >= minimum_age]
        if outsiders and replaceable:
            best_outsider = outsiders[0]
            weakest = min(replaceable, key=lambda asset: (transformed[asset], asset))
            if transformed[best_outsider] >= transformed[weakest] + entry_buffer:
                selected[selected.index(weakest)] = best_outsider
                changed = True
    new_ages = {
        asset: ages.get(asset, 0) + 1 if asset in current else 0
        for asset in selected
    }
    return selected, new_ages, changed


def month_end_weekly_dates(dates: list[str]) -> set[str]:
    result = set()
    for index, day in enumerate(dates):
        if index == len(dates) - 1 or dates[index + 1][:7] != day[:7]:
            result.add(day)
    return result
