# Phase 2B Dual-Track Summary

## Outcome

Phase 2B produced two conditional-promote candidates that both cleared the +0.05 production-score margin over the Phase 1 incumbent without worsening drawdown or CVaR. Rather than treating them as two simultaneous production defaults, the project is pinned in a dual-track configuration:

- **Official production track (A):** `improved_phase2b_regime_confidence_boost`
- **Shadow research runner-up (F):** `improved_phase2b_combo_abc`

A is the single headline production candidate across the dashboard, reports, and narratives. F is kept alive as a tracked alternate baseline, surfaced only as a comparison, never as a second headline.

## Headline metrics (post-regeneration)

| Metric | Baseline HRP | **A — Production** | F — Shadow |
|---|---|---|---|
| Ann. return | 5.06% | **6.89%** | 6.86% |
| Sharpe | 0.794 | **0.884** | 0.884 |
| Calmar | 0.414 | 0.493 | **0.502** |
| Max drawdown | -12.2% | -14.0% | -13.7% |
| CVaR (5%) | -2.23% | -2.62% | -2.61% |
| Production score | 0.291 | **0.786** | 0.749 |

A wins on the composite production score (+0.04 vs F). F wins on Calmar (+0.009) and on stressed-state Sharpe (per the Phase 2B report). Both pass the DD and CVaR deterioration gates relative to the Phase 1 incumbent.

## Why A is the official production strategy

1. **Best production score.** A scores 0.786 vs F's 0.749 on the rank-weighted composite (Sharpe 0.22, Calmar 0.16, DD 0.14, CVaR 0.10, upside 0.12, recovery 0.10, cash 0.08, turnover 0.08). The composite was the pre-registered selection rule, and A wins it cleanly.
2. **Simplest single-signal pass.** A is a single orthogonal modifier on `regime_multiplier` — a regime-confidence boost applied on top of the Phase 2A overlay penalty mode. It adds no additional state machine, no additional feature columns, and no extra retraining schedule.
3. **Cleanest explainability.** A's behaviour is fully inspectable from the confidence score itself: fires on ~28% of weeks, concentrated in `neutral_mixed` and `recovery_fragile`, mean offset +0.004. There is no stacking of meta-layer outputs.
4. **Best return/Sharpe balance.** A has the highest annualised return and matching Sharpe versus F, with only a marginally worse Calmar. For a pinned production default, stable Sharpe and composite score matter more than a few bps of Calmar.
5. **Lower operational risk.** A has fewer moving parts to break, less potential for silent regression under drift, and a simpler rollback story.

## Why F is kept as a tracked research runner-up

1. **Best Calmar on the out-of-sample record (+0.009 over A).**
2. **Best stressed-state Sharpe**, per the Phase 2B walk-forward slice. In the `stressed_panic` and early `recovery_fragile` regimes, F's combined signals reduce effective exposure faster than A alone.
3. **Diversification value as a shadow benchmark.** F combines three Phase 2B signals (A + B + C) and therefore probes a different part of the design space than A. Keeping it live protects against the scenario where A degrades under an unfamiliar regime mix while F's additional defensive gating still holds.
4. **Not worth promoting now.** F's extra complexity (three stacked signals, heavier parameter surface) does not justify demoting A given that A wins the composite score and is simpler.

F is therefore surfaced in the dashboard as an alternate comparison only — via `overview.researchVersion`, `overview.researchAllocationSummary`, and `overview.trackPolicy` — and never as a second headline production candidate.

## Rule for future Phase 3 work

Any future candidate must be evaluated against **both tracks separately** before any promotion decision:

1. **Report incremental contribution vs A (production).** A candidate can replace A only if it:
   - Beats A on production score by at least +0.05, AND
   - Does not worsen max drawdown by more than 0.005, AND
   - Does not worsen CVaR(5%) by more than 0.002, AND
   - Does not meaningfully worsen turnover or cash drag.
   If all four hold, the candidate is promoted to production and A is retired.
2. **Report incremental contribution vs F (shadow).** A candidate can replace F only if it:
   - Strictly dominates F on both Calmar and stressed-state Sharpe, AND
   - Does not worsen DD or CVaR relative to F.
   If it dominates F but does not beat A on the composite score, it becomes the new shadow and F is retired.
3. **If a candidate beats A on the composite but loses to F on Calmar and stressed Sharpe,** it is promoted to production and F remains as the shadow — i.e. the two tracks move independently.
4. **If a candidate fails both tests,** it is Research-only or Dropped — never added as a third track. The dual-track structure is fixed at two slots.

This prevents ambiguous "two winners" framing and forces every future sprint to pick which track each change is aimed at before testing.

## Where the dual-track pins live in code

- `CLAUDE.md` — declares both tracks and the dual-track rule at the project root.
- `scripts/build-dashboard-data.mjs` — explicit `PRODUCTION_VERSION_NAME` and `RESEARCH_VERSION_NAME` pins, plus `researchVersion`, `researchAllocationSummary`, and `trackPolicy` in `payload.overview`.
- `src/types/dashboard.ts` — typed overview fields for the research track and policy.
- `src/components/executive-summary.tsx` — SSR first-paint narrative names A as the production default and F as the research runner-up; future Phase 3 reporting rules summarised inline.
- `public/dashboard-data.json` — regenerated to carry the pins.
