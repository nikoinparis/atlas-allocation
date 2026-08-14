# Signal Discovery Source Review

Research-only source review. The sprint copied ideas and category patterns, not code. No source was treated as proof that a signal works in this repo; every idea remains untested until it passes the project IC/state/holdout/cost framework.

## Sources Reviewed

- **AQR_TSMOM**: AQR Time Series Momentum dataset / Moskowitz-Ooi-Pedersen: https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data
- **AQR_LIBRARY**: AQR academic data library: https://www.aqr.com/insights/datasets/an-academic-quality-data-library-for-practitioners
- **AQR_VME**: AQR Value and Momentum Everywhere dataset: https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Factors-Monthly
- **AQR_BAB**: AQR Betting Against Beta dataset: https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Original-Paper-Data
- **NBER_VOL**: Moreira and Muir, Volatility Managed Portfolios: https://www.nber.org/papers/w22208
- **FABER_TAA**: Meb Faber, A Quantitative Approach to Tactical Asset Allocation: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- **FRED_SAHM**: FRED Sahm Rule Recession Indicator: https://fred.stlouisfed.org/release?rid=456
- **CBOE_VIX**: Cboe VIX historical data and volatility indices: https://www.cboe.com/tradable-products/vix/vix-historical-data
- **AAII**: AAII historical sentiment download instructions: https://aaiiweb.atlassian.net/wiki/spaces/APS/pages/156663829/Sentiment%2BSurvey
- **BREADTH**: Herding for Profits / market breadth paper: https://www.sciencedirect.com/science/article/pii/S0264999319312982
- **GITHUB_AA**: GitHub asset-allocation topic and TAA repos: https://github.com/topics/asset-allocation
- **PURGED_CV**: Purged cross-validation overview: https://en.wikipedia.org/wiki/Purged_cross-validation
- **MAN_TREND**: Man Group trend-following crisis-alpha discussion: https://www.man.com/maninstitute/trend-following-equity-and-bond-crisis-alpha
- **ROBECO_FACTORS**: Robeco factor investing research: https://www.robeco.com/en-int/insights/2022/12/factors-are-an-all-season-phenomenon
- **PIMCO_CREDIT**: PIMCO public credit liquidity lens: https://www.pimco.com/us/en/insights/the-credit-market-lens-a-data-driven-look-at-public-credit-liquidity
- **BRIDGEWATER_REGIME**: Bridgewater growth/inflation/liquidity framing: https://www.bridgewater.com/_document/a-new-era-of-higher-inflation-risks?id=0000019a-0342-d9ed-affe-cb72d0730000
- **QUANTPEDIA**: Quantpedia value/momentum/carry categories: https://quantpedia.com/strategies/value-and-momentum-factors-across-asset-classes
- **CBOE_PUTCALL**: Cboe daily options market statistics / put-call ratios: https://www.cboe.com/markets/us/options/market-statistics/daily

## What Translates Well To This Repo

- AQR-style multi-asset trend, value, carry, defensive, and BAB categories map naturally to Layer 1 signal files and redundancy/IC monitoring.
- Faber/GTAA and TAA research maps to weekly/monthly trend filters, moving-average slope, and canary/risk-on confirmation. The repo already has many price inputs, so these are feasible without new data.
- Moreira-Muir volatility management maps to realized volatility trend, downside volatility, volatility-managed momentum, and signal-environment shrinkage. It should be tested as signal quality/risk adjustment, not as a blind turnover increase.
- FRED macro data maps to a repaired `macro_weekly` ingestion path: Sahm rule, yield curve, real rates, financial conditions, funding stress, industrial production, housing starts, and policy-rate trend.
- Cboe volatility indices map to VIX/VIX3M/VIX6M already present, plus VVIX and VIX9D as stress-protection candidates.
- Breadth literature maps to an immediate ETF/sector breadth proxy and a future paid/PIT stock breadth path.
- López de Prado validation ideas map to purged walk-forward tests, triple-barrier/meta-labeling only after a base signal edge exists, deflated/selection-aware evidence, and explicit multiple-testing discipline.

## What Does Not Translate Cleanly

- HFT, market making, tick data, order book imbalance, queue position, and intraday execution signals are outside a weekly ETF allocation project.
- Proprietary order flow, institutional ETF flows, TRACE microstructure, and paid option datasets are not realistic unless explicitly marked paid/future.
- Current-constituent stock breadth can be useful for research, but it is not production-valid because it has survivorship/lookahead risk unless PIT membership is obtained.
- Black-box ML/RL is already represented in the ML lab and remains high-risk; the evidence says better simple signals should come before R5/R6 ensemble work.

## Source-Specific Notes

- **AQR**: supports the broad taxonomy of trend/momentum, value, carry, defensive, BAB, and cross-asset style premia. In this repo, raw momentum is already strong and likely crowded/redundant; carry/value/BAB need better proxies or state-gating.
- **Alpha Architect / Faber / TAA literature**: reinforces simple trend filters and tactical allocation, but current repo already has trend. The underexplored part is breadth/canary confirmation and path quality.
- **ReSolve/Newfound/GestaltU-style TAA**: maps to ensemble-like signal agreement/disagreement, trend plus risk filters, and whipsaw control. This is appropriate as research-only meta-signal work before R5.
- **Man Group trend following**: crisis-alpha framing is relevant, but weekly long-only ETFs cannot replicate futures trend following. The realistic translation is defensive/risk-off detection and trend quality.
- **PIMCO credit/liquidity**: direct credit and liquidity stress proxies are more promising than the HYG/LQD price proxy that R2 used when OAS failed.
- **Bridgewater public regime framing**: growth/inflation/liquidity quadrant thinking is realistic if simplified to public FRED/ETF proxies and treated as slow regime information.
- **Robeco/factor research**: factor ETF leadership and defensive/low-vol leadership are realistic weekly ETF proxies.
- **Quantpedia-style taxonomy**: useful as a checklist, but high multiple-testing risk means only simple, pre-specified signals should enter the sprint queue.
- **GitHub repos**: useful for architecture patterns like TAA notebooks and allocation libraries, but no code should be copied unless license and fit are clear. Current task only borrows ideas.

## Repo Inspection Summary

- Existing strong signals are mostly momentum/trend/MA distance; this raises redundancy risk for additional price-momentum variants.
- R2 found `r2_dollar_strength` as the only strict pass. Macro/VIX/credit looked useful in calm states but dangerous in stressed_panic, implying the next work should test state-gated or defensive versions.
- R4 showed ETF pair mean-reversion is not a broad weekly signal family here.
- `macro_weekly.csv` is underpopulated, making FRED ingestion one of the most valuable infrastructure tasks for future research.

## Citation Links

- AQR Time Series Momentum dataset / Moskowitz-Ooi-Pedersen: https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data
- AQR academic data library: https://www.aqr.com/insights/datasets/an-academic-quality-data-library-for-practitioners
- AQR Value and Momentum Everywhere dataset: https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Factors-Monthly
- AQR Betting Against Beta dataset: https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Original-Paper-Data
- Moreira and Muir, Volatility Managed Portfolios: https://www.nber.org/papers/w22208
- Meb Faber, A Quantitative Approach to Tactical Asset Allocation: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- FRED Sahm Rule Recession Indicator: https://fred.stlouisfed.org/release?rid=456
- Cboe VIX historical data and volatility indices: https://www.cboe.com/tradable-products/vix/vix-historical-data
- AAII historical sentiment download instructions: https://aaiiweb.atlassian.net/wiki/spaces/APS/pages/156663829/Sentiment%2BSurvey
- Herding for Profits / market breadth paper: https://www.sciencedirect.com/science/article/pii/S0264999319312982
- GitHub asset-allocation topic and TAA repos: https://github.com/topics/asset-allocation
- Purged cross-validation overview: https://en.wikipedia.org/wiki/Purged_cross-validation
- Man Group trend-following crisis-alpha discussion: https://www.man.com/maninstitute/trend-following-equity-and-bond-crisis-alpha
- Robeco factor investing research: https://www.robeco.com/en-int/insights/2022/12/factors-are-an-all-season-phenomenon
- PIMCO public credit liquidity lens: https://www.pimco.com/us/en/insights/the-credit-market-lens-a-data-driven-look-at-public-credit-liquidity
- Bridgewater growth/inflation/liquidity framing: https://www.bridgewater.com/_document/a-new-era-of-higher-inflation-risks?id=0000019a-0342-d9ed-affe-cb72d0730000
- Quantpedia value/momentum/carry categories: https://quantpedia.com/strategies/value-and-momentum-factors-across-asset-classes
- Cboe daily options market statistics / put-call ratios: https://www.cboe.com/markets/us/options/market-statistics/daily
