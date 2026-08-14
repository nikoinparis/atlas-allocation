# Ensemble and Dependence Batch 03

The ten provisional candidates represent approximately **1.15** independent return streams by the correlation participation ratio.

## Dependence

- Pairwise full-history return correlations range from **0.838** to **0.981**; median **0.931**.
- Average historical holdings overlap is **69.1%**.
- At correlation ≥ 0.90, the candidates form **1** connected clusters.

## Netted portfolio ensembles

- **frozen_v4**: annual return 9.91%, Sharpe 0.754, drawdown -26.25%, annual turnover 1.93.
- **equal_all_candidates**: annual return 9.42%, Sharpe 0.830, drawdown -22.74%, annual turnover 2.02.
- **correlation_cluster_balanced**: annual return 9.42%, Sharpe 0.830, drawdown -22.74%, annual turnover 2.02.
- **greedy_four_from_v4**: annual return 9.24%, Sharpe 0.816, drawdown -23.28%, annual turnover 2.19.

## Multiple-testing correction

The original search contained **288** strategies. Under independent zero-alpha Gaussian trials, the expected best Sharpe is approximately **0.620**. Serial-dependence-aware 13-week block-bootstrap p-values were Bonferroni-adjusted across all 288 trials.

Candidates passing the declared multiple-testing gate: **10 of 10**.

## Interpretation

The ensemble comparison uses netted target weights and therefore does not double-charge turnover shared across sleeves. However, every ensemble was designed after observing this history. It is evidence about redundancy and portfolio mechanics, not an untouched performance claim.
