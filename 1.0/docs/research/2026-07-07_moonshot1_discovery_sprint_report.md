# Moonshot Discovery Sprint — Final Report

**Date:** 2026-07-07
**Type:** Discovery research sprint. No production pin changes. No production code modified.
**Production pin (unchanged):** `improved_frontier_phase5_fragility_guard`
**Prerequisite note:** `Quant_Portfolio_Master_Guide.pdf` (listed as required reading) does not exist anywhere in the repository; all other required materials were read.

---

## 1. Executive Summary — was a genuine breakthrough found?

**No candidate reached the sprint's own breakthrough bar (+0.05 Sharpe vs the
production pin), and nothing is promoted.** Saying that clearly first.

What the sprint did find, ranked by evidence quality:

1. **The production signal is systematically under-sized (strongest finding).**
   The pin applies the R2A deployment-quality scale at amplitude α=0.08 — a
   value predeclared conservatively in Frontier Phase 1B and never revisited.
   A walk-forward objective-selection test (no lookahead: at each 26-week
   checkpoint, choose α on expanding past data) picks the **maximum available
   α at essentially every checkpoint since 2009** (100% of weeks at grid max
   under the tail-utility objective, 92% ≥0.24 under Sharpe). The full α
   curve is monotone in Sharpe/CVaR up to the **turnover-cost gate, which
   binds at α≈0.48** — governance, not the data, is the constraint.
   α=0.20–0.40 pass **all 8 Phase D gates** vs the pin. A shuffled-signal
   control at the same amplitude is worse than doing nothing (null mean
   Sharpe 0.913 vs actual 0.962, actual beats **50/50 nulls**) — the gain is
   timing information, not mechanical vol shrinkage.
2. **A structural blind spot with a real but under-powered mechanism.** The
   episode opportunity map shows 67% of early-recovery weeks (the biggest
   repeating per-week opportunity: SPY +73% annualized across 76 weeks) are
   labeled `stressed_panic` — the one state where every prior overlay froze
   its modifier at 1.0 by convention. A "panic-but-improving" (PBI) re-risk
   rule (credit + breadth + VIX-term-structure confirmations inside deep-
   drawdown panic weeks) fires in 9 distinct episodes across 21 years,
   improves stressed_panic Sharpe, beats 91% of random-placement nulls, and
   its inverted control hurts (−0.025) — but its maximum achievable effect
   through the wrapper is ~+0.003 Sharpe because panic weeks hold only ~15%
   offense. The mechanism looks real; the wrapper cannot express it.
3. **The combined candidate passes all 8 gates with return preserved:**
   α=0.16 (the value selected by the *predeclared* walk-forward grid) +
   latched PBI = full Sharpe **0.9600 (+0.0117)** at unchanged 7.13% return,
   stressed_panic Sharpe **improved** (+0.0155), bootstrap P=0.90, rolling-
   origin win rate 0.79, holdout Sharpe 2.2063 (+0.028), better COVID window.
4. **Clean negative results from the AI/ML track:** a walk-forward kNN
   analog engine finds real structure (beats all 50 shuffled-target nulls)
   but only *matches* the hand-built R2A composite (dev rank IC 0.090 vs
   0.092) and delivers far less portfolio value (+0.002 vs +0.012) — the
   hand-built rule is near the information ceiling of the existing feature
   set. Walk-forward k-means state discovery adds nothing (69th percentile
   vs permuted-action nulls). This is evidence, not failure: richer
   representations on these features do not beat the domain composite.

**Promotion status: nothing.** The gate-passing candidates contain post-hoc
elements (α extension beyond 0.16, the PBI latch fix, PBI amplitude), and the
official holdout has been consulted repeatedly across sprints. The correct
next step is a single pre-registered confirmation sprint (below), followed by
human review — per pin governance, which this sprint does not touch.

## 2. What Was Read

Everything from the Frontier-2 sprint audit (project journey all sections,
scoreboard, CLAUDE.md, Track A hardening, production scripts, wrapper,
validation governance, options-convexity ×4, macro-overlay closure, ml_lab
summaries, B6/R2 signal tables, external-research series), plus the
Frontier-2 report itself, `phase_frontier10_final_evaluation.py` (gate
definitions), frontier phase 1/2/4 signal panels, and the Layer 2B state
history. The Master Guide PDF is absent from the repo.

## 3. Opportunity Map (Phase 2 deliverable)

Mechanical episode segmentation of 2005–2026 ([episode_opportunity_map.csv](../../data/research/moonshot1_discovery/episode_opportunity_map.csv)):

| Episode label | Weeks | Share | Pin ann. | SPY ann. | Pin avg BIL | Reading |
|---|---|---|---|---|---|---|
| bull_broad | 320 | 29% | 6.0% | 9.3% | 13% | Known calm-trend gap (PIT-data bound) |
| late_recovery | 224 | 20% | 10.9% | 19.5% | 17% | Moderate gap, partly mandate |
| calm_weakening | 164 | 15% | 11.6% | 19.1% | 17% | Pin handles well |
| chop | 139 | 13% | 11.3% | 28.0% | 44% | Mixed; small windows |
| decline | 137 | 12% | **−9.1%** | **−47.1%** | 44% | **Defense works** |
| early_recovery | 76 | 7% | 11.9% | **+72.6%** | **53%** | **The repeating gap** |
| false_rally | 30 | 3% | +7.1% | +3.3% | 60% | Already handled well |

The top four contiguous opportunity gaps are all early recoveries (2009-03:
−23pp vs the ideal bound; 2020-03: −15pp; 2025-04: −12pp; 2019-01: −10pp).
Cross-tabbing against Layer 2B states: **67% of early-recovery weeks and 100%
of false-rally weeks are `stressed_panic`** — the regime engine correctly
identifies panic but cannot distinguish improving panic from deteriorating
panic, and the production convention freezes all modifiers there.

## 4. The Five Required Directions — findings

1. **New market-state representation.** Two tests. (a) Hand-built: the
   "panic-but-improving" sub-state (PBI) is real — see §5. (b) Learned:
   walk-forward k-means (k=5/7/9) over 19 causal features adds nothing over
   the existing 5-state engine (permuted-action null percentile 69%,
   portfolio delta −0.0003). The existing state engine is better than a
   generic learned one; its one documented deficiency is inside panic.
2. **Recovery timing.** The PBI mechanism: in `stressed_panic` weeks where a
   deep drawdown (≤−10%) occurred within the last 13 weeks, count three
   causal confirmations — credit confirmation > 0, 4-week breadth change > 0,
   VIX term structure back in contango (all shifted one week). Fire offense
   ×1.15 (2 of 3) / ×1.30 (3 of 3); never scale below 1.0; never touch
   non-panic weeks. Fires 49 weeks across 2008/09/11/16/18/19/20/22/25.
   Improvement is spread across episodes; SP Sharpe improves; random-
   placement null percentile 91%; inverted composite hurts −0.025. Effect
   size through the wrapper: +0.0021 (+0.0034 at max amplitude) — **capped by
   the ~15% offense base in panic weeks**, not by the signal.
3. **Cross-asset disagreement.** Investigated through the map first: the pin
   already avoids false rallies well (60% BIL, positive return during them),
   so a false-rally veto has little to add — consistent with Frontier 7A's
   negative lead-lag result. Disagreement signals were instead used as
   *confirmations* inside PBI (credit + breadth + vol structure agreeing),
   where they carry real information (inverted control test).
4. **Meta-strategy / signal-trust engine.** The kNN analog engine *is* a
   trust engine — it decides, from historical analogs, when offense deserves
   more or less budget. Result: real signal, beats all shuffled nulls, but
   does not beat the hand-built R2A composite on the same features (IC 0.090
   vs 0.092; portfolio +0.002 vs +0.012). Feature-group ablations show the
   IC is credit/quality-driven, yet dropping any group barely moves portfolio
   value — IC and decision value are decoupled here. Conclusion: **R2A is
   close to the information ceiling of the current feature set; trust
   engineering should wait for new features (PIT breadth), not new models.**
5. **Objective-function invention.** Walk-forward α-selection under three
   objectives (Sharpe, tail-utility = CAGR − 5·|CVaR| − 2·DD-excess,
   Calmar-blend). Finding: the objective barely matters for *which* signal to
   use, but strongly confirms *amplitude*: Sharpe and tail-utility pick the
   grid maximum at almost every checkpoint since 2009; Calmar-blend prefers
   ~0.17 (its DD denominator doesn't improve with α). The system's binding
   objective is effectively the turnover-cost gate, which is what stops the
   α curve at ~0.40–0.48.

## 5. AI/ML Track — full disclosure (required answers)

**kNN analog engine (M2).** Learns: forward 4-week offense-vs-BIL excess
return by averaging the outcomes of the k=25 most similar past weeks
(19 standardized causal features; expanding standardization; 8-week embargo
> 4-week label horizon; analogs strictly past). Output mapped to a bounded
offense multiplier at production amplitude. Why it might beat a rule:
nonlinear, interaction-aware, nonparametric — suits ~1,000 samples. Leakage
controls: embargo, expanding stats, truncation-invariance verified in code.
Baselines: constant (GGG), walk-forward ridge (same features/target), and
the production R2A rule. Result: kNN dev rank IC +0.090 (ridge +0.038, R2A
+0.092); portfolio delta vs GGG +0.0021 vs R2A's +0.0121; beats 50/50
shuffled-target nulls but fails both gates and the R2A baseline.
**Verdict: research-only negative result — the model class is fine, the
features are exhausted.**

**k-means state discovery (M3).** Learns: 7 market-state prototypes refit
yearly on expanding past data, with per-cluster offense actions estimated
from past cluster-conditional outcomes. Nulls: 200 permuted cluster-action
mappings. Result: delta −0.0003, null percentile 69% — indistinguishable
from noise. **Verdict: drop.**

Deep learning, transformers, and RL were explicitly not attempted: ~1,000
weekly samples with ~20 features cannot support them, the repo's own ml_lab
already documented this failure mode, and both low-capacity ML tracks above
underperformed a hand-built linear composite — capacity is not the binding
constraint.

## 6. Search Accounting and Data-Mining Risk

- Total wrapper evaluations: **488 (main run) + ~270 (follow-ups) ≈ 760**,
  of which ~500 were null-distribution draws (they are controls, not
  candidates) and 62+18 were declared sensitivity grids.
- Selection discipline: primary configs predeclared in code before running;
  sensitivity grids never used for selection; walk-forward selection used
  dev/expanding data only.
- **Post-hoc elements (flagged):** (a) the α extension beyond the predeclared
  0.16 grid boundary; (b) the PBI "latch" fix (motivated by the diagnosed
  2025 timing miss — a framing failure, but still post-hoc); (c) PBI
  amplitude at (1.25, 1.50). Any candidate containing these **requires a
  pre-registered confirmation sprint and cannot be promoted from this data.**
- Holdout burn: the official holdout was consumed only in final gate tables
  (~20 variants), never for selection — but across sprints its evidential
  value keeps degrading; treat holdout numbers as descriptive.

## 7. Metrics Table (full period, net of costs; holdout = 104w from 2024-04-19)

| Variant | CAGR | Sharpe | MaxDD | CVaR5 | Vol | Avg TO | Holdout Sharpe | Boot P | Roll win | Gates vs pin |
|---|---|---|---|---|---|---|---|---|---|---|
| GGG baseline | 7.14% | 0.9362 | −11.77% | −2.54% | 7.62% | 0.062 | 2.1510 | — | — | — |
| **Production pin (α=0.08)** | 7.13% | 0.9483 | −11.60% | −2.49% | 7.52% | 0.067 | 2.1786 | — | — | — |
| M1 PBI (predeclared) | 7.14% | 0.9496 | −11.60% | −2.49% | 7.52% | 0.067 | 2.1786 | 0.88* | 0.53 | FAIL (full Δ +0.0013) |
| M1 PBI latched (post-hoc fix) | 7.15% | 0.9503 | −11.60% | −2.49% | 7.52% | 0.068 | 2.1817 | 0.88 | 0.59 | FAIL (full Δ +0.0021) |
| M2 kNN replace | 6.94% | 0.9383 | −11.87% | −2.44% | — | 0.065 | 2.1547 | 0.11 | 0.26 | FAIL |
| M3 k-means replace | 6.89% | 0.9360 | −11.90% | −2.45% | — | 0.064 | 2.1464 | 0.07 | 0.23 | FAIL |
| α=0.16 (walk-forward-selected) | 7.10% | 0.9566 | −11.61% | −2.46% | 7.43% | 0.074 | 2.2012 | 0.83 | 0.74 | FAIL (full Δ +0.0083 < +0.01) |
| α=0.24 (post-hoc ext.) | 7.06% | 0.9615 | −11.61% | −2.42% | 7.34% | 0.080 | 2.2227 | 0.77 | 0.71 | **PASS 8/8** |
| α=0.40 (post-hoc ext.) | 6.97% | 0.9707 | −11.61% | −2.35% | 7.18% | 0.092 | 2.2608 | 0.75 | 0.73 | **PASS 8/8** |
| α=0.48 | 6.92% | 0.9725 | −11.61% | −2.32% | 7.12% | 0.098 | 2.2742 | 0.73 | 0.73 | FAIL (cost gate 0.16%) |
| **Combo α=0.16 + PBI-latched** | **7.13%** | **0.9600** | −11.61% | −2.46% | 7.43% | 0.075 | 2.2063 | **0.90** | **0.79** | **PASS 8/8** |
| Combo α=0.24 + PBI-latched | 7.08% | 0.9650 | −11.61% | −2.42% | 7.34% | 0.081 | 2.2279 | 0.83 | 0.77 | **PASS 8/8** |

\* bootstrap for predeclared M1 computed in the latched follow-up file.

Stress windows (combo α=0.24+PBI vs pin): GFC −0.73% vs −0.53%; COVID
**−7.4% vs −9.9% (better)**; 2022 bear −4.7% vs −4.8%. Stressed_panic Sharpe
*improves* for all PBI-containing variants (+0.010 to +0.017). Recovery
capture: PBI adds return exactly in the early-recovery windows the map
identified; α slightly trims recovery_fragile (same trade-off as any
amplitude increase — flagged for the confirmation sprint).

## 8. Null / Control Tests

| Test | Result |
|---|---|
| M1 random-placement nulls (200) | actual at 91st pctile (suggestive, not >95%) |
| M1 inverted composite | −0.0253 (fires on non-confirmation hurt — direction is real) |
| M2 shuffled-target nulls (50) | actual beats 50/50 (signal real, just not better than R2A) |
| M3 permuted-action nulls (200) | 69th pctile (noise) |
| α=0.24 shuffled-r2a nulls (50) | actual beats 50/50; null mean *worse than pin* → timing, not vol-shrink |

## 9. What Failed / What Is Promising / What Deserves Promotion

- **Failed:** learned k-means states (M3); kNN as an R2A replacement (M2);
  objective-function inventions as signal-choosers (they only re-confirm
  amplitude); false-rally veto (the map shows the pin already handles it).
- **Promising:** (1) the α amplitude re-calibration — monotone, gate-passing
  to 0.40, walk-forward-supported direction, timing-real by control test;
  (2) the PBI panic-but-improving state — economically grounded, episode-
  diverse, SP-improving, but wrapper-capped at ~+0.003; its full expression
  requires native Layer 2B / allocator integration (a human architecture
  decision, given the journey's warnings about allocator rebuilds).
- **Deserves promotion: nothing in this sprint.** The gate-passing combo
  contains post-hoc elements and the +0.05 breakthrough bar was not reached.

## 10. Required Next Sprint (pre-registration)

> **Confirmation sprint, all parameters locked here before any run:**
> Candidate A: α=0.24 R2A scale (leadership cap intact, SP untouched).
> Candidate B: Candidate A + PBI-latched (gate=2of3, mults 1.15/1.30, latch
> 13w, DD ≤ −10%). Candidate C (control): α=0.16 + PBI. Gates: standard
> Phase D 8 vs the production pin, plus 2×-cost stress, plus the
> recovery_fragile capture delta ≥ −0.05 Sharpe. Include the down-only vol
> throttle from Frontier-2 as a comparison arm only. Success = Candidate A or
> B passes everything; then hand to human review for the pin decision with
> paper-trading/fresh-week confirmation explicitly recommended (holdout is
> burned). Failure = classify the amplitude finding RESEARCH-ONLY permanently
> and stop tuning α. No new parameters may be introduced mid-sprint.

## 11. Files Created / How to Run

All in `scripts/moonshot1_discovery/` (research namespace; production untouched):
[episode_opportunity_map.py](../../scripts/moonshot1_discovery/episode_opportunity_map.py),
[moonshot_features.py](../../scripts/moonshot1_discovery/moonshot_features.py),
[moonshot_models.py](../../scripts/moonshot1_discovery/moonshot_models.py),
[run_moonshot_discovery.py](../../scripts/moonshot1_discovery/run_moonshot_discovery.py),
[run_moonshot_followups.py](../../scripts/moonshot1_discovery/run_moonshot_followups.py),
[verify_moonshot_outputs.py](../../scripts/moonshot1_discovery/verify_moonshot_outputs.py).
Outputs in `data/research/moonshot1_discovery/` (16 required files + paths + manifests).

```bash
cd scripts/moonshot1_discovery
python3 episode_opportunity_map.py
python3 run_moonshot_discovery.py     # ~35s, 488 wrapper evaluations
python3 run_moonshot_followups.py     # ~3min incl. 250 null draws
python3 verify_moonshot_outputs.py    # ALL CHECKS PASS
```

## 12. Risks and Caveats

- The α finding re-sizes an existing signal; if R2A's information content
  decays out-of-sample, higher amplitude amplifies the decay. The shuffled
  control shows historical timing value, not future value.
- Return falls monotonically with α (7.13% → 6.92% at 0.48): this buys
  Sharpe/CVaR with CAGR. The α=0.16+PBI combo is the only variant that holds
  return flat — which is why it is the recommended primary despite its
  smaller Sharpe delta.
- PBI has 49 fire-weeks over 21 years; one bad future episode could erase
  years of contribution. Its per-episode risk is bounded (≤1.5× on a ~15%
  offense base) but not zero — 2008-style improving-then-collapsing panics
  are the failure mode (the 2008 fires cost little historically; verify in
  the confirmation sprint's stress section).
- Objective-sensitivity: Calmar-style objectives do not prefer higher α.
  If the project's true utility weights drawdown recovery time heavily, the
  amplitude case weakens.
