from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase_ww_recovery_overlay_rescue import (
    PRODUCTION_NAME,
    SHADOW_NAME,
    VV_REFERENCE_NAME,
    STATE_ORDER,
    add_state_labels,
    annual_return,
    avg_etf_exposures,
    bucket_series,
    build_versions,
    calmar_ratio,
    compute_capture,
    cvar_5,
    load_frame,
    max_drawdown,
    sharpe_ratio,
    state_summary_for_version,
    summary_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
RESEARCH_DIR = ROOT / "data" / "research" / "phase_yy_composite_sleeve_decomposition"

XX_REFERENCE_NAME = "improved_phasexx_conservative_hybrid_overlay"
YY_CANDIDATES = [
    "improved_phaseyy_composite_cash_explicit",
    "improved_phaseyy_composite_offense_defense_split",
    "improved_phaseyy_decomposition_vv_reference",
    "improved_phaseyy_conservative_decomposition",
]

SOURCE_SLEEVE = "composite_regime_conditioned"
OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"

OFFENSE_ETFS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"]
DEFENSE_ETFS = ["HYG", "LQD", "GLD", "TLT"]
CASH_ETF = "BIL"
TARGET_STATES = {"recovery_confirmed", "recovery_fragile", "neutral_healthy_proxy"}

YY_BUCKET_MAP = {
    "dual_momentum_topn": "offense",
    "cta_trend_long_only": "offense",
    "composite_selective_signals": "offense",
    OFFENSE_COMPONENT: "offense",
    "taa_10m_sma": "defense",
    DEFENSE_COMPONENT: "defense",
    "cash::BIL": "cash",
}


def load_simple_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df


def bucket_series_yy(sleeve_weights: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=sleeve_weights.index)
    for bucket in ["offense", "defense", "cash"]:
        cols = [name for name, bucket_name in YY_BUCKET_MAP.items() if bucket_name == bucket and name in sleeve_weights.columns]
        out[bucket] = sleeve_weights.reindex(columns=cols).sum(axis=1) if cols else 0.0
    out["composite_family"] = sleeve_weights.reindex(
        columns=[c for c in [SOURCE_SLEEVE, OFFENSE_COMPONENT, DEFENSE_COMPONENT] if c in sleeve_weights.columns]
    ).sum(axis=1)
    return out


def build_component_positions(source_positions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    positions = source_positions.copy().fillna(0.0)
    offense_cols = [c for c in OFFENSE_ETFS if c in positions.columns]
    defense_cols = [c for c in DEFENSE_ETFS if c in positions.columns]
    all_cols = list(positions.columns)

    def normalize_subset(cols: list[str]) -> pd.DataFrame:
        out = pd.DataFrame(0.0, index=positions.index, columns=all_cols)
        subset_sum = positions.reindex(columns=cols).sum(axis=1)
        active = subset_sum > 1e-12
        if cols:
            out.loc[active, cols] = positions.loc[active, cols].div(subset_sum.loc[active], axis=0)
        out.loc[~active, CASH_ETF] = 1.0
        return out

    cash_positions = pd.DataFrame(0.0, index=positions.index, columns=all_cols)
    cash_positions[CASH_ETF] = 1.0
    return {
        OFFENSE_COMPONENT: normalize_subset(offense_cols),
        DEFENSE_COMPONENT: normalize_subset(defense_cols),
        CASH_COMPONENT: cash_positions,
    }


def approximate_component_returns(component_positions: dict[str, pd.DataFrame], weekly_returns: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=weekly_returns.index)
    aligned_returns = weekly_returns.reindex(index=weekly_returns.index, columns=weekly_returns.columns).fillna(0.0)
    for name, pos in component_positions.items():
        aligned_pos = pos.reindex(aligned_returns.index).reindex(columns=aligned_returns.columns).fillna(0.0)
        out[name] = (aligned_pos * aligned_returns).sum(axis=1)
    return out


def component_state_tables(
    state_df: pd.DataFrame,
    source_positions: pd.DataFrame,
    component_returns: pd.DataFrame,
    production_sleeve_weights: pd.DataFrame,
    production_returns: pd.Series,
    benchmark_returns: pd.Series,
    bil_returns: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows_weights: list[dict] = []
    rows_returns: list[dict] = []
    rows_diag: list[dict] = []

    offense_share = source_positions.reindex(columns=[c for c in OFFENSE_ETFS if c in source_positions.columns]).sum(axis=1)
    defense_share = source_positions.reindex(columns=[c for c in DEFENSE_ETFS if c in source_positions.columns]).sum(axis=1)
    cash_share = source_positions.get(CASH_ETF, pd.Series(0.0, index=source_positions.index))
    production_composite_weight = production_sleeve_weights.get(SOURCE_SLEEVE, pd.Series(0.0, index=source_positions.index)).reindex(source_positions.index).fillna(0.0)

    component_weight_frame = pd.DataFrame(
        {
            OFFENSE_COMPONENT: offense_share,
            DEFENSE_COMPONENT: defense_share,
            CASH_COMPONENT: cash_share,
        },
        index=source_positions.index,
    )

    for state_name in STATE_ORDER:
        mask = state_df["state_label"].eq(state_name)
        if int(mask.sum()) == 0:
            continue
        for comp_name in [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]:
            comp_ret = component_returns.loc[mask, comp_name]
            comp_weight = component_weight_frame.loc[mask, comp_name]
            approx_contrib = (production_composite_weight.loc[mask] * comp_weight * comp_ret).mean() * 52.0
            rows_weights.append(
                {
                    "state": state_name,
                    "component_name": comp_name,
                    "n_weeks": int(mask.sum()),
                    "avg_weight": float(comp_weight.mean()),
                }
            )
            rows_returns.append(
                {
                    "state": state_name,
                    "component_name": comp_name,
                    "n_weeks": int(mask.sum()),
                    "ann_return_approx": annual_return(comp_ret),
                    "ann_vol_approx": float(pd.Series(comp_ret).std(ddof=0) * np.sqrt(52.0)),
                    "sharpe_approx": sharpe_ratio(comp_ret),
                    "corr_with_production": float(pd.Series(comp_ret).corr(production_returns.loc[mask])),
                    "corr_with_spy": float(pd.Series(comp_ret).corr(benchmark_returns.loc[mask])),
                    "corr_with_bil": float(pd.Series(comp_ret).corr(bil_returns.loc[mask])) if bil_returns is not None else np.nan,
                    "approx_portfolio_contribution_ann": float(approx_contrib),
                }
            )
        rows_diag.append(
            {
                "state": state_name,
                "avg_offense_component_weight": float(offense_share.loc[mask].mean()),
                "avg_defense_component_weight": float(defense_share.loc[mask].mean()),
                "avg_cash_component_weight": float(cash_share.loc[mask].mean()),
                "offense_minus_cash": float(offense_share.loc[mask].mean() - cash_share.loc[mask].mean()),
                "defense_minus_cash": float(defense_share.loc[mask].mean() - cash_share.loc[mask].mean()),
                "cash_dominant": bool(float(cash_share.loc[mask].mean()) > max(float(offense_share.loc[mask].mean()), float(defense_share.loc[mask].mean()))),
            }
        )

    corr_rows = []
    for comp_name in [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]:
        series = component_returns[comp_name]
        corr_rows.append(
            {
                "component_name": comp_name,
                "corr_with_production_full": float(series.corr(production_returns)),
                "corr_with_spy_full": float(series.corr(benchmark_returns)),
                "corr_with_bil_full": float(series.corr(bil_returns)) if bil_returns is not None else np.nan,
            }
        )
    return (
        pd.DataFrame(rows_weights),
        pd.DataFrame(rows_returns),
        pd.DataFrame(corr_rows),
        pd.DataFrame(rows_diag),
    )


def hidden_composite_behavior(
    sleeve_weights: pd.DataFrame,
    source_positions: pd.DataFrame,
    component_positions: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    idx = sleeve_weights.index.intersection(source_positions.index)
    weights = sleeve_weights.reindex(idx).fillna(0.0)
    source = source_positions.reindex(idx).fillna(0.0)
    offense_pos = component_positions[OFFENSE_COMPONENT].reindex(idx).fillna(0.0)
    defense_pos = component_positions[DEFENSE_COMPONENT].reindex(idx).fillna(0.0)
    source_defense_share = source.reindex(columns=[c for c in DEFENSE_ETFS if c in source.columns]).sum(axis=1)
    out = pd.DataFrame(index=idx)
    out["hidden_composite_cash"] = weights.get(SOURCE_SLEEVE, pd.Series(0.0, index=idx)) * source.get(CASH_ETF, pd.Series(0.0, index=idx))
    out["hidden_composite_defense"] = weights.get(SOURCE_SLEEVE, pd.Series(0.0, index=idx)) * source_defense_share
    out["decomposed_hidden_cash"] = (
        weights.get(OFFENSE_COMPONENT, pd.Series(0.0, index=idx)) * offense_pos.get(CASH_ETF, pd.Series(0.0, index=idx))
        + weights.get(DEFENSE_COMPONENT, pd.Series(0.0, index=idx)) * defense_pos.get(CASH_ETF, pd.Series(0.0, index=idx))
    )
    out["explicit_component_defense"] = weights.get(DEFENSE_COMPONENT, pd.Series(0.0, index=idx))
    out["composite_family_weight"] = weights.reindex(columns=[c for c in [SOURCE_SLEEVE, OFFENSE_COMPONENT, DEFENSE_COMPONENT] if c in weights.columns]).sum(axis=1)
    return out


def state_hidden_summary(name: str, hidden_df: pd.DataFrame, state_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state_name in STATE_ORDER:
        mask = state_df["state_label"].eq(state_name)
        if int(mask.sum()) == 0:
            continue
        grp = hidden_df.loc[mask]
        rows.append(
            {
                "name": name,
                "state": state_name,
                "avg_hidden_composite_cash": float(grp["hidden_composite_cash"].mean()),
                "avg_hidden_composite_defense": float(grp["hidden_composite_defense"].mean()),
                "avg_decomposed_hidden_cash": float(grp["decomposed_hidden_cash"].mean()),
                "avg_explicit_component_defense": float(grp["explicit_component_defense"].mean()),
                "avg_composite_family_weight": float(grp["composite_family_weight"].mean()),
            }
        )
    return pd.DataFrame(rows)


def build_state_summary_yy(
    name: str,
    returns_df: pd.DataFrame,
    sleeve_weights: pd.DataFrame,
    etf_weights: pd.DataFrame,
    state_df: pd.DataFrame,
) -> pd.DataFrame:
    bucket_weights = bucket_series_yy(sleeve_weights)
    rows = []
    for state_name in STATE_ORDER:
        mask = state_df["state_label"].eq(state_name)
        if int(mask.sum()) == 0:
            continue
        state_returns = returns_df.loc[mask, "net_return"]
        state_etf = etf_weights.loc[mask]
        state_bucket = bucket_weights.loc[mask]
        exposures = avg_etf_exposures(state_etf)
        rows.append(
            {
                "name": name,
                "state": state_name,
                "n_weeks": int(mask.sum()),
                "ann_return": annual_return(state_returns),
                "sharpe": sharpe_ratio(state_returns),
                "avg_BIL": exposures["avg_BIL"],
                "avg_SPY": exposures["avg_SPY"],
                "avg_offense": exposures["avg_offense"],
                "avg_defense": exposures["avg_defense"],
                "avg_cash": exposures["avg_cash"],
                "avg_composite_family": float(state_bucket["composite_family"].mean()),
                "bucket_offense": float(state_bucket["offense"].mean()),
                "bucket_defense": float(state_bucket["defense"].mean()),
                "bucket_cash": float(state_bucket["cash"].mean()),
            }
        )
    return pd.DataFrame(rows)


def assemble_results(
    state_df: pd.DataFrame,
    comparison_names: list[str],
    candidate_names: list[str],
    source_positions: pd.DataFrame,
    component_positions: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    weekly_returns.index = pd.to_datetime(weekly_returns.index).tz_localize(None)
    spy_returns = weekly_returns["SPY"].reindex(state_df.index).fillna(0.0)
    holdout_start = pd.Timestamp("2024-04-19")
    recovery_mask = state_df["state_label"].isin(["recovery_confirmed", "recovery_fragile"])

    metrics_rows = []
    state_frames = []
    hidden_frames = []
    for version_name in comparison_names:
        returns_df = load_frame(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv").reindex(state_df.index).fillna(0.0)
        sleeve_df = load_frame(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv").reindex(state_df.index).fillna(0.0)
        etf_df = load_frame(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv").reindex(state_df.index).fillna(0.0)
        net = returns_df["net_return"]
        holdout = net.loc[net.index >= holdout_start]
        bucket_df = bucket_series_yy(sleeve_df)
        exposures = avg_etf_exposures(etf_df)
        hidden_df = hidden_composite_behavior(sleeve_df, source_positions, component_positions).reindex(state_df.index).fillna(0.0)
        hidden_frames.append(state_hidden_summary(version_name, hidden_df, state_df))

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
                "avg_bucket_cash": float(bucket_df["cash"].mean()),
                "avg_composite_family": float(bucket_df["composite_family"].mean()),
                "avg_hidden_composite_cash": float(hidden_df["hidden_composite_cash"].mean()),
                "avg_hidden_composite_defense": float(hidden_df["hidden_composite_defense"].mean()),
                "avg_decomposed_hidden_cash": float(hidden_df["decomposed_hidden_cash"].mean()),
                "avg_explicit_component_defense": float(hidden_df["explicit_component_defense"].mean()),
            }
        )
        state_frames.append(build_state_summary_yy(version_name, returns_df, sleeve_df, etf_df, state_df))

    metrics_df = pd.DataFrame(metrics_rows)
    state_summary_df = pd.concat(state_frames, ignore_index=True)
    hidden_state_df = pd.concat(hidden_frames, ignore_index=True)

    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    shadow_row = metrics_df[metrics_df["name"] == SHADOW_NAME].iloc[0]
    vv_row = metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0]
    xx_row = metrics_df[metrics_df["name"] == XX_REFERENCE_NAME].iloc[0]

    for base_name, base_row in [("prod", prod_row), ("shadow", shadow_row), ("vv", vv_row), ("xx", xx_row)]:
        for col in [
            "ann_return",
            "ann_vol",
            "sharpe",
            "max_drawdown",
            "cvar_5",
            "avg_BIL",
            "avg_SPY",
            "avg_offense",
            "avg_defense",
            "avg_composite_family",
            "avg_hidden_composite_cash",
            "avg_hidden_composite_defense",
        ]:
            metrics_df[f"{col}_delta_vs_{base_name}"] = metrics_df[col] - float(base_row[col])

    prod_state = state_summary_df[state_summary_df["name"] == PRODUCTION_NAME].set_index("state")
    vv_state = state_summary_df[state_summary_df["name"] == VV_REFERENCE_NAME].set_index("state")
    xx_state = state_summary_df[state_summary_df["name"] == XX_REFERENCE_NAME].set_index("state")
    for target_name, target_df in [("prod", prod_state), ("vv", vv_state), ("xx", xx_state)]:
        state_summary_df[f"ann_return_delta_vs_{target_name}"] = state_summary_df.apply(
            lambda row: float(row["ann_return"] - target_df.at[row["state"], "ann_return"]) if row["state"] in target_df.index else np.nan,
            axis=1,
        )
        state_summary_df[f"sharpe_delta_vs_{target_name}"] = state_summary_df.apply(
            lambda row: float(row["sharpe"] - target_df.at[row["state"], "sharpe"]) if row["state"] in target_df.index else np.nan,
            axis=1,
        )

    prod_hidden = hidden_state_df[hidden_state_df["name"] == PRODUCTION_NAME].set_index("state")
    diag_rows = []
    for candidate_name in candidate_names:
        cand_hidden = hidden_state_df[hidden_state_df["name"] == candidate_name]
        for _, row in cand_hidden.iterrows():
            state_name = row["state"]
            diag_rows.append(
                {
                    **row.to_dict(),
                    "hidden_cash_reduction_vs_prod": float(prod_hidden.at[state_name, "avg_hidden_composite_cash"] - row["avg_decomposed_hidden_cash"]) if state_name in prod_hidden.index else np.nan,
                    "hidden_defense_reduction_vs_prod": float(prod_hidden.at[state_name, "avg_hidden_composite_defense"] - row["avg_explicit_component_defense"]) if state_name in prod_hidden.index else np.nan,
                }
            )
    candidate_diag_df = pd.DataFrame(diag_rows)
    return metrics_df, state_summary_df, candidate_diag_df


def screen_candidate(
    row: pd.Series,
    prod_row: pd.Series,
    vv_row: pd.Series,
    state_summary_df: pd.DataFrame,
    candidate_diag_df: pd.DataFrame,
) -> tuple[str, list[str]]:
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
    if float(row["avg_SPY_delta_vs_prod"]) > 0.015 and float(row["sharpe_delta_vs_prod"]) < 0.006:
        reasons.append("improvement may be mostly hidden SPY/beta")

    state_slice = state_summary_df[state_summary_df["name"] == row["name"]].set_index("state")
    if "stressed_panic" in state_slice.index:
        if float(state_slice.at["stressed_panic", "ann_return_delta_vs_prod"]) < -0.0025 or float(state_slice.at["stressed_panic", "sharpe_delta_vs_prod"]) < -0.03:
            reasons.append("stressed_panic worsens materially")
    if "recovery_fragile" in state_slice.index:
        if float(state_slice.at["recovery_fragile", "ann_return_delta_vs_prod"]) < -0.0025 or float(state_slice.at["recovery_fragile", "sharpe_delta_vs_prod"]) < -0.03:
            reasons.append("recovery_fragile worsens materially")

    diag_slice = candidate_diag_df[candidate_diag_df["name"] == row["name"]]
    targeted = diag_slice[diag_slice["state"].isin(TARGET_STATES)]
    if targeted.empty or float(targeted["hidden_cash_reduction_vs_prod"].mean()) <= 0.0:
        reasons.append("decomposition does not reduce duplicated cash behavior")

    if reasons:
        return "REJECT", reasons
    return "PRODUCTION CHALLENGER PENDING HUMAN REVIEW", []


def choose_best(metrics_df: pd.DataFrame, candidate_names: list[str]) -> str:
    candidate_df = metrics_df[metrics_df["name"].isin(candidate_names)].copy()
    candidate_df = candidate_df.sort_values(["sharpe", "ann_return"], ascending=[False, False])
    return str(candidate_df.iloc[0]["name"])


def main() -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    comparison_names = [
        PRODUCTION_NAME,
        SHADOW_NAME,
        VV_REFERENCE_NAME,
        XX_REFERENCE_NAME,
        *YY_CANDIDATES,
    ]
    build_versions(comparison_names)

    state_df = add_state_labels(load_frame(LAYER2B_DIR / "market_state_history.csv"))
    source_positions = load_frame(LAYER2A_DIR / "strategy_positions_composite_regime_conditioned.csv").reindex(state_df.index).fillna(0.0)
    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    weekly_returns.index = pd.to_datetime(weekly_returns.index).tz_localize(None)
    weekly_returns = weekly_returns.reindex(source_positions.index).fillna(0.0)
    component_positions = build_component_positions(source_positions)
    component_returns = approximate_component_returns(component_positions, weekly_returns)

    production_sleeve_weights = load_frame(LAYER3_DIR / f"portfolio_version_sleeve_weights_{PRODUCTION_NAME}.csv").reindex(state_df.index).fillna(0.0)
    production_returns = load_frame(LAYER3_DIR / f"portfolio_version_returns_{PRODUCTION_NAME}.csv").reindex(state_df.index).fillna(0.0)["net_return"]
    benchmark_returns = weekly_returns["SPY"].reindex(state_df.index).fillna(0.0)
    component_weights_df, component_returns_df, component_corr_df, component_diag_df = component_state_tables(
        state_df,
        source_positions,
        component_returns.reindex(state_df.index).fillna(0.0),
        production_sleeve_weights,
        production_returns,
        benchmark_returns,
        weekly_returns[CASH_ETF].reindex(state_df.index).fillna(0.0) if CASH_ETF in weekly_returns.columns else None,
    )

    metrics_df, state_summary_df, candidate_diag_df = assemble_results(
        state_df,
        comparison_names,
        YY_CANDIDATES,
        source_positions,
        component_positions,
    )
    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    vv_row = metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0]

    selection_rows = []
    for _, row in metrics_df[metrics_df["name"].isin(YY_CANDIDATES)].iterrows():
        status, reasons = screen_candidate(row, prod_row, vv_row, state_summary_df, candidate_diag_df)
        selection_rows.append(
            {
                "name": row["name"],
                "status": status,
                "reasons": " | ".join(reasons),
            }
        )
    selection_df = pd.DataFrame(selection_rows)
    best_candidate = choose_best(metrics_df, YY_CANDIDATES)

    component_weights_df.to_csv(RESEARCH_DIR / "phase_yy_composite_component_weights_by_state.csv", index=False)
    component_returns_df.to_csv(RESEARCH_DIR / "phase_yy_composite_component_returns_by_state.csv", index=False)
    component_corr_df.to_csv(RESEARCH_DIR / "phase_yy_composite_component_correlations.csv", index=False)
    component_diag_df.to_csv(RESEARCH_DIR / "phase_yy_composite_component_diagnostics.csv", index=False)
    candidate_diag_df.to_csv(RESEARCH_DIR / "phase_yy_candidate_diagnostics.csv", index=False)

    metrics_df.to_csv(LAYER3_DIR / "phase_yy_candidate_metrics_full.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_yy_state_summary.csv", index=False)
    selection_df.to_csv(LAYER3_DIR / "phase_yy_selection_table.csv", index=False)
    protocol = {
        "phase": "YY",
        "best_candidate": best_candidate,
        "production_reference": PRODUCTION_NAME,
        "shadow_reference": SHADOW_NAME,
        "vv_reference": VV_REFERENCE_NAME,
        "xx_reference": XX_REFERENCE_NAME,
        "candidates": YY_CANDIDATES,
        "decomposition_method": {
            "source_sleeve": SOURCE_SLEEVE,
            "offense_etfs": OFFENSE_ETFS,
            "defense_etfs": DEFENSE_ETFS,
            "cash_etf": CASH_ETF,
            "note": "Component sleeves are causal ETF-position decompositions of composite_regime_conditioned. Candidate portfolio returns are still generated through the canonical production construction path.",
        },
    }
    (LAYER3_DIR / "phase_yy_protocol.json").write_text(json.dumps(protocol, indent=2))
    print(f"Phase YY complete. Best candidate: {best_candidate}")


if __name__ == "__main__":
    main()
