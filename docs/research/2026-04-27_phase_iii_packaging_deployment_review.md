# Phase III Packaging / Deployment Review

Date: 2026-04-27

## Commands executed

```
python3 scripts/phase_iii_packaging_review.py
```

## Files created / modified

- `scripts/phase_iii_packaging_review.py`
- `data/05_layer3_portfolio_construction/production_candidate_registry.json`
- `data/05_layer3_portfolio_construction/production_candidate_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_state_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_exposure_summary.csv`
- `public/production-candidate-dashboard-bundle.json`
- `public/dashboard-summary.json`
- `public/dashboard-timeseries.json`
- `public/dashboard-state-summary.json`
- `public/dashboard-exposures.json`
- `docs/research/2026-04-27_phase_iii_packaging_deployment_review.md`
- `docs/research/project_journey.md`
- `CLAUDE.md`

## Registry status

GGG1 is registered as `PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW`.
Current production and rollback remain `improved_phase2b_regime_confidence_boost`. Official shadow remains
`improved_phase2b_combo_abc`.

## Dashboard / export bundle status

Created lightweight dashboard/export bundle:

- `production_candidate_summary.csv`
- `production_candidate_state_summary.csv`
- `production_candidate_exposure_summary.csv`
- `public/production-candidate-dashboard-bundle.json`
- `public/dashboard-summary.json`
- `public/dashboard-timeseries.json`
- `public/dashboard-state-summary.json`
- `public/dashboard-exposures.json`

The full dashboard payload was not rebuilt and the old production row was not
removed.

## GGG1 vs production

- annual return: 7.14% vs 6.89% (+0.246pp)
- Sharpe: 0.9366 vs 0.8848 (+0.0518)
- max drawdown: -11.77% vs -13.98% (+2.20pp)
- CVaR-5%: -2.54% vs -2.62% (+0.08pp)
- holdout Sharpe: 1.8224 vs 1.6249 (+0.1975)
- avg SPY: 6.03% vs 7.08% (-1.06pp)
- turnover ratio: 1.0998x

## GGG1 vs official shadow

- annual return delta: +0.280pp
- Sharpe delta: +0.0526
- max drawdown delta: +1.90pp
- CVaR-5% delta: +0.07pp
- holdout Sharpe delta: +0.1947

## Audit checklist

Phase III promotion checklist: 18/18 passed.
Research committee remains `KEEP AS SHADOW` due to the internal +0.30pp
annual-return gate. Realism audit passes doubled cost. Allocator benchmark
passes. Robustness simulation point estimates beat production, but bootstrap
intervals overlap.

## Caveats

- committee internal +0.30pp annual-return gate was not met exactly
- bootstrap confidence intervals overlap
- worst single week is worse than production
- human deployment review still required

## Final packaging recommendation

**READY FOR HUMAN DEPLOYMENT REVIEW.**

## Exact next manual steps

1. Human reviewer confirms GGG1 deployment acceptance despite the listed caveats.
2. If accepted, update the live production pin in the dashboard/app config in a separate deployment PR.
3. Preserve `improved_phase2b_regime_confidence_boost` as rollback in the registry and deployment notes.
4. Rebuild the full dashboard payload only after the human deployment decision.
