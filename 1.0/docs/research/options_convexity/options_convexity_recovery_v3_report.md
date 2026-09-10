# Recovery Options Overlay v3 Report

> Standalone research extension. Not production. v1, v2, and prior recovery outputs are preserved.

**Final verdict: `REJECT`**

> PROXY RESULTS - APPROXIMATE, NOT PRODUCTION-GRADE.
> Real historical option-chain data is required before trusting any result.

## 1. Main Result

- Main variant: `v3|dte=60-90|mny=atm_5otm|profit=partial_runner`.
- Trades: 12; add-on success: 58.33%; partial-profit trigger rate: 0.00%.
- Late-entry block rate across diagnostics: 89.79%.

| Metric | ETF Baseline | Prior Recovery Main | v3 Options | v3 Tactical Tilt | v3 Vol-Scaled Tilt |
|---|---:|---:|---:|---:|---:|
| CAGR | 7.13% | 7.17% | 7.15% | 7.13% | 7.14% |
| Net Sharpe | 0.948 | 0.958 | 0.951 | 0.949 | 0.949 |
| Max drawdown | -11.60% | -11.62% | -11.63% | -11.60% | -11.60% |
| CVaR 5% weekly | -2.49% | -2.48% | -2.50% | -2.49% | -2.49% |
| CVaR 1% weekly | -3.81% | n/a | -3.81% | -3.81% | -3.81% |

## 2. Profit-Taking Comparison

Best primary profit-taking variant by v3 options Sharpe: `no_target`.

| Profit Variant | Trades | Sharpe | CAGR | MaxDD | Sharpe ex Top 3 | Partial Trigger | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| `no_target` | 12 | 0.951 | 7.15% | -11.63% | 0.947 | 0.00% | REJECT |
| `full_100` | 12 | 0.951 | 7.15% | -11.63% | 0.947 | 0.00% | REJECT |
| `partial_runner` | 12 | 0.951 | 7.15% | -11.63% | 0.947 | 0.00% | REJECT |

## 3. Focused Sensitivities

| Variant | Trades | Sharpe | Tilt Sharpe | MaxDD | Late Block Rate | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `v3|dte=60-90|mny=atm_5otm|profit=no_target` | 12 | 0.951 | 0.949 | -11.63% | 89.79% | REJECT |
| `v3|dte=60-90|mny=atm_5otm|profit=full_100` | 12 | 0.951 | 0.949 | -11.63% | 89.79% | REJECT |
| `v3|dte=60-90|mny=atm_5otm|profit=partial_runner` | 12 | 0.951 | 0.949 | -11.63% | 89.79% | REJECT |
| `v3|dte=90-120|mny=atm_5otm|profit=partial_runner` | 19 | 0.949 | 0.949 | -11.64% | 83.16% | REJECT |
| `v3|dte=60-90|mny=itm_atm|profit=partial_runner` | 19 | 0.952 | 0.949 | -11.64% | 81.79% | REJECT |
| `v3|dte=60-90|mny=otm_5_8|profit=partial_runner` | 1 | 0.948 | 0.948 | -11.60% | 99.59% | RESEARCH-ONLY |

## 4. Validation Gates

| Gate | Result | Detail |
|---|---|---|
| sharpe_vs_baseline | FAIL | v3 0.951 vs baseline 0.948 (need +0.05) |
| sharpe_vs_tilt | FAIL | v3 0.951 vs tactical tilt 0.949 (need +0.03) |
| cagr_vs_baseline | FAIL | v3 0.0715 vs baseline 0.0713 (need +0.0025) |
| drawdown_ok | PASS | v3 -0.116 vs baseline -0.116 |
| cvar5_ok | FAIL | v3 -0.0250 vs baseline -0.0249 |
| cvar1_ok | FAIL | v3 -0.0381 vs baseline -0.0381 |
| sharpe_ex_best_ok | PASS | ex-best 0.949 vs baseline 0.948 |
| sharpe_ex_top3_ok | FAIL | ex-top3 0.947 vs baseline 0.948 |
| annual_premium_ok | PASS | 0.11% NAV/yr (cap 1.50%) |
| concurrent_premium_ok | PASS | 0.38% NAV concurrent (cap 0.75%) |
| enough_trades | PASS | 12 trades (need >= 10) |
| not_one_subperiod | PASS | trades present in 3/3 time-thirds |
| costs_conservative | PASS | IV markup x1.05 plus 5% entry and exit slippage on gross option notional |
| no_lookahead | PASS | signals lagged one week; verifier re-checks representative feature lag |
| matches_or_beats_tilt | PASS | v3 Sharpe 0.951 vs tactical tilt 0.949 |

## 5. Research Questions

1. Did staged entry improve results? Add-ons occurred in 58.33% of main trades, but the main variant did not clear material gates.
2. Did smaller sizing preserve the defensive profile better? Yes mechanically: max drawdown stayed close to baseline, but the edge was also very small.
3. Did late-entry filtering improve trade quality? It blocked 89.79% of logged candidates; this preserved risk but also reduced opportunity.
4. Did partial profit-taking plus runner improve robustness? The best primary profit variant was `no_target`; the main partial-runner variant still failed top-3 robustness.
5. Which profit-taking variant worked best? `no_target` by full-period Sharpe in the primary setup.
6. Did v3 beat the ETF baseline? Sharpe was 0.951 vs baseline 0.948, but not by the required +0.05.
7. Did v3 beat tactical ETF tilt? Sharpe was 0.951 vs tactical tilt 0.949, below the required +0.03 edge.
8. Did v3 survive best-trade and top-3 removal? Ex-best 0.949; ex-top3 0.947.
9. Did max drawdown and CVaR remain acceptable? Drawdown stayed close; CVaR gates decide this strictly in the table above.
10. Did the result depend on one subperiod? See the not_one_subperiod gate.
11. Were there enough trades? Main variant had 12 trades.
12. Status: `REJECT`.
13. Next data required: real historical option chains with bid/ask, IV skew, term structure, expirations, dividends, and realistic fill modeling.

## 6. Proxy Caveats

- Pricing is Black-Scholes on lagged realized-vol proxies, marked up for IV and slippage.
- No real historical chains, no bid/ask history, no skew, no term structure, no fill model.
- This cannot establish production validity. Real chain testing is required before any trust decision.
