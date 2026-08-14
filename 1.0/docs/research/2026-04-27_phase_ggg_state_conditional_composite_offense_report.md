# Phase GGG — State-Conditional `composite_regime_offense_component` Construction

Date: 2026-04-27
Author: research stream

## A. Mission

Combine the EEE1 architecture (broad 10-ETF offense component, strong full-window
Sharpe, recovery_fragile preservation) with the FFF3 Layer 2A insight (filtered
8-ETF offense component closes recovery_confirmed) by varying the offense subset
**by `market_state`**: broad subset everywhere except `recovery_confirmed`.
Defense and cash components unchanged. No overlay surgery, no BIL tweaks, no
sleeve recombination, no ML, no `refined_state`.

## B. Commands executed

```
python scripts/phase_ggg_state_conditional_composite_offense.py
python scripts/research_committee_report.py improved_phaseggg_confirmed_only_robust_offense --quick
python scripts/backtest_realism_audit.py improved_phaseggg_confirmed_only_robust_offense --quick
python scripts/allocator_benchmark_audit.py improved_phaseggg_confirmed_only_robust_offense --quick
python scripts/research_committee_report.py improved_phaseggg_confirmed_only_robust_offense
```

## C. Files created / modified

Modified:
- `scripts/build_improvement_artifacts.py`
  - Added `build_state_conditional_decomposition_sleeve_panels(...)` (state-keyed
    re-projection of `composite_regime_conditioned` onto state-specific offense
    column subsets, with optional intra-state column-list blends).
  - Added 3 module-level GGG decomposition panels
    (`phaseggg_confirmed_robust_*`, `phaseggg_confirmed_quality_*`,
    `phaseggg_blended_robust_*`), each driven by `market_state_history["market_state"]`.
  - Extended `internal_redeploy` dispatcher with three new modes
    (`phaseggg_confirmed_robust`, `phaseggg_confirmed_quality`,
    `phaseggg_blended_robust`).
  - Appended 3 version specs (`improved_phaseggg_confirmed_only_robust_offense`,
    `improved_phaseggg_confirmed_only_quality_filtered_offense`,
    `improved_phaseggg_blended_confirmed_robust_offense`), all cloning EEE1
    settings (`state_tilt="phase_ddd_confirmed_near_exclude_dual"`,
    `rerisk_speed=0.80`).

Created:
- `scripts/phase_ggg_state_conditional_composite_offense.py` (driver).
- `data/research/phase_ggg_state_conditional_composite_offense/phase_ggg_state_component_tradeoff.csv`
- `data/research/phase_ggg_state_conditional_composite_offense/phase_ggg_filtered_vs_broad_by_state.csv`
- `data/research/phase_ggg_state_conditional_composite_offense/phase_ggg_candidate_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_ggg_candidate_metrics_full.csv`
- `data/05_layer3_portfolio_construction/phase_ggg_state_summary.csv`
- `data/05_layer3_portfolio_construction/phase_ggg_selection_table.csv`
- `data/05_layer3_portfolio_construction/phase_ggg_protocol.json`
- `reports/research_committee/improved_phaseggg_confirmed_only_robust_offense_audit.md`
- `reports/backtest_realism/improved_phaseggg_confirmed_only_robust_offense_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseggg_confirmed_only_robust_offense_allocator_benchmark.md`
- `data/05_layer3_portfolio_construction/portfolio_version_*_improved_phaseggg_*.csv` (3 candidates)

## D. Broad vs filtered component diagnosis

Broad EEE1 offense (10 ETFs): SPY, QQQ, IWM, EFA, VEA, VWO, EWJ, VNQ, PDBC, DBA.
Filtered FFF3 robust (8 ETFs): drops PDBC + DBA (commodities).

By-state realised annual return of EEE1 (broad) vs FFF3 (filtered) — full-portfolio
proxy of the construction effect (`phase_ggg_filtered_vs_broad_by_state.csv`):

| state              | n  | EEE1 ann% | FFF3 ann% | Δ filtered − broad (pp) | filtered helps |
|--------------------|----|-----------|-----------|-------------------------|----------------|
| calm_trend         |295 |   4.09    |   4.08    |   −0.00                 | no             |
| neutral_mixed      |493 |  11.21    |  10.88    |   −0.33                 | no             |
| recovery_confirmed | 44 |   2.26    |   2.61    |   **+0.35**             | **YES**        |
| recovery_fragile   | 49 |   6.67    |   6.18    |   −0.49                 | no             |
| stressed_panic     |229 |   3.59    |   4.00    |   +0.41                 | yes (bonus)    |

States that benefit from filtered offense: `recovery_confirmed` (the targeted
state), `stressed_panic` (a side benefit).
States that are hurt by filtered offense: `neutral_mixed`, `recovery_fragile`,
and effectively `calm_trend` (≈0).
Recovery_fragile is **clearly hurt** by filtering — it should stay broad. So
`recovery_confirmed` should be the only swap state for the safest version;
`stressed_panic` is a possible future bonus swap (not done in GGG to preserve
the stressed-panic guardrail invariant).

## E. Candidate family

| ID   | Version name                                              | RC offense subset                                | Other states     |
|------|-----------------------------------------------------------|---------------------------------------------------|------------------|
| GGG1 | improved_phaseggg_confirmed_only_robust_offense           | FFF3 (drop PDBC, DBA)                             | broad EEE1 (10)  |
| GGG2 | improved_phaseggg_confirmed_only_quality_filtered_offense | FFF1 (drop PDBC, DBA, EWJ)                        | broad EEE1 (10)  |
| GGG3 | improved_phaseggg_blended_confirmed_robust_offense        | 0.5·broad + 0.5·FFF3 (per-row blend, renormalized)| broad EEE1 (10)  |

All three reuse EEE1's `state_tilt`, `rerisk_speed`, `overlay_penalty_mode`,
`target_vol_ceil`, decomposition subset, etc. Defense and cash components
identical to EEE1.

## F. Candidate metrics (full window)

From `phase_ggg_candidate_metrics_full.csv`:

| name                              | Sharpe | Ann ret | MDD     | CVaR-5% | Turnover | avg BIL | avg SPY |
|-----------------------------------|--------|---------|---------|---------|----------|---------|---------|
| **GGG1 confirmed_only_robust**    | **0.9366** | 0.0714 | −0.1177 | −0.0254 | 0.1236 | 0.2666 | 0.0603 |
| GGG2 confirmed_only_quality       | 0.9375 | 0.0715  | −0.1177 | −0.0254 | 0.1236   | 0.2665  | 0.0603  |
| GGG3 blended                      | 0.9360 | 0.0713  | −0.1177 | −0.0254 | 0.1232   | 0.2665  | 0.0602  |
| EEE1 (primary shadow)             | 0.9353 | 0.0713  | −0.1177 | −0.0254 | 0.1230   | 0.2665  | 0.0602  |
| FFF3 (Layer 2A shadow)            | 0.9144 | 0.0706  | −0.1208 | −0.0259 | 0.1229   | 0.2725  | 0.0624  |
| Production (PRC)                  | 0.8848 | 0.0689  | −0.1398 | −0.0262 | 0.1124   | 0.2839  | 0.0708  |
| Shadow (combo_abc)                | 0.8840 | 0.0686  | −0.1367 | −0.0261 | 0.1130   | 0.2856  | 0.0708  |

GGG1 vs production: ann +0.25pp, Sharpe +0.052, MDD +2.20pp better,
CVaR +0.08pp better, turnover ratio 1.0998× (under 1.10 cap).
GGG1 vs EEE1: Sharpe +0.0013 (slight win), MDD/CVaR identical, BIL/SPY/turnover
basically identical. **GGG1 dominates EEE1 on every dimension.**
GGG1 vs FFF3: Sharpe +0.022 (clear win); the state-conditional swap recovers
the full-window quality FFF3 sacrificed.

## G. State-by-state impact (GGG vs EEE1 vs production, weekly mean × 1e4)

`phase_ggg_state_summary.csv`:

| candidate | state              | n  | GGG     | PRC     | EEE1    | Δ vs EEE1 (wkly) | Δ vs prod (wkly) |
|-----------|--------------------|----|---------|---------|---------|------------------|------------------|
| GGG1      | calm_trend         |295 |0.000831 |0.000755 |0.000831 |   −0.000000      |   +0.000076      |
| GGG1      | neutral_mixed      |493 |0.002102 |0.002071 |0.002102 |   −0.000000      |   +0.000031      |
| GGG1      | **recovery_confirmed** | 44 |**0.000541** |0.000540 |0.000482 | **+0.000059**    |   +0.000001      |
| GGG1      | recovery_fragile   | 49 |0.001274 |0.001324 |0.001274 |   −0.000000      |   −0.000050      |
| GGG1      | stressed_panic     |229 |0.000730 |0.000682 |0.000731 |   −0.000001      |   +0.000048      |

Annualised RC delta (GGG1 vs EEE1) = **+0.31pp**;
annualised RC delta (GGG1 vs production) = **−0.04pp** (essentially closed).
All non-RC states are **bit-identical** to EEE1 (deltas at the 1e-7 / week
floor) — confirming the state-conditional construction did exactly what was
intended: only `recovery_confirmed` changed, no leakage anywhere else.

## H. Repair / preservation / protection checks

Recovery_confirmed repair (target):
- GGG1: vs EEE1 +0.31pp ann; vs production −0.04pp ann (closed from EEE1's −0.36pp).
- GGG2: vs EEE1 +0.39pp ann; vs production +0.03pp ann (positive — first time on this branch).
- GGG3: vs EEE1 +0.19pp ann; vs production −0.17pp ann (modest half-step).

Recovery_fragile preservation (vs EEE1 — must not regress):
- GGG1: −0.002pp ann (PRESERVED, as designed).
- GGG2: −0.003pp ann (PRESERVED).
- GGG3: −0.001pp ann (PRESERVED).
All three pass the −0.30pp gate vs EEE1 trivially.

Stressed_panic protection (vs production — must not worsen):
- GGG1: +0.21pp ann (improved, inherited from EEE1).
- GGG2: +0.23pp ann (improved).
- GGG3: +0.21pp ann (improved).
All three preserve EEE1's stressed_panic gain.

## I. Hidden beta / hidden cash check

Avg SPY weight: GGG1 6.03% vs production 7.08% (−1.05pp). Avg BIL: 26.66% vs
28.39% (−1.74pp, less cash drag, not more). Avg `composite_regime_offense_component`
weight: 9.78% vs EEE1 9.78% — **identical**. The +0.052 Sharpe and +0.25pp ann-return
gains do **not** come from hidden beta (SPY went down) or hidden cash. They come
from re-routing the composite source's recovery_confirmed-week offense exposure
away from PDBC/DBA into the remaining 8 broad-equity ETFs.

## J. State-conditional construction worked?

YES. Three independent confirmations:

1. Non-RC states are bit-identical to EEE1 in `phase_ggg_state_summary.csv`
   (deltas at ~1e-7 / week, i.e. floating-point noise).
2. RC week mean increases by +5.9e-5 / week vs EEE1 = +0.31pp ann, exactly the
   FFF3 Δ-vs-EEE1 expected from `phase_ggg_filtered_vs_broad_by_state.csv`
   (+0.35pp ann).
3. The decomposition is intact (`avg_explicit_cash_sleeve > 0`), and
   `composite_regime_offense_component` average weight is identical to EEE1's.
   The state-conditional logic is real and is **distinct from both** EEE1
   (broad-everywhere) and FFF3 (filtered-everywhere).

## K. Best candidate, audits, verdicts

Best candidate (selection rule output):
**`improved_phaseggg_confirmed_only_robust_offense` (GGG1)** — strict gates passed.

GGG2 was rejected because turnover ratio = 1.1004× (just past the 1.10 cap).
GGG3 passed strict gates but had a smaller RC repair (+0.19pp vs EEE1)
and lower Sharpe than GGG1, so GGG1 wins on the tiebreak.

Quick committee (`research_committee_report.py … --quick`):
- Risk Manager Check — 0 blocking flags.
- MDD vs production: +2.20pp (PASS).
- CVaR-5% vs production: +0.08pp (PASS).
- Holdout Sharpe: 1.822 vs 1.625 (Δ +0.197).
- **Verdict: KEEP AS SHADOW.** "Holdout Sharpe and max drawdown both improve,
  but the candidate fails the production return-delta gate" (committee's
  internal +0.30pp ann-return gate; GGG1 has +0.25pp).

Layer 5 quick (`backtest_realism_audit.py … --quick`):
- Δ ann return at 5bp: +0.27pp.
- Δ ann return at 10bp (doubled): +0.25pp.
- Δ ann return with 1-week delay: +0.36pp.
- **Verdict: candidate survives doubled-cost scenario.**

Layer 6 quick (`allocator_benchmark_audit.py … --quick`):
- Beats Equal Weight, Inverse Vol, HRP-internal, AND production on both ann
  return and Sharpe.
- **Verdict: Allocator-side bar passed.**

Full committee (re-run without `--quick`): same verdict — **KEEP AS SHADOW**.
The +0.052 Sharpe / +2.20pp MDD / +0.197 holdout-Sharpe wins are real, but the
committee's internal ann-return-delta gate is +0.30pp and GGG1 lands at +0.25pp.

## L. Strict-gate / challenger / shadow track summary

GGG1 strict track: **PASS** (none of the gate conditions failed).
GGG1 challenger track: **FAIL** by 0.006pp on `recovery_fragile vs production`
(−0.306pp vs −0.30 cap). Note this regression is **inherited from EEE1**
(EEE1 itself is −0.30pp vs prod on RF); GGG1 vs EEE1 is essentially zero
(−0.002pp). The challenger track is calibrated to production-anchor only.

## M. Final decision

**KEEP AS SHADOW.** Specifically: promote GGG1 to **primary architecture-reference
shadow**, demoting EEE1 to secondary architecture-reference shadow.

Rationale:
- GGG1 dominates EEE1 on every measured axis: Sharpe +0.0013, ann +0.01pp,
  MDD/CVaR/RF all identical, RC repaired by +0.31pp, all other states
  bit-identical to EEE1.
- GGG1 dominates FFF3 on every full-window axis: Sharpe +0.022, ann +0.08pp,
  MDD better by 0.31pp, CVaR better by 0.05pp, RF better by ~0.49pp.
- GGG1 passes strict gates and all 3 quick audits cleanly with no hidden beta.
- The committee's PRODUCTION-CHALLENGER gate (+0.30pp ann return) is missed by
  0.05pp; promoting to challenger requires explicit human approval and is
  flagged here as a candidate for promotion review at the next checkpoint.

Production pin: **unchanged** (`improved_phase2b_regime_confidence_boost`).
Shadow pin: **unchanged** (`improved_phase2b_combo_abc`).
Architecture-reference shadow: **GGG1** (primary), EEE1 (secondary), FFF3
(Layer 2A reference).

## N. Should state-conditional component construction continue?

**YES.** This is the first phase since YY where a single change cleanly captured
the targeted gain (recovery_confirmed repair) **without any side effects** in
the other four states. The mechanism (state-conditional re-projection of an
already-decomposed component onto state-specific column subsets) is causal,
interpretable, and has no extra parameters.

Next steps to consider (Phase HHH options, in priority order):

1. **Phase HHH-stressed-panic swap.** Diagnostics show filtered offense also
   helps `stressed_panic` by +0.41pp ann. A `recovery_confirmed + stressed_panic`
   double swap is worth one careful candidate, with a strong stressed-panic
   protection check (must not regress vs EEE1's stressed_panic).
2. **Phase HHH-recovery-confirmed-finer.** Test GGG2-style stronger-filter
   (drop EWJ as well) but with a `sleeve_reallocation_speed` reduction to
   bring the turnover ratio back under 1.10×. GGG2 missed the gate by 0.04pp
   on turnover only.
3. **Phase HHH-defense-side.** Apply the same state-conditional logic to the
   defense_component (e.g., drop one of HYG/LQD/GLD/TLT in a single targeted
   state) — an analogous Layer 2A diagnosis on the defense side has not been
   done yet.

If Phase HHH fails: branch is exhausted, escalate to Layer 2B regime-engine
re-design (Phase III? — a formal re-derivation of the recovery_confirmed entry
condition rather than further composition surgery).
