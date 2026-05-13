# Phase MLX Feature Panel Notes

Phase MLX-2 builds a date × ETF machine-learning feature panel for the experimental hard-ML research lab.

## Data Source

Required inputs come from the Phase MLX-1 expanded ETF universe:

- `data/research/ml_lab/expanded_universe/expanded_etf_prices_weekly.csv`
- `data/research/ml_lab/expanded_universe/expanded_etf_returns_weekly.csv`

These inputs are based on `yfinance` research data. They are not production-valid and should not be used for live trading decisions.

## Feature Definitions

The panel is one row per ETF per weekly Friday date. ETF-level features use information available at or before date `t`, including trailing returns, 12-1 momentum, realized volatility, rolling Sharpe, trailing max drawdown, drawdown from 52-week high, relative strength versus `SPY` and `BIL`, rolling beta/correlation to `SPY`, and cross-sectional ranks computed only from same-date trailing features.

Optional regime features are merged by date when project state files are available. Market-state values are converted to one-hot variables, and numeric risk/regime/probability/score fields are included without global standardization.

Optional stock breadth prototype features are merged by date when `data/research/stock_breadth/stock_breadth_weekly.csv` exists. These features are current-S&P/yfinance prototype features and are survivorship-biased, research-only, and not production-valid.

## Target Definitions

Targets are saved separately from features:

- `forward_return_4w`
- `forward_return_13w`
- `forward_rank_4w`
- `forward_rank_13w`
- `beats_SPY_4w`
- `beats_BIL_4w`
- `positive_forward_4w`
- `top_quintile_forward_4w`

Forward returns and forward ranks are labels only. They are not joined into the feature parquet.

## Leakage Prevention

- Feature columns use trailing or same-date information only.
- Forward returns are kept only in `ml_targets.parquet`.
- The script does not globally standardize, normalize, or fit scalers.
- Cross-sectional feature ranks use same-date trailing values, not future returns.
- Future ranks are target columns only.

## Missing File Warnings

Project regime/state files and stock breadth prototype files are optional. Missing or unparseable optional files should produce warnings and metadata entries, not crashes.

## Research-Only Status

This panel is experimental and high-overfitting-risk. The expanded ETF universe can introduce selection bias and data-mining risk. No output from this lab is production-valid, no dashboard code is changed, and no strategy candidate should be promoted from this work without separate validation and human review.

## Next Step

MLX-3 will train initial tabular ML models on this feature/target split with explicit walk-forward validation and leakage checks.
