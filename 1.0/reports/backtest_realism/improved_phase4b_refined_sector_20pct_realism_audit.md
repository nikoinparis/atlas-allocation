# Backtest Realism Audit — improved_phase4b_refined_sector_20pct

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0717           0.0628            0.0090       0.8818       0.8009        0.0809      -0.1474     -0.0274       0.4863
              5           0.0697           0.0612            0.0085       0.8567       0.7812        0.0755      -0.1478     -0.0274       0.4713
             10           0.0676           0.0597            0.0080       0.8317       0.7615        0.0702      -0.1482     -0.0275       0.4563
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0697           0.0612            0.0085       0.8567        0.0755      -0.1478
           1           0.0573           0.0510            0.0063       0.6870        0.0454      -0.1484
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0697           0.0612            0.0085       0.8567        0.0755
         0.0050           0.0699           0.0614            0.0085       0.8596        0.0759
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.85pp
- Δ ann return at 10bp (doubled): +0.80pp
- Δ ann return with 1-week delay: +0.63pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
