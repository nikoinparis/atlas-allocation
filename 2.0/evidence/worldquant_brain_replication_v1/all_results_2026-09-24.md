# WorldQuant BRAIN — every ladder measured, 2026-09-22 to 2026-09-24

Consolidated by hand because successive runs at neutralization NONE overwrote a shared
`summary.json` (fixed 2026-09-24: output dirs are now tagged by neutralization AND signal
set). Numbers marked *(log only)* were read from a run log that has since been cleaned up
and are recorded here because that is the only surviving copy.

**The bar that matters is not 0.5 and not BRAIN's 1.25. It is `control_size`.**
`group_rank(assets, sector)` — ranking companies by total assets, no skill in it whatever —
scores **monotonicity +0.867, middle-8 +0.905** market-neutral on 10/10 clean deciles.
Any signal that does not clear that is measuring size.

## Ladders, neutralization NONE unless stated

| signal | monotonicity | middle-8 | d10−d1 | distinct | vs control +0.867 |
|---|---|---|---|---|---|
| `sales_yield` *(log only)* | +0.988 | +0.976 | +43.5pp | 10/10 | +0.121 |
| `cash_conversion` | +0.939 | +0.905 | +26.4pp | 10/10 | +0.072 |
| `earnings_yield` *(log only)* | +0.891 | — | +26.7pp | 10/10 | +0.024 |
| `free_cash_flow_yield` *(log only)* | +0.879 | +0.762 | +31.2pp | 10/10 | +0.012 |
| **`control_size` (MARKET, NO SKILL)** | **+0.867** | **+0.905** | +14.1pp | 10/10 | — |
| `growth` | +0.855 | +0.738 | +35.9pp | 10/10 | **−0.012** |
| `control_size` (NONE, 9/10) | +0.832 | — | +25.3pp | 9/10 | — |
| `quality_acceleration` | +0.648 | +0.643 | +11.0pp | 10/10 | **−0.219** |
| `profitability` | +0.442 | +0.262 | +28.1pp | 10/10 | **−0.425** |
| `shareholder_discipline` | +0.139 | −0.381 | +11.2pp | 10/10 | **−0.728** |
| `balance_sheet_quality` | −0.927 | −0.857 | −24.0pp | 10/10 | inverted |

**Never obtained:** `composite_value` and `quality_at_reasonable_price`. Their first run died
on a session expiry and the re-run's output was overwritten before it was read. Two of
twelve families remain unmeasured and that is a gap, not a result.

## Production forms, SUBINDUSTRY, delay 1, TOP3000, ~3,045 names positioned

| signal | Sharpe | returns | turnover | fitness | drawdown |
|---|---|---|---|---|---|
| `growth` | **1.27** | 8.35% | 4.26% | **1.04** | 12.67% |
| `sales_yield` | 1.22 | 12.69% | 3.74% | — | — |
| `control_size` **(NO SKILL)** | 0.86 | **8.57%** | 2.13% | 0.71 | 25.61% |
| `cash_conversion` | 0.48 | 4.63% | 2.51% | 0.29 | 31.11% |
| `balance_sheet_quality` | −1.17 | −7.77% | 2.46% | −0.92 | 42.48% |

`growth` clears BRAIN's submission bar (Sharpe ≥ 1.25, fitness ≥ 1.0) **and returns less than
the no-skill control** (8.35% vs 8.57%). Its higher Sharpe is a drawdown difference.

## What MARKET neutralization did

| signal | mono NONE | mono MARKET | spread NONE | spread MARKET | beta share |
|---|---|---|---|---|---|
| `cash_conversion` | +0.939 | +0.939 | +26.4pp | +14.7pp | 44.3% |
| `growth` | +0.855 | +0.855 | +35.9pp | +20.4pp | 43.2% |
| `balance_sheet_quality` | −0.927 | −0.927 | −24.0pp | −13.4pp | 44.4% |

Monotonicity is **bit-identical** — market neutralization shifts decile levels without
reordering them, and monotonicity is scale-free, so it cannot see the change. What it removes
is ~44% of the *spread*, and the near-identical figure across three different signals is one
shared exposure rather than three independent ones. `cash_conversion`'s top decile earns
**+3.2%/yr** market-neutral, not +40% — Step 295's 16.65%→1.59% on someone else's data.

## Window and settings

`2019-01-01` to `2023-12-31` — five years, ~20 quarterly decisions. Read from the alpha
record's own `settings`, correcting an earlier claim of 2019–2022/four years. The `os`,
`train`, `test` and `prod` blocks are **null** on an unsubmitted alpha, so there are no
separate out-of-sample tabs and the entire span is in-sample. 2023 falls outside Step 300's
2013–2022 window; the other four years do not.

USA / TOP3000 / delay 1 / decay 0 / truncation 0.08 / pasteurization ON / nanHandling ON.
All fundamental fields sit at exactly **0.5 instrument coverage** — on the density floor,
clearing it but only just, and that is the binding caveat on every number above.

## Verdict

**Ten of twelve families measured. Zero beat a no-skill size control.** Four clear the
declared 0.5 monotonicity bar; all four clear it by roughly the margin `control_size` does,
and the highest of them (`sales_yield`, +0.988) is the most mechanically size-linked
construction in the set — sales over market cap is close to a size ranking with extra steps.

The Step 296–308 null replicates on data this project does not own, on a panel it did not
build, through a backtester it did not write, with a ~6× cross-section (3,045 names against
509). That was the declared expected outcome and it is the valuable one.

**The one genuinely new thing, which could not have been produced at home:** a decile ladder
on long-only baskets orders itself at +0.83 to +0.87 *on no signal at all*. Every monotonicity
this project has ever read needs that calibration point beside it.

---

# Correction, 2026-09-24: the control depends on coverage, and `cap` is flat

An earlier version of this file, and several statements made while producing it, generalised
the `control_size` result to *"a decile ladder on long-only baskets orders itself at +0.83 to
+0.87 on no signal at all."* **That generalisation is wrong and is retracted.**

Measured market-neutral, ten clean deciles each:

| no-skill ranking | coverage | monotonicity | middle-8 |
|---|---|---|---|
| `group_rank(assets, sector)` | **0.5** | **+0.867** | +0.905 |
| `group_rank(cap, sector)` | **1.0** | **+0.091** | −0.119 |

A no-skill ranking at full coverage is **flat**. The +0.867 is specific to `assets`, not a
property of decile ladders.

**The likely mechanism, stated as a hypothesis rather than a finding.** `assets` sits at 0.5
instrument coverage, so its ladder ranks only the half of the universe carrying fundamental
data, and which companies carry that data is not random. The `assets` ladder therefore mixes
an asset-size ordering with a has-fundamental-coverage ordering. `cap` has no such hole.

**What this does and does not change.**

- It does **not** rescue any fundamental signal. `cash_conversion`, `growth`, the valuation
  families and the three recovered families are all built from coverage-0.5 `fundamental6`
  fields with the same NaN pattern as `assets`. `assets` remains the correct comparator for
  them, and none of them beats it. The replication of the null stands.
- It does mean **the right control is whichever no-skill ranking shares the candidate's
  coverage.** For a coverage-0.5 fundamental signal that is `assets` at +0.867. For a
  coverage-1.0 field — the news and social sentiment fields — it is `cap` at +0.091.
- It makes the news18 bar both far more achievable and far more meaningful, because +0.091
  is a genuinely flat baseline rather than a contaminated one.

**Recorded as a lesson rather than a number:** a control must match the candidate's coverage,
or it is not measuring the same universe. This project has now been caught twice by coverage
patterns being informative in their own right — Step 298's 93.3%-zero signal, and this.

# Ravenpack (news18) unblocked, 2026-09-24

The `group_rank does not support event inputs` rejection was never an operator problem.
news18 publishes every sentiment field **twice**: a per-story `VECTOR` stream, and a
daily-aggregated `MATRIX` under a `mean_` prefix. 71 MATRIX fields, ten at coverage 1.0.

`equity_sentiment_score` (VECTOR, rejected) → `mean_equity_sentiment_score` (MATRIX, works).

Verified that the convention is exactly aggregation: `vec_avg(equity_sentiment_score)` and
`mean_equity_sentiment_score` return **identical** statistics (Sharpe 0.70, returns 3.87%,
turnover 0.9581). Either route works; the `mean_` fields are the cheaper one.

## First pass, MARKET-neutral, coverage 1.0, on a dataset with 8,996 users

| construction | Sharpe | returns | turnover | submittable? |
|---|---|---|---|---|
| `mean_news_impact_projection` | **1.44** | 4.60% | 107% | **no — over the 70% cap** |
| `mean_equity_sentiment × mean_entity_relevance` | 1.18 | 4.16% | 102% | no |
| `mean_earnings_evaluation_sentiment` | 0.76 | 4.39% | 99% | no |
| `mean_equity_sentiment_score` | 0.70 | 3.87% | 96% | no |
| `mean_event_novelty_score` | 0.70 | 2.30% | 107% | no |

Sharpe 1.44 market-neutral is the highest figure produced anywhere in this exercise, and
**every one of these is untradeable as written.** News sentiment turns over daily, so the book
churns essentially completely. `scl12_sentiment` already showed what the fix costs: smoothing
to 20 days dropped turnover from 111% to 14% and took Sharpe from +0.42 to **−0.19**.

The binding question is therefore not whether a news signal has content — it plainly has some
— but whether any of it survives being slowed to a tradeable speed. Six smoothing/decay
configurations are being measured, and that parameter search is declared: **six trials, into
the cumulative ledger, not free.**

**Nothing above is a candidate yet.** These are production-form Sharpes, which guardrail 1
declares is not the evidence. No ladder has been run on any news field.

# The news ladders, 2026-09-24 — Sharpe 1.44, monotonicity +0.042

The strongest construction found anywhere in this exercise, laddered against a control that
is genuinely flat and coverage-matched. `group_rank(cap, sector)` = **+0.091 / −0.119**.

| decile | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| raw | **−10.41%** | +1.95% | +1.96% | +0.91% | +1.49% | +1.59% | +3.68% | +0.90% | +1.80% | +1.15% |
| smoothed 10d | **−12.05%** | +0.20% | +1.60% | +2.29% | +2.20% | +3.77% | +0.97% | +1.50% | +0.51% | −0.96% |

| construction | monotonicity | middle-8 | d10−d1 | distinct | excess over control |
|---|---|---|---|---|---|
| `news_impact_RAW` | **+0.042** | **−0.214** | +11.56pp | 10/10 | **−0.049** |
| `news_impact_smoothed_10d` | **+0.006** | −0.095 | +11.09pp | 10/10 | **−0.085** |
| `news_impact_DESIZED` (within cap quintiles) | **+0.055** | −0.119 | +11.74pp | 10/10 | **−0.036** |

**Sharpe 1.44 and monotonicity +0.042.** All three ladders are flat, all three middle-eights
are **negative**, and all three sit **below a flat control**.

The whole +11.6pp spread is decile 1. The signal finds the worst-news names — they lose
10–12% a year — and orders the remaining ninety per cent of the cross-section not at all.
That is content at one extreme with noise everywhere else: the shape CLAUDE.md records Step
296 finding six times over, and the reason monotonicity rather than Sharpe is the deciding
statistic here.

**Three things this result settles.**

1. **The scoreboard would have called this the find of the project.** Sharpe 1.44
   market-neutral clears BRAIN's 1.25 bar. The ladder says short-side concentration. This is
   the cleanest demonstration in the whole exercise of why guardrail 1 exists, and it was
   produced by following it rather than by arguing for it.
2. **Smoothing made it worse, not better** (+0.042 → +0.006). The turnover problem and the
   skill problem were never trading off against each other — there was no skill to preserve.
   The earlier worry that "slowing it down might kill the signal" had the causality backwards.
3. **De-sizing changed nothing** (+0.042 → +0.055), which is what de-sizing a signal with no
   ordering should do. The bucket method is fine; there was simply nothing to remove.

Separately, the arithmetic already closed submission for this field before the ladder ran:
`fitness = Sharpe × sqrt(|returns| / max(turnover, 0.125))` = 1.44 × sqrt(0.046/1.067) =
**0.30** against a bar of 1.0. Reaching 1.0 at that Sharpe and return needs turnover ≤ 9.5%
against an actual 107%.

# 1.0 was not tested, and cannot be tested on BRAIN

Asked directly on 2026-09-24 whether the legacy 1.0 ETF strategies had been tried here. They
had not, and three structural reasons make it impossible rather than merely undone:

1. **Wrong instruments.** 1.0 trades ETFs — SPY, QQQ, IWM, TLT, GLD, HYG, LQD, EEM, USO and
   the XL* sector set. BRAIN's USA/TOP3000 is individual common stock, and all fourteen
   datasets visible to this account are `instrumentType: EQUITY`.
2. **Wrong strategy shape.** 1.0 is a time-series regime allocator — rotate defensive when the
   macro regime turns. BRAIN's engine converts a *cross-sectional score over ~3,000 names*
   into a dollar-neutral long-short book. It has no cash position and no timing dimension, so
   "go defensive" has no expression in the language.
3. **The deciding measurement is unconstructible there.** Ten deciles over 12–35 ETFs gives
   one to three assets per decile. Step 246 already found 35 multi-asset ETFs supply
   **4.16 effective assets**, so the breadth is not there either.

Testing 1.0 adversarially is a real and open piece of work. It needs a multi-asset backtester
on our own data, not BRAIN. Logged as queue item **S16**.

# Final tally

**Fifteen constructions. Four datasets. Twelve signal families. Zero with cross-sectional
skill above a coverage-matched no-skill control.**

| family group | best monotonicity | its control | cleared? |
|---|---|---|---|
| fundamentals (coverage 0.5) | `sales_yield` +0.988 | `assets` +0.867 | marginal, and it is sales÷market-cap |
| news sentiment (coverage 1.0) | `news_impact` +0.055 | `cap` +0.091 | **no** |
| social sentiment (coverage 1.0) | Sharpe 0.38 best | `cap` +0.091 | not laddered — Sharpe below control |

BRAIN removed all four stated weaknesses of the Step 296–308 null at once — a panel we built,
a universe we restricted, a construction-error history, and our own backtester — and returned
the same answer on a ~6× cross-section. **The null replicates.** That was the declared expected
outcome and it is the valuable one.

Nothing was submitted. `submission_authorized` remains `false`. The account holds 0 submitted
alphas against ~200 simulations run, which is the correct number.
