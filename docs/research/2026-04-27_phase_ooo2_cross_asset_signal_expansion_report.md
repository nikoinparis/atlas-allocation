# Phase OOO2 — Cross-Asset Signal Expansion and Validation

Date: 2026-04-27

## Commands executed
```
git status --short
sed -n '1,180p' docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md
find data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery -maxdepth 1 -type f | sort
find data/02_layer1_signals -maxdepth 1 -type f | sort | sed -n '1,80p'
tail -n 70 docs/research/project_journey.md
python3 scripts/phase_ooo2_cross_asset_signal_expansion.py
```

## Files created / modified
- `scripts/phase_ooo2_cross_asset_signal_expansion.py`
- `data/research/phase_ooo_signal_discovery/ooo2_cross_asset_signal_expansion/*.csv`
- `docs/research/2026-04-27_phase_ooo2_cross_asset_signal_expansion_report.md`
- `docs/research/project_journey.md`

## OOO1 shortlist used
OOO2 started from OOO1's cross-asset lead-lag, breadth/state-interaction, and
regime-risk shortlist. Portfolio candidates were not created.

## Candidate signal designs
| signal_name | source_feature | expected_use | states_where_it_may_matter | source_ooo1_discovery_score |
| --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal | leadlag_EFA_minus_SPY_13w | risk confirmation | neutral_mixed|recovery_confirmed|calm_trend | 2.997500 |
| leadlag_GLD_minus_SPY_13w_signal | leadlag_GLD_minus_SPY_13w | risk confirmation | stressed_panic|neutral_mixed | 2.915000 |
| leadlag_DBA_minus_SPY_13w_signal | leadlag_DBA_minus_SPY_13w | risk confirmation | neutral_mixed|calm_trend | 2.920000 |
| leadlag_HYG_minus_LQD_13w_signal | leadlag_HYG_minus_LQD_13w | risk confirmation | calm_trend|recovery_confirmed | 2.520000 |
| breadth_ret13_positive_signal | breadth_ret13_positive | gate | all | 2.567500 |
| breadth_ret26_positive_signal | breadth_ret26_positive | gate | all | 2.837500 |
| canary_breadth_pair_signal | regime_canary_breadth_pair | risk confirmation | all | 2.927500 |
| recent_stress_26w_signal | regime_recent_stress_26w | risk confirmation | stressed_panic|recovery_fragile | 3.047500 |
| market_drawdown_signal | regime_market_drawdown | risk confirmation | stressed_panic|recovery_fragile | 3.195000 |
| market_trend_positive_signal | regime_market_trend_positive | gate | calm_trend|neutral_mixed | 2.805000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | breadth_ret13_positive_x_state_recovery_confirmed | state quality | recovery_confirmed | 2.877500 |
| breadth_ret13_positive_x_neutral_mixed_signal | breadth_ret13_positive_x_state_neutral_mixed | state quality | neutral_mixed | 3.102500 |
| breadth_ret13_positive_x_stressed_panic_signal | breadth_ret13_positive_x_state_stressed_panic | state quality | stressed_panic | 3.042500 |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | leadlag_HYG_minus_LQD_13w_x_state_calm_trend | state quality | calm_trend | 2.817500 |

## Signal construction summary
| signal_name | start_date | end_date | missingness | causal_ok | next_validation_stage |
| --- | --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal | 2005-02-18 | 2026-04-10 | 0.005405 | True | OOO2 validation |
| leadlag_GLD_minus_SPY_13w_signal | 2005-02-18 | 2026-04-10 | 0.005405 | True | OOO2 validation |
| leadlag_DBA_minus_SPY_13w_signal | 2005-02-18 | 2026-04-10 | 0.005405 | True | OOO2 validation |
| leadlag_HYG_minus_LQD_13w_signal | 2005-02-18 | 2026-04-10 | 0.005405 | True | OOO2 validation |
| breadth_ret13_positive_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| breadth_ret26_positive_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| canary_breadth_pair_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| recent_stress_26w_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| market_drawdown_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| market_trend_positive_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| breadth_ret13_positive_x_recovery_confirmed_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| breadth_ret13_positive_x_neutral_mixed_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| breadth_ret13_positive_x_stressed_panic_signal | 2005-01-14 | 2026-04-10 | 0.000901 | True | OOO2 validation |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | 2005-02-18 | 2026-04-10 | 0.005405 | True | OOO2 validation |

## Missing signal sources
_No rows._

## IC / validation summary
| signal_name | target_group | target | horizon_weeks | mean_ic | holdout_mean_ic_2016_forward | n_entities | t_stat_method |
| --- | --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_stressed_panic_signal | MARKET | fwd_stress_transition_4w | 4.000000 | 0.685368 | 0.738026 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| market_trend_positive_signal | MARKET | fwd_stress_transition_4w | 4.000000 | -0.544889 | -0.672095 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret13_positive_signal | MARKET | fwd_stress_transition_4w | 4.000000 | -0.487550 | -0.541515 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret26_positive_signal | MARKET | fwd_stress_transition_4w | 4.000000 | -0.486793 | -0.526447 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| recent_stress_26w_signal | MARKET | fwd_stress_transition_4w | 4.000000 | 0.453769 | 0.391225 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| leadlag_GLD_minus_SPY_13w_signal | MARKET | fwd_stress_transition_4w | 4.000000 | 0.385839 | 0.378720 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| market_drawdown_signal | MARKET | fwd_stress_transition_4w | 4.000000 | -0.375470 | -0.550490 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| leadlag_DBA_minus_SPY_13w_signal | MARKET | fwd_stress_transition_4w | 4.000000 | 0.366922 | 0.352316 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| leadlag_HYG_minus_LQD_13w_signal | MARKET | fwd_stress_transition_4w | 4.000000 | -0.222635 | -0.070402 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret13_positive_x_neutral_mixed_signal | MARKET | fwd_stress_transition_4w | 4.000000 | -0.220058 | -0.198381 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| canary_breadth_pair_signal | MARKET | fwd_drawdown_worsening_4w | 4.000000 | 0.217843 | 0.278391 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | fwd_ggg1_risk_adj_8w | 8.000000 | 0.180960 | 0.281907 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret26_positive_signal | MARKET | fwd_drawdown_worsening_4w | 4.000000 | 0.178130 | 0.255521 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret26_positive_signal | MARKET | fwd_ggg1_return_13w | 13.000000 | 0.173747 | 0.111793 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | fwd_ggg1_return_8w | 8.000000 | 0.173060 | 0.276868 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret26_positive_signal | MARKET | state_quality_good_4w | 4.000000 | 0.167370 | 0.115980 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | fwd_ggg1_risk_adj_13w | 13.000000 | 0.160247 | 0.271052 | 1.000000 | time-series Spearman/Pearson; no fitted model |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | fwd_ggg1_return_13w | 13.000000 | 0.155695 | 0.267832 | 1.000000 | time-series Spearman/Pearson; no fitted model |

## IC decay by horizon
| signal_name | horizon_weeks | mean_ic | holdout_mean_ic_2016_forward | positive_entity_share |
| --- | --- | --- | --- | --- |
| breadth_ret13_positive_signal | 1.000000 | -0.003692 | -0.016484 | 0.428571 |
| breadth_ret13_positive_signal | 4.000000 | -0.007643 | -0.027640 | 0.428571 |
| breadth_ret13_positive_signal | 8.000000 | -0.017888 | -0.041489 | 0.314286 |
| breadth_ret13_positive_signal | 13.000000 | 0.002782 | -0.019869 | 0.485714 |
| breadth_ret13_positive_x_neutral_mixed_signal | 1.000000 | 0.027785 | 0.018207 | 0.771429 |
| breadth_ret13_positive_x_neutral_mixed_signal | 4.000000 | 0.018429 | 0.006157 | 0.628571 |
| breadth_ret13_positive_x_neutral_mixed_signal | 8.000000 | 0.005629 | -0.017074 | 0.514286 |
| breadth_ret13_positive_x_neutral_mixed_signal | 13.000000 | 0.000437 | -0.032866 | 0.542857 |
| breadth_ret13_positive_x_recovery_confirmed_signal | 1.000000 | -0.007927 | -0.012278 | 0.371429 |
| breadth_ret13_positive_x_recovery_confirmed_signal | 4.000000 | 0.015419 | 0.019526 | 0.771429 |
| breadth_ret13_positive_x_recovery_confirmed_signal | 8.000000 | 0.035583 | 0.057260 | 0.857143 |
| breadth_ret13_positive_x_recovery_confirmed_signal | 13.000000 | 0.036768 | 0.067137 | 0.800000 |
| breadth_ret13_positive_x_stressed_panic_signal | 1.000000 | 0.006834 | 0.003207 | 0.542857 |
| breadth_ret13_positive_x_stressed_panic_signal | 4.000000 | 0.004926 | 0.021258 | 0.571429 |
| breadth_ret13_positive_x_stressed_panic_signal | 8.000000 | 0.021035 | 0.056310 | 0.657143 |
| breadth_ret13_positive_x_stressed_panic_signal | 13.000000 | 0.019730 | 0.071361 | 0.571429 |
| breadth_ret26_positive_signal | 1.000000 | 0.002669 | -0.013819 | 0.400000 |
| breadth_ret26_positive_signal | 4.000000 | -0.011411 | -0.048986 | 0.285714 |
| breadth_ret26_positive_signal | 8.000000 | -0.014411 | -0.060401 | 0.285714 |
| breadth_ret26_positive_signal | 13.000000 | -0.000073 | -0.044952 | 0.457143 |

## State-specific behavior
| signal_name | target_group | market_state | horizon_weeks | mean_ic | n_entities |
| --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | recovery_confirmed | 4.000000 | 0.448641 | 1.000000 |
| canary_breadth_pair_signal | MARKET | recovery_confirmed | 13.000000 | 0.418136 | 1.000000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | recovery_confirmed | 4.000000 | 0.402823 | 1.000000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | recovery_confirmed | 8.000000 | 0.398091 | 1.000000 |
| market_drawdown_signal | MARKET | recovery_fragile | 13.000000 | -0.397294 | 1.000000 |
| breadth_ret26_positive_signal | MARKET | recovery_confirmed | 13.000000 | 0.391989 | 1.000000 |
| market_drawdown_signal | MARKET | recovery_fragile | 13.000000 | -0.372373 | 1.000000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | recovery_confirmed | 4.000000 | 0.371830 | 1.000000 |
| market_drawdown_signal | SLEEVE_forward_returns | recovery_fragile | 13.000000 | -0.364509 | 6.000000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | recovery_confirmed | 4.000000 | 0.364100 | 1.000000 |
| market_drawdown_signal | MARKET | recovery_fragile | 13.000000 | -0.339589 | 1.000000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | MARKET | recovery_confirmed | 8.000000 | 0.336974 | 1.000000 |
| canary_breadth_pair_signal | MARKET | recovery_confirmed | 13.000000 | 0.334439 | 1.000000 |
| market_drawdown_signal | MARKET | recovery_confirmed | 4.000000 | -0.331511 | 1.000000 |
| breadth_ret13_positive_x_neutral_mixed_signal | MARKET | recovery_confirmed | 4.000000 | -0.327201 | 1.000000 |
| breadth_ret13_positive_x_neutral_mixed_signal | MARKET | recovery_confirmed | 4.000000 | -0.321280 | 1.000000 |
| leadlag_DBA_minus_SPY_13w_signal | MARKET | recovery_confirmed | 4.000000 | 0.320447 | 1.000000 |
| breadth_ret13_positive_x_recovery_confirmed_signal | SLEEVE_forward_returns | recovery_confirmed | 4.000000 | 0.317416 | 6.000000 |

## Redundancy / incrementality
| signal_name | avg_abs_redundancy_ooo2 | max_abs_redundancy_ooo2 | avg_abs_corr_existing_layer1 | max_abs_corr_existing_layer1 | cluster_label |
| --- | --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal | 0.088569 | 0.283320 | 0.045451 | 0.157081 | LOW_TO_MODERATE_REDUNDANCY |
| leadlag_GLD_minus_SPY_13w_signal | 0.255100 | 0.559813 | 0.056969 | 0.245631 | LOW_TO_MODERATE_REDUNDANCY |
| leadlag_DBA_minus_SPY_13w_signal | 0.219024 | 0.559813 | 0.041794 | 0.355975 | LOW_TO_MODERATE_REDUNDANCY |
| leadlag_HYG_minus_LQD_13w_signal | 0.159075 | 0.437005 | 0.054149 | 0.238434 | LOW_TO_MODERATE_REDUNDANCY |
| breadth_ret13_positive_signal | 0.299858 | 0.636189 | 0.107454 | 0.792652 | LOW_TO_MODERATE_REDUNDANCY |
| breadth_ret26_positive_signal | 0.300446 | 0.636189 | 0.129866 | 0.761048 | LOW_TO_MODERATE_REDUNDANCY |
| canary_breadth_pair_signal | 0.116649 | 0.383360 | 0.161871 | 0.463168 | LOW_TO_MODERATE_REDUNDANCY |
| recent_stress_26w_signal | 0.209769 | 0.516704 | 0.097345 | 0.589503 | LOW_TO_MODERATE_REDUNDANCY |
| market_drawdown_signal | 0.262170 | 0.544504 | 0.230576 | 0.564918 | LOW_TO_MODERATE_REDUNDANCY |
| market_trend_positive_signal | 0.330802 | 0.632300 | 0.139651 | 0.512702 | LOW_TO_MODERATE_REDUNDANCY |
| breadth_ret13_positive_x_recovery_confirmed_signal | 0.114346 | 0.215693 | 0.077053 | 0.182345 | LOW_TO_MODERATE_REDUNDANCY |
| breadth_ret13_positive_x_neutral_mixed_signal | 0.148031 | 0.424479 | 0.041783 | 0.190865 | LOW_TO_MODERATE_REDUNDANCY |
| breadth_ret13_positive_x_stressed_panic_signal | 0.316735 | 0.587658 | 0.112270 | 0.472013 | LOW_TO_MODERATE_REDUNDANCY |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | 0.093877 | 0.437005 | 0.034071 | 0.102982 | LOW_TO_MODERATE_REDUNDANCY |

## Keep / reject decisions
| signal_name | decision | incremental_signal_score | best_abs_ic | best_holdout_abs_ic | best_state_abs_ic | redundancy_penalty |
| --- | --- | --- | --- | --- | --- | --- |
| market_drawdown_signal | KEEP_HIGH_PRIORITY | 3.642857 | 0.375470 | 0.550490 | 0.397294 | 0.262170 |
| breadth_ret13_positive_x_stressed_panic_signal | KEEP_STATE_SPECIFIC | 3.464286 | 0.685368 | 0.738026 | 0.309848 | 0.316735 |
| recent_stress_26w_signal | KEEP_HIGH_PRIORITY | 2.964286 | 0.453769 | 0.391225 | 0.248108 | 0.209769 |
| breadth_ret26_positive_signal | KEEP_HIGH_PRIORITY | 2.928571 | 0.486793 | 0.526447 | 0.391989 | 0.300446 |
| breadth_ret13_positive_x_neutral_mixed_signal | KEEP_STATE_SPECIFIC | 2.857143 | 0.220058 | 0.198381 | 0.327201 | 0.148031 |
| market_trend_positive_signal | KEEP_HIGH_PRIORITY | 2.785714 | 0.544889 | 0.672095 | 0.313003 | 0.330802 |
| canary_breadth_pair_signal | KEEP_HIGH_PRIORITY | 2.785714 | 0.217843 | 0.314692 | 0.418136 | 0.161871 |
| breadth_ret13_positive_x_recovery_confirmed_signal | KEEP_STATE_SPECIFIC | 2.607143 | 0.180960 | 0.281907 | 0.448641 | 0.114346 |
| breadth_ret13_positive_signal | KEEP_FOR_TRIPLE_BARRIER_VALIDATION | 2.178571 | 0.487550 | 0.541515 | 0.209446 | 0.299858 |
| leadlag_DBA_minus_SPY_13w_signal | KEEP_FOR_TRIPLE_BARRIER_VALIDATION | 2.142857 | 0.366922 | 0.352316 | 0.320447 | 0.219024 |
| leadlag_GLD_minus_SPY_13w_signal | KEEP_FOR_TRIPLE_BARRIER_VALIDATION | 1.821429 | 0.385839 | 0.378720 | 0.243537 | 0.255100 |
| leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_TRIPLE_BARRIER_VALIDATION | 1.392857 | 0.076487 | 0.103025 | 0.249169 | 0.088569 |
| leadlag_HYG_minus_LQD_13w_signal | KEEP_FOR_TRIPLE_BARRIER_VALIDATION | 1.250000 | 0.222635 | 0.132751 | 0.314643 | 0.159075 |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | KEEP_STATE_SPECIFIC | 0.928571 | 0.101718 | 0.157039 | 0.224888 | 0.093877 |

## Top 5 signals to test next
| signal_name | decision | assigned_next_phase | incremental_signal_score |
| --- | --- | --- | --- |
| market_drawdown_signal | KEEP_HIGH_PRIORITY | OOO6 GGG1 portfolio pass-through after OOO3/OOO5 | 3.642857 |
| breadth_ret13_positive_x_stressed_panic_signal | KEEP_STATE_SPECIFIC | OOO5 triple-barrier/meta-label validation | 3.464286 |
| recent_stress_26w_signal | KEEP_HIGH_PRIORITY | OOO6 GGG1 portfolio pass-through after OOO3/OOO5 | 2.964286 |
| breadth_ret26_positive_signal | KEEP_HIGH_PRIORITY | OOO6 GGG1 portfolio pass-through after OOO3/OOO5 | 2.928571 |
| breadth_ret13_positive_x_neutral_mixed_signal | KEEP_STATE_SPECIFIC | OOO5 triple-barrier/meta-label validation | 2.857143 |

## How OOO2 feeds OOO3, OOO5, and OOO6
OOO2 only validates explicit signals. Surviving state-specific/risk signals
should go to OOO5 triple-barrier/meta-label validation before portfolio
pass-through. Signals that need sizing polish should go to OOO3. Only after
OOO3/OOO5 should any signal enter OOO6 GGG1 pass-through.

## Final recommendation
**PROCEED_TO_OOO5_TRIPLE_BARRIER_VALIDATION**

Reason: OOO2 produced surviving explicit signals with validation evidence.

## Exact prompt outline for next phase
Use the OOO2 signal queue to run triple-barrier/meta-label validation and/or volatility-managed sizing before any GGG1 portfolio pass-through.
