"""Accounting invariants for daily strategy continuation."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("continuation", Path(__file__).parents[1] / "scripts/build_dashboard_continuation_v1.py")
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


def test_a_close_trade_only_earns_the_next_sessions_return():
    days = pd.bdate_range("2026-11-09", periods=3)
    prices = pd.DataFrame({"A": [100., 110., 110.], "B": [100., 100., 120.]}, index=days)
    rows = engine.continuation(prices, {"A": 1}, {days[1]: {"B": 1}}, 50)
    assert rows[0]["grossReturn"] == pytest.approx(.1)
    assert rows[0]["netReturn"] == pytest.approx(1.1 * .995 - 1)
    assert rows[0]["cost"] == pytest.approx(.0055)
    assert rows[1]["netReturn"] == pytest.approx(.2)
    assert rows[1]["rebalance"] is False


def test_turnover_is_measured_against_drifted_holdings():
    days = pd.bdate_range("2026-11-09", periods=2)
    prices = pd.DataFrame({"A": [100., 200.], "B": [100., 100.]}, index=days)
    row = engine.continuation(prices, {"A": .5, "B": .5}, {days[1]: {"A": .5, "B": .5}}, 50)[0]
    assert row["grossReturn"] == pytest.approx(.5)
    assert row["turnover"] == pytest.approx(1 / 6)
    assert row["netReturn"] == pytest.approx(1.5 * (1 - .005 / 6) - 1)


def test_missing_held_price_is_an_error_not_a_flat_return():
    prices = pd.DataFrame({"A": [100., float("nan")]}, index=pd.bdate_range("2026-11-09", periods=2))
    with pytest.raises(ValueError, match="missing held price"):
        engine.continuation(prices, {"A": 1}, {}, 50)


def test_future_prices_cannot_change_earlier_daily_results():
    days = pd.bdate_range("2026-11-09", periods=5)
    prices = pd.DataFrame({"A": [100., 101., 102., 103., 104.], "B": [100., 99., 101., 102., 103.]}, index=days)
    events = {days[1]: {"A": .4, "B": .6}, days[3]: {"B": 1}}
    original = engine.continuation(prices, {"A": 1}, events, 50)
    prices.loc[days[3]:] *= 10
    changed = engine.continuation(prices, {"A": 1}, events, 50)
    assert original[:2] == changed[:2]


def test_quarterly_sleeves_drift_instead_of_resetting_equal_weights():
    days = pd.date_range("2026-10-02", periods=3, freq="W-FRI")
    prices = pd.DataFrame({"A": [100., 200., 200.], "B": [100., 100., 100.]}, index=days)
    books = engine.drift_books({days[0]: {"A": .5, "B": .5}}, prices)
    assert books[days[1]]["A"] == pytest.approx(2 / 3)
    assert books[days[2]]["B"] == pytest.approx(1 / 3)


def test_invalid_allocation_cannot_create_or_destroy_capital():
    days = pd.bdate_range("2026-11-09", periods=2)
    prices = pd.DataFrame({"A": [100., 100.]}, index=days)
    with pytest.raises(ValueError, match="sum to one"):
        engine.continuation(prices, {"A": 1}, {days[1]: {"A": .7}}, 50)


def test_an_unpriced_new_selection_is_explicitly_budgeted_to_cash():
    days = pd.bdate_range("2026-11-09", periods=2)
    prices = pd.DataFrame({"A": [100., 101.], "B": [float("nan"), float("nan")]}, index=days)
    events, audit = engine.route_unpriced_targets({days[1]: {"A": .8, "B": .2}}, prices)
    assert events[days[1]] == {"A": .8, engine.CASH: .2}
    assert audit == [{"date": "2026-11-10", "symbol": "B", "weightHeldAsCash": .2}]


def test_clock_price_filter_keeps_attribution_quotes_and_drops_unheld_years():
    from build_clock_histories_v1 import held_price_payload
    days = pd.bdate_range("2025-01-01", "2026-11-13")
    levels = {"A": pd.Series(100., index=days)}
    payload = {"records": [{"date": "2026-10-02", "holdings": [{"symbol": "A", "weight": 1}]},
                           {"date": "2026-10-09", "holdings": [{"symbol": "A", "weight": 0}]}]}
    data = held_price_payload(payload, levels, pd.Timestamp("2026-11-13"))["A"]
    assert data[-1]["date"] == "2026-10-09"
    assert data[0]["date"] > "2025-12-31"
    assert {"2026-10-01", "2026-10-02", "2026-10-08", "2026-10-09"} <= {p["date"] for p in data}
