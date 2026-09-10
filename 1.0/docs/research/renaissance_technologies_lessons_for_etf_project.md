# Renaissance Technologies — Lessons for the ETF Quant Portfolio Project

**Date:** 2026-05-18  
**Type:** Research/analysis only. No code changes. No strategy changes. No production pin changes.  
**Production pin:** `improved_phase2b_regime_confidence_boost` (unchanged)

---

## Sources Reviewed

- Gregory Zuckerman, *The Man Who Solved the Market: How Jim Simons Launched the Quant Revolution* (2019, Portfolio/Penguin) — authoritative public account based on interviews with 400+ people
- Marcos López de Prado, *Advances in Financial Machine Learning* (2018, Wiley) — directly applicable methodology
- Jim Simons, MIT Sloan interview (2010): "Quant pioneer James Simons on math, money, and philanthropy" — https://mitsloan.mit.edu/ideas-made-to-matter/quant-pioneer-james-simons-math-money-and-philanthropy
- Renaissance Technologies Wikipedia article — https://en.wikipedia.org/wiki/Renaissance_Technologies
- AQR, "Value and Momentum Everywhere" — https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Factors-Monthly
- Gatev, Goetzmann, Rouwenhorst (2006), "Pairs Trading: Performance of a Relative-Value Arbitrage Rule" — Journal of Financial Studies
- Moreira & Muir (2017), "Volatility-Managed Portfolios" — Journal of Finance
- Hudson & Thames, "Meta-Labeling" research — https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/
- Markov Processes International (2007), "The Law of Large Numbers" — MPI Quant Research Series
- NavnoorBawa, "Renaissance Technologies: The $100 Billion Built on Statistical Arbitrage" — Substack
- Daniel Scrivner, "Renaissance Technologies Business Breakdown" — https://www.danielscrivner.com/renaissance-technologies-business-breakdown/
- Cointegration-based pairs trading study, 2000–2024, *Journal of Asset Management* — https://link.springer.com/article/10.1057/s41260-025-00416-0
- CBS Master Thesis, "Pairs Trading with ETFs Backtested from 2007-2020" — https://research.cbs.dk/files/62183889/903049_Master_thesis_Pairs_trading_on_ETFs.pdf

---

## Section 7 — Repo Inspection (Executed First)

The following repo files were inspected before writing this report.

### Layer 1 — Signals (data/02_layer1_signals/)

**22 signals tracked**, including:
- Price momentum: `tsmom_vol_scaled`, `xsmom_global`, `xsmom_asset_class_neutral`, `multi_mom_equal`, `multi_mom_invvol`
- Reversal: `reversal_1w_global`, `reversal_4w_global`, `reversal_1w_asset_class_neutral`, `reversal_4w_asset_class_neutral`
- Quality: `trend_clarity_momentum`, `moving_average_distance`, `breadth_confirmed_momentum`, `residual_momentum`, `contained_recovery_quality`
- Factor proxies: `bab_proxy`, `carry_proxy`, `value_proxy`, `quality_proxy` (all with asset-class-neutral variants)

**Infrastructure already in place:**
- `signal_manifest.json` — signal registry with definitions
- `signal_ic_by_horizon.csv` — IC across 1–13w horizons
- `signal_redundancy_matrix.csv` — pairwise signal redundancy
- `signal_incremental_contribution.csv` — marginal contribution to Sharpe
- `signal_summary_table.csv` — composite validation score per signal

**Top IC signals** (from signal_summary_table.csv):
- `multi_mom_equal`: IC t-stat NW = 2.90, validation score 3.65, recommendation: strong
- `xsmom_global`: IC t-stat NW = 2.83, validation score 3.59, recommendation: strong
- `moving_average_distance`: IC t-stat NW = 2.75, validation score 3.49, recommendation: strong

### Layer 2B — Regime Engine (data/04_layer2b_risk_regime_engine/)

Five states: `calm_trend`, `neutral_mixed`, `stressed_panic`, `recovery_fragile`, `recovery_confirmed`  
State history from 2005-01-07. Transition matrix computed. ML calibration exists (`phase_jj_ml_calibration.csv`).

### Layer 3 — Portfolio Construction (data/05_layer3_portfolio_construction/)

316 portfolio version return files. HRP-based construction with regime overlay.  
Production pin: GGG1 at ~7.14% / 0.936 Sharpe  
Best shadow: Phase 7 stretch at ~7.88% / 0.926 Sharpe

### Data Hub (data/01_data_hub/)

35 ETF universe: SPY, QQQ, IWM, EEM, EFA, EWJ, TLT, IEF, SHY, BIL, TIP, MBB, LQD, HYG, GLD, IAU, SLV, USO, DBA, PDBC, UUP, VNQ, XL{K,F,V,E,I,U,P,B,Y}, VUG, VTV, VEA, VWO  
Weekly returns from 2005. Macro data exists (`macro_weekly.csv`). VIX term structure. Google Trends.

### ML Lab (data/research/ml_lab/, scripts/ml_lab/)

Scripts 00–12 now exist. Most recent (07–12) are untracked. Outputs: tabular ML, neural networks, sequence models, transformers, meta-labeling. All marked experimental, high-overfitting-risk.

### Audit Infrastructure (scripts/)

`backtest_realism_audit.py`, `research_committee_report.py`, `allocator_benchmark_audit.py` all exist.

---

## Section 1 — Executive Summary

### What Renaissance Actually Teaches Us

Renaissance Technologies, under Jim Simons, built the most successful quantitative trading operation in history: the Medallion Fund returned ~66% gross / ~39% net annually from 1988–2018, with a Sharpe ratio reportedly between 4 and 5. The operation is almost entirely secret. What is publicly known comes from Zuckerman's *The Man Who Solved the Market* (2019) and a handful of Simons interviews.

The publicly documented core principles are:

1. **Start with data, not hypotheses.** Renaissance collected and cleaned every data source they could find before deciding what to trade. Simons: *"We don't start with models. We start with data."*
2. **Many small, independent signals beat one complex model.** Medallion likely ran hundreds or thousands of weak signals in a portfolio. Each signal was right only ~50.75% of the time, but ensemble diversification converted small edges into extraordinary Sharpe.
3. **Test ruthlessly. Reject most ideas.** By 1997, >50% of their signals were "nonintuitive" — they worked statistically but lacked a clear economic story. They ran them anyway, at limited size, while building understanding.
4. **Automate execution and remove human override.** Once live, no human interference. The system was sovereign.
5. **Manage risk at every level.** Kelly-criterion position sizing, hard position limits, automatic drawdown-triggered reductions.
6. **Extreme talent + collaborative culture.** PhDs from math, physics, computational linguistics, signal processing — not finance. No financial ego, only statistical evidence.

### What Is Realistic for This ETF Project

The ETF project cannot replicate Renaissance. Full stop. But these principles can be adapted:

| Principle | Adaptation | Verdict |
|-----------|-----------|---------|
| Many weak signals | Expand signal zoo from 22 to 50+ with explicit IC and redundancy testing | **Realistic** |
| Rigorous validation factory | Already partially built; extend to decay testing, regime-conditional IC, cost testing | **Realistic** |
| Data-first discovery | Add yield curve, credit spread, implied vol, macro features as new signal inputs | **Realistic** |
| Signal ensemble | Improve signal weighting (beyond equal-weight or simple rank); test IC-weighted ensemble | **Realistic** |
| Remove human discretion | Already done — the project is fully systematic | **Already done** |
| Risk management | Add Kelly-inspired position sizing within the offensive sleeve | **Realistic** |
| Regime-conditioned signal weights | Test whether signal ICs vary by regime state; use regime as a meta-feature | **Realistic** |
| Pairs / statistical arbitrage | ETF pairs lab using cointegration of SPY/QQQ/IWM/sector ETFs | **Realistic (limited)** |
| Meta-labeling | Secondary ML classifier on existing signals — ML lab already has this | **Realistic** |

### What Is Unrealistic

| Item | Why |
|------|-----|
| Medallion-level Sharpe (4–5) | Impossible at weekly ETF frequency with 35 instruments. They trade thousands of instruments at tick speed. |
| HFT / intraday execution | Not compatible with weekly ETF rebalancing |
| Petabytes of alternative data | Satellite imagery, shipping logs, weather data are not available or actionable at weekly ETF resolution |
| 1000+ signal ensemble | With 35 ETFs and weekly data, the effective sample is N=1110 weeks, making 1000 signals meaningless without data leakage |
| True statistical arbitrage at scale | Requires microsecond execution and market-making infrastructure |
| Accurate cloning of their models | Entirely secret; anything specific is speculation |
| 66% annual gross returns | Requires short-term edge from microstructure and ultra-frequent rebalancing |

**Honest ceiling assessment:** With 35 ETFs, weekly rebalancing, and ~1110 weekly observations back to 2005, the project is operating in a data-limited regime where Renaissance principles can improve *process quality* but will not unlock Medallion-level returns. The current ceiling without PIT stock data appears to be ~7.9% annual / Sharpe ~0.93–0.96. Renaissance-inspired pipeline improvements could realistically push this toward 8.5–9% with careful, validated signal additions — but 10%+ would require either (a) PIT stock breadth data, (b) a fundamentally different asset universe, or (c) higher rebalancing frequency.

---

## Section 2 — Transferable Lessons

### Lesson 1 — Many Small, Independent Signals > One Complex Model

**Renaissance principle:** Medallion likely ran hundreds of signals, each contributing a marginal Sharpe edge of ~0.01–0.05. The diversification of independent bets lowered variance proportionally to √N. Individual signal accuracy was ~50.75% — far below what discretionary traders would consider worth trading.

**ETF project adaptation:** The current signal library has 22 signals with significant redundancy (the `signal_redundancy_matrix.csv` shows `breadth_confirmed_momentum` and `moving_average_distance` have pairwise redundancy of 0.822 — very high). The project needs more *orthogonal* signals, not more redundant ones.

Specific actions:
- Add yield curve slope (10Y-2Y) as an explicit signal — currently absent from signal manifest
- Add credit spread level (HYG spread vs IG) as a distinct signal
- Add currency carry explicitly (DXY direction, UUP momentum)
- Add commodity carry (PDBC vs USO momentum spread, contango proxy)
- Add ETF volume-price divergence (price up + volume down = weakness signal)
- Add implied volatility term structure (VIX term structure is already fetched; use it as signal)

**Expected benefit:** +0.01–0.04 Sharpe improvement per orthogonal signal added, if ICs clear the ≥0.05 hurdle with NW t-stat ≥ 2.0.

**Implementation difficulty:** Low–Medium. The signal infrastructure already exists.  
**Overfitting risk:** Medium. Each new signal must clear the existing IC pipeline with walk-forward NW t-stat. No cherry-picking.  
**Data requirements:** FRED (free), existing VIX term structure data (already fetched).

---

### Lesson 2 — Signal Decay Testing

**Renaissance principle:** Signals were tracked for *how long they stayed valid*, not just whether they worked. Short-horizon signals require faster execution; longer-horizon signals are more robust for slower funds.

**ETF project adaptation:** The current `signal_ic_by_horizon.csv` tracks IC at 1, 2, 4, 8, 13 weeks. The decay rate is not explicitly characterized. Adding a decay half-life estimate per signal would tell the portfolio: which signals are still predictive at 4 weeks? Which die by week 2?

At weekly rebalancing, only signals with IC half-life ≥ 3 weeks are worth trading (shorter decay means the signal is stale before the portfolio rebalances).

**Expected benefit:** Removes signals that look good at 1-week IC but are dead by the actual rebalancing horizon, reducing false confidence in short-decay signals.  
**Implementation difficulty:** Low. Fit an exponential decay to the IC-by-horizon curve for each signal.  
**Overfitting risk:** Low. This is diagnostic, not a parameter fit.  
**Data requirements:** Existing signal_ic_by_horizon.csv.

---

### Lesson 3 — Regime-Conditional Signal Weights

**Renaissance principle:** Not explicitly public, but the ensemble approach implies signals are not equally weighted at all times. Statistical regime awareness is standard in advanced quant shops.

**ETF project adaptation:** The project's regime engine (5 states) is a genuine differentiator. The current signal library is tested at the full-period aggregate. It does not test IC *within state*. This is a potentially large gap: a signal that has IC = 0.05 full-period might have IC = 0.12 in `calm_trend` and IC = -0.03 in `stressed_panic`. Using this information for regime-conditional signal weighting could substantially improve signal quality in the states that matter most.

The `signal_state_summary.csv` already computes state-by-state signal diagnostics. The question is whether the regime-conditional ICs are stable enough to use for weighting.

**Expected benefit:** If even 2–3 signals show strong state-conditional IC patterns (IC > 0.10 in one state), the portfolio could weight them higher during those states — targeting the return gap in `calm_trend` without using PIT stock data.  
**Implementation difficulty:** Medium. Requires computing state-masked IC and ensuring no lookahead (signal at t-1 predicts return at t, masked by state known at t-1).  
**Overfitting risk:** Medium-High. State frequency is low (295 calm weeks, 44 recovery_confirmed weeks), so state-specific IC estimates have wide confidence intervals.  
**Data requirements:** Existing.

---

### Lesson 4 — Orthogonality Enforcement in the Signal Portfolio

**Renaissance principle:** Simons's team explicitly tested for redundancy and suppressed it. Adding a signal that was 90% correlated with an existing one added almost nothing to the ensemble Sharpe — the `1/√N` diversification benefit only applies to *independent* bets.

**ETF project adaptation:** The `signal_redundancy_matrix.csv` shows high pairwise redundancy among the momentum family:
- `breadth_confirmed_momentum` ↔ `moving_average_distance`: 0.822
- `breadth_confirmed_momentum` ↔ `multi_mom_equal`: 0.837
- `breadth_confirmed_momentum` ↔ `multi_mom_invvol`: 0.837
- `xsmom_global` ↔ `multi_mom_invvol`: 0.81 (estimated)

The `bab_proxy` and `carry_proxy` are the most orthogonal signals (near-zero or negative correlation with the momentum cluster). The `incremental_contribution.csv` confirms this: adding `bab_proxy` to the base 4-signal portfolio raises Sharpe from 0.583 to 0.734 (+0.151), the largest single-signal improvement.

**Action:** Any new signal proposed for production must pass a redundancy threshold: pairwise Pearson correlation ≤ 0.5 with existing strong signals. Signals above this threshold should be rejected or treated as sub-variants of existing signals.

**Expected benefit:** Prevents the signal library from growing in number but not in diversity.  
**Implementation difficulty:** Very low (already computed).  
**Overfitting risk:** Very low (diagnostic).  
**Data requirements:** Existing.

---

### Lesson 5 — Kelly-Criterion-Inspired Position Sizing

**Renaissance principle:** Medallion used Kelly position sizing — allocate proportionally to (edge / variance), capped to prevent ruin. This maximizes long-run geometric growth rate.

**ETF project adaptation:** The current HRP construction implicitly uses inverse-variance weighting, which is related to fractional Kelly. The project could make this explicit by:
- Computing per-signal IC as an estimate of "edge"
- Using IC²/variance as the Kelly-inspired weight for each signal
- Applying a Kelly fraction (e.g., 0.25× full Kelly) for conservatism

In the sleeve framework, this would translate to: increase the offensive sleeve budget in states where the regime engine has high signal IC, reduce it when IC is low.

**Expected benefit:** Better calibration of offense budget to regime quality. When the regime engine is highly confident (high `transition_good_state_prob`) AND the leading signals have high IC, allow more offense. When uncertain, be more conservative.  
**Implementation difficulty:** Medium. Requires IC estimates per-period and per-state.  
**Overfitting risk:** Medium. IC estimates are noisy at short windows.  
**Data requirements:** Existing.

---

### Lesson 6 — Data-First, Hypothesis-Second

**Renaissance principle:** Renaissance did not require an economic story before testing a signal. They tested first; hypotheses followed the data. They ran "nonintuitive" signals at reduced size while building understanding.

**ETF project adaptation:** The current project has a bias toward causal, interpretable signals (consistent with the CLAUDE.md mandate). This is good for production robustness. However, there is room to explore a few data-driven signals that don't have an obvious story but have empirical grounding:
- VIX term structure shape (front vs. back month — contango vs. backwardation)
- ETF volume anomalies (volume spikes on falling prices)
- Cross-asset divergence (equities making new highs while credit spreads widen — internal stress signal)

Each would be added to the "research only" track with strict IC gating before any production consideration.

**Expected benefit:** Potentially finds signals the current hypothesis-first approach misses.  
**Overfitting risk:** High if not gated. Medium if gated at IC NW t-stat ≥ 2.0.  
**Data requirements:** VIX term structure (already fetched), ETF volume (available via yfinance).

---

### Lesson 7 — Meta-Labeling for Signal Confidence

**Renaissance principle:** Not directly documented, but the ensemble approach implies some form of confidence scoring — not all signals are treated equally in every market state.

**ETF project adaptation:** The ML lab already has meta-labeling scripts (`scripts/ml_lab/06_run_meta_labeling.py`, `scripts/ml_lab/11_run_triple_barrier_meta_labeling_and_drift.py`). The core idea: train a secondary classifier to predict *when* the primary signal is likely to be correct. The primary signal says "go long equities"; the meta-classifier says "this is a high-confidence week for that signal."

The Lopez de Prado framework uses:
1. Primary model → direction (side)
2. Meta-model → probability of success (size)

Applied to this project: regime engine → state label; meta-classifier → probability that the signal's direction is correct in this state. Reduce position when meta-classifier confidence is low.

**Expected benefit:** If meta-labeling can identify the top 30% of signal weeks where the signal is most likely correct, and the project over-weights those weeks, the Sharpe improvement could be meaningful (+0.05–0.10).  
**Implementation difficulty:** High. ML lab has the code; integration into Layer 3 requires careful lookahead prevention.  
**Overfitting risk:** High. Must validate on holdout only.  
**Data requirements:** Existing (ML lab outputs).

---

### Lesson 8 — Research Culture: Peer Review and No Sacred Cows

**Renaissance principle:** Simons explicitly fostered a culture where any idea could be challenged and any signal could be dropped if the evidence warranted. No one "owned" a signal.

**ETF project adaptation:** The project already has a strong governance framework (dual-track pins, bootstrap testing, pre-declared holdouts). The missing piece is a formal *idea log* — a record of every idea tested, why it was accepted or rejected, and what evidence drove the decision. This prevents re-testing ideas that already failed and provides a public record of research integrity.

**Expected benefit:** Research efficiency, not return improvement.  
**Implementation difficulty:** Very low (just documentation).  
**Overfitting risk:** Zero.  
**Data requirements:** None.

---

## Section 3 — Data Ideas We Can Copy Safely

### Free and Accessible

| Data | Source | Cost | PIT Risk | Survivorship Risk | How it helps |
|------|--------|------|----------|------------------|-------------|
| Yield curve (10Y-2Y, 10Y-3M) | FRED (free API) | Free | None | None | Regime indicator; 10Y-2Y inversion precedes recession; current project uses `macro_weekly.csv` but yield curve slope is not a first-class signal |
| Credit spreads (HYG OAS, LQD OAS) | FRED (ICE BofA OAS series) | Free | None | None | Risk-off signal; credit spreads widening → stressed state approaching; already partially captured via HYG returns but not OAS level/change |
| VIX term structure slope | CBOE (already fetched) | Free | None | None | Contango = calm; backwardation = stressed; already fetched as `vix_term_structure.csv` but not converted to a signal |
| FRED financial conditions index (NFCI) | FRED | Free | 1-week | None | Composite macro stress indicator; tighter conditions → reduce offense |
| Commodity carry proxy | PDBC/USO/DBA price ratio | Free (yfinance) | None | None | Contango/backwardation proxy for commodity markets |
| Currency momentum | UUP weekly momentum | Free (already in universe) | None | None | USD strength → risk-off global signal; currently in universe but not used as explicit signal |
| ETF volume divergence | yfinance (already accessed) | Free | None | None | Price up + volume down = weak breadth; price down + volume up = distribution/panic |
| Google Trends fear | Already fetched | Free | None | None | `google_trends.csv` exists but integration into signal library unclear |

### Available but Requires More Work

| Data | Source | Cost | Notes |
|------|--------|------|-------|
| PIT stock breadth (S&P 500 % above 200d MA) | Norgate / WRDS | ~$600–$1200/yr | Identified as the #1 missing signal for calm_trend; Phase 5A-Free prototype built; requires purchase |
| Implied volatility surface (SPX/VIX options) | CBOE data (subscription) | Moderate | Term structure of implied vol is a refined signal; VIX/VVIX ratio available free from CBOE |
| AAII sentiment survey | AAII weekly (free with registration) | Free | Contrarian sentiment signal; weekly, no survivorship bias |
| COT (Commitments of Traders) | CFTC (free) | Free | Futures positioning data; available for gold, oil, currencies; potential carry signal |
| Recession probability | FRED (Smoothed recession probability) | Free | Binary/probabilistic macro overlay; Sahm Rule also available |

### Realistic Priority Order (No Paid Data)

1. **VIX term structure slope signal** — data already fetched, just needs signal conversion
2. **Yield curve 10Y-2Y slope signal** — FRED free, not yet a first-class signal
3. **Credit spread level/change** — FRED free (HYG OAS series BAMLH0A0HYM2)
4. **ETF volume divergence signal** — volume data available via yfinance; add to expanded universe script
5. **FRED NFCI composite** — weekly financial conditions index, free
6. **COT positioning data** — free from CFTC, could enhance carry signal

---

## Section 4 — Strategy Ideas Inspired by Renaissance

### Idea 1 — Expanded Signal Zoo (Most Realistic)

Add 6–10 orthogonal signals to the existing library, testing each with the established IC pipeline. Focus on signals from factor families not yet represented:

- Yield curve carry signal (10Y-2Y slope → predict bond vs equity allocation)
- Credit spread level signal (BAMLH0A0HYM2 → stress regime predictor)
- VIX term structure signal (front-back spread → calm vs stress)
- Cross-asset divergence signal (SPY trend ≠ HYG trend → internal stress)
- Dollar carry signal (UUP 13w momentum → risk-off overlay)
- Commodity momentum (PDBC 26w momentum → growth/reflation signal)

**Priority:** High. Directly actionable with free data.

---

### Idea 2 — ETF Pairs / Statistical Arbitrage Lab

Based on the literature (CBS Thesis 2007-2020, Journal of Asset Management 2000-2024), cointegration-based pairs trading with ETFs has shown:
- Positive Sharpe (0.8–1.5 depending on implementation)
- Annual returns of 10–15% for a full pairs portfolio
- Works well during stress periods when individual momentum signals fail

For this project, relevant pairs to explore:
- SPY/QQQ (large cap vs tech)
- IWM/SPY (small vs large cap value spread)
- TLT/SPY (duration/equity yield spread)
- GLD/TLT (real vs nominal safe haven)
- XLE/USO (energy equity vs commodity basis)
- XLK/QQQ (tech sector vs tech index — there's a basis here)

**What this adds:** A *mean-reversion* signal family that is structurally orthogonal to the existing *momentum* family. When momentum is weak (calm markets, neutral periods), mean-reversion tends to work. This could specifically address the `calm_trend` bottleneck.

**Constraints:**
- At weekly frequency, pairs signals have IC half-lives of 2–4 weeks — viable for weekly rebalancing
- Transaction costs must be modeled — pairs trading requires simultaneous long/short, but ETFs can be traded cheaply
- The ETF pairs signal would feed the *existing* signal framework as another Layer 1 signal — not a separate strategy

**Priority:** Medium-High. Requires a new pairs research script.

---

### Idea 3 — Ensemble Signal Weighting (IC-Weighted vs Equal-Weight)

Current signal combination is implicitly equal-weight or HRP-based. Renaissance suggests ensemble weighting based on signal quality. The IC-weighted combination is:

```
w_i = IC_i / sum(IC_j)
```

Or more robustly: IC-Square-Root-Weighted (ICS):

```
w_i = sqrt(IC_i) / sum(sqrt(IC_j))
```

Applied to this project: the existing `signal_summary_table.csv` has composite validation scores. Using these scores to weight signals in the Layer 2 combination could improve the ensemble Sharpe vs equal-weighting.

**Expected benefit:** Small but robust. Literature suggests IC-weighted combinations improve ensemble Sharpe by 5–15% vs equal-weight.

**Priority:** Medium. Small code change with measurable impact.

---

### Idea 4 — Short-Horizon Reversal as a Separate Signal Class

Reversal signals are already in the library (`reversal_1w_global`, `reversal_4w_global`) but the `incremental_contribution.csv` shows that adding `reversal_4w_global` to the core portfolio **reduced Sharpe** (from 0.583 to 0.497, −0.086). This is a known issue: reversal signals work in isolation but often hurt momentum portfolios.

The Renaissance-inspired fix: use reversal signals *only in specific regimes* (e.g., only in `stressed_panic` recovery windows, or only in `recovery_fragile`). Suppressing reversal in `calm_trend` prevents the momentum/reversal conflict.

**Priority:** Medium. Requires regime-conditional signal switching (already partially implemented via state tilts).

---

### Idea 5 — Transaction-Cost-Aware Signal Scoring

Renaissance modeled execution costs explicitly and rejected signals whose gross edge did not survive realistic transaction costs. The current project reports `ann_return_10bps` (net of 10bps cost assumption). This is one-size-fits-all.

ETF bid-ask spreads vary: BIL has 1bp spread; HYG might be 5–10bps; emerging market ETFs (EEM, VWO) can be 15–25bps. A signal that looks good at 10bps flat may be worse than expected for the high-spread ETFs.

**Action:** Compute per-ETF cost estimates from yfinance bid-ask or use published ETF cost data. Run net-of-cost IC separately for each ETF in the universe.

**Priority:** Low-Medium. Diagnostic improvement; unlikely to change top signals.

---

## Section 5 — Research Pipeline Proposal

A Renaissance-inspired research factory for this project. This extends and formalizes the existing pipeline.

### Stage 1 — Idea Intake

**Format:** A research log entry for every idea, with:
- Name, date, hypothesis (if any), data sources required
- Pre-registration of acceptance threshold (IC NW t-stat ≥ 2.0, redundancy < 0.50 vs existing)
- Assign category: momentum / reversal / carry / value / quality / macro / breadth / sentiment / pairs

**Output:** `docs/research/signal_research_log.md` — living document

---

### Stage 2 — Feature Creation

- All features computed from lagged data only (lag=1 week minimum)
- No look-ahead: signal at t uses only data available at t-1 or earlier
- Saved to `data/02_layer1_signals/` with consistent naming convention
- Leakage audit: new `data_leakage_auditor` agent run on every new signal script

---

### Stage 3 — IC Testing

Standard battery:
1. Full-period IC + NW t-stat at 1, 2, 4, 8, 13 weeks
2. Holdout IC (2020-forward) must be positive with p ≤ 0.20
3. State-conditional IC by regime (optional but encouraged)
4. IC half-life estimate (decay to 50% of peak IC)

**Promotion gate:** NW IC t-stat ≥ 2.0 full-period AND holdout IC positive

---

### Stage 4 — Redundancy Testing

- Compute pairwise Pearson correlation vs all existing signals in the library
- Max allowed redundancy: 0.50 vs any existing "strong" signal
- If redundant: either drop or designate as a sub-variant; never add both

---

### Stage 5 — Incremental Contribution

Run `signal_incremental_contribution` test:
- Does adding this signal improve Sharpe vs the current best 4-signal baseline?
- Does it improve Sharpe in at least 2 of the 4 holdout windows (2016+, 2020+, 2021+, 2022 bear)?

**Promotion gate:** Δ Sharpe > 0 in at least 2 holdout windows

---

### Stage 6 — Walk-Forward Testing

Use time-ordered splits (no random shuffling):
- Train on first 60%, validate on next 20%, test on last 20%
- Block bootstrap: 13-week blocks, 2000 iterations
- Check P(signal > 0 IC on test set) ≥ 0.65

---

### Stage 7 — State-by-State Testing

For each signal, compute state-conditional statistics:
- IC per state (calm_trend, neutral_mixed, stressed_panic, recovery_fragile, recovery_confirmed)
- Note if signal is positive in stressed_panic (potential to hurt protection)
- Flag signals with IC > 0.10 in calm_trend (highest value state)

---

### Stage 8 — Transaction Cost Testing

- Apply per-ETF cost estimates (flat 10bps base, higher for EM/commodity ETFs)
- Test whether net-of-cost Sharpe remains positive
- Compute break-even cost level (at what bps does the signal become unprofitable?)

---

### Stage 9 — Robustness / Stress Testing

Run the signal portfolio through:
- 2008 crisis period
- 2020 COVID crash
- 2022 inflation/rate shock
- Any period where the signal's IC flipped negative (identify fragility dates)

---

### Stage 10 — Promotion / Rejection Decision

Three tiers:
- **Promote to Layer 1:** Full IC battery passed + holdout positive + non-redundant
- **Research only:** IC positive but holdout weak; keep in research log; revisit after more data
- **Reject:** IC negative full-period OR signal increases stressed_panic losses OR pure data mining

Every decision logged in `docs/research/signal_research_log.md`.

---

### Stage 11 — Research Log / Report Generation

Each signal sprint produces:
- A markdown research note (following `docs/research/ml_lab/` style)
- A CSV of key metrics
- A decision record with verdict and rationale

This creates the "research audit trail" that Renaissance's culture required: every idea tested, every result documented, no sacred cows.

---

## Final Note

This is a research-and-roadmap document. No code has been changed. No production pins have been modified. All findings are based on public sources cited above.
