# Atlas Offensive — R01 Pre-Registration: PIT Stock Breadth Confirmation

- **Run ID:** R01
- **Registration date:** 2026-07-21 (filed before any R01 experiment executed)
- **Author / executor:** Claude Code session under human owner nicholasturangan
- **Book component targeted:** REGIME_BRAIN (calm-state aggression input) — FEEDER→UPGRADE
- **Builds on:** R00 governance artifacts; Phase 5A PIT breadth scaffold
  (`scripts/build_pit_stock_breadth_panel.py`)
- **Execution status at registration:** BLOCKED_PREREQUISITE — Norgate Data subscription not
  installed on this machine. This pre-registration is binding for whichever future session
  executes R01 once the data is installed. No grid, threshold, or control below may be altered
  by that session.

## 1. Hypothesis

Unbiased point-in-time stock breadth retains at least half of the survivorship-biased lift
measured in the Phase 5A-Free diagnostic:

> **Top-vs-bottom breadth tercile spread of 4-week forward SPY returns within `calm_trend`
> weeks ≥ +0.26% per 4 weeks, with correct (monotonic) tercile ordering.**

Reference point (biased, descriptive-only): +0.517%/4w stock-level lift vs −0.457%/4w
ETF-level breadth in the same state.

## 2. Data and universe

- **Source:** Norgate Data (Platinum/Diamond tier) — PIT S&P 500 membership + delisting-aware
  daily adjusted prices, exported to 2005. **No substitute or scraped universe is permitted.**
- **Panel builder:** `scripts/build_pit_stock_breadth_panel.py` (existing scaffold; inputs under
  `data/stock_breadth/raw/`; templates and `SAMPLE_NOT_REAL` sentinels are rejected by design).
- **Development window:** through **2025-12-31**. The sealed 2026-01-01+ holdout is untouched
  (see `offensive_holdout_declaration.md`).
- **Lag convention:** all weekly signals lagged 1 week (`*_lag1w` columns).

## 3. Locked design

1. Build weekly breadth signals, all lagged 1 week: `pct_above_200d_ma`,
   advance/decline ratio, net new highs.
2. Reproduce the 5A diagnostic exactly but unbiased: 4-week forward SPY returns by breadth
   tercile within `calm_trend` weeks, development window only.
3. **Only if the hypothesis passes**, test breadth-scaled offense in `calm_trend` AND
   `neutral_mixed` via the checkpoint wrapper with BOTH locked grids (and no others):
   - **Conservative:** ×0.85 / ×1.00 / ×1.15 for breadth <40% / 40–70% / >70%
   - **Return-first:** ×1.00 / ×1.15 / ×1.30 for the same tercile boundaries
4. Baselines: unmodified base strategy (walk-forward), production pin (reporting benchmark
   only), 5A-Free biased diagnostic (descriptive comparison).

## 4. Primary metrics

Diagnostic: tercile spread of 4-week forward SPY returns within calm_trend (%/4w).
Portfolio: full-period net CAGR and expected log growth vs the unmodified base; per-state
expectancy; beta-vs-alpha decomposition of any improvement (reported, labeled honestly).

## 5. Recorded, non-gating metrics

Sharpe, max drawdown, CVaR, volatility, turnover — in every table, never pass/fail.

## 6. Costs

Per-instrument costs from `data/research/atlas_offensive_cost_library.csv` (R00 v1); every
portfolio variant also reported at 2x costs. 10bps flat assumption retired.

## 7. Null controls

- **200 random-tercile placements** (random assignment of tercile labels within calm_trend
  weeks); the live variant must beat ≥90% of placements on the primary metric.
- **Inverted-signal control** (breadth terciles flipped); expected to hurt — if it helps,
  the live result is presumed noise.

## 8. Success / failure criteria (locked)

- **Diagnostic pass:** unbiased lift ≥ +0.26%/4w with correct tercile ordering.
- **Portfolio pass:** best locked variant improves full-period net CAGR AND log growth vs the
  unmodified base in walk-forward, beats ≥90% of placement nulls, and survives 2x costs.
- **Both pass → CONFIRMED-FOR-HUMAN-REVIEW:** breadth becomes a REGIME_BRAIN input; recommend
  R02 (PBI native rebuild) and R03 (stock universe) in parallel.
- **Diagnostic < +0.26%/4w → breadth classified DIAGNOSTIC-ONLY permanently;** record the
  survivorship lesson; state explicitly whether Norgate remains justified by R03 alone.
- **Ambiguous → RESEARCH-ONLY** with exactly one pre-registered follow-up experiment specified
  for the next session.

## 9. Prohibited actions

Consulting the sealed 2026+ holdout; adding grids mid-run; scraping a substitute universe;
touching production pins/weights/`public/dashboard-data.json`; `git add -A`; regenerating
dashboard bundles. Promotion requires explicit human authorization.
