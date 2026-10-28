# Free ETF Data Acquisition

Snapshot: `20261027T163652Z-c69f63655e983f53`

A rootless Podman container downloaded the configured ETF universe through a fully pinned yfinance environment. No host Python packages or paid services were used. The normalized output was validated and stored immutably.

## Acquisition

- Symbols: **35**.
- Daily price rows: **211,528**.
- Corporate-action rows observed: **3,843**.
- Latest market date: **2026-10-27**.
- Maximum calendar staleness: **0 days**.
- Freshness and completeness gate: **pass**.

## Revision monitoring

- Common price rows: 211,283.
- Revised historical rows: 151,661 (71.7810%).
- Newly observed rows: 245.
- Disappeared rows: 0.

## Safety classification

This snapshot is free and useful for current ETF research, forward paper-data collection, and detecting revisions between future pulls. It remains research-only: Yahoo-adjusted history can be revised, the universe was selected with hindsight, ticker IDs are not permanent, and complete delisting/membership coverage is unavailable.

Paid CRSP/Norgate work is deferred. The free collection path does not depend on it.
