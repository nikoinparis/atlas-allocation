# Portfolio Robustness — Batch 07

The Batch 06 development-selected minimum-variance portfolio was stressed at 50 bps using rolling windows, serial block bootstrap, stale and synthetically revised covariance observations, missing estimator inputs, and malformed covariance fallbacks.

- Overall robustness gate: **PASS**.
- Baseline at 50 bps: **6.58%** annual return, **0.769** Sharpe, **-23.50%** drawdown.
- Rolling 3-year windows: **20** evaluated; worst drawdown **-23.50%**.
- Bootstrap 95% annual-return interval: **3.09% to 9.96%**.
- Bootstrap 95% Sharpe interval: **0.361 to 1.231**.

Passing this batch freezes the rules for forward observation; it does not make the portfolio final, survivorship-safe, or approved for real money.
