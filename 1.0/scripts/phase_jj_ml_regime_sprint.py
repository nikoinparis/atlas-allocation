"""Phase JJ — Controlled ML sprint for the ETF quant portfolio project.

This script runs Parts 1–3a and 3c of the Phase JJ sprint:
  Part 1: Build a causal weekly ML dataset with feature manifest.
  Part 2: Train / walk-forward score baseline + 6 controlled models on
          4 forward-risk targets. Strict expanding-window OOS.
  Part 3a: Select the best model on Target A (stress_transition_4w),
           blend its predictions with p_regime_confidence (75/25 and 50/50)
           and save phase_jj_blended_predictions.csv.
  Part 3b: Invoke build_improvement_artifacts.py via subprocess to build
           portfolio candidates JJ1 (riskdial_25) and JJ2 (riskdial_50)
           through the production pipeline. (Requires the matching
           edits in build_improvement_artifacts.py — added in the same
           sprint commit.)
  Part 3c / 4: Compute selection table, save protocol, return best name.
              The driver invokes the quick committee screen in a separate
              shell command, kept outside this script for token efficiency.

External dependencies: only sklearn (already installed).
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
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, roc_auc_score, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


# ----------------------------------------------------------------------
# config
# ----------------------------------------------------------------------

PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
JJ1_NAME = "improved_phasejj_ml_riskdial_25"
JJ2_NAME = "improved_phasejj_ml_riskdial_50"
PHASE_JJ_PORTFOLIO_CANDIDATES = [JJ1_NAME, JJ2_NAME]

INITIAL_TRAIN_WEEKS = 260      # ~5 years
RETRAIN_FREQ_WEEKS = 26        # bi-annual retraining
FORWARD_HORIZON_WEEKS = 4
TRAIN_MIN_POS = 5              # require at least this many positives in train
RNG_SEED = 20260427


# Existing Phase 2B regime features
EXISTING_REGIME_FEATURES = [
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
EXISTING_PHASE2B_PREDS = ["p_regime_confidence", "p_transition_quality", "p_tail_risk"]

# Phase CC refined-state one-hot indicators (causal in the refined-state file
# because they were computed walk-forward).
REFINED_STATE_VALUES = [
    "calm_trend",
    "neutral_healthy",
    "neutral_mixed",
    "neutral_deteriorating",
    "recovery_confirmed",
    "recovery_fragile",
    "stressed_panic",
]
REFINED_NUMERIC_FEATURES = [
    "deterioration_z",
    "deterioration_rank_neutral_mixed",
    "defensive_overlay_hint",   # used as a numeric feature only — never as a multiplier
]

# Macro audit features
MACRO_FEATURE_COLS = [
    "hyg_lqd_credit_spread_proxy",
    "uup_dollar_strength_4w",
    "tlt_rate_sensitive_4w",
    "gld_defensive_4w",
    "spy_realized_vol_4w",
    "spy_drawdown_from_52w_high",
    "spy_minus_iei_3m",
    "xlf_minus_xlu_3m",
    "ig_credit_4w",
    "hy_credit_4w",
]


# ----------------------------------------------------------------------
# Part 1 — dataset build
# ----------------------------------------------------------------------

def load_market_state_full() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_refined_state() -> pd.DataFrame:
    p = roc.LAYER2B_DIR / "market_state_history_refined.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_phase2b_predictions() -> pd.DataFrame:
    p = roc.LAYER2B_DIR / "phase2b_meta_predictions.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_macro_features() -> pd.DataFrame:
    p = roc.ROOT / "data" / "research" / "macro_feature_audit" / "macro_features_weekly.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def load_weekly_returns() -> pd.DataFrame:
    return roc.load_weekly_returns()


def causal_lag(df: pd.DataFrame, lag_weeks: int = 1) -> pd.DataFrame:
    """Lag every feature by lag_weeks so a feature available at end of week
    t-1 is used to predict targets defined at time t (forward window)."""
    return df.shift(lag_weeks)


def build_target_stress_transition_4w(state_history: pd.DataFrame, horizon: int = 4) -> pd.Series:
    """Target A: 1 if any of the next H weeks is stressed_panic."""
    s = state_history["market_state"].astype(str)
    panic = (s == "stressed_panic").astype(float)
    fwd = panic.shift(-1).rolling(window=horizon, min_periods=horizon).max().shift(-(horizon - 1))
    return fwd


def build_target_prod_bad_return_4w(prod_returns: pd.Series, horizon: int = 4) -> pd.Series:
    """Target B: 1 if forward H-week production net return is in bottom 25% historically (causal threshold per row uses the OBSERVATION-SET historical quantile only at scoring time; for the dataset we use the global quantile but only for label definition, not as a feature)."""
    log_r = np.log1p(prod_returns.fillna(0.0))
    fwd = np.expm1(log_r.shift(-1).rolling(window=horizon, min_periods=horizon).sum().shift(-(horizon - 1)))
    cutoff = float(fwd.dropna().quantile(0.25))
    return (fwd <= cutoff).astype(float)


def build_target_spy_bad_return_4w(spy_returns: pd.Series, horizon: int = 4) -> pd.Series:
    log_r = np.log1p(spy_returns.fillna(0.0))
    fwd = np.expm1(log_r.shift(-1).rolling(window=horizon, min_periods=horizon).sum().shift(-(horizon - 1)))
    cutoff = float(fwd.dropna().quantile(0.25))
    return (fwd <= cutoff).astype(float)


def build_target_prod_drawdown_worsens_4w(prod_returns: pd.Series, horizon: int = 4,
                                          worsen_threshold: float = -0.03) -> pd.Series:
    """Target D: 1 if the drawdown over the next H weeks deepens by more
    than 3pp (i.e., min cumulative log-return over next H is < -3%)."""
    log_r = np.log1p(prod_returns.fillna(0.0))
    fwd_min_cum = log_r.shift(-1).rolling(window=horizon, min_periods=horizon).apply(
        lambda x: np.cumsum(x).min(), raw=True
    ).shift(-(horizon - 1))
    return (np.expm1(fwd_min_cum) <= worsen_threshold).astype(float)


def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (X, y_df, manifest_df)."""
    print("[Part 1] loading inputs...")
    state_full = load_market_state_full()
    refined = load_refined_state()
    p2b = load_phase2b_predictions()
    macro = load_macro_features()
    weekly = load_weekly_returns()
    prod_ret_df = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret_df is None:
        raise RuntimeError("Production returns missing — required for Targets B and D")
    prod_returns = prod_ret_df["net_return"].astype(float)
    spy = weekly["SPY"].astype(float) if "SPY" in weekly.columns else pd.Series(dtype=float)

    # Master index: market state history dates
    master_idx = state_full.index

    # ---- assemble feature columns ----
    feat = pd.DataFrame(index=master_idx)

    # A. existing regime features (already 1w lagged inside regime engine, but
    #    we apply an extra causal lag(1) here to ensure features at t use only
    #    information available at end of week t-1).
    for col in EXISTING_REGIME_FEATURES:
        if col in state_full.columns:
            feat[col] = state_full[col].astype(float)
    # Phase 2B existing predictions
    if not p2b.empty:
        for col in EXISTING_PHASE2B_PREDS:
            if col in p2b.columns:
                feat[col] = p2b[col].reindex(master_idx).astype(float)

    # B. Phase CC refined-state features
    if not refined.empty:
        if "refined_state" in refined.columns:
            for v in REFINED_STATE_VALUES:
                feat[f"refined_state_is_{v}"] = (
                    refined["refined_state"].astype(str).reindex(master_idx) == v
                ).astype(float)
        for col in REFINED_NUMERIC_FEATURES:
            if col in refined.columns:
                feat[col] = refined[col].reindex(master_idx).astype(float)

    # C. macro / ETF-derived features
    if not macro.empty:
        for col in MACRO_FEATURE_COLS:
            if col in macro.columns:
                feat[col] = macro[col].reindex(master_idx).astype(float)

    # ---- causal lag: shift all features by 1 week ----
    feat_lagged = causal_lag(feat, lag_weeks=1)

    # ---- targets (NOT lagged — they are forward-looking by construction) ----
    y_df = pd.DataFrame(index=master_idx)
    y_df["target_A_stress_transition_4w"] = build_target_stress_transition_4w(state_full)
    y_df["target_B_prod_bad_return_4w"] = build_target_prod_bad_return_4w(prod_returns).reindex(master_idx)
    y_df["target_C_spy_bad_return_4w"] = build_target_spy_bad_return_4w(spy).reindex(master_idx) if not spy.empty else pd.Series(np.nan, index=master_idx)
    y_df["target_D_prod_drawdown_worsens_4w"] = build_target_prod_drawdown_worsens_4w(prod_returns).reindex(master_idx)

    # ---- feature manifest ----
    manifest_rows = []
    for c in feat_lagged.columns:
        # feature group
        if c in EXISTING_REGIME_FEATURES:
            group = "A_existing_regime"
            source = "market_state_history.csv"
        elif c in EXISTING_PHASE2B_PREDS:
            group = "A_existing_phase2b_pred"
            source = "phase2b_meta_predictions.csv"
        elif c.startswith("refined_state_is_"):
            group = "B_phase_cc_refined_state_one_hot"
            source = "market_state_history_refined.csv"
        elif c in REFINED_NUMERIC_FEATURES:
            group = "B_phase_cc_refined_numeric"
            source = "market_state_history_refined.csv"
        elif c in MACRO_FEATURE_COLS:
            group = "C_macro_etf_proxy"
            source = "macro_features_weekly.csv"
        else:
            group = "other"
            source = "?"
        manifest_rows.append({
            "feature": c,
            "source": source,
            "feature_group": group,
            "is_causal": True,   # all features are 1-week lagged before they enter X
            "lag_or_fill_rule": "shift(+1) week + ffill via X.fillna",
            "allowed_in_live_scoring": True,
            "leakage_risk_notes": (
                "all source columns are computed walk-forward in their respective files; "
                "1-week lag added here to guarantee feature at t uses only info up to t-1"
            ),
            "used_in_final_model": True,   # may be overwritten later if dropped
        })
    manifest = pd.DataFrame(manifest_rows)

    # ffill features (fill early NaNs with feature median over training horizon happens at fit-time)
    feat_lagged = feat_lagged.ffill()

    # Trim rows where ALL features are NaN
    feat_lagged = feat_lagged.dropna(how="all")
    y_df = y_df.reindex(feat_lagged.index)

    # Save
    out_dataset = pd.concat([feat_lagged, y_df], axis=1)
    out_dataset.to_csv(roc.LAYER2B_DIR / "phase_jj_ml_dataset.csv")
    manifest.to_csv(roc.LAYER2B_DIR / "phase_jj_ml_feature_manifest.csv", index=False)
    print(f"[Part 1] dataset shape: {out_dataset.shape}; features: {feat_lagged.shape[1]}; targets: {y_df.shape[1]}")
    print(f"[Part 1] target class balance:")
    for c in y_df.columns:
        s = y_df[c].dropna()
        print(f"  {c}: n={len(s)}, pos_rate={s.mean():.3f}")
    return feat_lagged, y_df, manifest


# ----------------------------------------------------------------------
# Part 2 — model experiments (walk-forward)
# ----------------------------------------------------------------------

def make_model(name: str):
    if name == "logistic":
        return LogisticRegression(max_iter=1000, solver="liblinear", random_state=RNG_SEED)
    if name == "logistic_l2":
        return LogisticRegression(max_iter=1000, solver="liblinear",
                                   C=0.5, penalty="l2", random_state=RNG_SEED)
    if name == "tree_d3":
        return DecisionTreeClassifier(max_depth=3, min_samples_leaf=20, random_state=RNG_SEED)
    if name == "rf_shallow":
        return RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20,
                                       random_state=RNG_SEED, n_jobs=1)
    if name == "hgb_shallow":
        return HistGradientBoostingClassifier(max_iter=100, max_depth=3, learning_rate=0.05,
                                               min_samples_leaf=20, l2_regularization=0.5,
                                               early_stopping=True, validation_fraction=0.2,
                                               random_state=RNG_SEED)
    raise ValueError(f"unknown model {name}")


MODEL_LIST = [
    ("logistic", "regime_only", EXISTING_REGIME_FEATURES + EXISTING_PHASE2B_PREDS),
    ("logistic", "regime_plus_refined", None),  # None = use ALL features
    ("logistic_l2", "all", None),
    ("tree_d3", "all", None),
    ("rf_shallow", "all", None),
    ("hgb_shallow", "all", None),
]


def walk_forward_predict(X: pd.DataFrame, y: pd.Series, model_name: str,
                         feature_subset: list[str] | None = None) -> tuple[pd.Series, list[dict]]:
    """Expanding-window walk-forward. Train on observations with index <
    train_end. Score the next RETRAIN_FREQ_WEEKS weeks. Repeat."""
    if feature_subset is None:
        feature_cols = list(X.columns)
    else:
        feature_cols = [c for c in feature_subset if c in X.columns]
    Xs = X[feature_cols].astype(float)
    valid_y = y.dropna()
    if len(valid_y) < INITIAL_TRAIN_WEEKS + RETRAIN_FREQ_WEEKS:
        return pd.Series(np.nan, index=y.index, dtype=float), []
    out = pd.Series(np.nan, index=y.index, dtype=float)
    fit_log = []
    indexed = X.index
    valid_pos = pd.Series(range(len(indexed)), index=indexed)
    train_end = INITIAL_TRAIN_WEEKS
    while train_end < len(indexed):
        # Train on rows where y is not NaN AND index_pos < train_end
        # AND X has no NaN in the selected columns
        train_mask = pd.Series(False, index=indexed)
        train_mask.iloc[:train_end] = True
        # only include rows where y is not NaN
        train_mask = train_mask & y.notna() & Xs.notna().all(axis=1)
        y_train = y[train_mask]
        if y_train.sum() < TRAIN_MIN_POS or (y_train == 0).sum() < TRAIN_MIN_POS:
            train_end += RETRAIN_FREQ_WEEKS
            continue
        X_train_arr = Xs[train_mask].fillna(0).values
        y_train_arr = y_train.astype(int).values

        # Train model
        try:
            if model_name in {"logistic", "logistic_l2"}:
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train_arr)
                model = make_model(model_name)
                model.fit(X_train_scaled, y_train_arr)
            else:
                scaler = None
                model = make_model(model_name)
                model.fit(X_train_arr, y_train_arr)
        except Exception as e:
            print(f"  WARNING: {model_name} train at {indexed[min(train_end-1, len(indexed)-1)].date()} failed: {e}")
            train_end += RETRAIN_FREQ_WEEKS
            continue

        # Score the next RETRAIN_FREQ_WEEKS rows
        score_end = min(train_end + RETRAIN_FREQ_WEEKS, len(indexed))
        score_idx = indexed[train_end:score_end]
        X_score = Xs.reindex(score_idx).fillna(0).values
        if scaler is not None:
            X_score = scaler.transform(X_score)
        try:
            proba = model.predict_proba(X_score)[:, 1]
        except Exception:
            proba = np.full(len(score_idx), np.nan)
        out.loc[score_idx] = proba

        fit_log.append({
            "model": model_name,
            "train_end_date": str(indexed[train_end - 1])[:10],
            "n_train": int(len(y_train)),
            "pos_rate_train": float(y_train.mean()),
            "score_start": str(score_idx[0])[:10] if len(score_idx) else "",
            "score_end": str(score_idx[-1])[:10] if len(score_idx) else "",
        })
        train_end += RETRAIN_FREQ_WEEKS
    return out, fit_log


def metrics_oos(y_true: pd.Series, y_pred: pd.Series) -> dict:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p")], axis=1).dropna()
    if df.empty:
        return {"n_obs": 0, "brier": float("nan"), "auc": float("nan"), "log_loss": float("nan"),
                "pos_rate": float("nan"), "pred_mean": float("nan")}
    y = df["y"].astype(int).values
    p = df["p"].astype(float).clip(1e-6, 1 - 1e-6).values
    n_obs = int(len(df))
    brier = float(brier_score_loss(y, p))
    try:
        auc = float(roc_auc_score(y, p))
    except Exception:
        auc = float("nan")
    try:
        ll = float(log_loss(y, p))
    except Exception:
        ll = float("nan")
    pos_rate = float(y.mean())
    pred_mean = float(p.mean())
    return {"n_obs": n_obs, "brier": brier, "auc": auc, "log_loss": ll,
            "pos_rate": pos_rate, "pred_mean": pred_mean}


def calibration_table(y_true: pd.Series, y_pred: pd.Series, n_bins: int = 5) -> pd.DataFrame:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["bucket"] = pd.qcut(df["p"], q=n_bins, labels=False, duplicates="drop")
    out = df.groupby("bucket").agg(n=("y", "count"), mean_pred=("p", "mean"),
                                     mean_actual=("y", "mean")).reset_index()
    return out


def stability_by_period(y_true: pd.Series, y_pred: pd.Series, n_periods: int = 4) -> pd.DataFrame:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["period"] = pd.qcut(np.arange(len(df)), q=n_periods, labels=False)
    rows = []
    for p, sub in df.groupby("period"):
        m = metrics_oos(sub["y"], sub["p"])
        m["period"] = int(p)
        m["start"] = str(sub.index.min())[:10]
        m["end"] = str(sub.index.max())[:10]
        rows.append(m)
    return pd.DataFrame(rows)


def stability_by_state(y_true: pd.Series, y_pred: pd.Series, refined_state: pd.Series) -> pd.DataFrame:
    df = pd.concat([y_true.rename("y"), y_pred.rename("p"),
                     refined_state.rename("refined_state")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    rows = []
    for s, sub in df.groupby("refined_state"):
        if len(sub) < 10: continue
        m = metrics_oos(sub["y"], sub["p"])
        m["refined_state"] = s
        rows.append(m)
    return pd.DataFrame(rows)


def feature_importance_dump(X: pd.DataFrame, y: pd.Series, model_name: str) -> dict:
    """Fit ONE final full-sample model and dump coefficients/importances.
    For interpretability only; not used in OOS predictions."""
    Xs = X.astype(float).fillna(0)
    valid = y.dropna().index
    Xs = Xs.loc[valid]
    y = y.loc[valid].astype(int)
    if y.nunique() < 2 or len(y) < 50:
        return {}
    if model_name in {"logistic", "logistic_l2"}:
        scaler = StandardScaler()
        Xs_a = scaler.fit_transform(Xs.values)
        m = make_model(model_name)
        m.fit(Xs_a, y.values)
        return dict(zip(Xs.columns, m.coef_.ravel().tolist()))
    elif model_name == "tree_d3":
        m = make_model(model_name)
        m.fit(Xs.values, y.values)
        return dict(zip(Xs.columns, m.feature_importances_.tolist()))
    elif model_name == "rf_shallow":
        m = make_model(model_name)
        m.fit(Xs.values, y.values)
        return dict(zip(Xs.columns, m.feature_importances_.tolist()))
    elif model_name == "hgb_shallow":
        m = make_model(model_name)
        m.fit(Xs.values, y.values)
        try:
            return dict(zip(Xs.columns, m.feature_importances_.tolist()))
        except Exception:
            return {}
    return {}


def part2_run_all_models(X: pd.DataFrame, y_df: pd.DataFrame, refined_state: pd.Series) -> dict:
    print("\n[Part 2] running models...")
    pred_store = {}     # (model, label, target) -> Series
    metrics_rows = []
    cal_rows = []
    importance_rows = []
    fit_log_rows = []

    # Baseline: existing p_regime_confidence as predictor of stress (1 - p_reg)
    if "p_regime_confidence" in X.columns:
        baseline_pred = 1.0 - X["p_regime_confidence"].fillna(method="bfill").fillna(0.5)
        for tcol in y_df.columns:
            m = metrics_oos(y_df[tcol], baseline_pred)
            metrics_rows.append({"model": "baseline_existing", "label": "p_regime_only_inverted",
                                  "target": tcol, **m})
            cal = calibration_table(y_df[tcol], baseline_pred)
            cal["model"] = "baseline_existing"; cal["target"] = tcol
            cal_rows.append(cal)
        pred_store[("baseline_existing", "p_regime_only_inverted", "target_A_stress_transition_4w")] = baseline_pred

    # Real models
    for model_name, label, feature_subset in MODEL_LIST:
        for tcol in y_df.columns:
            print(f"  - {model_name} ({label}) on {tcol}")
            try:
                pred, log = walk_forward_predict(X, y_df[tcol], model_name, feature_subset)
                fit_log_rows.extend([{**l, "label": label, "target": tcol} for l in log])
                m = metrics_oos(y_df[tcol], pred)
                metrics_rows.append({"model": model_name, "label": label, "target": tcol, **m})
                cal = calibration_table(y_df[tcol], pred)
                cal["model"] = model_name; cal["label"] = label; cal["target"] = tcol
                cal_rows.append(cal)
                pred_store[(model_name, label, tcol)] = pred
            except Exception as e:
                print(f"    FAILED: {e}")
                metrics_rows.append({"model": model_name, "label": label, "target": tcol,
                                      "n_obs": 0, "brier": float("nan"), "auc": float("nan"),
                                      "log_loss": float("nan"), "pos_rate": float("nan"),
                                      "pred_mean": float("nan"), "error": str(e)})
        # importance dump (use all-features full-sample on Target A)
        if feature_subset is None:
            try:
                imp = feature_importance_dump(X, y_df["target_A_stress_transition_4w"], model_name)
                for f, v in imp.items():
                    importance_rows.append({"model": model_name, "label": label,
                                             "feature": f, "coef_or_importance": v})
            except Exception as e:
                print(f"    importance dump for {model_name}/{label} failed: {e}")

    metrics_df = pd.DataFrame(metrics_rows)
    cal_df = pd.concat([df for df in cal_rows if not df.empty], ignore_index=True) if cal_rows else pd.DataFrame()
    importance_df = pd.DataFrame(importance_rows)
    fit_log_df = pd.DataFrame(fit_log_rows)

    metrics_df.to_csv(roc.LAYER2B_DIR / "phase_jj_ml_model_metrics.csv", index=False)
    cal_df.to_csv(roc.LAYER2B_DIR / "phase_jj_ml_calibration.csv", index=False)
    importance_df.to_csv(roc.LAYER2B_DIR / "phase_jj_ml_feature_importance.csv", index=False)
    fit_log_df.to_csv(roc.LAYER2B_DIR / "phase_jj_ml_fit_log.csv", index=False)

    # Predictions store: stack into long table
    pred_rows = []
    for (model, label, target), s in pred_store.items():
        for ts, v in s.items():
            if pd.notna(v):
                pred_rows.append({"date": ts, "model": model, "label": label, "target": target, "p": float(v)})
    if pred_rows:
        pd.DataFrame(pred_rows).to_csv(roc.LAYER2B_DIR / "phase_jj_ml_predictions.csv", index=False)

    print("\n[Part 2] OOS metrics on Target A (stress_transition_4w):")
    view = metrics_df[metrics_df["target"] == "target_A_stress_transition_4w"][[
        "model", "label", "n_obs", "brier", "auc", "log_loss", "pos_rate"]]
    print(view.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    return {
        "metrics_df": metrics_df,
        "cal_df": cal_df,
        "importance_df": importance_df,
        "pred_store": pred_store,
    }


# ----------------------------------------------------------------------
# Part 3a — select best ML model + write blended predictions
# ----------------------------------------------------------------------

def select_best_model(metrics_df: pd.DataFrame, target_name: str = "target_A_stress_transition_4w") -> tuple[str, str]:
    """Pick model with lowest OOS Brier on the target. Skip baseline."""
    sub = metrics_df[(metrics_df["target"] == target_name) &
                      (metrics_df["model"] != "baseline_existing")].copy()
    sub = sub.dropna(subset=["brier"])
    if sub.empty:
        return "", ""
    best = sub.sort_values("brier", ascending=True).iloc[0]
    return str(best["model"]), str(best["label"])


def write_blended_predictions(p_existing: pd.Series, p_ml: pd.Series, out_path: Path) -> pd.DataFrame:
    """Save phase_jj_blended_predictions.csv with two blended columns.

    Convention: p_existing is p_regime_confidence (high = healthy regime).
    p_ml is forward-stress probability (high = stress coming).
    Blended healthy probability = w_existing * p_existing + w_ml * (1 - p_ml).
    """
    df = pd.DataFrame({"p_existing": p_existing, "p_ml_stress": p_ml})
    df["p_ml_healthy"] = 1.0 - df["p_ml_stress"]
    df["p_regime_confidence_blended_25"] = (
        0.75 * df["p_existing"].fillna(0.5) + 0.25 * df["p_ml_healthy"].fillna(0.5)
    )
    df["p_regime_confidence_blended_50"] = (
        0.50 * df["p_existing"].fillna(0.5) + 0.50 * df["p_ml_healthy"].fillna(0.5)
    )
    df.index.name = "Date"
    df.to_csv(out_path)
    return df


# ----------------------------------------------------------------------
# Part 3b/c — invoke production pipeline + select best portfolio candidate
# ----------------------------------------------------------------------

def run_production_path(rebuild_production: bool = True) -> None:
    targets = list(PHASE_JJ_PORTFOLIO_CANDIDATES)
    if rebuild_production:
        targets.append(PRODUCTION)
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    print(f"[Part 3b] Invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 30 lines) ---")
    for line in (res.stdout or "").splitlines()[-30:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 40 lines) ---")
        for line in (res.stderr or "").splitlines()[-40:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def candidate_summary(refined_state: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    state_rows = []
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns missing")
    prod_net = prod_ret["net_return"]
    for name in PHASE_JJ_PORTFOLIO_CANDIDATES + [PRODUCTION, SHADOW]:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            continue
        w = roc.load_portfolio_weights(name)
        net = ret["net_return"].dropna()
        full_m = roc.metric_block(net)
        hold_m = roc.metric_block(net.tail(roc.HOLDOUT_WEEKS))
        row = {
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
        if w is not None:
            row["avg_BIL"] = float(w["BIL"].mean()) if "BIL" in w.columns else float("nan")
            row["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else float("nan")
            row["avg_turnover"] = float(w.diff().abs().sum(axis=1).fillna(0.0).mean())
        else:
            row["avg_BIL"] = float("nan"); row["avg_SPY"] = float("nan"); row["avg_turnover"] = float("nan")
        if "turnover" in ret.columns and pd.isna(row["avg_turnover"]):
            row["avg_turnover"] = float(ret["turnover"].mean())
        rows.append(row)

        if name in PHASE_JJ_PORTFOLIO_CANDIDATES:
            df = pd.concat([net.rename("jj"), prod_net.rename("prod")], axis=1).join(
                refined_state.rename("refined_state"), how="inner"
            ).dropna()
            for s, sub in df.groupby("refined_state"):
                state_rows.append({
                    "candidate": name, "state": s, "n_weeks": int(len(sub)),
                    "jj_mean_wkly": float(sub["jj"].mean()),
                    "prod_mean_wkly": float(sub["prod"].mean()),
                    "delta_mean_wkly": float(sub["jj"].mean() - sub["prod"].mean()),
                    "jj_minus_prod_cumulative": float(((1+sub["jj"]).prod()-1) - ((1+sub["prod"]).prod()-1)),
                })
    return pd.DataFrame(rows), pd.DataFrame(state_rows)


def select_best_portfolio(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_JJ_PORTFOLIO_CANDIDATES)].copy()
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
        spy_change_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100
        sub = state_df[state_df["candidate"] == name]
        sp = sub[sub["state"] == "stressed_panic"]; rf = sub[sub["state"] == "recovery_fragile"]
        hl = sub[sub["state"] == "neutral_healthy"]; ct = sub[sub["state"] == "calm_trend"]
        sp_d = float(sp["delta_mean_wkly"].iloc[0]) if not sp.empty else float("nan")
        rf_d = float(rf["delta_mean_wkly"].iloc[0]) if not rf.empty else float("nan")
        hl_d = float(hl["delta_mean_wkly"].iloc[0]) if not hl.empty else float("nan")
        ct_d = float(ct["delta_mean_wkly"].iloc[0]) if not ct.empty else float("nan")
        cond_no_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = bil_inc_pp <= 5.0
        cond_sp = (np.isnan(sp_d) or sp_d >= -1e-4)
        cond_rf = (np.isnan(rf_d) or rf_d >= -1e-4)
        cond_hl = (np.isnan(hl_d) or hl_d >= -1e-4)
        cond_ct = (np.isnan(ct_d) or ct_d >= -1e-4)
        cond_hidden_beta = not (spy_change_pp > 10.0 and ann_imp_pp < 0.20)
        passes = all([cond_no_drag, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_bil,
                       cond_sp, cond_rf, cond_hl, cond_ct, cond_hidden_beta])
        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_no_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"bil_inc>5pp ({bil_inc_pp:+.2f}pp)" if not cond_bil else "",
            f"stressed_panic worse ({sp_d:+.6f}/wk)" if not cond_sp else "",
            f"recovery_fragile worse ({rf_d:+.6f}/wk)" if not cond_rf else "",
            f"neutral_healthy worse ({hl_d:+.6f}/wk)" if not cond_hl else "",
            f"calm_trend worse ({ct_d:+.6f}/wk)" if not cond_ct else "",
            f"hidden beta SPY +{spy_change_pp:.2f}pp" if not cond_hidden_beta else "",
        ])) or "none"
        rows.append({
            "name": name, "ann_imp_pp": ann_imp_pp, "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp_pp, "cvar_imp_pp": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio, "bil_inc_pp": bil_inc_pp,
            "stressed_panic_delta_wkly": sp_d, "recovery_fragile_delta_wkly": rf_d,
            "neutral_healthy_delta_wkly": hl_d, "calm_trend_delta_wkly": ct_d,
            "passes_all_gates": passes, "fail_reasons": fail,
        })
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        best = passing.sort_values(["sharpe_imp", "ann_imp_pp"], ascending=[False, False]).iloc[0]
        rationale = f"Selected {best['name']}: passes all gates."
        return best["name"], rationale, decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp", "ann_imp_pp"], ascending=[False, False]).iloc[0]
    rationale = f"NO Phase JJ portfolio candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}."
    return "", rationale, decision.to_dict("records")


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    # Part 1
    X, y_df, manifest = build_dataset()
    refined = load_refined_state()
    refined_state_series = refined["refined_state"].astype(str) if "refined_state" in refined.columns else pd.Series(dtype=str)

    # Part 2
    res = part2_run_all_models(X, y_df, refined_state_series)
    metrics_df = res["metrics_df"]; pred_store = res["pred_store"]

    # Stability
    print("\n[Part 2] stability summary on Target A (best model)...")
    target_A = "target_A_stress_transition_4w"
    best_model_name, best_label = select_best_model(metrics_df, target_A)
    print(f"  Best ML model on Target A by OOS Brier: {best_model_name} ({best_label})")
    if best_model_name:
        best_pred = pred_store[(best_model_name, best_label, target_A)]
        baseline_pred = 1.0 - X["p_regime_confidence"].fillna(method="bfill").fillna(0.5)
        for predictor_name, p_series in [("baseline_existing", baseline_pred), (f"{best_model_name}_{best_label}", best_pred)]:
            sb = stability_by_period(y_df[target_A], p_series, n_periods=4)
            sb["predictor"] = predictor_name
            sb.to_csv(roc.LAYER2B_DIR / f"phase_jj_ml_stability_period_{predictor_name}.csv", index=False)
            print(f"  {predictor_name} period brier: {sb['brier'].tolist()}")
            sst = stability_by_state(y_df[target_A], p_series, refined_state_series)
            if not sst.empty:
                sst["predictor"] = predictor_name
                sst.to_csv(roc.LAYER2B_DIR / f"phase_jj_ml_stability_state_{predictor_name}.csv", index=False)

    # Part 3a — write blended predictions IF best model improves OOS Brier vs baseline
    baseline_brier = float(metrics_df[(metrics_df["model"] == "baseline_existing") &
                                       (metrics_df["target"] == target_A)]["brier"].iloc[0]) if not metrics_df[(metrics_df["model"] == "baseline_existing") &
                                       (metrics_df["target"] == target_A)].empty else float("nan")
    best_brier = float(metrics_df[(metrics_df["model"] == best_model_name) &
                                    (metrics_df["label"] == best_label) &
                                    (metrics_df["target"] == target_A)]["brier"].iloc[0]) if best_model_name else float("nan")
    print(f"\n  baseline_brier on Target A: {baseline_brier:.4f}")
    print(f"  best ML brier on Target A:   {best_brier:.4f}")
    ml_improves_oos = pd.notna(best_brier) and pd.notna(baseline_brier) and best_brier < baseline_brier
    print(f"  ML improves OOS Brier?       {ml_improves_oos}")

    if ml_improves_oos and best_model_name:
        # Write blended predictions
        # p_existing = p_regime_confidence; p_ml = best_pred (forward stress probability)
        p_existing = X["p_regime_confidence"].copy()
        # Where best_pred is NaN (early window), fall back to baseline (1 - p_existing)
        p_ml = best_pred.fillna(1.0 - p_existing.fillna(0.5))
        out_path = roc.LAYER2B_DIR / "phase_jj_blended_predictions.csv"
        blended_df = write_blended_predictions(p_existing, p_ml, out_path)
        print(f"\n  Saved blended predictions to {out_path}")
    else:
        print("\n  ML did NOT improve OOS Brier — skipping portfolio candidate generation.")

    # Part 3b — invoke production pipeline (only if blended predictions were written)
    portfolio_built = False
    if ml_improves_oos:
        try:
            run_production_path(rebuild_production=True)
            portfolio_built = True
        except Exception as e:
            print(f"  Production pipeline invocation FAILED: {e}")
            portfolio_built = False

    # Part 3c — candidate summary + selection
    selection_records = []
    best_portfolio = ""
    portfolio_rationale = "ML did not improve OOS Brier — no portfolio candidates generated"
    if portfolio_built:
        summary, state_df = candidate_summary(refined_state_series)
        summary.to_csv(roc.LAYER3_DIR / "phase_jj_candidate_metrics_full.csv", index=False)
        state_df.to_csv(roc.LAYER3_DIR / "phase_jj_state_summary.csv", index=False)
        best_portfolio, portfolio_rationale, selection_records = select_best_portfolio(summary, state_df)
        pd.DataFrame([{"best_candidate": best_portfolio, "rationale": portfolio_rationale}] + selection_records).to_csv(
            roc.LAYER3_DIR / "phase_jj_selection_table.csv", index=False)
        print("\n[Part 3c] Phase JJ candidate summary:")
        print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        print(f"\n[Part 3c] {portfolio_rationale}")

    protocol = {
        "phase": "Phase JJ — Controlled ML sprint",
        "ml_dataset_shape": [int(X.shape[0]), int(X.shape[1])],
        "targets_evaluated": list(y_df.columns),
        "models_tested": [{"model": m, "label": l, "feature_subset_size": (len(s) if s else len(X.columns))} for m, l, s in MODEL_LIST],
        "validation_scheme": {
            "method": "expanding-window walk-forward",
            "initial_train_weeks": INITIAL_TRAIN_WEEKS,
            "retrain_freq_weeks": RETRAIN_FREQ_WEEKS,
            "min_train_pos": TRAIN_MIN_POS,
        },
        "leakage_checks": [
            "All features lagged by 1 week before entering X (causal_lag).",
            "Targets are forward-looking by construction; never appear as features.",
            "Train indices strictly less than score indices in walk-forward loop.",
            "Refined-state features inherit Phase CC's walk-forward construction (rank uses only past neutral_mixed weeks, z-score uses trailing 156-week window lagged 1 week).",
        ],
        "best_ml_model": {"model": best_model_name, "label": best_label,
                           "baseline_brier": baseline_brier, "best_brier": best_brier,
                           "improves_oos": bool(ml_improves_oos)},
        "portfolio_candidates": PHASE_JJ_PORTFOLIO_CANDIDATES if portfolio_built else [],
        "best_portfolio_candidate": best_portfolio,
        "portfolio_selection_rationale": portfolio_rationale,
    }
    (roc.LAYER3_DIR / "phase_jj_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase JJ artifacts.")
    return best_portfolio


if __name__ == "__main__":
    main()
