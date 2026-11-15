# Portfolio Optimizer 2.0 Dashboard

Streamlined dark-mode research dashboard for the Version 2 strategy library.
It displays five research portfolios and ten forward-clock histories with portfolio value, calendar
returns, allocation history, holdings changes, stock-price inspection, and
configurable starting-capital scenarios.

## Run locally

```bash
npm install
npm run dev
```

The checked-in `public/return-first-dashboard.json` is generated from sealed
Version 2 evidence artifacts. Rebuild it from the `2.0` directory with the
project's configured Python or Podman research runtime:

```bash
python3 dashboard/scripts/build-return-first-dashboard.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python dashboard/scripts/extend-dashboard-daily.py
.venv/bin/python scripts/build_clock_histories_v1.py
```

The activity refresh preserves saved historical daily returns through each final
allocation date and continues the original selection/allocation rules with newer
prices and quarterly SEC inputs. It reconstructs the fixed ETF model (checking
its overlap against the saved weights), growth confidence and drift caps,
cash-conversion breadth, sector/tranche allocations, and quarterly residual ranks.
Trades execute after the day's price move; holdings drift between trades, and
50 bps is charged on security-level one-way turnover. This continuation's costs
can differ from the sealed research's nested-sleeve weekly accounting. It is a
retrospective simulation and never advances an untouched forward clock.

The wrapper checks the quarterly selection date and acquires/scores a new SEC
quarter when needed. Raw downloads are cached separately; the roster vintages,
normalized new factor inputs, scores, ETF training audit, and source hashes are
retained under `data/dashboard_continuation_*` and
`evidence/dashboard_continuation_v1`. Missing execution quotes route the intended
weight to cash and are listed in the simulation settings; missing held prices
fail the refresh. VIX inputs refresh when needed. All views open from the
strategy's first recorded date, and current return badges use the latest 252 sessions.

Forward clocks follow their actual recorded decisions after their start date,
including any frozen-book policy. Their separate price payloads now support the
holdings drill-down and attribution; only held intervals plus a 90-day chart
lead-in are sent, to keep the largest payload below the old 200 MB size.

This is a research interface only. Results are simulated, some candidates were
selected after observing the displayed history, and the leading candidate is
only 0/52 through its untouched forward protocol. It has no brokerage
connection and cannot place trades.
