# Phase QQQ -- Deep Feature Interaction Mining

Date: 2026-04-27

## Commands Executed
- `sed -n '1,280p' docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md`
- `find data/research/phase_ppp_latent_factor_discovery -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf "%s\t" "$(basename "{}")"; wc -l < "{}"'`
- `python3 - <<'PY' ...PPP schema and target/input summaries...`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md`
- `sed -n '1,220p' docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md`
- `find data/research/phase_ooo_signal_discovery data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction -maxdepth 2 -type f | sort | sed -n '1,280p'`
- `ls -lh data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2b_combo_abc.csv`
- `python3 - <<'PY' ...available sklearn package check...`
- `tail -n 90 docs/research/project_journey.md`
- `python3 -m py_compile scripts/phase_qqq_deep_feature_interaction_mining.py`
- `python3 scripts/phase_qqq_deep_feature_interaction_mining.py`
- `find data/research/phase_qqq_deep_feature_interaction_mining -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf "%s\t" "$(basename "{}")"; wc -l < "{}"'`
- `ls -lh data/research/phase_qqq_deep_feature_interaction_mining | sed -n '1,120p'`
- `rg -n "qqq_ml_dataset|phase_qqq|model_predictions" .gitignore || true`
- `python3 - <<'PY' ...QQQ output metric and shortlist summaries...`
- `git status --short`

## Files Created / Modified
- `scripts/phase_qqq_deep_feature_interaction_mining.py`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset_sample.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_dataset_schema.json`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_feature_manifest.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_target_summary.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_data_quality_report.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_leakage_checklist.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_walkforward_splits.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_baseline_model_metrics.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_metrics.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_predictions.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_calibration_summary.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_feature_importance.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_feature_family_importance.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_interaction_importance.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_state_specific_model_performance.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_subperiod_stability.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_extracted_interaction_rules.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_rule_performance_summary.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_state_specific_rules.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_rule_stability.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_redundancy_summary.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_incrementality_summary.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_rule_event_overlap.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_candidate_interaction_signal_shortlist.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_rejected_interaction_log.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_next_phase_queue.csv`
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_next_action_recommendation.csv`
- `docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md`
- `docs/research/project_journey.md`
- `.gitignore` (added the bulky QQQ row-level dataset/prediction artifacts)

`qqq_ml_dataset.csv` is about 75 MB and `qqq_model_predictions.csv` is about
125 MB, so both remain saved locally but are ignored for GitHub hygiene. The
sample, schema, manifests, metrics, rule summaries, shortlist, and report remain
available as compact review artifacts.

## Dataset Construction Summary
| item | value |
| --- | --- |
| rows | 38850 |
| columns | 151 |
| tickers | 35 |
| start_date | 2005-01-07 |
| end_date | 2026-04-10 |

The QQQ dataset uses PPP lagged ETF features as the main source, adds lagged
known proxy returns and lagged PPP factor returns, creates lagged state dummies,
and builds explicit economically constrained interactions. Current
`market_state` is retained for validation grouping only.

## Leakage Checks
| check | passed | note |
| --- | --- | --- |
| all_ppp_source_features_lagged | 1.0000 | PPP manifest states rolling/Layer1/OOO features are lagged. |
| qqq_generated_proxy_features_lagged | 1.0000 | Known proxy and PPP factor context shifted one week. |
| target_columns_excluded_from_feature_list | 1.0000 | Feature manifest excludes target/fwd_return columns. |
| current_market_state_not_live_feature | 1.0000 | Current market_state retained only for validation grouping; live state dummies use lag1. |
| no_forward_returns_as_features | 1.0000 | Forward returns are target/outcome columns only. |
| no_random_splits | 1.0000 | Walk-forward expanding dates only. |
| no_centered_windows | 1.0000 | QQQ uses PPP trailing features and same-date cross-sectional z-scores. |
| no_production_or_shadow_change | 1.0000 | production=improved_phase2b_regime_confidence_boost; shadow=improved_phase2b_combo_abc; GGG1=improved_phaseggg_confirmed_only_robust_offense. |
| dataset_has_targets | 1.0000 | All four requested ETF targets exist. |

## Target Definitions and Class Balance
| target | entity_type | n_observations | positive_rate | start_date | end_date | enough_samples | definition | horizon_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_etf_forward_top_quantile_4w | ETF | 37345.0000 | 0.2603 | 2005-01-07 | 2026-03-13 | 1.0000 | forward_top_quantile | 4.0000 |
| target_etf_forward_top_quantile_4w__state_calm_trend | ETF_STATE_SUBSET | 10060.0000 | 0.2604 | 2005-08-19 | 2025-08-29 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_top_quantile_4w__state_neutral_mixed | ETF_STATE_SUBSET | 16264.0000 | 0.2607 | 2005-01-07 | 2026-03-06 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_top_quantile_4w__state_recovery_confirmed | ETF_STATE_SUBSET | 1479.0000 | 0.2576 | 2006-11-10 | 2025-11-14 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_top_quantile_4w__state_recovery_fragile | ETF_STATE_SUBSET | 1678.0000 | 0.2592 | 2006-08-18 | 2025-06-27 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_top_quantile_4w__state_stressed_panic | ETF_STATE_SUBSET | 7864.0000 | 0.2602 | 2006-05-26 | 2026-03-13 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_top_quantile_8w | ETF | 37205.0000 | 0.2603 | 2005-01-07 | 2026-02-13 | 1.0000 | forward_top_quantile | 8.0000 |
| target_etf_forward_top_quantile_8w__state_calm_trend | ETF_STATE_SUBSET | 10060.0000 | 0.2604 | 2005-08-19 | 2025-08-29 | 1.0000 | state-specific diagnostic target balance only | 8.0000 |
| target_etf_forward_top_quantile_8w__state_neutral_mixed | ETF_STATE_SUBSET | 16159.0000 | 0.2607 | 2005-01-07 | 2026-02-13 | 1.0000 | state-specific diagnostic target balance only | 8.0000 |
| target_etf_forward_top_quantile_8w__state_recovery_confirmed | ETF_STATE_SUBSET | 1479.0000 | 0.2576 | 2006-11-10 | 2025-11-14 | 1.0000 | state-specific diagnostic target balance only | 8.0000 |
| target_etf_forward_top_quantile_8w__state_recovery_fragile | ETF_STATE_SUBSET | 1678.0000 | 0.2592 | 2006-08-18 | 2025-06-27 | 1.0000 | state-specific diagnostic target balance only | 8.0000 |
| target_etf_forward_top_quantile_8w__state_stressed_panic | ETF_STATE_SUBSET | 7829.0000 | 0.2602 | 2006-05-26 | 2025-05-30 | 1.0000 | state-specific diagnostic target balance only | 8.0000 |
| target_etf_forward_risk_adjusted_top_quantile_4w | ETF | 37100.0000 | 0.2604 | 2005-02-25 | 2026-03-13 | 1.0000 | risk_adjusted_top_quantile | 4.0000 |
| target_etf_forward_risk_adjusted_top_quantile_4w__state_calm_trend | ETF_STATE_SUBSET | 10052.0000 | 0.2599 | 2005-08-19 | 2025-08-29 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_risk_adjusted_top_quantile_4w__state_neutral_mixed | ETF_STATE_SUBSET | 16039.0000 | 0.2609 | 2005-02-25 | 2026-03-06 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |
| target_etf_forward_risk_adjusted_top_quantile_4w__state_recovery_confirmed | ETF_STATE_SUBSET | 1479.0000 | 0.2576 | 2006-11-10 | 2025-11-14 | 1.0000 | state-specific diagnostic target balance only | 4.0000 |

## Walk-Forward Validation Design
Initial train dates: `260`. Refit frequency: `26` weekly dates.
Splits generated: `33`.

| split_id | train_start_date | train_end_date | test_start_date | test_end_date | n_train_dates | n_test_dates |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0000 | 2005-01-07 | 2009-12-25 | 2010-01-01 | 2010-06-25 | 260.0000 | 26.0000 |
| 1.0000 | 2005-01-07 | 2010-06-25 | 2010-07-02 | 2010-12-24 | 286.0000 | 26.0000 |
| 2.0000 | 2005-01-07 | 2010-12-24 | 2010-12-31 | 2011-06-24 | 312.0000 | 26.0000 |
| 3.0000 | 2005-01-07 | 2011-06-24 | 2011-07-01 | 2011-12-23 | 338.0000 | 26.0000 |
| 4.0000 | 2005-01-07 | 2011-12-23 | 2011-12-30 | 2012-06-22 | 364.0000 | 26.0000 |
| 5.0000 | 2005-01-07 | 2012-06-22 | 2012-06-29 | 2012-12-21 | 390.0000 | 26.0000 |
| 6.0000 | 2005-01-07 | 2012-12-21 | 2012-12-28 | 2013-06-21 | 416.0000 | 26.0000 |
| 7.0000 | 2005-01-07 | 2013-06-21 | 2013-06-28 | 2013-12-20 | 442.0000 | 26.0000 |

## Baseline Model Results
| target | model | n_oos | positive_rate | brier | auc | log_loss | pearson_ic | spearman_ic | positive_spearman_ic_rate | top_minus_bottom_forward_return_spread | top_decile_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_etf_forward_risk_adjusted_top_quantile_4w | simple_momentum_rank | 29350.0000 | 0.2594 | 0.3338 | 0.5171 | 1.2014 | 0.0070 | 0.0167 | 0.5366 | -0.0001 | 0.2695 |
| target_etf_forward_risk_adjusted_top_quantile_4w | naive_historical_class_rate | 29350.0000 | 0.2594 | 0.1921 | 0.5037 | 0.5725 | -0.0000 |  | 0.0000 | -0.0004 | 0.2308 |
| target_etf_forward_risk_adjusted_top_quantile_4w | state_only_lag1_rate | 29350.0000 | 0.2594 | 0.1921 | 0.5032 | 0.5725 | -0.0000 |  | 0.0000 | -0.0004 | 0.2308 |
| target_etf_forward_risk_adjusted_top_quantile_8w | simple_momentum_rank | 29210.0000 | 0.2594 | 0.3367 | 0.5092 | 1.2184 | -0.0148 | -0.0093 | 0.5071 | -0.0009 | 0.2530 |
| target_etf_forward_risk_adjusted_top_quantile_8w | naive_historical_class_rate | 29210.0000 | 0.2594 | 0.1921 | 0.5037 | 0.5725 | 0.0000 |  | 0.0000 | -0.0008 | 0.2372 |
| target_etf_forward_risk_adjusted_top_quantile_8w | state_only_lag1_rate | 29210.0000 | 0.2594 | 0.1921 | 0.5032 | 0.5725 | 0.0000 |  | 0.0000 | -0.0008 | 0.2372 |
| target_etf_forward_top_quantile_4w | simple_momentum_rank | 29357.0000 | 0.2594 | 0.3376 | 0.5073 | 1.1944 | 0.0071 | 0.0168 | 0.5366 | -0.0001 | 0.3056 |
| target_etf_forward_top_quantile_4w | naive_historical_class_rate | 29357.0000 | 0.2594 | 0.1921 | 0.5038 | 0.5724 | 0.0000 |  | 0.0000 | 0.0001 | 0.2166 |
| target_etf_forward_top_quantile_4w | state_only_lag1_rate | 29357.0000 | 0.2594 | 0.1921 | 0.5034 | 0.5724 | -0.0000 |  | 0.0000 | 0.0001 | 0.2166 |
| target_etf_forward_top_quantile_8w | simple_momentum_rank | 29217.0000 | 0.2594 | 0.3405 | 0.4995 | 1.2150 | -0.0146 | -0.0091 | 0.5071 | -0.0009 | 0.2865 |
| target_etf_forward_top_quantile_8w | naive_historical_class_rate | 29217.0000 | 0.2594 | 0.1921 | 0.5038 | 0.5724 | 0.0000 |  | 0.0000 | -0.0001 | 0.2004 |
| target_etf_forward_top_quantile_8w | state_only_lag1_rate | 29217.0000 | 0.2594 | 0.1921 | 0.5034 | 0.5724 | -0.0000 |  | 0.0000 | -0.0001 | 0.2004 |

## Nonlinear Model Results
| target | model | n_oos | positive_rate | brier | auc | log_loss | pearson_ic | spearman_ic | positive_spearman_ic_rate | top_minus_bottom_forward_return_spread | top_decile_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target_etf_forward_risk_adjusted_top_quantile_4w | simple_momentum_rank | 29350.0000 | 0.2594 | 0.3338 | 0.5171 | 1.2014 | 0.0070 | 0.0167 | 0.5366 | -0.0001 | 0.2695 |
| target_etf_forward_risk_adjusted_top_quantile_4w | hist_gradient_depth3 | 29350.0000 | 0.2594 | 0.1918 | 0.5636 | 0.5716 | -0.0316 | -0.0338 | 0.4598 | -0.0007 | 0.3221 |
| target_etf_forward_risk_adjusted_top_quantile_4w | logistic_l2_interactions | 29350.0000 | 0.2594 | 0.1922 | 0.5596 | 0.5724 | -0.0448 | -0.0434 | 0.4551 | -0.0046 | 0.3053 |
| target_etf_forward_risk_adjusted_top_quantile_4w | random_forest_depth4 | 29350.0000 | 0.2594 | 0.1903 | 0.5648 | 0.5677 | -0.0485 | -0.0466 | 0.4385 | -0.0041 | 0.3224 |
| target_etf_forward_risk_adjusted_top_quantile_8w | simple_momentum_rank | 29210.0000 | 0.2594 | 0.3367 | 0.5092 | 1.2184 | -0.0148 | -0.0093 | 0.5071 | -0.0009 | 0.2530 |
| target_etf_forward_risk_adjusted_top_quantile_8w | hist_gradient_depth3 | 29210.0000 | 0.2594 | 0.1911 | 0.5742 | 0.5705 | -0.0347 | -0.0267 | 0.4727 | -0.0010 | 0.3429 |
| target_etf_forward_risk_adjusted_top_quantile_8w | logistic_l2_interactions | 29210.0000 | 0.2594 | 0.1923 | 0.5645 | 0.5744 | -0.0560 | -0.0532 | 0.4287 | -0.0084 | 0.3328 |
| target_etf_forward_risk_adjusted_top_quantile_8w | random_forest_depth4 | 29210.0000 | 0.2594 | 0.1895 | 0.5708 | 0.5660 | -0.0697 | -0.0663 | 0.4264 | -0.0087 | 0.3616 |
| target_etf_forward_top_quantile_4w | logistic_l2_base | 29357.0000 | 0.2594 | 0.1899 | 0.5853 | 0.5659 | 0.0167 | 0.0417 | 0.5863 | 0.0011 | 0.3454 |
| target_etf_forward_top_quantile_4w | logistic_l2_interactions | 29357.0000 | 0.2594 | 0.1907 | 0.5799 | 0.5683 | 0.0252 | 0.0375 | 0.5816 | 0.0002 | 0.3310 |
| target_etf_forward_top_quantile_4w | random_forest_depth4 | 29357.0000 | 0.2594 | 0.1884 | 0.5923 | 0.5626 | 0.0235 | 0.0359 | 0.5591 | 0.0003 | 0.3454 |
| target_etf_forward_top_quantile_4w | decision_tree_depth3 | 29357.0000 | 0.2594 | 0.1930 | 0.5608 | 0.5742 | 0.0124 | 0.0258 | 0.5449 | 0.0010 | 0.3319 |
| target_etf_forward_top_quantile_8w | logistic_l2_interactions | 29217.0000 | 0.2594 | 0.1910 | 0.5851 | 0.5691 | 0.0524 | 0.0652 | 0.6045 | 0.0054 | 0.3210 |
| target_etf_forward_top_quantile_8w | hist_gradient_depth3 | 29217.0000 | 0.2594 | 0.1912 | 0.5818 | 0.5698 | 0.0504 | 0.0556 | 0.5998 | 0.0065 | 0.3337 |
| target_etf_forward_top_quantile_8w | random_forest_depth4 | 29217.0000 | 0.2594 | 0.1878 | 0.5966 | 0.5605 | 0.0505 | 0.0552 | 0.5855 | 0.0057 | 0.3498 |
| target_etf_forward_top_quantile_8w | logistic_l2_base | 29217.0000 | 0.2594 | 0.1903 | 0.5870 | 0.5664 | 0.0285 | 0.0544 | 0.5867 | 0.0035 | 0.3144 |

## Feature Family Importance
| feature_family | mean_abs_importance | feature_count |
| --- | --- | --- |
| volatility_quality | 0.1387 | 149.0000 |
| drawdown_stress | 0.0882 | 39.0000 |
| style_layer1 | 0.0841 | 122.0000 |
| explicit_interaction | 0.0635 | 188.0000 |
| momentum | 0.0467 | 145.0000 |
| trend_breadth | 0.0308 | 347.0000 |
| relative_strength_leadlag | 0.0299 | 332.0000 |
| regime_state_context | 0.0096 | 5.0000 |

## Interaction and Rule Findings
Top explicit interaction importances:

| target | feature | mean_importance | mean_abs_importance | sign_stability | n_models | n_refits | interaction_source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_carry_x_lowvol | 0.0912 | 0.0912 | 1.0000 | 3.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_market_trend_x_mom13 | 0.0860 | 0.0860 | 1.0000 | 2.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_mom13_x_lowvol13 | 0.0618 | 0.0618 | 1.0000 | 3.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_momentum_x_recovery_confirmed | 0.0611 | 0.0611 | 1.0000 | 1.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_quality_x_highvol | 0.0572 | 0.0582 | 0.9846 | 3.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_mom26_x_ma_distance26 | 0.0516 | 0.0516 | 1.0000 | 3.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_real_asset_strength_x_stress | 0.0509 | 0.0509 | 1.0000 | 2.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_breadth_x_mom13 | -0.0323 | 0.0442 | 0.6316 | 2.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_bab_x_highvol | -0.0294 | 0.0372 | 0.5156 | 2.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_calm_neutral_trend_x_relspy | -0.0040 | 0.0333 | 0.7451 | 2.0000 | 32.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_trend_consistency_x_lowdownsidevol | 0.0280 | 0.0280 | 1.0000 | 2.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_momentum_x_recovery_fragile | 0.0263 | 0.0263 | 1.0000 | 1.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_international_strength_x_calm | -0.0201 | 0.0255 | 0.7200 | 1.0000 | 25.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_ppp_duration_factor_x_quality | 0.0039 | 0.0248 | 0.6296 | 2.0000 | 25.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_breadth_recovery_x_mom13 | 0.0037 | 0.0246 | 0.5833 | 1.0000 | 24.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_mom13_x_drawdown_repair | 0.0021 | 0.0230 | 0.7273 | 2.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_credit_strength_x_trend | -0.0003 | 0.0196 | 0.5758 | 3.0000 | 33.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_ppp_equity_factor_x_lowvol_mom | 0.0193 | 0.0193 | 1.0000 | 2.0000 | 29.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_reversal_x_drawdown | -0.0092 | 0.0168 | 0.5714 | 3.0000 | 30.0000 | explicit_interaction_feature |
| target_etf_forward_risk_adjusted_top_quantile_4w | int_mom26_x_lowvol26 | -0.0042 | 0.0166 | 0.6071 | 2.0000 | 33.0000 | explicit_interaction_feature |

Extracted rule examples:

| rule_name | interaction_feature | features_used | rule_formula | economic_interpretation | target | model_source | oos_metric_lift | event_frequency | stability | redundancy_warning | next_recommended_phase | mean_abs_model_importance | subperiods_with_events | positive_return_lift_share | positive_precision_lift_share | min_subperiod_events |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rule_int_momentum_x_recovery_confirmed__forward_top_quantile_8w | int_momentum_x_recovery_confirmed | z_l1_multi_horizon_mom_multi_mom_equal_score_tradable\|state_lag1_recovery_confirmed | lagged recovery_confirmed and Layer 1 multi-horizon momentum score > 0.5 | Layer 1 momentum active during confirmed recovery | target_etf_forward_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0237 | 0.0164 | 0.8333 |  |  | 0.0433 | 3.0000 | 0.6667 | 1.0000 | 72.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_risk_adjusted_top_quantile_8w | int_momentum_x_recovery_confirmed | z_l1_multi_horizon_mom_multi_mom_equal_score_tradable\|state_lag1_recovery_confirmed | lagged recovery_confirmed and Layer 1 multi-horizon momentum score > 0.5 | Layer 1 momentum active during confirmed recovery | target_etf_forward_risk_adjusted_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0236 | 0.0164 | 0.6667 |  |  | 0.0426 | 3.0000 | 0.6667 | 0.6667 | 72.0000 |
| rule_int_breadth_recovery_x_mom13__forward_top_quantile_8w | int_breadth_recovery_x_mom13 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal\|z_mom_13w | OOO breadth recovery signal active and z_mom_13w > 0.5 | recovery-confirmed breadth with ETF momentum | target_etf_forward_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0204 | 0.0133 | 0.8333 |  |  | 0.0332 | 3.0000 | 0.6667 | 1.0000 | 71.0000 |
| rule_int_breadth_recovery_x_mom13__forward_risk_adjusted_top_quantile_8w | int_breadth_recovery_x_mom13 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal\|z_mom_13w | OOO breadth recovery signal active and z_mom_13w > 0.5 | recovery-confirmed breadth with ETF momentum | target_etf_forward_risk_adjusted_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0204 | 0.0133 | 0.5000 |  |  | 0.0301 | 3.0000 | 0.6667 | 0.3333 | 71.0000 |
| rule_int_quality_x_highvol__forward_top_quantile_8w | int_quality_x_highvol | z_l1_quality_quality_score_tradable\|z_vol_13w | Layer 1 quality score > 0.5 and z_vol_13w > 0.5 | quality selection when realized volatility is elevated | target_etf_forward_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0149 | 0.0024 | 0.8333 |  |  | 0.0870 | 2.0000 | 0.6667 | 1.0000 | 14.0000 |
| rule_int_quality_x_highvol__forward_risk_adjusted_top_quantile_8w | int_quality_x_highvol | z_l1_quality_quality_score_tradable\|z_vol_13w | Layer 1 quality score > 0.5 and z_vol_13w > 0.5 | quality selection when realized volatility is elevated | target_etf_forward_risk_adjusted_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0149 | 0.0024 | 0.6667 |  |  | 0.0594 | 2.0000 | 0.6667 | 0.6667 | 14.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_top_quantile_4w | int_momentum_x_recovery_confirmed | z_l1_multi_horizon_mom_multi_mom_equal_score_tradable\|state_lag1_recovery_confirmed | lagged recovery_confirmed and Layer 1 multi-horizon momentum score > 0.5 | Layer 1 momentum active during confirmed recovery | target_etf_forward_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0139 | 0.0164 | 1.0000 |  |  | 0.0552 | 3.0000 | 1.0000 | 1.0000 | 72.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_risk_adjusted_top_quantile_4w | int_momentum_x_recovery_confirmed | z_l1_multi_horizon_mom_multi_mom_equal_score_tradable\|state_lag1_recovery_confirmed | lagged recovery_confirmed and Layer 1 multi-horizon momentum score > 0.5 | Layer 1 momentum active during confirmed recovery | target_etf_forward_risk_adjusted_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0139 | 0.0164 | 1.0000 |  |  | 0.0611 | 3.0000 | 1.0000 | 1.0000 | 72.0000 |
| rule_int_breadth_recovery_x_mom13__forward_top_quantile_4w | int_breadth_recovery_x_mom13 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal\|z_mom_13w | OOO breadth recovery signal active and z_mom_13w > 0.5 | recovery-confirmed breadth with ETF momentum | target_etf_forward_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0112 | 0.0132 | 1.0000 |  |  | 0.0289 | 3.0000 | 1.0000 | 1.0000 | 71.0000 |
| rule_int_breadth_recovery_x_mom13__forward_risk_adjusted_top_quantile_4w | int_breadth_recovery_x_mom13 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal\|z_mom_13w | OOO breadth recovery signal active and z_mom_13w > 0.5 | recovery-confirmed breadth with ETF momentum | target_etf_forward_risk_adjusted_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0112 | 0.0132 | 0.6667 |  |  | 0.0246 | 3.0000 | 1.0000 | 0.3333 | 71.0000 |
| rule_int_gld_spy_strength_x_stress__forward_top_quantile_8w | int_gld_spy_strength_x_stress | ooo2_leadlag_GLD_minus_SPY_13w_signal\|state_lag1_stressed_panic | GLD-SPY lead/lag strength > 0 and lagged stressed_panic | gold leadership during lagged stress | target_etf_forward_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0110 | 0.1289 | 0.3333 |  |  | 0.0082 | 3.0000 | 0.6667 | 0.0000 | 755.0000 |
| rule_int_gld_spy_strength_x_stress__forward_risk_adjusted_top_quantile_8w | int_gld_spy_strength_x_stress | ooo2_leadlag_GLD_minus_SPY_13w_signal\|state_lag1_stressed_panic | GLD-SPY lead/lag strength > 0 and lagged stressed_panic | gold leadership during lagged stress | target_etf_forward_risk_adjusted_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0109 | 0.1289 | 0.3333 |  |  | 0.0107 | 3.0000 | 0.6667 | 0.0000 | 755.0000 |
| rule_int_gld_spy_strength_x_stress__forward_top_quantile_4w | int_gld_spy_strength_x_stress | ooo2_leadlag_GLD_minus_SPY_13w_signal\|state_lag1_stressed_panic | GLD-SPY lead/lag strength > 0 and lagged stressed_panic | gold leadership during lagged stress | target_etf_forward_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0062 | 0.1282 | 0.1667 |  |  | 0.0076 | 3.0000 | 0.3333 | 0.0000 | 755.0000 |
| rule_int_gld_spy_strength_x_stress__forward_risk_adjusted_top_quantile_4w | int_gld_spy_strength_x_stress | ooo2_leadlag_GLD_minus_SPY_13w_signal\|state_lag1_stressed_panic | GLD-SPY lead/lag strength > 0 and lagged stressed_panic | gold leadership during lagged stress | target_etf_forward_risk_adjusted_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0062 | 0.1283 | 0.1667 |  |  | 0.0137 | 3.0000 | 0.3333 | 0.0000 | 755.0000 |
| rule_int_quality_x_highvol__forward_top_quantile_4w | int_quality_x_highvol | z_l1_quality_quality_score_tradable\|z_vol_13w | Layer 1 quality score > 0.5 and z_vol_13w > 0.5 | quality selection when realized volatility is elevated | target_etf_forward_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0048 | 0.0024 | 0.8333 |  |  | 0.0607 | 2.0000 | 0.6667 | 1.0000 | 14.0000 |
| rule_int_quality_x_highvol__forward_risk_adjusted_top_quantile_4w | int_quality_x_highvol | z_l1_quality_quality_score_tradable\|z_vol_13w | Layer 1 quality score > 0.5 and z_vol_13w > 0.5 | quality selection when realized volatility is elevated | target_etf_forward_risk_adjusted_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0048 | 0.0024 | 0.6667 |  |  | 0.0582 | 2.0000 | 0.6667 | 0.6667 | 14.0000 |

## State-Specific Interactions
| rule_name | target | market_state | n_state_obs | n_events | event_frequency | precision | baseline_precision | precision_lift | avg_forward_return | baseline_avg_forward_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rule_int_quality_x_highvol__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | recovery_confirmed | 1395.0000 | 7.0000 | 0.0050 | 1.0000 | 0.2581 | 0.7419 | 0.0854 | 0.0192 |
| rule_int_quality_x_highvol__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | recovery_fragile | 1220.0000 | 3.0000 | 0.0025 | 1.0000 | 0.2582 | 0.7418 | 0.0375 | 0.0045 |
| rule_int_quality_x_highvol__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | calm_trend | 8906.0000 | 20.0000 | 0.0022 | 0.7000 | 0.2597 | 0.4403 | 0.0274 | 0.0014 |
| rule_int_breadth_recovery_x_mom13__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | recovery_fragile | 1220.0000 | 12.0000 | 0.0098 | 0.6667 | 0.2582 | 0.4085 | 0.0300 | 0.0045 |
| rule_int_quality_x_highvol__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | recovery_fragile | 1217.0000 | 3.0000 | 0.0025 | 0.6667 | 0.2588 | 0.4078 | 0.0375 | 0.0047 |
| rule_int_mom13_x_lowvol13__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | recovery_confirmed | 1395.0000 | 24.0000 | 0.0172 | 0.6250 | 0.2581 | 0.3669 | 0.0383 | 0.0192 |
| rule_int_international_strength_x_calm__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | recovery_confirmed | 1395.0000 | 10.0000 | 0.0072 | 0.6000 | 0.2581 | 0.3419 | 0.0739 | 0.0192 |
| rule_int_international_strength_x_calm__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | recovery_confirmed | 1395.0000 | 10.0000 | 0.0072 | 0.6000 | 0.2581 | 0.3419 | 0.0552 | 0.0057 |
| rule_int_international_strength_x_calm__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | recovery_confirmed | 1395.0000 | 10.0000 | 0.0072 | 0.6000 | 0.2581 | 0.3419 | 0.0739 | 0.0192 |
| rule_int_breadth_recovery_x_mom13__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | recovery_fragile | 1220.0000 | 12.0000 | 0.0098 | 0.5833 | 0.2582 | 0.3251 | 0.0079 | -0.0002 |
| rule_int_breadth_recovery_x_mom13__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | recovery_fragile | 1217.0000 | 12.0000 | 0.0099 | 0.5833 | 0.2588 | 0.3245 | 0.0300 | 0.0047 |
| rule_int_mom13_x_drawdown_repair__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | recovery_confirmed | 1395.0000 | 40.0000 | 0.0287 | 0.5750 | 0.2581 | 0.3169 | 0.0337 | 0.0192 |
| rule_int_quality_x_highvol__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | calm_trend | 8906.0000 | 20.0000 | 0.0022 | 0.5500 | 0.2597 | 0.2903 | 0.0274 | 0.0014 |
| rule_int_mom26_x_lowvol26__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | recovery_fragile | 1217.0000 | 44.0000 | 0.0362 | 0.5227 | 0.2588 | 0.2639 | 0.0085 | 0.0002 |
| rule_int_mom13_x_lowvol13__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | recovery_confirmed | 1395.0000 | 24.0000 | 0.0172 | 0.5000 | 0.2581 | 0.2419 | 0.0383 | 0.0192 |
| rule_int_international_strength_x_calm__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | recovery_confirmed | 1395.0000 | 10.0000 | 0.0072 | 0.5000 | 0.2581 | 0.2419 | 0.0552 | 0.0057 |

## Redundancy and Incrementality
| rule_name | target | incrementality_flag | max_abs_correlation | max_corr_comparison | max_corr_comparison_type | max_event_overlap | max_overlap_comparison | event_frequency | n_events | return_lift | precision_lift | positive_subperiod_return_lift_share | tradeable_actionable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rule_int_efa_spy_strength_x_market_trend__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2469 | 7213.0000 | 0.0016 | 0.0002 | 0.6667 | 1.0000 |
| rule_int_efa_spy_strength_x_market_trend__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2469 | 7213.0000 | 0.0016 | 0.0001 | 0.6667 | 1.0000 |
| rule_int_efa_spy_strength_x_market_trend__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2505 | 7353.0000 | 0.0012 | 0.0001 | 0.6667 | 1.0000 |
| rule_int_efa_spy_strength_x_market_trend__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2505 | 7353.0000 | 0.0012 | 0.0001 | 0.6667 | 1.0000 |
| rule_int_market_trend_x_mom13__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2429 | 7132.0000 | 0.0003 | 0.0354 | 0.6667 | 1.0000 |
| rule_int_market_trend_x_mom13__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2430 | 7132.0000 | 0.0003 | 0.0154 | 0.6667 | 1.0000 |
| rule_int_market_trend_x_mom13__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2429 | 7097.0000 | 0.0002 | 0.0355 | 0.6667 | 1.0000 |
| rule_int_market_trend_x_mom13__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2430 | 7097.0000 | 0.0001 | 0.0041 | 0.6667 | 1.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | INSUFFICIENT_EVIDENCE | 0.5763 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | regime_state_context | 0.3429 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0164 | 480.0000 | 0.0237 | 0.0740 | 0.6667 | 1.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | INSUFFICIENT_EVIDENCE | 0.5763 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | regime_state_context | 0.3429 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0164 | 480.0000 | 0.0236 | -0.0011 | 0.6667 | 1.0000 |
| rule_int_breadth_recovery_x_mom13__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | INSUFFICIENT_EVIDENCE | 0.5126 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal | trend_breadth | 0.1491 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0133 | 388.0000 | 0.0204 | 0.0680 | 0.6667 | 1.0000 |
| rule_int_breadth_recovery_x_mom13__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | INSUFFICIENT_EVIDENCE | 0.5126 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal | trend_breadth | 0.1491 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0133 | 388.0000 | 0.0204 | -0.0301 | 0.6667 | 1.0000 |
| rule_int_quality_x_highvol__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | INSUFFICIENT_EVIDENCE | 0.0621 | z_l1_xsmom_xsmom_score_tradable | momentum | 0.0062 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0024 | 70.0000 | 0.0149 | 0.2263 | 0.6667 | 1.0000 |
| rule_int_quality_x_highvol__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | INSUFFICIENT_EVIDENCE | 0.0621 | z_l1_xsmom_xsmom_score_tradable | momentum | 0.0062 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0024 | 70.0000 | 0.0149 | 0.1406 | 0.6667 | 1.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | INSUFFICIENT_EVIDENCE | 0.5763 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | regime_state_context | 0.3429 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0164 | 480.0000 | 0.0139 | 0.1115 | 1.0000 | 1.0000 |
| rule_int_momentum_x_recovery_confirmed__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | INSUFFICIENT_EVIDENCE | 0.5763 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | regime_state_context | 0.3429 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0164 | 480.0000 | 0.0139 | 0.0614 | 1.0000 | 1.0000 |
| rule_int_breadth_recovery_x_mom13__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | INSUFFICIENT_EVIDENCE | 0.5126 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal | trend_breadth | 0.1491 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0132 | 388.0000 | 0.0112 | 0.0705 | 1.0000 | 1.0000 |
| rule_int_breadth_recovery_x_mom13__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | INSUFFICIENT_EVIDENCE | 0.5126 | ooo2_breadth_ret13_positive_x_recovery_confirmed_signal | trend_breadth | 0.1491 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0132 | 388.0000 | 0.0112 | 0.0086 | 1.0000 | 1.0000 |
| rule_int_quality_x_highvol__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | INSUFFICIENT_EVIDENCE | 0.0621 | z_l1_xsmom_xsmom_score_tradable | momentum | 0.0062 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0024 | 70.0000 | 0.0048 | 0.1692 | 0.6667 | 1.0000 |
| rule_int_quality_x_highvol__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | INSUFFICIENT_EVIDENCE | 0.0621 | z_l1_xsmom_xsmom_score_tradable | momentum | 0.0062 | ooo3event_breadth_ret13_positive_x_recovery_confirmed_state_filtered_event | 0.0024 | 70.0000 | 0.0048 | 0.0549 | 0.6667 | 1.0000 |

## Candidate Interaction Signal Shortlist
| rule_name | interaction_feature | features_used | rule_formula | economic_interpretation | target | model_source | oos_metric_lift | event_frequency | stability | redundancy_warning | next_recommended_phase | mean_abs_model_importance | subperiods_with_events | positive_return_lift_share | positive_precision_lift_share | min_subperiod_events | n_events | event_frequency_perf | precision | baseline_precision | precision_lift | avg_forward_return | baseline_avg_forward_return | return_lift | incrementality_flag | max_abs_correlation | max_corr_comparison | max_corr_comparison_type | max_event_overlap | max_overlap_comparison | event_frequency_inc | n_events_inc | return_lift_inc | precision_lift_inc | positive_subperiod_return_lift_share | tradeable_actionable | best_state | best_state_precision_lift | best_state_event_frequency | classification | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rule_int_efa_spy_strength_x_market_trend__forward_top_quantile_8w | int_efa_spy_strength_x_market_trend | ooo2_leadlag_EFA_minus_SPY_13w_signal\|ooo2_market_trend_positive_signal | EFA-SPY lead/lag strength > 0 and market trend positive | international leadership signal under positive market trend | target_etf_forward_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0016 | 0.2469 | 0.3333 |  | QQQ2 or OOO5-style triple-barrier validation | 0.0070 | 3.0000 | 0.6667 | 0.0000 | 1925.0000 | 7213.0000 | 0.2469 | 0.2595 | 0.2594 | 0.0002 | 0.0127 | 0.0111 | 0.0016 | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2469 | 7213.0000 | 0.0016 | 0.0002 | 0.6667 | 1.0000 | recovery_confirmed | 0.0016 | 0.1491 | NEEDS_TRIPLE_BARRIER_VALIDATION | positive event-return lift but stability/coverage gates are not high-priority clean |
| rule_int_efa_spy_strength_x_market_trend__forward_risk_adjusted_top_quantile_8w | int_efa_spy_strength_x_market_trend | ooo2_leadlag_EFA_minus_SPY_13w_signal\|ooo2_market_trend_positive_signal | EFA-SPY lead/lag strength > 0 and market trend positive | international leadership signal under positive market trend | target_etf_forward_risk_adjusted_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0016 | 0.2469 | 0.3333 |  | QQQ2 or OOO5-style triple-barrier validation | 0.0096 | 3.0000 | 0.6667 | 0.0000 | 1925.0000 | 7213.0000 | 0.2469 | 0.2595 | 0.2594 | 0.0001 | 0.0127 | 0.0112 | 0.0016 | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2469 | 7213.0000 | 0.0016 | 0.0001 | 0.6667 | 1.0000 | recovery_confirmed | 0.0016 | 0.1491 | NEEDS_TRIPLE_BARRIER_VALIDATION | positive event-return lift but stability/coverage gates are not high-priority clean |
| rule_int_efa_spy_strength_x_market_trend__forward_top_quantile_4w | int_efa_spy_strength_x_market_trend | ooo2_leadlag_EFA_minus_SPY_13w_signal\|ooo2_market_trend_positive_signal | EFA-SPY lead/lag strength > 0 and market trend positive | international leadership signal under positive market trend | target_etf_forward_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0012 | 0.2505 | 0.3333 |  | QQQ2 or OOO5-style triple-barrier validation | 0.0062 | 3.0000 | 0.6667 | 0.0000 | 2065.0000 | 7353.0000 | 0.2505 | 0.2595 | 0.2594 | 0.0001 | 0.0067 | 0.0055 | 0.0012 | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2505 | 7353.0000 | 0.0012 | 0.0001 | 0.6667 | 1.0000 | recovery_confirmed | 0.0016 | 0.1491 | NEEDS_TRIPLE_BARRIER_VALIDATION | positive event-return lift but stability/coverage gates are not high-priority clean |
| rule_int_efa_spy_strength_x_market_trend__forward_risk_adjusted_top_quantile_4w | int_efa_spy_strength_x_market_trend | ooo2_leadlag_EFA_minus_SPY_13w_signal\|ooo2_market_trend_positive_signal | EFA-SPY lead/lag strength > 0 and market trend positive | international leadership signal under positive market trend | target_etf_forward_risk_adjusted_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0012 | 0.2505 | 0.3333 |  | QQQ2 or OOO5-style triple-barrier validation | 0.0108 | 3.0000 | 0.6667 | 0.0000 | 2065.0000 | 7353.0000 | 0.2505 | 0.2595 | 0.2594 | 0.0001 | 0.0067 | 0.0055 | 0.0012 | INCREMENTAL_NEW_SIGNAL | 0.6911 | ooo3_leadlag_EFA_minus_SPY_13w_signal__direction_strength | relative_strength_leadlag | 0.4019 | ooo3event_efa_spy_market_trend_confirmed_top20_event | 0.2505 | 7353.0000 | 0.0012 | 0.0001 | 0.6667 | 1.0000 | recovery_confirmed | 0.0016 | 0.1491 | NEEDS_TRIPLE_BARRIER_VALIDATION | positive event-return lift but stability/coverage gates are not high-priority clean |
| rule_int_market_trend_x_mom13__forward_top_quantile_4w | int_market_trend_x_mom13 | ooo2_market_trend_positive_signal\|z_mom_13w | market trend positive and z_mom_13w > 0.5 | market trend gate confirms asset momentum | target_etf_forward_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0003 | 0.2429 | 0.8333 |  | QQQ2 state-specific interaction validation | 0.1180 | 3.0000 | 0.6667 | 1.0000 | 1970.0000 | 7132.0000 | 0.2429 | 0.2947 | 0.2594 | 0.0354 | 0.0058 | 0.0055 | 0.0003 | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2429 | 7132.0000 | 0.0003 | 0.0354 | 0.6667 | 1.0000 | recovery_confirmed | 0.0861 | 0.2875 | PROMISING_STATE_SPECIFIC_SIGNAL | interaction is strongest in a specific state and needs state-specific validation |
| rule_int_market_trend_x_mom13__forward_risk_adjusted_top_quantile_4w | int_market_trend_x_mom13 | ooo2_market_trend_positive_signal\|z_mom_13w | market trend positive and z_mom_13w > 0.5 | market trend gate confirms asset momentum | target_etf_forward_risk_adjusted_top_quantile_4w | explicit_interaction_feature plus nonlinear model importance | 0.0003 | 0.2430 | 0.8333 |  | QQQ2 state-specific interaction validation | 0.0860 | 3.0000 | 0.6667 | 1.0000 | 1970.0000 | 7132.0000 | 0.2430 | 0.2748 | 0.2594 | 0.0154 | 0.0058 | 0.0055 | 0.0003 | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2430 | 7132.0000 | 0.0003 | 0.0154 | 0.6667 | 1.0000 | recovery_fragile | 0.0501 | 0.2473 | PROMISING_STATE_SPECIFIC_SIGNAL | interaction is strongest in a specific state and needs state-specific validation |
| rule_int_market_trend_x_mom13__forward_top_quantile_8w | int_market_trend_x_mom13 | ooo2_market_trend_positive_signal\|z_mom_13w | market trend positive and z_mom_13w > 0.5 | market trend gate confirms asset momentum | target_etf_forward_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0002 | 0.2429 | 0.8333 |  | QQQ2 state-specific interaction validation | 0.1553 | 3.0000 | 0.6667 | 1.0000 | 1935.0000 | 7097.0000 | 0.2429 | 0.2949 | 0.2594 | 0.0355 | 0.0113 | 0.0111 | 0.0002 | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2429 | 7097.0000 | 0.0002 | 0.0355 | 0.6667 | 1.0000 | recovery_fragile | 0.0940 | 0.2467 | PROMISING_STATE_SPECIFIC_SIGNAL | interaction is strongest in a specific state and needs state-specific validation |
| rule_int_market_trend_x_mom13__forward_risk_adjusted_top_quantile_8w | int_market_trend_x_mom13 | ooo2_market_trend_positive_signal\|z_mom_13w | market trend positive and z_mom_13w > 0.5 | market trend gate confirms asset momentum | target_etf_forward_risk_adjusted_top_quantile_8w | explicit_interaction_feature plus nonlinear model importance | 0.0001 | 0.2430 | 0.6667 |  | QQQ2 or OOO5-style triple-barrier validation | 0.1598 | 3.0000 | 0.6667 | 0.6667 | 1935.0000 | 7097.0000 | 0.2430 | 0.2635 | 0.2594 | 0.0041 | 0.0113 | 0.0112 | 0.0001 | INCREMENTAL_NEW_SIGNAL | 0.3512 | z_l1_reversal_reversal_4w_score_tradable | style_layer1 | 0.2866 | ooo2_market_trend_positive_signal | 0.2430 | 7097.0000 | 0.0001 | 0.0041 | 0.6667 | 1.0000 | stressed_panic | 0.0327 | 0.1040 | NEEDS_TRIPLE_BARRIER_VALIDATION | positive event-return lift but stability/coverage gates are not high-priority clean |

## Rejected Interactions and Why
| rule_name | target | classification | reason | return_lift | precision_lift | event_frequency |
| --- | --- | --- | --- | --- | --- | --- |
| rule_int_mom13_x_lowvol13__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0014 | -0.0553 | 0.0556 |
| rule_int_mom13_x_lowvol13__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0048 | -0.0815 | 0.0558 |
| rule_int_mom13_x_lowvol13__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0015 | 0.0825 | 0.0556 |
| rule_int_mom13_x_lowvol13__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0049 | 0.0700 | 0.0558 |
| rule_int_mom26_x_lowvol26__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0007 | -0.0790 | 0.0474 |
| rule_int_mom26_x_lowvol26__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0021 | -0.0913 | 0.0476 |
| rule_int_mom26_x_lowvol26__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0007 | 0.0746 | 0.0474 |
| rule_int_mom26_x_lowvol26__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0022 | 0.0883 | 0.0477 |
| rule_int_mom13_x_drawdown_repair__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0033 | -0.0281 | 0.0943 |
| rule_int_mom13_x_drawdown_repair__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0056 | -0.0461 | 0.0947 |
| rule_int_mom13_x_drawdown_repair__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0033 | 0.0442 | 0.0943 |
| rule_int_mom13_x_drawdown_repair__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0057 | 0.0334 | 0.0947 |
| rule_int_mom26_x_ma_distance26__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0006 | 0.0231 | 0.2228 |
| rule_int_mom26_x_ma_distance26__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | REJECT | insufficient stable incremental evidence | 0.0001 | 0.0159 | 0.2232 |
| rule_int_mom26_x_ma_distance26__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0007 | 0.0175 | 0.2228 |
| rule_int_mom26_x_ma_distance26__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | REJECT | insufficient stable incremental evidence | 0.0001 | 0.0064 | 0.2232 |
| rule_int_trend_consistency_x_lowdownsidevol__forward_top_quantile_4w | target_etf_forward_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0024 | -0.0746 | 0.1200 |
| rule_int_trend_consistency_x_lowdownsidevol__forward_top_quantile_8w | target_etf_forward_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0057 | -0.0993 | 0.1202 |
| rule_int_trend_consistency_x_lowdownsidevol__forward_risk_adjusted_top_quantile_4w | target_etf_forward_risk_adjusted_top_quantile_4w | REJECT | insufficient stable incremental evidence | -0.0024 | 0.0630 | 0.1200 |
| rule_int_trend_consistency_x_lowdownsidevol__forward_risk_adjusted_top_quantile_8w | target_etf_forward_risk_adjusted_top_quantile_8w | REJECT | insufficient stable incremental evidence | -0.0058 | 0.0841 | 0.1202 |

## Final Recommendation
**PROCEED_TO_SSS_REGIME_SEQUENCE_MODELING**

Reason: Interaction value appears state-specific or state-engine-like rather than a clean broad ETF signal.

## Exact Prompt Outline for Next Phase
Implement Phase SSS regime-sequence modeling as a diagnostic-only research
phase. Use PPP latent-factor diagnostics, QQQ state-specific interaction
outputs, existing Layer 1/OOO signals, Layer 2B regime/state history, and GGG1
performance by state to test whether transition paths and state persistence
explain the weak but recurring QQQ interaction value. Build causal lagged
state-sequence features only, use expanding/walk-forward validation, compare
against state-only and existing regime-engine baselines, extract interpretable
transition rules, check redundancy versus current Layer 2B logic and GGG1
sleeves, and produce either a regime-sequence signal shortlist or a stop/return
decision. Do not change production/shadow/GGG1 logic, do not create portfolio
candidates, and do not use future states as live features.

## Resume-Worthy Technical Summary
QQQ built four ETF cross-sectional top-quartile targets from the PPP panel:
4w/8w forward return and 4w/8w risk-adjusted forward return. It used fixed
expanding-window splits with no random shuffling, evaluated naive/state/momentum
baselines, L2 logistic models, shallow decision trees, controlled random
forests, and shallow histogram gradient boosting. It generated economically
motivated explicit interactions such as momentum x volatility, credit strength
x trend, breadth x momentum, real-asset strength x stress, quality/BAB/carry x
volatility, OOO lead-lag x state/trend, and PPP factor context x ETF
characteristics. QQQ extracted rule events, checked subperiod and state
behavior, compared rules against existing Layer 1/OOO/PPP/state/proxy context,
and wrote a shortlist without creating portfolio candidates or changing any
production/shadow/GGG1 logic.
