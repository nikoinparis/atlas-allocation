# Statistical Validation Audit Report

Research-only audit across available strategy return files. This report does not promote any candidate.

## Scope

-   Return series scanned: `358`
-   Approximate trial count from metrics/results files: `3869` across `154` files.
-   Purged CV sanity check folds: `4.0`, max train/test overlap: `0.0`.

## Verdict Counts

| validation_verdict | count |
|--------------------|-------|
| overfit_risk       | 358   |

## Top Rows By Verdict Then Sharpe

| candidate | source_file | annual_return | sharpe | max_drawdown | cvar_5 | psr | dsr_proxy | multiple_testing_adjusted_support | pbo_proxy | validation_verdict |
|----|----|----|----|----|----|----|----|----|----|----|
| sequence_multiseed_backtest_returns | data/research/ml_lab/sequence_models/multiseed_walkforward/sequence_multiseed_backtest_returns.csv | 0.1706 | 1.3073 | -0.3325 | -0.0381 | 0.9996 | 1.0000 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaseq_abstention_aware_meta_allocator | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseq_abstention_aware_meta_allocator.csv | 0.0581 | 1.0376 | -0.0816 | -0.0179 | 0.6713 | 0.8294 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase3_high_breadth_calm_us_offense | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_high_breadth_calm_us_offense.csv | 0.0727 | 0.9664 | -0.1190 | -0.0248 | 0.5607 | 0.7461 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaseq_abstention_regime_regret_meta_allocator | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseq_abstention_regime_regret_meta_allocator.csv | 0.0675 | 0.9651 | -0.1269 | -0.0230 | 0.5577 | 0.7403 | 0.0000 | 0.6667 | overfit_risk |
| improved_phasebb_w1cap_060_hrp_7sleeve | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phasebb_w1cap_060_hrp_7sleeve.csv | 0.0376 | 0.9623 | -0.0692 | -0.0127 | 0.5494 | 0.7463 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase4b_refined_sector_20pct | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv | 0.0776 | 0.9590 | -0.1377 | -0.0267 | 0.5497 | 0.7377 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase6_neutral_classifier_unlock | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase6_neutral_classifier_unlock.csv | 0.0775 | 0.9584 | -0.1377 | -0.0267 | 0.5485 | 0.7366 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase6_recovery_quality_rerisk | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase6_recovery_quality_rerisk.csv | 0.0775 | 0.9567 | -0.1377 | -0.0267 | 0.5460 | 0.7352 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaset_soft_regime_posterior_allocator | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaset_soft_regime_posterior_allocator.csv | 0.0699 | 0.9563 | -0.1313 | -0.0239 | 0.5437 | 0.7264 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaset_soft_trust_weighted_allocator | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaset_soft_trust_weighted_allocator.csv | 0.0702 | 0.9554 | -0.1331 | -0.0241 | 0.5424 | 0.7252 | 0.0000 | 0.6667 | overfit_risk |
| improved_phasebb_w1cap_055_hrp_7sleeve | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phasebb_w1cap_055_hrp_7sleeve.csv | 0.0391 | 0.9550 | -0.0746 | -0.0134 | 0.5371 | 0.7338 | 0.0000 | 0.6667 | overfit_risk |
| improved_phasebb_w1cap_055_others_050_hrp_7sleeve | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phasebb_w1cap_055_others_050_hrp_7sleeve.csv | 0.0391 | 0.9550 | -0.0746 | -0.0134 | 0.5371 | 0.7338 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaseq_regime_bucket_meta_allocator | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseq_regime_bucket_meta_allocator.csv | 0.0682 | 0.9546 | -0.1306 | -0.0235 | 0.5408 | 0.7261 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaset_production_anchored_soft_combo | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaset_production_anchored_soft_combo.csv | 0.0703 | 0.9546 | -0.1340 | -0.0243 | 0.5411 | 0.7241 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase7_expression_boost | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase7_expression_boost.csv | 0.0774 | 0.9539 | -0.1383 | -0.0268 | 0.5414 | 0.7318 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase4b_sector_phase3_hybrid | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4b_sector_phase3_hybrid.csv | 0.0722 | 0.9536 | -0.1244 | -0.0249 | 0.5399 | 0.7319 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase6_continuous_aggression_score | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase6_continuous_aggression_score.csv | 0.0780 | 0.9534 | -0.1418 | -0.0270 | 0.5407 | 0.7287 | 0.0000 | 0.6667 | overfit_risk |
| improved_phaser_fast_narrow_regret_allocator | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaser_fast_narrow_regret_allocator.csv | 0.0682 | 0.9527 | -0.1304 | -0.0236 | 0.5377 | 0.7226 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase6_calm_bull_quality_offense | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase6_calm_bull_quality_offense.csv | 0.0773 | 0.9520 | -0.1432 | -0.0268 | 0.5382 | 0.7257 | 0.0000 | 0.6667 | overfit_risk |
| improved_phase4_sector_small_overlay | data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4_sector_small_overlay.csv | 0.0736 | 0.9512 | -0.1306 | -0.0256 | 0.5364 | 0.7274 | 0.0000 | 0.6667 | overfit_risk |

## Interpretation

-   Treat `statistically_supported` as permission for deeper review, not promotion.
-   Treat `promising_but_underpowered` as a candidate for controlled holdout/bootstrap work.
-   Treat `overfit_risk` and `diagnostic_only` as research memory, not deployment evidence.
-   High trial counts should make future frontier sprints more skeptical, not more excited.

## Limitations

-   The audit uses available saved returns and metrics files; it cannot reconstruct unlogged experiments.
-   The PBO value is a project-level proxy across a bounded return-file universe, not a full CPCV estimate.
-   Some research files are long-form and some are one-series files; the script standardizes what it can and skips unreadable files.
