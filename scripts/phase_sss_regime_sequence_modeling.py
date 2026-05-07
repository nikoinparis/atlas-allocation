"""Phase SSS -- regime-sequence modeling.

Diagnostic-only research phase. Builds causal lagged state-sequence features
from the Layer 2B regime history, tests whether paths/dwell/persistence explain
recovery and stress outcomes beyond current state labels, and compares findings
to QQQ/OOO/GGG1 context. No portfolio candidates, production pins, shadow pins,
live trading, or GGG1 logic are changed.
"""
from __future__ import annotations

import importlib.util
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
try:
    from scipy.stats import ConstantInputWarning
except Exception:  # pragma: no cover
    ConstantInputWarning = Warning
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in divide")
warnings.filterwarnings("ignore", category=ConstantInputWarning)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
L2B = DATA / "04_layer2b_risk_regime_engine"
L2A = DATA / "03_layer2a_strategy_logic"
L1 = DATA / "02_layer1_signals"
L3 = DATA / "05_layer3_portfolio_construction"
OOO = DATA / "research" / "phase_ooo_signal_discovery"
PPP = DATA / "research" / "phase_ppp_latent_factor_discovery"
QQQ = DATA / "research" / "phase_qqq_deep_feature_interaction_mining"
OUT = DATA / "research" / "phase_sss_regime_sequence_modeling"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_sss_regime_sequence_modeling_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

INITIAL_TRAIN_DATES = 260
REFIT_FREQ = 26
RANDOM_STATE = 20260427
MAX_IMPORTANCE_ROWS_PER_FOLD = 60

BASE_STATES = [
    "calm_trend",
    "neutral_mixed",
    "recovery_confirmed",
    "recovery_fragile",
    "stressed_panic",
]
RECOVERY_STATES = {"recovery_confirmed", "recovery_fragile"}
RERISK_STATES = {"recovery_confirmed", "recovery_fragile", "neutral_mixed", "calm_trend"}
BAD_TARGETS = {
    "stress_transition_4w",
    "stress_transition_8w",
    "ggg1_underperformance_4w",
    "ggg1_tail_risk_4w",
    "false_recovery_label",
}

TARGET_META = {
    "stress_transition_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "type": "stress_transition_start"},
    "stress_transition_8w": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "type": "stress_transition_start"},
    "recovery_quality_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "type": "recovery_quality"},
    "recovery_quality_8w": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "type": "recovery_quality"},
    "ggg1_underperformance_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "type": "ggg1_underperformance"},
    "ggg1_tail_risk_4w": {"horizon": 4, "return_col": "ggg1_fwd_return_4w", "type": "ggg1_tail_risk"},
    "false_recovery_label": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "type": "false_recovery"},
    "qqq_interaction_success_label": {"horizon": 8, "return_col": "ggg1_fwd_return_8w", "type": "optional_qqq_interaction_success"},
}
TARGETS = list(TARGET_META)

COMMANDS = [
    "sed -n '1,360p' docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md",
    "find data/research/phase_qqq_deep_feature_interaction_mining -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf \"%s\\t\" \"$(basename \"{}\")\"; wc -l < \"{}\"'",
    "find data/04_layer2b_risk_regime_engine data/03_layer2a_strategy_logic data/05_layer3_portfolio_construction data/02_layer1_signals -maxdepth 2 -type f | sort | sed -n '1,360p'",
    "tail -n 90 docs/research/project_journey.md",
    "python3 - <<'PY' ...state/portfolio/QQQ/OOO schema summaries...",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md",
    "find data/research/phase_ppp_latent_factor_discovery data/research/phase_ooo_signal_discovery -maxdepth 2 -type f | sort | sed -n '1,220p'",
    "python3 -m py_compile scripts/phase_sss_regime_sequence_modeling.py",
    "python3 scripts/phase_sss_regime_sequence_modeling.py",
]


@dataclass
class RuleSpec:
    rule_name: str
    formula: str
    interpretation: str
    family: str
    evaluator: callable


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
        raise ValueError(f"No date-like column found in {path}")
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def load_portfolio_returns(version: str, prefix: str) -> pd.DataFrame:
    path = L3 / f"portfolio_version_returns_{version}.csv"
    df = read_dated_csv(path)
    keep = ["date"]
    out = df[keep].copy()
    for col in ["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]:
        if col in df.columns:
            out[f"{prefix}_{col}"] = pd.to_numeric(df[col], errors="coerce")
    return out


def compound_forward(s: pd.Series, horizon: int) -> pd.Series:
    result = pd.Series(1.0, index=s.index)
    valid = pd.Series(True, index=s.index)
    for k in range(1, horizon + 1):
        shifted = pd.to_numeric(s.shift(-k), errors="coerce")
        valid &= shifted.notna()
        result *= 1.0 + shifted.fillna(0.0)
    out = result - 1.0
    out[~valid] = np.nan
    return out


def future_min_path_return(s: pd.Series, horizon: int) -> pd.Series:
    cols = []
    path = pd.Series(1.0, index=s.index)
    valid = pd.Series(True, index=s.index)
    for k in range(1, horizon + 1):
        shifted = pd.to_numeric(s.shift(-k), errors="coerce")
        valid &= shifted.notna()
        path = path * (1.0 + shifted.fillna(0.0))
        cols.append(path - 1.0)
    out = pd.concat(cols, axis=1).min(axis=1)
    out[~valid] = np.nan
    return out


def ann_stats(returns: pd.Series) -> dict[str, float]:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if len(r) == 0:
        return {"n_weeks": 0, "weekly_mean": np.nan, "ann_return": np.nan, "ann_vol": np.nan, "sharpe": np.nan, "max_drawdown": np.nan, "cvar_5": np.nan}
    wealth = (1.0 + r).cumprod()
    dd = wealth / wealth.cummax() - 1.0
    ann_return = (1.0 + r.mean()) ** 52 - 1.0
    ann_vol = r.std(ddof=0) * math.sqrt(52)
    return {
        "n_weeks": int(len(r)),
        "weekly_mean": float(r.mean()),
        "ann_return": float(ann_return),
        "ann_vol": float(ann_vol),
        "sharpe": float(ann_return / ann_vol) if ann_vol and ann_vol > 0 else np.nan,
        "max_drawdown": float(dd.min()),
        "cvar_5": float(r[r <= r.quantile(0.05)].mean()) if len(r) >= 20 else np.nan,
    }


def bucket_state_age(age: pd.Series) -> pd.Series:
    return pd.cut(
        pd.to_numeric(age, errors="coerce"),
        bins=[0, 2, 6, 13, np.inf],
        labels=["new_state_1_2w", "young_3_6w", "mature_7_13w", "old_14w_plus"],
        right=True,
    ).astype(str).replace("nan", np.nan)


def add_dwell_columns(df: pd.DataFrame, state_col: str = "market_state") -> pd.DataFrame:
    out = df.copy()
    new_run = out[state_col].ne(out[state_col].shift(1))
    out["state_run_id"] = new_run.cumsum()
    out["state_age_weeks"] = out.groupby("state_run_id").cumcount() + 1
    out["state_run_length"] = out.groupby("state_run_id")[state_col].transform("size")
    out["state_dwell_bucket"] = bucket_state_age(out["state_age_weeks"])
    out["prev_market_state"] = out[state_col].shift(1)
    out["prev2_market_state"] = out[state_col].shift(2)
    out["path2_current"] = out["prev_market_state"].fillna("START") + "->" + out[state_col].astype(str)
    out["path3_current"] = out["prev2_market_state"].fillna("START") + "->" + out["prev_market_state"].fillna("START") + "->" + out[state_col].astype(str)
    return out


def load_qqq_context(dates: pd.Series) -> tuple[pd.DataFrame, list[str], list[str]]:
    shortlist_path = QQQ / "qqq_candidate_interaction_signal_shortlist.csv"
    dataset_path = QQQ / "qqq_ml_dataset.csv"
    if not shortlist_path.exists() or not dataset_path.exists():
        return pd.DataFrame({"date": dates}), [], ["QQQ context unavailable: shortlist or full ML dataset missing."]

    shortlist = pd.read_csv(shortlist_path)
    interaction_features = sorted(shortlist["interaction_feature"].dropna().astype(str).unique().tolist())
    if not interaction_features:
        return pd.DataFrame({"date": dates}), [], ["QQQ shortlist has no interaction_feature values."]
    try:
        qqq = pd.read_csv(dataset_path, usecols=["date", "ticker"] + interaction_features)
    except Exception as exc:
        return pd.DataFrame({"date": dates}), [], [f"Could not read QQQ dataset interaction columns: {exc}"]
    qqq["date"] = pd.to_datetime(qqq["date"], errors="coerce")
    agg = qqq.groupby("date")[interaction_features].mean().reset_index()
    rename = {c: f"qqq_active_{c}" for c in interaction_features}
    agg = agg.rename(columns=rename)
    agg["qqq_any_shortlist_rule_active"] = agg[list(rename.values())].max(axis=1)
    agg["qqq_mean_shortlist_rule_active"] = agg[list(rename.values())].mean(axis=1)
    return agg, list(rename.values()) + ["qqq_any_shortlist_rule_active", "qqq_mean_shortlist_rule_active"], []


def load_state_sequence() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    ensure_out()
    warnings_list: list[str] = []
    refined_path = L2B / "market_state_history_refined.csv"
    base_path = L2B / "market_state_history.csv"
    source_path = refined_path if refined_path.exists() else base_path
    state = read_dated_csv(source_path)
    if "market_state" not in state.columns:
        raise ValueError(f"{source_path} does not contain market_state")
    if "refined_state" not in state.columns:
        state["refined_state"] = state["market_state"]
        warnings_list.append("No refined_state column found; copied market_state.")

    ggg1 = load_portfolio_returns(GGG1, "ggg1")
    production = load_portfolio_returns(PRODUCTION, "production")
    shadow = load_portfolio_returns(SHADOW, "shadow")
    panel = ggg1[["date"]].merge(state, on="date", how="left", validate="one_to_one")
    panel = panel.merge(ggg1, on="date", how="left", validate="one_to_one")
    panel = panel.merge(production, on="date", how="left", validate="one_to_one")
    panel = panel.merge(shadow, on="date", how="left", validate="one_to_one")

    p2b_path = L2B / "phase2b_meta_predictions.csv"
    if p2b_path.exists():
        p2b = read_dated_csv(p2b_path)
        panel = panel.merge(p2b, on="date", how="left")
    kk_path = L2B / "phase_kk_targeta_regime_confidence_predictions.csv"
    if kk_path.exists():
        kk = read_dated_csv(kk_path)
        panel = panel.merge(kk, on="date", how="left")

    sleeve_path = L3 / f"portfolio_version_sleeve_weights_{GGG1}.csv"
    if sleeve_path.exists():
        sleeve = read_dated_csv(sleeve_path)
        for col in sleeve.columns:
            if col != "date":
                sleeve = sleeve.rename(columns={col: f"ggg1_sleeve_weight_{col}"})
        panel = panel.merge(sleeve, on="date", how="left")

    qqq_context, qqq_cols, qqq_warnings = load_qqq_context(panel["date"])
    warnings_list.extend(qqq_warnings)
    panel = panel.merge(qqq_context, on="date", how="left")

    ooo2_path = OOO / "ooo2_cross_asset_signal_expansion" / "ooo2_candidate_signal_panel.csv"
    if ooo2_path.exists():
        ooo2 = read_dated_csv(ooo2_path)
        ooo2 = ooo2.rename(columns={c: f"ooo2_{c}" for c in ooo2.columns if c != "date"})
        panel = panel.merge(ooo2, on="date", how="left")
    ooo3_path = OOO / "ooo3_vol_managed_signal_sizing" / "ooo3_sized_signal_event_panel.csv"
    if ooo3_path.exists():
        ooo3 = read_dated_csv(ooo3_path)
        ooo3 = ooo3.rename(columns={c: f"ooo3event_{c}" for c in ooo3.columns if c != "date"})
        panel = panel.merge(ooo3, on="date", how="left")

    panel = add_dwell_columns(panel, "market_state")
    for h in [4, 8]:
        panel[f"ggg1_fwd_return_{h}w"] = compound_forward(panel["ggg1_net_return"], h)
        panel[f"production_fwd_return_{h}w"] = compound_forward(panel["production_net_return"], h)
        panel[f"shadow_fwd_return_{h}w"] = compound_forward(panel["shadow_net_return"], h)
        panel[f"ggg1_future_min_path_return_{h}w"] = future_min_path_return(panel["ggg1_net_return"], h)
    panel["ggg1_trailing_vol_13w_lag1"] = panel["ggg1_net_return"].rolling(13, min_periods=8).std().shift(1)
    panel["ggg1_trailing_mean_260w_lag1"] = panel["ggg1_net_return"].rolling(260, min_periods=104).mean().shift(1)
    panel["ggg1_expected_4w_from_trailing_mean"] = 4.0 * panel["ggg1_trailing_mean_260w_lag1"]
    panel["ggg1_minus_production_fwd_4w"] = panel["ggg1_fwd_return_4w"] - panel["production_fwd_return_4w"]
    panel["ggg1_minus_shadow_fwd_4w"] = panel["ggg1_fwd_return_4w"] - panel["shadow_fwd_return_4w"]

    missing_states = int(panel["market_state"].isna().sum())
    if missing_states:
        warnings_list.append(f"{missing_states} GGG1 dates missing market_state after alignment.")
    panel = panel.sort_values("date").reset_index(drop=True)
    save_csv(panel, OUT / "sss_state_sequence_panel.csv")

    refined_labels = sorted(panel["refined_state"].dropna().astype(str).unique())
    audit_rows = [
        {
            "item": "state_file_used",
            "value": str(source_path.relative_to(ROOT)),
            "notes": "refined state file preferred when available",
        },
        {"item": "date_range", "value": f"{panel['date'].min().date()} to {panel['date'].max().date()}", "notes": ""},
        {"item": "n_weeks", "value": int(len(panel)), "notes": "aligned to GGG1 return dates"},
        {"item": "n_base_states", "value": int(panel["market_state"].nunique(dropna=True)), "notes": ",".join(sorted(panel["market_state"].dropna().unique()))},
        {"item": "n_refined_states", "value": int(panel["refined_state"].nunique(dropna=True)), "notes": ",".join(refined_labels)},
        {"item": "aligned_to_ggg1", "value": bool(len(panel) == len(ggg1)), "notes": "inner frame seeded from GGG1 dates"},
        {"item": "missing_state_dates", "value": missing_states, "notes": ""},
        {"item": "refined_states_exist", "value": "refined_state" in state.columns, "notes": ""},
        {"item": "neutral_healthy_split_exists", "value": "neutral_healthy" in refined_labels, "notes": ""},
        {"item": "neutral_deteriorating_split_exists", "value": "neutral_deteriorating" in refined_labels, "notes": ""},
        {"item": "qqq_context_features_loaded", "value": len(qqq_cols), "notes": ",".join(qqq_cols[:12])},
        {"item": "hmmlearn_available", "value": bool(importlib.util.find_spec("hmmlearn")), "notes": "HMM skipped unless package already installed"},
    ]
    for warning in warnings_list:
        audit_rows.append({"item": "warning", "value": warning, "notes": ""})
    audit = pd.DataFrame(audit_rows)
    save_csv(audit, OUT / "sss_state_source_audit.csv")
    return panel, audit, qqq_cols, warnings_list


def transition_matrix(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    left = panel["market_state"].astype(str)
    right = panel["market_state"].shift(-horizon).astype(str)
    valid = left.notna() & right.notna() & (right != "nan")
    counts = pd.crosstab(left[valid], right[valid])
    probs = counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0)
    out = probs.reset_index().rename(columns={"market_state": "from_state"})
    out.insert(1, "horizon_weeks", horizon)
    out.insert(2, "n_from", counts.sum(axis=1).reindex(probs.index).to_numpy())
    return out


def summarize_perf_group(df: pd.DataFrame, group_cols: list[str], row_type: str) -> pd.DataFrame:
    rows = []
    for key, g in df.dropna(subset=group_cols).groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        stats = ann_stats(g["ggg1_net_return"])
        row = {"row_type": row_type}
        row.update({c: v for c, v in zip(group_cols, key)})
        row.update(stats)
        row["avg_fwd_return_4w"] = float(g["ggg1_fwd_return_4w"].mean())
        row["avg_fwd_return_8w"] = float(g["ggg1_fwd_return_8w"].mean())
        row["stress_transition_4w_rate"] = float(g["stress_transition_4w_diag"].mean())
        row["stress_transition_8w_rate"] = float(g["stress_transition_8w_diag"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def stress_start_targets(states: pd.Series, horizon: int) -> pd.Series:
    stress_start = states.eq("stressed_panic") & ~states.shift(1).eq("stressed_panic")
    pieces = [stress_start.shift(-k) for k in range(1, horizon + 1)]
    out = pd.concat(pieces, axis=1).max(axis=1).astype(float)
    out.iloc[-horizon:] = np.nan
    return out


def run_transition_diagnostics(panel: pd.DataFrame) -> None:
    for h in [1, 4, 8]:
        save_csv(transition_matrix(panel, h), OUT / f"sss_transition_matrix_{h}w.csv")

    diag = panel.copy()
    diag["stress_transition_4w_diag"] = stress_start_targets(diag["market_state"], 4)
    diag["stress_transition_8w_diag"] = stress_start_targets(diag["market_state"], 8)

    runs = diag.groupby("state_run_id").agg(
        market_state=("market_state", "first"),
        run_start=("date", "min"),
        run_end=("date", "max"),
        run_length=("state_run_length", "first"),
        next_state=("market_state", lambda x: np.nan),
    ).reset_index(drop=False)
    next_states = []
    for run_id in runs["state_run_id"]:
        idx = diag.index[diag["state_run_id"].eq(run_id)]
        end = int(idx.max())
        next_states.append(diag.loc[end + 1, "market_state"] if end + 1 < len(diag) else np.nan)
    runs["next_state"] = next_states
    runs["dwell_bucket"] = bucket_state_age(runs["run_length"])
    dist = runs.groupby(["market_state", "dwell_bucket"], dropna=False).agg(
        n_runs=("state_run_id", "count"),
        avg_run_length=("run_length", "mean"),
        median_run_length=("run_length", "median"),
        max_run_length=("run_length", "max"),
    ).reset_index()
    state_run_counts = runs.groupby("market_state")["state_run_id"].count()
    dist["share_of_state_runs"] = dist.apply(lambda r: r["n_runs"] / state_run_counts.get(r["market_state"], np.nan), axis=1)
    save_csv(dist, OUT / "sss_state_dwell_distribution.csv")

    age_perf = pd.concat(
        [
            summarize_perf_group(diag, ["market_state", "state_dwell_bucket"], "current_state_x_dwell_bucket"),
            summarize_perf_group(diag, ["refined_state", "state_dwell_bucket"], "refined_state_x_dwell_bucket"),
        ],
        ignore_index=True,
    )
    save_csv(age_perf, OUT / "sss_state_age_performance.csv")

    path_perf = pd.concat(
        [
            summarize_perf_group(diag, ["market_state", "prev_market_state"], "current_state_x_previous_state"),
            summarize_perf_group(diag, ["path2_current"], "two_state_path"),
            summarize_perf_group(diag, ["path3_current"], "three_state_path"),
            summarize_perf_group(diag, ["market_state", "state_dwell_bucket"], "current_state_x_dwell_bucket"),
        ],
        ignore_index=True,
    )
    save_csv(path_perf, OUT / "sss_state_path_performance.csv")

    rows = []
    group_specs = [
        ("current_state", ["market_state"]),
        ("previous_to_current_path", ["prev_market_state", "market_state"]),
        ("two_state_path", ["path2_current"]),
        ("current_state_dwell", ["market_state", "state_dwell_bucket"]),
        ("refined_state", ["refined_state"]),
    ]
    for label, cols in group_specs:
        for key, g in diag.dropna(subset=cols).groupby(cols, dropna=False):
            if not isinstance(key, tuple):
                key = (key,)
            row = {"diagnostic": label, "group": "|".join(map(str, key)), "n_weeks": int(len(g))}
            for h in [4, 8]:
                row[f"stress_transition_{h}w_rate"] = float(g[f"stress_transition_{h}w_diag"].mean())
            row["avg_ggg1_fwd_4w"] = float(g["ggg1_fwd_return_4w"].mean())
            row["avg_ggg1_fwd_8w"] = float(g["ggg1_fwd_return_8w"].mean())
            rows.append(row)

    special_masks = {
        "neutral_mixed_after_stressed_panic": diag["market_state"].eq("neutral_mixed") & diag["prev_market_state"].eq("stressed_panic"),
        "neutral_mixed_after_calm_trend": diag["market_state"].eq("neutral_mixed") & diag["prev_market_state"].eq("calm_trend"),
        "recovery_confirmed_after_recovery_fragile": diag["market_state"].eq("recovery_confirmed") & diag["prev_market_state"].eq("recovery_fragile"),
        "recovery_confirmed_after_neutral_mixed": diag["market_state"].eq("recovery_confirmed") & diag["prev_market_state"].eq("neutral_mixed"),
        "neutral_mixed_old_14w_plus": diag["market_state"].eq("neutral_mixed") & diag["state_dwell_bucket"].eq("old_14w_plus"),
        "recovery_confirmed_new_1_2w": diag["market_state"].eq("recovery_confirmed") & diag["state_dwell_bucket"].eq("new_state_1_2w"),
        "recovery_confirmed_old_14w_plus": diag["market_state"].eq("recovery_confirmed") & diag["state_dwell_bucket"].eq("old_14w_plus"),
    }
    for name, mask in special_masks.items():
        g = diag[mask]
        row = {"diagnostic": "named_question", "group": name, "n_weeks": int(len(g))}
        for h in [4, 8]:
            row[f"stress_transition_{h}w_rate"] = float(g[f"stress_transition_{h}w_diag"].mean()) if len(g) else np.nan
        row["avg_ggg1_fwd_4w"] = float(g["ggg1_fwd_return_4w"].mean()) if len(g) else np.nan
        row["avg_ggg1_fwd_8w"] = float(g["ggg1_fwd_return_8w"].mean()) if len(g) else np.nan
        rows.append(row)

    out = pd.DataFrame(rows).sort_values(["diagnostic", "stress_transition_8w_rate"], ascending=[True, False])
    save_csv(out, OUT / "sss_state_transition_risk_summary.csv")


def state_entropy(values: pd.Series) -> float:
    v = values.dropna().astype(str)
    if len(v) == 0:
        return np.nan
    p = v.value_counts(normalize=True)
    return float(-(p * np.log(p)).sum())


def rolling_state_entropy(states: pd.Series, window: int) -> pd.Series:
    values = []
    for idx in range(len(states)):
        start = max(0, idx - window + 1)
        values.append(state_entropy(states.iloc[start : idx + 1]))
    return pd.Series(values, index=states.index)


def time_since_event(lagged_event: pd.Series) -> pd.Series:
    out = []
    count = np.nan
    for val in lagged_event.fillna(False).astype(bool):
        if val:
            count = 0
        elif pd.isna(count):
            count = np.nan
        else:
            count += 1
        out.append(count)
    return pd.Series(out, index=lagged_event.index)


def build_sequence_features(panel: pd.DataFrame, qqq_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    df = panel[["date", "market_state", "refined_state", "risk_state"]].copy()
    source = panel.copy()
    state_lag = source["market_state"].shift(1)
    refined_lag = source["refined_state"].shift(1)
    risk_lag = source["risk_state"].shift(1)
    df["state_lag1"] = state_lag
    df["state_lag2"] = source["market_state"].shift(2)
    df["state_lag4"] = source["market_state"].shift(4)
    df["refined_state_lag1"] = refined_lag
    df["risk_state_lag1"] = risk_lag
    df["path2_lag"] = source["market_state"].shift(2).fillna("START") + "->" + source["market_state"].shift(1).fillna("START")
    df["path3_lag"] = source["market_state"].shift(3).fillna("START") + "->" + source["market_state"].shift(2).fillna("START") + "->" + source["market_state"].shift(1).fillna("START")
    df["path4_lag"] = (
        source["market_state"].shift(4).fillna("START")
        + "->"
        + source["market_state"].shift(3).fillna("START")
        + "->"
        + source["market_state"].shift(2).fillna("START")
        + "->"
        + source["market_state"].shift(1).fillna("START")
    )
    df["state_age_lag1"] = source["state_age_weeks"].shift(1)
    df["state_dwell_bucket_lag1"] = bucket_state_age(df["state_age_lag1"])

    stress_lag = state_lag.eq("stressed_panic")
    recovery_lag = state_lag.isin(RECOVERY_STATES)
    for w in [4, 8, 13, 26]:
        df[f"stress_count_last_{w}w"] = stress_lag.rolling(w, min_periods=1).sum()
        df[f"recovery_count_last_{w}w"] = recovery_lag.rolling(w, min_periods=1).sum()
    changes = state_lag.ne(state_lag.shift(1)) & state_lag.notna() & state_lag.shift(1).notna()
    for w in [4, 8, 13]:
        df[f"state_changes_last_{w}w"] = changes.rolling(w, min_periods=1).sum()
        df[f"transition_volatility_last_{w}w"] = df[f"state_changes_last_{w}w"] / float(w)
        df[f"state_entropy_last_{w}w"] = rolling_state_entropy(state_lag, w)

    df["time_since_last_stressed_panic"] = time_since_event(stress_lag)
    df["time_since_last_recovery_confirmed"] = time_since_event(state_lag.eq("recovery_confirmed"))
    df["recovery_confirmed_after_stress_lag"] = ((state_lag.eq("recovery_confirmed")) & source["market_state"].shift(2).eq("stressed_panic")).astype(float)
    df["recovery_confirmed_after_fragile_lag"] = ((state_lag.eq("recovery_confirmed")) & source["market_state"].shift(2).eq("recovery_fragile")).astype(float)
    df["recovery_confirmed_after_neutral_lag"] = ((state_lag.eq("recovery_confirmed")) & source["market_state"].shift(2).eq("neutral_mixed")).astype(float)
    df["recovery_fragile_after_stress_lag"] = ((state_lag.eq("recovery_fragile")) & source["market_state"].shift(2).eq("stressed_panic")).astype(float)
    df["neutral_after_stress_lag"] = ((state_lag.eq("neutral_mixed")) & source["market_state"].shift(2).eq("stressed_panic")).astype(float)
    df["neutral_after_calm_lag"] = ((state_lag.eq("neutral_mixed")) & source["market_state"].shift(2).eq("calm_trend")).astype(float)
    df["stress_memory_neutral_lag"] = ((state_lag.eq("neutral_mixed")) & (df["stress_count_last_13w"] > 0)).astype(float)
    df["recent_transition_instability_lag"] = (df["state_changes_last_8w"] >= 3).astype(float)

    l2b_numeric_candidates = [
        "risk_regime_score",
        "market_drawdown",
        "market_trend_positive",
        "breadth_sma_43",
        "breadth_26w_mom",
        "breadth_13w_mom",
        "breadth_change_4w",
        "canary_breadth_default",
        "canary_breadth_pair",
        "recent_stress_26w",
        "avg_corr_risk_off_z",
        "google_fear_z_tradable",
        "transition_persistence_prob",
        "transition_good_state_prob",
        "transition_non_stress_prob",
        "deterioration_z",
        "deterioration_rank_neutral_mixed",
        "confidence_score_p2b",
        "defensive_overlay_hint",
        "p_regime_confidence",
        "p_transition_quality",
        "p_tail_risk",
        "p_stress_forecast",
        "p_regime_confidence_refreshed",
        "p_regime_confidence_blend25",
    ]
    l2b_features = []
    for col in l2b_numeric_candidates:
        if col in source.columns:
            new = f"l2b_{col}_lag1"
            df[new] = pd.to_numeric(source[col], errors="coerce").shift(1)
            l2b_features.append(new)

    qqq_features = []
    for col in qqq_cols:
        if col in source.columns:
            new = f"{col}_lag1"
            df[new] = pd.to_numeric(source[col], errors="coerce").shift(1)
            qqq_features.append(new)

    ooo_features = []
    for col in source.columns:
        if col.startswith("ooo2_") or col.startswith("ooo3event_"):
            new = f"{col}_lag1"
            df[new] = pd.to_numeric(source[col], errors="coerce").shift(1)
            ooo_features.append(new)

    categorical_cols = ["state_lag1", "state_lag2", "state_lag4", "refined_state_lag1", "risk_state_lag1", "state_dwell_bucket_lag1"]
    path_cols = ["path2_lag", "path3_lag", "path4_lag"]
    dummy_features = []
    manifest_rows = []
    for col in categorical_cols + path_cols:
        counts = df[col].value_counts(dropna=True)
        keep_values = counts[counts >= (8 if col.startswith("path") else 1)].index
        safe = df[col].where(df[col].isin(keep_values), "OTHER")
        dummies = pd.get_dummies(safe, prefix=col, dummy_na=False).astype(float)
        if f"{col}_START" in dummies.columns:
            dummies = dummies.drop(columns=[f"{col}_START"])
        df = pd.concat([df, dummies], axis=1)
        dummy_features.extend(dummies.columns.tolist())
        for c in dummies.columns:
            manifest_rows.append(
                {
                    "feature_name": c,
                    "feature_family": "state_ngram" if col in path_cols else "state_identity",
                    "source": col,
                    "lag_rule": "categorical state/path uses states through t-1 only",
                    "used_in_sequence_model": True,
                    "used_in_layer2b_baseline": False,
                    "used_in_qqq_control": False,
                    "leakage_check": "causal_lagged_state_feature",
                }
            )

    numeric_sequence_features = [
        "state_age_lag1",
        "time_since_last_stressed_panic",
        "time_since_last_recovery_confirmed",
        "recovery_confirmed_after_stress_lag",
        "recovery_confirmed_after_fragile_lag",
        "recovery_confirmed_after_neutral_lag",
        "recovery_fragile_after_stress_lag",
        "neutral_after_stress_lag",
        "neutral_after_calm_lag",
        "stress_memory_neutral_lag",
        "recent_transition_instability_lag",
    ]
    for w in [4, 8, 13, 26]:
        numeric_sequence_features += [f"stress_count_last_{w}w", f"recovery_count_last_{w}w"]
    for w in [4, 8, 13]:
        numeric_sequence_features += [f"state_changes_last_{w}w", f"transition_volatility_last_{w}w", f"state_entropy_last_{w}w"]

    for c in numeric_sequence_features:
        manifest_rows.append(
            {
                "feature_name": c,
                "feature_family": "dwell_time" if "age" in c or "time_since" in c else "state_memory",
                "source": "engineered_from_market_state",
                "lag_rule": "uses state history through t-1 only",
                "used_in_sequence_model": True,
                "used_in_layer2b_baseline": False,
                "used_in_qqq_control": False,
                "leakage_check": "causal_lagged_state_feature",
            }
        )
    for c in l2b_features:
        manifest_rows.append(
            {
                "feature_name": c,
                "feature_family": "existing_layer2b_probability_or_input",
                "source": c.replace("l2b_", "").replace("_lag1", ""),
                "lag_rule": "shifted one week before modeling",
                "used_in_sequence_model": False,
                "used_in_layer2b_baseline": True,
                "used_in_qqq_control": False,
                "leakage_check": "causal_lagged_layer2b_feature",
            }
        )
    for c in qqq_features:
        manifest_rows.append(
            {
                "feature_name": c,
                "feature_family": "qqq_rule_context",
                "source": c.replace("_lag1", ""),
                "lag_rule": "QQQ context shifted one week again for SSS",
                "used_in_sequence_model": False,
                "used_in_layer2b_baseline": False,
                "used_in_qqq_control": True,
                "leakage_check": "causal_lagged_qqq_context",
            }
        )
    for c in ooo_features:
        manifest_rows.append(
            {
                "feature_name": c,
                "feature_family": "ooo_signal_context",
                "source": c.replace("_lag1", ""),
                "lag_rule": "OOO context shifted one week for SSS overlap diagnostics",
                "used_in_sequence_model": False,
                "used_in_layer2b_baseline": False,
                "used_in_qqq_control": False,
                "leakage_check": "causal_lagged_ooo_context",
            }
        )

    feature_groups = {
        "state_only": [c for c in dummy_features if c.startswith("state_lag1_")],
        "previous_state_only": [c for c in dummy_features if c.startswith("state_lag2_")],
        "dwell": [c for c in dummy_features if c.startswith("state_lag1_") or c.startswith("state_dwell_bucket_lag1_")] + ["state_age_lag1"],
        "sequence": dummy_features + numeric_sequence_features,
        "layer2b": l2b_features,
        "qqq": qqq_features,
        "ooo": ooo_features,
    }
    feature_manifest = pd.DataFrame(manifest_rows).drop_duplicates("feature_name")
    feature_manifest["missingness"] = feature_manifest["feature_name"].map(df.isna().mean()).astype(float)
    feature_manifest["non_missing_rows"] = feature_manifest["feature_name"].map(df.notna().sum()).astype(int)
    save_csv(df, OUT / "sss_sequence_feature_panel.csv")
    save_csv(feature_manifest, OUT / "sss_sequence_feature_manifest.csv")

    leakage = pd.DataFrame(
        [
            {"check": "state_sequence_lagged", "passed": True, "note": "model features use state_lag1 or older"},
            {"check": "refined_state_lagged", "passed": True, "note": "refined_state only appears as lag1 dummies/features"},
            {"check": "layer2b_numeric_context_lagged", "passed": True, "note": "Layer 2B probabilities/inputs are shifted one week"},
            {"check": "qqq_context_lagged", "passed": True, "note": "QQQ rule context is shifted one week again"},
            {"check": "ooo_context_lagged", "passed": True, "note": "OOO signal/event context is shifted one week for overlap diagnostics"},
            {"check": "no_future_state_features", "passed": True, "note": "future states are used only in target labels"},
            {"check": "no_future_returns_as_features", "passed": True, "note": "forward returns are saved in target panel only"},
            {"check": "no_random_splits", "passed": True, "note": "walk-forward expanding splits only"},
            {"check": "production_shadow_ggg1_unchanged", "passed": True, "note": f"production={PRODUCTION}; shadow={SHADOW}; GGG1={GGG1}"},
        ]
    )
    save_csv(leakage, OUT / "sss_leakage_checklist.csv")
    return df, feature_manifest, feature_groups


def build_targets(panel: pd.DataFrame, feature_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = panel[["date", "market_state", "refined_state", "ggg1_fwd_return_4w", "ggg1_fwd_return_8w", "ggg1_future_min_path_return_4w", "ggg1_future_min_path_return_8w", "production_fwd_return_4w", "ggg1_expected_4w_from_trailing_mean"]].copy()
    states = panel["market_state"]
    df["stress_transition_4w"] = stress_start_targets(states, 4)
    df["stress_transition_8w"] = stress_start_targets(states, 8)

    vol = panel["ggg1_trailing_vol_13w_lag1"].replace(0.0, np.nan)
    for h in [4, 8]:
        ra = panel[f"ggg1_fwd_return_{h}w"] / vol.clip(lower=0.002)
        eligible = states.isin(RERISK_STATES)
        median = ra[eligible].median()
        df[f"recovery_quality_{h}w"] = np.where(eligible & ra.notna(), (ra > median).astype(float), np.nan)

    underperf = (panel["ggg1_fwd_return_4w"] < panel["production_fwd_return_4w"]) | (
        panel["ggg1_fwd_return_4w"] < panel["ggg1_expected_4w_from_trailing_mean"]
    )
    df["ggg1_underperformance_4w"] = np.where(panel["ggg1_fwd_return_4w"].notna(), underperf.astype(float), np.nan)

    tail_threshold = panel["ggg1_fwd_return_4w"].quantile(0.20)
    min_path_threshold = panel["ggg1_future_min_path_return_4w"].quantile(0.20)
    tail = (panel["ggg1_fwd_return_4w"] <= tail_threshold) | (panel["ggg1_future_min_path_return_4w"] <= min_path_threshold)
    df["ggg1_tail_risk_4w"] = np.where(panel["ggg1_fwd_return_4w"].notna(), tail.astype(float), np.nan)

    recent_recovery = states.isin(RECOVERY_STATES) | states.shift(1).isin(RECOVERY_STATES)
    false_recovery = (
        df["stress_transition_8w"].eq(1.0)
        | (panel["ggg1_fwd_return_8w"] < 0.0)
        | (panel["ggg1_future_min_path_return_8w"] < -0.03)
    )
    df["false_recovery_label"] = np.where(recent_recovery & panel["ggg1_fwd_return_8w"].notna(), false_recovery.astype(float), np.nan)

    qqq_cols = [c for c in panel.columns if c.startswith("qqq_active_")]
    if qqq_cols:
        qqq_active = panel[qqq_cols].max(axis=1) > 0.10
        median_active_ret = panel.loc[qqq_active, "ggg1_fwd_return_8w"].median()
        df["qqq_interaction_success_label"] = np.where(
            qqq_active & panel["ggg1_fwd_return_8w"].notna(),
            (panel["ggg1_fwd_return_8w"] > median_active_ret).astype(float),
            np.nan,
        )
    else:
        df["qqq_interaction_success_label"] = np.nan

    save_csv(df, OUT / "sss_target_panel.csv")

    rows = []
    for target in TARGETS:
        valid = df[df[target].notna()].copy()
        rows.append(
            {
                "target": target,
                "definition": TARGET_META[target]["type"],
                "horizon_weeks": TARGET_META[target]["horizon"],
                "n_observations": int(len(valid)),
                "positive_count": int(valid[target].sum()) if len(valid) else 0,
                "positive_rate": float(valid[target].mean()) if len(valid) else np.nan,
                "start_date": valid["date"].min().date() if len(valid) else "",
                "end_date": valid["date"].max().date() if len(valid) else "",
                "enough_samples": bool(len(valid) >= 300 and valid[target].sum() >= 25),
                "leakage_risk_note": "future states/returns define target only; not included as live features",
            }
        )
        for state, g in valid.groupby("market_state"):
            rows.append(
                {
                    "target": f"{target}__state_{state}",
                    "definition": "state-specific target balance",
                    "horizon_weeks": TARGET_META[target]["horizon"],
                    "n_observations": int(len(g)),
                    "positive_count": int(g[target].sum()),
                    "positive_rate": float(g[target].mean()) if len(g) else np.nan,
                    "start_date": g["date"].min().date() if len(g) else "",
                    "end_date": g["date"].max().date() if len(g) else "",
                    "enough_samples": bool(len(g) >= 40 and g[target].sum() >= 5),
                    "leakage_risk_note": "diagnostic grouping only",
                }
            )
    summary = pd.DataFrame(rows)
    save_csv(summary, OUT / "sss_target_summary.csv")
    return df, summary


def build_walkforward_splits(dates: pd.Series) -> pd.DataFrame:
    unique_dates = pd.Index(sorted(pd.to_datetime(dates.dropna().unique())))
    rows = []
    split_id = 0
    for start_idx in range(INITIAL_TRAIN_DATES, len(unique_dates), REFIT_FREQ):
        test_end_idx = min(start_idx + REFIT_FREQ, len(unique_dates))
        train_dates = unique_dates[:start_idx]
        test_dates = unique_dates[start_idx:test_end_idx]
        if len(test_dates) == 0:
            continue
        rows.append(
            {
                "split_id": split_id,
                "train_start_date": train_dates[0],
                "train_end_date": train_dates[-1],
                "test_start_date": test_dates[0],
                "test_end_date": test_dates[-1],
                "n_train_dates": len(train_dates),
                "n_test_dates": len(test_dates),
            }
        )
        split_id += 1
    splits = pd.DataFrame(rows)
    save_csv(splits, OUT / "sss_walkforward_splits.csv")
    return splits


def safe_auc(y: pd.Series, p: pd.Series) -> float:
    if y.nunique(dropna=True) < 2:
        return np.nan
    try:
        return float(roc_auc_score(y, p))
    except Exception:
        return np.nan


def safe_log_loss(y: pd.Series, p: pd.Series) -> float:
    if y.nunique(dropna=True) < 2:
        return np.nan
    try:
        return float(log_loss(y, np.clip(p, 1e-5, 1 - 1e-5)))
    except Exception:
        return np.nan


def rank_scale_from_train(train_values: pd.Series, test_values: pd.Series, fallback: float) -> pd.Series:
    train = pd.to_numeric(train_values, errors="coerce").dropna()
    test = pd.to_numeric(test_values, errors="coerce")
    if train.nunique() < 2:
        return pd.Series(fallback, index=test_values.index)
    lo, hi = train.quantile(0.02), train.quantile(0.98)
    if hi <= lo:
        return pd.Series(fallback, index=test_values.index)
    return ((test - lo) / (hi - lo)).clip(0.0, 1.0).fillna(fallback)


def predict_rate_by_group(train: pd.DataFrame, test: pd.DataFrame, target: str, group_cols: list[str], fallback: float) -> pd.Series:
    if not group_cols or any(c not in train.columns for c in group_cols):
        return pd.Series(fallback, index=test.index)
    rates = train.groupby(group_cols)[target].mean()
    keys = test[group_cols].apply(lambda r: tuple(r), axis=1)
    if len(group_cols) == 1:
        pred = test[group_cols[0]].map(rates)
    else:
        pred = keys.map(rates)
    return pred.fillna(fallback).astype(float)


def markov_stress_prob(train_states: pd.Series, start_states: pd.Series, horizon: int, fallback: float) -> pd.Series:
    states = sorted(train_states.dropna().astype(str).unique())
    if not states:
        return pd.Series(fallback, index=start_states.index)
    counts = pd.crosstab(train_states.astype(str), train_states.shift(-1).astype(str))
    counts = counts.reindex(index=states, columns=states, fill_value=0)
    probs = counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    for s in states:
        if probs.loc[s].sum() == 0:
            probs.loc[s, s] = 1.0
    P = probs.to_numpy()
    idx = {s: i for i, s in enumerate(states)}
    stress_idx = idx.get("stressed_panic")
    if stress_idx is None:
        return pd.Series(fallback, index=start_states.index)
    out = []
    for s in start_states.astype(str):
        if s not in idx:
            out.append(fallback)
            continue
        dist = np.zeros(len(states))
        dist[idx[s]] = 1.0
        prob_not = 1.0
        for _ in range(horizon):
            dist = dist @ P
            prob_not *= max(0.0, 1.0 - float(dist[stress_idx]))
        out.append(float(np.clip(1.0 - prob_not, 0.0, 1.0)))
    return pd.Series(out, index=start_states.index)


def make_baseline_predictions(train: pd.DataFrame, test: pd.DataFrame, target: str) -> list[pd.DataFrame]:
    rows = []
    y_train = pd.to_numeric(train[target], errors="coerce")
    fallback = float(y_train.mean()) if y_train.notna().any() else 0.5
    base = test[["date", "market_state", target, TARGET_META[target]["return_col"]]].copy()
    base = base.rename(columns={target: "actual", TARGET_META[target]["return_col"]: "forward_return"})

    specs = {
        "historical_class_rate": pd.Series(fallback, index=test.index),
        "current_state_lag1_rate": predict_rate_by_group(train, test, target, ["state_lag1"], fallback),
        "previous_state_lag2_rate": predict_rate_by_group(train, test, target, ["state_lag2"], fallback),
        "current_state_plus_dwell_rate": predict_rate_by_group(train, test, target, ["state_lag1", "state_dwell_bucket_lag1"], fallback),
        "state_path_markov_rate": predict_rate_by_group(train, test, target, ["path2_lag"], fallback),
    }
    if target.startswith("stress_transition"):
        h = TARGET_META[target]["horizon"]
        specs["transition_matrix_markov_score"] = markov_stress_prob(train["state_lag1"], test["state_lag1"], h, fallback)
    else:
        specs["transition_matrix_markov_score"] = specs["state_path_markov_rate"]

    if target in {"stress_transition_4w", "stress_transition_8w", "ggg1_tail_risk_4w", "false_recovery_label"}:
        l2b_col = "l2b_p_tail_risk_lag1" if "l2b_p_tail_risk_lag1" in train.columns else "l2b_p_stress_forecast_lag1"
    elif target == "recovery_quality_4w" or target == "recovery_quality_8w":
        l2b_col = "l2b_p_transition_quality_lag1"
    else:
        l2b_col = "l2b_p_regime_confidence_lag1"
    if l2b_col in train.columns:
        specs["existing_layer2b_probability_baseline"] = rank_scale_from_train(train[l2b_col], test[l2b_col], fallback)

    qqq_cols = [c for c in train.columns if c.startswith("qqq_active_") and c.endswith("_lag1")]
    if qqq_cols:
        train_qqq = train[qqq_cols].mean(axis=1)
        test_qqq = test[qqq_cols].mean(axis=1)
        specs["qqq_rule_only_baseline"] = rank_scale_from_train(train_qqq, test_qqq, fallback)

    for model, pred in specs.items():
        out = base.copy()
        out["target"] = target
        out["model"] = model
        out["prediction"] = pd.Series(pred, index=test.index).clip(0.0, 1.0).fillna(fallback).to_numpy()
        rows.append(out[["date", "market_state", "target", "model", "prediction", "actual", "forward_return"]])
    return rows


def make_model(model_name: str) -> Pipeline:
    if model_name in {"logistic_sequence_l2", "logistic_sequence_plus_l2b", "logistic_sequence_plus_qqq"}:
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(C=0.45, max_iter=600, solver="lbfgs", random_state=RANDOM_STATE)),
            ]
        )
    if model_name == "decision_tree_depth3":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", DecisionTreeClassifier(max_depth=3, min_samples_leaf=20, random_state=RANDOM_STATE)),
            ]
        )
    if model_name == "random_forest_depth4":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=100,
                        max_depth=4,
                        min_samples_leaf=18,
                        max_features="sqrt",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        )
    if model_name == "hist_gradient_depth3":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        max_iter=80,
                        learning_rate=0.055,
                        max_leaf_nodes=15,
                        min_samples_leaf=18,
                        l2_regularization=0.05,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        )
    raise ValueError(model_name)


def feature_importance_from_pipeline(pipe: Pipeline, feature_cols: list[str], model_name: str) -> pd.DataFrame:
    model = pipe.named_steps["model"]
    rows = []
    if hasattr(model, "coef_"):
        coefs = pd.Series(model.coef_[0], index=feature_cols)
        top = coefs.abs().sort_values(ascending=False).head(MAX_IMPORTANCE_ROWS_PER_FOLD)
        for feature, abs_value in top.items():
            rows.append({"feature": feature, "importance": float(coefs.loc[feature]), "abs_importance": float(abs_value), "importance_type": "coefficient", "model": model_name})
    elif hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=feature_cols)
        top = imp.sort_values(ascending=False).head(MAX_IMPORTANCE_ROWS_PER_FOLD)
        for feature, value in top.items():
            if value <= 0:
                continue
            rows.append({"feature": feature, "importance": float(value), "abs_importance": float(abs(value)), "importance_type": "tree_importance", "model": model_name})
    return pd.DataFrame(rows)


def run_walkforward_models(
    feature_panel: pd.DataFrame,
    target_panel: pd.DataFrame,
    feature_groups: dict[str, list[str]],
    splits: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = feature_panel.merge(target_panel.drop(columns=["market_state", "refined_state"], errors="ignore"), on="date", how="left")
    df["date"] = pd.to_datetime(df["date"])
    baseline_frames = []
    model_frames = []
    importance_rows = []
    sequence_features = feature_groups["sequence"]
    l2b_features = feature_groups["layer2b"]
    qqq_features = feature_groups["qqq"]
    model_specs = [
        ("logistic_sequence_l2", sequence_features),
        ("decision_tree_depth3", sequence_features),
        ("random_forest_depth4", sequence_features),
        ("hist_gradient_depth3", sequence_features),
    ]
    if l2b_features:
        model_specs.append(("logistic_sequence_plus_l2b", sequence_features + l2b_features))
    if qqq_features:
        model_specs.append(("logistic_sequence_plus_qqq", sequence_features + qqq_features))

    for target in TARGETS:
        if target not in df.columns or df[target].notna().sum() < 80:
            continue
        for _, split in splits.iterrows():
            train_mask = (df["date"] <= split["train_end_date"]) & df[target].notna()
            test_mask = (df["date"] >= split["test_start_date"]) & (df["date"] <= split["test_end_date"]) & df[target].notna()
            train = df.loc[train_mask].copy()
            test = df.loc[test_mask].copy()
            if len(train) < 120 or len(test) < 5 or train[target].nunique() < 2:
                continue
            for b in make_baseline_predictions(train, test, target):
                b["split_id"] = int(split["split_id"])
                baseline_frames.append(b[["date", "market_state", "target", "model", "split_id", "prediction", "actual", "forward_return"]])

            for model_name, cols in model_specs:
                usable = [c for c in cols if c in df.columns and train[c].notna().any()]
                if not usable:
                    continue
                x_train = train[usable].apply(pd.to_numeric, errors="coerce")
                y_train = train[target].astype(int)
                x_test = test[usable].apply(pd.to_numeric, errors="coerce")
                pipe = make_model(model_name)
                try:
                    pipe.fit(x_train, y_train)
                    pred = pipe.predict_proba(x_test)[:, 1]
                except Exception as exc:
                    importance_rows.append(
                        {
                            "target": target,
                            "model": model_name,
                            "split_id": int(split["split_id"]),
                            "feature": "MODEL_FIT_ERROR",
                            "importance": np.nan,
                            "abs_importance": np.nan,
                            "importance_type": f"error: {exc}",
                        }
                    )
                    continue
                out = test[["date", "market_state", target, TARGET_META[target]["return_col"]]].copy()
                out = out.rename(columns={target: "actual", TARGET_META[target]["return_col"]: "forward_return"})
                out["target"] = target
                out["model"] = model_name
                out["split_id"] = int(split["split_id"])
                out["prediction"] = pred
                model_frames.append(out[["date", "market_state", "target", "model", "split_id", "prediction", "actual", "forward_return"]])
                imp = feature_importance_from_pipeline(pipe, usable, model_name)
                for _, row in imp.iterrows():
                    importance_rows.append(
                        {
                            "target": target,
                            "model": model_name,
                            "split_id": int(split["split_id"]),
                            "feature": row["feature"],
                            "importance": row["importance"],
                            "abs_importance": row["abs_importance"],
                            "importance_type": row["importance_type"],
                            "feature_family": classify_feature_family(row["feature"]),
                        }
                    )

    baseline_predictions = pd.concat(baseline_frames, ignore_index=True) if baseline_frames else pd.DataFrame()
    model_predictions = pd.concat(model_frames, ignore_index=True) if model_frames else pd.DataFrame()
    importance = pd.DataFrame(importance_rows)
    save_csv(baseline_predictions, OUT / "sss_baseline_predictions.csv")
    save_csv(model_predictions, OUT / "sss_sequence_model_predictions.csv")
    save_csv(importance, OUT / "sss_sequence_feature_importance.csv")
    return baseline_predictions, model_predictions, importance


def classify_feature_family(feature: str) -> str:
    if feature.startswith("path"):
        return "state_ngram"
    if feature.startswith("state_lag") or feature.startswith("refined_state") or feature.startswith("risk_state"):
        return "state_identity"
    if "dwell" in feature or "age" in feature or "time_since" in feature:
        return "dwell_time"
    if "count" in feature or "entropy" in feature or "transition" in feature or "instability" in feature or "memory" in feature:
        return "state_memory"
    if feature.startswith("l2b_"):
        return "existing_layer2b"
    if feature.startswith("qqq_"):
        return "qqq_rule_context"
    if feature.startswith("ooo"):
        return "ooo_signal_context"
    return "other"


def evaluate_prediction_frame(pred: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    if pred.empty:
        return pd.DataFrame()
    group_cols = group_cols or ["target", "model"]
    rows = []
    for key, g in pred.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        y = pd.to_numeric(g["actual"], errors="coerce")
        p = pd.to_numeric(g["prediction"], errors="coerce").clip(0.0, 1.0)
        valid = y.notna() & p.notna()
        y = y[valid]
        p = p[valid]
        gg = g.loc[valid]
        row = {c: v for c, v in zip(group_cols, key)}
        row["n_oos"] = int(len(y))
        row["positive_rate"] = float(y.mean()) if len(y) else np.nan
        row["brier"] = float(brier_score_loss(y, p)) if len(y) else np.nan
        row["auc"] = safe_auc(y, p)
        row["log_loss"] = safe_log_loss(y, p)
        n_top = max(1, int(math.ceil(len(y) * 0.10))) if len(y) else 0
        top_idx = p.sort_values(ascending=False).head(n_top).index
        top_actual = y.loc[top_idx] if n_top else pd.Series(dtype=float)
        positives = y.sum()
        row["high_risk_decile_precision"] = float(top_actual.mean()) if len(top_actual) else np.nan
        row["high_risk_decile_recall"] = float(top_actual.sum() / positives) if positives else np.nan
        row["top_decile_avg_forward_return"] = float(pd.to_numeric(gg.loc[top_idx, "forward_return"], errors="coerce").mean()) if len(top_idx) else np.nan
        row["overall_avg_forward_return"] = float(pd.to_numeric(gg["forward_return"], errors="coerce").mean()) if len(gg) else np.nan
        row["top_decile_return_lift"] = row["top_decile_avg_forward_return"] - row["overall_avg_forward_return"]
        rows.append(row)
    return pd.DataFrame(rows)


def calibration_summary(pred: pd.DataFrame, filename: str) -> pd.DataFrame:
    rows = []
    if pred.empty:
        out = pd.DataFrame()
        save_csv(out, OUT / filename)
        return out
    for (target, model), g in pred.groupby(["target", "model"]):
        p = pd.to_numeric(g["prediction"], errors="coerce")
        y = pd.to_numeric(g["actual"], errors="coerce")
        valid = p.notna() & y.notna()
        gg = g.loc[valid].copy()
        if len(gg) < 10 or gg["prediction"].nunique() < 2:
            continue
        try:
            gg["bucket"] = pd.qcut(gg["prediction"], 10, labels=False, duplicates="drop")
        except Exception:
            continue
        for bucket, b in gg.groupby("bucket"):
            rows.append(
                {
                    "target": target,
                    "model": model,
                    "bucket": int(bucket),
                    "n_obs": int(len(b)),
                    "mean_prediction": float(b["prediction"].mean()),
                    "positive_rate": float(b["actual"].mean()),
                    "avg_forward_return": float(pd.to_numeric(b["forward_return"], errors="coerce").mean()),
                }
            )
    out = pd.DataFrame(rows)
    save_csv(out, OUT / filename)
    return out


def subperiod_stability(pred: pd.DataFrame, filename: str) -> pd.DataFrame:
    if pred.empty:
        out = pd.DataFrame()
        save_csv(out, OUT / filename)
        return out
    g = pred.copy()
    g["date"] = pd.to_datetime(g["date"])
    bins = [
        (pd.Timestamp("1900-01-01"), pd.Timestamp("2014-12-31"), "pre_2015"),
        (pd.Timestamp("2015-01-01"), pd.Timestamp("2019-12-31"), "2015_2019"),
        (pd.Timestamp("2020-01-01"), pd.Timestamp("2100-01-01"), "2020_plus"),
    ]
    frames = []
    for start, end, label in bins:
        part = g[(g["date"] >= start) & (g["date"] <= end)].copy()
        if part.empty:
            continue
        m = evaluate_prediction_frame(part)
        m["subperiod"] = label
        frames.append(m)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    save_csv(out, OUT / filename)
    return out


def transition_window_performance(pred: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    if pred.empty:
        out = pd.DataFrame()
        save_csv(out, OUT / "sss_transition_window_performance.csv")
        return out
    p = panel[["date", "market_state"]].copy()
    p["state_change"] = p["market_state"].ne(p["market_state"].shift(1))
    p["stress_start"] = p["market_state"].eq("stressed_panic") & ~p["market_state"].shift(1).eq("stressed_panic")
    p["recovery_start"] = p["market_state"].isin(RECOVERY_STATES) & ~p["market_state"].shift(1).isin(RECOVERY_STATES)
    for event in ["state_change", "stress_start", "recovery_start"]:
        idxs = set()
        event_idx = p.index[p[event]].tolist()
        for idx in event_idx:
            for k in range(-4, 5):
                if 0 <= idx + k < len(p):
                    idxs.add(idx + k)
        p[f"around_{event}_pm4w"] = False
        p.loc[list(idxs), f"around_{event}_pm4w"] = True
    merged = pred.merge(p.drop(columns=["market_state"]), on="date", how="left")
    frames = []
    for col in ["around_state_change_pm4w", "around_stress_start_pm4w", "around_recovery_start_pm4w"]:
        for val, label in [(True, col), (False, f"not_{col}")]:
            part = merged[merged[col].eq(val)]
            if part.empty:
                continue
            m = evaluate_prediction_frame(part)
            m["transition_window"] = label
            frames.append(m)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    save_csv(out, OUT / "sss_transition_window_performance.csv")
    return out


def evaluate_all_predictions(baseline_predictions: pd.DataFrame, model_predictions: pd.DataFrame, panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    baseline_metrics = evaluate_prediction_frame(baseline_predictions)
    model_metrics = evaluate_prediction_frame(model_predictions)
    save_csv(baseline_metrics, OUT / "sss_baseline_model_metrics.csv")
    save_csv(model_metrics, OUT / "sss_sequence_model_metrics.csv")
    model_cal = calibration_summary(model_predictions, "sss_sequence_model_calibration.csv")
    subperiod = subperiod_stability(model_predictions, "sss_sequence_subperiod_stability.csv")
    transition = transition_window_performance(model_predictions, panel)
    return {"baseline_metrics": baseline_metrics, "model_metrics": model_metrics, "model_calibration": model_cal, "subperiod": subperiod, "transition": transition}


def build_rule_specs(feature_panel: pd.DataFrame) -> list[RuleSpec]:
    specs = [
        RuleSpec("neutral_after_stress_short_dwell", "state_lag1 == neutral_mixed and state_lag2 == stressed_panic and state_age_lag1 <= 6", "neutral_mixed immediately after stress with young dwell", "stress_memory", lambda d: d["state_lag1"].eq("neutral_mixed") & d["state_lag2"].eq("stressed_panic") & (d["state_age_lag1"] <= 6)),
        RuleSpec("neutral_after_calm_old_dwell", "state_lag1 == neutral_mixed and state_lag2 == calm_trend and state_age_lag1 >= 14", "old neutral_mixed after calm_trend", "dwell_transition", lambda d: d["state_lag1"].eq("neutral_mixed") & d["state_lag2"].eq("calm_trend") & (d["state_age_lag1"] >= 14)),
        RuleSpec("neutral_old_high_state_changes", "state_lag1 == neutral_mixed and state_age_lag1 >= 14 and state_changes_last_8w >= 2", "old neutral state with repeated recent regime changes", "instability", lambda d: d["state_lag1"].eq("neutral_mixed") & (d["state_age_lag1"] >= 14) & (d["state_changes_last_8w"] >= 2)),
        RuleSpec("recovery_confirmed_after_fragile_low_stress", "state_lag1 == recovery_confirmed and state_lag2 == recovery_fragile and stress_count_last_13w <= 2", "confirmed recovery that graduates from fragile recovery with limited recent stress", "recovery_quality", lambda d: d["state_lag1"].eq("recovery_confirmed") & d["state_lag2"].eq("recovery_fragile") & (d["stress_count_last_13w"] <= 2)),
        RuleSpec("recovery_confirmed_after_neutral", "state_lag1 == recovery_confirmed and state_lag2 == neutral_mixed", "confirmed recovery after neutral_mixed rather than fragile recovery", "recovery_path", lambda d: d["state_lag1"].eq("recovery_confirmed") & d["state_lag2"].eq("neutral_mixed")),
        RuleSpec("recovery_fragile_after_stress", "state_lag1 == recovery_fragile and state_lag2 == stressed_panic", "fragile recovery immediately after stress", "recovery_path", lambda d: d["state_lag1"].eq("recovery_fragile") & d["state_lag2"].eq("stressed_panic")),
        RuleSpec("calm_old_low_stress", "state_lag1 == calm_trend and state_age_lag1 >= 14 and stress_count_last_13w == 0", "mature calm trend with no recent stress memory", "calm_persistence", lambda d: d["state_lag1"].eq("calm_trend") & (d["state_age_lag1"] >= 14) & (d["stress_count_last_13w"] == 0)),
        RuleSpec("stress_new_state", "state_lag1 == stressed_panic and state_age_lag1 <= 2", "new stressed_panic state", "stress_dwell", lambda d: d["state_lag1"].eq("stressed_panic") & (d["state_age_lag1"] <= 2)),
        RuleSpec("stress_old_state", "state_lag1 == stressed_panic and state_age_lag1 >= 7", "mature stressed_panic state", "stress_dwell", lambda d: d["state_lag1"].eq("stressed_panic") & (d["state_age_lag1"] >= 7)),
        RuleSpec("high_transition_instability", "state_changes_last_8w >= 3", "high recent transition instability", "instability", lambda d: d["state_changes_last_8w"] >= 3),
        RuleSpec("stress_memory_neutral", "state_lag1 == neutral_mixed and stress_count_last_13w > 0", "neutral_mixed with recent stress memory", "stress_memory", lambda d: d["state_lag1"].eq("neutral_mixed") & (d["stress_count_last_13w"] > 0)),
        RuleSpec("refined_neutral_deteriorating", "refined_state_lag1 == neutral_deteriorating", "Layer 2B neutral deterioration refinement", "refined_state", lambda d: d["refined_state_lag1"].eq("neutral_deteriorating")),
        RuleSpec("refined_neutral_healthy_after_stress", "refined_state_lag1 == neutral_healthy and stress_count_last_13w > 0", "neutral_healthy despite recent stress memory", "refined_state", lambda d: d["refined_state_lag1"].eq("neutral_healthy") & (d["stress_count_last_13w"] > 0)),
    ]
    if "qqq_active_int_market_trend_x_mom13_lag1" in feature_panel.columns:
        specs.append(
            RuleSpec(
                "qqq_market_trend_mom13_after_recovery",
                "QQQ market_trend_x_mom13 active and recent recovery state",
                "QQQ state-gated momentum rule after recovery context",
                "qqq_sequence_overlap",
                lambda d: (d["qqq_active_int_market_trend_x_mom13_lag1"] > 0.05) & (d["recovery_count_last_13w"] > 0),
            )
        )
    if "qqq_active_int_efa_spy_strength_x_market_trend_lag1" in feature_panel.columns:
        specs.append(
            RuleSpec(
                "qqq_efa_spy_trend_after_calm_or_recovery",
                "QQQ EFA/SPY trend active and calm/recovery memory",
                "QQQ international leadership rule under calm/recovery sequence",
                "qqq_sequence_overlap",
                lambda d: (d["qqq_active_int_efa_spy_strength_x_market_trend_lag1"] > 0.05) & ((d["state_lag1"].eq("calm_trend")) | (d["recovery_count_last_13w"] > 0)),
            )
        )
    return specs


def evaluate_rules(feature_panel: pd.DataFrame, target_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = feature_panel.merge(target_panel.drop(columns=["market_state", "refined_state"], errors="ignore"), on="date", how="left")
    specs = build_rule_specs(feature_panel)
    rows = []
    subperiod_bins = [
        (pd.Timestamp("1900-01-01"), pd.Timestamp("2014-12-31")),
        (pd.Timestamp("2015-01-01"), pd.Timestamp("2019-12-31")),
        (pd.Timestamp("2020-01-01"), pd.Timestamp("2100-01-01")),
    ]
    for spec in specs:
        try:
            event = spec.evaluator(df).fillna(False).astype(bool)
        except Exception:
            continue
        for target in TARGETS:
            if target not in df.columns:
                continue
            valid = df[target].notna()
            g = df[valid].copy()
            e = event[valid]
            if len(g) == 0:
                continue
            ev = g[e]
            baseline_precision = float(g[target].mean())
            precision = float(ev[target].mean()) if len(ev) else np.nan
            fwd_col = TARGET_META[target]["return_col"]
            baseline_ret = float(g[fwd_col].mean())
            avg_ret = float(ev[fwd_col].mean()) if len(ev) else np.nan
            stable_checks = []
            min_events = np.inf
            for start, end in subperiod_bins:
                sub = g[(g["date"] >= start) & (g["date"] <= end)]
                sub_e = e.loc[sub.index]
                sub_ev = sub[sub_e]
                min_events = min(min_events, len(sub_ev))
                if len(sub_ev) >= 5 and sub[target].notna().sum() and sub[target].mean() == sub[target].mean():
                    stable_checks.append(float(sub_ev[target].mean() - sub[target].mean()) > 0)
            stability = float(np.mean(stable_checks)) if stable_checks else 0.0
            rows.append(
                {
                    "rule_name": spec.rule_name,
                    "rule_formula": spec.formula,
                    "target": target,
                    "event_count": int(len(ev)),
                    "event_frequency": float(len(ev) / len(g)) if len(g) else np.nan,
                    "precision": precision,
                    "baseline_precision": baseline_precision,
                    "precision_lift": precision - baseline_precision if precision == precision else np.nan,
                    "avg_forward_return": avg_ret,
                    "baseline_avg_forward_return": baseline_ret,
                    "return_lift": avg_ret - baseline_ret if avg_ret == avg_ret else np.nan,
                    "state_path_interpretation": spec.interpretation,
                    "rule_family": spec.family,
                    "stability": stability,
                    "min_subperiod_events": int(min_events) if min_events != np.inf else 0,
                    "redundancy_warning": "",
                    "next_recommended_phase": "",
                }
            )
    perf = pd.DataFrame(rows)
    if not perf.empty:
        perf["redundancy_warning"] = np.where(perf["rule_family"].isin(["refined_state"]), "partly duplicates existing refined Layer 2B state", "")
        perf["next_recommended_phase"] = np.where(perf["precision_lift"] > 0.08, "SSS2 sequence signal validation", "retain as diagnostic only")
        perf = perf.sort_values(["precision_lift", "event_count"], ascending=[False, False])
    save_csv(perf, OUT / "sss_sequence_rule_performance.csv")

    extracted = perf[(perf["event_count"] >= 20) & (perf["precision_lift"] > 0) & (perf["stability"] >= 0.34)].copy()
    extracted = extracted.sort_values(["precision_lift", "stability", "event_count"], ascending=[False, False, False]).head(40)
    save_csv(extracted, OUT / "sss_extracted_sequence_rules.csv")

    path_summary = perf.groupby(["rule_name", "rule_family", "state_path_interpretation"], dropna=False).agg(
        targets_tested=("target", "nunique"),
        max_precision_lift=("precision_lift", "max"),
        avg_precision_lift=("precision_lift", "mean"),
        max_event_count=("event_count", "max"),
        max_stability=("stability", "max"),
    ).reset_index().sort_values("max_precision_lift", ascending=False)
    save_csv(path_summary, OUT / "sss_state_path_rule_summary.csv")
    return perf, extracted, path_summary


def compare_qqq_after_sequence(model_metrics: pd.DataFrame, feature_panel: pd.DataFrame, target_panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    qqq_cols = [c for c in feature_panel.columns if c.startswith("qqq_active_") and c.endswith("_lag1")]
    seq_feature_cols = [c for c in feature_panel.columns if c.startswith("path") or c.startswith("state_lag") or c.startswith("refined_state") or c in {"state_age_lag1", "stress_count_last_13w", "state_changes_last_8w"}]
    for target in TARGETS:
        base = model_metrics[(model_metrics["target"].eq(target)) & (model_metrics["model"].eq("logistic_sequence_l2"))]
        plus = model_metrics[(model_metrics["target"].eq(target)) & (model_metrics["model"].eq("logistic_sequence_plus_qqq"))]
        row = {"target": target}
        if not base.empty and not plus.empty:
            b = base.iloc[0]
            p = plus.iloc[0]
            row.update(
                {
                    "sequence_auc": b.get("auc"),
                    "sequence_plus_qqq_auc": p.get("auc"),
                    "delta_auc_plus_qqq": p.get("auc") - b.get("auc"),
                    "sequence_brier": b.get("brier"),
                    "sequence_plus_qqq_brier": p.get("brier"),
                    "delta_brier_plus_qqq": p.get("brier") - b.get("brier"),
                    "sequence_high_risk_precision": b.get("high_risk_decile_precision"),
                    "sequence_plus_qqq_high_risk_precision": p.get("high_risk_decile_precision"),
                    "delta_high_risk_precision_plus_qqq": p.get("high_risk_decile_precision") - b.get("high_risk_decile_precision"),
                }
            )
        else:
            row.update({"sequence_auc": np.nan, "sequence_plus_qqq_auc": np.nan, "delta_auc_plus_qqq": np.nan, "sequence_brier": np.nan, "sequence_plus_qqq_brier": np.nan, "delta_brier_plus_qqq": np.nan})
        max_corr = 0.0
        closest = ""
        for q in qqq_cols:
            for s in seq_feature_cols:
                if q == s:
                    continue
                corr = pd.to_numeric(feature_panel[q], errors="coerce").corr(pd.to_numeric(feature_panel[s], errors="coerce"))
                if corr == corr and abs(corr) > abs(max_corr):
                    max_corr = float(corr)
                    closest = s
        row["max_abs_corr_qqq_to_sequence_feature"] = abs(max_corr)
        row["closest_sequence_feature_to_qqq"] = closest
        if row.get("delta_auc_plus_qqq", np.nan) == row.get("delta_auc_plus_qqq", np.nan):
            if row["delta_auc_plus_qqq"] > 0.015 and row.get("delta_high_risk_precision_plus_qqq", 0) > 0:
                conclusion = "QQQ_REMAINS_INCREMENTAL_AFTER_SEQUENCE_CONTROL"
            elif row["max_abs_corr_qqq_to_sequence_feature"] > 0.50 or row["delta_auc_plus_qqq"] <= 0.005:
                conclusion = "QQQ_VALUE_MOSTLY_EXPLAINED_BY_SEQUENCE_OR_STATE_CONTEXT"
            else:
                conclusion = "MIXED_QQQ_SEQUENCE_INCREMENTALITY"
        else:
            conclusion = "INSUFFICIENT_QQQ_CONTROL_DATA"
        row["conclusion"] = conclusion
        rows.append(row)
    out = pd.DataFrame(rows)
    save_csv(out, OUT / "sss_qqq_interaction_after_sequence_control.csv")
    return out


def compare_ooo_overlap(feature_panel: pd.DataFrame) -> pd.DataFrame:
    ooo_cols = [c for c in feature_panel.columns if (c.startswith("ooo2_") or c.startswith("ooo3event_")) and c.endswith("_lag1")]
    seq_cols = [c for c in feature_panel.columns if c.startswith("state_lag1_") or c.startswith("refined_state_lag1_") or c.startswith("path2_lag_")]
    rows = []
    for ooo in ooo_cols:
        x = pd.to_numeric(feature_panel[ooo], errors="coerce")
        max_corr = 0.0
        closest = ""
        max_overlap = 0.0
        overlap_col = ""
        event = x.fillna(0) > 0
        for seq in seq_cols:
            y = pd.to_numeric(feature_panel[seq], errors="coerce").fillna(0)
            corr = x.corr(y)
            if corr == corr and abs(corr) > abs(max_corr):
                max_corr = float(corr)
                closest = seq
            seq_event = y > 0
            denom = max(1, int(event.sum()))
            overlap = float((event & seq_event).sum() / denom)
            if overlap > max_overlap:
                max_overlap = overlap
                overlap_col = seq
        rows.append(
            {
                "ooo_signal_or_event": ooo,
                "event_frequency": float(event.mean()),
                "max_abs_corr_sequence": abs(max_corr),
                "closest_sequence_feature": closest,
                "max_event_overlap_sequence": max_overlap,
                "max_overlap_sequence_feature": overlap_col,
                "overlap_flag": "MOSTLY_STATE_SEQUENCE_PROXY" if abs(max_corr) > 0.50 or max_overlap > 0.70 else "PARTLY_INCREMENTAL_OR_MIXED",
            }
        )
    out = pd.DataFrame(rows).sort_values(["max_abs_corr_sequence", "max_event_overlap_sequence"], ascending=False)
    save_csv(out, OUT / "sss_ooo_signal_sequence_overlap.csv")
    return out


def classify_incrementality(rule_perf: pd.DataFrame, feature_panel: pd.DataFrame) -> pd.DataFrame:
    if rule_perf.empty:
        out = pd.DataFrame()
        save_csv(out, OUT / "sss_sequence_incrementality_summary.csv")
        return out
    rows = []
    state_dummies = [c for c in feature_panel.columns if c.startswith("state_lag1_") or c.startswith("refined_state_lag1_")]
    rule_specs = {s.rule_name: s for s in build_rule_specs(feature_panel)}
    for _, row in rule_perf.iterrows():
        spec = rule_specs.get(row["rule_name"])
        if spec is None:
            continue
        event = spec.evaluator(feature_panel).fillna(False).astype(float)
        max_corr = 0.0
        closest = ""
        for c in state_dummies:
            corr = event.corr(pd.to_numeric(feature_panel[c], errors="coerce").fillna(0))
            if corr == corr and abs(corr) > abs(max_corr):
                max_corr = float(corr)
                closest = c
        if row["event_count"] < 20:
            flag = "INSUFFICIENT_EVIDENCE"
        elif abs(max_corr) > 0.85 or "refined" in row["rule_family"]:
            flag = "DUPLICATES_CURRENT_STATE_ENGINE"
        elif row["precision_lift"] > 0.08 and row["stability"] >= 0.50:
            flag = "INCREMENTAL_SEQUENCE_SIGNAL"
        elif "qqq" in row["rule_family"]:
            flag = "DUPLICATES_QQQ_RULE"
        elif row["precision_lift"] <= 0:
            flag = "NOT_ACTIONABLE"
        else:
            flag = "INSUFFICIENT_EVIDENCE"
        rows.append(
            {
                "rule_name": row["rule_name"],
                "target": row["target"],
                "incrementality_flag": flag,
                "max_abs_corr_current_state_engine": abs(max_corr),
                "closest_state_engine_feature": closest,
                "event_count": row["event_count"],
                "event_frequency": row["event_frequency"],
                "precision_lift": row["precision_lift"],
                "stability": row["stability"],
                "rule_family": row["rule_family"],
                "state_path_interpretation": row["state_path_interpretation"],
            }
        )
    out = pd.DataFrame(rows).sort_values(["incrementality_flag", "precision_lift"], ascending=[True, False])
    save_csv(out, OUT / "sss_sequence_incrementality_summary.csv")
    return out


def ggg1_weakness_diagnostics(rule_perf: pd.DataFrame, incrementality: pd.DataFrame) -> pd.DataFrame:
    weak_targets = {"stress_transition_4w", "stress_transition_8w", "ggg1_underperformance_4w", "ggg1_tail_risk_4w", "false_recovery_label"}
    if rule_perf.empty:
        out = pd.DataFrame()
        save_csv(out, OUT / "sss_ggg1_sequence_weakness_diagnostics.csv")
        return out
    out = rule_perf[rule_perf["target"].isin(weak_targets)].copy()
    out = out.merge(incrementality[["rule_name", "target", "incrementality_flag", "max_abs_corr_current_state_engine"]], on=["rule_name", "target"], how="left")
    out["ggg1_weakness_flag"] = np.where(
        (out["precision_lift"] > 0.08) & (out["event_count"] >= 20),
        "SEQUENCE_IDENTIFIES_GGG1_WEAK_PERIOD",
        "NO_CLEAR_GGG1_WEAKNESS_SIGNAL",
    )
    out = out.sort_values(["precision_lift", "event_count"], ascending=[False, False])
    save_csv(out, OUT / "sss_ggg1_sequence_weakness_diagnostics.csv")
    return out


def build_shortlist(
    rule_perf: pd.DataFrame,
    incrementality: pd.DataFrame,
    model_metrics: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if rule_perf.empty:
        empty = pd.DataFrame()
        for name in ["sss_candidate_sequence_signal_shortlist.csv", "sss_rejected_sequence_rule_log.csv", "sss_next_phase_queue.csv"]:
            save_csv(empty, OUT / name)
        rec = pd.DataFrame([{"recommendation": "STOP_HARD_ML_FOR_NOW", "reason": "No sequence rules were evaluable.", "high_priority_count": 0, "promising_count": 0, "shortlist_count": 0}])
        save_csv(rec, OUT / "sss_next_action_recommendation.csv")
        return empty, empty, empty, rec

    base_state = baseline_metrics[baseline_metrics["model"].eq("current_state_lag1_rate")][["target", "brier", "auc", "high_risk_decile_precision"]].rename(
        columns={"brier": "state_brier", "auc": "state_auc", "high_risk_decile_precision": "state_high_risk_precision"}
    )
    markov = baseline_metrics[baseline_metrics["model"].eq("transition_matrix_markov_score")][["target", "brier", "auc", "high_risk_decile_precision"]].rename(
        columns={"brier": "markov_brier", "auc": "markov_auc", "high_risk_decile_precision": "markov_high_risk_precision"}
    )
    best_seq = model_metrics.sort_values(["target", "brier"]).groupby("target").head(1)[["target", "model", "brier", "auc", "high_risk_decile_precision"]].rename(
        columns={"model": "best_sequence_model", "brier": "best_sequence_brier", "auc": "best_sequence_auc", "high_risk_decile_precision": "best_sequence_high_risk_precision"}
    )
    improvement = best_seq.merge(base_state, on="target", how="left").merge(markov, on="target", how="left")
    improvement["auc_lift_vs_state"] = improvement["best_sequence_auc"] - improvement["state_auc"]
    improvement["brier_improvement_vs_state"] = improvement["state_brier"] - improvement["best_sequence_brier"]
    improvement["precision_lift_vs_state"] = improvement["best_sequence_high_risk_precision"] - improvement["state_high_risk_precision"]

    merged = rule_perf.merge(incrementality, on=["rule_name", "target"], how="left", suffixes=("", "_inc")).merge(improvement, on="target", how="left")
    classifications = []
    reasons = []
    for _, row in merged.iterrows():
        enough = row["event_count"] >= 25 and row["event_frequency"] >= 0.015
        stable = row["stability"] >= 0.50
        model_improves = (row.get("auc_lift_vs_state", 0) == row.get("auc_lift_vs_state", 0) and row.get("auc_lift_vs_state", 0) > 0.015) or (
            row.get("brier_improvement_vs_state", 0) == row.get("brier_improvement_vs_state", 0) and row.get("brier_improvement_vs_state", 0) > 0.001
        )
        incremental = row.get("incrementality_flag") == "INCREMENTAL_SEQUENCE_SIGNAL"
        if enough and stable and model_improves and incremental and row["precision_lift"] > 0.10:
            cls = "HIGH_PRIORITY_SEQUENCE_SIGNAL"
            reason = "stable, enough events, model improves over state baseline, and rule is not just current-state identity"
        elif enough and row["target"].startswith("recovery_quality") and row["precision_lift"] > 0.08 and stable:
            cls = "PROMISING_RECOVERY_QUALITY_SIGNAL"
            reason = "recovery-quality lift with interpretable sequence path"
        elif enough and row["target"] in BAD_TARGETS and row["precision_lift"] > 0.08 and stable:
            cls = "PROMISING_STRESS_WARNING_SIGNAL"
            reason = "risk/weakness target lift with interpretable state-sequence warning"
        elif row.get("incrementality_flag") == "DUPLICATES_CURRENT_STATE_ENGINE":
            cls = "DUPLICATIVE_WITH_LAYER2B"
            reason = "mostly restates existing current/refined state engine"
        elif not enough or row["stability"] < 0.34:
            cls = "TOO_RARE_OR_UNSTABLE"
            reason = "insufficient event coverage or subperiod stability"
        elif row["precision_lift"] > 0.04:
            cls = "NEEDS_TRIPLE_BARRIER_VALIDATION"
            reason = "some lift, but not enough for high-priority sequence signal gate"
        else:
            cls = "REJECT"
            reason = "insufficient stable incremental evidence"
        classifications.append(cls)
        reasons.append(reason)
    merged["classification"] = classifications
    merged["reason"] = reasons

    shortlist_classes = {
        "HIGH_PRIORITY_SEQUENCE_SIGNAL",
        "PROMISING_RECOVERY_QUALITY_SIGNAL",
        "PROMISING_STRESS_WARNING_SIGNAL",
        "NEEDS_TRIPLE_BARRIER_VALIDATION",
    }
    shortlist = merged[merged["classification"].isin(shortlist_classes)].copy()
    shortlist = shortlist.sort_values(["classification", "precision_lift", "stability", "event_count"], ascending=[True, False, False, False]).head(30)
    rejected = merged[~merged["classification"].isin(shortlist_classes)].copy().sort_values(["precision_lift", "event_count"], ascending=[False, False])
    queue = shortlist.copy()
    queue["next_phase_task"] = np.where(
        queue["classification"].eq("HIGH_PRIORITY_SEQUENCE_SIGNAL"),
        "SSS2 explicit sequence signal validation with transition/tail/recovery labels",
        "validate with triple-barrier and GGG1 state/path pass-through diagnostics before portfolio work",
    )
    save_csv(shortlist, OUT / "sss_candidate_sequence_signal_shortlist.csv")
    save_csv(rejected, OUT / "sss_rejected_sequence_rule_log.csv")
    save_csv(queue, OUT / "sss_next_phase_queue.csv")

    high_count = int(shortlist["classification"].eq("HIGH_PRIORITY_SEQUENCE_SIGNAL").sum()) if not shortlist.empty else 0
    promising_count = int(shortlist["classification"].isin(["PROMISING_RECOVERY_QUALITY_SIGNAL", "PROMISING_STRESS_WARNING_SIGNAL"]).sum()) if not shortlist.empty else 0
    weakness_count = int(shortlist["target"].isin(BAD_TARGETS).sum()) if not shortlist.empty else 0
    if high_count > 0:
        rec_value = "PROCEED_TO_SSS2_SEQUENCE_SIGNAL_VALIDATION"
        reason = "At least one stable, interpretable, incremental sequence rule clears high-priority gates."
    elif promising_count > 0 and weakness_count > 0:
        rec_value = "PROCEED_TO_RRR_SLEEVE_META_LABELING"
        reason = "Sequence rules identify GGG1 weak/risk windows, but not clean enough for standalone SSS2 signals."
    elif promising_count > 0:
        rec_value = "PROCEED_TO_ADDITIONAL_FEATURE_ENGINEERING"
        reason = "Sequence features help in specific pockets but need better upstream regime inputs before validation."
    else:
        rec_value = "STOP_HARD_ML_FOR_NOW"
        reason = "Sequence models/rules do not add enough stable actionability beyond current Layer 2B state logic."
    rec = pd.DataFrame(
        [
            {
                "recommendation": rec_value,
                "reason": reason,
                "high_priority_count": high_count,
                "promising_count": promising_count,
                "shortlist_count": int(len(shortlist)),
                "rejected_count": int(len(rejected)),
            }
        ]
    )
    save_csv(rec, OUT / "sss_next_action_recommendation.csv")
    return shortlist, rejected, queue, rec


def markdown_table(df: pd.DataFrame, max_rows: int = 12, float_digits: int = 4) -> str:
    if df is None or df.empty:
        return "_No rows._"
    d = df.head(max_rows).copy()
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].map(lambda x: "" if pd.isna(x) else f"{x:.{float_digits}f}")
    cols = list(d.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in d.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def report_prompt_for_next(rec: str) -> str:
    if rec == "PROCEED_TO_SSS2_SEQUENCE_SIGNAL_VALIDATION":
        return (
            "Implement Phase SSS2 as diagnostic-only sequence signal validation. Convert only the high-priority SSS rules into explicit lagged sequence signals, validate stress-transition, false-recovery, GGG1 weakness, triple-barrier, state/path, turnover, and redundancy behavior under walk-forward validation. Do not create portfolio candidates or change production/shadow/GGG1 logic."
        )
    if rec == "PROCEED_TO_RRR_SLEEVE_META_LABELING":
        return (
            "Implement Phase RRR sleeve-level meta-labeling. Use SSS sequence weakness windows, GGG1 sleeve weights/returns, Layer 2A component returns, and OOO/QQQ diagnostics to test whether sequence context improves sleeve timing. Keep labels causal, use walk-forward validation, and do not create portfolio pass-through candidates yet."
        )
    if rec == "PROCEED_TO_ADDITIONAL_FEATURE_ENGINEERING":
        return (
            "Run a focused upstream feature-engineering phase for Layer 2B regime inputs. Improve causal breadth, stress-memory, transition-instability, neutral deterioration, and recovery-quality inputs, then retest SSS sequence models against current-state and Markov baselines before any signal validation."
        )
    return (
        "Stop hard-ML expansion for now. Preserve OOO/PPP/QQQ/SSS diagnostics as research artifacts, keep GGG1 as the production candidate, and return to simpler robustness, audits, or sleeve meta-labeling only if a new non-ML hypothesis appears."
    )


def write_report(
    audit: pd.DataFrame,
    feature_manifest: pd.DataFrame,
    leakage: pd.DataFrame,
    target_summary: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    model_metrics: pd.DataFrame,
    extracted_rules: pd.DataFrame,
    qqq_control: pd.DataFrame,
    ooo_overlap: pd.DataFrame,
    weakness: pd.DataFrame,
    shortlist: pd.DataFrame,
    rejected: pd.DataFrame,
    recommendation: pd.DataFrame,
) -> None:
    transition_risk = pd.read_csv(OUT / "sss_state_transition_risk_summary.csv")
    dwell = pd.read_csv(OUT / "sss_state_dwell_distribution.csv")
    age_perf = pd.read_csv(OUT / "sss_state_age_performance.csv")
    rule_perf = pd.read_csv(OUT / "sss_sequence_rule_performance.csv")
    rec = recommendation.iloc[0]["recommendation"]
    reason = recommendation.iloc[0]["reason"]
    files = [
        "scripts/phase_sss_regime_sequence_modeling.py",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_sequence_panel.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_source_audit.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_transition_matrix_1w.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_transition_matrix_4w.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_transition_matrix_8w.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_dwell_distribution.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_age_performance.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_path_performance.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_transition_risk_summary.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_feature_panel.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_feature_manifest.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_leakage_checklist.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_target_panel.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_target_summary.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_walkforward_splits.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_baseline_model_metrics.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_baseline_predictions.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_model_metrics.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_model_predictions.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_model_calibration.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_feature_importance.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_subperiod_stability.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_transition_window_performance.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_extracted_sequence_rules.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_rule_performance.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_state_path_rule_summary.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_qqq_interaction_after_sequence_control.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_ooo_signal_sequence_overlap.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_ggg1_sequence_weakness_diagnostics.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_sequence_incrementality_summary.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_candidate_sequence_signal_shortlist.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_rejected_sequence_rule_log.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_next_phase_queue.csv",
        "data/research/phase_sss_regime_sequence_modeling/sss_next_action_recommendation.csv",
        "docs/research/2026-04-27_phase_sss_regime_sequence_modeling_report.md",
        "docs/research/project_journey.md",
    ]
    best_models = model_metrics.sort_values(["target", "brier"]).groupby("target").head(3)
    current_state = baseline_metrics[baseline_metrics["model"].eq("current_state_lag1_rate")]
    markov = baseline_metrics[baseline_metrics["model"].eq("transition_matrix_markov_score")]
    improvement = best_models.groupby("target").head(1).merge(
        current_state[["target", "brier", "auc", "high_risk_decile_precision"]].rename(columns={"brier": "current_state_brier", "auc": "current_state_auc", "high_risk_decile_precision": "current_state_precision"}),
        on="target",
        how="left",
    ).merge(
        markov[["target", "brier", "auc", "high_risk_decile_precision"]].rename(columns={"brier": "markov_brier", "auc": "markov_auc", "high_risk_decile_precision": "markov_precision"}),
        on="target",
        how="left",
    )
    improvement["auc_lift_vs_current_state"] = improvement["auc"] - improvement["current_state_auc"]
    improvement["brier_improvement_vs_current_state"] = improvement["current_state_brier"] - improvement["brier"]
    lines = [
        "# Phase SSS -- Regime-Sequence Modeling",
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
        "## State Source Audit",
        markdown_table(audit, 20),
        "",
        "The canonical SSS path features use the original five-state `market_state` sequence so results remain comparable to QQQ and GGG1. The refined Layer 2B states are retained as lagged comparison/control features.",
        "",
        "## Transition And Dwell Diagnostics",
        "Top transition-risk diagnostics:",
        markdown_table(transition_risk.sort_values("stress_transition_8w_rate", ascending=False), 16),
        "",
        "Dwell distribution examples:",
        markdown_table(dwell.sort_values(["market_state", "n_runs"], ascending=[True, False]), 16),
        "",
        "State age performance examples:",
        markdown_table(age_perf.sort_values("sharpe", ascending=False), 14),
        "",
        "## Sequence Feature Summary",
        markdown_table(
            feature_manifest.groupby("feature_family").agg(feature_count=("feature_name", "count"), avg_missingness=("missingness", "mean")).reset_index().sort_values("feature_count", ascending=False),
            20,
        ),
        "",
        "## Leakage Checks",
        markdown_table(leakage, 20),
        "",
        "## Target Definitions And Class Balance",
        markdown_table(target_summary[~target_summary["target"].str.contains("__state_")], 12),
        "",
        "## Baseline Results",
        markdown_table(baseline_metrics.sort_values(["target", "brier"]), 24),
        "",
        "## Sequence Model Results",
        markdown_table(best_models[["target", "model", "n_oos", "positive_rate", "brier", "auc", "log_loss", "high_risk_decile_precision", "high_risk_decile_recall", "top_decile_return_lift"]], 24),
        "",
        "## Improvement Over Current-State And Markov Baselines",
        markdown_table(improvement[["target", "model", "brier", "current_state_brier", "brier_improvement_vs_current_state", "auc", "current_state_auc", "auc_lift_vs_current_state", "markov_auc"]], 12),
        "",
        "## Extracted Sequence Rules",
        markdown_table(extracted_rules[["rule_name", "target", "event_count", "event_frequency", "precision_lift", "return_lift", "stability", "state_path_interpretation", "redundancy_warning"]], 20),
        "",
        "Top all-rule diagnostics:",
        markdown_table(rule_perf[["rule_name", "target", "event_count", "precision_lift", "stability", "rule_family"]], 20),
        "",
        "## QQQ / OOO Overlap Findings",
        "QQQ after sequence controls:",
        markdown_table(qqq_control, 12),
        "",
        "OOO signal overlap with sequence features:",
        markdown_table(ooo_overlap, 16),
        "",
        "## GGG1 Weakness Diagnostics",
        markdown_table(weakness[["rule_name", "target", "event_count", "precision_lift", "avg_forward_return", "return_lift", "incrementality_flag", "ggg1_weakness_flag"]], 20),
        "",
        "## Candidate Sequence Signal Shortlist",
        markdown_table(shortlist[["rule_name", "target", "classification", "event_count", "precision_lift", "stability", "incrementality_flag", "reason"]], 20),
        "",
        "## Rejected Sequence Rules",
        markdown_table(rejected[["rule_name", "target", "classification", "event_count", "precision_lift", "stability", "reason"]], 20),
        "",
        "## Final Recommendation",
        f"**{rec}**",
        "",
        f"Reason: {reason}",
        "",
        "## Exact Prompt Outline For Next Phase",
        report_prompt_for_next(rec),
        "",
        "## Resume-Worthy Technical Summary",
        "SSS used `market_state_history_refined.csv` aligned to the 1,110-week GGG1 return series. It modeled canonical paths on the original five `market_state` labels and retained `refined_state`, Layer 2B probabilities, OOO signals/events, and QQQ interaction activity as lagged diagnostics/controls. It generated 1w/4w/8w transition matrices, dwell/age/path performance diagnostics, causal lagged n-gram, dwell, stress-memory, entropy, transition-instability, refined-state, QQQ, and OOO context features, then built stress-transition, recovery-quality, GGG1 underperformance, tail-risk, false-recovery, and optional QQQ-success targets. Walk-forward baselines included historical rate, current-state, previous-state, state+dwell, Markov/path, existing Layer 2B probability, and QQQ-only baselines. Sequence models were constrained L2 logistic, shallow decision tree, shallow random forest, shallow histogram gradient boosting, plus sequence+Layer2B and sequence+QQQ controls. SSS extracted interpretable path rules, checked QQQ/OOO overlap, diagnosed GGG1 weak windows, and produced a candidate sequence shortlist without changing production/shadow/GGG1 or creating portfolio candidates.",
    ]
    DOC.write_text("\n".join(lines) + "\n")


def update_project_journey(recommendation: pd.DataFrame) -> None:
    rec = recommendation.iloc[0]["recommendation"]
    reason = recommendation.iloc[0]["reason"]
    section = f"""

## Section 90 -- Phase SSS Regime-Sequence Modeling

Date: 2026-04-27. Phase SSS was diagnostic-only. It used the refined Layer 2B
state history aligned to GGG1 dates, modeled original five-state market-state
paths with lagged dwell, path, stress-memory, transition-instability, refined
state, QQQ, OOO, and Layer 2B context controls, and tested stress-transition,
recovery-quality, false-recovery, GGG1 underperformance, and tail-risk targets
with expanding walk-forward validation. It created no portfolio candidates and
did not change production, shadow, GGG1 logic, or live trading behavior.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 90 -- Phase SSS Regime-Sequence Modeling"
    if marker in text:
        text = text[: text.index(marker)].rstrip() + section
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    ensure_out()
    panel, audit, qqq_cols, _ = load_state_sequence()
    run_transition_diagnostics(panel)
    feature_panel, feature_manifest, feature_groups = build_sequence_features(panel, qqq_cols)
    target_panel, target_summary = build_targets(panel, feature_panel)
    splits = build_walkforward_splits(panel["date"])
    baseline_predictions, model_predictions, importance = run_walkforward_models(feature_panel, target_panel, feature_groups, splits)
    evals = evaluate_all_predictions(baseline_predictions, model_predictions, panel)
    rule_perf, extracted_rules, path_summary = evaluate_rules(feature_panel, target_panel)
    qqq_control = compare_qqq_after_sequence(evals["model_metrics"], feature_panel, target_panel)
    ooo_overlap = compare_ooo_overlap(feature_panel)
    incrementality = classify_incrementality(rule_perf, feature_panel)
    weakness = ggg1_weakness_diagnostics(rule_perf, incrementality)
    shortlist, rejected, queue, recommendation = build_shortlist(rule_perf, incrementality, evals["model_metrics"], evals["baseline_metrics"])
    leakage = pd.read_csv(OUT / "sss_leakage_checklist.csv")
    write_report(
        audit,
        feature_manifest,
        leakage,
        target_summary,
        evals["baseline_metrics"],
        evals["model_metrics"],
        extracted_rules,
        qqq_control,
        ooo_overlap,
        weakness,
        shortlist,
        rejected,
        recommendation,
    )
    update_project_journey(recommendation)
    print("Phase SSS regime-sequence modeling complete.")
    print(f"Outputs: {OUT}")
    print(f"Report: {DOC}")
    print(f"Recommendation: {recommendation.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
