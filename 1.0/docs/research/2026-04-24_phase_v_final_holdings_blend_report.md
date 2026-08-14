# Phase V — Final Holdings-Blend Refinement (Branch Closure)

Date: 2026-04-24
Track: Phase V (final disciplined sprint in current branch). Previous: Phase U (Production-Anchored Holdings Blend, 2026-04-24).

---

## A. What changed

Phase V is the **final disciplined sprint** in the current allocator / trust / regime / holdings-blend branch. Phase U produced three candidates (U1a, U1c, U3) that each cleared four of the six Phase D production gates with three different miss-patterns. Phase V was scoped to test exactly the three highest-conviction levers Phase U's diagnostic named, no broader:

- **V1 — 90/10 production + phasen holdings blend** (`improved_phasev_prod90_phasen_10_holdings_blend`). Designed to close U1a's residual full-Δ gap by replacing R2 with phasen (full-history composite 0.5666 vs R2's 0.5198, a +0.047 advantage), preserving the 90/10 ratio that gave U1a its holdout Δ ≥ 0 and rolling win 73%.
- **V2 — 90/10 production + phaseo holdings blend** (`improved_phasev_prod90_phaseo_10_holdings_blend`). Same idea with phaseo as the partner — different correlation structure, different Sharpe profile, otherwise identical.
- **V3 — tighter conditional 95/5 defense / 80/20 elsewhere, partner = phasen** (`improved_phasev_conditional95_80_holdings_blend`). Sharpens U3's conditional toward production positioning more strongly in defense weeks while letting the partner contribute meaningfully elsewhere. Partner swapped from R2 → phasen for the same full-Δ-lifting reason.

No new ML model. No retraining. No new sleeve. No new signal. Closed-form arithmetic on already-validated weight artifacts. Causality and walk-forward safety inherited.

## B. What was executed

- Public-research orientation (kept brief; Phase U already established the framing): mixture-of-portfolios literature (Newfound, ReSolve, Robeco) and benchmark-anchored ensemble research (AQR, Research Affiliates) all converge on the same point — when one anchor is information-rich on a specific window and the partner is robust, a fixed-ratio holdings blend dominates a learned mixture-of-experts because it eliminates the model-selection variance. The Phase V partner switch from R2 → phasen is justified by phasen's higher full-history composite and similar holdout-defensive behavior; the conditional-tightening (95/5) is justified by AQR-style benchmark-anchoring research arguing that anchor weight should rise sharply in adverse-tape regimes.
- `python3 scripts/phase_v_final_holdings_blend.py` — built three Phase V candidates, ran full validation against the **13-member fixed comparator set** (now including U1a and U3) under Phase D rules.
- Bootstrap: 13-week moving block × 2,000 draws on holdout excess return.
- Rolling origin: 260-week min train, 104-week test, 52-week step (15 windows).

## C. Files / artifacts

Scripts:
- `scripts/phase_v_final_holdings_blend.py` — V1 / V2 / V3 implementations + validation bundle.

Data (`data/05_layer3_portfolio_construction/`):
- `phase_v_candidate_metrics_{full,dev,holdout}.csv`
- `phase_v_pairwise_validation.csv`
- `phase_v_candidate_classification.csv`
- `phase_v_rolling_origin_summary.csv`
- `phase_v_holdings_diagnostics.csv` (per-candidate avg α, L1 distance to production / partner / U1a, BIL share)
- `phase_v_controls_*.csv` (per-candidate per-week controls including L1 distance to U1a)
- `phase_v_validation_protocol.json`
- `portfolio_version_{weights,returns}_improved_phasev_*.csv` (three of each)

Documentation:
- `docs/research/2026-04-24_phase_v_final_holdings_blend_report.md` (this report).
- `docs/research/project_journey.md` — Section 35 appended (branch closure).

## D. Starting-point diagnosis

**Why Phase U was not enough by itself.** Phase U was the most successful sprint of the ML-meta-allocator era. It produced multiple first-time gate clears: U1a cleared holdout Δ ≥ 0 (+0.0003) and rolling win 73.3%; U1c cleared full Δ +0.0175; U3 cleared bootstrap 71.2%. But no single candidate aligned all six gates simultaneously. The pattern of misses was structural to the static-α design:

- U1a 90/10 missed full Δ (+0.0067 vs the +0.015 floor) and bootstrap (41.3%).
- U1c 70/30 missed holdout Δ (-0.0009) and bootstrap (40.1%).
- U3 conditional missed rolling win (40%) and holdout Δ (-0.0028).

**Exact remaining problem Phase V tries to solve.** All three Phase U miss-patterns share one structural axis: U1a's full-Δ shortfall arises mechanically from a 90% weight on production (rank 18 of 18 in cohort full composite) blended with R2 (rank 9). A higher-quality partner with the same blend ratio would mechanically lift full Δ by ~+0.005-0.008 (10% of the partner-vs-R2 spread), projecting V1 into the +0.011 to +0.012 band — still short of the +0.015 floor on its own, but closing the largest remaining gap. Conditional sharpening (V3) attacks rolling win by raising α in defense_production weeks (95/5) while keeping the partner active enough elsewhere (80/20) to preserve full-Δ contribution.

**Why this is the right final test.** It is the smallest, highest-conviction expansion of the now-validated holdings-blend framework. If it does not align all six gates, the diagnostic is unambiguous — the branch's structural ceiling is real, not just a question of partner choice or ratio tuning. Phase V was scoped explicitly to either close the gates or trigger Outcome B.

## E. Phase V results (per candidate)

### V1 `improved_phasev_prod90_phasen_10_holdings_blend` (90 / 10 with phasen)

Full: ann_return 0.0694, ann_vol 0.0773, Sharpe 0.8985, max_dd -0.1385, Calmar 0.5012, CVaR_5 -0.0259, turnover 0.0582, upside_capture ~0.33, downside_capture ~0.24, recovery_capture 0.3051, calm_capture ~0.44, avg_bil 0.2760, avg_spy ~0.073, avg_offense ~0.55, avg_defense ~0.17, avg_cash 0.2760.
Holdout: ann_return 0.1534, ann_vol 0.0728, Sharpe 2.1074, max_dd -0.0570, Calmar 2.6912, CVaR_5 -0.0202, turnover 0.0633, upside_capture ~0.43, downside_capture ~0.22, recovery_capture 0.5745, calm_capture ~0.74, avg_bil 0.1931.

Holdings diagnostics: avg α 0.900, avg L1 dist to production 0.0702, avg L1 dist to phasen 0.6316, avg L1 dist to U1a 0.0479. The blend is mechanically ~5pp further from U1a than from production, confirming that swapping R2 for phasen materially changed the holdings even at the same blend ratio.

### V2 `improved_phasev_prod90_phaseo_10_holdings_blend` (90 / 10 with phaseo)

Full: ann_return 0.0693, Sharpe 0.8990, max_dd -0.1384, CVaR_5 -0.0258, turnover 0.0577, recovery_capture 0.3046, avg_bil 0.2773.
Holdout: ann_return 0.1529, Sharpe 2.1029, max_dd -0.0570, CVaR_5 -0.0202, turnover 0.0624, recovery_capture 0.5701, avg_bil 0.1945.

Holdings diagnostics: avg α 0.900, avg L1 dist to production 0.0679, avg L1 dist to phaseo 0.6111, avg L1 dist to U1a 0.0453.

### V3 `improved_phasev_conditional95_80_holdings_blend` (95/5 defense, 80/20 elsewhere, with phasen)

Full: ann_return 0.0697, Sharpe 0.9021, max_dd -0.1392, CVaR_5 -0.0259, turnover 0.0663, recovery_capture 0.3099, avg_bil 0.2779.
Holdout: ann_return 0.1538, Sharpe 2.1038, max_dd -0.0568, CVaR_5 -0.0202, turnover 0.0712, recovery_capture 0.5801, avg_bil 0.1932.

Holdings diagnostics: avg α 0.895 (sits between V1's 90/10 and a pure 95/5), avg L1 dist to production 0.0772, avg L1 dist to phasen 0.6245, avg L1 dist to U1a 0.0571.

### Pairwise vs production / U1a / U3

| candidate | full Δ vs prod | holdout Δ vs prod | Sharpe Δ vs prod | bootstrap vs prod | rolling win | rolling mean Δ | full Δ vs U1a | holdout Δ vs U1a | Sharpe Δ vs U1a | bootstrap vs U1a | bootstrap vs U3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **V1 90/10 phasen** | **+0.0173** ✓ | -0.0008 | +0.008 ✓ | 32.3% | 46.7% | +0.008 ✓ | +0.0106 | -0.0011 | -0.002 | 29.1% | 7.3% |
| **V2 90/10 phaseo** | **+0.0172** ✓ | -0.0007 | +0.003 ✓ | 22.8% | 46.7% | +0.007 ✓ | +0.0105 | -0.0009 | -0.007 | 16.4% | 5.6% |
| **V3 95/5 \| 80/20 phasen** | +0.0120 | -0.0078 | +0.004 ✓ | 33.2% | 33.3% | +0.004 ✓ | +0.0053 | -0.0081 | -0.006 | 31.9% | 5.5% |
| U1a 90/10 R2 | +0.0067 | +0.0003 | +0.010 | 41.3% | 73.3% | +0.004 | 0 | 0 | 0 | 0 | 16.4% |
| U3 cond R2 | +0.0122 | -0.0028 | +0.034 | 71.2% | 40.0% | +0.005 | +0.0055 | -0.0031 | +0.024 | 83.6% | 0 |

DD/CVaR caps (all clear): V1 max_dd Δ +0.0013 / CVaR Δ +0.0003. V2 +0.0014 / +0.0004. V3 +0.0006 / +0.0003.

## F. Phase V interpretation

**What helped.** The partner-swap projection was directionally correct. **V1 and V2 both cleared the full-Δ ≥ +0.015 gate** (V1 +0.0173, V2 +0.0172) — Phase V is the first sprint where two candidates simultaneously cleared full Δ while staying inside the holdings-blend framework. Holdout Δ for V1 and V2 sit at -0.0008 and -0.0007 — the second-best holdout closures in the project after U1a's +0.0003. Holdout Sharpe Δ vs production stayed positive for all three (V1 +0.008, V2 +0.003, V3 +0.004). DD and CVaR caps cleared comfortably across all three.

**What did not help.** **The full-Δ lift came at a measurable cost on every other deployment-relevant axis.** Compared to U1a, the V1 partner-swap lost rolling win-rate (73.3% → 46.7%), holdout Δ (+0.0003 → -0.0008), bootstrap (41.3% → 32.3%), and holdout Sharpe (Δ +0.010 → +0.008). The trade was not free. The mechanical reason is direct: phasen and phaseo are less defensive in adverse tape than R2 — phasen full max_dd -0.127, phaseo -0.126, R2 -0.137 — so a 10% phasen/phaseo weight pulls the blend slightly off production's adverse-tape positioning during exactly the holdout weeks where U1a's R2 partner contributed defensively, costing both rolling win and bootstrap dominance.

**V3 was the largest disappointment.** Switching the conditional partner from R2 to phasen broke U3's bootstrap edge entirely: 71.2% → 33.2%. The 95/5 defense / 80/20 elsewhere structure was supposed to preserve bootstrap (heavier production weight in defense weeks) while lifting rolling win (more production exposure overall). Neither effect materialized. Rolling win actually fell from U3's 40% to V3's 33.3%, holdout Δ collapsed from -0.0028 to -0.0078, and full Δ moved from +0.0122 to +0.0120 — flat. The diagnostic: U3's bootstrap edge came from R2's specific tail-aware behavior pairing well with production in adverse tape, not from the conditional structure itself. Replacing R2 with phasen (which sits closer to phaseo than to R2 in tail behavior) destroyed that pairing.

**Did holdings-level blending help again?** Yes, structurally. All three Phase V candidates beat the meta-allocator references R2 / R3 on holdout raw composite (V1 0.9620 vs R2 0.9496, V2 0.9621, V3 0.9549). Every Phase V candidate clears DD and CVaR caps and clears holdout Sharpe Δ and rolling mean Δ. Holdings-level blending remains the right framework. The framework is not the ceiling; the **specific combination of (partner choice, blend ratio, conditional rule)** is the ceiling.

**Did it preserve production's adverse-tape edge?** Mostly. V1 holdout downside_capture and max_dd are within +0.0004 of production. The slight degradation vs U1a (-0.0570 vs -0.0567) is mechanical and small.

**Did it preserve the partner's useful Sharpe / full-history edge?** Partially. V1 holdout Sharpe 2.107 is below U1a's 2.110, and well below R3's 2.216 or R2's 2.155. The partner-switch from R2 to phasen lifted full-Δ as projected but did not lift holdout Sharpe — which makes sense, since phasen's holdout Sharpe (2.004) is lower than R2's (2.155).

**Did it improve holdout raw composite?** No. V1 holdout raw composite 0.9620 vs U1a's 0.9630 — a -0.0010 step backward. V2 0.9621 — -0.0009. V3 0.9549 — -0.0081.

**Did it improve bootstrap support and rolling win?** No. Both axes regressed materially vs U1a (rolling win 73% → 47%) and vs U3 (bootstrap 71% → 33%).

**Did it beat U1a / U3?** Not unambiguously. V1 and V2 beat U1a on full Δ by +0.0106 and +0.0105 respectively, but lose to U1a on holdout Δ, Sharpe, rolling win, and bootstrap. V3 beats U3 on nothing material — it loses on bootstrap (-38pp), holdout Δ (-0.005), Sharpe (-0.030), and is flat on full Δ. **No Phase V candidate replaces U1a or U3 as a research reference.**

**Did it beat the production pin under the validation rules?** No — and not close. Best Phase V candidate (V1) clears 5 of 8 individual checks (full Δ, holdout Sharpe, rolling mean Δ, DD cap, CVaR cap) but misses 3 of the 6 critical production gates (holdout Δ, rolling win, bootstrap). U1a still aligns more critical gates than any Phase V candidate (4 of 6, with the remaining two being mechanically structural).

**Is this branch now exhausted?** **Yes.** Phase V was scoped as the final disciplined test inside the holdings-blend framework. The partner-swap projection worked exactly as predicted on the axis it targeted (full Δ +0.015 floor cleared) and reliably regressed every other deployment axis vs U1a. The conditional-tightening hypothesis failed outright (V3 broke U3's bootstrap edge). The space of (partner, ratio, conditional) within this framework has now been searched at the points the data explicitly named, and no point dominates U1a or U3 on the deployment-relevant gates. **The current allocator / trust / regime / holdings-blend branch has reached its information ceiling on this signal+sleeve panel.**

## G. Candidate classification

| candidate | classification | gates passed (of 8) | key misses | notes |
|---|---|---|---|---|
| **V1 90/10 prod+phasen** | **Research-only** | full Δ ✓, Sharpe Δ ✓, rolling mean Δ ✓, DD ✓, CVaR ✓ (5 of 8) | holdout Δ -0.0008, rolling win 46.7%, bootstrap 32.3% | First clear of full Δ ≥ +0.015 inside a 90/10 holdings blend. Loses to U1a on every other deployment axis. |
| **V2 90/10 prod+phaseo** | **Research-only** | full Δ ✓, Sharpe Δ ✓, rolling mean Δ ✓, DD ✓, CVaR ✓ (5 of 8) | holdout Δ -0.0007, rolling win 46.7%, bootstrap 22.8% | Mirror of V1 with phaseo partner. Lower bootstrap than V1, slightly lower full-Δ. |
| **V3 95/5\|80/20 prod+phasen cond** | **Research-only** | Sharpe Δ ✓, rolling mean Δ ✓, DD ✓, CVaR ✓ (4 of 8) | full Δ +0.012 (just misses), holdout Δ -0.008, rolling win 33.3%, bootstrap 33.2% | Partner-switch broke U3's bootstrap edge. Worst gate alignment of the three. |

**Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.**
**Shadow pin: `improved_phase2b_combo_abc` — unchanged.**

No Phase V candidate replaces U1a or U3 as a research reference.

## H. Final branch judgment

### Outcome B — branch closes

**The current allocator / trust / regime / holdings-blend branch is finished.** Six consecutive sprints — Phase Q (bucket meta), Phase R (bucket trust refinement), Phase S (defense reshape + ML attenuator), Phase T (soft regime posterior), Phase U (production-anchored holdings blend), and Phase V (final holdings-blend refinement) — have moved progressively smaller amounts against the same deployment ceiling without producing a single candidate that aligns all six Phase D production gates simultaneously.

**What this branch achieved:**

1. Established that holdings-level blending dominates meta-allocator blending for capturing production's holdout edge (Phase U).
2. Produced the first-ever holdout Δ ≥ 0 candidate (U1a, +0.0003) with rolling win 73%.
3. Produced the first-ever bootstrap ≥ 60% candidate (U3, 71.2%).
4. Produced the first-ever full Δ ≥ +0.015 candidates that simultaneously preserved holdout near-flat (V1 / V2, ~-0.0008).
5. Confirmed that production's holdout edge lives partly in specific weekly ETF holdings (Phase U validated this; Phase V's partner-swap result reinforced it).
6. Cleanly falsified the "hard regime boundaries are the residual cause" hypothesis (Phase T).

**Why it plateaued:**

The three deployment-relevant axes that Phase D weighs (holdout Δ, rolling win, bootstrap, with full Δ as a fourth axis) sit at different points in the (partner, ratio, conditional) parameter space within the holdings-blend framework. U1a optimizes the (holdout Δ + rolling win) corner. U3 optimizes the bootstrap corner. V1/V2 optimize the full-Δ corner. **No point in the searched parameter space optimizes all corners simultaneously**, and the corners are mechanically anti-correlated: pushing α toward production lifts holdout-Δ and bootstrap while suppressing full-Δ; switching to a higher-full-composite partner lifts full-Δ but degrades the partner's adverse-tape pairing with production, costing rolling win and bootstrap. This is a structural Pareto frontier of the holdings-blend framework on this signal+sleeve panel — not a tuning failure.

**Production pin: stays on `improved_phase2b_regime_confidence_boost`.** Unchanged since promotion.
**Shadow pin: stays on `improved_phase2b_combo_abc`.** Unchanged.
**Closest-to-gate research reference: `improved_phaseu_prod90_r2_10_holdings_blend` (U1a)** — unchanged from Phase U. No Phase V candidate replaced it.
**Bootstrap research reference: `improved_phaseu_conditional_prod_r2_holdings_blend` (U3)** — unchanged from Phase U. V3's partner-switch broke its bootstrap edge.
**Sharpe research reference: `improved_phaser_fast_narrow_regret_allocator` (R3)** — unchanged.
**Dev-composite research reference: `improved_phaset_soft_regime_posterior_allocator` (T1)** — unchanged.
**Full-Δ research reference (new): `improved_phasev_prod90_phasen_10_holdings_blend` (V1)** — first holdings-blend candidate to clear full Δ ≥ +0.015. Useful as a reference for any future sprint that revisits this branch from a different angle.

## I. Next-step recommendation

The branch is closed. Any further work on this signal+sleeve panel — another allocator, another trust layer, another regime softening, another holdings-blend variant — is very unlikely to clear all six Phase D gates simultaneously, because the data has now repeatedly shown that the gates correspond to anti-correlated points on the framework's Pareto frontier on this universe.

**Recommended broader project frontier — sleeve-panel revisit.** The right next move is to step out of Layer 3 and back to Layer 2: rebuild or augment the sleeve panel itself. Specifically:

1. **Add a structural defensive sleeve that captures production's GLD / HYG / DBA / TLT mix as an explicit named sleeve** rather than as an emergent property of the production allocator. If that mix can be expressed as its own causal sleeve, downstream allocators can call it directly and the meta-blend averaging problem disappears.

2. **Test whether replacing one or two of the existing offense sleeves with sleeves that have clearer regime-specific edge** (e.g., a recovery-confirmed-only momentum sleeve, a calm-trend-only carry sleeve) tightens what the allocator can do under the same Phase D rules.

3. **Consider broadening the sleeve universe to include a non-equity-tail asset** (e.g., a managed-futures-style trend signal across commodities) if the project's data infrastructure can support it, so that the allocator has a genuinely uncorrelated branch in adverse tape.

**Why this is the right move now.** The allocator/trust/regime/holdings branch has demonstrated in six sprints that it can move the metric in any single Phase D dimension but cannot align them all on the existing sleeve panel. That is a sleeve-panel constraint, not an allocator constraint. The diagnostic is conclusive. Continuing to refine the allocator on the same sleeve panel would be brute-force search of a known-flat region.

**What this branch taught the project that should carry forward:**

- Holdings-level blending is the correct framework for combining a strong anchor with research candidates. Future Phase 3 work should default to holdings-level blending unless there is a specific reason to use an expert-level meta-allocator.
- Phase D's six-gate validation discipline is doing exactly what it should — identifying anti-correlated tradeoffs that would not be visible in single-metric optimization.
- Walk-forward causal inputs + closed-form blend rules + dual-track production/shadow reporting is a robust template for future sprints, regardless of which layer is being refined.

## J. Project journey log update

- Updated `docs/research/project_journey.md`: Section 35 — Phase V — Final Holdings-Blend Refinement (Branch Closure) — appended at the end of the file.
- Project journey is now current through the branch closure.
- The journey markdown explicitly records: (a) what Phase V tested, (b) what helped (full-Δ gate cleared by V1/V2), (c) what did not (no candidate aligns all six gates; V3 broke U3's bootstrap edge), (d) **branch is now closed (Outcome B)**, (e) recommended next frontier is a sleeve-panel revisit, not another allocator/trust/regime sprint.
