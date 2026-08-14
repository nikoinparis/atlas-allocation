# ATLAS OFFENSIVE — MASTER RUN BOOK
## The Complete, Self-Contained Program of Research Runs for Building a High-Return Machine

**Date:** 2026-07-21 · **Version:** 1.0
**Purpose:** One document containing every recommended research run — with enough backstory that any LLM (or human) can pick up any run cold and implement it correctly.
**Prime directive of every run: RETURN FIRST.** The goal is the highest defensible net compound return. Volatility, drawdown, and Sharpe are *recorded* in every run but they are **not** pass/fail gates until the final risk-engineering stage. The only hard gates during discovery are *integrity gates* — no look-ahead, no survivorship bias, honest costs, honest trial counting. A run fails on fake alpha, never on "too risky."
**Production pin (never touched by any run):** `improved_frontier_phase5_fragility_guard`.

---

# PART A — BACKSTORY: READ THIS BEFORE ANY RUN

## A.1 What this project is and how we got here

Atlas Allocation is a weekly ETF tactical allocation system built over ~60 research phases. Architecture: Layer 1 alpha signals (momentum, trend, reversal, breadth, dollar-strength, macro/VIX features, all lagged 1 week) → Layer 2A sleeves (8 sleeve strategies) → Layer 2B causal 5-state regime engine (`stressed_panic`, `recovery_fragile`, `recovery_confirmed`, `neutral_mixed`, `calm_trend`) → Layer 3 HRP portfolio construction with regime multipliers, target-vol scaling, a BIL (T-bill) defensive overlay, and a crowding guardrail.

Production result: **7.13% CAGR, 0.948 Sharpe, −11.6% max drawdown, SPY beta 0.24, average 27.6% cash.** Over the same period SPY compounded ~10.5%. The system is an excellent *defensive* product — and that is exactly the problem this program exists to solve.

## A.2 The five lessons that shape every run below

**Lesson 1 — The universe was the ceiling, not the ideas.** 35 collinear ETFs behave like ~5 independent bets. Every cross-sectional idea (residual momentum, reversal, carry/value, ML rankers, latent factor discovery) failed or plateaued *on this universe* while the same ideas have strong published evidence *on wide stock universes*. Runs that move to single stocks are not retrying failures; they are running the experiment for the first time.

**Lesson 2 — Long-only strangled the relative signals.** Track C proved reversal/residual-momentum signals have real information (holdout rank IC up to 0.407 — the best signal evidence in the repo) yet lose money expressed as long-only ETF tilts. Long/short expression is not optional for these families.

**Lesson 3 — The defense mandate suppressed measured, validated return.** The Moonshot episode map: in 76 early-recovery weeks SPY compounded at +73% annualized while the system held 53% cash and earned 12%. The four biggest opportunity gaps in 21 years are all early recoveries (−23pp, −15pp, −12pp, −10pp per episode vs the achievable bound). 67% of those weeks are labeled `stressed_panic`, where every overlay multiplier is frozen at 1.0 *by convention*. A validated fix (PBI, below) is capped at +0.003 Sharpe purely by that convention. Separately, the production signal amplitude (α=0.08) is provably 3–6× under-sized — walk-forward selection picks 0.24–0.40 at essentially every checkpoint since 2009, and what stops it is a turnover-cost gate, not information.

**Lesson 4 — Models never beat features here.** A leakage-controlled kNN analog engine found real signal and still only *matched* the hand-built composite (IC 0.090 vs 0.092). GBM, trust models, meta-allocators, learned states — all failed on ~1,000 weekly samples. ML earns its place only after breadth exists (millions of panel observations). Never run heavy ML before the data layer that feeds it.

**Lesson 5 — The options verdicts are void.** All four internal options experiments (v1 REJECT, v2 REJECT, recovery RESEARCH-ONLY, v3 REJECT) priced options with a Black–Scholes proxy on realized vol — a fiction every report itself flags. Options are an *untested* domain, not a rejected one.

## A.3 The return-first doctrine (what "we deal with other metrics later" means operationally)

1. **Primary metrics in every run:** net CAGR, expected log growth, per-trade expectancy, profit factor, and residual alpha after regressing on SPY + standard factors. Rank candidates by these.
2. **Recorded but non-gating:** volatility, max drawdown, CVaR, Sharpe, turnover, concentration. Report them honestly; never reject a candidate for them during discovery.
3. **Integrity gates (always binding):** point-in-time data, survivorship-free universes, 1-period signal lags, time-ordered splits, per-instrument realistic costs (never the old 10bps flat), every tested variant logged in the trial registry, null controls (shuffled/inverted/random-placement) for any headline claim, and the sealed 2026+ holdout untouched.
4. **A "beta is not alpha" rule with a twist:** Track B taught that more return via more beta is trivially available. We still *report* the decomposition (beta vs alpha) in every run — but under the return-first doctrine, *fuller intelligent beta is an acceptable win* (e.g., cutting the 27.6% cash drag) as long as it is labeled as what it is. We just refuse to *call* it alpha.
5. **Risk engineering is Stage 7, not a reflex.** Stops, vol caps, tail hedges, and drawdown budgets are added at the end, priced explicitly (each protection must state how much CAGR it costs). Never re-impose the old 10% vol target, BIL floors, or Sharpe-first gates inside a discovery run.

## A.4 Standing implementation rules for any LLM executing a run

- Read `CLAUDE.md` first. Never modify production code, pins, weights, or `public/dashboard-data.json`. Never `git add -A`; stage files by name.
- Each run works in its own namespace: `scripts/atlas_offensive_runNN/` with outputs in `data/research/atlas_offensive_runNN/`, and ends with a report in `docs/research/atlas_offensive/runNN_report.md`.
- Pre-register before running: hypothesis, candidates, parameter grids, primary metric, success/failure thresholds — written to a file *before* the first backtest. Post-hoc discoveries are allowed but must be labeled post-hoc and re-confirmed in a locked follow-up before being believed (this is how the α/PBI findings were handled — copy that pattern).
- Every run report answers: What was run? What improved *return*? Standalone and in combination with the current best book? Verdict: **Adopt into book / Confirm in follow-up / Research-only / Drop permanently**. Plus: trial count, warnings, git status.
- The stack of record for combination tests is the **Offensive Book** (defined in A.5), not the defensive production pin. The pin is a reporting benchmark only.
- If a prerequisite (data subscription, capital decision, prior run's artifact) is missing: **stop and report**, don't improvise substitutes.

## A.5 The Offensive Book — the single thread connecting all runs

Every run either **adds an engine**, **upgrades a component**, or **replaces a component** of one evolving portfolio called the **Offensive Book**. This is how runs "correlate and keep improving":

- **Book v0** = 100% of offensive capital in the best simple benchmark (SPY buy-and-hold). Any adopted run must beat or diversify this, net of costs.
- Each run card below states **Builds on** (which prior runs/artifacts it consumes) and **Improves or Replaces** (which Book component it upgrades or swaps out).
- After every adopted run, re-run the standing **Book integration test**: does the Book's net CAGR / log growth improve when the new component is added at its proposed weight? A component that wins standalone but not in combination is held in the bench registry, not deleted.
- The Book's component slots: `EQUITY_CORE` (long stock exposure engine), `REGIME_BRAIN` (state machine deciding aggression), `LS_ALPHA` (long/short sleeve), `TREND_MACRO` (futures sleeve), `OPTIONS` (convexity/premium sleeve), `SHORT_HORIZON` (overnight/daily sleeve), `EVENT` (event-driven sleeve), `SIZING` (position sizing/leverage logic), `ALLOCATOR` (capital allocation across sleeves), `DEFENSE` (the old Atlas system, kept as an optional capital-preservation slot — deliberately last).

## A.6 Data purchases the program assumes (buy when the run needing it starts)

| Purchase | ~Cost | First needed by |
|---|---|---|
| Norgate US stocks (PIT constituents, survivorship-free, delistings) | ~$110/mo | Run 1 |
| Sharadar SF1 fundamentals (25y PIT as-reported) | ~$50/mo | Run 6 |
| ORATS or ThetaData options chains (2007+) | ~$100–160/mo | Run 13 |
| Norgate futures or Databento CME (micro futures) | ~$100–200/mo | Run 8 |
| Polygon or Databento intraday bars | ~$125–199/mo | Run 17 |

Free and already sufficient: FRED/ALFRED vintages, SEC EDGAR (Form 4/13F/filings), FINRA short interest, CBOE indices, crypto exchange APIs.

---

# PART B — PROGRAM MAP

## B.1 Stages

| Stage | Runs | Theme | Book effect |
|---|---|---|---|
| 0 Foundation | R00–R01 | Governance + first data unlock | Creates the rules and the breadth signal |
| 1 Internal unlocks | R02, R2B, R2C | Un-freeze the regime engine | Builds REGIME_BRAIN v1 |
| 2 Breadth platform | R03–R07 | Single-stock universe, momentum→factors→long/short | Builds EQUITY_CORE + LS_ALPHA |
| 3 New markets | R08–R12, R17–R21 | Futures, macro, carry, events, earnings, overnight, alt-data, crypto | Builds TREND_MACRO, EVENT, SHORT_HORIZON |
| 4 Options | R13–R16 | The untested domain, on real data | Builds OPTIONS |
| 5 ML ladder | R22–R34 | GBM workhorse + challengers | Upgrades EQUITY_CORE/LS_ALPHA signal quality |
| 6 Math transfers | R35–R41 | Bounded cross-field experiments | Feature/component upgrades anywhere |
| 7 Integration & risk | R42–R47 | Sizing, leverage, allocation, then (and only then) drawdown engineering | Builds SIZING + ALLOCATOR, prices DEFENSE |
| 8 Evergreen | R48–R63 | Refresh, expand, regenerate — the program that never runs out | Continuous Book improvement |

## B.2 The improve-vs-replace convention

Every card carries one of:
- **[ADD]** — creates a new Book component (empty slot filled).
- **[UPGRADE]** — improves an existing component; old version stays as fallback in the bench registry.
- **[REPLACE-IF-BETTER]** — head-to-head against an existing component; winner takes the slot, loser goes to the bench with its results.
- **[FEEDER]** — produces signals/data/infrastructure consumed by other runs, no direct Book slot.
- **[PROBE]** — cheap feasibility test that decides whether a family of runs opens or closes.

## B.3 Critical path and parallel tracks

**Critical path:** R00 → R01 → R03 → R04 (first deployable Book v1) → R05 → R22 → R42 → R43 → R44 → R45 → R47.
**Parallel any time after R00:** futures track (R08→R09/R10/R21), options track (R13→R14/R15/R16), short-horizon track (R17→R18), free alt-data (R19).
**Rule:** at most one heavy run in flight per track; cheap probes may interleave.

---

# PART C — THE RUN CARDS

Template: **Backstory** (why this run exists — what we know), **Mission** (return-first question), **Builds on / Improves-Replaces**, **Do** (implementation sketch), **Success / Failure / Next**.

---

## STAGE 0 — FOUNDATION

### R00 — Governance Reset [FEEDER] · difficulty 2 · $0 · days

**Backstory.** Atlas's greatest asset is its honesty culture: walk-forward labels, pre-registration, null controls. Its old holdout (2024-04-19) is burned from repeated use, and its old gates were Sharpe-first — structurally hostile to return-seeking. Both must be rebuilt before anything else, or every later result is untrustworthy.
**Mission.** Stand up the return-first rulebook every subsequent run obeys.
**Builds on:** existing Phase D validation stack. **Improves:** replaces Sharpe-first gate set with the A.3 doctrine.
**Do.** (1) Seal new holdout: declare a 2026 cutoff date; data after it untouched until final Book promotion. (2) Create trial registry (one table: run_id, variant, params, primary metric, verdict) — *every* variant logged. (3) Write pre-registration template. (4) Build per-instrument cost library: measured ETF/stock spreads, futures commissions+rolls, options at-spread fills, borrow schedule; retire the 10bps flat model. (5) Codify the A.3 return-first metric set as the standard report table.
**Success:** registry + templates exist; first cost library committed. **Failure:** n/a — skipping this is the only failure. **Next:** R01 immediately; R08/R13/R17 may start in parallel.

### R01 — PIT Stock Breadth Confirmation [FEEDER→UPGRADE of REGIME_BRAIN] · difficulty 2 · ~$110/mo · 1–2 weeks

**Backstory.** The single best-validated internal diagnostic: stock-level breadth predicted +0.517% per 4 weeks in calm markets where ETF-level breadth showed −0.457%. But it was measured on survivorship-biased current constituents. The pipeline (`scripts/build_pit_stock_breadth_panel.py`) is already built and waiting for point-in-time data. Calm markets are 27% of all weeks and the system currently earns ~4.2% annualized in them while SPY runs away — this is the cheapest known attack on the biggest passive gap.
**Mission.** Does the breadth lift survive honest data? If yes, how much offense can it justify in calm states?
**Builds on:** R00; Phase 5A scaffold. **Improves:** REGIME_BRAIN's calm-state aggression logic.
**Do.** Buy Norgate. Export PIT S&P 500 membership + delisting-aware prices to 2005. Build `pct_above_200d`, advance/decline, net new highs (weekly, lagged). Reproduce the 5A diagnostic unbiased. If lift ≥ half the biased number, test breadth-scaled offense (pre-registered tiers ×0.85/1.00/1.15, then a bolder ×1.0/1.15/1.30 return-first grid) in calm and neutral states.
**Success:** unbiased lift confirmed → adopt breadth as a REGIME_BRAIN input; feeds R02/R03. **Failure:** lift < half → breadth demoted to diagnostic; Norgate still justified by R03. **Next:** R02 and R03 in parallel.

---

## STAGE 1 — UN-FREEZE THE REGIME ENGINE

### R02 — Offensive Regime Rebuild: PBI Native [UPGRADE of REGIME_BRAIN] · difficulty 5 · $0 · 3–6 weeks

**Backstory.** The most important suppressed finding in the repo. "Panic-but-improving" (PBI): inside deep-drawdown panic weeks, three lagged confirmations (credit improving, 4-week breadth change positive, VIX term structure back in contango) identify improving panic. It fired in 9 distinct episodes over 21 years, beat 91% of random-placement nulls, its inverted version *hurts* (−0.025 — direction is real), it improved stressed-panic performance, and a locked confirmation sprint passed it three ways. Yet its measured effect is ~+0.003 Sharpe — because the production wrapper freezes panic offense at ~15% by convention. Early-recovery weeks are where SPY does +73% annualized. This run removes the freeze.
**Mission.** How much CAGR is recoverable when confirmed-improving panic is allowed real offense?
**Builds on:** R01 (breadth confirmation input); Moonshot/Confirm1 artifacts. **Improves:** REGIME_BRAIN — adds a sixth state `stressed_panic_improving`; the frozen-modifier convention is **replaced**.
**Do.** (1) Implement PBI as a native Layer-2B sub-state (reuse the locked Confirm1 rule: deep-DD latch ≤−10% within 13w; 2-of-3 confirmations ×1.15, 3-of-3 ×1.30 — then extend with pre-registered offense-base grids 25/40/55/70% for the sub-state itself). (2) Hard per-episode stop: if drawdown deepens ≥X% after re-risk, revert to panic defense (grid X ∈ {3,5,7}%). (3) Benchmark the whole state engine against a statistical jump model (transition-penalized clustering) and an HMM for label stability. (4) Replay 2008 explicitly — the improving-then-collapsing panic is THE failure mode.
**Success:** average early-recovery episode capture +5pp or better, 2008 replay survivable → REGIME_BRAIN v2 adopted; feeds R15 (same trigger buys calls). **Failure:** stop-losses can't contain 2008-type reversals → keep PBI at confirmed modest amplitude (the Confirm1 version) and log the ceiling. **Next:** R2B, R2C.

### R2B — Amplitude Liberation (α Re-Derivation) [UPGRADE of REGIME_BRAIN] · difficulty 3 · $0 · 1–2 weeks

**Backstory.** The production offense-scaling signal (R2A state quality) runs at α=0.08, a value pre-declared conservatively in 2026 and never revisited. Walk-forward objective selection — no lookahead — picks α at the top of the grid at essentially every checkpoint since 2009. Higher α passed all old gates up to 0.40, but under the *old* objective it traded CAGR for Sharpe (7.13%→6.97%). That trade was an artifact of the defensive base: with cash floors, scaling "offense" mostly de-risked earlier. On an offensive base the same signal should scale exposure up, not down.
**Mission.** Re-derive the optimal amplitude of state-quality scaling under a log-growth objective on the offensive base (post-R02 REGIME_BRAIN, reduced cash floor).
**Builds on:** R02. **Replaces:** the α=0.08 convention.
**Do.** Walk-forward α selection with expected-log-growth as the objective; cash floor 0–10% except unconfirmed panic; report the full α curve (return, growth, drawdown) rather than a single point; shuffled-signal null at chosen amplitude (the Moonshot control showed the timing is real — verify it still is on the new base).
**Success:** growth-optimal α adopted into REGIME_BRAIN v2. **Failure:** signal value doesn't survive the base change → document and keep state scaling modest. **Next:** R2C.

### R2C — Macro Sub-States for the Dead Zone [UPGRADE of REGIME_BRAIN] · difficulty 5 · $0 · 3–6 weeks

**Backstory.** `neutral_mixed` is 44% of all weeks and is a no-conviction catch-all. Internal macro-quadrant work (growth × inflation factors from FRED data) found a real +1.41%/4w development-period spread — the `slowdown` sub-regime inside neutral_mixed returned +1.47%/4w vs +0.24% for `stress` — but holdout rank order inverted, and weekly-overlay expressions all failed. Diagnosis: vintages weren't used (revised data leaked), lags were too optimistic, and monthly information was forced into weekly decisions.
**Mission.** Split the 44% dead zone into actionable sub-states using honestly-lagged vintage macro data at monthly cadence.
**Builds on:** R02; V1–V3 classifier code. **Improves:** REGIME_BRAIN's neutral_mixed handling.
**Do.** Rebuild the PCA quadrant classifier on ALFRED *vintage* data (free) with a 2-month publication lag; expanding-window, sign-anchored; quadrants condition *monthly offense budgets* within neutral_mixed only; explicitly test whether the 2024–26 "stress-but-rallying" holdout anomaly persists under vintages (it may have been a data artifact).
**Success:** holdout rank consistency + neutral_mixed return improvement → adopt as monthly conditioning layer. **Failure:** quadrants unstable under honest lags → close the macro-overlay family permanently (it will have had three honest chances). **Next:** Stage 2 continues regardless.

---

## STAGE 2 — THE BREADTH PLATFORM (EQUITY_CORE + LS_ALPHA)

### R03 — Single-Stock Universe + Momentum Family [ADD: EQUITY_CORE foundation] · difficulty 5 · in Norgate · 1–2 months

**Backstory.** Lesson 1 in action. Cross-sectional momentum is the most replicated return source in finance (93 countries, a century of data; survives the "replication crisis" audit), and Atlas has never actually tested it — dual-momentum over 35 ETFs is ~5 effective bets, not a cross-section. The panel built here (PIT membership, delisting returns, per-name costs) is the platform every later equity run inherits: this is the program's single most important infrastructure investment.
**Mission.** Build the panel; establish which momentum variants deliver net return on 500–2,000 stocks.
**Builds on:** R01 (Norgate live). **Feeds:** every equity run (R04–R07, R11–R12, R19–R20, R22+).
**Do.** (1) Panel: Russell-1000-like PIT universe, daily prices, delistings, splits/dividends, per-name spread estimates. (2) Variants: 12-1, 6-1, 52-week-high proximity, residual momentum (vs rolling 3-factor fits), vol-scaled, sector-relative. (3) Measure decile spreads (informational) and implementable top-k long portfolios (deployable). (4) Decade-by-decade decomposition; the planning assumption is post-publication decay of ⅓–½ — post-2010 results decide.
**Success:** ≥1 variant with post-2010 net top-k return > SPY → EQUITY_CORE candidate signals exist. **Failure:** nothing beats SPY net → EQUITY_CORE falls back to intelligent-beta (R04 still runs — concentration + regime gating of plain exposure). **Next:** R04 (deploy), R05 (short leg), R06 (factors).

### R04 — Concentrated Compounder: Book v1 [ADD: EQUITY_CORE] · difficulty 4 · in Norgate · 2–4 weeks

**Backstory.** Atlas's HRP allocator spreads capital across everything, always — conviction was never allowed to concentrate. Under return-first, concentration is the cheapest known monetizer of signal strength (breadth × IC arithmetic). This run creates the first deployable offensive product: a 5–20 name portfolio from R03's best ranks, run with the REGIME_BRAIN deciding aggression.
**Mission.** Beat SPY's compound return net of costs with a concentrated, regime-aware, long-only stock portfolio.
**Builds on:** R03 ranks + R02 REGIME_BRAIN. **Improves-Replaces:** Book v0 (SPY) → Book v1; also **replaces** HRP-style dilution for this sleeve.
**Do.** Grid k ∈ {5,10,20}, rebalance ∈ {1w,2w,1m}; sector cap 40%; per-position trailing stops (recorded, since stops are also a return decision); REGIME_BRAIN scales gross exposure 0.7–1.3. Compare directly against the same signals HRP-diluted (the concentration test old Atlas never ran).
**Success:** net CAGR > SPY + 2pp in walk-forward → **Book v1 adopted**. **Failure:** concentration adds turnover and vol but not return → k=20+ diversified variant becomes EQUITY_CORE. **Next:** R05, R06 upgrade its signals; R42 later re-sizes it.

### R05 — Long/Short Equity v1 [ADD: LS_ALPHA] · difficulty 7 · in Norgate · 2–3 months

**Backstory.** Lesson 2. Track C's residual momentum and reversal sleeves had genuine predictive content and still lost money long-only — the short leg is where half (often more) of relative-signal return lives. Nobody has ever shorted a share in this project. The open question isn't the signals; it's whether retail shorting economics (borrow fees, locates, margin) leave the spread intact.
**Mission.** Does a dollar-neutral book on our best relative signals make money net of real borrow/costs?
**Builds on:** R03 panel + signals. **Adds:** LS_ALPHA slot.
**Do.** Easy-borrow large-cap universe only; dollar-neutral, |beta| < 0.1 verified, sector-neutralized; signals: residual momentum + short-term reversal + (post-R06) factor composites; collect live IBKR borrow fees from day one and haircut history with them; cost-doubling stress mandatory; squeeze filter via short-interest screens.
**Success:** net market-neutral return > 5% annualized (report Sharpe, don't gate on it) → LS_ALPHA adopted; opens R07. **Failure:** costs eat it → **document retail L/S infeasibility as a permanent finding**, route relative signals into R04's long-only tilts, close R07. **Next:** R07 if pass; R22 either way.

### R06 — Fundamental Factor Library [UPGRADE of EQUITY_CORE signals] · difficulty 5 · ~$50/mo · 1–2 months

**Backstory.** Atlas has never had a fundamental datapoint in it. Value, quality/profitability, investment, issuance, accruals are among the factors that survive the big replication audits, and they diversify momentum (value-momentum negative correlation is one of the most reliable relationships in equities). Sharadar's as-reported (PIT) fundamentals make this honest at retail cost.
**Mission.** Which fundamental factors replicate on retail PIT data, and do they improve R04's ranks?
**Builds on:** R03 panel. **Improves:** EQUITY_CORE composite; feeds LS_ALPHA and R22's feature library.
**Do.** Value composite (E/P, B/P, FCF/EV, shareholder yield), gross profitability, accruals, net issuance, asset growth, betting-against-beta. FDR control across the family — this is a factor zoo by construction, so the trial registry counts every definition tested. Sanity-check signs against published Ken-French-style series.
**Success:** ≥3 factors with correct-sign post-2010 net spreads → blend into R04 composite (momentum+quality+value ranks). **Failure:** retail data too noisy → single-source risk documented; escalate to better data only if R22 later shows fundamentals matter. **Next:** R11, R12, R22.

### R07 — Statistical Arbitrage v1 [ADD: extends LS_ALPHA] · difficulty 7 · in Norgate · 2–3 months

**Backstory.** Classic distance-pairs trading publicly decayed after 2010 — but the surviving literature points at residual/cluster-based variants and bear-market conditional alpha. Internally, the reversal composite's 0.407 holdout IC (measured on ETFs, never deployable there) is the repo's loudest untested lead. The ETF pair test (HYG/LQD) was two correlated ETFs, not stat arb.
**Mission.** Does daily-frequency residual mean reversion pay after real costs on hundreds of stock pairs?
**Builds on:** R05 (proves shorting economics first — hard prerequisite). **Improves:** LS_ALPHA with a faster, lower-beta return stream.
**Do.** Cluster-based pair formation (graph clustering on correlation/sector), PCA-residual reversal portfolios, Kalman-filter hedge ratios, 1–20d holding, regime-break stops; borrow + cost accounting from R05's measured data; test the bear-market-conditional claim explicitly.
**Success:** net positive expectancy at scale on 2015+ sample → adopt as LS_ALPHA fast sleeve. **Failure:** post-2010 decay confirmed for all variants → permanent close with documentation (valuable negative). **Next:** R37 (transfer-entropy pair discovery) only if this passes.

---

## STAGE 3 — NEW MARKETS AND NEW EFFECTS

### R08 — Micro-Futures Trend Platform [ADD: TREND_MACRO] · difficulty 6 · ~$100–200/mo · 2–3 months

**Backstory.** Trend following is the premium with a century of evidence, positive 2020–25 out-of-sample results, and crisis convexity (2022 was a banner year) — and Atlas's version is a long-only ETF caricature that discards the short half and the leverage. Micro futures ($5/point on MES) made real multi-market trend replication retail-feasible; commission friction is the binding constraint below ~$10–25k allocated. This is the Book's first genuinely non-equity engine.
**Mission.** Positive standalone expectancy, near-zero equity correlation, at solo scale.
**Builds on:** R00 + owner's capital declaration (blocking prerequisite: the futures capital band must be stated). **Adds:** TREND_MACRO slot. **Replaces:** `cta_trend_long_only` sleeve conceptually.
**Do.** 10–15 micro/mini markets (MES MNQ M2K, ZN ZF, micro gold/silver/crude, micro FX majors); multi-speed TSMOM (2w–12m) + breakout ensemble; inverse-vol position scaling; 2× notional cap; roll-cost modeling; benchmark vs SG Trend index and DBMF/KMLM ETFs (if we can't beat the ETF net of everything, hold the ETF — that is a legitimate adoption).
**Success:** expectancy > 0 with corr < 0.3 to equity Book → TREND_MACRO adopted (system or ETF form). **Failure:** micro frictions eat it → hold trend exposure via ETF (DBMF/KMLM) as TREND_MACRO v0. **Next:** R09, R10, R21.

### R09 — Macro Conditioning of Capital [UPGRADE of ALLOCATOR] · difficulty 5 · $0 · 3–6 weeks

**Backstory.** Same evidence base as R2C, different target: instead of sub-dividing a regime state, use the growth/inflation quadrants to tilt capital *across sleeves* monthly (equity vs trend vs defensive). The literature (2024–25 TAA-with-macro-regimes work) supports exactly this monthly-cadence use.
**Mission.** Do macro quadrants improve the Book's sleeve mix over static weights?
**Builds on:** R2C classifier (vintage, lagged); R08 (needs ≥2 sleeves to allocate between). **Improves:** ALLOCATOR (pre-R44 interim version).
**Do.** Quadrant-conditional sleeve budgets, monthly, walk-forward; compare vs fixed mix; robustness: quadrant-boundary perturbations.
**Success:** Book CAGR improves in walk-forward → adopt as interim allocator until R44. **Failure:** no allocation value → quadrants remain a REGIME_BRAIN input only (if R2C passed) or close macro entirely (if R2C also failed). **Next:** R44 inherits whatever wins.

### R10 — Cross-Asset Carry [ADD: extends TREND_MACRO] · difficulty 6 · in futures data · 2–3 months

**Backstory.** Carry — being paid for holding the unpopular side of a curve — is the classic diversifier to trend (negatively correlated in crises, positively additive in calm). Atlas's only carry attempt was an ETF proxy, long-only, which failed exactly as Lesson 2 predicts. Real carry lives on futures curves: backwardation/contango cross-sections in commodities, rate differentials in FX, term premium in bonds, roll-down in VIX futures.
**Mission.** Positive-expectancy carry sleeve uncorrelated to the trend sleeve.
**Builds on:** R08 infrastructure. **Improves:** TREND_MACRO into a trend+carry engine.
**Do.** Commodity curve carry (long backwardated / short contangoed micros), FX carry+momentum+value combined (never carry alone — the crash literature is clear), bond carry, small VIX-futures roll-down sleeve with hard sizing caps. Crash-profile reporting mandatory (carry's tails are its price).
**Success:** carry adds return at low correlation to trend → merge into TREND_MACRO. **Failure:** carry crashes dominate the sample → trend-only TREND_MACRO stands. **Next:** R44.

### R11 — Event-Driven Probe [PROBE→ADD: EVENT] · difficulty 6 · low cost · 2 months

**Backstory.** Merger arbitrage is having its best stretch since 2021 (~500bps median spread over cash; faster regulatory clocks), and it is one of the few hedge-fund staples executable manually at retail in cash deals. Spinoffs, buybacks/issuance, and lockups have decent literatures. The disappearing index effect is the known dud — included as a negative control.
**Mission.** Which event families produce per-event expectancy worth a Book slot?
**Builds on:** R06 (event data via Sharadar + EDGAR parsing). **Adds:** EVENT slot if any family passes.
**Do.** Backtest-then-paper: cash-deal merger arb (spread capture vs deal-break sizing), spinoff parents/children, buyback announcers, index-effect (expected negative). Position caps per deal; break-risk accounting.
**Success:** merger sleeve > cash + 3pp with controlled breaks → EVENT adopted (semi-systematic is acceptable). **Failure:** spreads < retail execution → close; revisit only if deal-flow regime changes. **Next:** R44.

### R12 — Earnings Alpha: PEAD + Revisions [UPGRADE of EQUITY_CORE] · difficulty 6 · low · 2 months

**Backstory.** Post-earnings-announcement drift is contested territory: gone from large caps since ~2006 by some accounts, alive in small/mid caps per 2025 papers. Revision momentum (analysts chasing their own errors) is steadier. Atlas never had earnings dates in its data. Under return-first this is an EQUITY_CORE feature upgrade: earnings-aware entries/exits and a small dedicated small-cap drift sleeve.
**Mission.** Is there net return in post-announcement drift and revision ranks on honest PIT timing?
**Builds on:** R03 + R06 (Sharadar events/estimates). **Improves:** EQUITY_CORE features; possible small EVENT sub-sleeve.
**Do.** SUE ranks, announcement-window returns, drift capture 1–13 weeks, revision momentum ranks; small/mid-cap emphasis with honest liquidity-cost modeling; the large-cap null is the control.
**Success:** small-cap drift net positive post-2015 → adopt as feature + sub-sleeve. **Failure:** dead everywhere → permanent close, feature set still keeps earnings dates (risk management around announcements is free).

### R17 — Overnight & Daily Effects [ADD: SHORT_HORIZON] · difficulty 6 · ~$130–200/mo · 2 months

**Backstory.** The overnight anomaly — close-to-open returns carrying most of equity drift, and essentially all of momentum's alpha (overnight 3-factor alpha 0.95%/mo vs 0.11% intraday) — is persistent since the 1990s, unexplained, and *structurally invisible* to a weekly-rebalance system. This family was never rejected by Atlas; it was never observable.
**Mission.** Can close-to-open exposure patterns add net return after honest overnight spread/slippage?
**Builds on:** R00 cost library; needs intraday/open-close data (first Polygon/Databento purchase) and an event-driven backtest engine (build here — LEAN local or custom; this engine is also R13's prerequisite quality bar).
**Adds:** SHORT_HORIZON slot.
**Do.** Overnight-hold sleeves on liquid ETFs/large caps; momentum-conditioned overnight exposure (hold winners overnight, flat intraday); turn-of-month and seasonality overlays as free riders; execution modeled at MOC/MOO with measured spreads; random-timing nulls.
**Success:** net overnight capture > 2pp/yr on deployed capital → SHORT_HORIZON adopted. **Failure:** costs consume it (the honest risk) → close family, keep the event-driven engine as infrastructure. **Next:** R18 only if pass.

### R18 — Swing Systems (2–10 day) [UPGRADE of SHORT_HORIZON] · difficulty 7 · same data · 2 months

**Backstory.** Between overnight and monthly lives the swing band: gap reversals, post-shock reversion, volume-spike continuation. Retail-sized, capacity-limited edges that institutions leave behind. Internally, short-horizon reversal families showed the repo's best ICs; externally the band is cost-sensitive but real.
**Mission.** Positive per-trade expectancy after costs across three regimes.
**Builds on:** R17 engine + panel. **Improves:** SHORT_HORIZON.
**Do.** Gap-reversal entries, post-shock (>2σ) reversion, volume-conditioned continuation; per-trade stops; expectancy accounting per setup family; random-entry nulls.
**Success:** ≥1 setup family with robust expectancy → add to SHORT_HORIZON. **Failure:** noise → close band, document.

### R19 — Free Alt-Data Screens [FEEDER/UPGRADE] · difficulty 4 · $0 · 3–6 weeks

**Backstory.** SEC EDGAR is a free, timestamped alt-data goldmine Atlas never touched: Form 4 insider cluster buys (decent literature), 13F crowding, congressional disclosures (45-day lag — mostly entertainment, test anyway as a control). All lag-honest by construction since filings carry timestamps.
**Mission.** Do free filing-derived signals add anything to R03/R06 ranks?
**Builds on:** R03 panel. **Improves:** EQUITY_CORE/LS_ALPHA features.
**Do.** EDGAR ingestion pipeline; insider cluster-buy screens (multiple insiders, open-market, size thresholds); 13F holdings-concentration crowding measure (also feeds R39); event-study alphas with entries at filing-date+1.
**Success:** insider cluster alpha positive at honest lags → feature adopted. **Failure:** all priced by filing date → close, keep the pipeline (13F crowding still feeds R39).

### R20 — LLM Text Signals with PIT Discipline [UPGRADE of feature library] · difficulty 7 · low-med · 2–3 months

**Backstory.** 2024–25 literature: LLM-extracted news/filings sentiment shows 3–10 day predictive windows; the two failure modes are backfill bias (news archives rewritten after the fact) and priced-in-ness (signal real but gone before you can trade). The filings-change effect ("Lazy Prices": firms that quietly rewrite their 10-K underperform) is slower and free to test on EDGAR.
**Mission.** Do text features add IC over the price/fundamental feature set *at tradable lags*?
**Builds on:** R03 panel + R19 EDGAR pipeline. **Improves:** feature library for R22.
**Do.** Start with filings diffs (free, timestamped): year-over-year 10-K/Q similarity scores. Then transcript tone/uncertainty (cheap APIs, timestamp-audited). Then news sentiment only with a verified PIT news source. Mandatory control: enter at t+2 — if all signal lives at t0, it was never tradable. LLM outputs cached and versioned for reproducibility.
**Success:** any text feature adds net IC at t+2 → adopt into R22's library. **Failure:** all priced-in → close news branch; filings-diff may still survive as slow factor.

### R21 — Crypto Sleeve Probe [PROBE] · difficulty 4 · $0 · 2–4 weeks

**Backstory.** BTC/ETH trend-follows well historically (retail-driven, high-vol trends), funding/basis carry exists but compressed (basis ~25%→~4.5% over 2024–25; funding positive ~92% of the time on majors), and US-person access to offshore perps is a hard constraint. Worth exactly one bounded probe at small risk budget — a return-first program shouldn't ignore the most volatile liquid asset class, or over-commit to it.
**Mission.** Does BTC/ETH trend + regulated-venue basis justify a 5–10% risk-budget sleeve?
**Builds on:** R08 trend code (same TSMOM machinery, new asset). **Adds:** small TREND_MACRO extension if pass.
**Do.** TSMOM ensemble on BTC/ETH (free exchange data); regulated basis capture feasibility note (CME micro BTC futures vs spot); venue-risk assessment.
**Success:** positive expectancy + diversification at acceptable venue risk → small sleeve. **Failure:** whipsaw-dominated post-2022 → close; re-probe annually (R63).

---

## STAGE 4 — OPTIONS: THE UNTESTED DOMAIN

### R13 — Options Data Foundation + Vol Forecasting [FEEDER] · difficulty 6 · ~$100–160/mo · 2 months

**Backstory.** Lesson 5: every internal options verdict priced a Black–Scholes fiction. Before any options strategy, we need real chains (ORATS/ThetaData, 2007+) and a forecasting layer: HAR-family realized-vol models (the workhorse of the vol literature — beats GARCH), implied-vs-realized gap tracking, term/skew features, and GEX-style dealer-positioning proxies (popular, mixed formal evidence — test against nulls).
**Mission.** Can we forecast realized vol and identify when implied is rich/cheap, better than unconditional rules?
**Builds on:** R00; the R17 event-driven engine if built (otherwise build the options simulator here). **Feeds:** R14, R15, R16, and vol-features into R22.
**Do.** Ingest chains; build surface features; HAR + implied blend forecasts; conditional VRP sign prediction (when does short premium lose?); arbitrage-free surface sanity checks; dealer-positioning features with strict null controls.
**Success:** conditional edge over unconditional VRP established → R14/R15 proceed with signals. **Failure:** no conditioning edge → R14 still tests *unconditional* defined-risk premium (evidence says it pays on average), R15 still tests recovery convexity.

### R14 — Defined-Risk Volatility Premium [ADD: OPTIONS income leg] · difficulty 7 · same · 2–3 months

**Backstory.** Selling insurance pays: the variance risk premium is one of the most persistent premia known — and it blows up (2018 −90%+ for naked products, 2020, the 2025 tariff spike: SVOL −33%). Crowding halved after 2018 (VIX futures OI at half pre-COVID), arguably improving the premium. The retail-survivable expression is *defined-risk only*: put credit spreads and iron condors where max loss is structural, plus small VIX term-structure carry. Atlas's regime engine — which correctly identifies stress — is a genuine comparative advantage for *when not to sell*.
**Mission.** Net CAGR contribution from premium selling that survives its own tail episodes.
**Builds on:** R13 data/signals + REGIME_BRAIN gating (sell premium only outside stress/pre-stress states — pre-register the gate as the *existing* regime states, unchanged, to avoid hindsight gate design). **Adds:** OPTIONS income leg.
**Do.** SPY/SPX put credit spreads and condors, 2–8 week tenors; sizing so a max-loss month costs ≤2% of Book; VIX carry sleeve capped small; stress replay of 2018/2020/2022/2025 analogs including gap-through-strike scenarios.
**Success:** +2pp CAGR contribution surviving all replayed episodes → adopt. **Failure:** tails erase multi-year premium even defined-risk → close income leg; R15's long-convexity leg is unaffected.

### R15 — Recovery Convexity on Real Chains [ADD: OPTIONS convexity leg] · difficulty 6 · same · 2 months

**Backstory.** The one internal options survivor: long calls bought only at defensive→risk-on recovery inflections beat baseline even on pessimistic proxy pricing (0.958 vs 0.948) — but only barely beat an equivalent delta-one tilt (+0.008), on a premium budget so tiny (0.5% NAV) it couldn't matter. R02's PBI state and this run are the same thesis at different convexity: when improving-panic confirms, upside is violent (+73% annualized episodes) and implied vol is still elevated-but-falling — the textbook setup for call spreads.
**Mission.** Does real-chain convexity at PBI/recovery triggers beat the equivalent ETF tilt by enough to earn the slot?
**Builds on:** R02 (triggers) + R13 (chains). **Adds:** OPTIONS convexity leg. **Replaces-if-better:** pure delta-one re-risking from R02 at episode starts.
**Do.** Call spreads/outright calls on SPY/QQQ at PBI fire dates; DTE 60–120; premium budget grid 1/2/4% NAV per episode; the *tilt control* (same signal, same dollars, delta-one) is mandatory — options must beat it, not just baseline; real IV entry levels from chains decide spread-vs-outright per episode.
**Success:** options > tilt meaningfully on real data → convexity leg adopted for recovery episodes. **Failure:** tilt equivalence → drop options leg, R02 re-risks with shares, savings on theta documented.

### R16 — Dispersion & Exotic Structures: Feasibility Note [PROBE] · difficulty 9 · same · 2–3 weeks

**Backstory.** Dispersion (short index vol vs long single-name vol) is institutionally lucrative and retail-hostile: the edge dies in execution across hundreds of single-name spreads. One honest feasibility note prevents this idea from haunting future sessions.
**Mission.** Is any simplified expression (5–10 name "dirty dispersion") viable after full spread costs?
**Builds on:** R13. **Do:** paper-model a 5-name dirty dispersion basket at real spreads; document the execution arithmetic. **Success:** (unlikely) viable → small experiment. **Failure:** documented close — Tier-6 status confirmed, never revisit without institutional execution.

---

## STAGE 5 — THE ML LADDER (SIGNAL FACTORY ON THE PANEL)

### R22 — Gradient-Boosted Ranking Engine [UPGRADE of EQUITY_CORE/LS_ALPHA signals] · difficulty 6 · GPU optional · 2–3 months

**Backstory.** Lesson 4 said models can't beat features on 1,000 samples. On a panel of 1,000 stocks × 3,000 days, the evidence flips: gradient-boosted trees and shallow nets roughly *double* linear strategies' performance in the canonical study and its replications. This is the single most evidence-backed ML bet available, and everything Atlas learned about leakage control now gets applied at proper scale.
**Mission.** Beat the linear composite rank (R03/R06 blend) by ≥50% in IC and in net top-k return.
**Builds on:** R03 panel, R06 factors, R19/R20 features — the 150+ feature library. **Improves:** the ranking signal feeding R04/R05. The linear composite stays as the permanent baseline and fallback.
**Do.** LightGBM ranker; purged K-fold with embargo; expanding-window walk-forward; DSR/PBO per experiment family; SHAP audits (a model whose top features make no economic sense is presumed leaky until proven otherwise); seed-stability (5 seeds, report dispersion).
**Success:** GBM > linear by pre-registered margin OOS → EQUITY_CORE/LS_ALPHA signals upgraded. **Failure:** parity → linear wins (cheaper, robust); ladder above shrinks to curiosity budget. **Next:** R23 always; R24+ only on success.

### R23 — Targets & Labels Laboratory [FEEDER] · difficulty 5 · existing · 3–6 weeks

**Backstory.** Internal work (triple-barrier, decision labels) already hinted that *what you predict* matters more than *what you predict with*. The literature agrees: rank targets, threshold targets ("will it beat costs?"), and barrier labels each beat naive point-return regression in different settings; meta-labeling (predicting when your own signal works) adds a cheap layer.
**Mission.** Which target maximizes realized top-k return per unit of overfit risk, on identical features/models?
**Builds on:** R22 setup. **Improves:** every learning run after it.
**Do.** Fixed GBM + features; swap targets: forward return, rank, top-quintile membership, P(beat costs), triple-barrier, MFE/MAE, log-growth contribution; meta-label layer on the best; identical validation everywhere.
**Success:** a target dominates → becomes house standard. **Failure:** indifference → simplest target (rank) wins by default.

### R24–R29 — The Challenger Ladder [REPLACE-IF-BETTER vs R22] · difficulty 5–8 · GPU rental · interleaved

**Backstory.** Five model families with loud literatures and thin honest finance evidence. Each gets one controlled shot at the R22 champion — same features, same validation, same trial accounting. The published pattern to expect: temporal CNNs (R24) and LSTM/S4/Mamba (R25) rarely beat tuned GBMs on tabular financial panels; transformers/cross-asset attention (R26) occasionally add value on relational structure; GNNs (R27) mostly re-discover what graph-derived *features* already give a GBM — so the baseline is GBM+graph-features, not vanilla GBM; time-series foundation models (R29 — TimesFM/Chronos zero-shot and fine-tuned) showed near-parity with scratch baselines on equities in 2025 benchmarking. R28 (self-supervised embeddings, conditional autoencoders) doubles as the feature-refresh for R30.
**Mission (each):** beat the reigning champion OOS with seed stability, or close the branch cheaply.
**Builds on:** R22/R23. **Rule:** losers are documented and closed — a confirmed negative here saves months later. Only a winner replaces the champion signal.
**Success/Failure:** per-rung pre-registered margins; any rung that wins gets a locked confirmation before adoption (the α/PBI pattern).

### R30 — Analog Retrieval v2 [UPGRADE of REGIME_BRAIN] · difficulty 5 · existing · 3–6 weeks

**Backstory.** The internal kNN analog engine was Atlas's most honest ML result: real signal, matched the hand rule, features exhausted. The features are no longer exhausted — R01 breadth, R2C macro factors, R13 vol-surface features triple the state space. Retrieval ("what happened after the 25 most similar market states?") is interpretable and cheap.
**Mission.** Does enriched-feature retrieval finally beat the hand-built state-quality composite?
**Builds on:** R01+R2C+R13 features; internal M2 code. **Improves-Replaces:** R2A composite inside REGIME_BRAIN if it wins.
**Do.** Re-run the M2 design (k=25, embargo, expanding standardization) on the enriched state vector; same nulls as Moonshot; portfolio-value comparison, not just IC.
**Success:** beats hand composite in decision value → REGIME_BRAIN input upgraded. **Failure:** ceiling persists → strong evidence the regime problem is feature-complete; stop spending on it.

### R31 — Decision-Focused Learning [REPLACE-IF-BETTER vs predict-then-rank] · difficulty 8 · GPU · 2–3 months

**Backstory.** 2024–25 literature: training the forecaster through the portfolio objective (differentiable optimization layers, Sharpe/growth losses) beats two-stage predict-then-optimize on decision metrics — with a documented pathology of turnover inflation. Atlas's Frontier P6 built decision labels but never closed the loop.
**Mission.** Does end-to-end training of the top-k allocation beat R22's two-stage pipeline *net of the extra turnover*?
**Builds on:** R22 champion as baseline. **Do:** cvxpylayers/SPO+ top-k layer; log-growth and cost-aware losses; turnover-inflation check pre-registered as the primary failure mode.
**Success:** net improvement → allocation head adopted. **Failure:** turnover eats it → close, keep two-stage.

### R32–R34 — Execution RL, Generative Stress, Automated Discovery [bounded frontier]

**R32 Execution RL** (after live paper fills exist, R46): offline RL on our own order data vs TWAP/limit-ladder rules; scope strictly execution — portfolio RL stays banned (OOS failure record + sample arithmetic). Success = implementation-shortfall reduction ≥20%.
**R33 Generative stress engine** (after R44): TimeGAN/diffusion scenario generation for stress-testing the Book — never for alpha training (that use is the negative control). Success = coverage of 2008/2020-type paths the historical record undersamples.
**R34 Automated discovery with guardrails:** LLM hypothesis agents + genetic feature synthesis, allowed only with: every generated candidate logged, family-wise DSR, MDL complexity penalties, and a standing rule that nothing agent-found is believed without a locked confirmation run. Mission: one novel validated signal per quarter without becoming an overfit factory.

---

## STAGE 6 — MATHEMATICS TRANSFERS (BOUNDED EXPERIMENTS)

### R35 — MPC Rebalancing [UPGRADE of Book plumbing] · difficulty 6

**Backstory.** Model-predictive control (receding-horizon optimization with costs) is the established math for multi-period rebalancing (Boyd's cvxportfolio lineage). Atlas rebalances myopically. Costs are the tax every sleeve pays; cutting them is certain return.
**Mission/Success:** turnover down ≥20% at flat-or-better return across the Book → adopt as standard rebalancer.

### R36 — Spectral & Signature Features [FEEDER probe] · difficulty 6

**Backstory.** Wavelet multi-scale decomposition and path signatures (active 2024–25 finance literature) are principled ways to encode path shape that hand features may miss. Boundary leakage is the classic implementation bug — audit for it explicitly.
**Mission/Success:** incremental IC in R22 ablations → features adopted; else closed.

### R37 — Transfer-Entropy Lead-Lag [PROBE] · difficulty 7

**Backstory.** Atlas's weekly ETF lead-lag failed (wrong horizon, wrong universe). Information-theoretic directed-flow measures on *daily stock/sector* data are the honest retest, with brutal multiple-testing control.
**Mission/Success:** TE-discovered pairs beat correlation-discovered pairs in R07's machinery → feeds LS_ALPHA; else closed. Requires R07 alive.

### R38 — Geometry Suite: OT, DRO, TDA [PROBE, negative-control framing] · difficulty 7

**Backstory.** Optimal-transport regime distance and distributionally-robust allocation have credible literatures; persistent-homology crash prediction mostly proxies correlation/vol (expected negative — include as the control that keeps us honest).
**Mission/Success:** any component beats its simple baseline (z-score regimes; mean-variance; vol-based warning) → adopt that component; publish the negatives.

### R39 — Network Crowding Gauge [REPLACE-IF-BETTER vs leadership guard] · difficulty 6

**Backstory.** The production fragility guard uses ETF leadership as a crowding proxy — it works but costs SPY exposure. 13F co-ownership centrality (free data via R19) is a richer crowding measure. Internal warning encoded: the absorption-ratio throttle failed because fragility de-risking double-counts stress on a *defensive* base — test only on the offensive Book.
**Mission/Success:** crowding-conditional performance beats the leadership guard → guard replaced; else keep.

### R40 — Causal Robustness Screens [FEEDER] · difficulty 7

**Backstory.** The decay problem (factors fade post-publication) is a causality problem: signals that survive orthogonalization (double-ML) and stay stable across regime environments (invariant prediction) should decay slower. If the screen predicts OOS survival, it becomes a standing filter on every signal the factory produces.
**Mission/Success:** invariant signals demonstrably decay less in our own registry data → screen institutionalized.

### R41 — Complex-Systems Early Warning [PROBE, expected modest] · difficulty 7

**Backstory.** Critical-slowing-down/contagion indicators claim crash early-warning. High false-positive rates documented. One bounded test against VIX/breadth baselines; feeds REGIME_BRAIN only if it genuinely adds warning time.

---

## STAGE 7 — INTEGRATION: TURN ENGINES INTO A MACHINE

### R42 — Sizing Laboratory [ADD: SIZING] · difficulty 5 · prerequisite: ≥3 adopted engines

**Backstory.** Atlas sized by inverse-vol and Sharpe-first instinct. Return-first sizing is Kelly mathematics: log-growth-optimal fractions, shrunk for estimation error (half-Kelly as the sane default), conviction-scaled by signal strength. Sizing is the highest-leverage free upgrade in the program — the same signals at better sizes compound visibly faster.
**Mission.** The sizing rule that maximizes Book log growth at survivable (recorded, not gated) drawdown.
**Builds on:** every adopted engine's return series. **Adds:** SIZING slot.
**Do.** Compare equal-risk, inverse-vol, fractional Kelly (¼/½/full), conviction-scaled, conformal-interval-scaled; estimation-error stress (bootstrap the inputs); report growth-vs-drawdown frontier.
**Success:** growth-optimal sizing beats naive at same realized drawdown → adopt. **Next:** R43.

### R43 — Dynamic Leverage ≤1.5× [UPGRADE of SIZING] · difficulty 6 · prerequisite: owner capital declaration

**Backstory.** The Book runs unlevered until here by design. Modest leverage on a diversified multi-engine book is the classic final return lever: financing at IBKR tiered rates (or embedded via futures), never daily-reset levered ETFs (decay documented). Leverage amplifies model error exactly when correlations converge — hence last, capped, and state-aware.
**Mission.** Does 1.0–1.5× state-conditional leverage raise compound growth net of financing?
**Builds on:** R42 sizing + REGIME_BRAIN (de-lever in stress states — the one defensive reflex allowed early because it's return-motivated: avoiding ruin is a growth strategy).
**Success:** levered log growth > unlevered with survivable stress replay → adopt with hard 1.5× cap. **Failure:** financing + error erase it → Book stays unlevered; futures notional remains the only leverage.

### R44 — Multi-Strategy Capital Allocation [ADD: ALLOCATOR] · difficulty 6 · prerequisite: ≥3 engines in paper

**Backstory.** The end-state: capital flowing across genuinely different engines (equity, trend, options, events, short-horizon) — the diversification Atlas faked with eight flavors of long-only equity beta. Combining modestly-good uncorrelated engines beats perfecting any single one; that arithmetic is the whole reason multi-strategy funds exist.
**Mission.** Book-level net CAGR above the best single engine.
**Builds on:** all adopted engines; R09's interim allocator; RMT-cleaned covariance; strategy-momentum tilts (allocate more to what's working, slowly).
**Do.** Risk-budgeted baseline; monthly reallocation; correlation-regime awareness (crisis convergence modeled); drawdown-aware de-allocation *rules recorded but not yet binding* (they bind in R45).
**Success:** Book > best engine → ALLOCATOR adopted; this Book is the machine. **Failure:** engines too correlated → the honest finding that we built one engine several ways; concentrate capital in the best and keep hunting (Stage 8).

### R45 — Drawdown Engineering, Priced [UPGRADE of Book — the deferred metrics arrive] · difficulty 5

**Backstory.** Now — with real alpha assembled — the other metrics get their turn, exactly as the mandate ordered: last. Every protection (per-position stops, regime de-risking, vol caps, R15 tail hedges, CVaR budgets) is added only with its price tag measured: CAGR given up per point of drawdown saved. Budget: max 20% of Book CAGR may be spent on protection. The old Atlas (DEFENSE slot) competes here as one protection option among several — its true cost is now measurable.
**Mission.** Cut worst-case damage meaningfully for ≤20% CAGR give-up.
**Success:** MaxDD down ≥30% within budget → protections adopted. **Failure:** protection costs more than it saves → run the Book rawer, size DEFENSE slot accordingly, document.

### R46 — Execution & Cost Engine [FEEDER, continuous from first paper trade]

**Backstory.** The 10bps flat assumption once gated real signal amplitude (the α story). From the first paper order onward, measure actual spreads/fills, build limit-order policies, feed measured costs back into every backtest. Cost cutting is riskless return.
**Mission/Success:** measured costs ≤ modeled; models continuously updated; opens R32 if rule-based execution leaves shortfall on the table.

### R47 — Paper-Trading Gate [the only gate before real money] · difficulty 4 · 13+ weeks minimum

**Backstory.** Nothing in this project has ever traded live; there is no internal prior on backtest-to-live degradation. The paper period builds it. Human authorization required for any real capital — that rule survives from the old governance untouched.
**Mission.** Book tracks its backtest expectation within declared confidence bands for 13+ consecutive weeks.
**Success:** owner decision on live capital with degradation data in hand. **Failure:** degradation beyond bands → back to the responsible run with live-vs-backtest diagnostics (usually costs → R46, or regime → R02-family).

---

## STAGE 8 — EVERGREEN RUNS: THE PROGRAM THAT NEVER RUNS OUT

These recur or unlock conditionally — the standing supply of next runs.

### R48 — Quarterly Signal Refresh [recurring]
Re-validate every adopted signal on the newest quarter: IC drift, decay curves vs R40's predictions, regime-conditional health. Any signal two consecutive quarters below its adoption threshold goes to the bench; benched signals showing revival get one locked re-confirmation. *This run is the Book's immune system.*

### R49 — Universe Expansion: Mid/Small Caps [conditional on R03]
Extend the panel to Russell-2000 names with honest liquidity costs. Momentum/reversal/PEAD effects are historically stronger down-cap; costs are too. Return-first question: does the extra spread survive the extra friction?

### R50 — International via ADRs [conditional on R03]
Rerun the R03/R06 factory on liquid ADRs: fresh cross-section, different macro exposures, same infrastructure. Also the honest out-of-sample test for every US-discovered signal.

### R51 — Sector & Industry Rotation Revisited [conditional on R01]
Old sector rotation failed on ETF breadth; with stock-level breadth per sector (R01 data), rebuild sector scores bottom-up. Replaces the failed Phase 4B approach if it wins.

### R52 — Ensemble Regeneration [recurring, semi-annual]
Re-blend all live signals with fresh IC-weighted / regime-conditional weights (the R22 champion re-trained, the linear fallback re-fit). Guards against silent staleness of the combination layer even when components stay healthy.

### R53 — Bench Resurrection Sprint [recurring, annual]
Everything ever benched (failed runs, retired signals, losing challengers) gets one annual look: has new data/infrastructure changed any verdict? The registry's `no_retest_justified` rows stay dead; everything else is eligible. This is where "completely replace a part" happens on schedule.

### R54 — Capacity & Slippage Audit [recurring, tied to capital growth]
As capital grows, re-test every sleeve's edge at the new size; retire capacity-constrained edges gracefully (swing/event sleeves first).

### R55 — New-Data Probe Slots [standing]
A permanent budget for one new dataset probe per quarter (next candidates: cheap estimate feeds for R12 upgrade, borrow-fee history vendors, transcript embeddings archive, futures tick data for R08 speed-up). Each probe: 2 weeks, pre-registered, adopt-or-drop.

### R56 — Volatility Surface Alpha [conditional on R13/R14 adoption]
Second-generation options: cross-sectional single-name vol screens (rich/cheap IV vs forecast), earnings-vol calendars, skew trades. Only if the index-level program earned its slot.

### R57 — Treasury & Rates Macro Sleeve [conditional on R08]
Duration timing and curve trades (2s10s steepeners/flatteners via micro yield futures) using R2C's macro factors. The natural second use of the futures stack.

### R58 — Leveraged Recovery Protocol [conditional on R02+R43]
The maximum-aggression composite: PBI-confirmed early recovery + R43 leverage + R15 convexity simultaneously — the full return-first expression of the single best episode type in the dataset. Pre-registered episode caps; this is the Book's designated "swing big when it's time" module.

### R59 — Short-Side Alpha Specialization [conditional on R05]
If shorting economics work, build the dedicated short book: issuance/dilution screens, accrual deterioration, failed-momentum, lockup expiries. Short alpha decays slower (fewer players can hold it).

### R60 — Cross-Engine Signal Sharing [conditional on ≥3 engines]
Systematically test every engine's internal state as a feature for every other engine (trend-sleeve drawdown as equity de-risk signal; options skew as reversal timing; breadth as futures filter). The correlation structure of *signals*, not just returns.

### R61 — Second ML Generation [conditional on R22 + 2 years of data growth]
Re-run the challenger ladder (R24–R29 families, updated architectures) once the panel has grown and the first generation's verdicts are two years stale. Model verdicts expire; this run enforces that.

### R62 — Alternative Return Streams Probe [standing, annual]
One structured look per year at anything newly feasible: prediction markets at scale, new listed products, tokenized assets with real liquidity, new micro futures launches. Two-week probes, registry-logged.

### R63 — Annual Program Audit [recurring]
The meta-run: re-read this run book against the registry; retire finished branches; write the next year's run cards; re-rank everything by realized (not projected) return contribution. Produces version N+1 of this document.

---

# PART D — QUICK REFERENCE

## D.1 Run index by Book component

| Component | Creating run | Upgrading runs | Potential replacers |
|---|---|---|---|
| EQUITY_CORE | R03/R04 | R06, R12, R19, R20, R22, R23, R49–R52 | R31 (allocation head) |
| REGIME_BRAIN | R02 | R01, R2B, R2C, R30, R41 | R30 (if retrieval wins) |
| LS_ALPHA | R05 | R07, R22, R37, R59 | — |
| TREND_MACRO | R08 | R10, R21, R57 | ETF fallback (DBMF/KMLM) |
| OPTIONS | R14/R15 | R13, R56 | R15 tilt-control may delete convexity leg |
| SHORT_HORIZON | R17 | R18 | — |
| EVENT | R11 | R12 | — |
| SIZING | R42 | R43, R58 | — |
| ALLOCATOR | R09 (interim) | R44, R35, R60 | R44 replaces R09 |
| DEFENSE | legacy Atlas | R45 prices it | R45 may shrink it to zero |

## D.2 If you only have time for five runs

R01 (breadth) → R02 (PBI native) → R03 (stock universe) → R04 (Book v1) → R08 (futures trend). That sequence alone plausibly moves the Book from a 7% defensive machine to a diversified return-seeking one, for ~$250/month of data.

## D.3 Failure is output

Every closed branch above is listed with its closure condition. A run that ends in a documented, null-controlled negative has done its job — it prevents the same idea from consuming a future session. The registry (`atlas_offensive_future_run_registry.csv` + trial registry from R00) is the memory; this book is the map. Update both, always.

---

*Master Run Book v1.0 · 2026-07-21 · Companion to the Atlas Offensive Exhaustive Discovery Blueprint. The blueprint holds the full evidence base (catalogs, ledgers, coverage disclosure); this book holds the executable program. Production pin untouched: `improved_frontier_phase5_fragility_guard`.*
