# Macro Regime Classifier — Research Sprint Notes

**Sprint date:** 2026-06-05  
**Verdict:** `RESEARCH-ONLY`

---

## Design

| Parameter | Value |
| --- | --- |
| FRED series | BAMLH0A0HYM2, NFCI, UMCSENT, FEDFUNDS, UNRATE, CPIAUCSL_yoy, INDPRO_yoy, PAYEMS_yoy, RSAFS_yoy, HOUST_yoy |
| PCA window | Expanding, quarterly refit, min 60 months |
| PC1 | `growth_factor` (sign-anchored on INDPRO_yoy) |
| PC2 | `inflation_financial_conditions_factor` (sign-anchored on NFCI) |
| Quadrants | expansion / overheating / slowdown / stress |
| Lag | Monthly factors → weekly via merge_asof + 1-week shift |
| Development | through 2024-04-12 |
| Holdout | 2024-04-19 onward (last 104 weeks) |

## Quadrant Classification

| growth_factor | inflation_fc_factor | macro_quadrant |
| --- | --- | --- |
| > 0 | < 0 | expansion (Goldilocks: growth up, conditions loose) |
| > 0 | > 0 | overheating (growth up, conditions tighten) |
| < 0 | < 0 | slowdown (growth down, conditions loose) |
| < 0 | > 0 | stress (growth down, conditions tight) |

## Coverage

- Total weekly observations: 1110
- Weeks with macro quadrant assigned: 1109 (99.9%)

### Weekly quadrant distribution

| Quadrant | Count |
| --- | --- |
| expansion | 180 |
| overheating | 276 |
| slowdown | 441 |
| stress | 212 |

## 4-Week Forward SPY Returns by Quadrant

### Development period

| Quadrant | N | Mean 4w | Std 4w | Sharpe |
| --- | --- | --- | --- | --- |
| expansion | 180 | 0.00227 | 0.05607 | 0.04 |
| overheating | 256 | 0.00762 | 0.03541 | 0.215 |
| slowdown | 441 | 0.01386 | 0.03784 | 0.366 |
| stress | 128 | -0.00022 | 0.06773 | -0.003 |

### Holdout period

| Quadrant | N | Mean 4w | Std 4w | Sharpe |
| --- | --- | --- | --- | --- |
| expansion | 0 | nan | nan | nan |
| overheating | 20 | 0.00932 | 0.03967 | 0.235 |
| slowdown | 0 | nan | nan | nan |
| stress | 80 | 0.01241 | 0.03749 | 0.331 |

## Neutral-Mixed Sub-Split

neutral_mixed total weeks: 490

### Macro quadrant distribution within neutral_mixed

| Quadrant | Count |
| --- | --- |
| slowdown | 237 |
| overheating | 106 |
| stress | 80 |
| expansion | 67 |

### 4-week forward SPY within neutral_mixed (dev period)

| Quadrant | N | Mean 4w | Std 4w | Sharpe |
| --- | --- | --- | --- | --- |
| expansion | 67 | 0.00373 | 0.03657 | 0.102 |
| overheating | 95 | 0.01015 | 0.03745 | 0.271 |
| slowdown | 237 | 0.01466 | 0.0316 | 0.464 |
| stress | 35 | 0.00241 | 0.04007 | 0.06 |

## Pass / Fail Criteria

| Criterion | Threshold | Result | Met? |
| --- | --- | --- | --- |
| Dev 4w SPY spread | > 1.0% (0.01) | 0.0141 | YES |
| Neutral-mixed spread | > 0.5% (0.005) | 0.0123 | YES |
| Holdout rank-consistent | Best/worst quad match | False | NO |

## Verdict: `RESEARCH-ONLY`

- Dev 4w SPY spread: 0.0141 (threshold >0.01) — MET
- Neutral-mixed spread: 0.0123 (threshold >0.005) — MET
- Holdout rank-consistent: False — NOT MET

## Implications and Next Steps

The macro quadrant classifier shows a weak but non-zero signal. Not strong enough
for immediate promotion. Recommended next steps:

1. Investigate whether combining macro quadrant with existing market states improves signal quality.
2. Consider alternative PCA feature sets or additional transformations.
3. Do NOT integrate into production allocation without clearing all 8 Phase D gates.

## Warnings

- FETCH FAILED T10Y2Y: HTTP Error 504: Gateway Time-out
- FETCH FAILED DGS3MO: HTTP Error 504: Gateway Time-out
- FETCH FAILED DTWEXBGS: HTTP Error 504: Gateway Time-out
- FETCH FAILED ICSA: HTTP Error 504: Gateway Time-out

---
*Research artifact sprint — no production artifacts modified.*
