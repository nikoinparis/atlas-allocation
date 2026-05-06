# Phase JJJ1 — Constraint, Overlay, and Lookthrough Drag Isolation

Date: 2026-04-27
Author: research stream

## Commands executed
```
sed -n '1,220p' docs/research/2026-04-27_phase_jjj0_foundation_diagnostic_audit_report.md
ls -1 data/research/phase_jjj0_foundation_diagnostic_audit | sort
rg -n "SAVE_CONSTRAINT_DIAGNOSTICS|constraint_diag|target_vol_multiplier|target_vol|save_checkpoint|checkpoint_stage|post_overlay_pre_lookthrough|final_sleeve_weights|final_etf_weights|lookthrough" scripts/build_improvement_artifacts.py | head -160
sed -n '4680,5035p' scripts/build_improvement_artifacts.py
python3 scripts/phase_jjj1_constraint_drag_isolation.py
```

## Files created / modified
- `scripts/phase_jjj1_constraint_drag_isolation.py`
- `data/research/phase_jjj1_constraint_drag_isolation/*.csv`
- `data/research/phase_jjj1_constraint_drag_isolation/raw/*.csv`
- `docs/research/2026-04-27_phase_jjj1_constraint_drag_isolation_report.md`
- `docs/research/project_journey.md`

## Instrumentation added or reused
- Reused existing allocator checkpoints for all three core versions.
- Reused existing `portfolio_version_diagnostics_timeseries.csv` for target-vol/regime binding diagnostics.
- Derived raw overlay, cap-proxy, turnover, and per-sleeve lookthrough instrumentation from saved artifacts.
- Raw instrumentation files: `['cap_diagnostics_proxy_by_sleeve_state.csv', 'component_missing_instrumentation.csv', 'lookthrough_diagnostics_by_date_sleeve_etf.csv', 'lookthrough_missing_sleeve_positions.csv', 'overlay_diagnostics_by_state.csv', 'target_vol_diagnostics_by_date.csv', 'turnover_diagnostics_by_date.csv']`.
- Did not edit strategy logic or production pins.

## Stage drag attribution
- Drag flag counts: `{'NEUTRAL': 47, 'ACCIDENTAL_GOOD_STATE_DRAG': 15, 'NEEDS_REVIEW': 7, 'STRESS_PROTECTION': 6}`.
- Overlay and final lookthrough stages are the dominant drag points.

## Lookthrough drag by sleeve / ETF
- Per-sleeve ETF contribution is available for sleeves with saved `strategy_positions_*` files.
- GGG1 component sleeves lack saved position panels, so their contribution is documented as missing rather than guessed.

## Target-vol / overlay / cap binding findings
- Target-vol rows: 15. Favorable-state target-vol binding rows: 1.
- Overlay rows: 15. Favorable-state overlay cash drag rows: 9.
- Cap diagnostics are proxy-only because explicit pre/post cap weights are not persisted.

## Turnover boundary findings
- Turnover diagnostics use final ETF weekly L1 turnover and return-file turnover. Proposed/smoothed/executed/deadband traces are not persisted.

## Component purity findings
- Component role flags: `{'INSUFFICIENT_DATA': 3}`.
- `composite_regime_offense_component` and `composite_regime_defense_component` remain insufficiently instrumented.

## Top bottlenecks
- **HIGH** — Favorable-state lookthrough offense drag: improved_phase2b_regime_confidence_boost recovery_fragile -15.64% Recommendation: Fix or instrument sleeve-to-ETF lookthrough before advanced allocator.
- **HIGH** — GGG1 component purity still unproven: composite_regime_offense_component, composite_regime_defense_component, composite_regime_cash_component Recommendation: Persist component returns and ETF positions.
- **MEDIUM** — Overlay cash added in favorable states: 9 version/state rows Recommendation: Separate intentional recovery guardrail from accidental good-state cash.
- **MEDIUM** — Target-vol binds in favorable states: 1 rows Recommendation: Review target-vol before allocator changes.
- **LOW** — Cap proxy boundary observed: 42 rows Recommendation: Add explicit cap pre/post instrumentation if this becomes material.
- **LOW** — Turnover near boundary: 3 state rows Recommendation: Monitor GGG1 turnover in any follow-up.
- **INFO** — Next action: FIX_LOOKTHROUGH_DRAG Recommendation: Final sleeve-to-ETF translation removes offense in favorable states, and component lookthrough panels are missing for GGG1.

## Intended protection vs accidental bottleneck
- `STRESS_PROTECTION` rows are treated as intended unless they also remove offense in favorable states.
- Favorable-state overlay cash additions and final lookthrough offense losses are treated as accidental bottlenecks needing review.

## Final next-action recommendation
**FIX_LOOKTHROUGH_DRAG**

Reason: Final sleeve-to-ETF translation removes offense in favorable states, and component lookthrough panels are missing for GGG1.

Safe to proceed to adaptive risk-contribution allocation: **False**.

## Exact prompt outline for the next phase
Implement Phase JJJ2 as a diagnostic-only lookthrough/component instrumentation pass. Do not create candidates. Persist GGG1 composite component return and ETF-position panels, build per-sleeve ETF contribution tables including components, and then decide whether to repair lookthrough drag or proceed to adaptive risk contribution.
