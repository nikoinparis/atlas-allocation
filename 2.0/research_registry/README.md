# Research Registry

`strategy_candidates.json` is the canonical shortlist of strategies worth
further testing. A candidate entry is never an approval: it records why the
strategy was retained, the gates it passed, the gates still missing, and its
latest robustness status. Failed robustness candidates remain in the file as
`provisional_fragile` rather than being erased.

The registry is the authoritative inventory of projects, resources, and ideas
reviewed for Portfolio Optimizer 2.0. Every substantive linked listing from the
source catalog receives a record even when it cannot be executed.

The pinned August 5, 2026 source snapshot contains 344 linked listings: 315 in
the main catalog and 29 in the crypto-focused catalog. The registry preserves
all 17 duplicate listings and points each one to its first canonical row. It
also retains supplemental links, including GitHub source links attached to a
project's primary website.

Important fields include source revision, category, license, maintenance,
required data, reproducibility, test status, evidence location, integration
decision, and rationale.

`inventory_summary.json` contains coverage counts, file hashes, review-batch
totals, flags, and all 15 non-entry bullets. Those bullets are headings,
organization labels, technology notes, or “more coming” notes; none is silently
dropped.

## Rebuild

From the `2.0` directory:

```bash
python3 scripts/build_catalog_inventory.py
```

The default revision is intentionally pinned. Updating the catalog is a
separate reviewed action so that an experiment's source universe cannot change
silently.
