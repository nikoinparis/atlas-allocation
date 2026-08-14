---
editor_options: 
  markdown: 
    wrap: 72
---

# Frontier Deployment Intelligence — Source Review

**Document version:** 2026-05-20\
**Purpose:** Literature and practitioner research review supporting the
frontier roadmap\
**Scope:** Academic papers, public practitioner research, open-source
frameworks relevant to frontier phases 1–7

------------------------------------------------------------------------

## Overview

This document reviews the public research and academic literature that
informed the frontier roadmap. For each source category, it records:
what the source suggests, what realistically applies to this ETF
project, what does not apply, an implementation warning, and the
recommended phase placement.

No proprietary strategies are reproduced. All sources are public.

------------------------------------------------------------------------

## 1. AQR: Time-Series Momentum, Trend Quality, BAB, Defensive Equity

### Key Papers

-   Moskowitz, Ooi, Pedersen (2012): "Time series momentum." *Journal of
    Financial Economics*.
-   Hurst, Ooi, Pedersen (2017): "A century of evidence on
    trend-following investing." *Journal of Portfolio Management*.
-   Frazzini and Pedersen (2014): "Betting against beta." *Journal of
    Financial Economics*.
-   Asness, Frazzini, Pedersen (2014): "Low-risk investing without
    industry bets." *Financial Analysts Journal*.

### What AQR Suggests

Time-series momentum (TSMOM) is the strategy of going long (short)
assets that had positive (negative) trailing returns. The AQR finding is
that TSMOM: 1. Works across asset classes and time horizons (1–12
months) 2. Is distinct from cross-sectional momentum 3. Survives costs
and transaction friction at monthly rebalance 4. Provides "time-varying
crisis alpha" — historically positive during prolonged equity crises

The trend-quality paper (Hurst et al.) shows that trend following has
worked for a century across many markets, but the strength varies with
trend "quality" — defined as the ratio of the directional component to
the total path variance. Clean trends (high direction-to-noise ratio)
produce better Sharpe ratios than choppy trends.

BAB: Low-beta assets have higher risk-adjusted returns than high-beta
assets. AQR explains this as a leverage-constraint story — constrained
investors bid up high-beta assets, creating mispricing. Defensive equity
(low-beta, low-volatility) captures this.

### What Realistically Applies

1.  **Trend quality scoring is directly applicable.** The project's
    `trend_clarity_momentum` signal (Phase A) was an early
    implementation of this idea. Frontier Phase 2 should formalize it
    using the ratio of trend component variance to total price variance
    (i.e., R² of linear regression), consistent with the Hurst et al.
    framework.

2.  **Cross-horizon agreement is applicable.** AQR uses signals at
    1-month, 3-month, 6-month, and 12-month horizons. The project can
    replicate this with 4w, 13w, 26w, and 52w lookbacks. Assets where
    all horizons agree on direction are higher-quality trend
    opportunities.

3.  **Crisis alpha framing is useful for W1 (structural defense
    sleeve).** W1 is already the most distinctive defensive sleeve in
    the project. The AQR crisis-alpha framing supports keeping it as an
    always-available defense that earns positively in stressed periods.

### What Does NOT Apply

1.  **Short positions are assumed in all AQR TSMOM papers.** The project
    is long-only. The crisis alpha benefit of TSMOM comes largely from
    the short leg. Long-only TSMOM captures only the risk-on
    participation, not the short-side crisis contribution.

2.  **BAB requires individual stock selection.** The project's ETF
    universe cannot implement stock-level BAB. Low-beta ETF tilts (XLU,
    XLP) are rough proxies, not clean implementations.

3.  **AQR's signal calibration is for daily or monthly rebalance.** The
    project uses weekly. Signal parameters need adjustment.

### Implementation Warning

R² of trend is NOT the same as R² of recent momentum performance. A
high-beta asset can have a smooth trend with R² = 0.95 in a bull market.
The trend quality filter should be applied cross-sectionally (rank ETFs
by R²), not as a regime filter.

### Phase Placement

-   Frontier Phase 2 (Trend/Setup Quality Engine): R², cross-horizon
    agreement, whipsaw probability
-   Frontier Phase 4 (Cross-Sectional Leadership): leadership quality
    ranking uses trend quality as input

------------------------------------------------------------------------

## 2. Man Group: Trend Following, Signal Quality, Speed Selection

### Key Sources

-   Man AHL public research series (trend following papers available at
    man.com/ahl)
-   Man Institute publications on systematic strategies
-   Cowan, Wilderman (Man AHL): "Trend following: Equity and bond
    diversification."
-   Various "AHL alpha sources" public overview documents

### What Man Group Suggests

Man Group / AHL's public research emphasizes:

1.  **Signal speed diversity.** Combining fast (1-month), medium (3-6
    month), and slow (12+ month) trend signals improves out-of-sample
    Sharpe because different speeds work in different regimes. Fast
    signals are good in trend reversals; slow signals are good in
    persistent trends.

2.  **Trend quality vs. trend strength.** AHL explicitly discusses
    selecting high-"quality" trend environments based on the
    autocorrelation of daily returns. In high-autocorrelation
    environments, trend following is more profitable. In mean-reverting
    environments, it destroys value.

3.  **Crisis alpha from managed futures.** Man/AHL's research shows
    trend-following CTA strategies are positively correlated with equity
    market volatility — they tend to make money when equity volatility
    spikes. This is the "crisis alpha" property.

4.  **Capacity constraints in trend following.** At scale, fast signals
    become crowded. The project's ETF universe is small enough that
    crowding is not a concern, but the signal construction lessons
    apply.

### What Realistically Applies

1.  **Speed blending.** Instead of a single 52-week lookback for trend,
    use a blend of 13w, 26w, and 52w momentum signals, with weights that
    adapt to which speed is currently exhibiting higher autocorrelation.

2.  **Autocorrelation as a trend-quality filter.** Compute 8-week
    rolling autocorrelation of weekly returns for each ETF. When
    autocorrelation is positive (trending), the trend signal is more
    reliable. When autocorrelation is negative or zero
    (mean-reverting/choppy), reduce the signal weight.

3.  **The W4 sleeve (macro trend diversifier, Phase W) was directly
    motivated by the crisis alpha literature.** The high vol of W4's
    current implementation makes it undeployable, but a vol-capped
    version with managed-futures-style risk targeting (target 10%
    annualized vol, scale down when realized vol rises) could capture
    managed-futures-like properties.

### What Does NOT Apply

1.  **Man/AHL uses leverage and shorting.** Long-only ETF adaptation
    requires treating "flat/cash" as the equivalent of the short side.

2.  **Man/AHL uses futures with high liquidity.** ETF liquidity is
    adequate but different. The signal persistence and transaction cost
    structure is different.

3.  **Cross-asset trend at the commodity/FX futures level** requires
    data the project does not currently have.

### Implementation Warning

Autocorrelation-based trend quality is the most technically correct
implementation of the Man/AHL speed-selection idea, but it requires at
least 26 weeks of weekly data to be stable. With 35 ETFs, this is
feasible. The risk is that autocorrelation can be non-stationary (it
changes regime), so rolling estimation is required.

### Phase Placement

-   Frontier Phase 2: autocorrelation-based trend quality filter, speed
    blending
-   Frontier Phase 8 (conditional): vol-capped W4 sleeve redesign if
    Phase 2 signals confirm value

------------------------------------------------------------------------

## 3. Moreira-Muir (2017): Volatility-Managed Portfolios

### Key Paper

-   Moreira, A. and Muir, T. (2017): "Volatility-Managed Portfolios."
    *Journal of Finance* 72(4).

### What Moreira-Muir Suggests

Scale portfolio exposure inversely with lagged realized variance.
Specifically: at the start of period t, set position size proportional
to `1 / σ²(t-1)` where σ² is measured from the previous month's (or few
weeks') daily returns.

Their finding: this simple rule improves Sharpe ratios for momentum,
value, carry, and market factors. The economic intuition: high realized
variance predicts high future variance (GARCH-like persistence), and the
reward-to-risk ratio of most factors is approximately constant, so
scaling down when variance is high preserves risk-adjusted returns.

### What Realistically Applies

1.  **Per-ETF vol scaling within the offense sleeves.** Instead of
    equal-weight or momentum-ranked top-N, scale ETF weights within a
    sleeve by `1 / σ²(t-1)` where σ² is 13-week realized variance. This
    is the core Moreira-Muir idea adapted to ETF selection.

2.  **Portfolio-level vol target.** Scale the total offense budget by
    `target_vol / trailing_vol` where trailing_vol is the 8-week
    realized portfolio volatility. This is already partially captured by
    the `volatility_risk_overlay` checkpoint but could be made more
    responsive.

3.  **Recovery state application.** Moreira-Muir vol scaling is
    especially valuable in recovery states where volatility is falling
    from elevated levels. As volatility falls, scale up offense
    exposure. This naturally produces faster re-risking when conditions
    are calming.

### What Does NOT Apply

1.  **Daily data.** Moreira-Muir use daily data for variance estimation.
    The project uses weekly. The 13-week weekly realized variance is a
    reasonable substitute.

2.  **Factor-level implementation.** Their paper applies vol scaling to
    individual factors, not multi-sleeve ETF portfolios. Adaptation is
    straightforward but introduces some modeling choices.

### Implementation Warning

Vol scaling with lagged 13-week variance on a weekly-rebalanced
portfolio adds modest turnover. At the ETF level, if one ETF's vol is
temporarily elevated (e.g., during earnings), the scaling may
underweight it at exactly the wrong time. Winsorize the variance to
avoid extreme scaling from outlier events.

### Phase Placement

-   Frontier Phase 2: per-ETF volatility-scaled offense weighting
-   Frontier Phase 3: recovery-state vol-scaling as a re-risking
    accelerant

------------------------------------------------------------------------

## 4. Faber: GTAA, Trend-Following Asset Allocation

### Key Papers

-   Faber, M. (2007): "A quantitative approach to tactical asset
    allocation." *Journal of Wealth Management*.
-   Faber, M. (2013): "Global Value: How to Spot Bubbles, Avoid Market
    Crashes, and Earn Big Returns in the Stock Market."

### What Faber Suggests

Simple 10-month (200-day) moving average filter across 5 global asset
classes (US equity, foreign equity, real estate, commodities, bonds)
dramatically improves risk-adjusted returns. The mechanism: avoid assets
when they are below their 10-month MA, hold cash instead.

Extensions: equal-weight all above-MA assets. This is the simplest
possible tactical allocation rule and it still works out-of-sample
across 100+ years of data.

### What Realistically Applies

1.  **The `taa_10m_sma` sleeve already directly implements this.** It is
    one of the project's most reliable calm-trend sleeves. No additional
    Faber-type sleeve is needed.

2.  **Breadth of 10-month MA crossings as a regime indicator.** How many
    of the project's key ETFs (SPY, EFA, VWO, TLT, HYG, GLD, DBC) are
    currently above their 10-month MA? A high count = broad
    confirmation; low count = regime deterioration. This "MA breadth
    score" is a clean, interpretable cross-asset confirmation signal for
    Phase 4 (Leadership Systems).

3.  **The simplicity of Faber's rule is a useful benchmark.** Any new
    regime signal should be compared against "does this add value over
    the simple 10-month MA rule?"

### What Does NOT Apply

1.  **Faber's equal-weight-above-MA approach doesn't distinguish between
    asset quality.** The project's multi-sleeve architecture already
    does more sophisticated state conditioning.

2.  **Faber's 5-asset universe is too coarse** for the project's 35-ETF
    panel. But the principle of counting assets above long-term trend is
    directly applicable as a confirmation feature.

### Implementation Warning

The MA breadth score can give false positives during late-cycle
environments where most assets are above their MA but momentum is
narrowing to a small subset of leaders. Always complement MA breadth
with leadership concentration (Frontier Phase 4).

### Phase Placement

-   Already implemented as `taa_10m_sma` sleeve
-   Frontier Phase 4: MA breadth count as a cross-asset confirmation
    feature

------------------------------------------------------------------------

## 5. Newfound Research / ReSolve Asset Management: Fragility, Path Dependency, Rebalance Luck

### Key Sources

-   Hoffstein, C. (Newfound Research): "Quantifying the Rebalancing
    Premium" (2016)
-   Hoffstein, C.: "Fragility Case Study: Momentum's Cliff" (2020)
-   Hoffstein, C.: "Navigating with CAPE" (2017)
-   Butler, A., Gordillo, R. (ReSolve): "Adaptive Asset Allocation"
    (2015) 
-   GestaltU / Salient Partners: blog series on trend quality and
    fragility

### What Newfound/ReSolve Suggests

1.  **Fragility / rebalance luck.** A signal's apparent performance is
    sensitive to the exact day of the month (or week) it is measured. A
    12-month momentum signal measured on the last day of the month gives
    systematically different results from one measured on the 10th day.
    This is "rebalance luck" and it means single-signal strategies have
    higher variance than they appear.

2.  **Path dependency.** Two portfolios can arrive at the same return
    level via very different paths. A portfolio that arrived at 100
    after a smooth grind is structurally different from one that arrived
    at 100 after a sharp drawdown and V-shaped recovery. The recovery
    version has much higher conditional volatility and worse forward
    prospects.

3.  **Ensemble of measurement windows.** To reduce rebalance luck, use
    an ensemble of momentum lookbacks (e.g., average 11-month, 10-month,
    and 9-month momentum) rather than a single 12-month lookback. This
    has been shown to reduce drawdowns and improve out-of-sample Sharpe
    with zero additional information.

4.  **Trend quality from the path, not just the endpoint.** Newfound's
    research shows that a 12-month return of +15% achieved via a smooth
    upward trend has very different forward prospects than +15% achieved
    via a drawdown-and-recovery path. Trend quality should measure path
    characteristics, not just endpoint return.

### What Realistically Applies

1.  **Ensemble momentum is directly implementable.** Use an average of
    13w, 17w, 22w, 26w, and 34w momentum signals instead of a single 26w
    signal. This is a 5-line code change with real out-of-sample
    benefit. Can be incorporated into any offensive sleeve.

2.  **Path-clarity scoring is the right frame for Frontier Phase 2.**
    The R²-based trend quality measure is a formalization of Newfound's
    "smooth path" concept. R² measures how well the observed price path
    is explained by a straight-line trend — exactly the path clarity
    concept.

3.  **The "fragile calm" state concept comes directly from this
    research.** A `calm_trend` state where the last 52 weeks was a
    smooth, steady grind has different properties than `calm_trend`
    state where the last 52 weeks included a sharp selloff that was
    entirely recovered. The smooth grind is less fragile. This motivates
    the "good calm vs fragile calm" distinction in Frontier Phase 1.

4.  **Rebalance luck reduction is free.** Use average of 4-week, 5-week,
    and 6-week measurement windows for all signals. This reduces noise
    without any theoretical cost.

### What Does NOT Apply

1.  **ReSolve's Adaptive Asset Allocation** uses HRP-style
    diversification across 10+ asset classes. The project already does
    this with the HRP sleeve allocator.

2.  **Newfound's momentum-with-value-timing** requires valuation data
    (CAPE ratios) for each asset class. The project does not use
    valuation data; this branch is not worth opening without a clear
    data path.

### Implementation Warning

Ensemble momentum averaging can increase correlation between signals if
all lookbacks are from the same trend. Monitor ensemble IC carefully —
the benefit comes from diversity of signal timing, not from averaging
similar signals.

### Phase Placement

-   Frontier Phase 1: path-clarity framing, "fragile calm" vs "good
    calm" state quality labels
-   Frontier Phase 2: R²-based path clarity, ensemble momentum,
    rebalance luck reduction
-   Frontier Phase 4: path-conditioned leadership quality

------------------------------------------------------------------------

## 6. Robeco: Low-Volatility, Factor Timing, Quality Factors

### Key Papers

-   Blitz, D. and Vliet, P. (2007): "The Volatility Effect." *Journal of
    Portfolio Management*.
-   Blitz, D. (2016): "The Volatility Effect Revisited." *Journal of
    Portfolio Management*.
-   Blitz, D., Baltussen, G., Van Vliet, P. (2020): "Beyond
    Fama-French." *Journal of Portfolio Management*.
-   Robeco.com factor investing publications (public factsheets and
    research notes)

### What Robeco Suggests

1.  **The volatility effect is real and distinct from beta.**
    Low-volatility stocks and ETFs outperform high-volatility ones on a
    risk-adjusted basis, and this cannot be fully explained by beta,
    size, or other factors.

2.  **Quality-factor timing.** When the market is in a "risk-on"
    expansion phase, quality stocks (high profitability, low leverage,
    stable earnings) tend to lag. But quality factors protect strongly
    in drawdowns and mean-revert to leadership faster in recovery. This
    creates a timing opportunity.

3.  **Factor defensiveness.** Defensive factors (low vol, quality) are
    not just drawdown protectors — they have a carry-like positive
    expected return across time. This is Robeco's core argument for
    always holding some defensive exposure.

### What Realistically Applies

1.  **Quality-factor ETF selection.** Within the offensive sleeves,
    prefer ETFs that represent quality-factor exposure (e.g., QUAL, VIG,
    MOAT) over pure momentum ETFs in uncertain environments. This can be
    expressed as a quality-tilt modifier at the `offense_budget`
    checkpoint.

2.  **Defensive factor rotation.** The existing structural defense
    sleeve (W1) captures some of this. The frontier extension is to add
    a "quality defensive rotation" signal that overweights
    quality-momentum ETFs when breadth is narrowing or leadership
    quality is declining (signals from Phase 4).

3.  **Volatility-adjusted selection.** Within any momentum ranking,
    scale by trailing volatility (inverse vol weighting). This is
    already done in some form, but formalizing it within the trend
    quality engine (Phase 2) is the right approach.

### What Does NOT Apply

1.  **Individual stock quality factors (ROE, accruals, leverage).**
    These require fundamental data at the stock level, which the project
    does not use.

2.  **Robeco's specific factor exposure construction** is at the stock
    level. The ETF universe offers factor-like ETFs as proxies, not
    pure-factor exposures.

### Implementation Warning

Quality ETFs (QUAL, VIG) are often large-cap US growth proxies. In the
current ETF universe, "quality" often means "SPY-correlated with lower
vol" which is not a distinct new exposure. Verify that any quality-tilt
modifier is not simply a beta-reduction that could be achieved by
holding more cash.

### Phase Placement

-   Frontier Phase 4: quality-factor leadership signal as part of
    leadership type scoring
-   Frontier Phase 2: vol-adjusted ETF selection within offensive
    sleeves

------------------------------------------------------------------------

## 7. PIMCO / Bridgewater: Macro Regime and Credit/Liquidity Signals

### Key Sources

-   Bridgewater Associates: "Principles for Navigating Big Debt Crises"
    (2018, public)
-   Bridgewater Associates: "All Weather Strategy" public overview
    documents
-   PIMCO: "Secular Outlook" reports (public)
-   PIMCO: "Economic Outlook" monthly publications

### What PIMCO/Bridgewater Suggests

1.  **Growth-inflation-liquidity quadrant framing.** Bridgewater's All
    Weather explicitly decomposes environments into four regimes based
    on:

    -   Rising growth vs. falling growth
    -   Rising inflation vs. falling inflation The assets that do well
        in each quadrant differ systematically (equities do well in
        rising growth + falling inflation; gold does well in rising
        inflation; bonds do well in falling growth + falling inflation).

2.  **Credit / liquidity as a leading indicator.** PIMCO's research
    emphasizes that credit market conditions (HYG/LQD spreads, bank
    lending standards, LIBOR/OIS) lead economic conditions by 2–6
    months. Credit tightening precedes equity market stress; credit
    easing precedes equity market recovery.

3.  **Duration positioning.** In deflationary recessions, long-duration
    bonds (TLT) are valuable risk-reducers. In inflationary expansions,
    commodities (GLD, PDBC) hedge inflation and provide diversification.

### What Realistically Applies

1.  **Credit spread signal (HYG/LQD ratio) as a confirmation/warning
    indicator.** The project's `macro_stress` rule already uses some
    version of this. The frontier extension (Phase 7) would build a more
    formal rolling model of HYG/LQD trend and incorporate it as a
    lead-lag signal with explicit lag estimation.

2.  **Growth-inflation regime vector.** Using simple proxies (ISM PMI
    from FRED, CPI momentum, treasury yield spread), it is possible to
    estimate which growth-inflation quadrant the current environment is
    in. This can be computed from free data. This feeds the
    deployment-state quality composite (Phase 1) as a macro backdrop
    feature.

3.  **Dollar as a regime signal.** The project already has a
    `dollar_pressure` rule. The frontier extension identifies specific
    cross-asset consequences: UUP momentum leading EM equity (VWO) and
    commodity weakness, which is a reliable enough relationship to be
    formalized in Phase 7.

### What Does NOT Apply

1.  **Bridgewater's All Weather risk parity** requires leverage and
    shorts across multiple asset classes at institutional scale. The
    project is a retail-scale long-only ETF portfolio.

2.  **PIMCO's credit analysis** requires CDS market data and structured
    credit instruments not available in the ETF universe.

3.  **The specific weighting of the All Weather portfolio** (roughly 55%
    bonds, 30% equity, 15% alternatives) would dramatically underperform
    an equity-focused tactical portfolio in a bull market.

### Implementation Warning

The growth-inflation quadrant has low-frequency regime transitions
(months to years). It is NOT a weekly signal. Use it as a slow-changing
backdrop feature (update monthly or quarterly) that modifies the
deployment quality score slightly, not as a rapid-acting signal.

### Phase Placement

-   Frontier Phase 7 (Cross-Asset Relational Intelligence): HYG/LQD
    lead-lag, dollar leading EM
-   Frontier Phase 1 (as a background macro feature): slow-changing
    growth-inflation backdrop

------------------------------------------------------------------------

## 8. Lopez de Prado: HRP, Purged CV, Meta-Labeling, Triple-Barrier

### Key Books and Papers

-   Lopez de Prado, M. (2018): "Advances in Financial Machine Learning."
    *Wiley*.
-   Lopez de Prado, M. (2016): "Building Diversified Portfolios that
    Outperform Out of Sample." *Journal of Portfolio Management*.
-   Bailey, D. and Lopez de Prado, M. (2014): "The Deflated Sharpe
    Ratio: Correcting for Selection Bias, Backtest Overfitting and
    Non-Normality." *Journal of Portfolio Management*.
-   Lopez de Prado, M. (2019): "A Data Science Solution to the
    Multiple-Testing Problem in Finance." *Journal of Financial Data
    Science*.

### What Lopez de Prado Suggests

1.  **HRP.** Hierarchical Risk Parity uses the correlation structure to
    build diversified portfolios without estimating expected returns. It
    is the allocator core of the project (already in production).

2.  **Meta-labeling.** Train a primary model to generate a binary signal
    (long/cash). Train a secondary model to learn P(primary model is
    correct at time t). The meta-model improves precision without
    sacrificing recall. This is the correct framing for Frontier Phase

    6.  

3.  **Triple-barrier labels.** Label events (portfolio entry points) as
    profit barrier hit (+1), loss barrier hit (-1), or time-expired (0).
    This avoids the noisy-label problem of using raw forward returns as
    training targets.

4.  **Purged cross-validation.** For time-series data, standard k-fold
    CV leaks through overlapping labels. Purging (removing samples where
    training labels overlap with test labels) and embargoing (adding a
    gap of k weeks at the train/test boundary) are required for honest
    time-series ML evaluation. Failure to purge systematically
    overstates model performance.

5.  **Deflated Sharpe Ratio.** When multiple strategies are tried, the
    expected maximum Sharpe from random search is approximately sqrt(2
    \* log(K)) / sqrt(T) where K is the number of trials and T is the
    number of observations. The "deflated Sharpe" penalizes for the
    number of trials, giving a more honest estimate of strategy
    significance. The project should track the total number of strategy
    variants tested across all phases and apply this correction.

### What Realistically Applies

1.  **Meta-labeling is the correct framework for Frontier Phase 6.** The
    production allocator is the "primary model." The Phase 6 meta-model
    learns P(production is better than alternative \| current state
    features).

2.  **Triple-barrier labels are more honest than raw return labels.**
    Use them in Phase 6 label construction. Specifically: define profit
    barrier = production's average 8-week recovery-confirmed return,
    loss barrier = production's average 8-week stressed drawdown. If the
    labeled period hits profit before loss → deploy label. This is
    cleanly implementable with existing data.

3.  **Purged CV is mandatory for any ML work in this project.** 4-week
    minimum embargo. This was applied in earlier ML phases (Phases N–P)
    but should be documented explicitly in Phase 6.

4.  **The deflated Sharpe observation is relevant.** The project has now
    tested 35+ strategy variants. The expected maximum Sharpe from
    random search is not negligible. Any future candidate's Sharpe
    improvement should be assessed in light of this deflation — a +0.05
    Sharpe improvement from trial 50 is less significant than a +0.05
    improvement from trial 5.

### What Does NOT Apply

1.  **HFT and microstructure content.** Lopez de Prado's books spend
    significant space on order book dynamics, market impact, and
    intraday execution. None of this applies to weekly-rebalanced ETF
    portfolios.

2.  **The specific AFML code examples** are for individual stock
    selection with daily data. Adaptation to weekly ETF data requires
    significant modification.

3.  **Fractional differentiation (AFML Chapter 5)** is designed to make
    price series stationary while preserving memory. Weekly ETF returns
    are already stationary; this is not needed.

### Implementation Warning

The deflated Sharpe correction is sobering. After 35+ tested strategies,
the expected Sharpe inflation from selection bias is significant. Future
phase reports should explicitly note the total number of trials and
apply a rough deflation. A strategy that ranks #1 in a pool of 50 trials
needs a substantially higher raw Sharpe to achieve significance than a
strategy from a pool of 5 trials.

**Specific deflation estimate for this project:** With K ≈ 50 strategy
variants tested and T ≈ 1110 weekly observations, the expected maximum
Sharpe from zero-skill search is approximately:
`E[max Sharpe] ≈ sqrt(2 * log(50)) / sqrt(1110) ≈ 0.12`

This means a strategy would need a raw annualized Sharpe of
approximately 0.88 + 0.12 = 1.00+ to be clearly above the selection-bias
ceiling, or equivalently, a +0.12 improvement vs. the production
baseline to survive deflation. The Phase D +0.015 composite improvement
requirement is below this bar, which suggests the Phase D gates are set
conservatively and should be interpreted accordingly.

### Phase Placement

-   Already implemented: HRP (production allocator)
-   Frontier Phase 6: meta-labeling, triple-barrier labels, purged CV
-   Ongoing: Deflated Sharpe awareness in all phase reports

------------------------------------------------------------------------

## 9. Decision-Focused Learning Literature

### Key Papers

-   Elmachtoub, A. and Grigas, P. (2022): "Smart 'Predict, then
    Optimize.'" *Management Science*.
-   Donti, P., Amos, B., and Kolter, J.Z. (2017): "Task-Based End-to-End
    Model Learning in Stochastic Optimization." *NeurIPS*.
-   Wilder, B., Dilkina, B., Tambe, M. (2019): "Melding the
    Data-Decisions Pipeline." *AAAI*.
-   Mandi, J. et al. (2022): "SPO+ for ML-based CO." *NeurIPS*.
-   Dalle Molle, R., Sfeir, G. (2019): "Portfolio Optimization Using
    Predict+Optimize."

### What Decision-Focused Learning Suggests

The key insight is that prediction error (RMSE, MAE) is the wrong loss
function for portfolio decisions. What matters is the cost of the
*downstream decision* made using the prediction. If the portfolio makes
a binary risk-on/risk-off decision, then the right training signal for
the prediction model is "did this prediction lead to a good deployment
decision?" not "how accurate was the return forecast?"

Concretely for a portfolio: 1. Define the decision space: deploy
(risk-on), stay defensive (risk-off), reduce (partial). 2. Define the
utility function: a function U(portfolio return \| decision) that
rewards returns and penalizes drawdowns. 3. Train a prediction model to
minimize expected utility loss, not prediction error.

This has been shown to outperform standard predict-then-optimize
approaches in tasks where the prediction model is used to make discrete
decisions with asymmetric payoffs.

### What Realistically Applies

1.  **The deploy/wait binary decision is exactly the right framing.**
    The project's Phase 6 should train a model with utility-weighted
    labels (deploy = profit above threshold before loss; wait = loss
    before profit or ambiguous).

2.  **Asymmetric payoff structure.** The portfolio's downside
    (stressed_panic) is typically 3-5x worse than its upside
    (calm_trend, recovery). A decision-aware loss function would
    penalize wrong "deploy" decisions 3-5x more than wrong "wait"
    decisions. This is a more honest calibration than binary accuracy.

3.  **The portfolio-as-optimizer wrapper.** Instead of optimizing a
    prediction separately and then feeding it to the portfolio, the
    predict+optimize framework would jointly optimize the feature
    weights to minimize portfolio regret. This requires differentiable
    portfolio construction, which is feasible with modern autograd
    frameworks.

### What Does NOT Apply

1.  **Continuous-time applications.** The Elmachtoub/Grigas work is
    often applied to supply chain and scheduling. The portfolio
    equivalent requires significant adaptation.

2.  **Very deep neural networks.** The project's data volume (1110
    weekly observations, \~35 features) is too small for deep learning.
    Linear + shallow gradient boosting is the correct model class.

3.  **Real-time retraining.** Decision-focused learning requires walking
    forward in a computationally tractable way. Retraining a PyTorch
    model weekly for 1100 weeks is feasible for shallow models but
    expensive for deep ones.

### Implementation Warning

Decision-focused learning is the highest overfitting risk approach in
this project. The combination of: - Small dataset (1110 observations) -
Complex decision landscape (6 market states × 7 sleeves × deployment
decisions) - High dimensionality of label construction choices (barrier
levels, horizons)

Creates massive opportunity for in-sample overfit. The ONLY acceptable
implementation discipline: 1. Declare all label parameters (profit
barrier, loss barrier, horizon) BEFORE looking at the full history. 2.
Never select hyperparameters based on full-history performance. 3.
Report only on the pre-declared 104-week holdout. 4. Compare against the
simplest possible benchmark: "deploy when Phase 1 quality \> threshold."

### Phase Placement

-   Frontier Phase 6: deploy/wait labels, meta-labeling,
    utility-weighted training

------------------------------------------------------------------------

## 10. Cross-Asset Attention and Lead-Lag Research

### Key Papers

-   Bianchi, D., Buechner, M., Tamoni, A. (2021): "Bond Risk Premiums
    with Machine Learning." *Review of Financial Studies*.
-   Lim, B. and Zohren, S. (2021): "Time-series forecasting with deep
    learning: a survey." *Philosophical Transactions of the Royal
    Society A*.
-   Ke, Z.T., Kelly, B.T., Xiu, D. (2020): "Predicting Returns with Text
    Data." *NBER Working Paper*.
-   Hjalmarsson, E. (2010): "Predicting Global Stock Returns." *Journal
    of Financial and Quantitative Analysis*.
-   Asness, C. et al. (2013): "Value and Momentum Everywhere." *Journal
    of Finance*.

### What This Research Suggests

1.  **Cross-asset lead-lag relationships exist and are exploitable.**
    Credit markets (HYG/LQD spreads) lead equity markets by 1–6 weeks in
    regime transitions. This is well-documented and economically
    motivated: credit pricing reflects forward-looking default risk;
    equity pricing is more susceptible to short-term sentiment.

2.  **Small-cap relative performance leads market quality.** When
    IWM/SPY ratio is rising, it signals broader risk appetite than
    large-cap leadership alone. When IWM/SPY ratio peaks and starts
    falling while SPY continues rising, it often signals late-cycle /
    narrowing leadership.

3.  **Attention models for multi-asset lead-lag.** Recent ML work
    proposes using self-attention (Transformer-style) to learn which
    assets lead which others in different regimes. However, these models
    require much more data than the project has available.

4.  **Simple correlation-based lead-lag diagnostics** are effective for
    the parameter range relevant here (1–8 week leads, weekly data, 35
    assets). Sophisticated models are not necessary for the first pass.

### What Realistically Applies

1.  **Static lead-lag diagnostics are the right starting point for Phase
    7.** Compute rolling 52-week cross-correlations between all pairs of
    important signals at lags of 1, 2, and 4 weeks. Identify which
    relationships are historically stable (present in \> 70% of rolling
    windows).

2.  **A "credit confirms equity" binary signal.** If HYG/LQD 4-week
    momentum is positive (credit is expanding), the equity regime is
    more likely to be sustained. This is directly implementable and
    should be a Phase 7 confirmation signal.

3.  **The bond/equity relationship as a regime transition signal.** When
    TLT momentum turns positive (bonds rallying) while equity is still
    rallying, it historically signals a late-cycle / risk-off
    transition. This can be computed from free data.

### What Does NOT Apply

1.  **Transformer / attention models.** The project's 1110 weekly
    observations and 35-asset universe cannot support meaningful
    attention model training. With transformer models, 10,000+
    observations per asset would be needed.

2.  **Text-based signals.** Ke, Kelly, Xiu's text data approach requires
    NLP pipelines and news data. Not within the project's scope.

3.  **High-frequency cross-asset dynamics.** The microstructure of ETF
    bid-ask spreads and intraday lead-lag dynamics are not relevant at
    weekly rebalance.

### Implementation Warning

Lead-lag relationships are non-stationary. The HYG → SPY lead may work
in normal credit cycles but may weaken during quantitative easing
periods when credit spreads are artificially compressed. Always monitor
rolling stability and deactivate signals when stability falls below
threshold.

### Phase Placement

-   Frontier Phase 7: HYG/LQD lead-lag, TLT lead-lag, IWM/SPY rotation
    diagnostic, UUP/EM lead-lag

------------------------------------------------------------------------

## 11. Relevant Open-Source Repos and Tools

### PyPortfolioOpt (<https://github.com/robertmartin8/PyPortfolioOpt>)

**What it offers:** Clean Python implementation of portfolio
optimization (MVO, HRP, Black-Litterman). The HRP implementation is
particularly clean and replicable.

**What applies:** The project already uses HRP. PyPortfolioOpt's
covariance estimation utilities (Ledoit-Wolf shrinkage, exponentially
weighted covariance) are useful as comparison tools for Frontier Phase
5.

**License:** MIT. Free to use with attribution.

**Implementation warning:** PyPortfolioOpt's default parameters are not
calibrated for weekly tactical allocation. The covariance estimation
window and shrinkage parameters need adjustment.

### Riskfolio-Lib (<https://github.com/dcajasn/Riskfolio-Lib>)

**What it offers:** Comprehensive portfolio optimization including HRP,
HERC, CVaR optimization, hierarchical clustering allocators.

**What applies:** Frontier Phase 5 (Allocator Objective Redesign) could
benefit from Riskfolio-Lib's CVaR optimization capabilities. A
CVaR-constrained allocator that is also opportunity-quality-aware could
be an interesting Phase 5 direction.

**License:** BSD 3-clause. Free to use with attribution.

**Implementation warning:** Riskfolio-Lib is more complex than the
project needs. Use only specific components (CVaR estimation, efficient
frontier tools).

### mlfinlab (<https://github.com/hudson-thames/mlfinlab>) / mlfinance

**What it offers:** Python implementation of several Lopez de Prado
methods including triple-barrier labeling, purged cross-validation,
meta-labeling, and fractional differentiation.

**What applies:** Frontier Phase 6. The triple-barrier implementation
and purged CV are directly usable.

**License:** BSD 3-clause (core components). Note: Some advanced
features are commercial.

**Implementation warning:** mlfinlab's implementations assume daily
data. Weekly adaptation requires parameter adjustment. Verify the
embargo period is adjusted to the project's weekly cadence (4-week
minimum embargo instead of the daily default).

### bt (<https://github.com/pmorissette/bt>) and vectorbt (<https://github.com/polakowo/vectorbt>)

**What they offer:** Flexible backtesting frameworks for portfolio
strategies.

**What applies:** These are useful for quick signal-level IC validation
in Phases 1–4 before full wrapper integration. The project's wrapper is
the production-appropriate tool, but bt or vectorbt can speed up
exploratory signal analysis.

**License:** bt = MIT. vectorbt = GNU LGPL 3.0.

**Implementation warning:** Neither framework replicates the project's
specific cost model (5bp half-spread turnover) or checkpoint
architecture. Use for exploration only; never as the definitive
performance source.

------------------------------------------------------------------------

## 12. Summary Table

| Source | Primary Phase | Key Contribution | Overfitting Risk |
|----|----|----|----|
| AQR TSMOM/Trend | Phase 2 | R², cross-horizon agreement | Low |
| Man Group speed | Phase 2 | Autocorrelation filter, speed blend | Low |
| Moreira-Muir | Phases 2, 3 | Per-ETF vol scaling | Low |
| Faber GTAA | Already implemented | `taa_10m_sma` sleeve | N/A |
| Newfound fragility | Phases 1, 2 | Path clarity, ensemble momentum | Low |
| ReSolve adaptive | Phase 5 | Confidence-weighted risk budget | Medium |
| Robeco defensive | Phase 4 | Quality factor leadership | Low |
| PIMCO/Bridgewater | Phases 7, 1 | Credit leads, macro quadrant | Low |
| Lopez de Prado | Phase 6 | Meta-labeling, purged CV, triple-barrier | **High** |
| Decision-focused ML | Phase 6 | Deploy/wait labels, utility loss | **Very High** |
| Cross-asset attention | Phase 7 | Lead-lag diagnostics | Medium |
| PyPortfolioOpt | Phase 5 | Covariance estimation tools | Low |
| mlfinlab | Phase 6 | Purged CV, triple-barrier implementation | Medium |

------------------------------------------------------------------------

*Document ends. No production files modified.*
