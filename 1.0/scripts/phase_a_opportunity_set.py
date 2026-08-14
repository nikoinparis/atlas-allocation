from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "02_layer1_alpha_signals.ipynb"
OUTPUT_DIR = ROOT / "data" / "02_layer1_signals"
STATE_HISTORY_PATH = ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv"


SETUP_CELLS = [1, 3, 4, 5, 6, 8]
BASE_SIGNAL_CELLS = [10, 12, 14, 16, 18, 20, 22, 24, 26]


def load_notebook_cells(notebook_path: Path, cell_indices: list[int], namespace: dict) -> dict:
    notebook = json.loads(notebook_path.read_text())
    for idx in cell_indices:
        cell = notebook["cells"][idx]
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if idx == 1:
            # Optional upstream data rebuild imports should not block Phase A
            # signal work when the local runtime lacks those packages.
            source = source.replace("except ImportError:", "except Exception:")
        exec(compile(source, f"{notebook_path.name}:cell_{idx}", "exec"), namespace)
    return namespace


def replace_or_append_row(df: pd.DataFrame, key_col: str, row: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame([row])
    out = df.copy()
    if key_col in out.columns:
        out = out[out[key_col] != row[key_col]]
    return pd.concat([out, pd.DataFrame([row])], ignore_index=True)


def rolling_trend_r2(panel: pd.DataFrame, window: int, min_periods: int) -> pd.DataFrame:
    def _r2(arr: np.ndarray) -> float:
        arr = np.asarray(arr, dtype=float)
        arr = arr[~np.isnan(arr)]
        n = len(arr)
        if n < min_periods:
            return np.nan
        x = np.arange(n, dtype=float)
        x_centered = x - x.mean()
        y_centered = arr - arr.mean()
        denom = np.sqrt(float(np.dot(x_centered, x_centered)) * float(np.dot(y_centered, y_centered)))
        if denom <= 0:
            return np.nan
        corr = float(np.dot(x_centered, y_centered) / denom)
        return corr * corr

    return panel.rolling(window=window, min_periods=min_periods).apply(_r2, raw=True)


def average_cross_sectional_correlation(stacked_a: pd.DataFrame, stacked_b: pd.DataFrame, min_assets: int) -> float:
    joint = stacked_a.join(stacked_b, how="inner", lsuffix="_a", rsuffix="_b").dropna()
    if joint.empty:
        return np.nan
    valid_counts = joint.groupby(level=0).size()
    valid_dates = valid_counts[valid_counts >= min_assets].index
    if len(valid_dates) == 0:
        return np.nan
    joint = joint.loc[joint.index.get_level_values(0).isin(valid_dates)]
    grouped_corr = joint.groupby(level=0)[["value_a", "value_b"]].corr(method="spearman")
    pair_corrs = grouped_corr.loc[(slice(None), "value_a"), "value_b"]
    pair_corrs.index = pair_corrs.index.droplevel(1)
    if pair_corrs.empty:
        return np.nan
    return float(pair_corrs.mean())


def broadcast_group_average(
    panel: pd.DataFrame,
    group_map: dict[str, str],
    *,
    min_group_size: int = 3,
    fallback: pd.Series | None = None,
) -> pd.DataFrame:
    out = pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    groups: dict[str, list[str]] = {}
    for ticker, group_name in group_map.items():
        if ticker in panel.columns:
            groups.setdefault(group_name, []).append(ticker)

    for tickers in groups.values():
        if len(tickers) < min_group_size:
            continue
        avg_series = panel[tickers].mean(axis=1)
        out.loc[:, tickers] = avg_series.to_numpy()[:, None]

    if fallback is not None:
        out = out.apply(lambda col: col.fillna(fallback))
    return out


def add_phase_a_signals(ns: dict) -> list[str]:
    weekly_prices = ns["weekly_prices"]
    weekly_log_returns = ns["weekly_log_returns"]
    weekly_simple_returns = ns["weekly_simple_returns"]
    research_universe = ns["research_universe"]
    asset_class_map = ns["asset_class_map"]
    asset_class_frame = ns["asset_class_frame"]
    panel_dict_to_long = ns["panel_dict_to_long"]
    register_cross_signal = ns["register_cross_signal"]
    register_time_series_signal = ns["register_time_series_signal"]
    apply_signal_lag = ns["apply_signal_lag"]
    trailing_simple_return = ns["trailing_simple_return"]
    annualized_realized_vol = ns["annualized_realized_vol"]
    panel_score = ns["panel_score"]
    add_manifest_record = ns["add_manifest_record"]
    total_lag_weeks = ns["total_lag_weeks"]
    OUTPUT_DIR = ns["OUTPUT_DIR"]

    new_signal_names: list[str] = []

    # ------------------------------------------------------------------
    # 1. Trend clarity momentum
    # Alpha Architect summary of Cai, Li, Keasey (2024) argues that the
    # clarity of the price path is a necessary condition for momentum.
    # Weekly approximation: 52-week log-price trend R^2 times 52-4 momentum.
    # ------------------------------------------------------------------
    trend_clarity_r2_observed = rolling_trend_r2(np.log(weekly_prices), window=52, min_periods=39)
    trend_clarity_mom_raw_observed = trailing_simple_return(weekly_prices, lookback=52, skip=4) * trend_clarity_r2_observed
    trend_clarity_mom_score_observed = panel_score(trend_clarity_mom_raw_observed, winsorize=True)
    trend_clarity_mom_score_tradable = apply_signal_lag(trend_clarity_mom_score_observed)
    trend_clarity_mom_raw_tradable = apply_signal_lag(trend_clarity_mom_raw_observed)

    trend_clarity_long = panel_dict_to_long(
        {
            "trend_clarity_r2_observed": trend_clarity_r2_observed,
            "trend_clarity_momentum_raw_observed": trend_clarity_mom_raw_observed,
            "trend_clarity_momentum_raw_tradable": trend_clarity_mom_raw_tradable,
            "trend_clarity_momentum_score_observed": trend_clarity_mom_score_observed,
            "trend_clarity_momentum_score_tradable": trend_clarity_mom_score_tradable,
        }
    ).merge(asset_class_frame, on="Ticker", how="left")
    trend_clarity_path = OUTPUT_DIR / "signal_trend_quality.csv"
    trend_clarity_long.to_csv(trend_clarity_path, index=False)
    register_cross_signal("trend_clarity_momentum", trend_clarity_mom_score_tradable)
    register_time_series_signal("trend_clarity_momentum", trend_clarity_mom_raw_tradable)
    add_manifest_record(
        signal_name="trend_clarity_momentum",
        file_name=trend_clarity_path.name,
        description="52-4 week momentum weighted by 52-week trend-regression R-squared as a path-clarity proxy.",
        category="trend_quality",
        cross_sectional_or_time_series="both",
        required_inputs=["weekly_prices.csv"],
        lookback="52 weeks",
        skip_period="4 weeks",
        lag_applied=total_lag_weeks("price"),
        normalization_method="winsorized cross-sectional rank of momentum times rolling trend-clarity R-squared",
        caveats="A weekly approximation of trend clarity; still related to medium-term momentum by construction.",
    )
    new_signal_names.append("trend_clarity_momentum")

    # ------------------------------------------------------------------
    # 2. Moving-average distance
    # Alpha Architect summary of Avramov, Kaplanski, Subrahmanyam (2023/24)
    # highlights short-vs-long moving-average distance as incremental to
    # classic momentum.
    # ------------------------------------------------------------------
    ma_short = weekly_prices.rolling(13, min_periods=8).mean()
    ma_long = weekly_prices.rolling(52, min_periods=26).mean()
    moving_average_distance_observed = ma_short.div(ma_long).sub(1.0)
    moving_average_distance_score_observed = panel_score(moving_average_distance_observed, winsorize=True)
    moving_average_distance_score_tradable = apply_signal_lag(moving_average_distance_score_observed)
    moving_average_distance_tradable = apply_signal_lag(moving_average_distance_observed)

    mad_long = panel_dict_to_long(
        {
            "ma_13w_observed": ma_short,
            "ma_52w_observed": ma_long,
            "moving_average_distance_observed": moving_average_distance_observed,
            "moving_average_distance_tradable": moving_average_distance_tradable,
            "moving_average_distance_score_observed": moving_average_distance_score_observed,
            "moving_average_distance_score_tradable": moving_average_distance_score_tradable,
        }
    ).merge(asset_class_frame, on="Ticker", how="left")
    mad_path = OUTPUT_DIR / "signal_moving_average_distance.csv"
    mad_long.to_csv(mad_path, index=False)
    register_cross_signal("moving_average_distance", moving_average_distance_score_tradable)
    register_time_series_signal("moving_average_distance", moving_average_distance_tradable)
    add_manifest_record(
        signal_name="moving_average_distance",
        file_name=mad_path.name,
        description="13-week versus 52-week moving-average distance as a trend setup-quality signal.",
        category="trend_quality",
        cross_sectional_or_time_series="both",
        required_inputs=["weekly_prices.csv"],
        lookback="13 and 52 weeks",
        skip_period="0 weeks",
        lag_applied=total_lag_weeks("price"),
        normalization_method="winsorized cross-sectional rank of 13w / 52w moving-average distance",
        caveats="Closely related to trend strength, but intended to capture setup quality rather than only cumulative return.",
    )
    new_signal_names.append("moving_average_distance")

    # ------------------------------------------------------------------
    # 3. Breadth-confirmed momentum
    # Inspired by breadth-momentum / ensemble literature: own momentum is
    # more credible when peer breadth is also healthy. Use asset-class
    # confirmation when enough peers exist and fall back to global breadth.
    # ------------------------------------------------------------------
    own_mom_26_4w = trailing_simple_return(weekly_prices, lookback=26, skip=4)
    ma_26 = weekly_prices.rolling(26, min_periods=13).mean()
    breadth_flag = ((own_mom_26_4w > 0) & (weekly_prices > ma_26)).astype(float)
    global_breadth = breadth_flag[[c for c in research_universe if c in breadth_flag.columns]].mean(axis=1)
    asset_class_breadth = broadcast_group_average(breadth_flag, asset_class_map, min_group_size=3, fallback=global_breadth)
    asset_class_breadth = asset_class_breadth.clip(lower=0.0, upper=1.0)
    signed_breadth = asset_class_breadth * 2.0 - 1.0
    own_mom_sign = np.sign(own_mom_26_4w.fillna(0.0))
    breadth_multiplier = (1.0 + 0.5 * own_mom_sign * signed_breadth).clip(lower=0.50, upper=1.50)
    breadth_confirmed_mom_observed = own_mom_26_4w * breadth_multiplier
    breadth_confirmed_mom_score_observed = panel_score(breadth_confirmed_mom_observed, winsorize=True)
    breadth_confirmed_mom_score_tradable = apply_signal_lag(breadth_confirmed_mom_score_observed)
    breadth_confirmed_mom_tradable = apply_signal_lag(breadth_confirmed_mom_observed)

    breadth_long = panel_dict_to_long(
        {
            "own_momentum_26_4w_observed": own_mom_26_4w,
            "asset_class_breadth_confirmation_observed": asset_class_breadth,
            "breadth_confirmation_multiplier_observed": breadth_multiplier,
            "breadth_confirmed_momentum_observed": breadth_confirmed_mom_observed,
            "breadth_confirmed_momentum_tradable": breadth_confirmed_mom_tradable,
            "breadth_confirmed_momentum_score_observed": breadth_confirmed_mom_score_observed,
            "breadth_confirmed_momentum_score_tradable": breadth_confirmed_mom_score_tradable,
        }
    ).merge(asset_class_frame, on="Ticker", how="left")
    breadth_path = OUTPUT_DIR / "signal_breadth_confirmation.csv"
    breadth_long.to_csv(breadth_path, index=False)
    register_cross_signal("breadth_confirmed_momentum", breadth_confirmed_mom_score_tradable)
    register_time_series_signal("breadth_confirmed_momentum", breadth_confirmed_mom_tradable)
    add_manifest_record(
        signal_name="breadth_confirmed_momentum",
        file_name=breadth_path.name,
        description="26-4 week momentum strengthened or weakened by asset-class breadth confirmation.",
        category="cross_asset_confirmation",
        cross_sectional_or_time_series="both",
        required_inputs=["weekly_prices.csv", "universe_metadata.csv"],
        lookback="26 weeks",
        skip_period="4 weeks",
        lag_applied=total_lag_weeks("price"),
        normalization_method="winsorized cross-sectional rank of 26-4 momentum scaled by signed peer breadth confirmation",
        caveats="Uses asset-class peer breadth as a causal confirmation proxy; thin groups fall back to global breadth.",
    )
    new_signal_names.append("breadth_confirmed_momentum")

    # ------------------------------------------------------------------
    # 4. Contained recovery quality
    # A recovery is more actionable when it is both profitable and orderly.
    # Blend short-horizon return, distance from 26-week highs, and recent
    # realized volatility into a single signed, asset-level recovery score.
    # ------------------------------------------------------------------
    recovery_mom_13w = trailing_simple_return(weekly_prices, lookback=13, skip=0)
    recovery_vol_13w = annualized_realized_vol(weekly_log_returns, window=13, min_periods=8).clip(lower=0.03)
    recovery_drawdown_26w = weekly_prices.div(weekly_prices.rolling(26, min_periods=13).max()).sub(1.0)
    contained_recovery_multiplier = (1.0 + recovery_drawdown_26w.clip(lower=-0.35, upper=0.0)).clip(lower=0.65, upper=1.0)
    contained_recovery_quality_observed = recovery_mom_13w.div(recovery_vol_13w).mul(contained_recovery_multiplier)
    contained_recovery_quality_score_observed = panel_score(contained_recovery_quality_observed, winsorize=True)
    contained_recovery_quality_score_tradable = apply_signal_lag(contained_recovery_quality_score_observed)
    contained_recovery_quality_tradable = apply_signal_lag(contained_recovery_quality_observed)

    contained_long = panel_dict_to_long(
        {
            "recovery_momentum_13w_observed": recovery_mom_13w,
            "recovery_vol_13w_observed": recovery_vol_13w,
            "recovery_drawdown_26w_observed": recovery_drawdown_26w,
            "contained_recovery_multiplier_observed": contained_recovery_multiplier,
            "contained_recovery_quality_observed": contained_recovery_quality_observed,
            "contained_recovery_quality_tradable": contained_recovery_quality_tradable,
            "contained_recovery_quality_score_observed": contained_recovery_quality_score_observed,
            "contained_recovery_quality_score_tradable": contained_recovery_quality_score_tradable,
        }
    ).merge(asset_class_frame, on="Ticker", how="left")
    contained_path = OUTPUT_DIR / "signal_contained_recovery.csv"
    contained_long.to_csv(contained_path, index=False)
    register_cross_signal("contained_recovery_quality", contained_recovery_quality_score_tradable)
    register_time_series_signal("contained_recovery_quality", contained_recovery_quality_tradable)
    add_manifest_record(
        signal_name="contained_recovery_quality",
        file_name=contained_path.name,
        description="13-week recovery strength scaled by 13-week volatility and penalized by distance from 26-week highs.",
        category="recovery_quality",
        cross_sectional_or_time_series="both",
        required_inputs=["weekly_prices.csv", "weekly_returns.csv"],
        lookback="13 and 26 weeks",
        skip_period="0 weeks",
        lag_applied=total_lag_weeks("price"),
        normalization_method="winsorized cross-sectional rank of volatility-scaled recovery return times a drawdown containment multiplier",
        caveats="Targets orderly recoveries; may behave like quality-adjusted momentum in already benign states.",
    )
    new_signal_names.append("contained_recovery_quality")

    return new_signal_names


def build_state_buckets(market_state_history: pd.DataFrame) -> pd.Series:
    state = market_state_history["market_state"].copy()
    strong_neutral = (
        state.eq("neutral_mixed")
        & market_state_history["market_trend_positive"].fillna(0.0).gt(0.0)
        & market_state_history["breadth_sma_43"].fillna(0.0).ge(0.55)
        & market_state_history["breadth_26w_mom"].fillna(0.0).ge(0.50)
    )
    out = state.copy()
    out.loc[strong_neutral] = "strong_neutral"
    out.loc[state.eq("neutral_mixed") & ~strong_neutral] = "weak_neutral"
    return out


def finalize_signal_outputs(ns: dict, new_signal_names: list[str]) -> dict:
    OUTPUT_DIR = ns["OUTPUT_DIR"]
    research_universe = ns["research_universe"]
    market_proxy_ticker = ns["market_proxy_ticker"]
    cross_summary_table = pd.concat(ns["cross_sectional_summaries"], ignore_index=True) if ns["cross_sectional_summaries"] else pd.DataFrame()
    cross_ic_ts_table = pd.concat(ns["cross_sectional_ic_timeseries"], ignore_index=True) if ns["cross_sectional_ic_timeseries"] else pd.DataFrame()
    time_summary_table = pd.concat(ns["time_series_summaries"], ignore_index=True) if ns["time_series_summaries"] else pd.DataFrame()
    cost_summary_table = pd.concat(ns["cost_summaries"], ignore_index=True) if ns["cost_summaries"] else pd.DataFrame()

    ic_summary_path = OUTPUT_DIR / "signal_ic_by_horizon.csv"
    cross_summary_table.to_csv(ic_summary_path, index=False)

    stacked_signal_panels = {
        name: panel.stack().rename("value").to_frame()
        for name, panel in ns["cross_signal_panels"].items()
    }

    signal_names_for_redundancy = sorted(ns["cross_signal_panels"].keys())
    redundancy_matrix = pd.DataFrame(index=signal_names_for_redundancy, columns=signal_names_for_redundancy, dtype=float)
    for signal_name in signal_names_for_redundancy:
        redundancy_matrix.loc[signal_name, signal_name] = 1.0
    for left_name, right_name in combinations(signal_names_for_redundancy, 2):
        corr = average_cross_sectional_correlation(
            stacked_signal_panels[left_name],
            stacked_signal_panels[right_name],
            min_assets=ns["MIN_CROSS_SECTION"],
        )
        redundancy_matrix.loc[left_name, right_name] = corr
        redundancy_matrix.loc[right_name, left_name] = corr

    redundancy_path = OUTPUT_DIR / "signal_redundancy_matrix.csv"
    redundancy_matrix.to_csv(redundancy_path)

    pair_rows = []
    for left_name, right_name in combinations(signal_names_for_redundancy, 2):
        corr = redundancy_matrix.loc[left_name, right_name]
        pair_rows.append(
            {
                "left_signal": left_name,
                "right_signal": right_name,
                "avg_cs_corr": corr,
                "abs_avg_cs_corr": abs(corr) if pd.notna(corr) else np.nan,
            }
        )
    pair_table = pd.DataFrame(pair_rows)
    if pair_table.empty:
        pair_table = pd.DataFrame(columns=["left_signal", "right_signal", "avg_cs_corr", "abs_avg_cs_corr"])
    else:
        pair_table = pair_table.sort_values("abs_avg_cs_corr", ascending=False)
    redundancy_pairs_path = OUTPUT_DIR / "signal_redundancy_pairs.csv"
    pair_table.to_csv(redundancy_pairs_path, index=False)

    all_signal_names = sorted(
        set(cross_summary_table.get("signal_name", pd.Series(dtype=str)).dropna().tolist())
        | set(time_summary_table.get("signal_name", pd.Series(dtype=str)).dropna().tolist())
        | set(cost_summary_table.get("signal_name", pd.Series(dtype=str)).dropna().tolist())
    )
    signal_summary = pd.DataFrame(index=all_signal_names)

    if not cross_summary_table.empty:
        cross_agg = cross_summary_table.groupby("signal_name").agg(
            avg_mean_ic=("mean_ic", "mean"),
            avg_ic_tstat=("ic_tstat", "mean"),
            avg_ic_tstat_nw=("ic_tstat_nw", "mean"),
            positive_horizon_share=("mean_ic", lambda s: (s > 0).mean()),
            avg_cross_coverage=("mean_coverage", "mean"),
        )
        signal_summary = signal_summary.join(cross_agg, how="left")

    if not time_summary_table.empty:
        time_agg = time_summary_table.groupby("signal_name").agg(
            avg_signed_strategy_mean=("signed_strategy_mean", "mean"),
            avg_signed_strategy_tstat=("signed_strategy_tstat", "mean"),
            avg_signed_strategy_tstat_nw=("signed_strategy_tstat_nw", "mean"),
            avg_directional_hit_rate=("directional_hit_rate", "mean"),
            positive_ts_horizon_share=("signed_strategy_mean", lambda s: (s > 0).mean()),
        )
        signal_summary = signal_summary.join(time_agg, how="left")

    if not cost_summary_table.empty:
        cost_10 = cost_summary_table[cost_summary_table["cost_bps"] == 10].set_index("signal_name")
        signal_summary = signal_summary.join(
            cost_10[["ann_return", "ann_vol", "sharpe", "avg_weekly_turnover"]].rename(
                columns={
                    "ann_return": "ann_return_10bps",
                    "ann_vol": "ann_vol_10bps",
                    "sharpe": "net_sharpe_10bps",
                }
            ),
            how="left",
        )

    if not redundancy_matrix.empty:
        avg_abs_corr = redundancy_matrix.abs().replace(1.0, np.nan).mean(axis=1)
        signal_summary["avg_abs_redundancy"] = avg_abs_corr
        signal_summary["distinctiveness_score"] = 1.0 - avg_abs_corr

    for required_col in [
        "avg_ic_tstat",
        "avg_ic_tstat_nw",
        "avg_signed_strategy_tstat",
        "avg_signed_strategy_tstat_nw",
        "positive_horizon_share",
        "positive_ts_horizon_share",
        "net_sharpe_10bps",
        "avg_weekly_turnover",
        "avg_cross_coverage",
        "distinctiveness_score",
    ]:
        if required_col not in signal_summary.columns:
            signal_summary[required_col] = np.nan

    signal_summary["primary_validation_stat"] = (
        signal_summary["avg_ic_tstat_nw"]
        .fillna(signal_summary["avg_ic_tstat"])
        .fillna(signal_summary["avg_signed_strategy_tstat_nw"])
        .fillna(signal_summary["avg_signed_strategy_tstat"])
    )
    signal_summary["robust_horizon_share"] = signal_summary["positive_horizon_share"].fillna(signal_summary["positive_ts_horizon_share"])
    signal_summary["validation_quality_score"] = (
        signal_summary["primary_validation_stat"].fillna(0.0)
        + 0.5 * signal_summary["robust_horizon_share"].fillna(0.0)
        + 0.5 * signal_summary["net_sharpe_10bps"].fillna(0.0)
        + 0.25 * signal_summary["distinctiveness_score"].fillna(0.0)
        - 0.1 * signal_summary["avg_weekly_turnover"].fillna(0.0)
    )
    signal_summary = signal_summary.sort_values("validation_quality_score", ascending=False).reset_index().rename(columns={"index": "signal_name"})

    def recommendation_label(row: pd.Series) -> str:
        if pd.notna(row["validation_quality_score"]) and row["validation_quality_score"] >= signal_summary["validation_quality_score"].quantile(0.75):
            return "strong"
        if pd.notna(row["validation_quality_score"]) and row["validation_quality_score"] <= signal_summary["validation_quality_score"].quantile(0.25):
            return "weak"
        if pd.notna(row["robust_horizon_share"]) and row["robust_horizon_share"] >= 0.8:
            return "robust"
        return "mixed"

    signal_summary["recommendation"] = signal_summary.apply(recommendation_label, axis=1)

    coverage_lookup = {}
    if not cross_summary_table.empty:
        coverage_lookup = (
            cross_summary_table[cross_summary_table["horizon_weeks"] == 1]
            .set_index("signal_name")["mean_coverage"]
            .div(len(research_universe))
            .to_dict()
        )

    eligibility_template = [
        {"signal_name": "tsmom_vol_scaled", "equities": "High", "bonds": "High", "reits": "Medium", "commodities": "High", "fx": "Medium", "base_proxy_quality": "High", "notes": "Clean price-based trend signal."},
        {"signal_name": "xsmom_global", "equities": "High", "bonds": "High", "reits": "Low", "commodities": "High", "fx": "Low", "base_proxy_quality": "High", "notes": "Global relative-strength signal across the universe."},
        {"signal_name": "xsmom_asset_class_neutral", "equities": "High", "bonds": "High", "reits": "Low", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Useful when broad asset-class rotation dominates."},
        {"signal_name": "reversal_1w_global", "equities": "Medium", "bonds": "Medium", "reits": "Low", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "High", "notes": "Fast and regime-sensitive."},
        {"signal_name": "reversal_1w_asset_class_neutral", "equities": "Medium", "bonds": "Medium", "reits": "Low", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Cleaner within-group reversal where enough names exist."},
        {"signal_name": "reversal_4w_global", "equities": "Medium", "bonds": "Medium", "reits": "Low", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "High", "notes": "Slower reversal proxy."},
        {"signal_name": "reversal_4w_asset_class_neutral", "equities": "Medium", "bonds": "Medium", "reits": "Low", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Neutral version for slower reversal."},
        {"signal_name": "multi_mom_equal", "equities": "High", "bonds": "High", "reits": "Medium", "commodities": "High", "fx": "Medium", "base_proxy_quality": "High", "notes": "Blended trend signal."},
        {"signal_name": "multi_mom_invvol", "equities": "High", "bonds": "High", "reits": "Medium", "commodities": "High", "fx": "Medium", "base_proxy_quality": "High", "notes": "More stable blended trend signal."},
        {"signal_name": "residual_momentum", "equities": "High", "bonds": "Medium", "reits": "Medium", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "Medium", "notes": f"Depends on explicit market proxy {market_proxy_ticker}."},
        {"signal_name": "carry_proxy", "equities": "Low", "bonds": "High", "reits": "Medium", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Low", "notes": "Proxy only; strongest where distributions are economically meaningful."},
        {"signal_name": "carry_proxy_asset_class_neutral", "equities": "Low", "bonds": "High", "reits": "Medium", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Low", "notes": "Within-asset-class version of the carry proxy."},
        {"signal_name": "value_proxy", "equities": "Medium", "bonds": "Medium", "reits": "Medium", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Own-history value, not balance-sheet value."},
        {"signal_name": "value_proxy_asset_class_neutral", "equities": "Medium", "bonds": "Medium", "reits": "Medium", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Within-asset-class version of own-history value."},
        {"signal_name": "bab_proxy", "equities": "High", "bonds": "Medium", "reits": "Low", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Low-beta proxy, not full BAB construction."},
        {"signal_name": "bab_proxy_asset_class_neutral", "equities": "High", "bonds": "Medium", "reits": "Low", "commodities": "Low", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Within-asset-class low-beta ranking."},
        {"signal_name": "quality_proxy", "equities": "Medium", "bonds": "Medium", "reits": "Medium", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "High", "notes": "Return-path stability proxy."},
        {"signal_name": "quality_proxy_asset_class_neutral", "equities": "Medium", "bonds": "Medium", "reits": "Medium", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "High", "notes": "Within-asset-class quality ranking."},
        {"signal_name": "trend_clarity_momentum", "equities": "High", "bonds": "High", "reits": "Medium", "commodities": "High", "fx": "Medium", "base_proxy_quality": "High", "notes": "Momentum weighted by trend-path clarity (R-squared)."},
        {"signal_name": "moving_average_distance", "equities": "High", "bonds": "High", "reits": "Medium", "commodities": "Medium", "fx": "Medium", "base_proxy_quality": "High", "notes": "Setup-quality signal from short-vs-long moving-average distance."},
        {"signal_name": "breadth_confirmed_momentum", "equities": "High", "bonds": "High", "reits": "Low", "commodities": "High", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Own momentum confirmed by peer breadth in the same asset class."},
        {"signal_name": "contained_recovery_quality", "equities": "High", "bonds": "Medium", "reits": "Medium", "commodities": "Medium", "fx": "Low", "base_proxy_quality": "Medium", "notes": "Rewards orderly recoveries near highs and penalizes volatile rebounds."},
        {"signal_name": "vix_term_structure_regime", "equities": "Conditioning", "bonds": "Conditioning", "reits": "Conditioning", "commodities": "Conditioning", "fx": "Conditioning", "base_proxy_quality": "High", "notes": "Market-level conditioning feature, not a per-ETF alpha."},
        {"signal_name": "macro_risk_score", "equities": "Conditioning", "bonds": "Conditioning", "reits": "Conditioning", "commodities": "Conditioning", "fx": "Conditioning", "base_proxy_quality": "Medium", "notes": "Macro conditioning signal with conservative lagging."},
        {"signal_name": "google_fear_regime", "equities": "Conditioning", "bonds": "Conditioning", "reits": "Conditioning", "commodities": "Conditioning", "fx": "Conditioning", "base_proxy_quality": "Low", "notes": "Noisy fear / sentiment conditioning feature."},
    ]

    def reliability_label(base_proxy_quality: str, coverage_ratio: float) -> str:
        score = {"High": 2, "Medium": 1, "Low": 0}.get(base_proxy_quality, 1)
        if pd.notna(coverage_ratio):
            if coverage_ratio >= 0.8:
                score += 1
            elif coverage_ratio < 0.4:
                score -= 1
        score = max(0, min(3, score))
        return {3: "High", 2: "Medium-High", 1: "Medium", 0: "Low"}[score]

    eligibility_rows = []
    for row in eligibility_template:
        coverage_ratio = coverage_lookup.get(row["signal_name"], np.nan)
        row["coverage_ratio_h1"] = coverage_ratio
        row["reliability"] = reliability_label(row["base_proxy_quality"], coverage_ratio)
        eligibility_rows.append(row)
    eligibility_df = pd.DataFrame(eligibility_rows)
    eligibility_path = OUTPUT_DIR / "signal_eligibility_matrix.csv"
    eligibility_df.to_csv(eligibility_path, index=False)

    summary_path = OUTPUT_DIR / "signal_summary_table.csv"
    signal_summary.to_csv(summary_path, index=False)

    manifest_path = OUTPUT_DIR / "signal_manifest.json"
    manifest_records = []
    seen = set()
    for record in ns["signal_manifest_records"]:
        key = record.get("signal_name")
        if key in seen:
            continue
        manifest_records.append(record)
        seen.add(key)
    manifest_path.write_text(json.dumps(manifest_records, indent=2))

    market_state_history = pd.read_csv(STATE_HISTORY_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    state_bucket = build_state_buckets(market_state_history)
    phase_a_state = (
        cross_ic_ts_table[cross_ic_ts_table["signal_name"].isin(new_signal_names)]
        .merge(state_bucket.rename("state_bucket"), left_on="Date", right_index=True, how="left")
    )
    phase_a_state_summary = (
        phase_a_state.groupby(["signal_name", "state_bucket"])
        .agg(
            avg_state_mean_ic=("ic", "mean"),
            avg_state_nw_tstat=("ic", ns["newey_west_tstat"]),
            avg_state_hit_rate=("ic", lambda s: (pd.Series(s) > 0).mean()),
            avg_state_coverage=("coverage", "mean"),
            n_state_dates=("Date", "nunique"),
        )
        .reset_index()
    )
    phase_a_state_path = OUTPUT_DIR / "phase_a_signal_state_summary.csv"
    phase_a_state_summary.to_csv(phase_a_state_path, index=False)

    existing_anchor_signals = ["xsmom_global", "multi_mom_invvol", "tsmom_vol_scaled", "residual_momentum"]
    candidate_rows = []
    summary_lookup = signal_summary.set_index("signal_name")
    for signal_name in new_signal_names:
        row = summary_lookup.loc[signal_name]
        state_slice = phase_a_state_summary[phase_a_state_summary["signal_name"] == signal_name]
        state_lookup = state_slice.set_index("state_bucket")["avg_state_mean_ic"].to_dict()
        corr_context = {
            f"corr_to_{anchor}": redundancy_matrix.loc[signal_name, anchor]
            if anchor in redundancy_matrix.index and signal_name in redundancy_matrix.index
            else np.nan
            for anchor in existing_anchor_signals
        }
        candidate_rows.append(
            {
                "signal_name": signal_name,
                "avg_mean_ic": row.get("avg_mean_ic"),
                "avg_ic_tstat_nw": row.get("avg_ic_tstat_nw"),
                "avg_cross_coverage": row.get("avg_cross_coverage"),
                "avg_abs_redundancy": row.get("avg_abs_redundancy"),
                "distinctiveness_score": row.get("distinctiveness_score"),
                "validation_quality_score": row.get("validation_quality_score"),
                "strong_neutral_mean_ic": state_lookup.get("strong_neutral"),
                "weak_neutral_mean_ic": state_lookup.get("weak_neutral"),
                "recovery_fragile_mean_ic": state_lookup.get("recovery_fragile"),
                "recovery_confirmed_mean_ic": state_lookup.get("recovery_confirmed"),
                "calm_trend_mean_ic": state_lookup.get("calm_trend"),
                **corr_context,
            }
        )
    candidate_df = pd.DataFrame(candidate_rows).sort_values("validation_quality_score", ascending=False)
    candidate_path = OUTPUT_DIR / "phase_a_signal_candidate_summary.csv"
    candidate_df.to_csv(candidate_path, index=False)

    return {
        "signal_summary": signal_summary,
        "phase_a_candidates": candidate_df,
        "phase_a_state_summary": phase_a_state_summary,
        "redundancy_matrix": redundancy_matrix,
        "output_paths": {
            "signal_ic_by_horizon": ic_summary_path,
            "signal_redundancy_matrix": redundancy_path,
            "signal_redundancy_pairs": redundancy_pairs_path,
            "signal_summary_table": summary_path,
            "signal_manifest": manifest_path,
            "signal_eligibility_matrix": eligibility_path,
            "phase_a_signal_state_summary": phase_a_state_path,
            "phase_a_signal_candidate_summary": candidate_path,
        },
    }


def main() -> None:
    namespace: dict = {"__name__": "__main__", "__file__": str(NOTEBOOK_PATH)}
    print(f"Loading notebook setup from {NOTEBOOK_PATH}...")
    load_notebook_cells(NOTEBOOK_PATH, SETUP_CELLS, namespace)
    print("Rebuilding existing Layer 1 signals for an integrated Phase A run...")
    load_notebook_cells(NOTEBOOK_PATH, BASE_SIGNAL_CELLS, namespace)
    print("Adding new Phase A opportunity-set signals...")
    new_signal_names = add_phase_a_signals(namespace)
    results = finalize_signal_outputs(namespace, new_signal_names)

    print("\nPhase A candidate summary")
    print(results["phase_a_candidates"].round(4).to_string(index=False))
    print("\nPhase A state summary")
    print(results["phase_a_state_summary"].round(4).to_string(index=False))
    print("\nSaved outputs:")
    for key, path in results["output_paths"].items():
        print(f" - {key}: {path}")


if __name__ == "__main__":
    main()
