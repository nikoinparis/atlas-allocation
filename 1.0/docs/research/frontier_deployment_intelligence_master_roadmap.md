# Frontier Deployment Intelligence — Master Roadmap

**Document version:** 2026-05-20\
**Status:** Research roadmap — no production files modified\
**Production pin:** `improved_phase2b_regime_confidence_boost` (unchanged)\
**Shadow pin:** `improved_phase2b_combo_abc` (unchanged)\
**Production candidate (pending review):** `improved_phaseggg_confirmed_only_robust_offense`

------------------------------------------------------------------------

## 1. Executive Summary

### Are we ready to move into frontier research after stabilization?

Yes. The Deployment Architecture Stabilization Sprint confirms:

-   The no-modifier wrapper reproduces exact GGG returns to machine precision (max error 2.116e-16, correlation 1.000).
-   Safe checkpoints are clearly defined and usable: `regime_multipliers`, `offense_budget`, `cash_bil_budget`, `transition_rerisk_smoothing`, `derisk_smoothing`, `volatility_risk_overlay`.
-   Architecture-valid rules are tested and confirmed: `offense_eligibility`, `breadth_confirmation`, `transition_quality_rerisk`, `deterioration_acceleration`, `dollar_pressure`, `macro_stress`, `combined_conservative`.
-   The rule harness ran consistently across all tested configurations.
-   Production and dashboard files were not modified.

The wrapper is ready to serve as an exact baseline for frontier experiments. The foundation is clean.

### Is this the correct direction for significant improvement?

Yes, with important caveats.

The project has exhausted the following levers: - Simple overlay geometry and threshold tuning - Regime confidence calibration at the current granularity - Trust-layer meta-allocation (Phases P–S) - Holdings-level blending (Phases U–V, AA) - Allocator family variants (HRP, ERC, HERC, inverse-vol, learning allocators) - Holdings-blend refinement (Phases X–Z) - Sleeve separability redesign (Phases W–Z)

The project has NOT yet seriously explored: - **Deployment-state quality labeling**: distinguishing good risk-on from structurally fragile risk-on - **Trend setup quality**: which trends deserve capital versus which are noise - **Re-risking speed intelligence**: faster entry when quality is confirmed, not just when a state label flips - **Cross-sectional leadership systems**: where is leadership coming from, and is it broad or narrow? - **Allocator objective redesign around opportunity quality**: not static diversification but deployment-quality-aware allocation - **Decision-focused learning**: learning deploy/wait decisions, not raw returns

These directions are architecturally grounded, causally motivated, and meaningfully different from the prior 35+ sprints.

### What is realistic versus unrealistic?

**Realistic** with existing free data and the current ETF universe: - Recovering 0.1–0.3pp of annual return per well-targeted frontier phase - Improving Sharpe by 0.01–0.04 per phase through better deployment timing - Reducing unnecessary BIL drag in clear good-state windows - Improving re-risking speed after confirmed recoveries without weakening stressed_panic - Total plausible frontier arc improvement: **+0.3pp to +0.8pp** above the current best (7.88%)

**Realistic** with PIT stock breadth data (Norgate/WRDS): - An additional **+0.2–0.5pp** from better calm_trend classification - Potentially reaching 8.0–8.5% annualized with full frontier stack

**Unrealistic** without major structural changes: - Reaching 10% annualized return within this ETF universe and current risk discipline - The project has documented that calm_trend (26.6% of weeks) is the binding constraint, and even exhaustive manipulation of the existing signals could not push calm_trend capture meaningfully higher without PIT breadth data

**What would make 10% annual return plausible:** 1. PIT stock breadth data that cleanly separates high-return calm weeks from ordinary ones 2. Expansion to a broader ETF universe including commodity trend, managed futures, or multi-asset carry signals that are genuinely uncorrelated with the current offensive sleeve cluster 3. Accepting meaningfully higher drawdown or CVaR, which the project's gates explicitly prohibit 4. The combination of (1) + (2) with the frontier deployment intelligence stack described here

Honest statement: **10% is not a likely near-term outcome** with this configuration. 8.0–8.5% is a realistic upper bound for the current free-data frontier. Chase 10% only by improving the opportunity set with new uncorrelated return sources, not by overfitting existing signals.

------------------------------------------------------------------------

## 2. Current Project State

### Production and Shadow Pins

| Role | Strategy | Return | Sharpe | Max DD |
|----|----|----|----|----|
| Production pin | `improved_phase2b_regime_confidence_boost` | \~6.90% | \~0.885 | \~-13.98% |
| Production candidate (pending) | `improved_phaseggg_confirmed_only_robust_offense` | \~7.14% | \~0.936 | \~-13.7% |
| Shadow pin | `improved_phase2b_combo_abc` | \~6.85% | \~0.880 | \~-14.2% |
| Best research aggressive shadow | `improved_phase7_stretch_target` | \~7.88% | \~0.926 | \~-15.28% |

### Stabilized Wrapper and Checkpoints

**Safe checkpoints (directly usable in frontier experiments):** - `regime_multipliers` — post-state-tilt sleeve weights, 1110 × 7 - `offense_budget` — post-layer3-expression sleeve weights, 1110 × 7 - `cash_bil_budget` — post-overlay pre-lookthrough, 1110 × 7 - `transition_rerisk_smoothing` — post-overlay pre-lookthrough, 1110 × 7 - `derisk_smoothing` — post-overlay pre-lookthrough, 1110 × 7 - `volatility_risk_overlay` — post-overlay pre-lookthrough, 1110 × 7 - `final_etf_lookthrough_weights` — comparison only, 1110 × 35

**Dangerous checkpoints (diagnostic only, never direct modification):** - `raw_sleeve_targets` — HRP sleeve weights before regime/overlay - `defense_budget` — post-layer3 expression before overlay - `cost_turnover_calculation` — final ETF weights for cost computation

### What Is Solved

-   Exact wrapper reproduction of the production candidate baseline
-   Deployment architecture: rule harness, checkpoint system, architecture-valid rules
-   Evaluation stack: pre-declared holdout (104-week), rolling-origin, bootstrap, raw-metric composite
-   Phase D production gates: full-Δ, holdout-Δ, holdout-Sharpe, rolling win rate, rolling mean-Δ, bootstrap probability, MDD cap, CVaR cap
-   Sleeve-panel separability: `composite_structural_defense_sleeve` (W1) added and promoted
-   Signal inventory: all existing Layer 1 signals are documented and checkpointed
-   Historical regime states: `market_state_history.csv` provides walk-forward state labels
-   Dual-track governance: production + shadow + candidate comparison discipline

### What Is Not Solved

-   **Deployment-state quality**: the engine knows *when* the market is in recovery, but not *how good* that recovery is
-   **Trend setup quality**: the engine does not have a principled "is this trend worth following?" score
-   **Re-risking speed**: the re-entry logic is still too conservative in confirmed good states
-   **Cross-sectional leadership**: leadership concentration, breadth, and rotation are not systematically tracked
-   **Calm_trend under-capture**: 26.6% of all weeks, binding constraint on reaching 8%+
-   **Allocator objective**: still static diversification-centric, not opportunity-quality-aware

### Branches That Are Closed

| Branch | Verdict | Reason |
|----|----|----|
| Allocator-refinement family (Phases A–M) | Closed | Plateaued; all candidates fail holdout Sharpe vs production under Phase D discipline |
| ML meta-allocator (Phases N–V) | Closed | Structural Pareto frontier on existing sleeve panel |
| HRP on 7-sleeve panel (Phases X–Z) | Closed | MAX_SLEEVE_WEIGHT cap creates over-defensiveness |
| Holdings-blend with Z1 (Phase AA) | Closed | Linear blend math has no complementarity; overlap adversely in stressed regimes |
| Trust-layer softening (Phase T) | Closed | Hard regime boundaries are NOT the residual gap cause (cleanly falsified) |
| Simple overlay geometry and threshold tuning | Closed | Mostly saturated throughout Phases 1–3.5 |
| Phase P–S trust-layer meta-allocators | Closed | Structural -0.013 holdout residual could not be closed by any trust-layer modification |
| Random ML feature zoo | Closed (never opened) | Correctly never started |

### Branches That Remain Open

| Branch | Priority | Why |
|----|----|----|
| Deployment-state intelligence | High | Not yet explored at this resolution |
| Trend/setup quality engine | High | Partially explored in signal validation, not yet in allocator |
| Smart re-risking engine | High | Phase 3.x work surfaced the problem; no solution exists yet |
| Cross-sectional leadership | Medium-High | ETF breadth signal exists but is coarse |
| Allocator objective redesign | Medium | Opportunity-quality awareness not yet built into the allocator |
| Decision-focused learning | Medium | Only safe after interpretable phases are stable |
| Cross-asset relational intelligence | Medium | Lead-lag diagnostics not yet formalized |
| PIT stock breadth (paid data gating) | High (data-gated) | Phase 5A diagnostic confirmed promising signal (+0.517% per 4w in calm_trend) |

------------------------------------------------------------------------

## 3. Strategic Diagnosis

### The Core Bottleneck

After 35+ sprints, the project's remaining performance gap is not caused by: - Missing risk discipline (already deep) - Insufficient regime confidence tuning (already optimized) - A better allocator family (closed, Phases A–M) - A trust layer on top of ML allocators (closed, Phases P–S) - A better sleeve blend (exhausted, Phases Q–V) - Holdings-level blending (exhausted, Phase U–AA)

The core bottleneck is **deployment intelligence**: the system knows the current state label but does not know the *quality* of that state. Specifically:

1.  **State quality is not modeled.** A `recovery_confirmed` label 2 weeks after a crash bottom is different from a `recovery_confirmed` label with broad breadth confirmation, rising quality stocks, credit spreads tightening, and 10 weeks of persistence. The current engine treats both identically.

2.  **Trend setup quality is not scored.** The system enters risk-on positions when the regime is favorable, but it doesn't distinguish a smooth, R²=0.90 trend from a noisy, choppy 52-week return with high drawdown along the path. Allocating more to cleaner trends is a structurally different and more defensible behavior than allocating more when the state label is favorable.

3.  **Re-risking is still too conservative.** The project documented this as early as Section 3.1–3.5 of the project journey. Recovery-confirmed capture is still only \~0.57 (production pin), meaning the system misses \~43% of the recovery-confirmed upside. This is the single largest identified opportunity in the project.

4.  **Leadership information is used coarsely.** The breadth signal distinguishes "above 50-day MA" from "below" across ETFs. It does not know whether leadership is coming from quality cyclicals (bullish signal) or speculative junk (fragile signal), or whether leadership concentration is rising (narrowing = warning) or falling (broadening = confirmation).

5.  **The allocator does not know its own confidence.** The allocator currently deploys based on the state label and sleeve quality scores. It has no notion of "I am highly confident this is a clean setup" versus "I am uncertain whether this is recovery or a dead cat bounce."

### The Opportunity

The frontier phases below target all five of these gaps. The expected improvement per phase: - **Deployment-state intelligence** (Phase 1): +0.10–0.25pp return, +0.02–0.05 Sharpe - **Trend quality engine** (Phase 2): +0.05–0.15pp return, +0.01–0.03 Sharpe, reduced whipsaw - **Smart re-risking** (Phase 3): +0.05–0.20pp return, improved recovery-confirmed capture - **Cross-sectional leadership** (Phase 4): +0.05–0.15pp return, better calm_trend and neutral capture - **Allocator objective redesign** (Phase 5): +0.02–0.10pp return, turnover reduction, better holdout stability - **Decision-focused learning** (Phase 6): uncertain, potentially +0.05–0.15pp, high overfitting risk - **Cross-asset relational intelligence** (Phase 7): +0.03–0.10pp, better regime transition timing

Total realistic frontier arc (Phases 1–7, cumulative, with synergy): **+0.3–0.8pp** above current best research.

------------------------------------------------------------------------

## 4. Literature and Source Review

*Full source review is in* `frontier_deployment_intelligence_source_review.md`. *Summary below.*

### AQR: Time-Series Momentum, Trend Quality, Defensive Equity

**What it suggests:** Moskowitz, Ooi, and Pedersen (2012) show that time-series momentum works across many assets and time horizons. AQR's later work on trend quality (Hurst, Ooi, Pedersen 2017) shows that trend signals with higher R² or lower realized noise generate better forward returns per unit of risk.

**What applies here:** The project already has time-series momentum sleeves. What is missing is a **trend quality filter** that allocates more capital to cleaner trends and less to noisy ones. The `trend_clarity_momentum` signal (Phase A) was a step in this direction. The frontier Phase 2 can formalize this into a per-ETF trend R² score and integrate it at the `offense_budget` checkpoint.

**What does not apply:** AQR's research covers hundreds of assets across futures markets. The ETF universe here is small (35 ETFs). The academic models typically require leverage and shorting. Neither applies here.

**Implementation warning:** Do not assume trend R² is always a better filter than momentum sign alone. In trending markets, R² can be high for both up-trends and down-trends. The signal is best used as a *modulator* of position size, not as an on/off switch.

**Phase placement:** Frontier Phase 2 (Trend/Setup Quality Engine).

------------------------------------------------------------------------

### Man Group: Crisis Alpha, Trend Following, Path Quality

**What it suggests:** Man Group's research (Winton/AHL adjacent, public papers) emphasizes that managed-futures trend following provides "crisis alpha" — positive returns during equity crises. Their research on signal quality shows that trend signals degrade in choppy, low-autocorrelation regimes and that "speed" selection (fast vs slow trend) improves out-of-sample quality.

**What applies here:** The anti-chop logic (already partially implemented in `composite_anti_chop_clarity`, Phase W-era research) is motivated by exactly this. The frontier Phase 2 should compute a per-ETF "trend persistence" or "autocorrelation score" that distinguishes orderly trends (high autocorrelation, low whipsaw probability) from choppy noise.

**What does not apply:** Man Group's live crisis alpha requires short positions. The project is long-only. The signal principles apply; the implementation cannot be copied directly.

**Phase placement:** Frontier Phases 2 (Trend Quality) and 4 (Cross-Sectional Leadership).

------------------------------------------------------------------------

### Moreira-Muir (2017): Volatility-Managed Portfolios

**What it suggests:** Moreira and Muir (2017, JPE) show that scaling positions inversely with realized volatility — independent of momentum sign — generates significant risk-adjusted improvement. The intuition is that low-volatility periods predict higher Sharpe in subsequent weeks.

**What applies here:** The project already has a `volatility_risk_overlay` checkpoint. What is missing is a *per-ETF* volatility-managed position size within the offense sleeve. Rather than applying a portfolio-level vol overlay, applying it at the individual ETF level within the top-N selection could reduce exposure during high-vol drawdown recovery while maintaining exposure during low-vol calm.

**What does not apply:** Moreira-Muir's full model assumes continuous daily rebalancing and full leverage flexibility. The project's weekly ETF universe with turnover discipline requires significant adaptation.

**Implementation warning:** Volatility management adds turnover unless it is slow (e.g., 13-week realized vol) or discretized into buckets. Model it at the `offense_budget` checkpoint and monitor turnover carefully.

**Phase placement:** Frontier Phase 2 (Trend Quality), as part of the volatility-adjusted momentum score.

------------------------------------------------------------------------

### Faber: Global Tactical Asset Allocation (GTAA)

**What it suggests:** Meb Faber's GTAA (2007, 2013) uses a simple 10-month moving-average rule across 5 asset classes to improve risk-adjusted returns dramatically. The core insight is that "being above the 200-day MA" is a reliable long-horizon filter for regime.

**What applies here:** The `taa_10m_sma` sleeve already implements this directly and is one of the project's most reliable calm-trend sleeves. The frontier extension would be to build a **confirmation-weight** system: how many asset classes are above their 10-month MA simultaneously? A higher count = broader confirmation = more weight to the offense sleeves.

**What does not apply:** Faber's GTAA works as a 5-class asset allocation, not a multi-ETF within-class tactical sleeve. The project's multi-sleeve architecture is already more sophisticated.

**Phase placement:** Frontier Phase 4 (Cross-Sectional Leadership) as a "leadership breadth" diagnostic.

------------------------------------------------------------------------

### Newfound / ReSolve / GestaltU: Fragility, Trend Quality, Rebalance Luck

**What it suggests:** Newfound Research (Hoffstein, Cady) extensively documents: 1. **Fragile alpha**: signals that look good on one rebalance schedule may break on another. ETF momentum strategies are particularly sensitive to measurement timing. 2. **Path dependency**: the same signal looks different depending on the path the market took to arrive at the current level. A market at the same level after a smooth rally vs after a sharp drawdown-and-recovery deserves different treatment. 3. **Trend quality**: not all moving-average crossovers are equal. A fast-crossing trend in a noisy environment generates more whipsaw and lower net returns than a slow, smooth trend.

**What applies here:** - Path dependency is directly relevant to the "good calm vs fragile calm" distinction the project wants to make in Frontier Phase 1. A calm state after a smooth 52-week grind upward is qualitatively different from a calm state after a V-shaped recovery. - The rebalance-luck literature motivates the "ensemble of measurement windows" approach: instead of a single lookback for trend, use a distribution of lookbacks to reduce sensitivity to single-point measurement. - Trend quality scoring (R², path clarity) is directly relevant to Frontier Phase 2.

**What does not apply:** ReSolve's specific ensemble approaches often require daily rebalancing or daily signal updates. The project uses weekly data.

**Phase placement:** Frontier Phases 1 (Deployment-State Quality) and 2 (Trend Setup Quality).

------------------------------------------------------------------------

### Robeco: Defensive Factor Research, Factor Timing

**What it suggests:** Robeco's research on low-volatility / defensive factors shows that: 1. Defensive factors genuinely outperform in drawdown environments even when risk-adjusted. 2. Factor timing (when to lean defensive vs. offensive) works modestly when conditioned on valuation spreads or macro regimes. 3. The quality-of-trend matters for factor timing: clean trends in macro indicators predict factor behavior better than raw momentum.

**What applies here:** The project already has a strong defensive sleeve (W1, structural defense). The gap is **factor-conditional timing** within the offensive sleeves. When quality signals (profitability, stability) are strong across the ETF universe, lean more toward the quality-momentum blends. When quality signals are deteriorating, reduce offensive exposure even if price momentum is still positive.

**What does not apply:** Robeco's specific BAB (betting-against-beta) and defensive factor research requires individual stock selection. The ETF universe cannot directly implement stock-level BAB.

**Phase placement:** Frontier Phase 4 (Cross-Sectional Leadership), as a sector quality diagnostic.

------------------------------------------------------------------------

### PIMCO / Bridgewater: Growth/Inflation/Liquidity Regime Framework

**What it suggests:** Bridgewater's All Weather framework decomposes market environments into quadrants: rising growth + rising inflation, rising growth + falling inflation, etc. PIMCO's research on credit regimes highlights that HYG/LQD spreads, credit expansion/contraction, and liquidity conditions are leading indicators for equity regimes.

**What applies here:** - The project already uses `dollar_pressure` and `macro_stress` rules at the architecture level. The frontier extension is to build a more explicit **growth/inflation regime vector** that feeds into the `regime_multipliers` checkpoint. When growth is decelerating + credit spreads widening → defensive tilt. When growth is accelerating + credit spreads tightening → offense tilt. - The HYG/LQD spread ratio is a clean, free, causal feature that the project underuses. It should be part of the deployment-state intelligence map.

**What does not apply:** Bridgewater's All Weather is a risk-parity-at-scale institutional strategy. The project's ETF portfolio cannot implement the exact framework. The macro regime framing is useful as a signal input, not as a portfolio construction method.

**Phase placement:** Frontier Phase 7 (Cross-Asset Relational Intelligence).

------------------------------------------------------------------------

### Lopez de Prado: HRP, Meta-Labeling, Purged CV, Triple-Barrier

**What it suggests:** - **HRP** is already in production. - **Meta-labeling** (AFML, Chapter 3): instead of learning to predict returns, first build a primary model that generates binary signals (deploy/don't deploy), then use a secondary model to learn when the primary model is likely correct. This avoids fitting to noisy return labels and focuses on decision quality. - **Triple-barrier labels** (AFML, Chapter 3): label events as "won before stop" (1) or "stopped out first" (-1) or "time-expired" (0), using symmetric barriers. This produces cleaner classification targets than raw forward returns. - **Purged cross-validation** (AFML, Chapter 7): for time-series ML, do not use standard k-fold. Use purging (remove samples near the train-test boundary) and embargoing (leave a gap between train and test) to prevent leakage.

**What applies here:** - Meta-labeling is directly applicable to Frontier Phase 6 (Decision-Focused Learning). The primary model already exists (the current production allocator). The secondary model should learn when to deploy more aggressively vs stay defensive. - Triple-barrier labels are the right label construction for this weekly-data, tactical-allocation context. - Purged CV must be used for any walk-forward ML experiment in this project. Standard k-fold will overstate performance.

**What does not apply:** Lopez de Prado's high-frequency microstructure content does not apply. The specific implementations in the AFML code are written for individual equity execution, not ETF tactical allocation.

**Phase placement:** Frontier Phase 6 (Decision-Focused Learning).

------------------------------------------------------------------------

### Decision-Focused Learning Literature

**What it suggests:** Recent ML literature (e.g., Elmachtoub-Grigas 2022 "SPO+", Donti et al. 2017, Wilder et al. 2019) proposes learning prediction models where the loss function is the *downstream decision cost*, not the prediction error. In a portfolio context, this means training a model to minimize portfolio regret (the cost of a wrong allocation decision), not to minimize return prediction error.

**What applies here:** The project's Phase O/P/Q experiments already discovered this empirically: models trained to minimize return prediction error did not minimize holdout drawdown or capture holdout upside. The frontier Phase 6 should explicitly build decision labels (deploy/wait, risk-on/risk-off, confidence-high/confidence-low) and train models with utility-weighted loss functions.

**Implementation warning:** Decision-focused learning is among the highest overfitting-risk approaches in this project. It should come AFTER interpretable phases (1–5) are stable. The training labels must be defined before looking at the test data.

**Phase placement:** Frontier Phase 6 (Decision-Focused Learning).

------------------------------------------------------------------------

## 5. The Seven Frontier Directions

### A. Deployment-State Intelligence

**Core concept:** The current regime engine produces state labels (`calm_trend`, `neutral_mixed`, `recovery_confirmed`, `recovery_fragile`, `stressed_panic`, `strong_neutral`). But each label is a distribution of sub-states with very different forward return implications. A `recovery_confirmed` that is broad (all sectors participating), smooth (high R² trend path), and persistent (6+ weeks) is fundamentally different from a `recovery_confirmed` that is narrow (only tech), choppy, and 2 weeks old.

**State quality dimensions:** - **Breadth quality**: is participation broad or narrow? - **Path quality**: is the trend smooth or choppy? R² of 4-week rolling price path. - **Persistence quality**: how many consecutive weeks in the current state? - **Transition history**: did we arrive from a good state or from stressed_panic? - **Leadership quality**: are quality/defensive leaders confirming? Or is it just speculative junk rallying? - **Credit confirmation**: is HYG/LQD spread tightening (confirming) or widening (warning)? - **Macro backdrop**: growth-inflation quadrant, dollar pressure

**State quality labels (to build):** - `good_calm` (high breadth, smooth trend, long persistence) vs `fragile_calm` (narrowing breadth, junk-led) - `real_recovery` (broad, confirmed, persistent) vs `fake_recovery` (narrow, choppy, short) - `healthy_neutral` vs `deteriorating_neutral` (signals diverging, quality declining) - `high_quality_risk_on` vs `low_quality_risk_on` - `late_cycle` (risk-on but momentum diverging from breadth, credit spreads not tight)

### B. Trend/Setup Quality

**Core concept:** Not all trends deserve the same capital. A trend with R² = 0.92, low realized vol, strong breadth confirmation, and positive momentum across multiple lookback windows is worth much more than a trend with R² = 0.40, high noise, and momentum confined to one lookback window.

**Quality dimensions:** - **R² of trend regression** (52-week linear fit to price): measures path smoothness - **Whipsaw probability**: frequency of sign reversals over rolling 26 weeks - **Trend persistence**: how long has the trend been positive? - **Breadth confirmation**: is the ETF's trend supported by peer breadth? - **Volatility ratio**: trailing 13w vol / trailing 52w vol (rising = deteriorating quality) - **Moving-average distance**: distance from 52-week MA as a setup-quality measure - **Multi-window agreement**: do 13w, 26w, and 52w all agree on direction?

**Anti-chop filter:** In a noisy environment (whipsaw probability \> threshold), reduce position size or require a higher confirmation bar before adding exposure. This was partially explored in `composite_anti_chop_clarity` but never formalized as a per-ETF signal.

### C. Smart Re-Risking

**Core concept:** The project's most persistent documented failure mode is slow re-entry after stress. Recovery-confirmed capture in production is approximately 57%, meaning the portfolio misses 43% of the available recovery-confirmed upside. The goal is not to become more aggressive — it is to be *faster when quality is high* and still conservative when quality is unclear.

**Re-risking quality dimensions:** - **Recovery quality score**: breadth-confirmed, smooth path, rising quality - **Transition persistence**: how many consecutive weeks of improving state? - **Credit confirmation**: HYG/LQD spread trajectory - **Drawdown exit confirmation**: distance from recent 52-week high recovering - **Volume/breadth acceleration**: participation broadening week-over-week

**Asymmetric logic:** - Fast re-entry (higher `transition_rerisk_smoothing` weight) when recovery quality score is high - Conservative hold when recovery quality score is mixed - Never weaken stressed_panic defense regardless of re-risking speed

### D. Cross-Sectional Leadership Systems

**Core concept:** The project measures breadth as "ETF above 50-day MA" or "ETF above 200-day MA." This is coarse. Better questions: Which ETFs are leading? Are leaders quality or speculative? Is leadership broadening or narrowing? Are the leaders from this week the same as last week (persistence) or rotating quickly (instability)?

**Leadership dimensions:** - **Leadership type**: QQQ/SPY (quality growth), HYG/JNK (credit/risk), small-cap (IWM), EM (VWO/EFA), cyclicals (XLY/XLI), defensives (XLU/XLP) - **Leadership breadth score**: number of ETFs in top-quartile momentum - **Leadership concentration**: Herfindahl of momentum rankings (high HHI = narrow) - **Rotation persistence**: rank-correlation of this week's leaders vs last week - **Risk-on vs defensive leadership**: is offensive leadership leading defensive by \>X%? - **Cross-asset confirmation**: bonds / credit / equity alignment

**Implementation approach:** - Build a per-week leadership score matrix from existing ETF data - Aggregate into a "breadth and leadership quality" composite - Feed as a modifier at the `regime_multipliers` or `offense_budget` checkpoint - Do NOT use stock-level breadth here — ETF-level only (free data)

### E. Allocator Objective Redesign

**Core concept:** The current allocator uses HRP with state-conditioned regime multipliers. This is good diversification logic. The frontier extension is to make the allocator explicitly aware of **deployment confidence**: when the deployment-state intelligence system (Phase 1) says quality is high, allow more concentration; when quality is ambiguous, require more diversification.

**New objective dimensions:** - **Confidence-weighted risk budget**: scale offense budget by deployment quality score - **Opportunity-minus-fragility objective**: maximize `quality_of_opportunity - fragility_penalty` - **Tail-aware deployment score**: how much expected CVaR does this allocation add vs. the BIL alternative? - **Transition-adjusted risk budget**: when transitioning from stress → recovery, scale up only as quality is confirmed - **Turnover penalty with context**: higher penalty during low-quality states, lower during clean setups

**Critical constraint:** The allocator should NEVER reduce the stressed_panic defense. The confidence-adjustment logic applies only to offensive allocation, not to the defensive floor.

### F. Decision-Focused Learning

**Core concept:** Rather than predicting return magnitude, learn which *deployment decisions* are correct. The primary model (production allocator) already makes decisions. A secondary meta-model should learn when those decisions are likely to be optimal vs. when a more conservative posture would have been better.

**Label construction:** - **Deploy/wait label**: did the portfolio beat BIL over the next 4 weeks? (threshold-adjusted) - **Confidence label**: was the forward Sharpe over 8 weeks \> production's rolling average? - **Re-risk label**: was entering risk-on this week (given the state) profitable over 13 weeks? - **Triple-barrier label**: did the portfolio reach the profit target before the loss threshold?

**Training approach:** - Walk-forward expanding windows, no leakage - Purged cross-validation (4-week embargo at train/test boundary) - Calibrated probability output (not hard binary) - Features: causal-only state features, no forward-looking signals

**Why this comes last:** Decision-focused learning requires the interpretable phases (1–5) to be stable first. It is most valuable as a *trust modifier* — learning when the interpretable rules are likely correct — not as a replacement for them.

### G. Cross-Asset Relational Intelligence

**Core concept:** Asset classes lead and lag each other. Credit spreads typically lead equity by 2–4 weeks in regime transitions. Small caps lead large caps in early recovery. Gold leads defensively-oriented regimes. The project currently captures some of these through the `dollar_pressure` and `macro_stress` rules, but not systematically.

**Lead-lag relationships to model:** - TLT/IEF leading SPY (bonds pricing regime change ahead of equities) - HYG/LQD spread leading equity regime transitions - IWM/SPY ratio as a risk appetite indicator - GLD as a macro stress / real-rate signal - PDBC/DBA as an inflation / commodity-cycle signal - Dollar (UUP) leading EM and commodities - VIX term structure (VIX vs VXX relationship) as fear indicator

**Implementation approach:** - Compute rolling lead-lag correlations (8-week and 16-week) between these pairs - Measure rolling stability of these relationships (a stable lead-lag is more usable than an unstable one) - Build an interpretable "cross-asset confirmation score" as a composite of alignment signals - Start with static linear lead-lag diagnostics before any graph/attention-style models

**Why this comes later (Phase 7):** Cross-asset relational intelligence is powerful but complex. The simpler, more interpretable phases (1–5) should be validated first. The diagnostic value of this work (understanding *when* cross-asset signals are reliable) may be more important than its direct portfolio value.

------------------------------------------------------------------------

## 6. Recommended Phase Order

The proposed phase order is accepted as reasonable. The following revisions are made based on the project history:

1.  **Phases 1 + 2 are intentionally coupled.** Deployment-state quality and trend quality both feed the same checkpoint (`offense_budget` and `regime_multipliers`). Running them consecutively (not simultaneously) prevents confounding.

2.  **Phase 3 (Re-Risking) should draw on Phase 1's quality scores.** Re-riskng without quality scoring is just "react faster," which the project history shows leads to more false positives. Phase 1 first.

3.  **Phase 5 (Allocator Objective) should come after Phases 1–4** have generated the quality signals the objective function needs to use. It is an integration phase.

4.  **Phase 6 (Decision-Focused Learning) is correctly placed last** before the new sleeve evaluation and data expansion decisions.

5.  **Phases 8–10 are placeholders** — do not open until Phase 1–7 diagnostics reveal what is missing. Avoid sprints based on hypothetical future findings.

### Revised Phase Summary

| Phase | Name | Type | Expected Value |
|----|----|----|----|
| 0 | Stabilization Confirmation | Diagnostic | Required prerequisite |
| 1 | Deployment-State Intelligence Map | Diagnostic → Portfolio | High |
| 2 | Trend/Setup Quality Engine | Diagnostic → Portfolio | High |
| 3 | Smart Re-Risking Engine | Portfolio modifier | Medium-High |
| 4 | Cross-Sectional Leadership System | Diagnostic → Portfolio | Medium-High |
| 5 | Deployment-Quality Allocator Objective | Portfolio modifier | Medium |
| 6 | Decision-Focused Learning | Sandbox → Portfolio | Medium (high overfitting risk) |
| 7 | Cross-Asset Relational Intelligence | Diagnostic → Portfolio | Medium |
| 8 | New Sleeve / Opportunity Module Design | Layer 2 | Only if Phases 1–7 reveal gap |
| 9 | Optional Data Expansion | Data-gated | Only if justified by diagnostics |
| 10 | Final Production Candidate Evaluation | Governance | Required before promotion |

------------------------------------------------------------------------

## 7. Phase Detail Specifications

### Frontier Phase 0: Stabilization Confirmation

**Purpose:** Confirm that the wrapper produces exact GGG baseline and that all safe checkpoints are accessible and consistent. This is a prerequisite gate, not a research sprint.

**Status:** COMPLETED during Deployment Architecture Stabilization Sprint.

**Evidence:** - Net-return max error: 2.116e-16 (machine epsilon) - Return correlation vs saved GGG: 1.0000000000 - All safe checkpoints: present, 1110 rows, expected column dimensions

**Gate to proceed:** Pass (already completed).

------------------------------------------------------------------------

### Frontier Phase 1: Deployment-State Intelligence Map

**Purpose:** Build a principled, causal map of state quality. Answer: "Not just what state are we in, but how good is this state?"

**Hypothesis:** States of equal label but different quality (breadth, path smoothness, persistence, confirmation) have materially different forward returns. If the allocator can distinguish high-quality from low-quality instances of the same state label, it can deploy more confidently in high-quality instances and conserve capital in low-quality instances.

**Inputs needed (all free data, all causal):** - `data/01_raw/`: ETF price histories, existing market state features - `data/02_layer1_signals/`: existing breadth, momentum, trend signals - `data/03_layer2_strategy/market_state_history.csv`: existing state labels - `scripts/allocator_checkpoint_wrapper.py`: baseline wrapper

**Output signals (to build):** - `signal_state_breadth_quality` — breadth-confirmed fraction within current state (4w rolling, 1w lag) - `signal_state_path_clarity` — R² of 13-week price regression vs SPY, winsorized, 1w lag - `signal_state_persistence_score` — number of consecutive weeks in current label (capped at 12w) - `signal_state_credit_confirmation` — HYG/LQD 4w trend direction, 1w lag - `signal_state_leadership_quality` — fraction of offensive ETFs above both 50d and 200d MA, 1w lag - `signal_deployment_quality_composite` — z-scored blend of above, updated weekly

**Scripts to create:** - `scripts/phase_frontier1_state_quality_signals.py`: compute the above signals, output to `data/02_layer1_signals/` - `scripts/phase_frontier1_state_quality_validation.py`: validate ICs by state, run bootstrap significance tests - `scripts/phase_frontier1_wrapper_diagnostic.py`: load checkpoint `regime_multipliers`, build a deployment-quality modifier, apply to `offense_budget` checkpoint, compare returns vs GGG baseline (no write to production)

**Data outputs:** - `data/research/frontier_phase1/state_quality_signals.csv` - `data/research/frontier_phase1/state_quality_ic_by_state.csv` - `data/research/frontier_phase1/state_quality_composite_validation.csv` - `data/research/frontier_phase1/wrapper_diagnostic_results.csv`

**Markdown report:** - `docs/research/frontier_phase1_deployment_state_intelligence_report.md`

**Validation tests:** 1. IC analysis: is `signal_deployment_quality_composite` predictive of 4w forward SPY return within each state label? 2. State-conditional IC: does quality score IC differ across states (e.g., higher IC in recovery states than calm states)? 3. Bootstrap: block-bootstrap significance of IC at 0.05 level 4. Monotonicity check: does forward return increase monotonically across quality quintiles? 5. Regime stability: does the quality score shift meaningfully between true "good" and "fragile" periods the project can identify ex post?

**Acceptance gates:** - IC of composite quality signal \> 0.05 in at least two states (annualized, sign-consistent) - Monotonic improvement from quality quintile 1 → 5 in at least 3 of 5 state labels - Bootstrap P(IC \> 0) ≥ 0.70

**Rejection criteria:** - IC \< 0.02 across all states → signal is noise, stop this sub-track - If quality high vs quality low periods produce indistinguishable forward returns → state quality not useful

**Common failure modes:** - Quality composite correlated with existing momentum signals → redundant, needs orthogonalization - Persistence score dominates → already partially captured by state smoothing in the engine - IC driven by single year (2008/2009) → winsorize and check period-specific robustness

**Overfitting risks:** - Do NOT optimize the composite weights on the validation set. Use equal weights or pre-defined economic weights. - Do NOT use state quality labels that require future information (no hindsight state labels). - Do NOT allow quality signal to vary the stressed_panic defense.

**Implementation guidelines:** - All signals computed with 1-week lag (no look-ahead) - Load checkpoints read-only, no writes to production paths - Compare against GGG baseline using the no-modifier wrapper - Report state-conditional returns for all 6 states

**Suggested first implementation prompt:** \> "Implement `scripts/phase_frontier1_state_quality_signals.py`. This script should compute six causal, 1-week-lagged quality signals: state breadth quality (fraction of offensive ETFs above both 50d and 200d MA), path clarity (13-week R² of SPY price regression), state persistence score (consecutive weeks in current state), credit confirmation (HYG/LQD 4-week trend), leadership quality (breadth-weighted offensive momentum fraction), and a composite z-scored blend. Output to `data/research/frontier_phase1/state_quality_signals.csv`. Do not modify any production files. No look-ahead allowed."

**Wrapper connection:** Read from `regime_multipliers` checkpoint. Diagnostic-only wrapper run (no write).

**Mode:** Diagnostic-only in Phase 1. Portfolio pass-through candidate only if IC gates pass.

**Free data:** Yes (all existing ETF data).

**Paid data requirement:** No.

**Expected improvement:** Returns: +0.1–0.25pp (if IC gates pass). Sharpe: +0.02–0.05. Drawdown: neutral to +0.2pp improvement (no weakening).

------------------------------------------------------------------------

### Frontier Phase 2: Trend / Setup Quality Engine

**Purpose:** Build a per-ETF trend quality score that answers: "Is this trend worth following?" Distinguish smooth, persistent, broadly-confirmed trends from noisy, choppy, unstable ones.

**Hypothesis:** ETFs with high-quality trends (high R², low whipsaw, broad confirmation, multi-window agreement) generate better forward returns per unit of risk than ETFs with noisy trends. Allocating more offense capital to high-quality-trend ETFs, and less to noisy-trend ETFs, improves the portfolio's information ratio.

**Inputs needed:** - All existing ETF price history - Phase 1 breadth confirmation signal - Existing `trend_clarity_momentum` signal (Phase A, validated)

**Output signals:** - `signal_trend_r2` — per-ETF 52-week linear R² (1w lag) - `signal_trend_persistence` — consecutive weeks of positive trend (capped at 26w) - `signal_whipsaw_probability` — frequency of 4w sign reversals over rolling 26 weeks - `signal_moving_average_distance_z` — z-scored distance from 52w MA within ETF history - `signal_multi_window_agreement` — whether 13w, 26w, and 52w momentum agree (0 to 3 count) - `signal_trend_quality_composite` — per-ETF blend of above

**Scripts to create:** - `scripts/phase_frontier2_trend_quality_signals.py` - `scripts/phase_frontier2_trend_quality_validation.py` - `scripts/phase_frontier2_wrapper_experiment.py` — build a trend-quality modifier at the `offense_budget` checkpoint

**Validation tests:** 1. Cross-sectional IC: does `signal_trend_quality_composite` predict next-week ETF excess return cross-sectionally? 2. Quantile backtests: high quality quintile vs low quality quintile forward return 3. Whipsaw reduction: does applying the quality filter reduce average turnover cost without sacrificing returns? 4. State-conditional robustness: does quality signal help in calm_trend and recovery states specifically?

**Acceptance gates:** - Per-ETF cross-sectional IC \> 0.03 (sign-consistent) - Quintile 5 vs Quintile 1 forward return spread \> 1.5pp annualized - Quality filter does not meaningfully increase turnover (\< 2pp per year)

**Rejection criteria:** - Cross-sectional IC \< 0.01 → signal is ETF-universe-noise-dominated - If high quality = high past return (momentum tautology) → already in stack, drop

**Overfitting risks:** - R² by itself favors assets that have trended strongly recently — verify it is not a past-return proxy - Do not fit the composite weights to maximize backtested IC

**Suggested first implementation prompt:** \> "Implement `scripts/phase_frontier2_trend_quality_signals.py`. Compute six per-ETF trend quality signals: 52-week linear R² (1w lag), consecutive weeks of positive trend, 26-week whipsaw probability (frequency of 4w sign reversals), z-scored 52w MA distance, multi-window momentum agreement count (13w/26w/52w), and a composite. All signals must be 1-week lagged. Output as panel CSVs to `data/research/frontier_phase2/`. No production files modified."

**Wrapper connection:** Modify `offense_budget` checkpoint. Diagnostic-only initially.

**Mode:** Diagnostic-only in Phase 2 validation. Portfolio pass-through candidate if acceptance gates pass.

**Free data:** Yes.

**Expected improvement:** Returns: +0.05–0.15pp. Sharpe: +0.01–0.03. Turnover: potentially reduced by better ETF selection quality.

------------------------------------------------------------------------

### Frontier Phase 3: Smart Re-Risking Engine

**Purpose:** Fix the conservative re-entry problem documented throughout Phases 3.x and later. Build a principled re-risking quality score that allows faster re-entry when quality is confirmed, while maintaining strict stressed_panic defense.

**Hypothesis:** The project's recovery-confirmed capture is \~57% (43% of recovery-confirmed upside is missed). A significant fraction of this is caused by the current re-risking smoothing being uniform across recovery quality. If high-quality recoveries trigger faster re-risking and low-quality recoveries trigger slower re-risking, overall recovery capture improves without weakening the defensive floor.

**Key constraint:** This phase must NOT weaken `stressed_panic` defense. Recovery quality scoring applies only to the re-entry phase, not to the exit phase.

**Inputs needed:** - Phase 1 deployment quality composite - Phase 2 trend quality composite (per-ETF) - `data/03_layer2_strategy/market_state_history.csv` - `transition_rerisk_smoothing` checkpoint

**Output signals:** - `signal_recovery_quality_score` — weighted blend of breadth confirmation, path clarity, credit confirmation, persistence (Phase 1 sub-signals, re-weighted for recovery context) - `signal_transition_quality` — was the state transition from stressed to recovery fast (V-shape) or slow (grinding recovery)? Different re-risking speeds are appropriate for each.

**Re-risking rule design:**

```         
if market_state in ['recovery_confirmed', 'recovery_fragile']:
    rr_speed = base_rr_speed × (1 + recovery_quality_boost × quality_score)
elif market_state == 'stressed_panic':
    rr_speed = 0  # no re-risk during stress regardless of quality
else:
    rr_speed = base_rr_speed  # unchanged
```

**Acceptance gates:** - Recovery-confirmed capture improves by ≥ 5pp vs GGG baseline - Holdout recovery-confirmed capture ≥ baseline (no regression) - Stressed-panic sharpe unchanged or better - Turnover increase \< 3pp per year

**Rejection criteria:** - If quality-gated re-risking only moves weight by \< 2pp on average → signal is not strong enough - If recovery-confirmed capture improvement comes with \> 1.5pp drawdown worsening → unacceptable trade

**Overfitting risks:** - Do not tune recovery quality thresholds to maximize recovery capture in-sample - The quality score weights should come from Phase 1's pre-defined economic weights

**Suggested first implementation prompt:** \> "Using Phase 1's state quality signals and Phase 2's trend quality signals, implement `scripts/phase_frontier3_smart_rerisk_engine.py`. Build a recovery quality score (recovery breadth, path clarity, credit confirmation, state persistence). Create a wrapper modifier that scales `transition_rerisk_smoothing` by (1 + boost × quality_score) inside recovery states, while leaving stressed_panic `rr_speed = 0` unconditionally. Run diagnostic comparison vs GGG baseline using the checkpoint wrapper. Report: recovery-confirmed capture, stressed-panic sharpe, turnover. No production files modified."

**Wrapper connection:** Modify `transition_rerisk_smoothing` checkpoint.

**Mode:** Portfolio pass-through candidate if acceptance gates pass.

**Free data:** Yes.

**Expected improvement:** Recovery-confirmed capture: +5–20pp. Returns: +0.05–0.20pp. Sharpe: +0.01–0.04.

------------------------------------------------------------------------

### Frontier Phase 4: Cross-Sectional Leadership System

**Purpose:** Build a systematic measurement of where market leadership is coming from, how broad it is, and whether it is consistent with a durable risk-on environment.

**Hypothesis:** Leadership type and breadth contain information about the *quality* and *durability* of the current risk-on environment beyond what the current regime engine captures. Broad, quality-led, persistent leadership predicts better forward returns than narrow, junk-led, unstable leadership.

**Leadership signals:** - `signal_leadership_breadth` — fraction of offensive ETFs in top-half momentum decile (1w lag) - `signal_leadership_concentration` — HHI of momentum rankings among offensive ETFs - `signal_leadership_type_quality` — weighted average of quality-oriented ETF momentum rank (QQQ, XLK, VUG) vs. speculative (HYG, IWM, VWO) - `signal_leadership_rotation_persistence` — rank correlation of top-quartile ETFs this week vs. 4 weeks ago - `signal_leadership_credit_alignment` — HYG/LQD momentum aligning with (or diverging from) equity leadership

**Scripts to create:** - `scripts/phase_frontier4_leadership_signals.py` - `scripts/phase_frontier4_leadership_validation.py` - `scripts/phase_frontier4_wrapper_experiment.py`

**Acceptance gates:** - At least 2 of 5 leadership signals show IC \> 0.03 in calm_trend or recovery states - Composite leadership quality score shows Sharpe spread \> 0.15 between top and bottom quintiles - No hidden SPY beta from leadership signals (beta \< 0.10 incremental)

**Overfitting risks:** - Leadership signals are highly correlated with existing breadth signals — check residual IC after controlling for existing signals - Do not optimize leadership composite weights on backtested IC

**Suggested first implementation prompt:** \> "Implement `scripts/phase_frontier4_leadership_signals.py`. Build five causal, 1-week-lagged leadership signals: leadership breadth (fraction of offensive ETFs in top-half momentum), leadership concentration (HHI of momentum rankings), leadership quality type (QQQ/XLK momentum vs HYG/IWM momentum), rotation persistence (rank correlation of top-quartile ETFs week vs -4), and credit alignment (HYG/LQD momentum vs equity momentum). Output to `data/research/frontier_phase4/`. No production files modified."

**Wrapper connection:** Modify `regime_multipliers` or `offense_budget` checkpoint.

**Mode:** Diagnostic-only in Phase 4 validation. Portfolio pass-through if acceptance gates pass.

**Free data:** Yes.

**Expected improvement:** Calm_trend capture: +0.05–0.15pp. Sharpe: +0.01–0.03. Best state: calm_trend and strong_neutral.

------------------------------------------------------------------------

### Frontier Phase 5: Deployment-Quality Allocator Objective

**Purpose:** Redesign the allocator objective to explicitly incorporate deployment quality signals from Phases 1–4. Move from static HRP diversification toward a confidence-weighted, opportunity-quality-aware allocation.

**Hypothesis:** The allocator currently has no notion of "I am very confident this is a clean setup" vs "I am uncertain whether to deploy." If the allocator can scale its offense budget by a deployment quality composite (built from Phases 1–4), it will take larger positions in high-confidence environments and more conservative positions in uncertain environments, improving risk-adjusted returns.

**Design:** - Base allocation: existing HRP with regime multipliers (unchanged) - Overlay: scale `offense_budget` by `(1 + alpha × deployment_quality_composite)` - Constraint: `alpha` is bounded such that max offense budget increase ≤ 15% - Anti-chop constraint: if trend quality (Phase 2) is below threshold, do NOT increase offense budget regardless of state quality

**Acceptance gates:** - Full-history Sharpe improvement ≥ +0.02 vs GGG baseline - Holdout Sharpe improvement ≥ 0 vs GGG baseline (no regression) - Turnover increase ≤ 2pp per year - Stressed-panic allocation unchanged

**Overfitting risks:** - `alpha` must be fixed before looking at holdout results - Do not optimize `alpha` on the full history

**Suggested first implementation prompt:** \> "Using the deployment quality composite from Phase 1 and trend quality composite from Phase 2, implement `scripts/phase_frontier5_deployment_quality_allocator.py`. Create a wrapper modifier that scales the `offense_budget` checkpoint by `(1 + 0.10 × deployment_quality_composite)` where the composite is bounded [-1, +1] and only active in non-stressed states. Compare vs GGG baseline across full, holdout, rolling-origin, and state-conditional windows. Report all Phase D metrics."

**Mode:** Portfolio pass-through candidate if acceptance gates pass.

**Free data:** Yes.

**Expected improvement:** Returns: +0.02–0.10pp. Sharpe: +0.01–0.03. Turnover: neutral.

------------------------------------------------------------------------

### Frontier Phase 6: Decision-Focused Learning

**Purpose:** Learn which deployment decisions are correct, not which returns are highest. Build a meta-layer that identifies when to trust the interpretable signals from Phases 1–5 vs. when to fall back to the production baseline.

**Hypothesis:** Even with high-quality interpretable signals (Phases 1–5), there will be periods where those signals are misleading and the production allocator's conservative posture is correct. A secondary model trained on deployment decision quality (did this deployment decision outperform the BIL alternative?) can improve the overall allocation by being more aggressive when interpretable signals are reliable and more conservative when they are not.

**Label construction:** - Primary label: `deploy_quality_label[t]` = 1 if deploying offense (vs. BIL) over next 4 weeks generates Sharpe \> 0.5 annualized, 0 otherwise. **Computed using 1-week delay on all features, 4-week forward window** (no look-ahead). - Secondary label: `rerisk_quality_label[t]` = 1 if transitioning to risk-on was profitable over next 8 weeks vs. staying defensive. - Triple-barrier variant: label = 1 if forward 8w return exceeds +2% before drawdown of -1.5%; label = -1 if drawdown occurs first; label = 0 otherwise.

**Model requirements:** - Walk-forward expanding window training only - Minimum 260-week training window before first prediction - Purged cross-validation: 4-week embargo at train/test boundary - Model: calibrated logistic regression or gradient-boosted classifier with max_depth ≤ 3 - Features: causal Phase 1–4 quality signals only (no price look-ahead)

**Acceptance gates:** - Out-of-sample decision accuracy \> 58% (vs 50% naive) - Applying the decision labels to the production allocator improves holdout Sharpe ≥ +0.01 - Bootstrap support P(cand \> prod on holdout) ≥ 60% - Deployment accuracy is higher than a simpler regime-state rule (Phase 1 quality \> threshold)

**Rejection criteria:** - Decision accuracy \< 53% → labels contain too much noise - If a simple momentum rule (past 4w return \> 0) achieves the same accuracy → signal is not adding value

**Overfitting risks (highest in the project):** - NEVER optimize label thresholds on the full history - NEVER use holdout data to select model hyperparameters - MUST use purged cross-validation - MUST report results on the pre-declared holdout window only - If the model is more than 80% correlated with the Phase 1–4 quality composite, it is likely redundant

**Suggested first implementation prompt:** \> "Implement `scripts/phase_frontier6_decision_labels.py`. Build three walk-forward-safe decision quality labels: `deploy_quality_label` (1 if next 4w offense return Sharpe \> 0.5, 0 otherwise), `rerisk_quality_label` (1 if entering risk-on was profitable over next 8w vs defensive), and `triple_barrier_label` (1/-1/0 based on profit/loss threshold before expiry). All labels computed with full 1-week lag on features, NO look-ahead. Output labeled dataset to `data/research/frontier_phase6/decision_labels.csv`. Document the embargo window. Do NOT train any model yet."

**Mode:** Sandbox → Portfolio pass-through. This phase is research-only until acceptance gates pass.

**Free data:** Yes.

**Expected improvement:** Returns: +0.05–0.15pp. Sharpe: +0.01–0.03 (if it works). Very high overfitting risk.

------------------------------------------------------------------------

### Frontier Phase 7: Cross-Asset Relational Intelligence

**Purpose:** Model lead-lag relationships between asset classes and build a systematic cross-asset confirmation signal for regime transitions.

**Hypothesis:** Credit spreads lead equity regimes by 2–4 weeks. Small-cap relative strength leads broad equity by 1–2 weeks. Dollar strength leads EM and commodity regimes by 2–6 weeks. If these lead-lag relationships are stable, they can improve the timing of regime transitions (re-risking and de-risking).

**Lead-lag pairs to build:** - HYG/LQD vs SPY (credit leading equity) - TLT/IEF 4w momentum vs SPY (bond market pricing regime change) - IWM/SPY ratio momentum vs broad equity (small-cap as risk appetite signal) - UUP 4w momentum vs VWO/EFA (dollar leading EM) - GLD 4w momentum vs TLT (real rates / macro stress signal)

**Stability monitoring:** For each pair, compute a rolling 52-week lead-lag correlation and a rolling 104-week stability score. A lead-lag that is stable over 104 weeks and consistent across multiple historical periods is more usable than an unstable relationship.

**Implementation approach:** 1. Start with simple fixed-lag correlations (1w, 2w, 4w leads) 2. Build a cross-asset confirmation composite: how many pairs are aligned with the current regime direction? 3. Use composite as a modifier at the `transition_rerisk_smoothing` or `regime_multipliers` checkpoint 4. Monitor rolling stability of each relationship — deactivate when unstable

**Acceptance gates:** - At least 3 of 5 lead-lag pairs show stable (52w rolling correlation \> 0.20) lead-lag relationship over 70%+ of history - Cross-asset confirmation composite IC \> 0.03 in regime transition periods - No hidden beta from lead-lag signals

**Suggested first implementation prompt:** \> "Implement `scripts/phase_frontier7_crossasset_leadlag.py`. For each of five cross-asset pairs (HYG/LQD vs SPY, TLT vs SPY, IWM/SPY ratio vs equity breadth, UUP vs VWO, GLD vs TLT), compute 1w, 2w, and 4w lead-lag correlations using 52-week rolling windows. Measure stability as the fraction of 52-week windows with correlation \> 0.15. Output stability diagnostics to `data/research/frontier_phase7/crossasset_leadlag_diagnostics.csv`. This is diagnostic-only. No portfolio candidates yet."

**Mode:** Diagnostic-only in Phase 7 validation. Portfolio pass-through only if lead-lag stability gates pass.

**Free data:** Yes.

**Expected improvement:** Returns: +0.03–0.10pp. Best states: recovery transitions.

------------------------------------------------------------------------

### Frontier Phase 8: New Sleeve / Opportunity Module Design

**Purpose:** If Phases 1–7 diagnostics reveal a return stream that is genuinely missing from the current sleeve panel, design a new sleeve to fill it.

**Decision gate to open Phase 8:** At least one of the following: - Phase 7 finds a cross-asset signal with IC \> 0.05 that is NOT captured by any existing sleeve - Phase 4 finds a leadership type that deserves its own sleeve (e.g., EM-specific momentum) - Phase 1 finds a state-quality dimension that cannot be expressed through the existing checkpoints

**If Phase 8 is opened:** Use the Phase W sleeve design discipline: - Single sleeve hypothesis, economically motivated - Tested standalone before integration - Distinctness verification (correlation to existing sleeve panel \< 0.40) - Portfolio integration test at naive equal weight, then allocator-conditional

**Do NOT open Phase 8** without diagnostic evidence from Phases 1–7.

------------------------------------------------------------------------

### Frontier Phase 9: Optional Data Expansion

**Purpose:** If diagnostics from Phases 1–7 reveal a specific signal that requires PIT stock breadth or a paid data source, define the data acquisition criteria.

**Pre-condition to open Phase 9:** - Phase 5A (PIT stock breadth diagnostic) already confirmed: +0.517% per 4w SPY lift in calm_trend from stock breadth signal - Norgate Data US Stocks Platinum/Diamond is the recommended data path - Phase 9 should be opened only after the frontier Phases 1–4 are complete, so the stock breadth data augments a more mature signal stack

**If Phase 9 is opened:** 1. Define minimum acceptable data quality: PIT membership, delisting coverage, price continuity 2. Run `scripts/build_pit_stock_breadth_panel.py` and validate leakage checklist 3. Build breadth signals and run the same IC validation as Phase 1 4. Only build portfolio candidates after validation passes

------------------------------------------------------------------------

### Frontier Phase 10: Final Production Candidate Evaluation

**Purpose:** Evaluate the full frontier stack as a production candidate using the Phase D promotion rules.

**Required before Phase 10:** - Phases 1–4 completed and at least 2 have passed acceptance gates - Phase 5 completed - Candidate strategy defined as a specific wrapper modifier combination - Holdout window pre-declared (do not change after declaration)

**Evaluation requirements:** - Full-history evaluation against production pin, shadow pin, and all frontier phase references - Phase D 8-gate evaluation - Rolling-origin evaluation (104-week windows, 52-week step) - Block bootstrap (2000 iterations, 13-week blocks) - State-by-state return and Sharpe (all 6 states) - Cost/turnover analysis - Hidden beta and BIL exposure analysis - SPY/offense/defense/BIL exposure diagnostics

**Promotion gates (per existing Phase D rules):** - Full-Δ ≥ +0.015 vs production - Holdout-Δ ≥ 0 vs production - Holdout Sharpe Δ ≥ -0.02 vs production - Rolling win rate ≥ 55% vs production - Rolling mean Δ \> 0 vs production - Bootstrap P(cand \> prod on holdout) ≥ 60% - Max DD Δ ≥ -0.01 (not more than 1pp worse) - CVaR Δ ≥ -0.002

**Do NOT promote without passing all 8 gates.**

------------------------------------------------------------------------

## 8. Implementation Guidelines

These guidelines govern all frontier phase sprints. No exceptions without explicit justification in the sprint report.

### Wrapper Rules

1.  **Use the exact wrapper baseline.** Every frontier experiment starts from the no-modifier wrapper that reproduces GGG to machine precision.
2.  **Read-only checkpoints first.** Every sprint starts with diagnostic-only wrapper runs before any modifier is applied.
3.  **Safe checkpoints only** for portfolio-pass-through candidates. The dangerous checkpoints (`raw_sleeve_targets`, `defense_budget`, `cost_turnover_calculation`) may be read for diagnostics but never modified in a portfolio candidate.
4.  **Primary checkpoint targets:** `offense_budget`, `regime_multipliers`, `transition_rerisk_smoothing`, `derisk_smoothing`, `volatility_risk_overlay`.
5.  **Never modify stressed_panic defense** via any checkpoint modification. The defense floor is sacred.

### Signal Rules

6.  **All signals must be one-week lagged.** No contemporaneous features in any production-facing signal. Use `t-1` closing data for all signals used at rebalance time `t`.
7.  **No hindsight regime labels.** Market state labels used as features must be from `t-1` or earlier.
8.  **No look-ahead in validation.** All IC computations, cross-validation, and bootstrap tests use only past data at the point of each evaluation.

### Validation Rules

9.  **All reports must include:**

    -   Full-history and pre-declared holdout metrics
    -   Rolling-origin evaluation (104-week windows, 52-week step)
    -   Block bootstrap (2000 iterations, 13-week blocks)
    -   State-by-state returns and Sharpe for all 6 states
    -   Cost and turnover analysis
    -   Hidden beta and BIL/cash exposure
    -   SPY / offense / defense / BIL exposure diagnostics
    -   Delta vs production pin AND shadow pin

10. **Pre-declare the holdout window** before running any experiment. The declared holdout is the last 104 weeks of data. Never change it after declaration.

11. **Use purged cross-validation** for any ML model training. Minimum 4-week embargo at train/test boundary.

### Governance Rules

12. **Every sprint updates `project_journey.md`** with a new section. No sprint is complete without a project journey update.
13. **Every sprint writes a summary markdown report** in `docs/research/`.
14. **Every candidate gets exactly one of:** Promote / Keep as Shadow / Research-only / Drop.
15. **No promotion without passing all 8 Phase D gates.**
16. **Do not change production pins unless explicitly authorized** in CLAUDE.md.
17. **Stage specific files by name.** Never use `git add -A` or `git add .` blindly.
18. **Never commit files over 100 MB.** Check before staging.
19. **Do not regenerate or commit `public/dashboard-data.json`.**

------------------------------------------------------------------------

## 9. Code / Skeleton Guidance

### Deployment-Quality Label Creation

``` python
import pandas as pd
import numpy as np

def build_deployment_quality_composite(
    market_state: pd.Series,           # t-1 state label
    breadth_above_50d: pd.Series,      # fraction of offensive ETFs above 50d MA, t-1
    breadth_above_200d: pd.Series,     # fraction above 200d MA, t-1
    path_clarity_r2: pd.Series,        # 13w R² of SPY price path, t-1
    state_persistence: pd.Series,      # consecutive weeks in current state, t-1
    credit_confirmation: pd.Series,    # HYG/LQD 4w trend direction, t-1
    weights: dict = None,
) -> pd.Series:
    """
    Build a deployment quality composite. All inputs are 1-week lagged.
    Returns a z-scored composite in [-3, +3] range.
    Never uses information from future dates.
    """
    if weights is None:
        weights = {
            'breadth_50d': 0.25,
            'breadth_200d': 0.20,
            'path_clarity': 0.20,
            'persistence': 0.15,
            'credit': 0.20,
        }
    
    # Normalize each component to [0, 1]
    def safe_rank(s): return s.rank(pct=True, na_option='keep')
    
    composite = (
        weights['breadth_50d']   * safe_rank(breadth_above_50d) +
        weights['breadth_200d']  * safe_rank(breadth_above_200d) +
        weights['path_clarity']  * safe_rank(path_clarity_r2) +
        weights['persistence']   * safe_rank(state_persistence) +
        weights['credit']        * safe_rank(credit_confirmation)
    )
    
    # Z-score and winsorize
    z = (composite - composite.mean()) / composite.std()
    return z.clip(-3, 3)
```

### Trend Quality Score (Per-ETF)

``` python
def compute_trend_quality_score(
    prices: pd.DataFrame,   # ETF prices, columns = ETF tickers, index = weekly dates
    lookback_r2: int = 52,  # weeks for R² computation
    lookback_whipsaw: int = 26,
    lag: int = 1,
) -> pd.DataFrame:
    """
    Compute per-ETF trend quality score. All outputs are lag-week delayed.
    Returns DataFrame with same index/columns as prices, values in [0, 1].
    """
    results = {}
    
    for ticker in prices.columns:
        price = prices[ticker].dropna()
        
        # R² of linear trend
        r2_series = price.rolling(lookback_r2).apply(
            lambda x: np.corrcoef(np.arange(len(x)), x)[0, 1] ** 2,
            raw=True
        )
        
        # Whipsaw probability: frequency of 4w sign reversals
        mom_4w = price.pct_change(4)
        sign_changes = (mom_4w.diff() != 0).rolling(lookback_whipsaw).mean()
        whipsaw_prob = sign_changes.clip(0, 1)
        
        # Multi-window agreement (0, 1, 2, or 3)
        mom_13w = price.pct_change(13).apply(np.sign)
        mom_26w = price.pct_change(26).apply(np.sign)
        mom_52w = price.pct_change(52).apply(np.sign)
        agreement = ((mom_13w + mom_26w + mom_52w + 3) / 2).clip(0, 3) / 3
        
        # Composite (quality = high R², low whipsaw, high agreement)
        quality = (r2_series + (1 - whipsaw_prob) + agreement) / 3
        
        # Apply lag
        results[ticker] = quality.shift(lag)
    
    return pd.DataFrame(results)
```

### Re-Risk Rule

``` python
def build_rerisk_modifier(
    market_state: pd.Series,
    recovery_quality_score: pd.Series,   # from deployment quality composite
    base_rr_speed: float = 0.30,
    max_boost: float = 0.25,
) -> pd.Series:
    """
    Build a re-risk speed modifier. Only active in recovery states.
    Never modifies stressed_panic behavior.
    """
    modifier = pd.Series(base_rr_speed, index=market_state.index)
    
    is_recovery = market_state.isin(['recovery_confirmed', 'recovery_fragile'])
    quality_boost = (recovery_quality_score * max_boost).clip(0, max_boost)
    
    modifier[is_recovery] = base_rr_speed + quality_boost[is_recovery]
    
    # Stressed panic: always use base_rr_speed = 0 (no re-risk during stress)
    is_stressed = market_state == 'stressed_panic'
    modifier[is_stressed] = 0.0
    
    return modifier
```

### Lead-Lag Diagnostic

``` python
def compute_leadlag_matrix(
    signals: pd.DataFrame,   # columns = signal names, index = dates
    lags: list = [1, 2, 4],  # lag weeks to test
    rolling_window: int = 52,
) -> pd.DataFrame:
    """
    Compute rolling lead-lag correlations between signal pairs.
    Returns a DataFrame of (date, signal_a, signal_b, lag, correlation) rows.
    """
    records = []
    for lag in lags:
        for a in signals.columns:
            for b in signals.columns:
                if a == b:
                    continue
                # a leads b by lag weeks
                corr = signals[a].rolling(rolling_window).corr(signals[b].shift(-lag))
                for date, c in corr.dropna().items():
                    records.append({'date': date, 'signal_a': a, 'signal_b': b, 'lag': lag, 'corr': c})
    return pd.DataFrame(records)
```

### Decision-Focused Label Creation

``` python
def build_triple_barrier_labels(
    portfolio_returns: pd.Series,   # weekly portfolio returns
    profit_barrier: float = 0.02,   # +2% cumulative profit
    loss_barrier: float = -0.015,   # -1.5% cumulative loss
    horizon: int = 8,               # 8-week maximum horizon
    lag: int = 1,                   # 1-week lag to avoid look-ahead
) -> pd.Series:
    """
    Triple-barrier labels for walk-forward decision quality.
    label = 1 if profit barrier hit first, -1 if loss barrier hit first, 0 if time-expired.
    All labels are computed at t and reflect what happens from t+lag to t+lag+horizon.
    """
    returns = portfolio_returns.shift(-lag)  # align to next week's start
    
    labels = pd.Series(np.nan, index=returns.index)
    
    for t in range(len(returns) - horizon):
        path = (1 + returns.iloc[t:t+horizon]).cumprod() - 1
        
        if (path >= profit_barrier).any():
            first_profit = (path >= profit_barrier).idxmax()
        else:
            first_profit = None
        
        if (path <= loss_barrier).any():
            first_loss = (path <= loss_barrier).idxmax()
        else:
            first_loss = None
        
        if first_profit is None and first_loss is None:
            labels.iloc[t] = 0
        elif first_profit is None:
            labels.iloc[t] = -1
        elif first_loss is None:
            labels.iloc[t] = 1
        elif path.index.get_loc(first_profit) < path.index.get_loc(first_loss):
            labels.iloc[t] = 1
        else:
            labels.iloc[t] = -1
    
    return labels
```

### Wrapper Modifier Function Signature

``` python
def apply_offense_budget_modifier(
    checkpoint_df: pd.DataFrame,      # offense_budget checkpoint, shape (N, 7)
    quality_score: pd.Series,         # deployment quality composite, shape (N,)
    alpha: float = 0.10,              # max offset fraction (pre-declared, not tuned)
    active_states: list = None,       # states where modifier is active
    market_state: pd.Series = None,   # required if active_states is provided
) -> pd.DataFrame:
    """
    Apply a quality-scaled modifier to the offense_budget checkpoint.
    Only active in non-stressed states. Bounded to avoid excessive change.
    """
    if active_states is None:
        active_states = ['calm_trend', 'neutral_mixed', 'recovery_confirmed', 
                         'recovery_fragile', 'strong_neutral']
    
    modified = checkpoint_df.copy()
    
    for t in checkpoint_df.index:
        if market_state is not None and market_state.get(t) not in active_states:
            continue  # no modification in stressed or undefined states
        
        q = quality_score.get(t, 0.0)
        scale_factor = 1.0 + alpha * np.clip(q, -1.0, 1.0)
        
        # Scale only offensive sleeves (not defensive, not cash)
        offense_cols = ['dual_momentum_topn', 'cta_trend_long_only', 
                        'composite_selective_signals']
        modified.loc[t, offense_cols] *= scale_factor
        
        # Renormalize row to sum to 1
        row_sum = modified.loc[t].sum()
        if row_sum > 0:
            modified.loc[t] /= row_sum
    
    return modified
```

### Validation Table Creation

``` python
def build_validation_table(
    returns_dict: dict,        # {strategy_name: pd.Series of weekly returns}
    holdout_start: str,        # e.g., '2024-04-19'
    benchmark_name: str,       # e.g., 'improved_phase2b_regime_confidence_boost'
    state_labels: pd.Series,   # market state labels
) -> pd.DataFrame:
    """
    Build a comprehensive validation table for all candidates.
    Reports full-history, holdout, and state-conditional metrics.
    """
    rows = []
    
    holdout_start = pd.Timestamp(holdout_start)
    benchmark_returns = returns_dict[benchmark_name]
    
    for name, rets in returns_dict.items():
        full = rets
        holdout = rets[rets.index >= holdout_start]
        pre_holdout = rets[rets.index < holdout_start]
        
        row = {
            'strategy': name,
            'full_return': (1 + full).prod() ** (52 / len(full)) - 1,
            'full_sharpe': full.mean() / full.std() * np.sqrt(52),
            'full_max_dd': compute_max_drawdown(full),
            'holdout_return': (1 + holdout).prod() ** (52 / len(holdout)) - 1,
            'holdout_sharpe': holdout.mean() / holdout.std() * np.sqrt(52),
            'holdout_max_dd': compute_max_drawdown(holdout),
        }
        
        # State-conditional Sharpe
        for state in state_labels.unique():
            mask = state_labels.reindex(rets.index) == state
            state_rets = rets[mask]
            if len(state_rets) >= 10:
                row[f'sharpe_{state}'] = (
                    state_rets.mean() / state_rets.std() * np.sqrt(52) 
                    if state_rets.std() > 0 else np.nan
                )
        
        # Delta vs benchmark
        row['holdout_delta_vs_benchmark'] = row['holdout_sharpe'] - (
            benchmark_returns[benchmark_returns.index >= holdout_start].mean() /
            benchmark_returns[benchmark_returns.index >= holdout_start].std() * np.sqrt(52)
        )
        
        rows.append(row)
    
    return pd.DataFrame(rows).set_index('strategy')
```

### Bootstrap Check

``` python
def block_bootstrap_test(
    candidate_returns: pd.Series,
    benchmark_returns: pd.Series,
    n_boot: int = 2000,
    block_size: int = 13,
    seed: int = 20260420,
) -> dict:
    """
    Block bootstrap test of candidate vs benchmark on holdout Sharpe.
    Returns mean delta, 95% CI, and P(candidate > benchmark).
    """
    np.random.seed(seed)
    aligned = pd.concat([candidate_returns, benchmark_returns], axis=1).dropna()
    n = len(aligned)
    n_blocks = n // block_size + 1
    
    boot_deltas = []
    for _ in range(n_boot):
        starts = np.random.choice(n - block_size + 1, n_blocks, replace=True)
        idx = np.concatenate([np.arange(s, min(s + block_size, n)) for s in starts])[:n]
        sample = aligned.iloc[idx]
        
        cand_sharpe = sample.iloc[:, 0].mean() / sample.iloc[:, 0].std() * np.sqrt(52)
        bench_sharpe = sample.iloc[:, 1].mean() / sample.iloc[:, 1].std() * np.sqrt(52)
        boot_deltas.append(cand_sharpe - bench_sharpe)
    
    boot_deltas = np.array(boot_deltas)
    return {
        'mean_delta': np.mean(boot_deltas),
        'ci_95_lower': np.percentile(boot_deltas, 2.5),
        'ci_95_upper': np.percentile(boot_deltas, 97.5),
        'p_cand_gt_bench': (boot_deltas > 0).mean(),
    }
```

### Rolling-Origin Validation

``` python
def rolling_origin_evaluation(
    returns_dict: dict,        # {name: pd.Series}
    benchmark_name: str,
    min_train_weeks: int = 260,
    test_window: int = 104,
    step_weeks: int = 52,
) -> pd.DataFrame:
    """
    Rolling-origin (expanding window) evaluation.
    Each origin: train = t0..t_start, test = t_start..t_start+test_window.
    """
    all_returns = pd.concat(returns_dict, axis=1).dropna()
    n = len(all_returns)
    
    results = []
    for start in range(min_train_weeks, n - test_window, step_weeks):
        test_slice = all_returns.iloc[start:start + test_window]
        bench_sharpe = (
            test_slice[benchmark_name].mean() /
            test_slice[benchmark_name].std() * np.sqrt(52)
        )
        
        for name in returns_dict:
            cand_sharpe = (
                test_slice[name].mean() /
                test_slice[name].std() * np.sqrt(52)
            )
            results.append({
                'origin': all_returns.index[start],
                'strategy': name,
                'test_sharpe': cand_sharpe,
                'delta_vs_bench': cand_sharpe - bench_sharpe,
            })
    
    return pd.DataFrame(results)
```

------------------------------------------------------------------------

## 10. Roadmap Decision

### Are we ready to start Frontier Phase 1?

**Yes.** The stabilization sprint passed all prerequisites: - Exact wrapper is operational - Safe checkpoints are accessible and verified - Architecture-valid rules are tested - Production files are protected

### Is Frontier Phase 1 the correct first sprint?

**Yes.** Deployment-state intelligence is the highest-priority frontier because: 1. It requires no new data sources (all existing free data) 2. It operates at the correct architectural level (`regime_multipliers` and `offense_budget` checkpoints) 3. The hypothesis is economically motivated (not all `recovery_confirmed` instances are equal) 4. The signals are causal and interpretable 5. It builds the foundation that Phases 2–5 depend on (quality composite as a shared input)

### What should the first implementation prompt be?

> "You are implementing Frontier Phase 1 of the post-stabilization frontier deployment intelligence arc. The goal is to build a deployment-state quality composite from causal, 1-week-lagged ETF signals. The wrapper baseline (`scripts/allocator_checkpoint_wrapper.py`) must be used as the exact GGG reproducer (no modifications to production files). Implement `scripts/phase_frontier1_state_quality_signals.py` that: (1) loads existing breadth signals from `data/02_layer1_signals/`; (2) computes breadth quality (fraction of offensive ETFs above 50d MA, 1w lag), path clarity (13-week R² of SPY price regression, 1w lag), state persistence (consecutive weeks in current market state, from `market_state_history.csv`, 1w lag), credit confirmation (HYG/LQD 4w trend, 1w lag), and leadership quality (offensive ETFs above both 50d and 200d MA, 1w lag); (3) builds a z-scored composite with pre-defined equal-ish economic weights; and (4) runs a diagnostic wrapper experiment using the `regime_multipliers` checkpoint to evaluate whether the quality composite has predictive content for forward state-conditional returns. Output all signals and diagnostics to `data/research/frontier_phase1/`. Write `docs/research/frontier_phase1_deployment_state_intelligence_report.md`. Do NOT modify any production files, dashboard files, or public files."

### What should we avoid?

1.  **Avoid opening Phase 6 (Decision-Focused Learning) too early.** It requires stable Phase 1–5 signals as inputs. Starting it before Phase 2–3 are validated creates noise.
2.  **Avoid the "another overlay" trap.** Each phase should produce a substantive new signal or architecture, not a threshold adjustment to an existing rule.
3.  **Avoid abandoning the interpretability constraint.** The project history shows that black-box learners do not generalize to the holdout window on this dataset. Keep all signals interpretable until Phase 6.
4.  **Avoid optimizing composite weights on full history.** All composites should use pre-defined economic weights or weights from cross-validated sub-samples.
5.  **Avoid claiming improvement before holdout validation.** The pre-declared holdout is the last 104 weeks. No promotion without passing all 8 Phase D gates.
6.  **Avoid re-opening closed branches.** The allocator-refinement, trust-layer, and holdings-blend branches are closed. Do not reopen unless new evidence (specifically from Phase 1–7 diagnostics) changes the diagnosis.
7.  **Avoid the PIT data detour early.** Phase 9 is the data expansion decision point. Don't let the PIT data path distract from the free-data frontier phases.

### What would make us stop and pivot?

1.  **Phase 1 acceptance gates fail**: IC of state quality composite \< 0.02 across all states → quality labeling does not add value over existing state labels. In this case, the frontier hypothesis about "state quality" is wrong, and the roadmap should pivot to direct sleeve design (Phase 8 type work) or data expansion (Phase 9).

2.  **Phase 2 cross-sectional IC is \< 0.01**: trend quality signal is redundant with existing momentum signals → stop the trend quality track and reassess whether the project needs genuinely new asset class exposure.

3.  **Phase 3 recovery capture improvement \< 3pp**: re-risking quality does not improve recovery participation → the re-risking bottleneck is not the quality signal but something structural (e.g., the stressed_panic-to-recovery transition rule itself needs redesign).

4.  **All Phases 1–4 produce \< 0.05 Sharpe improvement each**: the frontier signals collectively add no value → the project has reached the information ceiling of this ETF universe without paid data. Pivot to: (a) Phase 9 PIT data acquisition, or (b) genuinely new return streams (commodities/futures), or (c) accept current results as the production ceiling.

5.  **Any phase produces a Sharpe improvement at the cost of \> 1.5pp drawdown worsening**: the improvement is not within the project's risk discipline → do not promote, research-only.

------------------------------------------------------------------------

## 11. Appendix: Phase D Promotion Checklist

For any frontier phase candidate to be considered for promotion:

| Gate | Threshold | Notes |
|----|----|----|
| Full-history Δ vs production | ≥ +0.015 on raw target composite | Fixed comparator set |
| Holdout-Δ vs production | ≥ 0 on raw target composite | Pre-declared 104-week holdout |
| Holdout Sharpe Δ vs production | ≥ -0.02 | Minimum -2% below production Sharpe on holdout |
| Rolling win rate vs production | ≥ 55% | 104-week rolling windows, 52-week step |
| Rolling mean Δ vs production | \> 0 | Average delta across rolling windows |
| Bootstrap P(cand \> prod) | ≥ 60% | 2000 iterations, 13-week blocks, holdout only |
| Max drawdown Δ | ≥ -0.01 | Not more than 1pp worse than production |
| CVaR 5% Δ | ≥ -0.002 | Not more than 0.2pp worse than production |

All 8 gates must pass simultaneously for promotion.

------------------------------------------------------------------------

*Document ends. No production files modified by the creation of this document.*
