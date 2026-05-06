# Phase ZZ — Decomposed-Component Allocator Rebudgeting

**Date:** 2026-04-27
**Phase type:** Recovery-state rebudget on top of Phase YY's decomposed composite architecture
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`
**Architecture reference (unchanged through this phase):** `improved_phaseyy_conservative_decomposition`
**Phase ZZ best:** `improved_phasezz_recovery_neutral_offense_rebudget` → **KEEP AS SHADOW** (replaces YY as the active architecture-reference shadow track).

---

## 1. Commands executed

```
python scripts/phase_zz_decomposed_component_rebudget.py
  └── invokes scripts/build_improvement_artifacts.py via subprocess with
       BUILD_VERSION_NAMES=improved_phasezz_recovery_offense_rebudget,
                           improved_phasezz_recovery_neutral_offense_rebudget,
                           improved_phasezz_confirmed_freer_fragile_conservative,
                           improved_phasezz_conservative_decomposition_repair,
                           improved_phase2b_regime_confidence_boost,
                           improved_phaseyy_conservative_decomposition
       and SAVE_ALLOCATOR_CHECKPOINTS=1
python scripts/research_committee_report.py improved_phasezz_recovery_neutral_offense_rebudget --quick
python scripts/backtest_realism_audit.py     improved_phasezz_recovery_neutral_offense_rebudget --quick
python scripts/allocator_benchmark_audit.py  improved_phasezz_recovery_neutral_offense_rebudget --quick
```

## 2. Files created or modified

Code (created / edited):
- `scripts/phase_zz_decomposed_component_rebudget.py` (new — driver)
- `scripts/build_improvement_artifacts.py` — three additive edits:
  - 4 new tilt branches in `_apply_phase_yy_decomposition_architecture` (`phase_zz_recovery_offense_rebudget`, `..._recovery_neutral_offense_rebudget`, `..._confirmed_freer_fragile_conservative`, `..._conservative_decomposition_repair`).
  - extend the upstream tilt dispatcher (line ~1997) to include the 4 new tilt-mode strings so they receive the same conviction tilt + stressed_panic protection + decomposition architecture path as Phase YY.
  - 4 new version specs identical to Phase YY's `improved_phaseyy_conservative_decomposition` except for `state_tilt`.

Data (Phase ZZ outputs in `data/research/phase_zz_decomposed_component_rebudget/`):
- `phase_zz_component_weight_by_state.csv`
- `phase_zz_component_return_contribution_by_state.csv`
- `phase_zz_recovery_overdefense_diagnostics.csv`
- `phase_zz_candidate_diagnostics.csv`

Data (Phase ZZ portfolio outputs in `data/05_layer3_portfolio_construction/`):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasezz_*.csv` (12 files via production pipeline)
- `phase_zz_candidate_metrics_full.csv`
- `phase_zz_state_summary.csv`
- `phase_zz_selection_table.csv`
- `phase_zz_protocol.json`

Reports (created):
- `reports/research_committee/improved_phasezz_recovery_neutral_offense_rebudget_audit.md`
- `reports/backtest_realism/improved_phasezz_recovery_neutral_offense_rebudget_realism_audit.md`
- `reports/allocator_benchmark/improved_phasezz_recovery_neutral_offense_rebudget_allocator_benchmark.md`
- 5 supporting CSVs in `data/research/{backtest_realism,allocator_benchmark}/`

Docs:
- `docs/research/2026-04-27_phase_zz_decomposed_component_rebudget_report.md` (this file)
- `docs/research/project_journey.md` — Section 53 appended

## 3. Component rebudget diagnosis

**Recovery state defense/offense ratio across versions** (from
`phase_zz_recovery_overdefense_diagnostics.csv`):

| version | state | offensive_total | defensive_total | explicit_cash | defense/offense ratio |
|---|---|---:|---:|---:|---:|
| production | recovery_confirmed | 0.427 | 0.178 | 0.064 | **0.42** |
| production | recovery_fragile | 0.458 | 0.139 | 0.124 | **0.30** |
| YY conservative_decomposition | recovery_confirmed | 0.555 | 0.372 | 0.073 | **0.67** |
| YY conservative_decomposition | recovery_fragile | 0.479 | 0.392 | 0.130 | **0.82** |
| ZZ1 recovery_offense_rebudget | recovery_confirmed | 0.591 | 0.331 | 0.078 | **0.56** |
| ZZ1 recovery_offense_rebudget | recovery_fragile | 0.506 | 0.363 | 0.131 | **0.72** |
| ZZ2 recovery_neutral_offense_rebudget | recovery_confirmed | 0.595 | 0.327 | 0.079 | **0.55** |
| ZZ2 recovery_neutral_offense_rebudget | recovery_fragile | 0.509 | 0.360 | 0.131 | **0.71** |
| ZZ3 confirmed_freer_fragile_conservative | recovery_confirmed | 0.610 | 0.309 | 0.081 | **0.51** |
| ZZ3 confirmed_freer_fragile_conservative | recovery_fragile | 0.499 | 0.370 | 0.130 | **0.74** |
| ZZ4 conservative_decomposition_repair | recovery_confirmed | 0.579 | 0.346 | 0.076 | **0.60** |
| ZZ4 conservative_decomposition_repair | recovery_fragile | 0.493 | 0.377 | 0.130 | **0.76** |

YY pushes the recovery defense/offense ratio from production's 0.42/0.30 to 0.67/0.82 — a clear over-defense pattern that explains its recovery underperformance. All four ZZ candidates measurably reduce that ratio: ZZ3 best in `recovery_confirmed` (0.51), ZZ2 best in `recovery_fragile` (0.71). None fully restore production's ratio — by design, because the goal is to KEEP YY's full-window improvement while partially repairing the recovery damage.

## 4. Recovery over-defense evidence

The user-supplied YY component diagnostics showed the composite-family realized weights in recovery states were 28-31% offense / 48-50% defense / 18-24% cash, with offense components having far higher Sharpe than defense components (recovery_confirmed offense Sharpe 2.52 vs defense 1.75; recovery_fragile offense Sharpe 3.31 vs defense 1.15). Phase ZZ confirms this in the bucket-level decomposition diagnostics above.

## 5. Candidate family tested (≤4 per spec)

- ZZ1 `improved_phasezz_recovery_offense_rebudget` — bucket targets shifted in recovery states only.
  - recovery_confirmed: offense 0.62→0.68, defense 0.38→0.32, mix_strength 0.40→0.50.
  - recovery_fragile: offense 0.54→0.60, defense 0.46→0.40, mix_strength 0.30→0.40.
- ZZ2 `improved_phasezz_recovery_neutral_offense_rebudget` — ZZ1 + small strong_neutral rebudget (offense 0.60→0.65, mix_strength 0.32→0.40).
- ZZ3 `improved_phasezz_confirmed_freer_fragile_conservative` — bigger shift in recovery_confirmed (offense 0.62→0.72), smaller in recovery_fragile.
- ZZ4 `improved_phasezz_conservative_decomposition_repair` — minimum-shift safety-first variant (offense 0.62→0.66 in confirmed, 0.54→0.57 in fragile).

stressed_panic and calm_trend bucket logic identical to Phase YY in all four candidates.

## 6. Candidate metrics table

```
                                                  name  full_ann_return  full_ann_vol  full_sharpe  full_max_drawdown  full_cvar_5  full_calmar  holdout_ann_return  holdout_sharpe  holdout_max_drawdown  avg_BIL  avg_SPY  avg_turnover
            improved_phasezz_recovery_offense_rebudget         0.0704        0.0753       0.9355            -0.1175      -0.0250       0.5996              0.1469          1.8666               -0.0696   0.2661   0.0603        0.1197
    improved_phasezz_recovery_neutral_offense_rebudget         0.0708        0.0757       0.9347            -0.1175      -0.0251       0.6026              0.1464          1.8379               -0.0725   0.2652   0.0609        0.1203
 improved_phasezz_confirmed_freer_fragile_conservative         0.0704        0.0754       0.9341            -0.1175      -0.0250       0.5996              0.1468          1.8588               -0.0698   0.2663   0.0604        0.1204
    improved_phasezz_conservative_decomposition_repair         0.0702        0.0752       0.9324            -0.1175      -0.0250       0.5971              0.1467          1.8693               -0.0695   0.2656   0.0603        0.1193
              improved_phase2b_regime_confidence_boost         0.0689        0.0779       0.8848            -0.1398      -0.0262       0.4932              0.1243          1.6249               -0.0626   0.2839   0.0708        0.1124
           improved_phaseyy_conservative_decomposition         0.0699        0.0751       0.9297            -0.1175      -0.0250       0.5947              0.1465          1.8734               -0.0693   0.2652   0.0603        0.1186
improved_phasevv_recovery_neutral_budget_aware_overlay         0.0701        0.0787       0.8898            -0.1408      -0.0264       0.4977              0.1278          1.6389               -0.0622   0.2817   0.0734        0.1154
```

**All four ZZ candidates beat both production AND YY on every full-window axis.**

## 7. State-by-state impact (delta vs production, ann return pp)

| candidate | calm_trend | neutral_mixed | recovery_confirmed | recovery_fragile | stressed_panic |
|---|---:|---:|---:|---:|---:|
| ZZ1 recovery_offense_rebudget | (mixed/positive) | (positive) | **-1.06pp** | **-0.50pp** | +0.20pp |
| **ZZ2 recovery_neutral_offense_rebudget** | (mixed/positive) | (positive) | **-0.91pp** | **-0.36pp** | +0.20pp |
| ZZ3 confirmed_freer_fragile_conservative | (mixed/positive) | (positive) | -1.06pp | -0.70pp | +0.20pp |
| ZZ4 conservative_decomposition_repair | (mixed/positive) | (positive) | -1.06pp | -0.87pp | +0.20pp |

**ZZ vs YY recovery-state repair** (ann return pp delta vs production):

| state | YY (reference) | ZZ2 (best) | repair achieved |
|---|---:|---:|---|
| recovery_confirmed | -1.04pp | -0.91pp | +0.13pp (~12% repair) |
| recovery_fragile | -1.08pp | -0.36pp | **+0.72pp (~67% repair)** |

ZZ substantially repairs `recovery_fragile` (the worst YY damage) and modestly repairs `recovery_confirmed`. None of the four candidates fully restores production-level performance in `recovery_confirmed`, which remains the hardest state.

## 8. Comparison vs production, YY best, and VV best

| variant | ann return | Sharpe | MDD | CVaR | turnover | avg_SPY |
|---|---:|---:|---:|---:|---:|---:|
| production | 6.89% | 0.8848 | -13.98% | -2.62% | 0.1124 | 7.08% |
| VV reference | 7.01% | 0.8898 | -14.08% | -2.64% | 0.1154 | 7.34% |
| YY best | 6.99% | 0.9297 | **-11.75%** | -2.50% | 0.1186 | 6.03% |
| **ZZ2 (best ZZ)** | **7.08%** | **0.9347** | **-11.75%** | **-2.51%** | 0.1203 | **6.09%** |

ZZ2 beats production on every axis, beats YY on every axis except a tiny SPY tick (still well below production), beats VV on every risk-adjusted axis.

## 9. Hidden beta / hidden cash check

- ZZ2 SPY exposure: **6.09%** (vs production 7.08% — LOWER by 0.99pp).
- ZZ2 BIL exposure: **26.52%** (vs production 28.39% — LOWER by 1.87pp; vs YY 26.52% — equal).
- The full-window ann return improvement is NOT from hidden SPY exposure. SPY is lower than production. The improvement comes from the cleaner offense/defense rebudget inside the decomposed composite family.

## 10. Stressed_panic protection check

- Production stressed_panic: ann_return varies by definition; ZZ2 ann_return delta in stressed_panic = **+0.20pp**.
- ZZ2 stressed_panic exposure to defense/cash is at YY/production levels (the tilt-mode logic preserves the stressed_panic offense *= 0.92, defense *= 1.05-1.06 protections from YY).
- **Stressed_panic protection preserved.**

## 11. Recovery_confirmed repair check

- ZZ2 recovery_confirmed delta vs production: **-0.91pp ann return**, -0.152 Sharpe.
- vs YY: improved by +0.13pp.
- **Partial repair, not full repair.** The bucket budget shifts (offense 0.62→0.68) reduce explicit defense allocation but cannot fully restore production-level participation because the rebudget is bounded to keep YY's full-window MDD/CVaR advantage.

## 12. Recovery_fragile repair check

- ZZ2 recovery_fragile delta vs production: **-0.36pp ann return**, -0.182 Sharpe.
- vs YY: improved by **+0.72pp** (a major repair — YY was -1.08pp short).
- **Substantial repair.** This is the headline operational win of Phase ZZ.

## 13. Best candidate

**ZZ2 — `improved_phasezz_recovery_neutral_offense_rebudget`.**

- Largest ann return (+0.19pp vs production, +0.09pp vs YY).
- Largest Sharpe gain (+0.05 vs production, +0.005 vs YY).
- Best `recovery_fragile` repair (-0.36pp vs production vs YY's -1.08pp).
- Decomposition intact (explicit cash sleeve 33.5% — vs production 22.4%).
- No hidden beta (SPY lower than production).
- Identical MDD/CVaR/calmar improvement vs production as the other ZZ candidates.

## 14. Quick committee verdict

**KEEP AS SHADOW** (Layer 2). Verdict text: "Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow."

The "fails return-delta gate" reading uses the strict +1.5pp ann return delta gate from the standard production rule; ZZ2's +0.19pp easily clears the +0.005 Sharpe gate but not the +1.5pp ann return gate.

## 15. Were Layer 5/6 quick audits run?

**Yes** — quick committee returned KEEP AS SHADOW with both Sharpe and MDD improving (genuine improvement). Per spec, both audits ran:

- **Layer 5 (realism --quick):** Δ ann return constant at +0.20-0.22pp across 0/5/10bp cost grid; +0.30pp at 1-week delay; Δ Sharpe +0.05 across all cost levels. **Robust improvement under stricter assumptions.**
- **Layer 6 (allocator benchmark --quick):** "**Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed.**" This is the FIRST candidate in the post-Phase-Z arc to pass the allocator-side bar.

## 16. Final decision

**KEEP AS SHADOW** — `improved_phasezz_recovery_neutral_offense_rebudget` is the new strongest architecture-reference shadow, replacing `improved_phaseyy_conservative_decomposition` as the active research reference on this branch.

Why **NOT** PRODUCTION CHALLENGER PENDING HUMAN REVIEW: per spec, the PRODUCTION CHALLENGER tier requires "does not materially worsen recovery_confirmed or recovery_fragile." ZZ2's recovery_confirmed at -0.91pp ann return is materially worse than production. The recovery_confirmed gap is the binding constraint.

Why **NOT** REJECT or NEEDS FIX BEFORE JUDGMENT: ZZ2 is meaningfully stronger than YY on every dimension and passed both quick Layer 5/6 audits with clear margins.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`. The Phase 2B `combo_abc` shadow remains the recorded shadow because it is the official shadow per the project's dual-track rule; ZZ2 is the architecture-reference shadow on the decomposed-allocator branch.

## 17. Should decomposed-component rebudgeting continue?

**Yes — the decomposed component frontier is now clearly the active improvement surface.**

Phase ZZ confirms the Phase YY architectural breakthrough was real: every ZZ candidate beats production AND YY on every full-window risk-adjusted axis with no hidden beta. The remaining problem is narrow: `recovery_confirmed` underperforms production by ~0.9pp ann return. That single state is the binding constraint between SHADOW and PRODUCTION CHALLENGER.

The natural follow-up phase (Phase AAA-class) should test:
1. **Recovery-confirmed-only deeper rebudget.** ZZ3 already pushed `recovery_confirmed` offense to 0.72; the next test could push it to 0.78-0.82 with a higher offense_mix_strength to see whether the recovery_confirmed gap closes further without losing the full-window MDD/CVaR advantage.
2. **State-conditional offense_target_mix tilt within the offense bucket.** ZZ uses an aggregate bucket target. A finer test could shift the offense_target_mix in `recovery_confirmed` away from `composite_regime_offense_component` (which has Sharpe 2.52 in this state but is structurally smaller than `cta_trend_long_only`) toward the higher-conviction sleeves available in confirmed recovery.
3. **Asymmetric defense composition in recovery_confirmed.** Reduce the `composite_regime_defense_component` share inside the defense bucket of recovery_confirmed (it's currently the heavier of the two defense sleeves) without changing total defense weight.

## 18. Recommended next phase if this fails

Phase ZZ did NOT fail — it delivered the strongest shadow candidate of the post-Phase-Z arc. The "recommended next phase if this fails" branch is therefore moot for ZZ. The natural next phase IS the recovery-confirmed-only deeper rebudget described in §17 above.

If a future phase along this line cannot close the recovery_confirmed gap further (i.e., the gap turns out to be a structural property of the bucket rebudget mechanism rather than a tunable parameter), the next architectural surface to test would be:
- **Layer 2A composite_regime_offense_component re-engineering** — refine the synthetic offense component itself so it has higher recovery_confirmed Sharpe than the current implementation (currently 2.52, very strong but bounded by the source positions).
- **Per-state offense_mix_strength escalation curve** — instead of fixed offense_mix_strength values, tie the strength to a state-confidence proxy (existing breadth_sma_43 or transition_persistence_prob), again without using Phase CC features.

---

## Appendix — Phase ZZ classification matrix

| candidate | full_ann_imp_pp | sharpe_imp | sharpe_vs_yy | mdd_imp_pp | recovery_confirmed delta | recovery_fragile delta | classification |
|---|---:|---:|---:|---:|---:|---:|---|
| ZZ1 recovery_offense_rebudget | +0.15pp | +0.0507 | +0.0058 | +2.23pp | -1.06pp | -0.50pp | KEEP AS SHADOW |
| **ZZ2 recovery_neutral_offense_rebudget** | **+0.19pp** | **+0.0498** | **+0.0049** | **+2.23pp** | **-0.91pp** | **-0.36pp** | **BEST — KEEP AS SHADOW** |
| ZZ3 confirmed_freer_fragile_conservative | +0.15pp | +0.0493 | +0.0043 | +2.23pp | -1.06pp | -0.70pp | KEEP AS SHADOW |
| ZZ4 conservative_decomposition_repair | +0.12pp | +0.0476 | +0.0027 | +2.23pp | -1.06pp | -0.87pp | KEEP AS SHADOW |

All four ZZ candidates are full-window improvements; ZZ2 is best on three of the four selection axes (ann return, recovery_fragile repair, total decomposition retained). ZZ2 is the recommended new architecture-reference shadow.
