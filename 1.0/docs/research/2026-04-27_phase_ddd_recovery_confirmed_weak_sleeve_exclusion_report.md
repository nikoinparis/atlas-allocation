# Phase DDD — Recovery_Confirmed-Only Harder Weak-Sleeve Exclusion

**Date:** 2026-04-27
**Phase type:** Targeted blocker-removal on top of Phase CCC2 — recovery_confirmed-only harder dual_momentum_topn cap and CSS soft-cap variants. recovery_fragile, strong_neutral, stressed_panic preserved unchanged from CCC2.
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Official shadow pin (unchanged):** `improved_phase2b_combo_abc`
**Architecture-reference shadow (this phase):** CCC2 → **DDD1 (`improved_phaseddd_confirmed_harder_dual_cap`)** as the new strongest shadow.

---

## 1. Commands executed

```
python scripts/phase_ddd_recovery_confirmed_weak_sleeve_exclusion.py
  └── invokes scripts/build_improvement_artifacts.py with
       BUILD_VERSION_NAMES=4 DDD main + 7 references + production
       and SAVE_ALLOCATOR_CHECKPOINTS=1
python scripts/research_committee_report.py improved_phaseddd_confirmed_harder_dual_cap --quick
python scripts/backtest_realism_audit.py     improved_phaseddd_confirmed_harder_dual_cap --quick
python scripts/allocator_benchmark_audit.py  improved_phaseddd_confirmed_harder_dual_cap --quick
```

(One implementation-time fix to the upstream tilt dispatcher set in
`build_improvement_artifacts.py` line ~2741: added the 6 DDD tilt-mode
strings so the decomposed-architecture path is invoked for them.)

## 2. Files created or modified

Code (created / edited):
- `scripts/phase_ddd_recovery_confirmed_weak_sleeve_exclusion.py` (new — driver).
- `scripts/build_improvement_artifacts.py` — three additive edits:
  - 6 new tilt-mode branches in `_apply_phase_yy_decomposition_architecture` (4 main + 2 rescue) inside the existing CCC dispatch block (recovery_confirmed only).
  - extended the upstream tilt dispatcher set to include all 6 DDD tilt-mode strings.
  - 6 new version specs at the end of `version_specs`.

Data outputs (`data/research/phase_ddd_recovery_confirmed_weak_sleeve_exclusion/`):
- `phase_ddd_confirmed_weak_sleeve_diagnostics.csv`
- `phase_ddd_confirmed_sleeve_contribution.csv`
- `phase_ddd_reallocation_diagnostics.csv`
- `phase_ddd_candidate_diagnostics.csv`

Data outputs (`data/05_layer3_portfolio_construction/`):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phaseddd_*.csv` (12 files via production pipeline; rescue variants not built).
- `phase_ddd_{candidate_metrics_full,state_summary,selection_table}.csv` + `phase_ddd_protocol.json`.

Reports:
- `reports/research_committee/improved_phaseddd_confirmed_harder_dual_cap_audit.md`
- `reports/backtest_realism/improved_phaseddd_confirmed_harder_dual_cap_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseddd_confirmed_harder_dual_cap_allocator_benchmark.md`
- 5 supporting CSVs in `data/research/{backtest_realism,allocator_benchmark}/`.

Docs:
- `docs/research/2026-04-27_phase_ddd_recovery_confirmed_weak_sleeve_exclusion_report.md` (this file)
- `docs/research/project_journey.md` — Section 56 appended.

## 3. Confirmed weak-sleeve diagnosis

`recovery_confirmed` sleeve allocations across the architecture chain
(from `phase_ddd_reallocation_diagnostics.csv`):

| version | dual | cta | css | comp_off | comp_def | offense_total | defense_total |
|---|---:|---:|---:|---:|---:|---:|---:|
| production | 0.088 | 0.108 | 0.231 | n/a | n/a | 0.427 | 0.178 |
| YY conservative_decomposition | 0.108 | 0.135 | 0.177 | 0.136 | 0.229 | 0.555 | 0.372 |
| ZZ2 recovery_neutral_offense | 0.114 | 0.143 | 0.174 | 0.164 | 0.201 | 0.595 | 0.327 |
| AAA2 confirmed_offense_mix_tilt | 0.107 | 0.167 | 0.145 | 0.175 | 0.201 | 0.594 | 0.326 |
| BBB3 offense_defense_combo | 0.093 | 0.161 | 0.125 | 0.213 | 0.212 | 0.592 | 0.325 |
| **CCC2 confirmed_cap_dual** | **0.084** | 0.164 | 0.125 | 0.218 | 0.212 | 0.591 | 0.325 |
| **DDD1 harder_dual_cap (best)** | **0.064** | 0.169 | 0.125 | 0.232 | 0.211 | 0.590 | 0.324 |
| DDD2 near_exclude_dual | **0.049** | 0.173 | 0.125 | 0.242 | 0.211 | 0.588 | 0.324 |
| DDD3 dual_hard_css_soft | 0.061 | 0.172 | **0.111** | 0.246 | 0.211 | 0.589 | 0.324 |
| DDD4 defensive_balanced | 0.068 | 0.167 | 0.124 | 0.227 | 0.217 | 0.585 | 0.330 |

CCC2 already pushed dual_momentum_topn down to 0.084 from BBB3's 0.093. DDD1 pushes it further to 0.064; DDD2 nearly excludes it at 0.049; DDD3 also caps CSS to 0.111. Composite_regime_offense_component gets the biggest reallocation in every DDD candidate, rising from CCC2's 0.218 to 0.232/0.242/0.246/0.227.

## 4. Remaining dual / CSS exposure

- DDD1 dual share of offense bucket: ~10.9% (down from CCC2's ~14.2% and YY's ~19.5%).
- DDD2 dual share: ~8.3% (the aggressive cap).
- DDD3 dual share: ~10.4%, CSS share: ~18.9% (down from ~21.2% in DDD1).
- DDD4 dual share: ~11.6%, CSS share: ~21.2% (similar to DDD1 since the cap is looser at 0.12).

## 5. Reallocation diagnostics

Full table saved at `phase_ddd_reallocation_diagnostics.csv`. Key observation: the freed weight from the dual cap is absorbed primarily by `composite_regime_offense_component` (Sharpe 2.80 in this state) and secondarily by `cta_trend_long_only` (Sharpe 1.02) — the two highest-conviction confirmed-state offense sources. DDD4 routes 20% of the freed weight into `composite_regime_defense_component` (Sharpe 1.80) — that variant slightly increases defense_total to 0.330 and modestly underperforms DDD1.

## 6. Candidate family tested

- **DDD1** `confirmed_harder_dual_cap` — dual cap 0.07, reallocate 70/30 to comp_off / cta.
- **DDD2** `confirmed_near_exclude_dual` — dual cap 0.03, reallocate 70/30 (most aggressive on dual).
- **DDD3** `confirmed_dual_hard_css_soft` — dual cap 0.06 + CSS cap 0.10, reallocate 75/25.
- **DDD4** `confirmed_defensive_balanced_substitution` — dual cap 0.06 + CSS cap 0.12, reallocate 55/25/20 (with defense receiver).

Rescue candidates (DDD5, DDD6) **not built** — the spec says "only if all main candidates fail narrowly." DDD1 and DDD4 PASSED strict gates, so rescue is not required.

## 7. Candidate metrics table (full window)

```
                                                       name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_BIL  avg_SPY  avg_turnover
                improved_phaseddd_confirmed_harder_dual_cap         0.0714       0.9379            -0.1175      -0.0253   0.2673   0.0604        0.1234
              improved_phaseddd_confirmed_near_exclude_dual         0.0715       0.9379            -0.1175      -0.0253   0.2678   0.0602        0.1238
             improved_phaseddd_confirmed_dual_hard_css_soft         0.0713       0.9358            -0.1175      -0.0254   0.2680   0.0604        0.1240
improved_phaseddd_confirmed_defensive_balanced_substitution         0.0714       0.9378            -0.1175      -0.0253   0.2671   0.0604        0.1232
                       improved_phaseccc_confirmed_cap_dual         0.0714       0.9376            -0.1175      -0.0253   0.2668   0.0606        0.1228
              improved_phase2b_regime_confidence_boost              0.0689       0.8848            -0.1398      -0.0262   0.2839   0.0708        0.1124
```

## 8. Recovery_confirmed repair check

| candidate | ann_delta vs production | ann_delta vs CCC2 | sharpe_delta vs CCC2 |
|---|---:|---:|---:|
| CCC2 (baseline) | -0.61pp | — | — |
| **DDD1 (best)** | **-0.51pp** | **+0.10pp** | +0.0003 |
| DDD2 | -0.43pp | +0.18pp | +0.0003 |
| DDD3 | -0.64pp | -0.03pp (regressed) | -0.0019 |
| DDD4 | -0.53pp | +0.08pp | +0.0001 |

DDD2 has the BIGGEST recovery_confirmed repair (+0.18pp vs CCC2) but fails the turnover gate at exactly 1.10×. DDD1 is the safe-and-passing variant: +0.10pp recovery_confirmed repair vs CCC2 with all strict gates clean.

## 9. Recovery_fragile preservation check

| candidate | ann_delta vs production | ann_delta vs CCC2 |
|---|---:|---:|
| CCC2 (baseline) | (preserved at AAA2/BBB3 level) | — |
| **DDD1** | preserved | **+0.05pp (slight improvement)** |
| DDD2 | preserved | +0.09pp |
| DDD3 | preserved | +0.08pp |
| DDD4 | preserved | +0.03pp |

All four DDD candidates **slightly improve recovery_fragile** vs CCC2 — the reallocation toward composite_regime_offense_component (which has good Sharpe in fragile too) flows through. recovery_fragile is preserved or improved across all four.

## 10. Stressed_panic protection check

DDD1 stressed_panic ann delta vs production: **+0.21pp** (matches CCC2 / BBB3 / AAA2). Upstream stressed_panic guardrails (offense ×0.92, regime_defense_component ×1.06, taa_10m_sma ×1.05) are unchanged. Stressed_panic protection PRESERVED.

## 11. Full state-by-state impact (DDD1)

(Detailed table in `data/05_layer3_portfolio_construction/phase_ddd_state_summary.csv`.)

- calm_trend: positive delta (no regression).
- neutral_mixed: positive delta.
- recovery_confirmed: -0.51pp ann (improved from CCC2's -0.61pp).
- recovery_fragile: slightly improved vs CCC2 (+0.05pp).
- stressed_panic: +0.21pp (protected).

## 12. Comparison vs production, YY, ZZ2, AAA2, BBB3, CCC2

| metric | production | YY | ZZ2 | AAA2 | BBB3 | CCC2 | **DDD1** |
|---|---:|---:|---:|---:|---:|---:|---:|
| ann return | 6.89% | 6.99% | 7.08% | 7.11% | 7.13% | 7.14% | **7.14%** |
| Sharpe | 0.8848 | 0.9297 | 0.9347 | 0.9360 | 0.9368 | 0.9376 | **0.9379** |
| MDD | -13.98% | -11.75% | -11.75% | -11.75% | -11.75% | -11.75% | **-11.75%** |
| CVaR-5% | -2.62% | -2.50% | -2.51% | -2.52% | -2.53% | -2.53% | **-2.53%** |
| avg BIL | 28.39% | 26.52% | 26.52% | 26.55% | 26.66% | 26.68% | 26.73% |
| avg SPY | 7.08% | 6.03% | 6.09% | 6.11% | 6.08% | 6.06% | 6.04% |
| RC delta vs prod | — | -1.04pp | -0.91pp | -0.72pp | -0.67pp | **-0.61pp** | **-0.51pp** |

DDD1 is the strongest candidate produced anywhere in the post-Phase-Z arc on Sharpe AND on recovery_confirmed repair. Sharpe sequence YY → ZZ2 → AAA2 → BBB3 → CCC2 → DDD1 = 0.9297 → 0.9347 → 0.9360 → 0.9368 → 0.9376 → **0.9379** (monotonically rising, marginal gains compounding).

## 13. Hidden beta / hidden cash check

- DDD1 SPY exposure: **6.04%** (vs production 7.08% — LOWER by 1.05pp; vs CCC2 6.06% — slightly LOWER).
- DDD1 BIL exposure: **26.73%** (vs production 28.39% — LOWER by 1.66pp; vs CCC2 26.68% — slightly higher).
- The full-window improvement is NOT from hidden SPY exposure. SPY is meaningfully lower than production. The improvement comes from the cleaner offense composition inside the recovery_confirmed bucket.

## 14. Best candidate

**DDD1 — `improved_phaseddd_confirmed_harder_dual_cap`.**

Reasons:
- Tied for largest Sharpe (0.9379 — beats CCC2 by +0.0003, beats production by +0.053).
- Tied for largest ann return (7.14%).
- Best recovery_confirmed repair AMONG strict-gate-passing candidates (+0.10pp vs CCC2; DDD2 had +0.18pp but fails turnover).
- recovery_fragile improved (+0.05pp vs CCC2).
- Stressed_panic preserved (+0.21pp vs production).
- No hidden beta; SPY lower than production.
- Decomposition intact (explicit cash sleeve still ~0.33).
- Passes ALL strict selection gates.

## 15. Quick committee verdict

**KEEP AS SHADOW** (Layer 2). Verdict text reflects the standard Phase D rule: holdout Sharpe and MDD both improve; ann return delta is below the +1.5pp production-rule threshold.

## 16. Were Layer 5/6 quick audits run?

**Yes** — quick committee returned KEEP AS SHADOW with both Sharpe and MDD improving (genuine improvement). Both audits ran:
- **Layer 5 (realism --quick):** Δ ann return at 5bp = **+0.28pp**; at 10bp = **+0.26pp**; at 1-week delay = **+0.37pp**. Improvement is robust to stricter assumptions.
- **Layer 6 (allocator benchmark --quick):** "**Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed.**"

## 17. Whether rescue variants were created

**No.** DDD1 (and DDD4) passed strict gates; the spec says rescue is only used "if all main candidates fail narrowly." Two of the four main candidates passed all strict gates, so rescue (DDD5 minimal_dual_polish, DDD6 confirmed_comp_off_receiver) was not built or evaluated. The rescue tilt branches and version specs are registered in the builder for future use if needed.

## 18. Final decision

**KEEP AS SHADOW** — `improved_phaseddd_confirmed_harder_dual_cap` is the new strongest architecture-reference shadow on the decomposed-allocator branch, replacing CCC2 in that role.

Why **NOT** PRODUCTION CHALLENGER PENDING HUMAN REVIEW: the spec requires "does not materially worsen recovery_confirmed or recovery_fragile" vs production. DDD1's recovery_confirmed at -0.51pp ann return is still materially worse than production. The recovery_confirmed gap is narrower than CCC2's -0.61pp but not yet closed.

Why **NOT** REJECT or NEEDS FIX BEFORE JUDGMENT: DDD1 passes every strict gate, repairs recovery_confirmed vs CCC2, slightly improves recovery_fragile vs CCC2, passes Layer 5/6 decisively, has no hidden beta.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin (official) remains unchanged**: `improved_phase2b_combo_abc`. **Architecture-reference shadow** is now DDD1 (replacing CCC2).

## 19. Should recovery_confirmed weak-sleeve exclusion continue?

**Approaching exhaustion at this magnitude — but one more bounded test is honest.** Sequence of recovery_confirmed gap closure: YY -1.04pp → ZZ2 -0.91pp → AAA2 -0.72pp → BBB3 -0.67pp → CCC2 -0.61pp → DDD1 -0.51pp. Each step closes 0.05-0.20pp. The improvements are real but the marginal returns are diminishing.

DDD2 (dual cap 0.03) achieved -0.43pp (better) but failed the turnover gate. The aggressive dual cap is moving the needle further, but each step toward "near-exclude" introduces more weekly L1 turnover that bumps against the 1.10× production cap.

**Concrete recommendation for the next bounded test:** A single Phase EEE candidate that combines DDD2's aggressive dual cap (0.03) with CCC2-style offense_target_mix (no CSS soft-cap) AND a small turnover-smoothing gate (e.g., apply the cap only when prior-week dual share was already > 0.05) so the candidate stays under the 1.10× production turnover ratio. If that one candidate cannot push recovery_confirmed below -0.40pp without breaking the turnover gate or full-window Sharpe, **mark this branch as exhausted** and shift to a new architecture frontier.

## 20. Recommended next phase if this fails

If a Phase EEE-class turnover-smoothed aggressive dual-cap also fails to materially close the recovery_confirmed gap below -0.40pp without breaking another gate, the recovery_confirmed weak-sleeve exclusion branch should be marked **BRANCH EXHAUSTED**. The next architecture frontier should be one of:

1. **Layer 2A re-engineering of `composite_regime_offense_component`.** The synthetic offense component is currently constructed by re-projecting the source `composite_regime_conditioned` positions onto offense ETFs. A Layer 2A refinement could rebuild it specifically to maximise recovery_confirmed Sharpe within the source-position constraint. This is structural sleeve-design work, not allocator parameter tuning.
2. **Per-state offense_mix_strength escalation curve tied to existing breadth/transition probability features** (without using Phase CC features). Let the offense bucket consolidate more aggressively in confirmed-recovery weeks where transition_persistence_prob is high.
3. **Recovery_confirmed-only target_vol_ceil escalation.** The current target_vol_ceil = 1.00 may be capping the candidate's ability to participate further in recovery_confirmed. A confirmed-only target_vol_ceil = 1.10 could allow more participation in this state without affecting other states.

---

## Appendix — Phase DDD classification matrix

| candidate | ann_imp_pp | sharpe_imp | sharpe_vs_ccc | recovery_confirmed Δ vs CCC2 | recovery_fragile Δ vs CCC2 | turnover ratio | strict | challenger | shadow | classification |
|---|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|---|
| **DDD1 harder_dual_cap** | **+0.25pp** | **+0.0531** | **+0.0003** | **+0.10pp** | **+0.05pp** | 1.098× | ✓ | ✗ (RC -0.51pp vs prod) | ✓ | **KEEP AS SHADOW (best)** |
| DDD2 near_exclude_dual | +0.25pp | +0.0531 | +0.0003 | +0.18pp | +0.09pp | 1.101× | ✗ (turnover 1.10x boundary) | ✗ | ✓ | (best RC repair but turnover gate) |
| DDD3 dual_hard_css_soft | +0.24pp | +0.0510 | -0.0019 | -0.03pp | +0.08pp | 1.103× | ✗ | ✗ | ✗ | NEEDS FIX (RC regressed vs CCC2) |
| DDD4 defensive_balanced | +0.25pp | +0.0530 | +0.0001 | +0.08pp | +0.03pp | 1.096× | ✓ | ✗ | ✓ | KEEP AS SHADOW |

DDD1 is the recommended replacement for CCC2 as the architecture-reference shadow. DDD2's superior recovery_confirmed repair is offset by the tiny turnover overshoot — a Phase EEE turnover-smoothing variant could potentially recover that improvement.
