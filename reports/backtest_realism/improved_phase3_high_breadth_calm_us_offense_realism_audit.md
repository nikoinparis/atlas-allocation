# Backtest Realism Audit — improved_phase3_high_breadth_calm_us_offense

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0673           0.0628            0.0045       0.8903       0.8009        0.0894      -0.1262     -0.0255       0.5332
              5           0.0654           0.0612            0.0042       0.8659       0.7812        0.0847      -0.1265     -0.0255       0.5175
             10           0.0636           0.0597            0.0040       0.8416       0.7615        0.0801      -0.1267     -0.0256       0.5020
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0654           0.0612            0.0042       0.8659        0.0847      -0.1265
           1           0.0558           0.0510            0.0048       0.7266        0.0850      -0.1258
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0654           0.0612            0.0042       0.8659        0.0847
         0.0050           0.0657           0.0614            0.0043       0.8693        0.0856
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.42pp
- Δ ann return at 10bp (doubled): +0.40pp
- Δ ann return with 1-week delay: +0.48pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
