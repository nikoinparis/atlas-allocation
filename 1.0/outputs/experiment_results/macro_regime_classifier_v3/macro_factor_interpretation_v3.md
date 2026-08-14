# Macro Factor Interpretation — V3

## Factor Architecture

| Factor | Method | Anchor |
| --- | --- | --- |
| growth_factor | Monthly expanding PCA (PC1) | INDPRO_yoy positive |
| financial_conditions_proxy | Weekly composite (equal-weight z-scores) | VIX, HYG/LQD, SPY DD, avg_corr |
| inflation_policy_factor | Monthly composite (equal-weight z-scores) | CPIAUCSL_yoy, FEDFUNDS, T10Y2Y_inv, DXY_mom |

## Quadrant Map

| growth_factor | financial_conditions_proxy | macro_state |
| --- | --- | --- |
| > 0 | < 0 | **expansion** (Goldilocks) |
| > 0 | > 0 | **overheating** (tight but growing) |
| < 0 | < 0 | **slowdown** (growth weak, conditions benign) |
| < 0 | > 0 | **stress** (growth weak AND conditions tight) |

## Growth Factor Loadings (last dev refit)

| Feature | PC1 loading |
| --- | --- |
| INDPRO_yoy | 0.475 |
| PAYEMS_yoy | 0.484 |
| RSAFS_yoy | 0.433 |
| HOUST_yoy | 0.286 |
| UMCSENT | 0.277 |
| UNRATE | -0.324 |
| ICSA | -0.298 |

## Financial Conditions Proxy Components

- VIX_z: expanding z-score of VIX level (higher = more stress)
- credit_z: expanding z-score of -(HYG/LQD ratio), higher = tighter credit
- drawdown_z: expanding z-score of -SPY_drawdown, higher = deeper drawdown
- corr_z: avg_corr_risk_off_z from regime engine (already z-scored)

## Important Caveats

- `financial_conditions_proxy` is NOT true NFCI. NFCI was unavailable.
- The proxy uses fully market-observable signals with weekly frequency.
- Stress-period sanity checks (2008, 2020, 2022) validate proxy adequacy.
- `T10Y2Y_proxy` = ^TNX 10yr yield minus ^IRX 3-month yield from yfinance.
- Dollar momentum = DX-Y.NYB 3-month percent change from yfinance.

---
*Research artifact — no production code modified.*
