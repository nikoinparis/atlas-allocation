# External Research — Part D: Prioritized Idea Backlog

**Date:** 2026-05-12
**Type:** Research/analysis only. No strategy changes.

---

## Evaluation Framework

Each idea is rated on:
- **Bottleneck targeted** — which confirmed bottleneck it addresses
- **Expected benefit** — honest estimate of incremental return/Sharpe improvement
- **Can test now** — whether existing data and code are sufficient
- **PIT stock data required** — whether Norgate/WRDS is needed
- **Overfitting risk** — given existing data volume (1,110 weekly observations; 295 calm weeks)
- **Resume-friendly** — whether the idea reads well to a quant interviewer

---

## Category 1: Can Test Now With Existing Data

---

### Idea 1.1 — Volatility-Scaled Sector Sleeve

**Name:** Volatility-managed sector sleeve
**Description:** Scale the sector sleeve budget by the inverse of its own realized volatility over the past 13 or 26 weeks. When the sleeve has been choppy, reduce its budget; when smooth, allow the full budget. Inspired by Barroso-Santa-Clara (2015) and Moreira-Muir (2017).
**Bottleneck targeted:** Sharpe-return tradeoff; sector sleeve performance in calm_trend and neutral_mixed
**Expected benefit:** Reduce max drawdown by 0.5–1.5% while preserving most of the return improvement. Estimated Sharpe improvement: +0.01–0.03 vs Phase 4B best.
**Why it might work:** When the sector sleeve has high recent realized vol, adding more of it increases portfolio vol disproportionately. Scaling back mechanically reduces the vol contribution without removing the alpha source.
**Why it might fail:** The sector sleeve's realized vol may be insufficiently forecastable at weekly frequency. Scaling back may reduce exposure exactly when sector leadership is rotating, costing return.
**Required data:** Existing sector ETF returns history.
**Implementation complexity:** Low (1–2 day sprint). Add a `sector_vol_scalar = target_vol / realized_vol` multiplier to the sector sleeve budget capped between 0.5 and 1.5.
**Validation method:** Full-period and holdout comparison vs Phase 4B best. Check: does Sharpe improve at constant return, or does return fall?
**Overfitting risk:** Low. Single parameter (target vol level); motivated by published literature.
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Yes — "volatility-managed sector sleeve inspired by Moreira-Muir (2017)."
**Recommended priority:** #1 — High. Best combination of literature support, low code complexity, direct bottleneck targeting, and low overfitting risk.

---

### Idea 1.2 — Continuous Canary Count for BIL Budget

**Name:** Continuous canary score for BIL reduction
**Description:** Replace the binary `canary_breadth_default` signal with a continuous 0–4 canary asset count (SPY, EEM, AGG, HYG or similar). When all 4 are above their trend: full offense. When 3 are positive: 90% offense. When 2: 75%. When 1 or 0: defensive. Inspired by Keller-Keuning DAA (2018).
**Bottleneck targeted:** BIL drag during near-good-state weeks; neutral_mixed return improvement
**Expected benefit:** Reduce average BIL by 1–3 pp in weeks where 3 of 4 canaries are positive but current binary signal fires. Estimated return improvement: +0.02–0.05 pp.
**Why it might work:** The existing binary canary fires when any single canary is negative, which may be too conservative in weeks where 3 of 4 canaries are strongly positive.
**Why it might fail:** The binary canary's protective behavior may be necessary — even one weak canary can signal a turning point. Relaxing the threshold may allow offensive allocation into early-decline weeks.
**Required data:** Existing canary ETF prices (already available as features).
**Implementation complexity:** Low. Modify the canary feature computation from binary to 0/4 count; wire into BIL budget as a continuous scalar.
**Validation method:** Compare vs Phase 4B best in stress windows (does 2022 protection hold?) and full period.
**Overfitting risk:** Low. Simple counting rule, no fitted parameters.
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Moderate.
**Recommended priority:** #2 — High.

---

### Idea 1.3 — Absolute Momentum Check for Sector Activation

**Name:** Absolute momentum gate on sector sleeve
**Description:** Only activate the sector sleeve when the top-ranked sector ETF also has positive absolute momentum vs BIL (i.e., the sector's 12-month return is positive vs T-bills). Inspired by Antonacci dual momentum (2012).
**Bottleneck targeted:** Sector sleeve quality in declining neutral periods; reducing false-positive sector activations
**Expected benefit:** Reduce sector exposure during early bear markets when relative momentum ranking still shows a sector "leader" but absolute momentum is already negative. Estimated: −0.5 pp max drawdown improvement; Sharpe +0.01–0.02.
**Why it might work:** Cross-sectional ranking can identify the "best of bad" sectors during early market decline. Absolute momentum check prevents deployment into genuinely negative trend sectors.
**Why it might fail:** Absolute momentum filter may delay sector re-entry during recoveries, costing recovery_confirmed capture. Overlaps with existing state gating (sector already blocked in stressed_panic).
**Required data:** Existing ETF price history.
**Implementation complexity:** Low.
**Validation method:** Compare sector_active_delta vs Phase 4B; check 2022 bear protection.
**Overfitting risk:** Low. Published dual momentum strategy.
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Yes — "dual momentum sector gate inspired by Antonacci (2012)."
**Recommended priority:** #3 — High.

---

### Idea 1.4 — Transition Probability Multiplier on Sector Sleeve

**Name:** Regime transition probability scalar for offense
**Description:** Use the existing `transition_good_state_prob` feature as a continuous multiplier on the sector sleeve budget within calm_trend and neutral_mixed. Higher probability of staying in a good state → higher sector allocation. Inspired by Ang-Bekaert (2004) regime-conditional allocation.
**Bottleneck targeted:** Calm_trend sub-classification; BIL drag in high-confidence calm weeks
**Expected benefit:** Modest. `transition_good_state_prob` is already in use as a classifier feature (Phase 6 showed it rarely fires above 0.60 in neutral). In calm_trend, it may have more variation. Estimated: +0.01–0.03 pp.
**Why it might work:** In weeks where the regime engine is highly confident of staying in a good state, it is rational to deploy more offense. The feature is already computed and causal.
**Why it might fail:** Phase 6 showed that `transition_good_state_prob` has limited range in neutral_mixed (max 0.205). In calm_trend, the range may be wider, but still uncertain. May add complexity without meaningful signal.
**Required data:** Existing `market_state_history.csv` features.
**Implementation complexity:** Low (1 day).
**Validation method:** Compare vs Phase 4B best in calm_trend state specifically.
**Overfitting risk:** Low.
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Moderate.
**Recommended priority:** #4 — Medium.

---

### Idea 1.5 — Ensemble Allocator Across Phase 4B / Phase 6 / Phase 7

**Name:** Shadow ensemble allocator
**Description:** At each week, take a weighted average of Phase 4B, Phase 6, and Phase 7 stretch allocations (e.g., 50% Phase 4B + 30% Phase 6 + 20% Phase 7). The ensemble should split the return-Sharpe tradeoff between best Sharpe (Phase 4B) and best return (Phase 7).
**Bottleneck targeted:** Sharpe-return tradeoff
**Expected benefit:** Return roughly midway between Phase 4B (7.76%) and Phase 7 stretch (7.88%), with Sharpe between 0.926 and 0.959. May not be clearly superior to Phase 4B best.
**Why it might work:** Averaging reduces the concentration risk of any single candidate's allocation decisions. If Phase 7 adds value only in recovery states, the ensemble captures that value while Phase 4B anchors the Sharpe.
**Why it might fail:** The candidates overlap heavily (Phase 6 and 7 are built from Phase 4B base). Averaging redundant signals rarely provides true diversification. May just produce a weighted average return without Sharpe improvement.
**Required data:** Existing portfolio weights for all three candidates.
**Implementation complexity:** Low (2 hours).
**Validation method:** Full-period and holdout vs Phase 4B best; bootstrap Sharpe comparison.
**Overfitting risk:** Medium (ensemble weights are an additional free parameter).
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Moderate ("ensemble of shadow candidates").
**Recommended priority:** #5 — Medium. Low expected incremental value but very low cost to test.

---

### Idea 1.6 — Covariance Shrinkage (Ledoit-Wolf) for Sector HRP

**Name:** Ledoit-Wolf shrinkage for sector covariance
**Description:** Replace the raw covariance matrix used in HRP for the sector sleeve with a Ledoit-Wolf shrinkage estimator. With only 11 sector ETFs, the 11×11 covariance matrix is estimated from noisy weekly data. Shrinkage reduces estimation error and improves HRP stability.
**Bottleneck targeted:** Construction quality; sector sleeve stability
**Expected benefit:** Reduce turnover in the sector sleeve (currently 5–16% per week). Estimated: turnover reduction of 10–20%; Sharpe improvement unclear but stability improvement likely.
**Why it might work:** HRP with raw covariance can produce unstable weights when the covariance matrix is noisy (as it is with N=11 assets and only ~100 active weeks per state).
**Why it might fail:** HRP already uses a hierarchical structure that is more robust than MVO. Ledoit-Wolf may not add much on top.
**Required data:** Existing ETF return history.
**Implementation complexity:** Low (sklearn LedoitWolf estimator is available).
**Validation method:** Compare turnover and Sharpe vs Phase 4B best.
**Overfitting risk:** Low.
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Yes — demonstrates quantitative sophistication.
**Recommended priority:** #6 — Medium.

---

## Category 2: Small Code Changes With Meaningful Impact

---

### Idea 2.1 — Trend Quality Score for Sector Admission

**Name:** Trend quality filter for sector sleeve
**Description:** Only admit a sector ETF into the active sleeve if it passes a trend quality check: the sector's price above its 52-week MA AND the 26-week momentum is positive AND the R-squared of its return trend over 26 weeks is above a threshold. Inspired by Phase A's `trend_clarity_momentum` signal.
**Bottleneck targeted:** Sector sleeve quality in calm_trend and neutral_mixed; reducing "junk sector" admission
**Expected benefit:** Remove sectors with noisy or declining trends from the sleeve, even if they rank highly in relative momentum. Estimated: +0.01–0.03 pp Sharpe; -0.01–0.02 pp return.
**Why it might work:** Relative momentum ranking can elevate sectors that are merely declining less than others. Adding a trend quality filter removes these false leaders.
**Why it might fail:** With only 11 sectors, applying strict quality filters may leave too few sectors active, concentrating the sleeve.
**Required data:** Existing sector ETF price history.
**Implementation complexity:** Low–Medium (2 days).
**Overfitting risk:** Medium (R-squared threshold is a fitted parameter).
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Yes.
**Recommended priority:** #7 — Medium.

---

### Idea 2.2 — Portfolio Objective Rewrite v2 (Return-Targeting within Budget)

**Name:** Target-return allocator in calm_trend
**Description:** Replace the HRP objective within the offensive budget in calm_trend states with a return-targeting approach: maximize expected return subject to max risk budget and drawdown constraints. Use trailing 26-week returns as expected return estimates.
**Bottleneck targeted:** calm_trend return; BIL drag in confirmed good states
**Expected benefit:** Uncertain. Phase 7 already tested aggressive expression within HRP (shift_budget=0.12) and improved return slightly at Sharpe cost. A true target-return objective may go further.
**Why it might work:** HRP by design is a diversification-focused allocator; it does not explicitly seek return. In confirmed good states, a return-seeking objective with guardrails may capture more of the available alpha.
**Why it might fail:** Expected return estimation from trailing returns is noisy and mean-reverting. The target-return allocator may rotate into past winners (sectors that just had high returns) at exactly the wrong time.
**Required data:** Existing ETF return history.
**Implementation complexity:** Medium (2–3 day sprint).
**Overfitting risk:** High (trailing returns as expected returns is unstable).
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Yes — demonstrates understanding of allocation objectives.
**Recommended priority:** #8 — Medium. High overfitting risk limits expected value.

---

## Category 3: Requires Better Data Later

---

### Idea 3.1 — PIT Stock Breadth Full Production Signal (Phase 5B)

**Name:** PIT stock breadth for calm_trend and recovery classification
**Description:** Use point-in-time S&P 500 constituent history (Norgate Platinum/Diamond or WRDS/CRSP) with daily adjusted prices back to 2005. Compute % above 200d MA, % positive 13w/26w return, breadth thrust signals at weekly frequency. Use as an additional classifier feature for calm_trend and recovery_confirmed.
**Bottleneck targeted:** Primary bottleneck. The main data gap.
**Expected benefit:** +0.12–0.30 pp full-period return (enough to close the 8.0% target). The Phase 5A-Free diagnostic showed +0.347% per 4-week Phase 4B lift in calm_trend. With 295 calm weeks, sustained improvement of even 0.10% per 4 weeks = +0.65 pp annualized in that state alone.
**Why it might work:** Stock breadth is the economically correct signal for distinguishing high-quality bull markets. When most stocks are above their 200d MA, the market's advance is broad-based and more durable. The Phase 5A-Free biased diagnostic confirmed the directional effect.
**Why it might fail:** Survivorship bias was substantial in the Phase 5A-Free diagnostic. PIT data may show weaker effects than the biased estimate. Also, 2005–2026 includes only 295 calm weeks — still a limited sample for fitting a classifier.
**Required data:** Norgate US Stocks Platinum/Diamond ($600–$1200/year) OR WRDS CRSP/Compustat subscription.
**Implementation complexity:** Medium (Phase 5A scaffold already exists).
**Validation method:** Full-period and holdout comparison vs Phase 4B best; state-by-state analysis.
**Overfitting risk:** Medium (breadth threshold parameters could be fit to history).
**Can test now:** No. Requires data purchase.
**PIT data required:** Yes.
**Resume-friendly:** Strongly yes. "Point-in-time stock breadth signal for regime quality assessment."
**Recommended priority:** #1 when budget allows.

---

### Idea 3.2 — Sharadar S&P 500 Constituent History (Budget Alternative)

**Name:** Sharadar (Nasdaq Data Link) PIT constituent history
**Description:** Sharadar via Nasdaq Data Link offers a cheaper alternative to Norgate for S&P 500 PIT constituent data (~$50–$200/year depending on plan). Less comprehensive than Norgate but may suffice for breadth signals back to 2000.
**Bottleneck targeted:** Same as 3.1.
**Expected benefit:** Same directional as 3.1 but coverage may not extend to 2005.
**Why it might fail:** Sharadar's delisted stock coverage and PIT accuracy require verification. If the history only goes back to 2010, the full-period backtest will not have 2005–2010 data.
**Can test now:** No. Requires subscription verification and data audit.
**PIT data required:** Yes (cheaper option).
**Recommended priority:** #2 when budget allows (fallback to Sharadar if Norgate is out of budget).

---

### Idea 3.3 — Free CRSP-Equivalent via Open-Source (OSAP, WRDS Alternative)

**Name:** Open-source PIT breadth alternative
**Description:** Several academic open-source datasets provide S&P 500 constituent history:
- **S&P 500 PIT History via CRSP Open:** Some universities share CRSP constituent files.
- **Compustat-style data from EDGAR:** Daily stock prices from EDGAR XBRL filings (2009+).
- **Historical S&P 500 constituent changes from Wikipedia + Yahoo Finance:** Imperfect but free.
**Bottleneck targeted:** Data limitation (free alternative path).
**Expected benefit:** Lower than Norgate/Sharadar due to incomplete coverage, but directionally useful for a biased diagnostic.
**Why it might fail:** Free data sources are typically incomplete (missing delistings, inaccurate PIT constituency, gaps in adjusted price history). Not suitable for production signals.
**Can test now:** Partially (Wikipedia + yfinance already tested in Phase 5A-Free).
**Recommended priority:** Research-only diagnostic. Already done in Phase 5A-Free. Do not build production signal from this.

---

## Category 4: Requires Major ML/Research Effort

---

### Idea 4.1 — Meta-Labeling for Calm_Trend Quality Classification

**Name:** Meta-labeling classifier for calm_trend offense activation
**Description:** Train a secondary ML classifier (gradient boosting or random forest) on ETF features (breadth, momentum, volatility, cross-asset trend) to predict which calm_trend weeks will produce above-median returns for the Phase 4B portfolio. Use as an offense activation gate.
**Bottleneck targeted:** calm_trend sub-classification; separating high-quality from low-quality calm weeks
**Expected benefit:** Uncertain. With N=295 calm weeks and only ETF features, the signal-to-noise ratio is very low. If the classifier finds a meaningful split, +0.02–0.05 pp improvement in calm_trend is possible.
**Why it might work:** There may be subtle patterns in ETF cross-sectional spreads, vol structures, or breadth dynamics that distinguish premium calm weeks from mediocre ones. ML can discover nonlinear combinations that hand-crafted rules miss.
**Why it might fail:** N=295 training examples with ETF features only is well within the regime where ML overfits. Purged cross-validation will show very wide confidence intervals. Every Phase 6 attempt to classify calm_trend quality with ETF features failed.
**Required data:** Existing (but marginal). PIT stock breadth would transform this from marginal to promising.
**Implementation complexity:** High (2–3 sprint weeks; requires careful purged CV, bootstrap validation).
**Overfitting risk:** Very high.
**Can test now:** Technically yes, but expected value is low without PIT data.
**PIT data required:** Not required but strongly recommended.
**Resume-friendly:** Yes — "meta-labeling for regime quality classification" is a known ML-in-finance technique.
**Recommended priority:** #9 — Low without PIT data. #3 with PIT data.

---

### Idea 4.2 — Hidden Markov Model for Regime Detection

**Name:** Gaussian HMM for market state classification
**Description:** Train a 3-state or 5-state Gaussian HMM on weekly ETF return + vol + breadth features. Compare HMM state sequences vs the current causal classifier. Use HMM posterior probabilities as continuous allocation inputs.
**Bottleneck targeted:** State classification quality; calm_trend transition accuracy
**Expected benefit:** Uncertain. If HMM identifies a finer regime structure, it could improve transition quality. However, HMMs fitted to financial returns are notoriously unstable and regime labels change with retraining.
**Why it might fail:** HMM regimes are statistical, not causal. The project explicitly avoids hindsight labels. HMM can produce different regimes when retrained on different windows, making walk-forward validation challenging.
**Implementation complexity:** High (walk-forward HMM retraining is non-trivial).
**Overfitting risk:** High.
**Can test now:** Yes (hmmlearn available).
**PIT data required:** No, but more features would help.
**Resume-friendly:** Yes — HMMs are a recognized quantitative technique.
**Recommended priority:** #10 — Low. Worth a diagnostic comparison but unlikely to improve on the causal classifier.

---

### Idea 4.3 — Online Learning / Contextual Bandit for Allocation

**Name:** Contextual multi-armed bandit for sleeve allocation
**Description:** Model the allocation decision as a contextual bandit problem: at each week, given a context vector (regime state, breadth, vol), choose the offensive allocation weights to maximize expected return subject to risk constraints. Update the reward model online.
**Bottleneck targeted:** Adaptive allocation; calm_trend return optimization
**Expected benefit:** Very uncertain. Online learning is appealing in theory but in practice has a cold-start problem (poor early performance) and is difficult to validate out-of-sample.
**Why it might fail:** The reward signal (weekly return) is very noisy. Contextual bandits require many observations to learn stable policies. With 1,110 total observations (only 295 calm), the sample is too small for reliable online learning.
**Implementation complexity:** Very high.
**Overfitting risk:** Very high.
**Can test now:** Yes.
**PIT data required:** No.
**Resume-friendly:** Yes — cutting-edge technique.
**Recommended priority:** #11 — Not recommended in the near term.

---

## Category 5: Not Recommended

---

### Idea 5.1 — Small Stock Alpha Sleeve

**Name:** Small-cap alpha sleeve from individual stocks
**Description:** Add a small-stock long-only sleeve based on micro/small-cap momentum or quality signals. Provides return diversification beyond ETFs.
**Why rejected:** Requires PIT stock data (prices, fundamental data, constituent history back to 2005). Without PIT data, survivorship bias would invalidate the backtest. Even with PIT data, adding individual stocks changes the strategy mandate and requires a much richer risk management framework.
**Recommended priority:** Not recommended without PIT data. Future research lane only if mandate expands.

---

### Idea 5.2 — Synthetic Carry / Macro Proxy Features

**Name:** Currency carry, term premium, and commodity carry features
**Description:** Add carry signals (TLT yield curve slope, currency carry via ETFs like UUP/FXE, commodity carry via contango/backwardation proxies).
**Why rejected:** The project already uses fixed income ETFs (AGG, TLT, HYG) as part of the defensive and diversification sleeves. Adding explicit carry signals increases the feature space without strong evidence that carry is the missing signal in calm_trend. Phase A's research on cross-asset confirmation was already largely harvested.
**Recommended priority:** Research-only if a specific hypothesis emerges. Low priority.

---

### Idea 5.3 — Crash Risk / Momentum-Crash Filter

**Name:** Momentum crash risk filter
**Description:** Estimate the probability of a momentum crash (following Daniel-Moskowitz 2016) and reduce offensive exposure when crash risk is elevated. Crash risk is high when: recent market returns are very negative AND market volatility is elevated.
**Why downgraded:** The project already captures this through the stressed_panic state. The existing state engine already reduces offense (and increases BIL to ~52%) during exactly the conditions Daniel-Moskowitz identify as high-crash-risk. Adding an explicit momentum crash filter would be largely redundant.
**Recommended priority:** Reference only. Current implementation already captures this.

---

## Full Priority Ranking

| Rank | Idea | Category | Expected Value | Can Test Now |
|------|------|---------|---------------|-------------|
| 1 | Volatility-scaled sector sleeve | 1 | High | Yes |
| 2 | Continuous canary count for BIL | 1 | Medium-High | Yes |
| 3 | Absolute momentum gate on sector | 1 | Medium | Yes |
| 4 | Transition probability multiplier | 1 | Medium | Yes |
| 5 | Shadow ensemble allocator | 1 | Low-Medium | Yes |
| 6 | Ledoit-Wolf covariance shrinkage | 1 | Medium | Yes |
| 7 | Trend quality sector filter | 2 | Medium | Yes |
| 8 | Return-targeting allocator v2 | 2 | Medium | Yes |
| 9 | Meta-labeling classifier (ETF only) | 4 | Low | Yes |
| 10 | HMM regime detection diagnostic | 4 | Low | Yes |
| 11 | PIT stock breadth (Phase 5B) | 3 | **Very High** | **No** (needs data) |
| 12 | Sharadar alternative data | 3 | Very High | No |
| 13 | Online learning / bandit | 4 | Very uncertain | Yes |
| 14 | Small stock alpha sleeve | 5 | N/A without PIT | No |
| 15 | Synthetic carry / macro proxies | 5 | Low | Yes |
| 16 | Crash-risk filter | 5 | Redundant | Yes |
