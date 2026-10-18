# Fresh-eyes review: what a quant firm would try next (2026-10-18, Step 369)

## Diagnosis

368 steps have fished in the most competitive pond in finance: cross-sectional selection of liquid US
stocks from public data at weekly-to-quarterly horizons, long-only and unlevered. The firms that win there
have at least one of three things: **breadth** (thousands of tiny, market-neutral, levered bets), **speed**,
or **proprietary data**. This project has none of the three by design, so a near-zero IC everywhere is the
expected result, not a sign of bad implementation. Steps 354-368 checked the implementation directly
(positive controls, link spot checks, precision reads) and the nulls held.

What remains available to a small, patient, long-only investor:

1. **Risk premia you are paid to hold**, combined well (equity, duration, gold, trend), judged on long
   external histories rather than a 14-year in-sample window.
2. **Event-driven risk-transfer trades with an identifiable counterparty**: someone pays you to take a risk
   they want rid of.
3. **Capacity niches** too small for funds: illiquid names where the published drifts actually live.
4. **Costs, taxes and drawdown control**, which matter more than signals at this size.

## Recommendations, ranked

| rank | idea | why it is different from what failed | data | effort | prior |
|---|---|---|---|---|---|
| **1** | **Merger arbitrage, cash deals, long the target only** (A30) | Not a signal: you sell insurance against deal failure. Low beta except in crashes. Mitchell & Pulvino (JF 2001): about 4%/yr excess after costs, 1963-1998. Spreads have compressed since 2002 but stay positive. Long-only works because cash deals need no short. | EDGAR, free: SC TO-T (tender offers), DEFM14A, 8-K 1.01 announcements with "$X per share in cash"; daily prices on disk | 2-3 sessions | moderate, as a low-correlation sleeve |
| **2** | **Diversifiers as an allocation, judged forward** (A31) | Step 340's 20% trend sleeve went the right way (Sharpe 1.00 vs 0.91, max drawdown −7.8% vs −12.7%) and was rejected as if it were alpha. A diversifier should be judged on its century-long record (Hurst, Ooi & Pedersen 2017) and its crisis behaviour, then frozen forward. | ETF prices, free | 1 session | moderate |
| **3** | **Drift in small, illiquid stocks with realistic costs** (A32) | Every drift here was tested on the top 500 or on names with $5M+ daily volume. Chan (2003) and PEAD say the effects live in small, illiquid names, which a small investor can trade and a fund cannot. Needs spread estimates (Corwin-Schultz from daily high/low). | Yahoo OHLC, free | 2 sessions | gross yes, net uncertain |
| 4 | Spin-offs (A33) | Forced selling by index funds and holders who never wanted the subsidiary. Cusatis, Miles & Woolridge (1993) found outperformance; recent evidence is mixed (recalled, not read). | EDGAR Form 10-12B, free | 1-2 sessions | low-moderate |

## Recorded so nobody proposes them again: published as gone in the US

- **Earnings-announcement premium.** Savor & Wilson (JF 2016) found 9.9%/yr; Heitz, Narayanamoorthy &
  Zekhnini (2020) report it has vanished in the US since the 2000s, though it survives abroad. Our
  58,503 results dates would allow a test, but the literature already answers it.
- **Pre-FOMC drift.** Lucca & Moench (JF 2015); disappeared after 2015 (Kurov, Wolfe & Gilbert, FRL 2021).
- **S&P index inclusion.** +7.4% in the 1990s to +0.3% in the last decade (Greenwood & Sammon, JF 2025).
- **SPAC arbitrage.** The opportunity closed with SPAC issuance after 2022 (recalled).

## Process

- **Stop new signal searches on the 2012-2026 US panel.** Each one adds to a multiple-testing count above 60
  trials in this sequence alone.
- **Diversifiers and risk premia** need a different test from signals: economic rationale, a long external
  history, crisis behaviour, then a frozen forward clock.
- **The forward clocks are the only clean evidence.** There are now seven stock and ETF clocks plus the
  quarterly avoid list. Protect them first.
