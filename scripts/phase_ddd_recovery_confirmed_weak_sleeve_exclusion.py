"""Phase DDD — recovery_confirmed-only harder weak-sleeve exclusion on top of CCC2.

CCC2 (`improved_phaseccc_confirmed_cap_dual`) hard-caps dual_momentum_topn at 0.12
share of the recovery_confirmed offense bucket and reallocates 65% to
composite_regime_offense_component / 35% to cta_trend_long_only. The remaining
recovery_confirmed gap vs production is -0.6107pp ann return.

Phase DDD pushes the dual cap lower (and optionally the CSS cap) and tests four
main + two rescue rebudgets. recovery_fragile, strong_neutral and stressed_panic
are unchanged from CCC.

Main:
  DDD1 = improved_phaseddd_confirmed_harder_dual_cap          (dual cap 0.07)
  DDD2 = improved_phaseddd_confirmed_near_exclude_dual         (dual cap 0.03)
  DDD3 = improved_phaseddd_confirmed_dual_hard_css_soft        (dual 0.06 + css 0.10)
  DDD4 = improved_phaseddd_confirmed_defensive_balanced_substitution (dual 0.06 + css 0.12, def receiver)

Rescue (only used if all main fail narrowly):
  DDD5 = improved_phaseddd_minimal_dual_polish                 (dual 0.10, comp_off only)
  DDD6 = improved_phaseddd_confirmed_comp_off_receiver         (dual 0.07, comp_off only)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
YY_BEST = "improved_phaseyy_conservative_decomposition"
ZZ2 = "improved_phasezz_recovery_neutral_offense_rebudget"
AAA2 = "improved_phaseaaa_confirmed_offense_mix_tilt"
BBB3 = "improved_phasebbb_offense_defense_composition_combo"
CCC2 = "improved_phaseccc_confirmed_cap_dual"

DDD1 = "improved_phaseddd_confirmed_harder_dual_cap"
DDD2 = "improved_phaseddd_confirmed_near_exclude_dual"
DDD3 = "improved_phaseddd_confirmed_dual_hard_css_soft"
DDD4 = "improved_phaseddd_confirmed_defensive_balanced_substitution"
DDD5 = "improved_phaseddd_minimal_dual_polish"
DDD6 = "improved_phaseddd_confirmed_comp_off_receiver"
PHASE_DDD_MAIN = [DDD1, DDD2, DDD3, DDD4]
PHASE_DDD_RESCUE = [DDD5, DDD6]
PHASE_DDD_ALL = PHASE_DDD_MAIN + PHASE_DDD_RESCUE
REFERENCES = [PRODUCTION, SHADOW, YY_BEST, ZZ2, AAA2, BBB3, CCC2]

OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"
COMPOSITE_FAMILY = [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]
OFFENSIVE_SLEEVES = ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", OFFENSE_COMPONENT]
DEFENSIVE_SLEEVES = ["taa_10m_sma", DEFENSE_COMPONENT]

OUT_DATA = roc.ROOT / "data" / "research" / "phase_ddd_recovery_confirmed_weak_sleeve_exclusion"
OUT_DATA.mkdir(parents=True, exist_ok=True)


def run_pipeline(version_names: list[str]) -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(version_names)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print(f"[Phase DDD] invoking build_improvement_artifacts.py with {len(version_names)} versions")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 8 lines) ---")
    for line in (res.stdout or "").splitlines()[-8:]:
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
    if ret is None: return {"name": name}
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
    if ret is None: return {}
    df = ret[["net_return"]].join(state[["market_state"]], how="inner").dropna()
    out = {}
    for s, sub in df.groupby("market_state"):
        n = sub["net_return"]
        out[s] = {"ann_return": roc.annualised_return(n), "sharpe": roc.sharpe(n),
                   "n_weeks": int(len(sub))}
    return out


def state_weights(name: str, state: pd.DataFrame) -> pd.DataFrame:
    sw = roc.load_portfolio_sleeve_weights(name)
    if sw is None: return pd.DataFrame()
    joined = sw.join(state[["market_state"]], how="inner").dropna(subset=["market_state"])
    rows = []
    for s, sub in joined.groupby("market_state"):
        row = {"version": name, "state": s, "n_weeks": int(len(sub))}
        for c in COMPOSITE_FAMILY + ["dual_momentum_topn", "cta_trend_long_only",
                                       "composite_selective_signals", "taa_10m_sma"]:
            row[f"avg_{c}"] = float(sub[c].mean()) if c in sub.columns else float("nan")
        off = [c for c in OFFENSIVE_SLEEVES if c in sub.columns]
        defe = [c for c in DEFENSIVE_SLEEVES if c in sub.columns]
        row["avg_offensive_total"] = float(sub[off].sum(axis=1).mean()) if off else float("nan")
        row["avg_defensive_total"] = float(sub[defe].sum(axis=1).mean()) if defe else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate(summary: pd.DataFrame, all_state: dict[str, dict],
             candidate_names: list[str]) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(candidate_names)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    ccc = summary[summary["name"] == CCC2]
    ccc_d = ccc.iloc[0].to_dict() if not ccc.empty else {}
    rows = []
    prod_state = all_state.get(PRODUCTION, {})
    ccc_state = all_state.get(CCC2, {})
    for _, r in cands.iterrows():
        name = r["name"]
        cand_state = all_state.get(name, {})
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        sharpe_vs_ccc = r["full_sharpe"] - ccc_d.get("full_sharpe", float("nan"))
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        spy_inc_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100

        def sd(state_name, ref_state):
            cand = cand_state.get(state_name, {}); refp = ref_state.get(state_name, {})
            return ((cand.get("ann_return", float("nan")) - refp.get("ann_return", float("nan"))) * 100,
                    cand.get("sharpe", float("nan")) - refp.get("sharpe", float("nan")))
        sp_ann, _ = sd("stressed_panic", prod_state)
        rc_ann, rc_sh = sd("recovery_confirmed", prod_state)
        rf_ann, _ = sd("recovery_fragile", prod_state)
        rc_vs_ccc, _ = sd("recovery_confirmed", ccc_state)
        rf_vs_ccc, _ = sd("recovery_fragile", ccc_state)

        decomp_ok = pd.notna(r.get("avg_explicit_cash_sleeve")) and float(r.get("avg_explicit_cash_sleeve", 0.0)) > 0.001

        # gates
        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_sharpe_vs_ccc = (np.isnan(sharpe_vs_ccc)) or (sharpe_vs_ccc >= -0.02)
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_sp = (np.isnan(sp_ann) or sp_ann >= -0.30)
        cond_rf_no_regression = (np.isnan(rf_vs_ccc) or rf_vs_ccc >= -0.30)
        cond_rc_improves_vs_ccc = (np.isnan(rc_vs_ccc) or rc_vs_ccc > 0.0)
        cond_hidden_beta = not (spy_inc_pp > 1.0 and ann_imp_pp < 0.20)
        passes_strict = all([cond_drag, cond_sharpe, cond_sharpe_vs_ccc, cond_mdd, cond_cvar,
                              cond_turn, cond_sp, cond_rf_no_regression, cond_rc_improves_vs_ccc,
                              cond_hidden_beta, decomp_ok])

        # PRODUCTION CHALLENGER PENDING HUMAN REVIEW
        cond_chal_sharpe = sharpe_imp >= 0.020
        cond_chal_mdd = mdd_imp_pp >= -0.10
        cond_chal_cvar = cvar_imp_pp >= -0.02
        cond_chal_rc = (np.isnan(rc_ann) or rc_ann >= -0.30)
        cond_chal_rf = (np.isnan(rf_ann) or rf_ann >= -0.30)
        challenger = all([cond_chal_sharpe, cond_chal_mdd, cond_chal_cvar,
                            cond_chal_rc, cond_chal_rf, cond_hidden_beta, decomp_ok])

        repairs_rc = (not np.isnan(rc_vs_ccc)) and rc_vs_ccc > 0.0
        cond_shadow = (sharpe_imp > 0) and (ann_imp_pp >= -0.30) and cond_sp and decomp_ok and repairs_rc

        fail_reasons = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"sharpe_vs_ccc<-0.02 ({sharpe_vs_ccc:+.4f})" if not cond_sharpe_vs_ccc else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"stressed_panic worse ({sp_ann:+.2f}pp)" if not cond_sp else "",
            f"recovery_fragile regressed vs CCC2 ({rf_vs_ccc:+.2f}pp)" if not cond_rf_no_regression else "",
            f"recovery_confirmed did not improve vs CCC2 ({rc_vs_ccc:+.2f}pp)" if not cond_rc_improves_vs_ccc else "",
            f"hidden beta SPY +{spy_inc_pp:+.2f}pp" if not cond_hidden_beta else "",
            "decomposition not intact" if not decomp_ok else "",
        ])) or "none"

        rows.append({
            "name": name, "ann_imp_pp_vs_prod": ann_imp_pp, "sharpe_imp_vs_prod": sharpe_imp,
            "sharpe_vs_ccc": sharpe_vs_ccc, "mdd_imp_pp_vs_prod": mdd_imp_pp,
            "cvar_imp_pp_vs_prod": cvar_imp_pp, "turnover_ratio_vs_prod": turn_ratio,
            "spy_inc_pp_vs_prod": spy_inc_pp,
            "stressed_panic_ann_delta_pp": sp_ann,
            "recovery_confirmed_ann_delta_pp_vs_prod": rc_ann,
            "recovery_fragile_ann_delta_pp_vs_prod": rf_ann,
            "recovery_confirmed_ann_delta_pp_vs_ccc": rc_vs_ccc,
            "recovery_fragile_ann_delta_pp_vs_ccc": rf_vs_ccc,
            "decomposition_intact": decomp_ok,
            "passes_strict_gates": passes_strict,
            "passes_challenger_track": challenger,
            "passes_shadow_track": cond_shadow,
            "fail_reasons_strict": fail_reasons,
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
        return b["name"], f"Selected {b['name']} as KEEP AS SHADOW (improves vs production with partial RC repair vs CCC2).", decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
    return "", f"NO Phase DDD candidate passes any track. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons_strict']}.", decision.to_dict("records")


def collect_summary(names: list[str], state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows = []
    state_rows = []
    all_state_metrics: dict[str, dict] = {}
    for name in names:
        h = headline(name)
        if h: rows.append(h)
        all_state_metrics[name] = state_metrics(name, state)
        sw = state_weights(name, state)
        if not sw.empty: state_rows.append(sw)
    summary = pd.DataFrame(rows)
    weights_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    return summary, weights_df, all_state_metrics


def main():
    print("[Phase DDD] Step 1: building MAIN candidates only")
    if "--no-rebuild" not in sys.argv:
        run_pipeline(PHASE_DDD_MAIN + REFERENCES)
    state = load_state()

    main_summary, weights_df, all_state_main = collect_summary(PHASE_DDD_MAIN + REFERENCES, state)
    main_summary.to_csv(roc.LAYER3_DIR / "phase_ddd_candidate_metrics_full.csv", index=False)

    weights_df.to_csv(OUT_DATA / "phase_ddd_confirmed_weak_sleeve_diagnostics.csv", index=False)
    rc_view = weights_df[weights_df["state"] == "recovery_confirmed"]
    rc_view.to_csv(OUT_DATA / "phase_ddd_confirmed_sleeve_contribution.csv", index=False)

    # state-by-state DELTAs vs production for each candidate
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    state_summary_rows = []
    for name in PHASE_DDD_MAIN:
        ret = roc.load_portfolio_returns(name)
        if ret is None: continue
        df = pd.concat([ret["net_return"].rename("ddd"), prod_ret["net_return"].rename("prod")], axis=1).join(
            state[["market_state"]], how="inner"
        ).dropna()
        for s, sub in df.groupby("market_state"):
            state_summary_rows.append({"candidate": name, "state": s, "n_weeks": int(len(sub)),
                                         "ddd_mean_wkly": float(sub["ddd"].mean()),
                                         "prod_mean_wkly": float(sub["prod"].mean()),
                                         "delta_mean_wkly": float(sub["ddd"].mean() - sub["prod"].mean()),
                                         "ddd_minus_prod_cumulative": float(((1+sub["ddd"]).prod()-1) - ((1+sub["prod"]).prod()-1))})
    pd.DataFrame(state_summary_rows).to_csv(roc.LAYER3_DIR / "phase_ddd_state_summary.csv", index=False)

    # Evaluate main
    best, rationale, recs = evaluate(main_summary, all_state_main, PHASE_DDD_MAIN)
    pd.DataFrame(recs).to_csv(OUT_DATA / "phase_ddd_candidate_diagnostics.csv", index=False)

    # Decide whether to bring in rescues. Per spec: only if all main fail narrowly.
    main_decision = pd.DataFrame(recs)
    main_passes_strict = main_decision["passes_strict_gates"].any()
    main_passes_shadow = main_decision["passes_shadow_track"].any()
    used_rescue = False
    if not (main_passes_strict or main_passes_shadow):
        # check that the failure was narrow (top main candidate has improvement vs CCC2 within ~0.05pp)
        top = main_decision.sort_values("recovery_confirmed_ann_delta_pp_vs_ccc", ascending=False).iloc[0]
        if top["recovery_confirmed_ann_delta_pp_vs_ccc"] >= -0.05 and top["sharpe_vs_ccc"] >= -0.02:
            print("[Phase DDD] All main fail narrowly; running RESCUE candidates")
            run_pipeline(PHASE_DDD_RESCUE)
            used_rescue = True
            full_summary, weights_df_full, all_state_full = collect_summary(
                PHASE_DDD_ALL + REFERENCES, state)
            full_summary.to_csv(roc.LAYER3_DIR / "phase_ddd_candidate_metrics_full.csv", index=False)
            weights_df_full.to_csv(OUT_DATA / "phase_ddd_confirmed_weak_sleeve_diagnostics.csv", index=False)
            best, rationale, recs = evaluate(full_summary, all_state_full, PHASE_DDD_ALL)
            pd.DataFrame(recs).to_csv(OUT_DATA / "phase_ddd_candidate_diagnostics.csv", index=False)
            main_summary = full_summary
        else:
            print("[Phase DDD] All main fail and not narrowly — skipping rescue per spec.")

    # selection table
    pd.DataFrame([{"best_candidate": best, "rationale": rationale,
                    "rescue_used": used_rescue}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_ddd_selection_table.csv", index=False)

    # reallocation diagnostics — what each DDD did to dual / css / comp_off / cta in recovery_confirmed
    rc_alloc = weights_df[weights_df["state"] == "recovery_confirmed"][[
        "version", "n_weeks",
        "avg_dual_momentum_topn", "avg_cta_trend_long_only",
        "avg_composite_selective_signals", "avg_composite_regime_offense_component",
        "avg_composite_regime_defense_component",
        "avg_offensive_total", "avg_defensive_total"]]
    rc_alloc.to_csv(OUT_DATA / "phase_ddd_reallocation_diagnostics.csv", index=False)

    # Print
    print("\n=== Phase DDD candidate summary (main + references) ===")
    print(main_summary[["name","full_ann_return","full_sharpe","full_max_drawdown","full_cvar_5","avg_BIL","avg_SPY","avg_turnover"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== recovery_confirmed sleeve allocation by version ===")
    print(rc_alloc.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase DDD selection records ===")
    print(pd.DataFrame(recs)[["name","ann_imp_pp_vs_prod","sharpe_imp_vs_prod","sharpe_vs_ccc","mdd_imp_pp_vs_prod","recovery_confirmed_ann_delta_pp_vs_prod","recovery_confirmed_ann_delta_pp_vs_ccc","recovery_fragile_ann_delta_pp_vs_ccc","stressed_panic_ann_delta_pp","passes_strict_gates","passes_challenger_track","passes_shadow_track","fail_reasons_strict"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase DDD — recovery_confirmed-only harder weak-sleeve exclusion",
        "main_candidates": PHASE_DDD_MAIN,
        "rescue_candidates": PHASE_DDD_RESCUE if used_rescue else [],
        "production_pin": PRODUCTION, "shadow_pin": SHADOW,
        "ccc_reference": CCC2, "best_candidate": best, "rationale": rationale,
        "rescue_used": used_rescue,
    }
    (roc.LAYER3_DIR / "phase_ddd_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase DDD artifacts.")
    return best


if __name__ == "__main__":
    main()
