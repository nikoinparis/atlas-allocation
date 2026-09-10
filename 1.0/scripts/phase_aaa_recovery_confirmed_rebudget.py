"""Phase AAA — recovery_confirmed-only deeper rebudget on top of Phase ZZ2.

Phase ZZ2 (`improved_phasezz_recovery_neutral_offense_rebudget`) is the
strongest architecture-reference shadow: ann return +0.19pp, Sharpe
+0.05, MDD +2.23pp, CVaR +0.10pp vs production, with no hidden beta
(SPY -0.99pp). It still leaves recovery_confirmed at -0.91pp ann return
vs production. Phase AAA is the targeted blocker-removal phase: keep
ZZ2's full-window profile and recovery_fragile repair, push the
recovery_confirmed gap closed.

Four candidates (≤4 per spec):
  AAA1 = improved_phaseaaa_confirmed_offense_escalation
  AAA2 = improved_phaseaaa_confirmed_offense_mix_tilt
  AAA3 = improved_phaseaaa_confirmed_defense_composition_repair
  AAA4 = improved_phaseaaa_confirmed_only_combined_repair

All produced via the production construction pipeline through new tilt
branches in `_apply_phase_yy_decomposition_architecture`. recovery_fragile
and strong_neutral are identical to ZZ2 in all four candidates.
stressed_panic protected upstream.
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

AAA1 = "improved_phaseaaa_confirmed_offense_escalation"
AAA2 = "improved_phaseaaa_confirmed_offense_mix_tilt"
AAA3 = "improved_phaseaaa_confirmed_defense_composition_repair"
AAA4 = "improved_phaseaaa_confirmed_only_combined_repair"
PHASE_AAA_CANDIDATES = [AAA1, AAA2, AAA3, AAA4]

OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"
COMPOSITE_FAMILY = [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]
OFFENSIVE_SLEEVES = ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", OFFENSE_COMPONENT]
DEFENSIVE_SLEEVES = ["taa_10m_sma", DEFENSE_COMPONENT]

OUT_DATA = roc.ROOT / "data" / "research" / "phase_aaa_recovery_confirmed_rebudget"
OUT_DATA.mkdir(parents=True, exist_ok=True)


def run_production_path() -> None:
    targets = list(PHASE_AAA_CANDIDATES) + [PRODUCTION, ZZ2, YY_BEST]
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print(f"[Phase AAA] invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 25 lines) ---")
    for line in (res.stdout or "").splitlines()[-25:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 40 lines) ---")
        for line in (res.stderr or "").splitlines()[-40:]:
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
        for c in COMPOSITE_FAMILY:
            row[f"avg_{c}"] = float(sub[c].mean()) if c in sub.columns else float("nan")
        off = [c for c in OFFENSIVE_SLEEVES if c in sub.columns]
        defe = [c for c in DEFENSIVE_SLEEVES if c in sub.columns]
        cash_col = [c for c in sub.columns if c.startswith("cash::")]
        row["avg_offensive_total"] = float(sub[off].sum(axis=1).mean()) if off else float("nan")
        row["avg_defensive_total"] = float(sub[defe].sum(axis=1).mean()) if defe else float("nan")
        row["avg_explicit_cash"] = float(sub[cash_col].sum(axis=1).mean()) if cash_col else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def state_etf_exposure(name: str, state: pd.DataFrame) -> pd.DataFrame:
    """ETF-level exposure by state for hidden-beta / hidden-cash check."""
    w = roc.load_portfolio_weights(name)
    if w is None: return pd.DataFrame()
    joined = w.join(state[["market_state"]], how="inner").dropna(subset=["market_state"])
    rows = []
    for s, sub in joined.groupby("market_state"):
        row = {"version": name, "state": s, "n_weeks": int(len(sub))}
        for tic in ["SPY", "BIL", "QQQ", "IWM", "GLD", "TLT", "HYG", "LQD"]:
            if tic in sub.columns:
                row[f"avg_{tic}"] = float(sub[tic].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate(summary: pd.DataFrame, all_state_metrics: dict[str, dict]) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_AAA_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    zz2 = summary[summary["name"] == ZZ2]
    zz2_d = zz2.iloc[0].to_dict() if not zz2.empty else {}
    rows = []
    prod_state = all_state_metrics.get(PRODUCTION, {})
    zz2_state = all_state_metrics.get(ZZ2, {})

    for _, r in cands.iterrows():
        name = r["name"]
        cand_state = all_state_metrics.get(name, {})
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        sharpe_vs_zz2 = r["full_sharpe"] - zz2_d.get("full_sharpe", float("nan"))
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        spy_inc_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100

        def state_d(state_name):
            cand = cand_state.get(state_name, {})
            p = prod_state.get(state_name, {})
            ann = (cand.get("ann_return", float("nan")) - p.get("ann_return", float("nan"))) * 100
            sh = cand.get("sharpe", float("nan")) - p.get("sharpe", float("nan"))
            return ann, sh
        sp_ann, sp_sh = state_d("stressed_panic")
        rc_ann, rc_sh = state_d("recovery_confirmed")
        rf_ann, rf_sh = state_d("recovery_fragile")
        # vs ZZ2
        z = zz2_state.get("recovery_confirmed", {}); zf = zz2_state.get("recovery_fragile", {})
        rc_vs_zz2 = (cand_state.get("recovery_confirmed", {}).get("ann_return", float("nan")) - z.get("ann_return", float("nan"))) * 100
        rf_vs_zz2 = (cand_state.get("recovery_fragile", {}).get("ann_return", float("nan")) - zf.get("ann_return", float("nan"))) * 100

        decomposition_intact = pd.notna(r.get("avg_explicit_cash_sleeve")) and float(r.get("avg_explicit_cash_sleeve", 0.0)) > 0.001

        # Strict gates per spec
        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_sharpe_vs_zz2 = (np.isnan(sharpe_vs_zz2)) or (sharpe_vs_zz2 >= -0.02)
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_sp = (np.isnan(sp_ann) or sp_ann >= -0.30)
        cond_rf_no_regression = (np.isnan(rf_vs_zz2) or rf_vs_zz2 >= -0.30)
        cond_rc_improves_vs_zz2 = (np.isnan(rc_vs_zz2) or rc_vs_zz2 > 0.0)
        cond_hidden_beta = not (spy_inc_pp > 1.0 and ann_imp_pp < 0.20)
        cond_decomposition = decomposition_intact

        passes_strict = all([cond_drag, cond_sharpe, cond_sharpe_vs_zz2, cond_mdd, cond_cvar,
                              cond_turn, cond_sp, cond_rf_no_regression, cond_rc_improves_vs_zz2,
                              cond_hidden_beta, cond_decomposition])

        # PRODUCTION CHALLENGER PENDING HUMAN REVIEW track:
        # - Sharpe materially better than production
        # - mdd / cvar preserve or improve
        # - recovery_confirmed not materially worse than production
        # - recovery_fragile not materially worse than production
        cond_challenger_sharpe = sharpe_imp >= 0.020
        cond_challenger_mdd = mdd_imp_pp >= -0.10
        cond_challenger_cvar = cvar_imp_pp >= -0.02
        cond_challenger_rc = (np.isnan(rc_ann) or rc_ann >= -0.30)
        cond_challenger_rf = (np.isnan(rf_ann) or rf_ann >= -0.30)
        challenger_track = all([cond_challenger_sharpe, cond_challenger_mdd, cond_challenger_cvar,
                                  cond_challenger_rc, cond_challenger_rf, cond_hidden_beta, cond_decomposition])

        # Shadow track: improvement vs production AND repairs recovery_confirmed at least partially (vs ZZ2)
        repairs_rc_vs_zz2 = (not np.isnan(rc_vs_zz2)) and rc_vs_zz2 > 0.0
        cond_shadow = (
            (sharpe_imp > 0) and (ann_imp_pp >= -0.30) and cond_sp and cond_decomposition and
            (repairs_rc_vs_zz2 or cond_rc_improves_vs_zz2)
        )

        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"sharpe_vs_zz2<-0.02 ({sharpe_vs_zz2:+.4f})" if not cond_sharpe_vs_zz2 else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"stressed_panic worse ({sp_ann:+.2f}pp ann)" if not cond_sp else "",
            f"recovery_fragile regressed vs ZZ2 ({rf_vs_zz2:+.2f}pp ann)" if not cond_rf_no_regression else "",
            f"recovery_confirmed did not improve vs ZZ2 ({rc_vs_zz2:+.2f}pp ann)" if not cond_rc_improves_vs_zz2 else "",
            f"hidden beta SPY +{spy_inc_pp:+.2f}pp" if not cond_hidden_beta else "",
            f"decomposition not intact" if not cond_decomposition else "",
        ])) or "none"

        rows.append({
            "name": name, "ann_imp_pp_vs_prod": ann_imp_pp, "sharpe_imp_vs_prod": sharpe_imp,
            "sharpe_vs_zz2": sharpe_vs_zz2, "mdd_imp_pp_vs_prod": mdd_imp_pp,
            "cvar_imp_pp_vs_prod": cvar_imp_pp, "turnover_ratio_vs_prod": turn_ratio,
            "spy_inc_pp_vs_prod": spy_inc_pp, "bil_inc_pp_vs_prod": bil_inc_pp,
            "stressed_panic_ann_delta_pp": sp_ann,
            "recovery_confirmed_ann_delta_pp_vs_prod": rc_ann,
            "recovery_fragile_ann_delta_pp_vs_prod": rf_ann,
            "recovery_confirmed_ann_delta_pp_vs_zz2": rc_vs_zz2,
            "recovery_fragile_ann_delta_pp_vs_zz2": rf_vs_zz2,
            "decomposition_intact": cond_decomposition,
            "passes_strict_gates": passes_strict,
            "passes_challenger_track": challenger_track,
            "passes_shadow_track": cond_shadow,
            "fail_reasons_strict": fail,
        })
    decision = pd.DataFrame(rows)
    challenger = decision[decision["passes_challenger_track"]]
    if not challenger.empty:
        best = challenger.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        return best["name"], f"PRODUCTION CHALLENGER PENDING HUMAN REVIEW: {best['name']}", decision.to_dict("records")
    strict = decision[decision["passes_strict_gates"]]
    if not strict.empty:
        best = strict.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        return best["name"], f"Selected {best['name']} (strict gates passed; just below challenger threshold).", decision.to_dict("records")
    shadow = decision[decision["passes_shadow_track"]]
    if not shadow.empty:
        best = shadow.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        return best["name"], f"Selected {best['name']} as KEEP AS SHADOW: improves vs production with partial recovery_confirmed repair vs ZZ2.", decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
    return "", f"NO Phase AAA candidate passes any track. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons_strict']}.", decision.to_dict("records")


def main():
    if "--no-rebuild" not in sys.argv:
        run_production_path()
    else:
        print("--no-rebuild: using existing files")

    state = load_state()

    # Part A — diagnosis: component weights + state metrics + ETF exposure
    print("[Phase AAA Part A] component weight + state diagnostics...")
    rows_w = []; rows_etf = []
    for name in [PRODUCTION, YY_BEST, ZZ2] + PHASE_AAA_CANDIDATES:
        sw = state_weights(name, state)
        if not sw.empty: rows_w.append(sw)
        ee = state_etf_exposure(name, state)
        if not ee.empty: rows_etf.append(ee)
    weights_df = pd.concat(rows_w, ignore_index=True) if rows_w else pd.DataFrame()
    etf_df = pd.concat(rows_etf, ignore_index=True) if rows_etf else pd.DataFrame()
    weights_df.to_csv(OUT_DATA / "phase_aaa_recovery_confirmed_component_diagnostics.csv", index=False)
    etf_df.to_csv(OUT_DATA / "phase_aaa_recovery_confirmed_exposure_diagnostics.csv", index=False)

    # Headline
    rows = []
    for name in PHASE_AAA_CANDIDATES + [PRODUCTION, ZZ2, YY_BEST]:
        h = headline(name)
        if h: rows.append(h)
    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_aaa_candidate_metrics_full.csv", index=False)

    # state-by-state for each candidate vs production
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    state_rows = []
    all_state_metrics = {}
    for name in PHASE_AAA_CANDIDATES + [PRODUCTION, ZZ2, YY_BEST]:
        all_state_metrics[name] = state_metrics(name, state)
    for name in PHASE_AAA_CANDIDATES:
        ret = roc.load_portfolio_returns(name)
        if ret is None: continue
        cand_net = ret["net_return"]
        df = pd.concat([cand_net.rename("aaa"), prod_ret["net_return"].rename("prod")], axis=1).join(
            state[["market_state"]], how="inner"
        ).dropna()
        for s, sub in df.groupby("market_state"):
            state_rows.append({"candidate": name, "state": s, "n_weeks": int(len(sub)),
                                "aaa_mean_wkly": float(sub["aaa"].mean()),
                                "prod_mean_wkly": float(sub["prod"].mean()),
                                "delta_mean_wkly": float(sub["aaa"].mean() - sub["prod"].mean()),
                                "aaa_minus_prod_cumulative": float(((1+sub["aaa"]).prod()-1) - ((1+sub["prod"]).prod()-1))})
    state_df = pd.DataFrame(state_rows)
    state_df.to_csv(roc.LAYER3_DIR / "phase_aaa_state_summary.csv", index=False)

    best, rationale, recs = evaluate(summary, all_state_metrics)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_aaa_selection_table.csv", index=False)
    pd.DataFrame(recs).to_csv(OUT_DATA / "phase_aaa_candidate_diagnostics.csv", index=False)

    print("\n=== Phase AAA candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase AAA recovery_confirmed component diagnostics ===")
    rc_view = weights_df[weights_df["state"] == "recovery_confirmed"][[
        "version", "n_weeks", "avg_composite_regime_offense_component",
        "avg_composite_regime_defense_component",
        "avg_offensive_total", "avg_defensive_total", "avg_explicit_cash"]]
    print(rc_view.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase AAA selection ===")
    print(pd.DataFrame(recs).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase AAA — recovery_confirmed-only deeper rebudget",
        "candidates": PHASE_AAA_CANDIDATES,
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "yy_reference": YY_BEST,
        "zz2_reference": ZZ2,
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_aaa_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase AAA artifacts.")
    return best


if __name__ == "__main__":
    main()
