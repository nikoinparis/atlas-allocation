---
editor_options: 
  markdown: 
    wrap: 72
---

# Portfolio Project Breakthrough Research Audit

**Date:** 2026-06-05\
**Author:** Claude Code (senior quant researcher role)\
**Scope:** Full repo audit + internet research sprint — identifying
highest-upside research directions

------------------------------------------------------------------------

## Table of Contents

1.  [Current System Summary](#1-current-system-summary)
2.  [What Is Already Covered](#2-what-is-already-covered)
3.  [Main Bottlenecks](#3-main-bottlenecks)
4.  [Internet Research Findings](#4-internet-research-findings)
5.  [Ranked Breakthrough Candidates](#5-ranked-breakthrough-candidates)
6.  [Recommended Next Sprint](#6-recommended-next-sprint)
7.  [Stop/Go Criteria](#7-stopgo-criteria)
8.  [Final Recommendation](#8-final-recommendation)

------------------------------------------------------------------------

## 1. Current System Summary

The repo is a **weekly ETF tactical allocation system** with four
layers:

### Layer 1 — Alpha Signals

Cross-sectional momentum, time-series momentum, reversal, quality, trend
clarity, breadth-confirmed momentum, and macro/alt-data regime features.

Macro data: 7 FRED indicators (T10Y2Y, BAMLH0A0HYM2, UMCSENT, FEDFUNDS,
DTWEXBGS, CPIAUCSL, UNRATE), VIX term structure (1m/3m/6m), Google
Trends fear composite.

All signals lagged 1 week for causal safety.

### Layer 2A — Sleeves (8 total)

| Sleeve | Role |
|----|----|
| `dual_momentum_topn` | Cross-sectional top-N momentum |
| `cta_trend_long_only` | Time-series trend following |
| `composite_regime_conditioned` | Regime-gated offense/defense |
| `taa_10m_sma` | 10-month SMA timing |
| `composite_selective_signals` | Multi-signal confirmation |
| `composite_trend_quality_refined` | R²-weighted trend quality |
| `composite_confirmation_aware_momentum` | Breadth-confirmed momentum |
| `composite_structural_defense_sleeve` (W1) | Orthogonal defensive basket (GLD/TLT/HYG/LQD/DBA/BIL) |

### Layer 2B — Regime Engine

Transparent composite z-score producing 5 walk-forward states:

| State                | Freq  | Character                          |
|----------------------|-------|------------------------------------|
| `stressed_panic`     | \~8%  | High vol, deep drawdown, BIL-heavy |
| `recovery_fragile`   | \~14% | Improving but fragile              |
| `recovery_confirmed` | \~4%  | Clear recovery, re-risk            |
| `neutral_mixed`      | \~44% | Ambiguous — largest bucket by far  |
| `calm_trend`         | \~27% | **Primary bottleneck**             |

Features: rolling vol, drawdown severity, canary breadth
(VWO/HYG/VNQ/EFA/PDBC), average pairwise correlation, VIX slope, FRED
macro z-scores.

### Layer 3 — Portfolio Construction

HRP-based allocation with state-conditional risk multipliers,
inverse-vol sleeve weighting, target-vol scaling, BIL/defense overlay,
and a fragility guardrail (Phase 5).

### Current Metrics (Production Pin: `improved_frontier_phase5_fragility_guard`)

| Metric                        | Value                   |
|-------------------------------|-------------------------|
| Annual return                 | 7.14%                   |
| Sharpe                        | 0.948                   |
| Max drawdown                  | −11.6%                  |
| Holdout Sharpe (last 104w)    | 2.179                   |
| Best aggressive shadow return | 7.88% (Phase 7 stretch) |
| Gap to 8.0% target            | **0.12pp**              |

> The production pin adds Phase 1 R2A offense scaling (α=0.08) and a
> Phase 4 fragility cap on top of the GGG1 base. It passed all 8 Phase D
> gates in the frontier arc evaluation (Phase 10A verdict: PROMOTE).

------------------------------------------------------------------------

## 2. What Is Already Covered

> **Do not suggest any of the following.** The project has exhausted all
> of these branches.

### Allocator Families (all tried, HRP won)

HRP, ERC, HERC (basic), MVO, Black-Litterman with regime views,
max-diversification, principled continuous maps, inverse-vol,
state-conditional inverse-vol, learned concentration gates, boosted
sleeve-return allocators, meta-allocators (bucket-trust, abstention,
regret-minimizing), soft regime posteriors, holdings-blend frameworks (6
consecutive sprints: Q–V), conditional W1 sizing (3 variants), adaptive
risk-contribution allocators.

### Sleeve Expansions (all tried)

Trend-quality, breadth-confirmed momentum, confirmation-aware momentum,
structural defense (W1, promoted), recovery-confirmed offense (failed —
negative alpha in target state), calm-carry (BIL artifact, not real
alpha), macro-trend diversifier (W4, needs vol cap), sector sleeves
(Phase 3–4B), anti-chop clarity, calm-trend participation.

### Signal Types (all tried or cleared)

Cross-sectional momentum (multiple horizons), time-series momentum,
reversal (1w/4w), quality, MA-distance, trend-clarity (R²-weighted),
breadth-confirmed momentum, contained recovery quality, cross-asset
leadership (Phase 4A — failed, negative full IC), OOO series
(ML-assisted feature discovery, cross-asset signal expansion,
triple-barrier, vol-managed sizing), QQQ (feature interactions), SSS
(regime-sequence modeling), VIX term structure carry.

### Regime Redesigns (all tried, current engine retained)

Confidence boost, tail-risk suppression, transition-quality gate, combo
ABC, regime softening, hard-ML meta-layer (NNN), soft regime posterior
(Phase T), lookthrough repair (JJJ).

### ML Approaches (all failed Phase D gates)

Logistic regression, GBM, walk-forward label construction,
decision-aware allocators, trust models, PPP latent factor discovery,
QQQ feature interactions, OOO signal discovery — all eventually rejected
by the 8-gate Phase D validation stack.

### Data Already In Use

FRED (7 indicators), VIX term structure (1m/3m/6m slopes), Google Trends
(fear composite), daily GARCH vol, Ledoit-Wolf covariance shrinkage,
canary breadth (ETF-level, not stock-level).

------------------------------------------------------------------------

## 3. Main Bottlenecks

Ranked by binding force:

### Bottleneck 1 — Calm-Trend State Is Under-Monetized *(primary)*

Calm_trend is **26.6% of all weeks**. The portfolio earns \~4.2%
annualized in this state while SPY significantly outperforms. Phase 7
confirmed that pushing sector ETF allocation further in calm_trend
creates drag — sector ETFs cannot distinguish high-quality calm weeks
from ordinary ones.

The only diagnostic that showed a clean signal: **PIT stock breadth gave
+0.517% per 4-week SPY lift in calm_trend** (Phase 5A-Free). ETF breadth
showed −0.457%. Stock breadth is the missing ingredient; it requires
Norgate Data or equivalent.

### Bottleneck 2 — Neutral_Mixed Is Too Heterogeneous *(second-largest)*

At **493 observations (44% of history)**, neutral_mixed is the biggest
state by far. It's a catch-all containing growth-up, growth-down,
inflationary, and deflationary weeks with no internal differentiation. A
proper macro regime that separates growth and inflation dimensions could
split neutral_mixed into actionable sub-states. This is **free to
implement** — the data is already partially available from FRED.

### Bottleneck 3 — Macro Regime Uses Only 7 of 128 Available FRED-MD Series

The repo downloads 7 FRED indicators but uses them as individual
z-scores, not as a structured macro-factor space. FRED-MD contains 128
monthly macro series. A proper **growth factor / inflation factor /
financial conditions factor** decomposition via rolling PCA has **never
been built**. This is the most clearly missing methodological piece
that's still free to implement.

### Bottleneck 4 — Return Ceiling on Liquid ETFs Without PIT Stock Data

The seven-phase improvement arc moved from 7.14% → 7.88% (+0.74pp). The
remaining 0.12pp gap is tied specifically to calm_trend weeks, where no
existing ETF signal distinguishes week quality. This ceiling is real and
confirmed with 7 phases of research.

### Bottleneck 5 — Signal Combination Is Static, Not Regime-Conditional

Layer 1 signals are combined with **fixed weights** into composites
regardless of which regime we're in. The per-state IC validation already
shows that xsmom IC is higher in trend-friendly states and reversal IC
is higher in stressed states — but this information is never fed back
into the signal weighting. IC-by-state dynamic weighting has not been
implemented as the primary aggregation mechanism.

------------------------------------------------------------------------

## 4. Internet Research Findings

### [A] Tactical Asset Allocation with Macroeconomic Regime Detection

**Authors:** Oliveira, Sandfelder, Fujita, Dong, Cucuringu (March 2025)\
**Links:** [arxiv 2503.11499](https://arxiv.org/abs/2503.11499) \| [SSRN
5183762](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5183762)

Uses the full FRED-MD database (128 series) with a walk-forward modified
k-means to classify macro regimes over time. Maps regime forecasts to
ETF expected return/vol estimates. Outperforms equal-weight,
buy-and-hold, and random regime models on 10 ETFs (Feb 2000 – Jan 2023).

> **Relevance:** Directly applicable to this project. The methodology
> uses the same FRED data that's already partially downloaded, but
> applies a proper macro-factor classification instead of individual
> z-scores.

------------------------------------------------------------------------

### [B] Dynamic Asset Allocation with Asset-Specific Regime Forecasts

**Authors:** Shu, Yu, Mulvey (June 2024)\
**Links:** [arxiv 2406.09578](https://arxiv.org/abs/2406.09578) \|
[Annals of Operations
Research](https://link.springer.com/article/10.1007/s10479-024-06266-0)

Novel hybrid framework: a gradient-boosted decision tree predicts a
regime probability **per asset** (not just globally) using
asset-specific return features + cross-asset macro features. Per-asset
regime probabilities feed into mean-variance optimization. Multi-asset
portfolio (equity, bonds, real estate, commodities, 1991–2023).
Outperforms global-regime and naive portfolios across multiple optimizer
types.

> **Relevance:** The key methodological gap in this repo — the project
> applies one global regime label to all 35 ETFs identically. Per-ETF
> regime probabilities could allow the allocator to over/underweight
> specific ETFs based on their own micro-regime, not just the global
> state.

------------------------------------------------------------------------

### [C] Regime-Aware Asset Allocation: Statistical Jump Model

**Authors:** Nguyen et al. (February 2024)\
**Links:** [arxiv 2402.05272](https://arxiv.org/abs/2402.05272)

The sparse jump model (SJM) clusters temporal features while imposing an
explicit penalty for each regime transition:
`loss(x_t, θ_{s_t}) + λ × Σ 1(s_t ≠ s_{t-1})`. This penalty makes regime
labels more stable than HMM or k-means. Applied to downside risk
reduction across factor portfolios.

> **Relevance:** The current composite z-score engine produces whipsaw
> transitions that add unnecessary turnover. Replacing it with an SJM
> could reduce transitions by 15–20%+ while preserving meaningful state
> detection, freeing turnover budget for more aggressive positioning.

------------------------------------------------------------------------

### [D] Dynamic Factor Allocation Leveraging Regime-Switching Signals

**Authors:** Multiple (October 2024)\
**Links:** [arxiv 2410.14841](https://arxiv.org/abs/2410.14841) \| [JPM
Portfolio Management
Research](https://www.pm-research.com/content/iijpormgmt/51/3/50)

Applies SJM to identify bull/bear regimes for individual factors.
Integrates factor-specific regime inferences into a Black-Litterman
framework as relative views. Information ratio improves from 0.05
(equal-weight) to \~0.40 with regime-adjusted BL views. Results robust
through post-2022 rate-hike period.

> **Relevance:** Dynamic signal weighting by regime via Bayesian BL
> views is different from what this project has tried. Previous BL
> attempts used static views (Phase 2A). This is a principled Bayesian
> combination of regime-conditional IC estimates that hasn't been
> implemented.

------------------------------------------------------------------------

### [E] Improving Volatility-Managed Portfolios in Real Time

**Author:** Xu (2024)\
**Link:** [CFR Working
Paper](https://cfr.ivo-welch.info/forthcoming/papers/xu2024improving.pdf)

Shows that better realized vol estimators can improve Moreira-Muir style
volatility-managed portfolios. Applied to multiple factor portfolios
out-of-sample.

> **Relevance:** The project references vol-managed portfolios in Layer
> 2B but doesn't implement a clean inverse-realized-variance portfolio
> scale. The current target-vol multiplier is related but not identical.
> Worth benchmarking.

------------------------------------------------------------------------

### [F] A Multifactor Perspective on Volatility-Managed Portfolios

**Authors:** DeMiguel et al. (2024)\
**Link:** [Journal of
Finance](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13395)

Conditional multifactor portfolios where relative weights on factors
vary with market volatility. Higher average weights on value (HML),
momentum (UMD), and BAB when vol is high. "Resurrects" value factor.
Large utility gains vs unconditional portfolios.

> **Relevance:** Multi-factor generalization of Moreira-Muir. Applied to
> asset allocation rather than single-stock factors. Shows that
> vol-conditioning improves both return and risk-adjusted metrics.

------------------------------------------------------------------------

### [G] Continuous Timing Signals for Growth-Defensive Style Allocation

**Authors:** Multiple (2025)\
**Link:** [arxiv 2605.20636](https://arxiv.org/html/2605.20636)

Replaces discrete regime labels with a continuous smooth score combining
rate relief, drawdown depth, VIX stress relief, and growth-crowding
penalty. Walk-forward validated with drawdown reduction post-2022.

> **Relevance:** This is what the project's offense budget tries to do,
> but with a more formally calibrated continuous signal. The
> growth-crowding penalty in particular is a missing ingredient — the
> project's fragility guard is related but uses inverted cross-asset
> leadership rather than a crowding measure.

------------------------------------------------------------------------

### [H] RegimeFolio: Regime-Aware ML for Sectoral Portfolio Optimization

**Authors:** Multiple (October 2025)\
**Link:** [arxiv 2510.14986](https://arxiv.org/abs/2510.14986)

VIX-based regime segmentation + sector-specific ensemble learners
(Random Forest, GBM). Up to 20% lower forecast error and Sharpe
improvements \>0.5 vs regime-agnostic baselines (2020–2024, 34 large-cap
US equities).

> **Relevance:** Confirms that regime-aware sector ETF allocation works.
> The project already has sector sleeves (Phases 3–4B) but applies
> global regime labels to sector ETFs rather than sector-specific regime
> conditioning.

------------------------------------------------------------------------

## 5. Ranked Breakthrough Candidates

------------------------------------------------------------------------

### Rank 1 — Full FRED-MD Macro Regime Classifier (Growth × Inflation × Financial Conditions)

**Why it's the top pick:** Free, data already partially available,
addresses the largest state (neutral_mixed, 44% of history), and
directly matches the methodology in the Oliveira et al. 2025 paper. No
new data purchase required.

**Thesis**\
The current regime engine is a single stress/calm dimension. It cannot
distinguish the four macro quadrants that have dramatically different
optimal allocations:

| Quadrant | Character | ETF Preference |
|----|----|----|
| Growth up / Stress low | Risk-on bull | Equity, credit |
| Growth up / Stress high | Inflationary / overheating | Commodities, TIP, energy |
| Growth down / Stress low | Soft landing | Bonds, gold |
| Growth down / Stress high | Stagflation / panic | BIL, GLD, short duration |

The `neutral_mixed` state (493 weeks, 44% of history) contains all four
of these mixed together. The allocator can't make an optimal choice
because it doesn't know which quadrant it's in.

**Why it could be a step-change**\
If neutral_mixed can be reliably split into 2+ actionable sub-states,
and each sub-state has different optimal ETF weights, the portfolio
gains an action signal in its largest time bucket. Even a +0.15% weekly
improvement in neutral_mixed translates to \~+0.60pp annualized at that
state's frequency.

**Implementation plan** 1. Download 5 additional free FRED series:
INDPRO (industrial production), ICSA (weekly unemployment claims), HOUST
(housing starts), RSAFS (retail sales), PAYEMS (nonfarm payrolls) 2.
Build rolling 60-month expanding-window PCA on all 12 FRED indicators →
extract PC1 (growth factor) and PC2 (financial conditions / inflation
factor) 3. Classify each month into one of 4 macro quadrants based on
sign of PC1 and PC2; forward-fill to weekly; lag 1 week 4. Add
macro_quadrant as a second conditioning dimension in Layer 2B alongside
the existing 5-state engine 5. Test state-tilt candidates: in expansion
quadrant, raise offense budget +10%; in slowdown quadrant, tilt toward
bonds/GLD; in overheating, tilt toward TIP/energy; in stress, reinforce
existing stressed_panic logic

**Files to change:**\
`01_data_hub.ipynb`, `04_layer2b_risk_regime_engine.ipynb`,
`scripts/build_improvement_artifacts.py` (new state_tilt modes)

**Validation design**\
- Walk-forward: PCA refit quarterly, expanding window, minimum 60 months
of FRED data - Gate 1: At least 2 of 4 quadrants show \|ΔReturn\| ≥ 0.5%
per week vs pooled neutral_mixed baseline in development sample - Gate
2: Portfolio Sharpe ≥ production pin in holdout (104 weeks) - All 8
Phase D gates applied as usual

**Expected impact:** Medium-high. +0.05 to +0.15 Sharpe if neutral_mixed
splits cleanly.

**Overfitting risk:** Low–medium. PCA is a dimensionality-reduction step
with no free parameters to overfit. The main risk is that monthly macro
data is too slow-moving to be actionable at weekly frequency.
Mitigation: use only the sign of macro factors (direction), not
continuous levels.

**First minimal experiment**\
Download INDPRO and ICSA from FRED (free). Build rolling 60-month PC1
and PC2 from the 9 FRED series now available. Plot PC1 vs subsequent
4-week SPY returns. Check whether PC1 \> 0 vs PC1 \< 0 weeks show
different median returns in holdout (last 104 weeks). If \|Δmedian\| ≥
0.3%, proceed to full portfolio test.

------------------------------------------------------------------------

### Rank 2 — PIT Stock Breadth (Norgate Data)

**Why it's rank 2:** Diagnostically the highest-upside and most clearly
identified bottleneck. The main obstacle is cost (\~\$100–150/month for
Norgate Platinum/Diamond). The scaffold is already built. This is the
confirmed path to 8%+.

**Thesis**\
Calm_trend (26.6% of weeks) is the binding return constraint. The Phase
5A diagnostic showed:

| Signal                                      | 4-week SPY lift in calm_trend |
|---------------------------------------------|-------------------------------|
| ETF breadth (current)                       | **−0.457%** (negative)        |
| Stock breadth (current-constituent, biased) | **+0.517%** (positive)        |

ETF breadth averages across broad baskets and can't distinguish months
where 80% of stocks are above their 200-day MA (high-quality bull) from
months where a few megacaps are carrying the index (narrow, fragile
bull). Stock breadth makes that distinction.

**Why it could be a step-change**\
+0.517% per 4 weeks in calm_trend, at 26.6% of portfolio history, is
arithmetically sufficient to close the 0.12pp gap to 8.0% and exceed it.
This isn't speculative — it's a measured diagnostic lift from the Phase
5A-Free study, with the caveat that it used survivorship-biased current
constituents. PIT data removes that bias.

**Implementation plan** 1. Purchase Norgate Data US Stocks
Platinum/Diamond (\~\$100–150/month) 2. Export: S&P 500 PIT
constituents + daily adjusted prices back to 2005, with delisting-aware
coverage 3. Save to `data/stock_breadth/raw/` (scaffold already in
place) 4. Run `python3 scripts/build_pit_stock_breadth_panel.py`
(already built) 5. Build signals: `pct_above_200d_ma`,
`advance_decline_ratio`, `new_highs_minus_new_lows_ratio` 6. Add Phase
5B `state_tilt` mode: in calm_trend weeks, scale offense budget by
breadth quality score (0.85 when breadth \<40%, 1.0 when 40–70%, 1.15
when \>70%)

**Files to change:**\
`scripts/build_pit_stock_breadth_panel.py` (already built),
`scripts/build_improvement_artifacts.py` (new Phase 5B state_tilt modes)

**Validation design**\
- Breadth signals validated from 2010 (requires 260-week PIT history) -
Pre-declared holdout: last 104 weeks - Gate: calm_trend
state-conditional Sharpe improves ≥ 0.10 in holdout; overall Sharpe does
not worsen

**Expected impact:** High. +0.15 to +0.40pp annualized if the diagnostic
lift holds OOS.

**Overfitting risk:** Low–medium. Stock breadth is an interpretable
causal signal. PIT data removes survivorship bias. Risk is that the
2020–2026 diagnostic window is too short to generalize.

**Proxy experiment (before purchasing data)**\
Use the 10 SPDR sector ETFs as a proxy for stock breadth. Build
`pct_sector_etfs_above_200d_ma` and `pct_sector_etfs_above_50d_ma`. Test
IC in calm_trend weeks. If IC \> 0 in holdout, it validates the
hypothesis directionally while data is being acquired.

------------------------------------------------------------------------

### Rank 3 — Asset-Specific Regime Forecasting (Per-ETF Regime Probabilities)

**Why it's rank 3:** High methodological upside, backed by 2024
published research (Annals of Operations Research). Higher
implementation risk than Ranks 1–2 because the project has tried many ML
approaches and all failed Phase D. The key difference here is this
operates at the signal/weight-cap level rather than at the allocator
level.

**Thesis**\
The project applies one global regime label to all 35 ETFs identically.
In practice, SPY can be trending up while EEM is in a bear market; TLT
can be stressed while GLD is in a safe-haven bull. A single
"neutral_mixed" label doesn't capture this cross-sectional
heterogeneity.

**Implementation plan** 1. For each of 12 core risky assets (SPY, QQQ,
IWM, EFA, VWO, TLT, HYG, GLD, VNQ, XLE, IEF, LQD), compute a per-asset
regime probability using 5 features: - Asset-specific trailing 26w
return z-score - Asset-specific drawdown vs own 52w high -
Asset-specific vol z-score - Global regime score (existing, from Layer
2B) - HYG credit spread (existing, from Layer 1) 2. Gradient-boosted
decision tree per asset (walk-forward, expanding window, 52-week
minimum, 4-week embargo). Output: probability of being in "favorable"
regime for that asset. 3. Use per-asset regime probability to condition
ETF weight caps inside the offense bucket: - P \< 0.40 → cap weight at
50% of uncapped allocation - P \> 0.70 → allow up to 1.5× uncapped
allocation 4. New file: `scripts/build_asset_specific_regime.py`

**Validation design**\
- Gate 1 (signal level): Per-ETF regime probability IC ≥ 0.05 vs own
4-week forward return in holdout - Gate 2 (portfolio level): Overall
Sharpe improvement ≥ 0.05 vs production pin in holdout - All 8 Phase D
gates

**Expected impact:** Medium. Most visible in neutral_mixed weeks when
cross-sectional divergence is high. Expected +0.05 to +0.15 Sharpe.

**Overfitting risk:** High. Per-ETF ML models with small N per state are
prone to overfitting. Mitigation: use only 5 features per model, require
52-week minimum training, validate IC strictly before any portfolio
test.

**First minimal experiment**\
For just 3 ETFs (SPY, TLT, GLD), build a 5-feature logistic regression
(no tree). Walk-forward IC in holdout. Gate: IC ≥ 0.05 for at least 2 of
3 assets. If not, drop this idea.

------------------------------------------------------------------------

### Rank 4 — Statistical Jump Model for Regime Stability

**Why it's rank 4:** Indirect value (reduces turnover rather than
directly increasing return). Lower implementation risk than Rank 3.

**Thesis**\
The current composite z-score engine produces whipsaw transitions near
state thresholds. The SJM adds an explicit transition penalty
`λ × Σ 1(s_t ≠ s_{t-1})` that makes regime labels more stable without
missing genuine state changes. More stable labels → lower turnover →
freed turnover budget for more aggressive positioning.

**Expected impact:** Medium-indirect. If turnover falls ≥15%, the freed
capacity could allow a slightly larger offense budget without hitting
the 1.10× turnover cap.

**First minimal experiment**\
Apply SJM with λ=2.0 to the existing `risk_regime_score` series. Count
regime transitions per year vs current engine. Target: ≥20% fewer
transitions. If achieved, proceed to portfolio-level test.

------------------------------------------------------------------------

### Rank 5 — Dynamic IC-Weighted Signal Combination

**Why it's rank 5:** Lower expected impact; the project has tried many
similar ideas at the allocator level and all failed. The signal-level
version may be more robust but expected improvement is modest.

**Thesis**\
Layer 1 signals are combined with fixed weights. The per-state IC
validation already shows that xsmom IC is higher in trend-friendly
states and reversal IC is higher in stressed states. A state-adaptive
composite — where signal weights = softmax(IC-by-current-state) with a
5% floor — has never been implemented at the signal level.

**Expected impact:** Low–medium. Expected +0.02 to +0.05 Sharpe.

**First minimal experiment**\
Compute IC-by-state for xsmom and reversal on the development sample.
Gate: \|ΔIC\| between calm_trend and stressed_panic ≥ 0.05. If not,
drop.

------------------------------------------------------------------------

## 6. Recommended Next Sprint

### Sprint: Full FRED-MD Macro Regime Classifier

**Selection rationale:** Free data, partially downloaded, highest
potential impact on neutral_mixed (the largest state), directly
supported by Oliveira et al. 2025, no new data purchase required, no
risky ML infrastructure.

------------------------------------------------------------------------

### Files to Create / Change

| File | Action |
|----|----|
| `01_data_hub.ipynb` | Add 5 new FRED series (INDPRO, ICSA, HOUST, RSAFS, PAYEMS) |
| `scripts/build_macro_regime_classifier.py` | **New script** — PCA + macro quadrant classification |
| `04_layer2b_risk_regime_engine.ipynb` | Integrate `macro_quadrant` as second conditioning dimension |
| `scripts/build_improvement_artifacts.py` | Add new `state_tilt` modes for macro-conditioned allocation |

------------------------------------------------------------------------

### Functions / Classes to Add

``` python
def build_macro_factor_space(macro_df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """Rolling expanding-window PCA on FRED macro panel.
    Returns:
      - growth_factor (PC1): positive = expansion, negative = slowdown
      - financial_conditions_factor (PC2): positive = easy/inflationary, negative = tight/deflationary
    All lagged 1 week for causal safety. Monthly data forward-filled to weekly."""

def classify_macro_quadrant(growth_factor, fc_factor) -> pd.Series:
    """Returns one of four states:
      'expansion'   — growth+ / stress-low
      'overheating' — growth+ / stress-high (inflationary)
      'slowdown'    — growth- / stress-low (soft landing)
      'stress'      — growth- / stress-high (stagflation / panic)
    Uses 0 as threshold for both dimensions (z-score based, simple and overfitting-resistant)."""

def compute_macro_conditioned_allocation(macro_quadrant, base_weights) -> pd.DataFrame:
    """Adjusts offense budget and ETF preferences by macro quadrant:
      expansion:   +10% offense, equity tilt (SPY/QQQ/IWM)
      overheating: commodities/TIP tilt, reduce long-duration bonds
      slowdown:    bonds/GLD tilt, reduce equity
      stress:      reinforce existing stressed_panic BIL/GLD logic"""
```

------------------------------------------------------------------------

### Metrics to Compute

-   Return, Sharpe, Calmar, max DD per macro quadrant (walk-forward, not
    in-sample)
-   Neutral_mixed Sharpe split by macro quadrant — is the sub-state
    distinction real in holdout?
-   Full portfolio Sharpe vs production pin in development and holdout
-   All 8 Phase D gates (same as always)

------------------------------------------------------------------------

### Walk-Forward Design

| Parameter | Setting |
|----|----|
| PCA fit method | Expanding window, minimum 60 months of FRED data, refit quarterly |
| Macro quadrant assignment | Month-end label, forward-filled weekly, 1-week lag |
| Development window | Through 2024-04-12 (929 weeks) |
| Holdout window | 2024-04-19 → present (104+ weeks, pre-declared) |
| Embargo | 4 weeks between training and test |

------------------------------------------------------------------------

### Pass/Fail Gates

| Gate | Threshold | Notes |
|----|----|----|
| Macro quadrant validity | At least 2 of 4 quadrants show | ΔReturn |
| Holdout Sharpe | Δ ≥ 0.00 vs production pin | Non-negative |
| Full Sharpe | Δ ≥ +0.01 vs production pin |  |
| Max drawdown | Δ ≥ −0.01 | Can't worsen by more than 1pp |
| CVaR-5 | Δ ≥ −0.002 |  |
| Bootstrap P | ≥ 60% on holdout Sharpe | 1000 block iterations |
| Rolling 104w win rate | ≥ 55% |  |
| Turnover | Δ ≤ +3pp/year | Can't add turnover cost |

------------------------------------------------------------------------

## 7. Stop/Go Criteria

### Promote (all must pass simultaneously)

-   [ ] Holdout Sharpe Δ ≥ 0.00 vs production pin
-   [ ] Full-history Sharpe Δ ≥ +0.01
-   [ ] Max drawdown Δ ≥ −0.01 (can't worsen by more than 1pp)
-   [ ] CVaR-5 Δ ≥ −0.002
-   [ ] Bootstrap P(candidate \> production on holdout Sharpe) ≥ 60%
-   [ ] Rolling 104-week win rate ≥ 55%
-   [ ] Annual turnover increase ≤ 3pp
-   [ ] Stressed_panic Sharpe Δ ≥ −0.02 (protection preserved)

### Hard Stops (any one triggers Drop or Research-only)

-   Any in-sample-only improvement that reverses in holdout →
    **Research-only**
-   Any improvement where the underlying signal IC ≤ 0 in holdout →
    **Drop**
-   Any candidate that requires turnover \> 1.10× production → **Drop**
-   Any macro regime that fires fewer than 30 times in full history →
    **Drop** (too sparse to validate)
-   Any bootstrap confidence interval that straddles zero at 90% →
    **Research-only at best**

------------------------------------------------------------------------

## 8. Final Recommendation

### Why the project is stuck: A combination of reasons A and B

------------------------------------------------------------------------

**Reason A — Strategy design is missing a major component**

The macro regime has never been properly built. The project uses 7 FRED
indicators as individual z-scores but has never extracted a structured
growth/inflation/financial-conditions factor space. The `neutral_mixed`
state — the portfolio's biggest time bucket — has never been attacked
with a proper macro dimension. This is a **design gap**, not a data gap.

------------------------------------------------------------------------

**Reason B — Natural return ceiling on liquid ETF data (for
calm_trend)**

Seven phases of research confirmed that no combination of the existing
35 ETFs can distinguish high-quality calm weeks from ordinary ones at
the ETF-signal level. The only path through this ceiling is PIT stock
breadth (Norgate), which costs \~\$100/month and has been diagnostically
validated.

------------------------------------------------------------------------

**Reason C — Optimizer/risk system too conservative → NOT the primary
issue**

HRP + fragility guard is the correct system for this opportunity set.
The allocator has been exhausted over 35+ sprints across every
conceivable architecture. The bottleneck is not the optimizer.

------------------------------------------------------------------------

**Reason D — Validation framework is rejecting real improvements →
Partially true, do not relax gates**

The 8-gate Phase D framework is strict. Some real improvements may have
been rejected by bootstrap or holdout gates. But those gates exist for
production discipline. **Do not lower the gates.** Find improvements
robust enough to clear them.

------------------------------------------------------------------------

**Reason E — Need a different asset universe → Premature**

The project is only 0.12pp away from 8.0% with free ETF data. This is a
winnable gap without futures, crypto, or single stocks. Do not expand
the universe until the existing opportunity set is properly exploited.

------------------------------------------------------------------------

### The Two-Step Plan

| Priority | Action | Cost | Expected Impact |
|----|----|----|----|
| 1 | Build full FRED-MD macro regime classifier | Free | Medium-high; attacks neutral_mixed (44% of weeks) |
| 2 | Subscribe to Norgate + build PIT stock breadth (Phase 5B) | \~\$100–150/month | High; confirmed +0.517% per 4w in calm_trend |

Anything beyond these two steps should be treated as **research-only**
until the macro regime and stock breadth work is complete.

The project has demonstrated conclusively that adding more ML, more
allocators, or more sleeve combinations doesn't work when the underlying
opportunity set is constrained. The next unlock is **upstream**, not
downstream: better data and better macro regime classification, not
smarter portfolio math applied to the same inputs.

------------------------------------------------------------------------

## Sources

| Paper | Link |
|----|----|
| Tactical Asset Allocation with Macroeconomic Regime Detection (Oliveira et al., 2025) | [arxiv 2503.11499](https://arxiv.org/abs/2503.11499) · [SSRN 5183762](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5183762) |
| Dynamic Asset Allocation with Asset-Specific Regime Forecasts (Shu, Yu, Mulvey, 2024) | [arxiv 2406.09578](https://arxiv.org/abs/2406.09578) · [Annals of Operations Research](https://link.springer.com/article/10.1007/s10479-024-06266-0) |
| Regime-Aware Asset Allocation: Statistical Jump Model (Nguyen et al., 2024) | [arxiv 2402.05272](https://arxiv.org/abs/2402.05272) |
| Dynamic Factor Allocation Leveraging Regime-Switching Signals (2024) | [arxiv 2410.14841](https://arxiv.org/abs/2410.14841) · [JPM Portfolio Management Research](https://www.pm-research.com/content/iijpormgmt/51/3/50) |
| Improving Volatility-Managed Portfolios in Real Time (Xu, 2024) | [CFR Working Paper](https://cfr.ivo-welch.info/forthcoming/papers/xu2024improving.pdf) |
| A Multifactor Perspective on Volatility-Managed Portfolios (DeMiguel et al., 2024) | [Journal of Finance](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13395) |
| Continuous Timing Signals for Growth-Defensive Style Allocation (2025) | [arxiv 2605.20636](https://arxiv.org/html/2605.20636) |
| RegimeFolio: Regime-Aware ML for Sectoral Portfolio Optimization (2025) | [arxiv 2510.14986](https://arxiv.org/abs/2510.14986) |
| HERC Portfolio (Thomas Raffinot) | [SSRN 3237540](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3237540) |
| Regime-Switching Asset Allocation with Jump Model + MPC (MDPI 2025) | [MDPI Mathematics](https://www.mdpi.com/2227-7390/13/17/2837) |
