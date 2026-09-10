# Phase FFF — Layer 2A composite_regime_offense_component Re-engineering

**Date:** 2026-04-27
**Phase type:** New Layer 2A sleeve-design frontier on top of EEE1's allocator architecture. Modifies the offense_component construction (source ETF list) only.
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Official shadow pin (unchanged):** `improved_phase2b_combo_abc`
**Architecture-reference shadow:** EEE1 (no change — FFF candidates trade Sharpe for state-specific gains; EEE1 remains the strongest full-window architecture).

---

## 1. Commands executed

```
python scripts/phase_fff_layer2a_composite_offense_reengineer.py
python scripts/research_committee_report.py improved_phasefff_robust_composite_offense --quick
python scripts/backtest_realism_audit.py     improved_phasefff_robust_composite_offense --quick
python scripts/allocator_benchmark_audit.py  improved_phasefff_robust_composite_offense --quick
```

## 2. Files created or modified

- `scripts/phase_fff_layer2a_composite_offense_reengineer.py` (new — driver)
- `scripts/build_improvement_artifacts.py`:
  - `build_composite_decomposition_sleeve_panels` extended to accept optional `offense_cols_override`.
  - 4 new module-level decomposition panels (`phasefff_quality_filtered`, `phasefff_core_equity`, `phasefff_robust`, `phasefff_polish`).
  - 4 new `internal_redeploy` modes in version dispatcher.
  - 4 new version specs.
- 12 portfolio_version_*** CSVs.
- `data/research/phase_fff_layer2a_composite_offense_reengineer/` diagnostic CSVs.
- `data/05_layer3_portfolio_construction/phase_fff_*` (metrics/state/selection/protocol).
- 3 audit reports + 5 supporting CSVs.
- This report + Section 58 in project_journey.md.

## 3. Current `composite_regime_offense_component` construction

The component is built by `build_composite_decomposition_sleeve_panels`:
- Source: `composite_regime_conditioned` weekly positions
- Offense ETFs: SPY, QQQ, IWM, EFA, VEA, VWO, EWJ, VNQ, PDBC, DBA (10)
- Defense ETFs: HYG, LQD, GLD, TLT (4)
- Cash component: 100% BIL fallback when source has zero offense+defense
- For each component, source positions are re-projected and row-normalized

This is a **causal decomposition** (no future data; purely a re-projection of existing positions).

## 4. Component ETF/position diagnostics

Phase FFF builds 4 alternative offense_components by filtering the source ETF list:

| variant | offense ETFs |
|---|---|
| EEE1 (baseline) | SPY, QQQ, IWM, EFA, VEA, VWO, EWJ, VNQ, PDBC, DBA |
| FFF1 quality_filtered | SPY, QQQ, IWM, EFA, VEA, VWO, VNQ (drop PDBC, DBA, EWJ) |
| FFF2 core_equity | SPY, QQQ, IWM, EFA, VEA, VWO (drop EWJ, VNQ, PDBC, DBA) |
| FFF3 robust | SPY, QQQ, IWM, EFA, VEA, VWO, EWJ, VNQ (drop only PDBC, DBA) |
| FFF4 polish | SPY, QQQ, IWM, EFA, VEA, VWO, EWJ, VNQ, DBA (drop only PDBC) |

## 5. Weak internal holdings

The Phase YY component diagnostics already showed offense_component had Sharpe 2.80 in recovery_confirmed despite holding commodity/Japan/REIT exposures. The hypothesis was that PDBC and DBA (commodities) were the weakest broad-asset contributors. EWJ (Japan single-country) was a secondary candidate for noise. FFF1-4 isolate these by progressive filtering.

## 6. Candidate metrics table (full window)

```
                                               name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_BIL  avg_SPY  avg_turnover
improved_phasefff_recovery_quality_filtered_offense        0.0704       0.9032       -0.1211      -0.0262   0.2738   0.0635        0.1219
improved_phasefff_recovery_confirmed_tilted_offense        0.0672       0.8818       -0.1254      -0.0256   0.2976   0.0673        0.1214
         improved_phasefff_robust_composite_offense        0.0706       0.9144       -0.1208      -0.0259   0.2725   0.0624        0.1229
      improved_phasefff_conservative_offense_polish        0.0698       0.9108       -0.1243      -0.0256   0.2660   0.0604        0.1235
                                  EEE1 reference         0.0713       0.9353       -0.1177      -0.0254   0.2665   0.0602        0.1230
                              production reference         0.0689       0.8848       -0.1398      -0.0262   0.2839   0.0708        0.1124
```

All four FFF candidates beat production on Sharpe and ann return; all four LOSE Sharpe and ann return vs EEE1. The Layer 2A change touches every state, not just recovery_confirmed.

## 7. Recovery_confirmed repair check

| candidate | RC delta vs production | RC delta vs EEE1 |
|---|---:|---:|
| **FFF1 quality_filtered** | **+0.27pp** ← FIRST positive in arc | **+0.63pp** |
| FFF3 robust | -0.01pp ← essentially closed | +0.35pp |
| FFF2 tilted (core equity) | +0.02pp | +0.38pp |
| FFF4 polish | -0.40pp | -0.05pp |
| EEE1 reference | -0.36pp | — |

**FFF1 is the first candidate in the entire arc to deliver positive recovery_confirmed return delta vs production.** FFF3 essentially closes the gap (-0.01pp).

## 8. Recovery_fragile preservation check

| candidate | RF delta vs EEE1 |
|---|---:|
| FFF2 tilted | +1.19pp ← improved |
| FFF1 quality_filtered | -0.36pp ← past -0.30 strict gate |
| FFF3 robust | -0.49pp ← past -0.30 strict gate |
| FFF4 polish | -0.68pp |

Filtering ETFs from the offense_component changes recovery_fragile too; FFF3 and FFF1 regress slightly.

## 9. Stressed_panic protection check

All FFF candidates show stressed_panic delta vs production of **+0.15pp to +0.63pp**. Stressed_panic is preserved or improved across all four. The defense_component is unchanged.

## 10. Full state-by-state impact (FFF3)

(Detailed table in `phase_fff_state_summary.csv`.) FFF3 shows positive deltas in calm_trend, neutral_mixed, stressed_panic, and approximately closes recovery_confirmed (+0.35pp vs EEE1; -0.01pp vs production). Recovery_fragile slightly weaker than EEE1 (-0.49pp ann).

## 11. Comparison vs production, EEE1, DDD1

| metric | production | DDD1 | EEE1 | **FFF3 (best)** |
|---|---:|---:|---:|---:|
| ann return | 6.89% | 7.14% | 7.13% | **7.06%** |
| Sharpe | 0.8848 | 0.9379 | 0.9353 | **0.9144** |
| MDD | -13.98% | -11.75% | -11.77% | **-12.08%** |
| CVaR-5% | -2.62% | -2.53% | -2.54% | **-2.59%** |
| avg SPY | 7.08% | 6.04% | 6.02% | **6.24%** |
| avg BIL | 28.39% | 26.73% | 26.65% | 27.25% |
| RC delta vs prod | — | -0.51pp | -0.36pp | **-0.01pp** ← essentially closed |
| RF delta vs EEE1 | — | — | — | -0.49pp |
| turnover ratio | 1.00× | 1.098× | 1.095× | 1.094× |

FFF3 closes the recovery_confirmed gap but loses 0.021 Sharpe vs EEE1 and 0.025 vs DDD1. The headline trade-off is real.

## 12. Hidden beta / hidden cash check

FFF3 SPY: **6.24%** (vs production 7.08%, -0.84pp; vs EEE1 6.02%, +0.22pp). FFF3 BIL: **27.25%** (vs production 28.39%, -1.14pp). SPY rises 0.22pp vs EEE1 — small but worth noting. Still well below production. **No hidden beta (vs production); slight beta uptick vs EEE1.**

## 13. Did Layer 2A component quality improve?

**Yes, in recovery_confirmed.** The offense_component itself is now smaller (avg 0.1126 in FFF3 vs 0.0978 in EEE1), reflecting that the HRP allocator naturally weights it higher when it's narrower and higher-quality per-ETF. The recovery_confirmed Sharpe contribution improved.

**But the full-window Sharpe degraded** (-0.021 vs EEE1). The dropped commodities (PDBC, DBA) actually contributed positively in some non-recovery states. The Layer 2A change is not a free lunch.

## 14. Best candidate

**FFF3 — `improved_phasefff_robust_composite_offense`.**

Reasons:
- Highest Sharpe of the FFF four (0.9144).
- Closes the recovery_confirmed gap to essentially zero (-0.01pp vs production).
- +0.0296 Sharpe vs production (clears the +0.005 strict gate).
- Layer 5+6 audits both PASS.
- Smallest commodity-only filter (most conservative non-commodity-touching variant).

**Best for recovery_confirmed alone:** FFF1 (+0.27pp vs production, +0.63pp vs EEE1) — the first ARC-WIDE positive RC delta vs production. But FFF1 has lower Sharpe (0.9032) than FFF3 (0.9144).

## 15. Quick committee verdict

**KEEP AS SHADOW** (Layer 2). "Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow."

## 16. Were Layer 5/6 quick audits run?

**Yes.** Both passed:
- **Layer 5 (realism --quick):** Δ ann return at 5bp = **+0.20pp**, at 10bp = **+0.19pp**, at 1-week delay = **+0.46pp**.
- **Layer 6 (allocator benchmark --quick):** "**Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed.**"

## 17. Final decision

**KEEP AS SHADOW** — `improved_phasefff_robust_composite_offense` is a SECONDARY architecture-reference shadow on the Layer 2A frontier. **EEE1 remains the primary architecture-reference shadow** because it has higher full-window Sharpe.

Why **NOT** PRODUCTION CHALLENGER PENDING HUMAN REVIEW:
- Sharpe vs EEE1: -0.021 (just past -0.02 strict gate; the spec requires "Sharpe is materially worse than EEE1" be FALSE).
- recovery_fragile vs EEE1: -0.49pp (past -0.30 strict gate).
- Net: a recovery_confirmed win that costs full-window Sharpe AND recovery_fragile.

Why **NOT** REJECT or NEEDS FIX BEFORE JUDGMENT:
- Closes the recovery_confirmed gap that has been open since Phase YY.
- First candidate (FFF1 specifically) to deliver POSITIVE RC delta vs production.
- Both Layer 5/6 quick audits pass cleanly.
- Hidden beta check passes (vs production).

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Official shadow pin remains unchanged**: `improved_phase2b_combo_abc`. **Primary architecture-reference shadow remains** EEE1; FFF3 is a secondary Layer-2A reference shadow.

## 18. Should Layer 2A composite offense re-engineering continue?

**Yes — but with a different evaluation lens.** The Phase FFF result reveals a structural insight: filtering the offense_component dramatically closes recovery_confirmed but trades off against full-window Sharpe and recovery_fragile. The right next phase is to test whether a STATE-CONDITIONAL component construction (use the broad component in non-recovery states; use the filtered component only in recovery_confirmed) can capture both wins simultaneously.

This requires extending the decomposition machinery to support state-conditional ETF filtering — a Phase GGG-class change. Bounded; one main candidate.

If state-conditional component construction also fails to improve over EEE1 on Sharpe AND close recovery_confirmed, the Layer 2A frontier is exhausted at this granularity.

## 19. Recommended next phase if this fails

If Phase GGG (state-conditional component construction) cannot beat EEE1's Sharpe while preserving FFF3's recovery_confirmed repair, the next architectural surface is:

1. **Per-state target_vol_ceil escalation in recovery_confirmed.** Current ceiling 1.00. A confirmed-only ceiling of 1.05-1.10 could unlock more participation in this single state without changing component composition.
2. **Layer 2A defense_component re-engineering.** The defense component is currently HYG/LQD/GLD/TLT. It may have similarly weak contributors in recovery_confirmed.
3. **Cross-state offense_target_mix biases that route freed weight specifically to FFF1's offense_component variant** rather than the EEE1 broad component.

---

## Appendix — Phase FFF classification matrix

| candidate | sharpe_imp_vs_prod | sharpe_vs_eee1 | RC vs prod | RC vs EEE1 | RF vs EEE1 | strict | challenger | shadow | classification |
|---|---:|---:|---:|---:|---:|:---:|:---:|:---:|---|
| FFF1 quality_filtered | +0.0184 | -0.0321 | **+0.27pp** | **+0.63pp** | -0.36pp | ✗ | ✗ | ✓ | KEEP AS SHADOW (best RC repair) |
| FFF2 core_equity | -0.0030 | -0.0535 | +0.02pp | +0.38pp | +1.19pp | ✗ | ✗ | ✗ | NEEDS FIX (Sharpe drag too large) |
| **FFF3 robust** | **+0.0296** | **-0.0209** | **-0.01pp** | **+0.35pp** | -0.49pp | ✗ | ✗ | ✓ | **KEEP AS SHADOW (best Sharpe in family)** |
| FFF4 polish | +0.0259 | -0.0245 | -0.40pp | -0.05pp | -0.68pp | ✗ | ✗ | ✗ | NEEDS FIX (RC barely moved, RF regressed) |

FFF3 is the recommended secondary architecture-reference shadow on the Layer 2A frontier. EEE1 remains primary on the allocator-architecture frontier.
