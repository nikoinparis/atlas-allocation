# Track B Benchmark Comparison

All benchmarks use existing weekly prices and Track A canonical metrics/cost logic.

| name | ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | avg_weekly_turnover | holdout_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_a_production | 0.07134169432 | 0.07523466355 | 0.9482556438 | -0.1160345789 | 0.6148313289 | -0.02494792886 | 0.2760603192 | 0.2949097764 | 0.2402307405 | 0.06738780266 | 2.178585179 |
| spy_buy_hold | 0.1053309083 | 0.175658379 | 0.5996349785 | -0.5461301945 | 0.1928677619 | -0.0580042681 | 0 | 1 | 1 | 0 | 1.219906078 |
| static_60_spy_40_ief | 0.0808715342 | 0.1030775479 | 0.7845698297 | -0.3138361945 | 0.2576870853 | -0.03273141716 | 0 | 0.6 | 0.569015337 | 0 | 1.484958316 |
| static_80_spy_20_bil | 0.08872865466 | 0.1404121812 | 0.6319156495 | -0.4584235979 | 0.1935516737 | -0.04633090118 | 0.2 | 0.8 | 0.799338497 | 0 | 1.296778084 |
| aggressive_taa_spy_trend | 0.09237202193 | 0.1253582216 | 0.7368644892 | -0.3624634652 | 0.2548450556 | -0.04069558701 | 0.1653153153 | 0.8346846847 | 0.6719788291 | 0.04147880974 | 1.542338 |
| dual_momentum_top1 | 0.05619201476 | 0.1825298972 | 0.3078510185 | -0.3964845068 | 0.1417256256 | -0.05786057138 | 0.05135135135 | 0.6027027027 | 0.3380573284 | 0.1992786294 | 1.070313971 |
| static_global_growth_90_10 | 0.1049740919 | 0.1639798182 | 0.6401647047 | -0.4987412313 | 0.2104780702 | -0.05380554386 | 0.05 | 0.9 | 0.9204453864 | 0 | 1.405214474 |

Machine-readable outputs:

- `data/research/track_b_aggressive/track_b_benchmark_returns.csv`
- `data/research/track_b_aggressive/track_b_benchmark_weights.csv`
- `data/research/track_b_aggressive/track_b_benchmark_metrics.csv`
