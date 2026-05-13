# Phase MLX Overfitting Warning

Phase MLX is an experimental, research-only hard-ML lab. It is not production and is not production-valid.

Expanded ETF testing creates a large search space. That raises the risk of:

- Selection bias from choosing ETFs after seeing historical behavior.
- Data-mining from trying many features, labels, horizons, filters, and model classes.
- Overfitting from tuning models to historical quirks that may not repeat.
- Multiple-testing error from comparing many candidate signals and allocators.
- False confidence from clean-looking backtests built on noisy financial data.
- Survivorship, adjustment, and vendor-quality issues from `yfinance` research data.

Any result from this lab must be treated as a hypothesis generator only. It should not influence live trading, production allocation, dashboard reporting, or candidate promotion without separate walk-forward validation, robustness checks, implementation-realism review, and explicit human approval.

Phase MLX exists to support experimentation and ML infrastructure learning while keeping production strategy logic isolated.
