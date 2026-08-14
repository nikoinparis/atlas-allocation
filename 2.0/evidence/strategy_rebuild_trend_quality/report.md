# Point-in-Time Rebuild: Trend Quality Strategy

This is an independent portfolio re-execution from the five dated tradable signal files. It does not reuse the saved strategy returns. Before BIL has a price known on the decision date, the defensive allocation is explicitly recorded as zero-yield USD cash.

## Result

- Current signal files reproduce the old saved positions: **no**.
- The difference affects 203 weekly rows across 47 rebalance dates, from 2006-08-25 to 2026-03-20.
- Five one-week signal-lag reconciliations passed: **yes**.
- Unpriced nonzero exposures: **0**.
- Cash is explicit for 33 weeks; BIL first becomes observable on 2007-06-01.
- Evidence label: **B-rebuilt, research only**. It is not Grade A and is not approved for live money.

## Performance comparison

| Strategy | Annual return | Sharpe | Max drawdown | Since-2021 return | Since-2021 Sharpe |
|---|---:|---:|---:|---:|---:|
| Rebuilt v2 | 9.97% | 0.756 | -26.25% | 14.17% | 1.055 |
| Original saved | 10.59% | 0.800 | -26.25% | 14.17% | 1.044 |
| Current Grade B | 7.03% | 0.739 | -20.16% | 7.96% | 0.918 |
| SPY | 10.54% | 0.660 | -54.61% | 13.71% | 0.883 |

## Trading-cost stress

- 10 bps: 9.97% annual return, 0.756 Sharpe.
- 25 bps: 9.65% annual return, 0.736 Sharpe.
- 50 bps: 9.13% annual return, 0.701 Sharpe.

## What this does and does not prove

The return accounting, one-week execution timing, monthly portfolio construction, turnover costs, and missing-price handling are now reproducible. The current signal files do not exactly reproduce the older saved holdings, so the old headline result is not treated as validated; the lower rebuilt result is the candidate of record. The backtest remains selected on already-seen history and uses a previously researched ETF universe. Its numbers are stronger evidence than the saved artifact, but they are not a promise of future profit. The locked forward test beginning 2026-08-14 remains required.
