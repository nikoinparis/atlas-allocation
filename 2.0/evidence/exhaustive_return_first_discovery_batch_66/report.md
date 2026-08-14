# Batch 66 — exhaustive return-first discovery and validation

The frozen campaign evaluated **805** candidates built from **72** advanced causal sources, benchmark-aware blends, four regime rules, simple benchmark portfolios, two past-only selectors, and **8** nonlinear embargoed ML allocators. Determinism: **True**; prefix invariance: **True**; ML embargo: **True**.

The breadth ceiling returned **28.17%** and XLK returned **31.72%** after the frozen training cutoff. The unrestricted retrospective ceiling was `regime::broad_risk_on::rank_consensus__top1__score_invvol` at **52.35%**, but it is not eligible for promotion because the same holdout selected it.

Among **30** candidates fixed without using holdout outcomes, `ml::hist_gradient_boosting::sign` was best at **34.71%** CAGR, Sharpe **1.432**, and drawdown **-19.77%**. Qualified replacements: **0**. Selected replacement: `None`. Failed gates for the point leader: `rolling, multiplicity`.

Decision: `retain_current_strategy_and_save_unconfirmed_research_ceiling`. The existing 52-week forward protocol was not modified. No leverage, shorting, live trading, or paper-broker execution was enabled.
