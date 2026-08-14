# Macro Feature Regime Correlation Report

**No predictive claims** — averages by state and pre/post transition deltas only.

## Average feature value by ORIGINAL state

```
             state  n_weeks  hyg_lqd_credit_spread_proxy  uup_dollar_strength_4w  tlt_rate_sensitive_4w  gld_defensive_4w  spy_realized_vol_4w  spy_drawdown_from_52w_high  spy_minus_iei_3m  xlf_minus_xlu_3m  ig_credit_4w  hy_credit_4w  regime_recent_stress_26w  regime_avg_corr_risk_off_z  regime_transition_non_stress_prob  regime_market_drawdown  regime_breadth_sma_43
        calm_trend      295                       0.0115                  0.0008                 0.0024            0.0086               0.0810                     -0.0111            0.0561            0.0289        0.0056        0.0085                    0.1356                     -0.9287                             1.0000                 -0.0464                 0.8395
     neutral_mixed      492                       0.0065                  0.0020                 0.0003            0.0056               0.1068                     -0.0377            0.0301            0.0043        0.0011        0.0024                    0.3618                      0.3019                             0.9482                 -0.0483                 0.6193
recovery_confirmed       44                       0.0038                 -0.0020                 0.0010            0.0079               0.0997                     -0.0088            0.0680            0.0160        0.0098        0.0127                    1.0000                     -0.0161                             1.0000                 -0.0109                 0.8685
  recovery_fragile       49                       0.0119                 -0.0065                 0.0068            0.0132               0.1132                     -0.0784            0.0558            0.0182        0.0156        0.0207                    1.0000                      0.3082                             0.9109                 -0.0913                 0.7245
    stressed_panic      229                      -0.0215                  0.0024                 0.0055            0.0128               0.2198                     -0.1576           -0.0818           -0.0908       -0.0006       -0.0051                    0.9956                      0.5968                             0.1504                 -0.1525                 0.3185
```

## Average feature value by REFINED state (Phase CC)

Highlight: these are the rows that matter most for distinguishing `neutral_healthy` vs `neutral_deteriorating`.

```
                state  n_weeks  hyg_lqd_credit_spread_proxy  uup_dollar_strength_4w  tlt_rate_sensitive_4w  gld_defensive_4w  spy_realized_vol_4w  spy_drawdown_from_52w_high  spy_minus_iei_3m  xlf_minus_xlu_3m  ig_credit_4w  hy_credit_4w  regime_recent_stress_26w  regime_avg_corr_risk_off_z  regime_transition_non_stress_prob  regime_market_drawdown  regime_breadth_sma_43
           calm_trend      295                       0.0115                  0.0008                 0.0024            0.0086               0.0810                     -0.0111            0.0561            0.0289        0.0056        0.0085                    0.1356                     -0.9287                             1.0000                 -0.0464                 0.8395
neutral_deteriorating      171                       0.0051                  0.0039                 0.0030           -0.0089               0.1056                     -0.0482            0.0259            0.0066        0.0012        0.0004                    0.7018                      0.7289                             0.9365                 -0.0512                 0.5196
      neutral_healthy      210                       0.0071                  0.0010                -0.0012            0.0142               0.1149                     -0.0313            0.0375            0.0186        0.0025        0.0054                    0.1476                     -0.1507                             0.9407                 -0.0587                 0.7772
        neutral_mixed      111                       0.0168                 -0.0022                -0.0009            0.0118               0.0928                     -0.0307            0.0216           -0.0302       -0.0016       -0.0116                    0.2432                      0.5842                             0.9832                 -0.0243                 0.4743
   recovery_confirmed       44                       0.0038                 -0.0020                 0.0010            0.0079               0.0997                     -0.0088            0.0680            0.0160        0.0098        0.0127                    1.0000                     -0.0161                             1.0000                 -0.0109                 0.8685
     recovery_fragile       49                       0.0119                 -0.0065                 0.0068            0.0132               0.1132                     -0.0784            0.0558            0.0182        0.0156        0.0207                    1.0000                      0.3082                             0.9109                 -0.0913                 0.7245
       stressed_panic      229                      -0.0215                  0.0024                 0.0055            0.0128               0.2198                     -0.1576           -0.0818           -0.0908       -0.0006       -0.0051                    0.9956                      0.5968                             0.1504                 -0.1525                 0.3185
```

### Healthy vs Deteriorating (Phase CC) — feature delta

Positive `delta_d_minus_h` = feature is higher in deteriorating weeks. Note the sign expectations: credit spread proxies should be more negative in deteriorating; drawdown more negative in deteriorating; realized vol higher; risk-on - risk-off lower.

```
                          feature  healthy_mean  deteriorating_mean  delta_d_minus_h
      hyg_lqd_credit_spread_proxy       +0.0071             +0.0051          -0.0019
           uup_dollar_strength_4w       +0.0010             +0.0039          +0.0029
            tlt_rate_sensitive_4w       -0.0012             +0.0030          +0.0042
                 gld_defensive_4w       +0.0142             -0.0089          -0.0231
              spy_realized_vol_4w       +0.1149             +0.1056          -0.0093
       spy_drawdown_from_52w_high       -0.0313             -0.0482          -0.0169
                 spy_minus_iei_3m       +0.0375             +0.0259          -0.0116
                 xlf_minus_xlu_3m       +0.0186             +0.0066          -0.0119
                     ig_credit_4w       +0.0025             +0.0012          -0.0013
                     hy_credit_4w       +0.0054             +0.0004          -0.0049
         regime_recent_stress_26w       +0.1476             +0.7018          +0.5541
       regime_avg_corr_risk_off_z       -0.1507             +0.7289          +0.8796
regime_transition_non_stress_prob       +0.9407             +0.9365          -0.0042
           regime_market_drawdown       -0.0587             -0.0512          +0.0075
            regime_breadth_sma_43       +0.7772             +0.5196          -0.2576
```

## Pre/post stressed_panic transition window (event study)

Window: 4 weeks before vs 4 weeks after the first week of each stressed_panic transition.

```
                          feature  n_transitions  n_usable_events  mean_before_4w  mean_after_4w  delta_after_minus_before
      hyg_lqd_credit_spread_proxy             31               27         -0.0066        -0.0122                   -0.0056
           uup_dollar_strength_4w             31               27         +0.0040        +0.0041                   +0.0001
            tlt_rate_sensitive_4w             31               30         +0.0134        +0.0152                   +0.0018
                 gld_defensive_4w             31               30         +0.0124        +0.0025                   -0.0099
              spy_realized_vol_4w             31               30         +0.1197        +0.1753                   +0.0556
       spy_drawdown_from_52w_high             31               30         -0.0602        -0.0879                   -0.0278
                 spy_minus_iei_3m             31               30         +0.0008        -0.0338                   -0.0346
                 xlf_minus_xlu_3m             31               30         -0.0275        -0.0441                   -0.0166
                     ig_credit_4w             31               30         +0.0048        -0.0033                   -0.0080
                     hy_credit_4w             31               27         +0.0023        -0.0120                   -0.0143
         regime_recent_stress_26w             31               30         +0.7000        +0.9917                   +0.2917
       regime_avg_corr_risk_off_z             31               30         +0.0894        +0.2927                   +0.2033
regime_transition_non_stress_prob             31               29         +0.7972        +0.4537                   -0.3434
           regime_market_drawdown             31               30         -0.0622        -0.0895                   -0.0274
            regime_breadth_sma_43             31               30         +0.4994        +0.4095                   -0.0899
```

Interpretation guide: `delta_after_minus_before` should be **negative** for credit and risk-on - risk-off proxies and **positive** for realized vol and stress proxies.

