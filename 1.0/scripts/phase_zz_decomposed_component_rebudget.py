"""Phase ZZ — Decomposed-component allocator rebudgeting.

Phase YY decomposed `composite_regime_conditioned` into three explicit
components (offense / defense / cash) and produced
`improved_phaseyy_conservative_decomposition`, which improved the full
window Sharpe from 0.8953 → 0.9369 and MDD from -13.98% → -11.75% but
materially worsened recovery_confirmed (-1.04pp ann return, -0.168 Sharpe)
and recovery_fragile (-1.08pp, -0.301 Sharpe).

The diagnosis (from the user-supplied YY component diagnostics): in
recovery states the composite family was 28-31% offense / 48-50% defense
/ 18-24% cash even though the component returns clearly favored offense
(recovery_confirmed offense Sharpe 2.52 vs defense 1.75; recovery_fragile
offense Sharpe 3.31 vs defense 1.15).

Phase ZZ keeps the YY decomposed architecture and rebudgets the
offense/defense bucket targets in the recovery states (and optionally
strong_neutral) to repair the recovery underperformance while preserving
YY's full-window Sharpe/MDD advantage. Stressed_panic, calm_trend, and
the cash component machinery are unchanged.

Four candidates (≤4 per spec):
  ZZ1 = improved_phasezz_recovery_offense_rebudget
  ZZ2 = improved_phasezz_recovery_neutral_offense_rebudget
  ZZ3 = improved_phasezz_confirmed_freer_fragile_conservative
  ZZ4 = improved_phasezz_conservative_decomposition_repair

All candidates are produced via the production construction pipeline
through new tilt-mode branches in `_apply_phase_yy_decomposition_architecture`.
No post-hoc reconstruction. No ML, no Phase CC features.
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
VV_REFERENCE = "improved_phasevv_recovery_neutral_budget_aware_overlay"

ZZ1 = "improved_phasezz_recovery_offense_rebudget"
ZZ2 = "improved_phasezz_recovery_neutral_offense_rebudget"
ZZ3 = "improved_phasezz_confirmed_freer_fragile_conservative"
ZZ4 = "improved_phasezz_conservative_decomposition_repair"
PHASE_ZZ_CANDIDATES = [ZZ1, ZZ2, ZZ3, ZZ4]

OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"
COMPOSITE_FAMILY = [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]
OFFENSIVE_SLEEVES = ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", OFFENSE_COMPONENT]
DEFENSIVE_SLEEVES = ["taa_10m_sma", DEFENSE_COMPONENT]

OUT_DATA = roc.ROOT / "data" / "research" / "phase_zz_decomposed_component_rebudget"
OUT_DATA.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# subprocess invocation
# ----------------------------------------------------------------------

def run_production_path() -> None:
    targets = list(PHASE_ZZ_CANDIDATES) + [PRODUCTION, YY_BEST]
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print(f"[Phase ZZ] invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
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


# ----------------------------------------------------------------------
# loaders + helpers
# ----------------------------------------------------------------------

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
    out = {
        "name": name,
        "full_ann_return": full_m["ann_return"], "full_ann_vol": full_m["ann_vol"],
        "full_sharpe": full_m["sharpe"], "full_max_drawdown": full_m["max_drawdown"],
        "full_cvar_5": full_m["cvar_5"], "full_calmar": full_m["calmar"],
        "holdout_ann_return": hold_m["ann_return"], "holdout_sharpe": hold_m["sharpe"],
        "holdout_max_drawdown": hold_m["max_drawdown"],
    }
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
        # Composite-family components
        for c in COMPOSITE_FAMILY:
            out[f"avg_{c}"] = float(sw[c].mean()) if c in sw.columns else float("nan")
    if "turnover" in ret.columns and pd.isna(out.get("avg_turnover", float("nan"))):
        out["avg_turnover"] = float(ret["turnover"].mean())
    return out


def state_breakdown(name: str, prod_net: pd.Series, state: pd.DataFrame) -> pd.DataFrame:
    ret = roc.load_portfolio_returns(name)
    sw = roc.load_portfolio_sleeve_weights(name)
    if ret is None: return pd.DataFrame()
    cand_net = ret["net_return"]
    df = pd.concat([cand_net.rename("zz"), prod_net.rename("prod")], axis=1).join(
        state[["market_state"]], how="inner"
    ).dropna()
    rows = []
    for s, sub in df.groupby("market_state"):
        row = {"candidate": name, "state": s, "n_weeks": int(len(sub)),
                "zz_mean_wkly": float(sub["zz"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "delta_mean_wkly": float(sub["zz"].mean() - sub["prod"].mean()),
                "zz_minus_prod_cumulative": float(((1+sub["zz"]).prod()-1) - ((1+sub["prod"]).prod()-1))}
        # Component weights by state for this candidate
        if sw is not None:
            sw_state = sw.reindex(sub.index)
            for c in COMPOSITE_FAMILY:
                row[f"avg_{c}"] = float(sw_state[c].mean()) if c in sw_state.columns else float("nan")
            off = [c for c in OFFENSIVE_SLEEVES if c in sw_state.columns]
            defe = [c for c in DEFENSIVE_SLEEVES if c in sw_state.columns]
            row["avg_offensive_sleeve"] = float(sw_state[off].sum(axis=1).mean()) if off else float("nan")
            row["avg_defensive_sleeve"] = float(sw_state[defe].sum(axis=1).mean()) if defe else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def state_ann_metrics(name: str, state: pd.DataFrame) -> dict:
    """Annualised return + Sharpe per state for `name`."""
    ret = roc.load_portfolio_returns(name)
    if ret is None: return {}
    df = ret[["net_return"]].join(state[["market_state"]], how="inner").dropna()
    out = {}
    for s, sub in df.groupby("market_state"):
        n = sub["net_return"]
        out[s] = {"ann_return": roc.annualised_return(n), "sharpe": roc.sharpe(n),
                   "max_dd": roc.max_drawdown(n), "n_weeks": int(len(sub))}
    return out


# ----------------------------------------------------------------------
# selection
# ----------------------------------------------------------------------

def evaluate_candidates(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_ZZ_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    yy = summary[summary["name"] == YY_BEST]
    yy_sharpe = float(yy.iloc[0]["full_sharpe"]) if not yy.empty else float("nan")

    # state-level for each candidate
    state = load_state()
    prod_state_metrics = state_ann_metrics(PRODUCTION, state)
    rows = []
    for _, r in cands.iterrows():
        name = r["name"]
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        sharpe_vs_yy = r["full_sharpe"] - yy_sharpe if pd.notna(yy_sharpe) else float("nan")
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        spy_inc_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100

        cand_state_metrics = state_ann_metrics(name, state)
        # Specific state checks
        sp_d = (cand_state_metrics.get("stressed_panic", {}).get("ann_return", float("nan"))
                - prod_state_metrics.get("stressed_panic", {}).get("ann_return", float("nan"))) * 100
        rc_d = (cand_state_metrics.get("recovery_confirmed", {}).get("ann_return", float("nan"))
                - prod_state_metrics.get("recovery_confirmed", {}).get("ann_return", float("nan"))) * 100
        rf_d = (cand_state_metrics.get("recovery_fragile", {}).get("ann_return", float("nan"))
                - prod_state_metrics.get("recovery_fragile", {}).get("ann_return", float("nan"))) * 100
        rc_sh = cand_state_metrics.get("recovery_confirmed", {}).get("sharpe", float("nan")) - prod_state_metrics.get("recovery_confirmed", {}).get("sharpe", float("nan"))
        rf_sh = cand_state_metrics.get("recovery_fragile", {}).get("sharpe", float("nan")) - prod_state_metrics.get("recovery_fragile", {}).get("sharpe", float("nan"))

        # Decomposition still in effect: explicit cash sleeve > 0 (decomposition writes cash to its own bucket)
        decomposition_intact = pd.notna(r.get("avg_explicit_cash_sleeve")) and float(r.get("avg_explicit_cash_sleeve", 0.0)) > 0.001

        # Selection gates
        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_sharpe_vs_yy = (np.isnan(sharpe_vs_yy)) or (sharpe_vs_yy >= -0.02)  # remain competitive with YY
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_sp = (np.isnan(sp_d) or sp_d >= -0.30)
        cond_rc = (np.isnan(rc_d) or rc_d >= -0.30)
        cond_rf = (np.isnan(rf_d) or rf_d >= -0.30)
        cond_hidden_beta = not (spy_inc_pp > 1.0 and ann_imp_pp < 0.20)
        cond_decomposition = decomposition_intact

        passes_strict = all([cond_drag, cond_sharpe, cond_sharpe_vs_yy, cond_mdd, cond_cvar,
                              cond_turn, cond_sp, cond_rc, cond_rf, cond_hidden_beta, cond_decomposition])

        # Shadow-track passes: improvement vs production AND repairs at least one recovery state
        repairs_at_least_one_recovery = (rc_d >= -0.30) or (rf_d >= -0.30)
        cond_shadow = (
            (sharpe_imp > 0) and (ann_imp_pp >= -0.30) and
            cond_sp and cond_decomposition and repairs_at_least_one_recovery
        )

        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"sharpe_vs_YY<-0.02 ({sharpe_vs_yy:+.4f})" if not cond_sharpe_vs_yy else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"stressed_panic worse ({sp_d:+.2f}pp ann)" if not cond_sp else "",
            f"recovery_confirmed not repaired ({rc_d:+.2f}pp ann)" if not cond_rc else "",
            f"recovery_fragile not repaired ({rf_d:+.2f}pp ann)" if not cond_rf else "",
            f"hidden beta SPY +{spy_inc_pp:+.2f}pp" if not cond_hidden_beta else "",
            f"decomposition not intact" if not cond_decomposition else "",
        ])) or "none"

        rows.append({
            "name": name, "ann_imp_pp_vs_prod": ann_imp_pp, "sharpe_imp_vs_prod": sharpe_imp,
            "sharpe_vs_yy": sharpe_vs_yy, "mdd_imp_pp_vs_prod": mdd_imp_pp,
            "cvar_imp_pp_vs_prod": cvar_imp_pp, "turnover_ratio_vs_prod": turn_ratio,
            "spy_inc_pp_vs_prod": spy_inc_pp, "bil_inc_pp_vs_prod": bil_inc_pp,
            "stressed_panic_ann_delta_pp": sp_d, "recovery_confirmed_ann_delta_pp": rc_d,
            "recovery_fragile_ann_delta_pp": rf_d, "recovery_confirmed_sharpe_delta": rc_sh,
            "recovery_fragile_sharpe_delta": rf_sh,
            "decomposition_intact": cond_decomposition,
            "passes_strict_gates": passes_strict,
            "passes_shadow_track": cond_shadow,
            "fail_reasons_strict": fail,
        })
    decision = pd.DataFrame(rows)
    strict_pass = decision[decision["passes_strict_gates"]]
    if not strict_pass.empty:
        best = strict_pass.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        rationale = f"Selected {best['name']} as PRODUCTION CHALLENGER PENDING HUMAN REVIEW: passes all strict gates."
        return best["name"], rationale, decision.to_dict("records")
    shadow_pass = decision[decision["passes_shadow_track"]]
    if not shadow_pass.empty:
        best = shadow_pass.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
        rationale = f"Selected {best['name']} as KEEP AS SHADOW: improvement vs production with at least one recovery state repaired."
        return best["name"], rationale, decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"], ascending=[False, False]).iloc[0]
    rationale = f"NO Phase ZZ candidate passes strict OR shadow gates. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons_strict']}."
    return "", rationale, decision.to_dict("records")


# ----------------------------------------------------------------------
# Part A — diagnosis
# ----------------------------------------------------------------------

def part_a_diagnosis(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows_weights = []
    rows_returns = []
    for name in [PRODUCTION, YY_BEST] + PHASE_ZZ_CANDIDATES:
        ret = roc.load_portfolio_returns(name)
        sw = roc.load_portfolio_sleeve_weights(name)
        if ret is None or sw is None:
            continue
        net = ret["net_return"]
        df = sw.join(state[["market_state"]], how="inner").dropna(subset=["market_state"])
        for s, sub in df.groupby("market_state"):
            row = {"version": name, "state": s, "n_weeks": int(len(sub))}
            for c in COMPOSITE_FAMILY:
                row[f"avg_{c}"] = float(sub[c].mean()) if c in sub.columns else float("nan")
            off = [c for c in OFFENSIVE_SLEEVES if c in sub.columns]
            defe = [c for c in DEFENSIVE_SLEEVES if c in sub.columns]
            cash_col = [c for c in sub.columns if c.startswith("cash::")]
            row["avg_offensive_total"] = float(sub[off].sum(axis=1).mean()) if off else float("nan")
            row["avg_defensive_total"] = float(sub[defe].sum(axis=1).mean()) if defe else float("nan")
            row["avg_explicit_cash"] = float(sub[cash_col].sum(axis=1).mean()) if cash_col else float("nan")
            rows_weights.append(row)
        # state-level returns
        ret_state = ret[["net_return"]].join(state[["market_state"]], how="inner")
        for s, sub in ret_state.groupby("market_state"):
            n = sub["net_return"]
            rows_returns.append({"version": name, "state": s, "n_weeks": int(len(sub)),
                                  "ann_return": roc.annualised_return(n),
                                  "sharpe": roc.sharpe(n), "max_dd": roc.max_drawdown(n)})
    weights_df = pd.DataFrame(rows_weights)
    returns_df = pd.DataFrame(rows_returns)
    weights_df.to_csv(OUT_DATA / "phase_zz_component_weight_by_state.csv", index=False)
    returns_df.to_csv(OUT_DATA / "phase_zz_component_return_contribution_by_state.csv", index=False)

    # Recovery over-defense diagnostic: for each version, recovery_* defense vs offense weight
    rows_diag = []
    for name in [PRODUCTION, YY_BEST] + PHASE_ZZ_CANDIDATES:
        sub = weights_df[weights_df["version"] == name]
        for state_name in ["recovery_confirmed", "recovery_fragile"]:
            row = sub[sub["state"] == state_name]
            if row.empty: continue
            row = row.iloc[0]
            ratio = (row["avg_defensive_total"] / row["avg_offensive_total"]
                     if row["avg_offensive_total"] > 0 else float("nan"))
            rows_diag.append({
                "version": name, "state": state_name,
                "avg_offensive_total": row["avg_offensive_total"],
                "avg_defensive_total": row["avg_defensive_total"],
                "avg_explicit_cash": row["avg_explicit_cash"],
                "defense_to_offense_ratio": ratio,
            })
    diag_df = pd.DataFrame(rows_diag)
    diag_df.to_csv(OUT_DATA / "phase_zz_recovery_overdefense_diagnostics.csv", index=False)
    return weights_df, returns_df, diag_df


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    if "--no-rebuild" not in sys.argv:
        run_production_path()
    else:
        print("--no-rebuild: using existing files")

    state = load_state()

    # Part A — diagnosis
    print("[Phase ZZ Part A] Component weight + return diagnostics...")
    weights_df, returns_df, diag_df = part_a_diagnosis(state)

    # Headline summary
    rows = []
    for name in PHASE_ZZ_CANDIDATES + [PRODUCTION, YY_BEST]:
        h = headline(name)
        if h:
            rows.append(h)
    # Try VV reference if present
    vv_path = roc.LAYER3_DIR / f"portfolio_version_returns_{VV_REFERENCE}.csv"
    if vv_path.exists():
        rows.append(headline(VV_REFERENCE))
    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_zz_candidate_metrics_full.csv", index=False)

    # State-by-state
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns missing")
    state_rows = []
    for name in PHASE_ZZ_CANDIDATES:
        sb = state_breakdown(name, prod_ret["net_return"], state)
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    state_df.to_csv(roc.LAYER3_DIR / "phase_zz_state_summary.csv", index=False)

    # Selection
    best, rationale, recs = evaluate_candidates(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_zz_selection_table.csv", index=False)
    pd.DataFrame(recs).to_csv(OUT_DATA / "phase_zz_candidate_diagnostics.csv", index=False)

    print("\n=== Phase ZZ candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== Phase ZZ recovery over-defense diagnostics (vs production / YY) ===")
    print(diag_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== Phase ZZ selection ===")
    print(pd.DataFrame(recs).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase ZZ — Decomposed-component allocator rebudgeting",
        "candidates": PHASE_ZZ_CANDIDATES,
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "yy_reference": YY_BEST,
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_zz_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase ZZ artifacts.")
    return best


if __name__ == "__main__":
    main()
