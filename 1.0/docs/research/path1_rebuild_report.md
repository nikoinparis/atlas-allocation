# Path 1 Rebuild Report

Research-only exact GGG reference rebuild attempt.

## Result

- Exact reconstruction success: `True`
- The exact reconstruction uses saved final ETF weights plus `weekly_prices.pct_change().shift(-1)`, one-way turnover, and 10 bps cost.

## Best Rebuild

| rebuild_name | rebuild_ann_return | rebuild_sharpe | rebuild_max_drawdown | rebuild_cvar_5 | net_return_corr_vs_saved | net_return_max_abs_error |
| --- | --- | --- | --- | --- | --- | --- |
| exact_saved_final_etf_weights | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 1.0000 | 0.0000 |

## B7/B8 Sandbox Baseline Mismatch

| rebuild_name | rebuild_ann_return | rebuild_sharpe | net_return_corr_vs_saved | net_return_max_abs_error | turnover_mean_abs_error | cost_mean_abs_error |
| --- | --- | --- | --- | --- | --- | --- |
| b7_b8_sandbox_plumbing | 0.0588 | 0.7683 | -0.1035 | 0.1252 | 0.0618 | 0.0001 |

## Largest Divergence Weeks For B7/B8-Style Plumbing

| Date | net_return | net_return_saved | net_error | gross_return | gross_return_saved | turnover | turnover_saved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2020-03-20 00:00:00 | -0.0550 | 0.0701 | -0.1252 | -0.0550 | 0.0702 | 0.0164 | 0.0082 |
| 2020-03-06 00:00:00 | 0.0243 | -0.0683 | 0.0926 | 0.0244 | -0.0683 | 0.0241 | 0.0121 |
| 2020-03-27 00:00:00 | 0.0659 | -0.0041 | 0.0699 | 0.0667 | -0.0036 | 0.8520 | 0.4260 |
| 2018-02-09 00:00:00 | -0.0366 | 0.0300 | -0.0666 | -0.0365 | 0.0300 | 0.0310 | 0.0155 |
| 2010-05-14 00:00:00 | 0.0253 | -0.0406 | 0.0659 | 0.0253 | -0.0406 | 0.0130 | 0.0065 |
| 2010-05-07 00:00:00 | -0.0398 | 0.0257 | -0.0654 | -0.0397 | 0.0257 | 0.0346 | 0.0173 |
| 2020-10-30 00:00:00 | -0.0239 | 0.0404 | -0.0643 | -0.0236 | 0.0405 | 0.3202 | 0.1601 |
| 2010-05-21 00:00:00 | -0.0417 | 0.0166 | -0.0582 | -0.0416 | 0.0166 | 0.0236 | 0.0118 |
| 2022-03-04 00:00:00 | 0.0342 | -0.0202 | 0.0544 | 0.0342 | -0.0202 | 0.0299 | 0.0150 |
| 2020-02-28 00:00:00 | -0.0294 | 0.0245 | -0.0540 | -0.0282 | 0.0251 | 1.2392 | 0.6196 |
| 2011-08-05 00:00:00 | -0.0342 | 0.0178 | -0.0521 | -0.0342 | 0.0179 | 0.0572 | 0.0286 |
| 2007-03-02 00:00:00 | -0.0391 | 0.0115 | -0.0506 | -0.0390 | 0.0116 | 0.0593 | 0.0296 |

## Interpretation

- Exact GGG can be reconstructed accurately from saved final ETF weights and the correct return/cost convention.
- A full first-principles rebuild of HRP/raw sleeve decisions was not run because `build_improvement_artifacts.py` writes production Layer 3 files as a side effect.
- The available allocator checkpoints are sufficient to isolate the mismatch without overwriting production artifacts.

## Warnings

- None.
