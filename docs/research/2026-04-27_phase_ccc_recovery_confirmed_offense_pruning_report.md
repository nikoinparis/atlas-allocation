# Phase CCC — Recovery_Confirmed Offense Pruning

**Date:** 2026-05-01  
**Phase type:** bounded recovery_confirmed offense-pruning extension on top of BBB3  
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`  
**Official shadow pin (unchanged):** `improved_phase2b_combo_abc`  
**Starting architecture-reference shadow:** `improved_phasebbb_offense_defense_composition_combo`  
**Best Phase CCC candidate:** `improved_phaseccc_confirmed_cap_dual`

## 1. Commands executed

```bash
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_ccc_recovery_confirmed_offense_pruning.py
python3 scripts/phase_ccc_recovery_confirmed_offense_pruning.py
python3 scripts/research_committee_report.py improved_phaseccc_confirmed_cap_dual --quick
python3 scripts/backtest_realism_audit.py improved_phaseccc_confirmed_cap_dual --quick
python3 scripts/allocator_benchmark_audit.py improved_phaseccc_confirmed_cap_dual --quick
python3 scripts/research_committee_report.py improved_phaseccc_confirmed_cap_dual
```

`phase_ccc_recovery_confirmed_offense_pruning.py` invoked `scripts/build_improvement_artifacts.py` with:

```text
BUILD_VERSION_NAMES=
  improved_phase2b_regime_confidence_boost,
  improved_phase2b_combo_abc,
  improved_phaseyy_conservative_decomposition,
  improved_phasezz_recovery_neutral_offense_rebudget,
  improved_phaseaaa_confirmed_offense_mix_tilt,
  improved_phasebbb_offense_defense_composition_combo,
  improved_phaseccc_confirmed_cap_css,
  improved_phaseccc_confirmed_cap_dual,
  improved_phaseccc_confirmed_cap_dual_css,
  improved_phaseccc_conservative_confirmed_pruning
SAVE_ALLOCATOR_CHECKPOINTS=1
```

## 2. Files created or modified

Code:
- [build_improvement_artifacts.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/build_improvement_artifacts.py)
- [phase_ccc_recovery_confirmed_offense_pruning.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/phase_ccc_recovery_confirmed_offense_pruning.py)

Diagnostics:
- [phase_ccc_recovery_confirmed_pruning_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ccc_recovery_confirmed_offense_pruning/phase_ccc_recovery_confirmed_pruning_diagnostics.csv)
- [phase_ccc_recovery_confirmed_sleeve_contribution.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ccc_recovery_confirmed_offense_pruning/phase_ccc_recovery_confirmed_sleeve_contribution.csv)
- [phase_ccc_candidate_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ccc_recovery_confirmed_offense_pruning/phase_ccc_candidate_diagnostics.csv)

Candidate outputs:
- [phase_ccc_candidate_metrics_full.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ccc_candidate_metrics_full.csv)
- [phase_ccc_state_summary.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ccc_state_summary.csv)
- [phase_ccc_selection_table.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ccc_selection_table.csv)
- [phase_ccc_protocol.json](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ccc_protocol.json)

Audits:
- [improved_phaseccc_confirmed_cap_dual_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phaseccc_confirmed_cap_dual_audit.md)
- [improved_phaseccc_confirmed_cap_dual_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phaseccc_confirmed_cap_dual_realism_audit.md)
- [improved_phaseccc_confirmed_cap_dual_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phaseccc_confirmed_cap_dual_allocator_benchmark.md)

Docs:
- [2026-04-27_phase_ccc_recovery_confirmed_offense_pruning_report.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/2026-04-27_phase_ccc_recovery_confirmed_offense_pruning_report.md)
- [project_journey.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/project_journey.md)

## 3. Recovery_confirmed offense pruning diagnosis

The repo evidence says the remaining confirmed-state drag is now a **weak-sleeve allocation problem** inside BBB3's offense bucket.

Confirmed-state standalone sleeve quality:

| sleeve/component | ann return | Sharpe | BBB3 avg confirmed weight |
|---|---:|---:|---:|
| `composite_regime_offense_component` | 31.62% | 2.80 | 0.2130 |
| `composite_regime_defense_component` | 13.30% | 1.80 | 0.2118 |
| `cta_trend_long_only` | 9.69% | 1.02 | 0.1608 |
| `taa_10m_sma` | 2.93% | 0.37 | 0.1132 |
| `dual_momentum_topn` | 0.10% | 0.01 | 0.0930 |
| `composite_selective_signals` | -1.44% | -0.22 | 0.1251 |

The important conclusion is unchanged from the user brief and confirmed by the repo diagnostics:
- `dual_momentum_topn` is weak in `recovery_confirmed`
- `composite_selective_signals` is weak in `recovery_confirmed`
- `composite_regime_offense_component` is the strongest confirmed offense sleeve
- `cta_trend_long_only` is still a good confirmed offense sleeve
- `composite_regime_defense_component` remains helpful, not the blocker

## 4. Weak sleeve contribution evidence

BBB3 still left too much confirmed offense budget in the weak sleeves:

| sleeve | share of confirmed offense bucket | uplift if 1pp moved to `comp_off` | uplift if 1pp moved to `cta` |
|---|---:|---:|---:|
| `dual_momentum_topn` | 15.72% | +0.3152pp ann | +0.0959pp ann |
| `composite_selective_signals` | 21.14% | +0.3306pp ann | +0.1114pp ann |

This is the cleanest new Phase CCC evidence:
- capping `dual_momentum_topn` had the strongest realized effect
- capping `composite_selective_signals` alone barely moved confirmed performance
- the best reallocation target remained `composite_regime_offense_component`, with `cta_trend_long_only` as the secondary receiver

## 5. Candidate family tested

- `improved_phaseccc_confirmed_cap_css`
  - cap `composite_selective_signals` in `recovery_confirmed`
  - reallocate to `composite_regime_offense_component` and `cta_trend_long_only`
- `improved_phaseccc_confirmed_cap_dual`
  - cap `dual_momentum_topn` in `recovery_confirmed`
  - reallocate to `composite_regime_offense_component` and `cta_trend_long_only`
- `improved_phaseccc_confirmed_cap_dual_css`
  - cap both weak confirmed offense sleeves
  - reallocate mostly to `composite_regime_offense_component`
- `improved_phaseccc_conservative_confirmed_pruning`
  - smaller dual+CSS caps
  - conservative redistribution back into stronger confirmed sleeves

All four candidates:
- started from BBB3
- changed only `recovery_confirmed`
- preserved `recovery_fragile` logic as much as possible
- preserved `stressed_panic`
- kept the decomposed YY/ZZ/AAA/BBB architecture intact

## 6. Candidate metrics table

| candidate | ann return | Sharpe | MDD | CVaR-5% | avg BIL | avg SPY |
|---|---:|---:|---:|---:|---:|---:|
| production | 6.89% | 0.8848 | -13.98% | -2.62% | 28.39% | 7.08% |
| BBB3 | 7.13% | 0.9368 | -11.75% | -2.53% | 26.66% | 6.08% |
| CCC1 | 7.13% | 0.9366 | -11.75% | -2.53% | 26.69% | 6.08% |
| **CCC2** | **7.14%** | **0.9376** | **-11.75%** | **-2.53%** | **26.68%** | **6.06%** |
| CCC3 | 7.14% | 0.9370 | -11.76% | -2.53% | 26.72% | 6.10% |
| CCC4 | 7.14% | 0.9375 | -11.75% | -2.53% | 26.67% | 6.08% |

CCC2 was the best full-window candidate.

## 7. Recovery_confirmed repair check

Recovery_confirmed annual return deltas:

| candidate | vs production | vs BBB3 |
|---|---:|---:|
| BBB3 | -0.6692pp | — |
| CCC1 | -0.6667pp | +0.0025pp |
| **CCC2** | **-0.6107pp** | **+0.0585pp** |
| CCC3 | -0.6370pp | +0.0321pp |
| CCC4 | -0.6325pp | +0.0366pp |

Result:
- all four CCC candidates improved `recovery_confirmed` versus BBB3
- the strongest confirmed repair came from **capping `dual_momentum_topn`**
- CSS-only pruning was too weak
- dual+CSS pruning helped, but not more than the simpler dual-only cap

The confirmed gap is still materially below production, but CCC2 narrowed it the most.

## 8. Recovery_fragile preservation check

Recovery_fragile annual return deltas:

| candidate | vs production | vs BBB3 |
|---|---:|---:|
| BBB3 | -0.2044pp | — |
| CCC1 | -0.2044pp | +0.0000pp |
| **CCC2** | **-0.1804pp** | **+0.0240pp** |
| CCC3 | -0.1607pp | +0.0437pp |
| CCC4 | -0.1914pp | +0.0130pp |

CCC2 preserved and modestly improved `recovery_fragile` versus BBB3.

## 9. Stressed_panic protection check

CCC2 preserved stressed-panic behavior:
- stressed_panic ann delta vs production: `+0.2067pp`
- stressed_panic ann delta vs BBB3: `+0.0007pp`
- stressed_panic Sharpe delta vs production: `-0.0164`

That is effectively unchanged relative to the architecture win already achieved in BBB3.

## 10. Full state-by-state impact

For the best candidate CCC2:

| state | delta mean weekly vs production | delta mean weekly vs BBB3 |
|---|---:|---:|
| `calm_trend` | `+0.000091` | `+0.000000` |
| `neutral_mixed` | `+0.000027` | `+0.000000` |
| `recovery_confirmed` | `-0.000105` | `+0.000011` |
| `recovery_fragile` | `-0.000027` | `+0.000004` |
| `stressed_panic` | `+0.000047` | `+0.000000` |

Interpretation:
- CCC2 improved the targeted blocker state versus BBB3
- it did so without giving back `recovery_fragile`
- it left the rest of the architecture essentially unchanged

## 11. Comparison vs production, YY best, ZZ2, AAA2, and BBB3

| metric | production | YY best | ZZ2 | AAA2 | BBB3 | **CCC2** |
|---|---:|---:|---:|---:|---:|---:|
| ann return | 6.89% | 6.99% | 7.08% | 7.11% | 7.13% | **7.14%** |
| Sharpe | 0.8848 | 0.9297 | 0.9347 | 0.9360 | 0.9368 | **0.9376** |
| MDD | -13.98% | -11.75% | -11.75% | -11.75% | -11.75% | **-11.75%** |
| CVaR-5% | -2.62% | -2.50% | -2.51% | -2.52% | -2.53% | **-2.53%** |
| avg BIL | 28.39% | 26.52% | 26.52% | 26.55% | 26.66% | 26.68% |
| avg SPY | 7.08% | 6.03% | 6.09% | 6.11% | 6.08% | **6.06%** |
| recovery_confirmed Δ vs prod | — | -1.04pp | -0.91pp | -0.72pp | -0.67pp | **-0.61pp** |
| recovery_fragile Δ vs prod | — | -1.08pp | -0.36pp | -0.27pp | -0.20pp | **-0.18pp** |

## 12. Hidden beta / hidden cash check

CCC2 is still not a hidden-beta shortcut:
- avg SPY fell to `6.06%` vs production `7.08%`
- avg BIL stayed lower than production at `26.68%` vs `28.39%`
- explicit decomposed cash stayed in place
- the architecture still avoids the old hidden `composite_regime_conditioned` defense/cash duplication

So the Phase CCC improvement is still coming from **better confirmed offense composition**, not from more beta or more hidden cash relief.

## 13. Best candidate

**`improved_phaseccc_confirmed_cap_dual`**

Why it won:
- best annual return of the CCC set
- best Sharpe of the CCC set
- strongest `recovery_confirmed` improvement versus BBB3
- preserved `recovery_fragile`
- preserved stressed-panic
- not hidden beta

## 14. Quick committee verdict

Quick committee verdict for CCC2: **KEEP AS SHADOW**

Reference:
- [improved_phaseccc_confirmed_cap_dual_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phaseccc_confirmed_cap_dual_audit.md)

I also ran the full committee report because CCC2 passed the phase-local strict CCC gates and cleared the quick Layer 5/6 path. The final committee verdict remained **KEEP AS SHADOW** because the candidate still fails the production handoff return-delta standard in `recovery_confirmed`.

## 15. Were Layer 5/6 quick audits run?

**Yes.**

Layer 5 realism:
- Δ ann return at 5bp: `+0.27pp`
- Δ ann return at 10bp: `+0.25pp`
- Δ ann return with 1-week delay: `+0.36pp`
- verdict: **candidate survives doubled-cost scenario**

Layer 6 allocator benchmark:
- beats equal weight, inverse vol, internal HRP, and production on annual return and Sharpe
- verdict: **allocator-side bar passed**

References:
- [improved_phaseccc_confirmed_cap_dual_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phaseccc_confirmed_cap_dual_realism_audit.md)
- [improved_phaseccc_confirmed_cap_dual_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phaseccc_confirmed_cap_dual_allocator_benchmark.md)

## 16. Final decision

**KEEP AS SHADOW**

Why not `PRODUCTION CHALLENGER PENDING HUMAN REVIEW`:
- CCC2 materially improves full-window Sharpe, MDD, and CVaR versus production
- CCC2 improves `recovery_confirmed` versus BBB3
- CCC2 passes quick realism and allocator benchmark
- CCC2 is not hidden beta
- but `recovery_confirmed` is still `-0.6107pp` annual return versus production, so the exact blocker state is still not closed enough for a production-challenger handoff

Pin status:
- production pin unchanged: `improved_phase2b_regime_confidence_boost`
- official shadow pin unchanged: `improved_phase2b_combo_abc`
- architecture-reference shadow should now move from BBB3 to **CCC2**

## 17. Whether recovery_confirmed offense pruning should continue

**Yes, but narrowly.**

Phase CCC did exactly what it was supposed to test:
- it confirmed that confirmed-state weak-sleeve pruning works
- it showed the strongest improvement came from pruning `dual_momentum_topn`, not from CSS-only pruning
- it preserved BBB3's excellent full-window profile

This branch is not exhausted yet because the confirmed gap kept shrinking without breaking the rest of the architecture.

## 18. Recommended next phase if this fails

The next bounded step should stay on the active BBB/CCC architecture and test a **confirmed-only harder weak-sleeve exclusion / substitution phase**:
- push `dual_momentum_topn` lower still in `recovery_confirmed`
- test whether `composite_selective_signals` should also be near-excluded there
- preserve `composite_regime_offense_component`, `cta_trend_long_only`, and `composite_regime_defense_component`
- keep total confirmed offense/defense bucket near BBB3 / CCC2

The architecture is now clearly right. The remaining problem is the final confirmed-state offense mix, not overlays, not hidden BIL, and not total offense size.
