# WorldQuant BRAIN — how it works, and what this project should actually use it for

*Written 2026-09-22. Status: scoping document. Nothing has been run. No account exists yet.*

This document has two halves. The first explains the platform plainly. The second is the
part that matters: **what BRAIN can and cannot tell this project**, and a bounded
experiment that uses it for the one thing it is genuinely good for here.

The short version of the second half, stated up front so it is not buried: BRAIN's
headline scoreboard (Sharpe, fitness) is the *wrong* instrument for this project, because
it is the same instrument that produced eleven years of headline numbers here that all
died. BRAIN's **data** is the right instrument, because it fixes the three specific
weaknesses the Step 296–308 null still carries. Use the data, ignore the scoreboard.

---

# Part 1 — How BRAIN works

## What it is

WorldQuant BRAIN is a free, web-hosted simulation platform. You write a one-line-to-
several-line mathematical expression ("an alpha") over their point-in-time market and
fundamental data; their engine turns it into a portfolio, backtests it, and scores it.
WorldQuant is a real quant fund; the platform is how they crowdsource signal ideas. Strong
contributors can become paid "Research Consultants."

You do not get the data. You get to compute on it, inside their sandbox.

## The seven steps

**1. Sign up.** Free, at `platform.worldquantbrain.com`. Approved-country restrictions
apply for the paid consultant track; simulation access is open.

**2. Pick your simulation settings.** These are the backtest's ground rules:

| setting | what it means | what we would use |
|---|---|---|
| `region` | market: USA, CHN, EUR, ASI, GLB | `USA` first — it is the market our signals were built on |
| `universe` | liquidity bucket: TOP3000 / TOP1000 / TOP500 / TOP200 | `TOP3000` — the widest cross-section |
| `delay` | 1 = yesterday's data trades today. 0 = same-day | **always 1** (see §"Where the bugs live") |
| `decay` | exponentially smooth the alpha over N days | `0` to start; it is a turnover-reduction knob |
| `neutralization` | strip out MARKET / SECTOR / INDUSTRY / SUBINDUSTRY exposure | this is the important one — see below |
| `truncation` | cap on any single name's weight (e.g. 0.08) | caps concentration by construction |
| `pasteurization` | drop names that were not tradeable that day | `ON` |
| `nanHandling` | how missing values are treated | `ON` |

**3. Write the alpha.** The language is "FastExpr" — a compact vectorised DSL. Every
expression is evaluated for every stock on every day. The main operator families:

- cross-sectional: `rank(x)`, `zscore(x)`, `winsorize(x, std=4)`, `scale(x)`
- time-series: `ts_mean(x,d)`, `ts_delta(x,d)`, `ts_delay(x,d)`, `ts_rank(x,d)`, `ts_zscore(x,d)`
- grouping: `group_rank(x, subindustry)`, `group_neutralize(x, sector)`, `group_zscore(x, g)`
- conditional: `if_else(cond, a, b)`, `trade_when(cond, x, n)`
- fields: `close`, `volume`, `vwap`, `cap`, `returns`, plus fundamental fields (`sales`,
  `cashflow_op`, `capex`, `assets`, `liabilities`, `debt`, `equity`, …) and dozens of
  vendor datasets (analyst estimates, news, options, sentiment).

**4. The engine turns your number into a portfolio.** This is the step people skip, and it
is the one that decides what the score means:

> the alpha value for each stock, after neutralization, is normalised across the universe
> and scaled to the book size. **Positive value → long. Negative value → short. Magnitude
> → position size.**

So the expression is not a buy list. It is a *cross-sectional score*, and the book is
automatically dollar-neutral-ish long-short across all ~3000 names, with the chosen group
exposure stripped out. `neutralization = SUBINDUSTRY` means the book is long the good
names and short the bad names *within each subindustry*, carrying no market, sector, or
industry bet at all.

**5. Simulate.** Runs over their in-sample window (multi-year, same window for everyone).
You get Sharpe, returns, turnover, max drawdown, margin, a PnL curve, and a pass/fail
checklist.

**6. Read the scorecard.** Submission thresholds, as commonly documented — *verify current
values on the platform, they vary by region and delay and they change*:

- **Sharpe ≥ 1.25**
- **Fitness ≥ 1.0**, where `Fitness = Sharpe × sqrt(|returns| / max(turnover, 0.125))`
- **Turnover between 1% and 70%**
- **Self-correlation < 0.7** against your own already-submitted alphas (or Sharpe ≥ 1.1×
  the correlated one)
- sub-universe Sharpe check, weight-concentration check

**7. Submit.** A passing alpha enters their pool and accrues an out-of-sample record from
the submission date forward. Consultants are paid on that.

## The API

Everything above is scriptable. Base `https://api.worldquantbrain.com`:

- `POST /authentication` with HTTP Basic auth → session cookie
- `POST /simulations` with `{"type":"REGULAR","settings":{…},"regular":"<expression>"}`
  → `201`, and the `Location` header carries the simulation id
- poll that location until `status == "COMPLETE"` → yields an `alpha_id`
- `GET /alphas/{id}` → full record including `is.checks`
- `GET /alphas/{id}/recordsets/pnl` → the daily PnL series
- `GET /data-fields?dataset.id=…` → the field dictionary

**Note for this session:** `api.worldquantbrain.com` is blocked by this environment's
egress proxy (403 on CONNECT). Any script written here is unvalidated against the live API
and must be run from the owner's own machine.

---

# Part 2 — What this is actually worth to this project

## The three things BRAIN fixes that we could not fix ourselves

Every one of these is a named, recorded weakness of the current null, not a hypothetical.

**1. It gives point-in-time fundamentals on a wide universe with real history, free.**
Step 287 found every fundamental panel here began in 2023, so nothing had ever been tested
off its selection window. SEC FSDS pushed that back to 2012 at considerable effort. BRAIN
supplies professionally-cleaned point-in-time fundamentals with delisted names included,
over a decade-plus, across ~3000 names. Step 300 got the universe from 509 issuers to
2,681 and called it "the one free change that affects" the power problem. BRAIN gives that
for nothing, with none of the FSDS tag-mapping work and none of the roster-construction
risk that Step 312 caught silently deleting two-thirds of a cache.

**2. Neutralization is a setting, not a project.** Step 295 spent a full step establishing
that removing market beta took cash conversion from 16.65% CAGR to 1.59% — ninety per cent
of the return was beta. Steps 293 and 295 then built market-neutral machinery and found
nothing to put in it. On BRAIN, `neutralization = SUBINDUSTRY` removes market, sector *and*
industry exposure **by construction, before scoring**. Every number BRAIN reports is
already past the gate that killed the dashboard. That is a genuinely different measuring
instrument.

**3. It is an independent implementation.** This project has twice found real lookahead
bugs that a code read missed (`bt`'s same-bar execution; GGG's covariance lookahead).
BRAIN's `delay=1` is enforced by someone else's engine, on someone else's data, with no
code of ours in the path. A null that replicates there is a null that survived an
independent re-implementation — which is the strongest form this project's central finding
could take.

## The four ways it could mislead us

**1. BRAIN does not report the measurement that decides things here.** It reports Sharpe,
fitness, turnover, returns, drawdown. It does **not** report rank IC, decile spread, or
decile monotonicity. CLAUDE.md §2 is explicit that monotonicity is "the one that matters
most and the one this project went 296 steps without measuring," and that six of thirteen
signals showed a positive IC alongside a *negative* decile spread — noise measured twice.
Walking onto BRAIN and reading the Sharpe is a regression to exactly the pre-Step-296 way
of evaluating that produced 337% CAGRs that all died. **Monotonicity has to be constructed
by hand from decile-sliced alphas. That is the experiment, and it is step one.**

**2. BRAIN is the largest multiple-testing machine this project has ever touched.**
Unlimited simulations, thousands of users, an operator zoo, a fixed in-sample window
shared by everyone, and community-circulated "golden combination" templates. Anything that
clears Sharpe 1.25 there is the survivor of a search whose size is not merely uncounted but
*uncountable*. CLAUDE.md §1.3 requires reporting the actual cumulative N; on BRAIN we
cannot. A BRAIN pass is therefore **weaker** evidence than a Sharpe of 1.25 produced here,
not stronger, and must be described that way. Their own in-sample window is collectively
burned. The only genuinely untouched data on that platform is the forward record after a
submission date.

**3. Daily bars will inflate every t-statistic on a quarterly signal.** Our three
fundamental signals update when a filing lands — four times a year. On BRAIN they sit on a
daily grid, forward-filled between reports. Thirteen years is ~3,250 daily observations and
about **52 independent decisions**. Step 303 recorded exactly this failure mode: "t-statistics
climb with horizon purely from overlap; reading the t instead would have manufactured three
discoveries." Any significance number BRAIN's daily series implies is badly overstated for
these signals. Read shape, not significance — the same call Steps 296, 302 and 303 made.

**4. A BRAIN result does not validate the Atlas book, and cannot be traded by us.** BRAIN's
portfolio is delay-1, ~3000 names, dollar-neutral, subindustry-neutral, truncated, at
1–70% turnover. Our books are weekly, long-only, top-5 to top-20 names. These are not the
same object. Also: returns appear to be reported **gross**, with turnover entering only
through the fitness penalty rather than as a bps deduction — *verify this on the platform* —
so a BRAIN pass does **not** satisfy CLAUDE.md §7, and the 0/10/50/100 bps stress still has
to happen on our side. And the data stays theirs: a working alpha there is not portable to
anything we could run.

## So what is it for?

**Not for finding a strategy.** For *falsifying, or failing to falsify, our central claim on
data we do not own.*

The claim is: **nought of thirteen dashboard signals, and nought of fourteen closed
families, order their deciles.** Its honest weaknesses are stated in CLAUDE.md and in the
registries — 13–14 quarterly decisions, a panel we built ourselves, a universe we
restricted ourselves, and construction errors that have been found before.

BRAIN removes all four weaknesses at once. That makes it the cheapest available adversarial
pass on the most important finding this project has produced.

Both outcomes are worth having:

- **The ladders are flat on BRAIN too.** The Step 296–308 null is now replicated on
  independent, professionally-constructed, point-in-time data with ~5× the cross-section,
  through someone else's backtester. **Not with more decisions — see the correction
  below.** That is close to as strong as
  this finding can get, and it closes the "maybe our panel was wrong" objection permanently.
- **A ladder orders itself on BRAIN.** That is the first genuine lead in 312 steps — and
  the immediate next question is *not* "trade it," it is "is this a real signal we missed,
  or a difference between their data construction and ours?" Which is itself the most
  informative question available, because it would mean our panel has a defect worth finding.

State the prior plainly: nought of thirteen, nought of fourteen closed families, nought of
six out-of-sample, nought of three on the wide universe, nought of four in Indonesia, nought
of six at long horizons. **The probability that these three signals order their deciles on
BRAIN is low.** Going in expecting otherwise is how this project has burned sessions before.

---

# Part 3 — The experiment

## Phase 0 — audit before measuring (half a day)

Do not write a signal yet.

1. Create the account. Confirm region/universe availability and the current threshold values.
2. `GET /data-fields` for the fundamental dataset. **Confirm the actual field ids** — the
   names used below (`sales`, `cashflow_op`, `capex`, `assets`, `liabilities`, `debt`,
   `equity`, `net_income`) are the commonly-cited ones and are **not verified**.
3. **Density guard, per CLAUDE.md §2.** Before any decile reading, check coverage: what
   fraction of TOP3000 names on a given day have a non-null value for each field. Step 298
   nearly reported Form 4 as a discovery on a signal that was 93.3% zeros. A field that is
   sparse or stale cannot be read on deciles at all. If a field is below 50% dense, the
   signal built on it is not measurable and that must be recorded, not worked around.
4. Confirm whether reported returns are gross or net of costs.

## Phase 1 — the decile ladder (the actual test)

For each of the three dashboard signals, run **twelve** simulations:

- **ten decile alphas**, each long-only and equal-weight on one decile of the signal, with
  `neutralization = NONE`. Their reported `returns` is that decile's mean return. All ten
  carry the same long-only market exposure, so comparing across them is beta-neutral in
  exactly the sense the Step 296 registry defines.
- **one long-short**, top decile minus bottom decile, `neutralization = NONE` → the decile
  spread as a tradeable book.
- **one production form**, the continuous ranked signal at `neutralization = SUBINDUSTRY` →
  what BRAIN would actually score.

Then compute, off-platform, the same three numbers Step 296 computed:

- **rank IC** proxy (from the production form's PnL, or directly from the ladder)
- **top-minus-bottom decile spread**
- **decile monotonicity** — Spearman correlation between decile index 1–10 and decile mean
  return. **This is the number that decides.**

36 simulations for three signals. Add a negative control: the same ladder on raw `assets`
(size), which should be flat after neutralization, plus a sign-flipped run of each signal.
Note honestly that this is a weaker placebo than the block bootstrap used here — BRAIN has
no shuffle operator — and that the dispersion of the ten decile returns around their own
mean is the best in-built noise scale available.

## Phase 2 — conditional, and only conditional

**Nothing proceeds to Phase 2 unless a ladder clears monotonicity.** Declare the bar before
running: every signal measured in this project sits within ±0.17 of zero. A result worth
pursuing is **monotonicity above 0.5 with interpretable deciles** — the same bar the
`cross_sectional_skill_registry_v1` declared for Steps 300 and 303.

If nothing clears: write it into `PROJECT_HISTORY.md` as a replication of the null on
independent data, move the item to the queue's `Closed` table, and stop. That is a complete
and valuable result, and it is the expected one.

If something clears: the next step is **not** to submit it or build a book on it. It is to
find out why their data says something ours does not — field definitions, universe
composition, restatement handling, delisted-name inclusion. A disagreement between two
point-in-time panels is a data finding before it is a signal finding.

## The expressions

**Syntax correction, 2026-09-22.** An earlier draft of this document used semicolon-separated
statements with variable assignment (`ocf_margin = ...;`) and compound booleans (`&&`). Both
are unsafe: FastExpr's multi-statement form is not reliably documented at every account tier,
and its boolean operators are function-style (`and`, `or`, `less`, `greater`) rather than C
style. Everything below is a **single inlined expression using only `>`**. Verbose beats
clever when a parse error costs a simulation slot.

Generate them ready to paste with:

```
python scripts/run_worldquant_brain_decile_ladder_v1.py --print-expressions
```

Direct translations of `build_dashboard_signals_out_of_sample_v1.py::SIGNALS`. Our scoring
is a sector-neutral mean of percentile-ranked features, which is exactly
`group_rank(x, sector)` averaged — the mapping is close to one-to-one. **Field ids
unverified; confirm in Phase 0.**

```
# cash_conversion_breadth20
(group_rank(cashflow_op / sales, sector)
 + group_rank((cashflow_op - capex) / sales, sector)
 + group_rank(cashflow_op / sales - net_income / sales, sector)) / 3

# balance_sheet_quality
(group_rank(cash / assets, sector) + group_rank(equity / assets, sector)
 - group_rank(debt / assets, sector) - group_rank(liabilities / assets, sector)) / 4

# growth_top5
(group_rank(ts_delta(sales, 250) / abs(ts_delay(sales, 250)), sector)
 + group_rank(ts_delta(net_income, 250) / abs(ts_delay(net_income, 250)), sector)
 + group_rank(ts_delta(cashflow_op, 250) / abs(ts_delay(cashflow_op, 250)), sector)) / 3
```

**Decile k**, as the difference of two step functions rather than a compound condition —
`(rank > lo) - (rank > hi)` is exactly the indicator for the half-open band:

```
if_else(rank(SIG) > <lo>, 1, 0) - if_else(rank(SIG) > <hi>, 1, 0)
```

with `lo = (k-1)/10`, `hi = k/10`, and `lo = -1` for decile 1 so that both terms propagate
NaN identically (`rank()` can return exactly 0 for the minimum name, which `> 0` would drop).

**Top-minus-bottom spread:**

```
if_else(rank(SIG) > 0.9, 1, 0) - if_else(rank(SIG) > 0.1, 0, 1)
```

### Quarterly fields are fine — and do not build TTM with ts_sum

Our panel uses trailing-four-quarter figures for the flow items (`qtrs == 4`). If BRAIN
exposes only quarterly variants, use them directly and record the difference:

- **margins** are ratios, so quarterly numerator over quarterly denominator is a valid
  margin — noisier than TTM, not wrong;
- **YoY growth** over ~250 trading days compares a quarter against the same quarter a year
  earlier, which is what our `.shift(4)` does;
- **balance-sheet ratios** are stock over stock and never had the question.

**Do not reach for `ts_sum(sales, 250)` to synthesise TTM.** Fundamental fields are step
functions forward-filled on a daily grid, so that sums one forward-filled value ~250 times
rather than four quarters. This is the kind of silent construction error that cost Steps 291
and 312.

### Three deliberate differences from our implementation

Recorded so they are not discovered later and mistaken for bugs:

- we group by a hand-built SIC→sector map over 69 major groups; BRAIN groups by its own
  classification. Start with `sector` as the closest analogue.
- our `minimum: 2` rule (score only names with at least two non-null features) has no direct
  FastExpr equivalent. BRAIN's `nanHandling` governs it instead. This is precisely why
  Phase 0's density audit comes first.
- our books are weekly top-N long-only; BRAIN's decile alphas are daily-rebalanced
  equal-weight baskets. The ladder measures the signal's ranking content, which is the
  question — it does not reproduce the book.

## Pre-registration

If this is run, freeze a `worldquant_brain_replication_v1.json` in `2.0/config/` **before
the first simulation**, in the house style: `registered_before_any_result_existed: true`,
`this_is_a_diagnostic_not_a_search: true`, `strategy_promotion_authorized: false`, the
trials declared (36 + controls), the Bonferroni bar, the declared reading in both
directions, and the known weaknesses above stated up front. No strategy comes out of this
regardless of outcome — a signal that scores well here is a reason to *construct* something
and test it under its own pre-registration, not a candidate.

## What this cannot do

- It cannot satisfy the cost gate (§7). Do that here, on our data.
- It cannot produce a tradeable strategy — their data does not leave the platform.
- It cannot produce an untouched forward record for *our* purposes on the in-sample window;
  only a submission's forward accrual is genuinely untouched, and that record belongs to
  WorldQuant.
- It cannot count its own multiple testing, and must say so.

---

# Run log

## 2026-09-22 — Phase 0 and the production forms, partial

**Correction to this document: the in-sample window is far shorter than assumed.**
An earlier draft claimed BRAIN supplies "a decade-plus" and "~4× the decisions." The
simulator's own IS summary shows a **TRAIN period of 2019–2022 — four years**, roughly
**16 quarterly decisions** against Step 296's 13–14. On the decision-count axis BRAIN buys
this project almost nothing. Separate TEST / IS / OS tabs exist and may extend the total
span; that has not been established yet and must be before any power claim is repeated.

**Two consequences, both of which the plan survives.**
1. The real gain is **cross-sectional depth**, not calendar length: ~3,000 scored names
   against the 509 the fundamental signals have always used. Step 300 decomposed
   per-decision IC dispersion into a sampling component of 0.115 and true time variation of
   0.086–0.196, and only the first shrinks with names — so this improves per-decision
   precision and does nothing for the number of decisions.
2. **The significance null is underpowered here too**, exactly as it was in Steps 296, 302
   and 303. Monotonicity carries the weight, because it reads the shape of the relationship
   rather than its significance. The experiment is unchanged; the framing is.

**A further honest limit: 2019–2022 is not an untouched window.** Step 300's wide-universe
screen ran 2013–2022, so BRAIN's TRAIN period sits *inside* ground this project has already
covered. What is independent is the data construction, the vendor, the universe and the
backtester — not the calendar. This is a replication on independent *data*, not on an
independent *period*.

### Field ids — resolved and unresolved

Confirmed to exist and parse: `assets`, `assets_curr`, `capex`, `cash`, `cash_st`,
`cashflow`, `cashflow_op`, `cogs`, `current_ratio`, `debt`, `debt_lt`, `debt_st`, `ebit`,
`ebitda`, `sales`, `equity`, `liabilities`. Instrument coverage reads **50%** across the
fundamental fields with 100% date coverage — above the 50% density floor, but only just,
and it should be treated as the binding caveat on every reading below.

**`net_income` does not exist.** The simulator rejects it: *"Attempted to use unknown
variable net_income."* This blocks `cash_conversion` (which needs it for the cash-conversion
spread) and `growth` (which needs it for one of three growth legs). Resolve with
`--find-field <dataset> income` before re-running either.

### Results so far

| signal | neutralization | Sharpe | returns | turnover | status |
|---|---|---|---|---|---|
| `group_rank(cashflow_op / sales, sector)` (smoke test) | — | 0.64 | 6.64% | 2.46% | pipeline confirmed |
| `balance_sheet_quality` | (confirm) | **−1.47** | **−10.38%** | 2.56% | ran; **wrong sign** |
| `cash_conversion` | — | — | — | — | blocked on `net_income` |
| `growth` | — | — | — | — | blocked on `net_income` |

### balance_sheet_quality: refuted on sign, and the trap that comes next

Sharpe −1.47, returns −10.38%, and **negative in all four years** (−1.84, −1.30, −2.03,
−1.22). That consistency is not a noise pattern.

The declared sign for this signal is **positive**: more cash, more equity, less debt, fewer
liabilities should rank higher. BRAIN's data says the opposite, consistently, on a
four-year window.

**This is a refutation of the declared hypothesis. It is not the discovery of an inverted
one.** Community guidance around BRAIN explicitly encourages flipping a negative Sharpe
("a Sharpe of −1.8 is a good alpha with a minus sign missing"). For this project that
advice is poison: post-hoc sign flipping doubles the search space for free and converts
every refutation into a discovery. The project has held this line before and must hold it
here — Step 286 recorded Form 4 opportunistic insiders as *"refuted on sign, rather than
flipped"* at IC −0.0188, and Step 282 refused to rescue FINRA short volume from a −28% book
by reversing it, because *"the sign was declared, the IC behind it is insignificant."*

Three readings remain open and the decile ladder separates them:

1. **Real inverted content.** Low-quality, levered balance sheets outperformed. Plausible on
   2019–2022 specifically, which contains the 2020 crash and the 2020–21 junk-and-leverage
   recovery — a regime, not an edge (CLAUDE.md §6). An inverted signal would need its own
   pre-registration on a window not used to find the inversion.
2. **A definition difference.** Our `debt` is a sum of three SEC tags
   (`LongTermDebtNoncurrent`, `LongTermDebt`, `DebtCurrent`); BRAIN exposes `debt`,
   `debt_lt` and `debt_st` separately and their aggregation is unknown. Same for
   `liabilities` and `equity`. A sign this strong from a ratio this simple deserves the
   definitions checked before it is believed in either direction.
3. **Concentration.** A strong Sharpe from the extremes with an unordered middle is what
   Step 296 found six times over: positive IC alongside a negative decile spread, which is
   noise measured twice.

**Nothing is concluded until the ladder runs.** Record the neutralization setting used —
the table above cannot be read without it.
