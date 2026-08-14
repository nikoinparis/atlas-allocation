# ml-quant-trading ETF factor qualification — Batch 30

Pinned repository commit: `867e8dfe628b1d0ea2af987ec6f74c32c645f63e`

The repository registered 213 factors; 213 completed the mechanical finiteness audit. No factor outside the six source-preselected ETF factors was screened for performance.

| Factor | Dev direction | Dev mean IC | Validation signed IC | Test signed IC | Combined lower bound | Qualified |
|---|---:|---:|---:|---:|---:|---|
| best_001 | +1 | 0.0408 | 0.0241 | -0.0056 | -0.0102 | no |
| best_002 | +1 | 0.0466 | 0.0328 | 0.0115 | 0.0036 | yes |
| original_001 | +1 | 0.0258 | 0.0377 | 0.0199 | 0.0138 | yes |
| stock_001 | -1 | -0.0113 | 0.0036 | -0.0004 | -0.0129 | no |
| add_015 | -1 | -0.0124 | 0.0175 | 0.0091 | -0.0038 | no |
| old_042 | +1 | 0.0272 | 0.0048 | 0.0184 | -0.0043 | no |

Qualified factors: best_002, original_001.

This is a close-to-next-close rank-IC diagnostic on a fixed survivor ETF universe using a typical-price VWAP proxy. It is not a tradable return series. A portfolio backtest is permitted only for factors that pass every predeclared gate, and would require separate next-session execution, turnover, costs, and risk controls.
