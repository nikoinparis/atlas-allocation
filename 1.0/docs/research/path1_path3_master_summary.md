# Path 1 + Path 3 Master Summary

Research-only combined sprint. No production pins, dashboard/public files, production artifacts, R5/R6 logic, allocator rewrite, or live-trading logic were intentionally changed.

## Path 1 Answers

1. Why did B7/B8 fail? The sprint identified a concrete plumbing mismatch: B7/B8 used `weekly_returns.csv` with shifted weights and full L1 turnover, while GGG uses price-derived forward returns and one-way turnover.
2. Was sandbox plumbing materially different from real GGG? Yes. The return source/alignment and turnover convention were materially different.
3. Can GGG now be reconstructed accurately? `True`.
4. Does deployment location matter? Yes. Final-weight scaling is not equivalent to pre-overlay or overlay-native confidence changes because regime, target-vol, recovery budget, and look-through steps are nonlinear.
5. Is the project ready for future controlled pass-through? It is ready only if future tests use the exact GGG path or allocator-native checkpoints; B7/B8-style post-hoc plumbing should be retired.

## Rebuild Evidence

| rebuild_name | rebuild_ann_return | rebuild_sharpe | net_return_corr_vs_saved | net_return_max_abs_error | turnover_max_abs_error |
| --- | --- | --- | --- | --- | --- |
| exact_saved_final_etf_weights | 0.0714 | 0.9366 | 1.0000 | 0.0000 | 0.0000 |

B7/B8-style mismatch:

| rebuild_name | rebuild_ann_return | rebuild_sharpe | net_return_corr_vs_saved | net_return_max_abs_error | turnover_mean_abs_error | cost_mean_abs_error |
| --- | --- | --- | --- | --- | --- | --- |
| b7_b8_sandbox_plumbing | 0.0588 | 0.7683 | -0.1035 | 0.1252 | 0.0618 | 0.0001 |

## Deployment Location Evidence

| variant | ann_return | sharpe | max_drawdown | cvar_5 | delta_sharpe_vs_exact_ggg | promising |
| --- | --- | --- | --- | --- | --- | --- |
| dollar_pressure_location_proxy | 0.0713 | 0.9382 | -0.1177 | -0.0253 | 0.0016 | True |
| regime_aware_scaling | 0.0712 | 0.9363 | -0.1177 | -0.0253 | -0.0002 | True |
| defense_preserving_scaling | 0.0711 | 0.9355 | -0.1177 | -0.0253 | -0.0011 | True |
| post_hoc_weight_scaling | 0.0717 | 0.9348 | -0.1185 | -0.0255 | -0.0018 | True |
| offense_only_scaling | 0.0710 | 0.9342 | -0.1177 | -0.0253 | -0.0024 | True |

## Path 3 Answers

6. Did confidence-aware deployment look more promising? `True` based on the strict exact-GGG acceptance flag; use the table below for magnitude.
7. Did transition-quality estimation help? It is diagnostically useful if strong/broad buckets show higher success and lower whipsaw than weak/deteriorating buckets.
8. Did offense eligibility logic look useful? Eligibility rules are useful as diagnostics when allowed weeks show higher forward returns/lower whipsaw than suppressed weeks.
9. Are breadth/macro signals better used as confidence modifiers than direct alpha? Current evidence favors confidence/eligibility use over direct final-weight alpha.
10. Strongest deployment ideas: exact return plumbing, transition-aware gating, deterioration suppression, and overlay-native confidence mapping.
11. Fragile ideas: broad final-weight scaling, symmetric breadth pass-through, and any rule that cuts recovery/calm participation too often.

## Transition Quality Evidence

| transition_quality_bucket | n_transitions | success_rate_4w | whipsaw_rate_4w | avg_future_4w_ggg_return |
| --- | --- | --- | --- | --- |
| strong_broad | 59 | 0.3729 | 0.4576 | 0.0040 |
| constructive | 21 | 0.2857 | 0.4762 | 0.0040 |
| deteriorating | 4 | 0.2500 | 0.0000 | 0.0051 |

## Offense Eligibility Evidence

| rule_name | allowed_share | suppressed_share | future_return_lift_allowed_minus_suppressed | whipsaw_rate_allowed | whipsaw_rate_suppressed |
| --- | --- | --- | --- | --- | --- |
| strict_all_clear | 0.4486 | 0.5514 | 0.0027 | 0.2711 | 0.5911 |
| deterioration_suppression_only | 0.7559 | 0.2441 | 0.0022 | 0.2968 | 0.9179 |
| transition_quality_stable | 0.7225 | 0.2775 | 0.0010 | 0.3005 | 0.8328 |
| broad_breadth_low_deterioration | 0.5784 | 0.4216 | 0.0010 | 0.2882 | 0.6667 |
| risk_appetite_positive | 0.5820 | 0.4180 | 0.0005 | 0.2910 | 0.6659 |
| recovery_asymmetric_permission | 0.6631 | 0.3369 | 0.0005 | 0.2871 | 0.7634 |

## Confidence Sandbox Evidence

| variant | ann_return | sharpe | max_drawdown | cvar_5 | delta_sharpe_vs_exact_ggg | promising_vs_exact_ggg |
| --- | --- | --- | --- | --- | --- | --- |
| p3_combined_confidence_modifier | 0.0715 | 0.9395 | -0.1181 | -0.0253 | 0.0029 | True |
| p3_asymmetric_rerisking | 0.0716 | 0.9365 | -0.1182 | -0.0255 | -0.0001 | True |
| p3_confidence_offense_eligibility_mild | 0.0713 | 0.9364 | -0.1177 | -0.0253 | -0.0002 | True |
| p3_transition_aware_gating | 0.0714 | 0.9364 | -0.1177 | -0.0254 | -0.0002 | True |
| p3_confidence_bounded_scaling | 0.0716 | 0.9360 | -0.1183 | -0.0255 | -0.0006 | True |

## Strategic Answers

12. The bottleneck is now plumbing fidelity plus deployment architecture, transition-quality estimation, and confidence estimation rather than raw signal discovery.
13. R5 ensemble logic remains premature until allocator-native confidence mapping is tested with exact plumbing.
14. Exact next sprint: allocator-native confidence insertion test using saved checkpoints or a no-write wrapper around `run_subset_custom`, focused on overlay-regime multiplier offsets and transition-aware re-risk timing.
15. Production/dashboard files were not intentionally changed; the required final git diff command must remain clean.

## Warnings

- None.
