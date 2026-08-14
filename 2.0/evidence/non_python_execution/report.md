# First Non-Python Execution Gate

Generated: 2026-08-08

Dependency acquisition ran with network access in disposable Podman named
volumes. Tests ran with networking disabled, a read-only container root,
dropped capabilities, no-new-privileges, bounded resources, no secrets, and no
host-directory mounts. Passing tests establish software behavior only—not
market-data correctness, profitability, or fitness for live trading.

## TradingView Screener API (`ast-0051`)

- Pinned commit: `b3db2009de8f85bc3ccdaa9d9365f1d7ddff55f1`
- `package-lock.json` SHA-256:
  `786121a19530badc3bbc875e17fb0f301dcc878b827dde774162953c03a26e8e`
- Dependency restoration: passed using `npm ci --ignore-scripts`.
- Offline unit result: 108/108 passed across seven files.
- Offline integration-style result: 34/34 passed across three files. These
  tests use controlled behavior and include a handled network-error path; they
  did not establish successful access to live TradingView data.

Decision: advance only as a candidate data/screening adapter. The next gate
must test timestamp semantics, point-in-time behavior, missing/stale data,
schema changes, retries/rate limits, and a vendor-independent recorded fixture.
It is not a strategy and has no profitability evidence.

## QUANTAXIS Rust package (`ast-0036`)

- Pinned commit: `a69e978a2e38d045a64c380cc3b5c9fa08fa4903`
- Root `Cargo.lock` SHA-256:
  `71a4654986a3a6794c4c625483924b259666f01935bb063c6cf2820014dcbc70`
- `qapro-rs/Cargo.lock` SHA-256:
  `f755b51403c37dac90dadb96a7a01559e34501a63388afc085f1e4765d598c91`

A modern Rust 1.85 diagnostic restored dependencies but compilation reached an
obsolete `packed_simd_2` syntax error. The repository's own pinned Dockerfile
declares Rust 1.55, so the platform built a matching legacy toolchain with its
native prerequisites and retried the locked graph. Rust 1.55 then failed
dependency selection: the pinned Polars Git revision advertises package version
`0.0.1`, while the graph requires exactly `0.19.1`.

Decision: do not import or silently patch the full Rust component. Retain
QUANTAXIS for source-level idea review and separately evaluate narrowly scoped
algorithms or its Python layer. This is a reproducibility/dependency failure,
not evidence that every idea in the repository is invalid.

Machine-readable evidence is in each `ast-*.json` result,
`runtime_images.json`, and `summary.json`.

## Barter instrument core (`ast-0021`)

- Pinned commit: `33e56188e2095781331f85aa3d7f88e251eec65a`
- Upstream has no Cargo lockfile, so the gate generated one and recorded SHA-256
  `0767b9c99a350d303c5977ca78ee167d9c365d1c0abf3506ddac1cc8e0055986`.
- Rust 1.91.1 was pinned because the repository requests changing `stable` and
  its chained-let syntax does not compile on Rust 1.85.
- Result: 15/15 `barter-instrument` tests passed offline.

Decision: advance the instrument/indexing foundation to adversarial identity,
serialization, duplicate, and malformed-input probes. This result does not
test Barter execution, accounting, backtesting, live connectivity, or profit.

## hftbacktest core (`ast-0046`)

- Pinned commit: `5f3ec40b2afb764e0fea112f941ed85523ef4e88`
- The manifest requires Rust 1.91.1; the gate built and recorded that profile.
- Upstream has no Cargo lockfile, so the generated resolution was recorded at
  SHA-256 `50ae0dda20bff6f4595568869f855e05846b2d7019c1cebf9ecb4622ac45a182`.
- Result: 22/22 backtest-only library tests passed offline with live features
  disabled. The initial broad command exposed an example/live feature mismatch;
  narrowing to `--lib` tested the intended core without hiding that boundary.

The subsequent platform-owned behavioral probe passed 8/8 deterministic tests.
Six confirmed latency, queue, partial-fill, cancellation, fee, and accounting
behavior. Two deliberately confirmed unsafe raw-library boundaries: overfills
are accepted by the direct state API and non-finite fees can propagate into
accounting state.

Decision: retain the backtest core only as a conditional sandbox candidate
behind finite-value, order-state, remaining-quantity, accounting-reconciliation,
and visible-depth guards. Advance it to recorded order-book replay; do not treat
this as profitability evidence. Full findings are in
`../hftbacktest_behavioral/report.md`.

The next small recorded-data gate subsequently passed using 23 pinned BTCUSDT
rows transformed into 42 dual-chronology engine events. It validated ingestion
and timestamp ordering only; a full-session fill/P&L test remains pending. See
`../hftbacktest_recorded_replay/report.md`.

The aggregate result is three passing scoped candidates and one reproducibility
failure across this non-Python gate.
