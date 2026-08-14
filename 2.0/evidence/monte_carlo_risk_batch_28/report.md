# Frozen Portfolio Monte Carlo Risk — Batch 28

This batch uses the repository's Gaussian Monte Carlo and best-fit path as diagnostics, then adds empirical and serial block models for risk estimation. No simulated path changes the portfolio or creates an alpha signal.

Historical reconstruction: **6.58%** annual return, **0.769** Sharpe, and **-23.50%** drawdown across **1126** weeks.

Five-year 13-week block model: **3.5%** probability of ending below starting wealth, **1.6%** probability of a 30% drawdown, and **3.1%** fifth-percentile terminal return.

Five-year positive-mean haircut: **18.8%** probability of ending below starting wealth and **-13.4%** fifth-percentile terminal return.

Forced worst historical 13-week block (2019-12-27 to 2020-03-20, **-21.2%**): **75.9%** recovered starting wealth within five years; **33.8%** ended below it.

Rolling past-only 90% calibration coverage: terminal return **87.5%**, maximum drawdown **75.0%**, across **16** annual origins.

Predeclared risk-validation gate: **PASS**. Source best-fit forecasting edge: **False**. Portfolio promotion/live approval: **False/False**.
