# External Research — Part E: Recommended Next 3 Sprints

**Date:** 2026-05-12
**Type:** Research recommendations only. No strategy changes.
**Constraints applied:**
- No paid stock data
- No Norgate as immediate sprint
- No blind phase recommendations
- No overfitted ML
- No individual-stock trading without PIT data

---

## Context: Where the Project Stands

After 7 phases of systematic existing-data optimization, the full-period return arc is:
- GGG1 baseline: 7.14% / 0.936 Sharpe
- Phase 7 stretch (best return): 7.88% / 0.926 Sharpe
- Phase 4B (best Sharpe): 7.76% / 0.959 Sharpe
- Gap to 8.0% target: 0.12 pp

The 0.12 pp gap cannot be closed with existing data. The primary bottleneck is calm_trend classification quality, driven by the absence of PIT stock breadth.

**Recommendation framework for the next three sprints:**
1. Sprint 1: A focused, low-complexity improvement to the sector sleeve timing with strong literature backing. Clear success/failure criteria. Does not require PIT data.
2. Sprint 2: A portfolio construction quality improvement that targets the Sharpe-return tradeoff without requiring a new signal.
3. Sprint 3: A diagnostic sprint that prepares the project for the PIT data acquisition decision and establishes the regime classifier as a credible, publishable piece of infrastructure.

---

## Sprint 1 — Volatility-Managed Sector Sleeve

**Sprint name:** Phase 8 — Volatility-Managed Sector Sleeve

**Why now:**
- The sector sleeve is the largest marginal lever available with existing data
- Phases 4B, 6, and 7 all showed that adding more sector exposure in calm_trend fails (it doesn't increase calm return but does increase volatility)
- Moreira-Muir (2017) and Barroso-Santa-Clara (2015) provide strong academic backing for volatility scaling
- The fix is a single scalar multiplier on the sector sleeve budget — minimal code change
- The Sharpe-return tradeoff (each +1 pp return costs ~3.3 Sharpe points) is the most actionable near-term problem

**What it tests:**
- Whether scaling the sector sleeve by the inverse of its own 13-week or 26-week realized volatility improves Sharpe without materially reducing return
- Whether the mechanism is robust across full period, 2020+, and 2022 bear window
- Whether the improvement holds after combining with Phase 4B vs Phase 6 vs Phase 7 bases

**Specific hypotheses:**
- H1: Vol-scaled sector reduces max drawdown by ≥0.5 pp vs Phase 4B best
- H2: Vol-scaled sector improves Sharpe by ≥0.005 vs Phase 4B best
- H3: Full-period return does not fall by more than 0.10 pp vs Phase 4B best

**Files likely touched:**
- `scripts/phase_8_volatility_managed_sector_sleeve.py` (new script)
- `scripts/build_improvement_artifacts.py` (add Phase 8 state tilt modes)
- `data/research/phase_8_volatility_managed_sector_sleeve/` (outputs)

**Expected outputs:**
- Full-period and holdout metrics vs Phase 4B best, Phase 6 best, Phase 7 stretch
- State-by-state breakdown (does vol scaling hurt recovery_confirmed, where sector matters?)
- Realized vol time series for the sector sleeve
- Audit results (research committee, backtest realism, allocator benchmark)

**Success criteria:**
- Full-period Sharpe ≥ 0.965 (vs Phase 4B's 0.959) without losing more than 0.10 pp return
- OR: Full-period return ≥ 7.80% with Sharpe ≥ 0.950
- Max drawdown not worsening vs Phase 4B best (−13.77%)
- 2022 bear return not worse than Phase 4B − 4pp (mandate threshold)
- Passes all three audits (research committee, realism, benchmark)

**Failure criteria:**
- Sharpe does not improve vs Phase 4B best
- Max drawdown worsens by ≥ 0.5 pp
- 2022 protection fails

**Whether it needs web/data:** No. Existing ETF price history is sufficient.
**Agent recommendation:** Claude Code. Straightforward implementation sprint; uses the established build pipeline.
**Sprint type:** Implementation + validation.
**Estimated effort:** 1–2 sprint days.

---

## Sprint 2 — Construction Quality Audit and ERC Alternative

**Sprint name:** Phase 8B (or Phase 9) — Sector Sleeve Construction Upgrade

**Why now:**
- After 7 phases of testing signal-level improvements, no phase has explicitly tested construction-level improvements to the sector sleeve itself
- The sector ETFs (11 SPDR XL funds) form a small universe where HRP's covariance estimation may be unstable (N=11 assets, ~100 active weeks per state)
- Ledoit-Wolf covariance shrinkage and ERC (equal risk contribution) are well-motivated alternatives with minimal overfitting risk
- This sprint does not require new signals or data — it changes how existing signals are turned into weights

**What it tests:**
Three construction variants for the sector sleeve:
- **C1:** Ledoit-Wolf shrinkage applied to the sector covariance matrix before HRP (reduces estimation error)
- **C2:** ERC (equal risk contribution) weights for the sector ETFs instead of HRP (all sectors contribute equally to sleeve variance)
- **C3:** Inverse volatility (simplest possible) weights for the sector ETFs

**Specific hypotheses:**
- H1: Shrinkage reduces sector sleeve turnover by ≥10% (cleaner covariance → more stable weights)
- H2: ERC reduces max drawdown in the sector sleeve by allocating less to the highest-vol sector ETFs
- H3: At least one construction variant improves full-period Sharpe vs Phase 4B best without reducing return

**Files likely touched:**
- `scripts/phase_9_sector_construction_upgrade.py` (new script)
- `scripts/build_improvement_artifacts.py` (add construction variants)
- `data/research/phase_9_sector_construction_upgrade/` (outputs)

**Expected outputs:**
- Turnover comparison: raw HRP vs shrinkage vs ERC vs inverse-vol
- Full-period and holdout metrics vs Phase 4B best
- Max single-sector weight concentration over time
- State-by-state breakdown

**Success criteria:**
- Full-period Sharpe ≥ 0.960 (vs Phase 4B's 0.959) with full-period return ≥ 7.70%
- Sector sleeve turnover reduced by ≥10%
- Max drawdown not worsening
- 2022 protection maintained

**Failure criteria:**
- No construction variant improves on Phase 4B best Sharpe
- Turnover is not reduced

**Whether it needs web/data:** No. Existing ETF returns are sufficient.
**Agent recommendation:** Claude Code. Well-defined scope; standard portfolio math.
**Sprint type:** Implementation + validation.
**Estimated effort:** 1–2 sprint days.

---

## Sprint 3 — Regime Classifier Robustness and Publication-Ready Diagnostic

**Sprint name:** Phase RRR — Regime Engine Robustness and Documentation Sprint

**Why now:**
- The project has run 7 phases of strategy improvements but has not produced a rigorous statistical analysis of the regime engine itself
- The regime engine (Layer 2B) is the project's most distinctive architectural contribution — it is what makes this a real systematic strategy rather than a momentum backtest
- Before acquiring PIT data and building Phase 5B, the project should document how well the current regime engine works: transition accuracy, false positive/negative rates, state persistence, and economic validity of each state
- This sprint produces a research artifact that is independently publishable (or presentable) and makes the project much more impressive to quants
- It also prepares the ground: when PIT stock breadth is added, this diagnostic becomes the validation baseline

**What it tests:**
A rigorous multi-test validation of the regime engine:
- **T1:** State persistence (how long do states last? how often do they correctly persist vs prematurely transition?)
- **T2:** Forward return validation by state (are the regime labels economically meaningful? does calm_trend have lower forward SPY returns than recovery_confirmed as expected?)
- **T3:** Transition accuracy (after a stressed_panic → recovery_fragile transition, how often does recovery_confirmed follow within N weeks?)
- **T4:** Walk-forward simulation (if the regime engine had been run forward from 2010, 2012, 2015, 2018, what would state accuracy look like?)
- **T5:** Comparison to simple alternative classifiers (12-month SMA, volatility-only classifier, CAPE-based classifier) — does the current multi-feature engine add value vs simpler alternatives?

**Files likely touched:**
- `scripts/phase_rrr_regime_classifier_robustness.py` (new script)
- `data/research/phase_rrr_regime_classifier_robustness/` (outputs)
- `docs/research/YYYY-MM-DD_phase_rrr_regime_classifier_robustness_report.md` (report)

**Expected outputs:**
- State frequency and persistence statistics (transition matrix, average state duration)
- Forward return validation table by state (SPY, GGG1, Phase 4B vs state label)
- Economic validity scorecard: each state's SPY forward return should rank appropriately (recovery_confirmed > calm_trend > neutral_mixed > stressed_panic on 13-week forward SPY)
- Comparison table vs SMA and vol-only classifier alternatives
- Walk-forward accuracy simulation

**Success criteria (regime engine diagnostic):**
- calm_trend SPY 13-week forward return > neutral_mixed SPY 13-week forward return (directional validity)
- recovery_confirmed > calm_trend (directional validity)
- stressed_panic < neutral_mixed (protection validity)
- State persistence ≥ 3 weeks on average (avoids noise trading)
- No competitor (SMA, vol-only) achieves equivalent state discrimination with simpler inputs

**Failure criteria:**
- The regime engine's state labels are not consistently associated with different forward returns
- A simple SMA or vol-only rule performs as well as the multi-feature engine

**Whether it needs web/data:** No. Uses existing `market_state_history.csv` and price data.
**Agent recommendation:** Claude Code (analysis) + optional ChatGPT-led narrative writing for the report.
**Sprint type:** Analysis-only. No new strategy candidates created. No production pins changed.
**Estimated effort:** 1–2 sprint days.

**Why this is important for the resume/portfolio:**
A rigorous regime engine diagnostic answers the question every quant interviewer will ask: "How do you know your regime labels are meaningful, not just overfitted?" This sprint produces a publishable answer. It also sets up the Phase 5B PIT stock breadth integration: when breadth is added, the regime engine diagnostic becomes the before/after comparison.

---

## What Is NOT Recommended as the Next Sprint

| Sprint type | Why not |
|------------|---------|
| Another blind phase testing many feature combinations | No strong prior. Phase 7 already exhausted the search space. |
| Norgate data acquisition sprint | User does not want to pay for data now. Explicitly excluded. |
| HMM regime classification sprint | Overfitting risk too high with N=295 calm weeks. PIT data first. |
| Meta-labeling with ETF features only | Expected value is very low without PIT data. Phase 6 already tried this. |
| Full allocator rewrite (MVO, Black-Litterman) | Phase 2A already tested alternatives. HRP won on the composite. |
| Individual stock alpha sleeve | Requires PIT data; changes mandate. Not appropriate. |

---

## Sprint Sequencing Summary

```
Sprint 1: Phase 8 — Volatility-Managed Sector Sleeve
  → Implementation + validation sprint
  → Expected: Small Sharpe improvement at modest return cost
  → Literature: Moreira-Muir (2017), Barroso-Santa-Clara (2015)

Sprint 2: Phase 9 — Sector Construction Upgrade (ERC/Shrinkage)
  → Implementation + validation sprint
  → Expected: Turnover reduction; potential Sharpe improvement
  → Literature: Roncalli risk parity; PyPortfolioOpt Ledoit-Wolf

Sprint 3: Phase RRR — Regime Classifier Robustness Diagnostic
  → Analysis-only sprint (no new candidates)
  → Expected: Publication-ready regime engine validation
  → Literature: Hamilton (1989); Ang-Bekaert (2004); Harvey-Liu-Zhu (2016)

Future (when budget): Phase 5B — PIT Stock Breadth Integration
  → Data acquisition sprint
  → Expected: +0.12–0.30 pp return to close 8.0% target
  → Literature: Phase 5A-Free diagnostic; López de Prado meta-labeling
```
