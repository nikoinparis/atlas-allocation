# Recovery Options Overlay v3 Research Plan

> Standalone research extension. Not Track A/B/C/D. No production behavior is modified,
> no existing production allocation logic is changed, and no result is promoted.

## Hypothesis

The prior recovery options design was research-only: it slightly improved the shape but
barely beat tactical ETF tilt and did not clearly survive top-3 trade removal. v3 tests
one focused improvement: smaller staged entries, late-entry blocking, and partial
profit-taking with a runner.

## Scope

- Underlyings: SPY and QQQ only.
- Structure: outright long calls only.
- DTE: 60-90 primary and 90-120 secondary.
- Moneyness: ATM to 5% OTM primary, with slightly ITM/ATM and 5-8% OTM sensitivities.
- Sizing: 0.125% NAV pilot plus 0.125% add-on; 0.25% normal full position.
- Caps: 0.75% concurrent premium-at-risk and 1.50% annual premium-at-risk.

## Variants

The primary DTE/moneyness setup compares exactly three profit-taking variants: no target,
full exit at +100%, and 50% sale at +100% with a runner. Additional focused sensitivities
use the partial-runner variant only.

## Proxy Caveat

Historical option chains are unavailable. Results use proxy Black-Scholes pricing on
lagged realized volatility with IV markup and slippage. Real historical option-chain
data is required before trusting any result.
