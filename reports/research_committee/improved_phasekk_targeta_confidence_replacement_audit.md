# Research Committee Audit — improved_phasekk_targeta_confidence_replacement

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasekk_targeta_confidence_replacement` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-07` → `2026-04-10` (1110 weeks).

```
      metric  improved_phasekk_targeta_confidence_replacement (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasekk_targeta_confidence_replacement (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                                  0.0699                                           0.0689      0.0009                                                     0.1262                                              0.1243         0.0019
     ann_vol                                                  0.0790                                           0.0779      0.0011                                                     0.0780                                              0.0765         0.0015
      sharpe                                                  0.8838                                           0.8848     -0.0010                                                     1.6179                                              1.6249        -0.0070
max_drawdown                                                 -0.1451                                          -0.1398     -0.0053                                                    -0.0628                                             -0.0626        -0.0002
      cvar_5                                                 -0.0265                                          -0.0262     -0.0004                                                    -0.0214                                             -0.0210        -0.0004
      calmar                                                  0.4816                                           0.4932     -0.0116                                                     2.0080                                              1.9850         0.0230
```

## Bull Case

- No clear axis on which the surrogate beats production at full or holdout window.

## Bear Case

- No clear axis on which the surrogate underperforms.

## Risk Manager Check

- max drawdown delta vs production: -0.53pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.04pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: +0.19pp
- holdout sharpe delta vs production: -0.007 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1129 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 27.61% vs 28.39%
- avg SPY exposure (cand vs prod): 7.14% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      493          0.0021          0.0021           0.0000         0.0107         0.0105
        calm_trend      295          0.0008          0.0008           0.0000         0.0128         0.0128
    stressed_panic      229          0.0007          0.0007          -0.0000         0.0097         0.0094
  recovery_fragile       49          0.0013          0.0013           0.0000         0.0073         0.0073
recovery_confirmed       44          0.0005          0.0005          -0.0000         0.0095         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-07 → 2026-04-10, 1110 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phasekk_targeta_confidence_replacement`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phasekk_targeta_confidence_replacement`._

## Final Recommendation

**Verdict: KEEP AS SHADOW (research reference).**

Candidate is competitive on risk-adjusted axes but does not pass the production return-delta gate.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

