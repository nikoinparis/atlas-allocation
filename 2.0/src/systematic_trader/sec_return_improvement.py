"""Causal building blocks for the frozen SEC return-improvement program.

The functions in this module construct signals and weights only. They do not
load the broad research panel or calculate a strategy performance result; that
remains behind the explicit broad-universe research gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

CASH = "cash::USD"


def _finite(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)


def robust_rank(values: pd.Series, *, minimum: int = 3) -> pd.Series:
    """Winsorized percentile rank on [-1, 1], preserving missing values."""
    clean = _finite(values)
    valid = clean.dropna()
    result = pd.Series(np.nan, index=values.index, dtype=float)
    if len(valid) < minimum:
        return result
    lower, upper = valid.quantile([0.05, 0.95])
    clipped = valid.clip(lower, upper)
    result.loc[valid.index] = clipped.rank(pct=True, method="average") * 2.0 - 1.0
    return result


def _row_ranks(frame: pd.DataFrame, *, minimum: int = 3) -> pd.DataFrame:
    return frame.apply(lambda row: robust_rank(row, minimum=minimum), axis=1)


def _sector_median(frame: pd.DataFrame, sectors: dict[str, str]) -> pd.DataFrame:
    result = pd.DataFrame(np.nan, index=frame.index, columns=frame.columns, dtype=float)
    groups: dict[str, list[str]] = {}
    for asset in frame.columns:
        groups.setdefault(str(sectors.get(asset, "unknown")), []).append(asset)
    for assets in groups.values():
        median = frame[assets].median(axis=1, skipna=True)
        result.loc[:, assets] = np.repeat(median.to_numpy()[:, None], len(assets), axis=1)
    return result


def residual_momentum_scores(
    prices: pd.DataFrame,
    sectors: dict[str, str],
    *,
    lookback_weeks: int,
    skip_weeks: int,
    sector_weight: float = 0.7,
    market_weight: float = 0.3,
    minimum_history_weeks: int = 26,
) -> pd.DataFrame:
    """Sector/market-residual momentum known one full observation before use."""
    if lookback_weeks <= skip_weeks or minimum_history_weeks <= skip_weeks:
        raise ValueError("lookback and minimum history must exceed skip")
    if not np.isclose(sector_weight + market_weight, 1.0):
        raise ValueError("sector and market residual weights must sum to one")
    observed = prices.apply(pd.to_numeric, errors="coerce").shift(1)
    momentum = observed.shift(skip_weeks).div(observed.shift(lookback_weeks)) - 1.0
    history = observed.notna().rolling(lookback_weeks, min_periods=1).sum()
    momentum = momentum.where(history >= minimum_history_weeks)
    sector_component = momentum - _sector_median(momentum, sectors)
    market_median = momentum.median(axis=1, skipna=True)
    market_component = momentum.sub(market_median, axis=0)
    residual = sector_weight * sector_component + market_weight * market_component
    return _row_ranks(residual)


def trend_quality_scores(
    prices: pd.DataFrame,
    *,
    high_window_weeks: int = 52,
    positive_week_window: int = 26,
    momentum_horizons_weeks: Iterable[int] = (13, 26, 52),
    skip_weeks: int = 4,
    component_weights: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Blend 52-week-high proximity, consistency, and multi-horizon strength."""
    weights = component_weights or {
        "high_proximity": 0.3,
        "trend_consistency": 0.3,
        "multi_horizon_strength": 0.4,
    }
    required = {"high_proximity", "trend_consistency", "multi_horizon_strength"}
    if set(weights) != required or not np.isclose(sum(weights.values()), 1.0):
        raise ValueError("trend component weights must name all components and sum to one")
    observed = prices.apply(pd.to_numeric, errors="coerce").shift(1)
    returns = prices.apply(pd.to_numeric, errors="coerce").pct_change(fill_method=None).shift(1)
    high_proximity = observed.div(observed.rolling(high_window_weeks, min_periods=high_window_weeks // 2).max())
    positive_share = returns.gt(0.0).rolling(positive_week_window, min_periods=positive_week_window // 2).mean()
    long_momentum = observed.shift(skip_weeks).div(observed.shift(max(momentum_horizons_weeks))) - 1.0
    consistency = long_momentum * positive_share
    horizon_scores = []
    for horizon in momentum_horizons_weeks:
        raw = observed.shift(min(skip_weeks, max(0, horizon - 1))).div(observed.shift(horizon)) - 1.0
        horizon_scores.append(_row_ranks(raw))
    components = {
        "high_proximity": _row_ranks(high_proximity),
        "trend_consistency": _row_ranks(consistency),
        "multi_horizon_strength": sum(horizon_scores) / len(horizon_scores),
    }
    blended = sum(components[name] * float(weights[name]) for name in required)
    available = sum(frame.notna().astype(int) for frame in components.values())
    return blended.where(available >= 2), components


def sector_neutral_quality_scores(
    panel: pd.DataFrame,
    *,
    positive_features: Iterable[str],
    negative_features: Iterable[str],
    minimum_available_features: int,
) -> pd.DataFrame:
    """Point-in-time sector-neutral quality momentum for a long-form panel."""
    required = {"decision_at", "cik10", "sector"}
    if not required.issubset(panel.columns):
        raise ValueError(f"quality panel missing {sorted(required - set(panel.columns))}")
    features = [(name, 1.0) for name in positive_features] + [(name, -1.0) for name in negative_features]
    missing = [name for name, _ in features if name not in panel.columns]
    if missing:
        raise ValueError(f"quality panel missing features: {missing}")
    output = panel[[column for column in panel.columns if column not in {name for name, _ in features}]].copy()
    scores = pd.DataFrame(np.nan, index=panel.index, columns=[name for name, _ in features], dtype=float)
    for (_, sector), indices in panel.groupby(["decision_at", "sector"], sort=True).groups.items():
        for feature, sign in features:
            scores.loc[indices, feature] = robust_rank(panel.loc[indices, feature]) * sign
    output["available_features"] = scores.notna().sum(axis=1)
    output["quality_momentum_score"] = scores.mean(axis=1, skipna=True).where(
        output["available_features"] >= int(minimum_available_features)
    )
    return output


def event_conditioned_scores(
    base_scores: pd.DataFrame,
    events: pd.DataFrame,
    *,
    event_weight: float,
    lookback_weeks: int,
    delay_weeks: int = 1,
    neutral_event_score: float = 0.5,
) -> pd.DataFrame:
    """Add only events strictly known before each decision's delayed cutoff."""
    required_base = {"decision_at", "cik10", "score"}
    required_event = {"available_at", "cik10", "event_score"}
    if not required_base.issubset(base_scores) or not required_event.issubset(events):
        raise ValueError("base or event schema is incomplete")
    if not 0.0 <= event_weight <= 1.0 or delay_weeks < 1:
        raise ValueError("event weight must be in [0, 1] and delay at least one week")
    base = base_scores.copy()
    base["decision_at"] = pd.to_datetime(base["decision_at"], utc=True)
    event_frame = events.copy()
    event_frame["available_at"] = pd.to_datetime(event_frame["available_at"], utc=True)
    rows = []
    for decision, frame in base.groupby("decision_at", sort=True):
        cutoff = decision - pd.Timedelta(weeks=delay_weeks)
        start = cutoff - pd.Timedelta(weeks=lookback_weeks)
        known = event_frame[(event_frame.available_at < cutoff) & (event_frame.available_at >= start)]
        known = known.sort_values("available_at").drop_duplicates("cik10", keep="last")
        event_map = known.set_index("cik10")["event_score"].to_dict()
        block = frame.copy()
        block["event_score"] = block["cik10"].map(event_map).fillna(float(neutral_event_score))
        centered = block["event_score"] - float(neutral_event_score)
        block["conditioned_score"] = (1.0 - event_weight) * block["score"] + event_weight * centered * 2.0
        block["event_cutoff"] = cutoff
        rows.append(block)
    return pd.concat(rows, ignore_index=True) if rows else base.assign(conditioned_score=np.nan)


def concentration_confidence(component_scores: pd.DataFrame) -> float:
    """Generic confidence from score separation, dispersion, and component agreement."""
    clean = component_scores.apply(pd.to_numeric, errors="coerce").dropna(how="all")
    if len(clean) < 5 or clean.shape[1] < 2:
        return 0.0
    composite = clean.mean(axis=1, skipna=True).sort_values(ascending=False)
    gap = float(composite.iloc[0] - composite.iloc[min(4, len(composite) - 1)])
    dispersion = float(composite.std(ddof=1))
    top = composite.index[0]
    agreement = float((clean.rank(pct=True).loc[top] >= 0.75).mean())
    gap_score = float(np.clip(gap / 0.75, 0.0, 1.0))
    dispersion_score = float(np.clip(dispersion / 0.5, 0.0, 1.0))
    return float(np.mean([gap_score, dispersion_score, agreement]))


def adaptive_breadth(
    component_scores: pd.DataFrame,
    *,
    breadth_tiers: tuple[int, int, int] = (5, 10, 20),
    high_confidence_minimum: float = 0.75,
    medium_confidence_minimum: float = 0.5,
) -> tuple[int, float]:
    tiers = tuple(sorted(int(value) for value in breadth_tiers))
    if len(tiers) != 3 or not 0.0 <= medium_confidence_minimum <= high_confidence_minimum <= 1.0:
        raise ValueError("invalid adaptive breadth specification")
    confidence = concentration_confidence(component_scores)
    breadth = tiers[0] if confidence >= high_confidence_minimum else tiers[1] if confidence >= medium_confidence_minimum else tiers[2]
    return breadth, confidence


def _redistribute_with_caps(
    raw: pd.Series,
    sectors: dict[str, str],
    *,
    issuer_cap: float,
    sector_cap: float,
) -> pd.Series:
    weights = raw.clip(lower=0.0)
    weights = weights / weights.sum() if weights.sum() > 0 else weights
    for _ in range(20):
        previous = weights.copy()
        weights = weights.clip(upper=issuer_cap)
        for sector in sorted({sectors.get(asset, "unknown") for asset in weights.index}):
            assets = [asset for asset in weights.index if sectors.get(asset, "unknown") == sector]
            total = float(weights.loc[assets].sum())
            if total > sector_cap:
                weights.loc[assets] *= sector_cap / total
        residual = 1.0 - float(weights.sum())
        if residual <= 1e-12:
            break
        capacity = pd.Series(
            {
                asset: max(0.0, min(issuer_cap - weights[asset], sector_cap - float(weights[[x for x in weights.index if sectors.get(x, "unknown") == sectors.get(asset, "unknown")]].sum())))
                for asset in weights.index
            }
        )
        eligible = capacity[capacity > 1e-12]
        if eligible.empty:
            break
        addition = residual * raw.loc[eligible.index].clip(lower=1e-12)
        addition = addition / addition.sum() * min(residual, float(eligible.sum()))
        weights.loc[eligible.index] += np.minimum(addition, eligible)
        if np.allclose(previous, weights, atol=1e-12, rtol=0.0):
            break
    return weights


def adaptive_concentration_weights(
    scores: pd.Series,
    sectors: dict[str, str],
    *,
    breadth: int,
    issuer_cap: float,
    sector_cap: float,
    conviction_power: float = 1.0,
) -> pd.Series:
    """Generic conviction weights; unallocatable cap excess remains explicit cash."""
    if breadth < 1 or not 0.0 < issuer_cap <= 1.0 or not 0.0 < sector_cap <= 1.0:
        raise ValueError("invalid concentration limits")
    selected = _finite(scores).dropna().sort_values(ascending=False).head(breadth)
    shifted = (selected - selected.min() + 1e-6).pow(conviction_power)
    weights = _redistribute_with_caps(shifted, sectors, issuer_cap=issuer_cap, sector_cap=sector_cap)
    result = weights.copy()
    result.loc[CASH] = max(0.0, 1.0 - float(weights.sum()))
    return result


@dataclass(frozen=True)
class WalkForwardFold:
    train_decisions: tuple[pd.Timestamp, ...]
    test_decisions: tuple[pd.Timestamp, ...]


def purged_walk_forward_folds(
    decisions: Iterable[pd.Timestamp],
    *,
    minimum_training_decisions: int,
    test_decisions_per_fold: int,
    purge_decisions: int,
    embargo_decisions: int,
) -> list[WalkForwardFold]:
    """Expanding causal folds with an explicit label purge and post-test embargo."""
    ordered = tuple(sorted(pd.DatetimeIndex(decisions).unique()))
    folds: list[WalkForwardFold] = []
    cursor = minimum_training_decisions + purge_decisions
    while cursor < len(ordered):
        test = ordered[cursor: cursor + test_decisions_per_fold]
        if not test:
            break
        train_end = cursor - purge_decisions
        train = ordered[:train_end]
        if len(train) >= minimum_training_decisions:
            folds.append(WalkForwardFold(tuple(train), tuple(test)))
        cursor += test_decisions_per_fold + embargo_decisions
    return folds


def walk_forward_ridge_rank(
    panel: pd.DataFrame,
    *,
    features: list[str],
    target: str,
    alphas: Iterable[float],
    minimum_training_decisions: int,
    test_decisions_per_fold: int,
    purge_decisions: int,
    embargo_decisions: int,
    minimum_training_rows: int,
) -> pd.DataFrame:
    """Out-of-sample ridge ensemble predictions with model-agreement confidence."""
    required = {"decision_at", "cik10", target, *features}
    if not required.issubset(panel):
        raise ValueError(f"ML panel missing {sorted(required - set(panel))}")
    data = panel.copy()
    data["decision_at"] = pd.to_datetime(data["decision_at"], utc=True)
    folds = purged_walk_forward_folds(
        data.decision_at,
        minimum_training_decisions=minimum_training_decisions,
        test_decisions_per_fold=test_decisions_per_fold,
        purge_decisions=purge_decisions,
        embargo_decisions=embargo_decisions,
    )
    outputs = []
    for fold_id, fold in enumerate(folds):
        train = data[data.decision_at.isin(fold.train_decisions)].dropna(subset=[*features, target])
        test = data[data.decision_at.isin(fold.test_decisions)].dropna(subset=features)
        if len(train) < minimum_training_rows or test.empty:
            continue
        mean = train[features].mean()
        scale = train[features].std(ddof=1).replace(0.0, 1.0).fillna(1.0)
        x_train = ((train[features] - mean) / scale).to_numpy(float)
        y_train = _finite(train[target]).to_numpy(float)
        x_test = ((test[features] - mean) / scale).to_numpy(float)
        x_train = np.column_stack([np.ones(len(x_train)), x_train])
        x_test = np.column_stack([np.ones(len(x_test)), x_test])
        predictions = []
        residual_scales = []
        for alpha in alphas:
            penalty = np.eye(x_train.shape[1]) * float(alpha)
            penalty[0, 0] = 0.0
            coefficients = np.linalg.pinv(x_train.T @ x_train + penalty) @ x_train.T @ y_train
            fitted = x_train @ coefficients
            predictions.append(x_test @ coefficients)
            residual_scales.append(float(np.std(y_train - fitted, ddof=1)))
        matrix = np.column_stack(predictions)
        prediction = matrix.mean(axis=1)
        disagreement = matrix.std(axis=1, ddof=0)
        noise = max(float(np.mean(residual_scales)), 1e-12)
        confidence = np.abs(prediction) / (noise + disagreement)
        block = test[["decision_at", "cik10"]].copy()
        block["prediction"] = prediction
        block["model_disagreement"] = disagreement
        block["confidence"] = confidence
        block["prediction_rank"] = block.groupby("decision_at")["prediction"].rank(pct=True, method="average")
        block["confidence_rank"] = block.groupby("decision_at")["confidence"].rank(pct=True, method="average")
        block["fold_id"] = fold_id
        block["train_end"] = max(fold.train_decisions)
        outputs.append(block)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame(
        columns=["decision_at", "cik10", "prediction", "model_disagreement", "confidence", "prediction_rank", "confidence_rank", "fold_id", "train_end"]
    )


def buffered_holding_selections(
    score_panel: pd.DataFrame,
    *,
    breadth: int,
    entry_rank_buffer: int,
    exit_rank_multiple: float,
    minimum_holding_decisions: int,
    maximum_holding_decisions: int,
) -> pd.DataFrame:
    """Keep winners until rank decay or maximum age, while enforcing minimum age."""
    required = {"decision_at", "cik10", "score"}
    if not required.issubset(score_panel):
        raise ValueError("holding panel schema is incomplete")
    if minimum_holding_decisions > maximum_holding_decisions:
        raise ValueError("minimum holding period exceeds maximum")
    panel = score_panel.copy()
    panel["decision_at"] = pd.to_datetime(panel["decision_at"], utc=True)
    current: list[str] = []
    ages: dict[str, int] = {}
    rows = []
    for decision, frame in panel.groupby("decision_at", sort=True):
        ranked = frame.dropna(subset=["score"]).sort_values(["score", "cik10"], ascending=[False, True]).copy()
        ranked["rank"] = np.arange(1, len(ranked) + 1)
        rank_map = ranked.set_index("cik10")["rank"].to_dict()
        eligible_entry = set(ranked.loc[ranked["rank"] <= breadth + entry_rank_buffer, "cik10"])
        exit_rank = int(np.ceil(breadth * exit_rank_multiple))
        survivors = []
        for cik in current:
            # A missing current score is unavailable evidence, not merely a
            # weak rank. Do not preserve it through a turnover buffer.
            if cik not in rank_map:
                continue
            age = ages.get(cik, 0)
            keep_for_minimum = age < minimum_holding_decisions
            keep_on_rank = rank_map.get(cik, np.inf) <= exit_rank and age < maximum_holding_decisions
            if keep_for_minimum or keep_on_rank:
                survivors.append(cik)
        candidates = [cik for cik in ranked.cik10 if cik in eligible_entry and cik not in survivors]
        selected = (survivors + candidates)[:breadth]
        ages = {cik: ages.get(cik, 0) + 1 if cik in current else 1 for cik in selected}
        current = selected
        for cik in selected:
            rows.append({
                "decision_at": decision,
                "cik10": cik,
                "rank": int(rank_map[cik]),
                "holding_age_decisions": int(ages[cik]),
                "intended_weight": 1.0 / breadth,
            })
    return pd.DataFrame(rows)


def causal_strategy_allocator(
    sleeve_returns: pd.DataFrame,
    *,
    lookback_weeks: int,
    minimum_history_weeks: int,
    momentum_lookbacks_weeks: Iterable[int],
    maximum_sleeve_weight: float,
    minimum_active_sleeve_weight: float,
    independence_penalty: float,
) -> pd.DataFrame:
    """Allocate using only returns strictly before each output date."""
    if not 0.0 < maximum_sleeve_weight <= 1.0 or not 0.0 <= independence_penalty <= 1.0:
        raise ValueError("invalid allocator limits")
    returns = sleeve_returns.apply(pd.to_numeric, errors="coerce")
    columns = [*returns.columns, CASH]
    output = pd.DataFrame(0.0, index=returns.index, columns=columns)
    output[CASH] = 1.0
    for position, date in enumerate(returns.index):
        history = returns.iloc[max(0, position - lookback_weeks):position].dropna(how="all")
        if len(history) < minimum_history_weeks:
            continue
        strengths = []
        for horizon in momentum_lookbacks_weeks:
            window = history.tail(int(horizon))
            strengths.append(window.mean() / window.std(ddof=1).replace(0.0, np.nan))
        strength = pd.concat(strengths, axis=1).mean(axis=1).clip(lower=0.0).fillna(0.0)
        correlation = history.corr(min_periods=max(8, minimum_history_weeks // 2)).fillna(0.0)
        independence = pd.Series(1.0, index=returns.columns)
        for sleeve in returns.columns:
            peers = correlation.loc[sleeve].drop(labels=[sleeve], errors="ignore").abs()
            independence[sleeve] = 1.0 - independence_penalty * (float(peers.max()) if len(peers) else 0.0)
        raw = strength * independence.clip(lower=0.0)
        active = raw[raw > 0.0]
        if active.empty:
            continue
        weights = active / active.sum()
        for _ in range(10):
            weights = weights.clip(upper=maximum_sleeve_weight)
            eligible = weights[weights >= minimum_active_sleeve_weight]
            if eligible.empty:
                break
            weights = eligible / eligible.sum()
            if float(weights.max()) <= maximum_sleeve_weight + 1e-12:
                break
        weights = weights.clip(upper=maximum_sleeve_weight)
        output.loc[date, weights.index] = weights
        output.loc[date, CASH] = max(0.0, 1.0 - float(weights.sum()))
    return output
