# Recovery Prediction Research Report

> Standalone research experiment. Not production. No allocation logic was modified.

**Final verdict: `RESEARCH-ONLY`**

## 1. Summary

Best train IC family: `short_horizon_reversal`.
Predeclared regime-gated composite Sharpe: 0.952 vs baseline 0.948.
Incremental CAGR: 0.02%; incremental Sharpe: 0.004.
Random placebo Sharpe: 0.961.

## 2. Family IC Scores

| Family | Window | Rank IC | Precision Top Quintile | Avg Fwd 8w Top Quintile |
|---|---|---:|---:|---:|
| `drawdown_reversal` | full | 0.011 | 44.60% | 2.01% |
| `drawdown_reversal` | train | 0.001 | 43.45% | 1.78% |
| `drawdown_reversal` | holdout | 0.130 | 58.00% | 4.64% |
| `short_horizon_reversal` | full | 0.032 | 40.15% | 2.05% |
| `short_horizon_reversal` | train | 0.021 | 39.19% | 1.99% |
| `short_horizon_reversal` | holdout | 0.161 | 50.75% | 2.69% |
| `breadth_thrust` | full | -0.061 | 37.56% | 2.09% |
| `breadth_thrust` | train | -0.058 | 36.63% | 2.07% |
| `breadth_thrust` | holdout | -0.078 | 45.00% | 1.30% |
| `credit_improvement` | full | -0.069 | 42.31% | 1.77% |
| `credit_improvement` | train | -0.070 | 42.08% | 1.73% |
| `credit_improvement` | holdout | -0.026 | 57.50% | 2.64% |
| `volatility_normalization` | full | -0.023 | 40.36% | 2.18% |
| `volatility_normalization` | train | -0.010 | 38.96% | 2.07% |
| `volatility_normalization` | holdout | -0.168 | 48.72% | 2.43% |
| `momentum_reversal_interaction` | full | 0.009 | 45.12% | 2.09% |
| `momentum_reversal_interaction` | train | 0.006 | 43.92% | 1.84% |
| `momentum_reversal_interaction` | holdout | 0.059 | 58.97% | 4.86% |

## 3. ETF Tilt Backtests

| Variant | Sharpe | CAGR | MaxDD | CVaR 5% | Activations/Yr | Ex Top 3 Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| `equal_weight_six_family_composite` | 0.950 | 7.14% | -11.60% | -2.49% | 0.515 | 0.946 |
| `regime_gated_composite` | 0.952 | 7.15% | -11.60% | -2.49% | 1.640 | 0.946 |
| `and_gated_drawdown_credit_vol` | 0.956 | 7.18% | -11.60% | -2.49% | 1.921 | 0.950 |
| `or_score_composite` | 0.974 | 7.23% | -12.07% | -2.47% | 6.980 | 0.967 |
| `momentum_reversal_interaction` | 0.948 | 7.13% | -11.60% | -2.49% | 0.000 | 0.948 |
| `classifier_logistic_l2` | 0.986 | 7.32% | -11.40% | -2.48% | 4.497 | 0.976 |
| `classifier_ridge_probability` | 0.985 | 7.32% | -11.40% | -2.47% | 4.404 | 0.975 |
| `random_timing_placebo` | 0.961 | 7.22% | -11.60% | -2.49% | 3.795 | 0.953 |

## 4. Classifiers

Best holdout classifier by top-quartile precision: `logistic_l2`.

| Model | Window | Precision | Recall | False Positive Rate | Risk-Off FPR |
|---|---|---:|---:|---:|---:|
| `logistic_l2` | train | 54.47% | 33.79% | 19.10% | 26.28% |
| `logistic_l2` | holdout | 36.54% | 22.89% | 26.40% | 3.57% |
| `ridge_probability` | train | 54.47% | 33.79% | 19.10% | 27.21% |
| `ridge_probability` | holdout | 34.62% | 21.69% | 27.20% | 7.14% |

## 5. Options-Readiness Diagnostic

No options strategy is tested here. This only asks whether ETF recovery signals
identify moves that might later justify real option-chain testing.

Best readiness variant: `equal_weight_six_family_composite`.

| Variant | Signals/Yr | Avg Fwd 8w | Rough Breakeven | Surplus | Status |
|---|---:|---:|---:|---:|---|
| `equal_weight_six_family_composite` | 1.077 | 4.22% | 4.50% | -0.28% | NOT READY |
| `regime_gated_composite` | 4.076 | 2.43% | 4.50% | -2.07% | NOT READY |
| `and_gated_drawdown_credit_vol` | 5.903 | 2.41% | 4.50% | -2.09% | NOT READY |
| `momentum_reversal_interaction` | 0.000 | n/a | 4.50% | n/a | NOT READY |

## 6. Validation Gates

| # | Gate | Result | Detail |
|---:|---|---|---|
| 1 | `signal_family_positive_ic_train_holdout` | PASS | stable positive families: ['drawdown_reversal', 'momentum_reversal_interaction', 'short_horizon_reversal'] |
| 2 | `combined_signal_improves_ic` | FAIL | equal-weight train rank IC -0.034, best family 0.021 |
| 3 | `not_one_crisis_period` | FAIL | ex-top3 Sharpe 0.946 vs baseline 0.948 |
| 4 | `enough_activations` | PASS | 87 signal rows |
| 5 | `precision_better_than_base_rate` | PASS | best precision 0.439, base 0.403 |
| 6 | `risk_off_false_positives_controlled` | PASS | logistic holdout risk-off FPR 0.036 |
| 7 | `tilt_sharpe_improves_005` | FAIL | incremental Sharpe 0.004 |
| 8 | `tilt_cagr_improves_0025` | FAIL | incremental CAGR 0.0002 |
| 9 | `drawdown_not_worse_0025` | PASS | overlay -0.116, baseline -0.116 |
| 10 | `cvar5_not_worse` | PASS | overlay -0.0249, baseline -0.0249 |
| 11 | `cvar1_not_worse` | PASS | overlay -0.0380, baseline -0.0381 |
| 12 | `survives_best_signal_period` | PASS | ex-best 0.950 |
| 13 | `survives_top3_signal_periods` | FAIL | ex-top3 0.946 |
| 14 | `holdout_performance_positive` | PASS | holdout Sharpe 2.192 |
| 15 | `beats_random_placebo` | FAIL | signal 0.952, placebo 0.961 |
| 16 | `turnover_reasonable` | PASS | avg weekly turnover 0.0033 |
| 17 | `not_purely_2020_or_one_rebound` | PASS | activations/year 1.64, avg length 1.6 |
| 18 | `options_move_large_enough` | FAIL | best avg 8w surplus -0.0028 |
| 19 | `options_signal_frequency_reasonable` | PASS | max signals/year 5.90 |
| 20 | `options_readiness_research_only` | PASS | proxy-only diagnostic; no option-chain conclusion |

## 7. Answers

1. Best family: `short_horizon_reversal` by train rank IC.
2. Failed families are visible in the IC table where train/holdout rank IC is weak or unstable.
3. Stable IC requires positive train and holdout IC; see validation gate 1.
4. Combination improvement is checked by gate 2.
5. Classifiers did not automatically dominate simple rules; best holdout classifier was `logistic_l2`.
6. Portfolio impact: regime-gated composite Sharpe 0.952 vs baseline 0.948.
7. Sharpe/CAGR/drawdown/CVaR are reported in the ETF tilt table and gates.
8. Random timing placebo Sharpe was 0.961.
9. Best/top-3 signal period robustness is checked by gates 12 and 13.
10. Fake-bounce labels are included in targets and classifier prediction diagnostics.
11. Options-readiness is diagnostic only and remains proxy research.
12. Status: `RESEARCH-ONLY`.
13. Next: investigate the highest-stability signals with stricter point-in-time data and only then consider real option-chain testing.
