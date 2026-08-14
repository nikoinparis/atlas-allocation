# Stabilization Checkpoint Wrapper Test Report

- No-modifier wrapper reproduces exact GGG: `True`.
- This test is required before any future deployment rule harness can be trusted.

## Rebuild Metrics

| variant | ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_turnover | cost_drag | avg_BIL | avg_SPY | avg_offense | avg_defense |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_modifier_wrapper_rebuild | 0.0714 | 0.0762 | 0.9366 | -0.1177 | 0.6063 | -0.0254 | 0.0618 | 0.0686 | 0.2666 | 0.0603 | 0.4162 | 0.5447 |

## Match Against Saved GGG

| net_return_corr_vs_saved | gross_return_max_abs_error | net_return_max_abs_error | turnover_max_abs_error | cost_max_abs_error | weeks_compared |
| --- | --- | --- | --- | --- | --- |
| 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1110.0000 |

## Warnings

- None.
