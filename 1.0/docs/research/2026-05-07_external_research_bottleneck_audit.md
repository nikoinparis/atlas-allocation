# External Research — Part A: Local Project Bottleneck Audit

**Date:** 2026-05-12
**Type:** Research/analysis only. No strategy changes. No production pin changes.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense` (GGG1)

---

## Startup Check Confirmation

| Check | Result |
|-------|--------|
| Working directory | `/Users/nicholasturangan/Documents/Portfolio Optimizer` |
| Branch | `main` |
| Worktree | Main worktree active; one Claude worktree exists (`objective-dubinsky-1d724a`) but not active here |
| CLAUDE.md | Present |
| Phase 7 report | Present |
| Phase 6 report | Present |
| Phase 5A-Free report | Present |
| Phase 4B report | Present |
| project_journey.md | Present |

---

## Evidence Reviewed

- `docs/research/2026-05-07_phase_7_allocator_objective_rewrite_report.md`
- `docs/research/2026-05-07_phase_6_market_state_classifier_rebuild_report.md`
- `docs/research/2026-05-07_phase_5a_free_current_constituent_breadth_diagnostic_report.md`
- `docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md`
- `docs/research/project_journey.md` (sections 1–17)
- `data/research/phase_7_allocator_objective_rewrite/phase7_state_summary.csv`
- `data/research/phase_7_allocator_objective_rewrite/phase7_candidate_metrics_full.csv`
- `public/dashboard-summary.json`

---

## 1. Top 5 Bottlenecks

### Bottleneck 1 — calm_trend state is the structural ceiling [CONFIRMED BY DATA]

**Evidence:**
- calm_trend represents 26.6% of all weeks (295 of 1,110)
- Phase 4B best in calm_trend: 4.39% annualized / Sharpe 0.510
- SPY during calm_trend weeks: 16.87% annualized
- Opportunity cost: −12.48 pp per year in the most common "good" state
- Every attempt to boost calm_trend via sector reallocation (Phase 4, Phase 4B, Phase 7) either did not help or made it worse:
  - Phase 7 stretch: pushed sector from 18.5% to 29.7% in calm_trend → return fell from 4.39% to 4.21%
  - Phase 6 extreme_quality_calm signal: showed positive SPY lift (+0.271%) but negative Phase 4B lift (−0.019%)
  - Phase 6 aggression_score_high: showed −0.041% same-state lift in calm_trend

**Why:** The sector ETF sleeve (XLK, XLF, etc.) does not deliver systematically higher returns in calm bull markets than the diversified Phase 4B mix. Sector leadership during calm weeks is not predictable with existing ETF breadth features. The differentiating signal is stock-level breadth quality, which requires PIT data.

**Magnitude:** Closing the calm_trend gap to even a 6% annualized rate (vs current 4.39%) would add roughly +0.43 pp to full-period returns, enough to close the 8% target.

---

### Bottleneck 2 — Data limitation: no point-in-time stock breadth [CONFIRMED BY DATA]

**Evidence:**
- Phase 5A-Free diagnostic confirmed that stock breadth (% above 200d MA, positive 13w/26w return) shows +0.517% per 4-week SPY lift in calm_trend vs off-signal weeks
- For Phase 4B specifically: +0.347% per 4-week lift in calm_trend
- At 13-week horizon, broad_stock_bull shows +1.290% SPY lift (83.3% hit rate) vs +0.040% at 4-week
- The existing ETF breadth feature (`breadth_sma_43`) shows **negative** SPY lift (−0.457%) in the 2020+ period because the ETF universe includes bonds, REITs, and commodities — their breadth can be low even during equity bull markets
- Stock breadth clearly outperforms ETF breadth as a forward return predictor for both SPY and Phase 4B

**Why this is a data problem, not a code problem:** The Phase 5A-Free script proved stock breadth is meaningful, but it used survivorship-biased current constituents. Production-valid signals require PIT constituent history back to 2005 (Norgate, WRDS/CRSP, or Sharadar). Without PIT history, any production candidate built on stock breadth would be biased.

---

### Bottleneck 3 — The Sharpe-return tradeoff is steepening [CONFIRMED BY DATA]

**Evidence:**
| Phase | Ann Return | Sharpe | Tradeoff |
|-------|-----------|--------|----------|
| GGG1 | 7.14% | 0.936 | baseline |
| Phase 4B best | 7.76% | 0.959 | +0.62pp return, +0.023 Sharpe |
| Phase 6 best | 7.80% | 0.953 | +0.66pp return, +0.017 Sharpe |
| Phase 7 stretch | 7.88% | 0.926 | +0.74pp return, −0.010 Sharpe |

- Phase 4B to Phase 6: +0.04pp return costs −0.006 Sharpe
- Phase 4B to Phase 7: +0.12pp return costs −0.033 Sharpe (≈−2.75 Sharpe pts per pp of return)
- The 2020-forward holdout confirms this: Phase 7 stretch trails Phase 4B on Sharpe in the holdout (0.947 vs 1.012)

**Why:** Each marginal unit of return is being purchased by taking on more concentrated sector exposure, more reallocation speed, or both. These increase short-term volatility and drawdown risk without a proportional increase in median returns. The diversification premium from HRP is being diluted.

---

### Bottleneck 4 — recovery_confirmed has too few weeks to move the needle [CONFIRMED BY DATA]

**Evidence:**
- recovery_confirmed: 44 weeks / 1,110 total = 4.0% of all weeks
- Phase 7 stretch achieves +1.01pp vs Phase 4B in recovery_confirmed
- But at 4% frequency, this improvement contributes only ~0.04 pp to full-period returns
- Even "perfect" recovery_confirmed performance cannot close the calm_trend gap
- SPY in recovery_confirmed: 40.09% annualized. Best Phase 7 candidate: 5.37%. Still −34.7 pp opportunity cost.

**Why this matters:** Multiple phases (Phase 4B, Phase 6, Phase 7) all prioritized improving recovery states because the signal lift was visible and causal. But frequency-weighted contribution is small. The improvement arc is limited by base rate.

---

### Bottleneck 5 — BIL/cash drag in offense windows [CONFIRMED, but partly structural]

**Evidence:**
- GGG1 avg BIL: 26.7%
- Phase 4B best avg BIL: 23.6%
- Phase 7 stretch avg BIL: 21.6%
- In calm_trend specifically: Phase 4B holds 7.5% avg BIL, Phase 7 stretch holds 6.1%
- In neutral_mixed: Phase 4B holds 22.2% avg BIL, Phase 7 stretch holds 21.6%
- Production pin (`improved_phase2b_regime_confidence_boost`): 28.4% avg BIL

**Why this is partly structural:** The HRP base allocator naturally holds BIL as a diversification buffer. Reducing BIL without a corresponding signal quality improvement tends to increase drawdown (as Phase 7 stretch demonstrates: BIL fell to 21.6%, max drawdown deepened to −15.28%). BIL drag is not the primary bottleneck — it is a symptom of conservative signal quality, especially in calm_trend.

---

## 2. Confirmed vs Hypothesized Bottlenecks

| Bottleneck | Status | Evidence |
|-----------|--------|---------|
| calm_trend is the structural ceiling | **CONFIRMED** | Phase 4B, 6, 7 reports; state_summary.csv; direct sector-boost experiments |
| No PIT stock breadth limits calm_trend improvement | **CONFIRMED** | Phase 5A-Free; stock vs ETF breadth comparison; ETF breadth shows negative lift |
| Sharpe-return tradeoff steepening | **CONFIRMED** | Phase 4B → 7 progression; holdout metrics |
| recovery_confirmed too infrequent | **CONFIRMED** | 4% frequency × 1.01pp lift = ~0.04pp portfolio impact |
| BIL drag in offense windows | **CONFIRMED** (structural) | avg_BIL across all phases |
| neutral_mixed still improvable | **HYPOTHESIS** | Phase 6 shows 12.07% already > SPY; further improvement possible but unconfirmed |
| ETF universe too narrow | **HYPOTHESIS** | Sector ETFs don't outperform in calm, but this could be a selection/weighting issue |
| HRP construction suboptimal | **HYPOTHESIS** | Phase 2A tested ERC/HERC/MVO — none dominates HRP on the composite |

---

## 3. States Assessment

### Working Well

| State | Best candidate return | Notes |
|-------|----------------------|-------|
| stressed_panic | 3.83% | SPY: −4.92% in same periods. Protection excellent. BIL ~52%. |
| neutral_mixed | 12.29% (Phase 7 stretch) | Already beats SPY (8.64% in same periods). Phase 4B massive improvement here. |
| recovery_fragile | 7.95% (Phase 7 stretch) | Solid, though frequency is low (4.4%). |

### Underperforming

| State | Best candidate return | SPY in same periods | Gap |
|-------|----------------------|---------------------|-----|
| calm_trend | 4.39% (Phase 4B) | 16.87% | **−12.48 pp** |
| recovery_confirmed | 5.37% (Phase 7 stretch) | 40.09% | −34.7 pp |

**Note:** recovery_confirmed's gap is enormous but lower priority due to 4% frequency. calm_trend's gap is the binding constraint.

---

## 4. Root Cause Taxonomy

| Issue type | Severity | Confirmed? |
|-----------|---------|-----------|
| **Data limitation** (no PIT stock breadth) | Critical | Yes |
| **Signal quality** (existing features can't split calm weeks) | Critical | Yes |
| **ETF universe limitation** (sector ETFs don't outperform in calm) | High | Yes |
| **State classification** (can't identify high-quality calm sub-weeks) | High | Yes (from feature failure) |
| **Allocator mapping** (HRP too conservative) | Medium | Partially tested — HRP won Phase 2A |
| **Weak alpha** (the sleeves themselves) | Medium | Yes in calm; No in neutral/stress |

**Primary verdict:** The issue is primarily a **data limitation** that creates a **signal quality** problem, which in turn limits **state classification** resolution, which means the **ETF universe** (even a good one) cannot be well-deployed. The allocator is not the main constraint.

---

## 5. Is the Project Too Defensive?

**Answer: Defensive in the right stressed places, but over-conservative in calm_trend.**

- In stressed_panic: 52% BIL, 3.83% return vs SPY −4.92%. This defensiveness is excellent — it is the portfolio's strongest feature.
- In calm_trend: 7.5% BIL (Phase 4B), but the sector sleeve doesn't add value over a diversified mix. The portfolio is **not too defensive** (BIL is only 7.5%) — it simply lacks the right offensive ETF combination for calm weeks.
- In neutral_mixed: already beating SPY at 12.07% annualized. Not too defensive here either.

**The framing "too defensive" is wrong.** The issue is that the offensive instruments available (sector ETFs) are not sufficiently superior to the existing diversified mix during calm bull markets. More aggression (lower BIL, higher sector) without better signal quality makes calm_trend worse, as Phase 7 demonstrated.

---

## 6. Is the Portfolio Underexposed to US Beta, QQQ/Growth, or Sector Leadership?

**Partially yes, by design and by evidence:**

- Beta to SPY across all candidates: ≈ −0.033 (slightly negative — the portfolio diversifies away from SPY correlation)
- In calm_trend weeks, SPY earns 16.87% annualized. The portfolio earns 4.39%. This is a massive divergence.
- Phase 3 (high_breadth_calm_us_offense) tested pure US equity offense in calm_trend → improved Sharpe (0.966) but not return enough
- Phase 4B sector sleeve (XLK, XLF etc.) → improves full-period return but not calm_trend specifically
- **QQQ/growth underexposure is real:** The best full-period return is 7.88% vs QQQ 14.69% (2005–2026). But adding direct QQQ exposure would add SPY-like beta that the mandate explicitly avoids.

**The mandate requires low SPY/QQQ beta.** Given this constraint, the portfolio is appropriately exposed to US equity. The problem is that within that constraint, existing features cannot identify which calm weeks are worth pressing harder on.

---

## 7. Return Limits: Source Analysis

| Source | Severity | Notes |
|--------|---------|-------|
| Weak alpha in calm_trend | **Primary** | 4.39% vs 16.87% SPY; no ETF signal to improve |
| BIL/cash drag | Secondary | 23-26% avg BIL in best candidates; reducing without signal hurts DD |
| Sleeve design (sector ETFs don't outperform calm) | Secondary | Confirmed in Phase 4B, 6, 7 |
| HRP conservatism | Tertiary | Phase 2A found HRP robust; not the binding constraint |
| Risk controls (max DD, CVaR, turnover) | Tertiary | These are guardrails; they bind only when reaching for return |
| Volatility targeting | Minor | Not explicitly in pipeline; Phase 7 tested faster reallocation |

**Verdict:** The return ceiling is primarily driven by the absence of a differentiated calm_trend offense signal. BIL drag and construction conservatism are secondary contributors that become visible only once the signal gap is acknowledged.

---

## 8. Previous Failures and Why

| Attempt | Phase | Why it failed |
|---------|-------|--------------|
| Combo1 (C1a + A1g sector sleeve) | Phase 3.2 | A1g hurt holdout (Sharpe dropped −0.05); sector sleeve addition was harmful in holdout |
| Tighter state gate (recovery_confirmed only, R1/R3) | Phase 3.2 | Dropped recovery_fragile contribution; lift collapsed to +0.0045 |
| T1/T2/T3 tail overlays | Phase 3.4 | No-ops on holdout; never triggered in practice |
| A1g sector sleeve | Phase 3.5 attribution | Source of all DD damage and holdout failure in Combo1 |
| High_quality_neutral signal | Phase 6 | Never fired — `transition_good_state_prob` max 0.205 in neutral_mixed, condition required ≥0.60 |
| Larger sector sleeve in calm_trend (C5 Phase 7) | Phase 7 | Sector at 29.7% in calm → return fell from 4.39% to 4.21%; sector ETFs don't outperform diversified mix |
| Phase 6 extreme_quality_calm booster | Phase 6 | Phase 4B already optimally deployed sector in those weeks; extra boost created over-allocation drag |
| Phase 6 aggression_score in calm/neutral | Phase 6 | Same-state lift was −0.041% (calm) and −0.089% (neutral) — signal fires in too many non-recovery weeks |
| ERC/HERC/MVO allocators | Phase 2A | None consistently dominated HRP on the composite; HRP's diversification interacts well with regime overlay |
| Phase 4 25% sector sleeve | Phase 4 | Extra 5% funded from useful sleeves; sector volatility too high; return flat, Sharpe deteriorated |
| Contained_recovery_quality signal | Phase A | Full-sample validation weak; not holding up as independent signal |

---

## 9. Summary Diagnosis

**The project has exhausted the systematic improvement arc available with existing ETF/sector/regime data.**

- Full-period return: 7.14% → 7.88% (+0.74 pp over 7 phases)
- Gap to 8.0% target: 0.12 pp
- The 0.12 pp cannot be closed without a new signal source in calm_trend
- The binding constraint is stock-level breadth quality in calm_trend (PIT data required)
- The allocator, HRP construction, and risk controls are secondary to this data gap
- The portfolio's defensive posture in stressed states is a genuine asset, not a problem
- neutral_mixed performance is already good (12.07% annualized, above SPY)
- The only state where meaningful improvement remains addressable with existing data is a very narrow further improvement in neutral_mixed sub-classification — but even that is uncertain given Phase 6's near-zero delta there

**The project is currently near the ceiling with existing data.**
