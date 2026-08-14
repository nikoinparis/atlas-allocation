# Confidence sizing with universal stock caps v1

The cap applies identically to every fundamental stock. The stock that happens to grow beyond its limit is trimmed; there is no Micron-specific branch. Signals use prior gross returns and therefore remain identical across transaction-cost scenarios.

| variant | cap_name | window | cagr | sharpe_zero_rf | max_drawdown | peak_largest_stock_weight | annual_total_turnover | cagr_change_vs_control |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| confidence_10_40 | cap_1.00x | since_incumbent_holdout_start | 0.380041 | 1.466275 | -0.212057 | 0.137867 | 2.241330 | -0.035141 |
| confidence_10_40 | cap_1.00x | trailing_1y | 0.888482 | 2.401805 | -0.130641 | 0.137867 | 1.764500 | 0.078037 |
| confidence_10_40 | cap_1.00x | ytd | 0.850992 | 2.122183 | -0.130641 | 0.137867 | 1.718831 | 0.156746 |
| confidence_10_40 | cap_1.50x | since_incumbent_holdout_start | 0.387137 | 1.478351 | -0.212416 | 0.147835 | 2.079397 | -0.028045 |
| confidence_10_40 | cap_1.50x | trailing_1y | 0.923104 | 2.433138 | -0.134419 | 0.147835 | 1.423374 | 0.112660 |
| confidence_10_40 | cap_1.50x | ytd | 0.883113 | 2.146540 | -0.134419 | 0.147835 | 1.277282 | 0.188867 |
| confidence_10_40 | cap_2.00x | since_incumbent_holdout_start | 0.387881 | 1.479797 | -0.212416 | 0.155934 | 2.070294 | -0.027301 |
| confidence_10_40 | cap_2.00x | trailing_1y | 0.925688 | 2.435188 | -0.134937 | 0.155934 | 1.397245 | 0.115244 |
| confidence_10_40 | cap_2.00x | ytd | 0.887306 | 2.150475 | -0.134937 | 0.155934 | 1.234006 | 0.193060 |
| confidence_10_40 | uncapped | since_incumbent_holdout_start | 0.387881 | 1.479797 | -0.212416 | 0.155934 | 2.070294 | -0.027301 |
| confidence_10_40 | uncapped | trailing_1y | 0.925688 | 2.435188 | -0.134937 | 0.155934 | 1.397245 | 0.115244 |
| confidence_10_40 | uncapped | ytd | 0.887306 | 2.150475 | -0.134937 | 0.155934 | 1.234006 | 0.193060 |
| fixed_20 | cap_1.00x | since_incumbent_holdout_start | 0.415182 | 1.653436 | -0.189656 | 0.070635 | 0.877066 | 0.000000 |
| fixed_20 | cap_1.00x | trailing_1y | 0.810445 | 2.374671 | -0.123989 | 0.070635 | 0.819274 | 0.000000 |
| fixed_20 | cap_1.00x | ytd | 0.694246 | 1.953548 | -0.123989 | 0.070635 | 0.934352 | 0.000000 |
