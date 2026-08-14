# Track A Validation Governance Report

## Scope

- Production candidate: `improved_frontier_phase5_fragility_guard`
- Saved portfolio return artifacts inventoried: `317`
- Statistical audit candidates scanned: `358`
- Estimated trial count applied: `3869`
- Production candidate present in statistical audit: `False`

## Artifact Classes

| artifact_class | count |
| --- | --- |
| rejected | 311 |
| diagnostic-only | 2 |
| research-only | 2 |
| production | 1 |
| shadow | 1 |

## Production Statistical Warning

- PSR vs zero benchmark: `0.999988`
- DSR proxy with trial count: `0.729205`
- Multiple-testing adjusted support: `0.955244`
- Project PBO proxy median: `0.666667`

These are governance warnings, not retroactive de-promotion rules. The production artifact remains pinned only because it is the human-authorized conservative production candidate and now has exact reproduction checks.

## Promotion Gates

| gate | status | hard_gate | detail |
| --- | --- | --- | --- |
| registry_current_pin_matches | PASS | True | current_production_pin=improved_frontier_phase5_fragility_guard |
| registry_production_candidate_matches | PASS | True | production_candidate=improved_frontier_phase5_fragility_guard |
| exact_reproduction | PASS | True | report=data/research/track_a_production_hardening/production_reproduction_report.json |
| phase10a_pairwise_gates | PASS | True | source=data/research/frontier_phase10/final_candidate_phase_d_gates.csv |
| statistical_audit_presence | WARN | False | Current production candidate was not present in the saved statistical audit; project-level trial count is still applied. |
| multiple_testing_warning | WARN | False | trial_count=3869, scanned_candidates=358 |
| cost_sensitivity | PASS | False | source=data/research/track_a_production_hardening/production_cost_sensitivity.csv |
| holdout_metrics_present | PASS | True | holdout_start=2024-04-19, holdout_sharpe=2.178585178584977 |
| manual_promotion_required | PASS | True | This script cannot promote candidates. Future production status requires explicit registry edit and hard-gate report. |

## Bootstrap / Rolling Support

| comparison | p_cand_gt_base | mean_delta | ci95_lo | ci95_hi | n_boot | rolling_win_rate |
| --- | --- | --- | --- | --- | --- | --- |
| FG_vs_GGG | 0.841 | 0.02984389709 | -0.02283280014 | 0.08064946135 | 2000 | 0.7333333333 |
| FG_vs_PROD | 0.8415 | 0.1739593997 | -0.2074661023 | 0.4793256325 | 2000 | 0.7333333333 |

## Outputs

- `data/research/track_a_production_hardening/experiment_registry_snapshot.csv`
- `data/research/track_a_production_hardening/production_promotion_gate_report.csv`
- `data/research/track_a_production_hardening/track_a_validation_governance_summary.json`
