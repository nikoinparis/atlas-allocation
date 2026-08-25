# Fragility exposure control v1

## Objective

After the independent broad-universe tournament failed, this sealed 22-rule
study asked a narrower question: can mathematical exposure control push the
existing 186.90% fragility-aware alpha path above 200% or 300%, and what evidence
is sacrificed when it does?

The study tested fixed exposure from 1.35x to 2.00x under 8% and 12% financing,
lagged volatility targets, fractional Kelly rules, and fragility-tier rules. All
dynamic decisions used lagged information, and the source alpha, costs, delays,
and issuer stresses were unchanged.

## Main results

| Candidate | Recent CAGR | Sharpe | Recent drawdown | Two-year CAGR | Full drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed 1.50x, 8% financing | 217.11% | 3.183 | -16.70% | 101.74% | -27.75% |
| Fixed 1.65x, 8% financing | 249.96% | 3.164 | -18.33% | 113.18% | -30.45% |
| Volatility 35%, cap 1.75x | 220.60% | 3.213 | -15.45% | 96.97% | -32.26% |
| Fixed 2.00x, 8% financing | 337.83% | 3.132 | -22.02% | 141.27% | -37.16% |

The 2.00x return ceiling retained 242.39% recent CAGR at 200-bps costs,
279.16% under the worst delayed-execution proxy, and 284.83% under the
conservative five-issuer proxy. Its raw block-bootstrap probability was 99.24%.

## Why 337.83% is not a validated replacement

No rule passed all frozen gates. For the 2.00x return ceiling:

- familywise-adjusted bootstrap probability was 83.28%, below 95%;
- deflated-Sharpe probability was 85.90%, below 95%;
- CSCV probability of backtest overfitting was 37.14%, above 20%;
- full-history drawdown expanded to -37.16%;
- the source strategy and this exposure study were both selected after observing
  the same historical sample;
- untouched forward evidence is still zero weeks for this new exposure rule.

The result proves that the historical path can mechanically exceed 300% using
2.00x exposure. It does not prove that a future investor should expect 300%.
Leverage increased both compounded upside and loss severity; it did not create
new information about which securities will outperform.

## Decision

Save three research diagnostics:

1. `fixed_1.50x_8pct` as the simplest above-200% historical path;
2. `vol35_cap1.75_8pct` as the best recent return/drawdown balance;
3. `fixed_2.00x_8pct` as the above-300% fragile return ceiling.

Do not replace the incumbent, update the live/default dashboard strategy, or
enable execution. A new forward protocol must freeze any exposure rule before
its first eligible realization.

