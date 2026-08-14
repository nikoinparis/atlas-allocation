# Atlas Offensive — R02 Pre-Registration: Offensive Regime Rebuild (PBI Native)

- **Run ID:** R02
- **Registration date:** 2026-07-21 — filed before any R02 backtest executed
- **Author / executor:** Claude Code session under human owner nicholasturangan
- **Book component targeted:** REGIME_BRAIN (UPGRADE — adds `stressed_panic_improving` sub-state)
- **Builds on:** R00 governance (holdout seal, trial registry, cost library); Moonshot episode
  map; Confirm1 locked PBI rule. R01 breadth input is BLOCKED — this run uses the existing
  ETF-level 4-week breadth-change confirmation already inside the locked Confirm1 rule.
  **Pre-declared future enrichment:** when R01 unblocks, the PBI confirmation set may be
  re-tested with PIT stock-level breadth in a locked follow-up. No breadth substitute is
  improvised here.

## 1. Hypothesis

Allowing confirmed-improving panic weeks a native offense base (25–70%) instead of the
wrapper-capped ~15%×1.15/1.30 recovers a material share of the early-recovery opportunity:
average per-episode capture ≥ +5pp annualized vs the unmodified base, with full-period net
CAGR and log growth improving, survivable 2008 replay, and null controls passed.

## 2. Data, base, and window

- **Base stack ("unmodified base"):** the exact GGG reconstruction
  (`improved_phaseggg_confirmed_only_robust_offense`) via `AllocatorCheckpointWrapper`,
  no modifiers, recomputed net of per-instrument costs (below). The production pin is reported
  as a reference benchmark only.
- **Development window:** evaluation uses path rows whose forward week completes by
  2025-12-31 (last decision row 2025-12-19). The sealed 2026+ holdout is untouched; no 2026
  fire weeks exist. All metrics, selections, and tables use the dev window only.
- **States/features:** production `market_state_history.csv` labels; the locked Confirm1 PBI
  rule imported from `scripts/confirm1_alpha_pbi/confirm_candidates.py` /
  `moonshot_features.py` — latch (13w rolling min market drawdown ≤ −10%), confirmations
  (credit confirmation > 0, 4-week breadth change > 0, VIX 1m–3m slope > 0, all one-week
  shifted), gate ≥ 2-of-3. **No latch/confirmation parameter is re-tuned.**

## 3. Locked design — Phase A (native sub-state)

1. **Sub-state entry:** a `stressed_panic` week with the locked rule firing enters
   `stressed_panic_improving`. Fire weeks are exactly the Confirm1 fire set (49 weeks;
   44 at 2-of-3, 5 at 3-of-3).
2. **Native offense base, grid LOCKED B ∈ {25%, 40%, 55%, 70%}:** in a fire week the offense
   basket (production OFFENSE set) is scaled to target share T:
   - 3-of-3 confirmations: T = B
   - 2-of-3 confirmations: T = B × (1.15/1.30) ≈ 0.885·B (preserves the locked conviction
     grading ratio; no new parameter)
   - T = max(T, baseline offense share) — the sub-state never reduces offense vs base.
   - Weights: offense columns scaled proportionally to sum T; all non-offense columns
     (BIL + defense) scaled by (1−T)/(1−current offense share). No other week is touched.
3. **Per-episode stop, grid LOCKED S ∈ {3%, 5%, 7%}:** episodes are fire-week clusters
   (consecutive fires ≤ 13 calendar weeks apart — the latch length; yields exactly 9
   episodes: 2008a, 2008b, 2009, 2011, 2016, 2018–19, 2020, 2022, 2025). Entry = first fire
   of the episode. If at any week-close after entry the variant's wealth is ≥ S% below its
   entry-week-close wealth, the sub-state is disabled from the next decision week for the
   remainder of that episode (baseline weights in its remaining fire weeks). The next episode
   re-arms fresh. Stops are causal (decision at t+1 uses returns through t) and applied by
   forward-sequential recomputation.
4. **12 variants** = 4 offense bases × 3 stops. All evaluated walk-forward on the dev window,
   net of per-instrument costs.
5. **Costs:** per-instrument one-way costs from `data/research/atlas_offensive_cost_library.csv`
   (`one_way_cost_bps`); cost_t = Σᵢ 0.5·|Δwᵢ,t|·cᵢ/10⁴ (canonical one-way convention,
   per-instrument rates). The 10bps flat model is not used. 2× stress doubles every cᵢ.

## 4. Locked design — Phase B (label-stability benchmark; not a replacement decision)

- Features: the 19-feature causal moonshot panel (Layer-2B state features + R2A + leadership
  + VIX term structure, all one-week shifted), expanding-window standardized (min 104w).
- **Jump model:** K=5, λ ∈ {1, 2, 4} (LOCKED), fit by alternating DP assignment (switch
  penalty λ) and centroid updates on expanding data, refit every 52 weeks (first fit at
  ≥ 260 weeks), causal online assignment between refits.
- **HMM:** 5-state Gaussian (diagonal), EM, same refit schedule, filtered-posterior argmax
  (causal).
- **Comparison:** transitions/year, median spell length, and portfolio value under one common
  action rule applied identically to production labels, jump labels, and HMM labels:
  per-state offense_budget multiplier = 1.10 if the expanding past mean of next-week
  offense-minus-BIL excess return conditional on the state is > 0, else 0.90 (min 26 past
  observations, else 1.0), applied at the wrapper offense_budget checkpoint, net of
  per-instrument costs.

## 5. Locked design — Phase C (null battery, best Phase A variant)

- **Placement nulls (n=200, seed 20260721):** same number of fire weeks (49) with the same
  2-of-3/3-of-3 grade counts placed uniformly at random among dev-window `stressed_panic`
  weeks; expressed with the best variant's offense base, **no stop**; compared against the
  best variant's no-stop expression on ΔCAGR vs base. Bar: actual ≥ 90th percentile.
- **Inverted-confirmation control:** fire when ≥2 of the 3 confirmations are ≤ 0 within the
  SP ∧ latch domain (2-neg → T = B×(1.15/1.30), 3-neg → T = B), no stop. Must hurt
  (ΔCAGR < 0 expected; must at minimum be below the actual variant).
- **Episode-blocked bootstrap:** 10,000 resamples (with replacement) of the 9 per-episode
  capture deltas → 95% CI of mean capture.
- **2× cost stress:** all 12 variants at doubled per-instrument costs; best variant must keep
  ΔCAGR > 0 and Δlog-growth > 0 vs base at 2×.

## 6. Primary metrics (return-first, ranked on these)

Net CAGR; expected log growth (52 × mean ln(1+r_net)); average per-episode capture
(annualized within-episode return delta vs base; episode window = first fire → last fire
+ 4 weeks, truncated at dev end); residual alpha (annualized intercept of weekly OLS of
variant net return on SPY weekly return, dev window).

## 7. Recorded, non-gating metrics

Sharpe, MaxDD, CVaR5, vol, avg one-way turnover, per-state expectancy (52 × mean weekly net
return by production state), beta-vs-alpha decomposition of the improvement (Δbeta·SPY-mean
vs Δalpha).

## 8. Success / failure criteria (LOCKED)

- **Pass:** best variant (highest dev net CAGR subject to containment; ties → higher log
  growth) achieves: mean episode capture ≥ +5pp; full-period net CAGR AND log growth above
  base; worst single episode contribution ≥ −2 × (best variant's annual CAGR improvement ×
  1yr) — i.e., no episode erases more than 2 years of average contribution — with the 2008
  replay explicitly examined; ≥90% of placement nulls beaten; inverted control hurts;
  2× costs survived. → **CONFIRMED-FOR-HUMAN-REVIEW** (REGIME_BRAIN v2 candidate);
  recommend R2B next; note R15 linkage.
- **Capture real but stops fail 2008 containment:** hold PBI at Confirm1 modest amplitudes;
  uncapped version **RESEARCH-ONLY** with the measured ceiling; R2B proceeds.
- **Nulls not beaten:** **Drop** the uncap thesis permanently; Confirm1 candidates remain the
  owner's pending decision.
- **Ambiguous:** RESEARCH-ONLY + exactly one pre-registered follow-up.

## 9. Prohibited

Consulting the sealed holdout; re-tuning latch/confirmations; adding grid points; touching
production pins/weights/`public/dashboard-data.json`; `git add -A`; substituting scraped
stock data for R01. Nothing is promoted without explicit human authorization.

## 10. Registry

Every variant (12 Phase A, Phase B arms, null batches, inverted control, 2× stress) is logged
in `data/research/atlas_offensive_trial_registry.csv` under run_id R02. Seed: 20260721.
