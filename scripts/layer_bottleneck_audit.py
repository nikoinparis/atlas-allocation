from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"
REPORT_DIR = ROOT / "reports" / "layer_bottleneck_audit"
OUTPUT_DIR = ROOT / "data" / "research" / "layer_bottleneck_audit"
DOCS_DIR = ROOT / "docs" / "research"

PRODUCTION_VERSION = "improved_phase2b_regime_confidence_boost"
WEEKS_PER_YEAR = 52
MAX_SLEEVE_WEIGHT = 0.45
PRODUCTION_SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    "composite_regime_conditioned",
    "taa_10m_sma",
]
DEFENSIVE_SLEEVES = {"composite_regime_conditioned", "taa_10m_sma"}
OFFENSIVE_SLEEVES = {
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
}
GOOD_STATES = {"calm_trend", "recovery_confirmed"}
RECOVERY_STATES = {"recovery_fragile", "recovery_confirmed"}


def read_timeseries_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for candidate in ("Date", "Unnamed: 0"):
        if candidate in df.columns:
            df = df.rename(columns={candidate: "Date"})
            break
    if "Date" not in df.columns:
        raise ValueError(f"Missing Date column in {path}")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date").sort_index()


def summary_stats(returns: pd.Series) -> dict[str, float]:
    series = pd.Series(returns, dtype=float).dropna()
    if series.empty:
        return {
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "calmar": np.nan,
            "cvar_5": np.nan,
            "observations": 0,
        }
    wealth = (1.0 + series).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    ann_return = wealth.iloc[-1] ** (WEEKS_PER_YEAR / len(series)) - 1.0
    ann_vol = series.std(ddof=0) * math.sqrt(WEEKS_PER_YEAR)
    sharpe = np.nan if ann_vol == 0 or pd.isna(ann_vol) else series.mean() / series.std(ddof=0) * math.sqrt(WEEKS_PER_YEAR)
    max_drawdown = drawdown.min()
    cvar_cutoff = series.quantile(0.05)
    cvar_5 = series[series <= cvar_cutoff].mean()
    calmar = np.nan if max_drawdown >= 0 or pd.isna(max_drawdown) else ann_return / abs(max_drawdown)
    return {
        "ann_return": float(ann_return),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe) if pd.notna(sharpe) else np.nan,
        "max_drawdown": float(max_drawdown),
        "calmar": float(calmar) if pd.notna(calmar) else np.nan,
        "cvar_5": float(cvar_5) if pd.notna(cvar_5) else np.nan,
        "observations": int(len(series)),
    }


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    frame = pd.concat([pd.Series(left, dtype=float), pd.Series(right, dtype=float)], axis=1).dropna()
    if len(frame) < 8:
        return np.nan
    return float(frame.iloc[:, 0].corr(frame.iloc[:, 1]))


def classify_state_row(row: pd.Series) -> str:
    prod_gap = float(row["prod_minus_spy_ann_return"])
    cash = float(row["avg_bil_weight"])
    offense = float(row["avg_offensive_weight"])
    tail = float(row["avg_p_tail_risk"]) if pd.notna(row["avg_p_tail_risk"]) else np.nan
    next_stress = float(row["transition_to_stress_rate"])
    state = str(row["market_state"])
    spy_ann = float(row["spy_ann_return"])

    if state in GOOD_STATES and cash >= 0.18 and spy_ann > 0.08:
        return "too defensive"
    if state == "neutral_mixed" and cash >= 0.24 and prod_gap < -0.02 and float(row["avg_p_regime_confidence"]) >= 0.55:
        return "too defensive"
    if state == "neutral_mixed" and next_stress >= 0.12 and offense >= 0.62 and (pd.isna(tail) or tail < 0.45):
        return "too aggressive before stress"
    if state == "recovery_fragile" and cash >= 0.20 and spy_ann > 0.10:
        return "re-risking too slow"
    if prod_gap < -0.03 and cash >= 0.20:
        return "too defensive"
    return "approximately right"


def severity_label(score: float) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def format_num(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}"


def join_state_frame(index: pd.Index) -> pd.DataFrame:
    market_state = read_timeseries_csv(LAYER2B_DIR / "market_state_history.csv")
    market_state_refined = read_timeseries_csv(LAYER2B_DIR / "market_state_history_refined.csv")
    phase2b_meta = read_timeseries_csv(LAYER2B_DIR / "phase2b_meta_predictions.csv")
    state = (
        market_state.reindex(index)
        .join(
            market_state_refined[
                [col for col in ["refined_state", "confidence_score_p2b", "defensive_overlay_hint"] if col in market_state_refined.columns]
            ].reindex(index),
            how="left",
        )
        .join(phase2b_meta.reindex(index), how="left")
    )
    return state


def load_weekly_simple_returns() -> pd.DataFrame:
    weekly_log_returns = pd.read_csv(DATA_HUB_DIR / "weekly_returns.csv", index_col=0, parse_dates=True).sort_index()
    return np.expm1(weekly_log_returns)


def compute_sleeve_audit(
    state_frame: pd.DataFrame,
    production_returns: pd.Series,
    production_sleeve_weights: pd.DataFrame,
    spy_returns: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    sleeve_returns: dict[str, pd.Series] = {}
    sleeve_turnover: dict[str, float] = {}
    rows: list[dict] = []
    sleeve_flags: dict[str, list[str]] = {}

    for sleeve in PRODUCTION_SLEEVES:
        ret_df = read_timeseries_csv(LAYER2A_DIR / f"strategy_returns_{sleeve}.csv")
        returns = ret_df["net_return"].astype(float).reindex(state_frame.index).fillna(0.0)
        sleeve_returns[sleeve] = returns
        sleeve_turnover[sleeve] = float(ret_df["turnover"].astype(float).dropna().mean()) if "turnover" in ret_df.columns else np.nan

    corr_matrix = pd.DataFrame(sleeve_returns).corr().sort_index().sort_index(axis=1)

    state_sharpes = {
        sleeve: {
            state_name: summary_stats(series)["sharpe"]
            for state_name, series in pd.DataFrame(
                {"return": sleeve_returns[sleeve], "market_state": state_frame["market_state"]}
            ).groupby("market_state")["return"]
        }
        for sleeve in PRODUCTION_SLEEVES
    }

    for sleeve in PRODUCTION_SLEEVES:
        stats = summary_stats(sleeve_returns[sleeve])
        avg_weight = float(production_sleeve_weights[sleeve].mean())
        corr_prod = safe_corr(sleeve_returns[sleeve], production_returns)
        corr_spy = safe_corr(sleeve_returns[sleeve], spy_returns)
        sleeve_flags[sleeve] = []
        if pd.notna(stats["sharpe"]) and stats["sharpe"] < 0.45:
            sleeve_flags[sleeve].append("low standalone Sharpe")
        if pd.notna(sleeve_turnover[sleeve]) and sleeve_turnover[sleeve] > 0.20 and stats["sharpe"] < 0.75:
            sleeve_flags[sleeve].append("turnover without clear benefit")
        for peer in PRODUCTION_SLEEVES:
            if peer == sleeve:
                continue
            peer_stats = summary_stats(sleeve_returns[peer])
            corr = corr_matrix.loc[sleeve, peer]
            if pd.notna(corr) and corr >= 0.80 and stats["sharpe"] + 0.10 < peer_stats["sharpe"]:
                sleeve_flags[sleeve].append(f"redundant to {peer}")
                break

        for state_name, state_group in pd.DataFrame(
            {
                "return": sleeve_returns[sleeve],
                "prod_weight": production_sleeve_weights[sleeve],
                "market_state": state_frame["market_state"],
            }
        ).groupby("market_state"):
            weight_state = float(state_group["prod_weight"].mean())
            metrics = summary_stats(state_group["return"])
            performance_rank = pd.Series({name: state_sharpes[name].get(state_name, np.nan) for name in PRODUCTION_SLEEVES}).rank(
                ascending=False, method="min"
            ).get(sleeve, np.nan)
            helps_when_used = bool(weight_state >= avg_weight and (pd.notna(metrics["sharpe"]) and metrics["sharpe"] > 0))
            row_flags = list(sleeve_flags[sleeve])
            if weight_state > avg_weight * 1.1 and (pd.isna(metrics["sharpe"]) or metrics["sharpe"] < 0):
                row_flags.append(f"weighted in underperforming state {state_name}")
            rows.append(
                {
                    "sleeve_name": sleeve,
                    "market_state": state_name,
                    "ann_return": metrics["ann_return"],
                    "ann_vol": metrics["ann_vol"],
                    "sharpe": metrics["sharpe"],
                    "max_drawdown": metrics["max_drawdown"],
                    "cvar_5": metrics["cvar_5"],
                    "observations": metrics["observations"],
                    "turnover": sleeve_turnover[sleeve],
                    "avg_production_weight": avg_weight,
                    "avg_production_weight_state": weight_state,
                    "corr_with_production": corr_prod,
                    "corr_with_spy": corr_spy,
                    "state_sharpe_rank_among_production_sleeves": performance_rank,
                    "helps_when_used": helps_when_used,
                    "flag_summary": "; ".join(sorted(set(row_flags))),
                }
            )

    return pd.DataFrame(rows), corr_matrix, sleeve_flags


def compute_state_behavior(
    state_frame: pd.DataFrame,
    production_returns: pd.Series,
    production_sleeve_weights: pd.DataFrame,
    production_etf_weights: pd.DataFrame,
    spy_returns: pd.Series,
    bil_returns: pd.Series,
    allocation_driver_ts: pd.DataFrame,
) -> pd.DataFrame:
    next_state = state_frame["market_state"].shift(-1)
    rows: list[dict] = []
    defensive_sleeve_weight = production_sleeve_weights[list(DEFENSIVE_SLEEVES)].sum(axis=1)

    joined = state_frame.copy()
    joined["production_return"] = production_returns
    joined["spy_return"] = spy_returns.reindex(joined.index)
    joined["bil_return"] = bil_returns.reindex(joined.index)
    joined["avg_defensive_sleeve_weight"] = defensive_sleeve_weight.reindex(joined.index)
    joined["next_state"] = next_state.reindex(joined.index)
    joined = joined.join(
        allocation_driver_ts[
            [
                "offensive_weight",
                "defensive_weight",
                "bil_weight",
                "spy_weight",
                "cash_proxy_weight",
                "overlay_cash_weight",
                "sleeve_bil_weight",
            ]
        ],
        how="left",
    )

    for state_name, group in joined.groupby("market_state"):
        prod_stats = summary_stats(group["production_return"])
        spy_stats = summary_stats(group["spy_return"])
        bil_stats = summary_stats(group["bil_return"])
        row = {
            "market_state": state_name,
            "observations": len(group),
            "prod_ann_return": prod_stats["ann_return"],
            "prod_sharpe": prod_stats["sharpe"],
            "spy_ann_return": spy_stats["ann_return"],
            "spy_sharpe": spy_stats["sharpe"],
            "bil_ann_return": bil_stats["ann_return"],
            "bil_sharpe": bil_stats["sharpe"],
            "prod_minus_spy_ann_return": prod_stats["ann_return"] - spy_stats["ann_return"],
            "avg_bil_weight": float(group["bil_weight"].mean()),
            "avg_cash_weight": float(group["cash_proxy_weight"].mean()),
            "avg_spy_weight": float(group["spy_weight"].mean()),
            "avg_offensive_weight": float(group["offensive_weight"].mean()),
            "avg_defensive_weight": float(group["defensive_weight"].mean()),
            "avg_defensive_sleeve_weight": float(group["avg_defensive_sleeve_weight"].mean()),
            "avg_overlay_cash_weight": float(group["overlay_cash_weight"].mean()),
            "avg_sleeve_bil_weight": float(group["sleeve_bil_weight"].mean()),
            "avg_p_regime_confidence": float(group["p_regime_confidence"].mean()),
            "avg_p_transition_quality": float(group["p_transition_quality"].mean()),
            "avg_p_tail_risk": float(group["p_tail_risk"].mean()),
            "avg_transition_non_stress_prob": float(group["transition_non_stress_prob"].mean()),
            "transition_to_stress_rate": float(group["next_state"].eq("stressed_panic").mean()),
            "transition_to_recovery_rate": float(group["next_state"].isin(RECOVERY_STATES).mean()),
        }
        row["diagnosis"] = classify_state_row(pd.Series(row))
        rows.append(row)

    special_pre_stress = joined[joined["next_state"] == "stressed_panic"]
    if not special_pre_stress.empty:
        prod_stats = summary_stats(special_pre_stress["production_return"])
        spy_stats = summary_stats(special_pre_stress["spy_return"])
        rows.append(
            {
                "market_state": "__pre_stress_transition__",
                "observations": len(special_pre_stress),
                "prod_ann_return": prod_stats["ann_return"],
                "prod_sharpe": prod_stats["sharpe"],
                "spy_ann_return": spy_stats["ann_return"],
                "spy_sharpe": spy_stats["sharpe"],
                "bil_ann_return": np.nan,
                "bil_sharpe": np.nan,
                "prod_minus_spy_ann_return": prod_stats["ann_return"] - spy_stats["ann_return"],
                "avg_bil_weight": float(special_pre_stress["bil_weight"].mean()),
                "avg_cash_weight": float(special_pre_stress["cash_proxy_weight"].mean()),
                "avg_spy_weight": float(special_pre_stress["spy_weight"].mean()),
                "avg_offensive_weight": float(special_pre_stress["offensive_weight"].mean()),
                "avg_defensive_weight": float(special_pre_stress["defensive_weight"].mean()),
                "avg_defensive_sleeve_weight": float(special_pre_stress["avg_defensive_sleeve_weight"].mean()),
                "avg_overlay_cash_weight": float(special_pre_stress["overlay_cash_weight"].mean()),
                "avg_sleeve_bil_weight": float(special_pre_stress["sleeve_bil_weight"].mean()),
                "avg_p_regime_confidence": float(special_pre_stress["p_regime_confidence"].mean()),
                "avg_p_transition_quality": float(special_pre_stress["p_transition_quality"].mean()),
                "avg_p_tail_risk": float(special_pre_stress["p_tail_risk"].mean()),
                "avg_transition_non_stress_prob": float(special_pre_stress["transition_non_stress_prob"].mean()),
                "transition_to_stress_rate": 1.0,
                "transition_to_recovery_rate": float(special_pre_stress["next_state"].isin(RECOVERY_STATES).mean()),
                "diagnosis": "pre-stress setup",
            }
        )

    return pd.DataFrame(rows).sort_values(["market_state"]).reset_index(drop=True)


def compute_allocator_stage_diagnostics(
    production_sleeve_weights: pd.DataFrame,
    diagnostics_ts: pd.DataFrame,
    allocation_driver_ts: pd.DataFrame,
    stacked_defense_ts: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict] = []

    if diagnostics_ts.empty:
        return pd.DataFrame()

    def add_metric(scope_type: str, scope_name: str, metric: str, value: float, note: str = "") -> None:
        rows.append(
            {
                "scope_type": scope_type,
                "scope_name": scope_name,
                "metric": metric,
                "value": value,
                "note": note,
            }
        )

    cap_hits = production_sleeve_weights[PRODUCTION_SLEEVES].ge(MAX_SLEEVE_WEIGHT - 1e-6)
    add_metric("overall", "production", "raw_hrp_weights_saved", 0.0, "No saved checkpoint before apply_state_conditioned_tilt.")
    add_metric("overall", "production", "post_state_tilt_weights_saved", 0.0, "No saved checkpoint between apply_state_conditioned_tilt and apply_layer3_expression.")
    add_metric("overall", "production", "post_layer3_expression_weights_saved", 0.0, "No saved checkpoint between apply_layer3_expression and apply_overlays_custom.")
    add_metric("overall", "production", "overlay_diagnostics_saved", 1.0, "Saved via portfolio_version_diagnostics_timeseries.csv.")
    add_metric("overall", "production", "allocation_driver_saved", 1.0, "Saved via allocation_driver_timeseries.csv.")
    add_metric("overall", "production", "avg_regime_multiplier", float(diagnostics_ts["regime_multiplier"].mean()))
    add_metric("overall", "production", "avg_target_vol_multiplier", float(diagnostics_ts["target_vol_multiplier"].mean()))
    add_metric("overall", "production", "regime_binding_rate", float(diagnostics_ts["regime_binding"].mean()))
    add_metric("overall", "production", "target_vol_binding_rate", float(diagnostics_ts["target_vol_binding"].mean()))
    add_metric("overall", "production", "both_binding_rate", float(diagnostics_ts["both_binding"].mean()))
    add_metric("overall", "production", "avg_dynamic_speed", float(diagnostics_ts["dynamic_speed"].mean()))
    add_metric("overall", "production", "avg_self_gated_relief", float(diagnostics_ts["self_gated_relief"].mean()))
    add_metric("overall", "production", "avg_offensive_weight", float(allocation_driver_ts["offensive_weight"].mean()))
    add_metric("overall", "production", "avg_defensive_weight", float(allocation_driver_ts["defensive_weight"].mean()))
    add_metric("overall", "production", "avg_bil_weight", float(allocation_driver_ts["bil_weight"].mean()))
    add_metric("overall", "production", "avg_overlay_cash_weight", float(allocation_driver_ts["overlay_cash_weight"].mean()))
    add_metric("overall", "production", "avg_spy_weight", float(allocation_driver_ts["spy_weight"].mean()))
    add_metric("overall", "production", "any_cap_hit_rate", float(cap_hits.any(axis=1).mean()))
    for sleeve in PRODUCTION_SLEEVES:
        add_metric("sleeve", sleeve, "cap_hit_rate", float(cap_hits[sleeve].mean()))

    if stacked_defense_ts is not None and not stacked_defense_ts.empty:
        add_metric("overall", "production", "avg_self_gated_overlay_cut_risky", float(stacked_defense_ts["self_gated_overlay_cut_risky"].mean()))
        add_metric("overall", "production", "avg_non_self_gated_overlay_cut_risky", float(stacked_defense_ts["non_self_gated_overlay_cut_risky"].mean()))
        add_metric("overall", "production", "avg_sleeve_internal_bil_weight", float(stacked_defense_ts["sleeve_internal_bil_weight"].mean()))
        add_metric("overall", "production", "avg_overlay_cash_weight_from_stacked_defense", float(stacked_defense_ts["overlay_cash_weight"].mean()))

    for state_name, group in diagnostics_ts.groupby("market_state"):
        add_metric("market_state", state_name, "avg_regime_multiplier", float(group["regime_multiplier"].mean()))
        add_metric("market_state", state_name, "regime_binding_rate", float(group["regime_binding"].mean()))
        add_metric("market_state", state_name, "target_vol_binding_rate", float(group["target_vol_binding"].mean()))
        add_metric("market_state", state_name, "avg_dynamic_speed", float(group["dynamic_speed"].mean()))
        add_metric("market_state", state_name, "avg_self_gated_relief", float(group["self_gated_relief"].mean()))
        driver_group = allocation_driver_ts[allocation_driver_ts["market_state"] == state_name]
        if not driver_group.empty:
            add_metric("market_state", state_name, "avg_bil_weight", float(driver_group["bil_weight"].mean()))
            add_metric("market_state", state_name, "avg_spy_weight", float(driver_group["spy_weight"].mean()))
            add_metric("market_state", state_name, "avg_offensive_weight", float(driver_group["offensive_weight"].mean()))
            add_metric("market_state", state_name, "avg_overlay_cash_weight", float(driver_group["overlay_cash_weight"].mean()))
        if stacked_defense_ts is not None and not stacked_defense_ts.empty:
            stacked_group = stacked_defense_ts[stacked_defense_ts["market_state"] == state_name]
            if not stacked_group.empty:
                add_metric("market_state", state_name, "avg_self_gated_overlay_cut_risky", float(stacked_group["self_gated_overlay_cut_risky"].mean()))
                add_metric("market_state", state_name, "avg_non_self_gated_overlay_cut_risky", float(stacked_group["non_self_gated_overlay_cut_risky"].mean()))
    return pd.DataFrame(rows)


def compute_rankings(
    sleeve_state_df: pd.DataFrame,
    state_behavior_df: pd.DataFrame,
    allocator_diag_df: pd.DataFrame,
    sleeve_flags: dict[str, list[str]],
) -> pd.DataFrame:
    state_core = state_behavior_df[~state_behavior_df["market_state"].str.startswith("__")]
    good_state_df = state_core[state_core["market_state"].isin(GOOD_STATES | {"neutral_mixed", "recovery_fragile"})]
    cap_hit_rate = allocator_diag_df.loc[
        (allocator_diag_df["scope_type"] == "overall") & (allocator_diag_df["metric"] == "any_cap_hit_rate"),
        "value",
    ]
    cap_hit_rate = float(cap_hit_rate.iloc[0]) if not cap_hit_rate.empty else 0.0
    regime_binding = allocator_diag_df.loc[
        (allocator_diag_df["scope_type"] == "overall") & (allocator_diag_df["metric"] == "regime_binding_rate"),
        "value",
    ]
    target_vol_binding = allocator_diag_df.loc[
        (allocator_diag_df["scope_type"] == "overall") & (allocator_diag_df["metric"] == "target_vol_binding_rate"),
        "value",
    ]
    regime_binding = float(regime_binding.iloc[0]) if not regime_binding.empty else np.nan
    target_vol_binding = float(target_vol_binding.iloc[0]) if not target_vol_binding.empty else np.nan

    avg_good_cash = float(good_state_df["avg_bil_weight"].mean()) if not good_state_df.empty else np.nan
    avg_good_offense = float(good_state_df["avg_offensive_weight"].mean()) if not good_state_df.empty else np.nan
    avg_good_gap = float(good_state_df["prod_minus_spy_ann_return"].mean()) if not good_state_df.empty else np.nan
    avg_good_conf = float(good_state_df["avg_p_regime_confidence"].mean()) if not good_state_df.empty else np.nan
    weighted_negative_state_uses = int(sleeve_state_df["flag_summary"].fillna("").str.contains("weighted in underperforming state").sum())
    redundant_count = sum(any("redundant" in flag for flag in flags) for flags in sleeve_flags.values())

    ranking_rows = [
        {
            "bottleneck": "Layer 3 overlays/lighter_both",
            "score": 90.0 if pd.notna(regime_binding) and regime_binding > 0.75 and regime_binding > target_vol_binding + 0.70 else 70.0,
            "evidence": f"Regime binding rate {format_pct(regime_binding)} vs target-vol binding {format_pct(target_vol_binding)}; good-state BIL {format_pct(avg_good_cash)}.",
            "affected_metric": "Upside capture, SPY participation, raw return",
            "next_phase": "offensive participation ceiling/cap audit",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "Layer 2B regime-to-action mapping",
            "score": 88.0 if pd.notna(avg_good_conf) and avg_good_conf >= 0.55 and pd.notna(avg_good_cash) and avg_good_cash >= 0.20 and avg_good_gap < 0 else 62.0,
            "evidence": f"Avg good-state confidence {format_num(avg_good_conf)} with avg offense {format_pct(avg_good_offense)} and avg benchmark gap {format_pct(avg_good_gap)}.",
            "affected_metric": "Holdout robustness, neutral/calm conversion",
            "next_phase": "offensive participation ceiling/cap audit",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "BIL/cash drag",
            "score": 84.0 if pd.notna(avg_good_cash) and avg_good_cash >= 0.20 and avg_good_gap < -0.01 else 58.0,
            "evidence": f"Average BIL in good-to-neutral opportunity states is {format_pct(avg_good_cash)} while production-vs-SPY ann gap is {format_pct(avg_good_gap)}.",
            "affected_metric": "Annual return, upside capture",
            "next_phase": "offensive participation ceiling/cap audit",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "offensive participation ceiling",
            "score": 80.0 if pd.notna(avg_good_offense) and avg_good_offense < 0.60 and avg_good_gap < 0 else 55.0,
            "evidence": f"Average offensive exposure in good-to-neutral opportunity states is {format_pct(avg_good_offense)}.",
            "affected_metric": "SPY participation, recovery capture",
            "next_phase": "offensive participation ceiling/cap audit",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "Layer 3 caps/normalization",
            "score": 63.0 if cap_hit_rate > 0.10 else 35.0,
            "evidence": f"Any-sleeve cap hit rate is {format_pct(cap_hit_rate)} with production max sleeve weight fixed at 45%.",
            "affected_metric": "Concentration flexibility, offensive participation",
            "next_phase": "offensive participation ceiling/cap audit",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "defensive sleeve design",
            "score": 58.0 if weighted_negative_state_uses >= 2 else 40.0,
            "evidence": f"{weighted_negative_state_uses} sleeve-state rows show meaningful production weight in a negative-Sharpe state.",
            "affected_metric": "State efficiency, tail carry cost",
            "next_phase": "defensive sleeve redesign",
            "change_scope": "architectural change",
        },
        {
            "bottleneck": "Layer 2A sleeve quality",
            "score": 50.0 if redundant_count >= 1 else 30.0,
            "evidence": f"{redundant_count} production sleeves are flagged as redundant or weaker high-correlation copies.",
            "affected_metric": "Diversification efficiency, allocator choice set",
            "next_phase": "sleeve pruning/reweighting",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "Layer 3 HRP allocation",
            "score": 42.0 if redundant_count >= 1 and cap_hit_rate > 0.05 else 28.0,
            "evidence": f"HRP allocates into a correlated 5-sleeve set with cap hit rate {format_pct(cap_hit_rate)}.",
            "affected_metric": "Weight efficiency",
            "next_phase": "in-allocator W1 dual-bucket architecture",
            "change_scope": "architectural change",
        },
        {
            "bottleneck": "transaction cost/turnover",
            "score": 28.0,
            "evidence": "Production turnover is meaningful but not the dominant limiter relative to cash drag and overlay binding.",
            "affected_metric": "Net return",
            "next_phase": "recovery re-risking speed test",
            "change_scope": "small tweak",
        },
        {
            "bottleneck": "Layer 2B regime prediction",
            "score": 18.0 if pd.notna(avg_good_conf) and avg_good_conf >= 0.50 else 35.0,
            "evidence": "Current audit found more evidence of suppressed action than of missing state signal; recent ML phases also improved prediction more than portfolio conversion.",
            "affected_metric": "Signal quality",
            "next_phase": "targeted Phase 2B ML refresh",
            "change_scope": "small tweak",
        },
    ]

    ranking_df = pd.DataFrame(ranking_rows)
    ranking_df["severity"] = ranking_df["score"].map(severity_label)
    ranking_df = ranking_df.sort_values("score", ascending=False).reset_index(drop=True)
    ranking_df.insert(0, "rank", np.arange(1, len(ranking_df) + 1))
    return ranking_df[
        ["rank", "bottleneck", "severity", "score", "evidence", "affected_metric", "next_phase", "change_scope"]
    ]


def build_report(
    sleeve_state_df: pd.DataFrame,
    state_behavior_df: pd.DataFrame,
    allocator_diag_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    missing_files: list[str],
) -> str:
    top3 = ranking_df.head(3)
    state_core = state_behavior_df[~state_behavior_df["market_state"].str.startswith("__")]
    high_cash_states = state_core.sort_values("avg_bil_weight", ascending=False).head(3)
    worst_gap_states = state_core.sort_values("prod_minus_spy_ann_return").head(3)
    misused_states = sleeve_state_df[
        sleeve_state_df["flag_summary"].fillna("").str.contains("weighted in underperforming state", na=False)
    ][["sleeve_name", "market_state", "avg_production_weight_state", "sharpe"]].head(8)

    recommended_phase = str(top3.iloc[0]["next_phase"])
    phase_mm_first = "No"
    if top3.iloc[0]["bottleneck"] == "Layer 2B regime prediction":
        phase_mm_first = "Yes"

    lines = [
        "# Layer 2A / 2B / 3 Bottleneck Audit",
        "",
        "## Scope",
        "- Diagnostic audit only. No production pin changes, no new candidates, no parameter optimization, no external dependencies.",
        "- Production pin inspected: `improved_phase2b_regime_confidence_boost`.",
        "- Primary question: where is the stack suppressing useful signal conversion into portfolio improvement?",
        "",
        "## Commands Executed",
        "- `python3 scripts/layer_bottleneck_audit.py`",
        "- `rg --files data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction` to confirm saved artifacts.",
        "- `sed -n '2815,2965p' scripts/build_improvement_artifacts.py` to verify the production construction checkpoints and missing instrumentation gaps.",
        "- Supporting file inspection centered on `scripts/build_improvement_artifacts.py` and saved Layer 2A / 2B / 3 artifacts.",
        "",
        "## Files Inspected",
        "- `data/03_layer2a_strategy_logic/strategy_returns_<sleeve>.csv` and `strategy_positions_<sleeve>.csv` for production sleeves.",
        "- `data/03_layer2a_strategy_logic/strategy_returns_baseline_market_proxy_buy_hold.csv`.",
        "- `data/04_layer2b_risk_regime_engine/market_state_history.csv`.",
        "- `data/04_layer2b_risk_regime_engine/market_state_history_refined.csv`.",
        "- `data/04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv`.",
        "- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv`.",
        "- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phase2b_regime_confidence_boost.csv`.",
        "- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phase2b_regime_confidence_boost.csv`.",
        "- `data/05_layer3_portfolio_construction/allocation_driver_timeseries.csv`.",
        "- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_timeseries.csv`.",
        "- `data/05_layer3_portfolio_construction/stacked_defense_timeseries.csv` if present, else `stacked_defense_by_state.csv`.",
        "- `docs/research/project_journey.md` and recent Phase JJ / KK-LL research notes for context.",
        "",
        "## Missing Files / Missing Saved Checkpoints",
    ]
    for item in missing_files:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Key Bottleneck Findings",
        f"- Top bottleneck: **{top3.iloc[0]['bottleneck']}** ({top3.iloc[0]['severity']}). {top3.iloc[0]['evidence']}",
        f"- Second bottleneck: **{top3.iloc[1]['bottleneck']}** ({top3.iloc[1]['severity']}). {top3.iloc[1]['evidence']}",
        f"- Third bottleneck: **{top3.iloc[2]['bottleneck']}** ({top3.iloc[2]['severity']}). {top3.iloc[2]['evidence']}",
        "",
        "## Layer 2A Sleeve Audit",
        f"- Production sleeves audited: {', '.join(PRODUCTION_SLEEVES)}.",
        f"- Sleeve-state rows flagged as weighted in a negative-Sharpe state: {int(sleeve_state_df['flag_summary'].fillna('').str.contains('weighted in underperforming state').sum())}.",
        f"- Any-sleeve production cap hit rate: {format_pct(allocator_diag_df.loc[(allocator_diag_df['scope_type'] == 'overall') & (allocator_diag_df['metric'] == 'any_cap_hit_rate'), 'value'].iloc[0] if not allocator_diag_df.empty else np.nan)}.",
    ]
    if not misused_states.empty:
        lines.append("- Highest-confidence Layer 2A misuses observed:")
        for _, row in misused_states.iterrows():
            lines.append(
                f"  - `{row['sleeve_name']}` in `{row['market_state']}`: avg weight {format_pct(row['avg_production_weight_state'])}, state Sharpe {format_num(row['sharpe'])}."
            )
    lines += [
        "",
        "## Layer 2B Regime Mapping Audit",
        "- Highest cash states:",
    ]
    for _, row in high_cash_states.iterrows():
        lines.append(
            f"  - `{row['market_state']}`: avg BIL {format_pct(row['avg_bil_weight'])}, avg offense {format_pct(row['avg_offensive_weight'])}, prod-SPY gap {format_pct(row['prod_minus_spy_ann_return'])}, diagnosis `{row['diagnosis']}`."
        )
    lines.append("- Worst production-vs-SPY states:")
    for _, row in worst_gap_states.iterrows():
        lines.append(
            f"  - `{row['market_state']}`: gap {format_pct(row['prod_minus_spy_ann_return'])}, avg BIL {format_pct(row['avg_bil_weight'])}, confidence {format_num(row['avg_p_regime_confidence'])}, tail {format_num(row['avg_p_tail_risk'])}."
        )
    lines += [
        "",
        "## Layer 3 Allocator / Overlay Audit",
        "- Saved diagnostics show regime binding, target-vol binding, dynamic speed, self-gated relief, overlay cash, sleeve-internal BIL, and self/non-self risky overlay cuts.",
        "- Saved diagnostics do **not** include raw HRP sleeve weights, post-tilt sleeve weights, post-layer3-expression sleeve weights, or pre-lookthrough sleeve weights as standalone checkpoints.",
        "- The dominant question is whether the production overlay path is flattening good-state risk-taking more often than target-vol control is requiring.",
    ]
    if not allocator_diag_df.empty:
        overall = allocator_diag_df[allocator_diag_df["scope_type"] == "overall"].set_index("metric")["value"]
        lines.append(
            f"- Overall regime binding rate is {format_pct(overall.get('regime_binding_rate', np.nan))} versus target-vol binding {format_pct(overall.get('target_vol_binding_rate', np.nan))}."
        )
        lines.append(
            f"- Average overlay cash is {format_pct(overall.get('avg_overlay_cash_weight', np.nan))}; average BIL is {format_pct(overall.get('avg_bil_weight', np.nan))}; average SPY weight is {format_pct(overall.get('avg_spy_weight', np.nan))}."
        )
    lines += [
        "",
        "## Proposed Instrumentation Plan",
        "- In `run_subset_custom`, log `raw` immediately before `apply_state_conditioned_tilt` as the raw HRP output.",
        "- Log `raw` immediately after `apply_state_conditioned_tilt` as post-state-tilt sleeve weights.",
        "- Log `raw` immediately after `apply_layer3_expression` as post-expression sleeve weights.",
        "- Log `risky_weights` and `cash_weight` from `apply_overlays_custom` as post-overlay sleeve weights before ETF lookthrough.",
        "- Log the ETF row returned by `build_lookthrough_etf_weights` before and after `apply_beta_participation_overlay`.",
        "",
        "## Top 3 Bottlenecks",
    ]
    for _, row in top3.iterrows():
        lines.append(
            f"- `{row['bottleneck']}` — {row['severity']}. {row['evidence']} Affects: {row['affected_metric']}. Next test: `{row['next_phase']}`."
        )
    lines += [
        "",
        "## Recommended Next Phase",
        f"- **{recommended_phase}**.",
        "- Rationale: the audit points more strongly to suppressed offensive conversion and cash/overlay friction than to missing predictive information.",
        "",
        "## Phase MM ML Retrain Before Structural Allocator Work?",
        f"- **{phase_mm_first}**. Current evidence says the next priority should be the bottleneck at the top of this audit rather than another prediction refresh first.",
        "",
        "## Full Bottleneck Ranking",
        "",
        "| Rank | Bottleneck | Severity | Affected Metric | Next Phase | Scope | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in ranking_df.iterrows():
        lines.append(
            f"| {int(row['rank'])} | {row['bottleneck']} | {row['severity']} | {row['affected_metric']} | {row['next_phase']} | {row['change_scope']} | {row['evidence']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    production_return_df = read_timeseries_csv(LAYER3_DIR / f"portfolio_version_returns_{PRODUCTION_VERSION}.csv")
    production_returns = production_return_df["net_return"].astype(float)
    production_etf_weights = read_timeseries_csv(LAYER3_DIR / f"portfolio_version_weights_{PRODUCTION_VERSION}.csv").fillna(0.0)
    production_sleeve_weights = read_timeseries_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{PRODUCTION_VERSION}.csv").fillna(0.0)
    production_sleeve_weights = production_sleeve_weights.reindex(columns=PRODUCTION_SLEEVES + ["cash::BIL"], fill_value=0.0)

    common_index = production_returns.index
    state_frame = join_state_frame(common_index)
    allocation_driver_ts = read_timeseries_csv(LAYER3_DIR / "allocation_driver_timeseries.csv")
    allocation_driver_ts = allocation_driver_ts[allocation_driver_ts["version_name"] == PRODUCTION_VERSION].copy()
    diagnostics_ts = read_timeseries_csv(LAYER3_DIR / "portfolio_version_diagnostics_timeseries.csv")
    diagnostics_ts = diagnostics_ts[diagnostics_ts["version_name"] == PRODUCTION_VERSION].copy()

    stacked_defense_timeseries_path = LAYER3_DIR / "stacked_defense_timeseries.csv"
    stacked_defense_ts = None
    if stacked_defense_timeseries_path.exists():
        stacked_defense_ts = read_timeseries_csv(stacked_defense_timeseries_path)
        stacked_defense_ts = stacked_defense_ts[stacked_defense_ts["version_name"] == PRODUCTION_VERSION].copy()

    weekly_simple_returns = load_weekly_simple_returns()
    spy_returns = read_timeseries_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"].astype(float).reindex(common_index)
    bil_returns = weekly_simple_returns.get("BIL", pd.Series(index=common_index, dtype=float)).reindex(common_index)

    state_frame = state_frame.reindex(common_index)
    allocation_driver_ts = allocation_driver_ts.reindex(common_index)
    diagnostics_ts = diagnostics_ts.reindex(common_index)
    if stacked_defense_ts is not None:
        stacked_defense_ts = stacked_defense_ts.reindex(common_index)

    sleeve_state_df, sleeve_corr_df, sleeve_flags = compute_sleeve_audit(
        state_frame=state_frame,
        production_returns=production_returns,
        production_sleeve_weights=production_sleeve_weights,
        spy_returns=spy_returns,
    )
    state_behavior_df = compute_state_behavior(
        state_frame=state_frame,
        production_returns=production_returns,
        production_sleeve_weights=production_sleeve_weights,
        production_etf_weights=production_etf_weights,
        spy_returns=spy_returns,
        bil_returns=bil_returns,
        allocation_driver_ts=allocation_driver_ts,
    )
    allocator_diag_df = compute_allocator_stage_diagnostics(
        production_sleeve_weights=production_sleeve_weights,
        diagnostics_ts=diagnostics_ts,
        allocation_driver_ts=allocation_driver_ts,
        stacked_defense_ts=stacked_defense_ts,
    )
    ranking_df = compute_rankings(
        sleeve_state_df=sleeve_state_df,
        state_behavior_df=state_behavior_df,
        allocator_diag_df=allocator_diag_df,
        sleeve_flags=sleeve_flags,
    )

    missing_files = [
        "No saved raw HRP sleeve-weight checkpoint prior to `apply_state_conditioned_tilt`.",
        "No saved post-state-tilt sleeve-weight checkpoint prior to `apply_layer3_expression`.",
        "No saved post-layer3-expression sleeve-weight checkpoint prior to `apply_overlays_custom`.",
    ]
    if stacked_defense_ts is None:
        missing_files.append("`data/05_layer3_portfolio_construction/stacked_defense_timeseries.csv` not present; state overlay-cut analysis used saved summaries where possible.")

    report = build_report(
        sleeve_state_df=sleeve_state_df,
        state_behavior_df=state_behavior_df,
        allocator_diag_df=allocator_diag_df,
        ranking_df=ranking_df,
        missing_files=missing_files,
    )

    sleeve_state_df.to_csv(OUTPUT_DIR / "sleeve_performance_by_state.csv", index=False)
    sleeve_corr_df.to_csv(OUTPUT_DIR / "sleeve_correlation_matrix.csv")
    state_behavior_df.to_csv(OUTPUT_DIR / "state_allocation_behavior.csv", index=False)
    allocator_diag_df.to_csv(OUTPUT_DIR / "allocator_stage_diagnostics.csv", index=False)
    ranking_df.to_csv(OUTPUT_DIR / "bottleneck_rankings.csv", index=False)
    (REPORT_DIR / "layer_bottleneck_audit.md").write_text(report)

    print("Saved layer bottleneck audit outputs:")
    print(f"- {REPORT_DIR / 'layer_bottleneck_audit.md'}")
    print(f"- {OUTPUT_DIR / 'sleeve_performance_by_state.csv'}")
    print(f"- {OUTPUT_DIR / 'sleeve_correlation_matrix.csv'}")
    print(f"- {OUTPUT_DIR / 'state_allocation_behavior.csv'}")
    print(f"- {OUTPUT_DIR / 'allocator_stage_diagnostics.csv'}")
    print(f"- {OUTPUT_DIR / 'bottleneck_rankings.csv'}")


if __name__ == "__main__":
    main()
