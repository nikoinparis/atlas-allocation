# Macro Regime Classifier: V1 vs V2 Comparison

**V1 verdict:** `RESEARCH-ONLY`
**V2 verdict:** `RESEARCH-ONLY`

## Key Differences

| Metric | V1 | V2 |
| --- | --- | --- |
| n_fred_series_used | 10 | 10 |
| dev_spread | 0.01408 | 0.02416 |
| nm_spread | 0.01225 | 0.03779 |
| holdout_rank_consistent | False | False |
| holdout_quads_populated | 2 | 3 |
| verdict | RESEARCH-ONLY | RESEARCH-ONLY |

## Full Comparison Table

| Metric | V1 | V2 |
| --- | --- | --- |
| n_fred_series_used | 10 | 10 |
| series_v1 | BAMLH0A0HYM2, NFCI, UMCSENT, FEDFUNDS, UNRATE, CPIAUCSL_yoy, INDPRO_yoy, PAYEMS_yoy, RSAFS_yoy, HOUST_yoy | BAMLH0A0HYM2, UMCSENT, FEDFUNDS, UNRATE, CPIAUCSL_yoy, INDPRO_yoy, PAYEMS_yoy, RSAFS_yoy, HOUST_yoy, ICSA |
| series_missing_v2 |  | T10Y2Y, NFCI, DGS3MO, DTWEXBGS |
| weekly_count_expansion | 180 | 287 |
| weekly_count_overheating | 276 | 264 |
| weekly_count_slowdown | 441 | 188 |
| weekly_count_stress | 212 | 370 |
| dev_mean_4w_expansion | 0.00227 | 0.00565 |
| dev_mean_4w_overheating | 0.00762 | 0.00965 |
| dev_mean_4w_slowdown | 0.01386 | -0.00907 |
| dev_mean_4w_stress | -0.00022 | 0.01509 |
| dev_spread | 0.01408 | 0.02416 |
| nm_spread | 0.01225 | 0.03779 |
| hold_mean_4w_expansion | nan | 0.0014 |
| hold_mean_4w_overheating | 0.00932 | 0.02238 |
| hold_mean_4w_slowdown | nan | 0.01189 |
| hold_mean_4w_stress | 0.01241 | nan |
| holdout_rank_consistent | False | False |
| holdout_quads_populated | 2 | 3 |
| verdict | RESEARCH-ONLY | RESEARCH-ONLY |

*Research artifact — no production code modified.*
