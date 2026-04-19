Layered ETF quant research project.

Structure:
- Layer 1 = alpha signals
- Layer 2 = strategy logic / sleeves
- Layer 2B = causal regime engine
- Layer 3 = portfolio construction
- Dashboard = research explainer + comparison + diagnostics

Goals:
- robust, interpretable, out-of-sample ETF portfolio
- avoid overfitting and brute-force search
- improve return without carelessly worsening Sharpe, drawdown, CVaR, or turnover

Rules:
- prefer simple causal logic over black-box ML
- no hindsight regime labels
- test incremental contribution, not just standalone signal quality
- keep only changes that help out of sample alone or in combination
- prioritize state-transition quality, re-risking speed, and reducing unnecessary BIL/cash drag

Current production candidate (official):
- improved_phase2b_regime_confidence_boost

Current research runner-up (shadow / alternate baseline):
- improved_phase2b_combo_abc

Dual-track rule:
- `improved_phase2b_regime_confidence_boost` is the single production default in the dashboard, narratives, and reports.
- `improved_phase2b_combo_abc` is kept alive as a tracked research runner-up. It appears in the dashboard as an alternate comparison only, never as the headline production candidate.
- Future Phase 3 sprints should report incremental contribution versus BOTH tracks separately (production + shadow) before promoting anything new.

Dashboard:
- homepage must be inspectable immediately on first load
- no key content hidden behind tabs/accordions/loading states
- visible summaries for baseline vs improved, current state, allocations, layers 1-3, diagnostics, benchmarks, holdings, and sleeve mix

For every task, report:
- what was executed
- which files/artifacts changed
- whether the change helped standalone
- whether it helped in combination
- final classification: Promote / Conditional / Research-only / Drop