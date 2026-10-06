# Free ETF Data Acquisition

Snapshot: `20261003T120024Z-a7ff75431d4f7435`

A rootless Podman container downloaded the configured ETF universe through a fully pinned yfinance environment. No host Python packages or paid services were used. The normalized output was validated and stored immutably.

## Acquisition

- Symbols: **35**.
- Daily price rows: **210,933**.
- Corporate-action rows observed: **3,843**.
- Latest market date: **2026-10-02**.
- Maximum calendar staleness: **1 days**.
- Freshness and completeness gate: **pass**.

## Revision monitoring

- Common price rows: 210,793.
- Revised historical rows: 155,972 (73.9930%).
- Newly observed rows: 140.
- Disappeared rows: 0.

## Safety classification

This snapshot is free and useful for current ETF research, forward paper-data collection, and detecting revisions between future pulls. It remains research-only: Yahoo-adjusted history can be revised, the universe was selected with hindsight, ticker IDs are not permanent, and complete delisting/membership coverage is unavailable.

Paid CRSP/Norgate work is deferred. The free collection path does not depend on it.
