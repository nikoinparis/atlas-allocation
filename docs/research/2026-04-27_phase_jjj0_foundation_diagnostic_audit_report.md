# Phase JJJ0 — Foundation Diagnostic Audit

Date: 2026-04-27
Author: research stream

## Commands executed
```
sed -n '1,180p' docs/research/2026-04-27_phase_iii_production_candidate_review_report.md
sed -n '1,180p' docs/research/2026-04-27_phase_ggg_state_conditional_composite_offense_report.md
tail -80 docs/research/project_journey.md
rg -n "composite_regime|phaseggg|VERSION|version_specs|internal_redeploy|sleeve|market_state|allocator_checkpoint|checkpoint|target_vol|overlay|lookthrough|deadband|turnover|cap" scripts/build_improvement_artifacts.py | head -160
sed -n '1,220p' scripts/phase_ggg_state_conditional_composite_offense.py
rg --files data/05_layer3_portfolio_construction | rg 'portfolio_version_(returns|weights|sleeve_weights)_(improved_phaseggg_confirmed_only_robust_offense|improved_phase2b_regime_confidence_boost|improved_phase2b_combo_abc)\.csv$|phase_ggg|phase_iii|production_candidate' | sort
rg --files data/03_layer2a_strategy_logic | head -120
rg --files data/04_layer2b_risk_regime_engine | head -120
rg --files data/research/allocator_checkpoints | head -120
python3 scripts/phase_jjj0_foundation_diagnostic_audit.py
```

## Files created / modified
- `scripts/phase_jjj0_foundation_diagnostic_audit.py`
- `data/research/phase_jjj0_foundation_diagnostic_audit/*.csv`
- `docs/research/2026-04-27_phase_jjj0_foundation_diagnostic_audit_report.md`
- `docs/research/project_journey.md`

## Artifact inventory
- Inventory rows: 1221.
- Core production/candidate/shadow return, ETF weight, and sleeve weight files: present.
- Allocator checkpoints for raw HRP, post-state-tilt, post-layer3-expression, post-overlay/pre-lookthrough, final sleeve, and final ETF: present for all three core versions.

## Sleeve purity findings
- Sleeve role flag counts: `{'HIDDEN_DEFENSE_RISK': 3, 'INSUFFICIENT_DATA': 2, 'CLEAN_ROLE': 1, 'NEEDS_DECOMPOSITION_REVIEW': 1, 'HIDDEN_BETA_RISK': 1}`.
- `composite_regime_conditioned` remains the known mixed sleeve in production/shadow; GGG1 removes it from the candidate stack.
- GGG1 component sleeves do not have persisted component-level return/position files, so their direct purity audit is marked as missing instrumentation rather than inferred.

## State budget alignment findings
- State mismatch flag counts: `{'STATE_MAPPING_OK': 10, 'OFFENSE_TOO_LOW_FOR_STATE': 5}`.
- The audit compares state sleeve weights against available sleeve return/Sharpe ranks. Component sleeves without return panels are marked `INSUFFICIENT_DATA` in rank files.

## Risk contribution findings
- ETF-level risk contribution is available from final ETF weights and weekly ETF returns.
- Sleeve-level risk contribution is approximate for sleeves with saved return files; component sleeve contribution is limited by missing component return panels.

## Constraint / overlay / lookthrough drag findings
- Stage-drag flag counts: `{'CONSTRAINTS_CLEAN': 50, 'LOOKTHROUGH_DRAG': 13, 'OVERLAY_CASH_DRAG': 12}`.
- Target-vol binding, exact cap binding, deadband, and per-sleeve ETF lookthrough cannot be fully audited from current saved artifacts.

## GGG1 sanity check
- Readiness category: `NEEDS_MORE_VALIDATION`.
- Validation gap: component-level GGG1 offense/defense return and position panels are not persisted.
- GGG1 still improves Sharpe/drawdown versus production and lowers SPY/BIL exposure; production and shadow pins were not changed.

## Top 10 bottlenecks
- **HIGH** — Component purity cannot be proven: composite_regime_defense_component, composite_regime_offense_component Recommendation: Persist component-level returns and ETF positions.
- **MEDIUM** — Overlay cash drag still appears in stage deltas: 12 state/stage rows Recommendation: Inspect overlay cash deltas before changing allocator complexity.
- **MEDIUM** — State budget mismatch flags exist: 5 rows Recommendation: Review state-level weights versus state sleeve performance.
- **MEDIUM** — GGG1 cleanness limited by missing component panels: Cannot directly audit offense/defense component purity. Recommendation: Add instrumentation, do not infer purity from final ETF weights alone.
- **LOW** — Turnover remains near policy boundary: Phase III turnover ratio is just under 1.10x. Recommendation: Monitor during packaging/shadow tracking.
- **INFO** — Production pin unchanged: improved_phase2b_regime_confidence_boost Recommendation: Rollback path remains intact.

## Missing instrumentation
- `target_vol` / `all` / `target_vol_multiplier timeseries`: Persist pre/post target-vol multipliers and binding booleans by date/state.
- `lookthrough` / `all` / `per-sleeve final ETF contribution table`: Persist sleeve x ETF lookthrough contributions to isolate sleeve-level drag.
- `turnover` / `all` / `trade deadband / rerisk speed trace`: Persist proposed weights, smoothed weights, executed weights, and deadband decisions.
- `component_sleeves` / `improved_phaseggg_confirmed_only_robust_offense` / `component return/position panels for composite_regime_offense_component and defense_component`: Save component-level returns and ETF positions from the decomposition builder.

## Final next-frontier recommendation
**FIX_CONSTRAINT_DRAG_FIRST**

Reason: Stage diagnostics show repeated overlay/lookthrough bucket drag across states.

Safe to proceed to adaptive risk-contribution allocation: **False**.

## Exact prompt outline for the next phase
Implement Phase JJJ1 as a diagnostic-only constraint, overlay, and lookthrough drag isolation pass. Do not create strategy variants or change production pins. Add or use instrumentation for target-vol multipliers, overlay cash deltas, cap binding, deadband/rerisk traces, and per-sleeve ETF lookthrough contributions. Decide whether the observed cash/offense drag is an intended stressed-state guardrail or an accidental good-state bottleneck before testing adaptive risk contribution.
