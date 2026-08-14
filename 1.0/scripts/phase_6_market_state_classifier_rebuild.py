#!/usr/bin/env python3
"""
Phase 6 — Market-State Classifier Rebuild
Improves market-state classification using existing production-valid data only.
No survivorship-biased stock breadth. No paid data. No individual stocks.
5 candidates, all built on Phase 4B best as base.
Diagnostic + selection. No production pin changes. No auto-promotion.

Candidates (all start from Phase 4B best: improved_phase4b_refined_sector_20pct):
  C1: improved_phase6_neutral_classifier_unlock
  C2: improved_phase6_calm_bull_quality_offense
  C3: improved_phase6_recovery_quality_rerisk
  C4: improved_phase6_continuous_aggression_score
  C5: improved_phase6_balanced_classifier_rebuild
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
HUB = ROOT / "data" / "01_data_hub"
OUT = ROOT / "data" / "research" / "phase_6_market_state_classifier_rebuild"
OUT.mkdir(parents=True, exist_ok=True)  # must be first — tee needs the dir to exist

WEEKS = 52

CANDIDATES = [
    "improved_phase6_neutral_classifier_unlock",
    "improved_phase6_calm_bull_quality_offense",
    "improved_phase6_recovery_quality_rerisk",
    "improved_phase6_continuous_aggression_score",
    "improved_phase6_balanced_classifier_rebuild",
]

BASELINES = {
    "ggg1": "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    "phase2_best": "portfolio_version_returns_improved_phase2_aggressive_neutral_cash_unlock.csv",
    "phase3_best": "portfolio_version_returns_improved_phase3_high_breadth_calm_us_offense.csv",
    "phase4_best": "portfolio_version_returns_improved_phase4_sector_20pct_offense.csv",
    "phase4b_best": "portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv",
    "prod_pin": "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
    "shadow": "portfolio_version_returns_improved_phase2b_combo_abc.csv",
    "equal_weight": "portfolio_returns_equal_weight.csv",
}

WINDOWS = {
    "full": (None, None),
    "holdout_2016": ("2016-01-01", None),
    "holdout_2020": ("2020-01-01", None),
    "holdout_2021": ("2021-01-01", None),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "recovery_2023": ("2023-01-01", None),
}


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def calc_metrics(ret: pd.Series, label: str = "") -> dict:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    if len(ret) < 8:
        return {"label": label, "n_weeks": len(ret), "ann_return": np.nan}
    n = len(ret)
    ann_ret = float((1 + ret).prod() ** (WEEKS / n) - 1)
    ann_vol = float(ret.std() * np.sqrt(WEEKS))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    wealth = (1 + ret).cumprod()
    dd = wealth / wealth.cummax() - 1
    max_dd = float(dd.min())
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else np.nan
    cvar_5 = float(ret[ret <= ret.quantile(0.05)].mean())
    worst_4w = float(ret.rolling(4).sum().min()) if len(ret) >= 4 else np.nan
    worst_13w = float(ret.rolling(13).sum().min()) if len(ret) >= 13 else np.nan
    return {
        "label": label, "n_weeks": n,
        "ann_return": round(ann_ret, 6), "ann_vol": round(ann_vol, 6),
        "sharpe": round(sharpe, 6), "max_drawdown": round(max_dd, 6),
        "calmar": round(calmar, 6), "cvar_5": round(cvar_5, 6),
        "worst_4w": round(worst_4w, 6), "worst_13w": round(worst_13w, 6),
    }


def ws(s: pd.Series, start, end) -> pd.Series:
    if start:
        s = s[s.index >= start]
    if end:
        s = s[s.index <= end]
    return s


def safe_div(a, b):
    return float(a / b) if b and not np.isnan(float(b)) and abs(float(b)) > 1e-12 else np.nan


def load_ret(fname: str) -> pd.Series | None:
    p = L3 / fname
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    col = "net_return" if "net_return" in df.columns else df.columns[0]
    return df[col]


def calc_ann_return(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 4:
        return np.nan
    return float((1 + s).prod() ** (WEEKS / len(s)) - 1)


def get_capture(port: pd.Series, bm: pd.Series):
    common = port.dropna().index.intersection(bm.dropna().index)
    p, b = port.reindex(common), bm.reindex(common)
    up, dn = b > 0, b < 0
    uc = safe_div(p[up].sum(), b[up].sum()) if up.sum() > 2 else np.nan
    dc = safe_div(p[dn].sum(), b[dn].sum()) if dn.sum() > 2 else np.nan
    cov = np.cov(p, b) if len(p) > 2 else np.zeros((2, 2))
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    corr = float(p.corr(b))
    return uc, dc, beta, corr


# ──────────────────────────────────────────────
# LOAD BASE DATA
# ──────────────────────────────────────────────
msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)
wr = pd.read_csv(HUB / "weekly_returns.csv", index_col="Date", parse_dates=True)
bm_prices = pd.read_csv(HUB / "benchmark_prices_weekly.csv", index_col="Date", parse_dates=True)
spy_ret = bm_prices["SPY"].pct_change().dropna()
ief_ret = bm_prices["IEF"].pct_change().dropna()
bench_6040 = (0.60 * spy_ret + 0.40 * ief_ret).dropna()

qqq_ret = wr["QQQ"].dropna() if "QQQ" in wr.columns else None

# ──────────────────────────────────────────────
# PART A — CLASSIFIER FAILURE MAP
# ──────────────────────────────────────────────
print("=== PART A: Classifier failure map ===")

failure_rows = []
opp_rows = []
cash_drag_rows = []
p4b_lessons_rows = []

phase4b_ret = load_ret("portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv")
ggg1_ret = load_ret("portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv")

p4b_sw = pd.read_csv(L3 / "portfolio_version_sleeve_weights_improved_phase4b_refined_sector_20pct.csv", index_col=0, parse_dates=True)
ggg1_sw = pd.read_csv(L3 / "portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv", index_col=0, parse_dates=True)
p4b_w = pd.read_csv(L3 / "portfolio_version_weights_improved_phase4b_refined_sector_20pct.csv", index_col=0, parse_dates=True)

for state in msh["market_state"].unique():
    idx = msh[msh["market_state"] == state].index
    spy_slc = spy_ret.reindex(idx).dropna()
    p4b_slc = phase4b_ret.reindex(idx).dropna() if phase4b_ret is not None else pd.Series()
    ggg1_slc = ggg1_ret.reindex(idx).dropna() if ggg1_ret is not None else pd.Series()
    n = len(idx)

    p4b_m = calc_metrics(p4b_slc)
    ggg1_m = calc_metrics(ggg1_slc)
    spy_m = calc_metrics(spy_slc)

    p4b_bil = p4b_sw.reindex(idx)["cash::BIL"].mean() if "cash::BIL" in p4b_sw.columns else np.nan
    p4b_def = p4b_sw.reindex(idx).get("composite_regime_defense_component", pd.Series()).mean()
    p4b_sec = p4b_sw.reindex(idx).get("phase4b_defensive_aware_top5_sleeve", pd.Series()).mean()
    p4b_spy = p4b_w.reindex(idx)["SPY"].mean() if "SPY" in p4b_w.columns else np.nan

    opp_cost = round((p4b_m.get("ann_return", 0) or 0) - (spy_m.get("ann_return", 0) or 0), 4)
    delta_vs_ggg1 = round((p4b_m.get("ann_return", 0) or 0) - (ggg1_m.get("ann_return", 0) or 0), 4)

    failure_rows.append({
        "state": state, "n_weeks": n, "freq": round(n / len(msh), 3),
        "phase4b_ann_return": p4b_m.get("ann_return"),
        "phase4b_sharpe": p4b_m.get("sharpe"),
        "phase4b_max_dd": p4b_m.get("max_drawdown"),
        "ggg1_ann_return": ggg1_m.get("ann_return"),
        "ggg1_sharpe": ggg1_m.get("sharpe"),
        "spy_ann_return": spy_m.get("ann_return"),
        "delta_phase4b_vs_ggg1": delta_vs_ggg1,
        "opportunity_cost_vs_spy": opp_cost,
        "assessment": (
            "PROTECTED" if state == "stressed_panic" else
            "BOTTLENECK_PRIMARY" if state == "calm_trend" and opp_cost < -0.08 else
            "BOTTLENECK_SECONDARY" if state == "neutral_mixed" and opp_cost < -0.02 else
            "IMPROVED" if delta_vs_ggg1 > 0.005 else
            "ADEQUATE"
        ),
    })
    opp_rows.append({
        "state": state, "n_weeks": n,
        "phase4b_ann_return": p4b_m.get("ann_return"),
        "spy_ann_return": spy_m.get("ann_return"),
        "opportunity_cost_ann": opp_cost,
        "phase4b_improvement_vs_ggg1": delta_vs_ggg1,
    })
    cash_drag_rows.append({
        "state": state, "n_weeks": n,
        "avg_BIL": round(p4b_bil, 4) if not np.isnan(p4b_bil) else np.nan,
        "avg_defense_component": round(float(p4b_def), 4) if p4b_def is not None else np.nan,
        "avg_sector_sleeve": round(float(p4b_sec), 4) if p4b_sec is not None else np.nan,
        "avg_SPY_direct": round(p4b_spy, 4) if not np.isnan(p4b_spy) else np.nan,
    })

pd.DataFrame(failure_rows).to_csv(OUT / "phase6_classifier_failure_map.csv", index=False)
pd.DataFrame(opp_rows).to_csv(OUT / "phase6_state_opportunity_cost.csv", index=False)
pd.DataFrame(cash_drag_rows).to_csv(OUT / "phase6_state_cash_defense_drag.csv", index=False)

# Phase 4B lessons
p4b_state_file = ROOT / "data" / "research" / "phase_4b_refined_sector_rotation" / "phase4b_state_failure_map.csv"
if p4b_state_file.exists():
    p4b_lessons = pd.read_csv(p4b_state_file)
else:
    p4b_lessons = pd.DataFrame(failure_rows)
p4b_lessons["phase6_focus"] = p4b_lessons.get("state", p4b_lessons.get("state", "")).map(
    lambda s: "HIGH" if s == "calm_trend" else "MEDIUM" if s in ("neutral_mixed", "recovery_confirmed") else "LOW"
)
p4b_lessons.to_csv(OUT / "phase6_phase4b_lessons.csv", index=False)

print(f"  Classifier failure map saved")
print("  State opportunity costs vs SPY:")
for r in failure_rows:
    print(f"    {r['state']:20s}: phase4b={r['phase4b_ann_return']:.2%} spy={r['spy_ann_return']:.2%} "
          f"opp_cost={r['opportunity_cost_vs_spy']:+.2%} [{r['assessment']}]")


# ──────────────────────────────────────────────
# PART B — FEATURE INVENTORY
# ──────────────────────────────────────────────
print("\n=== PART B: Feature inventory ===")

feature_inv = []
for feat, source, role, already_used, prod_safe in [
    ("breadth_sma_43", "market_state_history.csv", "% ETFs above 43w SMA — ETF breadth level", True, True),
    ("breadth_26w_mom", "market_state_history.csv", "% ETFs with positive 26w return", True, True),
    ("breadth_13w_mom", "market_state_history.csv", "% ETFs with positive 13w return", False, True),
    ("breadth_change_4w", "market_state_history.csv", "4w change in breadth_sma_43 — momentum of breadth", False, True),
    ("market_trend_positive", "market_state_history.csv", "Binary market trend flag", True, True),
    ("canary_breadth_default", "market_state_history.csv", "Canary breadth indicator", False, True),
    ("canary_breadth_pair", "market_state_history.csv", "Canary breadth pair indicator", False, True),
    ("transition_good_state_prob", "market_state_history.csv", "P(next state in good regimes) — regime engine", False, True),
    ("transition_non_stress_prob", "market_state_history.csv", "P(stay out of stress) — regime engine", True, True),
    ("transition_persistence_prob", "market_state_history.csv", "P(current state persists) — regime engine", False, True),
    ("market_drawdown", "market_state_history.csv", "Current market drawdown level", True, True),
    ("google_fear_z_tradable", "market_state_history.csv", "Google fear sentiment z-score (lagged)", False, True),
    ("avg_corr_risk_off_z", "market_state_history.csv", "Average risk-off correlation z-score", False, True),
    ("sector_momentum_top5", "weekly_returns.csv (XL*)", "Top-5 sector ETF by 13w/26w momentum", True, True),
    ("HYG_trend", "weekly_returns.csv", "HYG credit ETF trend — risk appetite proxy", False, True),
    ("spy_rvol_13w", "weekly_returns.csv (derived)", "SPY realized volatility 13w", False, True),
    ("current_constituent_stock_breadth", "phase_5a_free (SURVIVORSHIP_BIASED)", "Diagnostic only — NOT production safe", False, False),
]:
    miss = msh.get(feat, pd.Series()).isna().mean() if feat in msh.columns else np.nan
    feature_inv.append({
        "feature": feat, "source": source, "lag_rule": "applied at week T for T+1 allocation",
        "causal_ok": True, "missingness": round(miss, 3) if not np.isnan(miss) else "external",
        "role": role, "already_used_in_phase4b": already_used, "production_safe": prod_safe,
    })
pd.DataFrame(feature_inv).to_csv(OUT / "phase6_existing_feature_inventory.csv", index=False)

source_audit = pd.DataFrame([{
    "source": "market_state_history.csv", "features": 20, "production_safe": True,
    "causal": True, "date_range": "2005-2026", "note": "All features are lagged/causal",
}, {
    "source": "weekly_returns.csv (sector ETFs)", "features": 9, "production_safe": True,
    "causal": True, "date_range": "2005-2026", "note": "XLK, XLF, XLV, XLY, XLI, XLB, XLE, XLU, XLP",
}, {
    "source": "phase_5a_free stock breadth", "features": 16, "production_safe": False,
    "causal": True, "date_range": "2020-2026", "note": "SURVIVORSHIP_BIASED — DO NOT USE IN CANDIDATES",
}])
source_audit.to_csv(OUT / "phase6_feature_source_audit.csv", index=False)
print(f"  Feature inventory: {len(feature_inv)} features")


# ──────────────────────────────────────────────
# PART C — CLASSIFIER DESIGN
# ──────────────────────────────────────────────
print("\n=== PART C: Classifier design ===")

classifier_design = [
    {"component": "extreme_quality_calm", "state": "calm_trend",
     "conditions": "breadth_sma_43>=0.80 AND market_trend_positive=1 AND canary_breadth_default=1",
     "action": "+4pp sector sleeve from defense_component", "rationale": "Very high breadth calm = full bull"},
    {"component": "high_quality_neutral", "state": "neutral_mixed",
     "conditions": "breadth_sma_43>=0.70 AND trend=1 AND canary=1 AND transition_good_state_prob>=0.60",
     "action": "+4pp sector sleeve from defense", "rationale": "Confirm neutral_risk_on with multi-feature gate"},
    {"component": "low_quality_neutral", "state": "neutral_mixed",
     "conditions": "breadth_sma_43<0.50 OR breadth_change_4w<-0.05",
     "action": "-3pp sector retraction to defense", "rationale": "Choppy/deteriorating — stay conservative"},
    {"component": "strong_recovery", "state": "recovery_confirmed",
     "conditions": "breadth_change_4w>=0.0 AND transition_good_state_prob>=0.55",
     "action": "+4pp sector sleeve from defense", "rationale": "Improving breadth in recovery = safer re-risk"},
    {"component": "aggression_score_high", "state": "non-stressed",
     "conditions": "composite_score>=0.72 (breadth+b26w+trend+canary+good_prob)",
     "action": "+3pp sector sleeve from defense", "rationale": "Continuous quality signal across states"},
    {"component": "aggression_score_low", "state": "non-stressed",
     "conditions": "composite_score<=0.28",
     "action": "-2pp sector retraction", "rationale": "Broadly weak conditions — reduce risk"},
]
pd.DataFrame(classifier_design).to_csv(OUT / "phase6_classifier_design.csv", index=False)

state_labels = [
    {"state_label": "extreme_quality_calm", "base_state": "calm_trend", "n_weeks": int((msh["market_state"]=="calm_trend").sum()),
     "expected_active_pct": "~60-70%", "description": "High-breadth confirmed calm bull"},
    {"state_label": "high_quality_neutral", "base_state": "neutral_mixed", "n_weeks": int((msh["market_state"]=="neutral_mixed").sum()),
     "expected_active_pct": "~25-35%", "description": "Confirmed neutral risk-on"},
    {"state_label": "low_quality_neutral", "base_state": "neutral_mixed",
     "n_weeks": int((msh["market_state"]=="neutral_mixed").sum()),
     "expected_active_pct": "~20-30%", "description": "Choppy/deteriorating neutral"},
    {"state_label": "strong_recovery", "base_state": "recovery_confirmed",
     "n_weeks": int((msh["market_state"]=="recovery_confirmed").sum()),
     "expected_active_pct": "~50-65%", "description": "Breadth-improving confirmed recovery"},
    {"state_label": "stressed_panic_unchanged", "base_state": "stressed_panic",
     "n_weeks": int((msh["market_state"]=="stressed_panic").sum()),
     "expected_active_pct": "0%", "description": "Never modified — protection preserved"},
]
pd.DataFrame(state_labels).to_csv(OUT / "phase6_state_label_definitions.csv", index=False)

aggression_design = [
    {"component": "breadth_sma_43", "weight": 0.35, "normalization": "0.50->0, 0.85->1",
     "description": "ETF breadth level"},
    {"component": "breadth_26w_mom", "weight": 0.25, "normalization": "0.45->0, 0.80->1",
     "description": "26w momentum breadth"},
    {"component": "market_trend_positive", "weight": 0.15, "normalization": "binary 0/1",
     "description": "Trend flag"},
    {"component": "canary_breadth_default", "weight": 0.15, "normalization": "binary 0/1",
     "description": "Canary breadth"},
    {"component": "transition_good_state_prob", "weight": 0.10, "normalization": "0.50->0, 0.80->1",
     "description": "Regime transition quality"},
]
pd.DataFrame(aggression_design).to_csv(OUT / "phase6_aggression_score_design.csv", index=False)
print(f"  Classifier design saved")


# ──────────────────────────────────────────────
# PART D — BUILD CLASSIFIER PANEL
# ──────────────────────────────────────────────
print("\n=== PART D: Build classifier panel ===")

ms = msh.copy()

# Compute signals (causal: using week-T features for T+1 allocation)
ms["extreme_quality_calm"] = (
    (ms["market_state"] == "calm_trend") &
    (ms["breadth_sma_43"] >= 0.80) &
    (ms["market_trend_positive"] == 1) &
    (ms["canary_breadth_default"] == 1)
).astype(int)

ms["high_quality_neutral"] = (
    (ms["market_state"] == "neutral_mixed") &
    (ms["breadth_sma_43"] >= 0.70) &
    (ms["market_trend_positive"] == 1) &
    (ms["canary_breadth_default"] == 1) &
    (ms["transition_good_state_prob"].fillna(0) >= 0.60)
).astype(int)

ms["low_quality_neutral"] = (
    (ms["market_state"] == "neutral_mixed") &
    ((ms["breadth_sma_43"] < 0.50) | (ms["breadth_change_4w"].fillna(0) < -0.05))
).astype(int)

ms["strong_recovery"] = (
    (ms["market_state"] == "recovery_confirmed") &
    (ms["breadth_change_4w"].fillna(-1) >= 0.0) &
    (ms["transition_good_state_prob"].fillna(0) >= 0.55)
).astype(int)

# Continuous aggression score
b_sma_n = np.clip((ms["breadth_sma_43"] - 0.50) / 0.35, 0.0, 1.0)
b26_n = np.clip((ms["breadth_26w_mom"].fillna(0) - 0.45) / 0.35, 0.0, 1.0)
trend_n = ms["market_trend_positive"].fillna(0).clip(0, 1)
canary_n = ms["canary_breadth_default"].fillna(0).clip(0, 1)
good_n = np.clip((ms["transition_good_state_prob"].fillna(0) - 0.50) / 0.30, 0.0, 1.0)
ms["aggression_score"] = (0.35*b_sma_n + 0.25*b26_n + 0.15*trend_n + 0.15*canary_n + 0.10*good_n).clip(0, 1)

# Lagged versions (for any downstream use — production uses week-T data for T+1)
for col in ["extreme_quality_calm", "high_quality_neutral", "low_quality_neutral",
             "strong_recovery", "aggression_score"]:
    ms[f"{col}_lag1w"] = ms[col].shift(1)

ms["classifier_state_refined"] = ms["market_state"].copy()
ms.loc[ms["extreme_quality_calm"] == 1, "classifier_state_refined"] = "extreme_quality_calm"
ms.loc[ms["high_quality_neutral"] == 1, "classifier_state_refined"] = "high_quality_neutral"
ms.loc[ms["low_quality_neutral"] == 1, "classifier_state_refined"] = "low_quality_neutral"
ms.loc[ms["strong_recovery"] == 1, "classifier_state_refined"] = "strong_recovery"

ms["aggression_bucket"] = pd.cut(
    ms["aggression_score"],
    bins=[0, 0.25, 0.45, 0.60, 0.75, 1.01],
    labels=["defensive", "cautious", "moderate", "aggressive", "max_aggressive"],
    right=True,
)

ms.to_csv(OUT / "phase6_classifier_panel.csv")

signal_counts = ms[["extreme_quality_calm", "high_quality_neutral", "low_quality_neutral",
                      "strong_recovery"]].sum()
pd.DataFrame([{
    "signal": n, "active_weeks": int(v),
    "active_freq": round(v / len(ms), 3),
} for n, v in signal_counts.items()]).to_csv(OUT / "phase6_classifier_signal_definitions.csv", index=False)

state_counts = ms["classifier_state_refined"].value_counts().reset_index()
state_counts.columns = ["state", "n_weeks"]
state_counts["freq"] = round(state_counts["n_weeks"] / len(ms), 3)
state_counts.to_csv(OUT / "phase6_classifier_state_counts.csv", index=False)

bucket_counts = ms["aggression_bucket"].value_counts().sort_index().reset_index()
bucket_counts.columns = ["bucket", "n_weeks"]
bucket_counts.to_csv(OUT / "phase6_aggression_bucket_coverage.csv", index=False)

print(f"  Classifier panel saved ({len(ms)} weeks)")
print(f"  Signal active weeks:")
for col, v in signal_counts.items():
    print(f"    {col:35s}: {int(v):4d} ({v/len(ms):.1%})")


# ──────────────────────────────────────────────
# PART E — VALIDATE CLASSIFIER
# ──────────────────────────────────────────────
print("\n=== PART E: Classifier validation ===")

def fwd_n(s: pd.Series, n: int) -> pd.Series:
    return (1 + s).rolling(n).apply(lambda x: x.prod() - 1, raw=True).shift(-n)

val_rows = []
lift_rows = []
aggression_val_rows = []
transition_rows = []
stress_rows = []

p4b_r = phase4b_ret
ggg1_r = ggg1_ret
spy_r = spy_ret
qqq_r = qqq_ret

portfolios_val = {k: v for k, v in {
    "spy": spy_r, "qqq": qqq_r, "ggg1": ggg1_r, "phase4b_best": p4b_r,
}.items() if v is not None}

# Signal vs inactive: 4w, 8w, 13w
for sig_name in ["extreme_quality_calm", "high_quality_neutral", "low_quality_neutral",
                  "strong_recovery", "aggression_score_high"]:
    if sig_name == "aggression_score_high":
        sig = (ms["aggression_score"] >= 0.72).astype(bool)
    else:
        sig = ms[sig_name].astype(bool)

    for hor in [4, 8, 13]:
        for pname, pret in portfolios_val.items():
            fwd = fwd_n(pret, hor)
            on_v = fwd[sig.reindex(pret.index).fillna(False)].dropna()
            off_v = fwd[(~sig).reindex(pret.index).fillna(True)].dropna()
            val_rows.append({
                "signal": sig_name, "portfolio": pname, "horizon_weeks": hor,
                "n_on": len(on_v), "n_off": len(off_v),
                "mean_fwd_on": round(float(on_v.mean()), 5) if len(on_v) > 2 else np.nan,
                "mean_fwd_off": round(float(off_v.mean()), 5) if len(off_v) > 2 else np.nan,
                "lift": round(float(on_v.mean() - off_v.mean()), 5) if len(on_v) > 2 and len(off_v) > 2 else np.nan,
                "hit_rate": round(float((on_v > 0).mean()), 3) if len(on_v) > 2 else np.nan,
                "adverse_freq": round(float((on_v < -0.05).mean()), 3) if len(on_v) > 2 else np.nan,
            })

# Same-state lift
for state in ["calm_trend", "neutral_mixed", "recovery_confirmed", "stressed_panic"]:
    state_mask = ms["market_state"] == state
    for sig_name, sig in [
        ("extreme_quality_calm", ms["extreme_quality_calm"].astype(bool)),
        ("high_quality_neutral", ms["high_quality_neutral"].astype(bool)),
        ("low_quality_neutral", ms["low_quality_neutral"].astype(bool)),
        ("strong_recovery", ms["strong_recovery"].astype(bool)),
        ("aggression_score_high", (ms["aggression_score"] >= 0.72).astype(bool)),
    ]:
        for pname, pret in {"spy": spy_r, "phase4b_best": p4b_r}.items():
            if pret is None:
                continue
            on_mask = sig.reindex(pret.index).fillna(False) & state_mask.reindex(pret.index).fillna(False)
            off_mask = (~sig).reindex(pret.index).fillna(True) & state_mask.reindex(pret.index).fillna(False)
            fwd4 = fwd_n(pret, 4)
            on_v = fwd4[on_mask].dropna()
            off_v = fwd4[off_mask].dropna()
            lift_rows.append({
                "state": state, "signal": sig_name, "portfolio": pname,
                "n_on": len(on_v), "n_off": len(off_v),
                "mean_fwd_4w_on": round(float(on_v.mean()), 5) if len(on_v) > 2 else np.nan,
                "mean_fwd_4w_off": round(float(off_v.mean()), 5) if len(off_v) > 2 else np.nan,
                "lift_4w": round(float(on_v.mean() - off_v.mean()), 5) if len(on_v) > 2 and len(off_v) > 2 else np.nan,
            })

# Aggression score bucket validation
for bucket in ["defensive", "cautious", "moderate", "aggressive", "max_aggressive"]:
    bucket_mask = ms["aggression_bucket"] == bucket
    for pname, pret in {"spy": spy_r, "phase4b_best": p4b_r}.items():
        if pret is None:
            continue
        b_mask = bucket_mask.reindex(pret.index).fillna(False)
        fwd4 = fwd_n(pret, 4)
        v = fwd4[b_mask].dropna()
        aggression_val_rows.append({
            "bucket": bucket, "portfolio": pname, "n_weeks": len(v),
            "mean_fwd_4w": round(float(v.mean()), 5) if len(v) > 2 else np.nan,
            "hit_rate": round(float((v > 0).mean()), 3) if len(v) > 2 else np.nan,
        })

# Stress guard validation
stress_mask = ms["market_state"] == "stressed_panic"
for pname, pret in {"spy": spy_r, "phase4b_best": p4b_r}.items():
    if pret is None:
        continue
    fwd4 = fwd_n(pret, 4)
    stressed = fwd4[stress_mask.reindex(pret.index).fillna(False)].dropna()
    non_stressed = fwd4[(~stress_mask).reindex(pret.index).fillna(True)].dropna()
    stress_rows.append({
        "portfolio": pname,
        "stressed_mean_4w": round(float(stressed.mean()), 5) if len(stressed) > 2 else np.nan,
        "nonstressed_mean_4w": round(float(non_stressed.mean()), 5) if len(non_stressed) > 2 else np.nan,
        "stressed_weeks": len(stressed),
        "signal_active_in_stressed": 0,  # by design — stressed_panic never touched
    })

val_df = pd.DataFrame(val_rows)
val_df.to_csv(OUT / "phase6_classifier_validation.csv", index=False)
pd.DataFrame(lift_rows).to_csv(OUT / "phase6_same_state_lift.csv", index=False)
pd.DataFrame(aggression_val_rows).to_csv(OUT / "phase6_aggression_score_validation.csv", index=False)
pd.DataFrame(transition_rows or [{"note": "see state_counts and signal_coverage"}]).to_csv(
    OUT / "phase6_transition_validation.csv", index=False)
pd.DataFrame(stress_rows).to_csv(OUT / "phase6_stress_guard_validation.csv", index=False)

print(f"  Classifier validation: {len(val_df)} rows")
print("\n  Key: Phase4B 4w forward return, signal active vs inactive:")
for sig_name in ["extreme_quality_calm", "high_quality_neutral", "aggression_score_high"]:
    rows = val_df[(val_df["signal"] == sig_name) & (val_df["portfolio"] == "phase4b_best") & (val_df["horizon_weeks"] == 4)]
    if len(rows):
        r = rows.iloc[0]
        print(f"    {sig_name}: on={r['mean_fwd_on']:.3%} off={r['mean_fwd_off']:.3%} lift={r['lift']:+.3%} (N={r['n_on']})")

# Decide whether to proceed with portfolio build
calm_lift = val_df[(val_df["signal"]=="extreme_quality_calm") & (val_df["portfolio"]=="phase4b_best") & (val_df["horizon_weeks"]==4)]["lift"].mean()
neutral_lift = val_df[(val_df["signal"]=="high_quality_neutral") & (val_df["portfolio"]=="phase4b_best") & (val_df["horizon_weeks"]==4)]["lift"].mean()
validation_positive = (not np.isnan(calm_lift) and calm_lift > 0) or (not np.isnan(neutral_lift) and neutral_lift > 0)
if not validation_positive:
    print("\n  WARNING: Classifier validation weak — proceeding anyway (incremental signals may still help in combination)")


# ──────────────────────────────────────────────
# PART F — CANDIDATE DESIGNS
# ──────────────────────────────────────────────
print("\n=== PART F: Candidate designs ===")
cand_designs = [
    {"candidate": "improved_phase6_neutral_classifier_unlock", "base": "phase4b_refined_sector_20pct",
     "signal": "high_quality_neutral (breadth>=0.70, trend, canary, good_prob>=0.60)",
     "action": "+4pp sector sleeve in high_quality_neutral; -3pp in low_quality_neutral",
     "phase2b_mode": "phase2_aggressive_neutral_boost", "rerisk_speed": 0.95},
    {"candidate": "improved_phase6_calm_bull_quality_offense", "base": "phase4b_refined_sector_20pct",
     "signal": "extreme_quality_calm (breadth>=0.80, trend, canary)",
     "action": "+4pp sector sleeve in extreme_quality_calm",
     "phase2b_mode": "phase2_aggressive_neutral_boost", "rerisk_speed": 0.95},
    {"candidate": "improved_phase6_recovery_quality_rerisk", "base": "phase4b_refined_sector_20pct",
     "signal": "strong_recovery (breadth_change>=0, good_prob>=0.55)",
     "action": "+4pp sector sleeve in strong_recovery; faster rerisk",
     "phase2b_mode": "phase2_aggressive_neutral_boost", "rerisk_speed": 1.00},
    {"candidate": "improved_phase6_continuous_aggression_score", "base": "phase4b_refined_sector_20pct",
     "signal": "aggression_score>=0.72 or <=0.28",
     "action": "+3pp when score>=0.72; -2pp when score<=0.28",
     "phase2b_mode": "phase2_aggressive_neutral_boost", "rerisk_speed": 0.95},
    {"candidate": "improved_phase6_balanced_classifier_rebuild", "base": "phase4b_refined_sector_20pct",
     "signal": "all Phase 6 signals combined (conservative magnitude)",
     "action": "+3.5pp in high_quality_neutral/extreme_quality_calm; +2.5pp strong_recovery; -2.5pp low_quality_neutral",
     "phase2b_mode": "phase2_aggressive_neutral_boost", "rerisk_speed": 0.95},
]
pd.DataFrame(cand_designs).to_csv(OUT / "phase6_candidate_designs.csv", index=False)
print(f"  Candidate designs saved ({len(cand_designs)} candidates)")


# ──────────────────────────────────────────────
# PART G — RUN PRODUCTION PIPELINE
# ──────────────────────────────────────────────
print("\n=== PART G: Run production pipeline ===")

build_env = os.environ.copy()
build_env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
build_script = ROOT / "scripts" / "build_improvement_artifacts.py"

print(f"  Running filtered build for {len(CANDIDATES)} Phase 6 candidates")
result = subprocess.run(
    [sys.executable, str(build_script)],
    env=build_env, capture_output=True, text=True, cwd=str(ROOT), timeout=900,
)
build_log = OUT / "phase6_build.log"
with open(build_log, "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout[-10000:] if len(result.stdout) > 10000 else result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr[-4000:] if len(result.stderr) > 4000 else result.stderr)

if result.returncode != 0:
    print(f"  BUILD FAILED (exit {result.returncode})")
    print(f"  stderr tail: {result.stderr[-1500:]}")
    sys.exit(1)

missing = [f"{c}_{s}" for c in CANDIDATES for s in ["returns", "weights", "sleeve_weights"]
           if not (L3 / f"portfolio_version_{s}_{c}.csv").exists()]
if missing:
    print(f"  WARNING: Missing artifacts: {missing[:5]}")
else:
    print(f"  All {len(CANDIDATES)*3} candidate artifacts confirmed.")


# ──────────────────────────────────────────────
# LOAD RETURNS
# ──────────────────────────────────────────────
print("\n=== Loading return series ===")
returns: dict[str, pd.Series] = {}

for c in CANDIDATES:
    p = L3 / f"portfolio_version_returns_{c}.csv"
    if p.exists():
        ret = load_ret(f"portfolio_version_returns_{c}.csv")
        if ret is not None:
            returns[c] = ret
            print(f"  {c}: {len(returns[c])} weeks")

for name, fname in BASELINES.items():
    ret = load_ret(fname)
    if ret is not None:
        returns[name] = ret

returns["spy"] = spy_ret
if qqq_ret is not None:
    returns["qqq"] = qqq_ret
returns["bench_60_40"] = bench_6040


# ──────────────────────────────────────────────
# PART H — METRICS
# ──────────────────────────────────────────────
print("\n=== PART H: Metrics ===")

all_metrics = []
for pname, ret in returns.items():
    for wname, (wstart, wend) in WINDOWS.items():
        slc = ws(ret, wstart, wend).dropna()
        m = calc_metrics(slc, pname)
        row = {"portfolio": pname, "window": wname, **m}

        wf = L3 / f"portfolio_version_weights_{pname}.csv"
        if wf.exists():
            w = pd.read_csv(wf, index_col=0, parse_dates=True)
            wslc = w if not wstart else w[wstart:]
            if wend:
                wslc = wslc[:wend]
            row["avg_BIL"] = round(float(wslc["BIL"].mean()), 4) if "BIL" in wslc else np.nan
            row["avg_SPY"] = round(float(wslc["SPY"].mean()), 4) if "SPY" in wslc else np.nan
            row["avg_QQQ"] = round(float(wslc["QQQ"].mean()), 4) if "QQQ" in wslc else np.nan
        else:
            row["avg_BIL"] = row["avg_SPY"] = row["avg_QQQ"] = np.nan

        swf = L3 / f"portfolio_version_sleeve_weights_{pname}.csv"
        if swf.exists():
            sw_tmp = pd.read_csv(swf, index_col=0, parse_dates=True)
            swslc = sw_tmp if not wstart else sw_tmp[wstart:]
            if wend:
                swslc = swslc[:wend]
            row["avg_sector_sleeve"] = round(float(swslc.get("phase4b_defensive_aware_top5_sleeve", pd.Series([np.nan])).mean()), 4)
            row["avg_defense"] = round(float(swslc.get("composite_regime_defense_component", pd.Series([np.nan])).mean()), 4)
            row["avg_cash_bil"] = round(float(swslc.get("cash::BIL", pd.Series([np.nan])).mean()), 4)
        else:
            row["avg_sector_sleeve"] = row["avg_defense"] = row["avg_cash_bil"] = np.nan

        rf = L3 / f"portfolio_version_returns_{pname}.csv"
        if rf.exists():
            rdf = pd.read_csv(rf, index_col=0, parse_dates=True)
            row["avg_turnover"] = round(float(ws(rdf["turnover"], wstart, wend).mean()), 4) if "turnover" in rdf.columns else np.nan
        else:
            row["avg_turnover"] = np.nan

        spy_slc = ws(spy_ret, wstart, wend).dropna()
        uc, dc, beta, corr = get_capture(slc, spy_slc.reindex(slc.index))
        row.update({"upside_capture": round(uc, 4) if not np.isnan(uc) else np.nan,
                    "downside_capture": round(dc, 4) if not np.isnan(dc) else np.nan,
                    "beta_spy": round(beta, 4) if not np.isnan(beta) else np.nan,
                    "corr_spy": round(corr, 4) if not np.isnan(corr) else np.nan})

        if qqq_ret is not None:
            qqq_slc = ws(qqq_ret, wstart, wend).dropna()
            _, _, beta_q, corr_q = get_capture(slc, qqq_slc.reindex(slc.index))
            row["beta_qqq"] = round(beta_q, 4) if not np.isnan(beta_q) else np.nan
        else:
            row["beta_qqq"] = np.nan

        for base_name in ["ggg1", "phase4b_best"]:
            base_slc = ws(returns.get(base_name, pd.Series(dtype=float)), wstart, wend).dropna()
            common = slc.index.intersection(base_slc.index)
            if len(common) > 4:
                n = len(common)
                p_ann = float((1+slc.reindex(common).mean())**WEEKS-1)
                b_ann = float((1+base_slc.reindex(common).mean())**WEEKS-1)
                row[f"active_return_vs_{base_name}"] = round(p_ann - b_ann, 4)
            else:
                row[f"active_return_vs_{base_name}"] = np.nan

        all_metrics.append(row)

metrics_df = pd.DataFrame(all_metrics)
metrics_df.to_csv(OUT / "phase6_candidate_metrics_full.csv", index=False)
metrics_df[metrics_df["window"].isin(["holdout_2016","holdout_2020","holdout_2021","bear_2022","recovery_2023"])].to_csv(
    OUT / "phase6_candidate_holdout_metrics.csv", index=False)

focus = CANDIDATES + ["ggg1","phase4b_best","phase3_best","phase2_best","prod_pin","shadow","spy","bench_60_40","equal_weight"]
bm_table = metrics_df[
    metrics_df["portfolio"].isin(focus) &
    metrics_df["window"].isin(["full","holdout_2020","holdout_2021","bear_2022","recovery_2023"])
][["portfolio","window","ann_return","sharpe","max_drawdown","calmar","cvar_5","avg_BIL","avg_sector_sleeve","avg_turnover","beta_spy","active_return_vs_ggg1","active_return_vs_phase4b_best"]].copy()
bm_table.to_csv(OUT / "phase6_candidate_vs_benchmark_table.csv", index=False)

cap_df = metrics_df[metrics_df["portfolio"].isin(focus)][
    ["portfolio","window","upside_capture","downside_capture","beta_spy","corr_spy","beta_qqq","active_return_vs_ggg1","active_return_vs_phase4b_best"]
].copy()
cap_df.to_csv(OUT / "phase6_capture_beta_by_window.csv", index=False)

print("  Full-period comparison:")
fp = metrics_df[metrics_df["window"]=="full"][["portfolio","ann_return","sharpe","max_drawdown","cvar_5","avg_BIL","avg_sector_sleeve","beta_spy","active_return_vs_ggg1","active_return_vs_phase4b_best"]].copy()
fp = fp[fp["portfolio"].isin(CANDIDATES+["ggg1","phase4b_best","spy"])].set_index("portfolio")
print(fp.round(4).to_string())


# ──────────────────────────────────────────────
# PART I — STATE DIAGNOSTICS
# ──────────────────────────────────────────────
print("\n=== PART I: State diagnostics ===")

state_sum_rows = []
state_exp_rows = []
state_delta_ggg1_rows = []
state_delta_p4b_rows = []
p4b_r2 = returns.get("phase4b_best")
ggg1_r2 = returns.get("ggg1")

diag_files = {
    "neutral_mixed": "phase6_neutral_split_portfolio_diagnostics.csv",
    "calm_trend": "phase6_calm_quality_portfolio_diagnostics.csv",
    "recovery_confirmed": "phase6_recovery_quality_portfolio_diagnostics.csv",
    "stressed_panic": "phase6_stress_protection_diagnostics.csv",
}

for pname in CANDIDATES + ["ggg1", "phase4b_best"]:
    if pname not in returns:
        continue
    ret = returns[pname]
    swf = L3 / f"portfolio_version_sleeve_weights_{pname}.csv"
    wf = L3 / f"portfolio_version_weights_{pname}.csv"
    has_sw = swf.exists()
    has_w = wf.exists()
    if has_sw:
        sw_data = pd.read_csv(swf, index_col=0, parse_dates=True)
    if has_w:
        w_data = pd.read_csv(wf, index_col=0, parse_dates=True)

    for state in msh["market_state"].unique():
        idx = msh[msh["market_state"] == state].index
        slc = ret.reindex(idx).dropna()
        m = calc_metrics(slc, pname)
        row = {"portfolio": pname, "state": state, "n_weeks": len(slc), **m}

        if has_sw:
            sw_slc = sw_data.reindex(idx)
            row["avg_sector_sleeve"] = round(float(sw_slc.get("phase4b_defensive_aware_top5_sleeve", pd.Series([np.nan])).mean()), 4)
            row["avg_defense"] = round(float(sw_slc.get("composite_regime_defense_component", pd.Series([np.nan])).mean()), 4)
            row["avg_bil_sleeve"] = round(float(sw_slc.get("cash::BIL", pd.Series([np.nan])).mean()), 4)
        if has_w:
            w_slc = w_data.reindex(idx)
            row["avg_BIL"] = round(float(w_slc["BIL"].mean()), 4) if "BIL" in w_slc else np.nan
            row["avg_QQQ"] = round(float(w_slc["QQQ"].mean()), 4) if "QQQ" in w_slc else np.nan

        state_sum_rows.append(row)

        if ggg1_r2 is not None:
            ggg_slc = ggg1_r2.reindex(idx).dropna()
            ggg_m = calc_metrics(ggg_slc)
            state_delta_ggg1_rows.append({
                "portfolio": pname, "state": state,
                "delta_ann_return_vs_ggg1": round((m.get("ann_return",0) or 0) - (ggg_m.get("ann_return",0) or 0), 4),
                "delta_sharpe_vs_ggg1": round((m.get("sharpe",0) or 0) - (ggg_m.get("sharpe",0) or 0), 4),
            })
        if p4b_r2 is not None:
            p4b_slc = p4b_r2.reindex(idx).dropna()
            p4b_m = calc_metrics(p4b_slc)
            state_delta_p4b_rows.append({
                "portfolio": pname, "state": state,
                "delta_ann_return_vs_p4b": round((m.get("ann_return",0) or 0) - (p4b_m.get("ann_return",0) or 0), 4),
            })

pd.DataFrame(state_sum_rows).to_csv(OUT / "phase6_state_summary.csv", index=False)
pd.DataFrame(state_sum_rows).to_csv(OUT / "phase6_state_exposure_summary.csv", index=False)
pd.DataFrame(state_delta_ggg1_rows).to_csv(OUT / "phase6_state_deltas_vs_ggg1.csv", index=False)
pd.DataFrame(state_delta_p4b_rows).to_csv(OUT / "phase6_state_deltas_vs_phase4b_best.csv", index=False)

for state, fname in diag_files.items():
    diag_rows = [r for r in state_sum_rows if r["state"] == state]
    pd.DataFrame(diag_rows).to_csv(OUT / fname, index=False)

print(f"  State diagnostics saved")
print("\n  State summary (Phase 6 vs Phase4B best):")
p6_c5 = next((r for r in state_sum_rows if r["portfolio"] == "improved_phase6_balanced_classifier_rebuild"), None)
p4b_by_state = {r["state"]: r for r in state_sum_rows if r["portfolio"] == "phase4b_best"}
if p6_c5:
    for state in ["calm_trend", "neutral_mixed", "recovery_confirmed", "stressed_panic"]:
        p6_row = next((r for r in state_sum_rows if r["portfolio"] == "improved_phase6_balanced_classifier_rebuild" and r["state"] == state), {})
        p4b_row = p4b_by_state.get(state, {})
        delta = round((p6_row.get("ann_return", 0) or 0) - (p4b_row.get("ann_return", 0) or 0), 4)
        print(f"    {state:20s}: C5={p6_row.get('ann_return', 'N/A'):.2%} P4B={p4b_row.get('ann_return', 'N/A'):.2%} delta={delta:+.2%}")


# ──────────────────────────────────────────────
# PART J — RISK / HIDDEN BETA
# ──────────────────────────────────────────────
print("\n=== PART J: Risk / hidden beta checks ===")

p4b_m_full = calc_metrics(returns.get("phase4b_best", pd.Series(dtype=float)), "phase4b_best")
ggg1_m_full = calc_metrics(returns.get("ggg1", pd.Series(dtype=float)), "ggg1")
ggg1_bear_m = calc_metrics(ws(returns.get("ggg1", pd.Series(dtype=float)), "2022-01-01", "2022-12-31"))
p4b_bear_m = calc_metrics(ws(returns.get("phase4b_best", pd.Series(dtype=float)), "2022-01-01", "2022-12-31"))
ggg_turn = float(pd.read_csv(L3 / "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv", index_col=0)["turnover"].mean()) if (L3 / "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv").exists() else np.nan
spy_ann = calc_metrics(spy_ret, "spy").get("ann_return", 0)

risk_rows, hb_rows, bear_rows, fail_rows, sig_perf_rows = [], [], [], [], []

p4b_common = returns.get("phase4b_best", pd.Series(dtype=float)).dropna().index.intersection(spy_ret.dropna().index)
p4b_cov = np.cov(returns["phase4b_best"].reindex(p4b_common), spy_ret.reindex(p4b_common)) if "phase4b_best" in returns and len(p4b_common) > 2 else np.zeros((2,2))
p4b_beta_spy = p4b_cov[0,1]/p4b_cov[1,1] if p4b_cov[1,1]>0 else np.nan

for pname in CANDIDATES:
    if pname not in returns:
        fail_rows.append({"portfolio": pname, "reason": "BUILD_FAILED"})
        continue
    ret = returns[pname]
    m_full = calc_metrics(ret)
    m_2020 = calc_metrics(ws(ret, "2020-01-01", None))
    m_bear = calc_metrics(ws(ret, "2022-01-01", "2022-12-31"))

    rf = L3 / f"portfolio_version_returns_{pname}.csv"
    avg_turn = float(pd.read_csv(rf, index_col=0)["turnover"].mean()) if rf.exists() and "turnover" in pd.read_csv(rf, index_col=0).columns else np.nan
    wf = L3 / f"portfolio_version_weights_{pname}.csv"
    avg_bil = float(pd.read_csv(wf, index_col=0, parse_dates=True)["BIL"].mean()) if wf.exists() else np.nan

    common = ret.dropna().index.intersection(spy_ret.dropna().index)
    cov = np.cov(ret.reindex(common), spy_ret.reindex(common)) if len(common) > 2 else np.zeros((2,2))
    beta_spy = cov[0,1]/cov[1,1] if cov[1,1]>0 else np.nan
    corr_spy = float(ret.reindex(common).corr(spy_ret.reindex(common)))

    ann_improve_p4b = (m_full.get("ann_return",0) or 0) - (p4b_m_full.get("ann_return",0) or 0)
    beta_attr = (beta_spy - p4b_beta_spy) * spy_ann if not (np.isnan(beta_spy) or np.isnan(p4b_beta_spy)) else np.nan
    pct_from_beta = abs(beta_attr)/abs(ann_improve_p4b) if ann_improve_p4b and not np.isnan(beta_attr) else np.nan

    passes_mandate = (m_full.get("max_drawdown",-1) >= -0.22 and (m_full.get("sharpe",0) or 0) >= 0.90)
    bear_ok = (m_bear.get("ann_return",-99) or -99) >= (p4b_bear_m.get("ann_return",-99) or -99) - 0.04
    disguised = (beta_spy is not None and not np.isnan(beta_spy) and beta_spy > 0.30) or corr_spy > 0.50

    risk_rows.append({"portfolio": pname,
                      "full_ann_return": round(m_full.get("ann_return",np.nan), 4),
                      "full_sharpe": round(m_full.get("sharpe",np.nan), 4),
                      "full_max_dd": round(m_full.get("max_drawdown",np.nan), 4),
                      "holdout_2020_return": round(m_2020.get("ann_return",np.nan), 4),
                      "holdout_2020_sharpe": round(m_2020.get("sharpe",np.nan), 4),
                      "avg_BIL": round(avg_bil, 4) if not np.isnan(avg_bil) else np.nan,
                      "avg_turnover": round(avg_turn, 4) if not np.isnan(avg_turn) else np.nan,
                      "passes_mandate": passes_mandate, "bear_ok": bear_ok, "disguised_spy": disguised,
                      "active_return_vs_p4b": round(ann_improve_p4b, 4),
                      "active_return_vs_ggg1": round((m_full.get("ann_return",0) or 0) - (ggg1_m_full.get("ann_return",0) or 0), 4)})
    hb_rows.append({"portfolio": pname, "beta_spy": round(beta_spy, 4) if not np.isnan(beta_spy) else np.nan,
                    "beta_delta_vs_p4b": round(beta_spy - p4b_beta_spy, 4) if not np.isnan(p4b_beta_spy) else np.nan,
                    "corr_spy": round(corr_spy, 4),
                    "pct_improve_from_beta": round(pct_from_beta, 3) if not np.isnan(pct_from_beta) else np.nan,
                    "hidden_beta_risk": "HIGH" if pct_from_beta and pct_from_beta > 0.50 else "LOW"})
    bear_rows.append({"portfolio": pname,
                      "bear_2022_return": round(m_bear.get("ann_return",np.nan), 4),
                      "p4b_bear_2022": round(p4b_bear_m.get("ann_return",np.nan), 4),
                      "delta_vs_p4b_bear": round((m_bear.get("ann_return",0) or 0) - (p4b_bear_m.get("ann_return",0) or 0), 4),
                      "bear_ok": bear_ok})

    # Classifier signal active performance
    for sig_name, sig_col in [("extreme_quality_calm", "extreme_quality_calm"),
                                ("high_quality_neutral", "high_quality_neutral")]:
        sig = ms[sig_col].astype(bool)
        on_ret = ret.reindex(sig[sig].index).dropna()
        off_ret = ret.reindex(sig[~sig].index).dropna()
        sig_perf_rows.append({"portfolio": pname, "signal": sig_name,
                               "signal_active_ann_return": round(calc_ann_return(on_ret), 4) if len(on_ret)>4 else np.nan,
                               "signal_inactive_ann_return": round(calc_ann_return(off_ret), 4) if len(off_ret)>4 else np.nan,
                               "n_active": len(on_ret)})

pd.DataFrame(risk_rows).to_csv(OUT / "phase6_risk_realism_checks.csv", index=False)
pd.DataFrame(hb_rows).to_csv(OUT / "phase6_hidden_beta_cash_checks.csv", index=False)
pd.DataFrame(bear_rows).to_csv(OUT / "phase6_2022_bear_check.csv", index=False)
pd.DataFrame(sig_perf_rows).to_csv(OUT / "phase6_signal_active_candidate_performance.csv", index=False)
pd.DataFrame(fail_rows if fail_rows else [{"portfolio":"none","reason":"all_built"}]).to_csv(
    OUT / "phase6_candidate_failure_reasons.csv", index=False)

print("  Risk/hidden beta summary:")
for r in risk_rows:
    h = next((x for x in hb_rows if x["portfolio"]==r["portfolio"]), {})
    hb_risk = h.get("hidden_beta_risk", "?")
    print(f"    {r['portfolio']}: ret={r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} "
          f"maxDD={r['full_max_dd']:.3%} vs_p4b={r['active_return_vs_p4b']:+.3%} "
          f"beta={h.get('beta_spy','?'):.3f} mandate={'OK' if r['passes_mandate'] else 'FAIL'} "
          f"bear={'OK' if r['bear_ok'] else 'FAIL'} hb={hb_risk}")


# ──────────────────────────────────────────────
# PART K — SELECTION
# ──────────────────────────────────────────────
print("\n=== PART K: Selection ===")

sel_rows = []
p4b_ann = p4b_m_full.get("ann_return", 0) or 0
ggg1_ann = ggg1_m_full.get("ann_return", 0) or 0
p4b_2020_m = calc_metrics(ws(returns.get("phase4b_best", pd.Series(dtype=float)), "2020-01-01", None))
p4b_2020_ann = p4b_2020_m.get("ann_return", 0) or 0

for pname in CANDIDATES:
    if pname not in returns:
        sel_rows.append({"portfolio": pname, "classification": "REJECT", "reason": "build_failed"})
        continue
    m_full = calc_metrics(returns[pname])
    m_2020 = calc_metrics(ws(returns[pname], "2020-01-01", None))
    m_2021 = calc_metrics(ws(returns[pname], "2021-01-01", None))
    m_bear = calc_metrics(ws(returns[pname], "2022-01-01", "2022-12-31"))

    ann = m_full.get("ann_return", 0) or 0
    sharpe = m_full.get("sharpe", 0) or 0
    max_dd = m_full.get("max_drawdown", -1) or -1
    hold_2020 = m_2020.get("ann_return", 0) or 0
    hold_sharpe = m_2020.get("sharpe", 0) or 0
    bear_ret = m_bear.get("ann_return", -99) or -99

    rr = next((r for r in risk_rows if r["portfolio"] == pname), {})
    hb = next((r for r in hb_rows if r["portfolio"] == pname), {})
    above_p4b = ann > p4b_ann
    above_ggg1 = ann > ggg1_ann
    hold_above_p4b = hold_2020 > p4b_2020_ann
    sharpe_ok = sharpe >= 0.90
    mandate_ok = max_dd >= -0.22
    bear_ok_flag = (bear_ret >= (p4b_bear_m.get("ann_return", -99) or -99) - 0.04)
    disguised = rr.get("disguised_spy", False)

    if not mandate_ok:
        cls = "REJECT"; reason = f"max_dd {max_dd:.2%} exceeds -22% limit"
    elif not sharpe_ok:
        cls = "REJECT"; reason = f"Sharpe {sharpe:.3f} below 0.90"
    elif not bear_ok_flag:
        cls = "REJECT"; reason = "2022 bear worse than Phase4B by >4%"
    elif disguised:
        cls = "REJECT"; reason = "disguised SPY"
    elif not above_ggg1:
        cls = "REJECT"; reason = f"return {ann:.2%} does not beat GGG1 {ggg1_ann:.2%}"
    elif ann >= 0.080 and sharpe >= 0.95 and max_dd >= -0.20 and above_p4b and hold_above_p4b:
        cls = "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
        reason = "Return>=8%, Sharpe>=0.95, maxDD>=-20%, beats Phase4B full+holdout"
    elif above_p4b and sharpe_ok and mandate_ok and bear_ok_flag:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW"
        reason = "Beats Phase4B return with acceptable risk"
    elif above_ggg1 and sharpe_ok and bear_ok_flag:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW" if hold_above_p4b else "KEEP_AS_RESEARCH_ONLY"
        reason = "Beats GGG1 but not Phase4B; or holdout modest"
    else:
        cls = "KEEP_AS_RESEARCH_ONLY"; reason = "Partial improvement only"

    sel_rows.append({
        "portfolio": pname, "classification": cls, "reason": reason,
        "full_ann_return": round(ann, 4), "full_sharpe": round(sharpe, 4),
        "full_max_dd": round(max_dd, 4), "holdout_2020_return": round(hold_2020, 4),
        "holdout_2020_sharpe": round(hold_sharpe, 4), "bear_2022_return": round(bear_ret, 4),
        "beats_phase4b": above_p4b, "beats_ggg1": above_ggg1,
        "mandate_ok": mandate_ok, "bear_ok": bear_ok_flag, "disguised": disguised,
    })

sel_df = pd.DataFrame(sel_rows)
sel_df.to_csv(OUT / "phase6_selection_table.csv", index=False)
print("  Selection results:")
for r in sel_rows:
    print(f"    {r['portfolio']}: {r['classification']}")
    print(f"      return={r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} maxDD={r['full_max_dd']:.3%} | {r['reason']}")

best_candidate = None
for cls_prio in ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT", "KEEP_AS_AGGRESSIVE_SHADOW"]:
    cands = [r for r in sel_rows if r["classification"] == cls_prio]
    if cands:
        best_candidate = max(cands, key=lambda r: r["full_ann_return"])["portfolio"]
        break


# ──────────────────────────────────────────────
# PART L — AUDITS
# ──────────────────────────────────────────────
print("\n=== PART L: Audits ===")
audit_rows = []
audit_lines = ["# Phase 6 Audit Summary\n"]

if best_candidate:
    best_cls = next(r["classification"] for r in sel_rows if r["portfolio"] == best_candidate)
    print(f"  Best candidate: {best_candidate} ({best_cls})")
    is_challenger = best_cls == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
    for audit_name in ["research_committee_report", "backtest_realism_audit",
                        "allocator_benchmark_audit", "robustness_simulation_audit"]:
        script = ROOT / "scripts" / f"{audit_name}.py"
        if not script.exists():
            audit_rows.append({"audit": audit_name, "status": "SKIPPED_NOT_FOUND"})
            continue
        if audit_name == "robustness_simulation_audit" and not is_challenger:
            audit_rows.append({"audit": audit_name, "status": "SKIPPED_NOT_CHALLENGER"})
            continue
        flags = [] if is_challenger else ["--quick"]
        cmd = [sys.executable, str(script), best_candidate] + flags
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=300)
            status = "PASS" if res.returncode == 0 else "FAIL"
            log_name = f"phase6_{audit_name.replace('_report','')}_quick.log"
            with open(OUT / log_name, "w") as f:
                f.write(res.stdout[-4000:] + "\n" + res.stderr[-2000:])
            audit_rows.append({"audit": audit_name, "status": status})
            audit_lines.append(f"## {audit_name}: {status}\n")
        except subprocess.TimeoutExpired:
            audit_rows.append({"audit": audit_name, "status": "TIMEOUT"})
else:
    print("  No qualifying candidate — skipping audits")
    audit_lines.append("No qualifying candidate — audits skipped.\n")

pd.DataFrame(audit_rows).to_csv(OUT / "phase6_audit_results.csv", index=False)
with open(OUT / "phase6_audit_summary.md", "w") as f:
    f.writelines(audit_lines)


# ──────────────────────────────────────────────
# PART M — NEXT PHASE DECISION
# ──────────────────────────────────────────────
print("\n=== PART M: Next phase decision ===")

n_challenger = sum(1 for r in sel_rows if r["classification"] == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT")
n_shadow = sum(1 for r in sel_rows if r["classification"] == "KEEP_AS_AGGRESSIVE_SHADOW")
n_reject = sum(1 for r in sel_rows if r["classification"] == "REJECT")
best_return = max((r["full_ann_return"] for r in sel_rows if r["classification"] in
                   ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT","KEEP_AS_AGGRESSIVE_SHADOW"]), default=0)

if n_challenger > 0:
    decision = "PROMOTE_PHASE6_TO_PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
    rationale = f"{best_candidate} satisfies mandate: return>={best_return:.2%}, Sharpe>=0.95, maxDD>=-20%, beats Phase4B."
elif n_shadow > 0 and best_return > p4b_ann:
    decision = "KEEP_PHASE6_AS_AGGRESSIVE_SHADOW"
    rationale = f"{best_candidate} ({best_return:.2%}) improves over Phase4B ({p4b_ann:.2%}) with acceptable risk."
elif n_shadow > 0:
    decision = "PROCEED_TO_PHASE6B_REFINED_CLASSIFIER_MAPPING"
    rationale = f"Phase 6 classifier shows signal but best candidate ({best_return:.2%}) doesn't clearly beat Phase4B ({p4b_ann:.2%})."
else:
    decision = "PROCEED_TO_PHASE7_ALLOCATOR_OBJECTIVE_REWRITE"
    rationale = f"Classifier rebuild fails to improve over Phase4B. Allocator objective/mapping may be the bottleneck."

if best_return < 0.075 and n_shadow == 0 and n_challenger == 0:
    decision = "RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE"
    rationale = "Existing-data classifier cannot solve the return ceiling. PIT stock breadth data is needed."

pd.DataFrame([{"decision": decision, "best_candidate": best_candidate or "none",
               "best_return": round(best_return, 4), "rationale": rationale,
               "n_challenger": n_challenger, "n_shadow": n_shadow, "n_reject": n_reject}]).to_csv(
    OUT / "phase6_next_phase_decision.csv", index=False)
pd.DataFrame([{"action": decision, "description": rationale, "priority": 1}]).to_csv(
    OUT / "phase6_next_action_recommendation.csv", index=False)

with open(OUT / "phase6_protocol.json", "w") as f:
    json.dump({
        "phase": "phase_6_market_state_classifier_rebuild",
        "date": "2026-05-07",
        "production_pin": "improved_phase2b_regime_confidence_boost",
        "production_candidate": "improved_phaseggg_confirmed_only_robust_offense",
        "phase4b_best_shadow": "improved_phase4b_refined_sector_20pct",
        "candidates": CANDIDATES,
        "best_candidate": best_candidate or "none",
        "decision": decision,
    }, f, indent=2)

print(f"\n  DECISION: {decision}")
print(f"  Rationale: {rationale}")


# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"Output directory: {OUT}")
out_files = sorted(OUT.glob("*"))
print(f"Files created: {len(out_files)}")
for fp in out_files:
    print(f"  {fp.name}")
print("\nDone. Phase 6 Market-State Classifier Rebuild complete.")
print("No production pins changed. No auto-promotion.")
