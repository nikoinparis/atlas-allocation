# Research Laboratory — Batch 01

**288** standardized trend/momentum and portfolio-construction experiments were run on immutable snapshot `20260808T212827Z-de103c2e063d6c4a` through 2026-08-07.

## What was tested

Eight signal recipes × three smoothing windows × three portfolio sizes × four allocation methods. Every experiment used lagged signals, calendar-causal monthly decisions, next-week return realization, and 10 bps turnover costs.

## Development-selected leader

- Experiment: `exp-3a187e9134eefe61`.
- Recipe / construction: **time_series_momentum_only / score_inverse_volatility**, top 6, smoothing 1 weeks.
- Development (2006–2015): annual return **8.29%**, Sharpe **0.901**, drawdown **-13.39%**.
- Retrospective 2016–2020: annual return **5.11%**, Sharpe **0.474**, drawdown **-19.27%**.
- Retrospective 2021–present: annual return **9.57%**, Sharpe **1.027**, drawdown **-13.58%**.

## Frozen-v4 benchmark row

The exact all-five, four-week smoothing, top-four equal-weight configuration is `exp-fc7248702f02b421`. Full-history annual return is **9.91%**, Sharpe **0.754**, and maximum drawdown **-26.25%**.

## Retrospective walk-forward

- 2016-01-01 to 2020-12-31: `exp-3a187e9134eefe61`; evaluation Sharpe 0.474, annual return 5.11%.
- 2021-01-01 to 9999-12-31: `exp-36a0f3d51675c16f`; evaluation Sharpe 1.158, annual return 13.30%.

The stitched evaluation path has annual return **9.36%**, Sharpe **0.825**, and maximum drawdown **-19.27%**. Selection used only each fold's earlier training window, but this is still retrospective—not untouched—evidence.

## Ideas taken from the awesome repository

- [vectorbt](https://github.com/polakowo/vectorbt): evaluate many parameter combinations through one consistent vector-style research path; no source code copied.
- [pysystemtrade](https://github.com/robcarver17/pysystemtrade): separate forecasting rules from position sizing and portfolio construction; no source code copied.
- [skfolio](https://github.com/skfolio/skfolio): treat portfolio optimization like model selection with chronological evaluation; no source code copied.
- [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib): compare multiple risk-aware allocation objectives rather than assuming one weighting rule; no source code copied.
- [Manifold-BT](https://github.com/manifoldbt/manifoldbt): make costs, look-ahead control, walk-forward testing, and parameter sweeps first-class evidence; no source code copied.

## Interpretation

This batch is a research funnel, not a money-making claim. The 288-way comparison raises false-discovery risk, and the free ETF universe lacks point-in-time membership. Candidates must survive parameter-neighborhood, cost, regime, and future untouched tests before promotion.
