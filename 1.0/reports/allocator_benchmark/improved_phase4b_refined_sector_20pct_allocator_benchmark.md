# Allocator Benchmark Audit — improved_phase4b_refined_sector_20pct

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
    candidate:improved_phase4b_refined_sector_20pct      0.0776   0.0809  0.9590       -0.1377 -0.0267  0.5635        0.0732         0.0010
```

## Risk Contribution — improved_phase4b_refined_sector_20pct

```
            sleeve  avg_dollar_weight  avg_risk_contribution  risk_contribution_pct  risk_minus_dollar_weight_pct
dual_momentum_topn             0.0920                 0.0000                 0.5333                        0.4413
       taa_10m_sma             0.0828                 0.0000                 0.4667                        0.3839
```

**Hidden concentration flagged:**
- `dual_momentum_topn`: dollar weight 9.2% but risk contribution 53.3% (delta +44.1pp).
- `taa_10m_sma`: dollar weight 8.3% but risk contribution 46.7% (delta +38.4pp).

## Baseline Challenge

- Does the candidate beat **Equal Weight** on annualised return? **YES** (cand +7.76% vs Equal Weight +5.45%); on Sharpe? **YES** (cand 0.959 vs Equal Weight 0.777).
- Does the candidate beat **Inverse Vol** on annualised return? **YES** (cand +7.76% vs Inverse Vol +4.72%); on Sharpe? **YES** (cand 0.959 vs Inverse Vol 0.863).
- Does the candidate beat **HRP (internal)** on annualised return? **YES** (cand +7.76% vs HRP (internal) +4.19%); on Sharpe? **YES** (cand 0.959 vs HRP (internal) 0.925).
- Does the candidate beat **production** on annualised return? **YES** (cand +7.76% vs prod +6.89%); on Sharpe? **YES**.

**Is the extra complexity justified?**

YES — candidate Sharpe exceeds the best simple baseline (Equal Weight / Inverse Vol) by more than 0.05.

## Promotion-readiness sign-off

Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. **Allocator-side bar passed.**

