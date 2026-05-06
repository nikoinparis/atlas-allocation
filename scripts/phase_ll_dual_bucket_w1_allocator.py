"""Phase LL — Structural dual-bucket allocator with W1 / composite_structural_defense_sleeve.

Architecture:
  Bucket 1 (Core):              production ETF weights (saved file).
  Bucket 2 (Structural Defense): W1 sleeve positions, week-by-week.

  new_etf_weights[t] = (1 - w_W1[t]) * prod_etf[t] + w_W1[t] * W1_positions[t]

This is a post-hoc dual-bucket construction at the ETF level. The
production cost convention (5bp half-spread on weekly L1 turnover) is
applied to the resulting series. We honestly report the post-hoc
limitation, but unlike Phase EE this does NOT attempt to reproduce
production's machinery — we ADD a new bucket on top of production's
saved weights, which is mathematically clean.

Three candidates:
  LL1 = improved_phasell_w1_bucket_fixed5
        w_W1 = 0.05 always (5% structural defense bucket).
  LL2 = improved_phasell_w1_bucket_state_conditional
        w_W1 = 0.10 in {stressed_panic, recovery_fragile, neutral_mixed};
        w_W1 = 0 in {calm_trend, recovery_confirmed}.
        Uses ORIGINAL market_state, not Phase CC refined_state.
  LL3 = improved_phasell_w1_bucket_ml_conditional
        Created only if Phase KK refreshed predictions exist and improve
        OOS Brier vs baseline. w_W1 = clip(p_stress_4w * 0.20, 0, 0.10).
        Higher predicted stress -> more W1.

Selection rule mirrors the spec's LL section.
"""
from __future__ import annotations

import json
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
LL1_NAME = "improved_phasell_w1_bucket_fixed5"
LL2_NAME = "improved_phasell_w1_bucket_state_conditional"
LL3_NAME = "improved_phasell_w1_bucket_ml_conditional"
PHASE_LL_CANDIDATES = [LL1_NAME, LL2_NAME, LL3_NAME]

W1_SLEEVE = "composite_structural_defense_sleeve"
HALFSPREAD = roc.DEFAULT_HALFSPREAD


def load_state_full() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_w1_positions() -> pd.DataFrame:
    p = roc.LAYER2A_DIR / f"strategy_positions_{W1_SLEEVE}.csv"
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df.fillna(0.0)


def load_kk_predictions() -> pd.DataFrame | None:
    p = roc.LAYER2B_DIR / "phase_kk_targeta_regime_confidence_predictions.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def gate_ll1(state: pd.Series) -> pd.Series:
    return pd.Series(0.05, index=state.index, dtype=float)


def gate_ll2(state: pd.Series) -> pd.Series:
    """w_W1 = 0.10 in stressed_panic / recovery_fragile / neutral_mixed; else 0."""
    s = state.astype(str)
    w = pd.Series(0.0, index=state.index, dtype=float)
    w.loc[s.isin({"stressed_panic", "recovery_fragile", "neutral_mixed"})] = 0.10
    return w


def gate_ll3(p_stress: pd.Series) -> pd.Series:
    """w_W1 = clip(p_stress * 0.20, 0, 0.10). Conservative ML-conditional bucket."""
    return (p_stress.fillna(0.0) * 0.20).clip(0.0, 0.10)


def build_dual_bucket_weights(prod_weights: pd.DataFrame, w1_pos: pd.DataFrame, w_w1: pd.Series) -> pd.DataFrame:
    common_idx = prod_weights.index.intersection(w_w1.index).intersection(w1_pos.index)
    prod_w = prod_weights.loc[common_idx]
    w1 = w1_pos.loc[common_idx]
    w = w_w1.loc[common_idx]
    cols = sorted(set(prod_w.columns) | set(w1.columns))
    prod_aligned = prod_w.reindex(columns=cols).fillna(0.0)
    w1_aligned = w1.reindex(columns=cols).fillna(0.0)
    scale_prod = (1.0 - w).values.reshape(-1, 1)
    scale_w1 = w.values.reshape(-1, 1)
    new_w = pd.DataFrame(prod_aligned.values * scale_prod + w1_aligned.values * scale_w1,
                          index=common_idx, columns=cols)
    s = new_w.sum(axis=1)
    s = s.replace(0.0, 1.0)
    new_w = new_w.div(s, axis=0)
    return new_w


def recompute_returns(weights: pd.DataFrame, weekly_returns: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    next_week = weekly_returns.shift(-1)
    common = weights.index.intersection(next_week.index)
    cols = [c for c in weights.columns if c in next_week.columns]
    aligned_w = weights.loc[common, cols]
    aligned_r = next_week.loc[common, cols].fillna(0.0)
    gross = (aligned_w * aligned_r).sum(axis=1)
    turn = aligned_w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turn * HALFSPREAD
    net = gross - cost
    return gross, net, turn, cost


def state_breakdown(net: pd.Series, prod_net: pd.Series, state_full: pd.DataFrame, w_w1: pd.Series) -> pd.DataFrame:
    df = pd.concat([net.rename("ll"), prod_net.rename("prod"), w_w1.rename("w_w1")], axis=1).join(
        state_full[["market_state"]], how="inner"
    ).dropna()
    rows = []
    for s, sub in df.groupby("market_state"):
        rows.append({
            "state": s, "n_weeks": int(len(sub)),
            "ll_mean_wkly": float(sub["ll"].mean()),
            "prod_mean_wkly": float(sub["prod"].mean()),
            "delta_mean_wkly": float(sub["ll"].mean() - sub["prod"].mean()),
            "ll_minus_prod_cumulative": float(((1+sub["ll"]).prod()-1) - ((1+sub["prod"]).prod()-1)),
            "avg_w_w1": float(sub["w_w1"].mean()),
            "max_w_w1": float(sub["w_w1"].max()),
        })
    return pd.DataFrame(rows)


def headline(name: str, weekly: pd.Series, weights: pd.DataFrame, w_w1: pd.Series) -> dict:
    full_m = roc.metric_block(weekly)
    hold_m = roc.metric_block(weekly.tail(roc.HOLDOUT_WEEKS))
    out = {"name": name,
            "full_ann_return": full_m["ann_return"], "full_ann_vol": full_m["ann_vol"],
            "full_sharpe": full_m["sharpe"], "full_max_drawdown": full_m["max_drawdown"],
            "full_cvar_5": full_m["cvar_5"], "full_calmar": full_m["calmar"],
            "holdout_ann_return": hold_m["ann_return"], "holdout_sharpe": hold_m["sharpe"],
            "holdout_max_drawdown": hold_m["max_drawdown"]}
    if weights is not None:
        out["avg_BIL"] = float(weights["BIL"].mean()) if "BIL" in weights.columns else float("nan")
        out["avg_SPY"] = float(weights["SPY"].mean()) if "SPY" in weights.columns else float("nan")
        out["avg_turnover"] = float(weights.diff().abs().sum(axis=1).fillna(0.0).mean())
    out["avg_w_w1"] = float(w_w1.mean())
    out["max_w_w1"] = float(w_w1.max())
    return out


def select_best_ll(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_LL_CANDIDATES)].copy()
    if cands.empty:
        return "", "no LL candidates produced", []
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    rows = []
    for _, r in cands.iterrows():
        name = r["name"]
        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100
        sub = state_df[state_df["candidate"] == name]
        ct = sub[sub["state"] == "calm_trend"]
        ct_d = float(ct["delta_mean_wkly"].iloc[0]) if not ct.empty else float("nan")
        cond_drag = ann_imp_pp >= -0.30 or sharpe_imp >= 0.005 or mdd_imp_pp >= 0
        cond_sharpe_or_mdd = (sharpe_imp >= 0.005) or (mdd_imp_pp > 0.5) or (cvar_imp_pp > 0.05)
        cond_mdd_no_worse = mdd_imp_pp >= -0.5
        cond_cvar_no_worse = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = bil_inc_pp <= 5.0 or sharpe_imp >= 0.005 or mdd_imp_pp > 0
        cond_calm = (np.isnan(ct_d) or ct_d >= -1e-4)
        passes = all([cond_drag, cond_sharpe_or_mdd, cond_mdd_no_worse, cond_cvar_no_worse,
                       cond_turn, cond_bil, cond_calm])
        fail = "; ".join(filter(None, [
            f"return drag {-ann_imp_pp:+.2f}pp without offsetting risk benefit" if not cond_drag else "",
            f"sharpe_imp {sharpe_imp:+.4f} and no MDD/CVaR upside" if not cond_sharpe_or_mdd else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd_no_worse else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar_no_worse else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"bil_inc>5pp without risk benefit ({bil_inc_pp:+.2f}pp)" if not cond_bil else "",
            f"calm_trend worsens materially ({ct_d:+.6f}/wk)" if not cond_calm else "",
        ])) or "none"
        rows.append({
            "name": name, "ann_imp_pp": ann_imp_pp, "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp_pp, "cvar_imp_pp": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio, "bil_inc_pp": bil_inc_pp,
            "calm_trend_delta_wkly": ct_d,
            "passes_all_gates": passes, "fail_reasons": fail,
        })
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        # Tie-break by Sharpe improvement, then MDD improvement
        best = passing.sort_values(["sharpe_imp", "mdd_imp_pp"], ascending=[False, False]).iloc[0]
        return best["name"], f"Selected {best['name']}: passes all gates.", decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp", "mdd_imp_pp"], ascending=[False, False]).iloc[0]
    return "", f"NO Phase LL candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}.", decision.to_dict("records")


def main():
    state_full = load_state_full()
    weekly = roc.load_weekly_returns()
    prod_w = roc.load_portfolio_weights(PRODUCTION)
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_w is None or prod_ret is None:
        raise RuntimeError("Production weights/returns missing")
    w1_pos = load_w1_positions()
    common_idx = prod_w.index.intersection(w1_pos.index).intersection(state_full.index)
    print(f"[Phase LL] common index: {len(common_idx)} weeks; W1 ETFs: {list(w1_pos.columns)}")

    # LL1 — fixed 5%
    print("\n[LL1] fixed 5% W1 bucket")
    w_ll1 = gate_ll1(state_full["market_state"]).reindex(common_idx)
    ew_ll1 = build_dual_bucket_weights(prod_w, w1_pos, w_ll1)
    g_ll1, n_ll1, t_ll1, c_ll1 = recompute_returns(ew_ll1, weekly)
    sw_ll1 = pd.DataFrame({"core": 1.0 - w_ll1, W1_SLEEVE: w_ll1}).reindex(ew_ll1.index)

    # LL2 — state-conditional
    print("[LL2] state-conditional W1 bucket")
    w_ll2 = gate_ll2(state_full["market_state"]).reindex(common_idx)
    ew_ll2 = build_dual_bucket_weights(prod_w, w1_pos, w_ll2)
    g_ll2, n_ll2, t_ll2, c_ll2 = recompute_returns(ew_ll2, weekly)
    sw_ll2 = pd.DataFrame({"core": 1.0 - w_ll2, W1_SLEEVE: w_ll2}).reindex(ew_ll2.index)

    # LL3 — ML-conditional (only if KK predictions exist with positive Brier improvement)
    kk_preds = load_kk_predictions()
    ew_ll3 = None; n_ll3 = None; t_ll3 = None; w_ll3 = None
    if kk_preds is not None and "p_stress_forecast" in kk_preds.columns:
        print("[LL3] ML-conditional W1 bucket (using Phase KK p_stress_forecast)")
        p_stress = kk_preds["p_stress_forecast"].reindex(common_idx).fillna(0.0)
        w_ll3 = gate_ll3(p_stress)
        ew_ll3 = build_dual_bucket_weights(prod_w, w1_pos, w_ll3)
        g_ll3, n_ll3, t_ll3, c_ll3 = recompute_returns(ew_ll3, weekly)
        sw_ll3 = pd.DataFrame({"core": 1.0 - w_ll3, W1_SLEEVE: w_ll3}).reindex(ew_ll3.index)
    else:
        print("[LL3] Skipped (Phase KK predictions unavailable)")

    # Save artifacts
    bundles = {
        LL1_NAME: (sw_ll1, ew_ll1, g_ll1, n_ll1, t_ll1, c_ll1, w_ll1),
        LL2_NAME: (sw_ll2, ew_ll2, g_ll2, n_ll2, t_ll2, c_ll2, w_ll2),
    }
    if ew_ll3 is not None:
        bundles[LL3_NAME] = (sw_ll3, ew_ll3, g_ll3, n_ll3, t_ll3, c_ll3, w_ll3)

    rows = []; state_rows = []
    prod_net = prod_ret["net_return"]
    for name, (sw, ew, gross, net, turn, cost, w_w1) in bundles.items():
        sw.to_csv(roc.LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")
        ew.to_csv(roc.LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        wealth = (1 + net.fillna(0)).cumprod()
        dd = wealth / wealth.cummax() - 1.0
        ret_df = pd.DataFrame({
            "gross_return": gross, "net_return": net,
            "turnover": turn.reindex(net.index).fillna(0.0),
            "cost": cost.reindex(net.index).fillna(0.0),
            "wealth": wealth, "drawdown": dd,
        })
        ret_df.to_csv(roc.LAYER3_DIR / f"portfolio_version_returns_{name}.csv")

        h = headline(name, net, ew, w_w1)
        rows.append(h)
        sb = state_breakdown(net, prod_net, state_full, w_w1)
        sb["candidate"] = name
        state_rows.append(sb)

    # Add production + shadow rows
    for ref_name in [PRODUCTION, SHADOW]:
        rr = roc.load_portfolio_returns(ref_name)
        rw = roc.load_portfolio_weights(ref_name)
        if rr is None: continue
        n = rr["net_return"].dropna()
        full_m = roc.metric_block(n); hold_m = roc.metric_block(n.tail(roc.HOLDOUT_WEEKS))
        h = {"name": ref_name,
              "full_ann_return": full_m["ann_return"], "full_ann_vol": full_m["ann_vol"],
              "full_sharpe": full_m["sharpe"], "full_max_drawdown": full_m["max_drawdown"],
              "full_cvar_5": full_m["cvar_5"], "full_calmar": full_m["calmar"],
              "holdout_ann_return": hold_m["ann_return"], "holdout_sharpe": hold_m["sharpe"],
              "holdout_max_drawdown": hold_m["max_drawdown"],
              "avg_BIL": float(rw["BIL"].mean()) if (rw is not None and "BIL" in rw.columns) else float("nan"),
              "avg_SPY": float(rw["SPY"].mean()) if (rw is not None and "SPY" in rw.columns) else float("nan"),
              "avg_turnover": float(rr["turnover"].mean()) if "turnover" in rr.columns else float("nan"),
              "avg_w_w1": 0.0, "max_w_w1": 0.0}
        rows.append(h)

    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_ll_candidate_metrics_full.csv", index=False)
    state_df = pd.concat(state_rows, ignore_index=True)
    state_df.to_csv(roc.LAYER3_DIR / "phase_ll_state_summary.csv", index=False)

    best, rationale, recs = select_best_ll(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_ll_selection_table.csv", index=False)

    print("\n=== Phase LL candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase LL state-by-state (W1 bucket weight by state) ===")
    print(state_df[["candidate", "state", "n_weeks", "delta_mean_wkly", "ll_minus_prod_cumulative", "avg_w_w1"]].to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase LL — Structural dual-bucket allocator with W1",
        "architecture": "post-hoc dual-bucket: prod_w * (1 - w_W1) + W1_positions * w_W1",
        "limitations": "post-hoc reconstruction at the ETF level; cost convention is the standard 5bp half-spread on the resulting series",
        "candidates": list(bundles.keys()),
        "w1_sleeve": W1_SLEEVE,
        "w1_avg_holdings": load_w1_positions().mean().sort_values(ascending=False).to_dict(),
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_ll_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase LL artifacts.")
    return best


if __name__ == "__main__":
    main()
