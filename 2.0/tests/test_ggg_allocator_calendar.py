import pandas as pd


def test_incomplete_final_friday_is_not_calendar_month_end():
    date = pd.Timestamp("2026-08-07")
    assert (date + pd.Timedelta(days=7)).month == date.month


def test_actual_final_friday_is_calendar_month_end():
    date = pd.Timestamp("2026-07-31")
    assert (date + pd.Timedelta(days=7)).month != date.month
