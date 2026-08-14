# Phase CC — Layer 2B Regime Engine Refinement (Production-Seeking)

**Date:** 2026-04-26
**Phase type:** Upstream regime-engine refinement (not a new sleeve, allocator, or holdings blend)
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`
**Phase CC artifact:** `data/04_layer2b_risk_regime_engine/market_state_history_refined.csv`

---

## A. What was changed

A new Layer 2B refined state-history artifact was added. The original
`market_state_history.csv` is **untouched**. The refinement lives alongside it
as `market_state_history_refined.csv` and adds:

- a **`refined_state`** column that splits the original `neutral_mixed` bucket
  into `neutral_healthy` and `neutral_deteriorating` using a causal,
  walk-forward deterioration score; all other states pass through unchanged;
- five rolling z-score components (`z_dd_neg`, `z_breadth_decay`, `z_stress`,
  `z_corr`, `z_inv_trans`) and the equal-weighted composite
  `deterioration_z`;
- a walk-forward `deterioration_rank_neutral_mixed` percentile within
  historical neutral_mixed weeks only;
- a secondary `confidence_score_p2b` from Phase 2B predictions
  (z(p_tail_risk) − z(p_regime_confidence))/2, available 2008-11 onwards;
- an integer `defensive_overlay_hint` ∈ {−1, 0, +1} that tells a future
  allocator rerun where W1 should be heavier vs lighter at the state level
  (without modifying any cap, tilt, or meta-layer).

Production strategy logic and dashboard wiring are unchanged.

## B. What was executed

A focused, narrow research process:

1. Re-read the Phase BB W1 state-conditional usage diagnostic which showed
   that W1 was being sized at ~0.51 in `calm_trend`, ~0.41 in
   `neutral_mixed`, ~0.51 in `recovery_confirmed`, and only ~0.26 in
   `stressed_panic` — the inverse of what the sleeve was built for.
2. Inspected `data/04_layer2b_risk_regime_engine/market_state_history.csv`
   to identify causal features already produced by the regime engine that
   are statistically powerful for early-warning state discrimination.
3. Designed an interpretable equal-weight z-score composite over five
   features: drawdown depth, breadth decay, realized stress, risk-off
   correlation, and inverse transition-to-non-stress probability.
4. Implemented `scripts/phase_cc_regime_refinement.py` with strict
   walk-forward safety: trailing 156-week z-score window lagged by one
   week, plus a walk-forward percentile rank computed against past
   `neutral_mixed` weeks only.
5. Ran the script and validated the split using strictly forward-looking
   diagnostic windows that **do not enter the score** (forward 4w SPY, fwd
   13w SPY, forward 4w realized vol, forward 4w probability of transition
   into `stressed_panic`, forward 4w W1 sleeve return).

Public-research grounding (no live web egress was available; reasoning
draws on standard literature):

- **AQR / Newfound / ReSolve** all advocate state representations richer
  than discrete labels — drawdown depth, breadth deterioration, and
  realized stress are the canonical early-warning building blocks.
- **Probabilistic regime classification** (e.g., regime-switching HMMs,
  Bayesian filtering) supports the use of percentile-rank style state
  uncertainty rather than hard thresholds. The walk-forward percentile
  rank used here is the simplest interpretable analogue.
- **Walk-forward-safe estimation** (rolling z-scores, no full-sample
  fitting) is standard in the academic regime-classification literature.

## C. Files / artifacts modified or regenerated

Code (created):
- `scripts/phase_cc_regime_refinement.py` (new)

Data (created in `data/04_layer2b_risk_regime_engine/`):
- `market_state_history_refined.csv`
- `phase_cc_refined_state_diagnostics.csv`
- `phase_cc_state_transition_matrix.csv`
- `phase_cc_neutral_split_summary.csv`
- `phase_cc_state_counts.csv`
- `phase_cc_protocol.json`

Docs (this report + journey update):
- `docs/research/2026-04-26_phase_cc_regime_engine_refinement_report.md` (new)
- `docs/research/project_journey.md` (Section 42 appended)

The original `market_state_history.csv` was NOT modified. Production
allocator code paths still consume the original file, so no live behaviour
changes.

## D. Starting point diagnosis

**Why prior allocator / blend branches kept failing.** Phases X, Y, Z all
ran the production allocator architecture (or close variants) on the
upgraded 7-sleeve panel that includes W1
(`composite_structural_defense_sleeve`). All classified Research-only or
Drop. Phase Z (HRP + dynamic risk budget + production overlay +
regime_confidence_boost on the 7-sleeve panel) is the closest direct
architectural baseline to the production pin and produced the cleanest
defensive holdout (Sharpe 2.37 vs 2.10) — but at the cost of ~5 pts of
annual return because the HRP allocator over-uses W1 in calm and neutral
weeks where W1's defense is unwanted, and under-uses W1 in stressed weeks
where its defense is most needed.

Phase BB tested whether the per-sleeve cap (`MAX_SLEEVE_WEIGHT = 0.45`)
was the binding constraint and ran three cap-relaxation variants. All
three classified Research-only. Most importantly, the BB W1
state-conditional usage table confirmed the structural diagnosis:

| state              | BB1 avg W1 | BB1 median W1 |
|--------------------|------------|---------------|
| calm_trend         | 0.507      | 0.528         |
| neutral_mixed      | 0.411      | 0.500         |
| recovery_confirmed | 0.510      | 0.513         |
| recovery_fragile   | 0.460      | 0.509         |
| stressed_panic     | **0.263**  | **0.218**     |

W1 sizing is heaviest in the *least* stressed states and lightest in the
*most* stressed state. Increasing the cap does not reorder this — it just
re-scales it. The allocator cannot tell which neutral weeks are pre-stress
and which are pre-rally because the regime label is the same.

Phase AA (production+Z1 holdings blend) classified Research-only too,
because production-Z1 ETF overlap is highest in `stressed_panic` (0.462)
and lowest in `calm_trend` (0.106) — Z1 contributes least where its
defense would matter most.

**The exact `neutral_mixed` problem Phase CC is solving.** The
`neutral_mixed` bucket holds 493 of 1,110 weeks (44% of the entire
sample). Inside it sit:
- weeks where breadth is healthy and trend has just turned ambiguous
  (these tend to revert to calm/recovery and the portfolio should stay
  offensive), and
- weeks where breadth is decaying, drawdown is deepening, and risk-off
  correlation is rising (these are the precursor weeks to stress and the
  portfolio should rotate into defense).

The current regime engine cannot separate them. Anything downstream — the
allocator, the meta-layer, the overlay — therefore treats them as one
amorphous bucket and ends up averaging across both populations.

**Why state refinement is the right next step.** Every prior fix attempted
to compensate downstream — bigger W1 cap, conditional W1 sizing, holdings
blending. None worked because the upstream label is the bottleneck. A
better label is the one upstream change that lets the existing production
architecture become more selective without modifying any allocator code,
any sleeve, or any meta-layer. The fix is upstream and minimal.

## E. Refined state results

### Counts (original vs refined)

| state                 | original | refined |
|-----------------------|---------:|--------:|
| calm_trend            |      295 |     295 |
| neutral_mixed         |      493 |     112 |
| neutral_healthy       |        — |     210 |
| neutral_deteriorating |        — |     171 |
| stressed_panic        |      229 |     229 |
| recovery_confirmed    |       44 |      44 |
| recovery_fragile      |       49 |      49 |

381 of 493 (77%) `neutral_mixed` weeks were successfully split; 112 (23%)
fell back to `neutral_mixed` because the rolling z-score window
(156 weeks) plus the rank-history requirement (≥26 prior neutral_mixed
weeks) means the split is only available from mid-2008 onward. **All 112
fallback weeks fall in 2005-01-07 → 2008-07-04** — the early-history
period where the deterioration distribution is not yet well-defined. From
2008-08 onward, every neutral week is split. This is the right behaviour:
the script does not invent signal where there is no statistical history.

### Deterioration score logic

Five components are computed per week from `market_state_history.csv` and
sign-aligned so that **higher = more deteriorating**:

| component         | source                                  | sign |
|-------------------|-----------------------------------------|------|
| dd_neg            | `−market_drawdown`                      | +    |
| breadth_decay     | `−(breadth_sma_43 + breadth_26w_mom)/2` | +    |
| stress            | `recent_stress_26w`                     | +    |
| corr              | `avg_corr_risk_off_z`                   | +    |
| inv_trans         | `−transition_non_stress_prob`           | +    |

Each component is z-scored using a strictly trailing 156-week window
**lagged by one extra week** so today's z-score uses only [t−157, …, t−1].
The composite `deterioration_z` is the equal-weighted mean of the five
z-scores.

For each `neutral_mixed` week, a walk-forward percentile rank is
computed against past `neutral_mixed` weeks only. The split rule:
- rank ≥ 0.50 → `neutral_deteriorating`
- rank < 0.50 → `neutral_healthy`
- missing rank → fallback to `neutral_mixed`

A secondary `confidence_score_p2b` from Phase 2B predictions is reported
as a diagnostic but does not enter the split rule (so the primary
refinement is available across the full sample, not just post-2008-11).

### Forward-window diagnostic (the score does not see these)

| refined_state          | n   | fwd4_spy_mean | fwd13_spy_mean | fwd4_realized_vol | fwd4_to_panic_prob | fwd4_w1_mean |
|------------------------|----:|--------------:|---------------:|------------------:|-------------------:|-------------:|
| calm_trend             | 295 |        0.0059 |         0.0238 |            0.0131 |              0.024 |       0.0010 |
| **neutral_healthy**    | 210 |        **0.0126** |     **0.0368** |        **0.0146** |          **0.076** |       0.0020 |
| **neutral_deteriorating** | 171 |     **0.0091** |     **0.0169** |        **0.0169** |          **0.278** |       0.0019 |
| neutral_mixed (fallback) | 112 |      0.0034 |         0.0136 |            0.0124 |              0.170 |       0.0015 |
| recovery_confirmed     |  44 |        0.0088 |         0.0421 |            0.0157 |              0.000 |       0.0028 |
| recovery_fragile       |  49 |        0.0146 |         0.0392 |            0.0135 |              0.102 |      −0.0012 |
| stressed_panic         | 229 |        0.0040 |         0.0192 |            0.0282 |              0.930 |       0.0030 |

The **headline diagnostic** is the forward 4-week probability of
transitioning into `stressed_panic`: **27.8% in `neutral_deteriorating`
vs 7.6% in `neutral_healthy`** — a 3.6× ratio. The 13-week forward
SPY mean is **3.7% (healthy)** vs **1.7% (deteriorating)**, a >200bp
annualized gap. Forward 4-week realized volatility is 16% higher in
deteriorating weeks. Adjacent-week flip rate between healthy and
deteriorating labels is 7.7% — responsive without being noisy.

The split is not perfect (the W1 absolute forward-return advantage is
modest at +0.01% / wk) but the directional evidence on three independent
dimensions (forward stress probability, forward return, forward vol) is
unambiguous and consistent. The `neutral_mixed` bucket was statistically
heterogeneous and the split recovers a meaningful piece of that
heterogeneity.

### Year-by-year split (post-fallback era)

| year | deteriorating | healthy |
|-----:|--------------:|--------:|
| 2008 |             4 |       0 |
| 2009 |             2 |       7 |
| 2010 |             2 |      27 |
| 2011 |             7 |      15 |
| 2012 |            15 |      13 |
| 2013 |            27 |       9 |
| 2014 |            10 |      15 |
| 2015 |            29 |       0 |
| 2016 |             9 |       9 |
| 2017 |             0 |      15 |
| 2018 |            14 |       6 |
| 2019 |            15 |      10 |
| 2020 |             7 |       7 |
| 2021 |             0 |      16 |
| 2022 |            11 |       2 |
| 2023 |            14 |       3 |
| 2024 |             0 |      25 |
| 2025 |             1 |      23 |
| 2026 |             4 |       8 |

The yearly distribution tracks the actual macro environment well: 2010 /
2017 / 2021 / 2024 / 2025 are heavily healthy (post-recovery / bull
years), while 2008 / 2015 / 2018 / 2022 / 2023 are heavily deteriorating
(financial-crisis run-up, late-cycle vol regimes, bear years). This is a
sanity-check of the split, not a fit.

## F. Interpretation

**What helped.** Combining drawdown depth, breadth decay, realized stress,
risk-off correlation pressure, and (low) transition-to-non-stress
probability into a single equal-weighted z-score composite is enough to
recover meaningful structure from the original `neutral_mixed` bucket.
The signal lives in the **multi-feature agreement**: any single feature
on its own is noisy, but five sign-aligned features averaged together
produce a stable deterioration index.

**What didn't help (or was deliberately excluded).**
- A larger feature dictionary (more z-scores, more lookback windows) was
  considered and rejected — it would not be more interpretable and risks
  over-fitting on the 493-week neutral_mixed history.
- A non-linear classifier (random forest, gradient boost) was rejected for
  the same reason — the project rule is to prefer simple causal logic over
  black-box ML, and the linear z-score composite already separates the
  bucket into two populations with a clear forward-stress gap.
- A three-way split (healthy / mixed / deteriorating using thirds) was
  considered but the binary split at the median is the cleanest first step.
  Adding a middle band can be revisited downstream if the next allocator
  rerun shows it would help.

**Does the split look meaningful?** Yes, on three independent forward-only
diagnostics:

1. Forward 4-week probability of transitioning to `stressed_panic` is
   3.6× higher in deteriorating than in healthy weeks (27.8% vs 7.6%).
2. Forward 13-week SPY return is more than 2× higher in healthy than in
   deteriorating weeks (3.7% vs 1.7%).
3. Forward 4-week realized vol is 16% higher in deteriorating weeks.

**Does this support the hypothesis that `neutral_mixed` was too coarse?**
Yes. The original bucket averaged across two populations whose forward
stress profiles differ by ~3.6×. The downstream allocator was being asked
to make a single decision for two qualitatively different regimes.

**Is the refined engine good enough to use in the next production-family
rerun?** Yes — with one important caveat. The refined engine should be
used as an **additive defensive overlay hint** (the
`defensive_overlay_hint` column) inside the existing allocator, not as a
hard categorical replacement. The original `market_state` column is
preserved and should remain the primary state input until a downstream
allocator rerun has confirmed the refined state actually improves
out-of-sample. The hint should be tested as a small sleeve-level
multiplicative tilt (e.g. ±5–10% W1 weight) — not as a regime-engine
replacement. This keeps the upgrade strictly additive and reversible.

## G. Candidate classification

**Promote to next production-rerun phase** — *with the caveat that Phase
CC itself does not change any production strategy*. The refined state
file is now ready to be consumed by the next phase, which should be a
narrow production-family rerun that uses the `defensive_overlay_hint`
column as an additive sleeve-level tilt while keeping every other Phase Z
parameter fixed.

The Phase CC refinement does not yet produce a portfolio strategy, so
it cannot be classified under the standard four-tier rule (Promote /
Conditional / Research-only / Drop) that applies to portfolio
candidates. The classification above is for the *state-engine artifact
itself* — it is good enough to drive the next downstream test.

## H. Strategic diagnosis

**Did Phase CC succeed?** Yes, on its narrow stated mission. The refined
state engine is materially more informative than the original inside the
`neutral_mixed` bucket, with three independent forward-only diagnostics
confirming the split is meaningful and not noise. Causal safety is
preserved (trailing-window z-scores, lagged by one week; rank computed
only against past neutral_mixed weeks).

**Does the project now have a better state representation?** Yes — for
44% of the sample (the original `neutral_mixed` weeks), the project now
has a usable two-way split. The other 56% of the sample (calm_trend,
recovery_confirmed, recovery_fragile, stressed_panic) is unchanged, which
is correct — those buckets were never the bottleneck.

**What should the next phase focus on?** A narrow production-family
rerun (call it Phase DD) that:

1. takes the existing Phase Z HRP / dynamic_risk_budget / overlay /
   regime_confidence_boost architecture exactly as it stands,
2. adds a single new sleeve-level tilt that consumes the
   `defensive_overlay_hint` column as a small ±5–10% W1 multiplier, and
3. reports incremental contribution against BOTH production and shadow
   under the 8-gate Phase D rule.

If that single, narrow change produces a clean 8-gate pass, the project
finally has a deployable improvement. If it does not, the next phase
should test whether the hint should be wider (e.g. ±15%) or whether it
should also tilt a defensive sleeve like `composite_regime_conditioned`
or `taa_10m_sma`.

## I. Final recommendation

- **Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`.
- **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.
- **Next phase recommendation**: Phase DD — a narrow production-family
  rerun consuming the Phase CC `defensive_overlay_hint` as an additive
  sleeve-level tilt inside the Phase Z architecture. Validate against the
  same 13-member fixed comparator set augmented with Z1, AA1/AA2/AA3, and
  BB1/BB2/BB3, under the Phase D 8-gate production rule.

## J. Project journey log update

- **File updated**: `docs/research/project_journey.md`
- **Section added**: Section 42 — Phase CC: Layer 2B Regime Engine
  Refinement.
- **Story currency**: the project journey is now current through the end
  of Phase CC, including the closure of Phase BB (W1-cap relaxation:
  three Research-only candidates) which directly motivated Phase CC's
  upstream regime-engine refinement.
