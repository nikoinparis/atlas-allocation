# Robustness Simulation Audit — improved_phaseggg_confirmed_only_robust_offense

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Bootstrap method:** moving-block bootstrap, block=26 weeks, samples=1000.

## Bootstrap confidence intervals (90% CI, block=26w)

```
    series       metric  point_estimate  ci_lo_5pct  ci_hi_95pct  n_samples
 candidate   ann_return          0.0714      0.0485       0.0968       1000
 candidate       sharpe          0.9366      0.6242       1.2942       1000
 candidate max_drawdown         -0.1177     -0.1789      -0.0889       1000
 candidate       cvar_5         -0.0254     -0.0289      -0.0217       1000
production   ann_return          0.0689      0.0457       0.0952       1000
production       sharpe          0.8848      0.5771       1.2466       1000
production max_drawdown         -0.1398     -0.1921      -0.0915       1000
production       cvar_5         -0.0262     -0.0303      -0.0221       1000
```

## Worst Rolling Windows

```
 window_weeks  cand_worst cand_start   cand_end  prod_worst prod_start   prod_end  delta_cand_minus_prod
           13      -7.70% 2008-07-11 2008-10-03     -10.37% 2019-12-20 2020-03-13                 +2.67%
           26      -7.85% 2008-04-18 2008-10-10     -10.47% 2019-09-20 2020-03-13                 +2.61%
           52      -8.69% 2015-01-23 2016-01-15      -8.00% 2015-01-23 2016-01-15                 -0.69%
```

## Stress-state-only performance

### stressed_panic

- candidate: n=229, mean wkly=+0.0007, min wkly=-0.0683
- production: n=229, mean wkly=+0.0007, min wkly=-0.0568
- candidate vs production mean wkly delta: +0.0000

### recovery_fragile

- candidate: n=49, mean wkly=+0.0013, min wkly=-0.0227
- production: n=49, mean wkly=+0.0013, min wkly=-0.0202
- candidate vs production mean wkly delta: -0.0000

## Doubled-cost sensitivity

- candidate (doubled cost): ann return +7.05%, Sharpe 0.925, MDD -11.79%
- production (doubled cost): ann return +6.81%, Sharpe 0.875, MDD -13.99%
- delta ann return: +0.24pp

## Robustness Verdict

**Bootstrap 5%-quantile annual return of candidate does NOT exceed 95%-quantile of production** (overlap exists).

- point-estimate annualised return: cand +7.14% vs prod +6.89%
- point-estimate Sharpe: cand 0.937 vs prod 0.885

