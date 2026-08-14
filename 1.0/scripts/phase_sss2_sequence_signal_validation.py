"""Phase SSS2 -- explicit regime-sequence signal validation.

Diagnostic-only research phase. Converts the high-priority Phase SSS sequence
rules into causal lagged binary signals, validates event/path outcomes, checks
holdout stability and redundancy, and decides whether the signals deserve a
future pass-through, sleeve meta-labeling, more feature engineering, or a stop.

No production pins, shadow pins, GGG1 logic, live trading, or portfolio
candidates are changed.
"""
from __future__ import annotations

import json
import math
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
L3 = DATA / "05_layer3_portfolio_construction"
SSS = DATA / "research" / "phase_sss_regime_sequence_modeling"
QQQ = DATA / "research" / "phase_qqq_deep_feature_interaction_mining"
OOO = DATA / "research" / "phase_ooo_signal_discovery"
OUT = DATA / "research" / "phase_sss2_sequence_signal_validation"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_sss2_sequence_signal_validation_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

PRIMARY_CLASSES = {
    "HIGH_PRIORITY_SEQUENCE_SIGNAL",
    "PROMISING_RECOVERY_QUALITY_SIGNAL",
    "PROMISING_STRESS_WARNING_SIGNAL",
}
WATCHLIST_CLASSES = {"NEEDS_TRIPLE_BARRIER_VALIDATION"}

SIGNALS = [
    "calm_old_low_stress_signal",
    "stress_new_state_signal",
    "stress_memory_neutral_signal",
    "qqq_efa_spy_trend_after_calm_or_recovery_signal",
    "high_transition_instability_signal",
    "refined_neutral_deteriorating_signal",
]

TARGET_META = {
    "stress_transition_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "direction": "bad"},
    "stress_transition_8w": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "direction": "bad"},
    "recovery_quality_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "direction": "good"},
    "recovery_quality_8w": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "direction": "good"},
    "ggg1_underperformance_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "direction": "bad"},
    "ggg1_tail_risk_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "direction": "bad"},
    "false_recovery_label": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "direction": "bad"},
}

PRIMARY_TARGETS = {
    "calm_old_low_stress_signal": ["ggg1_underperformance_4w", "ggg1_tail_risk_4w"],
    "stress_new_state_signal": ["stress_transition_8w", "stress_transition_4w", "ggg1_tail_risk_4w"],
    "stress_memory_neutral_signal": ["stress_transition_4w", "stress_transition_8w", "false_recovery_label"],
    "qqq_efa_spy_trend_after_calm_or_recovery_signal": ["recovery_quality_8w", "recovery_quality_4w"],
    "high_transition_instability_signal": ["recovery_quality_8w", "stress_transition_4w", "ggg1_tail_risk_4w"],
    "refined_neutral_deteriorating_signal": ["stress_transition_4w", "stress_transition_8w", "ggg1_underperformance_4w"],
}

RISK_WARNING_SIGNALS = {
    "calm_old_low_stress_signal",
    "stress_new_state_signal",
    "stress_memory_neutral_signal",
    "high_transition_instability_signal",
    "refined_neutral_deteriorating_signal",
}

COMMANDS = [
    "sed -n '1,360p' docs/research/2026-04-27_phase_sss_regime_sequence_modeling_report.md",
    "find data/research/phase_sss_regime_sequence_modeling -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf \"%s\\t\" \"$(basename \"{}\")\"; wc -l < \"{}\"'",
    "python3 - <<'PY' ...SSS candidate queue, feature, target, and state schema summaries...",
    "sed -n '1,260p' docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md",
    "sed -n '1,180p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md",
    "sed -n '1,220p' scripts/phase_sss_regime_sequence_modeling.py",
    "tail -n 220 scripts/phase_sss_regime_sequence_modeling.py",
    "python3 -m py_compile scripts/phase_sss2_sequence_signal_validation.py",
    "python3 scripts/phase_sss2_sequence_signal_validation.py",
]


def ensure_out() -> None:
    OUT.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def read_dated_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = None
    for candidate in ["date", "Date", "Unnamed: 0"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError(f"No date column found in {path}")
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def markdown_table(df: pd.DataFrame, max_rows: int = 20, max_cols: int | None = None) -> str:
    if df is None or df.empty:
        return "_No rows._"
    out = df.copy().head(max_rows)
    if max_cols is not None:
        out = out.iloc[:, :max_cols]
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
        else:
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else str(x).replace("\n", " "))
    cols = [str(c) for c in out.columns]
    rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in out.iterrows():
        values = [str(row[col]).replace("|", "\\|") for col in out.columns]
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def safe_mean(s: pd.Series) -> float:
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.mean()) if len(x) else np.nan


def safe_rate(s: pd.Series) -> float:
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.mean()) if len(x) else np.nan


def safe_corr(a: pd.Series, b: pd.Series) -> float:
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    m = x.notna() & y.notna()
    if m.sum() < 5:
        return np.nan
    if x[m].std(ddof=0) == 0 or y[m].std(ddof=0) == 0:
        return np.nan
    return float(x[m].corr(y[m]))


def event_run_stats(dates: pd.Series, signal: pd.Series) -> dict[str, float]:
    x = pd.to_numeric(signal, errors="coerce").fillna(0).astype(int)
    if len(x) == 0 or x.sum() == 0:
        return {
            "event_start_count": 0,
            "avg_event_duration_weeks": np.nan,
            "max_event_duration_weeks": np.nan,
            "event_starts_per_year": 0.0,
            "avg_gap_between_event_starts_weeks": np.nan,
        }
    starts = (x.eq(1) & x.shift(1, fill_value=0).ne(1))
    run_id = starts.cumsum()
    run_lengths = x[x.eq(1)].groupby(run_id[x.eq(1)]).size()
    date_span_years = max((pd.to_datetime(dates).max() - pd.to_datetime(dates).min()).days / 365.25, 1e-9)
    start_idx = np.flatnonzero(starts.to_numpy())
    gaps = np.diff(start_idx)
    return {
        "event_start_count": int(starts.sum()),
        "avg_event_duration_weeks": float(run_lengths.mean()) if len(run_lengths) else np.nan,
        "max_event_duration_weeks": int(run_lengths.max()) if len(run_lengths) else np.nan,
        "event_starts_per_year": float(starts.sum() / date_span_years),
        "avg_gap_between_event_starts_weeks": float(np.mean(gaps)) if len(gaps) else np.nan,
    }


def weighted_same_group_mean(df: pd.DataFrame, event_mask: pd.Series, group_col: str, value_col: str) -> float:
    valid = df[value_col].notna() & df[group_col].notna()
    if event_mask.sum() == 0 or valid.sum() == 0:
        return np.nan
    group_means = df.loc[valid].groupby(group_col)[value_col].mean()
    event_groups = df.loc[event_mask & df[group_col].notna(), group_col]
    if event_groups.empty:
        return np.nan
    mapped = event_groups.map(group_means).dropna()
    return float(mapped.mean()) if len(mapped) else np.nan


def weighted_same_group_return(df: pd.DataFrame, event_mask: pd.Series, group_col: str, return_col: str) -> float:
    valid = df[return_col].notna() & df[group_col].notna()
    if event_mask.sum() == 0 or valid.sum() == 0:
        return np.nan
    group_means = df.loc[valid].groupby(group_col)[return_col].mean()
    event_groups = df.loc[event_mask & df[group_col].notna(), group_col]
    if event_groups.empty:
        return np.nan
    mapped = event_groups.map(group_means).dropna()
    return float(mapped.mean()) if len(mapped) else np.nan


def load_inputs() -> dict[str, pd.DataFrame]:
    required = {
        "candidate": SSS / "sss_candidate_sequence_signal_shortlist.csv",
        "queue": SSS / "sss_next_phase_queue.csv",
        "features": SSS / "sss_sequence_feature_panel.csv",
        "targets": SSS / "sss_target_panel.csv",
        "state": SSS / "sss_state_sequence_panel.csv",
        "extracted_rules": SSS / "sss_extracted_sequence_rules.csv",
        "weakness": SSS / "sss_ggg1_sequence_weakness_diagnostics.csv",
        "incrementality": SSS / "sss_sequence_incrementality_summary.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required SSS inputs: {missing}")
    return {
        "candidate": pd.read_csv(required["candidate"]),
        "queue": pd.read_csv(required["queue"]),
        "features": read_dated_csv(required["features"]),
        "targets": read_dated_csv(required["targets"]),
        "state": read_dated_csv(required["state"]),
        "extracted_rules": pd.read_csv(required["extracted_rules"]),
        "weakness": pd.read_csv(required["weakness"]),
        "incrementality": pd.read_csv(required["incrementality"]),
    }


def build_signal_definitions(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    queue = inputs["queue"].copy()
    usable = queue[queue["classification"].isin(PRIMARY_CLASSES | WATCHLIST_CLASSES)].copy()

    specs = [
        {
            "signal_name": "calm_old_low_stress_signal",
            "source_rule": "calm_old_low_stress",
            "rule_formula": "state_lag1 == 'calm_trend' and state_age_lag1 >= 14 and stress_count_last_13w == 0",
            "intended_use": "GGG1 weak-window warning",
            "lag_rule": "uses only lagged market_state, lagged dwell age, and trailing 13w stress count",
            "expected_state_path": "mature calm_trend with no recent stressed_panic memory",
            "target_family": "ggg1_underperformance / tail risk",
            "selection_reason": "high-priority SSS rule with stable underperformance lift",
            "priority": "primary",
        },
        {
            "signal_name": "stress_new_state_signal",
            "source_rule": "stress_new_state",
            "rule_formula": "state_lag1 == 'stressed_panic' and state_age_lag1 <= 2",
            "intended_use": "stress-transition warning",
            "lag_rule": "uses only lagged market_state and lagged dwell age",
            "expected_state_path": "new stressed_panic state",
            "target_family": "stress_transition / tail risk",
            "selection_reason": "high-priority SSS rule for 4w and 8w stress-transition risk",
            "priority": "primary",
        },
        {
            "signal_name": "stress_memory_neutral_signal",
            "source_rule": "stress_memory_neutral",
            "rule_formula": "state_lag1 == 'neutral_mixed' and stress_count_last_13w > 0",
            "intended_use": "neutral-after-stress warning",
            "lag_rule": "uses only lagged market_state and trailing 13w stress count",
            "expected_state_path": "neutral_mixed while stress memory is still present",
            "target_family": "stress_transition / false recovery",
            "selection_reason": "high-priority SSS rule with enough events and same-state incrementality potential",
            "priority": "primary",
        },
        {
            "signal_name": "qqq_efa_spy_trend_after_calm_or_recovery_signal",
            "source_rule": "qqq_efa_spy_trend_after_calm_or_recovery",
            "rule_formula": "qqq_active_int_efa_spy_strength_x_market_trend_lag1 > 0.05 and (state_lag1 == 'calm_trend' or recovery_count_last_13w > 0)",
            "intended_use": "re-risking quality filter",
            "lag_rule": "uses only lagged QQQ interaction activity and lagged/trailing state context",
            "expected_state_path": "EFA/SPY leadership interaction after calm or recovery context",
            "target_family": "recovery_quality",
            "selection_reason": "high-priority SSS rule connecting QQQ interaction value to state path context",
            "priority": "primary",
        },
        {
            "signal_name": "high_transition_instability_signal",
            "source_rule": "high_transition_instability",
            "rule_formula": "state_changes_last_8w >= 3",
            "intended_use": "transition-instability warning",
            "lag_rule": "uses only trailing state-change count",
            "expected_state_path": "rapid recent state changes / high sequence instability",
            "target_family": "recovery_quality / stress / tail watchlist",
            "selection_reason": "SSS watchlist rule needing triple-barrier validation",
            "priority": "watchlist",
        },
        {
            "signal_name": "refined_neutral_deteriorating_signal",
            "source_rule": "refined_neutral_deteriorating",
            "rule_formula": "refined_state_lag1 == 'neutral_deteriorating'",
            "intended_use": "Layer 2B deterioration benchmark comparison",
            "lag_rule": "uses only lagged refined_state",
            "expected_state_path": "neutral_mixed split classified as deteriorating by refined Layer 2B engine",
            "target_family": "stress_transition / underperformance benchmark",
            "selection_reason": "watchlist benchmark; SSS flagged as mostly duplicative with current refined-state engine",
            "priority": "watchlist",
        },
    ]
    definitions = pd.DataFrame(specs)
    source_cols = [
        "rule_name",
        "target",
        "event_count",
        "precision_lift",
        "stability",
        "classification",
        "incrementality_flag",
    ]
    source = usable[[c for c in source_cols if c in usable.columns]].copy()
    agg = source.groupby("rule_name", as_index=False).agg(
        sss_targets=("target", lambda x: "; ".join(sorted(set(map(str, x))))),
        sss_max_event_count=("event_count", "max"),
        sss_max_precision_lift=("precision_lift", "max"),
        sss_min_stability=("stability", "min"),
        sss_classifications=("classification", lambda x: "; ".join(sorted(set(map(str, x))))),
        sss_incrementality_flags=("incrementality_flag", lambda x: "; ".join(sorted(set(map(str, x))))),
    )
    definitions = definitions.merge(agg, left_on="source_rule", right_on="rule_name", how="left").drop(columns=["rule_name"])
    definitions["causal_ok"] = True
    definitions["source_phase"] = "SSS"
    save_csv(definitions, OUT / "sss2_sequence_signal_definitions.csv")
    return definitions


def build_base_panel(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    features = inputs["features"].copy()
    targets = inputs["targets"].copy()
    state = inputs["state"].copy()

    target_drop = [c for c in ["market_state", "refined_state"] if c in targets.columns]
    panel = features.merge(targets.drop(columns=target_drop), on="date", how="left")
    extra_cols = [c for c in state.columns if c == "date" or c not in panel.columns]
    panel = panel.merge(state[extra_cols], on="date", how="left")

    if "ggg1_trailing_vol_13w_lag1" not in panel.columns:
        panel["ggg1_trailing_vol_13w_lag1"] = pd.to_numeric(panel["ggg1_net_return"], errors="coerce").rolling(13).std().shift(1)

    sleeve_cols = [c for c in panel.columns if c.startswith("ggg1_sleeve_weight_")]
    offense_keywords = [
        "dual_momentum_topn",
        "cta_trend_long_only",
        "composite_selective_signals",
        "composite_regime_offense_component",
        "taa_10m_sma",
    ]
    offense_cols = [c for c in sleeve_cols if any(k in c for k in offense_keywords)]
    defense_cols = [c for c in sleeve_cols if "defense" in c or "cash::BIL" in c]
    panel["ggg1_offense_exposure"] = panel[offense_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1) if offense_cols else np.nan
    panel["ggg1_defense_exposure"] = panel[defense_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1) if defense_cols else np.nan
    bil_col = "ggg1_sleeve_weight_cash::BIL"
    panel["ggg1_bil_exposure"] = pd.to_numeric(panel[bil_col], errors="coerce") if bil_col in panel.columns else np.nan
    for col, label in [("ggg1_bil_exposure", "bil"), ("ggg1_offense_exposure", "offense"), ("ggg1_defense_exposure", "defense")]:
        x = pd.to_numeric(panel[col], errors="coerce")
        hi = x.quantile(0.75)
        lo = x.quantile(0.25)
        panel[f"high_{label}_exposure"] = (x >= hi).astype(int)
        panel[f"low_{label}_exposure"] = (x <= lo).astype(int)
    return panel.sort_values("date").reset_index(drop=True)


def build_signal_panel(panel: pd.DataFrame, definitions: pd.DataFrame) -> pd.DataFrame:
    out = panel[[
        "date",
        "market_state",
        "refined_state",
        "risk_state",
        "state_lag1",
        "refined_state_lag1",
        "path2_lag",
        "path3_lag",
        "state_age_lag1",
        "state_dwell_bucket_lag1",
        "stress_count_last_4w",
        "stress_count_last_8w",
        "stress_count_last_13w",
        "stress_count_last_26w",
        "recovery_count_last_13w",
        "state_changes_last_8w",
        "state_entropy_last_8w",
        "time_since_last_stressed_panic",
        "qqq_active_int_efa_spy_strength_x_market_trend_lag1",
        "ggg1_bil_exposure",
        "ggg1_offense_exposure",
        "ggg1_defense_exposure",
        "high_bil_exposure",
        "high_offense_exposure",
    ]].copy()

    out["calm_old_low_stress_signal"] = (
        panel["state_lag1"].eq("calm_trend")
        & (pd.to_numeric(panel["state_age_lag1"], errors="coerce") >= 14)
        & (pd.to_numeric(panel["stress_count_last_13w"], errors="coerce") == 0)
    ).astype(int)
    out["stress_new_state_signal"] = (
        panel["state_lag1"].eq("stressed_panic")
        & (pd.to_numeric(panel["state_age_lag1"], errors="coerce") <= 2)
    ).astype(int)
    out["stress_memory_neutral_signal"] = (
        panel["state_lag1"].eq("neutral_mixed")
        & (pd.to_numeric(panel["stress_count_last_13w"], errors="coerce") > 0)
    ).astype(int)
    out["qqq_efa_spy_trend_after_calm_or_recovery_signal"] = (
        (pd.to_numeric(panel["qqq_active_int_efa_spy_strength_x_market_trend_lag1"], errors="coerce") > 0.05)
        & (panel["state_lag1"].eq("calm_trend") | (pd.to_numeric(panel["recovery_count_last_13w"], errors="coerce") > 0))
    ).astype(int)
    out["high_transition_instability_signal"] = (
        pd.to_numeric(panel["state_changes_last_8w"], errors="coerce") >= 3
    ).astype(int)
    out["refined_neutral_deteriorating_signal"] = panel["refined_state_lag1"].eq("neutral_deteriorating").astype(int)

    for sig in SIGNALS:
        out[f"{sig}_score"] = out[sig].astype(float)

    manifest_rows = []
    for _, row in definitions.iterrows():
        sig = row["signal_name"]
        manifest_rows.append({
            "feature_name": sig,
            "feature_type": "binary_sequence_signal",
            "source_rule": row["source_rule"],
            "rule_formula": row["rule_formula"],
            "priority": row["priority"],
            "intended_use": row["intended_use"],
            "lagged_causal": True,
            "uses_future_state": False,
            "uses_forward_return": False,
            "missingness": float(out[sig].isna().mean()),
            "event_count": int(out[sig].sum()),
            "event_frequency": float(out[sig].mean()),
        })
    manifest = pd.DataFrame(manifest_rows)
    missing = []
    for sig in SIGNALS:
        stats = event_run_stats(out["date"], out[sig])
        missing.append({
            "signal_name": sig,
            "missing_count": int(out[sig].isna().sum()),
            "missing_rate": float(out[sig].isna().mean()),
            "event_count": int(out[sig].sum()),
            "event_frequency": float(out[sig].mean()),
            **stats,
        })
    missingness = pd.DataFrame(missing)
    leakage = pd.DataFrame([
        {"check": "all_signal_inputs_lagged_or_trailing", "status": "PASS", "detail": "Formulas use state_lag1, refined_state_lag1, lagged QQQ activity, trailing stress/recovery counts, trailing state changes, and lagged dwell age."},
        {"check": "no_future_state_features", "status": "PASS", "detail": "Signal panel excludes future regime labels; current market_state/refined_state retained only for diagnostics and same-state baselines."},
        {"check": "no_forward_returns_as_features", "status": "PASS", "detail": "Signal panel does not include forward return, target, or future path columns."},
        {"check": "no_random_splits", "status": "PASS", "detail": "Validation uses deterministic calendar subperiods and pre-2016/2016-forward holdout comparisons."},
        {"check": "sss_queue_filter", "status": "PASS", "detail": "Only SSS high-priority/promising rules and watchlist NEEDS_TRIPLE_BARRIER_VALIDATION rules were converted."},
        {"check": "production_shadow_ggg1_unchanged", "status": "PASS", "detail": "Script reads production, shadow, and GGG1 artifacts only; it creates no strategy variants or portfolio candidates."},
    ])

    save_csv(out, OUT / "sss2_sequence_signal_panel.csv")
    save_csv(manifest, OUT / "sss2_sequence_signal_manifest.csv")
    save_csv(missingness, OUT / "sss2_signal_missingness.csv")
    save_csv(leakage, OUT / "sss2_leakage_checklist.csv")
    return out


def attach_signals(panel: pd.DataFrame, signal_panel: pd.DataFrame) -> pd.DataFrame:
    sig_cols = ["date"] + SIGNALS + [f"{s}_score" for s in SIGNALS]
    return panel.merge(signal_panel[sig_cols], on="date", how="left")


def event_validation(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    state_rows = []
    run_stats_by_signal = {sig: event_run_stats(panel["date"], panel[sig]) for sig in SIGNALS}

    for sig in SIGNALS:
        event_mask_all = panel[sig].fillna(0).astype(int).eq(1)
        for target, meta in TARGET_META.items():
            if target not in panel.columns:
                continue
            valid = panel[target].notna()
            event_mask = event_mask_all & valid
            all_mask = valid
            ret_col = meta["return_col"]
            event_count = int(event_mask.sum())
            event_freq = float(event_count / max(int(all_mask.sum()), 1))
            precision = safe_rate(panel.loc[event_mask, target])
            baseline_precision = safe_rate(panel.loc[all_mask, target])
            same_current = weighted_same_group_mean(panel.loc[all_mask].copy(), event_mask.loc[all_mask], "market_state", target)
            same_lagged = weighted_same_group_mean(panel.loc[all_mask].copy(), event_mask.loc[all_mask], "state_lag1", target)
            event_return = safe_mean(panel.loc[event_mask, ret_col]) if ret_col in panel.columns else np.nan
            all_return = safe_mean(panel.loc[all_mask, ret_col]) if ret_col in panel.columns else np.nan
            same_current_return = weighted_same_group_return(panel.loc[all_mask].copy(), event_mask.loc[all_mask], "market_state", ret_col) if ret_col in panel.columns else np.nan
            same_lagged_return = weighted_same_group_return(panel.loc[all_mask].copy(), event_mask.loc[all_mask], "state_lag1", ret_col) if ret_col in panel.columns else np.nan
            adverse_freq = safe_rate(panel.loc[event_mask, "ggg1_tail_risk_4w"]) if "ggg1_tail_risk_4w" in panel.columns else np.nan
            same_state_tail = weighted_same_group_mean(panel.loc[all_mask].copy(), event_mask.loc[all_mask], "state_lag1", "ggg1_tail_risk_4w") if "ggg1_tail_risk_4w" in panel.columns else np.nan
            rows.append({
                "signal_name": sig,
                "target": target,
                "target_direction": meta["direction"],
                "horizon_weeks": meta["horizon"],
                "valid_observations": int(all_mask.sum()),
                "event_count": event_count,
                "event_frequency": event_freq,
                "target_positive_rate_during_event": precision,
                "unconditional_positive_rate": baseline_precision,
                "same_current_state_positive_rate": same_current,
                "same_lagged_state_positive_rate": same_lagged,
                "precision_lift_vs_all_weeks": precision - baseline_precision if pd.notna(precision) and pd.notna(baseline_precision) else np.nan,
                "precision_lift_vs_same_current_state": precision - same_current if pd.notna(precision) and pd.notna(same_current) else np.nan,
                "precision_lift_vs_same_lagged_state": precision - same_lagged if pd.notna(precision) and pd.notna(same_lagged) else np.nan,
                "avg_forward_return_during_event": event_return,
                "avg_forward_return_all_weeks": all_return,
                "avg_forward_return_same_current_state": same_current_return,
                "avg_forward_return_same_lagged_state": same_lagged_return,
                "return_lift_vs_all_weeks": event_return - all_return if pd.notna(event_return) and pd.notna(all_return) else np.nan,
                "return_lift_vs_same_current_state": event_return - same_current_return if pd.notna(event_return) and pd.notna(same_current_return) else np.nan,
                "return_lift_vs_same_lagged_state": event_return - same_lagged_return if pd.notna(event_return) and pd.notna(same_lagged_return) else np.nan,
                "adverse_tail_frequency_during_event": adverse_freq,
                "adverse_tail_frequency_same_lagged_state": same_state_tail,
                "adverse_tail_lift_vs_same_lagged_state": adverse_freq - same_state_tail if pd.notna(adverse_freq) and pd.notna(same_state_tail) else np.nan,
                **run_stats_by_signal[sig],
            })

        event_rows = panel[event_mask_all].copy()
        if not event_rows.empty:
            group_cols = ["market_state", "refined_state", "state_lag1", "refined_state_lag1", "path2_lag", "path3_lag"]
            for keys, group in event_rows.groupby(group_cols, dropna=False):
                record = {"signal_name": sig, "event_count": int(len(group))}
                for col, val in zip(group_cols, keys):
                    record[col] = val
                for target in TARGET_META:
                    if target in group.columns:
                        record[f"{target}_positive_rate"] = safe_rate(group[target])
                for ret_col in ["ggg1_fwd_return_4w", "ggg1_fwd_return_8w", "ggg1_future_min_path_return_4w", "ggg1_future_min_path_return_8w"]:
                    if ret_col in group.columns:
                        record[f"avg_{ret_col}"] = safe_mean(group[ret_col])
                state_rows.append(record)

    summary = pd.DataFrame(rows)
    state_summary = pd.DataFrame(state_rows).sort_values(["signal_name", "event_count"], ascending=[True, False])
    matrix = summary.pivot_table(
        index="signal_name",
        columns="target",
        values=["event_count", "precision_lift_vs_all_weeks", "precision_lift_vs_same_lagged_state", "return_lift_vs_same_lagged_state"],
        aggfunc="first",
    )
    matrix.columns = ["__".join(map(str, c)).strip() for c in matrix.columns.to_flat_index()]
    matrix = matrix.reset_index()

    save_csv(summary, OUT / "sss2_event_validation_summary.csv")
    save_csv(state_summary, OUT / "sss2_event_state_path_summary.csv")
    save_csv(matrix, OUT / "sss2_event_target_matrix.csv")
    return summary, state_summary, matrix


def compute_triple_barrier_base(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    returns = pd.to_numeric(panel["ggg1_net_return"], errors="coerce")
    vol = pd.to_numeric(panel["ggg1_trailing_vol_13w_lag1"], errors="coerce")
    records = []
    for i, row in panel.iterrows():
        if pd.isna(vol.iloc[i]) or vol.iloc[i] <= 0 or i + horizon >= len(panel):
            records.append({
                "date": row["date"],
                "horizon_weeks": horizon,
                "barrier_vol": vol.iloc[i],
                "upper_barrier": np.nan,
                "lower_barrier": np.nan,
                "first_hit": "no_data",
                "hit_week": np.nan,
                "end_return": np.nan,
                "min_path_return": np.nan,
                "max_path_return": np.nan,
            })
            continue
        upper = float(vol.iloc[i] * math.sqrt(horizon))
        lower = -upper
        path_values = []
        cumulative = 1.0
        first_hit = "vertical"
        hit_week = horizon
        valid = True
        for k in range(1, horizon + 1):
            r = returns.iloc[i + k]
            if pd.isna(r):
                valid = False
                break
            cumulative *= (1.0 + float(r))
            path_return = cumulative - 1.0
            path_values.append(path_return)
            if first_hit == "vertical" and path_return >= upper:
                first_hit = "upper"
                hit_week = k
            elif first_hit == "vertical" and path_return <= lower:
                first_hit = "lower"
                hit_week = k
        if not valid or len(path_values) < horizon:
            first_hit = "no_data"
            hit_week = np.nan
            end_return = min_ret = max_ret = np.nan
        else:
            end_return = path_values[-1]
            min_ret = min(path_values)
            max_ret = max(path_values)
        records.append({
            "date": row["date"],
            "horizon_weeks": horizon,
            "barrier_vol": vol.iloc[i],
            "upper_barrier": upper,
            "lower_barrier": lower,
            "first_hit": first_hit,
            "hit_week": hit_week,
            "end_return": end_return,
            "min_path_return": min_ret,
            "max_path_return": max_ret,
        })
    return pd.DataFrame(records)


def tb_stats(tb: pd.DataFrame) -> dict[str, float]:
    valid = tb[tb["first_hit"].ne("no_data")].copy()
    if valid.empty:
        return {
            "path_count": 0,
            "upper_hit_rate": np.nan,
            "lower_hit_rate": np.nan,
            "vertical_rate": np.nan,
            "avg_end_return": np.nan,
            "avg_min_path_return": np.nan,
            "avg_max_path_return": np.nan,
            "risk_warning_success_rate": np.nan,
            "risk_on_success_rate": np.nan,
        }
    lower_half = -0.5 * valid["upper_barrier"].abs()
    risk_warning_success = valid["first_hit"].eq("lower") | valid["end_return"].lt(0) | valid["min_path_return"].lt(lower_half)
    risk_on_success = valid["first_hit"].eq("upper") | (valid["end_return"].gt(0) & ~valid["first_hit"].eq("lower"))
    return {
        "path_count": int(len(valid)),
        "upper_hit_rate": float(valid["first_hit"].eq("upper").mean()),
        "lower_hit_rate": float(valid["first_hit"].eq("lower").mean()),
        "vertical_rate": float(valid["first_hit"].eq("vertical").mean()),
        "avg_end_return": safe_mean(valid["end_return"]),
        "avg_min_path_return": safe_mean(valid["min_path_return"]),
        "avg_max_path_return": safe_mean(valid["max_path_return"]),
        "risk_warning_success_rate": float(risk_warning_success.mean()),
        "risk_on_success_rate": float(risk_on_success.mean()),
    }


def weighted_tb_baseline(panel: pd.DataFrame, tb: pd.DataFrame, event_mask: pd.Series, group_col: str) -> dict[str, float]:
    merged = panel[["date", group_col]].merge(tb, on="date", how="left")
    event_groups = panel.loc[event_mask & panel[group_col].notna(), group_col]
    if event_groups.empty:
        return tb_stats(tb.iloc[0:0])
    rows = []
    for g in event_groups:
        rows.append(merged[merged[group_col].eq(g)])
    if not rows:
        return tb_stats(tb.iloc[0:0])
    return tb_stats(pd.concat(rows, ignore_index=True))


def triple_barrier_validation(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    outcomes = []
    summary_rows = []
    asym_rows = []
    base_by_horizon = {h: compute_triple_barrier_base(panel, h) for h in [4, 8, 13]}
    for sig in SIGNALS:
        event_mask = panel[sig].fillna(0).astype(int).eq(1)
        signal_direction = "risk_warning" if sig in RISK_WARNING_SIGNALS else "risk_on_confirmation"
        for horizon, tb in base_by_horizon.items():
            event_tb = tb.merge(panel[["date", sig, "market_state", "state_lag1", "refined_state_lag1"]], on="date", how="left")
            event_tb = event_tb[event_tb[sig].fillna(0).astype(int).eq(1)].copy()
            event_tb["signal_name"] = sig
            event_tb["signal_intended_direction"] = signal_direction
            outcomes.append(event_tb)

            event_stats = tb_stats(event_tb)
            all_stats = tb_stats(tb)
            same_lagged_stats = weighted_tb_baseline(panel, tb, event_mask, "state_lag1")
            same_current_stats = weighted_tb_baseline(panel, tb, event_mask, "market_state")
            row = {
                "signal_name": sig,
                "horizon_weeks": horizon,
                "signal_intended_direction": signal_direction,
                **{f"event_{k}": v for k, v in event_stats.items()},
                **{f"all_weeks_{k}": v for k, v in all_stats.items()},
                **{f"same_lagged_state_{k}": v for k, v in same_lagged_stats.items()},
                **{f"same_current_state_{k}": v for k, v in same_current_stats.items()},
            }
            for key in [
                "upper_hit_rate",
                "lower_hit_rate",
                "avg_end_return",
                "avg_min_path_return",
                "risk_warning_success_rate",
                "risk_on_success_rate",
            ]:
                row[f"{key}_lift_vs_all_weeks"] = row[f"event_{key}"] - row[f"all_weeks_{key}"] if pd.notna(row[f"event_{key}"]) and pd.notna(row[f"all_weeks_{key}"]) else np.nan
                row[f"{key}_lift_vs_same_lagged_state"] = row[f"event_{key}"] - row[f"same_lagged_state_{key}"] if pd.notna(row[f"event_{key}"]) and pd.notna(row[f"same_lagged_state_{key}"]) else np.nan
            summary_rows.append(row)
            success_key = "risk_warning_success_rate" if signal_direction == "risk_warning" else "risk_on_success_rate"
            asym_rows.append({
                "signal_name": sig,
                "horizon_weeks": horizon,
                "signal_intended_direction": signal_direction,
                "event_lower_minus_upper_hit_rate": row["event_lower_hit_rate"] - row["event_upper_hit_rate"],
                "all_weeks_lower_minus_upper_hit_rate": row["all_weeks_lower_hit_rate"] - row["all_weeks_upper_hit_rate"],
                "same_lagged_state_lower_minus_upper_hit_rate": row["same_lagged_state_lower_hit_rate"] - row["same_lagged_state_upper_hit_rate"],
                "preferred_success_metric": success_key,
                "preferred_success_rate": row[f"event_{success_key}"],
                "preferred_success_lift_vs_all_weeks": row[f"{success_key}_lift_vs_all_weeks"],
                "preferred_success_lift_vs_same_lagged_state": row[f"{success_key}_lift_vs_same_lagged_state"],
                "avg_end_return_lift_vs_same_lagged_state": row["avg_end_return_lift_vs_same_lagged_state"],
                "avg_min_path_return_lift_vs_same_lagged_state": row["avg_min_path_return_lift_vs_same_lagged_state"],
            })

    outcomes_df = pd.concat(outcomes, ignore_index=True) if outcomes else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    asym = pd.DataFrame(asym_rows)
    save_csv(outcomes_df, OUT / "sss2_triple_barrier_outcomes.csv")
    save_csv(summary, OUT / "sss2_triple_barrier_summary.csv")
    save_csv(asym, OUT / "sss2_path_outcome_asymmetry.csv")
    return outcomes_df, summary, asym


def period_masks(panel: pd.DataFrame) -> dict[str, pd.Series]:
    d = pd.to_datetime(panel["date"])
    return {
        "pre_2016": d < pd.Timestamp("2016-01-01"),
        "2016_forward": d >= pd.Timestamp("2016-01-01"),
        "2010_2015": (d >= pd.Timestamp("2010-01-01")) & (d < pd.Timestamp("2016-01-01")),
        "2016_2020": (d >= pd.Timestamp("2016-01-01")) & (d < pd.Timestamp("2021-01-01")),
        "2021_2026": d >= pd.Timestamp("2021-01-01"),
    }


def event_stats_for_subset(panel: pd.DataFrame, mask: pd.Series, sig: str, target: str) -> dict[str, float]:
    meta = TARGET_META[target]
    sub = panel[mask & panel[target].notna()].copy()
    event_mask = sub[sig].fillna(0).astype(int).eq(1)
    ret_col = meta["return_col"]
    precision = safe_rate(sub.loc[event_mask, target])
    baseline = safe_rate(sub[target])
    same_lagged = weighted_same_group_mean(sub, event_mask, "state_lag1", target)
    event_return = safe_mean(sub.loc[event_mask, ret_col]) if ret_col in sub.columns else np.nan
    all_return = safe_mean(sub[ret_col]) if ret_col in sub.columns else np.nan
    same_ret = weighted_same_group_return(sub, event_mask, "state_lag1", ret_col) if ret_col in sub.columns else np.nan
    return {
        "valid_observations": int(len(sub)),
        "event_count": int(event_mask.sum()),
        "event_frequency": float(event_mask.mean()) if len(sub) else np.nan,
        "precision": precision,
        "baseline_precision": baseline,
        "same_lagged_state_precision": same_lagged,
        "precision_lift_vs_all_weeks": precision - baseline if pd.notna(precision) and pd.notna(baseline) else np.nan,
        "precision_lift_vs_same_lagged_state": precision - same_lagged if pd.notna(precision) and pd.notna(same_lagged) else np.nan,
        "avg_forward_return": event_return,
        "baseline_avg_forward_return": all_return,
        "same_lagged_state_avg_forward_return": same_ret,
        "return_lift_vs_all_weeks": event_return - all_return if pd.notna(event_return) and pd.notna(all_return) else np.nan,
        "return_lift_vs_same_lagged_state": event_return - same_ret if pd.notna(event_return) and pd.notna(same_ret) else np.nan,
    }


def stability_validation(panel: pd.DataFrame, tb_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    masks = period_masks(panel)
    group_masks = {}
    for state in sorted(panel["market_state"].dropna().unique()):
        group_masks[f"state::{state}"] = panel["market_state"].eq(state)
    for state in sorted(panel["refined_state"].dropna().unique()):
        group_masks[f"refined::{state}"] = panel["refined_state"].eq(state)
    top_paths = panel["path2_lag"].value_counts(dropna=True).head(12).index
    for path in top_paths:
        group_masks[f"path2::{path}"] = panel["path2_lag"].eq(path)
    masks.update(group_masks)

    for sig in SIGNALS:
        for target in PRIMARY_TARGETS[sig]:
            if target not in panel.columns:
                continue
            for period, mask in masks.items():
                stats = event_stats_for_subset(panel, mask, sig, target)
                rows.append({"signal_name": sig, "target": target, "period": period, **stats})

    subperiod = pd.DataFrame(rows)

    hold_rows = []
    train_mask = masks["pre_2016"]
    holdout_mask = masks["2016_forward"]
    asym_lookup = tb_summary[tb_summary["horizon_weeks"].isin([4, 8])].copy()
    for sig in SIGNALS:
        for target in PRIMARY_TARGETS[sig]:
            if target not in panel.columns:
                continue
            train = event_stats_for_subset(panel, train_mask, sig, target)
            hold = event_stats_for_subset(panel, holdout_mask, sig, target)
            horizon = TARGET_META[target]["horizon"]
            tb = asym_lookup[(asym_lookup["signal_name"].eq(sig)) & (asym_lookup["horizon_weeks"].eq(horizon))]
            tb_success_lift = np.nan
            if not tb.empty:
                key = "risk_warning_success_rate_lift_vs_same_lagged_state" if sig in RISK_WARNING_SIGNALS else "risk_on_success_rate_lift_vs_same_lagged_state"
                tb_success_lift = float(tb.iloc[0].get(key, np.nan))
            train_lift = train["precision_lift_vs_same_lagged_state"]
            hold_lift = hold["precision_lift_vs_same_lagged_state"]
            hold_rows.append({
                "signal_name": sig,
                "target": target,
                "train_period": "pre_2016",
                "holdout_period": "2016_forward",
                "train_event_count": train["event_count"],
                "holdout_event_count": hold["event_count"],
                "train_precision_lift_vs_same_lagged_state": train_lift,
                "holdout_precision_lift_vs_same_lagged_state": hold_lift,
                "train_return_lift_vs_same_lagged_state": train["return_lift_vs_same_lagged_state"],
                "holdout_return_lift_vs_same_lagged_state": hold["return_lift_vs_same_lagged_state"],
                "sign_consistent": bool(pd.notna(train_lift) and pd.notna(hold_lift) and np.sign(train_lift) == np.sign(hold_lift) and np.sign(hold_lift) > 0),
                "enough_holdout_events": bool(hold["event_count"] >= 8),
                "triple_barrier_preferred_success_lift_vs_same_lagged_state": tb_success_lift,
                "holdout_validation_flag": "PASS" if hold["event_count"] >= 8 and pd.notna(hold_lift) and hold_lift > 0.03 and (pd.isna(train_lift) or train_lift >= -0.02) else "FAIL_OR_WEAK",
            })
    holdout = pd.DataFrame(hold_rows)
    save_csv(subperiod, OUT / "sss2_subperiod_stability.csv")
    save_csv(holdout, OUT / "sss2_holdout_validation_summary.csv")
    return subperiod, holdout


def make_binary_comparison_features(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    state_like = ["market_state", "state_lag1", "state_lag2", "state_lag4", "state_dwell_bucket_lag1", "path2_lag"]
    refined_like = ["refined_state", "refined_state_lag1"]
    for name, cols in [("market_state_engine", state_like), ("refined_state_engine", refined_like)]:
        parts = []
        for col in cols:
            if col in panel.columns:
                d = pd.get_dummies(panel[col].fillna("MISSING"), prefix=col, dtype=float)
                parts.append(d)
        features[name] = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=panel.index)
    l2b_cols = [c for c in panel.columns if c.startswith("l2b_") or c.startswith("p_") or c in ["risk_regime_score", "market_drawdown", "deterioration_z", "confidence_score_p2b", "defensive_overlay_hint"]]
    derived_signal_cols = set(SIGNALS + [f"{s}_score" for s in SIGNALS])
    qqq_cols = [c for c in panel.columns if c.startswith("qqq_") and c not in derived_signal_cols]
    ooo_cols = [c for c in panel.columns if c.startswith("ooo")]
    exposure_cols = [c for c in panel.columns if c.startswith("ggg1_sleeve_weight_") or c in [
        "ggg1_bil_exposure",
        "ggg1_offense_exposure",
        "ggg1_defense_exposure",
        "high_bil_exposure",
        "low_bil_exposure",
        "high_offense_exposure",
        "low_offense_exposure",
        "high_defense_exposure",
        "low_defense_exposure",
    ]]
    features["layer2b_numeric"] = panel[l2b_cols].apply(pd.to_numeric, errors="coerce") if l2b_cols else pd.DataFrame(index=panel.index)
    features["qqq_signals"] = panel[qqq_cols].apply(pd.to_numeric, errors="coerce") if qqq_cols else pd.DataFrame(index=panel.index)
    features["ooo_signals"] = panel[ooo_cols].apply(pd.to_numeric, errors="coerce") if ooo_cols else pd.DataFrame(index=panel.index)
    features["ggg1_exposure"] = panel[exposure_cols].apply(pd.to_numeric, errors="coerce") if exposure_cols else pd.DataFrame(index=panel.index)
    return features


def overlap_stats(signal: pd.Series, comp: pd.Series) -> dict[str, float]:
    sig = pd.to_numeric(signal, errors="coerce").fillna(0).astype(int)
    x = pd.to_numeric(comp, errors="coerce")
    if x.dropna().nunique() <= 2:
        binary = x.fillna(0).astype(float).gt(0)
    else:
        q = x.quantile(0.75)
        binary = x.ge(q)
    event_count = int(sig.sum())
    if event_count == 0:
        overlap = np.nan
    else:
        overlap = float(binary[sig.eq(1)].mean())
    union = (sig.eq(1) | binary).sum()
    jaccard = float(((sig.eq(1)) & binary).sum() / union) if union else np.nan
    return {
        "corr": safe_corr(sig, x),
        "abs_corr": abs(safe_corr(sig, x)) if pd.notna(safe_corr(sig, x)) else np.nan,
        "event_overlap_rate": overlap,
        "jaccard_overlap": jaccard,
    }


def redundancy_incrementality(
    panel: pd.DataFrame,
    event_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    groups = make_binary_comparison_features(panel)
    detail_rows = []
    for sig in SIGNALS:
        for group_name, comps in groups.items():
            for col in comps.columns:
                stats = overlap_stats(panel[sig], comps[col])
                detail_rows.append({
                    "signal_name": sig,
                    "comparison_group": group_name,
                    "comparison_feature": col,
                    **stats,
                })
    detail = pd.DataFrame(detail_rows)
    if detail.empty:
        detail = pd.DataFrame(columns=["signal_name", "comparison_group", "comparison_feature", "corr", "abs_corr", "event_overlap_rate", "jaccard_overlap"])
    summary = detail.sort_values(["signal_name", "comparison_group", "abs_corr"], ascending=[True, True, False]).groupby(["signal_name", "comparison_group"], as_index=False).head(1)
    summary = summary.rename(columns={
        "comparison_feature": "closest_feature",
        "abs_corr": "max_abs_corr",
        "event_overlap_rate": "max_event_overlap_rate",
    })

    layer2b = detail[detail["comparison_group"].isin(["market_state_engine", "refined_state_engine", "layer2b_numeric"])].sort_values(["signal_name", "abs_corr"], ascending=[True, False])
    ooo_qqq = detail[detail["comparison_group"].isin(["ooo_signals", "qqq_signals"])].sort_values(["signal_name", "abs_corr"], ascending=[True, False])
    exposure = detail[detail["comparison_group"].eq("ggg1_exposure")].sort_values(["signal_name", "abs_corr"], ascending=[True, False])

    inc_rows = []
    for sig in SIGNALS:
        candidates = event_summary[(event_summary["signal_name"].eq(sig)) & (event_summary["target"].isin(PRIMARY_TARGETS[sig]))].copy()
        if candidates.empty:
            continue
        candidates = candidates[candidates["event_count"].fillna(0) >= 25].copy() if candidates["event_count"].fillna(0).ge(25).any() else candidates
        candidates["rank_score"] = candidates["precision_lift_vs_same_lagged_state"].fillna(-999) + 0.25 * candidates["precision_lift_vs_all_weeks"].fillna(0)
        best = candidates.sort_values("rank_score", ascending=False).iloc[0]
        group_max = summary[summary["signal_name"].eq(sig)].set_index("comparison_group")
        def get(group: str, col: str, default=np.nan):
            return group_max.loc[group, col] if group in group_max.index else default
        max_market = get("market_state_engine", "max_abs_corr")
        max_refined = get("refined_state_engine", "max_abs_corr")
        max_l2b = max(get("layer2b_numeric", "max_abs_corr", 0), max_market if pd.notna(max_market) else 0, max_refined if pd.notna(max_refined) else 0)
        max_ooo = get("ooo_signals", "max_abs_corr")
        max_qqq = get("qqq_signals", "max_abs_corr")
        same_lift = best["precision_lift_vs_same_lagged_state"]
        all_lift = best["precision_lift_vs_all_weeks"]
        event_count = best["event_count"]
        if event_count < 25:
            flag = "TOO_RARE"
        elif sig == "refined_neutral_deteriorating_signal" or (pd.notna(max_refined) and max_refined >= 0.85):
            flag = "MOSTLY_REFINED_STATE_PROXY"
        elif pd.notna(max_market) and max_market >= 0.85 and (pd.isna(same_lift) or same_lift <= 0.03):
            flag = "MOSTLY_MARKET_STATE_PROXY"
        elif sig.startswith("qqq_") and pd.notna(max_qqq) and max_qqq >= 0.70:
            flag = "MOSTLY_OOO_QQQ_PROXY" if (pd.isna(same_lift) or same_lift <= 0.05) else "ACTIONABLE_BUT_STATE_DEPENDENT"
        elif pd.notna(same_lift) and same_lift > 0.05 and event_count >= 30 and (pd.isna(max_l2b) or max_l2b < 0.85):
            flag = "INCREMENTAL_TO_LAYER2B"
        elif pd.notna(all_lift) and all_lift > 0.05:
            flag = "ACTIONABLE_BUT_STATE_DEPENDENT"
        else:
            flag = "NOT_ACTIONABLE"
        inc_rows.append({
            "signal_name": sig,
            "best_target": best["target"],
            "event_count": int(event_count),
            "event_frequency": best["event_frequency"],
            "precision_lift_vs_all_weeks": all_lift,
            "precision_lift_vs_same_lagged_state": same_lift,
            "return_lift_vs_same_lagged_state": best["return_lift_vs_same_lagged_state"],
            "max_abs_corr_market_state_engine": max_market,
            "closest_market_state_feature": get("market_state_engine", "closest_feature", ""),
            "max_abs_corr_refined_state_engine": max_refined,
            "closest_refined_state_feature": get("refined_state_engine", "closest_feature", ""),
            "max_abs_corr_layer2b_numeric": get("layer2b_numeric", "max_abs_corr"),
            "closest_layer2b_feature": get("layer2b_numeric", "closest_feature", ""),
            "max_abs_corr_ooo_signals": max_ooo,
            "closest_ooo_feature": get("ooo_signals", "closest_feature", ""),
            "max_abs_corr_qqq_signals": max_qqq,
            "closest_qqq_feature": get("qqq_signals", "closest_feature", ""),
            "incrementality_flag": flag,
            "adds_timing_beyond_current_state": bool(pd.notna(same_lift) and same_lift > 0.03),
            "actionable": bool(flag in {"INCREMENTAL_TO_LAYER2B", "ACTIONABLE_BUT_STATE_DEPENDENT"}),
        })
    incrementality = pd.DataFrame(inc_rows)

    save_csv(summary, OUT / "sss2_sequence_signal_redundancy.csv")
    save_csv(incrementality, OUT / "sss2_sequence_signal_incrementality.csv")
    save_csv(ooo_qqq, OUT / "sss2_ooo_qqq_overlap.csv")
    save_csv(layer2b, OUT / "sss2_layer2b_overlap.csv")
    save_csv(exposure, OUT / "sss2_ggg1_exposure_overlap.csv")
    return summary, incrementality, ooo_qqq, layer2b, exposure


def keep_reject_decisions(
    event_summary: pd.DataFrame,
    tb_summary: pd.DataFrame,
    holdout: pd.DataFrame,
    incrementality: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for sig in SIGNALS:
        inc = incrementality[incrementality["signal_name"].eq(sig)]
        if inc.empty:
            continue
        incrementality_flag = inc.iloc[0]["incrementality_flag"]

        target_candidates = []
        for target_rank, target in enumerate(PRIMARY_TARGETS[sig]):
            ev = event_summary[(event_summary["signal_name"].eq(sig)) & (event_summary["target"].eq(target))]
            if ev.empty or target not in TARGET_META:
                continue
            ho = holdout[(holdout["signal_name"].eq(sig)) & (holdout["target"].eq(target))]
            horizon = TARGET_META[target]["horizon"]
            tb = tb_summary[(tb_summary["signal_name"].eq(sig)) & (tb_summary["horizon_weeks"].eq(horizon))]
            evrow = ev.iloc[0]
            horow = ho.iloc[0] if not ho.empty else pd.Series(dtype=object)
            tbrow = tb.iloc[0] if not tb.empty else pd.Series(dtype=object)

            event_count = int(evrow.get("event_count", 0))
            same_lift = evrow.get("precision_lift_vs_same_lagged_state", np.nan)
            all_lift = evrow.get("precision_lift_vs_all_weeks", np.nan)
            turnover = evrow.get("event_starts_per_year", np.nan)
            holdout_flag = horow.get("holdout_validation_flag", "FAIL_OR_WEAK")
            holdout_lift = horow.get("holdout_precision_lift_vs_same_lagged_state", np.nan)
            if sig in RISK_WARNING_SIGNALS:
                tb_success_lift = tbrow.get("risk_warning_success_rate_lift_vs_same_lagged_state", np.nan)
                tb_path_lift = tbrow.get("lower_hit_rate_lift_vs_same_lagged_state", np.nan)
                avg_end_lift = tbrow.get("avg_end_return_lift_vs_same_lagged_state", np.nan)
                direction_ok = (pd.notna(tb_success_lift) and tb_success_lift > 0.03) or (pd.notna(tb_path_lift) and tb_path_lift > 0.02) or (pd.notna(avg_end_lift) and avg_end_lift < -0.002)
            else:
                tb_success_lift = tbrow.get("risk_on_success_rate_lift_vs_same_lagged_state", np.nan)
                tb_path_lift = tbrow.get("upper_hit_rate_lift_vs_same_lagged_state", np.nan)
                direction_ok = (pd.notna(tb_success_lift) and tb_success_lift > 0.03) or (pd.notna(tb_path_lift) and tb_path_lift > 0.02)
            enough_events = event_count >= 40
            stable_holdout = holdout_flag == "PASS"
            same_state_ok = pd.notna(same_lift) and same_lift > 0.05
            turnover_ok = pd.isna(turnover) or turnover <= 12
            incremental_ok = incrementality_flag in {"INCREMENTAL_TO_LAYER2B", "ACTIONABLE_BUT_STATE_DEPENDENT"}
            pass_gate = enough_events and stable_holdout and same_state_ok and direction_ok and incremental_ok and turnover_ok
            score = (
                (10 if pass_gate else 0)
                + (2 if enough_events else 0)
                + (2 if stable_holdout else 0)
                + (2 if same_state_ok else 0)
                + (2 if direction_ok else 0)
                + (2 if incremental_ok else 0)
                + float(same_lift if pd.notna(same_lift) else -1)
                + 0.5 * float(holdout_lift if pd.notna(holdout_lift) else -1)
                + 0.25 * (len(PRIMARY_TARGETS[sig]) - target_rank)
            )
            target_candidates.append({
                "best_target": target,
                "event_count": event_count,
                "precision_lift_vs_all_weeks": all_lift,
                "precision_lift_vs_same_lagged_state": same_lift,
                "holdout_precision_lift_vs_same_lagged_state": holdout_lift,
                "triple_barrier_success_lift_vs_same_lagged_state": tb_success_lift,
                "triple_barrier_path_lift_vs_same_lagged_state": tb_path_lift,
                "event_starts_per_year": turnover,
                "incrementality_flag": incrementality_flag,
                "enough_events": enough_events,
                "same_state_ok": same_state_ok,
                "stable_holdout": stable_holdout,
                "path_asymmetry_ok": direction_ok,
                "turnover_ok": turnover_ok,
                "incremental_ok": incremental_ok,
                "pass_gate": pass_gate,
                "target_score": score,
            })
        if not target_candidates:
            continue
        chosen = sorted(target_candidates, key=lambda x: x["target_score"], reverse=True)[0]
        best_target = chosen["best_target"]
        event_count = chosen["event_count"]
        same_lift = chosen["precision_lift_vs_same_lagged_state"]
        all_lift = chosen["precision_lift_vs_all_weeks"]
        holdout_lift = chosen["holdout_precision_lift_vs_same_lagged_state"]
        tb_success_lift = chosen["triple_barrier_success_lift_vs_same_lagged_state"]
        tb_path_lift = chosen["triple_barrier_path_lift_vs_same_lagged_state"]
        turnover = chosen["event_starts_per_year"]
        enough_events = chosen["enough_events"]
        same_state_ok = chosen["same_state_ok"]
        stable_holdout = chosen["stable_holdout"]
        direction_ok = chosen["path_asymmetry_ok"]
        turnover_ok = chosen["turnover_ok"]
        incremental_ok = chosen["incremental_ok"]

        if enough_events and stable_holdout and same_state_ok and direction_ok and incremental_ok and turnover_ok:
            decision = "KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH"
            reason = "event lift, same-state lift, holdout, path asymmetry, incrementality, and turnover gates passed"
        elif incremental_ok and enough_events and (same_state_ok or stable_holdout):
            if sig == "qqq_efa_spy_trend_after_calm_or_recovery_signal":
                decision = "KEEP_FOR_RRR_SLEEVE_META_LABELING"
                reason = "real but maps more naturally to sleeve/re-risking timing than direct portfolio overlay"
            else:
                decision = "KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL"
                reason = "useful diagnostic evidence, but one or more pass-through gates failed"
        elif event_count < 25:
            decision = "NEEDS_MORE_EVENTS"
            reason = "too few events for a reliable pass-through decision"
        elif incrementality_flag in {"MOSTLY_REFINED_STATE_PROXY", "MOSTLY_MARKET_STATE_PROXY", "MOSTLY_OOO_QQQ_PROXY"}:
            decision = "MOSTLY_DUPLICATIVE"
            reason = f"incrementality check flagged {incrementality_flag}"
        elif not stable_holdout:
            decision = "TOO_UNSTABLE"
            reason = "holdout/same-state stability failed"
        else:
            decision = "REJECT"
            reason = "validation did not show actionable incremental evidence"

        rows.append({
            "signal_name": sig,
            "best_target": best_target,
            "decision": decision,
            "reason": reason,
            "event_count": event_count,
            "precision_lift_vs_all_weeks": all_lift,
            "precision_lift_vs_same_lagged_state": same_lift,
            "holdout_precision_lift_vs_same_lagged_state": holdout_lift,
            "triple_barrier_success_lift_vs_same_lagged_state": tb_success_lift,
            "triple_barrier_path_lift_vs_same_lagged_state": tb_path_lift,
            "event_starts_per_year": turnover,
            "incrementality_flag": incrementality_flag,
            "enough_events": enough_events,
            "same_state_ok": same_state_ok,
            "stable_holdout": stable_holdout,
            "path_asymmetry_ok": direction_ok,
            "turnover_ok": turnover_ok,
            "incremental_ok": incremental_ok,
        })
    decisions = pd.DataFrame(rows)

    queue_rows = []
    for _, row in decisions.iterrows():
        if row["decision"] in {"KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH", "KEEP_FOR_RRR_SLEEVE_META_LABELING", "KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL", "NEEDS_MORE_EVENTS"}:
            if row["decision"] == "KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH":
                task = "SSS3 controlled GGG1 pass-through test with tiny bounded overlay and explicit no-promotion default"
            elif row["decision"] == "KEEP_FOR_RRR_SLEEVE_META_LABELING":
                task = "RRR sleeve meta-labeling using sequence signal as sleeve timing/context feature"
            elif row["decision"] == "KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL":
                task = "Additional sequence feature engineering or monitoring diagnostics before portfolio use"
            else:
                task = "Collect more events / broaden related causal sequence family before retesting"
            queue_rows.append({**row.to_dict(), "next_phase_task": task})
    queue = pd.DataFrame(queue_rows)

    if decisions["decision"].eq("KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH").any():
        rec = "PROCEED_TO_SSS3_SEQUENCE_PORTFOLIO_PASS_THROUGH"
        reason = "At least one explicit sequence signal passed event, holdout, path-asymmetry, incrementality, and turnover gates for a controlled diagnostic pass-through."
    elif decisions["decision"].eq("KEEP_FOR_RRR_SLEEVE_META_LABELING").any():
        rec = "PROCEED_TO_RRR_SLEEVE_META_LABELING"
        reason = "Validated sequence evidence maps more naturally to sleeve/component timing than a direct GGG1 portfolio overlay."
    elif decisions["decision"].isin({"KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL", "NEEDS_MORE_EVENTS"}).any():
        rec = "PROCEED_TO_ADDITIONAL_SEQUENCE_FEATURE_ENGINEERING"
        reason = "Some sequence rules retain diagnostic value, but pass-through gates are not clean enough after same-state, holdout, path, and redundancy checks."
    else:
        rec = "STOP_HARD_ML_FOR_NOW"
        reason = "SSS2 validation found the explicit sequence signals unstable, duplicative, or not actionable."
    recommendation = pd.DataFrame([{"recommendation": rec, "reason": reason}])

    save_csv(decisions, OUT / "sss2_signal_keep_reject_decisions.csv")
    save_csv(queue, OUT / "sss2_next_phase_queue.csv")
    save_csv(recommendation, OUT / "sss2_next_action_recommendation.csv")
    return decisions, queue, recommendation


def write_schema(signal_panel: pd.DataFrame) -> None:
    schema = {
        "created_by": "scripts/phase_sss2_sequence_signal_validation.py",
        "date_range": {
            "start": str(pd.to_datetime(signal_panel["date"]).min().date()),
            "end": str(pd.to_datetime(signal_panel["date"]).max().date()),
            "rows": int(len(signal_panel)),
        },
        "signals": SIGNALS,
        "target_columns_excluded_from_signal_panel": list(TARGET_META),
        "production_pin": PRODUCTION,
        "official_shadow_pin": SHADOW,
        "current_production_candidate": GGG1,
    }
    (OUT / "sss2_dataset_schema.json").write_text(json.dumps(schema, indent=2))


def report_prompt_for_next(rec: str) -> str:
    if rec == "PROCEED_TO_SSS3_SEQUENCE_PORTFOLIO_PASS_THROUGH":
        return (
            "Implement Phase SSS3 as diagnostic-only controlled sequence portfolio pass-through. "
            "Use only SSS2 KEEP_FOR_SSS3 signals, apply tiny bounded GGG1 de-risk/re-risk overlays, "
            "compare against production/shadow/GGG1, require holdout and bootstrap discipline, and do not promote automatically."
        )
    if rec == "PROCEED_TO_RRR_SLEEVE_META_LABELING":
        return (
            "Implement Phase RRR sleeve-level meta-labeling. Use SSS2 kept sequence signals, SSS/QQQ context, "
            "and GGG1 sleeve/component returns to test sleeve timing labels with walk-forward validation, "
            "triple-barrier sleeve outcomes, and no portfolio deployment."
        )
    if rec == "PROCEED_TO_ADDITIONAL_SEQUENCE_FEATURE_ENGINEERING":
        return (
            "Implement an additional sequence-feature engineering sprint. Refine stress-memory, calm-age, "
            "transition-instability, and recovery-quality features using causal lagged state paths, then rerun SSS2-style validation."
        )
    return (
        "Stop hard-ML research for now. Preserve SSS2 diagnostics and return to simpler, auditable portfolio or sleeve research only if a new hypothesis appears."
    )


def write_report(
    definitions: pd.DataFrame,
    signal_panel: pd.DataFrame,
    leakage: pd.DataFrame,
    event_summary: pd.DataFrame,
    event_matrix: pd.DataFrame,
    tb_summary: pd.DataFrame,
    asym: pd.DataFrame,
    subperiod: pd.DataFrame,
    holdout: pd.DataFrame,
    redundancy: pd.DataFrame,
    incrementality: pd.DataFrame,
    ooo_qqq: pd.DataFrame,
    layer2b: pd.DataFrame,
    exposure: pd.DataFrame,
    decisions: pd.DataFrame,
    queue: pd.DataFrame,
    recommendation: pd.DataFrame,
    sss_queue: pd.DataFrame,
) -> None:
    rec = recommendation.iloc[0]["recommendation"]
    reason = recommendation.iloc[0]["reason"]
    files = [
        "scripts/phase_sss2_sequence_signal_validation.py",
        "data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_definitions.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_panel.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_manifest.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_signal_missingness.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_leakage_checklist.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_event_validation_summary.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_event_state_path_summary.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_event_target_matrix.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_triple_barrier_outcomes.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_triple_barrier_summary.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_path_outcome_asymmetry.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_subperiod_stability.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_holdout_validation_summary.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_redundancy.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_sequence_signal_incrementality.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_ooo_qqq_overlap.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_layer2b_overlap.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_ggg1_exposure_overlap.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_signal_keep_reject_decisions.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_next_phase_queue.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_next_action_recommendation.csv",
        "data/research/phase_sss2_sequence_signal_validation/sss2_dataset_schema.json",
        "docs/research/2026-04-27_phase_sss2_sequence_signal_validation_report.md",
        "docs/research/project_journey.md",
    ]
    signal_counts = signal_panel[SIGNALS].sum().rename("event_count").reset_index().rename(columns={"index": "signal_name"})
    signal_counts["event_frequency"] = signal_counts["event_count"] / len(signal_panel)
    top_event = event_summary[event_summary["target"].isin(["stress_transition_4w", "stress_transition_8w", "recovery_quality_8w", "ggg1_underperformance_4w", "ggg1_tail_risk_4w"])]
    top_event = top_event.sort_values("precision_lift_vs_same_lagged_state", ascending=False)
    lines = [
        "# Phase SSS2 -- Sequence Signal Validation",
        "",
        "Date: 2026-04-27",
        "",
        "## Commands Executed",
    ]
    lines += [f"- `{cmd}`" for cmd in COMMANDS]
    lines += ["", "## Files Created / Modified"]
    lines += [f"- `{f}`" for f in files]
    lines += [
        "",
        "## SSS Rule Queue Used",
        "Only high-priority/promising SSS rules and watchlist `NEEDS_TRIPLE_BARRIER_VALIDATION` rules were converted. Production/shadow/GGG1 artifacts were read only.",
        markdown_table(sss_queue[["rule_name", "target", "classification", "event_count", "precision_lift", "stability", "incrementality_flag"]], 20),
        "",
        "## Explicit Signal Definitions",
        markdown_table(definitions[["signal_name", "source_rule", "priority", "intended_use", "rule_formula", "causal_ok", "sss_targets", "sss_max_precision_lift"]], 12),
        "",
        "## Signal Panel Summary",
        f"Signal panel rows: {len(signal_panel):,}. Date range: {pd.to_datetime(signal_panel['date']).min().date()} to {pd.to_datetime(signal_panel['date']).max().date()}.",
        markdown_table(signal_counts, 12),
        "",
        "## Leakage Checks",
        markdown_table(leakage, 20),
        "",
        "## Event Validation Summary",
        markdown_table(top_event[["signal_name", "target", "event_count", "target_positive_rate_during_event", "unconditional_positive_rate", "same_lagged_state_positive_rate", "precision_lift_vs_all_weeks", "precision_lift_vs_same_lagged_state", "avg_forward_return_during_event", "return_lift_vs_same_lagged_state", "event_starts_per_year"]], 24),
        "",
        "## Target Matrix",
        markdown_table(event_matrix, 10, 18),
        "",
        "## Triple-Barrier / Path Outcome Findings",
        markdown_table(tb_summary[["signal_name", "horizon_weeks", "signal_intended_direction", "event_path_count", "event_upper_hit_rate", "event_lower_hit_rate", "event_avg_end_return", "risk_warning_success_rate_lift_vs_same_lagged_state", "risk_on_success_rate_lift_vs_same_lagged_state", "avg_end_return_lift_vs_same_lagged_state"]].sort_values(["signal_name", "horizon_weeks"]), 24),
        "",
        "Path asymmetry:",
        markdown_table(asym.sort_values(["signal_name", "horizon_weeks"]), 24),
        "",
        "## Subperiod / Holdout Stability",
        "Pre-2016 versus 2016-forward holdout diagnostics:",
        markdown_table(holdout.sort_values("holdout_precision_lift_vs_same_lagged_state", ascending=False), 24),
        "",
        "Calendar/state/path stability sample:",
        markdown_table(subperiod[subperiod["period"].isin(["pre_2016", "2016_forward", "2010_2015", "2016_2020", "2021_2026"])].sort_values(["signal_name", "target", "period"]), 24),
        "",
        "## Redundancy / Incrementality Findings",
        markdown_table(incrementality.sort_values("precision_lift_vs_same_lagged_state", ascending=False), 12),
        "",
        "Top state/Layer2B overlaps:",
        markdown_table(layer2b[["signal_name", "comparison_group", "comparison_feature", "corr", "abs_corr", "event_overlap_rate", "jaccard_overlap"]], 20),
        "",
        "Top OOO/QQQ overlaps:",
        markdown_table(ooo_qqq[["signal_name", "comparison_group", "comparison_feature", "corr", "abs_corr", "event_overlap_rate", "jaccard_overlap"]], 20),
        "",
        "GGG1 exposure overlaps:",
        markdown_table(exposure[["signal_name", "comparison_feature", "corr", "abs_corr", "event_overlap_rate", "jaccard_overlap"]], 20),
        "",
        "## Keep / Reject Decisions",
        markdown_table(decisions[["signal_name", "best_target", "decision", "event_count", "precision_lift_vs_same_lagged_state", "holdout_precision_lift_vs_same_lagged_state", "triple_barrier_success_lift_vs_same_lagged_state", "incrementality_flag", "reason"]], 12),
        "",
        "## Next Phase Queue",
        markdown_table(queue[["signal_name", "decision", "best_target", "next_phase_task"]] if not queue.empty else queue, 12),
        "",
        "## Final Recommendation",
        f"**{rec}**",
        "",
        f"Reason: {reason}",
        "",
        "## Is Portfolio Pass-Through Justified?",
        "Portfolio pass-through is justified only if at least one signal is classified `KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH`. SSS2 applies that gate after event, same-state, holdout, triple-barrier/path, redundancy, and turnover checks; the keep/reject table above is the authoritative result.",
        "",
        "## Exact Prompt Outline For Next Phase",
        report_prompt_for_next(rec),
        "",
        "## Resume-Worthy Technical Summary",
        "SSS2 loaded the SSS high-priority and watchlist rule queue, converted six explicit causal lagged sequence signals, and aligned them to the 1,110-week GGG1 state/return panel. It validated event precision against stress-transition, recovery-quality, underperformance, tail-risk, false-recovery, and forward return/path outcomes; ran 4w/8w/13w triple-barrier path checks using lagged 13w GGG1 volatility; tested pre-2016 vs 2016-forward and calendar/state/path stability; checked redundancy against current five-state labels, refined Layer 2B states/probabilities, OOO/QQQ signals, and GGG1 BIL/offense/defense exposure regimes; then classified each signal without creating any portfolio candidate or changing production/shadow/GGG1.",
    ]
    DOC.write_text("\n".join(lines) + "\n")


def update_project_journey(recommendation: pd.DataFrame, decisions: pd.DataFrame) -> None:
    rec = recommendation.iloc[0]["recommendation"]
    reason = recommendation.iloc[0]["reason"]
    decision_counts = decisions["decision"].value_counts().to_dict()
    section = f"""

## Section 91 -- Phase SSS2 Sequence Signal Validation

Date: 2026-04-27. Phase SSS2 was diagnostic-only. It converted the high-priority
SSS sequence rules into explicit lagged binary signals, validated event
precision, same-state incrementality, 4w/8w/13w triple-barrier path outcomes,
pre-2016 versus 2016-forward holdout stability, calendar/state/path stability,
and redundancy versus Layer 2B, OOO/QQQ, and GGG1 exposure regimes. It created no
portfolio candidates and did not change production, shadow, GGG1 logic, or live
trading behavior.

**Signal decisions.** `{decision_counts}`.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 91 -- Phase SSS2 Sequence Signal Validation"
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
    ensure_out()
    inputs = load_inputs()
    definitions = build_signal_definitions(inputs)
    base_panel = build_base_panel(inputs)
    signal_panel = build_signal_panel(base_panel, definitions)
    panel = attach_signals(base_panel, signal_panel)
    write_schema(signal_panel)
    event_summary, _, event_matrix = event_validation(panel)
    _, tb_summary, asym = triple_barrier_validation(panel)
    subperiod, holdout = stability_validation(panel, tb_summary)
    redundancy, incrementality, ooo_qqq, layer2b, exposure = redundancy_incrementality(panel, event_summary)
    decisions, queue, recommendation = keep_reject_decisions(event_summary, tb_summary, holdout, incrementality)
    leakage = pd.read_csv(OUT / "sss2_leakage_checklist.csv")
    sss_queue = inputs["queue"][inputs["queue"]["classification"].isin(PRIMARY_CLASSES | WATCHLIST_CLASSES)].copy()
    write_report(
        definitions,
        signal_panel,
        leakage,
        event_summary,
        event_matrix,
        tb_summary,
        asym,
        subperiod,
        holdout,
        redundancy,
        incrementality,
        ooo_qqq,
        layer2b,
        exposure,
        decisions,
        queue,
        recommendation,
        sss_queue,
    )
    update_project_journey(recommendation, decisions)
    print("Phase SSS2 sequence signal validation complete.")
    print(f"Outputs: {OUT}")
    print(f"Report: {DOC}")
    print(f"Recommendation: {recommendation.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
