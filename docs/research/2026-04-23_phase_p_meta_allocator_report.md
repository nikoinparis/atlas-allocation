# Phase P — Meta-Allocator / Trust Model (ML Phase 3)

Date: 2026-04-23

## 1. Starting point diagnosis

ML Phase 1 and ML Phase 2 had already isolated the remaining bottleneck.

- Phase N showed that uncertainty-aware sleeve opportunity modelling was informative.
- Phase O showed that five allocator philosophies on top of the same ML signal all failed the same 104-week holdout gates.
- That means the remaining problem is not primarily "better sleeve signal" or "better weight mapping."
- The remaining problem is: **when should the system trust the ML allocator, and when should it fall back to production or a more conservative ML branch?**

This sprint therefore treated trust as the actual modelling target.

## 2. Public research used

These sources guided the design choices:

- [AQR — Machine Learning and the Implementable Efficient Frontier](https://www.aqr.com/Insights/Research/Working-Paper/Machine-Learning-and-the-Implementable-Efficient-Frontier)
  - motivated explicit attention to trading costs, implementability, and economic objectives rather than pure prediction error
- [Newfound — Ensemble Multi-Asset Momentum](https://blog.thinknewfound.com/2019/07/ensemble-multi-asset-momentum/)
  - supported the idea that a strategy-of-strategies can diversify process risk rather than forcing one specification to always be "on"
- [Uziel & El-Yaniv — Online Learning of Commission Avoidant Portfolio Ensembles](https://arxiv.org/abs/1605.00788)
  - directly relevant to dynamic expert mixing under transaction costs
- [Yang & Lucas — DMS, AE, DAA](https://arxiv.org/abs/2110.11156)
  - supported dynamic model selection / adaptive ensembling as a legitimate time-series learning problem
- [Robeco — Real-life experience: Using ML and distance-to-default to predict distress risk](https://www.robeco.com/en-us/insights/2024/02/real-life-experience-using-ml-and-distance-to-default-to-predict-distress-risk)
  - reinforced the value of ML when it captures nonlinear interactions and is judged on real out-of-sample use, especially for tail-related problems

These were used to justify:

- a small expert set
- explicit fallback to production
- turnover-aware trust decisions
- uncertainty-aware blending rather than "ML always on"

## 3. What was built

Three Phase P candidates were implemented:

1. `improved_phasep_hard_trust_switch_allocator`
   - binary walk-forward trust model
   - chooses either production or `improved_phaseo_tail_priority_allocator`

2. `improved_phasep_soft_trust_blend_allocator`
   - uses the same trust probability
   - blends continuously between production and `improved_phaseo_tail_priority_allocator`

3. `improved_phasep_regret_aware_meta_allocator`
   - learned trust probabilities for both `improved_phasen_distributional_tail_allocator` and `improved_phaseo_tail_priority_allocator` versus production
   - combines those probabilities with causal recent-regret and state features
   - blends across three experts: production, conservative ML (Phase N), and aggressive ML (Phase O)

The feature set included:

- state / transition / risk-regime features
- Phase N uncertainty, tail, gate and dispersion features
- Phase O confidence / uncertainty / penalty controls
- ETF-weight disagreement features across production / Phase N / Phase O
- role-exposure summaries from the refined-panel sleeves
- causal recent relative-quality and state-conditioned trust features

## 4. Core results

### Full history

| Candidate | Ann Return | Sharpe | Max DD | CVaR 5% | Turnover | Raw Composite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `improved_phasep_hard_trust_switch_allocator` | 0.0698 | 0.9056 | -0.1400 | -0.0251 | 0.0980 | 0.4798 |
| `improved_phasep_soft_trust_blend_allocator` | 0.0693 | 0.9048 | -0.1382 | -0.0253 | 0.0767 | 0.4888 |
| `improved_phasep_regret_aware_meta_allocator` | 0.0704 | 0.9377 | -0.1311 | -0.0243 | 0.0801 | 0.5498 |

### Holdout (last 104 weeks)

| Candidate | Ann Return | Sharpe | Max DD | CVaR 5% | Turnover | Raw Composite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `improved_phasep_hard_trust_switch_allocator` | 0.1537 | 2.0931 | -0.0601 | -0.0204 | 0.1220 | 0.9491 |
| `improved_phasep_soft_trust_blend_allocator` | 0.1540 | 2.1470 | -0.0577 | -0.0198 | 0.0842 | 0.9454 |
| `improved_phasep_regret_aware_meta_allocator` | 0.1499 | 2.0776 | -0.0593 | -0.0189 | 0.0908 | 0.9500 |

### Key comparisons

`improved_phasep_regret_aware_meta_allocator` was the strongest overall Phase P candidate:

- full raw composite delta vs production: **+0.072**
- full raw composite delta vs `improved_phaseh_refined_state_allocator`: **+0.002**
- holdout raw composite delta vs `improved_phaseh_refined_state_allocator`: **0.000**
- holdout Sharpe delta vs `improved_phaseh_refined_state_allocator`: **+0.174**
- holdout Sharpe delta vs `improved_phasen_distributional_tail_allocator`: **+0.073**
- holdout Sharpe delta vs `improved_phaseo_tail_priority_allocator`: **+0.094**

But it still failed the production gate:

- holdout raw composite delta vs production: **-0.0128**
- holdout Sharpe delta vs production: **-0.0220**
- rolling raw win rate vs production: **40%**
- bootstrap outperformance probability vs production: **29.3%**

## 5. Interpretation

### What helped

- The trust layer clearly improved the **ML-vs-ML** problem.
  - The regret-aware meta allocator matched the best holdout raw composite of the ML research branches and beat both on holdout Sharpe.
- It also materially improved **turnover** versus the always-on ML branches.
  - turnover 0.080 vs 0.097 for Phase N and 0.092 for Phase O
- It improved **tail discipline** versus production on full history.
  - max drawdown delta vs production: +0.0087
  - CVaR delta vs production: +0.0019

### What did not help enough

- The production pin still dominated on holdout composite.
- Rolling win-rate and bootstrap support did not confirm a reliable production replacement.
- Hard switching was too brittle.
- Soft blending improved holdout Sharpe, but gave up too much full-history composite strength.

### Was this just conservative fallback?

No.

The best candidate was not simply hiding in cash or reverting to production:

- full-history average BIL was **0.243**, lower than production's **0.283**
- full-history average offense was **0.566**, slightly above production's **0.553**
- holdout expert mix still allocated meaningfully to both ML experts:
  - production: **30.4%**
  - Phase N: **36.3%**
  - Phase O: **33.4%**

It was a real three-expert allocator, not just a disguised fallback.

### Did uncertainty matter?

Yes.

For the regret-aware meta allocator:

- correlation of Phase O weight with model uncertainty: about **-0.28**
- correlation of Phase N weight with model uncertainty: about **-0.33**
- correlation of Phase O weight with model confidence: about **+0.30**

So higher uncertainty did reduce ML trust.

## 6. Candidate classification

- `improved_phasep_hard_trust_switch_allocator` — Research-only
- `improved_phasep_soft_trust_blend_allocator` — Research-only
- `improved_phasep_regret_aware_meta_allocator` — Research-only

## 7. Recommendation

- Production pin remains `improved_phase2b_regime_confidence_boost`
- Shadow pin remains `improved_phase2b_combo_abc`
- New Phase P trust-aware research reference: `improved_phasep_regret_aware_meta_allocator`

This is the first trust-aware branch that:

- materially improves on the old pre-ML allocator reference
- keeps most of the ML branch's full-history edge
- improves holdout Sharpe retention versus the always-on ML allocators
- and does so without just falling back to static conservatism

## 8. Next step

The next ML iteration should stay on the meta-allocation frontier and focus specifically on:

1. improving rolling win-rate against production
2. improving bootstrap support rather than relying on average-delta wins
3. giving the trust model a more explicit abstention / low-conviction mode
4. testing whether trust should be learned over broader regime buckets with stronger regret decay, instead of relatively smooth blends every week
