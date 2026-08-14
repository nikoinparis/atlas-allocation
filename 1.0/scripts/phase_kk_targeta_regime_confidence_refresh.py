"""Phase KK — Targeted Phase 2B ML refresh using Target A + Group A features only.

Phase JJ established that:
  * Light interpretable ML (logistic regression) wins.
  * Refined-state features hurt OOS.
  * Hard ML doesn't help on this dataset.
  * Target A (forward 4w stress_panic transition) is the most learnable target.

Phase KK builds on those findings and produces:
  * A clean walk-forward refreshed Target-A regime-confidence score (computed
    as 1 - p_stress_4w to align with production's existing higher = healthy
    convention).
  * Two portfolio candidates produced through the production pipeline:
      KK1 = improved_phasekk_targeta_confidence_replacement
      KK2 = improved_phasekk_targeta_confidence_blend25
  * No Phase CC features, no macro proxies. Group A only (15 features).
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

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, roc_auc_score, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
KK1_NAME = "improved_phasekk_targeta_confidence_replacement"
KK2_NAME = "improved_phasekk_targeta_confidence_blend25"
PHASE_KK_CANDIDATES = [KK1_NAME, KK2_NAME]

INITIAL_TRAIN_WEEKS = 260
RETRAIN_FREQ_WEEKS = 26
FORWARD_HORIZON_WEEKS = 4
TRAIN_MIN_POS = 5
RNG_SEED = 20260427

GROUP_A_REGIME = [
    "market_drawdown",
    "market_trend_positive",
    "breadth_sma_43",
    "breadth_26w_mom",
    "breadth_13w_mom",
    "breadth_change_4w",
    "canary_breadth_default",
    "recent_stress_26w",
    "transition_persistence_prob",
    "transition_good_state_prob",
    "transition_non_stress_prob",
    "avg_corr_risk_off_z",
]
GROUP_A_PHASE2B = ["p_regime_confidence", "p_transition_quality", "p_tail_risk"]
ALL_GROUP_A = GROUP_A_REGIME + GROUP_A_PHASE2B


def load_state_full() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_phase2b_predictions() -> pd.DataFrame:
    p = roc.LAYER2B_DIR / "phase2b_meta_predictions.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def build_dataset() -> tuple[pd.DataFrame, pd.Series]:
    state = load_state_full()
    p2b = load_phase2b_predictions()
    feat = pd.DataFrame(index=state.index)
    for c in GROUP_A_REGIME:
        if c in state.columns:
            feat[c] = state[c].astype(float)
    for c in GROUP_A_PHASE2B:
        if c in p2b.columns:
            feat[c] = p2b[c].reindex(state.index).astype(float)
    # 1-week causal lag
    feat = feat.shift(1).ffill()
    # Target A: forward 4w stressed_panic transition
    s = state["market_state"].astype(str)
    panic = (s == "stressed_panic").astype(float)
    fwd = panic.shift(-1).rolling(window=FORWARD_HORIZON_WEEKS, min_periods=FORWARD_HORIZON_WEEKS).max().shift(-(FORWARD_HORIZON_WEEKS - 1))
    return feat.dropna(how="all"), fwd.reindex(feat.index)


def walk_forward_logistic(X: pd.DataFrame, y: pd.Series) -> tuple[pd.Series, list[dict], dict]:
    indexed = X.index
    out = pd.Series(np.nan, index=y.index, dtype=float)
    fit_log = []
    Xs = X.astype(float).fillna(0)
    last_coefs = {}
    train_end = INITIAL_TRAIN_WEEKS
    while train_end < len(indexed):
        mask = pd.Series(False, index=indexed)
        mask.iloc[:train_end] = True
        mask = mask & y.notna() & Xs.notna().all(axis=1)
        y_train = y[mask]
        if y_train.sum() < TRAIN_MIN_POS or (y_train == 0).sum() < TRAIN_MIN_POS:
            train_end += RETRAIN_FREQ_WEEKS
            continue
        scaler = StandardScaler()
        X_train_arr = scaler.fit_transform(Xs[mask].values)
        y_train_arr = y_train.astype(int).values
        model = LogisticRegression(max_iter=1000, solver="liblinear", random_state=RNG_SEED)
        model.fit(X_train_arr, y_train_arr)
        last_coefs = {"date": str(indexed[train_end - 1])[:10],
                       "intercept": float(model.intercept_[0]),
                       **dict(zip(X.columns, model.coef_.ravel().tolist()))}
        score_end = min(train_end + RETRAIN_FREQ_WEEKS, len(indexed))
        score_idx = indexed[train_end:score_end]
        X_score = scaler.transform(Xs.reindex(score_idx).fillna(0).values)
        proba = model.predict_proba(X_score)[:, 1]
        out.loc[score_idx] = proba
        fit_log.append({"train_end": str(indexed[train_end - 1])[:10],
                         "n_train": int(len(y_train)), "pos_rate": float(y_train.mean())})
        train_end += RETRAIN_FREQ_WEEKS
    return out, fit_log, last_coefs


def metrics_oos(y_true: pd.Series, y_pred: pd.Series) -> dict:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p")], axis=1).dropna()
    if df.empty:
        return {"n_obs": 0, "brier": float("nan"), "auc": float("nan"), "log_loss": float("nan"),
                "pos_rate": float("nan"), "pred_mean": float("nan")}
    y = df["y"].astype(int).values
    p = df["p"].astype(float).clip(1e-6, 1 - 1e-6).values
    return {"n_obs": int(len(df)), "brier": float(brier_score_loss(y, p)),
            "auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan"),
            "log_loss": float(log_loss(y, p)) if len(set(y)) > 1 else float("nan"),
            "pos_rate": float(y.mean()), "pred_mean": float(p.mean())}


def calibration(y_true: pd.Series, y_pred: pd.Series, n_bins: int = 5) -> pd.DataFrame:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["bucket"] = pd.qcut(df["p"], q=n_bins, labels=False, duplicates="drop")
    return df.groupby("bucket").agg(n=("y", "count"), mean_pred=("p", "mean"),
                                      mean_actual=("y", "mean")).reset_index()


def stability(y_true: pd.Series, y_pred: pd.Series, n_periods: int = 4) -> pd.DataFrame:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["period"] = pd.qcut(np.arange(len(df)), q=n_periods, labels=False)
    rows = []
    for p, sub in df.groupby("period"):
        m = metrics_oos(sub["y"], sub["p"])
        m["period"] = int(p); m["start"] = str(sub.index.min())[:10]; m["end"] = str(sub.index.max())[:10]
        rows.append(m)
    return pd.DataFrame(rows)


def run_production_path() -> None:
    targets = list(PHASE_KK_CANDIDATES) + [PRODUCTION]
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    print(f"[Phase KK] invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 20 lines) ---")
    for line in (res.stdout or "").splitlines()[-20:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 30 lines) ---")
        for line in (res.stderr or "").splitlines()[-30:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def state_breakdown(net: pd.Series, prod_net: pd.Series, state_full: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("kk"), prod_net.rename("prod")], axis=1).join(
        state_full[["market_state"]], how="inner"
    ).dropna()
    rows = []
    for s, sub in df.groupby("market_state"):
        rows.append({
            "state": s, "n_weeks": int(len(sub)),
            "kk_mean_wkly": float(sub["kk"].mean()),
            "prod_mean_wkly": float(sub["prod"].mean()),
            "delta_mean_wkly": float(sub["kk"].mean() - sub["prod"].mean()),
            "kk_minus_prod_cumulative": float(((1+sub["kk"]).prod()-1) - ((1+sub["prod"]).prod()-1)),
        })
    return pd.DataFrame(rows)


def headline(name: str, weekly: pd.Series, weights: pd.DataFrame | None) -> dict:
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
    else:
        out["avg_BIL"] = float("nan"); out["avg_SPY"] = float("nan"); out["avg_turnover"] = float("nan")
    return out


def select_best_kk(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_KK_CANDIDATES)].copy()
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
        spy_inc_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100
        sub = state_df[state_df["candidate"] == name]
        sp = sub[sub["state"] == "stressed_panic"]; rf = sub[sub["state"] == "recovery_fragile"]
        sp_d = float(sp["delta_mean_wkly"].iloc[0]) if not sp.empty else float("nan")
        rf_d = float(rf["delta_mean_wkly"].iloc[0]) if not rf.empty else float("nan")
        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = bil_inc_pp <= 5.0
        cond_sp = (np.isnan(sp_d) or sp_d >= -1e-4)
        cond_rf = (np.isnan(rf_d) or rf_d >= -1e-4)
        cond_hidden = not (spy_inc_pp > 10.0 and ann_imp_pp < 0.20)
        passes = all([cond_drag, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_bil, cond_sp, cond_rf, cond_hidden])
        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"bil_inc>5pp ({bil_inc_pp:+.2f}pp)" if not cond_bil else "",
            f"stressed_panic worse ({sp_d:+.6f}/wk)" if not cond_sp else "",
            f"recovery_fragile worse ({rf_d:+.6f}/wk)" if not cond_rf else "",
            f"hidden beta SPY +{spy_inc_pp:.2f}pp" if not cond_hidden else "",
        ])) or "none"
        rows.append({"name": name, "ann_imp_pp": ann_imp_pp, "sharpe_imp": sharpe_imp,
                      "mdd_imp_pp": mdd_imp_pp, "cvar_imp_pp": cvar_imp_pp,
                      "turnover_ratio_vs_prod": turn_ratio, "bil_inc_pp": bil_inc_pp,
                      "stressed_panic_delta_wkly": sp_d, "recovery_fragile_delta_wkly": rf_d,
                      "passes_all_gates": passes, "fail_reasons": fail})
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        best = passing.sort_values(["sharpe_imp", "ann_imp_pp"], ascending=[False, False]).iloc[0]
        return best["name"], f"Selected {best['name']}: passes all gates.", decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp", "ann_imp_pp"], ascending=[False, False]).iloc[0]
    return "", f"NO Phase KK candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}.", decision.to_dict("records")


def main():
    print("[Phase KK] Building dataset...")
    X, y = build_dataset()
    print(f"  features: {X.shape[1]}; rows: {X.shape[0]}; pos_rate: {y.dropna().mean():.3f}")

    print("[Phase KK] Walk-forward logistic regression on Target A...")
    pred, fit_log, last_coefs = walk_forward_logistic(X, y)

    # baseline (existing p_regime_confidence as 1 - score)
    baseline_pred = 1.0 - X["p_regime_confidence"].fillna(0.5)

    base_m = metrics_oos(y, baseline_pred)
    fresh_m = metrics_oos(y, pred)
    metrics_df = pd.DataFrame([
        {"model": "baseline_existing", "label": "p_regime_only_inverted", "target": "target_A_stress_transition_4w", **base_m},
        {"model": "logistic_kk", "label": "regime_only_target_a", "target": "target_A_stress_transition_4w", **fresh_m},
    ])
    metrics_df.to_csv(roc.LAYER2B_DIR / "phase_kk_targeta_model_metrics.csv", index=False)

    print(f"  baseline Brier: {base_m['brier']:.4f}, AUC: {base_m['auc']:.4f}")
    print(f"  refreshed Brier: {fresh_m['brier']:.4f}, AUC: {fresh_m['auc']:.4f}")

    # Calibration + stability
    cal = calibration(y, pred); cal["model"] = "logistic_kk"
    cal.to_csv(roc.LAYER2B_DIR / "phase_kk_targeta_calibration.csv", index=False)
    sta = stability(y, pred); sta["model"] = "logistic_kk"
    sta.to_csv(roc.LAYER2B_DIR / "phase_kk_targeta_stability.csv", index=False)
    pd.DataFrame([last_coefs]).to_csv(roc.LAYER2B_DIR / "phase_kk_targeta_coefficients.csv", index=False)

    # Build refreshed regime confidence series:
    # production convention: higher p_regime_confidence = healthier market.
    # Phase KK ML predicts forward stress probability.
    # Refreshed score = 1 - p_stress (aligned to production direction).
    p_stress = pred.fillna(1.0 - X["p_regime_confidence"].fillna(0.5))  # fallback to baseline early
    p_existing = X["p_regime_confidence"].copy()
    p_refreshed = 1.0 - p_stress
    blended_25 = 0.75 * p_existing.fillna(0.5) + 0.25 * p_refreshed.fillna(0.5)

    out_pred_df = pd.DataFrame({
        "p_existing": p_existing,
        "p_stress_forecast": p_stress,
        "p_regime_confidence_refreshed": p_refreshed,
        "p_regime_confidence_blend25": blended_25,
    })
    out_pred_df.index.name = "Date"
    out_pred_df.to_csv(roc.LAYER2B_DIR / "phase_kk_targeta_regime_confidence_predictions.csv")
    print(f"  Saved phase_kk_targeta_regime_confidence_predictions.csv")

    # Run production pipeline
    if fresh_m["brier"] >= base_m["brier"]:
        print("  WARNING: refreshed model does NOT improve Brier. Skipping portfolio candidate generation.")
        return ""
    run_production_path()

    # Build candidate summary
    state_full = load_state_full()
    rows = []; state_rows = []
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns missing")
    prod_net = prod_ret["net_return"]
    for name in PHASE_KK_CANDIDATES + [PRODUCTION, SHADOW]:
        ret = roc.load_portfolio_returns(name)
        if ret is None: continue
        w = roc.load_portfolio_weights(name)
        net = ret["net_return"].dropna()
        h = headline(name, net, w)
        if "turnover" in ret.columns and pd.isna(h.get("avg_turnover")):
            h["avg_turnover"] = float(ret["turnover"].mean())
        rows.append(h)
        if name in PHASE_KK_CANDIDATES:
            sb = state_breakdown(net, prod_net, state_full)
            sb["candidate"] = name
            state_rows.append(sb)
    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_kk_candidate_metrics_full.csv", index=False)
    state_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    if not state_df.empty:
        state_df.to_csv(roc.LAYER3_DIR / "phase_kk_state_summary.csv", index=False)

    best, rationale, recs = select_best_kk(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_kk_selection_table.csv", index=False)

    print("\n=== Phase KK candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    if not state_df.empty:
        print("\n=== Phase KK state-by-state ===")
        print(state_df[["candidate", "state", "n_weeks", "delta_mean_wkly", "kk_minus_prod_cumulative"]].to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase KK — Targeted Phase 2B ML refresh (Target A + Group A only)",
        "model": "LogisticRegression(liblinear, max_iter=1000) with StandardScaler",
        "validation": {"method": "expanding-window walk-forward",
                        "initial_train_weeks": INITIAL_TRAIN_WEEKS,
                        "retrain_freq_weeks": RETRAIN_FREQ_WEEKS},
        "features_used": ALL_GROUP_A,
        "phase_cc_features_used": "NONE",
        "macro_features_used": "NONE",
        "target": "target_A_stress_transition_4w (forward 4w max indicator of stressed_panic)",
        "metrics": {"baseline_brier": base_m["brier"], "baseline_auc": base_m["auc"],
                     "refreshed_brier": fresh_m["brier"], "refreshed_auc": fresh_m["auc"]},
        "candidates": PHASE_KK_CANDIDATES,
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_kk_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase KK artifacts.")
    return best


if __name__ == "__main__":
    main()
