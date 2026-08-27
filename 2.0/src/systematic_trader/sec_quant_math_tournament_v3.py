"""Causal monthly feature and portfolio mathematics for quant tournament v3.

The module is deliberately independent of the real runner so its causal and
portfolio invariants can be tested on fixtures before the execution seal is
created. No function enables execution or live trading.
"""

from __future__ import annotations

from itertools import combinations
from statistics import NormalDist

import numpy as np
import pandas as pd


SIGNAL_FAMILIES = [
    "multi_horizon_residual_momentum",
    "residual_acceleration",
    "quality_momentum_interaction",
    "trend_breakout_quality",
    "reversal_conditioned_momentum",
    "causal_nonlinear_ridge",
]

RIDGE_FEATURES = [
    "residual_13", "residual_26", "residual_52", "momentum_acceleration",
    "trend_consistency", "downside_volatility", "quality_momentum",
    "event_centered", "quality_times_residual", "acceleration_times_quality",
]


def robust_z(values: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Winsorized median/MAD score with a safe standard-deviation fallback."""
    numeric = pd.to_numeric(values, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series(np.nan, index=values.index, dtype=float)
    lo, hi = valid.quantile([lower, upper])
    clipped = numeric.clip(lo, hi)
    center = clipped.median()
    mad = (clipped - center).abs().median()
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = clipped.std(ddof=1)
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = 1.0
    return ((clipped - center) / scale).clip(-8.0, 8.0)


def percentile(values: pd.Series, ascending: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.rank(pct=True, method="average", ascending=ascending)


def _compound(block: pd.DataFrame) -> pd.Series:
    return (1.0 + block).prod(axis=0, min_count=1) - 1.0


def _trailing_return(returns: pd.DataFrame, position: int, horizon: int, skip: int) -> pd.Series:
    end = position - skip + 1
    start = end - horizon
    if start < 0 or end <= start:
        return pd.Series(np.nan, index=returns.columns)
    return _compound(returns.iloc[start:end])


def _future_return(returns: pd.DataFrame, position: int, delay: int, horizon: int) -> tuple[pd.Series, pd.Timestamp | pd.NaT]:
    start = position + delay
    end = start + horizon
    if end > len(returns):
        return pd.Series(np.nan, index=returns.columns), pd.NaT
    return _compound(returns.iloc[start:end]), returns.index[end - 1]


def _latest_snapshot(panel: pd.DataFrame, decision: pd.Timestamp) -> pd.DataFrame:
    eligible = panel[panel.decision_at <= decision]
    if eligible.empty:
        return eligible
    source_decision = eligible.decision_at.max()
    snapshot = eligible[eligible.decision_at == source_decision].copy()
    snapshot = snapshot[snapshot.available_at <= decision]
    return snapshot.drop_duplicates("cik10", keep="last")


def _sector_residual(values: pd.Series, sectors: pd.Series) -> pd.Series:
    medians = values.groupby(sectors).transform("median")
    residual = values - medians
    return residual - residual.median()


def build_monthly_feature_panel(quarterly_panel: pd.DataFrame, weekly_returns: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Expand quarterly point-in-time SEC snapshots into causal 4-week decisions."""
    source = quarterly_panel.copy()
    source["cik10"] = source.cik10.astype(str).str.zfill(10)
    for column in ["decision_at", "execution_at", "label_end_at", "available_at"]:
        source[column] = pd.to_datetime(source[column], utc=True)
    returns = weekly_returns.copy().apply(pd.to_numeric, errors="coerce")
    returns.columns = returns.columns.astype(str).str.zfill(10)
    returns.index = pd.to_datetime(returns.index, utc=True)
    returns = returns.sort_index()
    cfg = config["price_features"]
    minimum = max(cfg["momentum_horizons_weeks"]) + cfg["skip_recent_weeks"]
    step = int(config["decision_frequency_weeks"])
    delay = int(config["execution_delay_weeks"])
    horizon = int(config["causal_model"]["label_horizon_weeks"])
    rows: list[pd.DataFrame] = []
    for position in range(minimum, len(returns) - delay, step):
        decision = returns.index[position]
        snapshot = _latest_snapshot(source, decision)
        if snapshot.empty:
            continue
        names = snapshot.cik10.astype(str)
        sectors = snapshot.set_index("cik10").sector.reindex(names).fillna("unknown")
        r13 = _trailing_return(returns, position, 13, cfg["skip_recent_weeks"]).reindex(names)
        r26 = _trailing_return(returns, position, 26, cfg["skip_recent_weeks"]).reindex(names)
        r52 = _trailing_return(returns, position, 52, cfg["skip_recent_weeks"]).reindex(names)
        recent = returns.iloc[max(0, position - 25): position + 1].reindex(columns=names)
        reversal = _trailing_return(returns, position, cfg["short_reversal_weeks"], 0).reindex(names)
        consistency = (recent > 0).sum().div(recent.notna().sum().replace(0, np.nan))
        downside = recent.where(recent < 0, 0.0).std(ddof=1) * np.sqrt(52)
        total = _compound(recent)
        path = (1.0 + recent.fillna(0.0)).cumprod()
        current_drawdown = path.iloc[-1].div(path.max()) - 1.0
        fwd, label_end = _future_return(returns, position, delay, horizon)
        fwd = fwd.reindex(names)
        frame = snapshot.set_index("cik10").reindex(names)[
            ["sector", "validated_price_available", "quality_momentum", "event_score", "available_at"]
        ].copy()
        frame["decision_at"] = decision
        frame["execution_at"] = returns.index[position + delay]
        frame["label_end_at"] = label_end
        frame["residual_13"] = _sector_residual(r13, sectors)
        frame["residual_26"] = _sector_residual(r26, sectors)
        frame["residual_52"] = _sector_residual(r52, sectors)
        frame["momentum_acceleration"] = frame.residual_13 - 0.5 * frame.residual_26 - 0.5 * frame.residual_52
        frame["short_reversal"] = reversal
        frame["trend_consistency"] = consistency
        frame["downside_volatility"] = downside
        frame["trailing_26_return"] = total
        frame["current_drawdown"] = current_drawdown
        frame["event_centered"] = pd.to_numeric(frame.event_score, errors="coerce").fillna(0.5) - 0.5
        frame["quality_times_residual"] = pd.to_numeric(frame.quality_momentum, errors="coerce") * frame.residual_26
        frame["acceleration_times_quality"] = frame.momentum_acceleration * pd.to_numeric(frame.quality_momentum, errors="coerce")
        frame["future_sector_relative_return"] = fwd - fwd.groupby(sectors).transform("median")
        frame["cik10"] = frame.index
        history_count = recent.notna().sum()
        frame["price_history_weeks"] = history_count
        frame["price_eligible"] = (
            frame.validated_price_available.astype(bool)
            & history_count.ge(cfg["minimum_price_history_weeks"])
            & returns.iloc[position].reindex(names).notna()
        )
        rows.append(frame.reset_index(drop=True))
    if not rows:
        return pd.DataFrame()
    output = pd.concat(rows, ignore_index=True)
    return output.sort_values(["decision_at", "cik10"]).reset_index(drop=True)


def _rank_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in [
        "residual_13", "residual_26", "residual_52", "momentum_acceleration",
        "trend_consistency", "short_reversal", "quality_momentum", "event_centered",
        "downside_volatility", "current_drawdown",
    ]:
        result[f"rank_{column}"] = percentile(result[column])
    residual = result[["rank_residual_13", "rank_residual_26", "rank_residual_52"]].mean(axis=1)
    quality = 0.8 * result.rank_quality_momentum.fillna(0.5) + 0.2 * result.rank_event_centered.fillna(0.5)
    result["multi_horizon_residual_momentum"] = residual
    result["residual_acceleration"] = 0.55 * result.rank_residual_13 + 0.25 * result.rank_momentum_acceleration + 0.20 * quality
    result["quality_momentum_interaction"] = np.sqrt(residual.clip(0) * quality.clip(0))
    result["trend_breakout_quality"] = (
        0.30 * result.rank_residual_13 + 0.20 * result.rank_residual_26
        + 0.20 * result.rank_trend_consistency + 0.15 * result.rank_current_drawdown
        + 0.15 * quality
    )
    result["reversal_conditioned_momentum"] = 0.60 * residual + 0.20 * quality + 0.20 * (1.0 - result.rank_short_reversal)
    return result


def causal_ridge_scores(monthly_panel: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Purged expanding-window ridge with a predeclared nonlinear basis."""
    cfg = config["causal_model"]
    data = monthly_panel.copy()
    decisions = sorted(data.decision_at.unique())
    scores, audits = [], []
    for test_pos, decision in enumerate(decisions):
        test = data[data.decision_at == decision].copy()
        safe = data[(data.label_end_at < decision) & data.future_sector_relative_return.notna()].copy()
        safe_decisions = sorted(safe.decision_at.unique())
        if len(safe_decisions) < cfg["minimum_training_decisions"] or test.empty:
            continue
        validation_decision = safe_decisions[-1]
        train = safe[safe.decision_at < validation_decision].dropna(subset=RIDGE_FEATURES + ["future_sector_relative_return"])
        validation = safe[safe.decision_at == validation_decision].dropna(subset=RIDGE_FEATURES + ["future_sector_relative_return"])
        usable_test = test.dropna(subset=RIDGE_FEATURES)
        if len(train) < 500 or validation.empty or usable_test.empty:
            continue
        center = train[RIDGE_FEATURES].median()
        scale = (train[RIDGE_FEATURES] - center).abs().median().mul(1.4826).replace(0, 1).fillna(1)
        xtrain = ((train[RIDGE_FEATURES] - center) / scale).clip(-6, 6).to_numpy(float)
        xvalid = ((validation[RIDGE_FEATURES] - center) / scale).clip(-6, 6).to_numpy(float)
        ytrain = train.future_sector_relative_return.to_numpy(float)
        yvalid = validation.future_sector_relative_return.to_numpy(float)
        choices = []
        for alpha in cfg["ridge_alphas"]:
            coef = np.linalg.pinv(xtrain.T @ xtrain + np.eye(xtrain.shape[1]) * alpha) @ xtrain.T @ ytrain
            prediction_rank = pd.Series(xvalid @ coef).rank(method="average")
            target_rank = pd.Series(yvalid).rank(method="average")
            correlation = prediction_rank.corr(target_rank)
            choices.append((float(correlation) if pd.notna(correlation) else -np.inf, float(alpha)))
        selected_alpha = max(choices, key=lambda item: (item[0], -item[1]))[1]
        refit = safe.dropna(subset=RIDGE_FEATURES + ["future_sector_relative_return"])
        center = refit[RIDGE_FEATURES].median()
        scale = (refit[RIDGE_FEATURES] - center).abs().median().mul(1.4826).replace(0, 1).fillna(1)
        xrefit = ((refit[RIDGE_FEATURES] - center) / scale).clip(-6, 6).to_numpy(float)
        coef = np.linalg.pinv(xrefit.T @ xrefit + np.eye(xrefit.shape[1]) * selected_alpha) @ xrefit.T @ refit.future_sector_relative_return.to_numpy(float)
        block = usable_test[["decision_at", "execution_at", "cik10"]].copy()
        block["causal_nonlinear_ridge"] = ((usable_test[RIDGE_FEATURES] - center) / scale).clip(-6, 6).to_numpy(float) @ coef
        scores.append(block)
        audits.append({
            "decision_at": decision, "train_end": safe.label_end_at.max(),
            "training_decisions": len(safe_decisions), "training_rows": len(refit),
            "selected_alpha": selected_alpha, "validation_rank_ic": max(x[0] for x in choices),
        })
    score_frame = pd.concat(scores, ignore_index=True) if scores else pd.DataFrame(columns=["decision_at", "execution_at", "cik10", "causal_nonlinear_ridge"])
    return score_frame, pd.DataFrame(audits)


def build_signal_panel(monthly_panel: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    blocks = [_rank_signal_frame(frame) for _, frame in monthly_panel.groupby("decision_at", sort=True)]
    ranked = pd.concat(blocks, ignore_index=True) if blocks else monthly_panel.copy()
    ridge, audit = causal_ridge_scores(monthly_panel, config)
    ranked = ranked.merge(ridge[["decision_at", "cik10", "causal_nonlinear_ridge"]], on=["decision_at", "cik10"], how="left", validate="one_to_one")
    for family in SIGNAL_FAMILIES:
        if family in ranked:
            ranked[family] = ranked.groupby("decision_at")[family].rank(pct=True, method="average")
    return ranked, audit


def _select_names(frame: pd.DataFrame, score_column: str, breadth: int, sector_cap: float, minimum_sectors: int) -> pd.DataFrame:
    ranked = frame[frame.price_eligible].dropna(subset=[score_column, "downside_volatility"]).sort_values([score_column, "cik10"], ascending=[False, True])
    chosen, counts = [], {}
    limit = max(1, int(np.floor(sector_cap * breadth)))
    for row in ranked.itertuples(index=False):
        sector = str(row.sector)
        if counts.get(sector, 0) >= limit:
            continue
        chosen.append(row)
        counts[sector] = counts.get(sector, 0) + 1
        if len(chosen) == breadth:
            break
    output = pd.DataFrame(chosen)
    if output.empty or output.sector.nunique() < minimum_sectors:
        return pd.DataFrame(columns=frame.columns)
    return output


def _project_caps(raw: pd.Series, sectors: pd.Series, issuer_cap: float, sector_cap: float) -> pd.Series:
    raw = raw.clip(lower=0).fillna(0)
    if raw.sum() <= 0:
        raw[:] = 1.0
    weights = raw / raw.sum()
    for _ in range(100):
        prior = weights.copy()
        weights = weights.clip(upper=issuer_cap)
        sector_sums = weights.groupby(sectors).transform("sum")
        over = sector_sums > sector_cap
        weights.loc[over] *= sector_cap / sector_sums.loc[over]
        deficit = 1.0 - weights.sum()
        if deficit > 1e-10:
            sector_used = weights.groupby(sectors).transform("sum")
            capacity = np.minimum(issuer_cap - weights, sector_cap - sector_used).clip(lower=0)
            floor = max(float(raw.max()), 1.0) * 1e-8
            eligible = (raw + floor).where(capacity > 1e-12, 0.0)
            if eligible.sum() <= 0:
                break
            proposal = deficit * eligible / eligible.sum()
            weights += np.minimum(proposal, capacity)
        if float((weights - prior).abs().max()) < 1e-10:
            break
    return weights / weights.sum() if weights.sum() else weights


def _covariance_weights(chosen: pd.DataFrame, weekly_returns: pd.DataFrame, decision: pd.Timestamp, score_column: str, config: dict) -> pd.Series:
    names = chosen.cik10.astype(str).tolist()
    history = weekly_returns.loc[:decision, names].tail(config["price_features"]["covariance_lookback_weeks"]).copy()
    history = history.fillna(history.median()).fillna(0.0)
    sample = history.cov().to_numpy(float)
    diagonal = np.diag(np.diag(sample))
    shrink = config["constraints"]["shrinkage_to_diagonal"]
    covariance = (1.0 - shrink) * sample + shrink * diagonal + np.eye(len(names)) * 1e-8
    alpha = percentile(chosen.set_index("cik10")[score_column]).fillna(0.5).to_numpy(float)
    raw = np.linalg.pinv(covariance) @ np.maximum(alpha - 0.25, 0.0)
    raw = pd.Series(np.clip(raw, 0, None), index=names)
    sectors = chosen.set_index("cik10").sector.reindex(names)
    return _project_caps(raw, sectors, config["constraints"]["maximum_issuer_weight"], config["constraints"]["maximum_sector_weight"])


def build_base_targets(signal_panel: pd.DataFrame, weekly_returns: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    targets: dict[str, list[dict]] = {}
    constraints = config["constraints"]
    for decision, frame in signal_panel.groupby("decision_at", sort=True):
        execution = frame.execution_at.iloc[0]
        for family in config["signal_families"]:
            for breadth in config["breadths"]:
                chosen = _select_names(frame, family, breadth, constraints["maximum_sector_weight"], constraints["minimum_distinct_sectors"])
                if chosen.empty:
                    continue
                for construction in config["portfolio_constructions"]:
                    key = f"{family}__n{breadth}__{construction}"
                    if construction == "rank_inverse_volatility":
                        conviction = percentile(chosen.set_index("cik10")[family]).pow(constraints["score_power"])
                        inverse_vol = 1.0 / chosen.set_index("cik10").downside_volatility.clip(lower=0.05)
                        raw = conviction * inverse_vol
                        sectors = chosen.set_index("cik10").sector
                        weights = _project_caps(raw, sectors, constraints["maximum_issuer_weight"], constraints["maximum_sector_weight"])
                    elif construction == "diagonal_shrinkage_signal_optimizer":
                        weights = _covariance_weights(chosen, weekly_returns, decision, family, config)
                    else:
                        raise ValueError(f"unknown construction {construction}")
                    targets.setdefault(key, []).extend(
                        {"decision_at": execution, "signal_at": decision, "cik10": cik, "weight": float(weight)}
                        for cik, weight in weights.items() if weight > 1e-12
                    )
    return {key: pd.DataFrame(rows) for key, rows in targets.items()}


def portfolio_path(targets: pd.DataFrame, weekly_returns: pd.DataFrame, cost_bps: int, extra_delay_weeks: int = 0, missing_scenario: str = "base_cash") -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    columns = weekly_returns.columns.astype(str)
    current = pd.Series(0.0, index=columns)
    previous = current.copy()
    schedule = {
        pd.Timestamp(date) + pd.Timedelta(weeks=extra_delay_weeks): frame
        for date, frame in targets.groupby("decision_at")
    }
    path, contributions, turnovers = [], [], []
    for date in weekly_returns.index:
        turnover = 0.0
        if date in schedule:
            updated = pd.Series(0.0, index=columns)
            frame = schedule[date]
            valid = frame[frame.cik10.astype(str).isin(columns)]
            updated.loc[valid.cik10.astype(str)] = valid.weight.to_numpy(float)
            turnover = float((updated - previous).abs().sum())
            current, previous = updated, updated.copy()
        observed = weekly_returns.loc[date].reindex(columns)
        if missing_scenario == "base_cash":
            observed = observed.fillna(0.0)
        elif missing_scenario == "adverse_total_loss":
            observed = observed.fillna(-1.0)
        else:
            raise ValueError("unknown missing scenario")
        contribution = current * observed
        path.append(float(contribution.sum()) - turnover * cost_bps / 10000.0)
        contributions.append(contribution.rename(date))
        turnovers.append(turnover)
    return pd.Series(path, index=weekly_returns.index, name="net_return"), pd.DataFrame(contributions), pd.Series(turnovers, index=weekly_returns.index, name="turnover")


def exposure_series(base_returns: pd.Series, rule: dict) -> pd.Series:
    if rule["kind"] == "fixed":
        return pd.Series(float(rule["gross"]), index=base_returns.index)
    if rule["kind"] != "volatility_target":
        raise ValueError("unknown exposure rule")
    lagged = base_returns.shift(1)
    volatility = lagged.rolling(rule["lookback_weeks"], min_periods=max(8, rule["lookback_weeks"] // 2)).std(ddof=1) * np.sqrt(52)
    gross = (rule["target_annual_volatility"] / volatility.replace(0, np.nan)).clip(rule["minimum_gross"], rule["maximum_gross"]).fillna(1.0)
    wealth = (1.0 + lagged.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.rolling(rule["drawdown_guard_weeks"], min_periods=2).max() - 1.0
    gross.loc[drawdown <= rule["drawdown_guard_threshold"]] = gross.loc[drawdown <= rule["drawdown_guard_threshold"]].clip(upper=rule["guarded_maximum_gross"])
    return gross


def apply_exposure(base_returns: pd.Series, gross: pd.Series, financing_rate: float, change_cost_bps: float) -> pd.Series:
    aligned = gross.reindex(base_returns.index).ffill().fillna(1.0)
    financing = (aligned - 1.0).clip(lower=0.0) * financing_rate / 52.0
    change_cost = aligned.diff().abs().fillna((aligned.iloc[0] - 1.0).__abs__()) * change_cost_bps / 10000.0
    return aligned * base_returns - financing - change_cost


def metrics(returns: pd.Series) -> dict[str, float]:
    clean = returns.fillna(0.0).astype(float)
    if clean.empty:
        return {"cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    wealth = (1.0 + clean).cumprod()
    years = len(clean) / 52.0
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if wealth.iloc[-1] > 0 and years > 0 else -1.0
    volatility = clean.std(ddof=1)
    sharpe = float(clean.mean() / volatility * np.sqrt(52)) if volatility > 0 else 0.0
    drawdown = float((wealth / wealth.cummax() - 1.0).min())
    return {"cagr": cagr, "sharpe": sharpe, "max_drawdown": drawdown}


def rolling_outperformance(candidate: pd.Series, control: pd.Series, weeks: int) -> tuple[float, int]:
    joined = pd.concat([candidate, control], axis=1).dropna()
    wins = []
    for end in range(weeks, len(joined) + 1):
        block = joined.iloc[end - weeks:end]
        wins.append(float((1.0 + block.iloc[:, 0]).prod() > (1.0 + block.iloc[:, 1]).prod()))
    return (float(np.mean(wins)) if wins else 0.0, len(wins))


def block_bootstrap_probability(excess: pd.Series, block: int, draws: int, seed: int) -> float:
    values = excess.dropna().to_numpy(float)
    if not len(values):
        return 0.0
    rng = np.random.default_rng(seed + block)
    positive = 0
    blocks_needed = int(np.ceil(len(values) / block))
    for _ in range(draws):
        starts = rng.integers(0, len(values), blocks_needed)
        sample = np.concatenate([values[(start + np.arange(block)) % len(values)] for start in starts])[:len(values)]
        positive += int(sample.mean() > 0)
    return positive / draws


def deflated_sharpe_probability(returns: pd.Series, trials: int) -> float:
    values = returns.dropna().to_numpy(float)
    if len(values) < 8 or np.std(values, ddof=1) <= 0:
        return 0.0
    sr = float(np.mean(values) / np.std(values, ddof=1))
    centered = values - np.mean(values)
    std = np.std(values, ddof=1)
    skew = float(np.mean((centered / std) ** 3))
    kurtosis = float(np.mean((centered / std) ** 4))
    variance = max(1e-12, (1.0 - skew * sr + (kurtosis - 1.0) * sr * sr / 4.0) / (len(values) - 1))
    sigma = np.sqrt(variance)
    normal = NormalDist()
    gamma = 0.5772156649
    expected_max = sigma * ((1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / trials) + gamma * normal.inv_cdf(1.0 - 1.0 / (trials * np.e)))
    return float(normal.cdf((sr - expected_max) / sigma))


def probability_of_backtest_overfitting(paths: pd.DataFrame, partitions: int = 8) -> float:
    """CSCV probability that the in-sample winner ranks below median OOS."""
    clean = paths.dropna(how="all").fillna(0.0)
    if clean.shape[1] < 2 or len(clean) < partitions or partitions % 2:
        return 1.0
    blocks = np.array_split(np.arange(len(clean)), partitions)
    failures = []
    for selected in combinations(range(partitions), partitions // 2):
        in_idx = np.concatenate([blocks[index] for index in selected])
        out_idx = np.concatenate([blocks[index] for index in range(partitions) if index not in selected])
        in_scores = clean.iloc[in_idx].mean().div(clean.iloc[in_idx].std(ddof=1).replace(0, np.nan)).fillna(-np.inf)
        winner = in_scores.idxmax()
        out_scores = clean.iloc[out_idx].mean().div(clean.iloc[out_idx].std(ddof=1).replace(0, np.nan)).fillna(-np.inf)
        percentile_rank = out_scores.rank(pct=True, method="average").get(winner, 0.0)
        failures.append(float(percentile_rank <= 0.5))
    return float(np.mean(failures)) if failures else 1.0


def verify_prefix_causality(original: pd.DataFrame, mutated: pd.DataFrame, cutoff: pd.Timestamp, columns: list[str]) -> None:
    left = original[original.decision_at <= cutoff][["decision_at", "cik10", *columns]].reset_index(drop=True)
    right = mutated[mutated.decision_at <= cutoff][["decision_at", "cik10", *columns]].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)
