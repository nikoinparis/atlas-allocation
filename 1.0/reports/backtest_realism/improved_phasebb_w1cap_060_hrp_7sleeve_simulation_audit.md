# Robustness Simulation Audit — improved_phasebb_w1cap_060_hrp_7sleeve

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-14 → 2026-04-10 (1109 weeks)

**Bootstrap method:** moving-block bootstrap, block=26 weeks, samples=1000.

## Bootstrap confidence intervals (90% CI, block=26w)

```
    series       metric  point_estimate  ci_lo_5pct  ci_hi_95pct  n_samples
 candidate   ann_return          0.0376      0.0246       0.0521       1000
 candidate       sharpe          0.9623      0.6144       1.3614       1000
 candidate max_drawdown         -0.0692     -0.1065      -0.0507       1000
 candidate       cvar_5         -0.0127     -0.0150      -0.0106       1000
production   ann_return          0.0690      0.0459       0.0945       1000
production       sharpe          0.8852      0.5722       1.2545       1000
production max_drawdown         -0.1398     -0.1913      -0.0907       1000
production       cvar_5         -0.0262     -0.0304      -0.0222       1000
```

## Worst Rolling Windows

```
 window_weeks  cand_worst cand_start   cand_end  prod_worst prod_start   prod_end  delta_cand_minus_prod
           13      -5.10% 2008-07-11 2008-10-03     -10.37% 2019-12-20 2020-03-13                 +5.27%
           26      -4.73% 2008-04-18 2008-10-10     -10.47% 2019-09-20 2020-03-13                 +5.74%
           52      -6.22% 2015-01-23 2016-01-15      -8.00% 2015-01-23 2016-01-15                 +1.78%
```

## Stress-state-only performance

### stressed_panic

- candidate: n=229, mean wkly=+0.0004, min wkly=-0.0327
- production: n=229, mean wkly=+0.0007, min wkly=-0.0568
- candidate vs production mean wkly delta: -0.0003

### recovery_fragile

- candidate: n=49, mean wkly=+0.0004, min wkly=-0.0119
- production: n=49, mean wkly=+0.0013, min wkly=-0.0202
- candidate vs production mean wkly delta: -0.0009

## Doubled-cost sensitivity

- candidate (doubled cost): ann return +3.63%, Sharpe 0.930, MDD -6.95%
- production (doubled cost): ann return +6.82%, Sharpe 0.875, MDD -13.99%
- delta ann return: -3.19pp

## Robustness Verdict

**Bootstrap 5%-quantile annual return of candidate does NOT exceed 95%-quantile of production** (overlap exists).

- point-estimate annualised return: cand +3.76% vs prod +6.90%
- point-estimate Sharpe: cand 0.962 vs prod 0.885

