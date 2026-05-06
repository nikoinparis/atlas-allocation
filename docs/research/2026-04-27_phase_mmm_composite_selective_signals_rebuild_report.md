# Phase MMM — Composite Selective Signals Rebuild

Date: 2026-04-27

## Commands executed
```
sed -n '1,130p' docs/research/2026-04-27_phase_lll_defense_component_rebuild_report.md
python3 - <<'PY' ... inspect KKK/LLL diagnostics and CSS internals ...
rg -n 'composite_selective_signals|selective_strategy_name|phase_mmm' scripts/build_improvement_artifacts.py | head -n 160
python3 scripts/phase_mmm_composite_selective_signals_rebuild.py
BUILD_VERSION_NAMES=improved_phasemmm_recovery_confirmed_css_cap,improved_phasemmm_recovery_confirmed_css_filter,improved_phasemmm_conservative_css_polish SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py
```

## Files created / modified
- `scripts/build_improvement_artifacts.py`
- `scripts/phase_mmm_composite_selective_signals_rebuild.py`
- `data/research/phase_mmm_composite_selective_signals_rebuild/*`
- `data/05_layer3_portfolio_construction/portfolio_version_*_improved_phasemmm_*.csv`
- `docs/research/2026-04-27_phase_mmm_composite_selective_signals_rebuild_report.md`
- `docs/research/project_journey.md`

## CSS diagnosis
| candidate | state | ann_return | sharpe | avg_BIL | avg_SPY | avg_DBA | avg_TLT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | 0.034451 | 0.447886 | 0.000000 | 0.030508 | 0.032203 | 0.066949 |
| improved_phaseggg_confirmed_only_robust_offense | neutral_mixed | 0.096143 | 1.132803 | 0.023327 | 0.032454 | 0.014706 | 0.140467 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | -0.021096 | -0.283127 | 0.000000 | 0.005682 | 0.045455 | 0.181818 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 0.018832 | 0.328658 | 0.000000 | 0.010204 | 0.025510 | 0.142857 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 0.054889 | 0.450766 | 0.000000 | 0.007642 | 0.041485 | 0.149563 |

## Internal ETF findings
| state | ETF | avg_weight | ann_contribution_proxy |
| --- | --- | --- | --- |
| calm_trend | EWJ | 0.013559 | -0.007680 |
| calm_trend | VNQ | 0.125424 | -0.007305 |
| calm_trend | TLT | 0.066949 | -0.006448 |
| calm_trend | QQQ | 0.000000 | 0.000000 |
| calm_trend | IWM | 0.000000 | 0.000000 |
| calm_trend | BIL | 0.000000 | 0.000000 |
| calm_trend | SPY | 0.030508 | 0.001926 |
| calm_trend | PDBC | 0.031356 | 0.002603 |
| calm_trend | EFA | 0.066949 | 0.004165 |
| calm_trend | VEA | 0.061864 | 0.004180 |
| calm_trend | VWO | 0.016102 | 0.005694 |
| calm_trend | HYG | 0.210169 | 0.008111 |
| calm_trend | DBA | 0.032203 | 0.010121 |
| calm_trend | LQD | 0.239831 | 0.010317 |
| calm_trend | GLD | 0.105085 | 0.016511 |
| neutral_mixed | SPY | 0.032454 | -0.000003 |
| neutral_mixed | IWM | 0.000000 | 0.000000 |
| neutral_mixed | BIL | 0.023327 | 0.000000 |
| ... |  |  |  |

## Candidate metrics
| name | ann_return | sharpe | max_drawdown | cvar_5 | turnover_ratio_vs_production | avg_BIL | avg_SPY |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasemmm_recovery_confirmed_css_cap | 0.068049 | 0.921569 | -0.119196 | -0.024749 | 1.032436 | 0.264536 | 0.059092 |
| improved_phasemmm_recovery_confirmed_css_filter | 0.071298 | 0.942044 | -0.117209 | -0.025382 | 1.108893 | 0.266700 | 0.060437 |
| improved_phasemmm_conservative_css_polish | 0.068049 | 0.921569 | -0.119196 | -0.024749 | 1.032436 | 0.264536 | 0.059092 |
| improved_phaseggg_confirmed_only_robust_offense | 0.071381 | 0.943460 | -0.117739 | -0.025377 | 1.099763 | 0.266580 | 0.060257 |
| improved_phase2b_regime_confidence_boost | 0.068923 | 0.895263 | -0.139754 | -0.026181 | 1.000000 | 0.283918 | 0.070812 |
| improved_phase2b_combo_abc | 0.068584 | 0.894473 | -0.136741 | -0.026085 | 1.006087 | 0.285552 | 0.070757 |

## CSS before / after
| candidate | state | ann_return | sharpe | avg_DBA | avg_TLT |
| --- | --- | --- | --- | --- | --- |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | -0.021096 | -0.283127 | 0.045455 | 0.181818 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 0.018832 | 0.328658 | 0.025510 | 0.142857 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 0.054889 | 0.450766 | 0.041485 | 0.149563 |
| improved_phasemmm_recovery_confirmed_css_filter | recovery_confirmed | -0.002281 | 0.006294 | 0.000000 | 0.000000 |
| improved_phasemmm_recovery_confirmed_css_filter | recovery_fragile | 0.018299 | 0.320795 | 0.025510 | 0.142857 |
| improved_phasemmm_recovery_confirmed_css_filter | stressed_panic | 0.054889 | 0.450766 | 0.041485 | 0.149563 |

## Selection table
| candidate | decision | delta_sharpe_vs_ggg1 | delta_ann_return_vs_ggg1 | turnover_under_cap | recovery_confirmed_improved | recovery_fragile_not_worse | stressed_panic_preserved | hidden_beta_not_higher |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasemmm_recovery_confirmed_css_cap | REJECT | -0.021891 | -0.003332 | True | False | False | True | True |
| improved_phasemmm_recovery_confirmed_css_filter | REJECT | -0.001417 | -0.000083 | False | True | True | True | True |
| improved_phasemmm_conservative_css_polish | REJECT | -0.021891 | -0.003332 | True | False | False | True | True |

## Candidate diagnostics
| candidate | doubled_cost_sharpe | one_week_delay_sharpe |
| --- | --- | --- |
| improved_phasemmm_recovery_confirmed_css_cap | 0.881020 | 0.642829 |
| improved_phasemmm_recovery_confirmed_css_filter | 0.899485 | 0.656631 |
| improved_phasemmm_conservative_css_polish | 0.881020 | 0.642829 |

## Audit results
- research_committee: skipped: no candidate qualified
- realism: skipped
- allocator: skipped

## Final decision
**KEEP_GGG1_AS_PRODUCTION_CANDIDATE**

Best candidate: `improved_phasemmm_recovery_confirmed_css_filter` (`REJECT`).

Reason: CSS rebuild candidates failed or only marginally helped; keep GGG1.

CSS rebuild should continue: **False**.

## Exact prompt outline for the next phase
Keep GGG1 as production candidate and move to packaging/human review; do not force more Layer 2A rebuilds unless a new diagnostic identifies a larger issue.
