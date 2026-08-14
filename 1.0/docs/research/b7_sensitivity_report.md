# B7 Sensitivity Report

Research-only small-grid sensitivity. This is a stability check, not parameter optimization.

- Sensitivity CSV: `data/research/b7_pass_through/b7_sensitivity_results.csv`

## Top Sensitivity Rows

| variant | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | holdout_2020_sharpe |
| --- | --- | --- | --- | --- | --- |
| sens_dollar_blended_medium | 0.0586 | 0.7724 | -0.1264 | -0.0260 | 0.9243 |
| sens_dollar_blended_mild | 0.0587 | 0.7712 | -0.1270 | -0.0261 | 0.9235 |
| sens_dollar_4w_medium | 0.0584 | 0.7698 | -0.1264 | -0.0260 | 0.9252 |
| sens_dollar_4w_mild | 0.0586 | 0.7695 | -0.1270 | -0.0261 | 0.9242 |
| sens_macro_mild | 0.0570 | 0.7692 | -0.1173 | -0.0254 | 0.9524 |
| sens_macro_medium | 0.0561 | 0.7683 | -0.1124 | -0.0251 | 0.9675 |
| sens_breadth_scaler_max1.05_floor0.85 | 0.0589 | 0.7675 | -0.1266 | -0.0264 | 0.9171 |
| sens_breadth_scaler_max1.05_floor0.90 | 0.0589 | 0.7675 | -0.1266 | -0.0264 | 0.9171 |
| sens_breadth_scaler_max1.05_floor0.95 | 0.0589 | 0.7675 | -0.1266 | -0.0264 | 0.9171 |
| sens_breadth_scaler_max1.10_floor0.85 | 0.0590 | 0.7658 | -0.1250 | -0.0265 | 0.9122 |
| sens_breadth_scaler_max1.10_floor0.90 | 0.0590 | 0.7658 | -0.1250 | -0.0265 | 0.9122 |
| sens_breadth_scaler_max1.15_floor0.85 | 0.0590 | 0.7642 | -0.1233 | -0.0266 | 0.9075 |
| sens_breadth_scaler_max1.10_floor0.95 | 0.0590 | 0.7640 | -0.1267 | -0.0265 | 0.9085 |
| sens_breadth_scaler_max1.15_floor0.90 | 0.0591 | 0.7635 | -0.1241 | -0.0266 | 0.9065 |
| sens_breadth_scaler_max1.15_floor0.95 | 0.0591 | 0.7602 | -0.1276 | -0.0267 | 0.8983 |

## Stability Read

- If results move materially across mild settings, the pass-through idea is fragile.
- No sensitivity row is a promotion candidate.
