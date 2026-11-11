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

---

# Phases 2-5 (added after the independent view above was committed in `19f0029`)

## Phase 2: research and tools

**gs-quant 2.2.5, installed and run in a scratch environment.**

| Part | Without Goldman Marquee credentials | Use to us |
|---|---|---|
| `timeseries` maths: returns, volatility, max drawdown, rolling correlation and beta, z-scores, RSI, MACD, Bollinger bands, `basket_series` | **Ran, works** on our own series | None; duplicates pandas |
| `sharpe_ratio`, `excess_returns_` | **Ran, fails**: fetches a cash curve from Marquee | None |
| Instrument pricing and risk (`IRSwap.price()` etc.) | **Ran, fails**: `GsSession is not initialised` | None |
| Backtest engines, optimiser, portfolio manager | Classes import; **not run**. `GenericEngine` prices through Marquee | Unverified; no claim made |
| Datasets, risk models, reports | Need an institutional API key | None |

Verdict: nothing in it improves this project's testing or construction for an individual.

**Papers.** All found by web search this session and known from **snippets and summaries only, not
read in full**, unless marked.
- Gonçalves, Loudis & Ogden (2025): post-publication anomaly alphas are close to zero when weights use
  only pre-publication data. Consistent with this project's nulls.
- "What Useful Alphas?" (arXiv 2607.06502): anomaly returns vanish when both large-cap and post-2005
  restrictions apply. Consistent with the Phase 1 prior on stock selection.
- Cederburg, O'Doherty, Wang & Yan (JFE): volatility-managed portfolios fail in real time. Matches
  Step 342.
- Hartley & Schwarz (2019), month-end Treasury returns: abstract summary read; tested as T3.
- Bouman & Jacobsen (AER 2002), Halloween effect: **recalled**, tested as T1.
- Managed-futures ETFs and return stacking: practitioner commentary only; no academic test found.

**New technology.** Nothing found that changes the testing. The project's existing tools (purged CV,
deflated Sharpe, CSCV, block bootstrap, calibrated decile shape) are ahead of the free libraries.

## Phase 3: each Phase 1 idea against the record

| # | Idea | Status |
|---|---|---|
| 1 | SHY to IEF/TIP barbell | Already tried (Step 321: 50/25/25 SPY/GLD/IEF Sharpe 0.75 vs 0.78; TLT fails 2022) |
| 2, 42 | Risk-parity / HRP weights | Already tried (Step 318 HRP; Step 244 risk budgeting; min-variance is on a clock) |
| 3 | Rebalancing bands | In queue as B19, untested. **Tested: T4** |
| 4 | Capital-efficient stacked funds | **New. Tested: T5** |
| 5 | Multi-manager trend sleeve | New; reported inside T5 |
| 6 | Long/flat ETF trend | Already tried (Step 205, 1.0 allocator, Batch 03) |
| 7 | Volatility-managed equity | Already tried (Step 342, reverses 1933-1992) |
| 8 | International equity | Already tried (Step 246: 1.27 effective assets) |
| 9, 10 | Defensive / quality factor | Already tried (Step 296: 0 of 13 signals; Step 344: no FF6 alpha) |
| 11 | BTAL anti-beta sleeve | **New. Tested: T2** |
| 12 | Broad commodities | Already tried (Step 321: DBC fails both crises; Step 277) |
| 13 | Bond carry / roll-down | New, not tested: the book holds no duration to tilt. Queued C |
| 14, 15 | Put-write, buy-write, collar | Already tried (Step 330: no alpha after beta) |
| 16 | VIX switch | Already tried (Steps 319, 321: random labels do as well) |
| 17 | Turn of month | Already tried (Step 341, dead) |
| 18 | Pre-FOMC; overnight drift | Pre-FOMC closed by the literature (Step 369). Overnight closed unstarted: 500 trades a year |
| 19 | Treasury month-end | **New. Tested: T3** |
| 20 | Halloween | **New. Tested: T1** |
| 21 | Merger arbitrage | Already tried (Step 370: funds fail); deal-level blocked on delisted prices (P5) |
| 22 | Spin-offs | Already tried (Step 373) |
| 23 | Net issuance / buybacks | Already tried (Step 201 built it; Step 296 screen) |
| 24 | Index additions/deletions | Closed by the literature (Step 369) |
| 25 | Closed-end fund discounts | New; **blocked**: no free point-in-time NAV history. Queued B |
| 26 | Earnings-announcement return | Already tried (Step 374); avoid-list use open as B20 |
| 27 | Insider clusters | Already tried (Steps 125, 298) |
| 28 | 13F best ideas | Already tried (Step 258) |
| 29 | Product-network lead-lag | Already tried (A19, A19b, A20, A21) |
| 30 | Federal contracts | Already tried (Step 345, inconclusive on density) |
| 31 | 10-K text change | Already tried (Step 255, inconclusive by construction) |
| 32 | Attention avoid list | Wikipedia and GDELT tried (Steps 348, 353); WSB open as B17 |
| 33 | Gradient-boosted ranking | Already tried (Step 264: only residual momentum matters) |
| 34 | LLM reading of filings | Parked as C4 |
| 35 | Regime / volatility model | Already tried (market-state classifier; Step 319); A3 open |
| 36 | Bitcoin sleeve | Closed unstarted: crypto closed on both gates |
| 37 | Leveraged ETF + 200-day | Closed unstarted: leverage on a correlated exposure |
| 38 | Catastrophe-bond fund | New; **blocked**: investable funds have under 3 years of record or need an adviser. Queued C |
| 39, 40 | Cash yield, tax-loss harvesting, asset location | New; not backtests. Recommendations below |
| 41 | Risk-budgeted blend of unrelated sleeves | **New. Tested: T6** |

36 of 42 already answered. Six tested. My Phase 1 prior held: nothing in the stock-selection rows
was new, and what was new sat in construction.

## Phase 4: the combination, designed before testing

Sleeves that survived as *candidates* for a blend: equity, gold, cash, trend. Sleeves the record had
already marked as weak but which are genuinely different streams: merger arbitrage, anti-beta,
intermediate Treasuries. The design registered as T6 used all six with inverse-volatility weights and
no borrowing. Measured (monthly, 2013-2026):

| | SPY | GLD | IEF | Trend | MERFX | BTAL |
|---|---|---|---|---|---|---|
| SPY | 1.00 | 0.08 | 0.10 | −0.15 | 0.41 | −0.59 |
| GLD | | 1.00 | 0.38 | 0.09 | 0.05 | 0.10 |
| IEF | | | 1.00 | −0.15 | −0.05 | 0.14 |
| Trend | | | | 1.00 | −0.09 | 0.18 |
| MERFX | | | | | 1.00 | −0.30 |

Effective number of bets: **5.18 of 6**, against 2.85 of 3 for SPY/GLD/SHY.

**The honest answer the brief asked for:** yes, the best realistic improvement is construction, costs
and diversification, not a new signal, and even diversification has a ceiling. Six nearly independent
sleeves raised Sharpe by 0.05 (p 0.41) and cut return from 7.7% to 4.4%, because most of the added
sleeves earn about the cash rate. More independent bets do not help when the bets have no return.

## Phase 5: results

Full record in `PROJECT_HISTORY.md` Step 377; numbers in `evidence/fresh_eyes_v2/results.json`.

| Trial | Verdict | Strategy (10 bps) | Comparator |
|---|---|---|---|
| T1 Halloween | Fail | Sharpe 0.54, CAGR 6.9%, DD −30% | 50/50 mix: 0.72, 6.7%, −28% |
| T2 BTAL sleeve | Fail | Sharpe 0.73, CAGR 5.7%, DD −8.6% | benchmark: 0.82, 7.7%, −12.7% |
| T3 Treasury month-end | Fail on cost; effect real (t 2.79) | +2.29%/yr at 0 bps, −0.12% at 10 bps | cash |
| T4 Rebalancing bands | Recommended | Sharpe 0.83, CAGR 8.62%, turnover 0.12× | weekly: 0.81, 8.41%, 0.64× |
| T5 Stacked trend | Supported as construction; p 0.165 | Sharpe 0.88, CAGR 8.42%, DD −9.0% | benchmark: 0.80, 7.68%, −12.7% |
| T6 Six-sleeve blend | Fail | Sharpe 0.85, CAGR 4.36%, DD −4.1% | benchmark: 0.80, 7.68%, −12.7% |

## Queue entries drafted, NOT written to `RESEARCH_QUEUE.md`

The queue's working copy holds an unconfirmed change (see Step 376), so these wait for the owner.

**For the Closed table:**
- Halloween / Sell in May (T1): fails; Sharpe 0.54 vs 0.72 for a same-exposure mix, 0 of 4 regimes. Step 377.
- BTAL anti-beta sleeve (T2): fails; pays in crises, costs −3.35% a year, loses to plain cash. Step 377.
- Treasury month-end as a standalone trade (T3): effect real (t 2.79 after publication), fails at 10 bps. Step 377.
- Six-sleeve inverse-vol combination (T6): fails; 5.18 effective bets, Sharpe +0.05, CAGR 4.4% vs 7.7%. Step 377.
- Rebalancing bands (was B19): done; 5pp band or annual reset recommended over weekly. Step 377.
- gs-quant: nothing usable without Marquee beyond pandas-equivalent maths. Step 376.
- Overnight drift, leveraged ETF with 200-day filter, one-coin Bitcoin sleeve: closed unstarted. Step 376.

**New open items:**
- **A35. Stacked-trend twin clock** (free; blocker: owner's decision on internal leverage). 20% in a
  stacked S&P-plus-trend fund, 13.3% SPY, 33.3% GLD, 33.3% SHY equals the benchmark plus 20% trend.
  Record forward next to `trend_sleeve_8020_v1`. T5 supports it as construction, not as alpha.
- **A36. Banded twin of the benchmark clock** (free; blocker: a recorder and a cycle dry run). T4.
- **B21. Month-end Treasury timing of trades already being made** (free; blocker: the book holds SHY,
  where the effect is untested and likely smaller). Never as a standalone trade.
- **B22. Second and third trend manager in the sleeve** (free; blocker: KMLM and CTA have under six
  years of record). T5 shows fund Sharpe ranging 0.29 to 0.63 since 2019.
- **B23. Closed-end fund discounts** (blocked: no free point-in-time NAV history).
- **C6. Catastrophe-bond funds** (blocked: record under three years or adviser-only access).
- **C7. Bond carry / roll-down** (parked: the book holds no duration to tilt).
