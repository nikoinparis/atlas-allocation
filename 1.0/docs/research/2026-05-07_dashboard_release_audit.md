# Dashboard Release Audit — 2026-05-07

**Purpose:** Confirm dashboard is public-ready with Phase 7 research state.

---

## Dashboard Architecture

- **Framework:** Next.js 15 (App Router, server-rendered)
- **Main data source:** `public/production-candidate-dashboard-bundle.json` (compact bundle)
- **Page entry:** `src/app/page.tsx` — imports bundle statically AND fetches at request time
- **Components:** `src/components/executive-summary.tsx` (server), `src/components/dashboard-shell.tsx` (client)
- **Data transform:** `src/lib/compact-dashboard.ts` — `compactBundleToDashboardData()`
- **Deployment:** Vercel (via `vercel.json`)

---

## Bundle Files Status

| File | Size | Tracked | Commit |
|---|---|---|---|
| `public/production-candidate-dashboard-bundle.json` | 1,370 KB | ✓ | ✓ Updated |
| `public/dashboard-summary.json` | 32 KB | ✓ | No change needed |
| `public/dashboard-timeseries.json` | 280 KB | ✓ | No change needed |
| `public/dashboard-exposures.json` | 12 KB | ✓ | No change needed |
| `public/dashboard-state-summary.json` | 8 KB | ✓ | No change needed |
| `public/dashboard-data.json` | 15 MB | NOT TRACKED | **FORBIDDEN** per CLAUDE.md — do not commit |
| `public/dashboard-data-detail-*.json` | 22–50 MB each | NOT TRACKED | Excluded — too large |

---

## Bundle Content After Update

**Summary versions (10 total):**

| Version | Role | Return | Sharpe | Max DD |
|---|---|---|---|---|
| `improved_phaseggg_confirmed_only_robust_offense` | production_candidate | 7.14% | 0.937 | -11.77% |
| `improved_phase2b_regime_confidence_boost` | production / rollback | 6.89% | 0.885 | -13.98% |
| `improved_phase2b_combo_abc` | official shadow | 6.86% | 0.884 | -13.67% |
| `improved_phase7_stretch_target` | aggressive_shadow_best_return | 7.88% | 0.926 | -15.28% |
| `improved_phase4b_refined_sector_20pct` | aggressive_shadow_best_risk_adjusted | 7.76% | 0.959 | -13.77% |
| `improved_phase6_continuous_aggression_score` | aggressive_shadow_best_classifier | 7.80% | 0.953 | -14.18% |
| `improved_phase7_expression_boost` | aggressive_shadow_best_sharpe_phase7 | 7.74% | 0.954 | -13.83% |
| `improved_phase7_max_sector_rerisk` | aggressive_shadow | 7.84% | 0.941 | -14.59% |
| `improved_phase7_larger_sector_calm` | aggressive_shadow | 7.83% | 0.939 | -14.59% |
| `improved_phase7_combined_offensive` | aggressive_shadow | 7.81% | 0.935 | -14.65% |

**Time series:** 1,110 return rows per version for all 10 versions
**State summary:** 40 rows (5 states × up to 8 versions)
**Registry:** 36 keys — updated to reflect Phase 7 completion

---

## Executive Summary Narrative (Updated)

The `researchRead` section in `src/components/executive-summary.tsx` was updated from the prior GGG1-focused narrative to now also communicate:
1. Seven phases of improvement from GGG1 (7.14%) to Phase 7 (7.88%, +0.74pp)
2. Best aggressive shadow: `improved_phase7_stretch_target` and `improved_phase4b_refined_sector_20pct`
3. Calm_trend bottleneck and PIT data future path
4. Phase 5A-Free is SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY

**Production governance:**
- Production pin unchanged: `improved_phase2b_regime_confidence_boost`
- GGG1 still the production candidate pending human review
- No auto-promotion

---

## TypeScript Changes for Bundle Compatibility

**`src/lib/compact-dashboard.ts`:**
- Added `InputRow` type (`Record<string, string|number|boolean|null|undefined>`) for bundle input rows
- Changed `summary`, `state_summary`, `exposure_summary`, `promotion_checklist` in `CompactBundle` from `AnyRow[]` to `InputRow[]`
- Added `normalizeInputRows()` helper that converts `undefined` → `null` before processing
- Updated `compactBundleToDashboardData()` to use `normalizeInputRows()` for those fields

**`src/types/dashboard.ts`:**
- Made `ReturnPoint.method` optional (`method?: string`) — new shadow returns don't have `method` field

---

## Build Result

```
✓ TypeScript type check: PASS
✓ Next.js build: PASS (compiled in 2.4s)
✓ Static pages generated: 3/3
```

Route: `/` — 146 KB page bundle, 249 KB first load JS

---

## Dashboard Content Verification

First page (server-rendered `ExecutiveSummary`) shows:
- Production Candidate: GGG1
- Annual Return, Vol, Sharpe, Max Drawdown for GGG1
- Current Market State
- Latest Research Takeaway (updated with Phase 7 context)
- How to read this page

Interactive dashboard shell shows:
- Version Lab with all 10 versions' returns
- State-by-state breakdown
- Allocator comparisons

**Dashboard is public-ready.** All information is backtest research; disclaimer included in registry.
