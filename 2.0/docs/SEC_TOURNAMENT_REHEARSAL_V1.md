# SEC tournament synthetic rehearsal v1

## Purpose

This rehearsal proves that the broad-universe tournament machinery can execute
without reading incomplete real-universe returns. Its generated performance
numbers are synthetic test fixtures and have no investment meaning.

## Completed workflow

1. Generated 260 deterministic weekly observations for 48 fictional issuers.
2. Created 15 quarterly point-in-time decision panels containing 720 rows.
3. Enforced `available_at <= decision_at` and a 13-week target horizon no longer
   than the 13-week decision interval.
4. Exercised residual momentum, trend quality, quality momentum, event
   conditioning, adaptive concentration, nested walk-forward ML, buffered
   holding/exit rules, and a causal strategy allocator.
5. Applied 50/100/200-bps costs, zero/one/two-week execution delays, cash and
   total-loss missing-price policies, issuer contribution checks, sector
   removal, rolling 26/52-week comparisons, and 4/13-week block bootstraps.
6. Verified outer-test targets cannot change nested ML predictions.
7. Sealed the configuration, schema, engine, runner, and tests by SHA-256.

## Gate boundary

The rehearsal does not materialize the real broad panel, calculate a real
strategy return, select a candidate, authorize promotion, or enable live
trading. After the independent research gate opens, the real panel must conform
to the sealed schema and receive its own immutable source manifest before the
frozen eight-family evaluation can run.

## Verification

Twenty-one focused and compatibility tests pass in the pinned Python 3.12.13,
NumPy 2.5.1, and pandas 3.0.5 runtime. The rehearsal exercised all eight
families, six nested ML test folds, and verified all persisted artifact hashes.
