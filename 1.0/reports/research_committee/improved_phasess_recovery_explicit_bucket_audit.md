# Research Committee Audit — improved_phasess_recovery_explicit_bucket

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasess_recovery_explicit_bucket` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-07` → `2026-04-10` (1110 weeks).

```
      metric  improved_phasess_recovery_explicit_bucket (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasess_recovery_explicit_bucket (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                            0.0698                                           0.0689      0.0008                                               0.1271                                              0.1243         0.0027
     ann_vol                                            0.0786                                           0.0779      0.0007                                               0.0778                                              0.0765         0.0013
      sharpe                                            0.8873                                           0.8848      0.0025                                               1.6327                                              1.6249         0.0078
max_drawdown                                           -0.1408                                          -0.1398     -0.0010                                              -0.0622                                             -0.0626         0.0005
      cvar_5                                           -0.0264                                          -0.0262     -0.0003                                              -0.0212                                             -0.0210        -0.0002
      calmar                                            0.4956                                           0.4932      0.0024                                               2.0437                                              1.9850         0.0588
```

## Bull Case

- Full-window Sharpe **0.887** vs production **0.885** (Δ +0.002).
- Holdout (last 156w) Sharpe **1.633** vs production **1.625** (Δ +0.008).

## Bear Case

- No clear axis on which the surrogate underperforms.

## Risk Manager Check

- max drawdown delta vs production: -0.10pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.03pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: +0.27pp
- holdout sharpe delta vs production: +0.008 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1148 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 28.13% vs 28.39%
- avg SPY exposure (cand vs prod): 7.28% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      493          0.0021          0.0021           0.0000         0.0106         0.0105
        calm_trend      295          0.0007          0.0008          -0.0000         0.0129         0.0128
    stressed_panic      229          0.0007          0.0007          -0.0000         0.0094         0.0094
  recovery_fragile       49          0.0015          0.0013           0.0001         0.0074         0.0073
recovery_confirmed       44          0.0006          0.0005           0.0001         0.0097         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-07 → 2026-04-10, 1110 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phasess_recovery_explicit_bucket`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phasess_recovery_explicit_bucket`._

## Final Recommendation

**Verdict: KEEP AS SHADOW (research reference).**

Candidate is competitive on risk-adjusted axes but does not pass the production return-delta gate.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

