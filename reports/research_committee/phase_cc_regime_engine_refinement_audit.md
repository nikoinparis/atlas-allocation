# Research Committee Audit — phase_cc_regime_engine_refinement

**Production baseline:** `improved_phase2b_regime_confidence_boost`

**Candidate kind:** state-engine refinement (Layer 2B)

**Closest portfolio surrogate audited in parallel:** `improved_phasez_production_hrp_7sleeve`

## Executive Verdict

**KEEP AS SHADOW-IN-WAITING for downstream consumption.**

Phase CC produces an upstream regime-engine refinement, not a portfolio. The refined state file is causally clean and statistically meaningful (forward 4w panic-transition probability is 3.6× higher in `neutral_deteriorating` than `neutral_healthy`). It does not change any production behaviour by itself. Recommend a downstream Phase DD that consumes the new `defensive_overlay_hint` as an additive sleeve-level tilt inside the Phase Z architecture, then judge that downstream candidate under the full 8-gate production rule.

## What Changed

- New artifact `data/04_layer2b_risk_regime_engine/market_state_history_refined.csv` adds:
  - `refined_state` (splits `neutral_mixed` into `neutral_healthy` / `neutral_deteriorating`),
  - `deterioration_z` (equal-weight composite of 5 z-scored causal features),
  - `deterioration_rank_neutral_mixed` (walk-forward percentile rank),
  - `confidence_score_p2b` (secondary, post-2008-11),
  - `defensive_overlay_hint` ∈ {-1, 0, +1} for downstream allocator consumption.
- The original `market_state_history.csv` is **untouched**.
- For portfolio-level audit purposes, the closest existing portfolio relative is `improved_phasez_production_hrp_7sleeve` (Phase Z HRP on the 7-sleeve panel). All portfolio-level metrics below describe that surrogate, NOT Phase CC itself.

## Phase CC — State-Engine Refinement Summary
**State counts (original vs refined)**

```
                state  original_count  refined_count
           calm_trend             295            295
       stressed_panic             229            229
      neutral_healthy               0            210
neutral_deteriorating               0            171
        neutral_mixed             493            112
     recovery_fragile              49             49
   recovery_confirmed              44             44
```

**Neutral_mixed split summary**

```
        refined_label  n_weeks  frac_of_neutral_mixed  deterioration_z_mean  deterioration_z_median  rank_mean
      neutral_healthy      210               0.425963             -0.517539               -0.510570   0.230012
        neutral_mixed      112               0.227181              0.099655               -0.053689        NaN
neutral_deteriorating      171               0.346856              0.264296                0.207830   0.760631
```

**Forward-window diagnostics by refined state** (the score does not see these)

```
        refined_state  n_weeks  fwd4_spy_mean  fwd4_spy_median  fwd4_spy_hit_rate  fwd13_spy_mean  fwd4_realized_vol  fwd4_to_panic_prob  fwd4_w1_mean  fwd4_w1_minus_spy
           calm_trend      295       0.005948         0.015114           0.691525        0.023783           0.013066            0.023729      0.000962          -0.004986
neutral_deteriorating      171       0.009115         0.010566           0.619883        0.016852           0.016889            0.278107      0.001931          -0.007185
      neutral_healthy      210       0.012596         0.015916           0.704762        0.036807           0.014580            0.076190      0.002015          -0.010581
        neutral_mixed      112       0.003398         0.011762           0.625000        0.013576           0.012368            0.169643      0.001454          -0.001842
   recovery_confirmed       44       0.008753         0.018835           0.659091        0.042093           0.015709            0.000000      0.002758          -0.005994
     recovery_fragile       49       0.014639         0.019987           0.775510        0.039233           0.013475            0.102041     -0.001203          -0.015842
       stressed_panic      229       0.003982         0.013020           0.558952        0.019174           0.028152            0.929825      0.003019          -0.000963
```

**Transition matrix (rows=original, cols=refined)**

```
                    calm_trend  neutral_deteriorating  neutral_healthy  neutral_mixed  recovery_confirmed  recovery_fragile  stressed_panic
original                                                                                                                                   
calm_trend                 295                      0                0              0                   0                 0               0
neutral_mixed                0                    171              210            112                   0                 0               0
recovery_confirmed           0                      0                0              0                  44                 0               0
recovery_fragile             0                      0                0              0                   0                49               0
stressed_panic               0                      0                0              0                   0                 0             229
```

**Causal-safety guarantees**

- All primary features are computed by the regime engine from 1-week-lagged inputs.
- trailing_z lags by one week (t excluded from its own moving window).
- walk_forward_percentile_rank uses only past values (s < t).
- Forward-window diagnostics enter NO score; they only validate.

## Headline Metric Comparison (portfolio level)

Compared on `2005-01-14` → `2026-04-10` (1109 weeks).

```
      metric  improved_phasez_production_hrp_7sleeve (full)  improved_phase2b_regime_confidence_boost (full)  delta_full  improved_phasez_production_hrp_7sleeve (holdout)  improved_phase2b_regime_confidence_boost (holdout)  delta_holdout
  ann_return                                         0.0424                                           0.0690     -0.0265                                            0.0891                                              0.1243        -0.0353
     ann_vol                                         0.0455                                           0.0779     -0.0324                                            0.0467                                              0.0765        -0.0298
      sharpe                                         0.9330                                           0.8852      0.0478                                            1.9059                                              1.6249         0.2810
max_drawdown                                        -0.0857                                          -0.1398      0.0541                                           -0.0372                                             -0.0626         0.0254
      cvar_5                                        -0.0151                                          -0.0262      0.0110                                           -0.0121                                             -0.0210         0.0089
      calmar                                         0.4954                                           0.4936      0.0017                                            2.3939                                              1.9850         0.4089
```

## Bull Case

- Full-window Sharpe **0.933** vs production **0.885** (Δ +0.048).
- Holdout (last 156w) Sharpe **1.906** vs production **1.625** (Δ +0.281).
- Full-window max drawdown **-8.57%** vs production **-13.98%** — shallower drawdown.
- Full-window CVaR-5% **-1.51%** vs production **-2.62%** — better tail.

**Phase CC-specific bull points:**
- Forward 4w probability of transition into `stressed_panic`: 27.8% in `neutral_deteriorating` vs 7.6% in `neutral_healthy` — 3.6× ratio.
- Forward 13w SPY mean: 3.7% in `neutral_healthy` vs 1.7% in `neutral_deteriorating` — >200bp annualized gap.
- Causal walk-forward construction: trailing 156w z-window lagged by 1w; rank uses only past `neutral_mixed` weeks.
- Strictly additive: original state file unchanged.

## Bear Case

- Full-window annualised return **4.24%** vs production **6.90%** — surrogate gives up **2.65pp** of return.
- Holdout annualised return **8.91%** vs production **12.43%** — surrogate gives up **3.53pp** of return.

**Phase CC-specific bear points:**
- The refinement is unused by any current production code path — its value is hypothesised, not measured.
- 112 of 493 original `neutral_mixed` weeks (2005-01 → 2008-07) fall back to the unrefined label due to insufficient z-window history.
- The forward W1 absolute-return advantage is modest (+0.01%/wk); the case rests on forward stress-probability, not direct W1 lift.
- Phase DD must still pass the 8-gate Phase D rule before any pin status change.

## Risk Manager Check

- max drawdown delta vs production: +5.41pp (PASS; cap ≥ -1.0pp)
- CVaR-5% delta vs production: +1.10pp (PASS; cap ≥ -0.20pp)
- holdout raw return delta vs production: -3.53pp
- holdout sharpe delta vs production: +0.281 (PASS; cap ≥ -0.02)
- avg weekly L1 turnover (cand vs prod): 0.1126 vs 0.1124
- avg BIL/cash exposure (cand vs prod): 51.64% vs 28.39%
- avg SPY exposure (cand vs prod): 4.90% vs 7.08%
- max single-ETF weight observed (cand vs prod): 100.00% vs 100.00%

**Blocking flags TRUE: 0**

## State-by-State Impact

**Original state buckets** (production engine):

```
             state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
     neutral_mixed      492          0.0012          0.0021          -0.0009         0.0058         0.0105
        calm_trend      295          0.0006          0.0008          -0.0001         0.0073         0.0128
    stressed_panic      229          0.0004          0.0007          -0.0003         0.0060         0.0094
  recovery_fragile       49          0.0007          0.0013          -0.0007         0.0051         0.0073
recovery_confirmed       44          0.0002          0.0005          -0.0004         0.0065         0.0093
```

**Refined state buckets** (Phase CC engine — surrogate portfolio reweighted by refined label):

```
                state  n_weeks  cand_mean_wkly  base_mean_wkly  delta_mean_wkly  cand_vol_wkly  base_vol_wkly
           calm_trend      295          0.0006          0.0008          -0.0001         0.0073         0.0128
       stressed_panic      229          0.0004          0.0007          -0.0003         0.0060         0.0094
      neutral_healthy      210          0.0018          0.0031          -0.0014         0.0066         0.0120
neutral_deteriorating      171          0.0010          0.0017          -0.0008         0.0059         0.0103
        neutral_mixed      111          0.0005          0.0006          -0.0001         0.0037         0.0067
     recovery_fragile       49          0.0007          0.0013          -0.0007         0.0051         0.0073
   recovery_confirmed       44          0.0002          0.0005          -0.0004         0.0065         0.0093
```

## Implementation Audit

- Candidate kind: state_engine
- Same date range: PASS (2005-01-14 → 2026-04-10, 1109 weeks)
- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)
- Net returns used: PASS
- Holdout window definition: PASS (last 156 weeks)
- Original `market_state_history.csv` preserved alongside refined file: PASS
- `defensive_overlay_hint` saved as additive column (not a hard categorical replacement): PASS

## Backtest Realism Summary (Layer 5 hand-off)

_Layer 5 realism report not yet produced for `improved_phasez_production_hrp_7sleeve`._

## Allocator Benchmark Summary (Layer 6 hand-off)

_Layer 6 allocator benchmark not yet produced for `improved_phasez_production_hrp_7sleeve`._

## Final Recommendation

**Verdict: KEEP AS SHADOW-IN-WAITING.**

- Phase CC delivers a clean, causally-safe, interpretable refined regime engine.
- It is *not* a portfolio strategy and therefore cannot itself satisfy the Phase D 8-gate production rule.
- Recommend Phase DD: a narrow production-family rerun that consumes `defensive_overlay_hint` as an additive sleeve-level tilt inside the Phase Z HRP architecture, validated against the same 13-member fixed comparator set augmented with Z1, AA1/AA2/AA3, BB1/BB2/BB3.
- Production pin: unchanged. Shadow pin: unchanged.

