# Atlas Offensive — Run 2B Prompt (v1.0, free-data execution, re-scoped after R02 DROP)

Copy-paste everything below the line to Fable 5. Executes **R2B (Amplitude
Liberation)** re-scoped to the existing base per the R02 verdict, plus the
R02 post-hoc panic-floor observation now properly pre-registered. Do not
edit mid-run.

---

You are executing **RUN 2B: Exposure-Level Re-Derivation (α amplitude +
panic offense floor)** from the Atlas Offensive Master Run Book, re-scoped
after R02's DROP verdict.

**Read first:** `CLAUDE.md`; Master Run Book Part A + R2B card;
`docs/research/atlas_offensive/run02_report.md` (the DROP verdict, the
inverted-control finding, the post-hoc floor observation, and the Base O
machinery you will reuse); `docs/research/2026-07-07_moonshot1_discovery_sprint_report.md`
§4.5/§7 (the α evidence and its passing shuffled control);
`data/research/atlas_offensive_cost_library.csv` (measured costs);
`docs/research/atlas_offensive/offensive_holdout_declaration.md`.

**Context you must internalize:**
- R02 killed the PBI *timing* thesis (lift = generic panic beta). It did
  NOT touch the R2A amplitude evidence, which has a clean passing control
  on record: at α=0.24, shuffled-R2A nulls had a mean WORSE than the pin
  and actual beat 50/50 — real timing content, unlike PBI.
- The old α curve was stopped at ~0.48 by a turnover-cost gate built on a
  10bps flat assumption. The R00 cost library measured ~0.5–2bp one-way on
  these instruments — the binding constraint was overstated ~5–20×. Where
  the α curve truly stops is an open, answerable question.
- R02's post-hoc observation: the base generically under-holds offense in
  deep-panic weeks (+0.10% CAGR available to RANDOM boosts). Arm C tests
  this as what it is — labeled intelligent beta, no timing claim.

**Type:** Research run. No production changes. Namespace
`scripts/atlas_offensive_run2b/`, outputs
`data/research/atlas_offensive_run2b/`, report
`docs/research/atlas_offensive/run2b_report.md`. Every variant logged in
the trial registry under R2B. Costs: per-instrument library, never flat
10bps. Dev window ends 2025-12-31; sealed 2026+ holdout untouchable. Reuse
R02's verified machinery (direct weight construction on the GGG panel;
Base O implementation; GGG reproduction check to ~2e-16 before any arm).

**Pre-register** (`run2b_preregistration.md`, before any backtest) exactly
the locked design below.

## Locked design — three arms, two bases

**Bases (from R02, unchanged):**
- **Base P:** production-stack allocation via direct weight construction.
- **Base O (vacuum):** 60/40 SPY/QQQ, weekly, exposure set purely by regime
  state (calm/neutral/recovery_confirmed 1.00, recovery_fragile 0.80,
  stressed_panic 0.20, remainder in BIL), no defensive machinery.

**Arm A — α re-derivation on Base P.** R2A state-quality scaling
(leadership cap intact, stressed_panic multiplier untouched at 1.0) at
LOCKED grid α ∈ {0.08, 0.16, 0.24, 0.32, 0.40, 0.48, 0.64, 0.80}.
Report the FULL curve: net CAGR, expected log growth, turnover cost drag,
(recorded: Sharpe/MaxDD/CVaR). Identify the growth-optimal α and the true
cost-binding point under measured costs. Walk-forward α selection
(expanding, 26-week checkpoints, log-growth objective) as the
selection-honesty check — report what it would have chosen each year.

**Arm B — α-analog on Base O.** Exposure multiplier = 1 + α·(R2A score),
clipped to [0.5, 1.5], same LOCKED α grid, applied to Base O's state-set
exposure in non-panic states only. This is the vacuum answer: what is the
state-quality signal worth with no defensive machinery around it?

**Arm C — deep-panic offense floor (pre-registered intelligent beta).**
On both bases: raise the offense/exposure floor in ALL deep-drawdown panic
weeks (drawdown ≤ −10% within trailing 13w — same latch definition as R02,
but NO confirmations, no timing claim) to LOCKED grid {none, 20%, 30%, 40%}
(Base P offense) / {0.20 (none), 0.35, 0.50} (Base O exposure). Judged on
net CAGR and log growth with drawdown honestly recorded; labeled BETA in
all reporting — the beta/alpha decomposition must show it as beta or the
labeling is wrong.

**Controls (LOCKED):**
- Arms A/B: 50 shuffled-R2A-signal nulls at the growth-optimal α on each
  base (the Moonshot control design, fresh seed). Actual must beat ≥90% of
  nulls AND the null mean must not replicate the gain (if shuffled signal
  matches actual, R2A timing content is dead at scale — report this loudly;
  it also undermines the pending Confirm1 candidates and the owner must
  know).
- Arm C: no timing nulls needed (no timing claim) — but run the 2011
  whipsaw window and 2008 explicitly, since R02 showed those are the
  floor's cost centers.
- All arms: 2× measured-cost stress; decade-by-decade decomposition;
  beta/alpha decomposition per §63.

## Locked success criteria (return-first)

- **Arm A:** growth-optimal α > 0.08 with nulls passed → amplitude
  recommendation recorded for the Book and for the owner's Confirm1
  context. If the curve's true binder is information (not cost), say where
  and why.
- **Arm B:** state-quality scaling improves Base O log growth vs α=0 →
  the signal earns a place in Book v1 design (R04's REGIME_BRAIN gross
  scaling).
- **Arm C:** floor improves net CAGR on both bases with the 2011/2008
  windows survivable → adopt as a labeled-beta Book design input.
- Any arm failing its control → that arm's thesis is closed with
  documentation.

## Prohibited

Holdout access; grid extensions; re-tuning R2A internals or the leadership
cap; touching stressed_panic multipliers with timing rules (that door
closed with R02); production pins/weights/dashboards; `git add -A`.

## Report and verdict

`run2b_report.md` per CLAUDE.md: full α curves both bases; walk-forward
selection table; floor tables with stress windows; null batteries; trial
count; beta/alpha decomposition; warnings; git status. Verdicts per arm:
Adopt-into-Book-design / Confirm-in-follow-up / Research-only / Drop.
Recommend the next free run (expected: R2C/R09 macro vintages, then R21
crypto probe) and restate what unblocks with Norgate (R01 → R03 path).
Never promote anything yourself; pin changes and Book adoption require
explicit human authorization.
