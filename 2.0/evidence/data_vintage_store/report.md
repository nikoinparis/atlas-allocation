# Versioned Data Store — Initial Snapshot

Snapshot: `20260415T081954Z-5c0effb962d04b1e`

The existing 1.0 ETF data is now stored as an immutable, hashed snapshot. It is deliberately labeled research-only and is unavailable to strict historical as-of queries before its April 2026 observation timestamp.

## Enforced results

- File-integrity verification: **pass**.
- Attempted 2005 access rejected as future knowledge: **pass**.
- Attempted production-grade selection rejected: **pass**.
- Historical simulation grade: **research_only**.

## Why this snapshot is not point-in-time

The adjusted history was downloaded in 2026, its earlier vendor revisions are unavailable, the ETF list was selected with hindsight, ticker-derived identifiers are not permanent IDs, and complete split/delisting coverage is not proven. The store records those facts instead of allowing the data to satisfy production gates.

## What the next vendor export must contain

- licensed or otherwise verified permanent security identifiers.
- point-in-time universe membership with knowledge timestamps.
- prices for active and delisted securities.
- split, distribution, merger, and delisting events with revision identifiers.
- multiple retained vintages so revisions can be detected.

The ingestion command and schemas are ready for that export. Each future pull creates a new content-addressed snapshot; existing snapshots are never overwritten.
