# Pre-Frontier Validation Hardening Summary

Research-only sprint. No production pins, dashboard/public files, production artifacts, live trading logic, or frontier strategy logic were changed.

## Commands Run

```bash
.venv/bin/python -m py_compile scripts/statistical_validation_layer.py scripts/run_statistical_validation_audit.py scripts/build_research_scoreboard.py
.venv/bin/python scripts/run_statistical_validation_audit.py
.venv/bin/python scripts/build_research_scoreboard.py
git status --short
git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv
shasum docs/research/frontier_deployment_intelligence_*.md
```

## Files Created

- `scripts/statistical_validation_layer.py`
- `scripts/run_statistical_validation_audit.py`
- `scripts/build_research_scoreboard.py`
- `docs/research/statistical_validation_layer.md`
- `data/research/validation/statistical_validation_audit.csv`
- `docs/research/statistical_validation_audit_report.md`
- `docs/research/frontier_validation_governance.md`
- `data/research/research_scoreboard.csv`
- `docs/research/research_scoreboard.md`
- `docs/research/pre_frontier_validation_hardening_summary.md`

## Validation Utilities Added

- Probabilistic Sharpe Ratio with skew/kurtosis adjustment.
- Deflated Sharpe Ratio proxy with trial-count adjustment.
- Multiple-testing adjusted support score.
- PBO-style proxy using in-sample winner versus out-of-sample median checks.
- Purged and embargoed CV split generator.
- Rolling-origin validation split generator.
- Standard strategy validation summary with return, volatility, Sharpe, drawdown, Calmar, CVaR, skew, kurtosis, PSR, DSR proxy, drawdown pain score, and turnover warning.

## Governance Rules Added

`docs/research/frontier_validation_governance.md` defines:

- Candidate classifications: Promote, Keep as Shadow, Research-only, Diagnostic-only, Drop.
- Required promotion evidence.
- Frontier-specific gates.
- Research hygiene requirements.
- Lopez de Prado leakage and overfitting checklist.
- Stop and pivot rules.

## Research Scoreboard

The scoreboard contains 13 curated starter rows covering:

- Phase 2B production / combo_abc.
- GGG / Phaseggg confirmed robust offense.
- R1-R4 Renaissance signal discovery.
- Dollar strength.
- Breadth / macro sprint.
- B6/B7/B8.
- Path 1/3 and native confidence insertion.
- Stabilization sprint.
- W1 / structural defense memory row.
- Q-V / trust / ML allocator branch.
- ML lab frontier branch.
- Pre-frontier validation layer.

## Known Limitations

- DSR is approximate because the true dependence structure across all tried variants is not fully known.
- PBO is a proxy, not full CPCV.
- The audit scans available saved returns and metrics files; it cannot recover unlogged experiments.
- Some CSVs produced mixed-type dtype warnings during scanning, but the audit completed and wrote output.
- The scoreboard is a manually curated starter set, not a perfect automatic parser of all dated reports.

## Future Frontier Usage

- Every frontier sprint should use the exact stabilized GGG wrapper baseline.
- Every frontier sprint should count all tried variants as trials.
- Any overlapping-label validation should use purging and embargo.
- Sprint summaries should report PSR, DSR proxy, PBO proxy, state behavior, turnover/cost impact, and hidden beta/cash checks.
- Scoreboard rows should be appended or regenerated when a research branch is closed.

## Confirmations

- Production/dashboard protected paths were not intentionally modified.
- `docs/research/frontier_deployment_intelligence_*.md` files were not edited by this sprint.
