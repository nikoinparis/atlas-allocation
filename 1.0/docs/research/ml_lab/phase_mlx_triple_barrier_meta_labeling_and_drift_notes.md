# Phase MLX Triple-Barrier Meta-Labeling and Drift Notes

## Research-Only Warning

Phase MLX triple-barrier meta-labeling is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data where applicable, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Triple-barrier labeling is a path-aware way to define financial outcomes. Instead of labeling a date only by the return at a fixed endpoint, it asks which event happened first: an upper profit barrier, a lower loss/risk barrier, or a vertical time barrier.

Path-aware labels matter because finance is path-dependent. A strategy that ends four weeks up may still have hit an unacceptable loss first. A strategy that ends flat may have offered a clean profit-taking opportunity along the way. Triple-barrier labels try to preserve that information.

Meta-labeling means using ML as a second-stage decision filter around an existing strategy. The model is not asked to invent the whole portfolio. It is asked questions such as: should production take risk, should Phase 4B replace production, should an ML sleeve be active, or should an offensive sleeve be reduced?

Fixed-horizon labels such as `forward_return_4w` can fail because they ignore stops, drawdowns, volatility, and path quality. Triple-barrier labels differ by encoding the first barrier hit over the future path. This connects to Marcos Lopez de Prado's financial ML framework: first define events and barriers, then train labels that match the trading decision.

Label design is part of the ML objective. If the label only rewards endpoint return, the model learns endpoint return. If the label rewards hitting a profit barrier before a loss barrier, the model learns something closer to path quality. In this ETF project, that matters because the real decision is not prediction accuracy; it is when to trust production, Phase 4B, or an ML sleeve.

## EECS 127 / Optimization Connection

Optimization starts by defining an objective function and feasible set. In portfolio ML, the objective might be return, Sharpe, drawdown control, CVaR, turnover, or a weighted combination. The feasible decisions might be long-only weights, risk limits, BIL fallback, or rules about when an ML sleeve is allowed to activate.

Constraints shape behavior. A filter creates a constraint on when a strategy can take risk. A probability threshold is a decision boundary. Turnover, volatility, and downside penalties are tradeoffs, just like penalty terms in constrained optimization.

MLX-12 showed the danger of optimizing the wrong objective too directly: a Sharpe-like objective found a trivial feasible solution by hiding in BIL/bonds. That was mathematically coherent but not the desired offensive alpha behavior. MLX-13 improves the problem definition before future optimization by changing the labels from endpoint returns to path-aware barrier outcomes.

This is very EECS 127: before solving, define the right objective, constraints, and feasible set. Bad problem formulation gives a bad optimum, even if the solver works perfectly.

## Technical Setup

- Tasks labeled: ['task_1_production_triple_barrier', 'task_2_phase4b_triple_barrier', 'task_3_phase4b_vs_production_switch', 'task_4_mlx9_sleeve_vs_production', 'task_5_mlx5_offensive_sleeve_danger']
- Barrier settings: [{'barrier_id': 'h4_u1_l1', 'horizon_weeks': 4, 'upper_barrier': 0.01, 'lower_barrier': -0.01}, {'barrier_id': 'h8_u2_l2', 'horizon_weeks': 8, 'upper_barrier': 0.02, 'lower_barrier': -0.02}, {'barrier_id': 'h13_u3_l3', 'horizon_weeks': 13, 'upper_barrier': 0.03, 'lower_barrier': -0.03}]
- Models run: ['gradient_boosting', 'lightgbm', 'logistic_regression', 'random_forest', 'xgboost']
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Leakage controls: features are known at date `t`; labels use future paths only as targets; forward-return target columns are excluded from features
- Skipped tasks/models: [{'task_id': 'task_3_phase4b_vs_production_switch', 'barrier_id': 'h13_u3_l3', 'model': 'xgboost', 'reason': 'fit failed: Invalid classes inferred from unique values of `y`.  Expected: [0 1], got [1 2]'}, {'task_id': 'task_4_mlx9_sleeve_vs_production', 'barrier_id': 'h4_u1_l1', 'model': 'xgboost', 'reason': 'fit failed: Invalid classes inferred from unique values of `y`.  Expected: [0 1], got [1 2]'}, {'task_id': 'task_4_mlx9_sleeve_vs_production', 'barrier_id': 'h8_u2_l2', 'reason': 'fewer than two train classes'}, {'task_id': 'task_4_mlx9_sleeve_vs_production', 'barrier_id': 'h13_u3_l3', 'reason': 'fewer than two train classes'}]

## Label Analysis

| task_id | barrier_id | split | market_state | n_labels | positive_rate | neutral_rate | negative_rate | average_time_to_barrier | imbalance_warning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| task_1_production_triple_barrier | h13_u3_l3 | holdout | calm_trend | 101 | 58.42% | 19.80% | 21.78% | 7.772277227722772 | False |
| task_1_production_triple_barrier | h13_u3_l3 | holdout | neutral_mixed | 115 | 61.74% | 29.57% | 8.70% | 8.278260869565218 | False |
| task_1_production_triple_barrier | h13_u3_l3 | holdout | recovery_confirmed | 20 | 85.00% | 15.00% | 0.00% | 8.15 | True |
| task_1_production_triple_barrier | h13_u3_l3 | holdout | recovery_fragile | 14 | 35.71% | 50.00% | 14.29% | 10.285714285714286 | False |
| task_1_production_triple_barrier | h13_u3_l3 | holdout | stressed_panic | 69 | 37.68% | 56.52% | 5.80% | 11.347826086956522 | False |
| task_1_production_triple_barrier | h13_u3_l3 | train | calm_trend | 182 | 53.30% | 22.53% | 24.18% | 7.653846153846154 | False |
| task_1_production_triple_barrier | h13_u3_l3 | train | neutral_mixed | 327 | 40.06% | 48.01% | 11.93% | 9.801223241590215 | False |
| task_1_production_triple_barrier | h13_u3_l3 | train | recovery_confirmed | 13 | 61.54% | 38.46% | 0.00% | 7.461538461538462 | False |
| task_1_production_triple_barrier | h13_u3_l3 | train | recovery_fragile | 31 | 54.84% | 29.03% | 16.13% | 8.838709677419354 | False |
| task_1_production_triple_barrier | h13_u3_l3 | train | stressed_panic | 125 | 28.00% | 64.80% | 7.20% | 11.168 | False |
| task_1_production_triple_barrier | h13_u3_l3 | train | unknown | 13 | 0.00% | 100.00% | 0.00% | 7.0 | True |
| task_1_production_triple_barrier | h13_u3_l3 | validation | calm_trend | 12 | 66.67% | 25.00% | 8.33% | 9.25 | False |
| task_1_production_triple_barrier | h13_u3_l3 | validation | neutral_mixed | 45 | 31.11% | 46.67% | 22.22% | 9.911111111111111 | False |
| task_1_production_triple_barrier | h13_u3_l3 | validation | recovery_confirmed | 10 | 100.00% | 0.00% | 0.00% | 7.4 | True |
| task_1_production_triple_barrier | h13_u3_l3 | validation | recovery_fragile | 4 | 0.00% | 25.00% | 75.00% | 10.25 | False |
| task_1_production_triple_barrier | h13_u3_l3 | validation | stressed_panic | 33 | 12.12% | 87.88% | 0.00% | 12.909090909090908 | True |
| task_1_production_triple_barrier | h4_u1_l1 | holdout | calm_trend | 101 | 58.42% | 5.94% | 35.64% | 2.089108910891089 | False |
| task_1_production_triple_barrier | h4_u1_l1 | holdout | neutral_mixed | 121 | 66.12% | 7.44% | 26.45% | 2.0991735537190084 | False |
| task_1_production_triple_barrier | h4_u1_l1 | holdout | recovery_confirmed | 20 | 65.00% | 5.00% | 30.00% | 2.3 | False |
| task_1_production_triple_barrier | h4_u1_l1 | holdout | recovery_fragile | 14 | 28.57% | 35.71% | 35.71% | 3.0 | False |
| task_1_production_triple_barrier | h4_u1_l1 | holdout | stressed_panic | 71 | 28.17% | 50.70% | 21.13% | 3.2535211267605635 | False |
| task_1_production_triple_barrier | h4_u1_l1 | train | calm_trend | 182 | 52.20% | 17.03% | 30.77% | 2.2857142857142856 | False |
| task_1_production_triple_barrier | h4_u1_l1 | train | neutral_mixed | 327 | 45.26% | 34.56% | 20.18% | 2.7217125382262997 | False |
| task_1_production_triple_barrier | h4_u1_l1 | train | recovery_confirmed | 13 | 61.54% | 23.08% | 15.38% | 2.3076923076923075 | False |
| task_1_production_triple_barrier | h4_u1_l1 | train | recovery_fragile | 31 | 41.94% | 32.26% | 25.81% | 3.0 | False |
| task_1_production_triple_barrier | h4_u1_l1 | train | stressed_panic | 125 | 28.00% | 51.20% | 20.80% | 3.24 | False |
| task_1_production_triple_barrier | h4_u1_l1 | train | unknown | 4 | 0.00% | 100.00% | 0.00% | 2.5 | True |
| task_1_production_triple_barrier | h4_u1_l1 | validation | calm_trend | 12 | 50.00% | 33.33% | 16.67% | 2.75 | False |
| task_1_production_triple_barrier | h4_u1_l1 | validation | neutral_mixed | 45 | 40.00% | 28.89% | 31.11% | 2.577777777777778 | False |
| task_1_production_triple_barrier | h4_u1_l1 | validation | recovery_confirmed | 10 | 30.00% | 70.00% | 0.00% | 3.7 | False |
| task_1_production_triple_barrier | h4_u1_l1 | validation | recovery_fragile | 4 | 25.00% | 50.00% | 25.00% | 3.0 | False |
| task_1_production_triple_barrier | h4_u1_l1 | validation | stressed_panic | 33 | 12.12% | 66.67% | 21.21% | 3.6666666666666665 | False |
| task_1_production_triple_barrier | h8_u2_l2 | holdout | calm_trend | 101 | 58.42% | 12.87% | 28.71% | 4.3861386138613865 | False |
| task_1_production_triple_barrier | h8_u2_l2 | holdout | neutral_mixed | 119 | 63.87% | 15.13% | 21.01% | 4.53781512605042 | False |
| task_1_production_triple_barrier | h8_u2_l2 | holdout | recovery_confirmed | 20 | 70.00% | 10.00% | 20.00% | 4.55 | False |
| task_1_production_triple_barrier | h8_u2_l2 | holdout | recovery_fragile | 14 | 28.57% | 50.00% | 21.43% | 6.928571428571429 | False |
| task_1_production_triple_barrier | h8_u2_l2 | holdout | stressed_panic | 70 | 24.29% | 65.71% | 10.00% | 6.942857142857143 | False |
| task_1_production_triple_barrier | h8_u2_l2 | train | calm_trend | 182 | 51.10% | 20.88% | 28.02% | 4.56043956043956 | False |
| task_1_production_triple_barrier | h8_u2_l2 | train | neutral_mixed | 327 | 42.20% | 41.90% | 15.90% | 5.801223241590214 | False |
| task_1_production_triple_barrier | h8_u2_l2 | train | recovery_confirmed | 13 | 69.23% | 30.77% | 0.00% | 5.0 | False |

## Model Results

### Best Classification Rows

| task_id | barrier_id | model_name | split | accuracy | balanced_accuracy | macro_f1 | precision_positive | recall_positive | precision_negative | recall_negative | predicted_positive_rate | predicted_danger_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | logistic_regression | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | random_forest | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | gradient_boosting | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | xgboost | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_4_mlx9_sleeve_vs_production | h4_u1_l1 | logistic_regression | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_4_mlx9_sleeve_vs_production | h4_u1_l1 | random_forest | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_4_mlx9_sleeve_vs_production | h4_u1_l1 | gradient_boosting | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_4_mlx9_sleeve_vs_production | h4_u1_l1 | lightgbm | validation | 1.000 | 1.000 | 1.000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_1_production_triple_barrier | h8_u2_l2 | logistic_regression | validation | 0.615 | 0.534 | 0.510 | 0.4603174603174603 | 0.8787878787878788 | 0.6666666666666666 | 0.13333333333333333 | 60.58% | 2.88% |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | logistic_regression | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | random_forest | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | gradient_boosting | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | xgboost | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | lightgbm | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h13_u3_l3 | logistic_regression | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h13_u3_l3 | random_forest | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h13_u3_l3 | gradient_boosting | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_3_phase4b_vs_production_switch | h13_u3_l3 | lightgbm | validation | 0.981 | 0.500 | 0.495 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier | h4_u1_l1 | random_forest | validation | 0.452 | 0.447 | 0.429 | 0.410958904109589 | 0.75 | 0.5714285714285714 | 0.38095238095238093 | 70.19% | 13.46% |
| task_1_production_triple_barrier | h4_u1_l1 | random_forest | validation | 0.423 | 0.438 | 0.414 | 0.3492063492063492 | 0.6875 | 0.47058823529411764 | 0.3333333333333333 | 60.58% | 16.35% |
| task_1_production_triple_barrier | h8_u2_l2 | random_forest | validation | 0.490 | 0.436 | 0.413 | 0.36923076923076925 | 0.7272727272727273 | 0.2222222222222222 | 0.13333333333333333 | 62.50% | 8.65% |
| task_1_production_triple_barrier | h13_u3_l3 | logistic_regression | validation | 0.577 | 0.451 | 0.411 | 0.5098039215686274 | 0.7222222222222222 | 0.0 | 0.0 | 49.04% | 0.00% |
| task_2_phase4b_triple_barrier | h13_u3_l3 | logistic_regression | validation | 0.587 | 0.457 | 0.411 | 0.4642857142857143 | 0.7878787878787878 | 0.0 | 0.0 | 53.85% | 0.00% |
| task_2_phase4b_triple_barrier | h4_u1_l1 | logistic_regression | validation | 0.510 | 0.436 | 0.403 | 0.45454545454545453 | 0.75 | 0.5 | 0.047619047619047616 | 63.46% | 1.92% |

### Confusion Matrix Sample

| task_id | barrier_id | model_name | split | actual_label | predicted_label | count |
| --- | --- | --- | --- | --- | --- | --- |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | -1 | -1 | 127 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | -1 | 0 | 7 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | -1 | 1 | 24 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | 0 | -1 | 22 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | 0 | 0 | 184 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | 0 | 1 | 19 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | 1 | -1 | 62 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | 1 | 0 | 28 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | train | 1 | 1 | 209 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | -1 | -1 | 1 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | -1 | 0 | 3 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | -1 | 1 | 20 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | 0 | -1 | 5 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | 0 | 0 | 18 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | 0 | 1 | 25 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | 1 | -1 | 3 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | 1 | 0 | 6 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | validation | 1 | 1 | 23 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | -1 | -1 | 43 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | -1 | 0 | 12 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | -1 | 1 | 39 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | 0 | -1 | 7 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | 0 | 0 | 29 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | 0 | 1 | 21 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | 1 | -1 | 80 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | 1 | 0 | 13 |
| task_1_production_triple_barrier | h4_u1_l1 | logistic_regression | holdout | 1 | 1 | 83 |
| task_1_production_triple_barrier | h4_u1_l1 | random_forest | train | -1 | -1 | 124 |
| task_1_production_triple_barrier | h4_u1_l1 | random_forest | train | -1 | 0 | 3 |
| task_1_production_triple_barrier | h4_u1_l1 | random_forest | train | -1 | 1 | 31 |

### Feature Importance Sample

| task_id | barrier_id | model_name | feature | importance | rank |
| --- | --- | --- | --- | --- | --- |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | phase4b_vol_13w | 147.0 | 1 |
| task_3_phase4b_vs_production_switch | h13_u3_l3 | lightgbm | avg_corr_risk_off_z | 144.0 | 1 |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | lightgbm | mlx12_decision_focused_vol_13w | 91.0 | 1 |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | production_vol_13w | 82.0 | 2 |
| task_1_production_triple_barrier | h8_u2_l2 | lightgbm | xs_mean_corr_to_SPY_26w | 79.0 | 1 |
| task_2_phase4b_triple_barrier | h4_u1_l1 | lightgbm | xs_mean_cross_sectional_return_rank_26w | 76.0 | 1 |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | p_regime_confidence_refreshed | 76.0 | 3 |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | production_drawdown_13w | 75.0 | 4 |
| task_1_production_triple_barrier | h13_u3_l3 | lightgbm | xs_mean_corr_to_SPY_26w | 74.0 | 1 |
| task_2_phase4b_triple_barrier | h13_u3_l3 | lightgbm | xs_mean_corr_to_SPY_26w | 71.0 | 1 |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | market_drawdown_risk_off_z | 71.0 | 5 |
| task_1_production_triple_barrier | h8_u2_l2 | lightgbm | xs_std_realized_vol_26w | 69.0 | 2 |
| task_3_phase4b_vs_production_switch | h4_u1_l1 | lightgbm | google_fear_z_tradable | 67.0 | 2 |
| task_2_phase4b_triple_barrier | h8_u2_l2 | lightgbm | xs_std_trailing_return_52w | 66.0 | 1 |
| task_3_phase4b_vs_production_switch | h8_u2_l2 | lightgbm | p_regime_confidence_blend25 | 64.0 | 6 |
| task_2_phase4b_triple_barrier | h13_u3_l3 | lightgbm | xs_std_beta_to_SPY_26w | 63.0 | 2 |
| task_5_mlx5_offensive_sleeve_danger | h4_u1_l1 | lightgbm | xs_std_trailing_return_52w | 59.0 | 1 |
| task_5_mlx5_offensive_sleeve_danger | h8_u2_l2 | lightgbm | xs_std_trailing_return_52w | 59.0 | 1 |
| task_2_phase4b_triple_barrier | h13_u3_l3 | lightgbm | xs_std_trailing_return_52w | 58.0 | 3 |
| task_5_mlx5_offensive_sleeve_danger | h13_u3_l3 | lightgbm | xs_mean_cross_sectional_return_rank_13w | 58.0 | 3 |
| task_5_mlx5_offensive_sleeve_danger | h13_u3_l3 | lightgbm | mlx5_sequence_vol_13w | 58.0 | 1 |
| task_5_mlx5_offensive_sleeve_danger | h13_u3_l3 | lightgbm | xs_std_trailing_return_52w | 58.0 | 2 |
| task_1_production_triple_barrier | h13_u3_l3 | lightgbm | xs_std_realized_vol_26w | 57.0 | 2 |
| task_1_production_triple_barrier | h4_u1_l1 | lightgbm | xs_std_trailing_return_52w | 56.0 | 1 |
| task_2_phase4b_triple_barrier | h8_u2_l2 | lightgbm | phase4b_drawdown_13w | 56.0 | 2 |
| task_1_production_triple_barrier | h8_u2_l2 | lightgbm | phase4b_drawdown_13w | 55.0 | 3 |
| task_1_production_triple_barrier | h4_u1_l1 | lightgbm | xs_std_beta_to_SPY_26w | 52.0 | 2 |
| task_1_production_triple_barrier | h13_u3_l3 | lightgbm | xs_std_trailing_return_52w | 52.0 | 3 |
| task_1_production_triple_barrier | h8_u2_l2 | lightgbm | market_vol_risk_off_z | 52.0 | 4 |
| task_2_phase4b_triple_barrier | h4_u1_l1 | lightgbm | xs_std_beta_to_SPY_26w | 51.0 | 2 |

## Strategy Results

- Best validation-selected strategy: `task_1_production_triple_barrier__h13_u3_l3__gradient_boosting__thr0.60__production_risk_filter`
- Validation-selected holdout annual return: 6.37%
- Validation-selected holdout Sharpe: 0.764
- Validation-selected max drawdown: -13.98%
- Validation-selected CVaR 5%: -2.74%
- Best holdout-diagnostic strategy: `task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.70__phase4b_danger_override` with Sharpe 1.165

| strategy_name | strategy_family | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_turnover | average_bil_exposure | average_ml_sleeve_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx12_decision_focused | benchmark | 1.73% | 0.49% | 3.577 | -2.33% | -0.12% | n/a | 0.00% | n/a |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.70__phase4b_danger_override | phase4b_danger_override | 10.28% | 8.82% | 1.165 | -12.44% | -2.56% | 6.27% | 0.94% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__random_forest__thr0.60__phase4b_danger_override | phase4b_danger_override | 10.29% | 8.88% | 1.159 | -12.44% | -2.64% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__random_forest__thr0.70__phase4b_danger_override | phase4b_danger_override | 10.29% | 8.88% | 1.159 | -12.44% | -2.64% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__xgboost__thr0.70__phase4b_danger_override | phase4b_danger_override | 10.29% | 8.88% | 1.159 | -12.44% | -2.64% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.92% | 8.80% | 1.126 | -12.44% | -2.57% | 7.52% | 1.25% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__random_forest__thr0.50__phase4b_danger_override | phase4b_danger_override | 9.95% | 8.86% | 1.123 | -12.44% | -2.64% | 2.51% | 0.31% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__gradient_boosting__thr0.50__phase4b_danger_override | phase4b_danger_override | 9.91% | 8.83% | 1.122 | -12.44% | -2.60% | 4.94% | 0.77% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.50__phase4b_danger_override | phase4b_danger_override | 9.40% | 8.62% | 1.091 | -12.44% | -2.57% | 8.78% | 1.72% | 0.00% |
| task_2_phase4b_triple_barrier__h4_u1_l1__random_forest__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.68% | 9.02% | 1.073 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h4_u1_l1__random_forest__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.68% | 9.02% | 1.073 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h4_u1_l1__xgboost__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.68% | 9.02% | 1.073 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| phase4b | benchmark | 9.64% | 9.01% | 1.070 | -12.44% | -2.72% | n/a | 0.00% | n/a |
| task_2_phase4b_triple_barrier__h13_u3_l3__lightgbm__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.31% | 8.75% | 1.063 | -12.44% | -2.64% | 5.02% | 0.63% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__xgboost__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.27% | 8.77% | 1.057 | -12.44% | -2.64% | 5.64% | 1.25% | 0.00% |
| task_2_phase4b_triple_barrier__h4_u1_l1__random_forest__thr0.50__phase4b_danger_override | phase4b_danger_override | 9.52% | 9.03% | 1.055 | -12.44% | -2.73% | 1.22% | 0.15% | 0.00% |
| task_2_phase4b_triple_barrier__h4_u1_l1__lightgbm__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.49% | 9.03% | 1.052 | -12.44% | -2.73% | 1.22% | 0.31% | 0.00% |
| task_2_phase4b_triple_barrier__h13_u3_l3__gradient_boosting__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.20% | 8.76% | 1.050 | -12.44% | -2.64% | 4.39% | 0.78% | 0.00% |
| task_2_phase4b_triple_barrier__h4_u1_l1__xgboost__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.36% | 9.01% | 1.039 | -12.44% | -2.73% | 1.22% | 0.46% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__random_forest__thr0.50__phase4b_danger_override | phase4b_danger_override | 9.29% | 8.97% | 1.035 | -12.44% | -2.70% | 2.47% | 0.46% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__gradient_boosting__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__gradient_boosting__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__lightgbm__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__random_forest__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__random_forest__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__xgboost__thr0.50__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__xgboost__thr0.60__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| task_2_phase4b_triple_barrier__h8_u2_l2__xgboost__thr0.70__phase4b_danger_override | phase4b_danger_override | 9.11% | 9.01% | 1.011 | -12.44% | -2.72% | 0.00% | 0.00% | 0.00% |
| phase7 | benchmark | 9.57% | 9.47% | 1.011 | -13.83% | -2.92% | n/a | 0.00% | n/a |
| phase6 | benchmark | 9.57% | 9.47% | 1.010 | -13.77% | -2.92% | n/a | 0.00% | n/a |

## Drift Monitoring

### Feature Drift

| feature | split | train_mean | split_mean | z_shift | abs_z_shift | psi | missing_rate_train | missing_rate_split |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xs_std_rolling_sharpe_26w | holdout | 1.1524196109710503 | 3.5492752527180578 | 5.6163729532442845 | 5.616 | 1.166 | 0.013844515441959531 | 0.0 |
| xs_std_rolling_sharpe_26w | validation | 1.1524196109710503 | 3.2214192721736286 | 4.848132501204797 | 4.848 | 9.750 | 0.013844515441959531 | 0.0 |
| xs_std_rolling_sharpe_13w | holdout | 1.6490843111738012 | 4.2152830818019895 | 4.0633105485585554 | 4.063 | 0.750 | 0.007454739084132056 | 0.0 |
| xs_std_rolling_sharpe_13w | validation | 1.6490843111738012 | 3.7452892542613108 | 3.319123894328353 | 3.319 | 10.790 | 0.007454739084132056 | 0.0 |
| BIL_ret_13w | holdout | 0.0009613936861457493 | 0.0065540802137882895 | 2.2082423842320322 | 2.208 | 2.027 | 0.4249201277955272 | 0.0 |
| BIL_ret_4w | holdout | 0.00032777569746051495 | 0.002030381466408523 | 1.7116325984065353 | 1.712 | 3.103 | 0.41533546325878595 | 0.0 |
| BIL_ret_13w | validation | 0.0009613936861457493 | 0.004584650202574803 | 1.430623470308496 | 1.431 | 10.732 | 0.4249201277955272 | 0.0 |
| xs_mean_beta_to_SPY_26w | validation | 0.7799006634719788 | 0.5755086785667285 | -1.1928534043420458 | 1.193 | 9.436 | 0.013844515441959531 | 0.0 |
| xs_std_trailing_return_52w | validation | 0.15776403369699357 | 0.10783541534434332 | -1.1185720174560638 | 1.119 | 4.610 | 0.055378061767838126 | 0.0 |
| BIL_ret_4w | validation | 0.00032777569746051495 | 0.0014236760172944647 | 1.1017105346653013 | 1.102 | 10.536 | 0.41533546325878595 | 0.0 |
| xs_mean_beta_to_SPY_26w | holdout | 0.7799006634719788 | 0.6291628990777292 | -0.8797216559345186 | 0.880 | 4.220 | 0.013844515441959531 | 0.0 |
| xs_std_cross_sectional_return_rank_26w | holdout | 0.2911827569572496 | 0.29015933530138743 | -0.8512423572726312 | 0.851 | 12.450 | 0.027689030883919063 | 0.0 |
| xs_std_cross_sectional_return_rank_26w | validation | 0.2911827569572496 | 0.2901593353013875 | -0.851242357272585 | 0.851 | 12.450 | 0.027689030883919063 | 0.0 |
| xs_mean_cross_sectional_return_rank_26w | validation | 0.5087330643875969 | 0.5051546391752577 | -0.848634680417904 | 0.849 | 12.511 | 0.027689030883919063 | 0.0 |
| xs_mean_cross_sectional_return_rank_26w | holdout | 0.5087330643875969 | 0.5051546391752578 | -0.8486346804178777 | 0.849 | 12.511 | 0.027689030883919063 | 0.0 |
| xs_std_cross_sectional_return_rank_13w | holdout | 0.2911683837742152 | 0.2901593295551788 | -0.8409763551631687 | 0.841 | 10.786 | 0.013844515441959531 | 0.0 |
| xs_std_cross_sectional_return_rank_13w | validation | 0.2911683837742152 | 0.2901593353013875 | -0.8409715660987788 | 0.841 | 10.751 | 0.013844515441959531 | 0.0 |
| xs_mean_cross_sectional_return_rank_13w | validation | 0.5086828273165813 | 0.5051546391752577 | -0.8384288657269772 | 0.838 | 10.874 | 0.013844515441959531 | 0.0 |
| xs_mean_cross_sectional_return_rank_13w | holdout | 0.5086828273165813 | 0.5051546391752578 | -0.8384288657269509 | 0.838 | 10.874 | 0.013844515441959531 | 0.0 |
| xs_std_cross_sectional_vol_rank_13w | holdout | 0.29116189433585593 | 0.29015933530138743 | -0.8363675945315074 | 0.836 | 10.798 | 0.007454739084132056 | 0.0 |
| xs_std_cross_sectional_vol_rank_13w | validation | 0.29116189433585593 | 0.2901593353013875 | -0.8363675945314611 | 0.836 | 10.805 | 0.007454739084132056 | 0.0 |
| BIL_ret_1w | holdout | 8.47712766170041e-05 | 0.0005088495560290827 | 0.8361907139121267 | 0.836 | 1.514 | 0.41214057507987223 | 0.0 |
| xs_mean_cross_sectional_vol_rank_13w | validation | 0.5086601136590192 | 0.5051546391752577 | -0.8338410534882278 | 0.834 | 10.769 | 0.007454739084132056 | 0.0 |
| xs_mean_cross_sectional_vol_rank_13w | holdout | 0.5086601136590192 | 0.5051546391752578 | -0.8338410534882014 | 0.834 | 10.769 | 0.007454739084132056 | 0.0 |
| xs_std_trailing_return_26w | validation | 0.10495599282842215 | 0.07442597988215545 | -0.8249652860276915 | 0.825 | 4.004 | 0.027689030883919063 | 0.0 |

### Prediction Drift

| task_id | barrier_id | model_name | split | year | market_state | mean_probability_up | mean_probability_down | predicted_positive_rate | predicted_danger_rate | mean_confidence | mean_entropy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2020 | calm_trend | 46.88% | 25.23% | 75.00% | 0.00% | 0.5125006136532694 | 1.004017600059486 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2020 | neutral_mixed | 47.79% | 13.75% | 64.29% | 0.00% | 0.5181679273216354 | 0.9436645147297138 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2020 | recovery_confirmed | 52.37% | 18.00% | 81.82% | 0.00% | 0.526266386496464 | 0.9760904673161055 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2020 | recovery_fragile | 40.82% | 10.21% | 0.00% | 0.00% | 0.48974411176295907 | 0.948345606476561 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2020 | stressed_panic | 51.82% | 9.59% | 55.56% | 0.00% | 0.601981427458195 | 0.8439248279250896 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2021 | calm_trend | 50.01% | 27.65% | 78.38% | 18.92% | 0.5364175367751376 | 0.9736134580184355 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2021 | neutral_mixed | 54.70% | 22.61% | 81.25% | 12.50% | 0.5503590312810722 | 0.9577136990607499 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2022 | neutral_mixed | 39.07% | 20.62% | 30.77% | 7.69% | 0.5513227875166502 | 0.9358767936422894 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2022 | stressed_panic | 32.44% | 12.28% | 17.95% | 0.00% | 0.59499987311924 | 0.8743622463470874 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2023 | calm_trend | 62.88% | 22.88% | 96.15% | 3.85% | 0.6338606130046394 | 0.8722024578653398 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2023 | neutral_mixed | 72.74% | 15.98% | 100.00% | 0.00% | 0.7274433559701233 | 0.7397293439493207 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2023 | recovery_fragile | 79.01% | 9.13% | 100.00% | 0.00% | 0.790067506513033 | 0.6485753010466263 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2024 | calm_trend | 48.26% | 29.39% | 92.59% | 7.41% | 0.5133912087638381 | 1.0007962610781138 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2024 | neutral_mixed | 41.21% | 30.77% | 56.00% | 32.00% | 0.4887326932745959 | 1.0210892774744782 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2025 | calm_trend | 37.12% | 29.81% | 66.67% | 0.00% | 0.4431970740234434 | 1.059704541504785 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2025 | neutral_mixed | 36.48% | 37.13% | 41.67% | 45.83% | 0.5304825125766598 | 0.982628590049182 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2025 | recovery_confirmed | 30.48% | 31.55% | 11.11% | 44.44% | 0.5272930713950964 | 0.9703393448537168 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2025 | recovery_fragile | 23.49% | 6.69% | 0.00% | 0.00% | 0.6981378474292305 | 0.7679114087578995 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2025 | stressed_panic | 36.25% | 8.51% | 16.67% | 0.00% | 0.5723271257288177 | 0.8648461241506911 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | holdout | 2026 | neutral_mixed | 8.06% | 84.88% | 0.00% | 100.00% | 0.8488389768137491 | 0.5267873361588358 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2004 | unknown | 11.83% | 1.59% | 0.00% | 0.00% | 0.8658179952088128 | 0.4382195086587888 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2005 | calm_trend | 7.99% | 1.74% | 0.00% | 0.00% | 0.9026599948829225 | 0.36247033053235267 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2005 | neutral_mixed | 7.66% | 1.49% | 0.00% | 0.00% | 0.9084885601414396 | 0.3434170868523172 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2006 | calm_trend | 55.07% | 5.17% | 71.43% | 0.00% | 0.7973498278443688 | 0.5880538414903704 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2006 | neutral_mixed | 32.77% | 3.26% | 38.89% | 0.00% | 0.830188752375846 | 0.4937033796371758 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2006 | recovery_confirmed | 67.07% | 7.59% | 100.00% | 0.00% | 0.6707408839396809 | 0.8075966538911338 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2006 | recovery_fragile | 73.20% | 4.99% | 100.00% | 0.00% | 0.7319602173126385 | 0.7075223618567819 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2006 | stressed_panic | 36.44% | 3.29% | 33.33% | 0.00% | 0.7772629783201267 | 0.6159114561798268 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2007 | calm_trend | 52.36% | 22.45% | 55.56% | 22.22% | 0.5529109245023969 | 0.9448039232080679 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2007 | neutral_mixed | 36.50% | 13.78% | 27.27% | 9.09% | 0.6044471047511187 | 0.8641733385676638 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2007 | recovery_fragile | 31.97% | 18.70% | 0.00% | 0.00% | 0.4932841172693263 | 1.024925423924176 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2007 | stressed_panic | 38.18% | 7.22% | 42.11% | 0.00% | 0.7153686161229466 | 0.7351107292668722 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2008 | neutral_mixed | 14.80% | 46.15% | 0.00% | 66.67% | 0.6121857096682445 | 0.9030426562993848 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2008 | recovery_fragile | 14.06% | 26.55% | 0.00% | 0.00% | 0.5939206752031744 | 0.9373298545069038 |
| task_1_production_triple_barrier | h13_u3_l3 | gradient_boosting | train | 2008 | stressed_panic | 28.44% | 15.56% | 33.33% | 10.26% | 0.6920858961804366 | 0.7673092151051834 |

### Strategy Behavior Drift

| strategy_name | split | year | market_state | mean_turnover | mean_bil_exposure | mean_core_exposure | mean_ml_sleeve_exposure | mean_net_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx12_decision_focused | holdout | 2020 | calm_trend | n/a | 0.0 | n/a | n/a | 0.0005577413562745251 |
| mlx12_decision_focused | holdout | 2020 | neutral_mixed | n/a | 0.0 | n/a | n/a | -0.0001084626045245611 |
| mlx12_decision_focused | holdout | 2020 | recovery_confirmed | n/a | 0.0 | n/a | n/a | -0.0002519590292566288 |
| mlx12_decision_focused | holdout | 2020 | recovery_fragile | n/a | 0.0 | n/a | n/a | -0.000401118092797 |
| mlx12_decision_focused | holdout | 2020 | stressed_panic | n/a | 0.0 | n/a | n/a | -0.00014556345163826856 |
| mlx12_decision_focused | holdout | 2021 | calm_trend | n/a | 0.0 | n/a | n/a | -0.00016432377345653527 |
| mlx12_decision_focused | holdout | 2021 | neutral_mixed | n/a | 0.0 | n/a | n/a | -0.00029524027837513154 |
| mlx12_decision_focused | holdout | 2022 | neutral_mixed | n/a | 0.0 | n/a | n/a | -9.85488564377967e-05 |
| mlx12_decision_focused | holdout | 2022 | stressed_panic | n/a | 0.0 | n/a | n/a | 0.00021605200399137583 |
| mlx12_decision_focused | holdout | 2023 | calm_trend | n/a | 0.0 | n/a | n/a | 0.0005372233846332648 |
| mlx12_decision_focused | holdout | 2023 | neutral_mixed | n/a | 0.0 | n/a | n/a | 0.000593047255116541 |
| mlx12_decision_focused | holdout | 2023 | recovery_fragile | n/a | 0.0 | n/a | n/a | 0.0004155378049907965 |
| mlx12_decision_focused | holdout | 2024 | calm_trend | n/a | 0.0 | n/a | n/a | 0.0009361512598433593 |
| mlx12_decision_focused | holdout | 2024 | neutral_mixed | n/a | 0.0 | n/a | n/a | 0.0008239202836983988 |
| mlx12_decision_focused | holdout | 2025 | calm_trend | n/a | 0.0 | n/a | n/a | 0.0011319322846085 |
| mlx12_decision_focused | holdout | 2025 | neutral_mixed | n/a | 0.0 | n/a | n/a | 0.0005869642109034316 |
| mlx12_decision_focused | holdout | 2025 | recovery_confirmed | n/a | 0.0 | n/a | n/a | 0.0007206640655998094 |
| mlx12_decision_focused | holdout | 2025 | recovery_fragile | n/a | 0.0 | n/a | n/a | 0.000720117180239675 |
| mlx12_decision_focused | holdout | 2025 | stressed_panic | n/a | 0.0 | n/a | n/a | 0.0006525935975366 |
| mlx12_decision_focused | holdout | 2026 | neutral_mixed | n/a | 0.0 | n/a | n/a | 0.0005575883824991345 |
| mlx12_decision_focused | holdout | 2026 | recovery_confirmed | n/a | 0.0 | n/a | n/a | 0.0002623380002606 |
| mlx12_decision_focused | holdout | 2026 | stressed_panic | n/a | 0.0 | n/a | n/a | 0.0001407034339258503 |
| mlx12_decision_focused | holdout | 2026 | unknown | n/a | 0.0 | n/a | n/a | 0.00020720748850284998 |
| mlx12_decision_focused | train | 2000 | unknown | n/a | 0.0 | n/a | n/a | -0.0012665982558697083 |
| mlx12_decision_focused | train | 2001 | unknown | n/a | 0.0 | n/a | n/a | -0.0020596194273895573 |
| mlx12_decision_focused | train | 2002 | unknown | n/a | 0.0 | n/a | n/a | -0.004539846398168952 |
| mlx12_decision_focused | train | 2003 | unknown | n/a | 0.0 | n/a | n/a | 0.0019231229034873656 |
| mlx12_decision_focused | train | 2004 | unknown | n/a | 0.0 | n/a | n/a | 0.0010741585825331187 |
| mlx12_decision_focused | train | 2005 | calm_trend | n/a | 0.0 | n/a | n/a | -0.0009587188975386667 |
| mlx12_decision_focused | train | 2005 | neutral_mixed | n/a | 0.0 | n/a | n/a | 0.0006650366210067812 |
| mlx12_decision_focused | train | 2006 | calm_trend | n/a | 0.0 | n/a | n/a | -0.0003867010511487285 |
| mlx12_decision_focused | train | 2006 | neutral_mixed | n/a | 0.0 | n/a | n/a | 0.00044816829366260826 |
| mlx12_decision_focused | train | 2006 | recovery_confirmed | n/a | 0.0 | n/a | n/a | 0.0007999114317298666 |
| mlx12_decision_focused | train | 2006 | recovery_fragile | n/a | 0.0 | n/a | n/a | -0.0009749450969525667 |
| mlx12_decision_focused | train | 2006 | stressed_panic | n/a | 0.0 | n/a | n/a | 0.00030715612615446665 |

### Performance Drift

| strategy_name | window | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | active_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mlx12_decision_focused | 2017_2018 | 0.50% | 0.33% | 1.540 | -0.35% | -0.10% | 104 |
| mlx12_decision_focused | 2019_2020 | 0.87% | 0.42% | 2.106 | -0.91% | -0.12% | 104 |
| mlx12_decision_focused | 2021_2022 | -0.18% | 0.35% | -0.525 | -1.31% | -0.11% | 105 |
| mlx12_decision_focused | 2023_2026 | 3.52% | 0.44% | 8.040 | -0.25% | -0.09% | 175 |
| mlx9_ensemble | 2017_2018 | 4.81% | 6.34% | 0.758 | -8.37% | -2.17% | 104 |
| mlx9_ensemble | 2019_2020 | 8.10% | 9.47% | 0.855 | -13.24% | -3.46% | 104 |
| mlx9_ensemble | 2021_2022 | 5.01% | 7.56% | 0.662 | -4.51% | -2.27% | 105 |
| mlx9_ensemble | 2023_2026 | 12.64% | 7.59% | 1.665 | -6.39% | -2.03% | 171 |
| phase4b | 2017_2018 | 4.84% | 6.26% | 0.773 | -9.20% | -2.15% | 104 |
| phase4b | 2019_2020 | 9.64% | 10.42% | 0.925 | -12.44% | -3.63% | 104 |
| phase4b | 2021_2022 | 4.80% | 7.40% | 0.648 | -6.79% | -2.14% | 105 |
| phase4b | 2023_2026 | 13.75% | 7.98% | 1.724 | -6.93% | -2.03% | 171 |
| production | 2017_2018 | 5.38% | 6.56% | 0.820 | -8.14% | -2.25% | 104 |
| production | 2019_2020 | 6.85% | 9.69% | 0.707 | -13.98% | -3.64% | 104 |
| production | 2021_2022 | 4.91% | 7.65% | 0.642 | -4.57% | -2.30% | 105 |
| production | 2023_2026 | 12.36% | 7.56% | 1.636 | -6.26% | -2.06% | 171 |
| task_1_production_triple_barrier__h13_u3_l3__gradient_boosting__thr0.60__production_risk_filter | 2017_2018 | 5.38% | 6.56% | 0.820 | -8.14% | -2.25% | 104 |
| task_1_production_triple_barrier__h13_u3_l3__gradient_boosting__thr0.60__production_risk_filter | 2019_2020 | 6.85% | 9.69% | 0.707 | -13.98% | -3.64% | 104 |
| task_1_production_triple_barrier__h13_u3_l3__gradient_boosting__thr0.60__production_risk_filter | 2021_2022 | 4.60% | 7.43% | 0.620 | -4.57% | -2.30% | 105 |
| task_1_production_triple_barrier__h13_u3_l3__gradient_boosting__thr0.60__production_risk_filter | 2023_2026 | 9.36% | 7.07% | 1.324 | -6.26% | -1.91% | 162 |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.70__phase4b_danger_override | 2017_2018 | 4.84% | 6.26% | 0.773 | -9.20% | -2.15% | 104 |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.70__phase4b_danger_override | 2019_2020 | 9.41% | 10.41% | 0.904 | -12.44% | -3.63% | 104 |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.70__phase4b_danger_override | 2021_2022 | 4.98% | 7.20% | 0.692 | -6.79% | -1.91% | 105 |
| task_2_phase4b_triple_barrier__h13_u3_l3__logistic_regression__thr0.70__phase4b_danger_override | 2023_2026 | 15.32% | 7.61% | 2.011 | -5.47% | -1.74% | 162 |

## Interpretation

- Did triple-barrier labels improve meta-labeling? False
- Did the validation-selected filter beat production by holdout Sharpe? False
- Did it beat Phase 4B by holdout Sharpe? False
- Did drift monitoring flag feature shifts? False
- Final recommendation: **USE LABELS FOR MLX-12B OBJECTIVE DESIGN**

These labels are useful for future MLX-12B objective design because they make the target path-aware before optimizing a portfolio loss. This remains research-only until it passes stricter walk-forward, PIT data, and monitoring tests.

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- Triple-barrier labels use future paths only as targets; results remain high overfitting risk.
- No triple-barrier model or filter is promoted automatically.
