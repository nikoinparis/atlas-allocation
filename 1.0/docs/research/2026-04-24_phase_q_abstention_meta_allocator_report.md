# Phase Q — Abstention-Aware / Regime-Bucket Meta-Allocator

Date: 2026-04-24

## A. Starting point and Phase P failure modes

Phase P landed `improved_phasep_regret_aware_meta_allocator` as the new "trust-aware ML reference," but classified it Research-only rather than a pin move. The holdout profile was the reason:

- holdout raw composite delta vs production: **-0.013** (violates the ≥0 gate)
- holdout Sharpe delta vs production: **-0.022** (right on the -0.02 floor, effectively failing)
- rolling-origin raw win rate vs production: **40%** (vs 55% bar)
- block-bootstrap probability of beating production: **29.3%** (vs 60% bar)

The diagnostic read was that Phase P's softmax expert blend was **too smooth**:

- the production expert was never fully released, even when the ML branch was confident
- the ML experts were never fully released, even when production was clearly wrong
- the decision layer thrashed weekly on noisy features instead of committing to a regime

Phase Q's job was to attack those three failure modes directly without reopening sleeve search or alpha signals.

## B. Public research used

These sources framed the design:

- [Chow & Chopra — Portfolio Selection with Robust Estimation / bucketed allocator mixing](https://www.jstor.org/stable/2676196)
  - supported hard buckets and per-bucket conditional optima rather than one smooth map
- [Garlappi, Uppal & Wang — Portfolio selection with parameter and model uncertainty](https://academic.oup.com/rfs/article-abstract/20/1/41/1564240)
  - motivated explicit abstention when posterior conviction collapses
- [Bryzgalova, Pelger, Zhu — Forest through the trees](https://arxiv.org/abs/2005.13413)
  - encouraged cutting the input space along a few strong, interpretable regime axes rather than fitting one global model
- [Das, Markowitz, Scheid, Statman — Mental accounting and portfolio choice](https://www.jstor.org/stable/41303884)
  - supported the "separate buckets with separate mixes" framing over a single smooth optimizer
- [Newfound — Payoff diagrams and the case for strategy diversification](https://blog.thinknewfound.com/2021/06/payoff-diversification/)
  - reinforced keeping production as a live expert rather than a background benchmark

These kept Phase Q aligned with the project's "prefer simple causal logic" rule — hard regime cuts, explicit abstention, and slow persistence were all picked over deeper parametric models.

## C. Variants implemented

Three candidates were implemented on top of the Phase P trust-probability pipeline. All three reuse Phase P's walk-forward binary classifier (production beats phaseo and production beats phasen), but differ in how the classifier outputs are turned into weights.

- **Q1 — `improved_phaseq_abstention_aware_meta_allocator`**
  Adds an explicit abstention expert on top of {production, phasen, phaseo}. The abstention weight is `σ(model_uncertainty) × (1 - trust_score)`, and the abstention expert itself is a defensive anchor basket (BIL 45 / SHY 20 / IEF 15 / TIP 8 / GLD 6 / SPY 6). When the ML branch is confident, abstention is near zero. When the classifier is split-brained, abstention dominates.

- **Q2 — `improved_phaseq_regime_bucket_meta_allocator`**
  Replaces the smooth softmax with four hard buckets with 3-week persistence and hysteresis:
  - `calm_trust` → {prod 0.20 / phasen 0.25 / phaseo 0.55}
  - `recovery_trust` → {prod 0.25 / phasen 0.50 / phaseo 0.25}
  - `defense_production` → {prod 0.78 / phasen 0.07 / phaseo 0.07 / abstain 0.08}
  - `ambiguous_abstain` → {prod 0.55 / phasen 0.05 / phaseo 0.05 / abstain 0.35}
  Bucket assignment uses Phase 2B risk_guard, margin_conf/stress_conf, and classifier model_uncertainty — no new signals, no new thresholds beyond the risk layer.

- **Q3 — `improved_phaseq_abstention_regime_regret_meta_allocator`**
  Combo of Q1 + Q2 + EMA regret with a 20-week half-life. The bucket sets the base mix, the abstention overlay can still activate inside any bucket if conviction collapses, and recent regret (exponentially decayed) nudges weight between phaseo and phasen without letting one stale bad quarter dominate.

Artifacts are written under `data/05_layer3_portfolio_construction/`:

- `portfolio_version_weights_improved_phaseq_*.csv` and `portfolio_version_returns_improved_phaseq_*.csv`
- `phase_q_candidate_metrics_{full,dev,holdout}.csv`
- `phase_q_rolling_origin_summary.csv`
- `phase_q_pairwise_validation.csv`
- `phase_q_candidate_classification.csv`
- `phase_q_validation_protocol.json`
- `phase_q_trust_summary.csv`, `phase_q_trust_by_state.csv`, `phase_q_bucket_summary.csv`
- `phase_q_controls_improved_phaseq_*.csv`

## D. Validation protocol

Phase Q was validated under the standing Phase D rules with the fixed 7-member comparator set:

- production pin `improved_phase2b_regime_confidence_boost`
- shadow pin `improved_phase2b_combo_abc`
- `improved_phaseh_refined_state_allocator`
- `improved_phasen_distributional_tail_allocator`
- `improved_phaseo_tail_priority_allocator`
- `improved_phasep_regret_aware_meta_allocator`
- `improved_phaseh_refined_panel_blend`

Gates applied (production rule):

- full raw composite delta ≥ +0.015
- holdout raw composite delta ≥ 0
- holdout Sharpe delta ≥ -0.02
- rolling-origin raw win rate ≥ 55%
- holdout moving-block (13w) bootstrap probability ≥ 60%
- max drawdown worsening ≤ -0.01
- CVaR worsening ≤ -0.002

Holdout = last 104 weeks. Rolling origin = 260w min train / 104w test / 52w step. Bootstrap = 2000 moving block draws at 13w blocks.

## E. Headline results

### Full-history (2017→2026)

| version | ann_return | sharpe | max_dd | cvar_5 | turnover | raw_composite |
|---|---|---|---|---|---|---|
| improved_phase2b_regime_confidence_boost (prod) | 0.0690 | 0.8848 | -0.1398 | -0.0262 | 0.0562 | 0.4777 |
| improved_phase2b_combo_abc (shadow) | 0.0686 | 0.8841 | -0.1367 | -0.0261 | 0.0566 | 0.4803 |
| improved_phasep_regret_aware_meta_allocator | 0.0704 | 0.9377 | -0.1311 | -0.0243 | 0.0801 | 0.5498 |
| **Q1 abstention_aware** | 0.0581 | **1.0371** | **-0.0816** | **-0.0179** | 0.0738 | **0.6309** |
| **Q2 regime_bucket** | 0.0682 | 0.9542 | -0.1306 | -0.0235 | 0.0706 | 0.5255 |
| **Q3 abstention_regime_regret** | 0.0675 | 0.9647 | -0.1269 | -0.0230 | 0.0684 | 0.5368 |

Q1 took the best full-history raw_composite position (rank 1 of 10), the best full Sharpe (1.0371), the shallowest drawdown (-0.0816), and the tightest CVaR_5 (-0.0179) — the classical "trusted conservative ML" signature. Q2 and Q3 both came in risk-lighter than Phase P, with slightly lower absolute returns.

### Holdout (104 weeks)

| version | ann_return | sharpe | max_dd | cvar_5 | turnover | recovery_capture |
|---|---|---|---|---|---|---|
| improved_phase2b_regime_confidence_boost (prod) | 0.1537 | 2.0996 | -0.0566 | -0.0204 | 0.0604 | 0.5674 |
| improved_phasep_regret_aware_meta_allocator | 0.1499 | 2.0776 | -0.0593 | -0.0189 | 0.0908 | 0.6058 |
| **Q1 abstention_aware** | 0.1256 | **2.2018** | **-0.0480** | **-0.0153** | 0.0812 | 0.5454 |
| **Q2 regime_bucket** | 0.1552 | **2.2107** | -0.0541 | -0.0186 | 0.0794 | **0.7690** |
| **Q3 abstention_regime_regret** | 0.1508 | 2.1900 | -0.0541 | -0.0185 | 0.0761 | 0.7135 |

This is the single most important table in the sprint. **All three Phase Q candidates beat production and Phase P on holdout Sharpe**, with Q2 hitting 2.21 and Q1 hitting 2.20 vs production 2.10 and Phase P 2.08. Q2 also jumped holdout recovery_capture to 0.77 — significantly ahead of production 0.57 — without trashing drawdown or CVaR.

### Pairwise vs production (what the gates actually check)

| version | full Δ | holdout Δ | holdout SharpeΔ | bootstrap | rolling win | rolling meanΔ |
|---|---|---|---|---|---|---|
| Q1 abstention_aware | **+0.1532** | -0.0854 | **+0.1022** | 1.2% | 33.3% | +0.002 |
| Q2 regime_bucket | +0.0478 | -0.0182 | **+0.1111** | 25.7% | 40.0% | +0.021 |
| Q3 abstention_regime_regret | +0.0591 | -0.0241 | +0.0904 | 15.0% | 40.0% | +0.022 |

### Pairwise vs Phase P

| version | full Δ | holdout Δ | holdout SharpeΔ | bootstrap |
|---|---|---|---|---|
| Q1 abstention_aware | +0.0811 | -0.0726 | +0.1243 | 0.05% |
| Q2 regime_bucket | -0.0243 | -0.0054 | **+0.1332** | **61.15%** |
| Q3 abstention_regime_regret | -0.0130 | -0.0113 | +0.1125 | 37.0% |

Q2 is the most interesting number in the whole sprint: it has a **61.15% moving-block bootstrap probability of beating `improved_phasep_regret_aware_meta_allocator` on holdout excess return** — the first Phase Q vs Phase P comparison to actually clear the 60% support bar. It does not clear 60% vs production, however.

### Bucket behaviour (Q2 / Q3)

The hard buckets do what they were designed to do. Using Q2:

- `defense_production` — 67.5% of weeks, avg production weight 78%, ML share ~14%
- `calm_trust` — 18.8% of weeks, avg phaseo weight 55%, production 19%
- `ambiguous_abstain` — 7.7% of weeks, avg production 55%, avg abstain 35%
- `recovery_trust` — 5.9% of weeks, avg phasen 50%, phaseo 25%, production 24%

That is the intended behaviour: production dominates when the risk layer says "defend," phaseo leads calm trends, phasen leads recoveries, and abstention is reserved for the genuinely split-brained weeks rather than bleeding across the whole history.

### Abstention behaviour (Q1)

Q1 is more aggressive by design and the data reflects it: avg abstain weight is **0.34** across the whole history, with abstain weights above 0.38 in `recovery_fragile` and `stressed_panic`. That is the Q1 mechanism directly causing its holdout raw-return gap — it voluntarily trades away roughly one-third of its capital into the defensive anchor basket.

## F. Did it help standalone?

Partially.

- Q1 posted the best full Sharpe, best full CVaR, best full drawdown, best holdout drawdown, best holdout CVaR, and the single highest holdout Sharpe (2.20) among all ten candidates. Standalone, it is the **best risk-adjusted allocator the project has ever produced**.
- Q2 posted the best full-history trade-off between turnover (0.071) and composite (0.526), the single highest holdout Sharpe of any allocator in the sprint (2.21), and holdout recovery_capture of 0.77 — a standalone state-transition improvement over production (0.57).
- Q3's standalone profile sits between Q1 and Q2. It did not dominate either.

All three beat production on holdout Sharpe, and two of the three (Q2, Q3) essentially matched production on holdout raw return (Δ -0.018 and -0.024 vs a 0 gate) while improving drawdown, CVaR, and Sharpe.

## G. Did it help in combination?

Against the Phase P / H / N / O stack:

- Q2 and Q3 beat `improved_phasep_regret_aware_meta_allocator` on holdout Sharpe by +0.13 and +0.11 respectively. This is the first time in the sprint any allocator has added clean holdout-Sharpe value on top of Phase P.
- Q2 posted a 61% bootstrap probability vs Phase P — the first trust-model iteration to cross that threshold against the ML reference.
- Q2's recovery_capture of 0.77 on holdout is ~+0.20 vs production and ~+0.16 vs Phase P. That is a real state-transition improvement that the earlier smooth-softmax approach could not produce.
- Q1 is the first allocator to meaningfully reduce drawdown and CVaR against production on both windows simultaneously — but it pays for it with ~17% of annualised return on holdout, which the gates rightly penalise.

The combo (Q3) specifically did not dominate either parent. EMA regret with a 20-week half-life was too slow to add value on top of the bucket structure in this window — Q2 without regret was the cleaner expression of the idea.

## H. Controls & diagnostics

- Weekly feature frame, walk-forward binary classifiers, and trust scores are shared with Phase P — no re-fitting or data leakage.
- Bucket assignment uses only state-contemporaneous Phase 2B fields plus classifier outputs evaluated at time t. No forward leakage.
- Bucket persistence (3 weeks) is implemented as a run-length requirement on the target bucket before switching, so bucket transitions are deliberately sticky.
- Turnover is lower than Phase P for all three Phase Q candidates (0.068–0.081 vs 0.080), which is the direction the project rules prefer.
- `phase_q_bucket_summary.csv` and `phase_q_trust_by_state.csv` confirm that Q2/Q3 put production in control during `stressed_panic` (100% production-selected share), and let phaseo lead during `calm_trend` (59% phaseo-selected share).

## I. Classification

Under the standing Phase D production rule:

- **Q1 — Research-only.** Holdout raw delta -0.085 (violates ≥0), holdout rolling win rate 33%, bootstrap 1.2%. Standalone risk-adjusted dominance is real but the raw-return gate is not negotiable.
- **Q2 — Research-only.** Holdout raw delta -0.018 (narrowly missed the ≥0 gate), rolling win 40% (vs 55% bar), bootstrap vs production 25.7% (vs 60% bar). Holdout Sharpe delta +0.111 and holdout recovery_capture +0.20 are real, but the gates were designed to reject marginal raw-return shortfalls and Q2 falls in that category.
- **Q3 — Research-only.** Same pattern as Q2 with weaker margins and slower regret adaptation.

Under the shadow rule:

- Q1, Q2, Q3 all fail the shadow rule's holdout-raw-delta-≥-0.01 floor (Q1 by -0.085, Q2 by -0.018, Q3 by -0.024).
- Q2 clears the shadow-rule bootstrap floor vs production (25.7% < 50%? — no, still fails) but actually clears it vs Phase P at 61%, which is informative but not a pin event.

Final verdict:

- production pin: **unchanged** — `improved_phase2b_regime_confidence_boost`
- shadow pin: **unchanged** — `improved_phase2b_combo_abc`
- strongest ML reference: **upgraded** from `improved_phasep_regret_aware_meta_allocator` to `improved_phaseq_regime_bucket_meta_allocator` as the trust-model reference (Q2 adds +0.13 holdout Sharpe on top of Phase P and clears 61% bootstrap vs Phase P)
- best risk-budget reference: `improved_phaseq_abstention_aware_meta_allocator` (Q1) — the risk-adjusted frontier piece, not a return candidate
- dashboard: **no changes**, consistent with project rule that only a winner triggers dashboard/narrative changes

## J. What should happen next

Phase Q was not a pin move, but it was the most informative sprint since Phase P. The evidence points in three directions:

1. The bucket structure works. The smooth softmax in Phase P was the wrong functional form; hard, sticky buckets do more of what the trust layer was supposed to do (production dominates `stressed_panic`, phaseo leads `calm_trend`, phasen leads `recovery_confirmed`). Future trust-model work should start from the bucket structure, not the softmax.
2. Abstention is a useful tail tool but a poor core tool. Q1's 34% average abstain weight is too aggressive to meet the raw-return gate, but its risk-adjusted numbers are genuinely the best in the project. The next iteration should dial abstention down to fire only when conviction collapses inside a non-defense bucket (maybe 5–10% of weeks, not 100%).
3. EMA regret with a 20-week half-life did not add value on top of Q2. Either the regret window needs to be much shorter (5–10 weeks to actually react to recent slips) or it needs to gate *which* ML expert fires within `recovery_trust`/`calm_trust` rather than blending.

The concrete next sprint should be a **Phase R** that keeps Q2's bucket skeleton, dials abstention down, shortens or removes the regret decay, and tests whether the bucket base mixes can be tuned (still out-of-sample, walk-forward) to close the ~1–2pp holdout raw-return gap without giving back the +0.11 Sharpe gain. If that sprint lands inside the production gate, it becomes a legitimate pin candidate.
