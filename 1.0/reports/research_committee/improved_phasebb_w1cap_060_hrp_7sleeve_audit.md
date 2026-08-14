# Research Committee Audit — improved_phasebb_w1cap_060_hrp_7sleeve

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasebb_w1cap_060_hrp_7sleeve` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-14` → `2026-04-10` (1109 weeks).

```
      metric  improved_phasebb_w1cap_060_hrp_7sleeve (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasebb_w1cap_060_hrp_7sleeve (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                         0.0376                                           0.0690     -0.0314                                            0.0815                                              0.1243        -0.0429
     ann_vol                                         0.0390                                           0.0779     -0.0389                                            0.0367                                              0.0765        -0.0398
      sharpe                                         0.9623                                           0.8852      0.0770                                            2.2214                                              1.6249         0.5965
max_drawdown                                        -0.0692                                          -0.1398      0.0705                                           -0.0275                                             -0.0626         0.0351
      cvar_5                                        -0.0127                                          -0.0262      0.0135                                           -0.0090                                             -0.0210         0.0120
      calmar                                         0.5425                                           0.4936      0.0489                                            2.9614                                              1.9850         0.9764
```

## Bull Case

- Full-window Sharpe **0.962** vs production **0.885** (Δ +0.077).
- Holdout (last 156w) Sharpe **2.221** vs production **1.625** (Δ +0.596).
- Full-window max drawdown **-6.92%** vs production **-13.98%** — shallower drawdown.
- Full-window CVaR-5% **-1.27%** vs production **-2.62%** — better tail.

## Bear Case

- Full-window annualised return **3.76%** vs production **6.90%** — surrogate gives up **3.14pp** of return.
- Holdout annualised return **8.15%** vs production **12.43%** — surrogate gives up **4.29pp** of return.

## Risk Manager Check

- max drawdown delta vs production: +7.05pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: +1.35pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: -4.29pp
- holdout sharpe delta vs production: +0.596 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.0937 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 57.72% vs 28.39%
- avg SPY exposure (cand vs prod): 3.67% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      492          0.0011          0.0021          -0.0010         0.0049         0.0105
        calm_trend      295          0.0006          0.0008          -0.0002         0.0062         0.0128
    stressed_panic      229          0.0004          0.0007          -0.0003         0.0056         0.0094
  recovery_fragile       49          0.0004          0.0013          -0.0009         0.0047         0.0073
recovery_confirmed       44          0.0001          0.0005          -0.0005         0.0057         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-14 → 2026-04-10, 1109 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

See `reports/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_realism_audit.md` for cost / delay / turnover / liquidity sensitivities.

## Allocator Benchmark Summary (Layer 6 hand-off)

See `reports/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_allocator_benchmark.md` for EW / IV / ERC / HRP comparisons.

## Final Recommendation

**Verdict: KEEP AS SHADOW.**

Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

