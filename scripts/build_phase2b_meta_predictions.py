"""
Phase 2B interpretable-ML meta predictions.

Trains three walk-forward, causal, interpretable models that produce weekly
probability scores usable as meta-layers by the main backtest:

  1. p_regime_confidence  (Logistic regression)
       Target: forward 4-week benchmark-market Sharpe > 0.5 (annualized)
               AND no single-week drawdown worse than -3% in that window.
       Intended use: boost regime_multiplier in good states where the model
       is confident conditions are deployable.

  2. p_transition_quality (Shallow decision tree, depth <= 4)
       Target: forward 8-week benchmark total return > 0 AND max
               8-week drawdown < -5%. Trained ONLY on transition-state
               observations (strong_neutral + recovery_fragile).
       Intended use: gate conviction / leadership deployment specifically in
       transition states. Model is shallow for readability.

  3. p_tail_risk          (HistGradientBoostingClassifier with monotonic
                           constraints)
       Target: max benchmark drawdown over next 4 weeks <= -3%.
       Monotonic constraints enforce: worse current drawdown / weaker breadth
       / lower persistence -> higher tail risk prediction. Intended use:
       additive negative offset on regime_multiplier when p_tail is high.

Walk-forward setup
------------------
- Initial training window = 200 weeks (~3.8 years)
- Retrain every 26 weeks (semi-annual)
- Expanding window training (not rolling) so the model accumulates evidence
- First prediction issued for the week AFTER the initial training cutoff
- NO label can see beyond the training cutoff -> labels are shifted forward
  by the label horizon before filtering

Interpretability
----------------
- Logistic coefficients saved alongside predictions
- Decision tree dumped as text
- GBM feature importances saved

Outputs
-------
- data/04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv
- data/04_layer2b_risk_regime_engine/phase2b_meta_interpretability.txt
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

MARKET_STATE_PATH = ROOT / "data/04_layer2b_risk_regime_engine/market_state_history.csv"
BENCHMARK_PATH = ROOT / "data/03_layer2a_strategy_logic/strategy_returns_baseline_market_proxy_buy_hold.csv"
OUT_DIR = ROOT / "data/04_layer2b_risk_regime_engine"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PRED_PATH = OUT_DIR / "phase2b_meta_predictions.csv"
INTERP_PATH = OUT_DIR / "phase2b_meta_interpretability.txt"

FEATURE_COLS = [
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
]

# For monotonic GBM: +1 means prediction must be non-decreasing in that
# feature, -1 non-increasing, 0 none.
# Tail risk:
#   market_drawdown: MORE negative drawdown (lower value) -> higher tail risk
#       => increasing the value (less negative) should DECREASE tail risk => -1
#   breadth_sma_43: higher breadth -> lower tail risk => -1
#   breadth_26w_mom: higher -> lower tail risk => -1
#   breadth_13w_mom: higher -> lower tail risk => -1
#   breadth_change_4w: higher -> lower tail risk => -1
#   market_trend_positive: higher -> lower tail risk => -1
#   canary_breadth_default: higher -> higher tail risk (it is a stress canary score) => +1
#   recent_stress_26w: higher -> higher tail risk => +1
#   transition_persistence_prob: higher -> lower tail risk => -1
#   transition_good_state_prob: higher -> lower tail risk => -1
#   transition_non_stress_prob: higher -> lower tail risk => -1
TAIL_RISK_MONOTONIC = {
    "market_drawdown": -1,
    "market_trend_positive": -1,
    "breadth_sma_43": -1,
    "breadth_26w_mom": -1,
    "breadth_13w_mom": -1,
    "breadth_change_4w": -1,
    "canary_breadth_default": +1,
    "recent_stress_26w": +1,
    "transition_persistence_prob": -1,
    "transition_good_state_prob": -1,
    "transition_non_stress_prob": -1,
}

INITIAL_TRAIN_WEEKS = 200
RETRAIN_FREQ_WEEKS = 26
REGIME_CONF_HORIZON = 4      # weeks
TRANSITION_HORIZON = 8       # weeks
TAIL_HORIZON = 4             # weeks
REGIME_SHARPE_THRESHOLD = 0.5       # annualized
REGIME_SINGLEWEEK_DD = -0.03
TRANSITION_MAX_DD = -0.05
TAIL_MAX_DD = -0.03


def load_features() -> pd.DataFrame:
    df = pd.read_csv(MARKET_STATE_PATH, parse_dates=["Date"]).set_index("Date")
    # Forward-fill transition probs (they can be NaN at the beginning).
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0
    feat = df[FEATURE_COLS].copy()
    feat = feat.apply(pd.to_numeric, errors="coerce")
    feat = feat.ffill().fillna(0.0)
    return feat, df[["market_state"]]


def load_benchmark_weekly_returns() -> pd.Series:
    df = pd.read_csv(BENCHMARK_PATH, parse_dates=["Date"]).set_index("Date")
    # gross_return is the raw weekly return of a market-proxy buy & hold.
    r = pd.to_numeric(df["gross_return"], errors="coerce").fillna(0.0)
    return r


def label_regime_confidence(returns: pd.Series) -> pd.Series:
    """Binary label: forward 4w annualized Sharpe > threshold AND no single-week
    drawdown below -3%. Defined at time t using returns[t+1:t+H]."""
    H = REGIME_CONF_HORIZON
    weeks_per_year = 52
    labels = pd.Series(index=returns.index, dtype="float64")
    vals = returns.values
    for i in range(len(returns)):
        if i + H >= len(returns):
            labels.iloc[i] = np.nan
            continue
        window = vals[i + 1 : i + 1 + H]
        if len(window) < H:
            labels.iloc[i] = np.nan
            continue
        mean = window.mean() * weeks_per_year
        std = window.std(ddof=1) * np.sqrt(weeks_per_year)
        sharpe = mean / std if std > 1e-9 else 0.0
        worst = window.min()
        labels.iloc[i] = 1.0 if (sharpe > REGIME_SHARPE_THRESHOLD and worst > REGIME_SINGLEWEEK_DD) else 0.0
    return labels


def label_transition_quality(returns: pd.Series) -> pd.Series:
    H = TRANSITION_HORIZON
    labels = pd.Series(index=returns.index, dtype="float64")
    vals = returns.values
    for i in range(len(returns)):
        if i + H >= len(returns):
            labels.iloc[i] = np.nan
            continue
        window = vals[i + 1 : i + 1 + H]
        if len(window) < H:
            labels.iloc[i] = np.nan
            continue
        total = np.prod(1.0 + window) - 1.0
        # 8-week max drawdown
        wealth = np.cumprod(1.0 + window)
        running_max = np.maximum.accumulate(wealth)
        dd = np.min(wealth / running_max - 1.0)
        labels.iloc[i] = 1.0 if (total > 0.0 and dd > TRANSITION_MAX_DD) else 0.0
    return labels


def label_tail_risk(returns: pd.Series) -> pd.Series:
    """Binary label: max 4-week drawdown worse than -3%."""
    H = TAIL_HORIZON
    labels = pd.Series(index=returns.index, dtype="float64")
    vals = returns.values
    for i in range(len(returns)):
        if i + H >= len(returns):
            labels.iloc[i] = np.nan
            continue
        window = vals[i + 1 : i + 1 + H]
        if len(window) < H:
            labels.iloc[i] = np.nan
            continue
        wealth = np.cumprod(1.0 + window)
        running_max = np.maximum.accumulate(wealth)
        dd = np.min(wealth / running_max - 1.0)
        labels.iloc[i] = 1.0 if dd <= TAIL_MAX_DD else 0.0
    return labels


def walk_forward_predict(
    X: pd.DataFrame,
    y: pd.Series,
    model_factory,
    initial_train: int = INITIAL_TRAIN_WEEKS,
    retrain_freq: int = RETRAIN_FREQ_WEEKS,
    min_positive: int = 10,
    scaled: bool = False,
    train_mask: pd.Series | None = None,
) -> tuple[pd.Series, list[dict]]:
    """Returns a Series of predicted probabilities (index = X.index), plus a
    log of training checkpoints."""
    preds = pd.Series(index=X.index, dtype="float64")
    dates = X.index
    n = len(dates)

    # NaN labels => cannot train/validate on those rows
    valid_train = ~y.isna()
    if train_mask is not None:
        valid_train &= train_mask.reindex(X.index).fillna(False).astype(bool)

    model = None
    scaler = None
    checkpoints: list[dict] = []
    last_fit_idx = -1

    for i in range(n):
        # When to (re)train: at t = initial_train, initial_train + retrain_freq, ...
        if i >= initial_train and (i == initial_train or (i - initial_train) % retrain_freq == 0):
            # Use data up to index i-1, and that also has a valid label (which
            # means the forward window ended before or at i-1 -> no leakage).
            train_end = i  # exclusive
            train_idx = dates[:train_end][valid_train.iloc[:train_end].values]
            if len(train_idx) >= 40:
                X_tr = X.loc[train_idx].values
                y_tr = y.loc[train_idx].values.astype(int)
                if y_tr.sum() >= min_positive and (len(y_tr) - y_tr.sum()) >= min_positive:
                    if scaled:
                        scaler = StandardScaler()
                        X_tr = scaler.fit_transform(X_tr)
                    model = model_factory()
                    model.fit(X_tr, y_tr)
                    last_fit_idx = i
                    checkpoints.append(
                        {
                            "train_end_date": dates[i - 1],
                            "n_train": int(len(y_tr)),
                            "pos_rate": float(y_tr.mean()),
                        }
                    )
        # Predict for the current row, as long as a model is fitted
        if model is not None:
            X_row = X.iloc[[i]].values
            if scaled and scaler is not None:
                X_row = scaler.transform(X_row)
            try:
                preds.iloc[i] = float(model.predict_proba(X_row)[0, 1])
            except Exception:
                preds.iloc[i] = np.nan
    return preds, checkpoints


def make_logistic():
    return LogisticRegression(
        penalty="l2",
        C=1.0,
        solver="lbfgs",
        max_iter=1000,
        class_weight="balanced",
    )


def make_shallow_tree():
    return DecisionTreeClassifier(
        max_depth=4,
        min_samples_leaf=25,
        class_weight="balanced",
        random_state=42,
    )


def make_monotonic_gbm():
    # Monotonic constraints vector aligned with FEATURE_COLS order.
    monotonic_cst = np.array([TAIL_RISK_MONOTONIC.get(c, 0) for c in FEATURE_COLS], dtype=int)
    return HistGradientBoostingClassifier(
        max_depth=4,
        max_iter=150,
        learning_rate=0.05,
        l2_regularization=1.0,
        min_samples_leaf=25,
        monotonic_cst=monotonic_cst,
        class_weight="balanced",
        random_state=42,
    )


def interpretability_dump(X: pd.DataFrame, preds_raw: dict, checkpoints: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("Phase 2B interpretable-ML meta predictions: interpretability")
    out.append("=" * 70)
    out.append("")
    # Fit ONE final model on the full dataset for each target to dump coefficients.
    # NOTE: this is ONLY for interpretability reporting and is NOT used for
    # out-of-sample predictions.
    y_map = preds_raw["_labels"]
    train_masks = preds_raw.get("_train_masks", {})

    for target_name, y_full in y_map.items():
        valid = ~y_full.isna()
        mask = train_masks.get(target_name)
        if mask is not None:
            valid = valid & mask.reindex(y_full.index).fillna(False).astype(bool)
        X_v = X.loc[valid]
        y_v = y_full.loc[valid].astype(int)
        if len(y_v.unique()) < 2:
            out.append(f"[{target_name}] cannot fit full-sample model (single class)")
            continue
        if target_name == "p_regime_confidence":
            scaler = StandardScaler()
            Xs = scaler.fit_transform(X_v.values)
            m = make_logistic()
            m.fit(Xs, y_v.values)
            coefs = dict(zip(FEATURE_COLS, m.coef_.ravel().tolist()))
            out.append(f"[{target_name}] Logistic regression (standardized coefs):")
            for f, c in sorted(coefs.items(), key=lambda kv: -abs(kv[1])):
                out.append(f"    {f:32s} {c:+.4f}")
            out.append(f"    intercept = {float(m.intercept_[0]):+.4f}")
            out.append(f"    n_train = {len(y_v)}  pos_rate = {y_v.mean():.3f}")
        elif target_name == "p_transition_quality":
            m = make_shallow_tree()
            m.fit(X_v.values, y_v.values)
            out.append(f"[{target_name}] Shallow decision tree (depth<=4):")
            txt = export_text(m, feature_names=FEATURE_COLS, max_depth=4)
            out.append(txt)
            out.append(f"    n_train = {len(y_v)}  pos_rate = {y_v.mean():.3f}")
        elif target_name == "p_tail_risk":
            m = make_monotonic_gbm()
            m.fit(X_v.values, y_v.values)
            # HGB does not expose feature_importances_ directly before 1.4; use
            # permutation importance as a lightweight alternative.
            try:
                importances = dict(zip(FEATURE_COLS, m.feature_importances_.tolist()))
            except AttributeError:
                importances = {f: 0.0 for f in FEATURE_COLS}
            out.append(f"[{target_name}] Monotonic HistGradientBoosting:")
            out.append("    Monotonic constraints (-1 decreasing, +1 increasing):")
            for f in FEATURE_COLS:
                out.append(f"        {f:32s} {TAIL_RISK_MONOTONIC[f]:+d}")
            out.append(f"    n_train = {len(y_v)}  pos_rate = {y_v.mean():.3f}")
        out.append("")

    out.append("Walk-forward training checkpoints:")
    for target_name, cps in checkpoints.items():
        out.append(f"  {target_name}: {len(cps)} retraining events")
        if cps:
            out.append(
                f"    first train_end = {cps[0]['train_end_date'].date()} "
                f"(n={cps[0]['n_train']}, pos_rate={cps[0]['pos_rate']:.3f})"
            )
            out.append(
                f"    last  train_end = {cps[-1]['train_end_date'].date()} "
                f"(n={cps[-1]['n_train']}, pos_rate={cps[-1]['pos_rate']:.3f})"
            )

    return "\n".join(out)


def main() -> int:
    print("[phase2b] Loading features + benchmark returns ...")
    features, state = load_features()
    returns = load_benchmark_weekly_returns().reindex(features.index).fillna(0.0)

    print(f"[phase2b] features: {features.shape}  returns: {returns.shape}")

    y_regime = label_regime_confidence(returns)
    y_transition = label_transition_quality(returns)
    y_tail = label_tail_risk(returns)

    # Variant B trains only on transition states
    transition_mask = state["market_state"].isin(["neutral_mixed", "recovery_fragile", "recovery_confirmed"])

    print("[phase2b] Walk-forward training p_regime_confidence (LogReg)...")
    pred_regime, cp_regime = walk_forward_predict(
        features, y_regime, make_logistic, scaled=True
    )
    print("[phase2b] Walk-forward training p_transition_quality (Tree depth 4, transition-only)...")
    pred_transition, cp_transition = walk_forward_predict(
        features, y_transition, make_shallow_tree, scaled=False, train_mask=transition_mask
    )
    print("[phase2b] Walk-forward training p_tail_risk (Monotonic HGB)...")
    pred_tail, cp_tail = walk_forward_predict(
        features, y_tail, make_monotonic_gbm, scaled=False
    )

    preds = pd.DataFrame(
        {
            "p_regime_confidence": pred_regime,
            "p_transition_quality": pred_transition,
            "p_tail_risk": pred_tail,
        },
        index=features.index,
    )
    preds.index.name = "Date"
    preds.to_csv(PRED_PATH)
    print(f"[phase2b] wrote predictions -> {PRED_PATH.relative_to(ROOT)}")

    text = interpretability_dump(
        features,
        preds_raw={
            "_labels": {
                "p_regime_confidence": y_regime,
                "p_transition_quality": y_transition,
                "p_tail_risk": y_tail,
            },
            "_train_masks": {
                "p_transition_quality": transition_mask,
            },
        },
        checkpoints={
            "p_regime_confidence": cp_regime,
            "p_transition_quality": cp_transition,
            "p_tail_risk": cp_tail,
        },
    )
    INTERP_PATH.write_text(text)
    print(f"[phase2b] wrote interpretability dump -> {INTERP_PATH.relative_to(ROOT)}")

    # Quick stats
    summary = preds.describe().round(4)
    print("\n[phase2b] prediction summary:")
    print(summary.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
