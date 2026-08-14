# Canonical Behavioral Probes: bt and FlashAlpha

Probe date: 2026-08-08

Both pinned repositories were installed in disposable Podman named volumes.
The platform-owned probes ran with networking disabled, a read-only container
root, dropped capabilities, bounded resources, and no host-directory mounts.

## Platform reference behavior

Portfolio Optimizer 2.0 now owns deterministic contracts for:

- pre-trade buying-power and position rejection;
- partial fills and remaining order quantity;
- duplicate-fill and overfill prevention;
- cash, position, fee, and marked-equity reconciliation;
- next-bar-open execution with explicit slippage;
- rejection of missing, crossed, non-positive, and non-finite quotes.

These contracts are the oracle. Third-party results cannot overwrite them.

## bt at `bd5650ad213760907ec38311c5c9468819084196`

Observed strengths:

- commission hooks reduce portfolio value as expected;
- rebalancing preserves non-negative cash in the canonical probe;
- positions and transactions are recorded.

Critical boundary:

- a signal evaluated from the 2024-02-02 close transacted on 2024-02-02 at
  that same 110.00 close. Therefore raw `bt` does not enforce our next-bar
  rule and fails the canonical lookahead boundary.

Decision: retain `bt` as a conditional research/backtest adapter. Every signal
must be lagged by the platform, and all simulated execution and accounting
must ultimately reconcile through the platform-owned engine. `bt` is not an
execution broker and supplies no native rejection or partial-fill lifecycle.

## FlashAlpha fill simulator at `e75838081d4e1adc3579fca834bdefe60fb25547`

Observed strengths:

- valid crosses fill at the posted limit;
- non-crosses do not fill;
- wide and crossed quotes are rejected;
- the loop wrapper's default start offset prevents same-bar fills.

Critical defect:

- a `NaN` bid on one leg passes the raw quote filter, produces a fill, and
  emits non-finite fill diagnostics. This matches the repository's own
  documented expected-failure test.

Decision: retain as a conditional fill-model component only behind the
platform quote/output guard. The wrapper rejects non-finite inputs before the
library is called and rejects non-finite diagnostics afterward. Fees, partial
fills, order state, cash, and positions remain platform responsibilities.

## Integration status

Neither repository is approved as an autonomous engine. The guarded adapters
are approved for further historical-fixture evaluation, where they will be
compared against canonical bars, options chains, fees, and adverse execution
conditions.
