# Phase JJJ4 — Adaptive Risk-Contribution Allocator

Date: 2026-04-27

## Commands executed
```
sed -n '1,160p' docs/research/2026-04-27_phase_jjj3_targeted_lookthrough_repair_report.md
sed -n '1,120p' docs/research/2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md
rg -n 'phaseggg|phase_jjj3|state_tilt|internal_redeploy|version_name|apply_state_conditioned_tilt|risk' scripts/build_improvement_artifacts.py | head -n 120
python3 - <<'PY' ... inspect GGG1 sleeve risk contribution ...
python3 scripts/phase_jjj4_adaptive_risk_contribution_allocator.py
BUILD_VERSION_NAMES=improved_phasejjj4_state_risk_contribution_caps,improved_phasejjj4_adaptive_mom_vol_corr_budget,improved_phasejjj4_conservative_adaptive_risk_budget SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py
```

## Files created / modified
- `scripts/build_improvement_artifacts.py`
- `scripts/phase_jjj4_adaptive_risk_contribution_allocator.py`
- `data/research/phase_jjj4_adaptive_risk_contribution_allocator/*`
- `data/05_layer3_portfolio_construction/phase_jjj4_*.csv`
- `docs/research/2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md`
- `docs/research/project_journey.md`

## Candidate metrics
| name | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | turnover_ratio_vs_production | avg_BIL | avg_SPY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasejjj4_state_risk_contribution_caps | 0.068049 | 0.921569 | -0.119196 | -0.024749 | 0.058001 | 1.032436 | 0.264536 | 0.059092 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | 0.068049 | 0.921569 | -0.119196 | -0.024749 | 0.058001 | 1.032436 | 0.264536 | 0.059092 |
| improved_phasejjj4_conservative_adaptive_risk_budget | 0.068049 | 0.921569 | -0.119196 | -0.024749 | 0.058001 | 1.032436 | 0.264536 | 0.059092 |
| improved_phaseggg_confirmed_only_robust_offense | 0.071381 | 0.943460 | -0.117739 | -0.025377 | 0.061783 | 1.099763 | 0.266580 | 0.060257 |
| improved_phase2b_regime_confidence_boost | 0.068923 | 0.895263 | -0.139754 | -0.026181 | 0.056179 | 1.000000 | 0.283918 | 0.070812 |
| improved_phase2b_combo_abc | 0.068584 | 0.894473 | -0.136741 | -0.026085 | 0.056521 | 1.006087 | 0.285552 | 0.070757 |

## Selection table
| candidate | decision | delta_sharpe_vs_ggg1 | delta_ann_return_vs_ggg1 | delta_risk_herfindahl_vs_ggg1 | turnover_under_cap | guard_states_preserved | hidden_beta_not_higher |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasejjj4_state_risk_contribution_caps | REJECT | -0.021891 | -0.003332 | 0.007895 | True | False | True |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | REJECT | -0.021891 | -0.003332 | 0.007895 | True | False | True |
| improved_phasejjj4_conservative_adaptive_risk_budget | REJECT | -0.021891 | -0.003332 | 0.007895 | True | False | True |

## Risk-contribution diagnosis
| state | sleeve | avg_weight | risk_contribution | risk_minus_weight | return_contribution_proxy |
| --- | --- | --- | --- | --- | --- |
| full_window | composite_regime_defense_component | 0.217157 | 0.201836 | -0.015321 | 0.013722 |
| full_window | composite_selective_signals | 0.154295 | 0.182700 | 0.028405 | 0.012227 |
| full_window | composite_regime_offense_component | 0.097840 | 0.175571 | 0.077731 | 0.006076 |
| full_window | taa_10m_sma | 0.112391 | 0.155396 | 0.043006 | 0.008520 |
| full_window | cta_trend_long_only | 0.102677 | 0.151932 | 0.049255 | 0.009423 |
| full_window | dual_momentum_topn | 0.090289 | 0.132624 | 0.042335 | 0.008491 |
| full_window | cash::BIL | 0.225352 | -0.000060 | -0.225412 | 0.002643 |
| recovery_confirmed | composite_regime_offense_component | 0.222000 | 0.358466 | 0.136465 | 0.008191 |
| recovery_confirmed | cta_trend_long_only | 0.163697 | 0.200349 | 0.036653 | 0.017210 |
| recovery_confirmed | composite_regime_defense_component | 0.218718 | 0.150943 | -0.067775 | -0.001769 |
| recovery_confirmed | taa_10m_sma | 0.120378 | 0.119062 | -0.001317 | 0.004102 |
| recovery_confirmed | composite_selective_signals | 0.132898 | 0.097728 | -0.035170 | -0.001437 |
| recovery_confirmed | dual_momentum_topn | 0.058039 | 0.073300 | 0.015261 | 0.000504 |
| recovery_confirmed | cash::BIL | 0.084270 | 0.000153 | -0.084118 | 0.001301 |
| recovery_fragile | composite_regime_defense_component | 0.240736 | 0.306055 | 0.065319 | -0.017962 |
| recovery_fragile | composite_regime_offense_component | 0.126386 | 0.154780 | 0.028394 | 0.019758 |
| recovery_fragile | cta_trend_long_only | 0.120863 | 0.153793 | 0.032930 | 0.019578 |
| recovery_fragile | composite_selective_signals | 0.156897 | 0.147400 | -0.009497 | 0.004611 |

## Concentration results
| candidate | state | risk_herfindahl | top_risk_sleeve | top_risk_contribution | avg_pairwise_corr |
| --- | --- | --- | --- | --- | --- |
| improved_phasejjj4_state_risk_contribution_caps | full_window | 0.177658 | composite_regime_defense_component | 0.232496 | 0.449518 |
| improved_phasejjj4_state_risk_contribution_caps | calm_trend | 0.171651 | composite_selective_signals | 0.214943 | 0.497520 |
| improved_phasejjj4_state_risk_contribution_caps | neutral_mixed | 0.180932 | composite_regime_defense_component | 0.256932 | 0.456942 |
| improved_phasejjj4_state_risk_contribution_caps | recovery_confirmed | 0.184065 | composite_regime_defense_component | 0.269663 | 0.515376 |
| improved_phasejjj4_state_risk_contribution_caps | recovery_fragile | 0.216448 | composite_regime_defense_component | 0.359379 | 0.375659 |
| improved_phasejjj4_state_risk_contribution_caps | stressed_panic | 0.184628 | composite_regime_defense_component | 0.243469 | 0.426538 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | full_window | 0.177658 | composite_regime_defense_component | 0.232496 | 0.449518 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | calm_trend | 0.171651 | composite_selective_signals | 0.214943 | 0.497520 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | neutral_mixed | 0.180932 | composite_regime_defense_component | 0.256932 | 0.456942 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | recovery_confirmed | 0.184065 | composite_regime_defense_component | 0.269663 | 0.515376 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | recovery_fragile | 0.216448 | composite_regime_defense_component | 0.359379 | 0.375659 |
| improved_phasejjj4_adaptive_mom_vol_corr_budget | stressed_panic | 0.184628 | composite_regime_defense_component | 0.243469 | 0.426538 |
| improved_phasejjj4_conservative_adaptive_risk_budget | full_window | 0.177658 | composite_regime_defense_component | 0.232496 | 0.449518 |
| improved_phasejjj4_conservative_adaptive_risk_budget | calm_trend | 0.171651 | composite_selective_signals | 0.214943 | 0.497520 |
| improved_phasejjj4_conservative_adaptive_risk_budget | neutral_mixed | 0.180932 | composite_regime_defense_component | 0.256932 | 0.456942 |
| improved_phasejjj4_conservative_adaptive_risk_budget | recovery_confirmed | 0.184065 | composite_regime_defense_component | 0.269663 | 0.515376 |
| improved_phasejjj4_conservative_adaptive_risk_budget | recovery_fragile | 0.216448 | composite_regime_defense_component | 0.359379 | 0.375659 |
| improved_phasejjj4_conservative_adaptive_risk_budget | stressed_panic | 0.184628 | composite_regime_defense_component | 0.243469 | 0.426538 |
| improved_phaseggg_confirmed_only_robust_offense | full_window | 0.169763 | composite_regime_defense_component | 0.201836 | 0.449518 |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | 0.168784 | composite_selective_signals | 0.199657 | 0.497520 |
| improved_phaseggg_confirmed_only_robust_offense | neutral_mixed | 0.170420 | composite_regime_defense_component | 0.202608 | 0.456942 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | 0.220521 | composite_regime_offense_component | 0.358466 | 0.515376 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 0.191721 | composite_regime_defense_component | 0.306055 | 0.375659 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 0.179865 | composite_regime_defense_component | 0.238096 | 0.426538 |

## Audit results
- research_committee: skipped: no candidate qualified
- realism: skipped
- allocator: skipped

## Final decision
**KEEP_GGG1_AS_PRODUCTION_CANDIDATE**

Best candidate: `improved_phasejjj4_state_risk_contribution_caps` (`REJECT`).

Reason: No adaptive risk-contribution candidate clearly improved or de-risked GGG1.

## Answers
- Did any JJJ4 candidate beat GGG1? No.
- Did any candidate reduce concentration or tail risk without hurting Sharpe? No.
- Did turnover stay under 1.10x production? True.
- Did guard states stay protected? False.
- Was improvement hidden beta or real? Hidden beta gate passed for all candidates: True.
- Adaptive risk-contribution allocation should continue: False.

## Exact prompt outline for the next phase
Keep GGG1 as production candidate; do not force allocator changes. Next work should be packaging/human review unless a separate Layer 2A sleeve-design hypothesis is explicitly requested.
