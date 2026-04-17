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


def evaluate_signal_combo(
    signal_names: list[str],
    *,
    top_n: int | None = None,
    min_signal: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    signal_panels = {name: ns3["baseline_signal_panels"][name] for name in signal_names if name in ns3["baseline_signal_panels"]}
    composite_signal = ns3["combine_signal_panels"](
        signal_panels,
        weight_history=None,
        smoothing_weeks=ns3["COMPOSITE_SMOOTHING_WEEKS"],
    )
    chosen_top_n = top_n if top_n is not None else min(5, max(3, len(ns3["broad_risk_assets"]) // 3)) if ns3["broad_risk_assets"] else 1
    weights = ns3["build_top_n_long_only_weights"](
        composite_signal.reindex(columns=ns3["broad_risk_assets"]),
        top_n=chosen_top_n,
        min_signal=min_signal,
        defensive_asset=ns3["defensive_asset"],
        fill_to_defensive=True,
    )
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

    recent_stress = regime_states["risk_state"].eq("stressed").rolling(26, min_periods=1).max().fillna(0.0).astype(bool)
    avg_corr_risk_off_z = regime_score.get("avg_corr_risk_off_z", pd.Series(np.nan, index=regime_states.index))
    google_fear = regime_score.get("google_fear_z_tradable", pd.Series(np.nan, index=regime_states.index))
    risk_score = regime_score.get("risk_regime_score", pd.Series(np.nan, index=regime_states.index))

    state = pd.Series("neutral_mixed", index=regime_states.index, dtype=object)
    stressed_mask = regime_states["risk_state"].eq("stressed") | ((market_drawdown <= -0.18) & (breadth_sma_43 < 0.35))
    recovery_mask = (
        ~stressed_mask
        & recent_stress
        & market_trend_positive.fillna(False)
        & (breadth_sma_43 >= 0.45)
        & (breadth_26w_mom >= 0.45)
        & (breadth_change_4w >= 0.05)
    )
    calm_mask = (
        ~stressed_mask
        & regime_states["risk_state"].eq("calm")
        & market_trend_positive.fillna(False)
        & (breadth_sma_43 >= 0.60)
        & (breadth_26w_mom >= 0.55)
    )
    state.loc[stressed_mask] = "stressed_panic"
    state.loc[recovery_mask] = "recovery_rebound"
    state.loc[calm_mask] = "calm_trend"

    state_reason = pd.Series("mixed inputs", index=state.index, dtype=object)
    state_reason.loc[stressed_mask] = "stress state, weak breadth, or deep drawdown"
    state_reason.loc[recovery_mask] = "recent stress plus improving breadth and positive market trend"
    state_reason.loc[calm_mask] = "calm regime with strong trend breadth"

    out = pd.DataFrame(
        {
            "Date": regime_states.index,
            "market_state": state.values,
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
            "recent_stress_26w": recent_stress.reindex(regime_states.index).astype(float).values,
            "avg_corr_risk_off_z": avg_corr_risk_off_z.reindex(regime_states.index).values,
            "google_fear_z_tradable": google_fear.reindex(regime_states.index).values,
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
    adjusted = adjusted.join(market_state_history[["market_state", "market_state_reason", "breadth_sma_43", "breadth_26w_mom", "market_trend_positive"]], how="left")
    if adjusted.empty or "overlay_multiplier" not in adjusted.columns:
        return adjusted
    if overlay_variant == "baseline":
        return adjusted

    neutral_mask = adjusted["risk_state"].eq("neutral")
    stressed_mask = adjusted["risk_state"].eq("stressed")
    adjusted.loc[neutral_mask, "overlay_multiplier"] = adjusted.loc[neutral_mask, "overlay_multiplier"].clip(lower=0.80)
    adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(lower=0.40)

    if overlay_variant == "looser_neutral_stress":
        return adjusted

    recovery_mask = adjusted["market_state"].eq("recovery_rebound")
    calm_mask = adjusted["market_state"].eq("calm_trend")
    strong_neutral_mask = (
        adjusted["market_state"].eq("neutral_mixed")
        & adjusted["market_trend_positive"].fillna(0.0).gt(0.0)
        & adjusted["breadth_sma_43"].fillna(0.0).ge(0.55)
        & adjusted["breadth_26w_mom"].fillna(0.0).ge(0.50)
    )
    adjusted.loc[recovery_mask, "overlay_multiplier"] = adjusted.loc[recovery_mask, "overlay_multiplier"].clip(lower=0.92)
    adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
    adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
    return adjusted


def apply_state_conditioned_tilt(raw_weights: pd.Series, market_state: str | None, tilt_mode: str = "none") -> pd.Series:
    if tilt_mode == "none":
        return ns5["normalize_long_only"](raw_weights, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    tilted = pd.Series(raw_weights, dtype=float).copy()
    offensive_sleeves = [
        name
        for name in [
            "dual_momentum_topn",
            "cta_trend_long_only",
            "composite_selective_signals",
            "composite_selective_concentrated",
            "composite_equal_weight",
        ]
        if name in tilted.index
    ]
    defensive_sleeves = [name for name in ["composite_regime_conditioned", "taa_10m_sma"] if name in tilted.index]

    if market_state == "recovery_rebound":
        for name in offensive_sleeves:
            tilted.loc[name] *= 1.12
        for name in defensive_sleeves:
            tilted.loc[name] *= 0.90
    elif market_state == "calm_trend":
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
    return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])


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
) -> tuple[pd.Series, float, dict]:
    raw_weights = ns5["normalize_long_only"](raw_weights, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    dynamic_speed = sleeve_reallocation_speed
    if rerisk_speed is not None and market_state in {"recovery_rebound", "calm_trend"}:
        dynamic_speed = rerisk_speed
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
    regime_multiplier = float(regime_row.get("overlay_multiplier", 1.0)) if isinstance(regime_row, pd.Series) else 1.0
    gross_multiplier = float(min(1.0, regime_multiplier, target_vol_multiplier))
    risky_weights = blended * gross_multiplier
    cash_weight = max(0.0, 1.0 - risky_weights.sum())
    diagnostics = {
        "predicted_ann_vol": predicted_ann_vol,
        "target_vol_multiplier": target_vol_multiplier,
        "regime_multiplier": regime_multiplier,
        "gross_multiplier": gross_multiplier,
        "cash_weight": cash_weight,
        "dynamic_speed": dynamic_speed,
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
    market_state_history: pd.DataFrame | None = None,
    sleeve_return_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    subset = [name for name in subset_sleeves if name in sleeve_return_panel.columns]
    if not subset:
        raise ValueError(f"No valid sleeves for subset {subset_name}")
    method_spec = next(spec for spec in ns5["method_specs"] if spec["method_name"] == method_name)
    variant_regime_states = build_variant_regime_states(ns5["regime_states"], market_state_history, overlay_variant)
    conviction_inputs = {
        key: value.reindex(columns=[name for name in subset if name in value.columns])
        for key, value in ns5["conviction_inputs"].items()
    }
    forward_weekly_returns = ns5["next_week_returns"].reindex(columns=ns5["weekly_prices"].columns)
    all_dates = sleeve_return_panel.index
    rebalance_dates = ns5["rebalance_mask"](all_dates, ns5["REBALANCE_FREQUENCY"])
    current_risky_alloc = pd.Series(0.0, index=subset, dtype=float)
    current_cash_weight = 1.0
    sleeve_alloc_rows: list[pd.Series] = []
    etf_weight_rows: list[pd.Series] = []
    diag_rows: list[dict] = []

    for date in all_dates:
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

                        market_state = market_state_history.loc[date, "market_state"] if market_state_history is not None and date in market_state_history.index else None
                        raw = apply_state_conditioned_tilt(raw, market_state, tilt_mode=state_tilt)
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
                        )
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
                                "market_state": market_state,
                                **overlay_diag,
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
        etf_row.name = date
        etf_weight_rows.append(etf_row)

    sleeve_alloc = pd.DataFrame(sleeve_alloc_rows).sort_index().fillna(0.0)
    etf_weights = pd.DataFrame(etf_weight_rows).sort_index().fillna(0.0)
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
    return sleeve_alloc, etf_weights, path, diagnostics, metrics


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

    recovery_mask = joined["market_state"].eq("recovery_rebound")
    calm_mask = joined["market_state"].eq("calm_trend")
    stressed_mask = joined["market_state"].eq("stressed_panic")

    return {
        "version_name": version_name,
        "upside_capture_positive_weeks": upside_capture,
        "downside_capture_negative_weeks": downside_capture,
        "recovery_week_capture": joined.loc[recovery_mask, "portfolio"].sum() / joined.loc[recovery_mask, "benchmark"].sum() if recovery_mask.any() and joined.loc[recovery_mask, "benchmark"].sum() != 0 else np.nan,
        "calm_week_capture": joined.loc[calm_mask, "portfolio"].sum() / joined.loc[calm_mask, "benchmark"].sum() if calm_mask.any() and joined.loc[calm_mask, "benchmark"].sum() != 0 else np.nan,
        "stress_downside_capture": joined.loc[stressed_mask, "portfolio"].sum() / joined.loc[stressed_mask, "benchmark"].sum() if stressed_mask.any() and joined.loc[stressed_mask, "benchmark"].sum() != 0 else np.nan,
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
        "avg_market_state_recovery": safe_mean(market_state_slice["market_state"].eq("recovery_rebound").astype(float)),
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
selective_weights, selective_path, selective_metrics = evaluate_signal_combo(selective_signal_names)
concentrated_weights, concentrated_path, concentrated_metrics = evaluate_signal_combo(selective_signal_names, top_n=3, min_signal=0.05)
selective_strategy_name = "composite_selective_signals"
concentrated_strategy_name = "composite_selective_concentrated"

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


strategy_lookup = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
strategy_lookup = strategy_lookup.set_index("strategy_name") if not strategy_lookup.empty else pd.DataFrame().set_index(pd.Index([], name="strategy_name"))

base_sleeve_return_panel = ns5["sleeve_return_panel"].copy()
base_sleeve_positions = dict(ns5["sleeve_positions"])
base_sleeve_return_panel[selective_strategy_name] = selective_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[selective_strategy_name] = selective_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[concentrated_strategy_name] = concentrated_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[concentrated_strategy_name] = concentrated_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)

baseline_subset = list(ns5["sleeve_return_panel"].columns)
drop_breadth_subset = [name for name in baseline_subset if name != "composite_breadth_filtered"]
replace_equal_subset = ["dual_momentum_topn", "cta_trend_long_only", selective_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
replace_equal_concentrated_subset = ["dual_momentum_topn", "cta_trend_long_only", concentrated_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
improved_subset = replace_equal_subset

subset_specs = {
    "baseline_current": baseline_subset,
    "drop_breadth": drop_breadth_subset,
    "drop_regime": [name for name in baseline_subset if name != "composite_regime_conditioned"],
    "replace_equal_with_selective": replace_equal_subset,
    "replace_equal_with_concentrated": replace_equal_concentrated_subset,
    "add_selective_drop_breadth": drop_breadth_subset + [selective_strategy_name],
    "add_concentrated_drop_breadth": drop_breadth_subset + [concentrated_strategy_name],
}


portfolio_version_rows: list[dict] = []
portfolio_version_regime_rows: list[pd.DataFrame] = []
portfolio_version_subperiod_rows: list[pd.DataFrame] = []
allocation_driver_rows: list[dict] = []
allocation_driver_breakdown_rows: list[dict] = []
allocation_driver_timeseries_rows: list[dict] = []
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
    _, baseline_weights, _, baseline_diag, baseline_metrics = run_subset_custom(
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
        _, weight_panel, path, diagnostics, metrics = run_subset_custom(
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
]


benchmark_market_returns = load_benchmark_returns("strategy_returns_baseline_market_proxy_buy_hold.csv")
benchmark_6040_returns = load_benchmark_returns("strategy_returns_baseline_60_40_proxy.csv")

version_results: dict[str, dict] = {}
version_baselines: dict[str, dict] = {}

for version in version_specs:
    sleeve_alloc, weight_panel, path, diagnostics, metrics = run_subset_custom(
        version["method_name"],
        version["subset_name"],
        version["subset_sleeves"],
        overlay_variant=version["overlay_variant"],
        speed=version["sleeve_reallocation_speed"],
        rerisk_speed=version["rerisk_speed"],
        state_tilt=version["state_tilt"],
        target_vol_ceil=version["target_vol_ceil"],
        market_state_history=market_state_history,
        sleeve_return_panel=base_sleeve_return_panel,
        sleeve_positions=base_sleeve_positions,
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
        **metrics,
        "avg_bil_weight": avg_bil,
        "avg_spy_weight": avg_spy,
        "avg_cash_weight": avg_cash,
        "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_dynamic_speed": diagnostics["dynamic_speed"].mean() if not diagnostics.empty else np.nan,
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
            "current_overlay_cash_weight": overlay_cash.loc[latest_date],
            "current_sleeve_bil_weight": sleeve_bil.loc[latest_date],
            "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_dynamic_speed": diagnostics["dynamic_speed"].mean() if not diagnostics.empty else np.nan,
            "calm_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("calm").mean(),
            "neutral_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("neutral").mean(),
            "stressed_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("stressed").mean(),
            "recovery_market_state_frequency": market_state_history["market_state"].eq("recovery_rebound").mean(),
            "calm_market_state_frequency": market_state_history["market_state"].eq("calm_trend").mean(),
        }
    )

    for date in weight_panel.index:
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
                "risk_state": ns5["regime_states"].loc[date, "risk_state"] if date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
            }
        )

    current_sleeve_alloc = sleeve_alloc.loc[latest_date] if latest_date in sleeve_alloc.index else pd.Series(dtype=float)
    for asset in [ns5["cash_proxy"], "SPY"]:
        overlay_value = current_sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", 0.0) if asset == ns5["cash_proxy"] else 0.0
        allocation_driver_breakdown_rows.append(
            {
                "version_name": version["version_name"],
                "horizon": "current",
                "asset": asset,
                "driver": "overlay_cash",
                "contribution": overlay_value,
            }
        )
        for sleeve_name in [name for name in current_sleeve_alloc.index if not str(name).startswith("cash::")]:
            sleeve_weight = current_sleeve_alloc.get(sleeve_name, 0.0)
            sleeve_position = base_sleeve_positions[sleeve_name].loc[latest_date].get(asset, 0.0) if latest_date in base_sleeve_positions[sleeve_name].index else 0.0
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
    }


candidate_strategy_returns = {
    "dual_momentum_topn": pd.read_csv(LAYER2A_DIR / "strategy_returns_dual_momentum_topn.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "cta_trend_long_only": pd.read_csv(LAYER2A_DIR / "strategy_returns_cta_trend_long_only.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "composite_regime_conditioned": pd.read_csv(LAYER2A_DIR / "strategy_returns_composite_regime_conditioned.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "taa_10m_sma": pd.read_csv(LAYER2A_DIR / "strategy_returns_taa_10m_sma.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    selective_strategy_name: selective_path["net_return"],
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

print("Saved improvement artifacts:")
for name in [
    "data/02_layer1_signals/signal_incremental_contribution.csv",
    "data/02_layer1_signals/signal_subset_comparison.csv",
    f"data/03_layer2a_strategy_logic/strategy_positions_{selective_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_returns_{selective_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_positions_{concentrated_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_returns_{concentrated_strategy_name}.csv",
    "data/04_layer2b_risk_regime_engine/market_state_history.csv",
    "data/04_layer2b_risk_regime_engine/sleeve_performance_by_state.csv",
    "data/05_layer3_portfolio_construction/sleeve_incremental_contribution.csv",
    "data/05_layer3_portfolio_construction/sleeve_subset_comparison.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_comparison.csv",
    "data/05_layer3_portfolio_construction/allocation_driver_summary.csv",
    "data/05_layer3_portfolio_construction/upside_capture_analysis.csv",
    "data/05_layer3_portfolio_construction/rally_window_attribution.csv",
    "data/05_layer3_portfolio_construction/targeted_window_summary.csv",
]:
    print(" -", name)
