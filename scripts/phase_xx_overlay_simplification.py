from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase_ww_recovery_overlay_rescue import (
    PRODUCTION_NAME,
    SHADOW_NAME,
    TT_REFERENCE_NAME,
    UU_REFERENCE_NAME,
    VV_REFERENCE_NAME,
    STATE_ORDER,
    TARGET_RECOVERY_STATES,
    add_state_labels,
    annual_return,
    avg_etf_exposures,
    bucket_series,
    build_versions,
    compute_capture,
    cvar_5,
    load_frame,
    load_simple_csv,
    max_drawdown,
    sharpe_ratio,
    state_summary_for_version,
    summary_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
CHECKPOINT_DIR = ROOT / "data" / "research" / "allocator_checkpoints"
RESEARCH_DIR = ROOT / "data" / "research" / "phase_xx_overlay_simplification"

WW_REFERENCE_NAME = "improved_phaseww_confirmed_only_lighter_both"
XX_CANDIDATES = [
    "improved_phasexx_guardrail_only_overlay",
    "improved_phasexx_guardrail_overlay_fragile_floor",
    "improved_phasexx_recovery_neutral_overlay_simplified",
    "improved_phasexx_conservative_hybrid_overlay",
]
INTENDED_CASH_BUDGETS: dict[str, dict[str, float]] = {
    PRODUCTION_NAME: {},
    TT_REFERENCE_NAME: {"recovery_confirmed": 0.060, "recovery_fragile": 0.100},
    UU_REFERENCE_NAME: {"recovery_confirmed": 0.052, "recovery_fragile": 0.112},
    VV_REFERENCE_NAME: {
        "neutral_healthy_proxy": 0.135,
        "recovery_confirmed": 0.060,
        "recovery_fragile": 0.100,
    },
    WW_REFERENCE_NAME: {
        "recovery_confirmed": 0.045,
    },
    "improved_phasexx_guardrail_only_overlay": {
        "recovery_confirmed": 0.060,
        "recovery_fragile": 0.100,
    },
    "improved_phasexx_guardrail_overlay_fragile_floor": {
        "recovery_confirmed": 0.055,
        "recovery_fragile": 0.120,
    },
    "improved_phasexx_recovery_neutral_overlay_simplified": {
        "neutral_healthy_proxy": 0.130,
        "recovery_confirmed": 0.055,
        "recovery_fragile": 0.115,
    },
    "improved_phasexx_conservative_hybrid_overlay": {
        "neutral_healthy_proxy": 0.130,
        "recovery_confirmed": 0.055,
        "recovery_fragile": 0.115,
    },
}


def intended_cash_budget(version_name: str, state_name: str, stage1_cash_budget: float) -> float:
    return float(INTENDED_CASH_BUDGETS.get(version_name, {}).get(state_name, stage1_cash_budget))


def weekly_budget_table(version_name: str, state_df: pd.DataFrame, diag_ts: pd.DataFrame, stacked_ts: pd.DataFrame) -> pd.DataFrame:
    stage1 = load_frame(CHECKPOINT_DIR / f"{version_name}__post_layer3_expression_sleeve_weights.csv").reindex(state_df.index).fillna(0.0)
    post_overlay = load_frame(CHECKPOINT_DIR / f"{version_name}__post_overlay_pre_lookthrough_sleeve_weights.csv").reindex(state_df.index).fillna(0.0)
    final_etf = load_frame(CHECKPOINT_DIR / f"{version_name}__final_etf_weights.csv").reindex(state_df.index).fillna(0.0)

    vdiag = diag_ts[diag_ts["version_name"] == version_name].copy()
    if not vdiag.empty:
        vdiag["Date"] = pd.to_datetime(vdiag["Date"]).dt.tz_localize(None)
        vdiag = vdiag.set_index("Date").reindex(state_df.index)
    else:
        vdiag = pd.DataFrame(index=state_df.index)

    vstack = stacked_ts[stacked_ts["version_name"] == version_name].copy()
    if not vstack.empty:
        vstack["Date"] = pd.to_datetime(vstack["Date"]).dt.tz_localize(None)
        vstack = vstack.set_index("Date").reindex(state_df.index)
    else:
        vstack = pd.DataFrame(index=state_df.index)

    def numeric_col(frame: pd.DataFrame, col: str, default: float = np.nan) -> pd.Series:
        if isinstance(frame, pd.DataFrame) and col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce")
        return pd.Series(default, index=state_df.index, dtype=float)

    weekly = pd.DataFrame(index=state_df.index)
    weekly["state"] = state_df["state_label"]
    weekly["stage1_cash_budget"] = stage1.get("cash::BIL", pd.Series(0.0, index=weekly.index))
    weekly["stage1_risky_budget"] = 1.0 - weekly["stage1_cash_budget"]
    weekly["post_overlay_cash_budget"] = post_overlay.get("cash::BIL", pd.Series(0.0, index=weekly.index))
    weekly["post_overlay_risky_budget"] = 1.0 - weekly["post_overlay_cash_budget"]
    weekly["final_etf_cash_budget"] = final_etf.get("BIL", pd.Series(0.0, index=weekly.index))
    weekly["final_etf_risky_budget"] = 1.0 - weekly["final_etf_cash_budget"]
    weekly["target_vol_multiplier"] = numeric_col(vdiag, "target_vol_multiplier")
    weekly["target_vol_binding"] = numeric_col(vdiag, "target_vol_binding", 0.0).fillna(0.0)
    weekly["regime_binding"] = numeric_col(vdiag, "regime_binding", 0.0).fillna(0.0)
    weekly["self_gated_overlay_cut_risky"] = numeric_col(vstack, "self_gated_overlay_cut_risky", 0.0).fillna(0.0)
    weekly["non_self_gated_overlay_cut_risky"] = numeric_col(vstack, "non_self_gated_overlay_cut_risky", 0.0).fillna(0.0)
    weekly["overlay_cash_weight"] = numeric_col(vstack, "overlay_cash_weight", 0.0).fillna(0.0)
    weekly["intended_cash_budget"] = [
        intended_cash_budget(version_name, state_name, float(stage1_cash))
        for state_name, stage1_cash in zip(weekly["state"], weekly["stage1_cash_budget"])
    ]
    weekly["intended_risky_budget"] = 1.0 - weekly["intended_cash_budget"]
    weekly["overlay_cash_added"] = weekly["post_overlay_cash_budget"] - weekly["stage1_cash_budget"]
    weekly["overlay_absorption"] = weekly["stage1_risky_budget"] - weekly["post_overlay_risky_budget"]
    weekly["lookthrough_absorption"] = weekly["post_overlay_risky_budget"] - weekly["final_etf_risky_budget"]
    weekly["total_absorption"] = weekly["stage1_risky_budget"] - weekly["final_etf_risky_budget"]
    weekly["target_vol_required_cash"] = np.maximum(0.0, 1.0 - weekly["target_vol_multiplier"].fillna(1.0))
    weekly["target_vol_active"] = weekly["target_vol_binding"] > 0.0
    weekly["panic_guardrail_active"] = weekly["state"].eq("stressed_panic")
    weekly["panic_guardrail_cash"] = np.where(weekly["panic_guardrail_active"], weekly["post_overlay_cash_budget"], 0.0)
    weekly["guardrail_cash_need"] = weekly[["target_vol_required_cash", "panic_guardrail_cash"]].max(axis=1)
    weekly["recovery_regime_relief_cash"] = np.where(
        weekly["state"].isin(["recovery_confirmed", "recovery_fragile", "neutral_healthy_proxy"]),
        np.maximum(0.0, weekly["post_overlay_cash_budget"] - np.maximum(weekly["guardrail_cash_need"], weekly["intended_cash_budget"])),
        0.0,
    )
    weekly["guardrail_cash_added"] = np.minimum(weekly["post_overlay_cash_budget"], np.maximum(weekly["guardrail_cash_need"], weekly["intended_cash_budget"]))
    weekly["duplicated_cash_over_intended"] = np.maximum(0.0, weekly["post_overlay_cash_budget"] - weekly["intended_cash_budget"])
    weekly["excess_cash_not_guardrail"] = np.maximum(0.0, weekly["post_overlay_cash_budget"] - np.maximum(weekly["guardrail_cash_need"], weekly["intended_cash_budget"]))
    weekly["target_vol_shortfall"] = np.where(
        weekly["target_vol_active"],
        np.maximum(0.0, weekly["target_vol_required_cash"] - weekly["post_overlay_cash_budget"]),
        0.0,
    )
    return weekly


def state_budget_absorption(version_name: str, weekly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state_name in STATE_ORDER:
        grp = weekly[weekly["state"] == state_name]
        if grp.empty:
            continue
        self_cut = float(grp["self_gated_overlay_cut_risky"].mean())
        nonself_cut = float(grp["non_self_gated_overlay_cut_risky"].mean())
        rows.append(
            {
                "name": version_name,
                "state": state_name,
                "n_weeks": int(len(grp)),
                "stage1_risky_budget": float(grp["stage1_risky_budget"].mean()),
                "stage1_cash_budget": float(grp["stage1_cash_budget"].mean()),
                "intended_risky_budget": float(grp["intended_risky_budget"].mean()),
                "intended_cash_budget": float(grp["intended_cash_budget"].mean()),
                "post_overlay_risky_budget": float(grp["post_overlay_risky_budget"].mean()),
                "post_overlay_cash_budget": float(grp["post_overlay_cash_budget"].mean()),
                "final_etf_risky_budget": float(grp["final_etf_risky_budget"].mean()),
                "final_etf_cash_budget": float(grp["final_etf_cash_budget"].mean()),
                "overlay_cash_added": float(grp["overlay_cash_added"].mean()),
                "overlay_absorption": float(grp["overlay_absorption"].mean()),
                "lookthrough_absorption": float(grp["lookthrough_absorption"].mean()),
                "total_absorption": float(grp["total_absorption"].mean()),
                "duplicated_cash_over_intended": float(grp["duplicated_cash_over_intended"].mean()),
                "recovery_regime_relief_cash": float(grp["recovery_regime_relief_cash"].mean()),
                "guardrail_cash_added": float(grp["guardrail_cash_added"].mean()),
                "excess_cash_not_guardrail": float(grp["excess_cash_not_guardrail"].mean()),
                "target_vol_active_share": float(grp["target_vol_active"].mean()),
                "panic_guardrail_active_share": float(grp["panic_guardrail_active"].mean()),
                "avg_target_vol_required_cash": float(grp["target_vol_required_cash"].mean()),
                "target_vol_shortfall_avg": float(grp["target_vol_shortfall"].mean()),
                "avg_self_gated_overlay_cut_risky": self_cut,
                "avg_non_self_gated_overlay_cut_risky": nonself_cut,
            }
        )
    return pd.DataFrame(rows)


def assemble_results(state_df: pd.DataFrame, comparison_names: list[str], candidate_names: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    diag_ts = load_simple_csv(LAYER3_DIR / "portfolio_version_diagnostics_timeseries.csv")
    stacked_ts = load_simple_csv(LAYER3_DIR / "stacked_defense_timeseries.csv")
    weekly_tables = {
        name: weekly_budget_table(name, state_df, diag_ts, stacked_ts)
        for name in comparison_names
    }
    absorption_df = pd.concat([state_budget_absorption(name, weekly_tables[name]) for name in comparison_names], ignore_index=True)

    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    weekly_returns.index = pd.to_datetime(weekly_returns.index).tz_localize(None)
    spy_returns = weekly_returns["SPY"].reindex(state_df.index).fillna(0.0)
    holdout_start = pd.Timestamp("2024-04-19")
    recovery_mask = state_df["state_label"].isin(["recovery_confirmed", "recovery_fragile"])

    metrics_rows = []
    state_frames = []
    for version_name in comparison_names:
        returns_df = load_frame(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv").reindex(state_df.index).fillna(0.0)
        sleeve_df = load_frame(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv").reindex(state_df.index).fillna(0.0)
        etf_df = load_frame(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv").reindex(state_df.index).fillna(0.0)
        net = returns_df["net_return"]
        holdout = net.loc[net.index >= holdout_start]
        bucket_df = bucket_series(sleeve_df)
        exposures = avg_etf_exposures(etf_df)
        metrics_rows.append(
            {
                "name": version_name,
                **summary_metrics(net),
                "avg_turnover": float(returns_df["turnover"].fillna(0.0).mean()) if "turnover" in returns_df.columns else np.nan,
                **exposures,
                "holdout_ann_return": annual_return(holdout),
                "holdout_sharpe": sharpe_ratio(holdout),
                "recovery_capture": compute_capture(net, spy_returns.reindex(net.index).fillna(0.0), recovery_mask.reindex(net.index).fillna(False)),
                "avg_bucket_offense": float(bucket_df["offense"].mean()),
                "avg_bucket_defense": float(bucket_df["defense"].mean()),
                "avg_bucket_composite": float(bucket_df["composite"].mean()),
                "avg_bucket_cash": float(bucket_df["cash"].mean()),
            }
        )
        state_frames.append(state_summary_for_version(version_name, returns_df, sleeve_df, etf_df, state_df))

    metrics_df = pd.DataFrame(metrics_rows)
    bases = {
        "prod": metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0],
        "shadow": metrics_df[metrics_df["name"] == SHADOW_NAME].iloc[0],
        "vv": metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0],
        "ww": metrics_df[metrics_df["name"] == WW_REFERENCE_NAME].iloc[0],
    }
    for base_name, base_row in bases.items():
        for col in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_SPY", "avg_offense", "avg_defense", "avg_cash", "avg_bucket_composite"]:
            metrics_df[f"{col}_delta_vs_{base_name}"] = metrics_df[col] - float(base_row[col])

    state_summary_df = pd.concat(state_frames, ignore_index=True)
    prod_state = state_summary_df[state_summary_df["name"] == PRODUCTION_NAME].set_index("state")
    state_summary_df["ann_return_delta_vs_prod"] = state_summary_df.apply(
        lambda row: float(row["ann_return"] - prod_state.at[row["state"], "ann_return"]) if row["state"] in prod_state.index else np.nan,
        axis=1,
    )
    state_summary_df["sharpe_delta_vs_prod"] = state_summary_df.apply(
        lambda row: float(row["sharpe"] - prod_state.at[row["state"], "sharpe"]) if row["state"] in prod_state.index else np.nan,
        axis=1,
    )

    candidate_diag_rows = []
    prod_abs = absorption_df[absorption_df["name"] == PRODUCTION_NAME].set_index("state")
    vv_abs = absorption_df[absorption_df["name"] == VV_REFERENCE_NAME].set_index("state")
    ww_abs = absorption_df[absorption_df["name"] == WW_REFERENCE_NAME].set_index("state")
    for candidate_name in candidate_names:
        cand_abs = absorption_df[absorption_df["name"] == candidate_name]
        for _, row in cand_abs.iterrows():
            state_name = row["state"]
            candidate_diag_rows.append(
                {
                    **row.to_dict(),
                    "duplicated_cash_reduction_vs_prod": float(prod_abs.at[state_name, "duplicated_cash_over_intended"] - row["duplicated_cash_over_intended"]) if state_name in prod_abs.index else np.nan,
                    "duplicated_cash_reduction_vs_vv": float(vv_abs.at[state_name, "duplicated_cash_over_intended"] - row["duplicated_cash_over_intended"]) if state_name in vv_abs.index else np.nan,
                    "duplicated_cash_reduction_vs_ww": float(ww_abs.at[state_name, "duplicated_cash_over_intended"] - row["duplicated_cash_over_intended"]) if state_name in ww_abs.index else np.nan,
                    "recovery_regime_relief_cash_reduction_vs_prod": float(prod_abs.at[state_name, "recovery_regime_relief_cash"] - row["recovery_regime_relief_cash"]) if state_name in prod_abs.index else np.nan,
                    "excess_cash_reduction_vs_prod": float(prod_abs.at[state_name, "excess_cash_not_guardrail"] - row["excess_cash_not_guardrail"]) if state_name in prod_abs.index else np.nan,
                    "overlay_absorption_reduction_vs_prod": float(prod_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]) if state_name in prod_abs.index else np.nan,
                }
            )
    candidate_diag_df = pd.DataFrame(candidate_diag_rows)
    return metrics_df, state_summary_df, absorption_df, candidate_diag_df


def screen_candidate(row: pd.Series, prod_row: pd.Series, vv_row: pd.Series, state_summary_df: pd.DataFrame, candidate_diag_df: pd.DataFrame) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if float(row["ann_return_delta_vs_prod"]) < -0.0030:
        reasons.append("annual return drag > 0.30pp vs production")
    if float(row["sharpe_delta_vs_prod"]) < 0.0050:
        reasons.append("Sharpe improvement < 0.005 vs production")
    if float(row["sharpe_delta_vs_vv"]) <= 0.0:
        reasons.append("Sharpe does not improve vs VV best")
    if float(row["max_drawdown_delta_vs_prod"]) < -0.0050:
        reasons.append("max drawdown worse by > 0.5pp vs production")
    if float(row["cvar_5_delta_vs_prod"]) < -0.0005:
        reasons.append("CVaR worse by > 0.05pp vs production")
    if float(row["avg_turnover"]) > 1.10 * float(prod_row["avg_turnover"]):
        reasons.append("turnover > 1.10x production")
    if float(row["avg_SPY_delta_vs_prod"]) > 0.010 and float(row["sharpe_delta_vs_prod"]) < 0.007:
        reasons.append("improvement comes only from hidden SPY/beta")

    state_rows = state_summary_df[state_summary_df["name"] == row["name"]].set_index("state")
    prod_states = state_summary_df[state_summary_df["name"] == PRODUCTION_NAME].set_index("state")
    if "stressed_panic" in state_rows.index and "stressed_panic" in prod_states.index:
        if float(state_rows.at["stressed_panic", "sharpe"] - prod_states.at["stressed_panic", "sharpe"]) < -0.05:
            reasons.append("stressed_panic worsens materially")
    if "recovery_fragile" in state_rows.index and "recovery_fragile" in prod_states.index:
        if float(state_rows.at["recovery_fragile", "ann_return"] - prod_states.at["recovery_fragile", "ann_return"]) < -0.005:
            reasons.append("recovery_fragile worsens materially")

    targeted = candidate_diag_df[(candidate_diag_df["name"] == row["name"]) & (candidate_diag_df["state"].isin(TARGET_RECOVERY_STATES))]
    if targeted.empty or float(targeted["duplicated_cash_reduction_vs_prod"].mean()) <= 0.0:
        reasons.append("duplicated recovery cash is not reduced")
    if not targeted.empty and float(targeted["target_vol_shortfall_avg"].max()) > 0.001:
        reasons.append("target-vol guardrails are overridden unsafely")

    status = "PASS" if not reasons else "REJECT"
    return status, reasons


def choose_best(metrics_df: pd.DataFrame) -> str:
    subset = metrics_df[metrics_df["name"].isin(XX_CANDIDATES)].copy()
    subset = subset.sort_values(["sharpe_delta_vs_prod", "ann_return_delta_vs_prod", "sharpe"], ascending=False)
    return str(subset.iloc[0]["name"])


def main() -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    state_df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    state_df.index = pd.to_datetime(state_df.index).tz_localize(None)
    state_df = add_state_labels(state_df)

    reference_names = [
        PRODUCTION_NAME,
        SHADOW_NAME,
        TT_REFERENCE_NAME,
        UU_REFERENCE_NAME,
        VV_REFERENCE_NAME,
        WW_REFERENCE_NAME,
    ]
    build_versions(reference_names + XX_CANDIDATES)

    comparison_names = reference_names + XX_CANDIDATES
    metrics_df, state_summary_df, absorption_df, candidate_diag_df = assemble_results(state_df, comparison_names, XX_CANDIDATES)

    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    vv_row = metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0]
    selection_rows = []
    for candidate_name in XX_CANDIDATES:
        row = metrics_df[metrics_df["name"] == candidate_name].iloc[0]
        status, reasons = screen_candidate(row, prod_row, vv_row, state_summary_df, candidate_diag_df)
        targeted = candidate_diag_df[(candidate_diag_df["name"] == candidate_name) & (candidate_diag_df["state"].isin(TARGET_RECOVERY_STATES))]
        selection_rows.append(
            {
                "name": candidate_name,
                "status": status,
                "reasons": "; ".join(reasons),
                "targeted_duplicated_cash_reduction_vs_prod": float(targeted["duplicated_cash_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "targeted_overlay_absorption_reduction_vs_prod": float(targeted["overlay_absorption_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "targeted_regime_relief_cash_reduction_vs_prod": float(targeted["recovery_regime_relief_cash_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "sharpe_delta_vs_prod": float(row["sharpe_delta_vs_prod"]),
                "sharpe_delta_vs_vv": float(row["sharpe_delta_vs_vv"]),
                "ann_return_delta_vs_prod": float(row["ann_return_delta_vs_prod"]),
            }
        )
    selection_df = pd.DataFrame(selection_rows)

    cash_duplication = absorption_df[
        absorption_df["name"].isin([PRODUCTION_NAME, VV_REFERENCE_NAME, WW_REFERENCE_NAME] + XX_CANDIDATES)
    ][
        [
            "name",
            "state",
            "stage1_cash_budget",
            "intended_cash_budget",
            "post_overlay_cash_budget",
            "final_etf_cash_budget",
            "overlay_cash_added",
            "duplicated_cash_over_intended",
            "excess_cash_not_guardrail",
            "recovery_regime_relief_cash",
            "guardrail_cash_added",
        ]
    ].copy()
    cash_duplication.to_csv(RESEARCH_DIR / "phase_xx_cash_decision_duplication_by_state.csv", index=False)

    guardrail_vs_relief = absorption_df[
        absorption_df["name"].isin([PRODUCTION_NAME, VV_REFERENCE_NAME, WW_REFERENCE_NAME] + XX_CANDIDATES)
    ][
        [
            "name",
            "state",
            "target_vol_active_share",
            "panic_guardrail_active_share",
            "avg_target_vol_required_cash",
            "guardrail_cash_added",
            "recovery_regime_relief_cash",
            "duplicated_cash_over_intended",
            "excess_cash_not_guardrail",
            "target_vol_shortfall_avg",
        ]
    ].copy()
    guardrail_vs_relief.to_csv(RESEARCH_DIR / "phase_xx_guardrail_vs_regime_relief_cash.csv", index=False)

    overlay_diag = absorption_df[
        absorption_df["name"].isin([PRODUCTION_NAME, VV_REFERENCE_NAME, WW_REFERENCE_NAME] + XX_CANDIDATES)
    ].copy()
    overlay_diag.to_csv(RESEARCH_DIR / "phase_xx_overlay_simplification_diagnostics.csv", index=False)
    candidate_diag_df.to_csv(RESEARCH_DIR / "phase_xx_candidate_diagnostics.csv", index=False)

    metrics_df.to_csv(LAYER3_DIR / "phase_xx_candidate_metrics_full.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_xx_state_summary.csv", index=False)
    selection_df.to_csv(LAYER3_DIR / "phase_xx_selection_table.csv", index=False)
    with open(LAYER3_DIR / "phase_xx_protocol.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": "2026-04-30",
                "references": reference_names,
                "candidates": XX_CANDIDATES,
                "best_candidate": choose_best(metrics_df),
            },
            f,
            indent=2,
        )

    print(f"Phase XX complete. Best candidate: {choose_best(metrics_df)}", flush=True)


if __name__ == "__main__":
    main()
