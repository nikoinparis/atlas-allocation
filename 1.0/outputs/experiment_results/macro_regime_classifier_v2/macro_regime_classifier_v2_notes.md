# Macro Regime Classifier V2 — Sprint Notes

**Sprint date:** 2026-06-05
**Verdict:** `RESEARCH-ONLY`

---

## 1. Did v2 recover the missing FRED series?

V1 used 10 series.
V2 attempted 14 series and successfully used 10.
Still missing: T10Y2Y, NFCI, DGS3MO, DTWEXBGS

**Criterion ≥12 series:** NOT MET

## 2. Did the full feature set change the PCA factors?

| Factor | Variance Explained |
| --- | --- |
| PC1_pct | 39.3% |
| PC2_pct | 18.4% |
| PC3_pct | 15.4% |

## 3. Are the factor loadings interpretable?

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

**Criterion loadings interpretable:** MET

## 4. Did v2 improve holdout consistency vs v1?

- V2 holdout rank consistent: False
- V2 holdout quadrants populated: 3/4
- Holdout improved vs v1: True
**Criterion:** MET

## 5. Does v2 split neutral_mixed better than v1?

V2 neutral_mixed dev spread: 0.0378

| Period | Quadrant | N | Mean 4w | Sharpe |
| --- | --- | --- | --- | --- |
| dev | expansion | 101 | 0.01096 | 0.336 |
| dev | overheating | 107 | 0.00908 | 0.255 |
| dev | slowdown | 21 | -0.02235 | -0.506 |
| dev | stress | 205 | 0.01544 | 0.479 |
| holdout | expansion | 10 | -0.01548 | -0.367 |
| holdout | overheating | 3 | 0.05623 | 4.059 |
| holdout | slowdown | 43 | 0.00325 | 0.101 |
| holdout | stress | 0 | nan | nan |

**Criterion nm_spread > 0.5%:** MET

## 6. Does macro work better alone or with confirmation?

| Diagnostic | Best Sharpe (dev) |
| --- | --- |
| A_macro_only | 0.368 |
| B_macro_plus_spy_trend | 0.526 |
| C_macro_plus_credit | 0.599 |
| D_macro_plus_neutral_mixed_state | 0.479 |

**Criterion confirmation better than macro-only:** MET

## 7. Should the project proceed to macro-conditioned ETF tilt testing?

**CONDITIONAL.** Dev signal exists but holdout is unstable. Recommended next steps:

1. Investigate the holdout period macro environment more carefully.
2. Test macro quadrants as a research-only conditioning feature in a sandbox.
3. Do not build a production ETF tilt overlay until holdout consistency improves.

## 8. Final Verdict

**`RESEARCH-ONLY`**

### Criteria Summary

| Criterion | Result | Met? |
| --- | --- | --- |
| Series used: 10/14 (threshold ≥12) | NOT MET |  |
| Dev 4w SPY spread: 0.0242 (threshold >0.01) | MET |  |
| Neutral-mixed spread: 0.0378 (threshold >0.005) | MET |  |
| Holdout rank consistent: False |  |  |
| Holdout improved vs v1: True | MET |  |
| Confirmation diagnostics better: True | MET |  |
| Loadings interpretable: True | MET |  |

## FRED Fetch Log

| Series | Source | N Obs |
| --- | --- | --- |
| T10Y2Y | FAILED | 0 |
| BAMLH0A0HYM2 | LIVE | 795 |
| NFCI | FAILED | 0 |
| DGS3MO | FAILED | 0 |
| UMCSENT | LIVE | 882 |
| FEDFUNDS | LIVE | 863 |
| DTWEXBGS | FAILED | 0 |
| UNRATE | LIVE | 941 |
| CPIAUCSL | LIVE | 952 |
| INDPRO | LIVE | 1288 |
| PAYEMS | LIVE | 1049 |
| RSAFS | LIVE | 412 |
| HOUST | LIVE | 808 |
| ICSA | CACHED | 3100 |

---
*Research artifact sprint — no production artifacts modified.*
