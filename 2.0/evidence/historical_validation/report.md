# Historical Component Validation

Generated: 2026-08-08

This is a falsification-oriented component test. It does not establish that a
strategy is profitable, safe, or suitable for live trading.

## Reproducible inputs

- The equity fixture contains 5,101 daily adjusted-close rows for SPY, TLT,
  and GLD from 2006-01-03 through 2026-04-14. It was copied from the 1.0 data
  hub without modifying 1.0. `fixtures/provenance.json` pins both source and
  output SHA-256 hashes plus the Yahoo metadata snapshot.
- The options fixture is the 29-bar SPY put-chain sample for 2024-06-03 checked
  into FlashAlpha at commit `e75838081d4e1adc3579fca834bdefe60fb25547`.
  Its observed SHA-256 is
  `f15e7cf7fee442c772040c2a212cff2565810f689af392ff348eb5e644280597`.
- Replays ran in disposable rootless Podman volumes. Repository installation
  was isolated; replay execution had no network and no host-directory mount.

The equity data is adjusted close, not an executable price tape. It cannot
test next-open execution, spreads, intraday slippage, or market impact. The
present-day three-ETF selection also has selection/survivorship bias.

## `bt` result

The deliberately fixed example was monthly equal weight among SPY, TLT, and
GLD when each had positive 252-day momentum and was above its 200-day mean.
Signals were shifted one observation before `bt` could act. This rule is a
probe instrument, not a promoted strategy.

| Scenario | Final normalized index | Holdout return (2021–2026-04-14) | Holdout max drawdown |
|---|---:|---:|---:|
| Zero commission | 668.72 | 63.98% | -26.83% |
| $0.005/share assumption | 666.60 | 63.88% | -26.84% |
| $0.02/share stress | 660.29 | 63.58% | -26.90% |
| SPY buy-and-hold benchmark | 796.17 | 102.28% | -24.50% |

Higher commissions monotonically reduced the result, and all reported values
were finite. However, the example failed the simple benchmark gate overall and
in the untouched date holdout: it returned less than SPY and also had a
slightly worse holdout drawdown. The commission stress is incomplete because
this adjusted-close replay does not model bid/ask spread, market impact, or
next-bar open prices.

Decision: retain `bt` only as a conditional research/backtest adapter behind
mandatory signal lagging and the platform-owned execution/accounting model.
Do not promote the example trading rule.

## FlashAlpha result

Eleven fixed 525/520 put-credit-spread limits were replayed against the real
fixture. Default settings filled 7/11. A stricter scenario—larger crossing
epsilon, narrower allowable relative spread, non-negative edge floor, and a
higher assumed two-leg entry fee—filled 0/11.

The result is useful because it exposes sensitivity rather than hiding it.
One 29-bar day is far too little data to estimate fill probability or P&L, and
the fee adjustment covers entry proceeds only, not exits or assignment.

Decision: retain FlashAlpha as a sandboxed experimental fill component behind
the platform quote/output guard. It is not approved for portfolio simulation
until it passes a much larger multi-date, multi-regime options fixture and its
known non-finite quote defect is either fixed upstream or permanently guarded.

## Gate outcome

| Gate | Outcome |
|---|---|
| Pinned provenance | Pass for the exact snapshots used |
| Offline deterministic replay | Pass |
| No-lookahead boundary | Pass only with platform guard / default next-bar offset |
| Adverse-cost sensitivity | Directionally pass, but incomplete execution costs |
| Simple benchmark comparison | Fail for the fixed `bt` example |
| Untouched date holdout | Measured; example fails SPY comparison |
| Multi-regime options generalization | Not tested; fixture is one day |
| Live or paper-trading approval | Not granted |

Machine-readable results are in `replays/ast-0022.json`,
`replays/ast-0047.json`, and `replays/summary.json`.
