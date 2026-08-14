# Confirmation Sprint — R2A Amplitude (α) and PBI-Latched Rule

**Date:** 2026-07-07
**Type:** Strict confirmation sprint. All parameters locked before any run. No discovery, no tuning, no new parameters.
**Production pin (unchanged):** `improved_frontier_phase5_fragility_guard` (α=0.08)

---

## 1. Executive Summary

**All three locked candidates pass every locked gate and are CONFIRMED-FOR-HUMAN-REVIEW. Nothing is promoted — pin changes require explicit human authorization, and paper-trading / fresh-week confirmation is strongly recommended because the official holdout is burned.**

| Verdict | Candidate | Full Sharpe (Δ vs pin) | CAGR | One-line read |
|---|---|---|---|---|
| CONFIRMED | **C: α=0.16 + PBI** | 0.9588 (+0.0105) | 7.12% (−0.01pp) | **Safest: return preserved, tightest bootstrap CI, best recovery profile** |
| CONFIRMED | **B: α=0.24 + PBI** | 0.9637 (+0.0154) | 7.07% (−0.06pp) | Best Sharpe; faster post-trough re-risking; PBI increment not independently significant |
| CONFIRMED | **A: α=0.24 alone** | 0.9615 (+0.0132) | 7.06% (−0.07pp) | Clean single-change; thinnest 2×-cost margin (+0.0029) |
| FAIL (as expected) | Throttle arm (reference) | 0.9591 (+0.0108) | 6.91% | Fails Phase D (rolling-origin) again → **research-only permanently per the Frontier-2 stop rule** |

Honest statistical framing: every candidate's bootstrap 95% CI for the Sharpe
delta still straddles zero (best: C at [−0.008, +0.029], P=0.88). These are
gate-passing, direction-robust, control-validated improvements of modest
size (+0.01 to +0.015 Sharpe) — not statistically conclusive edges. The
recommendation ranking for human review is **C first** (it preserves return,
has the highest bootstrap probability, the tightest CI, the best
recovery_fragile profile, and the largest 2×-cost margin among α carriers),
then B, then A.

## 2. Purpose

Confirm or reject the Moonshot Discovery Sprint's α/PBI finding with locked
parameters: the discovery-sprint numbers contained post-hoc elements (α
extension beyond the predeclared grid, the PBI latch fix) and could not be
promoted from the data that produced them. This sprint re-runs exactly those
configurations under the full locked validation battery with fresh-seed
null controls (seed 20260708 vs discovery's 20260707).

## 3. Locked Candidates (no parameter introduced or changed mid-sprint)

- **A:** α=0.24 R2A scale; leadership cap intact; stressed_panic forced to 1.0; no PBI.
- **B:** A + PBI-latched: stressed_panic only; deep-DD latch (min drawdown ≤ −10% within 13 weeks); confirmations = credit confirmation > 0, 4-week breadth change > 0, VIX 1m–3m slope > 0 (all one-week shifted); 2-of-3 → ×1.15, 3-of-3 → ×1.30; never below 1.0; never outside panic.
- **C:** α=0.16 + same PBI rule (control).
- **Comparison arm only:** Frontier-2 down-only vol throttle (26w, clip 0.85–1.00, 4-week update) stacked on the pin. Not combined with A/B/C.

## 4. What Was Read

Moonshot discovery report, Frontier-2 report, production wrapper +
`production_allocator/config/costs/metrics`, Phase D gate definitions
(`phase_frontier10_final_evaluation.py`), project_journey.md, research
scoreboard. Candidate functions are **imported from the already-verified
moonshot/frontier2 modules** — no re-implementation drift (and the α=0.08
equivalence check below proves it).

## 5. Files Created

`scripts/confirm1_alpha_pbi/`:
[confirm_candidates.py](../../scripts/confirm1_alpha_pbi/confirm_candidates.py) (locked definitions),
[run_confirmation_sprint.py](../../scripts/confirm1_alpha_pbi/run_confirmation_sprint.py),
[verify_confirmation_outputs.py](../../scripts/confirm1_alpha_pbi/verify_confirmation_outputs.py).
Outputs (12 required files + per-variant paths) in `data/research/confirm1_alpha_pbi/`.
No production file, registry, `public/`, or `src/` touched.

## 6. How to Run

```bash
cd scripts/confirm1_alpha_pbi
python3 run_confirmation_sprint.py    # ~30s
python3 verify_confirmation_outputs.py
```

## 7. Reproduction and Integrity Verification (all pass)

- Exact GGG reproduction: max abs net-return error **2.12e-16**.
- **Implementation equivalence: the candidate machinery at α=0.08 reproduces
  the production pin path with error 0.00e+00** — the confirmation tests the
  exact production logic at different amplitude, nothing else.
- PBI domain: 49 fire weeks, all inside stressed_panic, none below 1.0.
- PBI truncation-invariance (no-lookahead): pass.
- Accounting (net = gross − cost): pass on all saved paths.
- Manifest locked-parameter consistency: pass.

## 8. Full Metrics (full period, net of 10 bps/one-way; holdout = 104w from 2024-04-19)

| Variant | CAGR | Sharpe | MaxDD | CVaR5 | Calmar | Vol | Avg TO | Holdout Sharpe | Worst month | Worst quarter |
|---|---|---|---|---|---|---|---|---|---|---|
| GGG baseline | 7.14% | 0.9362 | −11.77% | −2.54% | 0.606 | 7.62% | 0.0618 | 2.1510 | −5.78% | −4.98% |
| Production pin | 7.13% | 0.9483 | −11.60% | −2.49% | 0.615 | 7.52% | 0.0674 | 2.1786 | −5.79% | −4.88% |
| **A: α=0.24** | 7.06% | 0.9615 | −11.61% | −2.42% | 0.608 | 7.34% | 0.0797 | 2.2227 | −5.79% | −4.72% |
| **B: α=0.24+PBI** | 7.07% | 0.9637 | −11.61% | −2.42% | 0.609 | 7.34% | 0.0802 | 2.2261 | −5.79% | −4.72% |
| **C: α=0.16+PBI** | 7.12% | 0.9588 | −11.61% | −2.46% | 0.614 | 7.43% | 0.0740 | 2.2045 | −5.79% | −4.80% |
| Throttle arm | 6.91% | 0.9591 | −11.61% | −2.37% | 0.596 | 7.21% | 0.0665 | 2.2467 | −5.79% | −4.69% |

Cost impact: extra annual cost vs pin ≈ 0.064%/yr (A/B), 0.034%/yr (C) —
well inside the 0.15% gate.

## 9–10. Phase D Gates and 2× Cost Stress

All of A, B, C: **PASS all 8 Phase D gates vs the production pin** and PASS
2×-cost stress (full-Sharpe delta at 20 bps: A +0.0029, B +0.0048, C +0.0051
— note C has the *largest* 2× margin; A the thinnest). Throttle arm: FAILS
Phase D (rolling-origin win rate again ~0.50, plus recovery_fragile capture
−0.035) — consistent with Frontier-2; per that report's pre-registered stop
rule it is now classified **research-only permanently**.

## 11. Stress Windows

| Window | Pin | A | B | C |
|---|---|---|---|---|
| GFC 2008 (ann.) | −0.53% | −0.62% | −0.68% | −0.64% |
| COVID 2020 (ann.) | −9.88% | **−7.44%** | **−7.44%** | −8.66% |
| 2022 bear (ann.) | −4.76% | −4.85% | −4.78% | −4.74% |
| Full-period MaxDD | −11.60% | −11.61% | −11.61% | −11.61% |

COVID improves materially (higher α cut offense harder into the crash); GFC
and 2022 are within noise; max drawdown is unchanged to 1 bp.

## 12–13. Recovery and Panic Behavior

- recovery_fragile Sharpe delta vs pin: A −0.0128, B −0.0124, **C −0.0039**
  (gate ≥ −0.05: all pass; C clearly safest).
- Re-risking speed (avg risky exposure in the 13 weeks after the six major
  SPY troughs 2009/2016/2018/2020/2022/2025): pin 48.48%; A 48.44% (−0.05pp,
  neutral); **B 49.14% and C 49.17% (+0.7pp — PBI makes re-risking faster,
  as designed).**
- stressed_panic Sharpe: pin 0.4793 → A 0.4761 (−0.003, within gate),
  B 0.4867 (+0.007), **C 0.4883 (+0.009)** — PBI improves panic behavior.
- PBI fragile-panic audit (B minus A return inside fire weeks, by year):
  positive in 8 of 9 episode-years incl. **2008 (+0.02%)**; worst year 2011
  at −0.08% — far above the −2% rejection threshold. No fragile-panic damage.

## 14–15. Bootstrap and Rolling-Origin (vs pin, 2000 iters, block 13, seed 20260708)

| Candidate | P(better) | Mean ΔSharpe | 95% CI | Rolling-origin win |
|---|---|---|---|---|
| A | 0.775 | +0.0138 | [−0.022, +0.049] | 0.71 |
| B | 0.810 | +0.0160 | [−0.021, +0.051] | 0.77 |
| **C** | **0.880** | +0.0109 | **[−0.008, +0.029]** | 0.74 |

All CIs straddle zero — improvements are robust in direction but not
statistically conclusive.

## 16. Exposure Paths

Average absolute L1 weight difference vs pin: A/B ≈ 1.7%/week, C ≈ 0.9%/week
(small, cost-consistent). By state: candidates hold slightly less offense in
low-quality non-panic weeks (the α cut side), slightly more in high-quality
weeks; B/C add up to +4.5pp offense in confirmed panic-improvement weeks.
Full table: `exposure_paths.csv`.

## 17–20. Verdicts

- **Candidate A — CONFIRMED-FOR-HUMAN-REVIEW.** All locked gates pass;
  shuffled-r2a null percentile **96%** (≥95% bar). Caveats: thinnest 2×-cost
  margin (+0.0029), −0.07pp CAGR, bootstrap CI straddles zero.
- **Candidate B — CONFIRMED-FOR-HUMAN-REVIEW.** Best Sharpe, faster
  re-risking, clean fragile-panic audit. Caveat: the PBI increment alone
  (+0.0022 over A) sits at the 92.5th percentile of placement nulls — real
  gates-wise, but not independently significant; B's case rests mainly on
  the α core.
- **Candidate C — CONFIRMED-FOR-HUMAN-REVIEW and recommended first.**
  Return preserved (7.12%), highest bootstrap probability with the tightest
  CI, best recovery_fragile and stressed_panic profile, largest 2×-cost
  margin, smallest footprint vs the pin.
- **Throttle arm — research-only permanently** (pre-registered stop rule
  triggered a second time on the same gate).

## 21–22. Promotion Status

Nothing is promoted in this sprint. A, B, and C are handed to **human
promotion review** per pin governance. Recommended review order: **C → B →
A**. Strong recommendation attached: given holdout burn, require a
paper-trading window (or the next ~26 weeks of fresh data re-scored by the
locked runner) before any pin change.

## 23. Risks and Caveats

- Bootstrap CIs straddle zero for all candidates; the α effect is a modest,
  robust re-calibration, not a new edge.
- α trades CAGR for Sharpe (A/B −0.06 to −0.07pp). C minimizes this cost.
- All confirmation data overlaps the discovery data; only fresh weeks and
  the fresh-seed nulls are genuinely new evidence here. The A-null (96%)
  passing its bar is the strongest new fact.
- If R2A's information decays, higher α amplifies the decay; the fragility
  guard caps the boost side but not the cut side.
- PBI remains capped by the wrapper (~+0.002); its native-integration
  question (Layer 2B panic sub-state) is an architecture decision for a
  human, not an overlay problem.

## 24. Next Recommended Sprint

1. **Human review of C (primary), B, A** with this report and the
   machine-readable gate tables.
2. If review is positive: **fresh-week confirmation protocol** — freeze the
   locked runner, re-score candidates on new data at +13 and +26 weeks, no
   parameter changes, pre-committed decision rule (C's full-period Sharpe
   delta vs pin remains > 0 and no gate regression).
3. Independent of the pin decision: scope the **native PBI integration**
   (Layer 2B "panic-but-improving" sub-state feeding the allocator's BIL
   budget directly) as a design review, since the wrapper caps the validated
   mechanism at ~1/5 of the mapped opportunity.
