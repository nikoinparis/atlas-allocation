# S17 — the 1.0 regime classifier: the calls were right and the trade was wrong

*Written 2026-09-24, at the owner's explicit instruction. Step 318 (S16) falsified 1.0's
allocator from its own recorded output. This tests the separate claim underneath it: do the
regime calls carry information?*

---

## First, a reproducibility finding that constrains everything else

**`1.0/data/` does not exist and was never committed to git.** Not gitignored — absent from the
repository's entire history.

Every one of 1.0's scripts depends on it. `build_macro_regime_classifier_v3.py` dies immediately
on a missing `data/01_data_hub/weekly_prices.csv`; `allocator_benchmark_audit.py` needs
`data/05_layer3_portfolio_construction/portfolio_version_returns_*.csv`.

**So none of 1.0's 32 allocator benchmarks, 35 realism audits or 3 regime classifier versions
can be re-executed or verified.** The shuffled-label placebo S17 asked for cannot be run on
1.0's own data, and that is not a matter of effort.

What follows is therefore a **reconstruction of the documented design on public data**, testing
the thesis rather than reproducing the numbers. Stated plainly so it is never cited as a
reproduction.

## The classifier's own recorded history, before any test

From `build_macro_regime_classifier_v3.py`'s docstring:

- **V1** — "RESEARCH-ONLY: promising dev spread, **holdout failed**, 4 FRED series timed out (incl. NFCI)"
- **V2** — "RESEARCH-ONLY: NFCI still missing, **PC2 became semantically unreliable** (captured Fed policy rather than financial conditions). Best signal: dev Sharpe 0.599"
- **V3** — financial conditions is a "**clearly labeled proxy — NOT true NFCI**"

All three marked research-only, no promotion. And one line deserves separate attention:

> **Hard requirement: 2008, March 2020, and late 2022 must classify as stress/tightening.**

A classifier *required* to reproduce known crises cannot then be credited for identifying them.
Its performance in exactly those windows is circular by construction.

## The reconstruction, and two declared departures

Weekly, 2005–2026, SPY as offense and TLT (or cash) as defense, strictly next-week execution.
Stress = V3's `financial_conditions_proxy`: VIX, HYG/LQD credit momentum, SPY drawdown and
realised volatility, each **expanding-window** z-scored so no future data enters a past decision.

1. **Market-observable inputs only.** V3's growth factor uses FRED INDPRO, which is *revised* —
   using today's vintage for a 2008 decision is lookahead. Market data is not revised.
2. **Two assets, not seven sleeves.** 1.0's panel is gone, so this is the thesis in its simplest
   faithful form, not its full machinery.

## The placebo, with the bar declared before running

Regime labels are persistent, so an iid shuffle would destroy their run-length structure and
make the placebo trade far more often than the real thing — flattering the real labels for a
reason unrelated to information. **The shuffle here permutes whole regime episodes**, so the
placebo has the identical number and length of episodes and differs only in *when* they fall.

**Bar: real-label Sharpe must exceed the 95th percentile of the shuffled distribution.**

### Result — refuted at every persistence setting

| smoothing | episodes | median length | real Sharpe | shuffled mean | shuffled 95th | p-value | verdict |
|---|---|---|---|---|---|---|---|
| 1w | 135 | 3w | +0.2796 | +0.3909 | +0.5959 | 0.83 | refuted |
| 4w | 63 | 13w | +0.3976 | +0.3847 | +0.5842 | 0.43 | refuted |
| 8w | 48 | 15w | +0.3805 | +0.3807 | +0.5970 | 0.47 | refuted |
| 13w | 36 | 20w | +0.4001 | +0.3854 | +0.5925 | 0.41 | refuted |
| 26w | 24 | 46w | +0.3396 | +0.3784 | +0.5786 | 0.60 | refuted |

The thesis was given five chances, spanning 3-week to 46-week regimes, so it is not being
refuted on a strawman of a trigger-happy classifier. **At every setting the real labels land
essentially at the median of their own placebo.** At the finest setting 82% of random shuffles
did better.

And every version loses to a benchmark that ignores the regime entirely:

| | Sharpe | annual return | max drawdown |
|---|---|---|---|
| **static 60/40 SPY/TLT** | **+0.5492** | +4.30% | −29.80% |
| always SPY | +0.4516 | +5.85% | −54.61% |
| regime → TLT | +0.4002 | +4.09% | −37.47% |
| always TLT | +0.1997 | +2.02% | −47.83% |

## The interesting part: the calls were right and the trade was wrong

CLAUDE.md §6 requires a regime split. **None of 1.0's 32 benchmark reports contains one.** Here
it is:

| window | regime→TLT | static 60/40 | SPY | % classified stress |
|---|---|---|---|---|
| **GFC 2007-10 → 2009-06** | **+15.05%** | −19.23% | −39.91% | 100.0% |
| COVID 2020-02 → 2020-06 | −2.47% | +5.35% | −1.95% | 84.1% |
| Rate shock 2022 | **−28.90%** | −20.55% | −16.97% | 86.7% |
| full sample | +290.32% | +359.35% | +599.52% | 32.9% |

**2008–09 is a genuine, large success** — the regime strategy made 15% while a static blend lost
19% and equities lost 40%. That is a 34-point swing and it is real.

**2020 and 2022 — the two crises after the design period — both failed.**

And the mechanism is precise. The classifier *did* identify all three as stress (100%, 84%,
87%). **The regime calls were correct. The response was wrong.** In 2008 the defensive asset
rallied hard; in 2022 the stock/bond hedge broke and TLT fell alongside equities, so going
defensive *into bonds* lost 28.9% against the static blend's 20.6%.

Knowing it is stressful does not tell you what to hold, and the thing that worked in the crisis
the model was built around was the thing that broke in the next one.

## Giving it the fairest possible shot: cash instead of bonds

1.0 had a cash unlock (`phase2_aggressive_neutral_cash_unlock`) and structural-defense sleeves,
so a TLT-only defense is harsher than its actual design. Testing cash as the defensive asset:

| variant | Sharpe | annual | max DD | 2008-09 | 2020 | 2022 |
|---|---|---|---|---|---|---|
| regime → TLT | +0.4002 | +4.09% | −37.47% | +15.05% | −2.47% | −28.90% |
| **regime → CASH** | **+0.4732** | +3.62% | **−17.39%** | +0.00% | −7.92% | **−8.58%** |
| static 60/40 | **+0.5492** | +4.30% | −29.80% | −19.23% | +5.35% | −20.55% |

Cash fixes 2022 (−8.58% against −28.90%) and delivers **the best maximum drawdown of anything
tested, −17.39%**. That is a real point in the thesis's favour and it should be said.

**But it still fails.** Placebo on this best form: real +0.4732, shuffled 95th +0.5685,
**p = 0.19**. And its drawdown advantage is bought by holding *less risk* — it sits in cash a
third of the time — not by timing. That is the same verdict S16 reached about the allocator:
**1.0's machinery makes risk-budget choices, not skilled ones.**

## Verdict

**S17 refutes the regime thesis as an allocation edge, and preserves one real finding inside
it.** Randomised labels do as well as the real ones at every persistence setting and in the
best cash form. A static 60/40 beats every regime variant on Sharpe. The drawdown advantage is
de-risking, not timing.

The finding worth keeping is that **the classifier identified all three crises correctly.** That
is not nothing — it is the part of 1.0 that could transfer. What it cannot do is tell you what
to own instead, and the 2008 answer was wrong by 2022.

**Nothing is promoted. Nothing is traded.** Preserved per CLAUDE.md §9.

## What this does not settle

- **1.0's actual seven-sleeve allocator was never run here** and cannot be — its data is gone.
  A richer defensive basket (gold, short duration, managed futures) might behave differently in
  2022, and that is untested rather than refuted.
- **The reconstruction uses a subset of V3's design** — market-observable inputs only, no growth
  factor. A classifier with the growth PCA might label differently, though V1's holdout failure
  and V2's semantic unreliability are 1.0's own recorded verdicts on that path.
- **Two assets, not seven sleeves.** The conclusion is about the thesis, not the implementation.
