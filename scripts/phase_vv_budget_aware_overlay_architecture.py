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
RESEARCH_DIR = ROOT / "data" / "research" / "phase_vv_budget_aware_overlay"

PRODUCTION_NAME = "improved_phase2b_regime_confidence_boost"
SHADOW_NAME = "improved_phase2b_combo_abc"
TT_REFERENCE_NAME = "improved_phasett_recovery_two_stage_bucket"
UU_REFERENCE_NAME = "improved_phaseuu_tt1_budget_aware_lighter_both"
VV_CANDIDATES = [
    "improved_phasevv_recovery_budget_aware_overlay",
    "improved_phasevv_recovery_overlay_tolerance_band",
    "improved_phasevv_recovery_neutral_budget_aware_overlay",
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
    TT_REFERENCE_NAME: {
        "recovery_confirmed": 0.060,
        "recovery_fragile": 0.100,
    },
    UU_REFERENCE_NAME: {
        "recovery_confirmed": 0.052,
        "recovery_fragile": 0.112,
    },
    "improved_phasevv_recovery_budget_aware_overlay": {
        "recovery_confirmed": 0.060,
        "recovery_fragile": 0.100,
    },
    "improved_phasevv_recovery_overlay_tolerance_band": {
        "recovery_confirmed": 0.075,
        "recovery_fragile": 0.115,
    },
    "improved_phasevv_recovery_neutral_budget_aware_overlay": {
        "neutral_healthy_proxy": 0.135,
        "recovery_confirmed": 0.060,
        "recovery_fragile": 0.100,
    },
}


def load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    first_col = frame.columns[0]
    frame[first_col] = pd.to_datetime(frame[first_col]).dt.tz_localize(None)
    return frame.rename(columns={first_col: "Date"}).set_index("Date").sort_index()


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
        cols = [name for name, bucket_name in SLEEVE_BUCKET_MAP.items() if bucket_name == bucket and name in sleeve_weights.columns]
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
                "bucket_offense": float(state_bucket["offense"].mean()),
                "bucket_defense": float(state_bucket["defense"].mean()),
                "bucket_composite": float(state_bucket["composite"].mean()),
                "bucket_cash": float(state_bucket["cash"].mean()),
            }
        )
    return pd.DataFrame(rows)


def intended_cash_budget(version_name: str, state_name: str, stage1_cash_budget: float) -> float:
    budget_map = INTENDED_CASH_BUDGETS.get(version_name, {})
    return float(budget_map.get(state_name, stage1_cash_budget))


def state_budget_absorption(version_name: str, state_df: pd.DataFrame) -> pd.DataFrame:
    post_tilt = load_frame(CHECKPOINT_DIR / f"{version_name}__post_state_tilt_sleeve_weights.csv").reindex(state_df.index).fillna(0.0)
    post_overlay = load_frame(CHECKPOINT_DIR / f"{version_name}__post_overlay_pre_lookthrough_sleeve_weights.csv").reindex(state_df.index).fillna(0.0)
    final_etf = load_frame(CHECKPOINT_DIR / f"{version_name}__final_etf_weights.csv").reindex(state_df.index).fillna(0.0)
    final_sleeve = load_frame(CHECKPOINT_DIR / f"{version_name}__final_sleeve_weights.csv").reindex(state_df.index).fillna(0.0)
    bucket_df = bucket_series(final_sleeve)

    rows = []
    for state_name in STATE_ORDER:
        mask = state_df["state_label"].eq(state_name)
        if int(mask.sum()) == 0:
            continue
        stage1_cash = float(post_tilt.loc[mask, "cash::BIL"].mean()) if "cash::BIL" in post_tilt.columns else 0.0
        stage1_risky = 1.0 - stage1_cash
        post_overlay_cash = float(post_overlay.loc[mask, "cash::BIL"].mean()) if "cash::BIL" in post_overlay.columns else 0.0
        post_overlay_risky = 1.0 - post_overlay_cash
        final_bil = float(final_etf.loc[mask, "BIL"].mean()) if "BIL" in final_etf.columns else 0.0
        final_risky = 1.0 - final_bil
        intended_cash = intended_cash_budget(version_name, state_name, stage1_cash)
        intended_risky = 1.0 - intended_cash
        rows.append(
            {
                "name": version_name,
                "state": state_name,
                "n_weeks": int(mask.sum()),
                "stage1_risky_budget": stage1_risky,
                "stage1_cash_budget": stage1_cash,
                "intended_risky_budget": intended_risky,
                "intended_cash_budget": intended_cash,
                "post_overlay_risky_budget": post_overlay_risky,
                "post_overlay_cash_budget": post_overlay_cash,
                "final_etf_risky_budget": final_risky,
                "final_etf_cash_budget": final_bil,
                "overlay_cash_added": post_overlay_cash - stage1_cash,
                "overlay_absorption": stage1_risky - post_overlay_risky,
                "lookthrough_absorption": post_overlay_risky - final_risky,
                "total_absorption": stage1_risky - final_risky,
                "post_overlay_budget_gap": post_overlay_cash - intended_cash,
                "final_etf_budget_gap": final_bil - intended_cash,
                "bucket_offense": float(bucket_df.loc[mask, "offense"].mean()),
                "bucket_defense": float(bucket_df.loc[mask, "defense"].mean()),
                "bucket_composite": float(bucket_df.loc[mask, "composite"].mean()),
                "bucket_cash": float(bucket_df.loc[mask, "cash"].mean()),
            }
        )
    return pd.DataFrame(rows)


def infer_branch_diagnostics(
    diag_ts: pd.DataFrame,
    stacked_ts: pd.DataFrame,
    state_df: pd.DataFrame,
    versions: list[str],
) -> pd.DataFrame:
    ts = diag_ts.copy()
    ts["Date"] = pd.to_datetime(ts["Date"]).dt.tz_localize(None)
    ts = ts.set_index("Date").join(state_df[["state_label"]], how="left")

    sd = stacked_ts.copy()
    sd["Date"] = pd.to_datetime(sd["Date"]).dt.tz_localize(None)
    sd = sd.set_index("Date").join(state_df[["state_label"]], how="left")

    rows = []
    for version_name in versions:
        vts = ts[ts["version_name"] == version_name]
        vsd = sd[sd["version_name"] == version_name]
        for state_name in STATE_ORDER:
            a = vts[vts["state_label"] == state_name]
            b = vsd[vsd["state_label"] == state_name]
            if a.empty and b.empty:
                continue
            binding_counts = a["binding_source"].value_counts(normalize=True) if "binding_source" in a.columns and not a.empty else pd.Series(dtype=float)
            regime_share = float(binding_counts.get("regime", 0.0) + binding_counts.get("both", 0.0))
            target_vol_share = float(binding_counts.get("target_vol", 0.0))
            none_share = float(binding_counts.get("none", 0.0))
            self_cut = float(b["self_gated_overlay_cut_risky"].mean()) if "self_gated_overlay_cut_risky" in b.columns and not b.empty else 0.0
            nonself_cut = float(b["non_self_gated_overlay_cut_risky"].mean()) if "non_self_gated_overlay_cut_risky" in b.columns and not b.empty else 0.0
            overlay_cash = float(b["overlay_cash_weight"].mean()) if "overlay_cash_weight" in b.columns and not b.empty else 0.0
            vv_override = float(a["vv_budget_override_applied"].mean()) if "vv_budget_override_applied" in a.columns and not a.empty else 0.0
            vv_guardrail = float(a["vv_target_vol_guardrail_active"].mean()) if "vv_target_vol_guardrail_active" in a.columns and not a.empty else 0.0
            vv_gap_post = float(a["vv_budget_gap_post"].mean()) if "vv_budget_gap_post" in a.columns and not a.empty else np.nan
            if target_vol_share > 0.5:
                inferred = "target_vol"
            elif (self_cut + nonself_cut) > 1e-4 and regime_share >= target_vol_share:
                inferred = "lighter_both_regime_relief"
            elif regime_share > 0.5:
                inferred = "regime_multiplier"
            else:
                inferred = "other_or_none"
            rows.append(
                {
                    "name": version_name,
                    "state": state_name,
                    "regime_binding_share": regime_share,
                    "target_vol_binding_share": target_vol_share,
                    "none_binding_share": none_share,
                    "avg_self_gated_overlay_cut_risky": self_cut,
                    "avg_non_self_gated_overlay_cut_risky": nonself_cut,
                    "avg_overlay_cash_weight": overlay_cash,
                    "overlay_penalty_mode": a["overlay_penalty_mode"].mode().iloc[0] if "overlay_penalty_mode" in a.columns and not a.empty else "unknown",
                    "inferred_overlay_cash_source": inferred,
                    "vv_budget_override_share": vv_override,
                    "vv_target_vol_guardrail_share": vv_guardrail,
                    "avg_vv_budget_gap_post": vv_gap_post,
                }
            )
    return pd.DataFrame(rows)


def target_vol_guardrail_cases(diag_ts: pd.DataFrame, state_df: pd.DataFrame, versions: list[str]) -> pd.DataFrame:
    ts = diag_ts.copy()
    ts["Date"] = pd.to_datetime(ts["Date"]).dt.tz_localize(None)
    ts = ts.set_index("Date").join(state_df[["state_label"]], how="left")
    ts = ts[ts["version_name"].isin(versions)].copy()
    ts["target_vol_guardrail_active"] = pd.to_numeric(ts.get("target_vol_binding", 0.0), errors="coerce").fillna(0.0) > 0.0
    rows = []
    guard = ts[ts["target_vol_guardrail_active"]].copy()
    for (version_name, state_name), grp in guard.groupby(["version_name", "state_label"], dropna=False):
        rows.append(
            {
                "name": version_name,
                "state": state_name,
                "n_guardrail_weeks": int(len(grp)),
                "guardrail_share_within_state": float(len(grp) / max(1, len(ts[(ts["version_name"] == version_name) & (ts["state_label"] == state_name)]))),
                "avg_target_vol_multiplier": float(pd.to_numeric(grp.get("target_vol_multiplier"), errors="coerce").mean()),
                "avg_regime_multiplier": float(pd.to_numeric(grp.get("regime_multiplier"), errors="coerce").mean()),
                "avg_cash_weight": float(pd.to_numeric(grp.get("cash_weight"), errors="coerce").mean()),
                "avg_vv_target_cash_budget": float(pd.to_numeric(grp.get("vv_target_cash_budget"), errors="coerce").mean()),
                "avg_vv_budget_gap_post": float(pd.to_numeric(grp.get("vv_budget_gap_post"), errors="coerce").mean()),
                "avg_vv_budget_override_applied": float(pd.to_numeric(grp.get("vv_budget_override_applied"), errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def screen_candidate(
    row: pd.Series,
    prod_row: pd.Series,
    uu_row: pd.Series,
    state_summary: pd.DataFrame,
    candidate_diag: pd.DataFrame,
    guardrail_cases: pd.DataFrame,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if float(row["ann_return_delta_vs_prod"]) < -0.0030:
        reasons.append("annual return drag > 0.30pp vs production")
    if float(row["sharpe_delta_vs_prod"]) < 0.0050:
        reasons.append("Sharpe improvement < 0.005 vs production")
    if float(row["sharpe_delta_vs_uu"]) <= 0.0:
        reasons.append("Sharpe does not improve vs UU best")
    if float(row["max_drawdown_delta_vs_prod"]) < -0.0050:
        reasons.append("max drawdown worse by > 0.5pp vs production")
    if float(row["cvar_5_delta_vs_prod"]) < -0.0005:
        reasons.append("CVaR worse by > 0.05pp vs production")
    if float(row["avg_turnover"]) > 1.10 * float(prod_row["avg_turnover"]):
        reasons.append("turnover > 1.10x production")

    candidate_states = state_summary[state_summary["name"] == row["name"]].set_index("state")
    prod_states = state_summary[state_summary["name"] == PRODUCTION_NAME].set_index("state")
    if "stressed_panic" in candidate_states.index and "stressed_panic" in prod_states.index:
        if float(candidate_states.at["stressed_panic", "sharpe"] - prod_states.at["stressed_panic", "sharpe"]) < -0.05:
            reasons.append("stressed_panic worsens materially")
    if "recovery_fragile" in candidate_states.index and "recovery_fragile" in prod_states.index:
        if float(candidate_states.at["recovery_fragile", "ann_return"] - prod_states.at["recovery_fragile", "ann_return"]) < -0.005:
            reasons.append("recovery_fragile worsens materially")
    if float(row["avg_SPY_delta_vs_prod"]) > 0.010 and float(row["sharpe_delta_vs_prod"]) < 0.007:
        reasons.append("improvement leans too much on hidden SPY/beta")

    targeted = candidate_diag[
        (candidate_diag["name"] == row["name"])
        & (candidate_diag["state"].isin(TARGET_RECOVERY_STATES))
    ]
    if targeted.empty or float(targeted["overlay_absorption_reduction_vs_prod"].mean()) <= 0.0:
        reasons.append("overlay absorption is not reduced in recovery states")

    guard = guardrail_cases[guardrail_cases["name"] == row["name"]]
    if not guard.empty and float(guard["avg_vv_budget_override_applied"].fillna(0.0).max()) > 0.0:
        reasons.append("target-vol guardrails are overridden unsafely")

    return ("PASS" if not reasons else "REJECT"), reasons


def main() -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    print("Phase VV: loading state history...", flush=True)
    state_df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    state_df.index = pd.to_datetime(state_df.index).tz_localize(None)
    state_df = add_state_labels(state_df)

    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    weekly_returns.index = pd.to_datetime(weekly_returns.index).tz_localize(None)
    spy_returns = weekly_returns["SPY"].reindex(state_df.index).fillna(0.0)

    build_versions = [PRODUCTION_NAME, SHADOW_NAME, TT_REFERENCE_NAME, UU_REFERENCE_NAME] + VV_CANDIDATES
    build_env = os.environ.copy()
    build_env["BUILD_VERSION_NAMES"] = ",".join(build_versions)
    build_env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print("Phase VV: running filtered builder with production, TT1, UU best, and VV candidates...", flush=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")],
        cwd=ROOT,
        check=True,
        env=build_env,
    )
    print("Phase VV: builder run finished, aggregating diagnostics...", flush=True)

    comparison_names = [PRODUCTION_NAME, TT_REFERENCE_NAME, UU_REFERENCE_NAME] + VV_CANDIDATES
    absorption_frames = [state_budget_absorption(name, state_df) for name in comparison_names]
    absorption_df = pd.concat(absorption_frames, ignore_index=True)
    absorption_df.to_csv(RESEARCH_DIR / "phase_vv_overlay_budget_gap_by_state.csv", index=False)

    diag_ts = load_simple_csv(LAYER3_DIR / "portfolio_version_diagnostics_timeseries.csv")
    stacked_ts = load_simple_csv(LAYER3_DIR / "stacked_defense_timeseries.csv")
    branch_diag = infer_branch_diagnostics(diag_ts, stacked_ts, state_df, comparison_names)
    branch_budget_gap = absorption_df.merge(
        branch_diag,
        on=["name", "state"],
        how="left",
    ).sort_values(["name", "state"])
    branch_budget_gap.to_csv(RESEARCH_DIR / "phase_vv_overlay_branch_budget_gap.csv", index=False)

    guardrail_df = target_vol_guardrail_cases(diag_ts, state_df, comparison_names)
    guardrail_df.to_csv(RESEARCH_DIR / "phase_vv_target_vol_guardrail_cases.csv", index=False)

    metrics_rows = []
    state_summary_frames = []
    holdout_start = pd.Timestamp("2024-04-19")
    recovery_mask = state_df["state_label"].isin(["recovery_confirmed", "recovery_fragile"])
    reporting_names = [PRODUCTION_NAME, SHADOW_NAME, TT_REFERENCE_NAME, UU_REFERENCE_NAME] + VV_CANDIDATES
    for version_name in reporting_names:
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
                "missing": False,
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
        state_summary_frames.append(state_summary_for_version(version_name, returns_df, sleeve_df, etf_df, state_df))

    metrics_df = pd.DataFrame(metrics_rows)
    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    shadow_row = metrics_df[metrics_df["name"] == SHADOW_NAME].iloc[0]
    tt1_row = metrics_df[metrics_df["name"] == TT_REFERENCE_NAME].iloc[0]
    uu_row = metrics_df[metrics_df["name"] == UU_REFERENCE_NAME].iloc[0]
    for base_name, base_row in [("prod", prod_row), ("shadow", shadow_row), ("tt1", tt1_row), ("uu", uu_row)]:
        for col in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_SPY", "avg_offense", "avg_defense", "avg_cash"]:
            metrics_df[f"{col}_delta_vs_{base_name}"] = metrics_df[col] - float(base_row[col])

    state_summary_df = pd.concat(state_summary_frames, ignore_index=True)
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
    prod_branch = branch_diag[branch_diag["name"] == PRODUCTION_NAME].set_index("state")
    tt_branch = branch_diag[branch_diag["name"] == TT_REFERENCE_NAME].set_index("state")
    uu_branch = branch_diag[branch_diag["name"] == UU_REFERENCE_NAME].set_index("state")
    guard_idx = guardrail_df.set_index(["name", "state"]) if not guardrail_df.empty else pd.DataFrame()
    for candidate_name in VV_CANDIDATES:
        cand_abs = absorption_df[absorption_df["name"] == candidate_name]
        cand_branch = branch_diag[branch_diag["name"] == candidate_name].set_index("state")
        for _, row in cand_abs.iterrows():
            state_name = row["state"]
            guard_row = guard_idx.loc[(candidate_name, state_name)] if not guardrail_df.empty and (candidate_name, state_name) in guard_idx.index else None
            candidate_diag_rows.append(
                {
                    "name": candidate_name,
                    "state": state_name,
                    "state_targeted": float(state_name in TARGET_RECOVERY_STATES),
                    "intended_risky_budget": float(row["intended_risky_budget"]),
                    "intended_cash_budget": float(row["intended_cash_budget"]),
                    "stage1_risky_budget": float(row["stage1_risky_budget"]),
                    "stage1_cash_budget": float(row["stage1_cash_budget"]),
                    "post_overlay_risky_budget": float(row["post_overlay_risky_budget"]),
                    "post_overlay_cash_budget": float(row["post_overlay_cash_budget"]),
                    "final_etf_risky_budget": float(row["final_etf_risky_budget"]),
                    "final_etf_cash_budget": float(row["final_etf_cash_budget"]),
                    "overlay_cash_added": float(row["overlay_cash_added"]),
                    "overlay_absorption": float(row["overlay_absorption"]),
                    "lookthrough_absorption": float(row["lookthrough_absorption"]),
                    "total_absorption": float(row["total_absorption"]),
                    "post_overlay_budget_gap": float(row["post_overlay_budget_gap"]),
                    "final_etf_budget_gap": float(row["final_etf_budget_gap"]),
                    "overlay_absorption_reduction_vs_prod": float(prod_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]),
                    "overlay_absorption_reduction_vs_tt1": float(tt_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]),
                    "overlay_absorption_reduction_vs_uu": float(uu_abs.at[state_name, "overlay_absorption"] - row["overlay_absorption"]),
                    "budget_gap_reduction_vs_prod": float(prod_abs.at[state_name, "post_overlay_budget_gap"] - row["post_overlay_budget_gap"]),
                    "budget_gap_reduction_vs_tt1": float(tt_abs.at[state_name, "post_overlay_budget_gap"] - row["post_overlay_budget_gap"]),
                    "budget_gap_reduction_vs_uu": float(uu_abs.at[state_name, "post_overlay_budget_gap"] - row["post_overlay_budget_gap"]),
                    "total_absorption_reduction_vs_prod": float(prod_abs.at[state_name, "total_absorption"] - row["total_absorption"]),
                    "total_absorption_reduction_vs_tt1": float(tt_abs.at[state_name, "total_absorption"] - row["total_absorption"]),
                    "total_absorption_reduction_vs_uu": float(uu_abs.at[state_name, "total_absorption"] - row["total_absorption"]),
                    "inferred_overlay_cash_source": cand_branch.at[state_name, "inferred_overlay_cash_source"] if state_name in cand_branch.index else "unknown",
                    "regime_binding_share": float(cand_branch.at[state_name, "regime_binding_share"]) if state_name in cand_branch.index else np.nan,
                    "target_vol_binding_share": float(cand_branch.at[state_name, "target_vol_binding_share"]) if state_name in cand_branch.index else np.nan,
                    "avg_self_gated_overlay_cut_risky": float(cand_branch.at[state_name, "avg_self_gated_overlay_cut_risky"]) if state_name in cand_branch.index else np.nan,
                    "avg_non_self_gated_overlay_cut_risky": float(cand_branch.at[state_name, "avg_non_self_gated_overlay_cut_risky"]) if state_name in cand_branch.index else np.nan,
                    "self_gated_overlay_cut_reduction_vs_prod": float(prod_branch.at[state_name, "avg_self_gated_overlay_cut_risky"] - cand_branch.at[state_name, "avg_self_gated_overlay_cut_risky"]) if state_name in cand_branch.index and state_name in prod_branch.index else np.nan,
                    "non_self_gated_overlay_cut_reduction_vs_prod": float(prod_branch.at[state_name, "avg_non_self_gated_overlay_cut_risky"] - cand_branch.at[state_name, "avg_non_self_gated_overlay_cut_risky"]) if state_name in cand_branch.index and state_name in prod_branch.index else np.nan,
                    "vv_budget_override_share": float(cand_branch.at[state_name, "vv_budget_override_share"]) if state_name in cand_branch.index else np.nan,
                    "vv_target_vol_guardrail_share": float(cand_branch.at[state_name, "vv_target_vol_guardrail_share"]) if state_name in cand_branch.index else np.nan,
                    "target_vol_guardrail_weeks": int(guard_row["n_guardrail_weeks"]) if guard_row is not None else 0,
                    "target_vol_guardrail_override_rate": float(guard_row["avg_vv_budget_override_applied"]) if guard_row is not None else 0.0,
                }
            )
    candidate_diag_df = pd.DataFrame(candidate_diag_rows)
    candidate_diag_df.to_csv(RESEARCH_DIR / "phase_vv_candidate_diagnostics.csv", index=False)

    selection_rows = []
    for candidate_name in VV_CANDIDATES:
        candidate_row = metrics_df[metrics_df["name"] == candidate_name].iloc[0]
        status, reasons = screen_candidate(candidate_row, prod_row, uu_row, state_summary_df, candidate_diag_df, guardrail_df)
        targeted = candidate_diag_df[
            (candidate_diag_df["name"] == candidate_name)
            & (candidate_diag_df["state"].isin(TARGET_RECOVERY_STATES))
        ]
        selection_rows.append(
            {
                "name": candidate_name,
                "quick_screen_status": status,
                "quick_screen_reasons": " | ".join(reasons),
                "ann_return_delta_vs_prod": float(candidate_row["ann_return_delta_vs_prod"]),
                "sharpe_delta_vs_prod": float(candidate_row["sharpe_delta_vs_prod"]),
                "sharpe_delta_vs_uu": float(candidate_row["sharpe_delta_vs_uu"]),
                "avg_BIL_delta_vs_prod": float(candidate_row["avg_BIL_delta_vs_prod"]),
                "avg_SPY_delta_vs_prod": float(candidate_row["avg_SPY_delta_vs_prod"]),
                "avg_bucket_composite_delta_vs_prod": float(candidate_row["avg_bucket_composite"] - prod_row["avg_bucket_composite"]),
                "avg_bucket_offense_delta_vs_prod": float(candidate_row["avg_bucket_offense"] - prod_row["avg_bucket_offense"]),
                "targeted_overlay_absorption_reduction_vs_prod": float(targeted["overlay_absorption_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "targeted_overlay_absorption_reduction_vs_tt1": float(targeted["overlay_absorption_reduction_vs_tt1"].mean()) if not targeted.empty else np.nan,
                "targeted_overlay_absorption_reduction_vs_uu": float(targeted["overlay_absorption_reduction_vs_uu"].mean()) if not targeted.empty else np.nan,
                "targeted_budget_gap_reduction_vs_prod": float(targeted["budget_gap_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "targeted_budget_gap_reduction_vs_uu": float(targeted["budget_gap_reduction_vs_uu"].mean()) if not targeted.empty else np.nan,
                "targeted_total_absorption_reduction_vs_prod": float(targeted["total_absorption_reduction_vs_prod"].mean()) if not targeted.empty else np.nan,
                "targeted_total_absorption_reduction_vs_uu": float(targeted["total_absorption_reduction_vs_uu"].mean()) if not targeted.empty else np.nan,
            }
        )
    selection_df = pd.DataFrame(selection_rows).sort_values(
        ["quick_screen_status", "sharpe_delta_vs_prod", "ann_return_delta_vs_prod"],
        ascending=[True, False, False],
    )
    best_candidate = selection_df.sort_values(
        ["sharpe_delta_vs_prod", "ann_return_delta_vs_prod"],
        ascending=[False, False],
    ).iloc[0]["name"]

    metrics_df.to_csv(LAYER3_DIR / "phase_vv_candidate_metrics_full.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_vv_state_summary.csv", index=False)
    selection_df.to_csv(LAYER3_DIR / "phase_vv_selection_table.csv", index=False)

    protocol = {
        "phase": "VV",
        "production_pin": PRODUCTION_NAME,
        "shadow_pin": SHADOW_NAME,
        "tt_reference": TT_REFERENCE_NAME,
        "uu_reference": UU_REFERENCE_NAME,
        "candidates": VV_CANDIDATES,
        "best_candidate": best_candidate,
        "selection_rule": {
            "annual_return_drag_vs_prod": -0.0030,
            "min_sharpe_delta_vs_prod": 0.0050,
            "must_improve_sharpe_vs_uu": True,
            "max_drawdown_worsening_vs_prod": -0.0050,
            "cvar_worsening_vs_prod": -0.0005,
            "max_turnover_multiple_vs_prod": 1.10,
            "require_recovery_overlay_absorption_reduction": True,
            "require_safe_target_vol_guardrails": True,
        },
    }
    (LAYER3_DIR / "phase_vv_protocol.json").write_text(json.dumps(protocol, indent=2))

    print(f"Phase VV complete. Best candidate: {best_candidate}")
    print(f"Diagnostics saved to {RESEARCH_DIR}")


if __name__ == "__main__":
    main()
