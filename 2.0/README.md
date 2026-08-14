# Portfolio Optimizer 2.0

Version 2.0 is a safety-first systematic-trading research and simulation platform.
It will evaluate the projects and ideas cataloged by
`awesome-systematic-trading` without allowing third-party components to bypass
the platform's data, accounting, validation, portfolio, or risk controls.

## Initial scope

- Historical backtesting using point-in-time information
- Event-driven historical replay with realistic simulated orders
- Live paper trading using real market prices and no real capital
- A registry covering every project, resource, and idea considered
- Reproducible experiments with pinned source versions and data snapshots
- Portfolio construction across independently validated strategy sleeves
- Independent pre-trade and portfolio-level risk controls
- Full experiment, decision, order, fill, and override audit trails

Live brokerage execution is deliberately outside the initial scope. The core
interfaces may support it later, but no strategy will receive a direct path to a
broker.

## Operating principles

1. Evaluate every entry; do not install everything into one environment.
2. Keep the core platform independent from third-party strategy code.
3. Test simple baselines before sophisticated models.
4. Treat costs, spreads, latency, missing data, and failed orders as normal.
5. Never promote a strategy using in-sample performance alone.
6. Preserve failed and inconclusive results in the research registry.
7. Prefer no position when evidence or operational state is unreliable.

## Layout

- `config/` — evaluation and risk-gate definitions
- `docs/` — architecture, protocols, and design decisions
- `evidence/` — pinned source-health, license, and experiment evidence
- `research_registry/` — inventory and status of every evaluated entry
- `scripts/build_catalog_inventory.py` — reproducible pinned-catalog importer
- `scripts/run_batch_01_smoke_tests.py` — hardened pinned-source smoke tests
- `scripts/run_python_candidate_tests.py` — disposable Python install and offline test gate
- `scripts/run_behavioral_probes.py` — canonical offline behavior probes for promoted candidates
- `scripts/build_strategy_scoreboard.py` — bias-aware return, risk, cost, benchmark, and uncertainty scoreboard
- `scripts/rebuild_trend_quality_strategy.py` — independent point-in-time rebuild of the leading repair candidate
- `scripts/rebuild_raw_signals_and_strategy.py` — raw weekly-data reconstruction of all five candidate signals and the resulting portfolio
- `scripts/register_legacy_data_snapshot.py` — immutable registration and quarantine of the existing research dataset
- `scripts/ingest_vendor_bundle.py` — validated ingestion entry point for future point-in-time vendor exports
- `scripts/acquire_free_etf_snapshot.py` — rootless, isolated, no-cost ETF acquisition and revision monitoring
- `scripts/build_free_snapshot_research_pipeline.py` — daily-to-weekly preparation, raw-signal rebuild, simulation, and non-trading paper target
- `scripts/run_research_lab_batch_01.py` — standardized 288-experiment trend/momentum, portfolio-construction, and retrospective walk-forward batch
- `scripts/build_strategy_candidate_registry.py` — diverse provisional shortlist with explicit missing promotion gates
- `scripts/run_robustness_batch_02.py` — parameter-neighborhood, 25–100 bps cost, and point-in-time regime stress tests
- `scripts/run_ensemble_dependence_batch_03.py` — candidate correlations, holdings overlap, netted ensembles, marginal contribution, and 288-test adjustment
- `scripts/run_new_families_batch_04.py` — 288 mean-reversion, defensive, and distribution-yield carry experiments plus multi-family diagnostics
- `scripts/run_new_family_robustness_batch_05.py` — neighborhood, 100 bps, causal-regime, 576-trial statistical, and robust-family ensemble gates
- `scripts/run_covariance_portfolios_batch_06.py` — causal minimum-variance, maximum-diversification, two-sleeve HRP, inverse-volatility, and volatility-target portfolio comparison
- `scripts/run_portfolio_robustness_batch_07.py` — rolling-window, serial-bootstrap, stale/revised-input, and allocator-failure audit for the selected portfolio
- `config/challenger_program_v1.json` — predeclared six-track Batch 08–13 gates, resource limits, and no-cherry-picking rules
- `scripts/run_trade_buffering_batch_08.py` — causal symmetric, asymmetric, and cost-aware no-trade-band comparison
- `scripts/run_fragility_guard_batch_09.py` — independent causal reconstruction of the 1.0 quality/leadership fragility guard
- `scripts/build_independent_sleeves_batch_10.py` — reconciled value, carry, reversal, and macro-defensive third-sleeve decisions
- `scripts/run_portfolio_library_probes.py` — isolated identical-input probes for cvxportfolio, skfolio, Riskfolio-Lib, and PyPortfolioOpt
- `scripts/run_nested_ml_baseline_batch_12.py` — embargoed nested walk-forward ML bar with label-shuffle negative control
- `scripts/run_vectorbt_equivalence_batch_13.py` — sandbox-only numerical, determinism, fee, and speed probe for restricted-license vectorbt
- `scripts/run_ggg_return_ceiling_batch_52.py` — fixed return-ceiling attribution plus turnover, breadth, and 12%–16% volatility-budget challengers
- `scripts/run_ggg_execution_aware_batch_53.py` — fixed scheduled, emergency, deadband, asymmetric, and volatility-adaptive GGG execution challengers
- `scripts/acquire_official_treasury_curve.py` — immutable, no-key acquisition of the official daily U.S. Treasury par-yield curve
- `scripts/run_treasury_term_structure_batch_14.py` — lagged monthly carry/roll and slope-regime Treasury challenger with 10–100 bps costs and adjusted OOS bootstrap
- `scripts/build_sec_value_source_gate_batch_15.py` — SEC filing-vintage source gate that blocks performance claims until historical universe and delisting controls exist
- `scripts/run_cross_sectional_factor_baseline_batch_16.py` — Qlib/ml-quant-inspired causal factor panel, monthly rank-IC audit, and fixed non-ML portfolio hurdle
- `scripts/run_robust_cross_sectional_ml_batch_17.py` — isolated 2,924-fit nested ML ensemble with embargoed folds, five seeds, negative controls, stale-input stress, common accounting, and paired uncertainty
- `scripts/run_ml_confidence_overlay_batch_18.py` — causal ensemble-confidence tiers, capped ML overlays, trailing risk guards, 10–100 bps cost stress, calibration, and paired uncertainty
- `scripts/run_ml_strong_confidence_overlay_batch_19.py` — abstaining strong-confidence follow-up with stricter 100-bps and serial-bootstrap promotion gates
- `scripts/run_ml_cost_aware_persistent_overlay_batch_20.py` — buffered ML holdings, two-decision confidence persistence, prior 100-bps excess hurdle, and paired validation
- `scripts/run_etf_pairs_batch_21.py` — independent causal Engle-Granger ETF-pairs rebuild with FDR selection, borrow/trading costs, negative controls, and core-blend evidence
- `scripts/record_forward_portfolio_evidence.py` — frozen-manifest verification, decision-time capture, later return realization, and append-only forward-clock updates
- `scripts/run_guarded_weekly_forward_cycle.py` — single guarded Podman acquisition, immutable revision audit, exact-snapshot recorder handoff, and concurrency/duplicate protection
- `src/systematic_trader/research_lab.py` — deterministic experiment identity, metrics, and chronological selection
- `src/systematic_trader/portfolio_construction.py` — platform-owned equal, score, inverse-volatility, and combined weighting methods
- `src/systematic_trader/ensemble.py` — dependence, clustering, combined-weight, and serial block-bootstrap research helpers
- `src/systematic_trader/non_momentum_signals.py` — lagged reversal, RSI, low-volatility, drawdown-resilience, defensive, and distribution-yield signals
- `src/systematic_trader/term_structure_challenger.py` — official-curve parsing, full-week signal lag, and fixed Treasury carry/roll rules
- `src/systematic_trader/sec_value_research.py` — filed-date as-of selection that prevents future filings and amendments from leaking backward
- `src/systematic_trader/cross_sectional_factors.py` — lagged ETF factor features, deterministic cross-sectional ranks, and capped inverse-volatility weights
- `src/systematic_trader/ml_protocol.py` — fail-closed embargo and ML promotion gates
- `src/systematic_trader/ml_confidence.py` — outcome-free ensemble confidence, expanding thresholds, and trailing risk guards
- `src/systematic_trader/pair_protocol.py` — market-neutral pair state transitions, full traded-notional turnover, and borrow-cost accounting
- `src/systematic_trader/ggg_return_expansion.py` — causal breadth, cash-redeployment, no-trade-band, minimum-change, and staggered-transition transformations
- `src/systematic_trader/ggg_execution.py` — long-only execution scheduling, emergency overrides, per-asset deadbands, and state-aware trade buffers
- `src/systematic_trader/ggg_layer1.py` — exact portable reconstruction of GGG momentum, residual, reversal, quality, value, BAB, carry, and regime-feature inputs
- `research_registry/ml_candidates.json` — promising but non-final ML candidates retained with passed and failed gates
- `src/systematic_trader/strategy_allocation.py` — covariance shrinkage, bounded strategy-sleeve allocation, dynamic aggregation, and underlying concentration caps
- `src/systematic_trader/forward_evidence.py` — hash-chained append-only record validation and frozen-file integrity checks
- `config/strategies/` — immutable strategy-version manifests and forward-test locks
- `config/portfolios/covariance_minimum_variance_v1.json` — frozen, non-final Batch 07 portfolio rules and zero-week forward clock boundary
- `config/forward/covariance_minimum_variance_v1.json` — separately pinned forward protocol, snapshot timing windows, 50 bps costs, and no-backfill policy
- `research_registry/strategy_candidates.json` — current promising-but-not-final strategy tracker
- `research_registry/portfolio_candidates.json` — development-selected but non-final multi-strategy portfolio tracker
- `data/vintages/` — content-addressed, immutable market-data snapshots
- `data/derived/` — hashed weekly datasets derived from specific immutable snapshots
- `src/systematic_trader/` — platform-owned application code
- `tests/` — accounting, data, risk, simulation, and regression tests

Version 1.0 remains available in the neighboring `../1.0` folder.

The complete chronological record of both versions is maintained in
[`PROJECT_HISTORY.md`](PROJECT_HISTORY.md).
