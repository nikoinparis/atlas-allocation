# Atlas Offensive — R2B Pre-Registration: Exposure-Level Re-Derivation (α + panic floor)

- **Run ID:** R2B
- **Registration date:** 2026-07-23 — filed before any R2B backtest executed
- **Author / executor:** Claude Code session under human owner nicholasturangan
- **Book component targeted:** REGIME_BRAIN amplitude logic (Arm A/B); Book v1 design inputs
  (Arm B/C). Re-scoped after R02's DROP: no timing rule touches stressed_panic multipliers.
- **Builds on:** R00 (holdout, registry, cost library); R02 verified machinery (direct weight
  construction on the GGG final-weights panel, per-instrument path conventions, latch
  definition); Moonshot §4.5/§7 α evidence (shuffled control passed at α=0.24).
- **Seed:** 20260723. Dev window: path rows with Date ≤ 2025-12-24 (forward week completes by
  2025-12-31). Sealed 2026+ holdout untouched.

## Bases

- **Base P (production stack):** GGG final-weights panel with the R2A scale applied by direct
  weight construction (offense columns × scale, then normalize-to-cash). Implementation
  equivalence gate: at α=0.08 the direct construction must reproduce the production-pin path
  (wrapper modifier) to ≤1e-12 before any arm runs. Note: the run prompt attributes "Base O"
  to R02; R02 contained no Base O — it is defined below and built fresh. Base P's Arm C
  baseline is the α=0.08 (pin-equivalent) construction.
- **Base O (vacuum):** 60/40 SPY/QQQ weekly; exposure by regime state — calm_trend,
  neutral_mixed, recovery_confirmed 1.00; recovery_fragile 0.80; stressed_panic 0.20;
  remainder BIL; no defensive machinery. Unlevered: total risky exposure capped at 1.00
  (BIL ≥ 0). Same index, same per-instrument cost path machinery.

## Arm A — α re-derivation on Base P (LOCKED)

- Scale: `r2a_scale_with_alpha` unchanged (q = clip(r2a, −1, 1); non-SP scale = 1 + α·q;
  leadership > 0.5 caps the boost side at 1.0; stressed_panic = 1.0). No internals re-tuned.
- Grid: α ∈ {0.08, 0.16, 0.24, 0.32, 0.40, 0.48, 0.64, 0.80}. Direct construction (no
  wrapper clip). Full curve reported: net CAGR, log growth, cost drag (annualized), and
  recorded Sharpe/MaxDD/CVaR/vol/turnover; both 1× and 2× measured costs.
- Growth-optimal α = argmax dev log growth (net, 1×). "True cost-binding point" = the α where
  marginal net log growth turns negative while marginal gross log growth is still positive
  (reported with the cost-drag column); if net and gross flatten together, the binder is
  information/saturation, not cost — say which and where.
- Walk-forward selection honesty check: expanding selection at 26-week checkpoints (first
  checkpoint at week 208), objective = expanding net log growth per candidate α; splice cost
  charged from true one-way turnover between outgoing/incoming weight rows at switch dates
  (per-instrument rates). Report chosen α per checkpoint/year and the spliced path's metrics.

## Arm B — α-analog on Base O (LOCKED)

- Multiplier m = clip(1 + α·q, 0.5, 1.5), same α grid, same q; applied to the state-set
  exposure in non-panic states only (stressed_panic stays 0.20). Total exposure capped at
  1.00 (unlevered). No leadership cap (none specified for the vacuum arm).
- Baseline: α = 0 (pure Base O). Success metric: dev net log growth vs α=0.
- Structural note recorded up front: with calm/neutral/recovery_confirmed at E=1.00 and no
  leverage, the boost side is inert in those states; the signal can only add value by cutting
  exposure on low quality or boosting recovery_fragile. This asymmetry is reported, not
  patched.

## Arm C — deep-panic offense floor (LOCKED; labeled INTELLIGENT BETA, no timing claim)

- Domain: stressed_panic ∧ latched weeks (latch = 13w rolling min market drawdown ≤ −10%,
  identical to R02; NO confirmations).
- Base P grid: offense-share floor F ∈ {none, 20%, 30%, 40%} — raise-only surgery on the
  α=0.08 construction (offense scaled up pro-rata to F, non-offense scaled down pro-rata).
- Base O grid: exposure floor ∈ {0.20 (= none), 0.35, 0.50} — raise-only on panic weeks in
  the domain.
- Judged on dev net CAGR and log growth; MaxDD/CVaR recorded; 2008 (2007-10..2009-03) and
  2011 (2011-05..2011-12) windows reported explicitly (R02 identified these as the floor's
  cost centers). The beta/alpha decomposition must attribute the gain to beta — if it shows
  up as alpha, the labeling is wrong and must be investigated before any verdict.

## Controls (LOCKED)

- Arms A/B: 50 shuffled-R2A nulls (permute the r2a series, rebuild the scale with unshuffled
  leadership/states, identical machinery) at the growth-optimal α on each base. Bars:
  actual ≥ 90% of nulls on dev log growth AND the null mean must not replicate the actual
  gain vs α=0.08 (Base P) / α=0 (Base O). If the shuffled mean matches actual, R2A timing
  content is dead at scale — reported loudly, with the Confirm1 implications stated.
- Arm C: no timing nulls (no timing claim); the 2008/2011 windows are the stress control.
- All arms: 2× measured-cost stress; decade decomposition (2005–2009, 2010–2019, 2020–2025);
  beta/alpha decomposition (weekly OLS on SPY next-week returns; ΔCAGR split into
  Δbeta × annualized SPY mean + Δresidual alpha, as in R02).

## Success criteria (LOCKED)

- **Arm A:** growth-optimal α > 0.08 with both null bars passed → amplitude recommendation
  recorded for the Book and the owner's Confirm1 context (no promotion). Binder identified
  (cost vs information) with evidence.
- **Arm B:** growth-optimal α improves Base O log growth vs α=0 → state-quality scaling
  earns a place in Book v1 design (R04 REGIME_BRAIN gross scaling input).
- **Arm C:** floor improves net CAGR AND log growth on BOTH bases, 2008/2011 windows
  survivable (no window erasing more than 2 years of the floor's average annual
  contribution), decomposition confirms beta → adopt as labeled-beta Book design input.
- Any arm failing its control → that arm's thesis closed with documentation.
- Ambiguous outcomes → RESEARCH-ONLY with exactly one pre-registered follow-up.

## Prohibited

Holdout access; grid extensions; re-tuning R2A internals or the leadership cap; timing rules
on stressed_panic (closed by R02); production pins/weights/dashboards; `git add -A`.

## Registry

Every variant, null batch, walk-forward arm, and 2× arm logged under run_id R2B in
`data/research/atlas_offensive_trial_registry.csv`.
