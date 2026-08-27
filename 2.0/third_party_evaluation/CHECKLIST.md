# Third-party evaluation checklist

This checklist is complete for the exact sources currently identifiable. A
completed check means the evaluation was performed, not that the tool was
approved for production.

- [x] Pin Kronos source, model, and tokenizer revisions.
- [x] Clone Kronos at the pinned commit in a disposable directory.
- [x] Compile its model source without installing dependencies or weights.
- [x] Run the pinned upstream 256-bar CPU regression fixture in a disposable environment; maximum relative difference was below the upstream tolerance.
- [x] Pass the real model forecast through the platform-owned feature contract.
- [x] Define and smoke-test a platform-owned OHLCV forecast-feature contract.
- [x] Prevent Kronos forecasts from directly creating orders.
- [x] Pin and probe OpenBB; identify the AGPL and provider-level data gates.
- [x] Pin and probe Scrapling; separate its software license from website and data rights.
- [x] Pin and probe NautilusTrader; restrict it to an execution-equivalence sandbox.
- [x] Pin and probe Everything Claude Code; classify it as workflow reference material.
- [x] Probe DAS Replay as a website and record why it is not reproducible automation evidence.
- [x] Block the ambiguous “Trading Systems” item until an exact URL is supplied.
- [x] Write machine-readable raw results and an aggregate human-readable report.
- [x] Test manifest pins, fail-closed permissions, result generation, and the Kronos contract.

## Non-negotiable promotion boundary

Third-party tools may produce candidate data, forecasts, orders, or fills only
through a versioned adapter. The platform re-runs causal, cost-aware,
out-of-sample validation using its own accounting. No upstream performance claim
or example backtest is accepted as evidence.
