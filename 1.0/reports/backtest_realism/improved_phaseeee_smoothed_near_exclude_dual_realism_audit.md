# Backtest Realism Audit — improved_phaseeee_smoothed_near_exclude_dual

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0655           0.0628            0.0027       0.8552       0.8009        0.0543      -0.1270     -0.0261       0.5157
              5           0.0638           0.0612            0.0026       0.8329       0.7812        0.0518      -0.1273     -0.0261       0.5012
             10           0.0621           0.0597            0.0024       0.8107       0.7615        0.0492      -0.1275     -0.0261       0.4868
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0638           0.0612            0.0026       0.8329        0.0518      -0.1273
           1           0.0547           0.0510            0.0037       0.7028        0.0612      -0.1290
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0638           0.0612            0.0026       0.8329        0.0518
         0.0050           0.0640           0.0614            0.0026       0.8348        0.0511
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.26pp
- Δ ann return at 10bp (doubled): +0.24pp
- Δ ann return with 1-week delay: +0.37pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
