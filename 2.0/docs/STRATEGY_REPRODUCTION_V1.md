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

| strategy | book reprices | holdings reprice | priced | manifest |
|---|---|---|---|---|
| SEC Growth Top-Five | **+0.984** | **+0.961** | 93.6% | no |
| Dynamic Breadth-20 (cash conversion) | **+0.904** | **+0.855** | 69.3% | no |
| Sector-Aware Signal Ensemble | +0.747 | +0.740 | 76.2% | no |
| Sector Ensemble 1.35x | +0.747 | **+0.920** | 84.8% | no |
| ETF Return-First 60/40 | not checked | not checked | — | **yes** |
| **Residual-Controlled 1.25x** | **no saved book** | **+0.493** | 45.6% | **yes** |

Two of six reproduce cleanly from a saved book. Three of six reproduce from the
holdings the dashboard itself publishes. Two of six have a frozen manifest.

## The one that matters most is the worst documented

**Residual-Controlled 1.25x is the dashboard's headline strategy, the one whose forward
clock starts 2026-09-11, and the one blended into the 50/50 protocol — and it has no
saved book at all.** Its published holdings reprice at +0.493 with only 45.6% of weight
priceable, because the book mixes SEC equities with ETFs and there is no flat ETF price
panel in this repository; ETF prices live in the vintage store under `data/vintages`.

That number is not evidence the strategy is wrong. It is evidence that **less than half
of it can currently be checked**, which is a different and more fixable problem. Until
an ETF panel is assembled and a dated book is saved, the honest statement is that this
strategy's arithmetic has not been independently verified.

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
Reference path: `evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv`.
No dated book is saved. See above.

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
