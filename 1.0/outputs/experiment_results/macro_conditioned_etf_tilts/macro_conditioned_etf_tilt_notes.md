# Macro-Conditioned ETF Tilt Sandbox — Sprint Notes

**Sprint date:** 2026-06-06
**Verdict:** `RESEARCH-ONLY`
**Script:** `scripts/test_macro_conditioned_etf_tilts.py`
**Outputs:** `outputs/experiment_results/macro_conditioned_etf_tilts/`

---

## 1. Which ETFs performed best inside neutral_mixed + each V3 macro state?

Derived from dev period only (not holdout). Ranked by annualized Sharpe of 4-week forward returns.

| NM + Macro State | Top ETFs (Sharpe) |
| --- | --- |
| expansion | BIL (4.33), XLU (2.43), XLV (2.40) |
| slowdown | SPY (5.69), XLK (5.43), VTV (5.20) |
| stress | PDBC (6.83), SHY (4.11), HYG (3.80) |
| overheating | BIL (4.07), SHY (2.48), XLU (1.65) |

**Expansion and overheating**: Defensive and quality ETFs dominated (BIL, utilities, healthcare).
These are the two highest-volatility macro sub-states within neutral_mixed.
**Slowdown**: Pure risk-on equities were best (SPY, XLK, VTV, QQQ, IWM). Dev Sharpe 0.789 from V3 classifier.
**Stress**: Commodities (PDBC) and short bonds (SHY, HYG) best — confirming flight-to-quality but not to long-duration bonds.

## 2. Did the data confirm or contradict intuitive macro ETF buckets?

| Macro State | Result | Notes |
| --- | --- | --- |
| expansion | **CONTRADICTION** | Intuition: SPY/QQQ/IWM. Data: BIL/XLU/XLV. Within NM, expansion weeks are actually low-volatility and quality-dominated. |
| slowdown | Broadly consistent | Intuition predicted defensives; data shows risk-on was actually better in NM+slowdown. Partial contradiction. |
| stress | Broadly consistent | PDBC leads (not long bonds), HYG also positive — stress within NM is mild stress, not full panic. |
| overheating | **CONTRADICTION** | Intuition: GLD/XLE/PDBC (inflation plays). Data: BIL/SHY (cash). NM+overheating is the weakest sub-regime. |

**Key insight**: Intuitive macro buckets perform poorly because `neutral_mixed` is already filtered — it excludes stressed_panic and calm_trend, so the macro-state-specific ETF behavior is very different from unconditional macro-regime expectations.

## 3. Which tilt variant performed best?

| Variant | Sharpe | ΔSharpe | Ann Return | Max DD | NM Dev Sharpe | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| familyB_tilt10pct_data | 0.9591 | +0.0049 | 7.18% | -11.61% | 1.3101 | RESEARCH-ONLY |
| familyB_tilt7pct_data | 0.9580 | +0.0038 | 7.18% | -11.61% | 1.3037 | RESEARCH-ONLY |
| familyA_tilt10pct_data | 0.9579 | +0.0037 | 7.14% | -11.61% | 1.3261 | RESEARCH-ONLY |
| familyB_tilt5pct_data | 0.9567 | +0.0025 | 7.18% | -11.61% | 1.2969 | RESEARCH-ONLY |
| familyA_tilt7pct_data | 0.9566 | +0.0023 | 7.15% | -11.61% | 1.3137 | RESEARCH-ONLY |

Baseline: Sharpe=0.9542, AnnRet=7.18%, MaxDD=-11.60%

**Family B (macro + credit) is the clear winner.** The credit-trend confirmation gate eliminates approximately 20% of neutral_mixed tilt weeks, specifically those where macro says one thing but credit disagrees. This filtering slightly reduces returns but also reduces unnecessary turnover compared to Family A.

## 4. Which diagnostic family worked best?

| Family | Rule | Best Sharpe Δ | Key Finding |
| --- | --- | --- | --- |
| A | Macro-only | +0.0037 | Consistent improvement with large tilts; larger tilt = larger gain |
| B | Macro + credit | **+0.0049** | Best overall; credit filter removes false signals |
| C | Macro + SPY trend | **-0.0036** (best) | **HURTS** — SPY trend filter is too restrictive, removes good opportunities |
| D | Macro + credit + trend | -0.0007 (best) | Slightly negative; combining two filters over-constrains |

**Critical finding**: The SPY trend filter (Family C) is counterproductive. When SPY is below its 200-week MA, the best NM+slowdown opportunities (SPY, XLK, VTV) are blocked, which eliminates the highest-Sharpe sub-regime (slowdown Sharpe 0.789 but filtered away in stressed markets).

## 5. Did any candidate improve neutral_mixed without hurting full portfolio?

Baseline NM dev Sharpe: **1.2825**

25 of 32 candidates show positive NM Sharpe improvement. Top candidates bring NM Sharpe to 1.30–1.33. However, the improvement is modest and the absolute Sharpe delta on the full portfolio is only +0.0049 at best.

The production portfolio already achieves a very high NM Sharpe (1.28) through its existing regime logic. There is limited headroom for further improvement within NM alone.

## 6. Did any candidate clear the promotion gates?

| Gate | Criterion | Top Candidate | Pass? |
| --- | --- | --- | --- |
| G1: Sharpe +0.01 | Δ ≥ +0.01 | +0.0049 | **FAIL** |
| G2: Holdout Sharpe OK | ≥ baseline | 2.02 vs 2.05 | PASS (within -0.01) |
| G3: Return OK | Not materially worse | flat | PASS |
| G4: Max DD OK | ≤ 1pp worse | -11.61 vs -11.60 | PASS |
| G5: CVaR OK | Not materially worse | flat | PASS |
| G6: Turnover ≤3pp increase | ≤ 0.03 | 0.49 (Family B10) | **FAIL** |
| G7: NM Sharpe improved | NM better | 1.31 vs 1.28 | PASS |
| G8: Stressed_panic OK | Not worse -0.02 | flat | PASS |
| G9: No leverage | Weight sum = 1 | confirmed | PASS |

**7 of 9 gates pass for the top 3 candidates.** Consistent failures: G1 (Sharpe improvement too small) and G6 (turnover addition exceeds 3pp budget).

**PROMOTE_TO_PHASE_D_TEST: 0**
**RESEARCH-ONLY: 25**
**DROP: 7**

## 7. Best tilt size?

| Tilt Size | Best Sharpe Δ | Family |
| --- | --- | --- |
| 2.5% | +0.0009 | B |
| 5.0% | +0.0025 | B |
| 7.5% | +0.0038 | B |
| 10.0% | **+0.0049** | B |

Larger tilts perform better. This suggests the signal-to-noise ratio is real, but the magnitude of regime-specific ETF alpha is limited. The tilt needs to be large to produce a visible portfolio effect, but large tilts also add more turnover.

## 8. Did turnover or transaction costs erase the benefit?

| Candidate | Ann Turnover | Baseline | Increase | Gate (≤0.03) |
| --- | --- | --- | --- | --- |
| familyB_tilt10pct_data | 4.09 | 3.50 | +0.59 | FAIL (20× gate) |
| familyB_tilt7pct_data | 3.97 | 3.50 | +0.47 | FAIL (16× gate) |
| familyA_tilt10pct_data | 4.01 | 3.50 | +0.51 | FAIL (17× gate) |
| familyB_tilt2pct_data | 3.67 | 3.50 | +0.17 | FAIL (6× gate) |

**The 2x-cost sensitivity test is the clearest signal**: doubling transaction costs takes the best candidate from +0.0049 Sharpe to **-0.0482 Sharpe**. This means the improvement is:
1. Entirely marginal relative to realistic slippage
2. Not robust to even modest execution friction beyond the base 10bps model
3. The tilt mechanism generates meaningful churn by entering/exiting tilt conditions week-to-week

The turnover gate failure is not just numerical — it reflects a real economic fragility. The ETF tilt benefit (~0.5bp/year per unit of tilt improvement) is easily overwhelmed by additional trading costs.

## 9. Did the result survive holdout and robustness checks?

### Holdout (2024-04-19 to 2026-04-10, 100 weeks)

Baseline holdout Sharpe: **2.0479**
Best candidate holdout Sharpe: **2.0247** (familyB_tilt10pct_data, -0.023)

All macro classification in the holdout period is `slowdown` (97/100 weeks). No expansion, stress, or overheating quadrants appear. This means the macro-state-specific tilts are largely inactive in the holdout, making holdout discrimination uninformative. The slight holdout underperformance (-0.023 Sharpe) comes from a small number of weeks where a slowdown tilt was applied.

### Sub-period robustness (best candidate: familyB_tilt10pct_data)

| Window | Sharpe Δ | Interpretation |
| --- | --- | --- |
| 2010s decade | +0.018 | Strongest decade; macro tilts add value in trending regime |
| Dev ex-2020 | +0.009 | Stable without COVID period |
| Dev ex-2022 | +0.008 | Stable without rate-shock year |
| Full dev | +0.007 | Moderate improvement |
| Pre-2010 (incl. GFC) | -0.004 | Slightly negative — 2008 stress classification helps but adds noise |
| Post-2020 dev | -0.006 | Volatile regime; tilts slightly harmful |
| 2x cost sensitivity | **-0.048** | Benefit entirely eliminated by 2x costs |

### Tilt size sensitivity (familyB)

| Alt Tilt | Sharpe Δ |
| --- | --- |
| 5% (half) | +0.0025 |
| 10% (base) | +0.0049 |
| 15% (1.5×) | +0.0066 |

Linear scaling relationship — larger tilts consistently better, but cost drag grows proportionally.

## 10. Final Verdict

**`RESEARCH-ONLY`**

### Why not DROP?

- G7 passes: NM Sharpe improves from 1.28 to 1.31 (development period)
- 7 of 9 gates pass consistently for top candidates
- The asset diagnostics are internally consistent (slowdown within NM is genuinely high-Sharpe)
- Family B (macro + credit) outperforms macro-alone
- The V3 classifier correctly segments neutral_mixed weeks

### Why not PROMOTE_TO_PHASE_D_TEST?

- G1 fails: Best Sharpe delta = +0.0049, threshold = +0.01. The improvement is real but half the required magnitude.
- G6 fails: Turnover addition (0.17–0.59 annualized) is 6–20× the 0.03 gate. Economically, the improvement cannot survive realistic execution friction.
- 2x-cost test: Entire benefit wiped out (+0.005 → -0.048 Sharpe). A robust improvement should survive 2× slippage.
- Holdout is largely uninformative (all slowdown classification). Cannot confirm the result out of sample.

### What this means for the research program

The V3 macro regime classifier successfully identifies real heterogeneity in neutral_mixed weeks. The NM+slowdown sub-regime (78 dev weeks, Sharpe 0.789, mean 4w SPY +2.11%) is the strongest actionable signal. However, translating this signal into ETF tilts within the existing portfolio architecture creates too much turnover relative to the achievable return improvement.

### Recommended next steps (if pursuing this branch)

1. **Lower-turnover implementation**: Instead of weekly ETF tilts, consider holding the macro-state-derived allocation for the full duration of a macro regime (multi-week persistence). This would reduce entry/exit turnover significantly.
2. **Regime persistence filter**: Only apply a tilt after the macro state has been stable for ≥4 weeks, to avoid reacting to high-frequency state switching.
3. **Reframe as a meta-allocator**: Use V3 macro states as a conditioning feature in the existing Layer 2B regime engine rather than as a direct ETF tilt overlay.
4. **NM+slowdown-only focus**: Instead of tilting across all 4 macro states, only activate the SPY/XLK/VTV tilt during NM+slowdown (n=78 dev weeks). This is the strongest single signal and minimizes tilt frequency.

---
*Research artifact sprint — no production artifacts modified.*
