# Atlas Offensive — Run Report: R02 (Offensive Regime Rebuild: PBI Native)

**Date:** 2026-07-22 (pre-registered 2026-07-21, before any backtest)
**Type:** Research run. No production pin/code/dashboard changes.
**Production pin (untouched):** `improved_frontier_phase5_fragility_guard`
**Run verdict: DROP the uncap thesis permanently** (pre-registered branch: placement nulls
not beaten AND inverted control fails to hurt). The Confirm1 wrapper-amplitude PBI candidates
(A/B/C) remain CONFIRMED-FOR-HUMAN-REVIEW — their evidence is untouched by this result.

---

## 1. Executive summary

The native `stressed_panic_improving` sub-state was implemented exactly as pre-registered
(locked Confirm1 fire rule, offense bases {25/40/55/70}%, per-episode stops {3/5/7}%,
per-instrument costs, walk-forward, dev window ending 2025-12-31). The best of 12 locked
variants (B=55%, S=7%) raises dev net CAGR by **+0.26%** and log growth by +0.0024 vs the
unmodified GGG base, and survives 2× costs. But every locked success gate beyond that fails:

| Gate (locked) | Bar | Result | Pass |
|---|---|---|---|
| Mean episode capture | ≥ +5pp ann. | **+2.17pp** (95% episode-bootstrap CI [−2.03, +6.05]) | **FAIL** |
| Containment | worst episode ≥ −2yr of avg contribution | worst −2.52% (2011-09) ≈ 10 yrs | **FAIL** |
| Placement nulls (200) | actual ≥ 90th pctile | **66.5th pctile** (null mean +0.10%) | **FAIL** |
| Inverted control | must hurt | **helps: +0.20%** (101 inverted fires) | **FAIL** |
| Full-period ΔCAGR & Δlog-growth > 0 | >0 | +0.26% / +0.0024 | pass |
| 2× per-instrument costs | Δ>0 at 2× | +0.25% | pass |

**The mechanism the improvement actually uses is generic panic beta, not confirmation
timing.** Randomly placed offense boosts across stressed_panic weeks gain +0.10% CAGR on
average; firing on *negative* confirmations gains +0.20% — nearly identical to the real
signal's +0.26%. The beta/alpha decomposition agrees: of the +0.26% improvement, ~+0.14%/yr
comes from higher SPY beta (0.241→0.254) and only ~+0.01%/yr from residual alpha
(4.55%→4.64%). At native amplitude, on a return metric, PBI's confirmations add nothing that
"more offense in deep-drawdown panic weeks" doesn't add on its own.

Two pre-registered expectations were also overturned (both informative):

1. **2008 was not the failure mode.** The feared improving-then-collapsing panic — including
   the single 2008-09-05 pre-Lehman fire — contributed *positively* at every offense base
   (2008-02: +0.63%, 2008-09: +0.25% at B55). The actual damage was **2011-09 whipsaw**
   (−2.52%) and late 2020-05 fires (−0.75%), neither of which the stop grid can catch: 2011's
   loss accrues in the post-fire tail below stop resolution.
2. **The stops hurt more than they protect.** S=3%/5% stops trigger in the January–February
   2009 final leg down and disable 5–6 fires that would have caught the March 2009 rebound —
   the loosest stop (7%) dominates the grid everywhere. A drawdown stop inside a panic
   re-risking rule sells the bottom by construction.

## 2. Commands executed

```bash
pwd; git status --short; git branch --show-current; git worktree list
# descriptive recon (fire weeks, offense shares, episode clustering) — before pre-registration
# pre-registration written: docs/research/atlas_offensive/run02_preregistration.md
cd scripts/atlas_offensive_run02
python3 run_phase_a.py    # 12 locked variants + 2x arms + episode attribution + 2008 replay (~8s)
python3 run_phase_c.py    # 200 placement nulls + inverted control + episode bootstrap (~6s)
python3 run_phase_b.py    # jump model λ∈{1,2,4} + 5-state HMM benchmark (~4s)
# trial registry append (32 rows under run_id R02)
```

Integrity checks: exact GGG reproduction err 2.12e-16; all stops causal (decision t+1 uses
returns through t, forward-sequential recomputation); dev window truncated at decision row
2025-12-19 (last forward week completing before 2026); sealed holdout untouched (no 2026
fire weeks exist; no post-2025 row used in any metric or selection).

## 3. Files created

- `scripts/atlas_offensive_run02/`: `r02_lib.py`, `run_phase_a.py`, `run_phase_b.py`, `run_phase_c.py`
- `docs/research/atlas_offensive/run02_preregistration.md` (locked before any backtest)
- `data/research/atlas_offensive_run02/`: `phase_a_variant_table.csv`,
  `phase_a_episode_attribution.csv`, `phase_a_stop_log.csv`, `phase_a_2008_replay.csv`,
  `base_and_pin_metrics.csv`, `path_ggg_base_1x.csv`, `path_pbi_native_B55_S7.csv`,
  `phase_b_label_benchmark.csv`, `phase_c_null_distribution.csv`, `phase_c_summary.json`,
  manifests
- `data/research/atlas_offensive_trial_registry.csv`: +32 rows (run_id R02)
- This report. No production file, pin, weight, `public/`, or dashboard bundle touched.

## 4. Base, pin, and best variant (dev window, per-instrument costs)

| Variant | Net CAGR | Log growth | Sharpe | MaxDD | CVaR5 | Vol | Avg 1-way TO | SPY beta | Resid. alpha |
|---|---|---|---|---|---|---|---|---|---|
| GGG base (unmodified) | 7.36% | 0.0710 | 0.980 | −11.72% | −2.50% | 7.55% | 0.062 | 0.241 | 4.55% |
| Production pin (reference) | 7.39% | 0.0713 | 0.996 | −11.60% | −2.45% | 7.44% | 0.067 | 0.238 | 4.61% |
| **pbi_native_B55_S7 (best)** | **7.62%** | **0.0734** | 0.997 | −11.72% | −2.52% | 7.66% | 0.076 | 0.254 | 4.64% |

Per-state expectancy (ann.): identical to base everywhere except the sub-state — fire weeks
improve from +2.6% (base) to +8.2% (B55_S7). Risk metrics recorded, not gated: MaxDD/CVaR
essentially unchanged; vol +0.11pp; turnover +1.4pp/week.

Note: dev-window CAGR levels are higher than older reports because per-instrument costs
(~0.3–1.9bp one-way) replace the retired 10bps flat model and the window differs; all
comparisons here use identical conventions, so deltas are apples-to-apples.

## 5. Phase A — 12 locked variants (dev window)

| Variant | ΔCAGR | Δlog-growth | Capture pp | Stops | Worst episode | ΔCAGR @2× |
|---|---|---|---|---|---|---|
| B25_S3 | −0.050% | −0.0005 | −0.08 | 2 | −0.88% (2009) | −0.050% |
| B25_S5 | +0.029% | +0.0003 | +0.25 | 1 | −0.88% (2011) | +0.029% |
| B25_S7 | +0.042% | +0.0004 | +0.28 | 0 | −0.88% (2011) | +0.041% |
| B40_S3 | −0.065% | −0.0007 | +0.36 | 2 | −1.80% (2009) | −0.067% |
| B40_S5 | −0.021% | −0.0002 | +0.47 | 2 | −1.80% (2009) | −0.022% |
| B40_S7 | +0.150% | +0.0014 | +1.20 | 0 | −1.70% (2011) | +0.148% |
| B55_S3 | −0.082% | −0.0008 | +0.85 | 2 | −2.73% (2009) | −0.084% |
| B55_S5 | +0.022% | +0.0002 | +1.12 | 1 | −2.73% (2009) | +0.019% |
| **B55_S7** | **+0.257%** | **+0.0024** | **+2.17** | 0 | −2.52% (2011) | +0.254% |
| B70_S3 | +0.031% | +0.0003 | +1.94 | 2 | −3.33% (2011) | +0.028% |
| B70_S5 | +0.042% | +0.0004 | +1.75 | 1 | −3.66% (2009) | +0.038% |
| B70_S7 | +0.042% | +0.0004 | +1.75 | 1 | −3.66% (2009) | +0.038% |

Containment fails for all 12. The stop column tells the structural story: every triggered
stop lands in 2009-01/02 or 2022-06/09 — the final legs of bear markets — and the disabled
fires are the recovery weeks the run was designed to catch. (B70_S5 and B70_S7 trigger on
different dates but disable the same five 2009 fires, hence identical paths.)

## 6. Best-variant per-episode attribution (B55_S7)

| Episode | Weeks | Fires | Variant ann. | Base ann. | Capture pp | Contribution |
|---|---|---|---|---|---|---|
| 2008-02 | 14 | 4 | −0.0% | −2.3% | +2.3 | +0.63% |
| 2008-09 (pre-Lehman) | 5 | 1 | −36.1% | −37.8% | +1.7 | +0.25% |
| 2009-01 | 24 | 9 | −0.1% | −3.8% | +3.8 | +1.76% |
| **2011-09** | 12 | 4 | −6.4% | +4.5% | **−10.8** | **−2.52%** |
| 2016-02 | 9 | 5 | +22.0% | +9.6% | +12.4 | +1.90% |
| 2018-12 | 11 | 5 | +18.7% | +10.9% | +7.9 | +1.50% |
| 2020-05 | 13 | 6 | +12.1% | +15.4% | −3.3 | −0.75% |
| 2022-03 | 44 | 11 | +2.6% | +0.4% | +2.2 | +1.87% |
| 2025-05 | 8 | 4 | +16.9% | +13.6% | +3.3 | +0.46% |

Mean capture +2.17pp; episode-blocked bootstrap 95% CI [−2.03, +6.05] — straddles zero.

## 7. 2008 replay (the pre-registered stress section)

Full weekly detail in `phase_a_2008_replay.csv`. Summary: the 2008-02 episode (4 fires,
spring bear rally) and the single 2008-09-05 fire two weeks before Lehman both end
*positive* for the variant — during those specific fire windows the GGG offense basket fell
slightly less than the defensive mix it replaced, and the stop was never needed. At B70 the
2008 contributions remain positive. **The 2008 improving-then-collapsing failure mode that
motivated the stop grid did not materialize; the binding failure mode is 2011-type post-fire
whipsaw, which no stop in the locked grid can reach (the loss accrues below stop resolution
in the episode tail).**

## 8. Phase B — label-stability benchmark (not a replacement decision)

| Arm | Transitions/yr | Median spell | ΔCAGR vs base (common action rule) |
|---|---|---|---|
| **Production 5-state** | 9.8 | 3w | **+0.198%** |
| Jump model λ=1 | 7.4 | 5w | +0.108% |
| Jump model λ=2 | 7.7 | 5w | +0.156% |
| Jump model λ=4 | 6.1 | 6w | +0.123% |
| HMM 5-state | 9.0 | 3w | +0.117% |

The statistical models produce more stable labels (as designed) but every one delivers less
portfolio value than the production labels under the identical expanding state-conditional
action rule. Consistent with Moonshot M3: the hand-built regime engine remains the best
label source on this feature set. REGIME_BRAIN keeps its slot; benchmark documented.

## 9. Null battery (Phase C, best variant, seed 20260721)

- **Placement nulls (200, dev SP-week domain, same fire count and grade mix, no-stop):**
  null mean ΔCAGR **+0.103%**, actual +0.257% at the **66.5th percentile** (bar ≥90%). FAIL.
- **Inverted-confirmation control (101 fires):** ΔCAGR **+0.203%** — it helps. FAIL (must hurt).
- **Episode bootstrap:** mean capture +2.17pp, 95% CI [−2.03, +6.05]. Not distinguishable
  from zero.
- **2× per-instrument costs:** best variant ΔCAGR +0.254%, Δlog-growth +0.0023 — survives
  (costs are not the binding issue at these spread levels).

## 10. Verdict (pre-registered branching)

**DROP the uncapped native-PBI thesis permanently.** The pre-registered branch for "nulls
not beaten" applies, reinforced by the inverted control failing in the worst possible way
(it helps). What Confirm1 validated at wrapper amplitude on a Sharpe metric does not carry
specific timing value at native amplitude on a return metric: the return lift is available
to *any* offense boost in deep-panic weeks, with the confirmations adding ~+0.05% over
random placement — noise-level.

Standing consequences, recorded for the registry and future sessions:

1. `stressed_panic_improving` as a high-offense native sub-state is closed. Do not re-test
   without a fundamentally new confirmation signal (e.g., PIT stock breadth after R01 —
   pre-declared enrichment, would require a fresh locked run).
2. The **Confirm1 candidates (C/B/A) are unaffected** — their claim (modest Sharpe
   improvement at ×1.15/1.30 wrapper amplitude, fresh-seed nulls passed) stands and remains
   the owner's pending promotion decision.
3. **Post-hoc observation (labeled POST-HOC, not tested here):** placement nulls gaining
   +0.10% CAGR on average says the base systematically under-holds offense in deep-panic
   weeks *generically*. Under doctrine A.3.4 this is a candidate *labeled intelligent-beta*
   win (a panic offense floor), not an alpha claim. If pursued, it needs its own
   pre-registered run with beta honestly declared. It is NOT adopted from this data.
4. **R2B guidance:** R2B (α re-derivation) remains viable as the next free run — its
   evidence base (walk-forward α selection, shuffled-signal controls at 96th percentile) is
   independent of this failure. But its run card assumes a post-R02 offensive base; since
   REGIME_BRAIN v2 does not exist, R2B must be re-scoped to the existing base and its
   pre-registration must not reference the dropped sub-state.

## 11. Trial count

Registry rows under R02: **32** (12 variants + 12 two-x arms + null batch + inverted +
bootstrap + 5 Phase B arms). Underlying path evaluations: ~250 primary (variants, nulls,
controls, benchmark arms) plus ~450 stop-iteration recomputations inside the sequential
stop machinery. Zero grid points added beyond the locked design; zero mid-run parameter
changes.

## 12. Warnings and anomalies

1. Dev CAGR levels (7.36% base) sit above older 10bps-flat reports — cost model change,
   documented in §4; all deltas are internally consistent.
2. B70_S5 and B70_S7 produce identical paths (different trigger dates, same disabled set).
3. The stop grid interacts pathologically with bear-market bottoms (sells before rebounds);
   any future stop design inside panic re-risking should key on market state, not portfolio
   drawdown.
4. Phase B jump/HMM are from-scratch numpy implementations (DP clustering; log-space EM);
   deterministic under seed 20260721.
5. The registry logs the 200-null batch as one row (distribution saved to
   `phase_c_null_distribution.csv`); counting nulls individually the run evaluated ~460
   distinct configurations.

## 13. Git status after work

Branch `main`; nothing staged or committed. New untracked from this run:
`scripts/atlas_offensive_run02/`, `data/research/atlas_offensive_run02/`,
`docs/research/atlas_offensive/run02_preregistration.md`, this report; modified:
`data/research/atlas_offensive_trial_registry.csv`. Production pin, weights,
`public/dashboard-data.json`, dashboard bundles untouched. Nothing promoted; pin changes
and Book adoption remain gated on explicit human authorization.
