# Atlas Offensive — Handoff Document (for any AI/agent continuing this work)

**Written:** 2026-07-23, by Claude Code (Claude Fable 5), for continuation by another
assistant (e.g. ChatGPT / Codex) or a future Claude session with no prior context.
**Repository (absolute path):** `/Users/nicholasturangan/Documents/Portfolio Optimizer`
**Git:** branch `main`, nothing committed by this program yet (see §7). Owner/user git
identity: `nikoinparis`. User email: nicholasturangan@gmail.com.

Read this whole file before touching anything. It is written to be self-contained: even
without access to the earlier conversation, everything needed to act correctly is here.

---

## 1. What this project is

A weekly ETF tactical allocation system ("Atlas Allocation") built over ~60 research
phases, now running a structured follow-on research program called **Atlas Offensive**
(started 2026-07-21) whose goal is to convert the system from a good *defensive* product
into a genuine *return-seeking* one, without ever compromising research integrity.

- **Architecture:** Layer 1 alpha signals → Layer 2A sleeves → Layer 2B causal 5-state
  regime engine (`stressed_panic`, `recovery_fragile`, `recovery_confirmed`,
  `neutral_mixed`, `calm_trend`) → Layer 3 HRP portfolio construction with regime
  multipliers, target-vol scaling, a BIL defensive overlay, and a crowding guardrail.
- **Current production result:** 7.13% CAGR, 0.948 Sharpe, −11.6% MaxDD, SPY beta 0.24,
  ~27.6% average cash. SPY itself compounded ~10.5% over the same period — the defensive
  posture is the specific problem Atlas Offensive exists to address.
- **Production pin (NEVER touched by any Atlas Offensive run):**
  `improved_frontier_phase5_fragility_guard`. See `CLAUDE.md` "Strategy Pins" section for
  the full pin registry (prior pin, shadow, candidate history). Pin changes require
  explicit human authorization — no AI may change it.

## 2. Non-negotiable rules (read `CLAUDE.md` in full — this is a summary, not a substitute)

- **Repo files are the source of truth.** Never invent phases, artifacts, metrics, signal
  names, or strategy state not present in the codebase.
- **Session start checklist, every time:** `pwd`, `git status`, `git branch`, `git worktree
  list`. Stop and report if a prerequisite file/artifact is missing — never improvise a
  substitute (this is exactly what happened with R01/Norgate; see §5).
- **Never change production pins, weights, or code.** Never regenerate/commit
  `public/dashboard-data.json`. Never `git add -A` or `git add .` — stage files by name.
- **Never promote anything.** Every run report ends with a verdict
  (Adopt-into-Book-design / Confirm-in-follow-up / Research-only / Drop), but actual
  promotion (pin changes, Book adoption) requires explicit human authorization, always.
- **Return-first doctrine** (Master Run Book Part A — read it in full, it's short and
  essential): primary metrics are net CAGR, expected log growth, per-state/per-episode
  expectancy, residual alpha. Sharpe/MaxDD/CVaR/vol/turnover are **recorded every time,
  never gating**, until the final risk-engineering stage (R45, far in the future).
- **Integrity gates (always binding, never relaxed):** point-in-time data, survivorship-
  free universes, ≥1-week signal lags, time-ordered splits only (no random train/test
  splits), per-instrument realistic costs (the flat 10bps assumption is retired — see
  §6), every tested variant logged in the trial registry, null controls for any headline
  claim, and the sealed 2026-01-01+ holdout left untouched until final promotion
  decisions.
- **Pre-register before running:** hypothesis, locked parameter grids, success/failure
  thresholds, written to a file *before the first backtest*. No grid points may be added
  mid-run. Post-hoc discoveries are allowed but must be labeled POST-HOC and re-confirmed
  in a fresh locked follow-up before being believed.
- **Each run works in its own namespace:** `scripts/atlas_offensive_runNN/`, outputs in
  `data/research/atlas_offensive_runNN/`, report in
  `docs/research/atlas_offensive/runNN_report.md`.
- **Every run report answers:** commands executed; files changed; outputs/metrics;
  whether the change helped standalone; whether it helped in combination; final verdict;
  warnings/anomalies; git status after work. (This is the CLAUDE.md "Task Reporting"
  section, restated for Atlas Offensive's run-report format.)

## 3. Key documents to read, in order, before doing anything

1. `CLAUDE.md` (repo root) — full project instructions, pin registry, dashboard rules,
   git rules.
2. `docs/research/atlas_offensive/atlas_offensive_master_run_book.md` — the full program:
   Part A (backstory, doctrine, standing rules — read completely), Part B (stage map),
   Part C (all run cards R00–R63), Part D (quick reference). This is the master plan;
   every run executed so far has been one card from this book, sometimes re-scoped by a
   prior run's verdict.
3. `docs/research/atlas_offensive/offensive_holdout_declaration.md` — the sealed
   2026-01-01+ holdout (binding on every run).
4. `data/research/atlas_offensive_trial_registry.csv` — every variant ever evaluated
   under this program, one row each: `run_id, date, variant, params, primary_metric,
   value, verdict, notes`. Read the tail to see what's been tried.
5. The run reports listed in §5 below, in order — each documents what was learned and
   what it changed for the next run.

## 4. Reusable machinery (do not reimplement — extend or import)

- `scripts/allocator_checkpoint_wrapper.py` — `AllocatorCheckpointWrapper`: the no-write
  research wrapper around the exact GGG portfolio reconstruction
  (`improved_phaseggg_confirmed_only_robust_offense`, the base stack all Atlas Offensive
  runs build on — NOT the production pin, which is only a reporting benchmark). Clips
  modifiers to [0.5, 1.5] — too narrow for large exposure changes, which is why R02/R2B
  moved to **direct weight construction** instead (see next item).
- `scripts/atlas_offensive_run02/r02_lib.py` — the machinery actually reused by R02 and
  R2B. Key exports:
  - `R02Machinery` class: loads the GGG base once, exposes `.base_weights`, `.nwr`
    (next-week returns), `.states`, `.offense_cols`, `.offense_share`, PBI fire/latch
    structure, episode segmentation.
  - `per_instrument_path(weights, next_week_returns, cost_bps_vec)` — canonical portfolio
    path (gross/net/turnover/cost/wealth/drawdown) using **per-instrument** one-way costs
    instead of a flat rate.
  - `load_cost_vector(multiplier)` — loads
    `data/research/atlas_offensive_cost_library.csv` (one_way_cost_bps per ticker; use
    multiplier=2.0 for the mandatory 2× cost stress).
  - `core_metrics(path, spy_next_returns)` — net CAGR, log growth, vol, Sharpe, MaxDD,
    CVaR5, avg turnover, SPY beta, residual annualized alpha (weekly OLS vs SPY next-week
    return) — this is the standard metrics dict every run should produce.
  - `dev_window(path)` — truncates to the pre-registered dev window (Date ≤
    2025-12-24, i.e. forward week completing by 2025-12-31). **Always call this before
    computing any metric** — it's how the sealed holdout stays untouched.
- `scripts/atlas_offensive_run02/confirm_candidates.py` (imported, not owned by R02) /
  `scripts/confirm1_alpha_pbi/confirm_candidates.py` and
  `scripts/moonshot1_discovery/moonshot_models.py` — locked signal definitions
  (`r2a_scale_with_alpha`, `pbi_latched_multiplier`) reused verbatim across runs so
  results stay comparable and no re-implementation drift creeps in.
- `data/01_data_hub/universe.json` — the 35-ETF traded universe (list `"all"`), asset
  class map, descriptions. This is the whole tradable universe until Norgate unblocks
  stock-level data (§5, R01).
- Cost model: `data/research/atlas_offensive_cost_library.csv`, built by
  `scripts/atlas_offensive_run01/build_cost_library.py`. Measured via a quiet-minute
  range proxy (P10 of 1-minute high-low/mid) cross-checked against closing quotes —
  **do not use the old flat 10bps model or naive daily-bar spread estimators** (both were
  tried and rejected/superseded; see R00 in `run01_report.md` for why).

## 5. Program status — every run so far, in order

### R00 — Governance Reset — **COMPLETE**
Sealed the 2026-01-01+ holdout (old 2024-04-19 holdout demoted to descriptive-only);
created the trial registry; wrote the pre-registration template; built the per-instrument
cost library v1 (retiring the flat 10bps assumption). Report:
`docs/research/atlas_offensive/run01_report.md` (R00 and R01 share one report since R01
blocked immediately).

### R01 — PIT Stock Breadth Confirmation — **BLOCKED_PREREQUISITE**
**This is the critical-path blocker for the entire back half of the program.** Norgate
Data (Platinum/Diamond tier, ~$110/mo) is not installed: `norgatedata` Python package is
absent, and `data/stock_breadth/raw/` contains only `*_TEMPLATE.csv` placeholders (the
scaffold at `scripts/build_pit_stock_breadth_panel.py` rejects templates by design — this
is correct behavior, not a bug). **Per the run card, no substitute/scraped universe was
used.** The full pre-registration is locked and waiting at
`docs/research/atlas_offensive/run01_preregistration.md` — when Norgate is installed,
run `python3 scripts/atlas_offensive_run01/check_r01_prerequisites.py` to confirm, then
execute R01 exactly as pre-registered (hypothesis: unbiased PIT stock breadth retains
≥+0.26%/4w of the biased +0.517%/4w calm_trend lift found in Phase 5A-Free). Unblocking
this run opens R03 (single-stock universe — the program's single most important
infrastructure investment) → R04 (Book v1) → the entire Stage 2+ program. **Norgate Data
Updater is Windows-only** — must be run on a Windows machine/VM, exported, and copied into
`data/stock_breadth/raw/`.

### R02 — Offensive Regime Rebuild: PBI Native — **DROP (permanent)**
Tested whether a native `stressed_panic_improving` sub-state (25–70% offense floor in
confirmed-improving deep-panic weeks, replacing the wrapper-capped ~15%×1.15/1.30) could
recover early-recovery-episode return. Best variant (+0.26% CAGR) failed its own
pre-registered null battery: random tercile placements scored at the 66.5th percentile
(bar ≥90%), and the **inverted-confirmation control helped** (+0.20%) instead of hurting
— proof the lift was generic panic-week beta, not real confirmation timing. **Verdict:
the native uncapped-PBI thesis is closed permanently.** The separate Confirm1
wrapper-amplitude candidates (α=0.16–0.24 + PBI at ×1.15/1.30, Sharpe-based case) are
UNAFFECTED and remain the owner's pending promotion decision — nothing here invalidates
them. Full report: `docs/research/atlas_offensive/run02_report.md`. One important
byproduct: R02 discovered that stop-losses inside a panic re-risking rule systematically
sell exactly at bear-market bottoms — a general design lesson for any future panic-timing
work.

### R2B — Exposure-Level Re-Derivation (α amplitude + panic floor) — **DROP / DROP /
RESEARCH-ONLY**
Re-scoped after R02's DROP to remove all panic *timing* claims. Three arms:
- **Arm A (α curve on production stack):** full grid α ∈ {0.08...0.80}. Growth-optimal α
  is **0.08 — the current production value**. The old "turnover-cost gate binds at
  α≈0.48" story from Moonshot is **refuted**: measured per-instrument costs are ~2bp
  annualized drag across the whole grid (the old flat-10bps model overstated this ~10×).
  The real binder is information: R2A's cut side buys Sharpe by giving up CAGR at every
  step past 0.16. Walk-forward log-growth selection chose α=0.08 at 28/35 checkpoints.
  **DROP the amplitude-increase thesis.**
- **Arm B (α-analog on a 60/40 SPY/QQQ vacuum base):** every α>0 hurts monotonically — the
  signal's only expressible side in an unlevered vacuum is de-risking, which only costs
  return. **DROP for unlevered Book v1**; revisit only after R43 adds leverage headroom.
- **Arm C (deep-panic offense floor, NO confirmations, labeled explicitly as beta not
  alpha):** real CAGR gain on both bases (e.g. Base P floor 20% = +0.19%/yr, unchanged
  MaxDD), decomposition confirms it IS beta (ΔSPY-beta +0.02 to +0.14, residual alpha ≈0),
  positive in all three decades — but **every floor level breaches the pre-registered
  survivability bar** (no stress window should erase >2 years of average annual
  contribution; even the smallest floor's 2008-window cost ≈4.7 years of its own annual
  gain). **RESEARCH-ONLY**, with exactly one pre-registered follow-up specified
  (`R2B-F1`: rolling-origin robustness check on P_floor_20/O_floor_35, with the owner
  fixing the survivability standard *before* that run). Full report:
  `docs/research/atlas_offensive/run2b_report.md`.

### R09 — Macro Factor Conditioning v2 (vintage data) — **IN PROGRESS / NOT YET STARTED**
This is the task queued next when this handoff was written. **See §6 for the full,
verbatim locked run prompt** — do not paraphrase it, use it exactly. Status as of this
handoff: pre-registration not yet written, no code yet exists in
`scripts/atlas_offensive_run09/`. If you are resuming this program and R09 has partial
files already (check `scripts/atlas_offensive_run09/`,
`data/research/atlas_offensive_run09/`,
`docs/research/atlas_offensive/run09_preregistration.md`), read whatever exists first —
do not restart from scratch or duplicate work.

## 6. R09 — the exact locked run prompt (verbatim, use as-is)

> You are executing **RUN 09 (R09): Macro Factor Conditioning on Vintage Data** from the
> Atlas Offensive Master Run Book. This is a free-data run: ALFRED vintages only, no
> purchases.
>
> **Read first, in this order:**
> 1. `CLAUDE.md`
> 2. Master Run Book Part A (return-first doctrine, standing rules) + the R09 and R2C
>    cards.
> 3. `docs/research/atlas_offensive/offensive_holdout_declaration.md`, `run02_report.md`,
>    `run2b_report.md` (the DROP/RESEARCH-ONLY verdicts and the reusable Base O /
>    direct-weight machinery).
> 4. The prior macro work you are superseding — read all of it, because R09 exists to fix
>    its specific defects: `docs/research/project_journey.md` sections "FRED-MD Macro
>    Regime Classifier" (V1), "V2 Sprint", "V3: Financial Conditions Anchor Repair",
>    "Macro-Conditioned ETF Tilt Sandbox (Step 2)", "Step 2B", "Step 2C"; and
>    `scripts/build_macro_regime_classifier_v3.py`.
>
> **Why this run exists (internalize before designing).** The growth × inflation quadrant
> idea produced a real +1.41%/4w development-period spread — the `slowdown` sub-regime
> inside neutral_mixed returned +1.47%/4w vs +0.24% in `stress`. But V1–V3 all ended
> RESEARCH-ONLY for three specific, fixable reasons: (a) they used **revised** FRED data
> (look-ahead — the published value at decision time differs from today's revised value),
> (b) optimistic publication lags, and (c) they forced **monthly** macro information into
> **weekly** overlay decisions where it has no weekly content. R09 fixes all three: true
> point-in-time ALFRED vintages, a 2-month publication lag, and conditioning at
> **monthly** cadence on **capital allocation**, not weekly tilts. This is the macro
> family's last honest chance — if it fails under these conditions, it closes
> permanently.
>
> **Type:** Research run. No production changes. Namespace
> `scripts/atlas_offensive_run09/`, outputs `data/research/atlas_offensive_run09/`,
> report `docs/research/atlas_offensive/run09_report.md`. Log every variant in the trial
> registry under R09. Costs: per-instrument R00 library, never flat 10bps. Dev window
> ends 2025-12-31; sealed 2026+ holdout untouchable.
>
> **Pre-register** (`run09_preregistration.md`, before any backtest) exactly the locked
> design below — no additions mid-run.
>
> ## Locked design
>
> **Phase A — Honest vintage macro factor space.**
> 1. Pull the FRED-MD-style series via the **ALFRED vintage** endpoint (free), so each
>    monthly observation uses only the value that was actually published as of the
>    decision date. LOCKED series set: the V3 list plus any V3 series that timed out
>    previously, documented explicitly; if a series has no vintage history, exclude it
>    and record the exclusion.
> 2. Apply a **2-month publication lag** to every series (decision at month t uses data
>    published on/before t−2).
> 3. Expanding-window PCA, quarterly refit, minimum 60 months. Sign-anchor PC1 (growth)
>    on INDPRO and PC2 (financial conditions / inflation) on NFCI, exactly as V3 — do not
>    re-tune the anchoring.
> 4. Classify each month into the four quadrants (expansion / overheating / slowdown /
>    stress) by the signs of PC1/PC2.
>
> **Phase B — Monthly capital conditioning (two bases, both mandatory).**
> - **Base O (vacuum):** the R2B Base O (60/40 SPY/QQQ, weekly, state-set exposure, no
>   defensive machinery). R09 adds a **monthly** quadrant multiplier on gross exposure.
>   LOCKED multiplier grid per quadrant: expansion {1.0, 1.1}, overheating {0.9, 1.0},
>   slowdown {1.0, 1.1}, stress {0.7, 0.85, 1.0}. Evaluate the full factorial
>   walk-forward.
> - **Base P (production stack):** quadrant conditions the sleeve/defense capital budget
>   monthly (equity-risk vs BIL/defense), same LOCKED grid applied to the offense budget.
>   Direct-weight construction on the GGG panel (GGG reproduction gate to ~2e-16 before
>   any arm).
> - Benchmarks: for each base, the unconditioned base and a **pooled** neutral_mixed
>   handling (no quadrant split).
>
> **Phase C — The two questions that decide the verdict.**
> 5. **Holdout rank consistency (the V1–V3 failure point):** do the quadrant forward-
>    return rankings in the development window hold in a walk-forward sense on honest
>    vintages? Report the quadrant return spread by decade and whether the 2024–26
>    "stress-but-rallying" anomaly persists under vintages (V3 could not tell if that was
>    a regime shift or a revised-data artifact — answer it here).
> 6. **Allocation value:** does monthly quadrant conditioning improve net CAGR and log
>    growth vs the unconditioned and pooled baselines, on each base?
>
> **Controls (LOCKED):**
> - Quadrant-label placebo: 200 random monthly quadrant assignments (same quadrant
>   frequencies) — actual must beat ≥90%.
> - Sign-flip control: invert the quadrant→multiplier map — must hurt.
> - 2× cost stress; decade-by-decade decomposition; beta/alpha decomposition per the R02
>   method (a return improvement that is pure beta is labeled beta).
>
> ## Locked success criteria (return-first)
>
> - **Promote-to-Book-design** requires ALL of: (a) holdout/walk-forward rank consistency
>   achieved on honest vintages; (b) monthly conditioning improves net CAGR AND log
>   growth vs both the unconditioned and pooled baselines on at least Base O; (c) beats
>   ≥90% of quadrant placebos; (d) sign-flip hurts; (e) survives 2× costs.
> - **RESEARCH-ONLY** if allocation value is positive but rank consistency still fails, or
>   if the effect is real but decomposes to pure beta (record as a labeled-beta
>   candidate, like the R2B panic floor).
> - **DROP / close the macro family permanently** if quadrants remain unstable under
>   honest vintages OR conditioning does not beat pooling — this is the macro family's
>   third-and-final honest test; a clean negative here retires the branch for good and is
>   a valuable result, not a failure of the run.
>
> ## Prohibited
>
> Holdout access; using revised (non-vintage) FRED data anywhere; grid extensions;
> re-tuning the V3 PCA anchoring; forcing monthly data into weekly decisions; production
> pins/weights/dashboards; `git add -A`.
>
> ## Report and verdict
>
> `run09_report.md` per CLAUDE.md: commands; files; the honest-vintage vs revised-data
> comparison (show how much the look-ahead mattered); quadrant spread by decade; the
> 2024–26 anomaly resolution; both-base allocation-value tables; placebo and sign-flip
> batteries; beta/alpha decomposition; trial count; warnings; git status. Verdict per the
> branches above. Then recommend the next free run (expected: R21 crypto probe — the last
> $0 run in the queue) and restate that Norgate remains the critical-path blocker (R01 →
> R03 → R04).
>
> Never promote anything yourself; pin changes and Book adoption require explicit human
> authorization.

## 7. Git status as of this handoff

Branch `main`. Nothing has been committed by Atlas Offensive work — everything is
untracked or (for `CLAUDE.md`, `README.md`, a few dashboard/journey files) pre-existing
modifications from before this program started, not caused by it. New paths so far:

```
docs/research/atlas_offensive/                    (holdout declaration, preregs, reports, this file)
data/research/atlas_offensive_cost_library.csv
data/research/atlas_offensive_trial_registry.csv
data/research/atlas_offensive_run01/
data/research/atlas_offensive_run02/
data/research/atlas_offensive_run2b/
scripts/atlas_offensive_run01/
scripts/atlas_offensive_run02/
scripts/atlas_offensive_run2b/
```

Nothing staged, nothing committed. **Do not `git add -A`.** When the user is ready to
commit, stage the specific Atlas Offensive paths by name.

## 8. Practical instructions for whoever picks this up

1. Run the session checklist (`pwd`, `git status`, `git branch`, `git worktree list`)
   before anything else — confirm you're in
   `/Users/nicholasturangan/Documents/Portfolio Optimizer` on `main`.
2. Read §2's rules again. They are not optional and this user has been consistent about
   enforcing them (pre-registration before backtests, no promotions, per-instrument
   costs, sealed holdout, namespace discipline).
3. Check whether `scripts/atlas_offensive_run09/` already has partial work (this handoff
   may be stale by the time you read it — a Claude session may have continued past this
   point). If so, read it before writing anything new.
4. If R09 has not started: read the four documents R09's prompt asks for (§6, "Read
   first"), especially the V1–V3 macro history in `project_journey.md` and
   `scripts/build_macro_regime_classifier_v3.py`, so you understand exactly which three
   defects you're fixing and don't re-introduce them.
5. Write `docs/research/atlas_offensive/run09_preregistration.md` locking the exact
   design in §6 before running any code.
6. Reuse `scripts/atlas_offensive_run02/r02_lib.py` machinery (`R02Machinery`,
   `per_instrument_path`, `dev_window`, `core_metrics`, `load_cost_vector`) rather than
   reimplementing the base stack or cost conventions.
7. ALFRED vintage data: FRED's ALFRED system (https://alfred.stlouisfed.org) exposes
   vintage series via the same FRED API with a `vintage_dates` / `realtime_start` /
   `realtime_end` parameter set — verify actual internet/API access before assuming it
   works; if blocked, treat it as a prerequisite failure and STOP AND REPORT per CLAUDE.md
   rather than substituting revised data (that would silently reproduce exactly the V1–V3
   look-ahead bug R09 exists to fix).
8. After R09, update this handoff file's §5 with the new verdict and §7 with the new git
   status, so the next continuation (by any assistant) stays accurate. Keep this file
   current — it is the project's continuity mechanism across sessions/assistants/model
   switches.
9. When done with each run, follow the CLAUDE.md Task Reporting format exactly, and
   always end by restating: nothing is promoted; pin changes and Book adoption require
   explicit human authorization from the user (nicholasturangan).
