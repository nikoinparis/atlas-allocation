# Quant Verification Checklist — ETF Quant Research Committee

**Candidate:** {candidate}

This checklist is the consolidated set of pass/fail items the four prior
templates each touch. It exists as a single page that the human reviewer
can sign off in one pass.

## Layer-by-layer

### Layer 1 — alpha signals
- [ ] all signals computed from 1-week-lagged inputs
- [ ] no full-sample normalisation (rolling z-score, not global z-score)
- [ ] sign convention documented

### Layer 2A — strategy / sleeves
- [ ] all sleeve positions and net returns reproducible from
      `scripts/phase_a_*` style construction
- [ ] sleeve net returns include 5bp half-spread cost
- [ ] sleeve panel matches the candidate's intended panel (5-sleeve
      production, 7-sleeve W1-augmented, etc.)

### Layer 2B — regime engine
- [ ] regime labels computed walk-forward only
- [ ] no future information enters any state label or transition prob
- [ ] if a refined state file is used, the original
      `market_state_history.csv` is preserved untouched
- [ ] additive `defensive_overlay_hint` (or equivalent) is consumed as a
      tilt, not a hard categorical replacement, in any allocator

### Layer 3 — portfolio construction
- [ ] long-only, weights sum to 1, max sleeve cap respected
- [ ] cash ETF (BIL) used for the cash share
- [ ] turnover computed as weekly L1 sum
- [ ] cost computed as turnover × half-spread (5bp half-spread)
- [ ] same rebalance schedule as production (last business day of month
      by default)
- [ ] portfolio_version files saved as
      `portfolio_version_{returns,weights,sleeve_weights}_{name}.csv`

### Validation
- [ ] candidate metrics computed on full window AND on holdout
- [ ] dev/holdout split function reused from `phase_d_validate.py`
- [ ] rolling-origin walk-forward run via `phase_p_evaluate.rolling_evaluation`
- [ ] pairwise validation table includes deltas vs production AND vs U1A
- [ ] bootstrap probability vs production computed via
      `phase_p_evaluate.safe_bootstrap`
- [ ] Phase D 8-gate production rule applied via
      `phase_p_evaluate.PRODUCTION_RULE` thresholds
- [ ] candidate classification computed via the same `classify` function
      used by all prior phases

### Documentation
- [ ] `docs/research/YYYY-MM-DD_phase_*_report.md` present
- [ ] Section X appended to `docs/research/project_journey.md`
- [ ] CLAUDE.md updated only if the user has explicitly approved a pin
      change (otherwise CLAUDE.md is unchanged)

## Single-page sign-off

I have checked that the candidate satisfies the items above:

Reviewer name: ______________________
Date: _____________
Recommendation forwarded to Final Judge: __ Yes
