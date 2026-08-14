# Backtest Realism Audit — improved_phase6_continuous_aggression_score

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0721           0.0628            0.0093       0.8762       0.8009        0.0754      -0.1516     -0.0277       0.4754
              5           0.0700           0.0612            0.0088       0.8510       0.7812        0.0699      -0.1521     -0.0278       0.4606
             10           0.0680           0.0597            0.0083       0.8259       0.7615        0.0644      -0.1525     -0.0278       0.4458
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0700           0.0612            0.0088       0.8510        0.0699      -0.1521
           1           0.0572           0.0510            0.0062       0.6772        0.0356      -0.1536
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0700           0.0612            0.0088       0.8510        0.0699
         0.0050           0.0702           0.0614            0.0088       0.8532        0.0695
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.88pp
- Δ ann return at 10bp (doubled): +0.83pp
- Δ ann return with 1-week delay: +0.62pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
