# Backtest Realism Audit — improved_phaseff_hint_inallocator_light

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0624           0.0628           -0.0003       0.7949       0.8009       -0.0060      -0.1501     -0.0270       0.4158
              5           0.0609           0.0612           -0.0003       0.7752       0.7812       -0.0059      -0.1503     -0.0271       0.4049
             10           0.0593           0.0597           -0.0003       0.7556       0.7615       -0.0059      -0.1506     -0.0271       0.3940
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0609           0.0612           -0.0003       0.7752       -0.0059      -0.1503
           1           0.0511           0.0510            0.0002       0.6429        0.0013      -0.1456
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0609           0.0612           -0.0003       0.7752       -0.0059
         0.0050           0.0610           0.0614           -0.0004       0.7775       -0.0062
```

## Realism Verdict

- Δ ann return at 5bp (baseline): -0.03pp
- Δ ann return at 10bp (doubled): -0.03pp
- Δ ann return with 1-week delay: +0.02pp

**Verdict: candidate does NOT survive doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
