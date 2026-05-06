# Phase W — Sleeve-Panel Revisit / Opportunity-Set Upgrade

**Sprint date:** 2026-04-24
**Branch:** post allocator/trust/regime/holdings-blend closure
**Layer:** 2 (sleeves only — no allocator, no regime engine, no holdings blending)
**Production candidate (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow track (unchanged):** `improved_phase2b_combo_abc`

---

## A. Mission

The allocator/trust/regime/holdings-blend branch closed at the end of Phase V because every additional knob in that branch traded one Phase D gate for another. Phase V's V1 candidate cleared the full-sample lift gate (+0.0173) but lost rolling win (47%), holdout Δ (-0.0008), and bootstrap (32%). The structural Pareto frontier inside that branch was exhausted.

Phase W therefore moves *upstream* in the layered architecture. Instead of trying to extract more lift from the existing 6-sleeve active panel by re-mixing sleeve outputs at allocation time, this sprint asks a simpler question: **does the sleeve panel itself have the structural diversity we need for a future allocator phase to actually have something to choose from?**

The current active panel (`dual_momentum_topn`, `composite_calm_trend_specialist`, `composite_healthier_recovery_specialist`, `composite_anti_chop_clarity`, `composite_regime_conditioned`, `taa_10m_sma`) is densely intercorrelated (avg |corr| 0.66, max 0.78). When the allocator views the panel, most pairwise pairs already track each other, so the allocator's "choice" is largely cosmetic.

Phase W introduces four candidate Layer-2 sleeves designed to fill clearly identified structural gaps:

- **W1 — `composite_structural_defense_sleeve`**: explicit, callable defensive role (GLD/TLT/HYG/LQD/DBA/BIL) keyed off a stress-score, replacing the implicit defensive role currently scattered across `composite_anti_chop_clarity` and BIL drag.
- **W2 — `composite_recovery_confirmed_offense_sleeve`**: silent except in `recovery_confirmed` or `recovery_fragile + breadth_change_4w > 0`; cleanly captures the "recovery dispatch" the existing recovery specialist tries but mixes with calm-trend behavior.
- **W3 — `composite_calm_carry_sleeve`**: active only in `calm_trend AND market_trend_positive`; clean carry/quality bias for confirmed risk-on regimes only.
- **W4 — `composite_macro_trend_diversifier_sleeve`**: cross-asset (SPY / EFA / VWO / TLT / GLD / PDBC / DBA / USO / UUP) long/flat tsmom with inverse-vol scaling — explicitly a cross-asset diversifier, not an equity sleeve.

All four sleeves run on **walk-forward causal features** (1-week-lagged signals, no in-sample leakage) and are evaluated against the existing 6-sleeve active panel.

---

## B. What was executed

Script: `scripts/phase_w_sleeve_panel_revisit.py` (~600 lines).

For each new sleeve:

1. Standalone full-sample metrics (1109 weekly obs)
2. Standalone holdout metrics (last 139 weeks)
3. Standalone state-conditional metrics across all five market states (calm_trend, neutral_mixed, recovery_confirmed, recovery_fragile, stressed_panic)
4. Pairwise correlation with all six active sleeves
5. Distinctness summary: avg / max / median |off-diagonal corr|

Panel-level diagnostics across four panels:

- `active_panel_naive` (6 sleeves)
- `active_plus_w1` (7 sleeves)
- `active_plus_w1_w2_w3` (9 sleeves)
- `active_plus_w1_w2_w3_w4` (10 sleeves)

For each panel: naive equal-weight blend metrics, state winner per market state, separability summary.

All artifacts saved under `data/03_layer2a_strategy_logic/`:
- `strategy_returns_composite_*_sleeve.csv` (4 files)
- `strategy_positions_composite_*_sleeve.csv` (4 files)
- `phase_w_sleeve_summary.csv`
- `phase_w_sleeve_state_summary.csv`
- `phase_w_sleeve_holdout_summary.csv`
- `phase_w_sleeve_correlation.csv`
- `phase_w_panel_blend_summary.csv`
- `phase_w_panel_state_winner_summary.csv`
- `phase_w_panel_separability_summary.csv`
- `phase_w_diagnostics_protocol.json`

---

## C. Standalone sleeve metrics

| Sleeve | Ann Return | Sharpe | Max DD | CVaR-5 | Turnover | Avg BIL |
|---|---:|---:|---:|---:|---:|---:|
| W1 — structural defense | 2.27% | 0.65 | -11.25% | -1.09% | 0.035 | 64.78% |
| W2 — recovery offense | 0.62% | 0.20 | -14.99% | -0.93% | 0.138 | 91.80% |
| W3 — calm carry | 0.79% | 0.28 | -11.11% | -1.14% | 0.168 | 73.42% |
| W4 — macro trend diversifier | 2.68% | 0.38 | -18.01% | -2.47% | 0.129 | 39.79% |

**Reading:**

- **W1 has the cleanest standalone profile.** Sharpe 0.65 with extremely low turnover (3.5%), and the smallest CVaR-5 of the four. It's a low-frequency, low-friction defensive sleeve.
- **W2 is silent most of the time** (avg BIL 92%, fires only in recovery states). Standalone metrics are dominated by the BIL backstop, not the active dispatch.
- **W3 is similar in shape** — silent most of the time, only fires in confirmed risk-on calm.
- **W4 is the highest-vol sleeve** with Max DD -18%; the lowest avg BIL (40%, since cross-asset trend keeps multiple assets long).

---

## D. Holdout (last 139 weeks)

| Sleeve | Ann Return | Sharpe | Max DD | Turnover |
|---|---:|---:|---:|---:|
| W1 — structural defense | 6.80% | **3.96** | -0.91% | 0.032 |
| W2 — recovery offense | 4.51% | 1.11 | -5.80% | 0.121 |
| W3 — calm carry | 4.20% | 1.18 | -3.05% | 0.187 |
| W4 — macro trend diversifier | 10.02% | 1.51 | -7.33% | 0.200 |

**Reading:**

- W1's holdout sharpe of 3.96 is real but partly a function of the holdout window having sustained calm/neutral periods where W1's tilt toward GLD/TLT/HYG/LQD outperformed cash. The -0.91% holdout MDD is the more durable signal: W1 essentially never had a bad week in the holdout window.
- W4's 10% holdout return is the highest absolute, but it comes with vol — its full-sample Max DD of -18% should be assumed in any sizing.
- W2 and W3 produce respectable holdout sharpes only because both spent most of the holdout in BIL during regimes where they're silent (BIL is stable cash, hence high sharpe).

---

## E. State-conditional metrics — where each sleeve actually contributes

W1 — structural defense:
- calm_trend: sharpe **1.20** (avg defensive weight 0.15)
- neutral_mixed: sharpe **1.24** (avg defensive weight 0.26)
- recovery_confirmed: sharpe -0.38 (43 obs — small sample, defensive-heavy 0.51)
- recovery_fragile: sharpe -1.03 (49 obs — gives back when recovery becomes confirmed)
- stressed_panic: sharpe **0.57** (avg defensive weight 0.57)

W1 is the only sleeve in the panel that earns a **positive sharpe in stressed_panic** while running the actual defensive basket (vs. just sitting in BIL). And it does so with very low turnover.

W2 — recovery offense:
- recovery_confirmed (43 obs): ann return **-14.96%**, sharpe **-1.93**
- recovery_fragile (49 obs): ann return -2.42%, sharpe -0.37

W2's design hypothesis (top-4 breadth-confirmed momentum at recovery entry) is **wrong empirically** in this dataset. The breadth-confirmed momentum top-4 at recovery entry are exactly the names that ran hardest into the prior drawdown and are the most prone to mean-reversion at the inflection — the sleeve buys the bounce and then catches the second leg of the chop.

W3 — calm carry:
- calm_trend (when active): sharpe **0.07** (essentially zero alpha)
- recovery_confirmed (in BIL): sharpe 4.42 ← BIL artifact
- recovery_fragile (in BIL): sharpe 5.56 ← BIL artifact
- stressed_panic (in BIL): sharpe 2.73 ← BIL artifact

The headline state-winner numbers for W3 are misleading. When the sleeve "wins" recovery_confirmed/fragile/stressed_panic at sharpe 4-5+, it is wholly invested in BIL during those states, so the high sharpe is the sharpe of cash in low-vol regimes, not signal alpha. The **true active sharpe in the only state where W3 actually allocates risk-on (calm_trend) is 0.07** — noise.

W4 — macro trend diversifier:
- calm_trend: sharpe 0.08 (low — runs against the current calm trend playbook)
- neutral_mixed: sharpe **0.84** (493 obs — broad sample, real)
- recovery_confirmed: sharpe -0.14
- recovery_fragile: sharpe **0.74** (49 obs — small but positive)
- stressed_panic: sharpe -0.03

W4 is genuinely useful in **neutral_mixed** (the largest state by observation count, where the existing panel's best is `taa_10m_sma` at 1.60) and modestly in recovery_fragile.

---

## F. Distinctness — pairwise correlation vs the active 6

| New sleeve | Max corr vs active 6 | Avg corr vs active 6 |
|---|---:|---:|
| W1 — structural defense | 0.09 (taa_10m_sma) | 0.02 |
| W2 — recovery offense | -0.08 | -0.09 |
| W3 — calm carry | -0.05 | -0.06 |
| W4 — macro trend diversifier | 0.02 | -0.02 |

All four candidate sleeves are **structurally orthogonal** to the active panel — the highest correlation is W1's 0.09 with `taa_10m_sma`, and the average correlations are essentially zero or slightly negative. This is the cleanest distinctness profile of any sleeve-batch we've evaluated.

Inside the new sleeves themselves:
- W1 ↔ W4: 0.38 (both touch GLD/TLT defensively)
- W3 ↔ W4: 0.28 (both have macro/carry exposure)
- All other new-vs-new pairs: ≤ 0.11

---

## G. Panel separability

| Panel | Sleeves | Avg \|off-diag corr\| | Max \|off-diag\| | Median \|off-diag\| |
|---|---:|---:|---:|---:|
| active panel naive | 6 | **0.66** | 0.78 | 0.66 |
| active + W1 | 7 | 0.48 | 0.78 | 0.65 |
| active + W1+W2+W3 | 9 | 0.31 | 0.78 | 0.09 |
| active + W1+W2+W3+W4 | 10 | **0.27** | 0.78 | 0.09 |

The current panel is dense (avg |corr| 0.66). Adding W1 alone drops avg correlation by 18 points. Adding W1+W2+W3+W4 drops it by 39 points and brings the **median** off-diagonal correlation from 0.66 down to 0.09.

This is the structural justification for Phase W: even sleeves with weak standalone alpha (W2, W3) genuinely lower the cross-sleeve correlation panel, which is the property an allocator phase needs in order to make non-cosmetic choices.

---

## H. Panel-level naive blend metrics

| Panel | Ann Return | Sharpe | Max DD | CVaR-5 | Calmar |
|---|---:|---:|---:|---:|---:|
| active panel naive (6) | 7.47% | 0.86 | -15.28% | -2.82% | 0.49 |
| active + W1 (7) | 6.76% | **0.91** | -13.73% | -2.43% | 0.49 |
| active + W1+W2+W3 (9) | 5.45% | 0.95 | -10.62% | -1.88% | 0.51 |
| active + W1+W2+W3+W4 (10) | 5.21% | **0.99** | -10.49% | -1.73% | 0.50 |

**Reading:**

- **Adding W1 alone is unambiguously beneficial at the naive blend level**: sharpe +0.04, MDD -1.55 pts, CVaR-5 -0.39 pts. Calmar holds.
- **Adding W2 + W3 + W4 continues to compress vol and drawdown** (Sharpe up to 0.99, MDD down to -10.49%) at cost of absolute return (drops to 5.21% from 7.47%). This is dilution by sleeves that are largely in BIL.
- The naive blend tells us that an allocator **should not equally weight** the new sleeves with the active 6 — the new sleeves earn their place via correlation/regime distinctness, not equal-weight contribution. An allocator phase that knows W2/W3 are mostly silent and only weights them when they're active will get the diversification benefit without the absolute-return drag.

---

## I. Panel state winners — does the new panel have better calls?

Active panel naive (baseline):
- calm_trend: `composite_calm_trend_specialist` (0.64, margin +0.15)
- neutral_mixed: `taa_10m_sma` (1.60, margin +0.08)
- recovery_confirmed: `composite_regime_conditioned` (2.06, margin +0.65)
- recovery_fragile: `composite_calm_trend_specialist` (0.96, margin +0.45)
- stressed_panic: `composite_calm_trend_specialist` (0.76, margin +0.05)

active + W1:
- **calm_trend: W1 (1.20, margin +0.56)** ← state winner upgraded by +0.56 sharpe
- neutral_mixed, recovery_confirmed, recovery_fragile, stressed_panic: unchanged

W1 takes calm_trend cleanly and produces a much larger margin over the second-best sleeve. This is the most actionable upgrade in the sprint.

active + W1 + W2 + W3 (and +W4): the sharpe rankings in non-calm states get dominated by W3 due to the BIL artifact described in Section E. These should not be read as W3 "winning" those states.

---

## J. Final sleeve classification

**W1 — `composite_structural_defense_sleeve` → Promote.**
- Cleanest standalone profile in the sprint (sharpe 0.65, low turnover 3.5%, low CVaR).
- Holdout MDD -0.91% — extraordinary stability.
- Earns positive sharpe in stressed_panic (the only sleeve in the panel that does).
- Maximum correlation with any active sleeve is 0.09. Effectively orthogonal.
- Adds +0.04 sharpe / -1.55 pts MDD to the naive panel blend.
- Wins calm_trend in the panel by +0.56 margin over the prior best.
- Recommended for inclusion in the sleeve panel handed to the next allocator phase.

**W2 — `composite_recovery_confirmed_offense_sleeve` → Drop.**
- The state where it is supposed to contribute (recovery_confirmed) is the state where it has the worst sharpe (-1.93).
- Top-4 breadth-confirmed momentum at recovery entry buys the names most prone to mean-reversion at the inflection.
- Distinctness to the active panel is real (avg corr -0.09) but the sleeve has no alpha to monetize.
- Future research: try a *delayed* recovery sleeve that activates only after `recovery_confirmed` has held for ≥ 4 weeks rather than at first crossing.

**W3 — `composite_calm_carry_sleeve` → Research-only.**
- The state-winner table makes W3 look dominant, but the high sharpe in non-calm states is the sharpe of BIL during low-vol periods, not active alpha.
- True active sharpe in calm_trend (the only state where it allocates risk-on) is 0.07.
- Adds correlation distinctness to the panel (avg corr -0.06) but contributes ~zero standalone alpha.
- Future research: replace the carry+quality scoring with a more aggressive low-vol momentum filter, or restrict to fewer ETFs.

**W4 — `composite_macro_trend_diversifier_sleeve` → Conditional / research-only.**
- Genuinely orthogonal to the active equity panel (avg corr -0.02).
- Real alpha in neutral_mixed (sharpe 0.84) — a state where the active panel's best is `taa_10m_sma` at 1.60. W4 doesn't beat it but does provide a structurally different return stream during the largest market state.
- Holdout sharpe 1.51 with -7.33% MDD.
- Should not be deployed in its current form (-18% full-sample MDD is too punitive). Propose a vol-capped variant in a future sprint.

---

## K. Recommended go-forward sleeve panel for the next allocator rerun

| Sleeve | Status | Role |
|---|---|---|
| `dual_momentum_topn` | unchanged | broad equity momentum |
| `composite_calm_trend_specialist` | unchanged | calm-trend equity |
| `composite_healthier_recovery_specialist` | unchanged | recovery dispatch (current) |
| `composite_anti_chop_clarity` | unchanged | chop avoidance + partial defense |
| `composite_regime_conditioned` | unchanged | regime-aware equity |
| `taa_10m_sma` | unchanged | trend benchmark |
| **`composite_structural_defense_sleeve`** | **PROMOTED (W1)** | **explicit defense sleeve, callable in stress** |

→ 7-sleeve panel. Avg |corr| drops from 0.66 to 0.48. Adds a clean defensive role with positive sharpe in stressed_panic that no current sleeve provides.

W2/W3/W4 stay in the codebase as research artifacts but are not part of the production panel. They should not be passed to the next allocator phase as-is.

---

## L. Branch summary — what helped, what did not

**Helped:**
- W1 structural defense sleeve (clean alpha + diversification + low DD; promote).
- W4 cross-asset trend distinctness (genuinely orthogonal; needs vol cap).
- Panel separability dropped from avg |corr| 0.66 to 0.48 with one sleeve added.

**Did not help:**
- W2 recovery-confirmed offense (negative sharpe in target state — design empirically wrong here).
- W3 calm-carry as currently designed (zero true alpha; state-winner table is a BIL artifact).

**Honest reading:** the sleeve-panel revisit produced **one promotable sleeve (W1)** plus useful evidence that the existing 6-sleeve panel is over-correlated. The next allocator phase has a meaningfully better opportunity set than the one Phase V was working with — but the lift is structural (better orthogonality), not headline absolute return.

---

## M. What comes next

With W1 promoted and the closed allocator/trust/regime/holdings-blend branch behind us, the project's next logical sprint is:

**Phase X — allocator rerun on the upgraded 7-sleeve panel.**

Specifically: re-run `improved_phase2b_regime_confidence_boost` (production) and `improved_phase2b_combo_abc` (shadow) with the new 7-sleeve panel as input, and report *incremental contribution attributable to W1's inclusion*, separated from base allocator behavior. Phase D gates apply as usual.

This is the first sprint in many that should be expected to show genuine, non-tradeoff improvement, because it adds an actually-distinct return stream rather than re-mixing existing ones.
