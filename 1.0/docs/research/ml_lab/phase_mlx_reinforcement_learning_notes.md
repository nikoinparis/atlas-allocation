# Phase MLX Reinforcement Learning Notes

## Research-Only Warning

Phase MLX-8 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Reinforcement learning is a setup where an agent learns by taking actions in an environment and receiving rewards. The environment is the simulated weekly ETF market. The observation is the information the agent sees at date `t`, such as recent ETF returns, volatility, regime features, model confidence summaries, and previous portfolio weights. The action is a long-only ETF allocation. The reward function is the score the agent tries to maximize, such as return after turnover costs, volatility penalties, drawdown penalties, and defensive regime penalties.

PPO is a policy-gradient RL algorithm that updates a policy cautiously so each new policy does not move too far from the previous one. SAC and A2C are other RL algorithms, but they were skipped here to keep the overnight CPU run bounded. RL is different from supervised learning because it learns a sequence of decisions and their consequences rather than labels for independent examples.

RL might help portfolio allocation because it can directly optimize allocation behavior with turnover, drawdown, and cash decisions in the loop. It is extremely overfit-prone in finance because the historical environment is short, noisy, non-stationary, and easy to memorize. Here, RL is used only to test whether an agent can learn useful long-only ETF weights across a small research universe.

## Technical Setup

- Packages: gymnasium={'available': True, 'version': '1.1.1'}, stable_baselines3={'available': True, 'version': '2.7.1'}, torch={'available': True, 'version': '2.8.0'}
- RL universe: ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'TLT', 'IEF', 'HYG', 'LQD', 'GLD', 'SLV', 'DBC', 'USO', 'VNQ', 'XLK', 'XLF', 'XLE', 'XLV', 'SMH', 'BIL']
- Observation features: selected ETF trailing returns, momentum, realized volatility, drawdown, rank features, date-level regime/risk/breadth/fear features, MLX-5/6 confidence summaries, and previous portfolio weights.
- Action space: continuous Box action converted with softmax into long-only weights summing to 1.
- Reward functions: `return_only, turnover_penalized, risk_aware, defensive_regime_aware`
- Algorithm used: PPO
- Algorithms skipped: SAC and A2C for bounded CPU runtime.
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Transaction cost: 10 bps per unit turnover.
- Leakage controls: observations at date `t` use known-at-date features only; action at `t` earns next-week return; target/forward columns are excluded.

## Results

- Runs completed: 12
- Runs skipped: 2
- Best validation policy: `ppo__return_only__seed2__softmax_long_only` with validation Sharpe 0.652
- Selected policy holdout Sharpe: 0.674
- Best holdout policy: `ppo__turnover_penalized__seed1__softmax_long_only` with holdout Sharpe 0.703

| strategy_name | reward_variant | seed | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_exposure | average_risky_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ppo__turnover_penalized__seed1__softmax_long_only | turnover_penalized | 1 | 10.34% | 14.71% | 0.703 | -29.66% | 0.349 | -4.95% | 8.32% | 0.43% | 6.21% | 80.18% |
| ppo__defensive_regime_aware__seed1__softmax_long_only | defensive_regime_aware | 1 | 10.24% | 14.63% | 0.700 | -28.09% | 0.365 | -4.87% | 8.23% | 0.43% | 6.06% | 79.39% |
| ppo__risk_aware__seed1__softmax_long_only | risk_aware | 1 | 10.24% | 14.65% | 0.699 | -28.33% | 0.362 | -4.88% | 8.08% | 0.42% | 5.96% | 79.27% |
| ppo__return_only__seed1__softmax_long_only | return_only | 1 | 10.04% | 14.65% | 0.685 | -29.51% | 0.340 | -4.94% | 7.91% | 0.41% | 6.30% | 79.93% |
| ppo__return_only__seed2__softmax_long_only | return_only | 2 | 9.90% | 14.69% | 0.674 | -29.04% | 0.341 | -4.89% | 8.40% | 0.44% | 5.81% | 79.61% |
| ppo__turnover_penalized__seed2__softmax_long_only | turnover_penalized | 2 | 9.81% | 14.69% | 0.668 | -28.99% | 0.338 | -4.89% | 8.88% | 0.46% | 5.86% | 79.58% |
| ppo__risk_aware__seed0__softmax_long_only | risk_aware | 0 | 9.69% | 14.79% | 0.655 | -29.12% | 0.333 | -4.97% | 7.59% | 0.39% | 5.13% | 79.70% |
| ppo__turnover_penalized__seed0__softmax_long_only | turnover_penalized | 0 | 9.55% | 14.90% | 0.641 | -29.47% | 0.324 | -4.99% | 6.90% | 0.36% | 4.95% | 78.70% |
| ppo__defensive_regime_aware__seed0__softmax_long_only | defensive_regime_aware | 0 | 9.53% | 14.96% | 0.637 | -29.91% | 0.319 | -5.03% | 7.48% | 0.39% | 5.15% | 79.79% |
| ppo__return_only__seed0__softmax_long_only | return_only | 0 | 9.42% | 15.00% | 0.628 | -29.88% | 0.315 | -5.02% | 7.20% | 0.37% | 5.12% | 78.61% |
| ppo__defensive_regime_aware__seed2__softmax_long_only | defensive_regime_aware | 2 | 9.17% | 14.71% | 0.624 | -29.75% | 0.308 | -4.92% | 9.18% | 0.48% | 5.53% | 79.38% |
| ppo__risk_aware__seed2__softmax_long_only | risk_aware | 2 | 9.19% | 14.76% | 0.623 | -29.95% | 0.307 | -4.94% | 9.51% | 0.49% | 5.67% | 79.33% |

## Benchmark Comparison

| comparison_label | category | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_exposure | average_risky_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only | n/a | n/a | 1.276 | -14.56% | n/a | -4.17% | n/a | n/a | n/a | n/a |
| phase4b | benchmark | 9.64% | 9.01% | 1.070 | -12.44% | 0.775 | -2.72% | n/a | 0.00% | 0.00% | n/a |
| phase7 | benchmark | 9.57% | 9.47% | 1.011 | -13.83% | 0.692 | -2.92% | n/a | 0.00% | 0.00% | n/a |
| phase6 | benchmark | 9.57% | 9.47% | 1.010 | -13.77% | 0.695 | -2.92% | n/a | 0.00% | 0.00% | n/a |
| mlx6_transformer | benchmark | 11.16% | 11.30% | 0.987 | -13.13% | 0.850 | -3.29% | n/a | 0.00% | 0.00% | n/a |
| mlx7_meta_label | benchmark | 8.64% | 8.94% | 0.966 | -13.88% | 0.622 | -2.74% | n/a | 0.00% | 0.00% | n/a |
| mlx5_sequence | benchmark | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | n/a | 0.00% | 0.00% | n/a |
| official_shadow | benchmark | 8.04% | 8.53% | 0.943 | -13.67% | 0.588 | -2.71% | n/a | 0.00% | 0.00% | n/a |
| production | benchmark | 8.07% | 8.60% | 0.938 | -13.98% | 0.577 | -2.73% | n/a | 0.00% | 0.00% | n/a |
| simple_momentum | benchmark | 22.21% | 25.57% | 0.869 | -43.50% | 0.511 | -7.83% | n/a | 0.00% | 0.00% | n/a |
| ppo__turnover_penalized__seed1__softmax_long_only | rl_policy | 10.34% | 14.71% | 0.703 | -29.66% | 0.349 | -4.95% | 8.32% | 0.43% | 6.21% | 80.18% |
| ppo__defensive_regime_aware__seed1__softmax_long_only | rl_policy | 10.24% | 14.63% | 0.700 | -28.09% | 0.365 | -4.87% | 8.23% | 0.43% | 6.06% | 79.39% |
| ppo__risk_aware__seed1__softmax_long_only | rl_policy | 10.24% | 14.65% | 0.699 | -28.33% | 0.362 | -4.88% | 8.08% | 0.42% | 5.96% | 79.27% |
| ppo__return_only__seed1__softmax_long_only | rl_policy | 10.04% | 14.65% | 0.685 | -29.51% | 0.340 | -4.94% | 7.91% | 0.41% | 6.30% | 79.93% |
| SPY | benchmark | 13.24% | 19.37% | 0.683 | -33.63% | 0.394 | -6.31% | n/a | 0.00% | 0.00% | n/a |
| 60_40 | benchmark | 8.19% | 12.05% | 0.680 | -21.88% | 0.375 | -3.85% | n/a | 0.00% | 0.00% | n/a |
| ppo__return_only__seed2__softmax_long_only | rl_policy | 9.90% | 14.69% | 0.674 | -29.04% | 0.341 | -4.89% | 8.40% | 0.44% | 5.81% | 79.61% |
| ppo__turnover_penalized__seed2__softmax_long_only | rl_policy | 9.81% | 14.69% | 0.668 | -28.99% | 0.338 | -4.89% | 8.88% | 0.46% | 5.86% | 79.58% |
| ppo__risk_aware__seed0__softmax_long_only | rl_policy | 9.69% | 14.79% | 0.655 | -29.12% | 0.333 | -4.97% | 7.59% | 0.39% | 5.13% | 79.70% |
| ppo__turnover_penalized__seed0__softmax_long_only | rl_policy | 9.55% | 14.90% | 0.641 | -29.47% | 0.324 | -4.99% | 6.90% | 0.36% | 4.95% | 78.70% |
| ppo__defensive_regime_aware__seed0__softmax_long_only | rl_policy | 9.53% | 14.96% | 0.637 | -29.91% | 0.319 | -5.03% | 7.48% | 0.39% | 5.15% | 79.79% |
| ppo__return_only__seed0__softmax_long_only | rl_policy | 9.42% | 15.00% | 0.628 | -29.88% | 0.315 | -5.02% | 7.20% | 0.37% | 5.12% | 78.61% |
| ppo__defensive_regime_aware__seed2__softmax_long_only | rl_policy | 9.17% | 14.71% | 0.624 | -29.75% | 0.308 | -4.92% | 9.18% | 0.48% | 5.53% | 79.38% |
| ppo__risk_aware__seed2__softmax_long_only | rl_policy | 9.19% | 14.76% | 0.623 | -29.95% | 0.307 | -4.94% | 9.51% | 0.49% | 5.67% | 79.33% |

## State-By-State Results

| market_state | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_bil_exposure | average_risky_exposure | weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unknown | 94.51% | 2.18% | 43.429 | 0.00% | 0.98% | 6.50% | 82.10% | 3 |
| recovery_fragile | 35.07% | 9.73% | 3.603 | -2.92% | -1.95% | 7.51% | 81.13% | 14 |
| neutral_mixed | 24.01% | 10.95% | 2.192 | -6.36% | -2.80% | 6.41% | 80.63% | 121 |
| calm_trend | 4.71% | 11.04% | 0.426 | -11.23% | -3.43% | 6.75% | 81.30% | 101 |
| recovery_confirmed | -0.13% | 13.09% | -0.010 | -5.74% | -3.73% | 7.94% | 80.86% | 21 |
| stressed_panic | -5.86% | 23.40% | -0.251 | -18.61% | -8.99% | 4.33% | 77.36% | 71 |

## Exposure Audit

| audit_type | item | category | average_weight | max_weight | holding_frequency |
| --- | --- | --- | --- | --- | --- |
| category | US sectors | US sectors | 25.94% | 28.75% | 100.00% |
| summary | average_top3_weight |  | 22.53% | 28.25% | n/a |
| category | Commodities | Commodities | 20.65% | 23.47% | 100.00% |
| summary | average_safe_asset_weight |  | 19.82% | 25.87% | n/a |
| summary | average_SPY_QQQ_SMH_weight |  | 17.15% | 20.63% | n/a |
| category | US broad equity | US broad equity | 15.78% | 18.10% | 100.00% |
| category | Bonds | Bonds | 15.33% | 21.50% | 100.00% |
| category | International equity | International equity | 9.05% | 12.87% | 100.00% |
| category | Credit | Credit | 8.64% | 15.01% | 100.00% |
| ticker | SMH | US sectors | 6.47% | 9.35% | 100.00% |
| ticker | USO | Commodities | 6.45% | 9.74% | 100.00% |
| ticker | BIL | Bonds | 6.21% | 8.70% | 100.00% |
| summary | average_BIL_weight |  | 6.21% | 8.70% | n/a |
| ticker | SPY | US broad equity | 5.83% | 7.80% | 100.00% |
| ticker | XLK | US sectors | 5.30% | 8.60% | 100.00% |
| ticker | IEF | Bonds | 5.24% | 8.61% | 100.00% |
| ticker | GLD | Commodities | 5.16% | 7.48% | 100.00% |
| ticker | XLV | US sectors | 5.15% | 8.11% | 100.00% |
| ticker | IWM | US broad equity | 5.09% | 7.43% | 100.00% |
| ticker | QQQ | US broad equity | 4.86% | 8.97% | 100.00% |
| ticker | EEM | International equity | 4.63% | 6.76% | 100.00% |
| ticker | VNQ | Real estate | 4.62% | 6.54% | 100.00% |
| category | Real estate | Real estate | 4.62% | 6.54% | 100.00% |
| ticker | XLE | US sectors | 4.61% | 7.37% | 100.00% |
| ticker | SLV | Commodities | 4.58% | 10.32% | 100.00% |
| ticker | LQD | Credit | 4.49% | 7.65% | 100.00% |
| ticker | DBC | Commodities | 4.46% | 7.67% | 100.00% |
| ticker | EFA | International equity | 4.42% | 6.67% | 100.00% |
| ticker | XLF | US sectors | 4.42% | 7.54% | 100.00% |
| ticker | HYG | Credit | 4.15% | 8.04% | 100.00% |

## Interpretation

- Did RL beat production? False
- Did RL beat Phase 4B? False
- Did RL beat MLX-5C? False
- Did risk-aware reward reduce drawdown? True
- Final recommendation: **NEEDS MORE TRAINING / BETTER ENVIRONMENT**

RL should remain research-only unless it survives richer walk-forward testing and a cleaner environment. A high holdout Sharpe alone is not enough because RL can learn brittle historical exposure patterns.

## Skipped Runs

- SAC: skipped to keep bounded overnight CPU run focused on PPO
- A2C: skipped to keep bounded overnight CPU run focused on PPO

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- No RL model is promoted automatically.
