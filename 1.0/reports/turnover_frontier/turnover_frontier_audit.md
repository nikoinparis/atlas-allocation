# Turnover Frontier Audit

Production pin: `improved_phase2b_regime_confidence_boost`. This is a research audit only; no production files or pins are promoted.

## Important Implementation Note

The production pin is HRP-based, so the notebook's optimizer `TURNOVER_PENALTY` constant is not directly binding for this strategy path. The audit therefore tests the effective turnover control: the sleeve reallocation speed/dynamic smoothing that governs how quickly the portfolio moves toward saved production target sleeves. The saved production gross risk/cash budget is preserved to isolate turnover smoothing rather than loosening the risk overlay.

## Headline Results

| variant | ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_turnover | cost_drag | avg_BIL_cash | avg_SPY | avg_offensive_exposure | holdout_ann_return | holdout_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| production_current | 6.89% | 7.79% | 0.884 | -13.98% | 0.493 | -2.62% | 5.62% | 0.31% | 28.39% | 7.08% | 55.22% | 12.43% | 1.620 |
| lower_penalty_50 | 5.81% | 7.92% | 0.734 | -15.66% | 0.371 | -2.75% | 5.36% | 0.29% | 28.67% | 7.09% | 55.10% | 11.65% | 1.506 |
| lower_penalty_75 | 5.91% | 7.87% | 0.751 | -15.24% | 0.388 | -2.72% | 5.51% | 0.30% | 28.54% | 7.08% | 55.15% | 11.63% | 1.509 |
| turnover_cap_2x | 5.88% | 7.89% | 0.745 | -15.38% | 0.382 | -2.73% | 5.46% | 0.30% | 28.58% | 7.08% | 55.14% | 11.63% | 1.508 |
| turnover_cap_4x | 6.01% | 7.83% | 0.768 | -14.82% | 0.406 | -2.70% | 5.70% | 0.31% | 28.46% | 7.07% | 55.16% | 11.61% | 1.513 |
| no_penalty_no_cap | 6.01% | 7.83% | 0.768 | -14.82% | 0.406 | -2.70% | 5.70% | 0.31% | 28.46% | 7.07% | 55.16% | 11.61% | 1.513 |
| no_penalty_2x_costs | 5.70% | 7.83% | 0.728 | -14.87% | 0.383 | -2.71% | 5.70% | 0.63% | 28.46% | 7.07% | 55.16% | 11.26% | 1.466 |
| no_penalty_3x_costs | 5.39% | 7.83% | 0.688 | -14.91% | 0.361 | -2.71% | 5.70% | 0.94% | 28.46% | 7.07% | 55.16% | 10.90% | 1.420 |

## Frontier

| variant | extra_turnover | delta_ann_return_vs_production | return_gained_per_extra_turnover | delta_sharpe_vs_production | sharpe_gained_per_extra_turnover | cost_sensitivity_2x_ann_return_delta | cost_sensitivity_3x_ann_return_delta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lower_penalty_50 | -0.27% | -1.08% | 4.054 | -0.150 | 56.398 | -0.29% | -0.59% |
| turnover_cap_2x | -0.16% | -1.02% | 6.170 | -0.139 | 84.585 | -0.30% | -0.60% |
| lower_penalty_75 | -0.11% | -0.98% | 8.756 | -0.134 | 119.097 | -0.30% | -0.60% |
| production_current | 0.00% | 0.00% | n/a | 0.000 | n/a | -0.31% | -0.62% |
| turnover_cap_4x | 0.07% | -0.88% | -12.136 | -0.117 | -160.979 | n/a | n/a |
| no_penalty_no_cap | 0.07% | -0.88% | -12.136 | -0.117 | -160.979 | -0.31% | -0.62% |

## State-By-State

| variant | market_state | n_weeks | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | avg_BIL_cash | avg_SPY | avg_offensive_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| production_current | calm_trend | 295 | 3.56% | 0.384 | -16.47% | -3.12% | 6.22% | 6.85% | 9.62% | 78.03% |
| production_current | neutral_mixed | 493 | 11.04% | 1.462 | -8.97% | -2.39% | 5.17% | 28.32% | 7.76% | 54.67% |
| production_current | recovery_confirmed | 44 | 2.61% | 0.385 | -4.97% | -2.03% | 5.77% | 12.57% | 5.96% | 58.18% |
| production_current | recovery_fragile | 49 | 6.97% | 1.317 | -3.09% | -1.48% | 9.52% | 21.82% | 6.23% | 56.20% |
| production_current | stressed_panic | 229 | 3.37% | 0.497 | -12.08% | -2.07% | 4.96% | 60.74% | 2.75% | 26.21% |
| lower_penalty_50 | calm_trend | 295 | 2.51% | 0.268 | -18.19% | -3.24% | 6.11% | 7.28% | 9.55% | 77.69% |
| lower_penalty_50 | neutral_mixed | 493 | 10.06% | 1.327 | -9.26% | -2.50% | 4.94% | 29.31% | 7.69% | 54.09% |
| lower_penalty_50 | recovery_confirmed | 44 | 1.86% | 0.279 | -5.21% | -2.04% | 5.51% | 15.64% | 5.75% | 56.04% |
| lower_penalty_50 | recovery_fragile | 49 | 5.93% | 1.172 | -3.24% | -1.46% | 8.16% | 25.53% | 6.06% | 53.67% |
| lower_penalty_50 | stressed_panic | 229 | 2.00% | 0.273 | -14.10% | -2.39% | 4.65% | 58.02% | 3.08% | 28.28% |
| lower_penalty_75 | calm_trend | 295 | 2.55% | 0.273 | -18.08% | -3.23% | 6.17% | 7.01% | 9.59% | 77.91% |
| lower_penalty_75 | neutral_mixed | 493 | 10.12% | 1.335 | -9.23% | -2.48% | 5.12% | 28.80% | 7.70% | 54.37% |
| lower_penalty_75 | recovery_confirmed | 44 | 1.89% | 0.279 | -5.29% | -2.07% | 5.55% | 13.71% | 5.88% | 57.37% |
| lower_penalty_75 | recovery_fragile | 49 | 6.19% | 1.190 | -3.24% | -1.49% | 8.87% | 23.34% | 6.18% | 55.23% |
| lower_penalty_75 | stressed_panic | 229 | 2.21% | 0.315 | -13.29% | -2.25% | 4.78% | 59.69% | 2.93% | 27.05% |
| turnover_cap_2x | calm_trend | 295 | 2.54% | 0.272 | -18.12% | -3.23% | 6.15% | 7.08% | 9.58% | 77.85% |
| turnover_cap_2x | neutral_mixed | 493 | 10.10% | 1.333 | -9.24% | -2.48% | 5.06% | 28.96% | 7.70% | 54.29% |
| turnover_cap_2x | recovery_confirmed | 44 | 1.88% | 0.278 | -5.27% | -2.06% | 5.53% | 14.24% | 5.84% | 56.99% |
| turnover_cap_2x | recovery_fragile | 49 | 6.09% | 1.182 | -3.24% | -1.48% | 8.62% | 24.02% | 6.14% | 54.74% |
| turnover_cap_2x | stressed_panic | 229 | 2.13% | 0.300 | -13.56% | -2.30% | 4.74% | 59.18% | 2.98% | 27.43% |
| turnover_cap_4x | calm_trend | 295 | 2.60% | 0.278 | -17.97% | -3.22% | 6.24% | 6.84% | 9.62% | 78.06% |
| turnover_cap_4x | neutral_mixed | 493 | 10.14% | 1.339 | -9.18% | -2.47% | 5.31% | 28.42% | 7.70% | 54.56% |
| turnover_cap_4x | recovery_confirmed | 44 | 1.98% | 0.291 | -5.32% | -2.07% | 5.77% | 12.59% | 5.95% | 58.22% |
| turnover_cap_4x | recovery_fragile | 49 | 6.49% | 1.221 | -3.23% | -1.51% | 9.66% | 21.55% | 6.28% | 56.52% |
| turnover_cap_4x | stressed_panic | 229 | 2.50% | 0.368 | -12.54% | -2.14% | 4.96% | 60.95% | 2.80% | 26.10% |
| no_penalty_no_cap | calm_trend | 295 | 2.60% | 0.278 | -17.97% | -3.22% | 6.24% | 6.84% | 9.62% | 78.06% |
| no_penalty_no_cap | neutral_mixed | 493 | 10.14% | 1.339 | -9.18% | -2.47% | 5.31% | 28.42% | 7.70% | 54.56% |
| no_penalty_no_cap | recovery_confirmed | 44 | 1.98% | 0.291 | -5.32% | -2.07% | 5.77% | 12.59% | 5.95% | 58.22% |
| no_penalty_no_cap | recovery_fragile | 49 | 6.49% | 1.221 | -3.23% | -1.51% | 9.66% | 21.55% | 6.28% | 56.52% |
| no_penalty_no_cap | stressed_panic | 229 | 2.50% | 0.368 | -12.54% | -2.14% | 4.96% | 60.95% | 2.80% | 26.10% |
| no_penalty_2x_costs | calm_trend | 295 | 2.27% | 0.243 | -18.46% | -3.23% | 6.24% | 6.84% | 9.62% | 78.06% |
| no_penalty_2x_costs | neutral_mixed | 493 | 9.84% | 1.299 | -9.32% | -2.47% | 5.31% | 28.42% | 7.70% | 54.56% |
| no_penalty_2x_costs | recovery_confirmed | 44 | 1.68% | 0.246 | -5.46% | -2.08% | 5.77% | 12.59% | 5.95% | 58.22% |
| no_penalty_2x_costs | recovery_fragile | 49 | 5.96% | 1.125 | -3.39% | -1.53% | 9.66% | 21.55% | 6.28% | 56.52% |
| no_penalty_2x_costs | stressed_panic | 229 | 2.24% | 0.329 | -12.64% | -2.14% | 4.96% | 60.95% | 2.80% | 26.10% |
| no_penalty_3x_costs | calm_trend | 295 | 1.94% | 0.208 | -18.94% | -3.24% | 6.24% | 6.84% | 9.62% | 78.06% |
| no_penalty_3x_costs | neutral_mixed | 493 | 9.54% | 1.260 | -9.46% | -2.48% | 5.31% | 28.42% | 7.70% | 54.56% |
| no_penalty_3x_costs | recovery_confirmed | 44 | 1.37% | 0.202 | -5.61% | -2.09% | 5.77% | 12.59% | 5.95% | 58.22% |
| no_penalty_3x_costs | recovery_fragile | 49 | 5.43% | 1.028 | -3.54% | -1.54% | 9.66% | 21.55% | 6.28% | 56.52% |
| no_penalty_3x_costs | stressed_panic | 229 | 1.97% | 0.290 | -12.80% | -2.15% | 4.96% | 60.95% | 2.80% | 26.10% |

## Cost Sensitivity

| base_variant | ann_return_1x_cost | ann_return_2x_cost | ann_return_3x_cost | delta_2x_vs_1x | delta_3x_vs_1x | sharpe_1x_cost | sharpe_2x_cost | sharpe_3x_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| production_current | 6.89% | 6.58% | 6.27% | -0.003 | -0.006 | 0.884 | 0.845 | 0.805 |
| lower_penalty_50 | 5.81% | 5.52% | 5.22% | -0.003 | -0.006 | 0.734 | 0.697 | 0.660 |
| lower_penalty_75 | 5.91% | 5.61% | 5.31% | -0.003 | -0.006 | 0.751 | 0.712 | 0.674 |
| turnover_cap_2x | 5.88% | 5.58% | 5.28% | -0.003 | -0.006 | 0.745 | 0.707 | 0.669 |
| no_penalty_no_cap | 6.01% | 5.70% | 5.39% | -0.003 | -0.006 | 0.768 | 0.728 | 0.688 |

## Audit Readout

- Best higher-turnover candidate: No accepted candidate. Best diagnostic higher-turnover row: `turnover_cap_4x` (4x higher turnover cap if caps exist).
- Removing turnover controls hurt full-sample net return and did not survive holdout.
- Transaction-cost stress survival for the no-penalty/no-cap path: no.
- Point where extra turnover stops helping: No positive marginal return/turnover point was found.
- Current turnover control verdict: too strict only if a higher-turnover row improves net return, risk, cost stress, and holdout together. The acceptance filters above are intentionally conservative.
