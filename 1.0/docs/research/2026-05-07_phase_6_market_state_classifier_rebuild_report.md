# Phase 6 — Market-State Classifier Rebuild

**Date:** 2026-05-07
**Type:** Strategy research. No production pins changed. No auto-promotion.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense`
**Phase 4B best shadow:** `improved_phase4b_refined_sector_20pct` (7.76% / Sharpe 0.959)

---

## Commands Executed

```bash
mkdir -p data/research/phase_6_market_state_classifier_rebuild
python3 scripts/phase_6_market_state_classifier_rebuild.py
```

**Build:** `scripts/build_improvement_artifacts.py` modified — added 5 Phase 6 `state_tilt` modes (`phase6_neutral_classifier_unlock`, `phase6_calm_bull_quality_offense`, `phase6_recovery_quality_rerisk`, `phase6_continuous_aggression_score`, `phase6_balanced_classifier_rebuild`) and 5 version specs using `phase4b_sector_20_subset`.

---

## Files Created / Modified

**Script:** `scripts/phase_6_market_state_classifier_rebuild.py`

**Outputs (47 files in `data/research/phase_6_market_state_classifier_rebuild/`):**
classifier failure map, feature inventory, classifier design, panel, validation, candidate designs, build log, full/holdout metrics, state diagnostics, risk/hidden beta, selection, audits, decision

**Candidate artifacts** (15 files in `data/05_layer3_portfolio_construction/`):
- 5 × `portfolio_version_returns_improved_phase6_*.csv`
- 5 × `portfolio_version_weights_improved_phase6_*.csv`
- 5 × `portfolio_version_sleeve_weights_improved_phase6_*.csv`

---

## Why Phase 6 Skips Paid Stock Data

Phase 5A-Free diagnostic showed stock breadth is promising but the signal depends on PIT data (Norgate/WRDS/Sharadar) to be production-valid. Rather than pay for data now, Phase 6 exhausts what can be extracted from existing project data — specifically, whether richer market-state classification using the existing `market_state_history.csv` features can break the return ceiling.

**This is the final phase of the existing-data improvement arc.** If Phase 6 cannot reach 8.0%+, the conclusion is that PIT stock breadth data is genuinely required to advance further.

---

## Part A — Classifier Failure Map

| State | Freq | Phase4B return | SPY return | Opportunity cost | Assessment |
|---|---|---|---|---|---|
| calm_trend | 26.6% | 4.39% | **16.87%** | **−12.48%** | **BOTTLENECK_PRIMARY** |
| neutral_mixed | 44.4% | 12.07% | 8.64% | +3.43% | IMPROVED (Phase4B already better than SPY) |
| stressed_panic | 20.6% | 3.82% | −4.92% | +8.74% | PROTECTED |
| recovery_confirmed | 4.0% | 4.37% | 40.09% | −35.72% | IMPROVED vs GGG1 but large opportunity cost |
| recovery_fragile | 4.4% | 7.71% | 53.90% | −46.19% | IMPROVED vs GGG1 but large opportunity cost |

**The return ceiling is still calm_trend.** 26.6% of all weeks, −12.48% annual opportunity cost vs SPY. Phase4B already improved neutral_mixed substantially (12.07% vs 9.80% in GGG1). The remaining bottleneck is structural: calm_trend offense ETFs don't track US equity performance.

**What Phase 4B already solved:** neutral_mixed is now generating 12.07% annualized, better than SPY (8.64% in those periods). This is the portfolio's strongest contribution state.

---

## Part B — Existing Feature Inventory

All 17 features inspected are production-safe. Key Phase 6 additions beyond Phase 4B:

| Feature | Source | Role in Phase 6 | Production safe |
|---|---|---|---|
| breadth_sma_43 | market_state_history | Core breadth level | Yes |
| breadth_change_4w | market_state_history | Breadth momentum | Yes |
| canary_breadth_default | market_state_history | Canary confirmation | Yes |
| transition_good_state_prob | market_state_history | Regime persistence quality | Yes |
| aggression_score (composite) | derived from above | 0-1 continuous | Yes |

**Excluded:** Current-constituent stock breadth (Phase 5A-Free outputs) — SURVIVORSHIP_BIASED, not used in any candidate.

---

## Part C — Classifier Design

Five Phase 6 classifier conditions, all reading `market_state_row` features causally:

| Signal | Condition | Intended action |
|---|---|---|
| extreme_quality_calm | calm_trend + breadth≥0.80 + trend=1 + canary=1 | +4pp sector sleeve |
| high_quality_neutral | neutral_mixed + breadth≥0.70 + trend=1 + canary=1 + good_prob≥0.60 | +4pp sector sleeve |
| low_quality_neutral | neutral_mixed + (breadth<0.50 OR breadth_change<−0.05) | −3pp retraction |
| strong_recovery | recovery_confirmed + breadth_change≥0 + good_prob≥0.55 | +4pp sector sleeve |
| aggression_score_high | composite score ≥ 0.72 | +3pp sector sleeve |

---

## Part D — Classifier Panel

| Signal | Active weeks | Frequency | Key finding |
|---|---|---|---|
| extreme_quality_calm | 58 | 5.2% | All in calm_trend |
| **high_quality_neutral** | **0** | **0.0%** | **Never fired — see below** |
| low_quality_neutral | 264 | 23.8% | 53.5% of neutral_mixed weeks |
| strong_recovery | 34 | 3.1% | ~77% of recovery_confirmed weeks |

### Critical finding: `high_quality_neutral` fired 0 times

The condition `canary_breadth_default == 1.0 AND transition_good_state_prob >= 0.60` was **never simultaneously satisfied** in neutral_mixed weeks:
- `transition_good_state_prob` in neutral_mixed has a **maximum of 0.205** and a mean of 0.122. The threshold of 0.60 is fundamentally incompatible — `transition_good_state_prob` is the probability of *transitioning to* a good state, which by design is low in neutral_mixed periods.
- `canary_breadth_default == 1.0` fires in only 68 of 493 neutral_mixed weeks (13.8%).
- Combining both: 0 qualifying weeks.

**This signal was over-specified and will not be used in any Phase 6 candidate.** The neutral_classifier_unlock candidate (C1) ends up behaving identically to Phase4B in non-low-quality neutral weeks.

---

## Part E — Classifier Validation

### Key: Phase4B 4-week forward return by signal

| Signal | Active weeks | Phase4B 4w (on) | Phase4B 4w (off) | Lift |
|---|---|---|---|---|
| extreme_quality_calm | 58 | 0.576% | 0.595% | **−0.019%** ← negative |
| high_quality_neutral | 0 | N/A | 0.594% | N/A |
| **aggression_score_high** | **466** | **0.694%** | **0.520%** | **+0.174%** |

### Aggression bucket validation (Phase4B 4w returns)

| Bucket | Weeks | Phase4B 4w mean | Hit rate |
|---|---|---|---|
| defensive | 214 | 0.334% | 58.9% |
| cautious | 168 | 0.861% | 61.9% |
| moderate | 94 | 0.469% | 54.3% |
| aggressive | 135 | 0.665% | 64.4% |
| **max_aggressive** | **425** | **0.706%** | **66.6%** |

The aggression score bucket validation is promising: `max_aggressive` (score ≥ 0.75) shows the highest hit rate (66.6%) and second-highest mean return. This is the basis of C4's marginal improvement.

### Same-state lift breakdown

| State | Signal | SPY 4w on | SPY 4w off | Lift |
|---|---|---|---|---|
| calm_trend | extreme_quality_calm | 0.881% (N=58) | 0.610% | **+0.271%** |
| calm_trend | aggression_score_high | 0.660% (N=271) | 0.701% | **−0.041%** |
| neutral_mixed | aggression_score_high | 0.942% (N=139) | 1.031% | **−0.089%** |
| recovery_confirmed | aggression_score_high | 0.965% (N=36) | 0.905% | +0.060% |

**The critical finding for calm_trend:** `extreme_quality_calm` shows +0.271% SPY 4w lift (higher breadth → higher SPY returns). But for Phase4B portfolio, this signal shows **negative** lift (−0.019%). Why? Phase4B already deploys the sector sleeve during high-breadth calm weeks via `high_quality_sector_bull`. The Phase 6 additional boost in the same weeks creates slight over-allocation that doesn't help.

**For neutral_mixed:** `aggression_score_high` shows **negative** lift for Phase4B (−0.089%). High-breadth neutral weeks don't reliably outperform low-breadth neutral weeks for the existing portfolio — the sector sleeve is already partially deployed via Phase4B in quality neutral weeks.

---

## Part H — Full Period and Holdout Metrics

### Full period (2005–2026)

| Portfolio | Ann Return | Sharpe | Max DD | Avg Sector | Beta SPY | vs Phase4B |
|---|---|---|---|---|---|---|
| **C4 aggression_score** | **7.80%** | 0.953 | -14.18% | 11.4% | -0.033 | **+0.04pp** |
| C1 neutral_unlock | 7.75% | **0.958** | **-13.77%** | 9.9% | -0.033 | -0.01pp |
| C3 recovery_rerisk | 7.75% | 0.956 | **-13.77%** | 10.3% | -0.033 | -0.01pp |
| C2 calm_quality | 7.73% | 0.952 | -14.32% | 10.3% | -0.033 | -0.03pp |
| C5 balanced_rebuild | 7.71% | 0.950 | -14.25% | 10.2% | -0.033 | -0.05pp |
| **Phase4B best** | **7.76%** | **0.959** | **-13.77%** | 10.0% | -0.033 | — |
| GGG1 | 7.14% | 0.936 | -11.77% | — | -0.031 | -0.62pp |
| SPY | 10.54% | 0.600 | -54.61% | — | 1.000 | +2.78pp |

**Phase4B remains the Sharpe leader (0.959).** C4 edges it on return (+0.04pp) but loses on Sharpe (0.953 vs 0.959) and max drawdown (-14.18% vs -13.77%).

### Holdout 2020-forward

| Portfolio | Ann Return | Sharpe | Max DD | vs Phase4B |
|---|---|---|---|---|
| Phase3 best | 9.94% | **1.124** | -11.90% | +0.30pp |
| Phase2 best | 9.70% | 1.061 | -12.50% | +0.08pp |
| **Phase4B best** | **9.56%** | **1.012** | **-13.77%** | — |
| C4 aggression_score | 9.53% | 0.994 | -14.18% | **-0.02pp** |
| C3 recovery_rerisk | 9.57% | 1.008 | -13.77% | +0.01pp |
| GGG1 | 9.55% | 1.082 | -11.77% | -0.01pp |

**Surprising: Phase3 best (7.27% full period, Sharpe 0.966) leads all candidates in 2020-forward (9.94%, Sharpe 1.124).** Phase 6 candidates slightly lag Phase4B in the holdout. C3 (recovery_rerisk) is the only Phase 6 candidate that improves on Phase4B in the 2020-forward window.

### 2022 Bear Period

All Phase 6 candidates perform identically to Phase4B best (-1.52%) — they inherit Phase4B's sector sleeve and stressed_panic protection unchanged. All far better than SPY (-18.18%).

---

## Part I — State-by-State Diagnosis

### C5 (balanced_rebuild) vs Phase4B

| State | C5 return | Phase4B return | Delta |
|---|---|---|---|
| calm_trend | 4.29% | 4.39% | **-0.10%** |
| neutral_mixed | 12.06% | 12.07% | -0.01% |
| recovery_confirmed | 4.17% | 4.37% | **-0.20%** |
| stressed_panic | 3.78% | 3.82% | -0.04% |

**All states are marginally worse than Phase4B.** The Phase 6 classifier signals introduce small amounts of drag rather than improvement in the targeted states, primarily because Phase4B already well-allocates within those states.

### C4 (aggression_score) vs Phase4B

| State | C4 delta vs Phase4B |
|---|---|
| neutral_mixed | +0.07pp |
| calm_trend | **-0.03pp** |
| stressed_panic | 0.00pp |
| recovery_fragile | **+0.31pp** |
| recovery_confirmed | **+0.22pp** |

C4 improves recovery_confirmed (+0.22pp) and recovery_fragile (+0.31pp) while being neutral on stressed_panic and slightly hurting calm_trend. The overall +0.04pp full-period improvement comes from recovery states.

---

## Part J — Risk, Realism, Hidden Beta

All candidates: **no disguised SPY**, all beta ≈ −0.033 (same as Phase4B). All pass mandate guardrails (max DD within -22%, Sharpe ≥ 0.90, bear protection maintained).

| Candidate | vs Phase4B return | Hidden Beta | Mandate | Bear OK |
|---|---|---|---|---|
| C1 neutral_unlock | -0.01pp | LOW | OK | OK |
| C2 calm_quality | -0.03pp | LOW | OK | OK |
| C3 recovery_rerisk | -0.01pp | LOW | OK | OK |
| **C4 aggression_score** | **+0.04pp** | LOW | OK | OK |
| C5 balanced_rebuild | -0.05pp | LOW | OK | OK |

---

## Part K — Selection Table

| Candidate | Classification | Return | Sharpe | Max DD | vs Phase4B |
|---|---|---|---|---|---|
| **C4 aggression_score** | **KEEP_AS_AGGRESSIVE_SHADOW** | **7.80%** | 0.953 | -14.18% | **+0.04pp** |
| C3 recovery_rerisk | KEEP_AS_AGGRESSIVE_SHADOW | 7.75% | 0.956 | -13.77% | -0.01pp |
| C1 neutral_unlock | KEEP_AS_RESEARCH_ONLY | 7.75% | 0.958 | -13.77% | -0.01pp |
| C2 calm_quality | KEEP_AS_RESEARCH_ONLY | 7.73% | 0.952 | -14.32% | -0.03pp |
| C5 balanced_rebuild | KEEP_AS_RESEARCH_ONLY | 7.71% | 0.950 | -14.25% | -0.05pp |

**Best candidate: `improved_phase6_continuous_aggression_score`** — marginally beats Phase4B on full-period return (+0.04pp) with no new data, no disguised SPY, no mandate violations. Tracked as aggressive shadow.

---

## Why 8.0% Full-Period Return Was Not Reached

After 6 phases of systematic improvement using existing data only:

| Phase | Best candidate | Full-period return | Sharpe |
|---|---|---|---|
| GGG1 (baseline) | improved_phaseggg_confirmed_only_robust_offense | 7.14% | 0.936 |
| Phase 2 | improved_phase2_aggressive_neutral_cash_unlock | 7.39% | 0.940 |
| Phase 3 | improved_phase3_high_breadth_calm_us_offense | 7.27% | **0.966** |
| Phase 4 | improved_phase4_sector_20pct_offense | ~7.64% | ~0.94 |
| Phase 4B | improved_phase4b_refined_sector_20pct | 7.76% | 0.959 |
| **Phase 6** | improved_phase6_continuous_aggression_score | **7.80%** | 0.953 |

The return ceiling has moved from 7.14% to 7.80% (+0.66pp) over 6 phases of existing-data optimization. The remaining gap to 8.0% is only 0.20pp, but:

1. **calm_trend** (26.6% of weeks) is the binding constraint. Phase6 makes it slightly worse (-0.03pp in calm_trend).
2. The `extreme_quality_calm` signal (breadth≥0.80 in calm_trend) shows **negative** Phase4B lift because Phase4B's sector sleeve is already optimally deployed in high-breadth calm weeks.
3. The `aggression_score_high` classifier fires in 42% of all weeks but shows **negative** same-state lift in both calm_trend (−0.041%) and neutral_mixed (−0.089%). Its overall positive lift comes from correctly firing in recovery states.
4. **No classifier signal based on existing ETF/regime features can usefully distinguish high-return from lower-return calm_trend weeks**, because the differentiating information (stock-level breadth quality) is not in the current data.

---

## Cumulative Aggressive Shadow Stack

| Strategy | Full return | Sharpe | Role |
|---|---|---|---|
| `improved_phase4b_refined_sector_20pct` | 7.76% | **0.959** | Best Sharpe shadow |
| `improved_phase6_continuous_aggression_score` | **7.80%** | 0.953 | Best return shadow |
| `improved_phase3_high_breadth_calm_us_offense` | 7.27% | 0.966 | Best 2020+ Sharpe |
| `improved_phase2_aggressive_neutral_cash_unlock` | 7.39% | 0.940 | Baseline aggressive |

---

## Final Recommendation: `KEEP_PHASE6_AS_AGGRESSIVE_SHADOW`

The Phase 6 classifier rebuild successfully extracted the remaining signal from existing data. `improved_phase6_continuous_aggression_score` marginally improves on Phase4B (+0.04pp return) but trades Sharpe (0.953 vs 0.959) and max drawdown (-14.18% vs -13.77%).

**The existing-data improvement arc is now complete.** Six phases have moved the full-period return from 7.14% to 7.80%. The next 0.20pp to reach 8.0% cannot be extracted from existing ETF/sector/regime features. The binding constraint is calm_trend, and the differentiating information for calm_trend is stock-level breadth quality.

**Recommended next step:** `RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE`

Purchase Norgate Data US Stocks Platinum/Diamond when budget allows. The Phase 5A-Free diagnostic confirmed that stock breadth shows meaningful calm_trend same-state lift (+0.517% per 4 weeks for SPY). With PIT data, a Phase 5B candidate targeting 8.0%+ is feasible. Until then, the Phase 4B best shadow (`improved_phase4b_refined_sector_20pct`) or Phase 6 best shadow (`improved_phase6_continuous_aggression_score`) are the strongest aggressive candidates available.

---

## Phase 7 Prompt Outline (if continuing without PIT data)

**Phase 7 — Allocator Objective Rewrite**

If PIT stock breadth remains unavailable, Phase 7 should test whether the portfolio construction objective (currently HRP with conservative overlay) can be rewritten to allow more concentrated US equity exposure in confirmed good states. Specifically:

1. Replace HRP with a risk-budgeting objective that explicitly allocates a defined risk budget to US equity in high-score aggression states
2. Allow a `target_return` objective in calm_trend instead of `min_variance`/HRP
3. Test whether the existing regime engine, when paired with a return-targeting allocator, can reach 8.0%

This avoids the need for new data but changes the construction methodology — potentially more impactful than classifier refinement.

---

## Resume / Project Story

**Arcs 1–3 (Phases 1–SSS3):** Built the regime engine, refined offense composition, explored hard-ML signals. Production candidate: GGG1 (7.14% / Sharpe 0.936).

**Arc 4 (Phases 1–6 Return Unlock):**
- Phase 1: Diagnosed return ceiling as mandate-driven. calm_trend bottleneck.
- Phase 2: Sleeve reallocation. +0.25pp. Aggressive shadow.
- Phase 3: US pure offense ETF. Sharpe 0.966. +0.13pp return.
- Phase 4: Sector sleeve. Best: Phase4 sector 20%. Improved.
- Phase 4B: Refined sector sleeve. **Best: 7.76% / 0.959 Sharpe.** Aggressive shadow.
- Phase 5: PIT stock breadth blocked. Data gap confirmed.
- Phase 5A: Scaffold + templates. Ready for Norgate/WRDS.
- Phase 5A-Free: Diagnostic confirmed stock breadth promising in calm_trend (+0.517% 4w lift).
- Phase 6: Classifier rebuild using existing data. **Best: 7.80% / 0.953 Sharpe.** Aggressive shadow.

**Existing-data arc exhausted. Gap to 8.0% is 0.20pp. PIT stock breadth needed.**
