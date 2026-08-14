# Atlas Offensive — Run 2 Prompt (v1.1, free-data execution)

v1.1 (pre-run amendment, before any experiment executed): added the locked
dual-base design. Base O evaluates PBI in a vacuum — a clean offensive base
with NO defensive machinery — per mandate §64 (evaluate the raw strategy
first). Base P measures the same rule inside the existing production stack.
Both are reported; neither is optional.

Copy-paste everything below the line to Fable 5. Executes **R02 (Offensive
Regime Rebuild: PBI Native)** from the Master Run Book, with the R01
dependency explicitly relaxed to existing-data inputs because R01 is
BLOCKED_PREREQUISITE (Norgate not yet installed). Do not edit mid-run.

---

You are executing **RUN 2 (R02): Offensive Regime Rebuild — PBI Native**
from the Atlas Offensive Master Run Book. This is a free-data run: it uses
only data already in the repository.

**Read first, in this order:**
1. `CLAUDE.md`
2. `docs/research/atlas_offensive/atlas_offensive_master_run_book.md` —
   Part A in full, then the R02 and R2B run cards.
3. `docs/research/atlas_offensive/offensive_holdout_declaration.md` and
   `docs/research/atlas_offensive/run01_report.md` (R00 outcomes; R01 block).
4. `docs/research/2026-07-07_moonshot1_discovery_sprint_report.md` and
   `docs/research/2026-07-07_confirm1_alpha_pbi_report.md` — the PBI
   evidence base and the exact locked rule.
5. `scripts/confirm1_alpha_pbi/confirm_candidates.py` (locked PBI
   definitions) and the episode map
   `data/research/moonshot1_discovery/episode_opportunity_map.csv`.

**Type:** Research run. No production pin/code/dashboard changes. Namespace:
`scripts/atlas_offensive_run02/`, outputs
`data/research/atlas_offensive_run02/`, report
`docs/research/atlas_offensive/run02_report.md`. Log every variant in
`data/research/atlas_offensive_trial_registry.csv` under run_id R02. Use the
R00 per-instrument cost library (never 10bps flat). The sealed 2026-01-01+
holdout is untouchable; development window ends 2025-12-31.

**Dependency note (binding):** the run book lists R01 breadth as an R02
input. R01 is blocked on Norgate. Proceed using the EXISTING ETF-level
4-week breadth-change signal already used by the locked Confirm1 PBI rule.
Record in the report that PIT stock breadth is a pre-declared future
enrichment: when R01 unblocks, the PBI confirmation set may be re-tested
with stock-level breadth in a locked follow-up — do not improvise a breadth
substitute now.

**Backstory to internalize (why this run matters most):** the Moonshot
episode map shows early-recovery weeks are the single largest repeating
opportunity: 76 weeks where SPY compounded at +72.6% annualized while the
production system held ~53% cash and earned 11.9%. The four biggest
opportunity gaps in 21 years are all early recoveries (−23pp, −15pp, −12pp,
−10pp per episode vs the achievable bound). 67% of those weeks are labeled
`stressed_panic`, where every overlay multiplier is frozen at 1.0 by
convention. The PBI rule (deep-drawdown latch ≤−10% within 13 weeks; three
lagged confirmations: credit confirmation > 0, 4-week breadth change > 0,
VIX 1m–3m slope > 0; 2-of-3 → ×1.15, 3-of-3 → ×1.30) is real — 91st
percentile vs placement nulls, inverted control hurts (−0.025), passed the
locked Confirm1 battery — but is capped at ~+0.003 Sharpe because panic
weeks hold only ~15% offense. This run removes the cap natively.

**Prime directive:** return first. Primary metrics: net CAGR, expected log
growth, per-episode capture (pp vs baseline), residual alpha. Sharpe, MaxDD,
CVaR, vol, turnover: RECORDED, never gating. Binding gates are integrity
gates only (walk-forward labels, 1-week lags, time-ordered splits, honest
costs, full trial logging, null controls).

**Pre-register before any backtest** (file:
`docs/research/atlas_offensive/run02_preregistration.md`), containing
exactly the locked design below — no additions mid-run.

## Locked design

**Phase A0 — Two evaluation bases (LOCKED; both mandatory).**

- **Base O ("vacuum" offensive base — the primary result of this run).**
  A clean base with ZERO defensive machinery: no target-vol overlay, no BIL
  floor outside panic, no HRP, no fragility guard, no turnover gate. Base O
  holds a simple risk portfolio (60% SPY / 40% QQQ, weekly rebalanced) with
  exposure set purely by the regime state:
  `calm_trend / neutral_mixed / recovery_confirmed = 1.00`,
  `recovery_fragile = 0.80`, `stressed_panic (not improving) = 0.20`
  (remainder in BIL as cash, not as a defensive overlay),
  `stressed_panic_improving = grid {0.40, 0.70, 1.00}`.
  This isolates the question: what is the regime engine + PBI worth on its
  own, uncontaminated by any defensive layer? Benchmarks for Base O: SPY
  buy-and-hold and the same base with the improving-panic exposure left at
  0.20 (no-PBI control).
- **Base P (production-stack base — the compatibility result).**
  The existing production allocation logic with the panic-freeze removed as
  originally specified below. Benchmarks: unmodified production pin and the
  Confirm1 candidates. This measures what the uncap adds to the current
  system, for the owner's separate Confirm1 decision context.

All Phase C null controls run on the best variant of EACH base. The report
presents Base O first — it is the vacuum answer; Base P is secondary.

**Phase A — Native PBI sub-state.**
1. Implement `stressed_panic_improving` as a native Layer-2B sub-state in
   research code (not a wrapper multiplier): a stressed_panic week enters it
   when the locked Confirm1 PBI conditions fire (latch and confirmations
   exactly as in `confirm_candidates.py`; do not re-tune them).
2. Offense-base grid for the sub-state (LOCKED): {25%, 40%, 55%, 70%}
   (baseline ~15%). Non-panic states untouched. Deteriorating panic
   (sub-state not fired) untouched.
3. Per-episode stop (LOCKED grid): if portfolio drawdown deepens by
   {3%, 5%, 7%} after sub-state entry, revert that episode to standard
   panic defense until the latch resets.
4. Evaluate all 12 combinations walk-forward through 2025-12-31, net of
   costs from the R00 library. Report per-episode attribution for all ~9
   historical episodes (2008, 2009, 2011, 2016, 2018, 2019, 2020, 2022,
   2025) — every episode individually, plus the 2008 improving-then-
   collapsing stress replay as its own section.

**Phase B — Label-stability benchmark.**
5. Fit a statistical jump model (transition-penalized clustering, λ grid
   {1,2,4} — LOCKED) and a 5-state Gaussian HMM on the existing Layer-2B
   feature set, walk-forward. Compare against the production 5-state engine
   on: transitions/year, state persistence, and portfolio value when each
   label set drives the same allocation rules. This is a benchmark, not a
   replacement decision — REGIME_BRAIN replacement would require its own
   locked follow-up.

**Phase C — Null and control battery (for the best Phase A variant).**
6. 200 random-placement nulls (same number of sub-state weeks placed
   randomly within stressed_panic).
7. Inverted-confirmation control (fire when confirmations are negative —
   must hurt).
8. Episode-blocked bootstrap for the capture estimate (block = episode).
9. 2× cost stress.

## Locked success criteria (return-first)

- **Base O (vacuum):** the best PBI variant improves Base O's full-period
  net CAGR and log growth vs the no-PBI control, and episode capture
  improves ≥ +5pp on average — with no defensive layer to hide behind or
  blame. This is the run's headline verdict.
- **Base P (production stack):** best variant improves average early-recovery episode capture by ≥ +5pp
  (annualized within-episode return vs the unmodified base) across
  episodes, with the 2008 replay contained by its stop (no single episode
  erasing more than 2 years of average contribution).
- Full-period net CAGR and log growth improve vs the unmodified base.
- Beats ≥90% of placement nulls; inverted control hurts; survives 2× costs.
- Report (not gate): Sharpe/MaxDD/CVaR deltas, stressed_panic-only metrics,
  beta-vs-alpha decomposition of the improvement.

## Prohibited

Consulting the sealed holdout; re-tuning the PBI latch/confirmations;
adding grid points; touching production pins/weights/dashboard bundles;
`git add -A`; substituting scraped stock data for the blocked R01 input.

## Report and verdict

`docs/research/atlas_offensive/run02_report.md` per CLAUDE.md: commands;
files; per-episode capture table (all episodes, all 12 variants summarized,
best variant detailed); 2008 replay section; Phase B benchmark table; null
battery; trial count; warnings; git status. Verdicts per the run book:
- All criteria pass → **CONFIRMED-FOR-HUMAN-REVIEW**: REGIME_BRAIN v2
  candidate; recommend R2B (amplitude re-derivation on the new base) as the
  immediate next free run, and note the R15 linkage (same trigger buys
  convexity once options data exists).
- Capture real but stops cannot contain 2008-type reversals → hold PBI at
  the Confirm1 modest amplitudes; classify the uncapped version
  RESEARCH-ONLY with the measured ceiling; R2B still proceeds.
- Nulls not beaten on the new base → **Drop** the uncap thesis permanently;
  the Confirm1 candidates remain the owner's pending decision; document.

Never promote anything yourself; pin changes and Book adoption require
explicit human authorization.
