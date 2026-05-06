# Phase JJJ3 — Targeted Lookthrough Repair

Date: 2026-04-27
Author: research stream

## Commands executed
```
sed -n '1,180p' docs/research/2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md
python3 - <<'PY' ... inspect JJJ2 drag summaries ...
sed -n '360,430p' scripts/build_improvement_artifacts.py
sed -n '1020,1225p' scripts/build_improvement_artifacts.py
sed -n '9685,9745p' scripts/build_improvement_artifacts.py
python3 scripts/phase_jjj3_targeted_lookthrough_repair.py
BUILD_VERSION_NAMES=improved_phasejjj3_targeted_lookthrough_repair SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py
```

## Files created / modified
- `scripts/build_improvement_artifacts.py`
- `scripts/phase_jjj3_targeted_lookthrough_repair.py`
- `data/research/phase_jjj3_targeted_lookthrough_repair/*.csv`
- `docs/research/2026-04-27_phase_jjj3_targeted_lookthrough_repair_report.md`
- `docs/research/project_journey.md`

## Top drag path identified
- Version: `improved_phaseggg_confirmed_only_robust_offense`
- State: `calm_trend`
- Sleeve: `composite_selective_signals`
- Drag: 0.1391
- Classification: `ACCIDENTAL_GOOD_STATE_DRAG`

## Candidate
- Created: `improved_phasejjj3_targeted_lookthrough_repair`
- Logic: GGG1 plus only a calm_trend cap on `composite_selective_signals` share of the offense bucket at 30%; excess stays within offense-family sleeves: 70% to `composite_regime_offense_component`, 30% to `cta_trend_long_only`.

## Metrics
| name | ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_turnover | avg_BIL | avg_SPY | turnover_ratio_vs_production |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phasejjj3_targeted_lookthrough_repair | 0.068049 | 0.074533 | 0.913005 | -0.119196 | 0.570900 | -0.024749 | 0.116002 | 0.264536 | 0.059092 | 1.032436 |
| improved_phaseggg_confirmed_only_robust_offense | 0.071381 | 0.076248 | 0.936168 | -0.117739 | 0.606267 | -0.025377 | 0.123566 | 0.266580 | 0.060257 | 1.099763 |
| improved_phase2b_regime_confidence_boost | 0.068923 | 0.077931 | 0.884416 | -0.139754 | 0.493176 | -0.026181 | 0.112357 | 0.283918 | 0.070812 | 1.000000 |
| improved_phase2b_combo_abc | 0.068584 | 0.077616 | 0.883625 | -0.136741 | 0.501559 | -0.026085 | 0.113041 | 0.285552 | 0.070757 | 1.006087 |

## Targeted drag before vs after
| version_before_ggg1 | market_state | sleeve | intended_role_before_ggg1 | avg_sleeve_weight_before_ggg1 | offense_contribution_before_ggg1 | defense_contribution_before_ggg1 | cash_contribution_before_ggg1 | commodity_contribution_before_ggg1 | SPY_contribution_before_ggg1 | BIL_contribution_before_ggg1 | lookthrough_offense_drag_before_ggg1 | version_after_jjj3 | intended_role_after_jjj3 | avg_sleeve_weight_after_jjj3 | offense_contribution_after_jjj3 | defense_contribution_after_jjj3 | cash_contribution_after_jjj3 | commodity_contribution_after_jjj3 | SPY_contribution_after_jjj3 | BIL_contribution_after_jjj3 | lookthrough_offense_drag_after_jjj3 | delta_lookthrough_offense_drag | targeted_drag_reduced |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | composite_selective_signals | offense | 0.202149 | 0.066865 | 0.102835 | 0.000000 | 0.032449 | 0.007544 | 0.000000 | 0.135284 | improved_phasejjj3_targeted_lookthrough_repair | offense | 0.215548 | 0.070260 | 0.110104 | 0.000000 | 0.035185 | 0.007884 | 0.000000 | 0.145288 | 0.010004 | False |

## State guardrails
| candidate | state | n_weeks | ann_return | sharpe | vol_wkly | mean_wkly |
| --- | --- | --- | --- | --- | --- | --- |
| improved_phasejjj3_targeted_lookthrough_repair | calm_trend | 295.000000 | 0.043431 | 0.546484 | 0.011021 | 0.000879 |
| improved_phasejjj3_targeted_lookthrough_repair | neutral_mixed | 493.000000 | 0.105915 | 1.437781 | 0.010216 | 0.001990 |
| improved_phasejjj3_targeted_lookthrough_repair | recovery_confirmed | 44.000000 | 0.015093 | 0.217856 | 0.009607 | 0.000333 |
| improved_phasejjj3_targeted_lookthrough_repair | recovery_fragile | 49.000000 | 0.045894 | 0.790668 | 0.008049 | 0.000895 |
| improved_phasejjj3_targeted_lookthrough_repair | stressed_panic | 229.000000 | 0.035750 | 0.483910 | 0.010245 | 0.000728 |
| improved_phaseggg_confirmed_only_robust_offense | calm_trend | 295.000000 | 0.040851 | 0.513625 | 0.011029 | 0.000831 |
| improved_phaseggg_confirmed_only_robust_offense | neutral_mixed | 493.000000 | 0.112112 | 1.461561 | 0.010637 | 0.002102 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_confirmed | 44.000000 | 0.025705 | 0.344267 | 0.010354 | 0.000541 |
| improved_phaseggg_confirmed_only_robust_offense | recovery_fragile | 49.000000 | 0.066671 | 1.142121 | 0.008095 | 0.001274 |
| improved_phaseggg_confirmed_only_robust_offense | stressed_panic | 229.000000 | 0.035803 | 0.480687 | 0.010329 | 0.000730 |
| improved_phase2b_regime_confidence_boost | calm_trend | 295.000000 | 0.035584 | 0.384275 | 0.012841 | 0.000755 |
| improved_phase2b_regime_confidence_boost | neutral_mixed | 493.000000 | 0.110433 | 1.462193 | 0.010473 | 0.002071 |
| improved_phase2b_regime_confidence_boost | recovery_confirmed | 44.000000 | 0.026147 | 0.384677 | 0.009426 | 0.000540 |
| improved_phase2b_regime_confidence_boost | recovery_fragile | 49.000000 | 0.069735 | 1.316840 | 0.007344 | 0.001324 |
| improved_phase2b_regime_confidence_boost | stressed_panic | 229.000000 | 0.033693 | 0.496727 | 0.009406 | 0.000682 |

## Hidden beta / cash / turnover
- See metrics table: avg SPY, avg BIL, and turnover ratio are included.

## Audit results
- research_committee: skipped: candidate rejected by selection rule
- realism: skipped
- allocator: skipped

## Final decision
**REJECT**

## Next action recommendation
**KEEP_GGG1_AND_PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION**

Reason: The one-path repair did not clear all selection gates; keep GGG1.

Safe to proceed to adaptive risk-contribution allocation: **True**.

## Exact prompt outline for the next phase
Proceed to a narrowly scoped adaptive risk-contribution allocator test using GGG1 as the base and JJJ diagnostics as constraints; do not promote JJJ3 unless human review wants a shadow-only diagnostic.
