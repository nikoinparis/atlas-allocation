# TradingView Recorded-Response Adoption Gate

Generated: 2026-08-08

A three-symbol response was captured from the public America scanner endpoint
and pinned in `fixtures/america_scan_2026-08-08.json`. It is a schema fixture,
not an authoritative or redistributable price-history dataset.

Observed boundaries:

- All rows reported `delayed_streaming_900`.
- The response provides no per-row observation or data-availability timestamp.
- SPY returned a null `market_cap_basic`, proving selected columns can be
  legitimately missing even when the row itself is present.
- Response values are positional arrays, so a schema/order mismatch could map
  valid-looking numbers to the wrong fields unless strictly checked.

The platform adapter therefore validates timezone-aware capture time, unique
symbols, positional length, finite numeric values, missing columns, and update
mode. It always marks this response type ineligible for point-in-time
historical decisions because receipt time is not market observation time.

Decision: useful for current screening only after freshness and vendor-policy
controls are added. Not approved as a historical price source or trading
signal input.
