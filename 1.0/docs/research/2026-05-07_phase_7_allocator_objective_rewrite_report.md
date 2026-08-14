# Phase 7 — Allocator Objective Rewrite

**Date:** 2026-05-07
**Type:** Strategy research. No production pins changed. No auto-promotion.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense`
**Phase 4B shadow:** `improved_phase4b_refined_sector_20pct` (7.76% / 0.959 Sharpe)
**Phase 6 shadow:** `improved_phase6_continuous_aggression_score` (7.80% / 0.953 Sharpe)

---

## Permission Change

Before running, the `python3 scripts/*` deny rule was narrowed:

**Removed from deny:** `"Bash(python3 scripts/*)"`

**Added to allow (5 specific entries only):**
- `"Bash(python3 scripts/phase_7_allocator_objective_rewrite.py)"`
- `"Bash(python3 scripts/research_committee_report.py*)"`
- `"Bash(python3 scripts/backtest_realism_audit.py*)"`
- `"Bash(python3 scripts/allocator_benchmark_audit.py*)"`
- `"Bash(python3 scripts/robustness_simulation_audit.py*)"`

No other scripts are broadly allowed. All other deny rules (rm, mv, cp, git push/add/commit, pip/npm install) preserved.

---

## Commands Executed

```
python3 scripts/phase_7_allocator_objective_rewrite.py
```

**Build command (internal):**
```
BUILD_VERSION_NAMES='improved_phase7_*' python3 scripts/build_improvement_artifacts.py
```

**Audits run (best candidate — KEEP_AS_AGGRESSIVE_SHADOW):**
```
python3 scripts/research_committee_report.py improved_phase7_stretch_target --quick  → PASS
python3 scripts/backtest_realism_audit.py improved_phase7_stretch_target --quick     → PASS
python3 scripts/allocator_benchmark_audit.py improved_phase7_stretch_target --quick  → PASS
```

---

## Files Created / Modified

**Scripts modified:** `scripts/build_improvement_artifacts.py` — added `phase7_aggressive_expression` layer3 mode, 5 Phase 7 `state_tilt` modes, 5 version specs

**New script:** `scripts/phase_7_allocator_objective_rewrite.py`

**Outputs (24 files in `data/research/phase_7_allocator_objective_rewrite/`):**
designs, build log, metrics, holdout metrics, benchmark table, state summary, state deltas, stress/calm diagnostics, risk/hidden beta, selection, audits, decision, protocol

**Candidate artifacts (15 files in `data/05_layer3_portfolio_construction/`):**
5 × returns/weights/sleeve_weights

---

## What Phase 7 Tests

Three levers applied to Phase 4B best as the base:

1. **Larger sector sleeve budget** — 28% (C1, C3, C4) or 32% (C5) vs Phase4B's 20%
2. **More aggressive layer3 expression** — `shift_budget=0.12` in calm_trend vs 0.06; reallocates within the risky budget from defense to offense
3. **Faster reallocation** — `sleeve_reallocation_speed` up to 0.70, `rerisk_speed=1.0`

---

## Full Period Metrics (2005–2026)

| Portfolio | Ann Return | Sharpe | Max DD | Avg Sector | Avg Defense | vs Phase4B | vs Phase6 |
|---|---|---|---|---|---|---|---|
| **C5 stretch_target** | **7.88%** | 0.926 | -15.28% | 15.6% | 17.2% | **+0.12pp** | **+0.07pp** |
| C3 max_sector_rerisk | 7.84% | 0.941 | -14.59% | 13.8% | 18.0% | +0.08pp | +0.04pp |
| C1 larger_sector_calm | 7.83% | 0.939 | -14.59% | 14.0% | 18.0% | +0.07pp | +0.02pp |
| C4 combined_offensive | 7.81% | 0.935 | -14.65% | 13.9% | 18.0% | +0.05pp | +0.00pp |
| C2 expression_boost | 7.74% | **0.954** | **-13.83%** | 10.0% | 19.9% | -0.02pp | -0.07pp |
| **Phase4B best** | **7.76%** | **0.959** | **-13.77%** | 10.0% | — | — | — |
| Phase6 best | 7.80% | 0.953 | -14.18% | 11.4% | — | +0.04pp | — |
| GGG1 | 7.14% | 0.936 | -11.77% | — | — | — | — |
| SPY | 10.54% | 0.600 | -54.61% | — | — | — | — |

---

## Holdout Metrics

### 2020-forward

| Portfolio | Ann Return | Sharpe | Max DD | vs Phase4B |
|---|---|---|---|---|
| Phase3 best | 9.94% | **1.124** | -11.90% | +0.31pp |
| **C2 expression_boost** | 9.57% | **1.010** | -13.83% | **+0.01pp** |
| Phase4B best | 9.56% | 1.012 | -13.77% | — |
| C5 stretch_target | 9.49% | 0.947 | -15.28% | -0.07pp |
| GGG1 | 9.55% | 1.082 | -11.77% | -0.01pp |

### 2021-forward

| Portfolio | Ann Return | Sharpe | vs Phase4B |
|---|---|---|---|
| C5 stretch | **10.81%** | 1.236 | +0.15pp |
| C4 combined | 10.77% | 1.258 | +0.09pp |
| Phase4B best | 10.71% | 1.303 | — |
| GGG1 | 10.22% | 1.348 | -0.49pp |

### 2022 Bear Period

| Portfolio | Ann Return | vs Phase4B |
|---|---|---|
| C2 expression_boost | **-1.62%** | -0.09pp |
| C1 larger_sector | -1.66% | -0.13pp |
| **Phase4B best** | **-1.52%** | — |
| C5 stretch_target | -1.94% | **-0.40pp** |
| Production pin | **+0.51%** | +2.03pp |
| GGG1 | -1.29% | +0.23pp |
| SPY | -18.18% | -16.66pp |

C5 (stretch) shows the largest 2022 degradation (-0.40pp vs Phase4B) but remains within mandate (>Phase4B − 4pp tolerance). All candidates far outperform SPY.

### 2023+ Recovery

C2 (expression_boost) leads all Phase 7 candidates in recovery (14.19%, Sharpe 1.645), edging Phase4B (14.09%, Sharpe 1.644). C5 stretch lags slightly (13.60%).

---

## State-by-State Diagnosis

### calm_trend — persistent bottleneck

| Portfolio | Ann Return | Sharpe | Avg Sector | Avg Defense |
|---|---|---|---|---|
| C2 expression_boost | **4.37%** | **0.506** | 18.5% | 22.5% |
| Phase4B best | 4.39% | **0.510** | 18.5% | — |
| C5 stretch_target | 4.21% | 0.450 | **29.7%** | 17.3% |
| GGG1 | 4.09% | 0.514 | — | — |

**Critical finding:** Pushing the sector sleeve from 18.5% to 29.7% in calm_trend (C5) makes calm_trend performance **worse** (4.21% vs 4.39%). The sector ETFs (XLK, XLF, etc.) do not deliver higher annualized returns in calm_trend than the diversified Phase4B defense + momentum mix. The sector sleeve's value comes from concentrated exposure to sector leadership, which doesn't systematically outperform the diversified base in the highest-momentum calm weeks.

### stressed_panic — protection preserved

| Portfolio | Ann Return | Sharpe | Avg BIL |
|---|---|---|---|
| C5 stretch_target | 3.83% | 0.494 | 52.2% |
| Phase4B best | 3.82% | 0.499 | ~50.9% |
| GGG1 | 3.58% | 0.481 | ~50.9% |

BIL in stressed_panic remains ~52% across all Phase 7 candidates — protection unchanged.

### recovery_confirmed — Phase 7's strongest win

C5 delta vs Phase4B in recovery_confirmed: **+1.01pp**. The larger sector sleeve allocation in recovery_confirmed contributes meaningfully. However, recovery_confirmed is only 4% of all weeks (44 weeks total), so the portfolio-level contribution is limited.

### Phase 7 stretch state deltas vs Phase4B

| State | Delta |
|---|---|
| neutral_mixed | **+0.26pp** |
| calm_trend | **−0.18pp** |
| stressed_panic | +0.02pp |
| recovery_fragile | +0.24pp |
| recovery_confirmed | **+1.01pp** |

---

## Risk, Realism, Hidden Beta

All candidates: **no disguised SPY** (beta ≈ −0.033, all negative). All pass mandate guardrails. All bear protection within tolerance.

| Candidate | Beta SPY | Hidden Beta | Mandate | Bear OK |
|---|---|---|---|---|
| C1-C5 | −0.033 to −0.034 | LOW | OK | OK |

The return improvement is not driven by SPY-like risk. It comes from:
1. **Larger sector sleeve** → more concentrated equity ETF exposure (still diversified across sectors)
2. **Faster reallocation speed** → quicker deployment in improving market conditions
3. **Expression shift** → more weight in offense vs defense in the risky budget

---

## Audit Results (C5 — KEEP_AS_AGGRESSIVE_SHADOW)

- Research committee: **PASS**
- Backtest realism: **PASS**
- Allocator benchmark: **PASS**

---

## Selection Table

| Candidate | Classification | Return | Sharpe | Max DD |
|---|---|---|---|---|
| **C5 stretch_target** | **KEEP_AS_AGGRESSIVE_SHADOW** | **7.88%** | 0.926 | -15.28% |
| C3 max_sector_rerisk | KEEP_AS_AGGRESSIVE_SHADOW | 7.84% | 0.941 | -14.59% |
| C1 larger_sector_calm | KEEP_AS_AGGRESSIVE_SHADOW | 7.83% | 0.939 | -14.59% |
| C4 combined_offensive | KEEP_AS_AGGRESSIVE_SHADOW | 7.81% | 0.935 | -14.65% |
| C2 expression_boost | KEEP_AS_AGGRESSIVE_SHADOW | 7.74% | **0.954** | **-13.83%** |

**Best return candidate: `improved_phase7_stretch_target`** (7.88%, Sharpe 0.926)
**Best Sharpe candidate: `improved_phase7_expression_boost`** (7.74%, Sharpe 0.954)
**Overall best Sharpe across all phases: `improved_phase4b_refined_sector_20pct`** (7.76%, Sharpe 0.959)

---

## Why 8.0% Was Not Reached — Final Diagnosis

After 7 phases of systematic existing-data optimization:

| Phase | Best return | Sharpe | Improvement |
|---|---|---|---|
| GGG1 baseline | 7.14% | 0.936 | — |
| Phase 2 | 7.39% | 0.940 | +0.25pp |
| Phase 3 | 7.27% | 0.966 | +0.13pp (vs GGG1) |
| Phase 4B | 7.76% | 0.959 | +0.62pp |
| Phase 6 | 7.80% | 0.953 | +0.66pp |
| **Phase 7** | **7.88%** | 0.926 | **+0.74pp** |

Total progress: +0.74pp over 7 phases. Gap to 8.0%: **0.12pp**.

The 0.12pp gap cannot be closed with existing data because:

1. **Calm_trend (26.6% of weeks) is the structural constraint.** More sector allocation in calm_trend hurts performance — the sector ETFs don't deliver superior returns vs the diversified Phase4B mix in quiet US bull markets. They do better in recovery and selective neutral periods.

2. **The Sharpe-return tradeoff is steepening.** Phase4B achieves 7.76% / 0.959 Sharpe. Phase7 stretch achieves 7.88% / 0.926 Sharpe. Each additional pp of return costs ~3.3 points of Sharpe.

3. **The missing signal is stock-level breadth quality in calm_trend.** The Phase 5A-Free diagnostic confirmed that stock breadth (% above 200d MA, positive 13w return) shows +0.517% per 4-week lift in calm_trend. This signal is not available without PIT data.

---

## Final Recommendation: `KEEP_PHASE7_AS_AGGRESSIVE_SHADOW`

Best return shadow: **`improved_phase7_stretch_target`** (7.88% / 0.926)
Best Sharpe shadow: **`improved_phase4b_refined_sector_20pct`** (7.76% / 0.959)

**The existing-data improvement arc is now complete.** Seven phases of optimization moved full-period return from 7.14% to 7.88% (+0.74pp). The remaining 0.12pp gap to 8.0% requires PIT stock breadth data.

---

## Next Phase: `RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE`

When Norgate Data US Stocks Platinum/Diamond becomes available:
1. Export S&P 500 PIT constituents + daily adjusted prices back to 2005
2. Save to `data/stock_breadth/raw/` using the real filenames (not `_TEMPLATE`)
3. Run: `python3 scripts/build_pit_stock_breadth_panel.py`
4. Validate leakage and coverage
5. Build Phase 5B candidates using stock breadth as an additional classifier signal for calm_trend and recovery_confirmed states

The Phase 5A-Free diagnostic already showed that stock breadth adds +0.517% per 4-week SPY lift in calm_trend. With full 2005-2026 PIT history, the production portfolio targeting 8.0%+ is within reach.

---

## Cumulative Aggressive Shadow Stack (Final)

| Strategy | Full Return | Sharpe | Best use |
|---|---|---|---|
| `improved_phase7_stretch_target` | **7.88%** | 0.926 | Best return |
| `improved_phase7_max_sector_rerisk` | 7.84% | 0.941 | Return + moderate risk |
| `improved_phase6_continuous_aggression_score` | 7.80% | 0.953 | Return + better Sharpe |
| `improved_phase4b_refined_sector_20pct` | 7.76% | **0.959** | **Best risk-adjusted** |
| `improved_phase3_high_breadth_calm_us_offense` | 7.27% | **0.966** | Best 2020+ Sharpe |

---

## Git Status

`scripts/build_improvement_artifacts.py` modified. `scripts/phase_7_allocator_objective_rewrite.py` new. All outputs untracked. Nothing staged. No production files touched.
