# Research Committee Audit — improved_phasemm_recovery_confirmed_sleeve_fix

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasemm_recovery_confirmed_sleeve_fix` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-07` → `2026-04-10` (1110 weeks).

```
      metric  improved_phasemm_recovery_confirmed_sleeve_fix (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasemm_recovery_confirmed_sleeve_fix (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                                 0.0690                                           0.0689      0.0001                                                    0.1243                                              0.1243        -0.0000
     ann_vol                                                 0.0780                                           0.0779      0.0001                                                    0.0767                                              0.0765         0.0002
      sharpe                                                 0.8853                                           0.8848      0.0005                                                    1.6214                                              1.6249        -0.0035
max_drawdown                                                -0.1398                                          -0.1398     -0.0000                                                   -0.0626                                             -0.0626         0.0000
      cvar_5                                                -0.0262                                          -0.0262     -0.0000                                                   -0.0210                                             -0.0210        -0.0000
      calmar                                                 0.4939                                           0.4932      0.0007                                                    1.9849                                              1.9850        -0.0001
```

## Bull Case

- Full-window Sharpe **0.885** vs production **0.885** (Δ +0.000).

## Bear Case

- Holdout annualised return **12.43%** vs production **12.43%** — surrogate gives up **0.00pp** of return.

## Risk Manager Check

- max drawdown delta vs production: -0.00pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: -0.00pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: -0.00pp
- holdout sharpe delta vs production: -0.004 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1127 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 28.42% vs 28.39%
- avg SPY exposure (cand vs prod): 7.12% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      493          0.0021          0.0021           0.0000         0.0105         0.0105
        calm_trend      295          0.0008          0.0008          -0.0000         0.0128         0.0128
    stressed_panic      229          0.0007          0.0007           0.0000         0.0094         0.0094
  recovery_fragile       49          0.0013          0.0013           0.0000         0.0073         0.0073
recovery_confirmed       44          0.0006          0.0005           0.0000         0.0094         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-07 → 2026-04-10, 1110 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

See `reports/backtest_realism/improved_phasemm_recovery_confirmed_sleeve_fix_realism_audit.md` for cost / delay / turnover / liquidity sensitivities.

## Allocator Benchmark Summary (Layer 6 hand-off)

See `reports/allocator_benchmark/improved_phasemm_recovery_confirmed_sleeve_fix_allocator_benchmark.md` for EW / IV / ERC / HRP comparisons.

## Final Recommendation

**Verdict: KEEP AS SHADOW (research reference).**

Candidate is competitive on risk-adjusted axes but does not pass the production return-delta gate.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

