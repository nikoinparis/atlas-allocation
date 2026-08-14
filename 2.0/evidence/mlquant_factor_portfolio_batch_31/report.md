# Qualified mlquant factor portfolios — Batch 31

Two constructions were fixed before returns were viewed. Signals are observed at a completed weekly close, entered at the following weekly close, and earn returns only after entry.

| Candidate | Return (50 bps) | Sharpe | Drawdown | Turnover/year | Return (100 bps) | 80/20 blend Sharpe | Core Sharpe | Historical gates |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| equal_weight_top5 | -1.31% | -0.002 | -64.46% | 23.19 | -12.14% | 0.569 | 0.769 | fail |
| inverse_volatility_top5 | -3.60% | -0.168 | -71.13% | 26.99 | -15.80% | 0.525 | 0.769 | fail |

Historical challengers: none.
Promoted candidates: none.

Even a historical-gate pass remains research-only because the ETF universe is a survivor list and no new untouched 52-week record exists. Live trading remains disabled.
