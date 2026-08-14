#!/usr/bin/env python3
"""
Phase MLX-1: build an expanded ETF universe for experimental ML research.

This script is research-only. It uses yfinance as non-production research data,
keeps outputs under data/research/ml_lab, and does not modify production inputs,
strategy logic, dashboard code, or package pins.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
PROJECT_UNIVERSE_PATH = ROOT / "data" / "01_data_hub" / "universe.json"

ADJ_CLOSE_CACHE = OUTPUT_DIR / "yfinance_adj_close_daily.csv"
VOLUME_CACHE = OUTPUT_DIR / "yfinance_volume_daily.csv"

UNIVERSE_OUT = OUTPUT_DIR / "expanded_etf_universe.csv"
PRICES_OUT = OUTPUT_DIR / "expanded_etf_prices_weekly.csv"
RETURNS_OUT = OUTPUT_DIR / "expanded_etf_returns_weekly.csv"
COVERAGE_OUT = OUTPUT_DIR / "expanded_etf_coverage_report.csv"
METADATA_OUT = OUTPUT_DIR / "expanded_etf_metadata.json"


@dataclass(frozen=True)
class EtfSpec:
    ticker: str
    category: str
    description: str


CURATED_ETFS: list[EtfSpec] = [
    # US broad equity
    EtfSpec("SPY", "US broad equity", "S&P 500 large-cap equity"),
    EtfSpec("IVV", "US broad equity", "S&P 500 large-cap equity alternate"),
    EtfSpec("VOO", "US broad equity", "S&P 500 large-cap equity Vanguard"),
    EtfSpec("VTI", "US broad equity", "Total US stock market"),
    EtfSpec("ITOT", "US broad equity", "Total US stock market alternate"),
    EtfSpec("SCHB", "US broad equity", "Broad US equity"),
    EtfSpec("QQQ", "US broad equity", "Nasdaq 100 growth and technology tilt"),
    EtfSpec("DIA", "US broad equity", "Dow Jones Industrial Average"),
    EtfSpec("IWM", "US broad equity", "Russell 2000 small-cap equity"),
    EtfSpec("IJH", "US broad equity", "S&P mid-cap equity"),
    EtfSpec("IJR", "US broad equity", "S&P small-cap equity"),
    EtfSpec("MDY", "US broad equity", "S&P mid-cap equity alternate"),
    # US sectors
    EtfSpec("XLK", "US sectors", "Technology sector"),
    EtfSpec("XLF", "US sectors", "Financials sector"),
    EtfSpec("XLE", "US sectors", "Energy sector"),
    EtfSpec("XLV", "US sectors", "Health care sector"),
    EtfSpec("XLI", "US sectors", "Industrials sector"),
    EtfSpec("XLY", "US sectors", "Consumer discretionary sector"),
    EtfSpec("XLP", "US sectors", "Consumer staples sector"),
    EtfSpec("XLU", "US sectors", "Utilities sector"),
    EtfSpec("XLB", "US sectors", "Materials sector"),
    EtfSpec("XLRE", "US sectors", "Real estate sector"),
    EtfSpec("XLC", "US sectors", "Communication services sector"),
    EtfSpec("SMH", "US sectors", "Semiconductor industry proxy"),
    EtfSpec("IBB", "US sectors", "Biotechnology industry proxy"),
    EtfSpec("XBI", "US sectors", "Biotechnology equal-weight proxy"),
    EtfSpec("KRE", "US sectors", "Regional banks industry proxy"),
    # Factors and styles
    EtfSpec("VTV", "Factors/styles", "Large-cap value"),
    EtfSpec("VUG", "Factors/styles", "Large-cap growth"),
    EtfSpec("IVE", "Factors/styles", "S&P 500 value"),
    EtfSpec("IVW", "Factors/styles", "S&P 500 growth"),
    EtfSpec("IWD", "Factors/styles", "Russell 1000 value"),
    EtfSpec("IWF", "Factors/styles", "Russell 1000 growth"),
    EtfSpec("MTUM", "Factors/styles", "US momentum factor"),
    EtfSpec("QUAL", "Factors/styles", "US quality factor"),
    EtfSpec("VLUE", "Factors/styles", "US value factor"),
    EtfSpec("USMV", "Factors/styles", "US minimum volatility factor"),
    EtfSpec("SPLV", "Factors/styles", "S&P 500 low volatility"),
    EtfSpec("RSP", "Factors/styles", "S&P 500 equal weight"),
    EtfSpec("SCHD", "Factors/styles", "US dividend equity"),
    EtfSpec("DVY", "Factors/styles", "US dividend equity alternate"),
    # International equity
    EtfSpec("EFA", "International equity", "Developed ex-US equity"),
    EtfSpec("VEA", "International equity", "Developed ex-US equity alternate"),
    EtfSpec("IEFA", "International equity", "Core developed ex-US equity"),
    EtfSpec("EEM", "International equity", "Emerging-market equity"),
    EtfSpec("VWO", "International equity", "Emerging-market equity alternate"),
    EtfSpec("IEMG", "International equity", "Core emerging-market equity"),
    EtfSpec("ACWX", "International equity", "Global ex-US equity"),
    EtfSpec("VT", "International equity", "Global all-country equity"),
    EtfSpec("EWJ", "International equity", "Japan equity"),
    EtfSpec("EWG", "International equity", "Germany equity"),
    EtfSpec("EWU", "International equity", "United Kingdom equity"),
    EtfSpec("EWY", "International equity", "South Korea equity"),
    EtfSpec("EWT", "International equity", "Taiwan equity"),
    EtfSpec("FXI", "International equity", "China large-cap equity"),
    EtfSpec("ASHR", "International equity", "China A-shares equity"),
    EtfSpec("INDA", "International equity", "India equity"),
    EtfSpec("EWZ", "International equity", "Brazil equity"),
    EtfSpec("EWW", "International equity", "Mexico equity"),
    EtfSpec("EWC", "International equity", "Canada equity"),
    EtfSpec("EWA", "International equity", "Australia equity"),
    # Bonds and duration
    EtfSpec("BIL", "Bonds", "Treasury bills cash proxy"),
    EtfSpec("SHV", "Bonds", "Short Treasury bills"),
    EtfSpec("SHY", "Bonds", "1-3 year Treasuries"),
    EtfSpec("VGSH", "Bonds", "Short-term Treasury"),
    EtfSpec("IEF", "Bonds", "7-10 year Treasuries"),
    EtfSpec("VGIT", "Bonds", "Intermediate-term Treasury"),
    EtfSpec("TLT", "Bonds", "20+ year Treasuries"),
    EtfSpec("EDV", "Bonds", "Extended-duration Treasuries"),
    EtfSpec("TIP", "Bonds", "Treasury inflation-protected securities"),
    EtfSpec("STIP", "Bonds", "Short-term TIPS"),
    EtfSpec("AGG", "Bonds", "US aggregate bonds"),
    EtfSpec("BND", "Bonds", "Total US bond market"),
    EtfSpec("MBB", "Bonds", "Agency mortgage-backed securities"),
    EtfSpec("MUB", "Bonds", "National municipal bonds"),
    # Credit
    EtfSpec("LQD", "Credit", "Investment-grade corporate credit"),
    EtfSpec("VCIT", "Credit", "Intermediate corporate credit"),
    EtfSpec("VCSH", "Credit", "Short-term corporate credit"),
    EtfSpec("HYG", "Credit", "High-yield corporate credit"),
    EtfSpec("JNK", "Credit", "High-yield corporate credit alternate"),
    EtfSpec("SJNK", "Credit", "Short-term high-yield credit"),
    EtfSpec("EMB", "Credit", "USD emerging-market sovereign debt"),
    EtfSpec("BKLN", "Credit", "Senior loans"),
    # Commodities
    EtfSpec("GLD", "Commodities", "Gold"),
    EtfSpec("IAU", "Commodities", "Gold alternate"),
    EtfSpec("SLV", "Commodities", "Silver"),
    EtfSpec("PDBC", "Commodities", "Broad commodities"),
    EtfSpec("DBC", "Commodities", "Broad commodities alternate"),
    EtfSpec("DBA", "Commodities", "Agriculture commodities"),
    EtfSpec("USO", "Commodities", "Crude oil"),
    EtfSpec("UNG", "Commodities", "Natural gas"),
    EtfSpec("CPER", "Commodities", "Copper"),
    # Real estate
    EtfSpec("VNQ", "Real estate", "US REITs"),
    EtfSpec("IYR", "Real estate", "US real estate"),
    EtfSpec("SCHH", "Real estate", "US REITs alternate"),
    EtfSpec("VNQI", "Real estate", "Global ex-US real estate"),
    EtfSpec("REET", "Real estate", "Global REITs"),
    # Currency / dollar
    EtfSpec("UUP", "Currency/dollar", "US dollar bullish index"),
    EtfSpec("FXE", "Currency/dollar", "Euro currency proxy"),
    EtfSpec("FXY", "Currency/dollar", "Japanese yen currency proxy"),
    EtfSpec("FXF", "Currency/dollar", "Swiss franc currency proxy"),
    EtfSpec("CYB", "Currency/dollar", "Chinese yuan currency proxy"),
    # Volatility proxies, not direct VIX futures trading recommendations.
    EtfSpec("VIXY", "Volatility proxies", "Short-term VIX futures proxy"),
    EtfSpec("VXX", "Volatility proxies", "Short-term VIX futures ETN proxy"),
]


EXCLUDED_LEVERAGED_OR_INVERSE = {
    "SSO", "UPRO", "SPXL", "TQQQ", "QLD", "SDS", "SPXU", "SH", "PSQ", "QID", "SQQQ",
    "TZA", "TNA", "FAZ", "FAS", "ERX", "ERY", "SOXL", "SOXS", "UVXY", "SVXY", "VIXM",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase MLX expanded ETF universe from yfinance research data."
    )
    parser.add_argument("--force", action="store_true", help="Redownload yfinance data even if cache exists.")
    parser.add_argument("--start", default="2000-01-01", help="Download start date.")
    parser.add_argument("--min-start-date", default="2016-01-01", help="Latest acceptable first weekly price date.")
    parser.add_argument("--min-weeks", type=int, default=520, help="Minimum weekly observations required.")
    parser.add_argument("--max-missing-pct", type=float, default=0.15, help="Maximum missingness over the test window.")
    parser.add_argument("--min-avg-volume", type=float, default=250_000, help="Minimum average daily volume if available.")
    parser.add_argument(
        "--include-leveraged-inverse",
        action="store_true",
        help="Include known leveraged/inverse tickers. Default excludes them.",
    )
    return parser.parse_args()


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def load_existing_project_tickers() -> set[str]:
    if not PROJECT_UNIVERSE_PATH.exists():
        warn(f"Optional project universe file not found: {PROJECT_UNIVERSE_PATH}")
        return set()
    try:
        payload = json.loads(PROJECT_UNIVERSE_PATH.read_text())
    except Exception as exc:
        warn(f"Could not parse optional project universe file {PROJECT_UNIVERSE_PATH}: {exc}")
        return set()

    tickers: set[str] = set()
    for key in ("core", "full", "all"):
        values = payload.get(key, [])
        if isinstance(values, list):
            tickers.update(str(t).upper().strip() for t in values if str(t).strip())
    return tickers


def build_universe(include_leveraged_inverse: bool) -> pd.DataFrame:
    project_tickers = load_existing_project_tickers()
    by_ticker: dict[str, EtfSpec] = {}
    for spec in CURATED_ETFS:
        ticker = spec.ticker.upper().strip()
        if not include_leveraged_inverse and ticker in EXCLUDED_LEVERAGED_OR_INVERSE:
            continue
        by_ticker[ticker] = spec

    curated_tickers = set(by_ticker)
    for ticker in sorted(project_tickers):
        if not ticker or (not include_leveraged_inverse and ticker in EXCLUDED_LEVERAGED_OR_INVERSE):
            continue
        by_ticker.setdefault(ticker, EtfSpec(ticker, "Existing project ETF", "Included from project universe.json"))

    rows = []
    for ticker in sorted(by_ticker):
        spec = by_ticker[ticker]
        rows.append(
            {
                **asdict(spec),
                "ticker": ticker,
                "in_curated_mlx_universe": ticker in curated_tickers,
                "in_existing_project_universe": ticker in project_tickers,
                "leveraged_inverse_excluded_by_default": ticker in EXCLUDED_LEVERAGED_OR_INVERSE,
                "research_only": True,
                "production_valid": False,
            }
        )
    return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)


def import_yfinance() -> Any | None:
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        warn("yfinance is not installed. This research-only builder will exit gracefully without downloads.")
        return None
    return yf


def normalize_yfinance_panel(downloaded: pd.DataFrame, tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    if downloaded is None or downloaded.empty:
        return pd.DataFrame(), pd.DataFrame(), tickers

    downloaded = downloaded.copy()
    downloaded.index = pd.to_datetime(downloaded.index).tz_localize(None)

    adj_close_series: dict[str, pd.Series] = {}
    volume_series: dict[str, pd.Series] = {}
    failed: list[str] = []

    if isinstance(downloaded.columns, pd.MultiIndex):
        level0 = set(str(x) for x in downloaded.columns.get_level_values(0))
        level1 = set(str(x) for x in downloaded.columns.get_level_values(1))
        ticker_first = any(t in level0 for t in tickers)
        field_first = any(field in level0 for field in ("Adj Close", "Close", "Volume")) and any(t in level1 for t in tickers)

        for ticker in tickers:
            try:
                if ticker_first and ticker in downloaded.columns.get_level_values(0):
                    block = downloaded[ticker]
                elif field_first and ticker in downloaded.columns.get_level_values(1):
                    block = downloaded.xs(ticker, axis=1, level=1)
                else:
                    failed.append(ticker)
                    continue

                price_field = "Adj Close" if "Adj Close" in block.columns else "Close" if "Close" in block.columns else None
                if price_field is None:
                    failed.append(ticker)
                    continue
                adj_close_series[ticker] = pd.to_numeric(block[price_field], errors="coerce")
                if "Volume" in block.columns:
                    volume_series[ticker] = pd.to_numeric(block["Volume"], errors="coerce")
            except Exception:
                failed.append(ticker)
    else:
        price_field = "Adj Close" if "Adj Close" in downloaded.columns else "Close" if "Close" in downloaded.columns else None
        if len(tickers) == 1 and price_field is not None:
            adj_close_series[tickers[0]] = pd.to_numeric(downloaded[price_field], errors="coerce")
            if "Volume" in downloaded.columns:
                volume_series[tickers[0]] = pd.to_numeric(downloaded["Volume"], errors="coerce")
        else:
            failed = tickers.copy()

    adj_close = pd.DataFrame(adj_close_series, index=downloaded.index).dropna(how="all").sort_index()
    volume = pd.DataFrame(volume_series, index=downloaded.index)
    volume = volume.reindex(index=adj_close.index).sort_index()
    empty_tickers = [ticker for ticker in tickers if ticker not in adj_close.columns or adj_close[ticker].dropna().empty]
    failed = sorted(set(failed).union(empty_tickers))

    return adj_close, volume, failed


def download_or_load_cache(tickers: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, list[str], str]:
    if not args.force and ADJ_CLOSE_CACHE.exists() and VOLUME_CACHE.exists():
        adj_close = pd.read_csv(ADJ_CLOSE_CACHE, index_col=0, parse_dates=True).sort_index()
        volume = pd.read_csv(VOLUME_CACHE, index_col=0, parse_dates=True).sort_index()
        adj_close.index = pd.to_datetime(adj_close.index).tz_localize(None)
        volume.index = pd.to_datetime(volume.index).tz_localize(None)
        missing_from_cache = [ticker for ticker in tickers if ticker not in adj_close.columns]
        if missing_from_cache:
            warn(f"Cache is missing {len(missing_from_cache)} requested tickers; use --force to redownload.")
        failed = [ticker for ticker in tickers if ticker not in adj_close.columns or adj_close[ticker].dropna().empty]
        return adj_close.reindex(columns=tickers), volume.reindex(columns=tickers), failed, "cache"

    yf = import_yfinance()
    if yf is None:
        return pd.DataFrame(), pd.DataFrame(), tickers, "missing_yfinance"

    try:
        downloaded = yf.download(
            tickers=tickers,
            start=args.start,
            progress=False,
            auto_adjust=False,
            group_by="ticker",
            threads=True,
        )
    except Exception as exc:
        warn(f"yfinance download failed: {exc}")
        return pd.DataFrame(), pd.DataFrame(), tickers, "download_failed"

    adj_close, volume, failed = normalize_yfinance_panel(downloaded, tickers)
    if adj_close.empty:
        warn("yfinance returned an empty adjusted-close panel.")
        return adj_close, volume, failed, "empty_download"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    adj_close.to_csv(ADJ_CLOSE_CACHE, index_label="Date")
    volume.to_csv(VOLUME_CACHE, index_label="Date")
    return adj_close.reindex(columns=tickers), volume.reindex(columns=tickers), failed, "download"


def build_weekly_prices(adj_close: pd.DataFrame) -> pd.DataFrame:
    if adj_close.empty:
        return pd.DataFrame()
    weekly_prices = adj_close.sort_index().resample("W-FRI").last()
    if not weekly_prices.empty:
        today = pd.Timestamp.today().normalize()
        last_weekly_label = weekly_prices.index.max()
        if pd.notna(last_weekly_label) and last_weekly_label > today:
            weekly_prices = weekly_prices.iloc[:-1]
    return weekly_prices.dropna(how="all")


def build_coverage_report(
    universe: pd.DataFrame,
    weekly_prices: pd.DataFrame,
    volume: pd.DataFrame,
    failed_tickers: list[str],
    args: argparse.Namespace,
) -> pd.DataFrame:
    min_start_date = pd.Timestamp(args.min_start_date)
    failed_set = set(failed_tickers)
    evaluation_index = weekly_prices.loc[weekly_prices.index >= min_start_date].index if not weekly_prices.empty else pd.DatetimeIndex([])
    total_eval_weeks = len(evaluation_index)

    rows: list[dict[str, Any]] = []
    for row in universe.to_dict("records"):
        ticker = row["ticker"]
        prices = weekly_prices[ticker] if ticker in weekly_prices.columns else pd.Series(dtype=float)
        valid = prices.dropna()
        eval_prices = prices.reindex(evaluation_index) if total_eval_weeks else pd.Series(dtype=float)
        eval_nonmissing = int(eval_prices.notna().sum()) if total_eval_weeks else 0
        missing_pct = 1.0 - (eval_nonmissing / total_eval_weeks) if total_eval_weeks else 1.0

        vol = volume[ticker] if ticker in volume.columns else pd.Series(dtype=float)
        avg_volume = float(vol.dropna().mean()) if not vol.dropna().empty else np.nan

        first_date = valid.index.min() if not valid.empty else pd.NaT
        last_date = valid.index.max() if not valid.empty else pd.NaT
        first_date_ok = bool(pd.notna(first_date) and first_date <= min_start_date)
        min_weeks_ok = int(valid.shape[0]) >= args.min_weeks
        missingness_ok = missing_pct <= args.max_missing_pct
        volume_ok = bool(pd.isna(avg_volume) or avg_volume >= args.min_avg_volume)
        downloaded_ok = ticker not in failed_set and not valid.empty
        kept = downloaded_ok and first_date_ok and min_weeks_ok and missingness_ok and volume_ok

        fail_reasons = []
        if not downloaded_ok:
            fail_reasons.append("download_failed_or_empty")
        if not first_date_ok:
            fail_reasons.append("insufficient_start_date")
        if not min_weeks_ok:
            fail_reasons.append("insufficient_weekly_observations")
        if not missingness_ok:
            fail_reasons.append("too_much_missingness")
        if not volume_ok:
            fail_reasons.append("average_volume_below_threshold")

        rows.append(
            {
                **row,
                "downloaded_ok": downloaded_ok,
                "first_weekly_date": first_date.date().isoformat() if pd.notna(first_date) else "",
                "last_weekly_date": last_date.date().isoformat() if pd.notna(last_date) else "",
                "weeks_available": int(valid.shape[0]),
                "eval_weeks_since_min_start": int(total_eval_weeks),
                "eval_nonmissing_weeks": eval_nonmissing,
                "missing_pct_since_min_start": float(missing_pct),
                "avg_daily_volume": avg_volume,
                "first_date_ok": first_date_ok,
                "min_weeks_ok": min_weeks_ok,
                "missingness_ok": missingness_ok,
                "volume_ok": volume_ok,
                "kept_after_filters": kept,
                "filter_fail_reasons": ";".join(fail_reasons),
            }
        )
    return pd.DataFrame(rows).sort_values(["kept_after_filters", "ticker"], ascending=[False, True]).reset_index(drop=True)


def write_outputs(
    universe: pd.DataFrame,
    coverage: pd.DataFrame,
    weekly_prices: pd.DataFrame,
    failed_tickers: list[str],
    cache_mode: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    kept_tickers = coverage.loc[coverage["kept_after_filters"], "ticker"].tolist()
    loaded_tickers = [ticker for ticker in universe["ticker"].tolist() if ticker not in set(failed_tickers)]

    kept_prices = weekly_prices.reindex(columns=kept_tickers).dropna(how="all")
    weekly_returns = np.log(kept_prices / kept_prices.shift(1)).dropna(how="all") if not kept_prices.empty else pd.DataFrame()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    universe.to_csv(UNIVERSE_OUT, index=False)
    kept_prices.to_csv(PRICES_OUT, index_label="Date")
    weekly_returns.to_csv(RETURNS_OUT, index_label="Date")
    coverage.to_csv(COVERAGE_OUT, index=False)

    metadata = {
        "phase": "MLX-1 expanded ETF universe",
        "source": "yfinance",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "no_live_trading_decisions": True,
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_existing_candidates_replaced": True,
        "leveraged_inverse_excluded_by_default": not args.include_leveraged_inverse,
        "cache_mode": cache_mode,
        "download_start": args.start,
        "min_start_date": args.min_start_date,
        "min_weeks": args.min_weeks,
        "max_missing_pct": args.max_missing_pct,
        "min_avg_volume": args.min_avg_volume,
        "tickers_requested": universe["ticker"].tolist(),
        "tickers_loaded": loaded_tickers,
        "tickers_failed": sorted(set(failed_tickers)),
        "tickers_kept_after_filters": kept_tickers,
        "requested_count": int(len(universe)),
        "loaded_count": int(len(loaded_tickers)),
        "kept_count": int(len(kept_tickers)),
        "weekly_price_start": kept_prices.index.min().date().isoformat() if not kept_prices.empty else None,
        "weekly_price_end": kept_prices.index.max().date().isoformat() if not kept_prices.empty else None,
        "created_outputs": {
            "universe": str(UNIVERSE_OUT.relative_to(ROOT)),
            "weekly_prices": str(PRICES_OUT.relative_to(ROOT)),
            "weekly_returns": str(RETURNS_OUT.relative_to(ROOT)),
            "coverage_report": str(COVERAGE_OUT.relative_to(ROOT)),
            "metadata": str(METADATA_OUT.relative_to(ROOT)),
            "adj_close_cache": str(ADJ_CLOSE_CACHE.relative_to(ROOT)),
            "volume_cache": str(VOLUME_CACHE.relative_to(ROOT)),
        },
        "warnings": [
            "Experimental research-only Phase MLX output; not production-valid.",
            "yfinance is used only as research data and can be incomplete or inconsistent.",
            "Expanded ETF universe testing can introduce selection bias and data-mining risk.",
            "High overfitting risk; do not use for live trading decisions.",
        ],
    }
    METADATA_OUT.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> int:
    args = parse_args()
    warnings.filterwarnings("default")

    print("Phase MLX-1 expanded ETF universe builder")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print("WARNING: expanded ETF testing may introduce selection bias and data-mining risk.")

    universe = build_universe(include_leveraged_inverse=args.include_leveraged_inverse)
    tickers = universe["ticker"].tolist()
    print(f"Tickers requested: {len(tickers)}")

    adj_close, volume, failed_tickers, cache_mode = download_or_load_cache(tickers, args)
    if cache_mode == "missing_yfinance":
        metadata = {
            "phase": "MLX-1 expanded ETF universe",
            "source": "yfinance",
            "production_valid": False,
            "research_only": True,
            "selection_bias_warning": True,
            "data_mining_warning": True,
            "overfitting_warning": True,
            "purpose": "experimental ML sandbox only",
            "warning": "yfinance missing; no data outputs produced",
            "tickers_requested": tickers,
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        METADATA_OUT.write_text(json.dumps(metadata, indent=2) + "\n")
        return 0

    if adj_close.empty:
        warn("No adjusted-close data available; writing metadata and empty reports only.")

    weekly_prices = build_weekly_prices(adj_close)
    coverage = build_coverage_report(universe, weekly_prices, volume, failed_tickers, args)
    metadata = write_outputs(universe, coverage, weekly_prices, failed_tickers, cache_mode, args)

    print(f"Cache mode: {cache_mode}")
    print(f"ETFs successfully loaded: {metadata['loaded_count']}")
    print(f"ETFs kept after filters: {metadata['kept_count']}")
    print(f"Failed tickers: {', '.join(metadata['tickers_failed']) if metadata['tickers_failed'] else 'none'}")
    print(f"Date range: {metadata['weekly_price_start']} to {metadata['weekly_price_end']}")
    print("Outputs:")
    for path in metadata["created_outputs"].values():
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
