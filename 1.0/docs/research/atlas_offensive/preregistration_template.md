# Atlas Offensive — Pre-Registration Template

> Copy this file to `docs/research/atlas_offensive/runNN_preregistration.md` and fill it in
> **before the first backtest of the run executes**. Post-hoc discoveries are permitted but must
> be labeled `POST-HOC` in the report and re-confirmed in a locked follow-up run before adoption
> (the α / PBI pattern). Every variant evaluated — including nulls and failures — gets a row in
> `data/research/atlas_offensive_trial_registry.csv`.

---

## Header

- **Run ID:**
- **Registration date:** (must precede first experiment execution)
- **Author / executor:**
- **Book component targeted:** (EQUITY_CORE / REGIME_BRAIN / LS_ALPHA / TREND_MACRO / OPTIONS /
  SHORT_HORIZON / EVENT / SIZING / ALLOCATOR / DEFENSE / FEEDER)
- **Builds on:** (prior runs / artifacts consumed)

## 1. Hypothesis (falsifiable, quantified)

State the exact claim with a numeric threshold and horizon.

## 2. Data and universe

- Sources (with point-in-time / survivorship status stated explicitly)
- Development window end date (must be ≤ 2025-12-31 per the sealed holdout declaration)
- Signal lag convention (minimum 1 week for weekly systems)

## 3. Locked design

- Signals / features (exact definitions)
- Parameter grids (exhaustive list — **no grid may be added mid-run**)
- Baselines and benchmarks
- Walk-forward / split scheme (time-ordered only)

## 4. Primary metrics (return-first)

Net CAGR, expected log growth, per-state expectancy, residual alpha (vs SPY + standard factors).
Ranking of candidates uses these only.

## 5. Recorded, non-gating metrics

Volatility, max drawdown, CVaR, Sharpe, turnover, concentration — reported in every table,
never used as pass/fail during discovery.

## 6. Costs

Per-instrument costs from `data/research/atlas_offensive_cost_library.csv`; report every
portfolio result at 1x and 2x costs. The 10bps flat assumption is retired.

## 7. Null controls

Specify before running: random-placement count, shuffled/inverted signal controls, and the
percentile threshold a headline claim must beat.

## 8. Success / failure criteria

- **Success:** (exact numeric conditions)
- **Failure:** (exact numeric conditions and the branch taken on failure)
- **Ambiguous:** (what verdict is recorded; at most one pre-registered follow-up experiment)

## 9. Prohibited actions

Consulting the sealed 2026+ holdout; tuning outside locked grids; touching production pins,
weights, or `public/dashboard-data.json`; `git add -A`; regenerating dashboard bundles.

## 10. Verdict vocabulary

`Adopt-into-Book` / `Confirm-in-follow-up` / `Research-only` / `Drop` — plus run-level
statuses `BLOCKED_PREREQUISITE` and `VOID_HOLDOUT_CONTAMINATION` where applicable.
Nothing is promoted without explicit human authorization.
