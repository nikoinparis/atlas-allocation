# Backtest Realism Audit — improved_phase4_sector_20pct_offense

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0705           0.0628            0.0078       0.8534       0.8009        0.0526      -0.1540     -0.0276       0.4579
              5           0.0683           0.0612            0.0071       0.8271       0.7812        0.0460      -0.1542     -0.0276       0.4431
             10           0.0662           0.0597            0.0065       0.8009       0.7615        0.0394      -0.1545     -0.0277       0.4283
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0683           0.0612            0.0071       0.8271        0.0460      -0.1542
           1           0.0564           0.0510            0.0055       0.6675        0.0259      -0.1535
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0683           0.0612            0.0071       0.8271        0.0460
         0.0050           0.0684           0.0614            0.0070       0.8276        0.0439
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.71pp
- Δ ann return at 10bp (doubled): +0.65pp
- Δ ann return with 1-week delay: +0.55pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
