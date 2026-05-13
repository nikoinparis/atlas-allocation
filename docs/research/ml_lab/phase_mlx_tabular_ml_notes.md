# Phase MLX Tabular ML Notes

Phase MLX-3 is experimental, research-only, not production-valid, and high overfitting risk. No model in this folder is promoted automatically or suitable for live trading decisions.

## Data Source Warning

Inputs are `data/research/ml_lab/feature_panel/ml_feature_panel.parquet` and `data/research/ml_lab/feature_panel/ml_targets.parquet`, derived from the Phase MLX expanded ETF universe. The upstream ETF data is `yfinance` research data and the expanded universe introduces selection-bias and data-mining risk. Stock breadth prototype features, when present, are survivorship-biased research diagnostics.

## Split Definitions

- Train: dates through 2017-12-31
- Validation: 2018-01-01 through 2019-12-31
- Holdout: 2020-01-01 onward

Preprocessing medians, means, and standard deviations are fit on the train split only.

## Models Run

- ridge_regression__forward_return_4w
- elasticnet_regression__forward_return_4w
- random_forest_regressor__forward_return_4w
- gradient_boosting_regressor__forward_return_4w
- logistic_regression__top_quintile_forward_4w
- logistic_regression__beats_SPY_4w
- logistic_regression__positive_forward_4w
- random_forest_classifier__top_quintile_forward_4w
- random_forest_classifier__beats_SPY_4w
- random_forest_classifier__positive_forward_4w
- gradient_boosting_classifier__top_quintile_forward_4w
- gradient_boosting_classifier__beats_SPY_4w
- gradient_boosting_classifier__positive_forward_4w
- xgboost_regressor__forward_return_4w
- xgboost_classifier__top_quintile_forward_4w
- xgboost_classifier__beats_SPY_4w
- xgboost_classifier__positive_forward_4w
- lightgbm_regressor__forward_return_4w
- lightgbm_classifier__top_quintile_forward_4w
- lightgbm_classifier__beats_SPY_4w
- lightgbm_classifier__positive_forward_4w

## Models Skipped

- None

## Target Definitions

- Regression: `forward_return_4w`
- Classification: `top_quintile_forward_4w`, `beats_SPY_4w`, and auxiliary `positive_forward_4w`

Forward labels remain in the target parquet only and are not model features.

## Backtest Assumptions

Model scores are converted into weekly ETF rankings. Each week tests top 3, top 5, and top 10 equal-weight and inverse-volatility portfolios. Realized next-week returns are derived from `trailing_return_1w` shifted one week forward by ticker. Transaction costs use the project-style 10 bps per unit turnover assumption. This remains an approximate research simulation, not a production allocator.

## Baseline Comparison

Baselines include SPY buy-and-hold, 60/40 SPY/IEF or SPY/AGG, equal-weight all available ETFs, top momentum ETFs using `momentum_12_1`, inverse-vol top momentum, and available project production/shadow/candidate return files.

## Best Models

- Best train model by Sharpe: lightgbm_regressor__forward_return_4w__top3__equal_weight (Sharpe 1.896, annual return 44.346%)
- Best validation model by Sharpe: logistic_regression__positive_forward_4w__top3__inverse_vol (Sharpe 8.031, annual return 1.673%)
- Best holdout model by Sharpe: random_forest_classifier__top_quintile_forward_4w__top10__inverse_vol (Sharpe 0.811, annual return 16.849%)
- Best holdout model by annual return: random_forest_classifier__top_quintile_forward_4w__top3__inverse_vol (Sharpe 0.698, annual return 19.997%)

## Holdout Read

- Any model beats simple momentum on holdout by Sharpe: False
- Any model beats SPY on holdout by Sharpe: True
- Any model beats 60/40 on holdout by Sharpe: True
- Any model beats production on holdout by Sharpe: False
- Any model beats official shadow on holdout by Sharpe: False

## Warnings

- None

## Interpretation

Treat any validation or holdout win as a hypothesis, not evidence of deployability. The search space includes many ETFs, targets, model classes, feature transforms, and portfolio construction choices, so overfitting and multiple-testing risk are high. MLX-3 is useful as ML/AI/data-science infrastructure and as a disciplined research benchmark, not as a production strategy.
