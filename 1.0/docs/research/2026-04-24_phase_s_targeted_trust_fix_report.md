# Phase S — Final Targeted Trust-Layer Fix

Date: 2026-04-24
Track: Phase S (narrow, targeted). Previous: Phase R (Bucket-Trust Refinement, 2026-04-24).

---

## A. Mission

Close, or clearly fail to close, the remaining Phase D production-gate gap on top of the Phase R candidates with the smallest disciplined intervention possible. Phase R diagnosis identified two specific residuals:

1. `defense_production` bucket over-diversifies away from the production allocator's adverse-tape behavior (weighted meta-blend adds drag in the exact state where "fall back to production" should look like production).
2. Rolling 13-week ML excess turns negative often enough inside `calm_trust`, `recovery_trust`, and `ambiguous_abstain` to pull rolling win-rate below 55%.

Phase S tested two narrow levers against those residuals and one combination. The user's mandate was explicit: *"If these two levers do not solve it, say so clearly."*

## B. Candidates

Three additions only. All share Phase R's four-bucket skeleton, 3-week persistence, and trust classifier pipeline.

- **S1 — `improved_phases_defense_reshape_allocator`**
  Keeps R2 (`improved_phaser_light_abstention_overlay_allocator`) intact everywhere except `defense_production`. Internal mix tightened from `{prod 0.85, phasen 0.075, phaseo 0.075, abstain 0}` to `{prod 0.95, phasen 0.025, phaseo 0.025, abstain 0}`. Pure reshape — no change to bucket logic, persistence, or classifier.

- **S2 — `improved_phases_conditional_ml_attenuator_allocator`**
  Keeps R2's base mixes for every bucket. Adds a causal 13-week trailing-excess attenuator that scales phaseo/phasen weights by a factor ∈ `[0.40, 1.0]` inside `calm_trust`, `recovery_trust`, and `ambiguous_abstain` when rolling ML excess vs production is below -0.0015. Removed ML mass is re-allocated 1:1 to production. Inputs are 1-week shifted (no lookahead).

- **S3 — `improved_phases_defense_reshape_ml_attenuator_combo`**
  S1 defense_production base mix + S2 conditional attenuator. Only built because S1 and S2 move on different axes.

## C. Validation protocol (unchanged from Phase D)

- Fixed 10-member comparator set: production pin, shadow pin, Phase H state allocator, Phase N distributional, Phase O tail-priority, Phase P regret-aware, Phase Q bucket meta, Phase R R2 (light abstention overlay), Phase R R3 (fast/narrow regret), active panel baseline.
- Full-history panel: 2016-11-11 → 2026-04-10.
- Holdout: 2023-08-25 → 2026-04-10 (139 weeks).
- Moving-block bootstrap: 13-week blocks × 2,000 draws on holdout excess return.
- Rolling origin: 260-week min train, 104-week test, 52-week step (15 windows).
- Phase D promotion rules unchanged: full Δ ≥ +0.015, holdout Δ ≥ 0, holdout Sharpe Δ ≥ -0.02, rolling win ≥ 55%, bootstrap ≥ 60%, DD/CVaR no worse than -0.01/-0.005 vs production.

## D. Headline results

### Full-history raw composite (rank out of 13)

| candidate | raw_composite | rank |
|---|---|---|
| R2 (phaser_light_abstention_overlay) | 0.5198 | 8 |
| **S1 (defense_reshape)** | **0.5075** | 10 |
| **S2 (conditional_ml_attenuator)** | **0.5131** | 9 |
| **S3 (combo)** | **0.5009** | 11 |
| production | 0.4777 | 13 |

### Holdout raw composite

| candidate | raw_composite | holdout Sharpe | rank |
|---|---|---|---|
| production | 0.9628 | 2.0996 | 1 |
| R2 | 0.9496 | 2.1549 | 5 |
| **S1** | **0.9491** | **2.1658** | 7 |
| **S2** | **0.9499** | **2.1450** | 4 |
| **S3** | **0.9493** | **2.1560** | 6 |

### Pairwise vs production (the gate)

| candidate | full Δ | holdout Δ | holdout Sharpe Δ | rolling win | bootstrap prob |
|---|---|---|---|---|---|
| R2 | +0.042 | -0.013 | +0.055 | 46.7% | 38.9% |
| **S1** | **+0.030** | **-0.014** | **+0.066** | **40.0%** | **46.6%** |
| **S2** | **+0.035** | **-0.013** | **+0.045** | **40.0%** | **39.1%** |
| **S3** | **+0.023** | **-0.013** | **+0.056** | **46.7%** | **47.3%** |

### Pairwise vs R2 (Phase S's own improvement axis)

| candidate | full Δ vs R2 | holdout Δ vs R2 | holdout Sharpe Δ vs R2 | bootstrap vs R2 |
|---|---|---|---|---|
| **S1** | -0.012 | -0.0006 | +0.011 | 81.0% |
| **S2** | -0.007 | +0.0003 | -0.010 | 55.7% |
| **S3** | -0.019 | -0.0003 | +0.001 | 79.8% |

## E. Phase D gate check

All three Phase S candidates fail the same three production gates that R2 failed.

- Full-history Δ ≥ +0.015 → S1 +0.030, S2 +0.035, S3 +0.023 — **all pass**.
- Holdout Δ ≥ 0 → S1 -0.014, S2 -0.013, S3 -0.013 — **all fail**.
- Holdout Sharpe Δ ≥ -0.02 → S1 +0.066, S2 +0.045, S3 +0.056 — **all pass** (and improve on production).
- Rolling win ≥ 55% → S1 40.0%, S2 40.0%, S3 46.7% — **all fail**.
- Bootstrap ≥ 60% → S1 46.6%, S2 39.1%, S3 47.3% — **all fail**.
- DD/CVaR caps → All pass (DD within +0.002, CVaR within +0.001 of production).

Final classification for all three: **Research-only**. Dual-track pins unchanged — production remains `improved_phase2b_regime_confidence_boost`, shadow remains `improved_phase2b_combo_abc`.

## F. Honest verdict on the two levers

**The two Phase S levers did not solve the production-gate gap.** Stated plainly:

- On holdout raw composite, all three Phase S candidates move by -0.0006 to +0.0003 vs R2. That is noise, not a closed gap. The -0.013 shortfall to production is structurally identical to R2's -0.013 shortfall.
- S1's disciplined upside was higher holdout Sharpe. It delivered: +0.011 vs R2 and +0.066 vs production — highest of any tested candidate. But it cost -0.012 on full composite (less ML mass during the pre-holdout period where ML-heavy buckets did work).
- S2's disciplined upside was higher rolling win-rate. It did not deliver: rolling win stayed at 40%, identical to the non-R2 baselines. The attenuator fires on holdout often enough (ML-excess window crossed threshold in ~31% of trust-bucket weeks) but not in a way that lines up with production's own adverse weeks.
- S3 combined the two: S1's Sharpe gain partially carries over, S2's rolling-win gain did not, full composite suffered the most (-0.019 vs R2).

Bootstrap probability vs R2 is high for S1 and S3 (81%, 79.8%) — those two reliably beat R2 in holdout-block resampling — but bootstrap probability vs production stays stuck at 39-47%. A candidate that reliably beats the intermediate reference but not the production pin is useful as a tracking reference, not a promotion.

Interpretation: the remaining gap is not located in the two places Phase R diagnosed. Tightening `defense_production` (S1) moved the composite in the wrong direction on full history. Attenuating ML on trailing-negative excess (S2) correlates poorly with production's actual weekly wins. **The trust-layer frontier is plateaued. Further narrow sprints inside this layer are very unlikely to close the remaining -0.013 holdout gap.**

## G. Where the remaining gap is likely hiding

Phase S's diagnostic residuals after the sprint point to two places the trust layer cannot see through:

1. **Layer 2B regime engine boundaries.** The four buckets are deterministic combinations of `market_state` outputs. When `market_state` changes slightly early or late, the bucket changes with it, and every trust-layer candidate inherits that error. Phase R and Phase S both moved small weights inside buckets but never altered the bucket itself.

2. **Per-week specific holdings.** Production's holdout edge is concentrated in a small handful of weeks where its specific GLD/HYG/DBA/BIL mix was favorable; every meta-blend over phaseo/phasen/production necessarily averages away from that point solution. No bucket-level mix change or conditional attenuator can recover those specific weeks without either (a) giving 100% weight to production in those exact weeks (overfitting), or (b) improving the upstream regime detection so those weeks are classified cleanly.

## H. Artifacts

Scripts:
- `scripts/phase_s_targeted_trust_fix.py` — S1, S2, S3 implementations; validation bundle writer.

Data (`data/05_layer3_portfolio_construction/`):
- `phase_s_candidate_metrics_full.csv`
- `phase_s_candidate_metrics_holdout.csv`
- `phase_s_candidate_metrics_dev.csv`
- `phase_s_pairwise_validation.csv`
- `phase_s_candidate_classification.csv`
- `phase_s_rolling_origin_summary.csv`
- `phase_s_trust_summary.csv`
- `phase_s_trust_by_state.csv`
- `phase_s_bucket_summary.csv`
- `phase_s_controls_improved_phases_defense_reshape_allocator.csv`
- `phase_s_controls_improved_phases_conditional_ml_attenuator_allocator.csv`
- `phase_s_controls_improved_phases_defense_reshape_ml_attenuator_combo.csv`
- `phase_s_validation_protocol.json`

Documentation:
- `docs/research/2026-04-24_phase_s_targeted_trust_fix_report.md` (this report).
- `docs/research/project_journey.md` — Section 32 appended.

## I. Classification summary

| candidate | standalone (vs R2) | combination (combo vs S1/S2) | final |
|---|---|---|---|
| improved_phases_defense_reshape_allocator | Sharpe +0.011, holdout flat, full -0.012 | — | **Research-only** |
| improved_phases_conditional_ml_attenuator_allocator | Sharpe -0.010, holdout +0.0003, full -0.007 | — | **Research-only** |
| improved_phases_defense_reshape_ml_attenuator_combo | Sharpe +0.001, holdout flat, full -0.019 | No material lift over S1 | **Research-only** |

Production pin: `improved_phase2b_regime_confidence_boost` — **unchanged**.
Shadow pin: `improved_phase2b_combo_abc` — **unchanged**.

## J. What should happen next

The honest recommendation, consistent with Phase R's fallback clause: **stop refining the trust layer.** Three consecutive sprints (Q → R → S) have moved progressively smaller amounts against the same -0.013 holdout residual without clearing it. The frontier inside the trust layer is flat.

The two remaining productive directions, in rough priority order:

1. **Layer 2B regime engine revisit.** Specifically, test whether making `market_state` a distribution (soft posterior) rather than a hard label, and feeding the distribution into the bucket mapping, lifts the holdout composite without giving back Sharpe. Phase Q/R/S all consumed a hard label; a softened posterior may tighten the exact boundary errors the trust layer cannot fix.

2. **Production-anchored combo at the portfolio level, not the allocator level.** Blend production's holdings 60-80% with the best trust-layer candidate's holdings 20-40% at the ETF-weight level, walk-forward. This is a more aggressive interpretation of "defense_production means look like production" and would bypass the meta-blend averaging problem directly. Test under Phase D rules.

If neither direction lifts the holdout composite materially within one sprint each, the project has reached its structural ceiling on this signal + sleeve set, and the conclusion is that production remains the best deployable allocator. R3 remains the Sharpe reference, R2 remains the closest-to-gate reference, and dual-track reporting continues unchanged.
