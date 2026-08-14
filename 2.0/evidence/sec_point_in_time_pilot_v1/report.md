# SEC point-in-time fundamental pilot v1

The free SEC data foundation is implemented and live vintage
`20260813T065239Z-sec-pit-v1` has passed its structural audit. The user-agent
contact was supplied transiently and is not stored in project artifacts.

Implemented controls:

- cached SEC ticker, Submissions, additional filing-history, and Company Facts retrieval;
- at most four requests per second, below the SEC ten-request-per-second ceiling;
- content hashes, retrieval timestamps, URLs, sizes, and HTTP metadata for every raw source;
- accession-number join from XBRL facts to EDGAR `acceptanceDateTime`;
- conservative 23:59:59 UTC filing-date fallback when acceptance time is absent;
- immutable amendments that affect only decisions after their later acceptance;
- canonical aliases for 16 growth, margin, cash-flow, balance-sheet, dilution, and repurchase inputs;
- direct-quarter and instantaneous period classification to avoid mixing quarterly, year-to-date, and annual values;
- strict `available_at < decision_time` as-of filtering;
- duplicate, missing-time, reversed-period, unit, period, amendment, and coverage fields in the vintage audit;
- raw filing and fact event tables plus derived filing-time-aware factor inputs.

Five synthetic focused tests passed. They prove that an amended Q1 revenue
value is invisible before the amendment acceptance time, becomes visible only
afterward, produces the correct point-in-time year-over-year growth, and that
live access is rejected without a declared user agent.

The live vintage contains 57,736 canonical events, 1,270 accessions, and 453
amendment events for 20 companies. It has zero duplicate facts, missing
availability times, or reversed periods. A single SLB debt fact reported in EUR
is retained in raw provenance and excluded from USD factor inputs. Accession
join coverage is 99.92%, and all filing rows contain precise acceptance times.
The quarterly builder produced 1,076 company-decision rows across 58 decisions,
with 17 companies at minimum and 19 at the median. Thirty-one inputs passed the
pilot coverage threshold.

The technology/energy universe remains an engineering pilot. It is
current-membership based and not survivorship-safe. Pilot factor diagnostics
are authorized, but strategy promotion remains prohibited.

For a future new vintage, set a real identifying value such as:

```text
SEC_USER_AGENT="Portfolio Optimizer your-real-contact@example.com"
```

Then run `scripts/build_sec_fundamental_vintage.py` in the configured project
environment. Raw responses are cached, so reruns do not repeatedly request the
same SEC resources.
