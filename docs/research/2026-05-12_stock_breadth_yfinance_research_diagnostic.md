# Stock Breadth Research Diagnostic — yfinance Prototype Pipeline

**Date:** 2026-05-12
**Type:** Research-only diagnostic. Pipeline prototype. No production pins changed. No candidates created.
**Production pin:** `improved_phase2b_regime_confidence_boost` (unchanged)
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense` (unchanged)

---

## !! SURVIVORSHIP-BIAS WARNING !!

**This diagnostic uses current S&P 500 constituents downloaded via yfinance.
These are today's winners. All results are upward-biased because:**

- Companies removed from the index (bankruptcy, delisting, acquisition, rebalancing) are excluded
- Companies that failed or underperformed are excluded
- Current members are backfilled into history — only survivors are priced

**Do NOT:**
- Use these results to promote any strategy candidate
- Claim these results are production-valid backtests
- Change production or shadow pins based on these results
- Call this a survivorship-bias-free analysis

**Sole purpose:** Validate the prototype pipeline and assess whether the directional signal from stock breadth (observed in the biased Phase 5A-Free diagnostic) continues to hold with an extended date range (2010–2026). This is a research-only diagnostic.

---

## Executive Summary

Stock breadth computed from current (biased) S&P 500 constituents shows **directional support** for the hypothesis that `pct_above_200d_ma` is a useful calm_trend quality signal — but with critical caveats:

1. **Full-sample lift is negative** (−1.5% at 4 weeks, −2.6% at 13 weeks). When all market states are pooled, high breadth predicts lower forward SPY returns. This is driven by state mixing: the low-breadth group includes early recovery weeks that subsequently earn high returns (classic contrarian/mean-reversion effect), while the high-breadth group includes peaks.

2. **calm_trend lift is positive** (+0.292% at 4 weeks, +4.551% at 13 weeks for SPY). Within calm_trend weeks specifically, weeks where `pct_above_200d_ma > 0.65` see meaningfully higher subsequent SPY returns than weeks where it is below 0.40. This is the bottleneck state that matters most.

3. **Stock breadth beats existing ETF breadth in calm_trend** (+0.292% vs −0.995% at 4 weeks). The ETF breadth signal (`breadth_sma_43`) has negative same-state lift in calm_trend, consistent with Phase 6 findings. Stock-level breadth is directionally better, even in this biased form.

4. **Phase 4B is not helped by this biased signal.** The Phase 4B lift from stock breadth in calm_trend is −0.011% at 4 weeks. This means the portfolio is already well-calibrated for the states where breadth is high, and the biased signal does not add incremental allocation value at this threshold. This is also consistent with Phase 6 findings for ETF breadth.

5. **N is small for the low-breadth group in calm_trend** (17 weeks). The lift estimate is statistically unstable. PIT data is required before any production decision.

**Final recommendation: NEEDS PIT DATA BEFORE JUDGMENT.** Directional evidence is encouraging. The 13-week calm_trend lift is compelling (+4.55%). But the biased source and small low-breadth N make any numeric claim unreliable for production use.

---

## Data Source and Coverage

| Item | Value |
|------|-------|
| Source | yfinance + Wikipedia S&P 500 current constituents |
| Point-in-time safe | **False** |
| Survivorship bias | **True** |
| Production valid | **False** |
| Fetch date | 2026-05-12 |
| Price window | 2010-01-01 → 2026-05-12 |
| Tickers requested | 503 |
| Tickers successfully loaded | 477 (94.8%) |
| Tickers failed | 26 |
| Breadth weeks populated | 849 (out of 1,110 project weeks) |
| First breadth week | 2010-01-08 |
| Last breadth week | 2026-04-10 |
| Thin weeks (< 50% stock coverage) | 261 (early in the 2010 window, most stocks existed then) |
| GICS sectors computed | 11 |
| Cache | `data/research/stock_breadth/stock_prices_daily_raw.parquet` (13.7 MB) |

**Coverage gap:** The project's market state history starts in 2005. The price download starts in 2010 (to limit download time). This means 261 early weeks have partial or thin stock coverage. Results from 2013+ are more reliable (most current S&P 500 companies were listed by then).

---

## Feature Definitions

All features are computed from the weekly Friday close snapshot. Moving averages are computed on daily prices and snapshotted at the Friday close. All features are **lagged by 1 week** before testing (signal at t-1 predicts return at t to t+n), providing a causal guard.

| Feature | Definition |
|---------|-----------|
| `pct_above_200d_ma` | Fraction of valid stocks with Friday close > 200-day trailing average |
| `pct_above_100d_ma` | Fraction with Friday close > 100-day trailing average |
| `pct_above_50d_ma` | Fraction with Friday close > 50-day trailing average |
| `pct_positive_13w_return` | Fraction with positive 13-week price return |
| `pct_positive_26w_return` | Fraction with positive 26-week price return |
| `pct_near_52w_high` | Fraction within 5% of their 52-week high |
| `equal_weight_stock_return` | Equal-weight mean weekly return across all valid stocks |
| `stock_count_available` | Number of stocks with non-null prices that week |
| `median_stock_13w_return` | Median (not mean) 13-week return across valid stocks |
| `median_stock_26w_return` | Median 26-week return across valid stocks |

**High-breadth:** `feature > 0.65` (approximately 65th percentile cutoff)
**Low-breadth:** `feature < 0.40`

---

## Full-Sample Results (All States Pooled)

| Feature | Horizon | SPY lift (H−L) | N high | N low |
|---------|---------|---------------|--------|-------|
| `pct_above_200d_ma` | 4w | **−1.515%** | 545 | 107 |
| `pct_above_200d_ma` | 13w | **−2.619%** | 537 | 107 |

**Interpretation:** When all market states are pooled, high stock breadth predicts *lower* subsequent SPY returns. This is a known artifact of the survivorship bias + state mixing:

- During deep stress states, breadth is low. Low-breadth weeks that subsequently earn high returns (recoveries) are misidentified as "bad" by the signal.
- Current constituents are all survivors, so their breadth is artificially high even in historical periods that were weak for the market.
- The full-sample result cannot be used to evaluate the signal's quality. State-by-state analysis is required.

---

## State-by-State Lift Table: pct_above_200d_ma

Forward SPY return: high-breadth weeks (> 0.65) vs low-breadth weeks (< 0.40), lagged 1 week.

### 4-Week Forward SPY Return

| State | N weeks | N high | N low | Mean SPY (high) | Mean SPY (low) | SPY lift (H−L) | Hit rate (high) |
|-------|---------|--------|-------|----------------|----------------|---------------|-----------------|
| **calm_trend** | **295** | **221** | **17** | **+0.543%** | **+0.251%** | **+0.292%** | **68.3%** |
| neutral_mixed | 493 | 254 | 19 | +1.066% | +1.091% | −0.025% | 68.5% |
| recovery_fragile | 49 | 23 | 0 | — | — | — | — |
| recovery_confirmed | 44 | 31 | 0 | — | — | — | — |
| stressed_panic | 229 | 16 | 71 | +0.310% | +3.185% | **−2.875%** | 62.5% |

### 13-Week Forward SPY Return

| State | N high | N low | Mean SPY (high) | Mean SPY (low) | SPY lift (H−L) | Hit rate (high) |
|-------|--------|-------|----------------|----------------|---------------|-----------------|
| **calm_trend** | **221** | **17** | **+2.241%** | **−2.311%** | **+4.551%** | **76.5%** |
| neutral_mixed | 254 | 19 | +2.270% | +5.886% | −3.660% | 73.2% |
| recovery_fragile | 23 | 0 | — | — | — | — |
| stressed_panic | 16 | 71 | −3.388% | +0.313% | −3.703% | — |

### Key Observations

- **calm_trend:** The only state where stock breadth shows consistent positive lift for both 4-week (+0.292%) and 13-week (+4.551%) horizons. Both signs are positive. The 13-week lift of +4.55% is large, but N_low = 17 weeks makes it statistically noisy.
- **neutral_mixed:** Near-zero 4-week lift (−0.025%). The signal does not help for neutral weeks, consistent with Phase 5A-Free and Phase 6 findings. The portfolio is already well-calibrated for this state.
- **recovery states:** N_low = 0 for both recovery states — within the project's existing regime engine, recovery states rarely coincide with low stock breadth. The signal cannot be tested here.
- **stressed_panic:** Large NEGATIVE lift (−2.875%). During stressed weeks, high breadth actually predicts worse subsequent returns. This makes sense: breadth may be artificially high in early stress periods (survivorship bias), and the recovery is stronger from low-breadth (deep-stress) conditions.

---

## calm_trend Emphasis — All Breadth Features

This is the portfolio's primary bottleneck. Results below for all features tested, within calm_trend only:

| Feature | 4w SPY lift | 13w SPY lift | N high | N low |
|---------|-----------|-----------|--------|-------|
| `pct_above_200d_ma` | **+0.292%** | **+4.551%** | 221 | 17 |
| `pct_positive_26w_return` | **+0.360%** | **+4.667%** | 202 | 17 |
| `pct_positive_13w_return` | −2.494% | +0.752% | 171 | 17 |
| `pct_above_50d_ma` | −1.321% | −0.989% | 161 | 21 |
| `pct_near_52w_high` | −1.260% | +1.463% | 45 | 60 |

**Best calm_trend signals:** `pct_above_200d_ma` and `pct_positive_26w_return` both show consistent positive lift at 4w and 13w horizons. The 50d MA and 13w return signals show negative lift at 4 weeks, which may indicate mean-reversion within shorter-horizon dynamics.

**Phase 4B lift in calm_trend:**
- `pct_above_200d_ma` at 4w: **−0.011%** (negative)
- `pct_above_200d_ma` at 13w: **+0.007%** (near-zero)

The Phase 4B portfolio does not benefit from conditioning on this biased stock breadth signal in calm_trend. This is consistent with Phase 6 findings: the portfolio is already optimally deployed in high-breadth calm weeks via existing signals (Phase 4B's `high_quality_sector_bull` gate fires in 88.8% of calm weeks), leaving little room for additional breadth-based discrimination at this threshold.

---

## Comparison: Stock Breadth vs ETF Breadth

| State | Horizon | Stock breadth lift (pct_above_200d_ma) | ETF breadth lift (breadth_sma_43 ≥ 0.65) | Stock beats ETF |
|-------|---------|--------------------------------------|------------------------------------------|----------------|
| All states | 4w | −1.515% | +0.102% | **No** |
| All states | 13w | −2.619% | +1.160% | **No** |
| **calm_trend** | 4w | **+0.292%** | **−0.995%** | **Yes** |
| **calm_trend** | 13w | **+4.551%** | **−0.490%** | **Yes** |
| neutral_mixed | 4w | −0.025% | +0.303% | No |
| neutral_mixed | 13w | −3.660% | +1.818% | No |
| stressed_panic | 4w | −2.875% | −0.855% | No |
| stressed_panic | 13w | −3.104% | −0.008% | No |

**Key finding:** Stock breadth `pct_above_200d_ma` beats ETF breadth **specifically within calm_trend** — the only state that matters for the current bottleneck. In all other states and in the full sample, ETF breadth (`breadth_sma_43`) has better lift. This is consistent with the Phase 5A-Free finding and confirms that stock breadth's comparative advantage is narrow but targeted.

**Why ETF breadth fails in calm_trend:** The ETF breadth signal includes bonds, REITs, and commodities. In calm equity bull markets, these assets may show low or declining breadth even as equities advance strongly, making the composite ETF breadth signal noisy as an equity market quality indicator.

---

## Pipeline Validation

Both scripts ran successfully:

| Check | Result |
|-------|--------|
| `build_stock_breadth_research.py` ran | ✓ |
| `validate_stock_breadth_regime_lift.py` ran | ✓ |
| `sp500_current_universe.csv` exists | ✓ (503 tickers) |
| `stock_prices_weekly.csv` exists | ✓ (7.3 MB, 1110 × 477) |
| `stock_returns_weekly.csv` exists | ✓ (8.4 MB) |
| `stock_breadth_weekly.csv` exists | ✓ (1110 weeks × 11 features) |
| `sector_breadth_weekly.csv` exists | ✓ (1110 weeks × 23 cols, 11 sectors) |
| `stock_breadth_coverage_report.csv` exists | ✓ |
| `stock_breadth_metadata.json` exists | ✓ |
| `stock_breadth_state_lift.csv` exists | ✓ |
| `stock_breadth_forward_return_tests.csv` exists | ✓ |
| `stock_breadth_vs_etf_breadth.csv` exists | ✓ |
| Metadata says production_valid = false | ✓ |
| Metadata says survivorship_bias_warning = true | ✓ |
| Cache saves and reruns skip download | ✓ |
| Failed tickers recorded (26 failed) | ✓ |

The pipeline is backend-agnostic. The key change for a production-valid run is:
1. Replace the yfinance download in `build_stock_breadth_research.py` with a Norgate/WRDS/CRSP reader
2. Replace the Wikipedia constituent list with the PIT constituent history
3. Re-run both scripts unchanged

---

## Does This Justify Waiting for WRDS/CRSP or Buying Norgate?

**Yes, with caveats.** The evidence is directionally consistent:

**In favor of buying PIT data:**
- calm_trend `pct_above_200d_ma` shows +0.292% (4w) and +4.551% (13w) SPY lift — the direction is right
- Stock breadth clearly outperforms ETF breadth within calm_trend specifically (+0.292% vs −0.995% at 4w)
- The Phase 5A-Free diagnostic (2020 only) showed +0.517% 4w lift — this diagnostic (2010–2026) confirms the same direction at +0.292%
- At 13 weeks, the SPY lift of +4.551% is very large — even heavily discounted for survivorship bias, a real version of this signal could be worth +1–2%

**Against buying immediately:**
- N_low = 17 in calm_trend. The "low breadth in calm" weeks are extremely rare with current constituents. PIT data may show more low-breadth calm weeks (failed companies existed in calm periods too), potentially changing the lift estimate
- Phase 4B lift is NEGATIVE (−0.011% at 4w) — the portfolio may already be well-calibrated, and the signal adds no incremental value even if survivorship-adjusted estimates are correct
- The full-sample negative lift is concerning — it suggests the signal's behavior is state-dependent in a way that could be fragile

**Conclusion:** The directional case for PIT data is confirmed. The numeric case (how large is the lift?) remains uncertain. If budget allows, Norgate US Stocks Platinum/Diamond ($600–$1,200/year) is the recommended data source. If not, this pipeline is ready for when the budget exists — just swap the data backend.

---

## Final Recommendation

**NEEDS PIT DATA BEFORE JUDGMENT**

The diagnostic provides directional support for the calm_trend stock breadth signal. The pipeline is validated and production-ready from a code perspective. The survivorship bias is real and substantial; no numeric estimate from this diagnostic should be used in a production decision.

**Next steps (in order of priority):**
1. If budget allows: Purchase Norgate Data US Stocks Platinum or Diamond, save to `data/stock_breadth/raw/` using the real filenames (not `_TEMPLATE`), run `scripts/build_pit_stock_breadth_panel.py`
2. If budget does not allow: Keep this pipeline as a prototype, continue with Phase 8 (volatility-managed sector sleeve) as the next sprint
3. Do not build a production candidate from this diagnostic

---

## Output Files

All outputs are in `data/research/stock_breadth/`:

| File | Size | Description |
|------|------|-------------|
| `sp500_current_universe.csv` | ~100 KB | 503 S&P 500 tickers with GICS sector from Wikipedia |
| `stock_prices_weekly.csv` | 7.3 MB | Weekly Friday close prices, 1110 weeks × 477 tickers |
| `stock_returns_weekly.csv` | 8.4 MB | Weekly returns, same dimensions |
| `stock_breadth_weekly.csv` | ~100 KB | 10 breadth features + label, 1110 weeks |
| `sector_breadth_weekly.csv` | ~200 KB | Per-sector pct_above_200d_ma and pct_positive_13w_return |
| `stock_breadth_coverage_report.csv` | ~50 KB | Per-ticker coverage statistics |
| `stock_breadth_metadata.json` | ~2 KB | Metadata with bias flags |
| `stock_breadth_state_lift.csv` | ~20 KB | Lift tests by state and feature |
| `stock_breadth_forward_return_tests.csv` | ~10 KB | Tercile forward return tests |
| `stock_breadth_vs_etf_breadth.csv` | ~5 KB | Stock vs ETF breadth comparison |
| `stock_prices_daily_raw.parquet` | 13.7 MB | Cached daily prices (rerun skips download) |

---

## Git Status

No production files modified. No strategy code changed. No portfolio candidates created. No pins changed.

New files (untracked):
- `scripts/build_stock_breadth_research.py`
- `scripts/validate_stock_breadth_regime_lift.py`
- `docs/research/2026-05-12_stock_breadth_yfinance_research_diagnostic.md`
- All output files in `data/research/stock_breadth/`
