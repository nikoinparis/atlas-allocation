# Options Convexity Recovery Research Plan

> Standalone research extension. This is not part of A/B/C/D workstreams, does not
> modify production allocation logic, and does not promote anything into production.
> v1/v2 options outputs are preserved and used only as rejected references.

## Hypothesis

Long-premium upside options may only be useful during rare defensive-to-risk-on
recovery transitions, when price acceleration, volatility normalization, and
expected-move surplus all support the trade. This experiment tests recovery
convexity, not generic bullish drift.

## Scope

- Underlyings: SPY and QQQ only.
- Structures: outright long calls and 1x2 call backspreads.
- DTE buckets: 60-90, 90-120, and combined 60-120.
- Sizing: 0.50% NAV premium-at-risk per trade, 1.00% concurrent cap, 2.00% annual cap.
- Funding: option premium/risk is compared against reducing the matching ETF exposure; no leverage.
- Exits: 21-30 DTE time stop, optional +100% profit target, thesis invalidation on panic or -8% underlying move.

## Activation Logic

Entries require positive SPY/QQQ baseline weight, recent defensive stress, an improving
current regime, no confirmed panic state, trend re-acceleration, and expected move
surplus above the structure breakeven. Soft confirmations include defensive-to-risk-on
transition, recovery from recent low, positive MA slope, MA reclaim, VIX normalization,
VIX term-structure normalization, realized-vol control, and HYG/LQD credit improvement.

## Validation

The main predeclared config is outright_call, combined 60-120 DTE, with profit-taking.
Descriptive sweeps cover DTE bucket, structure, and profit-taking. Promotion decisions
do not cherry-pick the sweep. The tactical ETF tilt benchmark runs the same signal dates
using a small ETF overweight instead of options.

## Proxy Caveat

No real historical option chains are used. Pricing is Black-Scholes on a realized-vol
proxy with IV markup and slippage. There is no real bid/ask, IV skew, term structure,
historical chain selection, dividend handling, or fill model. Results are approximate
and cannot establish production validity.
