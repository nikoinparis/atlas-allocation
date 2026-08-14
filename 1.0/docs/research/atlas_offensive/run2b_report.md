# Atlas Offensive — Run Report: R2B (Exposure-Level Re-Derivation: α Amplitude + Panic Floor)

**Date:** 2026-07-23 (pre-registered same day, before any backtest)
**Type:** Research run. No production pin/code/dashboard changes.
**Production pin (untouched):** `improved_frontier_phase5_fragility_guard`
**Verdicts:** Arm A **DROP the amplitude-increase thesis — α=0.08 is confirmed growth-optimal**
(the historic "cost gate" story is refuted: information, not cost, binds the curve).
Arm B **DROP** (the R2A signal strictly hurts the vacuum base).
Arm C **RESEARCH-ONLY** (real labeled-beta CAGR on both bases, but every floor breaches the
pre-registered 2008 single-window survivability bar; one follow-up pre-registered).

---

## 1. Executive summary

**Arm A — the amplitude question is now closed with a clean answer.** Under measured
per-instrument costs (annualized drag 1.8–2.9bp across the whole grid — negligible), the full
α curve on the production stack is flat to gently declining in return: net CAGR 7.39% at
α=0.08, 7.40% at 0.16, then monotonically down to 7.28% at 0.80. **Gross** log growth
declines the same way — so the binding constraint on amplitude was never the 10bps turnover
cost gate; it is the signal itself: R2A's cut side buys Sharpe (0.996 → 1.063 at α=0.80,
monotone) by giving up return at every step. "Amplitude liberation" was a Sharpe-objective
phenomenon. Under the return-first log-growth objective the walk-forward selector chooses
**α=0.08 at 28 of 35 checkpoints** (0.16 at the other 7). The production amplitude was
already right for this Book.

**Arm B — the vacuum answer is unambiguous.** On Base O (60/40 SPY/QQQ, state-set exposure,
no defensive machinery, unlevered), every α > 0 reduces CAGR and log growth monotonically
(10.94% at α=0 → 9.61% at α=0.80). The structural asymmetry flagged in the pre-registration
dominates: with calm/neutral/recovery_confirmed already at full exposure and no leverage,
the signal's boost side is inert and its cut side only costs return. State-quality scaling
earns no place in an unlevered Book v1; it becomes interesting again only with leverage
headroom (R43), where the boost side can express.

**Arm C — the panic floor is real, beta, and honestly priced.** Raising the offense floor in
deep-drawdown panic weeks (no confirmations, no timing claim) adds net CAGR on both bases
with correct beta labeling (ΔSPY-beta +0.024 to +0.135; residual alpha ≈ 0 to slightly
negative — exactly what "intelligent beta" should decompose to):

- Base P floor 20%: **+0.19% CAGR/yr with unchanged −11.60% MaxDD**, positive in all three
  decades, survives 2× costs. 2008 window cost: −0.90%.
- Base P floor 40%: +0.46%/yr but MaxDD −11.6%→−15.7% and 2008 cost −4.1%.
- Base O floor 0.35/0.50: +0.33%/+0.62%/yr; MaxDD −26.0%→−30.4%/−34.7%.
- 2011 — R02's cost center — is **positive** for the floor everywhere (+0.7 to +3.2pp window
  delta): the unconditional floor holds through whole latch periods, so 2011-type whipsaw
  that killed timed fires does not hurt it.

But the pre-registered survivability bar (no stress window erasing > 2 years of average
contribution) fails at **every** floor level: even the smallest floor's −0.90% 2008 window
delta is ~4.7 years of its +0.19%/yr contribution. Deep-panic beta concentrates its cost in
crashes by construction; whether "2 years" is the right standard is a risk-preference
question the pre-registration reserved for the ambiguous branch → RESEARCH-ONLY with one
follow-up (below), not adoption.

## 2. Commands executed

```bash
pwd; git status --short; git branch --show-current
# pre-registration written first: docs/research/atlas_offensive/run2b_preregistration.md
cd scripts/atlas_offensive_run2b && python3 run_r2b.py   # all arms + controls (~1s)
# trial registry append (27 rows under R2B)
```

Integrity gates passed before any arm: exact GGG reproduction (err 2.1e-16) and the
implementation-equivalence gate — direct weight construction at α=0.08 reproduces the
production-pin path with err **4.3e-19**. Dev window ends at decision row 2025-12-19;
null permutations restricted to dev-window positions; sealed 2026+ holdout untouched.

## 3. Files created

- `scripts/atlas_offensive_run2b/run_r2b.py`
- `docs/research/atlas_offensive/run2b_preregistration.md` (locked before any backtest)
- `data/research/atlas_offensive_run2b/`: `alpha_curves.csv`,
  `arm_a_walkforward_selection.csv`, `arm_c_floor_table.csv`, `nulls_base_P.csv`,
  `nulls_base_O.csv`, `r2b_manifest.json`
- Trial registry: +27 rows under R2B. This report. No production file touched.

## 4. Arm A — full α curve, Base P (dev window, per-instrument costs)

| α | Net CAGR | Log growth | Gross logG | Cost drag/yr | Sharpe | MaxDD | CVaR5 | SPY β | Resid α |
|---|---|---|---|---|---|---|---|---|---|
| 0.08 (prod) | 7.391% | 0.0713 | 0.0715 | 0.018% | 0.996 | −11.6% | −2.45% | 0.238 | 4.61% |
| 0.16 | 7.398% | 0.0714 | 0.0716 | 0.019% | 1.009 | −11.6% | −2.41% | 0.235 | 4.64% |
| 0.24 | 7.384% | 0.0712 | 0.0714 | 0.021% | 1.019 | −11.6% | −2.37% | 0.231 | 4.66% |
| 0.32 | 7.376% | 0.0712 | 0.0714 | 0.022% | 1.029 | −11.6% | −2.33% | 0.228 | 4.69% |
| 0.40 | 7.371% | 0.0711 | 0.0714 | 0.023% | 1.039 | −11.6% | −2.30% | 0.224 | 4.72% |
| 0.48 | 7.357% | 0.0710 | 0.0712 | 0.024% | 1.046 | −11.6% | −2.27% | 0.220 | 4.75% |
| 0.64 | 7.323% | 0.0707 | 0.0709 | 0.027% | 1.057 | −11.6% | −2.23% | 0.212 | 4.81% |
| 0.80 | 7.279% | 0.0703 | 0.0706 | 0.029% | 1.063 | −11.6% | −2.21% | 0.204 | 4.86% |

**Where the curve truly stops and why:** it doesn't stop at a cost wall — cost drag is ~2bp
flat across the grid (the old 10bps model overstated it ~10×, exactly as suspected). The
gross curve declines from α=0.16 onward, so the binder is **information**: R2A's asymmetric
expression (leadership cap kills the boost side when crowded; SP frozen) means higher α is
mostly a de-risking amplifier — it sheds beta (0.238→0.204), collects Sharpe/CVaR, and pays
CAGR. Every α ≥ 0.24 is a Sharpe trade, not a growth trade.

**Walk-forward selection honesty check (log-growth objective, 26w checkpoints, splice costs
charged):** chose α=0.08 at 28/35 checkpoints, α=0.16 at 7/35, never higher. The Moonshot's
"selector picks grid max at every checkpoint" was under Sharpe/tail-utility objectives; under
the return-first objective the production value was already optimal. Both stories are true;
they answer different questions.

**Null battery (50 shuffled-R2A, α=0.16, fresh seed):** actual log growth 0.0714 vs null
mean 0.0702 — nulls hurt (shuffled signal is worse than base, timing direction is real,
consistent with Confirm1's passing control) — but actual sits at the **86th percentile**,
below the 90% bar, because the gain being defended (+0.0001 logG over α=0.08) is ~1bp/yr.
**Arm A verdict: DROP the amplitude-increase thesis.** Owner's Confirm1 context: this
reinforces Candidate C (α=0.16, return-neutral) over A/B (α=0.24, which pays ~0.5–1bp of
growth for Sharpe) if the return-first doctrine governs; the Confirm1 Sharpe-based case for
A/B is unaffected on its own terms.

## 5. Arm B — α-analog on Base O (vacuum)

| α | Net CAGR | Log growth | Sharpe | MaxDD | SPY β |
|---|---|---|---|---|---|
| 0.00 | 10.94% | 0.1038 | 0.872 | −26.0% | 0.577 |
| 0.08 | 10.80% | 0.1026 | 0.881 | −25.8% | 0.564 |
| 0.16 | 10.66% | 0.1013 | 0.889 | −25.5% | 0.551 |
| 0.24 | 10.51% | 0.0999 | 0.897 | −25.2% | 0.539 |
| 0.40 | 10.19% | 0.0970 | 0.907 | −25.3% | 0.513 |
| 0.80 | 9.61% | 0.0918 | 0.895 | −26.0% | 0.487 |

Monotone decline; success criterion (improve log growth vs α=0) fails at every α. Null
battery (α=0.08): actual gain −0.0013 logG (negative), 72nd percentile — moot given the
outright failure. **Arm B verdict: DROP for unlevered Book v1 design.** Design note recorded:
the signal's only monetizable side in a vacuum is de-risking, which costs growth; revisit
solely as a leverage modulator after R43, where the boost side has headroom.

## 6. Arm C — deep-panic offense floor (labeled INTELLIGENT BETA)

| Variant | ΔCAGR | ΔlogG | Δβ | ΔresidAlpha | MaxDD | 2008 window | Δ2008 vs base | 2011 window | ΔCAGR @2× |
|---|---|---|---|---|---|---|---|---|---|
| P floor none | — | — | — | — | −11.60% | −0.4% | — | +0.5% | — |
| P floor 20% | +0.19% | +0.0018 | +0.024 | −0.001 | **−11.60%** | −1.3% | −0.9% | +1.2% | +0.19% |
| P floor 30% | +0.36% | +0.0033 | +0.049 | −0.002 | −12.85% | −2.9% | −2.5% | +2.5% | +0.36% |
| P floor 40% | +0.46% | +0.0042 | +0.079 | −0.004 | −15.65% | −4.5% | −4.1% | +3.7% | +0.46% |
| O floor none (0.20) | — | — | — | — | −26.0% | −20.7% | — | −14.1% | — |
| O floor 0.35 | +0.33% | +0.0030 | +0.067 | −0.004 | −30.4% | −23.0% | −2.3% | −11.8% | +0.33% |
| O floor 0.50 | +0.62% | +0.0056 | +0.135 | −0.009 | −34.7% | −25.5% | −4.8% | −9.6% | +0.62% |

Decade decomposition (Base P): positive contribution in **all three** decades at every floor
(e.g., floor 20%: +0.10pp in 2005–09, +0.15pp in 2010–19, +0.34pp in 2020–25) — the 2008
window cost is recovered within its own decade. Beta labeling verified: the gain decomposes
almost entirely into added SPY beta; residual alpha is zero to slightly negative. This is
what it claims to be.

**Locked survivability bar:** every floor breaches "no stress window erasing >2 years of
average contribution" (floor 20%: −0.90% ≈ 4.7yr; floor 40%: −4.1% ≈ 9yr; O floors ≈ 7–8yr).
2011 is not a cost center for the floor (positive everywhere) — R02's 2011 damage was a
property of *timed* fires, not of unconditional panic beta.

**Arm C verdict: RESEARCH-ONLY (ambiguous branch)** with exactly one pre-registered
follow-up: *R2B-F1 — rolling-origin robustness of P_floor_20 and O_floor_35 (13 origins,
same machinery, no new grid points), with the survivability standard fixed by the owner
BEFORE the run (choices: the 2-year rule as locked here, or an in-decade-recovery rule).
Adopt-into-Book-design only if the chosen standard passes on ≥90% of origins.* The
risk-preference question (how much crash-window pain per unit of CAGR) is the owner's, not
this run's.

## 7. Trial count

Registry rows under R2B: **27** (8 Arm A α + 1 walk-forward arm + 9 Arm B α + 7 Arm C floors
+ 2 null batches of 50). Underlying path evaluations: ~135 (grids, nulls, 2× arms). Zero
grid extensions; zero mid-run parameter changes; R2A internals and leadership cap untouched.

## 8. Warnings and anomalies

1. The run prompt attributes Base O to R02; R02 contained no Base O. It is fully specified
   in the prompt and was built fresh here (flagged in the pre-registration too).
2. The prompt's "beta/alpha decomposition per §63" reference resolves to no section of the
   Master Run Book; R02's decomposition (weekly OLS on SPY; Δβ×SPY-mean vs Δresidual-alpha)
   was used, as pre-registered.
3. The walk-forward-selected path's CAGR (7.90% from 2009) is not comparable to full-period
   fixed-α numbers (different window); only the chosen-α sequence is evidence.
4. Base O's no-leverage cap makes the Arm B boost side structurally inert in the three
   full-exposure states — pre-registered as a reported asymmetry, not patched mid-run.
5. Null permutations were restricted to dev-window positions so no 2026 signal values enter
   dev computations even inside controls.
6. Dev CAGR levels remain higher than pre-R00 reports (per-instrument costs); all deltas are
   internally consistent.

## 9. Recommendations (no promotions; owner authorization required for everything)

1. **Record in the Book design notes:** REGIME_BRAIN amplitude stays α=0.08 (growth-optimal;
   0.16 statistically indistinguishable); state-quality scaling is a Sharpe tool, not a
   growth tool, and is deferred to the leverage era (R43) for any offensive use.
2. **Owner's Confirm1 context:** under return-first, Candidate C (α=0.16+PBI) dominates A/B
   (α=0.24) — A/B's extra Sharpe is bought with growth. The Confirm1 verdicts themselves are
   unaffected.
3. **Panic floor:** hold as RESEARCH-ONLY pending R2B-F1 (above) and the owner's
   survivability standard.
4. **Next free run:** R2C/R09 (macro vintages via ALFRED — the classifier rebuild has three
   honest chances left and needs no purchase), then R21 (crypto probe, free exchange data).
5. **What unblocks with Norgate:** R01 (PIT breadth confirmation, pre-registration already
   locked) → R03 (single-stock universe + momentum family — the program's critical-path
   infrastructure investment) → R04 (Book v1). The R01 blocker remains the only thing
   between this program and its Stage 2 platform.

## 10. Git status after work

Branch `main`; nothing staged or committed. New untracked from this run:
`scripts/atlas_offensive_run2b/`, `data/research/atlas_offensive_run2b/`,
`docs/research/atlas_offensive/run2b_preregistration.md`, this report; modified:
`data/research/atlas_offensive_trial_registry.csv`. Production pins, weights,
`public/dashboard-data.json`, dashboard bundles untouched.
