# Upgrade Candidates V1 — Not Yet Tried, Ranked by Plausible Real Edge

Purpose: concrete next directions for raising *realistic, survivable* returns, grounded
in the reference books and in what `STRATEGY_TRACK_RECORD_AUDIT_V1.md` shows this
project has already exhausted. Read `CLAUDE.md` section 2 first — the framing here is
that this project's bottleneck is **breadth** (independent bets), not signal cleverness,
so ideas are ranked by whether they plausibly add a genuinely uncorrelated return
source versus whether they're just another way to retune the same signal family.

Citation note: ideas attributed to Grinold & Kahn and Chan below are drawn from general
knowledge of those books (I could not get the actual PDF/epub to stage into this
session this time — see the note at the end). Verify page/chapter references before
citing them as quotes in a doc that leaves this project. Hull, Tsay, López de Prado
(AFML), Shreve, and Joshi are cited only where the project history already shows their
methods in use, or flagged as "would need the book" where I'm not confident enough to
recommend specifics without reading it.

## Tier 1 — Plausibly adds real breadth (new, low-correlation return sources)

### 1. Deliberately size and track breadth using the Fundamental Law of Active Management
**Source:** Grinold & Kahn, *Advances in Active Portfolio Management* — the Fundamental
Law, IR ≈ IC × √(breadth), and the related transfer-coefficient/implementation-efficiency
framework.
**What to do:** Turn the informal Batch 03 finding (≈1.15 effective independent
strategies) into a standing metric computed and reported for every candidate portfolio,
not just once. For any new candidate, require reporting: its correlation to every
existing surviving candidate, its marginal contribution to portfolio breadth (not just
its own standalone Sharpe), and an explicit IC/IR decomposition where possible. Reject
"new" candidates whose marginal breadth contribution rounds to zero even if their
standalone backtest looks good — this is exactly the failure mode that already burned
the 10-candidate momentum family.
**Edge vs. overfit assessment:** This isn't a new return source by itself — it's a
governor that should be applied to *every other item in this doc* and every future
research batch. Low overfit risk because it's a measurement discipline, not a new
signal. High expected value because it directly targets the project's actual
bottleneck rather than another curve-fit.
**How to validate:** Compute pairwise correlation and holdings-overlap matrices as
already done in Batch 03, but make it a required gate (not an occasional audit) run
against the *entire* current candidate set for anything proposed going forward.

### 2. New asset classes with structurally different return drivers: futures/commodities trend, international equities, currencies
**Source:** Chan, *Quantitative Trading* — covers futures and currency strategy
construction, including why trend-following works differently (and historically with
lower correlation to equities) in futures than in single-stock momentum; general
diversification logic.
**What to do:** Rather than another equity/ETF variant, test a small, genuinely
different universe: a diversified futures trend sleeve (rates, commodities, currencies,
equity index futures as one instrument among many, not the whole book) or a developed-
market international equity sleeve. The point is not "more return," it's a return
stream whose drivers (global rate cycles, commodity supply shocks, currency carry) are
mechanically different from "US tech momentum in a 2023–2026 bull regime," which is
what most of this project's current headline numbers actually are.
**Edge vs. overfit assessment:** Genuinely promising *if* implemented with the same
discipline already used here (point-in-time data, realistic costs including futures
roll/margin mechanics, walk-forward, leave-one-instrument-out). Real risk: futures/FX
data quality and point-in-time discipline is a new engineering problem (margin,
contract rolls, different fee structures) — expect a multi-step data-provenance slog
similar to the SEC fundamentals program before any performance number can be trusted.
Don't let an early "great backtest" ship before that infrastructure work is done; that
exact sequencing mistake (return numbers before survivorship-safe data) is what
produced the Micron-driven false positive earlier in this project.
**How to validate:** Same full gate stack as any other family (benchmark, cost stress,
walk-forward, multiple-testing correction, regime test across at least 2008, 2020, and
one non-bull period specific to that asset class, leave-one-instrument-out).

### 3. Volatility risk premium / options overlay (selling short-dated equity index volatility)
**Source:** Would need Hull, *Options, Futures, and Other Derivatives* for correct
implementation (Greeks, margin/assignment mechanics, realistic vol-surface modeling) —
flagging this as directionally sound from general market knowledge, but do not
implement pricing/hedging logic without reading the relevant Hull chapters first (options
strategies are exactly the kind of thing where "looks fine in a naive backtest" hides
real tail risk).
**What to do:** The historical volatility risk premium (implied vol > subsequently
realized vol, on average) is one of the better-documented sources of return that is
mechanically uncorrelated with equity momentum/value/fundamentals factors — it's a
distinct risk (short volatility/tail risk) being harvested, not a directional equity
bet. Candidate structure: systematically selling short-dated index puts or covered
calls with strict position sizing and an explicit tail-risk budget.
**Edge vs. overfit assessment:** Real historical premium exists, but the payoff
structure is famously "picking up nickels in front of a steamroller" — the tail-risk
event is the whole ballgame and is exactly the kind of thing a backtest under-samples
(2008 and 2020 vol spikes need to be in the test window, not excluded as outliers).
Do not size this without an explicit worst-case-week stress test analogous to the
leverage shock arithmetic already done for the 2.00x leverage candidate. This is not a
"maybe" for standard practice here — a Hull-literate implementation with margin/
assignment mechanics done correctly is mandatory before any capital-sizing decision.
**How to validate:** Explicit tail scenario analysis (single-week and single-month
shocks at least as severe as Feb 2018 and Mar 2020 vol spikes), margin/assignment
mechanics correctly modeled, position sizing capped by a pre-declared max-loss-per-week
budget, not just a Sharpe/CAGR backtest.

### 4. Genuine cross-sectional value factor — finish the blocked work
**Source:** N/A — this is a project-internal open thread, not a new book idea, but
worth re-prioritizing given the breadth argument above: value has historically shown
low-to-negative correlation with momentum, which is exactly the kind of breadth this
project needs and hasn't gotten from any new family tried so far.
**What to do:** Finish the point-in-time market-cap normalization work that was
"partially completed" (per `PROJECT_HISTORY.md`) and re-run the cross-sectional value
pipeline through the same falsification gauntlet as everything else. This is lower
engineering cost than a new asset class since the SEC point-in-time infrastructure
already exists.
**Edge vs. overfit assessment:** Value/momentum's historical low correlation is one of
the more robust cross-sectional findings in the empirical asset-pricing literature —
worth finishing for that reason. But this project has already seen one growth/cash-
conversion SEC-fundamentals branch produce a dozen-plus false positives before finding
one durable-looking result — expect the same slog for value, not a quick win.
**How to validate:** Identical gate stack to the cash-conversion sleeve, including
leave-one-company-out (given the recurring single-issuer failure mode) before any
headline number is trusted.

## Tier 2 — Improves realized return per unit of existing risk, without claiming new alpha (lower overfit risk, addresses the concentration problem directly)

### 5. Kelly-criterion-adjacent, risk-budgeted position sizing instead of equal/top-N weighting
**Source:** Chan, *Quantitative Trading* covers fractional-Kelly position sizing as a
standard risk-management practice; Grinold & Kahn's transfer-coefficient framework
covers the general point that a portfolio's *realized* IR is systematically lower than
a signal's theoretical IR once real-world constraints (position limits, turnover caps,
concentration) are imposed — implementation efficiency is a separate lever from signal
quality.
**What to do:** The project's single most chronic failure mode is one name (Micron,
GitLab, Qualys, Rackspace, ProFrac, ...) explaining most of a claimed improvement. That
is a portfolio-construction problem, not a signal problem — equal-weighting a fixed
top-N SEC-fundamentals list structurally concentrates risk in whichever name has the
most extreme factor score. A covariance- and confidence-aware position-sizing scheme
(fractional-Kelly or a risk-parity-style budget capped per name and per sector) applied
to the *existing, already-validated* cash-conversion signal could reduce single-name
blowup risk without needing any new alpha source at all.
**Edge vs. overfit assessment:** Lower risk than searching for new signals, because
it's applied to a signal that has already survived falsification — the question is
purely "can we harvest the same edge with less concentration risk," not "is there an
edge." Genuine overfit risk still exists if position-sizing parameters are tuned on the
same historical window used to validate the underlying signal — treat sizing-parameter
search with the same multiple-testing discipline as everything else.
**How to validate:** Compare risk-adjusted return (not raw CAGR) of the resized
portfolio vs. the existing equal-weight breadth-20 leader, across cost levels and
regimes, with leave-one-name-out sensitivity reported for the resized version too (the
goal is to show the *sensitivity itself* is smaller, not just that the headline
number is similar or better).

### 6. Meta-labeling on existing signals, rather than searching for new ones
**Source:** López de Prado, *Advances in Financial Machine Learning* — meta-labeling
(ch. 3 in the published book, from memory — verify): use a primary model/signal to
decide direction/side (already have several: momentum, cash-conversion), then train a
secondary model only to decide bet *size or whether to take the bet at all*, using
purely a precision-improving objective rather than trying to invent new directional
alpha. This is a different technique from the ML overlays already tried and rejected
here (which tried to add or replace direction), and different from the ensemble/
confidence work already done (Batches 18–20) — the distinguishing feature of proper
meta-labeling is a genuinely separate train/serve step focused only on filtering false
positives of an already-fixed primary signal, evaluated on precision/F1 rather than
return directly, before ever touching a backtest.
**Edge vs. overfit assessment:** This project's ML confidence-overlay work (Batches
18–20) is close to this idea already and was rejected — worth explicitly checking
whether those batches implemented true meta-labeling (secondary model trained on
primary-model correctness as the label) or something adjacent (confidence tiers on the
same signal) before concluding this is fully explored. If it's genuinely untried,
overfit risk is moderate — same discipline (embargo, purge, negative controls) already
used elsewhere in this project should transfer directly.
**How to validate:** Full existing ML protocol gate stack (`ml_protocol.py`,
`ml_confidence.py`) already in the codebase — this is an application of infrastructure
that already exists, not new infrastructure.

### 7. Explicit regime-conditioning using a formal state model rather than ad hoc filters
**Source:** Tsay, *Analysis of Financial Time Series* — regime-switching /
Markov-switching models, GARCH-family volatility modeling, and structural-break
detection are covered in depth; the project's existing regime/state ML work (Layer 2B,
`composite_regime_conditioned`) is informal by comparison.
**What to do:** Given the project's own finding that most recent headline returns are
concentrated in one bull regime, a formally validated regime classifier (rather than
retroactively noticing "this only worked because of 2023–2026") could be used
defensively — to size down or flag reliance on regime rather than to chase more return.
This is explicitly a risk-management upgrade, not a return-chasing one.
**Edge vs. overfit assessment:** Moderate-to-low overfit risk if used defensively (to
cut exposure/flag fragility) rather than offensively (to try to predict regime
transitions and trade around them, which is a much harder, more overfit-prone
problem the project has arguably already tried and lost at with the rejected state-
transition ML work in the GGG pipeline).
**How to validate:** Test whether a formal regime classifier, applied only to *scale*
existing candidate exposure (not to pick new candidates), improves the worst-regime
drawdown without materially hurting full-history return — report separately from any
attempt to use it as a new alpha source.

## Tier 3 — Needs a missing book before it should be attempted at all

- **Options/volatility strategies (item 3 above)** — needs Hull read properly before
  any Greeks/margin/assignment logic is written.
- **Any strategy using stochastic calculus directly (e.g., pricing exotic derivatives,
  building a volatility surface model)** — needs Shreve I & II and Joshi's *Concepts
  and Practice of Mathematical Finance* read first; not recommended as a near-term
  priority given the project's equity/ETF/fundamentals focus, but flagged since the
  books are in the reference library.
- **Advanced time-series techniques from Tsay beyond basic regime-switching** (e.g.,
  multivariate volatility models, high-frequency-data-specific methods) — worth a
  deeper read once the futures/international data infrastructure (item 2) exists,
  since that's where these techniques are most applicable.

## What I could not verify this session

I was not able to get the Grinold & Kahn PDF or the Chan epub to actually transfer into
this session's workspace despite the staging tool reporting success three times each —
looks like an infrastructure hiccup with those two specific files (possibly the long,
special-character filenames). The ideas above attributed to those books are from
general knowledge, not a verbatim read this session. Before treating any citation above
as authoritative (e.g., in a doc that leaves this project, or before writing production
code from a formula stated here), either re-attempt the transfer or open the relevant
chapter directly and confirm.
