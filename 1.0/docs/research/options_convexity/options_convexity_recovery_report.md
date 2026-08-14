# Options Convexity Recovery Research Report

> Standalone research extension. Not production. v1/v2 options outputs are preserved.

**Final verdict: `RESEARCH-ONLY`**

> PROXY RESULTS - APPROXIMATE, NOT PRODUCTION-GRADE. No historical option-chain
> data, no real bid/ask, no true IV skew, no term structure, no real fill model.

## 1. Research Question

Earlier options work failed because it treated options as a normal bullish ETF overlay.
This experiment asks a narrower question: can long-premium upside convexity help only
during defensive-to-risk-on recoveries, when trend acceleration and volatility
normalization create enough expected-move surplus to clear option breakevens?

## 2. Main Predeclared Config

- Variant: `outright_call|dte=60-120|PT`.
- Underlyings: SPY and QQQ.
- Per-trade premium-at-risk: 0.50% NAV.
- Concurrent cap: 1.00% NAV; annual cap: 2.00% NAV.
- Trades: 22; activations/year: 1.031; premium-at-risk/year: 0.52%.

## 3. Full-Period Comparison

| Metric | ETF Baseline | v1 Rejected | v2 Rejected Main | Recovery Options | Tactical ETF Tilt |
|---|---:|---:|---:|---:|---:|
| CAGR | 7.13% | 7.13% | 7.13% | 7.17% | 7.14% |
| Ann. vol | 7.52% | 12.37% | 8.60% | 7.48% | 7.52% |
| Net Sharpe | 0.948 | 0.577 | 0.830 | 0.958 | 0.950 |
| Sortino | 1.176 | 0.578 | 0.987 | 1.186 | 1.178 |
| Max drawdown | -11.60% | -27.51% | -18.86% | -11.62% | -11.60% |
| CVaR 5% weekly | -2.49% | -3.95% | -2.95% | -2.48% | -2.49% |
| CVaR 1% weekly | -3.81% | n/a | n/a | -3.78% | -3.80% |

## 4. Trade Economics

- Option hit rate: 59.09%.
- Average / median trade return: 19.48% / 20.59%.
- Worst / best trade return: -99.97% / 191.18%.
- Sharpe excluding best trade: 0.954; excluding top 3: 0.946.
- Upside capture: 0.994; downside capture: 0.990.

## 5. Tactical ETF Tilt Test

The same entry signals were also expressed as a small tactical ETF overweight. This
checks whether options add value beyond simply leaning further into SPY/QQQ.

Main recovery options Sharpe is 0.958 versus tactical tilt 0.950.
Options minus tilt Sharpe: 0.008; options minus tilt CAGR: 0.03%.

## 6. Descriptive Sweep

Best descriptive recovery variant by full-period Sharpe: `outright_call|dte=60-90|PT`
 with Sharpe 0.969. This is descriptive only and does not change the main verdict.

| Variant | Trades | Options Sharpe | Tilt Sharpe | Options MaxDD | Sharpe ex Top 3 | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `outright_call|dte=60-90|PT` | 18 | 0.969 | 0.950 | -11.57% | 0.955 | RESEARCH-ONLY |
| `outright_call|dte=60-90|noPT` | 16 | 0.964 | 0.950 | -11.53% | 0.951 | RESEARCH-ONLY |
| `outright_call|dte=90-120|PT` | 24 | 0.964 | 0.951 | -11.49% | 0.952 | RESEARCH-ONLY |
| `outright_call|dte=90-120|noPT` | 21 | 0.948 | 0.951 | -11.66% | 0.936 | RESEARCH-ONLY |
| `outright_call|dte=60-120|PT` | 22 | 0.958 | 0.950 | -11.62% | 0.946 | RESEARCH-ONLY |
| `outright_call|dte=60-120|noPT` | 19 | 0.946 | 0.951 | -11.66% | 0.939 | RESEARCH-ONLY |
| `backspread_1x2|dte=60-90|PT` | 0 | 0.948 | 0.948 | -11.60% | 0.948 | RESEARCH-ONLY |
| `backspread_1x2|dte=60-90|noPT` | 0 | 0.948 | 0.948 | -11.60% | 0.948 | RESEARCH-ONLY |
| `backspread_1x2|dte=90-120|PT` | 0 | 0.948 | 0.948 | -11.60% | 0.948 | RESEARCH-ONLY |
| `backspread_1x2|dte=90-120|noPT` | 0 | 0.948 | 0.948 | -11.60% | 0.948 | RESEARCH-ONLY |
| `backspread_1x2|dte=60-120|PT` | 0 | 0.948 | 0.948 | -11.60% | 0.948 | RESEARCH-ONLY |
| `backspread_1x2|dte=60-120|noPT` | 0 | 0.948 | 0.948 | -11.60% | 0.948 | RESEARCH-ONLY |

## 7. Validation Gates

| Gate | Result | Detail |
|---|---|---|
| Sharpe improves materially | FAIL | options 0.958 vs baseline 0.948 (Δ +0.010, need +0.1) |
| Max drawdown not materially worse | PASS | options -0.116 vs baseline -0.116 |
| CVaR 5% not materially worse | PASS | options -0.0248 vs baseline -0.0249 |
| CVaR 1% not materially worse | PASS | options -0.0378 vs baseline -0.0381 |
| Survives best-trade removal | PASS | Sharpe ex-best 0.954 vs baseline 0.948 |
| Survives top-3 removal | FAIL | Sharpe ex-top3 0.946 vs baseline 0.948 |
| Competitive vs tactical ETF tilt | PASS | options Sharpe 0.958 vs tactical-tilt 0.950 |
| Enough activations to study | PASS | 22 trades (need >= 10) |
| Activations remain rare | PASS | 1.03 activations/yr (max 8.0) |
| Annual premium-at-risk within cap | PASS | 0.52% NAV/yr (cap 2.0%) |
| Concurrent premium-at-risk within cap | PASS | max concurrent 1.00% NAV (cap 1.0%) |
| Train/holdout consistency | PASS | train 0.828/0.817; holdout 2.200/2.179 |
| Not isolated to one period | PASS | trades present in 3/3 time-thirds |
| Not harmful in panic weeks | PASS | mean options-vs-baseline weekly diff in panic = -0.00001 |
| Costs conservative | PASS | entry+exit slippage 5% each on gross + IV markup x1.05; held to time-stop |
| No lookahead | PASS | all signals lagged 1wk (verifier re-checks shift relationship) |

## 8. Verdict Reasoning

14/16 validation gates passed on the predeclared main config.
The recovery framing improves the shape versus v1/v2, but it does not clear the material Sharpe and robustness bar. Keep as research-only.

## 9. Proxy Assumptions

- Historical option chains are unavailable, so this is a Black-Scholes proxy on lagged realized volatility.
- IV is marked up by 1.05 and entry/exit slippage is charged at 5% of gross option notional.
- No true bid/ask, skew, term structure, American exercise, dividends, or chain-selection constraints.
- The 1x2 backspread is rejected when the modeled risk-zone loss is too large relative to strike width.
- Results are directional research evidence only and cannot establish production validity.
