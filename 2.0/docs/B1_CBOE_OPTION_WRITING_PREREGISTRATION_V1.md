# B1 free first read: does selling S&P 500 option premium pay, after beta and costs?

Pre-registered 2026-09-30, before any return in this document was computed. Raw index files were
downloaded (so their date ranges are known) but no return, Sharpe or drawdown has been calculated.

## The question

Queue item B1 is the volatility risk premium: index options are, on average, priced above the
volatility that follows, so a seller of that insurance should earn a premium. Cboe publishes daily
histories of benchmark indices that mechanically sell S&P 500 options. They are free and they
cover 2008 and 2020. This test asks one thing: **after removing the S&P 500 exposure these
strategies obviously carry, is anything left, and does it survive costs and crises?**

Selling insurance has a known shape — many small gains and occasional large losses — so the
answer is judged on drawdown and crisis behaviour, not on Sharpe alone.

## Series (fixed; no others will be added after seeing results)

| Series | What it does | Starts |
|---|---|---|
| PUT | sells a 1-month at-the-money SPX put each month, fully cash-collateralised in T-bills | 1991 (daily from later) |
| WPUT | the same with weekly puts | 2006 |
| BXM | holds the S&P 500 and sells a 1-month at-the-money call (covered call) | 2002 in this file |
| BXMD | covered call with a 30-delta (out-of-the-money) call | 1986 |
| CNDR | sells a 1-month SPX iron condor | 1986 |

Benchmarks: S&P 500 total return (`^SP500TR`, Yahoo) and 13-week T-bill yield (`^IRX`, Yahoo) as cash.
Premium measure: VIX² against the S&P 500's realised variance over the following 21 trading days.

## Primary test (one per series, five in total)

Monthly returns (month-end to month-end). Regress each series' excess return on the S&P 500's
excess return: `r_i − rf = α + β (r_spx − rf) + ε`. **The claim under test is α > 0.** Compare each
series with its **beta-matched blend** (β × S&P 500 + (1 − β) × T-bills). Beating the blend on
return per unit of risk is what "the premium exists" means. Beating the S&P 500 outright is not the
test, because a lower-beta strategy can beat or lose to the index for reasons unrelated to the premium.

Significance: t-statistic on α with Newey-West errors (3 lags). Bonferroni across the five series:
α must clear p < 0.01. The five tests are the whole budget.

## Costs

The Cboe indices are computed from mid-quotes and exclude transaction costs. The cost ladder is
0, 10, 50 and 100 bps **of notional per roll**: monthly for PUT, BXM, BXMD and CNDR, weekly for WPUT.
So 10 bps a month is about 1.2% a year, and 10 bps a week is about 5.2% a year. That is deliberately
harsher on WPUT, because it trades four times as often.

## Windows (CLAUDE.md rule 6)

Full history for each series; 2005–2026; 2008–2009; 2020; 2022; 2023–2026.

## Reported for every series and window

CAGR, annualised volatility, Sharpe (excess over T-bills), maximum drawdown, worst month, skew of
monthly returns, β, α with t-statistic, and the same figures for the beta-matched blend.

## Robustness pass

- Leave-one-year-out: α with each calendar year removed. The worst case is reported, and the year
  whose removal hurts most is named.
- Crisis attribution: share of total excess return lost in the worst five months.
- Placebo control: the same regression with a synthetic "strategy" made of the S&P 500 at the same
  β plus zero-mean noise. This checks that the α machinery reports nothing when nothing is there.

## What would count as a finding

A series passes if **all** of these hold:
- α > 0 at p < 0.01 over the full history, after 10 bps a roll;
- α is positive in 2005–2026 **and** in 2023–2026;
- its 2008–2009 maximum drawdown is no worse than the beta-matched blend's by more than 10 points;
- α survives leave-one-year-out.

**A pass still does not make it a strategy.** The next step would be a design, with position sizing
and a tail hedge, a forward clock and the rest of the gate list in `README.md`. This is a free
first read to decide whether paid options data is worth buying.

## What would close B1

α indistinguishable from zero, or negative, after beta; or a premium that exists only because a
crisis was left out. Either outcome is recorded, and the ORATS/ThetaData purchase is declined.
