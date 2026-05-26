# Dashboard Research Journey Section Update

**Date:** 2026-05-25  
**Scope:** UI/content cleanup only — no portfolio logic, data, or production pins changed.

---

## Root Cause of the Old n/a Section

The compact bundle (`public/production-candidate-dashboard-bundle.json`) does not include:
- Live market-state history
- Upside/downside capture metrics (`upside_capture_positive_weeks`, `recovery_week_capture`, `calm_week_capture`, `downside_capture_negative_weeks`)
- Subset, overlay, and state-tilt metadata fields

The old dashboard code read these fields and rendered them via `titleCase()` and `metricValue()`, which both return `"n/a"` for missing values. The `compact-dashboard.ts` placeholder also hardcoded `market_state: "phase_iii_review"`, which `titleCase()` rendered as "Phase Iii Review" in the overview cards.

---

## Files Changed

| File | What Changed |
|------|-------------|
| `src/components/executive-summary.tsx` | Replaced n/a Allocator/Subset/Overlay/State-tilt lines with descriptive static strategy-design text |
| `src/components/dashboard-shell.tsx` | Multiple targeted fixes (see below) |
| `src/lib/compact-dashboard.ts` | Updated `market_state` placeholder from `"phase_iii_review"` to `"frontier_phase5_production"` |

---

## Section Replaced

**Old (broken) overview panel — "Immediate visible summary":**
- 12 MetricCards including "Current Market State" (showed "Phase Iii Review"), "Market State", "Off / Def / Cash", "Current SPY", "Current BIL"
- 4 overview cards: "Best by Sharpe", "Most Robust", "Drawdown Control", and "Current Market State" (showed "Phase Iii Review")
- These all rendered n/a or "Phase Iii Review" because the compact bundle does not carry live state history

**New panel — "Research Journey: How Phase 5 Became Production":**
- Wide summary card: "Production Strategy: Frontier Phase5 Fragility Guard" with narrative text
- 4 layer summary cards: Layer 1 Signal Foundation, Layer 2 Market State Quality, Layer 3 Portfolio Construction, Phase 5 Winning Guardrail
- 4 validation cards: "8/8 Phase D Gates", "84% Bootstrap Support", "73% Rolling Win Rate", "Stressed-Panic Defense Preserved" — all static from the final promotion report
- 4 before/after metric cards: Sharpe 0.884→0.948, Max Drawdown -13.98%→-11.60%, Holdout Sharpe 2.100→2.179, Production Pin — all static from the final evaluation

---

## Additional n/a Fixes in dashboard-shell.tsx

| Location | Old | New |
|----------|-----|-----|
| Overview sidebar cards (4 cards) | Current Market State / Best by Sharpe / Most Robust / Drawdown Control | Phase D Gates 8/8 / Bootstrap Support 84% / Rolling Win Rate 73% / Stressed-Panic Defense Preserved |
| `improvedItems[1]` (What improved panel) | Recovery capture n/a, calm capture n/a | Holdout Sharpe (2.100→2.179), BIL improvement |
| `improvedItems[2]` (What improved panel) | Redundant avg_cash = avg_bil, SPY "rose" (wrong — it fell) | CVaR and volatility comparison |
| `improvedItems[3]` (What improved panel) | Production score flag, avg_effective_n n/a | Max drawdown improvement + Phase D gate count |
| `gotWorseItems[0]` (What got worse panel) | "Max drawdown deepened" (factually wrong — it improved) | Turnover increased 5.6%→6.7% |
| `gotWorseItems[1]` (What got worse panel) | CVaR "worsened" (incorrect — it improved) | SPY exposure fell 7.1%→5.9% |
| `gotWorseItems[2]` (What got worse panel) | Downside capture n/a | Guardrail caveat (risk of missing crowded rallies) |
| `overallInterpretation` | Old candidate-under-review language | Accurate promoted-strategy summary |
| `MetricCard "Recovery Capture Delta"` (change-review section) | n/a (recovery_week_capture not in bundle) | Holdout Sharpe Delta (+0.08) |
| `Panel "Upside and downside capture"` (improvement-lab section) | All capture columns n/a | Renamed "Full-period vs holdout comparison"; columns changed to `sharpe, holdout_sharpe, max_drawdown, avg_bil_weight, avg_spy_weight` |

---

## executive-summary.tsx Fix

Replaced the two lines that showed:
```
Allocator: Improved Frontier Phase5 Fragility Guard · Subset: N/a
Overlay: N/a · State tilt: N/a
```

With descriptive static text:
```
Design: HRP wrapper · Phase 1 R2A offense scaling + Phase 4 fragility guardrail
Stressed-panic defense preserved · Phase 4 crowding check gates the offense boost
```

---

## Metrics: Static vs Bundle-Driven

| Source | Values |
|--------|--------|
| Static (from final promotion report) | Phase D Gates 8/8, Bootstrap Support 84%, Rolling Win Rate 73%, Sharpe 0.884→0.948, Max Drawdown -13.98%→-11.60%, Holdout Sharpe 2.100→2.179 |
| Bundle-driven (from compact bundle) | `full_sharpe`, `full_max_drawdown`, `full_cvar_5`, `holdout_sharpe`, `avg_BIL` / `avg_bil_weight`, `avg_SPY` / `avg_spy_weight`, `avg_turnover` |
| Removed (not in bundle) | `upside_capture_positive_weeks`, `downside_capture_negative_weeks`, `recovery_week_capture`, `calm_week_capture`, `subset_name`, `overlay_variant`, `state_tilt` |

---

## Build / Typecheck Results

```
npm run typecheck  →  no errors
npm run build      →  ✓ Compiled successfully in 1771ms
                       ✓ Generating static pages (3/3)
```

---

## Production Pin Status

**Not changed.** Production pin remains:
- **Current production:** `improved_frontier_phase5_fragility_guard`
- **Prior production / rollback:** `improved_phase2b_regime_confidence_boost`
- **Official shadow:** `improved_phase2b_combo_abc`

No portfolio logic, data calculations, or production registry entries were modified.

---

## Ready to Commit/Push?

Yes. All src changes are UI/content only:
- No data files modified
- No `public/dashboard-data.json` generated or committed
- No production logic or pin changes
- Build and typecheck both pass clean
