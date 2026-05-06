# Phase KKK — Signal and Sleeve Contribution Audit

Date: 2026-04-27

## Commands executed
```
sed -n '1,140p' docs/research/2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md
sed -n '1,100p' docs/research/2026-04-27_phase_iii_production_candidate_review_report.md
sed -n '1,100p' docs/research/2026-04-27_phase_ggg_state_conditional_composite_offense_report.md
find data/02_layer1_signals -maxdepth 1 -type f | sort | sed -n '1,120p'
find data/03_layer2a_strategy_logic -maxdepth 1 -type f | sort | sed -n '1,80p'
python3 scripts/phase_kkk_signal_sleeve_contribution_audit.py
```

## Files created / modified
- `scripts/phase_kkk_signal_sleeve_contribution_audit.py`
- `data/research/phase_kkk_signal_sleeve_contribution_audit/*.csv`
- `docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md`
- `docs/research/project_journey.md`

## Layer 1 signal findings
| signal_name | avg_ic_tstat_nw | avg_abs_redundancy | validation_quality_score | signal_flag |
| --- | --- | --- | --- | --- |
| multi_mom_equal | 2.897679 | 0.422781 | 3.655410 | KEEP_STRONG |
| xsmom_global | 2.832364 | 0.413829 | 3.594821 | KEEP_STRONG |
| moving_average_distance | 2.746720 | 0.418374 | 3.489608 | KEEP_STRONG |
| multi_mom_invvol | 2.667915 | 0.416425 | 3.391889 | KEEP_STRONG |
| trend_clarity_momentum | 2.329801 | 0.416585 | 3.057037 | KEEP_STRONG |
| breadth_confirmed_momentum | 1.805122 | 0.346614 | 2.458981 | STATE_SPECIFIC_ONLY |
| xsmom_asset_class_neutral | 1.506638 | 0.332764 | 2.223693 | STATE_SPECIFIC_ONLY |
| tsmom_vol_scaled | 1.025315 | 0.376872 | 1.727129 | STATE_SPECIFIC_ONLY |
| contained_recovery_quality | 0.622333 | 0.280009 | 1.184961 | NEEDS_REVALIDATION |
| residual_momentum | 0.488789 | 0.215134 | 1.138512 | NEEDS_REVALIDATION |
| reversal_4w_asset_class_neutral | 0.099309 | 0.122670 | 0.476232 | RETIRE_CANDIDATE |
| reversal_4w_global | 0.032327 | 0.147094 | 0.475335 | RETIRE_CANDIDATE |
| ... |  |  |  |  |

## Layer 2A sleeve findings
| sleeve | ann_return | sharpe | corr_with_ggg1 | avg_weight_ggg1 | max_weight_ggg1 | sleeve_flag |
| --- | --- | --- | --- | --- | --- | --- |
| cash::BIL | 0.011789 | 3.400088 | -0.004266 | 0.225352 | 1.000000 | CORE_KEEP |
| composite_regime_defense_component | 0.060217 | 0.654379 | 0.636385 | 0.217157 | 0.426726 | DIVERSIFIER_KEEP |
| composite_selective_signals | 0.075742 | 0.801323 | 0.833537 | 0.154295 | 0.308930 | CORE_KEEP |
| taa_10m_sma | 0.067639 | 0.587028 | 0.770333 | 0.112391 | 0.270931 | STATE_SPECIFIC_KEEP |
| cta_trend_long_only | 0.079232 | 0.662414 | 0.868509 | 0.102677 | 0.444870 | STATE_SPECIFIC_KEEP |
| composite_regime_offense_component | 0.048042 | 0.359545 | 0.712668 | 0.097840 | 0.313820 | STATE_SPECIFIC_KEEP |
| dual_momentum_topn | 0.087371 | 0.727742 | 0.848186 | 0.090289 | 0.248801 | STATE_SPECIFIC_KEEP |
| composite_anti_chop_clarity | 0.078272 | 0.823045 | 0.749492 | 0.000000 | 0.000000 | LOW_WEIGHT_MONITOR |
| composite_selective_trend_ensemble | 0.075742 | 0.801323 | 0.833537 | 0.000000 | 0.000000 | LOW_WEIGHT_MONITOR |
| composite_structural_defense_sleeve | 0.022632 | 0.661534 | 0.001224 | 0.000000 | 0.000000 | LOW_WEIGHT_MONITOR |
| composite_trend_quality_module | 0.087383 | 0.673377 | 0.836099 | 0.000000 | 0.000000 | LOW_WEIGHT_MONITOR |
| composite_trend_quality_refined | 0.105781 | 0.800070 | 0.823325 | 0.000000 | 0.000000 | LOW_WEIGHT_MONITOR |
| cross_sectional_reversal_combo_ls | -0.032667 | -0.333456 | 0.072468 | 0.000000 | 0.000000 | RETIRE_CANDIDATE |
| cta_trend_long_short_research | 0.014768 | 0.307122 | 0.240975 | 0.000000 | 0.000000 | LOW_WEIGHT_MONITOR |
| ... |  |  |  |  |  |  |

## State-by-state harmful sleeves
| version | state | sleeve | avg_weight | ann_return | sharpe | state_flag |
| --- | --- | --- | --- | --- | --- | --- |
| improved_phase2b_regime_confidence_boost | recovery_confirmed | composite_selective_signals | 0.231073 | -0.014439 | -0.183467 | STATE_HARMFUL |
| improved_phase2b_regime_confidence_boost | stressed_panic | taa_10m_sma | 0.076165 | -0.051923 | -0.193671 | STATE_HARMFUL |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | composite_regime_offense_component | 0.088667 | -0.041174 | -0.219300 | STATE_HARMFUL |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | composite_regime_defense_component | 0.218718 | -0.010965 | -0.105847 | STATE_HARMFUL |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | composite_selective_signals | 0.132898 | -0.014439 | -0.183467 | STATE_HARMFUL |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | composite_regime_defense_component | 0.240736 | -0.076193 | -0.786442 | STATE_HARMFUL |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | taa_10m_sma | 0.071832 | -0.051923 | -0.193671 | STATE_HARMFUL |

## Redundancy / diversification
- High-correlation clusters: 3
- Redundant weak sleeve rows: 3
- Diversifying sleeve rows: 1

## Weak / rebuild / retire candidates
| item | item_type | problem_type | affected_states | current_avg_weight_ggg1 | recommended_future_action | severity |
| --- | --- | --- | --- | --- | --- | --- |
| composite_regime_defense_component | sleeve | state_harmful_or_weak_used_sleeve | recovery_confirmed|recovery_fragile | 0.217157 | REBUILD_WEAK_LAYER2A_SLEEVE | HIGH |
| composite_selective_signals | sleeve | state_harmful_or_weak_used_sleeve | recovery_confirmed | 0.154295 | REBUILD_WEAK_LAYER2A_SLEEVE | HIGH |
| composite_regime_offense_component | sleeve | state_harmful_or_weak_used_sleeve | calm_trend | 0.097840 | REBUILD_WEAK_LAYER2A_SLEEVE | HIGH |
| taa_10m_sma | sleeve | state_harmful_or_weak_used_sleeve | stressed_panic | 0.112391 | STATE_GATING_REVIEW | MEDIUM |
| cta_trend_long_only | sleeve | state_harmful_or_weak_used_sleeve | calm_trend | 0.102677 | STATE_GATING_REVIEW | MEDIUM |
| dual_momentum_topn | sleeve | state_harmful_or_weak_used_sleeve | recovery_confirmed | 0.090289 | STATE_GATING_REVIEW | MEDIUM |
| contained_recovery_quality | signal | weak_or_redundant_signal_quality | unknown |  | REVALIDATE_LAYER1_SIGNALS | MEDIUM |
| residual_momentum | signal | weak_or_redundant_signal_quality | unknown |  | REVALIDATE_LAYER1_SIGNALS | MEDIUM |
| reversal_4w_asset_class_neutral | signal | weak_or_redundant_signal_quality | unknown |  | REVALIDATE_LAYER1_SIGNALS | MEDIUM |
| reversal_4w_global | signal | weak_or_redundant_signal_quality | unknown |  | REVALIDATE_LAYER1_SIGNALS | MEDIUM |

## GGG1 non-allocator sanity check
| check | result | readiness_category |
| --- | --- | --- |
| allocator_path | clean_enough_after_JJJ4 | NON_ALLOCATOR_STACK_CLEAN_ENOUGH |
| signal_lineage | partial_manifest_only | NEEDS_SIGNAL_REVALIDATION |
| state_sample_size | recovery_confirmed/recovery_fragile remain small samples | NEEDS_STATE_GATING_REVIEW |
| weak_used_sleeves | state-harmful used sleeves remain in GGG1 | NEEDS_SLEEVE_REBUILD |

## Missing data / instrumentation
| limitation | recommendation | severity |
| --- | --- | --- |
| Exact signal-to-sleeve lineage is only partially explicit in layer2_manifest. | Persist a Layer2A signal_usage_by_sleeve table during sleeve construction. | MEDIUM |

## Final next-frontier recommendation
**REBUILD_WEAK_LAYER2A_SLEEVE**

Reason: At least one heavily used GGG1 sleeve remains state-harmful or weak enough to justify a rebuild before more allocator work.

Another research phase justified: **True**.

## Exact prompt outline for the next phase
Implement a diagnostic-gated Layer 2A sleeve rebuild focused on the top KKK issue only; do not change allocator logic or production pins.
