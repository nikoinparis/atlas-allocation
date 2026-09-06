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

### S1. SEC 10-K language change — extend the corpus to 2011  *(reduced scope)*
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

## A tier

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

### A4. 13D and 13G activist and large-stake filings  *(new 2026-09-06)*
**Status:** never attempted. The best remaining free idea in this file.
**Why it is different from everything closed so far:** every family tested to date is a
*continuous* cross-sectional score -- a number every stock has every week. A 13D is a **discrete
event**: someone crossed 5% ownership with intent to influence. Events and scores fail for
different reasons, and this project has never tested an event-driven signal that was not
earnings.
**Data:** SEC EDGAR, free, full history. Forms SC 13D, SC 13D/A, SC 13G. Filing date is the
point-in-time anchor and the deadline is short, so the lag problem that may have killed A0 is
much smaller here.
**Design note before starting:** the sample is small -- a few thousand 13Ds a year across the
whole market -- so this is an event study with cohort dates, not a weekly cross-sectional IC.
Different statistics, and the registry has to say so up front.

### A5. FINRA short interest  *(new 2026-09-06)*
**Status:** never attempted. `IO_ShortInterest` sat in the OSAP screen's most-orthogonal band at
0.0033 against every existing strategy, and was named in A1 without a data source. FINRA
publishes short interest free, twice monthly, per security.
**Why it ranks below A4:** it is another continuous cross-sectional score, which is the shape
that has failed twelve times running. But it is genuinely orthogonal by measurement and the data
is free and complete.

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
| **13D/13G activist events (was A4)** | **Closed.** 38,849 subject events, 2013-2026, sector-matched abnormal returns bootstrapped with clustering by filing month. Nothing clears for either form in either window. The strongest reading, 13D at 13 weeks recently, is **-2.13%** -- the wrong sign against a declared positive. The 13G control is flat at 20,000 events, so the absence is real rather than a broken pipeline. Caught mid-run: EDGAR relabelled `SC 13D` to `SCHEDULE 13D` in 2025 and the first parse silently lost two years. | Step 260 |
| **13F institutional linkage (was A0)** | **Closed.** 110M holding rows, 73.4% identity match, manager cap declared before any signal. Every IC negative against a declared positive sign, none significant, at three caps and two horizons, and the sector-controlled column is equally flat so it is an absence rather than a sector effect. Mild evidence against buying P2. | Step 258 |
| **10-K language change (was S1)** | **Inconclusive by construction, scope reduced.** Corpus of 9,754 filings acquired and parsed and kept. Cosine on word counts is degenerate (IQR 0.0020); jaccard is the usable measure. 10-Ks are annual and cluster in Q1, so eight years give nine cross-sections and the smallest establishable IC is ~0.110. **Only worth reviving as: extend the corpus to 2011, declare ONE measure and ONE horizon, judge on sub-period replication rather than a p-value.** | Step 255 |
| **Earnings call transcripts (was S2)** | **Closed unstarted.** Audited: real, speaker-attributed, 2005-2026, but coverage is proportional to company size and age -- AAPL 84 transcripts, TXO zero. A cross-sectional signal on a source whose coverage tracks size is a selection problem before it is a signal. S1 showed the text channel cannot be established on annual data anyway. | Step 254 |
| **Eight price signal families (coskewness, idiosyncratic skewness, trend consistency, sector dispersion, vol-of-vol, downside beta, residual reversal, ind_ret_big)** | **Closed.** Selected on 2011-2019, evaluated on 2020-2026. Zero of eight clear Bonferroni in either window. ind_ret_big, the most orthogonal of them at 0.009, measures -0.0007 at t=-0.07. | Step 257 |
| Eight untried price signals -- coskewness, idiosyncratic skewness, trend consistency, sector dispersion, vol-of-vol, downside beta, residual reversal skip-1, industry return of big firms | **0 of 8 clear** Bonferroni 0.00625 in either the 2011-2019 selection window or the 2020-2026 evaluation window. Best is trend consistency at evaluate IC +0.0212, t=1.72, p=0.088. Two (coskewness, idiosyncratic skewness) are nominally significant with the **wrong sign**. | `evidence/untried_price_signals_v1/` |
| World Cup Trading Championship as external evidence that better strategies exist | **Tested against their own published record.** 42 flagship futures winners 1984-2025, **33 distinct names**; solving N(1-(1-1/N)^42)=33 gives **N~=85**, so the entire repeat-winner structure is what a stable field of ~85 identical traders produces by chance. Median winner **+252%**, range +53% to **+11,376%** -- a variance distribution, not a skill distribution. Field size is not published, so skill cannot be separated from entry volume, and their own footer permits multiple accounts per entrant. **Does not establish that better strategies exist.** The one thing it does corroborate is that the field trades futures and FX with leverage and both directions -- which is P1 and S4, already here. | Step 256 |
| PEAD / SUE standalone (was S3) — **REOPENED as a forward clock, Step 259.** The recent-window claim cannot be settled from history, so it is being settled forward: `sue_quarterly_forward_v1`, breadth 50, quarterly, first decision 2026-09-11, reading fixed in advance in both directions. Historical detail below. | **Closed underpowered, not refuted.** The only horizon that clears (26w, t=2.94) gets its significance from overlapping windows; corrected for half-overlap it is p=0.087, and the non-overlapping 13w horizon gives p=0.115. Separately worth remembering: the book Sharpes 1.04 after 50bps and correlates **0.002 / 0.008** with existing strategies, the lowest ever measured here. That is a reason to extend the sample, not to believe. **Revival attempted 2026-09-06; the remedy was tried and it did not work.** The panel was rebuilt to **58 decisions**, 2012-04-01 to 2026-07-01, 131,169 rows over 6,098 roster issuers. Across all 58 the IC is **+0.0053 at 13w (t=0.71)** and **+0.0077 at 26w (overlap-adjusted t=0.71)** -- nothing. It reaches +0.0330 at 26w (overlap-adjusted t=2.35, p=0.044) only once decisions are restricted to companyfacts coverage >=0.8, which leaves **20 decisions** and, because coverage runs 54.3% before 2016 against 91.0% from 2020, is very nearly just the 2016-2026 window. The added decisions carry a **36.6pp survivorship coverage gap** and no signal. Eight configurations against a Bonferroni threshold of 0.00625: **none clear.** The sample-extension remedy is now spent; do not propose it a third time. | Steps 253, 256 |

---

*Last updated 2026-09-06. Update this file in the same commit as the work it describes.*
