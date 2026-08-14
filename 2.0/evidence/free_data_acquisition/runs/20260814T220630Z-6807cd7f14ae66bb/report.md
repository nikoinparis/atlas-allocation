# Free ETF Data Acquisition

Snapshot: `20260814T220630Z-6807cd7f14ae66bb`

A rootless Podman container downloaded the configured ETF universe through a fully pinned yfinance environment. No host Python packages or paid services were used. The normalized output was validated and stored immutably.

## Acquisition

- Symbols: **35**.
- Daily price rows: **209,742**.
- Corporate-action rows observed: **3,812**.
- Latest market date: **2026-08-14**.
- Maximum calendar staleness: **0 days**.
- Freshness and completeness gate: **pass**.

## Revision monitoring

- Common price rows: 209,637.
- Revised historical rows: 150,313 (71.7016%).
- Newly observed rows: 105.
- Disappeared rows: 1.

## Safety classification

This snapshot is free and useful for current ETF research, forward paper-data collection, and detecting revisions between future pulls. It remains research-only: Yahoo-adjusted history can be revised, the universe was selected with hindsight, ticker IDs are not permanent, and complete delisting/membership coverage is unavailable.

Paid CRSP/Norgate work is deferred. The free collection path does not depend on it.
