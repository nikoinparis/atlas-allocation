# Improved Frontier Phase5 Dashboard Exposure Report

Date: 2026-05-22

## Final Status

**Dashboard exposure completed; ready for human review.**

The live production pin was not flipped. The compact dashboard bundle now exposes
`improved_frontier_phase5_fragility_guard` as the pending production candidate.

## Commands Run

```bash
pwd
git status
git branch
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py
.venv/bin/python scripts/run_deployment_rule_harness.py
rg -n "dashboard-data|dashboard bundle|compact bundle|production_candidate_registry|production_candidate_summary|Vercel|vercel|public/|bundle" scripts data docs package.json Makefile pyproject.toml README* 2>/dev/null
rg --files scripts | rg "dashboard|bundle|candidate|vercel|export|public|production"
find public -maxdepth 2 -type f | sort
sed -n '80,155p' README.md
cat package.json
sed -n '1,260p' scripts/build_release_dashboard_bundle.py
sed -n '1,180p' scripts/build-dashboard-data.mjs
sed -n '1,140p' docs/research/2026-05-07_release_validation_report.md
sed -n '260,620p' scripts/build_release_dashboard_bundle.py
sed -n '1,620p' scripts/phase_iii_packaging_review.py
find . -maxdepth 2 -type f \( -name '*dashboard*' -o -name '*smoke*' -o -name '*integrity*' \) | sort
rg -n "production-candidate-dashboard-bundle|dashboard-summary|dashboard-timeseries|dashboard-data|versionReturns|production_candidate" src public package.json scripts
find src -type f -maxdepth 4 | sort
sed -n '1,220p' src/lib/compact-dashboard.ts
sed -n '220,380p' src/lib/compact-dashboard.ts
sed -n '120,170p' src/components/executive-summary.tsx
sed -n '760,810p' src/components/dashboard-shell.tsx
.venv/bin/python -m py_compile scripts/build_production_candidate_dashboard_bundle.py scripts/phase_iii_packaging_review.py
npm run refresh:data
.venv/bin/python scripts/phase_iii_packaging_review.py
.venv/bin/python - <<'PY'
# dashboard bundle JSON / candidate visibility integrity check
PY
npm run typecheck
npm run build
git diff -- public src
git diff -- data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv
git status --short
```

## Dashboard Generation Command Used

The established repo command is `npm run refresh:data`, which delegates to
`python3 scripts/phase_iii_packaging_review.py`.

Inspection showed that `scripts/phase_iii_packaging_review.py` was still
hardcoded to the old GGG candidate. I added a guard so that when the current
registry candidate differs from the old Phase III candidate, the established
command delegates to the current-candidate compact generator:

```bash
.venv/bin/python scripts/phase_iii_packaging_review.py
```

`npm run refresh:data` was attempted first and failed because system `python3`
does not have `pandas` installed. The same established script succeeded under
the repo virtual environment.

## Files Created

- `scripts/build_production_candidate_dashboard_bundle.py`
- `docs/research/improved_frontier_phase5_dashboard_exposure_report.md`

## Files Modified

- `scripts/phase_iii_packaging_review.py`
- `src/lib/compact-dashboard.ts`
- `src/components/dashboard-shell.tsx`
- `src/components/executive-summary.tsx`
- `public/production-candidate-dashboard-bundle.json`
- `public/dashboard-summary.json`
- `public/dashboard-timeseries.json`
- `public/dashboard-state-summary.json`
- `public/dashboard-exposures.json`

Pre-existing production-candidate registry and comparison files remain modified
from the prior named-artifact packaging step:

- `data/05_layer3_portfolio_construction/production_candidate_registry.json`
- `data/05_layer3_portfolio_construction/production_candidate_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_state_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_exposure_summary.csv`

## Public Dashboard Data

- `public/production-candidate-dashboard-bundle.json`: changed
- `public/dashboard-summary.json`: changed
- `public/dashboard-timeseries.json`: changed
- `public/dashboard-state-summary.json`: changed
- `public/dashboard-exposures.json`: changed
- `public/dashboard-data.json`: unchanged
- `public/dashboard-data-detail-returns.json`: unchanged
- `public/dashboard-data-detail-weights.json`: unchanged
- `public/dashboard-data-detail-allocation.json`: unchanged

The forbidden monolithic `public/dashboard-data.json` was not regenerated.

## Pin Safety

- `current_production_pin`: `improved_phase2b_regime_confidence_boost`
- `official_shadow_pin`: `improved_phase2b_combo_abc`
- `production_candidate`: `improved_frontier_phase5_fragility_guard`
- `prior_production_candidate`: `improved_phaseggg_confirmed_only_robust_offense`

The live production pin and shadow pin did not change.

## Candidate Visibility

Confirmed in `public/production-candidate-dashboard-bundle.json`:

- candidate appears in `summary`
- candidate appears in `versionReturns`
- candidate appears in `versionWeights`
- candidate appears in `state_summary`
- bundle registry points `production_candidate` to `improved_frontier_phase5_fragility_guard`

The compact dashboard source constants/copy were updated from GGG to
`improved_frontier_phase5_fragility_guard` so the dashboard interprets the
bundle's pending production candidate correctly.

## Smoke Tests

- `.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py`: PASS
  - no-modifier exact match: true
  - max net-return error: `2.116e-16`
  - return correlation: `1.0000000000`
- `.venv/bin/python scripts/run_deployment_rule_harness.py`: PASS
  - architecture-valid rules: 7
- dashboard JSON integrity check: PASS
- `npm run typecheck`: PASS
- `npm run build`: PASS
  - compiled successfully
  - static pages generated: 3/3

## Warnings

- `npm run refresh:data` failed under system `python3` because `pandas` is not
  installed there. Use `.venv/bin/python scripts/phase_iii_packaging_review.py`
  for this repo unless the package script is later updated to call the venv.
- `scripts/build_release_dashboard_bundle.py` is stale for this workflow; it is
  tied to the older Phase 7 release bundle and was not used.
- `scripts/build-dashboard-data.mjs` targets the old large dashboard-data path;
  it was inspected but not run.

## Next Step

Human review should inspect the dashboard with the compact bundle visible. If
approved, run a separate explicit production-pin update sprint that changes
`current_production_pin`; this sprint intentionally did not do that.
