# C1 Exact GGG Baseline Note

Research-only baseline confirmation for allocator-native confidence insertion.

## Exact Reconstruction Evidence

| rebuild_name | rebuild_ann_return | rebuild_sharpe | rebuild_max_drawdown | rebuild_cvar_5 | net_return_corr_vs_saved | net_return_max_abs_error |
| --- | --- | --- | --- | --- | --- | --- |
| exact_saved_final_etf_weights | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 1.0000 | 0.0000 |

## Exact GGG Metrics Recomputed

| ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_turnover | cost_drag | avg_BIL | avg_SPY | avg_offense | avg_defense |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0714 | 0.0762 | 0.9366 | -0.1177 | 0.6063 | -0.0254 | 0.0618 | 0.0686 | 0.2666 | 0.0603 | 0.4162 | 0.5447 |

## Confirmed Plumbing

- Return alignment: `weekly_prices.pct_change().shift(-1)` on allocation-date index.
- Turnover convention: one-way turnover `0.5 * sum(abs(diff(final_etf_weights)))`.
- Cost convention: 10 bps times one-way turnover.
- State labels: `data/04_layer2b_risk_regime_engine/market_state_history.csv`.
- Offense exposure: sum of ETF columns in the project offense basket.
- Defense/cash exposure: BIL plus defensive ETF basket; BIL is the explicit cash proxy.

## State Labels

| market_state | n_weeks |
| --- | --- |
| neutral_mixed | 493 |
| calm_trend | 295 |
| stressed_panic | 229 |
| recovery_fragile | 49 |
| recovery_confirmed | 44 |

## Warnings

- None.
