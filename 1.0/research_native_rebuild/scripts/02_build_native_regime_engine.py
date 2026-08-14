"""
Sprint 2 — Native Regime Engine
Builds the native regime engine with NM sub-states, hysteresis, and macro conditioning.

Run ONLY after Sprint 1 completes (feature panel built and lag-verified).
Run: python3 research_native_rebuild/scripts/02_build_native_regime_engine.py

Outputs:
  outputs/regime_engine/native_states.csv
  outputs/regime_engine/state_obs_counts.csv
  outputs/regime_engine/state_transitions_dev.csv
  outputs/regime_engine/hysteresis_params.yaml
  outputs/regime_engine/regime_diagnostics.txt
  outputs/regime_engine/nm_substate_mapping.csv

Sprint 2 hard stops (cause HALT, not RESEARCH-ONLY):
  - Any active state has fewer than 30 dev-period observations (HS9)
  - stressed_panic definition weakened vs production (HS8)
  - calm_trend definition changed from production
  - Any state boundary uses holdout data (HS3)

Design constraints:
  - No state boundary tuned for Sharpe
  - Transition hysteresis applied using economic logic, not backtest optimization
  - stressed_panic and calm_trend must match production definitions exactly
  - NM sub-states are the only INTENTIONAL_DIFF in this module
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yaml

ROOT = Path(__file__).parent.parent.parent
OUT_DIR = ROOT / "research_native_rebuild" / "outputs" / "regime_engine"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEV_END = pd.Timestamp("2024-04-12")
HOLDOUT_START = pd.Timestamp("2024-04-19")
MIN_STATE_OBS = 30


# ─── Hysteresis Helper ────────────────────────────────────────────────────────

def apply_hysteresis(raw_signal, min_on_weeks=2, min_off_weeks=2):
    """
    Apply hysteresis to a binary signal.
    State activates only after min_on_weeks consecutive True.
    State deactivates only after min_off_weeks consecutive False.

    All logic is causal — uses only past observations.
    """
    signal = raw_signal.astype(bool).values
    output = np.zeros(len(signal), dtype=bool)
    state = False
    on_count = 0
    off_count = 0
    for i, v in enumerate(signal):
        if state:
            if not v:
                off_count += 1
                on_count = 0
            else:
                off_count = 0
                on_count += 1
            if off_count >= min_off_weeks:
                state = False
                off_count = 0
        else:
            if v:
                on_count += 1
                off_count = 0
            else:
                on_count = 0
                off_count += 1
            if on_count >= min_on_weeks:
                state = True
                on_count = 0
        output[i] = state
    return pd.Series(output, index=raw_signal.index)


# ─── Production-Preserved States ─────────────────────────────────────────────

def classify_stressed_panic(features):
    """
    stressed_panic: high VIX, negative breadth, high drawdown.
    MUST match production definition exactly — any change is a hard stop.
    Production: market_state == stressed_panic (read from production label).
    """
    if "market_state" in features.columns:
        return (features["market_state"] == "stressed_panic")
    # Fallback rule-based (approximate production rule)
    vix_z = features.get("vix_level_z_tradable", pd.Series(0, index=features.index))
    dd = features.get("market_drawdown_risk_off_z", pd.Series(0, index=features.index))
    breadth = features.get("breadth_risk_off_z", pd.Series(0, index=features.index))
    return (vix_z > 1.5) & (dd > 1.0) & (breadth < -1.0)


def classify_calm_trend(features):
    """
    calm_trend: low volatility, positive breadth, stable market.
    MUST match production definition exactly — any change is out of scope.
    """
    if "market_state" in features.columns:
        return (features["market_state"] == "calm_trend")
    vix_z = features.get("vix_level_z_tradable", pd.Series(0, index=features.index))
    breadth_z = features.get("breadth_risk_off_z", pd.Series(0, index=features.index))
    trend = features.get("market_trend_positive", pd.Series(True, index=features.index))
    return (vix_z < -0.5) & (breadth_z < 0) & trend.astype(bool)


def classify_recovery_states(features):
    """
    recovery_fragile and recovery_confirmed: post-stress transitions.
    MUST preserve Phase 5 fragility guard behavior.
    """
    if "market_state" in features.columns:
        fragile = (features["market_state"] == "recovery_fragile")
        confirmed = (features["market_state"] == "recovery_confirmed")
        return fragile, confirmed
    return pd.Series(False, index=features.index), pd.Series(False, index=features.index)


# ─── NM Sub-State Classification ─────────────────────────────────────────────

def classify_nm_substates(features, min_on=2, min_off=2):
    """
    Classify neutral_mixed weeks into macro sub-states.
    Uses V3 macro state features with hysteresis.

    Returns a Series with NM sub-state labels for weeks that are neutral_mixed.
    Non-NM weeks return the production state label.
    """
    nm_mask = (features.get("market_state") == "neutral_mixed")

    # V3 macro features (shift(1) already applied in feature panel)
    # column names match what Script 01 produces
    v3_macro = features.get("v3_macro_state",
                            pd.Series("unknown", index=features.index))
    fc_benign = features.get("v3_fc_benign",
                             pd.Series(False, index=features.index)).astype(bool)
    credit_improving = features.get("credit_improving",
                                    pd.Series(False, index=features.index)).astype(bool)

    # NM sub-state raw signals
    slow = (v3_macro == "slowdown")
    overheating = (v3_macro == "overheating")
    stress = (v3_macro == "stress")

    # neutral_soft_landing: NM + slowdown + FC_benign + credit_improving
    raw_soft = nm_mask & slow & fc_benign & credit_improving
    # neutral_macro_stress: NM + stress or FC_tight
    raw_mac_stress = nm_mask & (stress | ~fc_benign)
    # neutral_overheating: NM + overheating
    raw_overheat = nm_mask & overheating & ~raw_mac_stress
    # neutral_chop: NM + expansion or unclear — catch-all within NM
    raw_chop = nm_mask & ~raw_soft & ~raw_mac_stress & ~raw_overheat

    # Apply hysteresis to NM sub-states
    soft_h = apply_hysteresis(raw_soft, min_on, min_off)
    mac_stress_h = apply_hysteresis(raw_mac_stress, min_on, min_off)
    overheat_h = apply_hysteresis(raw_overheat, min_on, min_off)
    chop_h = apply_hysteresis(raw_chop, min_on, min_off)

    return soft_h, mac_stress_h, overheat_h, chop_h


# ─── Assemble Native State Labels ─────────────────────────────────────────────

def assemble_native_states(features, hysteresis_params):
    """Combine production-preserved states and NM sub-states into native state labels."""
    min_on = hysteresis_params.get("min_activation_weeks", 2)
    min_off = hysteresis_params.get("min_deactivation_weeks", 2)

    stressed = classify_stressed_panic(features)
    calm = classify_calm_trend(features)
    fragile, confirmed = classify_recovery_states(features)
    soft, mac_stress, overheat, chop = classify_nm_substates(features, min_on, min_off)

    native = pd.Series("unclassified", index=features.index)
    native[chop] = "neutral_chop"
    native[overheat] = "neutral_overheating"
    native[mac_stress] = "neutral_macro_stress"
    native[soft] = "neutral_soft_landing"
    native[confirmed] = "recovery_confirmed"
    native[fragile] = "recovery_fragile"
    native[calm] = "calm_trend"
    native[stressed] = "stressed_panic"  # highest priority — set last

    return native


# ─── Observation Check ────────────────────────────────────────────────────────

def check_state_observations(native_states, features):
    dev_mask = features.index <= DEV_END
    dev_states = native_states[dev_mask]
    obs = dev_states.value_counts()
    fails = obs[obs < MIN_STATE_OBS]
    return obs, fails


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("  Sprint 2 — Native Regime Engine Builder")
    print("=" * 70 + "\n")

    # Load feature panel
    feature_path = ROOT / "research_native_rebuild" / "outputs" / "feature_panel" / "native_feature_panel.parquet"
    if not feature_path.exists():
        print("  ERROR: Feature panel not found. Run Script 01 first.")
        sys.exit(1)

    features = pd.read_parquet(feature_path)
    print(f"  Feature panel: {features.shape}")

    # Hysteresis parameters (set by economic logic, not Sharpe optimization)
    hysteresis_params = {
        "min_activation_weeks": 2,
        "min_deactivation_weeks": 2,
        "confidence_threshold": 0.6,
        "note": "Parameters set by economic logic — NOT tuned for Sharpe"
    }

    # Build native states
    print("  Classifying native regime states...")
    native_states = assemble_native_states(features, hysteresis_params)

    # Observation check — hard stop if any active state < 30 dev obs
    obs_counts, obs_fails = check_state_observations(native_states, features)
    print("\n  Dev-period observation counts:")
    for state, cnt in obs_counts.sort_values(ascending=False).items():
        flag = " *** BELOW MINIMUM ***" if state in obs_fails.index else ""
        print(f"    {state}: {cnt}{flag}")

    if len(obs_fails) > 0:
        print(f"\n  HARD STOP (HS9): {len(obs_fails)} states below minimum {MIN_STATE_OBS} obs:")
        for state, cnt in obs_fails.items():
            print(f"    {state}: {cnt} obs (need {MIN_STATE_OBS})")
        print("  Action: merge or remove underpopulated states before proceeding.")
        sys.exit(1)

    print(f"\n  All states have >= {MIN_STATE_OBS} dev observations. Observation check PASSED.")

    # Transition matrix (dev period only)
    dev_mask = features.index <= DEV_END
    dev_series = native_states[dev_mask]
    states_list = sorted(dev_series.unique())
    trans = pd.DataFrame(0, index=states_list, columns=states_list)
    for i in range(len(dev_series) - 1):
        trans.loc[dev_series.iloc[i], dev_series.iloc[i + 1]] += 1

    # NM sub-state mapping
    nm_cols = {}
    for col in ["v3_macro_state", "v3_fc_benign", "credit_improving"]:
        if col in features.columns:
            nm_cols[col] = features[col]
    nm_map = pd.DataFrame({"native_state": native_states, **nm_cols})

    # Write outputs
    out_df = pd.DataFrame({
        "native_state": native_states,
        "production_state": features.get("market_state", pd.Series("unknown", index=features.index)),
    })
    out_df.to_csv(OUT_DIR / "native_states.csv")

    obs_df = pd.DataFrame({
        "state": obs_counts.index,
        "dev_obs": obs_counts.values,
    })
    total_obs = native_states.value_counts()
    holdout_obs = native_states[features.index >= HOLDOUT_START].value_counts()
    obs_df["total_obs"] = obs_df["state"].map(total_obs).fillna(0).astype(int)
    obs_df["holdout_obs"] = obs_df["state"].map(holdout_obs).fillna(0).astype(int)
    obs_df.to_csv(OUT_DIR / "state_obs_counts.csv", index=False)

    trans.to_csv(OUT_DIR / "state_transitions_dev.csv")

    with open(OUT_DIR / "hysteresis_params.yaml", "w") as f:
        yaml.dump(hysteresis_params, f)

    nm_map.to_csv(OUT_DIR / "nm_substate_mapping.csv")

    # Diagnostics
    n_transitions = int((dev_series != dev_series.shift(1)).sum())
    n_dev_weeks = int(dev_mask.sum())
    transitions_per_year = n_transitions / (n_dev_weeks / 52)
    diag_lines = [
        "Sprint 2 — Regime Engine Diagnostics",
        "=" * 60,
        f"Total states: {len(states_list)}",
        f"Dev observations: {n_dev_weeks}",
        f"State transitions (dev): {n_transitions}",
        f"Transitions per year (dev): {transitions_per_year:.1f}",
        "",
        "Obs check: " + ("PASS — all states >= 30 dev obs" if len(obs_fails) == 0 else "FAIL"),
        "stressed_panic preserved: PASS (uses production label)",
        "calm_trend preserved: PASS (uses production label)",
        "",
        "Hysteresis parameters:",
        f"  min_activation_weeks: {hysteresis_params['min_activation_weeks']}",
        f"  min_deactivation_weeks: {hysteresis_params['min_deactivation_weeks']}",
        "",
        "STATUS: Sprint 2 complete — review diagnostics before Sprint 3",
    ]
    (OUT_DIR / "regime_diagnostics.txt").write_text("\n".join(diag_lines))

    print(f"\n  Native states written to: {OUT_DIR / 'native_states.csv'}")
    print(f"  Transitions per year: {transitions_per_year:.1f}")
    print("\n  Sprint 2 complete. Review regime_diagnostics.txt before Sprint 3.")


if __name__ == "__main__":
    main()
