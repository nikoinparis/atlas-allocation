# Strategy Track Record Audit V1

Purpose: a single reader-friendly audit of everything this project has tried,
organized by whether it was implemented/tested correctly and why it was rejected or
retained. This is a distillation of `PROJECT_HISTORY.md` (176+ steps, 7,230 lines) —
read that file for full detail and exact numbers; this doc is the "so what" layer,
current as of 2026-08-24.

The project's own governing line, worth repeating here because it is the correct
standard to hold every row in this table to:

> Passing a software test means only that the tested behavior worked. It never means a
> strategy is profitable, safe in every market, or ready for real money.

## Bottom line

- **Strategies proven durably profitable and approved for real money: 0.**
- **Live trading: never enabled, at any point in 176+ steps.**
- Every strategy that has ever looked good on a "recent" or "trailing" window has, so
  far, either (a) failed a leave-one-holding-out test, (b) failed a multiple-testing-
  corrected significance test, (c) failed under causal (past-only) re-selection, or
  (d) turned out to be mostly a single-issuer or single-regime bet.
- The one substantive, still-standing structural finding is: **this project's roughly
  13 nominally "diverse" trend/momentum candidates have an effective independent
  strategy count of ≈1.15** (Batch 03, pairwise correlations 0.84–0.98). That is the
  real bottleneck, not signal quality — see `UPGRADE_CANDIDATES_V1.md` for what that
  implies.

## Was it implemented correctly? — process-level assessment

This is the audit the user specifically asked for: not "did it make money" but "was
the methodology sound." Overall verdict: **yes, unusually so for a solo/small-team
project**, with a short list of things to watch.

**Correctly implemented and genuinely rigorous:**
- Causal, embargoed, purged walk-forward ML (features strictly pre-decision, one-week
  embargo between training labels and outer test, deterministic label-shuffle and
  random-feature negative controls run alongside every real fit). This matches
  López de Prado-style purged K-fold + embargo methodology, not a naive train/test
  split.
- Multiple-testing correction computed against the actual number of trials searched
  (288, 576, 805, etc.), not just the finalists — and a real bug in this machinery
  (a 2,000-sample bootstrap that made a 5% Bonferroni gate mathematically unpassable
  across 288 trials) was found and fixed rather than silently worked around.
- Point-in-time data discipline: content-hashed immutable data vintages, revision
  auditing bucketed by economic materiality, and — the single largest and most
  important correction in the whole history — discovering that a "current survivor"
  universe would have silently dropped 63.1% of the 2012 eligible universe and
  rebuilding from actual historical SEC filer rosters (6,094 unique CIKs) instead.
- Leave-one-company-out / issuer-dependence testing, applied by default, which is the
  single most effective bias-catcher on record here — it caught Micron supplying
  67.63% of one candidate's entire positive return, and similar single-name blowups
  in at least six other candidates.
- Prefix-invariance / lookahead detectors that go beyond code review: this is how the
  project caught a real embedded lookahead bug in the GGG allocator (it used the
  current week's realized return inside the covariance matrix used to pick that same
  week's weights) that an exact mechanical-equivalence check had already missed.
  **Lesson worth keeping visible: reproducing a legacy strategy exactly is not proof
  it's causal.** Always run a dedicated future-perturbation test on anything ported
  or reconstructed, even from your own prior code.
- Third-party repository code has never been trusted at face value. Every "simple
  indicator" repo evaluated (pairs trading, MACD, Awesome Oscillator, Heikin-Ashi,
  Parabolic SAR, Bollinger pattern, RSI pattern, Shooting Star) turned out to contain
  an actual implementation bug — lookahead, inverted logic, non-portable constants, or
  a display bug — that had to be found before any economic evaluation could even
  start. Treat this as a standing prior: **assume catalog/GitHub strategy code is
  buggy until independently verified**, not just "unvalidated."

**Weaker than the headline label suggests — worth double-checking going forward:**
- "Robustness" gates have repeatedly been passed by families that are internally
  highly correlated (the ≈1.15 effective-strategies finding). A reader skimming for
  "N/N passed" headlines without checking correlation/overlap numbers will overstate
  how much diversification actually exists.
- Forward clocks have, on at least two occasions, been started on candidates the
  project's own notes call selection-contaminated (a breadth-ceiling candidate that
  failed causal-selection replication, and a 60/40 blend where both the blend weight
  and one component were chosen from the same data being "forward" tested). This is
  disclosed every time, not hidden — but it means "has a forward clock running" must
  never be read as "cleared for promotion." As of the last recorded step, **every
  forward clock in the project sits at 0 observed weeks.**
- Headline return figures computed on weekly-aggregated accounting have repeatedly
  come in higher than the same strategy's exact daily-close reconstruction (105.10%→
  102.49% in one case, 185.77%→174.97% in another). Treat any weekly-only headline
  number in the registry as an upper bound until daily-reconciled.
- The free/rate-limited delisted-price rescue process (Tiingo, 24 symbols/hour) hits a
  95%+ coverage floor, but that's a floor on completeness, not evidence the missing
  names are missing at random — bankrupt/delisted names are plausibly the hardest to
  find prices for, which could leave residual survivorship bias even after the gate
  numerically passes. The "-100% adverse case" sensitivity partially guards this; most
  reported headlines use the cash-neutral base case instead, which doesn't.
- Almost every strong "recent" result (100%+ trailing-1-year CAGR territory) is
  measured over 2023–2026, a single strong US tech/momentum bull regime. The project
  is honest about this in places, but the sheer number of eye-catching headlines from
  that one window should make you treat the whole late-history return-chasing branch
  as regime-specific until proven otherwise across a genuinely different regime.
- No result in the project's history has ever been checked against a dataset outside
  US equities/ETFs drawn from this one historical realization. All confidence is
  internal (bootstrap, rolling windows, leave-one-out) — there is no cross-market or
  cross-country confirmation anywhere in the record.

## What was tried, and why it was rejected (by family)

**Momentum / trend (v4 and successors).** The only family with a long, mostly-intact
track record: `composite_trend_quality_refined` (v4) is the frozen benchmark at 9.91%
annual return / 0.754 Sharpe / -26.25% max drawdown, independently re-derived from raw
signals to 8.64e-12 floating error (no formula bugs). Six separate rounds of trying to
improve its *recent* returns (momentum overlays, sleeve recency tilts, cash
redeployment, execution-frequency changes) all failed a predeclared ≥0.50pp improvement
gate. Read as: **this specific signal family is exhausted along the axes tried so
far.** Not a bug — a real result.

**Mean-reversion, defensive, carry-proxy (new families, Batches 04–05).** Defensive
family is the only one of the three that passed a 576-trial Bonferroni-corrected gate
(4.00% return / 0.518 Sharpe / -23.02% DD at 100bps) and is retained as
`provisional_robust_new_family` — still non-final, no forward evidence yet.
Mean-reversion had a -45.34% drawdown and is explicitly `provisional_fragile`. Carry's
own observed Sharpe (0.652) did not beat its own null estimate (0.665) — statistically
indistinguishable from noise, not a real signal.

**Cross-sectional ML on ETF universe.** Nested walk-forward ML lost to the frozen
portfolio (6.62% vs 7.59% at 10bps). Pre-selected factor screening on `ml-quant-trading`
passed only 2 of 6 candidates after Bonferroni correction, and both collapsed under
50–100bps cost as direct portfolio weights (turnover ~23x/year). As an ML feature
augmentation it improved point estimates on a small 14-ETF universe but reversed
entirely (underperformed baseline) on the full 35-ETF universe — track formally closed
per a predeclared stopping rule. **No ML alpha has been accepted anywhere in the
project to date.**

**Portfolio libraries (cvxportfolio, skfolio, Riskfolio-Lib, PyPortfolioOpt,
vectorbt).** All either supplied mechanical construction with no alpha, or failed
qualification outright (Riskfolio-Lib: all 7 bundled tests failed against a pinned
commit due to breaking API changes; skfolio: 2/94 native-ARM test failures disqualified
the full library under a predeclared "every test must pass" rule; vectorbt: license-
restricted, accelerator only). A narrowly-scoped skfolio drawdown-risk component beat
minimum-variance by 0.003 Sharpe — statistically indistinguishable, not promoted.

**Classic technical-indicator repos (`je-suis-tm/quant-trading` family).** Pairs
trading, MACD, Awesome Oscillator, Heikin-Ashi, Parabolic SAR, Bollinger pattern, RSI
pattern, Shooting Star — every one contained a real implementation bug in the source,
and every one was rejected on economics even after an independently-rebuilt, corrected
version was tested (mostly: profitable-looking at 10bps, destroyed by realistic 50bps
costs and high turnover, or -90%+ drawdowns).

**SEC fundamentals — cash-conversion / growth (the largest program, Steps 93–176).**
The most productive branch to date, but also the one with the most repeatedly-rejected
"almost there" candidates. The durable finding is a cash-conversion factor sleeve
(base case: 31.70% full-period CAGR / 0.948 Sharpe / -36.50% DD; adverse case: 16.69% /
0.597 / -45.60%) that survives leave-one-company-out (worst single name, Palo Alto
Networks, only 14.08pp) — this is the strongest genuinely-diversified result in the
project. A "breadth-20" construction on top of it reached 102.49% (daily-reconciled)
trailing-1yr CAGR and holds the incumbent forward-clock slot. Everything built on top
of it since — insider-cluster overlays, valuation/sales-yield overlays, PEAD-style
earnings-drift overlays, dispersion controllers, cluster-aware cash sleeves, leverage
studies up to 2.00x — has been rejected, in every case because either (a) a single
issuer explained most or all of the claimed improvement, or (b) bootstrap confidence
fell short of the 95% bar even after reaching triple-digit headline CAGRs. The final,
full-universe "real tournament" (40,284 issuer-decision rows, 6,094 CIKs) found **no
family qualified** — the best (residual momentum) trailed the existing cash-conversion
control and failed familywise bootstrap; the ML family lost 19.18% with a -42.64%
drawdown.

**Genuine cross-sectional value.** Still blocked — point-in-time market-cap
normalization was only partially completed and the pipeline never cleared
falsification. This is an open thread, not a rejected result — see upgrade doc.

**Everything else evaluated from the 344-entry catalog** (execution engines, fill
simulators, data/storage tools, broker/venue connectors, portfolio-construction
libraries): mostly qualified only as guarded infrastructure adapters or rejected on
dependency/packaging failure, never as sources of alpha. See `2.0/research_registry/`
for the full per-entry status.

## Hard lessons worth restating to any new session

1. Exact reproduction of a legacy strategy is not proof it's causal — always run a
   dedicated future-perturbation/lookahead test, even on your own code.
2. A backtest's "recent" performance is worthless as evidence if the strategy or its
   blend weights were selected using knowledge of that same recent window.
3. If removing one holding meaningfully changes the headline number, the number was
   never really about the strategy.
4. A statistically significant result inside one batch can still be noise once you
   account for how many batches came before it on the same underlying data.
5. Weekly-aggregated backtest accounting tends to overstate returns versus daily —
   always sanity-check a weekly headline against a daily reconstruction before trusting
   it.
