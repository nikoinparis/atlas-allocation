#!/usr/bin/env python3
"""
Phase 3 — Breadth-Confirmed US Offense Upgrade
Builds 6 candidates that switch offense ETF composition to pure US (SPY/QQQ/IWM)
during high-breadth non-stressed states, addressing the Phase 2 finding that
diversified offense sleeves don't capture US bull-market upside.
Diagnostic + selection. No production pin changes. No auto-promotion.
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
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L1 = ROOT / "data" / "02_layer1_signals"
HUB = ROOT / "data" / "01_data_hub"
OUT = ROOT / "data" / "research" / "phase_3_breadth_confirmed_us_offense"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS = 52

CANDIDATES = [
    "improved_phase3_breadth_neutral_cash_unlock",
    "improved_phase3_high_breadth_calm_us_offense",
    "improved_phase3_qqq_us_growth_leadership",
    "improved_phase3_breadth_credit_risk_on_offense",
    "improved_phase3_balanced_breadth_aggressive",
    "improved_phase3_stretch_breadth_aggressive",
]

BASELINES = {
    "ggg1": "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    "phase2_best": "portfolio_version_returns_improved_phase2_aggressive_neutral_cash_unlock.csv",
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


def load_ret(path: Path) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    col = "net_return" if "net_return" in df.columns else df.columns[0]
    return df[col]


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
bm_prices = pd.read_csv(HUB / "benchmark_prices_weekly.csv", index_col="Date", parse_dates=True)
daily_ret = pd.read_csv(HUB / "daily_returns.csv", index_col="Date", parse_dates=True)
daily_ret.index = pd.to_datetime(daily_ret.index)
weekly_ret = (1 + daily_ret).resample("W-FRI").prod() - 1
weekly_ret = weekly_ret.reindex(msh.index)

spy_weekly = bm_prices["SPY"].pct_change().dropna()
ief_weekly = bm_prices["IEF"].pct_change().dropna()
bench_6040 = (0.60 * spy_weekly + 0.40 * ief_weekly).dropna()

# Causal breadth signal (1-week lag applied inside the build script)
breadth_signal = (
    (msh["breadth_sma_43"] >= 0.65) &
    (msh["market_trend_positive"] == 1) &
    (~msh["market_state"].isin(["stressed_panic", "recovery_fragile"]))
)
canary_col = "canary_breadth_default"
credit_signal = (
    breadth_signal & (msh[canary_col] == 1)
    if canary_col in msh.columns else breadth_signal
)


# ──────────────────────────────────────────────
# PART A — SIGNAL INVENTORY
# ──────────────────────────────────────────────
print("=== PART A: Signal inventory ===")

breadth_inv = []
for feat in ["breadth_sma_43", "breadth_26w_mom", "breadth_13w_mom", "breadth_change_4w",
             "market_trend_positive", "canary_breadth_default", "canary_breadth_pair",
             "transition_good_state_prob", "transition_non_stress_prob"]:
    if feat not in msh.columns:
        continue
    col = msh[feat]
    breadth_inv.append({
        "feature": feat, "source": "market_state_history.csv",
        "non_null_pct": round(float(col.notna().mean()), 3),
        "mean": round(float(col.mean()), 3) if col.dtype != object else "N/A",
        "causal_ok": True,
        "already_in_ggg1": feat in ["breadth_sma_43", "market_trend_positive",
                                     "transition_good_state_prob", "transition_non_stress_prob"],
        "role": "breadth/trend/regime confirmation",
    })

# Add VIX from regime_features
rf_path = L1 / "regime_features.csv"
if rf_path.exists():
    rf = pd.read_csv(rf_path, index_col=0, parse_dates=True)
    for feat in ["vix_level_z_tradable", "vix_slope_risk_off_z_tradable", "macro_risk_score_tradable"]:
        if feat in rf.columns:
            breadth_inv.append({
                "feature": feat, "source": "regime_features.csv",
                "non_null_pct": round(float(rf[feat].notna().mean()), 3),
                "mean": round(float(rf[feat].dropna().mean()), 3),
                "causal_ok": True, "already_in_ggg1": False,
                "role": "volatility/macro risk proxy",
            })

pd.DataFrame(breadth_inv).to_csv(OUT / "phase3_breadth_signal_inventory.csv", index=False)

# US offense assets
us_assets = []
for ticker, desc, asset_class in [
    ("SPY", "S&P 500 ETF — US broad market", "US Equity"),
    ("QQQ", "NASDAQ 100 ETF — US tech/growth", "US Equity"),
    ("IWM", "Russell 2000 ETF — US small cap", "US Equity"),
    ("VUG", "Vanguard Growth ETF — US large-cap growth", "US Equity"),
    ("VTV", "Vanguard Value ETF — US large-cap value", "US Equity"),
    ("EFA", "iShares MSCI EAFE — developed ex-US equity", "Int'l Equity"),
    ("VEA", "Vanguard FTSE Dev'd Markets — developed ex-US", "Int'l Equity"),
    ("VWO", "Vanguard FTSE EM — emerging markets", "Int'l Equity"),
    ("EWJ", "iShares Japan — Japan equity", "Int'l Equity"),
    ("PDBC", "Invesco DB Commodity — diversified commodity", "Commodity"),
    ("DBA", "Invesco DB Agriculture — agricultural commodity", "Commodity"),
]:
    if ticker in weekly_ret.columns:
        ann = float((1 + weekly_ret[ticker].dropna().mean()) ** WEEKS - 1)
        vol = float(weekly_ret[ticker].dropna().std() * np.sqrt(WEEKS))
    else:
        ann = vol = np.nan
    us_assets.append({
        "ticker": ticker, "description": desc, "asset_class": asset_class,
        "full_period_ann_return": round(ann, 4),
        "full_period_ann_vol": round(vol, 4),
        "in_ggg1_default_offense": ticker in ["SPY","QQQ","IWM","EFA","VEA","VWO","EWJ","VNQ","PDBC","DBA"],
        "in_p3_us_pure": ticker in ["SPY","QQQ","IWM"],
        "in_p3_us_growth": ticker in ["QQQ","SPY","VUG"],
    })
pd.DataFrame(us_assets).to_csv(OUT / "phase3_available_us_offense_assets.csv", index=False)
pd.DataFrame([{
    "feature": "breadth_sma_43>=0.65 & trend_positive & not_stressed", "source": "market_state_history.csv",
    "causal_ok": True, "description": "Standard P3 breadth confirmation signal",
}, {
    "feature": "above + canary_breadth_default==1", "source": "market_state_history.csv",
    "causal_ok": True, "description": "Double-confirmed P3 signal (stricter)",
}]).to_csv(OUT / "phase3_feature_source_audit.csv", index=False)
print(f"  Saved signal inventory, asset inventory, feature audit")


# ──────────────────────────────────────────────
# PART B — SIGNAL DEFINITIONS
# ──────────────────────────────────────────────
print("\n=== PART B: Signal definitions ===")

signal_defs = []
for sig_name, signal, desc in [
    ("breadth_confirmed_standard", breadth_signal, "breadth_sma_43>=0.65 AND market_trend_positive=1 AND not stressed/fragile"),
    ("breadth_confirmed_double", credit_signal, "breadth_sma_43>=0.65 AND trend=1 AND canary=1 AND not stressed/fragile"),
]:
    freq = float(signal.mean())
    for state in msh["market_state"].unique():
        state_mask = msh["market_state"] == state
        state_sig = signal & state_mask
        signal_defs.append({
            "signal": sig_name, "state": state,
            "event_count": int(state_sig.sum()),
            "state_weeks": int(state_mask.sum()),
            "signal_freq_in_state": round(float(state_sig.sum() / max(state_mask.sum(), 1)), 3),
            "overall_freq": round(freq, 3),
            "description": desc,
            "causal_ok": True,
            "lag_rule": "1-week lag applied via augmented state series in build pipeline",
        })

pd.DataFrame(signal_defs).to_csv(OUT / "phase3_breadth_confirmed_signal_definitions.csv", index=False)

# Signal summary
sig_summary = pd.DataFrame([
    {"signal": "breadth_confirmed_standard", "total_active_weeks": int(breadth_signal.sum()),
     "calm_trend_active": int((breadth_signal & (msh["market_state"]=="calm_trend")).sum()),
     "neutral_mixed_active": int((breadth_signal & (msh["market_state"]=="neutral_mixed")).sum()),
     "stressed_panic_active": int((breadth_signal & (msh["market_state"]=="stressed_panic")).sum())},
    {"signal": "breadth_confirmed_double", "total_active_weeks": int(credit_signal.sum()),
     "calm_trend_active": int((credit_signal & (msh["market_state"]=="calm_trend")).sum()),
     "neutral_mixed_active": int((credit_signal & (msh["market_state"]=="neutral_mixed")).sum()),
     "stressed_panic_active": int((credit_signal & (msh["market_state"]=="stressed_panic")).sum())},
])
sig_summary.to_csv(OUT / "phase3_breadth_signal_summary.csv", index=False)
print(f"  breadth_confirmed_standard: {int(breadth_signal.sum())} active weeks (calm: "
      f"{int((breadth_signal & (msh['market_state']=='calm_trend')).sum())}, "
      f"neutral: {int((breadth_signal & (msh['market_state']=='neutral_mixed')).sum())})")
print(f"  breadth_confirmed_double: {int(credit_signal.sum())} active weeks")


# ──────────────────────────────────────────────
# PART C — OFFENSE BASKET DESIGNS
# ──────────────────────────────────────────────
print("\n=== PART C: Offense basket designs ===")

basket_designs = [
    {"basket": "ggg1_default_offense",
     "tickers": "SPY,QQQ,IWM,EFA,VEA,VWO,EWJ,VNQ,PDBC,DBA",
     "weighting": "momentum-based via composite_regime_conditioned positions",
     "causal_lag": "positions from prior allocation",
     "role": "Current GGG1 default — baseline for comparison",
     "problem": "International/commodity drag dilutes US bull-market upside"},
    {"basket": "p3_us_pure_offense",
     "tickers": "SPY,QQQ,IWM",
     "weighting": "proportional to composite_regime_conditioned weights for SPY/QQQ/IWM",
     "causal_lag": "positions from prior allocation",
     "role": "Phase 3 primary — US broad equity offense",
     "problem": "Misses growth tilt — may underperform during QQQ bull runs"},
    {"basket": "p3_us_growth_offense",
     "tickers": "QQQ,SPY,VUG",
     "weighting": "proportional to composite_regime_conditioned weights",
     "causal_lag": "positions from prior allocation",
     "role": "Phase 3 stretch — US growth/tech tilt",
     "problem": "More tech concentration risk; tested in C3/C6"},
]
pd.DataFrame(basket_designs).to_csv(OUT / "phase3_offense_basket_designs.csv", index=False)
pd.DataFrame([{"ticker": t, "in_universe": t in weekly_ret.columns} for t in
               ["SPY","QQQ","IWM","VUG","VTV","EFA","VEA","VWO","EWJ","VNQ","PDBC","DBA"]
               ]).to_csv(OUT / "phase3_offense_asset_inventory.csv", index=False)
print("  Saved offense basket designs")


# ──────────────────────────────────────────────
# PART D — EVENT VALIDATION
# ──────────────────────────────────────────────
print("\n=== PART D: Event / forward-return validation ===")

ggg_default_tickers = [t for t in ["SPY","QQQ","IWM","EFA","VEA","VWO","EWJ","VNQ","PDBC","DBA"] if t in weekly_ret.columns]
us_pure_tickers = ["SPY", "QQQ", "IWM"]
us_growth_tickers = [t for t in ["QQQ", "SPY", "VUG"] if t in weekly_ret.columns]

ggg_ew = weekly_ret[ggg_default_tickers].mean(axis=1)
us_pure = weekly_ret[us_pure_tickers].mean(axis=1)
us_growth = weekly_ret[us_growth_tickers].mean(axis=1)


def fwd_n(s: pd.Series, n: int) -> pd.Series:
    return (1 + s).rolling(n).apply(lambda x: x.prod() - 1, raw=True).shift(-n)


val_rows = []
for horizon in [4, 8, 13]:
    fwd_spy = fwd_n(weekly_ret["SPY"], horizon)
    fwd_us = fwd_n(us_pure, horizon)
    fwd_growth = fwd_n(us_growth, horizon)
    fwd_ggg = fwd_n(ggg_ew, horizon)

    for state in ["calm_trend", "neutral_mixed", "recovery_confirmed", "stressed_panic"]:
        state_mask = msh["market_state"] == state
        for sig_label, sig in [("all", pd.Series(True, index=msh.index)),
                                 ("breadth_on", breadth_signal),
                                 ("breadth_off", ~breadth_signal)]:
            mask = state_mask & sig
            n = int(mask.sum())
            if n < 4:
                continue
            val_rows.append({
                "state": state, "signal": sig_label, "horizon_weeks": horizon, "n_events": n,
                "spy_fwd_mean": round(float(fwd_spy[mask].mean()), 5),
                "us_pure_fwd_mean": round(float(fwd_us[mask].mean()), 5),
                "us_growth_fwd_mean": round(float(fwd_growth[mask].mean()), 5),
                "ggg_diversified_fwd_mean": round(float(fwd_ggg[mask].mean()), 5),
                "lift_us_pure_vs_ggg": round(float(fwd_us[mask].mean() - fwd_ggg[mask].mean()), 5),
                "lift_us_growth_vs_ggg": round(float(fwd_growth[mask].mean() - fwd_ggg[mask].mean()), 5),
                "hit_rate_us_pure_gt_ggg": round(float((fwd_us[mask] > fwd_ggg[mask]).mean()), 3),
            })

val_df = pd.DataFrame(val_rows)
val_df.to_csv(OUT / "phase3_signal_event_validation.csv", index=False)

# Forward return table
fwd_table_rows = []
for state in ["calm_trend", "neutral_mixed"]:
    for hor in [4, 8, 13]:
        for sig_label, sig in [("all", pd.Series(True, index=msh.index)), ("breadth_on", breadth_signal)]:
            mask = (msh["market_state"] == state) & sig
            n = int(mask.sum())
            if n < 4:
                continue
            fwd_spy = fwd_n(weekly_ret["SPY"], hor)
            fwd_us = fwd_n(us_pure, hor)
            fwd_ggg = fwd_n(ggg_ew, hor)
            fwd_table_rows.append({
                "state": state, "signal": sig_label, "horizon": hor, "n": n,
                "spy_fwd": round(float(fwd_spy[mask].mean()), 5),
                "us_pure_fwd": round(float(fwd_us[mask].mean()), 5),
                "ggg_fwd": round(float(fwd_ggg[mask].mean()), 5),
                "lift_us_vs_ggg": round(float(fwd_us[mask].mean() - fwd_ggg[mask].mean()), 5),
            })
pd.DataFrame(fwd_table_rows).to_csv(OUT / "phase3_offense_basket_forward_returns.csv", index=False)

# Same-state signal lift
lift_rows = []
for state in ["calm_trend", "neutral_mixed"]:
    for hor in [4, 13]:
        fwd_us = fwd_n(us_pure, hor)
        fwd_ggg = fwd_n(ggg_ew, hor)
        state_mask = msh["market_state"] == state
        on_mask = state_mask & breadth_signal
        off_mask = state_mask & ~breadth_signal
        if on_mask.sum() > 2 and off_mask.sum() > 2:
            lift_rows.append({
                "state": state, "horizon": hor,
                "breadth_on_us_pure_fwd": round(float(fwd_us[on_mask].mean()), 5),
                "breadth_on_ggg_fwd": round(float(fwd_ggg[on_mask].mean()), 5),
                "breadth_off_ggg_fwd": round(float(fwd_ggg[off_mask].mean()), 5),
                "lift_us_vs_ggg_when_breadth_on": round(float(fwd_us[on_mask].mean() - fwd_ggg[on_mask].mean()), 5),
                "breadth_on_weeks": int(on_mask.sum()),
                "breadth_off_weeks": int(off_mask.sum()),
            })
pd.DataFrame(lift_rows).to_csv(OUT / "phase3_same_state_signal_lift.csv", index=False)

pd.DataFrame([{"state": s, "signal": "breadth_on", "weeks": int((msh["market_state"]==s).sum()),
               "breadth_on_weeks": int(((msh["market_state"]==s) & breadth_signal).sum())}
              for s in msh["market_state"].unique()]).to_csv(OUT / "phase3_signal_state_coverage.csv", index=False)

print("  Signal validation key results:")
calm_4 = val_df[(val_df["state"]=="calm_trend") & (val_df["signal"]=="breadth_on") & (val_df["horizon_weeks"]==4)]
neutral_4 = val_df[(val_df["state"]=="neutral_mixed") & (val_df["signal"]=="breadth_on") & (val_df["horizon_weeks"]==4)]
if len(calm_4):
    r = calm_4.iloc[0]
    print(f"  calm_trend breadth_on 4w: spy={r['spy_fwd_mean']:.3%} us_pure={r['us_pure_fwd_mean']:.3%} "
          f"ggg={r['ggg_diversified_fwd_mean']:.3%} lift={r['lift_us_pure_vs_ggg']:.3%}")
if len(neutral_4):
    r = neutral_4.iloc[0]
    print(f"  neutral_mixed breadth_on 4w: spy={r['spy_fwd_mean']:.3%} us_pure={r['us_pure_fwd_mean']:.3%} "
          f"ggg={r['ggg_diversified_fwd_mean']:.3%} lift={r['lift_us_pure_vs_ggg']:.3%}")

# Check if signal has value before proceeding
calm_lift = float(calm_4["lift_us_pure_vs_ggg"].iloc[0]) if len(calm_4) else 0
neutral_lift = float(neutral_4["lift_us_pure_vs_ggg"].iloc[0]) if len(neutral_4) else 0
if calm_lift <= 0 and neutral_lift <= 0:
    print("  WARNING: No signal lift found in either state — consider stopping before portfolio build")
else:
    print(f"  Signal shows positive lift in {'calm_trend' if calm_lift > 0 else ''} "
          f"{'and neutral_mixed' if neutral_lift > 0 else ''} — proceeding with portfolio build")


# ──────────────────────────────────────────────
# PART E — CANDIDATE DESIGNS
# ──────────────────────────────────────────────
print("\n=== PART E: Candidate designs ===")
candidate_designs = [
    {"candidate": "improved_phase3_breadth_neutral_cash_unlock",
     "signal": "breadth_confirmed_standard",
     "states_modified": "neutral_mixed_breadth_on",
     "offense_basket": "us_pure (SPY/QQQ/IWM)",
     "state_tilt": "phase_ddd_confirmed_near_exclude_dual (GGG1)",
     "phase2b_mode": "phase2_aggressive_neutral_boost (+0.08)",
     "target": "9-10%",
     "hypothesis": "neutral_mixed opportunity cost fixed by US-quality offense + regime multiplier boost"},
    {"candidate": "improved_phase3_high_breadth_calm_us_offense",
     "signal": "breadth_confirmed_standard",
     "states_modified": "calm_trend_breadth_on",
     "offense_basket": "us_pure (SPY/QQQ/IWM)",
     "state_tilt": "phase_ddd_confirmed_near_exclude_dual (GGG1)",
     "phase2b_mode": "regime_confidence_boost (GGG1)",
     "target": "9-10%",
     "hypothesis": "calm_trend opportunity cost fixed by dropping international/commodity from offense"},
    {"candidate": "improved_phase3_qqq_us_growth_leadership",
     "signal": "breadth_confirmed_standard",
     "states_modified": "calm_trend_breadth_on + neutral_mixed_breadth_on",
     "offense_basket": "calm→us_growth (QQQ/SPY/VUG), neutral→blended 50/50 growth/pure",
     "state_tilt": "phase_ddd_confirmed_near_exclude_dual (GGG1)",
     "phase2b_mode": "regime_confidence_boost (GGG1)",
     "target": "9-10.5%",
     "hypothesis": "QQQ/growth concentration captures tech-led bull runs better"},
    {"candidate": "improved_phase3_breadth_credit_risk_on_offense",
     "signal": "breadth_confirmed_double (breadth+canary)",
     "states_modified": "calm_trend_breadth_on + neutral_mixed_breadth_on",
     "offense_basket": "us_pure (SPY/QQQ/IWM)",
     "state_tilt": "phase_ddd_confirmed_near_exclude_dual (GGG1)",
     "phase2b_mode": "regime_confidence_boost (GGG1)",
     "target": "9-10%",
     "hypothesis": "Stricter double-confirmation reduces false signals"},
    {"candidate": "improved_phase3_balanced_breadth_aggressive",
     "signal": "breadth_confirmed_standard",
     "states_modified": "calm_trend_breadth_on + neutral_mixed_breadth_on",
     "offense_basket": "us_pure (SPY/QQQ/IWM)",
     "state_tilt": "phase2_aggressive_nonstressed_offense (Phase2 C4)",
     "phase2b_mode": "phase2_aggressive_neutral_boost (+0.08) + faster rerisk",
     "target": "9-10.5%",
     "hypothesis": "Combined ETF quality upgrade + sleeve allocation + regime boost"},
    {"candidate": "improved_phase3_stretch_breadth_aggressive",
     "signal": "breadth_confirmed_standard (stretch)",
     "states_modified": "calm+neutral+rc_breadth_on",
     "offense_basket": "us_growth (QQQ/SPY/VUG) + blended",
     "state_tilt": "phase2_aggressive_stretch_offense (Phase2 C6)",
     "phase2b_mode": "phase2_aggressive_full_mandate (+0.10) + max rerisk",
     "target": "10.5-12%",
     "hypothesis": "Maximum combined offense upgrade — all three levers active"},
]
pd.DataFrame(candidate_designs).to_csv(OUT / "phase3_candidate_designs.csv", index=False)
print("  Saved candidate designs")


# ──────────────────────────────────────────────
# PART F — RUN PRODUCTION PIPELINE
# ──────────────────────────────────────────────
print("\n=== PART F: Run production pipeline ===")

build_names = ",".join(CANDIDATES)
build_env = os.environ.copy()
build_env["BUILD_VERSION_NAMES"] = build_names
build_script = ROOT / "scripts" / "build_improvement_artifacts.py"

print(f"  Running: BUILD_VERSION_NAMES='...phase3...' python3 build_improvement_artifacts.py")
result = subprocess.run(
    [sys.executable, str(build_script)],
    env=build_env, capture_output=True, text=True, cwd=str(ROOT), timeout=720,
)
build_log = OUT / "phase3_build.log"
with open(build_log, "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout[-10000:] if len(result.stdout) > 10000 else result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr[-4000:] if len(result.stderr) > 4000 else result.stderr)
if result.returncode != 0:
    print(f"  BUILD FAILED (exit {result.returncode})")
    print(f"  stderr tail: {result.stderr[-1500:]}")
    sys.exit(1)
print(f"  Build completed (exit 0). Log: {build_log.name}")

missing = [f"{c}_{s}" for c in CANDIDATES for s in ["returns","weights","sleeve_weights"]
           if not (L3 / f"portfolio_version_{s}_{c}.csv").exists()]
if missing:
    print(f"  WARNING: Missing artifacts: {missing[:5]}")
else:
    print(f"  All {len(CANDIDATES)*3} candidate artifacts confirmed.")


# ──────────────────────────────────────────────
# LOAD ALL RETURNS
# ──────────────────────────────────────────────
print("\n=== Loading return series ===")
returns: dict[str, pd.Series] = {}
for c in CANDIDATES:
    p = L3 / f"portfolio_version_returns_{c}.csv"
    if p.exists():
        returns[c] = load_ret(p)
        print(f"  {c}: {len(returns[c])} weeks")
for name, fname in BASELINES.items():
    p = L3 / fname
    if p.exists():
        returns[name] = load_ret(p)
returns["spy"] = spy_weekly
returns["qqq"] = weekly_ret["QQQ"].dropna() if "QQQ" in weekly_ret.columns else pd.Series(dtype=float)
returns["bench_60_40"] = bench_6040


# ──────────────────────────────────────────────
# PART G — FULL + HOLDOUT METRICS
# ──────────────────────────────────────────────
print("\n=== PART G: Metrics ===")

all_metrics = []
for pname, ret in returns.items():
    for wname, (wstart, wend) in WINDOWS.items():
        slc = ws(ret, wstart, wend).dropna()
        m = calc_metrics(slc, pname)
        row = {"portfolio": pname, "window": wname, **m}

        # Weights-based stats
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

        # Turnover
        rf = L3 / f"portfolio_version_returns_{pname}.csv"
        if rf.exists():
            rdf = pd.read_csv(rf, index_col=0, parse_dates=True)
            if "turnover" in rdf.columns:
                row["avg_turnover"] = round(float(ws(rdf["turnover"], wstart, wend).mean()), 4)
            else:
                row["avg_turnover"] = np.nan
        else:
            row["avg_turnover"] = np.nan

        # Capture vs SPY
        spy_slc = ws(spy_weekly, wstart, wend).dropna()
        uc, dc, beta, corr = get_capture(slc, spy_slc.reindex(slc.index))
        row.update({"upside_capture_spy": round(uc, 4) if not np.isnan(uc) else np.nan,
                    "downside_capture_spy": round(dc, 4) if not np.isnan(dc) else np.nan,
                    "beta_spy": round(beta, 4) if not np.isnan(beta) else np.nan,
                    "corr_spy": round(corr, 4) if not np.isnan(corr) else np.nan})

        # Capture vs QQQ
        if "qqq" in returns and len(returns["qqq"]) > 0:
            qqq_slc = ws(returns["qqq"], wstart, wend).dropna()
            _, _, beta_q, corr_q = get_capture(slc, qqq_slc.reindex(slc.index))
            row["beta_qqq"] = round(beta_q, 4) if not np.isnan(beta_q) else np.nan
            row["corr_qqq"] = round(corr_q, 4) if not np.isnan(corr_q) else np.nan
        else:
            row["beta_qqq"] = row["corr_qqq"] = np.nan

        # Active returns
        ggg_slc = ws(returns.get("ggg1", pd.Series(dtype=float)), wstart, wend).dropna()
        p2_slc = ws(returns.get("phase2_best", pd.Series(dtype=float)), wstart, wend).dropna()
        for baseline_name, baseline_slc in [("ggg1", ggg_slc), ("phase2_best", p2_slc)]:
            common = slc.index.intersection(baseline_slc.index)
            if len(common) > 4:
                n = len(common)
                p_ann = float((1+slc.reindex(common).mean())**WEEKS-1)
                b_ann = float((1+baseline_slc.reindex(common).mean())**WEEKS-1)
                row[f"active_return_vs_{baseline_name}"] = round(p_ann - b_ann, 4)
            else:
                row[f"active_return_vs_{baseline_name}"] = np.nan

        spy_ann_slc = float((1+spy_slc.reindex(slc.index).dropna().mean())**WEEKS-1) if len(slc) > 4 else np.nan
        row["active_return_vs_spy"] = round(m.get("ann_return", np.nan) - spy_ann_slc, 4) if not np.isnan(spy_ann_slc) else np.nan

        all_metrics.append(row)

metrics_df = pd.DataFrame(all_metrics)
metrics_df.to_csv(OUT / "phase3_candidate_metrics_full.csv", index=False)
hold_df = metrics_df[metrics_df["window"].isin(["holdout_2016","holdout_2020","holdout_2021","bear_2022","recovery_2023"])]
hold_df.to_csv(OUT / "phase3_candidate_holdout_metrics.csv", index=False)

focus = CANDIDATES + ["ggg1","phase2_best","prod_pin","shadow","spy","qqq","bench_60_40","equal_weight"]
bm_table = metrics_df[metrics_df["portfolio"].isin(focus) & metrics_df["window"].isin(["full","holdout_2020","holdout_2021","bear_2022","recovery_2023"])][
    ["portfolio","window","ann_return","sharpe","max_drawdown","calmar","cvar_5","avg_BIL","avg_SPY","avg_QQQ","avg_turnover","beta_spy","active_return_vs_ggg1","active_return_vs_phase2_best"]
].copy()
bm_table.to_csv(OUT / "phase3_candidate_vs_benchmark_table.csv", index=False)
cap_df = metrics_df[metrics_df["portfolio"].isin(focus)][
    ["portfolio","window","upside_capture_spy","downside_capture_spy","beta_spy","corr_spy","beta_qqq","corr_qqq","active_return_vs_spy","active_return_vs_ggg1","active_return_vs_phase2_best"]
].copy()
cap_df.to_csv(OUT / "phase3_capture_beta_by_window.csv", index=False)

print("  Full-period comparison:")
fp = metrics_df[metrics_df["window"]=="full"][["portfolio","ann_return","sharpe","max_drawdown","cvar_5","avg_BIL","avg_SPY","avg_QQQ","beta_spy","active_return_vs_ggg1","active_return_vs_phase2_best"]].copy()
fp = fp[fp["portfolio"].isin(CANDIDATES+["ggg1","phase2_best","spy"])].set_index("portfolio")
print(fp.round(4).to_string())


# ──────────────────────────────────────────────
# PART H — STATE-BY-STATE DIAGNOSIS
# ──────────────────────────────────────────────
print("\n=== PART H: State diagnostics ===")

state_summary_rows = []
state_delta_rows = []
ggg1_ret = returns.get("ggg1", pd.Series(dtype=float))
p2_ret = returns.get("phase2_best", pd.Series(dtype=float))

for pname in CANDIDATES + ["ggg1", "phase2_best"]:
    if pname not in returns:
        continue
    ret = returns[pname]
    wf = L3 / f"portfolio_version_weights_{pname}.csv"
    has_w = wf.exists()
    if has_w:
        w_full = pd.read_csv(wf, index_col=0, parse_dates=True)

    for state in msh["market_state"].unique():
        idx = msh[msh["market_state"] == state].index
        state_ret = ret.reindex(idx).dropna()
        if len(state_ret) < 4:
            continue
        m = calc_metrics(state_ret, pname)
        row = {"portfolio": pname, "state": state, "n_weeks": len(state_ret), **m}
        if has_w:
            ws_ = w_full.reindex(idx)
            row["avg_BIL"] = round(float(ws_["BIL"].mean()), 4) if "BIL" in ws_ else np.nan
            row["avg_SPY"] = round(float(ws_["SPY"].mean()), 4) if "SPY" in ws_ else np.nan
            row["avg_QQQ"] = round(float(ws_["QQQ"].mean()), 4) if "QQQ" in ws_ else np.nan
        state_summary_rows.append(row)

        ggg_state = ggg1_ret.reindex(idx).dropna()
        p2_state = p2_ret.reindex(idx).dropna()
        ggg_m = calc_metrics(ggg_state) if len(ggg_state) > 3 else {}
        p2_m = calc_metrics(p2_state) if len(p2_state) > 3 else {}
        state_delta_rows.append({
            "portfolio": pname, "state": state,
            "delta_ann_return_vs_ggg1": round((m.get("ann_return",np.nan) or 0) - (ggg_m.get("ann_return",0) or 0), 4),
            "delta_sharpe_vs_ggg1": round((m.get("sharpe",np.nan) or 0) - (ggg_m.get("sharpe",0) or 0), 4),
            "delta_ann_return_vs_phase2": round((m.get("ann_return",np.nan) or 0) - (p2_m.get("ann_return",0) or 0), 4),
        })

pd.DataFrame(state_summary_rows).to_csv(OUT / "phase3_state_summary.csv", index=False)
pd.DataFrame(state_delta_rows).to_csv(OUT / "phase3_state_deltas_vs_ggg1.csv", index=False)
pd.DataFrame([r for r in state_delta_rows if r.get("delta_ann_return_vs_phase2") is not None]).to_csv(
    OUT / "phase3_state_deltas_vs_phase2_best.csv", index=False)

# Sleeve-level exposure per state
sleeve_exp_rows = []
for pname in CANDIDATES:
    sf = L3 / f"portfolio_version_sleeve_weights_{pname}.csv"
    if not sf.exists():
        continue
    sw = pd.read_csv(sf, index_col=0, parse_dates=True)
    sw_ms = sw.join(msh[["market_state"]], how="left")
    for state, grp in sw_ms.groupby("market_state"):
        row = {"portfolio": pname, "state": state}
        for col in sw.columns:
            row[col] = round(float(grp[col].mean()), 4)
        sleeve_exp_rows.append(row)
pd.DataFrame(sleeve_exp_rows).to_csv(OUT / "phase3_state_exposure_summary.csv", index=False)


def state_diag_file(portfolio_names, state, fname):
    rows = []
    ggg1_sw = pd.read_csv(L3 / "portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv", index_col=0, parse_dates=True) if (L3 / "portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv").exists() else None
    for pname in portfolio_names:
        if pname not in returns:
            continue
        idx = msh[msh["market_state"] == state].index
        slc = returns[pname].reindex(idx).dropna()
        m = calc_metrics(slc, pname)
        ggg_slc = ggg1_ret.reindex(idx).dropna()
        ggg_m = calc_metrics(ggg_slc)
        sf = L3 / f"portfolio_version_sleeve_weights_{pname}.csv"
        avg_def = avg_off = avg_bil = np.nan
        if sf.exists():
            sw = pd.read_csv(sf, index_col=0, parse_dates=True).reindex(idx)
            avg_def = round(float(sw.get("composite_regime_defense_component", pd.Series([np.nan])).mean()), 4)
            avg_off = round(float(sw.get("composite_regime_offense_component", pd.Series([np.nan])).mean()), 4)
            avg_bil = round(float(sw.get("cash::BIL", pd.Series([np.nan])).mean()), 4)
        wf = L3 / f"portfolio_version_weights_{pname}.csv"
        avg_qqq = np.nan
        if wf.exists():
            w = pd.read_csv(wf, index_col=0, parse_dates=True).reindex(idx)
            avg_qqq = round(float(w["QQQ"].mean()), 4) if "QQQ" in w else np.nan
        rows.append({"portfolio": pname, "state": state,
                     "ann_return": m.get("ann_return"), "sharpe": m.get("sharpe"),
                     "max_drawdown": m.get("max_drawdown"),
                     "delta_vs_ggg1": round((m.get("ann_return",np.nan) or 0) - (ggg_m.get("ann_return",0) or 0), 4),
                     "avg_offense_sleeve": avg_off, "avg_defense_sleeve": avg_def,
                     "avg_cash_bil_sleeve": avg_bil, "avg_QQQ_etf": avg_qqq})
    pd.DataFrame(rows).to_csv(OUT / fname, index=False)

state_diag_file(CANDIDATES + ["ggg1","phase2_best"], "neutral_mixed", "phase3_neutral_cash_unlock_diagnostics.csv")
state_diag_file(CANDIDATES + ["ggg1","phase2_best"], "calm_trend", "phase3_calm_us_offense_diagnostics.csv")
state_diag_file(CANDIDATES + ["ggg1","phase2_best"], "recovery_confirmed", "phase3_recovery_participation_diagnostics.csv")
state_diag_file(CANDIDATES + ["ggg1","phase2_best"], "stressed_panic", "phase3_stress_protection_diagnostics.csv")
print(f"  Saved state summary, deltas, exposure, and diagnostic files")


# ──────────────────────────────────────────────
# PART I — RISK / REALISM / HIDDEN BETA
# ──────────────────────────────────────────────
print("\n=== PART I: Risk / realism / hidden beta ===")

ggg_m_full = calc_metrics(returns.get("ggg1", pd.Series(dtype=float)), "ggg1")
p2_m_full = calc_metrics(returns.get("phase2_best", pd.Series(dtype=float)), "phase2_best")
spy_ann_full = calc_metrics(spy_weekly, "spy").get("ann_return", 0)
ggg_bear_m = calc_metrics(ws(returns.get("ggg1", pd.Series(dtype=float)), "2022-01-01", "2022-12-31"))
ggg_turn_path = L3 / "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv"
ggg_turn = float(pd.read_csv(ggg_turn_path, index_col=0)["turnover"].mean()) if ggg_turn_path.exists() else np.nan

risk_rows, hb_rows, bear_rows, fail_rows, sig_perf_rows = [], [], [], [], []

for pname in CANDIDATES:
    if pname not in returns:
        fail_rows.append({"portfolio": pname, "reason": "BUILD_FAILED"})
        continue
    ret = returns[pname]
    m_full = calc_metrics(ret, pname)
    m_2020 = calc_metrics(ws(ret, "2020-01-01", None))
    m_bear = calc_metrics(ws(ret, "2022-01-01", "2022-12-31"))

    rp = L3 / f"portfolio_version_returns_{pname}.csv"
    avg_turn = np.nan
    if rp.exists():
        rdf = pd.read_csv(rp, index_col=0, parse_dates=True)
        if "turnover" in rdf.columns:
            avg_turn = float(rdf["turnover"].mean())

    wp = L3 / f"portfolio_version_weights_{pname}.csv"
    avg_bil = avg_qqq = np.nan
    if wp.exists():
        w = pd.read_csv(wp, index_col=0, parse_dates=True)
        avg_bil = float(w["BIL"].mean()) if "BIL" in w else np.nan
        avg_qqq = float(w["QQQ"].mean()) if "QQQ" in w else np.nan

    common = ret.dropna().index.intersection(spy_weekly.dropna().index)
    cov = np.cov(ret.reindex(common), spy_weekly.reindex(common))
    beta_spy = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    corr_spy = float(ret.reindex(common).corr(spy_weekly.reindex(common)))
    ggg_common = returns["ggg1"].dropna().index.intersection(spy_weekly.dropna().index) if "ggg1" in returns else common
    ggg_cov = np.cov(returns["ggg1"].reindex(ggg_common), spy_weekly.reindex(ggg_common)) if "ggg1" in returns else np.zeros((2,2))
    ggg_beta = ggg_cov[0,1]/ggg_cov[1,1] if ggg_cov[1,1]>0 else np.nan

    ann_improve = (m_full.get("ann_return",0) or 0) - (ggg_m_full.get("ann_return",0) or 0)
    beta_attr = (beta_spy - ggg_beta) * spy_ann_full if not (np.isnan(beta_spy) or np.isnan(ggg_beta)) else np.nan
    pct_from_beta = abs(beta_attr)/abs(ann_improve) if ann_improve and not np.isnan(beta_attr) else np.nan

    passes_mandate = (m_full.get("max_drawdown",-1) >= -0.22 and (m_full.get("sharpe",0) or 0) >= 0.90)
    bear_ok = (m_bear.get("ann_return",-99) or -99) >= (ggg_bear_m.get("ann_return",-99) or -99) - 0.04
    disguised = (beta_spy is not None and not np.isnan(beta_spy) and beta_spy > 0.30) or corr_spy > 0.50

    risk_rows.append({"portfolio": pname,
                      "full_ann_return": round(m_full.get("ann_return",np.nan), 4),
                      "full_sharpe": round(m_full.get("sharpe",np.nan), 4),
                      "full_max_dd": round(m_full.get("max_drawdown",np.nan), 4),
                      "holdout_2020_return": round(m_2020.get("ann_return",np.nan), 4),
                      "holdout_2020_sharpe": round(m_2020.get("sharpe",np.nan), 4),
                      "avg_BIL": round(avg_bil, 4) if not np.isnan(avg_bil) else np.nan,
                      "avg_QQQ": round(avg_qqq, 4) if not np.isnan(avg_qqq) else np.nan,
                      "avg_turnover": round(avg_turn, 4) if not np.isnan(avg_turn) else np.nan,
                      "turnover_ratio_vs_ggg1": round(avg_turn/ggg_turn, 3) if not np.isnan(avg_turn) and not np.isnan(ggg_turn) and ggg_turn>0 else np.nan,
                      "passes_mandate": passes_mandate, "bear_ok": bear_ok, "disguised_spy": disguised})

    hb_rows.append({"portfolio": pname, "beta_spy": round(beta_spy, 4),
                    "beta_delta_vs_ggg1": round(beta_spy - ggg_beta, 4) if not np.isnan(ggg_beta) else np.nan,
                    "corr_spy": round(corr_spy, 4), "ann_improve_vs_ggg1": round(ann_improve, 4),
                    "pct_from_beta": round(pct_from_beta, 3) if not np.isnan(pct_from_beta) else np.nan,
                    "hidden_beta_risk": "HIGH" if pct_from_beta and pct_from_beta > 0.50 else "LOW"})

    bear_rows.append({"portfolio": pname,
                      "bear_2022_return": round(m_bear.get("ann_return",np.nan), 4),
                      "ggg1_bear_2022": round(ggg_bear_m.get("ann_return",np.nan), 4),
                      "delta_vs_ggg1_bear": round((m_bear.get("ann_return",0) or 0)-(ggg_bear_m.get("ann_return",0) or 0), 4),
                      "bear_ok": bear_ok})

    # Signal-active performance
    idx_on = msh[breadth_signal].index
    idx_off = msh[~breadth_signal].index
    sig_on_ret = ret.reindex(idx_on).dropna()
    sig_off_ret = ret.reindex(idx_off).dropna()
    sig_perf_rows.append({"portfolio": pname,
                           "signal_active_ann_return": round(float((1+sig_on_ret.mean())**WEEKS-1), 4) if len(sig_on_ret) > 4 else np.nan,
                           "signal_inactive_ann_return": round(float((1+sig_off_ret.mean())**WEEKS-1), 4) if len(sig_off_ret) > 4 else np.nan,
                           "signal_active_weeks": len(sig_on_ret), "signal_inactive_weeks": len(sig_off_ret)})

pd.DataFrame(risk_rows).to_csv(OUT / "phase3_risk_realism_checks.csv", index=False)
pd.DataFrame(hb_rows).to_csv(OUT / "phase3_hidden_beta_cash_checks.csv", index=False)
pd.DataFrame(bear_rows).to_csv(OUT / "phase3_2022_bear_check.csv", index=False)
pd.DataFrame(sig_perf_rows).to_csv(OUT / "phase3_signal_active_candidate_performance.csv", index=False)
pd.DataFrame(fail_rows if fail_rows else [{"portfolio":"none","reason":"all_built"}]).to_csv(
    OUT / "phase3_candidate_failure_reasons.csv", index=False)

print("  Risk / hidden beta summary:")
for r in risk_rows:
    hb = next((h for h in hb_rows if h["portfolio"]==r["portfolio"]), {})
    print(f"    {r['portfolio']}: return={r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} "
          f"maxDD={r['full_max_dd']:.3%} BIL={r['avg_BIL']:.3%} QQQ={r['avg_QQQ']:.3%} "
          f"beta={hb.get('beta_spy','?'):.3f} mandate={'OK' if r['passes_mandate'] else 'FAIL'} "
          f"bear={'OK' if r['bear_ok'] else 'FAIL'}")


# ──────────────────────────────────────────────
# PART J — SELECTION
# ──────────────────────────────────────────────
print("\n=== PART J: Selection ===")

sel_rows = []
for pname in CANDIDATES:
    if pname not in returns:
        sel_rows.append({"portfolio": pname, "classification": "REJECT", "reason": "build_failed"})
        continue
    m_full = calc_metrics(returns[pname])
    m_2020 = calc_metrics(ws(returns[pname], "2020-01-01", None))
    m_2021 = calc_metrics(ws(returns[pname], "2021-01-01", None))
    m_bear = calc_metrics(ws(returns[pname], "2022-01-01", "2022-12-31"))
    ggg_2020 = calc_metrics(ws(returns.get("ggg1", pd.Series(dtype=float)), "2020-01-01", None))
    p2_2020 = calc_metrics(ws(returns.get("phase2_best", pd.Series(dtype=float)), "2020-01-01", None))

    ann = m_full.get("ann_return", 0) or 0
    sharpe = m_full.get("sharpe", 0) or 0
    max_dd = m_full.get("max_drawdown", -1) or -1
    hold_ret = m_2020.get("ann_return", 0) or 0
    hold_sharpe = m_2020.get("sharpe", 0) or 0
    bear_ret = m_bear.get("ann_return", -99) or -99
    ggg_ann = ggg_m_full.get("ann_return", 0) or 0
    p2_ann = p2_m_full.get("ann_return", 0) or 0

    above_ggg = ann > ggg_ann
    above_p2 = ann > p2_ann
    hold_above_ggg = hold_ret > (ggg_2020.get("ann_return",0) or 0)
    hold_above_p2 = hold_ret > (p2_2020.get("ann_return",0) or 0)
    sharpe_ok = sharpe >= 0.90
    mandate_ok = max_dd >= -0.22
    bear_ok_flag = bear_ret >= (ggg_bear_m.get("ann_return",-99) or -99) - 0.04

    hr = next((h for h in hb_rows if h["portfolio"]==pname), {})
    disguised = (hr.get("beta_spy",0) or 0) > 0.30 or (hr.get("corr_spy",0) or 0) > 0.50

    if not mandate_ok:
        cls = "REJECT"; reason = f"max_dd {max_dd:.2%} exceeds -22% limit"
    elif not sharpe_ok:
        cls = "REJECT"; reason = f"Sharpe {sharpe:.3f} below 0.90"
    elif not bear_ok_flag:
        cls = "REJECT"; reason = "2022 bear protection materially worse than GGG1"
    elif disguised:
        cls = "REJECT"; reason = "disguised SPY/QQQ"
    elif not above_ggg:
        cls = "REJECT"; reason = f"return {ann:.2%} does not beat GGG1 {ggg_ann:.2%}"
    elif ann >= 0.085 and sharpe >= 0.95 and max_dd >= -0.20 and above_p2 and hold_above_p2:
        cls = "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
        reason = "Meets primary mandate: return>=8.5%, Sharpe>=0.95, maxDD>=-20%, beats both GGG1 and P2"
    elif above_ggg and above_p2 and sharpe_ok and mandate_ok and bear_ok_flag:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW"
        reason = "Beats GGG1 and Phase2 best, passes all guardrails"
    elif above_ggg and sharpe_ok and bear_ok_flag:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW" if hold_above_ggg else "KEEP_AS_RESEARCH_ONLY"
        reason = "Beats GGG1 but not Phase2 best, or holdout modest"
    else:
        cls = "KEEP_AS_RESEARCH_ONLY"; reason = "Partial improvement"

    sel_rows.append({"portfolio": pname, "classification": cls, "reason": reason,
                     "full_ann_return": round(ann, 4), "full_sharpe": round(sharpe, 4),
                     "full_max_dd": round(max_dd, 4), "holdout_2020_return": round(hold_ret, 4),
                     "holdout_2020_sharpe": round(hold_sharpe, 4), "bear_2022_return": round(bear_ret, 4),
                     "beats_ggg1": above_ggg, "beats_phase2_best": above_p2,
                     "mandate_ok": mandate_ok, "bear_ok": bear_ok_flag, "disguised": disguised})

sel_df = pd.DataFrame(sel_rows)
sel_df.to_csv(OUT / "phase3_selection_table.csv", index=False)
print("  Selection results:")
for r in sel_rows:
    print(f"    {r['portfolio']}: {r['classification']}")
    print(f"      return={r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} maxDD={r['full_max_dd']:.3%} | {r['reason']}")

best_candidate = None
for cls_prio in ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT", "KEEP_AS_AGGRESSIVE_SHADOW"]:
    for row in sel_rows:
        if row["classification"] == cls_prio:
            if best_candidate is None or row["full_ann_return"] > sel_df[sel_df["portfolio"]==best_candidate]["full_ann_return"].values[0]:
                best_candidate = row["portfolio"]
    if best_candidate and next(r["classification"] for r in sel_rows if r["portfolio"]==best_candidate) == cls_prio:
        break


# ──────────────────────────────────────────────
# PART K — AUDITS
# ──────────────────────────────────────────────
print("\n=== PART K: Audits ===")
audit_rows = []
audit_lines = ["# Phase 3 Audit Summary\n"]

if best_candidate:
    best_cls = next(r["classification"] for r in sel_rows if r["portfolio"]==best_candidate)
    print(f"  Best candidate: {best_candidate} ({best_cls})")
    is_challenger = best_cls == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
    for audit_name in ["research_committee_report", "backtest_realism_audit", "allocator_benchmark_audit", "robustness_simulation_audit"]:
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
            log = OUT / f"phase3_{audit_name.replace('_report','')}_quick.log"
            with open(log, "w") as f:
                f.write(res.stdout[-4000:] + "\n" + res.stderr[-2000:])
            audit_rows.append({"audit": audit_name, "status": status})
            audit_lines.append(f"## {audit_name}: {status}\n")
        except subprocess.TimeoutExpired:
            audit_rows.append({"audit": audit_name, "status": "TIMEOUT"})
else:
    print("  No qualifying candidate — skipping audits")
    audit_lines.append("No qualifying candidate — audits skipped.\n")

pd.DataFrame(audit_rows).to_csv(OUT / "phase3_audit_results.csv", index=False)
with open(OUT / "phase3_audit_summary.md", "w") as f:
    f.writelines(audit_lines)


# ──────────────────────────────────────────────
# PART L — NEXT PHASE DECISION
# ──────────────────────────────────────────────
print("\n=== PART L: Next phase decision ===")

n_challenger = sum(1 for r in sel_rows if r["classification"]=="PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT")
n_shadow = sum(1 for r in sel_rows if r["classification"]=="KEEP_AS_AGGRESSIVE_SHADOW")
n_reject = sum(1 for r in sel_rows if r["classification"]=="REJECT")
all_reject = n_challenger + n_shadow == 0

best_return = max((r["full_ann_return"] for r in sel_rows if r["classification"] in
                   ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT","KEEP_AS_AGGRESSIVE_SHADOW"]), default=0)

if n_challenger > 0:
    decision = "PROMOTE_PHASE3_TO_PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
    rationale = f"{best_candidate} satisfies the aggressive mandate with return>={best_return:.2%}, Sharpe>=0.95, maxDD>=-20%, beats both GGG1 and Phase2."
elif n_shadow > 0 and best_return >= 0.08:
    decision = "KEEP_PHASE3_AS_AGGRESSIVE_SHADOW"
    rationale = f"{best_candidate} ({best_return:.2%}) improves on both GGG1 and Phase2 with acceptable risk but doesn't fully satisfy 8.5%/0.95 Sharpe guardrails."
elif n_shadow > 0:
    decision = "PROCEED_TO_PHASE3B_REFINED_US_OFFENSE_ENGINE"
    rationale = f"Phase 3 shows improvement (best {best_return:.2%}) but needs refinement. Consider stronger US offense concentration or better breadth signal thresholds."
elif all_reject:
    decision = "PROCEED_TO_PHASE4_SECTOR_BREADTH_ROTATION"
    rationale = "All Phase 3 candidates rejected. Pure US equity offense in high-breadth states is insufficient. Sector rotation/leadership signals needed."
else:
    decision = "PROCEED_TO_PHASE4_SECTOR_BREADTH_ROTATION"
    rationale = "Phase 3 improvements are marginal. Sector leadership information is the missing return source."

pd.DataFrame([{"decision": decision, "best_candidate": best_candidate or "none",
               "best_return": round(best_return, 4), "rationale": rationale,
               "n_challenger": n_challenger, "n_shadow": n_shadow, "n_reject": n_reject}]).to_csv(
    OUT / "phase3_next_phase_decision.csv", index=False)

with open(OUT / "phase3_protocol.json", "w") as f:
    json.dump({
        "phase": "phase_3_breadth_confirmed_us_offense",
        "date": "2026-05-07",
        "production_pin": "improved_phase2b_regime_confidence_boost",
        "production_candidate": "improved_phaseggg_confirmed_only_robust_offense",
        "phase2_aggressive_shadow": "improved_phase2_aggressive_neutral_cash_unlock",
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
print("\nDone. Phase 3 Breadth-Confirmed US Offense Upgrade complete.")
print("No production pins changed. No auto-promotion.")
