# Renaissance-Inspired Implementation Backlog

**Date:** 2026-05-18  
**Type:** Research + roadmap only. No implementation yet.  
**Reference documents:**
- `docs/research/renaissance_technologies_lessons_for_etf_project.md`
- `docs/research/renaissance_inspired_research_pipeline.md`

---

## Section 6 — Phased Implementation Plan

### Phase R1 — Research Log + Signal Decay (1–2 sprint days)

**Why this first:** Zero overfitting risk. Pure infrastructure. Prevents re-testing ideas that already failed. Signal decay testing requires no new data.

**Files to create:**
```
docs/research/signal_research_log.md
scripts/run_signal_decay_analysis.py
data/02_layer1_signals/signal_decay_profiles.csv
docs/research/r1_signal_decay_report.md
```

**Expected outputs:**
- Decay half-life estimate for all 22 existing signals
- Flag any signals with half-life < 2 weeks (not viable for weekly rebalancing)
- Retrospective log entries for all 22 existing signals

**Acceptance tests:**
- `signal_decay_profiles.csv` populated for all 22 signals
- `signal_research_log.md` initialized with all historical decisions
- At least 3 signals classified as "slow decay" (viable for weekly; expect tsmom, xsmom, multi_mom)
- No code changes to strategy logic or production files

**Reasons to reject/skip:**
- If IC-by-horizon data shows all signals with roughly flat IC across 1–13w (unlikely but possible): decay testing is uninformative; skip and document

**How to know it helped:**
- Signal selection for future phases is informed by decay rates
- No future sprint rediscovers a signal already rejected

---

### Phase R2 — Expanded Signal Zoo (3–5 sprint days)

**Why this second:** Orthogonal signals are the #1 actionable improvement. Free data is available. No paid data needed. The `bab_proxy` precedent shows +0.151 Sharpe when truly orthogonal signals are added.

**Files to create:**
```
scripts/build_macro_signal_library.py
    → inputs: FRED API (DGS10, DGS2, BAMLH0A0HYM2, NFCI)
    → outputs: data/02_layer1_signals/signal_yield_curve.csv
               data/02_layer1_signals/signal_credit_spread.csv
               data/02_layer1_signals/signal_financial_conditions.csv

scripts/build_vix_term_structure_signal.py
    → input: data/01_data_hub/vix_term_structure.csv (existing)
    → output: data/02_layer1_signals/signal_vix_ts.csv

scripts/build_volume_divergence_signal.py
    → input: yfinance weekly volume for 35 ETFs
    → output: data/02_layer1_signals/signal_volume_divergence.csv

scripts/run_r2_signal_validation.py
    → runs all R2 signals through IC battery
    → outputs: data/02_layer1_signals/r2_signal_validation_results.csv
               docs/research/r2_signal_validation_report.md
```

**Expected outputs:**
- 5–8 new signals computed and validated
- 2–4 signals promoted to Layer 1 (estimated, based on literature support)
- Updated `signal_manifest.json` for promoted signals
- Updated `signal_redundancy_matrix.csv`

**Acceptance tests:**
- At least 2 new signals pass IC NW t-stat ≥ 2.0 full-period
- At least 2 new signals pass holdout IC positive (2020+)
- All new signals have pairwise redundancy ≤ 0.50 with existing strong signals
- No new signal increases stressed_panic losses

**How to know it helped:**
- At least one new signal improves the incremental_contribution portfolio test (Δ Sharpe > 0)
- The signal redundancy matrix shows diversity improvement (lower average off-diagonal correlation for the expanded set)

**Reasons to reject/skip:**
- All FRED/VIX signals fail IC test (unlikely — yield curve and credit spreads have academic support)
- All new signals are highly correlated with existing momentum signals (possible for some; unlikely for yield curve)
- In that case: document in research log and move to R5 (pairs signals)

**Data requirements:** FRED API (free, requires registration), existing VIX data, yfinance for volume.  
**Overfitting risk:** Medium. Mitigated by requiring NW-corrected t-stat ≥ 2.0 AND holdout positive.

---

### Phase R3 — State-Conditional IC Testing (2 sprint days)

**Why this third:** Once the expanded signal zoo is in place, testing ICs within each regime state is the highest-leverage use of the regime engine. Finding a signal with IC > 0.08 in calm_trend is the most direct path to addressing the primary bottleneck without PIT data.

**Files to create:**
```
scripts/run_state_conditional_signal_ic.py
    → for each signal × state × horizon: compute IC, NW t-stat, hit rate
    → output: data/02_layer1_signals/signal_state_conditional_ic.csv
              docs/research/state_conditional_signal_report.md
```

**Expected outputs:**
- State × signal × horizon IC matrix (22+ signals × 5 states × 5 horizons)
- Identification of top 3 signals by calm_trend IC
- Identification of any signals with dangerous IC in stressed_panic

**Acceptance tests:**
- At least one signal shows IC ≥ 0.08 in calm_trend (otherwise: limit of existing-data approach confirmed)
- No promoted signal has IC < -0.05 in stressed_panic
- State-conditional IC report documents the analysis cleanly

**How to know it helped:**
- If calm_trend IC ≥ 0.08: we have a new signal to test as a state-conditional override → builds toward a Phase 8 production candidate
- If calm_trend IC < 0.05 for all signals: confirms that PIT stock breadth is truly needed; document clearly

**Reasons to reject/skip:**
- If all state-conditional ICs are within ±0.02 of the full-period IC (no state conditioning effect): skip and document

---

### Phase R4 — ETF Pairs Lab (3–4 sprint days)

**Why fourth:** Pairs signals are structurally orthogonal to momentum and could work especially in calm_trend (where momentum tends to flatten). The CBS thesis showed cointegrated ETF pairs achieved positive Sharpe 2007–2020 including the 2008 crisis period.

**Files to create:**
```
scripts/build_etf_pairs_signals.py
    → test 8 priority pairs for cointegration (Engle-Granger + ADF)
    → fit OU process for each cointegrated pair
    → compute z-score signals (lagged 1 week)
    → test IC at 1, 2, 4 week horizons
    → test state-conditional IC
    → output: data/02_layer1_signals/signal_etf_pairs_{pair}.csv
              data/02_layer1_signals/etf_pairs_cointegration_report.csv
              docs/research/etf_pairs_signal_report.md
```

**Priority pairs:**
1. SPY/QQQ — large cap vs mega-cap tech spread
2. IWM/SPY — small vs large cap value spread
3. TLT/SPY — duration vs equity yield spread
4. GLD/TLT — real vs nominal safe haven spread
5. XLE/USO — energy equity vs commodity basis
6. HYG/LQD — high yield vs investment grade credit spread
7. EEM/SPY — EM vs US equity premium
8. XLK/QQQ — tech sector vs tech-heavy index basis

**Expected outputs:**
- Cointegration test results for all 8 pairs
- OU half-life estimates for cointegrated pairs
- IC validation for viable pairs (OU half-life 2–10 weeks)
- Pairs signal files for any pairs that pass

**Acceptance tests:**
- At least 2 pairs pass the cointegration test (ADF p < 0.05 over 2005–2018)
- At least 1 pair shows IC ≥ 0.05 full-period with NW t-stat ≥ 1.5
- OU half-life 2–10 weeks (mean reversion observable at weekly rebalancing)

**How to know it helped:**
- At least one pairs signal passes the incremental contribution test (Δ Sharpe > 0 vs current best)
- Pairs signal shows positive IC in calm_trend (addresses the primary bottleneck)

**Reasons to reject/skip:**
- No pairs pass cointegration test over training period (documents the ETF pairs idea as not viable for this universe)
- All pairs IC < 0.04 NW t-stat < 1.5 (below the signal quality floor)
- Pairs signals are highly correlated with existing momentum signals (> 0.50 redundancy)

---

### Phase R5 — IC-Weighted Ensemble (2–3 sprint days)

**Why fifth:** Once the signal library is expanded and validated, testing whether IC-weighted combination improves the ensemble vs equal-weight is a small code change with potentially meaningful return improvement.

**Files to create:**
```
scripts/run_ic_weighted_ensemble_test.py
    → compare: equal-weight vs IC-weighted vs ICS-weighted (sqrt of IC)
    → use rolling 104-week IC estimates (walk-forward safe)
    → report full-period and holdout metrics vs current GGG1/Phase4B baseline
    → output: data/research/r5_ic_weighted_ensemble/
              docs/research/r5_ic_weighted_ensemble_report.md
```

**Expected outputs:**
- Full-period and holdout Sharpe comparison (equal-weight vs IC-weighted)
- Bootstrap P(IC-weighted > equal-weight) on holdout
- Decision: use IC weighting in production candidate or not

**Acceptance tests:**
- IC-weighted ensemble Sharpe ≥ equal-weight Sharpe on 2020+ holdout
- Bootstrap P(IC-weighted > equal-weight on holdout) ≥ 0.65
- 2022 bear period protection maintained

**Reasons to reject/skip:**
- IC-weighted ensemble performs worse on holdout (documents IC weighting as not robust for this universe)
- Rolling IC estimates are too noisy to use (high instability in rolling IC → uninformative weights)

---

### Phase R6 — Meta-Labeling Confidence Score (3–5 sprint days, high risk)

**Why sixth (and labeled high risk):** Meta-labeling is theoretically powerful but has significant overfitting risk at this data scale (1110 weekly observations). This phase should only be attempted if R1–R5 are complete and the holdout results are stable.

**Note:** The ML lab already has meta-labeling scripts (`scripts/ml_lab/06_run_meta_labeling.py`, `scripts/ml_lab/11_run_triple_barrier_meta_labeling_and_drift.py`). This phase is about integrating those outputs into the allocation pipeline as a production-quality confidence score, not rewriting from scratch.

**Files to create:**
```
scripts/run_meta_signal_confidence_integration.py
    → load meta-labeling outputs from data/research/ml_lab/meta_labeling/
    → compute meta-confidence score per week (how confident is the meta-model?)
    → test: high-confidence weeks vs low-confidence weeks (forward return lift)
    → integrate as a multiplier on the offensive sleeve budget
    → validate on holdout 2020+ with bootstrap
    → output: docs/research/r6_meta_confidence_integration_report.md
```

**Acceptance tests:**
- High-confidence meta weeks show higher forward 4-week SPY return than low-confidence weeks
- Bootstrap P(high > low) ≥ 0.70 on holdout
- Integration improves Sharpe by ≥ +0.02 on holdout
- 2022 bear protection unchanged

**High overfitting risk mitigation:**
- Only use meta-model trained on pre-2020 data
- All evaluation on 2020+ holdout (never seen by the meta-model)
- Require bootstrap confidence interval for the improvement claim

**Reasons to reject/skip:**
- Meta-model confidence does not predict forward returns on holdout (common outcome with small samples)
- Integration adds complexity without clear Sharpe improvement
- 2022 protection degrades (critical guardrail)

---

### Phase R7 — PIT Stock Breadth (When Budget Available)

**Why seventh:** This is the highest-expected-value idea in the entire backlog, but requires data purchase. Do this phase when and only when Norgate US Stocks Platinum/Diamond (~$600–1200/yr) or WRDS/Sharadar is available.

**Prerequisite:** Budget decision by the user.

**Files already created (scaffold exists):**
```
scripts/build_pit_stock_breadth_panel.py  ← exists
data/stock_breadth/raw/                   ← scaffold exists (fill with Norgate files)
```

**Expected output:**
- Full PIT stock breadth signal back to 2005
- Calm_trend IC estimated to be +0.30–0.50% per 4 weeks (based on Phase 5A-Free biased diagnostic)
- If confirmed: build Phase 5B production candidate from Phase 4B base + breadth signal

**Acceptance test:**
- PIT breadth IC > biased estimate (Phase 5A-Free showed +0.347% per 4w for Phase 4B — expect lower with PIT correction)
- IC confirms positive in calm_trend with NW t-stat ≥ 2.0 over full period 2005–2026
- Candidate improves full-period return ≥ +0.10 pp over Phase 4B best

---

### Phase R8 — Final Comparison vs Production Baseline

**Why last:** Comprehensive comparison after all signal improvements are made. This is the "have we helped?" checkpoint.

**Files to create:**
```
docs/research/renaissance_pipeline_final_comparison_report.md
```

**Format:** Structured like existing phase reports. Full-period + holdout comparison vs all baselines.

---

## Section 8 — Final Recommendation

### Top 5 Highest-ROI Ideas

| Rank | Idea | Expected benefit | Implementation complexity | Data needed |
|------|------|----------------|--------------------------|-------------|
| 1 | **Orthogonal macro signals (yield curve, credit spread, VIX term structure)** | +0.01–0.04 Sharpe | Low | FRED free + existing VIX |
| 2 | **State-conditional IC testing** | Identifies signals for calm_trend; +0.01–0.03 Sharpe if one signal passes | Low–Medium | Existing data |
| 3 | **ETF pairs / cointegration signals** | Orthogonal to momentum; especially valuable in calm; +0.01–0.03 Sharpe | Medium | Existing ETF prices |
| 4 | **Signal decay half-life characterization** | Research efficiency; ensures only viable signals survive weekly rebalancing | Very low | Existing |
| 5 | **IC-weighted ensemble combination** | +0.01–0.02 Sharpe vs equal-weight | Low | Existing |

### Top 5 Ideas to Avoid

| Rank | Idea | Why to avoid |
|------|------|-------------|
| 1 | **Intraday / HFT adaptation of Renaissance techniques** | Not compatible with weekly ETF rebalancing; infrastructure mismatch |
| 2 | **1000+ signal ensemble** | With 1110 weekly observations and 35 ETFs, 1000 signals = pure overfitting; no diversification benefit |
| 3 | **Satellite imagery / weather / shipping alternative data** | Not actionable at weekly ETF frequency; not meaningful for liquid ETF allocation |
| 4 | **Black-box deep learning without clear IC gate** | ML lab already showed this — high complexity, fragile holdout performance |
| 5 | **Meta-labeling before R1–R5 complete** | Layering ML on top of fragile signal library adds compounding overfitting risk |

### What Should Be Implemented First

**R1 (Signal decay testing + research log) → R2 (Macro/VIX/volume signals) → R3 (State-conditional IC)**

This is the minimum viable Renaissance-inspired improvement: rigorous process documentation + orthogonal free data signals + regime-conditioned testing. Total: 6–9 sprint days.

### What Requires Better Data

| Idea | Data needed | Cost |
|------|-----------|------|
| PIT stock breadth (highest-value) | Norgate US Stocks Platinum/Diamond | $600–1200/yr |
| PIT stock breadth (budget alt.) | Sharadar via Nasdaq Data Link | $50–200/yr |
| Implied volatility term structure | CBOE data subscription | Moderate |
| Earnings/fundamental signals | Compustat via WRDS | Expensive |

### Can Any Idea Realistically Push to 10% Annual Returns Without Overfitting?

**Honest assessment: unlikely with existing ETF-only data, but possible with PIT stock breadth.**

Current ceiling: ~7.88% / 0.926 Sharpe (Phase 7 stretch, best shadow)  
Gap to 10%: 2.12 pp  

Expected incremental improvement from R1–R5 (no new paid data):  
- Best case: +0.15–0.30 pp (if 2–3 orthogonal signals are found with IC ≥ 0.05)  
- Realistic case: +0.05–0.15 pp (some signals pass, pairs add marginal edge)  
- Updated ceiling with R1–R5: ~8.0–8.2% / Sharpe 0.95–0.97

Expected incremental improvement with PIT stock breadth (Phase 5B):  
- Phase 5A-Free biased diagnostic: +0.35% per 4-week in calm_trend for Phase 4B  
- PIT-corrected (remove survivorship bias, conservative): +0.20% per 4-week  
- With 295 calm weeks at 26.6% frequency: +0.20% × 13 periods × 26.6% = ~0.70 pp annualized  
- Updated ceiling: ~8.7–9.0% / Sharpe ~0.95–1.00

**The 10% target requires either:**
1. PIT stock breadth + successful calm_trend signal integration (gets to ~9%) PLUS
2. A meaningful ETF pairs signal in calm_trend (+0.3–0.5 pp) PLUS
3. Macro signal contributions (+0.1–0.2 pp)

**10% is theoretically reachable but is not a safe planning assumption.** The more honest target: 8.5–9.0% with the full R1–R5 + Phase 5B stack, if all ideas survive validation. Any specific claim of 10%+ would require cherry-picking the best scenario.

---

## Summary of Files and Actions

### Files to create (research only)

| File | Phase | Purpose |
|------|-------|---------|
| `docs/research/signal_research_log.md` | R1 | Living idea log |
| `scripts/run_signal_decay_analysis.py` | R1 | Decay half-life per signal |
| `data/02_layer1_signals/signal_decay_profiles.csv` | R1 | Decay output |
| `scripts/build_macro_signal_library.py` | R2 | FRED yield curve, credit, NFCI |
| `scripts/build_vix_term_structure_signal.py` | R2 | VIX term structure → signal |
| `scripts/build_volume_divergence_signal.py` | R2 | ETF price × volume signal |
| `scripts/run_r2_signal_validation.py` | R2 | IC battery for new signals |
| `scripts/run_state_conditional_signal_ic.py` | R3 | IC by regime state |
| `scripts/build_etf_pairs_signals.py` | R4 | Cointegration pairs signals |
| `scripts/run_ic_weighted_ensemble_test.py` | R5 | IC vs equal-weight ensemble |
| `scripts/run_meta_signal_confidence_integration.py` | R6 | Meta-labeling integration |

### Files NOT to touch

- `scripts/build_improvement_artifacts.py` (strategy logic)
- `data/05_layer3_portfolio_construction/portfolio_version_*` (production artifacts)
- `public/` directory or dashboard
- Any production or shadow pin definitions
- `CLAUDE.md` strategy pins section

### Final git status expectation

After this research document sprint: three new markdown files in `docs/research/`. No code changes. No staged changes to strategy files. Git status shows these three files as untracked `??`.
