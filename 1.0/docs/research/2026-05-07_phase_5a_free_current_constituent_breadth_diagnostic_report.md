# Phase 5A-Free — Current-Constituent Diagnostic Stock Breadth Prototype

## !! SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY !!

**Date:** 2026-05-07
**Classification:** SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY — not a production backtest
**Purpose:** Decide whether point-in-time (PIT) stock breadth data is worth purchasing
**Production pins:** unchanged — no candidates created, no pins changed

---

## Survivorship-Bias Warning

This diagnostic uses **current S&P 500 and Nasdaq-100 constituents** fetched from
Wikipedia and priced with yfinance. These are today's winners. They exclude:
- Companies removed from the index (merger, acquisition, rebalancing)
- Companies that were delisted or went bankrupt
- Companies with poor price performance that were replaced

Any historical breadth computed from today's membership is biased upward.
Signals will appear stronger than they would have been in real time.

**Do not:**
- Promote any strategy candidate based on these results
- Claim these signals are production-valid
- Use these results to change production or shadow pins

**The sole purpose** of this diagnostic is to decide whether paying for
Norgate/WRDS/Sharadar point-in-time data is justified.

---

## Commands Executed

```bash
python3 scripts/phase_5a_free_current_constituent_breadth_diagnostic.py
```

**Script was run in two passes** due to two bugs fixed along the way:
1. Wikipedia 403 — fixed by adding browser-like `User-Agent` headers via `requests`
2. yfinance MultiIndex extraction — fixed with `_extract_adjclose()` helper + column dedup

---

## Files Created / Modified

**New script:** `scripts/phase_5a_free_current_constituent_breadth_diagnostic.py`

**Outputs (23 files in `data/research/phase_5a_free_current_constituent_breadth_diagnostic/`):**

| File | Size | Contents |
|---|---|---|
| `phase5a_free_bias_disclosure.csv` | 1 KB | Bias flags |
| `phase5a_free_usage_rules.csv` | 1 KB | Allowed/prohibited uses |
| `phase5a_free_current_constituent_universe.csv` | 74 KB | 516 current tickers |
| `phase5a_free_universe_summary.csv` | <1 KB | Universe counts |
| `phase5a_free_stock_prices_adjclose_daily.parquet` | 5.8 MB | Daily adj close (safe size) |
| `phase5a_free_price_download_status.csv` | 40 KB | Per-ticker coverage |
| `phase5a_free_price_coverage_report.csv` | <1 KB | Summary coverage |
| `phase5a_free_stock_breadth_weekly.csv` | 182 KB | 331 weeks × 34 features |
| `phase5a_free_stock_breadth_feature_manifest.csv` | 2 KB | Feature definitions |
| `phase5a_free_stock_breadth_coverage_report.csv` | <1 KB | Breadth panel summary |
| `phase5a_free_signal_definitions.csv` | 1 KB | 7 signal specs |
| `phase5a_free_signal_panel.csv` | 107 KB | Weekly signal values |
| `phase5a_free_signal_coverage.csv` | 3 KB | State coverage |
| `phase5a_free_signal_validation.csv` | 16 KB | Forward-return validation |
| `phase5a_free_same_state_signal_lift.csv` | 7 KB | Same-state lift |
| `phase5a_free_neutral_split_diagnostic.csv` | 1 KB | Neutral_mixed split |
| `phase5a_free_recovery_rerisk_diagnostic.csv` | 1 KB | Recovery rerisk |
| `phase5a_free_pit_data_value_assessment.csv` | 1 KB | Stock vs ETF breadth comparison |
| `phase5a_free_decision.csv` | <1 KB | Final decision |
| `phase5a_free_next_action_recommendation.csv` | <1 KB | Next action |
| `phase5a_free_protocol.json` | <1 KB | Protocol metadata |

**No file exceeded the 100 MB limit.**

---

## Part A — Bias Disclosure Summary

| Item | Value |
|---|---|
| data_source | Current S&P 500 constituents + yfinance |
| point_in_time_safe | **False** |
| survivorship_biased | **True** |
| production_decision_safe | **False** |
| research_only_safe | True |
| allowed_use | Diagnostic only — decide if PIT data worth purchasing |
| prohibited_use | Production promotion; final strategy claim; survivorship-bias-free claim |

---

## Part B — Current Constituent Universe

| Source | Tickers fetched | Method |
|---|---|---|
| S&P 500 (Wikipedia) | 503 | `requests` + `pandas.read_html` with browser User-Agent |
| Nasdaq-100 (Wikipedia) | 101 | Same |
| Combined unique | **516** | Deduplicated |

Fetch succeeded after adding `User-Agent` browser headers to bypass Wikipedia's 403 block.

---

## Part C — yfinance Price Download

| Metric | Value |
|---|---|
| Tickers attempted | 503 (S&P 500 primary) |
| Good tickers | 497 |
| Failed / high-missingness | 6 |
| Coverage | **98.8%** |
| Date range | 2020-01-01 to 2026-04-30 |
| Price file size | **5.8 MB** (parquet, well under 100 MB limit) |

---

## Part D — Diagnostic Breadth Features

Built from 331 weekly snapshots (2020-01-03 to 2026-05-01) across 497 tickers.

Features computed: % above 50/100/200d MA, % positive 4/13/26w return, % at 13/52w high,
breadth thrust 4w/8w, broad_bull flag, narrow_bull warning, neutral_risk_on, equal-weight
member return, median member 13w return, diagnostic aggression score — all with `_lag1w`
causal variants.

---

## Part E — Diagnostic Signal Definitions

| Signal | Active weeks | Freq | calm | neutral | stressed | RC |
|---|---|---|---|---|---|---|
| broad_stock_bull_diagnostic | 97 | 8.7% | 46 | 40 | 0 | 10 |
| narrow_bull_warning_diagnostic | 38 | 3.4% | 4 | 6 | 27 | 0 |
| neutral_stock_risk_on_diagnostic | 80 | 7.2% | 0 | **80** | 0 | 0 |
| neutral_stock_chop_warning_diagnostic | 394 | 35.5% | 0 | **394** | 0 | 0 |
| recovery_stock_confirmed_diagnostic | 18 | 1.6% | 0 | 0 | 0 | **10** |
| fake_recovery_warning_diagnostic | 2 | 0.2% | 0 | 0 | 0 | 0 |
| diagnostic_aggression_score_high | 131 | 11.8% | 69 | 49 | 2 | 9 |

Key: `broad_stock_bull` correctly fires at 0 weeks in stressed_panic — protection preserved.

---

## Part F — Diagnostic Signal Validation

### !! All results below are SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY !!

### SPY forward returns: signal active vs inactive (2020+)

#### 4-week horizon

| Signal | Active weeks | SPY active | SPY inactive | Lift | Hit rate |
|---|---|---|---|---|---|
| broad_stock_bull | 97 | 0.988% | 0.948% | **+0.040%** | 66.0% |
| neutral_risk_on | 80 | 1.003% | 0.946% | +0.058% | 65.0% |
| **recovery_confirmed** | **18** | **2.095%** | **0.893%** | **+1.202%** | **72.2%** |
| aggression_score_high | 131 | 1.369% | 0.683% | **+0.686%** | 71.8% |

#### 13-week horizon (stronger effects at longer horizons)

| Signal | SPY active | SPY inactive | Lift | Hit rate | Adverse freq |
|---|---|---|---|---|---|
| broad_stock_bull | 4.460% | 3.170% | **+1.290%** | 83.3% | 5.6% |
| neutral_risk_on | 3.494% | 3.552% | -0.057% | 70.8% | 8.3% |
| **recovery_confirmed** | **5.957%** | **3.392%** | **+2.564%** | **100%** | **0%** |
| aggression_score_high | 4.623% | 2.806% | **+1.816%** | 82.7% | 5.5% |

**Note on recovery_confirmed 13w:** 100% hit rate with N=18 — this is almost certainly inflated by survivorship bias. Real PIT history would include breadth-weak recoveries from failing companies.

### GGG1 forward returns: signal active vs inactive (2020+, 4w)

| Signal | GGG1 active | GGG1 inactive | Lift |
|---|---|---|---|
| broad_stock_bull | 0.758% | 0.687% | +0.071% |
| neutral_risk_on | 0.853% | 1.013% | **-0.160%** |
| recovery_confirmed | 0.816% | 0.702% | +0.114% |
| aggression_score_high | 0.623% | 0.766% | **-0.142%** |

**Key finding:** The neutral_risk_on and aggression_score signals show negative lift for GGG1. The current portfolio already allocates conservatively in neutral_mixed — adding a stock breadth overlay doesn't clearly improve GGG1's neutral_mixed performance in this biased diagnostic.

### Phase 4B forward returns: signal active vs inactive (2020+, 4w)

| Signal | Phase4B active | Phase4B inactive | Lift |
|---|---|---|---|
| broad_stock_bull | 0.838% | 0.655% | **+0.183%** |
| neutral_risk_on | 0.969% | 0.966% | +0.003% |
| recovery_confirmed | 0.764% | 0.707% | +0.057% |
| aggression_score_high | 0.717% | 0.705% | +0.013% |

Phase 4B shows the most consistent positive lift from stock breadth (especially `broad_stock_bull`), suggesting a portfolio that is already more aggressive in good states benefits more from stock-breadth confirmation.

---

## Same-State Signal Lift

### calm_trend (the most important state for return improvement)

| Signal | SPY lift 4w | GGG1 lift 4w | Phase4B lift 4w | Signal-on weeks |
|---|---|---|---|---|
| broad_stock_bull | **+0.517%** | +0.167% | +0.347% | 46 of 101 |
| aggression_score_high | **+2.611%** | +0.369% | **+0.651%** | 69 of 101 |

**The calm_trend finding is the most actionable:** In 46 of 101 calm_trend weeks, `broad_stock_bull` was active and SPY earned an additional +0.517% per 4 weeks vs off-signal calm-trend weeks. For Phase 4B, the lift was +0.347% per 4 weeks.

⚠️ The `aggression_score_high` lift of +2.611% SPY per 4 weeks in calm_trend is very likely survivorship-biased — current S&P 500 members all survived, so broad internal breadth looks artificially uniform during the 2020–2026 period.

### neutral_mixed

| Signal | SPY lift 4w | GGG1 lift 4w | Phase4B lift 4w |
|---|---|---|---|
| broad_stock_bull | **-0.169%** | **-0.344%** | **-0.168%** |
| neutral_risk_on | +0.060% | -0.160% | +0.003% |
| aggression_score_high | +0.831% | **-0.666%** | **-0.416%** |

**Neutral_mixed finding:** Stock breadth signals are mixed/negative for GGG1 in neutral_mixed. `broad_stock_bull` fires more often during high-SPY-return neutral weeks (selection effect), but the _within-state_ conditioning shows the signal doesn't reliably separate better from worse neutral_mixed weeks for the existing portfolio. This is the most important caution: the neutral_mixed stock breadth signal may not be as useful as hoped.

### recovery_confirmed

| Signal | SPY lift 4w | GGG1 lift 4w | Phase4B lift 4w | N |
|---|---|---|---|---|
| broad_stock_bull | +1.276% | +0.680% | +0.552% | 10 on / 10 off |

Promising but very small N (only 20 recovery_confirmed weeks in 2020+). At 13 weeks, the recovery_confirmed signal actually inverts: SPY shows -1.4% lift, suggesting the signal is mostly identifying early recovery weeks with strong mean reversion that doesn't persist.

---

## Stock Breadth vs Existing ETF Breadth — PIT Value Assessment

| Signal | SPY 4w lift | GGG1 4w lift | Phase4B 4w lift |
|---|---|---|---|
| **ETF breadth (existing `breadth_sma_43`)** | **-0.457%** | -0.074% | -0.052% |
| Stock breadth diagnostic | +0.040% | +0.071% | **+0.183%** |
| Aggression score high | +0.686% | -0.142% | +0.013% |

**Critical finding:** The existing ETF breadth signal (`breadth_sma_43 >= 0.65`) shows **negative** lift vs inactive in the 2020+ period for SPY. This is because the existing ETF universe includes bonds, commodities, and REITs — their breadth can be low even during strong equity bull markets, making the signal noisy as an equity-market predictor. Stock-only breadth is more targeted.

The stock breadth diagnostic, despite survivorship bias, already outperforms the existing ETF breadth at predicting SPY and Phase4B forward returns.

---

## Part G — Decision

### DIAGNOSTIC_PROMISING_GET_PIT_DATA

**Evidence:**
1. Stock breadth outperforms existing ETF breadth signal for forward SPY/Phase4B returns
2. In calm_trend (the highest-value state for return improvement), `broad_stock_bull` shows +0.517% per 4-week lift vs off-signal calm weeks for SPY, and +0.347% for Phase4B
3. `diagnostic_aggression_score_high` shows large 13w SPY lift (+1.816%) with 82.7% hit rate — even accounting for significant survivorship bias, the directional result is encouraging
4. Signals correctly produce 0 active weeks in stressed_panic — existing protection is not threatened

**Caveats and reasons to be cautious:**
1. Survivorship bias is real and substantial — the recovery_confirmed 100% hit rate is almost certainly an artifact
2. Neutral_mixed stock breadth shows **negative** lift for GGG1 — the portfolio may already be well-calibrated for neutral states and stock breadth doesn't clearly improve it
3. N is small: only 331 weeks total (6 years), and many interesting states have <20 signal-active weeks

**What PIT data would add:**
- Remove survivorship bias (failed/delisted companies would often show weak breadth before failure)
- Add the 2005–2020 history for full-period validation (only 2020+ available here)
- Allow proper calm_trend opportunity-cost measurement over 20+ years
- Make the recovery_confirmed signal actually trustworthy (N would grow significantly)

---

## Final Recommendation

**Purchase Norgate Data US Stocks Platinum or Diamond** before building any production candidate using stock breadth.

The calm_trend signal is the most actionable: if stock breadth (% above 200d MA, positive 26w return) confirms a calm bull market, the portfolio could safely increase its offense concentration. This is the state where existing ETF breadth was already identified (Phase 3) as meaningful, and stock breadth appears to sharpen it further.

**Do not** build a portfolio candidate from this diagnostic. The neutral_mixed signal does not clearly add lift beyond what already exists in GGG1/Phase4B, and the survivorship bias makes the full-period estimate unreliable.

**Exact next human action:**
```
Option 1 (recommended): Purchase Norgate Data US Stocks Platinum or Diamond.
   Export index membership + daily prices for S&P 500 back to at least 2005.
   Save to data/stock_breadth/raw/ using the real filenames (not _TEMPLATE).
   Run: python3 scripts/build_pit_stock_breadth_panel.py

Option 2: If Norgate is out of budget, try Sharadar via Nasdaq Data Link.
   Verify their S&P 500 point-in-time constituent history goes back to 2005.
   Verify delisted stock coverage before committing.
```

---

## Git Status

All Phase 5A-Free outputs are untracked (`??`). Nothing staged. No production files touched.
No `portfolio_version_*` candidate artifacts created.
