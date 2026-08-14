# Macro Regime Classifier V3 — Sprint Notes

**Sprint date:** 2026-06-05
**Verdict:** `EXPERIMENTAL CANDIDATE`

---

## 1. Did V3 recover NFCI or build a reasonable proxy?

NFCI is still unavailable via FRED public CSV (consistent 504 timeout, all 3 sprints).
V3 builds a transparent `financial_conditions_proxy` from weekly market-observable signals:
- VIX level z-score (weekly, full coverage)
- -(HYG/LQD ratio) z-score (credit stress proxy)
- -SPY_drawdown z-score (equity market stress)
- avg_corr_risk_off_z (cross-asset correlation stress)

**Proxy quality: PROXY_USED**

## 2. Did V3 recover more of the intended 14-series macro set?

- Growth features: PAYEMS_yoy, INDPRO_yoy, RSAFS_yoy, HOUST_yoy, UMCSENT, UNRATE, ICSA (from V2 cache)
- Policy features: CPIAUCSL_yoy, FEDFUNDS (from V2 cache)
- T10Y2Y proxy: ^TNX - ^IRX from yfinance (NEW in V3)
- Dollar momentum: DX-Y.NYB from yfinance (NEW in V3)
- Still missing: T10Y2Y, NFCI, DGS3MO, DTWEXBGS from FRED direct

## 3. Are the growth, inflation/policy, and financial-conditions factors interpretable?

| Factor | Interpretable? | Notes |
| --- | --- | --- |
| growth_factor | YES | PC1 loads on PAYEMS_yoy, INDPRO_yoy, RSAFS_yoy (positive) and UNRATE, ICSA (negative) |
| financial_conditions_proxy | YES | Higher = VIX elevated, credit tight, SPY drawing down, correlations elevated |
| inflation_policy_factor | YES | Higher = CPI rising, Fed funds high, curve flat/inverted, dollar strengthening |

## 4. Do 2008, March 2020, and late 2022 classify correctly?

| Period | Dominant State | Pass? |
| --- | --- | --- |
| 2008_crisis | stress | YES |
| covid_crash_2020 | stress | YES |
| rate_shock_2022 | overheating | YES |

**Sanity checks all pass: YES**

## 5. Does V3 split neutral_mixed into useful sub-regimes?

neutral_mixed dev spread: 0.02287
Threshold: > 0.005 → MET

## 6. Does V3 improve holdout consistency vs V1/V2?

V3 holdout rank consistent: N/A
Holdout quads populated: 2/4

## 7. Does macro work better alone, or with credit/trend confirmation?

| Diagnostic | Best Dev Sharpe |
| --- | --- |
| A_macro_only | 0.269 |
| B_credit_trend_only | N/A |
| C_macro_plus_credit | 0.410 |
| D_macro_plus_spy_trend | 0.606 |
| E_macro_plus_fc_tight | 0.269 |
| G_state_plus_macro_plus_credit | 0.687 |

Best macro-only dev Sharpe: 0.269
Best macro+confirmation dev Sharpe: 0.606
Confirmation adds value: YES

## 8. Most actionable path?

**Macro-conditioned neutral_mixed ETF tilt testing is recommended.**

Specifically: in neutral_mixed weeks, test whether higher equity offense allocation
when macro state = expansion or overheating improves portfolio return.
Must run through Phase D gates before any production integration.

## 9. Final Verdict

**`EXPERIMENTAL CANDIDATE`**

### Criteria Summary

| Criterion | Result | Met? |
| --- | --- | --- |
| sanity_checks_pass | True |  |
| fc_interpretable_met | True |  |
| dev_4w_spread | 0.0081 |  |
| dev_4w_spread_met | False |  |
| nm_spread | 0.02287 |  |
| nm_spread_met | True |  |
| holdout_not_broken | True |  |
| holdout_rank_consistent | False |  |
| holdout_quads_populated | 2 |  |
| confirmation_better_met | True |  |
| no_sparse_quadrants_met | True |  |
| fc_proxy_quality | PROXY_USED |  |

---
*Research artifact sprint — no production artifacts modified.*
