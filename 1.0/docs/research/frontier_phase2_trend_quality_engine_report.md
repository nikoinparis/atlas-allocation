# Frontier Phase 2B: Trend Quality Engine — Wrapper Experiment Report

**Date:** 2026-05-20
**Mode:** Diagnostic-only — no production or dashboard files modified
**Best candidate:** `phase1_r2a_plus_phase2_trend_quality`

---

## 1. Sprint Summary

Phase 2B applies the Phase 2A trend quality and ma_distance_z signals as state-specific offensive ETF reweighting inside `recovery_confirmed` and `neutral_mixed` states only (where Phase 2A IC was positive). Signals are NOT applied in stressed_panic, recovery_fragile, or calm_trend. Phase 1 R2A uniform offense scaling is also included as a standalone and stacked candidate for comparison.

### Architecture Note

The wrapper's checkpoint mechanism applies a uniform multiplier to all offensive ETFs. Phase 2 requires *differential* per-ETF multipliers based on cross-sectional quality rank. This is not directly supported by a named checkpoint hook, so Phase 2 scaling is applied as a post-processing step on the final ETF weights before `production_portfolio_path` recomputes the path. Turnover and cost accounting are correct because `production_portfolio_path` derives turnover from the modified weight matrix.

---

## 2. Commands Run

```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier2_wrapper_experiment.py
```

---

## 3. Phase 2A Signal Recap

| state | trend_quality_IC | ma_distance_IC | used in Phase 2B? |
|-------|-----------------|---------------|-------------------|
| recovery_confirmed | +0.073 | N/A | ✓ YES |
| neutral_mixed | +0.024 | N/A | ✓ YES |
| calm_trend | +0.011 | N/A | ✗ NO (marginal) |
| recovery_fragile | −0.015 | N/A | ✗ NO (negative) |
| stressed_panic | −0.002 | N/A | ✗ NO (zero + defense) |

---

## 4. Full-History Metrics

| metric | baseline | p1_r2a | p2_tq | p2_ma | p1+p2_tq | p1+p2_ma |
|--------|------|------|------|------|------|------|
| Ann return | 7.14% | 7.13% | 7.16% | 7.21% | 7.15% | 7.21% |
| Sharpe | 0.9362 | 0.9457 | 0.9355 | 0.9389 | 0.9445 | 0.9480 |
| Max DD | -0.1177 | -0.1160 | -0.1175 | -0.1174 | -0.1160 | -0.1160 |
| CVaR 5% | -0.0254 | -0.0250 | -0.0255 | -0.0256 | -0.0252 | -0.0253 |
| Avg TO/wk | 0.0618 | 0.0680 | 0.0653 | 0.0652 | 0.0708 | 0.0706 |
| Avg BIL | 26.66% | 27.44% | 26.66% | 26.66% | 27.44% | 27.44% |
| Avg offense | 41.62% | 40.90% | 41.62% | 41.62% | 40.90% | 40.90% |
| Hidden β SPY | 0.2431 | 0.2412 | 0.2440 | 0.2452 | 0.2421 | 0.2433 |

*Sharpe deltas vs baseline:*
- baseline: +0.0000
- p1_r2a: +0.0095
- p2_tq: -0.0006
- p2_ma: +0.0027
- p1+p2_tq: +0.0083
- p1+p2_ma: +0.0119

---

## 5. Holdout Metrics (from 2024-04-19)

| metric | baseline | p1_r2a | p2_tq | p2_ma | p1+p2_tq | p1+p2_ma |
|--------|----------|--------|-------|-------|----------|----------|
| Return | 17.89% | 17.94% | 17.97% | 17.99% | 18.02% | 18.04% |
| Sharpe | 2.1510 | 2.1723 | 2.1738 | 2.1237 | 2.1943 | 2.1441 |
| Max DD | -0.0725 | -0.0729 | -0.0731 | -0.0749 | -0.0734 | -0.0752 |
| Avg BIL | 12.25% | 12.35% | 12.25% | 12.25% | 12.35% | 12.35% |

*Holdout Sharpe deltas vs baseline:*
- baseline: +0.0000
- p1_r2a: +0.0213
- p2_tq: +0.0228
- p2_ma: -0.0273
- p1+p2_tq: +0.0433
- p1+p2_ma: -0.0069

---

## 6. State-by-State (primary candidate vs baseline, full history)

Active Phase 2 states are recovery_confirmed and neutral_mixed.

| state | base_sharpe | base_capture | best_sharpe | best_capture | Δ_sharpe |
|-------|-------------|--------------|-------------|--------------|----------|
| calm_trend | 0.5136 | 0.4735 | 0.5269 | 0.4684 | +0.0133 |
| neutral_mixed ← active | 1.4616 | 0.9457 | 1.4680 | 0.9518 | +0.0064 |
| recovery_confirmed ← active | 0.3443 | 0.3955 | 0.3021 | 0.3626 | -0.0422 |
| recovery_fragile | 1.1421 | 0.2476 | 1.1580 | 0.2511 | +0.0158 |
| stressed_panic | 0.4807 | 0.4640 | 0.4779 | 0.4613 | -0.0028 |

---

## 7. Rolling-Origin and Bootstrap

| candidate | rolling_win_rate | bootstrap_P | mean_bs_delta | CI_95 |
|-----------|-----------------|-------------|---------------|-------|
| p1_r2a | 66.7% | 0.719 | +0.0193 | [-0.0493, +0.0829] |
| p2_tq | 46.7% | 0.930 | +0.0319 | [-0.0092, +0.0716] |
| p2_ma | 33.3% | 0.070 | -0.0254 | [-0.0602, +0.0091] |
| p1+p2_tq | 66.7% | 0.844 | +0.0504 | [-0.0454, +0.1372] |
| p1+p2_ma | 53.3% | 0.460 | -0.0072 | [-0.0936, +0.0681] |

---

## 8. Phase D Gate Summary

| candidate | gate_verdict | key_failures |
|-----------|-------------|--------------|
| p1_r2a | ✗ FAIL | Full-history Sharpe Δ=+0.0095 < +0.01 |
| p2_tq | ✗ FAIL | Full-history Sharpe Δ=-0.0006 < +0.01; Rolling win rate=46.7% < 55% |
| p2_ma | ✗ FAIL | Full-history Sharpe Δ=+0.0027 < +0.01; Holdout Sharpe Δ=-0.0273 < -0.02; Bootstr |
| p1+p2_tq | ✗ FAIL | Full-history Sharpe Δ=+0.0083 < +0.01 |
| p1+p2_ma | ✗ FAIL | Bootstrap P(cand>base)=0.460 < 0.60; Rolling win rate=53.3% < 55% |

---

## 9. ma_distance_z vs Trend Quality Composite Comparison

- trend_quality composite: full Sharpe=0.9355, holdout=2.1738
- ma_distance_z:           full Sharpe=0.9389, holdout=2.1237
- **Better on holdout:** trend_quality

---

## 10. Holdout Warning

Phase 2A showed holdout IC = −0.014 for the trend_quality composite (t=−0.69). Phase 2B tests whether this signal failure translates to portfolio-level holdout regression. The holdout Sharpe delta above is the primary gate for the final verdict. Any candidate with holdout Sharpe Δ < −0.02 is classified research-only regardless of full-history performance.

---

## 11. Verdict

**Keep as research-only diagnostic**

Best candidate (phase1_r2a_plus_phase2_trend_quality) shows directional improvement (full Δ=+0.0083, holdout Δ=+0.0433) but full-history Sharpe gain is below +0.01. Classify as research-only. Phase 2 quality signal may still feed Phase 3 (re-risking) as a quality confirmation signal.

### Should Phase 2 feed into Phases 3, 4, 5?

Conditionally. The Phase 2 signals did not demonstrate clear portfolio improvement, but the signal content is real (partial IC +0.008, recovery_confirmed IC +0.073). They should be used as:
- **Phase 3 quality confirmation inputs** (not as portfolio modifiers): trend_quality of the broad market is an input to the re-risk quality score.
- **Phase 4 leadership ranking**: trend_quality is a natural component of an ETF leadership quality index.
**Do NOT** apply Phase 2 ETF-level reweighting as a standalone portfolio modifier until the holdout issue is resolved.

---

## 12. Files Created

- `data/research/frontier_phase2/wrapper_experiment_results.csv`
- `data/research/frontier_phase2/wrapper_experiment_holdout_summary.csv`
- `data/research/frontier_phase2/wrapper_experiment_state_summary.csv`
- `data/research/frontier_phase2/wrapper_experiment_phase_d_gates.csv`
- `docs/research/frontier_phase2_trend_quality_engine_report.md`

## 13. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified
