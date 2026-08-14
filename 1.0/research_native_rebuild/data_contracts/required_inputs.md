# Path B — Required Input Files

**Sprint 0 — 2026-06-07**
**All files listed here are READ-ONLY for the shadow rebuild.**
**No script in `research_native_rebuild/` may write to any of these paths.**

---

## Availability Status Key

- `VERIFIED` — file confirmed present and loadable
- `EXPECTED` — expected at this path; not yet confirmed in Sprint 0
- `EMPTY` — file exists but has no usable data (known issue)
- `DERIVED` — path is a directory; specific artifact selected at runtime

---

## 1. Weekly Price Data

| File | Path | Columns | Rows | Status | Notes |
|------|------|---------|------|--------|-------|
| Weekly ETF prices | `data/01_data_hub/weekly_prices.csv` | DatetimeIndex + 35 ETF tickers | 1110 | EXPECTED | Index: Fridays 2005-01-07 to 2026-04-10; Yahoo Finance adjusted close |
| Benchmark returns | `data/01_data_hub/benchmark_returns_weekly.csv` | date, SPY, AGG | 1110 | EXPECTED | Weekly returns for SPY and AGG |

**Loading convention:**
```python
prices = pd.read_csv(path, index_col=0, parse_dates=True)
returns = prices.pct_change().dropna()
```

**Critical timing note:** All return calculations must use `pct_change()`. The execution delay is implemented as `gross[t] = w[t] @ etf_rets[t+1]`, which requires the forward return at t+1 for weights set at t.

---

## 2. Macro / Sentiment Data

| File | Path | Columns | Status | Notes |
|------|------|---------|--------|-------|
| FRED macro (weekly) | `data/01_data_hub/macro_weekly.csv` | date + FRED series | EMPTY | NFCI 504 timeout; 3 sprints failed; V3 proxy used instead |
| VIX term structure | `data/01_data_hub/vix_term_structure.csv` | date, vix_spot, vix_3m, vix_6m, slope_1m3m, slope_1m6m, contango_flag, stress_flag | EXPECTED | 1-week causal lag already applied to tradable columns |
| Google Trends fear | `data/01_data_hub/google_trends.csv` | date, recession, crash, inflation, bear_market, fear_composite, fear_composite_z | EXPECTED | 1-week causal lag already applied to tradable columns |

---

## 3. Production Regime Engine Artifacts

| File | Path | Key Columns | Status | Notes |
|------|------|------------|--------|-------|
| Market state history | `data/04_layer2b_risk_regime_engine/market_state_history.csv` | date, market_state, market_drawdown, market_trend_positive, breadth_sma_43, breadth_26w_mom, breadth_13w_mom, breadth_change_4w, canary_breadth_default, canary_breadth_pair, recent_stress_26w, avg_corr_risk_off_z, google_fear_z_tradable, transition_persistence_prob, transition_good_state_prob, transition_non_stress_prob | EXPECTED | Source of production state labels; 1-week causal lag on tradable columns |
| Regime score | `data/04_layer2b_risk_regime_engine/regime_score.csv` | date, market_vol_risk_off_z, market_drawdown_risk_off_z, breadth_risk_off_z, avg_corr_risk_off_z, macro_risk_score_tradable, vix_level_z_tradable, vix_slope_risk_off_z_tradable, google_fear_z_tradable, risk_regime_score, risk_state, signal_environment | EXPECTED | Tradable columns have 1-week causal lag; source of regime score inputs |

**Required columns for Script 01 (feature panel):**
- `market_state` — production regime label (for equivalence checks)
- `breadth_sma_43`, `breadth_26w_mom`, `breadth_13w_mom`, `breadth_change_4w` — breadth features
- `avg_corr_risk_off_z` — cross-asset correlation z-score
- `vix_level_z_tradable` — VIX level (1-week lagged)
- `google_fear_z_tradable` — Google fear composite (1-week lagged)
- `recent_stress_26w` — recent stressed_panic episode indicator
- `transition_persistence_prob`, `transition_good_state_prob`, `transition_non_stress_prob`

---

## 4. Layer 1 Alpha Signals

All signals are **REUSE_EXISTING** — shadow reads these files directly with no re-implementation.
All signals must be used with causal 1-week lag applied at the feature panel stage.

| Signal | File | Status |
|--------|------|--------|
| Cross-sectional momentum | `data/02_layer1_signals/signal_xsmom.csv` | EXPECTED |
| Time-series momentum | `data/02_layer1_signals/signal_tsmom.csv` | EXPECTED |
| Multi-horizon momentum | `data/02_layer1_signals/signal_multi_horizon_mom.csv` | EXPECTED |
| Reversal | `data/02_layer1_signals/signal_reversal.csv` | EXPECTED |
| Quality | `data/02_layer1_signals/signal_quality.csv` | EXPECTED |
| Carry | `data/02_layer1_signals/signal_carry.csv` | EXPECTED |
| Value | `data/02_layer1_signals/signal_value.csv` | EXPECTED |
| Trend quality | `data/02_layer1_signals/signal_trend_quality.csv` | EXPECTED |
| Breadth confirmation | `data/02_layer1_signals/signal_breadth_confirmation.csv` | EXPECTED |
| Credit spread | `data/02_layer1_signals/signal_r2_credit_spread.csv` | EXPECTED |
| VIX term structure | `data/02_layer1_signals/signal_r2_vix_term_structure.csv` | EXPECTED |
| Financial conditions | `data/02_layer1_signals/signal_r2_financial_conditions.csv` | EXPECTED |
| State-conditional IC | `data/02_layer1_signals/signal_state_conditional_ic.csv` | EXPECTED |
| HYG/LQD pair | `data/02_layer1_signals/signal_r4_pair_hyg_lqd.csv` | EXPECTED |
| Dollar strength (blended) | `data/02_layer1_signals/signal_bm_dollar_strength_blended.csv` | EXPECTED |

---

## 5. V3 Macro States

| File | Path | Key Columns | Status | Notes |
|------|------|------------|--------|-------|
| V3 macro state labels | `outputs/experiment_results/macro_regime_classifier_v3/macro_states_weekly_v3.csv` | date, growth_factor, inflation_policy_factor, fc_proxy, macro_state (expansion/slowdown/overheating/stress), fc_benign | EXPECTED | 1-week causal lag already applied; validated in Steps 2B and 2C |

**V3 column names (actual in file):**
- `financial_conditions_proxy` — FC composite (VIX z + HYG/LQD z + SPY_drawdown z + avg_corr z)
- `fc_benign` — derived: `financial_conditions_proxy < 0` (661/1110 weeks are benign)
- `growth_factor` — PCA of PAYEMS, INDPRO, RSAFS, UNRATE, ICSA
- `macro_state` — quadrant label: expansion / slowdown / overheating / stress

**V3 macro state definitions:**
- `expansion`: growth_factor ≥ 0 AND financial_conditions_proxy ≤ 0
- `slowdown`: growth_factor < 0 AND financial_conditions_proxy ≤ 0 (FC_benign)
- `overheating`: growth_factor ≥ 0 AND financial_conditions_proxy > 0
- `stress`: growth_factor < 0 AND financial_conditions_proxy > 0

**Signal E_4wk (reference from Step 2C best candidate):**
- Active when: `neutral_mixed AND slowdown AND fc_benign AND credit_improving`
- `credit_improving`: HYG/LQD rolling 4-week momentum > 0
- `fc_benign`: `financial_conditions_proxy < 0`
- 4-week rolling majority confirmation of above

---

## 6. Production Portfolio Artifacts

Used **only** for equivalence comparison in Sprint 0.5 and Sprint 6.
**Do not use holdout-period production weights for any calibration.**

| File | Path | Status | Notes |
|------|------|--------|-------|
| Production portfolio weights | `data/05_layer3_portfolio_construction/portfolio_version_*_improved_frontier_phase5_fragility_guard.csv` | EXPECTED | For turnover and metric equivalence check only |

---

## 7. Missing / Unavailable Inputs

| Input | Why Missing | Workaround |
|-------|------------|------------|
| FRED NFCI | 504 timeout; all 3 V1/V2 attempts failed | V3 fc_proxy (VIX + HYG + SPY_drawdown + avg_corr) |
| PIT stock breadth data (Norgate) | ~$100/month subscription; not available | Standard breadth indicators from market_state_history |
| Intraday execution data | Not needed for weekly system | Not applicable |
| Options market data | Not in current architecture | Not applicable |

---

## 8. Timing / Lag Requirements

All inputs to Script 01 (feature panel) must be verified to have 1-week causal lag applied.
Tradable columns in `regime_score.csv` and `market_state_history.csv` already have this applied.
V3 macro states must also be applied with 1-week lag before use as regime features.

**Verification in Sprint 0.5:** Script 00 checks that production regime scores used in backtests
align with the 1-week-lagged convention. Any feature that appears un-lagged triggers HS1 (hard stop).
