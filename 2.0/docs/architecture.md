# Architecture

## Boundary rule

Third-party repositories are research inputs or replaceable adapters. They do
not own canonical portfolio state and cannot submit simulated or future live
orders without passing the platform-owned risk gate.

The platform-owned execution oracle in `src/systematic_trader/execution.py`
defines cash, position, fee, order-state, fill, lookahead, and quote-validity
behavior. Guarded adapters may call third-party components only after inputs
pass these contracts, and their outputs are validated again before accounting.

## Planned flow

1. Data adapters normalize historical or live market observations.
2. A versioned data store preserves raw and adjusted values with provenance.
3. Strategy plug-ins convert available observations into timestamped signals.
4. Portfolio construction converts signals into proposed target positions.
5. The independent risk engine approves, clips, or rejects proposals.
6. Historical replay or the live paper broker simulates order execution.
7. The accounting ledger reconciles orders, fills, cash, positions, and costs.
8. Experiment storage records results, configuration, code, and data versions.
9. The dashboard compares strategies with benchmarks and promotion gates.

## Implemented data boundary

`src/systematic_trader/data_vintage.py` now implements the versioned data-store
boundary described above. Snapshots are immutable and content-addressed, payload
hashes are checked before reads, simulation-time selection enforces when a
snapshot became known, and production capability claims require normalized
point-in-time schemas. The legacy 1.0 data hub is quarantined as research-only.

`src/systematic_trader/weekly_data.py` converts a selected normalized daily
snapshot into completed Friday observations using the last available trading
day in each week. The free research pipeline then recalculates the five signals,
portfolio weights, next-week returns, and an inactive paper target. Live calendar
logic does not force a partial sample endpoint to masquerade as month-end.

## Implemented research laboratory

`src/systematic_trader/research_lab.py` gives every experiment a deterministic
identity derived from its complete strategy specification and immutable data
snapshot. `src/systematic_trader/portfolio_construction.py` currently compares
equal weight, score weight, inverse volatility, and score-plus-inverse-volatility
allocations behind one point-in-time interface. Missing strategy slots flow to
the defensive asset or explicit cash rather than being silently redistributed.

Research Batch 01 applies chronological training/evaluation folds and retains
every tested configuration in a JSON Lines registry. These folds are correctly
called retrospective out-of-sample evidence: the ordering is causal, but all of
the history was visible when the batch was designed. An untouched result can
only begin after the relevant frozen strategy version exists.

The v4 benchmark is frozen in
`config/strategies/composite_trend_quality_refined_free_snapshot_v4.json`. Its
manifest pins code, universe, source snapshot, derived data, parameters, and
the start of its forward clock. Any material mutation must use a new version.

## Candidate lifecycle

`research_registry/strategy_candidates.json` separates experiment rankings from
strategy approval. The shortlist keeps one qualifying configuration per signal
recipe, the frozen benchmark, and distinct configurations selected by causal
walk-forward folds. Entries retain their selection reason, current evidence,
passed gates, and missing gates.

Robustness labels are deliberately provisional. Batch 02 can mark a candidate
`provisional_robust` or `provisional_fragile`, but neither state is final or
approved for trading. Final promotion remains impossible without the declared
multiple-testing, ensemble, historical-data, and untouched-forward evidence.

Batch 03 supplies the first multiple-testing and ensemble-dependence layer.
Strategy weights are combined before portfolio accounting so shared trades are
netted and turnover is charged once at the resulting portfolio. Return
correlation, weighted holdings overlap, connected correlation clusters, and
leave-one-out marginal contribution expose duplicated sleeves.

The multiple-testing diagnostic centers each candidate's returns under a
zero-mean null, resamples 13-week circular blocks to retain serial dependence,
and applies Bonferroni adjustment for all 288 configurations originally tested.
Passing this diagnostic does not establish independence or future performance;
it only rejects the tested zero-mean explanation at the declared retrospective
threshold.

## Implemented non-momentum research

`src/systematic_trader/non_momentum_signals.py` adds short-horizon reversal,
moving-average deviation reversal, RSI reversal, low volatility, drawdown
resilience, gated defensive quality, and trailing cash-distribution yield. Every
observed score is shifted one week before it becomes tradable. Mean-reversion
specifications can use weekly decisions through an explicit strategy frequency;
existing monthly strategy identities remain unchanged.

Distribution yield divides cash distributions over the preceding year by the
unadjusted close available on the decision week. The formula uses only events
dated on or before the decision, but the entire source history was acquired in
one 2026 Yahoo vintage. The platform therefore records the signal as event-date
causal research, not archived point-in-time carry data.

Batch 05 applies the same promotion gates to the three new-family leaders. Each
leader is tested over a fixed nine-member parameter neighborhood, transaction
costs through 100 bps, and regimes defined only from trailing SPY observations.
Its 50,000-sample circular block bootstrap corrects for all 576 strategy
configurations searched across Batches 01 and 04. Only defensive passed every
gate. Carry and mean reversion remain recorded as fragile rather than being
discarded. Robust-family portfolio diagnostics combine target weights before
accounting so offsetting trades are netted and costs are charged once.

## Implemented strategy-family allocation

`src/systematic_trader/strategy_allocation.py` allocates across validated
strategy sleeves using covariance data known by each decision date. Batch 06
uses monthly decisions, a fixed 104-week covariance window, 52-week minimum,
25% shrinkage toward the diagonal, long-only weights, and an 80% sleeve cap.
Combined non-cash holdings are capped at 35%; excess concentration flows to
explicit cash rather than being redistributed into another risky asset.

Minimum variance uses the closed-form two-asset solution. With exactly two
sleeves, maximum diversification equals inverse-volatility allocation and HRP
reduces to inverse-variance allocation without a meaningful clustering tree.
The platform records these equivalences explicitly. Volatility targeting is
unlevered, so it can reduce exposure but cannot borrow to reach its target.
All strategies are aggregated into underlying target weights before one shared
accounting pass, preventing duplicated costs on offsetting trades.

Batch 07 adds a deterministic equal-weight fallback when covariance inputs are
missing, malformed, negative-variance, or non-finite. Zero variance is handled
as a valid degenerate estimate and also resolves to equal weight. The selected
minimum-variance rules are pinned in
`config/portfolios/covariance_minimum_variance_v1.json`, including code hashes,
source snapshot, concentration rules, and forward boundary. Frozen means the
rules may now accumulate untouched evidence; it does not mean final approval.

## Implemented forward-evidence boundary

`src/systematic_trader/forward_evidence.py` validates two hash-chained JSON
Lines logs. The first saves portfolio targets inside a strict post-close weekly
snapshot window. The second uses a later eligible snapshot to realize the next
week's return and references the immutable decision-record hash. This separation
prevents a later download from retroactively inventing a historical target.

`config/forward/covariance_minimum_variance_v1.json` pins the portfolio manifest,
constituent specifications, calculation dependencies, 50 bps cost model,
decision and realization dates, and the rule that missed windows cannot be
backfilled. A pre-freeze August 7 target is stored only as the turnover anchor
and never counts toward forward performance. The recorder has no broker or
execution capability.

`scripts/run_guarded_weekly_forward_cycle.py` is the outer orchestration
boundary. It obtains a process lock, enforces the Friday 21:00 UTC cutoff,
permits only one completed acquisition per decision week by default, launches
the pinned rootless Podman collector, verifies snapshot freshness and timing,
and hands only the resulting snapshot ID to the frozen recorder. A successful
download cannot bypass the recorder's later eligibility checks. The cycle
stores command-output hashes rather than treating console text as evidence and
never connects to a broker.

## Planned interfaces

- `DataAdapter`
- `SignalModel`
- `PortfolioModel`
- `RiskRule`
- `ExecutionModel`
- `Metric`
- `Strategy`

Each experiment must be reproducible from a pinned source revision, immutable
configuration, and identified data snapshot.
