# Robust Cross-Sectional ML — Batch 17

The isolated engine completed **2,924 model fits** across **15 embargoed outer folds**, three model families, five seeds, and four adversarial/staleness controls.

Real ML at 10 bps: **12.11%** annual return, **0.855** Sharpe, **-32.43%** maximum drawdown, and **8.35** annual turnover.

Fixed factor common-period Sharpe: **0.702**. Frozen winner common-period Sharpe: **0.848**.

ML maximum drawdown: **-32.43%** versus frozen winner **-23.39%**; safety gate passed: **False**.

Paired-bootstrap Sharpe advantage over the winner was statistically positive: **False**; lower Sharpe-difference bound **-0.303**.

Adjusted mean rank IC: **0.0696**; lower bound **0.0224**; gate passed: **True**.

Correlation to frozen winner: **0.723**. Positive outer-fold rank-IC share: **80.0%**. Negative controls passed: **True**.

Promotion: **False**. Failed gates remain explicit in `result.json`; no execution or live trading was enabled.
