# Research Committee Audit — improved_phaseee_sleeve_hint_light

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phaseee_sleeve_hint_light` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-14` → `2026-04-10` (1109 weeks).

```
      metric  improved_phaseee_sleeve_hint_light (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phaseee_sleeve_hint_light (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                     0.0611                                           0.0690     -0.0079                                        0.1165                                              0.1243        -0.0078
     ann_vol                                     0.0783                                           0.0779      0.0003                                        0.0764                                              0.0765        -0.0001
      sharpe                                     0.7807                                           0.8852     -0.1046                                        1.5255                                              1.6249        -0.0994
max_drawdown                                    -0.1496                                          -0.1398     -0.0098                                       -0.0639                                             -0.0626        -0.0012
      cvar_5                                    -0.0269                                          -0.0262     -0.0007                                       -0.0214                                             -0.0210        -0.0004
      calmar                                     0.4086                                           0.4936     -0.0850                                        1.8245                                              1.9850        -0.1604
```

## Bull Case

- No clear axis on which the surrogate beats production at full or holdout window.

## Bear Case

- Full-window annualised return **6.11%** vs production **6.90%** — surrogate gives up **0.79pp** of return.
- Holdout annualised return **11.65%** vs production **12.43%** — surrogate gives up **0.78pp** of return.

## Risk Manager Check

- max drawdown delta vs production: -0.98pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.07pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: -0.78pp
- holdout sharpe delta vs production: -0.099 (FAIL; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1138 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 28.48% vs 28.39%
- avg SPY exposure (cand vs prod): 7.08% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      492          0.0019          0.0021          -0.0001         0.0105         0.0105
        calm_trend      295          0.0006          0.0008          -0.0001         0.0129         0.0128
    stressed_panic      229          0.0005          0.0007          -0.0002         0.0095         0.0094
  recovery_fragile       49          0.0013          0.0013          -0.0001         0.0073         0.0073
recovery_confirmed       44          0.0004          0.0005          -0.0001         0.0093         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-14 → 2026-04-10, 1109 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phaseee_sleeve_hint_light`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phaseee_sleeve_hint_light`._

## Final Recommendation

**Verdict: REJECT.**

Full-window annual return underperforms production by 0.79pp.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

