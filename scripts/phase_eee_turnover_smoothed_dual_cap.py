"""Phase EEE — Turnover-smoothed aggressive dual cap.

DDD1 (dual cap 0.07, rerisk_speed=1.00) passes strict gates with
recovery_confirmed -0.51pp vs production. DDD2 (dual cap 0.03,
rerisk_speed=1.00) achieves -0.43pp recovery_confirmed but exceeds the
1.10× turnover gate (1.101×).

Phase EEE keeps DDD2's aggressive cap and lowers the rerisk_speed in
recovery_confirmed (1.00 -> 0.80 / 0.90 / 0.95) so the production
overlay's dynamic_speed mechanism smooths cap engagement transitions.
No new tilt branches; only version-spec changes.

Three candidates (≤3 per spec):
  EEE1 = improved_phaseeee_smoothed_near_exclude_dual    (DDD2 + rerisk 0.80)
  EEE2 = improved_phaseeee_turnover_aware_dual_cap        (DDD2 + rerisk 0.90)
  EEE3 = improved_phaseeee_selective_dual_escalation      (DDD1 + rerisk 0.95)
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
CCC2 = "improved_phaseccc_confirmed_cap_dual"
DDD1 = "improved_phaseddd_confirmed_harder_dual_cap"
DDD2 = "improved_phaseddd_confirmed_near_exclude_dual"

EEE1 = "improved_phaseeee_smoothed_near_exclude_dual"
EEE2 = "improved_phaseeee_turnover_aware_dual_cap"
EEE3 = "improved_phaseeee_selective_dual_escalation"
PHASE_EEE_CANDIDATES = [EEE1, EEE2, EEE3]
REFERENCES = [PRODUCTION, SHADOW, CCC2, DDD1, DDD2]

OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"
COMPOSITE_FAMILY = [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]
OFFENSIVE_SLEEVES = ["dual_momentum_topn", "cta_trend_long_only",
                      "composite_selective_signals", OFFENSE_COMPONENT]
DEFENSIVE_SLEEVES = ["taa_10m_sma", DEFENSE_COMPONENT]

OUT_DATA = roc.ROOT / "data" / "research" / "phase_eee_turnover_smoothed_dual_cap"
OUT_DATA.mkdir(parents=True, exist_ok=True)


def run_pipeline(version_names: list[str]) -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(version_names)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print(f"[Phase EEE] invoking build_improvement_artifacts.py with {len(version_names)} versions")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 6 lines) ---")
    for line in (res.stdout or "").splitlines()[-6:]:
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


def turnover_by_state(name: str, state: pd.DataFrame) -> pd.DataFrame:
    """Average weekly L1 turnover by market_state for a candidate."""
    w = roc.load_portfolio_weights(name)
    if w is None: return pd.DataFrame()
    turn = w.diff().abs().sum(axis=1).fillna(0.0).rename("turn")
    df = turn.to_frame().join(state[["market_state"]], how="inner").dropna()
    rows = []
    for s, sub in df.groupby("market_state"):
        rows.append({"version": name, "state": s, "n_weeks": int(len(sub)),
                      "avg_turnover": float(sub["turn"].mean()),
                      "max_turnover": float(sub["turn"].max())})
    return pd.DataFrame(rows)


def turnover_spike_diff(target: str, baseline: str, state: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Top weeks where target's weekly L1 turnover differs most from baseline."""
    wt = roc.load_portfolio_weights(target)
    wb = roc.load_portfolio_weights(baseline)
    if wt is None or wb is None: return pd.DataFrame()
    tt = wt.diff().abs().sum(axis=1).fillna(0.0)
    tb = wb.diff().abs().sum(axis=1).fillna(0.0)
    diff = (tt - tb).abs().rename("abs_turn_diff").to_frame()
    diff["target_turn"] = tt
    diff["baseline_turn"] = tb
    diff = diff.join(state[["market_state"]], how="left")
    return diff.sort_values("abs_turn_diff", ascending=False).head(top_n)


def evaluate(summary: pd.DataFrame, all_state: dict[str, dict]) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_EEE_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    ddd1 = summary[summary["name"] == DDD1]
    ddd1_d = ddd1.iloc[0].to_dict() if not ddd1.empty else {}
    rows = []
    prod_state = all_state.get(PRODUCTION, {})
    ddd1_state = all_state.get(DDD1, {})
    for _, r in cands.iterrows():
        name = r["name"]
        cand_state = all_state.get(name, {})
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        sharpe_vs_ddd1 = r["full_sharpe"] - ddd1_d.get("full_sharpe", float("nan"))
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
        rc_vs_ddd1, _ = sd("recovery_confirmed", ddd1_state)
        rf_vs_ddd1, _ = sd("recovery_fragile", ddd1_state)

        decomp_ok = pd.notna(r.get("avg_explicit_cash_sleeve")) and float(r.get("avg_explicit_cash_sleeve", 0.0)) > 0.001

        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_sharpe_vs_ddd1 = (np.isnan(sharpe_vs_ddd1)) or (sharpe_vs_ddd1 >= -0.02)
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_sp = (np.isnan(sp_ann) or sp_ann >= -0.30)
        cond_rf_no_regression = (np.isnan(rf_vs_ddd1) or rf_vs_ddd1 >= -0.30)
        cond_rc_improves_vs_ddd1 = (np.isnan(rc_vs_ddd1) or rc_vs_ddd1 > 0.0)
        cond_hidden_beta = not (spy_inc_pp > 1.0 and ann_imp_pp < 0.20)
        passes_strict = all([cond_drag, cond_sharpe, cond_sharpe_vs_ddd1, cond_mdd, cond_cvar,
                              cond_turn, cond_sp, cond_rf_no_regression, cond_rc_improves_vs_ddd1,
                              cond_hidden_beta, decomp_ok])

        # PRODUCTION CHALLENGER tier
        cond_chal_sharpe = sharpe_imp >= 0.020
        cond_chal_mdd = mdd_imp_pp >= -0.10
        cond_chal_cvar = cvar_imp_pp >= -0.02
        cond_chal_rc = (np.isnan(rc_ann) or rc_ann >= -0.30)
        cond_chal_rf = (np.isnan(rf_ann) or rf_ann >= -0.30)
        challenger = all([cond_chal_sharpe, cond_chal_mdd, cond_chal_cvar,
                            cond_chal_rc, cond_chal_rf, cond_hidden_beta, decomp_ok, cond_turn])

        repairs_rc = (not np.isnan(rc_vs_ddd1)) and rc_vs_ddd1 > 0.0
        cond_shadow = (sharpe_imp > 0) and (ann_imp_pp >= -0.30) and cond_sp and decomp_ok and repairs_rc and cond_turn

        fail_reasons = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"sharpe_vs_ddd1<-0.02 ({sharpe_vs_ddd1:+.4f})" if not cond_sharpe_vs_ddd1 else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.4f}x)" if not cond_turn else "",
            f"stressed_panic worse ({sp_ann:+.2f}pp)" if not cond_sp else "",
            f"recovery_fragile regressed vs DDD1 ({rf_vs_ddd1:+.2f}pp)" if not cond_rf_no_regression else "",
            f"recovery_confirmed did not improve vs DDD1 ({rc_vs_ddd1:+.2f}pp)" if not cond_rc_improves_vs_ddd1 else "",
            f"hidden beta SPY +{spy_inc_pp:+.2f}pp" if not cond_hidden_beta else "",
            "decomposition not intact" if not decomp_ok else "",
        ])) or "none"

        rows.append({
            "name": name, "ann_imp_pp_vs_prod": ann_imp_pp, "sharpe_imp_vs_prod": sharpe_imp,
            "sharpe_vs_ddd1": sharpe_vs_ddd1, "mdd_imp_pp_vs_prod": mdd_imp_pp,
            "cvar_imp_pp_vs_prod": cvar_imp_pp, "turnover_ratio_vs_prod": turn_ratio,
            "spy_inc_pp_vs_prod": spy_inc_pp,
            "stressed_panic_ann_delta_pp": sp_ann,
            "recovery_confirmed_ann_delta_pp_vs_prod": rc_ann,
            "recovery_fragile_ann_delta_pp_vs_prod": rf_ann,
            "recovery_confirmed_ann_delta_pp_vs_ddd1": rc_vs_ddd1,
            "recovery_fragile_ann_delta_pp_vs_ddd1": rf_vs_ddd1,
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
        return b["name"], f"Selected {b['name']} as KEEP AS SHADOW (improves vs production with RC repair vs DDD1).", decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
    return "", f"NO Phase EEE candidate passes any track. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons_strict']}.", decision.to_dict("records")


def main():
    if "--no-rebuild" not in sys.argv:
        run_pipeline(PHASE_EEE_CANDIDATES + REFERENCES)
    state = load_state()

    # Part A — turnover diagnosis
    print("[Phase EEE Part A] turnover diagnosis...")
    turn_rows = []
    all_state_metrics: dict[str, dict] = {}
    for name in PHASE_EEE_CANDIDATES + REFERENCES:
        sub = turnover_by_state(name, state)
        if not sub.empty: turn_rows.append(sub)
        all_state_metrics[name] = state_metrics(name, state)
    turn_df = pd.concat(turn_rows, ignore_index=True) if turn_rows else pd.DataFrame()
    turn_df.to_csv(OUT_DATA / "phase_eee_turnover_diagnostics.csv", index=False)

    # DDD2 vs DDD1 spike weeks (where the breach comes from)
    spike_df = turnover_spike_diff(DDD2, DDD1, state, top_n=15)
    spike_df.to_csv(OUT_DATA / "phase_eee_turnover_spike_weeks.csv")

    # Headline summary
    rows = []
    for name in PHASE_EEE_CANDIDATES + REFERENCES:
        h = headline(name)
        if h: rows.append(h)
    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_eee_candidate_metrics_full.csv", index=False)

    # state-by-state
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    state_rows = []
    for name in PHASE_EEE_CANDIDATES:
        ret = roc.load_portfolio_returns(name)
        if ret is None: continue
        df = pd.concat([ret["net_return"].rename("eee"), prod_ret["net_return"].rename("prod")], axis=1).join(
            state[["market_state"]], how="inner"
        ).dropna()
        for s, sub in df.groupby("market_state"):
            state_rows.append({"candidate": name, "state": s, "n_weeks": int(len(sub)),
                                "eee_mean_wkly": float(sub["eee"].mean()),
                                "prod_mean_wkly": float(sub["prod"].mean()),
                                "delta_mean_wkly": float(sub["eee"].mean() - sub["prod"].mean()),
                                "eee_minus_prod_cumulative": float(((1+sub["eee"]).prod()-1) - ((1+sub["prod"]).prod()-1))})
    pd.DataFrame(state_rows).to_csv(roc.LAYER3_DIR / "phase_eee_state_summary.csv", index=False)

    # Selection
    best, rationale, recs = evaluate(summary, all_state_metrics)
    pd.DataFrame(recs).to_csv(OUT_DATA / "phase_eee_candidate_diagnostics.csv", index=False)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_eee_selection_table.csv", index=False)

    # Print
    print("\n=== Phase EEE candidate summary ===")
    print(summary[["name","full_ann_return","full_sharpe","full_max_drawdown","full_cvar_5","avg_BIL","avg_SPY","avg_turnover"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase EEE turnover by state (recovery_confirmed slice) ===")
    rc_turn = turn_df[turn_df["state"] == "recovery_confirmed"]
    print(rc_turn.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase EEE selection records ===")
    print(pd.DataFrame(recs)[["name","ann_imp_pp_vs_prod","sharpe_imp_vs_prod","sharpe_vs_ddd1","turnover_ratio_vs_prod","recovery_confirmed_ann_delta_pp_vs_prod","recovery_confirmed_ann_delta_pp_vs_ddd1","recovery_fragile_ann_delta_pp_vs_ddd1","stressed_panic_ann_delta_pp","passes_strict_gates","passes_challenger_track","passes_shadow_track","fail_reasons_strict"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase EEE — turnover-smoothed aggressive dual cap",
        "candidates": PHASE_EEE_CANDIDATES,
        "production_pin": PRODUCTION, "shadow_pin": SHADOW,
        "ddd1_reference": DDD1, "ddd2_reference": DDD2,
        "best_candidate": best, "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_eee_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase EEE artifacts.")
    return best


if __name__ == "__main__":
    main()
