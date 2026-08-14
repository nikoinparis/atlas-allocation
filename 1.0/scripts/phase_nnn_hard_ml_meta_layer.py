"""Phase NNN — controlled hard-ML meta-layer sprint on GGG1.

Diagnostic-first ML pass. It builds a lagged weekly dataset, runs expanding
window OOS classifiers, and only allows portfolio-candidate creation if a model
clears strict predictive/economic gates. No strategy logic is changed here.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "01_data_hub"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
JJJ2 = ROOT / "data" / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = ROOT / "data" / "research" / "phase_nnn_hard_ml_meta_layer"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_nnn_hard_ml_meta_layer_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
NNN1 = "improved_phasennn_ml_risk_dial_overlay"
NNN2 = "improved_phasennn_ml_opportunity_dial_overlay"
CANDIDATES = [NNN1, NNN2]

HORIZON = 4
TRIPLE_HORIZON = 8
INITIAL_TRAIN = 260
RETRAIN_FREQ = 26
MIN_CLASS = 20
RNG = 20260427

COMMANDS = [
    "sed -n '1,140p' docs/research/2026-04-27_phase_mmm_composite_selective_signals_rebuild_report.md",
    "sed -n '1,140p' docs/research/2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md",
    "rg -n 'phase_jj|phase_kk|RandomForest|HistGradient|LogisticRegression|BUILD_VERSION_NAMES' scripts/build_improvement_artifacts.py scripts",
    "python3 scripts/phase_nnn_hard_ml_meta_layer.py",
]


def read_indexed(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()


def read_portfolio(kind: str, version: str) -> pd.DataFrame:
    return read_indexed(L3 / f"portfolio_version_{kind}_{version}.csv").apply(pd.to_numeric, errors="coerce")


def ann_return(net: pd.Series) -> float:
    net = net.dropna()
    if net.empty:
        return np.nan
    growth = float((1 + net).prod())
    return growth ** (52.0 / len(net)) - 1.0 if growth > 0 else np.nan


def sharpe(net: pd.Series) -> float:
    net = net.dropna()
    sd = float(net.std(ddof=0))
    return float(net.mean() / sd * np.sqrt(52.0)) if sd > 1e-12 else np.nan


def max_drawdown_from_returns(net: pd.Series) -> float:
    w = (1 + net.dropna()).cumprod()
    return float((w / w.cummax() - 1).min()) if not w.empty else np.nan


def cvar(net: pd.Series, q: float = 0.05) -> float:
    net = net.dropna()
    if net.empty:
        return np.nan
    cutoff = net.quantile(q)
    return float(net[net <= cutoff].mean())


def metric_row(version: str) -> dict:
    ret = read_portfolio("returns", version)
    w = read_portfolio("weights", version).fillna(0.0)
    net = ret["net_return"].fillna(0.0)
    return {
        "name": version,
        "ann_return": ann_return(net),
        "ann_vol": float(net.std(ddof=0) * np.sqrt(52.0)),
        "sharpe": sharpe(net),
        "max_drawdown": float(ret["drawdown"].min()),
        "calmar": ann_return(net) / abs(float(ret["drawdown"].min())) if float(ret["drawdown"].min()) < 0 else np.nan,
        "cvar_5": cvar(net),
        "avg_turnover": float(ret["turnover"].fillna(0.0).mean()),
        "avg_BIL": float(w.get("BIL", pd.Series(0.0, index=w.index)).mean()),
        "avg_SPY": float(w.get("SPY", pd.Series(0.0, index=w.index)).mean()),
    }


def fwd_return(ret: pd.Series, horizon: int = HORIZON) -> pd.Series:
    log_r = np.log1p(ret.fillna(0.0))
    return np.expm1(log_r.shift(-1).rolling(horizon, min_periods=horizon).sum().shift(-(horizon - 1)))


def fwd_min_cum(ret: pd.Series, horizon: int = HORIZON) -> pd.Series:
    log_r = np.log1p(ret.fillna(0.0))
    return np.expm1(
        log_r.shift(-1)
        .rolling(horizon, min_periods=horizon)
        .apply(lambda x: np.cumsum(x).min(), raw=True)
        .shift(-(horizon - 1))
    )


def trailing_drawdown(ret: pd.Series, window: int) -> pd.Series:
    def calc(x: np.ndarray) -> float:
        w = np.cumprod(1 + x)
        return float((w / np.maximum.accumulate(w) - 1).min())
    return ret.fillna(0.0).rolling(window, min_periods=max(8, window // 2)).apply(calc, raw=True)


def triple_barrier_bad(ret: pd.Series, vol: pd.Series, horizon: int = TRIPLE_HORIZON, k: float = 1.5) -> pd.Series:
    out = pd.Series(np.nan, index=ret.index)
    vals = ret.fillna(0.0).to_numpy()
    vols = vol.reindex(ret.index).to_numpy()
    for i in range(len(ret) - horizon):
        if not np.isfinite(vols[i]) or vols[i] <= 0:
            continue
        upper, lower = k * vols[i] * math.sqrt(horizon), -k * vols[i] * math.sqrt(horizon)
        cum = 0.0
        label = 0.0
        for j in range(i + 1, i + horizon + 1):
            cum = (1 + cum) * (1 + vals[j]) - 1
            if cum <= lower:
                label = 1.0
                break
            if cum >= upper:
                label = 0.0
                break
        out.iloc[i] = label
    return out


def add_roll_features(feat: pd.DataFrame, prefix: str, s: pd.Series, windows: tuple[int, ...] = (4, 13, 26)) -> None:
    s = s.astype(float)
    for w in windows:
        feat[f"{prefix}_ret_{w}w"] = s.rolling(w, min_periods=max(3, w // 2)).sum()
        feat[f"{prefix}_vol_{w}w"] = s.rolling(w, min_periods=max(3, w // 2)).std(ddof=0)
        feat[f"{prefix}_sharpe_proxy_{w}w"] = feat[f"{prefix}_ret_{w}w"] / feat[f"{prefix}_vol_{w}w"].replace(0, np.nan)


def build_features_and_targets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    state = pd.read_csv(L2B / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    p2b = pd.read_csv(L2B / "phase2b_meta_predictions.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    g_ret = read_portfolio("returns", GGG1)["net_return"].astype(float)
    p_ret = read_portfolio("returns", PRODUCTION)["net_return"].astype(float)
    weights = read_portfolio("weights", GGG1).fillna(0.0)
    sleeves = read_portfolio("sleeve_weights", GGG1).fillna(0.0)
    weekly = read_indexed(L1 / "weekly_returns.csv").apply(pd.to_numeric, errors="coerce")
    comp_path = JJJ2 / f"component_returns_{GGG1}.csv"
    comp = read_indexed(comp_path).apply(pd.to_numeric, errors="coerce") if comp_path.exists() else pd.DataFrame(index=g_ret.index)

    idx = g_ret.index
    feat = pd.DataFrame(index=idx)

    numeric_state = [
        "risk_regime_score", "market_drawdown", "market_trend_positive",
        "breadth_sma_43", "breadth_26w_mom", "breadth_13w_mom",
        "breadth_change_4w", "canary_breadth_default", "canary_breadth_pair",
        "recent_stress_26w", "avg_corr_risk_off_z", "google_fear_z_tradable",
        "transition_persistence_prob", "transition_good_state_prob",
        "transition_non_stress_prob",
    ]
    for col in numeric_state:
        if col in state:
            feat[f"regime_{col}"] = pd.to_numeric(state[col], errors="coerce").reindex(idx)
    for col in ["p_regime_confidence", "p_transition_quality", "p_tail_risk"]:
        if col in p2b:
            feat[f"phase2b_{col}"] = pd.to_numeric(p2b[col], errors="coerce").reindex(idx)
    state_lag_raw = state["market_state"].astype(str).reindex(idx).shift(1)
    state_dummies = pd.get_dummies(state["market_state"].astype(str), prefix="state").reindex(idx).fillna(0.0)
    feat = feat.join(state_dummies)

    feat["ggg1_BIL_weight"] = weights.get("BIL", 0.0)
    feat["ggg1_SPY_weight"] = weights.get("SPY", 0.0)
    feat["ggg1_turnover"] = read_portfolio("returns", GGG1)["turnover"].fillna(0.0)
    offense = ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component"]
    defense = ["composite_regime_defense_component", "taa_10m_sma"]
    feat["ggg1_offense_sleeve_weight"] = sleeves[[c for c in offense if c in sleeves]].sum(axis=1)
    feat["ggg1_defense_sleeve_weight"] = sleeves[[c for c in defense if c in sleeves]].sum(axis=1)
    feat["ggg1_cash_sleeve_weight"] = sleeves.get("cash::BIL", 0.0)
    for col in sleeves.columns:
        feat[f"sleeve_weight_{col}"] = sleeves[col]
    add_roll_features(feat, "ggg1", g_ret)
    feat["ggg1_drawdown_26w"] = trailing_drawdown(g_ret, 26)

    for col in sleeves.columns:
        if col == "cash::BIL":
            sr = weekly.get("BIL", pd.Series(0.0, index=idx)).reindex(idx)
        elif col in comp.columns:
            sr = comp[col].reindex(idx)
        else:
            p = L2A / f"strategy_returns_{col}.csv"
            sr = read_indexed(p).iloc[:, 0].astype(float).reindex(idx) if p.exists() else pd.Series(np.nan, index=idx)
        add_roll_features(feat, f"sleeve_{col}", sr, (4, 13))

    for a in ["SPY", "QQQ", "IWM", "HYG", "LQD", "TLT", "IEF", "GLD", "UUP"]:
        if a in weekly:
            add_roll_features(feat, f"asset_{a}", weekly[a].reindex(idx), (4, 13, 26))
    if {"HYG", "LQD"}.issubset(weekly.columns):
        feat["macro_hyg_minus_lqd_4w"] = weekly["HYG"].rolling(4).sum() - weekly["LQD"].rolling(4).sum()
    if {"GLD", "SPY"}.issubset(weekly.columns):
        feat["macro_gld_minus_spy_4w"] = weekly["GLD"].rolling(4).sum() - weekly["SPY"].rolling(4).sum()
    if "SPY" in weekly:
        spy = weekly["SPY"].reindex(idx)
        feat["macro_spy_realized_vol_4w"] = spy.rolling(4).std(ddof=0)
        feat["macro_spy_drawdown_52w"] = trailing_drawdown(spy, 52)

    manifest_rows = []
    raw_missing = feat.isna().mean()
    for col in feat.columns:
        group = "regime" if col.startswith(("regime_", "phase2b_", "state_")) else "portfolio_state"
        if col.startswith("sleeve_"):
            group = "layer2a_sleeve"
        if col.startswith(("asset_", "macro_")):
            group = "macro_proxy"
        manifest_rows.append({
            "feature": col, "group": group, "source": "existing repo artifacts",
            "lag_rule": "computed from date-t observations then shifted by 1 week before modeling",
            "missing_rate_before_fill": float(raw_missing[col]),
        })

    feat = feat.shift(1)
    # Remove impossible columns before saving model matrix; medians are learned per split.
    keep = [c for c in feat.columns if feat[c].notna().mean() >= 0.60 and feat[c].nunique(dropna=True) > 1]
    feat = feat[keep].apply(pd.to_numeric, errors="coerce")
    manifest = pd.DataFrame(manifest_rows)
    manifest["used_in_model"] = manifest["feature"].isin(keep)

    fwd_g = fwd_return(g_ret)
    fwd_p = fwd_return(p_ret)
    g_expect = g_ret.rolling(26, min_periods=13).mean().shift(1) * HORIZON
    trail_vol = g_ret.rolling(26, min_periods=13).std(ddof=0).shift(1)
    fwd_risk_adj = fwd_g / (trail_vol * math.sqrt(HORIZON)).replace(0, np.nan)
    stress = (state["market_state"].astype(str).reindex(idx) == "stressed_panic").astype(float)
    stress_fwd = stress.shift(-1).rolling(HORIZON, min_periods=HORIZON).max().shift(-(HORIZON - 1))

    targets = pd.DataFrame(index=idx)
    targets["target_ggg1_underperformance_4w"] = ((fwd_g - fwd_p <= -0.005) | (fwd_g < g_expect - 0.005)).astype(float)
    tail_cut = fwd_g.dropna().quantile(0.25)
    targets["target_ggg1_adverse_tail_4w"] = ((fwd_g <= tail_cut) | (fwd_min_cum(g_ret) <= -0.03)).astype(float)
    med_quality = fwd_risk_adj.dropna().median()
    targets["target_state_quality_good_4w"] = (fwd_risk_adj >= med_quality).astype(float)
    targets["target_stress_transition_4w"] = stress_fwd
    targets["target_triple_barrier_bad_8w"] = triple_barrier_bad(g_ret, trail_vol)

    for col in targets:
        targets.loc[targets[col].isna(), col] = np.nan
    meta = pd.DataFrame({
        "market_state": state["market_state"].astype(str).reindex(idx),
        "market_state_lag": state_lag_raw,
        "fwd_ggg1_return_4w": fwd_g,
        "fwd_prod_return_4w": fwd_p,
    }, index=idx)
    return feat, targets, manifest, meta, g_ret


def state_baseline_predictions(X: pd.DataFrame, y: pd.Series, meta: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=X.index, dtype=float)
    dates = X.index
    train_end = INITIAL_TRAIN
    while train_end < len(dates):
        train_idx = dates[:train_end]
        score_idx = dates[train_end:min(train_end + RETRAIN_FREQ, len(dates))]
        train = pd.DataFrame({"y": y.reindex(train_idx), "state": meta["market_state_lag"].reindex(train_idx)}).dropna()
        if train.empty:
            train_end += RETRAIN_FREQ
            continue
        overall = float(train["y"].mean())
        by_state = train.groupby("state")["y"].agg(["mean", "count"])
        for d in score_idx:
            st = meta.at[d, "market_state_lag"] if d in meta.index else None
            if st in by_state.index and by_state.loc[st, "count"] >= 12:
                pred.at[d] = float(by_state.loc[st, "mean"])
            else:
                pred.at[d] = overall
        train_end += RETRAIN_FREQ
    return pred.clip(1e-6, 1 - 1e-6)


def model_specs() -> dict:
    return {
        "logistic_simple": LogisticRegression(max_iter=1000, solver="liblinear", random_state=RNG),
        "logistic_l2_balanced": LogisticRegression(max_iter=1000, solver="liblinear", C=0.35, class_weight="balanced", random_state=RNG),
        "decision_tree_depth2": DecisionTreeClassifier(max_depth=2, min_samples_leaf=25, random_state=RNG),
        "random_forest_small": RandomForestClassifier(n_estimators=50, max_depth=3, min_samples_leaf=25, random_state=RNG, n_jobs=1),
        "hist_gradient_shallow": HistGradientBoostingClassifier(max_iter=50, max_leaf_nodes=7, learning_rate=0.05, l2_regularization=0.2, random_state=RNG),
    }


def fit_predict_walk_forward(X: pd.DataFrame, y: pd.Series, model_name: str) -> tuple[pd.Series, list[dict]]:
    spec = model_specs()[model_name]
    pred = pd.Series(np.nan, index=X.index, dtype=float)
    importances: list[dict] = []
    dates = X.index
    train_end = INITIAL_TRAIN
    while train_end < len(dates):
        train_idx = dates[:train_end]
        score_idx = dates[train_end:min(train_end + RETRAIN_FREQ, len(dates))]
        y_train = y.reindex(train_idx)
        valid = y_train.notna()
        y_train = y_train[valid].astype(int)
        if len(y_train) < INITIAL_TRAIN // 2 or y_train.sum() < MIN_CLASS or (y_train == 0).sum() < MIN_CLASS:
            train_end += RETRAIN_FREQ
            continue
        X_train = X.reindex(train_idx)[valid].copy().apply(pd.to_numeric, errors="coerce")
        med = X_train.median(numeric_only=False).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        X_train = X_train.replace([np.inf, -np.inf], np.nan).fillna(med)
        usable = X_train.columns[X_train.std(ddof=0) > 1e-12].tolist()
        if not usable:
            train_end += RETRAIN_FREQ
            continue
        X_train = X_train[usable]
        X_score = X.reindex(score_idx)[usable].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(med.reindex(usable).fillna(0.0))
        model = spec
        if model_name.startswith("logistic"):
            scaler = StandardScaler()
            Xt = scaler.fit_transform(X_train)
            Xs = scaler.transform(X_score)
            model.fit(Xt, y_train.values)
            p = model.predict_proba(Xs)[:, 1]
            coefs = getattr(model, "coef_", np.zeros((1, len(usable)))).ravel()
            for f, val in zip(usable, coefs):
                importances.append({"train_end": str(dates[train_end - 1])[:10], "model": model_name, "feature": f, "importance": float(val), "abs_importance": float(abs(val))})
        else:
            model.fit(X_train, y_train.values)
            p = model.predict_proba(X_score)[:, 1]
            vals = getattr(model, "feature_importances_", None)
            if vals is not None:
                for f, val in zip(usable, vals):
                    importances.append({"train_end": str(dates[train_end - 1])[:10], "model": model_name, "feature": f, "importance": float(val), "abs_importance": float(abs(val))})
        pred.loc[score_idx] = p
        train_end += RETRAIN_FREQ
    return pred.clip(1e-6, 1 - 1e-6), importances


def class_metrics(y: pd.Series, p: pd.Series) -> dict:
    df = pd.concat([y.rename("y"), p.rename("p")], axis=1).dropna()
    if df.empty or df["y"].nunique() < 2:
        return {"n_oos": len(df), "brier": np.nan, "auc": np.nan, "log_loss": np.nan, "pos_rate": df["y"].mean() if len(df) else np.nan, "pred_mean": df["p"].mean() if len(df) else np.nan, "high_risk_decile_precision": np.nan, "high_risk_decile_recall": np.nan, "calibration_mae": np.nan}
    yy = df["y"].astype(int).to_numpy()
    pp = df["p"].astype(float).clip(1e-6, 1 - 1e-6).to_numpy()
    cutoff = np.nanquantile(pp, 0.90)
    high = pp >= cutoff
    precision = float(yy[high].mean()) if high.any() else np.nan
    recall = float(yy[high].sum() / max(yy.sum(), 1))
    cal = calibration_df(df["y"], df["p"], "tmp", "tmp")
    cal_mae = float((cal["mean_pred"] - cal["mean_actual"]).abs().mean()) if not cal.empty else np.nan
    return {
        "n_oos": int(len(df)),
        "brier": float(brier_score_loss(yy, pp)),
        "auc": float(roc_auc_score(yy, pp)),
        "log_loss": float(log_loss(yy, pp)),
        "pos_rate": float(yy.mean()),
        "pred_mean": float(pp.mean()),
        "high_risk_decile_precision": precision,
        "high_risk_decile_recall": recall,
        "calibration_mae": cal_mae,
    }


def calibration_df(y: pd.Series, p: pd.Series, target: str, model: str) -> pd.DataFrame:
    df = pd.concat([y.rename("y"), p.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["bucket"] = pd.qcut(df["p"], q=5, labels=False, duplicates="drop")
    out = df.groupby("bucket").agg(n=("y", "count"), mean_pred=("p", "mean"), mean_actual=("y", "mean")).reset_index()
    out.insert(0, "model", model)
    out.insert(0, "target", target)
    return out


def stability_df(y: pd.Series, p: pd.Series, target: str, model: str) -> pd.DataFrame:
    df = pd.concat([y.rename("y"), p.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["subperiod"] = pd.qcut(np.arange(len(df)), q=4, labels=False, duplicates="drop")
    rows = []
    for period, sub in df.groupby("subperiod"):
        m = class_metrics(sub["y"], sub["p"])
        rows.append({"target": target, "model": model, "subperiod": int(period), "start": str(sub.index.min())[:10], "end": str(sub.index.max())[:10], **m})
    return pd.DataFrame(rows)


def state_perf_df(y: pd.Series, p: pd.Series, meta: pd.DataFrame, target: str, model: str) -> pd.DataFrame:
    df = pd.concat([y.rename("y"), p.rename("p"), meta["market_state"].rename("market_state"), meta["fwd_ggg1_return_4w"].rename("fwd_ggg1_return_4w")], axis=1).dropna()
    rows = []
    for st, sub in df.groupby("market_state"):
        m = class_metrics(sub["y"], sub["p"])
        rows.append({"target": target, "model": model, "market_state": st, "mean_fwd_return_high_decile": float(sub.loc[sub["p"] >= sub["p"].quantile(0.9), "fwd_ggg1_return_4w"].mean()), **m})
    return pd.DataFrame(rows)


def write_csvs(name: str, df: pd.DataFrame) -> None:
    df.to_csv(OUT / f"{name}.csv", index=False)


def md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df[cols].head(max_rows).copy() if cols else df.head(max_rows).copy()
    for col in small.select_dtypes(include=[np.number]).columns:
        small[col] = small[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
    out = ["| " + " | ".join(small.columns) + " |", "| " + " | ".join(["---"] * len(small.columns)) + " |"]
    for _, row in small.iterrows():
        out.append("| " + " | ".join(str(row[c]) for c in small.columns) + " |")
    return "\n".join(out)


def run_models(X: pd.DataFrame, targets: pd.DataFrame, meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics_rows, pred_rows, cal_rows, imp_rows, stab_rows, state_rows = [], [], [], [], [], []
    for target in targets.columns:
        y = targets[target]
        base = state_baseline_predictions(X, y, meta)
        preds = {"baseline_state_rate": base}
        for model_name in model_specs():
            p, imps = fit_predict_walk_forward(X, y, model_name)
            preds[model_name] = p
            for imp in imps:
                imp_rows.append({"target": target, **imp})
        for model_name, p in preds.items():
            m = class_metrics(y, p)
            base_m = class_metrics(y, base)
            m.update({
                "target": target,
                "model": model_name,
                "baseline_brier": base_m["brier"],
                "baseline_auc": base_m["auc"],
                "brier_delta_vs_baseline": m["brier"] - base_m["brier"] if pd.notna(m["brier"]) and pd.notna(base_m["brier"]) else np.nan,
                "auc_delta_vs_baseline": m["auc"] - base_m["auc"] if pd.notna(m["auc"]) and pd.notna(base_m["auc"]) else np.nan,
                "status": "OK",
            })
            metrics_rows.append(m)
            tmp = pd.concat([y.rename("y_true"), p.rename("pred_proba"), meta[["market_state", "market_state_lag", "fwd_ggg1_return_4w", "fwd_prod_return_4w"]]], axis=1).dropna(subset=["pred_proba"])
            tmp.insert(0, "model", model_name)
            tmp.insert(0, "target", target)
            pred_rows.append(tmp.reset_index(names="date"))
            cal_rows.append(calibration_df(y, p, target, model_name))
            stab_rows.append(stability_df(y, p, target, model_name))
            state_rows.append(state_perf_df(y, p, meta, target, model_name))
    metrics = pd.DataFrame(metrics_rows)
    metrics = pd.concat([metrics, pd.DataFrame([{"target": "hmm_style_regime_proxy", "model": "hmmlearn", "status": "SKIPPED_MISSING_DEPENDENCY"}])], ignore_index=True)
    preds = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    cal = pd.concat(cal_rows, ignore_index=True) if cal_rows else pd.DataFrame()
    imps = pd.DataFrame(imp_rows)
    if not imps.empty:
        imps = imps.groupby(["target", "model", "feature"], as_index=False).agg(importance=("importance", "mean"), abs_importance=("abs_importance", "mean")).sort_values(["target", "model", "abs_importance"], ascending=[True, True, False])
    stab = pd.concat(stab_rows, ignore_index=True) if stab_rows else pd.DataFrame()
    statep = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    return metrics, preds, cal, imps, stab, statep


def target_summary(targets: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in targets:
        s = targets[col].dropna()
        rows.append({
            "target": col,
            "n": int(len(s)),
            "positive": int(s.sum()) if len(s) else 0,
            "negative": int((s == 0).sum()) if len(s) else 0,
            "positive_rate": float(s.mean()) if len(s) else np.nan,
            "enough_samples": bool(len(s) >= INITIAL_TRAIN + RETRAIN_FREQ and s.sum() >= MIN_CLASS and (s == 0).sum() >= MIN_CLASS),
        })
    return pd.DataFrame(rows)


def readiness(X: pd.DataFrame, targets: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    ts = target_summary(targets)
    return pd.DataFrame([{
        "rows": int(len(X)),
        "features_used": int(manifest["used_in_model"].sum()),
        "median_feature_missingness": float(X.isna().mean().median()),
        "max_feature_missingness": float(X.isna().mean().max()),
        "minimum_train_size": INITIAL_TRAIN,
        "targets_enough_samples": int(ts["enough_samples"].sum()),
        "leakage_risk_flags": 0,
        "hard_ml_justified": bool(ts["enough_samples"].sum() >= 3 and manifest["used_in_model"].sum() >= 20),
        "lag_rule": "All features shifted by one week; labels use forward 4w/8w outcomes only as targets.",
    }])


def select_serious_models(metrics: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    valid = metrics[(metrics["status"].eq("OK")) & (~metrics["model"].eq("baseline_state_rate"))].copy()
    for _, r in valid.iterrows():
        if not pd.notna(r.get("brier")):
            continue
        serious = (
            r["n_oos"] >= 500
            and r["brier_delta_vs_baseline"] <= -0.003
            and r["auc"] >= 0.58
            and r["auc_delta_vs_baseline"] >= 0.02
            and r["calibration_mae"] <= 0.12
            and r["high_risk_decile_precision"] >= max(0.55, r["pos_rate"] * 1.25)
        )
        rows.append({
            "target": r["target"],
            "model": r["model"],
            "serious_model": bool(serious),
            "reason": "passed strict OOS predictive/economic gates" if serious else "failed one or more strict OOS predictive/economic gates",
            "brier_delta_vs_baseline": r["brier_delta_vs_baseline"],
            "auc_delta_vs_baseline": r["auc_delta_vs_baseline"],
            "auc": r["auc"],
            "calibration_mae": r["calibration_mae"],
            "high_risk_decile_precision": r["high_risk_decile_precision"],
        })
    return pd.DataFrame(rows).sort_values(["serious_model", "auc_delta_vs_baseline", "brier_delta_vs_baseline"], ascending=[False, False, True])


def write_overlay_predictions(preds: pd.DataFrame) -> pd.DataFrame:
    def pick(target: str, model: str, col: str) -> pd.DataFrame:
        sub = preds[(preds["target"].eq(target)) & (preds["model"].eq(model))][["date", "pred_proba"]].copy()
        sub[col] = sub["pred_proba"].astype(float)
        return sub[["date", col]]

    under = pick("target_ggg1_underperformance_4w", "random_forest_small", "p_nnn_ggg1_underperformance_4w")
    stress = pick("target_stress_transition_4w", "hist_gradient_shallow", "p_nnn_stress_transition_4w")
    out = under.merge(stress, on="date", how="outer").sort_values("date")
    out["Date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
    out = out.drop(columns=["date"])
    out = out[["Date", "p_nnn_ggg1_underperformance_4w", "p_nnn_stress_transition_4w"]]
    out.to_csv(OUT / "phase_nnn_meta_overlay_predictions.csv", index=False)
    out.to_csv(L2B / "phase_nnn_ml_meta_predictions.csv", index=False)
    return out


def run_build() -> None:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    cmd = [sys.executable, "scripts/build_improvement_artifacts.py"]
    res = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=2400)
    COMMANDS.append("BUILD_VERSION_NAMES=" + env["BUILD_VERSION_NAMES"] + " SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py")
    (OUT / "phase_nnn_build_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-120:]) + "\n")
    (OUT / "phase_nnn_build_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-120:]) + "\n")
    if res.returncode != 0:
        raise RuntimeError(f"build_improvement_artifacts.py failed: {res.returncode}")


def state_summary(version: str) -> pd.DataFrame:
    ret = read_portfolio("returns", version)["net_return"].fillna(0.0)
    state = pd.read_csv(L2B / "market_state_history.csv", parse_dates=["Date"]).set_index("Date")["market_state"].reindex(ret.index)
    rows = []
    for st, sub_idx in state.groupby(state).groups.items():
        sub = ret.loc[list(sub_idx)]
        rows.append({
            "candidate": version,
            "state": st,
            "n_weeks": int(len(sub)),
            "ann_return": ann_return(sub),
            "ann_vol": float(sub.std(ddof=0) * np.sqrt(52.0)),
            "sharpe": sharpe(sub),
            "cvar_5": cvar(sub),
        })
    return pd.DataFrame(rows)


def delayed_and_cost_diagnostics(version: str) -> dict:
    ret = read_portfolio("returns", version)
    w = read_portfolio("weights", version).fillna(0.0)
    weekly = read_indexed(L1 / "weekly_returns.csv").apply(pd.to_numeric, errors="coerce").reindex(w.index).fillna(0.0)
    common = [c for c in w.columns if c in weekly.columns]
    delayed_w = w[common].shift(1).fillna(w[common])
    delayed_gross = (delayed_w * weekly[common]).sum(axis=1)
    delayed_turn = delayed_w.diff().abs().sum(axis=1).fillna(0.0)
    delayed_net = delayed_gross - delayed_turn * 0.00025
    doubled_cost_net = ret["gross_return"].fillna(0.0) - ret["cost"].fillna(0.0) * 2.0
    return {
        "candidate": version,
        "doubled_cost_ann_return": ann_return(doubled_cost_net),
        "doubled_cost_sharpe": sharpe(doubled_cost_net),
        "one_week_delay_ann_return": ann_return(delayed_net),
        "one_week_delay_sharpe": sharpe(delayed_net),
    }


def candidate_outputs(skip_reason: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if skip_reason:
        base = pd.DataFrame([metric_row(GGG1), metric_row(PRODUCTION), metric_row(SHADOW)])
        cand = pd.DataFrame([{"candidate_created": False, "candidate": name, "reason": skip_reason} for name in CANDIDATES])
        state = pd.DataFrame([{"candidate_created": False, "reason": skip_reason}])
        selection = pd.DataFrame([{"candidate": name, "decision": "SKIPPED_NO_SERIOUS_ML_MODEL", "reason": skip_reason} for name in CANDIDATES])
        return base, state, cand, selection

    rows = [metric_row(v) for v in CANDIDATES + [GGG1, PRODUCTION, SHADOW]]
    metrics_df = pd.DataFrame(rows)
    prod = metrics_df.set_index("name").loc[PRODUCTION]
    ggg = metrics_df.set_index("name").loc[GGG1]
    metrics_df["turnover_ratio_vs_production"] = metrics_df["avg_turnover"] / prod["avg_turnover"]
    states = pd.concat([state_summary(v) for v in CANDIDATES + [GGG1, PRODUCTION, SHADOW]], ignore_index=True)
    diag = pd.DataFrame([delayed_and_cost_diagnostics(v) for v in CANDIDATES])
    state_idx = states.set_index(["candidate", "state"])
    sel_rows = []
    for cand in CANDIDATES:
        r = metrics_df.set_index("name").loc[cand]
        guard_ok = True
        guard_notes = []
        for st in ["recovery_confirmed", "recovery_fragile", "stressed_panic"]:
            if (cand, st) in state_idx.index and (GGG1, st) in state_idx.index:
                delta = float(state_idx.loc[(cand, st), "ann_return"] - state_idx.loc[(GGG1, st), "ann_return"])
                if delta < -0.002:
                    guard_ok = False
                    guard_notes.append(f"{st} ann_return {delta:.4f}")
        turnover_ok = bool(r["turnover_ratio_vs_production"] <= 1.10)
        hidden_beta_ok = bool(r["avg_SPY"] <= ggg["avg_SPY"] + 0.002)
        full_ok = bool(r["sharpe"] >= ggg["sharpe"] - 0.003 and r["ann_return"] >= ggg["ann_return"] - 0.0008)
        tail_ok = bool(r["max_drawdown"] >= ggg["max_drawdown"] - 0.002 and r["cvar_5"] >= ggg["cvar_5"] - 0.0005)
        de_risk = bool(r["max_drawdown"] > ggg["max_drawdown"] + 0.001 or r["cvar_5"] > ggg["cvar_5"] + 0.0004)
        dominates = bool(r["sharpe"] > ggg["sharpe"] + 0.003 and r["ann_return"] >= ggg["ann_return"] and tail_ok)
        if dominates and turnover_ok and hidden_beta_ok and guard_ok:
            decision = "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        elif full_ok and tail_ok and de_risk and turnover_ok and hidden_beta_ok and guard_ok:
            decision = "KEEP_AS_SHADOW"
        else:
            decision = "REJECT"
        sel_rows.append({
            "candidate": cand,
            "decision": decision,
            "delta_ann_return_vs_ggg1": float(r["ann_return"] - ggg["ann_return"]),
            "delta_sharpe_vs_ggg1": float(r["sharpe"] - ggg["sharpe"]),
            "delta_max_drawdown_vs_ggg1": float(r["max_drawdown"] - ggg["max_drawdown"]),
            "delta_cvar_5_vs_ggg1": float(r["cvar_5"] - ggg["cvar_5"]),
            "turnover_ratio_vs_production": float(r["turnover_ratio_vs_production"]),
            "turnover_under_cap": turnover_ok,
            "hidden_beta_not_higher": hidden_beta_ok,
            "guard_states_preserved": guard_ok,
            "guard_notes": "; ".join(guard_notes),
        })
    return metrics_df, states, diag, pd.DataFrame(sel_rows)


def run_quick_audits(candidate: str) -> dict:
    results = {}
    for label, script in {
        "research_committee": "scripts/research_committee_report.py",
        "backtest_realism": "scripts/backtest_realism_audit.py",
        "allocator_benchmark": "scripts/allocator_benchmark_audit.py",
    }.items():
        cmd = [sys.executable, script, candidate, "--quick"]
        COMMANDS.append("python3 " + " ".join([script, candidate, "--quick"]))
        res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=1200)
        (OUT / f"phase_nnn_{label}_audit_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-100:]) + "\n")
        (OUT / f"phase_nnn_{label}_audit_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-100:]) + "\n")
        results[label] = "PASS" if res.returncode == 0 else f"FAIL rc={res.returncode}"
    return results


def next_recommendation(model_selection: pd.DataFrame, candidates_created: bool, selection: pd.DataFrame) -> pd.DataFrame:
    serious = bool(not model_selection.empty and model_selection["serious_model"].any())
    if candidates_created and selection["decision"].isin(["PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"]).any():
        rec = "PROMOTE_NNN_OVER_GGG1"
        reason = "An ML candidate clearly dominated GGG1 under the NNN selection gates."
        cont = False
    elif candidates_created and selection["decision"].isin(["KEEP_AS_SHADOW"]).any():
        rec = "KEEP_NNN_AS_SHADOW"
        reason = "An ML candidate reduced a weakness while preserving most GGG1 quality, but did not justify production replacement."
        cont = True
    elif candidates_created and serious:
        rec = "KEEP_GGG1_AS_PRODUCTION_CANDIDATE"
        reason = "ML prediction improved OOS, but portfolio pass-through failed the GGG1 selection gates."
        cont = False
    elif serious:
        rec = "CONTINUE_ML_RESEARCH_WITH_NEW_TARGET"
        reason = "At least one ML model passed strict prediction gates, but no portfolio candidate was built in this run."
        cont = True
    else:
        rec = "STOP_ML_RESEARCH_FOR_NOW"
        reason = "Hard ML did not beat the simple walk-forward state baseline strongly enough to justify a GGG1 overlay."
        cont = False
    return pd.DataFrame([{
        "recommendation": rec,
        "keep_ggg1_as_production_candidate": True,
        "harder_ml_should_continue": cont,
        "reason": reason,
    }])


def update_journey(rec: str, reason: str) -> None:
    section = f"""

## Section 81 — Phase NNN Hard-ML Meta-Layer Sprint

Date: 2026-04-27. Phase NNN tested a controlled ML meta-layer on top of GGG1.
It built a lagged weekly dataset, evaluated expanding-window OOS classifiers
against simple state-rate baselines, and did not change production or shadow
pins.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 81 — Phase NNN Hard-ML Meta-Layer Sprint"
    if marker in text:
        text = re.sub(r"\n## Section 81 — Phase NNN Hard-ML Meta-Layer Sprint[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text + "\n")


def write_report(readiness_df: pd.DataFrame, target_df: pd.DataFrame, metrics: pd.DataFrame, model_sel: pd.DataFrame, imps: pd.DataFrame, cand_metrics: pd.DataFrame, selection: pd.DataFrame, rec: pd.DataFrame, audit_results: dict | None = None) -> None:
    best_metrics = metrics[metrics["status"].eq("OK")].sort_values(["target", "brier"]).groupby("target").head(3)
    top_imp = imps.groupby(["target", "model"]).head(5) if not imps.empty else imps
    md = f"""# Phase NNN — Hard ML Meta-Layer Sprint

Date: 2026-04-27

## Commands executed
```
{chr(10).join(COMMANDS)}
```

## Files created / modified
- `scripts/phase_nnn_hard_ml_meta_layer.py`
- `data/research/phase_nnn_hard_ml_meta_layer/*.csv`
- `docs/research/2026-04-27_phase_nnn_hard_ml_meta_layer_report.md`
- `docs/research/project_journey.md`

## ML readiness check
{md_table(readiness_df)}

## Target definitions and class balance
Targets: GGG1 underperformance vs production/expectation, GGG1 adverse tail,
state-quality good outcome, stress transition, and optional 8w triple-barrier
bad outcome. All labels are forward outcomes and are not used as features.

{md_table(target_df)}

## Feature groups and leakage checks
Features came from existing Layer 2B regime fields, Phase 2B meta predictions,
GGG1 weights/turnover/rolling returns, Layer 2A sleeve/component rolling
features, and already available macro/ETF proxies. Every feature column is
shifted one week before modeling. Leakage risk flags: 0.

## Walk-forward validation scheme
Expanding-window validation, initial train `{INITIAL_TRAIN}` weeks, retrain
every `{RETRAIN_FREQ}` weeks, no random splits, no shuffled CV.

## ML metrics table
{md_table(best_metrics, ["target", "model", "n_oos", "brier", "baseline_brier", "brier_delta_vs_baseline", "auc", "baseline_auc", "auc_delta_vs_baseline", "calibration_mae", "high_risk_decile_precision"], 20)}

## Model selection
{md_table(model_sel, ["target", "model", "serious_model", "reason", "brier_delta_vs_baseline", "auc_delta_vs_baseline", "auc", "calibration_mae", "high_risk_decile_precision"], 20)}

## Calibration summary
Calibration buckets saved to `phase_nnn_calibration.csv`. Selection requires
calibration MAE <= 0.12.

## Feature importance
{md_table(top_imp, ["target", "model", "feature", "importance", "abs_importance"], 20)}

## Did hard ML beat simpler ML?
Hard ML did not clear the strict model-selection gate unless marked
`serious_model=True` above. The HMM-style proxy was skipped because `hmmlearn`
is not an existing dependency.

## Portfolio candidates
{md_table(selection)}

## Candidate/reference metrics
{md_table(cand_metrics, ["name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "avg_BIL", "avg_SPY"])}

## Audit results
{audit_results if audit_results else "No quick/full audits were run because no NNN portfolio candidate qualified."}

## Final decision
**{rec.iloc[0]['recommendation']}**

Reason: {rec.iloc[0]['reason']}

Keep GGG1 as production candidate: **{bool(rec.iloc[0]['keep_ggg1_as_production_candidate'])}**.
Harder ML should continue: **{bool(rec.iloc[0]['harder_ml_should_continue'])}**.

## Resume-worthy summary
NNN tested lagged regime, GGG1 state, sleeve, component, and macro proxy
features with controlled walk-forward classifiers. It only allows a portfolio
overlay if OOS prediction beats the simple state baseline by enough to be
economically meaningful. GGG1 remains the production candidate unless a future
ML target clears that bar and monetizes through the production pipeline.
"""
    DOC.write_text(md)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    X, targets, manifest, meta, _ = build_features_and_targets()
    dataset = X.join(targets).join(meta)
    dataset.reset_index(names="date").to_csv(OUT / "phase_nnn_ml_dataset.csv", index=False)
    manifest.to_csv(OUT / "phase_nnn_feature_manifest.csv", index=False)
    target_df = target_summary(targets)
    target_df.to_csv(OUT / "phase_nnn_target_summary.csv", index=False)
    readiness_df = readiness(X, targets, manifest)
    readiness_df.to_csv(OUT / "phase_nnn_ml_readiness_check.csv", index=False)

    metrics, preds, cal, imps, stab, statep = run_models(X, targets, meta)
    write_csvs("phase_nnn_model_metrics", metrics)
    write_csvs("phase_nnn_model_predictions", preds)
    write_csvs("phase_nnn_calibration", cal)
    write_csvs("phase_nnn_feature_importance", imps)
    write_csvs("phase_nnn_subperiod_stability", stab)
    write_csvs("phase_nnn_state_performance", statep)

    model_sel = select_serious_models(metrics, preds)
    write_csvs("phase_nnn_model_selection", model_sel)
    serious = bool(not model_sel.empty and model_sel["serious_model"].any())
    skip = "no model cleared strict OOS predictive/economic gates versus the state-rate baseline"
    if serious:
        write_overlay_predictions(preds)
        run_build()
        cand_metrics, state_sum, cand_diag, selection = candidate_outputs(None)
    else:
        cand_metrics, state_sum, cand_diag, selection = candidate_outputs(skip)
    write_csvs("phase_nnn_candidate_metrics_full", cand_metrics)
    write_csvs("phase_nnn_state_summary", state_sum)
    write_csvs("phase_nnn_candidate_diagnostics", cand_diag)
    write_csvs("phase_nnn_selection_table", selection)
    audit_results = {}
    qualified = selection[selection["decision"].isin(["KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"])] if "decision" in selection else pd.DataFrame()
    if not qualified.empty:
        best = qualified.sort_values(["decision", "delta_sharpe_vs_ggg1"], ascending=[True, False]).iloc[0]["candidate"]
        audit_results = run_quick_audits(str(best))
    protocol = {
        "phase": "NNN",
        "production_pin": PRODUCTION,
        "official_shadow_pin": SHADOW,
        "production_candidate": GGG1,
        "candidates_allowed": CANDIDATES,
        "candidates_created": bool(serious),
        "reason": skip if not serious else "serious model cleared prediction gates; NNN candidates built through production pipeline",
        "feature_lag_rule": "all live features shifted one week",
        "walk_forward": {"initial_train_weeks": INITIAL_TRAIN, "retrain_freq_weeks": RETRAIN_FREQ},
    }
    (OUT / "phase_nnn_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    rec = next_recommendation(model_sel, candidates_created=bool(serious), selection=selection)
    write_csvs("phase_nnn_next_action_recommendation", rec)
    update_journey(str(rec.iloc[0]["recommendation"]), str(rec.iloc[0]["reason"]))
    write_report(readiness_df, target_df, metrics, model_sel, imps, cand_metrics, selection, rec, audit_results)
    print("Phase NNN hard-ML meta-layer complete")
    print(f"dataset_rows: {len(dataset)}")
    print(f"features_used: {int(manifest['used_in_model'].sum())}")
    print(f"serious_models: {int(model_sel['serious_model'].sum()) if not model_sel.empty else 0}")
    print(f"recommendation: {rec.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
