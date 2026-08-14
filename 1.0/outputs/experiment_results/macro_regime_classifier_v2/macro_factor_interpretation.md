# Macro Factor Interpretation

Factor loadings from the last quarterly PCA refit in the development period.
Signs have been adjusted so that:
- PC1 (growth_factor) is positive when INDPRO_yoy is positive (above-trend growth)
- PC2 (inflation_financial_conditions_factor) is positive when NFCI is positive (tight conditions)

## Variance Explained

| Factor | Var Explained |
| --- | --- |
| PC1_pct | 39.3% |
| PC2_pct | 18.4% |
| PC3_pct | 15.4% |

## Feature Loadings

Positive = feature rises when factor rises. Negative = inverse.

| Feature | PC1 | PC2 | PC3 |
| --- | --- | --- | --- |
| UMCSENT | 0.232 | 0.298 | 0.638 |
| FEDFUNDS | 0.267 | 0.537 | 0.009 |
| UNRATE | -0.349 | -0.405 | 0.072 |
| CPIAUCSL_yoy | 0.279 | -0.077 | -0.632 |
| INDPRO_yoy | 0.438 | -0.162 | 0.127 |
| PAYEMS_yoy | 0.463 | -0.046 | -0.094 |
| RSAFS_yoy | 0.393 | -0.384 | -0.031 |
| HOUST_yoy | 0.197 | -0.523 | 0.392 |
| ICSA | -0.276 | -0.052 | 0.095 |

## Interpretation Notes

### PC1 — growth_factor
- High positive: economy expanding, industrial production rising, payrolls growing
- High negative: contraction, rising unemployment, falling retail sales

### PC2 — inflation_financial_conditions_factor
- High positive: tight financial conditions (high NFCI), elevated spreads, high inflation
- High negative: loose conditions, low spreads, subdued inflation

### PC3 — credit_liquidity_factor (if applicable)
- Captures residual variation not explained by growth or inflation
- May reflect liquidity / currency / idiosyncratic credit conditions

## Quadrant Map

| growth_factor | inflation_fc_factor | macro_quadrant |
| --- | --- | --- |
| > 0 | < 0 | **expansion** (Goldilocks) |
| > 0 | > 0 | **overheating** |
| < 0 | < 0 | **slowdown** |
| < 0 | > 0 | **stress** |

*Research artifact — no production code modified.*
