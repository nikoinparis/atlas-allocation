# Phase PPP0/PPP1 -- IPCA / Latent Factor and Sleeve Discovery

Date: 2026-04-27

## Commands Executed
- `pwd && git status --short && rg --files | sed -n '1,220p'`
- `find docs/research data -maxdepth 3 -type d | sort | sed -n '1,220p'`
- `ls -lh portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv portfolio_version_returns_improved_phase2b_combo_abc 2>/dev/null || true`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md`
- `sed -n '1,220p' docs/research/2026-04-27_phase_iii_production_candidate_review_report.md`
- `tail -n 180 docs/research/project_journey.md`
- `find data/01_data_hub data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction data/research/phase_ooo_signal_discovery -maxdepth 2 -type f | sort | sed -n '1,260p'`
- `python3 - <<'PY' ...schema/package availability inspections...`
- `python3 scripts/phase_ppp_latent_factor_discovery.py`

## Files Created / Modified
- `scripts/phase_ppp_latent_factor_discovery.py`
- `data/research/phase_ppp_latent_factor_discovery/ppp_panel_etf_returns.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_panel_characteristics.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_panel_sleeve_returns.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_feature_manifest.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_data_quality_report.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_returns.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_loadings.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_pca_explained_variance.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_pca_loading_stability.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_state_performance.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_sleeve_correlation.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_factor_returns.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_characteristic_weights.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_factor_loadings.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_oos_prediction_metrics.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_state_performance.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_feature_stability.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_factor_validation_summary.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_factor_state_summary.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_factor_subperiod_stability.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_factor_redundancy_summary.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_factor_turnover_proxy.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_candidate_latent_sleeve_diagnostics.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_candidate_latent_sleeve_shortlist.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ggg1_latent_factor_exposure.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_ggg1_missing_factor_diagnostics.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_existing_sleeve_latent_redundancy.csv`
- `data/research/phase_ppp_latent_factor_discovery/ppp_next_action_recommendation.csv`
- `docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md`
- `docs/research/project_journey.md`

## Dataset Construction Summary
| panel | rows | columns | start | end |
| --- | --- | --- | --- | --- |
| ETF returns | 1110.0000 | 35.0000 | 2005-01-07 | 2026-04-10 |
| ETF characteristics long | 38850.0000 | 162.0000 | 2005-01-07 | 2026-04-10 |
| Sleeve/context returns | 1110.0000 | 46.0000 | 2005-01-07 | 2026-04-10 |

The ETF panel is aligned to GGG1 dates. Predictive characteristics are trailing
and lagged; state labels are retained for validation grouping and lagged
context, but not used as future labels in the IPCA-style cross-sectional model.
Layer 2A sleeve returns, GGG1 component returns, GGG1 ETF weights, and GGG1
sleeve weights were included as diagnostics/context rather than as live
predictive characteristics.

## Leakage Checks
| item | value | notes |
| --- | --- | --- |
| all_constructed_characteristics_lagged | True | rolling ETF features are shifted one week |
| layer1_values_lagged_again | True | source tradable Layer 1 values are shifted one additional week |
| ooo_values_lagged | True | OOO market-level signals/events are shifted one week |
| no_forward_returns_as_features | True | forward returns are never saved into characteristic panel |
| no_centered_rolling_windows | True | all rolling windows are trailing |
| no_random_train_test_split | True | PCA/IPCA validation uses full diagnostic or expanding/walk-forward windows |
| production_pins_unchanged | True | production=improved_phase2b_regime_confidence_boost; shadow=improved_phase2b_combo_abc; GGG1 remains candidate |

## PCA Factor Findings
Full-sample PCA is saved only as non-causal diagnostic context. The causal PCA
benchmark uses expanding-window refits after 260 weekly dates and
applies factor-mimicking weights to the next weekly ETF return.

Full-sample diagnostic explained variance for 5 factors:

| factor | explained_variance_ratio | cumulative_explained_variance |
| --- | --- | --- |
| f1 | 0.4756 | 0.4756 |
| f2 | 0.1405 | 0.6161 |
| f3 | 0.0833 | 0.6994 |
| f4 | 0.0379 | 0.7372 |
| f5 | 0.0288 | 0.7660 |

Top PCA validation rows:

| factor | causal_status | n_weeks | weekly_mean | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | corr_SPY | corr_BIL | corr_TLT | corr_GLD | corr_HYG | corr_LQD | corr_IEF | corr_QQQ | corr_EFA | corr_EEM | corr_VWO | corr_DBA | corr_PDBC | corr_XLE | corr_UUP | corr_VNQ | corr_GGG1 | max_abs_corr_existing_sleeve | most_redundant_existing_sleeve | max_abs_corr_known_proxy | max_abs_redundancy_any | uniqueness_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pca_exp_f1 | expanding_window_causal | 850.0000 | 0.0016 | 0.0785 | 0.1406 | 0.5587 | -0.3240 | -0.0476 | 0.9685 | -0.0657 | -0.2384 | 0.2308 | 0.7955 | 0.3789 | -0.1897 | 0.8617 | 0.9229 | 0.8263 | 0.8242 | 0.3177 | 0.4666 | 0.7323 | -0.3773 | 0.7807 | -0.1222 | 0.5979 | composite_macro_trend_diversifier_sleeve | 0.9685 | 0.9685 | 0.0315 |
| pca_exp_f2 | expanding_window_causal | 850.0000 | 0.0005 | 0.0231 | 0.0567 | 0.4081 | -0.1692 | -0.0174 | 0.1939 | 0.0243 | 0.6220 | 0.7650 | 0.4079 | 0.7252 | 0.6738 | 0.1466 | 0.2963 | 0.3117 | 0.3120 | 0.1448 | 0.2081 | 0.1353 | -0.5135 | 0.4350 | -0.0335 | 0.7394 | composite_structural_defense_sleeve | 0.7650 | 0.7650 | 0.2350 |
| pca_exp_f4 | expanding_window_causal | 850.0000 | 0.0006 | 0.0266 | 0.0684 | 0.3889 | -0.2943 | -0.0214 | 0.1031 | 0.0360 | 0.2243 | 0.2127 | 0.0428 | 0.1615 | 0.2150 | 0.1911 | 0.0691 | 0.0428 | 0.0344 | -0.2518 | -0.7150 | -0.4641 | -0.1152 | 0.1554 | 0.0181 | 0.1900 | composite_structural_defense_sleeve | 0.7150 | 0.7150 | 0.2850 |
| pca_exp_f5 | expanding_window_causal | 850.0000 | -0.0001 | -0.0037 | 0.0423 | -0.0875 | -0.2278 | -0.0136 | 0.3095 | -0.0294 | -0.2896 | -0.0832 | 0.2880 | -0.0148 | -0.2514 | 0.1937 | 0.2691 | 0.2060 | 0.2127 | 0.2158 | 0.4585 | 0.4728 | -0.0370 | 0.2619 | -0.0094 | 0.1886 | composite_macro_trend_diversifier_sleeve | 0.4728 | 0.4728 | 0.5272 |
| pca_exp_f3 | expanding_window_causal | 850.0000 | -0.0001 | -0.0071 | 0.0682 | -0.1045 | -0.4886 | -0.0215 | 0.0143 | 0.0319 | -0.1712 | 0.7675 | 0.0593 | -0.0624 | -0.1006 | -0.0384 | 0.1675 | 0.2899 | 0.2956 | 0.3426 | 0.6028 | 0.3393 | -0.3718 | 0.0200 | -0.0256 | 0.3327 | composite_macro_trend_diversifier_sleeve | 0.7675 | 0.7675 | 0.2325 |

## IPCA-Style Factor Findings
This is an internal IPCA-style characteristic-conditioned latent factor
approximation, not a claim of exact academic IPCA. It uses lagged ETF
characteristics, builds characteristic-managed factor portfolios, performs
expanding reduced-rank PCA on those characteristic-managed returns, and also
tests a walk-forward ridge cross-sectional return predictor.

OOS ridge / cross-sectional characteristic metrics:

| row_type | date | n_assets | pearson_ic | spearman_ic | top20_return | bottom20_return | top_bottom_spread | mse | baseline_mse | r2_vs_train_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| overall_summary |  | 29496.0000 | 0.0200 | 0.0308 | 0.0017 | 0.0009 | 0.0008 | 0.0006 | 0.0006 | -0.0126 |
| positive_rate_summary |  | 850.0000 | 0.5282 | 0.5306 | 0.5882 | 0.5435 | 0.5271 |  |  | 0.4282 |

Top IPCA-style characteristic weights:

| refit_date | factor | feature | characteristic_weight | abs_characteristic_weight | pca_component_weight | sign_rule | sign_anchor_abs_corr | train_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2011-07-01 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0787 | 0.0787 | -0.2707 | previous_loading_alignment |  | 338.0000 |
| 2014-06-27 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0783 | 0.0783 | -0.2705 | previous_loading_alignment |  | 494.0000 |
| 2013-12-27 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0780 | 0.0780 | -0.2708 | previous_loading_alignment |  | 468.0000 |
| 2014-12-26 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0778 | 0.0778 | -0.2695 | previous_loading_alignment |  | 520.0000 |
| 2010-01-01 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0777 | 0.0777 | -0.2599 | dominant_proxy_XLE | 0.6765 | 260.0000 |
| 2013-06-28 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0770 | 0.0770 | -0.2684 | previous_loading_alignment |  | 442.0000 |
| 2012-06-29 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0769 | 0.0769 | -0.2664 | previous_loading_alignment |  | 390.0000 |
| 2010-07-02 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0767 | 0.0767 | -0.2627 | previous_loading_alignment |  | 286.0000 |
| 2012-12-28 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0766 | 0.0766 | -0.2672 | previous_loading_alignment |  | 416.0000 |
| 2010-12-31 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0765 | 0.0765 | -0.2648 | previous_loading_alignment |  | 312.0000 |
| 2011-12-30 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0763 | 0.0763 | -0.2652 | previous_loading_alignment |  | 364.0000 |
| 2015-06-26 | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0763 | 0.0763 | -0.2669 | previous_loading_alignment |  | 546.0000 |

Top IPCA-style feature stability rows:

| source | factor | feature | mean_weight | mean_abs_weight | weight_std | sign_stability | n_refits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ipca_style_factor_pca | ipca_style_f2 | l1_bab_bab_score_asset_class_neutral_tradable | -0.0720 | 0.0720 | 0.0050 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | l1_quality_quality_score_asset_class_neutral_tradable | -0.0662 | 0.0662 | 0.0066 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f3 | l1_carry_carry_score_asset_class_neutral_tradable | 0.0542 | 0.0542 | 0.0073 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | l1_carry_carry_score_tradable | -0.0518 | 0.0518 | 0.0157 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f3 | l1_xsmom_xsmom_asset_class_neutral_tradable | -0.0518 | 0.0518 | 0.0055 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f3 | l1_reversal_reversal_4w_asset_class_neutral_tradable | -0.0490 | 0.0490 | 0.0060 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | vol_4w | 0.0460 | 0.0460 | 0.0010 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | vol_13w | 0.0432 | 0.0432 | 0.0008 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | l1_carry_carry_yield_trailing_52w_tradable | -0.0425 | 0.0425 | 0.0183 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | vol_26w | 0.0421 | 0.0421 | 0.0009 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f3 | l1_reversal_reversal_1w_asset_class_neutral_tradable | -0.0383 | 0.0383 | 0.0066 | 1.0000 | 33.0000 |
| ipca_style_factor_pca | ipca_style_f2 | l1_quality_quality_score_tradable | -0.0383 | 0.0383 | 0.0021 | 1.0000 | 33.0000 |

## Factor Validation Summary
| factor | causal_status | n_weeks | weekly_mean | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | corr_SPY | corr_BIL | corr_TLT | corr_GLD | corr_HYG | corr_LQD | corr_IEF | corr_QQQ | corr_EFA | corr_EEM | corr_VWO | corr_DBA | corr_PDBC | corr_XLE | corr_UUP | corr_VNQ | corr_GGG1 | max_abs_corr_existing_sleeve | most_redundant_existing_sleeve | max_abs_corr_known_proxy | max_abs_redundancy_any | uniqueness_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pca_exp_f1 | expanding_window_causal | 850.0000 | 0.0016 | 0.0785 | 0.1406 | 0.5587 | -0.3240 | -0.0476 | 0.9685 | -0.0657 | -0.2384 | 0.2308 | 0.7955 | 0.3789 | -0.1897 | 0.8617 | 0.9229 | 0.8263 | 0.8242 | 0.3177 | 0.4666 | 0.7323 | -0.3773 | 0.7807 | -0.1222 | 0.5979 | composite_macro_trend_diversifier_sleeve | 0.9685 | 0.9685 | 0.0315 |
| pca_full_diag_f2 | full_sample_noncausal_diagnostic | 1109.0000 | 0.0006 | 0.0295 | 0.0568 | 0.5196 | -0.1993 | -0.0167 | -0.1612 | 0.0748 | 0.7393 | 0.6947 | 0.0635 | 0.5723 | 0.7821 | -0.1652 | -0.0397 | -0.0370 | -0.0368 | 0.0294 | -0.0595 | -0.1457 | -0.3965 | 0.0444 | 0.0015 | 0.6508 | composite_structural_defense_sleeve | 0.7821 | 0.7821 | 0.2179 |
| pca_full_diag_f1 | full_sample_noncausal_diagnostic | 1109.0000 | 0.0014 | 0.0647 | 0.1558 | 0.4156 | -0.5386 | -0.0539 | 0.9691 | -0.1718 | -0.2439 | 0.1916 | 0.7643 | 0.3212 | -0.2037 | 0.8713 | 0.9332 | 0.8629 | 0.8625 | 0.3719 | 0.4644 | 0.7568 | -0.3866 | 0.7830 | -0.0684 | 0.5041 | composite_macro_trend_diversifier_sleeve | 0.9691 | 0.9691 | 0.0309 |
| pca_exp_f2 | expanding_window_causal | 850.0000 | 0.0005 | 0.0231 | 0.0567 | 0.4081 | -0.1692 | -0.0174 | 0.1939 | 0.0243 | 0.6220 | 0.7650 | 0.4079 | 0.7252 | 0.6738 | 0.1466 | 0.2963 | 0.3117 | 0.3120 | 0.1448 | 0.2081 | 0.1353 | -0.5135 | 0.4350 | -0.0335 | 0.7394 | composite_structural_defense_sleeve | 0.7650 | 0.7650 | 0.2350 |
| pca_exp_f4 | expanding_window_causal | 850.0000 | 0.0006 | 0.0266 | 0.0684 | 0.3889 | -0.2943 | -0.0214 | 0.1031 | 0.0360 | 0.2243 | 0.2127 | 0.0428 | 0.1615 | 0.2150 | 0.1911 | 0.0691 | 0.0428 | 0.0344 | -0.2518 | -0.7150 | -0.4641 | -0.1152 | 0.1554 | 0.0181 | 0.1900 | composite_structural_defense_sleeve | 0.7150 | 0.7150 | 0.2850 |
| ipca_style_f2 | ipca_style_walk_forward_causal | 850.0000 | 0.0004 | 0.0184 | 0.0748 | 0.2461 | -0.2108 | -0.0266 | 0.7903 | -0.0568 | -0.3525 | 0.2950 | 0.5781 | 0.1567 | -0.3116 | 0.7207 | 0.7240 | 0.6972 | 0.6952 | 0.3244 | 0.6034 | 0.6896 | -0.2671 | 0.5512 | -0.1321 | 0.6805 | composite_macro_trend_diversifier_sleeve | 0.7903 | 0.7903 | 0.2097 |
| pca_full_diag_f3 | full_sample_noncausal_diagnostic | 1109.0000 | 0.0001 | 0.0030 | 0.0791 | 0.0384 | -0.4913 | -0.0266 | -0.0142 | 0.0310 | -0.1390 | 0.8333 | -0.0179 | -0.0773 | -0.0720 | -0.0539 | 0.1715 | 0.2538 | 0.2622 | 0.4015 | 0.6397 | 0.3563 | -0.4389 | -0.0159 | -0.0345 | 0.4337 | composite_macro_trend_diversifier_sleeve | 0.8333 | 0.8333 | 0.1667 |
| pca_exp_f5 | expanding_window_causal | 850.0000 | -0.0001 | -0.0037 | 0.0423 | -0.0875 | -0.2278 | -0.0136 | 0.3095 | -0.0294 | -0.2896 | -0.0832 | 0.2880 | -0.0148 | -0.2514 | 0.1937 | 0.2691 | 0.2060 | 0.2127 | 0.2158 | 0.4585 | 0.4728 | -0.0370 | 0.2619 | -0.0094 | 0.1886 | composite_macro_trend_diversifier_sleeve | 0.4728 | 0.4728 | 0.5272 |
| pca_exp_f3 | expanding_window_causal | 850.0000 | -0.0001 | -0.0071 | 0.0682 | -0.1045 | -0.4886 | -0.0215 | 0.0143 | 0.0319 | -0.1712 | 0.7675 | 0.0593 | -0.0624 | -0.1006 | -0.0384 | 0.1675 | 0.2899 | 0.2956 | 0.3426 | 0.6028 | 0.3393 | -0.3718 | 0.0200 | -0.0256 | 0.3327 | composite_macro_trend_diversifier_sleeve | 0.7675 | 0.7675 | 0.2325 |
| ipca_style_f1 | ipca_style_walk_forward_causal | 850.0000 | -0.0002 | -0.0113 | 0.0785 | -0.1444 | -0.3804 | -0.0252 | 0.2431 | 0.0140 | -0.1417 | -0.0177 | 0.3620 | 0.1873 | -0.0974 | 0.1651 | 0.2974 | 0.2757 | 0.2802 | 0.0970 | 0.2467 | 0.3100 | -0.1836 | 0.2462 | 0.0236 | 0.1974 | composite_macro_trend_diversifier_sleeve | 0.3620 | 0.3620 | 0.6380 |
| ipca_style_f3 | ipca_style_walk_forward_causal | 850.0000 | -0.0004 | -0.0216 | 0.0647 | -0.3332 | -0.3933 | -0.0206 | -0.2552 | 0.0037 | 0.0151 | 0.0491 | -0.1775 | -0.1439 | 0.0410 | -0.2800 | -0.1437 | -0.1015 | -0.0967 | 0.0603 | 0.1644 | 0.0103 | -0.0219 | -0.1562 | -0.0094 | 0.3272 | composite_macro_trend_diversifier_sleeve | 0.2800 | 0.3272 | 0.6728 |
| pca_full_diag_f5 | full_sample_noncausal_diagnostic | 1109.0000 | -0.0003 | -0.0159 | 0.0393 | -0.4055 | -0.3202 | -0.0125 | 0.1924 | -0.0484 | -0.2917 | -0.3448 | 0.0289 | -0.2127 | -0.2810 | 0.3236 | 0.3301 | 0.4358 | 0.4314 | 0.2104 | 0.1906 | 0.1919 | -0.1080 | -0.0966 | 0.0631 | 0.2091 | composite_structural_defense_sleeve | 0.4358 | 0.4358 | 0.5642 |
| pca_full_diag_f4 | full_sample_noncausal_diagnostic | 1109.0000 | -0.0006 | -0.0320 | 0.0780 | -0.4109 | -0.6342 | -0.0260 | 0.0628 | -0.0359 | -0.1981 | -0.1559 | 0.1317 | -0.0142 | -0.1612 | -0.0764 | 0.0417 | 0.0186 | 0.0246 | 0.2923 | 0.7778 | 0.5395 | 0.0398 | 0.0180 | -0.0311 | 0.0596 | composite_anti_chop_clarity | 0.7778 | 0.7778 | 0.2222 |

## State-by-State Factor Behavior
Top PCA state rows:

| factor | market_state | n_weeks | weekly_mean | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pca_exp_f1 | recovery_fragile | 35.0000 | 0.0061 | 0.3706 | 0.0806 | 4.5994 | -0.0213 | -0.0184 |
| pca_exp_f1 | recovery_confirmed | 41.0000 | 0.0055 | 0.3272 | 0.0787 | 4.1583 | -0.0319 | -0.0135 |
| pca_exp_f1 | calm_trend | 257.0000 | 0.0022 | 0.1166 | 0.0915 | 1.2738 | -0.0890 | -0.0277 |
| pca_exp_f1 | neutral_mixed | 368.0000 | 0.0008 | 0.0333 | 0.1306 | 0.2549 | -0.2489 | -0.0421 |
| pca_exp_f1 | stressed_panic | 149.0000 | 0.0007 | 0.0083 | 0.2287 | 0.0361 | -0.2574 | -0.0776 |
| pca_exp_f2 | recovery_confirmed | 41.0000 | 0.0015 | 0.0793 | 0.0358 | 2.2151 | -0.0145 | -0.0063 |
| pca_exp_f2 | recovery_fragile | 35.0000 | 0.0012 | 0.0631 | 0.0453 | 1.3920 | -0.0174 | -0.0096 |
| pca_exp_f2 | calm_trend | 257.0000 | 0.0004 | 0.0218 | 0.0461 | 0.4722 | -0.0957 | -0.0133 |
| pca_exp_f2 | neutral_mixed | 368.0000 | 0.0004 | 0.0205 | 0.0562 | 0.3652 | -0.1080 | -0.0179 |
| pca_exp_f2 | stressed_panic | 149.0000 | 0.0002 | 0.0078 | 0.0775 | 0.1009 | -0.1369 | -0.0240 |
| pca_exp_f3 | recovery_confirmed | 41.0000 | 0.0010 | 0.0494 | 0.0516 | 0.9581 | -0.0305 | -0.0117 |
| pca_exp_f3 | neutral_mixed | 368.0000 | -0.0001 | -0.0070 | 0.0683 | -0.1023 | -0.3519 | -0.0216 |
| pca_exp_f3 | stressed_panic | 149.0000 | -0.0001 | -0.0107 | 0.0847 | -0.1258 | -0.1349 | -0.0254 |
| pca_exp_f3 | calm_trend | 257.0000 | -0.0002 | -0.0124 | 0.0581 | -0.2127 | -0.2044 | -0.0181 |
| pca_exp_f3 | recovery_fragile | 35.0000 | -0.0003 | -0.0193 | 0.0740 | -0.2613 | -0.0653 | -0.0213 |
| pca_exp_f4 | stressed_panic | 149.0000 | 0.0016 | 0.0841 | 0.0961 | 0.8752 | -0.1078 | -0.0253 |
| pca_exp_f4 | recovery_confirmed | 41.0000 | 0.0006 | 0.0273 | 0.0716 | 0.3821 | -0.0526 | -0.0194 |
| pca_exp_f4 | neutral_mixed | 368.0000 | 0.0004 | 0.0174 | 0.0656 | 0.2651 | -0.1974 | -0.0229 |
| pca_exp_f4 | calm_trend | 257.0000 | 0.0003 | 0.0127 | 0.0487 | 0.2598 | -0.0669 | -0.0147 |
| pca_exp_f4 | recovery_fragile | 35.0000 | -0.0002 | -0.0111 | 0.0739 | -0.1501 | -0.0788 | -0.0186 |

Top IPCA-style state rows:

| factor | market_state | n_weeks | weekly_mean | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ipca_style_f1 | recovery_fragile | 35.0000 | 0.0015 | 0.0794 | 0.0601 | 1.3223 | -0.0538 | -0.0149 |
| ipca_style_f1 | calm_trend | 257.0000 | 0.0003 | 0.0158 | 0.0504 | 0.3132 | -0.0973 | -0.0143 |
| ipca_style_f1 | recovery_confirmed | 41.0000 | 0.0002 | 0.0071 | 0.0541 | 0.1312 | -0.0355 | -0.0109 |
| ipca_style_f1 | stressed_panic | 149.0000 | -0.0002 | -0.0155 | 0.1210 | -0.1281 | -0.1700 | -0.0415 |
| ipca_style_f1 | neutral_mixed | 368.0000 | -0.0007 | -0.0382 | 0.0763 | -0.5009 | -0.3364 | -0.0221 |
| ipca_style_f2 | recovery_confirmed | 41.0000 | 0.0025 | 0.1373 | 0.0390 | 3.5209 | -0.0186 | -0.0084 |
| ipca_style_f2 | recovery_fragile | 35.0000 | 0.0026 | 0.1435 | 0.0534 | 2.6878 | -0.0230 | -0.0107 |
| ipca_style_f2 | calm_trend | 257.0000 | 0.0006 | 0.0287 | 0.0532 | 0.5393 | -0.0587 | -0.0160 |
| ipca_style_f2 | neutral_mixed | 368.0000 | 0.0002 | 0.0061 | 0.0764 | 0.0795 | -0.1825 | -0.0266 |
| ipca_style_f2 | stressed_panic | 149.0000 | -0.0004 | -0.0263 | 0.1065 | -0.2465 | -0.1801 | -0.0387 |
| ipca_style_f3 | recovery_fragile | 35.0000 | 0.0005 | 0.0265 | 0.0510 | 0.5190 | -0.0212 | -0.0163 |
| ipca_style_f3 | recovery_confirmed | 41.0000 | -0.0002 | -0.0142 | 0.0653 | -0.2182 | -0.0402 | -0.0199 |
| ipca_style_f3 | stressed_panic | 149.0000 | -0.0005 | -0.0301 | 0.0962 | -0.3131 | -0.1786 | -0.0280 |
| ipca_style_f3 | neutral_mixed | 368.0000 | -0.0004 | -0.0226 | 0.0613 | -0.3692 | -0.2809 | -0.0186 |
| ipca_style_f3 | calm_trend | 257.0000 | -0.0004 | -0.0226 | 0.0456 | -0.4960 | -0.1420 | -0.0148 |

## Redundancy vs Existing Sleeves and Proxies
| factor | comparison_type | comparison_name | correlation | abs_correlation |
| --- | --- | --- | --- | --- |
| ipca_style_f1 | known_proxy | HYG | 0.3620 | 0.3620 |
| ipca_style_f1 | factor | pca_full_diag_f4 | 0.3107 | 0.3107 |
| ipca_style_f1 | known_proxy | XLE | 0.3100 | 0.3100 |
| ipca_style_f2 | factor | pca_exp_f1 | 0.8309 | 0.8309 |
| ipca_style_f2 | factor | pca_full_diag_f1 | 0.8277 | 0.8277 |
| ipca_style_f2 | known_proxy | SPY | 0.7903 | 0.7903 |
| ipca_style_f3 | existing_sleeve_or_component | sleeve_return_composite_macro_trend_diversifier_sleeve | -0.3272 | 0.3272 |
| ipca_style_f3 | known_proxy | QQQ | -0.2800 | 0.2800 |
| ipca_style_f3 | known_proxy | SPY | -0.2552 | 0.2552 |
| pca_exp_f1 | factor | pca_full_diag_f1 | 0.9996 | 0.9996 |
| pca_exp_f1 | known_proxy | SPY | 0.9685 | 0.9685 |
| pca_exp_f1 | known_proxy | EFA | 0.9229 | 0.9229 |
| pca_exp_f2 | factor | pca_full_diag_f2 | 0.9156 | 0.9156 |
| pca_exp_f2 | known_proxy | GLD | 0.7650 | 0.7650 |
| pca_exp_f2 | existing_sleeve_or_component | sleeve_return_composite_structural_defense_sleeve | 0.7394 | 0.7394 |
| pca_exp_f3 | factor | pca_full_diag_f3 | 0.9926 | 0.9926 |
| pca_exp_f3 | known_proxy | GLD | 0.7675 | 0.7675 |
| pca_exp_f3 | known_proxy | PDBC | 0.6028 | 0.6028 |
| pca_exp_f4 | factor | pca_full_diag_f4 | -0.9259 | 0.9259 |
| pca_exp_f4 | known_proxy | PDBC | -0.7150 | 0.7150 |
| pca_exp_f4 | known_proxy | XLE | -0.4641 | 0.4641 |
| pca_exp_f5 | factor | pca_full_diag_f4 | 0.5462 | 0.5462 |
| pca_exp_f5 | known_proxy | XLE | 0.4728 | 0.4728 |
| pca_exp_f5 | known_proxy | PDBC | 0.4585 | 0.4585 |

## Candidate Latent Sleeve Shortlist
_None._

All causal factor diagnostics:

| factor | factor_type | economic_interpretation | top_positive_etf_loadings | top_negative_etf_loadings | state_where_it_helps | state_where_it_hurts | ann_return | sharpe | max_drawdown | positive_subperiod_share | redundancy_with_existing_sleeves | most_redundant_existing_sleeve | max_abs_corr_known_proxy | corr_GGG1 | fills_missing_role | tradeable_as_long_only_etf_sleeve | requires_long_short_construction | would_violate_project_constraints | deserves_ooo_ppp_follow_up | avg_l1_turnover_proxy | classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pca_exp_f1 | equity beta | Dominant positive relationship is broad equity/risk-on beta. | SPY,VUG,VTV,EFA,XLI,IWM | TLT,IEF,SHY,UUP,BIL,MBB | recovery_fragile | stressed_panic | 0.0785 | 0.5587 | -0.3240 | 0.7500 | 0.5979 | composite_macro_trend_diversifier_sleeve | 0.9685 | -0.1222 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0004 | REDUNDANT_WITH_EXISTING_SLEEVE |
| pca_exp_f2 | duration/rates | Dominant positive relationship is Treasury duration/rates exposure. | IEF,TIP,TLT,LQD,SHY,MBB | UUP,XLF,XLY,XLK,QQQ,XLI | recovery_confirmed | stressed_panic | 0.0231 | 0.4081 | -0.1692 | 0.7500 | 0.7394 | composite_structural_defense_sleeve | 0.7650 | -0.0335 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0015 | REDUNDANT_WITH_EXISTING_SLEEVE |
| ipca_style_f2 | equity beta | Dominant positive relationship is broad equity/risk-on beta. | USO,SLV,QQQ,XLK,IWM,XLF | BIL,SHY,MBB,TIP,IEF,HYG | recovery_fragile | stressed_panic | 0.0184 | 0.2461 | -0.2108 | 0.5000 | 0.6805 | composite_macro_trend_diversifier_sleeve | 0.7903 | -0.1321 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.1441 | REDUNDANT_WITH_EXISTING_SLEEVE |
| pca_exp_f3 | inflation/real asset | Dominant relationship is commodity, real-asset, or dollar/inflation exposure. | IAU,GLD,SLV,USO,DBA,XLE | LQD,UUP,TLT,IEF,MBB,XLV | recovery_confirmed | recovery_fragile | -0.0071 | -0.1045 | -0.4886 | 0.2500 | 0.3327 | composite_macro_trend_diversifier_sleeve | 0.7675 | -0.0256 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0012 | REDUNDANT_WITH_EXISTING_SLEEVE |
| pca_exp_f5 | inflation/real asset | Dominant relationship is commodity, real-asset, or dollar/inflation exposure. | BIL,USO,VNQ,SHY,TIP,XLF | EWJ,XLV,VWO,EEM,GLD,IAU | recovery_confirmed | stressed_panic | -0.0037 | -0.0875 | -0.2278 | 0.2500 | 0.1886 | composite_macro_trend_diversifier_sleeve | 0.4728 | -0.0094 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0056 | WEAK_OR_UNSTABLE |
| pca_exp_f4 | hidden/unknown | No single known proxy or ETF sleeve interpretation dominates. | VNQ,GLD,IAU,XLY,XLF,QQQ | USO,DBA,XLE,PDBC,LQD,XLU | stressed_panic | recovery_fragile | 0.0266 | 0.3889 | -0.2943 | 0.5000 | 0.1900 | composite_structural_defense_sleeve | 0.7150 | 0.0181 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0029 | UNTRADEABLE_OR_TOO_COMPLEX |
| ipca_style_f1 | hidden/unknown | No single known proxy or ETF sleeve interpretation dominates. | USO,XLE,SLV,TLT,EEM,DBA | QQQ,XLK,VUG,SPY,XLY,XLV | recovery_fragile | neutral_mixed | -0.0113 | -0.1444 | -0.3804 | 0.2500 | 0.1974 | composite_macro_trend_diversifier_sleeve | 0.3620 | 0.0236 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.2117 | UNTRADEABLE_OR_TOO_COMPLEX |
| ipca_style_f3 | hidden/unknown | No single known proxy or ETF sleeve interpretation dominates. | USO,XLE,VWO,SLV,HYG,EEM | QQQ,VUG,SHY,BIL,XLK,XLY | recovery_fragile | stressed_panic | -0.0216 | -0.3332 | -0.3933 | 0.0000 | 0.3272 | composite_macro_trend_diversifier_sleeve | 0.2800 | -0.0094 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.4255 | UNTRADEABLE_OR_TOO_COMPLEX |

## New Latent Sleeve Decision
The shortlist file is the gating artifact. PPP does not create or promote any
portfolio candidate. A new latent sleeve is justified only if a factor is
stable, interpretable, not redundant with known sleeves/proxies/GGG1, and
tradeable under project constraints.

## Comparison to GGG1
GGG1 factor exposure summary:

| factor | mean | min | max |
| --- | --- | --- | --- |
| ipca_style_f1 | -0.0141 | -0.0690 | 0.0135 |
| ipca_style_f2 | -0.0078 | -0.0527 | 0.0194 |
| ipca_style_f3 | -0.0076 | -0.0526 | 0.0274 |
| pca_exp_f1 | 0.0122 | -0.0089 | 0.0347 |
| pca_exp_f2 | 0.0204 | 0.0000 | 0.0536 |
| pca_exp_f3 | 0.0007 | -0.0357 | 0.0430 |
| pca_exp_f4 | 0.0052 | -0.0290 | 0.0350 |
| pca_exp_f5 | 0.0140 | -0.0246 | 0.1355 |

Missing-factor diagnostics:

| factor | avg_ggg1_weighted_factor_exposure | best_state_for_factor | worst_state_for_factor | best_state_avg_ggg1_exposure | worst_state_avg_ggg1_exposure | max_abs_corr_existing_sleeve | max_abs_corr_known_proxy | corr_GGG1 | proxy_disguise | could_plausibly_improve_ggg1 | diagnostic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pca_exp_f1 | 0.0122 | recovery_fragile | stressed_panic | 0.0106 | 0.0012 | 0.5979 | 0.9685 | -0.1222 | 1.0000 | 0.0000 | MOSTLY_REDUNDANT_OR_PROXY_DISGUISE |
| pca_exp_f2 | 0.0204 | recovery_confirmed | stressed_panic | 0.0308 | 0.0130 | 0.7394 | 0.7650 | -0.0335 | 1.0000 | 0.0000 | MOSTLY_REDUNDANT_OR_PROXY_DISGUISE |
| pca_exp_f3 | 0.0007 | recovery_confirmed | recovery_fragile | 0.0018 | -0.0035 | 0.3327 | 0.7675 | -0.0256 | 1.0000 | 0.0000 | MOSTLY_REDUNDANT_OR_PROXY_DISGUISE |
| pca_exp_f4 | 0.0052 | stressed_panic | recovery_fragile | 0.0033 | 0.0048 | 0.1900 | 0.7150 | 0.0181 | 0.0000 | 0.0000 | WATCHLIST_NOT_ENOUGH_FOR_SLEEVE |
| pca_exp_f5 | 0.0140 | recovery_confirmed | stressed_panic | 0.0091 | 0.0378 | 0.1886 | 0.4728 | -0.0094 | 0.0000 | 0.0000 | WEAK_OR_UNSTABLE_DO_NOT_ADD |
| ipca_style_f1 | -0.0141 | recovery_fragile | neutral_mixed | -0.0164 | -0.0125 | 0.1974 | 0.3620 | 0.0236 | 0.0000 | 0.0000 | WEAK_OR_UNSTABLE_DO_NOT_ADD |
| ipca_style_f2 | -0.0078 | recovery_fragile | stressed_panic | -0.0074 | -0.0173 | 0.6805 | 0.7903 | -0.1321 | 1.0000 | 0.0000 | MOSTLY_REDUNDANT_OR_PROXY_DISGUISE |
| ipca_style_f3 | -0.0076 | recovery_fragile | stressed_panic | -0.0066 | -0.0065 | 0.3272 | 0.2800 | -0.0094 | 0.0000 | 0.0000 | WEAK_OR_UNSTABLE_DO_NOT_ADD |

Existing sleeve latent redundancy:

| factor | sleeve_or_component | correlation | abs_correlation |
| --- | --- | --- | --- |
| ipca_style_f1 | composite_macro_trend_diversifier_sleeve | -0.1974 | 0.1974 |
| ipca_style_f1 | composite_structural_defense_sleeve | 0.1230 | 0.1230 |
| ipca_style_f1 | composite_calm_carry_sleeve | -0.1033 | 0.1033 |
| ipca_style_f1 | composite_recovery_confirmed_offense_sleeve | -0.0767 | 0.0767 |
| ipca_style_f1 | component::composite_regime_cash_component | 0.0657 | 0.0657 |
| ipca_style_f1 | composite_recovery_transition | 0.0611 | 0.0611 |
| ipca_style_f1 | composite_healthier_recovery_specialist | 0.0557 | 0.0557 |
| ipca_style_f1 | cta_trend_long_only | 0.0549 | 0.0549 |
| ipca_style_f1 | composite_confirmation_aware_momentum | 0.0533 | 0.0533 |
| ipca_style_f1 | cta_trend_vol_managed | 0.0525 | 0.0525 |
| ipca_style_f1 | sector_factor_rotation | 0.0440 | 0.0440 |
| ipca_style_f1 | component::composite_regime_offense_component | 0.0435 | 0.0435 |
| ipca_style_f1 | composite_calm_trend_participation | 0.0426 | 0.0426 |
| ipca_style_f1 | taa_10m_sma | 0.0382 | 0.0382 |
| ipca_style_f1 | composite_calm_trend_specialist | 0.0377 | 0.0377 |
| ipca_style_f1 | baseline_60_40_proxy | 0.0357 | 0.0357 |

## Final Recommendation
**PROCEED_TO_QQQ_DEEP_FEATURE_INTERACTION_MINING**

Reason: Latent factors are mostly redundant/proxy-like, but the walk-forward characteristic model has positive cross-sectional IC/spread evidence.

## Exact Prompt Outline for Next Phase
Implement Phase QQQ -- Deep Feature Interaction Mining. Use the PPP lagged ETF characteristic panel plus OOO feature lineage to mine economically constrained feature interactions with expanding-window validation only. Compare interaction signals to PPP latent factors, OOO signals, GGG1 sleeves, and state labels. Do not change production/shadow pins, do not create portfolio candidates unless the phase explicitly passes diagnostic gates, and require clear leakage checks, subperiod stability, redundancy controls, and a next-action recommendation.

## Resume-Worthy Technical Summary
PPP built a GGG1-aligned weekly ETF return panel and a lagged ETF characteristic
panel combining rolling momentum/volatility/drawdown/trend/relative-strength
features, existing Layer 1 tradable signals, OOO signal context, regime labels,
Layer 2A sleeve returns, GGG1 component returns, and GGG1 exposure context. It
ran full-sample diagnostic PCA and expanding-window causal PCA, then ran an
internal IPCA-style approximation through characteristic-managed returns,
expanding reduced-rank factors, factor loading scores, walk-forward ridge
cross-sectional return prediction, feature stability, state behavior,
redundancy, turnover proxies, candidate latent sleeve diagnostics, and GGG1
latent exposure diagnostics. Production pin `improved_phase2b_regime_confidence_boost`, official shadow
pin `improved_phase2b_combo_abc`, and GGG1 logic were not changed.
