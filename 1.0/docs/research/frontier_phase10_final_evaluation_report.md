# Frontier Phase 10A: Final Production Candidate Evaluation Report

**Date:** 2026-05-22
**Primary candidate:** `phase5_fragility_guard`
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Shadow pin:** `improved_phase2b_combo_abc`

---

## 1. Sprint Summary

Final governance evaluation for the frontier arc (Phases 1–7). phase5_fragility_guard is evaluated against the GGG baseline, production pin, and shadow pin using the full Phase D 8-gate framework plus governance checks.

---

## 2. Commands Run
```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier10_final_evaluation.py
```

---

## 3. Frontier Arc Summary (Phases 1–7)

| phase | result |
|-------|--------|
| Phase 1 (state quality) | R2A signal validated; portfolio modifier borderline |
| Phase 2 (trend quality) | Signal validated; ETF scaling research-only |
| Phase 3 (re-risking) | Gate calibration failure; signals useful as inputs |
| Phase 4 (leadership) | Anti-predictive; inverted as fragility guardrail in Phase 5 |
| Phase 5 (allocator) | phase5_fragility_guard PASSES all 8 Phase D gates |
| Phase 6 (ML) | Model beats naive; portfolio switching failed |
| Phase 7 (cross-asset) | 0/5 stable pairs; diagnostic-only |

---

## 4. Full-History Candidate Comparison

| metric | prod_pin | shadow_pin | ggg | p1_r2a | p1+p2 | p5_fg (CANDIDATE) |
|--------|------|------|------|------|------|------|
| Ann ret | 6.89% | 6.86% | 7.14% | 7.13% | 7.15% | 7.13% |
| Sharpe | 0.8844 | 0.8836 | 0.9362 | 0.9457 | 0.9445 | 0.9483 |
| Max DD | -0.1398 | -0.1367 | -0.1177 | -0.1160 | -0.1160 | -0.1160 |
| CVaR 5% | -0.0262 | -0.0261 | -0.0254 | -0.0250 | -0.0252 | -0.0249 |
| TO/wk | 0.0562 | 0.0566 | 0.0618 | 0.0680 | 0.0708 | 0.0674 |
| Cost/yr | 0.29% | 0.29% | 0.32% | 0.35% | 0.37% | 0.35% |
| BIL | 28.39% | 28.56% | 26.66% | 27.44% | 27.44% | 27.61% |
| Offense | 42.83% | 42.75% | 41.62% | 40.90% | 40.90% | 40.72% |
| β SPY | 0.2514 | 0.2501 | 0.2431 | 0.2412 | 0.2421 | 0.2402 |

---

## 5. Holdout Metrics (from 2024-04-19)

| metric | prod_pin | shadow_pin | ggg | p1_r2a | p1+p2 | p5_fg (CANDIDATE) |
|--------|------|------|------|------|------|------|
| Return | 15.37% | 15.36% | 17.89% | 17.94% | 18.02% | 17.91% |
| Sharpe | 2.0996 | 2.1130 | 2.1510 | 2.1723 | 2.1943 | 2.1786 |
| Max DD | -0.0566 | -0.0553 | -0.0725 | -0.0729 | -0.0734 | -0.0729 |

*Holdout Sharpe deltas:*
- prod_pin: vs GGG -0.0514
- shadow_pin: vs GGG -0.0380
- ggg: vs GGG +0.0000
- p1_r2a: vs GGG +0.0213
- p1+p2: vs GGG +0.0433
- p5_fg (CANDIDATE): vs GGG +0.0276

---

## 6. Phase D Gate Evaluation

### Phase5_FG vs GGG baseline

**✓ PASS**

- ✓ Full Sharpe Δ=+0.0121 ≥ +0.01
- ✓ Holdout Sharpe Δ=+0.0276 ≥ -0.02
- ✓ MaxDD Δ=+0.0017 ≥ -0.01
- ✓ CVaR Δ=+0.0004 ≥ -0.002
- ✓ SP Sharpe Δ=-0.0014 (intact)
- ✓ Extra cost=0.029% (< 0.15%)
- ✓ Bootstrap P=0.841 ≥ 0.60
- ✓ Rolling win=73.3% ≥ 55%

### Phase5_FG vs Production pin

**✓ PASS**

- ✓ Full Sharpe Δ=+0.0638 ≥ +0.01
- ✓ Holdout Sharpe Δ=+0.0790 ≥ -0.02
- ✓ MaxDD Δ=+0.0237 ≥ -0.01
- ✓ CVaR Δ=+0.0012 ≥ -0.002
- ✓ SP Sharpe Δ=-0.0174 (intact)
- ✓ Extra cost=0.058% (< 0.15%)
- ✓ Bootstrap P=0.842 ≥ 0.60
- ✓ Rolling win=73.3% ≥ 55%

---

## 7. Rolling-Origin and Bootstrap

| comparison | rolling_win | bootstrap_P | mean_Δ | CI_95 |
|------------|------------|------------|--------|-------|
| FG_vs_GGG | 73.3% | 0.841 | +0.0298 | [-0.0228, +0.0806] |
| FG_vs_PROD | 73.3% | 0.842 | +0.1740 | [-0.2075, +0.4793] |

---

## 8. Governance Checks (FG vs GGG)

| check | value | result |
|-------|-------|--------|
| Hidden beta Δ | -0.0029 | ✓ OK |
| BIL Δ | +0.0095 | ✓ OK |
| Offense Δ | -0.0091 | ✓ |
| Stressed-panic defense | — | ✓ intact |

---

## 9. State-by-State (phase5_fg vs production_pin)

| state | prod_sharpe | prod_capture | fg_sharpe | fg_capture | Δsharpe |
|-------|-------------|-------------|-----------|------------|---------|
| calm_trend | 0.3843 | 0.4124 | 0.5277 | 0.4692 | +0.1434 |
| neutral_mixed | 1.4622 | 0.9315 | 1.4739 | 0.9472 | +0.0117 |
| recovery_confirmed | 0.3847 | 0.4005 | 0.3387 | 0.3887 | -0.0460 |
| recovery_fragile | 1.3168 | 0.2590 | 1.1570 | 0.2497 | -0.1599 |
| stressed_panic | 0.4967 | 0.4367 | 0.4793 | 0.4626 | -0.0174 |

---

## 10. Final Verdict

**Promote**

phase5_fragility_guard passes all 8 Phase D gates vs GGG baseline and all governance checks. Full Sharpe Δ=+0.0121, holdout Δ=+0.0276, bootstrap P=0.841, rolling win=73.3%. Recommend as production candidate pending human deployment review.

### Production Governance Recommendation

phase5_fragility_guard is ready for a human deployment review as a production candidate. To promote:
1. Update CLAUDE.md: set `production candidate (pending)` to `phase5_fragility_guard`
2. Run full dashboard review with the new candidate exposed
3. Human review of state-by-state behavior, particularly recovery_confirmed capture
4. Only after human review: update the production pin via explicit CLAUDE.md change

**Do NOT run automated production pin updates.** This report is the research recommendation only. Final deployment authority rests with human review.

---

## 11. Files Created

- `data/research/frontier_phase10/final_candidate_metrics.csv`
- `data/research/frontier_phase10/final_candidate_holdout_summary.csv`
- `data/research/frontier_phase10/final_candidate_state_summary.csv`
- `data/research/frontier_phase10/final_candidate_phase_d_gates.csv`
- `data/research/frontier_phase10/final_candidate_bootstrap_summary.csv`
- `data/research/frontier_phase10/final_candidate_rolling_origin.csv`
- `docs/research/frontier_phase10_final_evaluation_report.md`

## 12. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: **UNCHANGED**
- No public/, src/, dashboard, or registry files modified
- All candidate outputs are research artifacts only