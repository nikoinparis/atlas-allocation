# Research Committee Audit — improved_phasell_w1_bucket_ml_conditional

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasell_w1_bucket_ml_conditional` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-14` → `2026-04-10` (1109 weeks).

```
      metric  improved_phasell_w1_bucket_ml_conditional (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasell_w1_bucket_ml_conditional (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                            0.0601                                           0.0690     -0.0089                                               0.1157                                              0.1243        -0.0087
     ann_vol                                            0.0768                                           0.0779     -0.0012                                               0.0758                                              0.0765        -0.0007
      sharpe                                            0.7828                                           0.8852     -0.1025                                               1.5257                                              1.6249        -0.0992
max_drawdown                                           -0.1450                                          -0.1398     -0.0052                                              -0.0631                                             -0.0626        -0.0005
      cvar_5                                           -0.0264                                          -0.0262     -0.0002                                              -0.0213                                             -0.0210        -0.0003
      calmar                                            0.4146                                           0.4936     -0.0790                                               1.8330                                              1.9850        -0.1520
```

## Bull Case

- No clear axis on which the surrogate beats production at full or holdout window.

## Bear Case

- Full-window annualised return **6.01%** vs production **6.90%** — surrogate gives up **0.89pp** of return.
- Holdout annualised return **11.57%** vs production **12.43%** — surrogate gives up **0.87pp** of return.

## Risk Manager Check

- max drawdown delta vs production: -0.52pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.02pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: -0.87pp
- holdout sharpe delta vs production: -0.099 (FAIL; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1128 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 28.81% vs 28.39%
- avg SPY exposure (cand vs prod): 6.90% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      492          0.0019          0.0021          -0.0002         0.0103         0.0105
        calm_trend      295          0.0006          0.0008          -0.0002         0.0127         0.0128
    stressed_panic      229          0.0005          0.0007          -0.0001         0.0093         0.0094
  recovery_fragile       49          0.0012          0.0013          -0.0002         0.0072         0.0073
recovery_confirmed       44          0.0003          0.0005          -0.0002         0.0092         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-14 → 2026-04-10, 1109 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phasell_w1_bucket_ml_conditional`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phasell_w1_bucket_ml_conditional`._

## Final Recommendation

**Verdict: REJECT.**

Full-window annual return underperforms production by 0.89pp.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

