# SysTradeBench application note

The paper is a benchmark for governed strategy-to-code systems, not a source of trading alpha. Batch 44 adopted its most relevant controls: canonical frozen semantics, deterministic hashes, stage/action trace comparison, static and runtime anti-leakage tests, behavioral micro-scenarios, structured audit logs, and a future patch budget.

The runtime prefix test proved materially useful: shocking only the first price observation after a decision date changed the legacy-equivalent date-t HRP and ETF weights. That exposed an inherited one-week allocator lookahead that ordinary return-path equivalence did not detect.

The paper's own profitability evidence should not be imported. Its D4 tests use sampled 10-bar windows and zero costs; full OOS and cost sweeps are explicitly deferred. We therefore use SysTradeBench as engineering governance and keep profitability experiments under Version 2's existing frozen, cost-aware research protocol.

Source: https://arxiv.org/html/2604.04812v1
