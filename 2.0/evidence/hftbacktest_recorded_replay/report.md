# hftbacktest Recorded Order-Book Replay

Generated: 2026-08-08

This is an integration and data-ordering test at hftbacktest commit
`5f3ec40b2afb764e0fea112f941ed85523ef4e88`. It is not a strategy backtest or
profitability test.

## Recorded input and provenance

The fixture is transcribed from the BTCUSDT raw/normalized example in the
repository's pinned `docs/data.rst` file (Git blob
`63f28de18a085e6e7f315f06aca6b3768e135170`). The example records Binance
Futures events around exchange timestamp 2023-02-15 00:00:05 UTC.

- Original rows: 23 (19 L2 depth updates and 4 trades)
- Fixture SHA-256:
  `06d39b5cc2b7da645eab73a46e3a1ebd1c6d9968c6eb94749f06d8b0d3b33929`
- Feed-latency check: every exchange timestamp is no later than its local timestamp
- Source ordering: nondecreasing local timestamps
- Retained data defect: one exchange-timestamp inversion, matching the condition
  documented by the repository

The public excerpt is genuine recorded data, but it is not a complete trading
day or a complete initial order-book snapshot.

## Replay transformation

The application retained the 23 source rows unchanged. To meet hftbacktest's
dual-processor chronology, each of the 19 inverted depth rows was emitted once
for the exchange processor and once for the local processor. The four trades
could retain combined exchange/local flags. This produced 42 engine events.

The transformation is explicit and tested; it does not change prices,
quantities, or timestamps.

## Result

The replay ran offline in the pinned Rust 1.91.1 Podman environment. Its
generated dependency-lock SHA-256 matched the earlier gate.

| Check | Outcome |
|---|---:|
| Integration test | 1/1 passed |
| Source rows | 23 |
| Engine events after chronology split | 42 |
| Timestamp inversions detected/corrected | 1 |
| Market trades preserved | 4 |
| Reconstructed best bid | 22,183.4 × 0.014 |
| Reconstructed best ask | 22,194.3 × 0.270 |
| Safe hypothetical buy size | 0.100 accepted by platform guard |
| Oversized hypothetical buy size | 0.500 rejected by platform guard |
| Orders submitted / simulated fills | 0 / 0 |

No order was deliberately submitted: the excerpt is too short and lacks a
complete initial snapshot, so a fill/P&L claim would be misleading.

## Decision

The recorded-data ingestion and timestamp-ordering gate **passes**. Retain
hftbacktest as a guarded sandbox execution candidate. This advances it to a
larger replay containing an initial snapshot and a continuous L2/trade stream.

It is still not approved for portfolio simulation or paper trading. The next
gate must use a substantially larger, hash-pinned dataset and test a fixed
order schedule, cancellations, fills, fees, adverse latency, missing events,
and visible-depth limits. Platform guards for overfills and non-finite values
remain mandatory.

Machine-readable evidence is in `result.json`; the source fixture is in
`fixtures/btcusdt_docs_excerpt.csv`.
