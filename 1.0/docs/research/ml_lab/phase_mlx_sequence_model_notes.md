# Phase MLX Sequence Model Notes

## Research-Only Warning

Phase MLX-5 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Sequence models are models that read ordered history rather than a single row. Here, each sample is the past 26 weekly feature observations for one ETF, and the model predicts whether that ETF will be a top-quintile forward performer.

An LSTM is a recurrent neural network designed to remember useful information across time while forgetting less useful information. A GRU is a simpler recurrent model with fewer gates, often faster and more compact. A Temporal CNN applies convolution filters across time windows, looking for local temporal patterns such as acceleration, reversal, or volatility bursts.

Time-window models might help financial prediction because ETF leadership can depend on paths: trend persistence, volatility compression, drawdown recovery, and regime transitions. They might overfit because financial samples are noisy, regimes change, the validation window is short, and many model/overlay choices create data-mining risk.

This project uses sequence models to rank ETFs weekly. The models are tested as offensive ETF selectors, not as replacements for the core production portfolio.

## Defensive Overlay Explanation

Raw ML can have attractive returns but high drawdown because it stays exposed when model confidence is wrong or when market-wide stress dominates cross-sectional signals. The core regime engine can act as a risk filter by reducing ML exposure in stressed states.

BIL fallback sends unused exposure to the Treasury-bill proxy. Volatility targeting scales the ML sleeve toward a 10% annualized volatility target. The drawdown kill switch cuts exposure after the ML sleeve itself enters a drawdown. These wrappers test whether ML is more credible as an offensive sleeve inside a defensive framework than as a standalone production replacement.

## Technical Setup

- Torch available: True / version: 2.8.0
- Device used: `cpu`
- Input sequence length: [26]
- Features: numeric MLX-2 features only; `Date` and `ticker` are identifiers.
- Main target: `top_quintile_forward_4w`
- Secondary target: `beats_SPY_4w`
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Architectures: small LSTM, GRU, Temporal CNN, and optional GRU for `beats_SPY_4w`.
- Loss: BCEWithLogitsLoss.
- Preprocessing: train-only median fill and train-only mean/std standardization.
- Leakage controls: no target-like `forward_*`, `beats_*`, or `top_quintile_*` input columns; validation and holdout do not fit preprocessing or model weights.

## Results

Models run:

- lstm_classifier_top_quintile_forward_4w_seq26
- gru_classifier_top_quintile_forward_4w_seq26
- temporal_cnn_classifier_top_quintile_forward_4w_seq26
- gru_classifier_beats_SPY_4w_seq26

Models skipped:

- None

- Best raw sequence model: temporal_cnn_classifier_top_quintile_forward_4w_seq26__top3__inverse_vol__raw_ml / Sharpe 0.844
- Best defensive-overlay sequence model: lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback / Sharpe 0.964
- Best holdout Sharpe: 0.964
- Best holdout annual return: 23.26%
- Best holdout max drawdown: -10.36%
- Comparison vs MLX-4 best: beats by Sharpe = True
- Comparison vs simple momentum: beats by Sharpe = True
- Comparison vs production: beats by Sharpe = True
- Comparison vs official shadow: beats by Sharpe = True
- Overlays improve drawdown vs raw: True
- Overlays improve Sharpe vs raw: True

## Holdout Comparison Table

| comparison_label | strategy_name | annual_return | sharpe | max_drawdown | calmar | cvar_5 |
| --- | --- | --- | --- | --- | --- | --- |
| Best raw sequence model | temporal_cnn_classifier_top_quintile_forward_4w_seq26__top3__inverse_vol__raw_ml | 0.233 | 0.844 | -0.294 | 0.790 | -0.078 |
| Best defensive-overlay sequence model | lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback | 0.117 | 0.964 | -0.113 | 1.028 | -0.036 |
| MLX-4 best MLP | mlx4_best_mlp | 0.180 | 0.907 | -0.294 | 0.613 | -0.061 |
| MLX-3 best tabular ML | mlx3_best_tabular_ml | 0.168 | 0.811 | -0.375 | 0.449 | -0.065 |
| Simple momentum baseline | baseline_top_momentum_momentum_12_1__top3__inverse_vol | 0.222 | 0.869 | -0.435 | 0.511 | -0.078 |
| SPY | baseline_spy_buy_hold | 0.154 | 0.802 | -0.318 | 0.485 | -0.061 |
| 60/40 | baseline_60_40_spy_ief_or_agg | 0.095 | 0.792 | -0.208 | 0.457 | -0.037 |
| Current production | current_production_improved_phase2b_regime_confidence_boost | 0.081 | 0.938 | -0.140 | 0.577 | -0.027 |
| Official shadow | official_shadow_improved_phase2b_combo_abc | 0.080 | 0.943 | -0.137 | 0.588 | -0.027 |
| Phase 4B best | project_improved_phase4b_sector_phase3_hybrid | 0.096 | 1.070 | -0.124 | 0.775 | -0.027 |
| Phase 6 best | project_improved_phase6_recovery_quality_rerisk | 0.096 | 1.010 | -0.138 | 0.695 | -0.029 |
| Phase 7 stretch/best | project_improved_phase7_expression_boost | 0.096 | 1.011 | -0.138 | 0.692 | -0.029 |

## Explicit Answers

1. Any sequence model beats current production on holdout Sharpe: True
2. Any sequence model beats official shadow on holdout Sharpe: True
3. Any sequence model beats production on annual return: True
4. Any sequence model beats production after considering max drawdown and CVaR: False
5. Defensive overlay makes ML more comparable to production risk: True
6. Standalone or offensive sleeve: research-only offensive sleeve candidate at most; not a production replacement.

## Interpretation

Sequence models test a richer time-history hypothesis than row-wise MLPs. The important question is not whether a single variant wins one holdout screen, but whether the result remains stable across stricter walk-forward tests and whether overlays reduce risk enough to resemble the core project. Anything promising remains ML shadow / research-only until it survives that process.

Warnings:

- Could not read project strategy /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_4_sector_breadth_rotation/phase4_sector_sleeve_returns.csv: "['gross_return', 'net_return'] not in index"
- Could not read project strategy /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_4b_refined_sector_rotation/phase4b_refined_sector_sleeve_returns.csv: "['gross_return', 'net_return'] not in index"
- Could not read project strategy /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ppp_latent_factor_discovery/ppp_panel_sleeve_returns.csv: "['gross_return', 'net_return'] not in index"
