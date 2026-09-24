"""Decile-ladder shape statistics, shared by every monotonicity screen in this project.

WHY THIS EXISTS (queue item S14, Step 320).

`run_cross_sectional_skill_v1.py` documents monotonicity as the statistic that catches
"a top decile that wins while two through nine are unordered", and applies a 0.5 bar. It does
not catch that shape. Nine tied deciles plus one large top decile scores **+0.522** on its own
pandas/scipy Spearman -- above the bar it was meant to fail.

Nothing measured in this project has ever come near 0.5, so the gap has never been
load-bearing. It becomes load-bearing on the first positive result, which is exactly when it
would be least welcome and least likely to be questioned.

Step 317 then produced the case in the wild, on WorldQuant BRAIN's data:
`mean_news_impact_projection` scored Sharpe 1.44 market-neutral -- clearing BRAIN's submission
bar -- with full-ladder monotonicity **+0.042** and middle-eight **-0.214**. Its entire
top-minus-bottom spread was decile one. Content at one extreme, noise everywhere else.

So the reading is always two numbers, never one:

    full ladder  > bar  AND  middle eight > bar, in the same direction.

`monotonicity_middle_8` drops the extremes and scores deciles 2..9 alone. A real ordering
orders its middle. A concentration effect leaves it flat, undefined, or negative.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ladder_monotonicity(means: pd.Series) -> float:
    """Spearman of decile index against decile mean return, over the whole ladder.

    Uses pandas' spearman, which applies scipy's AVERAGE ranks to ties and returns NaN at zero
    variance. Both matter: an ordinal ranker would score a dead-flat ladder +1.000, which is
    the bug Step 316 found in the BRAIN runner and fixed there.
    """
    if means is None or len(means) < 3:
        return float("nan")
    return float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman"))


def middle_monotonicity(means: pd.Series, drop: int = 1) -> float:
    """The same statistic over the interior of the ladder, extremes removed.

    `drop=1` scores deciles 2..9 of a ten-decile ladder. Returns NaN when fewer than eight
    interior deciles survive, because a shorter ladder cannot distinguish an ordering from
    the concentration it is meant to detect.
    """
    if means is None or len(means) < 2 * drop + 8:
        return float("nan")
    interior = means.iloc[drop:-drop]
    return ladder_monotonicity(interior)


def shape(means: pd.Series, drop: int = 1) -> dict:
    """Both numbers plus the diagnostics that say whether they can be read at all."""
    values = None if means is None else means.to_numpy(dtype=float)
    full = ladder_monotonicity(means)
    middle = middle_monotonicity(means, drop)
    if values is None or len(values) < 3:
        return {"monotonicity": full, "monotonicity_middle_8": middle,
                "top_minus_bottom": float("nan"), "distinct_values": 0,
                "decile_dispersion": float("nan"), "extremes_share_of_spread": float("nan")}
    spread = float(values[-1] - values[0])
    inner = float(values[-2] - values[1]) if len(values) >= 4 else float("nan")
    return {
        "monotonicity": full,
        "monotonicity_middle_8": middle,
        "top_minus_bottom": spread,
        "inner_spread": inner,
        "distinct_values": int(len(np.unique(np.round(values, 10)))),
        "decile_dispersion": float(np.std(values)),
        "extremes_share_of_spread": (
            float(1.0 - inner / spread) if spread and np.isfinite(inner) else float("nan")),
    }


def clears(full: float, middle: float, bar: float = 0.5) -> bool:
    """The declared reading: BOTH must clear, in the same direction.

    This is the whole point of S14. `abs(full) > bar` alone passes a pure concentration effect
    at +0.522, and passes a positive ladder sitting on a negative middle.
    """
    if not (np.isfinite(full) and np.isfinite(middle)):
        return False
    if abs(full) <= bar or abs(middle) <= bar:
        return False
    return np.sign(full) == np.sign(middle)


def verdict(full: float, middle: float, bar: float = 0.5) -> str:
    if not np.isfinite(full):
        return "DEGENERATE -- ladder carries no ordering information"
    if clears(full, middle, bar):
        return "ORDERS ITS DECILES -- full ladder and middle eight both clear"
    if abs(full) > bar:
        return (f"CONCENTRATION in the extremes -- full ladder {full:+.3f} clears but "
                f"middle eight {middle:+.3f} does not")
    return "flat -- no cross-sectional ordering"
