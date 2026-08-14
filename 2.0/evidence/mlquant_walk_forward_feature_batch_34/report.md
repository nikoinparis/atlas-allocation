# Walk-forward ML repository-feature ablation — Batch 34

Both engines used 3,252 identical asset-month rows and 15 embargoed outer folds.

| Model | Features | Mean rank IC | Return 10 bps | Sharpe 10 bps | Drawdown 10 bps | Sharpe 50 bps | Sharpe 100 bps |
|---|---:|---:|---:|---:|---:|---:|---:|
| matched_baseline | 11 | 0.0397 | 8.76% | 0.749 | -24.38% | 0.533 | 0.264 |
| mlquant_augmented | 13 | 0.0374 | 9.45% | 0.796 | -24.21% | 0.589 | 0.328 |

Paired 10-bps Sharpe lower difference: -0.073.
Historical gates passed: False. Promoted: False.

Live trading remains disabled.
