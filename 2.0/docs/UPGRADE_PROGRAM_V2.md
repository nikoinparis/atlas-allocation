# Upgrade program V2 — where the return actually is

Written 2026-08-27, after reading the full record through Step 198 and running two
new probes (Steps 199 and 200).

## 1. The diagnosis

The engineering in this project is not the problem. Point-in-time discipline, frozen
configs, permutation nulls, hash-chained forward evidence and the willingness to
publish negative results are all better than most professional shops manage. Four
structural facts, all established by the project's own evidence, explain why that rigour
has not converted into a defensible return.

**The sample is too short and it is all one regime.** The stock price panel starts
2022-12-02: 143 to 195 weekly observations, no bear market, no rate shock, no credit
event. Step 191 records the volatility-tilt gate as binding on data availability rather
than construction, which is the honest description of a much larger problem. Nothing
selected on this window can be shown to survive a regime it has never seen.

**The search has saturated that sample.** 576 configurations in Batch 05, 288-experiment
batches in Batches 01 and 04, 2,924 nested ML fits in Batch 17, 22 literature signals in
Steps 189 and 192, 200 recorded steps. Step 199 prices that search: at a thousand assumed
trials no saved book clears a deflated Sharpe of 0.95, and at a hundred none does either.
The Micron-led growth book has an annualised Sharpe of 0.95 against a null threshold of
1.75 — it underperforms what pure search alone would be expected to produce.

**Effective breadth is stuck near one bet.** Measured at 1.15 in Batch 03 and never moved
since, because every candidate has been a re-weighting of the same momentum and
cash-conversion family. Step 188 showed the signals cannot separate the tails; Step 190
showed a randomly chosen twenty-name book beats a randomly chosen five-name book on median
return, fifth-percentile outcome and both loss probabilities at once. Selection is not
where the money is here.

**The headline returns are a draw, not an expectation.** Step 196 put the saved books at
the 98th to 100th percentile of size- and volatility-matched random portfolios and said
correctly that this is close to tautological on the selection window. Step 197's rehearsal
found four of six books below the 0.50 weekly percentile over the last six weeks of that
same window — the pattern the selection hypothesis predicts.

The corollary is uncomfortable and worth stating once. **More search on this panel cannot
produce a defensible result.** Raising the observed Sharpe on the window the search ran
over also raises the null it is deflated against. Only two things move a deflated Sharpe:
a longer or genuinely independent sample, and fewer effective trials. Neither is available
by tuning.

## 2. On the 200% target

The trailing figures of 92% to 156% are already 200%-class returns in a good year. The
open question is not how to raise them; it is whether any of them repeats. Nothing in the
record supports 200% as a repeatable expectation, and the two mechanisms that would produce
it retrospectively — extreme concentration and a high-volatility tilt — are the two the
project has already measured and found wanting (Steps 188, 189, 190, 191).

The honest high-return route is arithmetic rather than heroic: raise Sharpe by adding
genuinely independent bets, cap the drawdown so the book is survivable, and then apply
deliberate, priced leverage to a book that has earned it. A blend at Sharpe 2.0 run at 25%
volatility is a 50% expected return; the same blend at Sharpe 1.0 needs 50% volatility for
the same number and will not survive the path. Every item below is aimed at the Sharpe and
the drawdown, because those are the two terms leverage multiplies.

## 3. Tier 0 — the unlock everything else depends on

**0.1 Extend the price panel back to 2012.** This is the single highest-value action
available and most of it is already built. `data/sec_fsds_sub_cache/` holds 57 quarters of
SEC Financial Statement Data Sets covering 2012q1 through 2026q1, with real filed dates and
no restatement leakage. The fundamentals for a fourteen-year point-in-time panel are on
disk today. The only missing half is prices, and the Tiingo acquisition path
(`scripts/acquire_tiingo_delisted_probe_batch_v1.py`, free tier, 1,000 requests per day,
60+ years of history, delisted support) already exists with a working token and a
terminal-membership audit behind it. At roughly two requests per symbol, 3,253 symbols is
about seven days of unattended collection.

What that buys: 2015-16, 2018, 2020 and 2022 all enter the sample. The volatility-tilt
gate in Step 191 becomes satisfiable. Every signal killed in Steps 189 and 192 gets retested
against regimes that punish the opposite exposure. The deflated Sharpe threshold falls
because the sample is four times longer. Do this before anything in Tier 1 that touches
single stocks.

Backups and parallel paths, all cheap: Twelve Data (800 free calls/day, so about four days
for the universe), Financial Modeling Prep (explicit delisted-symbol endpoints), Stooq
(free bulk daily US archives, quality needs auditing), EODHD (about $20/month, which is
worth paying to remove a seven-day bottleneck from the critical path). Keep the existing
delisting and terminal-outcome machinery whatever the source: it is the part that makes the
panel survivorship-safe, and it is already correct.

**0.2 Use the 33-year ETF panel already on disk.** `data/vintages/…/prices.csv` holds daily
OHLCV for 35 ETFs — SPY from 1993, sectors from 1998, and the full cross-asset set from
2007 — covering bonds, credit, TIPS, gold, silver, oil, broad commodities, the dollar,
international, emerging, REITs and style. Step 186 used it once, as a cross-sectional sector
rotation, and correctly rejected that. It has never been used for anything else. It is the
only asset in this repository that contains 2000, 2008, 2020 and 2022.

## 4. Tier 1 — new alpha, ranked by expected value

**1.1 Cross-asset time-series momentum as an independent sleeve. Already probed; see Step
200.** Sharpe 0.92 over 2007-2026 across 4,832 days, against SPY's 0.62 and 60/40's 0.77.
+12.5% through the GFC against SPY's -44.9%. Weekly correlation to four of the five saved
books between -0.087 and +0.149. Adding it lifts effective independent bets from 2.48 to
3.08 — the first tested source that moves the constraint Batch 03 identified. It lags badly
in 2023-2026 (45.4% against SPY's 112.3%), which is what a defensive diversifier is supposed
to do and the reason it must not be judged on that window. Next: extend to the full 1993
start with a documented small-universe caveat, add a conditional volatility-target variant,
and freeze one point on the leverage grid *before* looking at the blend results.

**1.2 Rehabilitate the investment factor rather than discarding it.** Step 192 found low
asset growth the sole survivor of 22 literature signals; Step 193 declined to freeze it
because the long-only book lost to the equal-weight universe. The rejection reasoning is
sound for that window and probably wrong as a conclusion. Investment is the
highest-replicating category in Hou, Xue and Zhang (2020) at 94.7%, against 87.7% for
momentum and 75.4% for value, in a study where 65% of 452 anomalies fail even a t of 1.96.
Step 193 tested it in a 3.7-year window that Steps 189 and 191 independently established was
paying for exactly the volatile, high-beta names low asset growth selects against. Retest it
sector-neutral, as a *veto screen* on an existing book rather than a standalone one, and
over 2012-2026 once Tier 0.1 lands.

**1.3 Lazy Prices — year-over-year textual change in 10-K and 10-Q filings.** Cohen, Malloy
and Nguyen (Journal of Finance, 2020). Firms that quietly change their filing language
underperform, with the drift accruing over 6 to 18 months and no announcement-day reaction.
Three properties make it unusually well suited here: the data is free from EDGAR and the
filing index is already cached; it is orthogonal by construction to both price signals and
XBRL fundamentals, which is exactly what a breadth of 1.15 needs; and a 6-to-18-month drift
means low turnover, so the 50 bps cost assumption barely bites. Roughly 3,000 issuers times
four filings a year times four years is about 48,000 documents — a large but ordinary
download.

**1.4 Short interest and days-to-cover from FINRA.** Free, twice monthly, published 7-10
business days after settlement so the availability lag is documentable. Days-to-cover is a
stronger predictor of poor returns than the raw short ratio. This project cannot short, but
a long-only book uses it the way it should be used anyway: as an exclusion screen that
removes the worst names rather than a ranking that buys the best. Genuinely orthogonal to
everything currently in the panel.

**1.5 PEAD, but the modern version.** Classic one-quarter SUE has decayed — a t of 2.18 on
all stocks through December 2024, falling to 1.43 excluding microcaps. The 2025 literature
revives it by extracting information from *multiple* quarters of SUE rather than the last
one, and text-based surprise measures generate drift larger than classic PEAD in exactly the
recent years where classic PEAD is near zero. The companyfacts cache and filed dates needed
for both are already on disk.

**1.6 Free SEC sources never tested here:** fails-to-deliver, 13D/13G activist filings,
buyback announcements in 8-Ks, and 13F institutional-ownership changes. All free, all
point-in-time, none currently in the panel. Lower prior than 1.3 and 1.4 but nearly free to
add once a filing pipeline exists.

**1.7 Seasonality.** Turn-of-month, factor seasonality and the documented seasonal pattern
in SEC filing volume (17% higher November-April than May-October, 2004-2023). Cheap,
orthogonal to everything else, and testable on the ETF panel over 33 years today with no new
data at all.

## 5. Tier 2 — make the evidence survive contact with reality

**2.1 Deflated Sharpe as a standing gate. Done for the saved books in Step 199; make it
mandatory.** Every future candidate reports its DSR against a documented trial count. This
is the gate that would have caught the Micron book before it reached a dashboard.

**2.2 Count the trials.** The project cannot currently state N. A simple append-only trial
ledger — one row per configuration evaluated, written at evaluation time — makes every
multiple-testing correction from here on honest instead of estimated.

**2.3 Combinatorial purged cross-validation** in place of single-path backtests. CPCV
generates many train/test paths with purging and embargo, producing a *distribution* of
backtest outcomes rather than one number, and it feeds the probability of backtest
overfitting directly. The existing embargo machinery in `ml_protocol.py` is most of the
work already.

**2.4 Bag the strategies instead of selecting one.** The single most effective structural
defence against the selection bias diagnosed in Step 196: hold the equal-weight average of
the top *k* candidates rather than the best one. It cannot be overfit by choosing a winner
because it does not choose. Step 190's breadth result is the same argument one level down.

**2.5 Protect the forward registry.** `config/forward_prediction_registry_v1.json` and the
September 4 pre-registration are the most valuable objects in this repository and the only
untouched evidence the project owns. Do not edit the thresholds, do not add strategies to it
after the fact, and do not let a Tier 1 result tempt a revision. Everything above is designed
to be ready *for* that clock, not to pre-empt it.

## 6. Tier 3 — construction and risk, where the reliable gains are

**3.1 Promote the drawdown-control overlay.** Step 198 already found it: halving exposure
below 8% from the running peak moved the maximum drawdown from -20.3% to -16.1% and the
worst rolling year from -5.5% to -0.5%, for 1.62 points of annual return and negligible
turnover. It was the only rule tested with a higher Sharpe than the baseline. Make it a
standing overlay on every candidate rather than a finding in a report.

**3.2 Conditional volatility targeting** rather than unconditional: scale only when realised
volatility is high, which the literature shows cuts drawdowns and tail risk across major
equity markets and the momentum factor with materially lower turnover and leverage than
plain volatility targeting.

**3.3 Regime-condition the exposure using data already on disk.**
`data/regime_vintages/…/normalized_v2/` holds VIX, VIX3M, VIX6M and term-structure slope back
to 2005, plus NFCI, high-yield OAS, the 10y-2y spread, fed funds and the dollar index. Paired
with the ETF panel that is a 2005-2026 regime overlay testable through 2008 — the bear-market
evidence Step 191's gate demands, obtainable today without acquiring anything.

**3.4 Integrated rather than mixed multi-factor construction.** The project has always mixed:
build sleeves, then allocate across them. The evidence favours integrating — combine signals
into one composite score, then build one book from it. Related and directly relevant to Step
193: the correct benchmark for a long-only factor book is *long minus market*, not top decile
minus bottom decile, and the long legs diversify better than the short legs (average
correlation -0.04 across long legs against +0.31 across short legs).

**3.5 Hold a breadth floor of at least twenty names.** Step 190 proved it on this exact
universe. The five-name growth book is strictly dominated by breadth it could have had for
free.

**3.6 Price leverage honestly if it is used at all.** Interactive Brokers Pro is the cheapest
mainstream margin lender at roughly 4.6%-5.5% depending on loan size; most retail tiers are
above 10%. Any levered variant should carry the real rate, a margin-call path, and a stated
maximum drawdown before it is compared with anything unlevered. Leverage is the legitimate
return lever, but only on a book that has already earned a low drawdown.

## 7. Tier 4 — tooling, honestly assessed

**NautilusTrader** is a production execution engine: Rust core, Python 3.12-3.14 bindings,
nanosecond event-driven simulation, venue fee and slippage models, and research-to-live
parity. It is genuinely excellent at what it does, and what it does is *execution*, not
research. It will not find alpha, and the current bottleneck is alpha and data, not fill
modelling. The registry's existing verdict — execution sandbox candidate, LGPL-3.0, adopt at
the paper-execution boundary — is correct and should not change until there is a candidate
worth executing. Adopting it now would spend weeks of integration on the one part of this
project that is not broken.

**OpenBB** is a reasonable data-normalisation layer but AGPL-3.0, which is viral and matters
if any of this is ever distributed. The existing conditional verdict stands.

**Research loop speed.** The panel is small enough that pandas is fine, but DuckDB over the
Parquet/CSV vintages would make the 2012-2026 panel queries substantially faster once Tier
0.1 quadruples the data.

## 8. Suggested order

1. Start the Tiingo backfill running today. It is seven unattended days on the critical path
   of almost everything else (0.1).
2. While it runs, work the ETF panel, which needs no new data: extend the trend probe to
   1993, add the regime overlay from the 2005+ VIX and macro vintages, and test seasonality
   (1.1, 3.3, 1.7).
3. Build the trial ledger and make deflated Sharpe a gate before any new candidate is
   evaluated, so the new work is counted from the start (2.1, 2.2).
4. When the panel lands, retest low asset growth properly and run the Lazy Prices and short
   interest pipelines against fourteen years instead of four (1.2, 1.3, 1.4).
5. Apply drawdown control, the breadth floor and integrated construction to whatever
   survives, and only then discuss leverage (3.1, 3.5, 3.4, 3.6).
6. Let September 4 arrive without touching the registry.

## References

Bailey and Lopez de Prado (2014), *The Deflated Sharpe Ratio*, Journal of Portfolio
Management. Cohen, Malloy and Nguyen (2020), *Lazy Prices*, Journal of Finance. Cooper,
Gulen and Schill (2008), *Asset Growth and the Cross-Section of Stock Returns*. Gu, Kelly and
Xiu (2020), *Empirical Asset Pricing via Machine Learning*, Review of Financial Studies. Hou,
Xue and Zhang (2020), *Replicating Anomalies*, Review of Financial Studies. Harvey, Liu and
Zhu (2016), *…and the Cross-Section of Expected Returns*. Hong, Li, Ni, Scheinkman and Yan,
*Days to Cover and Stock Returns*, NBER 21166. Moskowitz, Ooi and Pedersen (2012), *Time
Series Momentum*. Blitz, Baltussen and van Vliet on long-only versus long-short factor
implementation. Lopez de Prado (2018), *Advances in Financial Machine Learning*, on purged
and combinatorial cross-validation.
