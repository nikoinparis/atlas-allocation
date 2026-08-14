# Production vs Shadow Equivalence Map

**Path B Sprint 0 — 2026-06-07**
**Purpose**: Ensure the shadow rebuild is compared apples-to-apples against production.

Statuses:
- `MATCH` — shadow must produce identical output
- `REUSE_EXISTING` — shadow reads production artifact directly, no reimplementation
- `REIMPLEMENT_IDENTICAL` — shadow reimplements with identical behavior (verified by test)
- `INTENTIONAL_DIFF` — shadow deliberately differs here (primary research variables)
- `UNKNOWN` — not yet verified
- `NEEDS_TEST` — requires Sprint 0.5 equivalence check
- `NOT_USED` — not applicable in shadow system

---

## A. Data / Universe

| Component | Production Behavior | Shadow Behavior | Status | Source | Notes | Risk if Mismatched |
| --- | --- | --- | --- | --- | --- | --- |
| ETF universe | 35 ETFs (BIL, DBA, EEM, EFA, EWJ, GLD, HYG, IAU, IEF, IWM, QQQ, SPY, TLT, SHY, TIP, VEA, VNQ, VTV, VWO, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY, PDBC, IYR, EWJ, EWZ, ...) | Same 35 ETFs | REUSE_EXISTING | `data/01_data_hub/weekly_prices.csv` | Shadow reads same file | Universe difference would invalidate all metric comparisons |
| Weekly prices file | `data/01_data_hub/weekly_prices.csv` | Same file | REUSE_EXISTING | `weekly_prices.csv` | Identical load | — |
| Start/end dates | 2005-01-07 to 2026-04-10 | Same | REUSE_EXISTING | `weekly_prices.csv` | 1110 rows | Truncation would shift metrics |
| Date index alignment | Fridays (weekly) | Same | NEEDS_TEST | `00_compare_production_shadow_contract.py` | Sprint 0.5 verifies exact date match | Date misalignment would corrupt all returns |
| Adjusted close convention | Yahoo Finance adjusted close, as-of production run | Same file | REUSE_EXISTING | Same source | Using same CSV eliminates drift | — |
| Return calculation | `pct_change()` on weekly_prices | Same convention | REIMPLEMENT_IDENTICAL | Script 00 verifies | Must match to <1e-10 tolerance | Small convention diff compounds to large error over 21yr |
| Missing data handling | Forward-fill within universe | Same | REIMPLEMENT_IDENTICAL | Script 00 verifies | — | NA propagation could cause NaN weight errors |
| Survivorship | All 35 ETFs present for full history | Same | REUSE_EXISTING | Prices CSV | No lookback period changes | — |
| Benchmark returns | SPY, AGG weekly returns | Same | REUSE_EXISTING | `benchmark_returns_weekly.csv` | Shadow uses same benchmark file | — |
| BIL as cash proxy | BIL in ETF universe | Same | REUSE_EXISTING | Weekly prices | — | — |

---

## B. Timing / Causality

| Component | Production Behavior | Shadow Behavior | Status | Source | Notes | Risk if Mismatched |
| --- | --- | --- | --- | --- | --- | --- |
| Execution delay | 1 week: weights set at close of t, return earned t→t+1 | Same: `gross[t] = w[t] @ r[t+1]` | REIMPLEMENT_IDENTICAL | Script 00 verifies on production artifact | **Critical** — any deviation creates lookahead | Lookahead invalidates all backtest metrics |
| Signal availability | All signals set with 1-week causal lag at t, available to use at t+1 | Same | REIMPLEMENT_IDENTICAL | All scripts enforce shift(1) | — | Lookahead from lag error creates phantom alpha |
| Macro data lag | FRED data: month-end vintage with 1-month release lag | V3 proxy: 1-week VIX/HYG/SPY lag | INTENTIONAL_DIFF | V3 proxy replaces FRED | Proxy is more timely but less fundamental | Known difference — V3 proxy was validated in all 3 overlay sprints |
| FRED lag | ~1-month lag (unavailable in production — macro_weekly is empty) | Same — FRED not used | MATCH | macro_weekly.csv empty | V3 proxy used instead | — |
| VIX lag | 1-week tradable lag (vix_level_z_tradable) | Same | REUSE_EXISTING | `regime_score.csv` | Production already applies 1-week lag | — |
| Google Trends lag | 1-week lag (tradable column) | Same | REUSE_EXISTING | `regime_score.csv` | Production convention preserved | — |
| Forward return calculation | `gross[t] = w[t] @ r[t+1]` using `pct_change().shift(-1)` | Same | REIMPLEMENT_IDENTICAL | Verified in overlay scripts | — | — |
| Holdout split | Dev end: 2024-04-12; Holdout start: 2024-04-19 | Same | REIMPLEMENT_IDENTICAL | Hardcoded constants checked in Script 00 | Must be identical timestamps | Holdout contamination if split differs by even 1 week |
| One-week execution delay | Explicitly implemented via `etf_rets.shift(-1)` convention | Same | REIMPLEMENT_IDENTICAL | — | — | — |

---

## C. Layer 1 Signals

| Component | Production Behavior | Shadow Behavior | Status | Source | Notes | Risk if Mismatched |
| --- | --- | --- | --- | --- | --- | --- |
| Cross-sectional momentum | `signal_xsmom.csv` from 02_layer1_alpha_signals.ipynb | REUSE_EXISTING artifact | REUSE_EXISTING | `data/02_layer1_signals/signal_xsmom.csv` | No reimplementation | — |
| Time-series momentum | `signal_tsmom.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_tsmom.csv` | — | — |
| Multi-horizon momentum | `signal_multi_horizon_mom.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_multi_horizon_mom.csv` | — | — |
| Reversal | `signal_reversal.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_reversal.csv` | — | — |
| Quality | `signal_quality.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_quality.csv` | — | — |
| Carry | `signal_carry.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_carry.csv` | — | — |
| Value | `signal_value.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_value.csv` | — | — |
| Trend quality | `signal_trend_quality.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_trend_quality.csv` | — | — |
| Breadth confirmation | `signal_breadth_confirmation.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/signal_breadth_confirmation.csv` | — | — |
| Credit/bond | `signal_r2_credit_spread.csv`, `signal_r4_pair_hyg_lqd.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/` | — | — |
| VIX/FC signals | `signal_r2_vix_term_structure.csv`, `signal_r2_financial_conditions.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/` | — | — |
| State-conditional IC | `signal_state_conditional_ic.csv` | REUSE_EXISTING | REUSE_EXISTING | `data/02_layer1_signals/` | Used for baseline weighting reference | — |
| Signal normalization | Production convention (cross-sectional z-score or rank) | Same convention | NEEDS_TEST | Script 00 checks alignment | — | Different normalization = different rankings = different weights |
| Signal winsorization | Production convention (clip at ±3σ) | Same | NEEDS_TEST | Script 00 | — | — |
| Missing signal handling | NaN propagation or cross-sectional fill | Same | NEEDS_TEST | Script 00 | — | — |
| **New: Signal E_4wk** | Not in production | Native NM sub-state feature | INTENTIONAL_DIFF | V3 + credit build in Script 01 | New research feature | Allowed difference |

---

## D. Layer 2A Sleeves

| Component | Production Behavior | Shadow Behavior | Status | Source | Notes | Risk if Mismatched |
| --- | --- | --- | --- | --- | --- | --- |
| Sleeve definitions | 6 sleeves: dual_momentum_topn, cta_trend_long_only, composite_selective_signals, composite_regime_offense_component, composite_regime_defense_component, taa_10m_sma | Same 6 sleeves (Path B Sprint 0–5 does not change sleeves) | REUSE_EXISTING | Production sleeve CSV files | Sleeves are not the target of this rebuild | Sleeve change would confound regime engine comparison |
| Sleeve universe | Each sleeve selects from the 35-ETF universe | Same | REUSE_EXISTING | Layer 2A notebooks | — | — |
| Sleeve rebalance frequency | Weekly | Same | REUSE_EXISTING | — | — | — |
| Sleeve constraints | Long-only, max weight caps | Same | REUSE_EXISTING | — | — | — |
| Sleeve cost assumptions | 10 bps per unit turnover | Same | MATCH | Global constant | — | — |

---

## E. Layer 2B Regime Engine

| Component | Production Behavior | Shadow Behavior | Status | Source | Notes | Risk if Mismatched |
| --- | --- | --- | --- | --- | --- | --- |
| Production regime states | 5 states: neutral_mixed, calm_trend, stressed_panic, recovery_fragile, recovery_confirmed | Shadow adds NM sub-states | **INTENTIONAL_DIFF** | Primary research variable | Native NM decomposition is the hypothesis | Desired difference — must be documented |
| Production regime features | VIX z, drawdown z, breadth z, corr z, macro risk, google fear | Reuse production + add V3 macro/credit | INTENTIONAL_DIFF | V3 features new in shadow | Additional features allowed | Adds V3 proxy only — controlled addition |
| Risk score construction | Composite z-score from regime features | May differ in native rebuild | INTENTIONAL_DIFF | Sprint 2 defines | Must be documented vs production | — |
| neutral_mixed definition | Catch-all: not stressed, not calm | NM + macro sub-states in native | INTENTIONAL_DIFF | Core hypothesis | Intentionally splitting NM | — |
| calm_trend definition | Low volatility, positive breadth, stable | Same definition in native | MATCH | Must not accidentally change | Changing calm_trend is out of scope | Calm_trend change would confound results |
| stressed_panic definition | High VIX, negative breadth, high drawdown | Same | MATCH | Must preserve protection guarantee | Critical safety constraint | Any weakening of stress protection is a hard stop |
| Recovery states definition | Post-stress transition states | Same | MATCH | Fragility guard must be preserved | Phase 5 guard is production feature | — |
| Fragility guard | Phase 5: caps re-risking after stressed_panic | Same or stronger | MATCH/INTENTIONAL_DIFF | If changed: document explicitly | Cannot weaken fragility protection | Any weakening is hard stop |
| Transition behavior | Rule-based threshold crossing | Native may add hysteresis | INTENTIONAL_DIFF | Sprint 2 design | Goal of this sprint | — |
| **State persistence/hysteresis** | Not in production | New in native | INTENTIONAL_DIFF | Core hypothesis | The key improvement being tested | — |
| **Macro/credit features** | Not in production regime engine | Native includes V3 proxy + credit | INTENTIONAL_DIFF | Core hypothesis | V3 macro states as native features | — |

---

## F. Layer 3 Portfolio Construction

| Component | Production Behavior | Shadow Behavior | Status | Source | Notes | Risk if Mismatched |
| --- | --- | --- | --- | --- | --- | --- |
| Allocator type | Sleeve-based HRP/inverse-vol | Same (no change in Path B Sprint 0–5) | REUSE_EXISTING | Layer 3 notebooks | Constructor not the target | Changing allocator confounds regime comparison |
| HRP / inverse-vol behavior | Standard HRP on sleeve returns | Same | REUSE_EXISTING | — | — | — |
| Volatility targeting | 52-week vol estimate | Same | MATCH | — | — | — |
| Max position caps | 35% per ETF | Same | MATCH | Config constant | — | — |
| BIL floor | Varies by state | State-specific in native | INTENTIONAL_DIFF | Risk budget module | Offense/defense by state | Controlled difference |
| Offense budget | Varies by state | State-specific in native | INTENTIONAL_DIFF | Risk budget module | — | — |
| Risk multipliers | State-specific in production | State-specific in native | INTENTIONAL_DIFF | Risk budget module | — | — |
| Transaction costs | 10 bps per half-round-trip | Same | MATCH | Global constant | Cannot change | Cost change invalidates G6 comparison |
| Slippage assumptions | Embedded in 10 bps | Same | MATCH | — | — | — |
| Turnover calculation | `sum(|w[t] - drift(w[t-1])|) / 2` | Same convention | REIMPLEMENT_IDENTICAL | Script 00 verifies on production artifact | — | Convention difference would invalidate G6 |
| Long-only constraint | All weights ≥ 0, sum to 1 | Same | MATCH | Hard constraint | — | — |
| No leverage | Sum of weights = 1 always | Same | MATCH | Hard constraint | — | — |

---

## G. Validation / Metrics

| Component | Production Behavior | Shadow Behavior | Status | Notes |
| --- | --- | --- | --- | --- |
| Annualization convention | × √52 for Sharpe/vol, × 52 for return | Same | MATCH | Critical |
| Sharpe calculation | `mean(r) / std(r) * sqrt(52)` | Same | REIMPLEMENT_IDENTICAL | — |
| Max drawdown | `min(wealth / cummax(wealth) - 1)` | Same | REIMPLEMENT_IDENTICAL | — |
| CVaR calculation | Mean of returns below 5th percentile | Same | REIMPLEMENT_IDENTICAL | — |
| Turnover calculation | `sum(abs(w[t] - drift)) / 2` per week | Same | REIMPLEMENT_IDENTICAL | — |
| Transaction cost deduction | `gross[t] - turnover[t] * 0.001` | Same | REIMPLEMENT_IDENTICAL | — |
| Holdout window | 2024-04-19 to 2026-04-10 (104 weeks) | Same dates | MATCH | Cannot change |
| Rolling 104-week evaluation | Rolling Sharpe over 104-week windows | Same | REIMPLEMENT_IDENTICAL | — |
| Phase D gates | All 9 gates from production gate set | Same | MATCH | — |
| Bootstrap method | Block bootstrap if implemented | Same method | REIMPLEMENT_IDENTICAL | — |

---

## H. Summary of Intentional Differences

The shadow rebuild is **allowed to differ from production only in these 6 areas**:

| # | Area | What Changes |
| --- | --- | --- |
| 1 | Native regime engine states | Adding NM sub-states (neutral_soft_landing etc.) |
| 2 | Macro/credit regime features | V3 proxy + credit trend as native regime inputs |
| 3 | State persistence / hysteresis | Minimum episode lengths, transition penalties |
| 4 | State-specific signal weighting | Walk-forward IC weighting within each state |
| 5 | State-specific risk budgets | Offense/defense/fragility parameters per state |
| 6 | Turnover-aware transition behavior | Re-risking rules that account for transition cost |

**Everything else must MATCH production.** If any other difference is discovered during Sprint 0.5,
it must be either corrected (bring to MATCH) or explicitly documented with a rationale and risk
assessment before Sprint 1 proceeds.

---

## I. Hard Stops

The following conditions trigger immediate stoppage of the shadow experiment:

1. Any lookahead bias discovered in the feature pipeline
2. Any hidden leverage (weights > 1 or sum > 1)
3. Any state or risk parameter optimized using holdout data
4. Any improvement that disappears at 2x transaction costs
5. Any result driven entirely by 2020 COVID shock or 2024-2025 AI rally
6. Any undocumented difference from production that is not listed in Section H
7. Any change to the cost convention, lag rules, or date index without explicit documentation
8. Any weakening of stressed_panic protection
9. Any state with fewer than 30 dev-period observations being used for weight calibration

---

*This document must be reviewed before Sprint 1 begins.*
*Any UNKNOWN or NEEDS_TEST item must be resolved by Sprint 0.5.*
