# Phase SSS2 -- Sequence Signal Validation

Date: 2026-04-27

## Commands Executed
- `sed -n '1,360p' docs/research/2026-04-27_phase_sss_regime_sequence_modeling_report.md`
- `find data/research/phase_sss_regime_sequence_modeling -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf "%s\t" "$(basename "{}")"; wc -l < "{}"'`
- `python3 - <<'PY' ...SSS candidate queue, feature, target, and state schema summaries...`
- `sed -n '1,260p' docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md`
- `sed -n '1,180p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md`
- `sed -n '1,220p' scripts/phase_sss_regime_sequence_modeling.py`
- `tail -n 220 scripts/phase_sss_regime_sequence_modeling.py`
- `python3 -m py_compile scripts/phase_sss2_sequence_signal_validation.py`
- `python3 scripts/phase_sss2_sequence_signal_validation.py`

## Files Created / Modified
- `scripts/phase_sss2_sequence_signal_validation.py`
- `data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_definitions.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_panel.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_manifest.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_signal_missingness.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_leakage_checklist.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_event_validation_summary.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_event_state_path_summary.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_event_target_matrix.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_triple_barrier_outcomes.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_triple_barrier_summary.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_path_outcome_asymmetry.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_subperiod_stability.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_holdout_validation_summary.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_redundancy.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_incrementality.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_ooo_qqq_overlap.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_layer2b_overlap.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_ggg1_exposure_overlap.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_signal_keep_reject_decisions.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_next_phase_queue.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_next_action_recommendation.csv`
- `data/research/phase_sss2_sequence_signal_validation/sss2_dataset_schema.json`
- `docs/research/2026-04-27_phase_sss2_sequence_signal_validation_report.md`
- `docs/research/project_journey.md`

## SSS Rule Queue Used
Only high-priority/promising SSS rules and watchlist `NEEDS_TRIPLE_BARRIER_VALIDATION` rules were converted. Production/shadow/GGG1 artifacts were read only.
| rule_name | target | classification | event_count | precision_lift | stability | incrementality_flag |
| --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress | ggg1_underperformance_4w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 50 | 0.242785 | 1.000000 | INCREMENTAL_SEQUENCE_SIGNAL |
| stress_new_state | stress_transition_8w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 47 | 0.220952 | 0.666667 | INCREMENTAL_SEQUENCE_SIGNAL |
| stress_memory_neutral | stress_transition_4w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 117 | 0.174456 | 1.000000 | INCREMENTAL_SEQUENCE_SIGNAL |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_8w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 42 | 0.167292 | 0.666667 | INCREMENTAL_SEQUENCE_SIGNAL |
| stress_memory_neutral | stress_transition_8w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 117 | 0.132936 | 0.666667 | INCREMENTAL_SEQUENCE_SIGNAL |
| stress_new_state | stress_transition_4w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 47 | 0.126448 | 0.666667 | INCREMENTAL_SEQUENCE_SIGNAL |
| high_transition_instability | recovery_quality_8w | NEEDS_TRIPLE_BARRIER_VALIDATION | 227 | 0.073313 | 0.666667 | INSUFFICIENT_EVIDENCE |
| stress_new_state | ggg1_tail_risk_4w | NEEDS_TRIPLE_BARRIER_VALIDATION | 47 | 0.072313 | 1.000000 | INSUFFICIENT_EVIDENCE |
| high_transition_instability | recovery_quality_4w | NEEDS_TRIPLE_BARRIER_VALIDATION | 227 | 0.063877 | 1.000000 | INSUFFICIENT_EVIDENCE |
| stress_new_state | ggg1_underperformance_4w | NEEDS_TRIPLE_BARRIER_VALIDATION | 47 | 0.046189 | 0.666667 | INSUFFICIENT_EVIDENCE |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_4w | PROMISING_RECOVERY_QUALITY_SIGNAL | 42 | 0.119048 | 0.666667 | INCREMENTAL_SEQUENCE_SIGNAL |
| refined_neutral_deteriorating | stress_transition_4w | PROMISING_STRESS_WARNING_SIGNAL | 169 | 0.123174 | 1.000000 | DUPLICATES_CURRENT_STATE_ENGINE |
| calm_old_low_stress | ggg1_tail_risk_4w | PROMISING_STRESS_WARNING_SIGNAL | 50 | 0.113165 | 1.000000 | INCREMENTAL_SEQUENCE_SIGNAL |
| refined_neutral_deteriorating | ggg1_underperformance_4w | PROMISING_STRESS_WARNING_SIGNAL | 169 | 0.109767 | 1.000000 | DUPLICATES_CURRENT_STATE_ENGINE |
| refined_neutral_deteriorating | stress_transition_8w | PROMISING_STRESS_WARNING_SIGNAL | 167 | 0.092146 | 0.666667 | DUPLICATES_CURRENT_STATE_ENGINE |

## Explicit Signal Definitions
| signal_name | source_rule | priority | intended_use | rule_formula | causal_ok | sss_targets | sss_max_precision_lift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | calm_old_low_stress | primary | GGG1 weak-window warning | state_lag1 == 'calm_trend' and state_age_lag1 >= 14 and stress_count_last_13w == 0 | True | ggg1_tail_risk_4w; ggg1_underperformance_4w | 0.242785 |
| stress_new_state_signal | stress_new_state | primary | stress-transition warning | state_lag1 == 'stressed_panic' and state_age_lag1 <= 2 | True | ggg1_tail_risk_4w; ggg1_underperformance_4w; stress_transition_4w; stress_transition_8w | 0.220952 |
| stress_memory_neutral_signal | stress_memory_neutral | primary | neutral-after-stress warning | state_lag1 == 'neutral_mixed' and stress_count_last_13w > 0 | True | stress_transition_4w; stress_transition_8w | 0.174456 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | qqq_efa_spy_trend_after_calm_or_recovery | primary | re-risking quality filter | qqq_active_int_efa_spy_strength_x_market_trend_lag1 > 0.05 and (state_lag1 == 'calm_trend' or recovery_count_last_13w > 0) | True | recovery_quality_4w; recovery_quality_8w | 0.167292 |
| high_transition_instability_signal | high_transition_instability | watchlist | transition-instability warning | state_changes_last_8w >= 3 | True | recovery_quality_4w; recovery_quality_8w | 0.073313 |
| refined_neutral_deteriorating_signal | refined_neutral_deteriorating | watchlist | Layer 2B deterioration benchmark comparison | refined_state_lag1 == 'neutral_deteriorating' | True | ggg1_underperformance_4w; stress_transition_4w; stress_transition_8w | 0.123174 |

## Signal Panel Summary
Signal panel rows: 1,110. Date range: 2005-01-07 to 2026-04-10.
| signal_name | event_count | event_frequency |
| --- | --- | --- |
| calm_old_low_stress_signal | 50 | 0.045045 |
| stress_new_state_signal | 49 | 0.044144 |
| stress_memory_neutral_signal | 119 | 0.107207 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 44 | 0.039640 |
| high_transition_instability_signal | 256 | 0.230631 |
| refined_neutral_deteriorating_signal | 171 | 0.154054 |

## Leakage Checks
| check | status | detail |
| --- | --- | --- |
| all_signal_inputs_lagged_or_trailing | PASS | Formulas use state_lag1, refined_state_lag1, lagged QQQ activity, trailing stress/recovery counts, trailing state changes, and lagged dwell age. |
| no_future_state_features | PASS | Signal panel excludes future regime labels; current market_state/refined_state retained only for diagnostics and same-state baselines. |
| no_forward_returns_as_features | PASS | Signal panel does not include forward return, target, or future path columns. |
| no_random_splits | PASS | Validation uses deterministic calendar subperiods and pre-2016/2016-forward holdout comparisons. |
| sss_queue_filter | PASS | Only SSS high-priority/promising rules and watchlist NEEDS_TRIPLE_BARRIER_VALIDATION rules were converted. |
| production_shadow_ggg1_unchanged | PASS | Script reads production, shadow, and GGG1 artifacts only; it creates no strategy variants or portfolio candidates. |

## Event Validation Summary
| signal_name | target | event_count | target_positive_rate_during_event | unconditional_positive_rate | same_lagged_state_positive_rate | precision_lift_vs_all_weeks | precision_lift_vs_same_lagged_state | avg_forward_return_during_event | return_lift_vs_same_lagged_state | event_starts_per_year |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | recovery_quality_8w | 42 | 0.666667 | 0.499374 | 0.510225 | 0.167292 | 0.156442 | 0.019187 | 0.005412 | 0.799852 |
| calm_old_low_stress_signal | ggg1_underperformance_4w | 50 | 0.920000 | 0.677215 | 0.776271 | 0.242785 | 0.143729 | 0.000139 | -0.005771 | 0.282301 |
| refined_neutral_deteriorating_signal | ggg1_underperformance_4w | 169 | 0.786982 | 0.677215 | 0.643585 | 0.109767 | 0.143398 | 0.005615 | 0.000521 | 2.258405 |
| stress_memory_neutral_signal | stress_transition_4w | 117 | 0.282051 | 0.107595 | 0.150713 | 0.174456 | 0.131338 | 0.005254 | 0.000159 | 1.882004 |
| stress_new_state_signal | stress_transition_8w | 47 | 0.404255 | 0.183303 | 0.273128 | 0.220952 | 0.131128 | 0.006263 | -0.000838 | 1.458553 |
| stress_new_state_signal | ggg1_tail_risk_4w | 47 | 0.319149 | 0.246835 | 0.198238 | 0.072313 | 0.120911 | 0.001709 | -0.001274 | 1.458553 |
| stress_new_state_signal | recovery_quality_8w | 13 | 0.538462 | 0.499374 | 0.444444 | 0.039087 | 0.094017 | 0.004815 | -0.000231 | 1.458553 |
| stress_new_state_signal | stress_transition_4w | 47 | 0.234043 | 0.107595 | 0.140969 | 0.126448 | 0.093073 | 0.001709 | -0.001274 | 1.458553 |
| stress_memory_neutral_signal | stress_transition_8w | 117 | 0.316239 | 0.183303 | 0.225873 | 0.132936 | 0.090367 | 0.008474 | -0.001626 | 1.882004 |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | 50 | 0.360000 | 0.246835 | 0.271186 | 0.113165 | 0.088814 | 0.000139 | -0.005771 | 0.282301 |
| refined_neutral_deteriorating_signal | stress_transition_4w | 169 | 0.230769 | 0.107595 | 0.150713 | 0.123174 | 0.080056 | 0.005615 | 0.000521 | 2.258405 |
| stress_memory_neutral_signal | recovery_quality_8w | 100 | 0.520000 | 0.499374 | 0.462121 | 0.020626 | 0.057879 | 0.009863 | -0.002262 | 1.882004 |
| stress_memory_neutral_signal | ggg1_underperformance_4w | 117 | 0.700855 | 0.677215 | 0.643585 | 0.023640 | 0.057270 | 0.005254 | 0.000159 | 1.882004 |
| high_transition_instability_signal | recovery_quality_8w | 227 | 0.572687 | 0.499374 | 0.518159 | 0.073313 | 0.054528 | 0.017732 | 0.003183 | 2.117255 |
| refined_neutral_deteriorating_signal | stress_transition_8w | 167 | 0.275449 | 0.183303 | 0.225873 | 0.092146 | 0.049576 | 0.008384 | -0.001716 | 2.258405 |
| calm_old_low_stress_signal | stress_transition_8w | 50 | 0.120000 | 0.183303 | 0.071186 | -0.063303 | 0.048814 | 0.008424 | -0.002725 | 0.282301 |
| refined_neutral_deteriorating_signal | ggg1_tail_risk_4w | 169 | 0.307692 | 0.246835 | 0.260692 | 0.060857 | 0.047000 | 0.005615 | 0.000521 | 2.258405 |
| high_transition_instability_signal | ggg1_underperformance_4w | 255 | 0.701961 | 0.677215 | 0.655789 | 0.024746 | 0.046171 | 0.009393 | 0.002897 | 2.117255 |
| calm_old_low_stress_signal | stress_transition_4w | 50 | 0.080000 | 0.107595 | 0.033898 | -0.027595 | 0.046102 | 0.000139 | -0.005771 | 0.282301 |
| stress_new_state_signal | ggg1_underperformance_4w | 47 | 0.723404 | 0.677215 | 0.682819 | 0.046189 | 0.040585 | 0.001709 | -0.001274 | 1.458553 |
| refined_neutral_deteriorating_signal | recovery_quality_8w | 151 | 0.470199 | 0.499374 | 0.462121 | -0.029176 | 0.008077 | 0.009188 | -0.002937 | 2.258405 |
| high_transition_instability_signal | stress_transition_4w | 255 | 0.090196 | 0.107595 | 0.099921 | -0.017399 | -0.009725 | 0.009393 | 0.002897 | 2.117255 |
| stress_memory_neutral_signal | ggg1_tail_risk_4w | 117 | 0.247863 | 0.246835 | 0.260692 | 0.001028 | -0.012829 | 0.005254 | 0.000159 | 1.882004 |
| high_transition_instability_signal | ggg1_tail_risk_4w | 255 | 0.231373 | 0.246835 | 0.249756 | -0.015463 | -0.018383 | 0.009393 | 0.002897 | 2.117255 |

## Target Matrix
| signal_name | event_count__false_recovery_label | event_count__ggg1_tail_risk_4w | event_count__ggg1_underperformance_4w | event_count__recovery_quality_4w | event_count__recovery_quality_8w | event_count__stress_transition_4w | event_count__stress_transition_8w | precision_lift_vs_all_weeks__false_recovery_label | precision_lift_vs_all_weeks__ggg1_tail_risk_4w | precision_lift_vs_all_weeks__ggg1_underperformance_4w | precision_lift_vs_all_weeks__recovery_quality_4w | precision_lift_vs_all_weeks__recovery_quality_8w | precision_lift_vs_all_weeks__stress_transition_4w | precision_lift_vs_all_weeks__stress_transition_8w | precision_lift_vs_same_lagged_state__false_recovery_label | precision_lift_vs_same_lagged_state__ggg1_tail_risk_4w | precision_lift_vs_same_lagged_state__ggg1_underperformance_4w |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | 0 | 50 | 50 | 50 | 50 | 50 | 50 |  | 0.113165 | 0.242785 | -0.020000 | -0.139374 | -0.027595 | -0.063303 |  | 0.088814 | 0.143729 |
| high_transition_instability_signal | 71 | 255 | 255 | 227 | 227 | 255 | 255 | -0.041813 | -0.015463 | 0.024746 | 0.063877 | 0.073313 | -0.017399 | -0.042127 | -0.050243 | -0.018383 | 0.046171 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 16 | 44 | 44 | 42 | 42 | 44 | 44 | -0.031250 | -0.019563 | -0.018124 | 0.119048 | 0.167292 | -0.084868 | -0.115121 | -0.105548 | -0.043913 | -0.032526 |
| refined_neutral_deteriorating_signal | 16 | 169 | 169 | 152 | 151 | 169 | 167 | 0.281250 | 0.060857 | 0.109767 | -0.026316 | -0.029176 | 0.123174 | 0.092146 | 0.169643 | 0.047000 | 0.143398 |
| stress_memory_neutral_signal | 21 | 117 | 117 | 100 | 100 | 117 | 117 | 0.242560 | 0.001028 | 0.023640 | -0.030000 | 0.020626 | 0.174456 | 0.132936 | 0.130952 | -0.012829 | 0.057270 |
| stress_new_state_signal | 4 | 47 | 47 | 13 | 13 | 47 | 47 | 0.218750 | 0.072313 | 0.046189 | -0.192308 | 0.039087 | 0.126448 | 0.220952 | 0.000000 | 0.120911 | 0.040585 |

## Triple-Barrier / Path Outcome Findings
| signal_name | horizon_weeks | signal_intended_direction | event_path_count | event_upper_hit_rate | event_lower_hit_rate | event_avg_end_return | risk_warning_success_rate_lift_vs_same_lagged_state | risk_on_success_rate_lift_vs_same_lagged_state | avg_end_return_lift_vs_same_lagged_state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | 4 | risk_warning | 50 | 0.240000 | 0.220000 | 0.000139 | 0.074913 | -0.035958 | -0.005936 |
| calm_old_low_stress_signal | 8 | risk_warning | 50 | 0.300000 | 0.180000 | 0.008424 | 0.065366 | -0.094286 | -0.003036 |
| calm_old_low_stress_signal | 13 | risk_warning | 50 | 0.300000 | 0.180000 | 0.015111 | 0.025366 | -0.145645 | -0.004615 |
| high_transition_instability_signal | 4 | risk_warning | 248 | 0.362903 | 0.153226 | 0.009571 | -0.042712 | 0.052064 | 0.003687 |
| high_transition_instability_signal | 8 | risk_warning | 248 | 0.419355 | 0.149194 | 0.016588 | -0.031433 | 0.055947 | 0.004971 |
| high_transition_instability_signal | 13 | risk_warning | 248 | 0.479839 | 0.125000 | 0.024594 | -0.012585 | 0.033382 | 0.005217 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 4 | risk_on_confirmation | 42 | 0.547619 | 0.095238 | 0.009575 | -0.068881 | 0.043893 | 0.003624 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 8 | risk_on_confirmation | 42 | 0.571429 | 0.071429 | 0.019187 | -0.108400 | 0.079980 | 0.007332 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 13 | risk_on_confirmation | 41 | 0.585366 | 0.024390 | 0.031236 | -0.135300 | 0.080324 | 0.011334 |
| refined_neutral_deteriorating_signal | 4 | risk_warning | 169 | 0.360947 | 0.147929 | 0.005615 | 0.000433 | -0.009574 | -0.000231 |
| refined_neutral_deteriorating_signal | 8 | risk_warning | 167 | 0.371257 | 0.167665 | 0.008384 | 0.049387 | -0.061876 | -0.003160 |
| refined_neutral_deteriorating_signal | 13 | risk_warning | 167 | 0.365269 | 0.167665 | 0.015595 | 0.066114 | -0.093125 | -0.003673 |
| stress_memory_neutral_signal | 4 | risk_warning | 114 | 0.377193 | 0.201754 | 0.005195 | 0.036039 | -0.031529 | -0.000652 |
| stress_memory_neutral_signal | 8 | risk_warning | 114 | 0.421053 | 0.219298 | 0.008322 | 0.043609 | -0.043860 | -0.003222 |
| stress_memory_neutral_signal | 13 | risk_warning | 114 | 0.491228 | 0.228070 | 0.015765 | 0.079560 | -0.085141 | -0.003503 |
| stress_new_state_signal | 4 | risk_warning | 45 | 0.133333 | 0.222222 | 0.001193 | 0.133333 | -0.128889 | -0.001697 |
| stress_new_state_signal | 8 | risk_warning | 45 | 0.155556 | 0.200000 | 0.005469 | 0.084444 | -0.066667 | -0.001481 |
| stress_new_state_signal | 13 | risk_warning | 45 | 0.222222 | 0.155556 | 0.011498 | 0.057778 | -0.004444 | -0.000180 |

Path asymmetry:
| signal_name | horizon_weeks | signal_intended_direction | event_lower_minus_upper_hit_rate | all_weeks_lower_minus_upper_hit_rate | same_lagged_state_lower_minus_upper_hit_rate | preferred_success_metric | preferred_success_rate | preferred_success_lift_vs_all_weeks | preferred_success_lift_vs_same_lagged_state | avg_end_return_lift_vs_same_lagged_state | avg_min_path_return_lift_vs_same_lagged_state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | 4 | risk_warning | -0.020000 | -0.142996 | -0.153310 | risk_warning_success_rate | 0.500000 | 0.063230 | 0.074913 | -0.005936 | -0.009512 |
| calm_old_low_stress_signal | 8 | risk_warning | -0.120000 | -0.215820 | -0.233449 | risk_warning_success_rate | 0.480000 | 0.048359 | 0.065366 | -0.003036 | -0.012983 |
| calm_old_low_stress_signal | 13 | risk_warning | -0.120000 | -0.275761 | -0.320557 | risk_warning_success_rate | 0.440000 | 0.051384 | 0.025366 | -0.004615 | -0.011053 |
| high_transition_instability_signal | 4 | risk_warning | -0.209677 | -0.142996 | -0.166509 | risk_warning_success_rate | 0.403226 | -0.033545 | -0.042712 | 0.003687 | 0.002265 |
| high_transition_instability_signal | 8 | risk_warning | -0.270161 | -0.215820 | -0.216462 | risk_warning_success_rate | 0.407258 | -0.024383 | -0.031433 | 0.004971 | 0.002617 |
| high_transition_instability_signal | 13 | risk_warning | -0.354839 | -0.275761 | -0.263991 | risk_warning_success_rate | 0.362903 | -0.025713 | -0.012585 | 0.005217 | 0.002694 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 4 | risk_on_confirmation | -0.452381 | -0.142996 | -0.171833 | risk_on_success_rate | 0.690476 | 0.041644 | 0.043893 | 0.003624 | 0.002497 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 8 | risk_on_confirmation | -0.500000 | -0.215820 | -0.222586 | risk_on_success_rate | 0.761905 | 0.079288 | 0.079980 | 0.007332 | 0.004609 |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | 13 | risk_on_confirmation | -0.560976 | -0.275761 | -0.271076 | risk_on_success_rate | 0.829268 | 0.098159 | 0.080324 | 0.011334 | 0.007121 |
| refined_neutral_deteriorating_signal | 4 | risk_warning | -0.213018 | -0.142996 | -0.181604 | risk_warning_success_rate | 0.455621 | 0.018851 | 0.000433 | -0.000231 | 0.000652 |
| refined_neutral_deteriorating_signal | 8 | risk_warning | -0.203593 | -0.215820 | -0.211905 | risk_warning_success_rate | 0.497006 | 0.065365 | 0.049387 | -0.003160 | 0.000347 |
| refined_neutral_deteriorating_signal | 13 | risk_warning | -0.197605 | -0.275761 | -0.243373 | risk_warning_success_rate | 0.425150 | 0.036533 | 0.066114 | -0.003673 | -0.000723 |
| stress_memory_neutral_signal | 4 | risk_warning | -0.175439 | -0.142996 | -0.181604 | risk_warning_success_rate | 0.491228 | 0.054458 | 0.036039 | -0.000652 | 0.001218 |
| stress_memory_neutral_signal | 8 | risk_warning | -0.201754 | -0.215820 | -0.211905 | risk_warning_success_rate | 0.491228 | 0.059587 | 0.043609 | -0.003222 | 0.000421 |
| stress_memory_neutral_signal | 13 | risk_warning | -0.263158 | -0.275761 | -0.243373 | risk_warning_success_rate | 0.438596 | 0.049980 | 0.079560 | -0.003503 | -0.001246 |
| stress_new_state_signal | 4 | risk_warning | 0.088889 | -0.142996 | -0.004444 | risk_warning_success_rate | 0.555556 | 0.118785 | 0.133333 | -0.001697 | -0.003368 |
| stress_new_state_signal | 8 | risk_warning | 0.044444 | -0.215820 | -0.115556 | risk_warning_success_rate | 0.511111 | 0.079470 | 0.084444 | -0.001481 | -0.003230 |
| stress_new_state_signal | 13 | risk_warning | -0.066667 | -0.275761 | -0.182222 | risk_warning_success_rate | 0.488889 | 0.100273 | 0.057778 | -0.000180 | -0.004075 |

## Subperiod / Holdout Stability
Pre-2016 versus 2016-forward holdout diagnostics:
| signal_name | target | train_period | holdout_period | train_event_count | holdout_event_count | train_precision_lift_vs_same_lagged_state | holdout_precision_lift_vs_same_lagged_state | train_return_lift_vs_same_lagged_state | holdout_return_lift_vs_same_lagged_state | sign_consistent | enough_holdout_events | triple_barrier_preferred_success_lift_vs_same_lagged_state | holdout_validation_flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | recovery_quality_8w | pre_2016 | 2016_forward | 22 | 20 | 0.067280 | 0.241935 | 0.004435 | 0.005317 | True | True | 0.079980 | PASS |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | recovery_quality_4w | pre_2016 | 2016_forward | 22 | 20 | 0.064880 | 0.157275 | 0.003885 | 0.001618 | True | True | 0.043893 | PASS |
| calm_old_low_stress_signal | ggg1_underperformance_4w | pre_2016 | 2016_forward | 20 | 30 | 0.136220 | 0.147619 | -0.000597 | -0.008979 | True | True | 0.074913 | PASS |
| stress_memory_neutral_signal | false_recovery_label | pre_2016 | 2016_forward | 9 | 12 | 0.101010 | 0.147059 | -0.002736 | -0.007332 | True | True | 0.043609 | PASS |
| stress_new_state_signal | ggg1_tail_risk_4w | pre_2016 | 2016_forward | 32 | 15 | 0.113662 | 0.100000 | -0.003490 | 0.003934 | True | True | 0.133333 | PASS |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | pre_2016 | 2016_forward | 20 | 30 | 0.158661 | 0.044048 | -0.000597 | -0.008979 | True | True | 0.074913 | PASS |
| stress_new_state_signal | stress_transition_4w | pre_2016 | 2016_forward | 32 | 15 | 0.055863 | 0.040351 | -0.003490 | 0.003934 | True | True | 0.133333 | PASS |
| refined_neutral_deteriorating_signal | stress_transition_4w | pre_2016 | 2016_forward | 96 | 73 | 0.118197 | 0.033934 | 0.000447 | 0.000292 | True | True | 0.000433 | PASS |
| high_transition_instability_signal | recovery_quality_8w | pre_2016 | 2016_forward | 124 | 103 | 0.076464 | 0.032019 | 0.002034 | 0.004213 | True | True | -0.031433 | PASS |
| refined_neutral_deteriorating_signal | ggg1_underperformance_4w | pre_2016 | 2016_forward | 96 | 73 | 0.231930 | 0.025033 | 0.000447 | 0.000292 | True | True | 0.000433 | FAIL_OR_WEAK |
| stress_new_state_signal | stress_transition_8w | pre_2016 | 2016_forward | 32 | 15 | 0.075774 | 0.005263 | -0.001466 | 0.001064 | True | True | 0.084444 | FAIL_OR_WEAK |
| refined_neutral_deteriorating_signal | stress_transition_8w | pre_2016 | 2016_forward | 96 | 71 | 0.092049 | -0.003430 | -0.002362 | -0.001293 | False | True | 0.049387 | FAIL_OR_WEAK |
| high_transition_instability_signal | ggg1_tail_risk_4w | pre_2016 | 2016_forward | 146 | 109 | -0.006500 | -0.035084 | 0.002411 | 0.003029 | False | True | -0.042712 | FAIL_OR_WEAK |
| high_transition_instability_signal | stress_transition_4w | pre_2016 | 2016_forward | 146 | 109 | 0.011390 | -0.051509 | 0.002411 | 0.003029 | False | True | -0.042712 | FAIL_OR_WEAK |
| stress_memory_neutral_signal | stress_transition_4w | pre_2016 | 2016_forward | 74 | 43 | 0.245450 | -0.070240 | -0.000697 | 0.002053 | False | True | 0.036039 | FAIL_OR_WEAK |
| stress_memory_neutral_signal | stress_transition_8w | pre_2016 | 2016_forward | 74 | 43 | 0.221272 | -0.140017 | -0.002539 | 0.000469 | False | True | 0.043609 | FAIL_OR_WEAK |

Calendar/state/path stability sample:
| signal_name | target | period | valid_observations | event_count | event_frequency | precision | baseline_precision | same_lagged_state_precision | precision_lift_vs_all_weeks | precision_lift_vs_same_lagged_state | avg_forward_return | baseline_avg_forward_return | same_lagged_state_avg_forward_return | return_lift_vs_all_weeks | return_lift_vs_same_lagged_state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | 2010_2015 | 313 | 20 | 0.063898 | 0.450000 | 0.313099 | 0.288889 | 0.136901 | 0.161111 | 0.008015 | 0.004570 | 0.007819 | 0.003445 | 0.000196 |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | 2016_2020 | 261 | 12 | 0.045977 | 0.500000 | 0.218391 | 0.320000 | 0.281609 | 0.180000 | -0.022746 | 0.004926 | -0.001198 | -0.027672 | -0.021548 |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | 2016_forward | 533 | 30 | 0.056285 | 0.300000 | 0.238274 | 0.255952 | 0.061726 | 0.044048 | -0.005112 | 0.006229 | 0.003868 | -0.011341 | -0.008979 |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | 2021_2026 | 272 | 18 | 0.066176 | 0.166667 | 0.257353 | 0.204301 | -0.090686 | -0.037634 | 0.006644 | 0.007480 | 0.007953 | -0.000836 | -0.001308 |
| calm_old_low_stress_signal | ggg1_tail_risk_4w | pre_2016 | 573 | 20 | 0.034904 | 0.450000 | 0.254799 | 0.291339 | 0.195201 | 0.158661 | 0.008015 | 0.004762 | 0.008611 | 0.003253 | -0.000597 |
| calm_old_low_stress_signal | ggg1_underperformance_4w | 2010_2015 | 313 | 20 | 0.063898 | 0.900000 | 0.821086 | 0.844444 | 0.078914 | 0.055556 | 0.008015 | 0.004570 | 0.007819 | 0.003445 | 0.000196 |
| calm_old_low_stress_signal | ggg1_underperformance_4w | 2016_2020 | 261 | 12 | 0.045977 | 0.916667 | 0.681992 | 0.786667 | 0.234674 | 0.130000 | -0.022746 | 0.004926 | -0.001198 | -0.027672 | -0.021548 |
| calm_old_low_stress_signal | ggg1_underperformance_4w | 2016_forward | 533 | 30 | 0.056285 | 0.933333 | 0.671670 | 0.785714 | 0.261664 | 0.147619 | -0.005112 | 0.006229 | 0.003868 | -0.011341 | -0.008979 |
| calm_old_low_stress_signal | ggg1_underperformance_4w | 2021_2026 | 272 | 18 | 0.066176 | 0.944444 | 0.661765 | 0.784946 | 0.282680 | 0.159498 | 0.006644 | 0.007480 | 0.007953 | -0.000836 | -0.001308 |
| calm_old_low_stress_signal | ggg1_underperformance_4w | pre_2016 | 573 | 20 | 0.034904 | 0.900000 | 0.682373 | 0.763780 | 0.217627 | 0.136220 | 0.008015 | 0.004762 | 0.008611 | 0.003253 | -0.000597 |
| high_transition_instability_signal | ggg1_tail_risk_4w | 2010_2015 | 313 | 95 | 0.303514 | 0.273684 | 0.313099 | 0.316779 | -0.039415 | -0.043095 | 0.005095 | 0.004570 | 0.003836 | 0.000525 | 0.001259 |
| high_transition_instability_signal | ggg1_tail_risk_4w | 2016_2020 | 261 | 65 | 0.249042 | 0.230769 | 0.218391 | 0.232327 | 0.012378 | -0.001558 | 0.011206 | 0.004926 | 0.006718 | 0.006281 | 0.004488 |
| high_transition_instability_signal | ggg1_tail_risk_4w | 2016_forward | 533 | 109 | 0.204503 | 0.211009 | 0.238274 | 0.246093 | -0.027265 | -0.035084 | 0.011340 | 0.006229 | 0.008311 | 0.005111 | 0.003029 |
| high_transition_instability_signal | ggg1_tail_risk_4w | 2021_2026 | 272 | 44 | 0.161765 | 0.181818 | 0.257353 | 0.253906 | -0.075535 | -0.072088 | 0.011538 | 0.007480 | 0.009595 | 0.004058 | 0.001943 |
| high_transition_instability_signal | ggg1_tail_risk_4w | pre_2016 | 573 | 146 | 0.254799 | 0.246575 | 0.254799 | 0.253075 | -0.008224 | -0.006500 | 0.007940 | 0.004762 | 0.005529 | 0.003178 | 0.002411 |
| high_transition_instability_signal | recovery_quality_8w | 2010_2015 | 279 | 81 | 0.290323 | 0.444444 | 0.422939 | 0.417438 | 0.021505 | 0.027007 | 0.007690 | 0.010246 | 0.009613 | -0.002555 | -0.001922 |
| high_transition_instability_signal | recovery_quality_8w | 2016_2020 | 199 | 59 | 0.296482 | 0.627119 | 0.557789 | 0.600836 | 0.069330 | 0.026282 | 0.021826 | 0.009512 | 0.013073 | 0.012314 | 0.008752 |
| high_transition_instability_signal | recovery_quality_8w | 2016_forward | 416 | 103 | 0.247596 | 0.611650 | 0.540865 | 0.579632 | 0.070785 | 0.032019 | 0.021164 | 0.014000 | 0.016951 | 0.007164 | 0.004213 |
| high_transition_instability_signal | recovery_quality_8w | 2021_2026 | 217 | 44 | 0.202765 | 0.590909 | 0.525346 | 0.572462 | 0.065563 | 0.018447 | 0.020277 | 0.018117 | 0.020849 | 0.002160 | -0.000572 |
| high_transition_instability_signal | recovery_quality_8w | pre_2016 | 383 | 124 | 0.323760 | 0.540323 | 0.454308 | 0.463858 | 0.086014 | 0.076464 | 0.014880 | 0.012125 | 0.012847 | 0.002755 | 0.002034 |
| high_transition_instability_signal | stress_transition_4w | 2010_2015 | 313 | 95 | 0.303514 | 0.157895 | 0.169329 | 0.181366 | -0.011434 | -0.023472 | 0.005095 | 0.004570 | 0.003836 | 0.000525 | 0.001259 |
| high_transition_instability_signal | stress_transition_4w | 2016_2020 | 261 | 65 | 0.249042 | 0.015385 | 0.049808 | 0.055244 | -0.034424 | -0.039860 | 0.011206 | 0.004926 | 0.006718 | 0.006281 | 0.004488 |
| high_transition_instability_signal | stress_transition_4w | 2016_forward | 533 | 109 | 0.204503 | 0.009174 | 0.056285 | 0.060684 | -0.047111 | -0.051509 | 0.011340 | 0.006229 | 0.008311 | 0.005111 | 0.003029 |
| high_transition_instability_signal | stress_transition_4w | 2021_2026 | 272 | 44 | 0.161765 | 0.000000 | 0.062500 | 0.061688 | -0.062500 | -0.061688 | 0.011538 | 0.007480 | 0.009595 | 0.004058 | 0.001943 |

## Redundancy / Incrementality Findings
| signal_name | best_target | event_count | event_frequency | precision_lift_vs_all_weeks | precision_lift_vs_same_lagged_state | return_lift_vs_same_lagged_state | max_abs_corr_market_state_engine | closest_market_state_feature | max_abs_corr_refined_state_engine | closest_refined_state_feature | max_abs_corr_layer2b_numeric | closest_layer2b_feature | max_abs_corr_ooo_signals | closest_ooo_feature | max_abs_corr_qqq_signals | closest_qqq_feature | incrementality_flag | adds_timing_beyond_current_state | actionable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | recovery_quality_8w | 42 | 0.052566 | 0.167292 | 0.156442 | 0.005412 | 0.273828 | path2_lag_recovery_fragile->recovery_fragile | 0.248557 | refined_state_lag1_recovery_fragile | 0.169410 | l2b_transition_persistence_prob_lag1 | 0.481190 | ooo3event_efa_spy_market_trend_confirmed_top20_event_lag1 | 0.579791 | qqq_any_shortlist_rule_active_lag1 | INCREMENTAL_TO_LAYER2B | True | True |
| calm_old_low_stress_signal | ggg1_underperformance_4w | 50 | 0.045208 | 0.242785 | 0.143729 | -0.005771 | 0.464691 | state_dwell_bucket_lag1_old_14w_plus | 0.360994 | refined_state_lag1_calm_trend | 0.344460 | l2b_transition_good_state_prob_lag1 | 0.228434 | ooo3event_market_trend_recent_stress_filtered_event | 0.164536 | qqq_active_int_efa_spy_strength_x_market_trend | INCREMENTAL_TO_LAYER2B | True | True |
| refined_neutral_deteriorating_signal | ggg1_underperformance_4w | 169 | 0.152803 | 0.109767 | 0.143398 | 0.000521 | 0.477402 | state_lag1_neutral_mixed | 1.000000 | refined_state_lag1_neutral_deteriorating | 0.867554 | l2b_deterioration_rank_neutral_mixed_lag1 | 0.396676 | ooo2_breadth_ret13_positive_x_neutral_mixed_signal | 0.089290 | qqq_active_int_efa_spy_strength_x_market_trend | MOSTLY_REFINED_STATE_PROXY | True | False |
| stress_memory_neutral_signal | stress_transition_4w | 117 | 0.105787 | 0.174456 | 0.131338 | 0.000159 | 0.428997 | path2_lag_stressed_panic->neutral_mixed | 0.529703 | refined_state_lag1_neutral_deteriorating | 0.556224 | l2b_deterioration_rank_neutral_mixed_lag1 | 0.357690 | ooo2_recent_stress_26w_signal_lag1 | 0.032342 | qqq_active_int_efa_spy_strength_x_market_trend | INCREMENTAL_TO_LAYER2B | True | True |
| stress_new_state_signal | stress_transition_8w | 47 | 0.042650 | 0.220952 | 0.131128 | -0.000838 | 0.748557 | path2_lag_neutral_mixed->stressed_panic | 0.421513 | refined_state_lag1_stressed_panic | 0.397319 | l2b_transition_non_stress_prob_lag1 | 0.424364 | ooo2_breadth_ret13_positive_x_stressed_panic_signal | 0.447214 | qqq_interaction_success_label | INCREMENTAL_TO_LAYER2B | True | True |
| high_transition_instability_signal | recovery_quality_8w | 227 | 0.284105 | 0.073313 | 0.054528 | 0.003183 | 0.410945 | state_dwell_bucket_lag1_new_state_1_2w | 0.173865 | refined_state_lag1_recovery_fragile | 0.250898 | l2b_transition_persistence_prob_lag1 | 0.235335 | ooo2_recent_stress_26w_signal_lag1 | 0.089482 | qqq_active_int_market_trend_x_mom13 | INCREMENTAL_TO_LAYER2B | True | True |

Top state/Layer2B overlaps:
| signal_name | comparison_group | comparison_feature | corr | abs_corr | event_overlap_rate | jaccard_overlap |
| --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | market_state_engine | state_dwell_bucket_lag1_old_14w_plus | 0.464691 | 0.464691 | 1.000000 | 0.251256 |
| calm_old_low_stress_signal | market_state_engine | path2_lag_calm_trend->calm_trend | 0.399726 | 0.399726 | 1.000000 | 0.197628 |
| calm_old_low_stress_signal | market_state_engine | state_lag2_calm_trend | 0.360994 | 0.360994 | 1.000000 | 0.169492 |
| calm_old_low_stress_signal | market_state_engine | state_lag1_calm_trend | 0.360994 | 0.360994 | 1.000000 | 0.169492 |
| calm_old_low_stress_signal | refined_state_engine | refined_state_lag1_calm_trend | 0.360994 | 0.360994 | 1.000000 | 0.169492 |
| calm_old_low_stress_signal | market_state_engine | state_lag4_calm_trend | 0.360994 | 0.360994 | 1.000000 | 0.169492 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_transition_good_state_prob_lag1 | 0.344460 | 0.344460 | 1.000000 | 0.187266 |
| calm_old_low_stress_signal | market_state_engine | market_state_calm_trend | 0.301995 | 0.301995 | 0.880000 | 0.146179 |
| calm_old_low_stress_signal | refined_state_engine | refined_state_calm_trend | 0.301995 | 0.301995 | 0.880000 | 0.146179 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_risk_regime_score_lag1 | -0.242276 | 0.242276 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | layer2b_numeric | risk_regime_score | -0.222440 | 0.222440 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_recent_stress_26w_lag1 | -0.210916 | 0.210916 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_defensive_overlay_hint_lag1 | -0.209642 | 0.209642 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_deterioration_z_lag1 | -0.206453 | 0.206453 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | layer2b_numeric | defensive_overlay_hint | -0.200157 | 0.200157 | 0.020000 | 0.002008 |
| calm_old_low_stress_signal | market_state_engine | state_lag2_neutral_mixed | -0.194139 | 0.194139 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | market_state_engine | state_lag1_neutral_mixed | -0.194139 | 0.194139 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | market_state_engine | state_lag4_neutral_mixed | -0.193432 | 0.193432 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_canary_breadth_default_lag1 | 0.193028 | 0.193028 | 0.860000 | 0.087221 |
| calm_old_low_stress_signal | layer2b_numeric | l2b_p_tail_risk_lag1 | -0.189646 | 0.189646 | 0.000000 | 0.000000 |

Top OOO/QQQ overlaps:
| signal_name | comparison_group | comparison_feature | corr | abs_corr | event_overlap_rate | jaccard_overlap |
| --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_recent_stress_filtered_event | 0.228434 | 0.228434 | 1.000000 | 0.094877 |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_recent_stress_filtered_event_lag1 | 0.228346 | 0.228346 | 1.000000 | 0.094877 |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_breadth_confirmed_event_lag1 | 0.211295 | 0.211295 | 0.760000 | 0.106742 |
| calm_old_low_stress_signal | ooo_signals | ooo2_recent_stress_26w_signal | -0.210916 | 0.210916 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ooo_signals | ooo2_recent_stress_26w_signal_lag1 | -0.210820 | 0.210820 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ooo_signals | ooo2_breadth_ret26_positive_signal_lag1 | 0.190727 | 0.190727 | 0.740000 | 0.123333 |
| calm_old_low_stress_signal | ooo_signals | ooo2_breadth_ret26_positive_signal | 0.185205 | 0.185205 | 0.680000 | 0.112211 |
| calm_old_low_stress_signal | ooo_signals | ooo2_breadth_ret13_positive_x_neutral_mixed_signal_lag1 | -0.176638 | 0.176638 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ooo_signals | ooo2_breadth_ret13_positive_x_neutral_mixed_signal | -0.176423 | 0.176423 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_breadth_confirmed_event | 0.173808 | 0.173808 | 0.680000 | 0.094444 |
| calm_old_low_stress_signal | qqq_signals | qqq_active_int_efa_spy_strength_x_market_trend | -0.164536 | 0.164536 | 0.120000 | 0.018750 |
| calm_old_low_stress_signal | qqq_signals | qqq_mean_shortlist_rule_active | -0.164407 | 0.164407 | 0.120000 | 0.018750 |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_calm_neutral_event | 0.161110 | 0.161110 | 1.000000 | 0.069832 |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_calm_neutral_event_lag1 | 0.160982 | 0.160982 | 1.000000 | 0.069832 |
| calm_old_low_stress_signal | qqq_signals | qqq_active_int_efa_spy_strength_x_market_trend_lag1 | -0.150826 | 0.150826 | 0.120000 | 0.018750 |
| calm_old_low_stress_signal | qqq_signals | qqq_mean_shortlist_rule_active_lag1 | -0.149864 | 0.149864 | 0.120000 | 0.018750 |
| calm_old_low_stress_signal | ooo_signals | ooo2_leadlag_EFA_minus_SPY_13w_signal | -0.142154 | 0.142154 | 0.060000 | 0.009288 |
| calm_old_low_stress_signal | ooo_signals | ooo2_leadlag_EFA_minus_SPY_13w_signal_lag1 | -0.129526 | 0.129526 | 0.100000 | 0.015576 |
| calm_old_low_stress_signal | ooo_signals | ooo3event_market_trend_raw_event | 0.115586 | 0.115586 | 1.000000 | 0.057803 |
| calm_old_low_stress_signal | ooo_signals | ooo2_market_trend_positive_signal | 0.115405 | 0.115405 | 1.000000 | 0.057803 |

GGG1 exposure overlaps:
| signal_name | comparison_feature | corr | abs_corr | event_overlap_rate | jaccard_overlap |
| --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | ggg1_sleeve_weight_dual_momentum_topn | 0.279155 | 0.279155 | 0.720000 | 0.122034 |
| calm_old_low_stress_signal | ggg1_sleeve_weight_composite_regime_defense_component | 0.230380 | 0.230380 | 0.720000 | 0.123288 |
| calm_old_low_stress_signal | low_bil_exposure | 0.205295 | 0.205295 | 0.660000 | 0.111864 |
| calm_old_low_stress_signal | ggg1_sleeve_weight_composite_selective_signals | 0.161284 | 0.161284 | 0.420000 | 0.068404 |
| calm_old_low_stress_signal | ggg1_sleeve_weight_cash::BIL | -0.156952 | 0.156952 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ggg1_bil_exposure | -0.156952 | 0.156952 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | high_bil_exposure | -0.125844 | 0.125844 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | low_offense_exposure | -0.125844 | 0.125844 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | high_defense_exposure | -0.125844 | 0.125844 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ggg1_offense_exposure | 0.109781 | 0.109781 | 0.280000 | 0.044304 |
| calm_old_low_stress_signal | ggg1_defense_exposure | -0.109781 | 0.109781 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ggg1_sleeve_weight_taa_10m_sma | 0.096928 | 0.096928 | 0.500000 | 0.081433 |
| calm_old_low_stress_signal | ggg1_sleeve_weight_composite_regime_offense_component | -0.068243 | 0.068243 | 0.000000 | 0.000000 |
| calm_old_low_stress_signal | ggg1_sleeve_weight_cta_trend_long_only | -0.043993 | 0.043993 | 0.020000 | 0.003040 |
| calm_old_low_stress_signal | high_offense_exposure | 0.013876 | 0.013876 | 0.280000 | 0.044304 |
| calm_old_low_stress_signal | low_defense_exposure | 0.013876 | 0.013876 | 0.280000 | 0.044304 |
| high_transition_instability_signal | ggg1_sleeve_weight_composite_regime_offense_component | 0.310569 | 0.310569 | 0.410156 | 0.244755 |
| high_transition_instability_signal | ggg1_sleeve_weight_cta_trend_long_only | 0.226179 | 0.226179 | 0.429688 | 0.258216 |
| high_transition_instability_signal | ggg1_defense_exposure | -0.214963 | 0.214963 | 0.082031 | 0.040856 |
| high_transition_instability_signal | ggg1_offense_exposure | 0.214963 | 0.214963 | 0.363281 | 0.209932 |

## Keep / Reject Decisions
| signal_name | best_target | decision | event_count | precision_lift_vs_same_lagged_state | holdout_precision_lift_vs_same_lagged_state | triple_barrier_success_lift_vs_same_lagged_state | incrementality_flag | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | ggg1_underperformance_4w | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | 50 | 0.143729 | 0.147619 | 0.074913 | INCREMENTAL_TO_LAYER2B | event lift, same-state lift, holdout, path asymmetry, incrementality, and turnover gates passed |
| stress_new_state_signal | stress_transition_4w | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | 47 | 0.093073 | 0.040351 | 0.133333 | INCREMENTAL_TO_LAYER2B | event lift, same-state lift, holdout, path asymmetry, incrementality, and turnover gates passed |
| stress_memory_neutral_signal | stress_transition_4w | KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL | 117 | 0.131338 | -0.070240 | 0.036039 | INCREMENTAL_TO_LAYER2B | useful diagnostic evidence, but one or more pass-through gates failed |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | recovery_quality_8w | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | 42 | 0.156442 | 0.241935 | 0.079980 | INCREMENTAL_TO_LAYER2B | event lift, same-state lift, holdout, path asymmetry, incrementality, and turnover gates passed |
| high_transition_instability_signal | recovery_quality_8w | KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL | 227 | 0.054528 | 0.032019 | -0.031433 | INCREMENTAL_TO_LAYER2B | useful diagnostic evidence, but one or more pass-through gates failed |
| refined_neutral_deteriorating_signal | stress_transition_4w | MOSTLY_DUPLICATIVE | 169 | 0.080056 | 0.033934 | 0.000433 | MOSTLY_REFINED_STATE_PROXY | incrementality check flagged MOSTLY_REFINED_STATE_PROXY |

## Next Phase Queue
| signal_name | decision | best_target | next_phase_task |
| --- | --- | --- | --- |
| calm_old_low_stress_signal | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | ggg1_underperformance_4w | SSS3 controlled GGG1 pass-through test with tiny bounded overlay and explicit no-promotion default |
| stress_new_state_signal | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | stress_transition_4w | SSS3 controlled GGG1 pass-through test with tiny bounded overlay and explicit no-promotion default |
| stress_memory_neutral_signal | KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL | stress_transition_4w | Additional sequence feature engineering or monitoring diagnostics before portfolio use |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | recovery_quality_8w | SSS3 controlled GGG1 pass-through test with tiny bounded overlay and explicit no-promotion default |
| high_transition_instability_signal | KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL | recovery_quality_8w | Additional sequence feature engineering or monitoring diagnostics before portfolio use |

## Final Recommendation
**PROCEED_TO_SSS3_SEQUENCE_PORTFOLIO_PASS_THROUGH**

Reason: At least one explicit sequence signal passed event, holdout, path-asymmetry, incrementality, and turnover gates for a controlled diagnostic pass-through.

## Is Portfolio Pass-Through Justified?
Portfolio pass-through is justified only if at least one signal is classified `KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH`. SSS2 applies that gate after event, same-state, holdout, triple-barrier/path, redundancy, and turnover checks; the keep/reject table above is the authoritative result.

## Exact Prompt Outline For Next Phase
Implement Phase SSS3 as diagnostic-only controlled sequence portfolio pass-through. Use only SSS2 KEEP_FOR_SSS3 signals, apply tiny bounded GGG1 de-risk/re-risk overlays, compare against production/shadow/GGG1, require holdout and bootstrap discipline, and do not promote automatically.

## Resume-Worthy Technical Summary
SSS2 loaded the SSS high-priority and watchlist rule queue, converted six explicit causal lagged sequence signals, and aligned them to the 1,110-week GGG1 state/return panel. It validated event precision against stress-transition, recovery-quality, underperformance, tail-risk, false-recovery, and forward return/path outcomes; ran 4w/8w/13w triple-barrier path checks using lagged 13w GGG1 volatility; tested pre-2016 vs 2016-forward and calendar/state/path stability; checked redundancy against current five-state labels, refined Layer 2B states/probabilities, OOO/QQQ signals, and GGG1 BIL/offense/defense exposure regimes; then classified each signal without creating any portfolio candidate or changing production/shadow/GGG1.
