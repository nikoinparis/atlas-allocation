# Path B — Architecture Design Memo

**Date:** 2026-06-07
**Status:** Sprint 0 — Scaffold only
**Author:** Research program

---

## 1. Current Production Architecture Summary

### Data Hub (Layer 0)

| Component | Details |
| --- | --- |
| ETF universe | 35 ETFs (BIL, DBA, EEM, EFA, EWJ, GLD, HYG, IAU, IEF, IWM, QQQ, SPY, TLT, SHY, TIP, VEA, VNQ, VTV, VWO, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY, PDBC, IYR, EWJ, EWZ, ...) |
| Weekly date index | 2005-01-07 to 2026-04-10 (1110 weeks) |
| Rebalance frequency | Weekly, Friday close |
| Execution delay | 1 week (weights set at t, returns earned t→t+1) |
| Return convention | `gross[t] = w[t] @ etf_returns[t+1]` |
| Transaction costs | 10 bps per unit of half-round-trip turnover |
| Holdout split | Dev: through 2024-04-12; Holdout: 2024-04-19 onward (104 weeks) |
| FRED macro data | Empty (504 timeout, 3 sprints attempted; proxy built in V3) |
| VIX term structure | Available (VIX spot, VIX3M, VIX6M, slope, contango flag) |
| Google Trends | Available (recession, crash, inflation, bear market, fear composite) |

### Layer 1 — Alpha Signals (57 signal files)

Key signal families available:
- **Cross-sectional momentum** (`signal_xsmom.csv`): relative performance ranking
- **Time-series momentum** (`signal_tsmom.csv`): own-history momentum
- **Multi-horizon momentum** (`signal_multi_horizon_mom.csv`): 4w/13w/26w blended
- **Reversal** (`signal_reversal.csv`): short-term mean reversion
- **Quality** (`signal_quality.csv`, `signal_quality_features.csv`)
- **Carry** (`signal_carry.csv`)
- **Value** (`signal_value.csv`)
- **Residual momentum** (`signal_residual_momentum.csv`)
- **Trend quality** (`signal_trend_quality.csv`, `signal_moving_average_distance.csv`)
- **Breadth confirmation** (`signal_breadth_confirmation.csv`, `signal_bm_*`)
- **Credit/bond signals** (`signal_r2_credit_spread.csv`, `signal_r4_pair_hyg_lqd.csv`)
- **Dollar strength** (`signal_bm_dollar_strength_*.csv`, `signal_r2_dollar_strength.csv`)
- **VIX / financial conditions** (`signal_r2_vix_term_structure.csv`, `signal_r2_financial_conditions.csv`)
- **Commodity regime** (`signal_r2_commodity_regime.csv`)
- **Cross-asset divergence** (`signal_r2_cross_asset_divergence.csv`)
- **Yield curve** (`signal_r2_yield_curve.csv`, `signal_r2_yield_curve.csv`)
- **Betting against beta** (`signal_bab.csv`)
- **State-conditional IC** (`signal_state_conditional_ic.csv`)
- **Volume divergence** (`signal_r2_volume_divergence.csv`)
- **Eligibility matrix** (`signal_eligibility_matrix.csv`)

### Layer 2A — Strategy Sleeves

The current production system uses 6 active sleeves:

| Sleeve | Role | Type |
| --- | --- | --- |
| `dual_momentum_topn` | Offensive, top-N dual momentum | Tactical |
| `cta_trend_long_only` | Offensive, trend-following long-only | Trend |
| `composite_selective_signals` | Offensive, multi-signal composite | Multi-signal |
| `composite_regime_offense_component` | Offensive, regime-conditioned | Regime-aware |
| `composite_regime_defense_component` | Defensive, regime-conditioned | Defensive |
| `taa_10m_sma` | Structural, 10-month SMA timing | SMA timing |
| `cash::BIL` | Cash position | Residual |

### Layer 2B — Regime Engine

The production regime engine classifies weekly market conditions into 5 states:

| State | Count | Pct | Role |
| --- | --- | --- | --- |
| neutral_mixed | 493 | 44.4% | Default; tactical offense/defense balance |
| calm_trend | 295 | 26.6% | Bull; max offense; known alpha gap |
| stressed_panic | 229 | 20.6% | Bear; max defense; critical protection period |
| recovery_fragile | 49 | 4.4% | Early recovery; cautious re-risking |
| recovery_confirmed | 44 | 4.0% | Confirmed recovery; active re-risking |

**Production regime engine inputs** (from `regime_score.csv`):
- `market_vol_risk_off_z`: VIX-derived volatility z-score
- `market_drawdown_risk_off_z`: SPY drawdown z-score
- `breadth_risk_off_z`: Breadth indicator z-score
- `avg_corr_risk_off_z`: Cross-asset correlation z-score
- `macro_risk_score_tradable`: FRED/macro risk composite (1-week lagged)
- `vix_level_z_tradable`: VIX level z-score (1-week lagged)
- `vix_slope_risk_off_z_tradable`: VIX slope (contango/backwardation) z-score
- `google_fear_z_tradable`: Google Trends fear composite z-score
- `risk_regime_score`: composite of above
- `risk_state`: binary high/low risk
- `signal_environment`: regime context for signal selection

Additional state features in `market_state_history.csv`:
- `market_drawdown`, `market_trend_positive`
- `breadth_sma_43`, `breadth_26w_mom`, `breadth_13w_mom`, `breadth_change_4w`
- `canary_breadth_default`, `canary_breadth_pair`
- `recent_stress_26w`, `avg_corr_risk_off_z`, `google_fear_z_tradable`
- `transition_persistence_prob`, `transition_good_state_prob`, `transition_non_stress_prob`

The regime engine uses a rule-based classifier, not a learned model. States transition when
composite scores cross thresholds. The fragility guard (Phase 5) caps offensive re-risking
immediately after stressed_panic episodes.

**Known weakness**: The `neutral_mixed` bucket is a catch-all for ~44% of weeks. It is
heterogeneous — it contains weeks with very different macro sub-regimes (NM+slowdown with
FC_benign shows 2× higher Sharpe than NM+expansion), but the regime engine treats them
uniformly. This is the binding constraint identified in Steps 2, 2B, and 2C.

### Layer 3 — Portfolio Construction

- Sleeve-based HRP/inverse-vol allocator
- State-specific risk multipliers and offense/defense budgets
- Phase 5 fragility guard: caps re-risking after stressed_panic
- BIL as cash proxy and defensive buffer
- Long-only, no leverage, weights sum to 1
- 10 bps per unit half-round-trip transaction cost

### Current Production Pin

**`improved_frontier_phase5_fragility_guard`**
- Full-history Sharpe: 0.9542
- Annual return: 7.18%
- Max drawdown: -11.60%
- Holdout Sharpe (104 weeks): 2.0479
- Phase 10A gate evaluation: all gates passed, human authorized

---

## 2. Known Bottlenecks

| Bottleneck | Evidence | Priority |
| --- | --- | --- |
| calm_trend alpha gap | calm_trend (26.6% of weeks) contributes less than it should; primary frontier constraint | HIGH |
| neutral_mixed heterogeneity | NM contains 4 distinct macro sub-regimes; treated uniformly | HIGH |
| FRED macro data blocked | macro_weekly.csv is empty; NFCI unavailable | MEDIUM |
| PIT stock breadth | Norgate data unavailable (~$100/mo) | LOW (external) |
| Overlay turnover ceiling | NM has 8.9 transitions/yr; any overlay fails G6 | RESOLVED (closed) |

---

## 3. Exhausted Branches

The following research branches are **closed** — they have been tested extensively and either
failed gates or are structurally blocked:

| Branch | Sprints | Result | Why Closed |
| --- | --- | --- | --- |
| FRED macro regime (V1, V2) | V1/V2 sprints | RESEARCH-ONLY | NFCI 504 timeout |
| Weekly ETF tilt overlay | Step 2 | RESEARCH-ONLY | G1 fail, G6 fail |
| Persistent Layer 2B modifier | Step 2B | RESEARCH-ONLY | G6 fail (structural) |
| Near-zero-turnover calibration | Step 2C | RESEARCH-ONLY | G6 fail (structural) |
| ML meta-allocators | Phases N–V | RESEARCH-ONLY | Overfit, no OOS benefit |
| Holdings blends | Phases U–AA | RESEARCH-ONLY | No incremental gain |
| Allocator families | Phases A–M | RESEARCH-ONLY | Exhausted frontier |

---

## 4. Why the Macro Overlay Path is Closed

Steps 2, 2B, and 2C proved definitively that **post-hoc overlay mechanisms cannot profitably
implement the V3 macro/credit signal** given this portfolio's cost structure:

- The V3 NM+slowdown+FC_benign signal is real (G1 passes in Steps 2B and 2C)
- Signal E_4wk (NM+slowdown+FC_benign+credit_improving, 4-week rolling) passes holdout in both
  Step 2B (+0.041) and Step 2C (+0.016) — consistent out-of-sample evidence
- The turnover gate (≤0.03/yr) cannot be cleared because:
  - NM has 8.9 transitions/year
  - Each transition requires ~intensity/2 turnover per round-trip
  - Even at 1% intensity: extra turnover ≈ 0.045/yr (exceeds gate)
  - Quarterly frozen (lowest turnover) = 0.057/yr minimum (still 1.9× gate)
- The 2x-cost sensitivity test destroys the improvement in all three sprints

**Conclusion**: The signal must be integrated natively, not overlaid.

---

## 5. Why Path B Must Be Isolated

1. **No contamination of production**: production pin is the live benchmark; modifying it during
   research would invalidate the comparison
2. **Clean comparison baseline**: all non-target differences must be documented; any undocumented
   difference could masquerade as an improvement
3. **Safe failure mode**: if Path B fails, production is unaffected
4. **Controlled scope**: Path B is allowed to change exactly 6 things (native regime engine,
   macro conditioning, state persistence, signal weighting, risk budgets, turnover-aware
   transitions); everything else must match production

---

## 6. Path B Native Architecture

### Module A — Native Feature Panel

The native feature panel consolidates all available causal inputs into a single 1-week-lagged
feature matrix:

**Tier 1: Market structure (already in production)**
- VIX level z-score (1-week lagged tradable)
- VIX slope (contango/backwardation) z-score
- SPY market drawdown
- Market trend positive indicator
- Breadth: SMA43, 26w/13w/4w momentum, change
- Canary breadth (default and pair)
- Average cross-asset correlation z-score
- Google fear composite z-score
- Recent stress 26w indicator
- Transition probability features (persistence, good-state, non-stress)

**Tier 2: Macro/credit (V3 additions)**
- V3 growth_factor (PCA of PAYEMS, INDPRO, RSAFS, UNRATE, ICSA)
- V3 inflation_policy_factor
- V3 financial_conditions_proxy (VIX + HYG/LQD + SPY_drawdown + avg_corr)
- V3 macro_state (expansion/slowdown/overheating/stress)
- HYG/LQD credit trend (4w momentum)
- Credit improving / not-worsening binary
- FC_benign binary (fc_proxy < 0)
- Signal E_4wk (NM+slowdown+FC_benign+credit_improving, 4-week rolling)

**Tier 3: VIX term structure (direct)**
- VIX contango flag
- VIX slope 1m-3m
- VIX slope 1m-6m
- VIX stress_flag

**Important**: All features applied with 1-week causal lag. No feature computed using
information that would not be available at the close of the signal date.

### Module B — Native Regime Engine

The native regime engine is the primary innovation of Path B. It must:
- Produce at most 8 distinct states (enough observations in each)
- Use transition penalties / hysteresis to prevent weekly flip-flopping
- Encode macro/credit distinction natively within the NM sub-state
- Never use future returns to define state boundaries
- Never tune states directly for Sharpe

**Candidate state design**:

```
Tier 1 (preserved from production):
  stressed_panic         — high-risk, max defense, fragility protection
  recovery_fragile       — post-stress, cautious re-risking
  recovery_confirmed     — confirmed recovery, active re-risking
  calm_trend             — low-volatility bull market, max offense

Tier 2 (NM decomposition — native macro conditioning):
  neutral_soft_landing   — NM + slowdown + FC_benign (archived Signal E_4wk)
  neutral_macro_stress   — NM + stress or FC_tight
  neutral_overheating    — NM + overheating or inflation elevated
  neutral_chop           — NM + expansion or unclear macro
```

**Minimum observation requirement**: ≥ 30 dev observations per state. States with fewer than
30 observations must be merged.

**Transition rule design (to be formalized in Sprint 2)**:
- Require ≥ N consecutive weeks before state activation (hysteresis)
- Require ≥ M consecutive weeks before state deactivation
- Use probability scores rather than hard thresholds where possible
- Include regime score confidence as a continuous weight input

### Module C — Native Signal Weighting

- Compute walk-forward information coefficients (IC) for each signal in each regime state
- Apply shrinkage (toward equal weighting) to prevent overfitting IC estimates
- Use only dev-period data; no holdout look-ahead
- Minimum IC window: 52 weeks of state observations
- Signals with fewer than 30 dev observations in a state: use cross-state average IC

### Module D — Native Risk Budgets

State-specific parameters (to be calibrated in Sprint 4):
- `offense_budget`: maximum fraction of portfolio in offensive ETFs
- `defense_floor`: minimum fraction in defensive/BIL
- `fragility_cap`: cap on re-risking speed post-stress
- `risk_multiplier`: global risk scale within state
- `turnover_penalty`: implicit cost per additional rebalance within state

**Hard constraints** (must be preserved from production):
- stressed_panic: offense_budget ≤ 0.30, defense_floor ≥ 0.40
- recovery_fragile: no leverage, max re-risking speed limited
- No hidden leverage (weights always sum to 1, all ≥ 0)
- BIL must be available as cash buffer in all states
- Max single-ETF weight: 0.35

### Module E — Native Portfolio Construction

Start with the existing sleeve-based HRP/inverse-vol allocator, not a new optimizer. The native
rebuild changes the REGIME ENGINE and RISK BUDGETS, not the portfolio construction math. This is
critical for isolating what changed.

Only if sleeve-level changes are needed (Sprint 5): document them explicitly as intentional
differences vs production.

---

## 7. Design Principles and Constraints

1. **Causal purity**: All features and signals must be strictly 1-week lagged. No exceptions.
2. **Out-of-sample discipline**: Dev period only for parameter discovery. Holdout is sealed.
3. **Isolation**: Shadow writes only to `research_native_rebuild/outputs/`. Production untouched.
4. **Equivalence first**: Sprint 0.5 verifies all non-target components match before Sprint 1.
5. **No Sharpe optimization**: Native regime state boundaries are NOT tuned for Sharpe.
6. **Gate discipline**: Production pin remains champion until Sprint 6 gates are passed and
   human authorization is granted.
7. **Minimum observations**: No state with fewer than 30 dev observations is valid.
8. **Turnover budget**: Target annual turnover increase ≤ 0.03 vs production (the gate that
   closed the overlay path must be respected in the native rebuild too).

---

## 8. Known Risks

| Risk | Mitigation |
| --- | --- |
| NM sub-states may have too few observations | Sprint 2 checks; merge if needed |
| Macro state definitions may change with new data | V3 definitions are frozen as research features |
| New regime engine may change ALL state behaviors, not just NM | Use production as hard baseline; check every state metric |
| Signal weighting IC may be noisy / spurious | Shrinkage to equal weight; minimum obs requirement |
| The 8-state design adds complexity without benefit | Start with 6 states (production 5 + 1 new NM sub-state) |
| FRED macro remains blocked | Use V3 proxy only (VIX+HYG/LQD+SPY_drawdown+avg_corr) |
| Holdout period is uniformly "slowdown" (V3) | Holdout test is still valid; just interprets one macro state |

---

*Sprint 0 — design memo only. No performance claims.*
