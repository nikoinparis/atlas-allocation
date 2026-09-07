# How to recreate every strategy on the dashboard, and how well that currently works

Written 2026-09-06 because the owner asked the right question: a strategy nobody can
recreate is not a strategy, it is a number in a JSON file. This is the honest answer,
including the parts that fail.

Regenerate the table with:

    ./.venv/bin/python scripts/audit_dashboard_reproducibility_v1.py

## Three different questions, routinely confused

1. **Is there a saved book** — dated target weights on disk?
2. **Does repricing that book reproduce the published path?**
3. **Is there a frozen manifest** saying what the strategy *is*, independent of the
   artifacts one particular run happened to leave behind?

Most of these pass 2 and fail 3. The saved weights reprice correctly, and nothing
written down would let you derive those weights again from raw data. Passing 2 means
the arithmetic is honest. Only 3 means the strategy is reproducible.

## Where it stands

| strategy | book reprices | holdings reprice | weight priced | manifest |
|---|---|---|---|---|
| SEC Growth Top-Five | **+0.984** | **+0.961** | 93.1% | yes |
| Dynamic Breadth-20 (cash conversion) | **+0.904** | **+0.973** | 97.7% | yes |
| Sector-Aware Signal Ensemble | +0.747 | **+0.968** | 97.6% | yes |
| Sector Ensemble 1.35x | +0.747 | **+0.968** | 96.8% | yes |
| ETF Return-First 60/40 | wide matrix | **+0.988** | 100.0% | yes |
| Residual-Controlled 1.25x | **+0.853** | **+0.926** | 81.0% | yes |

**All six now carry a saved book and a frozen manifest, and all six reproduce from the
holdings the dashboard publishes**, at correlations of +0.926 to +0.988 with 81% to 100%
of portfolio weight priced. Three of six also reproduce from a saved long-form book.

This was not the state on the morning of 2026-09-06. Then it was two of six reproducing
from a book, two of six with a manifest, and the headline strategy repricing at +0.493
with under half its weight priceable. Three things closed the gap: a flat ETF weekly
panel assembled from the vintage store, a dated book saved for the residual composite,
and manifests written for the four strategies that had none.

## What is still not settled

**The sector ensemble reprices from its saved book at only +0.747, and has since Step
241.** Its published holdings reprice at +0.968, so the strategy's arithmetic is sound —
what is missing is the allocator sitting above the saved stock leg, which is not saved
anywhere. Its manifest says so in `known_weaknesses` rather than implying the file
describes the whole strategy. The same applies to its 1.35x form.

**The ETF 60/40's book is a wide date-by-symbol matrix**, not long-form dated weights, so
the book-reprice column does not apply to it. Its holdings reprice at +0.988.

**The ETF panel is not point-in-time.** `data/etf_weekly_panel_v1` is assembled from
vintage bundles whose own manifests declare `point_in_time_prices: false`. It is fit for
repricing a book already chosen, which is all it is used for here. It is not fit for
choosing one, and any strategy work on it inherits a revision problem this project spent
Steps 219-240 removing from the equity panels.

## Recreating each one

### SEC Growth Top-Five — `sec-growth-survivorship-aware-v1`
    ./.venv/bin/python scripts/run_sec_growth_survivorship_retest_v1.py
Book: `evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv`.
Path: `path_growth__base__50bps.csv`. Reproduces at +0.984. No frozen manifest.

### Dynamic Breadth-20 — `sec-cash-conversion-breadth20-dynamic-v1`
    ./.venv/bin/python scripts/build_cash_conversion_sleeve_path_v1.py
Book: `evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv`.
Path: `evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv`.
Reproduces at +0.904. No frozen manifest.

### Sector-Aware Signal Ensemble — `sec-sector-aware-signal-ensemble-v1` and its 1.35x form
    ./.venv/bin/python scripts/run_sec_sector_aware_signal_ensemble_v1.py
Book: `evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv`.
**Reproduces at only +0.747 from the saved book, below the 0.85 bar, and this has been
true since Step 241.** The stock leg is saved; whatever allocator sits above it is not,
so the saved artifacts describe part of the strategy. The 1.35x presentation reprices
better from published holdings (+0.920) than the underlying book does, which points at
the missing allocator rather than at the prices.

### ETF Return-First 60/40 — `candidate-return-first-60-40-forward-v1`
Manifest: `config/forward/return_first_60_40_blend_v1.json`. Weights:
`evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv`, a wide
date-by-symbol matrix covering 2005-2026. Not checked here because the audit has no
flat ETF price panel to price it against. **This is the best-documented strategy and
the least verified — the two are unrelated.**

### Residual-Controlled 1.25x — `sec-residual-controlled-1.25x-5pct-v1`
    ./.venv/bin/python scripts/build_control_composite_book_v1.py --decision-date <Friday>
Manifest: `config/forward/sec_residual_controlled_sleeve_forward_v1.json`.
Book: `evidence/control_composite_book_v1/books.csv` — 79 dated books, 2023-01-06 to
2026-07-31, one per rebalance, saved by the builder itself and never rewritten once
written. Reproduces at +0.853.

Backfilling those books found a real defect. An unpriced cash-conversion slot was routed
to cash, but a growth name with no ticker mapping was **dropped outright**, so eight 2023
decisions produced books summing to 0.92 and the builder aborted. Aborting was correct
and the missing 8% had never been chased. Unmapped growth weight now goes to cash the
same as the other leg, and every saved book sums to exactly 1.0.

### The ETF price panel these checks depend on
    ./.venv/bin/python scripts/build_etf_weekly_panel_v1.py
35 symbols, 1,754 weeks, 1993-2026, flattened from seven vintage bundles whose
`prices.csv` hashes are each verified against their manifest. Not point-in-time.

## The trap that will waste your afternoon

Reproduction requires sweeping **two** offsets that are easy to conflate:

- the **execution offset** — which weekly close a decision is filled at;
- the **date-labelling shift** — which Friday a given weekly return is stamped with.

Executing a week earlier barely moves a book that rebalances fourteen times in 188
weeks. Labelling the same weekly return with a different Friday moves the correlation
**from -0.02 to +0.90**.

Step 238 swept only the first, got -0.026, and reported that a strategy did not
reproduce. It was withdrawn in Step 241. **Writing this audit on 2026-09-06 I made the
identical mistake again** — swept only the execution offset, got correlations near
-0.02 across all six, and was one step from reporting that not a single dashboard
strategy could be rebuilt. The same bug, in the same repository, from the same author,
five days later.

So: if a reproduction comes back near zero, the harness is wrong until proven otherwise.
`scripts/reproduce_dashboard_strategy_independently_v1.py` is the reference
implementation and `audit_dashboard_reproducibility_v1.py` delegates to it rather than
reimplementing it, for exactly this reason.

## What is missing, ranked

1. **A dated book for the residual composite.** It is the headline strategy and the
   least checkable thing here.
2. **A flat ETF weekly price panel.** Without it, two strategies cannot be fully
   repriced and the ETF 60/40 cannot be repriced at all.
3. **Frozen manifests for the four strategies that lack them.** A rebuild script is not
   a manifest: the script is what was run, the manifest is what the strategy *is*.
4. **An explanation of the sector ensemble's 0.747.** Known since Step 241 and never
   chased down. The likely cause is an unsaved allocator above the saved stock leg.
