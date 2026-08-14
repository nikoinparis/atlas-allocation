from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor


ROOT = Path(__file__).resolve().parents[1]
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

BASELINE_VERSIONS = [
    "improved_phase2b_regime_confidence_boost",
    "improved_phase2b_combo_abc",
    "improved_phasec_sleeve_universe_base",
    "improved_phasec_state_conditioned_map",
]

BASE_VERSION = "improved_phasec_sleeve_universe_base"
STATE_MAP_VERSION = "improved_phasec_state_conditioned_map"

SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_trend_quality_refined",
    "composite_regime_conditioned",
    "taa_10m_sma",
    "composite_confirmation_aware_momentum",
]
NEW_PHASEB_SLEEVES = ["composite_trend_quality_refined", "composite_confirmation_aware_momentum"]
CASH_COLUMN = "cash::BIL"
CASH_PROXY = "BIL"
DEFAULT_COST_BPS = 10
HORIZON_WEEKS = 4
MIN_TRAIN_WEEKS = 156
RETRAIN_FREQUENCY_WEEKS = 13

PHASE_E_CANDIDATES = {
    "improved_phasee_gbt_allocator": "E1 richer learned sleeve allocator",
    "improved_phasee_concentration_gate": "E2 learned conditional concentration model",
    "improved_phasee_state_sleeve_boosting": "E3 richer state x sleeve interaction allocator",
    "improved_phasee_combo_allocator": "E4 disciplined heavier combo",
    "improved_phasee_state_prior_concentration": "E5 conservative state-prior concentration blend",
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


def read_weight_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame.sort_index().fillna(0.0)


def compute_portfolio_path(weights: pd.DataFrame, next_week_returns: pd.DataFrame, transaction_cost_bps: float = DEFAULT_COST_BPS) -> pd.DataFrame:
    weights = weights.reindex(index=next_week_returns.index, columns=next_week_returns.columns).fillna(0.0)
    gross_return = (weights * next_week_returns).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover) > 0:
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * (transaction_cost_bps / 10000.0)
    net_return = gross_return - cost
    wealth = (1.0 + net_return.fillna(0.0)).cumprod()
    running_peak = wealth.cummax()
    drawdown = wealth.div(running_peak) - 1.0
    return pd.DataFrame(
        {
            "gross_return": gross_return,
            "net_return": net_return,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": drawdown,
        }
    )


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


def rank_pct_frame(frame: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True, method="average", ascending=ascending)


def active_rank_feature(frame: pd.DataFrame, active_mask: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    masked = frame.where(active_mask)
    return masked.rank(axis=1, pct=True, method="average", ascending=ascending).fillna(0.5)


def centered_rank(series: pd.Series) -> pd.Series:
    if series.dropna().empty:
        return pd.Series(0.0, index=series.index, dtype=float)
    return ((series.rank(pct=True, method="average") - 0.5) * 2.0).fillna(0.0)


def center_and_scale(series: pd.Series) -> pd.Series:
    clean = pd.Series(series, dtype=float)
    if clean.dropna().empty:
        return pd.Series(0.0, index=clean.index, dtype=float)
    centered = clean - clean.mean()
    scale = centered.std(ddof=0)
    if pd.isna(scale) or scale <= 1e-9:
        return pd.Series(0.0, index=clean.index, dtype=float)
    return centered.div(scale).replace([np.inf, -np.inf], 0.0).fillna(0.0)


def base_state_frame(index: pd.Index, market_state_history: pd.DataFrame) -> pd.DataFrame:
    market = market_state_history.reindex(index).copy()
    state_dummies = pd.get_dummies(market["market_state"].fillna("unknown"), prefix="state", dtype=float)
    feature_frame = pd.DataFrame(index=index)
    for col in MARKET_FEATURE_COLUMNS:
        if col in market.columns:
            feature_frame[col] = pd.to_numeric(market[col], errors="coerce")
    feature_frame = feature_frame.join(state_dummies, how="left").fillna(0.0)
    feature_frame["strong_or_better"] = market["market_state"].isin(["strong_neutral", "calm_trend", "recovery_confirmed"]).astype(float)
    feature_frame["improving_state"] = market["market_state"].isin(["recovery_fragile", "recovery_confirmed", "strong_neutral"]).astype(float)
    feature_frame["stress_like"] = market["market_state"].isin(["stressed_panic", "crisis"]).astype(float)
    feature_frame["state_text"] = market["market_state"].fillna("unknown")
    return feature_frame


def load_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, pd.DataFrame],
    pd.Series,
    pd.DataFrame,
]:
    weekly_log_returns = read_panel_csv(DATA_HUB_DIR / "weekly_returns.csv")
    weekly_simple_returns = np.expm1(weekly_log_returns)
    next_week_returns = weekly_simple_returns.shift(-1)

    market_state_history = read_panel_csv(LAYER2B_DIR / "market_state_history.csv")
    benchmark_returns = read_panel_csv(
        LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv",
        value_col="net_return",
    )

    sleeve_return_panel = pd.DataFrame(
        {
            sleeve: read_panel_csv(LAYER2A_DIR / f"strategy_returns_{sleeve}.csv", value_col="net_return")
            for sleeve in SLEEVES
        }
    )
    sleeve_positions = {
        sleeve: read_panel_csv(LAYER2A_DIR / f"strategy_positions_{sleeve}.csv")
        for sleeve in SLEEVES
    }

    base_alloc = read_weight_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{BASE_VERSION}.csv").reindex(columns=SLEEVES + [CASH_COLUMN], fill_value=0.0)
    state_alloc = read_weight_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{STATE_MAP_VERSION}.csv").reindex(columns=SLEEVES + [CASH_COLUMN], fill_value=0.0)

    common_index = base_alloc.index
    common_index = common_index.intersection(state_alloc.index)
    common_index = common_index.intersection(sleeve_return_panel.index)
    common_index = common_index.intersection(next_week_returns.index)
    common_index = common_index.intersection(market_state_history.index)
    common_index = common_index.intersection(benchmark_returns.index)
    common_index = common_index.sort_values()

    base_alloc = base_alloc.reindex(common_index).fillna(0.0)
    state_alloc = state_alloc.reindex(common_index).fillna(0.0)
    sleeve_return_panel = sleeve_return_panel.reindex(common_index).fillna(0.0)
    market_state_history = market_state_history.reindex(common_index)
    next_week_returns = next_week_returns.reindex(common_index).fillna(0.0)
    benchmark_returns = benchmark_returns.reindex(common_index).fillna(0.0)
    sleeve_positions = {name: df.reindex(common_index).fillna(0.0) for name, df in sleeve_positions.items()}
    return base_alloc, state_alloc, sleeve_return_panel, market_state_history, sleeve_positions, benchmark_returns, next_week_returns


def build_feature_panels(
    base_alloc: pd.DataFrame,
    state_alloc: pd.DataFrame,
    sleeve_return_panel: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    active_mask = base_alloc[SLEEVES] > 1e-10

    mean_13 = sleeve_return_panel.rolling(13, min_periods=8).mean().shift(1)
    mean_26 = sleeve_return_panel.rolling(26, min_periods=8).mean().shift(1)
    mean_52 = sleeve_return_panel.rolling(52, min_periods=16).mean().shift(1)
    vol_13 = sleeve_return_panel.rolling(13, min_periods=8).std(ddof=0).shift(1)
    vol_26 = sleeve_return_panel.rolling(26, min_periods=8).std(ddof=0).shift(1)
    vol_52 = sleeve_return_panel.rolling(52, min_periods=16).std(ddof=0).shift(1)
    win_13 = (sleeve_return_panel > 0.0).astype(float).rolling(13, min_periods=8).mean().shift(1)
    cum_4 = trailing_compound(sleeve_return_panel, 4, 4).shift(1)
    cum_13 = trailing_compound(sleeve_return_panel, 13, 8).shift(1)
    cum_26 = trailing_compound(sleeve_return_panel, 26, 8).shift(1)
    cum_52 = trailing_compound(sleeve_return_panel, 52, 16).shift(1)
    dd_13 = rolling_drawdown(sleeve_return_panel, 13, 8).shift(1)
    dd_26 = rolling_drawdown(sleeve_return_panel, 26, 8).shift(1)

    quality_13 = mean_13.div(vol_13.replace(0.0, np.nan))
    quality_26 = mean_26.div(vol_26.replace(0.0, np.nan))
    quality_52 = mean_52.div(vol_52.replace(0.0, np.nan))

    base_risky_norm = base_alloc[SLEEVES].div(base_alloc[SLEEVES].sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    state_risky_norm = state_alloc[SLEEVES].div(state_alloc[SLEEVES].sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)

    rank_quality_13 = active_rank_feature(quality_13, active_mask, ascending=True)
    rank_quality_26 = active_rank_feature(quality_26, active_mask, ascending=True)
    rank_cum_13 = active_rank_feature(cum_13, active_mask, ascending=True)
    rank_cum_26 = active_rank_feature(cum_26, active_mask, ascending=True)
    rank_win_13 = active_rank_feature(win_13, active_mask, ascending=True)
    rank_vol_13 = active_rank_feature(vol_13, active_mask, ascending=False)
    rank_dd_13 = active_rank_feature(dd_13.abs(), active_mask, ascending=False)
    rank_base = active_rank_feature(base_risky_norm, active_mask, ascending=True)
    rank_state = active_rank_feature(state_risky_norm, active_mask, ascending=True)

    market_features = base_state_frame(base_alloc.index, market_state_history)

    shifted = sleeve_return_panel.shift(-1)
    forward_4w = (
        (1.0 + shifted).rolling(HORIZON_WEEKS, min_periods=HORIZON_WEEKS).apply(np.prod, raw=True).shift(-(HORIZON_WEEKS - 1)) - 1.0
    )
    forward_active = forward_4w.where(active_mask)

    top_counts = active_mask.sum(axis=1).clip(lower=1).clip(upper=2)
    rank_desc = forward_active.rank(axis=1, ascending=False, method="first")
    top2_label = rank_desc.le(top_counts, axis=0).astype(float).where(active_mask, np.nan)

    feature_rows: list[pd.DataFrame] = []
    simple_score_panel = pd.DataFrame(index=base_alloc.index, columns=SLEEVES, dtype=float)
    for sleeve in SLEEVES:
        sleeve_frame = pd.DataFrame(index=base_alloc.index)
        sleeve_frame["Date"] = base_alloc.index
        sleeve_frame["sleeve"] = sleeve
        sleeve_frame["active_base"] = active_mask[sleeve].astype(float)
        sleeve_frame["base_weight"] = base_risky_norm[sleeve]
        sleeve_frame["state_weight"] = state_risky_norm[sleeve]
        sleeve_frame["mean_13"] = mean_13[sleeve]
        sleeve_frame["mean_26"] = mean_26[sleeve]
        sleeve_frame["mean_52"] = mean_52[sleeve]
        sleeve_frame["vol_13"] = vol_13[sleeve]
        sleeve_frame["vol_26"] = vol_26[sleeve]
        sleeve_frame["vol_52"] = vol_52[sleeve]
        sleeve_frame["quality_13"] = quality_13[sleeve]
        sleeve_frame["quality_26"] = quality_26[sleeve]
        sleeve_frame["quality_52"] = quality_52[sleeve]
        sleeve_frame["cum_4"] = cum_4[sleeve]
        sleeve_frame["cum_13"] = cum_13[sleeve]
        sleeve_frame["cum_26"] = cum_26[sleeve]
        sleeve_frame["cum_52"] = cum_52[sleeve]
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
        sleeve_frame["rank_base"] = rank_base[sleeve]
        sleeve_frame["rank_state"] = rank_state[sleeve]
        sleeve_frame["target_return_4w"] = forward_4w[sleeve]
        sleeve_frame["target_top2"] = top2_label[sleeve]
        sleeve_frame = sleeve_frame.join(market_features.drop(columns=["state_text"]), how="left")
        feature_rows.append(sleeve_frame)
        simple_score_panel[sleeve] = (
            0.32 * (rank_quality_13[sleeve] - 0.5) * 2.0
            + 0.22 * (rank_quality_26[sleeve] - 0.5) * 2.0
            + 0.20 * (rank_cum_13[sleeve] - 0.5) * 2.0
            + 0.12 * (rank_win_13[sleeve] - 0.5) * 2.0
            + 0.08 * (rank_vol_13[sleeve] - 0.5) * 2.0
            + 0.06 * (rank_state[sleeve] - 0.5) * 2.0
        )

    long_panel = pd.concat(feature_rows, axis=0, ignore_index=True)
    long_panel["Date"] = pd.to_datetime(long_panel["Date"]).dt.tz_localize(None)
    sleeve_dummies = pd.get_dummies(long_panel["sleeve"], prefix="sleeve", dtype=float)
    long_panel = pd.concat([long_panel, sleeve_dummies], axis=1)

    active_count = active_mask.sum(axis=1)
    top_quality_13 = quality_13.where(active_mask).max(axis=1)
    median_quality_13 = quality_13.where(active_mask).median(axis=1)
    top_cum_13 = cum_13.where(active_mask).max(axis=1)
    median_cum_13 = cum_13.where(active_mask).median(axis=1)
    hhi_base = base_risky_norm.pow(2).sum(axis=1)
    future_spread = forward_active.max(axis=1) - forward_active.median(axis=1)

    date_panel = pd.DataFrame(index=base_alloc.index)
    date_panel["Date"] = base_alloc.index
    date_panel["active_count"] = active_count
    date_panel["risky_total_base"] = base_alloc[SLEEVES].sum(axis=1)
    date_panel["cash_weight_base"] = base_alloc[CASH_COLUMN]
    date_panel["state_cash_weight"] = state_alloc[CASH_COLUMN]
    date_panel["hhi_base"] = hhi_base
    date_panel["quality_top"] = top_quality_13
    date_panel["quality_gap"] = top_quality_13 - median_quality_13
    date_panel["cum_gap"] = top_cum_13 - median_cum_13
    date_panel["simple_score_gap"] = simple_score_panel.where(active_mask).max(axis=1) - simple_score_panel.where(active_mask).median(axis=1)
    date_panel["simple_score_std"] = simple_score_panel.where(active_mask).std(axis=1, ddof=0)
    date_panel["future_spread"] = future_spread
    date_panel = date_panel.join(market_features.drop(columns=["state_text"]), how="left")
    date_panel = date_panel.replace([np.inf, -np.inf], np.nan)

    long_panel = long_panel.replace([np.inf, -np.inf], np.nan)
    simple_score_panel = simple_score_panel.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return long_panel, date_panel, market_features, simple_score_panel


def walkforward_panel_model(
    panel: pd.DataFrame,
    *,
    feature_cols: list[str],
    target_col: str,
    is_classifier: bool,
) -> ModelPredictionResult:
    prediction_rows: list[pd.Series] = []
    feature_importances: list[pd.Series] = []
    fitted_model = None
    last_fit_date: pd.Timestamp | None = None
    dates = list(pd.Index(sorted(panel["Date"].dropna().unique())))

    for date in dates:
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[
                (panel["Date"] <= train_cutoff)
                & panel["active_base"].eq(1.0)
                & panel[target_col].notna()
            ].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                X_train = train[feature_cols].fillna(0.0)
                y_train = train[target_col].astype(float)
                if is_classifier:
                    if y_train.nunique() > 1:
                        fitted_model = GradientBoostingClassifier(
                            random_state=7,
                            n_estimators=180,
                            learning_rate=0.04,
                            max_depth=2,
                            subsample=0.8,
                        )
                        fitted_model.fit(X_train, y_train.astype(int))
                        feature_importances.append(pd.Series(fitted_model.feature_importances_, index=feature_cols))
                        last_fit_date = date
                else:
                    fitted_model = GradientBoostingRegressor(
                        random_state=7,
                        loss="huber",
                        n_estimators=220,
                        learning_rate=0.035,
                        max_depth=2,
                        subsample=0.8,
                    )
                    fitted_model.fit(X_train, y_train)
                    feature_importances.append(pd.Series(fitted_model.feature_importances_, index=feature_cols))
                    last_fit_date = date

        date_rows = panel[(panel["Date"] == date) & panel["active_base"].eq(1.0)].copy()
        if date_rows.empty:
            continue
        prediction = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)
        if fitted_model is None:
            prediction.loc[:] = 0.0 if not is_classifier else 0.5
        else:
            X_date = date_rows[feature_cols].fillna(0.0)
            if is_classifier:
                prediction.loc[:] = fitted_model.predict_proba(X_date)[:, 1]
            else:
                prediction.loc[:] = fitted_model.predict(X_date)
        prediction_rows.append(prediction)

    prediction_frame = pd.DataFrame(prediction_rows).reindex(columns=SLEEVES).sort_index().fillna(0.0 if not is_classifier else 0.5)
    if feature_importances:
        importance = pd.concat(feature_importances, axis=1).mean(axis=1).sort_values(ascending=False)
    else:
        importance = pd.Series(dtype=float)
    return ModelPredictionResult(prediction_frame=prediction_frame, feature_importance=importance)


def walkforward_date_model(date_panel: pd.DataFrame, feature_cols: list[str]) -> ModelPredictionResult:
    prediction_rows: list[pd.Series] = []
    feature_importances: list[pd.Series] = []
    fitted_model = None
    last_fit_date: pd.Timestamp | None = None
    panel = date_panel.copy().reset_index(drop=True)
    dates = list(pd.Index(sorted(panel["Date"].dropna().unique())))

    for date in dates:
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel["future_spread"].notna() & panel["active_count"].ge(2)].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                X_train = train[feature_cols].fillna(0.0)
                y_train = train["future_spread"].astype(float)
                fitted_model = GradientBoostingRegressor(
                    random_state=11,
                    loss="huber",
                    n_estimators=180,
                    learning_rate=0.04,
                    max_depth=2,
                    subsample=0.8,
                )
                fitted_model.fit(X_train, y_train)
                feature_importances.append(pd.Series(fitted_model.feature_importances_, index=feature_cols))
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        if date_rows.empty:
            continue
        value = 0.0
        if fitted_model is not None:
            value = float(fitted_model.predict(date_rows[feature_cols].fillna(0.0))[0])
        prediction_rows.append(pd.Series({"predicted_spread": value}, name=date))

    prediction_frame = pd.DataFrame(prediction_rows).sort_index()
    if feature_importances:
        importance = pd.concat(feature_importances, axis=1).mean(axis=1).sort_values(ascending=False)
    else:
        importance = pd.Series(dtype=float)
    return ModelPredictionResult(prediction_frame=prediction_frame, feature_importance=importance)


def normalize_prior(prior_row: pd.Series, active_mask: pd.Series) -> pd.Series:
    active_names = list(prior_row.index[active_mask.reindex(prior_row.index).fillna(False)])
    if not active_names:
        active_names = list(prior_row.index)
    prior = prior_row.reindex(active_names).clip(lower=0.0)
    total = float(prior.sum())
    if total <= 0.0:
        prior = pd.Series(1.0 / len(active_names), index=active_names)
    else:
        prior = prior / total
    return prior


def tilted_weights(
    prior: pd.Series,
    score: pd.Series,
    risky_total: float,
    *,
    blend: float,
    strength: float,
    multiplier_floor: float = 0.35,
    multiplier_cap: float = 2.40,
) -> pd.Series:
    centered = center_and_scale(score.reindex(prior.index).fillna(0.0))
    multipliers = np.exp(strength * centered).clip(multiplier_floor, multiplier_cap)
    tilted_norm = prior.mul(multipliers, axis=0)
    if float(tilted_norm.sum()) <= 0.0:
        tilted_norm = prior.copy()
    else:
        tilted_norm = tilted_norm / float(tilted_norm.sum())
    mixed = ((1.0 - blend) * prior + blend * tilted_norm).clip(lower=0.0)
    mixed = mixed / float(mixed.sum())
    return mixed * risky_total


def build_candidate_sleeve_weights(
    candidate_name: str,
    base_alloc: pd.DataFrame,
    state_alloc: pd.DataFrame,
    e1_pred: pd.DataFrame,
    e2_pred: pd.DataFrame,
    e3_pred: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    market_features: pd.DataFrame,
) -> pd.DataFrame:
    output_rows: list[pd.Series] = []
    pred_spread = e2_pred["predicted_spread"].reindex(base_alloc.index).fillna(0.0)

    for date in base_alloc.index:
        base_row = base_alloc.loc[date, SLEEVES]
        state_row = state_alloc.loc[date, SLEEVES]
        risky_total = float(base_row.sum())
        cash_weight = float(base_alloc.at[date, CASH_COLUMN])
        active = base_row > 1e-10

        new_row = pd.Series(0.0, index=SLEEVES + [CASH_COLUMN], name=date, dtype=float)
        new_row[CASH_COLUMN] = cash_weight
        if risky_total <= 0.0 or not active.any():
            output_rows.append(new_row)
            continue

        if candidate_name == "improved_phasee_gbt_allocator":
            prior = normalize_prior(base_row, active)
            score = e1_pred.loc[date, prior.index].fillna(0.0)
            risky = tilted_weights(prior, score, risky_total, blend=0.58, strength=0.95)
        elif candidate_name == "improved_phasee_concentration_gate":
            prior = normalize_prior(base_row, active)
            scalar = float(np.clip((pred_spread.loc[date] - 0.01) / 0.05, 0.0, 1.0))
            score = simple_score_panel.loc[date, prior.index].fillna(0.0)
            risky = tilted_weights(
                prior,
                score,
                risky_total,
                blend=0.18 + 0.55 * scalar,
                strength=0.45 + 0.90 * scalar,
                multiplier_floor=0.45,
                multiplier_cap=1.60 + 1.20 * scalar,
            )
        elif candidate_name == "improved_phasee_state_sleeve_boosting":
            prior = normalize_prior(state_row, active)
            score = e3_pred.loc[date, prior.index].fillna(0.5)
            risky = tilted_weights(prior, score, risky_total, blend=0.60, strength=1.05)
        elif candidate_name == "improved_phasee_combo_allocator":
            prior = normalize_prior(state_row, active)
            spread_scalar = float(np.clip((pred_spread.loc[date] - 0.008) / 0.055, 0.0, 1.0))
            reg_score = centered_rank(e1_pred.loc[date, prior.index].fillna(0.0))
            cls_score = centered_rank(e3_pred.loc[date, prior.index].fillna(0.5))
            combo_score = 0.60 * reg_score + 0.40 * cls_score
            if market_features.at[date, "stress_like"] > 0.5:
                spread_scalar = min(spread_scalar, 0.25)
            risky = tilted_weights(
                prior,
                combo_score,
                risky_total,
                blend=0.42 + 0.28 * spread_scalar,
                strength=0.80 + 0.70 * spread_scalar,
                multiplier_floor=0.42,
                multiplier_cap=2.00 + 0.70 * spread_scalar,
            )
        elif candidate_name == "improved_phasee_state_prior_concentration":
            prior = normalize_prior(state_row, active)
            spread_scalar = float(np.clip((pred_spread.loc[date] - 0.012) / 0.048, 0.0, 1.0))
            simple_score = centered_rank(simple_score_panel.loc[date, prior.index].fillna(0.0))
            cls_score = centered_rank(e3_pred.loc[date, prior.index].fillna(0.5))
            combo_score = 0.55 * simple_score + 0.45 * cls_score
            risky = tilted_weights(
                prior,
                combo_score,
                risky_total,
                blend=0.16 + 0.40 * spread_scalar,
                strength=0.40 + 0.70 * spread_scalar,
                multiplier_floor=0.50,
                multiplier_cap=1.45 + 0.85 * spread_scalar,
            )
        else:
            raise ValueError(f"Unknown candidate {candidate_name}")

        new_row.loc[risky.index] = risky
        output_rows.append(new_row)

    sleeve_weights = pd.DataFrame(output_rows).sort_index().fillna(0.0)
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
        for sleeve in SLEEVES:
            weight = float(sleeve_weights.at[date, sleeve])
            if weight <= 0.0:
                continue
            positions = sleeve_positions[sleeve].reindex(columns=all_columns, fill_value=0.0)
            etf_row = etf_row.add(weight * positions.loc[date].reindex(all_columns).fillna(0.0), fill_value=0.0)
        etf_row[CASH_PROXY] += float(sleeve_weights.at[date, CASH_COLUMN])
        rows.append(etf_row)
    return pd.DataFrame(rows).sort_index().fillna(0.0)


def state_summary(
    return_series: pd.Series,
    weight_panel: pd.DataFrame,
    market_state_history: pd.DataFrame,
    version_name: str,
) -> pd.DataFrame:
    joined = pd.DataFrame(
        {
            "net_return": return_series,
            "market_state": market_state_history.reindex(return_series.index)["market_state"],
            "bil_weight": weight_panel.get("BIL", pd.Series(0.0, index=weight_panel.index)).reindex(return_series.index).fillna(0.0),
            "spy_weight": weight_panel.get("SPY", pd.Series(0.0, index=weight_panel.index)).reindex(return_series.index).fillna(0.0),
        }
    ).dropna(subset=["market_state"])
    defensive_assets = [c for c in ["IEF", "SHY", "TLT", "TIP", "GLD"] if c in weight_panel.columns and c != CASH_PROXY]
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
    risky = sleeve_alloc[SLEEVES]
    risky_norm = risky.div(risky.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    state_series = market_state_history.reindex(risky.index)["market_state"]
    overall = pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_top1_share": float(risky_norm.max(axis=1).mean()),
                "avg_top2_share": float(np.sort(risky_norm.to_numpy(), axis=1)[:, -2:].sum(axis=1).mean()),
                "avg_hhi": float(risky_norm.pow(2).sum(axis=1).mean()),
                "avg_new_sleeve_share": float(risky_norm.reindex(columns=NEW_PHASEB_SLEEVES, fill_value=0.0).sum(axis=1).mean()),
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
                "avg_new_sleeve_share": float(sub.reindex(columns=NEW_PHASEB_SLEEVES, fill_value=0.0).sum(axis=1).mean()),
            }
        )
    return overall, pd.DataFrame(rows)


def main() -> None:
    base_alloc, state_alloc, sleeve_return_panel, market_state_history, sleeve_positions, benchmark_returns, next_week_returns = load_inputs()
    long_panel, date_panel, market_features, simple_score_panel = build_feature_panels(
        base_alloc,
        state_alloc,
        sleeve_return_panel,
        market_state_history,
    )

    panel_feature_cols = [
        col
        for col in long_panel.columns
        if col
        not in {
            "Date",
            "sleeve",
            "target_return_4w",
            "target_top2",
        }
    ]
    date_feature_cols = [col for col in date_panel.columns if col not in {"Date", "future_spread"}]

    e1 = walkforward_panel_model(
        long_panel,
        feature_cols=panel_feature_cols,
        target_col="target_return_4w",
        is_classifier=False,
    )
    e2 = walkforward_date_model(date_panel, date_feature_cols)
    e3 = walkforward_panel_model(
        long_panel,
        feature_cols=panel_feature_cols,
        target_col="target_top2",
        is_classifier=True,
    )

    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    feature_rows: list[dict[str, float | str]] = []

    for model_name, result in {
        "e1_regressor": e1.feature_importance,
        "e2_concentration": e2.feature_importance,
        "e3_classifier": e3.feature_importance,
    }.items():
        for feature_name, importance in result.head(20).items():
            feature_rows.append(
                {
                    "model_name": model_name,
                    "feature_name": feature_name,
                    "importance": float(importance),
                }
            )

    universe_columns = list(next_week_returns.columns)

    for version_name in PHASE_E_CANDIDATES:
        sleeve_weights = build_candidate_sleeve_weights(
            version_name,
            base_alloc,
            state_alloc,
            e1.prediction_frame,
            e2.prediction_frame,
            e3.prediction_frame,
            simple_score_panel,
            market_features,
        )
        etf_weights = build_lookthrough_weights(sleeve_weights, sleeve_positions, universe_columns)
        path = compute_portfolio_path(etf_weights, next_week_returns.reindex(index=etf_weights.index, columns=etf_weights.columns))

        sleeve_weights.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv")
        etf_weights.to_csv(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")
        path.to_csv(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")

        overall_alloc, state_alloc_summary = sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        overall_conc, state_conc = concentration_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(overall_alloc)
        sleeve_state_rows.append(state_alloc_summary)
        concentration_rows.append(overall_conc)
        concentration_state_rows.append(state_conc)
        state_rows.append(state_summary(path["net_return"], etf_weights, market_state_history, version_name))

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
                "avg_new_sleeve_share": float(
                    sleeve_weights.reindex(columns=NEW_PHASEB_SLEEVES, fill_value=0.0).sum(axis=1).mean()
                ),
            }
        )

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_e_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_e_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_e_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_e_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_e_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_e_concentration_by_state.csv", index=False)
    e1.prediction_frame.to_csv(LAYER3_DIR / "phase_e_e1_predicted_forward_returns.csv")
    e2.prediction_frame.to_csv(LAYER3_DIR / "phase_e_e2_predicted_spread.csv")
    e3.prediction_frame.to_csv(LAYER3_DIR / "phase_e_e3_predicted_top2_prob.csv")
    pd.DataFrame(feature_rows).to_csv(LAYER3_DIR / "phase_e_feature_importance_summary.csv", index=False)

    protocol = {
        "phase": "Phase E",
        "purpose": "Heavier learned allocator / richer model class",
        "candidates": PHASE_E_CANDIDATES,
        "baseline_versions": BASELINE_VERSIONS,
        "constraints": {
            "cash_split_anchor": BASE_VERSION,
            "bounded_state_prior": STATE_MAP_VERSION,
            "horizon_weeks": HORIZON_WEEKS,
            "min_train_weeks": MIN_TRAIN_WEEKS,
            "retrain_frequency_weeks": RETRAIN_FREQUENCY_WEEKS,
            "transaction_cost_bps": DEFAULT_COST_BPS,
        },
    }
    (LAYER3_DIR / "phase_e_allocator_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase E allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_e_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_e_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_e_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_e_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_e_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_e_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_e_feature_importance_summary.csv",
        "data/05_layer3_portfolio_construction/phase_e_allocator_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
