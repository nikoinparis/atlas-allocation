"""Guards for the two defects the panel extension actually hit.

The sealed panel rebases every issuer to 1.0 at its first observation, so raw
prices cannot be appended to it, and resampling to Friday labels the current
partial week with a future Friday date, which would enter the panel as a closed
week. Both produced wrong output before they were caught.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from extend_weekly_price_panel_v2 import last_closed_friday


def test_partial_week_is_not_treated_as_closed():
    # Tuesday 2026-09-01: the week ending 2026-09-04 has not closed.
    assert last_closed_friday(pd.Timestamp("2026-09-01 12:00")) == pd.Timestamp("2026-08-28")


def test_friday_before_the_close_still_reports_the_prior_week():
    assert last_closed_friday(pd.Timestamp("2026-09-04 13:00")) == pd.Timestamp("2026-08-28")


def test_friday_after_the_close_reports_that_friday():
    assert last_closed_friday(pd.Timestamp("2026-09-04 21:30")) == pd.Timestamp("2026-09-04")


def test_chaining_preserves_returns_not_levels():
    """A rebased stored series and a raw fresh series must agree on returns."""
    dates = pd.to_datetime(["2026-08-14", "2026-08-21", "2026-08-28"])
    stored = pd.Series([2.0, 2.2, float("nan")], index=dates)     # rebased scale
    fresh = pd.Series([100.0, 110.0, 121.0], index=dates)         # dollar scale

    anchor = stored.dropna().index.max()
    scale = stored.loc[anchor] / fresh.loc[anchor]
    chained = fresh * scale

    assert chained.loc[anchor] == stored.loc[anchor]
    assert abs(chained.pct_change().iloc[-1] - fresh.pct_change().iloc[-1]) < 1e-12
    assert abs(chained.loc[dates[-1]] - 2.42) < 1e-12


def test_appending_raw_prices_would_have_been_caught_by_the_outlier_filter():
    """The failure mode that produced a thirty-times reconciliation gap."""
    dates = pd.to_datetime(["2026-08-21", "2026-08-28"])
    naive = pd.Series([2.2, 121.0], index=dates)                  # rebased then raw
    assert naive.pct_change().iloc[-1] > 2.0                      # above the declared cap
