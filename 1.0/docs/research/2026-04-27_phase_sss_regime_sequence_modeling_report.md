# Phase SSS -- Regime-Sequence Modeling

Date: 2026-04-27

## Commands Executed
- `sed -n '1,360p' docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md`
- `find data/research/phase_qqq_deep_feature_interaction_mining -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf "%s\t" "$(basename "{}")"; wc -l < "{}"'`
- `find data/04_layer2b_risk_regime_engine data/03_layer2a_strategy_logic data/05_layer3_portfolio_construction data/02_layer1_signals -maxdepth 2 -type f | sort | sed -n '1,360p'`
- `tail -n 90 docs/research/project_journey.md`
- `python3 - <<'PY' ...state/portfolio/QQQ/OOO schema summaries...`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md`
- `find data/research/phase_ppp_latent_factor_discovery data/research/phase_ooo_signal_discovery -maxdepth 2 -type f | sort | sed -n '1,220p'`
- `python3 -m py_compile scripts/phase_sss_regime_sequence_modeling.py`
- `python3 scripts/phase_sss_regime_sequence_modeling.py`

## Files Created / Modified
- `scripts/phase_sss_regime_sequence_modeling.py`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_sequence_panel.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_source_audit.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_transition_matrix_1w.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_transition_matrix_4w.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_transition_matrix_8w.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_dwell_distribution.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_age_performance.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_path_performance.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_transition_risk_summary.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_feature_panel.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_feature_manifest.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_leakage_checklist.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_target_panel.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_target_summary.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_walkforward_splits.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_baseline_model_metrics.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_baseline_predictions.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_model_metrics.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_model_predictions.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_model_calibration.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_feature_importance.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_subperiod_stability.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_transition_window_performance.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_extracted_sequence_rules.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_rule_performance.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_state_path_rule_summary.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_qqq_interaction_after_sequence_control.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_ooo_signal_sequence_overlap.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_ggg1_sequence_weakness_diagnostics.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_sequence_incrementality_summary.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_candidate_sequence_signal_shortlist.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_rejected_sequence_rule_log.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_next_phase_queue.csv`
- `data/research/phase_sss_regime_sequence_modeling/sss_next_action_recommendation.csv`
- `docs/research/2026-04-27_phase_sss_regime_sequence_modeling_report.md`
- `docs/research/project_journey.md`

## State Source Audit
| item | value | notes |
| --- | --- | --- |
| state_file_used | data/04_layer2b_risk_regime_engine/market_state_history_refined.csv | refined state file preferred when available |
| date_range | 2005-01-07 to 2026-04-10 |  |
| n_weeks | 1110 | aligned to GGG1 return dates |
| n_base_states | 5 | calm_trend,neutral_mixed,recovery_confirmed,recovery_fragile,stressed_panic |
| n_refined_states | 7 | calm_trend,neutral_deteriorating,neutral_healthy,neutral_mixed,recovery_confirmed,recovery_fragile,stressed_panic |
| aligned_to_ggg1 | True | inner frame seeded from GGG1 dates |
| missing_state_dates | 0 |  |
| refined_states_exist | True |  |
| neutral_healthy_split_exists | True |  |
| neutral_deteriorating_split_exists | True |  |
| qqq_context_features_loaded | 4 | qqq_active_int_efa_spy_strength_x_market_trend,qqq_active_int_market_trend_x_mom13,qqq_any_shortlist_rule_active,qqq_mean_shortlist_rule_active |
| hmmlearn_available | False | HMM skipped unless package already installed |

The canonical SSS path features use the original five-state `market_state` sequence so results remain comparable to QQQ and GGG1. The refined Layer 2B states are retained as lagged comparison/control features.

## Transition And Dwell Diagnostics
Top transition-risk diagnostics:
| diagnostic | group | n_weeks | stress_transition_4w_rate | stress_transition_8w_rate | avg_ggg1_fwd_4w | avg_ggg1_fwd_8w |
| --- | --- | --- | --- | --- | --- | --- |
| named_question | neutral_mixed_after_stressed_panic | 24 | 0.5652 | 0.6087 | 0.0019 | 0.0033 |
| two_state_path | stressed_panic->neutral_mixed | 24 | 0.5652 | 0.6087 | 0.0019 | 0.0033 |
| previous_to_current_path | stressed_panic|neutral_mixed | 24 | 0.5652 | 0.6087 | 0.0019 | 0.0033 |
| previous_to_current_path | stressed_panic|recovery_fragile | 6 | 0.3333 | 0.5000 | 0.0063 | 0.0182 |
| two_state_path | stressed_panic->recovery_fragile | 6 | 0.3333 | 0.5000 | 0.0063 | 0.0182 |
| previous_to_current_path | neutral_mixed|stressed_panic | 28 | 0.2963 | 0.3846 | 0.0028 | 0.0032 |
| two_state_path | neutral_mixed->stressed_panic | 28 | 0.2963 | 0.3846 | 0.0028 | 0.0032 |
| current_state_dwell | stressed_panic|new_state_1_2w | 49 | 0.2083 | 0.3404 | 0.0032 | 0.0060 |
| refined_state | neutral_deteriorating | 171 | 0.2781 | 0.3393 | 0.0062 | 0.0091 |
| current_state_dwell | stressed_panic|young_3_6w | 53 | 0.0755 | 0.3019 | 0.0017 | 0.0065 |
| current_state_dwell | neutral_mixed|mature_7_13w | 103 | 0.1456 | 0.3010 | 0.0035 | 0.0058 |
| current_state_dwell | neutral_mixed|old_14w_plus | 86 | 0.2093 | 0.2771 | 0.0030 | 0.0079 |
| named_question | neutral_mixed_old_14w_plus | 86 | 0.2093 | 0.2771 | 0.0030 | 0.0079 |
| refined_state | neutral_mixed | 112 | 0.1696 | 0.2679 | 0.0022 | 0.0038 |
| two_state_path | neutral_mixed->neutral_mixed | 398 | 0.1637 | 0.2462 | 0.0057 | 0.0100 |
| previous_to_current_path | neutral_mixed|neutral_mixed | 398 | 0.1637 | 0.2462 | 0.0057 | 0.0100 |

Dwell distribution examples:
| market_state | dwell_bucket | n_runs | avg_run_length | median_run_length | max_run_length | share_of_state_runs |
| --- | --- | --- | --- | --- | --- | --- |
| calm_trend | new_state_1_2w | 16 | 1.5000 | 1.5000 | 2 | 0.3810 |
| calm_trend | young_3_6w | 11 | 4.8182 | 5.0000 | 6 | 0.2619 |
| calm_trend | mature_7_13w | 9 | 10.0000 | 10.0000 | 13 | 0.2143 |
| calm_trend | old_14w_plus | 6 | 21.3333 | 17.5000 | 33 | 0.1429 |
| neutral_mixed | new_state_1_2w | 40 | 1.3000 | 1.0000 | 2 | 0.4211 |
| neutral_mixed | young_3_6w | 34 | 3.7059 | 3.0000 | 6 | 0.3579 |
| neutral_mixed | mature_7_13w | 12 | 9.3333 | 8.5000 | 13 | 0.1263 |
| neutral_mixed | old_14w_plus | 9 | 22.5556 | 19.0000 | 42 | 0.0947 |
| recovery_confirmed | new_state_1_2w | 13 | 1.3846 | 1.0000 | 2 | 0.6842 |
| recovery_confirmed | young_3_6w | 6 | 4.3333 | 4.0000 | 5 | 0.3158 |
| recovery_fragile | new_state_1_2w | 15 | 1.2000 | 1.0000 | 2 | 0.6522 |
| recovery_fragile | young_3_6w | 8 | 3.8750 | 4.0000 | 4 | 0.3478 |
| stressed_panic | new_state_1_2w | 17 | 1.2353 | 1.0000 | 2 | 0.5484 |
| stressed_panic | mature_7_13w | 6 | 9.6667 | 9.5000 | 12 | 0.1935 |
| stressed_panic | old_14w_plus | 6 | 23.5000 | 18.0000 | 37 | 0.1935 |
| stressed_panic | young_3_6w | 2 | 4.5000 | 4.5000 | 5 | 0.0645 |

State age performance examples:
| row_type | market_state | state_dwell_bucket | n_weeks | weekly_mean | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | avg_fwd_return_4w | avg_fwd_return_8w | stress_transition_4w_rate | stress_transition_8w_rate | refined_state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| refined_state_x_dwell_bucket | nan | young_3_6w | 59 | 0.0042 | 0.2409 | 0.0741 | 3.2492 | -0.0337 | -0.0162 | 0.0102 | 0.0178 | 0.0169 | 0.1017 | neutral_healthy |
| refined_state_x_dwell_bucket | nan | new_state_1_2w | 76 | 0.0039 | 0.2230 | 0.0887 | 2.5151 | -0.0578 | -0.0289 | 0.0104 | 0.0219 | 0.0132 | 0.0263 | neutral_healthy |
| current_state_x_dwell_bucket | neutral_mixed | young_3_6w | 142 | 0.0026 | 0.1451 | 0.0707 | 2.0521 | -0.0747 | -0.0199 | 0.0078 | 0.0117 | 0.1479 | 0.2113 | nan |
| current_state_x_dwell_bucket | neutral_mixed | new_state_1_2w | 162 | 0.0029 | 0.1612 | 0.0807 | 1.9962 | -0.0502 | -0.0227 | 0.0077 | 0.0149 | 0.1750 | 0.2125 | nan |
| refined_state_x_dwell_bucket | nan | old_14w_plus | 35 | 0.0029 | 0.1601 | 0.0804 | 1.9903 | -0.0325 | -0.0291 | 0.0032 | 0.0138 | 0.1714 | 0.2424 | neutral_healthy |
| refined_state_x_dwell_bucket | nan | old_14w_plus | 20 | 0.0031 | 0.1756 | 0.0888 | 1.9779 | -0.0301 | -0.0202 | 0.0096 | 0.0102 | 0.2000 | 0.1579 | neutral_deteriorating |
| refined_state_x_dwell_bucket | nan | new_state_1_2w | 23 | 0.0019 | 0.1010 | 0.0547 | 1.8467 | -0.0164 | -0.0127 | 0.0057 | 0.0097 | 0.2174 | 0.3043 | neutral_mixed |
| refined_state_x_dwell_bucket | nan | new_state_1_2w | 34 | 0.0016 | 0.0856 | 0.0534 | 1.6028 | -0.0214 | -0.0144 | 0.0023 | 0.0106 | 0.1176 | 0.2353 | recovery_fragile |
| current_state_x_dwell_bucket | recovery_fragile | new_state_1_2w | 34 | 0.0016 | 0.0856 | 0.0534 | 1.6028 | -0.0214 | -0.0144 | 0.0023 | 0.0106 | 0.1176 | 0.2353 | nan |
| refined_state_x_dwell_bucket | nan | young_3_6w | 27 | 0.0012 | 0.0648 | 0.0413 | 1.5706 | -0.0127 | -0.0119 | 0.0049 | 0.0063 | 0.1852 | 0.2222 | neutral_mixed |
| current_state_x_dwell_bucket | stressed_panic | mature_7_13w | 64 | 0.0009 | 0.0504 | 0.0332 | 1.5200 | -0.0251 | -0.0099 | 0.0057 | 0.0109 | 0.1094 | 0.1719 | nan |
| refined_state_x_dwell_bucket | nan | mature_7_13w | 64 | 0.0009 | 0.0504 | 0.0332 | 1.5200 | -0.0251 | -0.0099 | 0.0057 | 0.0109 | 0.1094 | 0.1719 | stressed_panic |
| refined_state_x_dwell_bucket | nan | new_state_1_2w | 30 | 0.0020 | 0.1097 | 0.0747 | 1.4677 | -0.0372 | -0.0197 | 0.0132 | 0.0277 | 0.0000 | 0.0000 | recovery_confirmed |
| current_state_x_dwell_bucket | recovery_confirmed | new_state_1_2w | 30 | 0.0020 | 0.1097 | 0.0747 | 1.4677 | -0.0372 | -0.0197 | 0.0132 | 0.0277 | 0.0000 | 0.0000 | nan |

## Sequence Feature Summary
| feature_family | feature_count | avg_missingness |
| --- | --- | --- |
| state_ngram | 62 | 0.0000 |
| ooo_signal_context | 37 | 0.0019 |
| state_identity | 35 | 0.0000 |
| existing_layer2b_probability_or_input | 25 | 0.0745 |
| state_memory | 25 | 0.0001 |
| qqq_rule_context | 4 | 0.0072 |
| dwell_time | 3 | 0.0514 |

## Leakage Checks
| check | passed | note |
| --- | --- | --- |
| state_sequence_lagged | True | model features use state_lag1 or older |
| refined_state_lagged | True | refined_state only appears as lag1 dummies/features |
| layer2b_numeric_context_lagged | True | Layer 2B probabilities/inputs are shifted one week |
| qqq_context_lagged | True | QQQ rule context is shifted one week again |
| ooo_context_lagged | True | OOO signal/event context is shifted one week for overlap diagnostics |
| no_future_state_features | True | future states are used only in target labels |
| no_future_returns_as_features | True | forward returns are saved in target panel only |
| no_random_splits | True | walk-forward expanding splits only |
| production_shadow_ggg1_unchanged | True | production=improved_phase2b_regime_confidence_boost; shadow=improved_phase2b_combo_abc; GGG1=improved_phaseggg_confirmed_only_robust_offense |

## Target Definitions And Class Balance
| target | definition | horizon_weeks | n_observations | positive_count | positive_rate | start_date | end_date | enough_samples | leakage_risk_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stress_transition_4w | stress_transition_start | 4 | 1106 | 119 | 0.1076 | 2005-01-07 | 2026-03-13 | True | future states/returns define target only; not included as live features |
| stress_transition_8w | stress_transition_start | 8 | 1102 | 202 | 0.1833 | 2005-01-07 | 2026-02-13 | True | future states/returns define target only; not included as live features |
| recovery_quality_4w | recovery_quality | 4 | 802 | 401 | 0.5000 | 2006-07-07 | 2026-03-06 | True | future states/returns define target only; not included as live features |
| recovery_quality_8w | recovery_quality | 8 | 799 | 399 | 0.4994 | 2006-07-07 | 2026-02-13 | True | future states/returns define target only; not included as live features |
| ggg1_underperformance_4w | ggg1_underperformance | 4 | 1106 | 749 | 0.6772 | 2005-01-07 | 2026-03-13 | True | future states/returns define target only; not included as live features |
| ggg1_tail_risk_4w | ggg1_tail_risk | 4 | 1106 | 273 | 0.2468 | 2005-01-07 | 2026-03-13 | True | future states/returns define target only; not included as live features |
| false_recovery_label | false_recovery | 8 | 128 | 36 | 0.2812 | 2006-08-18 | 2025-11-21 | False | future states/returns define target only; not included as live features |
| qqq_interaction_success_label | optional_qqq_interaction_success | 8 | 6 | 3 | 0.5000 | 2009-06-26 | 2025-06-06 | False | future states/returns define target only; not included as live features |

## Baseline Results
| target | model | n_oos | positive_rate | brier | auc | log_loss | high_risk_decile_precision | high_risk_decile_recall | top_decile_avg_forward_return | overall_avg_forward_return | top_decile_return_lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ggg1_tail_risk_4w | historical_class_rate | 846 | 0.2660 | 0.1981 | 0.3992 | 0.5874 | 0.1176 | 0.0444 | 0.0102 | 0.0056 | 0.0046 |
| ggg1_tail_risk_4w | current_state_lag1_rate | 846 | 0.2660 | 0.2014 | 0.4871 | 0.6208 | 0.1647 | 0.0622 | 0.0087 | 0.0056 | 0.0031 |
| ggg1_tail_risk_4w | previous_state_lag2_rate | 846 | 0.2660 | 0.2020 | 0.4800 | 0.6102 | 0.1529 | 0.0578 | 0.0089 | 0.0056 | 0.0033 |
| ggg1_tail_risk_4w | state_path_markov_rate | 846 | 0.2660 | 0.2070 | 0.4713 | 0.7350 | 0.1294 | 0.0489 | 0.0100 | 0.0056 | 0.0044 |
| ggg1_tail_risk_4w | transition_matrix_markov_score | 846 | 0.2660 | 0.2070 | 0.4713 | 0.7350 | 0.1294 | 0.0489 | 0.0100 | 0.0056 | 0.0044 |
| ggg1_tail_risk_4w | current_state_plus_dwell_rate | 846 | 0.2660 | 0.2075 | 0.4878 | 0.6594 | 0.2118 | 0.0800 | 0.0021 | 0.0056 | -0.0035 |
| ggg1_tail_risk_4w | qqq_rule_only_baseline | 846 | 0.2660 | 0.2853 | 0.4442 | 1.1309 | 0.3294 | 0.1244 | 0.0019 | 0.0056 | -0.0038 |
| ggg1_tail_risk_4w | existing_layer2b_probability_baseline | 846 | 0.2660 | 0.3156 | 0.4415 | 1.1575 | 0.2000 | 0.0756 | 0.0024 | 0.0056 | -0.0032 |
| ggg1_underperformance_4w | existing_layer2b_probability_baseline | 846 | 0.7270 | 0.2099 | 0.5874 | 0.6509 | 0.8471 | 0.1171 | 0.0063 | 0.0056 | 0.0007 |
| ggg1_underperformance_4w | historical_class_rate | 846 | 0.7270 | 0.2116 | 0.3804 | 0.6150 | 0.5059 | 0.0699 | 0.0065 | 0.0056 | 0.0008 |
| ggg1_underperformance_4w | current_state_lag1_rate | 846 | 0.7270 | 0.2161 | 0.4902 | 0.6239 | 0.6706 | 0.0927 | 0.0089 | 0.0056 | 0.0033 |
| ggg1_underperformance_4w | previous_state_lag2_rate | 846 | 0.7270 | 0.2230 | 0.4409 | 0.6500 | 0.6471 | 0.0894 | 0.0076 | 0.0056 | 0.0020 |
| ggg1_underperformance_4w | current_state_plus_dwell_rate | 846 | 0.7270 | 0.2298 | 0.4656 | 0.6870 | 0.8118 | 0.1122 | 0.0029 | 0.0056 | -0.0027 |
| ggg1_underperformance_4w | state_path_markov_rate | 846 | 0.7270 | 0.2304 | 0.4614 | 0.7635 | 0.6000 | 0.0829 | 0.0094 | 0.0056 | 0.0038 |
| ggg1_underperformance_4w | transition_matrix_markov_score | 846 | 0.7270 | 0.2304 | 0.4614 | 0.7635 | 0.6000 | 0.0829 | 0.0094 | 0.0056 | 0.0038 |
| ggg1_underperformance_4w | qqq_rule_only_baseline | 846 | 0.7270 | 0.3578 | 0.4829 | 1.5067 | 0.7647 | 0.1057 | 0.0019 | 0.0056 | -0.0038 |
| recovery_quality_4w | historical_class_rate | 670 | 0.4881 | 0.2521 | 0.4390 | 0.6974 | 0.4776 | 0.0979 | 0.0076 | 0.0062 | 0.0014 |
| recovery_quality_4w | previous_state_lag2_rate | 670 | 0.4881 | 0.2577 | 0.4962 | 0.7104 | 0.4925 | 0.1009 | 0.0073 | 0.0062 | 0.0011 |
| recovery_quality_4w | current_state_lag1_rate | 670 | 0.4881 | 0.2598 | 0.4873 | 0.7169 | 0.5224 | 0.1070 | 0.0089 | 0.0062 | 0.0027 |
| recovery_quality_4w | state_path_markov_rate | 670 | 0.4881 | 0.2659 | 0.4958 | 0.8623 | 0.4925 | 0.1009 | 0.0084 | 0.0062 | 0.0022 |
| recovery_quality_4w | transition_matrix_markov_score | 670 | 0.4881 | 0.2659 | 0.4958 | 0.8623 | 0.4925 | 0.1009 | 0.0084 | 0.0062 | 0.0022 |
| recovery_quality_4w | current_state_plus_dwell_rate | 670 | 0.4881 | 0.2702 | 0.4800 | 0.8186 | 0.5522 | 0.1131 | 0.0108 | 0.0062 | 0.0046 |
| recovery_quality_4w | qqq_rule_only_baseline | 670 | 0.4881 | 0.3168 | 0.4741 | 1.1137 | 0.4328 | 0.0887 | 0.0011 | 0.0062 | -0.0051 |
| recovery_quality_4w | existing_layer2b_probability_baseline | 670 | 0.4881 | 0.3427 | 0.4684 | 1.4447 | 0.4925 | 0.1009 | 0.0078 | 0.0062 | 0.0016 |

## Sequence Model Results
| target | model | n_oos | positive_rate | brier | auc | log_loss | high_risk_decile_precision | high_risk_decile_recall | top_decile_return_lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ggg1_tail_risk_4w | random_forest_depth4 | 846 | 0.2660 | 0.2013 | 0.4568 | 0.5957 | 0.2706 | 0.1022 | 0.0038 |
| ggg1_tail_risk_4w | decision_tree_depth3 | 846 | 0.2660 | 0.2386 | 0.4436 | 0.7235 | 0.2353 | 0.0889 | 0.0037 |
| ggg1_tail_risk_4w | hist_gradient_depth3 | 846 | 0.2660 | 0.2527 | 0.4646 | 0.7570 | 0.2000 | 0.0756 | 0.0046 |
| ggg1_underperformance_4w | decision_tree_depth3 | 846 | 0.7270 | 0.2071 | 0.5383 | 0.6906 | 0.8000 | 0.1106 | 0.0027 |
| ggg1_underperformance_4w | random_forest_depth4 | 846 | 0.7270 | 0.2168 | 0.4501 | 0.6262 | 0.7294 | 0.1008 | 0.0006 |
| ggg1_underperformance_4w | hist_gradient_depth3 | 846 | 0.7270 | 0.2265 | 0.5287 | 0.7056 | 0.7529 | 0.1041 | 0.0047 |
| recovery_quality_4w | random_forest_depth4 | 670 | 0.4881 | 0.2619 | 0.4619 | 0.7182 | 0.3582 | 0.0734 | -0.0063 |
| recovery_quality_4w | decision_tree_depth3 | 670 | 0.4881 | 0.3001 | 0.4934 | 1.0611 | 0.3881 | 0.0795 | -0.0035 |
| recovery_quality_4w | logistic_sequence_l2 | 670 | 0.4881 | 0.3105 | 0.5009 | 0.9526 | 0.4925 | 0.1009 | 0.0006 |
| recovery_quality_8w | random_forest_depth4 | 667 | 0.4993 | 0.2641 | 0.4890 | 0.7250 | 0.5224 | 0.1051 | -0.0025 |
| recovery_quality_8w | logistic_sequence_l2 | 667 | 0.4993 | 0.3096 | 0.5071 | 0.9896 | 0.5821 | 0.1171 | 0.0045 |
| recovery_quality_8w | logistic_sequence_plus_qqq | 667 | 0.4993 | 0.3119 | 0.5181 | 1.0151 | 0.5522 | 0.1111 | 0.0037 |
| stress_transition_4w | random_forest_depth4 | 846 | 0.0981 | 0.0859 | 0.6615 | 0.3156 | 0.2118 | 0.2169 | -0.0016 |
| stress_transition_4w | decision_tree_depth3 | 846 | 0.0981 | 0.0967 | 0.5601 | 0.5416 | 0.2118 | 0.2169 | 0.0007 |
| stress_transition_4w | hist_gradient_depth3 | 846 | 0.0981 | 0.0980 | 0.5890 | 0.4273 | 0.2471 | 0.2530 | -0.0032 |
| stress_transition_8w | random_forest_depth4 | 842 | 0.1639 | 0.1378 | 0.6086 | 0.4580 | 0.3529 | 0.2174 | -0.0061 |
| stress_transition_8w | hist_gradient_depth3 | 842 | 0.1639 | 0.1682 | 0.6508 | 0.6239 | 0.3294 | 0.2029 | -0.0055 |
| stress_transition_8w | logistic_sequence_l2 | 842 | 0.1639 | 0.1682 | 0.5627 | 0.6343 | 0.1882 | 0.1159 | -0.0071 |

## Improvement Over Current-State And Markov Baselines
| target | model | brier | current_state_brier | brier_improvement_vs_current_state | auc | current_state_auc | auc_lift_vs_current_state | markov_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ggg1_tail_risk_4w | random_forest_depth4 | 0.2013 | 0.2014 | 0.0001 | 0.4568 | 0.4871 | -0.0303 | 0.4713 |
| ggg1_underperformance_4w | decision_tree_depth3 | 0.2071 | 0.2161 | 0.0090 | 0.5383 | 0.4902 | 0.0481 | 0.4614 |
| recovery_quality_4w | random_forest_depth4 | 0.2619 | 0.2598 | -0.0021 | 0.4619 | 0.4873 | -0.0254 | 0.4958 |
| recovery_quality_8w | random_forest_depth4 | 0.2641 | 0.2575 | -0.0066 | 0.4890 | 0.4545 | 0.0345 | 0.4915 |
| stress_transition_4w | random_forest_depth4 | 0.0859 | 0.0887 | 0.0028 | 0.6615 | 0.5801 | 0.0815 | 0.5461 |
| stress_transition_8w | random_forest_depth4 | 0.1378 | 0.1401 | 0.0023 | 0.6086 | 0.5623 | 0.0463 | 0.5406 |

## Extracted Sequence Rules
| rule_name | target | event_count | event_frequency | precision_lift | return_lift | stability | state_path_interpretation | redundancy_warning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| neutral_after_stress_short_dwell | stress_transition_4w | 23 | 0.0208 | 0.2837 | -0.0031 | 1.0000 | neutral_mixed immediately after stress with young dwell |  |
| neutral_after_stress_short_dwell | stress_transition_8w | 23 | 0.0209 | 0.2515 | -0.0086 | 1.0000 | neutral_mixed immediately after stress with young dwell |  |
| calm_old_low_stress | ggg1_underperformance_4w | 50 | 0.0452 | 0.2428 | -0.0053 | 1.0000 | mature calm trend with no recent stress memory |  |
| stress_memory_neutral | false_recovery_label | 21 | 0.1641 | 0.2426 | -0.0143 | 1.0000 | neutral_mixed with recent stress memory |  |
| stress_new_state | stress_transition_8w | 47 | 0.0426 | 0.2210 | -0.0047 | 0.6667 | new stressed_panic state |  |
| stress_memory_neutral | stress_transition_4w | 117 | 0.1058 | 0.1745 | -0.0002 | 1.0000 | neutral_mixed with recent stress memory |  |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_8w | 42 | 0.0526 | 0.1673 | 0.0061 | 0.6667 | QQQ international leadership rule under calm/recovery sequence |  |
| stress_memory_neutral | stress_transition_8w | 117 | 0.1062 | 0.1329 | -0.0025 | 0.6667 | neutral_mixed with recent stress memory |  |
| stress_new_state | stress_transition_4w | 47 | 0.0425 | 0.1264 | -0.0038 | 0.6667 | new stressed_panic state |  |
| refined_neutral_deteriorating | stress_transition_4w | 169 | 0.1528 | 0.1232 | 0.0001 | 1.0000 | Layer 2B neutral deterioration refinement | partly duplicates existing refined Layer 2B state |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_4w | 42 | 0.0524 | 0.1190 | 0.0029 | 0.6667 | QQQ international leadership rule under calm/recovery sequence |  |
| calm_old_low_stress | ggg1_tail_risk_4w | 50 | 0.0452 | 0.1132 | -0.0053 | 1.0000 | mature calm trend with no recent stress memory |  |
| refined_neutral_deteriorating | ggg1_underperformance_4w | 169 | 0.1528 | 0.1098 | 0.0001 | 1.0000 | Layer 2B neutral deterioration refinement | partly duplicates existing refined Layer 2B state |
| refined_neutral_deteriorating | stress_transition_8w | 167 | 0.1515 | 0.0921 | -0.0026 | 0.6667 | Layer 2B neutral deterioration refinement | partly duplicates existing refined Layer 2B state |
| high_transition_instability | recovery_quality_8w | 227 | 0.2841 | 0.0733 | 0.0046 | 0.6667 | high recent transition instability |  |
| stress_new_state | ggg1_tail_risk_4w | 47 | 0.0425 | 0.0723 | -0.0038 | 1.0000 | new stressed_panic state |  |
| high_transition_instability | recovery_quality_4w | 227 | 0.2830 | 0.0639 | 0.0038 | 1.0000 | high recent transition instability |  |
| neutral_after_stress_short_dwell | ggg1_underperformance_4w | 23 | 0.0208 | 0.0619 | -0.0031 | 0.5000 | neutral_mixed immediately after stress with young dwell |  |
| refined_neutral_deteriorating | ggg1_tail_risk_4w | 169 | 0.1528 | 0.0609 | 0.0001 | 0.6667 | Layer 2B neutral deterioration refinement | partly duplicates existing refined Layer 2B state |
| stress_new_state | ggg1_underperformance_4w | 47 | 0.0425 | 0.0462 | -0.0038 | 0.6667 | new stressed_panic state |  |

Top all-rule diagnostics:
| rule_name | target | event_count | precision_lift | stability | rule_family |
| --- | --- | --- | --- | --- | --- |
| stress_old_state | qqq_interaction_success_label | 1 | 0.5000 | 0.0000 | stress_dwell |
| neutral_after_stress_short_dwell | false_recovery_label | 4 | 0.4688 | 0.0000 | stress_memory |
| refined_neutral_healthy_after_stress | recovery_quality_8w | 11 | 0.4097 | 1.0000 | refined_state |
| recovery_confirmed_after_fragile_low_stress | ggg1_underperformance_4w | 2 | 0.3228 | 0.0000 | recovery_quality |
| recovery_fragile_after_stress | recovery_quality_8w | 5 | 0.3006 | 0.0000 | recovery_path |
| recovery_fragile_after_stress | recovery_quality_4w | 5 | 0.3000 | 0.0000 | recovery_path |
| neutral_after_stress_short_dwell | stress_transition_4w | 23 | 0.2837 | 1.0000 | stress_memory |
| refined_neutral_deteriorating | false_recovery_label | 16 | 0.2812 | 1.0000 | refined_state |
| recovery_confirmed_after_fragile_low_stress | ggg1_tail_risk_4w | 2 | 0.2532 | 0.0000 | recovery_quality |
| neutral_after_stress_short_dwell | stress_transition_8w | 23 | 0.2515 | 1.0000 | stress_memory |
| calm_old_low_stress | ggg1_underperformance_4w | 50 | 0.2428 | 1.0000 | calm_persistence |
| stress_memory_neutral | false_recovery_label | 21 | 0.2426 | 1.0000 | stress_memory |
| refined_neutral_healthy_after_stress | recovery_quality_4w | 11 | 0.2273 | 1.0000 | refined_state |
| stress_new_state | stress_transition_8w | 47 | 0.2210 | 0.6667 | stress_dwell |
| stress_new_state | false_recovery_label | 4 | 0.2188 | 0.0000 | stress_dwell |
| recovery_confirmed_after_fragile_low_stress | false_recovery_label | 2 | 0.2188 | 0.0000 | recovery_quality |
| stress_old_state | false_recovery_label | 2 | 0.2188 | 0.0000 | stress_dwell |
| stress_memory_neutral | stress_transition_4w | 117 | 0.1745 | 1.0000 | stress_memory |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_8w | 42 | 0.1673 | 0.6667 | qqq_sequence_overlap |
| recovery_confirmed_after_neutral | recovery_quality_8w | 12 | 0.1673 | 1.0000 | recovery_path |

## QQQ / OOO Overlap Findings
QQQ after sequence controls:
| target | sequence_auc | sequence_plus_qqq_auc | delta_auc_plus_qqq | sequence_brier | sequence_plus_qqq_brier | delta_brier_plus_qqq | sequence_high_risk_precision | sequence_plus_qqq_high_risk_precision | delta_high_risk_precision_plus_qqq | max_abs_corr_qqq_to_sequence_feature | closest_sequence_feature_to_qqq | conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stress_transition_4w | 0.5618 | 0.5457 | -0.0161 | 0.1013 | 0.1036 | 0.0023 | 0.1647 | 0.1765 | 0.0118 | 0.1952 | refined_state_lag1_neutral_mixed | QQQ_VALUE_MOSTLY_EXPLAINED_BY_SEQUENCE_OR_STATE_CONTEXT |
| stress_transition_8w | 0.5627 | 0.5746 | 0.0118 | 0.1682 | 0.1722 | 0.0039 | 0.1882 | 0.2000 | 0.0118 | 0.1952 | refined_state_lag1_neutral_mixed | MIXED_QQQ_SEQUENCE_INCREMENTALITY |
| recovery_quality_4w | 0.5009 | 0.4838 | -0.0171 | 0.3105 | 0.3222 | 0.0117 | 0.4925 | 0.4478 | -0.0448 | 0.1952 | refined_state_lag1_neutral_mixed | QQQ_VALUE_MOSTLY_EXPLAINED_BY_SEQUENCE_OR_STATE_CONTEXT |
| recovery_quality_8w | 0.5071 | 0.5181 | 0.0110 | 0.3096 | 0.3119 | 0.0022 | 0.5821 | 0.5522 | -0.0299 | 0.1952 | refined_state_lag1_neutral_mixed | MIXED_QQQ_SEQUENCE_INCREMENTALITY |
| ggg1_underperformance_4w | 0.5365 | 0.5146 | -0.0219 | 0.2429 | 0.2479 | 0.0050 | 0.7412 | 0.7765 | 0.0353 | 0.1952 | refined_state_lag1_neutral_mixed | QQQ_VALUE_MOSTLY_EXPLAINED_BY_SEQUENCE_OR_STATE_CONTEXT |
| ggg1_tail_risk_4w | 0.4998 | 0.4934 | -0.0064 | 0.2580 | 0.2598 | 0.0018 | 0.2353 | 0.2706 | 0.0353 | 0.1952 | refined_state_lag1_neutral_mixed | QQQ_VALUE_MOSTLY_EXPLAINED_BY_SEQUENCE_OR_STATE_CONTEXT |
| false_recovery_label |  |  |  |  |  |  |  |  |  | 0.1952 | refined_state_lag1_neutral_mixed | INSUFFICIENT_QQQ_CONTROL_DATA |
| qqq_interaction_success_label |  |  |  |  |  |  |  |  |  | 0.1952 | refined_state_lag1_neutral_mixed | INSUFFICIENT_QQQ_CONTROL_DATA |

OOO signal overlap with sequence features:
| ooo_signal_or_event | event_frequency | max_abs_corr_sequence | closest_sequence_feature | max_event_overlap_sequence | max_overlap_sequence_feature | overlap_flag |
| --- | --- | --- | --- | --- | --- | --- |
| ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event_lag1 | 0.0387 | 1.0000 | state_lag1_recovery_confirmed | 1.0000 | state_lag1_recovery_confirmed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo2_breadth_ret13_positive_x_recovery_confirmed_signal_lag1 | 0.0387 | 0.7614 | path2_lag_recovery_confirmed->recovery_confirmed | 0.5814 | state_lag1_recovery_confirmed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo2_breadth_ret13_positive_x_neutral_mixed_signal_lag1 | 0.4396 | 0.7461 | path2_lag_neutral_mixed->neutral_mixed | 0.8053 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo2_breadth_ret13_positive_x_stressed_panic_signal_lag1 | 0.2054 | 0.7185 | path2_lag_stressed_panic->stressed_panic | 0.8684 | state_lag1_stressed_panic | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo3event_market_trend_calm_neutral_event_lag1 | 0.6450 | 0.6886 | state_lag1_stressed_panic | 0.5894 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo2_market_trend_positive_signal_lag1 | 0.7793 | 0.6398 | state_lag1_stressed_panic | 0.4879 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo3event_market_trend_raw_event_lag1 | 0.7793 | 0.6378 | state_lag1_stressed_panic | 0.4879 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo3event_breadth_ret13_positive_x_recovery_confirmed_top20_event_lag1 | 0.9523 | 0.5768 | refined_state_lag1_neutral_mixed | 0.4229 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo2_breadth_ret26_positive_signal_lag1 | 0.9874 | 0.5497 | state_lag1_stressed_panic | 0.4380 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo2_breadth_ret13_positive_signal_lag1 | 0.9937 | 0.5378 | state_lag1_stressed_panic | 0.4415 | state_lag1_neutral_mixed | MOSTLY_STATE_SEQUENCE_PROXY |
| ooo3event_market_drawdown_top20_event_lag1 | 0.1523 | 0.4968 | path2_lag_stressed_panic->stressed_panic | 0.6805 | state_lag1_stressed_panic | PARTLY_INCREMENTAL_OR_MIXED |
| ooo2_recent_stress_26w_signal_lag1 | 0.4838 | 0.4817 | state_lag1_stressed_panic | 0.4078 | state_lag1_stressed_panic | PARTLY_INCREMENTAL_OR_MIXED |
| ooo2_leadlag_GLD_minus_SPY_13w_signal_lag1 | 0.4649 | 0.4811 | state_lag1_stressed_panic | 0.4109 | state_lag1_neutral_mixed | PARTLY_INCREMENTAL_OR_MIXED |
| ooo3event_market_trend_recent_stress_filtered_event_lag1 | 0.4748 | 0.4587 | state_lag1_stressed_panic | 0.5142 | state_lag1_neutral_mixed | PARTLY_INCREMENTAL_OR_MIXED |
| ooo3event_market_drawdown_vol_filtered_top20_event_lag1 | 0.1225 | 0.4502 | path2_lag_stressed_panic->stressed_panic | 0.6765 | state_lag1_stressed_panic | PARTLY_INCREMENTAL_OR_MIXED |
| ooo3event_breadth_ret13_positive_x_recovery_confirmed_vol_filtered_top20_event_lag1 | 0.6991 | 0.4398 | refined_state_lag1_neutral_mixed | 0.3995 | state_lag1_neutral_mixed | PARTLY_INCREMENTAL_OR_MIXED |

## GGG1 Weakness Diagnostics
| rule_name | target | event_count | precision_lift | avg_forward_return | return_lift | incrementality_flag | ggg1_weakness_flag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| neutral_after_stress_short_dwell | false_recovery_label | 4 | 0.4688 | -0.0042 | -0.0265 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| recovery_confirmed_after_fragile_low_stress | ggg1_underperformance_4w | 2 | 0.3228 | -0.0064 | -0.0118 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| neutral_after_stress_short_dwell | stress_transition_4w | 23 | 0.2837 | 0.0024 | -0.0031 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| refined_neutral_deteriorating | false_recovery_label | 16 | 0.2812 | 0.0064 | -0.0159 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| recovery_confirmed_after_fragile_low_stress | ggg1_tail_risk_4w | 2 | 0.2532 | -0.0064 | -0.0118 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| neutral_after_stress_short_dwell | stress_transition_8w | 23 | 0.2515 | 0.0023 | -0.0086 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| calm_old_low_stress | ggg1_underperformance_4w | 50 | 0.2428 | 0.0001 | -0.0053 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| stress_memory_neutral | false_recovery_label | 21 | 0.2426 | 0.0080 | -0.0143 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| stress_new_state | stress_transition_8w | 47 | 0.2210 | 0.0063 | -0.0047 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| stress_new_state | false_recovery_label | 4 | 0.2188 | 0.0178 | -0.0045 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| recovery_confirmed_after_fragile_low_stress | false_recovery_label | 2 | 0.2188 | -0.0002 | -0.0225 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| stress_old_state | false_recovery_label | 2 | 0.2188 | 0.0189 | -0.0034 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| stress_memory_neutral | stress_transition_4w | 117 | 0.1745 | 0.0053 | -0.0002 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| recovery_fragile_after_stress | stress_transition_8w | 6 | 0.1500 | 0.0221 | 0.0111 | INSUFFICIENT_EVIDENCE | NO_CLEAR_GGG1_WEAKNESS_SIGNAL |
| stress_memory_neutral | stress_transition_8w | 117 | 0.1329 | 0.0085 | -0.0025 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| stress_new_state | stress_transition_4w | 47 | 0.1264 | 0.0017 | -0.0038 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| refined_neutral_deteriorating | stress_transition_4w | 169 | 0.1232 | 0.0056 | 0.0001 | DUPLICATES_CURRENT_STATE_ENGINE | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| calm_old_low_stress | ggg1_tail_risk_4w | 50 | 0.1132 | 0.0001 | -0.0053 | INCREMENTAL_SEQUENCE_SIGNAL | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| refined_neutral_deteriorating | ggg1_underperformance_4w | 169 | 0.1098 | 0.0056 | 0.0001 | DUPLICATES_CURRENT_STATE_ENGINE | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |
| refined_neutral_deteriorating | stress_transition_8w | 167 | 0.0921 | 0.0084 | -0.0026 | DUPLICATES_CURRENT_STATE_ENGINE | SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD |

## Candidate Sequence Signal Shortlist
| rule_name | target | classification | event_count | precision_lift | stability | incrementality_flag | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress | ggg1_underperformance_4w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 50 | 0.2428 | 1.0000 | INCREMENTAL_SEQUENCE_SIGNAL | stable, enough events, model improves over state baseline, and rule is not just current-state identity |
| stress_new_state | stress_transition_8w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 47 | 0.2210 | 0.6667 | INCREMENTAL_SEQUENCE_SIGNAL | stable, enough events, model improves over state baseline, and rule is not just current-state identity |
| stress_memory_neutral | stress_transition_4w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 117 | 0.1745 | 1.0000 | INCREMENTAL_SEQUENCE_SIGNAL | stable, enough events, model improves over state baseline, and rule is not just current-state identity |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_8w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 42 | 0.1673 | 0.6667 | INCREMENTAL_SEQUENCE_SIGNAL | stable, enough events, model improves over state baseline, and rule is not just current-state identity |
| stress_memory_neutral | stress_transition_8w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 117 | 0.1329 | 0.6667 | INCREMENTAL_SEQUENCE_SIGNAL | stable, enough events, model improves over state baseline, and rule is not just current-state identity |
| stress_new_state | stress_transition_4w | HIGH_PRIORITY_SEQUENCE_SIGNAL | 47 | 0.1264 | 0.6667 | INCREMENTAL_SEQUENCE_SIGNAL | stable, enough events, model improves over state baseline, and rule is not just current-state identity |
| high_transition_instability | recovery_quality_8w | NEEDS_TRIPLE_BARRIER_VALIDATION | 227 | 0.0733 | 0.6667 | INSUFFICIENT_EVIDENCE | some lift, but not enough for high-priority sequence signal gate |
| stress_new_state | ggg1_tail_risk_4w | NEEDS_TRIPLE_BARRIER_VALIDATION | 47 | 0.0723 | 1.0000 | INSUFFICIENT_EVIDENCE | some lift, but not enough for high-priority sequence signal gate |
| high_transition_instability | recovery_quality_4w | NEEDS_TRIPLE_BARRIER_VALIDATION | 227 | 0.0639 | 1.0000 | INSUFFICIENT_EVIDENCE | some lift, but not enough for high-priority sequence signal gate |
| stress_new_state | ggg1_underperformance_4w | NEEDS_TRIPLE_BARRIER_VALIDATION | 47 | 0.0462 | 0.6667 | INSUFFICIENT_EVIDENCE | some lift, but not enough for high-priority sequence signal gate |
| qqq_efa_spy_trend_after_calm_or_recovery | recovery_quality_4w | PROMISING_RECOVERY_QUALITY_SIGNAL | 42 | 0.1190 | 0.6667 | INCREMENTAL_SEQUENCE_SIGNAL | recovery-quality lift with interpretable sequence path |
| refined_neutral_deteriorating | stress_transition_4w | PROMISING_STRESS_WARNING_SIGNAL | 169 | 0.1232 | 1.0000 | DUPLICATES_CURRENT_STATE_ENGINE | risk/weakness target lift with interpretable state-sequence warning |
| calm_old_low_stress | ggg1_tail_risk_4w | PROMISING_STRESS_WARNING_SIGNAL | 50 | 0.1132 | 1.0000 | INCREMENTAL_SEQUENCE_SIGNAL | risk/weakness target lift with interpretable state-sequence warning |
| refined_neutral_deteriorating | ggg1_underperformance_4w | PROMISING_STRESS_WARNING_SIGNAL | 169 | 0.1098 | 1.0000 | DUPLICATES_CURRENT_STATE_ENGINE | risk/weakness target lift with interpretable state-sequence warning |
| refined_neutral_deteriorating | stress_transition_8w | PROMISING_STRESS_WARNING_SIGNAL | 167 | 0.0921 | 0.6667 | DUPLICATES_CURRENT_STATE_ENGINE | risk/weakness target lift with interpretable state-sequence warning |

## Rejected Sequence Rules
| rule_name | target | classification | event_count | precision_lift | stability | reason |
| --- | --- | --- | --- | --- | --- | --- |
| stress_old_state | qqq_interaction_success_label | TOO_RARE_OR_UNSTABLE | 1 | 0.5000 | 0.0000 | insufficient event coverage or subperiod stability |
| neutral_after_stress_short_dwell | false_recovery_label | TOO_RARE_OR_UNSTABLE | 4 | 0.4688 | 0.0000 | insufficient event coverage or subperiod stability |
| refined_neutral_healthy_after_stress | recovery_quality_8w | TOO_RARE_OR_UNSTABLE | 11 | 0.4097 | 1.0000 | insufficient event coverage or subperiod stability |
| recovery_confirmed_after_fragile_low_stress | ggg1_underperformance_4w | TOO_RARE_OR_UNSTABLE | 2 | 0.3228 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_fragile_after_stress | recovery_quality_8w | TOO_RARE_OR_UNSTABLE | 5 | 0.3006 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_fragile_after_stress | recovery_quality_4w | TOO_RARE_OR_UNSTABLE | 5 | 0.3000 | 0.0000 | insufficient event coverage or subperiod stability |
| neutral_after_stress_short_dwell | stress_transition_4w | TOO_RARE_OR_UNSTABLE | 23 | 0.2837 | 1.0000 | insufficient event coverage or subperiod stability |
| refined_neutral_deteriorating | false_recovery_label | TOO_RARE_OR_UNSTABLE | 16 | 0.2812 | 1.0000 | insufficient event coverage or subperiod stability |
| recovery_confirmed_after_fragile_low_stress | ggg1_tail_risk_4w | TOO_RARE_OR_UNSTABLE | 2 | 0.2532 | 0.0000 | insufficient event coverage or subperiod stability |
| neutral_after_stress_short_dwell | stress_transition_8w | TOO_RARE_OR_UNSTABLE | 23 | 0.2515 | 1.0000 | insufficient event coverage or subperiod stability |
| stress_memory_neutral | false_recovery_label | TOO_RARE_OR_UNSTABLE | 21 | 0.2426 | 1.0000 | insufficient event coverage or subperiod stability |
| refined_neutral_healthy_after_stress | recovery_quality_4w | TOO_RARE_OR_UNSTABLE | 11 | 0.2273 | 1.0000 | insufficient event coverage or subperiod stability |
| stress_new_state | false_recovery_label | TOO_RARE_OR_UNSTABLE | 4 | 0.2188 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_confirmed_after_fragile_low_stress | false_recovery_label | TOO_RARE_OR_UNSTABLE | 2 | 0.2188 | 0.0000 | insufficient event coverage or subperiod stability |
| stress_old_state | false_recovery_label | TOO_RARE_OR_UNSTABLE | 2 | 0.2188 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_confirmed_after_neutral | recovery_quality_8w | TOO_RARE_OR_UNSTABLE | 12 | 0.1673 | 1.0000 | insufficient event coverage or subperiod stability |
| qqq_efa_spy_trend_after_calm_or_recovery | qqq_interaction_success_label | TOO_RARE_OR_UNSTABLE | 3 | 0.1667 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_fragile_after_stress | stress_transition_8w | TOO_RARE_OR_UNSTABLE | 6 | 0.1500 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_fragile_after_stress | ggg1_tail_risk_4w | TOO_RARE_OR_UNSTABLE | 6 | 0.0865 | 0.0000 | insufficient event coverage or subperiod stability |
| recovery_confirmed_after_neutral | recovery_quality_4w | TOO_RARE_OR_UNSTABLE | 12 | 0.0833 | 1.0000 | insufficient event coverage or subperiod stability |

## Final Recommendation
**PROCEED_TO_SSS2_SEQUENCE_SIGNAL_VALIDATION**

Reason: At least one stable, interpretable, incremental sequence rule clears high-priority gates.

## Exact Prompt Outline For Next Phase
Implement Phase SSS2 as diagnostic-only sequence signal validation. Convert only the high-priority SSS rules into explicit lagged sequence signals, validate stress-transition, false-recovery, GGG1 weakness, triple-barrier, state/path, turnover, and redundancy behavior under walk-forward validation. Do not create portfolio candidates or change production/shadow/GGG1 logic.

## Resume-Worthy Technical Summary
SSS used `market_state_history_refined.csv` aligned to the 1,110-week GGG1 return series. It modeled canonical paths on the original five `market_state` labels and retained `refined_state`, Layer 2B probabilities, OOO signals/events, and QQQ interaction activity as lagged diagnostics/controls. It generated 1w/4w/8w transition matrices, dwell/age/path performance diagnostics, causal lagged n-gram, dwell, stress-memory, entropy, transition-instability, refined-state, QQQ, and OOO context features, then built stress-transition, recovery-quality, GGG1 underperformance, tail-risk, false-recovery, and optional QQQ-success targets. Walk-forward baselines included historical rate, current-state, previous-state, state+dwell, Markov/path, existing Layer 2B probability, and QQQ-only baselines. Sequence models were constrained L2 logistic, shallow decision tree, shallow random forest, shallow histogram gradient boosting, plus sequence+Layer2B and sequence+QQQ controls. SSS extracted interpretable path rules, checked QQQ/OOO overlap, diagnosed GGG1 weak windows, and produced a candidate sequence shortlist without changing production/shadow/GGG1 or creating portfolio candidates.
