# hftbacktest Platform Behavioral Probe

Generated: 2026-08-08

This probe evaluates execution-model behavior at pinned commit
`5f3ec40b2afb764e0fea112f941ed85523ef4e88`. It does not establish strategy
profitability, market realism, or fitness for live trading.

## Reproducibility boundary

- Repository dependencies were restored in a disposable Podman named volume.
- The generated `Cargo.lock` SHA-256 was
  `50ae0dda20bff6f4595568869f855e05846b2d7019c1cebf9ecb4622ac45a182`,
  matching the earlier pinned execution gate.
- The behavioral test ran offline, without host-directory mounts, using the
  recorded Rust 1.91.1 image.
- Result: 8/8 deterministic tests passed.

## Useful behavior confirmed

Six tests confirmed behavior that is useful for a platform execution model:

- configured order-entry, response, and rejection latency is time ordered;
- an order bus does not move a later append backward in time;
- the risk-adverse queue model requires trades to clear displayed quantity
  ahead before filling the order;
- consecutive trades produce two partial fills whose quantities reconcile to
  the submitted quantity;
- a cancellation processed before a later trade prevents a fill; and
- maker/taker fees, cash, position, and equity reconcile for a fixed round trip.

These are controlled invariants, not a claim that the simulated fills match a
particular real venue.

## Unsafe library boundaries confirmed

Two tests deliberately pass because they reproduce hazards that the application
must block:

- the direct state-accounting API accepts a fill larger than the order quantity;
- a non-finite fee configuration can propagate `NaN` into accounting state.

The component's own partial-fill exchange documentation also warns that a large
liquidity-taking order may be unrealistic because the simulated order book is
not depleted. Accordingly, the application must validate order-state
transitions, reject non-finite prices/quantities/fees, cap fills at remaining
quantity, and constrain simulated size against visible depth.

## Decision

Retain the backtest execution core as a **conditional sandbox candidate**. It
may proceed to recorded order-book replay only behind platform-owned validation
and reconciliation guards. Do not expose its raw accounting API to strategies,
and do not use the current probe as profitability evidence.

The subsequent small recorded-data chronology replay passed. See
`../hftbacktest_recorded_replay/report.md`. A larger continuous replay with an
initial snapshot is still required.

Machine-readable output is in `result.json`; the injected integration test is
in `scripts/probes/hftbacktest_platform_execution.rs`.
