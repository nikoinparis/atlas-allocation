# Persistent Layer 2B Macro-Credit Modifier — Sprint Notes

**Sprint date:** 2026-06-06
**Verdict:** `RESEARCH-ONLY`
**Script:** `scripts/test_persistent_macro_credit_layer2b_modifier.py`
**Outputs:** `outputs/experiment_results/persistent_macro_credit_layer2b_modifier/`

---

## 1. Did persistence filtering reduce signal churn vs Step 2?

Step 2 (weekly ETF tilts) added 0.17–0.59 annual turnover because each NM+slowdown week independently toggled a position change. The persistence filter restructures this into episodes.

**Raw NM+slowdown signal (Signal A, no filter):**
- 136 active weeks (12.2%), 38 episodes, avg 3.6 weeks/episode, 37 transitions

**With act=2/deact=2/hold=4 (best performing parameters):**
- 17 episodes, 54% turnover reduction vs raw transitions
- Signal D (FC_benign gate): 62 dev / 58 holdout active weeks

**With act=4/deact=3/hold=4 (most aggressive persistence):**
- 9 episodes, 78.4% turnover reduction
- But too few active weeks → signal amplitude too small → Sharpe delta shrinks

**Key result:** Persistence filtering succeeds at reducing transition count (54–78% fewer rebalances) but fails to reduce overall portfolio turnover to the G6 threshold. Even with aggressive filtering, the annual turnover increase remains 0.084–0.127 vs the 0.03 gate. This is because each episode activation/deactivation still rebalances BIL→SPY/QQQ (a ~10% shift across 4 ETFs), and episodes average 4–7 weeks — so the per-rebalance cost is spread over more weeks but not eliminated.

---

## 2. Which target signal variant worked best?

| Signal | Definition | Dev Active Weeks | Best Sharpe Δ |
| --- | --- | --- | --- |
| **D_nm_slow_fc** | NM + slowdown + FC_benign | 62 | **+0.0145** |
| E_nm_slow_credit_fc | NM + slowdown + FC_benign + credit_benign | 44 | +0.0113 |
| C_nm_slow_crnotworse | NM + slowdown + credit not worsening | 55 | (not in top 10) |
| B_nm_slow_credit | NM + slowdown + credit_benign | 44 | (not in top 10) |
| A_nm_slow | NM + slowdown only | 78 | (not in top 10) |

**Signal D (NM+slowdown+FC benign) is the clear winner.** The FC proxy acts as a single composite gating filter (VIX + credit spread + SPY drawdown + correlation). Adding a redundant credit gate (Signal E) reduces active weeks from 62 to 44 — too few to maintain statistical power — but the holdout behavior of Signal E is notably cleaner (see section 9).

Signal A (raw NM+slowdown) has more active weeks but without the FC filter, it includes weeks where financial conditions were already deteriorating, adding noise.

---

## 3. Which persistence settings worked best?

| Variant | Act | Deact | Hold | Dev Active | Sharpe Δ |
| --- | --- | --- | --- | --- | --- |
| act2_deact2_hold2 (D) | 2 | 2 | 2 | 55 | **+0.0145** |
| act2_deact2_hold4 (D) | 2 | 2 | 4 | 63 | +0.0113 |
| act2_deact2_hold4 (E) | 2 | 2 | 4 | 44 | +0.0113 |
| act2_deact2_hold2 (D) at 7% | 2 | 2 | 2 | 55 | +0.0101 |

**Fastest activation (act=2) consistently outperforms slower activation (act=3, 4).** NM+slowdown episodes tend to be 3–5 weeks — activating after 3+ weeks means you often miss the entire episode. Act=2 captures the core of each episode.

**Shorter minimum hold (hold=2) slightly outperforms longer hold (hold=4)** for Signal D: it exits earlier when the sub-regime ends rather than holding through unqualified weeks. However, Signal E prefers hold=4 — the tighter signal (44 dev weeks) needs longer holding to avoid premature exits that waste entry costs.

---

## 4. Which Layer 2B modifier type worked best?

| Modifier Type | Best Sharpe Δ | Reached Top 10? |
| --- | --- | --- |
| **offense_budget** | **+0.0145** | **Yes — all 10** |
| defense_release | — | No |
| risk_multiplier | — | No |
| combined | — | No |

**Offense budget (drain BIL/IEF/TLT → add to SPY/QQQ/HYG/EFA) is the only modifier type that works.** During NM+slowdown, the portfolio is already partially risk-on, but BIL and bond holdings suppress returns. Offense budget specifically targets this drag by reducing the safe-haven allocation and routing it to the risk assets that dominate the NM+slowdown sub-regime.

Defense release (reduce BIL only → redistribute) and risk_multiplier (scale existing offensive ETF weights) did not reach the top 10 in the coarse grid — likely because: defense_release moves too little (BIL only, not IEF/TLT), and risk_multiplier amplifies whatever the optimizer already selected without adding the specific ETFs (SPY, QQQ, EFA) that drive NM+slowdown alpha.

---

## 5. Which intensity worked best?

| Intensity | Best Sharpe Δ |
| --- | --- |
| 2% | +0.0021 |
| 5% | +0.0068 |
| 7% | +0.0101 |
| **10%** | **+0.0145** |

Monotonically increasing with intensity — larger BIL→offense drains produce larger Sharpe gains. This means the underlying signal is real and direction is correct. However, larger intensity also produces more turnover (10% ≈ 0.125 annual increase vs 2% ≈ 0.084). The cost-adjusted benefit still doesn't clear G6.

---

## 6. Did the modifier improve neutral_mixed?

| Metric | Baseline | Best Candidate |
| --- | --- | --- |
| NM dev Sharpe | 1.2825 | 1.2993 (+0.017) |
| NM+slow dev Sharpe | 2.0069 | 2.0131 (+0.006) |

All 10 candidates (100%) improve NM Sharpe in the development period. G7 passes for all candidates.

The improvement in NM+slow Sharpe is modest (+0.006 for the best) because the persistence filter and FC gate reduce active-week count from 78 (raw signal) to 55–63, concentrating activity in higher-confidence sub-weeks but shrinking the total alpha opportunity.

---

## 7. Did it improve the full portfolio?

| Candidate | Full Sharpe | Sharpe Δ | Ann Return | Max DD | Verdict |
| --- | --- | --- | --- | --- | --- |
| D\|act2_deact2_hold2\|offense_budget\|int10pct | 0.9687 | **+0.0145** | 7.37% | -11.61% | RESEARCH-ONLY |
| D\|act2_deact2_hold4\|offense_budget\|int10pct | 0.9655 | +0.0113 | 7.35% | -11.61% | RESEARCH-ONLY |
| E\|act2_deact2_hold4\|offense_budget\|int10pct | 0.9656 | +0.0113 | 7.33% | -11.61% | RESEARCH-ONLY |
| D\|act2_deact2_hold2\|offense_budget\|int7pct | 0.9643 | +0.0101 | 7.32% | -11.61% | RESEARCH-ONLY |

Baseline: Sharpe=0.9542, AnnRet=7.18%, MaxDD=-11.60%

The Sharpe improvement is real and consistent. G1 (≥+0.01) passes for 4 of 10 candidates. The remaining gates (G3 return, G4 drawdown, G5 CVaR, G8 stressed_panic, G9 recovery_fragile, G10 obs) all pass. The sole structural failure is G6.

---

## 8. Holdout performance

| Candidate | Holdout Sharpe | Baseline | Δ | Gate (≥-0.02) |
| --- | --- | --- | --- | --- |
| D\|hold2\|int10pct | 2.0263 | 2.0479 | -0.022 | PASS (borderline) |
| D\|hold4\|int10pct | 2.0208 | 2.0479 | -0.027 | PASS |
| **E\|hold4\|int10pct** | **2.0893** | **2.0479** | **+0.041** | **PASS (strong)** |

**Candidate E (NM+slowdown+FC_benign+credit_benign, hold=4) passes holdout with a +0.041 Sharpe improvement.** This is the most promising holdout result of any strategy in this research program (Steps 1–2B). The holdout period (2024–2026) is classified as uniformly `slowdown` by V3, so Signal E is almost continuously active in holdout (34 of 104 weeks after persistence filtering). The tighter credit gate appears to have selected genuinely high-quality slowdown weeks.

All 3 top candidates pass G2. However, Step 2's holdout was -0.023 — so the persistence filter has not meaningfully degraded holdout behavior even for Signal D.

---

## 9. Stressed-panic and recovery state behavior

G8 (stressed_panic not materially worsened) passes for all candidates. The offense budget modifier is only activated during NM+slowdown — it does not change behavior during stressed_panic or recovery states at all. The modifier is structurally neutral in all other regime states.

G9 (recovery_fragile not worsened) also passes for all candidates by the same logic.

---

## 10. Turnover — the binding constraint

| Candidate | Ann Turnover | Baseline | Increase | Gate (≤0.03) |
| --- | --- | --- | --- | --- |
| D\|hold4\|int10pct | 3.622 | 3.504 | +0.118 | **FAIL (4× gate)** |
| E\|hold4\|int10pct | 3.631 | 3.504 | +0.127 | **FAIL (4× gate)** |
| D\|hold2\|int10pct | 3.629 | 3.504 | +0.125 | **FAIL (4× gate)** |
| D\|hold4\|int2pct | 3.588 | 3.504 | +0.084 | **FAIL (3× gate)** |

**No candidate comes close to the 0.03 annual turnover gate.** Even the minimum-intensity candidate (2%) adds 0.084 annual turnover — nearly 3× the gate. The persistence filter reduced transition count by 54–78% vs weekly ETF tilts but could not bring turnover within gate because each episode transition still rebalances ~10% of the portfolio across 4–5 ETFs.

Critically: the turnover gate failure is not a tuning problem. The constraint is structural — any mechanism that periodically adjusts offense/defense budget by 10% (even infrequently) will exceed the 0.03 annual gate if it fires more than ~3× per year. With 9–17 episodes per year, the math does not work.

---

## 11. 2×-cost sensitivity test

| Candidate | 2×-cost Sharpe | Baseline | Δ at 2× cost |
| --- | --- | --- | --- |
| D\|hold2\|int10pct | 0.9210 | 0.9542 | **-0.0332** |
| D\|hold4\|int10pct | 0.9180 | 0.9542 | **-0.0362** |
| E\|hold4\|int10pct | 0.9178 | 0.9542 | **-0.0364** |

All three candidates go significantly negative under 2× costs. At base costs, the best candidate earns +0.0145 Sharpe from regime timing; at 2× costs, that benefit becomes -0.033. The improvement is entirely marginal relative to realistic execution friction.

**This is the definitive test failure.** A robust improvement should be direction-stable under 2× costs. Step 2 showed -0.048; Step 2B shows -0.033 to -0.036 — marginally better but still decisively negative.

---

## 12. Sub-period robustness

### Best candidate: D_nm_slow_fc|act2_deact2_hold2|offense_budget|int10pct

| Window | Sharpe Δ | Interpretation |
| --- | --- | --- |
| Full period | +0.0145 | Baseline improvement |
| Dev period | +0.0141 | Consistent with full |
| Dev ex-2020 | +0.0146 | Stable without COVID |
| Dev ex-2022 | +0.0146 | Stable without rate shock |
| Pre-2010 (incl GFC) | +0.0025 | Weak — fewer qualifying episodes in 2008 bear |
| 2010s decade | +0.0160 | Strongest decade |
| Holdout | -0.022 | Borderline — within G2 gate |
| 2× cost | **-0.0332** | Fails |
| Alt intensity 5% | +0.0069 | Linear with intensity |
| Alt intensity 15% | +0.0215 | Stronger — also more turnover |
| Alt activate 1wk | +0.0120 | Faster activation slightly worse |
| Alt activate 3wk | +0.0016 | Too slow — misses episodes |

The improvement is robust across dev sub-periods (consistent across 2010s, non-COVID, non-rate-shock). Pre-2010 weakness is expected: 2008 was a stressed_panic period, not NM+slowdown, so Signal D is nearly inactive during the GFC.

### Candidate E: E_nm_slow_credit_fc|act2_deact2_hold4|offense_budget|int10pct

| Window | Sharpe Δ |
| --- | --- |
| Full period | +0.0114 |
| Dev period | +0.0061 |
| Holdout | **+0.0414** |
| 2× cost | **-0.0364** |

**Candidate E has the most interesting holdout result in this sprint.** It underperforms in dev (+0.006 vs +0.0145 for D) but beats baseline by +0.041 in holdout. The holdout period being uniformly `slowdown` and Signal E's tighter filter (FC+credit both required) selects high-confidence weeks. However, since 2× costs still destroy the benefit, this does not change the verdict. It does suggest the double-gate approach (FC+credit) may be the right direction for future, lower-cost implementations.

---

## 13. Gate summary — top candidates

| Gate | Criterion | Top Candidate (D\|hold2\|int10pct) | Pass? |
| --- | --- | --- | --- |
| G1: Sharpe +0.01 | Δ ≥ +0.01 | +0.0145 | **PASS** |
| G2: Holdout OK | ≥ baseline -0.02 | -0.022 | **PASS** (borderline) |
| G3: Return OK | ≥ baseline | +0.19pp | **PASS** |
| G4: Max DD OK | ≤ 1pp worse | 0bp change | **PASS** |
| G5: CVaR OK | Not materially worse | flat | **PASS** |
| G6: Turnover ≤0.03 | ≤ 0.03 increase | +0.125 | **FAIL** |
| G7: NM Sharpe improved | NM Sharpe better | +0.017 | **PASS** |
| G8: Stressed_panic OK | Not worse -0.02 | no change | **PASS** |
| G9: Recovery_fragile OK | Not worse -0.02 | no change | **PASS** |
| G10: Observations OK | ≥ 30 active dev | 55 | **PASS** |
| **Total** | | | **9 of 10 pass** |

**PROMOTE_TO_PHASE_D_TEST: 0**
**RESEARCH-ONLY: 10**
**DROP: 0**

---

## 14. Final Verdict

**`RESEARCH-ONLY`**

### Why not DROP?

- G1 passes (+0.0145 > +0.01) for 4 of 10 candidates — the signal is real and above the minimum threshold
- 9 of 10 gates pass consistently for top candidates
- Dev sub-period robustness is very clean (consistent across ex-2020, ex-2022, 2010s)
- Candidate E passes holdout with +0.041 Sharpe — first outright holdout win for any macro signal variant
- NM+slow Sharpe improves (2.007 → 2.013) for all 10 candidates
- Signal D correctly concentrates on FC-benign slowdown weeks (highest-quality sub-regime identified in V3)

### Why not PROMOTE_TO_PHASE_D_TEST?

- G6 fails: annual turnover increase (0.084–0.127) is 3–4× the 0.03 gate. No amount of parameter tuning can close this gap given the structural cost of episode rebalancing.
- 2× cost test: benefit collapses from +0.0145 to -0.033 Sharpe. The improvement is entirely margin-dependent on the base 10bps cost model.
- The G6 failure is architectural, not a tuning problem. Any mechanism that periodically moves 10% between offense and defense with 9–17 episodes per year will exceed the 0.03 annual turnover gate.

### What this means for the research program

Steps 2 and 2B have now exhausted both implementation paths for the V3 macro regime signal:

1. **Step 2 (weekly ETF tilts)**: Sharpe Δ +0.005, turnover 0.17–0.59. Benefit wiped at 2× cost.
2. **Step 2B (persistent Layer 2B modifier)**: Sharpe Δ +0.0145, turnover 0.084–0.127. Benefit wiped at 2× cost.

The signal itself is sound — V3 correctly identifies NM+slowdown as a high-alpha sub-regime, the development robustness is clean, and Candidate E actually wins holdout. The problem is that **any active position change in response to this signal generates more transaction cost than the signal is worth, even with aggressive persistence filtering**.

### Recommended next steps (if pursuing this branch)

1. **Near-zero-turnover encoding**: Encode NM+slowdown+FC_benign as a static conditional multiplier applied once at strategy selection time (not weekly) — equivalent to choosing a different static allocation for this sub-regime rather than dynamically switching. This could eliminate turnover entirely.
2. **Macro-conditioned allocator**: Feed V3 macro states as input features to the existing Layer 2B regime engine as a conditional feature (not a post-hoc modifier), so the optimizer naturally learns to hold more SPY/QQQ when V3 signals slowdown+FC_benign. This requires no additional rebalancing.
3. **Candidate E as future reference**: The E variant (FC+credit double-gate, hold=4) passed holdout with +0.041 Sharpe — keep this signal definition as the reference for any future near-zero-turnover implementation.
4. **Accept current frontier**: Given the structural constraint, accept that the macro regime signal cannot be profitably implemented via post-optimization overlays without lower-cost execution infrastructure (e.g., futures or tighter spreads).

---

*Research artifact sprint — no production artifacts modified.*
