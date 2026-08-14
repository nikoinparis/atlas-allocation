# Allocator Benchmark Audit — improved_phasepp_composite_combined_fallback_redesign

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
                                                   hrp_internal      0.0419   0.0453  0.9251       -0.1086 -0.0145  0.3857        0.0062         0.0001
            production:improved_phase2b_regime_confidence_boost      0.0689   0.0779  0.8848       -0.1398 -0.0262  0.4932        0.0562         0.0007
candidate:improved_phasepp_composite_combined_fallback_redesign      0.0697   0.0785  0.8879       -0.1401 -0.0264  0.4973        0.0576         0.0007
```

## Risk Contribution — improved_phasepp_composite_combined_fallback_redesign

```
                      sleeve  avg_dollar_weight  avg_risk_contribution  risk_contribution_pct  risk_minus_dollar_weight_pct
composite_regime_conditioned             0.2514                 0.0000                 0.4030                        0.1515
                 taa_10m_sma             0.1382                 0.0000                 0.3309                        0.1927
          dual_momentum_topn             0.1064                 0.0000                 0.2661                        0.1598
```

**Hidden concentration flagged:**
- `composite_regime_conditioned`: dollar weight 25.1% but risk contribution 40.3% (delta +15.2pp).
- `taa_10m_sma`: dollar weight 13.8% but risk contribution 33.1% (delta +19.3pp).
- `dual_momentum_topn`: dollar weight 10.6% but risk contribution 26.6% (delta +16.0pp).

## Baseline Challenge

- Does the candidate beat **Equal Weight** on annualised return? **YES** (cand +6.97% vs Equal Weight +5.45%); on Sharpe? **YES** (cand 0.888 vs Equal Weight 0.777).
- Does the candidate beat **Inverse Vol** on annualised return? **YES** (cand +6.97% vs Inverse Vol +4.72%); on Sharpe? **YES** (cand 0.888 vs Inverse Vol 0.863).
- Does the candidate beat **HRP (internal)** on annualised return? **YES** (cand +6.97% vs HRP (internal) +4.19%); on Sharpe? **NO** (cand 0.888 vs HRP (internal) 0.925).
- Does the candidate beat **production** on annualised return? **YES** (cand +6.97% vs prod +6.89%); on Sharpe? **YES**.

**Is the extra complexity justified?**

**NO / MARGINAL** — candidate Sharpe does not clearly exceed the best simple baseline by 0.05+. Extra complexity may not be earning its keep on Sharpe; consider whether the candidate's edge is on max drawdown, CVaR, or state-by-state defense rather than headline Sharpe.

## Promotion-readiness sign-off

Candidate does NOT beat production on annualised return OR does NOT clearly beat the best simple baseline on Sharpe. **Allocator-side bar NOT passed for production promotion.**

