# skfolio bounded drawdown component — Batch 38

The full skfolio library did not qualify, so this batch tested a boundary fixed
before component results: `MeanRisk`, `MINIMIZE_RISK`, CLARABEL, and only CDaR,
maximum drawdown, EDaR, and Ulcer Index. Entropy pooling, Black–Litterman, views,
and expected-return forecasts are expressly excluded.

All 274 matching upstream drawdown test parameterizations passed. On seeded
synthetic data, all four optimizers produced finite long-only weights summing to
one with a 35% cap. Exact repeats had zero maximum weight difference, and
perturbing future returns did not change weights at the prior decision point.

This narrow component is therefore qualified for a separately predeclared,
causal portfolio experiment. This result is an engineering qualification, not
evidence that the methods make money.
