# Backtest Realism Audit — improved_phase2_aggressive_neutral_cash_unlock

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0679           0.0628            0.0051       0.8596       0.8009        0.0588      -0.1348     -0.0268       0.5035
              5           0.0661           0.0612            0.0049       0.8376       0.7812        0.0564      -0.1351     -0.0268       0.4896
             10           0.0644           0.0597            0.0047       0.8155       0.7615        0.0540      -0.1354     -0.0268       0.4758
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0661           0.0612            0.0049       0.8376        0.0564      -0.1351
           1           0.0563           0.0510            0.0054       0.7025        0.0609      -0.1315
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0661           0.0612            0.0049       0.8376        0.0564
         0.0050           0.0664           0.0614            0.0050       0.8398        0.0561
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.49pp
- Δ ann return at 10bp (doubled): +0.47pp
- Δ ann return with 1-week delay: +0.54pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
