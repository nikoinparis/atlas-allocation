# Options Convexity Overlay — v2 Research Report

> **Standalone research experiment.** NOT Track A/B/C/D. Does NOT modify or import
> production allocation logic. v1 outputs are preserved unchanged. Not promoted.

**Final verdict: `REJECT`**

> ⚠️ **PROXY RESULTS — APPROXIMATE, NOT PRODUCTION-GRADE.** No real historical option-
> chain data. Spreads priced with Black-Scholes on a realized-vol IV proxy, with an IV
> markup, entry slippage, and a bid/ask half-spread proxy that bias results AGAINST the
> overlay. Directional evidence only.

## 1. What v2 changed vs v1

v1 used ETF-allocation signals to time options and was REJECTED (Sharpe, drawdown and
CVaR all worsened; the result leaned on one lucky winner). v2 adds an **options-specific**
signal engine that asks whether the ETF is likely to move *enough, soon enough* to beat the
spread's breakeven, and only fires in acceleration / recovery regimes when vol is not
expensive. v2 also sweeps DTE, structure and a cumulative entry-filter ablation, and sizes
smaller (default 1% vs 2%).

## 2. Pre-registered MAIN config

- Structure: `spread_3_7_10_20` (Call spread: long 5% OTM, short 15% OTM (v1-style).)
- DTE bucket: `45-75` (~60 days)
- Entry filter ablation level: **5** (bullish_acceleration_breakeven_iv_transition)
- Premium budget: 1.0% default; hard cap 3% total; self-funded by reducing the matching ETF; no leverage.
- Underlyings: SPY, QQQ, IWM, TLT, GLD.

## 3. Baseline vs v1 (rejected) vs v2 MAIN (full period)

| Metric | ETF Baseline | v1 (rejected) | v2 MAIN |
|--------|--------------|---------------|---------|
| CAGR | 7.13% | 7.13% | 7.13% |
| Ann. return (arith) | 7.18% | 7.69% | 7.27% |
| Ann. volatility | 7.52% | 12.37% | 8.60% |
| Net Sharpe | 0.948 | 0.577 | 0.830 |
| Sortino | 1.176 | 0.578 | 0.987 |
| Max drawdown | -11.60% | -27.51% | -18.86% |
| Calmar | 0.615 | 0.259 | 0.378 |
| CVaR 5% (weekly) | -2.49% | -3.95% | -2.95% |

v2 MAIN Sharpe excluding best trade: **0.776** (vs full overlay 0.830, baseline 0.948).

## 4. v2 MAIN activity & trade economics

- Trades: **27**; activations/yr: **1.26**; premium spent/yr: **1.26%**.
- Avg DTE: **60.000** days; avg long-leg moneyness: **5.00%** OTM.
- Option hit rate: **11.11%**; avg -52.48%, median -100.00%, worst -100.00%, best 573.66%.

Incremental vs baseline: CAGR 0.00%, Sharpe -0.119, max-drawdown impact -7.26%.

## 5. DTE sweep (structure & filters fixed at MAIN)

| DTE bucket | Trades | Act/yr | Avg DTE | Full Sharpe | Holdout Sharpe | Full MaxDD | Sharpe ex-best |
|-----------|--------|--------|---------|-------------|----------------|------------|----------------|
| 21-45 | 3 | 0.14 | 33.000 | 0.948 | 2.167 | -11.60% | 0.952 |
| 45-75 | 27 | 1.26 | 60.000 | 0.830 | 2.322 | -18.86% | 0.776 |
| 75-100 | 29 | 1.36 | 87.000 | 0.854 | 2.237 | -13.98% | 0.837 |
| 100-150 | 36 | 1.69 | 125.000 | 0.722 | 1.333 | -16.55% | 0.644 |

## 6. Structure sweep (DTE & filters fixed at MAIN)

| Structure | Preferred | Trades | Full Sharpe | Full MaxDD | Full CVaR | Sharpe ex-best |
|-----------|-----------|--------|-------------|------------|-----------|----------------|
| spread_3_7_10_20 | yes | 27 | 0.830 | -18.86% | -2.95% | 0.776 |
| spread_atm_10 | yes | 50 | 0.883 | -15.79% | -2.65% | 0.864 |
| spread_delta_40_20 | yes | 47 | 0.859 | -15.13% | -2.76% | 0.845 |
| naked_call_5otm | no (compare) | 27 | 0.830 | -18.86% | -2.94% | 0.777 |

## 7. Entry-filter ablation (DTE & structure fixed at MAIN)

| Level | Filters | Trades | Act/yr | Full Sharpe | Full MaxDD | Sharpe ex-best |
|-------|---------|--------|--------|-------------|------------|----------------|
| 1 | bullish_only | 130 | 6.09 | 0.302 | -44.72% | 0.120 |
| 2 | bullish_acceleration | 90 | 4.22 | 0.449 | -30.50% | 0.347 |
| 3 | bullish_acceleration_breakeven | 36 | 1.69 | 0.671 | -23.09% | 0.566 |
| 4 | bullish_acceleration_breakeven_iv | 33 | 1.55 | 0.670 | -23.09% | 0.564 |
| 5 | bullish_acceleration_breakeven_iv_transition | 27 | 1.26 | 0.830 | -18.86% | 0.776 |

## 8. Validation gates (evaluated on the pre-registered MAIN config)

| Gate | Result | Detail |
|------|--------|--------|
| 1. Net Sharpe improves | ❌ FAIL | overlay 0.830 vs baseline 0.948 |
| 2. Max drawdown not materially worse | ❌ FAIL | overlay -0.189 vs baseline -0.116 (Δ -0.0726) |
| 3. CVaR not materially worse | ❌ FAIL | overlay -0.0295 vs baseline -0.0249 (Δ -0.0045) |
| 4. Not driven by one best trade | ❌ FAIL | Sharpe ex-best 0.776 vs baseline 0.948 |
| 5. Sharpe ex-best retains edge | ✅ PASS | Sharpe ex-best 0.776 vs full overlay 0.830 (>=80% retained) |
| 6. Activates rarely but meaningfully | ✅ PASS | 1.26 activations/yr (want 0.3-12.0) |
| 7. Train & holdout both reasonable | ❌ FAIL | train 0.692/0.817; holdout 2.322/2.179 |
| 8. Costs/slippage included | ✅ PASS | entry slippage 5% + half-spread proxy 5% + IV markup x1.05 |
| 9. No lookahead bias | ✅ PASS | all signals lagged 1wk (verifier re-checks shift relationship) |
| 10. Proxy assumptions documented | ✅ PASS | PROXY mode labelled approximate in report and outputs |
| 11. Best variant not overfit-selected | ✅ PASS | MAIN config pre-registered (not chosen by maximizing the sweep) |

## 9. Answers to the v2 research questions

1. **Did shorter DTE help?** Best bucket: no bucket helped. See §5 — shorter DTE shrinks both the premium and the achievable move; the sweep shows whether the trade-off nets out.
2. **Did breakeven-aware entry help?** Compare L2→L3 in §7: Sharpe 0.449 → 0.671.
3. **Did acceleration/recovery filtering help?** Compare L1→L2 and L4→L5 in §7: 0.302 → 0.449; 0.670 → 0.830.
4. **Did IV/richness filtering help?** Compare L3→L4 in §7: 0.671 → 0.670.
5. **Best DTE bucket:** no bucket helped.
6. **Best structure:** no structure helped (call spreads remain the default preferred; the naked call is comparison-only).
7. **Did v2 improve Sharpe / MaxDD / CVaR?** Sharpe: no (0.948→0.830); MaxDD: worse; CVaR: worse.
8. **Robust or one lucky trade?** NOT robust — the edge leans on the single best trade.
9. **Status:** `REJECT`.
10. **Before real capital:** real historical option-chain data (true bid/ask, IV skew &
    term structure), live-execution modelling, early-exit / roll logic, dividend handling,
    and out-of-sample confirmation on data not used to design these filters.

## 10. Verdict reasoning

6/11 gates passed.
Core gates fail even under a cost-biased proxy. The v2 options-aware design does not improve the risk-adjusted profile as posed. Keep v1 and v2 both shelved unless a materially different idea appears.

## 11. Proxy assumptions

- IV proxied by trailing 13-week realized vol (lagged), marked up ×1.05. No skew/term structure.
- Black-Scholes European calls; ETF options are American & pay dividends — ignored. Held to expiry, cash-settled at intrinsic.
- Costs: 5% entry slippage + 5% bid/ask half-spread proxy on the debit; no early exit; liquidity assumed for the 5 ETFs.
- Option measured vs a static hold of the matching ETF slice over the option's life; baseline rebalances weekly (approximation).
- Expected forward move is a momentum-persistence PROXY (trailing 12w drift projected over the horizon), not a forecast model.
- Deterministic: identical inputs reproduce identical outputs.

