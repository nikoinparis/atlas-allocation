# Backtest Realism Audit — improved_phasesss3_calm_old_low_stress_derisk

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Date range:** 2005-01-07 → 2026-04-10 (1110 weeks)

**Cost convention baseline:** 5bp half-spread (project default).

**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.

## Cost Sensitivity

Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)

```
 halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  prod_sharpe  delta_sharpe  cand_max_dd  cand_cvar5  cand_calmar
              0           0.0656           0.0628            0.0029       0.8587       0.8009        0.0579      -0.1252     -0.0260       0.5244
              5           0.0639           0.0612            0.0027       0.8364       0.7812        0.0552      -0.1255     -0.0261       0.5096
             10           0.0622           0.0597            0.0026       0.8140       0.7615        0.0525      -0.1257     -0.0261       0.4949
```

## Rebalance Delay Sensitivity

Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).

```
 delay_weeks  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe  cand_max_dd
           0           0.0639           0.0612            0.0027       0.8364        0.0552      -0.1255
           1           0.0547           0.0510            0.0037       0.7034        0.0618      -0.1292
```

## Turnover-Threshold Sensitivity

Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).

```
 min_trade_size  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
         0.0000           0.0639           0.0612            0.0027       0.8364        0.0552
         0.0050           0.0641           0.0614            0.0027       0.8380        0.0543
```

## Realism Verdict

- Δ ann return at 5bp (baseline): +0.27pp
- Δ ann return at 10bp (doubled): +0.26pp
- Δ ann return with 1-week delay: +0.37pp

**Verdict: candidate survives doubled-cost scenario.**

## Warnings

- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.
- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.
