from __future__ import annotations

import math

import pandas as pd
import pytest

from src.systematic_trader.indonesia_rehearsal import build_weekly_feature_snapshot


def daily_rows(ticker: str, periods: int, *, knowledge: str = "2026-08-22T08:00:00Z") -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=periods)
    return pd.DataFrame(
        {
            "observation_date": dates,
            "ticker": f"{ticker}.JK",
            "close": [100.0 + index * 0.2 for index in range(periods)],
            "adjusted_close": [90.0 + index * 0.2 for index in range(periods)],
            "volume": [10_000_000.0] * periods,
            "knowledge_at_utc": knowledge,
        }
    )


def test_builds_causal_weekly_features_and_exclusions() -> None:
    prices = pd.concat([daily_rows("ABCD", 400), daily_rows("EFGH", 100)], ignore_index=True)
    features, exclusions, weekly = build_weekly_feature_snapshot(
        prices,
        known_at="2026-08-22T08:30:00Z",
        universe_tickers=["ABCD", "EFGH"],
    )
    assert list(features["ticker"]) == ["ABCD"]
    assert features.loc[0, "feature_asof_date"] == "2026-08-22T08:30:00+00:00"
    assert features.loc[0, "weekly_observations"] >= 53
    assert math.isclose(features.loc[0, "median_daily_value_idr"], 1_736_000_000.0)
    assert exclusions[["ticker", "reason"]].to_dict("records") == [
        {"ticker": "EFGH", "reason": "insufficient_weekly_history"}
    ]
    assert set(weekly["ticker"]) == {"ABCD", "EFGH"}
    assert (weekly["observation_date"] <= weekly["week_end"]).all()


def test_rejects_price_rows_not_known_by_snapshot_time() -> None:
    prices = daily_rows("ABCD", 400, knowledge="2026-08-23T08:00:00Z")
    with pytest.raises(ValueError, match="not known"):
        build_weekly_feature_snapshot(
            prices,
            known_at="2026-08-22T08:30:00Z",
            universe_tickers=["ABCD"],
        )


def test_ignores_benchmarks_and_nonmembers() -> None:
    prices = pd.concat(
        [daily_rows("ABCD", 400), daily_rows("WXYZ", 400)], ignore_index=True
    )
    benchmark = daily_rows("ABCD", 10)
    benchmark["ticker"] = "^JKSE"
    prices = pd.concat([prices, benchmark], ignore_index=True)
    features, _, weekly = build_weekly_feature_snapshot(
        prices,
        known_at="2026-08-22T08:30:00Z",
        universe_tickers=["ABCD"],
    )
    assert list(features["ticker"]) == ["ABCD"]
    assert set(weekly["ticker"]) == {"ABCD"}
