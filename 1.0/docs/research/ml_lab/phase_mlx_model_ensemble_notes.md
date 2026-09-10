# Phase MLX Model Ensemble Notes

## Research-Only Warning

Phase MLX-9 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data where applicable, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

An ensemble combines several models or strategies instead of relying on one forecast. Combining models can help when different models make different errors, but it can hurt when the added models are weak, overfit, or all just rediscover the same exposure.

Rank averaging converts each model's weekly ETF scores into within-date ranks and then averages those ranks. This makes signals easier to combine even when their raw probabilities are on different scales. An agreement filter only activates an ETF when multiple models independently rank it highly. A core plus ML sleeve keeps production or Phase 4B as the stable base and adds a smaller ML allocation only around the edges.

Validation selection matters because choosing the best result on holdout is hindsight. This script selects a primary ensemble by 2018-2019 validation Sharpe and reports the 2020+ holdout separately. The best holdout-only ensemble is included as diagnostic research, not as a valid promotion candidate.

## Technical Setup

- Components loaded: sequence_5c, sequence_base, transformer, mlp, tabular
- Components skipped: none
- Candidate ensemble families tested: rank-average, sequence-dominant, agreement-filter, defensive-first, core plus ML sleeve, meta-label-gated core/sleeve, and RL diagnostic blend.
- Validation selection: highest validation Sharpe among ensemble candidates, with holdout reported after selection.
- Overlays used: raw ML, BIL fallback, regime gate, 10% volatility target, and drawdown kill switch where applicable.
- Transaction cost assumption: 10 bps per unit turnover.
- Leakage controls: predictions at date `t` are treated as known-at-date scores; action at `t` earns next-week returns; forward target columns are not used as ensemble inputs.

## Results

- Best validation-selected ensemble: `meta_core_switch_plus_ml_sleeve_10pct_thr0.70`
- Validation Sharpe: 0.621
- Holdout annual return: 8.61%
- Holdout Sharpe: 1.005
- Holdout max drawdown: -13.24%
- Holdout CVaR 5%: -2.69%

- Best holdout-diagnostic ensemble: `phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate`
- Diagnostic holdout annual return: 9.59%
- Diagnostic holdout Sharpe: 1.078
- Diagnostic holdout max drawdown: -12.45%
- Diagnostic holdout CVaR 5%: -2.69%

### Validation Selection

| strategy_name | strategy_family | sharpe | annual_return | max_drawdown | cvar_5 | holdout_sharpe | holdout_annual_return | holdout_max_drawdown | selected_by_validation | best_holdout_diagnostic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | meta_label_gated | 0.621 | 3.90% | -8.37% | -2.28% | 1.004878951199151 | 0.08614393815980659 | -0.13238013204375465 | True | False |
| meta_phase4b_switch_thr0.70_random_forest | meta_label_gated | 0.610 | 4.02% | -8.40% | -2.43% | 0.940968973011734 | 0.07992198697880926 | -0.1329849806171225 | False | False |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.50 | meta_label_gated | 0.584 | 3.57% | -9.16% | -2.20% | 1.0174818363618618 | 0.09146463927295101 | -0.1344292442392634 | False | False |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.60 | meta_label_gated | 0.583 | 3.67% | -8.54% | -2.31% | 1.032591995953903 | 0.09010507210858765 | -0.1255922841212731 | False | False |
| meta_phase4b_switch_thr0.50_random_forest | meta_label_gated | 0.578 | 3.68% | -9.20% | -2.32% | 0.99610604451519 | 0.08954872177185913 | -0.13706252733788793 | False | False |
| production_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | core_ml_sleeve | 0.575 | 3.59% | -8.04% | -2.29% | 0.936621211208336 | 0.0802716673639301 | -0.13792418545783958 | False | False |
| production_plus_rl_diagnostic_10pct | rl_diagnostic_blend | 0.560 | 3.72% | -8.78% | -2.42% | 0.9244378615589238 | 0.08281905734546524 | -0.15580904280561858 | False | False |
| meta_core_switch_plus_ml_sleeve_20pct_thr0.70 | meta_label_gated | 0.554 | 3.37% | -8.72% | -2.17% | 0.9735742002090393 | 0.08432679812981392 | -0.13310248987526185 | False | False |
| production_plus_rl_diagnostic_5pct | rl_diagnostic_blend | 0.548 | 3.61% | -8.46% | -2.41% | 0.9322003017799894 | 0.08175880309156436 | -0.14780700679804215 | False | False |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | core_ml_sleeve | 0.526 | 3.22% | -8.97% | -2.19% | 1.0775749657612586 | 0.0959045066286146 | -0.12454094790095771 | False | True |
| production_plus_ml_sleeve_20pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | core_ml_sleeve | 0.510 | 3.05% | -8.22% | -2.16% | 0.8938378811631529 | 0.07669403229242566 | -0.13691907565613326 | False | False |
| phase4b_plus_rl_diagnostic_10pct | rl_diagnostic_blend | 0.507 | 3.31% | -9.72% | -2.33% | 1.0402983066332985 | 0.09698377239497913 | -0.14209664783971354 | False | False |
| meta_core_switch_plus_ml_sleeve_20pct_thr0.50 | meta_label_gated | 0.504 | 2.99% | -9.41% | -2.09% | 0.9589569344238038 | 0.0865780460036214 | -0.13405496506497527 | False | False |
| phase4b_plus_rl_diagnostic_5pct | rl_diagnostic_blend | 0.492 | 3.17% | -9.46% | -2.33% | 1.0564430631528805 | 0.09670875771024856 | -0.1332734390523771 | False | False |
| meta_core_switch_plus_ml_sleeve_30pct_thr0.70 | meta_label_gated | 0.478 | 2.83% | -9.07% | -2.09% | 0.9391040158700992 | 0.08248080977664762 | -0.1338418897103174 | False | False |

### Strategy Comparison

| strategy_name | category | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_bil_exposure | average_ml_sleeve_exposure | average_core_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only | n/a | n/a | 1.276 | -14.56% | -4.17% | n/a | n/a | n/a |
| latest_candidate | benchmark | 9.55% | 8.81% | 1.084 | -11.77% | -2.66% | n/a | n/a | n/a |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 9.59% | 8.90% | 1.078 | -12.45% | -2.69% | 3.27% | 10.00% | 90.00% |
| phase4b | benchmark | 9.64% | 9.01% | 1.070 | -12.44% | -2.72% | n/a | n/a | n/a |
| phase4b_plus_rl_diagnostic_5pct | ensemble | 9.67% | 9.15% | 1.056 | -13.33% | -2.76% | 0.31% | 5.00% | 95.00% |
| phase4b_plus_rl_diagnostic_10pct | ensemble | 9.70% | 9.32% | 1.040 | -14.21% | -2.81% | 0.62% | 10.00% | 90.00% |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.60 | ensemble | 9.01% | 8.73% | 1.033 | -12.56% | -2.65% | 1.89% | 7.01% | 92.99% |
| phase4b_plus_ml_sleeve_20pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 9.06% | 8.84% | 1.024 | -12.53% | -2.69% | 6.54% | 20.00% | 80.00% |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.50 | ensemble | 9.15% | 8.99% | 1.017 | -13.44% | -2.71% | 2.03% | 7.56% | 92.44% |
| phase7 | benchmark | 9.57% | 9.47% | 1.011 | -13.83% | -2.92% | n/a | n/a | n/a |
| phase6 | benchmark | 9.57% | 9.47% | 1.010 | -13.77% | -2.92% | n/a | n/a | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ensemble | 8.61% | 8.57% | 1.005 | -13.24% | -2.69% | 1.84% | 6.62% | 93.38% |
| meta_phase4b_switch_thr0.50_random_forest | ensemble | 8.95% | 8.99% | 0.996 | -13.71% | -2.73% | 0.00% | 0.00% | 100.00% |
| meta_core_switch_plus_ml_sleeve_20pct_thr0.60 | ensemble | 8.68% | 8.79% | 0.987 | -12.62% | -2.67% | 3.78% | 14.02% | 85.98% |
| mlx6_transformer | benchmark | 11.16% | 11.30% | 0.987 | -13.13% | -3.29% | 25.15% | n/a | n/a |
| meta_core_switch_plus_ml_sleeve_20pct_thr0.70 | ensemble | 8.43% | 8.66% | 0.974 | -13.31% | -2.72% | 3.69% | 13.23% | 86.77% |
| mlx7_meta_label | benchmark | 8.64% | 8.94% | 0.966 | -13.88% | -2.74% | 0.00% | n/a | n/a |
| mlx5_sequence | benchmark | 11.66% | 12.08% | 0.964 | -11.34% | -3.63% | 25.15% | n/a | n/a |
| phase4b_plus_ml_sleeve_30pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 8.52% | 8.84% | 0.964 | -12.61% | -2.72% | 9.81% | 30.00% | 70.00% |
| meta_core_switch_plus_ml_sleeve_20pct_thr0.50 | ensemble | 8.66% | 9.03% | 0.959 | -13.41% | -2.73% | 4.06% | 15.12% | 84.88% |
| official_shadow | benchmark | 8.04% | 8.53% | 0.943 | -13.67% | -2.71% | n/a | n/a | n/a |
| meta_phase4b_switch_thr0.60_random_forest | ensemble | 8.18% | 8.68% | 0.942 | -12.72% | -2.67% | 0.00% | 0.00% | 100.00% |
| meta_phase4b_switch_thr0.70_random_forest | ensemble | 7.99% | 8.49% | 0.941 | -13.30% | -2.66% | 0.00% | 0.00% | 100.00% |
| meta_core_switch_plus_ml_sleeve_30pct_thr0.70 | ensemble | 8.25% | 8.78% | 0.939 | -13.38% | -2.76% | 5.53% | 19.85% | 80.15% |
| meta_core_switch_plus_ml_sleeve_30pct_thr0.60 | ensemble | 8.35% | 8.90% | 0.938 | -12.69% | -2.70% | 5.68% | 21.04% | 78.96% |

### Walk-Forward Windows

| strategy_name | category | window | annual_return | sharpe | max_drawdown | cvar_5 | active_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ensemble | 2017_2018 | 4.81% | 0.758 | -8.37% | -2.17% | 104 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ensemble | 2019_2020 | 8.10% | 0.855 | -13.24% | -3.46% | 104 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ensemble | 2021_2022 | 5.01% | 0.662 | -4.51% | -2.27% | 105 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ensemble | 2023_2026 | 12.64% | 1.665 | -6.39% | -2.03% | 171 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 2017_2018 | 4.61% | 0.760 | -8.97% | -2.09% | 104 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 2019_2020 | 9.14% | 0.903 | -12.45% | -3.57% | 104 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 2021_2022 | 4.75% | 0.642 | -6.17% | -2.17% | 105 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | ensemble | 2023_2026 | 13.84% | 1.748 | -6.47% | -1.99% | 171 |
| production | benchmark | 2017_2018 | 5.38% | 0.820 | -8.14% | -2.25% | 104 |
| production | benchmark | 2019_2020 | 6.85% | 0.707 | -13.98% | -3.64% | 104 |
| production | benchmark | 2021_2022 | 4.91% | 0.642 | -4.57% | -2.30% | 105 |
| production | benchmark | 2023_2026 | 12.36% | 1.636 | -6.26% | -2.06% | 171 |
| official_shadow | benchmark | 2017_2018 | 5.44% | 0.817 | -8.24% | -2.29% | 104 |
| official_shadow | benchmark | 2019_2020 | 6.96% | 0.729 | -13.67% | -3.59% | 104 |
| official_shadow | benchmark | 2021_2022 | 4.79% | 0.628 | -4.56% | -2.32% | 105 |
| official_shadow | benchmark | 2023_2026 | 12.29% | 1.639 | -6.24% | -2.05% | 171 |
| phase4b | benchmark | 2017_2018 | 4.84% | 0.773 | -9.20% | -2.15% | 104 |
| phase4b | benchmark | 2019_2020 | 9.64% | 0.925 | -12.44% | -3.63% | 104 |
| phase4b | benchmark | 2021_2022 | 4.80% | 0.648 | -6.79% | -2.14% | 105 |
| phase4b | benchmark | 2023_2026 | 13.75% | 1.724 | -6.93% | -2.03% | 171 |
| phase6 | benchmark | 2017_2018 | 5.12% | 0.760 | -9.08% | -2.28% | 104 |
| phase6 | benchmark | 2019_2020 | 8.42% | 0.770 | -13.77% | -3.95% | 104 |
| phase6 | benchmark | 2021_2022 | 5.53% | 0.726 | -6.78% | -2.21% | 105 |
| phase6 | benchmark | 2023_2026 | 14.03% | 1.636 | -7.43% | -2.24% | 171 |
| phase7 | benchmark | 2017_2018 | 5.24% | 0.771 | -9.16% | -2.29% | 104 |
| phase7 | benchmark | 2019_2020 | 8.50% | 0.778 | -13.83% | -3.96% | 104 |
| phase7 | benchmark | 2021_2022 | 5.33% | 0.705 | -6.82% | -2.21% | 105 |
| phase7 | benchmark | 2023_2026 | 14.19% | 1.649 | -7.61% | -2.23% | 171 |
| SPY | benchmark | 2017_2018 | 6.30% | 0.466 | -17.76% | -5.22% | 104 |
| SPY | benchmark | 2019_2020 | 20.72% | 0.870 | -33.63% | -8.54% | 104 |
| SPY | benchmark | 2021_2022 | 1.55% | 0.085 | -25.52% | -5.11% | 105 |
| SPY | benchmark | 2023_2026 | 21.78% | 1.521 | -17.37% | -3.93% | 175 |
| 60_40 | benchmark | 2017_2018 | 4.64% | 0.586 | -9.78% | -3.03% | 104 |
| 60_40 | benchmark | 2019_2020 | 16.86% | 1.222 | -19.59% | -4.89% | 104 |
| 60_40 | benchmark | 2021_2022 | -2.64% | -0.222 | -21.88% | -3.43% | 105 |
| 60_40 | benchmark | 2023_2026 | 14.22% | 1.540 | -9.42% | -2.34% | 175 |
| simple_momentum | benchmark | 2017_2018 | 2.55% | 0.157 | -25.83% | -5.23% | 104 |
| simple_momentum | benchmark | 2019_2020 | 0.31% | 0.015 | -29.98% | -7.30% | 104 |
| simple_momentum | benchmark | 2021_2022 | 10.67% | 0.357 | -31.12% | -8.21% | 105 |
| simple_momentum | benchmark | 2023_2026 | 42.27% | 1.939 | -19.14% | -5.88% | 175 |

### State-By-State Results

| strategy_name | market_state | annual_return | sharpe | max_drawdown | cvar_5 | average_bil_exposure | average_ml_sleeve_exposure | average_core_exposure | weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | neutral_mixed | 21.43% | 2.613 | -3.47% | -1.91% | 3.17% | 7.93% | 92.07% | 121 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | recovery_fragile | 8.37% | 1.671 | -2.50% | -1.13% | 3.43% | 8.57% | 91.43% | 14 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | calm_trend | 3.73% | 0.427 | -7.24% | -2.68% | 0.00% | 6.44% | 93.56% | 101 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | recovery_confirmed | -0.47% | -0.064 | -3.47% | -1.97% | 0.00% | 10.00% | 90.00% | 21 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | stressed_panic | -1.55% | -0.165 | -5.55% | -3.57% | 2.43% | 3.24% | 96.76% | 71 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | neutral_mixed | 23.21% | 2.556 | -4.46% | -2.21% | 4.00% | 10.00% | 90.00% | 121 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | recovery_fragile | 8.30% | 1.479 | -2.80% | -1.26% | 4.00% | 10.00% | 90.00% | 14 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | calm_trend | 4.08% | 0.518 | -7.64% | -2.38% | 0.00% | 10.00% | 90.00% | 101 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | recovery_confirmed | 0.17% | 0.019 | -3.59% | -2.24% | 0.00% | 10.00% | 90.00% | 21 |
| phase4b_plus_ml_sleeve_10pct__defensive_first__sequence_dominant_70_20_10__top15__inverse_vol__regime_gate | stressed_panic | -0.58% | -0.058 | -5.56% | -3.62% | 7.50% | 10.00% | 90.00% | 71 |

### Exposure Audit

| strategy_name | audit_type | item | category | average_weight | max_weight | holding_frequency |
| --- | --- | --- | --- | --- | --- | --- |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Core strategy | Core strategy | 0.9338414634146344 | 1.0 | 1.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Bonds | Bonds | 0.018695967297256835 | 0.07954431848650871 | 0.40853658536585363 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | US sectors | US sectors | 0.015251630347280682 | 0.04606050593069354 | 0.600609756097561 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | International equity | International equity | 0.014081465469142768 | 0.051513266124376705 | 0.5640243902439024 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Commodities | Commodities | 0.011458092786120304 | 0.042442999443788085 | 0.5 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | US broad equity | US broad equity | 0.0032019642046040224 | 0.030740252359936243 | 0.1402439024390244 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Volatility proxies | Volatility proxies | 0.0013618875585392552 | 0.0059542918138601325 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Real estate | Real estate | 0.0010595841578629629 | 0.03360289895066913 | 0.04573170731707317 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Factors/styles | Factors/styles | 0.000910207142182927 | 0.015082466362221214 | 0.012195121951219513 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | category | Currency/dollar | Currency/dollar | 0.00013773762237610348 | 0.011160667001710369 | 0.003048780487804878 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | summary | average_top3_weight |  | 0.9594775405460516 | 1.0 | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | summary | average_safe_asset_weight |  | 0.018695967297256835 | 0.07954431848650871 | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | summary | average_BIL_weight |  | 0.01842987804878049 | 0.07500000000000001 | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | summary | average_sector_weight |  | 0.015251630347280682 | 0.04606050593069354 | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | summary | average_commodities_weight |  | 0.011458092786120304 | 0.042442999443788085 | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | summary | average_SPY_QQQ_SMH_weight |  | 0.0032906044161764136 | 0.017224445612716625 | n/a |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | CORE_PRODUCTION_PHASE4B_SWITCH | Core strategy | 0.9338414634146344 | 1.0 | 1.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | BIL | Bonds | 0.01842987804878049 | 0.07500000000000001 | 0.39939024390243905 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | SLV | Commodities | 0.0029043217180984124 | 0.01155096260811737 | 0.003048780487804878 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | SMH | US sectors | 0.0028815279368622727 | 0.010056146172886422 | 0.003048780487804878 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | XBI | US sectors | 0.0028380536036663913 | 0.0108437544577399 | 0.009146341463414634 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | EWZ | International equity | 0.0026938260671247956 | 0.011629680572796954 | 0.024390243902439025 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | FXI | International equity | 0.002645176373519642 | 0.009525738096105064 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | USO | Commodities | 0.0026290278941814445 | 0.009545348028356028 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | EWW | International equity | 0.002577483052597666 | 0.009585886523996133 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | KRE | US sectors | 0.002479971885898288 | 0.010008928815446827 | 0.003048780487804878 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | XLE | US sectors | 0.0024787953876882433 | 0.01005046878145905 | 0.003048780487804878 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | EWY | International equity | 0.002330223861857698 | 0.00934675305439974 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | ASHR | International equity | 0.001813327385678066 | 0.01255776471162895 | 0.012195121951219513 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | XLK | US sectors | 0.0016750832294075365 | 0.010664892589675276 | 0.009146341463414634 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | UNG | Commodities | 0.0014748057658368347 | 0.0062841981213848114 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | IWM | US broad equity | 0.001384766986312427 | 0.009353649547708563 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | VIXY | Volatility proxies | 0.0013618875585392552 | 0.0059542918138601325 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | IJR | US broad equity | 0.0013583428349601208 | 0.009186087503692113 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | GLD | Commodities | 0.0010646567274531092 | 0.011786056822512159 | 0.018292682926829267 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | IAU | Commodities | 0.0010390578186695878 | 0.010990191827413225 | 0.012195121951219513 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | EWT | International equity | 0.0009786700687291728 | 0.008683841019991376 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | PDBC | Commodities | 0.0009280691558233998 | 0.010820933249068 | 0.01524390243902439 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | IBB | US sectors | 0.0009088324286516743 | 0.009245515888501784 | 0.0 |
| meta_core_switch_plus_ml_sleeve_10pct_thr0.70 | ticker | DBC | Commodities | 0.0008153749461609802 | 0.011025819027283773 | 0.009146341463414634 |

## Interpretation

- Does the validation-selected ensemble beat production by holdout Sharpe? True
- Does it beat official shadow by holdout Sharpe? True
- Does it beat Phase 4B by holdout Sharpe? False
- Does it beat MLX-5C mean Sharpe? False
- Does it beat MLX-6 Transformer? True
- Does it beat MLX-7 meta-labeling? True
- Does it beat MLX-8 RL? True
- Is the best result selected by validation rather than holdout hindsight? Yes for the primary candidate; the holdout-only best is labeled diagnostic.
- Final recommendation: **PROMISING FILTER / SLEEVE BUT NEEDS WALK-FORWARD**

The ensemble is useful only if it improves risk-adjusted performance without hiding a worse tail profile behind model complexity. If the improvement comes mainly from one window or one component, it should remain a research-only shadow or offensive sleeve candidate.

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- Expanded ETF/yfinance research data can introduce selection bias and data-mining risk.
- No ensemble model is promoted automatically.
