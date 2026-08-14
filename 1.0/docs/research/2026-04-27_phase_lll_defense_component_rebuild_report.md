# Phase LLL — Defense Component Rebuild

Date: 2026-04-27

## Commands executed
```
sed -n '1,130p' docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md
python3 - <<'PY' ... summarize KKK sleeve issue diagnostics ...
rg -n 'build_state_conditional_decomposition_sleeve_panels|phaseggg_confirmed_robust|defense_component|internal_redeploy|phaseggg' scripts/build_improvement_artifacts.py | head -n 180
python3 - <<'PY' ... diagnose GGG1 defense ETF contribution by state ...
python3 scripts/phase_lll_defense_component_rebuild.py
BUILD_VERSION_NAMES=improved_phaselll_recovery_defense_filter,improved_phaselll_recovery_defense_blend,improved_phaselll_conservative_defense_polish SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py
```

## Files created / modified
- `scripts/build_improvement_artifacts.py`
- `scripts/phase_lll_defense_component_rebuild.py`
- `data/research/phase_lll_defense_component_rebuild/*`
- `data/05_layer3_portfolio_construction/portfolio_version_*_improved_phaselll_*.csv`
- `docs/research/2026-04-27_phase_lll_defense_component_rebuild_report.md`
- `docs/research/project_journey.md`

## Defense component diagnosis
| candidate | state | ann_return | sharpe | avg_GLD | avg_HYG | avg_LQD | avg_TLT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | 0.067421 | 1.013690 | 0.213559 | 0.284181 | 0.197740 | 0.107910 |
| improved_phaseggg_confirmed_only_robust_offense | neutral_mixed | 0.052850 | 0.603647 | 0.269777 | 0.209939 | 0.232590 | 0.200473 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | 0.130589 | 1.700421 | 0.352273 | 0.159091 | 0.223485 | 0.265152 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 0.086066 | 1.065606 | 0.253401 | 0.277211 | 0.256803 | 0.212585 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 0.054280 | 0.446052 | 0.209607 | 0.324600 | 0.268559 | 0.192868 |

## Internal ETF findings
| state | ETF | avg_weight | ann_contribution_proxy |
| --- | --- | --- | --- |
| calm_trend | TLT | 0.107910 | -0.000383 |
| calm_trend | BIL | 0.196610 | 0.000600 |
| calm_trend | LQD | 0.197740 | 0.003076 |
| calm_trend | HYG | 0.284181 | 0.034992 |
| calm_trend | GLD | 0.213559 | 0.040386 |
| neutral_mixed | BIL | 0.087221 | -0.000129 |
| neutral_mixed | TLT | 0.200473 | 0.000417 |
| neutral_mixed | LQD | 0.232590 | 0.003223 |
| neutral_mixed | HYG | 0.209939 | 0.013939 |
| neutral_mixed | GLD | 0.269777 | 0.046614 |
| recovery_confirmed | TLT | 0.265152 | -0.006253 |
| recovery_confirmed | BIL | 0.000000 | 0.000000 |
| recovery_confirmed | HYG | 0.159091 | 0.012994 |
| recovery_confirmed | LQD | 0.223485 | 0.024594 |
| recovery_confirmed | GLD | 0.352273 | 0.102016 |
| ... |  |  |  |

## Candidate metrics
| name | ann_return | sharpe | max_drawdown | cvar_5 | turnover_ratio_vs_production | avg_BIL | avg_SPY |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaselll_recovery_defense_filter | 0.071594 | 0.946223 | -0.117489 | -0.025347 | 1.153431 | 0.266593 | 0.060193 |
| improved_phaselll_recovery_defense_blend | 0.071185 | 0.940642 | -0.117448 | -0.025355 | 1.120021 | 0.266501 | 0.060205 |
| improved_phaselll_conservative_defense_polish | 0.071271 | 0.942064 | -0.117552 | -0.025362 | 1.108521 | 0.266565 | 0.060194 |
| improved_phaseggg_confirmed_only_robust_offense | 0.071381 | 0.943460 | -0.117739 | -0.025377 | 1.099763 | 0.266580 | 0.060257 |
| improved_phase2b_regime_confidence_boost | 0.068923 | 0.895263 | -0.139754 | -0.026181 | 1.000000 | 0.283918 | 0.070812 |
| improved_phase2b_combo_abc | 0.068584 | 0.894473 | -0.136741 | -0.026085 | 1.006087 | 0.285552 | 0.070757 |

## Defense component before / after
| candidate | state | ann_return | sharpe | avg_GLD | avg_HYG | avg_LQD | avg_TLT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | 0.130589 | 1.700421 | 0.352273 | 0.159091 | 0.223485 | 0.265152 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 0.086066 | 1.065606 | 0.253401 | 0.277211 | 0.256803 | 0.212585 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 0.054280 | 0.446052 | 0.209607 | 0.324600 | 0.268559 | 0.192868 |
| improved_phaselll_recovery_defense_filter | recovery_confirmed | 0.129016 | 1.387787 | 0.511364 | 0.193182 | 0.295455 | 0.000000 |
| improved_phaselll_recovery_defense_filter | recovery_fragile | 0.143318 | 2.247814 | 0.000000 | 0.370748 | 0.309524 | 0.258503 |
| improved_phaselll_recovery_defense_filter | stressed_panic | 0.054280 | 0.446052 | 0.209607 | 0.324600 | 0.268559 | 0.192868 |
| improved_phaselll_recovery_defense_blend | recovery_confirmed | 0.130182 | 1.600595 | 0.431818 | 0.176136 | 0.259470 | 0.132576 |
| improved_phaselll_recovery_defense_blend | recovery_fragile | 0.090208 | 1.207658 | 0.157313 | 0.323980 | 0.283163 | 0.235544 |
| improved_phaselll_recovery_defense_blend | stressed_panic | 0.054280 | 0.446052 | 0.209607 | 0.324600 | 0.268559 | 0.192868 |
| improved_phaselll_conservative_defense_polish | recovery_confirmed | 0.130481 | 1.672389 | 0.392045 | 0.167614 | 0.241477 | 0.198864 |
| improved_phaselll_conservative_defense_polish | recovery_fragile | 0.088384 | 1.144830 | 0.205357 | 0.300595 | 0.269983 | 0.224065 |
| improved_phaselll_conservative_defense_polish | stressed_panic | 0.054280 | 0.446052 | 0.209607 | 0.324600 | 0.268559 | 0.192868 |

## Selection table
| candidate | decision | delta_sharpe_vs_ggg1 | delta_ann_return_vs_ggg1 | turnover_under_cap | stressed_panic_preserved | recovery_confirmed_not_worse | recovery_fragile_not_worse | hidden_beta_not_higher |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaselll_recovery_defense_filter | REJECT | 0.002763 | 0.000213 | False | True | True | True | True |
| improved_phaselll_recovery_defense_blend | REJECT | -0.002818 | -0.000196 | False | True | True | False | True |
| improved_phaselll_conservative_defense_polish | REJECT | -0.001396 | -0.000110 | False | True | True | True | True |

## Candidate diagnostics
| candidate | doubled_cost_sharpe | one_week_delay_sharpe |
| --- | --- | --- |
| improved_phaselll_recovery_defense_filter | 0.901922 | 0.785157 |
| improved_phaselll_recovery_defense_blend | 0.897658 | 0.780563 |
| improved_phaselll_conservative_defense_polish | 0.899492 | 0.782339 |

## Audit results
- research_committee: skipped: no candidate qualified
- realism: skipped
- allocator: skipped

## Final decision
**REBUILD_COMPOSITE_SELECTIVE_SIGNALS_NEXT**

Best candidate: `improved_phaselll_recovery_defense_filter` (`REJECT`).

Reason: Defense rebuild candidates did not clearly improve GGG1; KKK's next strongest issue is composite_selective_signals.

Defense component rebuild should continue: **False**.

## Exact prompt outline for the next phase
Implement a narrow diagnostic-gated rebuild of composite_selective_signals focused only on recovery_confirmed drag; preserve GGG1 offense component logic and production pins.
