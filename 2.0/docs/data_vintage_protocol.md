# Data Vintage Protocol

## Purpose

Backtests may only use information that the system can prove was known by the
simulated decision time. A long historical CSV downloaded today is not treated
as point-in-time history merely because its rows have old dates.

## Snapshot rules

1. Every acquisition creates a new content-addressed directory under
   `data/vintages/`; existing snapshots are never overwritten.
2. Every payload file has a recorded SHA-256 hash and byte length.
3. `observed_at_utc` records when the complete export became available to this
   system. Row-level `knowledge_at_utc` records when an individual fact became
   knowable when the provider supplies that information.
4. A snapshot cannot be selected before `observed_at_utc`.
5. Required capability claims are explicit booleans. Missing point-in-time
   membership, permanent IDs, corporate actions, delistings, or revision
   vintages cannot be inferred from price coverage.
6. Tampered payloads fail integrity verification before reads.

## Production-grade bundle

The example descriptor in `config/data_snapshot_descriptor.example.json`
defines five normalized tables:

| Table | Purpose |
|---|---|
| `prices.csv` | Dated adjusted prices joined by permanent security ID |
| `universe_membership.csv` | Effective membership intervals plus knowledge timestamps |
| `security_master.csv` | Permanent identity across ticker/name/listing changes |
| `corporate_actions.csv` | Splits, distributions, mergers, and related adjustments |
| `delistings.csv` | Delisting dates, reasons, and delisting returns |

The ingestion gate validates required columns, positive finite adjusted prices,
unique security/date rows, non-overlapping membership intervals, knowledge
timestamps, and file integrity.

## Current legacy snapshot

The 1.0 Yahoo/yfinance cache is registered with every production claim set to
false. Its old observations were acquired in April 2026, so strict historical
queries before that timestamp are rejected. The snapshot preserves research
reproducibility but does not solve historical revisions, hindsight-selected ETF
membership, ticker identity, or delisting coverage.

## Vendor path

The store is vendor-neutral. As of August 2026, the practical individual-user
path identified from official documentation is a Norgate US Stocks Platinum or
Diamond subscription because those levels advertise both delisted securities
and historical index constituents. CRSP is the higher-quality institutional or
academic path when access is available because PERMNO supplies stable security
identity and CRSP includes explicit delisting-return and distribution fields.

No vendor claim is accepted merely from a product description. The first real
export must still pass schema, coverage, lag, license, and revision tests.

## Ingestion

Copy the example descriptor beside an export, update its metadata and file
mapping, then run:

```text
python3 scripts/ingest_vendor_bundle.py /path/to/descriptor.json
```

Running the same descriptor and files again is idempotent. Changed data creates
a different snapshot ID. Scheduled acquisition should run the vendor-specific
export first and invoke this command only after the export completes.

## Free ETF collection

Paid-data work is deferred. The current 35-ETF research universe can be refreshed
without installing provider packages on the host:

```text
podman build -t localhost/po2-yfinance:1.5.2-v1 -f config/images/yfinance-1.5.2.Containerfile .
python3 scripts/acquire_free_etf_snapshot.py
```

The container has a fully pinned dependency lock, receives no host filesystem
mount, and exports normalized results through `podman cp`. A run is rejected if
any configured symbol fails or is more than seven calendar days stale. Every
successful pull becomes a new snapshot and is compared with the preceding free
snapshot for changed, added, or disappeared price rows.

This path is suitable for current ETF research and building a forward paper-data
record. Its historical claims remain false because Yahoo history can be revised,
the universe is hindsight-selected, ticker IDs are synthetic, and delisting or
historical membership coverage is incomplete.
