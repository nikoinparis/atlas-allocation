# Phase SSS3 -- Sequence Portfolio Pass-Through

Date: 2026-04-27

## Commands Executed
- `sed -n '1,360p' docs/research/2026-04-27_phase_sss2_sequence_signal_validation_report.md`
- `find data/research/phase_sss2_sequence_signal_validation -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf "%s\t" "$(basename "{}")"; wc -l < "{}"'`
- `python3 - <<'PY' ...SSS2 queue/signal panel/GGG1 artifact schema summaries...`
- `sed -n '1,260p' scripts/build_improvement_artifacts.py`
- `rg -n "ooo6|phaseooo6|state_tilt|portfolio_version_returns" scripts/build_improvement_artifacts.py`
- `sed -n '220,460p' scripts/phase_ooo6_signal_portfolio_pass_through.py`
- `python3 -m py_compile scripts/build_improvement_artifacts.py`
- `python3 -m py_compile scripts/phase_sss3_sequence_portfolio_pass_through.py`
- `python3 scripts/phase_sss3_sequence_portfolio_pass_through.py`
- `BUILD_VERSION_NAMES=improved_phasesss3_calm_old_low_stress_derisk,improved_phasesss3_stress_new_state_defense,improved_phasesss3_recovery_sequence_rerisk,improved_phasesss3_combined_sequence_overlay python3 scripts/build_improvement_artifacts.py`
- `python3 scripts/research_committee_report.py improved_phasesss3_calm_old_low_stress_derisk --quick`
- `python3 scripts/backtest_realism_audit.py improved_phasesss3_calm_old_low_stress_derisk --quick`
- `python3 scripts/allocator_benchmark_audit.py improved_phasesss3_calm_old_low_stress_derisk --quick`

## Files Created / Modified
- `scripts/phase_sss3_sequence_portfolio_pass_through.py`
- `scripts/build_improvement_artifacts.py`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_pass_through_signal_designs.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_candidate_metrics_full.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_state_summary.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_state_guard_deltas.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_sequence_signal_active_performance.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_candidate_diagnostics.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_selection_table.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_audit_results.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_next_action_recommendation.csv`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_protocol.json`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_build.log`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_research_committee_quick.log`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_backtest_realism_quick.log`
- `data/research/phase_sss3_sequence_portfolio_pass_through/sss3_allocator_benchmark_quick.log`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_<SSS3 candidates>.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_weights_<SSS3 candidates>.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_<SSS3 candidates>.csv`
- `reports/research_committee/improved_phasesss3_calm_old_low_stress_derisk_audit.md`
- `reports/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_realism_audit.md`
- `reports/allocator_benchmark/improved_phasesss3_calm_old_low_stress_derisk_allocator_benchmark.md`
- `data/research/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_cost_sensitivity.csv`
- `data/research/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_rebalance_delay_sensitivity.csv`
- `data/research/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_turnover_threshold_sensitivity.csv`
- `data/research/allocator_benchmark/improved_phasesss3_calm_old_low_stress_derisk_allocator_comparison.csv`
- `data/research/allocator_benchmark/improved_phasesss3_calm_old_low_stress_derisk_risk_contribution.csv`
- `docs/research/2026-04-27_phase_sss3_sequence_portfolio_pass_through_report.md`
- `docs/research/project_journey.md`

## SSS2 Pass-Through Queue Used
| signal_name | SSS2_decision | event_count | event_frequency | best_target | precision_lift_vs_same_lagged_state | holdout_precision_lift_vs_same_lagged_state | selected_for_candidate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calm_old_low_stress_signal | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | 50 | 0.045045 | ggg1_underperformance_4w | 0.143729 | 0.147619 | improved_phasesss3_calm_old_low_stress_derisk |
| stress_new_state_signal | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | 47 | 0.044144 | stress_transition_4w | 0.093073 | 0.040351 | improved_phasesss3_stress_new_state_defense |
| qqq_efa_spy_trend_after_calm_or_recovery_signal | KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH | 42 | 0.039640 | recovery_quality_8w | 0.156442 | 0.241935 | improved_phasesss3_recovery_sequence_rerisk |

## Candidate Logic
- `improved_phasesss3_calm_old_low_stress_derisk`: When calm_old_low_stress_signal fires in calm_trend/neutral_mixed, shift at most 1.5% sleeve mass from offense-approved sleeves to existing defense sleeves.
- `improved_phasesss3_stress_new_state_defense`: When stress_new_state_signal fires in stressed_panic, shift at most 2.0% sleeve mass from offense-approved sleeves to existing defense sleeves.
- `improved_phasesss3_recovery_sequence_rerisk`: When qqq_efa_spy_trend_after_calm_or_recovery_signal fires in recovery_confirmed/calm_trend/strong neutral, shift at most 1.5% sleeve mass from existing defense sleeves to offense-approved sleeves.
- `improved_phasesss3_combined_sequence_overlay`: Stress/calm de-risk warnings dominate conflicts; otherwise recovery/calm re-risk confirmation applies. Shifts are smaller than individual overlays.

## Candidate Metrics
| version | ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_turnover | turnover_ratio_vs_production | avg_BIL | avg_SPY | spy_beta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phase2b_regime_confidence_boost | 0.068923 | 0.077931 | 0.884416 | -0.139754 | 0.493176 | -0.026181 | 0.056229 | 1.000000 | 0.283918 | 0.070812 | -0.025205 |
| improved_phase2b_combo_abc | 0.068584 | 0.077616 | 0.883625 | -0.136741 | 0.501559 | -0.026085 | 0.056571 | 1.006087 | 0.285552 | 0.070757 | -0.025163 |
| improved_phaseggg_confirmed_only_robust_offense | 0.071381 | 0.076248 | 0.936168 | -0.117739 | 0.606267 | -0.025377 | 0.061839 | 1.099763 | 0.266580 | 0.060257 | -0.031343 |
| improved_phasesss3_calm_old_low_stress_derisk | 0.071407 | 0.076109 | 0.938217 | -0.116008 | 0.615534 | -0.025329 | 0.061836 | 1.099715 | 0.266831 | 0.060206 | -0.031305 |
| improved_phasesss3_stress_new_state_defense | 0.071394 | 0.076245 | 0.936383 | -0.117739 | 0.606380 | -0.025375 | 0.061836 | 1.099716 | 0.266560 | 0.060245 | -0.031336 |
| improved_phasesss3_recovery_sequence_rerisk | 0.071403 | 0.076255 | 0.936371 | -0.117739 | 0.606455 | -0.025379 | 0.061847 | 1.099913 | 0.266545 | 0.060257 | -0.031343 |
| improved_phasesss3_combined_sequence_overlay | 0.071426 | 0.076158 | 0.937858 | -0.116585 | 0.612651 | -0.025345 | 0.061841 | 1.099803 | 0.266703 | 0.060215 | -0.031313 |

## Sequence-Signal Active Vs Inactive Results
| candidate | signal_name | n_weeks | ann_return_delta_vs_ggg1 | mean_weekly_delta_vs_ggg1 | cvar_5_delta_vs_ggg1 | max_drawdown_delta_vs_ggg1 |
| --- | --- | --- | --- | --- | --- | --- |
| improved_phasesss3_calm_old_low_stress_derisk | calm_old_low_stress_signal | 50 | -0.000135 | -0.000005 | 0.000289 | 0.000723 |
| improved_phasesss3_stress_new_state_defense | stress_new_state_signal | 49 | 0.000447 | 0.000008 | 0.000005 | 0.000156 |
| improved_phasesss3_recovery_sequence_rerisk | qqq_efa_spy_trend_after_calm_or_recovery_signal | 44 | 0.000155 | 0.000003 | -0.000033 | -0.000068 |
| improved_phasesss3_combined_sequence_overlay | calm_old_low_stress_signal | 50 | -0.000110 | -0.000004 | 0.000192 | 0.000456 |
| improved_phasesss3_combined_sequence_overlay | stress_new_state_signal | 49 | 0.000375 | 0.000006 | 0.000130 | 0.000488 |
| improved_phasesss3_combined_sequence_overlay | qqq_efa_spy_trend_after_calm_or_recovery_signal | 44 | 0.000063 | 0.000001 | -0.000031 | -0.000108 |

## State-By-State Impact
| version | state | n_weeks | ann_return | sharpe | max_drawdown | cvar_5 | avg_BIL | avg_SPY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | 295 | 0.040851 | 0.513625 | -0.139322 | -0.027026 | 0.110330 | 0.079825 |
| improved_phaseggg_confirmed_only_robust_offense | neutral_mixed | 493 | 0.112112 | 1.461561 | -0.091217 | -0.024706 | 0.260356 | 0.065839 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | 44 | 0.025705 | 0.344267 | -0.053798 | -0.022096 | 0.113607 | 0.055815 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 49 | 0.066671 | 1.142121 | -0.032194 | -0.017135 | 0.169929 | 0.054219 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 229 | 0.035803 | 0.480687 | -0.121622 | -0.023120 | 0.531336 | 0.025176 |
| improved_phasesss3_calm_old_low_stress_derisk | calm_trend | 295 | 0.040863 | 0.515318 | -0.139333 | -0.026914 | 0.111093 | 0.079679 |
| improved_phasesss3_calm_old_low_stress_derisk | neutral_mixed | 493 | 0.112099 | 1.461658 | -0.091217 | -0.024708 | 0.260440 | 0.065818 |
| improved_phasesss3_calm_old_low_stress_derisk | recovery_confirmed | 44 | 0.025703 | 0.344242 | -0.053800 | -0.022096 | 0.113601 | 0.055815 |
| improved_phasesss3_calm_old_low_stress_derisk | recovery_fragile | 49 | 0.066673 | 1.142151 | -0.032194 | -0.017135 | 0.169927 | 0.054220 |
| improved_phasesss3_calm_old_low_stress_derisk | stressed_panic | 229 | 0.035933 | 0.484613 | -0.120614 | -0.023030 | 0.531390 | 0.025167 |
| improved_phasesss3_stress_new_state_defense | calm_trend | 295 | 0.040851 | 0.513630 | -0.139322 | -0.027026 | 0.110330 | 0.079825 |
| improved_phasesss3_stress_new_state_defense | neutral_mixed | 493 | 0.112116 | 1.461698 | -0.091221 | -0.024702 | 0.260344 | 0.065841 |
| improved_phasesss3_stress_new_state_defense | recovery_confirmed | 44 | 0.025703 | 0.344258 | -0.053798 | -0.022095 | 0.113591 | 0.055821 |
| improved_phasesss3_stress_new_state_defense | recovery_fragile | 49 | 0.066617 | 1.141112 | -0.032194 | -0.017141 | 0.169766 | 0.054248 |
| improved_phasesss3_stress_new_state_defense | stressed_panic | 229 | 0.035869 | 0.481610 | -0.121615 | -0.023111 | 0.531301 | 0.025108 |
| improved_phasesss3_recovery_sequence_rerisk | calm_trend | 295 | 0.040885 | 0.513943 | -0.139328 | -0.027033 | 0.110204 | 0.079828 |
| improved_phasesss3_recovery_sequence_rerisk | neutral_mixed | 493 | 0.112142 | 1.461854 | -0.091218 | -0.024706 | 0.260353 | 0.065838 |
| improved_phasesss3_recovery_sequence_rerisk | recovery_confirmed | 44 | 0.025705 | 0.344267 | -0.053798 | -0.022096 | 0.113607 | 0.055815 |
| improved_phasesss3_recovery_sequence_rerisk | recovery_fragile | 49 | 0.066671 | 1.142122 | -0.032194 | -0.017135 | 0.169929 | 0.054219 |
| improved_phasesss3_recovery_sequence_rerisk | stressed_panic | 229 | 0.035803 | 0.480689 | -0.121622 | -0.023120 | 0.531336 | 0.025176 |
| improved_phasesss3_combined_sequence_overlay | calm_trend | 295 | 0.040887 | 0.515023 | -0.139334 | -0.026957 | 0.110734 | 0.079730 |
| improved_phasesss3_combined_sequence_overlay | neutral_mixed | 493 | 0.112130 | 1.461956 | -0.091221 | -0.024704 | 0.260400 | 0.065826 |
| improved_phasesss3_combined_sequence_overlay | recovery_confirmed | 44 | 0.025702 | 0.344243 | -0.053799 | -0.022095 | 0.113591 | 0.055819 |
| improved_phasesss3_combined_sequence_overlay | recovery_fragile | 49 | 0.066632 | 1.141388 | -0.032194 | -0.017139 | 0.169805 | 0.054241 |
| improved_phasesss3_combined_sequence_overlay | stressed_panic | 229 | 0.035940 | 0.483998 | -0.120945 | -0.023053 | 0.531346 | 0.025119 |

## Comparison Vs GGG1 / Production / Shadow
The selection table compares every SSS3 candidate against GGG1 while the turnover cap is measured against the current production pin.
| candidate | decision | delta_ann_return_vs_ggg1 | delta_sharpe_vs_ggg1 | delta_max_drawdown_vs_ggg1 | delta_cvar_5_vs_ggg1 | turnover_ratio_vs_production | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasesss3_calm_old_low_stress_derisk | KEEP_AS_SHADOW | 0.000026 | 0.002049 | 0.001731 | 0.000048 | 1.099715 | specific sequence weakness improves while GGG1 guardrails are preserved |
| improved_phasesss3_stress_new_state_defense | KEEP_AS_SHADOW | 0.000013 | 0.000215 | 0.000000 | 0.000002 | 1.099716 | specific sequence weakness improves while GGG1 guardrails are preserved |
| improved_phasesss3_recovery_sequence_rerisk | KEEP_AS_SHADOW | 0.000022 | 0.000203 | -0.000000 | -0.000002 | 1.099913 | specific sequence weakness improves while GGG1 guardrails are preserved |
| improved_phasesss3_combined_sequence_overlay | KEEP_AS_SHADOW | 0.000045 | 0.001690 | 0.001154 | 0.000032 | 1.099803 | specific sequence weakness improves while GGG1 guardrails are preserved |

## Hidden Beta / Cash / Turnover Checks
| candidate | delta_avg_BIL_vs_ggg1 | delta_avg_SPY_vs_ggg1 | delta_spy_beta_vs_ggg1 | hidden_beta_not_higher | hidden_cash_check | turnover_ratio_vs_production | state_guards_preserved | sequence_signal_active_windows_improved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasesss3_calm_old_low_stress_derisk | 0.000251 | -0.000050 | 0.000038 | True | PASS | 1.099715 | True | True |
| improved_phasesss3_stress_new_state_defense | -0.000020 | -0.000011 | 0.000007 | True | PASS | 1.099716 | True | True |
| improved_phasesss3_recovery_sequence_rerisk | -0.000035 | 0.000000 | 0.000001 | True | PASS | 1.099913 | True | True |
| improved_phasesss3_combined_sequence_overlay | 0.000123 | -0.000042 | 0.000031 | True | PASS | 1.099803 | True | True |

## Audit Results
| candidate | audit | returncode | verdict | log |
| --- | --- | --- | --- | --- |
| improved_phasesss3_calm_old_low_stress_derisk | research_committee_quick | 0 | PASS | /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_sss3_sequence_portfolio_pass_through/sss3_research_committee_quick.log |
| improved_phasesss3_calm_old_low_stress_derisk | backtest_realism_quick | 0 | PASS | /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_sss3_sequence_portfolio_pass_through/sss3_backtest_realism_quick.log |
| improved_phasesss3_calm_old_low_stress_derisk | allocator_benchmark_quick | 0 | PASS | /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_sss3_sequence_portfolio_pass_through/sss3_allocator_benchmark_quick.log |

## Final Decision
**KEEP_SSS3_AS_SHADOW**

Reason: improved_phasesss3_calm_old_low_stress_derisk improves a sequence-defined weakness and passed quick audits, but does not clearly dominate GGG1.

## Should Hard ML Continue?
Only continue hard-ML work if the final decision points to a controlled shadow, sleeve meta-labeling, or a clearly stronger audited challenger. No production or shadow pin was changed in SSS3.

## Exact Prompt Outline For Next Phase
Phase SSS3 follow-up: treat `improved_phasesss3_calm_old_low_stress_derisk` as a research shadow only. Run full research committee, backtest realism, allocator benchmark, and robustness simulation audits; add bootstrap/block-resample and recent-holdout review versus GGG1; explicitly verify the mature-calm signal is not a refined-state or cash/beta proxy; then decide whether the shadow deserves human review as a production challenger. Do not change production or official shadow pins automatically.

## Resume-Worthy Technical Summary
SSS3 converted the three SSS2-cleared sequence signals into four bounded production-pipeline candidate versions using explicit `state_tilt` modes in `build_improvement_artifacts.py`. Each candidate starts from GGG1's confirmed-only robust offense architecture, applies at most 1.0%-2.0% sleeve-level shifts inside existing offense/defense sleeves, writes normal Layer 3 returns/weights/sleeve-weight artifacts, and is compared against production, official shadow, and GGG1. Selection requires no material deterioration in Sharpe/return/DD/CVaR, turnover <= 1.10x production, preserved stressed/recovery/calm state behavior, no hidden SPY beta or cash-release risk, and improvement in sequence-active windows.
