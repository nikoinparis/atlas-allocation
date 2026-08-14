# Raw-Formula Point-in-Time Rebuild

All five strategy signals were recalculated in platform-owned code from weekly prices and weekly log returns. The saved strategy returns and saved signal values were not used to generate the new portfolio.

## Formula audit

- Intermediate columns checked: **31**.
- Numeric comparisons: **1,113,560**.
- Numeric mismatches above 1e-10: **0**.
- Missingness mismatches: **0**.
- Maximum absolute numerical error: **8.640e-12**.
- Complete formula reconstruction passed: **yes**.

## Portfolio audit

- Unpriced nonzero exposures: **0**.
- Fully invested and cost reconciliation passed: **yes**.
- Current inputs reproduce old saved positions: **no**; the old artifact remains comparison-only.
- Evidence label: **B-raw-rebuilt, research only**.

## Candidate-of-record performance

- Annual return: **9.97%**.
- Sharpe (0% risk-free rate): **0.756**.
- Maximum drawdown: **-26.25%**.
- Since-2021 annual return / Sharpe: **14.17% / 1.055**.
- 50 bps turnover stress return / Sharpe: **9.13% / 0.701**.
- Bootstrap 95% annual-return range: **4.99% to 15.14%**.
- Bootstrap 95% Sharpe range: **0.399 to 1.159**.
- Rolling three-year SPY win share: **22.75%**.

## Remaining limits

This is a weekly-data reconstruction, not a vintage-by-vintage vendor-data replay. The universe and strategy were selected using already-seen history, and the data can still contain survivorship or later-revision effects. Promotion remains blocked until the locked forward record has at least 52 untouched weeks.
