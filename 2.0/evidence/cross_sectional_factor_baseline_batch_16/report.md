# Cross-Sectional Factor Baseline — Batch 16

The causal panel contains **8,324 asset-month rows** across **247 monthly decisions**. All features stop one completed week before their decision; timing violations: **0**.

At 10 bps the fixed, non-ML ranker produced **8.52%** annual return, **0.689** Sharpe, and **-24.42%** maximum drawdown.

Mean monthly rank IC was **0.0309**; its one-sided serial-block-bootstrap lower bound was **-0.0088**. Rank-IC gate passed: **False**.

Both later windows remained profitable at 100 bps: **True**.

Correlation to the frozen winner was **0.817** over **1074** common weeks.

This is now the mandatory common baseline for cross-sectional ML. It is not promoted because the universe is survivorship-prone, the data are a current free vintage, and no untouched forward clock exists.
