# Phase OOO3 -- Volatility-Managed Signal Sizing

Date: 2026-04-27

## Commands executed
```
sed -n '1,210p' docs/research/2026-04-27_phase_ooo5_triple_barrier_signal_validation_report.md
find data/research/phase_ooo_signal_discovery/ooo5_triple_barrier_validation -maxdepth 1 -type f | sort
python3 - <<'PY' ...small OOO5/OOO2/return/state summaries...
tail -n 90 docs/research/project_journey.md
python3 scripts/phase_ooo3_vol_managed_signal_sizing.py
```

## Files created / modified
- `scripts/phase_ooo3_vol_managed_signal_sizing.py`
- `data/research/phase_ooo_signal_discovery/ooo3_vol_managed_signal_sizing/*.csv`
- `docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md`
- `docs/research/project_journey.md`

## OOO5 signal queue used
| signal_name | ooo5_decision | event_count | best_avg_return_lift | best_positive_barrier_lift | best_negative_barrier_lift | assigned_role_for_ooo3 |
| --- | --- | --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO3_VOL_MANAGED_SIZING | 221.000000 | 0.002656 | 0.021181 | -0.018535 | PRIMARY |
| market_trend_positive_signal | KEEP_FOR_OOO3_VOL_MANAGED_SIZING | 865.000000 | 0.001914 | 0.044793 | -0.003333 | PRIMARY |
| market_drawdown_signal | KEEP_STATE_SPECIFIC_META_LABEL | 222.000000 | 0.001640 | -0.029570 | 0.010905 | SECONDARY_REFERENCE |
| leadlag_GLD_minus_SPY_13w_signal | KEEP_STATE_SPECIFIC_META_LABEL | 221.000000 | 0.000596 | -0.065205 | -0.036012 | SECONDARY_REFERENCE |
| leadlag_DBA_minus_SPY_13w_signal | KEEP_STATE_SPECIFIC_META_LABEL | 221.000000 | 0.000323 | -0.129792 | -0.031353 | SECONDARY_REFERENCE |
| breadth_ret13_positive_x_recovery_confirmed_signal | PROMISING_BUT_NEEDS_MORE_EVENTS | 12.000000 | 0.037811 | 0.558268 | -0.036392 | SECONDARY_REFERENCE |

## Volatility / selectivity features
| feature_name | base_signal | feature_group | missingness | causal_ok |
| --- | --- | --- | --- | --- |
| leadlag_EFA_minus_SPY_13w_signal__raw | leadlag_EFA_minus_SPY_13w_signal | signal_strength | 0.005405 | True |
| leadlag_EFA_minus_SPY_13w_signal__percentile | leadlag_EFA_minus_SPY_13w_signal | signal_strength | 0.051351 | True |
| leadlag_EFA_minus_SPY_13w_signal__zscore | leadlag_EFA_minus_SPY_13w_signal | signal_strength | 0.051351 | True |
| leadlag_EFA_minus_SPY_13w_signal__strength_scaled_score | leadlag_EFA_minus_SPY_13w_signal | signal_strength | 0.053153 | True |
| market_trend_positive_signal__raw | market_trend_positive_signal | signal_strength | 0.000901 | True |
| market_trend_positive_signal__percentile | market_trend_positive_signal | signal_strength | 0.046847 | True |
| market_trend_positive_signal__zscore | market_trend_positive_signal | signal_strength | 0.077477 | True |
| market_trend_positive_signal__strength_scaled_score | market_trend_positive_signal | signal_strength | 0.053153 | True |
| market_drawdown_signal__raw | market_drawdown_signal | signal_strength | 0.000901 | True |
| market_drawdown_signal__percentile | market_drawdown_signal | signal_strength | 0.046847 | True |
| market_drawdown_signal__zscore | market_drawdown_signal | signal_strength | 0.046847 | True |
| market_drawdown_signal__strength_scaled_score | market_drawdown_signal | signal_strength | 0.053153 | True |
| leadlag_GLD_minus_SPY_13w_signal__raw | leadlag_GLD_minus_SPY_13w_signal | signal_strength | 0.005405 | True |
| leadlag_GLD_minus_SPY_13w_signal__percentile | leadlag_GLD_minus_SPY_13w_signal | signal_strength | 0.051351 | True |
| leadlag_GLD_minus_SPY_13w_signal__zscore | leadlag_GLD_minus_SPY_13w_signal | signal_strength | 0.051351 | True |
| leadlag_GLD_minus_SPY_13w_signal__strength_scaled_score | leadlag_GLD_minus_SPY_13w_signal | signal_strength | 0.053153 | True |
| leadlag_DBA_minus_SPY_13w_signal__raw | leadlag_DBA_minus_SPY_13w_signal | signal_strength | 0.005405 | True |
| leadlag_DBA_minus_SPY_13w_signal__percentile | leadlag_DBA_minus_SPY_13w_signal | signal_strength | 0.051351 | True |

## Sized variant definitions
| variant_name | base_signal | threshold_rule | vol_filter_rule | state_filter_rule | complexity_level |
| --- | --- | --- | --- | --- | --- |
| efa_spy_raw_top20_event | leadlag_EFA_minus_SPY_13w_signal | top20 | none | none | LOW |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | top10 | none | none | LOW |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | top30 | none | none | LOW |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | top20 | exclude highest vol quintile | none | LOW |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | top20 | LOW/NORMAL_VOL only | none | LOW |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | scaled top20 | vol scaled | none | MEDIUM |
| efa_spy_drawdown_aware_top20_event | leadlag_EFA_minus_SPY_13w_signal | top20 | none | exclude deep drawdown | LOW |
| efa_spy_market_trend_confirmed_top20_event | leadlag_EFA_minus_SPY_13w_signal | top20 | none | trend positive | LOW |
| market_trend_raw_event | market_trend_positive_signal | binary raw | none | none | LOW |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | binary + breadth | none | breadth confirmation | LOW |
| market_trend_ex_high_vol_drawdown_event | market_trend_positive_signal | binary | vol <= 80% | drawdown > -8% | LOW |
| market_trend_recent_stress_filtered_event | market_trend_positive_signal | binary | none | recent_stress_26w <= 0 | LOW |
| market_trend_calm_neutral_event | market_trend_positive_signal | binary | none | calm_trend or neutral_mixed | LOW |
| market_trend_vol_scaled_score_event | market_trend_positive_signal | binary + scaled | low vol favored | none | MEDIUM |
| market_drawdown_top20_event | market_drawdown_signal | top20 | none | none | LOW |
| market_drawdown_vol_filtered_top20_event | market_drawdown_signal | top20 | exclude highest vol quintile | none | LOW |
| leadlag_GLD_minus_SPY_13w_top20_event | leadlag_GLD_minus_SPY_13w_signal | top20 | none | none | LOW |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | leadlag_GLD_minus_SPY_13w_signal | top20 | exclude highest vol quintile | none | LOW |
| leadlag_DBA_minus_SPY_13w_top20_event | leadlag_DBA_minus_SPY_13w_signal | top20 | none | none | LOW |
| leadlag_DBA_minus_SPY_13w_vol_filtered_top20_event | leadlag_DBA_minus_SPY_13w_signal | top20 | exclude highest vol quintile | none | LOW |
| breadth_ret13_positive_x_recovery_confirmed_top20_event | breadth_ret13_positive_x_recovery_confirmed_signal | top20 | none | none | LOW |
| breadth_ret13_positive_x_recovery_confirmed_vol_filtered_top20_event | breadth_ret13_positive_x_recovery_confirmed_signal | top20 | exclude highest vol quintile | none | LOW |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | top20 | none | recovery_confirmed | LOW |

## Event performance summary
| variant_name | base_signal | horizon_weeks | event_count | positive_barrier_hit_rate | negative_barrier_hit_rate | avg_final_return | return_lift_vs_all_weeks | holdout_2016_event_count | holdout_2016_avg_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 13.000000 | 43.000000 | 0.837209 | 0.046512 | 0.045828 | 0.026572 | 34.000000 | 0.053248 |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 8.000000 | 43.000000 | 0.674419 | 0.046512 | 0.032721 | 0.021013 | 34.000000 | 0.037398 |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 4.000000 | 43.000000 | 0.395349 | 0.116279 | 0.016732 | 0.010896 | 34.000000 | 0.018953 |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 70.000000 | 0.442857 | 0.085714 | 0.029317 | 0.010060 | 41.000000 | 0.026062 |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 209.000000 | 0.660287 | 0.124402 | 0.028363 | 0.009107 | 139.000000 | 0.029361 |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 87.000000 | 0.505747 | 0.126437 | 0.027136 | 0.007880 | 46.000000 | 0.020332 |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 103.000000 | 0.456311 | 0.126214 | 0.026301 | 0.007045 | 54.000000 | 0.018957 |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 87.000000 | 0.413793 | 0.126437 | 0.016541 | 0.004832 | 46.000000 | 0.013837 |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 209.000000 | 0.531100 | 0.138756 | 0.016503 | 0.004795 | 139.000000 | 0.016801 |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 73.000000 | 0.424658 | 0.150685 | 0.015465 | 0.003757 | 44.000000 | 0.012325 |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 192.000000 | 0.479167 | 0.104167 | 0.022117 | 0.002861 | 105.000000 | 0.020471 |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | 13.000000 | 334.000000 | 0.494012 | 0.122754 | 0.022115 | 0.002859 | 201.000000 | 0.023806 |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 107.000000 | 0.383178 | 0.158879 | 0.014239 | 0.002530 | 58.000000 | 0.009290 |
| market_trend_vol_scaled_score_event | market_trend_positive_signal | 13.000000 | 178.000000 | 0.651685 | 0.235955 | 0.021692 | 0.002436 | 121.000000 | 0.026914 |
| market_trend_ex_high_vol_drawdown_event | market_trend_positive_signal | 13.000000 | 588.000000 | 0.474490 | 0.134354 | 0.021371 | 0.002115 | 346.000000 | 0.022248 |
| market_trend_raw_event | market_trend_positive_signal | 13.000000 | 802.000000 | 0.423940 | 0.114713 | 0.021170 | 0.001914 | 431.000000 | 0.021407 |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | 8.000000 | 339.000000 | 0.427729 | 0.141593 | 0.013413 | 0.001705 | 206.000000 | 0.014038 |
| efa_spy_market_trend_confirmed_top20_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 90.000000 | 0.388889 | 0.077778 | 0.020702 | 0.001445 | 40.000000 | 0.020123 |
| market_trend_raw_event | market_trend_positive_signal | 8.000000 | 807.000000 | 0.391574 | 0.136307 | 0.013136 | 0.001427 | 436.000000 | 0.013186 |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | leadlag_GLD_minus_SPY_13w_signal | 13.000000 | 119.000000 | 0.394958 | 0.042017 | 0.020494 | 0.001238 | 76.000000 | 0.030103 |

## Sized vs raw comparison
| variant_name | base_signal | horizon_weeks | return_lift_vs_raw | positive_barrier_lift_vs_raw | negative_barrier_lift_vs_raw | return_lift_vs_all_weeks |
| --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 13.000000 | 0.026572 | 0.441724 | -0.073214 | 0.026572 |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 8.000000 | 0.021013 | 0.316020 | -0.096066 | 0.021013 |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 4.000000 | 0.010896 | 0.103520 | -0.032554 | 0.010896 |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 0.009057 | 0.046032 | -0.025397 | 0.010060 |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 0.008103 | 0.263462 | 0.013291 | 0.009107 |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 0.006877 | 0.108922 | 0.015326 | 0.007880 |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 0.006042 | 0.059485 | 0.015102 | 0.007045 |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 0.005140 | 0.075332 | -0.012025 | 0.004832 |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 0.005103 | 0.192639 | 0.000294 | 0.004795 |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 0.004065 | 0.086196 | 0.012223 | 0.003757 |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 0.002838 | 0.044716 | 0.020417 | 0.002530 |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 0.001858 | 0.082341 | -0.006944 | 0.002861 |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | 4.000000 | 0.001613 | 0.109783 | -0.006366 | 0.000995 |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | 8.000000 | 0.001399 | 0.067630 | -0.016634 | 0.001091 |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | 4.000000 | 0.001022 | 0.031025 | 0.022975 | 0.000404 |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | 13.000000 | 0.000945 | 0.070072 | 0.008041 | 0.002859 |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | 4.000000 | 0.000685 | 0.024876 | -0.014925 | 0.000067 |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | 4.000000 | 0.000590 | 0.037519 | 0.030809 | -0.000028 |
| market_trend_vol_scaled_score_event | market_trend_positive_signal | 13.000000 | 0.000522 | 0.227745 | 0.121242 | 0.002436 |
| efa_spy_market_trend_confirmed_top20_event | leadlag_EFA_minus_SPY_13w_signal | 13.000000 | 0.000442 | -0.007937 | -0.033333 | 0.001445 |

## State-specific behavior
| variant_name | market_state | horizon_weeks | event_count | avg_final_return | return_lift_vs_same_state | positive_barrier_lift_vs_same_state |
| --- | --- | --- | --- | --- | --- | --- |
| leadlag_GLD_minus_SPY_13w_top20_event | recovery_confirmed | 13.000000 | 2.000000 | 0.110749 | 0.064920 | 0.162791 |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | recovery_confirmed | 13.000000 | 2.000000 | 0.110749 | 0.064920 | 0.162791 |
| market_drawdown_vol_filtered_top20_event | calm_trend | 13.000000 | 3.000000 | 0.056799 | 0.038217 | 0.550523 |
| market_drawdown_top20_event | calm_trend | 8.000000 | 4.000000 | 0.037917 | 0.026830 | 0.609756 |
| leadlag_DBA_minus_SPY_13w_top20_event | recovery_confirmed | 4.000000 | 1.000000 | 0.040150 | 0.023418 | 0.604651 |
| leadlag_DBA_minus_SPY_13w_vol_filtered_top20_event | recovery_confirmed | 4.000000 | 1.000000 | 0.040150 | 0.023418 | 0.604651 |
| market_drawdown_vol_filtered_top20_event | calm_trend | 8.000000 | 3.000000 | 0.034429 | 0.023342 | 0.609756 |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | recovery_fragile | 13.000000 | 7.000000 | 0.049172 | 0.023084 | 0.142857 |
| market_drawdown_top20_event | calm_trend | 13.000000 | 4.000000 | 0.040416 | 0.021835 | 0.550523 |
| leadlag_GLD_minus_SPY_13w_top20_event | recovery_confirmed | 8.000000 | 2.000000 | 0.054452 | 0.021730 | 0.325581 |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | recovery_confirmed | 8.000000 | 2.000000 | 0.054452 | 0.021730 | 0.325581 |
| efa_spy_strength_scaled_score_event | recovery_fragile | 13.000000 | 20.000000 | 0.047712 | 0.021624 | 0.171429 |
| efa_spy_vol_filtered_top20_event | recovery_fragile | 13.000000 | 14.000000 | 0.046726 | 0.020638 | 0.214286 |
| leadlag_GLD_minus_SPY_13w_top20_event | calm_trend | 13.000000 | 9.000000 | 0.039006 | 0.020425 | 0.217189 |
| market_trend_recent_stress_filtered_event | stressed_panic | 13.000000 | 4.000000 | 0.031890 | 0.020330 | -0.003333 |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | calm_trend | 13.000000 | 7.000000 | 0.038254 | 0.019673 | 0.407666 |
| efa_spy_low_or_normal_vol_top20_event | recovery_fragile | 13.000000 | 13.000000 | 0.045719 | 0.019631 | 0.186813 |
| market_drawdown_top20_event | recovery_fragile | 13.000000 | 14.000000 | 0.044306 | 0.018218 | 0.142857 |

## Selectivity / turnover proxy
| variant_name | base_signal | event_count | event_frequency | event_start_count | event_transition_count | max_state_overlap | incrementality_flag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | 44.000000 | 0.039640 | 19.000000 | 37.000000 | 1.000000 | DUPLICATES_STATE_ENGINE |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | 84.000000 | 0.075676 | 20.000000 | 40.000000 | 0.500000 | INCREMENTAL_SELECTIVE |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | 89.000000 | 0.080180 | 21.000000 | 42.000000 | 0.314607 | INCREMENTAL_SELECTIVE |
| efa_spy_market_trend_confirmed_top20_event | leadlag_EFA_minus_SPY_13w_signal | 107.000000 | 0.096396 | 32.000000 | 64.000000 | 0.532710 | INCREMENTAL_SELECTIVE |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | 109.000000 | 0.098198 | 24.000000 | 48.000000 | 0.403670 | INCREMENTAL_SELECTIVE |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | leadlag_GLD_minus_SPY_13w_signal | 124.000000 | 0.111712 | 33.000000 | 66.000000 | 0.604839 | INCREMENTAL_SELECTIVE |
| market_drawdown_vol_filtered_top20_event | market_drawdown_signal | 136.000000 | 0.122523 | 13.000000 | 26.000000 | 0.676471 | INCREMENTAL_SELECTIVE |
| efa_spy_raw_top20_event | leadlag_EFA_minus_SPY_13w_signal | 145.000000 | 0.130631 | 34.000000 | 67.000000 | 0.475862 | INCREMENTAL_SELECTIVE |
| efa_spy_drawdown_aware_top20_event | leadlag_EFA_minus_SPY_13w_signal | 145.000000 | 0.130631 | 34.000000 | 67.000000 | 0.475862 | INCREMENTAL_SELECTIVE |
| leadlag_DBA_minus_SPY_13w_vol_filtered_top20_event | leadlag_DBA_minus_SPY_13w_signal | 153.000000 | 0.137838 | 39.000000 | 78.000000 | 0.542484 | INCREMENTAL_SELECTIVE |
| market_drawdown_top20_event | market_drawdown_signal | 169.000000 | 0.152252 | 21.000000 | 42.000000 | 0.680473 | INCREMENTAL_SELECTIVE |
| market_trend_vol_scaled_score_event | market_trend_positive_signal | 178.000000 | 0.160360 | 21.000000 | 42.000000 | 0.432584 | INCREMENTAL_SELECTIVE |
| leadlag_GLD_minus_SPY_13w_top20_event | leadlag_GLD_minus_SPY_13w_signal | 197.000000 | 0.177477 | 39.000000 | 77.000000 | 0.568528 | INCREMENTAL_SELECTIVE |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | 211.000000 | 0.190090 | 35.000000 | 70.000000 | 0.336493 | INCREMENTAL_SELECTIVE |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | 219.000000 | 0.197297 | 39.000000 | 77.000000 | 0.433790 | INCREMENTAL_SELECTIVE |
| leadlag_DBA_minus_SPY_13w_top20_event | leadlag_DBA_minus_SPY_13w_signal | 226.000000 | 0.203604 | 51.000000 | 101.000000 | 0.513274 | INCREMENTAL_SELECTIVE |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | 344.000000 | 0.309910 | 66.000000 | 132.000000 | 0.488372 | INCREMENTAL_SELECTIVE |
| market_trend_recent_stress_filtered_event | market_trend_positive_signal | 527.000000 | 0.474775 | 17.000000 | 34.000000 | 0.514231 | TOO_BROAD |
| market_trend_ex_high_vol_drawdown_event | market_trend_positive_signal | 595.000000 | 0.536036 | 44.000000 | 88.000000 | 0.460504 | TOO_BROAD |
| market_trend_calm_neutral_event | market_trend_positive_signal | 716.000000 | 0.645045 | 61.000000 | 122.000000 | 0.589385 | TOO_BROAD |
| breadth_ret13_positive_x_recovery_confirmed_vol_filtered_top20_event | breadth_ret13_positive_x_recovery_confirmed_signal | 776.000000 | 0.699099 | 23.000000 | 46.000000 | 0.399485 | TOO_BROAD |
| market_trend_raw_event | market_trend_positive_signal | 865.000000 | 0.779279 | 35.000000 | 70.000000 | 0.487861 | TOO_BROAD |
| breadth_ret13_positive_x_recovery_confirmed_top20_event | breadth_ret13_positive_x_recovery_confirmed_signal | 1058.000000 | 0.953153 | 1.000000 | 1.000000 | 0.422495 | TOO_BROAD |

## Keep / reject decisions
| variant_name | base_signal | decision | event_count | event_frequency | best_return_lift_vs_all_weeks | best_return_lift_vs_raw | best_positive_barrier_lift_vs_raw | holdout_avg_return_best | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | KEEP_FOR_ADDITIONAL_EVENT_VALIDATION | 44.000000 | 0.039640 | 0.026572 | 0.026572 | 0.441724 | 0.053248 | Variant improves raw behavior but has simplification/state-overlap concerns. |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_ADDITIONAL_EVENT_VALIDATION | 211.000000 | 0.190090 | 0.009107 | 0.008103 | 0.263462 | 0.029361 | Variant improves raw behavior but has simplification/state-overlap concerns. |
| market_trend_vol_scaled_score_event | market_trend_positive_signal | KEEP_FOR_ADDITIONAL_EVENT_VALIDATION | 178.000000 | 0.160360 | 0.002436 | 0.000522 | 0.227745 | 0.026914 | Variant improves raw behavior but has simplification/state-overlap concerns. |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 84.000000 | 0.075676 | 0.010060 | 0.009057 | 0.046032 | 0.026062 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 89.000000 | 0.080180 | 0.007880 | 0.006877 | 0.108922 | 0.020332 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 109.000000 | 0.098198 | 0.007045 | 0.006042 | 0.059485 | 0.018957 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 219.000000 | 0.197297 | 0.002861 | 0.001858 | 0.082341 | 0.020471 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 344.000000 | 0.309910 | 0.002859 | 0.000945 | 0.070072 | 0.023806 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| efa_spy_market_trend_confirmed_top20_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 107.000000 | 0.096396 | 0.001445 | 0.000442 | -0.007937 | 0.020123 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| leadlag_GLD_minus_SPY_13w_vol_filtered_top20_event | leadlag_GLD_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 124.000000 | 0.111712 | 0.001238 | 0.000146 | 0.074958 | 0.030103 | Sized variant improves raw event behavior with acceptable selectivity and holdout. |
| market_trend_ex_high_vol_drawdown_event | market_trend_positive_signal | REJECT_SIZING_VALIDATION | 595.000000 | 0.536036 | 0.002115 | 0.000201 | 0.050550 | 0.022248 | Variant fires too often after sizing/selectivity filter. |
| market_trend_raw_event | market_trend_positive_signal | REJECT_SIZING_VALIDATION | 865.000000 | 0.779279 | 0.001914 | 0.000000 | 0.000000 | 0.021407 | Variant fires too often after sizing/selectivity filter. |
| leadlag_GLD_minus_SPY_13w_top20_event | leadlag_GLD_minus_SPY_13w_signal | REJECT_SIZING_VALIDATION | 197.000000 | 0.177477 | 0.001092 | 0.000000 | 0.000000 | 0.026827 | Sizing did not improve raw event behavior enough. |
| efa_spy_drawdown_aware_top20_event | leadlag_EFA_minus_SPY_13w_signal | REJECT_SIZING_VALIDATION | 145.000000 | 0.130631 | 0.001003 | 0.000000 | 0.000000 | 0.018456 | Sizing did not improve raw event behavior enough. |
| efa_spy_raw_top20_event | leadlag_EFA_minus_SPY_13w_signal | REJECT_SIZING_VALIDATION | 145.000000 | 0.130631 | 0.001003 | 0.000000 | 0.000000 | 0.018456 | Sizing did not improve raw event behavior enough. |
| leadlag_DBA_minus_SPY_13w_top20_event | leadlag_DBA_minus_SPY_13w_signal | REJECT_SIZING_VALIDATION | 226.000000 | 0.203604 | 0.000523 | 0.000000 | 0.000000 | 0.015060 | Sizing did not improve raw event behavior enough. |
| market_trend_calm_neutral_event | market_trend_positive_signal | REJECT_SIZING_VALIDATION | 716.000000 | 0.645045 | 0.000493 | -0.000319 | 0.019336 | 0.020263 | Variant fires too often after sizing/selectivity filter. |
| market_trend_recent_stress_filtered_event | market_trend_positive_signal | REJECT_SIZING_VALIDATION | 527.000000 | 0.474775 | 0.000098 | -0.000714 | -0.013092 | 0.020962 | Variant fires too often after sizing/selectivity filter. |
| breadth_ret13_positive_x_recovery_confirmed_top20_event | breadth_ret13_positive_x_recovery_confirmed_signal | REJECT_SIZING_VALIDATION | 1058.000000 | 0.953153 | 0.000000 | 0.000000 | 0.000000 | 0.020791 | Variant fires too often after sizing/selectivity filter. |
| breadth_ret13_positive_x_recovery_confirmed_vol_filtered_top20_event | breadth_ret13_positive_x_recovery_confirmed_signal | REJECT_SIZING_VALIDATION | 776.000000 | 0.699099 | -0.000479 | -0.000479 | 0.031625 | 0.021290 | Variant fires too often after sizing/selectivity filter. |
| market_drawdown_top20_event | market_drawdown_signal | REJECT_SIZING_VALIDATION | 169.000000 | 0.152252 | -0.000758 | 0.000000 | 0.000000 | 0.014820 | Sizing did not improve raw event behavior enough. |
| leadlag_DBA_minus_SPY_13w_vol_filtered_top20_event | leadlag_DBA_minus_SPY_13w_signal | REJECT_SIZING_VALIDATION | 153.000000 | 0.137838 | -0.000956 | -0.001479 | -0.002428 | 0.017747 | Sizing did not improve raw event behavior enough. |
| market_drawdown_vol_filtered_top20_event | market_drawdown_signal | REJECT_SIZING_VALIDATION | 136.000000 | 0.122523 | -0.002023 | -0.001265 | 0.012195 | 0.011586 | Sizing did not improve raw event behavior enough. |

## Top signals to test next
| variant_name | base_signal | decision | assigned_next_phase | best_return_lift_vs_all_weeks | best_return_lift_vs_raw |
| --- | --- | --- | --- | --- | --- |
| breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | breadth_ret13_positive_x_recovery_confirmed_signal | KEEP_FOR_ADDITIONAL_EVENT_VALIDATION | additional signal validation before portfolio pass-through | 0.026572 | 0.026572 |
| efa_spy_strength_scaled_score_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_ADDITIONAL_EVENT_VALIDATION | additional signal validation before portfolio pass-through | 0.009107 | 0.008103 |
| market_trend_vol_scaled_score_event | market_trend_positive_signal | KEEP_FOR_ADDITIONAL_EVENT_VALIDATION | additional signal validation before portfolio pass-through | 0.002436 | 0.000522 |
| efa_spy_raw_top10_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | OOO6 GGG1 portfolio pass-through | 0.010060 | 0.009057 |
| efa_spy_low_or_normal_vol_top20_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | OOO6 GGG1 portfolio pass-through | 0.007880 | 0.006877 |
| efa_spy_vol_filtered_top20_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | OOO6 GGG1 portfolio pass-through | 0.007045 | 0.006042 |
| efa_spy_raw_top30_event | leadlag_EFA_minus_SPY_13w_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | OOO6 GGG1 portfolio pass-through | 0.002861 | 0.001858 |
| market_trend_breadth_confirmed_event | market_trend_positive_signal | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | OOO6 GGG1 portfolio pass-through | 0.002859 | 0.000945 |

## Final recommendation
**PROCEED_TO_OOO6_PORTFOLIO_PASS_THROUGH**

Reason: OOO3 found at least one sized signal that cleared selectivity, raw-improvement, and holdout gates.

## Whether OOO6 portfolio pass-through is justified
Yes, at least one variant cleared the OOO3 pass-through gate.

## Exact prompt outline for next phase
Use the OOO3 keep queue only if a variant cleared pass-through; otherwise return to signal discovery or sleeve/factor momentum. Do not create portfolio candidates unless OOO3 says OOO6.
