from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import phase_d_validate as pdv
import phase_h_refined_panel_allocator as ph
import phase_i_refined_allocator_refinement as pi
import phase_j_structural_allocator as pj
import phase_k_allocator_framework as pk
import phase_l_learning_allocator as pl


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
TAIL_AWARE_BRANCH = "improved_phasel_tail_turnover_learning_allocator"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"
PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"

PHASE_M_CANDIDATES = {
    "improved_phasem_validation_first_learning_allocator": "F1 validation-first learning objective allocator",
    "improved_phasem_production_proximity_allocator": "F2 production-proximity allocator",
}

SELECTION_WINDOW_WEEKS = 156
PSEUDO_HOLDOUT_WEEKS = 52
SELECTION_STEP_WEEKS = 26
ROLLING_PROXY_WEEKS = 52
EPS = 1e-9


@dataclass(frozen=True)
class LearningConfig:
    name: str
    decision_weight: float
    tail_weight: float
    simple_weight: float
    prior_weight: float
    ref_weight: float
    tail_ref_weight: float
    mu_scale: float
    lambda_var: float
    lambda_down: float
    lambda_tail: float
    lambda_turn: float
    lambda_anchor: float
    lambda_hhi: float
    confidence_scale: float


CONFIGS: dict[str, list[LearningConfig]] = {
    "improved_phasem_validation_first_learning_allocator": [
        LearningConfig("vf_stable", 0.46, 0.22, 0.12, 0.08, 0.08, 0.04, 0.86, 1.12, 0.92, 0.92, 0.95, 0.82, 0.28, 0.78),
        LearningConfig("vf_balanced", 0.52, 0.20, 0.12, 0.06, 0.06, 0.04, 0.94, 1.02, 0.78, 0.78, 0.86, 0.74, 0.24, 0.92),
        LearningConfig("vf_retentive", 0.58, 0.16, 0.12, 0.06, 0.05, 0.03, 1.00, 0.96, 0.68, 0.66, 0.78, 0.64, 0.20, 1.04),
    ],
    "improved_phasem_production_proximity_allocator": [
        LearningConfig("pp_close", 0.42, 0.28, 0.10, 0.07, 0.06, 0.07, 0.82, 1.18, 1.02, 1.05, 1.02, 0.90, 0.30, 0.72),
        LearningConfig("pp_holdout", 0.48, 0.24, 0.10, 0.06, 0.06, 0.06, 0.88, 1.10, 0.90, 0.92, 0.94, 0.82, 0.26, 0.82),
        LearningConfig("pp_upside", 0.54, 0.20, 0.12, 0.05, 0.05, 0.04, 0.96, 1.00, 0.78, 0.78, 0.84, 0.72, 0.22, 0.92),
    ],
}


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)
    return clean / total


def build_signal(
    config: LearningConfig,
    date: pd.Timestamp,
    decision_scores: pd.DataFrame,
    tail_scores: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    state_prior: pd.DataFrame,
    ref_weights: pd.DataFrame,
    tail_ref_weights: pd.DataFrame,
) -> pd.Series:
    pieces = []
    if config.decision_weight:
        pieces.append(config.decision_weight * ph.centered_rank(decision_scores.loc[date, ph.ACTIVE_PANEL]))
    if config.tail_weight:
        pieces.append(config.tail_weight * ph.centered_rank(tail_scores.loc[date, ph.ACTIVE_PANEL]))
    if config.simple_weight:
        pieces.append(config.simple_weight * ph.centered_rank(simple_score_panel.loc[date, ph.ACTIVE_PANEL]))
    if config.prior_weight:
        pieces.append(config.prior_weight * ph.centered_rank(state_prior.loc[date, ph.ACTIVE_PANEL]))
    if config.ref_weight:
        pieces.append(config.ref_weight * ph.centered_rank(ref_weights.loc[date, ph.ACTIVE_PANEL]))
    if config.tail_ref_weight:
        pieces.append(config.tail_ref_weight * ph.centered_rank(tail_ref_weights.loc[date, ph.ACTIVE_PANEL]))
    total = sum(pieces)
    return total.fillna(0.0)


def learned_confidence(
    signal: pd.Series,
    meta: pd.DataFrame,
    spread_pred: pd.DataFrame,
    date: pd.Timestamp,
    config: LearningConfig,
) -> float:
    signal_gap = pj.top_margin(signal)
    margin = float(meta.loc[date, "margin_confidence"])
    agreement = float(meta.loc[date, "agreement"])
    pred_spread = float(spread_pred.reindex([date]).fillna(0.0).iloc[0].get("predicted_utility_spread", 0.0))
    pred_score = float(np.clip((pred_spread - 0.004) / 0.040, 0.0, 1.0))
    base = 0.35 * ph.bounded_zero_to_one(signal_gap, 0.04, 0.80) + 0.30 * margin + 0.20 * pred_score + 0.15 * agreement
    return float(np.clip(base * config.confidence_scale, 0.0, 1.0))


def candidate_bounds(candidate_name: str, st: pd.Series, confidence: float, margin_conf: float, agreement: float) -> tuple[dict[str, float], dict[str, float]]:
    floors, caps = pj.dynamic_bounds(st, margin_conf, agreement)
    floors = dict(floors)
    caps = dict(caps)
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))

    if candidate_name == "improved_phasem_validation_first_learning_allocator":
        if confidence < 0.45:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(caps.get(sleeve, 1.0), 0.26)
        elif confidence > 0.70 and risk_guard < 0.35:
            if st["calm_confidence"] == max(st["calm_confidence"], st["recovery_confidence"], st["stress_confidence"], st["chop_confidence"]):
                caps["composite_calm_trend_specialist"] = min(0.44, max(caps.get("composite_calm_trend_specialist", 0.36), 0.42))
                caps["taa_10m_sma"] = min(0.42, max(caps.get("taa_10m_sma", 0.36), 0.38))
            if st["recovery_confidence"] == max(st["calm_confidence"], st["recovery_confidence"], st["stress_confidence"], st["chop_confidence"]):
                caps["composite_healthier_recovery_specialist"] = min(0.44, max(caps.get("composite_healthier_recovery_specialist", 0.36), 0.42))

    if candidate_name == "improved_phasem_production_proximity_allocator":
        floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.08 + 0.08 * risk_guard)
        floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.07 + 0.06 * float(st["chop_confidence"]))
        if risk_guard > 0.40:
            caps["dual_momentum_topn"] = min(caps.get("dual_momentum_topn", 1.0), 0.12)
            caps["composite_calm_trend_specialist"] = min(caps.get("composite_calm_trend_specialist", 1.0), 0.24)
            caps["composite_healthier_recovery_specialist"] = min(caps.get("composite_healthier_recovery_specialist", 1.0), 0.22)
        if confidence < 0.45:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(caps.get(sleeve, 1.0), 0.24)

    return floors, caps


def build_config_weights(
    candidate_name: str,
    config: LearningConfig,
    decision_scores: pd.DataFrame,
    tail_scores: pd.DataFrame,
    spread_pred: pd.DataFrame,
    state_prior: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    ref_weights: pd.DataFrame,
    tail_ref_weights: pd.DataFrame,
    meta: pd.DataFrame,
    state_features: pd.DataFrame,
    cov_map: dict[pd.Timestamp, pd.DataFrame],
    down_cov_map: dict[pd.Timestamp, pd.DataFrame],
    tail_map: dict[pd.Timestamp, pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.Series] = []
    control_rows: list[pd.Series] = []
    prev_weights: pd.Series | None = None

    for date in ref_weights.index:
        ref = normalize(ref_weights.loc[date, ph.ACTIVE_PANEL])
        tail_ref = normalize(tail_ref_weights.loc[date, ph.ACTIVE_PANEL])
        prev = ref.copy() if prev_weights is None else prev_weights.copy()
        st = state_features.loc[date]
        margin_conf = float(meta.loc[date, "margin_confidence"])
        agreement = float(meta.loc[date, "agreement"])
        risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))
        signal = build_signal(config, date, decision_scores, tail_scores, simple_score_panel, state_prior, ref_weights, tail_ref_weights)
        confidence = learned_confidence(signal, meta, spread_pred, date, config)
        floors, caps = candidate_bounds(candidate_name, st, confidence, margin_conf, agreement)
        role_penalty = pj.risk_penalty_vector(st)

        safe_mix = min(0.07 + 0.18 * risk_guard + 0.10 * (1.0 - confidence), 0.34)
        anchor = normalize((1.0 - safe_mix) * (0.74 * ref + 0.26 * tail_ref) + safe_mix * pi.SAFE_ANCHOR)

        mu_scale = config.mu_scale * (0.24 + 0.96 * confidence)
        lambda_var = config.lambda_var * (1.0 + 0.18 * risk_guard)
        lambda_down = config.lambda_down * (1.0 + 0.32 * risk_guard)
        lambda_tail = config.lambda_tail * (1.0 + 0.48 * risk_guard)
        lambda_turn = config.lambda_turn * (1.18 - 0.42 * confidence + 0.10 * risk_guard)
        lambda_anchor = config.lambda_anchor * (1.08 - 0.20 * confidence)
        lambda_hhi = config.lambda_hhi * (1.12 - 0.38 * confidence + 0.12 * risk_guard)

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
                    "config_name": config.name,
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


def align_benchmark(index: pd.Index) -> tuple[pd.Series, pd.DataFrame]:
    benchmark_returns = pdv.read_return_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"]
    benchmark_returns = benchmark_returns.reindex(index).fillna(0.0)
    market_state_history = pd.read_csv(ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv", parse_dates=["Date"])
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index().reindex(index)
    return benchmark_returns, market_state_history


def metric_series(
    return_series: pd.Series,
    weight_panel: pd.DataFrame,
    turnover_series: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> pd.Series:
    metrics = pd.Series(pdv.summary_metrics(return_series, weight_panel, benchmark_returns, turnover_series), dtype=float)
    metrics["recovery_capture"] = pdv.recovery_capture(return_series, benchmark_returns, market_state_history)
    metrics["raw_target_composite"] = pdv.raw_metric_composite(metrics)
    return metrics


def rolling_proxy_delta(
    candidate_returns: pd.Series,
    candidate_weights: pd.DataFrame,
    candidate_turnover: pd.Series,
    production_returns: pd.Series,
    production_weights: pd.DataFrame,
    production_turnover: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> tuple[float, float]:
    if len(candidate_returns) < ROLLING_PROXY_WEEKS:
        return 0.0, 0.0
    diffs: list[float] = []
    for start in range(0, len(candidate_returns) - ROLLING_PROXY_WEEKS + 1, 26):
        idx = candidate_returns.index[start : start + ROLLING_PROXY_WEEKS]
        cand = metric_series(
            candidate_returns.reindex(idx),
            candidate_weights.reindex(idx).fillna(0.0),
            candidate_turnover.reindex(idx),
            benchmark_returns.reindex(idx),
            market_state_history,
        )
        prod = metric_series(
            production_returns.reindex(idx),
            production_weights.reindex(idx).fillna(0.0),
            production_turnover.reindex(idx),
            benchmark_returns.reindex(idx),
            market_state_history,
        )
        diffs.append(float(cand["raw_target_composite"] - prod["raw_target_composite"]))
    if not diffs:
        return 0.0, 0.0
    diffs_s = pd.Series(diffs, dtype=float)
    return float((diffs_s > 0.0).mean()), float(diffs_s.mean())


def validation_first_score(
    cand_returns: pd.Series,
    cand_weights: pd.DataFrame,
    cand_turnover: pd.Series,
    prod_returns: pd.Series,
    prod_weights: pd.DataFrame,
    prod_turnover: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> float:
    full_metrics = metric_series(cand_returns, cand_weights, cand_turnover, benchmark_returns, market_state_history)
    prod_full = metric_series(prod_returns, prod_weights, prod_turnover, benchmark_returns, market_state_history)

    dev_idx = cand_returns.index[:-PSEUDO_HOLDOUT_WEEKS]
    hold_idx = cand_returns.index[-PSEUDO_HOLDOUT_WEEKS:]
    hold_metrics = metric_series(
        cand_returns.reindex(hold_idx),
        cand_weights.reindex(hold_idx).fillna(0.0),
        cand_turnover.reindex(hold_idx),
        benchmark_returns.reindex(hold_idx),
        market_state_history,
    )
    prod_hold = metric_series(
        prod_returns.reindex(hold_idx),
        prod_weights.reindex(hold_idx).fillna(0.0),
        prod_turnover.reindex(hold_idx),
        benchmark_returns.reindex(hold_idx),
        market_state_history,
    )
    rolling_win, rolling_mean = rolling_proxy_delta(
        cand_returns,
        cand_weights,
        cand_turnover,
        prod_returns,
        prod_weights,
        prod_turnover,
        benchmark_returns,
        market_state_history,
    )

    score = (
        0.25 * float(full_metrics["raw_target_composite"])
        + 0.45 * float(hold_metrics["raw_target_composite"])
        + 0.25 * rolling_mean
        + 0.10 * rolling_win
    )

    penalties = 0.0
    penalties += 2.8 * max(0.0, -float(hold_metrics["raw_target_composite"] - prod_hold["raw_target_composite"]))
    penalties += 1.8 * max(0.0, -0.02 - float(hold_metrics["sharpe"] - prod_hold["sharpe"]))
    penalties += 1.6 * max(0.0, 0.55 - rolling_win)
    penalties += 1.6 * max(0.0, -rolling_mean)
    penalties += 1.4 * max(0.0, 0.10 - (0.105 - float(full_metrics["turnover"])))
    penalties += 2.8 * max(0.0, -0.01 - float(full_metrics["max_drawdown"] - prod_full["max_drawdown"]))
    penalties += 3.2 * max(0.0, -0.002 - float(full_metrics["cvar_5"] - prod_full["cvar_5"]))
    return float(score - penalties)


def production_proximity_score(
    cand_returns: pd.Series,
    cand_weights: pd.DataFrame,
    cand_turnover: pd.Series,
    prod_returns: pd.Series,
    prod_weights: pd.DataFrame,
    prod_turnover: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> float:
    full_metrics = metric_series(cand_returns, cand_weights, cand_turnover, benchmark_returns, market_state_history)
    prod_full = metric_series(prod_returns, prod_weights, prod_turnover, benchmark_returns, market_state_history)
    hold_idx = cand_returns.index[-PSEUDO_HOLDOUT_WEEKS:]
    hold_metrics = metric_series(
        cand_returns.reindex(hold_idx),
        cand_weights.reindex(hold_idx).fillna(0.0),
        cand_turnover.reindex(hold_idx),
        benchmark_returns.reindex(hold_idx),
        market_state_history,
    )
    prod_hold = metric_series(
        prod_returns.reindex(hold_idx),
        prod_weights.reindex(hold_idx).fillna(0.0),
        prod_turnover.reindex(hold_idx),
        benchmark_returns.reindex(hold_idx),
        market_state_history,
    )
    rolling_win, rolling_mean = rolling_proxy_delta(
        cand_returns,
        cand_weights,
        cand_turnover,
        prod_returns,
        prod_weights,
        prod_turnover,
        benchmark_returns,
        market_state_history,
    )

    shortfalls = 0.0
    shortfalls += max(0.0, 0.015 - float(full_metrics["raw_target_composite"] - prod_full["raw_target_composite"]))
    shortfalls += max(0.0, 0.0 - float(hold_metrics["raw_target_composite"] - prod_hold["raw_target_composite"]))
    shortfalls += max(0.0, -0.02 - float(hold_metrics["sharpe"] - prod_hold["sharpe"]))
    shortfalls += max(0.0, 0.55 - rolling_win)
    shortfalls += max(0.0, 0.0 - rolling_mean)
    shortfalls += max(0.0, -0.01 - float(full_metrics["max_drawdown"] - prod_full["max_drawdown"]))
    shortfalls += max(0.0, -0.002 - float(full_metrics["cvar_5"] - prod_full["cvar_5"]))
    shortfalls += max(0.0, float(full_metrics["turnover"]) - 0.095)

    upside_bonus = 0.45 * float(full_metrics["raw_target_composite"]) + 0.30 * float(hold_metrics["raw_target_composite"])
    return float(upside_bonus - 2.6 * shortfalls)


def select_final_path(
    candidate_name: str,
    config_weight_map: dict[str, pd.DataFrame],
    config_etf_map: dict[str, pd.DataFrame],
    config_path_map: dict[str, pd.DataFrame],
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
    production_path: pd.DataFrame,
    production_weights: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    index = next(iter(config_weight_map.values())).index
    default_name = CONFIGS[candidate_name][1].name
    last_selected = default_name
    last_score = np.nan
    last_retrain_loc = -SELECTION_STEP_WEEKS
    selection_rows: list[pd.Series] = []

    scorer = validation_first_score if candidate_name == "improved_phasem_validation_first_learning_allocator" else production_proximity_score

    for loc, date in enumerate(index):
        if loc >= SELECTION_WINDOW_WEEKS and (loc - last_retrain_loc) >= SELECTION_STEP_WEEKS:
            trailing_index = index[loc - SELECTION_WINDOW_WEEKS : loc]
            candidate_scores: dict[str, float] = {}
            for config_name, path in config_path_map.items():
                candidate_scores[config_name] = scorer(
                    path["net_return"].reindex(trailing_index),
                    config_etf_map[config_name].reindex(trailing_index).fillna(0.0),
                    path["turnover"].reindex(trailing_index),
                    production_path["net_return"].reindex(trailing_index),
                    production_weights.reindex(trailing_index).fillna(0.0),
                    production_path["turnover"].reindex(trailing_index),
                    benchmark_returns.reindex(trailing_index),
                    market_state_history,
                )
            last_selected = max(candidate_scores.items(), key=lambda kv: kv[1])[0]
            last_score = float(candidate_scores[last_selected])
            last_retrain_loc = loc

        selection_rows.append(pd.Series({"selected_config": last_selected, "selection_score": last_score}, name=date))

    selection = pd.DataFrame(selection_rows).sort_index()
    selected_weights = pd.DataFrame(index=index, columns=ph.ACTIVE_PANEL + [ph.CASH_COLUMN], dtype=float)
    selected_etf = pd.DataFrame(index=index, columns=next(iter(config_etf_map.values())).columns, dtype=float)
    for date, row in selection.iterrows():
        cfg = str(row["selected_config"])
        selected_weights.loc[date] = config_weight_map[cfg].loc[date]
        selected_etf.loc[date] = config_etf_map[cfg].loc[date]
    return selected_weights.fillna(0.0), selected_etf.fillna(0.0), selection


def selection_summary(version_name: str, selection: pd.DataFrame, market_state_history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall = selection["selected_config"].value_counts().rename_axis("selected_config").reset_index(name="observations")
    overall["selection_share"] = overall["observations"] / float(len(selection))
    overall["version_name"] = version_name
    overall["avg_selection_score"] = overall["selected_config"].map(selection.groupby("selected_config")["selection_score"].mean())

    joined = selection.join(market_state_history["market_state"], how="left")
    rows: list[dict[str, float | str]] = []
    for (cfg, state), group in joined.groupby(["selected_config", "market_state"], observed=False):
        rows.append(
            {
                "version_name": version_name,
                "selected_config": str(cfg),
                "market_state": str(state),
                "observations": int(len(group)),
                "selection_share_state": float(len(group) / max(1, (joined["market_state"] == state).sum())),
            }
        )
    return overall, pd.DataFrame(rows)


def confidence_summary(version_name: str, controls: pd.DataFrame, sleeve_weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    long_panel = pl.add_learning_targets(long_panel)
    date_learning_panel = pl.build_date_learning_panel(date_panel, long_panel)

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

    decision_model = pl.walkforward_panel_utility_model(long_panel, feature_cols, "decision_utility_target", alpha=2.8)
    tail_model = pl.walkforward_panel_utility_model(long_panel, feature_cols, "tail_utility_target", alpha=4.0)
    spread_model = pl.walkforward_date_utility_model(date_learning_panel, date_feature_cols, "future_utility_spread", alpha=2.8)

    ref_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv").reindex(state_prior.index).fillna(0.0)
    tail_ref_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{TAIL_AWARE_BRANCH}.csv").reindex(state_prior.index).fillna(0.0)
    production_path = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_returns_{PRODUCTION_PIN}.csv")
    production_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_weights_{PRODUCTION_PIN}.csv").reindex(state_prior.index).fillna(0.0)
    benchmark_returns, benchmark_state_history = align_benchmark(state_prior.index)
    opportunity, meta = pk.build_margin_meta(state_prior, simple_score_panel, decision_model.prediction_frame, ref_weights, state_features)
    cov_map, down_cov_map, tail_map = pk.risk_maps(active_returns)

    universe_columns = list(next_week_returns.columns)
    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    selection_rows: list[pd.DataFrame] = []
    selection_state_rows: list[pd.DataFrame] = []
    control_rows: list[pd.DataFrame] = []
    control_bucket_rows: list[pd.DataFrame] = []
    feature_rows: list[dict[str, float | str]] = []

    for model_name, importance in {
        "decision_utility_model": decision_model.feature_importance,
        "tail_utility_model": tail_model.feature_importance,
        "utility_spread_model": spread_model.feature_importance,
    }.items():
        for feature_name, value in importance.head(25).items():
            feature_rows.append({"model_name": model_name, "feature_name": feature_name, "importance": float(value)})

    for version_name in PHASE_M_CANDIDATES:
        config_weight_map: dict[str, pd.DataFrame] = {}
        config_etf_map: dict[str, pd.DataFrame] = {}
        config_path_map: dict[str, pd.DataFrame] = {}
        config_control_map: dict[str, pd.DataFrame] = {}

        for config in CONFIGS[version_name]:
            sleeve_weights, controls = build_config_weights(
                version_name,
                config,
                decision_model.prediction_frame,
                tail_model.prediction_frame,
                spread_model.prediction_frame,
                state_prior,
                simple_score_panel,
                ref_weights,
                tail_ref_weights,
                meta,
                state_features,
                cov_map,
                down_cov_map,
                tail_map,
            )
            etf_weights = ph.build_lookthrough_weights(sleeve_weights, active_positions, universe_columns)
            path = ph.pf.compute_portfolio_path(
                etf_weights,
                next_week_returns.reindex(index=etf_weights.index, columns=etf_weights.columns).fillna(0.0),
            )
            config_weight_map[config.name] = sleeve_weights
            config_etf_map[config.name] = etf_weights
            config_path_map[config.name] = path
            config_control_map[config.name] = controls

        sleeve_weights, etf_weights, selection = select_final_path(
            version_name,
            config_weight_map,
            config_etf_map,
            config_path_map,
            benchmark_returns,
            benchmark_state_history,
            production_path.reindex(state_prior.index).fillna(0.0),
            production_weights,
        )
        selected_controls = pd.DataFrame(index=selection.index)
        for date, row in selection.iterrows():
            cfg = str(row["selected_config"])
            selected_controls.loc[date, config_control_map[cfg].columns] = config_control_map[cfg].loc[date]
        selected_controls["selection_score"] = selection["selection_score"]
        selected_controls["selected_config"] = selection["selected_config"]

        path = ph.save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)
        state_rows.append(ph.state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = ph.sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        conc_summary, conc_state = ph.concentration_summary(sleeve_weights, market_state_history, version_name)
        concentration_rows.append(conc_summary)
        concentration_state_rows.append(conc_state)
        sel_summary, sel_state = selection_summary(version_name, selection, market_state_history)
        selection_rows.append(sel_summary)
        selection_state_rows.append(sel_state)
        ctrl_summary, ctrl_bucket = confidence_summary(version_name, selected_controls, sleeve_weights)
        control_rows.append(ctrl_summary)
        control_bucket_rows.append(ctrl_bucket)
        selection.to_csv(LAYER3_DIR / f"phase_m_selection_path_{version_name}.csv")
        selected_controls.to_csv(LAYER3_DIR / f"phase_m_controls_{version_name}.csv")

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

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_m_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_concentration_by_state.csv", index=False)
    pd.concat(selection_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_selection_summary.csv", index=False)
    pd.concat(selection_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_selection_by_state.csv", index=False)
    pd.concat(control_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_control_summary.csv", index=False)
    pd.concat(control_bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_m_control_by_confidence.csv", index=False)
    pd.DataFrame(feature_rows).to_csv(LAYER3_DIR / "phase_m_feature_importance_summary.csv", index=False)

    protocol = {
        "phase": "Phase M",
        "purpose": "Final allocator-category sprint on refined redesigned panel",
        "current_refined_allocator_reference": CURRENT_REFINED_REFERENCE,
        "current_learning_branch": TAIL_AWARE_BRANCH,
        "active_panel_baseline": ACTIVE_PANEL_BASELINE,
        "candidate_versions": PHASE_M_CANDIDATES,
        "selection_window_weeks": SELECTION_WINDOW_WEEKS,
        "pseudo_holdout_weeks": PSEUDO_HOLDOUT_WEEKS,
        "selection_step_weeks": SELECTION_STEP_WEEKS,
        "config_sets": {
            version_name: [config.__dict__ for config in configs]
            for version_name, configs in CONFIGS.items()
        },
        "design_principles": [
            "validation-first config selection using trailing pseudo-holdout and rolling proxy quality",
            "production-proximity scoring against Phase D-like acceptance shape",
            "role-aware learning signals from decision and tail utility models",
            "no broad sleeve search or model zoo expansion",
        ],
    }
    (LAYER3_DIR / "phase_m_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase M allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_m_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_m_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_m_selection_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_selection_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_m_control_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_control_by_confidence.csv",
        "data/05_layer3_portfolio_construction/phase_m_feature_importance_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
