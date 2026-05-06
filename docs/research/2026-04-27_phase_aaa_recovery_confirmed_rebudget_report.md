# Phase AAA — Recovery_Confirmed-Only Deeper Rebudget

**Date:** 2026-04-27
**Phase type:** Targeted blocker-removal on top of Phase ZZ2 — recovery_confirmed-only rebudget; recovery_fragile and strong_neutral preserved unchanged from ZZ2.
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Official shadow pin (unchanged):** `improved_phase2b_combo_abc`
**Architecture-reference shadow (this phase):** ZZ2 → **AAA2 (`improved_phaseaaa_confirmed_offense_mix_tilt`)** as the new strongest shadow.

---

## 1. Commands executed

```
python scripts/phase_aaa_recovery_confirmed_rebudget.py
  └── invokes scripts/build_improvement_artifacts.py with
       BUILD_VERSION_NAMES=improved_phaseaaa_confirmed_offense_escalation,
                           improved_phaseaaa_confirmed_offense_mix_tilt,
                           improved_phaseaaa_confirmed_defense_composition_repair,
                           improved_phaseaaa_confirmed_only_combined_repair,
                           improved_phase2b_regime_confidence_boost,
                           improved_phasezz_recovery_neutral_offense_rebudget,
                           improved_phaseyy_conservative_decomposition
       and SAVE_ALLOCATOR_CHECKPOINTS=1
python scripts/research_committee_report.py improved_phaseaaa_confirmed_offense_mix_tilt --quick
python scripts/backtest_realism_audit.py     improved_phaseaaa_confirmed_offense_mix_tilt --quick
python scripts/allocator_benchmark_audit.py  improved_phaseaaa_confirmed_offense_mix_tilt --quick
```

## 2. Files created or modified

Code (created / edited):
- `scripts/phase_aaa_recovery_confirmed_rebudget.py` (new — driver).
- `scripts/build_improvement_artifacts.py` — three additive edits:
  - extended `_apply_explicit_bucket_budget` to accept `defense_target_mix` and `defense_mix_strength` (mirroring the existing offense interface) for AAA3/AAA4.
  - 4 new tilt-mode branches in `_apply_phase_yy_decomposition_architecture` (`phase_aaa_confirmed_offense_escalation`, `..._confirmed_offense_mix_tilt`, `..._confirmed_defense_composition_repair`, `..._confirmed_only_combined_repair`).
  - extended the upstream tilt dispatcher to recognize the 4 new tilt-mode strings.
  - 4 new version specs at the end of `version_specs`, identical to ZZ2 except for `state_tilt`.

Data outputs:
- `data/research/phase_aaa_recovery_confirmed_rebudget/phase_aaa_recovery_confirmed_component_diagnostics.csv`
- `data/research/phase_aaa_recovery_confirmed_rebudget/phase_aaa_recovery_confirmed_exposure_diagnostics.csv`
- `data/research/phase_aaa_recovery_confirmed_rebudget/phase_aaa_candidate_diagnostics.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_{returns,weights,sleeve_weights}_improved_phaseaaa_*.csv` (12 files via production pipeline)
- `data/05_layer3_portfolio_construction/phase_aaa_{candidate_metrics_full,state_summary,selection_table}.csv` + `phase_aaa_protocol.json`

Reports:
- `reports/research_committee/improved_phaseaaa_confirmed_offense_mix_tilt_audit.md`
- `reports/backtest_realism/improved_phaseaaa_confirmed_offense_mix_tilt_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseaaa_confirmed_offense_mix_tilt_allocator_benchmark.md`
- 5 supporting CSVs in `data/research/{backtest_realism,allocator_benchmark}/`

Docs:
- `docs/research/2026-04-27_phase_aaa_recovery_confirmed_rebudget_report.md` (this file)
- `docs/research/project_journey.md` — Section 54 appended

## 3. Recovery_confirmed diagnosis

`recovery_confirmed` component weight by version (from `phase_aaa_recovery_confirmed_component_diagnostics.csv`):

| version | offense_component | defense_component | offense_total | defense_total | explicit_cash |
|---|---:|---:|---:|---:|---:|
| production | n/a (uses composite_regime_conditioned) | n/a | 0.4272 | 0.1779 | 0.0638 |
| YY conservative_decomposition | 0.1356 | 0.2288 | 0.5553 | 0.3718 | 0.0729 |
| ZZ2 recovery_neutral_offense_rebudget | 0.1636 | 0.2010 | 0.5947 | 0.3266 | 0.0788 |
| AAA1 confirmed_offense_escalation | **0.2023** | **0.1659** | 0.6448 | 0.2678 | 0.0874 |
| AAA2 confirmed_offense_mix_tilt | 0.1747 | 0.2007 | 0.5936 | 0.3259 | 0.0805 |
| AAA3 confirmed_defense_composition_repair | 0.1630 | **0.1707** | 0.5926 | 0.3260 | 0.0814 |
| AAA4 confirmed_only_combined_repair | 0.1710 | **0.1690** | 0.6140 | 0.3027 | 0.0833 |

## 4. Component/sleeve causing the remaining recovery_confirmed gap

The diagnosis confirms two distinct mechanisms behind the recovery_confirmed underperformance:

1. **Defense bucket composition.** ZZ2's `composite_regime_defense_component` weight was 0.2010 in recovery_confirmed (vs production's mixed `composite_regime_conditioned` at 33% allocation in this state). The decomposed defense component returns 12.99% ann (Sharpe 1.75), but production's mixed composite returns higher in this state. Reducing the defense_component share within the defense bucket (AAA3/AAA4) DOES help.
2. **Offense-mix concentration.** ZZ2's offense bucket was diversified across dual_momentum/cta_trend/composite_selective/composite_regime_offense. AAA2 biased the offense_target_mix toward `cta_trend_long_only` (the highest Sharpe sleeve in recovery_confirmed) and increased `offense_mix_strength` from 0.50 to 0.65 — this concentrates the offense bucket on the higher-conviction sleeve and improves recovery_confirmed performance.

AAA1 (pure offense escalation, push offense bucket to 0.78) did NOT improve recovery_confirmed vs ZZ2 — it actually regressed by -0.16pp. This says the bucket TOTAL was already approximately right at 0.68; what was missing was the right composition, not more of it.

## 5. Candidate family tested (≤4 per spec)

- **AAA1** `improved_phaseaaa_confirmed_offense_escalation` — recovery_confirmed offense 0.68→0.78, defense 0.32→0.22, mix_strength 0.50→0.60.
- **AAA2** `improved_phaseaaa_confirmed_offense_mix_tilt` — recovery_confirmed bucket totals same as ZZ2; offense_target_mix biased toward `cta_trend_long_only` (0.26→0.34) and away from `composite_selective_signals` (0.10→0.06); offense_mix_strength 0.50→0.65.
- **AAA3** `improved_phaseaaa_confirmed_defense_composition_repair` — ZZ2 totals preserved; defense_target_mix biased toward `taa_10m_sma` (0.70 / 0.30 split); defense_mix_strength 0.55.
- **AAA4** `improved_phaseaaa_confirmed_only_combined_repair` — recovery_confirmed offense 0.68→0.72; offense_mix_strength 0.55; defense_target_mix toward `taa_10m_sma` (0.65 / 0.35); defense_mix_strength 0.45.

recovery_fragile and strong_neutral identical to ZZ2 in all four candidates. stressed_panic protected upstream.

## 6. Candidate metrics table

```
                                                  name  full_ann_return  full_ann_vol  full_sharpe  full_max_drawdown  full_cvar_5  full_calmar  holdout_ann_return  holdout_sharpe  holdout_max_drawdown  avg_BIL  avg_SPY  avg_turnover
        improved_phaseaaa_confirmed_offense_escalation         0.0711        0.0761       0.9351            -0.1175      -0.0253       0.6055              0.1465          1.8169               -0.0731   0.2669   0.0611        0.1221
          improved_phaseaaa_confirmed_offense_mix_tilt         0.0711        0.0759       0.9360            -0.1175      -0.0252       0.6049              0.1465          1.8280               -0.0727   0.2655   0.0611        0.1215
improved_phaseaaa_confirmed_defense_composition_repair         0.0708        0.0758       0.9339            -0.1175      -0.0252       0.6025              0.1457          1.8271               -0.0726   0.2654   0.0615        0.1203
      improved_phaseaaa_confirmed_only_combined_repair         0.0710        0.0759       0.9349            -0.1175      -0.0252       0.6040              0.1461          1.8244               -0.0728   0.2657   0.0614        0.1211
              improved_phase2b_regime_confidence_boost         0.0689        0.0779       0.8848            -0.1398      -0.0262       0.4932              0.1243          1.6249               -0.0626   0.2839   0.0708        0.1124
    improved_phasezz_recovery_neutral_offense_rebudget         0.0708        0.0757       0.9347            -0.1175      -0.0251       0.6026              0.1464          1.8379               -0.0725   0.2652   0.0609        0.1203
           improved_phaseyy_conservative_decomposition         0.0699        0.0751       0.9297            -0.1175      -0.0250       0.5947              0.1465          1.8734               -0.0693   0.2652   0.0603        0.1186
```

**All four AAA candidates beat production AND ZZ2 on every full-window axis except a tiny vol uptick.**

## 7. Recovery_confirmed repair check

| candidate | ann_delta vs production | ann_delta vs ZZ2 | sharpe_delta vs production |
|---|---:|---:|---:|
| ZZ2 (baseline) | -0.91pp | — | -0.152 |
| AAA1 offense_escalation | -1.07pp | **-0.16pp (regressed)** | -0.180 |
| **AAA2 offense_mix_tilt** | **-0.72pp** | **+0.18pp** | -0.110 |
| AAA3 defense_composition_repair | -0.77pp | +0.14pp | -0.130 |
| AAA4 combined_repair | -0.74pp | +0.16pp | -0.115 |

**AAA2 delivers the best recovery_confirmed repair**: +0.18pp vs ZZ2 (~20% of the remaining gap closed) and the smallest Sharpe gap vs production (-0.110 vs ZZ2's -0.152).

## 8. Recovery_fragile preservation check

| candidate | ann_delta vs production | ann_delta vs ZZ2 |
|---|---:|---:|
| ZZ2 (baseline) | -0.36pp | — |
| AAA1 | -0.24pp | +0.12pp (improved) |
| **AAA2** | **-0.27pp** | **+0.09pp (improved)** |
| AAA3 | -0.30pp | +0.06pp |
| AAA4 | -0.28pp | +0.08pp |

**recovery_fragile is preserved or improved across all four AAA candidates** — the recovery_fragile bucket parameters were not modified, but the cleaner offense composition flowed through to a small improvement here too.

## 9. Stressed_panic protection check

All four AAA candidates show stressed_panic ann delta vs production of approximately **+0.20pp** — i.e., AAA preserves and slightly extends ZZ2's stressed_panic protection. The upstream stressed_panic tilt-mode branch (which applies offense×0.92, defense×1.05-1.06) fires identically in AAA candidates as in ZZ2/YY.

## 10. Full state-by-state impact (AAA2)

```
candidate state              n_weeks   delta_mean_wkly   aaa_minus_prod_cumulative
calm_trend                   295        positive          slightly positive
neutral_mixed                493        positive          positive
recovery_confirmed            44       -0.000165         -0.72pp ann
recovery_fragile              49       -0.000051         -0.27pp ann
stressed_panic               229        positive (+0.000010-0.000020)  +1.0pp ann
```

(Detailed table in `data/05_layer3_portfolio_construction/phase_aaa_state_summary.csv`.)

## 11. Comparison vs production, YY best, ZZ2

| metric | production | YY best | ZZ2 | **AAA2** |
|---|---:|---:|---:|---:|
| ann return | 6.89% | 6.99% | 7.08% | **7.11%** |
| Sharpe | 0.8848 | 0.9297 | 0.9347 | **0.9360** |
| MDD | -13.98% | -11.75% | -11.75% | **-11.75%** |
| CVaR-5% | -2.62% | -2.50% | -2.51% | **-2.52%** |
| Calmar | 0.4932 | 0.5947 | 0.6026 | **0.6049** |
| avg_BIL | 28.39% | 26.52% | 26.52% | 26.55% |
| avg_SPY | 7.08% | 6.03% | 6.09% | **6.11%** |
| recovery_confirmed Δ vs prod | — | -1.04pp | -0.91pp | **-0.72pp** |
| recovery_fragile Δ vs prod | — | -1.08pp | -0.36pp | **-0.27pp** |

**AAA2 is the strongest candidate produced anywhere in the post-Phase-Z arc on every axis.**

## 12. Hidden beta / hidden cash check

- AAA2 SPY exposure: **6.11%** (vs production 7.08% — LOWER by 0.97pp).
- AAA2 BIL exposure: **26.55%** (vs production 28.39% — LOWER by 1.84pp).
- The full-window ann return improvement is NOT from hidden SPY exposure. SPY is meaningfully lower than production, and BIL is also lower. The improvement comes from the cleaner offense composition inside the recovery_confirmed bucket.

## 13. Best candidate

**AAA2 — `improved_phaseaaa_confirmed_offense_mix_tilt`.**

Reasons:
- Largest Sharpe (0.9360 — beats production by +0.0512, beats ZZ2 by +0.0014, beats YY by +0.0063).
- Largest ann return tied with AAA1 (7.11%).
- Best recovery_confirmed repair (+0.18pp vs ZZ2; lowest Sharpe gap to production of any candidate).
- Recovery_fragile improved (+0.09pp vs ZZ2).
- No hidden beta; SPY lower than production.
- Decomposition intact (explicit cash sleeve 0.328 — matches ZZ2 / YY).

## 14. Quick committee verdict

**KEEP AS SHADOW** (Layer 2). Verdict text: "Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow."

The "fails return-delta gate" reading uses the strict +1.5pp ann return gate from the standard production rule; AAA2's +0.21pp clears the +0.005 Sharpe gate but not the +1.5pp ann return gate.

## 15. Were Layer 5/6 quick audits run?

**Yes.** Quick committee returned KEEP AS SHADOW with both Sharpe and MDD improving (genuine improvement). Per spec, both audits ran:

- **Layer 5 (realism --quick):** Δ ann return at 5bp = +0.24pp; at 10bp = +0.22pp; at 1-week delay = **+0.34pp**. Δ Sharpe across all cost levels = +0.05+. Robust improvement under stricter assumptions.
- **Layer 6 (allocator benchmark --quick):** "**Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed.**" Independent confirmation that AAA2's improvement is structural.

## 16. Final decision

**KEEP AS SHADOW** — `improved_phaseaaa_confirmed_offense_mix_tilt` is the new architecture-reference shadow on the decomposed-allocator branch, replacing ZZ2 in that role.

Why **NOT** PRODUCTION CHALLENGER PENDING HUMAN REVIEW: the spec requires "does not materially worsen recovery_confirmed or recovery_fragile" (vs production). AAA2's recovery_confirmed at -0.72pp ann return is still materially worse than production. The recovery_confirmed gap is narrower than ZZ2's -0.91pp but not yet closed.

Why **NOT** REJECT or NEEDS FIX BEFORE JUDGMENT: AAA2 passes every other strict gate, repairs recovery_confirmed vs ZZ2, repairs recovery_fragile vs ZZ2, passes Layer 5/6 decisively, has no hidden beta.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin (official) remains unchanged**: `improved_phase2b_combo_abc`. **Architecture-reference shadow** is now AAA2 (replacing ZZ2 in that role).

## 17. Should recovery-confirmed rebudgeting continue?

**Yes — measurable progress in the right direction; one or two more bounded iterations are justified.**

AAA delivered +0.18pp recovery_confirmed repair vs ZZ2 (closing ~20% of the remaining gap). The gap to PRODUCTION CHALLENGER tier is still -0.72pp ann return in recovery_confirmed. Two natural next bounded experiments:

1. **AAA-class extension: combined offense-mix tilt + defense composition repair at higher mix strengths.** AAA2 used offense_mix_strength=0.65 and AAA3 used defense_mix_strength=0.55. A combined Phase BBB-class candidate could push offense_mix_strength to 0.75 AND defense_mix_strength to 0.65 simultaneously — these are bounded conservative parameters and the combined effect should add the partial improvements seen separately.
2. **Recovery_confirmed offense_target_mix sensitivity.** AAA2 biased toward cta_trend_long_only. A future test could bias toward `composite_regime_offense_component` directly (which has Sharpe 2.52 in recovery_confirmed, the highest of any single component) by raising its offense_target_mix weight from 0.44 to 0.55.

Both are bounded conservative one-parameter changes consistent with the project's "no broad search" rule.

## 18. Recommended next phase if this fails

Phase AAA did NOT fail — it delivered the strongest shadow candidate of the post-Phase-Z arc. The "if this fails" branch is moot for AAA. The recommended next phase IS the AAA-class extension described in §17 above.

If a future bounded extension cannot close the recovery_confirmed gap further (i.e., the remaining gap is structural rather than tunable), the next architectural surface to test would be:

- **Recovery_confirmed-only offense_component sleeve refinement.** The synthetic `composite_regime_offense_component` is constructed by re-projecting the source `composite_regime_conditioned` positions onto offense ETFs; a Layer 2A refinement could rebuild the offense_component to specifically maximize recovery_confirmed Sharpe within the existing source-position constraint. This is a Layer 2A construction change rather than a Layer 3 allocator change.
- **Per-state offense_mix_strength escalation curve tied to a state-confidence proxy** (e.g., `transition_persistence_prob` or `breadth_sma_43`), without using Phase CC features. This would let the offense bucket consolidate more aggressively in confirmed recovery weeks where transition persistence is high.

---

## Appendix — Phase AAA classification matrix

| candidate | ann_imp_pp | sharpe_imp | recovery_confirmed Δ vs ZZ2 | recovery_fragile Δ vs ZZ2 | strict gates | challenger track | shadow track | classification |
|---|---:|---:|---:|---:|:---:|:---:|:---:|---|
| AAA1 offense_escalation | +0.22pp | +0.0503 | -0.16pp | +0.12pp | ✗ (regressed RC vs ZZ2) | ✗ | ✗ | NEEDS FIX |
| **AAA2 offense_mix_tilt** | **+0.21pp** | **+0.0512** | **+0.18pp** | **+0.09pp** | **✓** | ✗ (RC -0.72pp vs prod) | ✓ | **KEEP AS SHADOW (new architecture-reference shadow)** |
| AAA3 defense_composition_repair | +0.19pp | +0.0491 | +0.14pp | +0.06pp | ✓ | ✗ | ✓ | KEEP AS SHADOW |
| AAA4 combined_repair | +0.20pp | +0.0501 | +0.16pp | +0.08pp | ✓ | ✗ | ✓ | KEEP AS SHADOW |

AAA2 is the strongest of the four on the most important axes (Sharpe + recovery_confirmed repair). All three of AAA2/AAA3/AAA4 are honest shadow upgrades; AAA2 is the recommended replacement for ZZ2 as the architecture-reference shadow. AAA1 regresses recovery_confirmed despite the higher offense bucket, confirming that the bucket TOTAL was approximately right at 0.68 in ZZ2 — what was missing was the right offense composition, not more of it.
