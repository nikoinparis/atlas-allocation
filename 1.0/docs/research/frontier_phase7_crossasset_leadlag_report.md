# Frontier Phase 7A: Cross-Asset Relational Intelligence Report

**Date:** 2026-05-22
**Mode:** Diagnostic-only — no production or dashboard files modified

---

## 1. Sprint Summary

Phase 7A tests five cross-asset lead-lag pairs for stable, causal relationships. Rolling 52-week correlations (using `A.shift(lag).rolling(52).corr(B)`) ensure all computations are causal at date t.  The top-3 stable pairs are combined into a cross-asset confirmation score and validated via IC vs SPY 4-week forward return.

---

## 2. Commands Run
```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier7_crossasset_leadlag.py
```

---

## 3. Lead-Lag Stability Diagnostics

| pair | lag | mean_corr | std_corr | pct>0.15 | sign_cons | stability |
|------|-----|-----------|----------|---------|-----------|-----------|
| GLD_to_TLT | 1 | 0.0263 | 0.1682 | 0.39 | 0.58 | 0.485 |
| GLD_to_TLT | 2 | -0.0122 | 0.1022 | 0.14 | 0.53 | 0.336 |
| GLD_to_TLT | 4 | -0.0015 | 0.1153 | 0.20 | 0.49 | 0.344 |
| GLD_to_TLT | 8 | 0.0047 | 0.1334 | 0.29 | 0.51 | 0.397 |
| HYG_LQD_to_SPY | 1 | -0.1005 | 0.1062 | 0.36 | 0.82 | 0.592 |
| HYG_LQD_to_SPY | 2 | -0.0009 | 0.1549 | 0.30 | 0.43 | 0.364 |
| HYG_LQD_to_SPY | 4 | -0.0107 | 0.1676 | 0.39 | 0.55 | 0.472 |
| HYG_LQD_to_SPY | 8 | 0.0187 | 0.1601 | 0.37 | 0.58 | 0.472 |
| IWM_SPY_to_SPY | 1 | 0.0113 | 0.1651 | 0.37 | 0.48 | 0.425 |
| IWM_SPY_to_SPY | 2 | 0.0045 | 0.1267 | 0.25 | 0.52 | 0.382 |
| IWM_SPY_to_SPY | 4 | 0.0295 | 0.1568 | 0.38 | 0.55 | 0.461 |
| IWM_SPY_to_SPY | 8 | 0.0261 | 0.1497 | 0.34 | 0.50 | 0.421 |
| TLT_to_SPY | 1 | 0.0972 | 0.1145 | 0.37 | 0.80 | 0.589 |
| TLT_to_SPY | 2 | -0.0420 | 0.1547 | 0.30 | 0.64 | 0.473 |
| TLT_to_SPY | 4 | 0.0147 | 0.1478 | 0.33 | 0.58 | 0.456 |
| TLT_to_SPY | 8 | -0.0340 | 0.1374 | 0.30 | 0.64 | 0.472 |
| UUP_to_VWO | 1 | -0.0123 | 0.1682 | 0.41 | 0.54 | 0.478 |
| UUP_to_VWO | 2 | 0.0106 | 0.1387 | 0.28 | 0.51 | 0.398 |
| UUP_to_VWO | 4 | 0.0185 | 0.1334 | 0.29 | 0.53 | 0.411 |
| UUP_to_VWO | 8 | -0.0032 | 0.1346 | 0.28 | 0.50 | 0.391 |

---

## 4. Top Pairs by Stability

| rank | pair | best_lag | stability_score | mean_corr | stable? |
|------|------|----------|----------------|-----------|---------|
| 1 | HYG_LQD_to_SPY | 1 | 0.592 | -0.1005 | ✗ |
| 2 | TLT_to_SPY | 1 | 0.589 | 0.0972 | ✗ |
| 3 | GLD_to_TLT | 1 | 0.485 | 0.0263 | ✗ |
| 4 | UUP_to_VWO | 1 | 0.478 | -0.0123 | ✗ |
| 5 | IWM_SPY_to_SPY | 4 | 0.461 | 0.0295 | ✗ |

**Stable pairs (≥0.6): 0/5**

---

## 5. Cross-Asset Confirmation Score Construction

Built from top-3 pairs:
- HYG_LQD_to_SPY: mean_corr=-0.1005  best_lag=1
- TLT_to_SPY: mean_corr=0.0972  best_lag=1
- GLD_to_TLT: mean_corr=0.0263  best_lag=1

Formula: for each selected pair, `a_direction × expected_sign` where a_direction = sign(4w momentum of leader), expected_sign = sign(full-period mean corr). Average across pairs, expanding z-score, 1-week lag.

---

## 6. IC vs SPY 4-Week Forward Return

| scope | IC | n |
|-------|----|---|
| full | -0.0217 | 1105 |
| dev | -0.0094 | 1005 |
| holdout | -0.0858 | 100 |
| state_calm_trend | -0.0165 | 295 |
| state_neutral_mixed | -0.0442 | 490 |
| state_recovery_confirmed | 0.0477 | 43 |
| state_recovery_fragile | -0.1135 | 49 |
| state_stressed_panic | 0.0103 | 228 |

---

## 7. Transition-Specific IC

| window | n | IC |
|--------|---|-----|
| pre_stress | 122 | 0.0255 |
| post_stress | 116 | -0.1240 |
| recovery_all | 92 | -0.0231 |

---

## 8. Partial IC (after Phase 1 R2A + Phase 2 avg_tq + Phase 5 MDQ)

| scope | partial_IC |
|-------|-----------|
| full | -0.0202 |
| dev | 0.0035 |
| holdout | -0.1355 |

- corr(CA_score, Phase1_R2A): 0.0151
- corr(CA_score, Phase5_MDQ): -0.0088

---

## 9. Acceptance Gate Results

**✗ FAIL**

- ✓ Positive IC in at least one transition/recovery window
- ✓ Not a duplicate (rho_p1=+0.015, rho_p5=-0.009)
- ✗ Only 0/5 pairs stable (<3 needed)
- ✗ Holdout IC broken: -0.0858
- ✗ Partial IC not positive: -0.0202

---

## 10. Structural Diagnosis

**No lead-lag pairs reach the 0.60 stability threshold at weekly resolution.** The closest are HYG/LQD→SPY (0.592) and TLT→SPY (0.589) at 1-week lag. The stability scores are close to the threshold but don't clear it — the rolling 52-week correlations flip signs too often to be reliable.

**The IC is negative for the same structural reason as Phase 4 leadership signals.** The cross-asset confirmation score is built from:
- HYG/LQD (credit risk appetite): mean_corr = -0.100 with SPY — counter-intuitive, credit strength → lower next-week SPY
- TLT (bonds): mean_corr = +0.097 with SPY — bonds rallying → higher next-week SPY (also counter-intuitive)

Both relationships are likely capturing late-cycle/mean-reversion dynamics at 1-week resolution rather than the expected causal channel. The cross-asset relationships ARE real economically, but they operate at monthly or quarterly time scales, not weekly. At weekly resolution, noise dominates.

**Two positive signals worth noting:**
1. `pre_stress` IC = +0.025 (n=122): The score has weak positive IC in the 4 weeks BEFORE stress episodes, suggesting some faint warning content.
2. `recovery_confirmed` IC = +0.048 (n=43): Positive in recovery_confirmed, consistent with credit/bond confirming recovery.

Neither is strong enough or stable enough to justify a portfolio modifier.

**The frontier arc has now completed Phases 1–7.** No new cross-asset signal was found that passes the acceptance criteria. The project has reached the information ceiling of the current ETF/weekly universe.

---

## 11. Verdict

**Keep as diagnostic-only — Phase 7B not justified**

No Phase 7B wrapper experiment should be run. The cross-asset signals fail 3 of 5 acceptance gates:
- Stability: 0/5 pairs (closest: 0.592, 0.589 — below 0.60 threshold)
- Holdout IC: −0.086 (broken)
- Partial IC: −0.020 (negative)

**The frontier arc conclusion:**

After 7 phases of diagnostic and experimental work, the strongest frontier portfolio modifier is `phase5_fragility_guard` (Phase 5A):
- Full-history Sharpe Δ = +0.012 (passes the +0.01 gate)
- Holdout Sharpe Δ = +0.028
- Bootstrap P = 0.841
- Rolling win rate = 73.3%
- All 8 Phase D gates pass
- Stressed-panic preserved

This is the recommended candidate for Phase 10 (Final Production Candidate Evaluation). The project should move to Phase 10 evaluation without opening further diagnostic phases unless new data (PIT breadth, broader universe) becomes available.

---

## 11. Files Created

- `data/research/frontier_phase7/leadlag_stability_diagnostics.csv`
- `data/research/frontier_phase7/cross_asset_confirmation_score.csv`
- `data/research/frontier_phase7/cross_asset_confirmation_ic.csv`
- `data/research/frontier_phase7/cross_asset_transition_ic.csv`
- `docs/research/frontier_phase7_crossasset_leadlag_report.md`

## 12. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified