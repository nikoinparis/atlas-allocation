# A17: volatility-managed market exposure, long-only — pre-registration

Written and committed before any return in this test was computed. ^GSPC (1928–) and ^IRX
(1960–) were downloaded; only their first dates were read.

## Why this is not a closed idea

Volatility management appeared here only as an overlay on residual momentum (Step 74) and as a
target-vol multiplier that averaged 0.992 and never bound (Step 76). It was never tested on the
market itself against an exposure-matched null. The mechanism differs from every closed family:
volatility is highly forecastable month to month while expected return does not rise with it
(Moreira & Muir, JF 2017), so cutting exposure when recent variance is high should raise Sharpe.
Cederburg, O'Doherty, Wang & Yan (JFE 2020) found the gains do not survive out of sample across
103 factor strategies; whether the *market* version survives is what this asks.

## Rule (one construction)

At each month-end: realised variance = variance of the last 21 daily returns × 252. Exposure for
the next month = **min(1, target / realised variance)**, target = the **expanding median** of all
previous month-end realised variances (causal; first 60 months burn-in). Remainder in T-bills.
**No leverage: exposure capped at 1.** 10 bps one-way on |Δexposure|.

## Data and windows

- 1993-02 to 2026-09: SPY total return, BIL (SHY before 2007-06) as cash. **Primary window.**
- 1933-01 to 1992-12: ^GSPC price index (no dividends) and ^IRX as cash from 1960, zero before.
  Independent of the SPY era; context and replication.
- 2016-01 to 2026-09 reported separately as post-publication.

## Null

Constant mix of the market and T-bills at the rule's own average exposure in the same window,
rebalanced monthly. Placebo: 2,000 random permutations of the rule's monthly exposure series
(same exposures, timing destroyed).

## PASS requires all, in the primary window, at 10 bps

1. Sharpe (excess of T-bill) ≥ null + 0.10,
2. placebo p < 0.05,
3. the 1933–1992 window also shows Sharpe ≥ null (same sign),
4. the 2016–2026 window shows Sharpe ≥ null (same sign).

Trials: 1. Cumulative static/timing trials on the market in this project, for the record: 13
(Step 321) + 10 (Step 334) + 4 (Step 338) + 1 (B8) + this one.

## Reported alongside

0/10/50/100 bps; max drawdown; 1929–32 cannot be tested (burn-in); 1987, 2008–2009, 2020, 2022.
CAGR against SPY buy-and-hold, because a rule that wins on Sharpe by holding less equity still
earns less in absolute terms and the owner should see that number.
