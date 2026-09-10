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

## Standing decision, 2026-09-07: the search is paused, the clocks are the work

Fourteen signal families are closed. Three domains have been measured and every one
collapses to a handful of effective bets — multi-asset ETFs 4.16 of 35, crypto 3.09 of 20,
the SEC equity books 5-7 of 10-28. And Steps 287, 289 and 290 tested **every strategy on
the dashboard** on a period it was not selected on: **nought of six survive**, nothing
retains more than 11% of its in-sample edge, and three of six have the wrong sign.

Adding a fifteenth candidate has a poor prior. What has never once been tried in 290 steps
is **letting a clock finish**. Six start on 2026-09-11 and not one strategy here has a
single week of forward evidence.

**So the queue below is paused rather than closed.** Nothing in it is wrong; it is simply
not the binding constraint. Re-open it when there is forward evidence to compare a new
candidate against, or if a clock produces a result that points somewhere specific.

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



### S2. A third independent return source — anything that is not price and not a filing ratio *(new 2026-09-06)*
**Status:** the standing top priority, and deliberately not a specific idea.
**Why it is S and everything else is not:** Step 275 took the effective number of independent
bets from about 1.15 to about 2 by adding valuation next to growth, and that single step did
more for risk-adjusted return than 270 steps of retuning. `IR ≈ IC × √BR` says a third genuinely
independent source is worth another ~22% on IR *at unchanged IC* — no better signal required.
Nothing else in this file has that property.
**The screen to apply to any candidate before building it, both halves required:** correlate its
return stream against the valuation book and the residual composite -- below 0.3 against both --
**and** check it stands up alone at something near a 1.0 Sharpe. Step 277 established the second
half the hard way: XLE clears the correlation gate, raises effective bets from 2.00 to 2.88, and
adds 0.021 of Sharpe, because its own Sharpe is 0.568. `IR = IC x sqrt(BR)` is a product, and
breadth bought with an unskilled leg pays for itself in lost IC.
**Screening what is already on disk is finished** (Step 277): 691 saved paths, one distinct
object clears both gates, and it is a sector ETF.
**What is already known not to work, now in two directions:** continuous cross-sectional scores
over US equity have failed twelve times running, AND adding a different *asset class* does not
help, because every liquid domain measured here collapses to a handful of effective bets —
multi-asset ETFs 4.16 of 35 (Step 246), crypto 3.09 of 20 (Step 285), SEC equity books 5-7 of
10-28 (Step 245). **A third source has to be a different information channel with skill of its
own, not a different pile of correlated prices.** That rules out the remaining asset-class
ideas and leaves the information-channel ones.

### S3. Regenerate the valuation score panel each quarter *(new 2026-09-06)*
**Status:** operational, not research, and it will silently break the clock if missed.
The panel ends at 2026-04-01, so the forward book is 163 days stale at its first decision and
will never rebalance until `run_sec_survivorship_valuation_discovery_v1.py` is re-run. Fifty-two
weeks of a frozen April book is not the quarterly strategy that was backtested.
**Check:** `score_block_age_days` in the decision log. Above ~120, the refresh was missed.

### S4. Measure the leg correlation forward, and stop the blend if it fails *(new 2026-09-06)*
**Status:** running from 2026-09-11 as `valuation_growth_5050_blend_forward_v1`.
The entire Step 275 result rests on one number measured on the same searched window as
everything else. `status.json` flags `correlation_refuted` above 0.5. **This is the first thing
to read when the clock has enough weeks — before any Sharpe.**


## A tier


### A8. EU short-selling registers *(new 2026-09-10, owner-proposed)*
**Status:** never attempted. Free, daily, from ESMA and national regulators.
**Why it is genuinely better than what closed in Step 263:** FINRA short interest is an
anonymous aggregate. The EU registers name the **holder** and the **position size** for every
net short above 0.5% of issued capital. That is the identity dimension 13F lacked for shorts,
and it is a positioning channel rather than a price transform.
**The blocker, and it is large:** our universe is US tech and energy. Overlap with EU issuers
is approximately zero. Using this means building a European universe from scratch — point-in-
time membership, price panel, survivorship treatment. That is the biggest infrastructure job
on this list, larger than the FSDS acquisition was.
**Rank:** the signal is plausible; the cost is a whole new market.

### A9. CFTC Commitments of Traders *(new 2026-09-10, owner-proposed)*
**Status:** never attempted. Free, weekly, published Fridays. Commercial vs large-speculator
vs small-trader positioning in futures.
**Why it is real data:** it is genuine positioning, not a price transform, and it is one of the
few free datasets that is neither a price nor a filing ratio.
**The blocker:** it describes **futures**, and this project's futures work is closed — Step 248
found every significant trend IC negative, Step 249 found the roll repair did not work. There
is no futures book to express a COT signal in. Using it instead as a macro-state conditioner
for the equity books runs straight into Step 271, which found conditioning destroys value even
when the state variable is correctly identified.
**Rank:** real orthogonal data with no vehicle to trade it in. Revisit only if a futures book
ever exists.

### A10. Form ADV Schedule D, Section 7.B.(1) *(new 2026-09-10, owner-proposed)*
**Status:** never attempted. Free, from SEC IAPD.
**What it actually contains** — per private fund: gross asset value, fund type, and the fund's
service providers (auditor, prime broker, custodian, administrator, marketer). A
service-provider network plus adviser AUM. *The owner referenced item "7.8.1"; that
sub-numbering could not be verified against SEC's own Form ADV documentation on 2026-09-10, so
this entry describes Section 7.B.(1) generally and the specific item should be pinned down
before any work starts.*
**The blocker:** it is about **advisers**, not securities. Getting from an adviser to a
tradable signal requires 13F to map holdings, and 13F is closed — Step 258, every IC negative
against a declared positive at three caps and two horizons. Filing is annual, so the frequency
is wrong for anything but a slow flows proxy.
**Rank:** low for direct alpha. The one angle that is not obviously dead is adviser AUM change
as a capital-flows signal, which is still bounded by the 13F linkage failure.

### A11. Schedule 13D — ALREADY CLOSED, do not re-propose
Closed in Step 260. 38,849 subject events 2013-2026, sector-matched abnormal returns
bootstrapped with clustering by filing month. Nothing cleared for either form in either
window; the strongest reading was 13D at 13 weeks recently at **-2.13%**, the wrong sign
against a declared positive. The 13G control was flat at 20,000 events, so the absence is real
rather than a broken pipeline.

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
| **Triple-barrier labelling (was A9)** | **Closed.** Zero of four barrier configurations beat the plain forward return; the widest is a tie, and 9-43% of observations touch no barrier and are labelled zero. Also weakens the Step 201 hypothesis that meta-labelling failed for want of a barrier target underneath it. | Step 265 |
| **Feature importance MDA/MDI (was A7)** | **Done.** Model has modest held-out skill (+0.0337, positive in 86% of folds). Only residual momentum degrades it when shuffled (+0.0439, t=1.99). **Trend quality is 29.9% of MDI and -0.0059 of MDA** — the forest leans on it and it carries nothing. The feature that matters is the one Step 234 found picks twenty names from a tie of fifty-nine by lowest CIK. | Step 264 |
| **Short interest (was A5)** | **First signal to survive both windows, and still not worth holding.** IC -0.0312 (t=-4.80) select, -0.0435 (t=-5.30) evaluate. But a long-only book returns 12.54% at 50bps against a market at 13.15%, with a -36.5% drawdown, and correlates +0.873 with the market. Near-zero against our own strategies, which is the breadth property we want. **Open as an exclusion filter, closed as a strategy.** | Step 263 |
| **Fractional differencing of features (was A11)** | **Closed.** Order-0.3 differencing keeps 0.856 of the price level's memory against 0.050 for plain returns, but only 1 of 8 signal configurations improves and several flip sign. The memory it preserves is not the memory these signals used. Step 265's finding stands as a property of the series, not a usable improvement. | Step 268 |
| **Short-interest filter, pre-registered (was S4)** | **Closed as noise.** Nothing clears Bonferroni under a *paired* bootstrap; the best configuration gives p=0.0136 on the full window and 0.132/0.182 in the sub-periods. Step 268's apparent improvement came from comparing two nearly identical series without pairing. | Step 270 |
| **Selection-paying sizing (option 2)** | **Rejected, with a finding kept.** Eight of eight leveraged configurations improve Sharpe and reduce drawdown on the full window — but sizing helps **+0.14 to +0.23 Sharpe before April 2025** and hurts **-0.20 to -0.38 after**, unanimously. The full-window gain is an average of a real benefit and a real cost. **Kept:** the index is a timing tool that works in ordinary conditions and is actively wrong in a melt-up, which is the first description of the two periods this thread has produced that the data supports. | Step 270 |
| **Selection-paying classifier (A13)** | **Closed as not tradeable, but the relationship is real.** An index of whether eight generic characteristics predict returns, over 762 weeks. It does **not** shift at 2025-04-04 (probability 0.775 before, 0.648 after), so April 2025 was not selection starting to pay — this closes the regime thread. But all four strategies earn 20-30pp more when the index is high, the first conditioning variable here with the *correct* sign. Conditioning still destroys value because the low state still returns 23-25%: the difference is degree, not sign, so the only expression is sizing up in the good state, which is leverage. | Step 269 |
| **Pre-break strategy search (was A12)** | **Closed, and it weakens the regime thread.** 710 saved paths compared either side of 2025-04-04. A two-state story predicts a *negative* rank correlation between pre- and post-break performance; measured **+0.181 (p=0.0000)** — weakly positive. And **only 21.3% of everything this project has ever built beat the market before April 2025.** The break is not "a different strategy suited the earlier regime" — nothing worked, then four correlated things worked at once. | Step 267 |
| **Market-state classifier (was A10)** | **Closed as not actionable.** States from market observables (dispersion, correlation, breadth, volatility), fit 2011-2020, never refit, labelled causally. **No observable shows a persistent state change at 2025-04-04** — three spike near it and all four sit *lower* after than before, so a spike that reverts is not a transition. Pre-declared stop condition triggered; state-conditioned selection not authorised. All four strategies also do *worse* in the state these observables identify, so these are not the states that explain the break. | Step 266 |
| **Structural break tests (was A6)** | **Done, and it changed the reading of everything else.** All four strategies select the identical break week, 2025-04-04, scanning independently over 188-195 weeks. Mean return goes from 8-13% before to 80-105% after, betas near zero on both sides so it is not market exposure, and the market itself shows no break there. None clears Bonferroni 0.01 (p 0.022-0.038) so it is suggestive rather than established -- but four independent strategies do not pick the same week by chance, and it is the cleanest evidence yet that they are one bet. **Consequence: future tests should split at 2025-04-04, and no test in this project has ever asked what the strategies look like with those 75 weeks removed.** | Step 261 |
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
| Valuation family revival | REVIVED. Widening to breadth 20 fixes the concentration failure; near-zero correlation to all four incumbents; 9 of 9 blends beat both components on Sharpe. On a clock from 2026-09-11. | 274, 275 |
| **Breadth repair by construction (was A2)** | **Closed as noise.** Five constructions on two books attacking 61-71% persistence and 5-7 effective names. One of eight raised breadth and Sharpe together (de-persistence on cash conversion, bets 8.6->15.6, Sharpe 0.878->1.007) and the same intervention *lowered* Sharpe on valuation. Paired block bootstrap p=0.632 and p=0.426 against a Bonferroni bar of 0.0063; the two books move opposite directions by -2.07% and +2.05%. **Kept:** sector caps *reduce* effective independent names on both books (7.39->4.30, 6.39->3.99), so these books are not concentrated because they are sector-concentrated -- the premise of the intervention is backwards. | Step 279 |
| **Valuation panel quarterly refresh (was S3)** | **Done and defect fixed.** The builder loaded a stale checkpoint, passed ten validation checks, and re-emitted the same fourteen quarters. Guarded on membership vintage; panel now runs to 2026-07-01. | Step 278 |
| **FINRA daily short-sale volume (was S2a)** | **Closed on all three gates.** Pre-registered before download; 922 trading days, 487 issuers x 192 weeks. IC **+0.00383** (t=0.82, p=0.396) against a declared NEGATIVE sign — refuted. Declared book -28.07% CAGR at 50bps and -14.36% at 0bps, so wrong-signed rather than cost-killed. The reverse side returns 25.86% at Sharpe 1.178 and **does not rescue it**: the sign was declared, the IC behind it is insignificant, and it correlates **+0.886 with an equal weighting of its own universe** — market beta with a tilt. Distinct from Step 263's short *interest*. | Step 282 |
| **Crypto as a third asset class (new 2026-09-07)** | **Closed on both gates, both configurations.** Equal-weight 20 coins: Sharpe 0.238, corr +0.332 to valuation. Momentum top-5: Sharpe 0.374, corr +0.300. Momentum doubles return and does not move Sharpe because it buys it with vol (71.9% vs 62.3%). **Effective independent coins 3.09 of 20** — crypto's cross-section has no more breadth than the multi-asset ETF universe did (4.16 of 35). Test was survivorship-biased *in crypto's favour* and still failed. | Step 285 |
| **Form 4 opportunistic insiders (was S2b)** | **Refuted on sign; the split itself untested.** 667,153 purchases, 10,579 issuers, 2011-2026 — 260x the 2,560 filings that rejected this in Steps 125-126. Opportunistic IC **-0.0188, t=-4.87, p=0.0005** against a declared POSITIVE sign, so refuted rather than flipped. Sharpe 0.485, correlation +0.711 to valuation: gates 1-3 fail. **Gate 4 was UNTESTABLE** — routine purchases reach a median of 13 issuers per 4-week window and never the 30 the IC needs, so CMP's actual claim was never tested. Size control: negative in all five price quintiles. **Reviving it needs the full market, not the survivorship-aware roster; the classification rate is the binding constraint.** | Step 286 |
| **Pairs trading, GGR rule verbatim (was S5)** | **Closed on gates 2 and 3, but gates 1 and 4 PASSED.** 3.9M candidate pairs, top 20 by minimum SSD, disjoint 52w formation / 26w trading. Loses money at **zero cost** (-0.30%, Sharpe -0.079), so costs did not kill it -- there was nothing there. **Worse than a 200-run random-pair placebo** (-0.555 vs -0.117 mean), so minimum-distance selection subtracts information rather than adding it. **Kept, and it matters:** this is the first structure here that is genuinely orthogonal (+0.030 / -0.044) and genuinely market-neutral (beta -0.009, R2 0.001), and it clears those *by construction* rather than by hoping. The structure is the right direction; the GGR rule is the wrong occupant of it. | Step 293 |
| **Long-short cash conversion (was A7)** | **Closed on gate 3, the hypothesis.** Same top-20 long leg as the frozen book, bottom-20 short, 100% gross. Out of sample the long-short earns 1.59% at Sharpe 0.157 against its own long-only twin's 16.65% and 0.705; in sample -4.57% against 19.97%. Market beta +0.007 and orthogonality both PASS, as Step 293 predicted they would by construction. **The finding that matters:** neutralising the market removed ~90% of the return, so cash conversion's +1.08pp out-of-sample excess — the one positive in Step 289's nought-of-six — was substantially beta, not selection. Leave-one-short-out clean across 112 names (worst -0.58pp). **Together with Step 293: the structure is sound and there is no signal here worth putting in it.** | Step 295 |
| **Cross-sectional skill screen (new 2026-09-10)** | **Nought of thirteen.** Every signal on disk measured three beta-neutral ways at a 13-week horizon. No signal clears Bonferroni 0.0038 (best p=0.108), and **monotonicity is within ±0.17 of zero for all thirteen** — none of them orders its deciles. Six show a positive IC alongside a *negative* decile spread, which is what noise looks like measured twice. Explains Step 245's transfer coefficient of -103, Step 289's nought-of-six, and Step 295's ninety-per-cent beta at once: the books never won on ranking ability. **Honest limit:** 13-14 in-sample decisions cannot detect an IC of 0.03; the monotonicity result carries the weight because it measures shape, not significance. | Step 296 |
| **Closed-family monotonicity audit (new 2026-09-10)** | **All fifteen closures stand.** Ten families rebuilt and measured; nought order their deciles, monotonicity within ±0.11 for every one. Two clear Bonferroni and neither survives: Form 4 is **93.3% zeros** so its p=0.0000 is a *presence* test, not the intensity question Step 286 declared and measured at -0.0086/t=-1.34; trend consistency has a positive IC with a **negative** decile spread, the same contradiction as Step 245's -103 transfer coefficient. **Kept:** the screen needed a density guard, added after it nearly reported a spurious result — a signal non-zero in under 50% of cells cannot be read on deciles. | Step 298 |
