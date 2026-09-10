# CLAUDE.md — Operating Rules for This Project

This file governs how Claude (in any surface — Claude Code, Cowork, chat) must behave
when working on the Portfolio Optimizer project. Read this before touching strategy
code, running a backtest, or evaluating a claim of "improved returns." It applies to
both `1.0/` and `2.0/`, and it does not replace `2.0/README.md`'s operating principles
or `PROJECT_HISTORY.md` — it enforces them.

## 0. The one thing to internalize before anything else

The owner of this project is not short on ideas or on backtested returns that look
good. Over 176+ recorded research steps, this project has generated dozens of
"headline" strategies with trailing-1-year CAGRs from 100% to 337%. **Every single one
of them died under falsification** — leave-one-company-out, bootstrap significance
after multiple-testing correction, causal (past-only) re-selection, or an out-of-sample
window. Zero strategies have been promoted. Zero dollars have traded live.

That is not a failure of the project. That *is* the project working correctly. A quant
firm's research process is supposed to kill 95%+ of ideas that look good in a backtest,
because most of what looks good in a backtest is noise, selection bias, or concentration
risk wearing a Sharpe ratio as a costume. Your job here is to be the skeptic that keeps
killing bad ideas — including your own, including ones the user is excited about,
including ones that already technically "passed" a test.

If you find yourself about to write "this improves returns" or "this strategy works,"
stop and ask: passed which gates, on what data, with what multiple-testing correction,
compared to what null, and has it accumulated any genuinely untouched forward weeks?
If the answer to any of those is "no" or "not yet," the correct sentence is "this is a
research candidate that passed X but has not yet Y" — not "this works."

## 1. Non-negotiable process rules

1. **Never let a claim of improved performance stand without an adversarial pass.**
   Before reporting any backtested improvement as real, you must attempt to break it:
   leave-one-holding-out, parameter-neighborhood sensitivity, a placebo/random-signal
   control, and — if it involved any selection over more than a handful of trials — a
   multiple-testing-corrected significance test (Bonferroni/FDR at minimum; report the
   *actual* number of trials searched across the whole session that led here, not just
   the final batch).
2. **Every backtest must be causal.** No feature, label, universe-membership fact,
   corporate action, or parameter choice may be computed using information that would
   not have been known at decision time. When in doubt, write a prefix-invariance test
   (perturb only future data and confirm historical outputs are unchanged) rather than
   trusting a code read — this project has twice found real lookahead bugs (`bt`'s
   same-bar execution, GGG's covariance lookahead) that "the code looks causal" missed.
3. **Multiple testing compounds across the whole project, not just the current batch.**
   If you run N parameter/feature configurations today, that N stacks on top of every
   config already searched in earlier sessions on the same data. Treat any "still
   standing" candidate as the survivor of an enormous cumulative search, and say so.
4. **Point-in-time or it doesn't count.** Universe membership, fundamentals, prices,
   and corporate actions must reflect what was knowable as of the decision date.
   Survivorship-safe means built from historical filer/membership rosters, not a
   present-day ticker list filtered backward.
5. **Single-name concentration is this project's most chronic, recurring failure mode.**
   Micron, GitLab, Qualys, Rackspace, ProFrac, Palo Alto Networks, and 10x Genomics have
   each independently "explained" a supposed improvement that evaporated once removed.
   Any new candidate must report leave-one-out sensitivity by default, not on request.
6. **Regime-check everything.** Most of the strongest recent headline numbers come from
   a 2023–2026 window dominated by one bull/tech-momentum regime. Report performance
   across 2005–2026 full history, 2008–2009, 2020, and the recent window separately.
   A strategy that only works in one regime is a regime bet, not an edge, and should be
   labeled as such.
7. **Costs are not optional.** Report 0, 10, 50, and 100 bps (and borrow costs for any
   short position) as a matter of course. A strategy that only survives at 0–10bps is
   not a strategy.
8. **No strategy gets called "promoted" or "ready" without:** a benchmark comparison,
   cost stress, walk-forward/causal validation, an untouched forward-observation record
   (not backfilled, not restarted after a bad stretch), regime testing, multiple-testing
   correction, and a robustness/falsification pass — matching the gate list already in
   `2.0/README.md`. If any gate is missing, say which one, plainly.
9. **Preserve negative results.** A rejected strategy, a failed reproduction, or a bug
   found in a third-party repo is exactly as valuable a record as a passing one — write
   it into `PROJECT_HISTORY.md` and the relevant registry, don't just delete the branch.
10. **Update `PROJECT_HISTORY.md` as you go**, in the same append-only, dated style
    already used, including honest failures. Never record planned work as complete.

## 2. What "help me get more return without overfitting" actually means here

**Updated 2026-09-10 after Step 296. The previous version of this section named breadth as
the binding constraint and directed roughly fifty steps of work at raising it. That was
half right, and the missing half is the more important one.**

The Fundamental Law of Active Management (Grinold & Kahn) still frames it:

    IR ≈ IC × sqrt(BR)

where IC is the skill of a signal and BR is *breadth*, the number of genuinely independent
bets per year. **Both terms have now been measured in this project, and both are near
zero — but they are not equally binding.**

**Breadth is low and has proven unraisable here.** Batch 03 measured the trend/momentum
family at pairwise correlations of 0.84–0.98 and ≈1.15 effective independent strategies.
Step 292 measured the current four dashboard books at **1.690 effective bets of four**,
correlations 0.52–0.77, once a date-labelling offset was corrected. Step 246 found 35
multi-asset ETFs give 4.16 effective assets; Step 285 found 20 crypto assets give 3.09.
Every liquid domain collapses, because liquid assets share macro factors.

**IC is indistinguishable from zero, and that is the binding term.** Step 296 measured all
thirteen signals on disk three beta-neutral ways at the cadence the books actually
rebalance. **None clears Bonferroni. More decisively, none orders its deciles** —
monotonicity sits within ±0.17 of zero for every signal, and six show a positive
information coefficient alongside a *negative* top-minus-bottom decile spread, which is
what noise looks like when measured twice.

This explains the rest of the record at once. Step 245's transfer coefficient of −103.
Step 289's nought-of-six out-of-sample failure. Step 295, where neutralising the market
took cash conversion from 16.65% to 1.59% — ninety per cent of the return was beta. **The
top-N books were never winning on ranking ability. They won on market beta and on holding
a few names that went up.**

**The consequence for how to prioritise.** `IR = IC × sqrt(BR)` is a product. An IC
indistinguishable from zero yields an IR indistinguishable from zero *at any breadth*, so
breadth work cannot pay until there is skill to multiply. Two experiments confirm this
directly: Step 277 added XLE, which raised effective bets from 2.00 to 2.88 and bought
0.021 of Sharpe because its own Sharpe was 0.568; Step 279 closed breadth repair by
construction as noise. Steps 293 and 295 built a working market-neutral structure —
delivering betas of −0.009 and +0.007 — and found nothing to drive it.

**Default posture, replacing the previous breadth-first rule: demand evidence of
cross-sectional skill BEFORE anything is built around a signal.** The screen is cheap and
takes an afternoon: rank IC at the intended horizon, top-minus-bottom decile spread, and
**decile monotonicity**, all on a window the signal was not chosen on. Monotonicity is the
one that matters most and the one this project went 296 steps without measuring — a signal
whose deciles do not order themselves has no cross-sectional content, whatever its top
decile did. Several of the fifteen closed families would have been closed in an afternoon
rather than a session by running it first.

Breadth still matters and low-correlation sources are still preferred over retuned
variants of an existing family — that part of the old guidance stands. It is simply not
where the binding constraint currently is, and a proposal that raises breadth without
evidence of skill should be described as unlikely to move anything.

**One honest limit on Step 296, which must travel with the finding.** The in-sample window
has 13–14 quarterly decisions, and detecting a true IC of 0.03 at that dispersion needs
roughly a hundred decisions — about twenty-five years. The significance null is therefore
weak evidence. The monotonicity result is the robust part, because it measures the *shape*
of the relationship rather than its significance and would show at any sample size.

Leverage is not an exception to any of this: levering an existing correlated signal
amplifies both its return and its fragility (the project's own 2.00x leverage path carried
a CSCV-estimated 37% overfitting probability and 85.9% deflated-Sharpe confidence — not
compelling, and it doesn't add breadth, only variance). Levering a signal with no
cross-sectional skill multiplies a number that is already zero.

## 3. Using the reference books

The `Quant Study` folder on the user's device contains reference books relevant to this
project (Grinold & Kahn's *Advances in Active Portfolio Management*, López de Prado's
*Advances in Financial Machine Learning*, Tsay's *Analysis of Financial Time Series*,
Hull's *Options, Futures, and Other Derivatives*, Chan's *Quantitative Trading*, the
Shreve stochastic calculus volumes, and Joshi's *Concepts and Practice of Mathematical
Finance*, plus pure-math references). When proposing new research directions, ground
them in these where relevant and cite the concept/chapter, e.g. "Grinold & Kahn's
breadth/IC framework implies..." or "López de Prado's meta-labeling (AFML ch. 3)
suggests...". Don't cite a technique from memory as if it were verified against the
book text unless you've actually read the relevant section this session — say plainly
when a recommendation is from general knowledge of the book versus a direct read.

Techniques already implemented here that came from this literature (purged/embargoed
walk-forward CV, deflated Sharpe, CSCV, block bootstrap) are López de Prado-style methods
executed unusually well for a non-institutional project — don't re-suggest them as new
ideas; instead look for what from that same body of work *hasn't* been applied yet
(meta-labeling on existing signals, feature importance via MDA/MDI, fractional
differentiation for stationarity without full information loss, structural-break tests).

## 3b. Keep the research queue current — this is not optional

`2.0/docs/RESEARCH_QUEUE.md` is the living, ranked list of what to do next. It exists because
three of six strategies the owner proposed on 2026-09-06 had already been tested and rejected in
`PROJECT_HISTORY.md` and nobody remembered. It fails in both directions if it is not maintained:
good ideas get lost, and dead ideas get retried.

**Whenever you have a new idea worth trying, write it into the queue in the same turn you have
it** — even half-formed, even if you are not going to act on it. A line there costs nothing; a
lost idea costs a year. Rank it S/A/B/C, say whether it needs free or paid data, and name the
blocker, because "we forgot" is almost always "nobody wrote down what was stopping it."

**Whenever you finish an idea, delete it from the queue and move a one-line verdict into its
`Closed` table**, with the step number. The full record stays in `PROJECT_HISTORY.md`; the queue
carries just enough to stop the idea being proposed again.

**Read the queue before proposing anything new**, and read the `Closed` table first.

Sources of new ideas that have actually produced untried items here: this file's own section 3
(four López de Prado techniques were named there and sat unattempted for 272 steps), the OSAP
correlation screen's most-orthogonal band, and the "blocked on" and "should be continued" lines
buried in `PROJECT_HISTORY.md`.

## 4. Where things live

- `PROJECT_HISTORY.md` (repo root and mirrored in `2.0/`) — the full chronological
  record. Read relevant sections before proposing anything that might have already
  been tried.
- `2.0/docs/` — architecture, protocols, and per-program design docs, including:
  - `STRATEGY_TRACK_RECORD_AUDIT_V1.md` — audit of what's been tried and whether it
    was implemented/tested correctly, with a short list of hard lessons.
  - `UPGRADE_CANDIDATES_V1.md` — concrete, book-grounded, not-yet-tried directions,
    ranked by whether they plausibly add breadth vs. just retune existing signals.
- `2.0/research_registry/` — machine-readable status of every evaluated strategy/repo.
- `2.0/config/strategies/` and `2.0/config/forward/` — frozen manifests and forward-test
  locks; never edit a frozen candidate's config in place, version it.
- `1.0/` — the legacy completed ETF research app; treat as historical reference, not a
  place to add new work without explicit instruction.

## 5. Tone with the user

Be direct about dead ends. The user has explicitly asked for real double-checking and
has a project history that shows they've already survived a lot of "this looks great"
moments turning into rejections — don't soften that pattern to make a session feel more
productive. A session where you correctly kill three bad ideas and clearly explain why
is more valuable to this project than one that ships an exciting-looking backtest that
hasn't been stress-tested yet.
