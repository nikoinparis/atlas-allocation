# Frontier Phase 4A: Cross-Sectional Leadership Signals Report

**Date:** 2026-05-21
**Mode:** Diagnostic-only — no production or dashboard files modified

---

## 1. Sprint Summary

Phase 4A builds five causal 1-week-lagged leadership quality signals and a composite. Validates via time-series Spearman IC against SPY 4-week forward return.  Reports partial IC after controlling for Phase 1 R2A and Phase 2 average trend quality.

---

## 2. Commands Run

```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier4_leadership_signals.py
```

---

## 3. Source Paths and Ticker Notes

| resource | path |
|----------|------|
| Weekly prices | `data/01_data_hub/weekly_prices.csv` |
| Market state | `data/04_layer2b_risk_regime_engine/market_state_history.csv` |
| Phase 1 R2A | `data/research/frontier_phase1/state_quality_signals_r2.csv` |
| Phase 2 TQ | `data/research/frontier_phase2/trend_quality_panel.csv` |

**QUAL not in universe → VUG used as quality/growth substitute.**
Quality/growth ETFs used: ['QQQ', 'XLK', 'VUG']  (QUAL missing)
Speculative/risk ETFs: ['HYG', 'IWM', 'VWO']
Offensive ETFs: ['SPY', 'QQQ', 'XLK', 'XLY', 'XLI', 'XLF', 'XLE', 'IWM', 'VWO', 'EFA']
Date range: 2005-01-07 → 2026-04-10  (1110 rows)

---

## 4. Signal Definitions

All signals are computed unlagged and shifted forward 1 week.
| signal | definition | weight in composite |
|--------|------------|---------------------|
| `leadership_breadth` | Fraction of offensive ETFs with 13w mom in top-half of all 35 ETFs | +0.30 |
| `leadership_concentration` | HHI of 13w momentum rank shares among offensive ETFs | −0.20 |
| `leadership_type_quality` | Mean pct-rank(QQQ/XLK/VUG) − Mean pct-rank(HYG/IWM/VWO) in 13w mom | +0.25 |
| `leadership_rotation_persistence` | Spearman corr of offensive ETF 13w mom ranks vs 4 weeks prior | +0.15 |
| `credit_equity_alignment` | +1 if HYG 4w and SPY 4w both positive; −1 if they diverge; 0 otherwise | +0.10 |
| `leadership_quality_composite` | Weighted sum of z-scored components, re-z-scored, clipped ±3 | — |

---

## 5. IC Results

### Full / Dev / Holdout

| window | IC | n |
|--------|----|----|
| full | -0.0894 | ~1100 |
| dev | -0.0989 | ~1007 |
| holdout | 0.0472 | ~103 |

### By Market State (full period)

| market_state | IC | n |
|-------------|----|---|
| calm_trend | -0.0644 | 295 |
| neutral_mixed | -0.1642 | 491 |
| recovery_confirmed | -0.2614 | 43 |
| recovery_fragile | -0.0796 | 49 |
| stressed_panic | 0.0353 | 228 |

---

## 6. Component ICs (full period)

| component | full_IC |
|-----------|---------|
| leadership_breadth | -0.0505 |
| leadership_concentration | -0.0123 |
| leadership_type_quality | -0.0810 |
| leadership_rotation_persistence | 0.0271 |
| credit_equity_alignment | -0.0138 |
| leadership_quality_composite | – |

---

## 7. Partial IC (after controlling for Phase 1 R2A and Phase 2 avg trend_quality)

| scope | raw_IC | partial_IC |
|-------|--------|------------|
| full | -0.0894 | -0.0171 |
| dev | -0.0989 | -0.0261 |
| holdout | 0.0472 | 0.1090 |

- Spearman corr(leadership_composite, Phase1_R2A): -0.4455
- Spearman corr(leadership_composite, Phase2_avgTQ): 0.3736

---

## 8. Quintile Returns (full history)

| quintile | mean_4w_SPY_forward | n |
|----------|--------------------|----|
| Q1 | 0.0095 | 222 |
| Q2 | 0.0097 | 221 |
| Q3 | 0.0123 | 221 |
| Q4 | 0.0092 | 221 |
| Q5 | 0.0027 | 221 |

---

## 9. Acceptance Gate Results

**✗ FAIL**

- ✓ Holdout IC not broken: +0.0472
- ✓ Not duplicate of Phase1/2: corr_r2a=-0.445, corr_tq=+0.374
- ✗ Full IC not positive / too small: -0.0894
- ✗ Partial IC not positive: -0.0171
- ✗ IC not positive in calm_trend (-0.0644) or neutral_mixed (-0.1642)

---

## 10. Structural Diagnosis — Why the IC is Negative

The composite has consistently negative IC in every non-stressed state. This is not random noise — it is a real and interpretable signal with **inverted polarity** relative to the intended use.

**Economic interpretation:** The signals as constructed capture late-cycle / crowded-market dynamics:
- **High breadth** (offensive ETFs broadly in top-half momentum) → market is already broadly extended → mean reversion ahead
- **Quality/growth leading** (QQQ/XLK/VUG outranking HYG/IWM/VWO) → late-cycle growth premium already priced in → lower future returns
- **Persistent leadership** → mature trend → limited remaining upside before rotation

This is the same sign issue identified in Phase 1A: signals that indicate a "mature, broadly confirmed, good-looking" market are actually NEGATIVE predictors of near-term returns. Phase 1A's breadth_quality_score had IC −0.107 in calm_trend for exactly the same reason.

**The one positive component:** `leadership_rotation_persistence` has IC +0.027 (higher stability of leaders → slightly better returns), which is the exception. All other components pull in the wrong direction for a "deploy more" signal.

**Holdout asymmetry:** Full IC = −0.089, holdout IC = +0.047. This suggests the relationship between leadership quality and forward returns may have shifted in the recent regime (2024–2026 bull market). The partial holdout IC is +0.109 after controlling for Phase 1/2, which is notable. But 103 holdout observations is too few to trust.

**Quintile pattern:** Q3 has the highest return (0.0123), Q5 the lowest (0.0027). The pattern is not monotone but confirms that high-composite weeks (Q5) are the worst return environment.

**Potential salvage path:** The composite could be used with INVERTED polarity as a "fragility score":
- Low composite = fresh/fragile/early-cycle leadership → deploy with confidence
- High composite = crowded/late-cycle leadership → caution, reduce if combined with other stress signals

However, this requires formal redesign before any portfolio testing.

---

## 11. Verdict

**Drop Phase 4 as portfolio modifier — retain components as diagnostic inputs**

The leadership composite as designed has full-history IC of −0.089 and is anti-predictive in calm_trend and neutral_mixed — exactly the target states. The signal is real and informative but with inverted sign: high "quality leadership" predicts lower near-term returns (late-cycle crowding effect).

**Do not use the leadership_quality_composite in its current form as a portfolio modifier.** The composite would reduce offense when it should increase it and vice versa.

**What to carry forward:**
1. `leadership_rotation_persistence` (IC +0.027) is the only component with correct sign — it can be an input to Phase 5's deployment confidence score.
2. `credit_equity_alignment` (IC −0.014) is near zero but has clear economic motivation — keep as a Phase 5 component.
3. The full composite, INVERTED (−1 × leadership_quality_composite), is a potential fragility indicator for Phase 5. When leadership quality is historically high and prices are broadly extended, the inverted signal could be a caution flag in the allocator objective.

**Move directly to Phase 5** (Allocator Objective Redesign). Do not open Phase 4B.

---

## 11. Files Created

- `data/research/frontier_phase4/leadership_signals.csv`
- `data/research/frontier_phase4/leadership_ic_results.csv`
- `data/research/frontier_phase4/leadership_component_ic.csv`
- `data/research/frontier_phase4/leadership_quintile_returns.csv`
- `data/research/frontier_phase4/leadership_partial_ic.csv`
- `docs/research/frontier_phase4_leadership_signals_report.md`

## 12. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified