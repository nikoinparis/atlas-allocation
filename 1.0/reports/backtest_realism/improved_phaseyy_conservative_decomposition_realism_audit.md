# Backtest Realism Audit — improved_phaseyy_conservative_decomposition

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0641           0.0628            0.0013       0.8483       0.8009        0.0475      -0.1267     -0.0257       0.5055
              5           0.0624           0.0612            0.0012       0.8266       0.7812        0.0455      -0.1270     -0.0257       0.4915
             10           0.0608           0.0597            0.0011       0.8049       0.7615        0.0435      -0.1273     -0.0257       0.4776
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0624           0.0612            0.0012       0.8266        0.0455      -0.1270
           1           0.0535           0.0510            0.0025       0.6961        0.0546      -0.1323
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0624           0.0612            0.0012       0.8266        0.0455
         0.0050           0.0626           0.0614            0.0012       0.8282        0.0445
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.12pp
- Δ ann return at 10bp (doubled): +0.11pp
- Δ ann return with 1-week delay: +0.25pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
