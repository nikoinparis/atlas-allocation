# Frontier-2 Risk-Structure Overlay Sprint — Final Report

**Date:** 2026-07-06
**Type:** Research sprint. No production pin changes. No dashboard/public changes.
**Production pin (unchanged):** `improved_frontier_phase5_fragility_guard`
**Rollback pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Official shadow (unchanged):** `improved_phase2b_combo_abc`

---

## 1. Executive Summary

This sprint searched for overlay-style improvements to the current production
wrapper using signal families the stack has never tested at portfolio level:
VIX term-structure stress/resolution gating, DAA-style canary cash gating,
Kritzman absorption-ratio fragility throttling, and Moreira-Muir volatility-managed
offense scaling. All four were implemented as bounded, causal, one-week-lagged
checkpoint modifiers stacked on the production pin, evaluated with the full
Phase D 8-gate framework, block bootstrap, rolling-origin windows, three stress
windows, and predeclared parameter-sensitivity grids.

**Nothing is promoted.** On the predeclared primary configurations:

- **O1 VIX term-structure gate: DROP** (full Sharpe −0.0014, bootstrap P=0.334).
- **O2 canary cash gate: RESEARCH-ONLY** (full +0.0008 — a rounding error; the
  regime engine already does this job).
- **O3 absorption-ratio throttle: DROP** (negative everywhere, 0/18 grid
  configs positive — a useful negative result: correlation-concentration
  de-risking double-counts stress in an already-defensive portfolio).
- **O4 vol-managed offense: RESEARCH-ONLY** (full +0.0059, holdout +0.1280,
  8/8 grid configs positive, but misses the +0.01 full-Sharpe gate and the
  0.60 bootstrap gate, and worsens the COVID window by ~2pp).

The sprint's real finding came from the post-hoc leg attribution of O4: **all
of the value is in the defensive down-leg** (throttle offense when the
portfolio's own 26w realized vol is elevated) **and all of the harm is in the
up-leg** (boosting offense in calm — which loaded exposure into the COVID
crash). A down-only "vol throttle" (26w, floor 0.85, no boost, 4-week update)
passes **7 of 8 Phase D gates vs the production pin** (full Sharpe +0.0109,
holdout +0.0681, max DD unchanged, CVaR improved, turnover *reduced*,
bootstrap P=0.757), failing only the rolling-origin win-rate gate (0.500 vs
0.55). Because this configuration was discovered post hoc, it is **not
promotable from this sprint** and is handed to the next sprint as its
pre-registered primary hypothesis.

## 2. What Was Read

Project journey (all 100+ sections), research scoreboard, CLAUDE.md,
Track A production hardening docs, frontier validation governance,
`production_config/allocator/costs/metrics`, the checkpoint wrapper, prior
options-convexity reports (4 iterations), recovery-prediction report, the
2026-05-07 external-research series (bottleneck audit, prioritized backlog,
next sprints), B6/R2 signal validation tables, ml_lab summaries, and the
notebooks' data outputs (data hub, Layer 1 signal library, Layer 2B state
history, Layer 3 portfolio artifacts).

## 3. System Audit (Phase 1)

- **Architecture:** L1 signals → L2 sleeves → L2B causal 5-state regime engine
  (walk-forward, no hindsight labels) → L3 HRP + overlays. Production is a
  **wrapper**: saved GGG final ETF weights + one bounded post-processor at the
  `offense_budget` checkpoint (Phase 1 R2A offense scale α=0.08 + Phase 4
  inverted-leadership fragility cap; stressed_panic forced to 1.0). Costs:
  10 bps per one-way turnover; Friday-close weights applied to next-week
  returns; exact GGG reproduction verified to 2e-16 this sprint.
- **Current winner:** `improved_frontier_phase5_fragility_guard` — full Sharpe
  0.9483 (GGG 0.9362), holdout Sharpe 2.1786, max DD −11.60%, promoted after
  Phase 10A (all 8 gates) + human authorization.
- **Validation stack:** pre-declared 104-week holdout (2024-04-19+), 8 Phase D
  gates, 13-week block bootstrap, rolling-origin windows, PSR/DSR/PBO
  utilities, mandatory realism/leakage audit culture.
- **Known failures (closed branches):** allocator swaps (HRP won), ML
  meta-allocators (Phases N–V, NNN, ml_lab), holdings blends (U–AA), options
  convexity (v1 REJECT, v2 REJECT, recovery RESEARCH-ONLY, v3 REJECT),
  cross-asset lead-lag (Frontier 7A: 0/5 stable pairs), standalone leadership
  alpha (Frontier 4A), macro overlays (V3 Steps 2/2B/2C: no candidate ever
  passed Sharpe and turnover gates simultaneously), latent-factor discovery
  (PPP null), survivorship-free stock breadth (blocked on PIT data).
- **Known strengths to preserve:** state-conditioned deployment discipline,
  the R2A composite, the fragility guard's inverted-leadership veto,
  stressed_panic protection (+16.9% active vs SPY in 2022), the exact-wrapper
  research harness, and the strict promotion governance.
- **Biggest overfit risks:** rank-composite pool sensitivity (Phase 3.2/3.3
  lesson), post-hoc parameter selection, holdout burn from repeated use (the
  2024-04-19 holdout has now been consulted by many sprints — see §12 Risks),
  and tiny-delta promotion pressure.

## 4. Institutional Gap Analysis (Phase 2)

| Area | Status | Assessment |
|---|---|---|
| Alpha signals | Extensively mined | ETF-level breadth/trend/quality exhausted; PIT stock breadth is the known unlock (blocked on data purchase) |
| Regime detection | Strong (L2B + macro V3) | Marginal gains only; Signal E_4wk archived for a future rebuild |
| Vol modeling / vol targeting | **Gap until this sprint** | Never tested at the production-wrapper level; now tested (O4) |
| Option-market information (VIX TS) | **Gap until this sprint** | Rejected as alpha in R2; now tested as gate (O1) — still fails |
| Correlation-structure risk (absorption ratio) | **Gap until this sprint** | Now tested (O3) — clean negative result |
| Canary/breadth cash gating | Partially covered by regime engine | Now tested explicitly (O2) — redundant, confirmed |
| Covariance estimation (Ledoit-Wolf etc.) | Untested | Low priority: HRP uses rank clustering; effect likely small; test later |
| Options/convexity overlays | Closed (4 iterations) | Do not reopen without real option-chain data |
| Tail-risk protection | Adequate via regime engine | Literature (AQR, Israelov) says allocation-based de-risking beats bought protection — consistent with what this project already does |
| Multiple-testing control | Good (DSR/PBO utilities) | Continue reporting config counts per sprint (this sprint: 62 grid + 10 primary/stacked + 13 post-hoc runs) |
| Production monitoring / reproducibility | Strong | Wrapper + verifier pattern is institutional-grade |

## 5. External Research (Phase 3) — Findings and How They Were Used

1. **Volatility-managed portfolios**: [Moreira-Muir critique literature — Cederburg, O'Doherty, Wang, Yan (2020)](https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X) find no systematic out-of-sample Sharpe improvement across 103 strategies ([full paper](https://www.lehigh.edu/~xuy219/research/COWY.pdf)); [DeMiguel et al. (2024)](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13395) give a more nuanced multifactor view. → Informed O4's conservative design (bounded, 4-week update, non-stressed only) and the expectation that the up-leg is the fragile part — which the leg attribution confirmed.
2. **VIX term structure**: [Macrosynergy review](https://macrosynergy.com/research/vix-term-structure-as-a-trading-signal/), [MDPI: VIX futures as timing indicator](https://www.mdpi.com/1911-8074/12/3/113), [eco3min backwardation study](https://eco3min.fr/en/vix-backwardation-contango-volatility-term-structure/) — backwardation flags acute stress but is imprecise; resolution-to-contango is a modest re-risk confirmation. → O1 design. Portfolio result: no incremental value on top of L2B, consistent with the R2 alpha rejection.
3. **DAA canary breadth momentum**: [Keller & Keuning (2018)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862), [Allocate Smartly review](https://allocatesmartly.com/two-new-strategies-added-defensive-asset-allocation-and-accelerating-dual-momentum/). → O2 design (EEM + IEF as AGG proxy). Portfolio result: redundant with the regime engine.
4. **Absorption ratio / turbulence**: [Kritzman, Li, Page, Rigobon (2010)](https://www.ssrn.com/abstract=1633027), [Portfolio Optimizer blog replication](https://portfoliooptimizer.io/blog/the-absorption-ratio-measuring-financial-risk/). → O3 design. Portfolio result: negative — the portfolio's negative SPY beta means correlation-spike de-risking removes exposure it doesn't have.
5. **Momentum crashes**: [Daniel & Moskowitz (2016)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227) — crashes occur in panic states during rebounds. → Considered and *not* implemented: the L2B engine's stressed_panic/recovery_fragile states already encode this structure; a residual-momentum crash filter is queued in the backlog.
6. **Tail hedging vs allocation**: [Israelov "Pathetic Protection" (2019)](https://www.researchgate.net/publication/330637224_Pathetic_Protection_The_Elusive_Benefits_of_Protective_Puts), [AQR put-vs-trend white paper](https://images.aqr.com/-/media/AQR/Documents/Insights/White-Papers/AQR-Tail-Risk-Hedging-Contrasting-Put-and-Trend-Strategies.pdf). → Confirms the project's existing choice (allocation-based de-risking) and supports keeping options convexity closed absent real chain data.
7. **Credit lead-lag**: [eco3min HY spread lead-lag dataset](https://eco3min.fr/en/us-hy-credit-spread-leading-indicator-dataset/) — credit leads credit-driven bears but not rate-shock bears (2022). → Not implemented: `r2_credit_spread` was already rejected (stressed_panic damage) and credit confirmation already feeds R2A.

## 6. Candidate Backlog (Phase 5, ranked; top 4 were implemented)

1. **O4 vol-managed offense** (implemented) — literature-backed, wrapper-native, low turnover. → RESEARCH-ONLY; down-leg promising.
2. **O1 VIX TS stress/resolution gate** (implemented) — rare-event, low-turnover; complements price-based regime engine with option-market information. → DROP.
3. **O2 DAA canary cash gate** (implemented) — cheap, proven in TAA literature. → RESEARCH-ONLY (redundant).
4. **O3 absorption-ratio throttle** (implemented) — genuinely orthogonal information (correlation structure). → DROP.
5. Residual-momentum crash filter conditioned on L2B panic-rebound weeks (not implemented — queued).
6. Ledoit-Wolf shrinkage inside sleeve HRP (not implemented — likely small).
7. Regime-conditioned short-horizon reversal sleeve (not implemented — `short_horizon_reversal` was the best family in the recovery-prediction sprint; needs a sleeve-level design that respects turnover gates).
8. Moonshots considered and rejected for this sprint: options overlays without chain data (closed branch), HMM regime layer (hindsight-label risk), RL/deep learning (governance defers until simpler layers saturate).

## 7. What Was Implemented (Phase 7)

New research namespace `scripts/frontier2_overlays/` (nothing in production paths touched):

- [overlay_signals.py](scripts/frontier2_overlays/overlay_signals.py) — reusable causal signal builders (VIX backwardation events, Keller 13612W canary count with hysteresis, absorption-ratio shift, realized-vol scalar). All shifted one week beyond the Friday-close convention.
- [run_frontier2_overlay_experiments.py](scripts/frontier2_overlays/run_frontier2_overlay_experiments.py) — full runner: exact-GGG reproduction check, primary configs, stacked + standalone variants, Phase D gates vs pin and vs GGG, 2000-iteration seeded block bootstrap, rolling-origin windows, stress windows, sensitivity grids (reporting-only), machine-readable outputs + manifest.
- [verify_frontier2_overlay_outputs.py](scripts/frontier2_overlays/verify_frontier2_overlay_outputs.py) — verifier: file integrity, exact reproduction, stressed_panic neutrality, truncation-invariance (no-lookahead) checks, net=gross−cost accounting, manifest consistency. **All checks pass.**

Outputs: `data/research/frontier2_overlays/` (metrics, gates, bootstrap,
rolling-origin, sensitivity, multipliers, per-variant paths, manifest,
post-hoc attribution files).

**How to run:**

```bash
cd scripts/frontier2_overlays
python3 run_frontier2_overlay_experiments.py
python3 verify_frontier2_overlay_outputs.py
```

## 8. Metrics (full period 2005–2026 active history, net of 10 bps/one-way turnover)

| Variant | CAGR | Sharpe | MaxDD | CVaR5 | Calmar | Vol | Avg wk TO |
|---|---|---|---|---|---|---|---|
| GGG baseline | 7.14% | 0.9362 | −11.77% | −2.54% | 0.606 | 7.62% | 0.0618 |
| **Production pin (current winner)** | 7.13% | 0.9483 | −11.60% | −2.49% | 0.615 | 7.52% | 0.0674 |
| Rollback pin | 6.89% | 0.8844 | −13.98% | −2.62% | 0.493 | 7.79% | 0.0562 |
| Official shadow | 6.86% | 0.8836 | −13.67% | −2.61% | 0.502 | 7.76% | 0.0566 |
| O1 VIX gate (stacked) | 7.12% | 0.9469 | −11.60% | −2.49% | 0.614 | 7.52% | 0.0676 |
| O2 canary (stacked) | 7.17% | 0.9491 | −11.60% | −2.51% | 0.618 | 7.55% | 0.0684 |
| O3 absorption (stacked) | 7.07% | 0.9466 | −11.60% | −2.47% | 0.609 | 7.47% | 0.0674 |
| O4 vol-managed (stacked) | 6.96% | 0.9542 | −11.93% | −2.41% | 0.584 | 7.29% | 0.0684 |
| Post-hoc vol throttle 26w (diagnostic) | 6.91% | 0.9591 | −11.61% | −2.37% | 0.596 | 7.21% | 0.0665 |

Holdout (104 weeks from 2024-04-19): production pin Sharpe 2.1786; O4 stacked
2.3066 (+0.128); post-hoc throttle 2.2467 (+0.068). Stress windows: O4 worsens
COVID-2020 (−11.9% vs −9.9% annualized) via its up-leg; the down-only throttle
is neutral-to-better in all three stress windows (GFC ~0, COVID +0.96pp,
2022 +0.0pp). Recovery behavior: O4 modestly hurts recovery_fragile capture
(Sharpe 1.157→1.093) — vol throttling slows re-risking, a real cost given the
project's re-risking priority; this must be watched in the next sprint.

## 9. What Passed / Failed / Is Promising

- **Failed cleanly:** O1 (VIX TS adds nothing on top of L2B), O3 (absorption
  ratio actively hurts a negative-beta portfolio). Both are recorded as
  useful negative results — do not repeat without a materially different design.
- **Trivial:** O2 canary — the regime engine already embodies this information.
- **Promising but not promotable:** the O4 family. Full-Sharpe delta positive
  in 8/8 predeclared grid configs and 9/9 post-hoc throttle configs, holdout
  positive everywhere, turnover *negative* (the throttle trades less), max DD
  and CVaR unharmed in down-only form. The single failing gate for the
  down-only variant is rolling-origin win rate (0.500 vs 0.55): the benefit is
  episodic (high-vol regimes), and in calm windows the throttle slightly lags.
  It buys Sharpe/tail quality with ~0.2pp of CAGR — a defensible trade for the
  conservative track, but it must clear gates as a *pre-registered* primary.

## 10. What Deserves Promotion

**Nothing in this sprint.** The only near-miss configuration (down-only
26-week vol throttle) was identified post hoc and therefore cannot be
promoted from the same data it was discovered on without violating the
project's own forking-paths discipline.

## 11. Multiple-Testing Accounting

This sprint evaluated 4 predeclared primaries, 62 sensitivity configs
(reporting-only), 4 post-hoc attribution runs, and 9 post-hoc throttle
sensitivity configs (~79 total portfolio evaluations). The headline verdicts
use only the predeclared primaries. The post-hoc throttle's nominal 7/8 gate
pass should be discounted accordingly — that is precisely why it is
research-only pending re-validation.

## 12. Risks and Caveats

- **Holdout burn:** the official 104-week holdout has now been consulted by
  many sprints; its evidential value is degrading. The strongest antidote
  available without new data is the rolling-origin + bootstrap combination,
  which this sprint used. When the holdout window rolls forward (it moves with
  new data), the throttle hypothesis should be re-checked on unconsumed weeks.
- **Vol-throttle regime dependence:** its edge concentrates in high-vol
  episodes; a long calm regime would make it a small drag (~0.2pp CAGR).
- **Recovery drag:** the throttle can slow re-risking; the next sprint should
  test a recovery-state exemption (e.g., no throttle in recovery_confirmed)
  as a *predeclared* secondary, not a post-hoc rescue.
- The Cederburg et al. warning stands: vol-managed edges often vanish in real
  time. The down-only variant is closer to Barroso-Santa-Clara risk-scaling
  than to full Moreira-Muir timing, which is the more robust corner of that
  literature, but skepticism is still warranted.

## 13. Recommended Next Prompt

> Pre-registered validation of the down-only volatility throttle. Primary
> (locked before running): 26-week realized vol of the production pin's own
> net returns, expanding-median target, multiplier = clip(target/realized,
> 0.85, 1.00), 4-week update, stressed_panic forced to 1.0, applied at the
> offense_budget checkpoint stacked on `improved_frontier_phase5_fragility_guard`.
> Secondaries (also locked): recovery_confirmed exemption on/off; clip floor
> 0.80/0.90. Gates: the standard Phase D 8 vs the production pin, plus 2×-cost
> stress. Report rolling-origin win rate by regime (the known weak gate) and
> the recovery_fragile capture delta. If the rolling gate still fails, classify
> RESEARCH-ONLY permanently and stop this branch — do not tune further.
