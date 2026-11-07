# Free ETF Data Acquisition

Snapshot: `20261101T120030Z-ac1f1ed8958b7cb7`

A rootless Podman container downloaded the configured ETF universe through a fully pinned yfinance environment. No host Python packages or paid services were used. The normalized output was validated and stored immutably.

## Acquisition

- Symbols: **35**.
- Daily price rows: **211,633**.
- Corporate-action rows observed: **3,843**.
- Latest market date: **2026-10-30**.
- Maximum calendar staleness: **2 days**.
- Freshness and completeness gate: **pass**.

## Revision monitoring

- Common price rows: 211,528.
- Revised historical rows: 151,757 (71.7432%).
- Newly observed rows: 105.
- Disappeared rows: 0.

## Safety classification

This snapshot is free and useful for current ETF research, forward paper-data collection, and detecting revisions between future pulls. It remains research-only: Yahoo-adjusted history can be revised, the universe was selected with hindsight, ticker IDs are not permanent, and complete delisting/membership coverage is unavailable.

Paid CRSP/Norgate work is deferred. The free collection path does not depend on it.
