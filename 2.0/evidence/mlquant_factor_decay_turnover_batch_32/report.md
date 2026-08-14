# Factor decay and turnover controls — Batch 32

Development selected a 20-session IC horizon. Validation IC was 0.0694, test IC 0.0254, and the familywise lower bound 0.0084.

| Candidate | Return 10 bps | Return 50 bps | Sharpe | Drawdown | Turnover/year | Return 100 bps | Blend Sharpe | Core Sharpe | Historical gates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| monthly_equal_top5 | 7.73% | 5.24% | 0.399 | -52.80% | 5.84 | 2.21% | 0.702 | 0.769 | fail |
| monthly_inverse_volatility_top5 | 6.93% | 4.09% | 0.338 | -50.67% | 6.74 | 0.63% | 0.684 | 0.769 | fail |
| buffered_equal_top5 | 9.14% | 5.94% | 0.458 | -44.06% | 7.44 | 2.07% | 0.724 | 0.769 | fail |
| buffered_inverse_volatility_top5 | 8.39% | 4.37% | 0.377 | -40.37% | 9.46 | -0.45% | 0.701 | 0.769 | fail |

Historical challengers: none.
Promoted: none.

Live trading remains disabled.
