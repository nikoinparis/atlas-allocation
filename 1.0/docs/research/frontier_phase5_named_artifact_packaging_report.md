# Frontier Phase 5 Fragility Guard Named Artifact Packaging

**Mode:** production-candidate artifact packaging only. Live production pin unchanged.

## Stable Candidate

- Stable name: `improved_frontier_phase5_fragility_guard`
- Source research winner: `phase5_fragility_guard`
- Definition: exact stabilized GGG wrapper baseline plus Phase 1 R2A offense scaling and Phase 4 crowding guard.
- Phase 1 scale: `1 + 0.08 * clip(r2a, -1, 1)` outside `stressed_panic`.
- Fragility guard: when raw `leadership_quality_composite > 0.50`, cap any offense boost at zero.
- `stressed_panic`: unchanged.

## Artifacts Written

- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_frontier_phase5_fragility_guard.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_frontier_phase5_fragility_guard.csv`
- `data/05_layer3_portfolio_construction/production_candidate_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_state_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_exposure_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_registry.json`
- `data/research/frontier_phase10/named_artifact_packaging_summary.csv`

## Registry Safety

- `current_production_pin`: `improved_phase2b_regime_confidence_boost`
- `official_shadow_pin`: `improved_phase2b_combo_abc`
- `production_candidate`: `improved_frontier_phase5_fragility_guard`
- `candidate_status`: `FRONTIER_PHASE10A_PROMOTE_PENDING_HUMAN_REVIEW`
- Live production pin was not flipped.

## Metrics

| metric | current production | official shadow | frontier candidate |
|---|---:|---:|---:|
| full Sharpe | 0.8844 | 0.8836 | 0.9483 |
| full annual return | 6.8923% | 6.8584% | 7.1342% |
| max drawdown | -13.9754% | -13.6741% | -11.6035% |
| CVaR 5% | -2.6181% | -2.6085% | -2.4948% |
| holdout Sharpe | 2.0996 | 2.1130 | 2.1786 |
| avg BIL | 28.3918% | 28.5552% | 27.6060% |
| avg turnover | 5.6229% | 5.6571% | 6.7388% |

## Phase 10A Reproduction Check

| metric | named_artifact | phase10a_source | abs_diff |
| --- | --- | --- | --- |
| full_sharpe | 0.9482556438 | 0.9482556438 | 1.110223025e-16 |
| full_max_drawdown | -0.1160345789 | -0.1160345789 | 0 |
| full_cvar_5 | -0.02494792886 | -0.02494792886 | 6.938893904e-17 |
| avg_turnover | 0.06738780266 | 0.06738780266 | 2.775557562e-17 |

## Caveats

- The candidate is still pending human production review.
- The sleeve-weight file is a display/review proxy because the actual candidate is a wrapper modifier over final ETF weights.
- Public dashboard bundles were not regenerated in this sprint.

## Warnings

- None.
