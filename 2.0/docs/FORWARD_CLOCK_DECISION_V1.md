# Should the residual sleeve's forward clock start on 2026-09-11?

Written 2026-09-05, unprompted, because the question now has enough evidence attached that
leaving it implicit would be a choice in itself. This is a recommendation, not an action.
Nothing in `config/forward/` has been touched.

## What the evidence says

`sec_residual_controlled_sleeve_forward_v1` blends 80% cash-conversion control with 20%
residual momentum sleeve. Its first decision window opens 2026-09-11 21:00 UTC.

- The **control leg**, 80% of it, loses to an equal-weight portfolio of its own universe.
  17.72% against 26.55% under base and 7.74% against 13.74% under adverse, at 50bps
  (Step 222). It loses in both halves of the window, wins 19 of 98 rolling 52-week
  comparisons, and the result survives removing cost (which explains about a fifth of the
  gap) and size (which explains none). It holds at every coverage bar tested, including
  admitting every decision (Steps 223, 227).
- The **residual leg**, 20% of it, beats its own universe by roughly 47 points and carries
  the composite past its blended benchmark (Steps 224, 225). It cannot be validated outside
  its selection window: 48% of the early broad universe is permanently unpriceable, so the
  earliest decision clearing a 90% coverage bar is 2022-07-01 (Step 230).

So the composite is four fifths a leg that underperforms its universe and one fifth a leg
that cannot be checked.

## Three options, and why the obvious one is a trap

**Change the protocol before Friday.** Reweight toward the residual sleeve, or replace the
control leg. This is the intuitive response and it is the one to be most suspicious of. The
equal-weight comparison is new information, but it comes from the same 2023-2026 window every
other belief here came from. Rebuilding a protocol around a finding from the selection window
is fitting the protocol to the sample, and it restarts the clock at zero anyway. If the
control leg's failure also appears over 2012-2022, that is a different matter, because that
window played no part in choosing anything.

**Abandon the clock.** Defensible on opportunity cost: a year spent measuring something there
is good reason to think is broken. But it assumes the in-sample finding transfers, which is
precisely the assumption this project's record says not to make. The whole reason forward
evidence exists is that in-sample beliefs are unreliable, and that cuts in both directions.

**Start it as declared, and record the benchmark alongside.** The protocol governs what the
strategy decides; it says nothing about what else may be measured next to it. Running an
equal-weight portfolio of the same universe forward, on the same schedule and cost, in a
separate record that touches nothing frozen, costs nothing and answers the question this
document raises in the same 52 weeks rather than in a further 52 after a restart.

## Recommendation

Start the clock as declared, and stand up a parallel forward benchmark record.

The argument is not that the composite is good. It is that the alternative is to act on an
in-sample result to modify a protocol whose entire purpose is to be immune to in-sample
results. If the control leg is dead, a forward clock with a benchmark attached will show it,
and will show it with evidence nobody can re-look at. If it is not dead, the same record will
show that too, and the equal-weight finding will have been a regime artifact.

The cost of being wrong in this direction is a year of measurement. The cost of being wrong in
the other direction -- rebuilding the protocol around a number from the selection window -- is
that the clock restarts and the new construction carries an overfitting risk nobody can
quantify.

## What would change this recommendation

- The 2012-2022 out-of-sample run showing the control leg losing there too. That is
  out-of-sample evidence and it is not subject to the objection above. The pre-declared
  reading in `full_history_interpretation_registry_v1` already says this should stop the
  clock rather than adjust it.
- ~~Discovering that the composite's in-sample edge over its blended benchmark, 1.68 points
  under base, is inside the noise of a twelve-decision record.~~ **Tested 2026-09-05 (Step 231).
  It is.** A moving-block bootstrap puts the probability that the composite's mean weekly
  excess is positive at 0.533 under base and 0.650 under adverse: a coin flip and a weak lean.
  The control leg's deficit against its own universe, by contrast, comes in at 0.076, so the
  negative result is far better established than the positive one. The composite does not beat
  its benchmark; it fails to lose by a distinguishable amount. The recommendation above is
  unchanged, because it never rested on the composite having a demonstrated edge, but nobody
  should start this clock believing the in-sample record shows one.

## What is explicitly not recommended

Reweighting the sleeves. The residual leg looks better, and choosing 0.2 or any other number
after observing that is a parameter fitted to this sample. It would be a new trial, it would
need declaring as one, and it would restart the clock.

## Decision, 2026-09-05

The owner chose: **start the clock as declared.** No constant in
`config/forward/sec_residual_controlled_sleeve_forward_v1.json` changes. The first
decision is 2026-09-11, the 2026-08-28 and 2026-09-04 windows having lapsed and being
unbackfillable. The equal-weight benchmark record starts the same evening.
`docs/FORWARD_CLOCK_RUNBOOK_V1.md` has the sequence.

## A finding that arrived after the decision and changes what the clock measures

Preparing the packet assembler surfaced something neither this memo nor the protocol
knew, and it is worse than anything above. See Step 234 for the full numbers.

`robust_rank` winsorises at the 5th and 95th percentiles and then ranks the *clipped*
values, so every issuer above the 95th percentile receives the identical average rank.
`residual_momentum` is a single such rank, so its top block is one flat tie. At the
twentieth-best score the median tie pool is **59 names competing for 20 slots**, and
`top_weights` resolves it with `sort_values(["score", "cik10"])` -- lowest CIK first,
which is to say oldest SEC registrant first.

The residual leg's book is therefore an arbitrary draw. Against 200 random tie-breaks
of the same signal, the declared book sits at the **99th percentile** on recent 52-week
CAGR (78.3% against a random median of 29.7%) and the 97th on full-sample Sharpe. A
random draw shares only **34.3%** of its holdings. Holding the entire tie pool instead --
the tie-agnostic reading of the same signal -- gives 35.9% recent CAGR, close to the
random median and nowhere near the declared book.

The obvious question is whether registration age is a real factor. It is not. Inside
the tie pool, the rank correlation between CIK number and forward quarterly return
averages **+0.008** across thirteen quarters, and the lowest-20-CIK subset beat the pool
mean in **6 of 13** of them. The +2.8pp average excess comes almost entirely from two
quarters, 2025-07-01 and 2026-01-01.

This does not change the decision, for the same reason the memo gave originally:
re-specifying a tie-break after observing which one won is fitting the protocol to the
sample, and it would restart the clock. The declared rule is deterministic and causal --
CIK numbers are known at decision time -- so it is arbitrary, not invalid.

It does change what the forward record will mean, and that has to be said plainly.
The clock will test *this book*, not *residual momentum*. Anyone reading the result in
2027 must not conclude that the signal works, because two thirds of the holdings that
produced it were chosen by a sort key.

At the composite level the damage is smaller than at the sleeve level, because the
sleeve is only 20% of it: recent 52-week CAGR falls from 105.7% to 94.3% when the
residual leg is made tie-agnostic. Both remain below the control leg alone at 109.9%.
What survives the tie-break is the sleeve's *diversification* contribution, not its
return: full-sample Sharpe 1.792 declared against 1.753 tie-agnostic, both well above
the control's 1.531, and drawdown -18.7% and -19.6% against the control's -23.3%.

The cheap answer is the one already used for the equal-weight benchmark: record the
tie-agnostic pool book forward as a second measurement companion, touching nothing
frozen. In 52 weeks that answers whether the tie-break was luck, at no cost to the
clock. It is not built, because the owner has not asked for it.

## Correction, 2026-09-05: this memo overstates the case against the control leg

The memo above says the composite is "four fifths a leg that underperforms its universe"
and treats Step 222 as settled. Steps 239 to 242 show it is not.

- The panel that priced Step 222's benchmark carries 211 weekly returns above +100% and one
  infinite, across 130 issuers. No strategy holds any of them; every equal-weight benchmark
  holds all of them. The contamination sat only on the benchmark side, inflating it.
- Re-measured with both legs priced from one file on one convention, the gap is **1.09
  points**, not the 8.83 Step 222 reported. Of the difference, 0.74 points is the artifacts.
- A thirteen-week block bootstrap puts the probability the strategy beats its universe at
  **0.251**. That is a lean, not a result. Over the recent 52 weeks the control book is
  *ahead* by eleven points.

The decision to start the clock as declared is unchanged, because it never rested on the
control leg being good -- it rested on not rebuilding a protocol around in-sample results.
But nobody should read this memo as saying the control leg is known to be broken. It is not
known to be anything, which is the reason for the clock.
