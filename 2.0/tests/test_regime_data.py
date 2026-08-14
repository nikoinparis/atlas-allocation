import pandas as pd

from systematic_trader.regime_data import (
    completed_fridays,
    normalize_cboe,
    normalize_google,
    splice_frozen_history,
)


def test_cboe_uses_last_available_close_and_builds_slopes():
    index = completed_fridays("2026-01-02", "2026-01-09")
    rows = []
    for date, values in (("2026-01-02", (15, 17, 18)), ("2026-01-08", (20, 19, 21))):
        for name, value in zip(("VIX", "VIX3M", "VIX6M"), values):
            rows.append({"observation_date": date, "series_id": name, "value": value})
    result = normalize_cboe(pd.DataFrame(rows), index)
    assert result.loc[pd.Timestamp("2026-01-09"), "VIX"] == 20
    assert result.loc[pd.Timestamp("2026-01-09"), "slope_1m_3m"] == -1


def test_google_normalization_is_prefix_invariant():
    index = completed_fridays("2023-01-06", "2026-01-02")
    raw = pd.DataFrame({"Date": index})
    for offset, name in enumerate(("recession", "stock market crash", "inflation", "bear market")):
        raw[name] = range(offset, offset + len(index))
    full = normalize_google(raw, index)
    cutoff = pd.Timestamp("2025-01-03")
    short_index = index[index <= cutoff]
    short = normalize_google(raw.loc[raw.Date <= cutoff], short_index)
    pd.testing.assert_frame_equal(full.loc[:cutoff], short)


def test_splice_never_revises_frozen_prefix():
    index = completed_fridays("2026-01-02", "2026-01-30")
    frozen = pd.DataFrame({"x": [1, 2, 3]}, index=index[:3])
    continuation = pd.DataFrame({"x": [10, 20, 30, 40, 50]}, index=index)
    result = splice_frozen_history(frozen, continuation, "2026-01-16")
    assert result.loc[pd.Timestamp("2026-01-16"), "x"] == 3
    assert result.loc[pd.Timestamp("2026-01-23"), "x"] == 40
