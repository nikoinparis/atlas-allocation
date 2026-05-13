# Phase MLX-5C Sequence Multi-Seed Walk-Forward Report

## Research-Only Warning

Phase MLX-5C is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Random seed robustness checks whether a neural network result changes when training starts from different random initial weights and mini-batch order. Neural networks can produce different results from different seeds because optimization is non-convex and many parameter settings can fit noisy financial data.

Walk-forward validation trains on older data, validates on the next period, and tests on a later unseen period, then repeats this chronology across several market windows. It is more realistic than one train/validation/holdout split because it asks whether a strategy keeps working as market regimes change. Sequence length sensitivity checks whether the model depends on one very specific lookback window. This matters before trusting MLX-5 because a single 2020+ holdout win can still be seed-specific, regime-specific, or overlay-specific.

## Executive Summary

- Grid actually run: 9 training runs, 36 portfolio variants.
- Sequence lengths tested: [13, 26]
- Seeds tested: [0, 1, 2]
- Folds tested: ['fold_a_2017_2018', 'fold_b_2019_2020', 'fold_c_2021_2022', 'fold_d_2023_2026']
- Mean Sharpe across bil-fallback runs: 1.276
- Median Sharpe: 1.628
- Worst Sharpe: 0.159
- Percent Sharpe > 0: 100.00%
- Percent beating simple momentum: 77.78%
- Percent beating production: 55.56%
- Percent beating Phase 4B: 38.89%
- Worst max drawdown: -14.56%
- Worst CVaR 5%: -4.17%
- Final recommendation: **PROMISING OFFENSIVE SLEEVE BUT NOT PRODUCTION**

## MLX-5 / MLX-5B Recap

MLX-5 found a promising LSTM sequence model with BIL fallback in the 2020+ holdout, but MLX-5B showed weaker 2018+ performance, negative COVID crash/rebound performance, high cost sensitivity, weak calm-trend results, and no random-seed robustness yet. MLX-5C directly tests those open questions with multiple chronological folds and bounded seed/model/sequence variations.

## Fold Definitions

| fold_name | train_start | train_end | validation_start | validation_end | test_start | test_end |
| --- | --- | --- | --- | --- | --- | --- |
| fold_a_2017_2018 | 2000-01-01 00:00:00 | 2014-12-31 00:00:00 | 2015-01-01 00:00:00 | 2016-12-31 00:00:00 | 2017-01-01 00:00:00 | 2018-12-31 00:00:00 |
| fold_b_2019_2020 | 2000-01-01 00:00:00 | 2016-12-31 00:00:00 | 2017-01-01 00:00:00 | 2018-12-31 00:00:00 | 2019-01-01 00:00:00 | 2020-12-31 00:00:00 |
| fold_c_2021_2022 | 2000-01-01 00:00:00 | 2018-12-31 00:00:00 | 2019-01-01 00:00:00 | 2020-12-31 00:00:00 | 2021-01-01 00:00:00 | 2022-12-31 00:00:00 |
| fold_d_2023_2026 | 2000-01-01 00:00:00 | 2020-12-31 00:00:00 | 2021-01-01 00:00:00 | 2022-12-31 00:00:00 | 2023-01-01 00:00:00 | 2026-05-08 00:00:00 |

## Stability By Model

| group_value | runs | mean_sharpe | median_sharpe | min_sharpe | max_sharpe | std_sharpe | pct_sharpe_gt_0 | pct_beating_simple_momentum | pct_beating_current_production | pct_beating_phase4b | worst_case_max_drawdown | worst_case_cvar_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gru | 2 | 1.711 | 1.711 | 1.674 | 1.748 | 0.037 | 100.00% | 100.00% | 100.00% | 50.00% | -7.90% | -2.67% |
| lstm | 14 | 1.182 | 1.586 | 0.159 | 1.961 | 0.710 | 100.00% | 78.57% | 57.14% | 42.86% | -14.56% | -4.17% |
| tcn | 2 | 1.496 | 1.496 | 1.410 | 1.582 | 0.086 | 100.00% | 50.00% | 0.00% | 0.00% | -10.48% | -3.40% |

## Stability By Sequence Length

| group_value | runs | mean_sharpe | median_sharpe | min_sharpe | max_sharpe | std_sharpe | pct_sharpe_gt_0 | pct_beating_simple_momentum | pct_beating_current_production | pct_beating_phase4b | worst_case_max_drawdown | worst_case_cvar_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 13 | 2 | 1.833 | 1.833 | 1.704 | 1.961 | 0.128 | 100.00% | 100.00% | 100.00% | 50.00% | -7.45% | -3.12% |
| 26 | 16 | 1.206 | 1.525 | 0.159 | 1.956 | 0.659 | 100.00% | 75.00% | 50.00% | 37.50% | -14.56% | -4.17% |

## Stability By Seed

| group_value | runs | mean_sharpe | median_sharpe | min_sharpe | max_sharpe | std_sharpe | pct_sharpe_gt_0 | pct_beating_simple_momentum | pct_beating_current_production | pct_beating_phase4b | worst_case_max_drawdown | worst_case_cvar_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 14 | 1.148 | 1.496 | 0.159 | 1.961 | 0.685 | 100.00% | 78.57% | 50.00% | 28.57% | -14.56% | -4.17% |
| 1 | 2 | 1.794 | 1.794 | 1.774 | 1.815 | 0.021 | 100.00% | 100.00% | 100.00% | 100.00% | -10.36% | -3.00% |
| 2 | 2 | 1.654 | 1.654 | 1.468 | 1.839 | 0.185 | 100.00% | 50.00% | 50.00% | 50.00% | -10.78% | -3.18% |

## Walk-Forward Fold Performance

| group_value | runs | mean_sharpe | median_sharpe | min_sharpe | max_sharpe | std_sharpe | pct_sharpe_gt_0 | pct_beating_simple_momentum | pct_beating_current_production | pct_beating_phase4b | worst_case_max_drawdown | worst_case_cvar_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_a_2017_2018 | 2 | 0.187 | 0.187 | 0.159 | 0.214 | 0.028 | 100.00% | 100.00% | 0.00% | 0.00% | -9.56% | -2.45% |
| fold_b_2019_2020 | 2 | 0.339 | 0.339 | 0.190 | 0.487 | 0.148 | 100.00% | 0.00% | 0.00% | 0.00% | -14.56% | -4.17% |
| fold_c_2021_2022 | 2 | 0.638 | 0.638 | 0.607 | 0.669 | 0.031 | 100.00% | 100.00% | 50.00% | 50.00% | -8.53% | -3.39% |
| fold_d_2023_2026 | 12 | 1.720 | 1.729 | 1.410 | 1.961 | 0.164 | 100.00% | 83.33% | 75.00% | 50.00% | -10.78% | -3.40% |

## Best Bil-Fallback Runs

| fold_name | model_type | sequence_length | seed | top_n | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | average_bil_weight | beats_simple_momentum | beats_current_production | beats_phase4b |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_d_2023_2026 | lstm | 13 | 0 | 10 | 22.30% | 11.37% | 1.961 | -6.85% | 3.254 | -3.12% | 0.39623669763302016 | 17.14% | True | True | True |
| fold_d_2023_2026 | lstm | 26 | 0 | 10 | 23.11% | 11.81% | 1.956 | -8.68% | 2.663 | -3.19% | 0.36454672296721946 | 17.14% | True | True | True |
| fold_d_2023_2026 | lstm | 26 | 2 | 15 | 19.75% | 10.74% | 1.839 | -10.00% | 1.975 | -2.85% | 0.3135763605662201 | 17.14% | True | True | True |
| fold_d_2023_2026 | lstm | 26 | 1 | 10 | 20.53% | 11.31% | 1.815 | -10.36% | 1.981 | -3.00% | 0.3338074406868968 | 17.14% | True | True | True |
| fold_d_2023_2026 | lstm | 26 | 1 | 15 | 18.88% | 10.65% | 1.774 | -8.67% | 2.177 | -2.83% | 0.3235093760769336 | 17.14% | True | True | True |
| fold_d_2023_2026 | gru | 26 | 0 | 10 | 17.03% | 9.74% | 1.748 | -6.81% | 2.500 | -2.67% | 0.31540444519658445 | 17.14% | True | True | True |
| fold_d_2023_2026 | lstm | 26 | 0 | 15 | 18.09% | 10.58% | 1.710 | -9.29% | 1.948 | -2.65% | 0.3267451862677718 | 17.14% | True | True | False |
| fold_d_2023_2026 | lstm | 13 | 0 | 15 | 18.06% | 10.60% | 1.704 | -7.45% | 2.424 | -2.88% | 0.3416825105913328 | 17.14% | True | True | False |
| fold_d_2023_2026 | gru | 26 | 0 | 15 | 16.54% | 9.88% | 1.674 | -7.90% | 2.093 | -2.67% | 0.27338978495955996 | 17.14% | True | True | False |
| fold_d_2023_2026 | tcn | 26 | 0 | 10 | 18.51% | 11.70% | 1.582 | -8.24% | 2.246 | -3.40% | 0.39717314969952827 | 17.14% | True | False | False |
| fold_d_2023_2026 | lstm | 26 | 2 | 10 | 17.15% | 11.68% | 1.468 | -10.78% | 1.590 | -3.18% | 0.354246265577886 | 17.14% | False | False | False |
| fold_d_2023_2026 | tcn | 26 | 0 | 15 | 15.08% | 10.70% | 1.410 | -10.48% | 1.439 | -2.97% | 0.40474865063275534 | 17.14% | False | False | False |

## Worst Bil-Fallback Runs

| fold_name | model_type | sequence_length | seed | top_n | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | average_bil_weight | beats_simple_momentum | beats_current_production | beats_phase4b |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_a_2017_2018 | lstm | 26 | 0 | 10 | 1.24% | 7.80% | 0.159 | -8.09% | 0.153 | -2.45% | 0.3492232505239125 | 29.73% | True | False | False |
| fold_b_2019_2020 | lstm | 26 | 0 | 10 | 2.36% | 12.39% | 0.190 | -14.56% | 0.162 | -4.17% | 0.35632251663776976 | 27.41% | False | False | False |
| fold_a_2017_2018 | lstm | 26 | 0 | 15 | 1.41% | 6.59% | 0.214 | -9.56% | 0.148 | -2.12% | 0.2901776098841721 | 29.72% | True | False | False |
| fold_b_2019_2020 | lstm | 26 | 0 | 15 | 5.81% | 11.93% | 0.487 | -12.35% | 0.471 | -3.78% | 0.3242506145019131 | 28.07% | False | False | False |
| fold_c_2021_2022 | lstm | 26 | 0 | 10 | 6.92% | 11.41% | 0.607 | -8.53% | 0.811 | -3.39% | 0.2603771371224245 | 34.76% | True | False | False |
| fold_c_2021_2022 | lstm | 26 | 0 | 15 | 7.03% | 10.50% | 0.669 | -6.36% | 1.105 | -2.94% | 0.23809174551591633 | 34.76% | True | True | True |
| fold_d_2023_2026 | tcn | 26 | 0 | 15 | 15.08% | 10.70% | 1.410 | -10.48% | 1.439 | -2.97% | 0.40474865063275534 | 17.14% | False | False | False |
| fold_d_2023_2026 | lstm | 26 | 2 | 10 | 17.15% | 11.68% | 1.468 | -10.78% | 1.590 | -3.18% | 0.354246265577886 | 17.14% | False | False | False |

## Benchmark Comparison

| fold_name | benchmark_name | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_a_2017_2018 | 60_40 | 5.39% | 7.86% | 0.686 | -9.33% | 0.578 | -2.95% | 0.0 |
| fold_a_2017_2018 | MLX3_best_tabular | 7.30% | 14.58% | 0.501 | -24.14% | 0.303 | -4.67% | 0.515636614049448 |
| fold_a_2017_2018 | MLX4_best_MLP | -0.17% | 12.74% | -0.013 | -22.01% | -0.008 | -4.34% | 0.43045365339140973 |
| fold_a_2017_2018 | MLX5_original_best | 4.74% | 8.92% | 0.532 | -12.96% | 0.366 | -2.84% | 0.2930896522860714 |
| fold_a_2017_2018 | SPY | 7.42% | 13.40% | 0.554 | -17.08% | 0.434 | -5.08% | 0.0 |
| fold_a_2017_2018 | current_production | 5.38% | 6.56% | 0.820 | -8.14% | 0.661 | -2.25% | 0.05494299006010771 |
| fold_a_2017_2018 | official_shadow | 5.44% | 6.66% | 0.817 | -8.24% | 0.660 | -2.29% | 0.05520889475962038 |
| fold_a_2017_2018 | phase4b | 4.84% | 6.26% | 0.773 | -9.20% | 0.526 | -2.15% | 0.06798808867281371 |
| fold_a_2017_2018 | phase6 | 5.12% | 6.74% | 0.760 | -9.08% | 0.564 | -2.28% | 0.06668797414215853 |
| fold_a_2017_2018 | phase7 | 5.24% | 6.79% | 0.771 | -9.16% | 0.572 | -2.29% | 0.06785833125049884 |
| fold_a_2017_2018 | simple_momentum | -0.47% | 13.42% | -0.035 | -23.12% | -0.020 | -4.84% | 0.3752296018457706 |
| fold_b_2019_2020 | 60_40 | 18.71% | 13.59% | 1.377 | -18.32% | 1.021 | -4.62% | 0.0 |
| fold_b_2019_2020 | MLX3_best_tabular | 11.90% | 26.25% | 0.453 | -37.62% | 0.316 | -8.67% | 0.5343416855999578 |
| fold_b_2019_2020 | MLX4_best_MLP | 12.55% | 25.63% | 0.490 | -31.12% | 0.403 | -8.03% | 0.5032114103733547 |
| fold_b_2019_2020 | MLX5_original_best | 7.45% | 12.64% | 0.590 | -11.34% | 0.657 | -3.86% | 0.35051822884638895 |
| fold_b_2019_2020 | SPY | 24.00% | 23.47% | 1.023 | -31.83% | 0.754 | -8.10% | 0.0 |
| fold_b_2019_2020 | current_production | 6.85% | 9.69% | 0.707 | -13.98% | 0.490 | -3.64% | 0.050338607801271903 |
| fold_b_2019_2020 | official_shadow | 6.96% | 9.55% | 0.729 | -13.67% | 0.509 | -3.59% | 0.050551659927294205 |
| fold_b_2019_2020 | phase4b | 9.64% | 10.42% | 0.925 | -12.44% | 0.775 | -3.63% | 0.07425321524950773 |
| fold_b_2019_2020 | phase6 | 8.42% | 10.94% | 0.770 | -13.77% | 0.612 | -3.95% | 0.07899260703092728 |
| fold_b_2019_2020 | phase7 | 8.50% | 10.94% | 0.778 | -13.83% | 0.615 | -3.96% | 0.07718525574603204 |
| fold_b_2019_2020 | simple_momentum | 13.25% | 20.13% | 0.658 | -27.84% | 0.476 | -7.19% | 0.43622977840299587 |
| fold_c_2021_2022 | 60_40 | -1.00% | 12.00% | -0.083 | -20.76% | -0.048 | -3.35% | 0.0 |
| fold_c_2021_2022 | MLX3_best_tabular | 14.97% | 17.90% | 0.836 | -10.87% | 1.377 | -4.93% | 0.6264401779979252 |
| fold_c_2021_2022 | MLX4_best_MLP | 14.24% | 16.54% | 0.861 | -11.73% | 1.214 | -4.50% | 0.4035191590330951 |
| fold_c_2021_2022 | MLX5_original_best | 5.12% | 11.78% | 0.435 | -8.07% | 0.634 | -3.35% | 0.25315429539642237 |
| fold_c_2021_2022 | SPY | 3.35% | 18.41% | 0.182 | -23.93% | 0.140 | -4.98% | 0.0 |
| fold_c_2021_2022 | current_production | 4.91% | 7.65% | 0.642 | -4.57% | 1.075 | -2.30% | 0.05124417523000562 |
| fold_c_2021_2022 | official_shadow | 4.79% | 7.63% | 0.628 | -4.56% | 1.052 | -2.32% | 0.05164439734094103 |
| fold_c_2021_2022 | phase4b | 4.80% | 7.40% | 0.648 | -6.79% | 0.707 | -2.14% | 0.07485618687993946 |
| fold_c_2021_2022 | phase6 | 5.53% | 7.62% | 0.726 | -6.78% | 0.816 | -2.21% | 0.06778241008041849 |
| fold_c_2021_2022 | phase7 | 5.33% | 7.57% | 0.705 | -6.82% | 0.782 | -2.21% | 0.06849814506875608 |
| fold_c_2021_2022 | simple_momentum | 4.93% | 15.72% | 0.313 | -11.79% | 0.418 | -4.16% | 0.3931133245045052 |
| fold_d_2023_2026 | 60_40 | 14.36% | 9.19% | 1.563 | -9.02% | 1.591 | -2.28% | 0.005714285714285714 |
| fold_d_2023_2026 | MLX3_best_tabular | 20.96% | 16.19% | 1.295 | -17.68% | 1.185 | -4.69% | 0.6109792054425199 |
| fold_d_2023_2026 | MLX4_best_MLP | 22.34% | 15.13% | 1.477 | -12.60% | 1.773 | -4.62% | 0.4319949163821682 |
| fold_d_2023_2026 | MLX5_original_best | 16.13% | 11.04% | 1.460 | -7.74% | 2.084 | -3.17% | 0.3734943281814599 |
| fold_d_2023_2026 | SPY | 22.52% | 14.30% | 1.574 | -16.88% | 1.334 | -3.83% | 0.005714285714285714 |
| fold_d_2023_2026 | current_production | 12.36% | 7.56% | 1.636 | -6.26% | 1.974 | -2.06% | 0.060168460963774345 |
| fold_d_2023_2026 | official_shadow | 12.29% | 7.50% | 1.639 | -6.24% | 1.970 | -2.05% | 0.06088614663181226 |

## Skipped Runs

- fold_a_2017_2018 lstm seq13 seed0: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_a_2017_2018 lstm seq13 seed1: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_a_2017_2018 lstm seq13 seed2: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_a_2017_2018 lstm seq26 seed1: skipped by bounded MLX-5C grid
- fold_a_2017_2018 lstm seq26 seed2: skipped by bounded MLX-5C grid
- fold_a_2017_2018 lstm seq52 seed0: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 lstm seq52 seed1: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 lstm seq52 seed2: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 gru seq13 seed0: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_a_2017_2018 gru seq13 seed1: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 gru seq13 seed2: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 gru seq26 seed0: skipped by bounded MLX-5C grid
- fold_a_2017_2018 gru seq26 seed1: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 gru seq26 seed2: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 gru seq52 seed0: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 gru seq52 seed1: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 gru seq52 seed2: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 tcn seq13 seed0: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_a_2017_2018 tcn seq13 seed1: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 tcn seq13 seed2: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 tcn seq26 seed0: skipped by bounded MLX-5C grid
- fold_a_2017_2018 tcn seq26 seed1: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 tcn seq26 seed2: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_a_2017_2018 tcn seq52 seed0: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 tcn seq52 seed1: skipped 52-week sequence grid for bounded CPU runtime
- fold_a_2017_2018 tcn seq52 seed2: skipped 52-week sequence grid for bounded CPU runtime
- fold_b_2019_2020 lstm seq13 seed0: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_b_2019_2020 lstm seq13 seed1: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_b_2019_2020 lstm seq13 seed2: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_b_2019_2020 lstm seq26 seed1: skipped by bounded MLX-5C grid
- fold_b_2019_2020 lstm seq26 seed2: skipped by bounded MLX-5C grid
- fold_b_2019_2020 lstm seq52 seed0: skipped 52-week sequence grid for bounded CPU runtime
- fold_b_2019_2020 lstm seq52 seed1: skipped 52-week sequence grid for bounded CPU runtime
- fold_b_2019_2020 lstm seq52 seed2: skipped 52-week sequence grid for bounded CPU runtime
- fold_b_2019_2020 gru seq13 seed0: skipped non-primary 13-week seed/model expansion for bounded CPU runtime
- fold_b_2019_2020 gru seq13 seed1: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_b_2019_2020 gru seq13 seed2: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_b_2019_2020 gru seq26 seed0: skipped by bounded MLX-5C grid
- fold_b_2019_2020 gru seq26 seed1: skipped non-LSTM seed expansion for bounded CPU runtime
- fold_b_2019_2020 gru seq26 seed2: skipped non-LSTM seed expansion for bounded CPU runtime
- ... 59 additional bounded-grid skips recorded in JSON.

## Interpretation

The MLX-5 edge survives only if the average and worst-case rows above remain acceptable across folds, not merely because one 2020+ configuration looked good. If the average fold is weak but one fold is strong, this should stay research-only or ML-shadow at most. If the result remains positive across seeds and folds but does not reliably beat Phase 4B or production risk metrics, it is better framed as a possible offensive sleeve rather than a standalone strategy.

## Warnings

- 52-week sequence grid and full GRU/TCN seed expansion skipped for bounded CPU runtime.
- Experimental research-only Phase MLX output; not production-valid.
