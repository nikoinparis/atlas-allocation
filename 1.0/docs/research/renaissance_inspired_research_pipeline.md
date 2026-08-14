# Renaissance-Inspired Research Pipeline for the ETF Quant Portfolio Project

**Date:** 2026-05-18  
**Type:** Research design document. No implementation yet.

---

## Overview

This document proposes a formalized research pipeline for the ETF portfolio project, inspired by what is publicly known about Renaissance Technologies' research culture and extended by published academic methodology (López de Prado 2018, AQR, statistical arbitrage literature).

The pipeline is designed to:
1. Systematically discover and validate new signals without overfitting
2. Test every idea against the same acceptance battery
3. Maintain a clean research log so no idea is re-tested without documentation
4. Integrate cleanly with the existing Layer 1 → Layer 2B → Layer 3 architecture

This is a *process* document. It does not replace the existing audit scripts (`backtest_realism_audit.py`, `research_committee_report.py`). It adds upstream discipline to signal discovery.

---

## Current Pipeline Gaps (vs Renaissance Principles)

| Gap | Evidence | Impact |
|-----|---------|--------|
| No signal decay half-life estimate | `signal_ic_by_horizon.csv` exists but decay rate not characterized | Risk of using signals that are dead at the actual rebalancing horizon |
| No regime-conditional IC | `signal_state_summary.csv` exists but ICs not broken out within regime × signal | Missing the strongest use of the regime engine |
| No formal idea intake / pre-registration | No signal_research_log.md | Risk of unconscious cherry-picking |
| No explicit orthogonality enforcement at intake | Redundancy matrix computed but not used as a gate | New signals silently add redundant exposure |
| No per-ETF transaction cost model | Flat 10bps assumption for all ETFs | Overstates net edge for high-spread ETFs |
| No pairs / cointegration signal family | Signal library is entirely momentum + factor proxy | Structural gap in calm_trend state |
| No volume-based signals | Volume data available but not in signal manifest | Missing a whole dimension of market data |

---

## Phase R0 — Infrastructure (Pre-Existing, Confirm Status)

**Goal:** Confirm that all existing infrastructure is working and documented before adding anything new.

### Files to confirm exist and are current

```
data/02_layer1_signals/signal_manifest.json          ← signal registry
data/02_layer1_signals/signal_ic_by_horizon.csv      ← IC across horizons
data/02_layer1_signals/signal_redundancy_matrix.csv  ← pairwise redundancy
data/02_layer1_signals/signal_incremental_contribution.csv ← marginal Sharpe test
data/02_layer1_signals/signal_summary_table.csv      ← composite score per signal
data/04_layer2b_risk_regime_engine/market_state_history.csv ← regime labels
data/01_data_hub/macro_weekly.csv                    ← macro features
data/01_data_hub/vix_term_structure.csv              ← VIX term structure
```

### Acceptance test for R0

- All files above are ≤30 days stale (re-run signal scripts if needed)
- `signal_manifest.json` has entries for all 22 tracked signals
- No signals in `signal_summary_table.csv` with missing NW t-stat

---

## Phase R1 — Signal Research Log Initialization

**Goal:** Create the research log that documents every idea (tested or not).

### File to create

`docs/research/signal_research_log.md`

### Format

Each entry:

```markdown
### Signal: [name] — [date]
- **Hypothesis:** [brief economic story, if any; "empirical only" if none]
- **Category:** [momentum / reversal / carry / value / quality / macro / breadth / sentiment / pairs]
- **Data sources:** [existing vs new]
- **Pre-registered acceptance gate:** IC NW t-stat ≥ 2.0 full-period + holdout IC positive
- **Result:** [Promoted / Research-only / Rejected]
- **Key metrics:** IC = X, NW t-stat = Y, redundancy with closest signal = Z
- **Decision reason:** [1-2 sentences]
- **Reject-if:** [what would cause this idea to be dropped in future]
```

### Acceptance test for R1

- Log initialized with all 22 existing signals entered
- Retrospective entries use existing signal_summary_table.csv data
- Template committed to repo

---

## Phase R2 — Expanded Signal Zoo (Free Data, No Paid Data)

**Goal:** Add 6–10 orthogonal signals from free/existing data sources. Each must pass the full IC battery before entering the signal manifest.

### Candidate signals to research and test

#### R2.1 — Yield Curve Carry Signal

**Data:** FRED FEDFUNDS rate, DGS10 (10Y yield), DGS2 (2Y yield) — all free  
**Signal definition:** `(DGS10 - DGS2)` as 1-week change and level; rank ETFs by duration exposure  
**Hypothesis:** Flattening/inverted curve → reduce equity/credit; steepening → increase equity/EM  
**Expected IC horizon:** 4–8 weeks (macro signal, slow decay)  
**Redundancy risk:** Low — not represented in current library

#### R2.2 — Credit Spread Signal

**Data:** FRED `BAMLH0A0HYM2` (ICE BofA HY OAS) — free  
**Signal definition:** 4-week change in HYG OAS level; z-score vs trailing 52w mean  
**Hypothesis:** Widening spreads → risk-off; tightening → risk-on  
**Expected IC horizon:** 4–13 weeks  
**Redundancy risk:** Low — HYG return is in the price universe, but OAS level is not the same signal

#### R2.3 — VIX Term Structure Signal (convert existing data)

**Data:** `data/01_data_hub/vix_term_structure.csv` — already fetched  
**Signal definition:** Front-month VIX / back-month VIX (contango vs backwardation)  
**Hypothesis:** VIX contango (front < back) = calm regime confirmation; backwardation = stress  
**Expected IC horizon:** 2–4 weeks  
**Redundancy risk:** Medium — VIX level is partially captured in regime engine; term structure adds information

#### R2.4 — Dollar Strength Signal

**Data:** UUP weekly return (already in universe)  
**Signal definition:** UUP 13w and 26w momentum; z-score vs cross-asset momentum  
**Hypothesis:** USD strength → EM headwind (EEM, VWO underperform); risk-off signal globally  
**Expected IC horizon:** 4–13 weeks  
**Redundancy risk:** Medium — not explicitly tested; UUP is in universe but not a standalone signal  

#### R2.5 — Commodity Momentum Signal

**Data:** PDBC, USO, DBA, SLV weekly returns (all in universe)  
**Signal definition:** PDBC 26w momentum; blended commodity carry proxy  
**Hypothesis:** Strong commodity momentum → inflation regime; favor TIP, XLE, XLB vs TLT  
**Expected IC horizon:** 4–13 weeks  
**Redundancy risk:** Low — `carry_proxy` partially captures this; dedicated commodity signal adds resolution

#### R2.6 — ETF Volume Divergence Signal

**Data:** yfinance daily volume for all 35 ETFs; resample to weekly  
**Signal definition:** Weekly price return × sign vs volume surprise (price up + volume below 52w mean = weak signal; price down + volume above 52w mean = strong distribution)  
**Hypothesis:** High-volume price declines = genuine selling; low-volume rallies = weak breadth  
**Expected IC horizon:** 1–4 weeks (fast decay — requires tight timing)  
**Redundancy risk:** Low — no volume signals currently in the library

#### R2.7 — FRED Financial Conditions Signal

**Data:** FRED National Financial Conditions Index (NFCI) — weekly, free  
**Signal definition:** NFCI level z-score + 4w change  
**Hypothesis:** Tightening financial conditions → reduce equity offense; loosening → expand  
**Expected IC horizon:** 4–8 weeks  
**Redundancy risk:** Low — composite macro signal not in current library

#### R2.8 — Cross-Asset Divergence Signal

**Data:** Existing ETF return data  
**Signal definition:** SPY 4w return rank vs HYG 4w return rank; large divergence (SPY up, HYG down) = latent stress; (SPY down, HYG up) = early recovery  
**Hypothesis:** When credit and equity diverge, the asset leading tends to be correct about regime direction  
**Expected IC horizon:** 2–4 weeks  
**Redundancy risk:** Low — explicitly cross-asset; not captured in individual momentum signals

### Scripts to create

```
scripts/build_macro_signal_library.py
    → fetch FRED yield curve + credit spread + NFCI + recession probability
    → compute signals R2.1, R2.2, R2.7
    → save to data/02_layer1_signals/signal_{name}.csv

scripts/build_vix_term_structure_signal.py
    → load existing vix_term_structure.csv
    → compute front/back ratio and term-structure slope signal
    → save to data/02_layer1_signals/signal_vix_ts.csv

scripts/build_volume_divergence_signal.py
    → download weekly volume from yfinance (or use expanded_universe pipeline)
    → compute price × volume divergence per ETF
    → save to data/02_layer1_signals/signal_volume_divergence.csv

scripts/run_r2_signal_validation.py
    → run all R2 signals through the existing IC battery
    → compute NW t-stat, redundancy, state-conditional IC
    → save to data/02_layer1_signals/r2_signal_validation_results.csv
    → produce docs/research/r2_signal_validation_report.md
```

### Acceptance tests for R2

- Each signal passes IC NW t-stat ≥ 2.0 or is marked "Research only"
- Pairwise redundancy with existing strong signals ≤ 0.50
- Holdout IC (2020+) positive with p ≤ 0.20
- No signal adds losses in `stressed_panic` state

---

## Phase R3 — Signal Decay Testing

**Goal:** Characterize the IC half-life of every signal in the library and use this to assign rebalancing-appropriate weights.

### Scripts to create

```
scripts/run_signal_decay_analysis.py
    → for each signal: fit exponential decay model to IC-by-horizon curve
    → estimate half-life (horizon at which IC falls to 50% of 1-week IC)
    → classify signals: fast (< 2w), medium (2-6w), slow (> 6w)
    → flag fast-decaying signals as "requires daily/daily-lag refresh"
    → save decay profiles to data/02_layer1_signals/signal_decay_profiles.csv
    → produce docs/research/signal_decay_report.md
```

### Outputs

`data/02_layer1_signals/signal_decay_profiles.csv` — decay half-life per signal  
`docs/research/signal_decay_report.md` — which signals work at weekly rebalancing

### Acceptance tests for R3

- All 22 existing signals have a decay profile
- Signals with half-life < 2 weeks are flagged as "not viable for weekly rebalancing"
- Signals with half-life ≥ 3 weeks are prioritized for the Layer 1 ensemble

### Reasons to reject/skip

- If all signals have half-life > 3 weeks: decay testing adds no new information; skip
- If the IC-by-horizon data has too few points to fit a decay curve: report the limitation

---

## Phase R4 — State-Conditional IC Testing

**Goal:** Identify which signals have the highest IC *specifically within calm_trend* and *within stressed_panic*. Use this to build regime-conditional signal weights.

### Scripts to create

```
scripts/run_state_conditional_signal_ic.py
    → for each signal × state × horizon: compute IC, NW t-stat, hit rate
    → identify signals with IC > 0.08 in calm_trend (high-value state)
    → identify signals with IC > 0.10 in recovery_fragile/confirmed
    → identify any signals with IC < -0.05 in stressed_panic (dangerous signals)
    → save to data/02_layer1_signals/signal_state_conditional_ic.csv
    → produce docs/research/state_conditional_signal_report.md
```

### Key hypothesis to test

*Signals with high IC in calm_trend* are the most valuable new signals — they directly address the primary portfolio bottleneck. If yield curve flattening or VIX term structure or cross-asset divergence shows IC > 0.08 in calm_trend, it becomes a high-priority candidate for a calm_trend-specific sleeve override.

### Acceptance tests for R4

- At least one signal shows IC ≥ 0.08 in calm_trend with NW t-stat ≥ 1.5
- No promoted signal shows IC < -0.05 in stressed_panic
- Report documents state-conditional ICs for all 22+ signals

---

## Phase R5 — ETF Pairs / Statistical Arbitrage Lab

**Goal:** Test whether cointegration-based pairs signals between ETFs can provide an orthogonal signal source, particularly for the calm_trend state.

### Pairs to test

Priority pairs based on economic structure:
```
1. SPY / QQQ        — large cap vs mega-cap tech premium
2. IWM / SPY        — small vs large cap value spread
3. TLT / SPY        — duration vs equity yield spread
4. GLD / TLT        — real vs nominal safe haven spread
5. XLE / USO        — energy equity vs commodity basis
6. HYG / LQD        — high-yield vs investment-grade credit spread
7. EEM / SPY        — EM vs US equity premium
8. XLK / QQQ        — tech sector vs tech-heavy index (basis)
```

### Scripts to create

```
scripts/build_etf_pairs_signals.py
    → test each pair for cointegration (Engle-Granger test)
    → estimate half-life of mean reversion (Ornstein-Uhlenbeck fit)
    → compute z-score of spread vs rolling mean/std (52w window)
    → lag 1 week before testing
    → test IC at 1, 2, 4 week horizons
    → test state-conditional IC (expect high IC in calm_trend)
    → save signals to data/02_layer1_signals/signal_etf_pairs_{pair}.csv
    → produce docs/research/etf_pairs_signal_report.md
```

### Constraints

- All pairs signals must use lagged data (z-score at t-1 predicts return at t)
- Half-life filter: only use pairs with OU half-life of 2–10 weeks (too fast = noise; too slow = not useful at weekly rebalancing)
- Cointegration must be confirmed over training period; reject pairs where cointegration fails the ADF test
- No pairs signals in production without state-conditional IC test first

### Acceptance tests for R5

- At least one pair shows IC ≥ 0.06 with NW t-stat ≥ 1.8 full-period
- At least one pair shows positive IC in calm_trend
- OU half-life 2–10 weeks (mean reversion is observable at weekly frequency)

### Reasons to reject

- No pairs pass the cointegration test over 2005–2015 training period
- All pairs IC NW t-stats < 1.5
- Pairs signals are highly correlated with existing momentum signals (> 0.50 redundancy)

---

## Phase R6 — Better Data Audit and PIT Breadth Preparation

**Goal:** Document the exact data gaps and cost estimates for the next data acquisition decision.

### Scripts to create (analysis only)

```
scripts/run_data_quality_audit.py
    → enumerate all data sources currently in use
    → identify missing signal families (yield curve, credit, volume, breadth)
    → estimate data acquisition cost for PIT stock breadth
    → produce docs/research/data_quality_audit_report.md
```

### Key audit questions

1. What is the current coverage of `macro_weekly.csv`? Which macro series are included?
2. Is the VIX term structure data being used as a signal or just stored?
3. What Google Trends series are available and have they been validated as signals?
4. Is Sharadar viable as a lower-cost PIT alternative to Norgate?

### Acceptance tests for R6

- Full data inventory completed with source, cost, frequency, and bias risk
- Gap analysis identifies at least 5 new data series that are free and immediately actionable
- PIT stock breadth cost estimate documented

---

## Phase R7 — Ensemble Signal Weighting and Meta-Labeling

**Goal:** Test whether IC-weighted signal combination or meta-labeling improves the ensemble Sharpe vs the current approach.

### Scripts to create

```
scripts/run_ic_weighted_ensemble.py
    → compare IC-weighted vs equal-weight vs current HRP ensemble
    → use rolling 104-week IC estimates (walk-forward safe)
    → produce full-period and holdout metrics
    → produce docs/research/ic_weighted_ensemble_report.md

scripts/run_state_regime_meta_model.py
    → train a secondary classifier on regime state × signal IC patterns
    → predict: in this week's state, which signals are likely to be correct?
    → use meta-classifier confidence to scale signal weights
    → validate on holdout (2020+) with bootstrap
    → produce docs/research/meta_model_confidence_report.md
```

### Constraints

- Rolling IC estimates must use only past data (no future IC peeking)
- Meta-model trained on training period only (2005–2018); tested on 2019–2026
- Report must clearly state if the improvement is within bootstrap confidence intervals

### Acceptance tests for R7

- IC-weighted ensemble Sharpe ≥ equal-weight ensemble Sharpe on holdout (not just full period)
- Meta-model improvement ≥ +0.02 Sharpe on holdout
- Both tested with block bootstrap (13-week blocks, 1000+ iterations)

### Reasons to reject

- IC-weighted ensemble underperforms on holdout (possible overfitting to historical IC)
- Meta-model confidence is not stable across subperiods (regime-conditional ICs too noisy with low N)

---

## Phase R8 — Final Comparison Against Production Baseline

**Goal:** After all R1–R7 phases, run a comprehensive comparison of the improved signal library and ensemble against the current production baseline and shadows.

### Output

`docs/research/renaissance_pipeline_final_comparison_report.md`

### Format

Structured like existing phase reports: full-period and holdout metrics vs:
- Production pin (`improved_phase2b_regime_confidence_boost`)
- Production candidate (`improved_phaseggg_confirmed_only_robust_offense`)
- Best shadow (`improved_phase4b_refined_sector_20pct`)
- Phase 7 stretch (`improved_phase7_stretch_target`)

### Acceptance tests for R8

- New ensemble does not worsen 2022 bear period protection by more than 1 pp
- Sharpe improvement ≥ +0.01 on 2020+ holdout
- Max drawdown within −2 pp of best current shadow

---

## How the Pipeline Fits the Current Architecture

```
CURRENT ARCHITECTURE:
  Layer 1 (signals) → Layer 2 (sleeves) → Layer 2B (regime engine) → Layer 3 (HRP construction)

WHERE EACH PHASE FITS:
  R2 (signal zoo)    → Layer 1 (new signal files in data/02_layer1_signals/)
  R3 (decay testing) → Layer 1 diagnostic (informs which signals to use in Layer 2)
  R4 (state IC)      → Layer 2B interface (regime × signal interaction)
  R5 (ETF pairs)     → Layer 1 (new pairs signals alongside momentum signals)
  R7 (ensemble)      → Layer 2 (how signals are combined before Layer 3)
  R8 (comparison)    → Layer 3 evaluation (full portfolio-level test)

NOTHING in R1–R8 touches:
  → scripts/build_improvement_artifacts.py (unchanged)
  → portfolio_version_* artifacts (unchanged)
  → production pins / dashboard (unchanged)
  → Phase 4B/6/7 candidates (unchanged)
```

---

## Research Calendar (Suggested)

| Phase | Estimated sprint time | Prerequisites | Risk |
|-------|----------------------|---------------|------|
| R0 | 1 day | None | Very low |
| R1 | 1 day | R0 | Very low |
| R2 | 3–5 days | R1 | Medium (signal IC may not pass) |
| R3 | 1 day | R2 | Low |
| R4 | 2 days | R2, R3 | Medium (state N is small) |
| R5 | 3–4 days | R1 | Medium (pairs may not cointegrate) |
| R6 | 1 day | None | Very low |
| R7 | 3–5 days | R2–R5 | High (meta-labeling overfitting risk) |
| R8 | 2 days | All above | Low (evaluation only) |

**Total: ~15–20 sprint days** to execute the full pipeline. Each phase produces a standalone report and can be stopped at any point.
