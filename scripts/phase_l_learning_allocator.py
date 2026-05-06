from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import phase_h_refined_panel_allocator as ph
import phase_i_refined_allocator_refinement as pi
import phase_j_structural_allocator as pj
import phase_k_allocator_framework as pk


ROOT = Path(__file__).resolve().parents[1]
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
TAIL_AWARE_BRANCH = "improved_phasek_tail_aware_role_framework"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"

PHASE_L_CANDIDATES = {
    "improved_phasel_decision_utility_allocator": "L1 decision-aware role allocator",
    "improved_phasel_selective_concentration_allocator": "L2 robustness-aware selective concentration allocator",
    "improved_phasel_tail_turnover_learning_allocator": "L3 tail/turnover constrained learning allocator",
}

HORIZON_WEEKS = 4
MIN_TRAIN_WEEKS = 156
RETRAIN_FREQUENCY_WEEKS = 26
EPS = 1e-9


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)
    return clean / total


def add_learning_targets(long_panel: pd.DataFrame) -> pd.DataFrame:
    panel = long_panel.copy()
    future = pd.to_numeric(panel["target_return_4w"], errors="coerce")
    neg_future = future.clip(upper=0.0).abs()
    vol = pd.to_numeric(panel["vol_13"], errors="coerce").fillna(panel["vol_13"].median())
    drawdown = pd.to_numeric(panel["dd_13"], errors="coerce").abs().fillna(panel["dd_13"].abs().median())
    risk_guard = pd.concat(
        [
            pd.to_numeric(panel["stress_confidence"], errors="coerce"),
            pd.to_numeric(panel["chop_confidence"], errors="coerce"),
        ],
        axis=1,
    ).max(axis=1).fillna(0.0)
    offensive_role = 1.0 - (
        0.55 * pd.to_numeric(panel["role_defense"], errors="coerce").fillna(0.0)
        + 0.35 * pd.to_numeric(panel["role_chop"], errors="coerce").fillna(0.0)
    ).clip(0.0, 1.0)

    panel["decision_utility_raw"] = (
        future
        - 0.70 * neg_future
        - 0.10 * vol
        - 0.05 * drawdown
        - 0.018 * risk_guard * offensive_role
    )
    panel["tail_utility_raw"] = (
        future
        - 1.25 * neg_future
        - 0.18 * vol
        - 0.12 * drawdown
        - 0.030 * risk_guard * offensive_role
    )
    for raw_col, label_col in [
        ("decision_utility_raw", "decision_utility_target"),
        ("tail_utility_raw", "tail_utility_target"),
    ]:
        panel[label_col] = panel.groupby("Date")[raw_col].transform(
            lambda x: ((x.rank(pct=True, method="average") - 0.5) * 2.0)
        )
    return panel.replace([np.inf, -np.inf], np.nan)


def build_date_learning_panel(date_panel: pd.DataFrame, utility_panel: pd.DataFrame) -> pd.DataFrame:
    utility_by_date = utility_panel.pivot(index="Date", columns="sleeve", values="decision_utility_raw")
    frame = date_panel.copy()
    frame["future_utility_spread"] = utility_by_date.max(axis=1) - utility_by_date.median(axis=1)
    frame["future_utility_top_gap"] = utility_by_date.max(axis=1) - utility_by_date.apply(lambda row: row.nlargest(2).iloc[-1], axis=1)
    return frame.replace([np.inf, -np.inf], np.nan)


def walkforward_panel_utility_model(panel: pd.DataFrame, feature_cols: list[str], target_col: str, *, alpha: float) -> ph.ModelPredictionResult:
    prediction_rows: list[pd.Series] = []
    feature_importances: list[pd.Series] = []
    fitted_model = None
    last_fit_date: pd.Timestamp | None = None

    for date in sorted(pd.Index(panel["Date"].dropna().unique())):
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel[target_col].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model.fit(train[feature_cols].fillna(0.0), train[target_col].astype(float))
                fitted_model = model
                feature_importances.append(pd.Series(np.abs(model.named_steps["ridge"].coef_), index=feature_cols))
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        if date_rows.empty:
            continue
        prediction = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)
        if fitted_model is None:
            prediction.loc[:] = 0.0
        else:
            prediction.loc[:] = fitted_model.predict(date_rows[feature_cols].fillna(0.0))
        prediction_rows.append(prediction)

    prediction_frame = pd.DataFrame(prediction_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0)
    importance = pd.concat(feature_importances, axis=1).mean(axis=1).sort_values(ascending=False) if feature_importances else pd.Series(dtype=float)
    return ph.ModelPredictionResult(prediction_frame=prediction_frame, feature_importance=importance)


def walkforward_date_utility_model(panel: pd.DataFrame, feature_cols: list[str], target_col: str, *, alpha: float) -> ph.ModelPredictionResult:
    prediction_rows: list[pd.Series] = []
    feature_importances: list[pd.Series] = []
    fitted_model = None
    last_fit_date: pd.Timestamp | None = None

    for date in sorted(pd.Index(panel["Date"].dropna().unique())):
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel[target_col].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model.fit(train[feature_cols].fillna(0.0), train[target_col].astype(float))
                fitted_model = model
                feature_importances.append(pd.Series(np.abs(model.named_steps["ridge"].coef_), index=feature_cols))
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        if date_rows.empty:
            continue
        value = 0.0 if fitted_model is None else float(fitted_model.predict(date_rows[feature_cols].fillna(0.0))[0])
        prediction_rows.append(pd.Series({target_col.replace("future_", "predicted_"): value}, name=date))

    prediction_frame = pd.DataFrame(prediction_rows).sort_index()
    importance = pd.concat(feature_importances, axis=1).mean(axis=1).sort_values(ascending=False) if feature_importances else pd.Series(dtype=float)
    return ph.ModelPredictionResult(prediction_frame=prediction_frame, feature_importance=importance)


def candidate_signal(
    candidate_name: str,
    date: pd.Timestamp,
    decision_scores: pd.DataFrame,
    tail_scores: pd.DataFrame,
    state_prior: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    reference_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
) -> pd.Series:
    decision_rank = ph.centered_rank(decision_scores.loc[date, ph.ACTIVE_PANEL])
    tail_rank = ph.centered_rank(tail_scores.loc[date, ph.ACTIVE_PANEL])
    prior_rank = ph.centered_rank(state_prior.loc[date, ph.ACTIVE_PANEL])
    simple_rank = ph.centered_rank(simple_score_panel.loc[date, ph.ACTIVE_PANEL])
    ref_rank = ph.centered_rank(reference_weights.loc[date, ph.ACTIVE_PANEL])
    tail_ref_rank = ph.centered_rank(tail_weights.loc[date, ph.ACTIVE_PANEL])

    if candidate_name == "improved_phasel_decision_utility_allocator":
        signal = 0.58 * decision_rank + 0.16 * simple_rank + 0.14 * prior_rank + 0.12 * ref_rank
    elif candidate_name == "improved_phasel_selective_concentration_allocator":
        signal = 0.50 * decision_rank + 0.20 * simple_rank + 0.12 * prior_rank + 0.10 * ref_rank + 0.08 * tail_rank
    elif candidate_name == "improved_phasel_tail_turnover_learning_allocator":
        signal = 0.45 * tail_rank + 0.25 * decision_rank + 0.12 * prior_rank + 0.10 * tail_ref_rank + 0.08 * ref_rank
    else:
        raise ValueError(candidate_name)
    return signal.fillna(0.0)


def learned_confidence(
    candidate_name: str,
    date: pd.Timestamp,
    signal: pd.Series,
    meta: pd.DataFrame,
    spread_pred: pd.DataFrame,
) -> float:
    top_gap = pj.top_margin(signal)
    margin = float(meta.loc[date, "margin_confidence"])
    agreement = float(meta.loc[date, "agreement"])
    pred_col = "predicted_utility_spread"
    predicted_spread = float(spread_pred.reindex([date]).fillna(0.0).iloc[0].get(pred_col, 0.0))
    pred_score = float(np.clip((predicted_spread - 0.004) / 0.045, 0.0, 1.0))
    base = 0.35 * pk.ph.bounded_zero_to_one(top_gap, 0.05, 0.90) + 0.30 * margin + 0.20 * pred_score + 0.15 * agreement
    if candidate_name == "improved_phasel_selective_concentration_allocator":
        return float(np.clip(base * 1.15, 0.0, 1.0))
    if candidate_name == "improved_phasel_tail_turnover_learning_allocator":
        return float(np.clip(0.75 * base, 0.0, 1.0))
    return float(np.clip(base, 0.0, 1.0))


def learned_bounds(candidate_name: str, st: pd.Series, confidence: float, margin_conf: float, agreement: float) -> tuple[dict[str, float], dict[str, float]]:
    floors, caps = pj.dynamic_bounds(st, margin_conf, agreement)
    floors = dict(floors)
    caps = dict(caps)
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))

    if candidate_name == "improved_phasel_selective_concentration_allocator":
        if confidence > 0.65 and risk_guard < 0.45:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(max(caps.get(sleeve, 0.36), 0.42), 0.48)
        elif confidence < 0.40:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(caps.get(sleeve, 1.0), 0.28)

    if candidate_name == "improved_phasel_tail_turnover_learning_allocator":
        floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.08 + 0.10 * risk_guard)
        floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.08 + 0.08 * float(st["chop_confidence"]))
        if risk_guard > 0.42:
            caps["dual_momentum_topn"] = min(caps.get("dual_momentum_topn", 1.0), 0.12)
            caps["composite_calm_trend_specialist"] = min(caps.get("composite_calm_trend_specialist", 1.0), 0.22)
            caps["composite_healthier_recovery_specialist"] = min(caps.get("composite_healthier_recovery_specialist", 1.0), 0.20)

    return floors, caps


def build_candidate_weights(
    candidate_name: str,
    decision_scores: pd.DataFrame,
    tail_scores: pd.DataFrame,
    spread_pred: pd.DataFrame,
    state_prior: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    reference_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
    meta: pd.DataFrame,
    state_features: pd.DataFrame,
    cov_map: dict[pd.Timestamp, pd.DataFrame],
    down_cov_map: dict[pd.Timestamp, pd.DataFrame],
    tail_map: dict[pd.Timestamp, pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.Series] = []
    control_rows: list[pd.Series] = []
    prev_weights: pd.Series | None = None

    for date in reference_weights.index:
        ref = normalize(reference_weights.loc[date, ph.ACTIVE_PANEL])
        tail_ref = normalize(tail_weights.loc[date, ph.ACTIVE_PANEL])
        prev = ref.copy() if prev_weights is None else prev_weights.copy()
        st = state_features.loc[date]
        margin_conf = float(meta.loc[date, "margin_confidence"])
        agreement = float(meta.loc[date, "agreement"])
        risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))
        signal = candidate_signal(candidate_name, date, decision_scores, tail_scores, state_prior, simple_score_panel, reference_weights, tail_weights)
        confidence = learned_confidence(candidate_name, date, signal, meta, spread_pred)
        floors, caps = learned_bounds(candidate_name, st, confidence, margin_conf, agreement)

        if candidate_name == "improved_phasel_decision_utility_allocator":
            anchor = normalize(0.78 * ref + 0.12 * tail_ref + 0.10 * pi.SAFE_ANCHOR)
            mu_scale = 0.95 * (0.32 + 0.82 * confidence)
            lambda_turn = 0.72 * (1.15 - 0.30 * confidence)
            lambda_anchor = 0.70 * (1.05 - 0.20 * confidence)
            lambda_var = 1.05 * (1.0 + 0.15 * risk_guard)
            lambda_down = 0.74 * (1.0 + 0.35 * risk_guard)
            lambda_tail = 0.62 * (1.0 + 0.50 * risk_guard)
            lambda_hhi = 0.24 * (1.12 - 0.25 * confidence)
        elif candidate_name == "improved_phasel_selective_concentration_allocator":
            anchor = normalize(0.76 * ref + 0.10 * tail_ref + 0.14 * pi.SAFE_ANCHOR)
            mu_scale = 1.08 * (0.18 + 1.05 * confidence)
            lambda_turn = 0.88 * (1.45 - 0.82 * confidence + 0.20 * risk_guard)
            lambda_anchor = 0.72 * (1.18 - 0.34 * confidence)
            lambda_var = 0.98 * (1.0 + 0.22 * risk_guard)
            lambda_down = 0.68 * (1.0 + 0.35 * risk_guard)
            lambda_tail = 0.58 * (1.0 + 0.45 * risk_guard)
            lambda_hhi = 0.30 * (1.25 - 0.55 * confidence + 0.25 * risk_guard)
        elif candidate_name == "improved_phasel_tail_turnover_learning_allocator":
            anchor = normalize(0.48 * ref + 0.34 * tail_ref + 0.18 * pi.SAFE_ANCHOR)
            mu_scale = 0.82 * (0.26 + 0.74 * confidence)
            lambda_turn = 1.10 * (1.12 - 0.22 * confidence)
            lambda_anchor = 0.88 * (1.10 - 0.16 * confidence)
            lambda_var = 1.24 * (1.0 + 0.30 * risk_guard)
            lambda_down = 1.02 * (1.0 + 0.55 * risk_guard)
            lambda_tail = 1.02 * (1.12 + 0.70 * risk_guard)
            lambda_hhi = 0.36 * (1.05 + 0.30 * risk_guard)
        else:
            raise ValueError(candidate_name)

        role_penalty = pj.risk_penalty_vector(st)
        risky = pk.solve_objective(
            signal,
            anchor,
            prev,
            cov_map[date],
            down_cov_map[date],
            tail_map[date],
            role_penalty,
            mu_scale=mu_scale,
            lambda_var=lambda_var,
            lambda_down=lambda_down,
            lambda_tail=lambda_tail,
            lambda_turn=lambda_turn,
            lambda_anchor=lambda_anchor,
            lambda_hhi=lambda_hhi,
            floors=floors,
            caps=caps,
        )

        row = pd.Series(0.0, index=ph.ACTIVE_PANEL + [ph.CASH_COLUMN], dtype=float, name=date)
        row.loc[ph.ACTIVE_PANEL] = risky
        rows.append(row)
        control_rows.append(
            pd.Series(
                {
                    "learned_confidence": confidence,
                    "margin_confidence": margin_conf,
                    "agreement": agreement,
                    "risk_guard": risk_guard,
                    "signal_top_gap": pj.top_margin(signal),
                    "mu_scale": mu_scale,
                    "lambda_turn": lambda_turn,
                    "lambda_tail": lambda_tail,
                },
                name=date,
            )
        )
        prev_weights = risky

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(control_rows).sort_index()


def control_summary(version_name: str, controls: pd.DataFrame, sleeve_weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risky = sleeve_weights[ph.ACTIVE_PANEL]
    risky_norm = risky.div(risky.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    merged = controls.copy()
    merged["top1_share"] = risky_norm.max(axis=1)
    merged["top2_share"] = pd.Series(np.sort(risky_norm.to_numpy(), axis=1)[:, -2:].sum(axis=1), index=risky_norm.index)
    merged["hhi"] = risky_norm.pow(2).sum(axis=1)
    merged["confidence_bucket"] = pd.cut(merged["learned_confidence"], bins=[-1e-9, 0.33, 0.66, 1.0], labels=["low", "medium", "high"])

    overall = pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_learned_confidence": float(merged["learned_confidence"].mean()),
                "avg_margin_confidence": float(merged["margin_confidence"].mean()),
                "avg_signal_top_gap": float(merged["signal_top_gap"].mean()),
                "avg_top1_share": float(merged["top1_share"].mean()),
                "avg_top2_share": float(merged["top2_share"].mean()),
                "avg_hhi": float(merged["hhi"].mean()),
                "avg_lambda_turn": float(merged["lambda_turn"].mean()),
                "avg_lambda_tail": float(merged["lambda_tail"].mean()),
            }
        ]
    )
    bucket_rows: list[dict[str, float | str | int]] = []
    for bucket, group in merged.groupby("confidence_bucket", observed=False):
        if group.empty:
            continue
        bucket_rows.append(
            {
                "version_name": version_name,
                "confidence_bucket": str(bucket),
                "observations": int(len(group)),
                "avg_learned_confidence": float(group["learned_confidence"].mean()),
                "avg_top1_share": float(group["top1_share"].mean()),
                "avg_top2_share": float(group["top2_share"].mean()),
                "avg_hhi": float(group["hhi"].mean()),
            }
        )
    return overall, pd.DataFrame(bucket_rows)


def main() -> None:
    next_week_returns, active_returns, active_positions, _, market_state_history = ph.load_inputs()
    state_features = ph.state_feature_frame(active_returns.index, market_state_history)
    state_prior = ph.role_alignment_score(state_features)
    long_panel, date_panel, simple_score_panel = ph.build_feature_panels(active_returns, state_features, state_prior)
    long_panel = add_learning_targets(long_panel)
    date_learning_panel = build_date_learning_panel(date_panel, long_panel)

    feature_cols = [
        col
        for col in long_panel.columns
        if col
        not in {
            "Date",
            "sleeve",
            "target_return_4w",
            "decision_utility_raw",
            "tail_utility_raw",
            "decision_utility_target",
            "tail_utility_target",
        }
    ]
    date_feature_cols = [col for col in date_learning_panel.columns if col not in {"Date", "future_spread", "future_utility_spread", "future_utility_top_gap"}]

    decision_model = walkforward_panel_utility_model(long_panel, feature_cols, "decision_utility_target", alpha=3.0)
    tail_model = walkforward_panel_utility_model(long_panel, feature_cols, "tail_utility_target", alpha=4.5)
    spread_model = walkforward_date_utility_model(date_learning_panel, date_feature_cols, "future_utility_spread", alpha=3.0)

    reference_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv").reindex(state_prior.index).fillna(0.0)
    tail_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{TAIL_AWARE_BRANCH}.csv").reindex(state_prior.index).fillna(0.0)
    opportunity, meta = pk.build_margin_meta(state_prior, simple_score_panel, decision_model.prediction_frame, reference_weights, state_features)
    cov_map, down_cov_map, tail_map = pk.risk_maps(active_returns)

    universe_columns = list(next_week_returns.columns)
    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    control_rows: list[pd.DataFrame] = []
    control_bucket_rows: list[pd.DataFrame] = []

    for version_name in PHASE_L_CANDIDATES:
        sleeve_weights, controls = build_candidate_weights(
            version_name,
            decision_model.prediction_frame,
            tail_model.prediction_frame,
            spread_model.prediction_frame,
            state_prior,
            simple_score_panel,
            reference_weights,
            tail_weights,
            meta,
            state_features,
            cov_map,
            down_cov_map,
            tail_map,
        )
        etf_weights = ph.build_lookthrough_weights(sleeve_weights, active_positions, universe_columns)
        path = ph.save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)

        state_rows.append(ph.state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = ph.sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        conc_summary, conc_state = ph.concentration_summary(sleeve_weights, market_state_history, version_name)
        concentration_rows.append(conc_summary)
        concentration_state_rows.append(conc_state)
        ctrl_summary, ctrl_bucket = control_summary(version_name, controls, sleeve_weights)
        control_rows.append(ctrl_summary)
        control_bucket_rows.append(ctrl_bucket)
        controls.to_csv(LAYER3_DIR / f"phase_l_learning_controls_{version_name}.csv")

        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        variant_rows.append(
            {
                "version_name": version_name,
                "ann_return": ann_ret,
                "ann_vol": ann_vol,
                "sharpe": ann_ret / ann_vol if ann_vol > 0 else np.nan,
                "max_drawdown": ph.max_drawdown(path["net_return"]),
                "turnover": float(path["turnover"].mean()),
                "avg_bil": float(etf_weights.get("BIL", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_spy": float(etf_weights.get("SPY", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_role_share_new": float(
                    sleeve_weights[["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]].sum(axis=1).mean()
                ),
            }
        )

    feature_rows: list[dict[str, float | str]] = []
    for model_name, importance in {
        "decision_utility_model": decision_model.feature_importance,
        "tail_utility_model": tail_model.feature_importance,
        "utility_spread_model": spread_model.feature_importance,
    }.items():
        for feature_name, value in importance.head(25).items():
            feature_rows.append({"model_name": model_name, "feature_name": feature_name, "importance": float(value)})

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_l_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_concentration_by_state.csv", index=False)
    pd.concat(control_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_learning_control_summary.csv", index=False)
    pd.concat(control_bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_l_learning_control_by_confidence.csv", index=False)
    pd.DataFrame(feature_rows).to_csv(LAYER3_DIR / "phase_l_feature_importance_summary.csv", index=False)

    protocol = {
        "phase": "Phase L",
        "purpose": "Decision-aware / robustness-aware learning allocator on refined redesigned sleeve panel",
        "current_refined_allocator_reference": CURRENT_REFINED_REFERENCE,
        "conditional_tail_aware_branch": TAIL_AWARE_BRANCH,
        "active_panel_baseline": ACTIVE_PANEL_BASELINE,
        "candidate_versions": PHASE_L_CANDIDATES,
        "training_design": {
            "decision_utility_label": "forward 4w sleeve return penalized for downside, trailing risk, drawdown, and fragile offensive exposure; cross-sectionally ranked by date",
            "tail_utility_label": "more heavily downside/tail-penalized decision utility; cross-sectionally ranked by date",
            "date_spread_label": "future utility winner spread for learned concentration gating",
            "walk_forward": {
                "min_train_weeks": MIN_TRAIN_WEEKS,
                "retrain_frequency_weeks": RETRAIN_FREQUENCY_WEEKS,
                "label_horizon_weeks": HORIZON_WEEKS,
            },
        },
    }
    (LAYER3_DIR / "phase_l_learning_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase L learning allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_l_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_l_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_l_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_l_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_l_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_l_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_l_learning_control_summary.csv",
        "data/05_layer3_portfolio_construction/phase_l_learning_control_by_confidence.csv",
        "data/05_layer3_portfolio_construction/phase_l_feature_importance_summary.csv",
        "data/05_layer3_portfolio_construction/phase_l_learning_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
