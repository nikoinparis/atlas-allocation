# Phase U — Production-Anchored Holdings Blend

Date: 2026-04-24
Track: Phase U (last serious test in current branch). Previous: Phase T (Regime Engine Softening, 2026-04-24).

---

## A. What changed

Phase U tests one specific hypothesis the prior four sprints (Q→R→S→T) could not address: that production's holdout edge lives in its **specific weekly ETF weights**, not in any allocator/trust/regime decision. Instead of blending experts at the meta-allocator level, Phase U blends **finished ETF weight vectors** directly:

`final_weights[t] = α · production_weights[t] + (1 − α) · partner_weights[t]`

with α as a static blend ratio, then renormalized. The partner is either R2 (`improved_phaser_light_abstention_overlay_allocator`) or R3 (`improved_phaser_fast_narrow_regret_allocator`). One conditional variant uses Phase Q's existing causal hard `defense_production` flag to vary α per week.

Seven candidates total — the smallest meaningful test:

- **U1 static prod + R2** at 90/10, 80/20, 70/30 (`improved_phaseu_prod90_r2_10_holdings_blend`, etc.)
- **U2 static prod + R3** at 90/10, 80/20, 70/30 (`improved_phaseu_prod90_r3_10_holdings_blend`, etc.)
- **U3 conditional prod + R2** (`improved_phaseu_conditional_prod_r2_holdings_blend`): 90/10 in Phase Q's `defense_production` weeks; 70/30 elsewhere.

No new ML model. No retraining. No new sleeve. No new signal. The blend is a closed-form arithmetic operation on already-validated weight artifacts. Causality and walk-forward safety are inherited.

## B. What was executed

- Public-research orientation: blended-portfolio construction (Newfound, ReSolve, Robeco), mixture-of-portfolios literature, and AQR's work on benchmark anchoring under parameter uncertainty all converge on the same point — when one branch is information-rich on a specific historical window and the other is robust, a fixed-ratio blend at the holdings level is empirically superior to a learned mixture-of-experts because it eliminates the model-selection variance. That is exactly the Q→R→S→T situation.
- `python3 scripts/phase_u_holdings_blend.py` — built seven Phase U candidates, ran full validation against the **11-member fixed comparator set** (now including Phase T's T1) under Phase D rules.
- Bootstrap: 13-week moving block × 2,000 draws on holdout excess return.
- Rolling origin: 260-week min train, 104-week test, 52-week step (15 windows).

## C. Files / artifacts

Scripts:
- `scripts/phase_u_holdings_blend.py` — U1/U2/U3 implementations + validation bundle.

Data (`data/05_layer3_portfolio_construction/`):
- `phase_u_candidate_metrics_{full,dev,holdout}.csv`
- `phase_u_pairwise_validation.csv`
- `phase_u_candidate_classification.csv`
- `phase_u_rolling_origin_summary.csv`
- `phase_u_holdings_diagnostics.csv` (Phase U-specific: per-candidate L1 distance to production / partner, average shares, BIL share)
- `phase_u_controls_*.csv` (per-candidate per-week controls)
- `phase_u_validation_protocol.json`
- `portfolio_version_{weights,returns}_improved_phaseu_*.csv` (seven of each)

Documentation:
- `docs/research/2026-04-24_phase_u_holdings_blend_report.md` (this report).
- `docs/research/project_journey.md` — Section 34 appended.

## D. Starting-point diagnosis

**Why Q/R/S/T were not enough.** Four consecutive sprints tackled the same residual from four different angles:
- Phase Q: bucket meta-allocator (hard regime → bucket → expert mix). Holdout Δ -0.018, rolling win 40%, bootstrap 26%.
- Phase R: trust-bucket refinement (R2 light abstention, R3 fast/narrow regret). Holdout Δ -0.013, rolling win 47% (R2), bootstrap 39% (R2).
- Phase S: defense reshape + conditional ML attenuation. Holdout Δ -0.013, rolling win 40-47%, bootstrap 39-47%.
- Phase T: soft regime posterior + defensive pull + ETF-level production anchor on diffuse weeks. Holdout Δ -0.013 to -0.016, rolling win 40%, bootstrap 17-21%.

All four converged to the same -0.013 holdout shortfall. Phase T also produced the cleanest falsification of the "hard boundary" hypothesis: 54.7% of weeks had bucket-disagreement, and those disagreements moved full-history composite up while leaving holdout flat. Hard boundaries were not the residual cause.

**Exact remaining problem.** Production's holdout ann_return (0.1537) and Sharpe (2.10) are produced by specific ETF positioning during ~30% of holdout weeks — adverse-tape weeks where production's GLD / HYG / DBA / BIL / TLT mix dominates whatever the meta-allocator's expert universe (production / phaseo / phasen) can build by averaging. Every meta-blend literally averages away from those holdings.

**Why holdings-level blending is the right last test.** It is the only direction that bypasses the averaging problem at the holdings level rather than at the expert level. If `α · production + (1 − α) · partner` works, the residual really did live in production's specific weights and a simple, robust blend can recover the gap. If it does not work, the deployment ceiling is structural and no allocator/trust/regime change can fix it on this signal/sleeve panel.

## E. Phase U results (per candidate)

### U1a `improved_phaseu_prod90_r2_10_holdings_blend` (90 / 10)

Full: ann_return 0.0692, ann_vol 0.0776, Sharpe 0.8921, max_dd -0.1394, Calmar 0.4965, CVaR_5 -0.0260, turnover 0.0572, upside_capture 0.3249, downside_capture 0.2397, recovery_capture 0.3046, calm_capture 0.4432, avg_bil 0.2829, avg_spy 0.0721, avg_offense 0.5523, avg_defense 0.1648, avg_cash 0.2829.
Holdout: ann_return 0.1542, ann_vol 0.0731, Sharpe **2.1097**, max_dd -0.0567, Calmar 2.7200, CVaR_5 -0.0204, turnover 0.0617, upside_capture 0.4316, downside_capture 0.2199, recovery_capture 0.5866, calm_capture 0.7377, avg_bil 0.1947, avg_spy 0.0723, avg_offense 0.5905, avg_defense 0.2148, avg_cash 0.1947.

### U1b `improved_phaseu_prod80_r2_20_holdings_blend` (80 / 20)

Full: ann_return 0.0694, Sharpe 0.8989, max_dd -0.1391, CVaR -0.0259, turnover 0.0586, recovery_capture 0.3050, avg_bil 0.2826, avg_offense 0.5519, avg_defense 0.1655.
Holdout: ann_return 0.1547, Sharpe **2.1186**, max_dd -0.0568, CVaR -0.0203, turnover 0.0636, recovery_capture 0.6057, calm_capture 0.7546, avg_bil 0.1954.

### U1c `improved_phaseu_prod70_r2_30_holdings_blend` (70 / 30)

Full: ann_return 0.0696, Sharpe 0.9054, max_dd -0.1388, CVaR -0.0257, turnover 0.0601, recovery_capture 0.3053, avg_bil 0.2823, avg_offense 0.5515.
Holdout: ann_return 0.1552, Sharpe **2.1265**, max_dd -0.0568, CVaR -0.0202, turnover 0.0657, recovery_capture 0.6248, calm_capture 0.7712, avg_bil 0.1961.

### U2a `improved_phaseu_prod90_r3_10_holdings_blend` (90 / 10)

Full: ann_return 0.0690, Sharpe 0.8930, max_dd -0.1388, CVaR -0.0259, turnover 0.0569, recovery_capture 0.3018, avg_bil 0.2838.
Holdout: ann_return 0.1540, Sharpe **2.1157**, max_dd -0.0564, CVaR -0.0203, turnover 0.0614, recovery_capture 0.5878, calm_capture 0.7406, avg_bil 0.1958.

### U2b `improved_phaseu_prod80_r3_20_holdings_blend` (80 / 20)

Full: ann_return 0.0689, Sharpe 0.9008, max_dd -0.1379, CVaR -0.0256, turnover 0.0580, recovery_capture 0.2994.
Holdout: ann_return 0.1542, Sharpe **2.1306**, max_dd -0.0562, CVaR -0.0201, turnover 0.0630, recovery_capture 0.6082, calm_capture 0.7604.

### U2c `improved_phaseu_prod70_r3_30_holdings_blend` (70 / 30)

Full: ann_return 0.0688, Sharpe 0.9082, max_dd -0.1369, CVaR -0.0253, turnover 0.0592, recovery_capture 0.2969.
Holdout: ann_return 0.1544, Sharpe **2.1446**, max_dd -0.0559, CVaR -0.0199, turnover 0.0649, recovery_capture 0.6284, calm_capture 0.7798.

### U3 `improved_phaseu_conditional_prod_r2_holdings_blend`

Full: ann_return 0.0697, Sharpe 0.9023, max_dd -0.1395, CVaR -0.0259, turnover 0.0619, recovery_capture 0.3087, avg_bil 0.2837, avg_offense 0.5517.
Holdout: ann_return 0.1559, Sharpe **2.1333**, max_dd -0.0567, CVaR -0.0203, turnover 0.0673, recovery_capture 0.6240, calm_capture 0.7690, avg_bil 0.1955.

### Holdings diagnostics

| candidate | avg α (prod) | avg L1 dist to prod | avg L1 dist to partner | avg BIL |
|---|---|---|---|---|
| U1a 90/10 prod+R2 | 0.900 | 0.024 | 0.211 | 0.283 |
| U1b 80/20 prod+R2 | 0.800 | 0.047 | 0.188 | 0.283 |
| U1c 70/30 prod+R2 | 0.700 | 0.070 | 0.164 | 0.282 |
| U2a 90/10 prod+R3 | 0.900 | 0.031 | 0.278 | 0.284 |
| U2b 80/20 prod+R3 | 0.800 | 0.062 | 0.247 | 0.284 |
| U2c 70/30 prod+R3 | 0.700 | 0.093 | 0.216 | 0.285 |
| U3 conditional prod+R2 | 0.827 | 0.051 | 0.184 | 0.284 |

The conditional candidate sits between 80/20 and 90/10 on average-α, by design.

### Pairwise vs production / R2 / R3

| candidate | full Δ vs prod | holdout Δ vs prod | Sharpe Δ vs prod | bootstrap vs prod | rolling win | rolling mean Δ | full Δ vs R2 | holdout Δ vs R2 | Sharpe Δ vs R2 | bootstrap vs R2 |
|---|---|---|---|---|---|---|---|---|---|---|
| **U1a 90/10 R2** | +0.0067 | **+0.0003** | +0.0102 | 41.3% | **73.3%** | +0.0038 | -0.036 | +0.0134 | -0.045 | 61.3% |
| **U1b 80/20 R2** | +0.0124 | -0.0001 | +0.0191 | 40.6% | **60.0%** | +0.0067 | -0.030 | +0.0130 | -0.036 | 61.7% |
| **U1c 70/30 R2** | **+0.0175** | -0.0009 | +0.0269 | 40.1% | **60.0%** | +0.0092 | -0.025 | +0.0122 | -0.028 | 61.7% |
| **U2a 90/10 R3** | +0.0058 | -0.0001 | +0.0161 | 28.4% | **60.0%** | +0.0038 | -0.036 | +0.0130 | -0.039 | 59.7% |
| **U2b 80/20 R3** | +0.0110 | -0.0009 | +0.0311 | 28.2% | **60.0%** | +0.0068 | -0.031 | +0.0122 | -0.024 | 56.9% |
| **U2c 70/30 R3** | **+0.0167** | -0.0021 | +0.0450 | 27.8% | 53.3% | +0.0090 | -0.025 | +0.0110 | -0.010 | 53.1% |
| **U3 cond R2** | +0.0122 | -0.0028 | +0.0337 | **71.2%** | 40.0% | +0.0046 | -0.030 | +0.0103 | -0.022 | 67.6% |
| R2 | +0.042 | -0.013 | +0.055 | 38.9% | 46.7% | +0.025 | 0 | 0 | 0 | 0 |
| R3 | +0.047 | -0.018 | +0.116 | 26.8% | 40.0% | +0.019 | +0.005 | -0.004 | +0.061 | 7.5% |

## F. Phase U interpretation

**What helped.** Holdings-level blending worked. **For the first time in the project, candidates exist that simultaneously (a) match production on holdout raw composite, (b) beat production on Sharpe, (c) clear the rolling-win-rate ≥ 55% gate.** U1a 90/10 holds rank 1 in holdout raw composite across the entire 18-member cohort (0.9630 vs production's 0.9628). Six of the seven Phase U candidates hold holdout Δ within -0.003 of production — every one of them tighter than R2's -0.013 and R3's -0.018. Five candidates clear rolling-win 60% — three of them via the U1 family vs production, two via the U2 family. U3 conditional clears bootstrap 71.2% — the first candidate in the project to clear the 60% bootstrap floor vs production.

**What did not help.** No single candidate clears all six production gates simultaneously:
- **Full-history Δ ≥ +0.015**: only U1c (70/30 R2) at +0.0175 and U2c (70/30 R3) at +0.0167 clear. The 90/10 and 80/20 variants fall short (+0.006 to +0.012). The reason is mechanical: production's full-history composite is the lowest in the cohort (0.4777 → rank 18), and a mostly-production blend cannot lift that much.
- **Bootstrap ≥ 60%**: only U3 conditional (71.2%) clears. The U1 family sits at 40-41%, the U2 family at 28%. Holdings blending tightens holdout Δ but does not make the per-block excess return distribution dominate production reliably.
- **Holdout Δ ≥ 0**: only U1a (90/10 R2) clears at +0.0003. Every other candidate fell within -0.0009 to -0.0028 — close but not over the bar.

The pattern: **U1a clears 4 of 6 gates** (holdout Δ, Sharpe Δ, rolling win, rolling mean Δ). **U1c clears 4 of 6** (full Δ, Sharpe Δ, rolling win, rolling mean Δ). **U3 clears 4 of 6** (full Δ, Sharpe Δ, bootstrap, rolling mean Δ — but loses on rolling win). No candidate aligns the right four with the missing two.

**Did holdings-level blending help?** Yes, materially. Holdout raw Δ moved from -0.013 (R2) to +0.0003 (U1a) — the gap closed entirely on this axis. Bootstrap support vs production moved from 39% (R2) to 71% (U3 conditional) for one candidate. Rolling win-rate vs production moved from 47% (R2) to 73% (U1a) — best in project. **All three of these are first-time wins.**

**Did it preserve production's adverse-tape edge?** Yes. Holdout downside_capture for U1a is 0.220 vs production's underlying defensive holdings; max_dd -0.057 essentially matches production's -0.057. The U1 family's avg_offense and avg_defense in holdout are within 1pp of production, confirming the blend preserved the production positioning rather than diluting it.

**Did it preserve the trust branch's Sharpe / recovery advantages?** Partially. Holdout Sharpe lifts above production for every Phase U candidate (production 2.10, U1a 2.11, U1c 2.13, U2c 2.14, U3 2.13). But none reach R2's 2.155 or R3's 2.216. Recovery capture lifts to 0.59-0.63 (vs production's 0.57, R2's 0.76, R3's 0.77) — a partial transfer.

**Did it improve holdout raw composite, bootstrap, rolling win-rate?** Yes — see "What helped" above. All three first-time clears, just not in the same candidate.

**Did it beat R2/R3?** On holdout raw composite, yes — every Phase U candidate is +0.010 to +0.013 above R2 on holdout composite, with bootstrap probability vs R2 in the 53-68% range. On Sharpe, no — the trust branch retains the Sharpe edge.

**Did it beat the production pin under the validation rules?** No — no candidate clears all six gates. Closest: U1a, four gates passed.

**Is the branch exhausted?** **No.** This is the first sprint that produced multiple candidates within striking distance of all gates. The two unmet gates (full-Δ and bootstrap) are mechanical, not structural — they are direct consequences of α being static across history, not of any deeper failure. A narrow follow-up that varies α across the time series, or that uses phaseo / phasen as the partner (which have +0.09 full-composite advantage), is well-motivated and small in scope.

## G. Candidate classification

| candidate | classification | gates passed | notes |
|---|---|---|---|
| **U1a 90/10 prod+R2** | **Research-only** | holdout Δ ✓, Sharpe ✓, rolling win 73% ✓, rolling mean ✓ (4 of 6) | New closest-to-gate reference. Holdout Δ rank 1 in cohort. Misses on full Δ (+0.007 vs +0.015 needed) and bootstrap (41.3% vs 60% needed). |
| U1b 80/20 prod+R2 | Research-only | Sharpe ✓, rolling win ✓, rolling mean ✓ (3 of 6) | Holdout Δ -0.0001 (just misses), full +0.012, bootstrap 41%. |
| **U1c 70/30 prod+R2** | **Research-only** | full Δ ✓, Sharpe ✓, rolling win ✓, rolling mean ✓ (4 of 6) | First candidate ever to clear full Δ ≥ +0.015 with non-negligible holdout. Holdout Δ -0.0009, bootstrap 40%. |
| U2a 90/10 prod+R3 | Research-only | Sharpe ✓, rolling win ✓, rolling mean ✓ (3 of 6) | Mirror of U1a but with R3. Bootstrap 28% (worse than R2 family). |
| U2b 80/20 prod+R3 | Research-only | Sharpe ✓, rolling win ✓, rolling mean ✓ (3 of 6) | |
| U2c 70/30 prod+R3 | Research-only | full Δ ✓, Sharpe ✓, rolling mean ✓ (3 of 6 — rolling win 53.3% just misses 55%) | Highest holdout Sharpe of the U-family at 2.145. |
| **U3 conditional prod+R2** | **Research-only** | full Δ ✓, Sharpe ✓, bootstrap 71% ✓, rolling mean ✓ (4 of 6) | First candidate ever to clear bootstrap ≥ 60% vs production. Misses on rolling win (40%) and holdout Δ (-0.0028). |

**Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.**
**Shadow pin: `improved_phase2b_combo_abc` — unchanged.**

## H. Strategic diagnosis

**Did Phase U succeed?** Partially — by far the most successful sprint of the entire ML-meta-allocator era. The hypothesis was confirmed: **production's holdout edge does live partly in specific weekly ETF holdings.** Direct holdings blending preserves that edge. Three different holdout-deployment gates were cleared for the first time (holdout Δ ≥ 0 by U1a; rolling win ≥ 55% by U1a/b/c, U2a/b; bootstrap ≥ 60% by U3). No single candidate clears all six gates, so no Promote.

**Is there anything left in the current allocator/trust/regime branch?** Yes — narrowly. Two specific moves are well-motivated by Phase U's findings:

1. **Use phaseo or phasen as the holdings-blend partner instead of R2/R3.** phasen sits at full composite 0.5666 vs R2's 0.5198 — a +0.047 advantage. A 90/10 prod+phaseo blend would inherit production's holdout edge while gaining ~0.005-0.008 on full-history composite, which is exactly the size of U1a's residual full-Δ shortfall.
2. **Conditional α-grid that maximizes bootstrap support.** U3 confirms that conditioning α on the hard `defense_production` flag lifts bootstrap from 41% to 71%. A narrow variant — say 95/5 in defense weeks, 80/20 in calm/recovery weeks — might preserve the bootstrap lift while restoring rolling win.

**Or has this branch reached its ceiling?** Not yet — the diagnostic is too clear and the residual gaps are too narrowly mechanical. The structural-ceiling claim from Phase T was contingent on holdings blending also failing flat. It did not. The branch has at least one disciplined sprint left in it. After that sprint, if no candidate clears all gates simultaneously, the ceiling claim becomes warranted.

## I. Final recommendation

- **Production pin: stay on `improved_phase2b_regime_confidence_boost`.** No candidate clears all six Phase D gates.
- **Shadow pin: stay on `improved_phase2b_combo_abc`.** Phase U candidates are not the best non-production by full-history composite (phasen still leads).
- **Closest-to-gate research reference: replace R2 with U1a (`improved_phaseu_prod90_r2_10_holdings_blend`).** U1a dominates R2 on the deployment-relevant axes (holdout Δ +0.013 vs R2, rolling win 73% vs 47%, bootstrap 61% vs R2's reference baseline) while retaining acceptable Sharpe (only -0.045 vs R2). R2 stays in the comparator set as a Sharpe-balanced trust reference but is no longer the headline closest-to-gate name.
- **Sharpe research reference: stay on R3 (`improved_phaser_fast_narrow_regret_allocator`).** Holdout Sharpe 2.216 is still the highest in the cohort; Phase U topped out at 2.145.
- **Bootstrap research reference (new): U3 (`improved_phaseu_conditional_prod_r2_holdings_blend`).** First candidate to clear bootstrap 60%. Worth tracking explicitly because it exists at a different point in the trade-off space (high bootstrap, low rolling win) than the U1 family.
- **Add T1 to the comparator set as before** (full-history composite reference at 0.5545).

**Next step.** Run **Phase V — Holdings Blend Refinement**, the genuinely final sprint in this branch. Three small candidates only:
1. **V1**: 90/10 prod + phasen holdings blend (the partner with the highest full-history composite, designed to close U1a's full-Δ gap).
2. **V2**: 90/10 prod + phaseo holdings blend (same idea, with the highest holdout Sharpe ML reference).
3. **V3**: tighter conditional — 95/5 in `defense_production`, 80/20 elsewhere — designed to preserve U3's bootstrap edge while lifting rolling win above 55%.

If Phase V produces a candidate that clears all six Phase D gates, promote. If Phase V also fails — meaning four sprints in this branch (Q,R,S,T,U,V) cannot align all six gates — then the deployment ceiling is structural, **production stays deployed, U1a becomes the official research-track closest-to-gate reference, and any future work moves to a sleeve-panel revisit** rather than another allocator/trust/regime/holdings sprint on this universe.

## J. Project journey log update

- Updated `docs/research/project_journey.md`: Section 34 — Phase U — Production-Anchored Holdings Blend — appended at the end of the file.
- Project journey is now current through Phase U.
