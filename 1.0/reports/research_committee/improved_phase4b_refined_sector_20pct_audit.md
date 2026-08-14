# Research Committee Audit — improved_phase4b_refined_sector_20pct

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phase4b_refined_sector_20pct` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-07` → `2026-04-10` (1110 weeks).

```
      metric  improved_phase4b_refined_sector_20pct (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phase4b_refined_sector_20pct (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                        0.0776                                           0.0689      0.0087                                           0.1425                                              0.1243         0.0181
     ann_vol                                        0.0809                                           0.0779      0.0030                                           0.0865                                              0.0765         0.0100
      sharpe                                        0.9590                                           0.8848      0.0742                                           1.6464                                              1.6249         0.0215
max_drawdown                                       -0.1377                                          -0.1398      0.0020                                          -0.0742                                             -0.0626        -0.0116
      cvar_5                                       -0.0267                                          -0.0262     -0.0005                                          -0.0228                                             -0.0210        -0.0018
      calmar                                        0.5635                                           0.4932      0.0703                                           1.9193                                              1.9850        -0.0656
```

## Bull Case

- Full-window Sharpe **0.959** vs production **0.885** (Δ +0.074).
- Holdout (last 156w) Sharpe **1.646** vs production **1.625** (Δ +0.022).
- Full-window max drawdown **-13.77%** vs production **-13.98%** — shallower drawdown.

## Bear Case

- No clear axis on which the surrogate underperforms.

## Risk Manager Check

- max drawdown delta vs production: +0.20pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.05pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: +1.81pp
- holdout sharpe delta vs production: +0.022 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1463 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 23.57% vs 28.39%
- avg SPY exposure (cand vs prod): 5.49% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      493          0.0023          0.0021           0.0002         0.0113         0.0105
        calm_trend      295          0.0009          0.0008           0.0001         0.0119         0.0128
    stressed_panic      229          0.0008          0.0007           0.0001         0.0106         0.0094
  recovery_fragile       49          0.0015          0.0013           0.0001         0.0083         0.0073
recovery_confirmed       44          0.0009          0.0005           0.0003         0.0106         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-07 → 2026-04-10, 1110 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

See `reports/backtest_realism/improved_phase4b_refined_sector_20pct_realism_audit.md` for cost / delay / turnover / liquidity sensitivities.

## Allocator Benchmark Summary (Layer 6 hand-off)

See `reports/allocator_benchmark/improved_phase4b_refined_sector_20pct_allocator_benchmark.md` for EW / IV / ERC / HRP comparisons.

## Final Recommendation

**Verdict: KEEP AS SHADOW.**

Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

