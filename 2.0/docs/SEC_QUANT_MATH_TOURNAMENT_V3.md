# SEC quant mathematics tournament v3

## Objective

This one-shot tournament asked whether a substantially more mathematical broad-
universe engine could create independent recent-return alpha. It expanded the
14 quarterly observations in the earlier tournament into causal four-week
decisions while forward-filling only information already available from the
latest point-in-time SEC snapshot.

The frozen design counted 96 candidates: six signal families, two breadths,
two portfolio constructions, and four exposure rules. It included robust
median/MAD scaling, sector and market residualization, nonlinear interaction
features, purged expanding-window ridge, inverse-volatility sizing, diagonal
covariance shrinkage, volatility targeting, 200-bps costs, delayed execution,
issuer and sector removal, block bootstrap, deflated Sharpe, and CSCV probability
of backtest overfitting.

The mathematical design drew on:

- [Residual Momentum](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2319861)
- [Ledoit-Wolf covariance shrinkage](https://www.ledoit.net/honey_abstract.htm)
- [Quality Minus Junk](https://www.aqr.com/Insights/Research/Working-paper/Quality-minus-Junk)
- [Multiple-testing hurdles for new factors](https://academic.oup.com/rfs/article-abstract/29/1/5/1843824)
- [Backtest-overfitting discipline](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)

## Result

The best broad candidate was
`quality_momentum_interaction__n5__rank_inverse_volatility__fixed_1.50x`.

| Metric | Result |
| --- | ---: |
| Recent CAGR | 123.33% |
| Recent Sharpe | 1.590 |
| Recent maximum drawdown | -43.66% |
| Two-year CAGR | 95.10% |
| CAGR at 200-bps costs | 68.77% |
| Worst delayed-execution CAGR | 23.99% |
| Worst five-issuer-removal CAGR | -10.31% |
| Rolling 26-week outperformance share | 47.06% |
| Deflated-Sharpe probability | 24.44% |
| Probability of backtest overfitting | 35.71% |

No candidate passed the frozen historical gates. The broad engine therefore did
not beat the concentrated 150.86%, 174.97%, or 186.90% references. The most
important falsifier was not the headline return gap; it was the collapse under
delayed execution and top-five issuer removal.

## Decision

Reject the broad v3 candidates as replacements. Preserve the monthly causal
panel and engine as reusable research infrastructure, but do not add its winner
to the dashboard or forward protocol. Live trading remains disabled.

