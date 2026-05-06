# Backtest Realism Audit — improved_phasehh_refined_confidence_additive

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0628           0.0628            0.0001       0.8023       0.8009        0.0015      -0.1465     -0.0269       0.4288
              5           0.0613           0.0612            0.0001       0.7826       0.7812        0.0015      -0.1467     -0.0270       0.4176
             10           0.0597           0.0597            0.0001       0.7630       0.7615        0.0015      -0.1469     -0.0270       0.4065
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0613           0.0612            0.0001       0.7826        0.0015      -0.1467
           1           0.0512           0.0510            0.0002       0.6449        0.0033      -0.1416
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0613           0.0612            0.0001       0.7826        0.0015
         0.0050           0.0615           0.0614            0.0001       0.7854        0.0017
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.01pp
- Δ ann return at 10bp (doubled): +0.01pp
- Δ ann return with 1-week delay: +0.02pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
