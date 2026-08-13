# Portfolio Optimizer 2.0 Dashboard

Interactive research dashboard for the frozen Return-First 60/40 candidate.
It displays the saved 50-bps simulation path, calendar returns, allocation
history, holdings changes, and configurable starting-capital scenarios.

## Run locally

```bash
npm install
npm run dev
```

The checked-in `public/return-first-dashboard.json` is generated from the
Version 2 evidence artifacts. Rebuild it from the `2.0` directory with the
project's configured Python or Podman research runtime:

```bash
python3 dashboard/scripts/build-return-first-dashboard.py
```

This is a research interface only. It has no brokerage connection and cannot
place trades.
