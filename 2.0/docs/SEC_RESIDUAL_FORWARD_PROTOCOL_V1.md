# SEC Residual Controlled Sleeve — Frozen Forward Protocol V1

## Purpose

This protocol observes the post-selection 80% SEC cash-conversion control / 20%
residual-momentum sleeve without changing its rules after seeing new returns.
It tracks the exact unlevered candidate and the 1.25x research stress at both 5%
and 8% annual financing. It never places orders.

## Frozen boundary

- Historical research is visible through **August 21, 2026** and never counts
  as forward evidence.
- The first eligible decision is **August 28, 2026**.
- The first eligible realization is **September 4, 2026**.
- The required clock is **52 untouched weekly realizations**.
- A missed decision or realization window is permanently missing; a later data
  vintage cannot backfill it.
- Any change to the signal, sleeve weights, leverage, costs, financing, timing,
  data rules, or pinned code creates a new protocol and restarts the clock.

## Weekly evidence

Each decision packet must arrive within the Friday 21:00 UTC weekly snapshot
window and contain the point-in-time control and residual holdings, the source
data cutoff, an immutable source-manifest hash, and its own packet hash. The
source cutoff cannot be later than the decision date.

Each realization packet must arrive within its own Friday window and contain
security-level total returns for every held security. The recorder calculates
both sleeve returns, charges 50 basis points per unit of turnover, applies the
fixed 80/20 blend, and derives the two 1.25x paths. Missing held-security prices
fail closed rather than being silently treated as zero.

Decision and observation ledgers are independently append-only and
hash-chained. Duplicate, out-of-order, pre-boundary, changed, unhashed, and late
records are rejected.

## Interpretation

The historical 147.98% recent CAGR is a selection-contaminated research result,
not the expected forward return. The forward tracker starts at 0/52. Completion
of 52 observations permits a separately predeclared statistical review; it does
not automatically promote the strategy or authorize live trading.

## Controlling artifacts

- `config/forward/sec_residual_controlled_sleeve_forward_v1.json`
- `scripts/record_sec_residual_controlled_sleeve_forward_v1.py`
- `evidence/forward_sec_residual_controlled_sleeve_v1/anchor.json`
- `evidence/forward_sec_residual_controlled_sleeve_v1/decisions.jsonl`
- `evidence/forward_sec_residual_controlled_sleeve_v1/observations.jsonl`
- `evidence/forward_sec_residual_controlled_sleeve_v1/status.json`
- `tests/test_sec_residual_forward_recorder_v1.py`
