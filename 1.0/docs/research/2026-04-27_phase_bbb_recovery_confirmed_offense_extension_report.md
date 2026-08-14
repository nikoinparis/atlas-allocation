# Phase BBB — Recovery_Confirmed Offense-Composition Extension

**Date:** 2026-05-01  
**Phase type:** bounded recovery_confirmed offense-composition extension on top of AAA2  
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`  
**Official shadow pin (unchanged):** `improved_phase2b_combo_abc`  
**Starting architecture-reference shadow:** `improved_phaseaaa_confirmed_offense_mix_tilt`  
**Best Phase BBB candidate:** `improved_phasebbb_offense_defense_composition_combo`

## 1. Commands executed

```bash
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_bbb_recovery_confirmed_offense_extension.py
python3 scripts/phase_bbb_recovery_confirmed_offense_extension.py
python3 scripts/research_committee_report.py improved_phasebbb_offense_defense_composition_combo --quick
python3 scripts/backtest_realism_audit.py improved_phasebbb_offense_defense_composition_combo --quick
python3 scripts/allocator_benchmark_audit.py improved_phasebbb_offense_defense_composition_combo --quick
```

`phase_bbb_recovery_confirmed_offense_extension.py` invoked `scripts/build_improvement_artifacts.py` with:

```text
BUILD_VERSION_NAMES=
  improved_phase2b_regime_confidence_boost,
  improved_phase2b_combo_abc,
  improved_phaseyy_conservative_decomposition,
  improved_phasezz_recovery_neutral_offense_rebudget,
  improved_phaseaaa_confirmed_offense_mix_tilt,
  improved_phasebbb_stronger_confirmed_offense_mix,
  improved_phasebbb_composite_offense_component_tilt,
  improved_phasebbb_offense_defense_composition_combo,
  improved_phasebbb_conservative_confirmed_composition
SAVE_ALLOCATOR_CHECKPOINTS=1
```

## 2. Files created or modified

Code:
- [build_improvement_artifacts.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/build_improvement_artifacts.py)
- [phase_bbb_recovery_confirmed_offense_extension.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/phase_bbb_recovery_confirmed_offense_extension.py)

Diagnostics:
- [phase_bbb_recovery_confirmed_composition_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_bbb_recovery_confirmed_offense_extension/phase_bbb_recovery_confirmed_composition_diagnostics.csv)
- [phase_bbb_recovery_confirmed_sleeve_contribution.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_bbb_recovery_confirmed_offense_extension/phase_bbb_recovery_confirmed_sleeve_contribution.csv)
- [phase_bbb_candidate_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_bbb_recovery_confirmed_offense_extension/phase_bbb_candidate_diagnostics.csv)

Candidate outputs:
- [phase_bbb_candidate_metrics_full.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_bbb_candidate_metrics_full.csv)
- [phase_bbb_state_summary.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_bbb_state_summary.csv)
- [phase_bbb_selection_table.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_bbb_selection_table.csv)
- [phase_bbb_protocol.json](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_bbb_protocol.json)

Audits:
- [improved_phasebbb_offense_defense_composition_combo_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phasebbb_offense_defense_composition_combo_audit.md)
- [improved_phasebbb_offense_defense_composition_combo_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phasebbb_offense_defense_composition_combo_realism_audit.md)
- [improved_phasebbb_offense_defense_composition_combo_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phasebbb_offense_defense_composition_combo_allocator_benchmark.md)

Docs:
- [2026-04-27_phase_bbb_recovery_confirmed_offense_extension_report.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/2026-04-27_phase_bbb_recovery_confirmed_offense_extension_report.md)
- [project_journey.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/project_journey.md)

## 3. Recovery_confirmed composition diagnosis

The repo evidence still says the problem is **within-bucket composition**, not total recovery_confirmed offense size.

Recovery_confirmed average sleeve/component weights:

| version | dual | cta | css | comp_off | comp_def | taa | offense total | defense total | explicit cash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| production | 0.0878 | 0.1084 | 0.2311 | n/a | n/a | 0.1779 | 0.4272 | 0.1779 | 0.0638 |
| YY best | 0.1083 | 0.1348 | 0.1766 | 0.1356 | 0.2288 | 0.1430 | 0.5553 | 0.3718 | 0.0729 |
| ZZ2 | 0.1144 | 0.1432 | 0.1735 | 0.1636 | 0.2010 | 0.1255 | 0.5947 | 0.3266 | 0.0788 |
| AAA2 | 0.1070 | 0.1670 | 0.1448 | 0.1747 | 0.2007 | 0.1253 | 0.5936 | 0.3259 | 0.0805 |
| **BBB3** | **0.0930** | **0.1608** | **0.1251** | **0.2130** | **0.2118** | **0.1132** | **0.5918** | **0.3250** | **0.0832** |

Takeaways:
- AAA’s core finding held: keeping the total confirmed bucket around `0.68 / 0.32` was still right.
- `composite_regime_offense_component` remained the best recovery_confirmed offense leg and was still underused in AAA2.
- `cta_trend_long_only` remained helpful.
- `composite_selective_signals` remained the weak confirmed offense leg and still looked too large in AAA2.
- `dual_momentum_topn` was also weak in recovery_confirmed.
- Repo evidence still **did not** support a TAA-heavy defense fix in recovery_confirmed; `composite_regime_defense_component` remained the stronger defense sleeve there.

## 4. Sleeve/component causing the remaining recovery_confirmed gap

The remaining recovery_confirmed drag is mostly an **offense composition problem**, not a defense problem.

Recovery_confirmed standalone sleeve/component quality for AAA2 / BBB3:

| sleeve | standalone ann return | standalone Sharpe | AAA2 avg weight | BBB3 avg weight |
|---|---:|---:|---:|---:|
| `composite_regime_offense_component` | 31.62% | 2.80 | 0.1747 | **0.2130** |
| `composite_regime_defense_component` | 13.30% | 1.80 | 0.2007 | **0.2118** |
| `cta_trend_long_only` | 9.69% | 1.02 | 0.1670 | 0.1608 |
| `taa_10m_sma` | 2.93% | 0.37 | 0.1253 | **0.1132** |
| `composite_selective_signals` | -1.44% | -0.22 | 0.1448 | **0.1251** |
| `dual_momentum_topn` | 0.10% | 0.01 | 0.1070 | **0.0930** |

This means:
- `composite_regime_defense_component` is **not** the blocker.
- `taa_10m_sma` is **not** the better confirmed defense sleeve.
- The live blocker is that `composite_selective_signals` and `dual_momentum_topn` still absorb too much confirmed offense budget relative to their confirmed-state quality.

## 5. Candidate family tested

- `improved_phasebbb_stronger_confirmed_offense_mix`
  - AAA2 mix, same confirmed bucket totals, offense_mix_strength `0.65 → 0.75`.
- `improved_phasebbb_composite_offense_component_tilt`
  - AAA2 totals, more confirmed weight to `composite_regime_offense_component`, less to `dual_momentum_topn` and `composite_selective_signals`.
- `improved_phasebbb_offense_defense_composition_combo`
  - same confirmed totals, stronger offense mix plus a repo-evidence defense repair that leaned toward `composite_regime_defense_component`, not TAA.
- `improved_phasebbb_conservative_confirmed_composition`
  - minimum bounded increase in confirmed offense composition strength.

Recovery_fragile and stressed_panic logic were left unchanged in all four candidates.

## 6. Candidate metrics table

| candidate | ann return | Sharpe | MDD | CVaR-5% | avg BIL | avg SPY |
|---|---:|---:|---:|---:|---:|---:|
| production | 6.89% | 0.8848 | -13.98% | -2.62% | 28.39% | 7.08% |
| AAA2 | 7.11% | 0.9360 | -11.75% | -2.52% | 26.55% | 6.11% |
| BBB1 | 7.12% | 0.9362 | -11.75% | -2.52% | 26.58% | 6.11% |
| BBB2 | 7.12% | 0.9362 | -11.75% | -2.53% | 26.65% | 6.09% |
| **BBB3** | **7.13%** | **0.9368** | **-11.75%** | **-2.53%** | **26.66%** | **6.08%** |
| BBB4 | 7.12% | 0.9362 | -11.75% | -2.52% | 26.60% | 6.10% |

BBB3 was the strongest full-window candidate.

## 7. Recovery_confirmed repair check

Recovery_confirmed annual return deltas:

| candidate | vs production | vs AAA2 |
|---|---:|---:|
| AAA2 | -0.7230pp | — |
| BBB1 | -0.7246pp | -0.0016pp |
| BBB2 | -0.8667pp | -0.1437pp |
| **BBB3** | **-0.6692pp** | **+0.0539pp** |
| BBB4 | -0.7943pp | -0.0713pp |

Result:
- BBB3 is the only candidate that **actually improved recovery_confirmed versus AAA2**.
- The gain is modest, but it is real and it came from cleaner composition, not from more total offense or from higher SPY.
- BBB2 confirmed that simply forcing more `composite_regime_offense_component` without the right defense composition does not work cleanly.

## 8. Recovery_fragile preservation check

Recovery_fragile annual-return deltas:

| candidate | vs production | vs AAA2 |
|---|---:|---:|
| AAA2 | -0.2729pp | — |
| BBB1 | -0.2346pp | +0.0383pp |
| BBB2 | -0.2088pp | +0.0641pp |
| **BBB3** | **-0.2044pp** | **+0.0685pp** |
| BBB4 | -0.2313pp | +0.0416pp |

BBB3 preserved and slightly improved recovery_fragile versus AAA2.

## 9. Stressed_panic protection check

All four BBB candidates preserved stressed_panic behavior. For BBB3:
- stressed_panic ann delta vs production: `+0.2060pp`
- stressed_panic ann delta vs AAA2: `+0.0038pp`

So BBB did not pay for the confirmed-state repair by weakening the panic guardrail.

## 10. Full state-by-state impact

BBB3 weekly-state deltas versus production:

| state | delta mean weekly return | cumulative delta |
|---|---:|---:|
| `calm_trend` | `+0.000091` | `+0.0415` |
| `neutral_mixed` | `+0.000027` | `+0.0331` |
| `recovery_confirmed` | `-0.000117` | `-0.0056` |
| `recovery_fragile` | `-0.000031` | `-0.0019` |
| `stressed_panic` | `+0.000047` | `+0.0102` |

Interpretation:
- BBB3 still does not beat production inside recovery_confirmed.
- But it narrows the confirmed gap versus AAA2 and improves recovery_fragile at the same time.
- The full-window profile remains excellent because the architecture is still much cleaner than production in the rest of the sample.

## 11. Comparison vs production, YY best, ZZ2, and AAA2

| metric | production | YY best | ZZ2 | AAA2 | **BBB3** |
|---|---:|---:|---:|---:|---:|
| ann return | 6.89% | 6.99% | 7.08% | 7.11% | **7.13%** |
| Sharpe | 0.8848 | 0.9297 | 0.9347 | 0.9360 | **0.9368** |
| MDD | -13.98% | -11.75% | -11.75% | -11.75% | **-11.75%** |
| CVaR-5% | -2.62% | -2.50% | -2.51% | -2.52% | **-2.53%** |
| avg BIL | 28.39% | 26.52% | 26.52% | 26.55% | 26.66% |
| avg SPY | 7.08% | 6.03% | 6.09% | 6.11% | **6.08%** |
| recovery_confirmed Δ vs prod | — | -1.04pp | -0.91pp | -0.72pp | **-0.67pp** |
| recovery_fragile Δ vs prod | — | -1.08pp | -0.36pp | -0.27pp | **-0.20pp** |

## 12. Hidden beta / hidden cash check

BBB3 is still not a hidden-beta shortcut:
- avg SPY: `6.08%` vs production `7.08%`
- avg BIL: `26.66%` vs production `28.39%`
- explicit decomposed cash sleeve remains in place
- hidden composite cash/defense duplication is still reduced because `composite_regime_conditioned` remains absent from the allocator

So the improvement is still coming from sleeve/component composition, not from silently levering market beta.

## 13. Best candidate

**`improved_phasebbb_offense_defense_composition_combo`**

Why it won:
- best Sharpe of the BBB set
- best annual return of the BBB set
- only BBB candidate that improved recovery_confirmed versus AAA2
- preserved recovery_fragile and stressed_panic
- no hidden beta profile

## 14. Quick committee verdict

Quick committee verdict for BBB3: **KEEP AS SHADOW**

Reference:
- [improved_phasebbb_offense_defense_composition_combo_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phasebbb_offense_defense_composition_combo_audit.md)

The committee still did not mark it as a production challenger because the standard production handoff rule remains stricter than the phase-local BBB rule, and `recovery_confirmed` is still materially below production.

## 15. Were Layer 5/6 quick audits run?

**Yes.**

Layer 5 realism:
- doubled-cost delta ann return: `+0.25pp`
- 1-week delay delta ann return: `+0.35pp`
- verdict: **survives doubled-cost scenario**

Layer 6 allocator benchmark:
- beats production on annual return and Sharpe
- beats equal weight, inverse vol, and internal HRP on Sharpe
- verdict: **allocator-side bar passed**

References:
- [improved_phasebbb_offense_defense_composition_combo_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phasebbb_offense_defense_composition_combo_realism_audit.md)
- [improved_phasebbb_offense_defense_composition_combo_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phasebbb_offense_defense_composition_combo_allocator_benchmark.md)

## 16. Final decision

**KEEP AS SHADOW**

Why not `PRODUCTION CHALLENGER PENDING HUMAN REVIEW`:
- BBB3 clears the phase-local strict BBB gates.
- It passes quick Layer 5/6.
- It is not hidden beta.
- But `recovery_confirmed` is still `-0.6692pp` annual return versus production, so it still materially worsens the exact blocker state that kept AAA2 out of production.

Pin status:
- production pin unchanged: `improved_phase2b_regime_confidence_boost`
- official shadow pin unchanged: `improved_phase2b_combo_abc`
- architecture-reference shadow should now move from AAA2 to **BBB3**

## 17. Should recovery_confirmed composition extension continue?

**Yes.**

This branch is still active because BBB3 did exactly what the bounded extension was supposed to test:
- it improved full-window Sharpe versus AAA2
- it improved recovery_confirmed versus AAA2
- it preserved recovery_fragile and stressed_panic

So the architecture still has room on this frontier.

## 18. Recommended next phase if BBB is not enough

The next bounded phase should stay on the decomposed-component frontier and target the remaining low-quality confirmed offense directly:

1. confirmed-only pruning / harder cap on `dual_momentum_topn`
2. confirmed-only pruning / lower target share for `composite_selective_signals`
3. preserve `composite_regime_offense_component`, `cta_trend_long_only`, and `composite_regime_defense_component`

That is the cleanest next step because BBB shows the remaining recovery_confirmed gap is no longer about bucket totals, overlay cash, or defense being too large. It is about the last part of the **offense mix** still flowing to the wrong confirmed-state sleeves.
