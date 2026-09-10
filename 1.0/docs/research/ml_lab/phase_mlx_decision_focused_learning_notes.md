# Phase MLX Decision-Focused Portfolio Learning Notes

## Research-Only Warning

Phase MLX decision-focused learning is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Decision-focused learning trains a model by looking at the quality of the decision created from its predictions. In this sprint, the decision is a long-only ETF allocation. The model produces one score per ETF at date `t`; those scores are converted into portfolio weights; the portfolio earns next-week returns; and the loss can directly reward better portfolio outcomes.

Predict-then-optimize is the normal workflow: train a model to predict a label such as top-quintile membership, then separately turn predictions into rankings or weights. That can fail in finance because a model can improve classification accuracy while still picking assets with bad portfolio-level risk, high turnover, poor diversification, or weak downside behavior.

Portfolio loss is different from prediction loss. A prediction loss asks whether an ETF label was right. A portfolio loss asks whether the weights created from scores had good net return, acceptable volatility, manageable turnover, and tolerable downside. This is closer to the actual goal of an ETF allocator.

Differentiable portfolio learning means the allocation step is written in a way that gradients can flow through it. This first version uses a masked softmax allocation: higher model scores receive larger long-only weights, unavailable ETFs are masked out, and all weights sum to one. It is a simplification, not a full differentiable optimizer.

The Sharpe-like loss uses mean weekly net return divided by weekly volatility, with a small numerical stabilizer. Turnover and risk penalties discourage fragile high-churn or high-volatility allocations. These losses can overfit badly because the model is allowed to chase the exact historical portfolio objective. That is powerful, but dangerous.

This connects to decision-focused learning, predict-then-optimize, SPO-style losses, differentiable optimization layers such as `cvxpylayers`, and portfolio-learning libraries such as DeepDow. This script does not use cvxpy layers; it uses a CPU-safe softmax approximation first.

## Technical Setup

- Torch availability: {'available': True, 'version': '2.8.0', 'device': 'cpu', 'cuda_available': False, 'mps_available': True}
- Input tensor shape: `[1375, 97, 74]` as `[dates, ETFs, features]`
- ETF universe size: 97
- Features used: 74 total, including an availability mask
- Architecture: {'model': 'per-ETF MLP scorer with learned ETF embedding', 'input_projection': 'Linear(74 -> 64)', 'hidden_dim': 64, 'dropout': 0.15, 'output': 'one score per ETF per date', 'allocation_training': 'masked softmax long-only portfolio over ETFs', 'temperature': 0.5}
- Losses tested: ['prediction_bce', 'decision_return', 'decision_sharpe', 'decision_risk_aware', 'hybrid_bce_sharpe']
- Allocation transformation: masked softmax over available ETFs for decision losses; evaluation also tests top-10/top-15 equal/inverse-vol portfolios
- Transaction cost assumption: 10 bps per unit turnover
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill and train-only standardization
- Leakage controls: no target-like input columns; action at date `t` uses scores known at date `t` and earns next-week returns
- Candidate definitions: {'prediction_bce': 'Predict-then-optimize baseline trained on top_quintile_forward_4w BCE.', 'decision_return': 'Decision-focused loss = negative mean weekly net portfolio return plus small turnover penalty.', 'decision_sharpe': 'Decision-focused loss = negative differentiable Sharpe-like objective plus turnover penalty.', 'decision_risk_aware': 'Decision-focused loss with return, volatility, downside, and turnover terms.', 'hybrid_bce_sharpe': 'Hybrid supervised BCE plus decision-focused Sharpe-like loss.', 'allocation': 'Training uses masked softmax long-only weights over all available ETFs; evaluation also tests top10/top15 equal and inverse-vol portfolios.', 'overlays': ['raw_ml', 'bil_fallback_original', 'vol_target_10pct']}
- Skipped variants: [{'variant': 'differentiable_top_k', 'reason': 'deferred; first version uses masked softmax and separate top-N evaluation'}, {'variant': 'cvxpylayers_or_spo_loss', 'reason': 'deferred; optional package/deeper optimizer integration not required for first CPU-safe sprint'}, {'variant': 'full_walk_forward_retraining', 'reason': 'deferred; selected predictions are evaluated by window without retraining per fold'}, {'variant': 'seed_2', 'reason': 'skipped to keep first decision-focused run bounded on CPU'}, {'variant': 'true_drawdown_gradient_penalty', 'reason': 'simplified to volatility/downside/turnover penalties for stability'}]

## Results

- Models/losses run: ['prediction_bce_mlp_seed0', 'prediction_bce_mlp_seed1', 'decision_return_mlp_seed0', 'decision_return_mlp_seed1', 'decision_sharpe_mlp_seed0', 'decision_sharpe_mlp_seed1', 'decision_risk_aware_mlp_seed0', 'decision_risk_aware_mlp_seed1', 'hybrid_bce_sharpe_mlp_seed0', 'hybrid_bce_sharpe_mlp_seed1']
- Best prediction baseline holdout: `prediction_bce_mlp_seed0__softmax_all__bil_fallback_original` Sharpe 0.496
- Best decision-focused holdout: `decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original` Sharpe 3.711
- Best validation-selected model: `decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original` with validation Sharpe 5.632
- Validation-selected holdout annual return: 1.73%
- Validation-selected holdout Sharpe: 3.577
- Validation-selected max drawdown: -2.33%
- Validation-selected CVaR 5%: -0.12%
- Best holdout diagnostic model: `decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original` Sharpe 3.711

Important caveat: the strongest risk-aware result is low-return, low-volatility, BIL/bond-heavy, and highly concentrated. Its high Sharpe is educational evidence that the portfolio-aware loss found a defensive allocation, not evidence that it discovered robust offensive alpha.

### Top Holdout Strategies

| strategy_name | loss_kind | allocation_method | wrapper | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_turnover | average_bil_exposure | average_top3_weight | rank_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | decision_risk_aware | top15_inverse_vol | bil_fallback_original | 1.98% | 0.53% | 3.711 | -1.92% | -0.12% | 11.57% | 59.15% | 89.63% | -0.100 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | decision_risk_aware | top10_inverse_vol | bil_fallback_original | 1.73% | 0.49% | 3.577 | -2.33% | -0.12% | 16.03% | 62.42% | 92.80% | -0.100 |
| decision_risk_aware_mlp_seed1__top15_inverse_vol__bil_fallback_original | decision_risk_aware | top15_inverse_vol | bil_fallback_original | 1.65% | 0.61% | 2.693 | -2.35% | -0.16% | 16.03% | 57.69% | 87.69% | -0.078 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__raw_ml | decision_risk_aware | top10_inverse_vol | raw_ml | 1.56% | 0.72% | 2.173 | -3.36% | -0.19% | 15.34% | 50.41% | 90.71% | -0.100 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__vol_target_10pct | decision_risk_aware | top10_inverse_vol | vol_target_10pct | 1.56% | 0.72% | 2.173 | -3.36% | -0.19% | 15.34% | 50.41% | 90.71% | -0.100 |
| decision_risk_aware_mlp_seed1__top10_inverse_vol__bil_fallback_original | decision_risk_aware | top10_inverse_vol | bil_fallback_original | 1.30% | 0.62% | 2.086 | -3.13% | -0.17% | 23.01% | 53.70% | 90.55% | -0.078 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__raw_ml | decision_risk_aware | top15_inverse_vol | raw_ml | 1.81% | 0.91% | 1.983 | -3.54% | -0.23% | 8.70% | 46.48% | 86.41% | -0.100 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__vol_target_10pct | decision_risk_aware | top15_inverse_vol | vol_target_10pct | 1.81% | 0.91% | 1.983 | -3.54% | -0.23% | 8.70% | 46.48% | 86.41% | -0.100 |
| decision_risk_aware_mlp_seed1__top15_inverse_vol__raw_ml | decision_risk_aware | top15_inverse_vol | raw_ml | 1.35% | 0.96% | 1.414 | -3.90% | -0.29% | 15.96% | 43.88% | 84.35% | -0.078 |
| decision_risk_aware_mlp_seed1__top15_inverse_vol__vol_target_10pct | decision_risk_aware | top15_inverse_vol | vol_target_10pct | 1.35% | 0.96% | 1.414 | -3.90% | -0.29% | 15.96% | 43.88% | 84.35% | -0.078 |
| decision_risk_aware_mlp_seed1__top10_inverse_vol__raw_ml | decision_risk_aware | top10_inverse_vol | raw_ml | 1.02% | 0.81% | 1.260 | -4.34% | -0.24% | 24.37% | 39.74% | 88.75% | -0.078 |
| decision_risk_aware_mlp_seed1__top10_inverse_vol__vol_target_10pct | decision_risk_aware | top10_inverse_vol | vol_target_10pct | 1.02% | 0.81% | 1.260 | -4.34% | -0.24% | 24.37% | 39.74% | 88.75% | -0.078 |
| decision_return_mlp_seed0__softmax_all__bil_fallback_original | decision_return | softmax_all | bil_fallback_original | 6.16% | 8.52% | 0.723 | -13.72% | -2.72% | 12.60% | 26.25% | 28.64% | 0.046 |
| decision_sharpe_mlp_seed0__softmax_all__bil_fallback_original | decision_sharpe | softmax_all | bil_fallback_original | 6.04% | 8.40% | 0.719 | -13.30% | -2.67% | 12.86% | 26.30% | 28.80% | 0.038 |
| decision_return_mlp_seed1__softmax_all__bil_fallback_original | decision_return | softmax_all | bil_fallback_original | 5.92% | 8.38% | 0.707 | -13.47% | -2.68% | 13.12% | 26.21% | 29.20% | 0.008 |
| decision_sharpe_mlp_seed1__softmax_all__bil_fallback_original | decision_sharpe | softmax_all | bil_fallback_original | 5.78% | 8.20% | 0.706 | -12.95% | -2.62% | 13.26% | 26.25% | 29.35% | -0.007 |
| decision_sharpe_mlp_seed0__top15_inverse_vol__bil_fallback_original | decision_sharpe | top15_inverse_vol | bil_fallback_original | 4.11% | 6.21% | 0.662 | -10.57% | -2.13% | 31.58% | 41.11% | 77.47% | 0.038 |
| decision_risk_aware_mlp_seed0__softmax_all__bil_fallback_original | decision_risk_aware | softmax_all | bil_fallback_original | 1.94% | 3.09% | 0.626 | -7.61% | -0.96% | 18.84% | 32.78% | 45.13% | -0.100 |
| hybrid_bce_sharpe_mlp_seed0__softmax_all__bil_fallback_original | hybrid_bce_sharpe | softmax_all | bil_fallback_original | 5.88% | 9.62% | 0.611 | -15.02% | -3.04% | 17.34% | 25.60% | 32.43% | 0.036 |
| hybrid_bce_sharpe_mlp_seed1__softmax_all__bil_fallback_original | hybrid_bce_sharpe | softmax_all | bil_fallback_original | 5.47% | 9.08% | 0.602 | -15.12% | -2.90% | 16.35% | 25.87% | 32.35% | 0.015 |

### Strategy Comparison

| strategy_name | category | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_bil_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | decision_focused | 1.98% | 0.53% | 3.711 | -1.92% | -0.12% | 59.15% |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | decision_focused | 1.73% | 0.49% | 3.577 | -2.33% | -0.12% | 62.42% |
| decision_risk_aware_mlp_seed1__top15_inverse_vol__bil_fallback_original | decision_focused | 1.65% | 0.61% | 2.693 | -2.35% | -0.16% | 57.69% |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__raw_ml | decision_focused | 1.56% | 0.72% | 2.173 | -3.36% | -0.19% | 50.41% |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__vol_target_10pct | decision_focused | 1.56% | 0.72% | 2.173 | -3.36% | -0.19% | 50.41% |
| decision_risk_aware_mlp_seed1__top10_inverse_vol__bil_fallback_original | decision_focused | 1.30% | 0.62% | 2.086 | -3.13% | -0.17% | 53.70% |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__raw_ml | decision_focused | 1.81% | 0.91% | 1.983 | -3.54% | -0.23% | 46.48% |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__vol_target_10pct | decision_focused | 1.81% | 0.91% | 1.983 | -3.54% | -0.23% | 46.48% |
| decision_risk_aware_mlp_seed1__top15_inverse_vol__raw_ml | decision_focused | 1.35% | 0.96% | 1.414 | -3.90% | -0.29% | 43.88% |
| decision_risk_aware_mlp_seed1__top15_inverse_vol__vol_target_10pct | decision_focused | 1.35% | 0.96% | 1.414 | -3.90% | -0.29% | 43.88% |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only | n/a | n/a | 1.276 | -14.56% | -4.17% | n/a |
| decision_risk_aware_mlp_seed1__top10_inverse_vol__raw_ml | decision_focused | 1.02% | 0.81% | 1.260 | -4.34% | -0.24% | 39.74% |
| decision_risk_aware_mlp_seed1__top10_inverse_vol__vol_target_10pct | decision_focused | 1.02% | 0.81% | 1.260 | -4.34% | -0.24% | 39.74% |
| phase4b | benchmark | 9.64% | 9.01% | 1.070 | -12.44% | -2.72% | n/a |
| phase7 | benchmark | 9.57% | 9.47% | 1.011 | -13.83% | -2.92% | n/a |
| phase6 | benchmark | 9.57% | 9.47% | 1.010 | -13.77% | -2.92% | n/a |
| mlx9_ensemble | benchmark | 8.61% | 8.57% | 1.005 | -13.24% | -2.69% | 1.84% |
| mlx6_transformer | benchmark | 11.16% | 11.30% | 0.987 | -13.13% | -3.29% | 25.15% |
| mlx5_sequence | benchmark | 11.66% | 12.08% | 0.964 | -11.34% | -3.63% | 25.15% |
| official_shadow | benchmark | 8.04% | 8.53% | 0.943 | -13.67% | -2.71% | n/a |
| production | benchmark | 8.07% | 8.60% | 0.938 | -13.98% | -2.73% | n/a |
| mlx4_mlp | benchmark | 18.03% | 19.89% | 0.907 | -29.40% | -6.09% | n/a |
| simple_momentum | benchmark | 22.21% | 25.57% | 0.869 | -43.50% | -7.83% | 0.00% |
| mlx3_tabular | benchmark | 16.85% | 20.78% | 0.811 | -37.55% | -6.52% | n/a |
| decision_return_mlp_seed0__softmax_all__bil_fallback_original | decision_focused | 6.16% | 8.52% | 0.723 | -13.72% | -2.72% | 26.25% |
| decision_sharpe_mlp_seed0__softmax_all__bil_fallback_original | decision_focused | 6.04% | 8.40% | 0.719 | -13.30% | -2.67% | 26.30% |
| decision_return_mlp_seed1__softmax_all__bil_fallback_original | decision_focused | 5.92% | 8.38% | 0.707 | -13.47% | -2.68% | 26.21% |
| decision_sharpe_mlp_seed1__softmax_all__bil_fallback_original | decision_focused | 5.78% | 8.20% | 0.706 | -12.95% | -2.62% | 26.25% |
| SPY | benchmark | 13.24% | 19.37% | 0.683 | -33.63% | -6.31% | n/a |
| 60_40 | benchmark | 8.19% | 12.05% | 0.680 | -21.88% | -3.85% | n/a |

### Walk-Forward Window Evaluation

| strategy_name | window | annual_return | sharpe | max_drawdown | cvar_5 | active_weeks |
| --- | --- | --- | --- | --- | --- | --- |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | 2017_2018 | 0.50% | 1.540 | -0.35% | -0.10% | 104 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | 2019_2020 | 0.87% | 2.106 | -0.91% | -0.12% | 104 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | 2021_2022 | -0.18% | -0.525 | -1.31% | -0.11% | 105 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | 2023_2026 | 3.52% | 8.040 | -0.25% | -0.09% | 175 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | 2017_2018 | 0.66% | 1.574 | -0.44% | -0.13% | 104 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | 2019_2020 | 1.21% | 2.437 | -0.78% | -0.14% | 104 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | 2021_2022 | -0.08% | -0.230 | -1.09% | -0.10% | 105 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | 2023_2026 | 3.81% | 7.591 | -0.23% | -0.08% | 175 |

### State-By-State Results

| strategy_name | market_state | annual_return | sharpe | max_drawdown | cvar_5 | average_bil_exposure | average_risky_exposure | weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | calm_trend | 2.13% | 3.835 | -0.64% | -0.12% | 50.09% | 49.91% | 101 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | neutral_mixed | 1.90% | 3.788 | -1.08% | -0.11% | 62.59% | 37.41% | 121 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | recovery_confirmed | 0.99% | 2.329 | -0.23% | -0.08% | 43.55% | 56.45% | 21 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | recovery_fragile | 2.34% | 6.278 | -0.02% | -0.04% | 44.99% | 55.01% | 14 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | stressed_panic | 1.02% | 2.973 | -0.13% | -0.10% | 88.35% | 11.65% | 71 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | unknown | 1.08% | 2.483 | -0.08% | -0.08% | 68.99% | 31.01% | 4 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | calm_trend | 2.42% | 4.112 | -0.63% | -0.11% | 44.42% | 55.58% | 101 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | neutral_mixed | 2.38% | 4.571 | -0.72% | -0.09% | 59.29% | 40.71% | 121 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | recovery_confirmed | 1.44% | 3.021 | -0.20% | -0.05% | 41.53% | 58.47% | 21 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | recovery_fragile | 1.91% | 3.515 | -0.10% | -0.10% | 42.40% | 57.60% | 14 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | stressed_panic | 0.89% | 1.994 | -0.16% | -0.14% | 87.95% | 12.05% | 71 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | unknown | 1.03% | 2.326 | -0.09% | -0.09% | 67.18% | 32.82% | 4 |

### Exposure Audit

| strategy_name | audit_type | item | category | average_weight | max_weight | holding_frequency |
| --- | --- | --- | --- | --- | --- | --- |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | Bonds | Bonds | 0.9733713997285312 | 1.0 | 1.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | Credit | Credit | 0.019984216928607038 | 0.12911402057930177 | 0.5180722891566265 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | Currency/dollar | Currency/dollar | 0.003709380750973454 | 0.026701358511553735 | 0.12349397590361445 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | US sectors | US sectors | 0.0027648818924346005 | 0.01720770246603964 | 0.045180722891566265 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | Factors/styles | Factors/styles | 0.00010094878794360003 | 0.0071519517696385015 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | Commodities | Commodities | 4.312896134025531e-05 | 0.003221510012966375 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | category | International equity | International equity | 2.6042950170010633e-05 | 0.0015179044563212712 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | summary | average_top3_weight |  | 0.9279603807066256 | 1.0 | n/a |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | summary | average_safe_asset_weight |  | 0.697036713297982 | 1.0 | n/a |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | summary | average_BIL_weight |  | 0.6242474832600423 | 1.0 | n/a |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | summary | average_sector_weight |  | 0.0027648818924346005 | 0.01720770246603964 | n/a |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | summary | average_commodities_weight |  | 4.312896134025531e-05 | 0.003221510012966375 | n/a |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | summary | average_SPY_QQQ_SMH_weight |  | 0.0 | 0.0 | n/a |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | BIL | Bonds | 0.6242474832600423 | 1.0 | 0.9849397590361446 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | SHV | Bonds | 0.25731768781069875 | 0.7245355982225045 | 0.891566265060241 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | SHY | Bonds | 0.040019410655365587 | 0.19204045848758303 | 0.8403614457831325 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | STIP | Bonds | 0.015597168473067536 | 0.06621007539209728 | 0.608433734939759 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | MBB | Bonds | 0.013785743022489217 | 0.07616572828746683 | 0.45481927710843373 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | VCSH | Credit | 0.009989167994928137 | 0.10024399793415167 | 0.3493975903614458 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | IEF | Bonds | 0.006341381420440742 | 0.019013999884474896 | 0.14457831325301204 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | JNK | Credit | 0.006011900901357488 | 0.02802950958637737 | 0.2710843373493976 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | TIP | Bonds | 0.006000625224842089 | 0.028274685251133268 | 0.25903614457831325 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | UUP | Currency/dollar | 0.003698831348755718 | 0.026701358511553735 | 0.12349397590361445 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | MUB | Bonds | 0.0036651588387847447 | 0.034495975712809 | 0.1686746987951807 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | AGG | Bonds | 0.0034541579900077457 | 0.031433289450304006 | 0.16265060240963855 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | LQD | Credit | 0.0023556457643282708 | 0.016584230841313163 | 0.05421686746987952 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | XLP | US sectors | 0.0023172835461940937 | 0.012389899506467305 | 0.02710843373493976 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | BKLN | Credit | 0.0015600573401565567 | 0.034112759251504615 | 0.06325301204819277 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | VGIT | Bonds | 0.0011456657841587546 | 0.01806638288951763 | 0.04819277108433735 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | VGSH | Bonds | 0.0009646512881675192 | 0.09241111131447305 | 0.03313253012048193 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | TLT | Bonds | 0.0006851824909287936 | 0.009788802052682927 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | XLU | US sectors | 0.0004475983462405069 | 0.0069326471648484414 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | BND | Bonds | 0.00014708346953723855 | 0.010191728268653213 | 0.0030120481927710845 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | MTUM | Factors/styles | 0.00010094878794360003 | 0.0071519517696385015 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | VCIT | Credit | 6.744492783658634e-05 | 0.012042137204701996 | 0.0030120481927710845 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | DBA | Commodities | 2.72754629644581e-05 | 0.0012818977483764907 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | EWA | International equity | 1.6662266666155446e-05 | 0.0007577486360391815 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | IAU | Commodities | 1.267463528663895e-05 | 0.003221510012966375 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | FXE | Currency/dollar | 1.0549402217735914e-05 | 0.0035024015362883237 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | EWJ | International equity | 7.1736982588348465e-06 | 0.0008217940255874265 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | GLD | Commodities | 3.1788630891582643e-06 | 0.0010553825456005438 | 0.0 |
| decision_risk_aware_mlp_seed0__top10_inverse_vol__bil_fallback_original | ticker | ASHR | International equity | 2.2069852450203444e-06 | 0.0007327191013467544 | 0.0 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | Bonds | Bonds | 0.9606495360013703 | 1.0 | 1.0 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | Credit | Credit | 0.030068232392649188 | 0.09285842437509859 | 0.6987951807228916 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | Currency/dollar | Currency/dollar | 0.0046847413013012375 | 0.024413564808597712 | 0.10843373493975904 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | US sectors | US sectors | 0.003812110956920701 | 0.018449462610169415 | 0.04819277108433735 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | Factors/styles | Factors/styles | 0.00043154893381975223 | 0.011090834184930438 | 0.0030120481927710845 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | Commodities | Commodities | 0.00017390486680809178 | 0.005928046659489374 | 0.0 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | International equity | International equity | 0.0001538372061999936 | 0.008297244715837782 | 0.0 |
| decision_risk_aware_mlp_seed0__top15_inverse_vol__bil_fallback_original | category | Real estate | Real estate | 2.608834093071043e-05 | 0.0024507682733159227 | 0.0 |

## Interpretation

- Did decision-focused training beat the prediction-trained baseline? True
- Did the validation-selected model beat MLX-5C mean Sharpe? True
- Did it beat MLX-9? True
- Did it beat production? True
- Did it beat Phase 4B? True
- Final recommendation: **PROMISING LEARNING RESULT BUT NOT PORTFOLIO CANDIDATE**

The key learning question is whether a portfolio-aware objective reduces the mismatch between labels and allocation quality. This first version is deliberately simplified. A stronger next version should use explicit ranking or SPO-style decision losses, differentiable mean-variance or CVaR layers, better validation discipline, and full walk-forward retraining.

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- Expanded ETF/yfinance research data can introduce selection bias and data-mining risk.
- Best risk-aware result is BIL/bond-heavy and low-return; high Sharpe should not be interpreted as robust offensive alpha.
- No decision-focused model is promoted automatically.
