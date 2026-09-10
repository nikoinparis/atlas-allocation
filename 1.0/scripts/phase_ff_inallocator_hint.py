"""Phase FF — In-allocator integration of Phase CC's defensive_overlay_hint.

Unlike Phase DD (post-hoc ETF-level tilt) and Phase EE (post-hoc sleeve-level
rotation), Phase FF integrates the hint INSIDE production's own construction
path. Concretely, two new entries are added to the version_specs list in
scripts/build_improvement_artifacts.py:

  - improved_phaseff_hint_inallocator_light          (state_tilt='dynamic_risk_budget_phaseff_light')
  - improved_phaseff_hint_inallocator_state_gated    (state_tilt='dynamic_risk_budget_phaseff_state_gated')

The new tilt modes scale offensive sleeves by an additional 0.95 on Phase CC
gate weeks, BEFORE production's per-sleeve cap and the lighter_both overlay
run. The cost pipeline, overlay machinery, regime_confidence_boost meta
layer, beta participation overlay, and net-return computation are all the
SAME as production. Production tilt mode 'dynamic_risk_budget' is unchanged.

This driver:
  1. Runs build_improvement_artifacts.py as a subprocess with the
     BUILD_VERSION_NAMES env var set so only the two Phase FF candidates
     plus production (for re-comparison parity) are built.
  2. Reads back the saved portfolio_version_returns/weights/sleeve_weights
     files (which now come out of the same pipeline as production).
  3. Computes Phase FF candidate metrics + state breakdown vs production.
  4. Applies the 7-gate selection rule including the new
     'must not underperform in neutral_deteriorating' gate.
  5. Saves phase_ff_*.csv outputs and prints the verdict.

Usage:
    python scripts/phase_ff_inallocator_hint.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
FF1_NAME = "improved_phaseff_hint_inallocator_light"
FF2_NAME = "improved_phaseff_hint_inallocator_state_gated"
PHASE_FF_CANDIDATES = [FF1_NAME, FF2_NAME]


def run_production_path_for_phaseff(rebuild_production: bool = True) -> None:
    """Run scripts/build_improvement_artifacts.py with BUILD_VERSION_NAMES
    set so it produces Phase FF candidates (and optionally rebuilds
    production with the same up-to-date pipeline for parity)."""
    targets = list(PHASE_FF_CANDIDATES)
    if rebuild_production:
        targets.append(PRODUCTION)
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    print(f"Invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=1800)
    print("--- subprocess stdout (last 60 lines) ---")
    for line in (res.stdout or "").splitlines()[-60:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 60 lines) ---")
        for line in (res.stderr or "").splitlines()[-60:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def load_refined_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history_refined.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def state_breakdown(net: pd.Series, prod_net: pd.Series, refined: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("ff"), prod_net.rename("prod")], axis=1).join(
        refined[["market_state", "refined_state"]], how="inner"
    ).dropna()
    rows = []
    for col in ["market_state", "refined_state"]:
        for s, sub in df.groupby(col):
            rows.append({
                "state_kind": col,
                "state": s,
                "n_weeks": int(len(sub)),
                "ff_mean_wkly": float(sub["ff"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "delta_mean_wkly": float(sub["ff"].mean() - sub["prod"].mean()),
                "ff_minus_prod_cumulative": float(((1 + sub["ff"]).prod() - 1) - ((1 + sub["prod"]).prod() - 1)),
            })
    return pd.DataFrame(rows)


def headline(name: str, weekly: pd.Series, weights: pd.DataFrame | None) -> dict:
    full_m = roc.metric_block(weekly)
    hold_m = roc.metric_block(weekly.tail(roc.HOLDOUT_WEEKS))
    out = {
        "name": name,
        "full_ann_return": full_m["ann_return"],
        "full_ann_vol": full_m["ann_vol"],
        "full_sharpe": full_m["sharpe"],
        "full_max_drawdown": full_m["max_drawdown"],
        "full_cvar_5": full_m["cvar_5"],
        "full_calmar": full_m["calmar"],
        "holdout_ann_return": hold_m["ann_return"],
        "holdout_sharpe": hold_m["sharpe"],
        "holdout_max_drawdown": hold_m["max_drawdown"],
    }
    if weights is not None:
        out["avg_BIL"] = float(weights["BIL"].mean()) if "BIL" in weights.columns else float("nan")
        out["avg_SPY"] = float(weights["SPY"].mean()) if "SPY" in weights.columns else float("nan")
        out["max_etf_weight"] = float(weights.max(axis=1).max())
        t = weights.diff().abs().sum(axis=1).fillna(0.0)
        out["avg_turnover"] = float(t.mean())
    return out


def select_best(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_FF_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    rows = []
    for _, r in cands.iterrows():
        name = r["name"]
        ann_drag_pp = (prod["full_ann_return"] - r["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100
        det_row = state_df[(state_df["candidate"] == name) &
                           (state_df["state_kind"] == "refined_state") &
                           (state_df["state"] == "neutral_deteriorating")]
        det_delta_wkly = float(det_row["delta_mean_wkly"].iloc[0]) if not det_row.empty else float("nan")
        cond_drag = ann_drag_pp <= 0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = bil_inc_pp <= 5.0
        cond_det = (not np.isnan(det_delta_wkly)) and det_delta_wkly >= 0
        passes = all([cond_drag, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_bil, cond_det])
        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({ann_drag_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"bil_inc>5pp ({bil_inc_pp:+.2f}pp)" if not cond_bil else "",
            f"underperforms in neutral_deteriorating (Δ={det_delta_wkly:+.6f}/wk)" if not cond_det else "",
        ])) or "none"
        rows.append({
            "name": name,
            "ann_drag_pp": ann_drag_pp,
            "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp_pp,
            "cvar_imp_pp": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio,
            "bil_inc_pp": bil_inc_pp,
            "deteriorating_state_delta_wkly": det_delta_wkly,
            "passes_all_gates": passes,
            "fail_reasons": fail,
        })
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        best = passing.sort_values(["sharpe_imp", "ann_drag_pp"], ascending=[False, True]).iloc[0]
        rationale = (f"Selected {best['name']}: passes all 7 gates including "
                     f"`must not underperform in neutral_deteriorating` "
                     f"(Δ={best['deteriorating_state_delta_wkly']:+.6f}/wk).")
        return best["name"], rationale, decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp", "ann_drag_pp"], ascending=[False, True]).iloc[0]
    rationale = f"NO Phase FF candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}."
    return "", rationale, decision.to_dict("records")


def main():
    # Step 1: invoke production construction path with the new Phase FF version specs
    if "--no-rebuild" in sys.argv:
        print("--no-rebuild: skipping build_improvement_artifacts.py invocation; using existing files.")
    else:
        run_production_path_for_phaseff(rebuild_production=True)

    # Step 2: load Phase FF candidates + production
    refined = load_refined_state()
    summaries = []
    state_rows = []

    for name in PHASE_FF_CANDIDATES + [PRODUCTION, SHADOW]:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            print(f"WARNING: {name} returns file missing — skipping")
            continue
        w = roc.load_portfolio_weights(name)
        net = ret["net_return"].dropna()
        h = headline(name, net, w)
        if "avg_turnover" not in h and "turnover" in ret.columns:
            h["avg_turnover"] = float(ret["turnover"].mean())
        summaries.append(h)

    summary = pd.DataFrame(summaries)
    summary.to_csv(roc.LAYER3_DIR / "phase_ff_candidate_metrics_full.csv", index=False)

    # State breakdown for Phase FF candidates vs production
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns file is missing — cannot compute state breakdown")
    prod_net = prod_ret["net_return"]
    for name in PHASE_FF_CANDIDATES:
        cret = roc.load_portfolio_returns(name)
        if cret is None:
            continue
        sb = state_breakdown(cret["net_return"], prod_net, refined)
        sb["candidate"] = name
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    if not state_df.empty:
        state_df.to_csv(roc.LAYER3_DIR / "phase_ff_state_summary.csv", index=False)

    # Selection
    best, rationale, decision_records = select_best(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + decision_records).to_csv(
        roc.LAYER3_DIR / "phase_ff_selection_table.csv", index=False)

    # Print
    print("\n=== Phase FF candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    if not state_df.empty:
        print("\n=== Phase FF state-by-state (refined_state) ===")
        view = state_df[state_df["state_kind"] == "refined_state"][[
            "candidate", "state", "n_weeks", "delta_mean_wkly", "ff_minus_prod_cumulative"]]
        print(view.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase FF — In-allocator integration of Phase CC's defensive_overlay_hint",
        "candidates": PHASE_FF_CANDIDATES,
        "integration_point": "scripts/build_improvement_artifacts.py — apply_state_conditioned_tilt() new branches 'dynamic_risk_budget_phaseff_light' and 'dynamic_risk_budget_phaseff_state_gated'; tilt fires BEFORE per-sleeve cap and lighter_both overlay, preserving production's cost / overlay / cap pipeline",
        "tilt_mechanic": "On gate weeks, scale offensive sleeves by an additional 0.95 multiplier (5pp scale-down). Production cap, lighter_both overlay, regime_confidence_boost meta layer, and beta participation overlay all run unchanged.",
        "selection_rule": {
            "ann_ret_drag_max_pp": 0.30,
            "sharpe_improvement_min": 0.005,
            "mdd_worsening_max_pp": 0.5,
            "cvar_worsening_max_pp": 0.05,
            "turnover_ratio_max_vs_prod": 1.10,
            "bil_increase_max_pp": 5.0,
            "neutral_deteriorating_state_must_not_underperform": True,
        },
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_ff_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase FF artifacts.")
    return best


if __name__ == "__main__":
    main()
