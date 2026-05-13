# Phase MLX-5B Sequence Overlay Robustness Report

## Research-Only Warning

Phase MLX-5B is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Robustness testing asks whether a result survives reasonable changes in time window, transaction cost, portfolio size, weighting, and risk overlay rules. One good holdout result is not enough because financial markets are noisy and a strategy can look excellent in one regime while failing in the next.

Window sensitivity checks whether performance depends on a specific date range. Overlay sensitivity checks whether one fragile rule, such as a particular BIL fallback, is doing most of the work. Cost sensitivity tests whether turnover costs erase the apparent edge. State-by-state analysis checks which market regimes help or hurt the strategy. Holdings and exposure audits matter because a model can appear smart while mostly hiding a simple exposure, such as QQQ, SPY, tech, momentum, or cash.

## Executive Summary

- Best MLX-5 overlay strategy tested: `lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback`
- Original holdout Sharpe: 0.964
- Original holdout annual return: 11.66%
- Original holdout max drawdown: -11.34%
- Final recommendation: **NEEDS MULTI-SEED / WALK-FORWARD BEFORE JUDGMENT**

The MLX-5 overlay remains interesting, especially as a possible offensive sleeve, but the result is not robust enough for production judgment. The earlier MLX-5 caveat still matters: the best holdout strategy had weak train/validation Sharpe, so multi-seed and walk-forward testing are required before treating the edge as durable.

## Holdout-Window Sensitivity

| window | strategy_name | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2018_onward | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 8.40% | 11.47% | 0.732 | -16.54% | 0.508 | -3.53% | 32.01% | 1.66% | 27.41% |
| 2020_onward | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 34.17% | 1.78% | 25.15% |
| 2022_onward | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 13.24% | 10.69% | 1.238 | -9.59% | 1.381 | -3.09% | 32.79% | 1.70% | 27.53% |
| 2023_onward | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 16.13% | 11.04% | 1.460 | -7.74% | 2.084 | -3.17% | 37.35% | 1.94% | 17.14% |
| covid_crash_rebound | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | -5.90% | 14.09% | -0.418 | -6.57% | -0.898 | -4.96% | 34.72% | 1.81% | 54.46% |
| 2022_bear | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 8.13% | 10.00% | 0.813 | -4.09% | 1.989 | -2.29% | 16.31% | 0.85% | 62.80% |
| 2023_2025_ai_risk_on | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 13.57% | 10.77% | 1.259 | -7.74% | 1.753 | -3.01% | 36.62% | 1.90% | 16.35% |

## Overlay Sensitivity

| overlay_variant | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_weight | average_ml_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bil_fallback_original | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 34.17% | 1.78% | 25.15% | 74.85% |
| bil_fallback_mild | 12.96% | 14.00% | 0.926 | -17.28% | 0.750 | -4.19% | 33.39% | 1.74% | 16.79% | 83.21% |
| drawdown_kill_switch_original | 12.18% | 13.78% | 0.884 | -12.82% | 0.950 | -4.41% | 28.84% | 1.50% | 21.22% | 78.78% |
| regime_gate_original | 9.48% | 11.01% | 0.861 | -11.45% | 0.827 | -3.45% | 32.89% | 1.71% | 32.67% | 67.33% |
| drawdown_kill_switch_aggressive | 9.70% | 11.65% | 0.832 | -11.48% | 0.845 | -3.73% | 27.80% | 1.45% | 32.94% | 67.06% |
| bil_fallback_aggressive | 8.13% | 9.93% | 0.819 | -9.58% | 0.849 | -3.27% | 32.52% | 1.69% | 41.72% | 58.28% |
| drawdown_kill_switch_mild | 13.63% | 17.38% | 0.784 | -24.40% | 0.559 | -5.47% | 34.35% | 1.79% | 2.62% | 97.38% |
| raw_ml | 14.85% | 19.27% | 0.771 | -28.64% | 0.519 | -5.90% | 35.24% | 1.83% | 0.00% | 100.00% |
| vol_target_8pct | 7.14% | 9.40% | 0.759 | -13.41% | 0.532 | -3.20% | 23.26% | 1.21% | 46.79% | 53.21% |
| vol_target_12pct | 9.38% | 13.27% | 0.707 | -19.12% | 0.491 | -4.41% | 30.70% | 1.60% | 24.31% | 75.69% |
| vol_target_10pct | 8.15% | 11.56% | 0.705 | -16.62% | 0.490 | -3.91% | 27.72% | 1.44% | 34.40% | 65.60% |

## Top-N / Weighting Sensitivity

| top_n | weighting | overlay_variant | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | average_bil_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | inverse_vol | bil_fallback_original | 11.96% | 11.49% | 1.041 | -11.94% | 1.002 | -3.47% | 28.65% | 25.15% |
| 15 | equal_weight | bil_fallback_original | 10.47% | 10.74% | 0.975 | -9.60% | 1.091 | -3.22% | 22.69% | 25.15% |
| 10 | inverse_vol | bil_fallback_original | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 34.17% | 25.15% |
| 3 | inverse_vol | bil_fallback_original | 17.04% | 18.90% | 0.902 | -22.63% | 0.753 | -5.22% | 45.55% | 25.15% |
| 5 | inverse_vol | bil_fallback_original | 13.39% | 15.29% | 0.876 | -16.08% | 0.833 | -4.76% | 39.62% | 25.15% |
| 10 | equal_weight | bil_fallback_original | 8.98% | 11.79% | 0.762 | -12.88% | 0.698 | -3.72% | 27.65% | 25.15% |
| 5 | equal_weight | bil_fallback_original | 11.98% | 16.02% | 0.748 | -20.80% | 0.576 | -4.97% | 33.58% | 25.15% |
| 3 | equal_weight | bil_fallback_original | 13.75% | 20.50% | 0.671 | -23.35% | 0.589 | -5.97% | 38.91% | 25.15% |

## Cost Sensitivity

| cost_bps | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 13.65% | 12.09% | 1.129 | -11.08% | 1.232 | -3.59% | 34.17% | 0.00% |
| 10.0 | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 34.17% | 1.78% |
| 25.0 | 8.72% | 12.09% | 0.722 | -11.73% | 0.744 | -3.69% | 34.17% | 4.44% |
| 50.0 | 4.00% | 12.11% | 0.330 | -17.03% | 0.235 | -3.80% | 34.17% | 8.89% |

## State-By-State Performance

| market_state | weeks | weekly_mean_return | annual_return | annual_volatility | sharpe | hit_rate | average_bil_exposure | average_ml_exposure | average_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calm_trend | 101 | 0.02% | -0.03% | 13.11% | -0.002 | 57.43% | 0.00% | 100.00% | 35.75% |
| neutral_mixed | 121 | 0.43% | 24.11% | 12.01% | 2.007 | 58.68% | 25.00% | 75.00% | 36.41% |
| recovery_confirmed | 21 | 0.28% | 14.00% | 17.40% | 0.805 | 57.14% | 0.00% | 100.00% | 57.49% |
| recovery_fragile | 14 | 0.45% | 25.21% | 12.63% | 1.996 | 57.14% | 0.00% | 100.00% | 50.42% |
| stressed_panic | 71 | 0.06% | 2.79% | 7.53% | 0.370 | 52.11% | 75.00% | 25.00% | 17.51% |
| unknown | 4 | 1.28% | n/a | 6.45% | n/a | 75.00% | 0.00% | 100.00% | 43.34% |

## Holdings / Exposure Audit

Top average ETF weights:

| item | category | average_weight | holding_frequency | max_weight |
| --- | --- | --- | --- | --- |
| BIL | Bonds | 0.25150602409638556 | 0.5783132530120482 | 0.75 |
| SMH | US sectors | 0.05934766628152073 | 0.7590361445783133 | 0.1539799881640015 |
| SLV | Commodities | 0.056875555318186534 | 0.7228915662650602 | 0.17575550156166775 |
| XBI | US sectors | 0.056394085715255636 | 0.713855421686747 | 0.17111735330678388 |
| KRE | US sectors | 0.05255138671049847 | 0.6897590361445783 | 0.16724364510960746 |
| USO | Commodities | 0.047945775769650166 | 0.7409638554216867 | 0.14769331117043544 |
| FXI | International equity | 0.04632927896033869 | 0.5813253012048193 | 0.1468900179170277 |
| XLE | US sectors | 0.046076210741706994 | 0.6204819277108434 | 0.15268133196786657 |
| EWZ | International equity | 0.037575938506984985 | 0.5090361445783133 | 0.19031143479550516 |
| UNG | Commodities | 0.035164844806095136 | 0.8795180722891566 | 0.10077767547181016 |
| EWY | International equity | 0.029718236862832106 | 0.32228915662650603 | 0.14684673480981814 |
| ASHR | International equity | 0.02952650176310786 | 0.28012048192771083 | 0.19729448995510876 |
| EWW | International equity | 0.028601299977354677 | 0.29518072289156627 | 0.18981834195451186 |
| VIXY | Volatility proxies | 0.02401253693439367 | 0.6445783132530121 | 0.1042331333714433 |
| GLD | Commodities | 0.018179118305457403 | 0.17771084337349397 | 0.17635687786079668 |

Exposure summaries:

| item | value |
| --- | --- |
| average_SPY_weight | 0.00% |
| average_QQQ_weight | 0.56% |
| average_tech_like_weight | 8.17% |
| average_sector_weight | 26.28% |
| average_bond_cash_weight | 25.61% |
| average_BIL_weight | 25.15% |
| average_top3_etf_exposure | 51.65% |
| max_single_etf_weight | 75.00% |

The audit is meant to catch whether the model is secretly just QQQ/SPY/tech/momentum exposure or whether the BIL fallback dominates results. Any such concentration should be treated as a research warning rather than evidence of model skill.

## Project Strategy Comparison

2020+ aligned comparison:

| comparison_label | strategy_name | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | average_bil_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase4b | project_improved_phase4b_sector_phase3_hybrid | 9.64% | 9.01% | 1.070 | -12.44% | 0.775 | -2.72% | 8.44% | n/a |
| phase7 | project_improved_phase7_expression_boost | 9.57% | 9.47% | 1.011 | -13.83% | 0.692 | -2.92% | 7.86% | n/a |
| phase6 | project_improved_phase6_recovery_quality_rerisk | 9.57% | 9.47% | 1.010 | -13.77% | 0.695 | -2.92% | 7.88% | n/a |
| Best defensive-overlay sequence model | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 34.17% | 25.15% |
| official_shadow | official_shadow_improved_phase2b_combo_abc | 8.04% | 8.53% | 0.943 | -13.67% | 0.588 | -2.71% | 5.65% | n/a |
| current_production | current_production_improved_phase2b_regime_confidence_boost | 8.07% | 8.60% | 0.938 | -13.98% | 0.577 | -2.73% | 5.60% | n/a |
| MLX-4 best MLP | mlx4_best_mlp | 18.03% | 19.89% | 0.907 | -29.40% | 0.613 | -6.09% | 43.73% | n/a |
| Simple momentum baseline | baseline_top_momentum_momentum_12_1__top3__inverse_vol | 22.21% | 25.57% | 0.869 | -43.50% | 0.511 | -7.83% | 46.97% | 0.00% |
| Best raw sequence model | temporal_cnn_classifier_top_quintile_forward_4w_seq26__top3__inverse_vol__raw_ml | 23.26% | 27.55% | 0.844 | -29.44% | 0.790 | -7.80% | 66.86% | 0.00% |
| MLX-3 best tabular ML | mlx3_best_tabular_ml | 16.85% | 20.78% | 0.811 | -37.55% | 0.449 | -6.52% | 61.93% | n/a |
| SPY | baseline_spy_buy_hold | 15.44% | 19.25% | 0.802 | -31.83% | 0.485 | -6.06% | 0.30% | 0.00% |
| 60/40 | baseline_60_40_spy_ief_or_agg | 9.49% | 11.99% | 0.792 | -20.76% | 0.457 | -3.71% | 0.30% | 0.00% |

Explicit answers:

- Does MLX-5 beat current production across multiple windows or only 2020+? Across all tested windows: False; 2020+ only: True.
- Does MLX-5 beat official shadow across multiple windows? False.
- Does MLX-5 beat Phase 4B best? 2020+: False; all tested windows: False.
- Does MLX-5 have better return but worse CVaR? 2020+ sequence CVaR is -3.63% versus production -2.73%.
- Is MLX-5 more suitable as standalone strategy or offensive sleeve? It is more suitable as an offensive sleeve candidate, not a standalone production replacement.

## Random Seed / Instability Note

MLX-5B did not retrain the sequence models. The saved MLX-5 predictions appear to come from one seed, so random-seed robustness is not yet tested. A future MLX-5C should rerun LSTM/GRU/Temporal CNN models across multiple seeds and preferably walk-forward folds.

## Warnings

- Random-seed robustness was not retrained in MLX-5B; saved MLX-5 predictions appear to come from one training seed. MLX-5C should run multi-seed or walk-forward checks.
