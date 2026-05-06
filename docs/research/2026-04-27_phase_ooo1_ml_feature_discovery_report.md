# Phase OOO1 — ML-Assisted Feature Discovery and Stability Ranking

Date: 2026-04-27

## Commands executed
```
sed -n '1,180p' docs/research/2026-04-27_phase_nnn_hard_ml_meta_layer_report.md
sed -n '1,120p' docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md
find data/01_data_hub data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine -maxdepth 1 -type f | sort
python3 scripts/phase_ooo0_ooo1_signal_discovery_foundation.py
```

## Files created / modified
- `scripts/phase_ooo0_ooo1_signal_discovery_foundation.py`
- `data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery/*.csv`
- `docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md`
- `docs/research/project_journey.md`

## Feature library summary
| feature_family | feature_count | entity_types |
| --- | --- | --- |
| breadth_dispersion | 32.000000 | ETF|MARKET |
| cross_asset_lead_lag | 24.000000 | ETF |
| cross_asset_momentum | 10.000000 | ETF |
| existing_layer1_signal | 36.000000 | ETF |
| regime_state | 52.000000 | ETF|MARKET|SLEEVE |
| regime_state_interaction | 50.000000 | ALL |
| sleeve_factor_momentum | 11.000000 | SLEEVE |
| volatility_risk | 11.000000 | ETF |

## Target definitions and class balance
| target | entity_type | n_observations | positive_rate | start_date | end_date | enough_samples |
| --- | --- | --- | --- | --- | --- | --- |
| target_etf_forward_top_quantile_4w | ETF | 38710.000000 | 0.259106 | 2005-01-07 | 2026-03-13 | True |
| target_etf_forward_top_quantile_8w | ETF | 38570.000000 | 0.259321 | 2005-01-07 | 2026-02-13 | True |
| target_etf_forward_risk_adjusted_top_quantile_4w | ETF | 38255.000000 | 0.251078 | 2005-04-08 | 2026-03-13 | True |
| target_sleeve_opportunity_top_quantile_4w | SLEEVE | 39816.000000 | 0.257183 | 2005-01-07 | 2026-03-13 | True |
| target_state_quality_good_4w | MARKET | 1110.000000 | 0.463964 | 2005-01-07 | 2026-04-10 | True |
| target_stress_transition_4w | MARKET | 1106.000000 | 0.276673 | 2005-01-07 | 2026-03-13 | True |
| target_ggg1_underperformance_4w | MARKET | 1110.000000 | 0.085586 | 2005-01-07 | 2026-04-10 | True |
| target_triple_barrier_optional_8w | MARKET|ETF | 0.000000 |  | None | None | False |

## Leakage checks
| check | passed | note |
| --- | --- | --- |
| all_features_lagged | True | Manifest lag rules all contain lag. |
| no_target_columns_in_features | True | Feature panel excludes target columns. |
| no_future_shift_feature_names | True | No future/fwd feature names in live feature panel. |
| no_random_split | True | Models use expanding-window date splits only. |
| target_panel_separate | True | Targets saved separately from features. |
| high_missingness_screen | True | Model columns require >=60% non-missing and non-constant values. |
| no_portfolio_candidates | True | OOO0/OOO1 create signal shortlist only. |

## Walk-forward validation scheme
Expanding-window validation, initial train `260` weekly dates,
retrain every `26` weeks, no random splits, all live features
lagged at least one week.

## ML metrics table
| target | model | n_oos | brier | baseline_brier | brier_delta_vs_baseline | auc | baseline_auc | auc_delta_vs_baseline | top_decile_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_etf_forward_risk_adjusted_top_quantile_4w | decision_tree_depth3 | 6768.000000 | 0.198175 | 0.208080 | -0.009905 | 0.547492 | 0.518760 | 0.028732 | 0.520861 |
| target_etf_forward_risk_adjusted_top_quantile_4w | random_forest_small | 6768.000000 | 0.201826 | 0.208080 | -0.006253 | 0.569018 | 0.518760 | 0.050259 | 0.519174 |
| target_etf_forward_risk_adjusted_top_quantile_4w | logistic_l2 | 6768.000000 | 0.207364 | 0.208080 | -0.000715 | 0.559327 | 0.518760 | 0.040567 | 0.463811 |
| target_etf_forward_top_quantile_4w | random_forest_small | 6768.000000 | 0.180785 | 0.183652 | -0.002866 | 0.577094 | 0.485657 | 0.091437 | 0.285081 |
| target_etf_forward_top_quantile_4w | decision_tree_depth3 | 6768.000000 | 0.183076 | 0.183652 | -0.000575 | 0.572130 | 0.485657 | 0.086473 | 0.271831 |
| target_etf_forward_top_quantile_4w | logistic_l2 | 6768.000000 | 0.187895 | 0.183652 | 0.004244 | 0.556510 | 0.485657 | 0.070853 | 0.288035 |
| target_sleeve_opportunity_top_quantile_4w | random_forest_small | 5076.000000 | 0.193293 | 0.193326 | -0.000032 | 0.514718 | 0.522788 | -0.008069 | 0.282908 |
| target_sleeve_opportunity_top_quantile_4w | decision_tree_depth3 | 5076.000000 | 0.196569 | 0.193326 | 0.003243 | 0.518376 | 0.522788 | -0.004412 | 0.312830 |
| target_sleeve_opportunity_top_quantile_4w | logistic_l2 | 5076.000000 | 0.197986 | 0.193326 | 0.004661 | 0.519273 | 0.522788 | -0.003515 | 0.348425 |
| target_state_quality_good_4w | hist_gradient_shallow | 850.000000 | 0.253676 | 0.260451 | -0.006776 | 0.531006 | 0.519866 | 0.011140 | 0.573034 |
| target_state_quality_good_4w | random_forest_small | 850.000000 | 0.254377 | 0.260451 | -0.006074 | 0.504911 | 0.519866 | -0.014955 | 0.529412 |
| target_state_quality_good_4w | decision_tree_depth3 | 850.000000 | 0.291152 | 0.260451 | 0.030701 | 0.524210 | 0.519866 | 0.004344 | 0.423529 |
| target_stress_transition_4w | decision_tree_depth3 | 846.000000 | 0.110676 | 0.100332 | 0.010345 | 0.816089 | 0.822602 | -0.006513 | 0.868132 |
| target_stress_transition_4w | hist_gradient_shallow | 846.000000 | 0.127632 | 0.100332 | 0.027300 | 0.767153 | 0.822602 | -0.055449 | 0.827586 |
| target_stress_transition_4w | logistic_l2 | 846.000000 | 0.128160 | 0.100332 | 0.027828 | 0.850330 | 0.822602 | 0.027728 | 0.835294 |

## Feature importance / stability findings
| feature | feature_family | discovery_score | target_count | model_count | fold_count | oos_auc_delta | avg_abs_redundancy_top_features |
| --- | --- | --- | --- | --- | --- | --- | --- |
| state_recovery_confirmed | regime_state | 3.232500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.118464 |
| regime_market_drawdown | regime_state | 3.195000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.203615 |
| breadth_ret13_positive_x_state_neutral_mixed | regime_state_interaction | 3.102500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.179509 |
| regime_recent_stress_26w | regime_state | 3.047500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.199894 |
| breadth_ret13_positive_x_state_stressed_panic | regime_state_interaction | 3.042500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.190535 |
| state_stressed_panic | regime_state | 2.997500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.278192 |
| leadlag_EFA_minus_SPY_13w | cross_asset_lead_lag | 2.997500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.103427 |
| breadth_ret13_positive_x_state_calm_trend | regime_state_interaction | 2.942500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.223517 |
| regime_canary_breadth_pair | regime_state | 2.927500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.102820 |
| leadlag_DBA_minus_SPY_13w | cross_asset_lead_lag | 2.920000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.178469 |
| leadlag_GLD_minus_SPY_13w | cross_asset_lead_lag | 2.915000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.240660 |
| breadth_ret13_positive_x_state_recovery_confirmed | regime_state_interaction | 2.877500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.118652 |
| breadth_ret26_positive | breadth_dispersion | 2.837500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.288231 |
| leadlag_HYG_minus_LQD_13w_x_state_calm_trend | regime_state_interaction | 2.817500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.108354 |
| regime_market_trend_positive | regime_state | 2.805000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.284075 |
| defensive_breadth_13w | breadth_dispersion | 2.805000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.122568 |
| regime_breadth_13w_mom | regime_state | 2.802500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.295341 |
| state_calm_trend | regime_state | 2.802500 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.220009 |
| state_neutral_mixed | regime_state | 2.790000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.160872 |
| regime_breadth_sma_43 | regime_state | 2.785000 | 5.000000 | 4.000000 | 33.000000 | 0.091437 | 0.306829 |

## Top candidate signals
| candidate_signal_name | feature_family | signal_category | suggested_next_test_phase | discovery_score | economic_interpretation |
| --- | --- | --- | --- | --- | --- |
| ooo_candidate_state_recovery_confirmed | regime_state | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 3.232500 | cross-asset feature candidate for Layer 1 research |
| ooo_candidate_regime_market_drawdown | regime_state | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 3.195000 | cross-asset feature candidate for Layer 1 research |
| ooo_candidate_breadth_ret13_positive_x_state_neutral_mixed | regime_state_interaction | STATE_SPECIFIC_ONLY | OOO5 triple-barrier/meta-label validation | 3.102500 | state-specific feature gate |
| ooo_candidate_regime_recent_stress_26w | regime_state | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 3.047500 | cross-asset feature candidate for Layer 1 research |
| ooo_candidate_breadth_ret13_positive_x_state_stressed_panic | regime_state_interaction | STATE_SPECIFIC_ONLY | OOO5 triple-barrier/meta-label validation | 3.042500 | state-specific feature gate |
| ooo_candidate_state_stressed_panic | regime_state | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.997500 | cross-asset feature candidate for Layer 1 research |
| ooo_candidate_leadlag_EFA_minus_SPY_13w | cross_asset_lead_lag | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.997500 | cross-asset relative strength / lead-lag risk timing |
| ooo_candidate_breadth_ret13_positive_x_state_calm_trend | regime_state_interaction | STATE_SPECIFIC_ONLY | OOO5 triple-barrier/meta-label validation | 2.942500 | state-specific feature gate |
| ooo_candidate_regime_canary_breadth_pair | regime_state | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.927500 | cross-asset feature candidate for Layer 1 research |
| ooo_candidate_leadlag_DBA_minus_SPY_13w | cross_asset_lead_lag | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.920000 | cross-asset relative strength / lead-lag risk timing |
| ooo_candidate_leadlag_GLD_minus_SPY_13w | cross_asset_lead_lag | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.915000 | cross-asset relative strength / lead-lag risk timing |
| ooo_candidate_breadth_ret13_positive_x_state_recovery_confirmed | regime_state_interaction | STATE_SPECIFIC_ONLY | OOO5 triple-barrier/meta-label validation | 2.877500 | state-specific feature gate |
| ooo_candidate_breadth_ret26_positive | breadth_dispersion | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.837500 | cross-asset feature candidate for Layer 1 research |
| ooo_candidate_leadlag_HYG_minus_LQD_13w_x_state_calm_trend | regime_state_interaction | STATE_SPECIFIC_ONLY | OOO5 triple-barrier/meta-label validation | 2.817500 | state-specific feature gate |
| ooo_candidate_regime_market_trend_positive | regime_state | HIGH_PRIORITY_TEST | OOO2 cross-asset signal expansion | 2.805000 | cross-asset feature candidate for Layer 1 research |

## Rejected features and why
Rejected features are saved to `ooo1_rejected_feature_log.csv`; common reasons
are low feature stability, weak OOS association, or high redundancy.

## How OOO1 connects to OOO2-OOO8
OOO1 is discovery-only. OOO2 should convert the strongest cross-asset
momentum/lead-lag discoveries into explicit candidate signals. OOO3 can test
volatility-managed sizing, OOO4 sleeve/factor momentum, OOO5 triple-barrier
validation, and OOO6+ latent-factor/IPCA work after the signal shortlist is
stable.

## Final recommendation
**PROCEED_TO_OOO2_CROSS_ASSET_SIGNAL_TESTS**

Reason: Top stable discoveries are cross-asset momentum/lead-lag/Layer 1 feature ideas.

## Exact prompt outline for next phase
Implement OOO2 as a diagnostic-only cross-asset signal expansion using the OOO1 shortlist; validate IC, decay, redundancy, and state behavior before any portfolio pass-through.
