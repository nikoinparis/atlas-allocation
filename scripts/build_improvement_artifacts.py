from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "02_layer1_signals"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"


def load_notebook_namespace(notebook_path: Path, code_cell_indices: list[int]) -> dict:
    notebook = json.loads(notebook_path.read_text())
    namespace: dict = {"__name__": "__main__"}
    for idx in code_cell_indices:
        cell = notebook["cells"][idx]
        if cell["cell_type"] != "code":
            continue
        exec(compile("".join(cell["source"]), f"{notebook_path.name}:cell_{idx}", "exec"), namespace)
    return namespace


def replace_or_append_row(df: pd.DataFrame, key_col: str, row: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame([row])
    out = df.copy()
    if key_col in out.columns:
        out = out[out[key_col] != row[key_col]]
    return pd.concat([out, pd.DataFrame([row])], ignore_index=True)


def safe_mean(series: pd.Series) -> float:
    series = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    return float(series.mean()) if not series.empty else np.nan


def cumulative_return(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return np.nan
    return float((1.0 + series).prod() - 1.0)


def window_drawdown(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return np.nan
    wealth = (1.0 + series).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def classify_allocations(weight_panel: pd.DataFrame, cash_proxy: str) -> tuple[list[str], list[str]]:
    defensive_assets = [ticker for ticker in ["IEF", "SHY", "TLT", "TIP", "GLD"] if ticker in weight_panel.columns and ticker != cash_proxy]
    offensive_assets = [ticker for ticker in weight_panel.columns if ticker not in set(defensive_assets + [cash_proxy])]
    return offensive_assets, defensive_assets


def version_state_label(current_offensive: float, current_defensive: float, current_cash: float) -> str:
    if current_cash + current_defensive >= 0.55:
        return "defensive"
    if current_offensive >= 0.60 and current_cash <= 0.20:
        return "risk_on"
    return "neutral"


def load_benchmark_returns(file_name: str) -> pd.Series:
    frame = pd.read_csv(LAYER2A_DIR / file_name, parse_dates=["Date"])
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    frame = frame.set_index("Date").sort_index()
    return pd.Series(frame["net_return"], name=file_name.replace("strategy_returns_", "").replace(".csv", ""))


ns3 = load_notebook_namespace(
    ROOT / "03_layer2a_strategy_logic.ipynb",
    [2, 3, 4, 5, 6, 8],
)
ns5 = load_notebook_namespace(
    ROOT / "05_layer3_portfolio_construction.ipynb",
    [2, 4, 5, 7, 9, 11],
)

SELF_GATED_SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "cta_trend_vol_managed",
    "taa_10m_sma",
]


def bounded_interp(series: pd.Series, *, xp: list[float], fp: list[float]) -> pd.Series:
    values = pd.Series(series, dtype=float)
    return pd.Series(
        np.interp(values.fillna(values.median(skipna=True) if values.notna().any() else 0.0), xp, fp),
        index=values.index,
        dtype=float,
    )


def evaluate_signal_combo(
    signal_names: list[str],
    *,
    top_n: int | None = None,
    min_signal: float = 0.0,
    weight_mode: str = "equal_top_n",
    strength_power: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    signal_panels = {name: ns3["baseline_signal_panels"][name] for name in signal_names if name in ns3["baseline_signal_panels"]}
    composite_signal = ns3["combine_signal_panels"](
        signal_panels,
        weight_history=None,
        smoothing_weeks=ns3["COMPOSITE_SMOOTHING_WEEKS"],
    )
    chosen_top_n = top_n if top_n is not None else min(5, max(3, len(ns3["broad_risk_assets"]) // 3)) if ns3["broad_risk_assets"] else 1
    signal_panel = composite_signal.reindex(columns=ns3["broad_risk_assets"])
    if weight_mode == "equal_top_n":
        weights = ns3["build_top_n_long_only_weights"](
            signal_panel,
            top_n=chosen_top_n,
            min_signal=min_signal,
            defensive_asset=ns3["defensive_asset"],
            fill_to_defensive=True,
        )
    elif weight_mode == "strength_weighted":
        weight_rows: list[pd.Series] = []
        for date, row in signal_panel.iterrows():
            score_row = pd.Series(row, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
            weights_row = pd.Series(0.0, index=signal_panel.columns, dtype=float)
            selected = score_row.loc[score_row >= min_signal].nlargest(chosen_top_n)
            if not selected.empty:
                strength = selected.sub(min_signal).clip(lower=0.0)
                if strength_power != 1.0:
                    strength = strength.pow(strength_power)
                if float(strength.sum()) > 1e-12:
                    weights_row.loc[strength.index] = strength / strength.sum()
                else:
                    weights_row.loc[selected.index] = 1.0 / len(selected)
            if ns3["defensive_asset"] in weights_row.index:
                remaining = max(0.0, 1.0 - float(weights_row.sum()))
                weights_row.loc[ns3["defensive_asset"]] = remaining
            weight_rows.append(weights_row.rename(date))
        weights = pd.DataFrame(weight_rows).reindex(columns=signal_panel.columns).fillna(0.0)
    else:
        raise ValueError(f"Unknown signal weight mode: {weight_mode}")
    weights, _ = ns3["apply_rebalance_schedule"](weights, "monthly")
    path = ns3["compute_strategy_path"](
        weights,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    metrics = ns5["summary_metrics"](
        path["net_return"],
        turnover_series=path["turnover"],
        weight_panel=weights,
        allocation_panel=weights,
        trials=max(len(signal_names), 2),
    )
    metrics["avg_bil_weight"] = weights.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weights.columns else np.nan
    metrics["avg_spy_weight"] = weights.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weights.columns else np.nan
    subperiod_df = ns5["subperiod_summary"]("combo", path["net_return"])
    metrics["subperiod_sharpe_range"] = (
        subperiod_df["sharpe"].max() - subperiod_df["sharpe"].min() if not subperiod_df.empty else np.nan
    )
    return weights, path, metrics


def register_strategy_output(
    strategy_name: str,
    weights: pd.DataFrame,
    path: pd.DataFrame,
    summary_row: dict,
    manifest_row: dict,
) -> None:
    (LAYER2A_DIR / f"strategy_positions_{strategy_name}.csv").write_text(weights.to_csv())
    (LAYER2A_DIR / f"strategy_returns_{strategy_name}.csv").write_text(path.to_csv())

    strategy_summary = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
    strategy_summary = replace_or_append_row(strategy_summary, "strategy_name", summary_row)
    strategy_summary = strategy_summary.sort_values(["benchmark_group", "validation_score"], ascending=[True, False]).reset_index(drop=True)
    strategy_summary.to_csv(LAYER2A_DIR / "strategy_summary_table.csv", index=False)

    layer2_manifest = json.loads((LAYER2A_DIR / "layer2_manifest.json").read_text())
    layer2_manifest = [row for row in layer2_manifest if row.get("strategy_name") != strategy_name]
    layer2_manifest.append(manifest_row)
    (LAYER2A_DIR / "layer2_manifest.json").write_text(json.dumps(layer2_manifest, indent=2))


def build_market_state_history() -> pd.DataFrame:
    regime_states = ns5["regime_states"].copy()
    regime_score = ns5["regime_score"].copy()
    weekly_prices = ns5["weekly_prices"].copy()
    proxy_mapping = ns5.get("proxy_mapping", {})
    market_ticker = proxy_mapping.get("market_proxy", {}).get("ticker", "SPY")
    cash_proxy = ns5["cash_proxy"]

    offensive_assets = list(ns3.get("broad_risk_assets", []))
    if not offensive_assets:
        offensive_assets = [ticker for ticker in weekly_prices.columns if ticker not in {cash_proxy, "IEF", "SHY", "TLT", "TIP", "GLD"}]
    offensive_assets = [ticker for ticker in offensive_assets if ticker in weekly_prices.columns]

    market_price = weekly_prices[market_ticker].copy() if market_ticker in weekly_prices.columns else pd.Series(dtype=float)
    market_sma_43 = market_price.rolling(43, min_periods=20).mean()
    market_trend_positive = market_price > market_sma_43
    market_drawdown = market_price.div(market_price.cummax()).sub(1.0)

    offensive_prices = weekly_prices.reindex(columns=offensive_assets)
    breadth_sma_43 = offensive_prices.gt(offensive_prices.rolling(43, min_periods=20).mean()).mean(axis=1)
    breadth_26w_mom = offensive_prices.pct_change(26).gt(0.0).mean(axis=1)
    breadth_13w_mom = offensive_prices.pct_change(13).gt(0.0).mean(axis=1)
    breadth_change_4w = breadth_sma_43.sub(breadth_sma_43.shift(4))

    # Separate canary diagnostics for the conditional research pass. The broader
    # set mirrors the existing notebook convention; the pair proxy is a smaller,
    # public-research-style implementation that approximates BND/VWO using the
    # available ETF universe.
    canary_assets_default = [ticker for ticker in ["VWO", "HYG", "VNQ", "EFA", "PDBC"] if ticker in weekly_prices.columns]
    canary_pair_assets = [ticker for ticker in ["VWO", "IEF"] if ticker in weekly_prices.columns]
    if len(canary_pair_assets) < 2:
        canary_pair_assets = [ticker for ticker in ["VWO", "LQD"] if ticker in weekly_prices.columns]

    def lagged_abs_momentum_breadth(tickers: list[str]) -> pd.Series:
        if not tickers:
            return pd.Series(np.nan, index=weekly_prices.index, dtype=float)
        trailing_52_4w = weekly_prices[tickers].shift(4).div(weekly_prices[tickers].shift(52)).sub(1.0)
        return trailing_52_4w.gt(0.0).mean(axis=1)

    canary_breadth_default = lagged_abs_momentum_breadth(canary_assets_default)
    canary_breadth_pair = lagged_abs_momentum_breadth(canary_pair_assets)

    recent_stress = regime_states["risk_state"].eq("stressed").rolling(26, min_periods=1).max().fillna(0.0).astype(bool)
    avg_corr_risk_off_z = regime_score.get("avg_corr_risk_off_z", pd.Series(np.nan, index=regime_states.index))
    google_fear = regime_score.get("google_fear_z_tradable", pd.Series(np.nan, index=regime_states.index))
    risk_score = regime_score.get("risk_regime_score", pd.Series(np.nan, index=regime_states.index))

    state = pd.Series("neutral_mixed", index=regime_states.index, dtype=object)
    stressed_mask = regime_states["risk_state"].eq("stressed") | ((market_drawdown <= -0.18) & (breadth_sma_43 < 0.35))
    # Recovery universe: any rebound off stress with trend and breadth improving.
    recovery_universe = (
        ~stressed_mask
        & recent_stress
        & market_trend_positive.fillna(False)
        & (breadth_sma_43 >= 0.45)
        & (breadth_26w_mom >= 0.45)
        & (breadth_change_4w >= 0.05)
    )
    # Confirmed recovery: stricter breadth / momentum / trend / risk score confirmation.
    confirm_breadth = breadth_sma_43 >= 0.58
    confirm_breadth_mom_26 = breadth_26w_mom >= 0.55
    confirm_breadth_mom_13 = breadth_13w_mom >= 0.55
    confirm_trend = market_trend_positive.fillna(False)
    confirm_drawdown = market_drawdown >= -0.06
    confirm_risk = risk_score.reindex(regime_states.index).fillna(0.0) <= 0.35
    recovery_confirmed_mask = (
        recovery_universe
        & confirm_breadth
        & confirm_breadth_mom_26
        & confirm_breadth_mom_13
        & confirm_trend
        & confirm_drawdown
        & confirm_risk
    )
    recovery_fragile_mask = recovery_universe & ~recovery_confirmed_mask
    calm_mask = (
        ~stressed_mask
        & regime_states["risk_state"].eq("calm")
        & market_trend_positive.fillna(False)
        & (breadth_sma_43 >= 0.60)
        & (breadth_26w_mom >= 0.55)
    )
    state.loc[stressed_mask] = "stressed_panic"
    state.loc[recovery_fragile_mask] = "recovery_fragile"
    state.loc[recovery_confirmed_mask] = "recovery_confirmed"
    state.loc[calm_mask] = "calm_trend"

    state_reason = pd.Series("mixed inputs", index=state.index, dtype=object)
    state_reason.loc[stressed_mask] = "stress state, weak breadth, or deep drawdown"
    state_reason.loc[recovery_fragile_mask] = "recent stress with improving breadth but confirmation still partial"
    state_reason.loc[recovery_confirmed_mask] = "recent stress plus confirmed breadth, 13w and 26w momentum, trend, low drawdown, and low risk score"
    state_reason.loc[calm_mask] = "calm regime with strong trend breadth"

    # --- Causal transition-probability features ----------------------------------
    # For each week t (in state S), compute trailing-window estimates of
    #   P(next state == S | current state == S)            -> transition_persistence_prob
    #   P(next state in good regimes | current state == S) -> transition_good_state_prob
    # using only transitions that completed strictly before t (shift(1) after rolling).
    state_series = pd.Series(state.values, index=regime_states.index, dtype=object)
    state_next = state_series.shift(-1)
    pair_df = pd.DataFrame({"curr": state_series, "next": state_next}).dropna(subset=["next"])
    good_states_set = {"calm_trend", "recovery_fragile", "recovery_confirmed"}
    pair_df["stays"] = (pair_df["curr"] == pair_df["next"]).astype(float)
    pair_df["good_next"] = pair_df["next"].isin(good_states_set).astype(float)
    pair_df["non_stress_next"] = (~pair_df["next"].eq("stressed_panic")).astype(float)

    TRANSITION_WINDOW_WEEKS = 156  # ~3 years
    MIN_TRANSITION_PAIRS = 10

    persistence_prob = pd.Series(np.nan, index=regime_states.index, dtype=float)
    good_state_prob = pd.Series(np.nan, index=regime_states.index, dtype=float)
    non_stress_prob = pd.Series(np.nan, index=regime_states.index, dtype=float)
    for state_name in pair_df["curr"].dropna().unique():
        subset_mask = pair_df["curr"] == state_name
        if not subset_mask.any():
            continue
        subset = pair_df.loc[subset_mask]
        rolling_stays = (
            subset["stays"].rolling(TRANSITION_WINDOW_WEEKS, min_periods=MIN_TRANSITION_PAIRS).mean().shift(1)
        )
        rolling_good = (
            subset["good_next"].rolling(TRANSITION_WINDOW_WEEKS, min_periods=MIN_TRANSITION_PAIRS).mean().shift(1)
        )
        rolling_non_stress = (
            subset["non_stress_next"].rolling(TRANSITION_WINDOW_WEEKS, min_periods=MIN_TRANSITION_PAIRS).mean().shift(1)
        )
        mask_full = state_series == state_name
        if not mask_full.any():
            continue
        stays_ff = rolling_stays.reindex(state_series.index, method="ffill")
        good_ff = rolling_good.reindex(state_series.index, method="ffill")
        non_stress_ff = rolling_non_stress.reindex(state_series.index, method="ffill")
        persistence_prob.loc[mask_full] = stays_ff.loc[mask_full]
        good_state_prob.loc[mask_full] = good_ff.loc[mask_full]
        non_stress_prob.loc[mask_full] = non_stress_ff.loc[mask_full]

    # --- Stabilized state (one-sided hysteresis on entry into stressed_panic) -----
    # Delay the first week of stressed_panic entry by one week unless the drawdown is
    # already severe (<= -10%) or the risk_regime_score is very high (> 0.85). Exits
    # are NOT delayed; this only dampens one-week false entries into stress.
    risk_score_full = risk_score.reindex(regime_states.index).fillna(0.0)
    dd_full = market_drawdown.reindex(regime_states.index).fillna(0.0)
    severe_mask = (dd_full <= -0.10) | (risk_score_full > 0.85)
    state_shift_prev = state_series.shift(1)
    just_entered_stress = (
        state_series.eq("stressed_panic")
        & state_shift_prev.ne("stressed_panic")
        & ~severe_mask.reindex(state_series.index).fillna(False)
    )
    market_state_stable = state_series.copy()
    market_state_stable.loc[just_entered_stress] = state_shift_prev.loc[just_entered_stress]
    market_state_stable = market_state_stable.fillna(state_series)

    out = pd.DataFrame(
        {
            "Date": regime_states.index,
            "market_state": state.values,
            "market_state_stable": market_state_stable.reindex(regime_states.index).values,
            "market_state_reason": state_reason.values,
            "risk_state": regime_states["risk_state"].values,
            "signal_environment": regime_states.get("signal_environment", pd.Series(index=regime_states.index, dtype=object)).values,
            "risk_regime_score": risk_score.reindex(regime_states.index).values,
            "market_drawdown": market_drawdown.reindex(regime_states.index).values,
            "market_trend_positive": market_trend_positive.reindex(regime_states.index).astype(float).values,
            "breadth_sma_43": breadth_sma_43.reindex(regime_states.index).values,
            "breadth_26w_mom": breadth_26w_mom.reindex(regime_states.index).values,
            "breadth_13w_mom": breadth_13w_mom.reindex(regime_states.index).values,
            "breadth_change_4w": breadth_change_4w.reindex(regime_states.index).values,
            "canary_breadth_default": canary_breadth_default.reindex(regime_states.index).values,
            "canary_breadth_pair": canary_breadth_pair.reindex(regime_states.index).values,
            "recent_stress_26w": recent_stress.reindex(regime_states.index).astype(float).values,
            "avg_corr_risk_off_z": avg_corr_risk_off_z.reindex(regime_states.index).values,
            "google_fear_z_tradable": google_fear.reindex(regime_states.index).values,
            "transition_persistence_prob": persistence_prob.reindex(regime_states.index).values,
            "transition_good_state_prob": good_state_prob.reindex(regime_states.index).values,
            "transition_non_stress_prob": non_stress_prob.reindex(regime_states.index).values,
        }
    ).set_index("Date")
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.to_csv(LAYER2B_DIR / "market_state_history.csv")
    return out


def build_variant_regime_states(
    base_regime_states: pd.DataFrame,
    market_state_history: pd.DataFrame,
    overlay_variant: str,
) -> pd.DataFrame:
    adjusted = base_regime_states.copy()
    extra_columns = [
        "market_state",
        "market_state_reason",
        "breadth_sma_43",
        "breadth_26w_mom",
        "market_trend_positive",
        "canary_breadth_default",
        "canary_breadth_pair",
    ]
    for optional_column in (
        "transition_persistence_prob",
        "transition_good_state_prob",
        "transition_non_stress_prob",
        "market_state_stable",
    ):
        if market_state_history is not None and optional_column in market_state_history.columns:
            extra_columns.append(optional_column)
    adjusted = adjusted.join(market_state_history[extra_columns], how="left")
    if adjusted.empty or "overlay_multiplier" not in adjusted.columns:
        return adjusted
    if overlay_variant == "baseline":
        return adjusted

    # Variants with a raised neutral base (they lift the overall neutral floor modestly).
    neutral_floor_overrides = {
        "good_state_strong_offense": 0.83,
        "good_state_combo_plus": 0.83,
    }
    neutral_floor = neutral_floor_overrides.get(overlay_variant, 0.80)

    neutral_mask = adjusted["risk_state"].eq("neutral")
    stressed_mask = adjusted["risk_state"].eq("stressed")
    adjusted.loc[neutral_mask, "overlay_multiplier"] = adjusted.loc[neutral_mask, "overlay_multiplier"].clip(lower=neutral_floor)
    adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(lower=0.40)

    if overlay_variant == "looser_neutral_stress":
        return adjusted

    # Legacy aggregated-recovery flag (either sub-state counts as recovery for backward compat)
    recovery_any_mask = adjusted["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"])
    recovery_confirmed_mask = adjusted["market_state"].eq("recovery_confirmed")
    recovery_fragile_mask = adjusted["market_state"].eq("recovery_fragile")
    calm_mask = adjusted["market_state"].eq("calm_trend")
    strong_neutral_mask = (
        adjusted["market_state"].eq("neutral_mixed")
        & adjusted["market_trend_positive"].fillna(0.0).gt(0.0)
        & adjusted["breadth_sma_43"].fillna(0.0).ge(0.55)
        & adjusted["breadth_26w_mom"].fillna(0.0).ge(0.50)
    )
    recentered_strong_neutral_mask = (
        adjusted["market_state"].eq("neutral_mixed")
        & adjusted["market_trend_positive"].fillna(0.0).gt(0.0)
        & adjusted["breadth_sma_43"].fillna(0.0).ge(0.52)
        & adjusted["breadth_26w_mom"].fillna(0.0).ge(0.48)
    )

    if overlay_variant == "recovery_breadth_rerisk":
        # Original aggregated-recovery overlay: single 0.92 floor.
        adjusted.loc[recovery_any_mask, "overlay_multiplier"] = adjusted.loc[recovery_any_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "neutral_positive_ease":
        # Keep the incumbent recovery logic, but make positive-trend neutral weeks slightly less
        # punitive so we can test whether long-run underdeployment is mostly a neutral-state issue.
        adjusted.loc[recovery_any_mask, "overlay_multiplier"] = adjusted.loc[recovery_any_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    if overlay_variant == "good_state_participation":
        # Control already fixed part of the neutral-state bottleneck. This variant tests whether the
        # remaining weakness is still too much overlay cash in clearly good states.
        adjusted.loc[recovery_any_mask, "overlay_multiplier"] = adjusted.loc[recovery_any_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "recovery_fragile_participation":
        # Early recovery gets a slightly higher floor than confirmed recovery so we can test whether
        # the main missed-upside problem is hesitation during the fragile handoff out of stress.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.95)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "neutral_positive_ease_fragile_participation":
        # Combination test: keep the benign neutral easing from Variant A while also letting fragile
        # recovery rerisk slightly faster than confirmed recovery.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.95)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    if overlay_variant == "fragile_expression_only":
        # Distinct from the already-refuted confirmed-offense ladder: keep the current neutral easing,
        # leave confirmed recovery on the control floor, and only let fragile recovery rerisk a touch
        # faster if the lag is really in the handoff out of stress.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    if overlay_variant == "good_state_fragile_expression":
        # Best justified combination after the standalone pass: keep the stronger calm / strong-neutral
        # floors from the good-state offense variant, and add only the modest fragile-recovery lift.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "continuous_neutral_mapping":
        # Map the continuous risk_regime_score directly into the neutral-state deployment
        # multiplier so moderately good / moderately bad neutral weeks are not forced
        # through the same blunt neutral response. Recovery / calm / stress keep the
        # current control floors.
        mapped = bounded_interp(
            adjusted.get("risk_regime_score", pd.Series(np.nan, index=adjusted.index)),
            xp=[-1.25, -0.60, -0.10, 0.25, 0.75, 1.50, 3.00],
            fp=[1.00, 0.99, 0.95, 0.90, 0.76, 0.48, 0.28],
        )
        neutral_state_mask = adjusted["market_state"].eq("neutral_mixed")
        adjusted.loc[neutral_state_mask, "overlay_multiplier"] = mapped.loc[neutral_state_mask]
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(upper=0.40)
        return adjusted

    if overlay_variant == "continuous_neutral_mapping_careful":
        # Conservative continuous map: weak-neutral stays near the control path,
        # while clearly benign strong-neutral weeks get a smoother release valve.
        risk_values = adjusted.get("risk_regime_score", pd.Series(np.nan, index=adjusted.index))
        neutral_base_map = bounded_interp(
            risk_values,
            xp=[-1.25, -0.60, -0.10, 0.25, 0.75, 1.50, 3.00],
            fp=[0.91, 0.90, 0.88, 0.85, 0.73, 0.46, 0.28],
        )
        strong_neutral_map = bounded_interp(
            risk_values,
            xp=[-1.25, -0.60, -0.10, 0.25, 0.75, 1.50, 3.00],
            fp=[0.97, 0.96, 0.95, 0.92, 0.82, 0.48, 0.28],
        )
        neutral_state_mask = adjusted["market_state"].eq("neutral_mixed")
        adjusted.loc[neutral_state_mask, "overlay_multiplier"] = neutral_base_map.loc[neutral_state_mask]
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = strong_neutral_map.loc[strong_neutral_mask]
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(upper=0.40)
        return adjusted

    if overlay_variant == "separate_canary_proxy":
        # Minimal separate-canary test. If the canary pair is fully healthy, lift
        # only the clearly benign states slightly; otherwise stay on the control path.
        canary_pair_breadth = adjusted.get("canary_breadth_pair", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)
        canary_all_clear_mask = canary_pair_breadth >= 0.999
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        adjusted.loc[strong_neutral_mask & canary_all_clear_mask, "overlay_multiplier"] = adjusted.loc[
            strong_neutral_mask & canary_all_clear_mask, "overlay_multiplier"
        ].clip(lower=0.96)
        adjusted.loc[recovery_fragile_mask & canary_all_clear_mask, "overlay_multiplier"] = adjusted.loc[
            recovery_fragile_mask & canary_all_clear_mask, "overlay_multiplier"
        ].clip(lower=0.97)
        adjusted.loc[recovery_confirmed_mask & canary_all_clear_mask, "overlay_multiplier"] = adjusted.loc[
            recovery_confirmed_mask & canary_all_clear_mask, "overlay_multiplier"
        ].clip(lower=0.93)
        return adjusted

    if overlay_variant == "threshold_recentering":
        # Minimal threshold recentering only.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[recentered_strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[
            recentered_strong_neutral_mask, "overlay_multiplier"
        ].clip(lower=0.94)
        return adjusted

    if overlay_variant == "recovery_split_baseline":
        # Variant A: split recovery into two buckets but keep offense intensity roughly symmetric
        # with the aggregated recovery overlay. Confirmed gets a slightly stronger floor than fragile.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.90)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.94)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "recovery_split_confirmed_offense":
        # Variant B: split recovery + meaningfully stronger re-risking in confirmed recovery.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.88)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "recovery_split_confirmed_offense_neutral_ease":
        # Variant C: same as B + slightly less punitive neutral-state cash behavior when
        # neutral still has a positive trend (not a global relaxation of neutral stance).
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.88)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        # Raise the strong-neutral floor modestly (0.85 -> 0.90) so "quiet but trending up" weeks
        # carry a bit less sleeve-level cash.
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    # ------------------------------------------------------------------
    # Good-state transition-aware / stabilizer / mix-rotation family
    # (current research task, control = improved_hrp_good_state_fragile_combo)
    # ------------------------------------------------------------------
    transition_good_prob = adjusted.get("transition_good_state_prob", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)
    transition_persistence = adjusted.get("transition_persistence_prob", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)
    transition_non_stress = adjusted.get("transition_non_stress_prob", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)

    if overlay_variant == "good_state_fragile_transition_aware":
        # Variant A. Keep the control's floors but, when the trailing-window transition
        # matrix says the current regime is both persistent (>= 0.70) AND rarely
        # transitions to stressed_panic (>= 0.92 P(non-stress next)), lift the
        # strong-neutral floor from 0.94 -> 0.97. This targets observed cash drag
        # in strong-neutral weeks where the regime engine itself predicts benign
        # continuation. Using P(non-stress next) rather than P(next in good states)
        # is the decision-useful framing: persistence itself is a benign outcome
        # from neutral_mixed, since neutral_mixed rarely steps directly to stress.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        transition_boost_mask = (
            strong_neutral_mask
            & (transition_non_stress >= 0.92)
            & (transition_persistence >= 0.70)
        )
        adjusted.loc[transition_boost_mask, "overlay_multiplier"] = adjusted.loc[transition_boost_mask, "overlay_multiplier"].clip(lower=0.97)
        return adjusted

    if overlay_variant == "good_state_fragile_stabilizer":
        # Variant B. Identical floors to control, but run with market_state_stable
        # (one-sided hysteresis on entry into stressed_panic). The caller substitutes
        # market_state_stable into market_state upstream, so the masks here already
        # reflect the stabilized state; no extra overlay work needed.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "good_state_strong_offense":
        # Variant C. Raise the strong-neutral floor 0.94 -> 0.98 and the neutral base
        # 0.80 -> 0.83 (applied earlier) so clearly-benign states carry even less
        # residual overlay cash. Keeps fragile at 0.96 and confirmed at 0.92.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.98)
        return adjusted

    if overlay_variant == "good_state_mix_rotation":
        # Variant D. Same overlay floors as control; the change is entirely in the
        # state-conditioned sleeve tilt (fragile_plus_mix_rotation), which rotates
        # weight away from composite_regime_conditioned in calm_trend and toward the
        # trend-following trio (dual_momentum / cta_trend / composite_selective) in
        # calm + fragile.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "good_state_combo_plus":
        # Variant E. Best justified combination after standalone pass: keeps the
        # control fragile/confirmed/calm floors, layers in the transition-aware
        # strong-neutral boost (A) and the stronger strong-neutral floor (C), and
        # pairs with the mix-rotation tilt (D) at the tilt layer. Also uses the
        # stabilizer (B) via market_state_stable at the caller.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.97)
        transition_boost_mask = (
            strong_neutral_mask
            & (transition_non_stress >= 0.92)
            & (transition_persistence >= 0.70)
        )
        adjusted.loc[transition_boost_mask, "overlay_multiplier"] = adjusted.loc[transition_boost_mask, "overlay_multiplier"].clip(lower=0.98)
        return adjusted

    # Fallback: behave like looser_neutral_stress if an unknown variant string is passed.
    return adjusted


def compute_causal_confidence(market_state_row: pd.Series | None) -> float:
    """Bounded Layer 2B causal-confidence score in [0, 1].

    Composite of:
      - transition_non_stress_prob (regime engine stay-out-of-stress), normalized 0.85 -> 0, 1.00 -> 1
      - breadth_sma_43,                                                  normalized 0.50 -> 0, 0.80 -> 1
      - market_trend_positive > 0                                        (binary)
      - market_drawdown > -0.08                                          (binary: drawdown shallower than -8%)
    Weights: 0.40 / 0.25 / 0.20 / 0.15. Fully deterministic, no hindsight.
    """
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return 0.0

    def _safe_float(key: str, default: float = 0.0) -> float:
        value = market_state_row.get(key, default)
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    persistence = _safe_float("transition_non_stress_prob", 0.0)
    persistence_norm = float(np.clip((persistence - 0.85) / 0.15, 0.0, 1.0))
    breadth = _safe_float("breadth_sma_43", 0.0)
    breadth_norm = float(np.clip((breadth - 0.50) / 0.30, 0.0, 1.0))
    trend_positive = 1.0 if _safe_float("market_trend_positive", 0.0) > 0.0 else 0.0
    drawdown_shallow = 1.0 if _safe_float("market_drawdown", 0.0) > -0.08 else 0.0
    score = 0.40 * persistence_norm + 0.25 * breadth_norm + 0.20 * trend_positive + 0.15 * drawdown_shallow
    return float(np.clip(score, 0.0, 1.0))


def compute_rolling_sleeve_conviction(
    sleeve_return_panel: pd.DataFrame,
    as_of_date: pd.Timestamp,
    sleeves: list[str],
    *,
    lookback_weeks: int = 26,
) -> pd.Series:
    """Rank-based rolling Sharpe conviction in [-1, +1] for each sleeve.

    Uses only returns strictly up to and including `as_of_date` (no hindsight).
    Rank 1.0 (best in subset) -> +1; rank 0.0 (worst) -> -1. Returns 0 when
    there isn't enough history.
    """
    if not sleeves:
        return pd.Series(dtype=float)
    window = sleeve_return_panel.loc[:as_of_date, [s for s in sleeves if s in sleeve_return_panel.columns]].tail(lookback_weeks)
    if window.empty or len(window) < max(8, lookback_weeks // 4):
        return pd.Series(0.0, index=sleeves, dtype=float)
    mean = window.mean(axis=0)
    std = window.std(axis=0, ddof=0)
    sharpe = mean.div(std.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    if sharpe.dropna().empty:
        return pd.Series(0.0, index=sleeves, dtype=float)
    ranks = sharpe.rank(pct=True, method="average")
    conviction = (ranks - 0.5) * 2.0
    return conviction.reindex(sleeves).fillna(0.0)


def apply_state_conditioned_tilt(
    raw_weights: pd.Series,
    market_state: str | None,
    tilt_mode: str = "none",
    *,
    conviction: pd.Series | None = None,
    market_state_row: pd.Series | None = None,
) -> pd.Series:
    if tilt_mode == "none":
        return ns5["normalize_long_only"](raw_weights, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    tilted = pd.Series(raw_weights, dtype=float).copy()
    offensive_sleeves = [
        name
        for name in [
            "dual_momentum_topn",
            "cta_trend_long_only",
            "cta_trend_vol_managed",
            "composite_selective_signals",
            "composite_selective_trend_ensemble",
            "composite_selective_concentrated",
            "composite_equal_weight",
        ]
        if name in tilted.index
    ]
    defensive_sleeves = [name for name in ["composite_regime_conditioned", "taa_10m_sma"] if name in tilted.index]

    strong_neutral_flag = False
    if market_state_row is not None and isinstance(market_state_row, pd.Series) and not market_state_row.empty:
        strong_neutral_flag = is_strong_neutral_state_row(market_state_row)

    # Phase 1 Variant A: dynamic risk budgeting.
    # Apply a bounded rank-based conviction tilt on favorable states only.
    # Stressed_panic keeps the existing defensive shift; unknown / neutral
    # states pass through unchanged.
    if tilt_mode == "dynamic_risk_budget":
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            # Mild re-risk on top of the conviction tilt so the handoff
            # doesn't stall in fragile weeks.
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 1 Combo F: dynamic risk budget combined with good-state leadership
    # rotation. Applies the leadership rotation first (sleeve-mix level) and
    # then layers the conviction tilt on top, still bounded per-sleeve. Shared
    # stressed-panic protection.
    if tilt_mode == "dynamic_risk_budget_and_leadership":
        # --- Leadership stage (Variant E, bounded ±15%) ---
        if market_state == "calm_trend":
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.12
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.10
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.08
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.02
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.02
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.85
        elif market_state == "recovery_confirmed":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.15
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.15
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 0.95
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.88
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 0.88
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        elif market_state == "recovery_fragile":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.12
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.12
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.10
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.96
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.90
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        elif strong_neutral_flag:
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.10
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.08
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.04
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        # --- Conviction stage (Variant A, bounded ±10% inside combo) ---
        # Dampen the conviction modifier to ±10% since leadership is already
        # rotating the mix; avoid compounding into ±30% per sleeve.
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.10 * c, 0.90, 1.10))
                tilted.loc[name] *= multiplier
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 1 Variant E: good-state sleeve leadership (bounded ±15%).
    # Lean toward sleeves that lead in each favorable state and lighten the
    # chronic laggards, leaving gross-risk alone.
    if tilt_mode == "phase1_leadership":
        if market_state == "calm_trend":
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.12
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.10
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.08
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.02
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.02
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.85
        elif market_state == "recovery_confirmed":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.15
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.15
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 0.95
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.88
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 0.88
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        elif market_state == "recovery_fragile":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.12
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.12
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.10
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.96
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.90
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        elif strong_neutral_flag:
            # Strong-neutral: boost the trend trio moderately, soft fade
            # composite_regime_conditioned.
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.10
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.08
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.04
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        else:
            # Plain neutral_mixed, no signal: pass through unchanged.
            pass
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Backward compatibility: legacy "modest" tilt on the aggregated recovery state.
    if market_state == "recovery_rebound":
        for name in offensive_sleeves:
            tilted.loc[name] *= 1.12
        for name in defensive_sleeves:
            tilted.loc[name] *= 0.90
    elif market_state == "recovery_fragile":
        if tilt_mode == "fragile_first":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.12
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.92
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode == "fragile_plus":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.10
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.94
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode == "fragile_plus_mix_rotation":
            # Variant D (fragile leg). Like fragile_plus but leans harder toward the
            # trend-following trio observed to score best in recovery_fragile weeks
            # (cta_trend and dual_momentum by sleeve-by-state Sharpe).
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.15
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.15
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.12
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.06
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.06
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.94
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        # Fragile: modest re-risk only. Never lean hard into an unconfirmed bounce.
        if tilt_mode in {"modest", "split_modest", "split_aggressive"}:
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.06
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
    elif market_state == "recovery_confirmed":
        if tilt_mode == "fragile_first":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.08
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.94
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode in {"confirmed_leadership", "calm_confirmed_leadership", "calm_confirmed_fragile_leadership"}:
            # Recovery-confirmed is not an argument for "more offense everywhere";
            # it is an argument for better sleeve leadership. The sleeve-by-state
            # table shows CTA trend and TAA leading here, while selective and the
            # regime sleeve lag materially, so rotate the mix instead of loosening
            # the gross risk budget.
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.20
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.20
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 0.94
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.82
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 0.82
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.86
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode in {"modest", "split_modest", "fragile_plus", "fragile_plus_mix_rotation"}:
            # Treat confirmed like the legacy "modest" tilt. Do not revive a stronger
            # confirmed-offense ladder in the mix-rotation variant; the rotation is
            # concentrated in fragile + calm only.
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.12
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.90
        elif tilt_mode == "split_aggressive":
            # Aggressive offense only when breadth/trend/momentum/drawdown all confirm.
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.22
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.82
    elif market_state == "calm_trend":
        if tilt_mode in {"calm_confirmed_leadership", "calm_confirmed_fragile_leadership"}:
            # Calm-trend still undercaptures badly despite very little overlay cash.
            # That points to sleeve mix quality, not gross deployment. Favor the
            # sleeves that hold up best in calm conditions (TAA and selective),
            # keep dual roughly neutral, and reduce the regime-conditioned sleeve.
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.14
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.10
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.02
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 0.98
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 0.98
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.84
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode == "fragile_plus_mix_rotation":
            # Variant D (calm leg). Rotate away from composite_regime_conditioned
            # (lowest sleeve Sharpe in calm weeks) and toward the trend-following
            # trio. Keep taa_10m_sma roughly neutral so the rotation is about mix
            # quality, not simply adding more defense.
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.14
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.14
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.14
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.12
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.12
            if "composite_selective_concentrated" in tilted.index:
                tilted.loc["composite_selective_concentrated"] *= 1.10
            if "composite_equal_weight" in tilted.index:
                tilted.loc["composite_equal_weight"] *= 1.05
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.80
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.98
        else:
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.08
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.94
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.96
    elif market_state == "stressed_panic":
        for name in offensive_sleeves:
            tilted.loc[name] *= 0.92
        if "composite_regime_conditioned" in tilted.index:
            tilted.loc["composite_regime_conditioned"] *= 1.08
        if "taa_10m_sma" in tilted.index:
            tilted.loc["taa_10m_sma"] *= 1.05
    if market_state == "recovery_fragile" and tilt_mode == "calm_confirmed_fragile_leadership":
        # Recovery-fragile is still a rerisk handoff, but CTA and dual momentum
        # are the leaders here. Make the existing fragile tilt more selective by
        # pulling weight away from the weaker regime/selection sleeves.
        if "cta_trend_long_only" in tilted.index:
            tilted.loc["cta_trend_long_only"] *= 1.16
        if "cta_trend_vol_managed" in tilted.index:
            tilted.loc["cta_trend_vol_managed"] *= 1.16
        if "dual_momentum_topn" in tilted.index:
            tilted.loc["dual_momentum_topn"] *= 1.10
        if "composite_selective_signals" in tilted.index:
            tilted.loc["composite_selective_signals"] *= 0.94
        if "composite_selective_trend_ensemble" in tilted.index:
            tilted.loc["composite_selective_trend_ensemble"] *= 0.94
        if "composite_regime_conditioned" in tilted.index:
            tilted.loc["composite_regime_conditioned"] *= 0.88
        if "taa_10m_sma" in tilted.index:
            tilted.loc["taa_10m_sma"] *= 0.98
    return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])


def is_strong_neutral_state_row(market_state_row: pd.Series | None) -> bool:
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return False
    market_state = str(market_state_row.get("market_state") or "")
    market_trend_positive = float(market_state_row.get("market_trend_positive") or 0.0)
    breadth_sma_43 = float(market_state_row.get("breadth_sma_43") or 0.0)
    breadth_26w_mom = float(market_state_row.get("breadth_26w_mom") or 0.0)
    return (
        market_state == "neutral_mixed"
        and market_trend_positive > 0.0
        and breadth_sma_43 >= 0.55
        and breadth_26w_mom >= 0.50
    )


def apply_layer3_expression(
    raw_weights: pd.Series,
    market_state_row: pd.Series | None,
    conviction_row: pd.Series | None,
    *,
    expression_mode: str = "none",
) -> tuple[pd.Series, dict]:
    normalized = ns5["normalize_long_only"](pd.Series(raw_weights, dtype=float), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    diagnostics = {
        "layer3_expression_shift": 0.0,
        "layer3_expression_triggered": 0.0,
        "layer3_expression_mode": expression_mode,
    }
    if expression_mode == "none" or market_state_row is None or market_state_row.empty:
        return normalized, diagnostics

    market_state = str(market_state_row.get("market_state") or "")
    strong_neutral = is_strong_neutral_state_row(market_state_row)
    shift_budget = 0.0
    if expression_mode == "good_state_conviction_relax":
        if market_state == "calm_trend":
            shift_budget = 0.06
        elif strong_neutral:
            shift_budget = 0.05
        elif market_state == "recovery_fragile":
            shift_budget = 0.04
    if shift_budget <= 0.0:
        return normalized, diagnostics

    offensive_sleeves = [
        name
        for name in [
            "dual_momentum_topn",
            "cta_trend_long_only",
            "cta_trend_vol_managed",
            "composite_selective_signals",
            "composite_selective_trend_ensemble",
            "composite_selective_strength_weighted",
            "composite_selective_concentrated",
            "composite_equal_weight",
        ]
        if name in normalized.index
    ]
    defensive_sleeves = [name for name in ["composite_regime_conditioned", "taa_10m_sma"] if name in normalized.index]
    if not offensive_sleeves or not defensive_sleeves:
        return normalized, diagnostics

    defensive_budget = float(normalized.reindex(defensive_sleeves).sum())
    shift = min(shift_budget, defensive_budget * 0.35)
    if shift <= 1e-12:
        return normalized, diagnostics

    conviction = pd.Series(dtype=float) if conviction_row is None else pd.Series(conviction_row, dtype=float)
    conviction = conviction.reindex(offensive_sleeves).replace([np.inf, -np.inf], np.nan)
    if conviction.notna().any():
        conviction = conviction.fillna(float(conviction.median()))
    else:
        conviction = pd.Series(0.0, index=offensive_sleeves, dtype=float)
    strength = conviction.sub(float(conviction.min())).clip(lower=0.0)
    if float(strength.sum()) <= 1e-12:
        current_offense = normalized.reindex(offensive_sleeves).clip(lower=0.0)
        strength = current_offense if float(current_offense.sum()) > 1e-12 else pd.Series(1.0, index=offensive_sleeves, dtype=float)
    strength = strength / strength.sum()

    adjusted = normalized.copy()
    defensive_weights = adjusted.reindex(defensive_sleeves).fillna(0.0)
    adjusted.loc[defensive_sleeves] = (defensive_weights - shift * defensive_weights / defensive_weights.sum()).clip(lower=0.0)
    adjusted.loc[offensive_sleeves] = adjusted.reindex(offensive_sleeves).fillna(0.0) + shift * strength
    adjusted = ns5["normalize_long_only"](adjusted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    diagnostics["layer3_expression_shift"] = shift
    diagnostics["layer3_expression_triggered"] = 1.0
    return adjusted, diagnostics


def apply_beta_participation_overlay(
    etf_weights: pd.Series,
    market_state_row: pd.Series | None,
    *,
    beta_overlay_mode: str = "none",
) -> tuple[pd.Series, dict]:
    adjusted = pd.Series(etf_weights, dtype=float).copy()
    overlay_contribution = {"SPY": 0.0, ns5["cash_proxy"]: 0.0}
    if beta_overlay_mode == "none" or market_state_row is None or market_state_row.empty:
        return adjusted, overlay_contribution

    market_state = str(market_state_row.get("market_state") or "")
    strong_neutral = is_strong_neutral_state_row(market_state_row)

    desired_shift = 0.0
    if beta_overlay_mode == "good_state_spy":
        if market_state == "calm_trend":
            desired_shift = 0.06
        elif market_state == "recovery_fragile":
            desired_shift = 0.05
        elif strong_neutral:
            desired_shift = 0.04
    elif beta_overlay_mode == "good_state_spy_light":
        if market_state == "calm_trend":
            desired_shift = 0.04
        elif market_state == "recovery_fragile":
            desired_shift = 0.03
        elif strong_neutral:
            desired_shift = 0.025

    if desired_shift <= 0.0:
        return adjusted, overlay_contribution

    bil_ticker = ns5["cash_proxy"]
    current_bil = float(adjusted.get(bil_ticker, 0.0) or 0.0)
    current_spy = float(adjusted.get("SPY", 0.0) or 0.0)
    shift = min(current_bil, desired_shift, max(0.0, 0.18 - current_spy))
    if shift <= 0.0:
        return adjusted, overlay_contribution

    adjusted.loc[bil_ticker] = current_bil - shift
    adjusted.loc["SPY"] = current_spy + shift
    overlay_contribution[bil_ticker] = -shift
    overlay_contribution["SPY"] = shift
    return adjusted, overlay_contribution


def apply_overlays_custom(
    raw_weights: pd.Series,
    cov: pd.DataFrame,
    regime_row: pd.Series,
    *,
    prev_weights: pd.Series | None = None,
    target_vol_ceil: float = ns5["TARGET_VOL_CEIL"],
    sleeve_reallocation_speed: float = ns5["SLEEVE_REALLOCATION_SPEED"],
    rerisk_speed: float | None = None,
    market_state: str | None = None,
    market_state_row: pd.Series | None = None,
    prev_regime_multiplier: float | None = None,
    overlay_penalty_mode: str = "none",
    speed_mode: str = "default",
    improving_speed: float | None = None,
    deteriorating_speed: float | None = None,
) -> tuple[pd.Series, float, dict]:
    raw_weights = ns5["normalize_long_only"](raw_weights, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    regime_multiplier = float(regime_row.get("overlay_multiplier", 1.0)) if isinstance(regime_row, pd.Series) else 1.0
    strong_neutral = is_strong_neutral_state_row(market_state_row)
    dynamic_speed = sleeve_reallocation_speed
    if rerisk_speed is not None:
        if market_state in {"recovery_rebound", "recovery_confirmed", "calm_trend"}:
            dynamic_speed = rerisk_speed
        elif market_state == "recovery_fragile":
            # Partial re-risk during fragile recovery: halfway between baseline speed and rerisk_speed.
            dynamic_speed = sleeve_reallocation_speed + 0.5 * (rerisk_speed - sleeve_reallocation_speed)
    if speed_mode == "asymmetric_reallocation":
        improving = (
            strong_neutral
            or market_state in {"calm_trend", "recovery_fragile", "recovery_confirmed"}
            or (prev_regime_multiplier is not None and regime_multiplier >= prev_regime_multiplier + 0.02)
        )
        deteriorating = (
            market_state == "stressed_panic"
            or (prev_regime_multiplier is not None and regime_multiplier <= prev_regime_multiplier - 0.02)
        )
        if improving:
            dynamic_speed = max(dynamic_speed, improving_speed if improving_speed is not None else 0.75)
        if deteriorating:
            dynamic_speed = min(dynamic_speed, deteriorating_speed if deteriorating_speed is not None else sleeve_reallocation_speed)
    if prev_weights is not None and not prev_weights.empty:
        prev_weights = ns5["normalize_long_only"](prev_weights.reindex(raw_weights.index).fillna(0.0), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        blended = (1.0 - dynamic_speed) * prev_weights + dynamic_speed * raw_weights
    else:
        blended = raw_weights.copy()
    blended = ns5["normalize_long_only"](blended, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    predicted_ann_vol = np.sqrt(max(float(blended.values @ cov.values @ blended.values), 0.0)) * np.sqrt(ns5["WEEKS_PER_YEAR"])
    target_vol_multiplier = (
        1.0
        if predicted_ann_vol <= 0 or pd.isna(predicted_ann_vol)
        else float(np.clip(ns5["TARGET_VOL_ANN"] / predicted_ann_vol, ns5["TARGET_VOL_FLOOR"], target_vol_ceil))
    )
    regime_binding = float(regime_multiplier < target_vol_multiplier and regime_multiplier < 0.999)
    target_vol_binding = float(target_vol_multiplier < regime_multiplier and target_vol_multiplier < 0.999)
    both_binding = float(abs(regime_multiplier - target_vol_multiplier) <= 1e-6 and regime_multiplier < 0.999)

    per_sleeve_multiplier = pd.Series(float(min(1.0, regime_multiplier, target_vol_multiplier)), index=blended.index, dtype=float)
    self_gated_relief = 0.0
    non_self_gated_relief = 0.0
    self_gated_regime_multiplier = regime_multiplier
    non_self_gated_regime_multiplier = regime_multiplier
    final_self_gated_multiplier = float(per_sleeve_multiplier.iloc[0]) if not per_sleeve_multiplier.empty else np.nan
    final_non_self_gated_multiplier = float(per_sleeve_multiplier.iloc[0]) if not per_sleeve_multiplier.empty else np.nan
    apply_self_gated_relief = False
    apply_non_self_gated_relief = False
    # self-gated relief shape
    relief_cap = 0.06
    relief_scale = 0.50
    # non-self-gated relief shape (only used when apply_non_self_gated_relief is True)
    ns_relief_cap = 0.025
    ns_relief_scale = 0.20
    ns_relief_flat: float | None = None
    if (
        overlay_penalty_mode == "lighter_self_gated"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
    ):
        apply_self_gated_relief = True
    elif (
        overlay_penalty_mode == "lighter_self_gated_targeted"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
    elif (
        # Variant A: narrower targeted follow-up. Keeps the self-gated relief
        # line intact in {strong_neutral, recovery_fragile, recovery_confirmed}
        # and ADDS a smaller, scale-bounded relief to non-self-gated sleeves in
        # {strong_neutral, recovery_fragile} ONLY. recovery_confirmed is
        # intentionally excluded for non-self-gated sleeves to respect the
        # prior rule "do not revive confirmed-recovery aggression".
        overlay_penalty_mode == "lighter_both_targeted_narrow"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
            ns_relief_flat = None
    elif (
        # Variant B: flat-form non-self-gated relief. Same self-gated behavior,
        # but the non-self-gated relief is a fixed 0.02 nudge instead of being
        # scaled by (1 - regime_multiplier). Tests whether the signal is the
        # proportional-to-binding shape or a small fixed release.
        overlay_penalty_mode == "lighter_both_targeted_flat"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_flat = 0.02
    elif (
        # Variant C: extends the narrow scale-bounded non-self-gated relief
        # from Variant A to also include recovery_confirmed, but at a tighter
        # cap (0.015 vs 0.025) so it does not count as "confirmed-recovery
        # aggression". All other states behave exactly like Variant A. Self-
        # gated relief is unchanged. Stressed-panic protection unchanged.
        overlay_penalty_mode == "lighter_both_targeted_narrow_plus_confirmed"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Sprint Variant A: `lighter_both_wider_cap`. Same structure as the
        # narrow_plus_confirmed incumbent except the non-self-gated relief is
        # widened ONLY in strong_neutral and recovery_fragile (cap 0.045,
        # scale 0.28 vs incumbent 0.025 / 0.20). recovery_confirmed remains at
        # the incumbent tight values (0.015 / 0.15). Self-gated relief line
        # is unchanged. Stressed-panic protection is unchanged. This attacks
        # the cap-driven deployment bottleneck in the two good-but-not-
        # confirmed states without reviving confirmed-recovery aggression.
        overlay_penalty_mode == "lighter_both_wider_cap"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.045
            ns_relief_scale = 0.28
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Sprint Variant B: `lighter_both_wider_cap_persistence_gated`. Same as
        # Variant A but the widened cap in strong_neutral / recovery_fragile
        # only engages when the Layer 2B causal regime engine's
        # transition_non_stress_prob is high (>= 0.92). When the persistence
        # signal is weaker, the relief falls back to the incumbent narrow
        # values (0.025 / 0.20). This tests whether conditioning deployment
        # on the regime engine's own stay-out-of-stress confidence sharpens
        # the release to the "safest" fraction of those weeks and leaves the
        # tail-prone fraction defended.
        overlay_penalty_mode == "lighter_both_wider_cap_persistence_gated"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            persistence_score = 0.0
            if isinstance(market_state_row, pd.Series):
                raw_persistence = market_state_row.get("transition_non_stress_prob", 0.0)
                try:
                    persistence_score = float(raw_persistence) if raw_persistence is not None and not pd.isna(raw_persistence) else 0.0
                except (TypeError, ValueError):
                    persistence_score = 0.0
            apply_non_self_gated_relief = True
            if persistence_score >= 0.92:
                ns_relief_cap = 0.045
                ns_relief_scale = 0.28
            else:
                ns_relief_cap = 0.025
                ns_relief_scale = 0.20
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Phase 1 Variant B: continuous causal-confidence map. Non-self-gated
        # relief cap and scale are a linear function of the Layer 2B causal
        # confidence score (persistence + breadth + trend + shallow DD). At
        # confidence=0 the relief is tighter than incumbent (0.015 / 0.15);
        # at confidence=1 it is modestly wider than incumbent in the two
        # good-but-unconfirmed states (0.045 / 0.32). recovery_confirmed is
        # kept tighter overall so the "no confirmed-recovery aggression"
        # rule is preserved. Self-gated relief and stressed-panic
        # protection are unchanged.
        overlay_penalty_mode == "lighter_both_continuous_confidence_map"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        confidence_score = compute_causal_confidence(market_state_row if isinstance(market_state_row, pd.Series) else None)
        apply_non_self_gated_relief = True
        if strong_neutral or market_state == "recovery_fragile":
            ns_relief_cap = 0.015 + confidence_score * (0.045 - 0.015)
            ns_relief_scale = 0.15 + confidence_score * (0.32 - 0.15)
        elif market_state == "recovery_confirmed":
            ns_relief_cap = 0.010 + confidence_score * (0.025 - 0.010)
            ns_relief_scale = 0.10 + confidence_score * (0.20 - 0.10)
        ns_relief_flat = None
    elif (
        # Phase 1 Variant C: confidence-gated relief. Multiplicative gate
        # on the incumbent narrow values. High confidence pushes the cap
        # up to 0.045 / 0.30; low confidence stays near incumbent 0.025 /
        # 0.20. Same state set and protections as Variant B.
        overlay_penalty_mode == "lighter_both_confidence_gated"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        confidence_score = compute_causal_confidence(market_state_row if isinstance(market_state_row, pd.Series) else None)
        apply_non_self_gated_relief = True
        if strong_neutral or market_state == "recovery_fragile":
            ns_relief_cap = 0.025 + confidence_score * 0.020
            ns_relief_scale = 0.20 + confidence_score * 0.10
        elif market_state == "recovery_confirmed":
            ns_relief_cap = 0.015 + confidence_score * 0.010
            ns_relief_scale = 0.15 + confidence_score * 0.05
        ns_relief_flat = None

    if apply_self_gated_relief:
        self_gated_names = [name for name in blended.index if name in SELF_GATED_SLEEVES]
        non_self_gated_names = [name for name in blended.index if name not in SELF_GATED_SLEEVES]
        per_sleeve_multiplier.loc[:] = regime_multiplier
        headroom = max(0.0, target_vol_multiplier - regime_multiplier)
        if self_gated_names:
            relief = min(relief_cap, relief_scale * max(0.0, 1.0 - regime_multiplier), 0.75 * headroom if headroom > 0 else relief_cap)
            self_gated_relief = max(0.0, relief)
            self_gated_regime_multiplier = min(1.0, regime_multiplier + self_gated_relief)
            per_sleeve_multiplier.loc[self_gated_names] = self_gated_regime_multiplier
        if apply_non_self_gated_relief and non_self_gated_names:
            if ns_relief_flat is not None:
                ns_relief = min(ns_relief_flat, 0.75 * headroom if headroom > 0 else ns_relief_flat)
            else:
                ns_relief = min(
                    ns_relief_cap,
                    ns_relief_scale * max(0.0, 1.0 - regime_multiplier),
                    0.75 * headroom if headroom > 0 else ns_relief_cap,
                )
            non_self_gated_relief = max(0.0, ns_relief)
            non_self_gated_regime_multiplier = min(1.0, regime_multiplier + non_self_gated_relief)
            per_sleeve_multiplier.loc[non_self_gated_names] = non_self_gated_regime_multiplier
        if target_vol_multiplier < 1.0:
            total_risky = float((blended * per_sleeve_multiplier).sum())
            if total_risky > target_vol_multiplier and total_risky > 1e-12:
                per_sleeve_multiplier *= target_vol_multiplier / total_risky
        final_self_gated_multiplier = (
            float(per_sleeve_multiplier.loc[self_gated_names].mean()) if self_gated_names else np.nan
        )
        final_non_self_gated_multiplier = (
            float(per_sleeve_multiplier.loc[non_self_gated_names].mean())
            if non_self_gated_names
            else final_self_gated_multiplier
        )

    risky_weights = blended * per_sleeve_multiplier
    gross_multiplier = float(risky_weights.sum())
    if overlay_penalty_mode == "none":
        final_self_gated_multiplier = gross_multiplier
        final_non_self_gated_multiplier = gross_multiplier
    cash_weight = max(0.0, 1.0 - risky_weights.sum())
    diagnostics = {
        "predicted_ann_vol": predicted_ann_vol,
        "target_vol_multiplier": target_vol_multiplier,
        "regime_multiplier": regime_multiplier,
        "gross_multiplier": gross_multiplier,
        "cash_weight": cash_weight,
        "dynamic_speed": dynamic_speed,
        "regime_binding": regime_binding,
        "target_vol_binding": target_vol_binding,
        "both_binding": both_binding,
        "self_gated_relief": self_gated_relief,
        "self_gated_regime_multiplier": self_gated_regime_multiplier,
        "non_self_gated_relief": non_self_gated_relief,
        "non_self_gated_regime_multiplier": non_self_gated_regime_multiplier,
        "final_self_gated_multiplier": final_self_gated_multiplier,
        "final_non_self_gated_multiplier": final_non_self_gated_multiplier,
        "overlay_penalty_mode": overlay_penalty_mode,
        "speed_mode": speed_mode,
    }
    return risky_weights, cash_weight, diagnostics


def run_subset_custom(
    method_name: str,
    subset_name: str,
    subset_sleeves: list[str],
    *,
    overlay_variant: str = "baseline",
    speed: float = ns5["SLEEVE_REALLOCATION_SPEED"],
    target_vol_ceil: float = ns5["TARGET_VOL_CEIL"],
    rerisk_speed: float | None = None,
    state_tilt: str = "none",
    layer3_expression_mode: str = "none",
    overlay_penalty_mode: str = "none",
    speed_mode: str = "default",
    improving_speed: float | None = None,
    deteriorating_speed: float | None = None,
    beta_overlay_mode: str = "none",
    market_state_history: pd.DataFrame | None = None,
    stabilize_market_state: bool = False,
    sleeve_return_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    subset = [name for name in subset_sleeves if name in sleeve_return_panel.columns]
    if not subset:
        raise ValueError(f"No valid sleeves for subset {subset_name}")
    method_spec = next(spec for spec in ns5["method_specs"] if spec["method_name"] == method_name)
    # Optional one-sided hysteresis: swap in stabilized market_state (delays entry
    # into stressed_panic by 1 week unless the entry is severe). Only used by the
    # stabilizer variants; other variants continue to use the raw market_state.
    if (
        stabilize_market_state
        and market_state_history is not None
        and "market_state_stable" in market_state_history.columns
    ):
        effective_market_state_history = market_state_history.copy()
        effective_market_state_history["market_state"] = effective_market_state_history["market_state_stable"]
    else:
        effective_market_state_history = market_state_history
    variant_regime_states = build_variant_regime_states(ns5["regime_states"], effective_market_state_history, overlay_variant)
    conviction_inputs = {
        key: value.reindex(columns=[name for name in subset if name in value.columns])
        for key, value in ns5["conviction_inputs"].items()
    }
    forward_weekly_returns = ns5["next_week_returns"].reindex(columns=ns5["weekly_prices"].columns)
    all_dates = sleeve_return_panel.index
    rebalance_dates = ns5["rebalance_mask"](all_dates, ns5["REBALANCE_FREQUENCY"])
    current_risky_alloc = pd.Series(0.0, index=subset, dtype=float)
    current_cash_weight = 1.0
    prev_regime_multiplier_value: float | None = None
    sleeve_alloc_rows: list[pd.Series] = []
    etf_weight_rows: list[pd.Series] = []
    diag_rows: list[dict] = []
    beta_overlay_rows: list[pd.Series] = []

    for date in all_dates:
        market_state_row = (
            effective_market_state_history.loc[date]
            if effective_market_state_history is not None and date in effective_market_state_history.index
            else pd.Series(dtype=float)
        )
        market_state = market_state_row.get("market_state") if isinstance(market_state_row, pd.Series) else None
        if rebalance_dates.loc[date]:
            train_slice = sleeve_return_panel.loc[:date, subset].tail(ns5["TRAIN_WINDOW_WEEKS"])
            active = ns5["select_active_sleeves"](train_slice)
            if len(active) >= 2:
                train = train_slice[active].dropna(how="any")
                if len(train) >= max(26, min(ns5["MIN_TRAIN_OBS"], ns5["TRAIN_WINDOW_WEEKS"] // 2)):
                    cov = ns5["estimate_covariance"](train, method=method_spec["covariance_method"])
                    if not cov.empty:
                        active = list(cov.index)
                        train = train.reindex(columns=active).dropna(how="any")
                        prev_active = current_risky_alloc.reindex(active).fillna(0.0)
                        mu = pd.Series(0.0, index=active)
                        bl_diag = {"view_count": 0, "view_confidence": np.nan, "view_spread": np.nan}
                        hier_diag = {"hierarchical_fallback": False, "hierarchical_reason": "", "hierarchical_valid_sleeves": len(active)}
                        expected_return_key = method_spec["expected_return_key"]
                        if expected_return_key is not None and expected_return_key in conviction_inputs:
                            score_row = conviction_inputs[expected_return_key].reindex(columns=subset).loc[date].reindex(active)
                            mu = ns5["score_row_to_weekly_mu"](score_row, train)

                        engine = method_spec["engine"]
                        if engine == "equal_weight":
                            raw = pd.Series(1.0 / len(active), index=active)
                        elif engine == "inverse_vol":
                            raw = ns5["inverse_vol_weights_from_cov"](cov)
                        elif engine == "min_variance":
                            raw = ns5["optimize_min_variance"](cov, prev_weights=prev_active)
                        elif engine == "mvo":
                            raw = ns5["optimize_mean_variance"](mu, cov, prev_weights=prev_active)
                        elif engine == "max_sharpe":
                            raw = ns5["optimize_max_sharpe"](mu, cov, prev_weights=prev_active)
                        elif engine == "black_litterman":
                            posterior_mu, bl_diag = ns5["black_litterman_posterior"](
                                cov,
                                conviction_inputs[expected_return_key].loc[date].reindex(active),
                                prior_weights=prev_active if prev_active.sum() > 0 else None,
                            )
                            raw = ns5["optimize_mean_variance"](posterior_mu, cov, prev_weights=prev_active)
                        elif engine == "erc":
                            raw = ns5["optimize_erc"](cov, prev_weights=prev_active)
                        elif engine == "hrp":
                            raw, hier_diag = ns5["optimize_hrp"](cov, return_diagnostics=True)
                        elif engine == "herc":
                            raw, hier_diag = ns5["optimize_herc"](cov, return_diagnostics=True)
                        elif engine == "max_diversification":
                            raw = ns5["optimize_max_diversification"](cov, prev_weights=prev_active)
                        elif engine == "cvar":
                            raw = ns5["optimize_cvar"](train, prev_weights=prev_active)
                        else:
                            raise ValueError(f"Unknown engine: {engine}")

                        conviction_row = (
                            compute_rolling_sleeve_conviction(
                                sleeve_return_panel, date, list(active), lookback_weeks=26
                            )
                            if state_tilt in {"dynamic_risk_budget", "dynamic_risk_budget_and_leadership"}
                            else None
                        )
                        raw = apply_state_conditioned_tilt(
                            raw,
                            market_state,
                            tilt_mode=state_tilt,
                            conviction=conviction_row,
                            market_state_row=market_state_row if isinstance(market_state_row, pd.Series) else None,
                        )
                        default_conviction_row = (
                            conviction_inputs["default_blend"].loc[date].reindex(active)
                            if "default_blend" in conviction_inputs and date in conviction_inputs["default_blend"].index
                            else pd.Series(dtype=float)
                        )
                        raw, layer3_diag = apply_layer3_expression(
                            raw,
                            market_state_row if isinstance(market_state_row, pd.Series) else None,
                            default_conviction_row,
                            expression_mode=layer3_expression_mode,
                        )
                        overlay_row = variant_regime_states.loc[date] if date in variant_regime_states.index else pd.Series(dtype=float)
                        risky_weights, cash_weight, overlay_diag = apply_overlays_custom(
                            raw,
                            cov,
                            overlay_row,
                            prev_weights=prev_active,
                            target_vol_ceil=target_vol_ceil,
                            sleeve_reallocation_speed=speed,
                            rerisk_speed=rerisk_speed,
                            market_state=market_state,
                            market_state_row=market_state_row if isinstance(market_state_row, pd.Series) else None,
                            prev_regime_multiplier=prev_regime_multiplier_value,
                            overlay_penalty_mode=overlay_penalty_mode,
                            speed_mode=speed_mode,
                            improving_speed=improving_speed,
                            deteriorating_speed=deteriorating_speed,
                        )
                        prev_regime_multiplier_value = float(overlay_diag.get("regime_multiplier", np.nan)) if overlay_diag else prev_regime_multiplier_value
                        current_risky_alloc = pd.Series(0.0, index=subset, dtype=float)
                        current_risky_alloc.loc[risky_weights.index] = risky_weights
                        current_cash_weight = cash_weight
                        diag_rows.append(
                            {
                                "Date": date,
                                "method_name": method_name,
                                "engine": engine,
                                "method_category": "improvement_lab",
                                "active_sleeves": len(active),
                                "expected_return_key": expected_return_key or "n/a",
                                "covariance_method": method_spec["covariance_method"],
                                "overlay_variant": overlay_variant,
                                "state_tilt": state_tilt,
                                "layer3_expression_mode": layer3_expression_mode,
                                "overlay_penalty_mode": overlay_penalty_mode,
                                "speed_mode": speed_mode,
                                "beta_overlay_mode": beta_overlay_mode,
                                "market_state": market_state,
                                **overlay_diag,
                                **layer3_diag,
                                **bl_diag,
                                **hier_diag,
                            }
                        )

        allocation_row = current_risky_alloc.copy()
        allocation_row.loc[f"cash::{ns5['cash_proxy']}"] = current_cash_weight
        allocation_row.name = date
        sleeve_alloc_rows.append(allocation_row)

        etf_row = ns5["build_lookthrough_etf_weights"](
            date=date,
            sleeve_weights=current_risky_alloc,
            sleeve_positions=sleeve_positions,
            universe_columns=list(forward_weekly_returns.columns),
            cash_proxy=ns5["cash_proxy"],
            cash_weight=current_cash_weight,
        )
        etf_row, beta_overlay_diag = apply_beta_participation_overlay(
            etf_row,
            market_state_row if isinstance(market_state_row, pd.Series) else None,
            beta_overlay_mode=beta_overlay_mode,
        )
        etf_row.name = date
        etf_weight_rows.append(etf_row)
        beta_overlay_rows.append(
            pd.Series(
                {
                    "beta_overlay_spy": beta_overlay_diag.get("SPY", 0.0),
                    "beta_overlay_bil": beta_overlay_diag.get(ns5["cash_proxy"], 0.0),
                },
                name=date,
            )
        )

    sleeve_alloc = pd.DataFrame(sleeve_alloc_rows).sort_index().fillna(0.0)
    etf_weights = pd.DataFrame(etf_weight_rows).sort_index().fillna(0.0)
    beta_overlay_panel = pd.DataFrame(beta_overlay_rows).sort_index().fillna(0.0)
    path = ns5["compute_portfolio_path"](
        etf_weights,
        forward_weekly_returns.reindex(index=etf_weights.index, columns=etf_weights.columns),
        transaction_cost_bps=ns5["DEFAULT_COST_BPS"],
    )
    diagnostics = pd.DataFrame(diag_rows)
    metrics = ns5["summary_metrics"](
        path["net_return"],
        turnover_series=path["turnover"],
        weight_panel=etf_weights,
        allocation_panel=sleeve_alloc,
        trials=max(len(subset), 2),
    )
    return sleeve_alloc, etf_weights, path, diagnostics, beta_overlay_panel, metrics


def version_capture_summary(
    version_name: str,
    version_returns: pd.Series,
    benchmark_returns: pd.Series,
    weight_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> dict:
    aligned = pd.concat([version_returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    positive = aligned["benchmark"] > 0
    negative = aligned["benchmark"] < 0
    upside_capture = aligned.loc[positive, "portfolio"].mean() / aligned.loc[positive, "benchmark"].mean() if positive.any() else np.nan
    downside_capture = aligned.loc[negative, "portfolio"].mean() / aligned.loc[negative, "benchmark"].mean() if negative.any() else np.nan

    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))

    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)

    joined = pd.DataFrame(
        {
            "portfolio": aligned["portfolio"],
            "benchmark": aligned["benchmark"],
            "offensive_weight": offensive_weight.reindex(aligned.index),
            "defensive_weight": defensive_weight.reindex(aligned.index),
            "cash_weight": cash_weight.reindex(aligned.index),
            "market_state": market_state_history.reindex(aligned.index)["market_state"],
        }
    )
    if not diag_idx.empty:
        for col in ["regime_multiplier", "target_vol_multiplier", "gross_multiplier", "dynamic_speed"]:
            joined[col] = diag_idx.reindex(aligned.index)[col]

    recovery_any_mask = joined["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"])
    recovery_fragile_mask = joined["market_state"].eq("recovery_fragile")
    recovery_confirmed_mask = joined["market_state"].eq("recovery_confirmed")
    calm_mask = joined["market_state"].eq("calm_trend")
    stressed_mask = joined["market_state"].eq("stressed_panic")

    def bucket_capture(mask: pd.Series) -> float:
        if not mask.any():
            return np.nan
        bench_sum = joined.loc[mask, "benchmark"].sum()
        return joined.loc[mask, "portfolio"].sum() / bench_sum if bench_sum != 0 else np.nan

    return {
        "version_name": version_name,
        "upside_capture_positive_weeks": upside_capture,
        "downside_capture_negative_weeks": downside_capture,
        "recovery_week_capture": bucket_capture(recovery_any_mask),
        "recovery_fragile_capture": bucket_capture(recovery_fragile_mask),
        "recovery_confirmed_capture": bucket_capture(recovery_confirmed_mask),
        "calm_week_capture": bucket_capture(calm_mask),
        "stress_downside_capture": bucket_capture(stressed_mask),
        "avg_offensive_when_benchmark_positive": safe_mean(joined.loc[positive, "offensive_weight"]),
        "avg_cash_when_benchmark_positive": safe_mean(joined.loc[positive, "cash_weight"]),
        "avg_regime_multiplier_when_benchmark_positive": safe_mean(joined.loc[positive, "regime_multiplier"]) if "regime_multiplier" in joined else np.nan,
        "avg_target_vol_multiplier_when_benchmark_positive": safe_mean(joined.loc[positive, "target_vol_multiplier"]) if "target_vol_multiplier" in joined else np.nan,
        "avg_dynamic_speed_when_benchmark_positive": safe_mean(joined.loc[positive, "dynamic_speed"]) if "dynamic_speed" in joined else np.nan,
    }


def top_rally_windows(benchmark_returns: pd.Series, lookback_weeks: int = 26, top_n: int = 5, min_spacing_weeks: int = 20) -> list[dict]:
    rolling = (1.0 + benchmark_returns).rolling(lookback_weeks).apply(np.prod, raw=True) - 1.0
    candidates = rolling.dropna().sort_values(ascending=False)
    selected: list[dict] = []
    used_endpoints: list[pd.Timestamp] = []
    for end_date, value in candidates.items():
        if any(abs((end_date - prev).days) < min_spacing_weeks * 7 for prev in used_endpoints):
            continue
        start_date = benchmark_returns.index[max(0, benchmark_returns.index.get_loc(end_date) - lookback_weeks + 1)]
        selected.append(
            {
                "window_name": f"top_rally_{len(selected) + 1}",
                "window_type": "auto_rally",
                "start_date": start_date,
                "end_date": end_date,
                "benchmark_return": float(value),
            }
        )
        used_endpoints.append(end_date)
        if len(selected) >= top_n:
            break
    return selected


def manual_windows(index: pd.DatetimeIndex) -> list[dict]:
    specs = [
        ("stress_2008_2009", "stress", "2007-10-12", "2009-03-06"),
        ("recovery_2009_2010", "recovery", "2009-03-13", "2010-04-30"),
        ("calm_bull_2013_2014", "rising", "2013-01-04", "2014-06-27"),
        ("choppy_2015_2016", "choppy", "2015-05-29", "2016-11-04"),
        ("stress_2020_crash", "stress", "2020-02-21", "2020-03-27"),
        ("recovery_2020_2021", "recovery", "2020-04-03", "2021-12-31"),
        ("stress_2022_rates", "stress", "2022-01-07", "2022-10-14"),
        ("recovery_2023_2024", "recovery", "2023-01-06", "2024-12-27"),
        ("calm_rally_2017_2019", "rising", "2017-01-06", "2019-12-27"),
    ]
    out = []
    min_date, max_date = index.min(), index.max()
    for name, window_type, start, end in specs:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if end_ts < min_date or start_ts > max_date:
            continue
        out.append(
            {
                "window_name": name,
                "window_type": window_type,
                "start_date": max(start_ts, min_date),
                "end_date": min(end_ts, max_date),
            }
        )
    return out


def summarize_window(
    window: dict,
    version_name: str,
    version_returns: pd.Series,
    benchmark_returns: pd.Series,
    weight_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> dict:
    start = pd.Timestamp(window["start_date"])
    end = pd.Timestamp(window["end_date"])
    version_window = version_returns.loc[(version_returns.index >= start) & (version_returns.index <= end)]
    benchmark_window = benchmark_returns.loc[(benchmark_returns.index >= start) & (benchmark_returns.index <= end)]
    aligned = pd.concat([version_window.rename("portfolio"), benchmark_window.rename("benchmark")], axis=1).dropna()
    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))

    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)

    mask = (weight_panel.index >= start) & (weight_panel.index <= end)
    weight_slice = weight_panel.loc[mask]
    market_state_slice = market_state_history.loc[(market_state_history.index >= start) & (market_state_history.index <= end)]

    benchmark_ret = cumulative_return(aligned["benchmark"])
    portfolio_ret = cumulative_return(aligned["portfolio"])
    capture = portfolio_ret / benchmark_ret if pd.notna(benchmark_ret) and benchmark_ret != 0 else np.nan

    return {
        "version_name": version_name,
        "window_name": window["window_name"],
        "window_type": window["window_type"],
        "start_date": str(start.date()),
        "end_date": str(end.date()),
        "observations": int(len(aligned)),
        "portfolio_return": portfolio_ret,
        "benchmark_return": benchmark_ret,
        "excess_return": portfolio_ret - benchmark_ret if pd.notna(portfolio_ret) and pd.notna(benchmark_ret) else np.nan,
        "capture_ratio": capture,
        "portfolio_max_drawdown": window_drawdown(aligned["portfolio"]),
        "benchmark_max_drawdown": window_drawdown(aligned["benchmark"]),
        "avg_offensive_weight": safe_mean(offensive_weight.reindex(weight_slice.index)),
        "avg_defensive_weight": safe_mean(defensive_weight.reindex(weight_slice.index)),
        "avg_cash_weight": safe_mean(cash_weight.reindex(weight_slice.index)),
        "avg_bil_weight": safe_mean(weight_panel.get("BIL", pd.Series(index=weight_panel.index, dtype=float)).reindex(weight_slice.index)),
        "avg_spy_weight": safe_mean(weight_panel.get("SPY", pd.Series(index=weight_panel.index, dtype=float)).reindex(weight_slice.index)),
        "avg_regime_multiplier": safe_mean(diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end), "regime_multiplier"]) if not diag_idx.empty else np.nan,
        "avg_target_vol_multiplier": safe_mean(diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end), "target_vol_multiplier"]) if not diag_idx.empty else np.nan,
        "avg_dynamic_speed": safe_mean(diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end), "dynamic_speed"]) if not diag_idx.empty else np.nan,
        "avg_market_state_recovery": safe_mean(market_state_slice["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"]).astype(float)),
        "avg_market_state_recovery_fragile": safe_mean(market_state_slice["market_state"].eq("recovery_fragile").astype(float)),
        "avg_market_state_recovery_confirmed": safe_mean(market_state_slice["market_state"].eq("recovery_confirmed").astype(float)),
        "avg_market_state_stressed": safe_mean(market_state_slice["market_state"].eq("stressed_panic").astype(float)),
    }


def rerisking_lag_summary(
    window: dict,
    version_name: str,
    weight_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> dict:
    start = pd.Timestamp(window["start_date"])
    end = pd.Timestamp(window["end_date"])
    offensive_assets, _ = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))
    offensive_slice = offensive_weight.loc[(offensive_weight.index >= start) & (offensive_weight.index <= end)]
    cash_slice = cash_weight.loc[(cash_weight.index >= start) & (cash_weight.index <= end)]

    def first_hit(series: pd.Series, threshold_func) -> float:
        if series.empty:
            return np.nan
        hits = np.flatnonzero(threshold_func(series.to_numpy(dtype=float)))
        return float(hits[0]) if len(hits) else np.nan

    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)
        diag_slice = diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end)]
    else:
        diag_slice = pd.DataFrame()

    return {
        "version_name": version_name,
        "window_name": window["window_name"],
        "window_type": window["window_type"],
        "weeks_to_offensive_50": first_hit(offensive_slice, lambda arr: arr >= 0.50),
        "weeks_to_offensive_60": first_hit(offensive_slice, lambda arr: arr >= 0.60),
        "weeks_to_cash_below_35": first_hit(cash_slice, lambda arr: arr <= 0.35),
        "weeks_to_cash_below_25": first_hit(cash_slice, lambda arr: arr <= 0.25),
        "avg_dynamic_speed": safe_mean(diag_slice["dynamic_speed"]) if not diag_slice.empty else np.nan,
    }


base_signal_set = ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy"]
current_signal_set = list(ns3["baseline_signal_names"])
signal_incremental_rows: list[dict] = []
signal_subset_rows: list[dict] = []

_, _, base_signal_metrics = evaluate_signal_combo(base_signal_set)
signal_incremental_rows.append(
    {
        "study": "base_core",
        "test_type": "baseline",
        "candidate_signal": "base_core",
        "signal_count": len(base_signal_set),
        "signal_names": "|".join(base_signal_set),
        **base_signal_metrics,
    }
)

for candidate in [name for name in current_signal_set if name not in base_signal_set]:
    _, _, metrics = evaluate_signal_combo(base_signal_set + [candidate])
    signal_incremental_rows.append(
        {
            "study": "base_plus_one",
            "test_type": "add_one",
            "candidate_signal": candidate,
            "signal_count": len(base_signal_set) + 1,
            "signal_names": "|".join(base_signal_set + [candidate]),
            **metrics,
            "delta_ann_return_vs_base": metrics["ann_return"] - base_signal_metrics["ann_return"],
            "delta_sharpe_vs_base": metrics["sharpe"] - base_signal_metrics["sharpe"],
            "delta_max_drawdown_vs_base": metrics["max_drawdown"] - base_signal_metrics["max_drawdown"],
            "delta_cvar_5_vs_base": metrics["cvar_5"] - base_signal_metrics["cvar_5"],
            "delta_turnover_vs_base": metrics["avg_weekly_turnover"] - base_signal_metrics["avg_weekly_turnover"],
        }
    )

_, _, full_signal_metrics = evaluate_signal_combo(current_signal_set)
signal_incremental_rows.append(
    {
        "study": "current_full",
        "test_type": "baseline",
        "candidate_signal": "current_full",
        "signal_count": len(current_signal_set),
        "signal_names": "|".join(current_signal_set),
        **full_signal_metrics,
    }
)

for candidate in [name for name in current_signal_set if name not in base_signal_set]:
    reduced = [name for name in current_signal_set if name != candidate]
    _, _, metrics = evaluate_signal_combo(reduced)
    signal_incremental_rows.append(
        {
            "study": "drop_from_current_full",
            "test_type": "drop_one",
            "candidate_signal": candidate,
            "signal_count": len(reduced),
            "signal_names": "|".join(reduced),
            **metrics,
            "delta_ann_return_vs_current_full": metrics["ann_return"] - full_signal_metrics["ann_return"],
            "delta_sharpe_vs_current_full": metrics["sharpe"] - full_signal_metrics["sharpe"],
            "delta_max_drawdown_vs_current_full": metrics["max_drawdown"] - full_signal_metrics["max_drawdown"],
            "delta_cvar_5_vs_current_full": metrics["cvar_5"] - full_signal_metrics["cvar_5"],
            "delta_turnover_vs_current_full": metrics["avg_weekly_turnover"] - full_signal_metrics["avg_weekly_turnover"],
        }
    )

signal_subset_specs = {
    "core4": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy"],
    "core4_bab": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy"],
    "core4_bab_carry": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy", "carry_proxy"],
    "current_full": current_signal_set,
    "current_drop_residual": [name for name in current_signal_set if name != "residual_momentum"],
    "current_drop_reversal": [name for name in current_signal_set if name != "reversal_4w_global"],
    "current_drop_residual_reversal": [name for name in current_signal_set if name not in {"residual_momentum", "reversal_4w_global"}],
}

for combo_name, signal_names in signal_subset_specs.items():
    _, _, metrics = evaluate_signal_combo(signal_names)
    signal_subset_rows.append(
        {
            "combo_name": combo_name,
            "signal_count": len(signal_names),
            "signal_names": "|".join(signal_names),
            **metrics,
        }
    )

signal_incremental_df = pd.DataFrame(signal_incremental_rows)
signal_subset_df = pd.DataFrame(signal_subset_rows)
signal_incremental_df.to_csv(LAYER1_DIR / "signal_incremental_contribution.csv", index=False)
signal_subset_df.to_csv(LAYER1_DIR / "signal_subset_comparison.csv", index=False)


selective_signal_names = signal_subset_specs["core4_bab_carry"]
trend_ensemble_signal_names = [
    "xsmom_global",
    "multi_mom_equal",
    "multi_mom_invvol",
    "tsmom_vol_scaled",
    "quality_proxy",
    "value_proxy",
    "bab_proxy",
    "carry_proxy",
]
selective_weights, selective_path, selective_metrics = evaluate_signal_combo(selective_signal_names)
strength_weighted_weights, strength_weighted_path, strength_weighted_metrics = evaluate_signal_combo(
    selective_signal_names,
    weight_mode="strength_weighted",
    strength_power=1.35,
)
concentrated_weights, concentrated_path, concentrated_metrics = evaluate_signal_combo(selective_signal_names, top_n=3, min_signal=0.05)
trend_ensemble_weights, trend_ensemble_path, trend_ensemble_metrics = evaluate_signal_combo(trend_ensemble_signal_names)
selective_strategy_name = "composite_selective_signals"
strength_weighted_strategy_name = "composite_selective_strength_weighted"
concentrated_strategy_name = "composite_selective_concentrated"
trend_ensemble_strategy_name = "composite_selective_trend_ensemble"

selective_summary = ns3["summary_metrics"](selective_path["net_return"], turnover_series=selective_path["turnover"])
selective_summary.update(
    {
        "strategy_name": selective_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            selective_summary["sharpe"]
            + 0.5 * selective_summary["calmar"]
            + 0.2 * selective_summary["hit_rate"]
            - 0.1 * selective_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    selective_strategy_name,
    selective_weights,
    selective_path,
    selective_summary,
    {
        "strategy_name": selective_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{selective_strategy_name}.csv",
            f"strategy_returns_{selective_strategy_name}.csv",
        ],
        "caveats": "Selective composite keeps the signals that improved the long-only ETF sleeve most cleanly in the incremental study; it is still a practical top-N proxy rather than a fully optimized ensemble.",
        "description": "Top-N long-only strategy using the selective signal blend that retained trend, quality/value, BAB, and carry while excluding weaker add-ons.",
    },
)

trend_ensemble_summary = ns3["summary_metrics"](trend_ensemble_path["net_return"], turnover_series=trend_ensemble_path["turnover"])
trend_ensemble_summary.update(
    {
        "strategy_name": trend_ensemble_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            trend_ensemble_summary["sharpe"]
            + 0.5 * trend_ensemble_summary["calmar"]
            + 0.2 * trend_ensemble_summary["hit_rate"]
            - 0.1 * trend_ensemble_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    trend_ensemble_strategy_name,
    trend_ensemble_weights,
    trend_ensemble_path,
    trend_ensemble_summary,
    {
        "strategy_name": trend_ensemble_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_tsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; multi-horizon trend signals remain lagged and are combined with the same monthly rebalance schedule as the incumbent selective sleeve.",
        "output_files": [
            f"strategy_positions_{trend_ensemble_strategy_name}.csv",
            f"strategy_returns_{trend_ensemble_strategy_name}.csv",
        ],
        "caveats": "Minimal conditional test only. This adds a simple fast/slow trend ensemble to the incumbent selective sleeve rather than redesigning Layer 1 from scratch, and it should only survive if it adds value beyond the existing momentum complex.",
        "description": "Top-N long-only sleeve that augments the incumbent selective blend with a simple multi-horizon trend ensemble (cross-sectional momentum, multi-horizon momentum, and time-series momentum).",
    },
)

strength_weighted_summary = ns3["summary_metrics"](strength_weighted_path["net_return"], turnover_series=strength_weighted_path["turnover"])
strength_weighted_summary.update(
    {
        "strategy_name": strength_weighted_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            strength_weighted_summary["sharpe"]
            + 0.5 * strength_weighted_summary["calmar"]
            + 0.2 * strength_weighted_summary["hit_rate"]
            - 0.1 * strength_weighted_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    strength_weighted_strategy_name,
    strength_weighted_weights,
    strength_weighted_path,
    strength_weighted_summary,
    {
        "strategy_name": strength_weighted_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{strength_weighted_strategy_name}.csv",
            f"strategy_returns_{strength_weighted_strategy_name}.csv",
        ],
        "caveats": "This keeps the same selective signal blend and top-N universe as the incumbent sleeve, but weights selected ETFs by normalized signal strength so strong setups can express more than merely weak-positive ones.",
        "description": "Top-N long-only sleeve that uses the selective signal blend while scaling chosen ETF weights by normalized composite signal strength rather than equal slots.",
    },
)

concentrated_summary = ns3["summary_metrics"](concentrated_path["net_return"], turnover_series=concentrated_path["turnover"])
concentrated_summary.update(
    {
        "strategy_name": concentrated_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            concentrated_summary["sharpe"]
            + 0.5 * concentrated_summary["calmar"]
            + 0.2 * concentrated_summary["hit_rate"]
            - 0.1 * concentrated_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    concentrated_strategy_name,
    concentrated_weights,
    concentrated_path,
    concentrated_summary,
    {
        "strategy_name": concentrated_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{concentrated_strategy_name}.csv",
            f"strategy_returns_{concentrated_strategy_name}.csv",
        ],
        "caveats": "This is a more selective offensive sleeve for upside-capture testing. It is only promoted if better upside participation survives the drawdown and turnover checks.",
        "description": "A more concentrated top-3 version of the selective signal sleeve, used as a disciplined upside-capture test rather than a new default.",
    },
)

market_state_history = build_market_state_history()


def build_internal_redeployed_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    market_state_hist: pd.DataFrame,
    *,
    target_sleeves: list[str],
    redeploy_config: dict[str, float] | None = None,
    strong_neutral_fraction: float = 0.30,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Phase 1 Variant D: reduce per-sleeve internal BIL in favorable states
    and redistribute to the sleeve's existing risky picks proportionally.
    Recompute sleeve returns via the canonical compute_strategy_path so
    transaction costs and cash accrual stay consistent.

    Rules:
      - Only target sleeves in `target_sleeves`; others untouched.
      - Redeploy fraction is state-dependent (see defaults).
      - 100% BIL rows are preserved (no_signal defensive role untouched).
      - Redistribution is proportional to each risky pick's existing weight.
      - No hindsight: redeploy decisions use only the market_state at date t.
    """
    if redeploy_config is None:
        redeploy_config = {
            "recovery_fragile": 0.30,
            "recovery_confirmed": 0.20,
            "calm_trend": 0.40,
        }
    cash_proxy = ns5["cash_proxy"]
    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    state_hist = market_state_hist.reindex(base_return_panel.index)

    for sleeve_name in target_sleeves:
        if sleeve_name not in new_positions:
            continue
        positions = new_positions[sleeve_name].copy()
        if cash_proxy not in positions.columns:
            continue
        modified = positions.copy()
        for date, row in positions.iterrows():
            if date not in state_hist.index:
                continue
            state_row = state_hist.loc[date]
            market_state = str(state_row.get("market_state") or "")
            strong_neutral = is_strong_neutral_state_row(state_row)
            redeploy_fraction = 0.0
            if strong_neutral:
                redeploy_fraction = strong_neutral_fraction
            elif market_state in redeploy_config:
                redeploy_fraction = redeploy_config[market_state]
            if redeploy_fraction <= 0.0:
                continue
            bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
            if bil_weight <= 0.0:
                continue
            risky_row = row.drop(cash_proxy) if cash_proxy in row.index else row
            risky_sum = float(risky_row.sum())
            if risky_sum <= 1e-9:
                # 100% BIL row: preserve defensive role (no-signal state).
                continue
            bil_shift = bil_weight * redeploy_fraction
            new_bil = bil_weight - bil_shift
            modified.at[date, cash_proxy] = new_bil
            for col in risky_row.index:
                w = float(risky_row.get(col, 0.0) or 0.0)
                if w > 0.0:
                    modified.at[date, col] = w + bil_shift * (w / risky_sum)
        new_positions[sleeve_name] = modified
        path = ns3["compute_strategy_path"](
            modified,
            ns3["next_week_returns"],
            transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
            cash_proxy_returns=ns3["cash_proxy_return_series"],
        )
        new_return_panel[sleeve_name] = path["net_return"].reindex(new_return_panel.index).fillna(0.0)

    return new_return_panel, new_positions


strategy_lookup = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
strategy_lookup = strategy_lookup.set_index("strategy_name") if not strategy_lookup.empty else pd.DataFrame().set_index(pd.Index([], name="strategy_name"))

base_sleeve_return_panel = ns5["sleeve_return_panel"].copy()
base_sleeve_positions = dict(ns5["sleeve_positions"])
base_sleeve_return_panel[selective_strategy_name] = selective_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[selective_strategy_name] = selective_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[strength_weighted_strategy_name] = strength_weighted_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[strength_weighted_strategy_name] = strength_weighted_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[concentrated_strategy_name] = concentrated_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[concentrated_strategy_name] = concentrated_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[trend_ensemble_strategy_name] = trend_ensemble_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[trend_ensemble_strategy_name] = trend_ensemble_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)

# Phase 1 Variant D: build redeployed sleeve panels once, used only by the
# Variant D version_spec (and any combo that consumes it). Other variants
# continue to use `base_sleeve_return_panel` / `base_sleeve_positions`.
redeploy_target_sleeves = ["composite_regime_conditioned", "dual_momentum_topn", "cta_trend_long_only"]
redeployed_sleeve_return_panel, redeployed_sleeve_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=redeploy_target_sleeves,
)

# Restricted redeploy for combos: drops recovery_confirmed (where standalone
# Variant D hurt badly) and keeps strong_neutral / recovery_fragile / calm
# redeploy. Used by Combo G.
redeployed_restricted_return_panel, redeployed_restricted_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=redeploy_target_sleeves,
    redeploy_config={
        "recovery_fragile": 0.25,
        "calm_trend": 0.35,
        # recovery_confirmed intentionally omitted — standalone Variant D
        # showed recovery_confirmed_capture collapse from 41% -> 29%.
    },
    strong_neutral_fraction=0.25,
)

baseline_subset = list(ns5["sleeve_return_panel"].columns)
drop_breadth_subset = [name for name in baseline_subset if name != "composite_breadth_filtered"]
replace_equal_subset = ["dual_momentum_topn", "cta_trend_long_only", selective_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
replace_equal_strength_weighted_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    strength_weighted_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
replace_equal_concentrated_subset = ["dual_momentum_topn", "cta_trend_long_only", concentrated_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
replace_equal_trend_ensemble_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    trend_ensemble_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
replace_cta_with_vol_managed_subset = [
    "dual_momentum_topn",
    "cta_trend_vol_managed",
    selective_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
improved_subset = replace_equal_subset

subset_specs = {
    "baseline_current": baseline_subset,
    "drop_breadth": drop_breadth_subset,
    "drop_regime": [name for name in baseline_subset if name != "composite_regime_conditioned"],
    "replace_equal_with_selective": replace_equal_subset,
    "replace_equal_with_strength_weighted": replace_equal_strength_weighted_subset,
    "replace_equal_with_concentrated": replace_equal_concentrated_subset,
    "replace_equal_with_trend_ensemble": replace_equal_trend_ensemble_subset,
    "replace_cta_with_vol_managed": replace_cta_with_vol_managed_subset,
    "add_selective_drop_breadth": drop_breadth_subset + [selective_strategy_name],
    "add_strength_weighted_drop_breadth": drop_breadth_subset + [strength_weighted_strategy_name],
    "add_concentrated_drop_breadth": drop_breadth_subset + [concentrated_strategy_name],
}


portfolio_version_rows: list[dict] = []
portfolio_version_regime_rows: list[pd.DataFrame] = []
portfolio_version_subperiod_rows: list[pd.DataFrame] = []
allocation_driver_rows: list[dict] = []
allocation_driver_breakdown_rows: list[dict] = []
allocation_driver_timeseries_rows: list[dict] = []
version_diagnostics_timeseries_rows: list[dict] = []
stacked_defense_timeseries_rows: list[dict] = []
sleeve_incremental_rows: list[dict] = []
sleeve_subset_rows: list[dict] = []
upside_capture_rows: list[dict] = []
rally_window_rows: list[dict] = []
targeted_window_rows: list[dict] = []
window_capture_rows: list[dict] = []
rerisk_lag_rows: list[dict] = []
state_conditioned_allocation_rows: list[dict] = []
sleeve_performance_by_state_rows: list[dict] = []


baseline_rows_by_method: dict[str, dict] = {}
for method_name in ["hrp", "max_diversification"]:
    _, baseline_weights, _, baseline_diag, _, baseline_metrics = run_subset_custom(
        method_name,
        "baseline_current",
        baseline_subset,
        overlay_variant="baseline",
        speed=ns5["SLEEVE_REALLOCATION_SPEED"],
        market_state_history=market_state_history,
        sleeve_return_panel=base_sleeve_return_panel,
        sleeve_positions=base_sleeve_positions,
    )
    baseline_rows_by_method[method_name] = {
        "metrics": baseline_metrics,
        "avg_bil": baseline_weights.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in baseline_weights.columns else np.nan,
        "avg_cash_weight": baseline_diag["cash_weight"].mean() if not baseline_diag.empty else np.nan,
    }
    for subset_name, subset_sleeves in subset_specs.items():
        _, weight_panel, path, diagnostics, _, metrics = run_subset_custom(
            method_name,
            subset_name,
            subset_sleeves,
            overlay_variant="baseline",
            speed=ns5["SLEEVE_REALLOCATION_SPEED"],
            market_state_history=market_state_history,
            sleeve_return_panel=base_sleeve_return_panel,
            sleeve_positions=base_sleeve_positions,
        )
        row = {
            "method_name": method_name,
            "subset_name": subset_name,
            "sleeve_count": len(subset_sleeves),
            "sleeve_names": "|".join(subset_sleeves),
            **metrics,
            "avg_bil_weight": weight_panel.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weight_panel.columns else np.nan,
            "avg_spy_weight": weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan,
            "avg_cash_weight": diagnostics["cash_weight"].mean() if not diagnostics.empty else np.nan,
        }
        baseline = baseline_rows_by_method[method_name]["metrics"]
        row["delta_ann_return_vs_baseline"] = row["ann_return"] - baseline["ann_return"]
        row["delta_sharpe_vs_baseline"] = row["sharpe"] - baseline["sharpe"]
        row["delta_max_drawdown_vs_baseline"] = row["max_drawdown"] - baseline["max_drawdown"]
        row["delta_cvar_5_vs_baseline"] = row["cvar_5"] - baseline["cvar_5"]
        row["delta_turnover_vs_baseline"] = row["avg_weekly_turnover"] - baseline["avg_weekly_turnover"]
        row["delta_avg_bil_vs_baseline"] = row["avg_bil_weight"] - baseline_rows_by_method[method_name]["avg_bil"]
        row["delta_avg_cash_vs_baseline"] = row["avg_cash_weight"] - baseline_rows_by_method[method_name]["avg_cash_weight"]
        sleeve_subset_rows.append(row)

        if subset_name == "baseline_current":
            continue
        changed_sleeves = sorted(set(baseline_subset).symmetric_difference(set(subset_sleeves)))
        for sleeve_name in changed_sleeves:
            standalone = strategy_lookup.loc[sleeve_name].to_dict() if sleeve_name in strategy_lookup.index else {}
            sleeve_incremental_rows.append(
                {
                    "method_name": method_name,
                    "subset_name": subset_name,
                    "candidate_sleeve": sleeve_name,
                    "standalone_ann_return": standalone.get("ann_return"),
                    "standalone_sharpe": standalone.get("sharpe"),
                    "standalone_max_drawdown": standalone.get("max_drawdown"),
                    "standalone_avg_weekly_turnover": standalone.get("avg_weekly_turnover"),
                    **row,
                }
            )


version_specs = [
    {
        "version_name": "baseline_hrp_default",
        "method_name": "hrp",
        "subset_name": "baseline_current",
        "subset_sleeves": baseline_subset,
        "overlay_variant": "baseline",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Original baseline stack with the experimental breadth sleeve still active.",
    },
    {
        "version_name": "improved_hrp_selective",
        "method_name": "hrp",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Current improved reference: selective sleeve plus a looser but still symmetric overlay.",
    },
    {
        "version_name": "improved_hrp_recovery_tilt",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Adds a causal recovery state, faster re-risking than de-risking, and modest sleeve tilts when breadth and trend confirm recovery.",
    },
    {
        "version_name": "improved_hrp_recovery_concentrated",
        "method_name": "hrp",
        "subset_name": "upside_capture_concentrated",
        "subset_sleeves": replace_equal_concentrated_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Uses the same causal recovery logic but tests a slightly stronger offensive sleeve rather than assuming the broader sleeve is always best.",
    },
    {
        "version_name": "baseline_max_div_default",
        "method_name": "max_diversification",
        "subset_name": "baseline_current",
        "subset_sleeves": baseline_subset,
        "overlay_variant": "baseline",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Original maximum-diversification baseline.",
    },
    {
        "version_name": "improved_max_div_selective",
        "method_name": "max_diversification",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Current improved maximum-diversification reference.",
    },
    {
        "version_name": "improved_max_div_recovery_tilt",
        "method_name": "max_diversification",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Maximum-diversification allocator with causal recovery re-risking and modest sleeve tilts.",
    },
    {
        "version_name": "improved_inverse_vol_recovery_tilt",
        "method_name": "inverse_vol",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Inverse-vol reference run on the best causal recovery configuration.",
    },
    {
        "version_name": "improved_herc_recovery_tilt",
        "method_name": "herc",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "HERC reference run on the best causal recovery configuration.",
    },
    # ======================================================================
    # State-split controlled experiment (Part A of the current research task)
    #
    # Control        = improved_hrp_recovery_tilt (already above).
    # Variant A      = improved_hrp_recovery_split
    #                  Splits the recovery state into fragile vs confirmed but keeps
    #                  the same symmetric "modest" offense and the same rerisk_speed
    #                  trigger as the control, so the only change under test is the
    #                  state classifier precision itself.
    # Variant B      = improved_hrp_recovery_split_confirmed_offense
    #                  Adds meaningfully stronger offense only when breadth, 13w and
    #                  26w momentum, trend, drawdown and risk score all confirm the
    #                  recovery. Fragile recovery stays modest.
    # Variant C      = improved_hrp_recovery_split_confirmed_offense_neutral_ease
    #                  Variant B + a slightly less punitive neutral-state floor in
    #                  weeks that still have a positive market trend. Targets the
    #                  residual sleeve-level BIL/cash drag outside confirmed recovery.
    # ======================================================================
    {
        "version_name": "improved_hrp_recovery_split",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_split",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_split_baseline",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "split_modest",
        "target_vol_ceil": 1.00,
        "note": "Variant A: splits recovery into fragile vs confirmed using causal breadth / 13w and 26w momentum / trend / drawdown / risk-score confirmation, but keeps the same symmetric modest offense and rerisk pacing as improved_hrp_recovery_tilt so the classifier split itself can be tested in isolation.",
    },
    {
        "version_name": "improved_hrp_recovery_split_confirmed_offense",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_split_confirmed_offense",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_split_confirmed_offense",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "split_aggressive",
        "target_vol_ceil": 1.00,
        "note": "Variant B: adds the recovery state split plus a meaningfully stronger offense ladder only in confirmed recovery. Fragile recovery stays modest and uses a partial rerisk speed to avoid leaning hard into unconfirmed bounces.",
    },
    {
        "version_name": "improved_hrp_recovery_split_confirmed_offense_neutral_ease",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_split_confirmed_offense_neutral_ease",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_split_confirmed_offense_neutral_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "split_aggressive",
        "target_vol_ceil": 1.00,
        "note": "Variant C: Variant B plus a slightly less punitive neutral-state sleeve floor during neutral weeks whose market trend is still positive. Targets the residual BIL/cash drag that shows up outside confirmed recovery without globally relaxing the neutral stance.",
    },
    # ======================================================================
    # Participation-efficiency controlled experiment (current research task)
    #
    # Control        = improved_hrp_recovery_tilt (already above).
    # Variant A      = improved_hrp_neutral_ease
    #                  Mildly reduces positive-trend neutral cash drag without
    #                  changing the recovery split or adding confirmed offense.
    # Variant B      = improved_hrp_fragile_participation
    #                  Tests whether early / fragile recovery deserves slightly
    #                  more participation than confirmed recovery.
    # Variant C      = improved_hrp_beta_participation
    #                  Adds a small state-conditioned SPY budget by recycling a
    #                  slice of BIL in good states to test the "missing beta"
    #                  hypothesis directly.
    # Variant D      = improved_hrp_neutral_fragile_combo
    #                  Best justified combination after standalone tests:
    #                  neutral easing + fragile-first participation.
    # ======================================================================
    {
        "version_name": "improved_hrp_neutral_ease",
        "method_name": "hrp",
        "subset_name": "upside_capture_neutral_ease",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Variant A: keeps the incumbent recovery logic but raises the floor modestly in positive-trend neutral weeks so benign environments carry less residual BIL drag.",
    },
    {
        "version_name": "improved_hrp_fragile_participation",
        "method_name": "hrp",
        "subset_name": "upside_capture_fragile_participation",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_fragile_participation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_first",
        "target_vol_ceil": 1.00,
        "note": "Variant B: prioritizes fragile recovery over confirmed recovery with a slightly higher floor and sleeve tilt, testing whether the system is still rerisking too late after stress breaks.",
    },
    {
        "version_name": "improved_hrp_beta_participation",
        "method_name": "hrp",
        "subset_name": "upside_capture_beta_participation",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "beta_overlay_mode": "good_state_spy",
        "target_vol_ceil": 1.00,
        "note": "Variant C: keeps the incumbent sleeve logic but recycles a small amount of BIL into SPY only in calm, fragile-recovery, and strong positive-trend neutral states to test whether missing benchmark beta is the main return lag.",
    },
    {
        "version_name": "improved_hrp_neutral_fragile_combo",
        "method_name": "hrp",
        "subset_name": "upside_capture_neutral_fragile_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease_fragile_participation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_first",
        "target_vol_ceil": 1.00,
        "note": "Variant D: combines the winning mild neutral-state easing with the modest fragile-recovery-first participation tweak, without adding explicit benchmark-beta recycling.",
    },
    # ======================================================================
    # Good-state participation bottleneck study (current task)
    # ======================================================================
    {
        "version_name": "improved_hrp_strength_weighted_selective",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_strength_weighted_selective",
        "subset_sleeves": replace_equal_strength_weighted_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant A: momentum-strength-aware sleeve deployment. The selective sleeve keeps the same signal blend and top-N count as the control, but scales selected ETF weights by signal strength so strong positive setups can express more than weak ones.",
    },
    {
        "version_name": "improved_hrp_good_state_offense",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_offense",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_participation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant B: better good-state offense rules. Calm-trend and strong positive-trend neutral weeks carry a little less overlay cash, while stressed states stay unchanged.",
    },
    {
        "version_name": "improved_hrp_layer3_expression_relax",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_layer3_expression_relax",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "good_state_conviction_relax",
        "target_vol_ceil": 1.00,
        "note": "Variant C: modest Layer 3 dampener relaxation. In calm, strong-neutral, and fragile-recovery states, HRP shifts a small budget from defensive sleeves toward the strongest offensive sleeves rather than holding the defensive mix flat.",
    },
    {
        "version_name": "improved_hrp_fragile_expression",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_fragile_expression",
        "subset_sleeves": improved_subset,
        "overlay_variant": "fragile_expression_only",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant D: modest fragile-recovery expression only. It raises fragile-recovery participation slightly without reviving any stronger confirmed-recovery offense ladder.",
    },
    {
        "version_name": "improved_hrp_neutral_ease_beta_diag",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_beta_diagnostic",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "none",
        "beta_overlay_mode": "good_state_spy_light",
        "target_vol_ceil": 1.00,
        "note": "Variant F: controlled broad-beta diagnostic. Starting from the neutral-ease control, recycle only a small amount of BIL into SPY in clearly good states to test whether missing beta is still a major part of the lag.",
    },
    {
        "version_name": "improved_hrp_good_state_fragile_combo",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_fragile_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant E (prior round): best justified combination after the standalone pass. Keeps the stronger good-state overlay floors and combines them with modest fragile-recovery expression.",
    },
    # ======================================================================
    # Transition-aware / stabilizer / mix-rotation study (current research task)
    #
    # Control        = improved_hrp_good_state_fragile_combo (above).
    # Variant A      = improved_hrp_good_state_transition_aware
    #                  Uses trailing-window P(stay) and P(next in good state) to
    #                  lift the strong-neutral floor only when the current regime
    #                  is observationally both persistent and benign-continuing.
    # Variant B      = improved_hrp_good_state_stabilizer
    #                  One-sided hysteresis on entry into stressed_panic to damp
    #                  1-week false entries; does not delay exits.
    # Variant C      = improved_hrp_good_state_strong_offense
    #                  Raises the strong-neutral floor 0.94 -> 0.98 and the base
    #                  neutral floor 0.80 -> 0.83 so clearly benign states carry
    #                  less residual overlay cash.
    # Variant D      = improved_hrp_good_state_mix_rotation
    #                  Rotates away from composite_regime_conditioned in calm and
    #                  recovery_fragile (low sleeve-by-state Sharpe) and toward
    #                  the trend-following trio; no overlay floor change.
    # Variant E      = improved_hrp_good_state_combo_plus
    #                  Combines A + B + C + D where each helped or was neutral.
    # ======================================================================
    {
        "version_name": "improved_hrp_good_state_transition_aware",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_transition_aware",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_transition_aware",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant A: adds an observable, causal transition-matrix feature (trailing 156w P(stay) and P(next in good state)) and lifts the strong-neutral floor 0.94 -> 0.97 only when both are high, so benign-continuing regimes deploy more fully without globally relaxing the neutral stance.",
    },
    {
        "version_name": "improved_hrp_good_state_stabilizer",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_stabilizer",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_stabilizer",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "stabilize_market_state": True,
        "note": "Variant B: one-sided hysteresis on entry into stressed_panic. A new stressed week is delayed by one week unless drawdown is already <= -10% or the risk_regime_score > 0.85. Exits are never delayed, so the de-risking response to real stress is preserved.",
    },
    {
        "version_name": "improved_hrp_good_state_strong_offense",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_strong_offense",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_strong_offense",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant C: stronger strong-neutral and calm offense. Raises the strong-neutral overlay floor 0.94 -> 0.98 and the base neutral floor 0.80 -> 0.83 so the 45 percent of history that sits in neutral_mixed carries less residual overlay cash.",
    },
    {
        "version_name": "improved_hrp_good_state_mix_rotation",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_mix_rotation",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_mix_rotation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus_mix_rotation",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant D: better good-state sleeve mix. Rotates weight away from composite_regime_conditioned (weakest sleeve-by-state Sharpe in calm and fragile) and toward the trend-following trio (dual_momentum, cta_trend, composite_selective_signals) in those states; overlay floors unchanged.",
    },
    {
        "version_name": "improved_hrp_good_state_combo_plus",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_combo_plus",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_combo_plus",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus_mix_rotation",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "stabilize_market_state": True,
        "note": "Variant E: combination build. Uses the stabilizer (B), raises the strong-neutral floor to 0.97 with a further transition-aware lift to 0.98 when the trailing transition matrix says the regime is persistent and benign-continuing, and pairs the mix-rotation tilt (D). Keeps the neutral base floor at 0.83 (C).",
    },
    # ======================================================================
    # Stacked-defense tax study (current research task)
    #
    # Control        = improved_hrp_good_state_fragile_combo (above).
    # Variant A      = improved_hrp_stacked_defense_continuous_overlay
    #                  Replace the blunt neutral-state overlay response with a
    #                  bounded continuous map from risk_regime_score into neutral
    #                  deployment, while keeping the control's calm/recovery/stress
    #                  floors.
    # Variant B      = improved_hrp_stacked_defense_self_gated_overlay
    #                  Apply a lighter regime haircut to sleeves that already
    #                  self-gate internally (dual_momentum, cta_trend, taa_10m_sma)
    #                  so they are not de-risked twice in good states.
    # Variant C      = improved_hrp_stacked_defense_asymmetric_speed
    #                  Keep the control overlay, but let re-risking happen faster
    #                  in improving / strong-neutral states while leaving
    #                  deteriorating states at the baseline speed.
    # Variant D      = improved_hrp_stacked_defense_continuous_self_gated_combo
    #                  Best justified combination after the standalone readout:
    #                  pair the smoother continuous neutral mapping (A) with the
    #                  lighter haircut on self-gated sleeves (B). This tests
    #                  whether the deployment gain from A can survive once the
    #                  double-defense tax on internally gated sleeves is reduced.
    # ======================================================================
    {
        "version_name": "improved_hrp_stacked_defense_continuous_overlay",
        "method_name": "hrp",
        "subset_name": "stacked_defense_continuous_overlay",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant A: continuous overlay mapping only. Neutral-state deployment is mapped continuously from risk_regime_score instead of relying on the current blunt neutral response, while calm/recovery/stress keep the control floors.",
    },
    {
        "version_name": "improved_hrp_stacked_defense_self_gated_overlay",
        "method_name": "hrp",
        "subset_name": "stacked_defense_self_gated_overlay",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated",
        "target_vol_ceil": 1.00,
        "note": "Variant B: reduced overlay penalty on self-gated sleeves only. Dual momentum, CTA trend, and TAA already gate risk internally, so the portfolio overlay applies a lighter regime haircut to them outside stressed states.",
    },
    {
        "version_name": "improved_hrp_stacked_defense_asymmetric_speed",
        "method_name": "hrp",
        "subset_name": "stacked_defense_asymmetric_speed",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "speed_mode": "asymmetric_reallocation",
        "improving_speed": 0.80,
        "deteriorating_speed": 0.40,
        "target_vol_ceil": 1.00,
        "note": "Variant C: asymmetric reallocation speed only. Strong-neutral and improving good states re-risk faster, while deteriorating states stay on the baseline de-risk speed rather than slowing the defense response.",
    },
    {
        "version_name": "improved_hrp_stacked_defense_continuous_self_gated_combo",
        "method_name": "hrp",
        "subset_name": "stacked_defense_continuous_self_gated_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated",
        "target_vol_ceil": 1.00,
        "note": "Variant D: justified A+B combination only. Keep the continuous neutral-state overlay map, but reduce the portfolio-level haircut on sleeves that already self-gate internally so the smoother overlay does not still double-tax the same sleeves.",
    },
    # ======================================================================
    # Disciplined good-state deployment sprint (current research task)
    #
    # Control        = improved_hrp_good_state_fragile_combo (above).
    # Variant A      = improved_hrp_self_gated_relief_targeted
    #                  Tight, state-targeted relief for internally self-gated
    #                  sleeves only in strong-neutral and recovery states.
    # Variant B      = improved_hrp_continuous_overlay_careful
    #                  Conservative continuous mapping that mainly smooths
    #                  strong-neutral deployment while preserving stressed-state
    #                  protection and the control's recovery floors.
    # Variant C      = improved_hrp_targeted_relief_continuous_combo
    #                  Best justified A+B combination if the standalone readout
    #                  says both attack the same stacked-defense bottleneck.
    # Variant D      = improved_hrp_separate_canary_proxy
    #                  Minimal separate-canary overlay check using a tiny
    #                  principled canary proxy pair rather than broad mining.
    # Variant E      = improved_hrp_threshold_recentering
    #                  Tiny threshold recentering only; no broader tuning.
    # Variant F      = improved_hrp_trend_horizon_ensemble
    #                  Minimal horizon-ensemble trend sleeve replacing the
    #                  current equal-weight selective sleeve.
    # Variant G      = improved_hrp_cta_vol_managed_local
    #                  Sleeve-local volatility management by swapping in the
    #                  existing vol-managed CTA sleeve for the long-only CTA
    #                  sleeve, leaving the broader portfolio stack intact.
    # ======================================================================
    {
        "version_name": "improved_hrp_self_gated_relief_targeted",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_self_gated_relief_targeted",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated_targeted",
        "target_vol_ceil": 1.00,
        "note": "Variant A: reduce the overlay penalty only for sleeves that already self-gate internally, and only in strong-neutral plus early-recovery states. Keeps stressed-state protection and broader overlay discipline intact.",
    },
    {
        "version_name": "improved_hrp_continuous_overlay_careful",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_continuous_overlay_careful",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping_careful",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant B: a more careful continuous overlay map. It smooths deployment mainly in strong-neutral weeks while keeping weak-neutral and stressed states close to the control path.",
    },
    {
        "version_name": "improved_hrp_targeted_relief_continuous_combo",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_targeted_relief_continuous_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping_careful",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated_targeted",
        "target_vol_ceil": 1.00,
        "note": "Variant C: pair the careful continuous map with the tighter self-gated relief so only the sleeves most exposed to double-defense get extra release in good states.",
    },
    {
        "version_name": "improved_hrp_separate_canary_proxy",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_separate_canary_proxy",
        "subset_sleeves": improved_subset,
        "overlay_variant": "separate_canary_proxy",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant D: minimal separate-canary test. Uses a tiny canary proxy pair to modestly lift deployment only when the canary pair is fully healthy, without broad architecture sprawl.",
    },
    {
        "version_name": "improved_hrp_threshold_recentering",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_threshold_recentering",
        "subset_sleeves": improved_subset,
        "overlay_variant": "threshold_recentering",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant E: tiny threshold recentering only. Broadens the strong-neutral bucket slightly while leaving the rest of the control architecture intact.",
    },
    {
        "version_name": "improved_hrp_trend_horizon_ensemble",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_trend_horizon_ensemble",
        "subset_sleeves": replace_equal_trend_ensemble_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant F: replace the current selective sleeve with a simple multi-horizon trend ensemble sleeve to test whether a more graded trend aggregate improves deployment translation beyond the existing Layer 1 momentum blend.",
    },
    {
        "version_name": "improved_hrp_cta_vol_managed_local",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_cta_vol_managed_local",
        "subset_sleeves": replace_cta_with_vol_managed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant G: sleeve-local volatility-aware deployment. Swaps in the existing vol-managed CTA sleeve in place of the long-only CTA sleeve, leaving the broader overlay and allocator stack unchanged.",
    },
    # ======================================================================
    # Non-self-gated overlay relief study (current sprint)
    #
    # Motivation: `improved_hrp_self_gated_relief_targeted` was the cleanest
    # positive result on the prior sprint but the delta was too small to
    # beat the promotion margin. The remaining overlay-cash bottleneck is on
    # the non-self-gated sleeves (composite_selective_signals and
    # composite_regime_conditioned) in strong-neutral and recovery-fragile
    # states, where sleeves self-defend AND overlay cuts again AND target-vol
    # is not binding. The follow-up is to extend relief narrowly to those
    # non-self-gated sleeves, with tighter caps, in only those two states.
    #
    # Control     = improved_hrp_good_state_fragile_combo (above).
    # Variant A   = improved_hrp_non_self_gated_relief_narrow
    #               Scale-bounded non-self-gated relief (cap 0.025, scale
    #               0.20) in strong_neutral + recovery_fragile ONLY. Keeps
    #               the existing self-gated relief shape (cap 0.04, scale
    #               0.35) in strong_neutral + recovery_fragile + recovery_
    #               confirmed. Non-self-gated relief deliberately excludes
    #               recovery_confirmed to avoid reviving confirmed-recovery
    #               aggression.
    # Variant B   = improved_hrp_non_self_gated_relief_flat
    #               Same structure but non-self-gated relief is a flat 0.02
    #               nudge (no scaling). Tests whether the signal is in the
    #               proportional-to-binding shape or just a small fixed
    #               release.
    # Variant C   = improved_hrp_non_self_gated_relief_combo
    #               Created only if A and B each independently clear the
    #               Pareto bar. Pairs the narrower shape with the existing
    #               careful continuous map. Held in reserve; only added in
    #               a follow-up edit if warranted.
    # ======================================================================
    {
        "version_name": "improved_hrp_non_self_gated_relief_narrow",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_non_self_gated_relief_narrow",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow",
        "target_vol_ceil": 1.00,
        "note": "Variant A: extend overlay relief narrowly to non-self-gated sleeves (composite_selective_signals, composite_regime_conditioned) only in strong_neutral and recovery_fragile, cap 0.025 and scale 0.20. Self-gated relief line unchanged. Stressed-panic protection unchanged. Does not touch recovery_confirmed on the non-self-gated side.",
    },
    {
        "version_name": "improved_hrp_non_self_gated_relief_flat",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_non_self_gated_relief_flat",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_flat",
        "target_vol_ceil": 1.00,
        "note": "Variant B: same targeted state set as Variant A but the non-self-gated relief is a flat 0.02 nudge instead of scaled by (1 - regime_multiplier). Tests shape sensitivity.",
    },
    {
        "version_name": "improved_hrp_non_self_gated_relief_narrow_plus_confirmed",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_non_self_gated_relief_narrow_plus_confirmed",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant C: extends Variant A's non-self-gated relief to recovery_confirmed at a tighter cap (0.015) and scale (0.15). Tests whether the signal strengthens when the relief reaches additional binding weeks without crossing into confirmed-recovery aggression.",
    },
    # ======================================================================
    # Narrow sleeve-leadership follow-up (current research task)
    #
    # Control     = improved_hrp_non_self_gated_relief_narrow_plus_confirmed.
    # Variant A   = improved_hrp_confirmed_leadership
    #               Keep the incumbent overlay / relief logic, but rotate sleeve
    #               leadership inside recovery_confirmed toward the sleeves that
    #               actually lead there (CTA trend, then TAA) and away from the
    #               laggards (selective, regime-conditioned).
    # Variant B   = improved_hrp_calm_confirmed_leadership
    #               Extend the same idea to calm_trend, where overlay cash is
    #               already low and the remaining drag appears to come from a
    #               still-too-heavy regime-conditioned sleeve.
    # Variant C   = improved_hrp_calm_confirmed_fragile_leadership
    #               Add a more selective fragile-recovery leadership rotation to
    #               Variant B, favoring CTA and dual momentum over the weaker
    #               sleeves in that handoff regime.
    # ======================================================================
    {
        "version_name": "improved_hrp_confirmed_leadership",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_confirmed_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "confirmed_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant A: keep the current gross-risk and overlay design, but improve recovery_confirmed sleeve leadership by rotating toward CTA trend and TAA, away from selective and regime-conditioned sleeves that have lagged in that state.",
    },
    {
        "version_name": "improved_hrp_calm_confirmed_leadership",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_calm_confirmed_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "calm_confirmed_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant B: extend the leadership rotation to calm_trend as well. Targets the remaining undercapture in prolonged benign markets where overlay cash is already low and sleeve mix looks like the bottleneck.",
    },
    {
        "version_name": "improved_hrp_calm_confirmed_fragile_leadership",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_calm_confirmed_fragile_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "calm_confirmed_fragile_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant C: add a selective fragile-recovery leadership rotation on top of Variant B, favoring CTA and dual momentum in recovery_fragile while still keeping the incumbent overlay state set and stressed-state protection intact.",
    },
    # ======================================================================
    # Final classical sprint: wider overlay-cash relief in the two good-but-
    # not-confirmed states (strong_neutral, recovery_fragile).
    #
    # Control     = improved_hrp_non_self_gated_relief_narrow_plus_confirmed
    #               (incumbent, identical sleeve/state logic, incumbent caps).
    # Variant A   = improved_hrp_overlay_cash_wider_cap
    #               Same structure as the incumbent but widens the non-self-
    #               gated relief cap from 0.025 -> 0.045 and the scale from
    #               0.20 -> 0.28 in strong_neutral and recovery_fragile only.
    #               recovery_confirmed keeps incumbent tight values (0.015 /
    #               0.15). Self-gated relief and stressed-panic protection
    #               are unchanged. Directly attacks the cap-bound overlay
    #               cash (~15.3% / ~13.0%) in those two states.
    # Variant B   = improved_hrp_overlay_cash_wider_cap_persistence_gated
    #               Persistence-conditioned version of A. Engages the widened
    #               cap only when the Layer 2B causal regime engine's
    #               transition_non_stress_prob >= 0.92; otherwise falls back
    #               to incumbent narrow (0.025 / 0.20). Tests whether
    #               conditioning deployment on the regime engine's own
    #               stay-out-of-stress confidence cleans the tail.
    # ======================================================================
    {
        "version_name": "improved_hrp_overlay_cash_wider_cap",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_overlay_cash_wider_cap",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_wider_cap",
        "target_vol_ceil": 1.00,
        "note": "Sprint Variant A: widen the non-self-gated relief cap (0.025 -> 0.045) and scale (0.20 -> 0.28) in strong_neutral and recovery_fragile only. recovery_confirmed unchanged (0.015 / 0.15). Self-gated relief unchanged. Stressed-panic protection unchanged. Directly targets the ~15% strong_neutral and ~13% recovery_fragile overlay-cash that is cap-bound, not vol-bound.",
    },
    {
        "version_name": "improved_hrp_overlay_cash_wider_cap_persistence_gated",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_overlay_cash_wider_cap_persistence_gated",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_wider_cap_persistence_gated",
        "target_vol_ceil": 1.00,
        "note": "Sprint Variant B: persistence-gated widening. Same structure as Variant A but the widened non-self-gated cap (0.045 / 0.28) only fires when the Layer 2B regime engine's transition_non_stress_prob >= 0.92; otherwise falls back to incumbent narrow (0.025 / 0.20). recovery_confirmed unchanged. Self-gated relief unchanged. Stressed-panic protection unchanged.",
    },
    # ======================================================================
    # Phase 1 upgrade sprint (current sprint). Tests five standalone Phase 1
    # improvements plus justified combinations. Control for all of these is
    # `improved_hrp_non_self_gated_relief_narrow_plus_confirmed` (incumbent).
    #
    # Variant A  = improved_hrp_phase1_dynamic_risk_budget
    #   Dynamic risk budgeting: rolling-Sharpe rank-based ±15% sleeve
    #   conviction tilt in favorable states only. Stressed-panic keeps
    #   the existing defensive shift.
    # Variant B  = improved_hrp_phase1_continuous_confidence
    #   Continuous causal-confidence map: non-self-gated relief cap and
    #   scale linearly interpolated by the Layer 2B confidence score.
    # Variant C  = improved_hrp_phase1_confidence_gated
    #   Confidence-gated relief: multiplicative confidence gate on the
    #   incumbent narrow values.
    # Variant D  = improved_hrp_phase1_internal_redeploy
    #   Sleeve-internal cash redesign: reduce per-sleeve BIL in favorable
    #   states, redistribute to existing risky picks. Recomputed through
    #   the canonical compute_strategy_path cost model. Defensive full-
    #   BIL rows preserved.
    # Variant E  = improved_hrp_phase1_leadership
    #   Good-state sleeve leadership rotation bounded at ±15% per sleeve.
    # ======================================================================
    {
        "version_name": "improved_hrp_phase1_dynamic_risk_budget",
        "method_name": "hrp",
        "subset_name": "phase1_dynamic_risk_budget",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant A: rolling 26w rank-based sleeve-conviction tilt (±15%) in favorable states; incumbent overlay relief kept. Stressed-panic unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_continuous_confidence",
        "method_name": "hrp",
        "subset_name": "phase1_continuous_confidence",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_continuous_confidence_map",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant B: continuous causal-confidence map on the non-self-gated relief. cap/scale LERP from tight (0.015/0.15) at confidence=0 to wide (0.045/0.32) at confidence=1 in strong_neutral and recovery_fragile; recovery_confirmed kept tighter (0.010-0.025 / 0.10-0.20). Self-gated relief unchanged. Stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_confidence_gated",
        "method_name": "hrp",
        "subset_name": "phase1_confidence_gated",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_confidence_gated",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant C: multiplicative confidence gate on the incumbent narrow values. ns_relief_cap = 0.025 + confidence*0.020; ns_relief_scale = 0.20 + confidence*0.10 in strong_neutral and recovery_fragile; recovery_confirmed uses tighter additive gates (0.015+conf*0.010 / 0.15+conf*0.05). Self-gated relief unchanged. Stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_internal_redeploy",
        "method_name": "hrp",
        "subset_name": "phase1_internal_redeploy",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "internal_redeploy": True,
        "note": "Phase 1 Variant D: sleeve-internal cash redesign. Reduce per-sleeve internal BIL by 30% in strong_neutral and recovery_fragile, 20% in recovery_confirmed, 40% in calm_trend; redistribute to existing risky picks proportionally. Targets composite_regime_conditioned, dual_momentum_topn, cta_trend_long_only. 100%-BIL defensive rows preserved. Recomputed through compute_strategy_path. Overlay/tilt unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_leadership",
        "method_name": "hrp",
        "subset_name": "phase1_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase1_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant E: bounded ±15% good-state sleeve-leadership rotation. Calm_trend and strong_neutral favor trend trio + TAA / selective and fade regime_conditioned; recovery_confirmed favors CTA/TAA; recovery_fragile favors CTA + dual momentum. Overlay relief and gross-risk unchanged.",
    },
    # ======================================================================
    # Phase 1 justified combinations (current sprint).
    #
    # Combo F  = improved_hrp_phase1_combo_f_a_plus_e
    #   Two-way combo of the cleanest winner (A, dynamic risk budgeting)
    #   and the closest-to-neutral variant (E, leadership rotation).
    #   Applies the leadership rotation first, then layers a dampened
    #   conviction tilt on top (±10% instead of ±15%) to avoid compound
    #   blow-ups. Incumbent overlay/relief kept.
    # Combo G  = improved_hrp_phase1_combo_g_a_e_d_restricted
    #   Three-way combo of A + E + a restricted version of D that
    #   excludes recovery_confirmed (where standalone D hurt capture
    #   materially) and runs internal redeploy at lower fractions in
    #   strong_neutral / recovery_fragile / calm_trend only. Tests
    #   whether the disciplined D layer helps once A+E has set a
    #   cleaner sleeve mix.
    # ======================================================================
    {
        "version_name": "improved_hrp_phase1_combo_f_a_plus_e",
        "method_name": "hrp",
        "subset_name": "phase1_combo_f",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_and_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Combo F: dynamic risk budgeting (A, dampened to ±10%) layered on top of good-state leadership rotation (E, ±15%). Same state set as A, B, C, E. Incumbent overlay relief kept. Stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_combo_g_a_e_d_restricted",
        "method_name": "hrp",
        "subset_name": "phase1_combo_g",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_and_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "internal_redeploy": "restricted",
        "note": "Phase 1 Combo G: Combo F (A + E) plus restricted sleeve-internal cash redeploy (D-restricted) in strong_neutral (25%), recovery_fragile (25%), calm_trend (35%). recovery_confirmed intentionally EXCLUDED (standalone D hurt capture there). Targets composite_regime_conditioned, dual_momentum_topn, cta_trend_long_only. Incumbent overlay relief kept.",
    },
]


benchmark_market_returns = load_benchmark_returns("strategy_returns_baseline_market_proxy_buy_hold.csv")
benchmark_6040_returns = load_benchmark_returns("strategy_returns_baseline_60_40_proxy.csv")

version_results: dict[str, dict] = {}
version_baselines: dict[str, dict] = {}

for version in version_specs:
    version_redeploy_mode = version.get("internal_redeploy", False)
    if version_redeploy_mode == "restricted":
        version_sleeve_return_panel = redeployed_restricted_return_panel
        version_sleeve_positions = redeployed_restricted_positions
    elif bool(version_redeploy_mode):
        version_sleeve_return_panel = redeployed_sleeve_return_panel
        version_sleeve_positions = redeployed_sleeve_positions
    else:
        version_sleeve_return_panel = base_sleeve_return_panel
        version_sleeve_positions = base_sleeve_positions
    sleeve_alloc, weight_panel, path, diagnostics, beta_overlay_panel, metrics = run_subset_custom(
        version["method_name"],
        version["subset_name"],
        version["subset_sleeves"],
        overlay_variant=version["overlay_variant"],
        speed=version["sleeve_reallocation_speed"],
        rerisk_speed=version["rerisk_speed"],
        state_tilt=version["state_tilt"],
        layer3_expression_mode=version.get("layer3_expression_mode", "none"),
        overlay_penalty_mode=version.get("overlay_penalty_mode", "none"),
        speed_mode=version.get("speed_mode", "default"),
        improving_speed=version.get("improving_speed"),
        deteriorating_speed=version.get("deteriorating_speed"),
        beta_overlay_mode=version.get("beta_overlay_mode", "none"),
        target_vol_ceil=version["target_vol_ceil"],
        market_state_history=market_state_history,
        stabilize_market_state=bool(version.get("stabilize_market_state", False)),
        sleeve_return_panel=version_sleeve_return_panel,
        sleeve_positions=version_sleeve_positions,
    )

    weight_panel.to_csv(LAYER3_DIR / f"portfolio_version_weights_{version['version_name']}.csv")
    sleeve_alloc.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version['version_name']}.csv")
    path.to_csv(LAYER3_DIR / f"portfolio_version_returns_{version['version_name']}.csv")

    regime_split = ns5["regime_split_summary"](version["version_name"], path["net_return"], ns5["regime_states"].get("risk_state", pd.Series(dtype=object)))
    subperiod_split = ns5["subperiod_summary"](version["version_name"], path["net_return"])
    if not regime_split.empty:
        portfolio_version_regime_rows.append(regime_split)
    if not subperiod_split.empty:
        portfolio_version_subperiod_rows.append(subperiod_split)

    avg_bil = weight_panel.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weight_panel.columns else np.nan
    avg_spy = weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan
    avg_cash = diagnostics["cash_weight"].mean() if not diagnostics.empty else np.nan

    row = {
        **version,
        "beta_overlay_mode": version.get("beta_overlay_mode", "none"),
        **metrics,
        "avg_bil_weight": avg_bil,
        "avg_spy_weight": avg_spy,
        "avg_cash_weight": avg_cash,
        "avg_beta_overlay_spy": beta_overlay_panel["beta_overlay_spy"].mean() if not beta_overlay_panel.empty else 0.0,
        "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_dynamic_speed": diagnostics["dynamic_speed"].mean() if not diagnostics.empty else np.nan,
        "avg_layer3_expression_shift": diagnostics["layer3_expression_shift"].mean() if not diagnostics.empty and "layer3_expression_shift" in diagnostics.columns else 0.0,
        "layer3_expression_trigger_rate": diagnostics["layer3_expression_triggered"].mean() if not diagnostics.empty and "layer3_expression_triggered" in diagnostics.columns else 0.0,
    }
    family = version["method_name"]
    if version["version_name"].startswith("baseline_"):
        version_baselines[family] = row
    elif family in version_baselines:
        base = version_baselines[family]
        for key in [
            "ann_return",
            "ann_vol",
            "sharpe",
            "max_drawdown",
            "calmar",
            "cvar_5",
            "avg_weekly_turnover",
            "avg_effective_n",
            "avg_bil_weight",
            "avg_spy_weight",
            "avg_cash_weight",
        ]:
            row[f"delta_{key}_vs_baseline"] = row[key] - base[key]
    portfolio_version_rows.append(row)

    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))
    overlay_cash = sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", pd.Series(0.0, index=weight_panel.index))
    sleeve_bil = (cash_weight - overlay_cash).clip(lower=0.0)
    beta_overlay_spy = beta_overlay_panel.get("beta_overlay_spy", pd.Series(0.0, index=weight_panel.index))
    beta_overlay_bil = beta_overlay_panel.get("beta_overlay_bil", pd.Series(0.0, index=weight_panel.index))
    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)
    else:
        diag_idx = pd.DataFrame(index=weight_panel.index)
    latest_date = weight_panel.index[-1]
    current_offensive = offensive_weight.loc[latest_date]
    current_defensive = defensive_weight.loc[latest_date]
    current_cash = cash_weight.loc[latest_date]
    current_state = version_state_label(current_offensive, current_defensive, current_cash)

    allocation_driver_rows.append(
        {
            "version_name": version["version_name"],
            "method_name": version["method_name"],
            "current_date": str(latest_date.date()),
            "current_risk_state": ns5["regime_states"].loc[latest_date, "risk_state"] if latest_date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
            "current_market_state": market_state_history.loc[latest_date, "market_state"] if latest_date in market_state_history.index else None,
            "current_market_state_reason": market_state_history.loc[latest_date, "market_state_reason"] if latest_date in market_state_history.index else None,
            "current_state_label": current_state,
            "current_offensive_weight": current_offensive,
            "current_defensive_weight": current_defensive,
            "current_cash_proxy_weight": current_cash,
            "current_bil_weight": cash_weight.loc[latest_date],
            "current_spy_weight": weight_panel.loc[latest_date].get("SPY", np.nan),
            "avg_offensive_weight": offensive_weight.mean(),
            "avg_defensive_weight": defensive_weight.mean(),
            "avg_cash_proxy_weight": cash_weight.mean(),
            "avg_bil_weight": cash_weight.mean(),
            "avg_spy_weight": weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan,
            "avg_overlay_cash_weight": overlay_cash.mean(),
            "avg_sleeve_bil_weight": sleeve_bil.mean(),
            "avg_beta_overlay_spy_weight": beta_overlay_spy.mean(),
            "current_overlay_cash_weight": overlay_cash.loc[latest_date],
            "current_sleeve_bil_weight": sleeve_bil.loc[latest_date],
            "current_beta_overlay_spy_weight": beta_overlay_spy.loc[latest_date],
            "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_dynamic_speed": diagnostics["dynamic_speed"].mean() if not diagnostics.empty else np.nan,
            "avg_layer3_expression_shift": diagnostics["layer3_expression_shift"].mean() if not diagnostics.empty and "layer3_expression_shift" in diagnostics.columns else 0.0,
            "layer3_expression_trigger_rate": diagnostics["layer3_expression_triggered"].mean() if not diagnostics.empty and "layer3_expression_triggered" in diagnostics.columns else 0.0,
            "calm_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("calm").mean(),
            "neutral_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("neutral").mean(),
            "stressed_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("stressed").mean(),
            "recovery_market_state_frequency": market_state_history["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"]).mean(),
            "calm_market_state_frequency": market_state_history["market_state"].eq("calm_trend").mean(),
        }
    )

    for date in weight_panel.index:
        diag_row = diag_idx.loc[date] if date in diag_idx.index else pd.Series(dtype=float)
        regime_multiplier = float(diag_row.get("regime_multiplier", np.nan)) if len(diag_row) else np.nan
        target_vol_multiplier = float(diag_row.get("target_vol_multiplier", np.nan)) if len(diag_row) else np.nan
        gross_multiplier = float(diag_row.get("gross_multiplier", np.nan)) if len(diag_row) else np.nan
        self_gated_multiplier = float(diag_row.get("final_self_gated_multiplier", gross_multiplier)) if len(diag_row) else np.nan
        non_self_gated_multiplier = float(diag_row.get("final_non_self_gated_multiplier", gross_multiplier)) if len(diag_row) else np.nan
        if pd.isna(regime_multiplier):
            binding_source = "none"
        elif abs(regime_multiplier - target_vol_multiplier) <= 1e-6 and regime_multiplier < 0.999:
            binding_source = "both"
        elif regime_multiplier < target_vol_multiplier and regime_multiplier < 0.999:
            binding_source = "regime"
        elif target_vol_multiplier < regime_multiplier and target_vol_multiplier < 0.999:
            binding_source = "target_vol"
        else:
            binding_source = "none"
        version_diagnostics_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
                "regime_multiplier": regime_multiplier,
                "target_vol_multiplier": target_vol_multiplier,
                "gross_multiplier": gross_multiplier,
                "predicted_ann_vol": float(diag_row.get("predicted_ann_vol", np.nan)) if len(diag_row) else np.nan,
                "dynamic_speed": float(diag_row.get("dynamic_speed", np.nan)) if len(diag_row) else np.nan,
                "regime_binding": float(diag_row.get("regime_binding", 0.0)) if len(diag_row) else 0.0,
                "target_vol_binding": float(diag_row.get("target_vol_binding", 0.0)) if len(diag_row) else 0.0,
                "both_binding": float(diag_row.get("both_binding", 0.0)) if len(diag_row) else 0.0,
                "binding_source": binding_source,
                "self_gated_relief": float(diag_row.get("self_gated_relief", 0.0)) if len(diag_row) else 0.0,
                "final_self_gated_multiplier": self_gated_multiplier,
                "final_non_self_gated_multiplier": non_self_gated_multiplier,
                "overlay_penalty_mode": diag_row.get("overlay_penalty_mode", "none") if len(diag_row) else "none",
                "speed_mode": diag_row.get("speed_mode", "default") if len(diag_row) else "default",
            }
        )

        sleeve_row = sleeve_alloc.loc[date] if date in sleeve_alloc.index else pd.Series(dtype=float)
        sleeve_internal_bil_weight = 0.0
        self_gated_internal_bil_weight = 0.0
        self_gated_overlay_cut_total = 0.0
        self_gated_overlay_cut_risky = 0.0
        non_self_gated_overlay_cut_total = 0.0
        non_self_gated_overlay_cut_risky = 0.0
        for sleeve_name in [name for name in sleeve_row.index if not str(name).startswith("cash::")]:
            post_weight = float(sleeve_row.get(sleeve_name, 0.0) or 0.0)
            sleeve_positions_row = (
                version_sleeve_positions[sleeve_name].loc[date]
                if sleeve_name in version_sleeve_positions and date in version_sleeve_positions[sleeve_name].index
                else pd.Series(dtype=float)
            )
            internal_bil = float(sleeve_positions_row.get(ns5["cash_proxy"], 0.0) or 0.0)
            multiplier_used = self_gated_multiplier if sleeve_name in SELF_GATED_SLEEVES else non_self_gated_multiplier
            pre_overlay_weight = post_weight / multiplier_used if pd.notna(multiplier_used) and multiplier_used > 1e-9 else post_weight
            overlay_cut_total = max(0.0, pre_overlay_weight - post_weight)
            overlay_cut_risky = overlay_cut_total * max(0.0, 1.0 - internal_bil)
            sleeve_internal_bil_contrib = post_weight * internal_bil
            sleeve_internal_bil_weight += sleeve_internal_bil_contrib
            if sleeve_name in SELF_GATED_SLEEVES:
                self_gated_internal_bil_weight += sleeve_internal_bil_contrib
                self_gated_overlay_cut_total += overlay_cut_total
                self_gated_overlay_cut_risky += overlay_cut_risky
            else:
                non_self_gated_overlay_cut_total += overlay_cut_total
                non_self_gated_overlay_cut_risky += overlay_cut_risky
        stacked_defense_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
                "strong_neutral": float(
                    date in market_state_history.index
                    and market_state_history.loc[date, "market_state"] == "neutral_mixed"
                    and float(market_state_history.loc[date, "market_trend_positive"]) > 0.0
                    and float(market_state_history.loc[date, "breadth_sma_43"]) >= 0.55
                    and float(market_state_history.loc[date, "breadth_26w_mom"]) >= 0.50
                ),
                "bil_weight": cash_weight.loc[date],
                "overlay_cash_weight": overlay_cash.loc[date],
                "sleeve_bil_weight": sleeve_bil.loc[date],
                "sleeve_internal_bil_weight": sleeve_internal_bil_weight,
                "self_gated_internal_bil_weight": self_gated_internal_bil_weight,
                "self_gated_overlay_cut_total": self_gated_overlay_cut_total,
                "self_gated_overlay_cut_risky": self_gated_overlay_cut_risky,
                "non_self_gated_overlay_cut_total": non_self_gated_overlay_cut_total,
                "non_self_gated_overlay_cut_risky": non_self_gated_overlay_cut_risky,
                "regime_multiplier": regime_multiplier,
                "target_vol_multiplier": target_vol_multiplier,
                "gross_multiplier": gross_multiplier,
                "binding_source": binding_source,
            }
        )

        allocation_driver_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "offensive_weight": offensive_weight.loc[date],
                "defensive_weight": defensive_weight.loc[date],
                "cash_proxy_weight": cash_weight.loc[date],
                "bil_weight": cash_weight.loc[date],
                "spy_weight": weight_panel.loc[date].get("SPY", np.nan),
                "overlay_cash_weight": overlay_cash.loc[date],
                "sleeve_bil_weight": sleeve_bil.loc[date],
                "beta_overlay_spy_weight": beta_overlay_spy.loc[date],
                "beta_overlay_bil_weight": beta_overlay_bil.loc[date],
                "risk_state": ns5["regime_states"].loc[date, "risk_state"] if date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
            }
        )

    current_sleeve_alloc = sleeve_alloc.loc[latest_date] if latest_date in sleeve_alloc.index else pd.Series(dtype=float)
    for asset in [ns5["cash_proxy"], "SPY"]:
        overlay_value = current_sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", 0.0) if asset == ns5["cash_proxy"] else 0.0
        beta_overlay_value = beta_overlay_bil.loc[latest_date] if asset == ns5["cash_proxy"] else beta_overlay_spy.loc[latest_date]
        allocation_driver_breakdown_rows.append(
            {
                "version_name": version["version_name"],
                "horizon": "current",
                "asset": asset,
                "driver": "overlay_cash",
                "contribution": overlay_value,
            }
        )
        if abs(beta_overlay_value) > 1e-9:
            allocation_driver_breakdown_rows.append(
                {
                    "version_name": version["version_name"],
                    "horizon": "current",
                    "asset": asset,
                    "driver": "beta_overlay",
                    "contribution": beta_overlay_value,
                }
            )
        for sleeve_name in [name for name in current_sleeve_alloc.index if not str(name).startswith("cash::")]:
            sleeve_weight = current_sleeve_alloc.get(sleeve_name, 0.0)
            sleeve_position = version_sleeve_positions[sleeve_name].loc[latest_date].get(asset, 0.0) if sleeve_name in version_sleeve_positions and latest_date in version_sleeve_positions[sleeve_name].index else 0.0
            allocation_driver_breakdown_rows.append(
                {
                    "version_name": version["version_name"],
                    "horizon": "current",
                    "asset": asset,
                    "driver": sleeve_name,
                    "contribution": sleeve_weight * sleeve_position,
                }
            )

    state_conditioned_rows = sleeve_alloc.join(market_state_history[["market_state"]], how="left")
    for state_name, group in state_conditioned_rows.groupby("market_state"):
        if state_name is None or str(state_name) == "nan":
            continue
        sleeve_means = group.drop(columns=["market_state"], errors="ignore").mean()
        for sleeve_name, value in sleeve_means.items():
            state_conditioned_allocation_rows.append(
                {
                    "version_name": version["version_name"],
                    "method_name": version["method_name"],
                    "market_state": state_name,
                    "sleeve_name": sleeve_name,
                    "avg_weight": value,
                }
            )

    version_results[version["version_name"]] = {
        "weights": weight_panel,
        "sleeve_alloc": sleeve_alloc,
        "path": path,
        "diagnostics": diagnostics,
        "beta_overlay": beta_overlay_panel,
    }


candidate_strategy_returns = {
    "dual_momentum_topn": pd.read_csv(LAYER2A_DIR / "strategy_returns_dual_momentum_topn.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "cta_trend_long_only": pd.read_csv(LAYER2A_DIR / "strategy_returns_cta_trend_long_only.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "composite_regime_conditioned": pd.read_csv(LAYER2A_DIR / "strategy_returns_composite_regime_conditioned.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "taa_10m_sma": pd.read_csv(LAYER2A_DIR / "strategy_returns_taa_10m_sma.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    selective_strategy_name: selective_path["net_return"],
    strength_weighted_strategy_name: strength_weighted_path["net_return"],
    concentrated_strategy_name: concentrated_path["net_return"],
}
for strategy_name, strategy_returns in candidate_strategy_returns.items():
    aligned = pd.DataFrame({"return": strategy_returns}).join(market_state_history[["market_state"]], how="left").dropna()
    for state_name, group in aligned.groupby("market_state"):
        sample = group["return"].dropna()
        if sample.empty:
            continue
        metrics = ns5["summary_metrics"](sample, trials=max(len(candidate_strategy_returns), 2))
        sleeve_performance_by_state_rows.append(
            {
                "strategy_name": strategy_name,
                "market_state": state_name,
                **metrics,
            }
        )


benchmark_index = benchmark_market_returns.index.intersection(next(iter(version_results.values()))["path"].index)
target_windows = manual_windows(benchmark_index) + top_rally_windows(benchmark_market_returns.reindex(benchmark_index).dropna())

for version_name, payload in version_results.items():
    version_returns = payload["path"]["net_return"]
    weight_panel = payload["weights"]
    diagnostics = payload["diagnostics"]
    capture_row = version_capture_summary(version_name, version_returns, benchmark_market_returns, weight_panel, diagnostics, market_state_history)
    upside_capture_rows.append(capture_row)
    for window in target_windows:
        summary_row = summarize_window(window, version_name, version_returns, benchmark_market_returns, weight_panel, diagnostics, market_state_history)
        targeted_window_rows.append(summary_row)
        window_capture_rows.append(
            {
                "version_name": version_name,
                "window_name": window["window_name"],
                "window_type": window["window_type"],
                "capture_ratio": summary_row["capture_ratio"],
                "portfolio_return": summary_row["portfolio_return"],
                "benchmark_return": summary_row["benchmark_return"],
            }
        )
        if window["window_type"] in {"recovery", "rising", "auto_rally"}:
            rally_window_rows.append(summary_row)
        if window["window_type"] == "recovery":
            rerisk_lag_rows.append(rerisking_lag_summary(window, version_name, weight_panel, diagnostics))


upside_capture_df = pd.DataFrame(upside_capture_rows)
rally_window_df = pd.DataFrame(rally_window_rows)
targeted_window_df = pd.DataFrame(targeted_window_rows)
window_capture_df = pd.DataFrame(window_capture_rows)
rerisk_lag_df = pd.DataFrame(rerisk_lag_rows)
version_diagnostics_timeseries_df = pd.DataFrame(version_diagnostics_timeseries_rows)
stacked_defense_df = pd.DataFrame(stacked_defense_timeseries_rows)
off_def_cash_rallies_df = rally_window_df[
    [
        "version_name",
        "window_name",
        "window_type",
        "avg_offensive_weight",
        "avg_defensive_weight",
        "avg_cash_weight",
        "avg_bil_weight",
        "avg_spy_weight",
        "avg_regime_multiplier",
        "avg_target_vol_multiplier",
        "avg_dynamic_speed",
    ]
].copy()


version_df = pd.DataFrame(portfolio_version_rows).merge(upside_capture_df, on="version_name", how="left")


def rank_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.Series(series, dtype=float)
    if not higher_is_better:
        numeric = -numeric
    return numeric.rank(pct=True, method="average")


version_df["production_score"] = (
    0.22 * rank_score(version_df["sharpe"], True)
    + 0.16 * rank_score(version_df["calmar"], True)
    + 0.14 * rank_score(version_df["max_drawdown"].abs(), False)
    + 0.10 * rank_score(version_df["cvar_5"].abs(), False)
    + 0.12 * rank_score(version_df["upside_capture_positive_weeks"], True)
    + 0.10 * rank_score(version_df["recovery_week_capture"], True)
    + 0.08 * rank_score(version_df["avg_cash_weight"], False)
    + 0.08 * rank_score(version_df["avg_weekly_turnover"], False)
)

portfolio_version_rows = version_df.to_dict(orient="records")
upside_capture_df = upside_capture_df.merge(version_df[["version_name", "production_score"]], on="version_name", how="left")

if not version_diagnostics_timeseries_df.empty:
    version_diagnostics_state_summary_df = (
        version_diagnostics_timeseries_df.groupby(["version_name", "market_state"], dropna=False)[
            [
                "regime_multiplier",
                "target_vol_multiplier",
                "gross_multiplier",
                "dynamic_speed",
                "regime_binding",
                "target_vol_binding",
                "both_binding",
                "self_gated_relief",
                "final_self_gated_multiplier",
                "final_non_self_gated_multiplier",
            ]
        ]
        .mean()
        .reset_index()
    )
else:
    version_diagnostics_state_summary_df = pd.DataFrame()

if not stacked_defense_df.empty:
    stacked_defense_state_summary_df = (
        stacked_defense_df.groupby(["version_name", "market_state", "strong_neutral"], dropna=False)[
            [
                "bil_weight",
                "overlay_cash_weight",
                "sleeve_bil_weight",
                "sleeve_internal_bil_weight",
                "self_gated_internal_bil_weight",
                "self_gated_overlay_cut_total",
                "self_gated_overlay_cut_risky",
                "non_self_gated_overlay_cut_total",
                "non_self_gated_overlay_cut_risky",
                "regime_multiplier",
                "target_vol_multiplier",
                "gross_multiplier",
            ]
        ]
        .mean()
        .reset_index()
    )
else:
    stacked_defense_state_summary_df = pd.DataFrame()


upside_capture_df.to_csv(LAYER3_DIR / "upside_capture_analysis.csv", index=False)
rally_window_df.to_csv(LAYER3_DIR / "rally_window_attribution.csv", index=False)
off_def_cash_rallies_df.to_csv(LAYER3_DIR / "offensive_defensive_cash_during_rallies.csv", index=False)
targeted_window_df.to_csv(LAYER3_DIR / "targeted_window_summary.csv", index=False)
window_capture_df.to_csv(LAYER3_DIR / "upside_downside_capture_by_window.csv", index=False)
rerisk_lag_df.to_csv(LAYER3_DIR / "rerisking_lag_by_window.csv", index=False)
pd.DataFrame(sleeve_performance_by_state_rows).to_csv(LAYER2B_DIR / "sleeve_performance_by_state.csv", index=False)
pd.DataFrame(state_conditioned_allocation_rows).to_csv(LAYER3_DIR / "state_conditioned_allocation_summary.csv", index=False)
upside_capture_df.to_csv(LAYER3_DIR / "upside_capture_version_comparison.csv", index=False)

pd.DataFrame(sleeve_incremental_rows).to_csv(LAYER3_DIR / "sleeve_incremental_contribution.csv", index=False)
pd.DataFrame(sleeve_subset_rows).to_csv(LAYER3_DIR / "sleeve_subset_comparison.csv", index=False)
pd.DataFrame(portfolio_version_rows).to_csv(LAYER3_DIR / "portfolio_version_comparison.csv", index=False)
pd.concat(portfolio_version_regime_rows, ignore_index=True).to_csv(LAYER3_DIR / "portfolio_version_regime_split_summary.csv", index=False)
pd.concat(portfolio_version_subperiod_rows, ignore_index=True).to_csv(LAYER3_DIR / "portfolio_version_subperiod_summary.csv", index=False)
pd.DataFrame(allocation_driver_rows).to_csv(LAYER3_DIR / "allocation_driver_summary.csv", index=False)
pd.DataFrame(allocation_driver_breakdown_rows).to_csv(LAYER3_DIR / "allocation_driver_breakdown.csv", index=False)
pd.DataFrame(allocation_driver_timeseries_rows).to_csv(LAYER3_DIR / "allocation_driver_timeseries.csv", index=False)
version_diagnostics_timeseries_df.to_csv(LAYER3_DIR / "portfolio_version_diagnostics_timeseries.csv", index=False)
version_diagnostics_state_summary_df.to_csv(LAYER3_DIR / "portfolio_version_diagnostics_by_state.csv", index=False)
stacked_defense_df.to_csv(LAYER3_DIR / "stacked_defense_timeseries.csv", index=False)
stacked_defense_state_summary_df.to_csv(LAYER3_DIR / "stacked_defense_by_state.csv", index=False)

print("Saved improvement artifacts:")
for name in [
    "data/02_layer1_signals/signal_incremental_contribution.csv",
    "data/02_layer1_signals/signal_subset_comparison.csv",
    f"data/03_layer2a_strategy_logic/strategy_positions_{selective_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_returns_{selective_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_positions_{strength_weighted_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_returns_{strength_weighted_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_positions_{concentrated_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_returns_{concentrated_strategy_name}.csv",
    "data/04_layer2b_risk_regime_engine/market_state_history.csv",
    "data/04_layer2b_risk_regime_engine/sleeve_performance_by_state.csv",
    "data/05_layer3_portfolio_construction/sleeve_incremental_contribution.csv",
    "data/05_layer3_portfolio_construction/sleeve_subset_comparison.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_comparison.csv",
    "data/05_layer3_portfolio_construction/allocation_driver_summary.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_diagnostics_timeseries.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_diagnostics_by_state.csv",
    "data/05_layer3_portfolio_construction/stacked_defense_timeseries.csv",
    "data/05_layer3_portfolio_construction/stacked_defense_by_state.csv",
    "data/05_layer3_portfolio_construction/upside_capture_analysis.csv",
    "data/05_layer3_portfolio_construction/rally_window_attribution.csv",
    "data/05_layer3_portfolio_construction/targeted_window_summary.csv",
]:
    print(" -", name)
