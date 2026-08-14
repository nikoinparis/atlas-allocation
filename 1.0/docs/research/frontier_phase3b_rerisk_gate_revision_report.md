# Frontier Phase 3B: Smart Re-Risking Gate Revision Report

**Date:** 2026-05-21
**Mode:** Diagnostic-only — no production or dashboard files modified
**Best candidate:** `phase1_r2a_only`

---

## 1. Why Phase 3A Failed and Why Phase 3B Also Failed

**Phase 3A failure:** The ≥6-week gate fired only 3 times (0.3% of history) — a threshold calibration problem, not a signal failure.

**Phase 3B structural finding:** Lowering the gate threshold exposed a deeper architectural problem. The `rq_r2a_plus_trend` quality signal crosses zero in 43% of recovery weeks (40 out of 93 recovery rows have negative scores, mean = +0.09). The symmetric modifier — which both BOOSTS offense when quality > 0 AND REDUCES offense when quality < 0 — causes the portfolio to become **more defensive than baseline in 45% of recovery weeks**. This drags down recovery-confirmed capture below baseline, which is the opposite of the goal.

**Recovery weeks modifier distribution (continuous variant):**
- Quality > 0 → boost offense (boost rows): **51 / 93 (54.8%)**
- Quality < 0 → reduce offense (reduce rows): **42 / 93 (45.2%)**

**Core problem:** The quality signal is not consistently positive during recovery states. When R2A or trend quality is negative during a recovery, the modifier acts as a de-risking signal — the wrong direction for a re-risking engine. The negative reduction rows cause more portfolio harm than the positive boost rows provide benefit, because reducing offense in an actual recovery period is costly.

**What a correct re-risking design requires:** An asymmetric modifier that only boosts when quality is high (`max(1.0, 1.0 + boost × quality)`) and never reduces below the baseline in recovery states. This is the natural next revision if Phase 3 is revisited.

## 2. Gate Activation Summary

| gate | active weeks | % of history |
|------|-------------|--------------|
| ≥6w (Phase 3A) | 3 | 0.3% |
| ≥3w | 35 | 3.2% |
| ≥2w | 56 | 5.0% |
| Continuous | 93 | 8.4% |
| RC-only | 44 | 4.0% |

## 3. Commands Run

```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier3b_rerisk_gate_revision.py
```

---

## 4. Full-History Metrics

| metric | baseline | p1_r2a | p3b_3w | p3b_2w | p3b_cont | p3b_rc_only | p1+p3b |
|--------|------|------|------|------|------|------|------|
| Ann ret | 7.14% | 7.14% | 7.12% | 7.12% | 7.13% | 7.13% | 7.13% |
| Sharpe | 0.9362 | 0.9392 | 0.9336 | 0.9322 | 0.9346 | 0.9341 | 0.9368 |
| Max DD | -0.1177 | -0.1166 | -0.1177 | -0.1177 | -0.1177 | -0.1177 | -0.1166 |
| CVaR 5% | -0.0254 | -0.0253 | -0.0254 | -0.0254 | -0.0254 | -0.0254 | -0.0253 |
| TO/wk | 0.0618 | 0.0658 | 0.0627 | 0.0632 | 0.0635 | 0.0627 | 0.0675 |
| ExtraCost/yr | 0.32% | 0.34% | 0.33% | 0.33% | 0.33% | 0.33% | 0.35% |
| BIL | 26.66% | 26.88% | 26.63% | 26.64% | 26.64% | 26.59% | 26.89% |
| Offense | 41.62% | 41.45% | 41.66% | 41.65% | 41.65% | 41.69% | 41.46% |
| β SPY | 0.2431 | 0.2429 | 0.2434 | 0.2435 | 0.2434 | 0.2434 | 0.2431 |

*Full-history Sharpe Δ vs baseline:*
- baseline: +0.0000
- p1_r2a: +0.0030
- p3b_3w: -0.0026
- p3b_2w: -0.0040
- p3b_cont: -0.0015
- p3b_rc_only: -0.0021
- p1+p3b: +0.0006

---

## 5. Holdout Metrics (from 2024-04-19)

| metric | baseline | p1_r2a | p3b_3w | p3b_2w | p3b_cont | p3b_rc_only | p1+p3b |
|--------|------|------|------|------|------|------|------|
| Return | 17.89% | 17.94% | 17.81% | 17.75% | 17.88% | 17.87% | 17.92% |
| Sharpe | 2.1510 | 2.1517 | 2.1348 | 2.1251 | 2.1384 | 2.1365 | 2.1413 |
| Max DD | -0.0725 | -0.0736 | -0.0725 | -0.0725 | -0.0725 | -0.0725 | -0.0736 |

*Holdout Sharpe Δ vs baseline:*
- baseline: +0.0000
- p1_r2a: +0.0007
- p3b_3w: -0.0162
- p3b_2w: -0.0259
- p3b_cont: -0.0127
- p3b_rc_only: -0.0145
- p1+p3b: -0.0097

---

## 6. Recovery Capture Analysis

| state | baseline | p3b_3w | p3b_2w | p3b_cont | p3b_rc | p1+p3b | Δ_best |
|-------|----------|--------|--------|----------|--------|--------|--------|
| recovery_confirmed | 0.3955 | 0.3304 | 0.3167 | 0.3747 | 0.3746 | 0.3440 | -0.021 |
| recovery_fragile | 0.2476 | 0.2516 | 0.2498 | 0.2520 | 0.2475 | 0.2524 | +0.005 |

---

## 7. Stressed-Panic Preservation

All Phase 3B modifiers unconditionally set stressed_panic multiplier = 1.0.
Assertions passed for all candidates.

| variant | sp_sharpe | sp_max_dd | Δsp_sharpe | Δsp_dd |
|---------|-----------|-----------|-----------|--------|
| baseline | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p1_r2a | 0.4799 | -0.1216 | -0.0008 | -0.0000 |
| p3b_3w | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p3b_2w | 0.4806 | -0.1216 | -0.0000 | -0.0000 |
| p3b_cont | 0.4806 | -0.1216 | -0.0001 | -0.0000 |
| p3b_rc_only | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p1+p3b | 0.4798 | -0.1216 | -0.0009 | -0.0000 |

---

## 8. Rolling-Origin and Bootstrap

| candidate | rolling_win | bootstrap_P | mean_Δ | CI_95 |
|-----------|------------|------------|--------|-------|
| p1_r2a | 66.7% | 0.477 | -0.0019 | [-0.0454, +0.0364] |
| p3b_3w | 26.7% | 0.089 | -0.0221 | [-0.0780, +0.0041] |
| p3b_2w | 26.7% | 0.037 | -0.0343 | [-0.0915, +0.0012] |
| p3b_cont | 40.0% | 0.120 | -0.0194 | [-0.0654, +0.0088] |
| p3b_rc_only | 33.3% | 0.102 | -0.0217 | [-0.0717, +0.0085] |
| p1+p3b | 60.0% | 0.297 | -0.0171 | [-0.0821, +0.0337] |

---

## 9. Phase D Gate Summary

| candidate | verdict | key failures |
|-----------|---------|--------------|
| p1_r2a | ✗ FAIL | Full Sharpe Δ=+0.0030 < +0.01; RC capture Δ=-0.006 < +5pp; Bootstrap P=0.477 < 0.60 |
| p3b_3w | ✗ FAIL | Full Sharpe Δ=-0.0026 < +0.01; RC capture Δ=-0.065 < +5pp; Bootstrap P=0.089 < 0.60; Rolling win=26. |
| p3b_2w | ✗ FAIL | Full Sharpe Δ=-0.0040 < +0.01; Holdout Sharpe Δ=-0.0259 < -0.02; RC capture Δ=-0.079 < +5pp; Bootstr |
| p3b_cont | ✗ FAIL | Full Sharpe Δ=-0.0015 < +0.01; RC capture Δ=-0.021 < +5pp; Bootstrap P=0.120 < 0.60; Rolling win=40. |
| p3b_rc_only | ✗ FAIL | Full Sharpe Δ=-0.0021 < +0.01; RC capture Δ=-0.021 < +5pp; Bootstrap P=0.102 < 0.60; Rolling win=33. |
| p1+p3b | ✗ FAIL | Full Sharpe Δ=+0.0006 < +0.01; RC capture Δ=-0.051 < +5pp; Bootstrap P=0.297 < 0.60 |

---

## 10. Phase 3B vs Phase 1-Only vs Phase 2B Reference

**Note on Phase 1 reference in this sprint:** The `phase1_r2a_only` candidate here uses the **blended rq_r2a_plus_trend signal** (0.70×R2A + 0.30×avg_trend_quality) instead of the pure R2A used in Phase 1B and Phase 2B. This explains why the Phase 1 reference here shows full Sharpe +0.0030 and holdout +0.0007 instead of Phase 1B's +0.0095 and +0.0213. The pure R2A is the stronger signal; the blend dilutes it with trend_quality's noisier recovery-state content.

| candidate | full_Sharpe | holdout_Sharpe | RC_capture | rolling_win | bootstrap_P |
|-----------|------------|----------------|------------|------------|------------|
| baseline | 0.9362 | 2.1510 | 0.3955 | – | – |
| phase1_r2a (blended) | 0.9392 | 2.1517 | 0.3896 | 66.7% | 0.477 |
| best_p3b (phase1_r2a) | 0.9392 | 2.1517 | 0.3896 | 66.7% | 0.477 |
| **phase1_r2a pure (Phase 1B)** | **0.9457** | **2.1723** | 0.3682 | **66.7%** | **0.719** |
| **phase1+p2_tq (Phase 2B)** | **0.9445** | **2.1943** | – | **66.7%** | **0.844** |

*Phase 2B reference (phase1_rxa_plus_phase2_trend_quality from Phase 2B):*
holdout Sharpe Δ +0.043, bootstrap P 0.844, rolling win 66.7%

---

## 11. Verdict

**Keep as research-only diagnostic**

No Phase 3B candidate improves recovery-confirmed capture or holdout Sharpe vs baseline. All Phase 3B re-risking modifier candidates DECREASE recovery capture (by -0.021 to -0.079), because the signed quality modifier reduces offense in 45% of recovery weeks (when quality score is negative), causing more harm than the 55%-of-weeks positive boost can recover.

**Root cause:** `rq_r2a_plus_trend` has negative values in 43% of recovery weeks (mean +0.09 in recovery states, not consistently positive). A symmetric modifier (`1 + boost × quality`) becomes a DE-RISKER in those negative weeks. The design needs to be asymmetric: only boost, never reduce, during recovery.

**The Phase 3 re-risking approach requires revision before further testing:**
- Option A: asymmetric modifier `max(1.0, 1.0 + boost × quality)` — only upside
- Option B: quality as a binary gate (quality > threshold → apply fixed boost, else no change)
- Option C: de-couple quality signal from re-risk speed and use quality as a Phase 5 allocator input instead of a Phase 3 checkpoint modifier

### Should Phase 3 feed into Phases 4/5?

Yes — `recovery_quality_r2a_plus_trend` is a validated signal composite with:
- R2A holdout IC +0.218, recovery_confirmed IC +0.073 (t=+2.0)
- Phase 2 trend_quality confirms the signal's recovery-state relevance

Carry forward to:
- **Phase 4** (Cross-Sectional Leadership): recovery quality as leadership confirmation
- **Phase 5** (Allocator Objective): recovery quality as deployment confidence score component

Do NOT apply the Phase 3B re-risk modifier as a standalone portfolio modifier.
The strongest existing frontier portfolio modifier remains:
`phase1_r2a_plus_phase2_trend_quality` (Phase 2B): holdout Δ +0.043, bootstrap 84%.

---

## 12. Files Created

- `data/research/frontier_phase3/phase3b_rerisk_gate_results.csv`
- `data/research/frontier_phase3/phase3b_rerisk_gate_holdout_summary.csv`
- `data/research/frontier_phase3/phase3b_rerisk_gate_state_summary.csv`
- `data/research/frontier_phase3/phase3b_rerisk_gate_phase_d_gates.csv`
- `data/research/frontier_phase3/phase3b_rerisk_modifier_timeseries.csv`
- `docs/research/frontier_phase3b_rerisk_gate_revision_report.md`

## 13. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified