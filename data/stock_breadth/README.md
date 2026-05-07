# Point-in-Time Stock Breadth Data

This folder is reserved for future point-in-time stock breadth inputs and
processed breadth summaries. Phase 5A creates the scaffold only. It does not
install, download, or fabricate stock data.

## Expected Layout

- `raw/index_membership.parquet` or `raw/index_membership.csv`
- `raw/stock_prices_daily.parquet`, `raw/stock_prices_daily.csv`, or partitioned `raw/stock_prices_daily/`
- `raw/security_master.csv`
- `raw/sector_classification.csv`
- `interim/` for temporary normalized extracts
- `processed/stock_breadth_weekly.csv`
- `processed/stock_breadth_by_sector_weekly.csv`
- `metadata/source_manifest.csv`
- `metadata/data_quality_report.csv`
- `metadata/bias_risk_register.csv`
- `metadata/missing_inputs_report.csv`

## Required Rules

Use point-in-time index membership with effective start/end dates. Do not use
today's S&P 500 or Nasdaq-100 constituents as historical truth. Current
constituent diagnostics must be labeled `SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY`
and cannot support production or shadow promotion.

Daily prices must include split/dividend-adjusted close values. Delisted and
dead stocks should be included wherever possible, and delisting return handling
must be documented in `metadata/source_manifest.csv`.

Use a stable security id. Ticker alone is not enough because tickers change,
merge, disappear, and get reused.

All breadth features must be causal. Features through week `t` can only be used
as portfolio signals after an explicit one-week lag, e.g. `feature_lag1w`.

## Git And File Size

Never commit files over GitHub's 100 MB limit. Large raw stock panels should
stay local, use Git LFS, or live in external storage. Normal git should only
track this README, small source manifests, schema files, validation reports, and
small processed summaries after their size is checked.

Recommended future `.gitignore` rules, not applied automatically in Phase 5A:

```gitignore
data/stock_breadth/raw/*.parquet
data/stock_breadth/raw/stock_prices_daily/
data/stock_breadth/interim/
data/stock_breadth/processed/*.parquet
```
