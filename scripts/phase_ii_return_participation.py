"""Phase II — Return-participation upgrade for production using ONLY
existing non-Phase-CC features.

Two candidates, both integrated INSIDE the production construction path
(scripts/build_improvement_artifacts.py) so the cost / overlay / cap /
renormalization pipeline is identical to production.

  II1 = improved_phaseii_good_state_participation_light
        phase2b_mode='regime_confidence_boost_participation_v1'
        Gate: (market_state == 'calm_trend' OR strong_neutral)
              AND breadth_sma_43 >= 0.65
              AND breadth_26w_mom >= 0.50
              AND market_trend_positive > 0
        Action: regime_multiplier += 0.015 (capped at 1.0).

  II2 = improved_phaseii_recovery_confirmed_participation_light
        phase2b_mode='regime_confidence_boost_participation_v2'
        Gate: market_state == 'recovery_confirmed'
              AND breadth_sma_43 >= 0.55
              AND breadth_26w_mom >= 0.50
        Action: regime_multiplier += 0.015 (capped at 1.0).

Neither candidate uses Phase CC's refined_state, defensive_overlay_hint,
deterioration_z, or any other Phase CC artifact. Both use only features
already present in market_state_history.csv before Phase CC.

Selection rule (8 gates):
  - ann return improves >= 0.20pp OR Sharpe improves >= 0.005
  - max drawdown worsening <= 0.5pp
  - CVaR-5% worsening <= 0.05pp
  - turnover ratio vs production <= 1.10x
  - avg BIL drop <= 5pp without offsetting risk-adjusted benefit
  - stressed_panic / recovery_fragile state performance not materially worse
  - improvement is not pure SPY/beta exposure inflation
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
II1_NAME = "improved_phaseii_good_state_participation_light"
II2_NAME = "improved_phaseii_recovery_confirmed_participation_light"
PHASE_II_CANDIDATES = [II1_NAME, II2_NAME]


def run_production_path(rebuild_production: bool = True) -> None:
    targets = list(PHASE_II_CANDIDATES)
    if rebuild_production:
        targets.append(PRODUCTION)
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    print(f"Invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=1800)
    print("--- subprocess stdout (last 30 lines) ---")
    for line in (res.stdout or "").splitlines()[-30:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 30 lines) ---")
        for line in (res.stderr or "").splitlines()[-30:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def load_market_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def state_breakdown(net: pd.Series, prod_net: pd.Series, state_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("ii"), prod_net.rename("prod")], axis=1).join(
        state_df[["market_state"]], how="inner"
    ).dropna()
    rows = []
    for s, sub in df.groupby("market_state"):
        rows.append({
            "state": s,
            "n_weeks": int(len(sub)),
            "ii_mean_wkly": float(sub["ii"].mean()),
            "prod_mean_wkly": float(sub["prod"].mean()),
            "delta_mean_wkly": float(sub["ii"].mean() - sub["prod"].mean()),
            "ii_minus_prod_cumulative": float(((1 + sub["ii"]).prod() - 1) - ((1 + sub["prod"]).prod() - 1)),
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


def select_best(summary: pd.DataFrame, state_df_summary: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_II_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    rows = []
    for _, r in cands.iterrows():
        name = r["name"]
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        bil_change_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100
        spy_change_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100
        sub = state_df_summary[state_df_summary["candidate"] == name]
        sp_row = sub[sub["state"] == "stressed_panic"]
        rf_row = sub[sub["state"] == "recovery_fragile"]
        sp_delta = float(sp_row["delta_mean_wkly"].iloc[0]) if not sp_row.empty else float("nan")
        rf_delta = float(rf_row["delta_mean_wkly"].iloc[0]) if not rf_row.empty else float("nan")
        # Selection gates
        cond_improvement = (ann_imp_pp >= 0.20) or (sharpe_imp >= 0.005)
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = (bil_change_pp >= -5.0) or (sharpe_imp >= 0.005)  # tolerate BIL drop only with risk-adjusted benefit
        cond_sp = (np.isnan(sp_delta) or sp_delta >= -1e-4)  # not materially worse
        cond_rf = (np.isnan(rf_delta) or rf_delta >= -1e-4)
        # Hidden beta check: if SPY rises >10pp without ann return rising >0.20pp, flag
        cond_hidden_beta = not (spy_change_pp > 10.0 and ann_imp_pp < 0.20)
        passes = all([cond_improvement, cond_mdd, cond_cvar, cond_turn, cond_bil, cond_sp, cond_rf, cond_hidden_beta])
        fail = "; ".join(filter(None, [
            f"no qualifying improvement (ann +{ann_imp_pp:.2f}pp, sharpe {sharpe_imp:+.4f})" if not cond_improvement else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"bil_drop>5pp without risk benefit ({bil_change_pp:+.2f}pp)" if not cond_bil else "",
            f"stressed_panic worse ({sp_delta:+.6f}/wk)" if not cond_sp else "",
            f"recovery_fragile worse ({rf_delta:+.6f}/wk)" if not cond_rf else "",
            f"hidden beta — SPY +{spy_change_pp:.2f}pp without ann improvement" if not cond_hidden_beta else "",
        ])) or "none"
        rows.append({
            "name": name,
            "ann_imp_pp": ann_imp_pp,
            "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp_pp,
            "cvar_imp_pp": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio,
            "bil_change_pp": bil_change_pp,
            "spy_change_pp": spy_change_pp,
            "stressed_panic_delta_wkly": sp_delta,
            "recovery_fragile_delta_wkly": rf_delta,
            "passes_all_gates": passes,
            "fail_reasons": fail,
        })
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        # Tie-break by ann return improvement, then Sharpe improvement
        best = passing.sort_values(["ann_imp_pp", "sharpe_imp"], ascending=[False, False]).iloc[0]
        rationale = (f"Selected {best['name']}: passes all 8 gates; "
                     f"ann_imp +{best['ann_imp_pp']:.2f}pp; sharpe_imp {best['sharpe_imp']:+.4f}; "
                     f"mdd_imp {best['mdd_imp_pp']:+.2f}pp.")
        return best["name"], rationale, decision.to_dict("records")
    least = decision.sort_values(["ann_imp_pp", "sharpe_imp"], ascending=[False, False]).iloc[0]
    rationale = f"NO Phase II candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}."
    return "", rationale, decision.to_dict("records")


def main():
    if "--no-rebuild" not in sys.argv:
        run_production_path(rebuild_production=True)
    else:
        print("--no-rebuild: using existing files")

    state_hist = load_market_state()

    summaries = []
    state_rows = []
    for name in PHASE_II_CANDIDATES + [PRODUCTION, SHADOW]:
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
    summary.to_csv(roc.LAYER3_DIR / "phase_ii_candidate_metrics_full.csv", index=False)

    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns missing")
    prod_net = prod_ret["net_return"]
    for name in PHASE_II_CANDIDATES:
        cret = roc.load_portfolio_returns(name)
        if cret is None: continue
        sb = state_breakdown(cret["net_return"], prod_net, state_hist)
        sb["candidate"] = name
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    if not state_df.empty:
        state_df.to_csv(roc.LAYER3_DIR / "phase_ii_state_summary.csv", index=False)

    best, rationale, decision_records = select_best(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + decision_records).to_csv(
        roc.LAYER3_DIR / "phase_ii_selection_table.csv", index=False)

    print("\n=== Phase II candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    if not state_df.empty:
        print("\n=== Phase II state-by-state ===")
        view = state_df[["candidate", "state", "n_weeks", "delta_mean_wkly", "ii_minus_prod_cumulative"]]
        print(view.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase II — Return-participation upgrade for production (NO Phase CC features used)",
        "candidates": PHASE_II_CANDIDATES,
        "integration_point": "scripts/build_improvement_artifacts.py — apply_overlays_custom (II1/II2 add +0.015 to regime_multiplier in qualifying favorable weeks)",
        "features_used": ["market_state", "breadth_sma_43", "breadth_26w_mom", "market_trend_positive", "is_strong_neutral_state_row helper"],
        "phase_cc_artifacts_used": "NONE — refined_state, defensive_overlay_hint, deterioration_z explicitly NOT consulted",
        "selection_rule": {
            "ann_return_improvement_min_pp_or_sharpe_min": "0.20pp OR 0.005",
            "mdd_worsening_max_pp": 0.5,
            "cvar_worsening_max_pp": 0.05,
            "turnover_ratio_max_vs_prod": 1.10,
            "bil_drop_max_pp_without_offsetting_benefit": 5.0,
            "stressed_panic_must_not_be_materially_worse": True,
            "recovery_fragile_must_not_be_materially_worse": True,
            "no_hidden_beta_inflation": True,
        },
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_ii_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase II artifacts.")
    return best


if __name__ == "__main__":
    main()
