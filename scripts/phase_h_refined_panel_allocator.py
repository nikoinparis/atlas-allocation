from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import phase_f_sleeve_separability as pf


ROOT = Path(__file__).resolve().parents[1]
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

REFERENCE_PANEL = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

ACTIVE_PANEL = [
    "dual_momentum_topn",
    "composite_calm_trend_specialist",
    "composite_healthier_recovery_specialist",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

CASH_COLUMN = "cash::BIL"
CASH_PROXY = "BIL"
DEFAULT_COST_BPS = 10
HORIZON_WEEKS = 4
MIN_TRAIN_WEEKS = 156
RETRAIN_FREQUENCY_WEEKS = 26

BASELINE_VERSIONS = {
    "improved_phaseh_reference_core_blend": "Reference panel equal blend",
    "improved_phaseh_refined_panel_blend": "Active refined panel equal blend",
}

PHASE_H_CANDIDATES = {
    "improved_phaseh_refined_state_allocator": "A1 bounded state-conditioned allocator",
    "improved_phaseh_refined_learned_allocator": "A2 learned sleeve-quality allocator",
    "improved_phaseh_refined_concentration_allocator": "A3 conditional concentration allocator",
    "improved_phaseh_refined_combo_allocator": "A4 disciplined combo allocator",
}

ROLE_MAP = {
    "dual_momentum_topn": {"calm": 0.30, "recovery": 0.55, "chop": 0.10, "defense": 0.00},
    "composite_calm_trend_specialist": {"calm": 1.00, "recovery": 0.10, "chop": 0.10, "defense": 0.25},
    "composite_healthier_recovery_specialist": {"calm": 0.25, "recovery": 1.00, "chop": 0.00, "defense": 0.10},
    "composite_anti_chop_clarity": {"calm": 0.20, "recovery": 0.00, "chop": 1.00, "defense": 0.65},
    "composite_regime_conditioned": {"calm": 0.00, "recovery": 0.15, "chop": 0.60, "defense": 1.00},
    "taa_10m_sma": {"calm": 0.70, "recovery": 0.35, "chop": 0.20, "defense": 0.20},
}

MARKET_FEATURE_COLUMNS = [
    "market_trend_positive",
    "breadth_sma_43",
    "breadth_13w_mom",
    "breadth_26w_mom",
    "breadth_change_4w",
    "canary_breadth_pair",
    "recent_stress_26w",
    "avg_corr_risk_off_z",
    "google_fear_z_tradable",
    "transition_persistence_prob",
    "transition_good_state_prob",
    "transition_non_stress_prob",
    "market_drawdown",
    "risk_regime_score",
]


@dataclass
class ModelPredictionResult:
    prediction_frame: pd.DataFrame
    feature_importance: pd.Series


def read_panel_csv(path: Path, *, value_col: str | None = None) -> pd.DataFrame | pd.Series:
    frame = pd.read_csv(path)
    if "Date" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    frame = frame.set_index("Date").sort_index()
    if value_col is None:
        return frame
    return frame[value_col]


def annualized_return(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if series.empty:
        return np.nan
    return float((1.0 + series).prod() ** (52 / len(series)) - 1.0)


def annualized_vol(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if len(series) < 2:
        return np.nan
    return float(series.std(ddof=1) * np.sqrt(52))


def max_drawdown(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if series.empty:
        return np.nan
    wealth = (1.0 + series).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def rolling_drawdown(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    return series.rolling(window, min_periods=min_periods).apply(
        lambda x: (np.cumprod(1.0 + x) / np.maximum.accumulate(np.cumprod(1.0 + x)) - 1.0).min(),
        raw=True,
    )


def trailing_compound(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    return (1.0 + series).rolling(window, min_periods=min_periods).apply(np.prod, raw=True) - 1.0


def center_and_scale(series: pd.Series) -> pd.Series:
    clean = pd.Series(series, dtype=float)
    if clean.dropna().empty:
        return pd.Series(0.0, index=clean.index, dtype=float)
    centered = clean - clean.mean()
    scale = centered.std(ddof=0)
    if pd.isna(scale) or scale <= 1e-9:
        return pd.Series(0.0, index=clean.index, dtype=float)
    return centered.div(scale).replace([np.inf, -np.inf], 0.0).fillna(0.0)


def centered_rank(series: pd.Series) -> pd.Series:
    clean = pd.Series(series, dtype=float)
    if clean.dropna().empty:
        return pd.Series(0.0, index=clean.index, dtype=float)
    return ((clean.rank(pct=True, method="average") - 0.5) * 2.0).fillna(0.0)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame]:
    weekly_log_returns = read_panel_csv(DATA_HUB_DIR / "weekly_returns.csv")
    weekly_simple_returns = np.expm1(weekly_log_returns)
    next_week_returns = weekly_simple_returns.shift(-1)
    market_state_history = read_panel_csv(LAYER2B_DIR / "market_state_history.csv")

    active_returns = pd.DataFrame(
        {sleeve: read_panel_csv(LAYER2A_DIR / f"strategy_returns_{sleeve}.csv", value_col="net_return") for sleeve in ACTIVE_PANEL}
    )
    active_positions = {
        sleeve: read_panel_csv(LAYER2A_DIR / f"strategy_positions_{sleeve}.csv")
        for sleeve in ACTIVE_PANEL
    }
    reference_positions = {
        sleeve: read_panel_csv(LAYER2A_DIR / f"strategy_positions_{sleeve}.csv")
        for sleeve in REFERENCE_PANEL
    }

    common_index = next_week_returns.index
    common_index = common_index.intersection(market_state_history.index)
    common_index = common_index.intersection(active_returns.index)
    for sleeve in set(ACTIVE_PANEL + REFERENCE_PANEL):
        common_index = common_index.intersection(read_panel_csv(LAYER2A_DIR / f"strategy_positions_{sleeve}.csv").index)
    common_index = common_index.sort_values()

    next_week_returns = next_week_returns.reindex(common_index).fillna(0.0)
    market_state_history = market_state_history.reindex(common_index)
    active_returns = active_returns.reindex(common_index).fillna(0.0)
    active_positions = {name: df.reindex(common_index).fillna(0.0) for name, df in active_positions.items()}
    reference_positions = {name: df.reindex(common_index).fillna(0.0) for name, df in reference_positions.items()}
    return next_week_returns, active_returns, active_positions, reference_positions, market_state_history


def bounded_zero_to_one(value: pd.Series | float, low: float, high: float) -> pd.Series | float:
    scaled = (value - low) / (high - low)
    if isinstance(scaled, pd.Series):
        return scaled.clip(0.0, 1.0)
    return float(np.clip(scaled, 0.0, 1.0))


def state_feature_frame(index: pd.Index, market_state_history: pd.DataFrame) -> pd.DataFrame:
    market = market_state_history.reindex(index).copy()
    feature_frame = pd.DataFrame(index=index)
    for col in MARKET_FEATURE_COLUMNS:
        if col in market.columns:
            feature_frame[col] = pd.to_numeric(market[col], errors="coerce")
    feature_frame = feature_frame.fillna(0.0)

    trend_pos = feature_frame["market_trend_positive"].fillna(0.0)
    non_stress = bounded_zero_to_one(feature_frame["transition_non_stress_prob"], 0.45, 0.75)
    persistence = bounded_zero_to_one(feature_frame["transition_persistence_prob"], 0.40, 0.75)
    good_state = bounded_zero_to_one(feature_frame["transition_good_state_prob"], 0.30, 0.70)
    low_corr = bounded_zero_to_one(0.55 - feature_frame["avg_corr_risk_off_z"], 0.0, 0.55)
    low_fear = bounded_zero_to_one(0.45 - feature_frame["google_fear_z_tradable"], -0.10, 0.45)
    breadth_positive = bounded_zero_to_one(feature_frame["breadth_13w_mom"], -0.05, 0.15)
    breadth_improving = bounded_zero_to_one(feature_frame["breadth_change_4w"], -0.15, 0.25)
    stress = bounded_zero_to_one(feature_frame["recent_stress_26w"], 0.0, 2.0)
    drawdown_ok = bounded_zero_to_one(feature_frame["market_drawdown"], -0.20, -0.02)

    calm_confidence = pd.concat(
        [trend_pos, non_stress, persistence, low_corr, low_fear, breadth_positive],
        axis=1,
    ).mean(axis=1)
    calm_confidence = np.where(market["market_state"].eq("calm_trend"), np.minimum(1.0, calm_confidence + 0.15), calm_confidence)

    recovery_confidence = pd.concat(
        [good_state, non_stress, persistence, breadth_improving, trend_pos, drawdown_ok],
        axis=1,
    ).mean(axis=1)
    recovery_confidence = np.where(
        market["market_state"].eq("recovery_confirmed"),
        np.minimum(1.0, recovery_confidence + 0.18),
        recovery_confidence,
    )

    stress_like = pd.concat(
        [
            stress,
            bounded_zero_to_one(feature_frame["avg_corr_risk_off_z"], 0.15, 0.75),
            bounded_zero_to_one(feature_frame["google_fear_z_tradable"], 0.0, 0.70),
            1.0 - non_stress,
        ],
        axis=1,
    ).mean(axis=1)
    stress_like = np.where(market["market_state"].eq("stressed_panic"), np.minimum(1.0, stress_like + 0.20), stress_like)

    chop_confidence = pd.concat(
        [
            1.0 - persistence,
            bounded_zero_to_one(feature_frame["avg_corr_risk_off_z"], 0.15, 0.75),
            bounded_zero_to_one(feature_frame["google_fear_z_tradable"], 0.0, 0.70),
            1.0 - non_stress,
        ],
        axis=1,
    ).mean(axis=1)
    chop_confidence = np.where(market["market_state"].eq("neutral_mixed"), np.minimum(1.0, chop_confidence + 0.10), chop_confidence)

    feature_frame["calm_confidence"] = pd.Series(calm_confidence, index=index)
    feature_frame["recovery_confidence"] = pd.Series(recovery_confidence, index=index)
    feature_frame["stress_confidence"] = pd.Series(stress_like, index=index)
    feature_frame["chop_confidence"] = pd.Series(chop_confidence, index=index)
    feature_frame["state_text"] = market["market_state"].fillna("unknown")
    return feature_frame.fillna(0.0)


def equal_sleeve_weights(index: pd.Index, sleeves: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(0.0, index=index, columns=sleeves + [CASH_COLUMN], dtype=float)
    frame.loc[:, sleeves] = 1.0 / len(sleeves)
    return frame


def role_alignment_score(state_features: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.Series] = []
    for date in state_features.index:
        st = state_features.loc[date]
        score = pd.Series(0.0, index=ACTIVE_PANEL, dtype=float, name=date)
        for sleeve in ACTIVE_PANEL:
            role = ROLE_MAP[sleeve]
            value = (
                0.45 * role["calm"] * st["calm_confidence"]
                + 0.50 * role["recovery"] * st["recovery_confidence"]
                + 0.45 * role["chop"] * st["chop_confidence"]
                + 0.55 * role["defense"] * st["stress_confidence"]
            )
            if sleeve == "taa_10m_sma":
                value += 0.12 * st["market_trend_positive"] + 0.08 * st["calm_confidence"]
            if sleeve == "dual_momentum_topn":
                value += 0.15 * st["market_trend_positive"] + 0.10 * st["recovery_confidence"] - 0.08 * st["stress_confidence"]
            if sleeve == "composite_calm_trend_specialist":
                value += 0.20 * st["calm_confidence"] - 0.12 * st["stress_confidence"]
            if sleeve == "composite_healthier_recovery_specialist":
                value += 0.22 * st["recovery_confidence"] - 0.10 * st["chop_confidence"]
            if sleeve == "composite_anti_chop_clarity":
                value += 0.20 * st["chop_confidence"] + 0.10 * st["stress_confidence"] - 0.12 * st["recovery_confidence"]
            if sleeve == "composite_regime_conditioned":
                value += 0.25 * st["stress_confidence"] - 0.10 * st["calm_confidence"]
            score[sleeve] = max(0.02, value)
        rows.append(score)
    score_panel = pd.DataFrame(rows).sort_index().fillna(0.02)
    return score_panel.div(score_panel.sum(axis=1), axis=0).fillna(0.0)


def build_feature_panels(active_returns: pd.DataFrame, state_features: pd.DataFrame, state_prior: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mean_13 = active_returns.rolling(13, min_periods=8).mean().shift(1)
    mean_26 = active_returns.rolling(26, min_periods=8).mean().shift(1)
    vol_13 = active_returns.rolling(13, min_periods=8).std(ddof=0).shift(1)
    vol_26 = active_returns.rolling(26, min_periods=8).std(ddof=0).shift(1)
    win_13 = (active_returns > 0.0).astype(float).rolling(13, min_periods=8).mean().shift(1)
    cum_4 = trailing_compound(active_returns, 4, 4).shift(1)
    cum_13 = trailing_compound(active_returns, 13, 8).shift(1)
    cum_26 = trailing_compound(active_returns, 26, 8).shift(1)
    dd_13 = rolling_drawdown(active_returns, 13, 8).shift(1)
    dd_26 = rolling_drawdown(active_returns, 26, 8).shift(1)
    quality_13 = mean_13.div(vol_13.replace(0.0, np.nan))
    quality_26 = mean_26.div(vol_26.replace(0.0, np.nan))

    rank_quality_13 = quality_13.rank(axis=1, pct=True, method="average")
    rank_quality_26 = quality_26.rank(axis=1, pct=True, method="average")
    rank_cum_13 = cum_13.rank(axis=1, pct=True, method="average")
    rank_cum_26 = cum_26.rank(axis=1, pct=True, method="average")
    rank_win_13 = win_13.rank(axis=1, pct=True, method="average")
    rank_vol_13 = vol_13.rank(axis=1, pct=True, method="average", ascending=False)
    rank_dd_13 = dd_13.abs().rank(axis=1, pct=True, method="average", ascending=False)

    shifted = active_returns.shift(-1)
    forward_4w = (
        (1.0 + shifted).rolling(HORIZON_WEEKS, min_periods=HORIZON_WEEKS).apply(np.prod, raw=True).shift(-(HORIZON_WEEKS - 1)) - 1.0
    )

    long_rows: list[pd.DataFrame] = []
    simple_score_panel = pd.DataFrame(index=active_returns.index, columns=ACTIVE_PANEL, dtype=float)
    for sleeve in ACTIVE_PANEL:
        sleeve_frame = pd.DataFrame(index=active_returns.index)
        sleeve_frame["Date"] = active_returns.index
        sleeve_frame["sleeve"] = sleeve
        sleeve_frame["mean_13"] = mean_13[sleeve]
        sleeve_frame["mean_26"] = mean_26[sleeve]
        sleeve_frame["vol_13"] = vol_13[sleeve]
        sleeve_frame["vol_26"] = vol_26[sleeve]
        sleeve_frame["quality_13"] = quality_13[sleeve]
        sleeve_frame["quality_26"] = quality_26[sleeve]
        sleeve_frame["cum_4"] = cum_4[sleeve]
        sleeve_frame["cum_13"] = cum_13[sleeve]
        sleeve_frame["cum_26"] = cum_26[sleeve]
        sleeve_frame["win_13"] = win_13[sleeve]
        sleeve_frame["dd_13"] = dd_13[sleeve]
        sleeve_frame["dd_26"] = dd_26[sleeve]
        sleeve_frame["rank_quality_13"] = rank_quality_13[sleeve]
        sleeve_frame["rank_quality_26"] = rank_quality_26[sleeve]
        sleeve_frame["rank_cum_13"] = rank_cum_13[sleeve]
        sleeve_frame["rank_cum_26"] = rank_cum_26[sleeve]
        sleeve_frame["rank_win_13"] = rank_win_13[sleeve]
        sleeve_frame["rank_vol_13"] = rank_vol_13[sleeve]
        sleeve_frame["rank_dd_13"] = rank_dd_13[sleeve]
        sleeve_frame["state_prior_weight"] = state_prior[sleeve]
        sleeve_frame["target_return_4w"] = forward_4w[sleeve]
        sleeve_frame["role_calm"] = ROLE_MAP[sleeve]["calm"]
        sleeve_frame["role_recovery"] = ROLE_MAP[sleeve]["recovery"]
        sleeve_frame["role_chop"] = ROLE_MAP[sleeve]["chop"]
        sleeve_frame["role_defense"] = ROLE_MAP[sleeve]["defense"]
        sleeve_frame = sleeve_frame.join(state_features.drop(columns=["state_text"]), how="left")
        long_rows.append(sleeve_frame)

        simple_score_panel[sleeve] = (
            0.24 * (rank_quality_13[sleeve] - 0.5) * 2.0
            + 0.18 * (rank_quality_26[sleeve] - 0.5) * 2.0
            + 0.18 * (rank_cum_13[sleeve] - 0.5) * 2.0
            + 0.12 * (rank_win_13[sleeve] - 0.5) * 2.0
            + 0.08 * (rank_vol_13[sleeve] - 0.5) * 2.0
            + 0.08 * (rank_dd_13[sleeve] - 0.5) * 2.0
            + 0.12 * centered_rank(state_prior[sleeve])
        )

    long_panel = pd.concat(long_rows, axis=0, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    sleeve_dummies = pd.get_dummies(long_panel["sleeve"], prefix="sleeve", dtype=float)
    long_panel = pd.concat([long_panel, sleeve_dummies], axis=1)

    date_panel = pd.DataFrame(index=active_returns.index)
    date_panel["Date"] = active_returns.index
    date_panel["quality_top"] = quality_13.max(axis=1)
    date_panel["quality_gap"] = quality_13.max(axis=1) - quality_13.median(axis=1)
    date_panel["cum_gap"] = cum_13.max(axis=1) - cum_13.median(axis=1)
    date_panel["simple_score_gap"] = simple_score_panel.max(axis=1) - simple_score_panel.median(axis=1)
    date_panel["simple_score_std"] = simple_score_panel.std(axis=1, ddof=0)
    date_panel["prior_hhi"] = state_prior.pow(2).sum(axis=1)
    date_panel = date_panel.join(state_features.drop(columns=["state_text"]), how="left")

    future_spread = forward_4w.max(axis=1) - forward_4w.median(axis=1)
    date_panel["future_spread"] = future_spread
    return long_panel, date_panel.replace([np.inf, -np.inf], np.nan), simple_score_panel.replace([np.inf, -np.inf], 0.0).fillna(0.0)


def walkforward_panel_regressor(panel: pd.DataFrame, feature_cols: list[str]) -> ModelPredictionResult:
    prediction_rows: list[pd.Series] = []
    feature_importances: list[pd.Series] = []
    fitted_model = None
    last_fit_date: pd.Timestamp | None = None

    for date in sorted(pd.Index(panel["Date"].dropna().unique())):
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel["target_return_4w"].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                model = make_pipeline(
                    StandardScaler(),
                    Ridge(alpha=1.0),
                )
                model.fit(train[feature_cols].fillna(0.0), train["target_return_4w"].astype(float))
                fitted_model = model
                feature_importances.append(
                    pd.Series(np.abs(model.named_steps["ridge"].coef_), index=feature_cols)
                )
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

    prediction_frame = pd.DataFrame(prediction_rows).reindex(columns=ACTIVE_PANEL).sort_index().fillna(0.0)
    if feature_importances:
        importance = pd.concat(feature_importances, axis=1).mean(axis=1).sort_values(ascending=False)
    else:
        importance = pd.Series(dtype=float)
    return ModelPredictionResult(prediction_frame=prediction_frame, feature_importance=importance)


def walkforward_date_regressor(panel: pd.DataFrame, feature_cols: list[str]) -> ModelPredictionResult:
    prediction_rows: list[pd.Series] = []
    feature_importances: list[pd.Series] = []
    fitted_model = None
    last_fit_date: pd.Timestamp | None = None

    for date in sorted(pd.Index(panel["Date"].dropna().unique())):
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel["future_spread"].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                model = make_pipeline(
                    StandardScaler(),
                    Ridge(alpha=1.0),
                )
                model.fit(train[feature_cols].fillna(0.0), train["future_spread"].astype(float))
                fitted_model = model
                feature_importances.append(
                    pd.Series(np.abs(model.named_steps["ridge"].coef_), index=feature_cols)
                )
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        if date_rows.empty:
            continue
        value = 0.0 if fitted_model is None else float(fitted_model.predict(date_rows[feature_cols].fillna(0.0))[0])
        prediction_rows.append(pd.Series({"predicted_spread": value}, name=date))

    prediction_frame = pd.DataFrame(prediction_rows).sort_index()
    if feature_importances:
        importance = pd.concat(feature_importances, axis=1).mean(axis=1).sort_values(ascending=False)
    else:
        importance = pd.Series(dtype=float)
    return ModelPredictionResult(prediction_frame=prediction_frame, feature_importance=importance)


def normalize_prior(prior_row: pd.Series) -> pd.Series:
    prior = pd.Series(prior_row, dtype=float).clip(lower=0.0)
    total = float(prior.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(prior), index=prior.index)
    return prior / total


def tilted_weights(
    prior: pd.Series,
    score: pd.Series,
    *,
    blend: float,
    strength: float,
    multiplier_floor: float = 0.40,
    multiplier_cap: float = 2.10,
) -> pd.Series:
    centered = center_and_scale(score.reindex(prior.index).fillna(0.0))
    multipliers = np.exp(strength * centered).clip(multiplier_floor, multiplier_cap)
    tilted = prior.mul(multipliers, axis=0)
    tilted = tilted / float(tilted.sum())
    mixed = ((1.0 - blend) * prior + blend * tilted).clip(lower=0.0)
    mixed = mixed / float(mixed.sum())
    return mixed


def build_candidate_sleeve_weights(
    candidate_name: str,
    state_prior: pd.DataFrame,
    learned_pred: pd.DataFrame,
    spread_pred: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    state_features: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[pd.Series] = []
    spread_series = spread_pred["predicted_spread"].reindex(state_prior.index).fillna(0.0)
    equal_prior = pd.Series(1.0 / len(ACTIVE_PANEL), index=ACTIVE_PANEL)

    for date in state_prior.index:
        new_row = pd.Series(0.0, index=ACTIVE_PANEL + [CASH_COLUMN], dtype=float, name=date)
        prior_state = normalize_prior(state_prior.loc[date])
        learned_score = learned_pred.loc[date, ACTIVE_PANEL].fillna(0.0)
        simple_score = simple_score_panel.loc[date, ACTIVE_PANEL].fillna(0.0)
        spread_scalar = float(np.clip((spread_series.loc[date] - 0.008) / 0.050, 0.0, 1.0))
        st = state_features.loc[date]

        if candidate_name == "improved_phaseh_refined_state_allocator":
            risky = prior_state
        elif candidate_name == "improved_phaseh_refined_learned_allocator":
            risky = tilted_weights(
                equal_prior,
                learned_score,
                blend=0.60,
                strength=0.95,
                multiplier_floor=0.45,
                multiplier_cap=1.90,
            )
        elif candidate_name == "improved_phaseh_refined_concentration_allocator":
            role_score = 0.70 * centered_rank(simple_score) + 0.30 * centered_rank(prior_state)
            capped_scalar = spread_scalar
            if st["stress_confidence"] > 0.55:
                capped_scalar = min(capped_scalar, 0.20)
            risky = tilted_weights(
                prior_state,
                role_score,
                blend=0.20 + 0.55 * capped_scalar,
                strength=0.45 + 0.90 * capped_scalar,
                multiplier_floor=0.50,
                multiplier_cap=1.55 + 0.90 * capped_scalar,
            )
        elif candidate_name == "improved_phaseh_refined_combo_allocator":
            combo_score = 0.60 * centered_rank(learned_score) + 0.25 * centered_rank(simple_score) + 0.15 * centered_rank(prior_state)
            capped_scalar = spread_scalar
            if st["stress_confidence"] > 0.55:
                capped_scalar = min(capped_scalar, 0.25)
            if st["calm_confidence"] > 0.65 or st["recovery_confidence"] > 0.65:
                capped_scalar = min(1.0, capped_scalar + 0.10)
            risky = tilted_weights(
                prior_state,
                combo_score,
                blend=0.35 + 0.40 * capped_scalar,
                strength=0.65 + 0.85 * capped_scalar,
                multiplier_floor=0.45,
                multiplier_cap=1.85 + 0.75 * capped_scalar,
            )
        else:
            raise ValueError(f"Unknown candidate {candidate_name}")

        new_row.loc[risky.index] = risky
        rows.append(new_row)

    sleeve_weights = pd.DataFrame(rows).sort_index().fillna(0.0)
    sleeve_weights = sleeve_weights.div(sleeve_weights.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    return sleeve_weights


def build_lookthrough_weights(
    sleeve_weights: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    universe_columns: list[str],
) -> pd.DataFrame:
    rows: list[pd.Series] = []
    all_columns = list(dict.fromkeys(list(universe_columns) + [CASH_PROXY]))
    for date in sleeve_weights.index:
        etf_row = pd.Series(0.0, index=all_columns, dtype=float, name=date)
        for sleeve in ACTIVE_PANEL:
            weight = float(sleeve_weights.at[date, sleeve])
            if weight <= 0.0:
                continue
            positions = sleeve_positions[sleeve].reindex(columns=all_columns, fill_value=0.0)
            etf_row = etf_row.add(weight * positions.loc[date].reindex(all_columns).fillna(0.0), fill_value=0.0)
        etf_row[CASH_PROXY] += float(sleeve_weights.at[date, CASH_COLUMN])
        rows.append(etf_row)
    return pd.DataFrame(rows).sort_index().fillna(0.0)


def blend_lookthrough_weights(
    sleeve_names: list[str],
    sleeve_positions: dict[str, pd.DataFrame],
    universe_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sleeve_weights = equal_sleeve_weights(next(iter(sleeve_positions.values())).index, sleeve_names)
    rows: list[pd.Series] = []
    all_columns = list(dict.fromkeys(list(universe_columns) + [CASH_PROXY]))
    for date in sleeve_weights.index:
        etf_row = pd.Series(0.0, index=all_columns, dtype=float, name=date)
        for sleeve in sleeve_names:
            weight = float(sleeve_weights.at[date, sleeve])
            positions = sleeve_positions[sleeve].reindex(columns=all_columns, fill_value=0.0)
            etf_row = etf_row.add(weight * positions.loc[date].reindex(all_columns).fillna(0.0), fill_value=0.0)
        rows.append(etf_row)
    return sleeve_weights, pd.DataFrame(rows).sort_index().fillna(0.0)


def state_summary(return_series: pd.Series, weight_panel: pd.DataFrame, market_state_history: pd.DataFrame, version_name: str) -> pd.DataFrame:
    joined = pd.DataFrame(
        {
            "net_return": return_series,
            "market_state": market_state_history.reindex(return_series.index)["market_state"],
            "bil_weight": weight_panel.get("BIL", pd.Series(0.0, index=weight_panel.index)).reindex(return_series.index).fillna(0.0),
            "spy_weight": weight_panel.get("SPY", pd.Series(0.0, index=weight_panel.index)).reindex(return_series.index).fillna(0.0),
        }
    ).dropna(subset=["market_state"])
    defensive_assets = [c for c in ["IEF", "SHY", "TLT", "TIP", "GLD", "LQD"] if c in weight_panel.columns and c != CASH_PROXY]
    offensive_assets = [c for c in weight_panel.columns if c not in set(defensive_assets + [CASH_PROXY])]
    joined["offense_weight"] = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1).reindex(joined.index).fillna(0.0)
    joined["defense_weight"] = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1).reindex(joined.index).fillna(0.0)

    rows: list[dict[str, float | str | int]] = []
    for market_state, group in joined.groupby("market_state"):
        state_return = annualized_return(group["net_return"])
        state_vol = annualized_vol(group["net_return"])
        rows.append(
            {
                "version_name": version_name,
                "market_state": market_state,
                "observations": int(len(group)),
                "ann_return_state": state_return,
                "ann_vol_state": state_vol,
                "sharpe_state": state_return / state_vol if pd.notna(state_return) and pd.notna(state_vol) and state_vol > 0 else np.nan,
                "avg_bil_state": float(group["bil_weight"].mean()),
                "avg_spy_state": float(group["spy_weight"].mean()),
                "avg_offense_state": float(group["offense_weight"].mean()),
                "avg_defense_state": float(group["defense_weight"].mean()),
                "avg_cash_state": float(group["bil_weight"].mean()),
            }
        )
    return pd.DataFrame(rows)


def sleeve_allocation_summary(
    sleeve_alloc: pd.DataFrame,
    market_state_history: pd.DataFrame,
    version_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    state_series = market_state_history.reindex(sleeve_alloc.index)["market_state"]
    overall_rows: list[dict[str, float | str]] = []
    state_rows: list[dict[str, float | str]] = []
    for sleeve in sleeve_alloc.columns:
        if sleeve == CASH_COLUMN:
            continue
        overall_rows.append(
            {
                "version_name": version_name,
                "sleeve_name": sleeve,
                "avg_weight": float(sleeve_alloc[sleeve].mean()),
                "avg_weight_when_active": float(sleeve_alloc.loc[sleeve_alloc[sleeve] > 0, sleeve].mean()) if (sleeve_alloc[sleeve] > 0).any() else 0.0,
                "active_share": float((sleeve_alloc[sleeve] > 0).mean()),
            }
        )
        state_frame = pd.DataFrame({"weight": sleeve_alloc[sleeve], "market_state": state_series}).dropna(subset=["market_state"])
        for market_state, group in state_frame.groupby("market_state"):
            state_rows.append(
                {
                    "version_name": version_name,
                    "sleeve_name": sleeve,
                    "market_state": market_state,
                    "avg_weight_state": float(group["weight"].mean()),
                }
            )
    return pd.DataFrame(overall_rows), pd.DataFrame(state_rows)


def concentration_summary(sleeve_alloc: pd.DataFrame, market_state_history: pd.DataFrame, version_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    risky = sleeve_alloc[ACTIVE_PANEL]
    risky_norm = risky.div(risky.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    state_series = market_state_history.reindex(risky.index)["market_state"]
    overall = pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_top1_share": float(risky_norm.max(axis=1).mean()),
                "avg_top2_share": float(np.sort(risky_norm.to_numpy(), axis=1)[:, -2:].sum(axis=1).mean()),
                "avg_hhi": float(risky_norm.pow(2).sum(axis=1).mean()),
                "avg_role_share_new": float(
                    risky_norm[["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]].sum(axis=1).mean()
                ),
            }
        ]
    )
    rows: list[dict[str, float | str]] = []
    for market_state, idx in state_series.groupby(state_series).groups.items():
        sub = risky_norm.loc[idx]
        rows.append(
            {
                "version_name": version_name,
                "market_state": market_state,
                "avg_top1_share": float(sub.max(axis=1).mean()),
                "avg_top2_share": float(np.sort(sub.to_numpy(), axis=1)[:, -2:].sum(axis=1).mean()),
                "avg_hhi": float(sub.pow(2).sum(axis=1).mean()),
                "avg_role_share_new": float(
                    sub[["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]].sum(axis=1).mean()
                ),
            }
        )
    return overall, pd.DataFrame(rows)


def save_portfolio_version(version_name: str, sleeve_weights: pd.DataFrame, etf_weights: pd.DataFrame, next_week_returns: pd.DataFrame) -> pd.DataFrame:
    path = pf.compute_portfolio_path(etf_weights, next_week_returns.reindex(index=etf_weights.index, columns=etf_weights.columns).fillna(0.0))
    sleeve_weights.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv")
    etf_weights.to_csv(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")
    path.to_csv(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")
    return path


def main() -> None:
    next_week_returns, active_returns, active_positions, reference_positions, market_state_history = load_inputs()
    state_features = state_feature_frame(active_returns.index, market_state_history)
    state_prior = role_alignment_score(state_features)
    long_panel, date_panel, simple_score_panel = build_feature_panels(active_returns, state_features, state_prior)

    panel_feature_cols = [
        col
        for col in long_panel.columns
        if col not in {"Date", "sleeve", "target_return_4w"}
    ]
    date_feature_cols = [col for col in date_panel.columns if col not in {"Date", "future_spread"}]

    learned_model = walkforward_panel_regressor(long_panel, panel_feature_cols)
    spread_model = walkforward_date_regressor(date_panel, date_feature_cols)

    feature_rows: list[dict[str, float | str]] = []
    for model_name, result in {
        "learned_allocator_regressor": learned_model.feature_importance,
        "concentration_regressor": spread_model.feature_importance,
    }.items():
        for feature_name, importance in result.head(20).items():
            feature_rows.append({"model_name": model_name, "feature_name": feature_name, "importance": float(importance)})

    universe_columns = list(next_week_returns.columns)

    reference_sleeve_weights, reference_etf_weights = blend_lookthrough_weights(REFERENCE_PANEL, reference_positions, universe_columns)
    refined_blend_sleeve_weights, refined_blend_etf_weights = blend_lookthrough_weights(ACTIVE_PANEL, active_positions, universe_columns)

    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    variant_rows: list[dict[str, float | str]] = []

    for version_name, sleeve_weights, etf_weights in [
        ("improved_phaseh_reference_core_blend", reference_sleeve_weights, reference_etf_weights),
        ("improved_phaseh_refined_panel_blend", refined_blend_sleeve_weights, refined_blend_etf_weights),
    ]:
        path = save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)
        state_rows.append(state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        if version_name == "improved_phaseh_refined_panel_blend":
            conc_summary, conc_state = concentration_summary(sleeve_weights, market_state_history, version_name)
            concentration_rows.append(conc_summary)
            concentration_state_rows.append(conc_state)
        variant_rows.append(
            {
                "version_name": version_name,
                "ann_return": annualized_return(path["net_return"]),
                "ann_vol": annualized_vol(path["net_return"]),
                "sharpe": annualized_return(path["net_return"]) / annualized_vol(path["net_return"]) if annualized_vol(path["net_return"]) > 0 else np.nan,
                "max_drawdown": max_drawdown(path["net_return"]),
                "turnover": float(path["turnover"].mean()),
                "avg_bil": float(etf_weights.get("BIL", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_spy": float(etf_weights.get("SPY", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_role_share_new": float(
                    sleeve_weights.reindex(columns=["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"], fill_value=0.0).sum(axis=1).mean()
                ) if set(["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]).intersection(sleeve_weights.columns) else 0.0,
            }
        )

    for version_name in PHASE_H_CANDIDATES:
        sleeve_weights = build_candidate_sleeve_weights(
            version_name,
            state_prior,
            learned_model.prediction_frame,
            spread_model.prediction_frame,
            simple_score_panel,
            state_features,
        )
        etf_weights = build_lookthrough_weights(sleeve_weights, active_positions, universe_columns)
        path = save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)
        state_rows.append(state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        conc_summary, conc_state = concentration_summary(sleeve_weights, market_state_history, version_name)
        concentration_rows.append(conc_summary)
        concentration_state_rows.append(conc_state)
        variant_rows.append(
            {
                "version_name": version_name,
                "ann_return": annualized_return(path["net_return"]),
                "ann_vol": annualized_vol(path["net_return"]),
                "sharpe": annualized_return(path["net_return"]) / annualized_vol(path["net_return"]) if annualized_vol(path["net_return"]) > 0 else np.nan,
                "max_drawdown": max_drawdown(path["net_return"]),
                "turnover": float(path["turnover"].mean()),
                "avg_bil": float(etf_weights.get("BIL", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_spy": float(etf_weights.get("SPY", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_role_share_new": float(
                    sleeve_weights[["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]].sum(axis=1).mean()
                ),
            }
        )

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_h_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_h_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_h_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_h_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_h_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_h_concentration_by_state.csv", index=False)
    learned_model.prediction_frame.to_csv(LAYER3_DIR / "phase_h_predicted_forward_returns.csv")
    spread_model.prediction_frame.to_csv(LAYER3_DIR / "phase_h_predicted_spread.csv")
    pd.DataFrame(feature_rows).to_csv(LAYER3_DIR / "phase_h_feature_importance_summary.csv", index=False)

    protocol = {
        "phase": "Phase H",
        "purpose": "Allocator return on refined redesigned sleeve panel",
        "reference_panel": REFERENCE_PANEL,
        "active_panel": ACTIVE_PANEL,
        "baseline_versions": BASELINE_VERSIONS,
        "candidate_versions": PHASE_H_CANDIDATES,
        "constraints": {
            "transaction_cost_bps": DEFAULT_COST_BPS,
            "horizon_weeks": HORIZON_WEEKS,
            "min_train_weeks": MIN_TRAIN_WEEKS,
            "retrain_frequency_weeks": RETRAIN_FREQUENCY_WEEKS,
            "top_level_cash_overlay": "disabled",
        },
    }
    (LAYER3_DIR / "phase_h_allocator_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase H allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_h_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_h_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_h_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_h_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_h_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_h_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_h_feature_importance_summary.csv",
        "data/05_layer3_portfolio_construction/phase_h_allocator_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
