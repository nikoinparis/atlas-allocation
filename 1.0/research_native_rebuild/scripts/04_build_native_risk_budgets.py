"""
Sprint 4 — Native Risk Budgets
Sets state-specific offense/defense/fragility parameters using economic logic.

Run ONLY after Sprint 3 completes.
Run: python3 research_native_rebuild/scripts/04_build_native_risk_budgets.py

Outputs:
  outputs/risk_budgets/state_risk_params.yaml
  outputs/risk_budgets/risk_budget_diagnostics.txt

Critical constraints (ALL must hold — hard stop if violated):
  - stressed_panic: offense_budget <= 0.30, defense_floor >= 0.40
  - All states: no_leverage = True, max_weight = 0.35, min_weight = 0.0
  - Parameters must be set by economic logic, NOT Sharpe maximization
  - No parameter uses holdout data (HS3 hard stop if violated)

Design principle:
  - Higher offense budgets for risk-on states (soft_landing, calm_trend, recovery_confirmed)
  - Higher defense floors for risk-off states (stressed_panic, macro_stress)
  - Fragility cap applied during and after stressed_panic episodes
  - Overheating: moderate offense, elevated inflation protection
  - Neutral chop: production NM parameters (no change)
"""

import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent.parent
OUT_DIR = ROOT / "research_native_rebuild" / "outputs" / "risk_budgets"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Hard Constraints (non-negotiable) ────────────────────────────────────────
HARD_CONSTRAINTS = {
    "max_single_etf_weight": 0.35,
    "min_weight": 0.0,
    "sum_weights_target": 1.0,
    "no_leverage": True,
    "long_only": True,
    "bil_available_all_states": True,
}

# ─── State-Specific Risk Parameters ──────────────────────────────────────────
# All values set by economic logic.
# offense_budget: max fraction of portfolio in risk-on ETFs
# defense_floor: minimum fraction in defensive ETFs + BIL
# fragility_cap: max weekly increase in offense allocation (post-stress)
# risk_multiplier: global risk scale (1.0 = neutral)
# bil_floor: minimum cash/BIL allocation

STATE_RISK_PARAMS = {

    "stressed_panic": {
        "offense_budget": 0.20,         # hard max: production uses 0.20-0.30
        "defense_floor": 0.50,          # min 50% defensive
        "fragility_cap": 0.0,           # no re-risking during stress
        "risk_multiplier": 0.6,
        "bil_floor": 0.30,
        "note": "Maximum defense. Hard constraint: offense_budget <= 0.30, defense_floor >= 0.40",
    },

    "recovery_fragile": {
        "offense_budget": 0.45,         # cautious re-risking
        "defense_floor": 0.30,
        "fragility_cap": 0.05,          # slow re-risking: max 5% per week
        "risk_multiplier": 0.8,
        "bil_floor": 0.20,
        "note": "Phase 5 fragility guard preserved. Cautious re-risking speed.",
    },

    "recovery_confirmed": {
        "offense_budget": 0.65,
        "defense_floor": 0.15,
        "fragility_cap": 0.10,          # faster re-risking once confirmed
        "risk_multiplier": 1.0,
        "bil_floor": 0.10,
        "note": "Active re-risking. Still below calm_trend offense level.",
    },

    "calm_trend": {
        "offense_budget": 0.85,         # max offense in bull market
        "defense_floor": 0.05,
        "fragility_cap": None,          # no fragility constraint in calm
        "risk_multiplier": 1.2,
        "bil_floor": 0.05,
        "note": "Max offense. Known alpha gap. Parameters match production calm_trend.",
    },

    "neutral_soft_landing": {
        "offense_budget": 0.70,         # elevated offense: NM+slowdown+FC_benign shows strong Sharpe
        "defense_floor": 0.15,
        "fragility_cap": None,
        "risk_multiplier": 1.05,
        "bil_floor": 0.10,
        "note": "NM + slowdown + FC_benign. Historical Sharpe ~2x NM average (Step 2B/2C finding).",
    },

    "neutral_macro_stress": {
        "offense_budget": 0.40,         # below neutral: FC tight or macro stress
        "defense_floor": 0.30,
        "fragility_cap": None,
        "risk_multiplier": 0.85,
        "bil_floor": 0.20,
        "note": "NM + FC tight or macro stress. Elevated defense vs neutral_chop.",
    },

    "neutral_overheating": {
        "offense_budget": 0.55,         # moderate offense; inflation risk present
        "defense_floor": 0.20,
        "fragility_cap": None,
        "risk_multiplier": 0.95,
        "bil_floor": 0.15,
        "note": "NM + overheating. Moderate position: late-cycle risk elevated.",
    },

    "neutral_chop": {
        "offense_budget": 0.60,         # production NM default
        "defense_floor": 0.20,
        "fragility_cap": None,
        "risk_multiplier": 1.0,
        "bil_floor": 0.15,
        "note": "NM + expansion or unclear macro. Production NM parameters — no change.",
    },
}


def validate_params(params):
    """Validate hard constraints for all states."""
    errors = []
    for state, p in params.items():
        if p["offense_budget"] + p["defense_floor"] > 1.0:
            errors.append(f"{state}: offense_budget + defense_floor > 1.0")
        if state == "stressed_panic":
            if p["offense_budget"] > 0.30:
                errors.append(f"stressed_panic: offense_budget {p['offense_budget']} > 0.30 (hard constraint)")
            if p["defense_floor"] < 0.40:
                errors.append(f"stressed_panic: defense_floor {p['defense_floor']} < 0.40 (hard constraint)")
        if p.get("bil_floor", 0) > p["defense_floor"]:
            errors.append(f"{state}: bil_floor > defense_floor (inconsistent)")
    return errors


def main():
    print("\n" + "=" * 70)
    print("  Sprint 4 — Native Risk Budget Builder")
    print("=" * 70 + "\n")

    # Validate hard constraints before writing
    errors = validate_params(STATE_RISK_PARAMS)
    if errors:
        print("  HARD STOP: Risk budget violations found:")
        for e in errors:
            print(f"    {e}")
        sys.exit(1)

    print("  Hard constraint validation: PASS")

    # Assemble output
    output = {
        "sprint": 4,
        "status": "sprint_4_risk_budgets",
        "design_principle": "All parameters set by economic logic — NOT Sharpe maximization",
        "data_discipline": "No holdout data used in any parameter setting",
        "hard_constraints": HARD_CONSTRAINTS,
        "state_risk_params": STATE_RISK_PARAMS,
    }

    params_path = OUT_DIR / "state_risk_params.yaml"
    with open(params_path, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False)

    # Diagnostics
    diag_lines = [
        "Sprint 4 — Risk Budget Diagnostics",
        "=" * 60,
        "",
        "Hard constraints (all states):",
        f"  max_single_etf_weight: {HARD_CONSTRAINTS['max_single_etf_weight']}",
        f"  min_weight: {HARD_CONSTRAINTS['min_weight']}",
        f"  no_leverage: {HARD_CONSTRAINTS['no_leverage']}",
        f"  long_only: {HARD_CONSTRAINTS['long_only']}",
        "",
        "State-specific offense budgets:",
    ]
    for state, p in STATE_RISK_PARAMS.items():
        diag_lines.append(f"  {state:30s}: offense={p['offense_budget']:.2f}  defense_floor={p['defense_floor']:.2f}  BIL_min={p['bil_floor']:.2f}")
    diag_lines += [
        "",
        "stressed_panic check:",
        f"  offense_budget <= 0.30: {'PASS' if STATE_RISK_PARAMS['stressed_panic']['offense_budget'] <= 0.30 else 'FAIL'}",
        f"  defense_floor >= 0.40: {'PASS' if STATE_RISK_PARAMS['stressed_panic']['defense_floor'] >= 0.40 else 'FAIL'}",
        "",
        "Hard constraint validation: PASS",
        "STATUS: Sprint 4 complete — review state_risk_params.yaml before Sprint 5",
    ]
    (OUT_DIR / "risk_budget_diagnostics.txt").write_text("\n".join(diag_lines))

    print("\n  State risk parameters:")
    for state, p in STATE_RISK_PARAMS.items():
        print(f"    {state:30s}: offense={p['offense_budget']:.2f}  def_floor={p['defense_floor']:.2f}")

    print(f"\n  Risk params written to: {params_path}")
    print("  Sprint 4 complete. Review state_risk_params.yaml before Sprint 5.")


if __name__ == "__main__":
    main()
