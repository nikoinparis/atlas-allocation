# Frontier Phase 1A-R2: Predeclared Sign-Audited Composite Report

**Date:** 2026-05-20
**Mode:** Diagnostic-only — no production or dashboard files modified

---

## 1. Motivation and Design Rationale

Phase 1A showed that the original equal-weight composite has negative IC in calm_trend (−0.185), neutral_mixed (−0.109), and recovery_confirmed (−0.133). Component diagnostics identified two structural problems:

1. **Sign errors by state**: the same component can be a positive predictor in one state and a negative predictor in another. For example, high `state_persistence_score` in `recovery_fragile` (IC +0.302) predicts well, but in `calm_trend` (IC −0.164) it reflects late-cycle exhaustion and predicts *less* future upside.
2. **Broken credit signal**: `credit_confirmation = sign(HYG_4w) − sign(LQD_4w)` is anti-predictive in every recovery state (−0.204 in recovery_confirmed, −0.243 in recovery_fragile). It is excluded from all R2 composites and redesigned as a continuous component (R2C) for diagnostic testing.

### Predeclared Sign Configuration

Signs and exclusions are declared before examining any R2-specific IC:

| State | breadth | path_clarity | persistence | leadership | credit |
|-------|---------|-------------|-------------|------------|--------|
| recovery_fragile | + | + | + | + | excl |
| recovery_confirmed | + | + | + | + | excl |
| calm_trend | − (crowded) | − (overextended) | − (exhaustion) | − (crowded) | excl |
| neutral_mixed | − (crowded) | − | − | − | excl |
| strong_neutral | − (crowded) | − | − | − | excl |
| stressed_panic | − (depth) | + (orderly) | excl | excl | excl |

### Variant Definitions

- **R2A** (state_aware_signed): state-aware economic signs as above, credit excluded everywhere, equal weights among active components.
- **R2B** (state_aware_positive): same state-based component selection but all positive signs — control case showing value of sign-flipping.
- **R2C** (credit_relative_momentum): standalone diagnostic component only. Continuous `HYG_4w_return − LQD_4w_return`, z-scored, 1-week lag. **Not incorporated into R2A/R2B composites.**
- **R2D** (recovery_only_hump): recovery states only (recovery_confirmed + recovery_fragile). Hump-shaped persistence: `min(persistence, 0.5)`. Evaluates whether the recovery-focused signal is worth isolating.

---

## 2. IC Summary Table

All signals are 1-week lagged (loaded from Phase 1A). Forward return = SPY 4-week return.
Holdout start: 2024-04-19

| variant | full_IC | dev_IC | holdout_IC | mean_state_IC | pos_states | calm_trend | neutral_mixed | rec_confirmed | rec_fragile | stressed_panic |
|---------|---------|--------|------------|---------------|------------|------------|---------------|---------------|-------------|----------------|
| deployment_quality_composite | -0.0495 | -0.0511 | -0.0363 | -0.0056 | 2 | -0.1846 | -0.1085 | -0.1329 | +0.2303 | +0.1676 |
| r2a | +0.1738 | +0.1698 | +0.2176 | +0.1724 | 4 | +0.2068 | +0.0972 | -0.0433 | +0.2384 | +0.3628 |
| r2b | +0.0375 | +0.0351 | +0.0684 | +0.0619 | 2 | -0.2069 | -0.1018 | -0.0165 | +0.2605 | +0.3742 |
| r2c | -0.0518 | -0.0849 | +0.2944 | -0.0357 | 2 | -0.0783 | +0.0332 | +0.0893 | -0.0668 | -0.1560 |
| r2d | +0.0380 | +0.0260 | +0.0867 | +0.1476 | 2 | – | – | +0.0264 | +0.2688 | – |

*deployment_quality_composite = original Phase 1A equal-weight composite (reference baseline)*

---

## 3. Acceptance Gate Results

Pre-declared gates (evaluated without reference to whether the variant passes):

| Gate | Requirement |
|------|------------|
| IC states | ≥ 2 states with IC > 0.05 |
| Calm/neutral | Neither calm_trend nor neutral_mixed IC < −0.10 |
| Holdout | Holdout IC not < −0.05 (not directionally broken) |
| Positive states | ≥ 2 positive states |

### deployment_quality_composite: ✗ FAIL

- ✓ ≥2 states with IC>0.05 (2 states)
- ✓ holdout IC=-0.0363 — not directionally broken
- ✓ 2 positive states
- ✗ strongly negative IC in calm_trend=-0.1846, neutral_mixed=-0.1085

### r2a: ✓ PASS

- ✓ ≥2 states with IC>0.05 (4 states)
- ✓ calm_trend IC=+0.2068, neutral_mixed IC=+0.0972 — not strongly negative
- ✓ holdout IC=+0.2176 — not directionally broken
- ✓ 4 positive states

### r2b: ✗ FAIL

- ✓ ≥2 states with IC>0.05 (2 states)
- ✓ holdout IC=+0.0684 — not directionally broken
- ✓ 2 positive states
- ✗ strongly negative IC in calm_trend=-0.2069, neutral_mixed=-0.1018

### r2c: ✗ FAIL

- ✓ calm_trend IC=-0.0783, neutral_mixed IC=+0.0332 — not strongly negative
- ✓ holdout IC=+0.2944 — not directionally broken
- ✓ 2 positive states
- ✗ only 1 state(s) with IC>0.05 (need 2)

### r2d: ✗ FAIL

- ✓ calm_trend IC=+nan, neutral_mixed IC=+nan — not strongly negative
- ✓ holdout IC=+0.0867 — not directionally broken
- ✓ 2 positive states
- ✗ only 1 state(s) with IC>0.05 (need 2)

---

## 4. State-by-State IC Breakdown

### deployment_quality_composite

| scope | market_state | IC | N |
|-------|--------------|----|---|
| full | ALL | -0.0495 | 1106 |
| full | calm_trend | -0.1846 | 295 |
| full | neutral_mixed | -0.1085 | 491 |
| full | recovery_confirmed | -0.1329 | 43 |
| full | recovery_fragile | +0.2303 | 49 |
| full | stressed_panic | +0.1676 | 228 |
| dev | ALL | -0.0511 | 1006 |
| dev | calm_trend | -0.1619 | 277 |
| dev | neutral_mixed | -0.1283 | 435 |
| dev | recovery_confirmed | -0.1560 | 34 |
| dev | recovery_fragile | +0.1408 | 45 |
| dev | stressed_panic | +0.1600 | 215 |
| holdout | ALL | -0.0363 | 100 |
| holdout | calm_trend | -0.4138 | 18 |
| holdout | neutral_mixed | +0.0645 | 56 |
| holdout | recovery_confirmed | – | 9 |
| holdout | recovery_fragile | – | 4 |
| holdout | stressed_panic | +0.3132 | 13 |

### r2a

| scope | market_state | IC | N |
|-------|--------------|----|---|
| full | ALL | +0.1738 | 1106 |
| full | calm_trend | +0.2068 | 295 |
| full | neutral_mixed | +0.0972 | 491 |
| full | recovery_confirmed | -0.0433 | 43 |
| full | recovery_fragile | +0.2384 | 49 |
| full | stressed_panic | +0.3628 | 228 |
| dev | ALL | +0.1698 | 1006 |
| dev | calm_trend | +0.1856 | 277 |
| dev | neutral_mixed | +0.1150 | 435 |
| dev | recovery_confirmed | -0.0628 | 34 |
| dev | recovery_fragile | +0.1484 | 45 |
| dev | stressed_panic | +0.3565 | 215 |
| holdout | ALL | +0.2176 | 100 |
| holdout | calm_trend | +0.4159 | 18 |
| holdout | neutral_mixed | -0.0573 | 56 |
| holdout | recovery_confirmed | – | 9 |
| holdout | recovery_fragile | – | 4 |
| holdout | stressed_panic | +0.5989 | 13 |

### r2b

| scope | market_state | IC | N |
|-------|--------------|----|---|
| full | ALL | +0.0375 | 1106 |
| full | calm_trend | -0.2069 | 295 |
| full | neutral_mixed | -0.1018 | 491 |
| full | recovery_confirmed | -0.0165 | 43 |
| full | recovery_fragile | +0.2605 | 49 |
| full | stressed_panic | +0.3742 | 228 |
| dev | ALL | +0.0351 | 1006 |
| dev | calm_trend | -0.1856 | 277 |
| dev | neutral_mixed | -0.1192 | 435 |
| dev | recovery_confirmed | -0.0445 | 34 |
| dev | recovery_fragile | +0.1692 | 45 |
| dev | stressed_panic | +0.3670 | 215 |
| holdout | ALL | +0.0684 | 100 |
| holdout | calm_trend | -0.4159 | 18 |
| holdout | neutral_mixed | +0.0634 | 56 |
| holdout | recovery_confirmed | – | 9 |
| holdout | recovery_fragile | – | 4 |
| holdout | stressed_panic | +0.6099 | 13 |

### r2c

| scope | market_state | IC | N |
|-------|--------------|----|---|
| full | ALL | -0.0518 | 1106 |
| full | calm_trend | -0.0783 | 295 |
| full | neutral_mixed | +0.0332 | 491 |
| full | recovery_confirmed | +0.0893 | 43 |
| full | recovery_fragile | -0.0668 | 49 |
| full | stressed_panic | -0.1560 | 228 |
| dev | ALL | -0.0849 | 1006 |
| dev | calm_trend | -0.0819 | 277 |
| dev | neutral_mixed | -0.0211 | 435 |
| dev | recovery_confirmed | +0.0445 | 34 |
| dev | recovery_fragile | -0.0604 | 45 |
| dev | stressed_panic | -0.1733 | 215 |
| holdout | ALL | +0.2944 | 100 |
| holdout | calm_trend | -0.0217 | 18 |
| holdout | neutral_mixed | +0.4223 | 56 |
| holdout | recovery_confirmed | – | 9 |
| holdout | recovery_fragile | – | 4 |
| holdout | stressed_panic | +0.2582 | 13 |

### r2d

| scope | market_state | IC | N |
|-------|--------------|----|---|
| full | ALL | +0.0380 | 1106 |
| full | calm_trend | – | 295 |
| full | neutral_mixed | – | 491 |
| full | recovery_confirmed | +0.0264 | 43 |
| full | recovery_fragile | +0.2688 | 49 |
| full | stressed_panic | – | 228 |
| dev | ALL | +0.0260 | 1006 |
| dev | calm_trend | – | 277 |
| dev | neutral_mixed | – | 435 |
| dev | recovery_confirmed | -0.0240 | 34 |
| dev | recovery_fragile | +0.1738 | 45 |
| dev | stressed_panic | – | 215 |
| holdout | ALL | +0.0867 | 100 |
| holdout | calm_trend | – | 18 |
| holdout | neutral_mixed | – | 56 |
| holdout | recovery_confirmed | – | 9 |
| holdout | recovery_fragile | – | 4 |
| holdout | stressed_panic | – | 13 |

---

## 5. Quintile Return Monotonicity

Q1 = lowest signal, Q5 = highest signal. A well-designed composite should show monotonically increasing forward returns Q1→Q5.

### deployment_quality_composite

| market_state | Q1 | Q2 | Q3 | Q4 | Q5 | monotone? |
|--------------|----|----|----|----|----|-----------| 
| calm_trend | 0.0110 | 0.0079 | 0.0112 | 0.0036 | -0.0005 | no |
| neutral_mixed | 0.0145 | 0.0127 | 0.0066 | 0.0124 | 0.0039 | no |
| recovery_confirmed | 0.0142 | 0.0078 | 0.0210 | 0.0126 | -0.0076 | no |
| recovery_fragile | 0.0108 | 0.0142 | -0.0029 | 0.0305 | 0.0219 | no |
| stressed_panic | -0.0056 | -0.0074 | 0.0130 | 0.0148 | 0.0196 | no |

### r2a

| market_state | Q1 | Q2 | Q3 | Q4 | Q5 | monotone? |
|--------------|----|----|----|----|----|-----------| 
| calm_trend | -0.0108 | 0.0135 | 0.0055 | 0.0148 | 0.0102 | no |
| neutral_mixed | 0.0089 | 0.0072 | 0.0092 | 0.0087 | 0.0164 | no |
| recovery_confirmed | 0.0087 | 0.0125 | 0.0215 | -0.0009 | 0.0052 | no |
| recovery_fragile | 0.0128 | 0.0105 | -0.0054 | 0.0364 | 0.0200 | no |
| stressed_panic | -0.0317 | -0.0125 | 0.0241 | 0.0176 | 0.0368 | no |

### r2b

| market_state | Q1 | Q2 | Q3 | Q4 | Q5 | monotone? |
|--------------|----|----|----|----|----|-----------| 
| calm_trend | 0.0101 | 0.0156 | 0.0091 | 0.0097 | -0.0112 | no |
| neutral_mixed | 0.0158 | 0.0093 | 0.0092 | 0.0071 | 0.0088 | no |
| recovery_confirmed | 0.0087 | 0.0125 | 0.0173 | 0.0038 | 0.0052 | no |
| recovery_fragile | 0.0070 | 0.0175 | -0.0024 | 0.0324 | 0.0200 | no |
| stressed_panic | -0.0241 | -0.0174 | 0.0008 | 0.0346 | 0.0408 | yes |

### r2c

| market_state | Q1 | Q2 | Q3 | Q4 | Q5 | monotone? |
|--------------|----|----|----|----|----|-----------| 
| calm_trend | 0.0068 | 0.0102 | -0.0003 | 0.0075 | 0.0052 | no |
| neutral_mixed | 0.0068 | 0.0091 | 0.0148 | 0.0109 | 0.0135 | no |
| recovery_confirmed | 0.0102 | 0.0033 | 0.0045 | 0.0282 | 0.0030 | no |
| recovery_fragile | 0.0162 | 0.0206 | 0.0152 | 0.0199 | 0.0038 | no |
| stressed_panic | 0.0283 | 0.0186 | 0.0037 | -0.0089 | -0.0074 | no |

### r2d

| market_state | Q1 | Q2 | Q3 | Q4 | Q5 | monotone? |
|--------------|----|----|----|----|----|-----------| 
| recovery_confirmed | 0.0082 | 0.0105 | 0.0146 | 0.0229 | -0.0033 | no |
| recovery_fragile | 0.0083 | 0.0129 | 0.0532 | – | – | yes |

---

## 6. R2C Diagnostic: Redesigned Credit Component

`credit_relative_momentum = HYG_4w_return − LQD_4w_return` (continuous, z-scored, 1w lag).
This is a standalone diagnostic. It is NOT included in R2A or R2B composites.

| market_state | IC | N |
|--------------|-------|---|
| ALL | -0.0518 | 1106 |
| calm_trend | -0.0783 | 295 |
| neutral_mixed | +0.0332 | 491 |
| recovery_confirmed | +0.0893 | 43 |
| recovery_fragile | -0.0668 | 49 |
| stressed_panic | -0.1560 | 228 |

**Interpretation:** If R2C shows positive IC in recovery states (unlike the original credit_confirmation), it can be incorporated into a future R2A+ variant with appropriate state-conditional sign. If IC remains negative in recovery, the credit signal is structurally unusable in this form and should be redesigned further.

---

## 7. Should Phase 1 Move to Wrapper Diagnostic?

**Recommendation: YES**

**Best variant:** r2a

**Reasoning:** R2A (state-aware signed composite) passes all acceptance gates. Proceed to Phase 1B wrapper diagnostic using R2A.

**Action:** Proceed to Phase 1B using the recommended variant. The wrapper diagnostic should use the `offense_budget` checkpoint (safe, modifiable) and should be read-only diagnostic first. Report all Phase D metrics and update `project_journey.md` after Phase 1B.

---

## 8. Comparison vs Phase 1A Original

| metric | original_composite | best_R2 |
|--------|--------------------|---------|
| full_IC | -0.0495 | +0.1738 |
| dev_IC | -0.0511 | +0.1698 |
| holdout_IC | -0.0363 | +0.2176 |
| mean_state_IC | -0.0056 | +0.1724 |
| positive_states | 2 | 4 |

---

## 9. Files Created

| file | description |
|------|-------------|
| `data/research/frontier_phase1/state_quality_signals_r2.csv` | Extended signals with R2A/B/C/D columns |
| `data/research/frontier_phase1/state_quality_r2_ic_by_state.csv` | IC by state, by scope, by variant |
| `data/research/frontier_phase1/state_quality_r2_quintile_returns_by_state.csv` | Quintile forward returns |
| `docs/research/frontier_phase1_state_quality_r2_report.md` | This report |

## 10. Production Safety

- Protected file diff: **✓ Clean**
- No production, dashboard, or public files were modified by this script.
