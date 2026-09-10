# Backtest Realism Audit — improved_phaseww_confirmed_only_lighter_both

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0637           0.0628            0.0009       0.8056       0.8009        0.0048      -0.1501     -0.0271       0.4241
              5           0.0621           0.0612            0.0009       0.7855       0.7812        0.0044      -0.1503     -0.0271       0.4129
             10           0.0605           0.0597            0.0008       0.7654       0.7615        0.0040      -0.1505     -0.0272       0.4017
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0621           0.0612            0.0009       0.7855        0.0044      -0.1503
           1           0.0524           0.0510            0.0014       0.6551        0.0135      -0.1455
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0621           0.0612            0.0009       0.7855        0.0044
         0.0050           0.0622           0.0614            0.0008       0.7873        0.0036
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.09pp
- Δ ann return at 10bp (doubled): +0.08pp
- Δ ann return with 1-week delay: +0.14pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
