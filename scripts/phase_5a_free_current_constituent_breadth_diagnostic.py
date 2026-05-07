#!/usr/bin/env python3
"""
Phase 5A-Free — Current-Constituent Diagnostic Stock Breadth Prototype

!! SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY !!

This script uses CURRENT S&P 500 constituents and yfinance to build a diagnostic
stock breadth panel. The results ARE survivorship-biased because:
  - Current members are backfilled into history (winners only)
  - Removed, bankrupt, delisted, and failed companies are excluded
  - No point-in-time constituent history is used

Purpose: Decide whether PIT stock breadth data (Norgate/WRDS/Sharadar) is worth
         paying for before building a production-quality signal.

Do NOT use these outputs for:
  - Production portfolio decisions
  - Promotion of strategy candidates
  - Claiming survivorship-bias-free analysis
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DIAG_LABEL = "SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY"
FETCH_DATE = str(date.today())
PRICE_START = "2020-01-01"
PRICE_END = "2026-04-30"
MAX_TICKERS_SAMPLE = 100    # fallback sample if full download is too slow
FULL_DOWNLOAD = True         # try all constituents first

ROOT = Path(__file__).resolve().parents[1]
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
HUB = ROOT / "data" / "01_data_hub"
OUT = ROOT / "data" / "research" / "phase_5a_free_current_constituent_breadth_diagnostic"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS = 52


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def tag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["diagnostic_label"] = DIAG_LABEL
    return df


def calc_ann_return(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 4:
        return np.nan
    return float((1 + s).prod() ** (WEEKS / len(s)) - 1)


def fwd_n(s: pd.Series, n: int) -> pd.Series:
    return (1 + s).rolling(n).apply(lambda x: x.prod() - 1, raw=True).shift(-n)


# ──────────────────────────────────────────────
# PART A — BIAS DISCLOSURE
# ──────────────────────────────────────────────
print("=== PART A: Bias disclosure ===")

bias_rows = [{
    "item": "data_source", "value": "current S&P 500 constituents + yfinance",
    "diagnostic_label": DIAG_LABEL,
}, {
    "item": "point_in_time_safe", "value": "False", "diagnostic_label": DIAG_LABEL,
}, {
    "item": "survivorship_biased", "value": "True", "diagnostic_label": DIAG_LABEL,
}, {
    "item": "production_decision_safe", "value": "False", "diagnostic_label": DIAG_LABEL,
}, {
    "item": "research_only_safe", "value": "True", "diagnostic_label": DIAG_LABEL,
}, {
    "item": "allowed_use", "value": "diagnostic only — decide if PIT data is worth buying",
    "diagnostic_label": DIAG_LABEL,
}, {
    "item": "prohibited_use",
    "value": "production promotion; final strategy claim; survivorship-bias-free claim",
    "diagnostic_label": DIAG_LABEL,
}, {
    "item": "reason",
    "value": "current members are backfilled historically and exclude removed/delisted/failed companies",
    "diagnostic_label": DIAG_LABEL,
}]
pd.DataFrame(bias_rows).to_csv(OUT / "phase5a_free_bias_disclosure.csv", index=False)

rules_rows = [{
    "rule": "DO_NOT_PROMOTE", "description": "Do not promote any strategy candidate from this diagnostic",
    "diagnostic_label": DIAG_LABEL,
}, {
    "rule": "DO_NOT_CLAIM_VALIDITY", "description": "Do not claim these results are valid production backtests",
    "diagnostic_label": DIAG_LABEL,
}, {
    "rule": "DO_NOT_CHANGE_PINS", "description": "Do not change production or shadow pins",
    "diagnostic_label": DIAG_LABEL,
}, {
    "rule": "DO_NOT_USE_CURRENT_AS_HISTORICAL",
    "description": "Current constituents are not historical PIT truth",
    "diagnostic_label": DIAG_LABEL,
}, {
    "rule": "ONLY_DECIDE_IF_PIT_DATA_WORTH_PAYING",
    "description": "Sole purpose: assess whether PIT stock breadth signal is promising",
    "diagnostic_label": DIAG_LABEL,
}]
pd.DataFrame(rules_rows).to_csv(OUT / "phase5a_free_usage_rules.csv", index=False)
print(f"  Saved bias disclosure and usage rules")


# ──────────────────────────────────────────────
# PART B — CURRENT CONSTITUENT UNIVERSE
# ──────────────────────────────────────────────
print("\n=== PART B: Fetch current constituent universe ===")

MANUAL_TEMPLATE = OUT / "manual_current_constituents_TEMPLATE.csv"
MANUAL_FILLED = OUT / "manual_current_constituents.csv"

_UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html_tables(url: str) -> list[pd.DataFrame]:
    """Fetch page HTML with a browser-like User-Agent, then parse tables with read_html."""
    import requests as _requests
    resp = _requests.get(url, headers=_UA_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_html(resp.text, header=0)


def write_manual_template() -> None:
    """Write blank template CSV for manual constituent entry."""
    tmpl = pd.DataFrame(columns=[
        "ticker", "company", "sector", "index_name",
        "source_url", "fetch_date", "diagnostic_label",
    ])
    tmpl.to_csv(MANUAL_TEMPLATE, index=False)
    print(f"  Wrote manual template: {MANUAL_TEMPLATE.name}")
    print("  Fill it in with current S&P 500 / Nasdaq-100 tickers and re-run.")
    print("  Then rename it (remove _TEMPLATE) so the script picks it up:")
    print(f"    cp '{MANUAL_TEMPLATE}' '{MANUAL_FILLED}'")


tickers_sp500: list[str] = []
tickers_ndx: list[str] = []
tickers_meta: list[dict] = []
universe_error: str | None = None

# --- Attempt 1: S&P 500 from Wikipedia ---
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
try:
    tables = fetch_html_tables(sp500_url)
    sp500_table = tables[0]
    ticker_col = next((c for c in sp500_table.columns
                       if "symbol" in c.lower() or "ticker" in c.lower()), None)
    name_col = next((c for c in sp500_table.columns
                     if "security" in c.lower() or "company" in c.lower()), None)
    sector_col = next((c for c in sp500_table.columns
                       if "sector" in c.lower() or "gics" in c.lower()), None)
    if ticker_col is None:
        raise ValueError(f"No ticker column found — columns: {list(sp500_table.columns)}")
    tickers_sp500 = (sp500_table[ticker_col]
                     .dropna().str.strip()
                     .str.replace(".", "-", regex=False).tolist())
    for _, row in sp500_table.iterrows():
        tickers_meta.append({
            "ticker": str(row[ticker_col]).strip().replace(".", "-"),
            "name": str(row[name_col]).strip() if name_col else "",
            "sector": str(row[sector_col]).strip() if sector_col else "",
            "index": "S&P 500",
            "source_url": sp500_url,
            "fetch_date": FETCH_DATE,
            "diagnostic_label": DIAG_LABEL,
        })
    print(f"  S&P 500: {len(tickers_sp500)} tickers fetched from Wikipedia")
except Exception as e:
    universe_error = str(e)
    print(f"  S&P 500 fetch failed: {e}")

# --- Attempt 2: Nasdaq-100 from Wikipedia ---
ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
try:
    tables_ndx = fetch_html_tables(ndx_url)
    for t in tables_ndx:
        t_cols_lower = [c.lower() for c in t.columns]
        if any("ticker" in c or "symbol" in c for c in t_cols_lower) and len(t) > 50:
            ticker_col_ndx = next(
                (c for c in t.columns if "ticker" in c.lower() or "symbol" in c.lower()), None
            )
            if ticker_col_ndx:
                tickers_ndx = (t[ticker_col_ndx]
                               .dropna().str.strip()
                               .str.replace(".", "-", regex=False).tolist())
                existing_set = {m["ticker"] for m in tickers_meta}
                for tk in tickers_ndx:
                    if tk not in existing_set:
                        tickers_meta.append({
                            "ticker": tk, "name": "", "sector": "",
                            "index": "Nasdaq-100",
                            "source_url": ndx_url,
                            "fetch_date": FETCH_DATE,
                            "diagnostic_label": DIAG_LABEL,
                        })
                break
    print(f"  Nasdaq-100: {len(tickers_ndx)} tickers fetched from Wikipedia")
except Exception as e:
    print(f"  Nasdaq-100 fetch failed (non-critical): {e}")

# --- Attempt 3: manual filled file ---
if not tickers_sp500 and not tickers_ndx:
    if MANUAL_FILLED.exists():
        try:
            manual_df = pd.read_csv(MANUAL_FILLED)
            manual_df = manual_df.dropna(subset=["ticker"])
            if len(manual_df) > 0:
                tickers_meta = manual_df.to_dict("records")
                tickers_sp500 = manual_df[manual_df.get("index_name", pd.Series()) == "S&P 500"]["ticker"].tolist() \
                    if "index_name" in manual_df.columns else manual_df["ticker"].tolist()
                print(f"  Loaded manual constituent file: {len(manual_df)} tickers")
        except Exception as e:
            print(f"  Manual file load failed: {e}")

# --- All sources failed — write template and exit cleanly ---
if not tickers_sp500 and not tickers_ndx and not tickers_meta:
    pd.DataFrame([{
        "error": universe_error or "all fetch attempts failed",
        "fetch_date": FETCH_DATE,
        "sp500_url_tried": sp500_url,
        "ndx_url_tried": ndx_url,
        "diagnostic_label": DIAG_LABEL,
    }]).to_csv(OUT / "phase5a_free_universe_fetch_error.csv", index=False)
    write_manual_template()
    print("\n  STOPPED: No constituent universe could be fetched.")
    print("  Options to continue:")
    print("  1) Re-run after network connectivity is restored.")
    print(f"  2) Fill {MANUAL_TEMPLATE.name}, rename to manual_current_constituents.csv, re-run.")
    sys.exit(0)

universe_df = tag(pd.DataFrame(tickers_meta)).drop_duplicates("ticker")
universe_df.to_csv(OUT / "phase5a_free_current_constituent_universe.csv", index=False)

tag(pd.DataFrame([{
    "universe": "S&P 500", "tickers_fetched": len(tickers_sp500),
    "fetch_date": FETCH_DATE, "diagnostic_label": DIAG_LABEL,
}, {
    "universe": "Nasdaq-100", "tickers_fetched": len(tickers_ndx),
    "fetch_date": FETCH_DATE, "diagnostic_label": DIAG_LABEL,
}, {
    "universe": "combined_unique", "tickers_fetched": len(universe_df),
    "fetch_date": FETCH_DATE, "diagnostic_label": DIAG_LABEL,
}])).to_csv(OUT / "phase5a_free_universe_summary.csv", index=False)
print(f"  Combined unique tickers: {len(universe_df)}")


# ──────────────────────────────────────────────
# PART C — YFINANCE PRICE DOWNLOAD
# ──────────────────────────────────────────────
print("\n=== PART C: yfinance price download ===")

try:
    import yfinance as yf
    print(f"  yfinance version: {yf.__version__}")
except ImportError:
    print("  yfinance NOT installed.")
    print("  Run: pip install yfinance")
    pd.DataFrame([{"status": "MISSING", "install": "pip install yfinance",
                    "diagnostic_label": DIAG_LABEL}]).to_csv(
        OUT / "phase5a_free_price_download_status.csv", index=False)
    sys.exit(0)

# Use S&P 500 as primary download list
all_tickers = tickers_sp500 if tickers_sp500 else tickers_ndx
# Remove common problem tickers
problem_patterns = [".", "/"]
all_tickers = [t for t in all_tickers if not any(p in t for p in problem_patterns)]

if not FULL_DOWNLOAD:
    all_tickers = all_tickers[:MAX_TICKERS_SAMPLE]
    print(f"  Limited to sample of {MAX_TICKERS_SAMPLE} tickers")

print(f"  Downloading {len(all_tickers)} tickers from {PRICE_START} to {PRICE_END}")
print("  (downloading adjusted close only — this may take 1-3 minutes)")

# Download in a single batch call
try:
    raw = yf.download(
        tickers=all_tickers,
        start=PRICE_START,
        end=PRICE_END,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="ticker",
    )
    download_ok = True
    print(f"  Download complete. Raw shape: {raw.shape}")
except Exception as e:
    print(f"  yfinance download failed: {e}")
    pd.DataFrame([{"status": "FAILED", "error": str(e), "diagnostic_label": DIAG_LABEL}]).to_csv(
        OUT / "phase5a_free_price_download_status.csv", index=False)
    sys.exit(0)

# ── Robust adjclose extraction ──────────────────────────────────────────────
# yfinance 1.x with group_by="ticker" and auto_adjust=True produces a
# MultiIndex DataFrame: level-0 = ticker, level-1 = price type
# (Close, High, Low, Open, Volume).  Extract only the Close level.
def _extract_adjclose(raw_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw_df.columns, pd.MultiIndex):
        # Single ticker or already flat
        return raw_df[["Close"]] if "Close" in raw_df.columns else raw_df

    levels = [raw_df.columns.get_level_values(i) for i in range(raw_df.columns.nlevels)]
    # Detect which level holds price types (Close/Open/...) vs ticker names
    # Price-type level always contains "Close"; ticker level never does (usually).
    price_level = next(
        (i for i, lvl in enumerate(levels) if "Close" in lvl),
        None,
    )
    if price_level is None:
        # Fallback: return as-is (already one price per column)
        return raw_df

    ticker_level = 1 - price_level  # the other level
    try:
        out = raw_df.xs("Close", axis=1, level=price_level)
    except Exception:
        # xs can fail on some MultiIndex configurations — try direct slice
        close_mask = raw_df.columns.get_level_values(price_level) == "Close"
        out = raw_df.loc[:, close_mask]
        out.columns = raw_df.columns.get_level_values(ticker_level)[close_mask]
    return out


adjclose = _extract_adjclose(raw)

# ── Deduplicate columns ──────────────────────────────────────────────────────
# Some tickers appear in both S&P 500 and Nasdaq-100 lists, or yfinance
# returns duplicate columns.  Keep the first occurrence of each ticker name.
if adjclose.columns.duplicated().any():
    seen: set[str] = set()
    keep: list[int] = []
    for i, col in enumerate(adjclose.columns):
        if col not in seen:
            seen.add(col)
            keep.append(i)
    adjclose = adjclose.iloc[:, keep]

adjclose = adjclose.dropna(how="all").sort_index()
print(f"  Adjusted close panel: {adjclose.shape[0]} days × {adjclose.shape[1]} tickers")

# Coverage report
status_rows = []
for ticker in all_tickers:
    if ticker not in adjclose.columns:
        status_rows.append({
            "ticker": ticker, "status": "MISSING",
            "start_date": "", "end_date": "", "n_observations": 0,
            "missingness_pct": 100.0, "failed_download": True,
            "diagnostic_label": DIAG_LABEL,
        })
        continue

    raw_col = adjclose[ticker]
    # Guard: if a duplicate slipped through, coerce to Series (first column)
    if isinstance(raw_col, pd.DataFrame):
        raw_col = raw_col.iloc[:, 0]
        warn_flag = True
    else:
        warn_flag = False

    col = raw_col.dropna()
    miss = float(raw_col.isna().mean())
    status_rows.append({
        "ticker": ticker,
        "status": "WARN_DUPLICATE" if warn_flag else "OK",
        "start_date": str(col.index[0].date()) if len(col) > 0 else "",
        "end_date": str(col.index[-1].date()) if len(col) > 0 else "",
        "n_observations": len(col),
        "missingness_pct": round(miss * 100, 2),
        "failed_download": miss > 0.5,
        "diagnostic_label": DIAG_LABEL,
    })

status_df = pd.DataFrame(status_rows)
status_df.to_csv(OUT / "phase5a_free_price_download_status.csv", index=False)

good_tickers = status_df[status_df["failed_download"] == False]["ticker"].tolist()
bad_tickers = status_df[status_df["failed_download"] == True]["ticker"].tolist()
print(f"  Good tickers: {len(good_tickers)}, failed: {len(bad_tickers)}")
coverage_pct = len(good_tickers) / len(all_tickers) * 100
print(f"  Coverage: {coverage_pct:.1f}%")

if coverage_pct < 50:
    print("  WARNING: Less than 50% coverage — results may be unreliable")

# Save adjusted close (long format, compressed)
adjclose_good = adjclose[good_tickers].copy()
price_path = OUT / "phase5a_free_stock_prices_adjclose_daily.parquet"
try:
    adjclose_good.to_parquet(price_path)
    size_mb = price_path.stat().st_size / 1e6
    print(f"  Saved prices as parquet: {size_mb:.1f} MB")
    if size_mb > 95:
        print("  WARNING: Price file approaching 100MB limit")
        # Fall back to CSV of just Close columns
        price_path.unlink()
        price_path = OUT / "phase5a_free_stock_prices_adjclose_daily.csv"
        adjclose_good.to_csv(price_path)
        size_mb = price_path.stat().st_size / 1e6
        print(f"  Saved as CSV instead: {size_mb:.1f} MB")
except Exception:
    price_path = OUT / "phase5a_free_stock_prices_adjclose_daily.csv"
    adjclose_good.to_csv(price_path)
    size_mb = price_path.stat().st_size / 1e6
    print(f"  Saved prices as CSV: {size_mb:.1f} MB")

# Coverage report
cov_rows = [{
    "metric": "total_tickers_attempted", "value": len(all_tickers),
    "diagnostic_label": DIAG_LABEL,
}, {
    "metric": "good_tickers", "value": len(good_tickers), "diagnostic_label": DIAG_LABEL,
}, {
    "metric": "failed_tickers", "value": len(bad_tickers), "diagnostic_label": DIAG_LABEL,
}, {
    "metric": "coverage_pct", "value": round(coverage_pct, 1), "diagnostic_label": DIAG_LABEL,
}, {
    "metric": "date_range", "value": f"{PRICE_START} to {PRICE_END}", "diagnostic_label": DIAG_LABEL,
}, {
    "metric": "price_file_mb", "value": round(size_mb, 1), "diagnostic_label": DIAG_LABEL,
}, {
    "metric": "survivorship_bias_warning",
    "value": DIAG_LABEL, "diagnostic_label": DIAG_LABEL,
}]
pd.DataFrame(cov_rows).to_csv(OUT / "phase5a_free_price_coverage_report.csv", index=False)


# ──────────────────────────────────────────────
# PART D — BUILD DIAGNOSTIC BREADTH FEATURES
# ──────────────────────────────────────────────
print("\n=== PART D: Build diagnostic breadth features ===")

daily = adjclose_good.sort_index()
daily = daily.dropna(how="all")

# Weekly snapshots (Friday close)
weekly = daily.resample("W-FRI").last().dropna(how="all")
print(f"  Weekly panel: {weekly.shape[0]} weeks × {weekly.shape[1]} tickers")

# Rolling computations on daily prices (causal, trailing only)
ma50 = daily.rolling(50, min_periods=40).mean()
ma100 = daily.rolling(100, min_periods=80).mean()
ma200 = daily.rolling(200, min_periods=160).mean()

above_50d = (daily > ma50).resample("W-FRI").last()
above_100d = (daily > ma100).resample("W-FRI").last()
above_200d = (daily > ma200).resample("W-FRI").last()

weekly_ret = weekly.pct_change()
pos_4w = weekly.pct_change(4) > 0
pos_13w = weekly.pct_change(13) > 0
pos_26w = weekly.pct_change(26) > 0

high_13w = weekly >= weekly.rolling(13, min_periods=10).max()
high_52w = weekly >= weekly.rolling(52, min_periods=40).max()

drawdown = weekly / weekly.rolling(52, min_periods=20).max() - 1.0
dd_lt_10 = drawdown > -0.10

# Build breadth panel
breadth_rows = []
tickers_in_panel = [t for t in good_tickers if t in weekly.columns]

for week in weekly.index:
    n = weekly.loc[week].notna().sum()
    if n < 20:
        continue

    def safe_mean(s: pd.Series) -> float:
        v = s.reindex(index=[week])
        if v.empty or v.isna().all():
            return np.nan
        return float(v.iloc[0].mean() if hasattr(v.iloc[0], 'mean') else v.iloc[0])

    def col_mean(df: pd.DataFrame) -> float:
        row = df.reindex([week])
        if row.empty:
            return np.nan
        return float(row.iloc[0].mean())

    ew_ret = float(weekly_ret.loc[week].mean()) if week in weekly_ret.index else np.nan

    row = {
        "date": week,
        "active_member_count": int(n),
        "pct_members_above_50d_ma": col_mean(above_50d),
        "pct_members_above_100d_ma": col_mean(above_100d),
        "pct_members_above_200d_ma": col_mean(above_200d),
        "pct_members_positive_4w_return": col_mean(pos_4w),
        "pct_members_positive_13w_return": col_mean(pos_13w),
        "pct_members_positive_26w_return": col_mean(pos_26w),
        "pct_members_with_13w_high": col_mean(high_13w),
        "pct_members_with_52w_high": col_mean(high_52w),
        "pct_members_in_drawdown_less_than_10pct": col_mean(dd_lt_10),
        "equal_weight_current_constituent_return": ew_ret,
        "median_member_13w_return": float(weekly.pct_change(13).loc[week].median()) if week in weekly.index else np.nan,
        "diagnostic_label": DIAG_LABEL,
    }
    breadth_rows.append(row)

breadth = pd.DataFrame(breadth_rows).set_index("date").sort_index()

# Derived features
breadth["breadth_thrust_4w"] = (breadth["pct_members_above_50d_ma"]
                                 - breadth["pct_members_above_50d_ma"].shift(4))
breadth["breadth_thrust_8w"] = (breadth["pct_members_above_50d_ma"]
                                 - breadth["pct_members_above_50d_ma"].shift(8))
breadth["broad_bull_diagnostic_flag"] = (
    (breadth["pct_members_above_200d_ma"] >= 0.65) &
    (breadth["pct_members_positive_26w_return"] >= 0.60) &
    (breadth["breadth_thrust_4w"] >= -0.05)
).astype(int)
breadth["narrow_bull_diagnostic_warning"] = (
    (breadth["pct_members_above_200d_ma"] < 0.45) &
    (breadth["pct_members_positive_26w_return"] < 0.45)
).astype(int)
breadth["neutral_risk_on_diagnostic"] = (
    (breadth["pct_members_above_200d_ma"] >= 0.55) &
    (breadth["pct_members_positive_13w_return"] >= 0.50)
).astype(int)

# Lagged versions (causal — lag 1 week before use in any model)
lag_cols = [c for c in breadth.columns if c not in {"diagnostic_label", "active_member_count"}]
for col in lag_cols:
    breadth[f"{col}_lag1w"] = breadth[col].shift(1)

breadth.to_csv(OUT / "phase5a_free_stock_breadth_weekly.csv")
print(f"  Saved breadth panel: {len(breadth)} weeks × {len(breadth.columns)} features")
print(f"  Date range: {breadth.index[0].date()} to {breadth.index[-1].date()}")

# Feature manifest
manifest_rows = []
for col in [c for c in breadth.columns if not c.startswith("pct") and "lag" not in c]:
    pass
for col in lag_cols:
    manifest_rows.append({
        "feature": col,
        "lag1w_feature": f"{col}_lag1w",
        "causal_ok": True,
        "use_lag1w_for_trading": True,
        "diagnostic_label": DIAG_LABEL,
    })
tag(pd.DataFrame(manifest_rows)).to_csv(OUT / "phase5a_free_stock_breadth_feature_manifest.csv", index=False)
tag(pd.DataFrame([{
    "weeks_in_panel": len(breadth),
    "tickers_used": len(tickers_in_panel),
    "date_start": str(breadth.index[0].date()),
    "date_end": str(breadth.index[-1].date()),
    "survivorship_biased": True,
    "diagnostic_label": DIAG_LABEL,
}])).to_csv(OUT / "phase5a_free_stock_breadth_coverage_report.csv", index=False)


# ──────────────────────────────────────────────
# PART E — DIAGNOSTIC SIGNAL DEFINITIONS
# ──────────────────────────────────────────────
print("\n=== PART E: Signal definitions ===")

# Load market state history for state-conditional signals
msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)

# Align breadth to market state weekly index (both Friday)
breadth_aligned = breadth.reindex(msh.index)

# Load ETF weekly returns
wr = pd.read_csv(HUB / "weekly_returns.csv", index_col="Date", parse_dates=True)
spy = wr["SPY"]

# Causal lag: use _lag1w columns for any forward-looking comparison
b = breadth_aligned  # alias

signal_defs = []
signal_panel_rows = []

# Define signals using lag1w features (causal)
def sig_active(name: str) -> pd.Series:
    """Return the signal series and record its definition."""
    return signals[name]

signals: dict[str, pd.Series] = {}

# 1. broad_stock_bull_diagnostic
s = (
    (b["broad_bull_diagnostic_flag_lag1w"].fillna(0) == 1) &
    (msh["market_trend_positive"] == 1) &
    (~msh["market_state"].isin(["stressed_panic"]))
)
signals["broad_stock_bull_diagnostic"] = s

# 2. narrow_bull_warning_diagnostic
s2 = (
    (b["narrow_bull_diagnostic_warning_lag1w"].fillna(0) == 1) &
    (spy > 0)  # SPY positive on the week (not perfect lag but diagnostic ok)
)
signals["narrow_bull_warning_diagnostic"] = s2

# 3. neutral_stock_risk_on_diagnostic
s3 = (
    (msh["market_state"] == "neutral_mixed") &
    (b["neutral_risk_on_diagnostic_lag1w"].fillna(0) == 1)
)
signals["neutral_stock_risk_on_diagnostic"] = s3

# 4. neutral_stock_chop_warning_diagnostic
s4 = (
    (msh["market_state"] == "neutral_mixed") &
    (b["pct_members_above_200d_ma_lag1w"].fillna(0) < 0.50)
)
signals["neutral_stock_chop_warning_diagnostic"] = s4

# 5. recovery_stock_confirmed_diagnostic
s5 = (
    (msh["market_state"].isin(["recovery_confirmed", "recovery_fragile"])) &
    (b["breadth_thrust_4w_lag1w"].fillna(-1) > 0.02)
)
signals["recovery_stock_confirmed_diagnostic"] = s5

# 6. fake_recovery_warning_diagnostic
s6 = (
    (msh["market_state"].isin(["recovery_confirmed", "recovery_fragile"])) &
    (b["pct_members_positive_13w_return_lag1w"].fillna(1) < 0.45)
)
signals["fake_recovery_warning_diagnostic"] = s6

# 7. diagnostic_aggression_score (0-1)
score = (
    b["pct_members_above_200d_ma_lag1w"].fillna(0) * 0.35 +
    b["pct_members_positive_26w_return_lag1w"].fillna(0) * 0.30 +
    b["pct_members_above_50d_ma_lag1w"].fillna(0) * 0.20 +
    (b["breadth_thrust_4w_lag1w"].fillna(0).clip(-1, 1) + 1) / 2 * 0.15
)
breadth_aligned["diagnostic_aggression_score"] = score.clip(0, 1)
signals["diagnostic_aggression_score_high"] = score.fillna(0) >= 0.65

for name, sig in signals.items():
    active_n = int(sig.sum()) if sig.dtype == bool else int((sig >= 0.65).sum())
    freq = round(float(sig.mean()), 3) if hasattr(sig, 'mean') else 0
    state_cov = {}
    if sig.dtype == bool or sig.dtype == int:
        for st in msh["market_state"].unique():
            st_mask = msh["market_state"] == st
            state_cov[st] = int((sig & st_mask).sum())

    signal_defs.append({
        "signal": name,
        "active_weeks": active_n,
        "active_frequency": freq,
        "lag_rule": "use _lag1w features — 1 week causal lag",
        "state_coverage_calm": state_cov.get("calm_trend", ""),
        "state_coverage_neutral": state_cov.get("neutral_mixed", ""),
        "state_coverage_stressed": state_cov.get("stressed_panic", ""),
        "state_coverage_rc": state_cov.get("recovery_confirmed", ""),
        "causal_ok": True,
        "diagnostic_label": DIAG_LABEL,
    })

pd.DataFrame(signal_defs).to_csv(OUT / "phase5a_free_signal_definitions.csv", index=False)

# Signal panel
sig_panel = pd.DataFrame({name: sig for name, sig in signals.items()}, index=msh.index)
sig_panel["diagnostic_aggression_score"] = score
sig_panel["diagnostic_label"] = DIAG_LABEL
sig_panel.to_csv(OUT / "phase5a_free_signal_panel.csv")

# Coverage
cov_rows_sig = []
for name, sig in signals.items():
    for st in msh["market_state"].unique():
        st_mask = msh["market_state"] == st
        if isinstance(sig.dtype, bool) or sig.dtype == object:
            active_in_state = int((sig.astype(bool) & st_mask).sum())
        else:
            active_in_state = int((sig.astype(bool) & st_mask).sum())
        cov_rows_sig.append({"signal": name, "state": st,
                              "active_in_state": active_in_state,
                              "state_total_weeks": int(st_mask.sum()),
                              "diagnostic_label": DIAG_LABEL})
pd.DataFrame(cov_rows_sig).to_csv(OUT / "phase5a_free_signal_coverage.csv", index=False)
print(f"  Defined {len(signals)} diagnostic signals")
for name, sig in signals.items():
    active = int(sig.astype(bool).sum())
    print(f"    {name}: {active} active weeks ({active/len(sig):.1%})")


# ──────────────────────────────────────────────
# PART F — DIAGNOSTIC VALIDATION
# ──────────────────────────────────────────────
print("\n=== PART F: Diagnostic validation ===")

# Load portfolio returns
def load_ret(fname: str) -> pd.Series | None:
    p = L3 / fname
    if p.exists():
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        return df["net_return"] if "net_return" in df.columns else df.iloc[:, 0]
    return None

ggg1 = load_ret("portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv")
phase4b_best = load_ret("portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv")
bench_6040 = (0.60 * wr["SPY"] + 0.40 * pd.read_csv(
    HUB / "benchmark_prices_weekly.csv", index_col="Date", parse_dates=True
)["IEF"].pct_change()).dropna()

portfolios = {
    "spy": wr["SPY"].dropna(),
    "qqq": wr["QQQ"].dropna() if "QQQ" in wr.columns else None,
    "ggg1": ggg1,
    "phase4b_best": phase4b_best,
    "bench_60_40": bench_6040,
}
portfolios = {k: v for k, v in portfolios.items() if v is not None}

val_rows = []
for sig_name in ["broad_stock_bull_diagnostic", "neutral_stock_risk_on_diagnostic",
                  "recovery_stock_confirmed_diagnostic", "diagnostic_aggression_score_high"]:
    sig = signals[sig_name].astype(bool)
    sig_off = ~sig

    for horizon in [4, 8, 13]:
        for pname, pret in portfolios.items():
            # Limit to 2020-forward for diagnostic
            mask_2020 = pret.index >= "2020-01-01"
            for window_label, window_mask in [("2020_forward", mask_2020),
                                               ("2021_forward", pret.index >= "2021-01-01")]:
                p_slc = pret[window_mask]
                s_slc = sig.reindex(p_slc.index).fillna(False)
                s_off = sig_off.reindex(p_slc.index).fillna(True)

                fwd = fwd_n(p_slc, horizon)
                on_fwd = fwd[s_slc].dropna()
                off_fwd = fwd[s_off].dropna()

                val_rows.append({
                    "signal": sig_name,
                    "portfolio": pname,
                    "horizon_weeks": horizon,
                    "window": window_label,
                    "n_signal_on": len(on_fwd),
                    "n_signal_off": len(off_fwd),
                    "mean_fwd_signal_on": round(float(on_fwd.mean()), 5) if len(on_fwd) > 2 else np.nan,
                    "mean_fwd_signal_off": round(float(off_fwd.mean()), 5) if len(off_fwd) > 2 else np.nan,
                    "lift_vs_inactive": round(float(on_fwd.mean() - off_fwd.mean()), 5) if len(on_fwd) > 2 and len(off_fwd) > 2 else np.nan,
                    "hit_rate_positive": round(float((on_fwd > 0).mean()), 3) if len(on_fwd) > 2 else np.nan,
                    "adverse_freq": round(float((on_fwd < -0.05).mean()), 3) if len(on_fwd) > 2 else np.nan,
                    "diagnostic_label": DIAG_LABEL,
                })

val_df = pd.DataFrame(val_rows)
val_df.to_csv(OUT / "phase5a_free_signal_validation.csv", index=False)
print(f"  Signal validation: {len(val_df)} rows")

# Same-state signal lift
state_lift_rows = []
for state in ["calm_trend", "neutral_mixed", "recovery_confirmed", "stressed_panic"]:
    state_mask = msh["market_state"] == state
    for pname, pret in portfolios.items():
        for sig_name in ["broad_stock_bull_diagnostic", "neutral_stock_risk_on_diagnostic",
                          "diagnostic_aggression_score_high"]:
            sig = signals[sig_name].astype(bool)
            mask_2020 = pret.index >= "2020-01-01"
            on_mask = sig.reindex(pret.index).fillna(False) & state_mask.reindex(pret.index).fillna(False) & mask_2020
            off_mask = (~sig).reindex(pret.index).fillna(True) & state_mask.reindex(pret.index).fillna(False) & mask_2020

            fwd4 = fwd_n(pret, 4)
            on_v = fwd4[on_mask].dropna()
            off_v = fwd4[off_mask].dropna()

            state_lift_rows.append({
                "state": state, "portfolio": pname, "signal": sig_name,
                "signal_on_weeks": len(on_v), "signal_off_weeks": len(off_v),
                "mean_fwd_4w_on": round(float(on_v.mean()), 5) if len(on_v) > 2 else np.nan,
                "mean_fwd_4w_off": round(float(off_v.mean()), 5) if len(off_v) > 2 else np.nan,
                "lift_4w": round(float(on_v.mean() - off_v.mean()), 5) if len(on_v) > 2 and len(off_v) > 2 else np.nan,
                "diagnostic_label": DIAG_LABEL,
            })

pd.DataFrame(state_lift_rows).to_csv(OUT / "phase5a_free_same_state_signal_lift.csv", index=False)

# Neutral split diagnostic
neutral_rows = []
sig_neutral = signals["neutral_stock_risk_on_diagnostic"].astype(bool)
for pname, pret in portfolios.items():
    p_2020 = pret[pret.index >= "2020-01-01"]
    neutral_mask = msh["market_state"].reindex(p_2020.index) == "neutral_mixed"
    on_mask = sig_neutral.reindex(p_2020.index).fillna(False) & neutral_mask.fillna(False)
    off_mask = (~sig_neutral).reindex(p_2020.index).fillna(True) & neutral_mask.fillna(False)
    for hor in [4, 13]:
        fwd = fwd_n(p_2020, hor)
        on_v = fwd[on_mask].dropna()
        off_v = fwd[off_mask].dropna()
        neutral_rows.append({
            "portfolio": pname, "horizon": hor,
            "neutral_breadth_on_n": len(on_v), "neutral_breadth_off_n": len(off_v),
            "neutral_breadth_on_fwd": round(float(on_v.mean()), 5) if len(on_v) > 2 else np.nan,
            "neutral_breadth_off_fwd": round(float(off_v.mean()), 5) if len(off_v) > 2 else np.nan,
            "lift": round(float(on_v.mean() - off_v.mean()), 5) if len(on_v) > 2 and len(off_v) > 2 else np.nan,
            "diagnostic_label": DIAG_LABEL,
        })
pd.DataFrame(neutral_rows).to_csv(OUT / "phase5a_free_neutral_split_diagnostic.csv", index=False)

# Recovery rerisk diagnostic
recovery_rows = []
sig_rc = signals["recovery_stock_confirmed_diagnostic"].astype(bool)
sig_fake_rc = signals["fake_recovery_warning_diagnostic"].astype(bool)
for pname, pret in portfolios.items():
    p_2020 = pret[pret.index >= "2020-01-01"]
    rc_mask = msh["market_state"].reindex(p_2020.index).isin(["recovery_confirmed", "recovery_fragile"]).fillna(False)
    on_mask = sig_rc.reindex(p_2020.index).fillna(False) & rc_mask
    fake_mask = sig_fake_rc.reindex(p_2020.index).fillna(False) & rc_mask
    off_mask = (~sig_rc).reindex(p_2020.index).fillna(True) & rc_mask
    for hor in [4, 13]:
        fwd = fwd_n(p_2020, hor)
        on_v = fwd[on_mask].dropna()
        off_v = fwd[off_mask].dropna()
        fake_v = fwd[fake_mask].dropna()
        recovery_rows.append({
            "portfolio": pname, "horizon": hor,
            "recovery_breadth_confirmed_n": len(on_v),
            "recovery_breadth_off_n": len(off_v),
            "fake_recovery_n": len(fake_v),
            "recovery_confirmed_fwd": round(float(on_v.mean()), 5) if len(on_v) > 2 else np.nan,
            "recovery_off_fwd": round(float(off_v.mean()), 5) if len(off_v) > 2 else np.nan,
            "fake_recovery_fwd": round(float(fake_v.mean()), 5) if len(fake_v) > 2 else np.nan,
            "lift_confirmed_vs_off": round(float(on_v.mean() - off_v.mean()), 5) if len(on_v) > 2 and len(off_v) > 2 else np.nan,
            "diagnostic_label": DIAG_LABEL,
        })
pd.DataFrame(recovery_rows).to_csv(OUT / "phase5a_free_recovery_rerisk_diagnostic.csv", index=False)

# ETF breadth baseline comparison
# Check if our stock breadth adds lift vs existing ETF breadth (already in market_state_history)
etf_breadth_col = "breadth_sma_43"  # existing ETF breadth
etf_breadth_high = (msh[etf_breadth_col] >= 0.65)

pit_rows = []
for pname in ["spy", "ggg1", "phase4b_best"]:
    if pname not in portfolios:
        continue
    pret = portfolios[pname]
    p_2020 = pret[pret.index >= "2020-01-01"]
    for sig_name, sig in [
        ("etf_breadth_existing", etf_breadth_high),
        ("stock_breadth_diagnostic", signals["broad_stock_bull_diagnostic"]),
        ("aggression_score_high", signals["diagnostic_aggression_score_high"]),
    ]:
        s = sig.astype(bool).reindex(p_2020.index).fillna(False)
        fwd4 = fwd_n(p_2020, 4)
        on_v = fwd4[s].dropna()
        off_v = fwd4[~s].dropna()
        pit_rows.append({
            "portfolio": pname, "signal": sig_name,
            "signal_on_weeks": len(on_v),
            "mean_fwd_4w_on": round(float(on_v.mean()), 5) if len(on_v) > 2 else np.nan,
            "mean_fwd_4w_off": round(float(off_v.mean()), 5) if len(off_v) > 2 else np.nan,
            "lift_vs_off": round(float(on_v.mean() - off_v.mean()), 5) if len(on_v) > 2 and len(off_v) > 2 else np.nan,
            "diagnostic_label": DIAG_LABEL,
        })
pd.DataFrame(pit_rows).to_csv(OUT / "phase5a_free_pit_data_value_assessment.csv", index=False)
print(f"  Validation complete")

# Print key results
print("\n  Key validation results (SPY, 4-week forward, 2020+):")
spy_rows = val_df[(val_df["portfolio"] == "spy") & (val_df["horizon_weeks"] == 4) &
                   (val_df["window"] == "2020_forward")]
for _, r in spy_rows.iterrows():
    print(f"    {r['signal']}: on={r['mean_fwd_signal_on']:.3%} off={r['mean_fwd_signal_off']:.3%} "
          f"lift={r['lift_vs_inactive']:+.3%}")


# ──────────────────────────────────────────────
# PART G — DECISION RULE
# ──────────────────────────────────────────────
print("\n=== PART G: Decision ===")

# Evaluate whether signal shows promise
broad_bull_spy_lift = val_df[
    (val_df["signal"] == "broad_stock_bull_diagnostic") &
    (val_df["portfolio"] == "spy") &
    (val_df["horizon_weeks"] == 4) &
    (val_df["window"] == "2020_forward")
]["lift_vs_inactive"].mean()

neutral_ggg1_lift = val_df[
    (val_df["signal"] == "neutral_stock_risk_on_diagnostic") &
    (val_df["portfolio"] == "ggg1") &
    (val_df["horizon_weeks"] == 4) &
    (val_df["window"] == "2020_forward")
]["lift_vs_inactive"].mean()

# Compare stock breadth vs ETF breadth for spy
stock_lift_spy = next((r["lift_vs_off"] for r in pit_rows
                        if r["portfolio"] == "spy" and r["signal"] == "stock_breadth_diagnostic"), np.nan)
etf_lift_spy = next((r["lift_vs_off"] for r in pit_rows
                      if r["portfolio"] == "spy" and r["signal"] == "etf_breadth_existing"), np.nan)

print(f"  broad_stock_bull SPY 4w lift: {broad_bull_spy_lift:+.3%}")
print(f"  neutral_risk_on GGG1 4w lift: {neutral_ggg1_lift:+.3%}")
print(f"  Stock breadth vs ETF breadth (SPY): stock={stock_lift_spy:+.3%} etf={etf_lift_spy:+.3%}")

# Decision logic
signals_promising = (
    (not np.isnan(broad_bull_spy_lift) and broad_bull_spy_lift > 0.003) or
    (not np.isnan(neutral_ggg1_lift) and neutral_ggg1_lift > 0.001)
)
stock_beats_etf = (
    not np.isnan(stock_lift_spy) and not np.isnan(etf_lift_spy) and
    stock_lift_spy > etf_lift_spy * 0.8  # stock at least 80% as good as existing ETF breadth
)
coverage_sufficient = coverage_pct >= 70

if not coverage_sufficient:
    decision = "DIAGNOSTIC_INCONCLUSIVE_NEEDS_BETTER_FREE_SAMPLE"
    rationale = f"Coverage only {coverage_pct:.0f}% — need better free data sample"
elif signals_promising and stock_beats_etf:
    decision = "DIAGNOSTIC_PROMISING_GET_PIT_DATA"
    rationale = (f"Stock breadth shows lift vs inactive ({broad_bull_spy_lift:+.3%} SPY 4w). "
                 f"Competitive with ETF breadth. PIT data worth purchasing.")
elif signals_promising:
    decision = "DIAGNOSTIC_PROMISING_GET_PIT_DATA"
    rationale = (f"Stock breadth shows some lift ({broad_bull_spy_lift:+.3%}). "
                 f"May be incremental to existing ETF breadth. PIT data likely worth testing.")
else:
    decision = "DIAGNOSTIC_WEAK_SKIP_PAID_STOCK_BREADTH"
    rationale = "Stock breadth adds minimal lift over existing ETF breadth. Reconsider before paying for PIT data."

decision_rows = [{
    "decision": decision,
    "rationale": rationale,
    "broad_bull_spy_4w_lift": round(broad_bull_spy_lift, 5) if not np.isnan(broad_bull_spy_lift) else "N/A",
    "neutral_ggg1_4w_lift": round(neutral_ggg1_lift, 5) if not np.isnan(neutral_ggg1_lift) else "N/A",
    "stock_vs_etf_breadth_spy": f"{stock_lift_spy:+.4f}" if not np.isnan(stock_lift_spy) else "N/A",
    "coverage_pct": round(coverage_pct, 1),
    "survivorship_bias_warning": DIAG_LABEL,
    "next_action": (
        "Purchase Norgate Platinum/Diamond and run build_pit_stock_breadth_panel.py with real PIT data."
        if "PROMISING" in decision else
        "Do not purchase PIT stock breadth data — ETF breadth already covers the signal."
    ),
    "diagnostic_label": DIAG_LABEL,
}]
pd.DataFrame(decision_rows).to_csv(OUT / "phase5a_free_decision.csv", index=False)

next_action_rows = [{
    "action": "REQUIRED_BEFORE_ANY_PRODUCTION_USE",
    "description": "Replace current-constituent data with Norgate/WRDS/Sharadar PIT data",
    "priority": 1 if "PROMISING" in decision else 2,
    "diagnostic_label": DIAG_LABEL,
}, {
    "action": "DO_NOT_PROMOTE",
    "description": "Do not promote any strategy candidate based on this survivorship-biased diagnostic",
    "priority": 0,
    "diagnostic_label": DIAG_LABEL,
}]
pd.DataFrame(next_action_rows).to_csv(OUT / "phase5a_free_next_action_recommendation.csv", index=False)

with open(OUT / "phase5a_free_protocol.json", "w") as f:
    json.dump({
        "phase": "phase_5a_free_current_constituent_breadth_diagnostic",
        "date": FETCH_DATE,
        "classification": DIAG_LABEL,
        "production_pin": "improved_phase2b_regime_confidence_boost",
        "production_candidate": "improved_phaseggg_confirmed_only_robust_offense",
        "decision": decision,
        "coverage_pct": round(coverage_pct, 1),
        "survivorship_biased": True,
        "production_safe": False,
    }, f, indent=2)

print(f"\n  DECISION: {decision}")
print(f"  Rationale: {rationale}")


# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"Output directory: {OUT}")
out_files = sorted(OUT.glob("*"))
print(f"Files created: {len(out_files)}")
for fp in out_files:
    size_kb = fp.stat().st_size / 1024
    print(f"  {fp.name}  ({size_kb:.0f} KB)")

print(f"\nDone. {DIAG_LABEL}")
print("No production pins changed. No portfolio candidates created.")
