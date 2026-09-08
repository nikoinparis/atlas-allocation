"""Which week does a return stamped at date D belong to? Two answers live in this repo.

Step 291 found the valuation book correlating at -0.03 with three strategies it
actually correlates +0.69 with, and a blend that appeared to beat both its
components and does not. Nothing was corrupt. Two artifact families simply
disagree about what a date means, and every cross-series join between them was
silently comparing week t against week t+1.

    WEEK_ENDING   the value at D is the return realised over the week ENDING at D,
                  i.e. price(D) / price(D-1) - 1. This is what the price panels
                  themselves imply and what a standalone script naturally writes.

    FORWARD       the value at D is the return earned over the week FOLLOWING D,
                  i.e. price(D+1) / price(D) - 1. Produced by
                  `series.pct_change().shift(-1)` at line 285 of
                  run_sec_growth_survivorship_retest_v1, which every SEC strategy
                  script imports as `base`. It is a reasonable convention for a
                  decision-indexed path: it puts the decision and its consequence
                  on the same row.

Neither is wrong. Mixing them without saying so is, and there was nothing on
either artifact recording which one it carried.

Use `load_aligned` for anything that joins two return series by date. Use
`detect_convention` when the answer is not known: a long-only equity book has a
market beta near one, so the labelling that produces a sane beta is the labelling
that is right, and a book whose best beta is near zero at every shift is a
different problem than a misdated one.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

WEEK_ENDING = "week_ending"
FORWARD = "forward"

# Everything built on `run_sec_growth_survivorship_retest_v1` inherits FORWARD.
# Listed by the substring that identifies the artifact family, most specific first.
KNOWN_CONVENTIONS: dict[str, str] = {
    "sec_growth_survivorship_retest": FORWARD,
    "cash_conversion_sleeve_path": FORWARD,
    "sec_sector_aware_signal_ensemble": FORWARD,
    "sec_signal_neighborhood_ensemble": FORWARD,
    "sec_cluster_aware_cash_sleeve": FORWARD,
    "sec_regime_increment_tranching": FORWARD,
    "sec_residual_controlled_sleeve": FORWARD,
    # Written standalone against the price panel, so already week-ending.
    "valuation_revival": WEEK_ENDING,
    "valuation_out_of_sample": WEEK_ENDING,
    "dashboard_signals_out_of_sample": WEEK_ENDING,
    "composites_out_of_sample": WEEK_ENDING,
    "crypto_cross_sectional": WEEK_ENDING,
    "finra_short_volume": WEEK_ENDING,
    "form4_opportunistic": WEEK_ENDING,
}


class ConventionError(RuntimeError):
    """Raised when a series' convention cannot be established and must not be guessed."""


def convention_for(path: str | Path) -> str | None:
    text = str(path)
    for marker, convention in KNOWN_CONVENTIONS.items():
        if marker in text:
            return convention
    return None


def to_week_ending(series: pd.Series, convention: str) -> pd.Series:
    """Restate a series on the week-ending grid, which is the panel's own grid."""
    if convention == WEEK_ENDING:
        return series
    if convention == FORWARD:
        # A FORWARD value at D is the week ending D+1, so it moves one week later.
        return series.shift(1)
    raise ConventionError(f"unknown convention {convention!r}")


def detect_convention(series: pd.Series, benchmark: pd.Series,
                      *, minimum_r2: float = 0.10) -> tuple[str, float, float]:
    """Infer the convention by asking which labelling gives a sane equity beta.

    Returns (convention, beta, r_squared). Raises when no labelling clears
    `minimum_r2`, because a series that never looks like an equity book is not a
    misdated one and shifting it would only manufacture a fit.
    """
    best = None
    for convention, shift in ((WEEK_ENDING, 0), (FORWARD, 1)):
        joined = pd.concat({"s": series.shift(shift), "m": benchmark}, axis=1).dropna()
        if len(joined) < 30:
            continue
        beta, intercept = np.polyfit(joined.m, joined.s, 1)
        residual = joined.s - (beta * joined.m + intercept)
        r2 = 1.0 - residual.var() / joined.s.var()
        if best is None or r2 > best[2]:
            best = (convention, float(beta), float(r2))
    if best is None or best[2] < minimum_r2:
        raise ConventionError(
            f"no labelling gives R2 >= {minimum_r2:.2f} against the benchmark "
            f"(best {best[2]:.3f} if any); this series is not simply misdated")
    return best


def load_aligned(path: str | Path, *, root: Path | None = None,
                 benchmark: pd.Series | None = None) -> pd.Series:
    """Read a saved return path and return it on the week-ending grid.

    Every cross-series date join in this project should go through here. If the
    artifact is not in the registry and no benchmark is supplied to infer from,
    this raises rather than assuming -- assuming is what Step 275 did.
    """
    full = Path(path) if root is None else root / path
    frame = pd.read_csv(full)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    frame = frame.dropna(subset=[column]).set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    series = pd.to_numeric(frame[name], errors="coerce").dropna()

    convention = convention_for(path)
    if convention is None:
        if benchmark is None:
            raise ConventionError(
                f"{path} is not in KNOWN_CONVENTIONS and no benchmark was given to infer "
                f"from. Add it to the registry or pass a benchmark; do not guess.")
        convention, _, _ = detect_convention(series, benchmark)
    return to_week_ending(series, convention)
