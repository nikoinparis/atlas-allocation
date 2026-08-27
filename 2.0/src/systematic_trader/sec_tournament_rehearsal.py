"""Synthetic-only rehearsal machinery for the frozen broad SEC tournament."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

REQUIRED_PANEL_COLUMNS = {
    "decision_at", "available_at", "cik10", "sector", "price_at_decision",
    "residual_momentum", "trend_quality", "quality_momentum", "event_score",
    "future_sector_relative_return",
}


def frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.sort_values(sorted(frame.columns)).to_csv(index=False, float_format="%.12g").encode()
    return hashlib.sha256(payload).hexdigest()


def validate_point_in_time_panel(panel: pd.DataFrame, horizon_weeks: int, decision_interval_weeks: int) -> dict:
    missing = REQUIRED_PANEL_COLUMNS - set(panel.columns)
    if missing:
        raise ValueError(f"panel missing {sorted(missing)}")
    data = panel.copy()
    for column in ["decision_at", "available_at"]:
        data[column] = pd.to_datetime(data[column], utc=True)
    if data.duplicated(["decision_at", "cik10"]).any():
        raise ValueError("duplicate decision/issuer keys")
    if (data.available_at > data.decision_at).any():
        raise ValueError("feature available after decision")
    if horizon_weeks > decision_interval_weeks:
        raise ValueError("target horizon exceeds one decision interval; frozen purge is insufficient")
    return {"rows": len(data), "decisions": data.decision_at.nunique(), "issuers": data.cik10.nunique(),
            "prefix_causal": True, "required_purge_decisions": 1}


def synthetic_panel(seed: int, assets: int, weekly_periods: int, decision_interval_weeks: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2021-08-20", periods=weekly_periods, freq="W-FRI", tz="UTC")
    names = [f"{index:010d}" for index in range(1, assets + 1)]
    sectors = {name: f"sector_{index % 6}" for index, name in enumerate(names)}
    market = rng.normal(0.0015, 0.025, weekly_periods)
    latent = rng.normal(0, 1, assets)
    returns = pd.DataFrame(index=dates, columns=names, dtype=float)
    for index, name in enumerate(names):
        idio = rng.normal(0, 0.045, weekly_periods)
        returns[name] = market + 0.002 * latent[index] + idio
    prices = 100.0 * (1.0 + returns).cumprod()
    decisions = dates[52:-13:decision_interval_weeks]
    rows = []
    for dpos, decision in enumerate(decisions):
        loc = dates.get_loc(decision)
        forward = prices.iloc[loc + 13].div(prices.iloc[loc]) - 1.0
        sector_median = forward.groupby(pd.Series(sectors)).transform("median")
        target = forward - sector_median
        trailing = prices.iloc[loc - 4].div(prices.iloc[loc - 26]) - 1.0
        trend = prices.iloc[loc].div(prices.iloc[loc - 52:loc + 1].max())
        quality = pd.Series(latent, index=names) + rng.normal(0, 0.35, assets)
        event = 0.5 + 0.15 * np.tanh(quality) + rng.normal(0, 0.05, assets)
        for name in names:
            rows.append({"decision_at": decision, "available_at": decision - pd.Timedelta(days=1),
                         "cik10": name, "sector": sectors[name], "price_at_decision": prices.loc[decision, name],
                         "residual_momentum": trailing[name], "trend_quality": trend[name],
                         "quality_momentum": quality[name], "event_score": event[name],
                         "future_sector_relative_return": target[name]})
    return pd.DataFrame(rows), returns


def nested_ridge_predictions(panel: pd.DataFrame, features: list[str], alphas: list[float], minimum_train_decisions: int = 8) -> pd.DataFrame:
    decisions = sorted(panel.decision_at.unique())
    output = []
    for test_pos in range(minimum_train_decisions + 1, len(decisions)):
        test_decision = decisions[test_pos]
        outer_train_decisions = decisions[:test_pos - 1]
        validation_decision = outer_train_decisions[-1]
        inner_train_decisions = outer_train_decisions[:-2]
        train = panel[panel.decision_at.isin(inner_train_decisions)].dropna(subset=[*features, "future_sector_relative_return"])
        validation = panel[panel.decision_at == validation_decision].dropna(subset=[*features, "future_sector_relative_return"])
        test = panel[panel.decision_at == test_decision].dropna(subset=features)
        if len(train) < 100 or validation.empty or test.empty:
            continue
        mean, scale = train[features].mean(), train[features].std(ddof=1).replace(0, 1).fillna(1)
        x_train = ((train[features] - mean) / scale).to_numpy(float)
        x_valid = ((validation[features] - mean) / scale).to_numpy(float)
        y_train = train.future_sector_relative_return.to_numpy(float)
        scores = []
        for alpha in alphas:
            coef = np.linalg.pinv(x_train.T @ x_train + np.eye(len(features)) * alpha) @ x_train.T @ y_train
            prediction_rank = pd.Series(x_valid @ coef).rank(method="average")
            target_rank = pd.Series(validation.future_sector_relative_return.to_numpy()).rank(method="average")
            scores.append((prediction_rank.corr(target_rank), alpha))
        selected_alpha = max(scores, key=lambda item: (-np.inf if pd.isna(item[0]) else item[0], -item[1]))[1]
        refit = panel[panel.decision_at.isin(outer_train_decisions)].dropna(subset=[*features, "future_sector_relative_return"])
        mean, scale = refit[features].mean(), refit[features].std(ddof=1).replace(0, 1).fillna(1)
        x_refit = ((refit[features] - mean) / scale).to_numpy(float)
        coef = np.linalg.pinv(x_refit.T @ x_refit + np.eye(len(features)) * selected_alpha) @ x_refit.T @ refit.future_sector_relative_return.to_numpy(float)
        block = test[["decision_at", "cik10"]].copy()
        block["score"] = ((test[features] - mean) / scale).to_numpy(float) @ coef
        block["selected_alpha"] = selected_alpha
        block["train_end"] = max(outer_train_decisions)
        output.append(block)
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame()


def top_weights(scores: pd.DataFrame, breadth: int, issuer_cap: float, sector_cap: float) -> pd.DataFrame:
    rows = []
    for decision, frame in scores.groupby("decision_at", sort=True):
        ranked = frame.dropna(subset=["score"]).sort_values(["score", "cik10"], ascending=[False, True])
        chosen, sector_counts = [], {}
        sector_limit = max(1, int(np.floor(sector_cap * breadth)))
        for row in ranked.itertuples(index=False):
            if sector_counts.get(row.sector, 0) >= sector_limit:
                continue
            chosen.append(row.cik10); sector_counts[row.sector] = sector_counts.get(row.sector, 0) + 1
            if len(chosen) == breadth: break
        weight = min(issuer_cap, 1.0 / max(1, len(chosen)))
        rows.extend({"decision_at": decision, "cik10": cik, "weight": weight} for cik in chosen)
    return pd.DataFrame(rows)


def portfolio_path(weights: pd.DataFrame, weekly_returns: pd.DataFrame, cost_bps: int, delay_weeks: int = 0,
                   missing_scenario: str = "base_cash") -> tuple[pd.Series, pd.DataFrame]:
    dates = weekly_returns.index
    current = pd.Series(0.0, index=weekly_returns.columns)
    path, contributions = [], []
    schedule = {pd.Timestamp(d) + pd.Timedelta(weeks=delay_weeks): f for d, f in weights.groupby("decision_at")}
    previous = current.copy()
    for date in dates:
        cost = 0.0
        if date in schedule:
            current = pd.Series(0.0, index=weekly_returns.columns)
            frame = schedule[date]
            current.loc[frame.cik10] = frame.weight.to_numpy()
            cost = float((current - previous).abs().sum()) * cost_bps / 10000.0
            previous = current.copy()
        observed = weekly_returns.loc[date].copy()
        if missing_scenario == "base_cash": observed = observed.fillna(0.0)
        elif missing_scenario == "adverse_total_loss": observed = observed.fillna(-1.0)
        else: raise ValueError("unknown missing scenario")
        asset_contribution = current * observed
        path.append(float(asset_contribution.sum()) - cost)
        contributions.append(asset_contribution.rename(date))
    return pd.Series(path, index=dates, name="net_return"), pd.DataFrame(contributions)


def metrics(returns: pd.Series) -> dict[str, float]:
    clean = returns.fillna(0.0)
    years = len(clean) / 52.0
    wealth = (1 + clean).cumprod()
    cagr = float(wealth.iloc[-1] ** (1 / years) - 1) if years else 0.0
    sharpe = float(clean.mean() / clean.std(ddof=1) * np.sqrt(52)) if clean.std(ddof=1) else 0.0
    drawdown = float((wealth / wealth.cummax() - 1).min())
    return {"cagr": cagr, "sharpe": sharpe, "max_drawdown": drawdown}


def rolling_share(candidate: pd.Series, control: pd.Series, weeks: int) -> tuple[float, int]:
    joined = pd.concat([candidate, control], axis=1).dropna()
    wins = []
    for end in range(weeks, len(joined) + 1):
        block = joined.iloc[end - weeks:end]
        wins.append(float((1 + block.iloc[:, 0]).prod() > (1 + block.iloc[:, 1]).prod()))
    return (float(np.mean(wins)) if wins else 0.0, len(wins))


def bootstrap_probability(excess: pd.Series, block: int, draws: int, seed: int) -> float:
    values = excess.dropna().to_numpy(float); rng = np.random.default_rng(seed + block)
    if not len(values): return 0.0
    means = []
    for _ in range(draws):
        starts = rng.integers(0, len(values), int(np.ceil(len(values) / block)))
        sample = np.concatenate([values[(start + np.arange(block)) % len(values)] for start in starts])[:len(values)]
        means.append(sample.mean())
    return float(np.mean(np.asarray(means) > 0))
