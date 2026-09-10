# Statistical Validation Layer

Research-only utilities inspired by Fama/EMH discipline and Lopez de Prado-style leakage and overfitting controls.

## What This Layer Adds

- Probabilistic Sharpe Ratio using skew/kurtosis-adjusted Sharpe uncertainty.
- Deflated Sharpe Ratio proxy that raises the hurdle as the number of tested variants grows.
- Bonferroni-style multiple-testing support adjustment.
- Lightweight PBO proxy: top in-sample candidate is checked against median out-of-sample performance across purged subperiod splits.
- Purged and embargoed CV split utilities for overlapping forward-label research.
- Rolling-origin split utilities for causal validation.
- Standard strategy summary: annual return, vol, Sharpe, max drawdown, Calmar, CVaR, skew, kurtosis, PSR, DSR proxy, drawdown pain, and turnover warning.

## Honest Limitations

- DSR is approximate because the true dependence structure across all tried variants is not fully known.
- PBO is a proxy, not full CPCV, unless a future sprint supplies explicit combinatorial splits and a complete trial log.
- Metrics from saved return files cannot prove absence of research selection bias; they only make the risk visible.
- Statistical support is necessary but not sufficient: state behavior, turnover, hidden beta, cash exposure, and implementation simplicity still matter.

## How Frontier Sprints Should Use It

1. Use exact stabilized GGG wrapper output as benchmark.
2. Count every tried variant as a trial, including rejected variants.
3. Use purging/embargo whenever labels overlap future periods.
4. Report PSR, DSR proxy, PBO proxy, and limitations in sprint summaries.
5. Reject or downgrade ideas whose support disappears after multiple-testing adjustment.
