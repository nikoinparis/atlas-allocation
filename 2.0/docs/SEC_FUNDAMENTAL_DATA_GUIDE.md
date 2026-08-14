# SEC fundamental data guide

## Purpose

This layer supplies information independent of the frozen price strategies.
It must preserve what was knowable at each historical decision and must never
replace an old fact in place when a later amendment or restatement appears.

## Source hierarchy

1. SEC ticker/exchange association file maps current pilot tickers to CIKs.
2. Submissions JSON supplies accession numbers, forms, report dates, filing
   dates, and precise EDGAR acceptance timestamps.
3. Additional submission-history JSON files extend older filing coverage.
4. Company Facts JSON supplies standardized US-GAAP XBRL values.

Company Facts does not itself provide the full acceptance timestamp for each
fact. The pipeline joins every fact to Submissions by accession number. If the
join is unavailable, the fact is conservatively assigned to 23:59:59 UTC on
its filing date.

## Point-in-time rules

- A fact is usable only when `available_at < decision_time`.
- Amendments are new events; they never rewrite earlier decision snapshots.
- Quarterly factor inputs accept direct-quarter durations of 60–120 days.
- Balance-sheet inputs accept instantaneous contexts.
- Year-to-date and annual durations are retained in the raw event table but
  cannot silently enter direct-quarter comparisons.
- Year-over-year growth requires the same fiscal period from the prior fiscal
  year to have been available at the decision time.
- Every raw download is cached and content-hashed.

## Intended first factors

- revenue and net-income year-over-year growth;
- gross, operating, net, operating-cash-flow, and free-cash-flow margins;
- margin change versus the prior-year fiscal period;
- liabilities, debt, cash, and equity relative to assets;
- share-count growth and dilution;
- repurchases and stock compensation relative to revenue.

These inputs must first pass live coverage and unit audits. Only then may they
be ranked or blended with a frozen price strategy.

## Known limitation

The first 20 issuers are a present-day technology/energy engineering pilot.
They are not a historical investable universe. Their results may validate the
software and economic direction, but cannot validate a tradable strategy until
historical membership, delistings, and price availability are addressed.

## Historical filer-universe rebuild

The second-stage universe no longer begins with present-day tickers. It reads
the SEC Financial Statement Data Sets `SUB` table for every quarter from
2012Q1 through 2026Q1. At each calendar-quarter decision it selects only the
latest 10-K or 10-Q accepted strictly before the decision. The as-filed SIC
must belong to a declared technology or energy range, the as-filed filer
status must be Large Accelerated or Accelerated, and the filing must be no
more than 450 days old.

CIK is the permanent company key. Current SEC tickers are attached only after
membership has been constructed and never determine inclusion. Former and
unmapped companies are retained as explicit failures. Two symbol-recovery
passes inspect the last eligible filing: first the inline XBRL cover, then a
standalone legacy XBRL instance. Symbols must be explicitly tagged, contain a
letter, have one unambiguous value, and not collide across overlapping CIK
membership histories before they may enter a price probe.

The free Yahoo probe is a coverage diagnostic, not a strategy dataset. A
returned history must overlap the issuer's eligible period; otherwise it is
classified as possible ticker reuse. Missing histories and delisting returns
cannot be silently removed, forward-filled, or converted to cash. The
expanded fundamental backtest remains blocked until a source supplies enough
validated historical prices and declared delisting outcomes.

References:

- `config/sec_historical_filer_universe_v1.json`
- `data/sec_historical_universe_vintages/20260813T095119Z-sec-historical-filers-v1/manifest.json`
- `evidence/sec_historical_identity_v1/result.json`
- `evidence/sec_historical_identity_v1/report.md`
- `evidence/sec_recovered_price_probe_v1/result.json`
- `evidence/sec_recovered_price_probe_v1/report.md`
