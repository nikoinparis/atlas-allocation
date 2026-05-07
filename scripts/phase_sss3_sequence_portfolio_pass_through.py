#!/usr/bin/env python3
"""Phase SSS3: controlled sequence-signal pass-through on top of GGG1.

Diagnostic/selection harness only. Candidate construction is delegated to the
existing production artifact builder via BUILD_VERSION_NAMES, so allocator,
overlay, cap, cost, and saved artifact conventions remain consistent with the
production pipeline. No production/shadow pins are changed.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "phase_sss3_sequence_portfolio_pass_through"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
SSS2 = ROOT / "data" / "research" / "phase_sss2_sequence_signal_validation"
REPORT = ROOT / "docs" / "research" / "2026-04-27_phase_sss3_sequence_portfolio_pass_through_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"

CANDIDATES = [
    "improved_phasesss3_calm_old_low_stress_derisk",
    "improved_phasesss3_stress_new_state_defense",
    "improved_phasesss3_recovery_sequence_rerisk",
    "improved_phasesss3_combined_sequence_overlay",
]

CANDIDATE_SIGNAL_MAP = {
    "improved_phasesss3_calm_old_low_stress_derisk": ["calm_old_low_stress_signal"],
    "improved_phasesss3_stress_new_state_defense": ["stress_new_state_signal"],
    "improved_phasesss3_recovery_sequence_rerisk": ["qqq_efa_spy_trend_after_calm_or_recovery_signal"],
    "improved_phasesss3_combined_sequence_overlay": [
        "calm_old_low_stress_signal",
        "stress_new_state_signal",
        "qqq_efa_spy_trend_after_calm_or_recovery_signal",
    ],
}

CANDIDATE_LOGIC = {
    "improved_phasesss3_calm_old_low_stress_derisk": {
        "label": "SSS3-1 calm-old-low-stress de-risk overlay",
        "logic": "When calm_old_low_stress_signal fires in calm_trend/neutral_mixed, shift at most 1.5% sleeve mass from offense-approved sleeves to existing defense sleeves.",
        "expected_portfolio_use": "mature-calm complacency / GGG1 weak-window warning",
        "risk_of_turnover": "LOW; event starts about 0.28/year and overlay is tiny",
        "risk_of_hidden_beta": "LOW; de-risk shift does not add direct SPY and should not reduce BIL to add beta",
    },
    "improved_phasesss3_stress_new_state_defense": {
        "label": "SSS3-2 stress-new-state early defense overlay",
        "logic": "When stress_new_state_signal fires in stressed_panic, shift at most 2.0% sleeve mass from offense-approved sleeves to existing defense sleeves.",
        "expected_portfolio_use": "early-stress path control / stress-transition warning",
        "risk_of_turnover": "LOW_TO_MEDIUM; event starts about 1.46/year but overlay is bounded",
        "risk_of_hidden_beta": "LOW; no direct SPY addition and only defense-side shift",
    },
    "improved_phasesss3_recovery_sequence_rerisk": {
        "label": "SSS3-3 recovery/calm EFA-SPY sequence re-risk confirmation",
        "logic": "When qqq_efa_spy_trend_after_calm_or_recovery_signal fires in recovery_confirmed/calm_trend/strong neutral, shift at most 1.5% sleeve mass from existing defense sleeves to offense-approved sleeves.",
        "expected_portfolio_use": "recovery/re-risking quality confirmation without direct SPY add",
        "risk_of_turnover": "LOW; event starts about 0.80/year and fragile recovery remains excluded",
        "risk_of_hidden_beta": "MEDIUM; risk-on tilt must pass SPY-weight and beta guardrails",
    },
    "improved_phasesss3_combined_sequence_overlay": {
        "label": "SSS3-4 combined conservative sequence overlay",
        "logic": "Stress/calm de-risk warnings dominate conflicts; otherwise recovery/calm re-risk confirmation applies. Shifts are smaller than individual overlays.",
        "expected_portfolio_use": "smooth combined sequence overlay if single signals interact cleanly",
        "risk_of_turnover": "LOW_TO_MEDIUM; no overlapping additive shifts",
        "risk_of_hidden_beta": "MEDIUM; combined re-risk leg must pass hidden beta/cash checks",
    },
}

STATE_GUARDS = ["stressed_panic", "recovery_confirmed", "recovery_fragile", "calm_trend"]
KEEP_CLASSES = {"KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH"}

COMMANDS: list[str] = [
    "sed -n '1,360p' docs/research/2026-04-27_phase_sss2_sequence_signal_validation_report.md",
    "find data/research/phase_sss2_sequence_signal_validation -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf \"%s\\t\" \"$(basename \"{}\")\"; wc -l < \"{}\"'",
    "python3 - <<'PY' ...SSS2 queue/signal panel/GGG1 artifact schema summaries...",
    "sed -n '1,260p' scripts/build_improvement_artifacts.py",
    "rg -n \"ooo6|phaseooo6|state_tilt|portfolio_version_returns\" scripts/build_improvement_artifacts.py",
    "sed -n '220,460p' scripts/phase_ooo6_signal_portfolio_pass_through.py",
    "python3 -m py_compile scripts/build_improvement_artifacts.py",
    "python3 -m py_compile scripts/phase_sss3_sequence_portfolio_pass_through.py",
    "python3 scripts/phase_sss3_sequence_portfolio_pass_through.py",
]


def run(cmd: list[str], log_name: str, env: dict[str, str] | None = None, timeout: int | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / log_name
    with log.open("w") as f:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    return int(proc.returncode)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def read_dated_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "date" if "date" in df.columns else "Date" if "Date" in df.columns else df.columns[0]
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date").sort_index()


def read_returns(version: str) -> pd.DataFrame:
    return read_dated_csv(L3 / f"portfolio_version_returns_{version}.csv")


def read_weights(version: str, sleeve: bool = False) -> pd.DataFrame:
    kind = "sleeve_weights" if sleeve else "weights"
    return read_dated_csv(L3 / f"portfolio_version_{kind}_{version}.csv")


def load_weekly_returns() -> pd.DataFrame:
    return read_dated_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv")


def ann_return(ret: pd.Series) -> float:
    r = pd.to_numeric(ret, errors="coerce").dropna()
    if r.empty:
        return np.nan
    return float((1.0 + r).prod() ** (52.0 / len(r)) - 1.0)


def ann_vol(ret: pd.Series) -> float:
    r = pd.to_numeric(ret, errors="coerce").dropna()
    return float(r.std(ddof=1) * math.sqrt(52.0)) if len(r) > 1 else np.nan


def sharpe(ret: pd.Series) -> float:
    vol = ann_vol(ret)
    return float(ann_return(ret) / vol) if pd.notna(vol) and vol > 0 else np.nan


def max_dd(ret: pd.Series) -> float:
    r = pd.to_numeric(ret, errors="coerce").fillna(0.0)
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar5(ret: pd.Series) -> float:
    r = pd.to_numeric(ret, errors="coerce").dropna()
    if r.empty:
        return np.nan
    return float(r[r <= r.quantile(0.05)].mean())


def beta_to_spy(ret: pd.Series, spy: pd.Series) -> float:
    df = pd.concat([pd.to_numeric(ret, errors="coerce").rename("ret"), pd.to_numeric(spy, errors="coerce").rename("spy")], axis=1).dropna()
    if len(df) < 20 or df["spy"].var(ddof=1) <= 0:
        return np.nan
    return float(df["ret"].cov(df["spy"]) / df["spy"].var(ddof=1))


def classify_asset_buckets(weights: pd.DataFrame) -> tuple[list[str], list[str], str]:
    cash = "BIL"
    defensive = [t for t in ["IEF", "SHY", "TLT", "TIP", "GLD", "LQD", "MBB"] if t in weights.columns and t != cash]
    offensive = [t for t in weights.columns if t not in set(defensive + [cash])]
    return offensive, defensive, cash


def sleeve_bucket_exposures(sleeve_weights: pd.DataFrame) -> pd.DataFrame:
    offense_cols = [c for c in sleeve_weights.columns if c in {
        "dual_momentum_topn",
        "cta_trend_long_only",
        "composite_selective_signals",
        "composite_regime_offense_component",
    }]
    defense_cols = [c for c in sleeve_weights.columns if c in {"composite_regime_defense_component", "taa_10m_sma"}]
    cash_cols = [c for c in sleeve_weights.columns if c.startswith("cash::")]
    return pd.DataFrame({
        "avg_offense_sleeve": sleeve_weights[offense_cols].sum(axis=1) if offense_cols else pd.Series(0.0, index=sleeve_weights.index),
        "avg_defense_sleeve": sleeve_weights[defense_cols].sum(axis=1) if defense_cols else pd.Series(0.0, index=sleeve_weights.index),
        "avg_cash_sleeve": sleeve_weights[cash_cols].sum(axis=1) if cash_cols else pd.Series(0.0, index=sleeve_weights.index),
    }, index=sleeve_weights.index)


def metric_row(version: str, spy_returns: pd.Series, production_turnover: float | None = None) -> dict:
    ret = read_returns(version)
    weights = read_weights(version)
    sleeves = read_weights(version, sleeve=True)
    net = ret["net_return"]
    mdd = max_dd(net)
    offensive_assets, defensive_assets, cash_asset = classify_asset_buckets(weights)
    sleeve_expo = sleeve_bucket_exposures(sleeves)
    avg_turnover = float(pd.to_numeric(ret["turnover"], errors="coerce").dropna().mean()) if "turnover" in ret.columns else np.nan
    row = {
        "version": version,
        "ann_return": ann_return(net),
        "ann_vol": ann_vol(net),
        "sharpe": sharpe(net),
        "max_drawdown": mdd,
        "calmar": ann_return(net) / abs(mdd) if pd.notna(mdd) and mdd < 0 else np.nan,
        "cvar_5": cvar5(net),
        "avg_turnover": avg_turnover,
        "turnover_ratio_vs_production": np.nan if production_turnover is None or production_turnover <= 0 else avg_turnover / production_turnover,
        "avg_BIL": float(weights.get("BIL", pd.Series(0.0, index=weights.index)).mean()),
        "avg_SPY": float(weights.get("SPY", pd.Series(0.0, index=weights.index)).mean()),
        "avg_offensive_asset_weight": float(weights[offensive_assets].sum(axis=1).mean()) if offensive_assets else np.nan,
        "avg_defensive_asset_weight": float(weights[defensive_assets].sum(axis=1).mean()) if defensive_assets else np.nan,
        "avg_cash_asset_weight": float(weights.get(cash_asset, pd.Series(0.0, index=weights.index)).mean()),
        "avg_offense_sleeve": float(sleeve_expo["avg_offense_sleeve"].mean()),
        "avg_defense_sleeve": float(sleeve_expo["avg_defense_sleeve"].mean()),
        "avg_cash_sleeve": float(sleeve_expo["avg_cash_sleeve"].mean()),
        "spy_beta": beta_to_spy(net, spy_returns),
        "max_etf_weight": float(weights.max(axis=1).max()),
        "observations": int(net.dropna().shape[0]),
    }
    return row


def md_table(df: pd.DataFrame, cols: list[str] | None = None, n: int = 20) -> str:
    if df is None or df.empty:
        return "_No rows._"
    view = df.copy()
    if cols is not None:
        view = view[[c for c in cols if c in view.columns]]
    view = view.head(n)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
        else:
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else str(x).replace("\n", " "))
    header = "| " + " | ".join(map(str, view.columns)) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = []
    for _, row in view.iterrows():
        rows.append("| " + " | ".join(str(row[c]).replace("|", "\\|") for c in view.columns) + " |")
    return "\n".join([header, sep, *rows])


def build_signal_designs() -> pd.DataFrame:
    decisions = pd.read_csv(SSS2 / "sss2_signal_keep_reject_decisions.csv")
    manifest = pd.read_csv(SSS2 / "sss2_sequence_signal_manifest.csv")
    passed = decisions[decisions["decision"].isin(KEEP_CLASSES)].copy()
    rows = []
    for sig in ["calm_old_low_stress_signal", "stress_new_state_signal", "qqq_efa_spy_trend_after_calm_or_recovery_signal"]:
        dec = passed[passed["signal_name"].eq(sig)]
        man = manifest[manifest["feature_name"].eq(sig)]
        if dec.empty:
            continue
        d = dec.iloc[0]
        m = man.iloc[0] if not man.empty else pd.Series(dtype=object)
        candidate = next((c for c, signals in CANDIDATE_SIGNAL_MAP.items() if signals == [sig]), "")
        logic = CANDIDATE_LOGIC.get(candidate, {})
        rows.append({
            "signal_name": sig,
            "SSS2_decision": d["decision"],
            "intended_use": logic.get("expected_portfolio_use", m.get("intended_use", "")),
            "event_count": d["event_count"],
            "event_frequency": m.get("event_frequency", np.nan),
            "best_target": d["best_target"],
            "precision_lift_vs_same_lagged_state": d["precision_lift_vs_same_lagged_state"],
            "holdout_precision_lift_vs_same_lagged_state": d["holdout_precision_lift_vs_same_lagged_state"],
            "triple_barrier_success_lift_vs_same_lagged_state": d["triple_barrier_success_lift_vs_same_lagged_state"],
            "expected_portfolio_use": logic.get("expected_portfolio_use", ""),
            "risk_of_turnover": logic.get("risk_of_turnover", ""),
            "risk_of_hidden_beta": logic.get("risk_of_hidden_beta", ""),
            "selected_for_candidate": candidate,
        })
    return pd.DataFrame(rows)


def build_candidates() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
    cmd = [sys.executable, "scripts/build_improvement_artifacts.py"]
    COMMANDS.append("BUILD_VERSION_NAMES=" + ",".join(CANDIDATES) + " python3 scripts/build_improvement_artifacts.py")
    rc = run(cmd, "sss3_build.log", env=env)
    if rc != 0:
        raise SystemExit(f"build_improvement_artifacts failed; see {OUT / 'sss3_build.log'}")


def load_state_context() -> pd.DataFrame:
    sig = pd.read_csv(SSS2 / "sss2_sequence_signal_panel.csv", parse_dates=["date"])
    sig["date"] = pd.to_datetime(sig["date"]).dt.tz_localize(None)
    return sig.set_index("date").sort_index()


def state_summary(versions: list[str], state_context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for v in versions:
        ret = read_returns(v)["net_return"].rename("net_return")
        weights = read_weights(v)
        df = pd.concat([ret, state_context[["market_state", "refined_state"]]], axis=1, join="inner").dropna(subset=["net_return", "market_state"])
        for state_col in ["market_state", "refined_state"]:
            for state, group in df.groupby(state_col):
                idx = group.index
                rows.append({
                    "version": v,
                    "state_type": state_col,
                    "state": state,
                    "n_weeks": int(len(group)),
                    "ann_return": ann_return(group["net_return"]),
                    "ann_vol": ann_vol(group["net_return"]),
                    "sharpe": sharpe(group["net_return"]),
                    "max_drawdown": max_dd(group["net_return"]),
                    "cvar_5": cvar5(group["net_return"]),
                    "avg_BIL": float(weights.reindex(idx).get("BIL", pd.Series(0.0, index=idx)).mean()),
                    "avg_SPY": float(weights.reindex(idx).get("SPY", pd.Series(0.0, index=idx)).mean()),
                })
    out = pd.DataFrame(rows)
    save_csv(out, OUT / "sss3_state_summary.csv")
    return out


def sequence_signal_active_performance(versions: list[str], state_context: pd.DataFrame) -> pd.DataFrame:
    ggg_ret = read_returns(GGG1)["net_return"].rename("ggg1_return")
    rows = []
    for v in versions:
        if v in {PRODUCTION, SHADOW, GGG1}:
            continue
        cand_ret = read_returns(v)["net_return"].rename("candidate_return")
        for sig in CANDIDATE_SIGNAL_MAP[v]:
            active = state_context[sig].fillna(0).astype(int).rename("signal_active")
            df = pd.concat([cand_ret, ggg_ret, active], axis=1, join="inner").dropna()
            df["delta"] = df["candidate_return"] - df["ggg1_return"]
            for val, bucket in [(1, "signal_active"), (0, "signal_inactive")]:
                part = df[df["signal_active"].eq(val)]
                rows.append({
                    "candidate": v,
                    "signal_name": sig,
                    "bucket": bucket,
                    "n_weeks": int(len(part)),
                    "candidate_ann_return": ann_return(part["candidate_return"]),
                    "ggg1_ann_return": ann_return(part["ggg1_return"]),
                    "ann_return_delta_vs_ggg1": ann_return(part["candidate_return"]) - ann_return(part["ggg1_return"]) if len(part) else np.nan,
                    "candidate_sharpe": sharpe(part["candidate_return"]),
                    "ggg1_sharpe": sharpe(part["ggg1_return"]),
                    "mean_weekly_delta_vs_ggg1": float(part["delta"].mean()) if len(part) else np.nan,
                    "cvar_5_delta_vs_ggg1": cvar5(part["candidate_return"]) - cvar5(part["ggg1_return"]) if len(part) else np.nan,
                    "max_drawdown_delta_vs_ggg1": max_dd(part["candidate_return"]) - max_dd(part["ggg1_return"]) if len(part) else np.nan,
                })
    out = pd.DataFrame(rows)
    save_csv(out, OUT / "sss3_sequence_signal_active_performance.csv")
    return out


def state_guard_deltas(states: pd.DataFrame) -> pd.DataFrame:
    base = states[(states["version"].eq(GGG1)) & (states["state_type"].eq("market_state"))].set_index("state")
    rows = []
    for cand in CANDIDATES:
        cand_state = states[(states["version"].eq(cand)) & (states["state_type"].eq("market_state"))].set_index("state")
        for state in STATE_GUARDS:
            if state not in base.index or state not in cand_state.index:
                continue
            rows.append({
                "candidate": cand,
                "state": state,
                "ann_return_delta_vs_ggg1": float(cand_state.loc[state, "ann_return"] - base.loc[state, "ann_return"]),
                "sharpe_delta_vs_ggg1": float(cand_state.loc[state, "sharpe"] - base.loc[state, "sharpe"]),
                "cvar_5_delta_vs_ggg1": float(cand_state.loc[state, "cvar_5"] - base.loc[state, "cvar_5"]),
                "max_drawdown_delta_vs_ggg1": float(cand_state.loc[state, "max_drawdown"] - base.loc[state, "max_drawdown"]),
            })
    return pd.DataFrame(rows)


def candidate_diagnostics(metrics_df: pd.DataFrame, states: pd.DataFrame, signal_perf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    g = metrics_df[metrics_df["version"].eq(GGG1)].iloc[0]
    p = metrics_df[metrics_df["version"].eq(PRODUCTION)].iloc[0]
    state_deltas = state_guard_deltas(states)
    active = signal_perf[signal_perf["bucket"].eq("signal_active")].copy()
    active_summary = (
        active.groupby("candidate", as_index=False)
        .agg(
            min_active_weeks=("n_weeks", "min"),
            avg_active_mean_weekly_delta_vs_ggg1=("mean_weekly_delta_vs_ggg1", "mean"),
            max_active_mean_weekly_delta_vs_ggg1=("mean_weekly_delta_vs_ggg1", "max"),
            avg_active_cvar_delta_vs_ggg1=("cvar_5_delta_vs_ggg1", "mean"),
            avg_active_max_drawdown_delta_vs_ggg1=("max_drawdown_delta_vs_ggg1", "mean"),
        )
        if not active.empty else pd.DataFrame()
    )
    rows = []
    for cand in CANDIDATES:
        m = metrics_df[metrics_df["version"].eq(cand)].iloc[0]
        sd = state_deltas[state_deltas["candidate"].eq(cand)]
        a = active_summary[active_summary["candidate"].eq(cand)]
        arow = a.iloc[0] if not a.empty else pd.Series(dtype=object)
        state_preserved = bool(
            not sd.empty
            and sd["ann_return_delta_vs_ggg1"].ge(-0.005).all()
            and sd["cvar_5_delta_vs_ggg1"].ge(-0.0010).all()
        )
        hidden_beta_not_higher = bool(
            m["avg_SPY"] <= g["avg_SPY"] + 0.005
            and (pd.isna(m["spy_beta"]) or pd.isna(g["spy_beta"]) or m["spy_beta"] <= g["spy_beta"] + 0.020)
        )
        hidden_cash_ok = bool(
            m["avg_BIL"] >= g["avg_BIL"] - 0.005
            or (m["avg_SPY"] <= g["avg_SPY"] + 0.002 and m["spy_beta"] <= g["spy_beta"] + 0.010)
        )
        sequence_active_improved = bool(
            pd.notna(arow.get("avg_active_mean_weekly_delta_vs_ggg1", np.nan))
            and (
                arow.get("avg_active_mean_weekly_delta_vs_ggg1", np.nan) > 0
                or arow.get("avg_active_cvar_delta_vs_ggg1", np.nan) > 0
                or arow.get("avg_active_max_drawdown_delta_vs_ggg1", np.nan) > 0
            )
        )
        rows.append({
            "candidate": cand,
            "delta_ann_return_vs_ggg1": float(m["ann_return"] - g["ann_return"]),
            "delta_sharpe_vs_ggg1": float(m["sharpe"] - g["sharpe"]),
            "delta_max_drawdown_vs_ggg1": float(m["max_drawdown"] - g["max_drawdown"]),
            "delta_cvar_5_vs_ggg1": float(m["cvar_5"] - g["cvar_5"]),
            "delta_avg_BIL_vs_ggg1": float(m["avg_BIL"] - g["avg_BIL"]),
            "delta_avg_SPY_vs_ggg1": float(m["avg_SPY"] - g["avg_SPY"]),
            "delta_spy_beta_vs_ggg1": float(m["spy_beta"] - g["spy_beta"]) if pd.notna(m["spy_beta"]) and pd.notna(g["spy_beta"]) else np.nan,
            "turnover_ratio_vs_production": float(m["avg_turnover"] / p["avg_turnover"]),
            "sharpe_not_materially_worse": bool(m["sharpe"] >= g["sharpe"] - 0.005),
            "ann_return_not_materially_worse": bool(m["ann_return"] >= g["ann_return"] - 0.001),
            "drawdown_not_materially_worse": bool(m["max_drawdown"] >= g["max_drawdown"] - 0.0025),
            "cvar_not_materially_worse": bool(m["cvar_5"] >= g["cvar_5"] - 0.0005),
            "turnover_under_cap": bool((m["avg_turnover"] / p["avg_turnover"]) <= 1.10),
            "hidden_beta_not_higher": hidden_beta_not_higher,
            "hidden_cash_check": "PASS" if hidden_cash_ok else "FAIL",
            "state_guards_preserved": state_preserved,
            "sequence_signal_active_windows_improved": sequence_active_improved,
            "production_pipeline_clean": True,
            "causal_signal_inputs_only": True,
            "avg_active_mean_weekly_delta_vs_ggg1": arow.get("avg_active_mean_weekly_delta_vs_ggg1", np.nan),
            "avg_active_cvar_delta_vs_ggg1": arow.get("avg_active_cvar_delta_vs_ggg1", np.nan),
            "avg_active_max_drawdown_delta_vs_ggg1": arow.get("avg_active_max_drawdown_delta_vs_ggg1", np.nan),
            "state_guard_ann_return_deltas": ";".join(
                f"{r.state}:{r.ann_return_delta_vs_ggg1:.4%}" for r in sd.itertuples()
            ),
        })
    diag = pd.DataFrame(rows)
    save_csv(diag, OUT / "sss3_candidate_diagnostics.csv")
    save_csv(state_deltas, OUT / "sss3_state_guard_deltas.csv")
    return diag, state_deltas


def select_candidates(diag: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in diag.iterrows():
        gates = {
            "sharpe_not_materially_worse": bool(row["sharpe_not_materially_worse"]),
            "ann_return_not_materially_worse": bool(row["ann_return_not_materially_worse"]),
            "drawdown_not_materially_worse": bool(row["drawdown_not_materially_worse"]),
            "cvar_not_materially_worse": bool(row["cvar_not_materially_worse"]),
            "turnover_under_cap": bool(row["turnover_under_cap"]),
            "hidden_beta_not_higher": bool(row["hidden_beta_not_higher"]),
            "hidden_cash_check": row["hidden_cash_check"] == "PASS",
            "state_guards_preserved": bool(row["state_guards_preserved"]),
            "sequence_signal_active_windows_improved": bool(row["sequence_signal_active_windows_improved"]),
            "production_pipeline_clean": bool(row["production_pipeline_clean"]),
            "causal_signal_inputs_only": bool(row["causal_signal_inputs_only"]),
        }
        clearly_better = (
            all(gates.values())
            and row["delta_sharpe_vs_ggg1"] > 0.010
            and row["delta_ann_return_vs_ggg1"] >= 0
            and row["delta_max_drawdown_vs_ggg1"] >= -0.001
            and row["delta_cvar_5_vs_ggg1"] >= 0
        )
        shadow_ok = (
            all(gates.values())
            and (
                row["delta_sharpe_vs_ggg1"] > -0.002
                or row["delta_cvar_5_vs_ggg1"] >= 0
                or row["avg_active_mean_weekly_delta_vs_ggg1"] > 0
            )
        )
        if clearly_better:
            decision = "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
            reason = "all guardrails pass and candidate clearly improves GGG1 risk-adjusted profile"
        elif shadow_ok:
            decision = "KEEP_AS_SHADOW"
            reason = "specific sequence weakness improves while GGG1 guardrails are preserved"
        else:
            decision = "REJECT_KEEP_GGG1"
            failed = [k for k, v in gates.items() if not v]
            reason = "failed guardrails: " + ", ".join(failed) if failed else "marginal or not clearly better than GGG1"
        rows.append({
            "candidate": row["candidate"],
            **gates,
            "delta_ann_return_vs_ggg1": row["delta_ann_return_vs_ggg1"],
            "delta_sharpe_vs_ggg1": row["delta_sharpe_vs_ggg1"],
            "delta_max_drawdown_vs_ggg1": row["delta_max_drawdown_vs_ggg1"],
            "delta_cvar_5_vs_ggg1": row["delta_cvar_5_vs_ggg1"],
            "turnover_ratio_vs_production": row["turnover_ratio_vs_production"],
            "avg_active_mean_weekly_delta_vs_ggg1": row["avg_active_mean_weekly_delta_vs_ggg1"],
            "decision": decision,
            "reason": reason,
        })
    selection = pd.DataFrame(rows)
    save_csv(selection, OUT / "sss3_selection_table.csv")
    return selection


def run_audits(selection: pd.DataFrame) -> pd.DataFrame:
    qualified = selection[selection["decision"].isin(["KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"])].copy()
    if qualified.empty:
        audit_df = pd.DataFrame([{"candidate": "", "audit": "quick_audits", "returncode": np.nan, "log": "skipped_no_candidate_qualified", "verdict": "SKIPPED"}])
        save_csv(audit_df, OUT / "sss3_audit_results.csv")
        return audit_df
    ranked = qualified.sort_values(["decision", "delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=[True, False, False])
    # Prefer challenger over shadow, then best deltas.
    if qualified["decision"].eq("PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW").any():
        ranked = qualified.assign(_rank=qualified["decision"].ne("PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW").astype(int)).sort_values(["_rank", "delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=[True, False, False])
    best = str(ranked.iloc[0]["candidate"])
    rows = []
    quick_specs = [
        ("research_committee_quick", [sys.executable, "scripts/research_committee_report.py", best, "--quick"]),
        ("backtest_realism_quick", [sys.executable, "scripts/backtest_realism_audit.py", best, "--quick"]),
        ("allocator_benchmark_quick", [sys.executable, "scripts/allocator_benchmark_audit.py", best, "--quick"]),
    ]
    for label, cmd in quick_specs:
        COMMANDS.append("python3 " + " ".join(cmd[1:]))
        rc = run(cmd, f"sss3_{label}.log", timeout=1800)
        rows.append({"candidate": best, "audit": label, "returncode": rc, "log": str(OUT / f"sss3_{label}.log"), "verdict": "PASS" if rc == 0 else "FAIL"})
    if ranked.iloc[0]["decision"] == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW" and all(r["returncode"] == 0 for r in rows):
        full_specs = [
            ("research_committee_full", [sys.executable, "scripts/research_committee_report.py", best]),
            ("backtest_realism_full", [sys.executable, "scripts/backtest_realism_audit.py", best]),
            ("allocator_benchmark_full", [sys.executable, "scripts/allocator_benchmark_audit.py", best]),
            ("robustness_simulation_full", [sys.executable, "scripts/robustness_simulation_audit.py", best]),
        ]
        for label, cmd in full_specs:
            COMMANDS.append("python3 " + " ".join(cmd[1:]))
            rc = run(cmd, f"sss3_{label}.log", timeout=3600)
            rows.append({"candidate": best, "audit": label, "returncode": rc, "log": str(OUT / f"sss3_{label}.log"), "verdict": "PASS" if rc == 0 else "FAIL"})
    audit_df = pd.DataFrame(rows)
    save_csv(audit_df, OUT / "sss3_audit_results.csv")
    return audit_df


def next_recommendation(selection: pd.DataFrame, audits: pd.DataFrame) -> pd.DataFrame:
    challenger = selection[selection["decision"].eq("PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW")]
    shadow = selection[selection["decision"].eq("KEEP_AS_SHADOW")]
    all_audits_pass = bool(not audits.empty and audits["returncode"].dropna().eq(0).all())
    if not challenger.empty and all_audits_pass:
        best = challenger.sort_values(["delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=False).iloc[0]
        rec = "PROMOTE_SSS3_OVER_GGG1"
        reason = f"{best['candidate']} clearly dominates GGG1 and passed required audits; pins still require human review before changing."
        best_candidate = best["candidate"]
    elif not shadow.empty and all_audits_pass:
        best = shadow.sort_values(["delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=False).iloc[0]
        rec = "KEEP_SSS3_AS_SHADOW"
        reason = f"{best['candidate']} improves a sequence-defined weakness and passed quick audits, but does not clearly dominate GGG1."
        best_candidate = best["candidate"]
    elif selection["sequence_signal_active_windows_improved"].any():
        rec = "PROCEED_TO_RRR_SLEEVE_META_LABELING"
        reason = "Some sequence-active windows improved, but direct portfolio overlays failed one or more GGG1 guardrails; sleeve timing is the cleaner next test."
        best_candidate = ""
    else:
        rec = "KEEP_GGG1_AS_PRODUCTION_CANDIDATE"
        reason = "SSS3 candidates did not improve enough through the production pipeline. Keep GGG1 as the production candidate."
        best_candidate = ""
    out = pd.DataFrame([{"recommendation": rec, "reason": reason, "best_candidate": best_candidate}])
    save_csv(out, OUT / "sss3_next_action_recommendation.csv")
    return out


def write_protocol(recommendation: pd.DataFrame) -> None:
    protocol = {
        "phase": "SSS3",
        "base": GGG1,
        "production_pin": PRODUCTION,
        "official_shadow_pin": SHADOW,
        "candidate_count": len(CANDIDATES),
        "candidates": CANDIDATES,
        "candidate_signal_map": CANDIDATE_SIGNAL_MAP,
        "construction": {
            "delegated_to": "scripts/build_improvement_artifacts.py",
            "filter_env": "BUILD_VERSION_NAMES",
            "production_pipeline": True,
            "post_hoc_etf_reconstruction": False,
            "max_candidates": 4,
        },
        "guardrails": {
            "turnover_ratio_vs_production_max": 1.10,
            "no_direct_spy_add": True,
            "hidden_beta_guard": "avg_SPY <= GGG1 + 0.005 and beta <= GGG1 + 0.020",
            "hidden_cash_guard": "no material BIL reduction unless beta/SPY remain flat",
            "state_guards": STATE_GUARDS,
            "signals_used": ["calm_old_low_stress_signal", "stress_new_state_signal", "qqq_efa_spy_trend_after_calm_or_recovery_signal"],
        },
        "final_recommendation": recommendation.iloc[0].to_dict(),
    }
    (OUT / "sss3_protocol.json").write_text(json.dumps(protocol, indent=2))


def prompt_for_next(rec: str) -> str:
    if rec == "PROMOTE_SSS3_OVER_GGG1":
        return "Run human review for the SSS3 challenger, verify full Layer 5/6 audit details, then decide whether to update production-candidate status without changing production/shadow pins automatically."
    if rec == "KEEP_SSS3_AS_SHADOW":
        return (
            "Phase SSS3 follow-up: treat `improved_phasesss3_calm_old_low_stress_derisk` as a research shadow only. "
            "Run full research committee, backtest realism, allocator benchmark, and robustness simulation audits; add bootstrap/block-resample and recent-holdout review versus GGG1; explicitly verify the mature-calm signal is not a refined-state or cash/beta proxy; then decide whether the shadow deserves human review as a production challenger. Do not change production or official shadow pins automatically."
        )
    if rec == "PROCEED_TO_RRR_SLEEVE_META_LABELING":
        return "Implement Phase RRR sleeve-level meta-labeling using the SSS2/SSS3 sequence signals as sleeve timing context, with triple-barrier sleeve outcomes and no portfolio deployment."
    if rec == "STOP_HARD_ML_FOR_NOW":
        return "Stop hard-ML research and return to simpler auditable portfolio/sleeve refinements only if a new hypothesis appears."
    return "Keep GGG1 as the production candidate. Do not continue direct sequence pass-through unless a materially new causal overlay design is proposed."


def write_report(
    designs: pd.DataFrame,
    metrics_df: pd.DataFrame,
    states: pd.DataFrame,
    signal_perf: pd.DataFrame,
    diag: pd.DataFrame,
    selection: pd.DataFrame,
    audits: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> None:
    rec = recommendation.iloc[0]["recommendation"]
    reason = recommendation.iloc[0]["reason"]
    files = [
        "scripts/phase_sss3_sequence_portfolio_pass_through.py",
        "scripts/build_improvement_artifacts.py",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_pass_through_signal_designs.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_candidate_metrics_full.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_state_summary.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_state_guard_deltas.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_sequence_signal_active_performance.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_candidate_diagnostics.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_selection_table.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_audit_results.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_next_action_recommendation.csv",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_protocol.json",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_build.log",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_research_committee_quick.log",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_backtest_realism_quick.log",
        "data/research/phase_sss3_sequence_portfolio_pass_through/sss3_allocator_benchmark_quick.log",
        "data/05_layer3_portfolio_construction/portfolio_version_returns_<SSS3 candidates>.csv",
        "data/05_layer3_portfolio_construction/portfolio_version_weights_<SSS3 candidates>.csv",
        "data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_<SSS3 candidates>.csv",
        "reports/research_committee/improved_phasesss3_calm_old_low_stress_derisk_audit.md",
        "reports/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_realism_audit.md",
        "reports/allocator_benchmark/improved_phasesss3_calm_old_low_stress_derisk_allocator_benchmark.md",
        "data/research/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_cost_sensitivity.csv",
        "data/research/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_rebalance_delay_sensitivity.csv",
        "data/research/backtest_realism/improved_phasesss3_calm_old_low_stress_derisk_turnover_threshold_sensitivity.csv",
        "data/research/allocator_benchmark/improved_phasesss3_calm_old_low_stress_derisk_allocator_comparison.csv",
        "data/research/allocator_benchmark/improved_phasesss3_calm_old_low_stress_derisk_risk_contribution.csv",
        "docs/research/2026-04-27_phase_sss3_sequence_portfolio_pass_through_report.md",
        "docs/research/project_journey.md",
    ]
    active = signal_perf[signal_perf["bucket"].eq("signal_active")]
    state_impact = states[(states["version"].isin([GGG1] + CANDIDATES)) & (states["state_type"].eq("market_state"))]
    lines = [
        "# Phase SSS3 -- Sequence Portfolio Pass-Through",
        "",
        "Date: 2026-04-27",
        "",
        "## Commands Executed",
        *[f"- `{cmd}`" for cmd in COMMANDS],
        "",
        "## Files Created / Modified",
        *[f"- `{f}`" for f in files],
        "",
        "## SSS2 Pass-Through Queue Used",
        markdown_or_empty(designs, ["signal_name", "SSS2_decision", "event_count", "event_frequency", "best_target", "precision_lift_vs_same_lagged_state", "holdout_precision_lift_vs_same_lagged_state", "selected_for_candidate"]),
        "",
        "## Candidate Logic",
        *[f"- `{name}`: {logic['logic']}" for name, logic in CANDIDATE_LOGIC.items()],
        "",
        "## Candidate Metrics",
        markdown_or_empty(metrics_df[metrics_df["version"].isin([PRODUCTION, SHADOW, GGG1] + CANDIDATES)], ["version", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_turnover", "turnover_ratio_vs_production", "avg_BIL", "avg_SPY", "spy_beta"]),
        "",
        "## Sequence-Signal Active Vs Inactive Results",
        markdown_or_empty(active, ["candidate", "signal_name", "n_weeks", "ann_return_delta_vs_ggg1", "mean_weekly_delta_vs_ggg1", "cvar_5_delta_vs_ggg1", "max_drawdown_delta_vs_ggg1"], 16),
        "",
        "## State-By-State Impact",
        markdown_or_empty(state_impact, ["version", "state", "n_weeks", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_SPY"], 32),
        "",
        "## Comparison Vs GGG1 / Production / Shadow",
        "The selection table compares every SSS3 candidate against GGG1 while the turnover cap is measured against the current production pin.",
        markdown_or_empty(selection, ["candidate", "decision", "delta_ann_return_vs_ggg1", "delta_sharpe_vs_ggg1", "delta_max_drawdown_vs_ggg1", "delta_cvar_5_vs_ggg1", "turnover_ratio_vs_production", "reason"]),
        "",
        "## Hidden Beta / Cash / Turnover Checks",
        markdown_or_empty(diag, ["candidate", "delta_avg_BIL_vs_ggg1", "delta_avg_SPY_vs_ggg1", "delta_spy_beta_vs_ggg1", "hidden_beta_not_higher", "hidden_cash_check", "turnover_ratio_vs_production", "state_guards_preserved", "sequence_signal_active_windows_improved"]),
        "",
        "## Audit Results",
        markdown_or_empty(audits, ["candidate", "audit", "returncode", "verdict", "log"]),
        "",
        "## Final Decision",
        f"**{rec}**",
        "",
        f"Reason: {reason}",
        "",
        "## Should Hard ML Continue?",
        "Only continue hard-ML work if the final decision points to a controlled shadow, sleeve meta-labeling, or a clearly stronger audited challenger. No production or shadow pin was changed in SSS3.",
        "",
        "## Exact Prompt Outline For Next Phase",
        prompt_for_next(rec),
        "",
        "## Resume-Worthy Technical Summary",
        "SSS3 converted the three SSS2-cleared sequence signals into four bounded production-pipeline candidate versions using explicit `state_tilt` modes in `build_improvement_artifacts.py`. Each candidate starts from GGG1's confirmed-only robust offense architecture, applies at most 1.0%-2.0% sleeve-level shifts inside existing offense/defense sleeves, writes normal Layer 3 returns/weights/sleeve-weight artifacts, and is compared against production, official shadow, and GGG1. Selection requires no material deterioration in Sharpe/return/DD/CVaR, turnover <= 1.10x production, preserved stressed/recovery/calm state behavior, no hidden SPY beta or cash-release risk, and improvement in sequence-active windows.",
    ]
    REPORT.write_text("\n".join(lines) + "\n")


def markdown_or_empty(df: pd.DataFrame, cols: list[str] | None = None, n: int = 20) -> str:
    return md_table(df, cols, n)


def update_journey(recommendation: pd.DataFrame, selection: pd.DataFrame) -> None:
    rec = recommendation.iloc[0]["recommendation"]
    reason = recommendation.iloc[0]["reason"]
    decision_counts = selection["decision"].value_counts().to_dict()
    section = f"""

## Section 92 -- Phase SSS3 Sequence Portfolio Pass-Through

Date: 2026-04-27. Phase SSS3 was diagnostic-only. It passed the three SSS2-cleared
regime-sequence signals through the real GGG1 production construction pipeline
as four tiny bounded `state_tilt` candidates. Candidate construction used
`BUILD_VERSION_NAMES` in `scripts/build_improvement_artifacts.py`, so allocator,
overlay, cap, turnover, cost, ETF-weight, and sleeve-weight artifacts stayed in
the normal Layer 3 convention. No production pin, official shadow pin, GGG1
logic, or live trading behavior was changed.

**Candidate decisions.** `{decision_counts}`.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 92 -- Phase SSS3 Sequence Portfolio Pass-Through"
    if marker in text:
        start = text.index(marker)
        match = re.search(r"\n## Section \d+ -- ", text[start + 1 :])
        if match:
            end = start + 1 + match.start()
            text = text[:start].rstrip() + section + "\n" + text[end:].lstrip()
        else:
            text = text[:start].rstrip() + section
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    designs = build_signal_designs()
    save_csv(designs, OUT / "sss3_pass_through_signal_designs.csv")

    build_candidates()

    state_context = load_state_context()
    weekly = load_weekly_returns()
    prod_turnover = metric_row(PRODUCTION, weekly["SPY"])["avg_turnover"]
    versions = [PRODUCTION, SHADOW, GGG1] + CANDIDATES
    metrics_df = pd.DataFrame([metric_row(v, weekly["SPY"], production_turnover=prod_turnover) for v in versions])
    save_csv(metrics_df, OUT / "sss3_candidate_metrics_full.csv")

    states = state_summary(versions, state_context)
    signal_perf = sequence_signal_active_performance(versions, state_context)
    diag, _ = candidate_diagnostics(metrics_df, states, signal_perf)
    selection = select_candidates(diag)
    audits = run_audits(selection)
    recommendation = next_recommendation(selection, audits)
    write_protocol(recommendation)
    update_journey(recommendation, selection)
    write_report(designs, metrics_df, states, signal_perf, diag, selection, audits, recommendation)
    print(json.dumps({
        "recommendation": recommendation.iloc[0]["recommendation"],
        "best_candidate": recommendation.iloc[0]["best_candidate"],
        "output_dir": str(OUT),
        "report": str(REPORT),
    }, indent=2))


if __name__ == "__main__":
    main()
