"""Build the R2 ETF volume-divergence candidate signal.

Research-only output. Existing project files do not contain volume columns, so
this script attempts a yfinance pull and writes an explicit warning/placeholder
if that is not possible.
"""

from __future__ import annotations

import importlib.util
from datetime import timedelta

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import SIGNAL_DIR, attach_tradable_lag, ensure_parent, load_weekly_prices, robust_z


def empty_panel(prices: pd.DataFrame, reason: str) -> pd.DataFrame:
    rows = []
    for ticker in prices.columns:
        part = pd.DataFrame(
            {
                "Date": prices.index,
                "Ticker": ticker,
                "signal_name": "r2_volume_divergence",
                "signal_value_observed": np.nan,
                "source": "yfinance_unavailable_or_failed",
                "frequency": "weekly",
                "lag_periods": 1,
                "research_only": True,
                "notes": reason,
            }
        )
        rows.append(part)
    return attach_tradable_lag(pd.concat(rows, ignore_index=True)) if rows else pd.DataFrame()


def extract_volume(download: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if download.empty:
        return pd.DataFrame()
    if isinstance(download.columns, pd.MultiIndex):
        level0 = set(map(str, download.columns.get_level_values(0)))
        level1 = set(map(str, download.columns.get_level_values(1)))
        if "Volume" in level0:
            volume = download["Volume"].copy()
        elif "Volume" in level1:
            pieces = {}
            for ticker in tickers:
                if ticker in level0 and "Volume" in download[ticker].columns:
                    pieces[ticker] = download[ticker]["Volume"]
            volume = pd.DataFrame(pieces)
        else:
            return pd.DataFrame()
    elif "Volume" in download.columns:
        volume = download[["Volume"]].rename(columns={"Volume": tickers[0] if len(tickers) == 1 else "Volume"})
    else:
        return pd.DataFrame()
    volume.index = pd.to_datetime(volume.index)
    return volume[[c for c in volume.columns if c in tickers]].apply(pd.to_numeric, errors="coerce")


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    if prices.empty:
        raise SystemExit("weekly_prices.csv is required for volume divergence construction.")

    tickers = list(prices.columns)
    panel: pd.DataFrame
    if importlib.util.find_spec("yfinance") is None:
        reason = "yfinance is not installed; ETF volume divergence could not be pulled."
        warnings.append(reason)
        panel = empty_panel(prices, reason)
    else:
        try:
            import yfinance as yf

            start = (prices.index.min() - timedelta(days=10)).strftime("%Y-%m-%d")
            end = (prices.index.max() + timedelta(days=10)).strftime("%Y-%m-%d")
            raw = yf.download(
                tickers=tickers,
                start=start,
                end=end,
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
            daily_volume = extract_volume(raw, tickers)
            if daily_volume.empty:
                reason = "yfinance returned no usable Volume columns."
                warnings.append(reason)
                panel = empty_panel(prices, reason)
            else:
                weekly_volume = daily_volume.resample("W-FRI").sum().reindex(prices.index)
                rows = []
                for ticker in tickers:
                    if ticker not in weekly_volume.columns:
                        warnings.append(f"{ticker}: missing yfinance volume column.")
                        observed = pd.Series(index=prices.index, dtype=float)
                    else:
                        vol_z = robust_z(np.log1p(weekly_volume[ticker]), 156, 26)
                        mom13 = robust_z(prices[ticker].pct_change(13), 156, 52)
                        ret4 = prices[ticker].pct_change(4)
                        # Rising volume confirms positive 4w moves and penalizes negative 4w moves.
                        observed = mom13 + 0.40 * vol_z * np.sign(ret4.fillna(0.0))
                    rows.append(
                        pd.DataFrame(
                            {
                                "Date": prices.index,
                                "Ticker": ticker,
                                "signal_name": "r2_volume_divergence",
                                "signal_value_observed": observed.values,
                                "source": "yfinance:Volume plus weekly_prices.csv",
                                "frequency": "daily volume resampled to weekly Friday",
                                "lag_periods": 1,
                                "research_only": True,
                                "notes": "Volume surge confirms 4w direction; signal is lagged one week before validation.",
                            }
                        )
                    )
                panel = attach_tradable_lag(pd.concat(rows, ignore_index=True))
        except Exception as exc:
            reason = f"yfinance volume pull failed: {exc}"
            warnings.append(reason)
            panel = empty_panel(prices, reason)

    out = SIGNAL_DIR / "signal_r2_volume_divergence.csv"
    ensure_parent(out)
    panel.to_csv(out, index=False)
    missing = panel["signal_value_tradable"].isna().mean() if "signal_value_tradable" in panel.columns and len(panel) else np.nan
    print(f"Wrote {out} rows={len(panel)} tradable_missing={missing:.2%}" if pd.notna(missing) else f"Wrote {out} rows={len(panel)}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
