# Dashboard Strategy Survival Lab v2

## Purpose

This study applies one comparable historical-survival battery to all six
strategies saved in the Version 2 dashboard. It is designed to answer three
different questions without mixing them together:

1. Did the saved historical path survive prespecified modeled stresses?
2. Did the strategy pass its original research and falsification gates?
3. Has it accumulated enough untouched forward and implementation evidence to
   be considered proven in the real world?

The answer to the third question is **no for all six strategies**. Every result
remains research-only and live trading remains disabled.

## Frozen test battery

The suite uses native weekly records rather than the dashboard's visual daily
expansion. It includes:

- 10,000 moving-block bootstrap paths over 52 weeks, using both 4-week and
  13-week blocks;
- full-history and rolling-52-week drawdown and return checks;
- one additional copy of recorded trading costs, representing doubled costs;
- an additional 300 basis points of financing expense on borrowed exposure;
- a 25% haircut to every positive weekly return while retaining every loss;
- one forced -20% week inside an equal trailing-52-week window;
- largest displayed holding concentration; and
- the existing research-gate and untouched-forward status.

Monte Carlo preserves local sequences through block resampling, but it still
resamples the distribution already observed. It cannot represent every future
regime, liquidity discontinuity, delisting, price gap, financing change, or
model failure.

## Results

| Strategy | Modeled score | Historical grade | MC profit probability | MC drawdown over 30% | Worst rolling year | Live verdict |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| Dynamic Breadth-20 | 75 | Historically resilient | 95.84% | 0.68% | -14.07% | Not proven live |
| Sector-aware ensemble | 75 | Historically resilient | 94.70% | 0.80% | -14.06% | Not proven live |
| Residual-Controlled 1.25x | 75 | Historically resilient | 94.62% | 1.59% | -16.17% | Not proven live |
| Fragile Sector 1.35x | 75 | Historically resilient | 93.28% | 5.86% | -20.88% | Not proven live |
| Growth / Micron | 55 | Mixed evidence | 81.14% | 21.91% | -18.47% | Not proven live |
| ETF incumbent | 40 | Historically fragile | 77.72% | 5.31% | -39.81% | Not proven live |

The model score is deliberately not called a probability of future success.
The first four paths survived most of this modeled battery, but all had a
negative historical rolling year and all breached the conservative 30%
largest-displayed-holding threshold. The current 150.86% leader's 13-week
block bootstrap has a median 52-week return of 48.29%, a 5th-percentile return
of -0.83%, and a 1.59% chance of crossing a 30% drawdown in the resampled paths.

The 174.97% path has the largest modeled return ceiling but worse tail behavior:
its 5th-percentile 52-week return is -3.54% and 5.86% of paths cross a 30%
drawdown. The Micron-led strategy is materially more fragile, with a -19.21%
5th-percentile return and a 21.91% modeled probability of a 30% drawdown.

## Real-world gaps

The dashboard exposes the missing inputs rather than assuming them away:

- current executable spreads and market impact;
- portfolio-size-specific liquidity and days to exit;
- broker margin, borrow, and changing financing terms;
- taxes and account-specific limits;
- future delistings, data outages, and model drift; and
- 52 untouched forward observations for every eligible strategy.

The displayed concentration metric is conservative. A 90% ETF holding is not
the same as a 90% single-stock holding, but look-through ETF factor and issuer
exposures are not yet available in this dashboard payload.

## Next return-improvement program

The strongest next experiment is not additional fixed leverage. It is a
predeclared cross-strategy residual allocator:

1. measure lagged correlation and incremental alpha among the six saved paths;
2. select only sleeves whose recent return is not explained by the incumbent;
3. size them with covariance shrinkage and explicit issuer/sector look-through;
4. allow exposure to rise only when breadth, liquidity, and tail-risk gates all
   agree; and
5. validate the complete allocator under purged walk-forward windows, execution
   delays, doubled costs, missing-name stress, and untouched forward evidence.

This route targets genuinely additive returns. Financing can be tested after a
new unlevered source improves the portfolio; it should not be mistaken for the
source of alpha.

A post-result overlap diagnostic identifies the first branch to freeze. The
150.86% leader had only 0.079 recent-return correlation with the fragile 1.35x
sector path and 0.096 with Dynamic Breadth-20, versus 0.812 with the ETF
incumbent and 0.937 with the sector-signal ensemble. A discovery-only 80/20
leader/fragile-path blend returned 158.52% over the latest 52 weekly records,
with 3.730 Sharpe and -10.87% drawdown. Because the added source already failed
its own research gates and this blend was examined after seeing the sample,
these numbers are a hypothesis—not acceptable evidence. The next sealed run
should test whether a capped, unlevered residual version of that sleeve retains
the diversification benefit under purged walk-forward and issuer-removal tests.

## Evidence

- `config/dashboard_strategy_survival_lab_v2.json`
- `scripts/run_dashboard_strategy_survival_lab_v2.py`
- `tests/test_dashboard_strategy_survival_lab_v2.py`
- `evidence/dashboard_strategy_survival_lab_v2/final_result.json`
- `dashboard/public/strategy-survival.json`
- `dashboard/src/app/survival/page.tsx`
