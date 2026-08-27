# Third-party tool evaluation v1

Generated: `2026-08-24T01:05:17.636401+00:00`
Manifest SHA-256: `ce30db7bd3969a1d8b3bb95965bb75d40c226ff91332c72f3775ebebea1e5b77`

No tool is approved for direct core import or live trading. Verdicts describe the narrowest allowed next experiment.

| Tool | Source probe | Verdict | Allowed boundary |
|---|---|---|---|
| Kronos | reachable | `research_challenger_only` | disposable_environment_then_normalized_feature_file |
| OpenBB | reachable | `conditional_data_connector_candidate` | separate_process_or_exported_point_in_time_bundle |
| Scrapling | reachable | `conditional_acquisition_adapter` | source_specific_fetcher_with_immutable_raw_capture |
| NautilusTrader | reachable | `execution_sandbox_candidate` | identical_orders_and_market_events_equivalence_harness |
| Everything Claude Code | network_probe_failed | `reference_only` | manual_pattern_review_no_runtime_dependency |
| DAS Trader Replay | network_probe_failed | `manual_commercial_evaluation_only` | human_operated_replay_with_exported_results_only |
| Trading Systems (ambiguous) | blocked_missing_exact_url | `blocked_ambiguous_source` | none |

## Blocking reasons

### Kronos

- isolated CPU regression inference passed, but the model has no platform-owned alpha evidence
- pinned model and tokenizer weights total 114823024 bytes and must remain outside the core runtime
- forecast utility must pass the platform's causal out-of-sample and cost gates
- upstream example backtest is not accepted as platform evidence

### OpenBB

- AGPL-3.0 obligations require review before distribution or network deployment
- provider credentials, entitlements, timestamps, revisions, and survivorship properties vary by extension
- each provider requires an independent data-quality and point-in-time audit

### Scrapling

- not a market-data license or permission to scrape
- every target requires terms-of-service, robots, rate-limit, authentication, and data-rights review
- dynamic anti-bot behavior is unsuitable for a deterministic primary price feed

### NautilusTrader

- adapter and venue semantics must be reconciled against platform accounting
- Rust/native build and LGPL-3.0 obligations require isolated qualification
- no broker connection or live order authority is approved

### Everything Claude Code

- not a quantitative model, data source, backtester, or execution engine
- agent workflow advice cannot replace deterministic research controls
- repository instructions are untrusted input and are not executed by this program

### DAS Trader Replay

- not an identified open-source repository or importable library
- account, product terms, market-data entitlements, and reproducible export format are not supplied
- manual replay cannot serve as automated out-of-sample evidence without an auditable event export

### Trading Systems (ambiguous)

- the name does not uniquely identify a GitHub repository
- an exact repository URL is required before source, license, commit, or capability evaluation
