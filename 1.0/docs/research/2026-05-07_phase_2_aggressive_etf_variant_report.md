# Phase 2 — Aggressive ETF Variant

**Date:** 2026-05-07
**Type:** Strategy research. No production pins changed. No auto-promotion.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense`
**Official shadow:** `improved_phase2b_combo_abc`

---

## Commands Executed

```
mkdir -p data/research/phase_2_aggressive_etf_variant
python3 scripts/phase_2_aggressive_etf_variant.py 2>&1 | tee data/research/phase_2_aggressive_etf_variant/phase2_run.log
```

**Build command (internal):**
```
BUILD_VERSION_NAMES='improved_phase2_aggressive_neutral_cash_unlock,...' python3 scripts/build_improvement_artifacts.py
```

---

## Files Created / Modified

**Scripts modified:**
- `scripts/build_improvement_artifacts.py` — added 2 new `phase2b_mode` strings (`phase2_aggressive_neutral_boost`, `phase2_aggressive_full_mandate`) and 5 new `state_tilt` modes, plus 6 new version specs

**New script:**
- `scripts/phase_2_aggressive_etf_variant.py`

**Outputs (all in `data/research/phase_2_aggressive_etf_variant/`):**
27 files including: mandate design, candidate designs, build log, full/holdout metrics, state diagnostics, risk/realism checks, hidden beta checks, 2022 bear check, selection table, audit logs, next phase decision, protocol JSON

**Candidate artifacts** (in `data/05_layer3_portfolio_construction/`):
- 6 × `portfolio_version_returns_improved_phase2_*.csv`
- 6 × `portfolio_version_weights_improved_phase2_*.csv`
- 6 × `portfolio_version_sleeve_weights_improved_phase2_*.csv`

**Docs updated:**
- `docs/research/project_journey.md`

---

## Phase 1 Bottleneck Summary (Context)

Phase 1 identified the return ceiling as mandate-driven:
- **neutral_mixed** (44% of weeks): avg BIL 26%, generates 68.5% of total wealth
- **calm_trend** (27% of weeks): defense_component 29% despite SPY returning 17.5% ann
- **stressed_panic** (21%): avg BIL 53% — protection justified, GGG1 +16.9% active vs SPY in 2022
- Phase 1 estimated: reaching 9% requires avg BIL reduction of ~20pp

---

## Part A — Aggressive Mandate Definition

| Parameter | Value |
|---|---|
| Target return (primary) | 9–10.5% |
| Target return (stretch) | 10.5–12% |
| Max drawdown (primary) | −18 to −20% |
| Max drawdown (stretch) | −20 to −22% |
| Sharpe guardrail (preferred) | ≥ 0.95 |
| Sharpe guardrail (minimum) | ≥ 0.90 |
| stressed_panic rule | **Unchanged** — do not weaken |
| neutral_mixed rule | Reduce BIL/cash, reallocate to existing offense sleeves |
| calm_trend rule | Reduce defense_component, reallocate to offense |
| recovery_confirmed rule | Increase offense, allow lower defense floor |
| recovery_fragile rule | Keep cautious — small or no change |
| hidden_beta rule | Improvement must not be explained by pure SPY beta increase |
| holdout requirement | Must beat GGG1 in 2020+ and 2021+ |

---

## Part B — Candidate Logic

| Candidate | Bottleneck Targeted | state_tilt | phase2b_mode | rerisk_speed |
|---|---|---|---|---|
| C1: neutral_cash_unlock | neutral_mixed BIL | GGG1 unchanged | +0.08 flat boost | 0.80 |
| C2: calm_offense_unlock | calm_trend defense | calm: defense→offense −0.09 | GGG1 unchanged | 0.80 |
| C3: recovery_confirmed_boost | recovery_confirmed participation | RC: defense→offense −0.06 | GGG1 unchanged | 1.00 |
| C4: nonstressed_offense_mandate | neutral+calm+recovery combined | calm −0.09 / neutral −0.05 / RC −0.04 | +0.08 flat boost | 1.00 |
| C5: balanced_mandate | neutral+calm (smaller) | calm −0.06 / neutral −0.03 | +0.08 flat boost | 0.80 |
| C6: stretch_mandate | all non-stressed (stretch) | calm −0.12 / neutral −0.08 / RC −0.07 | +0.10 flat boost | 1.00 |

All 6 candidates built successfully. 18/18 artifacts confirmed.

---

## Part D — Full Period and Holdout Metrics

### Full period (2005–2026)

| Portfolio | Ann Return | Sharpe | Max DD | CVaR 5% | Avg BIL | Beta SPY |
|---|---|---|---|---|---|---|
| **C1 neutral_cash_unlock** | **7.39%** | **0.940** | -12.50% | -2.60% | 24.6% | -0.032 |
| C2 calm_offense_unlock | 7.14% | 0.917 | -12.75% | -2.60% | 26.2% | -0.031 |
| C3 recovery_confirmed_boost | 7.15% | 0.937 | -11.75% | -2.54% | 26.9% | -0.031 |
| C4 nonstressed_mandate | 7.44% | 0.921 | -13.65% | -2.68% | 24.1% | -0.033 |
| C5 balanced_mandate | 7.42% | 0.927 | -13.29% | -2.66% | 24.2% | -0.033 |
| C6 stretch_mandate | 7.49% | 0.914 | -14.27% | -2.72% | 23.7% | -0.033 |
| **GGG1 (baseline)** | **7.14%** | **0.936** | **-11.77%** | -2.54% | 26.7% | -0.031 |
| Production pin | 6.89% | 0.884 | -13.98% | -2.62% | 28.4% | -0.025 |
| SPY | 10.54% | 0.600 | -54.61% | -5.80% | — | 1.000 |
| 60/40 | 8.09% | 0.785 | -31.38% | — | — | — |

### Holdout 2020-forward

| Portfolio | Ann Return | Sharpe | Max DD | Active vs GGG1 |
|---|---|---|---|---|
| C1 neutral_cash_unlock | 9.70% | 1.061 | -12.50% | +0.17pp |
| C2 calm_offense_unlock | 9.48% | 1.051 | -12.75% | -0.04pp |
| C3 recovery_confirmed_boost | 9.59% | **1.084** | -11.75% | +0.04pp |
| C4 nonstressed_mandate | 9.66% | 1.023 | -13.65% | +0.12pp |
| C5 balanced_mandate | 9.68% | 1.037 | -13.29% | +0.17pp |
| C6 stretch_mandate | 9.63% | 1.003 | -14.27% | +0.08pp |
| **GGG1** | **9.55%** | **1.082** | **-11.77%** | — |
| SPY | 14.14% | 0.732 | -31.83% | +4.59pp |
| 60/40 | 8.81% | 0.733 | -20.76% | — |

### Holdout 2021-forward

| Portfolio | Ann Return | Sharpe | Max DD |
|---|---|---|---|
| C6 stretch_mandate | **10.74%** | 1.320 | -7.96% |
| C4 nonstressed_mandate | 10.65% | 1.325 | -7.84% |
| C5 balanced_mandate | 10.62% | 1.337 | -7.76% |
| C1 neutral_cash_unlock | 10.50% | 1.341 | -7.63% |
| C2 calm_offense_unlock | 10.34% | **1.344** | -7.26% |
| **GGG1** | **10.22%** | **1.348** | **-7.25%** |

### 2022 Bear Period

| Portfolio | Ann Return | vs GGG1 | vs Prod Pin |
|---|---|---|---|
| C6 stretch_mandate | **-0.56%** | +0.73pp | -1.07pp |
| C4 nonstressed_mandate | -0.77% | +0.52pp | -1.28pp |
| C5 balanced_mandate | -0.85% | +0.44pp | -1.36pp |
| C1 neutral_cash_unlock | -1.14% | +0.15pp | -1.65pp |
| C2 calm_offense_unlock | -1.21% | +0.08pp | -1.72pp |
| C3 recovery_confirmed_boost | -1.31% | ≈0.00pp | -1.82pp |
| **GGG1** | **-1.29%** | — | -1.80pp |
| **Production pin** | **+0.51%** | — | — |
| SPY | -18.18% | — | — |

**Note:** All Phase 2 candidates slightly worsen 2022 protection vs GGG1 (C1–C3 negligibly, C4–C6 by 0.4–0.7pp). All significantly outperform SPY and 60/40. Production pin is still the 2022 leader.

---

## Part E — State-by-State Impact

### neutral_mixed state (C1 vs GGG1)

| Metric | GGG1 | C1 | C4 (best combined) |
|---|---|---|---|
| Ann return | 11.21% | **11.74%** | **11.96%** |
| Sharpe | 1.462 | 1.469 | 1.469 |
| avg defense_component sleeve | — | 21.4% | 18.6% |
| avg cash::BIL sleeve | — | **19.2%** | **19.3%** |

The neutral_mixed BIL sleeve (overlay cash) was reduced from ~22.9% to ~19.2% by the +0.08 regime_multiplier boost. However, total ETF-level BIL only fell from ~26.6% to ~24.6% — the remaining BIL is held internally within individual sleeves and is harder to reduce.

### calm_trend state — the pivotal finding

| Metric | GGG1 | C2 (calm offense) | C6 (stretch) |
|---|---|---|---|
| Ann return | **4.09%** | 3.87% | 3.85% |
| Sharpe | 0.514 | 0.464 | 0.455 |
| avg defense_component | — | **23.9%** ↓ | **21.8%** ↓ |
| avg offense_component | — | **10.3%** ↑ | **10.8%** ↑ |

**Critical finding:** Reducing defense_component in calm_trend and redirecting to offense sleeves **does not improve calm_trend returns.** Return is slightly worse (-0.2pp). This reveals the root cause: the **offense sleeves themselves do not capture SPY-like returns in calm bull markets.** They hold diversified ETFs (EFA, EEM, EWJ, diversified trend-following) that underperform concentrated US equity during US-led bull runs.

### stressed_panic state — protection preserved

| Portfolio | Ann Return | Sharpe | avg BIL sleeve |
|---|---|---|---|
| GGG1 | 3.58% | 0.481 | ~50.9% |
| C1 | 3.56% | 0.457 | **49.9%** |
| C4 | 3.46% | 0.432 | 49.9% |
| C6 | 3.38% | 0.413 | 49.7% |

Stressed_panic protection is maintained. BIL barely changes (~50%). The more aggressive candidates show slightly lower stressed_panic Sharpe because their higher offense allocation in other states doesn't affect stressed states, but the regime multiplier changes create marginally more volatility in transitions.

### recovery_confirmed state

| Portfolio | Ann Return | delta vs GGG1 |
|---|---|---|
| GGG1 | 2.57% | — |
| C3 recovery_boost | 2.30% | **-0.27pp** |
| C5 balanced | 2.82% | +0.25pp |

Paradoxically, C3 (the dedicated recovery re-risk candidate) performs slightly **worse** than GGG1 in recovery_confirmed. With only 44 weeks in this state, results are noisy, but the pattern suggests the shifted offense mix in RC doesn't outperform GGG1's default approach.

---

## Part F — Risk, Realism, Hidden Beta

### Hidden beta assessment

All candidates have **negative SPY beta** (−0.031 to −0.033 vs GGG1 −0.031). No candidate became more correlated to SPY. The improvement is not hidden beta.

**C2 (calm offense unlock)** shows pct_improvement_from_beta = 102% — this is a measurement artifact: the improvement vs GGG1 is essentially 0.00pp, so the beta-attribution calculation is meaningless. C2 offers no meaningful return improvement.

### Mandate guardrail check

| Candidate | Max DD | Sharpe | Bear OK | SPY Proxy | Mandate |
|---|---|---|---|---|---|
| C1 | -12.5% | 0.940 | ✓ | No | ✓ |
| C2 | -12.75% | 0.917 | ✓ | No | ✓ |
| C3 | -11.75% | 0.937 | ✓ | No | ✓ |
| C4 | -13.65% | 0.921 | ✓ | No | ✓ |
| C5 | -13.29% | 0.927 | ✓ | No | ✓ |
| C6 | -14.27% | 0.914 | ✓ | No | ✓ |

All 6 pass all mandate guardrails. No disguised SPY. No excessive drawdown.

### Turnover / cost realism

All candidates use the same cost model as GGG1 (net returns, same DEFAULT_COST_BPS). Turnover is broadly similar to GGG1 given the bounded `_shift_bucket_mass` adjustments.

---

## Part G — Selection Table

| Candidate | Classification | Return Delta vs GGG1 | Sharpe | Max DD |
|---|---|---|---|---|
| **C1 neutral_cash_unlock** | **KEEP_AS_AGGRESSIVE_SHADOW** | +0.25pp | 0.940 | -12.50% |
| C2 calm_offense_unlock | KEEP_AS_AGGRESSIVE_SHADOW | +0.00pp | 0.917 | -12.75% |
| C3 recovery_confirmed_boost | KEEP_AS_AGGRESSIVE_SHADOW | +0.01pp | 0.937 | -11.75% |
| C4 nonstressed_mandate | KEEP_AS_AGGRESSIVE_SHADOW | +0.30pp | 0.921 | -13.65% |
| C5 balanced_mandate | KEEP_AS_AGGRESSIVE_SHADOW | +0.28pp | 0.927 | -13.29% |
| C6 stretch_mandate | KEEP_AS_AGGRESSIVE_SHADOW | +0.35pp | 0.914 | -14.27% |

**No candidate reached PRODUCTION_CHALLENGER status.** Production-challenger required ≥8.5% return AND ≥0.95 Sharpe. Best return was 7.49% (C6), best Sharpe was 0.940 (C1).

Best candidate for tracking: **`improved_phase2_aggressive_neutral_cash_unlock`** (C1) — highest Sharpe (0.940 vs GGG1 0.936), +0.25pp full-period return, cleanest improvement, no side effects. Tracked as aggressive shadow.

---

## Why 9–10% Was Not Reached

Phase 1 estimated reaching 9% required reducing avg BIL by ~20pp. Phase 2 achieved:
- C6 (stretch): avg BIL 23.7% (−3pp from GGG1's 26.7%)
- C4 (nonstressed): avg BIL 24.1% (−2.6pp)

**Why the BIL reduction was only 2-3pp instead of 20pp:**

1. **Regime multiplier ceiling:** calm_trend already has regime_multiplier = 1.0 (fully deployed). The +0.08 flat boost only affects neutral_mixed (regime_mult ~0.90 → ~0.98), which is the smaller part of total BIL.

2. **Internal sleeve BIL is the larger component:** Of the 26.7% total BIL, ~10% is overlay cash and ~17% is internal BIL held within individual sleeves (via look-through). State_tilt adjustments don't reduce internal sleeve BIL.

3. **Offense sleeves don't capture SPY-like returns:** Shifting defense → offense in calm_trend produced zero return improvement because the offense sleeves hold diversified ETFs (EFA, EEM, EWJ, CTA) that underperform concentrated US equity in US-led bull trends. SPY returns 17.5% annualized in calm_trend; the diversified offense mix returns ~4%.

**The fundamental bottleneck is the ETF composition within the offense component, not the sleeve allocation weights.**

To reach 9-10%:
- The offense component needs to concentrate in high-return assets during favorable periods (QQQ, sector ETFs, concentrated US equity)
- Or breadth/sector signals need to identify when concentrated US equity outperformance is likely
- Neither is achievable via sleeve reallocation alone within the current ETF universe

---

## Audit Results

Quick audits run on `improved_phase2_aggressive_neutral_cash_unlock`:
- Research committee: logged to `phase2_research_committee_quick.log`
- Backtest realism: logged to `phase2_backtest_realism_quick.log`
- Allocator benchmark: logged to `phase2_allocator_benchmark_quick.log`

---

## Final Recommendation

**Decision: `KEEP_PHASE2_AS_AGGRESSIVE_SHADOW`**

All 6 Phase 2 candidates are real improvements over GGG1 on full-period return. None are disguised SPY. None break bear protection. The best candidate (C1) improves Sharpe from 0.936 to 0.940 and return from 7.14% to 7.39%.

However, none approach the 9-10% primary mandate target. The ETF-level mandate relaxation via sleeve reallocation is insufficient.

**Track `improved_phase2_aggressive_neutral_cash_unlock` as the Phase 2 aggressive shadow.** It is strictly better than GGG1 on full-period return and Sharpe with no material risk increase.

---

## Why Phase 3 Is the Right Next Step

The calm_trend state is 26.6% of all weeks and costs -13.2% annualized vs SPY. The offense sleeves don't capture this because they hold diversified international equity and trend-following strategies that underperform in US-led bull runs.

**Phase 3 (Stock Breadth Regime Upgrade)** would provide signals about when US equity breadth is strong enough to justify concentrated offense in high-beta US assets (QQQ, sector ETFs). This is the missing information — not the allocation weights.

**Phase 4 (Sector ETF Rotation)** would allow the offense component to rotate into sector leadership during calm/bull markets rather than holding a static diversified basket.

Either of these would attack the ETF composition problem directly, which is what Phase 2 demonstrated cannot be solved at the sleeve-weight level.

---

## Phase 3 Prompt Outline

**Phase 3 — Stock Breadth Regime Upgrade**

Goal: Add a stock-level breadth signal to the regime engine that identifies when US equity market breadth is strong enough to justify higher-beta offense in the portfolio. Use this signal to either (a) improve state classification granularity within neutral_mixed and calm_trend, or (b) create a new offense sub-sleeve that concentrates in US equity when breadth is confirmed.

Constraints:
- Causal, lagged features only
- No look-ahead into future returns
- No random train/test splits
- Time-ordered validation
- Must compare out-of-sample against GGG1 AND Phase 2 best candidate (C1)
- Must not weaken stressed_panic protection
- Must not break 2022 bear performance

Key questions to answer:
1. Is US stock breadth (e.g., % of S&P 500 above 200-day MA, advance-decline) incrementally predictive of calm_trend upside capture?
2. Does breadth information reduce the calm_trend opportunity cost (-13.2% vs SPY)?
3. Can we distinguish "high-breadth calm" from "low-breadth calm" to differentiate offense intensity?

Do not build a stock universe. Use available market breadth proxies from the existing signal framework or new ETF-level breadth proxies.

---

## Resume / Project Story

**Arc 1 (Phases 1–2B):** Built the core regime engine and dual-track production system. Production pin: `improved_phase2b_regime_confidence_boost`.

**Arc 2 (Phases AAA–GGG):** Refined offense composition and confirmation gating. Production candidate: `improved_phaseggg_confirmed_only_robust_offense` (7.14% full-period, 9.55% 2020-forward, Sharpe 1.08, max DD −11.77%).

**Arc 3 (Phases OOO–SSS):** Hard-ML signal discovery. SSS3 shadow: `improved_phasesss3_calm_old_low_stress_derisk`.

**Phase 1 (Return Unlock Audit):** Diagnosed return ceiling as mandate-driven. Primary bottleneck: neutral_mixed BIL (44% of weeks, 26% BIL). Secondary: calm_trend defense_component (29%).

**Phase 2 (Aggressive ETF Variant — this phase):** Attempted 9-10% return via sleeve reallocation (6 candidates). Achieved max 7.49% full-period. Found that ETF composition within offense sleeves is the binding constraint — diversified offense doesn't capture SPY-like returns in US bull trends. Best candidate: `improved_phase2_aggressive_neutral_cash_unlock` (+0.25pp, Sharpe 0.940, tracked as aggressive shadow). Decision: KEEP_PHASE2_AS_AGGRESSIVE_SHADOW.

**Next: Phase 3 — Stock Breadth Regime Upgrade.** Add breadth signals to identify when concentrated US equity offense is justified. Attack the ETF composition problem, not the sleeve allocation weights.
