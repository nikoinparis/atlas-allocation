# Phase MLX Cross-Asset Attention Ranker Notes

## Research-Only Warning

Phase MLX cross-asset attention is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Cross-sectional prediction means ranking assets against each other at the same date. Instead of asking whether one ETF will go up in isolation, the model asks which ETFs look better than the rest of the ETF universe this week.

Cross-asset attention is a Transformer-style method where every ETF is treated as a token. Attention lets SPY, QQQ, TLT, GLD, sectors, international ETFs, commodities, and BIL interact at the same date. This differs from MLX-6, where the Transformer mainly processed one ETF's historical sequence. Here, the attention axis is the cross-section of ETFs at date `t`.

ETF allocation is naturally a ranking problem because the portfolio does not need perfect return forecasts for every ETF; it needs a useful ordering for top-N selection, sizing, and defensive overlay. Ranking jointly may help because relative relationships matter: bonds versus equities, growth versus value, commodities versus inflation-sensitive assets, and BIL versus risky assets.

This can overfit because ETF relationships change over time, the cross-section is small, and a Transformer can learn period-specific risk-on or tech momentum patterns. This sprint relates to research directions such as MASTER: Market-Guided Stock Transformer, self-attention for cross-sectional return forecasting, and learning-to-rank for asset selection.

## Technical Setup

- Torch availability: {'available': True, 'version': '2.8.0', 'device': 'cpu', 'cuda_available': False, 'mps_available': True}
- Input tensor shape: `[1375, 97, 74]` as `[dates, ETFs, features]`
- ETF universe size: 97
- Features used: 74 total, including an availability mask
- Target: `top_quintile_forward_4w`
- Architecture: {'input_projection': 'Linear(74 -> 32)', 'etf_embedding': True, 'attention_axis': 'asset/cross-section dimension at one date', 'd_model': 32, 'nhead': 4, 'num_layers': 1, 'dim_feedforward': 64, 'dropout': 0.2, 'output': 'one logit score per ETF per date'}
- Loss function: `BCEWithLogitsLoss` for `top_quintile_forward_4w`
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill and train-only standardization
- Leakage controls: no target-like input columns; action at date `t` uses scores known at date `t` and earns next-week returns
- Skipped variants: [{'variant': 'pairwise_ranking_loss', 'reason': 'deferred in first CPU-bounded version; BCE top-quintile loss used first'}, {'variant': 'listwise_ranking_loss', 'reason': 'deferred in first CPU-bounded version; explicit date-grouped ranking loss is next upgrade'}, {'variant': 'seed_2', 'reason': 'skipped to keep first cross-asset attention run bounded on CPU'}, {'variant': 'attention_weight_extraction', 'reason': 'PyTorch TransformerEncoder does not expose attention maps directly in this simple implementation'}, {'variant': 'full_walk_forward_retraining', 'reason': 'deferred; selected predictions are evaluated by window without retraining per fold'}]

## Results

- Models run: ['cross_asset_attention_ranker_seed0', 'cross_asset_attention_ranker_seed1']
- Best validation model: `cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first` with validation Sharpe 0.289
- Validation-selected holdout Sharpe: 0.361
- Validation-selected holdout annual return: 3.78%
- Validation-selected max drawdown: -15.46%
- Validation-selected CVaR 5%: -3.47%
- Best holdout model: `cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original` with holdout Sharpe 0.448

### Top Holdout Strategies

| strategy_name | seed | top_n | weighting | wrapper | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_turnover | average_bil_exposure | rank_ic | top_quintile_hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | 1 | 10 | inverse_vol | bil_fallback_original | 5.68% | 12.66% | 0.448 | -21.49% | -4.24% | 45.25% | 25.45% | 0.009 | 0.336 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__defensive_first | 1 | 10 | inverse_vol | defensive_first | 4.49% | 10.17% | 0.441 | -16.29% | -3.44% | 37.50% | 41.02% | 0.009 | 0.336 |
| cross_asset_attention_ranker_seed1__top15__inverse_vol__bil_fallback_original | 1 | 15 | inverse_vol | bil_fallback_original | 5.06% | 11.71% | 0.432 | -19.41% | -3.82% | 39.19% | 25.45% | 0.009 | 0.325 |
| cross_asset_attention_ranker_seed1__top15__inverse_vol__defensive_first | 1 | 15 | inverse_vol | defensive_first | 3.88% | 9.45% | 0.411 | -14.48% | -3.17% | 33.01% | 41.02% | 0.009 | 0.325 |
| cross_asset_attention_ranker_seed1__top15__equal_weight__bil_fallback_original | 1 | 15 | equal_weight | bil_fallback_original | 4.51% | 11.92% | 0.378 | -19.28% | -3.88% | 32.96% | 25.45% | 0.009 | 0.325 |
| cross_asset_attention_ranker_seed1__top15__equal_weight__defensive_first | 1 | 15 | equal_weight | defensive_first | 3.54% | 9.62% | 0.368 | -14.33% | -3.22% | 28.31% | 41.02% | 0.009 | 0.325 |
| cross_asset_attention_ranker_seed0__top15__inverse_vol__bil_fallback_original | 0 | 15 | inverse_vol | bil_fallback_original | 4.40% | 12.05% | 0.365 | -21.16% | -3.97% | 39.83% | 25.45% | 0.011 | 0.317 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__regime_gate_original | 1 | 10 | inverse_vol | regime_gate_original | 4.24% | 11.64% | 0.364 | -19.43% | -4.00% | 42.05% | 32.88% | 0.009 | 0.336 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | 1 | 10 | equal_weight | defensive_first | 3.78% | 10.45% | 0.361 | -15.46% | -3.47% | 32.35% | 41.02% | 0.009 | 0.336 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__bil_fallback_original | 1 | 10 | equal_weight | bil_fallback_original | 4.57% | 13.02% | 0.351 | -21.33% | -4.34% | 38.34% | 25.45% | 0.009 | 0.336 |
| cross_asset_attention_ranker_seed1__top15__inverse_vol__regime_gate_original | 1 | 15 | inverse_vol | regime_gate_original | 3.64% | 10.77% | 0.338 | -17.49% | -3.68% | 36.84% | 32.88% | 0.009 | 0.325 |
| cross_asset_attention_ranker_seed0__top15__equal_weight__bil_fallback_original | 0 | 15 | equal_weight | bil_fallback_original | 4.04% | 12.20% | 0.331 | -20.75% | -4.01% | 32.78% | 25.45% | 0.011 | 0.317 |
| cross_asset_attention_ranker_seed0__top15__inverse_vol__defensive_first | 0 | 15 | inverse_vol | defensive_first | 3.15% | 9.73% | 0.324 | -16.01% | -3.30% | 33.46% | 41.02% | 0.011 | 0.317 |
| cross_asset_attention_ranker_seed0__top10__inverse_vol__bil_fallback_original | 0 | 10 | inverse_vol | bil_fallback_original | 4.21% | 13.19% | 0.319 | -28.54% | -4.37% | 42.21% | 25.45% | 0.011 | 0.324 |
| cross_asset_attention_ranker_seed0__top15__equal_weight__defensive_first | 0 | 15 | equal_weight | defensive_first | 2.93% | 9.83% | 0.298 | -15.39% | -3.29% | 28.14% | 41.02% | 0.011 | 0.317 |

### Strategy Comparison

| strategy_name | category | annual_return | annual_volatility | sharpe | max_drawdown | cvar_5 | average_bil_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mlx5c_bil_fallback_mean_summary | benchmark_summary_only | n/a | n/a | 1.276 | -14.56% | -4.17% | n/a |
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
| SPY | benchmark | 13.24% | 19.37% | 0.683 | -33.63% | -6.31% | n/a |
| 60_40 | benchmark | 8.19% | 12.05% | 0.680 | -21.88% | -3.85% | n/a |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | cross_asset_attention | 5.68% | 12.66% | 0.448 | -21.49% | -4.24% | 25.45% |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__defensive_first | cross_asset_attention | 4.49% | 10.17% | 0.441 | -16.29% | -3.44% | 41.02% |
| cross_asset_attention_ranker_seed1__top15__inverse_vol__bil_fallback_original | cross_asset_attention | 5.06% | 11.71% | 0.432 | -19.41% | -3.82% | 25.45% |
| cross_asset_attention_ranker_seed1__top15__inverse_vol__defensive_first | cross_asset_attention | 3.88% | 9.45% | 0.411 | -14.48% | -3.17% | 41.02% |
| cross_asset_attention_ranker_seed1__top15__equal_weight__bil_fallback_original | cross_asset_attention | 4.51% | 11.92% | 0.378 | -19.28% | -3.88% | 25.45% |
| cross_asset_attention_ranker_seed1__top15__equal_weight__defensive_first | cross_asset_attention | 3.54% | 9.62% | 0.368 | -14.33% | -3.22% | 41.02% |
| cross_asset_attention_ranker_seed0__top15__inverse_vol__bil_fallback_original | cross_asset_attention | 4.40% | 12.05% | 0.365 | -21.16% | -3.97% | 25.45% |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__regime_gate_original | cross_asset_attention | 4.24% | 11.64% | 0.364 | -19.43% | -4.00% | 32.88% |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | cross_asset_attention | 3.78% | 10.45% | 0.361 | -15.46% | -3.47% | 41.02% |
| cross_asset_attention_ranker_seed1__top10__equal_weight__bil_fallback_original | cross_asset_attention | 4.57% | 13.02% | 0.351 | -21.33% | -4.34% | 25.45% |
| cross_asset_attention_ranker_seed1__top15__inverse_vol__regime_gate_original | cross_asset_attention | 3.64% | 10.77% | 0.338 | -17.49% | -3.68% | 32.88% |

### Walk-Forward Window Evaluation

| strategy_name | window | annual_return | sharpe | max_drawdown | cvar_5 | active_weeks |
| --- | --- | --- | --- | --- | --- | --- |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | 2017_2018 | 5.82% | 0.964 | -7.20% | -1.81% | 104 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | 2019_2020 | 2.89% | 0.245 | -15.46% | -3.94% | 104 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | 2021_2022 | -3.11% | -0.321 | -11.09% | -3.37% | 105 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | 2023_2026 | 9.89% | 1.062 | -9.56% | -2.69% | 175 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | 2017_2018 | 5.52% | 0.706 | -12.42% | -2.65% | 104 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | 2019_2020 | 5.01% | 0.359 | -18.82% | -4.89% | 104 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | 2021_2022 | -4.02% | -0.346 | -14.93% | -4.07% | 105 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | 2023_2026 | 13.42% | 1.183 | -12.24% | -3.26% | 175 |

### State-By-State Results

| strategy_name | market_state | annual_return | sharpe | max_drawdown | cvar_5 | average_bil_exposure | average_ml_exposure | weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | calm_trend | -5.67% | -0.425 | -17.94% | -4.49% | 10.00% | 0.9000000000000005 | 101 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | neutral_mixed | 14.76% | 1.644 | -5.88% | -2.39% | 45.00% | 0.5499999999999998 | 121 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | recovery_confirmed | 9.62% | 0.607 | -4.67% | -3.81% | 10.00% | 0.8999999999999998 | 21 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | recovery_fragile | 3.17% | 0.441 | -3.40% | -2.34% | 50.00% | 0.5 | 14 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | stressed_panic | -1.76% | -0.332 | -3.27% | -2.14% | 85.00% | 0.15000000000000002 | 71 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | unknown | 11.58% | 5.978 | -0.12% | -0.12% | 55.00% | 0.6 | 4 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | calm_trend | -6.54% | -0.457 | -21.85% | -5.00% | 0.00% | 1.0 | 101 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | neutral_mixed | 20.95% | 1.766 | -8.26% | -3.17% | 25.00% | 0.75 | 121 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | recovery_confirmed | 12.27% | 0.695 | -5.26% | -4.34% | 0.00% | 1.0 | 21 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | recovery_fragile | 10.98% | 0.777 | -7.07% | -3.49% | 0.00% | 1.0 | 14 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | stressed_panic | -3.01% | -0.352 | -5.70% | -3.47% | 75.00% | 0.25 | 71 |
| cross_asset_attention_ranker_seed1__top10__inverse_vol__bil_fallback_original | unknown | 11.40% | 3.021 | -0.31% | -0.31% | 25.00% | 1.0 | 4 |

### Exposure / Ranking Diagnostics

| strategy_name | audit_type | item | category | average_weight | max_weight | holding_frequency |
| --- | --- | --- | --- | --- | --- | --- |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | Bonds | Bonds | 0.41594879518072286 | 1.0 | 1.0 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | US sectors | US sectors | 0.20775602409638552 | 0.45000000000000007 | 0.9939759036144579 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | International equity | International equity | 0.18296686746987953 | 0.63 | 0.9728915662650602 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | Commodities | Commodities | 0.11917168674698797 | 0.45000000000000007 | 0.9457831325301205 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | Factors/styles | Factors/styles | 0.03209337349397591 | 0.09000000000000001 | 0.463855421686747 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | Real estate | Real estate | 0.019969879518072293 | 0.16500000000000004 | 0.3855421686746988 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | US broad equity | US broad equity | 0.014864457831325303 | 0.18000000000000002 | 0.23795180722891565 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | category | Volatility proxies | Volatility proxies | 0.0072289156626506035 | 0.09000000000000001 | 0.1566265060240964 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | summary | average_top3_weight |  | 0.5281927710843375 | 1.0 | n/a |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | summary | average_safe_asset_weight |  | 0.41594879518072286 | 1.0 | n/a |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | summary | average_BIL_weight |  | 0.41024096385542164 | 1.0 | n/a |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | summary | average_sector_weight |  | 0.20775602409638552 | 0.45000000000000007 | n/a |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | summary | average_commodities_weight |  | 0.11917168674698797 | 0.45000000000000007 | n/a |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | summary | average_SPY_QQQ_SMH_weight |  | 0.046400602409638565 | 0.18000000000000002 | n/a |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | BIL | Bonds | 0.41024096385542164 | 1.0 | 1.0 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | XBI | US sectors | 0.0552710843373494 | 0.09000000000000001 | 0.8644578313253012 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | KRE | US sectors | 0.04362951807228917 | 0.09000000000000001 | 0.7048192771084337 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | SMH | US sectors | 0.04349397590361446 | 0.09000000000000001 | 0.713855421686747 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | EWZ | International equity | 0.04046686746987953 | 0.09000000000000001 | 0.6867469879518072 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | SLV | Commodities | 0.03993975903614458 | 0.09000000000000001 | 0.7228915662650602 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | FXI | International equity | 0.03879518072289157 | 0.09000000000000001 | 0.5753012048192772 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | USO | Commodities | 0.036084337349397595 | 0.09000000000000001 | 0.6536144578313253 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | XLE | US sectors | 0.03328313253012049 | 0.09000000000000001 | 0.5963855421686747 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | MTUM | Factors/styles | 0.03209337349397591 | 0.09000000000000001 | 0.463855421686747 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | EWW | International equity | 0.027003012048192776 | 0.09000000000000001 | 0.4066265060240964 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | INDA | International equity | 0.024668674698795183 | 0.09000000000000001 | 0.34036144578313254 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | IBB | US sectors | 0.016671686746987952 | 0.09000000000000001 | 0.2680722891566265 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | EEM | International equity | 0.01632530120481928 | 0.09000000000000001 | 0.2319277108433735 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | GLD | Commodities | 0.01623493975903615 | 0.09000000000000001 | 0.23795180722891565 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | EWA | International equity | 0.015677710843373497 | 0.09000000000000001 | 0.2710843373493976 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | UNG | Commodities | 0.0151355421686747 | 0.09000000000000001 | 0.3072289156626506 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | XLU | US sectors | 0.012710843373493978 | 0.09000000000000001 | 0.21686746987951808 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | EWY | International equity | 0.009789156626506026 | 0.09000000000000001 | 0.13855421686746988 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | SCHH | Real estate | 0.009006024096385543 | 0.09000000000000001 | 0.286144578313253 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | IAU | Commodities | 0.007289156626506024 | 0.09000000000000001 | 0.15060240963855423 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | IYR | Real estate | 0.007259036144578315 | 0.09000000000000001 | 0.15963855421686746 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | VIXY | Volatility proxies | 0.0072289156626506035 | 0.09000000000000001 | 0.1566265060240964 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | IJR | US broad equity | 0.006837349397590363 | 0.09000000000000001 | 0.12048192771084337 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | TLT | Bonds | 0.005707831325301205 | 0.09000000000000001 | 0.12650602409638553 |
| cross_asset_attention_ranker_seed1__top10__equal_weight__defensive_first | ticker | ASHR | International equity | 0.005677710843373495 | 0.09000000000000001 | 0.09939759036144578 |

Attention weights were not extracted in this first CPU-bounded implementation. The diagnostics instead audit scores indirectly through top holdings, category exposures, BIL exposure, SPY/QQQ/SMH concentration, state-by-state behavior, rank IC, and top-quintile hit rate.

## Interpretation

- Did cross-asset attention beat MLX-5C mean Sharpe? False
- Did it beat MLX-6 Transformer? False
- Did it beat MLX-9 ensemble? False
- Did it beat production? False
- Did it beat Phase 4B? False
- Final recommendation: **KEEP AS RESEARCH ONLY**

The first version answers whether cross-sectional attention is promising enough for deeper work. A better version should add explicit pairwise/listwise ranking loss, extract attention maps, run full walk-forward retraining, test more seeds, and eventually move to PIT stock data.

## Warnings

- Experimental research-only Phase MLX output; not production-valid.
- Expanded ETF/yfinance research data can introduce selection bias and data-mining risk.
- No cross-asset attention model is promoted automatically.
