# Options Convexity Overlay — Research Report

> **Standalone research experiment.** NOT Track A/B/C/D. Does NOT modify or
> import production allocation logic. Not promoted into the main ETF strategy.

**Final verdict: `REJECT`**

> ⚠️ **PROXY RESULTS — APPROXIMATE, NOT PRODUCTION-GRADE.** No real historical
> option-chain data was available. Spreads are priced with Black-Scholes using a
> realized-volatility proxy for implied volatility, with a conservative IV markup
> and entry slippage that bias the model AGAINST the overlay. Treat all figures as
> directional evidence only.

## 1. Setup

- Baseline: production pin `improved_frontier_phase5_fragility_guard` (weekly net returns).
- Underlyings: SPY, QQQ, IWM, TLT, GLD.
- Structure: bull call spread, ~91 DTE (~13 weeks), held to expiry, non-overlapping per underlying.
- Premium budget: 2% default, hard cap 3% total; self-funded by reducing the matching ETF.
- Costs: entry slippage 5%, IV markup ×1.05, r=0.02.
- Mode: `historical_proxy_black_scholes`.

## 2. Activity

- Option trades: **32** over 1110 weeks.
- Activations per year: **1.50**.
- Premium spent per year: **3.00%** of portfolio (sum of premium fractions).
- Option hit rate: **43.75%**; avg trade return 101.33%, median -72.37%, worst -100.00%, best 1449.28%.

## 3. Baseline vs Baseline + Overlay (full period)

| Metric | Baseline | + Overlay |
|--------|----------|-----------|
| CAGR | 7.13% | 7.13% |
| Ann. return (arith) | 7.18% | 7.69% |
| Ann. volatility | 7.52% | 12.37% |
| Net Sharpe | 0.948 | 0.577 |
| Sortino | 1.176 | 0.578 |
| Max drawdown | -11.60% | -27.51% |
| Calmar | 0.615 | 0.259 |
| CVaR 5% (weekly) | -2.49% | -3.95% |
| Hit rate (weekly) | 55.50% | 53.87% |

Incremental: CAGR 0.00%, Sharpe -0.371, max-drawdown impact -15.91%.

Turnover/cost note: the overlay adds episodic option premium spend (~3.00%/yr) and reduces the matching ETF by the same amount; it does not add leverage. ETF-leg turnover impact is second-order and the dominant cost is the modelled option slippage/IV markup, already included.

## 4. Train / Holdout split

Holdout boundary: `2024-04-19` (time-ordered, no random split).

| Window | Baseline Sharpe | Overlay Sharpe | Baseline CAGR | Overlay CAGR |
|--------|-----------------|----------------|---------------|--------------|
| train | 0.817 | 0.488 | 6.08% | 6.02% |
| holdout | 2.179 | 1.464 | 17.91% | 18.49% |

## 5. Validation gates

| Gate | Result | Detail |
|------|--------|--------|
| 1. Net Sharpe improves | ❌ FAIL | overlay 0.577 vs baseline 0.948 |
| 2. Max drawdown not materially worse | ❌ FAIL | overlay -0.275 vs baseline -0.116 (Δ -0.1591) |
| 3. CVaR not materially worse | ❌ FAIL | overlay -0.0395 vs baseline -0.0249 (Δ -0.0146) |
| 4. Activates rarely | ✅ PASS | 1.50 activations/yr (cap 12.0) |
| 5. Not driven by one lucky trade | ❌ FAIL | Sharpe ex-best-trade 0.424 vs baseline 0.948 |
| 6. Survives train/holdout | ❌ FAIL | train Sharpe 0.488/0.817; holdout 1.464/2.179 |
| 7. Costs/slippage included | ✅ PASS | entry slippage (5%) + IV markup (x1.05) applied; baseline net of costs |
| 8. Proxy assumptions documented | ✅ PASS | PROXY mode clearly labelled approximate in report and outputs |

## 6. Interpretation & verdict

3/8 gates passed. **Verdict: `REJECT`.**

Core gates fail even under a proxy that is biased against options costs. The v0 convexity overlay does not improve the risk-adjusted profile. Shelve unless a materially different structure or activation logic is proposed.

## 7. Proxy assumptions (read before trusting numbers)

- **No real option data.** Implied vol is proxied by trailing 26-week realized vol (annualized), lagged one week, then marked up ×1.05. Real IV has skew, term structure, and a variance risk premium not modelled here.
- **Pricing.** Black-Scholes European calls; ETF options are American and pay dividends — ignored. Held to expiry, cash-settled at intrinsic.
- **Execution.** 5% entry slippage on the net debit; no early exit; no commissions beyond slippage. Liquidity assumed (the 5 ETFs are highly liquid); live mode applies real filters.
- **Accounting.** The option is measured against a STATIC hold of the matching ETF slice over the option's life (the self-funding source). The baseline itself rebalances weekly, so the counterfactual ETF slice is an approximation.
- **Determinism.** No randomness; identical inputs reproduce identical outputs.

