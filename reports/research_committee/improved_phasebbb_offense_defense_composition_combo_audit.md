# Research Committee Audit — improved_phasebbb_offense_defense_composition_combo

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** portfolio version

## Executive Verdict

## What Changed

- New portfolio version `improved_phasebbb_offense_defense_composition_combo` produced under the project's existing 5bp half-spread cost convention and last-Friday rebalance schedule.
- Compared against `improved_phase2b_regime_confidence_boost` on the same date range and same cost convention.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-07` → `2026-04-10` (1110 weeks).

```
      metric  improved_phasebbb_offense_defense_composition_combo (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasebbb_offense_defense_composition_combo (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                                      0.0713                                           0.0689      0.0024                                                         0.1465                                              0.1243         0.0222
     ann_vol                                                      0.0761                                           0.0779     -0.0018                                                         0.0806                                              0.0765         0.0041
      sharpe                                                      0.9368                                           0.8848      0.0520                                                         1.8173                                              1.6249         0.1924
max_drawdown                                                     -0.1175                                          -0.1398      0.0223                                                        -0.0728                                             -0.0626        -0.0102
      cvar_5                                                     -0.0253                                          -0.0262      0.0009                                                        -0.0220                                             -0.0210        -0.0010
      calmar                                                      0.6067                                           0.4932      0.1135                                                         2.0119                                              1.9850         0.0270
```

## Bull Case

- Full-window Sharpe **0.937** vs production **0.885** (Δ +0.052).
- Holdout (last 156w) Sharpe **1.817** vs production **1.625** (Δ +0.192).
- Full-window max drawdown **-11.75%** vs production **-13.98%** — shallower drawdown.
- Full-window CVaR-5% **-2.53%** vs production **-2.62%** — better tail.

## Bear Case

- No clear axis on which the surrogate underperforms.

## Risk Manager Check

- max drawdown delta vs production: +2.23pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: +0.09pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: +2.22pp
- holdout sharpe delta vs production: +0.192 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1226 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 26.66% vs 28.39%
- avg SPY exposure (cand vs prod): 6.08% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      493          0.0021          0.0021           0.0000         0.0106         0.0105
        calm_trend      295          0.0008          0.0008           0.0001         0.0110         0.0128
    stressed_panic      229          0.0007          0.0007           0.0000         0.0103         0.0094
  recovery_fragile       49          0.0013          0.0013          -0.0000         0.0080         0.0073
recovery_confirmed       44          0.0004          0.0005          -0.0001         0.0103         0.0093
```

## Implementation Audit

- Candidate kind: portfolio
- Same date range: PASS (2005-01-07 → 2026-04-10, 1110 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phasebbb_offense_defense_composition_combo`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phasebbb_offense_defense_composition_combo`._

## Final Recommendation

**Verdict: KEEP AS SHADOW.**

Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow.

Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.

