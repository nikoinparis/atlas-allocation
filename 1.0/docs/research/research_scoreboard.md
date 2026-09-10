# Research Scoreboard

Living starter scoreboard for major research branches. Some rows are manually curated from known reports because project history is spread across many dated documents.

## Top Successful Ideas

| phase_or_branch | candidate_or_idea | what_worked | final_decision | source_doc |
| --- | --- | --- | --- | --- |
| Phase 2B | improved_phase2b_regime_confidence_boost / combo_abc | Became pinned production reference in registry; combo_abc remains important comparator. | Keep as pinned comparator | docs/research/phase2b_dual_track_summary.md |
| GGG / Phaseggg | improved_phaseggg_confirmed_only_robust_offense | Exact reconstruction succeeded with net-return max error near 2.1e-16 and correlation 1.0000. | Use as official research baseline | docs/research/path1_rebuild_report.md |
| Dollar Strength | r2_dollar_strength / bm_dollar_strength_4w / blended | Only strict R2 pass; 4w and blended variants remained useful diagnostics. | Reuse as confidence input | docs/research/dollar_strength_deep_dive_report.md |
| Breadth + Macro | ETF/sector breadth and state-gated macro | ETF breadth, sector breadth, risk-on participation, and gated macro showed real information. | Reuse through wrapper only | docs/research/breadth_macro_sprint_summary.md |
| Path 1/3 + Native Confidence | exact plumbing and confidence-aware deployment | Exact GGG reconstruction succeeded; confidence modifier nearly improved exact GGG. | Keep as architecture direction | docs/research/c7_native_confidence_sprint_summary.md |
| Stabilization | no-write checkpoint wrapper and rule harness | Wrapper reproduced exact GGG; rule harness ran standardized checks. | Use as mandatory framework | docs/research/deployment_architecture_stabilization_summary.md |
| Pre-frontier Validation | statistical validation, governance, scoreboard | Adds PSR/DSR proxy, purged CV utilities, PBO proxy, governance, and scoreboard. | Mandatory for frontier phase | docs/research/statistical_validation_layer.md |

## Useful Negative Results

| phase_or_branch | candidate_or_idea | what_failed | reason_for_decision | next_action | source_doc |
| --- | --- | --- | --- | --- | --- |
| B7/B8 | Controlled pass-through and bounded refinement | B7/B8 plumbing used wrong return/turnover convention versus exact GGG. | Deployment architecture, not raw signal discovery, became the bottleneck. | Do not repeat post-hoc scaling without exact wrapper. | docs/research/b8_sprint_summary.md |
| Q-V / Trust / ML Allocator | trust-aware and abstention meta-allocators | Repeated holdout residuals and plateau; Phase S recommended stopping narrow trust refinement. | Three-sprint failure mode suggests pivot. | Use lessons, not the old branch itself. | docs/research/2026-04-24_phase_s_targeted_trust_fix_report.md |
| ML Lab | rankers, attention, decision-focused, RL, triple barrier | High overfitting risk before deployment architecture is fully mature. | Governance says frontier ML comes after simpler deployment architecture. | Only revisit after transition-quality wrapper tests. | docs/research/ml_lab/phase_mlx_machine_learning_in_finance_study_guide.md |

## Open Branches

| phase_or_branch | candidate_or_idea | status | reuse_later | next_action |
| --- | --- | --- | --- | --- |
| Phase 2B | improved_phase2b_regime_confidence_boost / combo_abc | active reference | Yes | Always compare frontier candidates against Phase2B and GGG. |
| GGG / Phaseggg | improved_phaseggg_confirmed_only_robust_offense | current research benchmark | Yes | Use no-write wrapper for all deployment tests. |
| R1-R4 | Renaissance signal discovery foundation | completed | Yes | Use validated signals only through stabilized deployment harness. |
| Dollar Strength | r2_dollar_strength / bm_dollar_strength_4w / blended | promising | Yes | Keep in confidence and deterioration feature sets. |
| Breadth + Macro | ETF/sector breadth and state-gated macro | promising diagnostics | Yes | Test with allocator-native insertion points only. |
| B6 | Unified signal validation | completed | Yes | Use B6 table for future rule inputs. |
| B7/B8 | Controlled pass-through and bounded refinement | negative result | Yes, as a warning | Do not repeat post-hoc scaling without exact wrapper. |
| Path 1/3 + Native Confidence | exact plumbing and confidence-aware deployment | near miss | Yes | Use stabilized wrapper for transition-quality frontier. |
| Stabilization | no-write checkpoint wrapper and rule harness | completed | Yes | Run frontier tests only through wrapper/harness. |
| W1 / Structural Defense | structural defense / W1 sizing family | historical branch | Maybe | Parse W/AA reports in a future memory-cleanup sprint. |
| ML Lab | rankers, attention, decision-focused, RL, triple barrier | defer | Maybe later | Only revisit after transition-quality wrapper tests. |
| Pre-frontier Validation | statistical validation, governance, scoreboard | new | Yes | Use in every frontier sprint summary. |

## Ideas To Avoid Repeating Blindly

| phase_or_branch | candidate_or_idea | reason_for_decision | next_action |
| --- | --- | --- | --- |
| B7/B8 | Controlled pass-through and bounded refinement | Deployment architecture, not raw signal discovery, became the bottleneck. | Do not repeat post-hoc scaling without exact wrapper. |
| ML Lab | rankers, attention, decision-focused, RL, triple barrier | Governance says frontier ML comes after simpler deployment architecture. | Only revisit after transition-quality wrapper tests. |

## Notes

- This is a curated starter scoreboard, not a perfect automatic parser.
- Future sprints should append or regenerate rows when a branch is closed.
- The goal is research memory: what worked, what failed, and why.
