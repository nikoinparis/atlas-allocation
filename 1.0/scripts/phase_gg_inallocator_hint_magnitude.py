"""Phase GG — Magnitude test for Phase CC hint integration. LAST test in
the Phase CC consumption branch.

Identical pipeline to Phase FF (in-allocator integration via
build_improvement_artifacts.py); the only difference is the
offensive-sleeve scale-down magnitude:

  - improved_phasegg_hint_inallocator_10  → 0.90 multiplier (10pp scale-down)
  - improved_phasegg_hint_inallocator_15  → 0.85 multiplier (15pp scale-down)

Gate (same as Phase FF light): defensive_overlay_hint == +1 AND market_state
NOT IN {stressed_panic, recovery_fragile}. On the current sample this
collapses to exactly the 171 `neutral_deteriorating` weeks.

If neither GG1 nor GG2 improves Sharpe AND neutral_deteriorating delta vs
production, the Phase CC hint-consumption branch is RETIRED per spec.
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
GG1_NAME = "improved_phasegg_hint_inallocator_10"
GG2_NAME = "improved_phasegg_hint_inallocator_15"
PHASE_GG_CANDIDATES = [GG1_NAME, GG2_NAME]


def run_production_path(rebuild_production: bool = True) -> None:
    targets = list(PHASE_GG_CANDIDATES)
    if rebuild_production:
        targets.append(PRODUCTION)
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    print(f"Invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=1800)
    print("--- subprocess stdout (last 40 lines) ---")
    for line in (res.stdout or "").splitlines()[-40:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 40 lines) ---")
        for line in (res.stderr or "").splitlines()[-40:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def load_refined_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history_refined.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def state_breakdown(net: pd.Series, prod_net: pd.Series, refined: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("gg"), prod_net.rename("prod")], axis=1).join(
        refined[["market_state", "refined_state"]], how="inner"
    ).dropna()
    rows = []
    for col in ["market_state", "refined_state"]:
        for s, sub in df.groupby(col):
            rows.append({
                "state_kind": col,
                "state": s,
                "n_weeks": int(len(sub)),
                "gg_mean_wkly": float(sub["gg"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "delta_mean_wkly": float(sub["gg"].mean() - sub["prod"].mean()),
                "gg_minus_prod_cumulative": float(((1 + sub["gg"]).prod() - 1) - ((1 + sub["prod"]).prod() - 1)),
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
    cands = summary[summary["name"].isin(PHASE_GG_CANDIDATES)].copy()
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
    rationale = f"NO Phase GG candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}."
    return "", rationale, decision.to_dict("records")


def main():
    if "--no-rebuild" not in sys.argv:
        run_production_path(rebuild_production=True)
    else:
        print("--no-rebuild: using existing files")

    refined = load_refined_state()
    summaries = []
    state_rows = []

    for name in PHASE_GG_CANDIDATES + [PRODUCTION, SHADOW]:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            print(f"WARNING: {name} returns missing — skipping")
            continue
        w = roc.load_portfolio_weights(name)
        net = ret["net_return"].dropna()
        h = headline(name, net, w)
        if "avg_turnover" not in h and "turnover" in ret.columns:
            h["avg_turnover"] = float(ret["turnover"].mean())
        summaries.append(h)

    summary = pd.DataFrame(summaries)
    summary.to_csv(roc.LAYER3_DIR / "phase_gg_candidate_metrics_full.csv", index=False)

    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns missing")
    prod_net = prod_ret["net_return"]
    for name in PHASE_GG_CANDIDATES:
        cret = roc.load_portfolio_returns(name)
        if cret is None: continue
        sb = state_breakdown(cret["net_return"], prod_net, refined)
        sb["candidate"] = name
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    if not state_df.empty:
        state_df.to_csv(roc.LAYER3_DIR / "phase_gg_state_summary.csv", index=False)

    best, rationale, decision_records = select_best(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + decision_records).to_csv(
        roc.LAYER3_DIR / "phase_gg_selection_table.csv", index=False)

    # Final retire-or-continue decision
    branch_should_retire = True
    for r in decision_records:
        if r["sharpe_imp"] >= 0.005 and r["deteriorating_state_delta_wkly"] >= 0:
            branch_should_retire = False
            break
    branch_decision = (
        "RETIRE Phase CC hint-consumption branch — neither 10pp nor 15pp magnitude improves Sharpe AND neutral_deteriorating delta. "
        "Recommend returning to a different improvement path."
        if branch_should_retire
        else "CONTINUE Phase CC hint-consumption branch — at least one magnitude improves both Sharpe and the neutral_deteriorating delta."
    )

    print("\n=== Phase GG candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    if not state_df.empty:
        print("\n=== Phase GG state-by-state (refined_state) ===")
        view = state_df[state_df["state_kind"] == "refined_state"][[
            "candidate", "state", "n_weeks", "delta_mean_wkly", "gg_minus_prod_cumulative"]]
        print(view.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    print(f"\n{rationale}")
    print(f"\nBranch decision: {branch_decision}")

    protocol = {
        "phase": "Phase GG — Magnitude test for Phase CC hint integration (last test in branch)",
        "candidates": PHASE_GG_CANDIDATES,
        "magnitudes": {GG1_NAME: 0.10, GG2_NAME: 0.15},
        "gate": "defensive_overlay_hint == +1 AND market_state NOT IN {stressed_panic, recovery_fragile}",
        "integration_point": "scripts/build_improvement_artifacts.py — apply_state_conditioned_tilt() new branches 'dynamic_risk_budget_phasegg_10' and 'dynamic_risk_budget_phasegg_15'",
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
        "branch_decision": branch_decision,
        "branch_should_retire": branch_should_retire,
    }
    (roc.LAYER3_DIR / "phase_gg_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase GG artifacts.")
    return best, branch_should_retire


if __name__ == "__main__":
    main()
