# Backtest Realism Audit — improved_phasedd_hint_light

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0619           0.0628           -0.0008       0.8015       0.8009        0.0006      -0.1440     -0.0266       0.4303
              5           0.0604           0.0612           -0.0008       0.7815       0.7812        0.0003      -0.1442     -0.0267       0.4188
             10           0.0588           0.0597           -0.0008       0.7615       0.7615        0.0000      -0.1444     -0.0267       0.4075
             25           0.0542           0.0550           -0.0008       0.7016       0.7025       -0.0008      -0.1451     -0.0268       0.3736
             50           0.0465           0.0473           -0.0008       0.6021       0.6044       -0.0023      -0.1462     -0.0269       0.3182
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0604           0.0612           -0.0008       0.7815        0.0003      -0.1442
           1           0.0506           0.0510           -0.0004       0.6452        0.0036      -0.1388
           5           0.0409           0.0411           -0.0002       0.4625        0.0026      -0.2050
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0604           0.0612           -0.0008       0.7815        0.0003
         0.0050           0.0605           0.0614           -0.0009       0.7830       -0.0007
         0.0100           0.0604           0.0610           -0.0007       0.7797        0.0023
```

## Realism Verdict

- Δ ann return at 5bp (baseline): -0.08pp
- Δ ann return at 10bp (doubled): -0.08pp
- Δ ann return with 1-week delay: -0.04pp

**Verdict: candidate does NOT survive doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
