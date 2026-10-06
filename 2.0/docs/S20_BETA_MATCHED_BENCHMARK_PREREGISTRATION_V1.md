# S20 — Beta-matched benchmark for the dashboard books: pre-registration

Written and committed 2026-10-06, **before any return in this test was computed.**

## Question

Each dashboard book runs at a market beta of 1.30–1.75 (Step 310). A book can beat SPY simply by
holding more market risk. Does any book earn a return **beyond what a passive portfolio with the
same market exposure earned**, measured without using any future information?

## Books (unlevered only, as the owner asked: no borrowed money, no financing)

| id | source | why |
|---|---|---|
| residual_controlled_1x | `evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv` | headline book at 1.00x (the dashboard shows 1.25x) |
| sector_aware_ensemble | dashboard record `sec-sector-aware-signal-ensemble-v1` | the 1.35x "fragile" book is this book with borrowed money, so it is excluded |
| cash_conversion_b20_dynamic | dashboard record `sec-cash-conversion-breadth20-dynamic-v1` | |
| growth_survivorship | dashboard record `sec-growth-survivorship-aware-v1` | |
| etf_60_40_return_first | dashboard record `candidate-return-first-60-40-forward-v1` | the only book with history before 2023 (from 2005) |

All are net of 50 bps costs as published. Every series is aligned to the week-ending grid through
`return_conventions.detect_convention` against SPY before any join (the Step 291 defect).

## Nulls (passive, investable)

- **N1, SPY:** one factor.
- **N2, XLK + XLE:** two factors, because the SEC books draw from a technology-and-energy universe.

ETF prices come from `data/etf_weekly_panel_v1`. The risk-free rate is BIL's weekly return.

## Construction, fixed

- Betas are estimated by OLS of the book's excess return on the factors' excess returns, over an
  **expanding window using only weeks strictly before t**, with at least 26 weeks. The first 26
  weeks of each book are excluded from the evaluation.
- Weekly alpha_t = (r_book − rf) − Σ β_{t−1} · (r_factor − rf).
- Matched benchmark return_t = rf + Σ β_{t−1} · (r_factor − rf). Where beta exceeds 1, this
  borrows at the T-bill rate. That is stated, not hidden.
- Alpha is annualized as the weekly mean × 52.

## Windows

- **Full:** all eligible weeks.
- **Pre-break:** through 2025-04-03.
- **Post-break:** from 2025-04-04, Step 261's break week. This is not a new choice.
- **ETF 60/40 only:** additionally reports 2008–2009 and 2020.

## Inference and the bar

- One-sided p for alpha > 0, from a stationary block bootstrap (mean block 8 weeks, 10,000 draws,
  seed 20261006) of the weekly alpha series, recentred to zero.
- **Trials in this test: 5 books × 2 nulls = 10. Bonferroni bar: p < 0.005.** This sits on top of
  the project's cumulative search of 300+ steps over the same 2023–2026 window, so even a pass is
  the survivor of a very large search.
- **PASS** requires all three:
  1. full-window alpha > 0 at p < 0.005;
  2. alpha > 0 in the pre-break window;
  3. alpha > 0 in the post-break window.

## Limits declared in advance

- These are path-level returns, so leave-one-holding-out cannot be run here. Steps 222–225 have
  that at the holdings level.
- The equal-weight universe paths (`evidence/full_history_out_of_sample_v1`) begin 2023-10, which
  leaves too few pre-break weeks. They are reported as a secondary check over their common window
  only, and do not enter the pass rule.
- Everything here is in-sample for the SEC books. A pass would mean "not explained by market and
  sector exposure in sample", nothing more.
