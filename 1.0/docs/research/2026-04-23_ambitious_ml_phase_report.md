# Ambitious ML Phase — Decision-Aware, Uncertainty-Aware Multi-Sleeve Allocator

This sprint starts the broader ML phase explicitly called for at the end of the allocator-refinement branch.

The old allocator-refinement family is treated as complete and plateaued. The new question is no longer "can one more manual rule or structural objective tweak improve the refined panel?" It is:

> can a walk-forward ML stack learn conditional sleeve utility, uncertainty, and downside-aware concentration well enough to turn the refined redesigned panel into a more holdout-robust, turnover-aware, tail-aware allocator?

Production and shadow pins remain the same throughout this sprint:

- Production pin: `improved_phase2b_regime_confidence_boost`
- Shadow pin: `improved_phase2b_combo_abc`

The active sleeve panel also remains fixed:

- `dual_momentum_topn`
- `composite_calm_trend_specialist`
- `composite_healthier_recovery_specialist`
- `composite_anti_chop_clarity`
- `composite_regime_conditioned`
- `taa_10m_sma`

## Why this broader ML phase is justified now

By the end of Phase M, the project had enough evidence to close the allocator-refinement category.

What had been learned already:

- the refined redesigned sleeve panel is now role-complete enough for allocator work to matter
- `improved_phaseh_refined_state_allocator` proved that state-aware sleeve allocation can create real edge
- `improved_phasel_tail_turnover_learning_allocator` showed that decision-aware learning can help
- but repeated structural and learning refinements kept failing in the same way:
  - holdout raw composite remained below production
  - holdout Sharpe retention remained too weak
  - turnover remained elevated
  - drawdown / CVaR improvement was not strong enough to compensate

That means the bottleneck is no longer sleeve completeness or one more rule tweak. The bottleneck is the map from:

- sleeve opportunity
- role-aware state information
- uncertainty
- turnover cost
- downside / tail context

to an actual capital-allocation decision.

This sprint therefore moves from "allocator refinement" to a broader ML framing:

- sleeve utility / confidence / uncertainty modeling
- decision-aware allocation with explicit turnover and tail penalties
- one more ambitious but still controlled branch via mixture-of-experts gating

## Public research inputs used to shape the design

These were used as design guidance, not as substitutes for testing:

- [AQR — Machine Learning and the Implementable Efficient Frontier](https://www.aqr.com/insights/research/working-paper/machine-learning-and-the-implementable-efficient-frontier)
- [Robeco / Blitz et al. — How can machine learning advance quantitative asset management?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4321398)
- [Uziel & El-Yaniv (AISTATS / PMLR) — Long-and Short-Term Forecasting for Portfolio Selection with Transaction Costs](https://proceedings.mlr.press/v108/uziel20a.html)
- [A Universal End-to-End Approach to Portfolio Optimization via Deep Learning](https://arxiv.org/abs/2111.09170)
- [Adaptive Market Intelligence: A Mixture of Experts Framework for Volatility-Sensitive Stock Forecasting](https://arxiv.org/abs/2508.02686)
- [Parsimonious Quantile Regression of Financial Asset Tail Dynamics via Sequential Learning](https://arxiv.org/abs/2010.08263)

Practical takeaways applied here:

- treat trading costs and implementability as first-class constraints, not afterthoughts
- prefer models that are expressive but still diagnosable
- use distributional / quantile views when the bottleneck is tail discipline rather than point forecasting alone
- keep evaluation walk-forward and label-safe
- let expert specialization happen, but verify whether the gate actually adds useful differentiation

## What changed

New code:

- `scripts/phase_n_ambitious_ml_allocator.py`
- `scripts/phase_n_evaluate.py`

New candidate allocators:

1. `improved_phasen_uncertainty_adjusted_allocator`
2. `improved_phasen_distributional_tail_allocator`
3. `improved_phasen_moe_role_gating_allocator`

New artifact families:

- allocator summaries, sleeve/state allocation summaries, concentration summaries
- uncertainty summaries and confidence/uncertainty bucket diagnostics
- MoE gate summaries and gate-by-state diagnostics
- feature-importance summaries for the decision, tail, spread, and gate models
- Phase N evaluation tables using the fixed comparator set and Phase D rules

## ML design

### ML1 — sleeve utility / confidence / uncertainty model

The sprint builds a walk-forward sleeve-level ensemble instead of a single raw-return regressor.

Targets:

- `decision_target`: forward 4-week sleeve utility penalized for downside, realized vol, drawdown, tail mean, and fragile offensive exposure
- `tail_target`: a more conservative left-tail-aware version of the same target
- `high_value_label`: date-wise top-opportunity sleeve classification

Models:

- Ridge
- GradientBoostingRegressor mean model
- GradientBoostingRegressor q20 model
- GradientBoostingRegressor q80 model
- GradientBoostingClassifier for high-value sleeve probability

Uncertainty is modeled explicitly as:

- quantile interval width
- disagreement between linear and boosted models
- classifier entropy

This is more decision-relevant than predicting raw next return alone.

### ML2 — decision-aware allocator

The allocator maps predicted opportunity, conservative quantiles, uncertainty, and state-role priors into weights via the existing constrained objective framework.

What it adds relative to the old learning branch:

- uncertainty-scaled concentration
- uncertainty-scaled anchor / safe mix
- dynamic top-level cash sleeve
- explicit turnover and tail penalty adjustment by uncertainty and state risk
- continued role-aware floors / caps

### ML3 — ambitious comparison branch

`improved_phasen_moe_role_gating_allocator` adds:

- three expert models (`calm`, `recovery`, `defense`)
- a learned multinomial gate over date-level regime / spread features
- gate-conditioned blending of expert sleeve scores

This is the resume-worthy branch of the sprint, but it is benchmarked honestly against the simpler alternatives.

## Fixed comparator set for evaluation

Exactly as requested:

1. `improved_phase2b_regime_confidence_boost`
2. `improved_phase2b_combo_abc`
3. `improved_phaseh_refined_state_allocator`
4. `improved_phasel_tail_turnover_learning_allocator`
5. `improved_phasek_tail_aware_role_framework`
6. `improved_phaseh_refined_panel_blend`

## Full-history results

### Core comparators

| Version | Ann Ret | Vol | Sharpe | Max DD | Calmar | CVaR 5% | Turnover | Avg BIL | Avg SPY | Offense | Defense | Cash | Recovery | Calm | Raw Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `improved_phaseh_refined_state_allocator` | 0.0758 | 0.0874 | 0.8674 | -0.1497 | 0.5063 | -0.0284 | 0.0990 | 0.1336 | 0.1107 | 0.6427 | 0.2237 | 0.1336 | 0.3769 | 0.5999 | 0.5476 |
| `improved_phasel_tail_turnover_learning_allocator` | 0.0769 | 0.0861 | 0.8921 | -0.1507 | 0.5101 | -0.0281 | 0.1072 | 0.1241 | 0.1116 | 0.6338 | 0.2422 | 0.1241 | 0.3142 | 0.6049 | 0.5221 |
| `improved_phasek_tail_aware_role_framework` | 0.0737 | 0.0854 | 0.8626 | -0.1470 | 0.5013 | -0.0277 | 0.1091 | 0.1269 | 0.1073 | 0.6347 | 0.2384 | 0.1269 | 0.2620 | 0.5361 | 0.4922 |
| `improved_phaseh_refined_panel_blend` | 0.0753 | 0.0865 | 0.8700 | -0.1527 | 0.4929 | -0.0282 | 0.0835 | 0.1321 | 0.1061 | 0.6303 | 0.2376 | 0.1321 | 0.3538 | 0.5589 | 0.5200 |

### New ML candidates

| Version | Ann Ret | Vol | Sharpe | Max DD | Calmar | CVaR 5% | Turnover | Avg BIL | Avg SPY | Offense | Defense | Cash | Recovery | Calm | Raw Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `improved_phasen_uncertainty_adjusted_allocator` | 0.0731 | 0.0811 | 0.9011 | -0.1437 | 0.5087 | -0.0263 | 0.1040 | 0.1807 | 0.1069 | 0.6058 | 0.2135 | 0.1807 | 0.3097 | 0.5937 | 0.5296 |
| `improved_phasen_distributional_tail_allocator` | 0.0710 | 0.0767 | 0.9255 | -0.1271 | 0.5585 | -0.0249 | 0.0968 | 0.2107 | 0.1006 | 0.5785 | 0.2108 | 0.2107 | 0.3016 | 0.5819 | 0.5666 |
| `improved_phasen_moe_role_gating_allocator` | 0.0741 | 0.0826 | 0.8978 | -0.1454 | 0.5099 | -0.0268 | 0.1072 | 0.1661 | 0.1092 | 0.6130 | 0.2209 | 0.1661 | 0.3052 | 0.5858 | 0.5257 |

## Holdout results

### Production and current references

| Version | Ann Ret | Vol | Sharpe | Max DD | Calmar | CVaR 5% | Turnover | Avg BIL | Avg SPY | Offense | Defense | Cash | Recovery | Calm | Raw Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `improved_phase2b_regime_confidence_boost` | 0.1537 | 0.0732 | 2.0996 | -0.0566 | 2.7135 | -0.0204 | 0.0604 | 0.1940 | 0.0700 | 0.5899 | 0.2161 | 0.1940 | 0.5674 | 0.7200 | 0.9628 |
| `improved_phaseh_refined_state_allocator` | 0.1612 | 0.0847 | 1.9035 | -0.0695 | 2.3177 | -0.0219 | 0.1039 | 0.1011 | 0.1427 | 0.6825 | 0.2164 | 0.1011 | 0.6834 | 0.9379 | 0.9500 |
| `improved_phasel_tail_turnover_learning_allocator` | 0.1579 | 0.0822 | 1.9211 | -0.0717 | 2.2039 | -0.0220 | 0.1256 | 0.1054 | 0.1354 | 0.6719 | 0.2228 | 0.1054 | 0.6401 | 1.1081 | 0.9497 |

### New ML candidates

| Version | Ann Ret | Vol | Sharpe | Max DD | Calmar | CVaR 5% | Turnover | Avg BIL | Avg SPY | Offense | Defense | Cash | Recovery | Calm | Raw Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `improved_phasen_uncertainty_adjusted_allocator` | 0.1522 | 0.0784 | 1.9416 | -0.0635 | 2.3970 | -0.0202 | 0.1165 | 0.1568 | 0.1338 | 0.6483 | 0.1949 | 0.1568 | 0.6972 | 1.0264 | 0.9500 |
| `improved_phasen_distributional_tail_allocator` | 0.1492 | 0.0744 | 2.0043 | -0.0606 | 2.4638 | -0.0194 | 0.1111 | 0.1852 | 0.1244 | 0.6175 | 0.1973 | 0.1852 | 0.6335 | 1.0747 | 0.9500 |
| `improved_phasen_moe_role_gating_allocator` | 0.1529 | 0.0796 | 1.9198 | -0.0646 | 2.3655 | -0.0204 | 0.1211 | 0.1432 | 0.1369 | 0.6581 | 0.1987 | 0.1432 | 0.7091 | 1.0543 | 0.9500 |

## What helped

The clear winner of the sprint is:

- `improved_phasen_distributional_tail_allocator`

Why it helped:

- it is the only candidate that **beats `improved_phaseh_refined_state_allocator` on the main full-history raw composite** (`+0.019`)
- it also beats the current learning branch `improved_phasel_tail_turnover_learning_allocator` by `+0.044`
- it improves on the refined state allocator in the exact risk-adjusted dimensions the project actually needs:
  - Sharpe `+0.058`
  - max drawdown `+0.0226` (less severe)
  - CVaR `+0.0036`
  - turnover `-0.0022`
- on holdout it still shows:
  - Sharpe `+0.101` vs `improved_phaseh_refined_state_allocator`
  - max drawdown `+0.0090`
  - CVaR `+0.0025`

In other words, the best ML candidate does **not** improve by becoming more aggressive. It improves by producing a cleaner opportunity-to-risk tradeoff.

This matters.

It means the ML stack is actually learning something useful about uncertainty, not just levering beta.

## What did not help

### 1. Pure uncertainty adjustment helped, but not enough

`improved_phasen_uncertainty_adjusted_allocator` improved Sharpe and tail metrics versus the current learning and tail-aware references, but it still trailed `improved_phaseh_refined_state_allocator` on the full raw composite (`-0.018`).

Interpretation:

- the uncertainty penalty helped the risk profile
- but the mapping was still not selective enough about when to spend that risk budget

### 2. The MoE branch stayed interesting but not useful enough

`improved_phasen_moe_role_gating_allocator` was the eye-catching branch.

What happened:

- the gate used sensible state features (`transition_good_state_prob`, `transition_persistence_prob`, `calm_confidence`, `market_drawdown`, `risk_regime_score`)
- but the learned gate mostly collapsed into a calm-dominant router outside stressed states
- recovery specialization never became important enough to justify the added complexity

So the MoE story is honest:

- technically interesting
- diagnostically interpretable
- but not performance-justified in this sample

## ML diagnostics

### Feature importance / contribution

The strongest recurring drivers across the decision and tail models were:

- `prior_rank`
- `learning_weight`
- `tail_weight`
- `state_role_alignment`
- `dd_26`
- `vol_13` / `vol_26`
- `tail_mean_13` / `tail_mean_26`
- `benchmark_beta_26`

That is a useful result.

The best candidate is not acting like a naive momentum forecaster. It is using:

- prior sleeve-role structure
- prior allocator context
- tail / drawdown context
- and risk sensitivity to form opportunity scores

### Uncertainty / confidence behavior

For `improved_phasen_distributional_tail_allocator`:

- average model confidence = `0.224`
- average model uncertainty = `0.426`
- average cash sleeve weight = `0.102`
- average top-1 sleeve share = `0.314`
- average top-2 sleeve share = `0.590`

Concentration behaves sensibly:

- low-confidence / medium-uncertainty bucket: top-1 share `0.310`
- medium-confidence / medium-uncertainty bucket: top-1 share `0.335`

So the allocator does become more concentrated when confidence improves, which was one of the main design goals.

### Role-aware behavior by state

The best candidate preserves the refined panel’s role structure:

- calm-trend: highest average sleeve weights remain `taa_10m_sma` and `composite_calm_trend_specialist`
- recovery-confirmed: `composite_healthier_recovery_specialist` remains elevated
- stressed-panic: `composite_regime_conditioned` and `composite_anti_chop_clarity` remain the main defense sleeves

So the ML model is not destroying the economic role map. It is mostly changing:

- how much capital to keep in reserve
- how much offense to release when the predictive interval is wide versus narrow

## Validation summary

### Phase D rule

No candidate passes the production rule.

Why the best candidate still fails:

- holdout raw composite vs production remains `-0.0128`
- holdout Sharpe vs production remains `-0.095`
- holdout bootstrap outperformance probability vs production is only `29.4%`
- rolling raw win rate vs production is only `33.3%`

That means the new ML phase does **not** reopen production promotion yet.

### But the best candidate does establish a new research reference

`improved_phasen_distributional_tail_allocator` is the best non-production candidate in the sprint and the best overall research allocator now:

- best full-history raw composite among all non-production candidates in the fixed set
- best full-history Sharpe among the research allocator branches
- materially better drawdown and CVaR than `improved_phaseh_refined_state_allocator`
- slightly lower full-history turnover than `improved_phaseh_refined_state_allocator`
- best rolling average raw composite of the entire fixed comparison set (`0.609`)

## Candidate classification

- `improved_phasen_distributional_tail_allocator` — **Conditional**
- `improved_phasen_uncertainty_adjusted_allocator` — **Research-only**
- `improved_phasen_moe_role_gating_allocator` — **Drop**

## Strategic diagnosis

This broader ML phase is a success even without a production promotion.

Why:

- it produced a new best research allocator reference
- it directly attacked the real bottleneck instead of reopening sleeve search
- it added technically substantive ML structure:
  - distributional utility estimation
  - explicit uncertainty modeling
  - decision-aware constrained allocation
  - MoE gating as a controlled comparison branch
- it stayed walk-forward and Phase D anchored

The main lesson is also clear:

- **distributional / uncertainty-aware utility modeling helped**
- **extra architectural expressiveness alone did not**

The next ML iteration should therefore focus on:

1. better opportunity retention in recovery-confirmed windows without giving back the new tail gains
2. explicit Sharpe-retention / holdout-aware selection objectives instead of excess-return bootstrap alone
3. more direct calibration of uncertainty to realized sleeve-regret rather than only interval width + disagreement
4. a more selective recovery expert or expert-routing design if the MoE branch is reopened

## Final recommendation

- Production pin should remain unchanged: `improved_phase2b_regime_confidence_boost`
- Shadow pin should remain unchanged: `improved_phase2b_combo_abc`
- New ML allocator reference should replace `improved_phaseh_refined_state_allocator`
  - new reference: `improved_phasen_distributional_tail_allocator`
- Best older conditional learning branch remains informative historically, but the broader ML phase now supersedes it as the main research frontier

## Commands executed

- `python3 -m py_compile scripts/phase_n_ambitious_ml_allocator.py scripts/phase_n_evaluate.py`
- `python3 scripts/phase_n_ambitious_ml_allocator.py`
- `python3 scripts/phase_n_evaluate.py`

## Main artifacts

- `data/05_layer3_portfolio_construction/phase_n_allocator_variant_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_allocator_state_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_sleeve_allocation_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_sleeve_allocation_by_state.csv`
- `data/05_layer3_portfolio_construction/phase_n_concentration_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_concentration_by_state.csv`
- `data/05_layer3_portfolio_construction/phase_n_uncertainty_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_uncertainty_by_bucket.csv`
- `data/05_layer3_portfolio_construction/phase_n_gate_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_gate_by_state.csv`
- `data/05_layer3_portfolio_construction/phase_n_feature_importance_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_candidate_metrics_full.csv`
- `data/05_layer3_portfolio_construction/phase_n_candidate_metrics_dev.csv`
- `data/05_layer3_portfolio_construction/phase_n_candidate_metrics_holdout.csv`
- `data/05_layer3_portfolio_construction/phase_n_rolling_origin_summary.csv`
- `data/05_layer3_portfolio_construction/phase_n_pairwise_validation.csv`
- `data/05_layer3_portfolio_construction/phase_n_candidate_classification.csv`
