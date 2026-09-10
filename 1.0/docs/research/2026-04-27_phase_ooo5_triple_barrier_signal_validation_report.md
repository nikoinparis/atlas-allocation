# Phase OOO5 -- Triple-Barrier Signal Validation

Date: 2026-04-27

## Commands executed
```
sed -n '1,220p' docs/research/2026-04-27_phase_ooo2_cross_asset_signal_expansion_report.md
find data/research/phase_ooo_signal_discovery/ooo2_cross_asset_signal_expansion -maxdepth 1 -type f | sort
python3 - <<'PY' ...small OOO2/return/state summaries...
tail -n 80 docs/research/project_journey.md
python3 scripts/phase_ooo5_triple_barrier_signal_validation.py
```

## Files created / modified
- `scripts/phase_ooo5_triple_barrier_signal_validation.py`
- `data/research/phase_ooo_signal_discovery/ooo5_triple_barrier_validation/*.csv`
- `docs/research/2026-04-27_phase_ooo5_triple_barrier_signal_validation_report.md`
- `docs/research/project_journey.md`

## OOO2 signal queue used
OOO5 used OOO2 signals classified as `KEEP_HIGH_PRIORITY`,
`KEEP_STATE_SPECIFIC`, or `KEEP_FOR_TRIPLE_BARRIER_VALIDATION`. No portfolio
candidates, pin changes, or strategy logic changes were created.

## Event definitions
| signal_name | event_direction | threshold_side | threshold_value | state_filter | n_events | event_frequency | min_event_count_passed | event_selectivity_passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| market_drawdown_signal | risk_off_stress | bottom | -0.122716 | none | 222.000000 | 0.200180 | True | True |
| breadth_ret13_positive_x_stressed_panic_signal | state_quality_or_risk | top | 0.485714 | stressed_panic | 47.000000 | 0.205240 | True | True |
| recent_stress_26w_signal | risk_off_stress | top | 1.000000 | none | 538.000000 | 0.485122 | True | False |
| breadth_ret26_positive_signal | risk_on_opportunity | top | 0.857143 | none | 227.000000 | 0.204689 | True | True |
| breadth_ret13_positive_x_neutral_mixed_signal | risk_on_opportunity | top | 0.771429 | neutral_mixed | 112.000000 | 0.227642 | True | True |
| market_trend_positive_signal | risk_on_opportunity | top | 1.000000 | none | 865.000000 | 0.779982 | True | False |
| canary_breadth_pair_signal | risk_on_opportunity | top | 1.000000 | none | 477.000000 | 0.430117 | True | True |
| breadth_ret13_positive_x_recovery_confirmed_signal | risk_on_opportunity | top | 0.885714 | recovery_confirmed | 12.000000 | 0.272727 | False | True |
| breadth_ret13_positive_signal | risk_on_opportunity | top | 0.828571 | none | 251.000000 | 0.226330 | True | True |
| leadlag_DBA_minus_SPY_13w_signal | defensive_leadership | top | 0.042132 | none | 221.000000 | 0.200181 | True | True |
| leadlag_GLD_minus_SPY_13w_signal | defensive_leadership | top | 0.082422 | none | 221.000000 | 0.200181 | True | True |
| leadlag_EFA_minus_SPY_13w_signal | risk_on_opportunity | top | 0.026594 | none | 221.000000 | 0.200181 | True | True |
| leadlag_HYG_minus_LQD_13w_signal | risk_on_opportunity | top | 0.026827 | none | 221.000000 | 0.200181 | True | True |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | risk_on_opportunity | top | 0.029574 | calm_trend | 59.000000 | 0.200000 | True | True |

## Triple-barrier methodology
Events use the OOO2 lagged signal panel. Primary events fire at the fixed top
or bottom 20% threshold; 30% events are diagnostic only. GGG1 outcomes use
4w/8w/13w forward paths, trailing 13-week weekly volatility known at the event
date, upper barrier `+1.0 * vol * sqrt(horizon)`, lower barrier
`-1.0 * vol * sqrt(horizon)`, and vertical horizon close.

## Event performance summary
| signal_name | event_direction | horizon_weeks | event_count | positive_barrier_hit_rate | negative_barrier_hit_rate | avg_final_return | return_lift_vs_all_weeks | positive_barrier_lift_vs_all_weeks | negative_barrier_lift_vs_all_weeks | holdout_event_count | holdout_avg_final_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_signal | risk_on_opportunity | 13.000000 | 12.000000 | 0.916667 | 0.083333 | 0.057068 | 0.037811 | 0.521181 | -0.036392 | 12.000000 | 0.057068 |
| breadth_ret13_positive_x_recovery_confirmed_signal | risk_on_opportunity | 8.000000 | 12.000000 | 0.916667 | 0.083333 | 0.045325 | 0.033617 | 0.558268 | -0.059245 | 12.000000 | 0.045325 |
| breadth_ret13_positive_x_recovery_confirmed_signal | risk_on_opportunity | 4.000000 | 12.000000 | 0.833333 | 0.083333 | 0.028112 | 0.022276 | 0.541505 | -0.065499 | 12.000000 | 0.028112 |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | risk_on_opportunity | 13.000000 | 59.000000 | 0.389831 | 0.135593 | 0.026854 | 0.007598 | -0.005655 | 0.015868 | 26.000000 | 0.015252 |
| breadth_ret13_positive_signal | risk_on_opportunity | 13.000000 | 246.000000 | 0.548780 | 0.154472 | 0.026446 | 0.007189 | 0.153295 | 0.034746 | 170.000000 | 0.026856 |
| breadth_ret26_positive_signal | risk_on_opportunity | 13.000000 | 217.000000 | 0.576037 | 0.119816 | 0.024931 | 0.005675 | 0.180551 | 0.000090 | 146.000000 | 0.022805 |
| breadth_ret26_positive_signal | risk_on_opportunity | 8.000000 | 222.000000 | 0.513514 | 0.135135 | 0.015430 | 0.003722 | 0.155115 | -0.007443 | 151.000000 | 0.013985 |
| breadth_ret13_positive_signal | risk_on_opportunity | 8.000000 | 248.000000 | 0.491935 | 0.157258 | 0.015356 | 0.003648 | 0.133537 | 0.014680 | 172.000000 | 0.016283 |
| breadth_ret13_positive_x_neutral_mixed_signal | risk_on_opportunity | 13.000000 | 105.000000 | 0.447619 | 0.066667 | 0.022577 | 0.003321 | 0.052133 | -0.053059 | 60.000000 | 0.025180 |
| leadlag_HYG_minus_LQD_13w_signal | risk_on_opportunity | 13.000000 | 219.000000 | 0.374429 | 0.109589 | 0.022001 | 0.002745 | -0.021057 | -0.010136 | 106.000000 | 0.020492 |
| leadlag_EFA_minus_SPY_13w_signal | risk_on_opportunity | 13.000000 | 168.000000 | 0.416667 | 0.101190 | 0.021912 | 0.002656 | 0.021181 | -0.018535 | 67.000000 | 0.018379 |
| breadth_ret13_positive_signal | risk_on_opportunity | 4.000000 | 251.000000 | 0.414343 | 0.139442 | 0.007996 | 0.002160 | 0.122514 | -0.009390 | 175.000000 | 0.007820 |
| market_trend_positive_signal | risk_on_opportunity | 13.000000 | 802.000000 | 0.423940 | 0.114713 | 0.021170 | 0.001914 | 0.028454 | -0.005012 | 431.000000 | 0.021407 |
| market_drawdown_signal | risk_off_stress | 13.000000 | 222.000000 | 0.351351 | 0.130631 | 0.020896 | 0.001640 | -0.044134 | 0.010905 | 60.000000 | 0.015870 |
| canary_breadth_pair_signal | risk_on_opportunity | 8.000000 | 462.000000 | 0.380952 | 0.160173 | 0.013168 | 0.001459 | 0.022554 | 0.017595 | 191.000000 | 0.016551 |
| market_trend_positive_signal | risk_on_opportunity | 8.000000 | 807.000000 | 0.391574 | 0.136307 | 0.013136 | 0.001427 | 0.033175 | -0.006271 | 436.000000 | 0.013186 |
| leadlag_EFA_minus_SPY_13w_signal | risk_on_opportunity | 8.000000 | 172.000000 | 0.360465 | 0.116279 | 0.013095 | 0.001386 | 0.002067 | -0.026299 | 71.000000 | 0.009447 |
| breadth_ret26_positive_signal | risk_on_opportunity | 4.000000 | 226.000000 | 0.384956 | 0.141593 | 0.007193 | 0.001357 | 0.093127 | -0.007240 | 155.000000 | 0.005848 |

## State-specific event behavior
| signal_name | market_state | horizon_weeks | event_count | avg_final_return | return_lift_vs_same_state | positive_barrier_lift_vs_same_state | negative_barrier_lift_vs_same_state |
| --- | --- | --- | --- | --- | --- | --- | --- |
| leadlag_GLD_minus_SPY_13w_signal | recovery_confirmed | 13.000000 | 2.000000 | 0.110749 | 0.064920 | 0.162791 | -0.046512 |
| leadlag_HYG_minus_LQD_13w_signal | recovery_fragile | 13.000000 | 9.000000 | 0.063614 | 0.037527 | 0.460317 | -0.113379 |
| breadth_ret26_positive_signal | stressed_panic | 4.000000 | 1.000000 | 0.039109 | 0.036184 | 0.889381 | -0.115044 |
| leadlag_HYG_minus_LQD_13w_signal | recovery_fragile | 8.000000 | 9.000000 | 0.041005 | 0.027410 | 0.480726 | -0.113379 |
| breadth_ret13_positive_signal | recovery_fragile | 13.000000 | 15.000000 | 0.049755 | 0.023667 | 0.171429 | -0.024490 |
| leadlag_DBA_minus_SPY_13w_signal | recovery_confirmed | 4.000000 | 1.000000 | 0.040150 | 0.023418 | 0.604651 | -0.116279 |
| leadlag_HYG_minus_LQD_13w_signal | recovery_confirmed | 13.000000 | 5.000000 | 0.068702 | 0.022874 | 0.162791 | -0.046512 |
| leadlag_GLD_minus_SPY_13w_signal | recovery_fragile | 13.000000 | 8.000000 | 0.048661 | 0.022573 | 0.071429 | -0.224490 |
| leadlag_GLD_minus_SPY_13w_signal | recovery_confirmed | 8.000000 | 2.000000 | 0.054452 | 0.021730 | 0.325581 | -0.046512 |
| breadth_ret26_positive_signal | recovery_fragile | 13.000000 | 4.000000 | 0.047451 | 0.021363 | 0.071429 | -0.224490 |
| market_drawdown_signal | recovery_fragile | 13.000000 | 15.000000 | 0.046738 | 0.020651 | 0.171429 | -0.091156 |
| breadth_ret26_positive_signal | recovery_fragile | 8.000000 | 4.000000 | 0.031019 | 0.017424 | 0.091837 | -0.224490 |
| leadlag_HYG_minus_LQD_13w_signal | recovery_confirmed | 8.000000 | 5.000000 | 0.048312 | 0.015591 | -0.074419 | 0.153488 |
| leadlag_HYG_minus_LQD_13w_signal | recovery_fragile | 4.000000 | 9.000000 | 0.019131 | 0.015386 | 0.442177 | -0.133787 |
| market_drawdown_signal | recovery_fragile | 8.000000 | 15.000000 | 0.027322 | 0.013727 | 0.191837 | -0.024490 |
| breadth_ret26_positive_signal | recovery_fragile | 4.000000 | 4.000000 | 0.017404 | 0.013658 | 0.275510 | -0.244898 |
| leadlag_GLD_minus_SPY_13w_signal | calm_trend | 13.000000 | 14.000000 | 0.032104 | 0.013523 | 0.121951 | -0.149826 |
| breadth_ret13_positive_x_recovery_confirmed_signal | recovery_confirmed | 8.000000 | 12.000000 | 0.045325 | 0.012604 | 0.242248 | 0.036822 |

## Baseline comparison
| signal_name | horizon_weeks | event_count | return_lift_vs_all_weeks | positive_barrier_lift_vs_all_weeks | negative_barrier_lift_vs_all_weeks | precision_beats_old_production | precision_avoids_bad_outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_signal | 13.000000 | 12.000000 | 0.037811 | 0.521181 | -0.036392 | 0.833333 | 0.916667 |
| breadth_ret13_positive_x_recovery_confirmed_signal | 8.000000 | 12.000000 | 0.033617 | 0.558268 | -0.059245 | 0.916667 | 0.916667 |
| breadth_ret13_positive_x_recovery_confirmed_signal | 4.000000 | 12.000000 | 0.022276 | 0.541505 | -0.065499 | 0.833333 | 0.916667 |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | 13.000000 | 59.000000 | 0.007598 | -0.005655 | 0.015868 | 0.322034 | 0.864407 |
| breadth_ret13_positive_signal | 13.000000 | 246.000000 | 0.007189 | 0.153295 | 0.034746 | 0.508130 | 0.845528 |
| breadth_ret26_positive_signal | 13.000000 | 217.000000 | 0.005675 | 0.180551 | 0.000090 | 0.603687 | 0.880184 |
| breadth_ret26_positive_signal | 8.000000 | 222.000000 | 0.003722 | 0.155115 | -0.007443 | 0.549550 | 0.864865 |
| breadth_ret13_positive_signal | 8.000000 | 248.000000 | 0.003648 | 0.133537 | 0.014680 | 0.508065 | 0.842742 |
| breadth_ret13_positive_x_neutral_mixed_signal | 13.000000 | 105.000000 | 0.003321 | 0.052133 | -0.053059 | 0.504762 | 0.933333 |
| leadlag_HYG_minus_LQD_13w_signal | 13.000000 | 219.000000 | 0.002745 | -0.021057 | -0.010136 | 0.365297 | 0.890411 |
| leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 168.000000 | 0.002656 | 0.021181 | -0.018535 | 0.309524 | 0.898810 |
| breadth_ret13_positive_signal | 4.000000 | 251.000000 | 0.002160 | 0.122514 | -0.009390 | 0.513944 | 0.860558 |
| market_trend_positive_signal | 13.000000 | 802.000000 | 0.001914 | 0.028454 | -0.005012 | 0.495012 | 0.885287 |
| market_drawdown_signal | 13.000000 | 222.000000 | 0.001640 | -0.044134 | 0.010905 | 0.423423 | 0.869369 |
| canary_breadth_pair_signal | 8.000000 | 462.000000 | 0.001459 | 0.022554 | 0.017595 | 0.497835 | 0.839827 |
| market_trend_positive_signal | 8.000000 | 807.000000 | 0.001427 | 0.033175 | -0.006271 | 0.470880 | 0.863693 |
| leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 172.000000 | 0.001386 | 0.002067 | -0.026299 | 0.360465 | 0.883721 |
| breadth_ret26_positive_signal | 4.000000 | 226.000000 | 0.001357 | 0.093127 | -0.007240 | 0.513274 | 0.858407 |

## Event overlap / incrementality
| signal_name | n_events | dominant_market_state | max_state_overlap | high_bil_overlap | max_signal_event_overlap | incrementality_flag |
| --- | --- | --- | --- | --- | --- | --- |
| leadlag_DBA_minus_SPY_13w_signal | 221.000000 | stressed_panic | 0.520362 | 0.434389 | 0.601810 | INCREMENTAL_TO_STATE_ENGINE |
| leadlag_EFA_minus_SPY_13w_signal | 221.000000 | neutral_mixed | 0.497738 | 0.361991 | 0.755656 | INCREMENTAL_TO_STATE_ENGINE |
| leadlag_GLD_minus_SPY_13w_signal | 221.000000 | stressed_panic | 0.547511 | 0.597285 | 0.642534 | INCREMENTAL_TO_STATE_ENGINE |
| market_drawdown_signal | 222.000000 | stressed_panic | 0.490991 | 0.459459 | 0.689189 | INCREMENTAL_TO_STATE_ENGINE |
| recent_stress_26w_signal | 538.000000 | stressed_panic | 0.407063 | 0.382900 | 0.628253 | INCREMENTAL_TO_STATE_ENGINE |
| market_trend_positive_signal | 865.000000 | neutral_mixed | 0.487861 | 0.127168 | 0.470520 | INCREMENTAL_TO_STATE_ENGINE |
| breadth_ret13_positive_x_recovery_confirmed_signal | 12.000000 | recovery_confirmed | 1.000000 | 0.000000 | 1.000000 | INSUFFICIENT_EVENTS |
| breadth_ret13_positive_x_stressed_panic_signal | 47.000000 | stressed_panic | 1.000000 | 0.851064 | 1.000000 | REDUNDANT_WITH_STRONGER_SIGNAL |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | 59.000000 | calm_trend | 1.000000 | 0.000000 | 1.000000 | REDUNDANT_WITH_STRONGER_SIGNAL |
| breadth_ret13_positive_x_neutral_mixed_signal | 112.000000 | neutral_mixed | 1.000000 | 0.044643 | 1.000000 | REDUNDANT_WITH_STRONGER_SIGNAL |
| leadlag_HYG_minus_LQD_13w_signal | 221.000000 | neutral_mixed | 0.407240 | 0.171946 | 0.823529 | REDUNDANT_WITH_STRONGER_SIGNAL |
| breadth_ret26_positive_signal | 227.000000 | calm_trend | 0.537445 | 0.000000 | 0.991189 | REDUNDANT_WITH_STRONGER_SIGNAL |
| breadth_ret13_positive_signal | 251.000000 | calm_trend | 0.398406 | 0.055777 | 0.988048 | REDUNDANT_WITH_STRONGER_SIGNAL |
| canary_breadth_pair_signal | 477.000000 | neutral_mixed | 0.475891 | 0.123690 | 0.853249 | REDUNDANT_WITH_STRONGER_SIGNAL |

## Keep / reject decisions
| signal_name | decision | event_count | event_frequency | event_selectivity_passed | event_direction | incrementality_flag | best_avg_return_lift | best_positive_barrier_lift | best_negative_barrier_lift | holdout_avg_return_best | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO3_VOL_MANAGED_SIZING | 221.000000 | 0.200181 | True | risk_on_opportunity | INCREMENTAL_TO_STATE_ENGINE | 0.002656 | 0.021181 | -0.018535 | 0.018379 | Directional lift exists but needs volatility/sizing/selectivity polish. |
| market_trend_positive_signal | KEEP_FOR_OOO3_VOL_MANAGED_SIZING | 865.000000 | 0.779982 | False | risk_on_opportunity | INCREMENTAL_TO_STATE_ENGINE | 0.001914 | 0.044793 | -0.003333 | 0.021407 | Directional lift exists but needs volatility/sizing/selectivity polish. |
| market_drawdown_signal | KEEP_STATE_SPECIFIC_META_LABEL | 222.000000 | 0.200180 | True | risk_off_stress | INCREMENTAL_TO_STATE_ENGINE | 0.001640 | -0.029570 | 0.010905 | 0.015870 | Event avoids adverse tails and has positive return lift. |
| leadlag_GLD_minus_SPY_13w_signal | KEEP_STATE_SPECIFIC_META_LABEL | 221.000000 | 0.200181 | True | defensive_leadership | INCREMENTAL_TO_STATE_ENGINE | 0.000596 | -0.065205 | -0.036012 | 0.028729 | Event avoids adverse tails and has positive return lift. |
| leadlag_DBA_minus_SPY_13w_signal | KEEP_STATE_SPECIFIC_META_LABEL | 221.000000 | 0.200181 | True | defensive_leadership | INCREMENTAL_TO_STATE_ENGINE | 0.000323 | -0.129792 | -0.031353 | 0.013651 | Event avoids adverse tails and has positive return lift. |
| breadth_ret13_positive_x_recovery_confirmed_signal | PROMISING_BUT_NEEDS_MORE_EVENTS | 12.000000 | 0.272727 | True | risk_on_opportunity | INSUFFICIENT_EVENTS | 0.037811 | 0.558268 | -0.036392 | 0.057068 | Primary event count below minimum. |
| leadlag_HYG_minus_LQD_13w_x_calm_trend_signal | REDUNDANT_OR_DUPLICATIVE | 59.000000 | 0.200000 | True | risk_on_opportunity | REDUNDANT_WITH_STRONGER_SIGNAL | 0.007598 | -0.005655 | 0.088455 | 0.015252 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| breadth_ret13_positive_signal | REDUNDANT_OR_DUPLICATIVE | 251.000000 | 0.226330 | True | risk_on_opportunity | REDUNDANT_WITH_STRONGER_SIGNAL | 0.007189 | 0.153295 | 0.034746 | 0.026856 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| breadth_ret26_positive_signal | REDUNDANT_OR_DUPLICATIVE | 227.000000 | 0.204689 | True | risk_on_opportunity | REDUNDANT_WITH_STRONGER_SIGNAL | 0.005675 | 0.180551 | 0.000090 | 0.022805 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| breadth_ret13_positive_x_neutral_mixed_signal | REDUNDANT_OR_DUPLICATIVE | 112.000000 | 0.227642 | True | risk_on_opportunity | REDUNDANT_WITH_STRONGER_SIGNAL | 0.003321 | 0.163528 | -0.032486 | 0.025180 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| leadlag_HYG_minus_LQD_13w_signal | REDUNDANT_OR_DUPLICATIVE | 221.000000 | 0.200181 | True | risk_on_opportunity | REDUNDANT_WITH_STRONGER_SIGNAL | 0.002745 | -0.017856 | 0.015551 | 0.020492 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| canary_breadth_pair_signal | REDUNDANT_OR_DUPLICATIVE | 477.000000 | 0.430117 | True | risk_on_opportunity | REDUNDANT_WITH_STRONGER_SIGNAL | 0.001459 | 0.023622 | 0.017595 | 0.026792 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| breadth_ret13_positive_x_stressed_panic_signal | REDUNDANT_OR_DUPLICATIVE | 47.000000 | 0.205240 | True | state_quality_or_risk | REDUNDANT_WITH_STRONGER_SIGNAL | 0.000526 | -0.100339 | -0.077172 | 0.015407 | Event timing flag: REDUNDANT_WITH_STRONGER_SIGNAL. |
| recent_stress_26w_signal | REJECT_EVENT_VALIDATION | 538.000000 | 0.485122 | False | risk_off_stress | INCREMENTAL_TO_STATE_ENGINE | -0.000304 | 0.029845 | 0.027723 | 0.021119 | Risk event did not show enough adverse-path or favorable asymmetry lift. |

## Top signals to test next
| signal_name | decision | assigned_next_phase | best_avg_return_lift | best_positive_barrier_lift |
| --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO3_VOL_MANAGED_SIZING | OOO3 volatility-managed signal sizing | 0.002656 | 0.021181 |
| market_trend_positive_signal | KEEP_FOR_OOO3_VOL_MANAGED_SIZING | OOO3 volatility-managed signal sizing | 0.001914 | 0.044793 |
| market_drawdown_signal | KEEP_STATE_SPECIFIC_META_LABEL | additional event validation before portfolio pass-through | 0.001640 | -0.029570 |
| leadlag_GLD_minus_SPY_13w_signal | KEEP_STATE_SPECIFIC_META_LABEL | additional event validation before portfolio pass-through | 0.000596 | -0.065205 |
| leadlag_DBA_minus_SPY_13w_signal | KEEP_STATE_SPECIFIC_META_LABEL | additional event validation before portfolio pass-through | 0.000323 | -0.129792 |
| breadth_ret13_positive_x_recovery_confirmed_signal | PROMISING_BUT_NEEDS_MORE_EVENTS | additional event validation before portfolio pass-through | 0.037811 | 0.558268 |

## Final recommendation
**PROCEED_TO_OOO3_VOL_MANAGED_SIGNAL_SIZING**

Reason: OOO5 found event evidence, but direct pass-through gates were not clean enough; volatility/selectivity sizing is needed first.

## How OOO5 feeds OOO3 or OOO6
OOO5 is an event-validation gate. Signals routed to OOO3 need volatility-managed
sizing before any portfolio pass-through. Signals routed to OOO6 may be tested
later through GGG1, but this phase created no portfolio candidates.

## Exact prompt outline for next phase
Use OOO5 event decisions to test volatility-managed sizing or, only for direct keep signals, a later GGG1 portfolio pass-through. Do not create portfolio candidates before that gate.
