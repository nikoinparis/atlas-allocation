from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
RESEARCH_DIR = ROOT / "data" / "research" / "phase_ss_explicit_bucket_allocator"

PRODUCTION_NAME = "improved_phase2b_regime_confidence_boost"
SHADOW_NAME = "improved_phase2b_combo_abc"
RR_REFERENCE_NAME = "improved_phaserr_combined_bucket_allocator"
SS_CANDIDATES = [
    "improved_phasess_recovery_explicit_bucket",
    "improved_phasess_good_state_explicit_bucket",
    "improved_phasess_combined_explicit_bucket",
]
STATE_ORDER = [
    "calm_trend",
    "neutral_healthy_proxy",
    "neutral_mixed",
    "recovery_confirmed",
    "recovery_fragile",
    "stressed_panic",
]
SLEEVE_BUCKET_MAP = {
    "dual_momentum_topn": "offense",
    "cta_trend_long_only": "offense",
    "composite_selective_signals": "offense",
    "taa_10m_sma": "defense",
    "composite_regime_conditioned": "composite",
    "cash::BIL": "cash",
}
ETF_DEFENSIVE = {"IEF", "SHY", "TLT", "TIP", "GLD", "LQD", "MBB", "UUP"}
TARGET_BUDGETS = {
    "calm_trend": {"offense": 0.56, "defense": 0.19, "composite": 0.25, "cash": 0.05},
    "neutral_healthy_proxy": {"offense": 0.50, "defense": 0.18, "composite": 0.23, "cash": 0.09},
    "recovery_confirmed": {"offense": 0.51, "defense": 0.20, "composite": 0.24, "cash": 0.07},
    "recovery_fragile": {"offense": 0.47, "defense": 0.19, "composite": 0.23, "cash": 0.11},
    "stressed_panic": {"offense": 0.24, "defense": 0.08, "composite": 0.17, "cash": 0.51},
}
CANDIDATE_STATE_APPLY = {
    "improved_phasess_recovery_explicit_bucket": {"recovery_confirmed", "recovery_fragile"},
    "improved_phasess_good_state_explicit_bucket": {"calm_trend", "neutral_healthy_proxy"},
    "improved_phasess_combined_explicit_bucket": {"calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"},
}


def load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    first_col = frame.columns[0]
    frame[first_col] = pd.to_datetime(frame[first_col]).dt.tz_localize(None)
    return frame.rename(columns={first_col: "Date"}).set_index("Date").sort_index()


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
        rows.append(
            {
                "name": name,
                "state": state_name,
                "n_weeks": int(mask.sum()),
                "ann_return": annual_return(state_returns),
                "sharpe": sharpe_ratio(state_returns),
                "avg_BIL": float(state_etf["BIL"].mean()) if "BIL" in state_etf.columns else 0.0,
                "avg_SPY": float(state_etf["SPY"].mean()) if "SPY" in state_etf.columns else 0.0,
                "avg_offense": avg_etf_exposures(state_etf)["avg_offense"],
                "avg_defense": avg_etf_exposures(state_etf)["avg_defense"],
                "avg_cash": avg_etf_exposures(state_etf)["avg_cash"],
                "bucket_offense": float(state_bucket["offense"].mean()),
                "bucket_defense": float(state_bucket["defense"].mean()),
                "bucket_composite": float(state_bucket["composite"].mean()),
                "bucket_cash": float(state_bucket["cash"].mean()),
            }
        )
    return pd.DataFrame(rows)


def screen_candidate(row: pd.Series, prod_row: pd.Series, state_summary: pd.DataFrame) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if float(row["ann_return_delta_vs_prod"]) < -0.0030:
        reasons.append("annual return drag > 0.30pp")
    if float(row["sharpe_delta_vs_prod"]) < 0.0050:
        reasons.append("Sharpe improvement < 0.005")
    if float(row["max_drawdown_delta_vs_prod"]) < -0.0050:
        reasons.append("max drawdown worse by > 0.5pp")
    if float(row["cvar_5_delta_vs_prod"]) < -0.0005:
        reasons.append("CVaR worse by > 0.05pp")
    if float(row["avg_turnover"]) > 1.10 * float(prod_row["avg_turnover"]):
        reasons.append("turnover > 1.10x production")

    candidate_states = state_summary[state_summary["name"] == row["name"]].set_index("state")
    prod_states = state_summary[state_summary["name"] == PRODUCTION_NAME].set_index("state")
    if "stressed_panic" in candidate_states.index and "stressed_panic" in prod_states.index:
        if float(candidate_states.at["stressed_panic", "sharpe"] - prod_states.at["stressed_panic", "sharpe"]) < -0.05:
            reasons.append("stressed_panic Sharpe worsened materially")
    if "recovery_fragile" in candidate_states.index and "recovery_fragile" in prod_states.index:
        if float(candidate_states.at["recovery_fragile", "ann_return"] - prod_states.at["recovery_fragile", "ann_return"]) < -0.005:
            reasons.append("recovery_fragile worsened materially")
    if float(row["avg_SPY_delta_vs_prod"]) > 0.010 and float(row["sharpe_delta_vs_prod"]) < 0.007:
        reasons.append("improvement leans too much on extra SPY without enough Sharpe")

    bottleneck_states = ["calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"]
    improved_bottleneck = False
    for state_name in bottleneck_states:
        if state_name in candidate_states.index and state_name in prod_states.index:
            if float(candidate_states.at[state_name, "ann_return"] - prod_states.at[state_name, "ann_return"]) > 0.0:
                improved_bottleneck = True
                break
    if not improved_bottleneck:
        reasons.append("bottleneck states not improved")
    return ("PASS" if not reasons else "REJECT"), reasons


def main() -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    print("Phase SS: loading production artifacts...", flush=True)

    state_df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    state_df.index = pd.to_datetime(state_df.index).tz_localize(None)
    state_df = add_state_labels(state_df)

    production_sleeve_weights = load_frame(LAYER3_DIR / f"portfolio_version_sleeve_weights_{PRODUCTION_NAME}.csv")
    production_returns = load_frame(LAYER3_DIR / f"portfolio_version_returns_{PRODUCTION_NAME}.csv")
    production_etf_weights = load_frame(LAYER3_DIR / f"portfolio_version_weights_{PRODUCTION_NAME}.csv")
    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    weekly_returns.index = pd.to_datetime(weekly_returns.index).tz_localize(None)
    spy_returns = weekly_returns["SPY"].reindex(state_df.index).fillna(0.0)

    current_bucket_weights = bucket_series(production_sleeve_weights.reindex(state_df.index).fillna(0.0))
    current_rows = []
    for state_name in STATE_ORDER:
        mask = state_df["state_label"].eq(state_name)
        if int(mask.sum()) == 0:
            continue
        row = {
            "state": state_name,
            "n_weeks": int(mask.sum()),
            "current_offense": float(current_bucket_weights.loc[mask, "offense"].mean()),
            "current_defense": float(current_bucket_weights.loc[mask, "defense"].mean()),
            "current_composite": float(current_bucket_weights.loc[mask, "composite"].mean()),
            "current_cash": float(current_bucket_weights.loc[mask, "cash"].mean()),
        }
        current_rows.append(row)
    current_df = pd.DataFrame(current_rows)
    current_df.to_csv(RESEARCH_DIR / "phase_ss_current_bucket_weights_by_state.csv", index=False)

    target_rows = []
    for state_name, targets in TARGET_BUDGETS.items():
        target_rows.append(
            {
                "state": state_name,
                "target_offense": targets["offense"],
                "target_defense": targets["defense"],
                "target_composite": targets["composite"],
                "target_cash": targets["cash"],
                "risky_budget_total": 1.0 - targets["cash"],
                "normalized_risky_offense": targets["offense"] / max(1e-12, 1.0 - targets["cash"]),
                "normalized_risky_defense": targets["defense"] / max(1e-12, 1.0 - targets["cash"]),
                "normalized_risky_composite": targets["composite"] / max(1e-12, 1.0 - targets["cash"]),
            }
        )
    target_df = pd.DataFrame(target_rows)
    target_df.to_csv(RESEARCH_DIR / "phase_ss_target_bucket_budget_table.csv", index=False)

    gap_df = current_df.merge(target_df, on="state", how="left")
    for bucket in ["offense", "defense", "composite", "cash"]:
        gap_df[f"{bucket}_gap"] = gap_df[f"current_{bucket}"] - gap_df[f"target_{bucket}"]
    gap_df.to_csv(RESEARCH_DIR / "phase_ss_bucket_gap_by_state.csv", index=False)
    print("Phase SS: saved current bucket weights, targets, and gaps.", flush=True)

    build_env = os.environ.copy()
    build_env["BUILD_VERSION_NAMES"] = ",".join(SS_CANDIDATES)
    print("Phase SS: running filtered builder for SS candidates...", flush=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")],
        cwd=ROOT,
        check=True,
        env=build_env,
    )
    print("Phase SS: builder run finished, aggregating results...", flush=True)

    comparison_names = [PRODUCTION_NAME, SHADOW_NAME, RR_REFERENCE_NAME] + SS_CANDIDATES
    metrics_rows = []
    state_summary_frames = []
    candidate_diag_rows = []
    holdout_start = pd.Timestamp("2024-04-19")
    recovery_mask = state_df["state_label"].isin(["recovery_confirmed", "recovery_fragile"])

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
        state_summary = state_summary_for_version(version_name, returns_df, sleeve_df, etf_df, state_df)
        state_summary_frames.append(state_summary)

        if version_name in SS_CANDIDATES:
            for _, row in state_summary.iterrows():
                state_name = row["state"]
                if state_name not in TARGET_BUDGETS:
                    continue
                target = TARGET_BUDGETS[state_name]
                candidate_diag_rows.append(
                    {
                        "name": version_name,
                        "state": state_name,
                        "state_targeted": float(state_name in CANDIDATE_STATE_APPLY[version_name]),
                        "target_offense": target["offense"],
                        "target_defense": target["defense"],
                        "target_composite": target["composite"],
                        "target_cash": target["cash"],
                        "realized_bucket_offense": float(row["bucket_offense"]),
                        "realized_bucket_defense": float(row["bucket_defense"]),
                        "realized_bucket_composite": float(row["bucket_composite"]),
                        "realized_bucket_cash": float(row["bucket_cash"]),
                        "offense_gap": float(row["bucket_offense"] - target["offense"]),
                        "defense_gap": float(row["bucket_defense"] - target["defense"]),
                        "composite_gap": float(row["bucket_composite"] - target["composite"]),
                        "cash_gap": float(row["bucket_cash"] - target["cash"]),
                        "avg_BIL": float(row["avg_BIL"]),
                        "avg_SPY": float(row["avg_SPY"]),
                        "ann_return": float(row["ann_return"]),
                        "sharpe": float(row["sharpe"]),
                    }
                )

    metrics_df = pd.DataFrame(metrics_rows)
    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    shadow_row = metrics_df[metrics_df["name"] == SHADOW_NAME].iloc[0]
    rr_row = metrics_df[metrics_df["name"] == RR_REFERENCE_NAME].iloc[0]

    for base_name, base_row in [("prod", prod_row), ("shadow", shadow_row), ("rr_best", rr_row)]:
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

    selection_rows = []
    for candidate_name in SS_CANDIDATES:
        candidate_row = metrics_df[metrics_df["name"] == candidate_name].iloc[0]
        status, reasons = screen_candidate(candidate_row, prod_row, state_summary_df)
        selection_rows.append(
            {
                "name": candidate_name,
                "quick_screen_status": status,
                "quick_screen_reasons": " | ".join(reasons),
                "ann_return_delta_vs_prod": float(candidate_row["ann_return_delta_vs_prod"]),
                "sharpe_delta_vs_prod": float(candidate_row["sharpe_delta_vs_prod"]),
                "avg_BIL_delta_vs_prod": float(candidate_row["avg_BIL_delta_vs_prod"]),
                "avg_SPY_delta_vs_prod": float(candidate_row["avg_SPY_delta_vs_prod"]),
                "avg_bucket_composite_delta_vs_prod": float(candidate_row["avg_bucket_composite"] - prod_row["avg_bucket_composite"]),
                "avg_bucket_offense_delta_vs_prod": float(candidate_row["avg_bucket_offense"] - prod_row["avg_bucket_offense"]),
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

    metrics_df.to_csv(LAYER3_DIR / "phase_ss_candidate_metrics_full.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_ss_state_summary.csv", index=False)
    selection_df.to_csv(LAYER3_DIR / "phase_ss_selection_table.csv", index=False)
    pd.DataFrame(candidate_diag_rows).to_csv(RESEARCH_DIR / "phase_ss_candidate_diagnostics.csv", index=False)

    protocol = {
        "phase": "SS",
        "production_pin": PRODUCTION_NAME,
        "shadow_pin": SHADOW_NAME,
        "rr_reference": RR_REFERENCE_NAME,
        "candidates": SS_CANDIDATES,
        "best_candidate": best_candidate,
        "selection_rule": {
            "annual_return_drag_vs_prod": -0.0030,
            "min_sharpe_delta_vs_prod": 0.0050,
            "max_drawdown_worsening_vs_prod": -0.0050,
            "cvar_worsening_vs_prod": -0.0005,
            "max_turnover_multiple_vs_prod": 1.10,
        },
        "target_budgets": TARGET_BUDGETS,
    }
    (LAYER3_DIR / "phase_ss_protocol.json").write_text(json.dumps(protocol, indent=2))

    print(f"Phase SS complete. Best candidate: {best_candidate}")
    print(f"Diagnostics saved to {RESEARCH_DIR}")


if __name__ == "__main__":
    main()
