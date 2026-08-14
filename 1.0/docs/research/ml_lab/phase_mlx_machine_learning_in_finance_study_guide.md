# Phase MLX — Machine Learning in Finance Study Guide

Research-only educational guide for the Phase MLX experimental hard-ML lab.

This document is not production guidance. It is a study guide and research backlog for understanding machine learning in finance, especially as it relates to a systematic ETF quant portfolio. All Phase MLX work remains experimental, yfinance-based where applicable, high-overfitting-risk, and not production-valid.

## 1. Executive Summary

Machine learning in finance tries to learn useful structure from noisy, incomplete, non-stationary market data. The goal may be to forecast returns, rank assets, forecast risk, detect regimes, improve portfolio construction, estimate trading costs, filter existing signals, or automate allocation decisions. In a portfolio project, ML is not only about predicting "what goes up." It is about improving decisions under uncertainty: what to own, how much to own, when to reduce risk, when to trust an offensive sleeve, and when to do nothing.

Finance ML is hard because the signal-to-noise ratio is low, markets adapt, labels are unstable, regimes change, transaction costs matter, and the historical sample is short relative to model complexity. A model can look excellent in a backtest because it found a period-specific exposure, a data leak, a survivorship artifact, or a lucky hyperparameter. This is why walk-forward validation, seed robustness, cost sensitivity, and point-in-time data are not optional details; they are the core of the problem.

Prediction accuracy is not enough. A model with better classification accuracy may still produce worse portfolios if it is wrong during drawdowns, trades too much, concentrates in fragile assets, or improves average return while worsening CVaR. The actual objective for this ETF project is closer to: improve risk-adjusted return after costs while controlling drawdown, CVaR, turnover, regime exposure, and implementation realism.

Data quality matters more than architecture novelty. In finance, point-in-time data means the dataset only contains information that would have been known at the historical decision date. Without point-in-time fundamentals, index membership, earnings release dates, corporate actions, and delisting-aware returns, models can accidentally learn the future. For this project, the biggest likely upgrade is not a larger neural network; it is point-in-time stock breadth and stock-level cross-sectional data through WRDS/CRSP/Compustat-style sources.

Connection to the ETF portfolio project:

- The core ETF strategy already contains economically grounded defensive logic.
- Raw ML has tended to increase risk.
- MLX-5C sequence models are the strongest ML component so far.
- MLX-9 suggests the cleanest production-adjacent pattern: use ML as a small sleeve or filter around a core strategy, not as a replacement.
- The next learning frontier is not "more models"; it is better problem framing: cross-asset ranking, decision-focused learning, self-supervised regime embeddings, point-in-time breadth, and stricter validation.

## 2. How ML is Used in Finance

### Return Prediction

**Task:** Estimate future return for an asset over a horizon such as next day, next week, next month, or next quarter.

**Common models:** Linear regression, Ridge/Lasso/ElasticNet, random forests, gradient boosting, XGBoost, LightGBM, MLPs, LSTM/GRU, Temporal CNN, Transformers, factor models, autoencoder asset-pricing models.

**Data needed:** Price/volume history, fundamentals, macro data, analyst estimates, flows, sentiment, sector/industry data, and point-in-time identifiers.

**Why it helps:** Expected return forecasts are natural inputs into ranking, allocation, and optimization.

**Why it can fail:** Returns are extremely noisy; MSE can reward small average improvements that do not translate into better portfolios; forecasts can be directionally weak but still produce overconfident allocations.

**ETF project application:** Weekly forward-return prediction was tested in MLX-3/4. It worked as infrastructure but was weaker than sequence ranking and defensive overlays.

### Cross-Sectional Ranking

**Task:** Rank assets relative to each other at date `t`, instead of forecasting exact returns.

**Common models:** Gradient boosting rankers, LambdaMART, XGBoost ranking objectives, LightGBM ranking, pairwise/listwise neural ranking losses, cross-sectional Transformers, graph attention networks.

**Data needed:** A broad cross-section of assets at each date, features known at date `t`, and future relative-return labels for training.

**Why it helps:** Portfolio construction often only needs "which assets are better than others," not exact return magnitude.

**Why it can fail:** Ranking can learn persistent sector/country/style bias; top-ranked names may be crowded, illiquid, or high beta; validation must be chronological and grouped by date.

**ETF project application:** This is likely one of the most promising next directions because the ETF task is naturally "rank ETF candidates weekly."

### Risk Forecasting

**Task:** Forecast volatility, drawdown risk, VaR/CVaR, correlation, or stress probability.

**Common models:** GARCH/GAS, EWMA, random forests, gradient boosting, quantile regression, distributional neural networks, time-series foundation models fine-tuned for quantiles.

**Data needed:** Return histories, realized volatility, options/implied volatility, credit spreads, macro stress variables, market breadth, liquidity.

**Why it helps:** Better risk forecasts can improve position sizing, volatility targeting, and defensive overlays.

**Why it can fail:** Tail events are rare; models can underestimate regime shifts; risk forecasts can look good on average while failing in crashes.

**ETF project application:** Directly relevant to the BIL fallback, defensive overlay, volatility targeting, and drawdown kill-switch ideas.

### Regime Detection

**Task:** Identify market states such as calm trend, neutral mixed, fragile recovery, confirmed recovery, or stressed panic.

**Common models:** HMMs, clustering, tree classifiers, logistic models, autoencoders, contrastive embeddings, state-space models, sequence models.

**Data needed:** Market returns, breadth, volatility, credit, rates, macro, correlation, sector leadership, trend persistence.

**Why it helps:** Many strategies work only in certain regimes. Regime filters can reduce drawdowns and prevent overexposure in hostile environments.

**Why it can fail:** Regime definitions are subjective; labels can be unstable; state boundaries can be overfit to past crises.

**ETF project application:** Already central to the core project. MLX should learn from the regime engine rather than replace it.

### Portfolio Optimization

**Task:** Turn predictions, risks, constraints, and costs into portfolio weights.

**Common models:** Mean-variance optimization, risk parity, HRP/HERC, CVaR optimization, Black-Litterman, robust optimization, differentiable optimization layers, decision-focused learning.

**Data needed:** Expected returns, covariance estimates, risk constraints, transaction cost assumptions, turnover constraints, asset group definitions.

**Why it helps:** Allocation quality can matter more than raw alpha forecasts.

**Why it can fail:** Optimizers amplify estimation error. Small forecast differences can create unstable weights.

**ETF project application:** Decision-focused learning is a strong next frontier because the project objective is Sharpe/drawdown/CVaR, not only prediction accuracy.

### Execution / Trading Cost Modeling

**Task:** Estimate slippage, spread, market impact, turnover drag, and capacity.

**Common models:** Linear cost models, spread models, random forests, gradient boosting, order-book models, execution RL.

**Data needed:** Bid/ask, volume, spreads, trade sizes, rebalance timing, liquidity conditions.

**Why it helps:** A high-turnover signal can disappear after realistic costs.

**Why it can fail:** Retail/proxy data often lacks real execution detail; historical spreads may not match future execution.

**ETF project application:** MLX-5B found cost sensitivity matters. ML signals should include conservative turnover penalties.

### Anomaly Detection

**Task:** Identify unusual market states, data errors, extreme exposures, or strategy behavior drift.

**Common models:** Isolation forests, autoencoders, robust z-scores, clustering, change-point detection.

**Data needed:** Returns, volatility, correlations, weights, drawdowns, cost history, model score distributions.

**Why it helps:** Detects when a strategy is operating outside its training distribution.

**Why it can fail:** Anomaly detection can be noisy and hard to calibrate.

**ETF project application:** Useful for model drift monitoring and ML shadow governance.

### Factor Discovery

**Task:** Learn latent drivers of returns or discover nonlinear versions of known factors.

**Common models:** PCA, IPCA, autoencoders, variational autoencoders, tree-based interactions, deep asset-pricing models.

**Data needed:** Broad cross-section, long histories, fundamentals, characteristics, returns.

**Why it helps:** Can explain what the model is really loading on.

**Why it can fail:** Latent factors can be unstable or economically meaningless.

**ETF project application:** Helpful as an audit tool: is ML just learning tech momentum, dollar exposure, commodities, or duration?

### News/Text/Sentiment

**Task:** Convert unstructured text into signals: sentiment, uncertainty, topic exposure, risk warnings.

**Common models:** FinBERT, FinGPT, BloombergGPT-style LLMs, embedding models, event classifiers.

**Data needed:** Timestamped news, filings, earnings calls, macro releases, social media, reliable publication times.

**Why it helps:** Text may capture information not in price features.

**Why it can fail:** Data licensing, timestamps, lookahead, hallucinated labels, and sentiment overfitting are serious risks.

**ETF project application:** Later-stage overlay only; useful for macro/regime context but not urgent before PIT market data.

### Reinforcement Learning

**Task:** Learn allocation actions by interacting with a simulated market environment.

**Common models:** PPO, SAC, A2C, DQN variants, Transformer-RL hybrids.

**Data needed:** Reliable environment, returns, costs, constraints, action space, state observations.

**Why it helps:** RL directly optimizes sequential decisions and can include turnover/drawdown penalties.

**Why it can fail:** Finance RL is extremely overfit-prone; environments are short, non-stationary, and easy to exploit in-sample.

**ETF project application:** MLX-8 built useful infrastructure, but PPO underperformed. Keep RL as a research track, not an ensemble core.

### Risk Management and Drawdown Control

**Task:** Decide when to reduce exposure, use BIL/cash, cap volatility, or pause offensive signals.

**Common models:** Rule-based overlays, logistic filters, meta-labeling, regime classifiers, volatility targeting, drawdown kill switches.

**Data needed:** Regime indicators, volatility, breadth, trend, drawdown state, model confidence.

**Why it helps:** A modest return signal can become useful if risk is controlled.

**Why it can fail:** Risk filters can miss crashes, overreact after drawdowns, or suppress recovery participation.

**ETF project application:** This has been the most important MLX lesson: ML works best when wrapped inside the core defensive logic.

## 3. ML Method Taxonomy

### Linear Models and Regularization

**Plain English:** Linear models learn weighted sums of features. Regularization penalizes large coefficients so the model does not chase noise.

**Problems solved:** Baseline return prediction, classification, meta-labeling, interpretable filtering.

**Finance use cases:** Factor models, recession/risk filters, cross-sectional return prediction, probability of drawdown.

**Data requirements:** Clean numeric features, enough samples, stable definitions.

**Strengths:** Interpretable, fast, hard to overfit compared with deep models, excellent benchmark.

**Weaknesses:** Miss nonlinear interactions unless engineered.

**Overfitting risks:** Feature mining, unstable coefficients, leakage through engineered variables.

**Papers/repos to read:** [Gu, Kelly, and Xiu, Empirical Asset Pricing via Machine Learning](https://academic.oup.com/rfs/article/33/5/2223/5758276); scikit-learn docs.

**Already tried in MLX:** Ridge, ElasticNet, Logistic Regression in MLX-3 and MLX-7.

**Next experiment:** Use logistic meta-labels for "trust production/Phase 4B" with stricter walk-forward selection.

### Tree Models and Boosting

**Plain English:** Trees split the feature space into rules. Boosting combines many weak trees to model nonlinear interactions.

**Problems solved:** Tabular prediction, ranking, feature importance, nonlinear regime filters.

**Finance use cases:** Return ranking, risk classification, cost modeling, factor interaction mining.

**Data requirements:** Tabular features with careful time splits.

**Strengths:** Strong on tabular data, handles nonlinearities, gives feature importance.

**Weaknesses:** Can overfit regime-specific patterns and spurious cross-sectional quirks.

**Overfitting risks:** Too many trees, shallow validation, target leakage, repeated feature selection.

**Papers/repos to read:** [LightGBM](https://github.com/microsoft/LightGBM), [XGBoost](https://github.com/dmlc/xgboost), [Qlib](https://github.com/microsoft/qlib).

**Already tried in MLX:** Random Forest, Gradient Boosting, XGBoost, LightGBM in MLX-3 and meta-label tree filters in MLX-7.

**Next experiment:** Learning-to-rank with grouped-by-date LightGBM/XGBoost objectives.

### Neural Networks / MLP

**Plain English:** An MLP learns nonlinear combinations of features through layers of weighted transformations.

**Problems solved:** Nonlinear tabular prediction and probability scoring.

**Finance use cases:** Return prediction, meta-labeling, risk classification.

**Data requirements:** Standardized numeric features, enough samples, regularization.

**Strengths:** Flexible, can combine many weak signals.

**Weaknesses:** Often less reliable than boosting on tabular data; sensitive to seeds and scaling.

**Overfitting risks:** Hidden layers memorize period-specific patterns.

**Papers/repos to read:** [Deep Learning in Asset Pricing](https://academic.oup.com/rfs/article/37/8/2545/7505230), [Deep Learning in Characteristics-Sorted Factor Models](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4567348).

**Already tried in MLX:** MLP with dropout in MLX-4.

**Next experiment:** Calibrated MLP uncertainty, not just point scores.

### CNNs / Temporal CNN

**Plain English:** Temporal CNNs scan time windows with filters that detect local patterns such as momentum bursts, volatility changes, or reversals.

**Problems solved:** Sequence classification and forecasting with efficient parallel training.

**Finance use cases:** Price-pattern classification, volatility regimes, short history feature extraction.

**Data requirements:** Fixed-length sequences per asset.

**Strengths:** Faster and often more stable than RNNs.

**Weaknesses:** Less naturally suited to long dependencies unless designed carefully.

**Overfitting risks:** Learning chart-pattern noise.

**Papers/repos to read:** Time-series CNN/TCN literature; Qlib model zoo examples.

**Already tried in MLX:** Temporal CNN in MLX-5/5C.

**Next experiment:** Cross-sectional TCN with ETF interactions, not one ETF at a time.

### RNNs / LSTM / GRU

**Plain English:** RNNs process sequences step by step. LSTM and GRU cells include gates that help remember or forget information.

**Problems solved:** Sequential prediction where order matters.

**Finance use cases:** Return classification, regime detection, volatility forecasting.

**Data requirements:** Historical sequences and careful walk-forward validation.

**Strengths:** Natural fit for time series.

**Weaknesses:** Slower than CNNs/Transformers and sensitive to seeds.

**Overfitting risks:** Memorizing one market era.

**Papers/repos to read:** [DeepDow](https://github.com/jankrepl/deepdow) for end-to-end deep portfolio examples; Qlib sequence models.

**Already tried in MLX:** LSTM and GRU in MLX-5/5C.

**Next experiment:** Multi-seed cross-asset GRU ranker with shared information across ETFs.

### Transformers / Attention

**Plain English:** Attention lets a model decide which parts of the input sequence matter most. A Transformer uses attention layers to model relationships across time steps.

**Problems solved:** Long-context sequence modeling and flexible representation learning.

**Finance use cases:** Time-series forecasting, market regime embeddings, return ranking, text-event fusion.

**Data requirements:** More data than simple models; sequences; careful regularization.

**Strengths:** Flexible and state of the art in many domains.

**Weaknesses:** Can be overkill for weekly ETF data.

**Overfitting risks:** High parameter count relative to financial sample size.

**Papers/repos to read:** [Attention Is All You Need in Asset Pricing](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4967865), [MASTER: Market-Guided Stock Transformer](https://arxiv.org/abs/2312.15235).

**Already tried in MLX:** Small Transformer encoder in MLX-6.

**Next experiment:** Cross-sectional attention ranker rather than per-ETF sequence Transformer.

### Cross-Sectional Attention

**Plain English:** Cross-sectional attention models relationships among assets at the same date. Instead of each ETF being predicted alone, SPY, QQQ, TLT, GLD, sectors, and international ETFs can influence each other.

**Problems solved:** Relative ranking, sector rotation, common factor awareness, crowding/dispersion signals.

**Finance use cases:** Stock selection, ETF ranking, asset pricing, cross-asset allocation.

**Data requirements:** A panel of assets by date, ideally larger than the ETF universe.

**Strengths:** Matches the portfolio problem: select among assets.

**Weaknesses:** Needs enough cross-section and strict date grouping.

**Overfitting risks:** Learning transient correlations.

**Papers/repos to read:** [MASTER](https://arxiv.org/abs/2312.15235); [Self-Attention-Based Approach to Cross-Sectional Return Forecasting](https://arxiv.org/abs/2407.18901).

**Already tried in MLX:** Not directly. Current sequence models process ETF histories mostly independently.

**Next experiment:** Cross-Asset Attention Ranker using weekly ETF panel and masked date-wise ranking loss.

### Graph Neural Networks

**Plain English:** GNNs model assets as nodes and relationships as edges. Edges can represent sectors, correlations, supply chains, common factors, or holdings overlap.

**Problems solved:** Learning from asset relationships.

**Finance use cases:** Stock return prediction, sector contagion, correlation-aware ranking, risk propagation.

**Data requirements:** Reliable graph structure and asset features.

**Strengths:** Encodes economic relationships beyond flat feature tables.

**Weaknesses:** Graph definition can dominate results.

**Overfitting risks:** Edges built from future correlations or current index membership create leakage.

**Papers/repos to read:** [Heterogeneous Graph Attention Networks for Stock Movement Prediction](https://arxiv.org/abs/2402.06680), [Attention-Based Dynamic Graph Neural Network for Asset Pricing](https://arxiv.org/abs/2301.10727), [HGAIT](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5460481).

**Already tried in MLX:** No.

**Next experiment:** ETF graph from asset class, sector, and rolling correlation edges.

### Autoencoders

**Plain English:** Autoencoders compress data into a smaller representation and reconstruct it. The middle representation can become a latent factor.

**Problems solved:** Dimensionality reduction, latent factors, denoising, anomaly detection.

**Finance use cases:** Factor discovery, regime embeddings, nonlinear risk factors.

**Data requirements:** Large panels; stable features.

**Strengths:** Useful for unsupervised representation learning.

**Weaknesses:** Learned factors may be hard to interpret.

**Overfitting risks:** Reconstructing noise.

**Papers/repos to read:** [Autoencoder Asset Pricing Models](https://www.aqr.com/Insights/Research/Working-Paper/Autoencoder-Asset-Pricing-Models), [Deep Learning in Asset Pricing](https://academic.oup.com/rfs/article/37/8/2545/7505230).

**Already tried in MLX:** Optional autoencoder was discussed but not a main result.

**Next experiment:** Self-supervised regime embeddings from ETF and stock breadth panels.

### Contrastive / Self-Supervised Learning

**Plain English:** Self-supervised learning creates training tasks from the data itself. Contrastive learning pulls related examples together and pushes unrelated examples apart.

**Problems solved:** Representation learning when labels are noisy.

**Finance use cases:** Regime embeddings, asset embeddings, similarity search, pretraining before ranking.

**Data requirements:** Many unlabeled sequences or panels.

**Strengths:** Avoids relying entirely on noisy forward-return labels.

**Weaknesses:** Pretext task may not align with portfolio value.

**Overfitting risks:** Learning augmentations instead of economics.

**Papers/repos to read:** [Contrastive Learning of Asset Embeddings from Financial Time Series](https://arxiv.org/abs/2409.15727), [TS-TCC](https://arxiv.org/abs/2106.14112), [Financial Time Series Representation Learning](https://www.sciencedirect.com/science/article/abs/pii/S0950705121003500).

**Already tried in MLX:** Not directly.

**Next experiment:** Contrastive regime embeddings using adjacent weeks as positives and different regimes as negatives.

### Time-Series Foundation Models

**Plain English:** Foundation models are pretrained on large collections of time series and adapted to new tasks.

**Problems solved:** Forecasting, embedding, anomaly detection, few-shot transfer.

**Finance use cases:** Volatility forecasting, VaR forecasting, representation extraction, macro/market embeddings.

**Data requirements:** Large pretraining corpora; finance-specific data improves relevance.

**Strengths:** Can transfer general time-series patterns.

**Weaknesses:** Off-the-shelf general models may perform poorly in finance.

**Overfitting risks:** False confidence from a famous model; mismatch between pretraining data and market data.

**Papers/repos to read:** [Re(Visiting) Time Series Foundation Models in Finance](https://arxiv.org/abs/2509.08870), [A Time-Series Foundation AI Model for Value-at-Risk Forecasting](https://arxiv.org/abs/2410.19342), [Chronos](https://arxiv.org/abs/2403.07815), [MOMENT](https://github.com/moment-timeseries-foundation-model/moment), [TimesFM](https://github.com/google-research/timesfm).

**Already tried in MLX:** No.

**Next experiment:** Use TS foundation embeddings as inputs to the ETF ranker, not as direct forecasts.

### Meta-Labeling

**Plain English:** Meta-labeling trains a second model to decide when to trust a base strategy or signal.

**Problems solved:** Filtering, position sizing, switch decisions.

**Finance use cases:** Strategy activation, production-vs-Phase-4B switch, ML sleeve activation, bad-week avoidance.

**Data requirements:** A base strategy, historical outcomes, and known-at-date state features.

**Strengths:** Often safer than raw return prediction because it asks a narrower question.

**Weaknesses:** Labels are still noisy and can overfit to known drawdown periods.

**Overfitting risks:** Threshold mining.

**Papers/repos to read:** [Lopez de Prado, Advances in Financial Machine Learning](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086); [mlfinlab documentation](https://hudsonthames.org/mlfinlab/).

**Already tried in MLX:** MLX-7.

**Next experiment:** Walk-forward triple-barrier meta-labeling around Phase 4B and ML sleeve activation.

### Triple-Barrier Labeling

**Plain English:** Triple-barrier labels outcomes based on which event happens first: profit target, stop loss, or time limit.

**Problems solved:** Event-based labeling that considers path risk, not just end return.

**Finance use cases:** Trade filtering, stop/target learning, meta-labeling.

**Data requirements:** High-quality price paths and realistic holding period assumptions.

**Strengths:** Closer to trading decisions than simple forward returns.

**Weaknesses:** Barrier parameters can be mined.

**Overfitting risks:** Choosing barriers after seeing results.

**Papers/repos to read:** Lopez de Prado's triple-barrier method; [mlfinpy labeling docs](https://mlfinpy.readthedocs.io/en/stable/Labelling.html).

**Already tried in MLX:** No. MLX-7 used simpler 4-week labels.

**Next experiment:** Triple-barrier labels for Phase 4B switch and ML sleeve risk.

### Learning-to-Rank

**Plain English:** Learning-to-rank trains models to order items. It optimizes pairwise or listwise ranking quality instead of prediction error.

**Problems solved:** Asset selection when relative rank matters more than exact forecast.

**Finance use cases:** Stock/ETF selection, sector rotation, top-N portfolio construction.

**Data requirements:** Date-grouped cross-sectional samples and future rank labels.

**Strengths:** Directly aligns with top-N ETF selection.

**Weaknesses:** Ranking losses can ignore portfolio risk.

**Overfitting risks:** Reusing the same validation window to tune rank objectives.

**Papers/repos to read:** [LambdaRankIC](https://arxiv.org/abs/2506.20653), [LightGBM ranking](https://lightgbm.readthedocs.io/), [XGBoost ranking](https://xgboost.readthedocs.io/).

**Already tried in MLX:** Indirectly via ranking model scores, not explicit ranking losses.

**Next experiment:** Date-grouped LambdaMART ETF selector.

### Decision-Focused Learning

**Plain English:** Instead of training a model to predict labels accurately, train it to produce inputs that lead to good decisions.

**Problems solved:** Prediction-optimization mismatch.

**Finance use cases:** Portfolio optimization, allocation, turnover-aware ranking, risk-adjusted objectives.

**Data requirements:** Differentiable or approximated decision layer and clear objective.

**Strengths:** Aligns training with portfolio value.

**Weaknesses:** Harder to implement and debug.

**Overfitting risks:** Optimizing a backtest objective too directly.

**Papers/repos to read:** [Decision-Focused Learning: Foundations, State of the Art, Benchmark and Future Opportunities](https://arxiv.org/abs/2307.13565), [Smart Predict-and-Optimize for Hard Combinatorial Optimization Problems](https://arxiv.org/abs/1711.08005), [Differentiable Convex Optimization Layers](https://arxiv.org/abs/1910.12430).

**Already tried in MLX:** No direct decision-focused training. MLX-9 is still predict-then-combine.

**Next experiment:** Differentiable mean-variance/CVaR layer with turnover penalty.

### Differentiable Optimization Layers

**Plain English:** Put an optimizer inside a neural network so gradients can flow through the final portfolio decision.

**Problems solved:** End-to-end learning of forecasts that matter for allocation.

**Finance use cases:** Mean-variance learning, constrained portfolio optimization, transaction-cost-aware allocation.

**Data requirements:** Differentiable objective, stable constraints, clean covariance estimates.

**Strengths:** Excellent educational bridge between ML and portfolio theory.

**Weaknesses:** Numerical stability and speed can be difficult.

**Overfitting risks:** Optimizer can exploit tiny forecast errors.

**Papers/repos to read:** [cvxpylayers](https://github.com/cvxgrp/cvxpylayers), [DeepDow](https://github.com/jankrepl/deepdow), [PyEPO](https://khalil-research.github.io/PyEPO/).

**Already tried in MLX:** No.

**Next experiment:** Small differentiable long-only allocation layer trained on weekly ETF returns.

### Reinforcement Learning

**Plain English:** RL learns a policy that maps observations to actions using rewards from a simulated environment.

**Problems solved:** Sequential allocation and dynamic risk control.

**Finance use cases:** Portfolio allocation, execution, market making, dynamic hedging.

**Data requirements:** Realistic environment, costs, constraints, action space, state features.

**Strengths:** Can directly include turnover and drawdown penalties.

**Weaknesses:** Very overfit-prone; simulation is not the market.

**Overfitting risks:** Learning quirks of one historical path.

**Papers/repos to read:** [FinRL](https://github.com/AI4Finance-Foundation/FinRL), [An Evaluation of Reinforcement Learning Based Portfolio Management Strategies](https://arxiv.org/abs/2306.14714), [Deep Reinforcement Learning for Portfolio Management](https://arxiv.org/abs/2011.09617).

**Already tried in MLX:** PPO allocator in MLX-8 underperformed.

**Next experiment:** Only revisit RL after improving environment realism and using RL as overlay/sizing, not full allocator.

### Ensemble Learning

**Plain English:** Combine multiple models or strategies to reduce reliance on one fragile signal.

**Problems solved:** Model risk, instability, noisy forecasts.

**Finance use cases:** Rank averaging, stacking, model averaging, strategy blending.

**Data requirements:** Independent model outputs and validation selection.

**Strengths:** Can improve stability if models make different errors.

**Weaknesses:** Combining weak models can dilute signal.

**Overfitting risks:** Hindsight weighting.

**Papers/repos to read:** General ensemble learning literature; Qlib model pipelines; sklearn stacking.

**Already tried in MLX:** MLX-9.

**Next experiment:** Calibrated stacking using validation-only weights and uncertainty penalties.

### LLM/Text-Based Finance Models

**Plain English:** LLMs and text models convert documents into structured information such as sentiment, topics, risk, or event signals.

**Problems solved:** Extracting information from news, filings, calls, and macro text.

**Finance use cases:** Sentiment overlays, risk event detection, earnings-call analysis, macro narrative features.

**Data requirements:** Timestamped text, reliable release times, embeddings, licensing.

**Strengths:** Captures information not in price data.

**Weaknesses:** Hard to validate; text data pipelines are expensive.

**Overfitting risks:** Lookahead through publication timestamps or revised documents.

**Papers/repos to read:** [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT), [BloombergGPT](https://arxiv.org/abs/2303.17564), [FinBERT](https://arxiv.org/abs/1908.10063), [Financial sentiment analysis survey](https://arxiv.org/abs/2411.13080).

**Already tried in MLX:** No.

**Next experiment:** Later-stage macro/news sentiment overlay, not before PIT data.

## 4. Recent Papers and What They Teach Us

This section emphasizes 2020-2026 work, especially 2023-2026. Some items are peer-reviewed journal papers; some are arXiv/SSRN preprints. Treat preprints as learning inputs, not settled evidence.

### Time-Series Foundation Models in Finance

#### Re(Visiting) Time Series Foundation Models in Finance

- **Authors/year:** Eghbal Rahimikia, Hao Ni, Weiguan Wang, 2025.
- **Link:** [arXiv](https://arxiv.org/abs/2509.08870)
- **Method category:** Time-series foundation models in finance.
- **What it does:** Evaluates general and finance-specific time-series foundation models on financial prediction tasks.
- **Data:** Financial time-series benchmarks; paper emphasizes financial sequence data rather than generic forecasting only.
- **Main finding:** The searched abstract indicates that off-the-shelf general time-series foundation models can perform poorly in finance, while finance-specific pretraining can help.
- **Why it matters:** This directly supports a cautious approach: do not assume Chronos/TimesFM-style models transfer automatically to ETF return ranking.
- **Limitations:** New preprint; details and benchmark design need careful reading.
- **Applies to ETF weekly data?** Yes as an embedding or pretraining experiment, but direct zero-shot forecasts should be treated skeptically.
- **Needs PIT stock data?** Not strictly for ETF-only experiments, but PIT stock data would make finance-specific pretraining much more meaningful.
- **Implementation idea:** Compare frozen foundation-model embeddings against MLX-5C sequence features in a validation-only ETF ranker.

#### A Time-Series Foundation AI Model for Value-at-Risk Forecasting

- **Authors/year:** Anubha Goel, Puneet Pasricha, Juho Kanniainen, 2024.
- **Link:** [arXiv](https://arxiv.org/abs/2410.19342)
- **Method category:** Foundation models for financial risk forecasting.
- **What it does:** Studies foundation-model style forecasting for VaR.
- **Data:** Financial time series for risk/quantile forecasting.
- **Main finding:** Foundation models may be more naturally useful for risk and distribution forecasting than for point return prediction.
- **Why it matters:** The ETF project cares about CVaR and drawdown, not just expected return.
- **Limitations:** VaR-specific; portfolio allocation impact must be tested separately.
- **Applies to ETF weekly data?** Yes, especially for volatility/CVaR overlay features.
- **Needs PIT stock data?** No for ETF risk forecasting; yes for stock breadth risk features.
- **Implementation idea:** Foundation-risk embedding or quantile forecast feeding BIL fallback/vol-target rules.

#### Chronos: Learning the Language of Time Series

- **Authors/year:** Ansari et al., 2024.
- **Link:** [arXiv](https://arxiv.org/abs/2403.07815), [GitHub](https://github.com/amazon-science/chronos-forecasting)
- **Method category:** General time-series foundation model.
- **What it does:** Tokenizes time series and trains language-model-style forecasting models.
- **Data:** Large general time-series corpora, not finance-specific by default.
- **Main finding:** General time-series pretraining can improve broad forecasting benchmarks.
- **Why it matters:** Useful baseline for learning foundation-model workflows.
- **Limitations:** Finance transfer is uncertain.
- **Applies to ETF weekly data?** Maybe for embeddings or risk features; direct return forecasts likely fragile.
- **Needs PIT stock data?** No for initial ETF experiment.
- **Implementation idea:** Freeze Chronos features and compare against standard trailing returns/vol.

#### MOMENT: A Family of Open Time-Series Foundation Models

- **Authors/year:** Mononito Goswami et al., 2024.
- **Link:** [GitHub](https://github.com/moment-timeseries-foundation-model/moment), [project page](https://moment-timeseries-foundation-model.github.io/)
- **Method category:** Time-series foundation model.
- **What it does:** Provides open foundation models for forecasting, classification, anomaly detection, and embedding.
- **Data:** Broad time-series pretraining.
- **Main finding:** Foundation models can be adapted across time-series tasks.
- **Why it matters:** Especially interesting for representation learning rather than direct trading.
- **Limitations:** Not finance-specific; setup complexity.
- **Applies to ETF weekly data?** Yes as feature extraction.
- **Needs PIT stock data?** No for ETF-only embeddings.
- **Implementation idea:** Use MOMENT embeddings as input to a date-grouped ETF ranker.

#### TimesFM and TimeGPT

- **Authors/year:** Google Research TimesFM, 2024; Nixtla TimeGPT, 2023-2024.
- **Links:** [TimesFM GitHub](https://github.com/google-research/timesfm), [Nixtla TimeGPT](https://www.nixtla.io/docs/forecasting/timegpt)
- **Method category:** General time-series foundation forecasting.
- **What they do:** Provide pretrained forecasting models or APIs.
- **Data:** Broad time-series corpora.
- **Main finding:** Useful for general forecasting workflows.
- **Why it matters:** Good educational baseline for foundation-model tooling.
- **Limitations:** Not designed specifically for noisy financial returns; TimeGPT is service/API oriented.
- **Applies to ETF weekly data?** Better for volatility/risk than raw returns.
- **Needs PIT stock data?** No for ETF-only tests.
- **Implementation idea:** Forecast realized volatility or drawdown-risk proxies instead of returns.

### Cross-Sectional Attention / Asset Pricing Transformers

#### Attention Is All You Need in Asset Pricing

- **Authors/year:** Authors listed on SSRN page, 2024.
- **Link:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4967865)
- **Method category:** Transformer/attention for asset pricing.
- **What it does:** Uses attention-style models for asset pricing and cross-sectional return prediction.
- **Data:** Cross-section of assets and characteristics.
- **Main finding:** Attention can model complex interactions among characteristics and assets.
- **Why it matters:** ETF ranking is cross-sectional; modeling interactions among assets may beat independent ETF sequence models.
- **Limitations:** Needs careful replication and PIT stock data for strongest version.
- **Applies to ETF weekly data?** Yes, but ETF cross-section is small.
- **Needs PIT stock data?** Strongly recommended for full asset-pricing version.
- **Implementation idea:** Cross-asset attention ranker over ETFs, then later stock-level version after WRDS.

#### MASTER: Market-Guided Stock Transformer

- **Authors/year:** Tong Li, Zhaoyang Liu, and coauthors, 2023.
- **Link:** [arXiv](https://arxiv.org/abs/2312.15235)
- **Method category:** Cross-sectional/time-series Transformer.
- **What it does:** Uses market-guided attention to improve stock price forecasting.
- **Data:** Stock market panels.
- **Main finding:** Market information can guide stock-level Transformer representations.
- **Why it matters:** Your ETF models should not treat each ETF as isolated; market context matters.
- **Limitations:** Stock-level benchmark; ETF universe is smaller.
- **Applies to ETF weekly data?** Yes as a simplified cross-ETF attention experiment.
- **Needs PIT stock data?** Not for ETF prototype, yes for serious stock version.
- **Implementation idea:** Use SPY/QQQ/TLT/GLD/regime tokens as market context in an ETF ranker.

#### Self-Attention-Based Approach to Cross-Sectional Return Forecasting and Portfolio Selection

- **Authors/year:** Xiang Xiao, Xia Hua, Kexin Qin, 2024.
- **Link:** [arXiv](https://arxiv.org/abs/2407.18901)
- **Method category:** Self-attention for cross-sectional return forecasting.
- **What it does:** Applies self-attention to cross-sectional forecasting and portfolio selection.
- **Data:** Cross-sectional financial assets.
- **Main finding:** Attention can help model relationships among assets for ranking/portfolio construction.
- **Why it matters:** Directly aligned with ETF ranking.
- **Limitations:** Requires careful validation and liquidity/cost controls.
- **Applies to ETF weekly data?** Yes, as a learning sprint.
- **Needs PIT stock data?** Not initially, but stronger with stock data.
- **Implementation idea:** Date-wise attention over ETF feature vectors with listwise rank loss.

### Decision-Focused Learning / Differentiable Portfolio Optimization

#### Decision-Focused Learning: Foundations, State of the Art, Benchmark and Future Opportunities

- **Authors/year:** Mandi et al., 2023.
- **Link:** [arXiv](https://arxiv.org/abs/2307.13565)
- **Method category:** Decision-focused learning survey.
- **What it does:** Surveys methods that train predictive models through downstream optimization quality.
- **Data:** General predict-and-optimize settings.
- **Main finding:** When predictions feed decisions, training should consider decision quality.
- **Why it matters:** The ETF objective is allocation quality, not classification accuracy.
- **Limitations:** General survey; finance implementation still needs careful constraints.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No for ETF proof of concept.
- **Implementation idea:** Train expected-return scores through a differentiable long-only optimizer with turnover penalty.

#### Smart Predict-and-Optimize for Hard Combinatorial Optimization Problems

- **Authors/year:** Elmachtoub and Grigas, 2017, still foundational.
- **Link:** [arXiv](https://arxiv.org/abs/1711.08005)
- **Method category:** SPO / predict-then-optimize.
- **What it does:** Introduces a loss that penalizes prediction errors by their decision impact.
- **Data:** General optimization tasks.
- **Main finding:** Decision-aware losses can beat standard prediction losses for downstream decisions.
- **Why it matters:** Explains why forward-return MSE can be the wrong loss.
- **Limitations:** Mapping to portfolio constraints requires care.
- **Applies to ETF weekly data?** Yes conceptually.
- **Needs PIT stock data?** No for ETF prototype.
- **Implementation idea:** Compare MSE-trained ranker vs decision-loss-trained top-N allocator.

#### Differentiable Convex Optimization Layers

- **Authors/year:** Agrawal et al., 2019.
- **Link:** [arXiv](https://arxiv.org/abs/1910.12430), [cvxpylayers GitHub](https://github.com/cvxgrp/cvxpylayers)
- **Method category:** Differentiable optimization layers.
- **What it does:** Allows convex optimization problems to be embedded in neural networks.
- **Data:** Any domain with differentiable convex decision layers.
- **Main finding:** Optimization layers can be trained end-to-end.
- **Why it matters:** Enables differentiable portfolio optimization experiments.
- **Limitations:** Numerical stability, speed, and objective design.
- **Applies to ETF weekly data?** Yes for long-only allocation.
- **Needs PIT stock data?** No initially.
- **Implementation idea:** Differentiable mean-variance/CVaR optimizer with turnover cost.

#### Return Prediction for Mean-Variance Portfolio Selection

- **Authors/year:** Lee, Jeon, Bae, Lee, 2023.
- **Link:** [arXiv](https://arxiv.org/abs/2309.10536)
- **Method category:** Decision-aware portfolio learning.
- **What it does:** Connects return prediction with mean-variance portfolio selection.
- **Data:** Equity/portfolio datasets.
- **Main finding:** Portfolio-aware training can matter more than pure prediction accuracy.
- **Why it matters:** Closely aligned with Phase MLX goals.
- **Limitations:** Mean-variance assumptions may not capture drawdown/CVaR.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No for ETF prototype.
- **Implementation idea:** Compare predicted-return model selected by validation MSE vs validation Sharpe.

### Self-Supervised Financial Time-Series Representation Learning

#### Contrastive Learning of Asset Embeddings from Financial Time Series

- **Authors/year:** Rian Dolphin, Barry Smyth, Ruihai Dong, 2024.
- **Link:** [arXiv](https://arxiv.org/abs/2409.15727)
- **Method category:** Contrastive/self-supervised asset embeddings.
- **What it does:** Learns embeddings of assets from financial time series using contrastive learning.
- **Data:** Asset return time series.
- **Main finding:** Asset similarity/representation can be learned without direct return labels.
- **Why it matters:** Helpful when forward-return labels are noisy.
- **Limitations:** Need to prove embeddings improve portfolios, not just similarity metrics.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No for ETF prototype; yes for broader stock cross-section.
- **Implementation idea:** Learn ETF embeddings and feed them into cross-asset ranker.

#### TS-TCC: Time-Series Representation Learning via Temporal and Contextual Contrasting

- **Authors/year:** Eldele et al., 2021.
- **Link:** [arXiv](https://arxiv.org/abs/2106.14112)
- **Method category:** General contrastive time-series learning.
- **What it does:** Learns representations by contrasting temporal/contextual views.
- **Data:** General time series.
- **Main finding:** Contrastive objectives can improve downstream classification.
- **Why it matters:** Provides a template for regime embeddings.
- **Limitations:** Not finance-specific.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No.
- **Implementation idea:** Pretrain on rolling ETF windows, then classify regimes or rank ETFs.

#### Financial Time Series Representation Learning

- **Authors/year:** ScienceDirect article, 2021.
- **Link:** [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950705121003500)
- **Method category:** Representation learning for financial time series.
- **What it does:** Studies learned representations for financial sequences.
- **Data:** Financial time series.
- **Main finding:** Representation learning can improve downstream financial tasks, but task alignment matters.
- **Why it matters:** Reinforces the embedding-first direction.
- **Limitations:** Needs detailed reading for datasets and validation.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** Optional.
- **Implementation idea:** Compare autoencoder/contrastive embeddings vs hand-built regime features.

### Graph Neural Networks for Stocks and Assets

#### Heterogeneous Graph Attention Networks for Stock Movement Prediction

- **Authors/year:** Yang Qiao, Yiping Xia, Xiang Li, Zheng Li, Yan Ge, 2024.
- **Link:** [arXiv](https://arxiv.org/abs/2402.06680)
- **Method category:** Heterogeneous graph attention.
- **What it does:** Models different types of relationships among stocks.
- **Data:** Stock-level features and graph relations.
- **Main finding:** Heterogeneous relationships can improve movement prediction.
- **Why it matters:** ETF relationships are also heterogeneous: sector, asset class, correlation, macro sensitivity.
- **Limitations:** Graph construction can leak if built with future information.
- **Applies to ETF weekly data?** Yes as a small graph prototype.
- **Needs PIT stock data?** For full stock version, yes.
- **Implementation idea:** ETF graph with asset-class edges and rolling correlation edges built only from past data.

#### Attention-Based Dynamic Graph Neural Network for Asset Pricing

- **Authors/year:** 2023 arXiv preprint.
- **Link:** [arXiv](https://arxiv.org/abs/2301.10727)
- **Method category:** Dynamic GNN asset pricing.
- **What it does:** Uses dynamic graph attention for asset pricing.
- **Data:** Stock return/characteristic panels.
- **Main finding:** Time-varying relationships can matter for asset pricing.
- **Why it matters:** Correlations and leadership rotate over time in ETFs.
- **Limitations:** More complex validation and graph updates.
- **Applies to ETF weekly data?** Yes for rolling correlation graph.
- **Needs PIT stock data?** Not for ETF prototype.
- **Implementation idea:** Graph attention over ETF nodes with rolling 52-week correlation edges.

#### HGAIT: Heterogeneous Graph Attention for Investor Asset Trends

- **Authors/year:** Dongwoo Lee, Seungeun Ock, Jae Wook Song, 2026 working paper.
- **Link:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5460481)
- **Method category:** Heterogeneous graph attention in finance.
- **What it does:** Uses graph attention to model asset trends.
- **Data:** Finance asset relationship data.
- **Main finding:** Relationship-aware learning may improve trend modeling.
- **Why it matters:** Good reading for graph construction ideas.
- **Limitations:** Working paper; not necessarily ETF-ready.
- **Applies to ETF weekly data?** Conceptually yes.
- **Needs PIT stock data?** Likely for best version.
- **Implementation idea:** Treat ETFs as nodes and economic categories as relation types.

### Portfolio RL / Transformer-RL

#### An Evaluation of Reinforcement Learning Based Portfolio Management Strategies

- **Authors/year:** Chung I Lu, 2023.
- **Link:** [arXiv](https://arxiv.org/abs/2306.14714)
- **Method category:** RL portfolio evaluation.
- **What it does:** Evaluates RL portfolio management strategies.
- **Data:** Portfolio-management benchmarks.
- **Main finding:** RL performance depends heavily on environment design and evaluation.
- **Why it matters:** Supports skepticism after MLX-8 PPO underperformed.
- **Limitations:** Benchmark-specific.
- **Applies to ETF weekly data?** Yes as evaluation guidance.
- **Needs PIT stock data?** No for ETF RL environment.
- **Implementation idea:** Improve MLX-8 environment before adding complexity.

#### FinRL

- **Authors/year:** AI4Finance Foundation, started 2020 and actively maintained.
- **Link:** [GitHub](https://github.com/AI4Finance-Foundation/FinRL)
- **Method category:** RL library for finance.
- **What it does:** Provides environments and agents for financial reinforcement learning.
- **Data:** Market data, trading environments.
- **Main finding:** Useful infrastructure, not proof that RL alpha is robust.
- **Why it matters:** Good learning reference.
- **Limitations:** Examples can be overfit if copied naively.
- **Applies to ETF weekly data?** Yes for environment patterns.
- **Needs PIT stock data?** No for ETF proof of concept.
- **Implementation idea:** Use ideas for environment diagnostics, not dependency yet.

### Meta-Labeling and Triple-Barrier Methods

#### Advances in Financial Machine Learning

- **Authors/year:** Marcos Lopez de Prado, 2018.
- **Link:** [Wiley](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)
- **Method category:** Meta-labeling, triple barrier, purged CV, financial ML validation.
- **What it does:** Introduces practical methods for financial ML labeling and validation.
- **Data:** Financial event labels and strategy signals.
- **Main finding:** Financial ML needs specialized labeling/validation.
- **Why it matters:** MLX-7 is directly inspired by meta-labeling.
- **Limitations:** Book predates recent deep learning wave, but validation concepts remain central.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No for ETF strategy filtering.
- **Implementation idea:** Triple-barrier labels for Phase 4B switch and ML sleeve risk.

#### Triple-Barrier Method Implementations

- **Authors/year:** Open-source documentation and libraries.
- **Links:** [mlfinpy labeling docs](https://mlfinpy.readthedocs.io/en/stable/Labelling.html), [mlfinlab overview](https://hudsonthames.org/mlfinlab/)
- **Method category:** Event labeling.
- **What it does:** Implements profit/stop/time-barrier labels.
- **Data:** Price paths and event start times.
- **Main finding:** Path-aware labels are more realistic than simple fixed-horizon labels.
- **Why it matters:** The project cares about drawdown and loss paths.
- **Limitations:** Barrier choices can be mined.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No for ETF-level prototype.
- **Implementation idea:** Replace simple 4-week meta-labels with triple-barrier outcomes.

### Learning-to-Rank for Asset Selection

#### LambdaRankIC: A Ranking Loss for Asset Returns

- **Authors/year:** Yan Lin and coauthors, 2025.
- **Link:** [arXiv](https://arxiv.org/abs/2506.20653)
- **Method category:** Learning-to-rank for finance.
- **What it does:** Proposes a ranking loss aimed at improving rank correlation for asset returns.
- **Data:** Cross-sectional asset return data.
- **Main finding:** Ranking-specific objectives can better align with asset selection.
- **Why it matters:** ETF selection is a ranking problem.
- **Limitations:** New preprint; implementation details need reading.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** Not for ETF prototype; useful for stock-scale version.
- **Implementation idea:** Compare rank correlation loss to binary top-quintile labels.

#### Learning-to-Rank with LightGBM/XGBoost

- **Authors/year:** Library methods, ongoing.
- **Links:** [LightGBM ranking](https://lightgbm.readthedocs.io/), [XGBoost ranking](https://xgboost.readthedocs.io/)
- **Method category:** LambdaMART / pairwise ranking.
- **What it does:** Trains rankers with grouped examples.
- **Data:** Date-grouped cross sections.
- **Main finding:** Mature, practical ranking baseline.
- **Why it matters:** Strong next step before exotic neural rankers.
- **Limitations:** Needs correct grouping by date.
- **Applies to ETF weekly data?** Yes.
- **Needs PIT stock data?** No initially.
- **Implementation idea:** Date-grouped ETF LambdaMART top-N selector.

### Deep Asset Pricing / Neural Asset Pricing

#### Empirical Asset Pricing via Machine Learning

- **Authors/year:** Shihao Gu, Bryan Kelly, Dacheng Xiu, 2020.
- **Link:** [Review of Financial Studies](https://academic.oup.com/rfs/article/33/5/2223/5758276)
- **Method category:** Broad ML asset pricing benchmark.
- **What it does:** Compares many ML methods for cross-sectional stock returns.
- **Data:** Large stock characteristic panel.
- **Main finding:** Nonlinear ML can improve cross-sectional return prediction, especially trees/neural networks.
- **Why it matters:** Foundational evidence that ML can help asset pricing with the right data scale.
- **Limitations:** Stock-level data, not weekly ETF-only data.
- **Applies to ETF weekly data?** Conceptually, but ETF sample is much smaller.
- **Needs PIT stock data?** Yes for a serious replication.
- **Implementation idea:** Stock-level WRDS cross-sectional ML after PIT data upgrade.

#### Deep Learning in Asset Pricing

- **Authors/year:** Luyang Chen, Markus Pelger, Jason Zhu, 2024 RFS.
- **Link:** [Review of Financial Studies](https://academic.oup.com/rfs/article/37/8/2545/7505230)
- **Method category:** Neural asset pricing.
- **What it does:** Uses deep learning for stochastic discount factor and asset pricing.
- **Data:** Cross-sectional stock returns and characteristics.
- **Main finding:** Deep learning can capture nonlinear asset pricing structure.
- **Why it matters:** Good advanced reading for factor discovery and representation learning.
- **Limitations:** Academically complex; not a direct ETF backtest recipe.
- **Applies to ETF weekly data?** Mostly as conceptual inspiration.
- **Needs PIT stock data?** Yes for serious replication.
- **Implementation idea:** Use neural factor diagnostics to audit MLX exposures.

#### Autoencoder Asset Pricing Models

- **Authors/year:** Shihao Gu, Bryan Kelly, Dacheng Xiu, working paper.
- **Link:** [AQR working paper page](https://www.aqr.com/Insights/Research/Working-Paper/Autoencoder-Asset-Pricing-Models)
- **Method category:** Autoencoder asset pricing.
- **What it does:** Learns latent factors and loadings with autoencoder structure.
- **Data:** Stock characteristics and returns.
- **Main finding:** Autoencoders can learn nonlinear latent asset-pricing factors.
- **Why it matters:** Useful for factor discovery and exposure auditing.
- **Limitations:** Needs broad stock data.
- **Applies to ETF weekly data?** Limited, but useful as latent factor inspiration.
- **Needs PIT stock data?** Yes.
- **Implementation idea:** Later-stage stock-level latent factor model.

### Financial Text / Sentiment / LLMs

#### FinGPT

- **Authors/year:** AI4Finance Foundation, 2023.
- **Link:** [GitHub](https://github.com/AI4Finance-Foundation/FinGPT), [paper](https://arxiv.org/abs/2306.06031)
- **Method category:** Financial LLM/open-source framework.
- **What it does:** Provides LLM tooling and datasets for financial NLP.
- **Data:** Financial text, news, filings, sentiment datasets.
- **Main finding:** Open-source financial LLM workflows are feasible.
- **Why it matters:** Useful later for macro/news sentiment overlays.
- **Limitations:** Text timestamps and licensing are hard.
- **Applies to ETF weekly data?** Only as an overlay.
- **Needs PIT stock data?** Not exactly, but needs point-in-time text.
- **Implementation idea:** Macro sentiment regime feature, not direct ETF ranker.

#### BloombergGPT

- **Authors/year:** Wu et al., 2023.
- **Link:** [arXiv](https://arxiv.org/abs/2303.17564)
- **Method category:** Domain-specific financial LLM.
- **What it does:** Trains a large language model on finance-heavy corpora.
- **Data:** Financial and general text.
- **Main finding:** Finance-specific pretraining improves financial NLP tasks.
- **Why it matters:** Supports domain-specific pretraining rather than generic models.
- **Limitations:** Proprietary-scale data and compute.
- **Applies to ETF weekly data?** Indirectly.
- **Needs PIT stock data?** Needs point-in-time text, not necessarily stock returns.
- **Implementation idea:** Read for domain adaptation concepts; do not try to replicate.

#### FinBERT

- **Authors/year:** Araci, 2019; still relevant.
- **Link:** [arXiv](https://arxiv.org/abs/1908.10063)
- **Method category:** Financial sentiment model.
- **What it does:** Fine-tunes BERT for financial sentiment.
- **Data:** Financial text.
- **Main finding:** Domain adaptation helps financial sentiment.
- **Why it matters:** Practical sentiment baseline.
- **Limitations:** Sentiment alone is not a portfolio strategy.
- **Applies to ETF weekly data?** As later overlay.
- **Needs PIT stock data?** Needs point-in-time text.
- **Implementation idea:** News sentiment as a regime feature.

## 5. Useful GitHub Repositories and Libraries

| Name | Link | License if obvious | What it does | Maintenance signal | Fit for project | Use/copy/inspiration | Risks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qlib | [GitHub](https://github.com/microsoft/qlib) | Check repo | AI-oriented quantitative investment platform | Microsoft-backed, active | Strong reference for ML research pipelines | Inspiration first | Heavy framework, may be overkill |
| FinRL | [GitHub](https://github.com/AI4Finance-Foundation/FinRL) | Check repo | Financial RL environments and agents | Active AI4Finance ecosystem | RL learning reference | Inspiration only for now | Easy to overfit examples |
| FinGPT | [GitHub](https://github.com/AI4Finance-Foundation/FinGPT) | MIT noted in search result | Financial LLM framework | Active | Later text/sentiment overlay | Inspiration | Requires text data and infrastructure |
| skfolio | [Docs](https://skfolio.org/), [GitHub](https://github.com/skfolio/skfolio) | BSD-3 noted in search result | Portfolio optimization, cross-validation, clustering, uncertainty sets | Active | Very relevant | Consider dependency later | API learning curve |
| Riskfolio-Lib | [GitHub](https://github.com/dcajasn/Riskfolio-Lib), [Docs](https://riskfolio-lib.readthedocs.io/) | Check repo | Portfolio optimization and risk measures | Active | Useful for CVaR/risk parity experiments | Consider dependency later | Adds dependency surface |
| PyPortfolioOpt | [GitHub](https://github.com/robertmartin8/PyPortfolioOpt) | MIT likely, verify | Mean-variance, HRP, Black-Litterman | Mature | Good educational baseline | Use as inspiration or dependency | Simpler than decision-focused learning |
| cvxportfolio | [GitHub](https://github.com/cvxgrp/cvxportfolio) | Check repo | Convex portfolio optimization/backtesting | Active cvxgrp | Strong for realistic allocation | Inspiration/dependency | Requires convex modeling discipline |
| cvxpylayers | [GitHub](https://github.com/cvxgrp/cvxpylayers) | Check repo | Differentiable convex optimization layers | Active academic library | Key for decision-focused sprint | Dependency if needed | Numerical complexity |
| DeepDow | [GitHub](https://github.com/jankrepl/deepdow) | Check repo | End-to-end portfolio optimization with deep learning | Older but educational | Excellent learning reference | Inspiration | May be less maintained |
| vectorbt | [GitHub](https://github.com/polakowo/vectorbt) | Check repo | Vectorized backtesting | Mature | Useful reference, but project already has backtests | Inspiration | Different assumptions |
| Chronos | [GitHub](https://github.com/amazon-science/chronos-forecasting) | Apache-2.0 likely, verify | Time-series foundation forecasting | Active research repo | Foundation model sprint | Dependency/inspiration | General TS, not finance-specific |
| TimesFM | [GitHub](https://github.com/google-research/timesfm) | Apache-style Google repo, verify | Time-series foundation model | Active | Foundation model sprint | Dependency/inspiration | General TS transfer risk |
| MOMENT | [GitHub](https://github.com/moment-timeseries-foundation-model/moment) | Check repo | Open time-series foundation models | Active | Embedding experiment | Dependency/inspiration | Setup and GPU/runtime |
| GluonTS | [GitHub](https://github.com/awslabs/gluonts) | Apache-2.0 likely, verify | Probabilistic time-series modeling | Mature | Risk/forecasting baseline | Inspiration/dependency | Forecasting focus |
| PyEPO | [Docs](https://khalil-research.github.io/PyEPO/) | Check repo | Predict-and-optimize learning | Active academic tool | Decision-focused learning sprint | Inspiration/dependency | General optimization, not finance-specific |
| LightGBM | [Docs](https://lightgbm.readthedocs.io/) | Microsoft repo | Gradient boosting and ranking | Active | Learning-to-rank ETF selector | Already likely available | Ranking groups must be correct |
| XGBoost | [Docs](https://xgboost.readthedocs.io/) | Apache-2.0 | Boosting and ranking | Active | Ranking baseline | Already used | Easy to overfit |
| PyG | [PyTorch Geometric](https://github.com/pyg-team/pytorch_geometric) | MIT likely, verify | Graph neural networks | Active | Graph asset model | Dependency later | New graph stack |
| DGL | [GitHub](https://github.com/dmlc/dgl) | Apache-2.0 likely, verify | Graph neural networks | Active | Alternative GNN stack | Inspiration | Install/setup risk |

Dependency rule for this project: do not add dependencies automatically. Use these repos for study first. Promote a dependency only when a specific sprint needs it and after checking license, maintenance, install friction, and whether the existing codebase really benefits.

## 6. What We Already Tried in Phase MLX

### MLX-3 Tabular ML

- **What we tried:** Ridge, ElasticNet, Logistic Regression, Random Forest, Gradient Boosting, XGBoost, LightGBM.
- **What worked:** Infrastructure, feature panel, model output format, feature importance, baselines.
- **What failed:** Best holdout Sharpe around 0.811 did not beat simple momentum, production, or official shadow.
- **What you learned:** Strong tabular models are not automatically strong portfolio strategies.
- **Related method family:** Linear models, tree models, boosting.
- **Better version:** Date-grouped learning-to-rank and decision-aware objective instead of ordinary forward-return/classification losses.

### MLX-4 MLP Neural Networks

- **What we tried:** MLP classifiers/regressor with dropout and early stopping.
- **What worked:** Improved over tabular ML and simple momentum in some comparisons.
- **What failed:** Still did not beat production or official shadow; drawdown remained high.
- **What you learned:** Nonlinear features helped, but raw ML risk was too high.
- **Related method family:** MLPs and neural nonlinear tabular modeling.
- **Better version:** Calibrated uncertainty, ranking loss, and defensive wrappers.

### MLX-5 / MLX-5B / MLX-5C Sequence Models

- **What we tried:** LSTM, GRU, Temporal CNN, BIL fallback, regime overlays, robustness checks, multi-seed walk-forward.
- **What worked:** MLX-5C was the strongest ML component: positive Sharpe across tested BIL fallback runs, mean Sharpe about 1.276, and better risk profile than raw ML.
- **What failed:** Earlier folds were weaker; performance was boosted by 2023-2026; COVID/rebound sensitivity appeared in MLX-5B.
- **What you learned:** Sequence ML is promising as an offensive sleeve, not a standalone portfolio.
- **Related method family:** RNNs, TCNs, sequence classification, defensive overlays.
- **Better version:** Cross-asset attention ranker and self-supervised regime embeddings.

### MLX-6 Transformer

- **What we tried:** Small Transformer encoder with defensive overlays.
- **What worked:** Competitive holdout Sharpe around 0.987 and better than production/shadow in 2020+ Sharpe.
- **What failed:** Did not beat MLX-5C mean Sharpe or Phase 4B; needs multi-seed/walk-forward.
- **What you learned:** Transformers are interesting but not clearly superior to simpler sequence models on this sample.
- **Related method family:** Attention, Transformer sequence models.
- **Better version:** Cross-sectional attention over all ETFs at a date.

### MLX-7 Meta-Labeling

- **What we tried:** Production risk filter, production beats BIL, Phase 4B beats production, ML sleeve activation, bad-week avoidance.
- **What worked:** Phase 4B switch/filter was modestly useful; best strategy Sharpe around 0.966.
- **What failed:** Production+BIL filter did not help; MLX-5 sleeve activation did not improve production.
- **What you learned:** Meta-labeling is most useful as a small switch/filter around already-strong strategies.
- **Related method family:** Meta-labeling, second-stage classification, triple-barrier inspiration.
- **Better version:** Triple-barrier labels and walk-forward threshold selection.

### MLX-8 Deep RL

- **What we tried:** PPO allocator with return-only, turnover-penalized, risk-aware, and defensive-regime-aware rewards.
- **What worked:** Built a research RL environment and diagnostics.
- **What failed:** Best RL holdout Sharpe about 0.703, high drawdown, weaker than production/Phase 4B/MLX-5C.
- **What you learned:** RL is educational and resume-worthy but not a main component yet.
- **Related method family:** Reinforcement learning, policy optimization.
- **Better version:** Better environment, action constraints, risk-aware state, and maybe RL for sizing rather than allocation.

### MLX-9 Model Ensemble

- **What we tried:** Rank-average, sequence-dominant, agreement filter, defensive-first, core plus ML sleeve, meta-label-gated core/sleeve, RL diagnostic blend.
- **What worked:** Validation-selected ensemble was a small meta-gated ML sleeve around core logic with holdout Sharpe about 1.005, beating production/shadow and MLX-6/7/8 but not Phase 4B or MLX-5C mean.
- **What failed:** Best holdout-only result was diagnostic/hindsight; validation selection still needs walk-forward.
- **What you learned:** The cleanest production-adjacent use is small ML sleeve/filter around the core.
- **Related method family:** Ensemble learning, stacking/rank averaging, meta-labeling.
- **Better version:** Walk-forward ensemble calibration and uncertainty-aware sleeve sizing.

## 7. Gaps Between My Project and Real Quant Firms

This section is meant to be educational, not discouraging. A student project can imitate the discipline of professional quant research even without institutional data and execution infrastructure.

### Data Scale

Professional firms often use thousands of stocks, many asset classes, intraday data, option surfaces, order books, fundamentals, estimates, corporate events, and alternative data. Phase MLX mostly uses weekly ETF data and some prototype breadth features. That is enough for learning but small for high-capacity ML.

**What to imitate:** Build clean panels, data dictionaries, versioned artifacts, and strict train/validation/holdout splits.

### Point-in-Time Data

Real firms care deeply about whether data was known at the decision date. PIT data includes historical index membership, restated fundamentals, delistings, earnings release timestamps, corporate actions, and vendor correction history.

**What to imitate:** Treat all non-PIT features as research-only, document survivorship risk, and prioritize WRDS/PIT stock breadth as the next real data upgrade.

### Stock Cross-Sections

Many academic ML asset-pricing results rely on thousands of stocks and hundreds of characteristics. ETF data has cleaner tradability but far fewer observations. Deep learning usually benefits from large cross-sections.

**What to imitate:** Prototype on ETFs, then rerun on PIT stock data when available.

### Transaction Costs and Execution

Real strategies must survive spreads, market impact, borrow constraints, rebalance delay, capacity, and tax/friction considerations. A 10 bps turnover assumption is a good conservative placeholder but not a real execution model.

**What to imitate:** Keep cost sensitivity tables, turnover diagnostics, and delayed-rebalance checks in every ML report.

### Alternative Data

Funds may use news, credit-card data, web traffic, satellite images, supply chains, analyst revisions, and proprietary feeds. These are expensive and easy to misuse.

**What to imitate:** Use public macro/news only after building timestamp discipline.

### Research Infrastructure

Professional research has data lineage, experiment tracking, parameter registries, model monitoring, approvals, and reproducibility.

**What to imitate:** Keep every MLX phase separate, save metadata JSON, record skipped models, and never promote automatically.

### Validation Discipline

Real quant validation includes walk-forward splits, purged/embargoed CV, cost and delay sensitivity, seed robustness, capacity checks, stress windows, and live shadow periods.

**What to imitate:** Make "validation-selected vs holdout-diagnostic" a permanent distinction.

### Model Risk Management

Models can fail silently. Firms monitor drift, feature distributions, turnover, drawdown, realized vs expected risk, and performance attribution.

**What to imitate:** Build ML shadow dashboards only after research; include drift detection before any production consideration.

## 8. Most Promising Future ML Experiments for My Project

Ranked by a blend of learning value, realistic portfolio relevance, and fit with existing MLX results.

| Rank | Experiment | Method family | What it tests | Why it might help | Data needed | Difficulty | Overfitting risk | Resume value | Expected portfolio value | Timing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Cross-Asset Attention Ranker | Cross-sectional Transformer | Date-wise attention over ETFs | Models interactions among SPY, sectors, bonds, commodities, BIL | Existing ETF feature panel | High | High | Very high | High | Now |
| 2 | Decision-Focused Portfolio Learning | Decision-focused / differentiable optimization | Train signals through allocation loss | Aligns training with Sharpe/CVaR/turnover | ETF panel and optimizer | High | High | Very high | High | Now |
| 3 | Learning-to-Rank ETF Selector | LambdaMART/listwise ranking | Date-grouped ranking objective | Better matches top-N ETF selection | ETF panel | Medium | Medium-high | High | Medium-high | Now |
| 4 | Triple-Barrier Meta-Labeling | Meta-labeling | Path-aware labels for Phase 4B/ML sleeve | Connects labels to drawdown/stop risk | ETF paths/core returns | Medium | Medium | High | Medium-high | Now |
| 5 | Self-Supervised Regime Embeddings | Contrastive/autoencoder | Learn regime/state vectors without noisy labels | Could improve calm/stress state detection | ETF panel, breadth | High | Medium-high | Very high | Medium | Now |
| 6 | PIT Stock Breadth + ML Filter | Tree/linear/meta-label | Better breadth features into filters | Likely best data upgrade | WRDS/PIT stock data | Medium | Medium | High | High | After WRDS |
| 7 | Stock-Level Cross-Sectional ML after WRDS | Boosting/deep asset pricing | Replicate Gu-Kelly-Xiu style stock ranker | Much larger cross-section | CRSP/Compustat/PIT data | High | High | Very high | High | After WRDS |
| 8 | Time-Series Foundation Model Embeddings | Foundation models | Use Chronos/MOMENT/TimesFM embeddings | Tests frontier TS transfer | ETF panel | Medium-high | High | High | Uncertain | Now, learning-first |
| 9 | Graph Asset Relationship Model | GNN | ETF graph from sector/correlation/asset class | Models asset relationships | ETF panel, graph edges | High | High | Very high | Medium | Later |
| 10 | Ensemble Calibration / Stacking | Ensemble learning | Validation-only weights for ML sleeves | Improves MLX-9 discipline | Existing outputs | Medium | Medium-high | High | Medium | Now |
| 11 | Uncertainty Estimation | Bayesian/dropout/ensembles | Penalize uncertain ML scores | Could prevent overconfident ML sleeves | Existing model outputs | Medium | Medium | High | Medium | Now |
| 12 | Conformal Prediction / Prediction Intervals | Distribution-free uncertainty | Add prediction sets/intervals | Improves risk communication | Validation residuals | Medium | Medium | High | Medium | Now |
| 13 | Model Drift Detection | Monitoring/anomaly detection | Detect score/exposure drift | Needed before shadow use | Saved predictions/weights | Low-medium | Low | High | Medium | Now |
| 14 | Text/News Sentiment Overlay | NLP/LLM | Macro or ETF-relevant sentiment feature | Adds non-price signal | Timestamped text | High | High | Very high | Uncertain | Much later |
| 15 | Better RL Environment / Transformer-RL | RL | More realistic RL with constraints/sizing | Tests whether RL can be useful as overlay | ETF panel, costs | Very high | Very high | Very high | Low-medium | Much later |
| 16 | Calm-Trend Specialist Model | Regime-specific ML | Improve calm_trend bottleneck | Directly targets known weakness | Regime labels, ETF panel | Medium | Medium-high | Medium | Medium | Now |
| 17 | Cross-Validated Core Switch | Meta-labeling | Walk-forward Phase 4B vs production switch | Extends MLX-7/9 | Project returns, regime features | Medium | Medium | High | Medium | Now |
| 18 | Risk-Aware Rank Loss | Custom neural loss | Rank assets while penalizing downside | Better aligns with CVaR/drawdown | ETF panel | High | High | High | Medium | Later |

Short interpretation:

- **Do now:** cross-asset attention, decision-focused learning, learning-to-rank, triple-barrier meta-labeling, drift/uncertainty.
- **Do after WRDS/PIT:** stock-level ML, true breadth filters, deep asset pricing replication.
- **Do much later:** text/LLM overlays and improved RL.

## 9. Recommended Next 3 Sprints

### Sprint 1: Cross-Asset Attention Ranker

**Purpose:** Build a date-wise Transformer/attention model that ranks ETFs jointly instead of predicting each ETF independently.

**Why worth learning:** This directly addresses the biggest modeling gap after MLX-5/6: relationships among assets.

**Files/scripts to create:**

- `scripts/ml_lab/09_run_cross_asset_attention_ranker.py`
- `data/research/ml_lab/cross_asset_attention/`
- `docs/research/ml_lab/phase_mlx_cross_asset_attention_notes.md`

**Outputs/reports:**

- ETF score panel
- attention diagnostics
- ranker backtests
- state-by-state performance
- comparison to MLX-5C/MLX-9

**Success criteria:**

- Validation-selected model beats simple momentum and is competitive with MLX-9.
- Attention diagnostics are interpretable enough to audit.

**Likely failure mode:** Small ETF cross-section and short weekly history lead to unstable attention weights.

**Resume line:** "Built cross-asset Transformer ranker for ETF allocation with walk-forward validation and defensive overlays."

### Sprint 2: Decision-Focused Portfolio Learning

**Purpose:** Train a model through a differentiable allocation objective instead of standard prediction loss.

**Why worth learning:** It teaches the key frontier idea that the decision objective matters more than prediction accuracy.

**Files/scripts to create:**

- `scripts/ml_lab/10_run_decision_focused_portfolio_learning.py`
- `data/research/ml_lab/decision_focused/`
- `docs/research/ml_lab/phase_mlx_decision_focused_learning_notes.md`

**Outputs/reports:**

- decision-loss training curves
- portfolio returns
- comparison to MSE/classification baselines
- turnover and CVaR diagnostics

**Success criteria:**

- Clear educational comparison: prediction-loss model vs decision-loss model.
- No leakage and train-only preprocessing.

**Likely failure mode:** Optimizer instability or overfitting to the validation objective.

**Resume line:** "Implemented decision-focused learning with differentiable portfolio optimization for long-only ETF allocation."

### Sprint 3: Triple-Barrier Meta-Labeling and Drift Monitoring

**Purpose:** Replace simple 4-week labels with triple-barrier labels and build a monitoring report for ML shadow candidates.

**Why worth learning:** This is both practical and production-adjacent without promoting anything.

**Files/scripts to create:**

- `scripts/ml_lab/11_run_triple_barrier_meta_labeling.py`
- `scripts/ml_lab/12_run_ml_shadow_drift_monitor.py`
- `data/research/ml_lab/triple_barrier_meta/`
- `data/research/ml_lab/shadow_monitoring/`
- `docs/research/ml_lab/phase_mlx_triple_barrier_and_drift_notes.md`

**Outputs/reports:**

- triple-barrier labels
- meta-label strategy summaries
- drift charts/tables
- score distribution changes
- exposure drift

**Success criteria:**

- Meta-labeling improves interpretability and downside-risk filtering.
- Drift report clearly flags when ML behavior changes across regimes.

**Likely failure mode:** Barrier choices become another hyperparameter-mining surface.

**Resume line:** "Designed triple-barrier meta-labeling and model-drift monitoring for a research ETF ML shadow strategy."

## 10. Glossary

**Point-in-time data:** Data stored as it was known on a historical date, without future revisions or later membership changes.

**Survivorship bias:** Bias from only including assets that survived to today, excluding dead/delisted assets.

**Lookahead bias:** Using information that would not have been known at the decision date.

**Cross-sectional prediction:** Predicting or ranking assets relative to one another at the same date.

**Time-series prediction:** Predicting the future of one series using its own history and context.

**Meta-labeling:** A second-stage model that learns when to trust a base signal or strategy.

**Triple barrier:** Labeling method using profit target, stop loss, and time limit barriers.

**Decision-focused learning:** Training a model based on downstream decision quality rather than prediction error.

**Differentiable optimization:** Optimization layer through which gradients can flow during neural network training.

**Self-supervised learning:** Learning representations from data-created tasks rather than manual labels.

**Contrastive learning:** Self-supervised method that pulls related examples together and pushes unrelated examples apart.

**Foundation model:** A large pretrained model adapted to many downstream tasks.

**Attention:** Mechanism that lets a model weight different inputs by relevance.

**Transformer:** Neural architecture built around attention layers.

**Graph neural network:** Model that learns from nodes and edges, such as assets and their relationships.

**Reinforcement learning:** Learning actions from rewards through interaction with an environment.

**Policy:** In RL, the rule/model mapping observations to actions.

**Reward:** In RL, the score the agent tries to maximize.

**Action space:** Set of actions an RL agent can take, such as portfolio weights.

**Regime:** A market state with distinct behavior, such as calm trend or stressed panic.

**Alpha:** Expected return unexplained by standard risk exposure.

**Beta:** Exposure to a broad market or risk factor.

**Turnover:** Amount of portfolio weight traded during rebalancing.

**Slippage:** Difference between expected and realized execution price.

**CVaR:** Conditional value at risk; average loss in the tail beyond a chosen quantile.

**Drawdown:** Decline from a prior equity high.

**Sharpe:** Annualized return divided by annualized volatility.

**Calmar:** Annual return divided by absolute max drawdown.

**Walk-forward validation:** Chronological evaluation where models are trained on the past and tested on future windows.

**Seed robustness:** Testing whether neural results persist across random initializations.

**Model drift:** Change in feature distributions, predictions, or performance over time.

**Data mining:** Repeatedly searching until a pattern appears, increasing the chance of false discovery.

## 11. Final Learning Roadmap

Study first:

1. Gu, Kelly, Xiu: [Empirical Asset Pricing via Machine Learning](https://academic.oup.com/rfs/article/33/5/2223/5758276).
2. Lopez de Prado: meta-labeling, triple barrier, purged validation.
3. Decision-focused learning survey: [arXiv 2307.13565](https://arxiv.org/abs/2307.13565).
4. Cross-sectional attention papers: [MASTER](https://arxiv.org/abs/2312.15235), [Cross-Sectional Self-Attention](https://arxiv.org/abs/2407.18901).
5. Time-series foundation caution paper: [Re(Visiting) Time Series Foundation Models in Finance](https://arxiv.org/abs/2509.08870).

Papers to read after that:

- [Deep Learning in Asset Pricing](https://academic.oup.com/rfs/article/37/8/2545/7505230)
- [Autoencoder Asset Pricing Models](https://www.aqr.com/Insights/Research/Working-Paper/Autoencoder-Asset-Pricing-Models)
- [Contrastive Learning of Asset Embeddings](https://arxiv.org/abs/2409.15727)
- [Heterogeneous Graph Attention Networks for Stock Movement Prediction](https://arxiv.org/abs/2402.06680)
- [LambdaRankIC](https://arxiv.org/abs/2506.20653)

Code experiments to run next:

1. Cross-Asset Attention Ranker.
2. Date-grouped LambdaMART ETF ranker.
3. Decision-focused ETF optimizer.
4. Triple-barrier meta-labeling.
5. ML shadow drift and uncertainty monitor.

Postpone until WRDS/PIT stock data:

- Stock-level cross-sectional ML.
- Deep asset-pricing replication.
- PIT stock breadth ML filters.
- Stock graph models with sector/industry/supply-chain edges.
- Fundamentals-based models.

Postpone until much later:

- LLM/news sentiment overlays.
- Transformer-RL hybrids.
- Large foundation-model fine-tuning.
- Intraday execution modeling.

Most resume-worthy:

- Cross-asset Transformer ranker with walk-forward validation.
- Decision-focused portfolio learning with differentiable optimizer.
- Triple-barrier meta-labeling and ML shadow monitoring.
- PIT stock breadth + ML filter after WRDS.
- Self-supervised regime embeddings.

Most likely to actually help the portfolio:

- PIT stock breadth and better regime filters.
- Small ML sleeves around production/Phase 4B.
- Cross-sectional rankers that improve ETF selection without increasing drawdown.
- Meta-labeling filters that reduce bad regimes without suppressing recoveries.
- Drift monitoring before any shadow candidate is trusted.

Final takeaway: Phase MLX should remain a learning-first research lab. The best current evidence says ML is useful as a small offensive sleeve, filter, diagnostic, or representation engine around the existing ETF core. The next serious leap is not a bigger model; it is better data, better ranking objectives, decision-aware training, and stricter validation.
