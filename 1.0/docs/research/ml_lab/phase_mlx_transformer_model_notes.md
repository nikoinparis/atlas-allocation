# Phase MLX Transformer Model Notes

## Research-Only Warning

Phase MLX-6 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

A Transformer is a neural network architecture that reads a sequence and uses attention to decide which past time steps matter most. Attention means the model can learn relationships between different weeks in the lookback window instead of only reading the sequence from left to right. Positional encoding gives the model a sense of order, so week 1 and week 26 are not treated as interchangeable.

Transformers might help ETF time-series ranking because they can look across the whole recent path for trend, volatility, recovery, or regime-transition patterns. They may overfit financial data because the signal-to-noise ratio is low, markets change, and attention layers can learn accidental historical quirks. In this project, the Transformer scores each ETF-date row, ETFs are ranked weekly by score, and defensive overlays such as BIL fallback, regime gates, and volatility targeting reduce exposure when risk conditions look unfavorable.

## Technical Setup

- Torch available: True / version: 2.8.0
- Device used: `cpu`
- Sequence lengths tested: [13, 26]
- Seeds tested: [0]
- Features: numeric MLX-2 features only; `Date` and `ticker` are identifiers.
- Target: `top_quintile_forward_4w`
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Architecture: input projection to d_model=32, learned positional embeddings, 1-layer TransformerEncoder, 4 attention heads, feedforward size 64, dropout 0.20, final-step pooling, one-logit classifier.
- Loss: `BCEWithLogitsLoss` with train-set positive-class weighting.
- Early stopping: validation loss only.
- Preprocessing: train-only median fill and train-only standardization.
- Leakage controls: targets are excluded from features, forward returns are targets only, and validation/holdout are never used for preprocessing statistics or model fitting.

## Models Run

- `transformer_encoder_top_quintile_forward_4w_seq13_seed0`: seq=13, seed=0, d_model=32, heads=4, layers=1
- `transformer_encoder_top_quintile_forward_4w_seq26_seed0`: seq=26, seed=0, d_model=32, heads=4, layers=1

## Models Skipped

- transformer_encoder_top_quintile_forward_4w_seq52_seed0: skipped 52-week Transformer for bounded CPU runtime
- transformer_encoder_top_quintile_forward_4w_seq26_seed1: skipped additional Transformer seed for bounded CPU runtime
- transformer_encoder_top_quintile_forward_4w_seq26_seed2: skipped additional Transformer seed for bounded CPU runtime
- transformer_encoder_beats_SPY_4w_seq26_seed0: skipped secondary beats_SPY target for bounded CPU runtime
- transformer_walk_forward_retraining: deferred full Transformer walk-forward retraining; use MLX-5C walk-forward sequence results for robustness context
- transformer_equal_weight_portfolios: skipped optional equal-weight portfolios to keep MLX-6 bounded

## Holdout Results

| strategy_name | sequence_length | seed | top_n | wrapper | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__bil_fallback_original | 26 | 0 | 15 | bil_fallback_original | 11.16% | 11.30% | 0.987 | -13.13% | 0.850 | -3.29% | 0.3056132883761278 | 1.59% | 25.15% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__regime_gate_original | 26 | 0 | 15 | regime_gate_original | 8.92% | 10.41% | 0.857 | -13.26% | 0.673 | -3.20% | 0.29409855334443563 | 1.53% | 32.67% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top10__inverse_vol__bil_fallback_original | 13 | 0 | 10 | bil_fallback_original | 10.31% | 13.29% | 0.775 | -19.89% | 0.518 | -4.25% | 0.34997533846458356 | 1.82% | 25.15% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__raw_ml | 26 | 0 | 15 | raw_ml | 13.76% | 18.18% | 0.757 | -30.05% | 0.458 | -5.33% | 0.29460784978678484 | 1.53% | 0.00% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top15__inverse_vol__bil_fallback_original | 13 | 0 | 15 | bil_fallback_original | 9.43% | 12.47% | 0.756 | -19.04% | 0.495 | -3.87% | 0.3130323282336813 | 1.63% | 25.15% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top10__inverse_vol__bil_fallback_original | 26 | 0 | 10 | bil_fallback_original | 8.90% | 12.12% | 0.734 | -15.51% | 0.574 | -3.58% | 0.3289335387389354 | 1.71% | 25.15% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__vol_target_10pct | 26 | 0 | 15 | vol_target_10pct | 7.85% | 11.62% | 0.675 | -17.76% | 0.442 | -3.76% | 0.25704651444606497 | 1.34% | 29.58% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top10__inverse_vol__regime_gate_original | 13 | 0 | 10 | regime_gate_original | 8.08% | 12.26% | 0.659 | -19.92% | 0.405 | -4.01% | 0.3332715138450582 | 1.73% | 32.67% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top15__inverse_vol__regime_gate_original | 13 | 0 | 15 | regime_gate_original | 7.50% | 11.53% | 0.651 | -19.08% | 0.393 | -3.72% | 0.3010902171337392 | 1.57% | 32.67% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top10__inverse_vol__regime_gate_original | 26 | 0 | 10 | regime_gate_original | 6.81% | 11.07% | 0.615 | -15.26% | 0.446 | -3.42% | 0.3137738391261654 | 1.63% | 32.67% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top10__inverse_vol__vol_target_10pct | 13 | 0 | 10 | vol_target_10pct | 6.76% | 11.71% | 0.577 | -20.10% | 0.336 | -4.08% | 0.2789514605966299 | 1.45% | 37.65% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top15__inverse_vol__raw_ml | 13 | 0 | 15 | raw_ml | 11.03% | 20.16% | 0.547 | -38.57% | 0.286 | -6.28% | 0.3215289128837204 | 1.67% | 0.00% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top10__inverse_vol__raw_ml | 13 | 0 | 10 | raw_ml | 11.78% | 21.67% | 0.544 | -40.65% | 0.290 | -7.00% | 0.36069044524010613 | 1.88% | 0.00% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top10__inverse_vol__vol_target_10pct | 26 | 0 | 10 | vol_target_10pct | 5.42% | 11.43% | 0.474 | -19.04% | 0.285 | -3.82% | 0.25723348085228787 | 1.34% | 34.93% |
| transformer_encoder_top_quintile_forward_4w_seq26_seed0__top10__inverse_vol__raw_ml | 26 | 0 | 10 | raw_ml | 8.97% | 19.11% | 0.470 | -31.96% | 0.281 | -5.83% | 0.3180524902900954 | 1.65% | 0.00% |
| transformer_encoder_top_quintile_forward_4w_seq13_seed0__top15__inverse_vol__vol_target_10pct | 13 | 0 | 15 | vol_target_10pct | 5.39% | 11.74% | 0.459 | -20.19% | 0.267 | -4.01% | 0.2637408637384611 | 1.37% | 33.65% |

## Best Results

- Best raw Transformer: `transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__raw_ml` with Sharpe 0.757.
- Best overlay Transformer: `transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__bil_fallback_original` with Sharpe 0.987.
- Best holdout annual return: `transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__raw_ml` at 13.76%.
- Best drawdown: `transformer_encoder_top_quintile_forward_4w_seq26_seed0__top15__inverse_vol__bil_fallback_original` with max drawdown -13.13%.

## Comparison Table

| comparison_label | category | annual_return | annual_volatility | sharpe | max_drawdown | calmar | cvar_5 | average_turnover | annual_cost_drag | average_bil_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MLX-5C bil-fallback mean | prior_mlx5c | n/a | n/a | 1.276 | -14.56% | n/a | -4.17% | n/a | n/a | n/a |
| Phase 4B best | phase4b | 9.64% | 9.01% | 1.070 | -12.44% | 0.775 | -2.72% | 0.0843634101391389 | 0.44% | 24.15% |
| Phase 7 stretch | phase7 | 9.57% | 9.47% | 1.011 | -13.83% | 0.692 | -2.92% | 0.0786404938202689 | 0.41% | 19.78% |
| Phase 6 best | phase6 | 9.57% | 9.47% | 1.010 | -13.77% | 0.695 | -2.92% | 0.0787856938656835 | 0.41% | 19.78% |
| Best overlay Transformer | transformer | 11.16% | 11.30% | 0.987 | -13.13% | 0.850 | -3.29% | 0.3056132883761278 | 1.59% | 25.15% |
| Best defensive-overlay sequence model | prior_mlx | 11.66% | 12.08% | 0.964 | -11.34% | 1.028 | -3.63% | 0.3417441582211503 | 1.78% | 25.15% |
| Official shadow | official_shadow | 8.04% | 8.53% | 0.943 | -13.67% | 0.588 | -2.71% | 0.0564538231817843 | 0.29% | 25.65% |
| Current production | current_production | 8.07% | 8.60% | 0.938 | -13.98% | 0.577 | -2.73% | 0.055975228867502 | 0.29% | 25.53% |
| MLX-4 best MLP | prior_mlx | 18.03% | 19.89% | 0.907 | -29.40% | 0.613 | -6.09% | 0.437319694390663 | 2.27% | n/a |
| Simple momentum top10 | baseline_momentum | 15.11% | 17.69% | 0.854 | -27.84% | 0.543 | -5.61% | 0.4164317346459591 | 2.17% | 2.56% |
| MLX-3 best tabular ML | prior_mlx | 16.85% | 20.78% | 0.811 | -37.55% | 0.449 | -6.52% | 0.6193395087666357 | 3.22% | n/a |
| SPY | baseline | 15.44% | 19.25% | 0.802 | -31.83% | 0.485 | -6.06% | 0.0030120481927710845 | 0.02% | 0.00% |
| 60/40 | baseline | 9.49% | 11.99% | 0.792 | -20.76% | 0.457 | -3.71% | 0.0030120481927710845 | 0.02% | 0.00% |
| Best raw Transformer | transformer | 13.76% | 18.18% | 0.757 | -30.05% | 0.458 | -5.33% | 0.29460784978678484 | 1.53% | 0.00% |
| Simple momentum top15 | baseline_momentum | 11.39% | 16.29% | 0.700 | -26.57% | 0.429 | -5.39% | 0.39953057281571314 | 2.08% | 6.09% |

## Interpretation

The Transformer should be judged against the simpler MLX-5/5C sequence models, not just against SPY or a single holdout period. If the Transformer does not clearly beat MLX-5C or Phase 4B, it should remain research-only or wait for ensemble testing rather than becoming an ML shadow. Defensive overlays are useful only if they improve Sharpe or reduce drawdown without making the model a disguised cash/BIL strategy.

Final recommendation: **NEEDS MULTI-SEED / WALK-FORWARD BEFORE JUDGMENT**

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- No Transformer model is promoted automatically.
