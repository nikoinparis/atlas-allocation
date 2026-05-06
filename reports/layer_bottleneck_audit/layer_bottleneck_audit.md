# Layer 2A / 2B / 3 Bottleneck Audit

## Scope
- Diagnostic audit only. No production pin changes, no new candidates, no parameter optimization, no external dependencies.
- Production pin inspected: `improved_phase2b_regime_confidence_boost`.
- Primary question: where is the stack suppressing useful signal conversion into portfolio improvement?

## Commands Executed
- `python3 scripts/layer_bottleneck_audit.py`
- `rg --files data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction` to confirm saved artifacts.
- `sed -n '2815,2965p' scripts/build_improvement_artifacts.py` to verify the production construction checkpoints and missing instrumentation gaps.
- Supporting file inspection centered on `scripts/build_improvement_artifacts.py` and saved Layer 2A / 2B / 3 artifacts.

## Files Inspected
- `data/03_layer2a_strategy_logic/strategy_returns_<sleeve>.csv` and `strategy_positions_<sleeve>.csv` for production sleeves.
- `data/03_layer2a_strategy_logic/strategy_returns_baseline_market_proxy_buy_hold.csv`.
- `data/04_layer2b_risk_regime_engine/market_state_history.csv`.
- `data/04_layer2b_risk_regime_engine/market_state_history_refined.csv`.
- `data/04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv`.
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv`.
- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phase2b_regime_confidence_boost.csv`.
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phase2b_regime_confidence_boost.csv`.
- `data/05_layer3_portfolio_construction/allocation_driver_timeseries.csv`.
- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_timeseries.csv`.
- `data/05_layer3_portfolio_construction/stacked_defense_timeseries.csv` if present, else `stacked_defense_by_state.csv`.
- `docs/research/project_journey.md` and recent Phase JJ / KK-LL research notes for context.

## Missing Files / Missing Saved Checkpoints
- No saved raw HRP sleeve-weight checkpoint prior to `apply_state_conditioned_tilt`.
- No saved post-state-tilt sleeve-weight checkpoint prior to `apply_layer3_expression`.
- No saved post-layer3-expression sleeve-weight checkpoint prior to `apply_overlays_custom`.

## Key Bottleneck Findings
- Top bottleneck: **Layer 3 overlays/lighter_both** (MEDIUM). Regime binding rate 15.14% vs target-vol binding 0.18%; good-state BIL 17.39%.
- Second bottleneck: **Layer 2B regime-to-action mapping** (MEDIUM). Avg good-state confidence 0.53 with avg offense 61.77% and avg benchmark gap -7.45%.
- Third bottleneck: **BIL/cash drag** (MEDIUM). Average BIL in good-to-neutral opportunity states is 17.39% while production-vs-SPY ann gap is -7.45%.

## Layer 2A Sleeve Audit
- Production sleeves audited: dual_momentum_topn, cta_trend_long_only, composite_selective_signals, composite_regime_conditioned, taa_10m_sma.
- Sleeve-state rows flagged as weighted in a negative-Sharpe state: 1.
- Any-sleeve production cap hit rate: 1.17%.
- Highest-confidence Layer 2A misuses observed:
  - `composite_selective_signals` in `recovery_confirmed`: avg weight 23.11%, state Sharpe -0.18.

## Layer 2B Regime Mapping Audit
- Highest cash states:
  - `stressed_panic`: avg BIL 60.74%, avg offense 26.21%, prod-SPY gap -4.35%, diagnosis `too defensive`.
  - `neutral_mixed`: avg BIL 28.32%, avg offense 54.67%, prod-SPY gap -0.81%, diagnosis `approximately right`.
  - `recovery_fragile`: avg BIL 21.82%, avg offense 56.20%, prod-SPY gap -19.95%, diagnosis `re-risking too slow`.
- Worst production-vs-SPY states:
  - `recovery_fragile`: gap -19.95%, avg BIL 21.82%, confidence 0.55, tail 0.45.
  - `calm_trend`: gap -5.07%, avg BIL 6.85%, confidence 0.50, tail 0.25.
  - `stressed_panic`: gap -4.35%, avg BIL 60.74%, confidence 0.28, tail 0.76.

## Layer 3 Allocator / Overlay Audit
- Saved diagnostics show regime binding, target-vol binding, dynamic speed, self-gated relief, overlay cash, sleeve-internal BIL, and self/non-self risky overlay cuts.
- Saved diagnostics do **not** include raw HRP sleeve weights, post-tilt sleeve weights, post-layer3-expression sleeve weights, or pre-lookthrough sleeve weights as standalone checkpoints.
- The dominant question is whether the production overlay path is flattening good-state risk-taking more often than target-vol control is requiring.
- Overall regime binding rate is 15.14% versus target-vol binding 0.18%.
- Average overlay cash is 22.11%; average BIL is 28.39%; average SPY weight is 7.08%.

## Proposed Instrumentation Plan
- In `run_subset_custom`, log `raw` immediately before `apply_state_conditioned_tilt` as the raw HRP output.
- Log `raw` immediately after `apply_state_conditioned_tilt` as post-state-tilt sleeve weights.
- Log `raw` immediately after `apply_layer3_expression` as post-expression sleeve weights.
- Log `risky_weights` and `cash_weight` from `apply_overlays_custom` as post-overlay sleeve weights before ETF lookthrough.
- Log the ETF row returned by `build_lookthrough_etf_weights` before and after `apply_beta_participation_overlay`.

## Top 3 Bottlenecks
- `Layer 3 overlays/lighter_both` — MEDIUM. Regime binding rate 15.14% vs target-vol binding 0.18%; good-state BIL 17.39%. Affects: Upside capture, SPY participation, raw return. Next test: `offensive participation ceiling/cap audit`.
- `Layer 2B regime-to-action mapping` — MEDIUM. Avg good-state confidence 0.53 with avg offense 61.77% and avg benchmark gap -7.45%. Affects: Holdout robustness, neutral/calm conversion. Next test: `offensive participation ceiling/cap audit`.
- `BIL/cash drag` — MEDIUM. Average BIL in good-to-neutral opportunity states is 17.39% while production-vs-SPY ann gap is -7.45%. Affects: Annual return, upside capture. Next test: `offensive participation ceiling/cap audit`.

## Recommended Next Phase
- **offensive participation ceiling/cap audit**.
- Rationale: the audit points more strongly to suppressed offensive conversion and cash/overlay friction than to missing predictive information.

## Phase MM ML Retrain Before Structural Allocator Work?
- **No**. Current evidence says the next priority should be the bottleneck at the top of this audit rather than another prediction refresh first.

## Full Bottleneck Ranking

| Rank | Bottleneck | Severity | Affected Metric | Next Phase | Scope | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Layer 3 overlays/lighter_both | MEDIUM | Upside capture, SPY participation, raw return | offensive participation ceiling/cap audit | small tweak | Regime binding rate 15.14% vs target-vol binding 0.18%; good-state BIL 17.39%. |
| 2 | Layer 2B regime-to-action mapping | MEDIUM | Holdout robustness, neutral/calm conversion | offensive participation ceiling/cap audit | small tweak | Avg good-state confidence 0.53 with avg offense 61.77% and avg benchmark gap -7.45%. |
| 3 | BIL/cash drag | MEDIUM | Annual return, upside capture | offensive participation ceiling/cap audit | small tweak | Average BIL in good-to-neutral opportunity states is 17.39% while production-vs-SPY ann gap is -7.45%. |
| 4 | offensive participation ceiling | MEDIUM | SPY participation, recovery capture | offensive participation ceiling/cap audit | small tweak | Average offensive exposure in good-to-neutral opportunity states is 61.77%. |
| 5 | defensive sleeve design | LOW | State efficiency, tail carry cost | defensive sleeve redesign | architectural change | 1 sleeve-state rows show meaningful production weight in a negative-Sharpe state. |
| 6 | Layer 3 caps/normalization | LOW | Concentration flexibility, offensive participation | offensive participation ceiling/cap audit | small tweak | Any-sleeve cap hit rate is 1.17% with production max sleeve weight fixed at 45%. |
| 7 | Layer 2A sleeve quality | LOW | Diversification efficiency, allocator choice set | sleeve pruning/reweighting | small tweak | 0 production sleeves are flagged as redundant or weaker high-correlation copies. |
| 8 | Layer 3 HRP allocation | LOW | Weight efficiency | in-allocator W1 dual-bucket architecture | architectural change | HRP allocates into a correlated 5-sleeve set with cap hit rate 1.17%. |
| 9 | transaction cost/turnover | LOW | Net return | recovery re-risking speed test | small tweak | Production turnover is meaningful but not the dominant limiter relative to cash drag and overlay binding. |
| 10 | Layer 2B regime prediction | LOW | Signal quality | targeted Phase 2B ML refresh | small tweak | Current audit found more evidence of suppressed action than of missing state signal; recent ML phases also improved prediction more than portfolio conversion. |
