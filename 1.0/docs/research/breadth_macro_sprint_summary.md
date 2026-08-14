# Breadth + State-Gated Macro Intelligence Sprint Summary

Research-only sprint. No production pins, dashboard/public files, production portfolio artifacts, allocation logic, R5 ensemble logic, R6 meta-labeling integration, or live trading logic were changed.

## Exact Commands Run

Successful requested sprint commands:

```bash
.venv/bin/python scripts/build_breadth_signal_library.py
.venv/bin/python scripts/run_state_gated_macro_tests.py
.venv/bin/python scripts/build_signal_quality_features.py
.venv/bin/python scripts/run_dollar_strength_deep_dive.py
git status --short
```

Verification and safety commands:

```bash
.venv/bin/python -m py_compile scripts/build_breadth_signal_library.py scripts/run_state_gated_macro_tests.py scripts/build_signal_quality_features.py scripts/run_dollar_strength_deep_dive.py
.venv/bin/python - <<'PY'
from pathlib import Path
import pandas as pd
# checked expected output existence, shapes, and top verdict rows
PY
git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv
```

Engineering repair commands during the sprint:

```bash
# Two long-running pre-optimization B2 attempts were stopped after CPU-bound IC loops.
kill <run_state_gated_macro_tests.py pid>

# B4 failed once while rendering optional relationship columns, then was patched and rerun successfully.
.venv/bin/python -m py_compile scripts/run_dollar_strength_deep_dive.py && .venv/bin/python scripts/run_dollar_strength_deep_dive.py
```

## Files Created Or Modified

Scripts:

- `scripts/build_breadth_signal_library.py`
- `scripts/run_state_gated_macro_tests.py`
- `scripts/build_signal_quality_features.py`
- `scripts/run_dollar_strength_deep_dive.py`

Research docs:

- `docs/research/breadth_macro_sprint_discovery_note.md`
- `docs/research/breadth_signal_report.md`
- `docs/research/state_gated_macro_report.md`
- `docs/research/signal_quality_report.md`
- `docs/research/dollar_strength_deep_dive_report.md`
- `docs/research/breadth_macro_priority_rankings.md`
- `docs/research/breadth_macro_sprint_summary.md`

Summary outputs:

- `data/02_layer1_signals/breadth_signal_summary.csv` - 14 rows
- `data/02_layer1_signals/state_gated_macro_results.csv` - 49 rows
- `data/02_layer1_signals/state_gated_macro_state_detail.csv` - 1,155 rows
- `data/02_layer1_signals/signal_quality_features.csv` - 233,100 rows
- `data/02_layer1_signals/signal_quality_feature_validation.csv` - 6 rows
- `data/02_layer1_signals/dollar_strength_deep_dive.csv` - 5 rows
- `data/02_layer1_signals/breadth_macro_priority_table.csv` - 74 rows

Candidate signal panels were also written under `data/02_layer1_signals/signal_bm_*.csv`. These are research-only Layer 1 candidates with a one-week tradable lag.

## Breadth Findings

Breadth looks like a real frontier for this project, but the first pass is also very risk-on by construction. The strongest unconditional breadth candidates were:

- `bm_etf_above_50d_ma`: full IC 0.1182, holdout IC 0.1258, calm_trend IC 0.1236, stressed_panic IC 0.0833.
- `bm_etf_above_200d_ma`: full IC 0.1208, holdout IC 0.1258, calm_trend IC 0.1236, stressed_panic IC 0.0833.
- `bm_etf_positive_13w_mom`: full IC 0.1213, holdout IC 0.1258, calm_trend IC 0.1236, stressed_panic IC 0.0833.
- `bm_etf_positive_26w_mom`: full IC 0.1198, holdout IC 0.1258, calm_trend IC 0.1236, stressed_panic IC 0.0833.
- `bm_risk_on_participation`: full IC 0.1209, holdout IC 0.1201, calm_trend IC 0.1263, stressed_panic IC 0.0436.
- Sector breadth variants also looked constructive, especially 26-week sector momentum and 50/200-day sector MA breadth.

Risk-on minus defensive breadth and the equivalent signal-quality feature were useful in calm_trend but damaged stressed_panic, so they belong in the conditional/gated bucket rather than unconditional candidate-pass.

## Gated Macro Findings

The best state-gated macro candidates were:

- `r2_financial_conditions__recovery_only`: holdout IC 0.1973, calm_trend IC 0.0873, stressed_panic IC 0.0417; promising-if-gated.
- `r2_commodity_regime__recovery_only`: holdout IC 0.0993, calm_trend IC 0.2611, stressed_panic IC 0.0301; promising-if-gated.
- `r2_credit_spread__calm_trend_only`: holdout IC 0.0916, calm_trend IC 0.0581, no stressed_panic activation; candidate-pass under the simple gate.
- `r2_vix_term_structure__calm_trend_only`: holdout IC 0.0705, calm_trend IC 0.0738, no stressed_panic activation; candidate-pass under the simple gate.
- `r2_credit_spread__vix_below_past_median`: holdout IC 0.0662, calm_trend IC 0.0642, stressed_panic IC 0.0252; promising-if-gated.
- `r2_vix_term_structure__no_stressed_panic`: holdout IC 0.0546, calm_trend IC 0.0857, stressed_panic IC 0.0880; promising-if-gated.

Signals that remained dangerous under at least one gate:

- `r2_yield_curve__recovery_only`: stressed_panic IC -0.3431.
- `r2_cross_asset_divergence__recovery_only`: stressed_panic IC -0.3744.
- `r2_vix_term_structure__recovery_only`: stressed_panic IC -0.3744.
- `r2_dollar_strength__recovery_only`: stressed_panic IC -0.1397.

State-gating helped, but the result is not permission to promote macro signals. The evidence says macro/VIX/credit signals need explicit state restrictions before any R5-style ensemble test.

## Signal Quality Findings

Best meta/signal-quality features:

- `bm_quality_breadth_confirmation`: candidate-pass and effectively matches ETF 13-week breadth behavior.
- `bm_quality_signal_agreement`: useful but highly redundant with existing strong signals, so it is a gating/meta feature rather than a new standalone alpha.
- `bm_quality_signal_dispersion`: small positive full/holdout IC and no major stressed_panic damage.
- `bm_quality_risk_on_confirmation`: calm_trend useful but stressed_panic-damaging; promising only if gated.

Rejected or weak:

- `bm_quality_trend_efficiency`: holdout IC was negative and stressed_panic behavior was weak.
- `bm_quality_deterioration_warning`: rejected as signed in this first implementation; it likely needs decomposition or sign review before reuse.

## Dollar Strength Conclusions

Dollar strength remains broadly useful, but not every window is robust:

- `bm_dollar_strength_4w`: candidate-pass; full IC 0.0145, holdout IC 0.0221.
- `bm_dollar_strength_blended`: candidate-pass; full IC 0.0189, holdout IC 0.0197.
- `bm_dollar_strength_13w`: candidate-pass; full IC 0.0065, holdout IC 0.0081.
- `bm_dollar_strength_8w`: candidate-pass by the simple rules, but holdout IC was only 0.0005, so treat as weak.
- `bm_dollar_strength_26w`: rejected because holdout IC was negative.

The signal still looks more like a cross-asset pressure/filter feature than a broad standalone alpha. The 4-week and blended variants deserve follow-up; the 26-week variant should not be advanced.

## Best Calm Trend Candidates

- ETF 50-day and 200-day MA breadth.
- ETF positive 13-week and 26-week momentum breadth.
- Sector 13-week and 26-week momentum breadth.
- Risk-on participation.
- `r2_commodity_regime__recovery_only`.
- `r2_vix_term_structure__no_stressed_panic`.
- `bm_quality_signal_agreement`.
- `bm_quality_risk_on_confirmation`, but only with stress protection.

## Best Deterioration-Warning Candidates

- `r2_credit_spread__vix_below_past_median`.
- `r2_vix_term_structure__no_stressed_panic`.
- `r2_credit_spread__calm_trend_only` as a calm-only confirmation feature.
- ETF breadth deterioration should be revisited with sign/decomposition rather than using the rejected first-pass combined deterioration score.
- Risk-on minus defensive breadth is informative but dangerous unless explicitly suppressed in stressed_panic.

## PIT Data Needs

No PIT-dependent signal was implemented in this sprint. Future PIT/paid candidates remain:

- True constituent breadth.
- Advance/decline line.
- New highs/new lows.
- Sector and industry constituent participation.
- PIT sector valuation breadth.
- ETF flow data.
- Cboe put/call history if a clean historical feed is required.

## Signals To Reject Or Hold Back

- `bm_quality_deterioration_warning` as currently signed.
- `bm_quality_trend_efficiency` as a standalone candidate.
- `bm_breadth_change_4w`, `bm_breadth_momentum_13w`, and `bm_participation_acceleration` as standalone unconditional signals.
- Recovery-only versions of yield curve, cross-asset divergence, VIX term structure, and dollar strength if they retain stressed_panic damage.
- Dollar strength 26-week window.

## Recommended Next Sprint Before R5

Run a narrow B6 validation sprint before R5:

1. Rebuild breadth candidates with a cleaner distinction between participation confirmation and deterioration warning.
2. Test only the top breadth and gated macro candidates in a unified state-conditional validation table.
3. Add purged/walk-forward robustness and redundancy drift checks for the top 10.
4. Do not ensemble or allocate yet.
5. Advance only signals that survive calm_trend usefulness, holdout IC, stressed_panic safety, and redundancy gates.

## Production And Dashboard Safety

The production/dashboard safety diff was clean:

```bash
git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv
```

The command returned no output. No production pins, dashboard/public files, production candidate metrics, or production portfolio artifacts were changed.

`git status --short` remains dirty due to pre-existing research/untracked files plus this sprint's research outputs. The relevant new sprint files are the B1-B5 scripts, research docs, and `signal_bm_*` research-only candidate signal panels.
