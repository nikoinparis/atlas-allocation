# Stabilization Checkpoint Wrapper Design

Research-only design for a no-write allocator checkpoint wrapper.

## Wrapper Contract

- Reads saved production/candidate artifacts and allocator checkpoints.
- Writes only to `data/research/stabilization/` and `docs/research/` through caller scripts.
- Reproduces exact GGG when no modifier is supplied.
- Accepts optional modifier functions that return bounded modifier series.
- Logs checkpoint, modifier bounds, and average weight movement.
- Uses exact GGG return/cost/turnover conventions.

## Exposed Checkpoints

| checkpoint | source_stage | available | safe_for_frontier_research | dangerous_without_allocator_hook | source_path |
| --- | --- | --- | --- | --- | --- |
| raw_sleeve_targets | raw_hrp_sleeve_weights | True | False | True | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__raw_hrp_sleeve_weights.csv |
| regime_multipliers | post_state_tilt_sleeve_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_state_tilt_sleeve_weights.csv |
| offense_budget | post_layer3_expression_sleeve_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_layer3_expression_sleeve_weights.csv |
| defense_budget | post_layer3_expression_sleeve_weights | True | False | True | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_layer3_expression_sleeve_weights.csv |
| cash_bil_budget | post_overlay_pre_lookthrough_sleeve_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_overlay_pre_lookthrough_sleeve_weights.csv |
| transition_rerisk_smoothing | post_overlay_pre_lookthrough_sleeve_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_overlay_pre_lookthrough_sleeve_weights.csv |
| derisk_smoothing | post_overlay_pre_lookthrough_sleeve_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_overlay_pre_lookthrough_sleeve_weights.csv |
| volatility_risk_overlay | post_overlay_pre_lookthrough_sleeve_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_overlay_pre_lookthrough_sleeve_weights.csv |
| final_etf_lookthrough_weights | final_etf_weights | True | True | False | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__final_etf_weights.csv |
| cost_turnover_calculation | final_etf_weights | True | False | True | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__final_etf_weights.csv |

## Safe Checkpoints

- `regime_multipliers`: useful for tiny confidence/risk-budget offsets.
- `offense_budget`: useful for offense eligibility, dollar pressure, and risk-on participation rules.
- `transition_rerisk_smoothing`: useful for controlled re-risk timing research.
- `derisk_smoothing`: useful for deterioration acceleration and stress filters.
- `volatility_risk_overlay`: useful for confidence modifiers that should respect risk overlay intent.
- `final_etf_lookthrough_weights`: safe only as a comparison layer, not preferred for production design.

## Dangerous Checkpoints

- `raw_sleeve_targets`: upstream HRP and sleeve construction interactions are not faithfully invertible from saved final weights.
- `defense_budget`: easy to damage stressed_panic defense unless a full sleeve-aware allocator hook is available.
- `cost_turnover_calculation`: should not be modified by signals; it is measurement plumbing.

## Limitation

Early checkpoint modifications are represented by conservative final-weight proxy transformations. This stabilizes research comparisons, but a future no-write allocator hook should eventually insert modifiers before ETF look-through.
