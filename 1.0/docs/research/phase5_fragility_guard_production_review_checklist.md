# phase5_fragility_guard — Production Review Checklist

**Date created:** 2026-05-22  
**Phase 10A evaluation verdict:** PROMOTE  
**Status:** Pending human production-pin authorization  
**Production pin NOT yet changed.** No registry, dashboard, or public files modified.

---

## 1. Final Phase 10A Metrics Summary

| metric | production_pin | ggg_baseline | phase5_fragility_guard | FG vs PROD | FG vs GGG |
|--------|---------------|-------------|------------------------|------------|-----------|
| Full Sharpe | 0.8844 | 0.9362 | **0.9483** | +0.0638 | +0.0121 |
| Full Max DD | −13.98% | −11.77% | **−11.60%** | +2.38pp | +0.17pp |
| Full CVaR 5% | −2.618% | −2.538% | **−2.497%** | +0.12pp | +0.04pp |
| Holdout Sharpe | 2.100 | 2.151 | **2.179** | +0.079 | +0.028 |
| Bootstrap P vs GGG | — | — | **0.841** | — | > 0.60 ✓ |
| Bootstrap P vs PROD | — | — | **0.842** | > 0.60 ✓ | — |
| Rolling win vs GGG | — | — | **73.3%** | — | > 55% ✓ |
| Turnover cost delta | — | — | +0.029%/yr | < 0.15% ✓ | — |
| Hidden beta Δ | — | — | −0.003 | negligible ✓ | — |
| BIL Δ | — | — | +0.010 | not BIL-driven ✓ | — |
| Stressed-panic | 0.4967 | 0.4807 | **0.4793** | Δ−0.017 (within tolerance ✓) | — |

All 8 Phase D gates **PASS** vs both GGG baseline and current production pin.

---

## 2. Why phase5_fragility_guard Passed

**Design:** Phase 1 R2A offense scaling with Phase 4 fragility guardrail.

- **Phase 1 R2A component**: scales offensive ETF weights by `1 + 0.08 × clip(r2a, -1, 1)` in non-stressed states. R2A is a causal, 1-week-lagged deployment quality composite (breadth, path clarity, state persistence, leadership quality).
- **Phase 4 fragility guardrail**: caps the offense boost (prevents increase above baseline) when the raw Phase 4 leadership composite exceeds 0.50, which historically indicates late-cycle/crowded market conditions.
- **Stressed-panic**: modifier is unconditionally 1.0. No offense increase possible.

**Why the guardrail mattered:** Phase 4 leadership signals are anti-predictive of near-term returns (high quality leadership → lower next-week returns, a late-cycle phenomenon). Using Phase 4 as a CAP on Phase 1 boosts — rather than as an additive signal — correctly prevents over-deployment into crowded conditions while preserving Phase 1's defensive-quality signal.

---

## 3. What Changed vs Production Pin

| dimension | production_pin | phase5_fragility_guard |
|-----------|---------------|----------------------|
| Allocator base | Phase 2B `regime_confidence_boost` | GGG1 (`ggg_confirmed_only_robust_offense`) |
| Offense modifier | None (production allocator) | Phase 1 R2A (+0.08 × quality in non-stressed) |
| Fragility cap | None | Phase 4 guardrail (cap boost when leadership crowded) |
| Stressed_panic | Unchanged | Unconditionally unchanged (0.000 breach) |
| Annual turnover | baseline | +0.058%/yr extra cost (negligible) |
| Full Sharpe improvement | — | +0.064 vs production |
| Holdout Sharpe improvement | — | +0.079 vs production |
| Max drawdown improvement | — | 2.38pp tighter |

**Important:** phase5_fragility_guard is a WRAPPER MODIFIER applied to GGG1's allocator, not a standalone named strategy. Creating a deployable production candidate requires generating a named artifact.

---

## 4. State-by-State Review Checklist

Review each state. The checkboxes below require human confirmation.

### calm_trend (295 weeks, 26.6% of history)

| candidate | Sharpe | Capture |
|-----------|--------|---------|
| production_pin | ~0.514 | ~0.47 |
| phase5_fg | ~0.529 | verify |

- [ ] calm_trend Sharpe is not materially worse than production pin
- [ ] The binding calm_trend constraint (historically: limited by lack of PIT breadth data) is not worsened
- [ ] Average BIL in calm_trend is not materially higher than production pin

### neutral_mixed (493 weeks, 44.4% of history)

- [ ] neutral_mixed Sharpe is not worse than production pin
- [ ] No regression vs prior candidate in this large state

### recovery_confirmed (44 weeks, 4.0% of history)

- [ ] recovery_confirmed capture is verified — Phase 5 was designed to avoid weakening this
- [ ] Phase 3 re-risking failed to improve this; Phase 5 should not worsen it

### recovery_fragile (49 weeks, 4.4% of history)

- [ ] recovery_fragile capture is not materially worse than production pin

### stressed_panic (229 weeks, 20.6% of history)

- [ ] Stressed-panic Sharpe: production pin ≈ 0.497, phase5_fg ≈ 0.479 (Δ −0.017)
  - [ ] **CRITICAL**: This delta is within the ±0.05 tolerance gate. Confirm acceptable.
- [ ] Stressed-panic max drawdown not materially worsened
- [ ] Stressed-panic BIL/cash allocation not decreased
- [ ] Verify offensive ETF weights are NOT higher in stressed_panic than production pin
- [ ] assertion: `max_sp_offense_change = 0.000000` confirmed (from Phase 10A run)

---

## 5. Stressed-Panic Defense Checklist (Critical)

- [x] Phase 10A SP offense change assertion: **0.000000** (passed automatically)
- [x] Modifier is unconditionally 1.0 in stressed_panic
- [x] Fragility guardrail CANNOT reduce the stressed_panic guard (separate condition)
- [ ] Human confirms: stressed_panic Sharpe Δ −0.017 is acceptable
- [ ] Human confirms: the stressed_panic max drawdown is unchanged or better

---

## 6. Hidden Beta / BIL / Cash Checklist

- [x] Hidden beta Δ = **−0.003** — SPY exposure decreased slightly (acceptable)
- [x] BIL Δ = **+0.010** — slightly more cash (not BIL-reduction driven)
- [x] Offense Δ = **−0.009** — slightly less offense (consistent with fragility guard)
- [ ] Human confirms: the improvement is not simply from reducing risk exposure
  - Evidence: Sharpe improved (+0.064 vs production) while offense DECREASED — the signal is adding quality, not just adding exposure

---

## 7. Dashboard Review Checklist

- [ ] Run the dashboard in review mode showing phase5_fragility_guard as the pending candidate
- [ ] Verify first-paint homepage shows correct pending candidate label
- [ ] Verify state-conditional comparison charts are correct
- [ ] Verify the production pin is still shown as the official live strategy
- [ ] **DO NOT use `phase5_fragility_guard` as the production label in the dashboard until the pin is officially changed**

**Deferred:** Dashboard exposure requires generating a named strategy artifact and updating the production candidate registry. See Section 9.

---

## 8. Human Authorization Checklist

The following actions require explicit human authorization before execution:

- [ ] **Generate named artifact**: Run the allocator pipeline to produce saved weight files for `phase5_fragility_guard` (or an equivalent named strategy)
- [ ] **Update production_candidate_registry.json**: Change `production_candidate` from `improved_phaseggg_confirmed_only_robust_offense` to the new named artifact
- [ ] **Update dashboard bundle files**: Regenerate compact bundle to expose the new candidate
- [ ] **Update production_candidate_summary.csv**: Add row for the new frontier candidate
- [ ] **Deploy to review environment**: Verify Vercel build with updated candidate
- [ ] **Human sign-off**: Explicitly approve the production pin change
- [ ] **Update CLAUDE.md `Production pin`**: Only after all above steps complete
- [ ] **Final commit**: Stage and commit only the named files, never `git add -A`

---

## 9. Production Registry Update Instructions (Deferred)

The `data/05_layer3_portfolio_construction/production_candidate_registry.json` currently references:
- `production_candidate`: `improved_phaseggg_confirmed_only_robust_offense`

To update this to phase5_fragility_guard:

**Step 1:** Generate a named strategy artifact for the fragility guard modifier.

Option A — Create a new named allocator version that incorporates the Phase 1 R2A + fragility guardrail as permanent logic in the allocator, not as a wrapper modifier. This is the cleaner production path.

Option B — Run the wrapper with the fragility guard modifier and save the resulting weights under a new name, e.g., `improved_frontier_phase5_fragility_guard`.

**Step 2:** After the named artifact exists, update the registry JSON:
```json
{
  "production_candidate": "improved_frontier_phase5_fragility_guard",
  "candidate_status": "FRONTIER_PHASE10A_PROMOTE_PENDING_HUMAN_REVIEW",
  "promotion_phase": "Frontier Phase 10A",
  "promotion_report": "docs/research/frontier_phase10_final_evaluation_report.md",
  "prior_production_candidate": "improved_phaseggg_confirmed_only_robust_offense",
  "do_not_auto_promote": true
}
```

**Step 3:** Update `production_candidate_summary.csv` and `production_candidate_exposure_summary.csv` with the new candidate row.

**Step 4:** Regenerate dashboard compact bundles (only after human authorization).

---

## 10. Current State (as of 2026-05-22)

| item | status |
|------|--------|
| Production pin | **UNCHANGED** (`improved_phase2b_regime_confidence_boost`) |
| Shadow pin | **UNCHANGED** (`improved_phase2b_combo_abc`) |
| CLAUDE.md updated | ✓ (pending candidate field updated) |
| production_candidate_registry.json | **UNCHANGED** (deferred) |
| production_candidate_summary.csv | **UNCHANGED** (deferred) |
| public/ | **UNCHANGED** |
| src/ | **UNCHANGED** |
| Dashboard bundles | **UNCHANGED** |
| Governance checklist | ✓ this file |
| Named artifact for phase5_fg | ⚠ NOT YET CREATED (required for registry update) |

---

## 11. References

- Phase 10A full evaluation: `docs/research/frontier_phase10_final_evaluation_report.md`
- Phase 10A metrics: `data/research/frontier_phase10/final_candidate_metrics.csv`
- Phase 5A evaluation: `docs/research/frontier_phase5_allocator_objective_report.md`
- Frontier arc roadmap: `docs/research/frontier_deployment_intelligence_master_roadmap.md`
- Deployment architecture: `docs/research/deployment_architecture_stabilization_summary.md`
