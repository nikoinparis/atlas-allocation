# GGG1 Production Candidate Packaging Review

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
- `docs/research/2026-04-27_ggg1_production_candidate_packaging_review.md`
- `docs/research/project_journey.md`

## Registry status

GGG1 is registered as `PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW`.
Current production and rollback remain `improved_phase2b_regime_confidence_boost`. Official shadow remains
`improved_phase2b_combo_abc`.

Latest research status:
`KEEP_GGG1_AS_PRODUCTION_CANDIDATE_AFTER_JJJ4_KKK_LLL_MMM`.

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

## Failed post-GGG1 research attempts

- JJJ4 adaptive risk-contribution allocation: failed to clearly improve or
  de-risk GGG1; final decision `KEEP_GGG1_AS_PRODUCTION_CANDIDATE`.
- LLL defense component rebuild: all defense-component rebuild candidates were
  rejected.
- MMM composite selective signals rebuild: all CSS rebuild candidates were
  rejected or failed turnover/quality gates.

## Caveats

- committee internal +0.30pp annual-return gate was not met exactly
- bootstrap confidence intervals overlap
- worst single week is worse than production
- turnover is close to the 1.10x limit
- human deployment review still required

## Final packaging recommendation

**READY FOR HUMAN DEPLOYMENT REVIEW.**

## Manual deployment checklist

1. Verify Vercel dashboard loads.
2. Verify compact bundle loads.
3. Verify old production rollback files exist.
4. Verify GGG1 return/weight/sleeve files exist.
5. Verify registry is correct.
6. Verify no giant `dashboard-data.json` is tracked.
7. Review caveats before officially flipping production pin.
8. After human approval, optionally update `current_production_pin` to GGG1 in a separate commit.
