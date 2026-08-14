# Frontier Phase 5A: Deployment-Quality Allocator Objective Report

**Date:** 2026-05-21
**Mode:** Diagnostic-only — no production or dashboard files modified
**Best candidate:** `phase1_plus_phase2_reference`

---

## 1. Sprint Summary

Phase 5A combines Phase 1 (R2A), Phase 2 (trend_quality) and Phase 4 (inverted leadership = fragility) into a master deployment quality score.  This score is applied as a bounded offense_budget multiplier.  Phase 4 enters INVERTED (raw composite was anti-predictive; inverted version captures fresh/uncrowded leadership as a positive signal).

### Master Deployment Quality Weights (predeclared)

| component | weight | source |
|-----------|--------|--------|
| phase1_state_quality (R2A) | 0.45 | Phase 1 |
| phase2_portfolio_tq (avg trend_quality) | 0.35 | Phase 2 |
| phase4_fragility_adjusted (−leadership) | 0.2 | Phase 4 (inverted) |

---

## 2. Commands Run
```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier5_deployment_quality_allocator.py
```

---

## 3. Full-History Metrics

| metric | baseline | p1_r2a | p1+p2 | p5_mdq010 | p5_mdq012 | p5_pos_only | p5_frag_grd | p5_mdq+frag |
|--------|------|------|------|------|------|------|------|------|
| Ann ret | 7.14% | 7.13% | 7.15% | 7.21% | 7.22% | 7.29% | 7.13% | 7.17% |
| Sharpe | 0.9362 | 0.9457 | 0.9445 | 0.9466 | 0.9479 | 0.9420 | 0.9483 | 0.9439 |
| Max DD | -0.1177 | -0.1160 | -0.1160 | -0.1160 | -0.1160 | -0.1177 | -0.1160 | -0.1160 |
| CVaR 5% | -0.0254 | -0.0250 | -0.0252 | -0.0254 | -0.0254 | -0.0258 | -0.0249 | -0.0253 |
| TO/wk | 0.0618 | 0.0680 | 0.0708 | 0.0699 | 0.0715 | 0.0660 | 0.0674 | 0.0694 |
| ExtraCost/yr | 0.32% | 0.35% | 0.37% | 0.36% | 0.37% | 0.34% | 0.35% | 0.36% |
| BIL | 26.66% | 27.44% | 27.44% | 26.94% | 27.04% | 25.76% | 27.61% | 27.11% |
| Offense | 41.62% | 40.90% | 40.90% | 41.46% | 41.39% | 42.64% | 40.72% | 41.27% |
| β SPY | 0.2431 | 0.2412 | 0.2421 | 0.2430 | 0.2429 | 0.2483 | 0.2402 | 0.2423 |

*Full Sharpe Δ vs GGG baseline:*
- baseline: +0.0000
- p1_r2a: +0.0095
- p1+p2: +0.0083
- p5_mdq010: +0.0105
- p5_mdq012: +0.0117
- p5_pos_only: +0.0058
- p5_frag_grd: +0.0121
- p5_mdq+frag: +0.0078

---

## 4. Holdout Metrics (from 2024-04-19)

| metric | baseline | p1_r2a | p1+p2 | p5_mdq010 | p5_mdq012 | p5_pos_only | p5_frag_grd | p5_mdq+frag |
|--------|------|------|------|------|------|------|------|------|
| Return | 17.89% | 17.94% | 18.02% | 18.05% | 18.09% | 18.04% | 17.91% | 17.98% |
| Sharpe | 2.1510 | 2.1723 | 2.1943 | 2.1404 | 2.1429 | 2.1170 | 2.1786 | 2.1439 |
| Max DD | -0.0725 | -0.0729 | -0.0734 | -0.0759 | -0.0760 | -0.0759 | -0.0729 | -0.0759 |

*Holdout Sharpe Δ vs GGG:*
- baseline: +0.0000
- p1_r2a: +0.0213
- p1+p2: +0.0433
- p5_mdq010: -0.0106
- p5_mdq012: -0.0081
- p5_pos_only: -0.0340
- p5_frag_grd: +0.0276
- p5_mdq+frag: -0.0071

---

## 5. State-by-State (best candidate vs baseline)

| state | base_sh | base_cap | best_sh | best_cap | Δsh |
|-------|---------|----------|---------|----------|-----|
| calm_trend | 0.5136 | 0.4735 | 0.5269 | 0.4684 | +0.0133 |
| neutral_mixed | 1.4616 | 0.9457 | 1.4680 | 0.9518 | +0.0064 |
| recovery_confirmed | 0.3443 | 0.3955 | 0.3021 | 0.3626 | -0.0422 |
| recovery_fragile | 1.1421 | 0.2476 | 1.1580 | 0.2511 | +0.0158 |
| stressed_panic ← active | 0.4807 | 0.4640 | 0.4779 | 0.4613 | -0.0028 |

---

## 6. Stressed-Panic Preservation

Assertions passed for all candidates.  Modifier is unconditionally 1.0 in stressed_panic.

| variant | sp_sharpe | sp_max_dd | Δsp_sh | Δsp_dd |
|---------|-----------|-----------|--------|--------|
| baseline | 0.4807 | -0.1216 | +0.0000 | +0.0000 |
| p1_r2a | 0.4791 | -0.1216 | -0.0016 | -0.0000 |
| p1+p2 | 0.4779 | -0.1217 | -0.0028 | -0.0001 |
| p5_mdq010 | 0.4788 | -0.1216 | -0.0019 | -0.0000 |
| p5_mdq012 | 0.4784 | -0.1216 | -0.0023 | -0.0000 |
| p5_pos_only | 0.4794 | -0.1216 | -0.0013 | -0.0000 |
| p5_frag_grd | 0.4793 | -0.1216 | -0.0014 | -0.0000 |
| p5_mdq+frag | 0.4788 | -0.1216 | -0.0018 | -0.0000 |

---

## 7. Rolling-Origin and Bootstrap

| candidate | rolling_win | bootstrap_P | mean_Δ | CI_95 |
|-----------|------------|------------|--------|-------|
| p1_r2a | 66.7% | 0.719 | +0.0193 | [-0.0493, +0.0829] |
| p1+p2 | 66.7% | 0.844 | +0.0504 | [-0.0454, +0.1372] |
| p5_mdq010 | 73.3% | 0.434 | -0.0062 | [-0.0859, +0.0680] |
| p5_mdq012 | 73.3% | 0.449 | -0.0056 | [-0.0947, +0.0817] |
| p5_pos_only | 53.3% | 0.043 | -0.0370 | [-0.0814, +0.0053] |
| p5_frag_grd | 73.3% | 0.841 | +0.0298 | [-0.0228, +0.0806] |
| p5_mdq+frag | 73.3% | 0.507 | +0.0010 | [-0.0721, +0.0732] |

---

## 8. Phase D Gate Summary

| candidate | verdict | key failures |
|-----------|---------|--------------|
| p1_r2a | ✗ FAIL | Full Sharpe Δ=+0.0095 < +0.01 |
| p1+p2 | ✗ FAIL | Full Sharpe Δ=+0.0083 < +0.01 |
| p5_mdq010 | ✗ FAIL | Bootstrap P=0.434 < 0.60 |
| p5_mdq012 | ✗ FAIL | Bootstrap P=0.449 < 0.60 |
| p5_pos_only | ✗ FAIL | Full Sharpe Δ=+0.0058 < +0.01; Holdout Sharpe Δ=-0.0340 < -0.02; Bootstrap P=0.043 < 0.60; Rolling w |
| p5_frag_grd | ✓ PASS |  |
| p5_mdq+frag | ✗ FAIL | Full Sharpe Δ=+0.0078 < +0.01; Bootstrap P=0.507 < 0.60 |

---

## 9. Phase 4 Fragility Guard Analysis

The Phase 4 inverted leadership composite enters the master quality score with weight 0.20.
The fragility guard additionally **CAPS** any offense increase when `phase4_fragility_adjusted < -0.50`
(i.e., when raw leadership composite > 0.50 — indicating potential late-cycle crowding).

**`phase5_fragility_guard` is the only candidate to pass all 8 Phase D gates:**

| metric | value |
|--------|-------|
| Full Sharpe | 0.9483 (Δ +0.0121) — passes +0.01 gate |
| Holdout Sharpe | 2.1786 (Δ +0.0276) |
| Max DD | −0.1160 (Δ +0.0017 — improved) |
| Bootstrap P | **0.841** — well above 0.60 |
| Rolling win | **73.3%** — above 55% |
| Extra cost | 0.029%/yr — negligible |

**How the fragility guard works:**
- Base: Phase 1 R2A offense scaling (`1 + 0.08 × clip(r2a, -1, 1)`) — same as Phase 1B
- Guard: when `phase4_fragility_adjusted < -0.50` (raw Phase 4 composite > 0.50 = market leadership looks broad, quality-led, persistent — historically a crowded/late-cycle signal), **cap the offense scale at 1.0** (prevent over-deployment)
- Reduction still applies: if quality is negative AND crowding is present, the scale can still go below 1.0
- Result: Phase 1 R2A with an asymmetric modification — we reduce in bad quality, we boost in good quality UNLESS the market also looks late-cycle/crowded

**Why the fragility guard finally clears the full-Sharpe gate:**

Phase 1 R2A alone achieved Sharpe +0.0095 (just below +0.01). The fragility guard lifts this to +0.0121 by preventing a specific class of false-positive boosts: weeks where the Phase 1 R2A signal says "deploy more" but Phase 4 leadership says "the market looks crowded, don't." By filtering these false positives, the guard improves the signal's precision.

**Phase 1+Phase 2 reference (p1+p2) note:**
p1+p2 remains the holdout champion (holdout Δ +0.043 vs +0.028 for p5_frag_grd) but fails the full-history gate (Sharpe +0.0083 < +0.01). For a production promotion, the Phase D rules require all 8 gates. `phase5_fragility_guard` is the promotable candidate.

**Phase 5 master quality candidates (p5_mdq010, p5_mdq012):**
Pass the full-Sharpe gate (+0.0105, +0.0117) but fail the bootstrap gate (P=0.434, 0.449). The holdout Sharpe is negative (−0.011, −0.008). The master quality score blending Phase 4 inverted leadership reduces holdout performance — the Phase 4 component adds signal in full history but hurts in the recent regime. The fragility guard's simpler design (Phase 4 as a cap, not a continuous blend) is more robust.

---

## 10. Verdict

**Promote to shared frontier input — `phase5_fragility_guard`**

`phase5_fragility_guard` passes all 8 Phase D gates:
- Full Sharpe Δ = **+0.0121** (first frontier candidate to clearly pass this gate)
- Holdout Sharpe Δ = **+0.0276** (strong holdout improvement)
- Bootstrap P = **0.841** (well above 0.60 gate)
- Rolling win = **73.3%** (above 55% gate)
- All tail, cost, and defense gates pass

**Design:** Phase 1 R2A offense scaling with a Phase 4 crowding cap. When Phase 4 raw leadership composite indicates a crowded/late-cycle market (raw > 0.50), the offense boost is capped at zero. This prevents over-deployment into crowded conditions while preserving the R2A signal's defensive reduction.

**The scoring function identified p1+p2 as "best" by holdout Sharpe**, but `phase5_fragility_guard` is the correct promotion candidate because it is the **only candidate passing all 8 Phase D gates**. The Phase 1+Phase 2 reference should be retained as the holdout reference benchmark.

**Updated frontier arc reference set:**
| role | strategy | key metrics |
|------|----------|------------|
| Production pin | `improved_phase2b_regime_confidence_boost` | unchanged |
| **Frontier PASS candidate** | `phase5_fragility_guard` | full Δ+0.012, holdout Δ+0.028, bootstrap 84% |
| Holdout reference | `phase1_plus_phase2_reference` | holdout Δ+0.043, bootstrap 84%, fails full gate |
| Phase 2B research reference | `phase1_rxa_plus_phase2_trend_quality` | holdout Δ+0.043, identical to p1+p2 here |

### Should Phase 5 feed into Phase 6?

Yes, in two ways:
1. **`phase5_fragility_guard` as a portfolio modifier candidate.** It passes all Phase D gates and should be tracked as the strongest promotable frontier candidate.
2. **`master_deployment_quality` as a Phase 6 feature.** The composite of Phase 1+2+4 signals should serve as a pre-conditioning feature in Phase 6 decision-focused learning, even if the direct modifier approach performs inconsistently.

---

## 11. Files Created

- `data/research/frontier_phase5/deployment_quality_allocator_results.csv`
- `data/research/frontier_phase5/deployment_quality_allocator_holdout_summary.csv`
- `data/research/frontier_phase5/deployment_quality_allocator_state_summary.csv`
- `data/research/frontier_phase5/deployment_quality_allocator_phase_d_gates.csv`
- `data/research/frontier_phase5/master_deployment_quality_timeseries.csv`
- `docs/research/frontier_phase5_allocator_objective_report.md`

## 12. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified