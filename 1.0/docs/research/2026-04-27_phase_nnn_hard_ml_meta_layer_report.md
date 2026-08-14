# Phase NNN — Hard ML Meta-Layer Sprint

Date: 2026-04-27

## Commands executed
```
sed -n '1,140p' docs/research/2026-04-27_phase_mmm_composite_selective_signals_rebuild_report.md
sed -n '1,140p' docs/research/2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md
rg -n 'phase_jj|phase_kk|RandomForest|HistGradient|LogisticRegression|BUILD_VERSION_NAMES' scripts/build_improvement_artifacts.py scripts
python3 scripts/phase_nnn_hard_ml_meta_layer.py
BUILD_VERSION_NAMES=improved_phasennn_ml_risk_dial_overlay,improved_phasennn_ml_opportunity_dial_overlay SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py
```

## Files created / modified
- `scripts/phase_nnn_hard_ml_meta_layer.py`
- `data/research/phase_nnn_hard_ml_meta_layer/*.csv`
- `docs/research/2026-04-27_phase_nnn_hard_ml_meta_layer_report.md`
- `docs/research/project_journey.md`

## ML readiness check
| rows | features_used | median_feature_missingness | max_feature_missingness | minimum_train_size | targets_enough_samples | leakage_risk_flags | hard_ml_justified | lag_rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1110.000000 | 173.000000 | 0.006306 | 0.181081 | 260.000000 | 5.000000 | 0.000000 | True | All features shifted by one week; labels use forward 4w/8w outcomes only as targets. |

## Target definitions and class balance
Targets: GGG1 underperformance vs production/expectation, GGG1 adverse tail,
state-quality good outcome, stress transition, and optional 8w triple-barrier
bad outcome. All labels are forward outcomes and are not used as features.

| target | n | positive | negative | positive_rate | enough_samples |
| --- | --- | --- | --- | --- | --- |
| target_ggg1_underperformance_4w | 1110.000000 | 424.000000 | 686.000000 | 0.381982 | True |
| target_ggg1_adverse_tail_4w | 1110.000000 | 280.000000 | 830.000000 | 0.252252 | True |
| target_state_quality_good_4w | 1110.000000 | 514.000000 | 596.000000 | 0.463063 | True |
| target_stress_transition_4w | 1106.000000 | 306.000000 | 800.000000 | 0.276673 | True |
| target_triple_barrier_bad_8w | 1024.000000 | 61.000000 | 963.000000 | 0.059570 | True |

## Feature groups and leakage checks
Features came from existing Layer 2B regime fields, Phase 2B meta predictions,
GGG1 weights/turnover/rolling returns, Layer 2A sleeve/component rolling
features, and already available macro/ETF proxies. Every feature column is
shifted one week before modeling. Leakage risk flags: 0.

## Walk-forward validation scheme
Expanding-window validation, initial train `260` weeks, retrain
every `26` weeks, no random splits, no shuffled CV.

## ML metrics table
| target | model | n_oos | brier | baseline_brier | brier_delta_vs_baseline | auc | baseline_auc | auc_delta_vs_baseline | calibration_mae | high_risk_decile_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_ggg1_adverse_tail_4w | random_forest_small | 850.000000 | 0.200361 | 0.203074 | -0.002713 | 0.517904 | 0.416656 | 0.101248 | 0.031588 | 0.282353 |
| target_ggg1_adverse_tail_4w | baseline_state_rate | 850.000000 | 0.203074 | 0.203074 | 0.000000 | 0.416656 | 0.416656 | 0.000000 | 0.102471 | 0.102273 |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | 850.000000 | 0.206966 | 0.203074 | 0.003892 | 0.509437 | 0.416656 | 0.092781 | 0.104167 | 0.441860 |
| target_ggg1_underperformance_4w | random_forest_small | 850.000000 | 0.232492 | 0.248674 | -0.016182 | 0.619940 | 0.514712 | 0.105228 | 0.023600 | 0.576471 |
| target_ggg1_underperformance_4w | hist_gradient_shallow | 850.000000 | 0.242846 | 0.248674 | -0.005828 | 0.603642 | 0.514712 | 0.088930 | 0.073638 | 0.600000 |
| target_ggg1_underperformance_4w | decision_tree_depth2 | 850.000000 | 0.245802 | 0.248674 | -0.002872 | 0.609925 | 0.514712 | 0.095213 | 0.086161 | 0.556818 |
| target_state_quality_good_4w | random_forest_small | 850.000000 | 0.254223 | 0.258870 | -0.004647 | 0.506301 | 0.527240 | -0.020939 | 0.051525 | 0.482353 |
| target_state_quality_good_4w | baseline_state_rate | 850.000000 | 0.258870 | 0.258870 | 0.000000 | 0.527240 | 0.527240 | 0.000000 | 0.100958 | 0.576471 |
| target_state_quality_good_4w | hist_gradient_shallow | 850.000000 | 0.271220 | 0.258870 | 0.012349 | 0.507198 | 0.527240 | -0.020042 | 0.119277 | 0.447059 |
| target_stress_transition_4w | hist_gradient_shallow | 846.000000 | 0.095727 | 0.099326 | -0.003598 | 0.861382 | 0.826503 | 0.034879 | 0.040507 | 0.964706 |
| target_stress_transition_4w | baseline_state_rate | 846.000000 | 0.099326 | 0.099326 | 0.000000 | 0.826503 | 0.826503 | 0.000000 | 0.064422 | 0.822917 |
| target_stress_transition_4w | random_forest_small | 846.000000 | 0.100184 | 0.099326 | 0.000859 | 0.864093 | 0.826503 | 0.037589 | 0.067924 | 0.964706 |
| target_triple_barrier_bad_8w | baseline_state_rate | 842.000000 | 0.052330 | 0.052330 | 0.000000 | 0.354124 | 0.354124 | 0.000000 | 0.060429 | 0.000000 |
| target_triple_barrier_bad_8w | hist_gradient_shallow | 712.000000 | 0.054768 | 0.052330 | 0.002438 | 0.653012 | 0.354124 | 0.298888 | 0.024363 | 0.138889 |
| target_triple_barrier_bad_8w | random_forest_small | 712.000000 | 0.056370 | 0.052330 | 0.004040 | 0.443095 | 0.354124 | 0.088972 | 0.037200 | 0.000000 |

## Model selection
| target | model | serious_model | reason | brier_delta_vs_baseline | auc_delta_vs_baseline | auc | calibration_mae | high_risk_decile_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_ggg1_underperformance_4w | random_forest_small | True | passed strict OOS predictive/economic gates | -0.016182 | 0.105228 | 0.619940 | 0.023600 | 0.576471 |
| target_ggg1_underperformance_4w | hist_gradient_shallow | True | passed strict OOS predictive/economic gates | -0.005828 | 0.088930 | 0.603642 | 0.073638 | 0.600000 |
| target_stress_transition_4w | hist_gradient_shallow | True | passed strict OOS predictive/economic gates | -0.003598 | 0.034879 | 0.861382 | 0.040507 | 0.964706 |
| target_triple_barrier_bad_8w | logistic_l2_balanced | False | failed one or more strict OOS predictive/economic gates | 0.053002 | 0.335855 | 0.689979 | 0.146940 | 0.152778 |
| target_triple_barrier_bad_8w | logistic_simple | False | failed one or more strict OOS predictive/economic gates | 0.019636 | 0.309138 | 0.663262 | 0.063545 | 0.125000 |
| target_triple_barrier_bad_8w | hist_gradient_shallow | False | failed one or more strict OOS predictive/economic gates | 0.002438 | 0.298888 | 0.653012 | 0.024363 | 0.138889 |
| target_ggg1_adverse_tail_4w | random_forest_small | False | failed one or more strict OOS predictive/economic gates | -0.002713 | 0.101248 | 0.517904 | 0.031588 | 0.282353 |
| target_ggg1_adverse_tail_4w | hist_gradient_shallow | False | failed one or more strict OOS predictive/economic gates | 0.008717 | 0.097813 | 0.514469 | 0.091375 | 0.341176 |
| target_ggg1_underperformance_4w | decision_tree_depth2 | False | failed one or more strict OOS predictive/economic gates | -0.002872 | 0.095213 | 0.609925 | 0.086161 | 0.556818 |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | False | failed one or more strict OOS predictive/economic gates | 0.003892 | 0.092781 | 0.509437 | 0.104167 | 0.441860 |
| target_triple_barrier_bad_8w | random_forest_small | False | failed one or more strict OOS predictive/economic gates | 0.004040 | 0.088972 | 0.443095 | 0.037200 | 0.000000 |
| target_ggg1_adverse_tail_4w | logistic_l2_balanced | False | failed one or more strict OOS predictive/economic gates | 0.114401 | 0.081126 | 0.497782 | 0.278378 | 0.223529 |
| target_ggg1_adverse_tail_4w | logistic_simple | False | failed one or more strict OOS predictive/economic gates | 0.099824 | 0.077520 | 0.494176 | 0.263413 | 0.176471 |
| target_ggg1_underperformance_4w | logistic_l2_balanced | False | failed one or more strict OOS predictive/economic gates | 0.075520 | 0.053515 | 0.568227 | 0.240789 | 0.458824 |
| target_ggg1_underperformance_4w | logistic_simple | False | failed one or more strict OOS predictive/economic gates | 0.093174 | 0.040577 | 0.555289 | 0.274263 | 0.411765 |
| target_stress_transition_4w | random_forest_small | False | failed one or more strict OOS predictive/economic gates | 0.000859 | 0.037589 | 0.864093 | 0.067924 | 0.964706 |
| target_state_quality_good_4w | logistic_l2_balanced | False | failed one or more strict OOS predictive/economic gates | 0.074054 | 0.003951 | 0.531190 | 0.251985 | 0.564706 |
| target_state_quality_good_4w | logistic_simple | False | failed one or more strict OOS predictive/economic gates | 0.099745 | -0.002168 | 0.525072 | 0.289578 | 0.541176 |
| target_stress_transition_4w | logistic_l2_balanced | False | failed one or more strict OOS predictive/economic gates | 0.045204 | -0.002417 | 0.824087 | 0.104398 | 0.764706 |
| target_triple_barrier_bad_8w | decision_tree_depth2 | False | failed one or more strict OOS predictive/economic gates | 0.013329 | -0.005227 | 0.348897 | 0.071148 | 0.026667 |

## Calibration summary
Calibration buckets saved to `phase_nnn_calibration.csv`. Selection requires
calibration MAE <= 0.12.

## Feature importance
| target | model | feature | importance | abs_importance |
| --- | --- | --- | --- | --- |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | sleeve_cta_trend_long_only_vol_4w | 0.310032 | 0.310032 |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | ggg1_ret_4w | 0.277698 | 0.277698 |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | sleeve_weight_taa_10m_sma | 0.104981 | 0.104981 |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | regime_breadth_sma_43 | 0.050122 | 0.050122 |
| target_ggg1_adverse_tail_4w | decision_tree_depth2 | sleeve_composite_regime_offense_component_vol_13w | 0.026850 | 0.026850 |
| target_ggg1_adverse_tail_4w | logistic_l2_balanced | asset_UUP_vol_26w | 0.887802 | 0.887802 |
| target_ggg1_adverse_tail_4w | logistic_l2_balanced | asset_IWM_vol_26w | -0.785897 | 0.785897 |
| target_ggg1_adverse_tail_4w | logistic_l2_balanced | regime_market_trend_positive | -0.735393 | 0.735393 |
| target_ggg1_adverse_tail_4w | logistic_l2_balanced | asset_UUP_ret_26w | 0.690567 | 0.690567 |
| target_ggg1_adverse_tail_4w | logistic_l2_balanced | regime_breadth_26w_mom | 0.675272 | 0.675272 |
| target_ggg1_adverse_tail_4w | logistic_simple | asset_IWM_vol_26w | -1.222145 | 1.222145 |
| target_ggg1_adverse_tail_4w | logistic_simple | asset_UUP_vol_26w | 1.043210 | 1.043210 |
| target_ggg1_adverse_tail_4w | logistic_simple | asset_UUP_ret_26w | 1.003172 | 1.003172 |
| target_ggg1_adverse_tail_4w | logistic_simple | sleeve_composite_regime_defense_component_vol_13w | -0.937686 | 0.937686 |
| target_ggg1_adverse_tail_4w | logistic_simple | regime_breadth_26w_mom | 0.930039 | 0.930039 |
| target_ggg1_adverse_tail_4w | random_forest_small | sleeve_cta_trend_long_only_vol_4w | 0.047502 | 0.047502 |
| target_ggg1_adverse_tail_4w | random_forest_small | ggg1_vol_4w | 0.033379 | 0.033379 |
| target_ggg1_adverse_tail_4w | random_forest_small | asset_HYG_vol_13w | 0.023835 | 0.023835 |
| target_ggg1_adverse_tail_4w | random_forest_small | sleeve_weight_cta_trend_long_only | 0.023793 | 0.023793 |
| target_ggg1_adverse_tail_4w | random_forest_small | regime_avg_corr_risk_off_z | 0.022141 | 0.022141 |

## Did hard ML beat simpler ML?
Hard ML did not clear the strict model-selection gate unless marked
`serious_model=True` above. The HMM-style proxy was skipped because `hmmlearn`
is not an existing dependency.

## Portfolio candidates
| candidate | decision | delta_ann_return_vs_ggg1 | delta_sharpe_vs_ggg1 | delta_max_drawdown_vs_ggg1 | delta_cvar_5_vs_ggg1 | turnover_ratio_vs_production | turnover_under_cap | hidden_beta_not_higher | guard_states_preserved | guard_notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasennn_ml_risk_dial_overlay | REJECT | -0.000008 | 0.000128 | 0.000000 | 0.000005 | 1.099442 | True | True | True |  |
| improved_phasennn_ml_opportunity_dial_overlay | REJECT | -0.000005 | -0.000075 | 0.000000 | -0.000001 | 1.099800 | True | True | True |  |

## Candidate/reference metrics
| name | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | avg_turnover | avg_BIL | avg_SPY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasennn_ml_risk_dial_overlay | 0.071373 | 0.076194 | 0.943588 | -0.117739 | -0.025372 | 0.061765 | 0.266871 | 0.060227 |
| improved_phasennn_ml_opportunity_dial_overlay | 0.071376 | 0.076215 | 0.943385 | -0.117739 | -0.025378 | 0.061785 | 0.266567 | 0.060257 |
| improved_phaseggg_confirmed_only_robust_offense | 0.071381 | 0.076214 | 0.943460 | -0.117739 | -0.025377 | 0.061783 | 0.266580 | 0.060257 |
| improved_phase2b_regime_confidence_boost | 0.068923 | 0.077896 | 0.895263 | -0.139754 | -0.026181 | 0.056179 | 0.283918 | 0.070812 |
| improved_phase2b_combo_abc | 0.068584 | 0.077582 | 0.894473 | -0.136741 | -0.026085 | 0.056521 | 0.285552 | 0.070757 |

## Audit results
No quick/full audits were run because no NNN portfolio candidate qualified.

## Final decision
**KEEP_GGG1_AS_PRODUCTION_CANDIDATE**

Reason: ML prediction improved OOS, but portfolio pass-through failed the GGG1 selection gates.

Keep GGG1 as production candidate: **True**.
Harder ML should continue: **False**.

## Resume-worthy summary
NNN tested lagged regime, GGG1 state, sleeve, component, and macro proxy
features with controlled walk-forward classifiers. It only allows a portfolio
overlay if OOS prediction beats the simple state baseline by enough to be
economically meaningful. GGG1 remains the production candidate unless a future
ML target clears that bar and monetizes through the production pipeline.
