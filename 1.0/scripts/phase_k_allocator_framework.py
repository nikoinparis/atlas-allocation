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


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"
REFERENCE_PANEL_VERSION = "improved_phaseh_reference_core_blend"
OLDER_BOUNDED_REFERENCE = "improved_phasec_state_conditioned_map"

PHASE_K_CANDIDATES = {
    "improved_phasek_robust_objective_framework": "F1 objective-based robust allocator framework",
    "improved_phasek_confidence_turnover_framework": "F2 confidence-margin + turnover-aware framework",
    "improved_phasek_tail_aware_role_framework": "F3 tail-aware robust role framework",
}

SELECTION_WINDOW_WEEKS = 156
SELECTION_STEP_WEEKS = 26
RISK_LOOKBACK_WEEKS = 52
MIN_HISTORY_WEEKS = 13
EPS = 1e-9


@dataclass(frozen=True)
class FrameworkConfig:
    name: str
    mu_scale: float
    lambda_var: float
    lambda_down: float
    lambda_tail: float
    lambda_turn: float
    lambda_anchor: float
    lambda_hhi: float
    confidence_power: float
    floor_lift: float
    cap_lift: float


FRAMEWORK_CONFIGS: dict[str, list[FrameworkConfig]] = {
    "improved_phasek_robust_objective_framework": [
        FrameworkConfig("conservative", 0.70, 1.65, 0.95, 0.90, 1.05, 0.95, 0.48, 1.20, 0.05, 0.00),
        FrameworkConfig("balanced", 0.90, 1.20, 0.78, 0.72, 0.82, 0.75, 0.34, 1.00, 0.03, 0.02),
        FrameworkConfig("conviction", 1.10, 0.95, 0.60, 0.58, 0.62, 0.58, 0.22, 0.85, 0.00, 0.05),
    ],
    "improved_phasek_confidence_turnover_framework": [
        FrameworkConfig("margin_strict", 0.88, 1.08, 0.70, 0.64, 1.18, 0.86, 0.34, 1.45, 0.04, 0.00),
        FrameworkConfig("margin_balanced", 1.02, 1.00, 0.62, 0.58, 0.94, 0.74, 0.28, 1.25, 0.02, 0.03),
        FrameworkConfig("margin_fast", 1.18, 0.92, 0.56, 0.50, 0.74, 0.60, 0.20, 1.10, 0.00, 0.06),
    ],
    "improved_phasek_tail_aware_role_framework": [
        FrameworkConfig("tail_guard", 0.82, 1.35, 1.05, 1.10, 0.88, 0.86, 0.38, 1.15, 0.05, -0.02),
        FrameworkConfig("tail_balanced", 0.96, 1.15, 0.86, 0.90, 0.76, 0.72, 0.30, 1.00, 0.03, 0.00),
        FrameworkConfig("tail_flexible", 1.06, 1.00, 0.74, 0.78, 0.68, 0.62, 0.24, 0.95, 0.01, 0.02),
    ],
}


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)
    return clean / total


def shrink_covariance(matrix: pd.DataFrame, diagonal_weight: float) -> pd.DataFrame:
    aligned = matrix.reindex(index=ph.ACTIVE_PANEL, columns=ph.ACTIVE_PANEL).fillna(0.0)
    diag = pd.DataFrame(np.diag(np.diag(aligned.to_numpy())), index=aligned.index, columns=aligned.columns)
    shrunk = (1.0 - diagonal_weight) * aligned + diagonal_weight * diag
    return shrunk.fillna(0.0)


def risk_maps(active_returns: pd.DataFrame) -> tuple[dict[pd.Timestamp, pd.DataFrame], dict[pd.Timestamp, pd.DataFrame], dict[pd.Timestamp, pd.Series]]:
    cov_map: dict[pd.Timestamp, pd.DataFrame] = {}
    down_cov_map: dict[pd.Timestamp, pd.DataFrame] = {}
    tail_map: dict[pd.Timestamp, pd.Series] = {}

    for date in active_returns.index:
        history = active_returns.loc[:date, ph.ACTIVE_PANEL].tail(RISK_LOOKBACK_WEEKS).dropna(how="all")
        if len(history) < MIN_HISTORY_WEEKS:
            cov = pd.DataFrame(np.eye(len(ph.ACTIVE_PANEL)) * 0.0008, index=ph.ACTIVE_PANEL, columns=ph.ACTIVE_PANEL)
            down_cov = cov.copy()
            tail = pd.Series(0.010, index=ph.ACTIVE_PANEL, dtype=float)
        else:
            cov = history.cov().reindex(index=ph.ACTIVE_PANEL, columns=ph.ACTIVE_PANEL).fillna(0.0)
            cov = shrink_covariance(cov, diagonal_weight=0.40)

            downside = history.clip(upper=0.0)
            if float(np.abs(downside.to_numpy()).sum()) <= EPS:
                down_cov = cov.copy()
            else:
                down_cov = downside.cov().reindex(index=ph.ACTIVE_PANEL, columns=ph.ACTIVE_PANEL).fillna(0.0)
                down_cov = shrink_covariance(down_cov, diagonal_weight=0.25)

            tail = pd.Series(index=ph.ACTIVE_PANEL, dtype=float)
            for sleeve in ph.ACTIVE_PANEL:
                sleeve_hist = history[sleeve].dropna()
                if sleeve_hist.empty:
                    tail[sleeve] = 0.010
                    continue
                cutoff = sleeve_hist.quantile(0.20)
                tail_slice = sleeve_hist[sleeve_hist <= cutoff]
                tail[sleeve] = float(abs(tail_slice.mean())) if len(tail_slice) else float(abs(sleeve_hist.mean()))
            tail = tail.replace([np.inf, -np.inf], np.nan).fillna(float(tail.mean()) if tail.notna().any() else 0.010)

        cov_map[date] = cov
        down_cov_map[date] = down_cov
        tail_map[date] = tail
    return cov_map, down_cov_map, tail_map


def build_margin_meta(
    state_prior: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    learned_scores: pd.DataFrame,
    reference_weights: pd.DataFrame,
    state_features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    opportunity, meta = pj.opportunity_frame(state_prior, simple_score_panel, learned_scores, reference_weights, state_features)
    meta["state_confidence"] = state_features[["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].max(axis=1)
    meta["risk_guard"] = state_features[["stress_confidence", "chop_confidence"]].max(axis=1)
    return opportunity, meta.fillna(0.0)


def framework_bounds(framework_name: str, st: pd.Series, margin_conf: float, agreement: float, config: FrameworkConfig) -> tuple[dict[str, float], dict[str, float]]:
    floors, caps = pj.dynamic_bounds(st, margin_conf, agreement)
    floors = dict(floors)
    caps = dict(caps)

    dominant = float(st[["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].max())
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))

    if dominant > 0.60 and risk_guard < 0.40:
        top_role = st[["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].idxmax()
        if top_role == "calm_confidence":
            caps["composite_calm_trend_specialist"] = min(0.46 + config.cap_lift, 0.52)
            caps["taa_10m_sma"] = min(0.40 + 0.5 * config.cap_lift, 0.45)
        elif top_role == "recovery_confidence":
            caps["composite_healthier_recovery_specialist"] = min(0.46 + config.cap_lift, 0.52)
            caps["dual_momentum_topn"] = min(0.30 + 0.3 * config.cap_lift, 0.36)
        elif top_role in {"stress_confidence", "chop_confidence"}:
            caps["composite_regime_conditioned"] = min(0.44 + config.cap_lift, 0.50)
            caps["composite_anti_chop_clarity"] = min(0.42 + config.cap_lift, 0.48)

    if framework_name == "improved_phasek_tail_aware_role_framework":
        floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.10 + 0.08 * risk_guard + config.floor_lift)
        floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.08 + 0.08 * float(st["chop_confidence"]) + config.floor_lift)
        for sleeve in ["dual_momentum_topn", "composite_healthier_recovery_specialist", "composite_calm_trend_specialist"]:
            caps[sleeve] = min(caps.get(sleeve, 1.0), 0.26 if risk_guard > 0.45 else caps.get(sleeve, 1.0))

    if framework_name == "improved_phasek_confidence_turnover_framework" and margin_conf < 0.45:
        for sleeve in ph.ACTIVE_PANEL:
            caps[sleeve] = min(caps.get(sleeve, 1.0), 0.28)

    return floors, caps


def robust_signal(opportunity_row: pd.Series, reference_row: pd.Series, margin_conf: float) -> pd.Series:
    opp_rank = ph.centered_rank(opportunity_row.reindex(ph.ACTIVE_PANEL).fillna(0.0))
    ref_rank = ph.centered_rank(reference_row.reindex(ph.ACTIVE_PANEL).fillna(0.0))
    signal = 0.82 * opp_rank + 0.18 * ref_rank
    shrink = 0.20 + 0.25 * (1.0 - margin_conf)
    signal = (1.0 - shrink) * signal + shrink * ph.centered_rank(pi.SAFE_ANCHOR)
    return signal.fillna(0.0)


def solve_objective(
    signal: pd.Series,
    anchor: pd.Series,
    prev_weights: pd.Series,
    cov: pd.DataFrame,
    down_cov: pd.DataFrame,
    tail_vector: pd.Series,
    role_penalty: pd.Series,
    *,
    mu_scale: float,
    lambda_var: float,
    lambda_down: float,
    lambda_tail: float,
    lambda_turn: float,
    lambda_anchor: float,
    lambda_hhi: float,
    floors: dict[str, float],
    caps: dict[str, float],
) -> pd.Series:
    idx = ph.ACTIVE_PANEL
    cov_matrix = cov.reindex(index=idx, columns=idx).fillna(0.0).to_numpy()
    down_matrix = down_cov.reindex(index=idx, columns=idx).fillna(0.0).to_numpy()
    tail_diag = np.diag(tail_vector.reindex(idx).fillna(tail_vector.mean()).to_numpy())
    role_diag = np.diag(role_penalty.reindex(idx).fillna(role_penalty.mean()).to_numpy())

    q = (
        mu_scale * signal.reindex(idx).fillna(0.0).to_numpy()
        + lambda_turn * prev_weights.reindex(idx).fillna(0.0).to_numpy()
        + lambda_anchor * anchor.reindex(idx).fillna(0.0).to_numpy()
    )
    q = q - lambda_tail * 0.70 * tail_vector.reindex(idx).fillna(tail_vector.mean()).to_numpy()
    q = q - lambda_tail * 0.35 * role_penalty.reindex(idx).fillna(role_penalty.mean()).to_numpy()

    qmat = (
        lambda_var * cov_matrix
        + lambda_down * down_matrix
        + lambda_tail * (0.55 * tail_diag + 0.25 * role_diag)
        + (lambda_turn + lambda_anchor + lambda_hhi) * np.eye(len(idx))
    )
    raw = np.linalg.pinv(qmat + 1e-6 * np.eye(len(idx))) @ q
    raw = pd.Series(raw, index=idx, dtype=float)
    raw = raw - float(raw.min()) + EPS
    return normalize(pi.bounded_normalize(raw, floors=floors, caps=caps))


def config_weights(
    framework_name: str,
    config: FrameworkConfig,
    reference_weights: pd.DataFrame,
    opportunity: pd.DataFrame,
    meta: pd.DataFrame,
    state_features: pd.DataFrame,
    cov_map: dict[pd.Timestamp, pd.DataFrame],
    down_cov_map: dict[pd.Timestamp, pd.DataFrame],
    tail_map: dict[pd.Timestamp, pd.Series],
) -> pd.DataFrame:
    rows: list[pd.Series] = []
    prev_weights: pd.Series | None = None

    for date in reference_weights.index:
        ref = normalize(reference_weights.loc[date, ph.ACTIVE_PANEL])
        prev = ref.copy() if prev_weights is None else prev_weights.copy()
        st = state_features.loc[date]
        margin_conf = float(meta.loc[date, "margin_confidence"])
        agreement = float(meta.loc[date, "agreement"])
        risk_guard = float(meta.loc[date, "risk_guard"])
        signal = robust_signal(opportunity.loc[date, ph.ACTIVE_PANEL], ref, margin_conf)
        floors, caps = framework_bounds(framework_name, st, margin_conf, agreement, config)
        role_penalty = pj.risk_penalty_vector(st)

        confidence_strength = margin_conf ** config.confidence_power
        safe_mix = min(0.08 + 0.18 * risk_guard + 0.08 * (1.0 - confidence_strength), 0.35)
        anchor = normalize((1.0 - safe_mix) * ref + safe_mix * pi.SAFE_ANCHOR)

        if framework_name == "improved_phasek_robust_objective_framework":
            mu_scale = config.mu_scale * (0.35 + 0.70 * confidence_strength)
            lambda_turn = config.lambda_turn * (1.12 - 0.30 * confidence_strength)
            lambda_anchor = config.lambda_anchor * (1.08 - 0.22 * confidence_strength)
            lambda_var = config.lambda_var * (1.00 + 0.20 * risk_guard)
            lambda_down = config.lambda_down * (1.00 + 0.30 * risk_guard)
            lambda_tail = config.lambda_tail * (1.00 + 0.45 * risk_guard)
            lambda_hhi = config.lambda_hhi * (1.0 + 0.15 * (1.0 - confidence_strength))
        elif framework_name == "improved_phasek_confidence_turnover_framework":
            mu_scale = config.mu_scale * (0.18 + 0.95 * confidence_strength)
            lambda_turn = config.lambda_turn * (1.45 - 0.75 * confidence_strength)
            lambda_anchor = config.lambda_anchor * (1.18 - 0.36 * confidence_strength)
            lambda_var = config.lambda_var * (0.92 + 0.25 * risk_guard)
            lambda_down = config.lambda_down * (0.92 + 0.30 * risk_guard)
            lambda_tail = config.lambda_tail * (0.95 + 0.40 * risk_guard)
            lambda_hhi = config.lambda_hhi * (1.18 - 0.40 * confidence_strength)
        elif framework_name == "improved_phasek_tail_aware_role_framework":
            mu_scale = config.mu_scale * (0.25 + 0.75 * confidence_strength)
            lambda_turn = config.lambda_turn * (1.05 - 0.15 * confidence_strength)
            lambda_anchor = config.lambda_anchor * (1.10 - 0.15 * confidence_strength)
            lambda_var = config.lambda_var * (1.05 + 0.30 * risk_guard)
            lambda_down = config.lambda_down * (1.12 + 0.55 * risk_guard)
            lambda_tail = config.lambda_tail * (1.15 + 0.65 * risk_guard)
            lambda_hhi = config.lambda_hhi * (1.10 + 0.15 * risk_guard)
        else:
            raise ValueError(framework_name)

        risky = solve_objective(
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
        prev_weights = risky

    return pd.DataFrame(rows).sort_index().fillna(0.0)


def recovery_capture_local(return_series: pd.Series, benchmark_returns: pd.Series, market_state_history: pd.DataFrame) -> float:
    return pdv.recovery_capture(return_series, benchmark_returns, market_state_history)


def raw_window_score(
    return_series: pd.Series,
    weight_panel: pd.DataFrame,
    turnover_series: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> float:
    if len(return_series.dropna()) < 26:
        return -1e6
    metrics = pd.Series(pdv.summary_metrics(return_series, weight_panel, benchmark_returns, turnover_series), dtype=float)
    metrics["recovery_capture"] = recovery_capture_local(return_series, benchmark_returns, market_state_history)
    base = pdv.raw_metric_composite(metrics)

    rolling_scores: list[float] = []
    if len(return_series) >= 52:
        for start in range(0, len(return_series) - 52 + 1, 52):
            idx = return_series.index[start : start + 52]
            sub_metrics = pd.Series(
                pdv.summary_metrics(
                    return_series.reindex(idx),
                    weight_panel.reindex(idx).fillna(0.0),
                    benchmark_returns.reindex(idx),
                    turnover_series.reindex(idx),
                ),
                dtype=float,
            )
            sub_metrics["recovery_capture"] = recovery_capture_local(
                return_series.reindex(idx),
                benchmark_returns.reindex(idx),
                market_state_history,
            )
            rolling_scores.append(pdv.raw_metric_composite(sub_metrics))

    rolling_mean = float(np.mean(rolling_scores)) if rolling_scores else base
    rolling_std = float(np.std(rolling_scores)) if len(rolling_scores) > 1 else 0.0
    return float(base + 0.15 * rolling_mean - 0.10 * rolling_std)


def align_benchmark(index: pd.Index) -> tuple[pd.Series, pd.DataFrame]:
    benchmark_returns = pdv.read_return_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"]
    benchmark_returns = benchmark_returns.reindex(index).fillna(0.0)
    market_state_history = pd.read_csv(ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv", parse_dates=["Date"])
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index().reindex(index)
    return benchmark_returns, market_state_history


def select_framework_path(
    framework_name: str,
    config_weight_map: dict[str, pd.DataFrame],
    config_etf_map: dict[str, pd.DataFrame],
    config_path_map: dict[str, pd.DataFrame],
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
    meta: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    index = next(iter(config_weight_map.values())).index
    default_name = FRAMEWORK_CONFIGS[framework_name][1].name
    last_selected = default_name
    last_retrain_loc = -SELECTION_STEP_WEEKS
    last_score = np.nan
    selection_rows: list[pd.Series] = []

    for loc, date in enumerate(index):
        if loc >= SELECTION_WINDOW_WEEKS and (loc - last_retrain_loc) >= SELECTION_STEP_WEEKS:
            trailing_index = index[loc - SELECTION_WINDOW_WEEKS : loc]
            candidate_scores: dict[str, float] = {}
            for config_name, path in config_path_map.items():
                candidate_scores[config_name] = raw_window_score(
                    path["net_return"].reindex(trailing_index),
                    config_etf_map[config_name].reindex(trailing_index).fillna(0.0),
                    path["turnover"].reindex(trailing_index),
                    benchmark_returns.reindex(trailing_index),
                    market_state_history,
                )
            last_selected = max(candidate_scores.items(), key=lambda kv: kv[1])[0]
            last_retrain_loc = loc
            last_score = float(candidate_scores[last_selected])

        selection_rows.append(
            pd.Series(
                {
                    "selected_config": last_selected,
                    "selection_score": last_score,
                    "margin_confidence": float(meta.loc[date, "margin_confidence"]),
                    "agreement": float(meta.loc[date, "agreement"]),
                    "score_top_gap": float(meta.loc[date, "score_top_gap"]),
                    "score_top_median_gap": float(meta.loc[date, "score_top_median_gap"]),
                },
                name=date,
            )
        )

    selection = pd.DataFrame(selection_rows).sort_index()
    selected_weights = pd.DataFrame(index=index, columns=ph.ACTIVE_PANEL + [ph.CASH_COLUMN], dtype=float)
    selected_etf = pd.DataFrame(index=index, columns=next(iter(config_etf_map.values())).columns, dtype=float)
    for date, row in selection.iterrows():
        cfg = str(row["selected_config"])
        selected_weights.loc[date] = config_weight_map[cfg].loc[date]
        selected_etf.loc[date] = config_etf_map[cfg].loc[date]
    return selected_weights.fillna(0.0), selected_etf.fillna(0.0), selection


def selection_summary(version_name: str, selection: pd.DataFrame, market_state_history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall = (
        selection["selected_config"]
        .value_counts(normalize=False)
        .rename_axis("selected_config")
        .reset_index(name="observations")
    )
    overall["selection_share"] = overall["observations"] / float(len(selection))
    overall["version_name"] = version_name
    overall["avg_selection_score"] = overall["selected_config"].map(
        selection.groupby("selected_config")["selection_score"].mean()
    )

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


def margin_usage_summary(version_name: str, sleeve_weights: pd.DataFrame, selection: pd.DataFrame) -> pd.DataFrame:
    risky = sleeve_weights[ph.ACTIVE_PANEL]
    buckets = pd.cut(selection["margin_confidence"], bins=[-1e-9, 0.33, 0.66, 1.0], labels=["low", "medium", "high"])
    rows: list[dict[str, float | str | int]] = []
    for bucket, idx in buckets.groupby(buckets, observed=False).groups.items():
        sub = risky.loc[idx]
        risky_norm = sub.div(sub.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
        rows.append(
            {
                "version_name": version_name,
                "margin_bucket": str(bucket),
                "observations": int(len(sub)),
                "avg_top1_share": float(risky_norm.max(axis=1).mean()),
                "avg_top2_share": float(np.sort(risky_norm.to_numpy(), axis=1)[:, -2:].sum(axis=1).mean()),
                "avg_hhi": float(risky_norm.pow(2).sum(axis=1).mean()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    next_week_returns, active_returns, active_positions, _, market_state_history = ph.load_inputs()
    state_features = ph.state_feature_frame(active_returns.index, market_state_history)
    state_prior = ph.role_alignment_score(state_features)
    long_panel, _, simple_score_panel = ph.build_feature_panels(active_returns, state_features, state_prior)

    panel_feature_cols = [col for col in long_panel.columns if col not in {"Date", "sleeve", "target_return_4w"}]
    learned_model = ph.walkforward_panel_regressor(long_panel, panel_feature_cols)
    learned_scores = learned_model.prediction_frame.reindex(state_prior.index).fillna(0.0)

    reference_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv")
    reference_weights = reference_weights.reindex(state_prior.index).fillna(0.0)

    opportunity, meta = build_margin_meta(state_prior, simple_score_panel, learned_scores, reference_weights, state_features)
    cov_map, down_cov_map, tail_map = risk_maps(active_returns)

    universe_columns = list(next_week_returns.columns)
    benchmark_returns, benchmark_state_history = align_benchmark(state_prior.index)

    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    selection_rows: list[pd.DataFrame] = []
    selection_state_rows: list[pd.DataFrame] = []
    margin_rows: list[pd.DataFrame] = []

    for version_name in PHASE_K_CANDIDATES:
        config_weight_map: dict[str, pd.DataFrame] = {}
        config_etf_map: dict[str, pd.DataFrame] = {}
        config_path_map: dict[str, pd.DataFrame] = {}

        for config in FRAMEWORK_CONFIGS[version_name]:
            sleeve_weights = config_weights(
                version_name,
                config,
                reference_weights,
                opportunity,
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

        sleeve_weights, etf_weights, selection = select_framework_path(
            version_name,
            config_weight_map,
            config_etf_map,
            config_path_map,
            benchmark_returns,
            benchmark_state_history,
            meta,
        )

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
        margin_rows.append(margin_usage_summary(version_name, sleeve_weights, selection))
        selection.to_csv(LAYER3_DIR / f"phase_k_selection_path_{version_name}.csv")

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

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_k_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_concentration_by_state.csv", index=False)
    pd.concat(selection_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_framework_selection_summary.csv", index=False)
    pd.concat(selection_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_framework_selection_by_state.csv", index=False)
    pd.concat(margin_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_k_margin_usage_summary.csv", index=False)

    protocol = {
        "phase": "Phase K",
        "purpose": "Robustness-aware allocator framework on refined redesigned sleeve panel",
        "current_refined_allocator_reference": CURRENT_REFINED_REFERENCE,
        "active_panel_baseline": ACTIVE_PANEL_BASELINE,
        "older_bounded_reference": OLDER_BOUNDED_REFERENCE,
        "candidate_versions": PHASE_K_CANDIDATES,
        "selection_window_weeks": SELECTION_WINDOW_WEEKS,
        "selection_step_weeks": SELECTION_STEP_WEEKS,
        "frameworks": {
            version_name: [config.__dict__ for config in configs]
            for version_name, configs in FRAMEWORK_CONFIGS.items()
        },
        "design_principles": [
            "objective-based role-aware allocation",
            "explicit turnover penalty inside objective",
            "explicit downside and tail penalties inside objective",
            "walk-forward selection of robust configurations using trailing history only",
        ],
    }
    (LAYER3_DIR / "phase_k_framework_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase K allocator framework artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_k_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_k_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_k_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_k_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_k_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_k_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_k_framework_selection_summary.csv",
        "data/05_layer3_portfolio_construction/phase_k_framework_selection_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_k_margin_usage_summary.csv",
        "data/05_layer3_portfolio_construction/phase_k_framework_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
