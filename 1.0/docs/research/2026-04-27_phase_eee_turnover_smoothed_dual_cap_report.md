# Phase EEE — Turnover-Smoothed Aggressive Dual Cap

**Date:** 2026-04-27
**Phase type:** Bounded turnover-smoothing on top of DDD2's aggressive dual cap. Recovery_confirmed only. recovery_fragile, strong_neutral, stressed_panic preserved unchanged.
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Official shadow pin (unchanged):** `improved_phase2b_combo_abc`
**Architecture-reference shadow (this phase):** DDD1 → **EEE1 (`improved_phaseeee_smoothed_near_exclude_dual`)**.

---

## 1. Commands executed

```
python scripts/phase_eee_turnover_smoothed_dual_cap.py
  └── invokes scripts/build_improvement_artifacts.py with
       BUILD_VERSION_NAMES=3 EEE + 5 references
python scripts/research_committee_report.py improved_phaseeee_smoothed_near_exclude_dual --quick
python scripts/backtest_realism_audit.py     improved_phaseeee_smoothed_near_exclude_dual --quick
python scripts/allocator_benchmark_audit.py  improved_phaseeee_smoothed_near_exclude_dual --quick
```

## 2. Files created or modified

- `scripts/phase_eee_turnover_smoothed_dual_cap.py` (new — driver).
- `scripts/build_improvement_artifacts.py` — 3 new version specs only (no new tilt branches; reuse `phase_ddd_confirmed_near_exclude_dual` and `phase_ddd_confirmed_harder_dual_cap` with lowered `rerisk_speed`).
- 9 portfolio_version_*** CSVs for the 3 EEE candidates.
- `data/research/phase_eee_turnover_smoothed_dual_cap/{phase_eee_turnover_diagnostics, phase_eee_turnover_spike_weeks, phase_eee_candidate_diagnostics}.csv`
- `data/05_layer3_portfolio_construction/phase_eee_{candidate_metrics_full, state_summary, selection_table}.csv` + `phase_eee_protocol.json`.
- `reports/research_committee/improved_phaseeee_smoothed_near_exclude_dual_audit.md`
- `reports/backtest_realism/improved_phaseeee_smoothed_near_exclude_dual_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseeee_smoothed_near_exclude_dual_allocator_benchmark.md`
- `docs/research/2026-04-27_phase_eee_turnover_smoothed_dual_cap_report.md` (this file)
- `docs/research/project_journey.md` — Section 57 appended.

## 3. Turnover diagnosis

`recovery_confirmed`-only avg weekly L1 turnover by version:

| version | rec_confirmed avg turnover | full-window avg | full ratio vs prod |
|---|---:|---:|---:|
| production | 0.1154 | 0.1124 | 1.000× |
| CCC2 | 0.1664 | 0.1228 | 1.092× |
| **DDD1** | 0.1718 | 0.1234 | 1.098× ✓ |
| **DDD2 (failed turnover)** | **0.1762** | **0.1238** | **1.101× ✗** |
| **EEE1 smoothed (rerisk 0.80)** | **0.1665** | **0.1230** | **1.095× ✓** |
| EEE2 (rerisk 0.90) | 0.1712 | 0.1234 | 1.098× ✓ |
| EEE3 (rerisk 0.95) | 0.1695 | 0.1232 | 1.096× ✓ |

## 4. Source of DDD2's turnover breach

DDD2 used `rerisk_speed=1.00`, meaning the production overlay's `dynamic_speed` was set to 1.0 in `recovery_confirmed`, fully re-risking sleeve weights every rebalance. With the aggressive 0.03 dual cap, that produced a 0.1762 avg recovery_confirmed turnover (vs production 0.1154). The full-window ratio of 1.101× narrowly exceeded the 1.10× gate.

The smoothing fix is structural rather than logical: lower `rerisk_speed` so the overlay's `dynamic_speed` mechanism partially smooths cap engagement transitions across consecutive weekly rebalances. EEE1 sets rerisk_speed=0.80 and brings turnover down to 1.095× while preserving (and slightly extending) DDD2's recovery_confirmed repair.

## 5. Candidate family tested

- **EEE1** `smoothed_near_exclude_dual` — DDD2 tilt (cap 0.03) + rerisk_speed 0.80.
- **EEE2** `turnover_aware_dual_cap` — DDD2 tilt (cap 0.03) + rerisk_speed 0.90.
- **EEE3** `selective_dual_escalation` — DDD1 tilt (cap 0.07) + rerisk_speed 0.95.

## 6. Candidate metrics table (full window)

```
                                         name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_BIL  avg_SPY  avg_turnover
 improved_phaseeee_smoothed_near_exclude_dual         0.0713       0.9353            -0.1177      -0.0254   0.2665   0.0602        0.1230
    improved_phaseeee_turnover_aware_dual_cap         0.0714       0.9371            -0.1175      -0.0254   0.2672   0.0602        0.1234
  improved_phaseeee_selective_dual_escalation         0.0714       0.9375            -0.1175      -0.0253   0.2671   0.0603        0.1232
       improved_phase2b_regime_confidence_boost       0.0689       0.8848            -0.1398      -0.0262   0.2839   0.0708        0.1124
                       improved_phaseccc_confirmed_cap_dual   0.0714  0.9376  -0.1175  -0.0253   0.2668   0.0606   0.1228
                improved_phaseddd_confirmed_harder_dual_cap   0.0714  0.9379  -0.1175  -0.0253   0.2673   0.0604   0.1234
              improved_phaseddd_confirmed_near_exclude_dual   0.0715  0.9379  -0.1175  -0.0253   0.2678   0.0602   0.1238
```

## 7. Turnover ratio check (vs 1.10× production gate)

| candidate | turnover ratio | passes 1.10× gate |
|---|---:|---|
| EEE1 | 1.095× | **✓** |
| EEE2 | 1.098× | ✓ |
| EEE3 | 1.096× | ✓ |
| DDD1 (reference) | 1.098× | ✓ |
| DDD2 (reference, failed) | 1.101× | ✗ |

All three EEE candidates clear the turnover gate.

## 8. Recovery_confirmed repair check

| candidate | RC delta vs production | RC delta vs DDD1 | RC delta vs DDD2 |
|---|---:|---:|---:|
| **EEE1 (best RC repair)** | **-0.36pp** | **+0.16pp** | **+0.07pp** ← beats DDD2 too |
| EEE2 | -0.39pp | +0.12pp | +0.04pp |
| EEE3 | -0.49pp | +0.03pp | -0.05pp |
| DDD1 (baseline) | -0.51pp | — | -0.08pp |
| DDD2 (reference, failed turnover) | -0.43pp | +0.08pp | — |

**EEE1 actually IMPROVES on DDD2's recovery_confirmed repair while passing the turnover gate.** This is the cleanest result of the phase.

## 9. Recovery_fragile preservation check

| candidate | RF delta vs production | RF delta vs DDD1 |
|---|---:|---:|
| EEE1 | preserved | -0.17pp (slight regression vs DDD1) |
| EEE2 | preserved | -0.06pp |
| EEE3 | preserved | -0.05pp |

EEE1 has the largest recovery_fragile regression vs DDD1 (-0.17pp), which is within the strict -0.30pp tolerance. The smoothing slightly reduces recovery_fragile participation. EEE2 and EEE3 preserve recovery_fragile better.

## 10. Stressed_panic protection check

EEE1 stressed_panic delta vs production: **+0.22pp** (matches DDD1/CCC2/BBB3). Upstream stressed_panic guardrails unchanged. Protection PRESERVED for all three EEE candidates.

## 11. Full state-by-state impact (EEE1)

(Detailed table in `data/05_layer3_portfolio_construction/phase_eee_state_summary.csv`.) Calm_trend / neutral_mixed positive vs production; recovery_confirmed -0.36pp (closing 30% of CCC2's gap and 15% of DDD1's gap); recovery_fragile preserved vs production; stressed_panic +0.22pp protected.

## 12. Comparison vs production, DDD1, and DDD2

| metric | production | DDD1 | DDD2 (failed) | **EEE1 (best)** |
|---|---:|---:|---:|---:|
| ann return | 6.89% | 7.14% | 7.15% | **7.13%** |
| Sharpe | 0.8848 | 0.9379 | 0.9379 | **0.9353** |
| MDD | -13.98% | -11.75% | -11.75% | -11.77% |
| CVaR-5% | -2.62% | -2.53% | -2.53% | -2.54% |
| avg BIL | 28.39% | 26.73% | 26.78% | 26.65% |
| avg SPY | 7.08% | 6.04% | 6.02% | **6.02%** |
| RC delta vs prod | — | -0.51pp | -0.43pp | **-0.36pp** ← best |
| turnover ratio | 1.00× | 1.098× | **1.101×** ✗ | **1.095×** ✓ |

EEE1 is essentially DDD1 on full-window metrics (Sharpe -0.0026 vs DDD1, ann return -0.01pp vs DDD1) but achieves the recovery_confirmed repair that DDD2 was reaching for, AND stays under the turnover cap. This is the goal of the phase.

## 13. Hidden beta / hidden cash check

EEE1 SPY exposure: **6.02%** (vs production 7.08% — LOWER by 1.06pp; vs DDD1 6.04% — slightly LOWER). EEE1 BIL: 26.65% (vs production 28.39% — LOWER). No hidden beta. Decomposition intact (explicit cash sleeve still ~0.33).

## 14. Best candidate

**EEE1 — `improved_phaseeee_smoothed_near_exclude_dual`.**

Reasons:
- Largest recovery_confirmed repair of any candidate in this branch (-0.36pp vs production; +0.16pp vs DDD1; +0.07pp vs DDD2).
- Stays under 1.10× turnover gate (1.095×).
- Sharpe within tolerance vs DDD1 (-0.0026, well within -0.02 strict gate).
- Preserves stressed_panic (+0.22pp vs production).
- recovery_fragile preserved vs production; -0.17pp regression vs DDD1 (within -0.30pp tolerance).
- No hidden beta; SPY lower than DDD1 and production.
- Decomposition intact.
- Passes ALL strict gates.

The script's automatic sort by Sharpe initially picked EEE3, but EEE3 has the SMALLEST recovery_confirmed repair (+0.026pp vs DDD1) and so is essentially equivalent to DDD1. EEE1 best matches the spec's stated goal: recover DDD2's stronger recovery_confirmed repair.

## 15. Quick committee verdict

**KEEP AS SHADOW** (Layer 2). "Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow." (Same standard Phase D rule wording.)

## 16. Were Layer 5/6 quick audits run?

**Yes** — quick committee returned KEEP AS SHADOW with both Sharpe and MDD improving. Both audits ran:
- **Layer 5 (realism --quick):** Δ ann return at 5bp = **+0.26pp**; at 10bp = **+0.24pp**; at 1-week delay = **+0.37pp**. Improvement is robust to stricter assumptions.
- **Layer 6 (allocator benchmark --quick):** "**Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed.**"

## 17. Final decision

**KEEP AS SHADOW** — `improved_phaseeee_smoothed_near_exclude_dual` is the new strongest architecture-reference shadow on the decomposed-allocator branch, replacing DDD1 in that role.

Why **NOT** PRODUCTION CHALLENGER PENDING HUMAN REVIEW: the spec requires "does not materially worsen recovery_confirmed or recovery_fragile" vs production. EEE1's recovery_confirmed at -0.36pp ann return is still materially worse than production (though substantially narrower than CCC2/DDD1). The recovery_confirmed gap is closer to closed but not yet there.

Why **NOT** REJECT or NEEDS FIX BEFORE JUDGMENT: EEE1 passes every strict gate, repairs recovery_confirmed materially vs DDD1 AND vs DDD2, preserves stressed_panic, passes Layer 5/6 decisively, has no hidden beta.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin (official) remains unchanged**: `improved_phase2b_combo_abc`. **Architecture-reference shadow** is now EEE1 (replacing DDD1).

## 18. Should turnover-smoothed dual cap continue?

**APPROACHING EXHAUSTION but one more bounded test is honest.** The recovery_confirmed gap closure sequence: YY -1.04pp → ZZ2 -0.91pp → AAA2 -0.72pp → BBB3 -0.67pp → CCC2 -0.61pp → DDD1 -0.51pp → **EEE1 -0.36pp**. Each step closes 0.05-0.20pp; EEE1's +0.16pp vs DDD1 is one of the larger jumps. But the marginal full-window cost is now showing up: EEE1's Sharpe (0.9353) is below DDD1's (0.9379) by 0.0026 — small but the first time in the YY→DDD1 sequence we lost Sharpe.

The natural bounded next test is rerisk_speed=0.85 (between EEE1's 0.80 and EEE2's 0.90) to find whether there's a spot that recovers more of DDD1's Sharpe while preserving EEE1's recovery_confirmed gain. If even that fails to push recovery_confirmed below -0.30pp without losing Sharpe, **mark this branch BRANCH EXHAUSTED**.

## 19. Recommended next phase if this fails

If a Phase FFF-class fine-tuning of rerisk_speed cannot push recovery_confirmed below -0.30pp without breaking another gate, the current confirmed-state offense-mix hypothesis is exhausted. The next architecture frontier should be ONE of:

1. **Layer 2A re-engineering of `composite_regime_offense_component`.** The synthetic offense component is constructed by re-projecting source `composite_regime_conditioned` positions onto offense ETFs. A Layer 2A refinement could rebuild it specifically to maximise recovery_confirmed Sharpe within the source-position constraint. This is structural sleeve-design work, not allocator-parameter tuning.
2. **Per-state `target_vol_ceil` escalation in recovery_confirmed.** Current ceiling is 1.00. A confirmed-only ceiling of 1.05-1.10 could allow more participation in this single state without affecting others.
3. **Recovery_confirmed-only `composite_regime_offense_component` direct boost** via a new tilt-mode parameter that adds a small additive multiplier to the offense_component AFTER the bucket budget.

---

## Appendix — Phase EEE classification matrix

| candidate | rerisk_speed | base tilt | full ann | Sharpe | sharpe_vs_DDD1 | turnover ratio | RC vs prod | RC vs DDD1 | RC vs DDD2 | strict | challenger | shadow | classification |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|---|
| **EEE1 smoothed_near_exclude** | 0.80 | DDD2 cap 0.03 | 7.13% | **0.9353** | -0.0026 | **1.095×** | **-0.36pp** | **+0.16pp** | **+0.07pp** | ✓ | ✗ | ✓ | **KEEP AS SHADOW (best)** |
| EEE2 turnover_aware | 0.90 | DDD2 cap 0.03 | 7.14% | 0.9371 | -0.0008 | 1.098× | -0.39pp | +0.12pp | +0.04pp | ✓ | ✗ | ✓ | KEEP AS SHADOW |
| EEE3 selective_escalation | 0.95 | DDD1 cap 0.07 | 7.14% | 0.9375 | -0.0004 | 1.096× | -0.49pp | +0.03pp | -0.05pp | ✓ | ✗ | ✓ | KEEP AS SHADOW |

EEE1 best matches the phase goal. EEE2 is a slightly safer alternative (smaller Sharpe loss vs DDD1, smaller RC repair). EEE3 is essentially DDD1 with a tiny safety margin and barely improves recovery_confirmed.
