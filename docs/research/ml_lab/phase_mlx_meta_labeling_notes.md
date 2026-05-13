# Phase MLX Meta-Labeling Notes

## Research-Only Warning

Phase MLX-7 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data where applicable, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Meta-labeling is a second-stage model. Instead of directly predicting which ETF will have the best return, it asks whether an already-defined strategy or sleeve should be trusted in the next period. For example, it can ask whether production is likely to beat BIL, whether Phase 4B is likely to beat production, or whether the MLX-5 sequence sleeve deserves activation.

This is different from direct return prediction because the model filters a decision that already exists. It might help this project by connecting the ML lab to the core ETF strategy: ML becomes a risk filter or offensive-sleeve activation signal rather than a replacement portfolio. It can overfit because the labels are noisy, the number of weekly examples is small, and a filter can accidentally learn one market era rather than durable behavior.

## Technical Setup

Meta-label tasks created:

- `task_a_core_production_risk_filter`: production next 4-week return is positive or beats BIL. Purpose: identify when production should be trusted or risk-reduced.
- `task_b_production_beats_bil`: production beats BIL over next 4 weeks. Purpose: reduce exposure when production expected excess return is poor.
- `task_c_phase4b_beats_production`: Phase 4B beats production over next 4 weeks. Purpose: identify when more aggressive Phase 4B-like offense should be preferred.
- `task_d_mlx5_sleeve_activation`: MLX-5 sequence sleeve beats production or BIL over next 4 weeks. Purpose: decide when to activate ML offensive sleeve.
- `task_e_bad_week_avoidance`: next 4-week production loss or weekly shock exceeds threshold. Purpose: predict when to reduce ML or offensive exposure.

Features used:
- date-level averages of safe numeric MLX-2 features
- market state and risk/regime features from the feature panel
- stock breadth prototype features, marked research-only and survivorship-biased in MLX-2 metadata
- aggregate MLX sequence/Transformer confidence features where prediction files were available
- recent production and ML sleeve return, drawdown, volatility, and turnover features

Models run: Logistic Regression, Random Forest, Gradient Boosting, and optional XGBoost/LightGBM when importable. Splits are chronological: train through 2017-12-31, validation 2018-01-01 through 2019-12-31, holdout 2020-01-01 onward.

Leakage controls: all meta features are known at date `t`; future 4-week strategy outcomes are used only as labels; forward target-like columns are excluded from input features; train-only medians and standardization are used for model fitting.

Skipped tasks:

- None

Skipped models:

- small_torch_mlp: optional MLP skipped to keep MLX-7 bounded and interpretable 

## Classification Results

| task_id | model_name | rows | positive_rate_actual | positive_prediction_rate | accuracy | precision | recall | f1 | roc_auc | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| task_e_bad_week_avoidance | xgboost | 332 | 4.52% | 0.00% | 95.48% | 0.00% | 0.00% | 0.00% | 74.93% | 0.043 |
| task_e_bad_week_avoidance | lightgbm | 332 | 4.52% | 0.30% | 95.18% | 0.00% | 0.00% | 0.00% | 73.55% | 0.045 |
| task_e_bad_week_avoidance | logistic_regression | 332 | 4.52% | 13.55% | 86.75% | 17.78% | 53.33% | 26.67% | 73.33% | 0.116 |
| task_e_bad_week_avoidance | random_forest | 332 | 4.52% | 2.11% | 93.37% | 0.00% | 0.00% | 0.00% | 70.24% | 0.076 |
| task_a_core_production_risk_filter | logistic_regression | 332 | 66.27% | 53.61% | 61.45% | 75.84% | 61.36% | 67.84% | 65.54% | 0.295 |
| task_b_production_beats_bil | logistic_regression | 332 | 62.65% | 67.17% | 67.17% | 72.20% | 77.40% | 74.71% | 62.99% | 0.273 |
| task_e_bad_week_avoidance | gradient_boosting | 332 | 4.52% | 1.20% | 94.28% | 0.00% | 0.00% | 0.00% | 62.41% | 0.055 |
| task_a_core_production_risk_filter | random_forest | 332 | 66.27% | 100.00% | 66.27% | 66.27% | 100.00% | 79.71% | 60.15% | 0.218 |
| task_c_phase4b_beats_production | random_forest | 332 | 55.42% | 95.18% | 54.22% | 55.06% | 94.57% | 69.60% | 59.20% | 0.246 |
| task_b_production_beats_bil | random_forest | 332 | 62.65% | 98.80% | 63.86% | 63.41% | 100.00% | 77.61% | 57.45% | 0.232 |
| task_a_core_production_risk_filter | gradient_boosting | 332 | 66.27% | 87.05% | 65.36% | 68.17% | 89.55% | 77.41% | 56.75% | 0.225 |
| task_b_production_beats_bil | gradient_boosting | 332 | 62.65% | 80.12% | 63.25% | 66.17% | 84.62% | 74.26% | 56.64% | 0.235 |
| task_a_core_production_risk_filter | xgboost | 332 | 66.27% | 88.25% | 65.96% | 68.26% | 90.91% | 77.97% | 55.82% | 0.225 |
| task_c_phase4b_beats_production | xgboost | 332 | 55.42% | 40.66% | 52.71% | 60.00% | 44.02% | 50.78% | 55.71% | 0.258 |
| task_c_phase4b_beats_production | lightgbm | 332 | 55.42% | 34.94% | 52.41% | 61.21% | 38.59% | 47.33% | 55.57% | 0.259 |
| task_c_phase4b_beats_production | gradient_boosting | 332 | 55.42% | 38.25% | 53.92% | 62.20% | 42.93% | 50.80% | 55.46% | 0.266 |
| task_c_phase4b_beats_production | logistic_regression | 332 | 55.42% | 68.98% | 55.72% | 58.08% | 72.28% | 64.41% | 53.10% | 0.326 |
| task_b_production_beats_bil | lightgbm | 332 | 62.65% | 90.96% | 63.25% | 64.24% | 93.27% | 76.08% | 53.09% | 0.238 |
| task_b_production_beats_bil | xgboost | 332 | 62.65% | 79.22% | 60.54% | 64.64% | 81.73% | 72.19% | 52.78% | 0.239 |
| task_a_core_production_risk_filter | lightgbm | 332 | 66.27% | 95.48% | 65.36% | 66.56% | 95.91% | 78.58% | 52.70% | 0.228 |
| task_d_mlx5_sleeve_activation | xgboost | 332 | 72.89% | 86.14% | 66.87% | 73.08% | 86.36% | 79.17% | 49.86% | 0.219 |
| task_d_mlx5_sleeve_activation | lightgbm | 332 | 72.89% | 86.14% | 66.87% | 73.08% | 86.36% | 79.17% | 49.81% | 0.219 |
| task_d_mlx5_sleeve_activation | logistic_regression | 332 | 72.89% | 74.70% | 60.84% | 72.58% | 74.38% | 73.47% | 48.03% | 0.313 |
| task_d_mlx5_sleeve_activation | gradient_boosting | 332 | 72.89% | 81.63% | 64.16% | 72.69% | 81.40% | 76.80% | 47.94% | 0.231 |
| task_d_mlx5_sleeve_activation | random_forest | 332 | 72.89% | 98.80% | 74.10% | 73.78% | 100.00% | 84.91% | 47.49% | 0.209 |

## Strategy Results

| strategy_name | strategy_family | task_id | model_name | threshold | sleeve_size | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_weight | average_ml_sleeve_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only |  |  | n/a | n/a | n/a | n/a | 1.276 | -14.56% | n/a | -4.17% | n/a | n/a | n/a | n/a |
| phase4b | benchmark |  |  | n/a | n/a | 9.64% | 9.01% | 1.070 | -12.44% | 0.775 | -2.72% | n/a | 0.00% | 0.00% | 0.00% |
| phase7 | benchmark |  |  | n/a | n/a | 9.57% | 9.47% | 1.011 | -13.83% | 0.692 | -2.92% | n/a | 0.00% | 0.00% | 0.00% |
| phase6 | benchmark |  |  | n/a | n/a | 9.57% | 9.47% | 1.010 | -13.77% | 0.695 | -2.92% | n/a | 0.00% | 0.00% | 0.00% |
| mlx6_transformer | benchmark |  |  | n/a | n/a | 11.16% | 11.30% | 0.987 | -13.13% | 0.850 | -3.29% | n/a | 0.00% | 0.00% | 100.00% |
| task_c_phase4b_beats_production__random_forest__thr0.50__phase4b_switch | phase4b_switch | task_c_phase4b_beats_production | random_forest | 0.5 | n/a | 8.64% | 8.94% | 0.966 | -13.88% | 0.622 | -2.74% | 0.07228915662650602 | 0.38% | 0.00% | 0.00% |
| task_e_bad_week_avoidance__xgboost__thr0.50__mlx5_or_bil | bad_week_avoid_mlx5 | task_e_bad_week_avoidance | xgboost | 0.5 | n/a | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 0.0 | 0.00% | 0.00% | 100.00% |
| task_e_bad_week_avoidance__xgboost__thr0.60__mlx5_or_bil | bad_week_avoid_mlx5 | task_e_bad_week_avoidance | xgboost | 0.6 | n/a | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 0.0 | 0.00% | 0.00% | 100.00% |
| task_e_bad_week_avoidance__xgboost__thr0.70__mlx5_or_bil | bad_week_avoid_mlx5 | task_e_bad_week_avoidance | xgboost | 0.7 | n/a | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 0.0 | 0.00% | 0.00% | 100.00% |
| mlx5_sequence | benchmark |  |  | n/a | n/a | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | n/a | 0.00% | 0.00% | 100.00% |
| official_shadow | benchmark |  |  | n/a | n/a | 8.04% | 8.53% | 0.943 | -13.67% | 0.588 | -2.71% | n/a | 0.00% | 0.00% | 0.00% |
| production | benchmark |  |  | n/a | n/a | 8.07% | 8.60% | 0.938 | -13.98% | 0.577 | -2.73% | n/a | 0.00% | 0.00% | 0.00% |
| task_e_bad_week_avoidance__xgboost__thr0.50__production_or_bil | bad_week_avoid_production | task_e_bad_week_avoidance | xgboost | 0.5 | n/a | 7.97% | 8.55% | 0.931 | -13.98% | 0.570 | -2.73% | 0.0 | 0.00% | 0.00% | 0.00% |
| task_e_bad_week_avoidance__xgboost__thr0.60__production_or_bil | bad_week_avoid_production | task_e_bad_week_avoidance | xgboost | 0.6 | n/a | 7.97% | 8.55% | 0.931 | -13.98% | 0.570 | -2.73% | 0.0 | 0.00% | 0.00% | 0.00% |
| task_e_bad_week_avoidance__xgboost__thr0.70__production_or_bil | bad_week_avoid_production | task_e_bad_week_avoidance | xgboost | 0.7 | n/a | 7.97% | 8.55% | 0.931 | -13.98% | 0.570 | -2.73% | 0.0 | 0.00% | 0.00% | 0.00% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.50__sleeve10% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.5 | 0.1 | 7.72% | 8.62% | 0.896 | -13.76% | 0.561 | -2.77% | 0.027710843373493974 | 0.14% | 0.00% | 8.61% |
| task_c_phase4b_beats_production__random_forest__thr0.70__phase4b_switch | phase4b_switch | task_c_phase4b_beats_production | random_forest | 0.7 | n/a | 7.44% | 8.43% | 0.882 | -13.38% | 0.556 | -2.66% | 0.16265060240963855 | 0.85% | 0.00% | 0.00% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.70__sleeve10% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.7 | 0.1 | 7.53% | 8.62% | 0.873 | -14.17% | 0.531 | -2.76% | 0.04216867469879518 | 0.22% | 0.00% | 2.95% |
| simple_momentum | benchmark |  |  | n/a | n/a | 22.21% | 25.57% | 0.869 | -43.50% | 0.511 | -7.83% | n/a | 0.00% | 0.00% | 0.00% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.50__sleeve20% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.5 | 0.2 | 7.47% | 8.76% | 0.853 | -13.54% | 0.552 | -2.82% | 0.05542168674698795 | 0.29% | 0.00% | 17.23% |
| task_c_phase4b_beats_production__random_forest__thr0.60__phase4b_switch | phase4b_switch | task_c_phase4b_beats_production | random_forest | 0.6 | n/a | 7.35% | 8.63% | 0.852 | -12.90% | 0.570 | -2.69% | 0.25903614457831325 | 1.35% | 0.00% | 0.00% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.60__sleeve10% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.6 | 0.1 | 7.26% | 8.60% | 0.845 | -13.76% | 0.528 | -2.77% | 0.03975903614457831 | 0.21% | 0.00% | 6.54% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.70__sleeve20% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.7 | 0.2 | 7.08% | 8.70% | 0.814 | -14.37% | 0.493 | -2.78% | 0.08433734939759036 | 0.44% | 0.00% | 5.90% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.50__sleeve30% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.5 | 0.3 | 7.22% | 8.95% | 0.806 | -13.32% | 0.542 | -2.88% | 0.08313253012048194 | 0.43% | 0.00% | 25.84% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.70__sleeve30% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.7 | 0.3 | 6.64% | 8.81% | 0.754 | -14.56% | 0.456 | -2.82% | 0.12650602409638556 | 0.66% | 0.00% | 8.86% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.60__sleeve20% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.6 | 0.2 | 6.56% | 8.70% | 0.754 | -13.54% | 0.484 | -2.82% | 0.07951807228915662 | 0.41% | 0.00% | 13.07% |
| SPY | benchmark |  |  | n/a | n/a | 13.24% | 19.37% | 0.683 | -33.63% | 0.394 | -6.31% | n/a | 0.00% | 0.00% | 0.00% |
| sixty_forty | benchmark |  |  | n/a | n/a | 8.19% | 12.05% | 0.680 | -21.88% | 0.375 | -3.85% | n/a | 0.00% | 0.00% | 0.00% |
| task_d_mlx5_sleeve_activation__xgboost__thr0.60__sleeve30% | mlx5_sleeve_activation | task_d_mlx5_sleeve_activation | xgboost | 0.6 | 0.3 | 5.85% | 8.85% | 0.661 | -13.32% | 0.439 | -2.88% | 0.11927710843373497 | 0.62% | 0.00% | 19.61% |
| task_a_core_production_risk_filter__gradient_boosting__thr0.50__production_or_bil | production_bil_filter | task_a_core_production_risk_filter | gradient_boosting | 0.5 | n/a | 4.59% | 8.26% | 0.555 | -13.98% | 0.328 | -2.70% | 0.2469879518072289 | 1.28% | 12.95% | 0.00% |

## Feature Importance

| task_id | model_name | feature | importance | importance_type |
| --- | --- | --- | --- | --- |
| task_b_production_beats_bil | lightgbm | feature_avg_cross_sectional_vol_rank_13w | 67.0 | feature_importance |
| task_d_mlx5_sleeve_activation | lightgbm | feature_avg_cross_sectional_vol_rank_13w | 59.0 | feature_importance |
| task_c_phase4b_beats_production | lightgbm | feature_avg_cross_sectional_vol_rank_13w | 38.0 | feature_importance |
| task_a_core_production_risk_filter | lightgbm | feature_avg_cross_sectional_vol_rank_13w | 38.0 | feature_importance |
| task_e_bad_week_avoidance | lightgbm | feature_avg_market_vol_risk_off_z | 31.0 | feature_importance |
| task_a_core_production_risk_filter | lightgbm | feature_avg_cross_sectional_return_rank_13w | 29.0 | feature_importance |
| task_b_production_beats_bil | lightgbm | production_drawdown_13w_trailing | 24.0 | feature_importance |
| task_c_phase4b_beats_production | lightgbm | feature_avg_cross_sectional_return_rank_13w | 24.0 | feature_importance |
| task_d_mlx5_sleeve_activation | lightgbm | feature_avg_drawdown_from_52w_high | 24.0 | feature_importance |
| task_e_bad_week_avoidance | lightgbm | production_vol_13w_trailing | 22.0 | feature_importance |
| task_e_bad_week_avoidance | lightgbm | feature_avg_google_fear_z_tradable | 20.0 | feature_importance |
| task_c_phase4b_beats_production | lightgbm | feature_avg_beta_to_SPY_26w | 19.0 | feature_importance |
| task_d_mlx5_sleeve_activation | lightgbm | seq_score_std | 17.0 | feature_importance |
| task_d_mlx5_sleeve_activation | lightgbm | mlx5_sequence_return_13w_trailing | 16.0 | feature_importance |
| task_d_mlx5_sleeve_activation | lightgbm | mlx5_sequence_drawdown_13w_trailing | 16.0 | feature_importance |
| task_c_phase4b_beats_production | lightgbm | feature_avg_google_fear_z_tradable | 16.0 | feature_importance |
| task_a_core_production_risk_filter | lightgbm | mlx5_sequence_vol_13w_trailing | 16.0 | feature_importance |
| task_a_core_production_risk_filter | lightgbm | feature_avg_cross_sectional_return_rank_26w | 15.0 | feature_importance |
| task_e_bad_week_avoidance | lightgbm | seq_score_median | 15.0 | feature_importance |
| task_c_phase4b_beats_production | lightgbm | mlx5_sequence_turnover_4w_avg | 15.0 | feature_importance |

## Interpretation

- Best classification model: `task_a_core_production_risk_filter / logistic_regression`
- Best meta-label strategy: `task_c_phase4b_beats_production__random_forest__thr0.50__phase4b_switch`
- Production+BIL filter improved production by holdout Sharpe: False
- Phase 4B switch improved production by holdout Sharpe: True
- MLX-5 sleeve activation improved production by holdout Sharpe: False
- Bad-week avoidance reduced drawdown versus production: True

Final recommendation: **PROMISING FILTER BUT NEEDS WALK-FORWARD**

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- No meta-label strategy is promoted automatically.
