"""Point-in-time feature preparation for the Indonesia current-universe rehearsal."""

from __future__ import annotations

from collections.abc import Iterable
import math

import pandas as pd

from .cross_sectional_factors import asset_features
from .indonesia_equity import normalize_idx_ticker


REQUIRED_PRICE_COLUMNS = {
    "observation_date",
    "ticker",
    "close",
    "adjusted_close",
    "volume",
    "knowledge_at_utc",
}


def _utc_timestamp(value: object) -> pd.Timestamp:
    result = pd.Timestamp(value)
    return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")


def build_weekly_feature_snapshot(
    prices: pd.DataFrame,
    *,
    known_at: object,
    universe_tickers: Iterable[str],
    liquidity_lookback_days: int = 63,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create one causal weekly feature snapshot from frozen daily observations.

    The function does not calculate a return path, a benchmark comparison, or
    any performance statistic. Each weekly row is the final actual observation
    in a Friday-ending calendar week; no missing prices are manufactured.
    """
    missing = sorted(REQUIRED_PRICE_COLUMNS - set(prices.columns))
    if missing:
        raise ValueError(f"daily prices missing columns: {missing}")
    if liquidity_lookback_days <= 0:
        raise ValueError("liquidity_lookback_days must be positive")

    cutoff = _utc_timestamp(known_at)
    allowed = {normalize_idx_ticker(ticker) for ticker in universe_tickers}
    rows = prices.copy()
    rows["knowledge_at_utc"] = pd.to_datetime(rows["knowledge_at_utc"], utc=True, errors="coerce")
    rows["observation_date"] = pd.to_datetime(rows["observation_date"], errors="coerce")
    if rows[["knowledge_at_utc", "observation_date"]].isna().any().any():
        raise ValueError("price timestamps must be valid")

    rows["local_ticker"] = rows["ticker"].map(
        lambda value: normalize_idx_ticker(value) if not str(value).startswith("^") else None
    )
    rows = rows[rows["local_ticker"].isin(allowed)].copy()
    if (rows["knowledge_at_utc"] > cutoff).any():
        raise ValueError("daily prices include observations not known by known_at")
    for column in ("close", "adjusted_close", "volume"):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    if rows.duplicated(["local_ticker", "observation_date"]).any():
        raise ValueError("duplicate ticker-date observations are not permitted")

    feature_rows: list[dict[str, object]] = []
    exclusion_rows: list[dict[str, object]] = []
    weekly_parts: list[pd.DataFrame] = []
    for ticker in sorted(allowed):
        daily = rows[rows["local_ticker"] == ticker].sort_values("observation_date").copy()
        valid = daily[
            daily["close"].map(lambda value: pd.notna(value) and math.isfinite(float(value)) and float(value) > 0)
            & daily["adjusted_close"].map(
                lambda value: pd.notna(value) and math.isfinite(float(value)) and float(value) > 0
            )
            & daily["volume"].map(
                lambda value: pd.notna(value) and math.isfinite(float(value)) and float(value) >= 0
            )
        ].copy()
        if valid.empty:
            exclusion_rows.append({"ticker": ticker, "reason": "no_valid_daily_prices"})
            continue

        valid["week_end"] = valid["observation_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
        weekly = valid.groupby("week_end", sort=True, as_index=False).tail(1).copy()
        weekly = weekly[
            [
                "local_ticker",
                "week_end",
                "observation_date",
                "close",
                "adjusted_close",
                "volume",
                "knowledge_at_utc",
            ]
        ].rename(columns={"local_ticker": "ticker"})
        weekly_parts.append(weekly)
        if len(weekly) < 53:
            exclusion_rows.append(
                {
                    "ticker": ticker,
                    "reason": "insufficient_weekly_history",
                    "weekly_observations": len(weekly),
                }
            )
            continue

        liquidity = valid.tail(liquidity_lookback_days).copy()
        liquidity_values = liquidity["close"] * liquidity["volume"]
        if len(liquidity_values) < liquidity_lookback_days:
            exclusion_rows.append(
                {
                    "ticker": ticker,
                    "reason": "insufficient_liquidity_history",
                    "liquidity_observations": len(liquidity_values),
                }
            )
            continue

        calculated = asset_features(
            weekly["adjusted_close"].astype(float).tolist(), asof_date=cutoff.isoformat()
        )
        feature_rows.append(
            {
                "ticker": ticker,
                **calculated,
                "price_observation_date": weekly["observation_date"].iloc[-1].date().isoformat(),
                "weekly_observations": len(weekly),
                "liquidity_observations": len(liquidity_values),
                "median_daily_value_idr": float(liquidity_values.median()),
            }
        )

    features = pd.DataFrame(feature_rows)
    if not features.empty:
        features = features.sort_values("ticker").reset_index(drop=True)
    exclusions = pd.DataFrame(
        exclusion_rows,
        columns=["ticker", "reason", "weekly_observations", "liquidity_observations"],
    )
    if not exclusions.empty:
        exclusions = exclusions.sort_values(["reason", "ticker"]).reset_index(drop=True)
    weekly_prices = (
        pd.concat(weekly_parts, ignore_index=True)
        .sort_values(["ticker", "week_end"])
        .reset_index(drop=True)
        if weekly_parts
        else pd.DataFrame()
    )
    return features, exclusions, weekly_prices
