# Atlas Offensive — Run 09 Prompt (v1.0, free-data execution)

Copy-paste everything below the line to Fable 5. Executes **R09 (Macro Factor
Conditioning v2, vintage data)** from the Master Run Book — the last major
free-data question. Do not edit mid-run.

---

You are executing **RUN 09 (R09): Macro Factor Conditioning on Vintage Data**
from the Atlas Offensive Master Run Book. This is a free-data run: ALFRED
vintages only, no purchases.

**Read first, in this order:**
1. `CLAUDE.md`
2. Master Run Book Part A (return-first doctrine, standing rules) + the R09
   and R2C cards.
3. `docs/research/atlas_offensive/offensive_holdout_declaration.md`,
   `run02_report.md`, `run2b_report.md` (the DROP/RESEARCH-ONLY verdicts and
   the reusable Base O / direct-weight machinery).
4. The prior macro work you are superseding — read all of it, because R09
   exists to fix its specific defects:
   `docs/research/project_journey.md` sections "FRED-MD Macro Regime
   Classifier" (V1), "V2 Sprint", "V3: Financial Conditions Anchor Repair",
   "Macro-Conditioned ETF Tilt Sandbox (Step 2)", "Step 2B", "Step 2C";
   and `scripts/build_macro_regime_classifier_v3.py`.

**Why this run exists (internalize before designing).** The growth × inflation
quadrant idea produced a real +1.41%/4w development-period spread — the
`slowdown` sub-regime inside neutral_mixed returned +1.47%/4w vs +0.24% in
`stress`. But V1–V3 all ended RESEARCH-ONLY for three specific, fixable
reasons: (a) they used **revised** FRED data (look-ahead — the published
value at decision time differs from today's revised value), (b) optimistic
publication lags, and (c) they forced **monthly** macro information into
**weekly** overlay decisions where it has no weekly content. R09 fixes all
three: true point-in-time ALFRED vintages, a 2-month publication lag, and
conditioning at **monthly** cadence on **capital allocation**, not weekly
tilts. This is the macro family's last honest chance — if it fails under
these conditions, it closes permanently.

**Type:** Research run. No production changes. Namespace
`scripts/atlas_offensive_run09/`, outputs `data/research/atlas_offensive_run09/`,
report `docs/research/atlas_offensive/run09_report.md`. Log every variant in
the trial registry under R09. Costs: per-instrument R00 library, never flat
10bps. Dev window ends 2025-12-31; sealed 2026+ holdout untouchable.

**Pre-register** (`run09_preregistration.md`, before any backtest) exactly the
locked design below — no additions mid-run.

## Locked design

**Phase A — Honest vintage macro factor space.**
1. Pull the FRED-MD-style series via the **ALFRED vintage** endpoint (free),
   so each monthly observation uses only the value that was actually
   published as of the decision date. LOCKED series set: the V3 list plus
   any V3 series that timed out previously, documented explicitly; if a
   series has no vintage history, exclude it and record the exclusion.
2. Apply a **2-month publication lag** to every series (decision at month t
   uses data published on/before t−2).
3. Expanding-window PCA, quarterly refit, minimum 60 months. Sign-anchor
   PC1 (growth) on INDPRO and PC2 (financial conditions / inflation) on NFCI,
   exactly as V3 — do not re-tune the anchoring.
4. Classify each month into the four quadrants (expansion / overheating /
   slowdown / stress) by the signs of PC1/PC2.

**Phase B — Monthly capital conditioning (two bases, both mandatory).**
- **Base O (vacuum):** the R2B Base O (60/40 SPY/QQQ, weekly, state-set
  exposure, no defensive machinery). R09 adds a **monthly** quadrant
  multiplier on gross exposure. LOCKED multiplier grid per quadrant:
  expansion {1.0, 1.1}, overheating {0.9, 1.0}, slowdown {1.0, 1.1},
  stress {0.7, 0.85, 1.0}. Evaluate the full factorial walk-forward.
- **Base P (production stack):** quadrant conditions the sleeve/defense
  capital budget monthly (equity-risk vs BIL/defense), same LOCKED grid
  applied to the offense budget. Direct-weight construction on the GGG panel
  (GGG reproduction gate to ~2e-16 before any arm).
- Benchmarks: for each base, the unconditioned base and a **pooled**
  neutral_mixed handling (no quadrant split).

**Phase C — The two questions that decide the verdict.**
5. **Holdout rank consistency (the V1–V3 failure point):** do the quadrant
   forward-return rankings in the development window hold in a walk-forward
   sense on honest vintages? Report the quadrant return spread by decade and
   whether the 2024–26 "stress-but-rallying" anomaly persists under vintages
   (V3 could not tell if that was a regime shift or a revised-data artifact —
   answer it here).
6. **Allocation value:** does monthly quadrant conditioning improve net CAGR
   and log growth vs the unconditioned and pooled baselines, on each base?

**Controls (LOCKED):**
- Quadrant-label placebo: 200 random monthly quadrant assignments (same
  quadrant frequencies) — actual must beat ≥90%.
- Sign-flip control: invert the quadrant→multiplier map — must hurt.
- 2× cost stress; decade-by-decade decomposition; beta/alpha decomposition
  per the R02 method (a return improvement that is pure beta is labeled beta).

## Locked success criteria (return-first)

- **Promote-to-Book-design** requires ALL of: (a) holdout/walk-forward rank
  consistency achieved on honest vintages; (b) monthly conditioning improves
  net CAGR AND log growth vs both the unconditioned and pooled baselines on
  at least Base O; (c) beats ≥90% of quadrant placebos; (d) sign-flip hurts;
  (e) survives 2× costs.
- **RESEARCH-ONLY** if allocation value is positive but rank consistency
  still fails, or if the effect is real but decomposes to pure beta (record
  as a labeled-beta candidate, like the R2B panic floor).
- **DROP / close the macro family permanently** if quadrants remain unstable
  under honest vintages OR conditioning does not beat pooling — this is the
  macro family's third-and-final honest test; a clean negative here retires
  the branch for good and is a valuable result, not a failure of the run.

## Prohibited

Holdout access; using revised (non-vintage) FRED data anywhere; grid
extensions; re-tuning the V3 PCA anchoring; forcing monthly data into weekly
decisions; production pins/weights/dashboards; `git add -A`.

## Report and verdict

`run09_report.md` per CLAUDE.md: commands; files; the honest-vintage vs
revised-data comparison (show how much the look-ahead mattered); quadrant
spread by decade; the 2024–26 anomaly resolution; both-base allocation-value
tables; placebo and sign-flip batteries; beta/alpha decomposition; trial
count; warnings; git status. Verdict per the branches above. Then recommend
the next free run (expected: R21 crypto probe — the last $0 run in the queue)
and restate that Norgate remains the critical-path blocker (R01 → R03 → R04).

Never promote anything yourself; pin changes and Book adoption require
explicit human authorization.
