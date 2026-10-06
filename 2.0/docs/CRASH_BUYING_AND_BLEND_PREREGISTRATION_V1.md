# Crash-buying, and a 1.0 + 2.0 blend: pre-registration

Written and committed 2026-10-06, **before either test computed a return.** Both ideas came from
the owner on 2026-10-06. No financing anywhere: no borrowing, and nothing above 100% invested.
Prices come from `data/etf_weekly_panel_v1` (weekly, adjusted).

---

## Part A — Buy after a crash

**Owner's idea.** After a disaster (COVID, the Ukraine invasion and others) the market falls.
Can that be exploited systematically?

**Never tested here.** Steps 319–321 tested the opposite trade, going defensive during stress.

### A1. Named-event study (descriptive only, NOT a test)
These events are picked with hindsight, so a list like this is lookahead by construction: it
leaves out the disasters after which the market did not fall, or kept falling. Reported for
intuition only, with SPY's forward 4/13/26/52-week return from the close of the event week, set
against the unconditional average for the same horizon.

| event | event week (Friday) |
|---|---|
| 9/11 | 2001-09-21 |
| Lehman | 2008-09-19 |
| Fukushima | 2011-03-11 |
| US downgrade | 2011-08-05 |
| Brexit vote | 2016-06-24 |
| COVID first crash week | 2020-02-28 |
| Ukraine invasion | 2022-02-25 |
| SVB failure | 2023-03-10 |
| Tariff announcement | 2025-04-04 |

### A2. The causal rule (the actual test)
- **Normal state:** 70% SPY / 30% SHY.
- **Crash state:** 100% SPY.
- **Entry:** SPY's close falls below its trailing 52-week high by at least the trigger (a
  downward crossing), observed at the week's close. The trade executes into the *next* week's
  return. After a hold of H weeks the book returns to normal; another entry needs a fresh
  crossing.
- **Grid:** trigger {10%, 20%, 30%} × hold {13, 26, 52} weeks = **9 trials. Bonferroni 0.0056.**
- **Window:** from SHY's first full year, 2003-01, to the panel end.
- **Costs:** 10 bps per unit of turnover (ETFs). 50 bps is also reported.
- **Null 1, exposure-matched constant mix:** SPY/SHY held at the strategy's own average SPY
  weight, rebalanced weekly. This answers "was it timing, or just more equity?"
- **Null 2, placebo:** the same number of entries at random weeks with the same hold, 2,000 draws.
  p is the share of draws whose Sharpe is at least the rule's.
- **PASS needs all of:**
  1. Sharpe and CAGR above Null 1;
  2. placebo p < 0.0056;
  3. a CAGR edge over Null 1 in both 2003–2014 and 2015–2026.

---

## Part B — Combine the best of 1.0 with the best of 2.0

**Components, fixed:**
- **1.0 side:** static equal-weight SPY/GLD/SHY, Step 321's distilled result (1.0's value was
  diversification, not timing).
- **2.0 side:** the headline residual book, unlevered. For 2013-04 to 2022-12 that is Step 290's
  rebuilt residual composite (`evidence/composites_out_of_sample_v1/path__residual_composite__50bps.csv`,
  genuinely out of sample). From 2023 it is `evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv`
  (in sample). The two constructions are close, not identical, and that is stated.

**One blend, declared:** 50% 1.0 side / 50% 2.0 side, rebalanced weekly, with 10 bps charged on
the rebalancing turnover between sleeves. Nothing else is tried.

**Null, which is the question that matters:** the same blend with the 2.0 book replaced by SPY,
i.e. 50% SPY/GLD/SHY + 50% SPY. The blend is only worth having if the 2.0 book beats SPY in that
seat.

**Windows:**
- 2013-04 to 2022-12 (out of sample for the 2.0 side);
- 2023-01 to 2025-04-03;
- 2025-04-04 to the end.

**PASS:** blend Sharpe above the null's in all three windows. One trial.

The full-period and per-window CAGR, Sharpe, maximum drawdown, 2020 and 2022 are reported for
the blend, the null, both components and SPY.
