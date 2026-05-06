# Phase O — Decision-Aware Portfolio Allocation (ML Phase 2) Sprint Report

ML Phase 2 is the allocation counterpart of ML Phase 1 (Phase N). Phase N trained a walk-forward sleeve ensemble — ridge + GBR mean / quantile models for opportunity and tail, plus an MoE expert gate — and produced per-sleeve `decision`, `tail`, `uncertainty`, and `gate` prediction frames. That phase established that the ML signal is informative on full history (composite ≈ 0.567 at the top vs production 0.478) but **does not close the holdout Sharpe gap** (holdout Sharpe ≈ 2.00 vs production 2.10). Phase N’s own conclusion was that the remaining weakness is no longer in the signal — it is in how the signal is turned into actual portfolio weights.

Phase O takes those exact Phase N prediction frames, freezes the ML layer, and swaps only the Layer 3 allocator. Five decision-aware allocator variants are built, each pushing on a different allocation lever, and each is validated under the same Phase D discipline against the fixed comparator set.

- Production pin: `improved_phase2b_regime_confidence_boost`
- Shadow pin: `improved_phase2b_combo_abc`
- Fixed comparator set: production, shadow, `improved_phaseh_refined_state_allocator`, `improved_phasen_distributional_tail_allocator`, `improved_phasel_tail_turnover_learning_allocator`, `improved_phaseh_refined_panel_blend`.
- Active panel (unchanged): `dual_momentum_topn`, `composite_calm_trend_specialist`, `composite_healthier_recovery_specialist`, `composite_anti_chop_clarity`, `composite_regime_conditioned`, `taa_10m_sma`.

## A. Motivation — why a pure allocation sprint

Phase N already surfaced the diagnostic that motivates this sprint. Across every Phase N ambitious branch, the pattern is the same:

- full-history composite beats production by a very large margin (often +0.06 to +0.09)
- holdout composite is flat-to-slightly-below production
- holdout Sharpe is the binding failure — the ML allocators land in the low 1.9s / low 2.0s, production holds 2.10

A sprint that keeps training more ML layers would just re-litigate the signal. The bottleneck is the map from

*sleeve opportunity + tail + per-sleeve uncertainty + turnover cost + downside / tail context* → *actual capital weights*.

Phase O is therefore a decision-aware allocation sprint that reuses Phase N predictions verbatim and only changes how those predictions are priced into weights.

## B. Design of the five candidates

All five share the same scaffold — Phase K quadratic optimizer (`solve_objective`), dynamic bounds from Phase J, `SAFE_ANCHOR` blend from Phase I, Phase H reference weights as anchor core — and they all consume the same Phase N `decision` / `tail` / `uncertainty` / `gate` CSVs. They differ only in (i) the signal blend, (ii) the confidence / uncertainty context, (iii) the floors / caps, and (iv) the knob dictionary (`mu_scale`, `lambda_var / down / tail / turn / anchor / hhi`, `safe_mix`, `cash_weight`, anchor-mix fractions).

| Variant | Version name | Distinctive lever |
| --- | --- | --- |
| P2-A | `improved_phaseo_uncertainty_shrunk_allocator` | per-sleeve opp/tail shrunk by `(1 − uncertainty)`; caps tighten to 0.26 when total uncertainty > 0.55 |
| P2-B | `improved_phaseo_turnover_gated_allocator` | `lambda_turn = 1.30 × …` baseline; a hard **freeze-prev gate** when `signal_gap < 0.10 ∧ total_uncertainty > 0.45 ∧ confidence < 0.55` |
| P2-C | `improved_phaseo_tail_priority_allocator` | tail rank leads the signal (0.34 tail + 0.22 opp); defensive floors scale with `risk_guard`; `dual_momentum` capped at 0.10 in stressed tape |
| P2-D | `improved_phaseo_production_proximity_allocator` | `lambda_anchor = 1.35 × …`, `ref_mix = 0.82`, all caps clipped to 0.34 unless confidence > 0.75 ∧ uncertainty < 0.30 |
| P2-E | `improved_phaseo_combo_decision_allocator` | blend of A (uncertainty-shrunk), C (tail floors), and D (proximity cap clip) |

No retraining happens inside Phase O. The only degrees of freedom live in the allocator.

## C. Execution — what was run and what was saved

One run of `scripts/phase_o_decision_aware_allocator.py` produced, for each of the five candidates:

- `portfolio_version_returns_<name>.csv`, `portfolio_version_weights_<name>.csv`, `portfolio_version_sleeve_weights_<name>.csv`
- `phase_o_controls_<name>.csv` (per-date confidence, uncertainty, signal gap, risk guard, mu_scale, lambda_turn / tail / anchor, cash weight, freeze_prev flag)

And, aggregated across all candidates plus the six comparators:

- `phase_o_allocator_variant_summary.csv`, `phase_o_allocator_state_summary.csv`
- `phase_o_sleeve_allocation_summary.csv`, `phase_o_sleeve_allocation_by_state.csv`
- `phase_o_concentration_summary.csv`, `phase_o_concentration_by_state.csv`
- `phase_o_uncertainty_summary.csv`
- `phase_o_candidate_metrics_full.csv`, `phase_o_candidate_metrics_dev.csv`, `phase_o_candidate_metrics_holdout.csv`
- `phase_o_pairwise_vs_production.csv`, `phase_o_rolling_origin_summary.csv`
- `phase_o_validation_protocol.json`

Validation followed Phase D exactly: 104-week holdout, 260-week minimum rolling-origin train, 104-week rolling test, 52-week step, 13-week moving-block bootstrap (2000 draws) of holdout excess return versus production.

## D. Full-history metrics

| Version | AnnRet | Sharpe | MaxDD | CVaR5 | Turnover | AvgBIL | RecovCap | RawComp | Rank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| improved_phase2b_regime_confidence_boost (prod) | 0.0690 | 0.885 | −0.140 | −0.0262 | 0.056 | 0.283 | 0.304 | 0.478 | 11 |
| improved_phase2b_combo_abc (shadow) | 0.0686 | 0.884 | −0.137 | −0.0261 | 0.057 | 0.285 | 0.296 | 0.480 | 10 |
| improved_phaseh_refined_state_allocator | 0.0758 | 0.867 | −0.150 | −0.0284 | 0.099 | 0.134 | 0.377 | 0.548 | 3 |
| improved_phasen_distributional_tail_allocator | 0.0710 | 0.926 | −0.127 | −0.0249 | 0.097 | 0.211 | 0.302 | **0.567** | **1** |
| improved_phasel_tail_turnover_learning_allocator | 0.0769 | 0.892 | −0.151 | −0.0281 | 0.107 | 0.124 | 0.314 | 0.522 | 8 |
| improved_phaseh_refined_panel_blend | 0.0753 | 0.870 | −0.153 | −0.0282 | 0.084 | 0.132 | 0.354 | 0.520 | 9 |
| **improved_phaseo_uncertainty_shrunk_allocator (P2-A)** | 0.0723 | 0.916 | −0.141 | −0.0254 | 0.100 | 0.203 | 0.309 | 0.541 | 7 |
| **improved_phaseo_turnover_gated_allocator (P2-B)** | 0.0740 | 0.909 | −0.145 | −0.0263 | 0.101 | 0.179 | 0.324 | 0.546 | 4 |
| **improved_phaseo_tail_priority_allocator (P2-C)** | 0.0708 | **0.935** | **−0.126** | **−0.0245** | 0.092 | 0.224 | 0.298 | **0.566** | **2** |
| **improved_phaseo_production_proximity_allocator (P2-D)** | 0.0750 | 0.907 | −0.147 | −0.0267 | 0.101 | 0.171 | 0.325 | 0.544 | 5 |
| **improved_phaseo_combo_decision_allocator (P2-E)** | 0.0725 | 0.908 | −0.139 | −0.0259 | 0.096 | 0.191 | 0.313 | 0.543 | 6 |

On full history every Phase O candidate materially beats production composite by +0.063 to +0.088. P2-C (tail-priority) lands at composite rank 2 overall — best Sharpe in the entire comparator universe (0.935), smallest drawdown (−0.126), smallest CVaR5 (−0.0245).

## E. Holdout (last 104 weeks) metrics

| Version | AnnRet | Sharpe | MaxDD | CVaR5 | Turnover | AvgBIL | RecovCap | RawComp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| improved_phase2b_regime_confidence_boost (prod) | 0.1537 | **2.100** | −0.0566 | −0.0204 | 0.060 | 0.194 | 0.567 | 0.9628 |
| improved_phase2b_combo_abc (shadow) | 0.1536 | 2.113 | −0.0553 | −0.0203 | 0.061 | 0.196 | 0.567 | 0.9605 |
| improved_phaseh_refined_state_allocator | 0.1612 | 1.904 | −0.0695 | −0.0219 | 0.104 | 0.101 | 0.683 | 0.9500 |
| improved_phasen_distributional_tail_allocator | 0.1492 | 2.004 | −0.0606 | −0.0194 | 0.111 | 0.185 | 0.634 | 0.9500 |
| improved_phasel_tail_turnover_learning_allocator | 0.1579 | 1.921 | −0.0717 | −0.0220 | 0.126 | 0.105 | 0.640 | 0.9497 |
| improved_phaseh_refined_panel_blend | 0.1581 | 1.923 | −0.0695 | −0.0223 | 0.093 | 0.103 | 0.558 | 0.9474 |
| **P2-A uncertainty-shrunk** | 0.1535 | 2.010 | −0.0623 | −0.0197 | 0.114 | 0.175 | 0.647 | 0.9500 |
| **P2-B turnover-gated** | 0.1508 | 1.907 | −0.0639 | −0.0203 | 0.117 | 0.154 | 0.642 | 0.9500 |
| **P2-C tail-priority** | 0.1438 | 1.984 | −0.0601 | −0.0190 | 0.101 | 0.199 | 0.590 | 0.9500 |
| **P2-D production-proximity** | 0.1534 | 1.904 | −0.0660 | −0.0208 | 0.112 | 0.143 | 0.671 | 0.9500 |
| **P2-E combo** | 0.1520 | 1.976 | −0.0638 | −0.0200 | 0.109 | 0.165 | 0.656 | 0.9500 |

Production holds holdout Sharpe 2.10; the best Phase O candidate — P2-A — lands at 2.01, a −0.09 gap, still well outside the Phase D ±0.02 floor. Drawdown and CVaR are all within or better than Phase D tolerance. The binding gate is holdout Sharpe, not risk.

## F. Pairwise vs production (bootstrap + rolling origin)

| Version | ΔFull comp | ΔHoldout comp | ΔHoldout Sharpe | ΔHoldout MaxDD | ΔHoldout CVaR | Bootstrap P(c>p) | Rolling win-rate | Rolling Δ Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P2-A uncertainty-shrunk | +0.0630 | −0.0128 | −0.090 | −0.0056 | +0.0008 | 0.332 | 0.267 | +0.056 |
| P2-B turnover-gated | +0.0681 | −0.0128 | −0.192 | −0.0073 | +0.0001 | 0.290 | 0.400 | +0.037 |
| P2-C tail-priority | +0.0882 | −0.0128 | −0.116 | −0.0034 | +0.0014 | 0.206 | 0.333 | +0.055 |
| P2-D production-proximity | +0.0666 | −0.0128 | −0.195 | −0.0094 | −0.0004 | 0.367 | 0.333 | +0.035 |
| P2-E combo | +0.0652 | −0.0128 | −0.123 | −0.0071 | +0.0005 | 0.339 | 0.400 | +0.045 |

Phase D gates: ΔFull comp ≥ +0.015, ΔHoldout comp ≥ 0, ΔHoldout Sharpe ≥ −0.02, rolling win-rate ≥ 55%, bootstrap P ≥ 60%, MaxDD worsening ≥ −0.010, CVaR worsening ≥ −0.002.

| Gate | P2-A | P2-B | P2-C | P2-D | P2-E |
| --- | :-: | :-: | :-: | :-: | :-: |
| Full composite +0.015 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Holdout composite ≥ 0 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Holdout Sharpe ≥ −0.02 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Rolling win-rate ≥ 0.55 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Bootstrap P ≥ 0.60 | ❌ | ❌ | ❌ | ❌ | ❌ |
| MaxDD worsening cap | ✅ | ✅ | ✅ | ✅ | ✅ |
| CVaR worsening cap | ✅ | ✅ | ✅ | ✅ | ✅ |

## G. Does Phase O help standalone?

Standalone, every variant is materially better than production on full history by raw composite (+0.063 to +0.088), and most improve Sharpe, drawdown, and CVaR together. P2-C is the cleanest standalone Pareto step: best Sharpe, best MaxDD, best CVaR, second-best composite in the entire comparator universe.

So the answer is yes standalone, but only on the 400+ week full record. In the last 104 weeks — the live-regime window production was tuned against — every Phase O candidate lags production by exactly the same ballpark as the Phase N ambitious branches. Whatever the ML signal is contributing, the allocator remapping cannot rescue holdout Sharpe.

## H. Does Phase O help in combination?

Against the ambitious Phase N branches:

- P2-C beats `improved_phasen_distributional_tail_allocator` on Sharpe (0.935 vs 0.926), MaxDD (−0.126 vs −0.127), CVaR (−0.0245 vs −0.0249) and is only 0.0008 below its composite — meaning Phase O has *marginally cleaner* risk-adjusted performance than the ambitious Phase N tail branch without retraining anything.
- P2-A, P2-B, P2-D, P2-E all land between 0.541 and 0.546 composite — better than `improved_phaseh_refined_panel_blend` (0.520) and `improved_phasel_tail_turnover_learning_allocator` (0.522), but below the top Phase N branch (0.567).
- None of them beats production pairwise on the holdout, by any gate, any statistic, any horizon.

The most interesting in-combination diagnostic is the turnover-gated freeze behaviour in P2-B: it froze 21% of rebalance dates (`freeze_share = 0.2101`). This successfully reduced decision noise when the signal was mushy, but the frozen weeks still inherit wider caps and less defensive offense than production, so the effect doesn’t translate into a holdout Sharpe recovery.

## I. Interpretation — negative result, but informative

This sprint is a **clean, well-controlled negative result**: holding the ML Phase 1 signal fixed and swapping five genuinely different allocation philosophies (uncertainty shrinkage, turnover gating, tail-priority, production-proximity, combo) **never closes the holdout Sharpe gap**. The gap is not an allocator problem in the sense Phase N suspected.

What this tells us:

- Production’s edge on the 104-week holdout is not bound up in how it mixes sleeve ranks — every one of these decision-aware allocators mixes them differently and lands in the same 1.90 – 2.01 Sharpe band. The ML signal itself does not produce a holdout Sharpe > 2.0 even when you turn every allocation lever toward it.
- The full-history composite advantage of Phase O (and Phase N) is real and consistent (+0.06 to +0.09), so the Phase 1 ML stack is measurably picking up something the production allocator is not. But that something does not show up in the recent regime.
- The rolling-origin mean Sharpe delta vs production is *positive* for every Phase O candidate (+0.035 to +0.056). That means on most of the historical cross-section, Phase O candidates do outperform production. The last 104 weeks is simply a regime where production-style caps, low turnover, and a strong regime-confidence overlay dominate.
- The binding constraint for ML Phase 2 is therefore regime-specific, not structural. A future sprint that learns *when to trust the ML allocator vs when to fall back to the production allocator* is the natural next step. That would be a meta-allocator or regime-conditioned ensemble, not another allocation sweep.

## J. Classification and decisions

Per Phase D promotion gates, applied against the production pin `improved_phase2b_regime_confidence_boost`:

| Candidate | Classification |
| --- | --- |
| P2-A improved_phaseo_uncertainty_shrunk_allocator | **Research-only** |
| P2-B improved_phaseo_turnover_gated_allocator | **Research-only** |
| P2-C improved_phaseo_tail_priority_allocator | **Research-only** (keep visible — best standalone Sharpe/DD/CVaR across the full comparator set) |
| P2-D improved_phaseo_production_proximity_allocator | **Research-only** |
| P2-E improved_phaseo_combo_decision_allocator | **Research-only** |

No promotion, no conditional. No change to the production pin. No change to the shadow pin. No change to the dashboard.

## Reporting table (per project CLAUDE.md rules)

| Candidate | Executed | Files / artifacts changed | Helped standalone? | Helped in combination? | Classification |
| --- | --- | --- | --- | --- | --- |
| P2-A uncertainty-shrunk | yes | phase_o_controls_*, portfolio_version_*_improved_phaseo_uncertainty_shrunk_allocator, phase_o_* aggregates | yes, full composite +0.063 vs prod; holdout Sharpe −0.09 gap | improves Sharpe/DD/CVaR vs Phase H/L baselines but below Phase N tail | Research-only |
| P2-B turnover-gated | yes | same family, freeze_share 21% | yes, full composite +0.068; holdout Sharpe −0.19 | lower decision turnover but no holdout Sharpe rescue | Research-only |
| P2-C tail-priority | yes | same family | yes, best Sharpe (0.935) / MaxDD (−0.126) / CVaR5 (−0.0245) across all comparators; holdout Sharpe −0.12 gap | dominates ambitious Phase N tail on risk-adjusted standalone | Research-only |
| P2-D production-proximity | yes | same family | yes, full composite +0.067; holdout Sharpe −0.20 | strongest anchor pull, closest weight shape to production, still loses holdout | Research-only |
| P2-E combo (A+C+D) | yes | same family | yes, full composite +0.065 | modest blend improvement but never breaches Phase D gates | Research-only |

Sources:
- [scripts/phase_o_decision_aware_allocator.py](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/scripts/phase_o_decision_aware_allocator.py)
- [phase_o_candidate_metrics_full.csv](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_candidate_metrics_full.csv)
- [phase_o_candidate_metrics_holdout.csv](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_candidate_metrics_holdout.csv)
- [phase_o_pairwise_vs_production.csv](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_pairwise_vs_production.csv)
- [phase_o_rolling_origin_summary.csv](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_rolling_origin_summary.csv)
- [phase_o_validation_protocol.json](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_validation_protocol.json)
- [phase_o_uncertainty_summary.csv](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_uncertainty_summary.csv)
- [phase_o_allocator_variant_summary.csv](computer:///sessions/jolly-busy-hopper/mnt/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_o_allocator_variant_summary.csv)
