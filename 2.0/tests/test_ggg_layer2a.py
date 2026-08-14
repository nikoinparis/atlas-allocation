import pandas as pd

from systematic_trader.ggg_layer2a import _schedule


def test_calendar_schedule_does_not_treat_incomplete_last_week_as_month_end():
    index = pd.to_datetime(["2026-07-31", "2026-08-07"])
    targets = pd.DataFrame({"A": [0.25, 0.90], "BIL": [0.75, 0.10]}, index=index)
    result = _schedule(targets, frequency="monthly", legacy_end_of_sample=False)
    assert result.loc[pd.Timestamp("2026-08-07"), "A"] == 0.25


def test_frozen_terminal_position_seeds_post_cutoff_month():
    index = pd.to_datetime(["2026-04-10", "2026-04-17", "2026-04-24"])
    targets = pd.DataFrame({"A": [0.1, 0.8, 0.6], "BIL": [0.9, 0.2, 0.4]}, index=index)
    frozen = pd.DataFrame({"A": [0.3], "BIL": [0.7]}, index=pd.to_datetime(["2026-04-10"]))
    result = _schedule(targets, frequency="monthly", legacy_end_of_sample=False, frozen=frozen, cutoff=pd.Timestamp("2026-04-10"))
    assert result.loc[pd.Timestamp("2026-04-17"), "A"] == 0.3
    assert result.loc[pd.Timestamp("2026-04-24"), "A"] == 0.6
