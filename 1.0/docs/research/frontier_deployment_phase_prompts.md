---
editor_options: 
  markdown: 
    wrap: 72
---

# Frontier Deployment Intelligence — Phase Implementation Prompts

**Document version:** 2026-05-20\
**Purpose:** Ready-to-use implementation prompts for each frontier
phase\
**Note:** These prompts are designed to be self-contained. Each can be
given directly to a coding assistant to start a sprint.

------------------------------------------------------------------------

## Pre-Phase Checklist (Run Before Any Sprint)

Before starting any frontier phase sprint, confirm:

```         
1. pwd — confirm you are in the Portfolio Optimizer working directory
2. git status — check for uncommitted changes
3. git branch — confirm main branch (no active worktree)
4. python scripts/test_allocator_checkpoint_wrapper.py — verify wrapper reproduces GGG
5. python scripts/run_deployment_rule_harness.py — verify rule harness baseline is clean
```

If any of these fail, stop and investigate before proceeding.

------------------------------------------------------------------------

## Phase 0: Stabilization Confirmation

**Status:** COMPLETED. See
`docs/research/deployment_architecture_stabilization_summary.md`.

To re-verify at any time:

```         
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py
.venv/bin/python scripts/run_deployment_rule_harness.py
```

Expected: net-return max error \< 1e-10, return correlation = 1.0000.

------------------------------------------------------------------------

## Phase 1: Deployment-State Intelligence Map

### Prompt 1A: State Quality Signals

> You are implementing Frontier Phase 1 of this ETF portfolio research
> project. The goal is to build a deployment-state quality composite — a
> principled, causal, 1-week-lagged score that answers "how good is the
> current market state?" beyond just the state label.
>
> Context: - The production pin is
> `improved_phase2b_regime_confidence_boost` - The stabilized wrapper in
> `scripts/allocator_checkpoint_wrapper.py` reproduces exact GGG
> returns - All work in this phase is diagnostic-only: read-only
> checkpoints, no production file modifications - Market state labels
> are in `data/03_layer2_strategy/market_state_history.csv` - Existing
> breadth signals are in `data/02_layer1_signals/`
>
> Implement `scripts/phase_frontier1_state_quality_signals.py` that:
>
> 1.  Loads market state history and existing Layer 1 breadth/momentum
>     signals
>
> 2.  Computes six causal state quality features (all 1-week lagged, no
>     look-ahead):
>
>     -   `breadth_quality_score`: fraction of offensive ETFs above both
>         50-day and 200-day MA (requires computing rolling averages
>         from raw ETF prices in `data/01_raw/`)
>     -   `path_clarity_r2`: 13-week R² of SPY price path vs linear
>         trend (rolling OLS)
>     -   `state_persistence_score`: consecutive weeks in current market
>         state label (capped at 12)
>     -   `credit_confirmation`: HYG 4-week momentum direction minus LQD
>         4-week momentum direction (sign of HYG/LQD spread tightening)
>     -   `leadership_quality_score`: fraction of offensive ETFs (SPY,
>         QQQ, XLK, XLY, XLI, IWM, VWO, EFA) in top half of 13-week
>         momentum ranking
>     -   `deployment_quality_composite`: z-scored equal-weighted blend
>         of above (winsorized at [-3, 3])
>
> 3.  Outputs to
>     `data/research/frontier_phase1/state_quality_signals.csv` with
>     columns: date, breadth_quality_score, path_clarity_r2,
>     state_persistence_score, credit_confirmation,
>     leadership_quality_score, deployment_quality_composite
>
> 4.  Runs an IC analysis: for each market state label, compute the
>     Spearman IC between `deployment_quality_composite[t]` and
>     `SPY_4w_forward_return[t+1..t+4]`. Report IC by state to stdout.
>
> Do NOT modify any production files, dashboard files, `public/`, or
> `src/` directories. Do NOT use any forward-looking data in signal
> computation. Use 1-week lag on all signals.

------------------------------------------------------------------------

### Prompt 1B: Wrapper Diagnostic Experiment

> Using the `deployment_quality_composite` computed in Phase 1A,
> implement `scripts/phase_frontier1_wrapper_diagnostic.py` that:
>
> 1.  Loads the allocator_checkpoint_wrapper (read-only mode)
> 2.  Loads `data/research/frontier_phase1/state_quality_signals.csv`
> 3.  Builds a quality-scaled modifier: when `market_state` is NOT
>     `stressed_panic`, scale the `offense_budget` checkpoint by
>     `(1 + 0.08 × clip(deployment_quality_composite, -1, 1))`. Do not
>     touch the `stressed_panic` rows.
> 4.  Runs the wrapper with and without the modifier
> 5.  Reports: full-history Sharpe, max DD, CVaR 5%, annual return,
>     recovery-confirmed capture, stressed-panic Sharpe, average BIL
>     weight, and turnover — for both the modifier and baseline GGG
> 6.  Outputs a comparison CSV to
>     `data/research/frontier_phase1/wrapper_diagnostic_results.csv`
> 7.  Writes a markdown report to
>     `docs/research/frontier_phase1_deployment_state_intelligence_report.md`
>
> Include state-by-state return comparison (all 6 states). Update
> `docs/research/project_journey.md` with a new section summarizing
> findings.
>
> The report must include: - IC results by state - Full-history vs
> holdout (last 104 weeks) comparison - Rolling-origin diagnostic
> (104-week windows) - Verdict: Research-only / Promote / Conditional
> based on IC gates (IC \> 0.05 in at least 2 states, bootstrap P \>
> 0.70)
>
> Do NOT modify production files.

------------------------------------------------------------------------

### Phase 1 Acceptance Gate Checklist

After running Phase 1B, evaluate: - [ ] IC of composite \> 0.05 in at
least 2 states (annualized, sign-consistent) - [ ] Monotonicity: forward
return increases Q1→Q5 in at least 3 of 5 states - [ ] Bootstrap P(IC \>
0) ≥ 0.70 - [ ] Wrapper diagnostic shows full-history Sharpe improvement
≥ +0.01 vs GGG - [ ] No meaningful increase in BIL/cash drag - [ ]
Stressed-panic Sharpe unchanged or better

If all gates pass → proceed to Phase 2 and use quality composite as
shared input. If IC gates fail → revise composite construction before
proceeding.

------------------------------------------------------------------------

## Phase 2: Trend / Setup Quality Engine

### Prompt 2A: Per-ETF Trend Quality Signals

> You are implementing Frontier Phase 2 of this ETF portfolio research
> project: building per-ETF trend quality scores.
>
> Context: - Phase 1 is complete and
> `data/research/frontier_phase1/state_quality_signals.csv` is
> available - All work is diagnostic-only initially - The production pin
> and all production files are UNCHANGED
>
> Implement `scripts/phase_frontier2_trend_quality_signals.py` that:
>
> 1.  For each ETF in the universe (use the 35-ETF list from
>     `data/01_raw/`):
>
>     -   `trend_r2_score[ticker]`: 52-week rolling R² of price vs
>         linear trend (OLS), 1w lag
>     -   `whipsaw_probability[ticker]`: fraction of 26-week rolling
>         windows with 4w momentum sign reversals
>     -   `trend_persistence_weeks[ticker]`: consecutive weeks with
>         positive 13w momentum (capped at 26, reset to 0 when
>         negative), 1w lag
>     -   `ma_distance_z[ticker]`: z-scored (within ticker history)
>         distance of current price from 52-week MA, 1w lag
>     -   `multi_window_agreement[ticker]`: 0, 1, 2, or 3 based on how
>         many of {13w, 26w, 52w momentum} are positive, 1w lag
>
> 2.  Builds a per-ETF composite:
>     `trend_quality[ticker] = (trend_r2 + (1-whipsaw) + multi_window_agreement/3) / 3`
>
> 3.  Computes cross-sectional IC of `trend_quality` vs next-week ETF
>     excess return (vs SPY)
>
> 4.  Outputs panel CSVs to `data/research/frontier_phase2/`:
>
>     -   `trend_quality_panel.csv` (date × ETF_ticker)
>     -   `trend_quality_ic_results.csv` (IC by state, IC by ETF)
>
> 5.  Validates that trend quality is not simply a restatement of recent
>     momentum: compute partial correlation of trend quality vs
>     next-week return after controlling for 13w and 26w momentum.
>     Report partial correlation to stdout.
>
> All signals must be 1-week lagged. No look-ahead. No production files
> modified.

------------------------------------------------------------------------

### Prompt 2B: Trend Quality Wrapper Experiment

> Using the per-ETF trend quality panel from Phase 2A, implement
> `scripts/phase_frontier2_wrapper_experiment.py` that:
>
> 1.  Builds a modifier at the `offense_budget` checkpoint: within each
>     offensive sleeve's top-N selection, multiply raw scores by
>     `(0.5 + 0.5 × trend_quality[ticker])` before ranking. Effectively
>     downweights low-quality-trend ETFs in the offense selection.
>
> 2.  Alternatively (test both): build a blend where
>     `combined_score = 0.70 × momentum_score + 0.30 × trend_quality_score`
>     for ETF selection within offensive sleeves.
>
> 3.  Runs wrapper diagnostic comparing:
>
>     -   GGG baseline (no modifier)
>     -   Phase 1 quality modifier alone
>     -   Phase 2 trend quality modifier alone
>     -   Phase 1 + Phase 2 combined modifier
>
> 4.  Reports the full Phase D metric table (all 8 gates) for all four
>     candidates on full-history AND pre-declared holdout (last 104
>     weeks).
>
> 5.  Outputs to `data/research/frontier_phase2/` and writes
>     `docs/research/frontier_phase2_trend_quality_engine_report.md`.
>
> 6.  Updates `docs/research/project_journey.md`.
>
> Do NOT modify production files.

------------------------------------------------------------------------

## Phase 3: Smart Re-Risking Engine

### Prompt 3A: Recovery Quality Score and Re-Risk Modifier

> You are implementing Frontier Phase 3: smart re-risking based on
> recovery quality.
>
> Context: - Phase 1 deployment quality composite is available at
> `data/research/frontier_phase1/state_quality_signals.csv` - Phase 2
> trend quality panel is available at
> `data/research/frontier_phase2/trend_quality_panel.csv` - The
> production pin's recovery-confirmed capture is approximately 57%; the
> goal is to improve this - CONSTRAINT: The stressed_panic defense must
> NOT be weakened by any change in this phase
>
> Implement `scripts/phase_frontier3_smart_rerisk_engine.py` that:
>
> 1.  Builds a `recovery_quality_score` from Phase 1 sub-signals:
>
>     -   Weighted:
>         `0.35 × breadth_quality + 0.25 × credit_confirmation + 0.25 × state_persistence + 0.15 × leadership_quality`
>     -   Scaled to [-1, +1] range
>
> 2.  Builds a `transition_quality_score`: was the recovery fast
>     (V-shape: \<= 8 weeks from stressed to recovery_confirmed) or slow
>     (grinding: 12+ weeks)? V-shape = lower confidence; grinding with
>     confirmation = higher confidence. Simple binary: `1` if
>     consecutive recovery weeks \>= 6, `0` otherwise.
>
> 3.  Creates a `rerisk_speed_modifier` time series:
>
>     -   In `recovery_confirmed` or `recovery_fragile`:
>         `base_speed × (1 + 0.20 × recovery_quality_score × transition_quality_score)`
>     -   In `stressed_panic`: ALWAYS 0 (NO re-risking during stress,
>         unconditional)
>     -   All other states: `base_speed` unchanged
>
> 4.  Applies the modifier to the `transition_rerisk_smoothing`
>     checkpoint (using the allocator wrapper)
>
> 5.  Reports: recovery-confirmed capture (before and after),
>     recovery-fragile capture, stressed-panic Sharpe (must be
>     unchanged), full-history Sharpe, holdout Sharpe, turnover delta
>
> 6.  Outputs to `data/research/frontier_phase3/` and writes
>     `docs/research/frontier_phase3_smart_rerisk_engine_report.md`
>
> Do NOT modify production files. Do NOT weaken stressed_panic defense
> under any circumstances.

------------------------------------------------------------------------

## Phase 4: Cross-Sectional Leadership System

### Prompt 4A: Leadership Signal Construction

> You are implementing Frontier Phase 4: a cross-sectional leadership
> system for the ETF portfolio.
>
> Implement `scripts/phase_frontier4_leadership_signals.py` that
> computes 5 causal leadership signals, all 1-week lagged, from existing
> ETF price data:
>
> 1.  `leadership_breadth`: fraction of offensive ETFs (SPY, QQQ, XLK,
>     XLY, XLI, XLF, XLE, IWM, VWO, EFA) where 13w momentum is in the
>     top half of all 35 ETFs
>
> 2.  `leadership_concentration`: Herfindahl-Hirschman Index of 13w
>     momentum rank distribution among the 10 offensive ETFs (high HHI =
>     narrow leadership = fragile)
>
> 3.  `leadership_type_quality`: (mean rank of quality-growth ETFs: QQQ,
>     XLK, QUAL, VUG) minus (mean rank of speculative ETFs: HYG, IWM,
>     VWO) in terms of 13w momentum; normalized to [-1, +1]
>
> 4.  `leadership_rotation_persistence`: Spearman correlation between
>     this week's and 4-weeks-ago top-quartile ETF membership (among
>     offensive ETFs); high = stable leadership, low = churning
>
> 5.  `credit_equity_alignment`: sign of (HYG 4w return) aligned with
>     sign of (SPY 4w return); +1 if both positive (credit confirming
>     equity), -1 if diverging
>
> 6.  `leadership_quality_composite`: z-scored weighted blend:
>     `0.30 × breadth - 0.20 × concentration + 0.25 × type_quality + 0.15 × persistence + 0.10 × credit_alignment`
>
> Validate: compute IC of composite vs next 4w SPY return by state.
> Compute partial IC after controlling for existing Phase 1 quality
> composite. Report to stdout.
>
> Output to `data/research/frontier_phase4/leadership_signals.csv` and
> `data/research/frontier_phase4/leadership_ic_results.csv`. No
> production files modified.

------------------------------------------------------------------------

### Prompt 4B: Leadership Wrapper Experiment

> Using Phase 4A leadership signals, implement
> `scripts/phase_frontier4_wrapper_experiment.py` that:
>
> 1.  Builds a modifier at the `regime_multipliers` checkpoint: scale
>     the offense regime multiplier by
>     `(1 + 0.12 × clip(leadership_quality_composite, -1, 1))` in
>     non-stressed states
>
> 2.  Tests four combinations:
>
>     -   Phase 1 only
>     -   Phase 4 only
>     -   Phase 1 + Phase 4
>     -   Phase 1 + Phase 2 + Phase 4
>
> 3.  Reports full Phase D metric table for all combinations on full and
>     holdout windows
>
> 4.  Reports state-conditional returns with special attention to
>     calm_trend and strong_neutral states (these are the target states
>     for leadership improvement)
>
> 5.  Writes `docs/research/frontier_phase4_leadership_system_report.md`
>     and updates `docs/research/project_journey.md`
>
> Acceptance gate: leadership composite adds ≥ 0.03 incremental IC in
> calm_trend state after controlling for Phase 1 quality composite. If
> not, classify as diagnostic-only.

------------------------------------------------------------------------

## Phase 5: Deployment-Quality Allocator Objective

### Prompt 5A: Confidence-Weighted Allocator

> You are implementing Frontier Phase 5: redesigning the allocator
> objective to incorporate deployment quality signals from Phases 1–4.
>
> Context: - Phase 1 quality composite, Phase 2 trend quality, and Phase
> 4 leadership composite are all available - The goal is to replace
> static diversification-based allocation with confidence-weighted risk
> budget - The stressed_panic defense remains unconditionally protected
>
> Implement `scripts/phase_frontier5_deployment_quality_allocator.py`
> that:
>
> 1.  Builds a `master_deployment_quality` score:
>     `0.40 × phase1_composite + 0.35 × phase2_portfolio_quality + 0.25 × phase4_leadership_composite`
>     (use portfolio-level average of Phase 2 per-ETF quality scores for
>     the current offense selection)
>
> 2.  Creates an offense budget modifier:
>     `offense_scale = 1 + alpha × clip(master_deployment_quality, -1, 1)`
>     where alpha = 0.12 (fixed, not tuned)
>
> 3.  Creates a diversification modifier: when
>     `master_deployment_quality > 0.5`, allow the HRP concentration
>     bound to tighten by 5% (concentrate slightly when confidence is
>     high); when `< -0.5`, expand by 5% (diversify when confidence is
>     low)
>
> 4.  Tests three candidates:
>
>     -   C1: offense budget modifier only
>     -   C2: diversification modifier only
>     -   C3: both combined
>
> 5.  Reports full Phase D metric table including: full-history,
>     holdout, rolling-origin, bootstrap, state-conditional, turnover,
>     BIL drag, hidden beta
>
> 6.  Alpha (0.12) is declared before the full-history evaluation and
>     NOT adjusted after seeing results
>
> 7.  Writes
>     `docs/research/frontier_phase5_allocator_objective_report.md` and
>     updates project journey
>
> Do NOT tune alpha or other parameters to maximize in-sample results.

------------------------------------------------------------------------

## Phase 6: Decision-Focused Learning

### Prompt 6A: Decision Label Construction

> You are implementing Frontier Phase 6, Step 1: decision quality label
> construction. This is the highest-risk phase in the project. Labels
> must be defined BEFORE examining their predictive content.
>
> The following label parameters are PRE-DECLARED (do not change after
> running): - `deploy_profit_barrier = 0.020` (+2% cumulative forward
> return over 8 weeks) - `deploy_loss_barrier = -0.012` (-1.2%
> cumulative forward return cutoff) - `horizon_weeks = 8` -
> `lag_weeks = 1` (all signals 1-week lagged) - Holdout start:
> 2024-04-19
>
> Implement `scripts/phase_frontier6_decision_labels.py` that:
>
> 1.  Loads portfolio returns for the GGG baseline (from
>     `data/research/stabilization/no_modifier_wrapper_rebuild_returns.csv`)
>
> 2.  Builds THREE label variants using the pre-declared parameters
>     above (computed with full 1-week lag — no look-ahead):
>
>     a.  `deploy_quality_label`: 1 if next 8w portfolio return ≥ 0 AND
>         annualized Sharpe of next 8w ≥ 0.5, else 0
>     b.  `triple_barrier_label`: 1 if profit barrier hit before loss
>         barrier, -1 if loss barrier hit first, 0 if neither within
>         horizon
>     c.  `rerisk_quality_label`: 1 if entering full risk-on this week
>         beats BIL over next 8 weeks by ≥ 1%, else 0; only evaluated
>         during recovery states
>
> 3.  Outputs label dataset to
>     `data/research/frontier_phase6/decision_labels.csv` with columns:
>     date, market_state, deploy_quality_label, triple_barrier_label,
>     rerisk_quality_label
>
> 4.  Reports label statistics: base rates, class balance,
>     state-conditional base rates — but does NOT yet train any model
>
> 5.  Writes `docs/research/frontier_phase6_decision_labels_report.md`
>     with the pre-declared parameters documented
>
> IMPORTANT: Do NOT examine label-vs-feature correlations in this
> script. That comes in Step 6B. The purpose of this script is to build
> honest labels without any feature peeking.

------------------------------------------------------------------------

### Prompt 6B: Decision Model Training and Validation

> Using the pre-declared labels from Phase 6A, implement
> `scripts/phase_frontier6_decision_model.py` that:
>
> 1.  Loads decision labels and Phase 1–4 quality signals as features
>     (all 1-week lagged, no look-ahead)
>
> 2.  Trains a walk-forward calibrated classifier:
>
>     -   Minimum training window: 260 weeks
>     -   Step: 26 weeks
>     -   Purged cross-validation: 4-week embargo at every train/test
>         boundary
>     -   Model: Logistic Regression or GradientBoostingClassifier
>         (max_depth=3, n_estimators=50)
>     -   Target: `deploy_quality_label` (binary)
>     -   Features: Phase 1 composite, Phase 2 portfolio quality, Phase
>         4 leadership, current market state (one-hot encoded), trailing
>         8w portfolio vol
>
> 3.  Evaluates the meta-model:
>
>     -   Out-of-sample accuracy, precision, recall on the pre-declared
>         holdout (2024-04-19 onward)
>     -   Comparison baseline: "always deploy" accuracy (class-balance
>         benchmark)
>     -   Comparison baseline: "deploy when Phase 1 quality \> 0"
>         accuracy
>
> 4.  Builds a simple portfolio rule: when `P(deploy_quality) < 0.35`,
>     switch to a half-offense position (blend 50% GGG / 50% BIL)
>
> 5.  Reports: holdout Sharpe with and without the meta-model gate,
>     recovery capture, BIL drag, turnover delta
>
> 6.  Acceptance gate: out-of-sample accuracy \> 56% AND holdout Sharpe
>     improvement ≥ +0.01 vs GGG baseline AND bootstrap P ≥ 60%
>
> 7.  Writes `docs/research/frontier_phase6_decision_model_report.md`
>
> Do NOT retrain the model on holdout data. Do NOT change label
> parameters after Phase 6A. Do NOT use test data during model
> selection.

------------------------------------------------------------------------

## Phase 7: Cross-Asset Relational Intelligence

### Prompt 7A: Lead-Lag Diagnostic Construction

> You are implementing Frontier Phase 7: cross-asset relational
> intelligence.
>
> Implement `scripts/phase_frontier7_crossasset_leadlag.py` that:
>
> 1.  Defines the following lead-lag pairs to investigate:
>
>     -   HYG (credit leader) → SPY (credit leading equity)
>     -   TLT (bond momentum) → SPY (bonds pricing regime change)
>     -   IWM/SPY ratio → equity breadth (small-cap risk appetite)
>     -   UUP (dollar strength) → VWO (dollar leading EM)
>     -   GLD momentum → TLT (inflation/deflation signal)
>
> 2.  For each pair, computes rolling 52-week cross-correlations at lags
>     of 1, 2, 4, and 8 weeks
>
> 3.  Measures stability: for each (pair, lag), compute fraction of
>     52-week rolling windows where \|correlation\| \> 0.15; stable if
>     \> 60% of windows
>
> 4.  Reports:
>
>     -   For each (pair, lag): mean correlation, correlation std,
>         stability score
>     -   Top 3 most stable lead-lag relationships
>     -   Periods where lead-lag relationships break down
>
> 5.  Builds a `cross_asset_confirmation_score` from the 3 most stable
>     pairs: +1 if lead asset confirms regime direction, -1 if it
>     contradicts, 0 if neutral
>
> 6.  Outputs to `data/research/frontier_phase7/`:
>
>     -   `leadlag_stability_diagnostics.csv`
>     -   `cross_asset_confirmation_score.csv`
>
> 7.  Writes
>     `docs/research/frontier_phase7_crossasset_leadlag_report.md`
>
> This is DIAGNOSTIC-ONLY. No portfolio candidates yet. The goal is to
> identify which lead-lag relationships are stable enough to use in a
> portfolio modifier.
>
> Acceptance gate to proceed to wrapper experiment: at least 3 of 5
> pairs show stability score ≥ 0.60 over 70%+ of history.

------------------------------------------------------------------------

### Prompt 7B: Cross-Asset Wrapper Experiment

> Using the `cross_asset_confirmation_score` from Phase 7A (only if
> acceptance gates passed), implement
> `scripts/phase_frontier7_wrapper_experiment.py` that:
>
> 1.  Builds a modifier at the `transition_rerisk_smoothing` checkpoint:
>     when `cross_asset_confirmation_score > 0` (cross-asset signals
>     confirm regime), increase re-risk speed by 10%; when `< 0`
>     (signals contradict), decrease by 10%
>
> 2.  Tests cross-asset modifier alone AND combined with Phase 3 smart
>     re-risking
>
> 3.  Reports full Phase D metric table with special attention to
>     recovery-state capture and regime transition timing
>
> 4.  Writes
>     `docs/research/frontier_phase7_crossasset_wrapper_report.md`

------------------------------------------------------------------------

## Phase 8: New Sleeve Design (Conditional)

### Pre-Condition Prompt

> Before opening Phase 8, answer these questions from Phases 1–7
> diagnostics:
>
> 1.  Is there a signal from Phases 1–7 with IC \> 0.05 that is NOT
>     captured by any existing sleeve? (If yes, identify it
>     specifically.)
> 2.  Is there a leadership type from Phase 4 that has materially
>     different state-conditional returns than any existing sleeve?
> 3.  Is there a cross-asset relationship from Phase 7 that deserves its
>     own dedicated sleeve module?
>
> If the answer to ALL THREE is "no", do NOT open Phase 8. The existing
> sleeve panel is sufficient. If the answer to any is "yes", document
> the specific evidence and proceed with the Phase 8 prompt.

### Prompt 8A: New Sleeve Design (Only If Pre-Condition Met)

> [This prompt is used only if Phase 8 pre-conditions are met.]
>
> Based on Phases 1–7 diagnostics, design ONE new sleeve that fills the
> identified structural gap: - Hypothesis: one sentence describing the
> economic motivation - Signal inputs: list all Layer 1 signals used
> (all 1-week lagged) - ETF selection rule: how does the sleeve
> rank/select ETFs? - State-gating: in which states is the sleeve
> active? - Cash/BIL rule: what does the sleeve hold when inactive?
>
> Implement `scripts/phase_frontier8_new_sleeve_design.py` that: 1.
> Builds the new sleeve using walk-forward safe logic 2. Runs standalone
> validation (Sharpe, MDD, state-conditional returns) 3. Runs
> distinctness verification: pairwise correlation against all existing 7
> sleeves (must be \< 0.40 to qualify) 4. Reports state winner margins
> 5. Does NOT automatically add the sleeve to the production panel —
> classification verdict required first

------------------------------------------------------------------------

## Phase 9: Optional Data Expansion (Data-Gated)

### Data Acquisition Checklist

Before Phase 9, verify: 1. PIT stock data is installed under
`data/stock_breadth/raw/` using the schema from
`scripts/build_pit_stock_breadth_panel.py` 2. Coverage: daily prices
back to 2005, S&P 500 PIT membership, delisting-aware 3. Run
`python scripts/build_pit_stock_breadth_panel.py` and verify no
MISSING_INPUTS_REPORTED errors

### Prompt 9A: PIT Stock Breadth Signal Validation

> [Only after PIT data is installed and validated]
>
> Using the installed PIT stock breadth data, implement
> `scripts/phase_frontier9_pit_breadth_signals.py` that:
>
> 1.  Builds a PIT stock breadth signal: fraction of S&P 500 members
>     (PIT, delisting-aware) above their 200-day MA, lagged 1 week
>
> 2.  Validates: compute IC vs 4w forward SPY return by market state,
>     with special attention to `calm_trend` (target: +0.517% per 4w
>     lift as identified in Phase 5A-Free diagnostic)
>
> 3.  Runs partial IC after controlling for ETF breadth signal to
>     confirm incremental value
>
> 4.  If IC gates pass, builds a wrapper experiment incorporating stock
>     breadth as an additional input to the Phase 1 deployment quality
>     composite
>
> 5.  Reports whether including PIT breadth improves the frontier stack
>     candidate above the GGG baseline on the pre-declared holdout

------------------------------------------------------------------------

## Phase 10: Final Production Candidate Evaluation

### Prompt 10A: Full Frontier Stack Evaluation

> After Phases 1–7 are complete and at least 2 phases have passed their
> acceptance gates, build the final frontier production candidate by
> combining the best-validated modifiers:
>
> 1.  Load the stabilized wrapper as the exact GGG baseline
>
> 2.  Apply the frontier modifiers in the following order at safe
>     checkpoints:
>
>     a.  Phase 1 quality composite → `regime_multipliers` modifier (if
>         passed acceptance)
>     b.  Phase 2 trend quality → `offense_budget` modifier (if passed
>         acceptance)
>     c.  Phase 3 smart re-risking → `transition_rerisk_smoothing`
>         modifier (if passed acceptance)
>     d.  Phase 4 leadership → `regime_multipliers` modifier (if passed
>         acceptance)
>     e.  Phase 5 allocator → `offense_budget` scaling (if passed
>         acceptance)
>     f.  Phase 6 meta-gate → half-position rule (if passed acceptance)
>     g.  Phase 7 cross-asset → `transition_rerisk_smoothing` boost (if
>         passed acceptance)
>
> 3.  Name the candidate: `improved_frontier_deployment_intelligence_v1`
>
> 4.  Run FULL Phase D evaluation:
>
>     -   Full-history vs production pin, shadow pin, production
>         candidate (GGG), and all frontier phase references
>     -   All 8 Phase D promotion gates
>     -   Rolling-origin (104-week, 52-week step)
>     -   Block bootstrap (2000 iterations, 13-week blocks, holdout
>         only)
>     -   State-by-state (all 6 states)
>     -   Cost/turnover analysis
>     -   Hidden beta and BIL exposure
>     -   SPY/offense/defense/BIL exposure
>
> 5.  Assign EXACTLY ONE verdict: Promote / Keep as Shadow /
>     Research-only / Drop
>
> 6.  Write `docs/research/frontier_phase10_final_evaluation_report.md`
>     and update project_journey.md

------------------------------------------------------------------------

## Sprint Completion Template

Every frontier sprint must include in its report:

``` markdown
## Sprint Summary

**Phase:** [Frontier Phase N: Name]
**Date:** [YYYY-MM-DD]
**Status:** [Diagnostic / Portfolio pass-through / Sandbox]

### Commands Run
- [list all commands]

### Files Created
- [list all new files]

### Files Modified
- [list all modified files, confirm no production files touched]

### Metrics Summary (Full History)
| Metric | GGG Baseline | This Sprint | Delta |
|--------|-------------|-------------|-------|
| Annual Return | | | |
| Sharpe | | | |
| Max DD | | | |
| CVaR 5% | | | |
| Recovery-Confirmed Capture | | | |
| Stressed-Panic Sharpe | | | |
| Avg BIL Weight | | | |
| Avg Turnover | | | |

### Holdout Metrics (Last 104 Weeks)
| Metric | GGG Baseline | This Sprint | Delta |
|--------|-------------|-------------|-------|
| Annual Return | | | |
| Sharpe | | | |
| Max DD | | | |

### Phase D Gate Results (Full Evaluation Only)
| Gate | Threshold | Result | Pass? |
|------|-----------|--------|-------|
| Full Δ | ≥ +0.015 | | |
| Holdout Δ | ≥ 0 | | |
| Holdout Sharpe Δ | ≥ -0.02 | | |
| Rolling Win Rate | ≥ 55% | | |
| Rolling Mean Δ | > 0 | | |
| Bootstrap P | ≥ 60% | | |
| MDD Δ | ≥ -0.01 | | |
| CVaR Δ | ≥ -0.002 | | |

### Verdict
[Promote / Keep as Shadow / Research-only / Drop]

### Key Finding
[One paragraph: what was the main finding?]

### What It Changes
[One paragraph: what does this tell us about the frontier direction?]

### Next Sprint Recommendation
[One sentence.]
```

------------------------------------------------------------------------

*Document ends. No production files modified.*
