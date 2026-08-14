# Backtest Realism Audit — improved_phasebb_w1cap_060_hrp_7sleeve

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0388           0.0628           -0.0239       0.9947       0.8009        0.1938      -0.0690     -0.0126       0.5628
              5           0.0376           0.0612           -0.0237       0.9623       0.7812        0.1811      -0.0692     -0.0127       0.5425
             10           0.0363           0.0597           -0.0234       0.9299       0.7615        0.1684      -0.0695     -0.0127       0.5225
             25           0.0325           0.0550           -0.0225       0.8327       0.7025        0.1303      -0.0704     -0.0128       0.4617
             50           0.0262           0.0473           -0.0211       0.6713       0.6044        0.0669      -0.0768     -0.0129       0.3418
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0376           0.0612           -0.0237       0.9623        0.1811      -0.0692
           1           0.0358           0.0510           -0.0151       0.9213        0.2798      -0.0650
           5           0.0292           0.0411           -0.0119       0.6996        0.2397      -0.0926
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0376           0.0612           -0.0237       0.9623        0.1811
         0.0050           0.0380           0.0614           -0.0234       0.9745        0.1908
         0.0100           0.0380           0.0610           -0.0231       0.9645        0.1871
```

## Realism Verdict

- Δ ann return at 5bp (baseline): -2.37pp
- Δ ann return at 10bp (doubled): -2.34pp
- Δ ann return with 1-week delay: -1.51pp

**Verdict: candidate does NOT survive doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
