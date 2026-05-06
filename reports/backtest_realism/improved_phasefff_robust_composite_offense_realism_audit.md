# Backtest Realism Audit — improved_phasefff_robust_composite_offense

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0650           0.0628            0.0022       0.8366       0.8009        0.0357      -0.1302     -0.0266       0.4990
              5           0.0633           0.0612            0.0020       0.8147       0.7812        0.0335      -0.1304     -0.0266       0.4849
             10           0.0616           0.0597            0.0019       0.7929       0.7615        0.0314      -0.1307     -0.0266       0.4709
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0633           0.0612            0.0020       0.8147        0.0335      -0.1304
           1           0.0555           0.0510            0.0046       0.7027        0.0611      -0.1317
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0633           0.0612            0.0020       0.8147        0.0335
         0.0050           0.0634           0.0614            0.0020       0.8157        0.0320
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.20pp
- Δ ann return at 10bp (doubled): +0.19pp
- Δ ann return with 1-week delay: +0.46pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
