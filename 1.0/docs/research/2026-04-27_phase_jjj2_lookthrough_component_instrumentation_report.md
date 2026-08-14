# Phase JJJ2 — Lookthrough Component Instrumentation

Date: 2026-04-27
Author: research stream

## Commands executed
```
sed -n '1,220p' docs/research/2026-04-27_phase_jjj1_constraint_drag_isolation_report.md
python3 - <<'PY' ... small JJJ1 summaries ...
rg -n "def build_state_conditional_decomposition_sleeve_panels|phaseggg_confirmed_robust|composite_regime_offense_component|composite_regime_defense_component|composite_regime_cash_component|build_decomposition|decomposition_sleeve" scripts/build_improvement_artifacts.py | head -180
sed -n '5960,6145p' scripts/build_improvement_artifacts.py
sed -n '6380,6460p' scripts/build_improvement_artifacts.py
python3 scripts/phase_jjj2_lookthrough_component_instrumentation.py
```

## Files created / modified
- `scripts/phase_jjj2_lookthrough_component_instrumentation.py`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/*.csv`
- `docs/research/2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md`
- `docs/research/project_journey.md`

## Component panels persisted
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_returns_improved_phaseggg_confirmed_only_robust_offense.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_positions_improved_phaseggg_confirmed_only_robust_offense.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_recipe_by_date_improved_phaseggg_confirmed_only_robust_offense.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_returns_improved_phaseeee_smoothed_near_exclude_dual.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_positions_improved_phaseeee_smoothed_near_exclude_dual.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_recipe_by_date_improved_phaseeee_smoothed_near_exclude_dual.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_returns_improved_phasefff_robust_composite_offense.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_positions_improved_phasefff_robust_composite_offense.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_recipe_by_date_improved_phasefff_robust_composite_offense.csv`
- `data/research/phase_jjj2_lookthrough_component_instrumentation/component_source_mapping.csv`

## Component purity findings
- Component role flags: `{'MIXED_BUT_ACCEPTABLE': 1, 'CLEAN_DEFENSE': 1, 'CLEAN_CASH': 1}`.
- GGG1 component panels now exist and were audited by market state.

## Per-sleeve ETF contribution findings
- Contribution rows: 73372. Zero contribution rows are omitted.
- Missing sleeve position rows: 0.

## Lookthrough drag source ranking
- Top favorable-state rows are saved in `phase_jjj2_favorable_state_drag_sources.csv`.

## Intended protection vs accidental drag
- Classification counts: `{'NEEDS_REVIEW': 48, 'ACCEPTABLE_DIVERSIFICATION': 20, 'ACCIDENTAL_GOOD_STATE_DRAG': 19, 'INTENDED_PROTECTION': 8}`.

## GGG1 component roles clean?
- Clean enough for diagnostics: `True`.

## GGG1 lookthrough cleaner than production?
- States cleaner than production on offense drag: 4/5.

## Top bottlenecks
- **HIGH** — GGG1 favorable-state offense drag remains: calm_trend / composite_selective_signals drag 13.91% Recommendation: Target the offending sleeve/ETF lookthrough path before advanced allocation.
- **INFO** — Component role purity improved: MIXED_BUT_ACCEPTABLE, CLEAN_DEFENSE, CLEAN_CASH Recommendation: No component redesign blocker found.
- **MEDIUM** — GGG1 lookthrough cleanliness vs production: 1 states not cleaner Recommendation: Use targeted repair if favorable-state drag is concentrated.
- **MEDIUM** — Accidental good-state drag sources: 19 Recommendation: Separate diversification from unintended offense loss.
- **INFO** — Next action: FIX_LOOKTHROUGH_DRAG_WITH_TARGETED_REPAIR Recommendation: Component roles are mostly clean, but a small set of favorable-state sleeve/ETF lookthrough paths causes material offense drag.

## Missing instrumentation remaining
- Exact cap pre/post, deadband/rerisk proposed-vs-smoothed-vs-executed traces remain outside this component/lookthrough pass.

## Final next-action recommendation
**FIX_LOOKTHROUGH_DRAG_WITH_TARGETED_REPAIR**

Reason: Component roles are mostly clean, but a small set of favorable-state sleeve/ETF lookthrough paths causes material offense drag.

Safe to proceed to adaptive risk-contribution allocation: **False**.

## Exact prompt outline for the next phase
Implement Phase JJJ3 as one targeted, diagnostic-gated lookthrough repair. Do not create a broad strategy search. Preserve GGG1 state/component logic, identify the top favorable-state sleeve/ETF drag path, make at most one tiny repair candidate, and require turnover, cost/delay, state guardrails, hidden-beta, and GGG1-vs-production checks.
