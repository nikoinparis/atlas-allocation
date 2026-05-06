from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler

import phase_h_refined_panel_allocator as ph
import phase_i_refined_allocator_refinement as pi
import phase_j_structural_allocator as pj
import phase_k_allocator_framework as pk


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
CURRENT_LEARNING_BRANCH = "improved_phasel_tail_turnover_learning_allocator"
TAIL_AWARE_BRANCH = "improved_phasek_tail_aware_role_framework"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"
PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"

PHASE_N_CANDIDATES = {
    "improved_phasen_uncertainty_adjusted_allocator": "ML1/ML2 uncertainty-adjusted decision allocator",
    "improved_phasen_distributional_tail_allocator": "ML1/ML2 distributional tail-aware allocator",
    "improved_phasen_moe_role_gating_allocator": "ML3 mixture-of-experts role-gating allocator",
}

EXPERT_NAMES = ["calm", "recovery", "defense"]
HORIZON_WEEKS = 4
MIN_TRAIN_WEEKS = 156
RETRAIN_FREQUENCY_WEEKS = 26
EPS = 1e-9


@dataclass
class RidgeBundle:
    scaler: StandardScaler
    model: Ridge


@dataclass
class SleeveEnsembleResult:
    combined_pred: pd.DataFrame
    ridge_pred: pd.DataFrame
    mean_pred: pd.DataFrame
    lower_pred: pd.DataFrame
    upper_pred: pd.DataFrame
    high_value_prob: pd.DataFrame
    uncertainty: pd.DataFrame
    feature_importance: pd.DataFrame


@dataclass
class DateModelResult:
    combined_pred: pd.DataFrame
    ridge_pred: pd.DataFrame
    mean_pred: pd.DataFrame
    lower_pred: pd.DataFrame
    upper_pred: pd.DataFrame
    feature_importance: pd.DataFrame


@dataclass
class ExpertMoEResult:
    expert_predictions: dict[str, pd.DataFrame]
    gate_probabilities: pd.DataFrame
    gate_detail: pd.DataFrame
    feature_importance: pd.DataFrame


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)
    return clean / total


def pct_rank_0_1(series: pd.Series) -> pd.Series:
    clean = pd.Series(series, dtype=float)
    if clean.dropna().empty:
        return pd.Series(0.0, index=clean.index, dtype=float)
    return clean.rank(pct=True, method="average").fillna(0.0)


def rolling_tail_mean(series: pd.Series, window: int, min_periods: int, quantile: float = 0.20) -> pd.Series:
    def _tail(arr: np.ndarray) -> float:
        clean = arr[np.isfinite(arr)]
        if len(clean) == 0:
            return np.nan
        cutoff = np.quantile(clean, quantile)
        tail = clean[clean <= cutoff]
        return float(tail.mean()) if len(tail) else float(clean.mean())

    return series.rolling(window, min_periods=min_periods).apply(_tail, raw=True)


def rolling_skew(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def _skew(arr: np.ndarray) -> float:
        clean = arr[np.isfinite(arr)]
        if len(clean) < 3:
            return np.nan
        mean = clean.mean()
        std = clean.std(ddof=0)
        if std <= 1e-9:
            return 0.0
        centered = (clean - mean) / std
        return float((centered**3).mean())

    return series.rolling(window, min_periods=min_periods).apply(_skew, raw=True)


def group_future_role_target(utility_panel: pd.DataFrame) -> pd.Series:
    rows: list[pd.Series] = []
    for date, group in utility_panel.groupby("Date", sort=True):
        calm_score = float((group["decision_utility_raw"] * group["role_calm"]).sum())
        recovery_score = float((group["decision_utility_raw"] * group["role_recovery"]).sum())
        defense_mix = 0.65 * group["role_defense"] + 0.35 * group["role_chop"]
        defense_score = float((group["tail_utility_raw"] * defense_mix).sum())
        best = max(
            {"calm": calm_score, "recovery": recovery_score, "defense": defense_score}.items(),
            key=lambda kv: kv[1],
        )[0]
        rows.append(pd.Series({"Date": date, "winning_expert": best}))
    frame = pd.DataFrame(rows)
    return frame.set_index("Date")["winning_expert"].sort_index()


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


def fit_ridge(X: pd.DataFrame, y: pd.Series, *, alpha: float) -> RidgeBundle:
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = Ridge(alpha=alpha)
    model.fit(Xs, y.astype(float))
    return RidgeBundle(scaler=scaler, model=model)


def predict_ridge(bundle: RidgeBundle, X: pd.DataFrame) -> np.ndarray:
    return bundle.model.predict(bundle.scaler.transform(X))


def importance_from_ridge(bundle: RidgeBundle, feature_cols: list[str], model_name: str) -> list[dict[str, float | str]]:
    return [
        {
            "model_name": model_name,
            "feature_name": feature_name,
            "importance": float(abs(coef)),
        }
        for feature_name, coef in zip(feature_cols, bundle.model.coef_)
    ]


def build_enhanced_learning_panels(
    active_returns: pd.DataFrame,
    state_features: pd.DataFrame,
    state_prior: pd.DataFrame,
    reference_weights: pd.DataFrame,
    learning_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
    blend_weights: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    long_panel, date_panel, simple_score_panel = ph.build_feature_panels(active_returns, state_features, state_prior)
    benchmark_returns = ph.read_panel_csv(
        LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv",
        value_col="net_return",
    ).reindex(active_returns.index).fillna(0.0)

    beta_26 = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)
    corr_26 = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)
    tail_13 = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)
    tail_26 = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)
    skew_26 = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)
    downside_freq_26 = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)

    bench_var = benchmark_returns.rolling(26, min_periods=8).var(ddof=0).shift(1).replace(0.0, np.nan)
    for sleeve in ph.ACTIVE_PANEL:
        sleeve_ret = active_returns[sleeve]
        beta_26[sleeve] = sleeve_ret.rolling(26, min_periods=8).cov(benchmark_returns).shift(1).div(bench_var)
        corr_26[sleeve] = sleeve_ret.rolling(26, min_periods=8).corr(benchmark_returns).shift(1)
        tail_13[sleeve] = rolling_tail_mean(sleeve_ret, 13, 8, quantile=0.20).shift(1)
        tail_26[sleeve] = rolling_tail_mean(sleeve_ret, 26, 8, quantile=0.20).shift(1)
        skew_26[sleeve] = rolling_skew(sleeve_ret, 26, 8).shift(1)
        downside_freq_26[sleeve] = (sleeve_ret < 0.0).astype(float).rolling(26, min_periods=8).mean().shift(1)

    ref_risky = reference_weights.reindex(columns=ph.ACTIVE_PANEL).fillna(0.0)
    learn_risky = learning_weights.reindex(columns=ph.ACTIVE_PANEL).fillna(0.0)
    tail_risky = tail_weights.reindex(columns=ph.ACTIVE_PANEL).fillna(0.0)
    blend_risky = blend_weights.reindex(columns=ph.ACTIVE_PANEL).fillna(0.0)

    role_alignment = pd.DataFrame(index=active_returns.index, columns=ph.ACTIVE_PANEL, dtype=float)
    risk_guard = state_features[["stress_confidence", "chop_confidence"]].max(axis=1).fillna(0.0)
    for sleeve in ph.ACTIVE_PANEL:
        role = ph.ROLE_MAP[sleeve]
        role_alignment[sleeve] = (
            role["calm"] * state_features["calm_confidence"]
            + role["recovery"] * state_features["recovery_confidence"]
            + role["chop"] * state_features["chop_confidence"]
            + role["defense"] * state_features["stress_confidence"]
        )

    for sleeve in ph.ACTIVE_PANEL:
        idx = long_panel["sleeve"] == sleeve
        long_panel.loc[idx, "benchmark_beta_26"] = beta_26[sleeve].values
        long_panel.loc[idx, "benchmark_corr_26"] = corr_26[sleeve].values
        long_panel.loc[idx, "tail_mean_13"] = tail_13[sleeve].values
        long_panel.loc[idx, "tail_mean_26"] = tail_26[sleeve].values
        long_panel.loc[idx, "skew_26"] = skew_26[sleeve].values
        long_panel.loc[idx, "downside_freq_26"] = downside_freq_26[sleeve].values
        long_panel.loc[idx, "reference_weight"] = ref_risky[sleeve].values
        long_panel.loc[idx, "learning_weight"] = learn_risky[sleeve].values
        long_panel.loc[idx, "tail_weight"] = tail_risky[sleeve].values
        long_panel.loc[idx, "blend_weight"] = blend_risky[sleeve].values
        long_panel.loc[idx, "reference_weight_change_1w"] = ref_risky[sleeve].diff().fillna(0.0).values
        long_panel.loc[idx, "learning_weight_change_1w"] = learn_risky[sleeve].diff().fillna(0.0).values
        long_panel.loc[idx, "state_role_alignment"] = role_alignment[sleeve].values
        long_panel.loc[idx, "role_guard_penalty"] = (risk_guard * (1.0 - ph.ROLE_MAP[sleeve]["defense"])).values
        long_panel.loc[idx, "simple_score_value"] = simple_score_panel[sleeve].values
        long_panel.loc[idx, "simple_score_rank"] = pct_rank_0_1(simple_score_panel[sleeve]).values
        long_panel.loc[idx, "prior_rank"] = pct_rank_0_1(state_prior[sleeve]).values

    date_panel["reference_hhi"] = ref_risky.pow(2).sum(axis=1)
    date_panel["learning_hhi"] = learn_risky.pow(2).sum(axis=1)
    date_panel["tail_hhi"] = tail_risky.pow(2).sum(axis=1)
    date_panel["reference_top1"] = ref_risky.max(axis=1)
    date_panel["learning_top1"] = learn_risky.max(axis=1)
    date_panel["tail_top1"] = tail_risky.max(axis=1)
    date_panel["reference_learning_gap"] = (ref_risky - learn_risky).abs().sum(axis=1)
    date_panel["reference_tail_gap"] = (ref_risky - tail_risky).abs().sum(axis=1)
    date_panel["blend_reference_gap"] = (blend_risky - ref_risky).abs().sum(axis=1)
    date_panel["market_vol_13"] = benchmark_returns.rolling(13, min_periods=8).std(ddof=0).shift(1)
    date_panel["market_tail_26"] = rolling_tail_mean(benchmark_returns, 26, 8, quantile=0.20).shift(1)
    date_panel["market_skew_26"] = rolling_skew(benchmark_returns, 26, 8).shift(1)

    state_dummies = pd.get_dummies(state_features["state_text"], prefix="state", dtype=float)
    date_panel = date_panel.join(state_dummies, how="left")
    long_panel = long_panel.replace([np.inf, -np.inf], np.nan)
    date_panel = date_panel.replace([np.inf, -np.inf], np.nan)
    return long_panel, date_panel, simple_score_panel


def add_ml_targets(long_panel: pd.DataFrame, date_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = long_panel.copy()
    future = pd.to_numeric(panel["target_return_4w"], errors="coerce")
    neg_future = future.clip(upper=0.0).abs()
    vol = pd.to_numeric(panel["vol_13"], errors="coerce").fillna(panel["vol_13"].median())
    drawdown = pd.to_numeric(panel["dd_13"], errors="coerce").abs().fillna(panel["dd_13"].abs().median())
    tail = pd.to_numeric(panel["tail_mean_13"], errors="coerce").abs().fillna(panel["tail_mean_13"].abs().median())
    risk_guard = pd.concat(
        [
            pd.to_numeric(panel["stress_confidence"], errors="coerce"),
            pd.to_numeric(panel["chop_confidence"], errors="coerce"),
        ],
        axis=1,
    ).max(axis=1).fillna(0.0)
    role_offense = 1.0 - (
        0.58 * pd.to_numeric(panel["role_defense"], errors="coerce").fillna(0.0)
        + 0.32 * pd.to_numeric(panel["role_chop"], errors="coerce").fillna(0.0)
    ).clip(0.0, 1.0)
    prior_support = pd.to_numeric(panel["state_role_alignment"], errors="coerce").fillna(0.0)

    panel["decision_utility_raw"] = (
        future
        - 0.92 * neg_future
        - 0.12 * vol
        - 0.08 * drawdown
        - 0.06 * tail
        - 0.020 * risk_guard * role_offense
        + 0.010 * prior_support
    )
    panel["tail_utility_raw"] = (
        future
        - 1.35 * neg_future
        - 0.18 * vol
        - 0.12 * drawdown
        - 0.18 * tail
        - 0.030 * risk_guard * role_offense
        + 0.006 * prior_support
    )
    panel["high_value_label"] = panel.groupby("Date")["decision_utility_raw"].transform(
        lambda x: (x.rank(pct=True, method="average") >= 0.67).astype(int)
    )
    panel["decision_target"] = panel.groupby("Date")["decision_utility_raw"].transform(
        lambda x: (x.rank(pct=True, method="average") - 0.5) * 2.0
    )
    panel["tail_target"] = panel.groupby("Date")["tail_utility_raw"].transform(
        lambda x: (x.rank(pct=True, method="average") - 0.5) * 2.0
    )

    utility_by_date = panel.pivot(index="Date", columns="sleeve", values="decision_utility_raw")
    tail_by_date = panel.pivot(index="Date", columns="sleeve", values="tail_utility_raw")
    top2 = utility_by_date.apply(lambda row: row.nlargest(2).mean(), axis=1)
    low2 = tail_by_date.apply(lambda row: row.nsmallest(2).mean(), axis=1)
    date_targets = date_panel.copy()
    date_targets["future_utility_spread"] = utility_by_date.max(axis=1) - utility_by_date.median(axis=1)
    date_targets["future_tail_spread"] = tail_by_date.max(axis=1) - tail_by_date.median(axis=1)
    date_targets["future_top2_mean"] = top2
    date_targets["future_worst2_mean"] = low2
    date_targets["winning_expert"] = group_future_role_target(panel)
    return panel.replace([np.inf, -np.inf], np.nan), date_targets.replace([np.inf, -np.inf], np.nan)


def walkforward_sleeve_ensemble(
    panel: pd.DataFrame,
    feature_cols: list[str],
    *,
    target_col: str,
    label_col: str,
    prefix: str,
) -> SleeveEnsembleResult:
    combined_rows: list[pd.Series] = []
    ridge_rows: list[pd.Series] = []
    mean_rows: list[pd.Series] = []
    lower_rows: list[pd.Series] = []
    upper_rows: list[pd.Series] = []
    prob_rows: list[pd.Series] = []
    uncertainty_rows: list[pd.Series] = []
    importance_records: list[dict[str, float | str]] = []

    fitted: dict[str, object] | None = None
    last_fit_date: pd.Timestamp | None = None
    classes_: np.ndarray | None = None

    unique_dates = sorted(pd.Index(panel["Date"].dropna().unique()))
    for date in unique_dates:
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel[target_col].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                X_train = train[feature_cols].fillna(0.0)
                y_train = train[target_col].astype(float)
                y_label = train[label_col].astype(int)

                ridge = fit_ridge(X_train, y_train, alpha=4.0)
                mean_model = GradientBoostingRegressor(
                    n_estimators=100,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.75,
                    random_state=11,
                )
                lower_model = GradientBoostingRegressor(
                    loss="quantile",
                    alpha=0.20,
                    n_estimators=90,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.80,
                    random_state=12,
                )
                upper_model = GradientBoostingRegressor(
                    loss="quantile",
                    alpha=0.80,
                    n_estimators=90,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.80,
                    random_state=13,
                )
                classifier = GradientBoostingClassifier(
                    n_estimators=90,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.80,
                    random_state=14,
                )

                mean_model.fit(X_train, y_train)
                lower_model.fit(X_train, y_train)
                upper_model.fit(X_train, y_train)
                classifier.fit(X_train, y_label)

                fitted = {
                    "ridge": ridge,
                    "mean": mean_model,
                    "lower": lower_model,
                    "upper": upper_model,
                    "classifier": classifier,
                }
                classes_ = getattr(classifier, "classes_", None)
                importance_records.extend(importance_from_ridge(ridge, feature_cols, f"{prefix}_ridge"))
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_mean_gbr",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, mean_model.feature_importances_)
                )
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_lower_q20_gbr",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, lower_model.feature_importances_)
                )
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_upper_q80_gbr",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, upper_model.feature_importances_)
                )
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_high_value_classifier",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, classifier.feature_importances_)
                )
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        if date_rows.empty:
            continue

        ridge_pred = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)
        mean_pred = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)
        lower_pred = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)
        upper_pred = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)
        prob_pred = pd.Series(index=date_rows["sleeve"], dtype=float, name=date)

        if fitted is None:
            ridge_pred.loc[:] = 0.0
            mean_pred.loc[:] = 0.0
            lower_pred.loc[:] = 0.0
            upper_pred.loc[:] = 0.0
            prob_pred.loc[:] = 0.5
        else:
            X_date = date_rows[feature_cols].fillna(0.0)
            ridge_values = predict_ridge(fitted["ridge"], X_date)
            mean_values = fitted["mean"].predict(X_date)
            lower_values = fitted["lower"].predict(X_date)
            upper_values = fitted["upper"].predict(X_date)
            prob_values = fitted["classifier"].predict_proba(X_date)

            ridge_pred.loc[:] = ridge_values
            mean_pred.loc[:] = mean_values
            lower_pred.loc[:] = np.minimum(lower_values, upper_values)
            upper_pred.loc[:] = np.maximum(lower_values, upper_values)
            if classes_ is not None and 1 in classes_:
                class_loc = int(np.where(classes_ == 1)[0][0])
                prob_pred.loc[:] = prob_values[:, class_loc]
            else:
                prob_pred.loc[:] = 0.5

        combined_pred = (0.58 * mean_pred + 0.42 * ridge_pred).rename(date)
        width = (upper_pred - lower_pred).clip(lower=0.0)
        disagreement = (mean_pred - ridge_pred).abs()
        entropy = (
            -(prob_pred.clip(1e-6, 1.0 - 1e-6) * np.log(prob_pred.clip(1e-6, 1.0 - 1e-6))
            + (1.0 - prob_pred.clip(1e-6, 1.0 - 1e-6)) * np.log((1.0 - prob_pred).clip(1e-6, 1.0 - 1e-6)))
            / np.log(2.0)
        )
        uncertainty = (
            0.45 * pct_rank_0_1(width)
            + 0.35 * pct_rank_0_1(disagreement)
            + 0.20 * entropy
        ).clip(0.0, 1.0).rename(date)

        combined_rows.append(combined_pred)
        ridge_rows.append(ridge_pred.reindex(ph.ACTIVE_PANEL))
        mean_rows.append(mean_pred.reindex(ph.ACTIVE_PANEL))
        lower_rows.append(lower_pred.reindex(ph.ACTIVE_PANEL))
        upper_rows.append(upper_pred.reindex(ph.ACTIVE_PANEL))
        prob_rows.append(prob_pred.reindex(ph.ACTIVE_PANEL))
        uncertainty_rows.append(uncertainty.reindex(ph.ACTIVE_PANEL))

    return SleeveEnsembleResult(
        combined_pred=pd.DataFrame(combined_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0),
        ridge_pred=pd.DataFrame(ridge_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0),
        mean_pred=pd.DataFrame(mean_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0),
        lower_pred=pd.DataFrame(lower_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0),
        upper_pred=pd.DataFrame(upper_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0),
        high_value_prob=pd.DataFrame(prob_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.5),
        uncertainty=pd.DataFrame(uncertainty_rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.5),
        feature_importance=feature_importance_frame(importance_records),
    )


def walkforward_date_models(
    panel: pd.DataFrame,
    feature_cols: list[str],
    *,
    target_col: str,
    prefix: str,
) -> DateModelResult:
    combined_rows: list[pd.Series] = []
    ridge_rows: list[pd.Series] = []
    mean_rows: list[pd.Series] = []
    lower_rows: list[pd.Series] = []
    upper_rows: list[pd.Series] = []
    importance_records: list[dict[str, float | str]] = []

    fitted: dict[str, object] | None = None
    last_fit_date: pd.Timestamp | None = None

    unique_dates = sorted(pd.Index(panel["Date"].dropna().unique()))
    for date in unique_dates:
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel[target_col].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS:
                X_train = train[feature_cols].fillna(0.0)
                y_train = train[target_col].astype(float)

                ridge = fit_ridge(X_train, y_train, alpha=3.0)
                mean_model = GradientBoostingRegressor(
                    n_estimators=90,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.80,
                    random_state=21,
                )
                lower_model = GradientBoostingRegressor(
                    loss="quantile",
                    alpha=0.20,
                    n_estimators=80,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.80,
                    random_state=22,
                )
                upper_model = GradientBoostingRegressor(
                    loss="quantile",
                    alpha=0.80,
                    n_estimators=80,
                    learning_rate=0.05,
                    max_depth=2,
                    subsample=0.80,
                    random_state=23,
                )
                mean_model.fit(X_train, y_train)
                lower_model.fit(X_train, y_train)
                upper_model.fit(X_train, y_train)

                fitted = {
                    "ridge": ridge,
                    "mean": mean_model,
                    "lower": lower_model,
                    "upper": upper_model,
                }
                importance_records.extend(importance_from_ridge(ridge, feature_cols, f"{prefix}_ridge"))
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_mean_gbr",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, mean_model.feature_importances_)
                )
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_lower_q20_gbr",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, lower_model.feature_importances_)
                )
                importance_records.extend(
                    {
                        "model_name": f"{prefix}_upper_q80_gbr",
                        "feature_name": feature,
                        "importance": float(value),
                    }
                    for feature, value in zip(feature_cols, upper_model.feature_importances_)
                )
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        if date_rows.empty:
            continue
        column_name = target_col.replace("future_", "predicted_")

        if fitted is None:
            ridge_value = mean_value = lower_value = upper_value = 0.0
        else:
            X_date = date_rows[feature_cols].fillna(0.0)
            ridge_value = float(predict_ridge(fitted["ridge"], X_date)[0])
            mean_value = float(fitted["mean"].predict(X_date)[0])
            low = float(fitted["lower"].predict(X_date)[0])
            high = float(fitted["upper"].predict(X_date)[0])
            lower_value, upper_value = min(low, high), max(low, high)

        combined_value = 0.58 * mean_value + 0.42 * ridge_value
        combined_rows.append(pd.Series({column_name: combined_value}, name=date))
        ridge_rows.append(pd.Series({column_name: ridge_value}, name=date))
        mean_rows.append(pd.Series({column_name: mean_value}, name=date))
        lower_rows.append(pd.Series({column_name: lower_value}, name=date))
        upper_rows.append(pd.Series({column_name: upper_value}, name=date))

    return DateModelResult(
        combined_pred=pd.DataFrame(combined_rows).sort_index().fillna(0.0),
        ridge_pred=pd.DataFrame(ridge_rows).sort_index().fillna(0.0),
        mean_pred=pd.DataFrame(mean_rows).sort_index().fillna(0.0),
        lower_pred=pd.DataFrame(lower_rows).sort_index().fillna(0.0),
        upper_pred=pd.DataFrame(upper_rows).sort_index().fillna(0.0),
        feature_importance=feature_importance_frame(importance_records),
    )


def walkforward_expert_moe(
    panel: pd.DataFrame,
    date_panel: pd.DataFrame,
    feature_cols: list[str],
    date_feature_cols: list[str],
    *,
    target_col: str,
) -> ExpertMoEResult:
    expert_pred_rows = {name: [] for name in EXPERT_NAMES}
    gate_prob_rows: list[pd.Series] = []
    gate_detail_rows: list[pd.Series] = []
    importance_records: list[dict[str, float | str]] = []

    fitted_experts: dict[str, RidgeBundle] | None = None
    fitted_gate: tuple[StandardScaler, LogisticRegression] | None = None
    last_fit_date: pd.Timestamp | None = None
    gate_classes: np.ndarray | None = None

    unique_dates = sorted(pd.Index(panel["Date"].dropna().unique()))
    for date in unique_dates:
        train_cutoff = date - pd.Timedelta(weeks=HORIZON_WEEKS)
        if last_fit_date is None or (date - last_fit_date).days >= 7 * RETRAIN_FREQUENCY_WEEKS:
            train = panel[(panel["Date"] <= train_cutoff) & panel[target_col].notna()].copy()
            train_date = date_panel[(date_panel["Date"] <= train_cutoff) & date_panel["winning_expert"].notna()].copy()
            if train["Date"].nunique() >= MIN_TRAIN_WEEKS and train_date["Date"].nunique() >= MIN_TRAIN_WEEKS:
                X_train = train[feature_cols].fillna(0.0)
                y_train = train[target_col].astype(float)
                fitted_experts = {}
                for expert_name in EXPERT_NAMES:
                    weight_col = f"expert_weight_{expert_name}"
                    weights = train[weight_col].fillna(0.0).clip(lower=0.05)
                    scaler = StandardScaler()
                    Xs = scaler.fit_transform(X_train)
                    model = Ridge(alpha=5.0)
                    model.fit(Xs, y_train, sample_weight=weights)
                    bundle = RidgeBundle(scaler=scaler, model=model)
                    fitted_experts[expert_name] = bundle
                    importance_records.extend(importance_from_ridge(bundle, feature_cols, f"moe_{expert_name}_expert"))

                X_gate = train_date[date_feature_cols].fillna(0.0)
                y_gate = train_date["winning_expert"].astype(str)
                gate_scaler = StandardScaler()
                Xg = gate_scaler.fit_transform(X_gate)
                gate_model = LogisticRegression(
                    C=0.75,
                    max_iter=2000,
                )
                gate_model.fit(Xg, y_gate)
                fitted_gate = (gate_scaler, gate_model)
                gate_classes = gate_model.classes_
                for class_loc, class_name in enumerate(gate_model.classes_):
                    for feature_name, coef in zip(date_feature_cols, gate_model.coef_[class_loc]):
                        importance_records.append(
                            {
                                "model_name": f"moe_gate_{class_name}",
                                "feature_name": feature_name,
                                "importance": float(abs(coef)),
                            }
                        )
                last_fit_date = date

        date_rows = panel[panel["Date"] == date].copy()
        date_meta = date_panel[date_panel["Date"] == date].copy()
        if date_rows.empty or date_meta.empty:
            continue

        if fitted_experts is None:
            for expert_name in EXPERT_NAMES:
                expert_pred_rows[expert_name].append(pd.Series(0.0, index=ph.ACTIVE_PANEL, name=date))
        else:
            X_date = date_rows[feature_cols].fillna(0.0)
            for expert_name in EXPERT_NAMES:
                bundle = fitted_experts[expert_name]
                pred = pd.Series(
                    predict_ridge(bundle, X_date),
                    index=date_rows["sleeve"],
                    name=date,
                ).reindex(ph.ACTIVE_PANEL).fillna(0.0)
                expert_pred_rows[expert_name].append(pred)

        fallback_probs = pd.Series(
            {
                "calm": float(state_value(date_meta.iloc[0], "calm_confidence")),
                "recovery": float(state_value(date_meta.iloc[0], "recovery_confidence")),
                "defense": float(
                    max(
                        state_value(date_meta.iloc[0], "stress_confidence"),
                        state_value(date_meta.iloc[0], "chop_confidence"),
                    )
                ),
            },
            name=date,
            dtype=float,
        )
        fallback_probs = fallback_probs.clip(lower=0.01)
        fallback_probs = fallback_probs / float(fallback_probs.sum())

        if fitted_gate is None or gate_classes is None:
            gate_prob = fallback_probs
        else:
            gate_scaler, gate_model = fitted_gate
            X_gate_date = date_meta[date_feature_cols].fillna(0.0)
            raw_probs = gate_model.predict_proba(gate_scaler.transform(X_gate_date))[0]
            gate_prob = pd.Series(0.0, index=EXPERT_NAMES, dtype=float, name=date)
            for class_name, value in zip(gate_classes, raw_probs):
                gate_prob[str(class_name)] = float(value)
            gate_prob = 0.70 * gate_prob + 0.30 * fallback_probs
            gate_prob = gate_prob.clip(lower=0.01)
            gate_prob = gate_prob / float(gate_prob.sum())

        gate_prob_rows.append(gate_prob)
        gate_entropy = float(
            -(gate_prob * np.log(gate_prob.clip(lower=1e-6))).sum() / np.log(len(EXPERT_NAMES))
        )
        gate_detail_rows.append(
            pd.Series(
                {
                    "top_expert": str(gate_prob.idxmax()),
                    "top_expert_prob": float(gate_prob.max()),
                    "gate_entropy": gate_entropy,
                },
                name=date,
            )
        )

    return ExpertMoEResult(
        expert_predictions={
            name: pd.DataFrame(rows).reindex(columns=ph.ACTIVE_PANEL).sort_index().fillna(0.0)
            for name, rows in expert_pred_rows.items()
        },
        gate_probabilities=pd.DataFrame(gate_prob_rows).reindex(columns=EXPERT_NAMES).sort_index().fillna(1.0 / len(EXPERT_NAMES)),
        gate_detail=pd.DataFrame(gate_detail_rows).sort_index(),
        feature_importance=feature_importance_frame(importance_records),
    )


def state_value(row: pd.Series, column: str) -> float:
    value = row.get(column, 0.0)
    return 0.0 if pd.isna(value) else float(value)


def prediction_rank_signal(
    decision_result: SleeveEnsembleResult,
    tail_result: SleeveEnsembleResult,
    state_prior: pd.DataFrame,
    reference_weights: pd.DataFrame,
    learning_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
    moe_result: ExpertMoEResult,
    date: pd.Timestamp,
    candidate_name: str,
) -> pd.Series:
    opportunity_rank = ph.centered_rank(decision_result.combined_pred.loc[date, ph.ACTIVE_PANEL])
    conservative_rank = ph.centered_rank(decision_result.lower_pred.loc[date, ph.ACTIVE_PANEL])
    classifier_rank = ph.centered_rank(decision_result.high_value_prob.loc[date, ph.ACTIVE_PANEL])
    tail_rank = ph.centered_rank(tail_result.combined_pred.loc[date, ph.ACTIVE_PANEL])
    tail_conservative_rank = ph.centered_rank(tail_result.lower_pred.loc[date, ph.ACTIVE_PANEL])
    certainty_rank = ph.centered_rank(1.0 - decision_result.uncertainty.loc[date, ph.ACTIVE_PANEL])
    prior_rank = ph.centered_rank(state_prior.loc[date, ph.ACTIVE_PANEL])
    ref_rank = ph.centered_rank(reference_weights.loc[date, ph.ACTIVE_PANEL])
    learning_rank = ph.centered_rank(learning_weights.loc[date, ph.ACTIVE_PANEL])
    tail_ref_rank = ph.centered_rank(tail_weights.loc[date, ph.ACTIVE_PANEL])

    if candidate_name == "improved_phasen_uncertainty_adjusted_allocator":
        signal = (
            0.34 * opportunity_rank
            + 0.18 * conservative_rank
            + 0.14 * classifier_rank
            + 0.12 * certainty_rank
            + 0.10 * prior_rank
            + 0.07 * ref_rank
            + 0.05 * learning_rank
        )
    elif candidate_name == "improved_phasen_distributional_tail_allocator":
        signal = (
            0.28 * conservative_rank
            + 0.22 * tail_rank
            + 0.16 * opportunity_rank
            + 0.10 * tail_conservative_rank
            + 0.10 * certainty_rank
            + 0.08 * tail_ref_rank
            + 0.06 * prior_rank
        )
    elif candidate_name == "improved_phasen_moe_role_gating_allocator":
        gate = moe_result.gate_probabilities.loc[date, EXPERT_NAMES]
        expert_combo = (
            gate["calm"] * ph.centered_rank(moe_result.expert_predictions["calm"].loc[date, ph.ACTIVE_PANEL])
            + gate["recovery"] * ph.centered_rank(moe_result.expert_predictions["recovery"].loc[date, ph.ACTIVE_PANEL])
            + gate["defense"] * ph.centered_rank(moe_result.expert_predictions["defense"].loc[date, ph.ACTIVE_PANEL])
        )
        signal = (
            0.42 * ph.centered_rank(expert_combo)
            + 0.18 * opportunity_rank
            + 0.12 * conservative_rank
            + 0.10 * classifier_rank
            + 0.08 * certainty_rank
            + 0.06 * learning_rank
            + 0.04 * prior_rank
        )
    else:
        raise ValueError(candidate_name)
    return signal.fillna(0.0)


def candidate_context(
    candidate_name: str,
    date: pd.Timestamp,
    signal: pd.Series,
    meta: pd.DataFrame,
    decision_result: SleeveEnsembleResult,
    spread_result: DateModelResult,
    moe_result: ExpertMoEResult,
) -> tuple[float, float, float]:
    margin_conf = float(meta.loc[date, "margin_confidence"])
    agreement = float(meta.loc[date, "agreement"])
    signal_gap = pj.top_margin(signal)

    signal_focus = (signal - float(signal.min()) + EPS).clip(lower=0.0)
    signal_focus = signal_focus / float(signal_focus.sum()) if float(signal_focus.sum()) > 0 else pd.Series(
        1.0 / len(signal), index=signal.index
    )
    sleeve_uncertainty = decision_result.uncertainty.loc[date, ph.ACTIVE_PANEL].fillna(0.5)
    focus_uncertainty = float((signal_focus.reindex(ph.ACTIVE_PANEL) * sleeve_uncertainty).sum())

    spread_col = "predicted_utility_spread"
    spread_mean = float(spread_result.combined_pred.reindex([date]).fillna(0.0).iloc[0].get(spread_col, 0.0))
    spread_low = float(spread_result.lower_pred.reindex([date]).fillna(0.0).iloc[0].get(spread_col, 0.0))
    spread_high = float(spread_result.upper_pred.reindex([date]).fillna(0.0).iloc[0].get(spread_col, 0.0))
    spread_score = float(np.clip((spread_mean - 0.004) / 0.040, 0.0, 1.0))
    spread_uncertainty = float(np.clip((spread_high - spread_low) / 0.070, 0.0, 1.0))

    confidence = (
        0.28 * ph.bounded_zero_to_one(signal_gap, 0.03, 0.75)
        + 0.24 * margin_conf
        + 0.16 * agreement
        + 0.20 * spread_score
        + 0.12 * (1.0 - spread_uncertainty)
        - 0.28 * focus_uncertainty
    )

    if candidate_name == "improved_phasen_moe_role_gating_allocator":
        top_prob = float(moe_result.gate_detail.loc[date, "top_expert_prob"])
        gate_entropy = float(moe_result.gate_detail.loc[date, "gate_entropy"])
        confidence += 0.14 * top_prob - 0.08 * gate_entropy
    elif candidate_name == "improved_phasen_distributional_tail_allocator":
        confidence -= 0.05 * spread_uncertainty

    confidence = float(np.clip(confidence, 0.0, 1.0))
    total_uncertainty = float(np.clip(0.60 * focus_uncertainty + 0.40 * spread_uncertainty, 0.0, 1.0))
    return confidence, total_uncertainty, spread_score


def candidate_bounds(
    candidate_name: str,
    st: pd.Series,
    margin_conf: float,
    agreement: float,
    confidence: float,
    total_uncertainty: float,
    moe_result: ExpertMoEResult | None = None,
    date: pd.Timestamp | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    floors, caps = pj.dynamic_bounds(st, margin_conf, agreement)
    floors = dict(floors)
    caps = dict(caps)
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))

    if total_uncertainty > 0.58:
        for sleeve in ph.ACTIVE_PANEL:
            caps[sleeve] = min(caps.get(sleeve, 1.0), 0.24 if candidate_name == "improved_phasen_distributional_tail_allocator" else 0.26)
    elif confidence > 0.72 and total_uncertainty < 0.35 and risk_guard < 0.34:
        if st["calm_confidence"] >= max(st["recovery_confidence"], st["stress_confidence"], st["chop_confidence"]):
            caps["composite_calm_trend_specialist"] = min(0.46, max(caps.get("composite_calm_trend_specialist", 0.36), 0.42))
            caps["taa_10m_sma"] = min(0.42, max(caps.get("taa_10m_sma", 0.36), 0.38))
        if st["recovery_confidence"] >= max(st["calm_confidence"], st["stress_confidence"], st["chop_confidence"]):
            caps["composite_healthier_recovery_specialist"] = min(0.46, max(caps.get("composite_healthier_recovery_specialist", 0.36), 0.42))
            caps["dual_momentum_topn"] = min(0.30, max(caps.get("dual_momentum_topn", 0.36), 0.24))

    if candidate_name == "improved_phasen_distributional_tail_allocator":
        floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.10 + 0.08 * risk_guard)
        floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.08 + 0.08 * float(st["chop_confidence"]))
        if risk_guard > 0.42 or total_uncertainty > 0.50:
            caps["dual_momentum_topn"] = min(caps.get("dual_momentum_topn", 1.0), 0.12)
            caps["composite_calm_trend_specialist"] = min(caps.get("composite_calm_trend_specialist", 1.0), 0.22)
            caps["composite_healthier_recovery_specialist"] = min(caps.get("composite_healthier_recovery_specialist", 1.0), 0.20)

    if candidate_name == "improved_phasen_moe_role_gating_allocator" and moe_result is not None and date is not None:
        gate = moe_result.gate_probabilities.loc[date, EXPERT_NAMES]
        if float(gate["calm"]) > 0.55 and total_uncertainty < 0.38:
            caps["composite_calm_trend_specialist"] = min(0.48, max(caps.get("composite_calm_trend_specialist", 0.36), 0.43))
            caps["taa_10m_sma"] = min(0.44, max(caps.get("taa_10m_sma", 0.36), 0.39))
        if float(gate["recovery"]) > 0.55 and total_uncertainty < 0.40:
            caps["composite_healthier_recovery_specialist"] = min(0.48, max(caps.get("composite_healthier_recovery_specialist", 0.36), 0.43))
            caps["dual_momentum_topn"] = min(0.30, max(caps.get("dual_momentum_topn", 0.36), 0.24))
        if float(gate["defense"]) > 0.50 or risk_guard > 0.40:
            floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.12 + 0.06 * float(gate["defense"]))
            floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.10 + 0.06 * float(gate["defense"]))
            caps["dual_momentum_topn"] = min(caps.get("dual_momentum_topn", 1.0), 0.14)

    return floors, caps


def build_candidate_weights(
    candidate_name: str,
    state_features: pd.DataFrame,
    state_prior: pd.DataFrame,
    decision_result: SleeveEnsembleResult,
    tail_result: SleeveEnsembleResult,
    spread_result: DateModelResult,
    reference_weights: pd.DataFrame,
    learning_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
    meta: pd.DataFrame,
    cov_map: dict[pd.Timestamp, pd.DataFrame],
    down_cov_map: dict[pd.Timestamp, pd.DataFrame],
    tail_map: dict[pd.Timestamp, pd.Series],
    moe_result: ExpertMoEResult,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.Series] = []
    control_rows: list[pd.Series] = []
    prev_risky: pd.Series | None = None

    for date in reference_weights.index:
        st = state_features.loc[date]
        margin_conf = float(meta.loc[date, "margin_confidence"])
        agreement = float(meta.loc[date, "agreement"])
        risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))

        ref = normalize(reference_weights.loc[date, ph.ACTIVE_PANEL])
        learn = normalize(learning_weights.loc[date, ph.ACTIVE_PANEL])
        tail_ref = normalize(tail_weights.loc[date, ph.ACTIVE_PANEL])
        prev = ref.copy() if prev_risky is None else prev_risky.copy()

        signal = prediction_rank_signal(
            decision_result,
            tail_result,
            state_prior,
            reference_weights,
            learning_weights,
            tail_weights,
            moe_result,
            date,
            candidate_name,
        )
        confidence, total_uncertainty, spread_score = candidate_context(
            candidate_name,
            date,
            signal,
            meta,
            decision_result,
            spread_result,
            moe_result,
        )
        floors, caps = candidate_bounds(
            candidate_name,
            st,
            margin_conf,
            agreement,
            confidence,
            total_uncertainty,
            moe_result=moe_result,
            date=date,
        )
        role_penalty = pj.risk_penalty_vector(st)

        if candidate_name == "improved_phasen_uncertainty_adjusted_allocator":
            safe_mix = min(0.06 + 0.16 * risk_guard + 0.16 * total_uncertainty + 0.06 * (1.0 - confidence), 0.26)
            anchor = normalize((1.0 - safe_mix) * (0.58 * ref + 0.24 * learn + 0.18 * tail_ref) + safe_mix * pi.SAFE_ANCHOR)
            cash_weight = float(np.clip(0.015 + 0.10 * risk_guard + 0.06 * total_uncertainty - 0.03 * confidence, 0.0, 0.10))
            mu_scale = 0.94 * (0.24 + 0.92 * confidence) * (1.0 - 0.18 * total_uncertainty)
            lambda_var = 1.02 * (1.0 + 0.22 * risk_guard + 0.08 * total_uncertainty)
            lambda_down = 0.84 * (1.0 + 0.30 * risk_guard + 0.12 * total_uncertainty)
            lambda_tail = 0.78 * (1.0 + 0.44 * risk_guard + 0.18 * total_uncertainty)
            lambda_turn = 0.90 * (1.12 - 0.48 * confidence + 0.30 * total_uncertainty)
            lambda_anchor = 0.76 * (1.04 - 0.18 * confidence + 0.12 * total_uncertainty)
            lambda_hhi = 0.26 * (1.10 - 0.38 * confidence + 0.24 * total_uncertainty)
        elif candidate_name == "improved_phasen_distributional_tail_allocator":
            safe_mix = min(0.08 + 0.22 * risk_guard + 0.18 * total_uncertainty + 0.08 * (1.0 - confidence), 0.34)
            anchor = normalize((1.0 - safe_mix) * (0.46 * ref + 0.24 * learn + 0.30 * tail_ref) + safe_mix * pi.SAFE_ANCHOR)
            cash_weight = float(np.clip(0.025 + 0.14 * risk_guard + 0.10 * total_uncertainty - 0.05 * confidence, 0.0, 0.16))
            mu_scale = 0.86 * (0.22 + 0.80 * confidence) * (1.0 - 0.24 * total_uncertainty)
            lambda_var = 1.14 * (1.0 + 0.28 * risk_guard + 0.12 * total_uncertainty)
            lambda_down = 1.00 * (1.0 + 0.45 * risk_guard + 0.18 * total_uncertainty)
            lambda_tail = 1.00 * (1.10 + 0.62 * risk_guard + 0.24 * total_uncertainty)
            lambda_turn = 1.02 * (1.12 - 0.34 * confidence + 0.32 * total_uncertainty)
            lambda_anchor = 0.84 * (1.10 - 0.14 * confidence + 0.14 * total_uncertainty)
            lambda_hhi = 0.32 * (1.08 - 0.26 * confidence + 0.18 * total_uncertainty)
        elif candidate_name == "improved_phasen_moe_role_gating_allocator":
            gate_top_prob = float(moe_result.gate_detail.loc[date, "top_expert_prob"])
            safe_mix = min(0.05 + 0.14 * risk_guard + 0.14 * total_uncertainty + 0.10 * (1.0 - gate_top_prob), 0.24)
            anchor = normalize((1.0 - safe_mix) * (0.54 * ref + 0.28 * learn + 0.18 * tail_ref) + safe_mix * pi.SAFE_ANCHOR)
            cash_weight = float(np.clip(0.010 + 0.08 * risk_guard + 0.05 * total_uncertainty - 0.04 * confidence, 0.0, 0.08))
            mu_scale = 0.98 * (0.28 + 1.02 * confidence) * (1.0 - 0.14 * total_uncertainty)
            lambda_var = 0.98 * (1.0 + 0.20 * risk_guard + 0.06 * total_uncertainty)
            lambda_down = 0.78 * (1.0 + 0.26 * risk_guard + 0.10 * total_uncertainty)
            lambda_tail = 0.72 * (1.0 + 0.36 * risk_guard + 0.12 * total_uncertainty)
            lambda_turn = 0.80 * (1.06 - 0.46 * confidence + 0.22 * total_uncertainty)
            lambda_anchor = 0.72 * (1.02 - 0.20 * confidence + 0.10 * total_uncertainty)
            lambda_hhi = 0.22 * (1.06 - 0.42 * confidence + 0.20 * total_uncertainty)
        else:
            raise ValueError(candidate_name)

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
        row.loc[ph.ACTIVE_PANEL] = (1.0 - cash_weight) * risky
        row.loc[ph.CASH_COLUMN] = cash_weight
        rows.append(row)
        control_rows.append(
            pd.Series(
                {
                    "model_confidence": confidence,
                    "model_uncertainty": total_uncertainty,
                    "spread_score": spread_score,
                    "margin_confidence": margin_conf,
                    "agreement": agreement,
                    "signal_top_gap": pj.top_margin(signal),
                    "risk_guard": risk_guard,
                    "cash_weight": cash_weight,
                    "mu_scale": mu_scale,
                    "lambda_turn": lambda_turn,
                    "lambda_tail": lambda_tail,
                    "gate_top_expert": moe_result.gate_detail.loc[date, "top_expert"],
                    "gate_top_prob": moe_result.gate_detail.loc[date, "top_expert_prob"],
                    "gate_entropy": moe_result.gate_detail.loc[date, "gate_entropy"],
                    "gate_prob_calm": moe_result.gate_probabilities.loc[date, "calm"],
                    "gate_prob_recovery": moe_result.gate_probabilities.loc[date, "recovery"],
                    "gate_prob_defense": moe_result.gate_probabilities.loc[date, "defense"],
                },
                name=date,
            )
        )
        prev_risky = normalize(row.loc[ph.ACTIVE_PANEL])

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(control_rows).sort_index()


def uncertainty_summary(version_name: str, controls: pd.DataFrame, sleeve_weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risky = sleeve_weights[ph.ACTIVE_PANEL]
    risky_norm = risky.div(risky.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    merged = controls.copy()
    merged["top1_share"] = risky_norm.max(axis=1)
    merged["top2_share"] = pd.Series(np.sort(risky_norm.to_numpy(), axis=1)[:, -2:].sum(axis=1), index=risky_norm.index)
    merged["hhi"] = risky_norm.pow(2).sum(axis=1)
    merged["confidence_bucket"] = pd.cut(
        merged["model_confidence"],
        bins=[-1e-9, 0.33, 0.66, 1.0],
        labels=["low", "medium", "high"],
    )
    merged["uncertainty_bucket"] = pd.cut(
        merged["model_uncertainty"],
        bins=[-1e-9, 0.33, 0.66, 1.0],
        labels=["low", "medium", "high"],
    )

    overall = pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_model_confidence": float(merged["model_confidence"].mean()),
                "avg_model_uncertainty": float(merged["model_uncertainty"].mean()),
                "avg_cash_weight": float(merged["cash_weight"].mean()),
                "avg_top1_share": float(merged["top1_share"].mean()),
                "avg_top2_share": float(merged["top2_share"].mean()),
                "avg_hhi": float(merged["hhi"].mean()),
                "avg_gate_top_prob": float(merged["gate_top_prob"].mean()),
            }
        ]
    )

    bucket_rows: list[dict[str, float | str | int]] = []
    grouped = merged.groupby(["confidence_bucket", "uncertainty_bucket"], observed=False)
    for (conf_bucket, unc_bucket), group in grouped:
        if group.empty:
            continue
        bucket_rows.append(
            {
                "version_name": version_name,
                "confidence_bucket": str(conf_bucket),
                "uncertainty_bucket": str(unc_bucket),
                "observations": int(len(group)),
                "avg_model_confidence": float(group["model_confidence"].mean()),
                "avg_model_uncertainty": float(group["model_uncertainty"].mean()),
                "avg_cash_weight": float(group["cash_weight"].mean()),
                "avg_top1_share": float(group["top1_share"].mean()),
                "avg_top2_share": float(group["top2_share"].mean()),
                "avg_hhi": float(group["hhi"].mean()),
            }
        )
    return overall, pd.DataFrame(bucket_rows)


def gate_summary(version_name: str, controls: pd.DataFrame, market_state_history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall = pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_gate_prob_calm": float(controls["gate_prob_calm"].mean()),
                "avg_gate_prob_recovery": float(controls["gate_prob_recovery"].mean()),
                "avg_gate_prob_defense": float(controls["gate_prob_defense"].mean()),
                "avg_gate_entropy": float(controls["gate_entropy"].mean()),
                "top_expert_share_calm": float((controls["gate_top_expert"] == "calm").mean()),
                "top_expert_share_recovery": float((controls["gate_top_expert"] == "recovery").mean()),
                "top_expert_share_defense": float((controls["gate_top_expert"] == "defense").mean()),
            }
        ]
    )
    joined = controls.join(market_state_history["market_state"], how="left")
    rows: list[dict[str, float | str]] = []
    for state, group in joined.groupby("market_state", observed=False):
        rows.append(
            {
                "version_name": version_name,
                "market_state": str(state),
                "avg_gate_prob_calm": float(group["gate_prob_calm"].mean()),
                "avg_gate_prob_recovery": float(group["gate_prob_recovery"].mean()),
                "avg_gate_prob_defense": float(group["gate_prob_defense"].mean()),
                "top_expert": str(group["gate_top_expert"].mode().iloc[0]) if not group["gate_top_expert"].mode().empty else "unknown",
            }
        )
    return overall, pd.DataFrame(rows)


def main() -> None:
    next_week_returns, active_returns, active_positions, _, market_state_history = ph.load_inputs()
    state_features = ph.state_feature_frame(active_returns.index, market_state_history)
    state_prior = ph.role_alignment_score(state_features)

    reference_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv").reindex(state_prior.index).fillna(0.0)
    learning_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_LEARNING_BRANCH}.csv").reindex(state_prior.index).fillna(0.0)
    tail_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{TAIL_AWARE_BRANCH}.csv").reindex(state_prior.index).fillna(0.0)
    blend_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{ACTIVE_PANEL_BASELINE}.csv").reindex(state_prior.index).fillna(0.0)

    long_panel, date_panel, simple_score_panel = build_enhanced_learning_panels(
        active_returns,
        state_features,
        state_prior,
        reference_weights,
        learning_weights,
        tail_weights,
        blend_weights,
    )
    long_panel, date_panel = add_ml_targets(long_panel, date_panel)

    panel_feature_cols = [
        col
        for col in long_panel.columns
        if col
        not in {
            "Date",
            "sleeve",
            "target_return_4w",
            "decision_utility_raw",
            "tail_utility_raw",
            "decision_target",
            "tail_target",
            "high_value_label",
        }
    ]
    date_feature_cols = [
        col
        for col in date_panel.columns
        if col not in {"Date", "future_utility_spread", "future_tail_spread", "future_top2_mean", "future_worst2_mean", "winning_expert"}
    ]

    decision_result = walkforward_sleeve_ensemble(
        long_panel,
        panel_feature_cols,
        target_col="decision_target",
        label_col="high_value_label",
        prefix="decision",
    )
    tail_result = walkforward_sleeve_ensemble(
        long_panel,
        panel_feature_cols,
        target_col="tail_target",
        label_col="high_value_label",
        prefix="tail",
    )
    spread_result = walkforward_date_models(
        date_panel,
        date_feature_cols,
        target_col="future_utility_spread",
        prefix="utility_spread",
    )
    _, meta = pk.build_margin_meta(
        state_prior,
        simple_score_panel,
        decision_result.combined_pred,
        reference_weights,
        state_features,
    )
    meta = meta.reindex(state_prior.index).fillna(0.0)

    long_panel["expert_weight_calm"] = 0.05 + long_panel["role_calm"] * long_panel["calm_confidence"] + 0.08 * long_panel["market_trend_positive"]
    long_panel["expert_weight_recovery"] = 0.05 + long_panel["role_recovery"] * long_panel["recovery_confidence"] + 0.06 * long_panel["transition_good_state_prob"]
    long_panel["expert_weight_defense"] = 0.05 + (
        0.65 * long_panel["role_defense"] + 0.35 * long_panel["role_chop"]
    ) * pd.concat([long_panel["stress_confidence"], long_panel["chop_confidence"]], axis=1).max(axis=1)

    moe_result = walkforward_expert_moe(
        long_panel,
        date_panel,
        panel_feature_cols,
        date_feature_cols,
        target_col="decision_target",
    )
    cov_map, down_cov_map, tail_map = pk.risk_maps(active_returns)

    universe_columns = list(next_week_returns.columns)
    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    uncertainty_rows: list[pd.DataFrame] = []
    uncertainty_bucket_rows: list[pd.DataFrame] = []
    gate_rows: list[pd.DataFrame] = []
    gate_state_rows: list[pd.DataFrame] = []

    for version_name in PHASE_N_CANDIDATES:
        sleeve_weights, controls = build_candidate_weights(
            version_name,
            state_features,
            state_prior,
            decision_result,
            tail_result,
            spread_result,
            reference_weights,
            learning_weights,
            tail_weights,
            meta,
            cov_map,
            down_cov_map,
            tail_map,
            moe_result,
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
        uncert_summary, uncert_buckets = uncertainty_summary(version_name, controls, sleeve_weights)
        uncertainty_rows.append(uncert_summary)
        uncertainty_bucket_rows.append(uncert_buckets)
        gate_summary_overall, gate_summary_state = gate_summary(version_name, controls, market_state_history)
        gate_rows.append(gate_summary_overall)
        gate_state_rows.append(gate_summary_state)
        controls.to_csv(LAYER3_DIR / f"phase_n_controls_{version_name}.csv")

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
                    sleeve_weights[
                        [
                            "composite_calm_trend_specialist",
                            "composite_healthier_recovery_specialist",
                            "composite_anti_chop_clarity",
                        ]
                    ].sum(axis=1).mean()
                ),
            }
        )

    importance = pd.concat(
        [
            decision_result.feature_importance,
            tail_result.feature_importance,
            spread_result.feature_importance,
            moe_result.feature_importance,
        ],
        ignore_index=True,
    )

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_n_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_concentration_by_state.csv", index=False)
    pd.concat(uncertainty_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_uncertainty_summary.csv", index=False)
    pd.concat(uncertainty_bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_uncertainty_by_bucket.csv", index=False)
    pd.concat(gate_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_gate_summary.csv", index=False)
    pd.concat(gate_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_n_gate_by_state.csv", index=False)
    importance.to_csv(LAYER3_DIR / "phase_n_feature_importance_summary.csv", index=False)
    decision_result.combined_pred.to_csv(LAYER3_DIR / "phase_n_decision_predictions.csv")
    tail_result.combined_pred.to_csv(LAYER3_DIR / "phase_n_tail_predictions.csv")
    decision_result.uncertainty.to_csv(LAYER3_DIR / "phase_n_prediction_uncertainty.csv")
    moe_result.gate_probabilities.to_csv(LAYER3_DIR / "phase_n_gate_probabilities.csv")

    protocol = {
        "phase": "Phase N",
        "purpose": "Ambitious ML phase: decision-aware, uncertainty-aware multi-sleeve allocator",
        "reference_panel_version": "improved_phaseh_reference_core_blend",
        "active_panel_version": ACTIVE_PANEL_BASELINE,
        "current_refined_allocator_reference": CURRENT_REFINED_REFERENCE,
        "current_learning_branch": CURRENT_LEARNING_BRANCH,
        "current_tail_aware_branch": TAIL_AWARE_BRANCH,
        "candidate_versions": PHASE_N_CANDIDATES,
        "training_design": {
            "label_horizon_weeks": HORIZON_WEEKS,
            "walk_forward_min_train_weeks": MIN_TRAIN_WEEKS,
            "retrain_frequency_weeks": RETRAIN_FREQUENCY_WEEKS,
            "label_purging": "train cut-off is current date minus 4 weeks to avoid overlap with forward 4-week labels",
            "decision_target": "cross-sectionally ranked forward sleeve utility penalized for downside, realized volatility, drawdown, tail mean, and fragile offensive exposure",
            "tail_target": "more conservative utility with heavier left-tail penalties",
            "uncertainty_model": "quantile interval width + model disagreement + classifier entropy",
            "moe_design": "three linear experts (calm, recovery, defense) blended by a learned multinomial gate on date-level features",
        },
    }
    (LAYER3_DIR / "phase_n_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase N ambitious ML allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_n_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_n_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_n_uncertainty_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_uncertainty_by_bucket.csv",
        "data/05_layer3_portfolio_construction/phase_n_gate_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_gate_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_n_feature_importance_summary.csv",
        "data/05_layer3_portfolio_construction/phase_n_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
