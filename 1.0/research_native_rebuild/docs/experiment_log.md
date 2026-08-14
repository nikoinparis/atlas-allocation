# Path B — Experiment Log

---

## Entry 0: Sprint 0 — Why Path B Exists (2026-06-07)

### What Previous Macro Overlay Sprints Proved

Three consecutive overlay sprints tested whether the V3 macro/credit regime signal (NM+slowdown
+FC_benign, "Signal E_4wk") could improve the production portfolio via post-hoc mechanisms:

**Step 2 — Weekly ETF Tilt Overlay**
- 32 candidates, best ΔSharpe = +0.0049 (below +0.01 gate)
- Minimum turnover increase: 0.170/yr (gate: ≤0.03)
- 2x-cost test: -0.048 Sharpe delta
- **Verdict: RESEARCH-ONLY**

**Step 2B — Persistent Layer 2B Modifier**
- 10 candidates (from 560 coarse grid), best ΔSharpe = +0.0145 (above +0.01 gate!)
- Signal E candidate: holdout ΔSharpe = +0.041 (first positive holdout in program)
- Minimum turnover increase: 0.084/yr (2.8× gate)
- 2x-cost test: -0.033 Sharpe delta
- **Verdict: RESEARCH-ONLY — 9/10 gates pass, only G6 (turnover) fails**

**Step 2C — Near-Zero-Turnover Calibration**
- 68 candidates across static NM, monthly/quarterly frozen, 4-week rolling, slow score
- Best ΔSharpe = +0.0194 (new program high, 4-week rolling D definition)
- Signal E_4wk holdout ΔSharpe = +0.016 (second consecutive positive holdout)
- Minimum turnover increase: 0.057/yr (1.9× gate)
- 2x-cost test: -0.028 Sharpe delta (best yet, still negative)
- **Verdict: RESEARCH-ONLY — G6 fails for all 68 candidates**

### What Is Now Closed

The following research paths are formally closed:

1. **Weekly overlay mechanisms**: Weekly ETF tilt, weekly modifier application — closed Step 2.
2. **Episodic overlay mechanisms**: Persistence-filtered Layer 2B modifiers — closed Step 2B.
3. **Frozen calibration overlays**: Monthly/quarterly frozen sub-state — closed Step 2C.
4. **Smooth overlay mechanisms**: Slow-score modifier — closed Step 2C.
5. **FRED macro V1/V2 classification**: NFCI unavailable, all 3 attempts failed — closed earlier.

**Root cause, confirmed across all three sprints**:
The NM market state has 8.9 transitions/year. Any mechanism that responds to a sub-state signal
within NM must rebalance at transition points. At any intensity that generates ΔSharpe ≥ +0.01,
the turnover gate (≤0.03/yr) is mathematically unreachable.

### What Remains Open

1. **Native regime engine**: Defining neutral_soft_landing as a NATIVE state (not an overlay)
   may avoid the turnover problem entirely — state transitions are already priced into the
   baseline rebalancing, so a native state change costs no additional turnover.

2. **calm_trend alpha gap**: The largest untapped frontier (~26.6% of weeks). PIT stock breadth
   data (Norgate, ~$100/mo) is the clearest path. Not addressed in Path B.

3. **Static strategy profile selection**: A different static allocation permanently calibrated to
   NM+slowdown behavior could be tested without any dynamic rebalancing. Tentatively in Path B.

4. **Completely rebuilt Layer 2B**: If the regime engine is rebuilt from scratch with macro
   conditioning as a native feature, the turnover costs are absorbed into the state-definition
   itself rather than layered on top.

### Why the Rebuild Must Be Isolated

- Production pin is the live champion benchmark and must not be contaminated by research changes.
- An isolated sandbox allows controlled experiments without risk to the existing system.
- Apples-to-apples comparison requires that all non-target differences are documented; any
  undocumented difference could produce false signals of improvement or harm.
- If Path B fails, the production system is unaffected and we roll back cleanly.

### Why Apples-to-Apples Comparison Is Required

The production pin `improved_frontier_phase5_fragility_guard` uses specific:
- ETF universe
- Return calculation convention
- Transaction cost model
- Holdout split
- Date index
- Timing/lag rules
- Annualization convention

If the shadow system uses different conventions (e.g., different lag, different cost model,
different holdout dates), any observed Sharpe difference could be entirely explained by the
convention difference rather than the regime engine change. This has historically been a source
of false positives in quant research.

The equivalence framework (Sprint 0.5) is designed to eliminate this risk before Sprint 1 begins.

### Open Questions for Sprint 1

1. Can the native feature panel be constructed with zero FRED data? (Yes — V3 proxy is available)
2. Do the NM sub-states (neutral_soft_landing, neutral_macro_stress, etc.) have enough
   observations to be statistically meaningful? (≥30 required; ~78 dev weeks for NM+slowdown)
3. What is the minimum transition penalty needed to prevent weekly state flip-flopping?
4. Can the existing HRP sleeve allocator be reused without changes in Sprint 5?
5. Is the 8-state design feasible, or should we start with the production 5 + 1 new NM sub-state?

---

*Further entries will be added at each sprint completion.*
