from __future__ import annotations

"""ML Phase 3 — Meta-Allocator / Trust Model.

Phase P sits on top of the existing ML stack rather than rebuilding it.

Inputs reused:
- Phase N sleeve-level opportunity / tail / uncertainty outputs
- Phase O strongest ML Phase 2 allocator (`improved_phaseo_tail_priority_allocator`)
- Production pin (`improved_phase2b_regime_confidence_boost`)
- Best ML Phase 1 research allocator (`improved_phasen_distributional_tail_allocator`)

The goal is to learn when the ML allocator should be trusted, when production
should take over, and when a conservative multi-expert blend is preferable.

Artifacts written to data/05_layer3_portfolio_construction/:
- phase_p_meta_features.csv
- phase_p_meta_targets.csv
- phase_p_model_predictions.csv
- phase_p_feature_importance_summary.csv
- phase_p_trust_summary.csv
- phase_p_trust_by_state.csv
- phase_p_controls_{version}.csv
- phase_p_protocol.json
- portfolio_version_{weights,returns}_{version}.csv
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import phase_d_validate as pdv
import phase_f_sleeve_separability as pf
import phase_h_refined_panel_allocator as ph


ROOT = Path(__file__).resolve().parents[1]
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
SHADOW_PIN = "improved_phase2b_combo_abc"
PHASEH_REFERENCE = "improved_phaseh_refined_state_allocator"
PHASEN_REFERENCE = "improved_phasen_distributional_tail_allocator"
PHASEO_REFERENCE = "improved_phaseo_tail_priority_allocator"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"

PHASE_P_CANDIDATES = {
    "improved_phasep_hard_trust_switch_allocator": "M3-A hard trust switch",
    "improved_phasep_soft_trust_blend_allocator": "M3-B soft trust blend",
    "improved_phasep_regret_aware_meta_allocator": "M3-C regret-aware expert blend",
}

EXPERT_TO_SHORT = {
    PRODUCTION_PIN: "production",
    PHASEN_REFERENCE: "phasen",
    PHASEO_REFERENCE: "phaseo",
}
SHORT_TO_EXPERT = {short: expert for expert, short in EXPERT_TO_SHORT.items()}
MULTICLASS_LABELS = ["production", "phasen", "phaseo"]

HORIZON_WEEKS = 4
MIN_TRAIN_WEEKS = 156
RETRAIN_FREQUENCY_WEEKS = 13
EPS = 1e-9

FAVOUR_ML_STATES = {"calm_trend", "stressed_panic", "recovery_fragile"}
UNFAVOUR_ML_STATES = {"neutral_mixed", "recovery_confirmed"}


def read_indexed_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "Date" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    return frame.set_index("Date").sort_index()


def sigmoid(x: float | pd.Series) -> float | pd.Series:
    return 1.0 / (1.0 + np.exp(-x))


def tanh_clip(value: float, scale: float) -> float:
    if not np.isfinite(value) or scale <= 0:
        return 0.0
    return float(np.tanh(value / scale))


def feature_importance_frame(records: list[dict[str, float | str]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["model_name", "feature_name", "importance"])
    frame = pd.DataFrame(records)
    frame["importance"] = pd.to_numeric(frame["importance"], errors="coerce").fillna(0.0)
    return (
        frame.groupby(["model_name", "feature_name"], as_index=False)["importance"]
        .mean()
        .sort_values(["model_name", "importance"], ascending=[True, False])
    )


def offensive_defensive_columns(columns: list[str]) -> tuple[list[str], list[str]]:
    defense = [c for c in ["IEF", "SHY", "TLT", "TIP", "GLD", "LQD"] if c in columns and c != "BIL"]
    offense = [c for c in columns if c not in set(defense + ["BIL"])]
    return offense, defense


def window_utility(return_slice: pd.Series, turnover_slice: pd.Series) -> float:
    returns = pd.Series(return_slice, dtype=float).dropna()
    turns = pd.Series(turnover_slice, dtype=float).fillna(0.0).reindex(returns.index).fillna(0.0)
    if len(returns) == 0:
        return np.nan
    wealth = (1.0 + returns).cumprod()
    max_dd = float(wealth.div(wealth.cummax()).sub(1.0).min())
    downside_cutoff = returns.quantile(0.25)
    tail_mean = float(returns[returns <= downside_cutoff].mean()) if len(returns) else 0.0
    # Positive return is primary; drawdown, tail, and turnover penalize mistrustful
    # episodes without overfitting to short-window rank composites.
    return float(returns.sum() + 0.35 * max_dd + 0.15 * tail_mean - 0.03 * turns.mean())


def forward_utility_series(path_frame: pd.DataFrame, index: pd.Index, horizon_weeks: int) -> pd.Series:
    values: list[float] = []
    returns = path_frame.reindex(index)["net_return"].astype(float)
    turnover = path_frame.reindex(index)["turnover"].astype(float).fillna(0.0)
    for i, _date in enumerate(index):
        sub_idx = index[i : i + horizon_weeks]
        if len(sub_idx) < horizon_weeks:
            values.append(np.nan)
            continue
        values.append(window_utility(returns.reindex(sub_idx), turnover.reindex(sub_idx)))
    return pd.Series(values, index=index, dtype=float)


def recent_state_feature(
    diff_series: pd.Series,
    state_series: pd.Series,
    *,
    as_hit_rate: bool = False,
) -> pd.Series:
    values: list[float] = []
    for i, date in enumerate(diff_series.index):
        hist = diff_series.iloc[:i].dropna()
        if len(hist) < 52:
            values.append(0.0)
            continue
        hist_states = state_series.reindex(hist.index)
        current_state = state_series.loc[date]
        if as_hit_rate:
            grouped = (hist > 0.0).astype(float).groupby(hist_states).mean()
        else:
            grouped = hist.groupby(hist_states).mean()
        values.append(float(grouped.get(current_state, 0.0)))
    return pd.Series(values, index=diff_series.index, dtype=float)


def trailing_relative_features(
    feature_frame: pd.DataFrame,
    *,
    expert_short: str,
    expert_returns: pd.Series,
    production_returns: pd.Series,
    state_series: pd.Series,
) -> None:
    excess = expert_returns - production_returns
    feature_frame[f"{expert_short}_excess_1w_lag"] = excess.shift(1).fillna(0.0)
    for window in [4, 8, 13, 26]:
        lagged = excess.shift(1)
        feature_frame[f"{expert_short}_ex_mean_{window}"] = (
            lagged.rolling(window, min_periods=max(2, window // 2)).mean().fillna(0.0)
        )
        feature_frame[f"{expert_short}_ex_hit_{window}"] = (
            (lagged > 0.0).astype(float).rolling(window, min_periods=max(2, window // 2)).mean().fillna(0.0)
        )
        vol = lagged.rolling(window, min_periods=max(4, window // 2)).std(ddof=0).replace(0.0, np.nan)
        sharpe_like = lagged.rolling(window, min_periods=max(4, window // 2)).mean().div(vol)
        feature_frame[f"{expert_short}_ex_sharpe_{window}"] = sharpe_like.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    feature_frame[f"{expert_short}_state_edge_mean"] = recent_state_feature(excess, state_series).fillna(0.0)
    feature_frame[f"{expert_short}_state_edge_hit"] = recent_state_feature(
        excess, state_series, as_hit_rate=True
    ).fillna(0.0)


def expert_exposure_features(
    feature_frame: pd.DataFrame,
    *,
    expert_short: str,
    etf_weights: pd.DataFrame,
    sleeve_weights: pd.DataFrame | None,
    decision_pred: pd.DataFrame,
    tail_pred: pd.DataFrame,
    uncertainty_pred: pd.DataFrame,
) -> None:
    weight_frame = etf_weights.copy()
    offense_cols, defense_cols = offensive_defensive_columns(list(weight_frame.columns))
    feature_frame[f"{expert_short}_cash"] = weight_frame.get("BIL", pd.Series(0.0, index=weight_frame.index)).fillna(0.0)
    feature_frame[f"{expert_short}_spy"] = weight_frame.get("SPY", pd.Series(0.0, index=weight_frame.index)).fillna(0.0)
    feature_frame[f"{expert_short}_offense"] = weight_frame.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1)
    feature_frame[f"{expert_short}_defense"] = weight_frame.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1)

    if sleeve_weights is None:
        return

    risky = sleeve_weights.reindex(columns=ph.ACTIVE_PANEL, fill_value=0.0)
    risky_norm = risky.div(risky.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    feature_frame[f"{expert_short}_top1_share"] = risky_norm.max(axis=1)
    feature_frame[f"{expert_short}_hhi"] = risky_norm.pow(2).sum(axis=1)
    feature_frame[f"{expert_short}_weighted_decision"] = (
        risky_norm.reindex(decision_pred.index).fillna(0.0) * decision_pred.reindex(risky_norm.index).fillna(0.0)
    ).sum(axis=1)
    feature_frame[f"{expert_short}_weighted_tail"] = (
        risky_norm.reindex(tail_pred.index).fillna(0.0) * tail_pred.reindex(risky_norm.index).fillna(0.0)
    ).sum(axis=1)
    feature_frame[f"{expert_short}_weighted_uncertainty"] = (
        risky_norm.reindex(uncertainty_pred.index).fillna(0.0) * uncertainty_pred.reindex(risky_norm.index).fillna(0.0)
    ).sum(axis=1)

    for role_name in ["calm", "recovery", "chop", "defense"]:
        role_values = pd.Series(
            {sleeve: ph.ROLE_MAP[sleeve][role_name] for sleeve in ph.ACTIVE_PANEL},
            dtype=float,
        )
        feature_frame[f"{expert_short}_role_{role_name}"] = risky_norm.mul(role_values, axis=1).sum(axis=1)


def softmax_weights(score_map: dict[str, float]) -> dict[str, float]:
    aligned = pd.Series(score_map, dtype=float).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    shifted = aligned - float(aligned.max())
    exp_values = np.exp(shifted).clip(lower=EPS)
    total = float(exp_values.sum())
    if total <= 0.0:
        return {key: 1.0 / len(aligned) for key in aligned.index}
    return {key: float(value / total) for key, value in exp_values.items()}


def save_meta_portfolio_version(version_name: str, etf_weights: pd.DataFrame, next_week_returns: pd.DataFrame) -> pd.DataFrame:
    aligned_returns = next_week_returns.reindex(index=etf_weights.index, columns=etf_weights.columns).fillna(0.0)
    path = pf.compute_portfolio_path(etf_weights, aligned_returns)
    etf_weights.to_csv(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")
    path.to_csv(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")
    return path


def walkforward_binary_classifier(
    feature_frame: pd.DataFrame,
    label_series: pd.Series,
    feature_cols: list[str],
    *,
    model_name: str,
) -> tuple[pd.Series, pd.DataFrame]:
    probs = pd.Series(0.0, index=feature_frame.index, dtype=float)
    importance_records: list[dict[str, float | str]] = []

    model: LogisticRegression | None = None
    scaler: StandardScaler | None = None
    last_fit_i = -10_000

    for i, date in enumerate(feature_frame.index):
        train_end = i - HORIZON_WEEKS
        if train_end > 0 and (model is None or (i - last_fit_i) >= RETRAIN_FREQUENCY_WEEKS):
            train_index = feature_frame.index[:train_end]
            y = label_series.reindex(train_index)
            X = feature_frame.reindex(train_index, columns=feature_cols).fillna(0.0)
            mask = y.notna()
            X = X.loc[mask]
            y = y.loc[mask].astype(int)
            if X.index.nunique() >= MIN_TRAIN_WEEKS and y.nunique() >= 2:
                scaler = StandardScaler()
                Xs = scaler.fit_transform(X)
                model = LogisticRegression(max_iter=2000, C=0.70, class_weight="balanced")
                model.fit(Xs, y)
                last_fit_i = i
                for feature_name, coef in zip(feature_cols, model.coef_[0]):
                    importance_records.append(
                        {
                            "model_name": model_name,
                            "feature_name": feature_name,
                            "importance": float(abs(coef)),
                        }
                    )

        if model is None or scaler is None:
            probs.loc[date] = 0.0
            continue
        X_now = feature_frame.loc[[date], feature_cols].fillna(0.0)
        probs.loc[date] = float(model.predict_proba(scaler.transform(X_now))[0, 1])

    return probs, feature_importance_frame(importance_records)


def build_feature_frame() -> tuple[
    pd.DataFrame,
    dict[str, pd.Series],
    dict[str, pd.DataFrame],
    dict[str, pd.Series],
    pd.DataFrame,
    pd.DataFrame,
]:
    next_week_returns = np.expm1(read_indexed_csv(DATA_HUB_DIR / "weekly_returns.csv")).shift(-1)
    market_state_history = read_indexed_csv(LAYER2B_DIR / "market_state_history.csv")

    returns_map: dict[str, pd.Series] = {}
    weights_map: dict[str, pd.DataFrame] = {}
    path_map: dict[str, pd.DataFrame] = {}
    sleeve_map: dict[str, pd.DataFrame] = {}

    for version_name in [PRODUCTION_PIN, PHASEN_REFERENCE, PHASEO_REFERENCE]:
        path_map[version_name] = read_indexed_csv(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")
        weights_map[version_name] = read_indexed_csv(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")
        returns_map[version_name] = path_map[version_name]["net_return"]

    for version_name in [PHASEN_REFERENCE, PHASEO_REFERENCE]:
        sleeve_map[version_name] = read_indexed_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv")

    index = weights_map[PRODUCTION_PIN].index
    for frame in list(weights_map.values()) + [next_week_returns, market_state_history]:
        index = index.intersection(frame.index)
    index = index.sort_values()

    next_week_returns = next_week_returns.reindex(index).fillna(0.0)
    market_state_history = market_state_history.reindex(index)
    for version_name in list(weights_map):
        weights_map[version_name] = weights_map[version_name].reindex(index).fillna(0.0)
        path_map[version_name] = path_map[version_name].reindex(index)
        returns_map[version_name] = returns_map[version_name].reindex(index)
    for version_name in list(sleeve_map):
        sleeve_map[version_name] = sleeve_map[version_name].reindex(index).fillna(0.0)

    state_features = ph.state_feature_frame(index, market_state_history)
    state_dummies = pd.get_dummies(state_features["state_text"], prefix="state", dtype=float)
    feature_frame = state_features.drop(columns=["state_text"]).join(state_dummies, how="left")

    controls = read_indexed_csv(LAYER3_DIR / f"phase_o_controls_{PHASEO_REFERENCE}.csv").reindex(index).fillna(0.0)
    decision_pred = read_indexed_csv(LAYER3_DIR / "phase_n_decision_predictions.csv").reindex(index).fillna(0.0)
    tail_pred = read_indexed_csv(LAYER3_DIR / "phase_n_tail_predictions.csv").reindex(index).fillna(0.0)
    uncertainty_pred = read_indexed_csv(LAYER3_DIR / "phase_n_prediction_uncertainty.csv").reindex(index).fillna(0.0)
    gate_probs = read_indexed_csv(LAYER3_DIR / "phase_n_gate_probabilities.csv").reindex(index).fillna(0.0)

    for col in [
        "model_confidence",
        "model_uncertainty",
        "margin_confidence",
        "agreement",
        "signal_top_gap",
        "risk_guard",
        "cash_weight",
        "mu_scale",
        "lambda_turn",
        "lambda_tail",
        "lambda_anchor",
        "safe_mix",
        "freeze_prev",
    ]:
        feature_frame[col] = pd.to_numeric(controls[col], errors="coerce").fillna(0.0)

    feature_frame["phase_n_avg_uncertainty"] = uncertainty_pred.mean(axis=1)
    feature_frame["phase_n_max_uncertainty"] = uncertainty_pred.max(axis=1)
    feature_frame["phase_n_uncertainty_std"] = uncertainty_pred.std(axis=1, ddof=0)
    feature_frame["phase_n_decision_gap"] = decision_pred.max(axis=1) - decision_pred.median(axis=1)
    feature_frame["phase_n_tail_gap"] = tail_pred.max(axis=1) - tail_pred.median(axis=1)
    feature_frame["phase_n_gate_top"] = gate_probs.max(axis=1)
    gate_entropy = -(gate_probs.clip(lower=1e-9) * np.log(gate_probs.clip(lower=1e-9))).sum(axis=1)
    feature_frame["phase_n_gate_entropy"] = gate_entropy.div(np.log(max(len(gate_probs.columns), 2))).fillna(0.0)

    expert_exposure_features(
        feature_frame,
        expert_short="phaseo",
        etf_weights=weights_map[PHASEO_REFERENCE],
        sleeve_weights=sleeve_map[PHASEO_REFERENCE],
        decision_pred=decision_pred[ph.ACTIVE_PANEL],
        tail_pred=tail_pred[ph.ACTIVE_PANEL],
        uncertainty_pred=uncertainty_pred[ph.ACTIVE_PANEL],
    )
    expert_exposure_features(
        feature_frame,
        expert_short="phasen",
        etf_weights=weights_map[PHASEN_REFERENCE],
        sleeve_weights=sleeve_map[PHASEN_REFERENCE],
        decision_pred=decision_pred[ph.ACTIVE_PANEL],
        tail_pred=tail_pred[ph.ACTIVE_PANEL],
        uncertainty_pred=uncertainty_pred[ph.ACTIVE_PANEL],
    )
    expert_exposure_features(
        feature_frame,
        expert_short="production",
        etf_weights=weights_map[PRODUCTION_PIN],
        sleeve_weights=None,
        decision_pred=decision_pred[ph.ACTIVE_PANEL],
        tail_pred=tail_pred[ph.ACTIVE_PANEL],
        uncertainty_pred=uncertainty_pred[ph.ACTIVE_PANEL],
    )

    feature_frame["phaseo_prod_l1_gap"] = (weights_map[PHASEO_REFERENCE] - weights_map[PRODUCTION_PIN]).abs().sum(axis=1)
    feature_frame["phasen_prod_l1_gap"] = (weights_map[PHASEN_REFERENCE] - weights_map[PRODUCTION_PIN]).abs().sum(axis=1)
    feature_frame["phaseo_phasen_l1_gap"] = (weights_map[PHASEO_REFERENCE] - weights_map[PHASEN_REFERENCE]).abs().sum(axis=1)

    state_series = state_features["state_text"]
    trailing_relative_features(
        feature_frame,
        expert_short="phaseo",
        expert_returns=returns_map[PHASEO_REFERENCE],
        production_returns=returns_map[PRODUCTION_PIN],
        state_series=state_series,
    )
    trailing_relative_features(
        feature_frame,
        expert_short="phasen",
        expert_returns=returns_map[PHASEN_REFERENCE],
        production_returns=returns_map[PRODUCTION_PIN],
        state_series=state_series,
    )

    utility_map = {
        PRODUCTION_PIN: forward_utility_series(path_map[PRODUCTION_PIN], index, HORIZON_WEEKS),
        PHASEN_REFERENCE: forward_utility_series(path_map[PHASEN_REFERENCE], index, HORIZON_WEEKS),
        PHASEO_REFERENCE: forward_utility_series(path_map[PHASEO_REFERENCE], index, HORIZON_WEEKS),
    }
    target_frame = pd.DataFrame(index=index)
    target_frame["production_forward_utility"] = utility_map[PRODUCTION_PIN]
    target_frame["phasen_forward_utility"] = utility_map[PHASEN_REFERENCE]
    target_frame["phaseo_forward_utility"] = utility_map[PHASEO_REFERENCE]
    target_frame["phaseo_minus_production_utility"] = (
        target_frame["phaseo_forward_utility"] - target_frame["production_forward_utility"]
    )
    target_frame["phasen_minus_production_utility"] = (
        target_frame["phasen_forward_utility"] - target_frame["production_forward_utility"]
    )
    target_frame["phaseo_trust_label"] = (
        target_frame["phaseo_minus_production_utility"] > 0.0
    ).astype(float)
    target_frame["phasen_trust_label"] = (
        target_frame["phasen_minus_production_utility"] > 0.0
    ).astype(float)

    feature_frame["state_text"] = state_series
    feature_frame = feature_frame.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return feature_frame, returns_map, weights_map, target_frame, next_week_returns, market_state_history


def build_candidate_weights(
    feature_frame: pd.DataFrame,
    *,
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
    weights_map: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    candidate_weights: dict[str, list[pd.Series]] = {name: [] for name in PHASE_P_CANDIDATES}
    control_rows: dict[str, list[pd.Series]] = {name: [] for name in PHASE_P_CANDIDATES}

    phaseo_weights = weights_map[PHASEO_REFERENCE]
    phasen_weights = weights_map[PHASEN_REFERENCE]
    prod_weights = weights_map[PRODUCTION_PIN]
    columns = list(prod_weights.columns)

    prev_hard_ml = False

    for date in feature_frame.index:
        st = feature_frame.loc[date, "state_text"]
        phaseo_state_edge = float(feature_frame.loc[date, "phaseo_state_edge_mean"])
        phasen_state_edge = float(feature_frame.loc[date, "phasen_state_edge_mean"])
        phaseo_ex13 = float(feature_frame.loc[date, "phaseo_ex_mean_13"])
        phasen_ex13 = float(feature_frame.loc[date, "phasen_ex_mean_13"])
        model_uncertainty = float(feature_frame.loc[date, "model_uncertainty"])
        model_confidence = float(feature_frame.loc[date, "model_confidence"])
        risk_guard = float(feature_frame.loc[date, "risk_guard"])
        p_phaseo = float(phaseo_prob.loc[date])
        p_phasen = float(phasen_prob.loc[date])

        favourable_flag = 1.0 if st in FAVOUR_ML_STATES else 0.0
        unfavourable_flag = 1.0 if st in UNFAVOUR_ML_STATES else 0.0

        # M3-A: hard trust switch.
        hard_trust = float(
            np.clip(
                p_phaseo
                + 0.08 * favourable_flag
                - 0.08 * unfavourable_flag
                + 0.05 * tanh_clip(phaseo_state_edge, 0.0015)
                + 0.03 * tanh_clip(phaseo_ex13, 0.0010)
                - 0.10 * model_uncertainty
                + 0.03 * model_confidence,
                0.0,
                1.0,
            )
        )
        threshold = 0.60 if not prev_hard_ml else 0.52
        use_phaseo = hard_trust >= threshold
        prev_hard_ml = use_phaseo
        hard_weights = phaseo_weights.loc[date] if use_phaseo else prod_weights.loc[date]
        candidate_weights["improved_phasep_hard_trust_switch_allocator"].append(
            hard_weights.reindex(columns).fillna(0.0).rename(date)
        )
        control_rows["improved_phasep_hard_trust_switch_allocator"].append(
            pd.Series(
                {
                    "state_text": st,
                    "production_weight": float(not use_phaseo),
                    "phasen_weight": 0.0,
                    "phaseo_weight": float(use_phaseo),
                    "trust_score": hard_trust,
                    "phaseo_prob": p_phaseo,
                    "threshold": threshold,
                    "model_confidence": model_confidence,
                    "model_uncertainty": model_uncertainty,
                    "phaseo_state_edge_mean": phaseo_state_edge,
                    "phaseo_ex_mean_13": phaseo_ex13,
                    "risk_guard": risk_guard,
                    "selected_expert": "phaseo" if use_phaseo else "production",
                },
                name=date,
            )
        )

        # M3-B: soft blend between production and Phase O.
        soft_trust = float(
            np.clip(
                0.72 * p_phaseo
                + 0.08 * favourable_flag
                - 0.09 * unfavourable_flag
                + 0.06 * tanh_clip(phaseo_state_edge, 0.0015)
                + 0.05 * tanh_clip(phaseo_ex13, 0.0010)
                - 0.14 * model_uncertainty
                + 0.04 * model_confidence
                - 0.05 * tanh_clip(float(feature_frame.loc[date, "phaseo_prod_l1_gap"]), 0.80) * model_uncertainty,
                0.0,
                1.0,
            )
        )
        soft_weights = soft_trust * phaseo_weights.loc[date] + (1.0 - soft_trust) * prod_weights.loc[date]
        candidate_weights["improved_phasep_soft_trust_blend_allocator"].append(
            soft_weights.reindex(columns).fillna(0.0).rename(date)
        )
        soft_selected_expert = "phaseo" if soft_trust >= 0.50 else "production"
        control_rows["improved_phasep_soft_trust_blend_allocator"].append(
            pd.Series(
                {
                    "state_text": st,
                    "production_weight": 1.0 - soft_trust,
                    "phasen_weight": 0.0,
                    "phaseo_weight": soft_trust,
                    "trust_score": soft_trust,
                    "phaseo_prob": p_phaseo,
                    "model_confidence": model_confidence,
                    "model_uncertainty": model_uncertainty,
                    "phaseo_state_edge_mean": phaseo_state_edge,
                    "phaseo_ex_mean_13": phaseo_ex13,
                    "risk_guard": risk_guard,
                    "selected_expert": soft_selected_expert,
                },
                name=date,
            )
        )

        # M3-C: regret-aware expert blend across production / Phase N / Phase O.
        expert_scores = {
            "production": 0.55
            + 0.10 * unfavourable_flag
            + 0.10 * model_uncertainty
            - 0.16 * max(p_phaseo, p_phasen)
            - 0.05 * favourable_flag,
            "phasen": 0.18
            + p_phasen
            + 0.05 * tanh_clip(phasen_state_edge, 0.0015)
            + 0.05 * tanh_clip(phasen_ex13, 0.0010)
            + 0.03 * model_uncertainty
            + 0.02 * favourable_flag,
            "phaseo": 0.18
            + p_phaseo
            + 0.10 * favourable_flag
            - 0.08 * unfavourable_flag
            + 0.07 * tanh_clip(phaseo_state_edge, 0.0015)
            + 0.04 * tanh_clip(phaseo_ex13, 0.0010)
            - 0.08 * model_uncertainty
            + 0.03 * model_confidence,
        }
        blend_map = softmax_weights(expert_scores)
        regret_weights = (
            blend_map["production"] * prod_weights.loc[date]
            + blend_map["phasen"] * phasen_weights.loc[date]
            + blend_map["phaseo"] * phaseo_weights.loc[date]
        )
        candidate_weights["improved_phasep_regret_aware_meta_allocator"].append(
            regret_weights.reindex(columns).fillna(0.0).rename(date)
        )
        control_rows["improved_phasep_regret_aware_meta_allocator"].append(
            pd.Series(
                {
                    "state_text": st,
                    "production_weight": blend_map["production"],
                    "phasen_weight": blend_map["phasen"],
                    "phaseo_weight": blend_map["phaseo"],
                    "trust_score": blend_map["phaseo"] + 0.5 * blend_map["phasen"],
                    "phaseo_prob": p_phaseo,
                    "phasen_prob": p_phasen,
                    "model_confidence": model_confidence,
                    "model_uncertainty": model_uncertainty,
                    "phaseo_state_edge_mean": phaseo_state_edge,
                    "phasen_state_edge_mean": phasen_state_edge,
                    "phaseo_ex_mean_13": phaseo_ex13,
                    "phasen_ex_mean_13": phasen_ex13,
                    "risk_guard": risk_guard,
                    "selected_expert": max(blend_map.items(), key=lambda kv: kv[1])[0],
                },
                name=date,
            )
        )

    weight_frames = {
        name: pd.DataFrame(rows).sort_index().fillna(0.0)
        for name, rows in candidate_weights.items()
    }
    control_frames = {
        name: pd.DataFrame(rows).sort_index()
        for name, rows in control_rows.items()
    }
    return weight_frames, control_frames


def trust_summary(version_name: str, controls: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    control = controls.copy()
    overall = pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_production_weight": float(control["production_weight"].mean()),
                "avg_phasen_weight": float(control["phasen_weight"].mean()),
                "avg_phaseo_weight": float(control["phaseo_weight"].mean()),
                "avg_trust_score": float(control["trust_score"].mean()),
                "avg_phaseo_prob": float(control["phaseo_prob"].mean()),
                "avg_model_confidence": float(control["model_confidence"].mean()),
                "avg_model_uncertainty": float(control["model_uncertainty"].mean()),
                "phaseo_selected_share": float((control["selected_expert"] == "phaseo").mean()),
                "production_selected_share": float((control["selected_expert"] == "production").mean()),
                "phasen_selected_share": float((control["selected_expert"] == "phasen").mean()),
            }
        ]
    )

    state_rows: list[dict[str, float | str]] = []
    for state_text, group in control.groupby("state_text"):
        state_rows.append(
            {
                "version_name": version_name,
                "market_state": state_text,
                "observations": int(len(group)),
                "avg_production_weight": float(group["production_weight"].mean()),
                "avg_phasen_weight": float(group["phasen_weight"].mean()),
                "avg_phaseo_weight": float(group["phaseo_weight"].mean()),
                "avg_trust_score": float(group["trust_score"].mean()),
                "avg_phaseo_prob": float(group["phaseo_prob"].mean()),
                "avg_model_confidence": float(group["model_confidence"].mean()),
                "avg_model_uncertainty": float(group["model_uncertainty"].mean()),
                "phaseo_selected_share": float((group["selected_expert"] == "phaseo").mean()),
                "production_selected_share": float((group["selected_expert"] == "production").mean()),
                "phasen_selected_share": float((group["selected_expert"] == "phasen").mean()),
            }
        )
    return overall, pd.DataFrame(state_rows)


def main() -> None:
    feature_frame, returns_map, weights_map, target_frame, next_week_returns, market_state_history = build_feature_frame()

    feature_cols = [
        col
        for col in feature_frame.columns
        if col != "state_text"
    ]

    phaseo_prob, phaseo_importance = walkforward_binary_classifier(
        feature_frame,
        target_frame["phaseo_trust_label"],
        feature_cols,
        model_name="phasep_binary_phaseo_vs_production",
    )
    phasen_prob, phasen_importance = walkforward_binary_classifier(
        feature_frame,
        target_frame["phasen_trust_label"],
        feature_cols,
        model_name="phasep_binary_phasen_vs_production",
    )

    model_predictions = pd.DataFrame(index=feature_frame.index)
    model_predictions["phaseo_trust_probability"] = phaseo_prob
    model_predictions["phasen_trust_probability"] = phasen_prob

    weight_frames, control_frames = build_candidate_weights(
        feature_frame,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        weights_map=weights_map,
    )

    trust_overall_rows = []
    trust_state_rows = []
    for version_name, etf_weights in weight_frames.items():
        path = save_meta_portfolio_version(version_name, etf_weights, next_week_returns)
        controls = control_frames[version_name]
        controls.to_csv(LAYER3_DIR / f"phase_p_controls_{version_name}.csv")
        overall, by_state = trust_summary(version_name, controls)
        trust_overall_rows.append(overall)
        trust_state_rows.append(by_state)

        ann_return = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        print(
            f"{version_name}: ann_return={ann_return:.4f} "
            f"sharpe={(ann_return / ann_vol) if ann_vol > 0 else np.nan:.4f} "
            f"turnover={path['turnover'].dropna().mean():.4f}"
        )

    importance_frames = [frame for frame in [phaseo_importance, phasen_importance] if not frame.empty]
    feature_importance = (
        pd.concat(importance_frames, ignore_index=True)
        if importance_frames
        else pd.DataFrame(columns=["model_name", "feature_name", "importance"])
    )
    trust_summary_df = pd.concat(trust_overall_rows, ignore_index=True)
    trust_by_state_df = pd.concat(trust_state_rows, ignore_index=True)

    feature_frame.drop(columns=["state_text"]).to_csv(LAYER3_DIR / "phase_p_meta_features.csv")
    target_frame.to_csv(LAYER3_DIR / "phase_p_meta_targets.csv")
    model_predictions.to_csv(LAYER3_DIR / "phase_p_model_predictions.csv")
    feature_importance.to_csv(LAYER3_DIR / "phase_p_feature_importance_summary.csv", index=False)
    trust_summary_df.to_csv(LAYER3_DIR / "phase_p_trust_summary.csv", index=False)
    trust_by_state_df.to_csv(LAYER3_DIR / "phase_p_trust_by_state.csv", index=False)

    protocol = {
        "phase": "Phase P — Meta-Allocator / Trust Model (ML Phase 3)",
        "production_pin": PRODUCTION_PIN,
        "shadow_pin": SHADOW_PIN,
        "reference_allocators": {
            "phaseh": PHASEH_REFERENCE,
            "phasen": PHASEN_REFERENCE,
            "phaseo": PHASEO_REFERENCE,
        },
        "phase_p_candidates": PHASE_P_CANDIDATES,
        "feature_family": {
            "state_confidence": True,
            "phase_n_uncertainty": True,
            "phase_o_controls": True,
            "expert_disagreement": True,
            "role_exposure_summaries": True,
            "recent_relative_quality": True,
            "state_conditioned_trust": True,
        },
        "target_definition": {
            "forward_horizon_weeks": HORIZON_WEEKS,
            "window_utility": "sum(net_return) + 0.35*max_drawdown + 0.15*tail_mean_25pct - 0.03*avg_turnover",
            "binary_target": "phaseo_forward_utility > production_forward_utility",
            "second_binary_target": "phasen_forward_utility > production_forward_utility",
        },
        "training_rule": {
            "min_train_weeks": MIN_TRAIN_WEEKS,
            "retrain_frequency_weeks": RETRAIN_FREQUENCY_WEEKS,
            "walkforward_safe": True,
            "default_before_training": "production",
        },
    }
    (LAYER3_DIR / "phase_p_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("Saved Phase P meta-allocation artifacts.")


if __name__ == "__main__":
    main()
