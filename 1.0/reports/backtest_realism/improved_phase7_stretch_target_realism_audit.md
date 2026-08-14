# Backtest Realism Audit — improved_phase7_stretch_target

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0729           0.0628            0.0101       0.8524       0.8009        0.0515      -0.1632     -0.0288       0.4467
              5           0.0706           0.0612            0.0094       0.8259       0.7812        0.0447      -0.1636     -0.0289       0.4316
             10           0.0684           0.0597            0.0087       0.7994       0.7615        0.0379      -0.1640     -0.0289       0.4167
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0706           0.0612            0.0094       0.8259        0.0447      -0.1636
           1           0.0565           0.0510            0.0055       0.6414       -0.0001      -0.1637
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0706           0.0612            0.0094       0.8259        0.0447
         0.0050           0.0705           0.0614            0.0091       0.8238        0.0401
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.94pp
- Δ ann return at 10bp (doubled): +0.87pp
- Δ ann return with 1-week delay: +0.55pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
