# Data Availability Report — Macro Regime Classifier V3

## FRED + yfinance Series

| Series | Source | N Raw Obs | First | Last |
| --- | --- | --- | --- | --- |
| INDPRO | V2_CACHE | 1288 | 1919-01-01 | 2026-04-01 |
| PAYEMS | V2_CACHE | 1049 | 1939-01-01 | 2026-05-01 |
| RSAFS | V2_CACHE | 412 | 1992-01-01 | 2026-04-01 |
| HOUST | V2_CACHE | 808 | 1959-01-01 | 2026-04-01 |
| UMCSENT | V2_CACHE | 882 | 1952-11-01 | 2026-04-01 |
| UNRATE | V2_CACHE | 941 | 1948-01-01 | 2026-05-01 |
| ICSA | V2_CACHE | 3100 | 1967-01-07 | 2026-05-30 |
| CPIAUCSL | V2_CACHE | 952 | 1947-01-01 | 2026-04-01 |
| FEDFUNDS | V2_CACHE | 863 | 1954-07-01 | 2026-05-01 |
| BAMLH0A0HYM2 | V2_CACHE | 795 | 2023-06-06 | 2026-06-04 |
| TNX_10yr_yield | YFINANCE | 6640 | 2000-01-03 | 2026-06-05 |
| IRX_3mo_yield | YFINANCE | 6640 | 2000-01-03 | 2026-06-05 |
| DXY_dollar_index | YFINANCE | 6675 | 2000-01-03 | 2026-06-05 |

## Financial Conditions Proxy Components

- VIX_z: expanding z-score of VIX level (higher = more stress)
- credit_z: expanding z-score of -(HYG/LQD ratio), higher = tighter credit
- drawdown_z: expanding z-score of -SPY_drawdown, higher = deeper drawdown
- corr_z: avg_corr_risk_off_z from regime engine (already z-scored)

---
*Research artifact — no production code modified.*
