# Research Queue

The living list of what to do next, ranked. **Read this before proposing anything new.**

Three of the six strategies proposed on 2026-09-06 had already been tested and rejected in
`PROJECT_HISTORY.md` and nobody remembered. This file exists so that stops happening in both
directions: good ideas do not get lost, and dead ideas do not get retried.

## How to use it

- **Add** an idea the moment it appears, even half-formed. A line here costs nothing; a lost
  idea costs a year.
- **Rank** it S / A / B / C. S means promising *and* actionable now. See the tier definitions
  below — they are about expected value and readiness, not about how interesting it sounds.
- **Free and paid are separate lists.** Nothing in the paid list gets started without the
  owner confirming the spend first.
- **Delete it when it is done**, and move a one-line verdict into `Closed` at the bottom so it
  is never proposed again. The full record stays in `PROJECT_HISTORY.md`.
- Every item names its **blocker** and its **data**, because "we forgot" is almost always
  "nobody wrote down what was stopping it."

## Tiers

| tier | meaning |
|---|---|
| **S** | Plausibly moves the needle, data is available, nothing is blocking a start today |
| **A** | Worth doing, but either the payoff is smaller or a dependency has to be built first |
| **B** | Real ideas with a known ceiling, or ones waiting on something else to resolve |
| **C** | Parked. Recorded so it is not re-proposed, not because it is worthless |

---

# FREE QUEUE

## S tier

### S1. SEC 10-K language change *(measured 2026-09-06; see below before continuing)*
**Status:** source-blocked since Step 202, never unblocked. This is the lost item that prompted
this file.
**Why it matters:** the only genuinely orthogonal information source available for free. Every
signal in the registry is a transform of prices or of reported numbers; filing *prose* is a
different channel. Step 245 measured the whole portfolio at 1.57 effective independent
strategies, and no rearrangement of price and fundamentals data will raise that.
**Data:** SEC EDGAR full text, free. The acquisition queue already exists: **9,755 filings
across 1,413 issuers** with at least one year-over-year pair, hash-backed.
**Blocker:** nobody ran the download. Needs SEC fair-access rate limiting and a parser for
stable comparable sections.
**Prior art here:** `scripts/audit_sec_language_change_readiness_v1.py`,
`evidence/sec_language_change_readiness_v1/`. The causal comparison is already registered.

**Measured, Step 255.** 9,754 filings acquired and parsed, 8,327 pairs, 2019-2026. Zero of
twelve configurations clear Bonferroni -- but the result is **inconclusive by construction**,
not negative. Cosine on word counts is degenerate (interquartile range 0.0020 across the whole
cross-section); jaccard is the right measure. And 10-K filings are annual and cluster in Q1, so
eight years give nine cross-sections, at which the smallest establishable IC is about 0.110 --
twice what any equity signal achieves. Best row: jaccard on Item 7 at 26 weeks, IC +0.0553,
t = 2.00, surviving the length control at +0.0579.
**To settle it:** extend the corpus to 2011 for roughly fifteen cross-sections, and declare
*one* measure and *one* horizon in advance instead of twelve trials. The text is acquired and
parsed, so this is a further download rather than a fresh start.

### S2. Earnings call transcripts
**Status:** new, never attempted.
**Why it matters:** same argument as S1 and a second, independent text channel. Management
language in a call is not in the 10-K and not in the price.
**Data:** `defeatbeta-api` (Apache-2.0, PyPI), backed by a HuggingFace Yahoo mirror with DuckDB.
60+ quarters deep on the sample checked. Free, no stated rate limit.
**Caveat:** it is a Yahoo mirror, so it inherits Yahoo's quality problems. Treat it the way
Steps 239-240 treated the price panels: audit before use, never trust a vendor panel unchecked.
**Do S1 first** — SEC text is authoritative, this is a mirror.

### S4. Beta-hedged reconstruction of the existing books *(new 2026-09-06)*
**Status:** never attempted. Every config in this repo sets `shorting: false` or
`long_only: true` -- US and Indonesia alike. The constraint has never been lifted or costed.
**Why it matters:** Step 245 measured growth-top-five at IC **-0.0015** and realised IR
**+0.457**, a transfer coefficient of **-103**. Those two facts cannot both be about stock
selection. Step 193 hit the same wall from the other side: low asset growth produced a positive
long-short spread that "does not convert into a long-only portfolio without a short book this
project cannot cost or borrow." A beta hedge is what separates selection alpha from market
exposure, and it is the only structural change on this list that needs **no new data at all**.
**What it answers:** whether these books contain any selection skill, or are levered beta plus
single-name concentration. Either answer is worth more than another signal test.
**Cost:** one script over the saved book weights and the benchmark path. Hedge against the
equal-weight panel or SPY, charge borrow explicitly, report at 0/10/50/100bps.
**Not a promotion path on its own.** A market-neutral book still faces every existing gate, and
the equal-weight panel benchmark to beat is 22.21% CAGR / 1.28 Sharpe / -20.3% drawdown.

## A tier

### A0. Institutional co-ownership linkage from Form 13F  *(new 2026-09-06)*
**Status:** never attempted here. This is the free analogue of the thread that is stuck in the
paid queue.
**The idea:** P2's shared-analyst-coverage effect works because two stocks watched by the same
people move together with a lag. The linkage does not have to be analysts. **Two stocks held by
the same institutional managers** is the same shared-attention mechanism, and 13F is free.
**Data:** SEC Form 13F structured data sets. **July 2013 to May 2026**, quarterly, flattened
cover page plus an information table of holdings per manager per security, 70-95 MB per quarter,
about 4 GB in total. Free bulk download, no rate limit, authoritative rather than a mirror.
**Why it ranks here and not in S:** the construction is more involved than a single-signal test
-- build the manager-holding matrix, link stocks by shared holders, form each stock's connected
portfolio, sort on its lagged return -- and it inherits the sample problem that 52 quarters is
still only 52 observations. But it is the only free path to a linkage signal, and linkage is the
one family in the literature that is genuinely not a price or fundamentals transform.
**Caveats to design around before starting:** 13F is filed 45 days after quarter end, so the
point-in-time date is the filing date and not the report date; it covers long US equity positions
over $100m only; and it says nothing about shorts.

### A1. The three near-zero-correlation OSAP anomalies that need no new data
**Status:** identified in Step 216, never tested.
**Which:** `EBM` (enterprise book-to-market, correlation 0.0018 against our strategies),
`ChForecastAccrual` (0.0029), `IO_ShortInterest` (0.0033). Also `HerfBE`, `DelDRC`, `grcapx3y`,
`AM`, `IndRetBig`, `Illiquidity` in the same band.
**Why it matters:** Step 216 found 54% of the published anomaly library correlates above 0.3
with what we own, but these sit near zero. Orthogonality is the scarce thing, not return.
**Blocker:** need to check per-signal which are computable from the companyfacts cache. `EBM`
and `grcapx3y` almost certainly are. `IO_ShortInterest` needs short-interest data — check
whether the free sources cover it.
**Precedent:** the last two batches of this kind (seasonal momentum, accounting change) both
failed 10/10 and 0/4. Expect the same and run them anyway; that is what a pre-registered
screen is for.

### A2. Fix breadth destruction in the existing books
**Status:** measured in Step 245, never acted on.
**The number:** the equity books carry 61-71% persistence between quarterly rebalances and 5-7
effective independent names out of 10-28 held. Nominal breadth 40-114 per year collapses to
**8.5**.
**Why it matters:** the breadth term is squared-rooted in `IR = IC x sqrt(BR)`, so this is the
cheapest available lever on risk-adjusted return, and it needs no new signal or data.
**Ceiling:** realistically 40-60 bets a year, still short of the 91 an IR of 0.25 needs. Worth
doing, will not be sufficient alone.

### A3. Formal regime model
**Status:** `UPGRADE_CANDIDATES_V1` item 7, never attempted. Note
`scripts/run_formal_markov_regime_scaling_v1.py` exists — check what it already did before
starting.
**Why it matters:** every regime rule in this project is an ad hoc threshold. A state model is
estimated rather than chosen, which removes a large unrecorded search.
**Ceiling:** it is a construction change, not a new signal. Step 245's cap applies.

### A4. FINRA short interest and daily short-sale volume *(new 2026-09-06)*
**Status:** new. Closes A1's open question -- "check whether the free sources cover it" for
`IO_ShortInterest`. They do. FINRA publishes consolidated short interest twice monthly and
daily short-sale volume files, both free and both authoritative rather than a mirror.
**Why it matters:** short positioning is a *positioning* channel, not a transform of price or
of reported numbers, which is the same orthogonality argument that puts S1 and S2 at the top.
**Design caveat:** short interest and short-sale volume are different signals with different
mechanisms. Declare which one, and one horizon, before testing -- do not test both and pick.

### A5. Analyst estimate-revision breadth, aggregate only *(new 2026-09-06)*
**Status:** new, coverage unverified.
**Distinct from P2**, which is blocked because it needs analyst *identity* to build a graph.
Revision direction and breadth are aggregates and may be obtainable on a free tier.
**Before it can be ranked properly:** thirty minutes establishing whether any free source gives
a point-in-time revision series. If not, it moves to the paid queue next to P2.

### A6. Cross-sectional residual work in a second market *(new 2026-09-06)*
**This corrects a likely misreading of Step 246, and the correction matters.** Step 246
measured 35 multi-asset ETFs at 4.16 effective assets and international equity at **1.27**, and
concluded international is near-redundant with US equity at weekly frequency. That is correct
and it refutes international *index* diversification. It does **not** refute international
*cross-sectional* work, because those are different quantities: a market-neutral cross-sectional
book in Indonesia nets out the country factor, and its residual can be near-orthogonal to a US
cross-sectional residual even when the two indices correlate 0.8. **Only asset correlation was
measured; residual correlation was not.**
**Data:** already on disk -- IDX80/LQ45/IDX30 point-in-time membership, fundamentals, extended
prices, and a written protocol in `docs/INDONESIA_EQUITY_RESEARCH_V1.md`.
**Depends on S4.** This means nothing while every book here is long-only.

## B tier

### B1. Volatility risk premium, reading first
**Status:** `UPGRADE_CANDIDATES_V1` item 3, Tier 3, "needs Hull read properly before".
**Why it is not higher:** selling option premium is selling insurance. Negatively skewed --
many small wins and an occasional catastrophic loss -- which is the wrong risk shape for an
account that has never traded. It also needs options data that is not free at usable quality,
which puts the implementation in the paid queue.
**What is free now:** reading Hull properly and writing the design down. Do that before
spending anything.

### B2. Audit the remaining Tiingo inventory
**Status:** Step 166 noted **446 candidates of which 315 are not yet audited**, plus seven
rejected legacy cases scheduled for one controlled recheck.
**Why it matters:** housekeeping that raises panel coverage, not a strategy.

### B3. The Lopez de Prado methods not yet applied here *(new 2026-09-06)*
CLAUDE.md section 3 names purged/embargoed walk-forward CV, deflated Sharpe, CSCV and block
bootstrap as already implemented unusually well, and asks what from that body of work is still
unused. The unused list is **fractional differentiation** (stationarity without full memory
loss), **MDA/MDI feature importance**, and **structural-break tests**.
**Why it is B and not A:** none of the three generates a signal. All three are diagnostics that
would say which existing features are doing work and whether a series changed regime. Useful,
bounded, and they do not touch the breadth ceiling.
*Recorded from general knowledge of AFML, not from a read of the text this session.*

## C tier -- parked, recorded so it is not re-proposed

### C1. Opening Range Breakout, single-stock version
The index and sector ETF version is **rejected** (Step 209, cost hurdle, and five-minute bars
made it worse not better). The single-stock version screens small caps on gaps and relative
volume and needs point-in-time intraday data across a broad stock universe. **No free source
supplies that at usable history length.** Source-blocked in the same sense as S1 was.

### C2. Stochastic calculus / Brownian motion strategies
Not a strategy family. It is the mathematics for *pricing and hedging* derivatives -- Black-
Scholes, Heston, the Shreve volumes. It does not generate equity alpha. Learn it if the options
thread ever opens; do not expect a signal from it.

### C3. VIX mean reversion
VIX is not tradeable. The tradeable expressions are VIX futures and VXX/UVXY, which carry
severe roll decay -- and Step 247 established we cannot get clean futures roll data for free.
Underneath, this is B1 wearing a costume.

---

# PAID QUEUE -- nothing here starts without the owner confirming the spend

## P1. Properly roll-adjusted futures data
**Cost:** Norgate roughly $300-500/year; Databento usage-priced; CME DataMine official.
**What it unblocks:** Step 247 measured a futures universe at **13.2 effective independent
assets and a projected 155 bets a year**, the only universe examined that clears the 91 an IR
of 0.25 requires. Step 248 then could not tell whether futures trend's negative IC was mean
reversion or roll contamination, and Step 249 showed a magnitude-based repair cannot fix it
because weekly roll gaps are not outliers. **Only contract-level data records roll timing.**
**Why it is first in this queue:** it is the single largest measured breadth opportunity in the
project and the blocker is money rather than merit.

## P2. IBES analyst detail file
**What it unblocks two things:**
- **Shared analyst coverage** (Step 205). Ali & Hirshleifer, NBER 25201, read directly rather
  than recalled: a value-weighted long-short earns **1.19% a month at t = 6.71**, equal-weighted
  **2.10% at t = 11.88**, across 98% of market cap, and only 39% of links share an industry so
  it is not a repackaged industry bet. **The strongest effect this project has ever identified.**
- **`ConsRecomm`**, the single most orthogonal anomaly in the OSAP screen.

**Blocker:** links require analyst *identity* -- which analyst covers which stock. Finnhub's
free tier gives aggregate recommendation counts only, which cannot build the graph. Checked
2026-09-06.
**Note:** Step 205 recorded this as "blocked on data rather than on merit, which makes it a
purchasing decision rather than a research one." It still is.

## P3. Options data
Needed to implement B1. Not worth pricing until B1's reading is done.

---

# CLOSED -- do not re-propose

| item | verdict | where |
|---|---|---|
| Opening Range Breakout, index/ETF | Rejected on the cost hurdle; five-minute bars made it worse | Step 209 |
| Short-term reversal | Bid-ask bounce; 0 of 9 survive skip-1; total loss at 100bps | Step 250 |
| The 22-signal literature screen | All eleven price signals negative; the sample rewarded volatility, not selection | Steps 189, 192 |
| Low asset growth | Real spread, unusable portfolio; declined to freeze | Step 193 |
| Seasonal momentum | 0 of 6 usable; the two uncorrelated configs lost 14%/yr with 93% drawdowns | Step 217 |
| Accounting change family | 0 of 4 clear Bonferroni; best t = 2.08 | Step 218 |
| Multi-asset ETF universe | 4.16 effective assets from 35; refuted on its own premise | Step 246 |
| Futures trend IC | Every significant result negative; inconclusive, blocked on roll repair | Steps 248, 249 |
| Futures roll repair by outlier detection | Weekly roll gaps are not outliers; 2 of 9 proxies improved | Step 249 |
| Risk-budgeted sizing | Passed on one book, reversed on two others | Step 244 |
| Meta-labeling | Failed its precondition | Step 201 |
| Supply-chain graph | Two of forty issuers had a named customer edge above 10% | Steps 202-204 |
| Form 4 insider clusters | Retained as a diversifier only, not a leader | Step 125 |
| Online performance chasing | Rejected across all saved strategies | Step 203 |
| Cross-asset crisis trend | Rejected as a fixed blend | Step 205 |
| Daily OHLCV alpha zoo | Rejected as a replacement | Step 200 |
| Breadth accounting | Done. IR ceiling below 0.1; the finding that reframed everything after it | Step 245 |
| Eight untried price signals -- coskewness, idiosyncratic skewness, trend consistency, sector dispersion, vol-of-vol, downside beta, residual reversal skip-1, industry return of big firms | **0 of 8 clear** Bonferroni 0.00625 in either the 2011-2019 selection window or the 2020-2026 evaluation window. Best is trend consistency at evaluate IC +0.0212, t=1.72, p=0.088. Two (coskewness, idiosyncratic skewness) are nominally significant with the **wrong sign**. | `evidence/untried_price_signals_v1/` |
| World Cup Trading Championship as external evidence that better strategies exist | **Tested against their own published record.** 42 flagship futures winners 1984-2025, **33 distinct names**; solving N(1-(1-1/N)^42)=33 gives **N~=85**, so the entire repeat-winner structure is what a stable field of ~85 identical traders produces by chance. Median winner **+252%**, range +53% to **+11,376%** -- a variance distribution, not a skill distribution. Field size is not published, so skill cannot be separated from entry volume, and their own footer permits multiple accounts per entrant. **Does not establish that better strategies exist.** The one thing it does corroborate is that the field trades futures and FX with leverage and both directions -- which is P1 and S4, already here. | Step 256 |
| PEAD / SUE standalone (was S3) | **Closed underpowered, not refuted.** The only horizon that clears (26w, t=2.94) gets its significance from overlapping windows; corrected for half-overlap it is p=0.087, and the non-overlapping 13w horizon gives p=0.115. Separately worth remembering: the book Sharpes 1.04 after 50bps and correlates **0.002 / 0.008** with existing strategies, the lowest ever measured here. That is a reason to extend the sample, not to believe. **Revival attempted 2026-09-06; the remedy was tried and it did not work.** The panel was rebuilt to **58 decisions**, 2012-04-01 to 2026-07-01, 131,169 rows over 6,098 roster issuers. Across all 58 the IC is **+0.0053 at 13w (t=0.71)** and **+0.0077 at 26w (overlap-adjusted t=0.71)** -- nothing. It reaches +0.0330 at 26w (overlap-adjusted t=2.35, p=0.044) only once decisions are restricted to companyfacts coverage >=0.8, which leaves **20 decisions** and, because coverage runs 54.3% before 2016 against 91.0% from 2020, is very nearly just the 2016-2026 window. The added decisions carry a **36.6pp survivorship coverage gap** and no signal. Eight configurations against a Bonferroni threshold of 0.00625: **none clear.** The sample-extension remedy is now spent; do not propose it a third time. | Steps 253, 256 |

---

*Last updated 2026-09-06. Update this file in the same commit as the work it describes.*
