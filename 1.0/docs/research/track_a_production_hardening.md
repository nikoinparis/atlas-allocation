# Track A Production Conservative Allocator Hardening

## Current Production Candidate

The official production candidate is `improved_frontier_phase5_fragility_guard`.
The source of truth is `data/05_layer3_portfolio_construction/production_candidate_registry.json`, where both `current_production_pin` and `production_candidate` point to that name.

The prior production pin, `improved_phase2b_regime_confidence_boost`, is retained as the rollback reference. The official shadow is `improved_phase2b_combo_abc`.

## Production Pipeline

The production system is wrapper-based, not a fully native allocator.

Pipeline:

1. Start from saved GGG final ETF weights: `improved_phaseggg_confirmed_only_robust_offense`.
2. Apply the canonical Frontier Phase 5 post-processor at the `offense_budget` checkpoint.
3. Recompute gross returns, one-way turnover, transaction costs, net returns, wealth, and drawdown with canonical production cost logic.
4. Compare the recomputed path to the saved production return and weight artifacts.

The canonical wrapper implementation lives in `scripts/production_allocator.py`.

## Wrapper Logic

The post-processor applies:

- Phase 1 R2A offense scale: `1 + 0.08 * clip(r2a, -1, 1)` outside `stressed_panic`.
- Phase 4 fragility guard: when `leadership_quality_composite > 0.50`, cap the offense boost at `1.0`.
- `stressed_panic`: force scale to `1.0`, preserving base stressed-panic offense behavior.

The relevant source data is:

- `data/research/frontier_phase1/state_quality_signals_r2.csv`
- `data/research/frontier_phase4/leadership_signals.csv`

## Data And Timing Assumptions

Production path recomputation uses saved final ETF weights and weekly close-to-close forward returns from weekly prices. The convention is Friday-close decision weights applied to next-week returns via `prices.pct_change().shift(-1)`.

This sprint does not prove live tradability at the next open and does not model market impact, borrow, taxes, intraday slippage, or brokerage-specific execution.

## Cost And Turnover Convention

Canonical module: `scripts/production_costs.py`.

- Turnover is one-way turnover: `0.5 * sum(abs(current_weight - prior_weight))`.
- The first row has undefined turnover and zero cost.
- Cost is decimal return drag: `one_way_turnover * cost_bps / 10000`.
- Production default is `10 bps` per unit of one-way turnover.
- Weekly turnover is averaged for `avg_weekly_turnover` and multiplied by `52` for annualized turnover.

## Metrics Convention

Canonical module: `scripts/production_metrics.py`.

- `ann_return` is CAGR/geometric annual return, kept under the old column name for compatibility.
- `arithmetic_ann_return` is reported separately as weekly mean times `52`.
- `ann_vol` is sample annualized weekly volatility with `ddof=1`.
- `sharpe` is `CAGR / ann_vol` with zero risk-free rate.
- `var_5` and `cvar_5` are weekly 5% tail metrics on the evaluated window.
- `max_drawdown` is computed from cumulative net returns.
- `calmar` is `CAGR / abs(max_drawdown)`.

Important convention note: some older helper code used `ddof=0` volatility, which slightly raised Sharpe for the same return series. The canonical convention matches the promoted production summary and registry.

## Holdout Period

The official holdout start date is `2024-04-19`.

The holdout is not pristine in a strict research sense because the project has repeatedly inspected holdout performance across many experiments. Track A treats holdout results as governance evidence, not as untouched discovery evidence.

## Validation Governance

Track A uses `scripts/run_track_a_validation_governance.py` to write:

- `data/research/track_a_production_hardening/experiment_registry_snapshot.csv`
- `data/research/track_a_production_hardening/production_promotion_gate_report.csv`
- `data/research/track_a_production_hardening/track_a_validation_governance_summary.json`

The statistical audit in `data/research/validation/statistical_validation_audit.csv` scanned 358 return series and estimated 3,869 trials across 154 files. Every scanned candidate was marked `overfit_risk`. The current production artifact was promoted by human authorization and exact reproduction checks, not by claiming the multiple-testing problem is solved.

Future production promotion requires explicit registry changes, exact reproduction, canonical metric/cost reports, holdout review, cost sensitivity, dashboard verification, and manual authorization.

## Dashboard Packaging

Canonical dashboard build script:

```bash
python3 scripts/build_production_candidate_dashboard_bundle.py
```

Canonical dashboard verifier:

```bash
python3 scripts/verify_dashboard_packaging.py
```

The dashboard reads compact bundle files under `public/`, especially `public/production-candidate-dashboard-bundle.json`. The old monolithic `public/dashboard-data.json` is not an active dependency.

## Known Limitations

- Production is conservative and return-capped by design.
- The production sleeve-weight artifact is a proxy because the candidate is a final-weight wrapper modifier.
- The candidate has only modest improvement versus the prior production and shadow references.
- The statistical audit warns that broad repeated experimentation creates false-confidence risk.
- Exact reproduction depends on saved weekly price-derived forward returns and saved final ETF weights.

## Out Of Scope For Track A

- New alpha strategies.
- Parameter tuning.
- ML models.
- New production candidates.
- Promotion or de-promotion decisions.
- Rewriting the native allocator.
- Changing the economic behavior of the production candidate.
