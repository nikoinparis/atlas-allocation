# External Research — Part B: Academic Papers and Practitioner Strategies

**Date:** 2026-05-12
**Type:** Research/analysis only. No strategy changes.
**Web access:** Available. All sources cited were confirmed reachable during this session.

---

## Web Research Availability

Web access was available and used. All papers and sources below were confirmed via live web search.

---

## Overview of Research Areas Covered

1. Tactical asset allocation / trend following
2. Dual momentum
3. Cross-sectional momentum across ETFs
4. Volatility-managed portfolios
5. Defensive equity / risk-on risk-off
6. Market breadth as regime classifier
7. Sector rotation
8. Macro regime switching / HMM
9. Dynamic risk budgeting / risk parity
10. Momentum crash risk
11. Data mining / multiple testing (anti-overfitting)
12. Portfolio construction beyond HRP

---

## Paper 1 — Faber (2007): A Quantitative Approach to Tactical Asset Allocation

- **Authors:** Mebane T. Faber
- **Year:** 2007 (published Journal of Wealth Management, Spring 2007)
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- **Key idea:** A simple 10-month moving average timing model tested on the US equity market and 20+ international markets. When price is above 10-month SMA, hold; otherwise move to T-bills. Historically improved risk-adjusted returns, reduced drawdown, avoided large bear markets.
- **Why it may help this project:** The project already uses a multi-state regime engine (Layer 2B) that partially captures what Faber's SMA attempts — distinguishing calm bull from stressed/declining conditions. Faber's approach is simpler but confirms the directional wisdom of trend-conditioned allocation.
- **Bottleneck targeted:** State classification quality; calm_trend vs stressed_panic distinction.
- **Implementation complexity:** Very low. Already directionally implemented.
- **Data requirements:** Price only. ETF-compatible.
- **Paid data required:** No.
- **Risk of overfitting:** Low (single simple rule, 100+ year backtest).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Reference only.** Already captured in the project's regime engine. Adding raw SMA rules would regress from the current multi-state engine.

---

## Paper 2 — Antonacci (2012/2014): Dual Momentum

- **Authors:** Gary Antonacci
- **Year:** 2012 SSRN; book published 2014
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750 (Risk Premia Harvesting Through Dual Momentum); https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1833722 (Optimal Momentum)
- **Key idea:** Combines absolute momentum (time-series: is SPY > T-bills?) with relative momentum (cross-sectional: which asset has highest momentum?). When absolute momentum is negative, hold T-bills. When positive, hold the top relative momentum asset.
- **Why it may help this project:** The project's neutral_mixed and calm_trend behavior could benefit from a more rigorous absolute vs relative momentum framework for the sector sleeve. Instead of activating the sector sleeve based on ETF breadth signals, a dual momentum framework would require both absolute momentum confirmation (sector trending up) AND relative momentum rank (sector is a leader).
- **Bottleneck targeted:** Sector sleeve activation quality in calm_trend and neutral_mixed.
- **Implementation complexity:** Low. Already partially implemented in the sector sleeve momentum ranking. The "absolute momentum" guard (T-bill comparison) is the missing piece.
- **Data requirements:** ETF prices only.
- **Paid data required:** No.
- **Risk of overfitting:** Low (dual momentum is a published, widely replicated strategy).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Test now.** Add an absolute momentum check to the sector sleeve activation gate: only activate sector sleeve when the top-ranked sector also has positive momentum vs T-bills (or BIL). This is a small code change with clear economic motivation.

---

## Paper 3 — Hurst, Ooi, Pedersen / AQR (2017): A Century of Evidence on Trend-Following Investing

- **Authors:** Brian Hurst, Yao Hua Ooi, Lasse Heje Pedersen (AQR)
- **Year:** 2017, Journal of Portfolio Management
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- **Key idea:** Time-series momentum (TSMOM) across 67 markets in 4 asset classes from 1880 to 2016. TSMOM delivers positive average returns in every decade. Works especially well during crisis periods (8 of 10 largest 60/40 drawdowns). The key insight is that trends are persistent across very long time horizons.
- **Why it may help this project:** Validates the core trend-following engine design. More importantly, the paper's analysis of TSMOM's behavior during different market regimes aligns with this project's regime engine. When TSMOM is negative (bear markets), defensiveness is warranted. When TSMOM is positive across asset classes, offensive allocation is more reliable. The project could use cross-asset TSMOM signals as an additional regime quality metric.
- **Bottleneck targeted:** Calm_trend classification quality (is the current calm trend durable or fragile?).
- **Implementation complexity:** Low–Medium. Already have price data for relevant ETFs.
- **Data requirements:** ETF prices for multiple asset classes (already available).
- **Paid data required:** No.
- **Risk of overfitting:** Low (century of evidence, widely replicated).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Save for later.** The project already captures cross-asset trend. A marginal improvement from formalizing TSMOM across more asset classes is possible but may not move the needle given the primary bottleneck is calm_trend within-state discrimination.

---

## Paper 4 — Lempérière, Deremble, Seager, Potters, Bouchaud (2014): Two Centuries of Trend Following

- **Authors:** Yves Lempérière, Cyril Deremble, Philip Seager, Marc Potters, Jean-Philippe Bouchaud (Capital Fund Management)
- **Year:** 2014, arXiv:1404.3274
- **URL / Citation:** https://arxiv.org/abs/1404.3274
- **Key idea:** Trend following across 4 asset classes (commodities, currencies, stock indices, bonds) exists robustly for 2 centuries. T-stat ≈ 5 since 1960, ≈ 10 since 1800. The trend signal is approximately as strong using 1-month to 5-year lookbacks.
- **Why it may help this project:** Provides statistical confidence that the existing trend backbone of the project is on solid ground. Also suggests that multi-lookback trend aggregation (blending 1m/3m/12m momentum) is more robust than single-lookback. This is already partially implemented in the project's blended momentum signals.
- **Bottleneck targeted:** Trend signal robustness; multi-lookback blending.
- **Implementation complexity:** Low (already done).
- **Recommended action:** **Reference only.** The project already blends multiple lookbacks. Confirms existing approach.

---

## Paper 5 — Moreira and Muir (2017): Volatility-Managed Portfolios

- **Authors:** Alan Moreira (U. Rochester), Tyler Muir (UCLA / NBER)
- **Year:** 2017, Journal of Finance vol. 72(4) pp. 1611–1644
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431
- **Key idea:** Managed portfolios that take less risk when volatility is high produce large Sharpe improvements vs unmanaged. Scale portfolio exposure by inverse of lagged realized variance. Works across equity, value, momentum, and factor strategies. Utility gains nearly twice those from return timing.
- **Why it may help this project:** The project uses BIL as a "safe" asset but does not explicitly scale portfolio-level risk by realized volatility within offense states. A volatility-managed offensive sleeve could dynamically reduce sector/offense exposure when recent realized volatility is elevated (even in calm states), and increase exposure when it is low. This is a form of risk-targeting within each state, not just between states.
- **Bottleneck targeted:** BIL drag vs return tradeoff; improving return within calm_trend when conditions are favorable.
- **Implementation complexity:** Medium. Requires tracking realized variance and scaling the offensive sleeve budget accordingly.
- **Data requirements:** ETF price returns (already available).
- **Paid data required:** No.
- **Risk of overfitting:** Low (published JF, widely replicated).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Test now.** A volatility-scaled offensive sleeve is implementable with existing data and addresses the Sharpe-return tradeoff directly. It may reduce drawdown at minimal cost to return. This is one of the top ideas.

---

## Paper 6 — Barroso and Santa-Clara (2015): Momentum Has Its Moments

- **Authors:** Pedro Barroso, Pedro Santa-Clara
- **Year:** 2015, Journal of Financial Economics vol. 116(1) pp. 111–120
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429
- **Key idea:** Scaling momentum exposure by the inverse of its 6-month realized variance nearly doubles Sharpe (0.53 → 0.97) and eliminates crash risk. The key insight is that momentum volatility is forecastable and predictive of subsequent momentum crash risk.
- **Why it may help this project:** The project's sector sleeve is effectively a cross-sectional momentum strategy. When sector momentum realized variance is elevated (sector choppiness), reducing the sleeve budget could improve Sharpe without sacrificing much return. Conversely, when sector momentum variance is low (clean trend), expanding the sleeve is safer. This gives a second discriminant for calm_trend quality beyond breadth signals.
- **Bottleneck targeted:** Sector sleeve Sharpe-return tradeoff; calm_trend and neutral_mixed timing.
- **Implementation complexity:** Low–Medium. Track 6-month realized variance of the sector sleeve returns; scale sector budget accordingly.
- **Data requirements:** Existing sector ETF price history.
- **Paid data required:** No.
- **Risk of overfitting:** Low (published JFE, multiple replications).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Test now.** Scaling the sector sleeve by inverse realized variance of the sleeve's own recent returns is a low-complexity improvement with strong literature support. Could directly address the observation that sector ETFs "don't outperform in calm" — by scaling down in choppy periods and scaling up in smooth ones.

---

## Paper 7 — Daniel and Moskowitz (2016): Momentum Crashes

- **Authors:** Kent Daniel (Columbia), Tobias J. Moskowitz (Yale / AQR)
- **Year:** 2016, Journal of Financial Economics vol. 122 pp. 221–247
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227
- **Key idea:** Momentum crashes are partly forecastable — they occur in "panic" states following market declines when volatility is high. The option-like payoffs of past losers create a risk premium that is priced in. A dynamic strategy using forecasts of momentum's mean and variance approximately doubles alpha and Sharpe.
- **Why it may help this project:** The project already has a stressed_panic regime detector. The Daniel-Moskowitz insight confirms that during stressed_panic periods, momentum crashes are most likely, and the portfolio's defensiveness in stressed_panic is economically well-grounded. However, the paper also identifies the "recovery" state transition as the moment of greatest momentum risk — past losers (beaten-down stocks) may dramatically outperform during sharp market recoveries, hurting long-momentum strategies. The project's recovery_fragile / recovery_confirmed distinction addresses this.
- **Bottleneck targeted:** Stressed_panic protection (already good); recovery state momentum risk management.
- **Implementation complexity:** Already addressed directionally.
- **Recommended action:** **Reference/Validate.** The project's regime engine already captures the key insight. The Daniel-Moskowitz crash risk framework could be used to validate the existing stressed_panic protection and confirm that the recovery state transitions are being handled correctly.

---

## Paper 8 — Keller and Keuning (2017): Vigilant Asset Allocation (VAA)

- **Authors:** Wouter J. Keller, Jan Willem Keuning
- **Year:** 2017, SSRN
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624
- **Key idea:** VAA replaces individual asset trend following with breadth momentum on the universe level for crash protection. When the number of assets with negative momentum exceeds a threshold, move to cash/bonds. Risky allocation is based on cross-sectional relative momentum. Results: >10% annual returns with <15% max drawdown on ETF-like data from 1925.
- **Why it may help this project:** The "canary universe" concept from the follow-on DAA paper (Keller & Keuning 2018, SSRN 3212862) uses a small set of "canary" assets (e.g., SPY, EEM, AGG, HYG) to signal defensive transitions. When canary assets show negative momentum, the portfolio shifts defensively. This is philosophically aligned with the project's existing canary breadth signal (`canary_breadth_default`). The key difference: VAA uses a strict breadth threshold whereas this project uses a continuous score.
- **Bottleneck targeted:** Regime transition quality; calm vs stressed classification.
- **Implementation complexity:** Low–Medium (canary concept already in the project).
- **Data requirements:** ETF prices only.
- **Paid data required:** No.
- **Risk of overfitting:** Medium (in-sample lookback selection).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Save for later.** The canary concept is already in the pipeline. A formal comparison of the VAA/DAA canary approach vs the current regime engine could be interesting but is unlikely to be the incremental gain the project needs.

---

## Paper 9 — Keller and Keuning (2018): Defensive Asset Allocation (DAA)

- **Authors:** Wouter J. Keller, Jan Willem Keuning
- **Year:** 2018, SSRN
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862
- **Key idea:** Extends VAA with a separate "canary" universe for crash protection signaling, allowing lower average cash fraction while maintaining crash protection. The amount of cash (BIL) is governed by the number of canary assets with bad (negative) momentum.
- **Why it may help this project:** DAA's core innovation — dynamically varying the cash fraction based on a canary signal — is already partially implemented in this project via the `canary_breadth_default` feature. The incremental idea worth testing: use the **number** of canary assets below trend (not just a binary canary signal) as a continuous input to the BIL budget. This could reduce BIL drag in weeks where most but not all canary assets are positive.
- **Bottleneck targeted:** BIL drag in partial-calm periods; reducing unnecessary cash during near-good-state weeks.
- **Implementation complexity:** Low.
- **Recommended action:** **Test now.** A small, targeted change: modify the `canary_breadth_default` threshold to use a continuous 0–4 canary count (all 4 positive = maximum offense, 3 positive = mild reduction, 2 = moderate, etc.). This is a one-day code change.

---

## Paper 10 — Jegadeesh and Titman (1993): Returns to Buying Winners and Selling Losers

- **Authors:** Narasimhan Jegadeesh, Sheridan Titman
- **Year:** 1993, Journal of Finance vol. 48(1) pp. 65–91
- **URL / Citation:** https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x
- **Key idea:** Cross-sectional stock momentum (3–12 month) generates significant positive returns. The foundational paper establishing momentum as an anomaly.
- **Why it may help this project:** The sector sleeve is based on cross-sectional sector ETF momentum. Jegadeesh-Titman provides the statistical foundation. The project's implementation is already largely consistent with the 6–12 month lookback recommendation. The key takeaway for this project: shorter-lookback momentum (1–3 month) is noisier and more exposed to reversals; the project's 13-week and 26-week blended lookbacks are reasonable.
- **Recommended action:** **Reference only.** Already implemented.

---

## Paper 11 — Hamilton (1989): A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle

- **Authors:** James D. Hamilton
- **Year:** 1989, Econometrica
- **URL / Citation (regime switching review):** https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf
- **Key idea:** Markov Regime Switching (MRS) model for time series. States are latent and transitions follow a Markov chain. Identifies distinct regimes (e.g., expansion vs. recession) from observed data.
- **Why it may help this project:** The project's Layer 2B regime engine is a hand-crafted causal classifier, not an HMM. A Gaussian HMM trained on ETF price/volume/breadth features could provide a probabilistic regime assignment (P(calm), P(stressed), etc.) rather than hard labels. This could improve transition handling and reduce the edge-classification problem that occasionally misclassifies the start of recovery periods.
- **Bottleneck targeted:** State classification quality; regime transition accuracy.
- **Implementation complexity:** Medium. Gaussian HMM is available in `hmmlearn` (Python). Training and forward-validation requires care to avoid lookahead.
- **Data requirements:** Existing ETF/breadth features.
- **Paid data required:** No.
- **Risk of overfitting:** High if not carefully cross-validated with walk-forward windows.
- **ETF-only compatible:** Yes.
- **Recommended action:** **Save for later.** The current causal classifier is more interpretable and controllable. HMM adds complexity and overfitting risk. Worth exploring if interpretability tradeoffs are acceptable.

---

## Paper 12 — Regime-Switching Factor Investing with Hidden Markov Models (2020, MDPI)

- **Authors:** Multiple (see: https://www.mdpi.com/1911-8074/13/12/311)
- **Year:** 2020, Journal of Risk and Financial Management
- **URL / Citation:** https://www.mdpi.com/1911-8074/13/12/311
- **Key idea:** Uses HMMs to identify market regimes (bull/bear) and switches factor exposures accordingly. When HMM identifies a bull regime, overweight momentum and growth factors; in bear regimes, overweight value and low-volatility.
- **Why it may help this project:** The regime-switching factor approach is directly aligned with the project's architecture (regime → allocation). The key difference: this approach uses HMM for classification. If the HMM's regimes align well with the project's causal states, it could sharpen calm_trend identification.
- **Bottleneck targeted:** Calm_trend classification quality.
- **Implementation complexity:** Medium.
- **Recommended action:** **Save for later.** High overfitting risk without PIT data for sufficient training examples.

---

## Paper 13 — López de Prado (2018): Advances in Financial Machine Learning

- **Authors:** Marcos López de Prado
- **Year:** 2018, Wiley
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104847 (Chapter 1)
- **Key idea:** Comprehensive treatment of ML in finance. Key contributions: HRP (Hierarchical Risk Parity) as an alternative to MVO; meta-labeling for building secondary classifiers on top of primary signals; purged cross-validation for time-series ML; fractional differentiation for stationarity.
- **Why it may help this project:** 
  1. **Meta-labeling:** Train a secondary classifier (meta-learner) to predict which regime-labeled weeks the primary offensive strategy will outperform. This could identify high-quality calm_trend weeks without PIT stock breadth, using ETF features as the meta-learner inputs.
  2. **HRP:** Already in use. Confirms current construction approach.
  3. **Purged CV:** Already used (time-ordered validation).
- **Bottleneck targeted:** Calm_trend sub-classification; state classification quality.
- **Implementation complexity:** High for meta-labeling; requires careful feature engineering and validation.
- **Data requirements:** Existing ETF features.
- **Paid data required:** No (for the meta-labeling approach).
- **Risk of overfitting:** High. Meta-labeling on small samples (295 calm weeks) with ETF features is the kind of ML that overfits easily.
- **ETF-only compatible:** Yes.
- **Recommended action:** **Save for later.** Meta-labeling is intellectually interesting but likely to overfit with N=295 calm weeks and only ETF features. PIT stock breadth would make this much more tractable.

---

## Paper 14 — Harvey, Liu, and Zhu (2016): ...And the Cross-Section of Expected Returns

- **Authors:** Campbell R. Harvey, Yan Liu, Heqing Zhu
- **Year:** 2016, Review of Financial Studies vol. 29(1) pp. 5–68
- **URL / Citation:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314
- **Key idea:** Over 316 factors have been documented in finance research. Most are likely false discoveries from data mining. By 2012, a new factor needs a t-statistic ≥ 3.0 to be credible (vs. the traditional 2.0 threshold), accounting for the large number of prior tests.
- **Why it may help this project:** Directly relevant to the project's governance discipline. Every candidate signal tested in Phases 1–7 is a factor subject to data-mining concerns. The lesson: the project should require strong economic motivation before testing, and should demand robust out-of-sample validation before promotion. This paper validates the existing research process rather than suggesting new signals.
- **Recommended action:** **Reference only.** Validates existing governance framework (holdout discipline, bootstrap testing, dual-track comparison).

---

## Paper 15 — Roncalli (2013/2016): Risk Parity and Risk Budgeting

- **Authors:** Thierry Roncalli (Amundi)
- **Year:** 2013/2016, Lyxor Asset Management / SSRN
- **URL / Citation:** http://www.thierry-roncalli.com/RiskParityBook.html
- **Key idea:** Risk parity (equal risk contribution) portfolios allocate so that each asset contributes equally to total portfolio variance. Extensions include hierarchical risk parity, targeted risk budgets, and CVaR-based risk budgeting.
- **Why it may help this project:** The project uses HRP which is related but different from ERC (equal risk contribution). ERC and targeted risk budgeting could offer an alternative construction for the offensive sleeve allocation. Within the offensive budget, instead of HRP across all sleeves, an ERC across sector ETFs could reduce sector concentration risk.
- **Bottleneck targeted:** BIL drag / portfolio construction within offense budget; Sharpe-return tradeoff.
- **Implementation complexity:** Low–Medium. ERC is well-implemented in Riskfolio-Lib and skfolio.
- **Data requirements:** Covariance matrix of ETF returns (already available).
- **Paid data required:** No.
- **Risk of overfitting:** Low (no in-sample parameter fitting beyond covariance).
- **ETF-only compatible:** Yes.
- **Recommended action:** **Test now.** Replace the within-sector HRP with ERC or inverse-variance weighting when the sector sleeve is active. Small change, strong motivation.

---

## Paper 16 — Ang and Bekaert (2004): How Regimes Affect Asset Allocation

- **Authors:** Andrew Ang, Geert Bekaert
- **Year:** 2004, Financial Analysts Journal
- **URL / Citation:** https://www.nber.org/system/files/working_papers/w17182/w17182.pdf (NBER Regime Changes and Financial Markets 2011, related work)
- **Key idea:** Regime-switching CAPM: different regimes (bear/bull) have different means, variances, and correlations. Allocations optimized for a single-regime model are suboptimal when regimes exist. The key practical implication: optimal allocation in a bear state is substantially different from a bull state, and the optimal portfolio must account for regime transition probabilities.
- **Why it may help this project:** The project's regime engine already acts on this insight. The Ang-Bekaert paper provides formal backing. One under-explored application: use **regime transition probabilities** from the state engine as a continuous allocation input. If P(staying in calm_trend) = 0.95 vs 0.70, the sector sleeve could be 20% vs 15% accordingly.
- **Bottleneck targeted:** Regime transition quality; BIL reduction in high-probability-calm weeks.
- **Implementation complexity:** Low. The `transition_good_state_prob` feature is already computed.
- **Recommended action:** **Test now.** Use `transition_good_state_prob` as a continuous multiplier on the sector sleeve budget within calm_trend weeks. Already available as a feature; needs wiring into the allocator.

---

## Summary Table

| # | Paper | Bottleneck | Action | Data needed |
|---|-------|-----------|--------|-------------|
| 1 | Faber TAA | Regime classification | Reference | ETF prices |
| 2 | Antonacci Dual Momentum | Sector activation | **Test now** | ETF prices |
| 3 | Hurst et al. Century Trend | Signal quality | Save for later | ETF prices |
| 4 | Lempérière Two Centuries | Signal robustness | Reference | ETF prices |
| 5 | Moreira-Muir Vol-Managed | Sharpe/return tradeoff | **Test now** | ETF prices |
| 6 | Barroso-Santa-Clara Mom Moments | Sector sleeve timing | **Test now** | ETF prices |
| 7 | Daniel-Moskowitz Mom Crashes | Stressed protection | Reference/validate | ETF prices |
| 8 | Keller-Keuning VAA | Regime classification | Save for later | ETF prices |
| 9 | Keller-Keuning DAA | BIL drag | **Test now** | ETF prices |
| 10 | Jegadeesh-Titman Momentum | Sector ranking | Reference | ETF prices |
| 11 | Hamilton HMM | State classification | Save for later | ETF features |
| 12 | HMM Factor Switching | State classification | Save for later | ETF features |
| 13 | López de Prado AFML | Meta-labeling | Save for later (PIT data) | PIT stock data |
| 14 | Harvey-Liu-Zhu Cross-Section | Anti-overfitting | Reference | N/A |
| 15 | Roncalli Risk Parity | Construction | **Test now** | ETF returns |
| 16 | Ang-Bekaert Regimes | Transition quality | **Test now** | Existing features |

---

## Top 5 "Test Now" Ideas from Literature

1. **Volatility-managed sector sleeve** (Moreira-Muir): Scale sector budget by inverse realized variance of the sleeve's own returns.
2. **Absolute momentum check for sector activation** (Antonacci): Only activate sector sleeve when top-ranked sector has positive momentum vs BIL.
3. **Sector sleeve realized-vol scaling** (Barroso–Santa-Clara): Use 6-month realized vol of the sector sleeve to scale its budget.
4. **Continuous canary count → BIL budget** (Keller-Keuning DAA): Replace binary canary signal with a continuous count.
5. **Transition probability multiplier on offense budget** (Ang-Bekaert): Use `transition_good_state_prob` as a continuous multiplier on the sector sleeve budget.
