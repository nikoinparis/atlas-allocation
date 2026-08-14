# Research Committee Audit — improved_phasegg_hint_inallocator_10

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasegg_hint_inallocator_10` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-07` → `2026-04-10` (1110 weeks).

```
      metric  improved_phasegg_hint_inallocator_10 (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasegg_hint_inallocator_10 (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                       0.0686                                           0.0689     -0.0003                                          0.1246                                              0.1243         0.0002
     ann_vol                                       0.0781                                           0.0779      0.0002                                          0.0767                                              0.0765         0.0002
      sharpe                                       0.8785                                           0.8848     -0.0063                                          1.6246                                              1.6249        -0.0003
max_drawdown                                      -0.1408                                          -0.1398     -0.0011                                         -0.0622                                             -0.0626         0.0005
      cvar_5                                      -0.0263                                          -0.0262     -0.0001                                         -0.0211                                             -0.0210        -0.0001
      calmar                                       0.4869                                           0.4932     -0.0063                                          2.0034                                              1.9850         0.0184
```

## Bull Case

- No clear axis on which the surrogate beats production at full or holdout window.

## Bear Case

- Full-window annualised return **6.86%** vs production **6.89%** — surrogate gives up **0.03pp** of return.

## Risk Manager Check

- max drawdown delta vs production: -0.11pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.01pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: +0.02pp
- holdout sharpe delta vs production: -0.000 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1125 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 28.40% vs 28.39%
- avg SPY exposure (cand vs prod): 7.09% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      493          0.0021          0.0021          -0.0000         0.0105         0.0105
        calm_trend      295          0.0007          0.0008          -0.0000         0.0129         0.0128
    stressed_panic      229          0.0007          0.0007          -0.0000         0.0094         0.0094
  recovery_fragile       49          0.0013          0.0013          -0.0000         0.0072         0.0073
recovery_confirmed       44          0.0005          0.0005          -0.0000         0.0093         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-07 → 2026-04-10, 1110 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phasegg_hint_inallocator_10`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phasegg_hint_inallocator_10`._

## Final Recommendation

**Verdict: KEEP AS SHADOW (research reference).**

Candidate is competitive on risk-adjusted axes but does not pass the production return-delta gate.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

