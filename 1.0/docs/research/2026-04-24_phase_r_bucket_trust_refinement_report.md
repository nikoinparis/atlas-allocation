# Phase R — Bucket-Trust Refinement

Date: 2026-04-24

## A. What was changed

This sprint is a tightly scoped refinement of the Phase Q winner
`improved_phaseq_regime_bucket_meta_allocator` (Q2). No new sleeves, signals,
or allocator philosophies. Four Phase R candidates were implemented on top of
the Phase Q / Phase P infrastructure, each targeting a specific Q2 weakness:

- **R1 — `improved_phaser_bucket_refined_meta_allocator`**
  Q2 skeleton with tuned per-bucket base mixes. Abstain cushion reduced from 8%
  to 4% in `defense_production` and from 35% to 12% in `ambiguous_abstain`.
  Production floor in `recovery_trust` cut from 25% to 18% to release more ML
  weight. Calm/recovery trust mixes left essentially as in Q2.

- **R2 — `improved_phaser_light_abstention_overlay_allocator`**
  Q2 skeleton with abstention removed from the base mixes in
  `defense_production` entirely (85% production / 7.5% phasen / 7.5% phaseo),
  and reduced to a runtime overlay that only activates when abstention_score
  > 0.60 inside a non-defense bucket, capped at 0.10 total abstain weight.
  Abstention becomes a rare tail tool, not a base mode.

- **R3 — `improved_phaser_fast_narrow_regret_allocator`**
  Q2 base mixes held fixed. 20-week EMA regret replaced with 8-week EMA. The
  regret signal can *only* reallocate weight between phaseo and phasen inside
  the existing ML share — it never touches production or abstain mass.

- **R4 — `improved_phaser_refined_bucket_fast_regret_combo`**
  R1 base mixes + R3 narrow fast regret. Built only because R1 and R3 both
  showed standalone movement; combined mechanically, not searched over.

No changes to the feature frame, walk-forward classifiers, or Phase 2B regime
engine. Bucket persistence (3 weeks) preserved.

## B. What was executed

- `scripts/phase_r_bucket_trust_refinement.py` (new): Phase R builder, reuses
  `phase_p_meta_allocator.build_feature_frame`,
  `phase_p_meta_allocator.walkforward_binary_classifier`,
  `phase_q_abstention_meta_allocator.compute_regime_bucket`, the Q1/Q3
  abstention score, and `phase_p_evaluate` for validation.
- Walk-forward binary classifiers re-fit under new model names
  (`phaser_binary_phaseo_vs_production`, `phaser_binary_phasen_vs_production`)
  so the trust probabilities are reproducible from scratch.
- Full validation against the fixed 9-member comparator set (production,
  shadow, phaseh, phasen, phaseo, phasep, phaseq bucket, phaseq abstention,
  refined panel blend) plus the four Phase R candidates.

## C. Files / artifacts changed

- `scripts/phase_r_bucket_trust_refinement.py` — new
- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaser_*.csv` — four new
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaser_*.csv` — four new
- `data/05_layer3_portfolio_construction/phase_r_controls_improved_phaser_*.csv` — four new
- `data/05_layer3_portfolio_construction/phase_r_candidate_metrics_{full,dev,holdout}.csv` — new
- `data/05_layer3_portfolio_construction/phase_r_rolling_origin_summary.csv` — new
- `data/05_layer3_portfolio_construction/phase_r_pairwise_validation.csv` — new
- `data/05_layer3_portfolio_construction/phase_r_candidate_classification.csv` — new
- `data/05_layer3_portfolio_construction/phase_r_trust_summary.csv`,
  `phase_r_trust_by_state.csv`, `phase_r_bucket_summary.csv` — new
- `data/05_layer3_portfolio_construction/phase_r_validation_protocol.json` — new
- `docs/research/2026-04-24_phase_r_bucket_trust_refinement_report.md` — this file
- `docs/research/project_journey.md` — extended with Section 31 (Phase R)

## D. Starting point diagnosis

**Why was Phase Q not enough.** Q2 was the strongest trust-model branch, but
it missed three Phase D production gates simultaneously, each by a small but
real margin:

- holdout raw composite Δ vs production: **-0.018** (needs ≥ 0)
- rolling-origin raw win rate vs production: **40%** (needs ≥ 55%)
- holdout moving-block bootstrap prob vs production: **25.7%** (needs ≥ 60%)

Diagnostic work showed Q2 already *beat* production on holdout ann_return
(+15.5% vs +15.4%), Sharpe (+0.111), max drawdown (-0.054 vs -0.057), CVaR
(-0.019 vs -0.020), and recovery_capture (+0.20). The -0.018 holdout composite
gap was driven by three composite components: slightly higher downside_capture
(0.257 vs 0.216), higher turnover (0.079 vs 0.060), and an 8%-of-weeks
defensive-anchor drag from the abstain cushion inside `defense_production`.

**What Phase R is trying to solve.** Close the 1-2pp holdout composite gap
while preserving the +0.11 Sharpe and +0.20 recovery_capture gains that Q2
already earned. Three interpretable levers looked promising a priori:
(i) trim the abstain cushions that aren't doing defensive work, (ii) reduce
production-floor over-insurance in ML-trust buckets, (iii) let faster, narrower
regret pick between the two ML experts without disturbing the bucket's
production/ML split.

**Why refining Q2 is the right next step.** Phase Q established empirically
that hard sticky buckets beat smooth softmax. Phase Q also established that
full abstention (Q1, 34% avg abstain) is too aggressive for the production
gate, and that a 20-week regret overlay (Q3) is too slow to add value. That
leaves a narrow middle band — refined buckets + targeted overlays — that the
project has not yet tested.

## E. Phase R results

### Full-history metrics

| candidate | ann_return | ann_vol | sharpe | max_dd | calmar | cvar_5 | turnover | upside | downside | avg_bil | avg_spy | avg_offense | avg_defense | avg_cash | recovery | calm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 bucket_refined | 0.0697 | 0.0736 | 0.9458 | -0.1333 | 0.5225 | -0.0243 | 0.0724 | 0.3248 | 0.2394 | 0.2822 | 0.0840 | 0.5369 | 0.1808 | 0.2822 | 0.2989 | 0.5166 |
| R2 light_abstention | 0.0708 | 0.0752 | 0.9419 | -0.1366 | 0.5185 | -0.0249 | 0.0733 | 0.3305 | 0.2437 | 0.2799 | 0.0836 | 0.5488 | 0.1713 | 0.2799 | 0.3052 | 0.5152 |
| R3 fast_narrow_regret | 0.0682 | 0.0716 | 0.9523 | -0.1304 | 0.5226 | -0.0236 | 0.0703 | 0.3143 | 0.2301 | 0.2882 | 0.0830 | 0.5172 | 0.1945 | 0.2882 | 0.2776 | 0.5028 |
| R4 combo | 0.0697 | 0.0737 | 0.9457 | -0.1333 | 0.5225 | -0.0243 | 0.0724 | 0.3248 | 0.2394 | 0.2822 | 0.0840 | 0.5370 | 0.1808 | 0.2822 | 0.2989 | 0.5166 |

### Holdout (104-week) metrics

| candidate | ann_return | ann_vol | sharpe | max_dd | calmar | cvar_5 | turnover | upside | downside | avg_bil | avg_spy | avg_offense | avg_defense | avg_cash | recovery | calm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 bucket_refined | 0.1570 | 0.0719 | 2.1836 | -0.0558 | 2.8145 | -0.0192 | 0.0818 | 0.4578 | 0.2540 | 0.2063 | 0.0939 | 0.5840 | 0.2097 | 0.2063 | 0.7742 | 0.9020 |
| R2 light_abstention | **0.1582** | 0.0734 | 2.1549 | -0.0572 | 2.7672 | -0.0198 | 0.0819 | **0.4634** | 0.2588 | 0.2008 | 0.0930 | **0.5960** | 0.2032 | 0.2008 | 0.7576 | 0.8858 |
| R3 fast_narrow_regret | 0.1556 | 0.0702 | **2.2157** | **-0.0542** | **2.8695** | **-0.0186** | 0.0792 | 0.4496 | 0.2450 | 0.2120 | 0.0926 | 0.5705 | 0.2175 | 0.2120 | 0.7697 | 0.9144 |
| R4 combo | 0.1570 | 0.0719 | 2.1835 | -0.0558 | 2.8145 | -0.0192 | 0.0819 | 0.4579 | 0.2540 | 0.2063 | 0.0939 | 0.5841 | 0.2096 | 0.2063 | **0.7744** | 0.9018 |

For reference, production posts holdout ann_return 0.1537, Sharpe 2.0996,
max_dd -0.0566, recovery 0.5674, calm 0.7200. Q2 bucket posts ann_return
0.1552, Sharpe 2.2107, max_dd -0.0541, recovery 0.7690, calm (n/a).

### Pairwise vs production

| candidate | full Δ | holdout Δ | holdout SharpeΔ | bootstrap | rolling win | rolling meanΔ |
|---|---|---|---|---|---|---|
| Q2 bucket (reference) | +0.048 | -0.018 | +0.111 | 25.7% | 40.0% | +0.021 |
| **R1 bucket_refined** | +0.045 | -0.016 | +0.084 | 31.8% | 40.0% | +0.023 |
| **R2 light_abstention** | +0.042 | **-0.013** | +0.055 | **38.9%** | **46.7%** | **+0.025** |
| **R3 fast_narrow_regret** | +0.047 | -0.018 | **+0.116** | 26.8% | 40.0% | +0.019 |
| **R4 combo** | +0.045 | -0.016 | +0.084 | 31.8% | 40.0% | +0.023 |

### Pairwise vs Q2 bucket reference (does Phase R beat the Phase Q winner?)

| candidate | full Δ | holdout Δ | holdout SharpeΔ | bootstrap |
|---|---|---|---|---|
| R1 bucket_refined | -0.003 | +0.003 | -0.027 | **94.8%** |
| R2 light_abstention | -0.006 | +0.005 | -0.056 | **94.8%** |
| R3 fast_narrow_regret | -0.001 | +0.001 | +0.005 | **98.4%** |
| R4 combo | -0.003 | +0.003 | -0.027 | **94.9%** |

All four Phase R candidates clear the 60% bootstrap floor *against Q2 on
holdout excess return*, by large margins. In other words, Phase R is doing
what it was designed to do: improving on Q2 with high statistical support,
even though it is not yet enough to clear the production gate.

### Meta-allocation diagnostics

Bucket shares are identical across all four candidates because the bucket
rule and persistence are unchanged from Q2:

- `defense_production` — 67.5% of weeks
- `calm_trust` — 18.8% of weeks
- `recovery_trust` — 5.9% of weeks
- `ambiguous_abstain` — 7.8% of weeks

Average abstain weight by candidate:

- Q1 abstention_aware (reference): 0.341
- Q2 bucket (reference): 0.082
- R1 bucket_refined: 0.036 (-46% vs Q2)
- R2 light_abstention_overlay: 0.008 (-90% vs Q2)
- R3 fast_narrow_regret: 0.081 (same as Q2 by design)
- R4 combo: 0.036 (same as R1 by design)

R2's abstain overlay fires rarely in practice because the abstention score
crosses the 0.60 hard gate in only a small minority of weeks inside
`calm_trust`, `recovery_trust`, or `ambiguous_abstain`. That matches the
design intent — abstention as a tail tool, not a base mode.

Regret effect inside buckets: R3's fast regret shifted phaseo and phasen
shares within each bucket by ≤ 1 percentage point in practice. The 8-week EMA
is still a conservative modulator, but it reliably moved holdout Sharpe from
2.211 (Q2) to 2.216 (R3) without sacrificing raw return. R4's combo inherits
the same near-identical regret effect on top of R1's base mixes.

## F. Phase R interpretation

**What helped.** Two things independently moved the needle against production:

1. Removing the 8%-of-weeks abstain cushion inside `defense_production`
   (R2's headline change). That single edit pushed holdout raw Δ from -0.018
   (Q2) to -0.013 (R2), rolling win rate from 40% to **46.7%** (the closest
   any Phase Q/R candidate has come to the 55% bar), and bootstrap from
   25.7% to **38.9%** (the closest any candidate has come to the 60% bar).
   R2 also posts the best holdout raw_composite_position among all ML
   candidates (rank 4 of 13, behind only production, shadow, and phaseh).

2. Replacing the 20-week EMA regret with an 8-week narrow regret overlay
   that only swaps phaseo for phasen within the ML share (R3's headline
   change). That move took holdout Sharpe from 2.211 to **2.216** — the
   single highest Sharpe of any candidate in the cohort — with essentially
   no disturbance to bucket behavior, composite, or bootstrap.

**What did not help.**

- R1's more aggressive bucket-mix retune (lower production floor in
  `recovery_trust`, heavier ML share in `calm_trust`) closed a small
  additional fraction of the holdout composite gap but *cost* 0.027 in
  holdout Sharpe relative to Q2. Net effect: weaker candidate than both R2
  and R3.
- The R4 combo is essentially identical to R1. R3's narrow regret was
  designed to nudge phaseo vs phasen inside the existing bucket share,
  and on top of R1's already-refined base mix it had very little marginal
  room to move. So R4 is a redundant candidate.

**Did the refinement improve holdout raw-return / composite?**
Yes — R2 pushed holdout composite from 0.9446 (Q2) to 0.9496 (R2), closing
roughly 27% of the -0.018 gap to production. R1 and R4 pushed it to 0.9471.
R3 stayed flat at 0.9452. None closed the full gap.

**Did it preserve or improve holdout Sharpe?**
Preserved. All four still beat production by at least +0.055 (R2) and up to
+0.116 (R3). R3 actually produced the highest holdout Sharpe of any
candidate in the full cohort.

**Did abstention help when used lightly?**
Yes — but the "lightness" is where the win comes from. Removing the Q2
defense_production abstain cushion entirely (R2) was the single most
productive change in the sprint. The runtime overlay on top barely fires,
which is consistent with the finding that abstention should be rare.

**Did faster regret help?**
Yes marginally. The 8-week narrow regret moved holdout Sharpe from 2.211 to
2.216 with no other side effects. It did not close the raw-composite gap
because it was scoped to only reallocate within ML. That scoping was the
right design choice — it kept the bucket structure intact — but it limits
the possible raw-return lift.

**Did Phase R beat `improved_phaseq_regime_bucket_meta_allocator`?**
Yes, with strong bootstrap support. All four candidates clear 60% bootstrap
probability against Q2 on holdout (R1 94.8%, R2 94.8%, R3 98.4%, R4 94.9%).
R2 beats Q2 on holdout composite, rolling win rate, and bootstrap vs
production. R3 beats Q2 on holdout Sharpe.

**Did Phase R beat the production pin under the validation rules?**
No. All four remain below the holdout raw composite ≥ 0 gate, below the 55%
rolling win gate, and below the 60% bootstrap-vs-production gate. R2 gets
the closest on all three, simultaneously.

**What should be improved next.** The holdout raw-composite gap has shrunk
from -0.018 (Q2) to -0.013 (R2). Two structural tensions remain:

- **Downside capture.** Q2/R-family still has higher downside_capture (0.26
  holdout) than production (0.22). This is almost entirely a regime-timing
  artifact in `defense_production` — production holds more GLD, HYG, DBA
  during that bucket than the meta-allocator's weighted mix does. Closing
  this gap would require either reshaping the weighted blend inside
  `defense_production` to look more like pure production in adverse tape
  or adjusting the bucket rule to reclassify more adverse weeks *out of*
  `defense_production` and into the existing `ambiguous_abstain` path
  (which is production-heavy already).

- **Rolling win rate.** R2 got to 46.7%, but needs 55%. A plausible read is
  that the remaining gap is distributional: the ML branches outperform by
  a lot when they're right, and underperform by a smaller amount when
  they're wrong. Lifting rolling win rate probably requires attenuating
  ML share in the small number of weeks that drive the losses — not
  adding a new ML layer.

## G. Candidate classification

| candidate | classification | reason |
|---|---|---|
| R1 bucket_refined | **Research-only** | Full Δ +0.045 (passes), holdout Δ -0.016, bootstrap 32% — fails raw and bootstrap gates. Sacrifices 0.027 holdout Sharpe vs Q2. |
| **R2 light_abstention** | **Research-only (new trust-model reference)** | Best Phase R candidate on holdout Δ, bootstrap, rolling win. Closes ~27% of the remaining gap. Still below gates but clearly the direction of travel. |
| R3 fast_narrow_regret | **Research-only (Sharpe reference)** | Best holdout Sharpe in the cohort (2.216). Raw profile essentially identical to Q2. Useful as a pure Sharpe-max reference. |
| R4 combo | **Drop** | Redundant with R1. R3's regret overlay is mechanically consumed by R1's base-mix shift; no marginal gain. |

## H. Strategic diagnosis

**Did Phase R succeed?** Yes, partially — as a refinement, not as a pin
move. Phase R produced two new references (R2 for raw-composite /
robustness, R3 for Sharpe) that both clear 94%+ bootstrap support against
the Phase Q winner. The direction of the trust-model frontier is now much
clearer than it was at the end of Phase Q.

**Is the bucket-trust frontier still the right one?** Yes, but with caveats.
The frontier is plateauing in the classical sense — each Phase R candidate
closes a fraction of the remaining gap but none individually clears the
production gates. What has changed is the *shape* of the remaining
problem: it is no longer about finding the right trust structure (buckets
+ persistence has landed), it is about a narrow reshaping of the
`defense_production` blend and a narrow reduction in ML-share during
losing weeks.

**What should the next iteration focus on?** The next sprint (call it
Phase S if it runs) should test exactly two narrow things:

1. A `defense_production` internal tilt toward production's actual holding
   mix in adverse tape. This is not a new signal; it is recognizing that
   the weighted blend inside that bucket is over-diversifying away from
   production's specific adverse-tape holdings.

2. A conditional ML-share attenuator that reduces phaseo/phasen weight when
   rolling-origin realized excess return over the last 13 weeks is
   negative, applied inside trust buckets only. This is the smallest
   possible "loss-week insurance" intervention that could move rolling
   win-rate.

If those two moves together do not clear the production gate, the project
should stop refining the trust layer and look elsewhere (e.g. at the
upstream Phase 2B regime engine, which is the one component the trust
layer cannot see through).

## I. Final recommendation

- **Production pin — unchanged.** `improved_phase2b_regime_confidence_boost`
  remains the single production default.
- **Shadow pin — unchanged.** `improved_phase2b_combo_abc` remains the
  dual-track shadow.
- **Trust-model research reference — upgraded.**
  `improved_phaseq_regime_bucket_meta_allocator` (Q2) is superseded for
  research purposes by:
  - `improved_phaser_light_abstention_overlay_allocator` (R2) — the best
    holdout composite / robustness branch; the closest anything has come
    to the production gate
  - `improved_phaser_fast_narrow_regret_allocator` (R3) — the Sharpe-max
    branch; highest holdout Sharpe in the entire cohort
- **R4 combo — drop.** Redundant with R1 in practice.
- **Next step.** Phase S, narrowly scoped to the two remaining levers
  identified in H: reshape `defense_production` internal blend + conditional
  ML-share attenuator. If Phase S does not clear the production gate, stop
  refining the trust layer and reopen the upstream regime engine.

## J. Project journey log update

- **File updated:** `docs/research/project_journey.md`
- **Section added:** Section 31 — Phase R (Bucket-Trust Refinement)
- **Status:** The project narrative is now current through Phase R
  (2026-04-24). The log explains why Q2 became the trust-model reference,
  why this sprint focused on refining Q2 rather than opening a new
  frontier, what helped (R2 light abstention removal, R3 fast narrow
  regret), what did not help (R1 deeper bucket retune, R4 mechanical
  combo), and what comes next (targeted defense_production internal
  reshape + conditional ML-share attenuator in Phase S).
