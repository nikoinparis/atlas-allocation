# Portfolio Optimizer 2.0 Dashboard

Streamlined dark-mode research dashboard for the Version 2 strategy library.
It compares five saved simulations, including the corrected 150.86% trailing
52-week residual-controlled candidate, and displays portfolio value, calendar
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
```

This is a research interface only. Results are simulated, some candidates were
selected after observing the displayed history, and the leading candidate is
only 0/52 through its untouched forward protocol. It has no brokerage
connection and cannot place trades.
