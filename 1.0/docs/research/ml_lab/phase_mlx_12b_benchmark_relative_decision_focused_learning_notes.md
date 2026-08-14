# Phase MLX-12B Benchmark-Relative Decision-Focused Learning Notes

## Research-Only Warning

Phase MLX-12B is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Benchmark-relative decision-focused learning trains the model on the quality of the portfolio decision relative to a benchmark such as production or Phase 4B. MLX-12 optimized an absolute Sharpe-like objective and found a low-volatility solution by hiding in BIL/bonds. MLX-12B asks a different question: can the model add incremental value over an existing strategy while keeping risk controlled?

Optimizing excess return versus production or Phase 4B is different from optimizing raw return or raw Sharpe. A portfolio that earns 2% with tiny volatility can have a high Sharpe, but it is not useful if production earns much more with acceptable risk. Relative objectives care about active return, tracking error, and information ratio.

Constraints on BIL and offensive exposure matter because otherwise a risk-aware model can choose the easiest feasible point: cash or bonds. This sprint penalizes excess safe-asset exposure in good states while still allowing BIL in stressed regimes. Tracking error measures the volatility of returns versus the benchmark. Information ratio is annualized excess return divided by tracking error.

Triple-barrier labels from MLX-13 help define path-aware penalties: danger labels penalize taking risk when bad paths historically occurred, while positive barrier labels discourage hiding in safe assets when good paths were available. This is still risky and can overfit because the labels are estimated from historical paths.

## EECS 127 / Optimization Connection

This sprint is an optimization-design exercise. The model has an objective function, a feasible set, and penalty terms. The feasible set is long-only ETF weights from a softmax allocation. The objective rewards benchmark-relative performance. The penalties represent Lagrangian-style tradeoffs: turnover, downside risk, BIL/safe-asset exposure, and triple-barrier path risk.

MLX-12 showed that the wrong objective gives the wrong optimum: absolute Sharpe made BIL/bonds look optimal. MLX-12B changes the objective and constraints, so the optimum is forced to answer a more useful question: can the model improve on a benchmark without simply becoming cash?

## Technical Setup

- Torch availability: {'available': True, 'version': '2.8.0', 'device': 'cpu', 'cuda_available': False, 'mps_available': True}
- Universe size: 97
- Input tensor shape: `[1375, 97, 74]`
- Architecture: {'model': 'per-ETF MLP scorer with learned ETF embedding', 'input_projection': 'Linear(74 -> 64)', 'hidden_dim': 64, 'dropout': 0.15, 'output': 'one score per ETF per date', 'allocation_training': 'masked softmax long-only ETF portfolio', 'temperature': 0.5}
- Objectives tested: ['relative_return', 'relative_info_ratio', 'risk_constrained_relative', 'offensive_exposure_constrained', 'triple_barrier_aware', 'hybrid_bce_relative']
- Benchmarks tested: ['production', 'phase4b']
- Candidate definitions: {'relative_return': 'Maximize portfolio return above benchmark with turnover, volatility, and safe-exposure penalties.', 'relative_info_ratio': 'Maximize mean excess return divided by tracking error with penalties.', 'risk_constrained_relative': 'Reward excess return while penalizing downside worse than the benchmark, CVaR proxy, turnover, and safe exposure.', 'offensive_exposure_constrained': 'Strongly penalize hiding in safe assets in good states.', 'triple_barrier_aware': 'Use MLX-13 path-aware labels as penalties: avoid risky exposure on danger labels and avoid safe hiding on positive labels.', 'hybrid_bce_relative': 'Combine top-quintile BCE with benchmark-relative decision loss.', 'benchmarks': ['production', 'phase4b'], 'wrappers': ['raw_ml', 'bil_fallback_original', 'regime_gate_original', 'production_core_plus_10pct_model_sleeve', 'phase4b_core_plus_10pct_model_sleeve']}
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill and train-only standardization
- Leakage controls: model inputs exclude target-like columns; MLX-13 labels are used only in losses/penalties, not as input features
- Skipped variants: [{'variant': 'absolute_sharpe_objective', 'reason': 'intentionally excluded to avoid MLX-12 BIL/bond collapse'}, {'variant': 'seed_2', 'reason': 'skipped to keep first benchmark-relative run bounded on CPU'}, {'variant': 'differentiable_top_k', 'reason': 'deferred; first version uses masked softmax training and top-N evaluation'}, {'variant': 'full_walk_forward_retraining', 'reason': 'deferred; selected predictions are evaluated by window without retraining per fold'}, {'variant': 'cvxpylayers_mean_variance_layer', 'reason': 'deferred; no optional optimizer-layer dependency added'}, {'variant': 'relative_info_ratio_seed1', 'reason': 'skipped after an initial full-grid attempt proved too slow for a bounded CPU first version'}, {'variant': 'offensive_exposure_constrained_seed1', 'reason': 'skipped after an initial full-grid attempt proved too slow for a bounded CPU first version'}, {'variant': 'triple_barrier_aware_seed1', 'reason': 'skipped after an initial full-grid attempt proved too slow for a bounded CPU first version'}]

## Results

- Best validation-selected model: `relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml` with validation information ratio 0.561
- Validation-selected holdout annual return: 0.69%
- Validation-selected holdout Sharpe: 0.040
- Validation-selected holdout max drawdown: -36.41%
- Validation-selected holdout CVaR 5%: -5.84%
- Validation-selected information ratio: -0.572
- Best holdout-diagnostic model: `triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve` with holdout information ratio 0.659

### Top Holdout Strategies

| strategy_name | loss_kind | objective_benchmark | allocation_method | wrapper | annual_return | sharpe | max_drawdown | cvar_5 | average_benchmark_excess_return | tracking_error | information_ratio | average_safe_exposure | average_bil_exposure | average_top3_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | triple_barrier_aware | production | top10_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.72% | 1.082 | -12.00% | -2.72% | 1.65% | 2.50% | 0.659 | 2.17% | 2.17% | 2.38% |
| triple_barrier_aware_production_seed0__top15_equal_weight__phase4b_core_plus_10pct_model_sleeve | triple_barrier_aware | production | top15_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.60% | 1.069 | -12.06% | -2.72% | 1.54% | 2.49% | 0.617 | 2.17% | 2.17% | 1.60% |
| triple_barrier_aware_production_seed0__softmax_all__phase4b_core_plus_10pct_model_sleeve | triple_barrier_aware | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.55% | 1.077 | -12.04% | -2.69% | 1.49% | 2.42% | 0.615 | 2.33% | 2.18% | 0.86% |
| triple_barrier_aware_production_seed0__top10_inverse_vol__phase4b_core_plus_10pct_model_sleeve | triple_barrier_aware | production | top10_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.55% | 1.073 | -11.89% | -2.70% | 1.49% | 2.49% | 0.597 | 2.17% | 2.17% | 3.52% |
| triple_barrier_aware_production_seed0__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | triple_barrier_aware | production | top15_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.52% | 1.069 | -11.99% | -2.70% | 1.46% | 2.47% | 0.593 | 2.17% | 2.17% | 2.55% |
| relative_info_ratio_production_seed0__softmax_all__phase4b_core_plus_10pct_model_sleeve | relative_info_ratio | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.40% | 1.078 | -11.93% | -2.65% | 1.33% | 2.35% | 0.567 | 3.15% | 2.25% | 0.39% |
| hybrid_bce_relative_production_seed0__softmax_all__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.37% | 1.072 | -11.90% | -2.65% | 1.31% | 2.35% | 0.558 | 2.82% | 2.19% | 0.69% |
| relative_return_production_seed0__softmax_all__phase4b_core_plus_10pct_model_sleeve | relative_return | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.37% | 1.080 | -11.86% | -2.64% | 1.30% | 2.34% | 0.557 | 3.35% | 2.26% | 0.32% |
| relative_return_production_seed1__softmax_all__phase4b_core_plus_10pct_model_sleeve | relative_return | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.36% | 1.079 | -11.86% | -2.64% | 1.30% | 2.34% | 0.554 | 3.36% | 2.25% | 0.34% |
| offensive_exposure_constrained_production_seed0__softmax_all__phase4b_core_plus_10pct_model_sleeve | offensive_exposure_constrained | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.34% | 1.077 | -11.83% | -2.64% | 1.27% | 2.34% | 0.544 | 3.49% | 2.28% | 0.37% |
| hybrid_bce_relative_production_seed1__softmax_all__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.28% | 1.062 | -11.95% | -2.65% | 1.22% | 2.35% | 0.521 | 2.70% | 2.20% | 1.08% |
| hybrid_bce_relative_production_seed0__top10_inverse_vol__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | top10_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.29% | 1.047 | -11.96% | -2.69% | 1.25% | 2.41% | 0.516 | 2.18% | 2.17% | 3.46% |
| hybrid_bce_relative_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | top10_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.26% | 1.056 | -11.69% | -2.63% | 1.21% | 2.42% | 0.500 | 2.17% | 2.17% | 2.38% |
| relative_info_ratio_production_seed0__top15_equal_weight__phase4b_core_plus_10pct_model_sleeve | relative_info_ratio | production | top15_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.23% | 1.037 | -12.11% | -2.70% | 1.20% | 2.43% | 0.493 | 2.44% | 2.18% | 1.60% |
| relative_info_ratio_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | relative_info_ratio | production | top10_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.24% | 1.037 | -12.13% | -2.70% | 1.20% | 2.44% | 0.492 | 2.33% | 2.17% | 2.38% |
| risk_constrained_relative_production_seed1__softmax_all__phase4b_core_plus_10pct_model_sleeve | risk_constrained_relative | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.19% | 1.067 | -11.69% | -2.62% | 1.13% | 2.33% | 0.484 | 4.15% | 2.34% | 0.97% |
| risk_constrained_relative_production_seed0__softmax_all__phase4b_core_plus_10pct_model_sleeve | risk_constrained_relative | production | softmax_all | phase4b_core_plus_10pct_model_sleeve | 9.18% | 1.064 | -11.72% | -2.63% | 1.12% | 2.34% | 0.480 | 4.07% | 2.40% | 0.70% |
| hybrid_bce_relative_production_seed0__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | top15_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.19% | 1.035 | -12.11% | -2.71% | 1.15% | 2.41% | 0.478 | 2.34% | 2.17% | 2.55% |
| hybrid_bce_relative_production_seed0__top15_equal_weight__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | top15_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.14% | 1.041 | -11.87% | -2.65% | 1.10% | 2.38% | 0.463 | 2.21% | 2.17% | 1.60% |
| hybrid_bce_relative_production_seed1__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | top15_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.11% | 1.019 | -12.13% | -2.74% | 1.09% | 2.45% | 0.444 | 2.17% | 2.17% | 2.32% |
| relative_return_production_seed0__top15_equal_weight__phase4b_core_plus_10pct_model_sleeve | relative_return | production | top15_equal_weight | phase4b_core_plus_10pct_model_sleeve | 9.07% | 1.048 | -11.69% | -2.63% | 1.03% | 2.37% | 0.432 | 4.03% | 2.54% | 1.60% |
| relative_info_ratio_production_seed0__top10_inverse_vol__phase4b_core_plus_10pct_model_sleeve | relative_info_ratio | production | top10_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.03% | 1.034 | -12.05% | -2.66% | 1.00% | 2.39% | 0.418 | 3.56% | 2.17% | 4.19% |
| hybrid_bce_relative_production_seed1__top10_inverse_vol__phase4b_core_plus_10pct_model_sleeve | hybrid_bce_relative | production | top10_inverse_vol | phase4b_core_plus_10pct_model_sleeve | 9.03% | 1.014 | -12.09% | -2.71% | 1.01% | 2.45% | 0.413 | 2.17% | 2.17% | 3.29% |
| relative_return_production_seed1__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | relative_return | production | top10_equal_weight | phase4b_core_plus_10pct_model_sleeve | 8.92% | 1.033 | -11.96% | -2.63% | 0.89% | 2.30% | 0.385 | 4.13% | 2.17% | 2.38% |
| relative_return_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | relative_return | production | top10_equal_weight | phase4b_core_plus_10pct_model_sleeve | 8.94% | 1.038 | -11.83% | -2.64% | 0.90% | 2.36% | 0.383 | 4.35% | 2.71% | 2.38% |

### Strategy Comparison

| strategy_name | category | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_benchmark_excess_return | tracking_error | information_ratio | average_safe_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx12_decision_focused | benchmark | 1.73% | 0.49% | 3.577 | -2.33% | -0.12% | -6.41% | 8.47% | -0.756 | 0.00% |
| risk_constrained_relative_production_seed0__top15_inverse_vol__regime_gate_original | benchmark_relative_model | 1.80% | 1.25% | 1.439 | -3.47% | -0.46% | -6.25% | 8.07% | -0.774 | 92.91% |
| risk_constrained_relative_phase4b_seed0__top15_inverse_vol__regime_gate_original | benchmark_relative_model | 1.79% | 1.26% | 1.424 | -3.55% | -0.46% | -7.72% | 8.54% | -0.904 | 93.24% |
| risk_constrained_relative_production_seed0__top15_inverse_vol__bil_fallback_original | benchmark_relative_model | 1.77% | 1.26% | 1.403 | -3.37% | -0.46% | -6.27% | 8.04% | -0.780 | 92.59% |
| risk_constrained_relative_phase4b_seed0__top15_inverse_vol__bil_fallback_original | benchmark_relative_model | 1.77% | 1.27% | 1.389 | -3.42% | -0.46% | -7.74% | 8.51% | -0.910 | 92.91% |
| offensive_exposure_constrained_phase4b_seed0__top15_inverse_vol__regime_gate_original | benchmark_relative_model | 2.11% | 1.57% | 1.345 | -3.33% | -0.48% | -7.40% | 8.52% | -0.869 | 91.49% |
| offensive_exposure_constrained_production_seed0__top15_inverse_vol__regime_gate_original | benchmark_relative_model | 2.11% | 1.57% | 1.345 | -3.33% | -0.48% | -5.93% | 8.03% | -0.739 | 91.49% |
| risk_constrained_relative_production_seed1__top15_inverse_vol__regime_gate_original | benchmark_relative_model | 1.78% | 1.33% | 1.338 | -4.54% | -0.48% | -6.27% | 8.04% | -0.780 | 89.25% |
| offensive_exposure_constrained_phase4b_seed0__top15_inverse_vol__bil_fallback_original | benchmark_relative_model | 2.07% | 1.59% | 1.304 | -3.33% | -0.48% | -7.44% | 8.49% | -0.877 | 91.11% |
| offensive_exposure_constrained_production_seed0__top15_inverse_vol__bil_fallback_original | benchmark_relative_model | 2.07% | 1.59% | 1.304 | -3.33% | -0.48% | -5.98% | 8.00% | -0.747 | 91.11% |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only | n/a | n/a | 1.276 | -14.56% | -4.17% | n/a | n/a | n/a | n/a |
| risk_constrained_relative_production_seed1__top15_inverse_vol__bil_fallback_original | benchmark_relative_model | 1.71% | 1.37% | 1.244 | -4.39% | -0.50% | -6.34% | 8.01% | -0.791 | 88.71% |
| risk_constrained_relative_phase4b_seed1__top15_inverse_vol__regime_gate_original | benchmark_relative_model | 1.59% | 1.31% | 1.216 | -4.51% | -0.51% | -7.92% | 8.50% | -0.932 | 89.28% |
| risk_constrained_relative_production_seed0__top10_inverse_vol__regime_gate_original | benchmark_relative_model | 1.85% | 1.56% | 1.183 | -4.66% | -0.54% | -6.20% | 8.10% | -0.765 | 92.86% |
| risk_constrained_relative_phase4b_seed0__top10_inverse_vol__regime_gate_original | benchmark_relative_model | 1.79% | 1.53% | 1.169 | -4.65% | -0.53% | -7.72% | 8.58% | -0.899 | 93.09% |
| mlx13_holdout_diagnostic | benchmark | 10.28% | 8.82% | 1.165 | -12.44% | -2.56% | 1.64% | 2.49% | 0.657 | 0.00% |
| offensive_exposure_constrained_phase4b_seed0__top10_inverse_vol__regime_gate_original | benchmark_relative_model | 2.15% | 1.85% | 1.161 | -4.29% | -0.64% | -7.36% | 8.54% | -0.862 | 91.69% |
| offensive_exposure_constrained_production_seed0__top10_inverse_vol__regime_gate_original | benchmark_relative_model | 2.15% | 1.85% | 1.161 | -4.29% | -0.64% | -5.90% | 8.05% | -0.733 | 91.69% |
| risk_constrained_relative_production_seed0__top10_inverse_vol__bil_fallback_original | benchmark_relative_model | 1.79% | 1.59% | 1.127 | -4.61% | -0.56% | -6.25% | 8.08% | -0.774 | 92.61% |
| risk_constrained_relative_phase4b_seed1__top15_inverse_vol__bil_fallback_original | benchmark_relative_model | 1.51% | 1.35% | 1.123 | -4.34% | -0.52% | -7.99% | 8.46% | -0.944 | 88.72% |
| offensive_exposure_constrained_phase4b_seed0__top10_inverse_vol__bil_fallback_original | benchmark_relative_model | 2.11% | 1.90% | 1.110 | -4.19% | -0.67% | -7.40% | 8.52% | -0.868 | 91.35% |
| offensive_exposure_constrained_production_seed0__top10_inverse_vol__bil_fallback_original | benchmark_relative_model | 2.11% | 1.90% | 1.110 | -4.19% | -0.67% | -5.93% | 8.02% | -0.739 | 91.35% |
| risk_constrained_relative_phase4b_seed0__top10_inverse_vol__bil_fallback_original | benchmark_relative_model | 1.72% | 1.56% | 1.105 | -4.64% | -0.55% | -7.78% | 8.56% | -0.908 | 92.84% |
| triple_barrier_aware_phase4b_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 9.81% | 8.99% | 1.091 | -11.77% | -2.71% | 0.27% | 0.94% | 0.290 | 2.17% |
| offensive_exposure_constrained_phase4b_seed0__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 8.80% | 8.12% | 1.084 | -11.21% | -2.47% | -0.73% | 0.85% | -0.861 | 9.07% |
| offensive_exposure_constrained_production_seed0__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 8.80% | 8.12% | 1.084 | -11.21% | -2.47% | 0.73% | 2.32% | 0.317 | 9.07% |
| offensive_exposure_constrained_phase4b_seed0__top10_inverse_vol__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 8.80% | 8.12% | 1.083 | -11.20% | -2.47% | -0.73% | 0.85% | -0.855 | 9.09% |
| offensive_exposure_constrained_production_seed0__top10_inverse_vol__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 8.80% | 8.12% | 1.083 | -11.20% | -2.47% | 0.74% | 2.32% | 0.318 | 9.09% |
| relative_return_phase4b_seed0__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 8.90% | 8.22% | 1.083 | -11.26% | -2.50% | -0.63% | 0.78% | -0.809 | 8.18% |
| relative_return_production_seed0__top15_inverse_vol__phase4b_core_plus_10pct_model_sleeve | benchmark_relative_model | 8.90% | 8.22% | 1.083 | -11.26% | -2.50% | 0.83% | 2.33% | 0.357 | 8.18% |

### State-By-State Results

| strategy_name | market_state | annual_return | sharpe | max_drawdown | cvar_5 | average_benchmark_excess_return | information_ratio | average_bil_exposure | average_risky_exposure | weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | calm_trend | -6.26% | -0.590 | -15.21% | -3.78% | -10.68% | -1.661 | 1.39% | 69.14% | 101 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | neutral_mixed | 13.06% | 1.092 | -16.63% | -3.12% | -8.46% | -0.850 | 0.00% | 65.36% | 121 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | recovery_confirmed | -11.41% | -1.143 | -5.33% | -3.38% | -11.16% | -1.640 | 0.00% | 58.05% | 21 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | recovery_fragile | 0.74% | 0.099 | -3.76% | -2.70% | -6.03% | -1.221 | 11.23% | 42.45% | 14 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | stressed_panic | -4.96% | -0.164 | -21.54% | -11.13% | -0.12% | -0.005 | 0.00% | 89.69% | 71 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | unknown | -0.01% | -0.014 | -0.20% | -0.20% | -0.01% | -0.010 | 25.00% | 5.02% | 4 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | calm_trend | 4.30% | 0.540 | -7.66% | -2.38% | 1.24% | 0.455 | 0.00% | 10.00% | 101 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | neutral_mixed | 23.41% | 2.428 | -4.68% | -2.35% | 2.13% | 0.785 | 0.00% | 10.00% | 121 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | recovery_confirmed | -0.26% | -0.029 | -3.53% | -2.30% | 1.12% | 0.351 | 0.00% | 10.00% | 21 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | recovery_fragile | 7.95% | 1.314 | -3.07% | -1.44% | 0.47% | 0.260 | 0.00% | 10.00% | 14 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | stressed_panic | -0.50% | -0.053 | -5.35% | -3.38% | 1.29% | 0.839 | 10.00% | 0.00% | 71 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | unknown | 11.43% | 9.483 | -0.02% | -0.02% | 10.84% | 8.995 | 2.50% | 10.00% | 4 |

### Walk-Forward Window Results

| strategy_name | window | annual_return | sharpe | max_drawdown | cvar_5 | average_benchmark_excess_return | information_ratio | active_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | 2017_2018 | 8.92% | 0.924 | -8.19% | -3.66% | 4.10% | 0.647 | 104 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | 2019_2020 | 8.30% | 0.357 | -36.41% | -8.33% | 1.04% | 0.062 | 104 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | 2021_2022 | -3.79% | -0.246 | -24.96% | -4.58% | -7.64% | -0.641 | 105 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | 2023_2026 | 3.42% | 0.339 | -14.59% | -3.32% | -9.04% | -1.073 | 175 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | 2017_2018 | 4.65% | 0.732 | -9.79% | -2.18% | -0.71% | -0.525 | 104 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | 2019_2020 | 9.84% | 0.980 | -12.00% | -3.50% | 2.80% | 1.187 | 104 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | 2021_2022 | 4.71% | 0.626 | -6.49% | -2.24% | -0.20% | -0.068 | 105 |
| triple_barrier_aware_production_seed0__top10_equal_weight__phase4b_core_plus_10pct_model_sleeve | 2023_2026 | 13.80% | 1.699 | -6.63% | -2.05% | 1.59% | 0.731 | 175 |

### Exposure Audit

| strategy_name | audit_type | item | category | average_weight | max_weight | holding_frequency |
| --- | --- | --- | --- | --- | --- | --- |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | Bonds | Bonds | 0.3044187677544446 | 1.0 | 0.4246987951807229 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | International equity | International equity | 0.1799666790312713 | 0.4150559532257122 | 0.9939759036144579 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | Factors/styles | Factors/styles | 0.13874412753299933 | 0.4239198042514026 | 0.963855421686747 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | US broad equity | US broad equity | 0.10273609127975722 | 0.2856417683833508 | 0.9457831325301205 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | Credit | Credit | 0.08953874264586 | 0.31821210073355133 | 0.8373493975903614 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | US sectors | US sectors | 0.08781159353664462 | 0.39995689982585625 | 0.8945783132530121 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | Real estate | Real estate | 0.08215238913672364 | 0.27632702644843127 | 0.8795180722891566 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | category | Commodities | Commodities | 0.014631609082299291 | 0.3159099361558394 | 0.1566265060240964 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | summary | average_top3_weight |  | 0.5128828152955335 | 1.0 | n/a |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | summary | average_safe_asset_weight |  | 0.3044187677544446 | 1.0 | n/a |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | summary | average_sector_weight |  | 0.08781159353664462 | 0.39995689982585625 | n/a |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | summary | average_commodities_weight |  | 0.014631609082299291 | 0.3159099361558394 | n/a |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | summary | average_BIL_weight |  | 0.011980018729049703 | 1.0 | n/a |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | summary | average_SPY_QQQ_SMH_weight |  | 0.001545163983772967 | 0.048144923938607184 | n/a |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | SHV | Bonds | 0.2662066934580685 | 0.9386895079228936 | 0.31626506024096385 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | EMB | Credit | 0.081141366023638 | 0.2664785514698435 | 0.7831325301204819 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VNQI | Real estate | 0.04943046553165748 | 0.17851524252653245 | 0.7560240963855421 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | EWC | International equity | 0.04426161249825885 | 0.13313123442585253 | 0.7650602409638554 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | INDA | International equity | 0.042584930913899824 | 0.12348979918711361 | 0.7018072289156626 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | EWA | International equity | 0.04011958097949933 | 0.07677573985056418 | 0.7710843373493976 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | XLI | US sectors | 0.03650033815047 | 0.0962998549534085 | 0.6686746987951807 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | IWM | US broad equity | 0.03135779774914682 | 0.07084977283138134 | 0.6234939759036144 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | SCHD | Factors/styles | 0.028897153391335785 | 0.1139132257420305 | 0.4367469879518072 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VWO | International equity | 0.026256300461612682 | 0.09207871861419448 | 0.4789156626506024 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | BND | Bonds | 0.0251092348303417 | 0.4807876149056756 | 0.1355421686746988 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VUG | Factors/styles | 0.024613137747703795 | 0.09977271470546041 | 0.45481927710843373 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VTI | US broad equity | 0.02438109206900946 | 0.09986714449603273 | 0.4006024096385542 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | DVY | Factors/styles | 0.0242309330964089 | 0.09342102472703458 | 0.39759036144578314 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | REET | Real estate | 0.024182897719086455 | 0.11352621162711218 | 0.42771084337349397 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | IVW | Factors/styles | 0.022891594297758267 | 0.10998475240983982 | 0.37650602409638556 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | MDY | US broad equity | 0.018551435154795095 | 0.07166277319696178 | 0.3433734939759036 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | IVE | Factors/styles | 0.017510647725975423 | 0.09897511609616798 | 0.29819277108433734 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | XLY | US sectors | 0.017490436678427434 | 0.07180537089117241 | 0.3493975903614458 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | XLRE | US sectors | 0.016542434836388113 | 0.07373175360339025 | 0.3253012048192771 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | FXI | International equity | 0.01543096981064766 | 0.13628200027441884 | 0.3132530120481928 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | BIL | Bonds | 0.011980018729049703 | 1.0 | 0.018072289156626505 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | RSP | Factors/styles | 0.010938808261428384 | 0.08098110776202792 | 0.17771084337349397 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | SCHB | US broad equity | 0.010871224909089922 | 0.07831047311327685 | 0.19578313253012047 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | JNK | Credit | 0.008397376622221989 | 0.15775815884576677 | 0.09939759036144578 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VOO | US broad equity | 0.008031389952377926 | 0.07413921595697416 | 0.13253012048192772 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | QUAL | Factors/styles | 0.00772917698711469 | 0.09637018349335232 | 0.12048192771084337 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | IAU | Commodities | 0.0060260348222543674 | 0.12591054232100138 | 0.07530120481927711 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | PDBC | Commodities | 0.005922878843253974 | 0.12224858929657649 | 0.0783132530120482 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VNQ | Real estate | 0.005427536533672339 | 0.06687154656924162 | 0.10843373493975904 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | XLP | US sectors | 0.005281591819412464 | 0.10474660315052078 | 0.07530120481927711 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | IJH | US broad equity | 0.004773802107295783 | 0.07019777604774145 | 0.08433734939759036 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | EWY | International equity | 0.004389504023279881 | 0.0579412563674995 | 0.10843373493975904 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | VEA | International equity | 0.004378778991013202 | 0.08481482264075958 | 0.07530120481927711 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | XBI | US sectors | 0.003877799429188473 | 0.06552507617170478 | 0.0963855421686747 |
| relative_info_ratio_phase4b_seed0__top15_inverse_vol__raw_ml | ticker | XLB | US sectors | 0.0034542482899257306 | 0.07589235634081601 | 0.060240963855421686 |

## Interpretation

- Did benchmark-relative training prevent BIL/bond collapse? True
- Did the validation-selected model beat original MLX-12 by annual return? False
- Did it beat production by Sharpe? False
- Did it beat Phase 4B by Sharpe? False
- Did it beat MLX-9 by Sharpe? False
- Final recommendation: **REJECT**

The key educational result is whether changing the objective and constraints changes the learned solution. A positive result does not imply production readiness; it means the problem formulation is more useful than absolute Sharpe.

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- Benchmark-relative objectives still use yfinance/expanded ETF research data and remain high overfitting risk.
- No benchmark-relative decision-focused model is promoted automatically.
