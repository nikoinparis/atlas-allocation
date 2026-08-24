# Guarded real SEC tournament v2

## Outcome

The independent gate opened at 95.0071% minimum decision-date price coverage,
100% Company Facts coverage, a complete 446/446 provider queue, and zero
unresolved early delistings. The hash-verified real panel was materialized and
the one-shot tournament completed. None of the eight families passed every
frozen gate against both benchmarks, so no winner or replacement was selected.

## Panel materialization

The v2 contract preserves decision, execution, label-end, and feature-
availability timestamps. Execution occurs no earlier than one full week after
the decision. A missing validated price remains an explicit null with the
frozen base-cash/adverse-total-loss policy; it is never silently removed or
substituted with a current ticker.

After authorization, the materializer requires a hash-verified causal input
package containing `causal_features.csv.gz`, `weekly_adjusted_prices.csv.gz`,
and `benchmark_weekly_returns.csv.gz`. It combines those sources with the
audited point-in-time membership, creates 13-week sector-relative ML labels,
and writes a separately hashed panel, weekly-return matrix, benchmark matrix,
and manifest.

## Tournament execution

The final entry point requires four independent conditions:

1. The frozen return-improvement configuration matches its preserved copy.
2. The broad research gate explicitly authorizes backtests.
3. Every materialized-panel artifact matches its manifest hash.
4. All twelve configuration, schema, engine, runner, and test files match the
   pre-result execution seal.

It then evaluates all eight workstreams against both frozen benchmarks. The
screen includes trailing-52-week and full-period returns, Sharpe, drawdown,
50/100/200-bps costs, one/two-week delays, adverse missing prices, issuer
contribution, sector removal, rolling outperformance, two block-bootstrap
horizons, and an eight-family multiplicity adjustment. A family qualifies only
if it passes against both benchmarks. The final result is one-shot: an existing
result cannot be overwritten.

## Current state

The input package contains 40,284 issuer-decision rows, 3,253 priced issuers,
14 decisions, and 7,609 hashed source-inventory records. Two pre-result
real-data compatibility defects were repaired before any performance artifact
was written: missing-score incumbents now exit buffered holdings, and serialized
decision/execution timestamps are normalized to UTC before merges. The repairs,
their predecessor seal, and 17 passing focused tests are recorded in the final
12-file execution seal.

Residual momentum was the strongest rejected family: 101.20% trailing-52-week
CAGR, 2.323 Sharpe, and -18.54% drawdown after 50 bps. It beat the ETF benchmark
on recent and full CAGR but trailed the SEC cash-conversion benchmark's 109.90%
recent CAGR and had zero familywise-adjusted bootstrap probability. All other
families also failed. Strategy promotion and live trading remain disabled.
