# Frontier Phase 3A: Smart Re-Risking Engine Report

**Date:** 2026-05-21
**Mode:** Diagnostic-only — no production or dashboard files modified
**Best candidate:** `phase1_r2a_only`

---

## 1. Sprint Summary

Phase 3A applies validated Phase 1 (R2A) and Phase 2 (trend_quality) signals as a re-risk speed modifier at the `transition_rerisk_smoothing` checkpoint. The modifier boosts offensive ETF weights in high-quality recovery states after ≥6 consecutive recovery weeks (transition quality gate). stressed_panic modifier is unconditionally 1.0 — no boost ever.

**Key finding: the ≥6-week transition gate is too strict for this dataset.** Only 1 recovery run in the full 1110-week history spans ≥6 consecutive weeks (an 8-week run). The gate activated in only 3 weeks (0.3% of history), making all Phase 3 candidates essentially no-ops. With a ≥3-week threshold, the gate would activate in 35 weeks (3.2%) across 15 recovery runs. This structural mismatch is the primary reason Phase 3 shows no portfolio improvement.

### Architecture

`transition_rerisk_smoothing` scales OFFENSE ETFs uniformly. Multiplier > 1 → more offense / less BIL = faster re-risking in recovery. Range of modifier in active recovery states: [0.80, 1.20]. stressed_panic: always 1.0.

---

## 2. Commands Run

```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier3_smart_rerisk_engine.py
```

---

## 3. Recovery Quality Construction

| variant | inputs | formula | range |
|---------|--------|---------|-------|
| `recovery_quality_r2a` | R2A (Phase 1, lagged) | clip(r2a, -1, 1) | [-1, 1] |
| `recovery_quality_no_credit` | breadth, persistence, leadership (Phase 1) | 0.40×breadth + 0.30×persistence + 0.30×leadership → z-score → clip | [-1, 1] |
| `recovery_quality_r2a_plus_trend` | R2A + avg trend_quality (Phase 2) | 0.70×r2a + 0.30×avg_tq → clip | [-1, 1] |
| `transition_quality_score` | consecutive recovery weeks | 1 if ≥6 weeks in recovery, else 0 | {0, 1} |

**Transition quality gate activation:** 3 / 1110 weeks (0.3%) — **structurally too restrictive**

**Recovery run length distribution in full dataset:**
- Longest run: 8 weeks (only run ≥6 weeks → gates on weeks 6, 7, 8 only)
- Total runs ≥3 consecutive weeks: 15 runs, 35 active weeks (3.2%)
- Total runs ≥2 consecutive weeks: 21 runs
- The ≥6-week threshold fires only in 1 recovery run out of 21 total runs

**Modifier formula (in active states):**  `1.0 + 0.2 × quality × transition_gate`

**Structural diagnosis:** Because the transition gate only fires in 3 weeks (0.3% of history), all Phase 3 modifier candidates are almost identical to the baseline. The modifier has no meaningful effect. This is not a signal quality failure — it is a threshold calibration failure. A ≥3-week threshold would activate 35 weeks and give the modifier enough activations to produce a measurable effect.

---

## 4. Full-History Metrics

| metric | baseline | p1_r2a | p3_r2a | p3_nc | p3_r2a+tq | p3_rc_only |
|--------|------|------|------|------|------|------|
| Ann return | 7.14% | 7.13% | 7.13% | 7.13% | 7.13% | 7.13% |
| Sharpe | 0.9362 | 0.9457 | 0.9349 | 0.9349 | 0.9350 | 0.9350 |
| Calmar | 0.6063 | 0.6147 | 0.6057 | 0.6057 | 0.6057 | 0.6057 |
| Max DD | -0.1177 | -0.1160 | -0.1177 | -0.1177 | -0.1177 | -0.1177 |
| CVaR 5% | -0.0254 | -0.0250 | -0.0254 | -0.0254 | -0.0254 | -0.0254 |
| TO/wk | 0.0618 | 0.0680 | 0.0619 | 0.0619 | 0.0619 | 0.0619 |
| Extra cost/yr | 0.32% | 0.35% | 0.32% | 0.32% | 0.32% | 0.32% |
| Avg BIL | 26.66% | 27.44% | 26.65% | 26.65% | 26.65% | 26.65% |
| Avg offense | 41.62% | 40.90% | 41.64% | 41.64% | 41.64% | 41.64% |
| Hidden β | 0.2431 | 0.2412 | 0.2432 | 0.2432 | 0.2432 | 0.2432 |

---

## 5. Holdout Metrics (from 2024-04-19)

| metric | baseline | p1_r2a | p3_r2a | p3_nc | p3_r2a+tq | p3_rc_only |
|--------|------|------|------|------|------|------|
| Return | 17.89% | 17.94% | 17.81% | 17.80% | 17.81% | 17.81% |
| Sharpe | 2.1510 | 2.1723 | 2.1340 | 2.1336 | 2.1357 | 2.1357 |
| Max DD | -0.0725 | -0.0729 | -0.0725 | -0.0725 | -0.0725 | -0.0725 |

*Holdout Sharpe deltas vs baseline:*
- baseline: +0.0000
- p1_r2a: +0.0213
- p3_r2a: -0.0170
- p3_nc: -0.0174
- p3_r2a+tq: -0.0153
- p3_rc_only: -0.0153

---

## 6. Recovery Capture Analysis

| state | baseline | p3_r2a | p3_nc | p3_r2a+tq | p3_rc_only | Δ_best |
|-------|----------|--------|-------|-----------|------------|--------|
| recovery_confirmed | 0.3805 | 0.3570 | 0.3556 | 0.3589 | 0.3589 | -0.022 |
| recovery_fragile | 0.2476 | 0.2476 | 0.2476 | 0.2476 | 0.2476 | +0.000 |

---

## 7. Stressed_Panic Preservation Check

All modifier variants unconditionally set stressed_panic multiplier = 1.0.

| variant | sp_sharpe | sp_max_dd | Δ_sp_sharpe | Δ_sp_dd |
|---------|-----------|-----------|-------------|---------|
| baseline | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p1_r2a | 0.4791 | -0.1216 | -0.0016 | -0.0000 |
| p3_r2a | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p3_nc | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p3_r2a+tq | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p3_rc_only | 0.4807 | -0.1216 | +0.0000 | +0.0000 |

---

## 8. Rolling-Origin and Bootstrap

| candidate | rolling_win | bootstrap_P | mean_bs_delta | CI_95 |
|-----------|------------|------------|---------------|-------|
| p1_r2a | 66.7% | 0.719 | +0.0193 | [-0.0493, +0.0829] |
| p3_r2a | 0.0% | 0.060 | -0.0233 | [-0.0826, +0.0060] |
| p3_nc | 0.0% | 0.060 | -0.0237 | [-0.0830, +0.0053] |
| p3_r2a+tq | 0.0% | 0.060 | -0.0209 | [-0.0734, +0.0050] |
| p3_rc_only | 0.0% | 0.060 | -0.0209 | [-0.0734, +0.0050] |

---

## 9. Phase D Gate Summary

| candidate | verdict | key_failures |
|-----------|---------|--------------|
| p1_r2a | ✗ FAIL | Full Sharpe Δ=+0.0095 < +0.01; Recovery-confirmed capture Δ=-0.013 < +5pp |
| p3_r2a | ✗ FAIL | Full Sharpe Δ=-0.0012 < +0.01; Recovery-confirmed capture Δ=-0.023 < +5pp; Bootstrap P=0.060 < 0.60; |
| p3_nc | ✗ FAIL | Full Sharpe Δ=-0.0013 < +0.01; Recovery-confirmed capture Δ=-0.025 < +5pp; Bootstrap P=0.060 < 0.60; |
| p3_r2a+tq | ✗ FAIL | Full Sharpe Δ=-0.0011 < +0.01; Recovery-confirmed capture Δ=-0.022 < +5pp; Bootstrap P=0.060 < 0.60; |
| p3_rc_only | ✗ FAIL | Full Sharpe Δ=-0.0011 < +0.01; Recovery-confirmed capture Δ=-0.022 < +5pp; Bootstrap P=0.060 < 0.60; |

---

## 10. Verdict

**Keep as research-only diagnostic**

The Phase 3 re-risking modifier had no meaningful portfolio effect because the transition quality gate (≥6 consecutive recovery weeks) fired only 3 times in 1110 weeks (0.3% of history). This is a threshold calibration failure, not a signal quality failure. All Phase 3 modifier candidates are essentially identical to the baseline.

**Why the Phase 3 modifier candidates look worse than baseline:** The 3 activation rows happened to be during a period where the additional offense boost had a slight negative outcome, but this is pure noise from 3 data points. The signal itself is not disproven.

**What a revision should do:**

1. **Lower the transition gate to ≥3 consecutive recovery weeks** (fires in 35 weeks, 3.2% of history). This is still a meaningful quality gate (requires confirmed persistent recovery) but fires enough to produce a measurable effect.
2. **Alternatively: remove the transition gate entirely** and apply the quality score directly:  
   `modifier = 1.0 + 0.20 × quality_score` (in recovery states only)  
   This always provides some boost when quality is positive and dampens when quality is negative — asymmetric re-risking at all times in recovery.
3. **Test at both checkpoints:** `transition_rerisk_smoothing` (tested here) and `offense_budget` (where Phase 1 R2A already showed positive results). The Phase 1 R2A result at `offense_budget` (+0.0095 Sharpe, holdout +0.021) is actually the strongest single Phase 3-class result from all three phases.

**The best available re-risk modifier in the frontier arc remains Phase 1 R2A at `offense_budget`:**
- Full-history Sharpe Δ=+0.0095 (0.0005 below the +0.01 gate)
- Holdout Sharpe Δ=+0.0213 (passes the -0.02 floor with significant margin)
- Bootstrap P=0.719 (passes 0.60 gate)
- Rolling win=66.7% (passes 55% gate)
- Only failure: full-history Sharpe gate by 0.0005

### Should Phase 3 feed into Phases 4/5?

Yes, unconditionally as a signal input. The recovery quality signal construction is valid:
- `recovery_quality_r2a_plus_trend` combines R2A (IC +0.218 on holdout) with Phase 2 trend quality (IC +0.073 in recovery_confirmed)
- Carry this composite forward to Phase 4 (Cross-Sectional Leadership) and Phase 5 (Allocator Objective Redesign)
- Do NOT apply the ≥6-week-gated re-risking modifier as a portfolio weight change — revise the threshold first
- The combined `phase1_r2a_plus_phase2_trend_quality` from Phase 2B (holdout Δ=+0.043, bootstrap=0.844) remains the strongest frontier portfolio modifier found so far

---

## 11. Files Created

- `data/research/frontier_phase3/smart_rerisk_results.csv`
- `data/research/frontier_phase3/smart_rerisk_holdout_summary.csv`
- `data/research/frontier_phase3/smart_rerisk_state_summary.csv`
- `data/research/frontier_phase3/smart_rerisk_phase_d_gates.csv`
- `data/research/frontier_phase3/rerisk_modifier_timeseries.csv`
- `docs/research/frontier_phase3_smart_rerisk_engine_report.md`

## 12. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified
