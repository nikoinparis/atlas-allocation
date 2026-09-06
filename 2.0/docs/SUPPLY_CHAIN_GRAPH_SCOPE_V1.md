# Supply-Chain Graph — Acquisition Scope V1

Status: **scoped, not approved, not built.** Every number below the "Measured" heading
was measured on this machine on 2026-09-02. Everything under "Projected" is arithmetic on
those measurements and is labelled as such. Nothing here is a result.

## 1. What this would be

A customer–supplier graph built from SEC filing text, used to test whether a customer's
returns predict its suppliers' returns with a lag. The underlying claim is Cohen &
Frazzini, *Economic Links and Predictable Returns* (Journal of Finance, 2008): investors
are slow to propagate news across economic links, so a customer's move this month
predicts the supplier's move next month. **Cited from general knowledge, not from a read
of the paper this session.** Verifying the original specification is task zero of Phase 1.

The reason to build it is not that it is machine learning or a graph. It is that
relationship data is a **different information source** from price and from XBRL
fundamentals, so it is structurally uncorrelated with everything in the registry. This
project's binding constraint is effective breadth ≈1.15 (Batch 03), and under
IR ≈ IC × √BR no further tuning of the existing family can raise it. This can.

## 2. Measured — the corpus already on disk

There is already a filing-text corpus here, which was not previously recognised as one.
`data/sec_broad_identity_cache_v2/` and `data/sec_historical_identity_cache/` hold
**1,800 gzipped primary filing documents** (439MB, 5,332 counting sidecars), full body
text, one filing per CIK, dated 2014–2026 and weighted to 2025.

It is an identity-resolution cache, not a filing history: **exactly one filing per
company, 1,093 distinct CIKs of the 3,253-name universe.** It is enough to measure
extraction yield, which is what it was used for. It is not enough to backtest.

## 3. Measured — extraction yield, on those 1,800 filings

| Quantity | Measured |
|---|---|
| Filings discussing customer concentration at all | 614 / 1,093 (56.2%) |
| Filings naming an entity, naive regex | 182 / 1,093 (16.7%) — **inflated** |
| Filings explicitly anonymous ("one customer accounted for…") | 156 / 1,093 (14.3%) |
| **Filings yielding a clean named edge with a revenue share** | **139 / 1,800 (7.7%)** |
| Clean weighted edges extracted | 349 |
| Distinct named customers | 193 |
| Median disclosed revenue share on an edge | 20% |

The 16.7% is inflated and the reason matters. Of 1,140 raw regex matches, **781 were the
junk entity "Company"** and others were boilerplate — FDIC deposit insurance, SIPC,
"Credit Risk The Company". A naive extractor is **~69% false positives**. The 7.7% figure
is after filtering to entities that are actually named.

The genuine hubs are exactly the ones the mechanism predicts: Apple, Cisco Systems,
McKesson, Samsung Electronics, IBM, Hewlett Packard Enterprise, AmerisourceBergen,
Southern Company, Boeing. A representative clean edge, verbatim in structure:
CIK 0000008063 → The Boeing Company, 10.4% of sales.

**Hub concentration, which decides whether this adds breadth:** the top 10 customers
carry only 19% of edges, and the Herfindahl over customers is 0.0090, giving
**~111 effective distinct customers from 193 named.** This is the single most encouraging
number in the scope. Supplier positions sharing one customer are one bet, not many; had
the graph collapsed into a few hubs it would have reproduced this project's chronic
single-name concentration failure. It does not.

## 4. Measured — what a full acquisition costs

From EDGAR's 2024 QTR1 full index (57.8MB, fetched): 4,980 10-K filings across all
filers, of which **2,535 are in our 3,253-name universe — 78% of the universe files a
10-K in Q1 alone.** Annual coverage is therefore near-total, ~3,100 filings/year.

Mean cached primary document 1.19MB, median 0.16MB, p90 3.29MB.

| History | Filings | Raw | Gzipped | Request time at EDGAR's 10/sec |
|---|---|---|---|---|
| 2005–2026 | ~62,000 | ~74GB | ~16GB | 1.7h |
| 2016–2026 | ~31,000 | ~37GB | ~8GB | 0.9h |
| 2021–2026 | ~15,500 | ~18GB | ~4GB | 0.4h |

Rate limiting is not the constraint. **Storage is**, and it is avoidable: extract the
candidate windows during download and discard the raw HTML. Only 56% of filings contain
concentration language and only the ±400-character windows are needed, so the retained
artefact is ~100–200MB rather than 16GB. The corpus is re-acquirable from EDGAR, so
nothing durable is lost by discarding.

## 5. Projected — the yield of a full build

Arithmetic on the measured rates, not results:

- ~3,100 filings/year × 7.7% clean-edge rate ≈ **~240 filers/year with a named customer**
- of named customers, those US-listed and in the price panel — judged from the observed
  hub list at roughly half, **unverified and the largest single uncertainty here** —
  gives **~120–140 tradeable supplier names/year**
- scaling the measured Herfindahl, plausibly **60–110 effective independent customers**

Against a current effective breadth of ≈1.15, even the bottom of that range is a change
of kind rather than degree. That is the entire case for building this.

## 6. Where this most likely dies

Stated before building, so the outcome cannot be rationalised afterwards.

1. **The effect is 18 years published.** Expect heavy decay. If the original specification
   does not replicate on 2005–2015 before being applied to recent data, stop.
2. **Extraction precision.** 69% false positives naive. A bad extractor manufactures edges,
   and a manufactured edge is a manufactured backtest.
3. **Name-to-ticker resolution.** "Samsung Electronics Co" is not investable here;
   "Nexty Electronics" may not resolve at all. This is where such projects usually die,
   and the ~50% tradeable assumption above is currently a guess.
4. **Point-in-time discipline.** A 10-K filed 2026-02 describing FY2025 relationships is
   knowable only from its filing date. Edges must be vintaged by filing date, never by
   fiscal period. Prefix-invariance test required, not a code read — this project has
   twice found real lookahead that a code read missed.
5. **Recency criteria cut both ways.** `success_criteria_v2` weights the trailing year at
   45%. A graph strategy that only worked pre-2015 fails on the owner's own criteria even
   if the academic effect is real.

## 7. Phases, with a kill gate on each

- **Phase 0 — verify the claim (hours).** Read the actual Cohen & Frazzini specification.
  Confirm horizon, portfolio construction, and reported effect size. *Kill if the paper's
  design cannot be reproduced with filing-derived edges.*
- **Phase 1 — extractor precision (1–2 days).** Build the extractor, hand-label a random
  200-filing sample, measure precision and recall. *Kill below ~85% precision.* This is
  the one place where a language model genuinely earns its place: bounded entity
  extraction from pre-filtered windows, ~20M tokens, verifiable against the hand labels.
  Not prediction — extraction.
- **Phase 2 — acquisition (1 day).** Stream 2016–2026 with window extraction and
  discard-raw, under the existing hash-audited vintage conventions in
  `scripts/acquire_sec_form4_bulk_v1.py`. Requires `SEC_USER_AGENT`.
- **Phase 3 — graph and resolution (2–3 days).** Resolve names to CIKs. *Kill below 40%
  resolution*, which would put tradeable names under ~100.
- **Phase 4 — the test (2–3 days).** Purged walk-forward, filing-date vintaging,
  leave-one-customer-out by default, costs at 10/50/100bps, regimes reported separately,
  correlation to all six existing candidates, and multiple-testing correction against the
  cumulative trial count. Graded on `success_criteria_v2` recent-window tiers.

Roughly two working weeks, dominated by Phases 1 and 3. **It cannot be ready for the
September 4 first realization and must not be rushed toward it.** It is the next research
arc; the forward clock and its seven pinned files are untouched by any of this.

## 8. What is being asked for

Approval to start Phase 0 and Phase 1 only, since those are cheap and Phase 1's precision
number decides whether the remaining eight days are worth spending. Phase 2 involves
sustained EDGAR downloading and should be separately confirmed.

Nothing here is promotion-authorized. Live trading remains disabled.
