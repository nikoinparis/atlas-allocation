# B8: turn-of-the-month on SPY — pre-registration

Written and committed before any return in this test was computed.

## Rule (one construction, no parameters searched)

McConnell & Xu (FAJ 2008) window: hold SPY for the **last trading day of each month and the first
three trading days of the next** (returns of days −1, +1, +2, +3), entering at the close of day −2
and exiting at the close of day +3. Otherwise hold BIL (SHY before 2007-06). Daily adjusted closes
from Yahoo.

## Window

**Decision window: 2006-01 to 2026-09** — McConnell & Xu's sample ends in 2005, so this is
post-publication. 2000–2005 is reported for context only.

## Null and pass rule

Null 1 (exposure-matched): a constant SPY/T-bill mix holding SPY at the rule's average exposure,
rebalanced monthly.
Null 2 (placebo): 2,000 versions of the rule using a random 4-consecutive-trading-day window inside
each month (same count of switches).

**PASS requires all three, at 10 bps one-way per switch:**
1. Sharpe (excess of T-bill) of the rule ≥ Null 1 + 0.10,
2. placebo p < 0.05 (share of random-window rules with Sharpe ≥ the rule's),
3. the rule's CAGR at 10 bps ≥ Null 1's CAGR.

Trials: 1.

## Reported alongside

0/10/50/100 bps; 2008–2009, 2020, 2022, 2023–2026; share of SPY's total return earned inside the
window; one leave-out: the result with the 5 best turn-of-month windows removed.

## Prior, stated before the test

Expected to fail on costs: about 24 switches a year at 100% of capital. It also holds equities
only ~19% of the time, so it is not a replacement for SPY even if it passes, only a low-exposure
sleeve.
