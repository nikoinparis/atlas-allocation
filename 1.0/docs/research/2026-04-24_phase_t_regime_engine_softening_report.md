# Phase T — Regime Engine Softening / Layer 2B Revisit

Date: 2026-04-24
Track: Phase T (upstream, narrow). Previous: Phase S (Final Targeted Trust-Layer Fix, 2026-04-24).

---

## A. What changed

This is the project's first sprint to touch Layer 2B since the trust-layer (Phase Q→R→S) frontier closed flat. Three things changed, all narrowly scoped:

- The hard per-week regime-bucket label (Phase Q's deterministic rule) is replaced by a **causal soft posterior** over the same four buckets: `calm_trust`, `recovery_trust`, `defense_production`, `ambiguous_abstain`.
- The posterior is a closed-form softmax (temperature 0.45) over handcrafted bucket-affinity scores built from the **same causal features** the hard rule already consumed: `state_text`, `model_confidence`, `model_uncertainty`, `margin_confidence`, `agreement`, `risk_guard`, `phase_n_gate_entropy`, and the four state confidences. No new fitted model; no new training window.
- A causal **3-week half-life EMA** smooths the posterior so it doesn't flicker, then the per-week expert mix becomes Σ over buckets of `posterior(bucket) × base_mix(bucket)`. R2's per-bucket base mixes and light-abstention overlay are preserved.

Two narrow upgrades sit on top of that posterior:
- **T2 defensive pull**: when the posterior is diffuse (max-prob < 0.65), pull up to 30% of the mix toward `defense_production`. Linear saturation between 0.40 (full pull) and 0.65 (zero pull).
- **T3 production anchor at the ETF level**: when the posterior is diffuse (max-prob < 0.60), blend up to 15% of the final ETF weights with production's actual holdings. Linear saturation between 0.40 and 0.60.

No code touched outside `scripts/phase_t_regime_softening.py`. No retraining of unrelated branches. Existing trust-classifier probabilities and Phase O/N/H/P weights are reused as-is.

## B. What was executed

- Public-research orientation (no new code): probabilistic regime work is broadly consistent across AQR, Man Group, Newfound, Robeco, and the Markov-switching literature on the same point — that hard state assignment harms portfolios on boundary weeks and that smoothed posteriors reduce regret in dynamic allocation. None of the literature suggests soft posteriors should produce miracles when the underlying signal–sleeve information is already exhausted, which is the operational concern after Phase S.
- `python3 scripts/phase_t_regime_softening.py` — built three Phase T candidates, computed soft posteriors per week, ran full validation against the 10-member fixed comparator set under Phase D rules.
- Bootstrap: 13-week moving block × 2,000 draws on holdout excess return.
- Rolling origin: 260-week min train, 104-week test, 52-week step (15 windows).

## C. Files / artifacts changed

Scripts:
- `scripts/phase_t_regime_softening.py` (T1/T2/T3 implementations + validation bundle).

Data (`data/05_layer3_portfolio_construction/`):
- `phase_t_candidate_metrics_{full,dev,holdout}.csv`
- `phase_t_pairwise_validation.csv`
- `phase_t_candidate_classification.csv`
- `phase_t_rolling_origin_summary.csv`
- `phase_t_trust_summary.csv`, `phase_t_trust_by_state.csv`
- `phase_t_bucket_summary.csv`
- `phase_t_posterior_summary.csv` (Phase T-specific: posterior diagnostics)
- `phase_t_controls_*.csv` (per-candidate per-week control)
- `phase_t_validation_protocol.json`
- `portfolio_version_{weights,returns}_improved_phaset_*.csv`

Documentation:
- `docs/research/2026-04-24_phase_t_regime_engine_softening_report.md` (this report).
- `docs/research/project_journey.md` — Section 33 appended.

## D. Starting-point diagnosis

**Why Phase S was not enough by itself.** Phase S tested the only two narrow trust-layer levers Phase R diagnosed — defense_production internal reshape (S1) and conditional ML-share attenuator on trailing-negative excess (S2). Both failed to move the holdout gap. S1 lifted holdout Sharpe to 2.166 (best in cohort) but cost full-history composite. S2 fired in ~31% of trust-bucket weeks but the firing weeks did not line up with production's winning weeks, so rolling win-rate stayed at 40%. The combo (S3) inherited S1's Sharpe gain and S2's inability to move rolling win-rate. All three classified Research-only.

**Exact remaining problem.** After Phase Q→R→S, the residual against production is structural and stable: holdout raw Δ = -0.013, rolling win-rate = 40-47%, bootstrap probability = 39-47%. Phase S's diagnostic concluded the residual was no longer reachable from Layer 3, because every trust-layer candidate inherited the same hard `market_state` label and the same hard regime-bucket assignment built on top of it. If a state changed slightly early or late, the bucket changed with it, and the trust layer could not see through the boundary error.

**Why Layer 2B is the right next frontier.** Two reasons. First, the hard bucket assignment is the only point in the pipeline that turns continuous evidence (state confidences, gate entropy, model uncertainty, risk guard) into a discrete decision before the allocator sees it. Every downstream component lives downstream of that decision. Second, the posterior over the same four buckets was 54.7% disagreement with the hard rule on this dataset (see Section F) — so there is real room for the boundary to move.

## E. Phase T results (per candidate)

### T1 `improved_phaset_soft_regime_posterior_allocator`

Full: ann_return 0.0699, ann_vol 0.0731, Sharpe 0.9558, max_dd -0.1313, Calmar 0.5324, CVaR_5 -0.0239, turnover 0.0743, upside_capture 0.3284, downside_capture 0.2435, recovery_capture 0.3165, avg_bil 0.2636, avg_spy 0.0887, avg_offense 0.5486, avg_defense 0.1878, avg_cash 0.2636.
Holdout: ann_return 0.1487, ann_vol 0.0713, Sharpe 2.0865, max_dd -0.0575, Calmar 2.5882, CVaR_5 -0.0187, turnover 0.0853, upside_capture 0.4569, downside_capture 0.2750, recovery_capture 0.5939, avg_bil 0.2063, avg_spy 0.1027, avg_offense 0.5892, avg_defense 0.2045, avg_cash 0.2063.

### T2 `improved_phaset_soft_trust_weighted_allocator`

Full: ann_return 0.0702, ann_vol 0.0735, Sharpe 0.9550, max_dd -0.1331, Calmar 0.5271, CVaR_5 -0.0241, turnover 0.0714, upside_capture 0.3278, downside_capture 0.2420, recovery_capture 0.3120, avg_bil 0.2679, avg_spy 0.0873, avg_offense 0.5482, avg_defense 0.1838, avg_cash 0.2679.
Holdout: ann_return 0.1514, ann_vol 0.0716, Sharpe 2.1154, max_dd -0.0574, Calmar 2.6380, CVaR_5 -0.0189, turnover 0.0812, upside_capture 0.4556, downside_capture 0.2657, recovery_capture 0.5889, avg_bil 0.2040, avg_spy 0.0992, avg_offense 0.5899, avg_defense 0.2061, avg_cash 0.2040.

### T3 `improved_phaset_production_anchored_soft_combo`

Full: ann_return 0.0703, ann_vol 0.0737, Sharpe 0.9542, max_dd -0.1340, Calmar 0.5247, CVaR_5 -0.0243, turnover 0.0703, upside_capture 0.3274, downside_capture 0.2412, recovery_capture 0.3099, avg_bil 0.2706, avg_spy 0.0867, avg_offense 0.5476, avg_defense 0.1818, avg_cash 0.2706.
Holdout: ann_return 0.1527, ann_vol 0.0717, Sharpe 2.1292, max_dd -0.0573, Calmar 2.6663, CVaR_5 -0.0190, turnover 0.0794, upside_capture 0.4549, downside_capture 0.2609, recovery_capture 0.5861, avg_bil 0.2031, avg_spy 0.0975, avg_offense 0.5900, avg_defense 0.2070, avg_cash 0.2031.

### Pairwise (vs production, vs R2, vs R3)

| candidate | full Δ vs prod | holdout Δ vs prod | holdout Sharpe Δ vs prod | bootstrap vs prod | rolling win | full Δ vs R2 | holdout Δ vs R2 | Sharpe Δ vs R2 | Sharpe Δ vs R3 | bootstrap vs R3 |
|---|---|---|---|---|---|---|---|---|---|---|
| **T1** | **+0.077** | -0.016 | -0.013 | 16.5% | 40.0% | +0.035 | -0.003 | -0.068 | -0.129 | 13.2% |
| **T2** | +0.070 | -0.015 | +0.016 | 19.1% | 40.0% | +0.028 | -0.002 | -0.040 | -0.100 | 24.7% |
| **T3** | +0.066 | -0.013 | +0.030 | 21.0% | 40.0% | +0.024 | -0.0003 | -0.026 | -0.087 | 33.4% |
| R2 | +0.042 | -0.013 | +0.055 | 38.9% | 46.7% | 0.000 | 0.000 | 0.000 | -0.061 | 92.6% |
| R3 | +0.047 | -0.018 | +0.116 | 26.8% | 40.0% | +0.005 | -0.004 | +0.061 | 0.000 | 0.000 |

### Posterior diagnostics (Phase T-specific)

- Hard-vs-soft bucket disagreement share: **54.7%** of weeks. The soft argmax differs from the Phase Q hard rule on more than half the dataset.
- Average posterior max-prob: **0.479**. Median: **0.469**.
- High-confidence weeks (max-prob ≥ 0.65): **14.0%**.
- Boundary weeks (max-prob < 0.55): **68.8%**.
- Diffuse weeks (max-prob < 0.45): **45.7%**.
- T2 defensive-pull average per-week magnitude: **0.185** (i.e., on average 18.5% of the mix nudged toward defense_production).
- T3 production-anchor average per-week magnitude: **0.085** (8.5% of final ETF weights blended with production).

The posterior found the **defense_production** bucket only 22.5% of the time vs the hard rule's 67.5%. Most weeks the soft posterior assigned `calm_trust` (65.9%) where the hard rule had assigned `defense_production`. That is the core reason Phase T candidates rank higher on **full-history** raw composite (T1 #3 in the cohort vs R2 #11) — they put more ML weight to work in calm-but-conservatively-labeled weeks. It is also the reason holdout suffered slightly: many of those reclassified weeks fell in production's adverse-tape window where production was the right answer.

## F. Phase T interpretation

**What helped.** Soft posteriors materially improved full-history raw composite. T1 reached 0.5545 (rank 3 of 13), well above R2's 0.5198 (rank 11). The improvement came from correctly identifying that the hard rule was over-classifying weeks as `defense_production` outside the holdout window — those weeks really did have ML edge. T2/T3 preserved that gain almost intact (0.5477 / 0.5436). Holdout drawdown, CVaR, and ann_return are competitive with R2 across all three candidates. T3 closed the holdout raw composite gap to R2 to essentially zero (-0.0003) while being slightly heavier on production exposure.

**What did not help, and why it matters.**

1. **Holdout Sharpe got worse, not better, vs the trust-layer references.** T1's Sharpe 2.087 is below production (2.100) and well below R3 (2.216) and R2 (2.155). T2/T3 recovered some of it via defensive pull and production anchor (Sharpe 2.115/2.129), but neither beats R2's 2.155 or R3's 2.216. The candidate that most aggressively used the soft posterior (T1) was Sharpe-worst, and tightening it back toward the hard-rule answer (T2, T3) clawed back some Sharpe but did not exceed the trust-layer references.

2. **Bootstrap probability vs production collapsed.** R2 sat at 38.9%; T1/T2/T3 are at 16.5% / 19.1% / 21.0%. The soft posterior trades cleanly-anchored decisions for a wider distribution of slightly-worse outcomes — typical of a model that adds variance without adding edge.

3. **Bootstrap probability vs R2 stayed below 15% for all three Phase T candidates.** They do not reliably beat R2 on holdout-block resampling.

4. **Rolling win-rate vs production stuck at 40%.** Same as Q2 / R3 / S1 / S2 / S3. Three of four windows are losers regardless of how the regime layer is softened. This is the single most stable observation across Phase Q→R→S→T.

**Soft regime did not solve the production-gate gap.** It moved the dev-vs-holdout balance modestly — bigger dev gains, slightly bigger holdout Sharpe loss — without closing any of the three failing Phase D gates (holdout Δ ≥ 0, rolling win ≥ 55%, bootstrap ≥ 60%).

**Did Phase T beat R2 / R3 references?** No. T3's full-history composite is +0.024 above R2 and +0.019 above R3, but its holdout raw composite is essentially tied with R2 (-0.0003), worse than R3 by -0.004, and Sharpe is below both R2 and R3. T1/T2 are similar in shape with worse Sharpe.

**Did Phase T beat the production pin?** No. Holdout Δ stuck at -0.013 to -0.016. Bootstrap 16-21%. Rolling win 40%.

**Is the regime-engine frontier exhausted?** Yes, on this signal + sleeve set. The 54.7% disagreement rate showed that softening genuinely changed bucket decisions, and those changes were locally helpful in the dev window but did not net out to a holdout improvement — meaning the residual gap is **not** primarily a hard-boundary problem. It is downstream of any bucket assignment, soft or hard. Most likely: (i) the holdout window is structurally favorable to production's specific weekly ETF holdings in a way no meta-blend can recover, or (ii) the signal/sleeve panel itself is at its information limit on this universe.

## G. Candidate classification

| candidate | classification | reason |
|---|---|---|
| improved_phaset_soft_regime_posterior_allocator (T1) | **Research-only** | Strong full-history composite (+0.077 vs production, +0.035 vs R2). Holdout Δ -0.016, Sharpe Δ -0.013 vs prod, Sharpe Δ -0.068 vs R2, bootstrap vs prod 16.5%, rolling win 40%. Fails three production gates and is dominated on holdout Sharpe by R2/R3. |
| improved_phaset_soft_trust_weighted_allocator (T2) | **Research-only** | Full Δ +0.070, holdout Δ -0.015, Sharpe Δ +0.016 vs prod (above prod, below R2 and R3). Bootstrap vs prod 19.1%, rolling win 40%. |
| improved_phaset_production_anchored_soft_combo (T3) | **Research-only** | Closest of the three to production on holdout (Δ -0.013, matches R2). Sharpe Δ +0.030 vs prod (best of T-trio, still below R2/R3). Bootstrap 21.0%, rolling win 40%. |

**Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.**
**Shadow pin: `improved_phase2b_combo_abc` — unchanged.**

## H. Strategic diagnosis

**Did Phase T succeed?** No on the success condition stated in the brief. None of the three candidates materially outperformed R2 or R3 on holdout Sharpe; none materially improved holdout raw composite, rolling win-rate, or bootstrap support; none got materially closer to or cleared the production promotion rule. The best holdout result (T3, raw Δ -0.013) ties R2 — same gap, different mechanism.

**Is the regime-engine frontier the right one?** On the evidence, no. The soft posterior produced large, real differences in bucket assignment (54.7% disagreement) and those differences moved the **full-history** composite up sharply (+0.077 for T1 vs production). If hard boundaries were the residual cause, the holdout would have moved with the full-history. It did not. The mechanism that worked in dev (more ML weight in calm-but-mislabeled-as-defense weeks) did not work in holdout, because in holdout the hard rule's defense classifications were largely correct.

**Or is this whole signal/sleeve/regime stack close to its ceiling?** On the same evidence, yes. Four sprints — Phase Q (bucket meta), Phase R (bucket trust refinement), Phase S (targeted defense reshape + ML attenuation), Phase T (soft regime posterior) — converged to the same structural -0.013 holdout shortfall. Each sprint addressed a different hypothesis (trust-aware vs trust-refined vs trust-attenuated vs upstream-softened) and none of the four cleared the gate. The most parsimonious read: the production allocator's holdout edge is in **specific weekly ETF positioning** that the meta-allocator's expert universe (production / phaseo / phasen) cannot replicate without literally giving 100% to production in those weeks (overfitting). No amount of regime softening fixes that.

## I. Final recommendation

- **Production pin: stay on `improved_phase2b_regime_confidence_boost`.** Unchanged.
- **Shadow pin: stay on `improved_phase2b_combo_abc`.** Unchanged.
- **Trust-layer research reference: stay on R2 (`improved_phaser_light_abstention_overlay_allocator`).** It remains the closest-to-gate candidate (holdout Δ -0.013, rolling win 46.7%, bootstrap 38.9%) and Phase T did not match or exceed it on the deployment-relevant axes. T3 ties R2 on holdout raw composite but loses on holdout Sharpe, bootstrap, and rolling win.
- **Sharpe research reference: stay on R3 (`improved_phaser_fast_narrow_regret_allocator`).** R3's holdout Sharpe 2.216 remains the highest in the cohort. Phase T candidates topped out at 2.129 (T3).
- **Add T1 to the comparator set as the "soft regime + best dev composite" reference.** T1's full-history raw composite (0.5545, rank 3 in the 13-member cohort) is the highest of any meta-allocator candidate that did not classify Promote. It is useful as a tracking reference for any future sprint that wants to claim it has helped both dev and holdout simultaneously.

**Next step.** Phase T closes the upstream regime-engine direction. Two viable next directions, in order of conviction:

1. **Portfolio-level production-anchored holdings blend (Phase S recommendation #2, not yet tested directly).** Skip the meta-allocator entirely on a controlled fraction of weeks: blend production's actual ETF weights 70-90% with R2's weights 10-30%, walk-forward, with the blend ratio possibly conditioned on Phase Q's hard `defense_production` flag. This is the only direction that bypasses the meta-blend averaging problem at the holdings level. **Recommend as Phase U.**

2. **Stop and ship.** If Phase U does not lift holdout composite above the gate, the project has reached its structural ceiling on this signal + sleeve panel. Production then remains the deployable allocator without further refinement, R2 remains the closest-to-gate research reference, R3 remains the Sharpe reference, and Phase T's T1 stays in the comparator set as the dev-strong soft-regime reference. Dual-track reporting continues unchanged.

If either direction beyond Phase U is to be considered later, it should be a **sleeve-panel revisit** (different sleeves, not different allocators on the same sleeves), not another allocator or trust-layer sprint.

## J. Project journey log update

- Updated `docs/research/project_journey.md`: Section 33 — Phase T — Regime Engine Softening / Layer 2B Revisit — appended at the end of the file.
- Project journey is now current through Phase T.
