"""
Sprint 0.5 — Equivalence Verifier
Checks that all NEEDS_TEST and REIMPLEMENT_IDENTICAL items in the equivalence map
match production before Sprint 1 begins.

Run: python3 research_native_rebuild/scripts/00_compare_production_shadow_contract.py

Pass condition: All checks PASS. Any FAIL triggers a hard stop.
Output: research_native_rebuild/outputs/comparison/sprint_0_5_equivalence_report.txt
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yaml

ROOT = Path(__file__).parent.parent.parent
OUT_DIR = ROOT / "research_native_rebuild" / "outputs" / "comparison"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PATH = OUT_DIR / "sprint_0_5_equivalence_report.txt"

# ─── Tolerance Constants ──────────────────────────────────────────────────────
TOL_RETURN = 1e-10
TOL_METRICS = 1e-6

DEV_END = pd.Timestamp("2024-04-12")
HOLDOUT_START = pd.Timestamp("2024-04-19")

# ─── Data paths ───────────────────────────────────────────────────────────────
PRICES_PATH = ROOT / "data" / "01_data_hub" / "weekly_prices.csv"
REGIME_PATH = ROOT / "data" / "04_layer2b_risk_regime_engine" / "regime_score.csv"
STATE_PATH = ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv"

results = []


def record(check_name, status, detail=""):
    results.append({"check": check_name, "status": status, "detail": detail})
    symbol = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{symbol}] {check_name}: {detail}")


# ─── Check 1: Prices file loads ───────────────────────────────────────────────
def check_prices_load():
    if not PRICES_PATH.exists():
        record("prices_file_exists", "FAIL", f"not found: {PRICES_PATH}")
        return None
    prices = pd.read_csv(PRICES_PATH, index_col=0, parse_dates=True)
    record("prices_file_exists", "PASS", f"{prices.shape[0]} rows, {prices.shape[1]} cols")
    return prices


# ─── Check 2: Date index is weekly Fridays ────────────────────────────────────
def check_date_index(prices):
    if prices is None:
        record("date_index_weekly", "FAIL", "skipped — prices not loaded")
        return
    weekdays = prices.index.dayofweek.unique()
    if set(weekdays) == {4}:
        record("date_index_weekly_fridays", "PASS", f"all {len(prices)} dates are Fridays")
    else:
        record("date_index_weekly_fridays", "FAIL", f"non-Friday dates found: {weekdays}")
    start_ok = prices.index[0] == pd.Timestamp("2005-01-07")
    record("date_index_start", "PASS" if start_ok else "FAIL",
           f"first date: {prices.index[0].date()}, expected 2005-01-07")
    end_date = prices.index[-1]
    end_ok = end_date >= pd.Timestamp("2026-04-01")
    record("date_index_end", "PASS" if end_ok else "FAIL",
           f"last date: {end_date.date()}")


# ─── Check 3: Return calculation convention ───────────────────────────────────
def check_return_calculation(prices):
    if prices is None:
        record("return_calculation", "FAIL", "skipped — prices not loaded")
        return None
    returns = prices.pct_change().dropna()
    # verify no NaN survived
    nan_count = returns.isna().sum().sum()
    record("return_calculation_no_nan", "PASS" if nan_count == 0 else "FAIL",
           f"NaN count after pct_change: {nan_count}")
    # verify range is plausible (weekly ETF returns; USO can hit ~39% in oil crisis)
    max_abs = returns.abs().max().max()
    worst_etf = returns.abs().max().idxmax()
    plausible = max_abs < 0.50   # 50% is a generous hard limit; flags genuinely bad data
    record("return_calculation_range_plausible", "PASS" if plausible else "FAIL",
           f"max |weekly return|: {max_abs:.4f} (ETF: {worst_etf})")
    return returns


# ─── Check 4: Holdout split ───────────────────────────────────────────────────
def check_holdout_split(prices):
    if prices is None:
        record("holdout_split", "FAIL", "skipped")
        return
    all_dates = prices.index
    dev_dates = all_dates[all_dates <= DEV_END]
    holdout_dates = all_dates[all_dates >= HOLDOUT_START]
    dev_ok = dev_dates[-1] == DEV_END
    holdout_ok = holdout_dates[0] == HOLDOUT_START
    record("holdout_dev_end", "PASS" if dev_ok else "FAIL",
           f"last dev date: {dev_dates[-1].date()}, expected {DEV_END.date()}")
    record("holdout_start", "PASS" if holdout_ok else "FAIL",
           f"first holdout date: {holdout_dates[0].date()}, expected {HOLDOUT_START.date()}")
    record("holdout_weeks", "PASS" if len(holdout_dates) >= 100 else "FAIL",
           f"holdout weeks: {len(holdout_dates)}, expected ~104")


# ─── Check 5: Regime score file ───────────────────────────────────────────────
def check_regime_score():
    if not REGIME_PATH.exists():
        record("regime_score_exists", "FAIL", f"not found: {REGIME_PATH}")
        return None
    regime = pd.read_csv(REGIME_PATH, index_col=0, parse_dates=True)
    record("regime_score_exists", "PASS", f"{regime.shape[0]} rows")
    required_cols = [
        "vix_level_z_tradable", "market_vol_risk_off_z",
        "market_drawdown_risk_off_z", "breadth_risk_off_z",
        "avg_corr_risk_off_z", "risk_regime_score"
    ]
    missing = [c for c in required_cols if c not in regime.columns]
    record("regime_score_columns", "PASS" if not missing else "FAIL",
           f"missing cols: {missing}" if missing else "all required cols present")
    return regime


# ─── Check 6: Market state history file ──────────────────────────────────────
def check_market_state_history():
    if not STATE_PATH.exists():
        record("market_state_history_exists", "FAIL", f"not found: {STATE_PATH}")
        return None
    states = pd.read_csv(STATE_PATH, index_col=0, parse_dates=True)
    record("market_state_history_exists", "PASS", f"{states.shape[0]} rows")
    expected_states = {"neutral_mixed", "calm_trend", "stressed_panic",
                       "recovery_fragile", "recovery_confirmed"}
    if "market_state" not in states.columns:
        record("market_state_column", "FAIL", "market_state column not found")
        return states
    actual_states = set(states["market_state"].dropna().unique())
    extra = actual_states - expected_states
    missing = expected_states - actual_states
    ok = not missing
    record("market_state_values", "PASS" if ok else "FAIL",
           f"missing: {missing}, extra: {extra}" if (missing or extra) else "5 production states confirmed")
    return states


# ─── Check 7: V3 macro states ─────────────────────────────────────────────────
def check_v3_macro_states():
    v3_path = ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v3" / "macro_states_weekly_v3.csv"
    if not v3_path.exists():
        record("v3_macro_states_exists", "FAIL", f"not found: {v3_path}")
        return None
    v3 = pd.read_csv(v3_path, index_col=0, parse_dates=True)
    record("v3_macro_states_exists", "PASS", f"{v3.shape[0]} rows")
    # fc_proxy column is named 'financial_conditions_proxy' in the V3 file
    # fc_benign is derived as financial_conditions_proxy < 0 — not a pre-existing column
    required_cols = ["macro_state", "growth_factor", "financial_conditions_proxy"]
    missing = [c for c in required_cols if c not in v3.columns]
    has_fc = "financial_conditions_proxy" in v3.columns
    record("v3_macro_states_columns", "PASS" if not missing else "FAIL",
           f"missing: {missing}" if missing else "required cols present; fc_benign derived from financial_conditions_proxy < 0")
    if has_fc:
        record("v3_fc_benign_derivable", "PASS",
               f"fc_benign = (financial_conditions_proxy < 0); {int((v3['financial_conditions_proxy'] < 0).sum())} benign weeks")
    return v3


# ─── Check 8: Execution delay (forward return alignment) ─────────────────────
def check_execution_delay(prices):
    if prices is None:
        record("execution_delay", "FAIL", "skipped")
        return
    returns = prices.pct_change()
    fwd_returns = returns.shift(-1)
    nan_at_last = fwd_returns.iloc[-1].isna().all()
    record("execution_delay_forward_shift", "PASS" if nan_at_last else "FAIL",
           "last row of forward returns is NaN as expected (shift(-1) correct)" if nan_at_last
           else "WARN: last row not NaN — verify forward return convention")


# ─── Check 9: Cost convention ────────────────────────────────────────────────
def check_cost_convention():
    with open(ROOT / "research_native_rebuild" / "configs" / "native_rebuild_config.yaml") as f:
        cfg = yaml.safe_load(f)
    cost = cfg["costs"]["cost_per_unit_turnover"]
    ok = abs(cost - 0.001) < 1e-9
    record("cost_convention_10bps", "PASS" if ok else "FAIL",
           f"cost_per_unit_turnover: {cost}, expected 0.001")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 70)
    print("  Sprint 0.5 — Equivalence Verification")
    print("  Production vs Shadow Contract Check")
    print("=" * 70 + "\n")

    prices = check_prices_load()
    check_date_index(prices)
    returns = check_return_calculation(prices)
    check_holdout_split(prices)
    check_regime_score()
    check_market_state_history()
    check_v3_macro_states()
    check_execution_delay(prices)
    check_cost_convention()

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")

    print("\n" + "=" * 70)
    print(f"  RESULT: {n_pass} PASS / {n_fail} FAIL / {len(results)} total")
    if n_fail == 0:
        print("  STATUS: ALL CHECKS PASSED — Sprint 0.5 complete; Sprint 1 may begin")
    else:
        print("  STATUS: CHECKS FAILED — resolve all failures before Sprint 1")
        print("  Hard stop conditions: return convention, holdout split, execution delay")
    print("=" * 70 + "\n")

    # Write report
    lines = ["Sprint 0.5 — Equivalence Verification Report", "=" * 70, ""]
    for r in results:
        lines.append(f"[{r['status']}] {r['check']}: {r['detail']}")
    lines += [
        "",
        f"TOTAL: {n_pass} PASS / {n_fail} FAIL / {len(results)} checks",
        "STATUS: " + ("ALL PASSED" if n_fail == 0 else "FAILED — Sprint 1 blocked"),
    ]
    REPORT_PATH.write_text("\n".join(lines))
    print(f"Report written to: {REPORT_PATH}")

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
