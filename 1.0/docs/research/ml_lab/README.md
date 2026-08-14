# Phase MLX Research Lab

Phase MLX is an experimental hard-ML sandbox for the ETF quant portfolio project.

This area is research-only. It is not production, is not production-valid, and should not be used for live trading decisions or portfolio recommendations. Outputs from this lab are meant for experimentation, model-risk learning, and resume-worthy ML, AI, and data science infrastructure.

## Boundaries

- No production pins are changed by Phase MLX.
- No dashboard code is changed by Phase MLX.
- No existing production strategy logic is changed by Phase MLX.
- No existing candidates are replaced by Phase MLX.
- No Phase MLX result is promoted automatically.
- Missing optional files or packages should create warnings rather than crashes.

## Data Limits

Phase MLX may use `yfinance` as research data only. `yfinance` data can have survivorship issues, revisions, vendor inconsistencies, adjusted-price quirks, missing histories, and operational fragility. It is useful for exploratory research, not production validation.

The expanded ETF universe is also research-only. A broad curated universe can introduce selection bias, data-mining risk, and overfitting by making it easy to search across many assets, feature definitions, labels, and model classes until something looks good by chance.

## Risk Label

All Phase MLX artifacts should be treated as:

- Experimental
- Research-only
- High overfitting risk
- High selection-bias risk when using expanded ETFs
- Not live-trading guidance
- Not production-valid

The purpose is to build a clearly separated ML research lab where hard-ML ideas can be tested without contaminating the production portfolio workflow.
