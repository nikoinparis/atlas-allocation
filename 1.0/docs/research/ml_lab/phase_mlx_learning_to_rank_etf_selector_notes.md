# Phase MLX-14 Date-Grouped Learning-to-Rank ETF Selector Notes

## Research-Only Warning

Phase MLX-14 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading, production pins, dashboard changes, or candidate promotion.

## Educational Explanation

Learning-to-rank trains a model to order items rather than predict an exact number. In this ETF project, the natural question is often not "what exact return will SPY or TLT have?" but "which ETFs should be ranked above the others this week?" That makes ETF selection a cross-sectional ranking problem.

Ranking differs from regression because the model does not need a perfectly calibrated return forecast. It mainly needs the relative ordering to be useful. Ranking differs from classification because a top-quintile classifier treats each ETF row as a separate yes/no decision, while a date-grouped ranker sees all ETFs from the same date as one comparison group.

Date-grouped ranking means every weekly date is its own group. The model should compare SPY, TLT, GLD, QQQ, sectors, bonds, and BIL against each other at date `t`; it should not compare a 2008 ETF row against a 2024 ETF row as if they were in the same selection contest.

LambdaRank and LambdaMART are ranking methods that optimize ordering quality by emphasizing swaps near the top of the ranked list. LightGBM and XGBoost expose these ideas through LambdaRank / rank:NDCG objectives. NDCG, or normalized discounted cumulative gain, rewards putting high-relevance assets near the top. Rank IC is the Spearman correlation between model scores and future cross-sectional ranks.

Ranking can still overfit. The labels come from future returns, the ETF universe is selected, yfinance histories are research-only, and weekly financial data is noisy. A good validation rank IC or NDCG is not automatically a good portfolio.

## EECS 127 / Optimization Connection

The ranking loss is an objective function. Top-N ETF selection is a constrained decision: choose a small set of long-only positions from the weekly ETF universe. The loss should match the decision. MLX-12 and MLX-12B tried direct portfolio losses and showed that the wrong objective can create unstable or strategically wrong optima. MLX-14 uses a less direct but more stable objective: learn the ordering, then apply portfolio constraints and overlays after scoring.

## Technical Setup

- Universe size: 97
- Feature count: 73
- Ranking targets: ['forward_return_4w date-group relevance', 'forward_return_13w date-group relevance', 'top_quintile_forward_4w fallback', 'forward_return_4w regression fallback']
- Packages: {'lightgbm': {'available': True, 'version': '4.6.0'}, 'xgboost': {'available': True, 'version': '2.1.4'}, 'sklearn': {'available': True, 'version': '1.6.1'}}
- Models run: ['lightgbm_lambdarank_relevance_4w', 'lightgbm_lambdarank_relevance_13w', 'xgboost_rank_ndcg_relevance_4w', 'random_forest_classifier_top_quintile_4w', 'gradient_boosting_classifier_top_quintile_4w', 'ridge_regression_forward_return_4w', 'elasticnet_regression_forward_return_4w']
- Skipped variants: [{'variant': 'full_walk_forward_retraining', 'reason': 'deferred; selected predictions are evaluated by window without retraining per fold'}, {'variant': 'pairwise_neural_ranking_loss', 'reason': 'deferred; first version uses LightGBM/XGBoost rankers plus supervised fallbacks'}, {'variant': 'triple_barrier_per_etf_relevance', 'reason': 'MLX-13 labels are strategy/date-level labels, not ETF-level ranking labels'}]
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill; train-only standardization for linear fallback models
- Leakage controls: target-like feature columns are excluded; date groups are chronological; action at date `t` earns next-week returns
- Transaction cost: 10 bps per unit turnover

## Results

- Best validation-selected ranker: `elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first`
- Validation-selected holdout annual return: 2.04%
- Validation-selected holdout Sharpe: 0.183
- Validation-selected holdout max drawdown: -19.11%
- Validation-selected holdout CVaR 5%: -3.93%
- Validation-selected holdout rank IC: 0.051
- Validation-selected holdout NDCG@10: 0.373
- Validation-selected holdout top-quintile hit rate: 0.304
- Best holdout-diagnostic ranker: `random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve`

### Top Holdout Ranker Strategies

| strategy_name | model_family | target_name | allocation_method | wrapper | annual_return | sharpe | max_drawdown | cvar_5 | rank_ic | ndcg_10 | top_quintile_hit_rate | average_bil_exposure | average_safe_exposure | average_top3_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | random_forest_classifier | top_quintile_forward_4w | top10_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.76% | 1.082 | -12.42% | -2.75% | 0.036 | 0.440 | 0.371 | 2.17% | 2.21% | 3.12% |
| xgboost_rank_ndcg_relevance_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | xgboost_ranker | forward_return_4w_rank_relevance | top10_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.77% | 1.075 | -12.14% | -2.78% | 0.046 | 0.412 | 0.341 | 2.17% | 2.23% | 3.07% |
| random_forest_classifier_top_quintile_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | random_forest_classifier | top_quintile_forward_4w | top5_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.82% | 1.072 | -12.63% | -2.77% | 0.036 | 0.440 | 0.405 | 2.17% | 2.21% | 5.51% |
| random_forest_classifier_top_quintile_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | random_forest_classifier | top_quintile_forward_4w | top15_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.56% | 1.067 | -12.01% | -2.73% | 0.036 | 0.440 | 0.344 | 2.17% | 2.23% | 2.16% |
| random_forest_classifier_top_quintile_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | random_forest_classifier | top_quintile_forward_4w | top10_equal_weight | phase4b_core_plus_10pct_ranker_sleeve | 9.56% | 1.066 | -12.44% | -2.72% | 0.036 | 0.440 | 0.371 | 2.17% | 2.20% | 2.38% |
| xgboost_rank_ndcg_relevance_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | xgboost_ranker | forward_return_4w_rank_relevance | top10_equal_weight | phase4b_core_plus_10pct_ranker_sleeve | 9.69% | 1.066 | -12.13% | -2.78% | 0.046 | 0.412 | 0.341 | 2.17% | 2.19% | 2.38% |
| lightgbm_lambdarank_relevance_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | lightgbm_ranker | forward_return_4w_rank_relevance | top15_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.63% | 1.065 | -12.12% | -2.73% | 0.030 | 0.414 | 0.328 | 2.19% | 2.27% | 2.07% |
| lightgbm_lambdarank_relevance_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | lightgbm_ranker | forward_return_4w_rank_relevance | top15_equal_weight | phase4b_core_plus_10pct_ranker_sleeve | 9.59% | 1.063 | -12.12% | -2.71% | 0.030 | 0.414 | 0.328 | 2.17% | 2.21% | 1.60% |
| ridge_regression_forward_return_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | ridge_regression | forward_return_4w | top10_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.07% | 1.063 | -12.33% | -2.64% | 0.036 | 0.353 | 0.283 | 4.87% | 6.93% | 5.91% |
| lightgbm_lambdarank_relevance_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | lightgbm_ranker | forward_return_4w_rank_relevance | top10_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.67% | 1.062 | -12.24% | -2.75% | 0.030 | 0.414 | 0.338 | 2.19% | 2.21% | 2.99% |
| ridge_regression_forward_return_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | ridge_regression | forward_return_4w | top15_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.04% | 1.060 | -12.31% | -2.64% | 0.036 | 0.353 | 0.265 | 4.82% | 6.95% | 5.58% |
| gradient_boosting_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | gradient_boosting_classifier | top_quintile_forward_4w | top10_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.59% | 1.060 | -12.27% | -2.74% | 0.027 | 0.432 | 0.361 | 2.17% | 2.21% | 3.12% |
| random_forest_classifier_top_quintile_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | random_forest_classifier | top_quintile_forward_4w | top15_equal_weight | phase4b_core_plus_10pct_ranker_sleeve | 9.41% | 1.058 | -11.99% | -2.70% | 0.036 | 0.440 | 0.344 | 2.17% | 2.21% | 1.60% |
| xgboost_rank_ndcg_relevance_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | xgboost_ranker | forward_return_4w_rank_relevance | top15_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.54% | 1.056 | -12.13% | -2.77% | 0.046 | 0.412 | 0.324 | 2.17% | 2.23% | 2.13% |
| gradient_boosting_classifier_top_quintile_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | gradient_boosting_classifier | top_quintile_forward_4w | top5_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.66% | 1.054 | -12.41% | -2.77% | 0.027 | 0.432 | 0.377 | 2.17% | 2.19% | 5.51% |
| xgboost_rank_ndcg_relevance_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | xgboost_ranker | forward_return_4w_rank_relevance | top15_equal_weight | phase4b_core_plus_10pct_ranker_sleeve | 9.52% | 1.054 | -12.11% | -2.76% | 0.046 | 0.412 | 0.324 | 2.17% | 2.20% | 1.60% |
| lightgbm_lambdarank_relevance_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | lightgbm_ranker | forward_return_4w_rank_relevance | top10_equal_weight | phase4b_core_plus_10pct_ranker_sleeve | 9.56% | 1.053 | -12.22% | -2.73% | 0.030 | 0.414 | 0.338 | 2.17% | 2.19% | 2.38% |
| gradient_boosting_classifier_top_quintile_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | gradient_boosting_classifier | top_quintile_forward_4w | top15_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.44% | 1.050 | -12.24% | -2.73% | 0.027 | 0.432 | 0.340 | 2.17% | 2.24% | 2.14% |
| ridge_regression_forward_return_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | ridge_regression | forward_return_4w | top5_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.00% | 1.050 | -12.45% | -2.66% | 0.036 | 0.353 | 0.284 | 4.85% | 6.67% | 6.78% |
| lightgbm_lambdarank_relevance_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | lightgbm_ranker | forward_return_4w_rank_relevance | top5_inverse_vol | phase4b_core_plus_10pct_ranker_sleeve | 9.52% | 1.049 | -12.28% | -2.75% | 0.030 | 0.414 | 0.350 | 2.20% | 2.21% | 5.46% |

### Ranking Metrics

| model_name | model_family | target_name | split | rank_ic | spearman_rank_corr | ndcg_5 | ndcg_10 | top_quintile_hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_forest_classifier_top_quintile_4w | random_forest_classifier | top_quintile_forward_4w | holdout | 0.036 | 0.036 | 0.457 | 0.440 | 0.371 |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | top_quintile_forward_4w | holdout | 0.027 | 0.027 | 0.440 | 0.432 | 0.361 |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | forward_return_4w_rank_relevance | holdout | 0.030 | 0.030 | 0.422 | 0.414 | 0.338 |
| xgboost_rank_ndcg_relevance_4w | xgboost_ranker | forward_return_4w_rank_relevance | holdout | 0.046 | 0.046 | 0.413 | 0.412 | 0.341 |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | forward_return_13w_rank_relevance | holdout | 0.081 | 0.081 | 0.420 | 0.412 | 0.331 |
| elasticnet_regression_forward_return_4w | elasticnet_regression | forward_return_4w | holdout | 0.051 | 0.051 | 0.384 | 0.373 | 0.282 |
| ridge_regression_forward_return_4w | ridge_regression | forward_return_4w | holdout | 0.036 | 0.036 | 0.348 | 0.353 | 0.283 |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | forward_return_4w_rank_relevance | train | 0.163 | 0.163 | 0.643 | 0.594 | 0.464 |
| xgboost_rank_ndcg_relevance_4w | xgboost_ranker | forward_return_4w_rank_relevance | train | 0.139 | 0.139 | 0.607 | 0.563 | 0.440 |
| random_forest_classifier_top_quintile_4w | random_forest_classifier | top_quintile_forward_4w | train | 0.138 | 0.138 | 0.600 | 0.561 | 0.459 |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | top_quintile_forward_4w | train | 0.089 | 0.089 | 0.535 | 0.511 | 0.416 |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | forward_return_13w_rank_relevance | train | 0.149 | 0.149 | 0.528 | 0.506 | 0.383 |
| ridge_regression_forward_return_4w | ridge_regression | forward_return_4w | train | 0.083 | 0.083 | 0.421 | 0.409 | 0.305 |
| elasticnet_regression_forward_return_4w | elasticnet_regression | forward_return_4w | train | 0.087 | 0.087 | 0.416 | 0.408 | 0.301 |
| random_forest_classifier_top_quintile_4w | random_forest_classifier | top_quintile_forward_4w | validation | -0.027 | -0.027 | 0.404 | 0.398 | 0.344 |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | top_quintile_forward_4w | validation | -0.047 | -0.047 | 0.390 | 0.392 | 0.330 |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | forward_return_13w_rank_relevance | validation | -0.000 | -0.000 | 0.406 | 0.391 | 0.309 |
| xgboost_rank_ndcg_relevance_4w | xgboost_ranker | forward_return_4w_rank_relevance | validation | -0.015 | -0.015 | 0.381 | 0.378 | 0.312 |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | forward_return_4w_rank_relevance | validation | -0.056 | -0.056 | 0.399 | 0.376 | 0.296 |
| elasticnet_regression_forward_return_4w | elasticnet_regression | forward_return_4w | validation | 0.022 | 0.022 | 0.361 | 0.350 | 0.259 |
| ridge_regression_forward_return_4w | ridge_regression | forward_return_4w | validation | 0.002 | 0.002 | 0.323 | 0.323 | 0.235 |

### Strategy Comparison

| strategy_name | category | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | top_quintile_hit_rate | rank_ic | ndcg_10 | average_bil_exposure | average_safe_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx12_decision_focused | benchmark | 1.73% | 0.49% | 3.577 | -2.33% | -0.12% | n/a | n/a | n/a | 0.00% | 0.00% |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only | n/a | n/a | 1.276 | -14.56% | -4.17% | n/a | n/a | n/a | n/a | n/a |
| mlx13_holdout_diagnostic | benchmark | 10.28% | 8.82% | 1.165 | -12.44% | -2.56% | n/a | n/a | n/a | 0.00% | 0.00% |
| mlx3_tabular | benchmark | 9.55% | 8.81% | 1.084 | -11.77% | -2.66% | n/a | n/a | n/a | 0.00% | 0.00% |
| mlx4_mlp | benchmark | 9.55% | 8.81% | 1.084 | -11.77% | -2.66% | n/a | n/a | n/a | 0.00% | 0.00% |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.76% | 9.02% | 1.082 | -12.42% | -2.75% | 0.371 | 0.036 | 0.440 | 2.17% | 2.21% |
| xgboost_rank_ndcg_relevance_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.77% | 9.09% | 1.075 | -12.14% | -2.78% | 0.341 | 0.046 | 0.412 | 2.17% | 2.23% |
| random_forest_classifier_top_quintile_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.82% | 9.16% | 1.072 | -12.63% | -2.77% | 0.405 | 0.036 | 0.440 | 2.17% | 2.21% |
| phase4b | benchmark | 9.64% | 9.01% | 1.070 | -12.44% | -2.72% | n/a | n/a | n/a | 0.00% | 0.00% |
| random_forest_classifier_top_quintile_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.56% | 8.96% | 1.067 | -12.01% | -2.73% | 0.344 | 0.036 | 0.440 | 2.17% | 2.23% |
| random_forest_classifier_top_quintile_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.56% | 8.96% | 1.066 | -12.44% | -2.72% | 0.371 | 0.036 | 0.440 | 2.17% | 2.20% |
| xgboost_rank_ndcg_relevance_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.69% | 9.09% | 1.066 | -12.13% | -2.78% | 0.341 | 0.046 | 0.412 | 2.17% | 2.19% |
| lightgbm_lambdarank_relevance_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.63% | 9.04% | 1.065 | -12.12% | -2.73% | 0.328 | 0.030 | 0.414 | 2.19% | 2.27% |
| lightgbm_lambdarank_relevance_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.59% | 9.02% | 1.063 | -12.12% | -2.71% | 0.328 | 0.030 | 0.414 | 2.17% | 2.21% |
| ridge_regression_forward_return_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.07% | 8.54% | 1.063 | -12.33% | -2.64% | 0.283 | 0.036 | 0.353 | 4.87% | 6.93% |
| lightgbm_lambdarank_relevance_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.67% | 9.11% | 1.062 | -12.24% | -2.75% | 0.338 | 0.030 | 0.414 | 2.19% | 2.21% |
| ridge_regression_forward_return_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.04% | 8.52% | 1.060 | -12.31% | -2.64% | 0.265 | 0.036 | 0.353 | 4.82% | 6.95% |
| gradient_boosting_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.59% | 9.05% | 1.060 | -12.27% | -2.74% | 0.361 | 0.027 | 0.432 | 2.17% | 2.21% |
| random_forest_classifier_top_quintile_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.41% | 8.89% | 1.058 | -11.99% | -2.70% | 0.344 | 0.036 | 0.440 | 2.17% | 2.21% |
| xgboost_rank_ndcg_relevance_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.54% | 9.03% | 1.056 | -12.13% | -2.77% | 0.324 | 0.046 | 0.412 | 2.17% | 2.23% |
| gradient_boosting_classifier_top_quintile_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.66% | 9.16% | 1.054 | -12.41% | -2.77% | 0.377 | 0.027 | 0.432 | 2.17% | 2.19% |
| xgboost_rank_ndcg_relevance_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.52% | 9.04% | 1.054 | -12.11% | -2.76% | 0.324 | 0.046 | 0.412 | 2.17% | 2.20% |
| lightgbm_lambdarank_relevance_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.56% | 9.08% | 1.053 | -12.22% | -2.73% | 0.338 | 0.030 | 0.414 | 2.17% | 2.19% |
| gradient_boosting_classifier_top_quintile_4w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.44% | 8.99% | 1.050 | -12.24% | -2.73% | 0.340 | 0.027 | 0.432 | 2.17% | 2.24% |
| ridge_regression_forward_return_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.00% | 8.57% | 1.050 | -12.45% | -2.66% | 0.284 | 0.036 | 0.353 | 4.85% | 6.67% |
| lightgbm_lambdarank_relevance_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.52% | 9.07% | 1.049 | -12.28% | -2.75% | 0.350 | 0.030 | 0.414 | 2.20% | 2.21% |
| lightgbm_lambdarank_relevance_13w__top15_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.42% | 8.98% | 1.049 | -12.36% | -2.76% | 0.323 | 0.081 | 0.412 | 2.21% | 2.31% |
| lightgbm_lambdarank_relevance_4w__top5_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.48% | 9.06% | 1.046 | -12.29% | -2.75% | 0.350 | 0.030 | 0.414 | 2.17% | 2.18% |
| lightgbm_lambdarank_relevance_13w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.39% | 8.99% | 1.045 | -12.36% | -2.75% | 0.323 | 0.081 | 0.412 | 2.17% | 2.23% |
| ridge_regression_forward_return_4w__top15_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.34% | 8.95% | 1.044 | -12.27% | -2.74% | 0.265 | 0.036 | 0.353 | 2.49% | 2.94% |
| lightgbm_lambdarank_relevance_13w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.43% | 9.04% | 1.043 | -12.48% | -2.75% | 0.331 | 0.081 | 0.412 | 2.17% | 2.25% |
| gradient_boosting_classifier_top_quintile_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.40% | 9.01% | 1.043 | -12.30% | -2.74% | 0.361 | 0.027 | 0.432 | 2.17% | 2.20% |
| xgboost_rank_ndcg_relevance_4w__top5_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.50% | 9.12% | 1.041 | -12.41% | -2.78% | 0.352 | 0.046 | 0.412 | 2.17% | 2.22% |
| ridge_regression_forward_return_4w__top10_equal_weight__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.30% | 8.94% | 1.040 | -12.28% | -2.73% | 0.283 | 0.036 | 0.353 | 2.64% | 3.18% |
| lightgbm_lambdarank_relevance_13w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | learning_to_rank_model | 9.38% | 9.02% | 1.040 | -12.46% | -2.76% | 0.331 | 0.081 | 0.412 | 2.19% | 2.29% |

### State-By-State Results

| strategy_name | market_state | annual_return | sharpe | max_drawdown | cvar_5 | average_bil_exposure | average_ml_exposure | weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | calm_trend | -9.79% | -0.661 | -21.17% | -4.92% | 16.35% | 85.00% | 101 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | neutral_mixed | 15.24% | 1.549 | -8.78% | -2.62% | 50.41% | 50.00% | 121 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | recovery_confirmed | -8.72% | -0.531 | -9.32% | -4.64% | 18.24% | 85.00% | 21 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | recovery_fragile | 6.91% | 1.539 | -0.97% | -0.97% | 62.86% | 40.00% | 14 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | stressed_panic | 0.11% | 0.034 | -2.15% | -1.22% | 91.04% | 10.00% | 71 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | unknown | 23.26% | 4.939 | -0.35% | -0.35% | 70.00% | 50.00% | 4 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | calm_trend | 3.54% | 0.440 | -7.94% | -2.47% | 0.00% | 10.00% | 101 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | neutral_mixed | 23.97% | 2.485 | -4.84% | -2.37% | 0.00% | 10.00% | 121 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | recovery_confirmed | 0.64% | 0.070 | -3.58% | -2.28% | 0.00% | 10.00% | 21 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | recovery_fragile | 9.86% | 1.575 | -2.99% | -1.38% | 0.00% | 10.00% | 14 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | stressed_panic | -0.50% | -0.053 | -5.35% | -3.38% | 10.00% | 0.00% | 71 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | unknown | 7.94% | 11.271 | -0.02% | -0.02% | 2.50% | 10.00% | 4 |

### Walk-Forward Window Results

| strategy_name | window | annual_return | sharpe | max_drawdown | cvar_5 | top_quintile_hit_rate | active_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | 2017_2018 | 4.95% | 0.723 | -7.90% | -1.90% | 0.277 | 104 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | 2019_2020 | 4.03% | 0.317 | -19.11% | -4.74% | 0.252 | 104 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | 2021_2022 | -2.80% | -0.292 | -13.09% | -3.14% | 0.253 | 105 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | 2023_2026 | 7.90% | 0.758 | -10.24% | -3.31% | 0.370 | 175 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | 2017_2018 | 5.47% | 0.870 | -9.34% | -2.12% | 0.401 | 104 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | 2019_2020 | 9.12% | 0.909 | -12.42% | -3.55% | 0.369 | 104 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | 2021_2022 | 4.75% | 0.632 | -5.94% | -2.28% | 0.382 | 105 |
| random_forest_classifier_top_quintile_4w__top10_inverse_vol__phase4b_core_plus_10pct_ranker_sleeve | 2023_2026 | 14.15% | 1.729 | -6.79% | -2.06% | 0.368 | 175 |

### Feature Importance

| model_name | model_family | feature | importance | importance_type |
| --- | --- | --- | --- | --- |
| elasticnet_regression_forward_return_4w | elasticnet_regression | z_breadth_decay | 0.014648284763097763 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | pct_above_200d_ma | 0.013225268572568893 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | transition_non_stress_prob | 0.01209036074578762 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | market_state_stressed_panic | 0.011247256770730019 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | market_drawdown | 0.011027233675122261 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | confidence_score_p2b | 0.010558434762060642 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | breadth_sma_43 | 0.010343896225094795 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | market_vol_risk_off_z | 0.008825499564409256 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | market_state_neutral_mixed | 0.008291936479508877 | coefficient_abs |
| elasticnet_regression_forward_return_4w | elasticnet_regression | market_trend_positive | 0.007419471628963947 | coefficient_abs |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | cross_sectional_vol_rank_13w | 0.33870436102877705 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | corr_to_SPY_26w | 0.1972441596664791 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | realized_vol_13w | 0.036172574952895775 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | cross_sectional_return_rank_26w | 0.0342549124581461 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | realized_vol_26w | 0.027824967713404473 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | beta_to_SPY_26w | 0.0276045839259179 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | z_dd_neg | 0.023652321091165225 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | transition_good_state_prob | 0.022407499455527325 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | google_fear_z_tradable | 0.02235338061569062 | feature_importance |
| gradient_boosting_classifier_top_quintile_4w | gradient_boosting_classifier | risk_regime_score | 0.01772213349383177 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | beta_to_SPY_26w | 53.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | trailing_return_52w | 32.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | corr_to_SPY_26w | 31.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | stock_count_available | 22.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | z_stress | 17.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | market_drawdown_risk_off_z | 17.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | google_fear_z_tradable | 15.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | realized_vol_26w | 14.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | cross_sectional_vol_rank_13w | 14.0 | feature_importance |
| lightgbm_lambdarank_relevance_13w | lightgbm_ranker | deterioration_z | 14.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | cross_sectional_vol_rank_13w | 50.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | beta_to_SPY_26w | 48.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | corr_to_SPY_26w | 45.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | google_fear_z_tradable | 44.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | cross_sectional_return_rank_26w | 27.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | target_vol_multiplier | 27.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | deterioration_z | 26.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | z_stress | 24.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | market_vol_risk_off_z | 22.0 | feature_importance |
| lightgbm_lambdarank_relevance_4w | lightgbm_ranker | market_drawdown_risk_off_z | 22.0 | feature_importance |

### Exposure Audit

| strategy_name | audit_type | item | category | average_weight | max_weight | holding_frequency |
| --- | --- | --- | --- | --- | --- | --- |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | Bonds | Bonds | 0.489066265060241 | 1.0 | 1.0 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | US sectors | US sectors | 0.18364457831325304 | 0.68 | 0.8493975903614458 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | International equity | International equity | 0.09725903614457831 | 0.68 | 0.5 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | Factors/styles | Factors/styles | 0.09159638554216867 | 0.51 | 0.4939759036144578 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | US broad equity | US broad equity | 0.07551204819277109 | 0.68 | 0.39457831325301207 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | Real estate | Real estate | 0.03575301204819278 | 0.68 | 0.1144578313253012 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | Commodities | Commodities | 0.026144578313253012 | 0.24000000000000005 | 0.20783132530120482 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | Credit | Credit | 0.0009036144578313254 | 0.2 | 0.009036144578313253 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | category | Currency/dollar | Currency/dollar | 0.0001204819277108434 | 0.020000000000000004 | 0.006024096385542169 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_top3_weight |  | 0.6962048192771084 | 1.0 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_safe_asset_weight |  | 0.4893674698795182 | 1.0 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_BIL_weight |  | 0.4746385542168675 | 1.0 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_sector_weight |  | 0.18364457831325304 | 0.68 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_international_weight |  | 0.09725903614457831 | 0.68 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_SPY_QQQ_SMH_weight |  | 0.0705120481927711 | 0.34 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | summary | average_commodities_weight |  | 0.026144578313253012 | 0.24000000000000005 | n/a |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | BIL | Bonds | 0.4746385542168675 | 1.0 | 1.0 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | SMH | US sectors | 0.045331325301204824 | 0.17 | 0.39457831325301207 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XLK | US sectors | 0.043132530120481925 | 0.17 | 0.35542168674698793 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | VUG | Factors/styles | 0.026716867469879522 | 0.17 | 0.23493975903614459 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | QQQ | US broad equity | 0.025180722891566264 | 0.17 | 0.20481927710843373 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XLY | US sectors | 0.024789156626506024 | 0.17 | 0.2289156626506024 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | MTUM | Factors/styles | 0.02310240963855422 | 0.17 | 0.19879518072289157 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | IWM | US broad equity | 0.02003012048192771 | 0.17 | 0.1566265060240964 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | IWF | Factors/styles | 0.01825301204819277 | 0.17 | 0.1686746987951807 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | KRE | US sectors | 0.018102409638554216 | 0.17 | 0.16566265060240964 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | EWY | International equity | 0.017740963855421687 | 0.17 | 0.13253012048192772 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | IVW | Factors/styles | 0.014638554216867472 | 0.17 | 0.14156626506024098 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XBI | US sectors | 0.01427710843373494 | 0.17 | 0.1355421686746988 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | EWZ | International equity | 0.013855421686746987 | 0.17 | 0.10542168674698796 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | USO | Commodities | 0.012861445783132532 | 0.17 | 0.10240963855421686 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | EWW | International equity | 0.012138554216867471 | 0.17 | 0.10240963855421686 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | SCHH | Real estate | 0.012138554216867471 | 0.17 | 0.09036144578313253 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | IJH | US broad equity | 0.011204819277108435 | 0.17 | 0.08132530120481928 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | EWT | International equity | 0.011174698795180724 | 0.17 | 0.10240963855421686 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | FXI | International equity | 0.009518072289156626 | 0.17 | 0.08734939759036145 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | REET | Real estate | 0.008704819277108434 | 0.17 | 0.06626506024096386 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | UNG | Commodities | 0.008493975903614458 | 0.17 | 0.06626506024096386 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | MDY | US broad equity | 0.008463855421686747 | 0.17 | 0.060240963855421686 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | IJR | US broad equity | 0.008433734939759036 | 0.17 | 0.06626506024096386 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XLB | US sectors | 0.00816265060240964 | 0.17 | 0.08132530120481928 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | SHV | Bonds | 0.007198795180722893 | 0.17 | 0.14457831325301204 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | VNQ | Real estate | 0.0071987951807228915 | 0.17 | 0.05120481927710843 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | IYR | Real estate | 0.0071987951807228915 | 0.17 | 0.05120481927710843 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XLRE | US sectors | 0.0071987951807228915 | 0.17 | 0.04819277108433735 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | EWG | International equity | 0.00641566265060241 | 0.17 | 0.0572289156626506 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XLF | US sectors | 0.0056626506024096395 | 0.17 | 0.060240963855421686 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | VLUE | Factors/styles | 0.005632530120481928 | 0.17 | 0.05120481927710843 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | XLE | US sectors | 0.005512048192771085 | 0.17 | 0.04819277108433735 |
| elasticnet_regression_forward_return_4w__top5_equal_weight__defensive_first | ticker | INDA | International equity | 0.004939759036144579 | 0.17 | 0.03313253012048193 |

## Interpretation

The key question is whether explicit date-grouped ranking helped more than prediction-trained ML and direct decision-focused losses. The validation-selected result is the main answer; holdout-only best rows are diagnostic and should not be treated as selected strategies.

Ranking is more aligned with ETF selection than ordinary regression/classification because the portfolio only needs a useful ordering. But it still has the same core finance ML risks: weak stationarity, regime dependence, transaction costs, and high data-mining risk.

Final recommendation: **KEEP AS RESEARCH ONLY**.

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- Learning-to-rank uses yfinance/expanded ETF research data and remains high overfitting risk.
- MLX-13 triple-barrier labels are strategy/date-level, not per-ETF relevance labels; they were not used as direct ETF ranking labels in MLX-14.
- No learning-to-rank model is promoted automatically.
