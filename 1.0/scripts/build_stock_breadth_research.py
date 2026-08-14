#!/usr/bin/env python3
"""
build_stock_breadth_research.py
=================================
!! SURVIVORSHIP-BIASED RESEARCH DIAGNOSTIC — NOT FOR PRODUCTION !!

Pipeline prototype that downloads current S&P 500 constituent prices via
yfinance and builds a weekly stock breadth panel aligned to the project's
existing market-state weekly date index.

The data backend can later be swapped to WRDS/CRSP or Norgate for
production-valid (point-in-time) signals.  All outputs include an explicit
bias warning embedded in stock_breadth_metadata.json.

Usage
-----
    python3 scripts/build_stock_breadth_research.py          # use cache
    python3 scripts/build_stock_breadth_research.py --force  # force redownload

Outputs: data/research/stock_breadth/
    sp500_current_universe.csv
    stock_prices_weekly.csv
    stock_returns_weekly.csv
    stock_breadth_weekly.csv
    sector_breadth_weekly.csv
    stock_breadth_coverage_report.csv
    stock_breadth_metadata.json
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ─── constants ────────────────────────────────────────────────────────────────
DIAG_LABEL = "SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY"
FETCH_DATE = str(date.today())
PRICE_START = "2010-01-01"   # download window — covers most of project history
PRICE_END = date.today().strftime("%Y-%m-%d")
WEEKS = 52
NEAR_HIGH_THRESHOLD = 0.95   # "near 52w high" = within 5% of max

_UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
L2B  = ROOT / "data" / "04_layer2b_risk_regime_engine"
HUB  = ROOT / "data" / "01_data_hub"
L3   = ROOT / "data" / "05_layer3_portfolio_construction"
OUT  = ROOT / "data" / "research" / "stock_breadth"
OUT.mkdir(parents=True, exist_ok=True)

RAW_CACHE = OUT / "stock_prices_daily_raw.parquet"
# Also check Phase 5A-Free parquet as a fallback cache for 2020+ data
PHASE5A_CACHE = (
    ROOT / "data" / "research"
    / "phase_5a_free_current_constituent_breadth_diagnostic"
    / "phase5a_free_stock_prices_adjclose_daily.parquet"
)


# ─── argument parsing ─────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Build stock breadth research panel")
parser.add_argument("--force", action="store_true",
                    help="Force re-download even if cache exists")
args = parser.parse_args()
FORCE = args.force

print("=" * 68)
print("BUILD STOCK BREADTH RESEARCH — PROTOTYPE PIPELINE")
print(f"!! {DIAG_LABEL} !!")
print("=" * 68)
print(f"  Date         : {FETCH_DATE}")
print(f"  Price window : {PRICE_START} → {PRICE_END}")
print(f"  Output dir   : {OUT}")
print(f"  Force reload : {FORCE}")


# ─── helpers ──────────────────────────────────────────────────────────────────

def breadth_fraction(condition_df: pd.DataFrame, valid_mask: pd.DataFrame) -> pd.Series:
    """Fraction of valid stocks satisfying `condition_df` each week."""
    denom = valid_mask.sum(axis=1).replace(0, np.nan)
    numer = condition_df.where(valid_mask).sum(axis=1)
    return numer / denom


def sanitize_col(s: str) -> str:
    """Make a string safe for use as a CSV column name."""
    return (s.replace(" & ", "_and_")
              .replace(" ", "_")
              .replace("&", "and")
              .replace("/", "_")
              .replace("-", "_")
              .lower())


def fetch_html_tables(url: str) -> list[pd.DataFrame]:
    import requests as _req
    resp = _req.get(url, headers=_UA_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_html(resp.text, header=0)


def extract_adjclose(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Robustly extract the Close/adjusted-close slice from a yfinance download."""
    if not isinstance(raw_df.columns, pd.MultiIndex):
        return raw_df[["Close"]] if "Close" in raw_df.columns else raw_df
    levels = [raw_df.columns.get_level_values(i) for i in range(raw_df.columns.nlevels)]
    price_level = next((i for i, lvl in enumerate(levels) if "Close" in lvl), None)
    if price_level is None:
        return raw_df
    ticker_level = 1 - price_level
    try:
        out = raw_df.xs("Close", axis=1, level=price_level)
    except Exception:
        close_mask = raw_df.columns.get_level_values(price_level) == "Close"
        out = raw_df.loc[:, close_mask]
        out.columns = raw_df.columns.get_level_values(ticker_level)[close_mask]
    return out


# ══════════════════════════════════════════════════════════════════════════════
# PART A — BIAS DISCLOSURE
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART A: Bias disclosure ===")

bias_rows = [
    {"item": "data_source",           "value": "yfinance + current Wikipedia S&P 500 list"},
    {"item": "point_in_time_safe",    "value": "False"},
    {"item": "survivorship_biased",   "value": "True"},
    {"item": "production_valid",      "value": "False"},
    {"item": "purpose",               "value": "pipeline prototype and research-only diagnostic"},
    {"item": "allowed_use",           "value": "diagnostic only; decide if PIT data is worth purchasing"},
    {"item": "prohibited_use",        "value": "production promotion; survivorship-bias-free claim"},
    {"item": "note",
     "value": ("Current constituents are backfilled into history. "
                "Removed, delisted, or bankrupt companies are excluded, "
                "biasing breadth upward throughout history.")},
]
pd.DataFrame(bias_rows).to_csv(OUT / "_bias_disclosure.csv", index=False)
print("  Saved _bias_disclosure.csv")


# ══════════════════════════════════════════════════════════════════════════════
# PART B — FETCH S&P 500 CONSTITUENT UNIVERSE
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART B: Fetch S&P 500 universe from Wikipedia ===")

sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
tickers_meta: list[dict] = []
tickers_sp500: list[str] = []

try:
    tables = fetch_html_tables(sp500_url)
    sp500_table = tables[0]
    ticker_col = next(
        (c for c in sp500_table.columns if "symbol" in c.lower() or "ticker" in c.lower()), None
    )
    name_col = next(
        (c for c in sp500_table.columns if "security" in c.lower() or "company" in c.lower()), None
    )
    sector_col = next(
        (c for c in sp500_table.columns if "sector" in c.lower() or "gics" in c.lower()), None
    )
    subind_col = next(
        (c for c in sp500_table.columns if "sub" in c.lower() and "ind" in c.lower()), None
    )
    if ticker_col is None:
        raise ValueError(f"No ticker column found; columns: {list(sp500_table.columns)}")

    for _, row in sp500_table.iterrows():
        raw_tk = str(row[ticker_col]).strip()
        yf_tk  = raw_tk.replace(".", "-")
        tickers_meta.append({
            "ticker_raw":  raw_tk,
            "ticker":      yf_tk,
            "name":        str(row[name_col]).strip()    if name_col    else "",
            "sector":      str(row[sector_col]).strip()  if sector_col  else "",
            "sub_industry": str(row[subind_col]).strip() if subind_col  else "",
            "index":       "S&P 500",
            "source_url":  sp500_url,
            "fetch_date":  FETCH_DATE,
            "diagnostic_label": DIAG_LABEL,
        })
        tickers_sp500.append(yf_tk)

    print(f"  S&P 500: {len(tickers_sp500)} tickers fetched from Wikipedia")

except Exception as e:
    print(f"  WARNING: Wikipedia fetch failed: {e}")
    print("  Will attempt to continue with empty universe.")

if not tickers_sp500:
    print("  CRITICAL: No tickers fetched. Exiting.")
    sys.exit(1)

universe_df = pd.DataFrame(tickers_meta).drop_duplicates("ticker")
universe_df.to_csv(OUT / "sp500_current_universe.csv", index=False)
print(f"  Saved sp500_current_universe.csv ({len(universe_df)} tickers)")

# Tickers to actually download (filter out obvious problem strings)
dl_tickers = [t for t in tickers_sp500 if t and "/" not in t]
print(f"  Tickers to download: {len(dl_tickers)}")


# ══════════════════════════════════════════════════════════════════════════════
# PART C — PRICE DOWNLOAD (with caching)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART C: Price download ===")

try:
    import yfinance as yf
    print(f"  yfinance version: {yf.__version__}")
except ImportError:
    print("  ERROR: yfinance not installed in this environment.")
    print("  Run: .venv/bin/pip install yfinance")
    sys.exit(1)

daily: pd.DataFrame | None = None

if not FORCE and RAW_CACHE.exists():
    print(f"  Loading cached prices from {RAW_CACHE.name}")
    try:
        daily = pd.read_parquet(RAW_CACHE)
        daily.index = pd.to_datetime(daily.index)
        print(f"  Cache loaded: {daily.shape[0]} days × {daily.shape[1]} tickers")
        # Check if cache covers the full requested window
        cache_end = daily.index.max()
        need_end = pd.Timestamp(PRICE_END)
        if (need_end - cache_end).days > 7:
            print(f"  Cache ends {cache_end.date()}; requesting refresh to {PRICE_END}")
            FORCE = True
    except Exception as e:
        print(f"  Cache load failed ({e}); will re-download")
        daily = None
        FORCE = True

if daily is None or FORCE:
    # Try Phase 5A-Free parquet as a starting point (covers 2020+)
    phase5a_daily: pd.DataFrame | None = None
    if PHASE5A_CACHE.exists():
        try:
            phase5a_daily = pd.read_parquet(PHASE5A_CACHE)
            phase5a_daily.index = pd.to_datetime(phase5a_daily.index)
            print(f"  Found Phase5A-Free cache: {phase5a_daily.shape} — will extend coverage")
        except Exception:
            phase5a_daily = None

    print(f"  Downloading {len(dl_tickers)} tickers from {PRICE_START} to {PRICE_END}")
    print("  (this may take 2–5 minutes for 500+ tickers)")

    try:
        raw = yf.download(
            tickers=dl_tickers,
            start=PRICE_START,
            end=PRICE_END,
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",
        )
        adjclose = extract_adjclose(raw)

        # Deduplicate columns
        if adjclose.columns.duplicated().any():
            seen: set = set()
            keep: list = []
            for i, col in enumerate(adjclose.columns):
                if col not in seen:
                    seen.add(col)
                    keep.append(i)
            adjclose = adjclose.iloc[:, keep]

        adjclose = adjclose.sort_index()
        print(f"  Download complete: {adjclose.shape[0]} days × {adjclose.shape[1]} tickers")

        # Merge with Phase 5A-Free cache for any additional tickers
        if phase5a_daily is not None:
            extra_tickers = [t for t in phase5a_daily.columns if t not in adjclose.columns]
            if extra_tickers:
                # Align date indexes, concat extra columns
                extra = phase5a_daily[extra_tickers]
                adjclose = adjclose.join(extra, how="outer")
                adjclose = adjclose.sort_index()
                print(f"  Merged {len(extra_tickers)} extra tickers from Phase5A-Free cache")

        daily = adjclose.dropna(how="all")

        # Save to cache
        try:
            daily.to_parquet(RAW_CACHE)
            size_mb = RAW_CACHE.stat().st_size / 1e6
            print(f"  Saved cache: {RAW_CACHE.name} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  WARNING: Could not save cache parquet: {e}")

    except Exception as e:
        print(f"  ERROR: yfinance download failed: {e}")
        if phase5a_daily is not None:
            print("  Falling back to Phase5A-Free cache only")
            daily = phase5a_daily
        else:
            print("  No fallback available. Exiting.")
            sys.exit(1)


# ── Coverage assessment ───────────────────────────────────────────────────────
good_tickers: list[str] = []
bad_tickers: list[str] = []
coverage_rows: list[dict] = []

for tk in dl_tickers:
    if tk not in daily.columns:
        bad_tickers.append(tk)
        coverage_rows.append({
            "ticker": tk, "status": "MISSING", "start_date": "", "end_date": "",
            "n_trading_days": 0, "missingness_pct": 100.0,
        })
        continue
    col = daily[tk]
    if isinstance(col, pd.DataFrame):
        col = col.iloc[:, 0]
    miss = float(col.isna().mean())
    valid = col.dropna()
    failed = miss > 0.50
    if failed:
        bad_tickers.append(tk)
    else:
        good_tickers.append(tk)
    coverage_rows.append({
        "ticker": tk,
        "status": "BAD" if failed else "OK",
        "start_date": str(valid.index.min().date()) if len(valid) > 0 else "",
        "end_date":   str(valid.index.max().date()) if len(valid) > 0 else "",
        "n_trading_days": len(valid),
        "missingness_pct": round(miss * 100, 2),
    })

coverage_pct = len(good_tickers) / len(dl_tickers) * 100 if dl_tickers else 0
print(f"  Good tickers: {len(good_tickers)} / {len(dl_tickers)} ({coverage_pct:.1f}%)")
if coverage_pct < 50:
    print("  WARNING: < 50% coverage — results may be unreliable")

pd.DataFrame(coverage_rows).to_csv(OUT / "stock_breadth_coverage_report.csv", index=False)
print("  Saved stock_breadth_coverage_report.csv")

# Keep only good tickers for breadth computation
daily_good = daily[[t for t in good_tickers if t in daily.columns]].copy()
if daily_good.empty:
    print("  ERROR: No valid tickers to compute breadth. Exiting.")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# PART D — WEEKLY CONVERSION & ALIGNMENT TO PROJECT DATE INDEX
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART D: Weekly conversion and alignment ===")

daily_good = daily_good.sort_index()

# Weekly Friday close (project convention)
prices_weekly = daily_good.resample("W-FRI").last()
prices_weekly = prices_weekly.dropna(how="all")
print(f"  Weekly panel (raw): {prices_weekly.shape[0]} weeks × {prices_weekly.shape[1]} tickers")

# Load project date index from market state history
try:
    state_hist = pd.read_csv(
        L2B / "market_state_history.csv", index_col=0, parse_dates=True
    )
    project_dates = state_hist.index
    print(f"  Project date index: {len(project_dates)} weeks "
          f"({project_dates.min().date()} → {project_dates.max().date()})")

    # Reindex to project dates (inner join — only where both exist)
    prices_aligned = prices_weekly.reindex(project_dates)
    n_aligned = prices_aligned.dropna(how="all").shape[0]
    print(f"  After alignment to project dates: {n_aligned} non-empty weeks")
except Exception as e:
    print(f"  WARNING: Could not load project date index ({e}); using raw weekly dates")
    prices_aligned = prices_weekly
    project_dates = prices_weekly.index

# Weekly returns
returns_weekly = prices_aligned.pct_change()

# ── Save price and return files ───────────────────────────────────────────────
prices_aligned.index.name = "Date"
returns_weekly.index.name = "Date"

prices_aligned.to_csv(OUT / "stock_prices_weekly.csv")
size_p = (OUT / "stock_prices_weekly.csv").stat().st_size / 1e6
print(f"  Saved stock_prices_weekly.csv ({size_p:.1f} MB, "
      f"{prices_aligned.shape[0]} weeks × {prices_aligned.shape[1]} tickers)")

returns_weekly.to_csv(OUT / "stock_returns_weekly.csv")
size_r = (OUT / "stock_returns_weekly.csv").stat().st_size / 1e6
print(f"  Saved stock_returns_weekly.csv ({size_r:.1f} MB)")


# ══════════════════════════════════════════════════════════════════════════════
# PART E — COMPUTE STOCK BREADTH FEATURES (vectorized)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART E: Compute stock breadth features ===")

# ── Moving averages: computed on daily, snapshotted at Friday ─────────────────
print("  Computing moving averages (daily → weekly Friday snapshot)...")
ma50  = daily_good.rolling(50,  min_periods=40 ).mean().resample("W-FRI").last().reindex(project_dates)
ma100 = daily_good.rolling(100, min_periods=80 ).mean().resample("W-FRI").last().reindex(project_dates)
ma200 = daily_good.rolling(200, min_periods=160).mean().resample("W-FRI").last().reindex(project_dates)

# ── Weekly-level computations ─────────────────────────────────────────────────
high_52w = prices_aligned.rolling(52, min_periods=40).max()

above_50d    = prices_aligned > ma50
above_100d   = prices_aligned > ma100
above_200d   = prices_aligned > ma200
near_high    = prices_aligned >= (NEAR_HIGH_THRESHOLD * high_52w)
pos_13w      = prices_aligned.pct_change(13) > 0
pos_26w      = prices_aligned.pct_change(26) > 0

valid_mask   = prices_aligned.notna()

print("  Aggregating breadth fractions...")
stock_breadth = pd.DataFrame({
    "pct_above_50d_ma":       breadth_fraction(above_50d,   valid_mask),
    "pct_above_100d_ma":      breadth_fraction(above_100d,  valid_mask),
    "pct_above_200d_ma":      breadth_fraction(above_200d,  valid_mask),
    "pct_positive_13w_return": breadth_fraction(pos_13w,    valid_mask),
    "pct_positive_26w_return": breadth_fraction(pos_26w,    valid_mask),
    "pct_near_52w_high":      breadth_fraction(near_high,   valid_mask),
    "equal_weight_stock_return": returns_weekly.mean(axis=1),
    "stock_count_available":  valid_mask.sum(axis=1),
    "median_stock_13w_return": prices_aligned.pct_change(13).median(axis=1),
    "median_stock_26w_return": prices_aligned.pct_change(26).median(axis=1),
}, index=project_dates)

stock_breadth.index.name = "Date"
stock_breadth["diagnostic_label"] = DIAG_LABEL

stock_breadth.to_csv(OUT / "stock_breadth_weekly.csv")
print(f"  Saved stock_breadth_weekly.csv "
      f"({stock_breadth.shape[0]} weeks × {stock_breadth.shape[1]} features)")
print(f"  Breadth coverage: "
      f"{stock_breadth['pct_above_200d_ma'].notna().sum()} non-null weeks")


# ══════════════════════════════════════════════════════════════════════════════
# PART F — SECTOR BREADTH FEATURES
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART F: Sector breadth features ===")

sector_breadth_cols: dict[str, pd.Series] = {}
sectors_computed: list[str] = []

# Build a ticker → sector map from the universe dataframe
ticker_sector = (
    universe_df[["ticker", "sector"]]
    .set_index("ticker")["sector"]
    .where(universe_df.set_index("ticker")["sector"] != "", other=pd.NA)
    .dropna()
)

unique_sectors = [s for s in ticker_sector.unique() if s and s != "nan"]
print(f"  GICS sectors found: {len(unique_sectors)}")

for sector in sorted(unique_sectors):
    sector_tickers = [
        t for t in ticker_sector[ticker_sector == sector].index
        if t in prices_aligned.columns
    ]
    if len(sector_tickers) < 3:
        continue

    sec_valid = valid_mask[sector_tickers]
    sec_above200 = above_200d[sector_tickers]
    sec_pos13w   = pos_13w[sector_tickers]

    safe_name = sanitize_col(sector)
    col_200d  = f"{safe_name}_pct_above_200d_ma"
    col_13w   = f"{safe_name}_pct_positive_13w_return"

    sector_breadth_cols[col_200d] = breadth_fraction(sec_above200, sec_valid)
    sector_breadth_cols[col_13w]  = breadth_fraction(sec_pos13w,   sec_valid)
    sectors_computed.append(sector)
    print(f"    {sector}: {len(sector_tickers)} tickers → computed")

if sector_breadth_cols:
    sector_breadth_df = pd.DataFrame(sector_breadth_cols, index=project_dates)
    sector_breadth_df.index.name = "Date"
    sector_breadth_df["diagnostic_label"] = DIAG_LABEL
    sector_breadth_df.to_csv(OUT / "sector_breadth_weekly.csv")
    print(f"  Saved sector_breadth_weekly.csv "
          f"({sector_breadth_df.shape[0]} weeks × {sector_breadth_df.shape[1]} cols)")
else:
    # Save empty placeholder so validate script can handle gracefully
    pd.DataFrame(columns=["Date", "diagnostic_label"]).to_csv(
        OUT / "sector_breadth_weekly.csv", index=False
    )
    print("  WARNING: No sector breadth computed (no sector metadata available)")


# ══════════════════════════════════════════════════════════════════════════════
# PART G — COVERAGE METRICS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART G: Coverage metrics ===")

breadth_notnull = stock_breadth["pct_above_200d_ma"].notna()
first_good_week = stock_breadth.index[breadth_notnull].min() if breadth_notnull.any() else pd.NaT
last_good_week  = stock_breadth.index[breadth_notnull].max() if breadth_notnull.any() else pd.NaT

# Missingness by week: % of stocks with data
coverage_by_week = valid_mask.mean(axis=1)
thin_weeks = int((coverage_by_week < 0.50).sum())

summary_rows = [
    {"metric": "tickers_requested",        "value": len(dl_tickers)},
    {"metric": "tickers_good",             "value": len(good_tickers)},
    {"metric": "tickers_failed",           "value": len(bad_tickers)},
    {"metric": "coverage_pct",             "value": round(coverage_pct, 1)},
    {"metric": "download_start_date",      "value": PRICE_START},
    {"metric": "download_end_date",        "value": PRICE_END},
    {"metric": "first_breadth_week",       "value": str(first_good_week.date()) if pd.notna(first_good_week) else ""},
    {"metric": "last_breadth_week",        "value": str(last_good_week.date())  if pd.notna(last_good_week)  else ""},
    {"metric": "project_weeks_total",      "value": len(project_dates)},
    {"metric": "breadth_weeks_populated",  "value": int(breadth_notnull.sum())},
    {"metric": "thin_weeks_lt50pct",       "value": thin_weeks},
    {"metric": "sectors_computed",         "value": len(sectors_computed)},
    {"metric": "diagnostic_label",         "value": DIAG_LABEL},
    {"metric": "survivorship_bias_warning", "value": "TRUE — current members backfilled into history"},
    {"metric": "production_valid",         "value": "FALSE"},
]
pd.DataFrame(summary_rows).to_csv(OUT / "stock_breadth_coverage_report.csv", index=False)
print(f"  Saved stock_breadth_coverage_report.csv")
print(f"  Breadth coverage: {int(breadth_notnull.sum())} weeks "
      f"({first_good_week.date() if pd.notna(first_good_week) else 'N/A'} → "
      f"{last_good_week.date() if pd.notna(last_good_week) else 'N/A'})")
print(f"  Thin weeks (< 50% stock coverage): {thin_weeks}")


# ══════════════════════════════════════════════════════════════════════════════
# PART H — METADATA JSON
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART H: Metadata JSON ===")

metadata = {
    "source":                   "yfinance + current Wikipedia S&P 500 list",
    "point_in_time_safe":       False,
    "survivorship_bias_warning": True,
    "production_valid":          False,
    "purpose": (
        "Pipeline prototype and research-only diagnostic. "
        "The data backend can later be swapped to WRDS/CRSP or Norgate "
        "for production-valid (point-in-time) signals."
    ),
    "diagnostic_label":          DIAG_LABEL,
    "fetch_date":                FETCH_DATE,
    "price_window_start":        PRICE_START,
    "price_window_end":          PRICE_END,
    "tickers_requested":         len(dl_tickers),
    "tickers_good":              len(good_tickers),
    "tickers_failed":            len(bad_tickers),
    "coverage_pct":              round(coverage_pct, 1),
    "first_breadth_week":        str(first_good_week.date()) if pd.notna(first_good_week) else "",
    "last_breadth_week":         str(last_good_week.date())  if pd.notna(last_good_week)  else "",
    "project_weeks_total":       len(project_dates),
    "breadth_weeks_populated":   int(breadth_notnull.sum()),
    "sectors_computed":          sectors_computed,
    "breadth_features": [
        "pct_above_50d_ma",
        "pct_above_100d_ma",
        "pct_above_200d_ma",
        "pct_positive_13w_return",
        "pct_positive_26w_return",
        "pct_near_52w_high",
        "equal_weight_stock_return",
        "stock_count_available",
        "median_stock_13w_return",
        "median_stock_26w_return",
    ],
    "output_files": [
        "sp500_current_universe.csv",
        "stock_prices_weekly.csv",
        "stock_returns_weekly.csv",
        "stock_breadth_weekly.csv",
        "sector_breadth_weekly.csv",
        "stock_breadth_coverage_report.csv",
        "stock_breadth_metadata.json",
    ],
    "do_not": [
        "Use these outputs for production portfolio decisions",
        "Promote any strategy candidate based on these results",
        "Claim survivorship-bias-free analysis",
        "Change production or shadow pins",
    ],
    "next_step": (
        "Purchase Norgate US Stocks Platinum/Diamond or WRDS/CRSP "
        "for point-in-time constituent history before building a "
        "production-valid stock breadth signal."
    ),
}

with open(OUT / "stock_breadth_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
print(f"  Saved stock_breadth_metadata.json")


# ── Final summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("BUILD COMPLETE")
print(f"  Output dir : {OUT}")
print(f"  Universe   : {len(good_tickers)} good tickers / {len(dl_tickers)} requested")
print(f"  Coverage   : {coverage_pct:.1f}%")
print(f"  Breadth    : {int(breadth_notnull.sum())} weeks populated")
print(f"  Bias       : !! {DIAG_LABEL} !!")
print("=" * 68)
