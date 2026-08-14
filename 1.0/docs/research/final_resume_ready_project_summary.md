# Final Resume-Ready Project Summary

**Generated:** 2026-05-25  
**Project:** Layered ETF Quant Portfolio — Production Strategy Snapshot

---

## 1. Project Overview

A research-grade systematic ETF portfolio built from scratch in Python and deployed as a live production strategy. The system uses a three-layer architecture to move from raw price data → alpha signals → causal market-state aware sleeves → a portfolio construction engine with regime overlays. Every design decision was driven by interpretability and walk-forward out-of-sample evidence.

The project spans 10+ research phases, a custom governance process, a Next.js research dashboard, and a final promoted production strategy that improves all headline metrics versus the prior production pin while preserving stressed-market defense.

---

## 2. Final Production Strategy

**Strategy name:** `improved_frontier_phase5_fragility_guard`  
**Status:** PROMOTED — human authorized after Phase 10A final evaluation  
**Promotion date:** 2026-05-23  
**Promotion report:** `docs/research/frontier_phase10_final_evaluation_report.md`

### Design

The strategy is a wrapper modifier applied on top of the GGG1 base allocation logic:

1. **Phase 1 R2A state-quality offense scaling**
   - Scales offense up by `(1 + 0.08 × R2A_score)` when market-state quality is high
   - One-week lag; clipped to a bounded range
   - Active in recovery, calm, and neutral states only
   - **No offense increase in `stressed_panic`**

2. **Phase 4 fragility/crowding guardrail**
   - Monitors leadership diagnostics (ETF leadership score)
   - **Blocks** the Phase 1 offense boost when leadership > 0.50 (crowded or late-cycle signal)
   - Phase 4 alone failed as a buy-more signal but works reliably as a risk-control gate
   - Key insight: the guardrail is asymmetric — it never forces defense, it only blocks additional offense

3. **Stressed-panic defense**
   - Unchanged versus GGG base
   - Verified: stressed_panic offense max diff vs GGG = **0.000e+00**

---

## 3. Before/After Metrics

| Metric | Prior Production (Phase2B) | Production (Phase5) | Delta |
|--------|---------------------------|---------------------|-------|
| Annual Return | 6.89% | 7.13% | +0.24pp |
| Annual Vol | 7.79% | 7.52% | −0.27pp |
| **Sharpe** | **0.884** | **0.948** | **+0.064** |
| **Max Drawdown** | **−13.98%** | **−11.60%** | **+2.38pp** |
| CVaR 5% | −2.62% | −2.49% | +0.13pp |
| Calmar | — | 0.615 | — |
| **Holdout Sharpe** | **2.100** | **2.179** | **+0.079** |
| Holdout Return | — | 17.91% | — |
| Avg BIL | 28.4% | 27.6% | −0.8pp |
| Avg SPY | 7.08% | 5.91% | −1.17pp ⚠ |
| Weekly Turnover | 5.62% | 6.74% | +1.12pp ⚠ |

**⚠ Trade-offs:** SPY exposure fell slightly (the guardrail blocks some market participation); turnover increased (conditional scaling adds rebalancing steps).

---

## 4. Validation Methods

| Check | Result |
|-------|--------|
| Phase D gates passed | **8/8** |
| Bootstrap support (Phase 10A) | **~84%** (0.841) |
| Rolling win rate | **73%** |
| Stressed-panic offense diff vs GGG | **0.000e+00** |
| Time-ordered train/test splits | Required throughout — no random splits |
| Hindsight regime labels | Prohibited — all labels are walk-forward |
| Incremental contribution test | Required vs GGG, prior production, and shadow |
| Prior production pin | Preserved as rollback |
| Allocator checkpoint wrapper | Exact match: net_return_max_abs_error = 2.116e-16 |
| Deployment rule harness | Architecture-valid rules = 7/8 |

---

## 5. Research Phase History

| Phase | Status | Key Outcome |
|-------|--------|-------------|
| Phase 1 (A–G) | Complete | Deployment discipline, state-conditioned leadership, dynamic risk budget |
| Phase 2A | Complete | Allocator research (ERC/HERC/MVO/BL) → HRP confirmed as production allocator |
| Phase 2B | Complete | Causal market-state engine: stressed_panic, recovery_fragile/confirmed, neutral_mixed, calm_trend |
| Phase OOO6 | Shadow only | Never promoted; valid comparison reference |
| Phase PPP | Null | No new latent sleeve found |
| Phase QQQ | Direction set | Pointed to regime-sequence modeling |
| Phase SSS2 | Signal audit | Cleared 3 signals for SSS3 |
| Frontier Phase 1 | Complete | R2A state-quality signal — offense scaling, holdout improvement |
| Frontier Phase 2 | Complete | Trend quality engine |
| Frontier Phase 3 | Complete | Smart re-risk engine |
| Frontier Phase 4 | Partial promote | Leadership/crowding diagnostics — failed as alpha, promoted as guardrail |
| **Frontier Phase 5** | **PROMOTED** | **Fragility guard wrapper — current production pin** |
| Frontier Phase 6 | Complete | Decision labels |
| Frontier Phase 7 | Complete | Cross-asset lead-lag signals |
| Phase 10A | Governance | Final evaluation complete; all 8 Phase D gates passed; human authorized |

---

## 6. Technical Architecture

### Data & Signals (Layer 1)
- **Universe:** Diversified ETF universe (equities, bonds, commodities, real estate, cash)
- **Signals:** ETF cross-sectional momentum, trend (50d/200d MA), breadth (% above moving averages), dollar-strength (4w/8w/13w/26w), quality indicators, regime-aware composite signals
- **Validation:** IC (mean, t-stat, Newey-West), decay profiles, redundancy heatmap, signal subset comparison

### Market-State Engine (Layer 2B)
- **States:** `stressed_panic`, `recovery_fragile`, `recovery_confirmed`, `neutral_mixed`, `calm_trend`
- **Features:** Causal, lagged — no look-ahead. Breadth momentum, market drawdown, VIX-based stress proxies, transition quality scores
- **Walk-forward:** States computed with only information available at decision time

### Sleeves (Layer 2)
- `dual_momentum_topn`: Cross-sectional + time-series dual-momentum ETF selector
- `cta_trend_long_only`: CTA-style trend following, long-only
- `composite_regime_offense/defense`: Regime-conditioned composite sleeves
- `taa_10m_sma`: Tactical asset allocation with 10-month moving average

### Portfolio Construction (Layer 3)
- **Base allocator:** HRP (Hierarchical Risk Parity) — confirmed best across 5+ allocator families
- **Regime overlay:** Scales sleeve weights by market-state multipliers
- **Target-vol overlay:** Dynamic risk budget (Phase 1A)
- **Fragility guardrail:** Phase 5 wrapper — R2A scaling gated by Phase 4 crowding diagnostics
- **Checkpointed plumbing:** New ideas tested against exact GGG baseline without rewriting production logic

### Dashboard
- **Framework:** Next.js 15 + TypeScript + Recharts
- **Server-side executive summary:** Renders key metrics before client JS hydrates
- **Compact bundle:** `production-candidate-dashboard-bundle.json` — avoids the 100MB+ full data file
- **Sections:** Overview / What Changed / Layer 1 / Layer 2 / Layer 3 / Allocators / Version Lab / Guardrails / Diagnostics
- **Governance:** Production pin + prior production + shadow all pinned in source code constants

### Production Governance
- **Registry:** `data/05_layer3_portfolio_construction/production_candidate_registry.json`
- **Pin constants:** Hardcoded in `src/components/dashboard-shell.tsx` and `src/lib/compact-dashboard.ts`
- **Rollback:** One-line registry change to `improved_phase2b_regime_confidence_boost`
- **Promotion gate:** Human authorization required before any pin change

---

## 7. Resume Bullets

**Quantitative Research / Systematic Strategy**
- Built a production ETF portfolio from scratch using a layered quant stack: cross-sectional alpha signals (Layer 1), a causal market-state engine with walk-forward regime labels (Layer 2B), and HRP portfolio construction with dynamic regime overlays (Layer 3).
- Improved Sharpe from 0.884 to 0.948 and max drawdown from −13.98% to −11.60% through 10+ research phases with strict no-look-ahead, time-ordered validation.
- Designed a fragility guardrail that blocks offense scaling when leadership diagnostics indicate crowded or late-cycle conditions — increasing full-period and holdout performance while preserving stressed-market defense (0.000e+00 offense diff vs baseline).
- Conducted comprehensive signal research across ETF momentum, trend, breadth, dollar-strength, and regime-aware indicators; redundancy-tested and IC-validated every candidate before production consideration.
- Built and passed an 8-gate promotion governance process including bootstrap validation (~84% support), rolling win-rate testing (73%), and stressed-panic regression audit before any production pin change.

**Software Engineering / Data Infrastructure**
- Implemented a Next.js research dashboard with server-side metric rendering, compact JSON bundle architecture, and interactive Recharts visualizations — accessible to non-technical reviewers on first paint.
- Designed a checkpointed allocator wrapper enabling exact reproducibility: allocator_checkpoint_wrapper test shows net_return_max_abs_error = 2.116e-16 vs saved production output.
- Maintained strict git governance: never committed large data files, regenerated bundles cleanly on demand, and enforced production pin hardcoding so accidental promotions are impossible.

---

## 8. Interview Explanation (2–3 minutes)

> "The project builds a systematic ETF portfolio using a three-layer architecture. Layer 1 produces alpha signals — momentum, trend, breadth, dollar-strength — validated with forward IC and decay analysis. Layer 2 uses a causal market-state engine to classify each week as stressed, recovering, neutral, or calm, then routes the allocation accordingly across specialized sleeves. Layer 3 uses HRP portfolio construction with dynamic regime overlays on top.
>
> The core research question was: can we improve risk-adjusted returns by being a bit more aggressive in genuinely good states without being more aggressive in crowded or stressed ones? The answer was yes, but with a twist: Phase 4 leadership diagnostics didn't work as a buy-more signal. What they *did* work for was blocking the Phase 1 offense boost in crowded conditions. That asymmetry — 'scale offense in high-quality states, but not when leadership looks overextended' — is the Phase 5 fragility guardrail.
>
> The result: Sharpe from 0.884 to 0.948, max drawdown from −13.98% to −11.60%, holdout Sharpe from 2.10 to 2.18, all with stressed-panic defense completely unchanged. The strategy passed an 8-gate governance review including bootstrap validation and a stressed-panic regression audit before it was promoted to production."

---

## 9. Caveats and Known Limitations

| Caveat | Detail |
|--------|--------|
| No live market-state feed | The compact dashboard bundle does not include live state history; the current date's state is not displayed |
| Guardrail is a judgment call | If Phase 4 crowding diagnostics fire incorrectly, the strategy misses a rally it would have caught without the filter |
| SPY exposure fell | From 7.08% to 5.91% avg — the guardrail reduces market participation in some states |
| Turnover increased | From 5.62% to 6.74% weekly — conditional scaling adds rebalancing steps |
| Sleeve-weight artifact | The sleeve-weight file in the compact bundle is a review proxy; ETF weights and returns are the production source of truth |
| Universe is ETFs only | No single-stock selection; signals are cross-sectional across the ETF universe |
| Bootstrap intervals overlap | Phase 10A bootstrap intervals between Phase5 and prior production overlap, so the gain is real but not statistically overwhelming — it is practically meaningful |

---

## 10. Rollback Plan

1. Open `data/05_layer3_portfolio_construction/production_candidate_registry.json`
2. Change `current_production_pin` to `improved_phase2b_regime_confidence_boost`
3. Change `production_candidate` accordingly
4. Regenerate the compact bundle: `.venv/bin/python scripts/phase_iii_packaging_review.py`
5. Update pin constants in `src/components/dashboard-shell.tsx` and `src/lib/compact-dashboard.ts`
6. Run `npm run build` to confirm clean

**Rollback references available:**
- Primary rollback: `improved_phase2b_regime_confidence_boost` (Phase 2B confidence boost)
- Secondary rollback: `improved_phaseggg_confirmed_only_robust_offense` (GGG1 — prior Phase III candidate)
- Official shadow (for comparison only): `improved_phase2b_combo_abc`

---

## 11. Key Files Reference

| Category | Path |
|----------|------|
| Production registry | `data/05_layer3_portfolio_construction/production_candidate_registry.json` |
| Phase 10A evaluation report | `docs/research/frontier_phase10_final_evaluation_report.md` |
| Production review checklist | `docs/research/phase5_fragility_guard_production_review_checklist.md` |
| Compact bundle generator | `scripts/phase_iii_packaging_review.py` |
| Allocator checkpoint wrapper | `scripts/allocator_checkpoint_wrapper.py` |
| Deployment rule harness | `scripts/run_deployment_rule_harness.py` |
| Dashboard shell | `src/components/dashboard-shell.tsx` |
| Executive summary | `src/components/executive-summary.tsx` |
| Compact bundle transformer | `src/lib/compact-dashboard.ts` |
| Dashboard bundle (public) | `public/production-candidate-dashboard-bundle.json` |
| Project journey narrative | `docs/research/project_journey.md` |
| Research scoreboard | `docs/research/research_scoreboard.md` |
