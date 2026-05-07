# How to Install Real Stock Breadth Inputs

## These files are templates only — they contain no usable data

The `*_TEMPLATE.csv` files in this directory define the required column schemas.
They are not real data. **Do not use them to build breadth signals or portfolio candidates.**

---

## Why point-in-time data is required

Using today's S&P 500 or Nasdaq-100 constituents as historical index membership is
**survivorship-biased**: it back-fills current winners into the past and excludes
companies that were delisted, went bankrupt, or were removed from the index.
Any breadth signal built on current-constituent lists will appear stronger in history
than it would have been in real time. No production decision should be based on
current-constituent or survivorship-biased diagnostics.

---

## Preferred data source paths

### Option 1 — Norgate Data US Stocks Platinum or Diamond (recommended)
- Provides point-in-time index constituents for S&P 500, Russell 2000, Nasdaq-100, etc.
- Includes delisted tickers with accurate delisting returns
- Python API: `norgate` package
- After exporting, rename or copy to the real input filenames below

### Option 2 — CRSP/Compustat via WRDS
- CRSP provides point-in-time S&P index constituents (`crsp.msp500list`)
- Adjusted prices with accurate split/dividend history
- Delisted returns in CRSP delistings table
- Requires WRDS institutional subscription

### Option 3 — Sharadar / Nasdaq Data Link (with caution)
- `SHARADAR/TICKERS` provides some historical delisted-stock metadata
- `SHARADAR/SEP` provides daily prices for active and some delisted stocks
- Verify that point-in-time S&P 500 constituent history is complete before use
- Check delisted-stock coverage carefully — missing delistings = survivorship bias

---

## Current-constituents + yfinance: diagnostic only, not promotable

Pulling today's S&P 500 members via `requests`/Wikipedia and pricing them with
`yfinance` is permitted for **diagnostic inspection only** (to confirm the pipeline
runs end-to-end). Any breadth signals produced from this approach:

- Are survivorship-biased
- Cannot be used to train or validate strategy candidates
- Cannot be committed to the repo as real research outputs
- Will not be promoted to shadow or production

---

## Real input file names expected by `build_pit_stock_breadth_panel.py`

After exporting from your chosen source, save or rename your files to:

| Schema template | Real input file (csv or parquet) |
|---|---|
| `index_membership_TEMPLATE.csv` | `index_membership.csv` or `index_membership.parquet` |
| `stock_prices_daily_TEMPLATE.csv` | `stock_prices_daily.csv`, `stock_prices_daily.parquet`, or `stock_prices_daily/` (partitioned parquet) |
| `security_master_TEMPLATE.csv` | `security_master.csv` or `security_master.parquet` |
| `sector_classification_TEMPLATE.csv` | `sector_classification.csv` or `sector_classification.parquet` |

---

## Then run

```bash
python3 scripts/build_pit_stock_breadth_panel.py
```

The script will:
1. Detect the real input files
2. Validate required columns and data quality
3. Build the weekly breadth panel at `data/stock_breadth/processed/stock_breadth_weekly.csv`
4. (If sector data is present) Build `data/stock_breadth/processed/stock_breadth_by_sector_weekly.csv`

---

## File size and commit warnings

Raw stock price panels for S&P 500 constituents (2005–present) typically range from
300 MB to several GB depending on format. These files:

- **Usually cannot be committed to GitHub** (100 MB file limit)
- Should remain local, in an external storage location, or be tracked via Git LFS
- Check file sizes before any `git add` with `du -sh data/stock_breadth/raw/*`

Processed aggregate breadth files (`stock_breadth_weekly.csv`) are small (~100–500 KB)
and are commit-safe after a size and license check.
