# Covariance-Aware Portfolios — Batch 06

Frozen trend v4 and the Batch 05 robust defensive sleeve were combined using only covariance observations available by each monthly decision date. All combined target weights were accounted together so overlapping trades were netted before costs. Each sleeve was capped at 80%, each underlying non-cash asset at 35%, and cap excess was held in explicit cash.

## Primary 104-week, 25% diagonal-shrinkage comparison

- **equal_weight**: annual return **8.62%**, Sharpe **0.859**, drawdown **-24.29%**, turnover **2.45**.
- **inverse_volatility**: annual return **8.27%**, Sharpe **0.888**, drawdown **-23.82%**, turnover **2.65**.
- **minimum_variance**: annual return **7.83%**, Sharpe **0.901**, drawdown **-23.39%**, turnover **2.90**.
- **maximum_diversification**: annual return **8.27%**, Sharpe **0.888**, drawdown **-23.82%**, turnover **2.65**.
- **hrp_two_sleeve**: annual return **8.06%**, Sharpe **0.903**, drawdown **-23.43%**, turnover **2.81**.
- **equal_weight_vol_target_10**: annual return **7.91%**, Sharpe **0.821**, drawdown **-24.29%**, turnover **2.39**.

## Decision

The method selected using only the 2006–2015 development score was **minimum_variance**. Its later-period results remain retrospective out-of-sample diagnostics, because Batch 06 itself was designed after the complete history was available.

With two sleeves, maximum diversification is mathematically equivalent to inverse-volatility weighting, while two-sleeve HRP has no meaningful hierarchy to discover. Duplicate return histories are explicitly reported rather than counted as independent methods.

No portfolio in this batch is final or approved for live trading. The free ETF universe remains survivorship-prone and the 52-week untouched forward clock is incomplete.
