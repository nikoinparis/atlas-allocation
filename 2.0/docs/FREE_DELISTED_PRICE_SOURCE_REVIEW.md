# Free delisted-price source review

## Decision

Tiingo is the preferred zero-cost validation source. Its free individual tier
publishes adjusted and raw EOD prices, dividends, splits, a daily symbol
inventory, and limited support for delisted tickers. The documented free limit
is 50 requests per hour, 1,000 per day, and 1 GB per month. The project probes
no more than 24 symbols per batch because metadata and prices require up to two
requests per symbol.

The public inventory was tested before requesting credentials. Of 327 SEC
identities whose recovered symbol failed at Yahoo, 284 have a Tiingo inventory
record overlapping the SEC eligibility period. That 86.9% candidate rescue
rate is sufficient to justify an authenticated probe, but inventory presence
alone does not prove issuer identity or price availability.

## Alternatives reviewed

| Source | Free usefulness | Decision |
|---|---|---|
| Tiingo | Free token; adjusted/raw EOD, actions, 60+ years, some delisted support, public dated inventory | Selected for validation |
| Alpha Vantage | Free historical listing/delisting roster | Rejected for prices because full adjusted daily history is premium |
| Nasdaq Data Link WIKI | Public-domain historical EOD table with free registered access | Archive ends in 2018, so it cannot validate recent-return research |
| SimFin | Free account includes five years of charts/fundamentals | Too short for the declared 2012 history and no verified delisting-return solution |
| Yahoo | No account | Measured failure: only 56 issuer-period-valid histories among 416 recovered former-company identities |

## Credential and validation rules

- Supply the token only through `TIINGO_API_TOKEN` for the process being run.
- Never write the token into configuration, source manifests, URLs, logs, or
  project files.
- Query metadata and prices for at most 24 new symbols per free-tier batch.
- Compare Tiingo's issuer name with the as-filed SEC company name.
- Require price dates to overlap the SEC eligibility interval.
- Retain empty histories, HTTP failures, and name mismatches as explicit rows.
- Do not authorize strategy testing until actual decision-date price coverage
  and delisting-outcome handling pass their declared gates.

## Official references

- [Tiingo EOD documentation](https://www.tiingo.com/documentation/end-of-day)
- [Tiingo symbology and delisted support](https://www.tiingo.com/documentation/appendix/symbology)
- [Tiingo free-tier product limits](https://www.tiingo.com/products/end-of-day-stock-price-data)
- [Alpha Vantage documentation](https://www.alphavantage.co/documentation/)
- [Nasdaq Data Link usage](https://docs.data.nasdaq.com/v1.0/docs/in-depth-usage)
- [SimFin pricing](https://www.simfin.com/en/prices/)

## Project references

- `config/tiingo_delisted_price_probe_v1.json`
- `src/systematic_trader/tiingo_delisted.py`
- `scripts/probe_tiingo_symbol_inventory_v1.py`
- `scripts/acquire_tiingo_delisted_probe_batch_v1.py`
- `tests/test_tiingo_delisted.py`
- `evidence/tiingo_delisted_coverage_probe_v1/result.json`
- `evidence/tiingo_delisted_coverage_probe_v1/report.md`
