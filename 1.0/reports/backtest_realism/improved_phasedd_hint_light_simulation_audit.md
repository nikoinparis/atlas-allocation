# Robustness Simulation Audit — improved_phasedd_hint_light

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-14 → 2026-04-10 (1109 weeks)

**Bootstrap method:** moving-block bootstrap, block=26 weeks, samples=1000.

## Bootstrap confidence intervals (90% CI, block=26w)

```
    series       metric  point_estimate  ci_lo_5pct  ci_hi_95pct  n_samples
 candidate   ann_return          0.0604      0.0372       0.0856       1000
 candidate       sharpe          0.7815      0.4669       1.1519       1000
 candidate max_drawdown         -0.1442     -0.2046      -0.0951       1000
 candidate       cvar_5         -0.0267     -0.0310      -0.0225       1000
production   ann_return          0.0690      0.0459       0.0945       1000
production       sharpe          0.8852      0.5722       1.2545       1000
production max_drawdown         -0.1398     -0.1913      -0.0907       1000
production       cvar_5         -0.0262     -0.0304      -0.0222       1000
```

## Worst Rolling Windows

```
 window_weeks  cand_worst cand_start   cand_end  prod_worst prod_start   prod_end  delta_cand_minus_prod
           13     -10.88% 2019-12-20 2020-03-13     -10.37% 2019-12-20 2020-03-13                 -0.52%
           26     -11.07% 2019-09-20 2020-03-13     -10.47% 2019-09-20 2020-03-13                 -0.61%
           52      -8.26% 2015-01-23 2016-01-15      -8.00% 2015-01-23 2016-01-15                 -0.25%
```

## Stress-state-only performance

### stressed_panic

- candidate: n=229, mean wkly=+0.0005, min wkly=-0.0571
- production: n=229, mean wkly=+0.0007, min wkly=-0.0568
- candidate vs production mean wkly delta: -0.0002

### recovery_fragile

- candidate: n=49, mean wkly=+0.0012, min wkly=-0.0195
- production: n=49, mean wkly=+0.0013, min wkly=-0.0202
- candidate vs production mean wkly delta: -0.0001

## Doubled-cost sensitivity

- candidate (doubled cost): ann return +5.88%, Sharpe 0.762, MDD -14.44%
- production (doubled cost): ann return +6.82%, Sharpe 0.875, MDD -13.99%
- delta ann return: -0.94pp

## Robustness Verdict

**Bootstrap 5%-quantile annual return of candidate does NOT exceed 95%-quantile of production** (overlap exists).

- point-estimate annualised return: cand +6.04% vs prod +6.90%
- point-estimate Sharpe: cand 0.782 vs prod 0.885

