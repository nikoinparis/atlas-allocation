"""Phase HHH — Extend GGG1 with state-conditional offense swap in stressed_panic.

GGG1 cleanly proved that state-conditional component construction works:
broad EEE1 offense in most states, FFF3 robust offense ONLY in
recovery_confirmed. The GGG diagnostic (`phase_ggg_filtered_vs_broad_by_state`)
also showed filtered offense helps stressed_panic by +0.41pp ann (without
weakening cash/defense routes). Phase HHH tests three narrow extensions
that ALSO swap to filtered offense in stressed_panic.

Three candidates (recovery_fragile / neutral_mixed / calm_trend stay broad):
  HHH1 = improved_phasehhh_confirmed_stressed_robust_offense
         (RC + SP -> FFF3 robust)
  HHH2 = improved_phasehhh_confirmed_robust_stressed_blended_offense
         (RC -> FFF3; SP -> 50/50 broad + FFF3 blend)
  HHH3 = improved_phasehhh_confirmed_quality_stressed_robust_offense
         (RC -> FFF1 quality_filtered; SP -> FFF3 robust)
"""
from __future__ import annotations

import json, os, subprocess, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc

PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
EEE1 = "improved_phaseeee_smoothed_near_exclude_dual"
FFF3 = "improved_phasefff_robust_composite_offense"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

HHH1 = "improved_phasehhh_confirmed_stressed_robust_offense"
HHH2 = "improved_phasehhh_confirmed_robust_stressed_blended_offense"
HHH3 = "improved_phasehhh_confirmed_quality_stressed_robust_offense"
PHASE_HHH_CANDIDATES = [HHH1, HHH2, HHH3]
REFERENCES = [PRODUCTION, SHADOW, EEE1, FFF3, GGG1]

OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"
COMPOSITE_FAMILY = [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]
OFFENSIVE_SLEEVES = ["dual_momentum_topn", "cta_trend_long_only",
                      "composite_selective_signals", OFFENSE_COMPONENT]
DEFENSIVE_SLEEVES = ["taa_10m_sma", DEFENSE_COMPONENT]

OUT_DATA = roc.ROOT / "data" / "research" / "phase_hhh_state_conditional_stressed_offense"
OUT_DATA.mkdir(parents=True, exist_ok=True)


def run_pipeline(version_names: list[str]) -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(version_names)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print(f"[Phase HHH] invoking build_improvement_artifacts.py with {len(version_names)} versions")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 5 lines) ---")
    for line in (res.stdout or "").splitlines()[-5:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 30 lines) ---")
        for line in (res.stderr or "").splitlines()[-30:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def load_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def headline(name: str) -> dict:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return {"name": name}
    w = roc.load_portfolio_weights(name)
    sw = roc.load_portfolio_sleeve_weights(name)
    net = ret["net_return"].dropna()
    full_m = roc.metric_block(net)
    hold_m = roc.metric_block(net.tail(roc.HOLDOUT_WEEKS))
    out = {"name": name,
            "full_ann_return": full_m["ann_return"], "full_ann_vol": full_m["ann_vol"],
            "full_sharpe": full_m["sharpe"], "full_max_drawdown": full_m["max_drawdown"],
            "full_cvar_5": full_m["cvar_5"], "full_calmar": full_m["calmar"],
            "holdout_ann_return": hold_m["ann_return"], "holdout_sharpe": hold_m["sharpe"],
            "holdout_max_drawdown": hold_m["max_drawdown"]}
    if w is not None:
        out["avg_BIL"] = float(w["BIL"].mean()) if "BIL" in w.columns else float("nan")
        out["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else float("nan")
        out["avg_turnover"] = float(w.diff().abs().sum(axis=1).fillna(0.0).mean())
    if sw is not None:
        off = [c for c in OFFENSIVE_SLEEVES if c in sw.columns]
        defe = [c for c in DEFENSIVE_SLEEVES if c in sw.columns]
        cash_col = [c for c in sw.columns if c.startswith("cash::")]
        out["avg_offensive_sleeve"] = float(sw[off].sum(axis=1).mean()) if off else float("nan")
        out["avg_defensive_sleeve"] = float(sw[defe].sum(axis=1).mean()) if defe else float("nan")
        out["avg_explicit_cash_sleeve"] = float(sw[cash_col].sum(axis=1).mean()) if cash_col else float("nan")
        for c in COMPOSITE_FAMILY:
            out[f"avg_{c}"] = float(sw[c].mean()) if c in sw.columns else float("nan")
    if "turnover" in ret.columns and pd.isna(out.get("avg_turnover", float("nan"))):
        out["avg_turnover"] = float(ret["turnover"].mean())
    return out


def state_metrics(name: str, state: pd.DataFrame) -> dict:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return {}
    df = ret[["net_return"]].join(state[["market_state"]], how="inner").dropna()
    out = {}
    for s, sub in df.groupby("market_state"):
        n = sub["net_return"]
        out[s] = {"ann_return": roc.annualised_return(n), "sharpe": roc.sharpe(n),
                   "n_weeks": int(len(sub))}
    return out


def evaluate(summary: pd.DataFrame, all_state: dict[str, dict]) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_HHH_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    ggg1 = summary[summary["name"] == GGG1]
    ggg1_d = ggg1.iloc[0].to_dict() if not ggg1.empty else {}
    eee1 = summary[summary["name"] == EEE1]
    eee1_d = eee1.iloc[0].to_dict() if not eee1.empty else {}
    fff3 = summary[summary["name"] == FFF3]
    fff3_d = fff3.iloc[0].to_dict() if not fff3.empty else {}

    rows = []
    prod_state = all_state.get(PRODUCTION, {})
    ggg1_state = all_state.get(GGG1, {})
    eee1_state = all_state.get(EEE1, {})
    fff3_state = all_state.get(FFF3, {})

    for _, r in cands.iterrows():
        name = r["name"]
        cand_state = all_state.get(name, {})
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        sharpe_vs_ggg1 = r["full_sharpe"] - ggg1_d.get("full_sharpe", float("nan"))
        sharpe_vs_eee1 = r["full_sharpe"] - eee1_d.get("full_sharpe", float("nan"))
        sharpe_vs_fff3 = r["full_sharpe"] - fff3_d.get("full_sharpe", float("nan"))
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        spy_inc_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100

        def sd(state_name, ref_state):
            cand = cand_state.get(state_name, {})
            refp = ref_state.get(state_name, {})
            return ((cand.get("ann_return", float("nan")) - refp.get("ann_return", float("nan"))) * 100,
                    cand.get("sharpe", float("nan")) - refp.get("sharpe", float("nan")))

        sp_ann_vs_prod, _ = sd("stressed_panic", prod_state)
        sp_ann_vs_ggg1, _ = sd("stressed_panic", ggg1_state)
        rc_ann_vs_prod, _ = sd("recovery_confirmed", prod_state)
        rc_ann_vs_ggg1, _ = sd("recovery_confirmed", ggg1_state)
        rf_ann_vs_prod, _ = sd("recovery_fragile", prod_state)
        rf_ann_vs_ggg1, _ = sd("recovery_fragile", ggg1_state)
        ct_vs_ggg1, _ = sd("calm_trend", ggg1_state)
        nm_vs_ggg1, _ = sd("neutral_mixed", ggg1_state)
        decomp_ok = pd.notna(r.get("avg_explicit_cash_sleeve")) and float(r.get("avg_explicit_cash_sleeve", 0.0)) > 0.001

        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_sharpe_vs_ggg1 = (np.isnan(sharpe_vs_ggg1)) or (sharpe_vs_ggg1 >= -0.02)
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_sp_vs_prod = (np.isnan(sp_ann_vs_prod) or sp_ann_vs_prod >= -0.30)
        cond_sp_vs_ggg1 = (np.isnan(sp_ann_vs_ggg1) or sp_ann_vs_ggg1 >= -0.20)
        cond_rf_no_regression = (np.isnan(rf_ann_vs_ggg1) or rf_ann_vs_ggg1 >= -0.20)
        cond_rc_no_regression = (np.isnan(rc_ann_vs_ggg1) or rc_ann_vs_ggg1 >= -0.20)
        cond_hidden_beta = not (spy_inc_pp > 1.0 and ann_imp_pp < 0.20)
        passes_strict = all([cond_drag, cond_sharpe, cond_sharpe_vs_ggg1, cond_mdd, cond_cvar,
                              cond_turn, cond_sp_vs_prod, cond_sp_vs_ggg1, cond_rf_no_regression,
                              cond_rc_no_regression, cond_hidden_beta, decomp_ok])

        cond_chal_sharpe = sharpe_imp >= 0.020
        cond_chal_mdd = mdd_imp_pp >= -0.10
        cond_chal_cvar = cvar_imp_pp >= -0.02
        cond_chal_rc = (np.isnan(rc_ann_vs_prod) or rc_ann_vs_prod >= -0.30)
        cond_chal_rf = (np.isnan(rf_ann_vs_prod) or rf_ann_vs_prod >= -0.30)
        challenger = all([cond_chal_sharpe, cond_chal_mdd, cond_chal_cvar,
                            cond_chal_rc, cond_chal_rf, cond_hidden_beta, decomp_ok, cond_turn])

        improves_vs_ggg1 = (sharpe_vs_ggg1 > 0) or (ann_imp_pp - (ggg1_d.get("full_ann_return", 0) - prod["full_ann_return"]) * 100 > 0)
        cond_shadow = (sharpe_imp > 0) and (ann_imp_pp >= -0.30) and cond_sp_vs_prod and decomp_ok and improves_vs_ggg1 and cond_turn

        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"sharpe_vs_ggg1<-0.02 ({sharpe_vs_ggg1:+.4f})" if not cond_sharpe_vs_ggg1 else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.4f}x)" if not cond_turn else "",
            f"stressed_panic vs prod worse ({sp_ann_vs_prod:+.2f}pp)" if not cond_sp_vs_prod else "",
            f"stressed_panic vs GGG1 worse ({sp_ann_vs_ggg1:+.2f}pp)" if not cond_sp_vs_ggg1 else "",
            f"recovery_fragile vs GGG1 regressed ({rf_ann_vs_ggg1:+.2f}pp)" if not cond_rf_no_regression else "",
            f"recovery_confirmed vs GGG1 regressed ({rc_ann_vs_ggg1:+.2f}pp)" if not cond_rc_no_regression else "",
            f"hidden beta SPY +{spy_inc_pp:+.2f}pp" if not cond_hidden_beta else "",
            "decomposition not intact" if not decomp_ok else "",
        ])) or "none"

        rows.append({
            "name": name, "ann_imp_pp_vs_prod": ann_imp_pp, "sharpe_imp_vs_prod": sharpe_imp,
            "sharpe_vs_ggg1": sharpe_vs_ggg1, "sharpe_vs_eee1": sharpe_vs_eee1, "sharpe_vs_fff3": sharpe_vs_fff3,
            "mdd_imp_pp_vs_prod": mdd_imp_pp, "cvar_imp_pp_vs_prod": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio, "spy_inc_pp_vs_prod": spy_inc_pp,
            "stressed_panic_ann_delta_pp_vs_prod": sp_ann_vs_prod,
            "stressed_panic_ann_delta_pp_vs_ggg1": sp_ann_vs_ggg1,
            "recovery_confirmed_ann_delta_pp_vs_prod": rc_ann_vs_prod,
            "recovery_confirmed_ann_delta_pp_vs_ggg1": rc_ann_vs_ggg1,
            "recovery_fragile_ann_delta_pp_vs_prod": rf_ann_vs_prod,
            "recovery_fragile_ann_delta_pp_vs_ggg1": rf_ann_vs_ggg1,
            "calm_trend_ann_delta_pp_vs_ggg1": ct_vs_ggg1,
            "neutral_mixed_ann_delta_pp_vs_ggg1": nm_vs_ggg1,
            "decomposition_intact": decomp_ok,
            "passes_strict_gates": passes_strict,
            "passes_challenger_track": challenger,
            "passes_shadow_track": cond_shadow,
            "fail_reasons_strict": fail,
        })

    decision = pd.DataFrame(rows)
    chal = decision[decision["passes_challenger_track"]]
    if not chal.empty:
        b = chal.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        return b["name"], f"PRODUCTION CHALLENGER PENDING HUMAN REVIEW: {b['name']}", decision.to_dict("records")
    strict = decision[decision["passes_strict_gates"]]
    if not strict.empty:
        b = strict.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        return b["name"], f"Selected {b['name']} (strict gates passed; below challenger threshold).", decision.to_dict("records")
    shadow = decision[decision["passes_shadow_track"]]
    if not shadow.empty:
        b = shadow.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        return b["name"], f"Selected {b['name']} as KEEP AS SHADOW (improves on GGG1).", decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
    return "", f"NO Phase HHH candidate passes any track. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons_strict']}.", decision.to_dict("records")


def main():
    if "--no-rebuild" not in sys.argv:
        run_pipeline(PHASE_HHH_CANDIDATES + REFERENCES)
    state = load_state()

    rows = []
    all_state_metrics: dict[str, dict] = {}
    for name in PHASE_HHH_CANDIDATES + REFERENCES:
        h = headline(name)
        if h:
            rows.append(h)
        all_state_metrics[name] = state_metrics(name, state)
    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_hhh_candidate_metrics_full.csv", index=False)

    # Component construction diagnostics
    construction = pd.DataFrame([
        {"version": GGG1, "construction": "state_conditional",
         "rc_offense": "FFF3 robust (8 ETFs)",
         "sp_offense": "broad EEE1 (10 ETFs)",
         "other_states_offense": "broad EEE1 (10 ETFs)"},
        {"version": HHH1, "construction": "state_conditional",
         "rc_offense": "FFF3 robust (8 ETFs)",
         "sp_offense": "FFF3 robust (8 ETFs)",
         "other_states_offense": "broad EEE1 (10 ETFs)"},
        {"version": HHH2, "construction": "state_conditional_blended",
         "rc_offense": "FFF3 robust (8 ETFs)",
         "sp_offense": "0.5*broad + 0.5*FFF3 robust",
         "other_states_offense": "broad EEE1 (10 ETFs)"},
        {"version": HHH3, "construction": "state_conditional",
         "rc_offense": "FFF1 quality_filtered (7 ETFs)",
         "sp_offense": "FFF3 robust (8 ETFs)",
         "other_states_offense": "broad EEE1 (10 ETFs)"},
    ])
    construction.to_csv(OUT_DATA / "phase_hhh_stressed_component_tradeoff.csv", index=False)

    # Filtered vs broad by state — re-derive from EEE1 vs FFF3 state metrics
    fff3_state_m = all_state_metrics.get(FFF3, {})
    eee1_state_m = all_state_metrics.get(EEE1, {})
    fbs_rows = []
    for s in ["calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]:
        eee1_v = eee1_state_m.get(s, {})
        fff3_v = fff3_state_m.get(s, {})
        delta = (fff3_v.get("ann_return", float("nan")) - eee1_v.get("ann_return", float("nan"))) * 100
        fbs_rows.append({"state": s, "n_weeks": eee1_v.get("n_weeks", 0),
                          "eee1_broad_ann_return_pct": eee1_v.get("ann_return", float("nan")) * 100,
                          "fff3_filtered_ann_return_pct": fff3_v.get("ann_return", float("nan")) * 100,
                          "filtered_minus_broad_pp": delta,
                          "filtered_helps": delta > 0})
    pd.DataFrame(fbs_rows).to_csv(OUT_DATA / "phase_hhh_filtered_vs_broad_by_state.csv", index=False)

    # State-by-state for HHH candidates
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    ggg1_ret = roc.load_portfolio_returns(GGG1)
    state_rows = []
    for name in PHASE_HHH_CANDIDATES:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            continue
        df = pd.concat([ret["net_return"].rename("hhh"),
                          prod_ret["net_return"].rename("prod"),
                          ggg1_ret["net_return"].rename("ggg1")], axis=1).join(
            state[["market_state"]], how="inner"
        ).dropna()
        for s, sub in df.groupby("market_state"):
            state_rows.append({
                "candidate": name, "state": s, "n_weeks": int(len(sub)),
                "hhh_mean_wkly": float(sub["hhh"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "ggg1_mean_wkly": float(sub["ggg1"].mean()),
                "delta_vs_prod_wkly": float(sub["hhh"].mean() - sub["prod"].mean()),
                "delta_vs_ggg1_wkly": float(sub["hhh"].mean() - sub["ggg1"].mean()),
                "hhh_minus_prod_cumulative": float(((1+sub["hhh"]).prod()-1) - ((1+sub["prod"]).prod()-1)),
                "hhh_minus_ggg1_cumulative": float(((1+sub["hhh"]).prod()-1) - ((1+sub["ggg1"]).prod()-1)),
            })
    pd.DataFrame(state_rows).to_csv(roc.LAYER3_DIR / "phase_hhh_state_summary.csv", index=False)

    best, rationale, recs = evaluate(summary, all_state_metrics)
    pd.DataFrame(recs).to_csv(OUT_DATA / "phase_hhh_candidate_diagnostics.csv", index=False)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_hhh_selection_table.csv", index=False)

    print("\n=== Phase HHH candidate summary ===")
    print(summary[["name","full_ann_return","full_sharpe","full_max_drawdown","full_cvar_5","avg_BIL","avg_SPY","avg_turnover","avg_composite_regime_offense_component"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase HHH selection records ===")
    print(pd.DataFrame(recs)[["name","ann_imp_pp_vs_prod","sharpe_imp_vs_prod","sharpe_vs_ggg1","turnover_ratio_vs_prod","stressed_panic_ann_delta_pp_vs_ggg1","recovery_confirmed_ann_delta_pp_vs_ggg1","recovery_fragile_ann_delta_pp_vs_ggg1","passes_strict_gates","passes_challenger_track","passes_shadow_track","fail_reasons_strict"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase HHH — State-conditional stressed_panic offense_component swap",
        "candidates": PHASE_HHH_CANDIDATES,
        "production_pin": PRODUCTION, "shadow_pin": SHADOW,
        "ggg1_reference": GGG1, "eee1_reference": EEE1, "fff3_reference": FFF3,
        "best_candidate": best, "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_hhh_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase HHH artifacts.")
    return best


if __name__ == "__main__":
    main()
