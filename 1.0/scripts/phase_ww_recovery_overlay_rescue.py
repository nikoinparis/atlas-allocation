from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
CHECKPOINT_DIR = ROOT / "data" / "research" / "allocator_checkpoints"
RESEARCH_DIR = ROOT / "data" / "research" / "phase_ww_recovery_overlay_rescue"

PRODUCTION_NAME = "improved_phase2b_regime_confidence_boost"
SHADOW_NAME = "improved_phase2b_combo_abc"
TT_REFERENCE_NAME = "improved_phasett_recovery_two_stage_bucket"
UU_REFERENCE_NAME = "improved_phaseuu_tt1_budget_aware_lighter_both"
VV_REFERENCE_NAME = "improved_phasevv_recovery_neutral_budget_aware_overlay"
MAIN_CANDIDATES = [
    "improved_phaseww_recovery_budget_native_lighter_both",
    "improved_phaseww_split_recovery_lighter_both",
    "improved_phaseww_vv_direct_lighter_both_rewrite",
]
RESCUE_CANDIDATES = [
    "improved_phaseww_confirmed_only_lighter_both",
    "improved_phaseww_fragile_defense_lighter_both",
    "improved_phaseww_vv_shadow_polish",
]
STATE_ORDER = [
    "calm_trend",
    "neutral_healthy_proxy",
    "neutral_mixed",
    "recovery_confirmed",
    "recovery_fragile",
    "stressed_panic",
]
TARGET_RECOVERY_STATES = {"recovery_confirmed", "recovery_fragile"}
SLEEVE_BUCKET_MAP = {
    "dual_momentum_topn": "offense",
    "cta_trend_long_only": "offense",
    "composite_selective_signals": "offense",
    "taa_10m_sma": "defense",
    "composite_regime_conditioned": "composite",
    "cash::BIL": "cash",
}
ETF_DEFENSIVE = {"IEF", "SHY", "TLT", "TIP", "GLD", "LQD", "MBB", "UUP"}
INTENDED_CASH_BUDGETS: dict[str, dict[str, float]] = {
    TT_REFERENCE_NAME: {"recovery_confirmed": 0.060, "recovery_fragile": 0.100},
    UU_REFERENCE_NAME: {"recovery_confirmed": 0.052, "recovery_fragile": 0.112},
    VV_REFERENCE_NAME: {
        "neutral_healthy_proxy": 0.135,
        "recovery_confirmed": 0.060,
        "recovery_fragile": 0.100,
    },
    "improved_phaseww_recovery_budget_native_lighter_both": {
        "recovery_confirmed": 0.055,
        "recovery_fragile": 0.095,
    },
    "improved_phaseww_split_recovery_lighter_both": {
        "recovery_confirmed": 0.045,
        "recovery_fragile": 0.105,
    },
    "improved_phaseww_vv_direct_lighter_both_rewrite": {
        "neutral_healthy_proxy": 0.120,
        "recovery_confirmed": 0.050,
        "recovery_fragile": 0.095,
    },
    "improved_phaseww_confirmed_only_lighter_both": {
        "recovery_confirmed": 0.045,
    },
    "improved_phaseww_fragile_defense_lighter_both": {
        "recovery_confirmed": 0.050,
        "recovery_fragile": 0.110,
    },
    "improved_phaseww_vv_shadow_polish": {
        "neutral_healthy_proxy": 0.123,
        "recovery_confirmed": 0.052,
        "recovery_fragile": 0.100,
    },
}


def load_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    first_col = df.columns[0]
    df[first_col] = pd.to_datetime(df[first_col]).dt.tz_localize(None)
    return df.rename(columns={first_col: "Date"}).set_index("Date").sort_index()


def load_simple_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df


def strong_neutral_mask(state_df: pd.DataFrame) -> pd.Series:
    return (
        state_df["market_state"].eq("neutral_mixed")
        & (pd.to_numeric(state_df["market_trend_positive"], errors="coerce").fillna(0.0) > 0.0)
        & (pd.to_numeric(state_df["breadth_sma_43"], errors="coerce").fillna(0.0) >= 0.55)
        & (pd.to_numeric(state_df["breadth_26w_mom"], errors="coerce").fillna(0.0) >= 0.50)
    )


def add_state_labels(state_df: pd.DataFrame) -> pd.DataFrame:
    out = state_df.copy()
    out["state_label"] = out["market_state"]
    out.loc[strong_neutral_mask(out), "state_label"] = "neutral_healthy_proxy"
    return out


def annual_return(series: pd.Series) -> float:
    s = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    return float(s.mean() * 52.0) if not s.empty else np.nan


def annual_vol(series: pd.Series) -> float:
    s = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    return float(s.std(ddof=0) * np.sqrt(52.0)) if not s.empty else np.nan


def sharpe_ratio(series: pd.Series) -> float:
    vol = annual_vol(series)
    if not np.isfinite(vol) or vol <= 1e-12:
        return np.nan
    return float(annual_return(series) / vol)


def max_drawdown(series: pd.Series) -> float:
    s = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return np.nan
    wealth = (1.0 + s).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def calmar_ratio(series: pd.Series) -> float:
    dd = max_drawdown(series)
    if not np.isfinite(dd) or abs(dd) <= 1e-12:
        return np.nan
    return float(annual_return(series) / abs(dd))


def cvar_5(series: pd.Series) -> float:
    s = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return np.nan
    cutoff = s.quantile(0.05)
    tail = s[s <= cutoff]
    return float(tail.mean()) if not tail.empty else float(cutoff)


def summary_metrics(return_series: pd.Series) -> dict[str, float]:
    return {
        "ann_return": annual_return(return_series),
        "ann_vol": annual_vol(return_series),
        "sharpe": sharpe_ratio(return_series),
        "max_drawdown": max_drawdown(return_series),
        "calmar": calmar_ratio(return_series),
        "cvar_5": cvar_5(return_series),
    }


def bucket_series(sleeve_weights: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=sleeve_weights.index)
    for bucket in ["offense", "defense", "composite", "cash"]:
        cols = [
            name
            for name, bucket_name in SLEEVE_BUCKET_MAP.items()
            if bucket_name == bucket and name in sleeve_weights.columns
        ]
        out[bucket] = sleeve_weights.reindex(columns=cols).sum(axis=1) if cols else 0.0
    return out


def avg_etf_exposures(etf_weights: pd.DataFrame) -> dict[str, float]:
    cols = set(etf_weights.columns)
    avg_bil = float(etf_weights["BIL"].mean()) if "BIL" in cols else 0.0
    avg_spy = float(etf_weights["SPY"].mean()) if "SPY" in cols else 0.0
    defense_cols = sorted(cols.intersection(ETF_DEFENSIVE))
    offense_cols = sorted(cols.difference(set(defense_cols) | {"BIL"}))
    return {
        "avg_BIL": avg_bil,
        "avg_SPY": avg_spy,
        "avg_offense": float(etf_weights.reindex(columns=offense_cols).sum(axis=1).mean()) if offense_cols else 0.0,
        "avg_defense": float(etf_weights.reindex(columns=defense_cols).sum(axis=1).mean()) if defense_cols else 0.0,
        "avg_cash": avg_bil,
    }


def compute_capture(candidate_returns: pd.Series, benchmark_returns: pd.Series, mask: pd.Series) -> float:
    aligned = pd.concat(
        [pd.Series(candidate_returns, dtype=float), pd.Series(benchmark_returns, dtype=float), pd.Series(mask, dtype=bool)],
        axis=1,
    ).dropna()
    aligned = aligned[aligned.iloc[:, 2]]
    if aligned.empty:
        return np.nan
    bench_mean = float(aligned.iloc[:, 1].mean())
    if abs(bench_mean) <= 1e-12:
        return np.nan
    return float(aligned.iloc[:, 0].mean() / bench_mean)


def intended_cash_budget(version_name: str, state_name: str, stage1_cash_budget: float) -> float:
    return float(INTENDED_CASH_BUDGETS.get(version_name, {}).get(state_name, stage1_cash_budget))


def build_versions(version_names: list[str]) -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(version_names)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")],
        cwd=ROOT,
        check=True,
        env=env,
    )


def infer_overlay_source(state_name: str, row: pd.Series) -> str:
    if state_name == "stressed_panic":
        return "panic_guardrail"
    if float(row.get("target_vol_binding_share", 0.0)) > 0.10:
        return "target_vol"
    if float(row.get("avg_self_gated_overlay_cut_risky", 0.0)) + float(row.get("avg_non_self_gated_overlay_cut_risky", 0.0)) > 1e-4:
        return "lighter_both_regime_relief"
    return "other_or_none"


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

    def object_col(frame: pd.DataFrame, col: str, default: str | None = None) -> pd.Series:
        if isinstance(frame, pd.DataFrame) and col in frame.columns:
            return frame[col]
        return pd.Series(default, index=state_df.index, dtype=object)

    weekly = pd.DataFrame(index=state_df.index)
    weekly["state"] = state_df["state_label"]
    weekly["stage1_cash_budget"] = stage1.get("cash::BIL", pd.Series(0.0, index=weekly.index))
    weekly["stage1_risky_budget"] = 1.0 - weekly["stage1_cash_budget"]
    weekly["post_overlay_cash_budget"] = post_overlay.get("cash::BIL", pd.Series(0.0, index=weekly.index))
    weekly["post_overlay_risky_budget"] = 1.0 - weekly["post_overlay_cash_budget"]
    weekly["final_etf_cash_budget"] = final_etf.get("BIL", pd.Series(0.0, index=weekly.index))
    weekly["final_etf_risky_budget"] = 1.0 - weekly["final_etf_cash_budget"]
    weekly["target_vol_multiplier"] = numeric_col(vdiag, "target_vol_multiplier")
    weekly["regime_multiplier"] = numeric_col(vdiag, "regime_multiplier")
    weekly["target_vol_binding"] = numeric_col(vdiag, "target_vol_binding", 0.0).fillna(0.0)
    weekly["regime_binding"] = numeric_col(vdiag, "regime_binding", 0.0).fillna(0.0)
    weekly["binding_source"] = object_col(vdiag, "binding_source", None)
    weekly["self_gated_overlay_cut_risky"] = numeric_col(vstack, "self_gated_overlay_cut_risky", 0.0).fillna(0.0)
    weekly["non_self_gated_overlay_cut_risky"] = numeric_col(vstack, "non_self_gated_overlay_cut_risky", 0.0).fillna(0.0)
    weekly["overlay_cash_weight"] = numeric_col(vstack, "overlay_cash_weight", 0.0).fillna(0.0)
    weekly["overlay_cash_added"] = weekly["post_overlay_cash_budget"] - weekly["stage1_cash_budget"]
    weekly["target_vol_required_cash"] = np.maximum(0.0, 1.0 - weekly["target_vol_multiplier"].fillna(1.0))
    weekly["target_vol_active"] = weekly["target_vol_binding"] > 0.0
    weekly["panic_guardrail_active"] = weekly["state"].eq("stressed_panic")
    weekly["panic_guardrail_cash"] = np.where(weekly["panic_guardrail_active"], weekly["post_overlay_cash_budget"], 0.0)
    weekly["intended_cash_budget"] = [
        intended_cash_budget(version_name, state_name, float(stage1_cash))
        for state_name, stage1_cash in zip(weekly["state"], weekly["stage1_cash_budget"])
    ]
    weekly["intended_risky_budget"] = 1.0 - weekly["intended_cash_budget"]
    weekly["guardrail_cash_floor"] = weekly[["intended_cash_budget", "target_vol_required_cash", "panic_guardrail_cash"]].max(axis=1)
    weekly["target_vol_justified_extra_cash"] = np.maximum(
        0.0,
        np.minimum(weekly["post_overlay_cash_budget"], weekly["target_vol_required_cash"]) - weekly["intended_cash_budget"],
    )
    weekly["panic_justified_extra_cash"] = np.where(
        weekly["panic_guardrail_active"],
        np.maximum(0.0, weekly["post_overlay_cash_budget"] - np.maximum(weekly["intended_cash_budget"], weekly["target_vol_required_cash"])),
        0.0,
    )
    weekly["excess_cash_not_guardrail"] = np.maximum(0.0, weekly["post_overlay_cash_budget"] - weekly["guardrail_cash_floor"])
    weekly["target_vol_shortfall"] = np.where(
        weekly["target_vol_active"],
        np.maximum(0.0, weekly["target_vol_required_cash"] - weekly["post_overlay_cash_budget"]),
        0.0,
    )
    weekly["overlay_absorption"] = weekly["stage1_risky_budget"] - weekly["post_overlay_risky_budget"]
    weekly["lookthrough_absorption"] = weekly["post_overlay_risky_budget"] - weekly["final_etf_risky_budget"]
    weekly["total_absorption"] = weekly["stage1_risky_budget"] - weekly["final_etf_risky_budget"]
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
                "post_overlay_budget_gap": float((grp["post_overlay_cash_budget"] - grp["intended_cash_budget"]).mean()),
                "final_etf_budget_gap": float((grp["final_etf_cash_budget"] - grp["intended_cash_budget"]).mean()),
                "target_vol_active_share": float(grp["target_vol_active"].mean()),
                "panic_guardrail_active_share": float(grp["panic_guardrail_active"].mean()),
                "avg_target_vol_required_cash": float(grp["target_vol_required_cash"].mean()),
                "avg_target_vol_justified_extra_cash": float(grp["target_vol_justified_extra_cash"].mean()),
                "avg_panic_guardrail_cash": float(grp["panic_guardrail_cash"].mean()),
                "avg_panic_justified_extra_cash": float(grp["panic_justified_extra_cash"].mean()),
                "avg_excess_cash_not_guardrail": float(grp["excess_cash_not_guardrail"].mean()),
                "target_vol_shortfall_avg": float(grp["target_vol_shortfall"].mean()),
                "avg_self_gated_overlay_cut_risky": self_cut,
                "avg_non_self_gated_overlay_cut_risky": nonself_cut,
                "inferred_overlay_cash_source": infer_overlay_source(
                    state_name,
                    pd.Series(
                        {
                            "target_vol_binding_share": float(grp["target_vol_active"].mean()),
                            "avg_self_gated_overlay_cut_risky": self_cut,
                            "avg_non_self_gated_overlay_cut_risky": nonself_cut,
                        }
                    ),
                ),
            }
        )
    return pd.DataFrame(rows)


def state_summary_for_version(
    name: str,
    returns_df: pd.DataFrame,
    sleeve_weights: pd.DataFrame,
    etf_weights: pd.DataFrame,
    state_df: pd.DataFrame,
) -> pd.DataFrame:
    bucket_weights = bucket_series(sleeve_weights)
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
                "avg_composite_bucket": float(state_bucket["composite"].mean()),
                "bucket_offense": float(state_bucket["offense"].mean()),
                "bucket_defense": float(state_bucket["defense"].mean()),
                "bucket_composite": float(state_bucket["composite"].mean()),
                "bucket_cash": float(state_bucket["cash"].mean()),
            }
        )
    return pd.DataFrame(rows)


def assemble_results(
    state_df: pd.DataFrame,
    comparison_names: list[str],
    candidate_names: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    diag_ts = load_simple_csv(LAYER3_DIR / "portfolio_version_diagnostics_timeseries.csv")
    stacked_ts = load_simple_csv(LAYER3_DIR / "stacked_defense_timeseries.csv")
    weekly_tables = {
        name: weekly_budget_table(name, state_df, diag_ts, stacked_ts)
        for name in comparison_names
    }
    absorption_df = pd.concat(
        [state_budget_absorption(name, weekly_tables[name]) for name in comparison_names],
        ignore_index=True,
    )

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
    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    shadow_row = metrics_df[metrics_df["name"] == SHADOW_NAME].iloc[0]
    tt_row = metrics_df[metrics_df["name"] == TT_REFERENCE_NAME].iloc[0]
    uu_row = metrics_df[metrics_df["name"] == UU_REFERENCE_NAME].iloc[0]
    vv_row = metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0]
    for base_name, base_row in [("prod", prod_row), ("shadow", shadow_row), ("tt1", tt_row), ("uu", uu_row), ("vv", vv_row)]:
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
    tt_abs = absorption_df[absorption_df["name"] == TT_REFERENCE_NAME].set_index("state")
    uu_abs = absorption_df[absorption_df["name"] == UU_REFERENCE_NAME].set_index("state")
    vv_abs = absorption_df[absorption_df["name"] == VV_REFERENCE_NAME].set_index("state")
    for candidate_name in candidate_names:
        cand_abs = absorption_df[absorption_df["name"] == candidate_name]
        for _, row in cand_abs.iterrows():
            state_name = row["state"]
            candidate_diag_rows.append(
                {
                    **row.to_dict(),
                    "overlay_absorption_reduction_vs_prod": float(prod_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]) if state_name in prod_abs.index else np.nan,
                    "overlay_absorption_reduction_vs_tt1": float(tt_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]) if state_name in tt_abs.index else np.nan,
                    "overlay_absorption_reduction_vs_uu": float(uu_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]) if state_name in uu_abs.index else np.nan,
                    "overlay_absorption_reduction_vs_vv": float(vv_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]) if state_name in vv_abs.index else np.nan,
                    "excess_cash_reduction_vs_prod": float(prod_abs.at[state_name, "avg_excess_cash_not_guardrail"] - row["avg_excess_cash_not_guardrail"]) if state_name in prod_abs.index else np.nan,
                    "excess_cash_reduction_vs_tt1": float(tt_abs.at[state_name, "avg_excess_cash_not_guardrail"] - row["avg_excess_cash_not_guardrail"]) if state_name in tt_abs.index else np.nan,
                    "excess_cash_reduction_vs_uu": float(uu_abs.at[state_name, "avg_excess_cash_not_guardrail"] - row["avg_excess_cash_not_guardrail"]) if state_name in uu_abs.index else np.nan,
                    "excess_cash_reduction_vs_vv": float(vv_abs.at[state_name, "avg_excess_cash_not_guardrail"] - row["avg_excess_cash_not_guardrail"]) if state_name in vv_abs.index else np.nan,
                }
            )
    candidate_diag_df = pd.DataFrame(candidate_diag_rows)

    return metrics_df, state_summary_df, absorption_df, candidate_diag_df


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
    if float(row["avg_SPY_delta_vs_prod"]) > 0.010 and float(row["sharpe_delta_vs_prod"]) < 0.007:
        reasons.append("improvement comes too much from hidden SPY/beta")

    state_rows = state_summary_df[state_summary_df["name"] == row["name"]].set_index("state")
    prod_states = state_summary_df[state_summary_df["name"] == PRODUCTION_NAME].set_index("state")
    if "stressed_panic" in state_rows.index and "stressed_panic" in prod_states.index:
        if float(state_rows.at["stressed_panic", "sharpe"] - prod_states.at["stressed_panic", "sharpe"]) < -0.05:
            reasons.append("stressed_panic worsens materially")
    if "recovery_fragile" in state_rows.index and "recovery_fragile" in prod_states.index:
        if float(state_rows.at["recovery_fragile", "ann_return"] - prod_states.at["recovery_fragile", "ann_return"]) < -0.005:
            reasons.append("recovery_fragile worsens materially")

    targeted = candidate_diag_df[
        (candidate_diag_df["name"] == row["name"])
        & (candidate_diag_df["state"].isin(TARGET_RECOVERY_STATES))
    ]
    if targeted.empty or float(targeted["overlay_absorption_reduction_vs_prod"].mean()) <= 0.0:
        reasons.append("overlay absorption is not reduced in recovery states")
    if targeted.empty or float(targeted["excess_cash_reduction_vs_prod"].mean()) <= 0.0:
        reasons.append("lighter_both excess cash is not reduced in recovery states")
    if not targeted.empty and float(targeted["target_vol_shortfall_avg"].max()) > 0.001:
        reasons.append("target-vol guardrails are overridden unsafely")

    status = "PASS" if not reasons else "REJECT"
    return status, reasons


def choose_best(metrics_df: pd.DataFrame, candidate_names: list[str]) -> str:
    subset = metrics_df[metrics_df["name"].isin(candidate_names)].copy()
    subset = subset.sort_values(["sharpe_delta_vs_prod", "ann_return_delta_vs_prod", "sharpe"], ascending=False)
    return str(subset.iloc[0]["name"])


def main() -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    print("Phase WW: loading state history...", flush=True)
    state_df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    state_df.index = pd.to_datetime(state_df.index).tz_localize(None)
    state_df = add_state_labels(state_df)

    reference_names = [PRODUCTION_NAME, SHADOW_NAME, TT_REFERENCE_NAME, UU_REFERENCE_NAME, VV_REFERENCE_NAME]
    print("Phase WW: building reference set plus main recovery overlay candidates...", flush=True)
    build_versions(reference_names + MAIN_CANDIDATES)

    metrics_df, state_summary_df, absorption_df, candidate_diag_df = assemble_results(
        state_df,
        reference_names + MAIN_CANDIDATES,
        MAIN_CANDIDATES,
    )

    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    vv_row = metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0]

    selection_rows = []
    for candidate_name in MAIN_CANDIDATES:
        row = metrics_df[metrics_df["name"] == candidate_name].iloc[0]
        status, reasons = screen_candidate(row, prod_row, vv_row, state_summary_df, candidate_diag_df)
        targeted = candidate_diag_df[(candidate_diag_df["name"] == candidate_name) & (candidate_diag_df["state"].isin(TARGET_RECOVERY_STATES))]
        selection_rows.append(
            {
                "name": candidate_name,
                "family": "main",
                "status": status,
                "reasons": "; ".join(reasons),
                "targeted_overlay_absorption_reduction_vs_prod": float(targeted["overlay_absorption_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "targeted_excess_cash_reduction_vs_prod": float(targeted["excess_cash_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "sharpe_delta_vs_prod": float(row["sharpe_delta_vs_prod"]),
                "sharpe_delta_vs_vv": float(row["sharpe_delta_vs_vv"]),
                "ann_return_delta_vs_prod": float(row["ann_return_delta_vs_prod"]),
            }
        )
    selection_df = pd.DataFrame(selection_rows)

    create_rescue = False
    rescue_reason = ""
    if not selection_df.empty and selection_df["status"].eq("REJECT").all():
        best_main_name = choose_best(metrics_df, MAIN_CANDIDATES)
        best_main = selection_df[selection_df["name"] == best_main_name].iloc[0]
        if float(best_main["sharpe_delta_vs_prod"]) >= 0.0025 and float(best_main["ann_return_delta_vs_prod"]) > -0.0010:
            create_rescue = True
            rescue_reason = (
                "All three main candidates failed narrowly: return and Sharpe improved, "
                "but the exact Sharpe gate or recovery overlay-absorption gate still failed."
            )

    full_candidate_names = list(MAIN_CANDIDATES)
    if create_rescue:
        print("Phase WW: main family failed narrowly; building rescue variants...", flush=True)
        build_versions(reference_names + RESCUE_CANDIDATES)
        full_candidate_names.extend(RESCUE_CANDIDATES)
        metrics_df, state_summary_df, absorption_df, candidate_diag_df = assemble_results(
            state_df,
            reference_names + full_candidate_names,
            full_candidate_names,
        )
        prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
        vv_row = metrics_df[metrics_df["name"] == VV_REFERENCE_NAME].iloc[0]
        rescue_rows = []
        for candidate_name in RESCUE_CANDIDATES:
            row = metrics_df[metrics_df["name"] == candidate_name].iloc[0]
            status, reasons = screen_candidate(row, prod_row, vv_row, state_summary_df, candidate_diag_df)
            targeted = candidate_diag_df[(candidate_diag_df["name"] == candidate_name) & (candidate_diag_df["state"].isin(TARGET_RECOVERY_STATES))]
            rescue_rows.append(
                {
                    "name": candidate_name,
                    "family": "rescue",
                    "status": status,
                    "reasons": "; ".join(reasons),
                    "targeted_overlay_absorption_reduction_vs_prod": float(targeted["overlay_absorption_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                    "targeted_excess_cash_reduction_vs_prod": float(targeted["excess_cash_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                    "sharpe_delta_vs_prod": float(row["sharpe_delta_vs_prod"]),
                    "sharpe_delta_vs_vv": float(row["sharpe_delta_vs_vv"]),
                    "ann_return_delta_vs_prod": float(row["ann_return_delta_vs_prod"]),
                }
            )
        selection_df = pd.concat([selection_df, pd.DataFrame(rescue_rows)], ignore_index=True)

    reporting_names = reference_names + full_candidate_names
    metrics_df = metrics_df[metrics_df["name"].isin(reporting_names)].copy().sort_values("name")
    state_summary_df = state_summary_df[state_summary_df["name"].isin(reporting_names)].copy().sort_values(["name", "state"])
    absorption_df = absorption_df[absorption_df["name"].isin(reporting_names)].copy().sort_values(["name", "state"])
    candidate_diag_df = candidate_diag_df[candidate_diag_df["name"].isin(full_candidate_names)].copy().sort_values(["name", "state"])

    excess_state = absorption_df[
        absorption_df["name"].isin(reference_names + full_candidate_names)
    ][
        [
            "name",
            "state",
            "n_weeks",
            "intended_cash_budget",
            "post_overlay_cash_budget",
            "final_etf_cash_budget",
            "overlay_cash_added",
            "avg_target_vol_required_cash",
            "avg_target_vol_justified_extra_cash",
            "avg_panic_guardrail_cash",
            "avg_panic_justified_extra_cash",
            "avg_excess_cash_not_guardrail",
            "target_vol_active_share",
            "panic_guardrail_active_share",
            "inferred_overlay_cash_source",
        ]
    ].copy()
    excess_state.to_csv(RESEARCH_DIR / "phase_ww_lighter_both_excess_cash_by_state.csv", index=False)

    guardrail_state = absorption_df[
        absorption_df["name"].isin(reference_names + full_candidate_names)
    ][
        [
            "name",
            "state",
            "n_weeks",
            "target_vol_active_share",
            "panic_guardrail_active_share",
            "avg_target_vol_required_cash",
            "avg_target_vol_justified_extra_cash",
            "avg_panic_guardrail_cash",
            "avg_panic_justified_extra_cash",
            "target_vol_shortfall_avg",
        ]
    ].copy()
    guardrail_state.to_csv(RESEARCH_DIR / "phase_ww_guardrail_activation_by_state.csv", index=False)

    branch_diag = absorption_df[
        absorption_df["name"].isin(reference_names + full_candidate_names)
    ][
        [
            "name",
            "state",
            "stage1_cash_budget",
            "stage1_risky_budget",
            "intended_cash_budget",
            "intended_risky_budget",
            "post_overlay_cash_budget",
            "post_overlay_risky_budget",
            "final_etf_cash_budget",
            "final_etf_risky_budget",
            "overlay_cash_added",
            "overlay_absorption",
            "lookthrough_absorption",
            "total_absorption",
            "post_overlay_budget_gap",
            "final_etf_budget_gap",
            "avg_self_gated_overlay_cut_risky",
            "avg_non_self_gated_overlay_cut_risky",
            "inferred_overlay_cash_source",
        ]
    ].copy()
    branch_diag.to_csv(RESEARCH_DIR / "phase_ww_overlay_branch_diagnostics.csv", index=False)

    comparison_df = absorption_df[absorption_df["name"].isin([PRODUCTION_NAME, TT_REFERENCE_NAME, UU_REFERENCE_NAME, VV_REFERENCE_NAME])].copy()
    comparison_df.to_csv(RESEARCH_DIR / "phase_ww_vv_tt_production_comparison.csv", index=False)
    candidate_diag_df.to_csv(RESEARCH_DIR / "phase_ww_candidate_diagnostics.csv", index=False)

    metrics_df.to_csv(LAYER3_DIR / "phase_ww_candidate_metrics_full.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_ww_state_summary.csv", index=False)
    selection_df.to_csv(LAYER3_DIR / "phase_ww_selection_table.csv", index=False)
    with open(LAYER3_DIR / "phase_ww_protocol.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": "2026-04-30",
                "references": reference_names,
                "main_candidates": MAIN_CANDIDATES,
                "rescue_candidates": RESCUE_CANDIDATES if create_rescue else [],
                "rescue_created": create_rescue,
                "rescue_reason": rescue_reason,
                "full_candidate_names": full_candidate_names,
            },
            f,
            indent=2,
        )

    best_candidate = choose_best(metrics_df, full_candidate_names)
    print(f"Phase WW complete. Best candidate: {best_candidate}", flush=True)


if __name__ == "__main__":
    main()
