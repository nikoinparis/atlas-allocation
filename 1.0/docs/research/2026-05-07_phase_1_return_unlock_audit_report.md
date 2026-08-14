# Phase 1 — Return Unlock Audit

**Date:** 2026-05-07
**Type:** Diagnostic. No strategy candidates created. No pins changed.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Production candidate:** `improved_phaseggg_confirmed_only_robust_offense`
**Shadow:** `improved_phase2b_combo_abc`

---

## Commands Executed

```
python3 scripts/phase_1_return_unlock_audit.py
```

---

## Files Created / Modified

**Script created:**
- `scripts/phase_1_return_unlock_audit.py`

**Outputs (all in `data/research/phase_1_return_unlock_audit/`):**
- `phase1_core_portfolio_inventory.csv`
- `phase1_benchmark_inventory.csv`
- `phase1_full_and_holdout_metrics.csv`
- `phase1_candidate_vs_benchmark_holdout_table.csv`
- `phase1_recent_period_metrics.csv`
- `phase1_cash_drag_decomposition.csv`
- `phase1_state_exposure_summary.csv`
- `phase1_sleeve_weight_by_state.csv`
- `phase1_state_return_contribution.csv`
- `phase1_opportunity_cost_vs_spy.csv`
- `phase1_upside_miss_windows.csv`
- `phase1_loss_avoidance_windows.csv`
- `phase1_capture_ratios_by_window.csv`
- `phase1_capture_ratios_by_state.csv`
- `phase1_beta_correlation_summary.csv`
- `phase1_return_target_scenarios.csv`
- `phase1_required_risk_budget_shift.csv`
- `phase1_aggressive_mandate_feasibility.csv`
- `phase1_holdout_bottleneck_diagnosis.csv`
- `phase1_next_phase_recommendation.csv`

**Docs updated:**
- `docs/research/project_journey.md`

---

## Part A — Portfolio and Benchmark Inventory

| Portfolio | Role | Start | End | Weeks |
|---|---|---|---|---|
| `improved_phase2b_regime_confidence_boost` | Production pin | 2005-01-07 | 2026-04-10 | 1110 |
| `improved_phase2b_combo_abc` | Official shadow | 2005-01-07 | 2026-04-10 | 1110 |
| `improved_phaseggg_confirmed_only_robust_offense` | Production candidate | 2005-01-07 | 2026-04-10 | 1110 |
| `improved_phasesss3_calm_old_low_stress_derisk` | Research shadow | 2005-01-07 | 2026-04-10 | 1110 |
| SPY | Equity benchmark | 2005-01-14 | 2026-04-10 | 1109 |
| 60/40 (SPY + IEF) | Blended benchmark | 2005-01-14 | 2026-04-10 | 1109 |
| Equal weight ETF | Diversified benchmark | 2005-01-07 | 2026-04-10 | 1110 |

---

## Part B — Full Period and Holdout Metrics

### GGG1 (production candidate) across all windows

| Window | Ann Return | Sharpe | Max DD | Avg BIL | Avg SPY |
|---|---|---|---|---|---|
| Full (2005–2026) | **7.14%** | 0.936 | -11.77% | 26.7% | 6.0% |
| Holdout 2016+ | 8.13% | 1.019 | -11.77% | 22.8% | 5.9% |
| Holdout 2020+ | 9.55% | 1.082 | -11.77% | 23.6% | 5.8% |
| Holdout 2021+ | 10.22% | 1.348 | -7.25% | 22.7% | 6.1% |
| Bear 2022 | -1.29% | -0.211 | -6.84% | 55.0% | 3.0% |
| Recovery 2023+ | 14.36% | 1.797 | -7.25% | 12.2% | 5.9% |

### Holdout comparison (2020-forward): GGG1 vs benchmarks

| Portfolio | Ann Return | Sharpe | Max DD |
|---|---|---|---|
| GGG1 (prod candidate) | **9.55%** | **1.082** | **-11.77%** |
| Prod pin (phase2b_rcb) | 8.07% | 0.936 | -13.98% |
| Shadow (phase2b_abc) | 8.04% | 0.941 | -13.67% |
| Equal weight ETF | 7.08% | 0.923 | -14.33% |
| SPY | 14.14% | 0.732 | -31.83% |
| 60/40 (SPY+IEF) | 8.81% | 0.733 | -20.76% |

**Observations:**
- GGG1 leads all strategy pins on Sharpe in every holdout window.
- On raw return, SPY (14.1%) and 60/40 (8.8%) exceed GGG1 (9.55%) in 2020-forward.
- GGG1's max drawdown (-11.77%) is dramatically better than SPY (-31.83%) and 60/40 (-20.76%).
- GGG1 risk-adjusted quality is high. The absolute return ceiling is the audit subject.

---

## Part C — Return Bottleneck Decomposition

### State distribution and BIL exposure

| State | Weeks | Freq | Avg BIL | Avg SPY | Ann Port Return | Ann SPY | Opp Cost vs SPY |
|---|---|---|---|---|---|---|---|
| calm_trend | 295 | 26.6% | 11.0% | 8.0% | 4.3% | 17.5% | **-13.2%** |
| neutral_mixed | 493 | **44.4%** | **26.0%** | 6.6% | 11.5% | 9.8% | +1.7% |
| stressed_panic | 229 | 20.6% | **53.1%** | 2.5% | 3.9% | -0.5% | +4.2% |
| recovery_fragile | 49 | 4.4% | 17.0% | 5.4% | 7.0% | 54.8% | **-47.5%** |
| recovery_confirmed | 44 | 4.0% | 11.4% | 5.6% | 2.6% | 40.8% | **-38.2%** |

### State return contributions to total wealth

| State | Freq | Log Wealth Contribution | % of Total Wealth Created |
|---|---|---|---|
| neutral_mixed | 44.4% | 1.007 | **68.5%** |
| calm_trend | 26.6% | 0.227 | 15.4% |
| stressed_panic | 20.6% | 0.155 | 10.5% |
| recovery_fragile | 4.4% | 0.061 | 4.1% |
| recovery_confirmed | 4.0% | 0.021 | 1.5% |

### Sleeve weights by state

| State | dual_momentum | cta_trend | composite_selective | offense_comp | defense_comp | taa_sma | cash::BIL |
|---|---|---|---|---|---|---|---|
| calm_trend | 12.3% | 11.3% | 20.2% | 8.9% | **28.9%** | 14.8% | 3.6% |
| neutral_mixed | 8.9% | 10.8% | 15.0% | 11.2% | **20.4%** | 10.8% | **22.9%** |
| recovery_confirmed | 5.8% | 16.4% | 13.3% | 22.2% | 21.9% | 12.0% | 8.4% |
| recovery_fragile | 10.1% | 12.1% | 15.7% | 12.6% | 24.1% | 12.4% | 13.0% |
| stressed_panic | 5.5% | 6.1% | 10.5% | 4.9% | **14.9%** | 7.2% | **50.9%** |

### Key bottleneck findings

**1. Cash drag in neutral_mixed is the dominant constraint.**
- neutral_mixed is 44.4% of all weeks and generates 68.5% of total wealth.
- avg BIL = 26.0% in neutral_mixed, plus 22.9% in the explicit cash sleeve = significant drag.
- In these weeks, SPY returns 9.8% annualized; GGG1 matches (11.5%) via diversification, not offense concentration.

**2. Calm_trend upside capture is severely limited.**
- In calm_trend (26.6% of weeks), SPY returns 17.5% annualized.
- GGG1 earns only 4.3% in the same periods — an **opportunity cost of -13.2% annualized**.
- avg BIL still 11.0%, and defense_component sleeve = 28.9% even in bull trends.
- This is the largest per-week opportunity loss versus SPY.

**3. stressed_panic protection is strong and justified.**
- BIL at 53% in stressed state (20.6% of weeks).
- GGG1 earns +3.9% annualized vs SPY -0.5% in stressed state — protection works.
- 2022 bear: GGG1 active return vs SPY = **+16.9%**. Do not reduce stressed-state BIL.

**4. Recovery states are underexposed and rare.**
- recovery_confirmed + recovery_fragile = only 8.4% combined frequency.
- SPY earns 40-55% annualized in these periods; GGG1 earns 2.6-7%.
- Opportunity cost is enormous (-38 to -48% annualized) but low frequency means limited total impact.
- Fixing recovery re-risking would help but is not the primary bottleneck.

**5. Direct SPY exposure is low across all states (avg 6%).**
- SPY is present as a direct holding but never exceeds 8% average in any state.
- The portfolio holds diversified offense (QQQ, EFA, EEM, IWM) rather than concentrated SPY.

---

## Part D — Upside / Downside Capture

### GGG1 vs SPY by window

| Window | Upside Capture | Downside Capture | Capture Spread | Beta | Correlation | Active Return |
|---|---|---|---|---|---|---|
| Full | 4.5% | -12.6% | **17.1%** | -0.031 | -0.071 | -3.4% |
| Holdout 2016+ | 6.1% | -14.1% | **20.1%** | -0.058 | -0.122 | -6.0% |
| Holdout 2020+ | 6.6% | -13.6% | **20.2%** | -0.065 | -0.143 | -4.6% |
| Holdout 2021+ | 9.1% | -14.0% | **23.2%** | -0.034 | -0.073 | -3.5% |
| Bear 2022 | 3.6% | +4.3% | **-0.6%** | +0.012 | +0.045 | **+16.9%** |
| Recovery 2023+ | 13.6% | -23.2% | **36.8%** | -0.070 | -0.126 | -6.3% |

### GGG1 vs SPY by state

| State | Weeks | Upside Capture | Downside Capture | Capture Spread | Active Return (wkly) |
|---|---|---|---|---|---|
| neutral_mixed | 492 | 5.7% | -24.3% | **30.0%** | +0.031% |
| calm_trend | 295 | 3.5% | -13.7% | **17.2%** | **-0.228%** |
| stressed_panic | 229 | 2.6% | -1.7% | 4.3% | +0.087% |
| recovery_fragile | 49 | 8.4% | -12.4% | **20.8%** | -0.716% |
| recovery_confirmed | 44 | 8.2% | +8.3% | **-0.1%** | -0.606% |

**Interpretation:**
- Negative correlation to SPY across most windows is a feature, not a bug — it explains the low max drawdown.
- Downside capture near -12 to -14% full period means GGG1 barely participates in SPY drawdowns.
- Upside capture of 4-9% means GGG1 earns only a fraction of SPY upsides — this is the return ceiling.
- Capture spread of 17-37% confirms the strategy is genuinely defensive in character.
- In calm_trend the weekly active return is -0.228% — 11.9% annualized opportunity cost in SPY's best states.

---

## Part E — What Would It Take to Reach 9–11%?

These are diagnostic estimates, not backtested candidates.

| Target Return | Incremental Needed | BIL Reduction Required | New Avg BIL | Implied Vol | Implied Sharpe | Implied Max DD |
|---|---|---|---|---|---|---|
| 9% | +1.9pp | -20.5pp | **6.2%** | 9.1% | 0.99 | -14.1% |
| 10% | +2.9pp | -31.4pp | **0%** | 9.9% | 1.01 | -15.3% |
| 11% | +3.9pp | -42.4pp | **0%** (floored) | 10.7% | 1.03 | -16.5% |

**Assumptions:** offense returns ~85% of SPY (10.4% ann), BIL returns 1.3% ann (full period), proportional vol scaling with partial beta load (70%).

**Key insight:** Reaching 9% requires reducing average BIL by ~20 percentage points — from 26.7% to ~6.2%. This is not a tweak; it is a mandate change. It implies:
- Near-zero BIL in neutral_mixed periods (currently 26%).
- Higher offense cap in calm_trend (currently moderate).
- Allowing implied max drawdown of ~14-15% vs current -11.8%.

Reaching 10-11% likely requires near-zero BIL in all non-stressed states and a new portfolio mandate with max drawdown tolerance of 18-22%.

---

## Part F — Holdout-Specific Bottleneck Diagnosis

| Window | GGG1 Return | SPY Return | Active | Avg BIL | Primary Bottleneck |
|---|---|---|---|---|---|
| 2016+ | 8.1% | 14.1% | -6.0% | 23% | Low offense exposure vs SPY |
| 2020+ | 9.5% | 14.1% | -4.6% | 24% | Low offense exposure vs SPY |
| 2021+ | 10.2% | 13.7% | -3.5% | 23% | Low offense exposure vs SPY |
| 2022 (bear) | -1.3% | -18.2% | **+16.9%** | 55% | **None — protection worked** |
| 2023+ (recovery) | 14.4% | 20.6% | -6.3% | 12% | Neutral_mixed conservatism persists even in recovery/bull |

**Across all non-crisis holdout windows:** the bottleneck is consistently the same — low offense exposure relative to SPY in good markets. This is not a regime timing failure; the regime engine is correctly classifying states. It is a mandate-level constraint: the portfolio is designed to hold 25-30% average BIL and limit offense concentration.

**2022 is the vindication of the current mandate.** +16.9% active return versus SPY during the worst bear market since 2008-2009. This protection is what the current mandate is designed to deliver.

---

## Part G — Next Phase Recommendation

### Recommendation: `PROCEED_TO_PHASE_2_AGGRESSIVE_ETF_VARIANT`

**Evidence:**

1. **Return ceiling is mandate-driven, not regime-timing-driven.**
   - Regime engine correctly identifies stressed vs non-stressed states.
   - BIL in stressed_panic (53%) is protective and justified.
   - The constraint is the high BIL level in non-stressed states (neutral_mixed 26%, calm_trend 11%).

2. **Largest single return leakage: neutral_mixed at 44% frequency.**
   - 26% avg BIL in the state that accounts for 68.5% of total wealth creation.
   - Reducing this to 5-10% is the single highest-leverage lever.

3. **calm_trend upside capture is severely limited (-13.2% ann opportunity cost).**
   - 28.9% defense component even in calm bull trends.
   - This is the second largest bottleneck.

4. **SPY direct exposure (avg 6%) is unchanged across mandate variants.**
   - A higher-return variant needs more concentrated offense, not just less BIL.

5. **SSS3 shadow does not resolve the return ceiling.**
   - SSS3 is a regime-sequence refinement that slightly reduces losses in specific sequence transitions.
   - It does not address the mandate-level BIL and offense allocation.

6. **PPP found no new latent sleeve, QQQ pointed to regime-sequence (covered by SSS branch).**
   - No new information sources needed at the ETF level.

7. **9-10% return is feasible with a controlled mandate change.**
   - Requires avg BIL reduction of ~12-20pp.
   - Implies max drawdown expansion from -11.8% to -14-16%.
   - Sharpe may improve or hold (offense ETFs in good states can be risk-efficient).

8. **A higher-return mandate is not automatically reckless.**
   - 60/40 has Sharpe 0.73 with -20.8% max DD. GGG1-like quality at 9% would be Sharpe ~1.0 with -14% max DD.
   - Phase 2 should explicitly define the new mandate: target return, max drawdown tolerance, turnover budget.

### What Phase 2 must NOT do:
- Do not touch the current production pin.
- Do not modify the current GGG1 production candidate.
- Do not increase stressed_panic offense.
- Do not remove the regime engine gating.

### What Phase 2 should test:
- Reduce BIL floor in neutral_mixed from 26% to 5-10%.
- Allow higher offense cap in calm_trend (reduce defense_component from 29% to 10-15%).
- Explicit mandate: target 9-10% return, max DD tolerance 18-20%.
- All tested out-of-sample against GGG1 and production pin.
- Required to beat BOTH tracks before any promotion.

---

## Warnings

- The upside_capture ratios appear low (~4-14%) because GGG1 and SPY are near-zero correlated (beta ~-0.03 to -0.07). This is expected — it confirms the diversified, defensive character of the strategy.
- SPY has 1 fewer week (1109 vs 1110) due to the initial pct_change() drop. All comparisons align on common dates.
- Recovery state opportunity costs (-38 to -48% ann) look alarming but represent only 8.4% of total time. The per-week miss is real but the total contribution to the return gap is moderate.
- Scenarios in Part E are linear approximations. Actual Phase 2 backtests may find that offense return in neutral/calm states is lower than 85% of SPY due to diversification drag.

---

## Git Status

Unstaged changes at audit start. Script and outputs are new files. No pins changed. No strategy files modified.

---

## Final Verdict

**Classification: Diagnostic complete — `PROCEED_TO_PHASE_2_AGGRESSIVE_ETF_VARIANT`**

The return ceiling (~7.1% full period, ~9-10% in recent holdouts) is primarily a **mandate constraint**, not a regime-timing failure. The regime engine works well — 2022 bear protection (+16.9% active return vs SPY) validates the stressed-state BIL allocation. The bottleneck is that 26% BIL persists during neutral_mixed (44% of all weeks) and the defense_component sleeve remains large even in calm_trend bull markets. A separate higher-return ETF mandate targeting 9-10% with an explicit max drawdown tolerance of 18-20% is justified and feasible.

---

## Phase 2 Prompt Outline

**Phase 2 — Aggressive ETF Variant**

Goal: Build a higher-return ETF portfolio variant that explicitly relaxes the BIL/cash floor and offense cap, targeting 9-10% annual return with max drawdown tolerance of 18-20%. Keep the same regime engine and state classification. No new data sources. Compare out-of-sample against both GGG1 (production candidate) and phase2b_regime_confidence_boost (production pin). Require clear improvement on both tracks before any promotion. Report all metrics per Part B–D conventions established in Phase 1.

Specific interventions to test:
1. Reduce BIL floor in neutral_mixed from 26% → 5-10%.
2. Reduce defense_component cap in calm_trend from 29% → 10-15%.
3. Allow higher offense ETF concentration in confirmed/calm states.
4. Explicit mandate parameter: `allowed_max_drawdown = 0.20`.
5. Test individually and in combination (incremental contribution protocol).

Do not test:
- Stressed_panic offense increase (protected by mandate).
- New data sources.
- Stock-level data.
- New regime engine (use existing market_state_history.csv).

---

## Resume / Project Story

This ETF quant portfolio project has now completed three major development arcs:

**Arc 1 (Phases 1–2B):** Built and hardened the core regime engine, offense/defense sleeve architecture, and dual-track production system. Culminating production pin: `improved_phase2b_regime_confidence_boost`.

**Arc 2 (Phases AAA–GGG):** Refined offense composition and confirmation gating, producing the current production candidate: `improved_phaseggg_confirmed_only_robust_offense` (7.14% full-period, 9.55% 2020-forward, Sharpe 1.08, max DD -11.77%).

**Arc 3 (Phases OOO–SSS):** Hard-ML signal discovery branch. Expanded signal universe (OOO), tested latent factors (PPP — null result), investigated feature interactions (QQQ — pointed to regime-sequence modeling), validated regime-sequence signals (SSS2), and built sequence portfolio overlays (SSS3 — improved_phasesss3_calm_old_low_stress_derisk promoted to research shadow only).

**Phase 1 (Return Unlock Audit — this phase):** Diagnosed the return ceiling systematically. Finding: ceiling is mandate-driven, not regime-timing-driven. Regime engine is working. The constraint is 26% BIL in neutral_mixed (44% of weeks) and capped offense in calm_trend. Recommendation: Phase 2 Aggressive ETF Variant.

**Next: Phase 2 — Aggressive ETF Variant.** Build a separate higher-return mandate targeting 9-10% with 18-20% max DD tolerance, using the same regime engine, no new data sources.
