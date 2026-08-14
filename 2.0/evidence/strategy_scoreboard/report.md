# Bias-Aware Strategy Scoreboard

Generated: 2026-08-08

This scoreboard shows every saved Layer 2 strategy, including weak and failed
results. It verifies portfolio returns against dated positions and the following
week's market returns, applies turnover costs, and reports uncertainty. It does
not call the 2021+ period an untouched holdout because these strategies were
researched while that history was already available.

## Executive findings

- 33/33 saved return/position pairs are shown; 28 reconstruct exactly and 5 fail reconciliation.
- Only two rows currently earn Grade B. The strongest non-benchmark Grade B candidate is
  `composite_selective_strength_weighted`: 7.03% annual return,
  0.739 Sharpe, -20.16% max drawdown,
  and 6.17% annual return under the 50 bps turnover stress.
- SPY returned 10.54% annually with a 0.660
  Sharpe but suffered a much deeper -54.61% drawdown.
- `composite_trend_quality_refined` is the clearest repair candidate: its headline return
  (10.59%) slightly exceeds SPY, but it remains Grade C because
  it carries nonzero positions across 33 weeks with missing asset returns.
- No strategy is promoted. The first genuinely untouched forward week is locked to 2026-08-14;
  changing strategy logic after the lock creates a new candidate version.

## Evidence grades

- **B:** return and cost accounting reconcile, a lag convention is documented,
  at least ten years are available, no nonzero holding lacks a price return,
  and no unmodeled short financing or free multi-asset rebalancing is detected.
- **C:** accounting reconciles, but missing-price exposure or missing primary
  manifest evidence reduces trust.
- **D:** saved returns do not reproduce from dated positions and next-week returns;
  numbers are visible but excluded from trustworthy ranking.
- No strategy can receive A yet: there is no genuinely untouched holdout after
  the research process, and signal generation has not been independently rebuilt.

## Results

| Rank | Strategy | Grade | Ann. return | Sharpe | Max DD | Recent Sharpe | 50 bps return | vs SPY return | Conservative Sharpe |
|---:|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `composite_selective_strength_weighted` | B | 7.03% | 0.739 | -20.16% | 0.918 | 6.17% | -3.51% | 0.396 |
| 2 | `baseline_market_proxy_buy_hold` | B | 10.54% | 0.660 | -54.61% | 0.883 | 10.54% | 0.00% | 0.245 |
| 3 | `composite_regime_conditioned` | C | 7.20% | 0.906 | -12.19% | 1.113 | 5.57% | -3.34% | 0.542 |
| 4 | `composite_anti_chop_clarity` | C | 7.84% | 0.824 | -18.01% | 0.729 | 5.24% | -2.70% | 0.504 |
| 5 | `composite_trend_quality_refined` | C | 10.59% | 0.800 | -26.25% | 1.044 | 9.78% | 0.05% | 0.462 |
| 6 | `composite_calm_trend_specialist` | C | 7.01% | 0.832 | -18.13% | 0.904 | 4.09% | -3.54% | 0.448 |
| 7 | `composite_selective_trend_ensemble` | C | 7.58% | 0.801 | -22.03% | 0.863 | 6.95% | -2.96% | 0.444 |
| 8 | `baseline_60_40_proxy` | C | 8.09% | 0.807 | -31.38% | 0.762 | 8.09% | -2.45% | 0.429 |
| 9 | `composite_selective_signals` | C | 7.58% | 0.801 | -22.03% | 0.863 | 6.95% | -2.96% | 0.417 |
| 10 | `dual_momentum_topn` | C | 8.75% | 0.728 | -18.08% | 0.987 | 7.79% | -1.80% | 0.400 |
| 11 | `composite_calm_trend_participation` | C | 7.14% | 0.749 | -18.80% | 0.725 | 4.51% | -3.40% | 0.366 |
| 12 | `composite_selective_concentrated` | C | 7.08% | 0.722 | -18.62% | 1.043 | 6.25% | -3.47% | 0.358 |
| 13 | `composite_healthier_recovery_specialist` | C | 6.24% | 0.681 | -23.00% | 0.408 | 2.92% | -4.30% | 0.336 |
| 14 | `composite_ic_weighted` | C | 8.32% | 0.695 | -27.47% | 0.955 | 6.74% | -2.23% | 0.326 |
| 15 | `cta_trend_long_only` | C | 7.93% | 0.663 | -25.71% | 0.803 | 4.84% | -2.61% | 0.323 |
| 16 | `composite_trend_quality_module` | C | 8.75% | 0.673 | -29.56% | 1.043 | 7.90% | -1.80% | 0.318 |
| 17 | `sector_rotation_with_sma_filter` | C | 6.88% | 0.662 | -19.42% | 0.901 | 4.13% | -3.67% | 0.300 |
| 18 | `composite_equal_weight` | C | 6.78% | 0.662 | -25.20% | 0.984 | 5.38% | -3.76% | 0.284 |
| 19 | `cta_trend_vol_managed` | C | 6.72% | 0.651 | -21.56% | 0.850 | 3.78% | -3.82% | 0.275 |
| 20 | `composite_recovery_transition` | C | 5.60% | 0.622 | -25.19% | 0.316 | 2.25% | -4.94% | 0.274 |
| 21 | `sector_factor_rotation` | C | 8.97% | 0.618 | -41.35% | 0.992 | 6.94% | -1.57% | 0.262 |
| 22 | `composite_confirmation_aware_momentum` | C | 8.40% | 0.614 | -38.32% | 0.988 | 7.34% | -2.14% | 0.258 |
| 23 | `taa_10m_sma` | C | 6.77% | 0.587 | -38.31% | 0.909 | 5.72% | -3.77% | 0.212 |
| 24 | `baseline_equal_weight_risk_assets` | C | 7.30% | 0.648 | -38.10% | 0.860 | 7.30% | -3.25% | 0.210 |
| 25 | `composite_breadth_filtered` | C | 4.83% | 0.578 | -23.04% | 1.166 | 3.05% | -5.72% | 0.197 |
| 26 | `dual_momentum_single_best` | C | 6.85% | 0.437 | -49.11% | 1.067 | 5.28% | -3.69% | 0.083 |
| 27 | `cta_trend_long_short_research` | C | 1.48% | 0.307 | -11.20% | 0.505 | -0.64% | -9.06% | -0.033 |
| 28 | `cross_sectional_reversal_combo_ls` | C | -3.27% | -0.333 | -54.04% | 0.010 | -14.95% | -13.81% | -0.629 |
| 29 | `composite_structural_defense_sleeve` | D | 2.26% | 0.659 | -11.25% | 0.974 | 1.51% | -8.29% | 0.233 |
| 30 | `composite_macro_trend_diversifier_sleeve` | D | 2.55% | 0.392 | -18.01% | 0.879 | -0.17% | -7.99% | 0.066 |
| 31 | `composite_calm_carry_sleeve` | D | 0.79% | 0.288 | -11.11% | 0.616 | -2.69% | -9.75% | -0.137 |
| 32 | `composite_recovery_confirmed_offense_sleeve` | D | 0.62% | 0.209 | -14.99% | 1.101 | -2.24% | -9.92% | -0.163 |
| 33 | `pairs_stat_arb_research` | D | -0.76% | -0.258 | -23.40% | -0.057 | -3.14% | -11.30% | -0.635 |

## Interpretation rules

1. Compare Grade B before Grade C; do not rank Grade D by performance.
2. Prefer conservative Sharpe, recent behavior, drawdown, and 50 bps cost
   stress over the highest full-period return.
3. A positive backtest is a research candidate, not proof of future profit.
4. The current ETF universe and repeated strategy search create survivorship
   and multiple-testing risk for every row.
5. Promotion remains blocked until strategies are rebuilt from point-in-time
   inputs and evaluated on a newly locked, genuinely untouched period.

Machine-readable details and every bias flag are in `strategy_scoreboard.json`.
