# A15 — five hypotheses on WorldQuant BRAIN, with 2023 held out, pre-registered

*Written 2026-09-30, committed before the first A15 simulation. Machine-readable twin:
`config/worldquant_brain_a15_v1.json`. If the two ever disagree, the JSON is the registration.
Runner: `scripts/run_worldquant_brain_a15_v1.py` (reuses the A12 runner's platform code).*

## What this is for, in plain words

The owner wants to keep looking on BRAIN for a signal that works. The problem is that BRAIN only
simulates **2019-01-01 to 2023-12-31** (Step 327), and 528 simulations have already been run on
that window from this account. Any further search there produces false positives unless part of
the window is held back. A12's two candidates (Step 326) both ordered their deciles in 2019-2022
and failed in 2023, which for their fields was the only year collected live.

So A15 **chooses everything on 2019-2022 and reads 2023 once, at the end**. That is the only
change of method from A12. Everything else (decile ladders, coverage-matched controls, the density
guard, never flipping a sign, delay 1) is carried over.

A pass would be **one BRAIN signal that ordered its deciles on data it was not chosen on**. That is
a reason to price the data and pre-register a construction on our own panel. It is not a
strategy, and nothing is promoted or submitted.

## The holdout design — declared before any simulation

- **Train = 2019, 2020, 2021, 2022.** The train ladder of a signal is, per decile, the mean of
  BRAIN's `yearly-stats` returns for those four years. Readability, bars, which variant is
  "best", and which hypotheses get kill tests are decided on this alone.
- **Holdout = 2023.** Read once, after `docs/BRAIN_A15_TRAIN_FREEZE_V1.md` (the frozen choices and
  their train numbers) is committed. The runner will not print a full-window or 2023 number before
  that, and `--phase holdout` refuses to run unless the freeze file is committed and clean.
- **Where 2023 is a real live-data holdout.** Only for fields BRAIN created by 2022-12-31. Checked
  per field with `GET /data-fields/{id}` (no simulation), saved to
  `evidence/worldquant_brain_a15_v1/field_verification.json`:

  | field | created | 2023 is |
  |---|---|---|
  | `anl4_buy`, `anl4_under`, `anl4_total_rec` | 2022-08-01 | live |
  | `anl4_bac1actualqfv110_actual` | 2022-07-01 | live |
  | `anl4_fs_actuals_basic_qf_nd_sales_value` | 2026-03-01 | loaded history (H2c only) |
  | `anl4_basicconafv110_numest`, `anl4_basicconqfv110_numest` | 2022-07-01 | live |
  | `anl4_basicconltv110_mean` | 2022-07-01 | live |
  | `implied_volatility_mean_30/90`, `historical_volatility_30/90` | 2022-05-01 | live |
  | `cap`, `close`, `returns`, `sector` (pv1) | 2023-07-01 | a catalogue re-listing date; prices are point-in-time by nature |

  Hypotheses were chosen partly *because* their fields were live by 2022, so that the holdout
  means something.
- **`testPeriod` is not used.** Step 327 found it only carves a slice out of the same window.
  The yearly-stats rows already give 2023 separately, so relying on an unverified setting would
  add risk and buy nothing.

## Settings (all runs)

USA / TOP3000 / delay 1 / decay 0 / truncation 0.08 / pasteurization ON / nanHandling ON /
unitHandling VERIFY. Decile ladders at MARKET, production forms at SUBINDUSTRY (reported only),
density probes at MARKET. Delay 0 is forbidden. BRAIN's 50 requests a minute is respected.

## The hypotheses

None is in the Closed table, and none was tested in A12 (H1-H5). Signs are inside the
expressions and never change. Decile 10 is always the declared "good" end.

### H1 — Recommendation changes, rebuilt (B5) · sign positive
Jegadeesh, Kim, Krische & Lee (2004): a change in consensus recommendation predicts returns
better than its level. Step 326's H5 was **unmeasured** at 0.3% density, because `vec_avg` of an
event field exists only on event days. Rebuilt: the net-buy share
`(buy − underweight) / total` is carried forward with `ts_backfill(·, 252)` before any change is
taken.
- H1a: 63-day change of the carried-forward share
- H1b: 126-day change
- H1c: the most recent change within 126 days (`x − last_diff_value(x, 126)`)

Horizons 63/126 replace A12's 21/63/126, because a 21-day change of a carried-forward series is
mostly zero by construction. **Outside source:** Finnhub's free tier gives monthly recommendation
counts with history.

### H2 — Earnings-announcement premium · sign positive
Frazzini & Lamont (2007); Barber, De George, Lehavy & Trueman (2013): stocks earn a premium around
scheduled earnings announcements. This is about **timing**, not surprise. PEAD/SUE (closed) is
about the size of the surprise. Days since the last announcement is `d = days_from_last_change` of
the carried-forward quarterly announced actuals. The signal peaks on the expected next date.
- H2a: `−|d − 63|` on `anl4_bac1actualqfv110_actual` (live from 2022-07)
- H2b: `−|d − 58|`, same field (the pre-announcement run-up)
- H2c: `−|d − 63|` on quarterly actual sales (`anl4_fs_actuals_basic_qf_nd_sales_value`; created
  2026-03, so its 2023 read is not live)

**Interpretation risk, declared now:**
- `d` is assumed to count trading days.
- A quarter whose averaged actuals do not change reads as a missed announcement.
- A restatement reads as an announcement.

**Outside source:** SEC EDGAR 8-K Item 2.02 dates are free, point-in-time, and cover the full
history. This is the most usable-by-us channel in the batch.

### H3 — Analyst coverage change · sign positive
Kelly & Ljungqvist (2012); Irvine (2003). Losing analysts raises information asymmetry and prices
fall; gaining them does the opposite. The signal is `log(1+N) − log(1+N 252 days ago)`, with `N`
carried forward. The change is year-on-year so that the fiscal-year roll compares like with like.
A12's H1 used the estimate count only as a denominator.
- H3a: `N` = number of annual-EPS consensus estimates (`anl4_basicconafv110_numest`)
- H3b: `N` = quarterly consensus estimates (`anl4_basicconqfv110_numest`)
- H3c: `N` = number of recommendations (`anl4_total_rec`)

**Outside source:** Finnhub's recommendation history gives analyst counts per month, free.

### H4 — Long-term growth forecast · sign negative
La Porta (1996); Dechow & Sloan (1997). Analysts over-extrapolate, so stocks with the highest
long-term growth forecasts underperform. This is the **level** of expectations, not their revision
(A12 H1) or the disagreement between analysts (A12 H2).
- Field: `anl4_basicconltv110_mean`, coverage 0.70.
- **Interpretation risk, declared now:** BRAIN describes it only as "Mean of estimations" in the
  long-term consensus family. The item code sits in `anl4_bac1conltv110_item` and cannot be
  filtered here. It is read as consensus LTG. If the family mixes other long-term items, the
  hypothesis is mis-specified.

Variants:
- H4a: ranked within sector
- H4b: ranked within industry
- H4c: ranked within subindustry

H4b and H4c are a grouping-neighbourhood check of H4a, not new ideas. **Outside source:** Yahoo's
"next 5 years" estimate is free but a snapshot only. Point-in-time history (IBES, Zacks) is paid.

### H5 — Implied minus realized volatility · sign negative
Bali & Hovakimian (2009): stocks whose option-implied volatility sits far above their realized
volatility subsequently underperform. This is distinct from A12's H3 (the smirk: OTM put against
OTM call) and H4 (ATM call against put). Fields are `option8`, live from 2022-05.
- H5a: 30-day IV − 30-day realized
- H5b: 90-day IV − 90-day realized
- H5c: 21-day mean of H5a, the lower-turnover form

**Known confounds:**
- It is related to the volatility level. Low volatility is closed, and Step 320 read
  `historical_volatility_20` at −0.006.
- It is related to A12's H4.

**Outside source:** our free forward collection (Step 327) plus free prices. Historical IV is paid.

### Considered and dropped before any simulation (not counted as trials)
- **Management guidance:** coverage 0.29-0.33, below the density floor.
- **Street-minus-GAAP exclusions** (Doyle, Lundholm & Soliman 2003): the fields resolve but were
  created in 2026-03, so there is no live holdout.
- **Dividend-month premium** (Hartzmark & Solomon 2013): the `dividend` field's semantics cannot be
  established without simulations, and non-payers would form one tie block.
- **An "EPS growth rate" field:** its siblings show it is reported EPS, not LTG.

## Density guard, first

Every variant is probed with `if_else(abs(<inner signal>) > 0, 1, 0)` at MARKET, where the inner
signal is the variant without its outer `group_rank`. `longCount / 3000 < 0.50` → **UNREADABLE**,
no ladder, nothing substituted.

This is a correction to A12, which probed the `group_rank`-wrapped expression. `group_rank` gives a
block of tied raw zeros one shared, generally non-zero rank, so exact zeros could have counted as
non-zero. It is stated here, not discovered later.

Every ladder must also pass the tie check: each decile holds 5-15% of scored names, averaged over
the train years.

## Controls

For each hypothesis, `group_rank(cap + 0 * <variant-a inner>, sector)`: market cap ranked within
sector on exactly that signal's mask. The mask is the **carried-forward** signal, not the
event-day-only field that made A12's C1 unreadable.
- A control is run only if its hypothesis has a readable variant.
- If a control fails its own tie check, the hypothesis falls back to the Step 317 full-coverage cap
  control (+0.091 / −0.119), but only when the variant scores ≥90% of the universe. Otherwise the
  control bar is UNTESTABLE and the variant cannot pass.

## Train bars (2019-2022 only)

- **T1** ORDERS ITS DECILES: full > 0.5 and middle-8 > 0.5, in the declared sign.
- **T2** Beats its control's train ladder on full AND middle-8.
- **T3** Passes the tie check.
- **T4** Monotonicity > 0 in at least 3 of the 4 train years.
- **T5** Train permutation p < 0.05 / (528 + 300) = **6.04e-5**. The denominator is the account's
  prior simulations plus this batch's maximum.

**Best variant per hypothesis:**
- Among variants passing T1-T5, the one with the largest train (full + middle-8). Ties are broken by
  lower 2019-2022 production turnover.
- If none passes, the one with the largest train (full + middle-8) is frozen for the record and
  **cannot pass**.

**Kill tests (conditional, kill-only).** These run for at most 3 hypotheses whose frozen variant
passes T1-T5:
- **K1 de-sized:** `group_rank(<inner>, bucket(rank(cap), range="0,1,0.2"))`
- **K2 momentum-neutral:** `group_rank(<inner>, bucket(rank(ts_sum(returns, 63)), range="0,1,0.2"))`

Each must ORDER on its train ladder, and must differ from the raw ladder (the grouping-live check
that caught Step 326's `buckets=5` bug).

## The pass, read after the freeze

A hypothesis **passes** only if its frozen variant has all of:
1. T1-T5 and K1-K2;
2. **P1** — the full 2019-2023 ladder ORDERS ITS DECILES, beats its control on full and middle-8,
   passes the tie check, and its permutation p < 0.05 / (528 + A15 simulations actually run);
3. **P2** — the 2023-only ladder has monotonicity > 0 **and** a positive d10 − d1.

Other variants' holdout numbers are reported as read-outs and cannot pass.

## Budget — fixed

| item | simulations |
|---|---|
| density probes | 15 |
| production forms | ≤ 15 |
| ladders | ≤ 150 |
| controls | ≤ 50 |
| kill tests | ≤ 60 |
| syntax corrections | ≤ 10 |

**Maximum 300.** The batch stops there whatever it finds. No hypothesis is added or substituted
after any result. One syntax-only correction is allowed per expression (same fields, sign and
horizon); it is recorded and counted.

## Multiple testing

- **Prior count.** The account held **528** simulations before A15, verified by
  `GET /users/self/alphas` (count 528, active 0), with no simulation spent.
- **Final Bonferroni.** Uses 528 + A15's actual count.
- **BH-FDR.** At q = 0.05 over A15's readable variants, reported alongside.
- **The limit behind both.** The 2019-2023 window has also been searched by thousands of other BRAIN
  users (field user counts up to 2,257 here), and that search cannot be counted.
- **Permutation test.** It treats ten decile returns as exchangeable, so it measures shape, not
  sampling error.

## If something passes

Nothing is submitted. The write-up describes, without running it, what a submittable version
would need: BRAIN's checks (Sharpe ≥ 1.25, fitness ≥ 1.0, turnover 1-70%, sub-universe Sharpe,
concentration, self-correlation). A submitted alpha's forward record is the only genuinely
untouched data BRAIN offers, and submitting is the owner's decision.

## Honest limits, stated before the run

- Four train years are about 16 quarterly decisions. One holdout year is about 4. **A 2023 pass is
  weak confirmation and a 2023 fail is weak refutation.** The holdout exists to catch what A12
  could not: an ordering that is purely a 2019-2022 artefact.
- H1, H3 and H4 all use `analyst4`, and H1 and H3c share `anl4_total_rec`. They are five
  hypotheses, not five independent datasets.
- The literature behind all five is post-publication and widely traded.
