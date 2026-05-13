# External Research — Part C: GitHub Repos and Libraries

**Date:** 2026-05-12
**Type:** Research/analysis only. No packages installed. No code copied. No dependencies modified.
**Web access:** Available.

---

## Important Constraints

- Do not install packages.
- Do not copy code.
- Do not modify repo dependencies.
- All entries below are research/inspiration only.

---

## Repo 1 — skfolio

- **URL:** https://github.com/skfolio/skfolio
- **Website:** https://skfolio.org/
- **License:** BSD-3-Clause
- **Stars/Activity:** Actively maintained (2024–2025). arXiv paper published 2025 (arxiv 2507.04176).
- **What it does:** Portfolio optimization library built on top of scikit-learn. Provides a unified interface for mean-variance, risk parity, HRP, HERC, ERC, CVaR optimization, maximum diversification, and Black-Litterman. Integrates with scikit-learn's `cross_validate`, `Pipeline`, `GridSearchCV` for hyperparameter tuning and walk-forward validation.
- **Relevant ideas to borrow:**
  1. Walk-forward cross-validation framework for portfolio optimization — directly relevant to the project's need for more rigorous holdout validation.
  2. HERC (Hierarchical Equal Risk Contribution) implementation — could replace HRP within the offensive sleeve to better balance risk contributions across sector ETFs.
  3. CVaR portfolio optimization — could test CVaR-minimizing allocation within the offense budget (already discussed as a potential sprint).
  4. Maximum diversification portfolio — could benchmark against the project's HRP for the base allocation.
- **Code usable:** Inspiration only (scikit-learn integration patterns); would need to add as a dependency.
- **Add as dependency?** Not yet. The project has its own build pipeline; adding skfolio would require careful integration and testing.
- **Bottleneck targeted:** Construction quality (HRP vs HERC vs ERC); Sharpe-return tradeoff.
- **Implementation risk:** Medium. Adding a new library dependency to a production pipeline requires audit.
- **Recommended action:** **Use as inspiration.** Review skfolio's HERC and ERC implementations to understand how to implement these manually within the existing Layer 3 framework. Do not add as dependency until a dedicated sprint for construction upgrade.

---

## Repo 2 — Riskfolio-Lib

- **URL:** https://github.com/dcajasn/Riskfolio-Lib
- **License:** BSD-3-Clause
- **Stars/Activity:** Actively maintained. Version 7.2 documented.
- **What it does:** Portfolio optimization library built on CVXPY and pandas. Covers MVO, risk parity, HRP, HERC, ERC, CVaR optimization, drawdown optimization, Black-Litterman, factor models, and worst-case MVO. Very comprehensive.
- **Relevant ideas to borrow:**
  1. **CVaR budgeting** — allocate risk budgets measured in CVaR rather than variance. Could replace HRP for the stressed-protection sleeve.
  2. **Drawdown-constrained optimization** — Riskfolio implements maximum drawdown constraints in the optimizer. Could be used to hard-constrain the offensive allocation to not exceed a drawdown budget.
  3. **HERC with linkage methods** — more flexible than HRP for the sector sleeve.
  4. **Regime-conditional optimization** — Riskfolio supports scenario-based optimization which could be used to build state-conditioned portfolios.
- **Code usable:** Inspiration only.
- **Add as dependency?** No. Similar to skfolio, would require audit of the build pipeline.
- **Bottleneck targeted:** Construction quality; Sharpe-return tradeoff; BIL drag.
- **Implementation risk:** Medium.
- **Recommended action:** **Use as inspiration.** The drawdown-constrained optimization and CVaR budgeting concepts from Riskfolio are the most relevant. These can be approximated within the existing framework using simpler rule-based approaches.

---

## Repo 3 — PyPortfolioOpt

- **URL:** https://github.com/PyPortfolio/PyPortfolioOpt
- **License:** MIT
- **Stars/Activity:** Widely used; actively maintained.
- **What it does:** Financial portfolio optimization including classical efficient frontier, Black-Litterman, HRP, and Hierarchical Clustering. Well-documented and beginner-friendly.
- **Relevant ideas to borrow:**
  1. **HRP implementation** — the project likely already has a similar implementation. PyPortfolioOpt's version is a useful reference for debugging or extending.
  2. **Black-Litterman with views** — could be used to incorporate regime-conditioned return estimates into the optimization. If the regime engine outputs "expected alpha" in each state, Black-Litterman could formally incorporate these as views.
  3. **Covariance shrinkage (Ledoit-Wolf)** — using shrinkage covariance for HRP inputs may improve stability of the sector sleeve allocation.
- **Code usable:** MIT license — inspiration and reference.
- **Add as dependency?** Possibly, as a lightweight addition for covariance shrinkage.
- **Bottleneck targeted:** Construction stability; HRP robustness with small covariance matrices.
- **Implementation risk:** Low.
- **Recommended action:** **Review for covariance shrinkage.** The project's HRP may benefit from Ledoit-Wolf shrinkage for the sector covariance matrix (only 11 sector ETFs — small N, potentially unstable covariance). No dependency needed; the implementation is simple.

---

## Repo 4 — cvxportfolio

- **URL:** https://github.com/cvxgrp/cvxportfolio
- **License:** Apache 2.0
- **Stars/Activity:** Actively maintained by Stanford/CVXPY team.
- **What it does:** Object-oriented library for portfolio optimization and backtesting. Implements models from the Boyd et al. (2024) paper on multi-period portfolio optimization. Key feature: multi-period convex optimization with transaction cost modeling, risk aversion parameters, and holding cost constraints.
- **Relevant ideas to borrow:**
  1. **Transaction cost-aware optimization** — cvxportfolio explicitly models transaction costs in the optimizer, which could reduce turnover-driven performance drag (the project's sector sleeve has meaningful weekly turnover ≈5–16%).
  2. **Risk aversion parameter** — use a state-conditioned risk aversion parameter to tune the offensive budget. High risk aversion in fragile/transition states, low in confirmed good states.
  3. **Multi-period optimization** — instead of weekly rebalancing independently, optimize over a rolling 4–8 week horizon. This could reduce churn in the sector sleeve.
- **Code usable:** Apache 2.0 — inspiration.
- **Add as dependency?** Not now. CVXPY adds significant overhead.
- **Bottleneck targeted:** Turnover; BIL drag; sector sleeve stability.
- **Implementation risk:** High (complex solver dependencies).
- **Recommended action:** **Save for later.** Multi-period optimization and transaction cost modeling are intellectually interesting but complex to integrate. Worth exploring if turnover is identified as a primary drag.

---

## Repo 5 — vectorbt

- **URL:** https://github.com/polakowo/vectorbt
- **License:** Elastic (BSL-1.1 or vectorbt Pro)
- **Stars/Activity:** Actively maintained. Commercial Pro version available.
- **What it does:** High-performance backtesting framework using NumPy/Numba. Enables fast vectorized backtests across many parameter combinations simultaneously.
- **Relevant ideas to borrow:**
  1. **Fast parameter sweep** — could be used to do a comprehensive parameter sweep of sector sleeve budget (10%, 15%, 20%, 25%) × activation signal threshold combinations in a single vectorized backtest. Would make the Phase 4B/7 type experiments much faster.
  2. **Monte Carlo simulation** — built-in Monte Carlo resampling for portfolio return paths, useful for stress testing the regime assumptions.
- **Code usable:** BSL-1.1 (free for non-commercial). Inspiration for vectorized backtest patterns.
- **Add as dependency?** No. Would need a major refactor of the existing pipeline.
- **Bottleneck targeted:** Research velocity (not a strategy bottleneck).
- **Implementation risk:** Very high (full pipeline refactor).
- **Recommended action:** **Reject.** Not worth the migration cost. The existing build pipeline works.

---

## Repo 6 — quantstats / empyrical

- **URL (quantstats):** https://github.com/ranaroussi/quantstats
- **URL (empyrical):** https://github.com/quantopian/empyrical
- **License:** Apache 2.0
- **What they do:** Performance analytics and portfolio statistics. quantstats generates tearsheets; empyrical computes alpha, beta, Sharpe, Calmar, max drawdown, etc.
- **Relevant ideas to borrow:**
  1. **Underwater/drawdown plotting** — useful for dashboard visualization showing drawdown periods alongside regime states.
  2. **Rolling alpha/Sharpe** — track rolling 52-week Sharpe by state to validate regime engine over time.
  3. **Benchmark comparison** — both libraries support multi-benchmark comparison that could be integrated with the dashboard.
- **Code usable:** Apache 2.0.
- **Add as dependency?** quantstats is already likely available in the project environment. Useful for reporting.
- **Bottleneck targeted:** Research validation; dashboard display quality.
- **Recommended action:** **Use for reporting.** No strategy bottleneck; useful for audit reports and dashboard.

---

## Repo 7 — hmmlearn

- **URL:** https://github.com/hmmlearn/hmmlearn
- **License:** BSD-3-Clause
- **Stars/Activity:** Actively maintained.
- **What it does:** Hidden Markov Models in Python. Supports Gaussian HMM (continuous observations), Multinomial HMM, and custom emission models.
- **Relevant ideas to borrow:**
  1. **Gaussian HMM for regime detection** — train a 3-state or 5-state Gaussian HMM on weekly return + volatility + breadth features to identify regimes probabilistically.
  2. **Viterbi decoding** — generates the most likely state sequence given observations; could be compared against the project's causal classifier.
  3. **State posterior probabilities** — HMM outputs P(state | observations) at each time step, providing a richer input to the allocator than a hard state label.
- **Code usable:** BSD-3-Clause. Inspiration; implementation would need causal (non-lookahead) training.
- **Add as dependency?** Possibly for a future HMM sprint.
- **Bottleneck targeted:** State classification quality; calm_trend sub-classification.
- **Implementation risk:** Medium. Requires careful walk-forward training to avoid lookahead bias.
- **Recommended action:** **Save for later.** Overfitting risk is real with weekly ETF data. Would be more tractable with PIT stock breadth expanding the feature space.

---

## Repo 8 — sktime / statsmodels Markov Switching

- **URL (statsmodels):** https://www.statsmodels.org/stable/markov_regression.html
- **License:** BSD-3-Clause
- **What it does:** statsmodels implements Hamilton's Markov Switching Regression and Markov Switching Autoregression, allowing direct comparison with the project's causal classifier.
- **Relevant ideas to borrow:**
  1. **Markov Switching Autoregression on returns** — model the return series as switching between a high-mean/low-vol and low-mean/high-vol regime. Provides transition probabilities automatically.
  2. **Compare smooth vs filtered probabilities** — a useful diagnostic for how well the causal classifier aligns with the econometrically estimated probabilities.
- **Add as dependency?** Already available in statsmodels (likely already in the project environment).
- **Bottleneck targeted:** State classification validation.
- **Recommended action:** **Use as diagnostic.** Run a 2-state or 3-state Markov Switching model as a cross-check on the current regime labels. If the econometric model and the causal classifier assign different labels to calm_trend, investigate which is better calibrated.

---

## Repo 9 — alpha_vantage / yfinance / pandas_datareader

These are data fetching libraries, not strategy libraries. Mentioned for completeness.

- **yfinance:** Used in Phase 5A-Free diagnostic for stock price downloads (503 S&P 500 tickers). Worked successfully after adding browser User-Agent headers.
- **Recommendation for PIT data:** yfinance is not PIT-safe (uses current prices + current constituents). Do not use for production stock breadth signals. Use Norgate, WRDS/CRSP, or Sharadar when budget allows.

---

## Repo 10 — Tactical Asset Allocation repos on GitHub

Several repos implement TAA strategies (Dual Momentum, VAA, DAA, Protective Momentum):

- **TuringTrader.com Antonacci Dual Momentum:** https://www.turingtrader.com/portfolios/antonacci-dual-momentum/ — good reference implementation.
- **Allocate Smartly:** https://allocatesmartly.com/ — tracks 60+ TAA strategies with updated performance. Useful benchmark for comparing this project's returns against published TAA strategies.
- **Note:** Allocate Smartly data is paywalled. Do not scrape; use for strategy identification only.

**Recommended action:** Check this project's returns against published TAA strategies on Allocate Smartly to contextualize the 7.14%–7.88% return arc. The benchmark question: is 7.88% / 0.926 Sharpe competitive with similar mandates?

---

## Summary: Recommended Library Actions

| Repo | Action | Why |
|------|--------|-----|
| skfolio | Borrow HERC/ERC concept, implement manually | Improve sector sleeve construction |
| Riskfolio-Lib | Borrow CVaR budgeting + drawdown constraint concepts | Address Sharpe-return tradeoff |
| PyPortfolioOpt | Borrow Ledoit-Wolf covariance shrinkage | Stabilize HRP with small sector universe |
| cvxportfolio | Save for later (transaction cost optimization) | Complex; useful if turnover is primary drag |
| vectorbt | Reject (full refactor required) | Not worth migration cost |
| quantstats | Use for reporting | Dashboard and audit reporting |
| hmmlearn | Save for later (PIT data) | Overfitting risk; better with richer features |
| statsmodels MS | Use as diagnostic | Cross-check regime labels |
