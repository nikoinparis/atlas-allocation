# Fresh-eyes review V2 (Phase 1: independent view)

Written 2026-11-11, before opening `PROJECT_HISTORY.md`, `RESEARCH_QUEUE.md` or any research doc.
Inputs: the brief's facts, the forward protocols and status files, and the ETF weekly panel.
Everything in this file is a first impression, not a tested claim. Phases 2-4 are appended below.

## 1. First impression

**What the portfolio is, economically.** Twelve clocks, about three exposures: US large-cap equity
beta, gold, and near-cash (SHY). Every stock clock is a long-only top-N US book, so each one is
"SPY beta plus tracking error". The ETF allocation books choose among the same few assets. The
count of clocks overstates the number of independent bets by a wide margin.

**The benchmark is a strong, low-risk mix, and that is why it is hard to beat.** From the ETF panel
(weekly, 2004-11 to 2026-09, rf = 0, my own quick calculation, not a tested result):

| Book | CAGR | Vol | Sharpe (rf=0) | Max DD |
|---|---|---|---|---|
| SPY/GLD/SHY thirds | 8.47% | 8.54% | 1.00 | -18.9% |
| SPY | 10.99% | 17.45% | 0.69 | -54.6% |
| 60/40 SPY/IEF (2002-) | 8.68% | 10.07% | 0.88 | -31.4% |

Three cautions on that 1.00:
1. Gold compounded at roughly 10% a year over this window. That is one asset's good two decades,
   not a law. Gold's real return 1980-2000 was sharply negative. A third of the book rests on it.
2. The mix was chosen from thirteen configurations on this same window (the protocol says so).
3. A third in SHY is one third of capital earning the bill rate. It lowers vol, not risk-adjusted
   return; the mix is simply a de-levered two-asset portfolio.

**Where it is weak.**
- *No duration, no credit, no international equity, no commodities beyond gold, no real-rate
  asset.* 2022 hurt 60/40 because stocks and bonds fell together; this book avoided that by
  holding no bonds, but that is an accident of composition, not a designed inflation defence.
- *The "more return" books buy return with beta.* `spy_riser_5050` is higher return and deeper
  drawdown, as its own role line says. Nothing in the set raises return per unit of risk.
- *Long-only stock selection in a survivor-heavy panel.* Only 44.6% of the 2012 roster has prices.
  Any small-cap or high-volatility tilt is flattered. Large-cap-only tests are far less affected.
- *The forward clocks cannot answer the question they are asked.* The standard error of an annual
  Sharpe ratio is about 1.0. A 52-week clock cannot separate a Sharpe of 1.0 from 0.8. The clocks
  are an honesty device (no backfill, no restarts), which is valuable, but verdicts will come
  from long external records and economic reasoning, not from 52 weeks.
- *Weekly reset to target weights.* In a taxable account that is turnover and realised gains for
  no measured benefit over banded or annual rebalancing.
- *Single-manager risk in the trend sleeve.* DBMF is one replication model.
- *Low vol means low return.* An 8.5%-vol book cannot beat SPY's CAGR in a bull market. If the aim
  is more return, the efficient routes are (a) less cash, (b) capital-efficient funds that carry
  leverage internally, (c) genuinely uncorrelated sleeves. Stock picking is the inefficient route.

**What a long-only individual can actually harvest.** Market-neutral premia are out of reach
directly. What remains: asset-class diversification, funds that package long/short strategies
(managed futures, merger arb, anti-beta, option overlays), construction and rebalancing, taxes
and fees, and event calendars that only require being long or flat.

## 2. Long list of candidates

Tag: **C** construction, **P** risk premia, **E** event/structural, **O** options/vol,
**S** seasonality, **D** alt data, **M** machine learning, **X** combination.

| # | Tag | Idea | Why it might work | Data |
|---|---|---|---|---|
| 1 | C | Replace SHY with a T-bill/IEF/TIP barbell | Adds term premium and a deflation hedge the book lacks | on disk |
| 2 | C | Inverse-vol (risk-parity) weights over SPY/GLD/IEF/commodities instead of equal thirds | Equal thirds is equity-risk dominated | on disk |
| 3 | C | Banded or annual rebalancing instead of weekly reset | Lower turnover and tax drag; rebalancing premium is small | on disk |
| 4 | C | Capital-efficient "stacked" funds (NTSX 90/60, GDE, RSSB/RSST) to free cash for diversifiers | Leverage inside the fund, none in the account | free (Yahoo) |
| 5 | P | Multi-manager trend sleeve (DBMF + KMLM + CTA) | Removes single-replicator risk | free |
| 6 | P | DIY long/flat time-series momentum on the 35-ETF panel | Trend is the best-documented crisis diversifier | on disk |
| 7 | P | Volatility-managed equity sleeve (scale SPY by inverse trailing variance) | Moreira-Muir; cuts left tail | on disk |
| 8 | P | Global equity (EFA/EEM/VEA) in place of part of SPY | US-only is a single-country bet | on disk |
| 9 | P | Defensive equity factor funds (USMV, QUAL, SPLV) in place of SPY | Low-risk anomaly, long-only-friendly | free |
| 10 | P | DIY large-cap quality/profitability book from XBRL | Novy-Marx gross profitability; large caps limit survivorship bias | on disk |
| 11 | P | Anti-beta fund (BTAL) as a crisis sleeve | Negative equity beta, positive carry in sell-offs | free |
| 12 | P | Broad commodity carry/roll-optimised fund next to gold | Diversifies the inflation hedge away from one metal | on disk (PDBC) + futures |
| 13 | P | Bond carry/roll-down: hold the steepest point of the curve | Carry predicts bond returns across maturities | treasury vintages |
| 14 | O | Cash-secured put-write (PUT/WPUT) in place of part of SPY | Volatility risk premium; equity-like return at lower vol | on disk (CBOE) |
| 15 | O | Buy-write and collar indices (BXM, BXMD, CNDR) | Same premium, different payoff | on disk (CBOE) |
| 16 | O | VIX term-structure or level as an equity de-risk switch | Backwardation flags stress | on disk (VIX) |
| 17 | S | Turn-of-month equity effect, long/flat | Persistent flow effect | daily prices |
| 18 | S | Pre-FOMC and overnight-return drift in SPY | Documented, though decayed after publication | daily OHLC |
| 19 | S | Treasury intramonth pattern (month-end bond strength) | Institutional rebalancing flow | daily prices |
| 20 | S | "Halloween" or Sell-in-May switch between SPY and bonds | Old, simple, worth one honest look | on disk |
| 21 | E | Merger-arbitrage sleeve (MNA/ARB/MERFX or DIY cash deals) | Deal-risk premium with low equity beta outside crashes | free + SEC |
| 22 | E | Spin-off parents and children, held 12 months | Forced selling by index funds | SEC filings |
| 23 | E | Net buyback/issuance: avoid issuers, hold shrinkers | Among the most robust anomalies after publication | XBRL shares |
| 24 | E | Index addition/deletion reversal | Deletions rebound | needs lists |
| 25 | E | Closed-end fund discount mean reversion | Structural retail mispricing | free, scrape |
| 26 | E | Earnings-announcement return (3-day reaction) alongside SUE | Captures surprise without analyst data | on disk |
| 27 | D | Insider cluster purchases (Form 4), event-style not decile-style | Sparse signal needs event-study treatment | on disk |
| 28 | D | 13F "best ideas" / conviction cloning | Managers' top positions outperform their books | on disk |
| 29 | D | Product-network (Hoberg-Phillips) peer lead-lag momentum | Slow diffusion across linked firms | on disk |
| 30 | D | Government contract award surprise (USASpending) | Underreaction to backlog | on disk |
| 31 | D | 10-K text change ("Lazy Prices") as an avoid list | Changed filings predict bad news | SEC filings |
| 32 | D | Attention spikes (Wikipedia, WSB, GDELT) as an avoid list | Attention-grabbing stocks underperform | on disk |
| 33 | M | Gradient-boosted ranking on OSAP-style characteristics, large caps only | Non-linear combination of weak signals | on disk |
| 34 | M | LLM reading of 8-K/10-Q for tone or guidance change | New technology; cheap now | SEC filings |
| 35 | M | Regime or volatility model (HMM, GARCH) to scale total risk | Vol clusters and is forecastable; returns are not | on disk |
| 36 | P | Small Bitcoin sleeve, trend-filtered (spot ETF) | Uncorrelated in calm, high vol; sizing is everything | free |
| 37 | P | Leveraged index ETF with a 200-day filter | High risk; test only to kill or confirm | on disk |
| 38 | P | Insurance-linked / catastrophe-bond fund | Truly unrelated premium (hurricanes, not markets) | free, short record |
| 39 | C | Cash-yield hygiene: T-bill ETF (SGOV/BIL) vs SHY, I-bonds, tax location | Free basis points, no model | free |
| 40 | C | Tax-loss harvesting and holding-period management on the stock sleeves | After-tax return is the return | none |
| 41 | X | Risk-budgeted blend of equity + gold + trend + put-write + merger-arb + anti-beta | The test of "mixing unrelated streams" | above |
| 42 | X | Hierarchical risk parity or shrinkage covariance for the blend | Stable weights with few assets | on disk |

## 3. Prior, before any research

My day-one expectation, stated so it can be checked later: the realistic improvement is in rows
tagged C, P and X (construction, premia packaged in funds, and combination), with one or two
option-overlay and event sleeves as candidates for genuinely different return streams. I expect the
stock-selection rows (D, M) to add tracking error rather than Sharpe for a long-only investor, and I
would require a monotone decile relationship on large caps before building anything on them.
