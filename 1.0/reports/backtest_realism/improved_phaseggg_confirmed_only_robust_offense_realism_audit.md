# Backtest Realism Audit — improved_phaseggg_confirmed_only_robust_offense

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0656           0.0628            0.0029       0.8566       0.8009        0.0558      -0.1270     -0.0261       0.5167
              5           0.0639           0.0612            0.0027       0.8343       0.7812        0.0532      -0.1273     -0.0261       0.5021
             10           0.0622           0.0597            0.0025       0.8120       0.7615        0.0505      -0.1275     -0.0262       0.4876
             25           0.0571           0.0550            0.0021       0.7452       0.7025        0.0427      -0.1284     -0.0263       0.4446
             50           0.0486           0.0473            0.0013       0.6341       0.6044        0.0298      -0.1298     -0.0265       0.3747
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0639           0.0612            0.0027       0.8343        0.0532      -0.1273
           1           0.0546           0.0510            0.0036       0.7014        0.0598      -0.1292
           5           0.0434           0.0411            0.0023       0.5001        0.0402      -0.1959
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0639           0.0612            0.0027       0.8343        0.0532
         0.0050           0.0641           0.0614            0.0027       0.8361        0.0524
         0.0100           0.0643           0.0610            0.0032       0.8373        0.0599
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.27pp
- Δ ann return at 10bp (doubled): +0.25pp
- Δ ann return with 1-week delay: +0.36pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
