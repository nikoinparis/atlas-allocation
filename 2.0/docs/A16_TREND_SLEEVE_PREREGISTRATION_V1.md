# A16: long/short trend as a sleeve beside the static blend — pre-registration

Written and committed before any return in this test was computed. The AQR file was opened only
to read its column names (TSMOM, TSMOM^CM, ^EQ, ^FI, ^FX) and its date range (1985-01 to 2026-05).

## Question

Does adding a long/short time-series momentum sleeve to the static equal-thirds SPY/GLD/SHY blend
raise risk-adjusted return **after a retail fund's fee**, on data after the paper was published?

## Data

- AQR "Time Series Momentum: Factors, Monthly", column `TSMOM` (all 58 instruments), monthly
  excess returns. **Not point-in-time** (AQR rebuilds history on each update) and **gross of fees**.
- Fund return = T-bill (BIL monthly total return) + TSMOM excess return − **1.00%/yr fee** (DBMF
  charges 0.85%, KMLM 0.90%; the rest covers trading and tracking error). Used as-is, no rescaling.
- Blend: SPY/GLD/SHY equal thirds from Yahoo adjusted closes, monthly returns.

## Window

**Decision window: 2013-01 to 2026-05** — the paper was published in 2012 with data to 2009, so
this is post-publication. 2005–2012 is reported for context only and cannot pass or fail anything.

## The one decisive test

Portfolio P = 80% blend + 20% trend fund, rebalanced monthly, 10 bps on traded weight.
Comparison B = 100% blend, same rebalancing and costs.

**PASS requires both:**
1. Sharpe (excess of T-bill, monthly, annualised) of P minus B ≥ **+0.05**, and
2. one-sided moving-block bootstrap p (block 12 months, 5,000 draws) for that difference < **0.05**.

One test; no Bonferroni division needed beyond counting it. Trials: 1.

## Reported alongside, not part of the pass rule

- Trend fund alone: CAGR, Sharpe, max drawdown; alpha against SPY and against the blend (OLS on
  monthly excess returns, Newey-West t, 6 lags).
- P and B at 0/10/50/100 bps; windows 2008–2009 (context), 2020, 2022, 2023–2026.
- Leave-one-asset-class-out: rebuild the sleeve from the equal-weight of three of the four sub-factors,
  each dropped in turn.
- Live check: the same 20% sleeve using the actual ETFs DBMF (from 2019-06) and KMLM (from 2021-01),
  descriptive only.

## Kill

If the test fails, A16 closes. The trend sleeve is not re-run at another weight, fee, window or
sub-factor mix — any of those would be a new searched design and would need its own registration.

## Owner decision outstanding

Managed-futures ETFs hold futures with internal leverage and short positions. Whether that is
compatible with "no leverage" is the owner's call even if this passes.
