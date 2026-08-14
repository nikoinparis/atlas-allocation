# Allocator Benchmark Audit — improved_phasefff_robust_composite_offense

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
candidate:improved_phasefff_robust_composite_offense      0.0706   0.0773  0.9144       -0.1208 -0.0259  0.5847        0.0615         0.0008
```

## Risk Contribution — improved_phasefff_robust_composite_offense

```
            sleeve  avg_dollar_weight  avg_risk_contribution  risk_contribution_pct  risk_minus_dollar_weight_pct
       taa_10m_sma             0.1105                 0.0000                 0.5577                        0.4472
dual_momentum_topn             0.0895                 0.0000                 0.4423                        0.3528
```

**Hidden concentration flagged:**
- `taa_10m_sma`: dollar weight 11.0% but risk contribution 55.8% (delta +44.7pp).
- `dual_momentum_topn`: dollar weight 8.9% but risk contribution 44.2% (delta +35.3pp).

## Baseline Challenge

- Does the candidate beat **Equal Weight** on annualised return? **YES** (cand +7.06% vs Equal Weight +5.45%); on Sharpe? **YES** (cand 0.914 vs Equal Weight 0.777).
- Does the candidate beat **Inverse Vol** on annualised return? **YES** (cand +7.06% vs Inverse Vol +4.72%); on Sharpe? **YES** (cand 0.914 vs Inverse Vol 0.863).
- Does the candidate beat **HRP (internal)** on annualised return? **YES** (cand +7.06% vs HRP (internal) +4.19%); on Sharpe? **NO** (cand 0.914 vs HRP (internal) 0.925).
- Does the candidate beat **production** on annualised return? **YES** (cand +7.06% vs prod +6.89%); on Sharpe? **YES**.

**Is the extra complexity justified?**

YES — candidate Sharpe exceeds the best simple baseline (Equal Weight / Inverse Vol) by more than 0.05.

## Promotion-readiness sign-off

Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. **Allocator-side bar passed.**

