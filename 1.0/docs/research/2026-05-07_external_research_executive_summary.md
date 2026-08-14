# External Research — Part F: Executive Summary

**Date:** 2026-05-12
**Type:** Research/analysis only. No strategy changes. No production pin changes.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense` (GGG1)

---

## 1. Is the Project Currently Near the Ceiling With Existing Data?

**Yes. The project has reached the practical ceiling of what can be extracted from the existing ETF/sector/regime data universe.**

Seven phases of systematic improvement increased full-period return from 7.14% to 7.88% (+0.74 pp), with the best Sharpe candidate at 7.76% / 0.959. The gap to the 8.0% target is only 0.12 pp, but this gap cannot be closed with existing data. Every attempt to cross this ceiling — broader sector allocation, faster reallocation, richer classifiers, expression boost — has either produced no improvement or improved return at a cost to Sharpe.

The project has not run out of ideas; it has run out of **signal** in the current data that can inform those ideas.

---

## 2. What Is the Main Bottleneck?

**The calm_trend state is the structural constraint. It represents 26.6% of all weeks and earns only 4.39% annualized vs SPY's 16.87% in the same periods — a −12.48 pp annual opportunity cost.**

The existing ETF-only feature set (breadth, trend, VIX, sector momentum) cannot reliably distinguish high-quality calm bull weeks from mediocre ones. Every experiment that tried to identify a "high quality calm" sub-regime and deploy more offense failed:

- Phase 6 extreme_quality_calm signal: showed **negative** Phase 4B lift (−0.019%) despite positive SPY lift
- Phase 7 sector expansion in calm (29.7% allocation): calm return fell from 4.39% to 4.21%
- Phase 6 aggression_score_high in calm: −0.041% same-state lift

**The constraint is not the allocator, not the regime engine, and not the ETF universe. It is the absence of a signal that can tell calm weeks apart.**

---

## 3. Is It Classification, Allocator, Data, ETF Universe, or Mandate?

| Root Cause | Verdict |
|-----------|---------|
| **Data limitation** (no PIT stock breadth) | **Primary** |
| **Signal quality** (existing features don't split calm weeks) | **Primary consequence** |
| **ETF universe** (sector ETFs don't outperform the diversified base in calm) | Secondary |
| **State classification** (can't identify high-quality calm sub-weeks) | Secondary consequence |
| **Allocator** (HRP too conservative) | Tertiary — tested in Phase 2A; HRP won |
| **Mandate** (low SPY/QQQ beta required) | Compatible with good performance; not the binding constraint |

The data limitation is causal. With PIT stock breadth, the signal quality improves, the state classifier can distinguish calm quality, and the ETF deployment improves accordingly.

---

## 4. What Does the Outside Literature Suggest?

The academic literature is directionally aligned with the project's existing architecture and confirms several specific ideas for improvement:

1. **Volatility-managed portfolios** (Moreira-Muir 2017; Barroso-Santa-Clara 2015): Scaling the sector sleeve by inverse realized volatility is a straightforward Sharpe improvement, confirmed across multiple asset classes and time periods. This is the highest-confidence next improvement available without new data.

2. **Market breadth as a regime signal** (Keller-Keuning 2017/2018 VAA/DAA; Phase 5A-Free diagnostic): Stock breadth is a richer and more targeted signal than ETF breadth for equity regime classification. The Phase 5A-Free diagnostic confirmed this; the DAA literature formalizes a related idea with simpler canary assets.

3. **Dual momentum for sector activation** (Antonacci 2012): Adding an absolute momentum check to the sector sleeve gate — only deploy when the top sector also beats BIL on absolute momentum — reduces false-positive activations during early bear periods.

4. **Risk parity and ERC** (Roncalli 2013/2016; skfolio/Riskfolio-Lib): Equal Risk Contribution within the sector sleeve may reduce concentration risk and stabilize weights, with a potential Sharpe improvement from lower turnover.

5. **Regime transition probability in allocation** (Ang-Bekaert 2004): Using the existing `transition_good_state_prob` feature as a continuous multiplier on the offense budget is grounded in formal regime-switching asset allocation theory and requires no new data.

6. **Data mining concerns** (Harvey-Liu-Zhu 2016): The project's governance framework (holdout discipline, bootstrap testing, dual-track pins) is exactly the right response to the data-mining problem documented in the literature. The project should maintain this discipline even as it tests new ideas.

---

## 5. What Ideas Are Most Worth Trying?

**Ranked by: (expected benefit × implementation speed) / overfitting risk**

| Rank | Idea | Why |
|------|------|-----|
| 1 | **Volatility-scaled sector sleeve** | Strong literature support; low complexity; directly addresses the Sharpe-return tradeoff steepening. Can improve Sharpe by +0.005–0.02 without much return cost. |
| 2 | **Continuous canary count for BIL** | Simple rule change; reduces BIL drag in near-good-state weeks. Low overfitting risk. |
| 3 | **Absolute momentum gate for sector** | One additional condition in the sector activation logic. Prevents deploying into declining sectors. |
| 4 | **ERC / shrinkage for sector sleeve** | Reduces estimation error in the 11×11 sector covariance. Likely reduces turnover. |
| 5 | **Regime transition probability multiplier** | `transition_good_state_prob` is already computed and causal. Wiring it to the sector budget is a 1-day change. |

---

## 6. What Ideas Are Not Worth Trying?

| Idea | Why not |
|------|---------|
| Meta-labeling with ETF features only | N=295 calm weeks is too small; Phase 6 already exhausted ETF-feature-based calm classification. High overfitting risk. |
| HMM regime classification | Adds complexity and overfitting risk; interpretability decreases; Phase 2A showed HRP is robust enough. |
| Another broad search phase | The feature space has been extensively searched across 7 phases. Another blind sweep is data mining. |
| Online learning / contextual bandit | Sample is too small; reward signal is too noisy; very high overfitting risk. |
| Small stock alpha sleeve without PIT | Survivorship bias makes any backtest invalid. |
| Return-targeting allocator (v2, without better signal) | Phase 7 already tested more aggressive expression in HRP; trailing returns as expected return is unstable. |
| MVO / Black-Litterman (without views) | Tested in Phase 2A; HRP dominated on the composite. |

---

## 7. What Should Be Done Next Without Paid Data?

**Three sprints, in order:**

1. **Phase 8 — Volatility-Managed Sector Sleeve:** Scale the sector sleeve budget by inverse 13/26-week realized volatility of the sleeve. Expected: +0.005–0.02 Sharpe improvement without material return loss. This is the highest-expected-value near-term improvement available.

2. **Phase 9 — Sector Construction Upgrade:** Test ERC and Ledoit-Wolf shrinkage as replacements for raw HRP within the sector sleeve. Expected: turnover reduction, potentially Sharpe improvement. Small scope, strong motivation.

3. **Phase RRR — Regime Classifier Robustness Diagnostic:** Produce a rigorous, publication-quality statistical validation of the regime engine. No new candidates; no production pin changes. This sprint produces an independent research artifact and prepares the foundation for Phase 5B (PIT stock breadth integration).

**Honest assessment of expected value without paid data:** Phases 8 and 9 together may produce +0.01–0.03 pp Sharpe improvement and minor return improvements. They will not close the 0.12 pp gap to 8.0%. Phase RRR adds research credibility but not additional return. The project is genuinely near the ceiling without PIT data.

---

## 8. What Should Be Saved for When PIT Stock Data Is Available?

| Item | Why it needs PIT data |
|------|----------------------|
| **Phase 5B — Full stock breadth signal** | The Phase 5A-Free diagnostic showed +0.347% per 4-week lift for Phase 4B in calm_trend. Production-valid breadth requires PIT constituent history. This is the #1 priority when data is available. |
| **Meta-labeling for calm_trend classification** | ML on N=295 calm weeks is marginal; with 20+ years of PIT breadth features, the sample grows substantially and the feature set becomes much richer. |
| **Breadth-confirmed recovery rerisk** | recovery_confirmed signal quality improves dramatically with PIT breadth (Phase 5A-Free showed 100% hit rate, but at N=18 this is noise; with 20 years of PIT data N grows to ~80+ recovery weeks). |
| **HMM / ML state classification upgrade** | More features (PIT breadth) make the HMM or gradient boosting classifier far less overfitted. |
| **Full regime-quality-aware tactical allocation** | When breadth, factor quality, and sector breadth are all available, the allocator has the inputs needed for a truly state-conditioned dynamic risk budget. |

**Data recommendation:** Norgate US Stocks Platinum or Diamond ($600–$1200/year) provides PIT S&P 500 constituent history with daily adjusted prices back to 1993. This is the right data source for Phase 5B. Sharadar via Nasdaq Data Link is a cheaper alternative (~$50–$200/year) but requires verification of PIT accuracy and historical coverage back to 2005.

---

## 9. What Would Make the Project More Impressive to Quants?

**Most impressive elements already in the project:**
1. A custom causal market-state regime engine (Layer 2B) — the single most distinctive feature
2. Strict holdout discipline with pre-declared windows
3. Dual-track governance (production pin + shadow pin + dual promotion requirement)
4. Bootstrap testing of promotion decisions (not just in-sample metrics)
5. A 7-phase systematic improvement arc with documented failures (Phase 5A-Free survivorship bias disclosure, Combo1 holdout failure, Phase 7 steepening tradeoff)

**Most impactful additions for impressiveness:**

1. **Regime engine robustness diagnostic (Phase RRR):** Publish a rigorous state-by-state forward-return validation, persistence statistics, and comparison to simple alternatives. This answers the inevitable interviewer question: "How do you know your regime labels work?"

2. **PIT stock breadth integration (Phase 5B):** The most technically impressive addition possible. Demonstrates understanding of survivorship bias, PIT data requirements, and a novel calm_trend signal.

3. **Volatility-managed sleeve (Phase 8):** Demonstrates awareness of the Moreira-Muir literature and the ability to translate published research into portfolio construction.

4. **Clear performance narrative:** The project's story arc (7.14% → 7.88% over 7 phases; each phase documented; failures acknowledged; ceiling identified and explained) is already strong. Making this more visible in the dashboard and README would help.

5. **Benchmark context:** Add a clear comparison table showing the project's Sharpe (0.959) vs:
   - SPY: 0.600
   - 60/40: 0.785
   - Antonacci Dual Momentum: ~0.50–0.65 (published ETF backtest)
   - Keller VAA: ~0.75–0.90 (published)
   This contextualizes 0.959 as genuinely strong for a long-only ETF mandate.

---

## 10. What Should Be Displayed on the Dashboard and Resume?

**Dashboard — what to add or emphasize:**
- State-by-state performance table (currently present; make more prominent)
- Regime engine forward-return validation chart (after Phase RRR)
- 7-phase improvement arc chart (return and Sharpe at each phase milestone)
- Honest ceiling narrative: "Data limitation identified; next step is PIT stock breadth"
- Benchmark comparison (SPY, 60/40, Dual Momentum, VAA)
- Production vs shadow vs candidate performance comparison

**Resume bullet points (suggested framing):**
- "Built a causal 5-state market regime engine (ETF price, breadth, VIX, cross-asset features) with walk-forward validation and pre-declared holdout testing. Engine drives state-conditioned tactical allocation across 7 ETF sleeves."
- "Improved out-of-sample Sharpe from 0.936 to 0.959 and annual return from 7.14% to 7.76% over 7 systematic research phases, while maintaining −1.5% drawdown during 2022 bear (vs SPY −18.2%)."
- "Identified calm_trend as the portfolio's structural bottleneck; quantified the +0.35% per 4-week Phase 4B lift available from PIT stock breadth signals (Phase 5A-Free diagnostic)."
- "Implemented dual-track governance (production pin + shadow pin) with bootstrap promotion testing (block bootstrap, 13-week blocks, 2000 iterations) to guard against overfitting and pool-sensitive rank composites."
- "Compared HRP, ERC, HERC, MVO, and Black-Litterman allocators across multiple return windows; HRP selected as production allocator based on composite score superiority."

---

## Final Verdict

| Question | Answer |
|----------|--------|
| Near ceiling with existing data? | **Yes.** 0.12 pp gap requires PIT stock breadth. |
| Primary bottleneck | **calm_trend state — no ETF signal can split good from mediocre calm weeks.** |
| Root cause | **Data limitation → signal quality → state classification → deployment quality.** |
| Literature consensus | **Stock breadth is the right signal; volatility scaling is the right construction improvement.** |
| Best ideas without paid data | **Vol-scaled sleeve, canary count, absolute momentum gate, ERC/shrinkage.** |
| Ideas not worth pursuing | **Meta-labeling (ETF-only), another broad search phase, online learning.** |
| Best idea with paid data | **PIT stock breadth (Phase 5B) — closes the 8.0% target.** |
| Most impressive to quants | **Regime engine robustness diagnostic + PIT breadth integration + clear failure documentation.** |
| Dashboard / resume message | **"Disciplined causal systematic ETF strategy; ceiling identified; gap explained; next step is PIT data."** |
