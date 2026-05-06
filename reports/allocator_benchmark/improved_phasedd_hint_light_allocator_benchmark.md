# Allocator Benchmark Audit — improved_phasedd_hint_light

**Production:** `improved_phase2b_regime_confidence_boost`

**Sleeve panel:** 7 sleeves; 1109 weeks; 2005-01-14 → 2026-04-10.

**Allocators tested (internal implementations):**
- equal_weight, inverse_vol, ERC (iterative), max_diversification (lightweight), HRP (single-linkage + bisection), benchmark_tracker (52w Sharpe top-half).
- All run on the same 7-sleeve panel with the same 156w training window, monthly rebalance, 5bp half-spread cost, long-only, max sleeve weight 0.45.
- External libs (skfolio, riskfolio-lib, pypfopt, vectorbt) NOT installed; web egress to GitHub for repo inspection BLOCKED. No external code is copied.

## Allocator Comparison

```
                                          allocator  ann_return  ann_vol  sharpe  max_drawdown  cvar_5  calmar  avg_turnover  cost_drag_ann
                                       equal_weight      0.0545   0.0701  0.7769       -0.1373 -0.0230  0.3968        0.0009         0.0000
                                        inverse_vol      0.0472   0.0547  0.8631       -0.1167 -0.0178  0.4044        0.0043         0.0001
                                       erc_internal      0.0423   0.0478  0.8859       -0.1122 -0.0154  0.3774        0.0028         0.0000
                           max_diversification_lite      0.0417   0.0467  0.8929       -0.1121 -0.0150  0.3724        0.0026         0.0000
                                       hrp_internal      0.0419   0.0453  0.9251       -0.1086 -0.0145  0.3857        0.0062         0.0001
                             benchmark_tracker_lite      0.0512   0.0709  0.7217       -0.1630 -0.0238  0.3141        0.0009         0.0000
production:improved_phase2b_regime_confidence_boost      0.0689   0.0779  0.8848       -0.1398 -0.0262  0.4932        0.0562         0.0007
              candidate:improved_phasedd_hint_light      0.0604   0.0773  0.7815       -0.1442 -0.0267  0.4188        0.1127         0.0015
```

## Risk Contribution — improved_phasedd_hint_light

```
                      sleeve  avg_dollar_weight  avg_risk_contribution  risk_contribution_pct  risk_minus_dollar_weight_pct
composite_regime_conditioned             0.2512                 0.0000                 0.4102                        0.1591
                 taa_10m_sma             0.1321                 0.0000                 0.3200                        0.1879
          dual_momentum_topn             0.1060                 0.0000                 0.2698                        0.1638
```

**Hidden concentration flagged:**
- `composite_regime_conditioned`: dollar weight 25.1% but risk contribution 41.0% (delta +15.9pp).
- `taa_10m_sma`: dollar weight 13.2% but risk contribution 32.0% (delta +18.8pp).
- `dual_momentum_topn`: dollar weight 10.6% but risk contribution 27.0% (delta +16.4pp).

## Baseline Challenge

- Does the candidate beat **Equal Weight** on annualised return? **YES** (cand +6.04% vs Equal Weight +5.45%); on Sharpe? **YES** (cand 0.782 vs Equal Weight 0.777).
- Does the candidate beat **Inverse Vol** on annualised return? **YES** (cand +6.04% vs Inverse Vol +4.72%); on Sharpe? **NO** (cand 0.782 vs Inverse Vol 0.863).
- Does the candidate beat **ERC (internal)** on annualised return? **YES** (cand +6.04% vs ERC (internal) +4.23%); on Sharpe? **NO** (cand 0.782 vs ERC (internal) 0.886).
- Does the candidate beat **HRP (internal)** on annualised return? **YES** (cand +6.04% vs HRP (internal) +4.19%); on Sharpe? **NO** (cand 0.782 vs HRP (internal) 0.925).
- Does the candidate beat **Max Diversification (lite)** on annualised return? **YES** (cand +6.04% vs Max Diversification (lite) +4.17%); on Sharpe? **NO** (cand 0.782 vs Max Diversification (lite) 0.893).
- Does the candidate beat **production** on annualised return? **NO** (cand +6.04% vs prod +6.89%); on Sharpe? **NO**.

**Is the extra complexity justified?**

**NO / MARGINAL** — candidate Sharpe does not clearly exceed the best simple baseline by 0.05+. Extra complexity may not be earning its keep on Sharpe; consider whether the candidate's edge is on max drawdown, CVaR, or state-by-state defense rather than headline Sharpe.

## Promotion-readiness sign-off

Candidate does NOT beat production on annualised return OR does NOT clearly beat the best simple baseline on Sharpe. **Allocator-side bar NOT passed for production promotion.**

