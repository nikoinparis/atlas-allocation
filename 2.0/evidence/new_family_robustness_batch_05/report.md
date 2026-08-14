# New-Family Robustness — Batch 05

The three Batch 04 family leaders were tested across parameter neighborhoods, costs through 100 bps, causal market regimes, and a 50,000-sample correction for all 576 strategies searched so far.

- Provisionally robust: **1**.
- Provisionally fragile: **2**.

## Candidate decisions

- **carry_proxy** `candidate-3aa6e07c0cd53e52`: **fragile** (neighborhood pass, 100 bps pass, regime pass, multiple testing fail).
- **defensive** `candidate-8a27cb8ba5a612a7`: **robust** (neighborhood pass, 100 bps pass, regime pass, multiple testing pass).
- **mean_reversion** `candidate-81ffdbdf4dcdab3c`: **fragile** (neighborhood pass, 100 bps fail, regime pass, multiple testing fail).

## Robust-family ensemble diagnostics

- **trend_v4**: annual return **9.91%**, Sharpe **0.754**, drawdown **-26.25%**, annual turnover **1.93**.
- **trend_plus_robust_defensive**: annual return **8.64%**, Sharpe **0.860**, drawdown **-24.29%**, annual turnover **2.45**.
- **equal_robust_multi_family_research**: annual return **8.64%**, Sharpe **0.860**, drawdown **-24.29%**, annual turnover **2.45**.

Carry cannot advance beyond research-only status from the current Yahoo action history, regardless of its statistical result. All ensemble numbers remain retrospective diagnostics.
