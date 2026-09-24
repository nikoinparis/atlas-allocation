# Testing 1.0 properly — the ETF allocator, put through the machinery it was never put through

*Written 2026-09-24, queue item S16, at the owner's explicit instruction. CLAUDE.md §4 marks
`1.0/` as historical reference not to be touched without one.*

**No backtest was re-run. Every number below is 1.0's own recorded output**, re-read against a
baseline its reports print but do not test against. That is the whole finding: the
instrumentation was there and the conclusions did not follow from it.

---

## What 1.0 is, and why BRAIN could not test it

An ETF regime allocator over 7 sleeves — SPY, QQQ, IWM, TLT, GLD, HYG, LQD, EEM, USO and the
XL* sector set. 1109 weekly decisions, 2005-01-14 → 2026-04-10. Monthly rebalance, long-only,
max sleeve weight 0.45, 5bp half-spread default, 156-week training window.

It cannot be tested on WorldQuant BRAIN, for three structural reasons rather than any lack of
effort: BRAIN's TOP3000 is individual common stock and every dataset visible to the account is
`instrumentType: EQUITY`; BRAIN converts a cross-sectional score into a dollar-neutral
long-short book with no cash position and no timing dimension, so "go defensive" has no
expression; and ten deciles over 12–35 ETFs gives one to three assets per decile, so
monotonicity — the statistic that decides everything in 2.0 — cannot be constructed. Step 246
already put 35 multi-asset ETFs at 4.16 effective assets.

## The search size is written into the filenames

**32 allocator variants**, each with a benchmark report, each named "improved":

```
phase2 phase3 phase4 phase4b phase6 phase7 phaseaaa phasebb phasebbb phaseccc phasedd
phaseddd phaseeee phaseff phasefff phaseggg phasehh phaseii phasemm phasenn phaseoo
phaseooo6 phasepp phasess phasesss3 phasett phaseuu phasevv phaseww phasexx phaseyy phasezz
```

Every one of the 32 benchmark reports concludes that the extra complexity is justified.

## The baseline that was printed and not tested against

Each report prints six internal allocators, including **HRP** (hierarchical risk parity,
single-linkage + bisection) — a standard, parameter-free allocator. Then it asks:

> Does the candidate beat **Equal Weight** … **Inverse Vol** … **production**?
> **Is the extra complexity justified?** YES — candidate Sharpe exceeds the best simple
> baseline (Equal Weight / Inverse Vol) by more than 0.05.

**"Best simple baseline" is defined as Equal Weight or Inverse Vol, excluding the HRP row on
the line above.** HRP is the strongest of the three, and it is the one omitted from the test.

HRP, on the identical 7-sleeve panel: **Sharpe 0.9251, annual return 4.19%, max drawdown
−10.86%, average turnover 0.0062.**

### Applying the reports' own bar, with HRP included

| test | result |
|---|---|
| candidate Sharpe > HRP Sharpe | 17 / 32 — a coin flip |
| **candidate beats HRP by more than 0.05 — the reports' own stated bar** | **0 / 32** |
| candidate max drawdown **worse** than HRP | **31 / 32** |
| candidate turnover vs HRP | **9× to 18×** |

**Zero of thirty-two variants pass the project's own criterion once the baseline it printed is
included.** The single variant with a better drawdown than HRP is
`phasebb_w1cap_060_hrp_7sleeve` — the one built on HRP.

## The defensive claim is inverted

1.0 was described as the more defensive, longer-term body of work. Its own numbers say the
opposite: **31 of 32 variants carry a deeper maximum drawdown than a parameter-free baseline.**
HRP draws down 10.86%; the candidates run 11.6% to 15.3%.

## The extra return is bought entirely with extra risk

If a candidate were a better *allocator*, its return multiple over HRP would exceed its
volatility multiple. Across all 32:

**mean(return multiple − volatility multiple) = −0.023, sd 0.066.**

Indistinguishable from zero. The candidates are HRP at roughly **1.7–1.9× exposure**. Leverage
would reproduce them at one-thirteenth the turnover — and CLAUDE.md §2 already states the
consequence: levering a correlated signal amplifies both its return and its fragility, and adds
no breadth. Thirty-two phases of allocator work amount to a risk-budget choice.

## Statistically, the best variant is noise

Best of the 32 is `phase3_high_breadth_calm_us_offense` at Sharpe 0.9664, **+0.0413 over HRP**.

Over 21.3 years the standard error of an annualised Sharpe (Lo 2002, iid approximation) is
**0.2623**. So the best variant's edge is **0.16 standard errors**, for a single comparison,
before any correction for having made 32 of them.

For reference, 32 *independent* draws under a null of no edge would be expected to throw up a
best of about +0.69 Sharpe from selection alone. The 32 variants here are heavily nested — many
share numbers to three decimals — so their effective count is far below 32 and that +0.69 is an
overstatement of the correction needed. The honest statement does not depend on it:
**+0.0413 at 0.16 standard errors is not evidence of anything.**

## At the project's own default cost, 31 of 32 lose to HRP

This is the sharpest result, and it comes from 1.0's own backtest realism audits rather than
from the benchmarks.

| test, at the project default 5bp half-spread | result |
|---|---|
| candidate Sharpe **below** HRP's 0.9251 | **31 / 32** |
| candidate Sharpe below HRP with a **1-week** rebalance delay | **30 / 30** |

At 5bp the candidates run Sharpe 0.775–0.836 (the sole exception being `phasebb` at 0.9623).
Add a one-week rebalance delay and they fall to **0.64–0.73**, which is 0.20–0.28 Sharpe
*below* a parameter-free baseline. A single week of execution delay costs more than the entire
claimed edge.

## Three sensitivity grids claim more levels than they print

Every one of the 32 realism audits states:

> Half-spread varied across {0, 5, 10, 25, 50} bps.

**Three of 32 print the 25bp and 50bp rows. Twenty-nine print only 0, 5 and 10** — and then
conclude *"candidate survives doubled-cost scenario"*, where doubled means 10bp. The same
pattern holds for rebalance delay (`{0, 1, 5}` weeks claimed, 5 weeks printed in three) and
turnover threshold (`{0, 0.5%, 1%}` claimed, 1% rarely printed).

The harsher level is absent in each case, and it matters: `phasebb`, which *does* print the full
grid, falls from Sharpe **0.9623 at 5bp to 0.6713 at 50bp**. HRP's cost drag is 0.0001 annually
at 5bp against the candidates' 0.0007–0.0011, so at 50bp the gap widens rather than narrows.
This does not satisfy CLAUDE.md §7, which asks for 0/10/50/100bps as a matter of course.

## 1.0 flagged its own chronic failure mode 31 times and shipped anyway

**31 of 32 benchmark reports contain a "Hidden concentration flagged" section.** Their own
risk-contribution analysis:

| sleeve | dollar weight | risk contribution |
|---|---|---|
| `taa_10m_sma` | 11.5% | **56.0%** |
| `dual_momentum_topn` | 9.2% | **44.0%** |
| `composite_regime_conditioned` | 25.1% | 41.0% |

Two sleeves at roughly a tenth of the book each carry the entire risk budget between them.
CLAUDE.md §5 names single-name concentration as "this project's most chronic, recurring failure
mode." Here it is measured, printed, labelled *hidden concentration flagged*, and then followed
by a verdict that the complexity is justified.

## What 1.0 did well, stated plainly

The instrumentation is genuinely good and better than most of what 2.0 had at the same stage.
1.0 built cost sensitivity, rebalance-delay sensitivity, turnover-threshold sensitivity,
risk-contribution decomposition, six internal baseline allocators, and a concentration detector
— and it ran all of them. It also recorded its own warnings honestly (no ETF volume data, flat
half-spread as a slippage proxy, 5-week delay as an extreme proxy).

**The failure is not measurement. It is that the conclusions ignore the measurements.** The HRP
row is printed and excluded from the baseline test. The concentration is detected and
overridden. The harsher cost levels are declared run and not shown. Every individual verdict is
locally defensible and the aggregate is a 32-variant search that never cleared a parameter-free
allocator.

## Verdict

**1.0's allocator work does not survive its own criteria.** Zero of 32 variants beat HRP by the
0.05 Sharpe the reports themselves require; 31 of 32 are worse on drawdown; 31 of 32 are below
HRP at the default 5bp cost; 30 of 30 are below it with one week of delay; the extra return is
proportional to extra risk; the best result is 0.16 standard errors from noise; and the
concentration warning fires in 31 of 32 reports.

The defensible conclusion from the same evidence is that **HRP on the 7-sleeve panel is the
right answer** — Sharpe 0.9251, drawdown −10.86%, turnover 0.0062 — and that 32 phases of
regime-conditioning added turnover, drawdown and complexity without adding risk-adjusted
return. If more return is wanted, the honest route is explicit leverage on HRP, priced and
disclosed as such.

**Nothing here is promoted, and nothing is traded.** This is a negative result on a legacy body
of work, preserved per CLAUDE.md §9 because a failed reproduction is as valuable a record as a
passing one.

## What this does not test

- **The regime classifier itself.** Whether the macro regime calls have skill is a separate
  question from whether the allocator built on them beats HRP. No regime-conditional
  performance split (2008–09, 2020, 2022 separately) exists in any of the 32 benchmark reports,
  and CLAUDE.md §6 requires one. That is the obvious next piece of work.
- **A shuffled-label placebo.** The decisive test for a regime allocator — feed the classifier
  randomised regime labels and confirm performance collapses — was never run and cannot be
  reconstructed from the reports. It needs the code path re-executed.
- **Out-of-sample.** The 1109-week panel is the window every one of the 32 variants was selected
  on. There is no untouched forward record.
