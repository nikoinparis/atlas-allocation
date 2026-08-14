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
RESEARCH_DIR = ROOT / "data" / "research" / "phase_rr_bucket_allocator"

RR_CANDIDATES = [
    "improved_phaserr_good_state_bucket_participation",
    "improved_phaserr_recovery_bucket_repair",
    "improved_phaserr_combined_bucket_allocator",
]
PRODUCTION_NAME = "improved_phase2b_regime_confidence_boost"
SHADOW_NAME = "improved_phase2b_combo_abc"
QQ_REFERENCE_NAME = "improved_phaseqq_pp_combined_score_filtered"
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
    strong = strong_neutral_mask(out)
    out["state_label"] = out["market_state"]
    out.loc[strong, "state_label"] = "neutral_healthy_proxy"
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


def correlation(lhs: pd.Series, rhs: pd.Series) -> float:
    aligned = pd.concat([pd.Series(lhs, dtype=float), pd.Series(rhs, dtype=float)], axis=1).dropna()
    if len(aligned) < 10:
        return np.nan
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))


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


def bucket_return_series(sleeve_weights: pd.DataFrame, sleeve_returns: pd.DataFrame, cash_returns: pd.Series) -> pd.DataFrame:
    bucket_weights = bucket_series(sleeve_weights)
    out = pd.DataFrame(index=sleeve_weights.index)
    for bucket in ["offense", "defense", "composite"]:
        cols = [name for name, bucket_name in SLEEVE_BUCKET_MAP.items() if bucket_name == bucket and name in sleeve_weights.columns]
        if not cols:
            out[bucket] = 0.0
            continue
        bucket_alloc = sleeve_weights.reindex(columns=cols).fillna(0.0)
        bucket_total = bucket_alloc.sum(axis=1).replace(0.0, np.nan)
        bucket_internal = bucket_alloc.div(bucket_total, axis=0).fillna(0.0)
        out[bucket] = (bucket_internal * sleeve_returns.reindex(columns=cols).fillna(0.0)).sum(axis=1)
    out["cash"] = pd.Series(cash_returns, index=out.index).fillna(0.0)
    out["bucket_cash_weight"] = bucket_weights["cash"]
    return out


def state_metric_rows(
    series_map: dict[str, pd.Series],
    state_labels: pd.Series,
    *,
    extra_fields: dict[str, dict[str, float]] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for label in STATE_ORDER:
        mask = state_labels.eq(label)
        n_weeks = int(mask.sum())
        if n_weeks == 0:
            continue
        for name, series in series_map.items():
            s = pd.Series(series, index=state_labels.index).loc[mask]
            metrics = summary_metrics(s)
            row = {"name": name, "state": label, "n_weeks": n_weeks, **metrics}
            if extra_fields and name in extra_fields:
                row.update(extra_fields[name])
            rows.append(row)
    return rows


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
    print("Phase RR: loading production state and portfolio artifacts...", flush=True)

    state_df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    state_df.index = pd.to_datetime(state_df.index).tz_localize(None)
    state_df = add_state_labels(state_df)

    production_sleeve_weights = load_frame(LAYER3_DIR / f"portfolio_version_sleeve_weights_{PRODUCTION_NAME}.csv")
    production_returns = load_frame(LAYER3_DIR / f"portfolio_version_returns_{PRODUCTION_NAME}.csv")
    production_etf_weights = load_frame(LAYER3_DIR / f"portfolio_version_weights_{PRODUCTION_NAME}.csv")
    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    weekly_returns.index = pd.to_datetime(weekly_returns.index).tz_localize(None)
    spy_returns = weekly_returns["SPY"].reindex(state_df.index).fillna(0.0)
    bil_returns = weekly_returns["BIL"].reindex(state_df.index).fillna(0.0)

    sleeve_names = [name for name in production_sleeve_weights.columns if name in SLEEVE_BUCKET_MAP and name != "cash::BIL"]
    sleeve_returns = {}
    for name in sleeve_names:
        frame = pd.read_csv(LAYER2A_DIR / f"strategy_returns_{name}.csv", parse_dates=["Date"]).set_index("Date").sort_index()
        col = "net_return" if "net_return" in frame.columns else frame.columns[0]
        sleeve_returns[name] = frame[col].reindex(state_df.index).fillna(0.0)
    sleeve_return_df = pd.DataFrame(sleeve_returns)
    sleeve_return_df["cash::BIL"] = bil_returns.reindex(sleeve_return_df.index).fillna(0.0)

    production_net = production_returns["net_return"].reindex(state_df.index).fillna(0.0)

    classification_rows = []
    state_perf_rows = []
    sleeve_corr = sleeve_return_df.reindex(columns=[c for c in SLEEVE_BUCKET_MAP if c in sleeve_return_df.columns]).corr()
    sleeve_corr.to_csv(RESEARCH_DIR / "phase_rr_sleeve_correlation_matrix.csv")

    for sleeve_name, bucket_name in SLEEVE_BUCKET_MAP.items():
        if sleeve_name not in sleeve_return_df.columns:
            continue
        series = sleeve_return_df[sleeve_name]
        full_metrics = summary_metrics(series)
        helps = []
        hurts = []
        for state_name in STATE_ORDER:
            mask = state_df["state_label"].eq(state_name)
            if int(mask.sum()) == 0:
                continue
            state_series = series.loc[mask]
            state_metrics = summary_metrics(state_series)
            state_perf_rows.append(
                {
                    "sleeve_name": sleeve_name,
                    "bucket": bucket_name,
                    "state": state_name,
                    "n_weeks": int(mask.sum()),
                    **state_metrics,
                    "avg_weight_in_production": float(production_sleeve_weights.loc[mask, sleeve_name].mean()) if sleeve_name in production_sleeve_weights.columns else np.nan,
                }
            )
            if np.isfinite(state_metrics["sharpe"]):
                if state_metrics["sharpe"] >= 0.50:
                    helps.append(state_name)
                if state_metrics["sharpe"] <= 0.0:
                    hurts.append(state_name)
        classification_rows.append(
            {
                "sleeve_name": sleeve_name,
                "bucket": bucket_name,
                **full_metrics,
                "avg_weight_in_production": float(production_sleeve_weights[sleeve_name].mean()) if sleeve_name in production_sleeve_weights.columns else np.nan,
                "corr_with_production": correlation(series, production_net),
                "corr_with_spy": correlation(series, spy_returns),
                "corr_with_bil": correlation(series, bil_returns),
                "helps_in_states": "|".join(helps),
                "hurts_in_states": "|".join(hurts),
            }
        )

    classification_df = pd.DataFrame(classification_rows).sort_values(["bucket", "avg_weight_in_production"], ascending=[True, False])
    state_perf_df = pd.DataFrame(state_perf_rows).sort_values(["state", "bucket", "sharpe"], ascending=[True, True, False])
    classification_df.to_csv(RESEARCH_DIR / "phase_rr_sleeve_bucket_classification.csv", index=False)
    state_perf_df.to_csv(RESEARCH_DIR / "phase_rr_sleeve_state_performance.csv", index=False)
    print("Phase RR: saved sleeve and bucket diagnostics.", flush=True)

    bucket_return_df = bucket_return_series(production_sleeve_weights.reindex(state_df.index).fillna(0.0), sleeve_return_df, bil_returns)
    bucket_rows = []
    for bucket_name in ["offense", "defense", "composite", "cash"]:
        for state_name in STATE_ORDER:
            mask = state_df["state_label"].eq(state_name)
            if int(mask.sum()) == 0:
                continue
            series = bucket_return_df.loc[mask, bucket_name]
            bucket_rows.append(
                {
                    "bucket": bucket_name,
                    "state": state_name,
                    "n_weeks": int(mask.sum()),
                    **summary_metrics(series),
                    "avg_bucket_weight": float(bucket_series(production_sleeve_weights).loc[mask, bucket_name].mean()),
                }
            )
    bucket_state_df = pd.DataFrame(bucket_rows)
    bucket_state_df.to_csv(RESEARCH_DIR / "phase_rr_bucket_state_performance.csv", index=False)

    current_bucket_rows = []
    for state_name in STATE_ORDER:
        mask = state_df["state_label"].eq(state_name)
        if int(mask.sum()) == 0:
            continue
        sub_sleeve = production_sleeve_weights.loc[mask]
        sub_etf = production_etf_weights.loc[mask]
        current_bucket_rows.append(
            {
                "state": state_name,
                "n_weeks": int(mask.sum()),
                "bucket_offense": float(bucket_series(sub_sleeve)["offense"].mean()),
                "bucket_defense": float(bucket_series(sub_sleeve)["defense"].mean()),
                "bucket_composite": float(bucket_series(sub_sleeve)["composite"].mean()),
                "bucket_cash": float(bucket_series(sub_sleeve)["cash"].mean()),
                **avg_etf_exposures(sub_etf),
                "prod_ann_return": annual_return(production_net.loc[mask]),
                "prod_sharpe": sharpe_ratio(production_net.loc[mask]),
                "spy_ann_return": annual_return(spy_returns.loc[mask]),
                "spy_sharpe": sharpe_ratio(spy_returns.loc[mask]),
            }
        )
    current_bucket_df = pd.DataFrame(current_bucket_rows)
    current_bucket_df.to_csv(RESEARCH_DIR / "phase_rr_current_bucket_exposure_by_state.csv", index=False)

    bottleneck_rows = []
    for row in current_bucket_rows:
        state_name = row["state"]
        if state_name == "calm_trend":
            bottleneck_rows.append(
                {
                    "state": state_name,
                    "bottleneck": "good_state participation still leans too heavily on composite drag",
                    "severity": "HIGH",
                    "evidence": f"bucket_composite={row['bucket_composite']:.3f}, bucket_cash={row['bucket_cash']:.3f}, prod_ann_return={row['prod_ann_return']:.4f}, spy_ann_return={row['spy_ann_return']:.4f}",
                    "suggested_rr_candidate": "improved_phaserr_good_state_bucket_participation",
                }
            )
        elif state_name == "neutral_healthy_proxy":
            bottleneck_rows.append(
                {
                    "state": state_name,
                    "bottleneck": "healthy neutral still carries too much composite plus sleeve-level cash drag",
                    "severity": "HIGH",
                    "evidence": f"bucket_composite={row['bucket_composite']:.3f}, bucket_cash={row['bucket_cash']:.3f}, avg_BIL={row['avg_BIL']:.3f}",
                    "suggested_rr_candidate": "improved_phaserr_good_state_bucket_participation",
                }
            )
        elif state_name == "recovery_confirmed":
            bottleneck_rows.append(
                {
                    "state": state_name,
                    "bottleneck": "recovery mix still overweights composite and weak recovery offense",
                    "severity": "HIGH",
                    "evidence": f"bucket_composite={row['bucket_composite']:.3f}, bucket_defense={row['bucket_defense']:.3f}, avg_BIL={row['avg_BIL']:.3f}",
                    "suggested_rr_candidate": "improved_phaserr_recovery_bucket_repair",
                }
            )
        elif state_name == "recovery_fragile":
            bottleneck_rows.append(
                {
                    "state": state_name,
                    "bottleneck": "fragile recovery still carries too much composite/cash drag into the rerisk handoff",
                    "severity": "HIGH",
                    "evidence": f"bucket_composite={row['bucket_composite']:.3f}, bucket_cash={row['bucket_cash']:.3f}, avg_BIL={row['avg_BIL']:.3f}",
                    "suggested_rr_candidate": "improved_phaserr_recovery_bucket_repair",
                }
            )
        elif state_name == "stressed_panic":
            bottleneck_rows.append(
                {
                    "state": state_name,
                    "bottleneck": "stress defense looks appropriate; this state is mainly a guardrail",
                    "severity": "LOW",
                    "evidence": f"bucket_cash={row['bucket_cash']:.3f}, avg_BIL={row['avg_BIL']:.3f}, prod_sharpe={row['prod_sharpe']:.3f}",
                    "suggested_rr_candidate": "preserve current behavior",
                }
            )
    pd.DataFrame(bottleneck_rows).to_csv(RESEARCH_DIR / "phase_rr_bucket_bottleneck_summary.csv", index=False)
    print("Phase RR: running filtered builder for RR candidates...", flush=True)

    build_env = os.environ.copy()
    build_env["BUILD_VERSION_NAMES"] = ",".join(RR_CANDIDATES)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")],
        cwd=ROOT,
        check=True,
        env=build_env,
    )
    print("Phase RR: builder run finished, aggregating candidate results...", flush=True)

    comparison_names = [PRODUCTION_NAME, SHADOW_NAME, QQ_REFERENCE_NAME] + RR_CANDIDATES
    metrics_rows = []
    state_summary_frames = []
    production_state_summary = None

    holdout_start = pd.Timestamp("2024-04-19")
    recovery_mask = state_df["state_label"].isin(["recovery_confirmed", "recovery_fragile"])

    for version_name in comparison_names:
        returns_df = load_frame(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")
        sleeve_df = load_frame(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv")
        etf_df = load_frame(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")

        returns_df = returns_df.reindex(state_df.index).fillna(0.0)
        sleeve_df = sleeve_df.reindex(state_df.index).fillna(0.0)
        etf_df = etf_df.reindex(state_df.index).fillna(0.0)
        net = returns_df["net_return"]
        holdout = net.loc[net.index >= holdout_start]

        exposures = avg_etf_exposures(etf_df)
        row = {
            "name": version_name,
            "missing": False,
            **summary_metrics(net),
            "avg_turnover": float(returns_df["turnover"].fillna(0.0).mean()) if "turnover" in returns_df.columns else np.nan,
            **exposures,
            "holdout_ann_return": annual_return(holdout),
            "holdout_sharpe": sharpe_ratio(holdout),
            "recovery_capture": compute_capture(net, spy_returns.reindex(net.index).fillna(0.0), recovery_mask.reindex(net.index).fillna(False)),
            "avg_bucket_offense": float(bucket_series(sleeve_df)["offense"].mean()),
            "avg_bucket_defense": float(bucket_series(sleeve_df)["defense"].mean()),
            "avg_bucket_composite": float(bucket_series(sleeve_df)["composite"].mean()),
            "avg_bucket_cash": float(bucket_series(sleeve_df)["cash"].mean()),
        }
        metrics_rows.append(row)

        state_summary = state_summary_for_version(version_name, returns_df, sleeve_df, etf_df, state_df)
        state_summary_frames.append(state_summary)
        if version_name == PRODUCTION_NAME:
            production_state_summary = state_summary.copy()

    metrics_df = pd.DataFrame(metrics_rows)
    prod_row = metrics_df[metrics_df["name"] == PRODUCTION_NAME].iloc[0]
    shadow_row = metrics_df[metrics_df["name"] == SHADOW_NAME].iloc[0]
    qq_row = metrics_df[metrics_df["name"] == QQ_REFERENCE_NAME].iloc[0]

    for base_name, base_row in [("prod", prod_row), ("shadow", shadow_row), ("qq_best", qq_row)]:
        for col in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_SPY", "avg_offense", "avg_defense", "avg_cash"]:
            metrics_df[f"{col}_delta_vs_{base_name}"] = metrics_df[col] - float(base_row[col])

    state_summary_df = pd.concat(state_summary_frames, ignore_index=True)
    if production_state_summary is not None:
        prod_state = production_state_summary.set_index("state")
        state_summary_df["ann_return_delta_vs_prod"] = state_summary_df.apply(
            lambda row: float(row["ann_return"] - prod_state.at[row["state"], "ann_return"]) if row["state"] in prod_state.index else np.nan,
            axis=1,
        )
        state_summary_df["sharpe_delta_vs_prod"] = state_summary_df.apply(
            lambda row: float(row["sharpe"] - prod_state.at[row["state"], "sharpe"]) if row["state"] in prod_state.index else np.nan,
            axis=1,
        )

    selection_rows = []
    for candidate_name in RR_CANDIDATES:
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

    metrics_df.to_csv(LAYER3_DIR / "phase_rr_candidate_metrics_full.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_rr_state_summary.csv", index=False)
    selection_df.to_csv(LAYER3_DIR / "phase_rr_selection_table.csv", index=False)

    protocol = {
        "phase": "RR",
        "production_pin": PRODUCTION_NAME,
        "shadow_pin": SHADOW_NAME,
        "qq_reference": QQ_REFERENCE_NAME,
        "candidates": RR_CANDIDATES,
        "best_candidate": best_candidate,
        "selection_rule": {
            "annual_return_drag_vs_prod": -0.0030,
            "min_sharpe_delta_vs_prod": 0.0050,
            "max_drawdown_worsening_vs_prod": -0.0050,
            "cvar_worsening_vs_prod": -0.0005,
            "max_turnover_multiple_vs_prod": 1.10,
        },
        "commands": [
            "python scripts/phase_rr_bucket_allocator_redesign.py",
            "python scripts/research_committee_report.py <best_candidate> --quick",
            "python scripts/backtest_realism_audit.py <best_candidate> --quick",
            "python scripts/allocator_benchmark_audit.py <best_candidate> --quick",
        ],
    }
    (LAYER3_DIR / "phase_rr_protocol.json").write_text(json.dumps(protocol, indent=2))

    print(f"Phase RR complete. Best candidate: {best_candidate}")
    print(f"Diagnostics saved to {RESEARCH_DIR}")


if __name__ == "__main__":
    main()
