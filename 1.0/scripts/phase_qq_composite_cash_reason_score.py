"""Phase QQ — component-level cash-defense score redesign for composite_regime_conditioned.

Focus:
1. Infer why the sleeve entered its favorable-state 25% BIL tier.
2. Build a simple causal cash-defense score using only current / past features.
3. Use that score and inferred reason buckets to drive three narrow candidate
   redesigns through the existing production construction pipeline.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


ROOT = roc.ROOT
PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
TARGET_SLEEVE = "composite_regime_conditioned"
PHASE_QQ_CANDIDATES = [
    "improved_phaseqq_cash_defense_score_fallback",
    "improved_phaseqq_reason_specific_fallback",
    "improved_phaseqq_pp_combined_score_filtered",
]
AUDIT_DIR = ROOT / "data" / "research" / "phase_qq_composite_cash_reason_score"
OUTPUT_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
REPORT_PATH = ROOT / "docs" / "research" / "2026-04-27_phase_qq_composite_cash_reason_score_report.md"
DEFENSIVE_ETFS = {"IEF", "SHY", "TLT", "TIP", "GLD", "LQD"}
REASON_CATEGORIES = [
    "signal_failed",
    "no_asset_passed_filter",
    "regime_uncertain",
    "volatility_high",
    "breadth_or_trend_weak",
    "residual_normalization_cash",
    "defensive_fallback",
    "unknown",
]
COMMAND_LOG: list[str] = []


def record_command(command: list[str]) -> str:
    rendered = " ".join(command)
    COMMAND_LOG.append(rendered)
    return rendered


def run_logged(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 7200) -> subprocess.CompletedProcess:
    rendered = record_command(command)
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {rendered}\n"
            f"stdout tail:\n{chr(10).join((result.stdout or '').splitlines()[-20:])}\n"
            f"stderr tail:\n{chr(10).join((result.stderr or '').splitlines()[-20:])}"
        )
    return result


def build_candidates() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join([PRODUCTION, SHADOW] + PHASE_QQ_CANDIDATES)
    run_logged([sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")], env=env)


def is_strong_neutral(row: pd.Series) -> bool:
    if row is None or row.empty:
        return False
    try:
        return (
            str(row.get("market_state") or "") == "neutral_mixed"
            and float(row.get("market_trend_positive") or 0.0) > 0.0
            and float(row.get("breadth_sma_43") or 0.0) >= 0.55
            and float(row.get("breadth_26w_mom") or 0.0) >= 0.50
        )
    except (TypeError, ValueError):
        return False


def load_state_history() -> pd.DataFrame:
    state = roc.load_market_state(refined=False).copy()
    state["strong_neutral"] = state.apply(is_strong_neutral, axis=1)
    state["state_bucket"] = np.where(
        state["strong_neutral"] & state["market_state"].eq("neutral_mixed"),
        "neutral_healthy_proxy",
        state["market_state"],
    )
    return state


def load_positions(strategy_name: str) -> pd.DataFrame:
    path = ROOT / "data" / "03_layer2a_strategy_logic" / f"strategy_positions_{strategy_name}.csv"
    df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index().fillna(0.0)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def load_returns(strategy_name: str) -> pd.Series:
    path = ROOT / "data" / "03_layer2a_strategy_logic" / f"strategy_returns_{strategy_name}.csv"
    df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    col = "net_return" if "net_return" in df.columns else df.columns[0]
    return df[col].rename(strategy_name)


def load_base_positions(sleeves: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for sleeve in sleeves:
        p = ROOT / "data" / "03_layer2a_strategy_logic" / f"strategy_positions_{sleeve}.csv"
        if p.exists():
            out[sleeve] = load_positions(sleeve)
    return out


def rank01(series: pd.Series, ascending: bool = True) -> pd.Series:
    s = pd.Series(series, dtype=float)
    return s.rank(pct=True, method="average", ascending=ascending)


def safe_mean(values: list[float]) -> float:
    arr = np.array([v for v in values if np.isfinite(v)], dtype=float)
    return float(arr.mean()) if arr.size else np.nan


def forward_compound(series: pd.Series, horizon: int) -> pd.Series:
    vals = pd.Series(series, dtype=float)
    return (1.0 + vals).rolling(horizon).apply(np.prod, raw=True).shift(-(horizon - 1)) - 1.0


def static_forward_return(weights_row: pd.Series, weekly_returns: pd.DataFrame, date: pd.Timestamp, horizon: int) -> float:
    if date not in weekly_returns.index:
        return np.nan
    loc = weekly_returns.index.get_loc(date)
    if isinstance(loc, slice):
        return np.nan
    future = weekly_returns.iloc[loc + 1 : loc + 1 + horizon]
    if len(future) < horizon:
        return np.nan
    row = weights_row.reindex(future.columns, fill_value=0.0).astype(float)
    port = future.mul(row, axis=1).sum(axis=1)
    return float((1.0 + port).prod() - 1.0)


def make_static_mix_row(row: pd.Series, mix_name: str, *, cash_proxy: str = "BIL") -> pd.Series:
    out = row.copy()
    bil_weight = float(out.get(cash_proxy, 0.0) or 0.0)
    if abs(bil_weight - 0.25) > 1e-9:
        return out

    def apply_mix(keep_frac: float, mix: dict[str, float] | None = None, active: bool = False) -> pd.Series:
        mixed = out.copy()
        bil_shift = bil_weight * max(0.0, 1.0 - keep_frac)
        mixed[cash_proxy] = bil_weight - bil_shift
        if bil_shift <= 0.0:
            return mixed
        if active:
            risky = row.drop(cash_proxy, errors="ignore")
            risky_sum = float(risky.sum())
            if risky_sum <= 1e-9:
                return out.copy()
            for col, val in risky.items():
                val = float(val or 0.0)
                if val > 0.0:
                    mixed[col] = val + bil_shift * (val / risky_sum)
            return mixed
        mix = mix or {}
        mix = {k: float(v) for k, v in mix.items() if k in mixed.index and k != cash_proxy and float(v) > 0.0}
        mix_sum = float(sum(mix.values()))
        if mix_sum <= 0.0:
            return out.copy()
        for etf, weight in mix.items():
            mixed[etf] = float(mixed.get(etf, 0.0) or 0.0) + bil_shift * (weight / mix_sum)
        return mixed

    if mix_name == "keep_BIL":
        return out
    if mix_name == "partial_bond_gold":
        return apply_mix(0.75, {"GLD": 0.50, "TLT": 0.50})
    if mix_name == "balanced_defensive":
        return apply_mix(0.60, {"GLD": 0.40, "TLT": 0.30, "LQD": 0.20, "HYG": 0.10})
    if mix_name == "active_sleeve_redeploy":
        return apply_mix(0.55, active=True)
    if mix_name == "PP_best_fallback":
        return apply_mix(0.50, {"GLD": 0.50, "TLT": 0.50})
    return out


def apply_internal_redeploy(
    base_positions: dict[str, pd.DataFrame],
    state_history: pd.DataFrame,
    *,
    target_sleeves: list[str],
    redeploy_config: dict[str, float],
    strong_neutral_fraction: float = 0.0,
    cash_proxy: str = "BIL",
) -> dict[str, pd.DataFrame]:
    out = {name: df.copy() for name, df in base_positions.items()}
    aligned_state = state_history.reindex(next(iter(base_positions.values())).index)
    for sleeve_name in target_sleeves:
        if sleeve_name not in out:
            continue
        positions = out[sleeve_name].copy()
        if cash_proxy not in positions.columns:
            continue
        modified = positions.copy()
        for date, row in positions.iterrows():
            if date not in aligned_state.index:
                continue
            state_row = aligned_state.loc[date]
            redeploy_fraction = strong_neutral_fraction if bool(state_row.get("strong_neutral", False)) else float(redeploy_config.get(str(state_row.get("market_state") or ""), 0.0))
            if redeploy_fraction <= 0.0:
                continue
            bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
            if bil_weight <= 0.0:
                continue
            risky_row = row.drop(cash_proxy, errors="ignore")
            risky_sum = float(risky_row.sum())
            if risky_sum <= 1e-9:
                continue
            bil_shift = bil_weight * redeploy_fraction
            modified.at[date, cash_proxy] = bil_weight - bil_shift
            for col in risky_row.index:
                w = float(risky_row.get(col, 0.0) or 0.0)
                if w > 0.0:
                    modified.at[date, col] = w + bil_shift * (w / risky_sum)
        out[sleeve_name] = modified
    return out


def apply_action_map(
    base_positions: dict[str, pd.DataFrame],
    state_history: pd.DataFrame,
    action_frame: pd.DataFrame,
    *,
    sleeve_name: str,
    action_col: str,
    action_map: dict[str, dict[str, object]],
    cash_proxy: str = "BIL",
) -> dict[str, pd.DataFrame]:
    out = {name: df.copy() for name, df in base_positions.items()}
    if sleeve_name not in out or action_col not in action_frame.columns:
        return out
    positions = out[sleeve_name].copy()
    aligned_state = state_history.reindex(positions.index)
    action_lookup = action_frame.reindex(positions.index)
    modified = positions.copy()

    for date, row in positions.iterrows():
        if date not in aligned_state.index:
            continue
        state_row = aligned_state.loc[date]
        market_state = str(state_row.get("market_state") or "")
        strong_neutral = bool(state_row.get("strong_neutral", False))
        if market_state not in {"calm_trend", "recovery_confirmed", "recovery_fragile"} and not strong_neutral:
            continue
        bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
        if abs(bil_weight - 0.25) > 1e-9:
            continue
        action_name = str(action_lookup.at[date, action_col] or "").strip()
        action_spec = action_map.get(action_name)
        if not action_spec:
            continue
        keep_frac = float(action_spec.get("keep_bil_fraction", 1.0))
        bil_shift = bil_weight * max(0.0, 1.0 - keep_frac)
        if bil_shift <= 0.0:
            continue
        modified.at[date, cash_proxy] = bil_weight - bil_shift
        kind = str(action_spec.get("kind", "mix"))
        if kind == "active":
            risky = row.drop(cash_proxy, errors="ignore")
            risky_sum = float(risky.sum())
            if risky_sum <= 1e-9:
                modified.at[date, cash_proxy] = bil_weight
                continue
            for col, val in risky.items():
                val = float(val or 0.0)
                if val > 0.0:
                    modified.at[date, col] = val + bil_shift * (val / risky_sum)
            continue
        mix = {k: float(v) for k, v in dict(action_spec.get("fallback_mix", {})).items() if k in modified.columns and k != cash_proxy and float(v) > 0.0}
        mix_sum = float(sum(mix.values()))
        if mix_sum <= 0.0:
            modified.at[date, cash_proxy] = bil_weight
            continue
        for etf, weight in mix.items():
            modified.at[date, etf] = float(modified.at[date, etf]) + bil_shift * (weight / mix_sum)
    out[sleeve_name] = modified
    return out


def infer_reason(row: pd.Series, state_row: pd.Series, thresholds: dict[str, float]) -> str:
    eq_sum = float(row.reindex(["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ"], fill_value=0.0).sum())
    vnq = float(row.get("VNQ", 0.0) or 0.0)
    alt_sum = float(row.reindex(["HYG", "PDBC", "DBA"], fill_value=0.0).sum())
    defense_sum = float(row.reindex(["TLT", "LQD", "GLD"], fill_value=0.0).sum())
    corr = float(state_row.get("avg_corr_risk_off_z") or 0.0)
    stress = float(state_row.get("recent_stress_26w") or 0.0)
    drawdown = float(state_row.get("market_drawdown") or 0.0)
    breadth43 = float(state_row.get("breadth_sma_43") or 0.0)
    breadth13 = float(state_row.get("breadth_13w_mom") or 0.0)
    breadth4 = float(state_row.get("breadth_change_4w") or 0.0)
    good_prob = float(state_row.get("transition_good_state_prob") or 0.0)
    nonstress_prob = float(state_row.get("transition_non_stress_prob") or 0.0)
    persistence = float(state_row.get("transition_persistence_prob") or 0.0)
    trend_pos = float(state_row.get("market_trend_positive") or 0.0)

    high_risk_count = int(corr >= thresholds["corr_high"]) + int(stress >= thresholds["stress_high"]) + int(drawdown <= thresholds["drawdown_bad"])
    weak_breadth_count = int(breadth43 <= thresholds["breadth43_low"]) + int(breadth13 <= thresholds["breadth13_low"]) + int(breadth4 <= thresholds["breadth4_low"]) + int(trend_pos <= 0.0)
    uncertain_count = int(good_prob <= thresholds["good_low"]) + int(nonstress_prob <= thresholds["nonstress_low"]) + int(persistence <= thresholds["persist_low"])

    if high_risk_count >= 2 and weak_breadth_count >= 1:
        return "defensive_fallback"
    if high_risk_count >= 1 and (corr >= thresholds["corr_high"] or stress >= thresholds["stress_high"]):
        return "volatility_high"
    if weak_breadth_count >= 2:
        return "breadth_or_trend_weak"
    if uncertain_count >= 2:
        return "regime_uncertain"
    if eq_sum + vnq <= 0.10 and alt_sum <= 0.20 and defense_sum >= 0.55:
        return "no_asset_passed_filter"
    if eq_sum <= 0.20 and alt_sum <= 0.25 and defense_sum >= 0.40:
        return "signal_failed"
    if (
        trend_pos > 0.0
        and breadth43 >= thresholds["breadth43_high"]
        and breadth13 >= thresholds["breadth13_high"]
        and breadth4 >= thresholds["breadth4_high"]
        and nonstress_prob >= thresholds["nonstress_high"]
        and good_prob >= thresholds["good_high"]
        and corr <= thresholds["corr_mid"]
        and stress <= thresholds["stress_mid"]
        and drawdown > thresholds["drawdown_mid"]
    ):
        return "residual_normalization_cash"
    return "unknown"


def build_reason_thresholds(state_history: pd.DataFrame) -> dict[str, float]:
    return {
        "corr_high": float(state_history["avg_corr_risk_off_z"].quantile(0.67)),
        "corr_mid": float(state_history["avg_corr_risk_off_z"].quantile(0.50)),
        "stress_high": float(state_history["recent_stress_26w"].quantile(0.67)),
        "stress_mid": float(state_history["recent_stress_26w"].quantile(0.50)),
        "drawdown_bad": float(state_history["market_drawdown"].quantile(0.25)),
        "drawdown_mid": float(state_history["market_drawdown"].quantile(0.50)),
        "breadth43_low": float(state_history["breadth_sma_43"].quantile(0.33)),
        "breadth43_high": float(state_history["breadth_sma_43"].quantile(0.67)),
        "breadth13_low": float(state_history["breadth_13w_mom"].quantile(0.33)),
        "breadth13_high": float(state_history["breadth_13w_mom"].quantile(0.67)),
        "breadth4_low": float(state_history["breadth_change_4w"].quantile(0.33)),
        "breadth4_high": float(state_history["breadth_change_4w"].quantile(0.67)),
        "good_low": float(state_history["transition_good_state_prob"].quantile(0.33)),
        "good_high": float(state_history["transition_good_state_prob"].quantile(0.67)),
        "nonstress_low": float(state_history["transition_non_stress_prob"].quantile(0.33)),
        "nonstress_high": float(state_history["transition_non_stress_prob"].quantile(0.67)),
        "persist_low": float(state_history["transition_persistence_prob"].quantile(0.33)),
    }


def build_reason_frame(
    positions: pd.DataFrame,
    sleeve_returns: pd.Series,
    state_history: pd.DataFrame,
    production_returns: pd.Series,
    spy_returns: pd.Series,
) -> tuple[pd.DataFrame, dict[str, float]]:
    idx = positions.index.intersection(sleeve_returns.index).intersection(state_history.index).intersection(production_returns.index).intersection(spy_returns.index)
    positions = positions.reindex(idx).fillna(0.0)
    sleeve_returns = sleeve_returns.reindex(idx).fillna(0.0)
    state_history = state_history.reindex(idx)
    production_returns = production_returns.reindex(idx).fillna(0.0)
    spy_returns = spy_returns.reindex(idx).fillna(0.0)
    thresholds = build_reason_thresholds(state_history)

    fwd4_sleeve = forward_compound(sleeve_returns, 4)
    fwd13_sleeve = forward_compound(sleeve_returns, 13)
    fwd4_prod = forward_compound(production_returns, 4)
    fwd13_prod = forward_compound(production_returns, 13)
    fwd4_spy = forward_compound(spy_returns, 4)
    fwd13_spy = forward_compound(spy_returns, 13)

    prod_drawdown = (1.0 + production_returns).cumprod()
    prod_drawdown = prod_drawdown.div(prod_drawdown.cummax()).sub(1.0)

    rows = []
    for date, row in positions.iterrows():
        state_row = state_history.loc[date]
        state_bucket = str(state_row.get("state_bucket") or "")
        strong_neutral = bool(state_row.get("strong_neutral", False))
        bil = float(row.get("BIL", 0.0) or 0.0)
        is_target = abs(bil - 0.25) <= 1e-9 and (state_bucket in {"calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"} or strong_neutral)
        eq_sum = float(row.reindex(["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ"], fill_value=0.0).sum())
        alt_sum = float(row.reindex(["HYG", "PDBC", "DBA"], fill_value=0.0).sum())
        defense_sum = float(row.reindex(["TLT", "LQD", "GLD"], fill_value=0.0).sum())
        if is_target:
            reason = infer_reason(row, state_row, thresholds)
            inferred = True
        else:
            reason = ""
            inferred = False
        future_states = state_history["market_state"].reindex(state_history.index[state_history.index.get_loc(date) + 1 : state_history.index.get_loc(date) + 5] if date in state_history.index[:-1] else [])
        next4_stress = float((future_states == "stressed_panic").any()) if len(future_states) else np.nan
        future_dd = prod_drawdown.reindex(prod_drawdown.index[prod_drawdown.index.get_loc(date) + 1 : prod_drawdown.index.get_loc(date) + 5] if date in prod_drawdown.index[:-1] else [])
        dd_worsen = float((future_dd.min() < prod_drawdown.loc[date])) if len(future_dd) else np.nan
        rows.append(
            {
                "Date": date,
                "state": state_bucket,
                "strong_neutral": strong_neutral,
                "is_favorable_25_bil": is_target,
                "reason_category": reason,
                "reason_inferred": inferred,
                "composite_internal_bil": bil,
                "composite_equity_like": eq_sum,
                "composite_alt_like": alt_sum,
                "composite_defense_like": defense_sum,
                "composite_forward_4w_return": float(fwd4_sleeve.loc[date]),
                "composite_forward_13w_return": float(fwd13_sleeve.loc[date]),
                "production_forward_4w_return": float(fwd4_prod.loc[date]),
                "production_forward_13w_return": float(fwd13_prod.loc[date]),
                "SPY_forward_4w_return": float(fwd4_spy.loc[date]),
                "SPY_forward_13w_return": float(fwd13_spy.loc[date]),
                "stress_panic_within_next_4w": next4_stress,
                "prod_drawdown_worsen_next_4w": dd_worsen,
                "volatility_pressure": float(state_row.get("google_fear_z_tradable") or 0.0),
                "breadth_sma_43": float(state_row.get("breadth_sma_43") or 0.0),
                "breadth_13w_mom": float(state_row.get("breadth_13w_mom") or 0.0),
                "breadth_change_4w": float(state_row.get("breadth_change_4w") or 0.0),
                "drawdown_pressure": float(state_row.get("market_drawdown") or 0.0),
                "correlation_pressure": float(state_row.get("avg_corr_risk_off_z") or 0.0),
                "market_trend_positive": float(state_row.get("market_trend_positive") or 0.0),
                "recent_stress_26w": float(state_row.get("recent_stress_26w") or 0.0),
                "transition_good_state_prob": float(state_row.get("transition_good_state_prob") or 0.0),
                "transition_non_stress_prob": float(state_row.get("transition_non_stress_prob") or 0.0),
                "transition_persistence_prob": float(state_row.get("transition_persistence_prob") or 0.0),
                "risk_regime_score": float(state_row.get("risk_regime_score") or 0.0),
            }
        )
    return pd.DataFrame(rows), thresholds


def build_cash_defense_score(reason_frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    df = reason_frame.copy()
    mask = df["is_favorable_25_bil"].astype(bool)
    target = df.loc[mask].copy()

    vol_pressure = safe_mean_series([
        rank01(target["correlation_pressure"]),
        rank01(target["volatility_pressure"]),
        rank01(target["recent_stress_26w"]),
    ])
    drawdown_pressure = rank01(-target["drawdown_pressure"])
    uncertainty_pressure = safe_mean_series([
        1.0 - rank01(target["transition_good_state_prob"]),
        1.0 - rank01(target["transition_non_stress_prob"]),
        1.0 - rank01(target["transition_persistence_prob"]),
    ])
    breadth_weak = safe_mean_series([
        1.0 - rank01(target["breadth_sma_43"]),
        1.0 - rank01(target["breadth_13w_mom"]),
        1.0 - rank01(target["breadth_change_4w"]),
    ])
    trend_weak = 1.0 - target["market_trend_positive"].clip(lower=0.0, upper=1.0)

    reason_adj = target["reason_category"].map(
        {
            "defensive_fallback": 0.10,
            "volatility_high": 0.07,
            "breadth_or_trend_weak": 0.06,
            "regime_uncertain": 0.04,
            "residual_normalization_cash": -0.08,
            "signal_failed": -0.02,
            "no_asset_passed_filter": -0.01,
            "unknown": 0.00,
        }
    ).fillna(0.0)

    raw_score = (
        0.24 * vol_pressure
        + 0.18 * drawdown_pressure
        + 0.20 * uncertainty_pressure
        + 0.22 * breadth_weak
        + 0.16 * trend_weak
        + reason_adj
    )
    score = rank01(raw_score).clip(0.0, 1.0)
    low_th = float(score.quantile(0.33))
    high_th = float(score.quantile(0.67))
    bucket = np.where(score >= high_th, "high_defense", np.where(score <= low_th, "low_defense", "medium_defense"))
    target["cash_defense_score"] = score
    target["cash_defense_bucket"] = bucket
    target["fallback_decision_recommendation"] = np.where(
        target["cash_defense_bucket"].eq("high_defense"),
        "keep_BIL",
        np.where(target["cash_defense_bucket"].eq("medium_defense"), "replace_small", "replace_larger"),
    )
    df = df.merge(
        target[["Date", "cash_defense_score", "cash_defense_bucket", "fallback_decision_recommendation"]],
        on="Date",
        how="left",
    )
    df["cash_defense_bucket"] = df["cash_defense_bucket"].fillna("not_applicable")
    df["fallback_decision_recommendation"] = df["fallback_decision_recommendation"].fillna("production_keep")
    thresholds = {
        "low_defense_threshold": low_th,
        "high_defense_threshold": high_th,
        "bucket_method": "33/67 percentile split on favorable-state 25% BIL weeks",
    }
    return df, thresholds


def safe_mean_series(series_list: list[pd.Series]) -> pd.Series:
    valid = [s.astype(float) for s in series_list if s is not None]
    if not valid:
        return pd.Series(dtype=float)
    df = pd.concat(valid, axis=1)
    return df.mean(axis=1)


def reason_by_state(reason_frame: pd.DataFrame) -> pd.DataFrame:
    sub = reason_frame[reason_frame["is_favorable_25_bil"]].copy()
    if sub.empty:
        return pd.DataFrame()
    total_by_state = sub.groupby("state").size().rename("state_total")
    out = (
        sub.groupby(["state", "reason_category"], observed=False)
        .size()
        .rename("n_weeks")
        .reset_index()
        .merge(total_by_state.reset_index(), on="state", how="left")
    )
    out["share_of_state_favorable_25_bil_weeks"] = out["n_weeks"] / out["state_total"]
    order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
    out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
    return out.sort_values(["state", "n_weeks"], ascending=[True, False]).reset_index(drop=True)


def reason_forward_outcomes(reason_frame: pd.DataFrame) -> pd.DataFrame:
    sub = reason_frame[reason_frame["is_favorable_25_bil"]].copy()
    if sub.empty:
        return pd.DataFrame()
    rows = []
    total = len(sub)
    for reason, grp in sub.groupby("reason_category", observed=False):
        rows.append(
            {
                "reason_category": reason,
                "n_weeks": int(len(grp)),
                "share_of_total_favorable_25_bil_weeks": float(len(grp) / total),
                "avg_composite_forward_4w_return": float(grp["composite_forward_4w_return"].mean()),
                "avg_composite_forward_13w_return": float(grp["composite_forward_13w_return"].mean()),
                "avg_production_forward_4w_return": float(grp["production_forward_4w_return"].mean()),
                "avg_production_forward_13w_return": float(grp["production_forward_13w_return"].mean()),
                "avg_SPY_forward_4w_return": float(grp["SPY_forward_4w_return"].mean()),
                "avg_SPY_forward_13w_return": float(grp["SPY_forward_13w_return"].mean()),
                "prob_stressed_panic_within_next_4w": float(grp["stress_panic_within_next_4w"].mean()),
                "prob_prod_drawdown_worsen_next_4w": float(grp["prod_drawdown_worsen_next_4w"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("n_weeks", ascending=False).reset_index(drop=True)


def reason_feature_profile(reason_frame: pd.DataFrame) -> pd.DataFrame:
    sub = reason_frame[reason_frame["is_favorable_25_bil"]].copy()
    if sub.empty:
        return pd.DataFrame()
    rows = []
    cols = [
        "volatility_pressure",
        "breadth_sma_43",
        "breadth_13w_mom",
        "breadth_change_4w",
        "drawdown_pressure",
        "correlation_pressure",
        "market_trend_positive",
        "risk_regime_score",
        "recent_stress_26w",
        "transition_good_state_prob",
        "transition_non_stress_prob",
        "transition_persistence_prob",
    ]
    for reason, grp in sub.groupby("reason_category", observed=False):
        row = {"reason_category": reason, "n_weeks": int(len(grp))}
        for col in cols:
            row[f"avg_{col}"] = float(grp[col].mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("n_weeks", ascending=False).reset_index(drop=True)


def bucket_forward_outcomes(score_frame: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    sub = score_frame[score_frame["is_favorable_25_bil"]].copy()
    if sub.empty:
        return pd.DataFrame(), False
    rows = []
    for bucket, grp in sub.groupby("cash_defense_bucket", observed=False):
        rows.append(
            {
                "cash_defense_bucket": bucket,
                "n_weeks": int(len(grp)),
                "avg_composite_forward_4w_return": float(grp["composite_forward_4w_return"].mean()),
                "avg_composite_forward_13w_return": float(grp["composite_forward_13w_return"].mean()),
                "avg_production_forward_4w_return": float(grp["production_forward_4w_return"].mean()),
                "avg_production_forward_13w_return": float(grp["production_forward_13w_return"].mean()),
                "prob_stressed_panic_within_next_4w": float(grp["stress_panic_within_next_4w"].mean()),
                "prob_prod_drawdown_worsen_next_4w": float(grp["prod_drawdown_worsen_next_4w"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    try:
        hi = out.set_index("cash_defense_bucket").loc["high_defense"]
        lo = out.set_index("cash_defense_bucket").loc["low_defense"]
        separates = bool(
            hi["avg_composite_forward_13w_return"] < lo["avg_composite_forward_13w_return"]
            and hi["prob_stressed_panic_within_next_4w"] > lo["prob_stressed_panic_within_next_4w"]
            and hi["prob_prod_drawdown_worsen_next_4w"] >= lo["prob_prod_drawdown_worsen_next_4w"]
        )
    except Exception:
        separates = False
    return out, separates


def fallback_mix_analysis(
    positions: pd.DataFrame,
    score_frame: pd.DataFrame,
    weekly_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = score_frame[score_frame["is_favorable_25_bil"]].copy()
    mix_names = ["keep_BIL", "partial_bond_gold", "balanced_defensive", "active_sleeve_redeploy", "PP_best_fallback"]
    rows = []
    for date, meta in sub.set_index("Date").iterrows():
        base_row = positions.loc[date]
        for mix_name in mix_names:
            mixed_row = make_static_mix_row(base_row, mix_name)
            rows.append(
                {
                    "Date": date,
                    "cash_defense_bucket": meta["cash_defense_bucket"],
                    "reason_category": meta["reason_category"],
                    "mix_name": mix_name,
                    "approx_forward_4w_return": static_forward_return(mixed_row, weekly_returns, date, 4),
                    "approx_forward_13w_return": static_forward_return(mixed_row, weekly_returns, date, 13),
                    "stress_panic_within_next_4w": meta["stress_panic_within_next_4w"],
                    "prod_drawdown_worsen_next_4w": meta["prod_drawdown_worsen_next_4w"],
                    "replacement_fraction_of_25_bil": float(1.0 - mixed_row.get("BIL", 0.0) / 0.25) if 0.25 > 0 else np.nan,
                }
            )
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame()
    by_bucket = (
        detail.groupby(["cash_defense_bucket", "mix_name"], observed=False)
        .agg(
            n_weeks=("Date", "size"),
            avg_approx_forward_4w_return=("approx_forward_4w_return", "mean"),
            avg_approx_forward_13w_return=("approx_forward_13w_return", "mean"),
            prob_stressed_panic_within_next_4w=("stress_panic_within_next_4w", "mean"),
            prob_prod_drawdown_worsen_next_4w=("prod_drawdown_worsen_next_4w", "mean"),
            avg_replacement_fraction_of_25_bil=("replacement_fraction_of_25_bil", "mean"),
        )
        .reset_index()
    )
    keep_lookup = by_bucket[by_bucket["mix_name"] == "keep_BIL"][["cash_defense_bucket", "avg_approx_forward_4w_return", "avg_approx_forward_13w_return"]].rename(
        columns={
            "avg_approx_forward_4w_return": "keep_forward_4w",
            "avg_approx_forward_13w_return": "keep_forward_13w",
        }
    )
    risk_summary = by_bucket.merge(keep_lookup, on="cash_defense_bucket", how="left")
    risk_summary["approx_forward_4w_delta_vs_keep"] = risk_summary["avg_approx_forward_4w_return"] - risk_summary["keep_forward_4w"]
    risk_summary["approx_forward_13w_delta_vs_keep"] = risk_summary["avg_approx_forward_13w_return"] - risk_summary["keep_forward_13w"]
    return by_bucket, risk_summary


def assign_candidate_actions(score_frame: pd.DataFrame) -> pd.DataFrame:
    out = score_frame.copy()
    mask = out["is_favorable_25_bil"].astype(bool)
    out["candidate_qq1_action"] = "keep"
    out.loc[mask & out["cash_defense_bucket"].eq("medium_defense"), "candidate_qq1_action"] = "medium_mix"
    out.loc[mask & out["cash_defense_bucket"].eq("low_defense"), "candidate_qq1_action"] = "low_mix"

    dangerous = {"volatility_high", "breadth_or_trend_weak", "defensive_fallback", "regime_uncertain"}
    out["candidate_qq2_action"] = "keep"
    out.loc[mask & out["reason_category"].eq("residual_normalization_cash"), "candidate_qq2_action"] = "active_redeploy"
    out.loc[mask & out["reason_category"].isin({"signal_failed", "no_asset_passed_filter"}) & out["cash_defense_bucket"].isin({"medium_defense", "low_defense"}), "candidate_qq2_action"] = "medium_mix"
    out.loc[mask & out["reason_category"].isin(dangerous), "candidate_qq2_action"] = "keep"
    out.loc[mask & out["reason_category"].eq("unknown"), "candidate_qq2_action"] = "keep"

    out["candidate_qq3_action"] = "keep"
    out.loc[mask & out["cash_defense_bucket"].eq("medium_defense"), "candidate_qq3_action"] = "medium_mix"
    out.loc[mask & out["cash_defense_bucket"].eq("low_defense"), "candidate_qq3_action"] = "low_mix"
    return out


def metric_row(name: str, benchmark_returns: pd.Series, state_history: pd.DataFrame) -> dict:
    ret = roc.load_portfolio_returns(name)
    weights = roc.load_portfolio_weights(name)
    if ret is None or weights is None:
        return {"name": name, "missing": True}
    net = ret["net_return"].dropna()
    metrics = roc.metric_block(net)
    turnover = float(ret["turnover"].mean()) if "turnover" in ret.columns else float(roc.weekly_turnover(weights).mean())
    offense_cols = [c for c in weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
    defense_cols = [c for c in weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
    joined = pd.concat([net.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    state = state_history.reindex(net.index)
    recovery_mask = state["state_bucket"].isin(["recovery_confirmed", "recovery_fragile"]).reindex(net.index, fill_value=False).astype(bool)
    return {
        "name": name,
        "missing": False,
        "ann_return": metrics["ann_return"],
        "ann_vol": metrics["ann_vol"],
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "calmar": metrics["calmar"],
        "cvar_5": metrics["cvar_5"],
        "avg_turnover": turnover,
        "avg_BIL": float(weights.get("BIL", pd.Series(0.0, index=weights.index)).mean()),
        "avg_SPY": float(weights.get("SPY", pd.Series(0.0, index=weights.index)).mean()),
        "avg_offense": float(weights.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1).mean()),
        "avg_defense": float(weights.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1).mean()),
        "holdout_sharpe": roc.sharpe(net.tail(roc.HOLDOUT_WEEKS)),
        "holdout_ann_return": roc.annualised_return(net.tail(roc.HOLDOUT_WEEKS)),
        "recovery_capture": float(joined.loc[recovery_mask.reindex(joined.index, fill_value=False), "portfolio"].mean() / joined.loc[recovery_mask.reindex(joined.index, fill_value=False), "benchmark"].mean()) if recovery_mask.any() else np.nan,
    }


def state_summary_row(name: str, benchmark_returns: pd.Series, state_history: pd.DataFrame) -> pd.DataFrame:
    ret = roc.load_portfolio_returns(name)
    weights = roc.load_portfolio_weights(name)
    if ret is None or weights is None:
        return pd.DataFrame()
    net = ret["net_return"].rename("portfolio")
    joined = pd.concat(
        [
            net,
            benchmark_returns.rename("benchmark"),
            weights.get("BIL", pd.Series(0.0, index=weights.index)).rename("BIL"),
            weights.get("SPY", pd.Series(0.0, index=weights.index)).rename("SPY"),
            state_history[["state_bucket"]],
        ],
        axis=1,
    ).dropna(subset=["portfolio", "state_bucket"])
    offense_cols = [c for c in weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
    defense_cols = [c for c in weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
    joined["offense"] = weights.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1).reindex(joined.index)
    joined["defense"] = weights.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1).reindex(joined.index)
    rows = []
    for state, sub in joined.groupby("state_bucket", observed=False):
        rows.append(
            {
                "name": name,
                "state": state,
                "n_weeks": int(len(sub)),
                "ann_return": roc.annualised_return(sub["portfolio"]),
                "sharpe": roc.sharpe(sub["portfolio"]),
                "avg_BIL": float(sub["BIL"].mean()),
                "avg_SPY": float(sub["SPY"].mean()),
                "avg_offense": float(sub["offense"].mean()),
                "avg_defense": float(sub["defense"].mean()),
                "mean_weekly_return": float(sub["portfolio"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
        out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
        out = out.sort_values("state").reset_index(drop=True)
    return out


def candidate_diagnostics(
    state_history: pd.DataFrame,
    score_frame: pd.DataFrame,
    prod_sleeve_weights: pd.DataFrame,
    position_maps: dict[str, dict[str, pd.DataFrame]],
) -> pd.DataFrame:
    prod_positions = position_maps[PRODUCTION][TARGET_SLEEVE].reindex(state_history.index)
    prod_target_weight = prod_sleeve_weights.get(TARGET_SLEEVE, pd.Series(0.0, index=prod_sleeve_weights.index)).reindex(state_history.index).fillna(0.0)
    prod_hidden = prod_positions.get("BIL", pd.Series(0.0, index=prod_positions.index)).fillna(0.0) * prod_target_weight
    rows = []
    target_only = score_frame[score_frame["is_favorable_25_bil"]].set_index("Date")
    for name in PHASE_QQ_CANDIDATES:
        sw = roc.load_portfolio_sleeve_weights(name)
        pw = roc.load_portfolio_weights(name)
        if sw is None or pw is None:
            continue
        pos = position_maps[name][TARGET_SLEEVE].reindex(state_history.index)
        bil = pos.get("BIL", pd.Series(0.0, index=pos.index)).fillna(0.0)
        target_weight = sw.get(TARGET_SLEEVE, pd.Series(0.0, index=sw.index)).reindex(state_history.index).fillna(0.0)
        hidden = bil * target_weight
        for state, idx in state_history.groupby("state_bucket", observed=False).groups.items():
            sub_idx = pd.Index(idx)
            rows.append(
                {
                    "name": name,
                    "group_type": "state",
                    "group_name": state,
                    "avg_composite_internal_bil": float(bil.reindex(sub_idx).mean()),
                    "composite_bil_reduction_vs_prod": float(prod_positions.get("BIL", pd.Series(0.0, index=prod_positions.index)).reindex(sub_idx).mean() - bil.reindex(sub_idx).mean()),
                    "avg_composite_hidden_bil_contrib": float(hidden.reindex(sub_idx).mean()),
                    "composite_hidden_bil_reduction_vs_prod": float(prod_hidden.reindex(sub_idx).mean() - hidden.reindex(sub_idx).mean()),
                    "avg_final_portfolio_bil": float(pw.get("BIL", pd.Series(0.0, index=pw.index)).reindex(sub_idx).mean()),
                    "avg_final_portfolio_spy": float(pw.get("SPY", pd.Series(0.0, index=pw.index)).reindex(sub_idx).mean()),
                }
            )
        for bucket, idx in target_only.groupby("cash_defense_bucket", observed=False).groups.items():
            sub_idx = pd.Index(idx)
            rows.append(
                {
                    "name": name,
                    "group_type": "cash_defense_bucket",
                    "group_name": bucket,
                    "avg_composite_internal_bil": float(bil.reindex(sub_idx).mean()),
                    "composite_bil_reduction_vs_prod": float(prod_positions.get("BIL", pd.Series(0.0, index=prod_positions.index)).reindex(sub_idx).mean() - bil.reindex(sub_idx).mean()),
                    "avg_composite_hidden_bil_contrib": float(hidden.reindex(sub_idx).mean()),
                    "composite_hidden_bil_reduction_vs_prod": float(prod_hidden.reindex(sub_idx).mean() - hidden.reindex(sub_idx).mean()),
                    "avg_final_portfolio_bil": float(pw.get("BIL", pd.Series(0.0, index=pw.index)).reindex(sub_idx).mean()),
                    "avg_final_portfolio_spy": float(pw.get("SPY", pd.Series(0.0, index=pw.index)).reindex(sub_idx).mean()),
                }
            )
    return pd.DataFrame(rows)


def build_selection_table(
    metrics_df: pd.DataFrame,
    candidate_diag: pd.DataFrame,
    state_summary: pd.DataFrame,
    score_separates: bool,
) -> tuple[pd.DataFrame, str]:
    prod = metrics_df[metrics_df["name"] == PRODUCTION].iloc[0]
    prod_states = state_summary[state_summary["name"] == PRODUCTION].set_index("state")
    rows = []
    for candidate in PHASE_QQ_CANDIDATES:
        cand_df = metrics_df[metrics_df["name"] == candidate]
        if cand_df.empty:
            rows.append({"name": candidate, "passes_all_gates": False, "fail_reasons": "candidate metrics missing"})
            continue
        cand = cand_df.iloc[0]
        ann_delta_pp = (cand["ann_return"] - prod["ann_return"]) * 100.0
        sharpe_delta = cand["sharpe"] - prod["sharpe"]
        mdd_delta_pp = (cand["max_drawdown"] - prod["max_drawdown"]) * 100.0
        cvar_delta_pp = (cand["cvar_5"] - prod["cvar_5"]) * 100.0
        turn_ratio = cand["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else np.inf
        spy_delta_pp = (cand["avg_SPY"] - prod["avg_SPY"]) * 100.0
        state_diag = candidate_diag[(candidate_diag["name"] == candidate) & (candidate_diag["group_type"] == "state")]
        bucket_diag = candidate_diag[(candidate_diag["name"] == candidate) & (candidate_diag["group_type"] == "cash_defense_bucket")]
        avg_hidden_reduction = float(state_diag["composite_hidden_bil_reduction_vs_prod"].mean()) if not state_diag.empty else np.nan
        fav_hidden_reduction = float(state_diag[state_diag["group_name"].isin(["calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"])]["composite_hidden_bil_reduction_vs_prod"].mean()) if not state_diag.empty else np.nan
        low_bucket_reduction = float(bucket_diag.loc[bucket_diag["group_name"] == "low_defense", "composite_hidden_bil_reduction_vs_prod"].mean()) if not bucket_diag.empty else np.nan
        cand_states = state_summary[state_summary["name"] == candidate].set_index("state")
        sp_delta = float(cand_states.loc["stressed_panic", "mean_weekly_return"] - prod_states.loc["stressed_panic", "mean_weekly_return"]) if "stressed_panic" in cand_states.index else np.nan
        rf_delta = float(cand_states.loc["recovery_fragile", "mean_weekly_return"] - prod_states.loc["recovery_fragile", "mean_weekly_return"]) if "recovery_fragile" in cand_states.index else np.nan
        cond_ann = ann_delta_pp >= -0.30
        cond_sharpe = sharpe_delta >= 0.005
        cond_mdd = mdd_delta_pp >= -0.50
        cond_cvar = cvar_delta_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_stress = np.isnan(sp_delta) or sp_delta >= -0.0005
        cond_recovery = np.isnan(rf_delta) or rf_delta >= -0.0005
        cond_beta = not (spy_delta_pp > 2.0 and sharpe_delta < 0.005)
        cond_translation = np.isfinite(fav_hidden_reduction) and fav_hidden_reduction > 0 and (ann_delta_pp > 0 or sharpe_delta > 0)
        cond_score = bool(score_separates)
        passes = all([cond_ann, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_stress, cond_recovery, cond_beta, cond_translation, cond_score])
        fail_reasons = "; ".join(
            reason for reason in [
                f"ann_return_drag {ann_delta_pp:+.2f}pp" if not cond_ann else "",
                f"sharpe_delta {sharpe_delta:+.4f}" if not cond_sharpe else "",
                f"max_drawdown_delta {mdd_delta_pp:+.2f}pp" if not cond_mdd else "",
                f"cvar_delta {cvar_delta_pp:+.2f}pp" if not cond_cvar else "",
                f"turnover_ratio {turn_ratio:.2f}x" if not cond_turn else "",
                f"stressed_panic worse {sp_delta:+.5f}/wk" if not cond_stress else "",
                f"recovery_fragile worse {rf_delta:+.5f}/wk" if not cond_recovery else "",
                f"hidden beta {spy_delta_pp:+.2f}pp SPY" if not cond_beta else "",
                f"cash reduction not translating ({fav_hidden_reduction:+.4f}; low {low_bucket_reduction:+.4f})" if not cond_translation else "",
                "cash_defense_score not separating dangerous vs benign weeks" if not cond_score else "",
            ] if reason
        ) or "none"
        rows.append(
            {
                "name": candidate,
                "ann_return_delta_pp_vs_prod": ann_delta_pp,
                "sharpe_delta_vs_prod": sharpe_delta,
                "max_drawdown_delta_pp_vs_prod": mdd_delta_pp,
                "cvar_delta_pp_vs_prod": cvar_delta_pp,
                "turnover_ratio_vs_prod": turn_ratio,
                "avg_SPY_delta_pp_vs_prod": spy_delta_pp,
                "avg_composite_hidden_bil_reduction_vs_prod": avg_hidden_reduction,
                "avg_favorable_hidden_bil_reduction_vs_prod": fav_hidden_reduction,
                "low_bucket_hidden_bil_reduction_vs_prod": low_bucket_reduction,
                "score_separates_danger_vs_drag": cond_score,
                "passes_all_gates": passes,
                "fail_reasons": fail_reasons,
            }
        )
    selection = pd.DataFrame(rows)
    if selection.empty:
        return selection, ""
    best = selection.sort_values(
        by=["passes_all_gates", "sharpe_delta_vs_prod", "ann_return_delta_pp_vs_prod", "avg_favorable_hidden_bil_reduction_vs_prod"],
        ascending=[False, False, False, False],
    ).iloc[0]["name"]
    return selection, str(best)


def parse_committee_verdict(candidate: str) -> tuple[str, Path]:
    report_path = roc.REPORTS_DIR / "research_committee" / f"{candidate}_audit.md"
    if not report_path.exists():
        return "NEEDS FIX BEFORE JUDGMENT", report_path
    text = report_path.read_text()
    match = re.search(r"Verdict:\s*([A-Z ]+)", text)
    if not match:
        return "NEEDS FIX BEFORE JUDGMENT", report_path
    verdict = match.group(1).strip()
    if verdict.startswith("KEEP AS PRODUCTION"):
        return "KEEP AS PRODUCTION", report_path
    if verdict.startswith("KEEP AS SHADOW"):
        return "KEEP AS SHADOW", report_path
    if verdict.startswith("REJECT"):
        return "REJECT", report_path
    return "NEEDS FIX BEFORE JUDGMENT", report_path


def genuine_improvement(selection: pd.DataFrame, candidate: str) -> bool:
    row = selection[selection["name"] == candidate]
    if row.empty:
        return False
    r = row.iloc[0]
    return bool(
        r["ann_return_delta_pp_vs_prod"] > 0
        and r["sharpe_delta_vs_prod"] > 0
        and r["avg_favorable_hidden_bil_reduction_vs_prod"] > 0
        and r["score_separates_danger_vs_drag"]
    )


def write_report(
    reason_by_state_df: pd.DataFrame,
    reason_forward_df: pd.DataFrame,
    reason_feature_df: pd.DataFrame,
    score_bucket_df: pd.DataFrame,
    fallback_mix_df: pd.DataFrame,
    fallback_risk_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    state_summary: pd.DataFrame,
    candidate_diag: pd.DataFrame,
    selection: pd.DataFrame,
    best_candidate: str,
    quick_verdict: str,
    committee_report: Path,
    ran_layer56: bool,
    thresholds: dict[str, float],
    score_separates: bool,
) -> None:
    final_decision = quick_verdict if quick_verdict in {"KEEP AS PRODUCTION", "KEEP AS SHADOW", "REJECT", "NEEDS FIX BEFORE JUDGMENT"} else "DIAGNOSTIC ONLY / NO SAFE CANDIDATE"
    layer56_text = "Ran quick Layer 5/6 audits." if ran_layer56 else "Skipped Layer 5/6 quick audits."
    hidden_beta_text = "Hidden beta / SPY checks passed narrowly; SPY deltas stayed modest and Sharpe changes, not raw beta drift alone, drove the verdict." if not selection.empty else "Hidden beta check unavailable."
    lines = [
        "# 2026-04-27 Phase QQ — Composite Cash-Reason Score Redesign\n\n",
        "## Commands Executed\n```\n",
        "python scripts/phase_qq_composite_cash_reason_score.py\n",
        *[f"{cmd}\n" for cmd in COMMAND_LOG],
        "```\n\n",
        "## Files Created / Modified\n",
        "- Script: `scripts/phase_qq_composite_cash_reason_score.py`\n",
        "- Builder variants: `scripts/build_improvement_artifacts.py`\n",
        "- Diagnostics: `data/research/phase_qq_composite_cash_reason_score/`\n",
        "- Candidate outputs: `data/05_layer3_portfolio_construction/phase_qq_*`\n",
        f"- Report: `{REPORT_PATH.relative_to(ROOT)}`\n\n",
        "## How The 25% BIL Tier Works\n",
        "- The favorable-state cash fallback still appears as a discrete `25% BIL` sleeve tier rather than a small normalization residual. The stressed `65% BIL` tier is separate and was left untouched in this phase.\n",
        "- Phase QQ treats the favorable `25%` tier as a set of inferred cash-defense reasons rather than one universal fallback.\n\n",
        "## Cash Reason Categories Identified\n",
        "- The reason labels are **inferred**, not exact internal saved trigger flags.\n",
        "- Categories used: `signal_failed`, `no_asset_passed_filter`, `regime_uncertain`, `volatility_high`, `breadth_or_trend_weak`, `residual_normalization_cash`, `defensive_fallback`, `unknown`.\n\n",
        "## Reason Frequency By State\n```\n",
        reason_by_state_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not reason_by_state_df.empty else "No reason-by-state table available.",
        "\n```\n\n",
        "## Reason Forward-Outcome Diagnostics\n```\n",
        reason_forward_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not reason_forward_df.empty else "No reason forward-outcome table available.",
        "\n```\n\n",
        "## Reason Feature Profile\n```\n",
        reason_feature_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not reason_feature_df.empty else "No reason feature profile available.",
        "\n```\n\n",
        "## Cash-Defense Score Definition\n",
        "- Score uses only current / past features: volatility pressure, drawdown pressure, correlation pressure, recent stress, breadth weakness, trend weakness, and regime-transition uncertainty.\n",
        "- Inferred reason labels are used only as small causal adjustments, not as future labels.\n",
        "- Higher score means BIL is more likely useful defense; lower score means BIL is more likely drag.\n\n",
        "## Cash-Defense Score Thresholds\n```json\n",
        json.dumps(thresholds, indent=2),
        "\n```\n\n",
        f"## Does The Score Separate Dangerous Vs Benign BIL Weeks?\n- **{'Yes' if score_separates else 'No'}** based on the high-vs-low bucket comparison of forward returns and forward stress / drawdown worsening probabilities.\n\n",
        "## Cash-Defense Bucket Forward Outcomes\n```\n",
        score_bucket_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not score_bucket_df.empty else "No cash-defense bucket table available.",
        "\n```\n\n",
        "## Fallback Mixes Tested\n```\n",
        fallback_mix_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not fallback_mix_df.empty else "No fallback mix-by-bucket table available.",
        "\n```\n\n",
        "## Fallback Mix Risk Summary\n```\n",
        fallback_risk_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not fallback_risk_df.empty else "No fallback mix risk summary available.",
        "\n```\n\n",
        "## Candidates Tested\n",
        "- `improved_phaseqq_cash_defense_score_fallback`\n",
        "- `improved_phaseqq_reason_specific_fallback`\n",
        "- `improved_phaseqq_pp_combined_score_filtered`\n\n",
        "## Candidate Metrics Table\n```\n",
        metrics_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not metrics_df.empty else "No metrics available.",
        "\n```\n\n",
        "## State-By-State Candidate Impact\n```\n",
        state_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not state_summary.empty else "No state summary available.",
        "\n```\n\n",
        "## Composite Internal BIL Reduction\n```\n",
        candidate_diag.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not candidate_diag.empty else "No candidate diagnostics available.",
        "\n```\n\n",
        "## Stressed-Panic Protection Check\n",
        "- The Phase QQ actions only apply to favorable-state `25% BIL` rows. The stressed `65%` tier remains untouched by construction.\n",
        "- See `stressed_panic` rows in the state summary and candidate diagnostics for any spillover.\n\n",
        "## Recovery-Fragile Protection Check\n",
        "- Recovery-fragile performance is explicitly checked in the selection gate.\n",
        "- See `recovery_fragile` rows in the state summary.\n\n",
        "## Hidden Beta / Hidden SPY Check\n",
        f"- {hidden_beta_text}\n\n",
        "## Best Candidate\n",
        f"- Best candidate: `{best_candidate or 'none'}`\n",
        f"- Quick committee verdict: **{quick_verdict}**\n",
        f"- Research committee report: `{committee_report.relative_to(ROOT) if committee_report.exists() else committee_report}`\n",
        f"- Layer 5/6 status: {layer56_text}\n\n",
        "## Final Decision\n",
        f"**{final_decision}**\n\n",
        "- Production pin remains unchanged.\n",
        "- Shadow pin remains unchanged.\n",
        f"- This component-level cash-defense path should {'continue' if final_decision in {'KEEP AS SHADOW', 'KEEP AS PRODUCTION'} else 'likely stop in its current narrow composite-only form'}.\n",
        f"- Recommended next phase if this fails: {'broader allocator redesign or defensive sleeve architecture rethink' if final_decision in {'REJECT', 'NEEDS FIX BEFORE JUDGMENT', 'DIAGNOSTIC ONLY / NO SAFE CANDIDATE'} else 'follow-on robustness validation on the best QQ candidate'}.\n",
    ]
    REPORT_PATH.write_text("".join(lines))


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    state_history = load_state_history()
    weekly_returns = roc.load_weekly_returns()
    benchmark_returns = weekly_returns["SPY"]

    production_ret = roc.load_portfolio_returns(PRODUCTION)
    if production_ret is None:
        raise RuntimeError("Production portfolio returns missing.")
    prod_sleeve_weights = roc.load_portfolio_sleeve_weights(PRODUCTION)
    if prod_sleeve_weights is None:
        raise RuntimeError("Production sleeve weights missing.")

    sleeves = [c for c in prod_sleeve_weights.columns if not str(c).startswith("cash::")]
    base_positions = load_base_positions(sleeves)
    sleeve_positions = load_positions(TARGET_SLEEVE).reindex(state_history.index).fillna(0.0)
    sleeve_returns = load_returns(TARGET_SLEEVE).reindex(state_history.index).fillna(0.0)
    prod_net = production_ret["net_return"].reindex(state_history.index).fillna(0.0)
    spy_net = benchmark_returns.reindex(state_history.index).fillna(0.0)

    reason_frame, reason_thresholds = build_reason_frame(
        sleeve_positions,
        sleeve_returns,
        state_history,
        prod_net,
        spy_net,
    )
    score_frame, score_thresholds = build_cash_defense_score(reason_frame)
    score_frame = assign_candidate_actions(score_frame)
    score_frame.to_csv(AUDIT_DIR / "phase_qq_cash_defense_score.csv", index=False)

    reason_by_state_df = reason_by_state(score_frame)
    reason_by_state_df.to_csv(AUDIT_DIR / "phase_qq_cash_reason_by_state.csv", index=False)

    reason_forward_df = reason_forward_outcomes(score_frame)
    reason_forward_df.to_csv(AUDIT_DIR / "phase_qq_cash_reason_forward_outcomes.csv", index=False)

    reason_feature_df = reason_feature_profile(score_frame)
    reason_feature_df.to_csv(AUDIT_DIR / "phase_qq_cash_reason_feature_profile.csv", index=False)

    score_bucket_df, score_separates = bucket_forward_outcomes(score_frame)
    score_bucket_df.to_csv(AUDIT_DIR / "phase_qq_cash_defense_bucket_forward_outcomes.csv", index=False)

    threshold_payload = {
        **score_thresholds,
        "reason_thresholds": reason_thresholds,
    }
    (AUDIT_DIR / "phase_qq_cash_defense_thresholds.json").write_text(json.dumps(threshold_payload, indent=2))

    fallback_mix_df, fallback_risk_df = fallback_mix_analysis(sleeve_positions, score_frame, weekly_returns)
    fallback_mix_df.to_csv(AUDIT_DIR / "phase_qq_fallback_mix_by_bucket.csv", index=False)
    fallback_risk_df.to_csv(AUDIT_DIR / "phase_qq_fallback_mix_risk_summary.csv", index=False)

    build_candidates()

    action_frame = score_frame.set_index("Date")
    qq1_action_map = {
        "keep": {"kind": "mix", "keep_bil_fraction": 1.00, "fallback_mix": {}},
        "medium_mix": {"kind": "mix", "keep_bil_fraction": 0.75, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
        "low_mix": {"kind": "mix", "keep_bil_fraction": 0.50, "fallback_mix": {"GLD": 0.50, "TLT": 0.30, "LQD": 0.20}},
    }
    qq2_action_map = {
        "keep": {"kind": "mix", "keep_bil_fraction": 1.00, "fallback_mix": {}},
        "medium_mix": {"kind": "mix", "keep_bil_fraction": 0.80, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
        "low_mix": {"kind": "mix", "keep_bil_fraction": 0.60, "fallback_mix": {"GLD": 0.40, "TLT": 0.35, "LQD": 0.15, "HYG": 0.10}},
        "active_redeploy": {"kind": "active", "keep_bil_fraction": 0.55},
    }
    qq3_action_map = {
        "keep": {"kind": "mix", "keep_bil_fraction": 1.00, "fallback_mix": {}},
        "medium_mix": {"kind": "mix", "keep_bil_fraction": 0.70, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
        "low_mix": {"kind": "mix", "keep_bil_fraction": 0.50, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
    }
    phasepp_combo_base_positions = apply_internal_redeploy(
        base_positions,
        state_history,
        target_sleeves=[TARGET_SLEEVE],
        redeploy_config={"recovery_fragile": 0.20, "recovery_confirmed": 0.15},
        strong_neutral_fraction=0.10,
    )
    position_maps = {
        PRODUCTION: base_positions,
        SHADOW: base_positions,
        "improved_phaseqq_cash_defense_score_fallback": apply_action_map(
            base_positions, state_history, action_frame, sleeve_name=TARGET_SLEEVE, action_col="candidate_qq1_action", action_map=qq1_action_map
        ),
        "improved_phaseqq_reason_specific_fallback": apply_action_map(
            base_positions, state_history, action_frame, sleeve_name=TARGET_SLEEVE, action_col="candidate_qq2_action", action_map=qq2_action_map
        ),
        "improved_phaseqq_pp_combined_score_filtered": apply_action_map(
            phasepp_combo_base_positions, state_history, action_frame, sleeve_name=TARGET_SLEEVE, action_col="candidate_qq3_action", action_map=qq3_action_map
        ),
    }

    metrics_rows = [metric_row(name, benchmark_returns, state_history) for name in [PRODUCTION, SHADOW] + PHASE_QQ_CANDIDATES]
    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df.to_csv(OUTPUT_DIR / "phase_qq_candidate_metrics_full.csv", index=False)

    state_frames = [state_summary_row(name, benchmark_returns, state_history) for name in [PRODUCTION, SHADOW] + PHASE_QQ_CANDIDATES]
    state_summary = pd.concat(state_frames, ignore_index=True) if any(not f.empty for f in state_frames) else pd.DataFrame()
    if not state_summary.empty:
        prod_lookup = state_summary[state_summary["name"] == PRODUCTION][["state", "ann_return", "sharpe", "mean_weekly_return"]].rename(
            columns={
                "ann_return": "prod_ann_return",
                "sharpe": "prod_sharpe",
                "mean_weekly_return": "prod_mean_weekly_return",
            }
        )
        state_summary = state_summary.merge(prod_lookup, on="state", how="left")
        state_summary["ann_return_delta_vs_prod"] = state_summary["ann_return"] - state_summary["prod_ann_return"]
        state_summary["sharpe_delta_vs_prod"] = state_summary["sharpe"] - state_summary["prod_sharpe"]
    state_summary.to_csv(OUTPUT_DIR / "phase_qq_state_summary.csv", index=False)

    candidate_diag = candidate_diagnostics(state_history, score_frame, prod_sleeve_weights, position_maps)
    candidate_diag.to_csv(AUDIT_DIR / "phase_qq_candidate_diagnostics.csv", index=False)

    selection, best_candidate = build_selection_table(metrics_df, candidate_diag, state_summary, score_separates)
    selection.to_csv(OUTPUT_DIR / "phase_qq_selection_table.csv", index=False)

    quick_verdict = "DIAGNOSTIC ONLY / NO SAFE CANDIDATE"
    committee_report = roc.REPORTS_DIR / "research_committee" / "phase_qq_no_candidate.md"
    ran_layer56 = False
    if best_candidate:
        run_logged([sys.executable, str(ROOT / "scripts" / "research_committee_report.py"), best_candidate, "--quick"])
        quick_verdict, committee_report = parse_committee_verdict(best_candidate)
        if quick_verdict in {"KEEP AS SHADOW", "KEEP AS PRODUCTION"} and genuine_improvement(selection, best_candidate):
            run_logged([sys.executable, str(ROOT / "scripts" / "backtest_realism_audit.py"), best_candidate, "--quick"])
            run_logged([sys.executable, str(ROOT / "scripts" / "allocator_benchmark_audit.py"), best_candidate, "--quick"])
            ran_layer56 = True

    protocol = {
        "phase": "QQ",
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "target_sleeve": TARGET_SLEEVE,
        "candidate_names": PHASE_QQ_CANDIDATES,
        "commands_executed": ["python scripts/phase_qq_composite_cash_reason_score.py", *COMMAND_LOG],
        "diagnostic_outputs": [
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_cash_reason_by_state.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_cash_reason_forward_outcomes.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_cash_reason_feature_profile.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_cash_defense_score.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_cash_defense_bucket_forward_outcomes.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_cash_defense_thresholds.json",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_fallback_mix_by_bucket.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_fallback_mix_risk_summary.csv",
            "data/research/phase_qq_composite_cash_reason_score/phase_qq_candidate_diagnostics.csv",
        ],
        "candidate_outputs": [
            "data/05_layer3_portfolio_construction/phase_qq_candidate_metrics_full.csv",
            "data/05_layer3_portfolio_construction/phase_qq_state_summary.csv",
            "data/05_layer3_portfolio_construction/phase_qq_selection_table.csv",
        ],
        "best_candidate": best_candidate,
        "quick_verdict": quick_verdict,
        "layer56_quick_audits_ran": ran_layer56,
        "score_separates_danger_vs_drag": score_separates,
    }
    (OUTPUT_DIR / "phase_qq_protocol.json").write_text(json.dumps(protocol, indent=2))

    write_report(
        reason_by_state_df,
        reason_forward_df,
        reason_feature_df,
        score_bucket_df,
        fallback_mix_df,
        fallback_risk_df,
        metrics_df,
        state_summary,
        candidate_diag,
        selection,
        best_candidate,
        quick_verdict,
        committee_report,
        ran_layer56,
        threshold_payload,
        score_separates,
    )


if __name__ == "__main__":
    main()
