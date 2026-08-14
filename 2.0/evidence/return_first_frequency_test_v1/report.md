# Return-first trading-frequency test

Tested the frozen monthly incumbent against full weekly refresh, weekly with a
5% turnover buffer, and monthly execution with a 15% emergency override. The
monthly incumbent remained the point leader at **41.66%** retrospective
holdout CAGR at 50 bps.

Full weekly refresh returned **20.64%**, buffered weekly **22.71%**, and
monthly-emergency **20.66%**. At zero costs, monthly returned **44.20%**, full
weekly **28.52%**, buffered weekly **29.34%**, and monthly-emergency **28.31%**.
The weekly shortfall therefore exists before fees and is amplified by annual
one-way turnover rising from 3.55 times capital for monthly to 10.56–12.70
times for the faster variants.

A one-week additional delay raised full weekly to **31.54%** and buffered
weekly to **31.63%**, but delayed monthly still led at **37.32%**. At 200-bps
costs full weekly fell to **-0.30%**, monthly-emergency to **0.29%**, and
buffered weekly to **4.75%**, versus **34.27%** for monthly.

Deterministic: **True**. ML embargo: **True**. Both truncated-history prefix
checks were exact. All portfolios were long-only and fully invested. This is
schedule-sensitivity evidence on an already selection-contaminated
retrospective candidate. The monthly incumbent was not replaced and no
forward-clock change, paper trading, or live trading was authorized.
