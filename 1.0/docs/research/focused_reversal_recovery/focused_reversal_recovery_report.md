# Focused Reversal Recovery Research Report

> Standalone research experiment. Not production. No allocation logic was modified.

**Final verdict: `RESEARCH-ONLY`**

## Summary

Best default +5% candidate by Sharpe: `classifier_ridge_reversal`.
Best focused train IC family: `drawdown_reversal`.
Best default candidate Sharpe: 0.990 vs baseline 0.948.
Best default incremental Sharpe: 0.042; incremental CAGR: 0.21%.
Focused composite Sharpe: 0.946; random timing placebo Sharpe: 0.954; prior broad reference Sharpe: 0.952.
Options-readiness best candidate: `classifier_logistic_reversal`.

## Signal Scores

| Family/Candidate | Window | Rank IC | Precision Top Quintile | Failed Bounce | Crash Continuation | Avg Fwd 8w Top Quintile |
|---|---|---:|---:|---:|---:|---:|
| `short_horizon_reversal` | full | 0.080 | 60.32% | 7.03% | 18.59% | 3.08% |
| `short_horizon_reversal` | train | 0.071 | 59.80% | 6.70% | 18.11% | 2.79% |
| `short_horizon_reversal` | holdout | 0.179 | 69.23% | 7.69% | 23.08% | 6.24% |
| `drawdown_reversal` | full | 0.116 | 64.17% | 7.03% | 5.22% | 2.60% |
| `drawdown_reversal` | train | 0.102 | 62.53% | 7.44% | 5.46% | 2.22% |
| `drawdown_reversal` | holdout | 0.267 | 82.05% | 0.00% | 0.00% | 5.98% |
| `momentum_reversal_interaction` | full | 0.061 | 64.85% | 6.80% | 6.12% | 2.90% |
| `momentum_reversal_interaction` | train | 0.034 | 63.77% | 6.95% | 6.45% | 2.61% |
| `momentum_reversal_interaction` | holdout | 0.356 | 71.79% | 5.13% | 0.00% | 5.70% |
| `short_reversal_only` | full | 0.080 | 60.32% | 7.03% | 18.59% | 3.08% |
| `short_reversal_only` | train | 0.071 | 59.80% | 6.70% | 18.11% | 2.79% |
| `short_reversal_only` | holdout | 0.179 | 69.23% | 7.69% | 23.08% | 6.24% |
| `drawdown_recovery_only` | full | 0.116 | 64.17% | 7.03% | 5.22% | 2.60% |
| `drawdown_recovery_only` | train | 0.102 | 62.53% | 7.44% | 5.46% | 2.22% |
| `drawdown_recovery_only` | holdout | 0.267 | 82.05% | 0.00% | 0.00% | 5.98% |
| `pullback_in_uptrend` | full | -0.074 | 54.42% | 5.22% | 4.54% | 2.15% |
| `pullback_in_uptrend` | train | -0.059 | 54.84% | 4.96% | 4.71% | 2.26% |
| `pullback_in_uptrend` | holdout | -0.255 | 56.41% | 10.26% | 2.56% | 2.92% |
| `oversold_rebound_after_stress` | full | 0.034 | 53.74% | 6.35% | 1.36% | 2.03% |
| `oversold_rebound_after_stress` | train | 0.008 | 52.11% | 6.95% | 1.49% | 1.74% |
| `oversold_rebound_after_stress` | holdout | 0.318 | 74.36% | 0.00% | 0.00% | 5.49% |
| `momentum_reversal_interaction_score` | full | 0.061 | 64.85% | 6.80% | 6.12% | 2.90% |
| `momentum_reversal_interaction_score` | train | 0.034 | 63.77% | 6.95% | 6.45% | 2.61% |
| `momentum_reversal_interaction_score` | holdout | 0.356 | 71.79% | 5.13% | 0.00% | 5.70% |
| `focused_reversal_composite` | full | 0.143 | 63.72% | 7.71% | 14.06% | 2.96% |
| `focused_reversal_composite` | train | 0.117 | 61.79% | 7.94% | 14.14% | 2.59% |
| `focused_reversal_composite` | holdout | 0.407 | 79.49% | 5.13% | 15.38% | 7.57% |

## Filter Diagnostics

Average filter effect: precision delta -0.62%, failed-bounce delta 0.69%, crash-continuation delta -2.88%.

| Candidate | Window | Raw Rows | Filtered Rows | Precision Delta | Failed Delta | Crash Delta |
|---|---|---:|---:|---:|---:|---:|
| `short_reversal_only` | full | 401 | 401 | 0.00% | 0.00% | 0.00% |
| `drawdown_recovery_only` | full | 156 | 156 | 0.00% | 0.00% | 0.00% |
| `pullback_in_uptrend` | full | 310 | 143 | -0.45% | -0.27% | -3.33% |
| `oversold_rebound_after_stress` | full | 818 | 701 | -1.09% | 0.41% | -1.06% |
| `momentum_reversal_interaction_score` | full | 0 | 0 | n/a | n/a | n/a |
| `focused_reversal_composite` | full | 40 | 19 | -1.58% | 3.29% | -10.00% |

## ETF Tilt Backtests

| Candidate | Tilt | Sharpe | CAGR | MaxDD | CVaR 5% | Inc Sharpe | Inc CAGR | Ex Top 3 Sharpe | Holdout Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | 0.00% | 0.948 | 7.13% | -11.60% | -2.49% | 0.000 | 0.00% | n/a | n/a |
| `short_reversal_only` | 5.00% | 0.966 | 7.16% | -11.40% | -2.48% | 0.018 | 0.02% | 0.956 | 2.202 |
| `drawdown_recovery_only` | 5.00% | 0.962 | 7.24% | -11.60% | -2.49% | 0.014 | 0.10% | 0.953 | 2.223 |
| `pullback_in_uptrend` | 5.00% | 0.959 | 7.15% | -12.07% | -2.48% | 0.010 | 0.02% | 0.951 | 2.181 |
| `oversold_rebound_after_stress` | 5.00% | 0.971 | 7.23% | -11.60% | -2.47% | 0.023 | 0.10% | 0.964 | 2.202 |
| `momentum_reversal_interaction_score` | 5.00% | 0.948 | 7.13% | -11.60% | -2.49% | 0.000 | 0.00% | 0.948 | 2.179 |
| `focused_reversal_composite` | 5.00% | 0.946 | 7.12% | -11.60% | -2.49% | -0.003 | -0.02% | 0.941 | 2.179 |
| `classifier_logistic_reversal` | 5.00% | 0.967 | 7.17% | -11.84% | -2.46% | 0.019 | 0.04% | 0.955 | 2.241 |
| `classifier_ridge_reversal` | 5.00% | 0.990 | 7.35% | -11.40% | -2.46% | 0.042 | 0.21% | 0.979 | 2.260 |
| `random_timing_placebo` | 5.00% | 0.954 | 7.17% | -11.60% | -2.49% | 0.005 | 0.04% | 0.947 | 2.182 |
| `always_on_spy_qqq_tilt` | 5.00% | 1.051 | 7.51% | -11.83% | -2.38% | 0.103 | 0.38% | 1.041 | 2.329 |
| `broad_previous_best_reference` | 5.00% | 0.952 | 7.15% | -11.60% | -2.49% | 0.004 | 0.02% | 0.946 | 2.192 |

## Classifiers

| Model | Window | Precision | Base Rate | FPR | Risk-Off FPR | Failed Bounce |
|---|---|---:|---:|---:|---:|---:|
| `classifier_logistic_reversal` | train | 71.07% | 53.51% | 15.56% | 0.00% | 8.60% |
| `classifier_logistic_reversal` | holdout | 73.58% | 50.96% | 13.73% | 0.00% | 1.89% |
| `classifier_ridge_reversal` | train | 70.65% | 53.51% | 15.78% | 0.00% | 8.18% |
| `classifier_ridge_reversal` | holdout | 74.42% | 50.96% | 10.78% | 0.00% | 2.33% |

## Placebo Tests

| Test | Reference Sharpe | Placebo Mean Sharpe | Placebo P95 Sharpe | Placebo Beat Rate |
|---|---:|---:|---:|---:|
| `random_entry_same_frequency` | 0.946 | 0.950 | 0.956 | 87.00% |
| `block_bootstrap_weekly_returns` | 0.946 | 0.978 | 1.321 | 54.00% |

## Options-Readiness Diagnostic

No options strategy is implemented. This only checks whether the ETF signal
identifies forward moves large enough to justify future option-chain research.

| Candidate | Signals/Yr | Avg Fwd 8w | Ex Top 3 Avg 8w | Breakeven | Surplus | Status |
|---|---:|---:|---:|---:|---:|---|
| `short_reversal_only` | 18.786 | 3.16% | 2.96% | 4.50% | -1.34% | NOT READY |
| `drawdown_recovery_only` | 7.308 | 3.25% | 2.86% | 4.50% | -1.25% | NOT READY |
| `pullback_in_uptrend` | 6.699 | 2.85% | 2.58% | 4.50% | -1.65% | NOT READY |
| `oversold_rebound_after_stress` | 32.840 | 1.78% | 1.68% | 4.50% | -2.72% | NOT READY |
| `momentum_reversal_interaction_score` | 0.000 | n/a | n/a | 4.50% | n/a | NOT READY |
| `focused_reversal_composite` | 0.890 | 3.02% | 0.99% | 4.50% | -1.48% | NOT READY |
| `classifier_logistic_reversal` | 24.829 | 3.97% | 3.84% | 4.50% | -0.53% | NOT READY |
| `classifier_ridge_reversal` | 24.360 | 3.87% | 3.74% | 4.50% | -0.63% | NOT READY |

## Validation Gates

| # | Gate | Result | Detail |
|---:|---|---|---|
| 1 | `focused_signal_positive_ic_train_holdout` | PASS | stable positive families: ['drawdown_reversal', 'momentum_reversal_interaction', 'short_horizon_reversal'] |
| 2 | `focused_composite_improves_prior_broad_ic` | PASS | focused train rank IC 0.117, prior broad composite -0.020 |
| 3 | `precision_beats_base_rate` | PASS | best train precision 0.638, base 0.526 |
| 4 | `risk_off_false_positives_controlled` | PASS | best filtered crash rate 0.000, logistic holdout risk-off FPR 0.000 |
| 5 | `not_one_crisis_period` | PASS | best candidate classifier_ridge_reversal ex-top3 Sharpe 0.979 |
| 6 | `default_tilt_sharpe_improves_005` | FAIL | classifier_ridge_reversal incremental Sharpe 0.042 |
| 7 | `default_tilt_cagr_improves_0025` | FAIL | classifier_ridge_reversal incremental CAGR 0.0021 |
| 8 | `max_drawdown_not_worse_0025` | PASS | overlay -0.114, baseline -0.116 |
| 9 | `cvar5_not_worse` | PASS | overlay -0.0246, baseline -0.0249 |
| 10 | `cvar1_not_worse` | PASS | overlay -0.0374, baseline -0.0381 |
| 11 | `beats_random_placebo` | PASS | best 0.990, placebo 0.954 |
| 12 | `survives_best_signal_period` | PASS | ex-best 0.986 |
| 13 | `survives_top3_signal_periods` | PASS | ex-top3 0.979 |
| 14 | `holdout_performance_positive` | PASS | holdout Sharpe 2.260 |
| 15 | `turnover_reasonable` | PASS | avg weekly turnover 0.0147 |
| 16 | `not_one_subperiod` | PASS | positive subperiods 3/3 |
| 17 | `placebo_distribution_supports_signal` | FAIL | random placebo beat focused composite 87.0% of runs |
| 18 | `options_move_large_enough` | FAIL | best surplus -0.0053, ex-top3 avg 0.0384 |
| 19 | `options_signal_frequency_reasonable` | FAIL | signals/year 24.83 |
| 20 | `options_readiness_research_only_without_chains` | PASS | no real option-chain data tested |

## Required Answers

1. Did focused reversal research improve over broad recovery prediction? Focused composite Sharpe was 0.946 vs prior broad reference 0.952; the IC comparison is gate 2.
2. Which reversal candidate worked best? `classifier_ridge_reversal` by default +5% Sharpe.
3. Did short-horizon reversal remain the best family? Best focused train IC family was `drawdown_reversal`.
4. Did drawdown reversal help? Its train/holdout rank IC and backtest row are reported above; it is not assumed helpful unless it clears those rows.
5. Did momentum/reversal interaction help? Its standalone score and candidate rows are reported separately from the composite.
6. Did credit/vol filters reduce false positives? Average filter effect: precision delta -0.62%, failed-bounce delta 0.69%, crash-continuation delta -2.88%.
7. Did any candidate beat random timing placebo? Best default candidate Sharpe 0.990 vs placebo 0.954.
8. Did any candidate improve ETF baseline Sharpe by +0.05? Best incremental Sharpe was 0.042.
9. Did any candidate improve CAGR by +0.25%? Best incremental CAGR was 0.21%.
10. Did max drawdown and CVaR remain acceptable? Best default MaxDD -11.40% vs baseline -11.60%; CVaR 5% -2.46% vs baseline -2.49%.
11. Did results survive best/top-3 removal? Best ex-best Sharpe 0.986; ex-top3 0.979.
12. Did holdout performance remain positive? Best holdout Sharpe was 2.260.
13. Was options-readiness improved? Best readiness candidate was `classifier_logistic_reversal` with status `NOT READY`.
14. Should this be rejected, research-only, candidate for ETF re-risking, or candidate for future options testing? `RESEARCH-ONLY`.
15. What should be tried next? If not rejected, the next step is stricter walk-forward thresholding and cleaner funding simulation for the strongest single candidate; options should wait for real option-chain data.

## Verdict Explanation

The evidence has some research value, but portfolio or placebo gates remain too weak for candidacy. Key failed gates: default_tilt_sharpe_improves_005, default_tilt_cagr_improves_0025, placebo_distribution_supports_signal, options_move_large_enough, options_signal_frequency_reasonable.
