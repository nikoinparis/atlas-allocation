from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"
LAYER1_DIR = ROOT / "data" / "02_layer1_signals"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"

CURRENT_PANEL = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

REDESIGNED_PANEL = [
    "dual_momentum_topn",
    "composite_calm_trend_participation",
    "composite_recovery_transition",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

REDESIGNED_SLEEVES = {
    "composite_calm_trend_participation": "S1 calm-trend participation sleeve",
    "composite_recovery_transition": "S2 recovery-transition sleeve",
    "composite_anti_chop_clarity": "S3 anti-chop / unstable-trend avoidance sleeve",
}

WEEKS_PER_YEAR = 52
HOLDOUT_WEEKS = 104
CASH_PROXY = "BIL"

CALM_UNIVERSE = ["QQQ", "SPY", "XLK", "XLI", "XLF", "XLY", "VUG", "XLV", "XLP", "XLU", "HYG", "LQD", "EFA", "VEA"]
RECOVERY_UNIVERSE = ["IWM", "QQQ", "SPY", "XLF", "XLI", "XLY", "VNQ", "HYG", "PDBC", "VWO", "EEM", "LQD"]
ANTI_CHOP_UNIVERSE = ["SPY", "QQQ", "EFA", "VEA", "LQD", "HYG", "GLD", "TLT", "PDBC", "DBA", "VNQ"]


def read_indexed_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "Date" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    return frame.set_index("Date").sort_index()


def read_return_series(name: str) -> pd.Series:
    frame = read_indexed_csv(LAYER2A_DIR / f"strategy_returns_{name}.csv")
    return frame["net_return"].rename(name)


def read_position_frame(name: str) -> pd.DataFrame:
    return read_indexed_csv(LAYER2A_DIR / f"strategy_positions_{name}.csv").fillna(0.0)


def annualized_return(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if series.empty:
        return np.nan
    return float((1.0 + series).prod() ** (WEEKS_PER_YEAR / len(series)) - 1.0)


def annualized_vol(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if len(series) < 2:
        return np.nan
    return float(series.std(ddof=1) * np.sqrt(WEEKS_PER_YEAR))


def max_drawdown(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if series.empty:
        return np.nan
    wealth = (1.0 + series).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def conditional_var(return_series: pd.Series, level: float = 0.05) -> float:
    series = pd.Series(return_series, dtype=float).dropna()
    if series.empty:
        return np.nan
    cutoff = series.quantile(level)
    tail = series[series <= cutoff]
    return float(tail.mean()) if len(tail) else np.nan


def compute_portfolio_path(weights: pd.DataFrame, next_week_returns: pd.DataFrame, transaction_cost_bps: float = 10.0) -> pd.DataFrame:
    weights = weights.reindex(index=next_week_returns.index, columns=next_week_returns.columns).fillna(0.0)
    gross_return = (weights * next_week_returns).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover) > 0:
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * (transaction_cost_bps / 10000.0)
    net_return = gross_return - cost
    wealth = (1.0 + net_return.fillna(0.0)).cumprod()
    drawdown = wealth.div(wealth.cummax()) - 1.0
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


def rank_to_signed(frame: pd.DataFrame, *, ascending: bool = True) -> pd.DataFrame:
    ranked = frame.rank(axis=1, pct=True, method="average", ascending=ascending)
    return ((ranked - 0.5) * 2.0).replace([np.inf, -np.inf], np.nan)


def top_k_weights(score_row: pd.Series, universe: list[str], *, k: int, power: float = 1.5, min_score: float = 0.0) -> pd.Series:
    score = pd.Series(score_row, dtype=float).reindex(universe).replace([np.inf, -np.inf], np.nan).dropna()
    score = score[score > min_score]
    if score.empty:
        return pd.Series(dtype=float)
    top = score.sort_values(ascending=False).head(k)
    if top.empty:
        return pd.Series(dtype=float)
    weights = top.pow(power)
    total = float(weights.sum())
    if total <= 0:
        return pd.Series(dtype=float)
    return weights / total


def write_strategy_files(name: str, positions: pd.DataFrame, path: pd.DataFrame) -> None:
    positions.to_csv(LAYER2A_DIR / f"strategy_positions_{name}.csv")
    path.to_csv(LAYER2A_DIR / f"strategy_returns_{name}.csv")


def summary_row(name: str, return_series: pd.Series, turnover: pd.Series, position_frame: pd.DataFrame) -> dict[str, float | str]:
    ann_return = annualized_return(return_series)
    ann_vol = annualized_vol(return_series)
    max_dd = max_drawdown(return_series)
    bil = position_frame.get(CASH_PROXY, pd.Series(0.0, index=position_frame.index))
    defensive_cols = [c for c in ["IEF", "SHY", "TLT", "TIP", "GLD", "LQD"] if c in position_frame.columns and c != CASH_PROXY]
    offensive_cols = [c for c in position_frame.columns if c not in set(defensive_cols + [CASH_PROXY])]
    return {
        "strategy_name": name,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": ann_return / ann_vol if pd.notna(ann_return) and pd.notna(ann_vol) and ann_vol > 0 else np.nan,
        "max_drawdown": max_dd,
        "calmar": ann_return / abs(max_dd) if pd.notna(ann_return) and pd.notna(max_dd) and max_dd != 0 else np.nan,
        "cvar_5": conditional_var(return_series),
        "turnover": float(turnover.dropna().mean()),
        "avg_bil": float(bil.mean()),
        "avg_offense": float(position_frame.reindex(columns=offensive_cols, fill_value=0.0).sum(axis=1).mean()),
        "avg_defense": float(position_frame.reindex(columns=defensive_cols, fill_value=0.0).sum(axis=1).mean()),
        "avg_cash": float(bil.mean()),
    }


def state_summary(name: str, return_series: pd.Series, positions: pd.DataFrame, market_state_history: pd.DataFrame) -> pd.DataFrame:
    state_map = market_state_history.reindex(return_series.index)["market_state"]
    bil = positions.get(CASH_PROXY, pd.Series(0.0, index=positions.index)).reindex(return_series.index).fillna(0.0)
    defensive_cols = [c for c in ["IEF", "SHY", "TLT", "TIP", "GLD", "LQD"] if c in positions.columns and c != CASH_PROXY]
    offensive_cols = [c for c in positions.columns if c not in set(defensive_cols + [CASH_PROXY])]
    offense = positions.reindex(columns=offensive_cols, fill_value=0.0).sum(axis=1).reindex(return_series.index).fillna(0.0)
    defense = positions.reindex(columns=defensive_cols, fill_value=0.0).sum(axis=1).reindex(return_series.index).fillna(0.0)
    joined = pd.DataFrame(
        {
            "net_return": return_series,
            "market_state": state_map,
            "bil_weight": bil,
            "offense_weight": offense,
            "defense_weight": defense,
        }
    ).dropna(subset=["market_state"])

    rows: list[dict[str, float | str | int]] = []
    for market_state, group in joined.groupby("market_state"):
        ann_return = annualized_return(group["net_return"])
        ann_vol = annualized_vol(group["net_return"])
        rows.append(
            {
                "strategy_name": name,
                "market_state": market_state,
                "observations": int(len(group)),
                "ann_return_state": ann_return,
                "ann_vol_state": ann_vol,
                "sharpe_state": ann_return / ann_vol if pd.notna(ann_return) and pd.notna(ann_vol) and ann_vol > 0 else np.nan,
                "avg_bil_state": float(group["bil_weight"].mean()),
                "avg_offense_state": float(group["offense_weight"].mean()),
                "avg_defense_state": float(group["defense_weight"].mean()),
                "avg_cash_state": float(group["bil_weight"].mean()),
            }
        )
    return pd.DataFrame(rows)


def split_dev_holdout(return_series: pd.Series, positions: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame, pd.DataFrame]:
    holdout_index = return_series.dropna().tail(HOLDOUT_WEEKS).index
    dev_index = return_series.index.difference(holdout_index)
    return (
        return_series.reindex(dev_index).dropna(),
        return_series.reindex(holdout_index).dropna(),
        positions.reindex(dev_index).fillna(0.0),
        positions.reindex(holdout_index).fillna(0.0),
    )


def build_signal_panel(file_name: str, value_col: str) -> pd.DataFrame:
    frame = pd.read_csv(LAYER1_DIR / file_name)
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    panel = frame.pivot(index="Date", columns="Ticker", values=value_col).sort_index()
    return panel


def load_inputs() -> dict[str, object]:
    weekly_prices = read_indexed_csv(DATA_HUB_DIR / "weekly_prices.csv")
    weekly_log_returns = read_indexed_csv(DATA_HUB_DIR / "weekly_returns.csv")
    weekly_simple_returns = np.expm1(weekly_log_returns)
    next_week_returns = weekly_simple_returns.shift(-1)
    market_state_history = read_indexed_csv(LAYER2B_DIR / "market_state_history.csv")

    trend_clarity = build_signal_panel("signal_trend_quality.csv", "trend_clarity_momentum_score_tradable")
    breadth_confirmation = build_signal_panel("signal_breadth_confirmation.csv", "breadth_confirmed_momentum_score_tradable")
    moving_average_distance = build_signal_panel("signal_moving_average_distance.csv", "moving_average_distance_score_tradable")
    contained_recovery = build_signal_panel("signal_contained_recovery.csv", "contained_recovery_quality_score_tradable")

    common_index = next_week_returns.index
    for panel in [trend_clarity, breadth_confirmation, moving_average_distance, contained_recovery, market_state_history]:
        common_index = common_index.intersection(panel.index)
    common_index = common_index.sort_values()

    weekly_simple_returns = weekly_simple_returns.reindex(common_index)
    next_week_returns = next_week_returns.reindex(common_index)
    weekly_prices = weekly_prices.reindex(common_index)
    market_state_history = market_state_history.reindex(common_index)
    trend_clarity = trend_clarity.reindex(common_index)
    breadth_confirmation = breadth_confirmation.reindex(common_index)
    moving_average_distance = moving_average_distance.reindex(common_index)
    contained_recovery = contained_recovery.reindex(common_index)

    mom_13 = ((1.0 + weekly_simple_returns).rolling(13, min_periods=8).apply(np.prod, raw=True) - 1.0).shift(1)
    mom_26 = ((1.0 + weekly_simple_returns).rolling(26, min_periods=8).apply(np.prod, raw=True) - 1.0).shift(1)
    vol_13 = weekly_simple_returns.rolling(13, min_periods=8).std(ddof=0).shift(1)
    dd_26 = weekly_simple_returns.rolling(26, min_periods=8).apply(
        lambda x: (np.cumprod(1.0 + x) / np.maximum.accumulate(np.cumprod(1.0 + x)) - 1.0).min(),
        raw=True,
    ).shift(1)

    return {
        "weekly_prices": weekly_prices,
        "weekly_simple_returns": weekly_simple_returns,
        "next_week_returns": next_week_returns,
        "market_state_history": market_state_history,
        "trend_clarity": trend_clarity,
        "breadth_confirmation": breadth_confirmation,
        "moving_average_distance": moving_average_distance,
        "contained_recovery": contained_recovery,
        "mom_13": rank_to_signed(mom_13, ascending=True),
        "mom_26": rank_to_signed(mom_26, ascending=True),
        "low_vol_score": rank_to_signed(vol_13, ascending=False),
        "drawdown_score": rank_to_signed(dd_26.abs(), ascending=False),
    }


def build_calm_trend_positions(inputs: dict[str, object]) -> pd.DataFrame:
    index = inputs["next_week_returns"].index
    market = inputs["market_state_history"]
    trend_clarity = inputs["trend_clarity"]
    breadth_confirmation = inputs["breadth_confirmation"]
    moving_average_distance = inputs["moving_average_distance"]
    mom_26 = inputs["mom_26"]
    low_vol = inputs["low_vol_score"]

    all_columns = list(dict.fromkeys(CALM_UNIVERSE + ["LQD", "TLT", CASH_PROXY]))
    rows: list[pd.Series] = []

    for date in index:
        row = pd.Series(0.0, index=all_columns, dtype=float, name=date)
        state = market.loc[date]
        calm_like = bool(
            state.get("market_trend_positive", 0.0) > 0.5
            and state.get("breadth_13w_mom", 0.0) > 0.0
            and state.get("transition_non_stress_prob", 0.0) >= 0.50
            and state.get("avg_corr_risk_off_z", 0.0) <= 0.55
        )
        strong_calm = bool(
            state.get("market_state") == "calm_trend"
            or (
                calm_like
                and state.get("transition_persistence_prob", 0.0) >= 0.50
                and state.get("google_fear_z_tradable", 0.0) <= 0.35
            )
        )
        score = (
            0.35 * trend_clarity.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.20 * moving_average_distance.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.15 * breadth_confirmation.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.10 * mom_26.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.20 * low_vol.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
        )
        eligible = [
            asset
            for asset in CALM_UNIVERSE
            if score.get(asset, 0.0) > 0.05
            and trend_clarity.loc[date].get(asset, 0.0) > 0.05
            and moving_average_distance.loc[date].get(asset, 0.0) > -0.10
        ]
        top_weights = top_k_weights(score, eligible, k=3, power=1.6, min_score=0.05)

        if strong_calm and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.80
            row["LQD"] = 0.10
            row["GLD"] = 0.10
        elif calm_like and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.65
            row["LQD"] = 0.20
            row["GLD"] = 0.15
        elif state.get("market_trend_positive", 0.0) > 0.5 and state.get("breadth_13w_mom", 0.0) > 0.0 and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.50
            row["LQD"] = 0.25
            row["GLD"] = 0.10
            row[CASH_PROXY] = 0.15
        else:
            row["LQD"] = 0.35
            row["TLT"] = 0.25
            row["GLD"] = 0.15
            row[CASH_PROXY] = 0.25
        rows.append(row)
    return pd.DataFrame(rows).sort_index().fillna(0.0)


def build_recovery_transition_positions(inputs: dict[str, object]) -> pd.DataFrame:
    index = inputs["next_week_returns"].index
    market = inputs["market_state_history"]
    trend_clarity = inputs["trend_clarity"]
    breadth_confirmation = inputs["breadth_confirmation"]
    moving_average_distance = inputs["moving_average_distance"]
    contained_recovery = inputs["contained_recovery"]
    mom_13 = inputs["mom_13"]

    all_columns = list(dict.fromkeys(RECOVERY_UNIVERSE + ["LQD", "TLT", CASH_PROXY]))
    rows: list[pd.Series] = []

    for date in index:
        row = pd.Series(0.0, index=all_columns, dtype=float, name=date)
        state = market.loc[date]
        improving = bool(
            state.get("transition_good_state_prob", 0.0) >= 0.42
            and state.get("breadth_change_4w", 0.0) > 0.0
            and state.get("market_drawdown", -1.0) > -0.18
            and state.get("recent_stress_26w", 0.0) <= 1.0
        )
        strong_recovery = bool(
            state.get("market_state") == "recovery_confirmed"
            or (
                improving
                and state.get("transition_persistence_prob", 0.0) >= 0.45
                and state.get("canary_breadth_pair", 0.0) >= 0.0
            )
        )
        score = (
            0.35 * breadth_confirmation.loc[date].reindex(RECOVERY_UNIVERSE).fillna(0.0)
            + 0.20 * contained_recovery.loc[date].reindex(RECOVERY_UNIVERSE).fillna(0.0)
            + 0.15 * trend_clarity.loc[date].reindex(RECOVERY_UNIVERSE).fillna(0.0)
            + 0.15 * moving_average_distance.loc[date].reindex(RECOVERY_UNIVERSE).fillna(0.0)
            + 0.15 * mom_13.loc[date].reindex(RECOVERY_UNIVERSE).fillna(0.0)
        )
        eligible = [
            asset
            for asset in RECOVERY_UNIVERSE
            if score.get(asset, 0.0) > 0.0
            and breadth_confirmation.loc[date].get(asset, 0.0) > -0.05
            and mom_13.loc[date].get(asset, 0.0) > -0.25
        ]
        top_weights = top_k_weights(score, eligible, k=3, power=1.5, min_score=0.0)

        if strong_recovery and not top_weights.empty:
            row.loc[top_weights.index] = top_weights
        elif improving and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.85
            row["LQD"] = 0.15
        elif state.get("market_trend_positive", 0.0) > 0.5 and state.get("transition_non_stress_prob", 0.0) > 0.45 and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.50
            row["LQD"] = 0.20
            row["HYG"] += 0.15
            row[CASH_PROXY] = 0.15
        else:
            row["LQD"] = 0.35
            row["HYG"] += 0.25
            row["TLT"] = 0.20
            row[CASH_PROXY] = 0.20
        rows.append(row)
    return pd.DataFrame(rows).sort_index().fillna(0.0)


def build_anti_chop_positions(inputs: dict[str, object]) -> pd.DataFrame:
    index = inputs["next_week_returns"].index
    market = inputs["market_state_history"]
    trend_clarity = inputs["trend_clarity"]
    moving_average_distance = inputs["moving_average_distance"]
    breadth_confirmation = inputs["breadth_confirmation"]
    low_vol = inputs["low_vol_score"]
    drawdown_score = inputs["drawdown_score"]
    mom_13 = inputs["mom_13"]

    all_columns = list(dict.fromkeys(ANTI_CHOP_UNIVERSE + ["GLD", "TLT", "LQD", CASH_PROXY]))
    rows: list[pd.Series] = []

    for date in index:
        row = pd.Series(0.0, index=all_columns, dtype=float, name=date)
        state = market.loc[date]
        unstable = bool(
            state.get("market_state") in {"neutral_mixed", "stressed_panic"}
            or state.get("avg_corr_risk_off_z", 0.0) > 0.55
            or state.get("transition_persistence_prob", 0.0) < 0.45
            or state.get("google_fear_z_tradable", 0.0) > 0.45
        )
        score = (
            0.35 * trend_clarity.loc[date].reindex(ANTI_CHOP_UNIVERSE).fillna(0.0)
            + 0.20 * low_vol.loc[date].reindex(ANTI_CHOP_UNIVERSE).fillna(0.0)
            + 0.15 * moving_average_distance.loc[date].reindex(ANTI_CHOP_UNIVERSE).fillna(0.0)
            + 0.15 * drawdown_score.loc[date].reindex(ANTI_CHOP_UNIVERSE).fillna(0.0)
            + 0.15 * mom_13.loc[date].reindex(ANTI_CHOP_UNIVERSE).fillna(0.0)
        )
        clean_assets = [
            asset
            for asset in ANTI_CHOP_UNIVERSE
            if score.get(asset, 0.0) > 0.05
            and trend_clarity.loc[date].get(asset, 0.0) > 0.0
            and low_vol.loc[date].get(asset, 0.0) > -0.10
            and drawdown_score.loc[date].get(asset, 0.0) > -0.15
        ]
        top_weights = top_k_weights(score, clean_assets, k=2, power=1.3, min_score=0.05)

        if not unstable and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.70
            row["GLD"] += 0.15
            row["LQD"] += 0.15
        elif not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.45
            row["GLD"] += 0.25
            row["TLT"] += 0.20
            row["LQD"] += 0.10
        else:
            row["GLD"] = 0.35
            row["TLT"] = 0.35
            row["LQD"] = 0.15
            row[CASH_PROXY] = 0.15
        rows.append(row)
    return pd.DataFrame(rows).sort_index().fillna(0.0)


def current_panel_diagnostics(market_state_history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    returns = pd.DataFrame({name: read_return_series(name) for name in CURRENT_PANEL})
    positions = {name: read_position_frame(name) for name in CURRENT_PANEL}
    corr = returns.corr()
    corr_rows: list[dict[str, float | str]] = []
    for i, left in enumerate(CURRENT_PANEL):
        for right in CURRENT_PANEL[i + 1 :]:
            corr_rows.append(
                {
                    "left_sleeve": left,
                    "right_sleeve": right,
                    "return_corr": float(corr.loc[left, right]),
                }
            )
    corr_df = pd.DataFrame(corr_rows).sort_values("return_corr", ascending=False).reset_index(drop=True)

    state_frames = [
        state_summary(name, returns[name], positions[name], market_state_history)
        for name in CURRENT_PANEL
    ]
    state_df = pd.concat(state_frames, ignore_index=True)

    role_rows: list[dict[str, float | str]] = []
    avg_abs_corr = corr.abs().where(~np.eye(len(corr), dtype=bool)).mean(axis=1)
    for name in CURRENT_PANEL:
        sleeve_state = state_df[state_df["strategy_name"] == name].copy()
        best_idx = sleeve_state["sharpe_state"].astype(float).idxmax()
        best_state = sleeve_state.loc[best_idx, "market_state"] if pd.notna(best_idx) else None
        role_rows.append(
            {
                "strategy_name": name,
                "avg_abs_corr_to_panel": float(avg_abs_corr[name]),
                "best_state_by_sharpe": best_state,
                "best_state_sharpe": float(sleeve_state["sharpe_state"].max()),
                "calm_trend_sharpe": float(sleeve_state.loc[sleeve_state["market_state"] == "calm_trend", "sharpe_state"].iloc[0]),
                "recovery_confirmed_sharpe": float(sleeve_state.loc[sleeve_state["market_state"] == "recovery_confirmed", "sharpe_state"].iloc[0]),
                "recovery_fragile_sharpe": float(sleeve_state.loc[sleeve_state["market_state"] == "recovery_fragile", "sharpe_state"].iloc[0]),
                "stressed_panic_sharpe": float(sleeve_state.loc[sleeve_state["market_state"] == "stressed_panic", "sharpe_state"].iloc[0]),
            }
        )
    role_df = pd.DataFrame(role_rows).sort_values(["avg_abs_corr_to_panel", "best_state_sharpe"], ascending=[False, False])
    return corr_df, state_df, role_df


def redesigned_diagnostics(
    market_state_history: pd.DataFrame,
    redesigned_returns: dict[str, pd.Series],
    redesigned_positions: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_names = CURRENT_PANEL + list(REDESIGNED_SLEEVES.keys())
    returns = pd.DataFrame({name: read_return_series(name) for name in CURRENT_PANEL})
    for name, series in redesigned_returns.items():
        returns[name] = series
    corr = returns[all_names].corr()

    corr_rows: list[dict[str, float | str]] = []
    for left in REDESIGNED_SLEEVES:
        for right in CURRENT_PANEL:
            corr_rows.append(
                {
                    "candidate_sleeve": left,
                    "reference_sleeve": right,
                    "return_corr": float(corr.loc[left, right]),
                }
            )
    corr_df = pd.DataFrame(corr_rows).sort_values(["candidate_sleeve", "return_corr"], ascending=[True, False]).reset_index(drop=True)

    summary_rows: list[dict[str, float | str]] = []
    holdout_rows: list[dict[str, float | str]] = []
    state_frames: list[pd.DataFrame] = []
    for name, label in REDESIGNED_SLEEVES.items():
        positions = redesigned_positions[name]
        returns_series = redesigned_returns[name]
        summary_rows.append(summary_row(name, returns_series, positions.diff().abs().sum(axis=1) * 0.5, positions))
        state_frames.append(state_summary(name, returns_series, positions, market_state_history))
        dev_returns, holdout_returns, dev_positions, holdout_positions = split_dev_holdout(returns_series, positions)
        holdout_rows.append(
            {
                "strategy_name": name,
                "full_ann_return": annualized_return(returns_series),
                "full_sharpe": annualized_return(returns_series) / annualized_vol(returns_series) if annualized_vol(returns_series) > 0 else np.nan,
                "dev_ann_return": annualized_return(dev_returns),
                "dev_sharpe": annualized_return(dev_returns) / annualized_vol(dev_returns) if annualized_vol(dev_returns) > 0 else np.nan,
                "holdout_ann_return": annualized_return(holdout_returns),
                "holdout_sharpe": annualized_return(holdout_returns) / annualized_vol(holdout_returns) if annualized_vol(holdout_returns) > 0 else np.nan,
                "dev_avg_bil": float(dev_positions.get(CASH_PROXY, pd.Series(0.0, index=dev_positions.index)).mean()),
                "holdout_avg_bil": float(holdout_positions.get(CASH_PROXY, pd.Series(0.0, index=holdout_positions.index)).mean()),
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    state_df = pd.concat(state_frames, ignore_index=True)
    holdout_df = pd.DataFrame(holdout_rows)
    return summary_df, state_df, corr_df, holdout_df


def universe_separability_summary(current_state_df: pd.DataFrame, redesigned_state_df: pd.DataFrame, current_corr_df: pd.DataFrame, redesigned_corr_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    key_states = ["calm_trend", "recovery_fragile", "recovery_confirmed", "stressed_panic"]
    rows: list[dict[str, float | str]] = []

    current_corr_mean = float(current_corr_df["return_corr"].mean())
    current_corr_abs_mean = float(current_corr_df["return_corr"].abs().mean())
    redesign_corr_abs_mean = float(redesigned_corr_df.groupby("candidate_sleeve")["return_corr"].mean().mean())

    def panel_state_rows(panel_name: str, state_df: pd.DataFrame) -> list[dict[str, float | str]]:
        out: list[dict[str, float | str]] = []
        for state in key_states:
            sub = state_df[state_df["market_state"] == state].sort_values("sharpe_state", ascending=False)
            if sub.empty:
                continue
            top = sub.iloc[0]
            second = sub.iloc[1] if len(sub) > 1 else None
            median = float(sub["sharpe_state"].median())
            out.append(
                {
                    "panel_name": panel_name,
                    "market_state": state,
                    "top_sleeve": top["strategy_name"],
                    "top_sharpe_state": float(top["sharpe_state"]),
                    "top_ann_return_state": float(top["ann_return_state"]),
                    "margin_vs_second_best_sharpe": float(top["sharpe_state"] - second["sharpe_state"]) if second is not None else np.nan,
                    "margin_vs_panel_median_sharpe": float(top["sharpe_state"] - median),
                }
            )
        return out

    state_rows = panel_state_rows("current_core_panel", current_state_df) + panel_state_rows("redesigned_candidate_panel", redesigned_state_df)
    summary_rows = [
        {
            "panel_name": "current_core_panel",
            "avg_pairwise_corr": current_corr_mean,
            "avg_abs_pairwise_corr": current_corr_abs_mean,
            "avg_top_minus_median_margin": float(pd.DataFrame(panel_state_rows("tmp", current_state_df))["margin_vs_panel_median_sharpe"].mean()),
        },
        {
            "panel_name": "redesigned_candidate_panel",
            "avg_pairwise_corr": np.nan,
            "avg_abs_pairwise_corr": redesign_corr_abs_mean,
            "avg_top_minus_median_margin": float(pd.DataFrame(panel_state_rows("tmp", redesigned_state_df))["margin_vs_panel_median_sharpe"].mean()),
        },
    ]
    return pd.DataFrame(summary_rows), pd.DataFrame(state_rows)


def panel_blend_diagnostics(
    market_state_history: pd.DataFrame,
    redesigned_returns: dict[str, pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    current_returns = {name: read_return_series(name) for name in CURRENT_PANEL}
    redesigned_panel_returns = {
        "dual_momentum_topn": current_returns["dual_momentum_topn"],
        "composite_regime_conditioned": current_returns["composite_regime_conditioned"],
        "taa_10m_sma": current_returns["taa_10m_sma"],
        **redesigned_returns,
    }
    panel_series = {
        "current_core_panel_blend": pd.concat([current_returns[name] for name in CURRENT_PANEL], axis=1).mean(axis=1),
        "redesigned_candidate_panel_blend": pd.concat([redesigned_panel_returns[name] for name in REDESIGNED_PANEL], axis=1).mean(axis=1),
    }

    summary_rows: list[dict[str, float | str]] = []
    state_rows: list[dict[str, float | str]] = []
    holdout_rows: list[dict[str, float | str]] = []
    for panel_name, series in panel_series.items():
        summary_rows.append(
            {
                "panel_name": panel_name,
                "ann_return": annualized_return(series),
                "ann_vol": annualized_vol(series),
                "sharpe": annualized_return(series) / annualized_vol(series) if annualized_vol(series) > 0 else np.nan,
                "max_drawdown": max_drawdown(series),
                "cvar_5": conditional_var(series),
            }
        )
        state_map = market_state_history.reindex(series.index)["market_state"]
        joined = pd.DataFrame({"net_return": series, "market_state": state_map}).dropna(subset=["market_state"])
        for market_state, group in joined.groupby("market_state"):
            ann_return = annualized_return(group["net_return"])
            ann_vol = annualized_vol(group["net_return"])
            state_rows.append(
                {
                    "panel_name": panel_name,
                    "market_state": market_state,
                    "ann_return_state": ann_return,
                    "ann_vol_state": ann_vol,
                    "sharpe_state": ann_return / ann_vol if pd.notna(ann_return) and pd.notna(ann_vol) and ann_vol > 0 else np.nan,
                }
            )

        dev_returns = series.dropna().iloc[:-HOLDOUT_WEEKS]
        holdout_returns = series.dropna().iloc[-HOLDOUT_WEEKS:]
        holdout_rows.append(
            {
                "panel_name": panel_name,
                "dev_ann_return": annualized_return(dev_returns),
                "dev_sharpe": annualized_return(dev_returns) / annualized_vol(dev_returns) if annualized_vol(dev_returns) > 0 else np.nan,
                "holdout_ann_return": annualized_return(holdout_returns),
                "holdout_sharpe": annualized_return(holdout_returns) / annualized_vol(holdout_returns) if annualized_vol(holdout_returns) > 0 else np.nan,
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(state_rows), pd.DataFrame(holdout_rows)


def main() -> None:
    inputs = load_inputs()
    market_state_history = inputs["market_state_history"]
    next_week_returns = inputs["next_week_returns"]

    current_corr_df, current_state_df, current_role_df = current_panel_diagnostics(market_state_history)

    redesigned_positions = {
        "composite_calm_trend_participation": build_calm_trend_positions(inputs),
        "composite_recovery_transition": build_recovery_transition_positions(inputs),
        "composite_anti_chop_clarity": build_anti_chop_positions(inputs),
    }

    redesigned_returns: dict[str, pd.Series] = {}
    for name, positions in redesigned_positions.items():
        aligned_next = next_week_returns.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
        path = compute_portfolio_path(positions, aligned_next)
        redesigned_returns[name] = path["net_return"]
        write_strategy_files(name, positions, path)

    redesigned_summary_df, redesigned_state_df, redesigned_corr_df, redesigned_holdout_df = redesigned_diagnostics(
        market_state_history,
        redesigned_returns,
        redesigned_positions,
    )
    separability_df, state_winner_df = universe_separability_summary(
        current_state_df[current_state_df["strategy_name"].isin(CURRENT_PANEL)],
        pd.concat(
            [
                current_state_df[current_state_df["strategy_name"].isin(["dual_momentum_topn", "composite_regime_conditioned", "taa_10m_sma"])],
                redesigned_state_df,
            ],
            ignore_index=True,
        ),
        current_corr_df,
        redesigned_corr_df,
    )
    panel_blend_summary_df, panel_blend_state_df, panel_blend_holdout_df = panel_blend_diagnostics(
        market_state_history,
        redesigned_returns,
    )

    current_corr_df.to_csv(LAYER2A_DIR / "phase_f_current_sleeve_correlation.csv", index=False)
    current_state_df.to_csv(LAYER2A_DIR / "phase_f_current_sleeve_state_summary.csv", index=False)
    current_role_df.to_csv(LAYER2A_DIR / "phase_f_current_sleeve_role_summary.csv", index=False)
    redesigned_summary_df.to_csv(LAYER2A_DIR / "phase_f_redesigned_sleeve_summary.csv", index=False)
    redesigned_state_df.to_csv(LAYER2A_DIR / "phase_f_redesigned_sleeve_state_summary.csv", index=False)
    redesigned_corr_df.to_csv(LAYER2A_DIR / "phase_f_redesigned_sleeve_correlation.csv", index=False)
    redesigned_holdout_df.to_csv(LAYER2A_DIR / "phase_f_redesigned_sleeve_holdout_summary.csv", index=False)
    separability_df.to_csv(LAYER2A_DIR / "phase_f_universe_separability_summary.csv", index=False)
    state_winner_df.to_csv(LAYER2A_DIR / "phase_f_state_winner_summary.csv", index=False)
    panel_blend_summary_df.to_csv(LAYER2A_DIR / "phase_f_panel_blend_summary.csv", index=False)
    panel_blend_state_df.to_csv(LAYER2A_DIR / "phase_f_panel_blend_state_summary.csv", index=False)
    panel_blend_holdout_df.to_csv(LAYER2A_DIR / "phase_f_panel_blend_holdout_summary.csv", index=False)

    print("Saved sleeve-separability artifacts:")
    for name in [
        "data/03_layer2a_strategy_logic/phase_f_current_sleeve_correlation.csv",
        "data/03_layer2a_strategy_logic/phase_f_current_sleeve_state_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_current_sleeve_role_summary.csv",
        "data/03_layer2a_strategy_logic/strategy_positions_composite_calm_trend_participation.csv",
        "data/03_layer2a_strategy_logic/strategy_returns_composite_calm_trend_participation.csv",
        "data/03_layer2a_strategy_logic/strategy_positions_composite_recovery_transition.csv",
        "data/03_layer2a_strategy_logic/strategy_returns_composite_recovery_transition.csv",
        "data/03_layer2a_strategy_logic/strategy_positions_composite_anti_chop_clarity.csv",
        "data/03_layer2a_strategy_logic/strategy_returns_composite_anti_chop_clarity.csv",
        "data/03_layer2a_strategy_logic/phase_f_redesigned_sleeve_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_redesigned_sleeve_state_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_redesigned_sleeve_correlation.csv",
        "data/03_layer2a_strategy_logic/phase_f_redesigned_sleeve_holdout_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_universe_separability_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_state_winner_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_panel_blend_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_panel_blend_state_summary.csv",
        "data/03_layer2a_strategy_logic/phase_f_panel_blend_holdout_summary.csv",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
