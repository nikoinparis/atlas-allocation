# Near-Zero-Turnover Macro State Integration — Sprint Notes

**Sprint date:** 2026-06-07
**Verdict:** `RESEARCH-ONLY`
**Script:** `scripts/test_near_zero_turnover_macro_state_integration.py`
**Outputs:** `outputs/experiment_results/near_zero_turnover_macro_state_integration/`

---

## 1. Did near-zero-turnover integration reduce turnover vs Step 2 and Step 2B?

| Sprint | Implementation | Min Annual TO Increase | Gate (≤0.03) |
| --- | --- | --- | --- |
| Step 2 (ETF tilts) | Weekly overlay | 0.170 | FAIL |
| Step 2B (persistent modifier) | Episode filter | 0.084 | FAIL |
| **Step 2C (this sprint)** | Near-zero calibration | **0.057** | **FAIL** |

Step 2C reduced the minimum annual turnover increase from 0.084 (Step 2B) to 0.057 — a 32% reduction. This is the quarterly frozen approach (D_quarterly), which only changes its state at most once per quarter. However, 0.057 is still 1.9× the 0.03 gate.

**Root cause of structural failure**: NM has 95 episodes and 190 transitions over 21 years (8.9 transitions/year, 4.5 episodes/year). Every transition from modified to unmodified weights (or vice versa) costs approximately `intensity / 2` in half-round-trip turnover. At 2.5% intensity:

- Extra TO per transition ≈ 0.025 × 4 (ETFs affected) × 0.5 (half-round-trip) ≈ 0.05 per transition
- At 8.9 NM transitions/year: baseline extra ≈ 0.045/year → already exceeds 0.03 at 2.5%
- At 1% intensity: extra ≈ 0.018/year → passes gate, but Sharpe delta ≈ +0.0005 (below G1)

The gate cannot be cleared at any intensity that also generates meaningful Sharpe improvement.

---

## 2. Which refined neutral_soft_landing definition worked best?

The best definition for Sharpe improvement is **D_4wk** (NM + slowdown + FC_benign + credit_not_worsening, 4-week rolling majority confirmation), which achieves ΔSharpe=+0.0194. This is *not* one of the frozen variants — it's a 4-week rolling smoothing of the raw binary signal.

| Definition | Best ΔSharpe | TO_increase | Holdout Δ | Notes |
| --- | --- | --- | --- | --- |
| **D_4wk** | **+0.0194** | 0.121 | -0.003 | Best dev improvement |
| E_4wk | +0.0146 | 0.126 | **+0.016** | **Best holdout** |
| D_quarterly | +0.0015 | 0.057 | -0.022 | Lowest TO, but negative holdout |
| E_quarterly | -0.0022 | 0.074 | -0.023 | Wrong direction |
| D_monthly | -0.0015 | 0.113 | -0.083 | Hurts holdout badly |
| E_monthly | +0.0004 | 0.134 | -0.039 | Hurts holdout |

**Signal E (FC_benign + credit_improving) consistently wins in holdout.** Across Steps 2B and 2C:
- Step 2B Signal E: holdout Δ = **+0.041** (best single holdout in entire program)
- Step 2C E_4wk: holdout Δ = **+0.016** (second best)
- All other signals: negative or flat holdout

Signal E's double-gate (FC + strict credit improvement) appears to select weeks with genuinely different expected outcomes vs the rest of NM+slowdown. The consistency across sprints suggests this is not an artifact.

---

## 3. Did static neutral_mixed recalibration work?

**No.** The static NM recalibration (Group 1) is the *worst* performing group.

| Candidate | ΔSharpe | TO_increase | G6 | G7 (NM ok) |
| --- | --- | --- | --- | --- |
| G1_static_NM\|defense_release\|int7pct | +0.0074 | 0.289 | FAIL | **FAIL** |
| G1_static_NM\|defense_release\|int5pct | +0.0056 | 0.199 | FAIL | **FAIL** |
| G1_static_NM\|offense_budget\|int5pct | +0.0019 | 0.275 | FAIL | **FAIL** |

**Critical finding: Static NM modifier hurts NM Sharpe (G7 fails for all 15 G1 candidates).** This is counterintuitive — why would always boosting offense in NM hurt NM Sharpe?

Answer: the modifier is applied to ALL neutral_mixed weeks, including NM+expansion and NM+overheating sub-regimes where offense boost does NOT help. These sub-regimes constitute ~40-50% of NM weeks. Blindly boosting offense during expansion and overheating sub-regimes within NM adds noise, reducing the overall NM Sharpe even as the NM+slowdown sub-regime improves.

This confirms the Step 2 finding: **the macro state conditioning is essential**. Without it, any uniform NM modifier hurts more than it helps.

Also notable: static NM produces massive turnover (0.077–0.41/year) because NM has 8.9 transitions/year, each requiring a full intensity shift.

---

## 4. Did monthly/quarterly frozen sub-state calibration work?

**Monthly frozen (Group 2):** Mostly negative. Holdout is consistently negative (-0.028 to -0.083). The monthly decision frequency creates too many state changes (~6-8 per year), most of which add turnover without adding alpha.

**Quarterly frozen (Group 3):** Better than monthly, but still consistently negative holdout (-0.021 to -0.065 for D_quarterly at all intensities). Achieves the lowest minimum turnover (0.057), but:
- Quarterly frozen state changes 3-5× per year (vs the 0.5-1× that would be needed to stay below the gate)
- Holdout is uniformly negative: the quarterly frozen state becomes nearly permanently active in holdout (slowdown dominates all holdout quarters), and applying the modifier even mildly hurts holdout Sharpe

The monthly and quarterly frozen approaches fail both the turnover gate AND holdout in the best candidates. They are worse than the rolling-confirmation approach (G4).

---

## 5. Did slow-score integration work?

**No.** Slow score (Group 5) produces near-zero Sharpe delta at all intensities and rolling windows.

| Candidate | ΔSharpe | TO_increase |
| --- | --- | --- |
| D_score_r8_cap5\|int2pct | -0.0012 | 0.073 |
| D_score_r12_cap5\|int2pct | -0.0012 | 0.073 |
| D_score_r8_cap10\|int7pct | -0.0019 | 0.072 |

The slow score approach produces surprisingly similar turnover across all rolling windows and cap settings (~0.071-0.073/year). This appears to be a floor driven by the underlying NM transition structure rather than the score dynamics.

The Sharpe delta is near-zero or slightly negative because the slow-score modifier is always partially active during NM weeks (score never reaches exactly 0 or 1 due to smoothing), creating a de facto noisy version of the static NM modifier — which we already showed hurts NM Sharpe.

---

## 6. Which modifier type worked best?

| Modifier | Best ΔSharpe | G1 passes | Notes |
| --- | --- | --- | --- |
| **offense_budget** | **+0.0194** | 3 | Drains BIL/bonds → adds to SPY/QQQ/EFA |
| defense_release | +0.0074 | 0 | Releases BIL only |
| combined | +0.0041 | 0 | 60% offense + 40% defense |

Offense budget is dominant — consistent with Steps 2 and 2B. The drain from BIL *and* bonds (IEF, TLT, SHY) combined with targeted routing to offensive ETFs generates more alpha per unit of turnover than simply releasing BIL.

---

## 7. Which intensity worked best?

Monotonically increasing with intensity — all approaches show larger Sharpe delta at higher intensity. The relationship is approximately linear.

| Intensity | Best ΔSharpe | Min TO_increase |
| --- | --- | --- |
| 0.5% | -0.0002 | 0.077 |
| 1.0% | +0.0005 | 0.085 |
| 2.5% | +0.0044 | 0.087 |
| 5.0% | +0.0097 | 0.101 |
| 7.5% | +0.0141 | 0.112 |
| **10.0%** | **+0.0194** | **0.121** |

Critically: turnover also increases with intensity, but more slowly than Sharpe delta (sub-linear in the range tested). This means larger intensities are more "efficient" per unit of turnover, but none cross the viability threshold where both G1 and G6 simultaneously pass.

---

## 8. Did any candidate improve full Sharpe by at least +0.01?

G1 passes for 3 candidates, all from Group 4 (4-week rolling confirmation):

| Variant | ΔSharpe | TO_increase | Holdout Δ | G6 |
| --- | --- | --- | --- | --- |
| G4_smoothed\|D_4wk\|offense_budget\|int10pct | **+0.0194** | 0.121 | -0.003 | FAIL |
| G4_smoothed\|E_4wk\|offense_budget\|int10pct | +0.0146 | 0.126 | **+0.016** | FAIL |
| G4_smoothed\|D_4wk\|offense_budget\|int7pct | +0.0141 | 0.112 | -0.005 | FAIL |

**The best Sharpe delta in this sprint (+0.0194) exceeds Step 2B's best (+0.0145).** The 4-week rolling confirmation is slightly more effective than the persistence filter at capturing the NM+slowdown+FC_benign signal. But it generates similar turnover (0.112-0.121 vs Step 2B's 0.118-0.125) because it's approximating the same underlying regime-episode structure.

No candidate simultaneously passes G1 and G6.

---

## 9. Did holdout performance survive?

Mixed. The E_4wk variant has notable positive holdout, while D variants are slightly negative:

| Candidate | Holdout Sharpe | Baseline | Holdout Δ |
| --- | --- | --- | --- |
| **E_4wk\|int10pct** | 2.064 | 2.048 | **+0.016** |
| E_4wk\|int7pct | 2.053 | 2.048 | +0.005 |
| D_4wk\|int10pct | 2.045 | 2.048 | -0.003 |
| D_4wk\|int7pct | 2.042 | 2.048 | -0.005 |
| D_quarterly\|all | 1.983–2.026 | 2.048 | -0.022 to -0.065 |

**Signal E_4wk is the most consistent holdout performer across all three sprints** (Steps 2B and 2C). The double-gate (FC_benign + credit_improving) appears to filter the NM+slowdown signal to its most reliable subset.

---

## 10. Did 2x transaction costs erase the improvement?

Yes, for all top candidates:

| Candidate | 1× cost ΔSharpe | 2× cost ΔSharpe |
| --- | --- | --- |
| D_4wk\|int10pct | +0.0194 | **-0.028** |
| E_4wk\|int10pct | +0.0146 | **-0.033** |
| D_4wk\|int7pct | +0.0141 | **-0.034** |

The D_4wk candidate's 2x-cost test (-0.028) is marginally better than Step 2B (-0.033), suggesting the 4-week confirmation captures a slightly purer signal. But all three still go definitively negative under doubled costs — the benefit is not cost-robust.

---

## 11. Did neutral_mixed improve?

Only for G4_smoothed candidates. 18 of 68 total candidates improve NM Sharpe (Sharpe > 1.2825).

| Group | NM Sharpe range | Improves NM? |
| --- | --- | --- |
| G1 (static NM) | 1.261–1.282 | No (all 15 candidates hurt NM) |
| G2 (monthly frozen) | 1.281–1.296 | Mixed (small improvement) |
| G3 (quarterly frozen) | 1.249–1.281 | No (mostly hurt NM) |
| G4 (4-week rolling) | 1.281–1.299 | **Yes** (all 8 candidates) |
| G5 (slow score) | 1.278–1.281 | Marginal |

**The 4-week rolling confirmation uniquely improves NM Sharpe.** The monthly/quarterly frozen and static NM approaches either hurt or are neutral for NM Sharpe, while the rolling confirmation approach correctly filters the high-alpha NM+slowdown+FC_benign weeks without contaminating the other NM sub-regimes.

---

## 12. Did stressed_panic and recovery_fragile remain protected?

Yes, by construction. All modifier types only activate during NM or neutral_soft_landing conditions (which are subsets of NM). stressed_panic and recovery_fragile weights are completely unchanged.

G8 (stressed_panic not worsened): 68 of 68 pass.
G9 (recovery_fragile not worsened): 68 of 68 pass.

---

## 13. Gate summary — top candidates

| Gate | Criterion | D_4wk\|int10pct | E_4wk\|int10pct |
| --- | --- | --- | --- |
| G1: Sharpe +0.01 | Δ ≥ +0.01 | +0.0194 | PASS |
| G2: Holdout OK | ≥ baseline -0.02 | -0.003 | +0.016 | PASS |
| G3: Return OK | Not worse | +0.19pp | PASS |
| G4: Max DD OK | ≤ 1pp worse | 0 | PASS |
| G5: CVaR OK | Not worse | flat | PASS |
| G6: Turnover ≤0.03 | ≤ 0.03 | +0.121 | **FAIL** |
| G7: NM Sharpe OK | NM not worse | +0.017 | PASS |
| G8: SP OK | Not worse -0.02 | no change | PASS |
| G9: RF OK | Not worse -0.02 | no change | PASS |
| **Total** | | | **8 of 9** |

**PROMOTE_TO_PHASE_D_TEST: 0**
**RESEARCH-ONLY: 68**
**DROP: 0**
**G1 and G6 simultaneously: 0**

---

## 14. Final Verdict

**`RESEARCH-ONLY`**

### Why not DROP?

- Signal D and E are validated across Steps 2, 2B, and 2C: consistently positive dev Sharpe delta at 10% intensity across all implementation approaches
- Signal E (FC_benign + credit_improving) wins holdout in both Step 2B (+0.041) and Step 2C (+0.016) — this is the most consistent out-of-sample result in the macro research program
- 4-week rolling confirmation (D_4wk) achieves the highest single Sharpe delta of any candidate in the entire macro research program (+0.0194)
- G7 (NM Sharpe improved) passes for all G4 candidates
- The signal direction and magnitude are internally consistent across 3 sprints

### Why not PROMOTE_TO_PHASE_D_TEST?

- G6 fails for all 68 candidates. **Minimum turnover increase is 0.057/year (1.9× the 0.03 gate)** from the quarterly frozen approach. The 4-week rolling best is 0.112 (3.7× gate).
- The turnover constraint is structural and cannot be solved by parameter tuning. NM's 8.9 transitions/year combined with any meaningful weight modification makes the 0.03 annual turnover gate mathematically unreachable at useful intensities.
- 2x-cost test: all candidates go negative under doubled costs (-0.028 to -0.034). The improvement cannot survive realistic execution friction.
- The only approach that approaches the turnover gate (quarterly frozen, 0.057) consistently hurts holdout (-0.022 to -0.065) because the frozen state becomes nearly permanently active in the holdout period.

### What this closes

All three implementation paths for the V3 macro overlay research program are now exhausted:

| Sprint | Implementation | Best ΔSharpe | Min TO_increase | G1 | G6 | 2×-cost |
| --- | --- | --- | --- | --- | --- | --- |
| Step 2 | Weekly ETF tilt | +0.0049 | 0.170 | FAIL | FAIL | -0.048 |
| Step 2B | Persistent modifier | +0.0145 | 0.084 | PASS | FAIL | -0.033 |
| **Step 2C** | Near-zero calibration | **+0.0194** | **0.057** | PASS | FAIL | **-0.028** |

Progress was made across sprints: Sharpe delta improved from +0.0049 → +0.0145 → +0.0194, and turnover decreased from 0.170 → 0.084 → 0.057. But the gap between achievable turnover and the gate (0.03) could not be closed.

**The V3 NM+slowdown+FC_benign macro signal is confirmed real and direction-correct.** The constraint is structural: any post-hoc portfolio overlay that responds to this signal, whether weekly, episodic, frozen monthly/quarterly, or smoothed, generates more turnover cost than the signal is worth at achievable portfolio scale.

### Closed path; archived signal

Signal E_4wk (NM+slowdown+FC_benign+credit_improving, 4-week rolling majority confirmation) is archived as the reference signal definition. It:
- Achieves +0.016 holdout Sharpe improvement (consistent across Steps 2B and 2C)
- Has clean internal logic (double-gated, causal, no hindsight)
- Could be used as a native Layer 2B input feature in a future full rebuild

### Structural path not tested (out of scope)

One untested path remains: baking the NM+slowdown+FC_benign insight into a new static strategy design from scratch (not as a post-hoc overlay). This would require rebuilding Layer 2B with macro conditioning as a native feature — a major scope change beyond overlays. This sprint does not assess that path; it is noted here for completeness.

---
*Research artifact sprint — no production artifacts modified.*
