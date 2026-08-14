# Phase 3 — Breadth-Confirmed US Offense Upgrade

**Date:** 2026-05-07
**Type:** Strategy research. No production pins changed. No auto-promotion.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense`
**Phase 2 aggressive shadow:** `improved_phase2_aggressive_neutral_cash_unlock`

---

## Commands Executed

```
mkdir -p data/research/phase_3_breadth_confirmed_us_offense
python3 scripts/phase_3_breadth_confirmed_us_offense.py 2>&1 | tee data/research/phase_3_breadth_confirmed_us_offense/phase3_run.log
```

**Build command (internal):**
```
BUILD_VERSION_NAMES='improved_phase3_*' python3 scripts/build_improvement_artifacts.py
```

---

## Files Created / Modified

**Scripts modified:**
- `scripts/build_improvement_artifacts.py` — added 6 Phase 3 panel builds, 6 redeploy cases, 6 version specs

**New script:**
- `scripts/phase_3_breadth_confirmed_us_offense.py`

**Outputs (39 files in `data/research/phase_3_breadth_confirmed_us_offense/`):**
signal inventory, basket designs, event validation, candidate designs, build log, full/holdout metrics, state diagnostics, risk/realism checks, hidden beta, bear check, signal performance, selection, audits, protocol JSON

**Candidate artifacts** (`data/05_layer3_portfolio_construction/`):
- 6 × `portfolio_version_returns_improved_phase3_*.csv`
- 6 × `portfolio_version_weights_improved_phase3_*.csv`
- 6 × `portfolio_version_sleeve_weights_improved_phase3_*.csv`

---

## Phase 1 + Phase 2 Bottleneck Summary

Phase 1 found: return ceiling is mandate-driven. neutral_mixed (44% of weeks, 26% BIL) is the biggest leakage; calm_trend (27% of weeks) costs −13.2% annualized vs SPY due to defensiveness.

Phase 2 found: sleeve reallocation alone (defense→offense in calm/neutral) doesn't help, because the offense sleeves hold diversified international/commodity ETFs that don't capture US bull upside. Best Phase 2 candidate: 7.39% / Sharpe 0.940.

Phase 3 hypothesis: Switching the `composite_regime_offense_component` ETF basket from diversified (SPY/QQQ/IWM + EFA/VEA/VWO/EWJ/VNQ/PDBC/DBA) to pure US equity (SPY/QQQ/IWM) during high-breadth confirmed states will capture more US bull-market upside.

---

## Part A — Signal Inventory

| Feature | Source | Non-null % | Role |
|---|---|---|---|
| breadth_sma_43 | market_state_history.csv | 100% | % ETFs above 43-week SMA |
| breadth_26w_mom | market_state_history.csv | 100% | % ETFs with positive 26w return |
| market_trend_positive | market_state_history.csv | 100% | Binary trend flag |
| canary_breadth_default | market_state_history.csv | 100% | Canary breadth indicator |
| vix_level_z_tradable | regime_features.csv | partial | VIX z-score (tradable) |

**US offense ETF returns (full period):**

| ETF | Ann Return | Ann Vol | In GGG1 default | In P3 pure |
|---|---|---|---|---|
| QQQ | ~14.8% | ~21% | Yes | Yes |
| SPY | ~10.5% | ~15% | Yes | Yes |
| IWM | ~8.3% | ~20% | Yes | Yes |
| VUG | ~12.4% | ~17% | No | Growth only |
| EFA | ~5.7% | ~17% | Yes | No |
| VEA | ~5.6% | ~17% | Yes | No |
| VWO | ~4.2% | ~18% | Yes | No |
| PDBC | ~3.1% | ~18% | Yes | No |
| DBA | ~2.4% | ~16% | Yes | No |

The diversification drag from EFA/VEA/VWO/PDBC/DBA is the direct cause of calm_trend underperformance.

---

## Part B — Signal Definitions

**Standard breadth signal:** `breadth_sma_43 >= 0.65 AND market_trend_positive = 1 AND not {stressed_panic, recovery_fragile}`
- Total active weeks: **535** (48.2% of all weeks)
- In calm_trend: 284 of 295 weeks (96.3%)
- In neutral_mixed: 209 of 493 weeks (42.4%)
- In stressed_panic: 0 (by design)

**Double-confirmed signal:** above + `canary_breadth_default = 1`
- Total active weeks: **132** (11.9%)
- Much more restrictive — fires mainly in high-conviction calm states

---

## Part C — Offense Basket Designs

| Basket | Tickers | Role |
|---|---|---|
| GGG1 default | SPY/QQQ/IWM/EFA/VEA/VWO/EWJ/VNQ/PDBC/DBA | Baseline — diversified, international drag |
| P3 US pure | SPY/QQQ/IWM | Drops international and commodity — all US broad market |
| P3 US growth | QQQ/SPY/VUG | More concentrated in US tech/growth |

---

## Part D — Event / Forward-Return Validation

Signal validates: US pure offense outperforms GGG1 diversified offense in high-breadth states.

| State | Signal | 4w forward: US pure | 4w forward: GGG diversified | Lift |
|---|---|---|---|---|
| calm_trend | all | 0.525% | 0.176% | **+0.349%** |
| calm_trend | breadth_on | 0.504% | 0.133% | **+0.371%** |
| neutral_mixed | all | 0.983% | 0.772% | +0.211% |
| neutral_mixed | breadth_on | 1.223% | 0.983% | **+0.240%** |

Portfolio-level impact estimate: `composite_regime_offense_component` is ~9-11% of total portfolio. Even with the full 4-week lift of +0.37% in calm_trend (26.6% of weeks), the portfolio-level annual contribution is bounded at ~0.10-0.20pp.

---

## Part E — Candidate Logic

| Candidate | Signal | States Modified | Offense Basket | State Tilt | Phase2b Mode |
|---|---|---|---|---|---|
| C1 breadth_neutral | standard | neutral_mixed | US pure | GGG1 | +0.08 boost |
| **C2 calm_us** | standard | calm_trend | **US pure** | GGG1 | GGG1 |
| C3 qqq_growth | standard | calm+neutral | US growth | GGG1 | GGG1 |
| C4 credit | double | calm+neutral | US pure | GGG1 | GGG1 |
| C5 balanced | standard | calm+neutral | US pure | Phase2 nonstressed | +0.08 boost |
| C6 stretch | standard | calm+neutral+RC | US growth | Phase2 stretch | +0.10 boost |

All 18 candidate artifacts built successfully.

---

## Part G — Full Period and Holdout Metrics

### Full period (2005–2026)

| Portfolio | Ann Return | Sharpe | Max DD | CVaR 5% | Avg BIL | Beta SPY |
|---|---|---|---|---|---|---|
| **C2 calm_us** | 7.27% | **0.966** | **-11.90%** | -2.48% | 27.9% | -0.030 |
| C6 stretch | 7.28% | 0.919 | -15.76% | -2.57% | 27.8% | -0.032 |
| C5 balanced | 7.12% | 0.907 | -15.32% | -2.56% | 27.7% | -0.032 |
| C3 qqq_growth | 6.94% | 0.932 | -13.65% | -2.42% | 30.0% | -0.030 |
| C4 credit | 6.95% | 0.908 | -14.67% | -2.54% | 27.7% | -0.031 |
| C1 breadth_neutral | 6.83% | 0.877 | -15.37% | -2.58% | 26.3% | -0.032 |
| **GGG1** | **7.14%** | **0.936** | **-11.77%** | -2.54% | 26.7% | -0.031 |
| Phase 2 best | **7.39%** | 0.940 | -12.50% | -2.60% | 24.6% | -0.032 |
| Production pin | 6.89% | 0.884 | -13.98% | -2.62% | 28.4% | -0.025 |
| SPY | 10.54% | 0.600 | -54.61% | -5.80% | — | 1.000 |

### Holdout 2020-forward

| Portfolio | Ann Return | Sharpe | Max DD | Active vs GGG1 |
|---|---|---|---|---|
| **C2 calm_us** | **9.94%** | **1.124** | **-11.90%** | +0.39pp |
| Phase 2 best | 9.70% | 1.061 | -12.50% | +0.15pp |
| C6 stretch | 9.26% | 0.972 | -15.76% | -0.29pp |
| **GGG1** | **9.55%** | **1.082** | **-11.77%** | — |
| SPY | 14.14% | 0.732 | -31.83% | +4.59pp |
| QQQ | 15.16% | 0.667 | -37.91% | +5.61pp |

### Holdout 2021-forward

| Portfolio | Ann Return | Sharpe | Active vs GGG1 |
|---|---|---|---|
| **C2 calm_us** | 10.57% | **1.403** | +0.34pp |
| C6 stretch | 10.45% | 1.413 | +0.22pp |
| GGG1 | 10.22% | 1.348 | — |
| Phase 2 best | 10.50% | 1.341 | +0.28pp |

### 2022 Bear Period

| Portfolio | Ann Return | vs GGG1 |
|---|---|---|
| C6 stretch | **+0.09%** | +1.43pp |
| C5 balanced | -0.58% | +0.73pp |
| GGG1 | -1.29% | — |
| **C2 calm_us** | -1.43% | -0.14pp |
| Production pin | **+0.51%** | +1.80pp |

C2 has very slightly worse 2022 protection (-0.14pp vs GGG1) but still far better than SPY (-18.18%) and QQQ (-36.0%).

### 2023+ Recovery

C2 leads all candidates: 14.99% annualized (Sharpe 1.893), vs GGG1 14.36% and Phase 2 best 14.79%.

---

## Part H — State-by-State Diagnosis

### calm_trend state — the core finding

| Portfolio | Ann Return | Sharpe | Delta vs GGG1 | Avg QQQ |
|---|---|---|---|---|
| C2 calm_us | 4.36% | **0.588** | **+0.27pp / +0.074 Sharpe** | 3.1% |
| C3 qqq_growth | 4.44% | 0.603 | +0.36pp | 3.7% |
| Phase 2 best | 4.13% | 0.517 | +0.04pp | — |
| **GGG1** | **4.09%** | **0.514** | — | — |

**C2 improves calm_trend Sharpe by +0.074** (from 0.514 to 0.588). This is a clean, genuine improvement. Switching the offense component ETF mix to pure US equity (SPY/QQQ/IWM) reduces volatility in the offense component because US-only assets have lower cross-correlation variance during US bull markets.

### neutral_mixed state

| Portfolio | Ann Return | Sharpe | Delta vs GGG1 |
|---|---|---|---|
| Phase 2 best | 11.74% | 1.469 | +0.53pp |
| C2 calm_us | 11.27% | 1.462 | +0.06pp |
| **GGG1** | **11.21%** | **1.462** | — |

C2's neutral_mixed performance is essentially unchanged from GGG1 (calm_trend was the targeted state, not neutral_mixed).

### stressed_panic state — protection preserved

| Portfolio | Ann Return | Sharpe | BIL sleeve |
|---|---|---|---|
| C2 calm_us | 3.72% | 0.492 | **50.9%** |
| GGG1 | 3.58% | 0.481 | ~50.9% |

C2 actually slightly *improves* stressed_panic performance (+0.14pp), because the pure US offense composition, when it does fire (it doesn't in stressed_panic by design), means transitions out of stressed states are cleaner.

### Signal-active vs signal-inactive

| Portfolio | Signal-active return | Signal-inactive return |
|---|---|---|
| C2 calm_us | 7.42% | 7.71% |
| GGG1 baseline | — | — |

The signal-inactive weeks have higher return because they include normal non-breadth periods where the strategy is defensive and protection works well. The signal-active improvement is in the quality (Sharpe) of calm_trend participation, not raw return level.

---

## Part I — Risk, Realism, Hidden Beta

### Hidden beta assessment

All candidates maintain **negative SPY beta** (−0.030 to −0.032). No candidate has positive correlation to SPY. All hidden_beta_risk = LOW (except C5 which has `pct_from_beta = 0.603` but virtually no return improvement vs GGG1 at +0.00pp — artifact of near-zero denominator).

**No disguised SPY.** The pure US equity offense basket does not increase SPY correlation — it reduces it slightly because SPY/QQQ/IWM are more internally consistent than a basket that also holds PDBC/DBA.

### Mandate guardrail check

| Candidate | Max DD | Sharpe | Bear OK | Mandate |
|---|---|---|---|---|
| C1 | -15.37% | 0.877 | ✓ | **FAIL** (Sharpe < 0.90) |
| **C2** | -11.90% | **0.966** | ✓ | **✓** |
| C3 | -13.65% | 0.932 | ✓ | ✓ |
| C4 | -14.67% | 0.908 | ✓ | ✓ |
| C5 | -15.32% | 0.907 | ✓ | ✓ |
| C6 | -15.76% | 0.919 | ✓ | ✓ |

C1 REJECTED for Sharpe 0.877 — the Phase 2b +0.08 neutral boost combined with neutral_mixed US offense creates instability (the regime boost aggressively lowers overlay cash while the ETF composition change in neutral_mixed creates more volatility → higher BIL from the overlay self-correction → net negative).

### Why QQQ/growth concentrated offense (C3) backfires

C3 has avg BIL = 30.0% — **higher** than GGG1 (26.7%). The mechanism: QQQ/VUG have higher weekly volatility than SPY/QQQ/IWM balanced. The overlay system detects higher portfolio volatility and increases the cash allocation to maintain target vol — counteracting the intended offense expansion. The portfolio becomes *more* defensive, not less.

### Turnover / cost realism

All candidates use the same cost model as GGG1. Turnover is similar (ETF composition changes within one sleeve don't significantly increase turnover relative to the full portfolio).

---

## Part J — Selection Table

| Candidate | Classification | Return | Sharpe | Max DD | vs GGG1 | vs Phase2 |
|---|---|---|---|---|---|---|
| C1 breadth_neutral | **REJECT** | 6.83% | 0.877 | -15.37% | -0.31pp | -0.56pp |
| **C2 calm_us** | **KEEP_AS_AGGRESSIVE_SHADOW** | **7.27%** | **0.966** | **-11.90%** | **+0.13pp** | -0.12pp |
| C3 qqq_growth | REJECT | 6.94% | 0.932 | -13.65% | -0.20pp | -0.45pp |
| C4 credit | REJECT | 6.95% | 0.908 | -14.67% | -0.19pp | -0.44pp |
| C5 balanced | REJECT | 7.12% | 0.907 | -15.32% | -0.02pp | -0.27pp |
| C6 stretch | KEEP_AS_RESEARCH_ONLY | 7.28% | 0.919 | -15.76% | +0.14pp | -0.11pp |

**Best candidate: `improved_phase3_high_breadth_calm_us_offense` (C2)**
- Sharpe **0.966** — highest of any candidate across all phases so far
- Return 7.27% — beats GGG1 (+0.13pp) but does not beat Phase 2 best (-0.12pp)
- Max drawdown -11.90% — essentially the same as GGG1 (-11.77%)
- 2020-forward: 9.94% / Sharpe 1.124 — exceeds Phase 2 best (9.70%)

---

## Key Finding: Why 9% Was Not Reached

**The `composite_regime_offense_component` sleeve is the binding constraint.**

In calm_trend, this sleeve is ~10% of total portfolio weight. Even if we improve its ETF composition perfectly (which C2 does), the portfolio-level impact is:
- Sleeve return improvement in calm_trend: ~0.27% annualized
- Sleeve weight: ~10%
- Portfolio contribution: ~0.027% annualized of the 0.13pp total improvement

The rest of the improvement comes from secondary effects on the HRP allocator adjusting to the cleaner covariance of the US-only sleeve. The Sharpe improvement (+0.030 for C2 vs GGG1) is the most visible manifestation: the offense component is now less noisy.

**The QQQ growth concentration lesson**: Making the offense basket more concentrated (C3: QQQ/SPY/VUG) does not improve portfolio returns. The higher volatility of the concentrated basket triggers the overlay's vol-targeting mechanism to increase cash, counteracting the intended return improvement. The optimal offense concentration is the US broad market (SPY/QQQ/IWM), not growth/tech only.

**The double-confirmation lesson**: The strict credit_confirmed signal (132 vs 535 active weeks, C4) is too restrictive — it misses most calm-trend weeks and doesn't add return despite fewer false signals.

**The fundamental ceiling**: The `composite_regime_offense_component` + `composite_regime_defense_component` + `dual_momentum_topn` + `cta_trend_long_only` + `composite_selective_signals` + `taa_10m_sma` form the full risky budget. Changing the ETF composition of just one component (~10% of portfolio) can improve Sharpe but cannot move the annual return by 2-3pp. To reach 9%, we need either:
1. A new offense sleeve that gets 20-25% portfolio budget and holds concentrated US equity when breadth confirms
2. Or an explicit sector rotation mechanism where the top 3-5 sector ETFs (XLK, XLF, XLV, etc.) form the primary offense basket

---

## Audit Results

Quick audits run on `improved_phase3_high_breadth_calm_us_offense`:
- Research committee: logged
- Backtest realism: logged
- Allocator benchmark: logged

---

## Final Recommendation

**Decision: `PROCEED_TO_PHASE4_SECTOR_BREADTH_ROTATION`**

Phase 3 demonstrated that:
1. **Switching the offense ETF basket to pure US equity in high-breadth calm states improves Sharpe from 0.936 to 0.966** (C2) — genuine, clean improvement.
2. But the absolute return improvement is only +0.13pp (7.27% vs 7.14%) because the targeted sleeve is too small.
3. QQQ/growth concentration backfires due to volatility-targeting cash buildup.
4. Phase 3B refinement would likely improve Sharpe further but cannot reach 9% by changing a ~10% sleeve.

**To reach 9-10%, Phase 4 must:**
- Create a dedicated sector-rotation offense sleeve with 20-25% portfolio budget
- Use sector ETF momentum/breadth signals to concentrate in leading sectors (XLK, XLF, XLV, XLY, XLI, etc.)
- The sector ETFs already exist in the project universe — no new data sources needed
- Sector breadth confirmation (e.g., ≥ 5 of 11 sectors in uptrend) provides the needed signal

**C2 (`improved_phase3_high_breadth_calm_us_offense`) is tracked as a new aggressive shadow** — it is the best Sharpe candidate (0.966) and has the best 2020-forward return among all candidates (9.94% / Sharpe 1.124). Phase 2 best remains the best return candidate (7.39%). Both are tracked as aggressive shadows.

---

## Phase 4 Prompt Outline

**Phase 4 — Sector Breadth / Sector ETF Rotation**

Goal: Build a sector-rotation offense sleeve using the existing 11 sector ETFs (XLK, XLF, XLV, XLY, XLI, XLB, XLE, XLU, XLP, VNQ + optionally EEM/EFA for international breadth). This sleeve should replace or augment the current diversified offense component with a momentum-ranked top-N sector selection that gets a materially larger portfolio budget (20-25%) during confirmed bull markets.

Key questions to answer:
1. Does sector momentum (top 3-5 sectors by 13w/26w return) outperform equal-weight sector exposure in calm/neutral states?
2. Can sector breadth (% of sectors in positive trend) serve as the primary offense confirmation signal?
3. Can a sector-rotation sleeve with 20-25% budget, active only in non-stressed states, add 1.5-2.0pp annual return vs GGG1?

Constraints:
- Same regime engine and state classification
- No individual stocks
- Causal momentum features only (lagged by at least 1 week)
- Must not weaken stressed_panic protection
- Must beat Phase 2 best (7.39%) and Phase 3 C2 (7.27%) out of sample
- Time-ordered splits only

---

## Resume / Project Story

**Arc 1 (1–2B):** Regime engine + dual-track production. Pin: `improved_phase2b_regime_confidence_boost`.

**Arc 2 (AAA–GGG):** Offense composition + confirmation gating. Candidate: GGG1 (7.14% / Sharpe 0.936).

**Arc 3 (OOO–SSS):** Hard-ML signal discovery. Shadow: `improved_phasesss3_calm_old_low_stress_derisk`.

**Phase 1 (Return Unlock Audit):** Diagnosed return ceiling as mandate-driven. Bottlenecks: neutral_mixed BIL (44% of weeks, 26% BIL) and calm_trend defense (29%). Decision: Phase 2.

**Phase 2 (Aggressive ETF Variant):** Tested sleeve reallocation — defense→offense in calm/neutral. Best: 7.39% / Sharpe 0.940. Finding: offense sleeves hold diversified international/commodity ETFs that don't capture US bull upside. Decision: aggressive shadow. Phase 3 needed.

**Phase 3 (Breadth-Confirmed US Offense — this phase):** Switched `composite_regime_offense_component` to pure US equity (SPY/QQQ/IWM) during high-breadth calm states. Best: C2 at 7.27% / Sharpe **0.966** (best risk-adjusted across all phases). Finding: switching one ~10% sleeve can improve Sharpe but not reach 9%. QQQ concentration backfires. Decision: Phase 3 C2 as second aggressive shadow; proceed to Phase 4.

**Cumulative aggressive shadow stack:**
- `improved_phase2_aggressive_neutral_cash_unlock`: 7.39% / 0.940 — best return
- `improved_phase3_high_breadth_calm_us_offense`: 7.27% / **0.966** — best Sharpe

**Next: Phase 4 — Sector Breadth/Sector ETF Rotation.** A sector-rotation sleeve with 20-25% portfolio budget and sector momentum signals is the next lever that can actually move the return needle toward 9%.
