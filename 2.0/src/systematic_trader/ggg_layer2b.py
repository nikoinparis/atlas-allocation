"""Portable GGG Layer 2b state engine and embargoed meta models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from systematic_trader.ggg_layer2a import BROAD_RISK, RESEARCH_UNIVERSE

CANARIES = ["VWO", "HYG", "VNQ", "EFA", "PDBC"]
FEATURES = [
    "market_drawdown", "market_trend_positive", "breadth_sma_43", "breadth_26w_mom",
    "breadth_13w_mom", "breadth_change_4w", "canary_breadth_default",
    "recent_stress_26w", "transition_persistence_prob", "transition_good_state_prob",
    "transition_non_stress_prob",
]


@dataclass(frozen=True)
class Layer2BBundle:
    regime_score: pd.DataFrame
    regime_states: pd.DataFrame
    market_state_history: pd.DataFrame
    meta_predictions: pd.DataFrame
    source_status: dict[str, str]


def rolling_zscore(series: pd.Series, window: int = 52) -> pd.Series:
    return (series - series.rolling(window, min_periods=max(10, window // 2)).mean()) / (
        series.rolling(window, min_periods=max(10, window // 2)).std() + 1e-12
    )


def average_pairwise_correlation(returns: pd.DataFrame, window: int = 26) -> pd.Series:
    def off_diagonal(block: pd.DataFrame) -> float:
        values = block.to_numpy(dtype=float, copy=False)
        if values.ndim != 2 or values.shape[0] < 2:
            return np.nan
        selected = values[~np.eye(values.shape[0], dtype=bool)]
        selected = selected[np.isfinite(selected)]
        return float(selected.mean()) if selected.size else np.nan
    frame = returns.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")
    output = pd.Series(np.nan, index=returns.index, dtype=float)
    if frame.shape[1] >= 2:
        correlations = frame.rolling(window, min_periods=min(window, max(8, window // 2))).corr()
        if not correlations.empty:
            output = correlations.groupby(level=0, sort=False).apply(off_diagonal).reindex(returns.index)
    return output


def build_regime_states(prices: pd.DataFrame, regime_features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = prices.reindex(columns=[name for name in RESEARCH_UNIVERSE if name in prices]).apply(pd.to_numeric, errors="coerce")
    simple = prices.pct_change(fill_method=None)
    market = simple["SPY"]
    broad = [name for name in BROAD_RISK if name in prices]
    canaries = [name for name in CANARIES if name in prices]
    market_vol = market.rolling(13, min_periods=6).std().mul(np.sqrt(52)).shift(1)
    rolling_high = prices[["SPY"]].rolling(52, min_periods=26).max()
    severity = prices[["SPY"]].div(rolling_high).sub(1).clip(upper=0).abs().rolling(52, min_periods=26).mean()["SPY"].shift(1)
    breadth = prices[canaries].shift(4).div(prices[canaries].shift(52)).sub(1).gt(0).mean(axis=1).shift(1)
    correlation = average_pairwise_correlation(simple[broad]).shift(1)
    score = pd.DataFrame(index=prices.index)
    score["market_vol_risk_off_z"] = rolling_zscore(market_vol)
    score["market_drawdown_risk_off_z"] = rolling_zscore(severity)
    score["breadth_risk_off_z"] = -rolling_zscore(breadth)
    score["avg_corr_risk_off_z"] = rolling_zscore(correlation)
    for column in ("macro_risk_score_tradable", "vix_level_z_tradable", "vix_slope_risk_off_z_tradable", "google_fear_z_tradable"):
        if column in regime_features:
            score[column] = pd.to_numeric(regime_features[column], errors="coerce").reindex(prices.index)
    score["risk_regime_score"] = score.mean(axis=1)
    score["risk_state"] = np.where(score.risk_regime_score >= 0.75, "stressed", np.where(score.risk_regime_score <= -0.50, "calm", "neutral"))
    score["signal_environment"] = np.where(
        breadth.ge(0.60) & score.risk_state.eq("calm"), "trend_friendly",
        np.where(breadth.le(0.40) | score.risk_state.eq("stressed"), "reversal_friendly", "mixed"),
    )
    overlay = pd.Series(np.where(score.risk_state.eq("stressed"), 0.30, np.where(score.risk_state.eq("calm"), 1.0, 0.65)), index=prices.index)
    target = (0.12 / market_vol.replace(0, np.nan)).clip(0.25, 1.25).fillna(0.75)
    states = pd.DataFrame(index=prices.index)
    states["risk_state"] = score.risk_state
    states["signal_environment"] = score.signal_environment
    states["overlay_multiplier"] = np.minimum(overlay, target)
    states["target_vol_multiplier"] = target
    states["defensive_weight"] = 1.0 - states.overlay_multiplier
    states["defensive_asset"] = "BIL"
    states["secondary_defensive_asset"] = "IEF"
    return score, states


def _legacy_transition_probabilities(state: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    next_state = state.shift(-1)
    pairs = pd.DataFrame({"curr": state, "next": next_state}).dropna(subset=["next"])
    pairs["stays"] = pairs.curr.eq(pairs.next).astype(float)
    pairs["good"] = pairs.next.isin({"calm_trend", "recovery_fragile", "recovery_confirmed"}).astype(float)
    pairs["non_stress"] = pairs.next.ne("stressed_panic").astype(float)
    outputs = [pd.Series(np.nan, index=state.index, dtype=float) for _ in range(3)]
    for state_name in pairs.curr.dropna().unique():
        subset = pairs.loc[pairs.curr.eq(state_name)]
        mask = state.eq(state_name)
        for output, column in zip(outputs, ("stays", "good", "non_stress")):
            trailing = subset[column].rolling(156, min_periods=10).mean().shift(1)
            expanded = trailing.reindex(state.index, method="ffill")
            output.loc[mask] = expanded.loc[mask]
    return tuple(outputs)


def _causal_transition_probabilities(state: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Estimate state-conditional transitions using only completed prior pairs."""
    persistence = pd.Series(np.nan, index=state.index, dtype=float)
    good = pd.Series(np.nan, index=state.index, dtype=float)
    non_stress = pd.Series(np.nan, index=state.index, dtype=float)
    histories: dict[str, dict[str, list[float]]] = {}
    good_states = {"calm_trend", "recovery_fragile", "recovery_confirmed"}
    previous: str | None = None
    for date, value in state.items():
        current = str(value)
        # The transition previous -> current has completed at date, but the
        # date-t feature is formed before incorporating that new outcome.
        history = histories.get(current, {})
        if len(history.get("stays", [])) >= 10:
            persistence.loc[date] = float(np.mean(history["stays"][-156:]))
            good.loc[date] = float(np.mean(history["good"][-156:]))
            non_stress.loc[date] = float(np.mean(history["non_stress"][-156:]))
        if previous is not None:
            prior = histories.setdefault(previous, {"stays": [], "good": [], "non_stress": []})
            prior["stays"].append(float(previous == current))
            prior["good"].append(float(current in good_states))
            prior["non_stress"].append(float(current != "stressed_panic"))
        previous = current
    return persistence, good, non_stress


def build_market_state_history(prices: pd.DataFrame, regime_score: pd.DataFrame, regime_states: pd.DataFrame, *, causal_transitions: bool = True) -> pd.DataFrame:
    prices = prices.reindex(columns=[name for name in RESEARCH_UNIVERSE if name in prices]).apply(pd.to_numeric, errors="coerce")
    broad = [name for name in BROAD_RISK if name in prices]
    market = prices["SPY"]
    trend = market.gt(market.rolling(43, min_periods=20).mean())
    drawdown = market.div(market.cummax()).sub(1)
    broad_prices = prices[broad]
    breadth43 = broad_prices.gt(broad_prices.rolling(43, min_periods=20).mean()).mean(axis=1)
    breadth26 = broad_prices.pct_change(26).gt(0).mean(axis=1)
    breadth13 = broad_prices.pct_change(13).gt(0).mean(axis=1)
    breadth_change = breadth43.sub(breadth43.shift(4))
    default_canary = prices[[name for name in CANARIES if name in prices]].shift(4).div(prices[[name for name in CANARIES if name in prices]].shift(52)).sub(1).gt(0).mean(axis=1)
    pair_names = [name for name in ("VWO", "IEF") if name in prices]
    pair_canary = prices[pair_names].shift(4).div(prices[pair_names].shift(52)).sub(1).gt(0).mean(axis=1)
    recent_stress = regime_states.risk_state.eq("stressed").rolling(26, min_periods=1).max().fillna(0).astype(bool)
    risk = pd.to_numeric(regime_score.risk_regime_score, errors="coerce")
    state = pd.Series("neutral_mixed", index=prices.index, dtype=object)
    stressed = regime_states.risk_state.eq("stressed") | (drawdown.le(-0.18) & breadth43.lt(0.35))
    recovery = ~stressed & recent_stress & trend & breadth43.ge(0.45) & breadth26.ge(0.45) & breadth_change.ge(0.05)
    confirmed = recovery & breadth43.ge(0.58) & breadth26.ge(0.55) & breadth13.ge(0.55) & trend & drawdown.ge(-0.06) & risk.fillna(0).le(0.35)
    fragile = recovery & ~confirmed
    calm = ~stressed & regime_states.risk_state.eq("calm") & trend & breadth43.ge(0.60) & breadth26.ge(0.55)
    state.loc[stressed] = "stressed_panic"; state.loc[fragile] = "recovery_fragile"; state.loc[confirmed] = "recovery_confirmed"; state.loc[calm] = "calm_trend"
    reason = pd.Series("mixed inputs", index=state.index, dtype=object)
    reason.loc[stressed] = "stress state, weak breadth, or deep drawdown"
    reason.loc[fragile] = "recent stress with improving breadth but confirmation still partial"
    reason.loc[confirmed] = "recent stress plus confirmed breadth, 13w and 26w momentum, trend, low drawdown, and low risk score"
    reason.loc[calm] = "calm regime with strong trend breadth"
    transition_builder = _causal_transition_probabilities if causal_transitions else _legacy_transition_probabilities
    persistence, good, non_stress = transition_builder(state)
    severe = drawdown.fillna(0).le(-0.10) | risk.fillna(0).gt(0.85)
    entered = state.eq("stressed_panic") & state.shift(1).ne("stressed_panic") & ~severe
    stable = state.copy(); stable.loc[entered] = state.shift(1).loc[entered]; stable = stable.fillna(state)
    return pd.DataFrame({
        "market_state": state, "market_state_stable": stable, "market_state_reason": reason,
        "risk_state": regime_states.risk_state, "signal_environment": regime_states.signal_environment,
        "risk_regime_score": risk, "market_drawdown": drawdown, "market_trend_positive": trend.astype(float),
        "breadth_sma_43": breadth43, "breadth_26w_mom": breadth26, "breadth_13w_mom": breadth13,
        "breadth_change_4w": breadth_change, "canary_breadth_default": default_canary,
        "canary_breadth_pair": pair_canary, "recent_stress_26w": recent_stress.astype(float),
        "avg_corr_risk_off_z": regime_score.get("avg_corr_risk_off_z"),
        "google_fear_z_tradable": regime_score.get("google_fear_z_tradable"),
        "transition_persistence_prob": persistence, "transition_good_state_prob": good,
        "transition_non_stress_prob": non_stress,
    }, index=prices.index)


def _future_labels(returns: pd.Series, horizon: int, kind: str) -> pd.Series:
    result = pd.Series(np.nan, index=returns.index, dtype=float)
    values = returns.to_numpy()
    for i in range(len(values)):
        if i + horizon >= len(values):
            continue
        window = values[i + 1:i + 1 + horizon]
        wealth = np.cumprod(1.0 + window); dd = np.min(wealth / np.maximum.accumulate(wealth) - 1.0)
        if kind == "regime":
            std = window.std(ddof=1) * np.sqrt(52); sharpe = window.mean() * 52 / std if std > 1e-9 else 0.0
            result.iloc[i] = float(sharpe > 0.5 and window.min() > -0.03)
        elif kind == "transition":
            result.iloc[i] = float(np.prod(1.0 + window) - 1.0 > 0 and dd > -0.05)
        else:
            result.iloc[i] = float(dd <= -0.03)
    return result


def build_meta_predictions(state_history: pd.DataFrame, market_returns: pd.Series, *, causal_embargo: bool = True) -> pd.DataFrame:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier
    X = state_history.reindex(columns=FEATURES).apply(pd.to_numeric, errors="coerce").ffill().fillna(0.0)
    returns = pd.to_numeric(market_returns, errors="coerce").reindex(X.index).fillna(0.0)
    specifications = {
        "p_regime_confidence": (4, _future_labels(returns, 4, "regime"), "logistic"),
        "p_transition_quality": (8, _future_labels(returns, 8, "transition"), "tree"),
        "p_tail_risk": (4, _future_labels(returns, 4, "tail"), "gbm"),
    }
    output = pd.DataFrame(index=X.index)
    transition = state_history.market_state.isin(["neutral_mixed", "recovery_fragile", "recovery_confirmed"])
    constraints = np.array([-1, -1, -1, -1, -1, -1, 1, 1, -1, -1, -1], dtype=int)
    for name, (horizon, labels, model_type) in specifications.items():
        predictions = pd.Series(np.nan, index=X.index, dtype=float); model = scaler = None
        base_valid = labels.notna() & (transition if model_type == "tree" else True)
        for i in range(len(X)):
            if i >= 200 and (i == 200 or (i - 200) % 26 == 0):
                # A label dated j is known only after j+horizon.  This embargo
                # is the correction missing from the saved Version 1 script.
                eligible_end = i - horizon if causal_embargo else i
                mask = base_valid.iloc[:eligible_end]
                train_index = X.index[:eligible_end][mask.to_numpy()]
                y = labels.loc[train_index].astype(int)
                if len(y) >= 40 and y.sum() >= 10 and (len(y) - y.sum()) >= 10:
                    values = X.loc[train_index].to_numpy()
                    if model_type == "logistic":
                        scaler = StandardScaler(); values = scaler.fit_transform(values)
                        model = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", max_iter=1000, class_weight="balanced")
                    elif model_type == "tree":
                        model = DecisionTreeClassifier(max_depth=4, min_samples_leaf=25, class_weight="balanced", random_state=42)
                    else:
                        model = HistGradientBoostingClassifier(max_depth=4, max_iter=150, learning_rate=0.05, l2_regularization=1.0, min_samples_leaf=25, monotonic_cst=constraints, class_weight="balanced", random_state=42)
                    model.fit(values, y.to_numpy())
            if model is not None:
                row = X.iloc[[i]].to_numpy(); row = scaler.transform(row) if scaler is not None else row
                predictions.iloc[i] = float(model.predict_proba(row)[0, 1])
        output[name] = predictions
    return output


def build_layer2b_bundle(prices: pd.DataFrame, regime_features: pd.DataFrame, *, causal_embargo: bool = True, causal_transitions: bool = True) -> Layer2BBundle:
    score, states = build_regime_states(prices, regime_features)
    history = build_market_state_history(prices, score, states, causal_transitions=causal_transitions)
    predictions = build_meta_predictions(history, prices["SPY"].pct_change(fill_method=None), causal_embargo=causal_embargo)
    return Layer2BBundle(score, states, history, predictions, {"regime_states": "complete", "market_state_history": "complete_causal_transitions" if causal_transitions else "historical_transition_compatibility", "meta_predictions": "complete_causal_embargo" if causal_embargo else "historical_leaky_compatibility"})
