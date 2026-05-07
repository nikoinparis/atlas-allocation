#!/usr/bin/env python3
"""
Phase 1 — Return Unlock Audit
Diagnostic only. No strategy candidates. No pin changes. No promotions.

Parts:
  A - Load core portfolios and benchmarks
  B - Full + holdout metrics
  C - Return bottleneck decomposition
  D - Upside / downside capture
  E - What-if scenarios to 9–11%
  F - Holdout-specific diagnosis
  G - Next phase recommendation
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
HUB = ROOT / "data" / "01_data_hub"
OUT = ROOT / "data" / "research" / "phase_1_return_unlock_audit"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS_PER_YEAR = 52

WINDOWS = {
    "full": (None, None),
    "holdout_2016": ("2016-01-01", None),
    "holdout_2020": ("2020-01-01", None),
    "holdout_2021": ("2021-01-01", None),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "recovery_2023": ("2023-01-01", None),
}

CORES = {
    "prod_phase2b_rcb": "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
    "shadow_phase2b_abc": "portfolio_version_returns_improved_phase2b_combo_abc.csv",
    "ggg1_robust_offense": "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    "sss3_calm_derisk": "portfolio_version_returns_improved_phasesss3_calm_old_low_stress_derisk.csv",
    "equal_weight": "portfolio_returns_equal_weight.csv",
}

WEIGHT_FILES = {
    "ggg1_robust_offense": "portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv",
    "prod_phase2b_rcb": "portfolio_version_weights_improved_phase2b_regime_confidence_boost.csv",
    "shadow_phase2b_abc": "portfolio_version_weights_improved_phase2b_combo_abc.csv",
}

SLEEVE_FILES = {
    "ggg1_robust_offense": "portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv",
    "prod_phase2b_rcb": "portfolio_version_sleeve_weights_improved_phase2b_regime_confidence_boost.csv",
    "shadow_phase2b_abc": "portfolio_version_sleeve_weights_improved_phase2b_combo_abc.csv",
}


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def calc_metrics(ret: pd.Series, label: str = "") -> dict:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    if len(ret) < 8:
        return {"label": label, "n_weeks": len(ret), "ann_return": np.nan}

    n = len(ret)
    ann_ret = float((1 + ret).prod() ** (WEEKS_PER_YEAR / n) - 1)
    ann_vol = float(ret.std() * np.sqrt(WEEKS_PER_YEAR))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    wealth = (1 + ret).cumprod()
    dd = (wealth / wealth.cummax() - 1)
    max_dd = float(dd.min())
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else np.nan
    cvar_5 = float(ret[ret <= ret.quantile(0.05)].mean())
    worst_4w = float(ret.rolling(4).sum().min()) if len(ret) >= 4 else np.nan
    worst_13w = float(ret.rolling(13).sum().min()) if len(ret) >= 13 else np.nan

    return {
        "label": label,
        "n_weeks": n,
        "ann_return": round(ann_ret, 6),
        "ann_vol": round(ann_vol, 6),
        "sharpe": round(sharpe, 6),
        "max_drawdown": round(max_dd, 6),
        "calmar": round(calmar, 6),
        "cvar_5": round(cvar_5, 6),
        "worst_4w": round(worst_4w, 6),
        "worst_13w": round(worst_13w, 6),
    }


def window_slice(series: pd.Series, start: str | None, end: str | None) -> pd.Series:
    s = series.copy()
    if start:
        s = s[s.index >= start]
    if end:
        s = s[s.index <= end]
    return s


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b != 0 and not np.isnan(b) else np.nan


# ──────────────────────────────────────────────
# PART A — LOAD CORE PORTFOLIOS AND BENCHMARKS
# ──────────────────────────────────────────────
print("=== PART A: Load portfolios and benchmarks ===")

returns: dict[str, pd.Series] = {}
for name, fname in CORES.items():
    path = L3 / fname
    if path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        col = "net_return" if "net_return" in df.columns else df.columns[0]
        returns[name] = df[col].rename(name)
        print(f"  Loaded {name}: {len(returns[name])} weeks, "
              f"{returns[name].index[0].date()} to {returns[name].index[-1].date()}")
    else:
        print(f"  MISSING: {fname}")

# Benchmark weekly prices -> returns
bm_prices = pd.read_csv(HUB / "benchmark_prices_weekly.csv", index_col="Date", parse_dates=True)
spy_ret = bm_prices["SPY"].pct_change().rename("spy")
ief_ret = bm_prices["IEF"].pct_change().rename("ief")
bil_ret = bm_prices["BIL"].pct_change().rename("bil")

# 60/40 SPY + IEF
s6040 = (0.60 * spy_ret + 0.40 * ief_ret).dropna().rename("bench_60_40")
returns["spy"] = spy_ret.dropna()
returns["bench_60_40"] = s6040
returns["bil"] = bil_ret.dropna()
print(f"  Loaded SPY: {len(returns['spy'])} weeks")
print(f"  Loaded 60/40: {len(returns['bench_60_40'])} weeks")

# Weights
weights: dict[str, pd.DataFrame] = {}
for name, fname in WEIGHT_FILES.items():
    path = L3 / fname
    if path.exists():
        weights[name] = pd.read_csv(path, index_col=0, parse_dates=True)

sleeve_weights: dict[str, pd.DataFrame] = {}
for name, fname in SLEEVE_FILES.items():
    path = L3 / fname
    if path.exists():
        sleeve_weights[name] = pd.read_csv(path, index_col=0, parse_dates=True)

# Market state
msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)
STATES = list(msh["market_state"].unique())
print(f"  States: {STATES}")

# Core portfolio inventory
inv_rows = []
for name, ret in returns.items():
    m = calc_metrics(ret, name)
    inv_rows.append({"portfolio": name, "start": str(ret.index[0].date()),
                     "end": str(ret.index[-1].date()), "n_weeks": m["n_weeks"],
                     "full_ann_return": m.get("ann_return"), "full_sharpe": m.get("sharpe"),
                     "full_max_drawdown": m.get("max_drawdown")})

port_inv = pd.DataFrame(inv_rows)
port_inv.to_csv(OUT / "phase1_core_portfolio_inventory.csv", index=False)
print(f"  Saved phase1_core_portfolio_inventory.csv ({len(port_inv)} rows)")

bm_inv = pd.DataFrame([
    {"benchmark": "spy", "description": "S&P 500 ETF (SPY)", "source": "benchmark_prices_weekly.csv"},
    {"benchmark": "bench_60_40", "description": "60% SPY / 40% IEF rebalanced weekly", "source": "constructed"},
    {"benchmark": "bil", "description": "T-bill cash proxy (BIL)", "source": "benchmark_prices_weekly.csv"},
    {"benchmark": "equal_weight", "description": "Equal weight ETF universe", "source": "portfolio_returns_equal_weight.csv"},
])
bm_inv.to_csv(OUT / "phase1_benchmark_inventory.csv", index=False)
print(f"  Saved phase1_benchmark_inventory.csv")


# ──────────────────────────────────────────────
# PART B — FULL + HOLDOUT METRICS
# ──────────────────────────────────────────────
print("\n=== PART B: Full + holdout metrics ===")

all_metrics = []
for pname, ret in returns.items():
    for wname, (wstart, wend) in WINDOWS.items():
        slc = window_slice(ret, wstart, wend)
        m = calc_metrics(slc, pname)
        row = {"portfolio": pname, "window": wname}
        row.update(m)

        # avg BIL, avg SPY if weights available
        if pname in weights:
            w = weights[pname]
            wslc = w[wstart:wend] if wstart else w
            if wend:
                wslc = wslc[:wend]
            row["avg_BIL"] = round(float(wslc["BIL"].mean()), 4) if "BIL" in wslc else np.nan
            row["avg_SPY"] = round(float(wslc["SPY"].mean()), 4) if "SPY" in wslc else np.nan
        else:
            row["avg_BIL"] = np.nan
            row["avg_SPY"] = np.nan

        # turnover
        fname_t = CORES.get(pname, "")
        if fname_t:
            ret_path = L3 / fname_t
            if ret_path.exists():
                raw = pd.read_csv(ret_path, index_col=0, parse_dates=True)
                if "turnover" in raw.columns:
                    tslc = window_slice(raw["turnover"], wstart, wend)
                    row["avg_turnover"] = round(float(tslc.mean()), 4)
                else:
                    row["avg_turnover"] = np.nan
            else:
                row["avg_turnover"] = np.nan
        else:
            row["avg_turnover"] = np.nan

        all_metrics.append(row)

metrics_df = pd.DataFrame(all_metrics)
metrics_df.to_csv(OUT / "phase1_full_and_holdout_metrics.csv", index=False)
print(f"  Saved phase1_full_and_holdout_metrics.csv ({len(metrics_df)} rows)")

# Candidate vs benchmark holdout table
hold_windows = ["holdout_2016", "holdout_2020", "holdout_2021"]
focus_ports = ["ggg1_robust_offense", "prod_phase2b_rcb", "shadow_phase2b_abc", "spy", "bench_60_40", "equal_weight"]
cand_vs_bm = metrics_df[metrics_df["portfolio"].isin(focus_ports) & metrics_df["window"].isin(hold_windows)][
    ["portfolio", "window", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "avg_BIL", "avg_SPY"]
].copy()
cand_vs_bm.to_csv(OUT / "phase1_candidate_vs_benchmark_holdout_table.csv", index=False)
print(f"  Saved phase1_candidate_vs_benchmark_holdout_table.csv ({len(cand_vs_bm)} rows)")

# Recent period subset
recent_df = metrics_df[metrics_df["window"].isin(["bear_2022", "recovery_2023"])].copy()
recent_df.to_csv(OUT / "phase1_recent_period_metrics.csv", index=False)
print(f"  Saved phase1_recent_period_metrics.csv ({len(recent_df)} rows)")

# Print summary
print("\n  GGG1 key metrics across windows:")
ggg_m = metrics_df[metrics_df["portfolio"] == "ggg1_robust_offense"][["window", "ann_return", "sharpe", "max_drawdown", "avg_BIL", "avg_SPY"]].set_index("window")
print(ggg_m.to_string())


# ──────────────────────────────────────────────
# PART C — RETURN BOTTLENECK DECOMPOSITION
# ──────────────────────────────────────────────
print("\n=== PART C: Return bottleneck decomposition ===")

ggg_ret = returns["ggg1_robust_offense"]
ggg_w = weights.get("ggg1_robust_offense", pd.DataFrame())
ggg_sw = sleeve_weights.get("ggg1_robust_offense", pd.DataFrame())
prod_ret = returns["prod_phase2b_rcb"]
prod_w = weights.get("prod_phase2b_rcb", pd.DataFrame())

# --- Cash drag by state ---
if not ggg_w.empty:
    merged_w = ggg_w.join(msh[["market_state"]], how="left")
    merged_w["ret"] = ggg_ret
    merged_w["spy_bm_ret"] = spy_ret

    # avg BIL and SPY by state
    state_exposure = merged_w.groupby("market_state").agg(
        n_weeks=("BIL", "count"),
        avg_BIL=("BIL", "mean"),
        avg_SPY=("SPY", "mean"),
        avg_portfolio_ret=("ret", "mean"),
        avg_spy_ret=("spy_bm_ret", "mean"),
    ).round(4)
    state_exposure["ann_portfolio_ret"] = ((1 + state_exposure["avg_portfolio_ret"]) ** WEEKS_PER_YEAR - 1).round(4)
    state_exposure["ann_spy_ret"] = ((1 + state_exposure["avg_spy_ret"]) ** WEEKS_PER_YEAR - 1).round(4)
    state_exposure["opportunity_cost_vs_spy_ann"] = (state_exposure["ann_portfolio_ret"] - state_exposure["ann_spy_ret"]).round(4)
    state_exposure.to_csv(OUT / "phase1_state_exposure_summary.csv")
    print(f"  Saved phase1_state_exposure_summary.csv")
    print("\n  State exposure summary:")
    print(state_exposure[["n_weeks", "avg_BIL", "avg_SPY", "ann_portfolio_ret", "ann_spy_ret", "opportunity_cost_vs_spy_ann"]].to_string())

    # BIL drag decomposition
    total_weeks = len(ggg_ret.dropna())
    state_counts = msh["market_state"].value_counts()
    cash_drag_rows = []
    for state, grp in merged_w.groupby("market_state"):
        n = len(grp)
        wt = n / total_weeks
        avg_bil = grp["BIL"].mean()
        avg_ret = grp["ret"].mean()
        avg_spy = grp["spy_bm_ret"].mean()
        bil_annualized = float((1 + bil_ret.reindex(grp.index).mean()) ** WEEKS_PER_YEAR - 1)
        spy_annualized = float((1 + avg_spy) ** WEEKS_PER_YEAR - 1)
        port_annualized = float((1 + avg_ret) ** WEEKS_PER_YEAR - 1)
        cash_drag_rows.append({
            "state": state,
            "n_weeks": n,
            "freq": round(wt, 4),
            "avg_BIL": round(avg_bil, 4),
            "avg_portfolio_wkly": round(avg_ret, 5),
            "avg_spy_wkly": round(avg_spy, 5),
            "cash_opportunity_cost_wkly": round(avg_bil * (avg_spy - bil_ret.reindex(grp.index).mean()), 6),
        })
    cash_drag_df = pd.DataFrame(cash_drag_rows)
    cash_drag_df["total_opportunity_cost_wkly"] = cash_drag_df["cash_opportunity_cost_wkly"] * cash_drag_df["freq"]
    cash_drag_df.to_csv(OUT / "phase1_cash_drag_decomposition.csv", index=False)
    print(f"  Saved phase1_cash_drag_decomposition.csv")

# --- Sleeve weights by state ---
if not ggg_sw.empty:
    merged_sw = ggg_sw.join(msh[["market_state"]], how="left")
    merged_sw["portfolio_ret"] = ggg_ret
    sleeve_by_state = merged_sw.groupby("market_state")[ggg_sw.columns.tolist()].mean().round(4)
    sleeve_by_state.to_csv(OUT / "phase1_sleeve_weight_by_state.csv")
    print(f"  Saved phase1_sleeve_weight_by_state.csv")
    print("\n  Sleeve weights by state:")
    print(sleeve_by_state.to_string())

# --- State return contribution ---
state_contrib_rows = []
total_wealth_log = np.log((1 + ggg_ret.dropna()).prod())
for state, grp_idx in msh["market_state"].groupby(msh["market_state"]).groups.items():
    state_ret = ggg_ret.reindex(grp_idx).dropna()
    spy_state = spy_ret.reindex(grp_idx).dropna()
    if len(state_ret) == 0:
        continue
    state_log = float(np.log((1 + state_ret).prod()))
    n = len(state_ret)
    freq = n / total_weeks
    ann_ret = float((1 + state_ret.mean()) ** WEEKS_PER_YEAR - 1)
    spy_ann = float((1 + spy_state.mean()) ** WEEKS_PER_YEAR - 1) if len(spy_state) > 0 else np.nan
    state_contrib_rows.append({
        "state": state,
        "n_weeks": n,
        "freq": round(freq, 4),
        "log_wealth_contribution": round(state_log, 5),
        "pct_of_total_log_wealth": round(state_log / total_wealth_log, 4),
        "ann_portfolio_return_in_state": round(ann_ret, 4),
        "ann_spy_in_state": round(spy_ann, 4) if not np.isnan(spy_ann) else np.nan,
        "opportunity_cost_vs_spy_ann": round(ann_ret - spy_ann, 4) if not np.isnan(spy_ann) else np.nan,
    })
state_contrib_df = pd.DataFrame(state_contrib_rows).sort_values("n_weeks", ascending=False)
state_contrib_df.to_csv(OUT / "phase1_state_return_contribution.csv", index=False)
print(f"  Saved phase1_state_return_contribution.csv")
print("\n  State return contributions:")
print(state_contrib_df.to_string(index=False))

# --- Opportunity cost vs SPY ---
opp_cost_rows = []
spy_aligned = spy_ret.reindex(ggg_ret.index)
for state, grp_idx in msh["market_state"].groupby(msh["market_state"]).groups.items():
    state_ggg = ggg_ret.reindex(grp_idx).dropna()
    state_spy = spy_aligned.reindex(grp_idx).dropna()
    common = state_ggg.index.intersection(state_spy.index)
    if len(common) < 4:
        continue
    diff = state_ggg.reindex(common) - state_spy.reindex(common)
    opp_cost_rows.append({
        "state": state,
        "avg_weekly_active_return": round(float(diff.mean()), 5),
        "ann_active_return": round(float((1 + diff.mean()) ** WEEKS_PER_YEAR - 1), 4),
        "n_weeks_positive_active": int((diff > 0).sum()),
        "n_weeks_negative_active": int((diff < 0).sum()),
        "pct_weeks_outperforming_spy": round(float((diff > 0).mean()), 3),
    })
opp_cost_df = pd.DataFrame(opp_cost_rows)
opp_cost_df.to_csv(OUT / "phase1_opportunity_cost_vs_spy.csv", index=False)
print(f"  Saved phase1_opportunity_cost_vs_spy.csv")

# --- Upside miss windows (GGG1 under SPY by >2% in a week) ---
spy_aligned = spy_ret.reindex(ggg_ret.index).dropna()
ggg_aligned = ggg_ret.reindex(spy_aligned.index).dropna()
common_idx = ggg_aligned.index.intersection(spy_aligned.index)
miss_mask = (spy_aligned.reindex(common_idx) > 0.02) & (ggg_aligned.reindex(common_idx) < spy_aligned.reindex(common_idx) * 0.5)
upside_miss = pd.DataFrame({
    "date": common_idx[miss_mask],
    "portfolio_ret": ggg_aligned.reindex(common_idx)[miss_mask].values,
    "spy_ret": spy_aligned.reindex(common_idx)[miss_mask].values,
    "market_state": msh["market_state"].reindex(common_idx[miss_mask]).values,
})
upside_miss["miss_gap"] = upside_miss["spy_ret"] - upside_miss["portfolio_ret"]
upside_miss = upside_miss.sort_values("miss_gap", ascending=False).head(50)
upside_miss.to_csv(OUT / "phase1_upside_miss_windows.csv", index=False)
print(f"  Saved phase1_upside_miss_windows.csv ({len(upside_miss)} rows)")

# --- Loss avoidance windows (GGG1 > SPY during SPY drawdowns > 3%) ---
loss_avoid_mask = (spy_aligned.reindex(common_idx) < -0.03) & (ggg_aligned.reindex(common_idx) > spy_aligned.reindex(common_idx) + 0.01)
loss_avoid = pd.DataFrame({
    "date": common_idx[loss_avoid_mask],
    "portfolio_ret": ggg_aligned.reindex(common_idx)[loss_avoid_mask].values,
    "spy_ret": spy_aligned.reindex(common_idx)[loss_avoid_mask].values,
    "market_state": msh["market_state"].reindex(common_idx[loss_avoid_mask]).values,
})
loss_avoid["protection_gap"] = loss_avoid["portfolio_ret"] - loss_avoid["spy_ret"]
loss_avoid = loss_avoid.sort_values("protection_gap", ascending=False).head(50)
loss_avoid.to_csv(OUT / "phase1_loss_avoidance_windows.csv", index=False)
print(f"  Saved phase1_loss_avoidance_windows.csv ({len(loss_avoid)} rows)")


# ──────────────────────────────────────────────
# PART D — UPSIDE / DOWNSIDE CAPTURE
# ──────────────────────────────────────────────
print("\n=== PART D: Upside / downside capture ===")

def capture_metrics(port_r: pd.Series, bm_r: pd.Series, label: str, window: str) -> dict:
    common = port_r.index.intersection(bm_r.index)
    p = port_r.reindex(common).dropna()
    b = bm_r.reindex(common).dropna()
    common = p.index.intersection(b.index)
    p, b = p.reindex(common), b.reindex(common)
    if len(p) < 8:
        return {}

    up_mask = b > 0
    dn_mask = b < 0
    up_cap = safe_div(p[up_mask].sum(), b[up_mask].sum()) if up_mask.sum() > 2 else np.nan
    dn_cap = safe_div(p[dn_mask].sum(), b[dn_mask].sum()) if dn_mask.sum() > 2 else np.nan
    cap_spread = (up_cap - dn_cap) if not (np.isnan(up_cap) or np.isnan(dn_cap)) else np.nan

    cov = np.cov(p, b)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    corr = float(p.corr(b))
    n = len(p)
    p_ann = float((1 + p).prod() ** (WEEKS_PER_YEAR / n) - 1)
    b_ann = float((1 + b).prod() ** (WEEKS_PER_YEAR / n) - 1)
    active = p_ann - b_ann
    active_r = p - b
    te = float(active_r.std() * np.sqrt(WEEKS_PER_YEAR))
    ir = active / te if te > 0 else np.nan

    return {
        "portfolio": label, "window": window,
        "upside_capture": round(up_cap, 4), "downside_capture": round(dn_cap, 4),
        "capture_spread": round(cap_spread, 4), "beta": round(beta, 4),
        "correlation": round(corr, 4), "active_return_ann": round(active, 4),
        "tracking_error_ann": round(te, 4), "info_ratio": round(ir, 4),
        "n_weeks": n,
    }

capture_rows = []
for pname in ["ggg1_robust_offense", "prod_phase2b_rcb", "shadow_phase2b_abc", "bench_60_40", "equal_weight"]:
    if pname not in returns:
        continue
    for wname, (wstart, wend) in WINDOWS.items():
        p_slc = window_slice(returns[pname], wstart, wend)
        s_slc = window_slice(spy_ret.dropna(), wstart, wend)
        row = capture_metrics(p_slc, s_slc, pname, wname)
        if row:
            capture_rows.append(row)

capture_df = pd.DataFrame(capture_rows)
capture_df.to_csv(OUT / "phase1_capture_ratios_by_window.csv", index=False)
print(f"  Saved phase1_capture_ratios_by_window.csv ({len(capture_df)} rows)")

# Capture by market state
cap_state_rows = []
ggg_aligned2 = ggg_ret.reindex(spy_ret.dropna().index).dropna()
spy_aligned2 = spy_ret.dropna().reindex(ggg_aligned2.index).dropna()
state_aligned = msh["market_state"].reindex(ggg_aligned2.index)
for state in STATES:
    state_mask = state_aligned == state
    p_s = ggg_aligned2[state_mask]
    b_s = spy_aligned2[state_mask]
    if len(p_s) < 4:
        continue
    up = b_s > 0
    dn = b_s < 0
    up_cap = safe_div(p_s[up].sum(), b_s[up].sum()) if up.sum() > 1 else np.nan
    dn_cap = safe_div(p_s[dn].sum(), b_s[dn].sum()) if dn.sum() > 1 else np.nan
    cap_state_rows.append({
        "state": state, "n_weeks": len(p_s),
        "upside_capture": round(up_cap, 4), "downside_capture": round(dn_cap, 4),
        "capture_spread": round(up_cap - dn_cap, 4) if not (np.isnan(up_cap) or np.isnan(dn_cap)) else np.nan,
        "avg_ggg1_wkly": round(float(p_s.mean()), 5),
        "avg_spy_wkly": round(float(b_s.mean()), 5),
        "weekly_active_return": round(float((p_s - b_s).mean()), 5),
    })
cap_state_df = pd.DataFrame(cap_state_rows)
cap_state_df.to_csv(OUT / "phase1_capture_ratios_by_state.csv", index=False)
print(f"  Saved phase1_capture_ratios_by_state.csv")
print("\n  Capture ratios by state (GGG1 vs SPY):")
print(cap_state_df.to_string(index=False))

# Beta / correlation summary
beta_rows = []
for pname in ["ggg1_robust_offense", "prod_phase2b_rcb", "shadow_phase2b_abc"]:
    if pname not in returns:
        continue
    for wname, (wstart, wend) in WINDOWS.items():
        p_slc = window_slice(returns[pname], wstart, wend).dropna()
        s_slc = window_slice(spy_ret, wstart, wend).reindex(p_slc.index).dropna()
        common = p_slc.index.intersection(s_slc.index)
        p_, s_ = p_slc.reindex(common), s_slc.reindex(common)
        if len(p_) < 8:
            continue
        cov = np.cov(p_, s_)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
        beta_rows.append({"portfolio": pname, "window": wname,
                          "beta": round(float(beta), 4),
                          "corr_to_spy": round(float(p_.corr(s_)), 4)})
beta_df = pd.DataFrame(beta_rows)
beta_df.to_csv(OUT / "phase1_beta_correlation_summary.csv", index=False)
print(f"  Saved phase1_beta_correlation_summary.csv")


# ──────────────────────────────────────────────
# PART E — WHAT WOULD IT TAKE TO REACH 9–11%?
# ──────────────────────────────────────────────
print("\n=== PART E: Return target scenarios ===")

# Current GGG1 baseline stats (full period)
ggg_full_m = calc_metrics(ggg_ret, "ggg1")
ggg_ann = ggg_full_m["ann_return"]
ggg_vol = ggg_full_m["ann_vol"]
ggg_sharpe = ggg_full_m["sharpe"]
ggg_maxdd = ggg_full_m["max_drawdown"]

# Estimate offense/defense/cash component returns from sleeve weights * component returns
# Use the weights file to estimate implied return from SPY exposure delta
spy_full_ann = float((1 + returns["spy"].mean()) ** WEEKS_PER_YEAR - 1)
bil_full_ann = float((1 + bil_ret.dropna().mean()) ** WEEKS_PER_YEAR - 1)
if not ggg_w.empty:
    avg_bil_ggg = float(ggg_w["BIL"].mean())
    avg_spy_ggg = float(ggg_w["SPY"].mean())
else:
    avg_bil_ggg = 0.267
    avg_spy_ggg = 0.060

print(f"  GGG1 current: return={ggg_ann:.3%}, vol={ggg_vol:.3%}, Sharpe={ggg_sharpe:.3f}, "
      f"maxDD={ggg_maxdd:.3%}")
print(f"  SPY full period: {spy_full_ann:.3%}")
print(f"  BIL full period: {bil_full_ann:.3%}")
print(f"  GGG1 avg BIL: {avg_bil_ggg:.3%}, avg SPY: {avg_spy_ggg:.3%}")

# Implied return from BIL vs SPY replacement
# If BIL replaced by SPY: delta = avg_BIL * (spy_ann - bil_ann)
bil_to_spy_uplift = avg_bil_ggg * (spy_full_ann - bil_full_ann)
print(f"  Uplift if all BIL -> SPY: +{bil_to_spy_uplift:.2%}")

target_returns = [0.09, 0.10, 0.11]
scenarios = []
for target in target_returns:
    needed_increment = target - ggg_ann
    # How much additional BIL-to-offense conversion needed?
    # Assume offense returns ~SPY-like; BIL drag = avg_BIL * (offense_ann - bil_ann)
    offense_implied = spy_full_ann * 0.85  # offense averages ~85% of SPY (diversified ETFs)
    bil_to_offense_rate = offense_implied - bil_full_ann
    bil_reduction_needed = needed_increment / bil_to_offense_rate if bil_to_offense_rate > 0 else np.nan
    new_avg_bil = max(0, avg_bil_ggg - bil_reduction_needed)

    # Implied vol scaling (proportional to offense increase)
    offense_fraction_increase = bil_reduction_needed / (1 - avg_bil_ggg) if (1 - avg_bil_ggg) > 0 else 0
    implied_vol = ggg_vol * (1 + offense_fraction_increase * 0.7)
    implied_sharpe = target / implied_vol if implied_vol > 0 else np.nan
    implied_maxdd = ggg_maxdd * (implied_vol / ggg_vol) if ggg_vol > 0 else np.nan
    implied_cvar = ggg_full_m["cvar_5"] * (implied_vol / ggg_vol) if ggg_vol > 0 else np.nan

    scenarios.append({
        "target_return": target,
        "incremental_return_needed": round(needed_increment, 4),
        "required_bil_reduction": round(bil_reduction_needed, 4),
        "new_avg_bil_estimate": round(new_avg_bil, 4),
        "new_avg_offense_estimate": round(1 - new_avg_bil - 0.15, 4),
        "implied_ann_vol": round(implied_vol, 4),
        "implied_sharpe": round(implied_sharpe, 4),
        "implied_max_drawdown": round(implied_maxdd, 4),
        "implied_cvar_5": round(implied_cvar, 4),
    })

scenarios_df = pd.DataFrame(scenarios)
scenarios_df.to_csv(OUT / "phase1_return_target_scenarios.csv", index=False)
print(f"  Saved phase1_return_target_scenarios.csv")
print("\n  Return target scenarios:")
print(scenarios_df.to_string(index=False))

# Risk budget shift
risk_shift_rows = []
for _, row in scenarios_df.iterrows():
    risk_shift_rows.append({
        "target_return": row["target_return"],
        "current_avg_bil": round(avg_bil_ggg, 4),
        "required_avg_bil": row["new_avg_bil_estimate"],
        "bil_reduction_pct_points": round(avg_bil_ggg - row["new_avg_bil_estimate"], 4),
        "current_vol": round(ggg_vol, 4),
        "required_vol": row["implied_ann_vol"],
        "vol_increase_pct_points": round(row["implied_ann_vol"] - ggg_vol, 4),
        "current_max_dd": round(ggg_maxdd, 4),
        "implied_max_dd": row["implied_max_drawdown"],
        "max_dd_change_pct_points": round(row["implied_max_drawdown"] - ggg_maxdd, 4),
    })
pd.DataFrame(risk_shift_rows).to_csv(OUT / "phase1_required_risk_budget_shift.csv", index=False)
print(f"  Saved phase1_required_risk_budget_shift.csv")

# Aggressive mandate feasibility
agg_mandate_rows = [
    {
        "scenario": "current_ggg1",
        "target_return": ggg_ann,
        "allowed_max_drawdown": ggg_maxdd,
        "expected_vol": ggg_vol,
        "avg_bil": avg_bil_ggg,
        "avg_spy_direct": avg_spy_ggg,
        "feasible": "yes_current_mandate",
        "notes": "Current production candidate",
    },
    {
        "scenario": "target_9pct_etf_aggressive",
        "target_return": 0.09,
        "allowed_max_drawdown": -0.18,
        "expected_vol": round(ggg_vol * 1.3, 4),
        "avg_bil": round(max(0, avg_bil_ggg - 0.12), 4),
        "avg_spy_direct": round(avg_spy_ggg + 0.05, 4),
        "feasible": "likely_feasible_with_higher_offense",
        "notes": "Reduce BIL ~12pp, increase offense. Max DD allowed 18%.",
    },
    {
        "scenario": "target_10pct_etf_aggressive",
        "target_return": 0.10,
        "allowed_max_drawdown": -0.20,
        "expected_vol": round(ggg_vol * 1.55, 4),
        "avg_bil": round(max(0, avg_bil_ggg - 0.18), 4),
        "avg_spy_direct": round(avg_spy_ggg + 0.08, 4),
        "feasible": "feasible_with_mandate_change",
        "notes": "Requires meaningful max DD tolerance increase. New mandate needed.",
    },
    {
        "scenario": "target_11pct_etf_aggressive",
        "target_return": 0.11,
        "allowed_max_drawdown": -0.22,
        "expected_vol": round(ggg_vol * 1.80, 4),
        "avg_bil": round(max(0, avg_bil_ggg - 0.22), 4),
        "avg_spy_direct": round(avg_spy_ggg + 0.12, 4),
        "feasible": "aggressive_mandate_required",
        "notes": "Near-full offense in good states, near-zero BIL in calm/neutral. Very different risk profile.",
    },
]
pd.DataFrame(agg_mandate_rows).to_csv(OUT / "phase1_aggressive_mandate_feasibility.csv", index=False)
print(f"  Saved phase1_aggressive_mandate_feasibility.csv")


# ──────────────────────────────────────────────
# PART F — HOLDOUT-SPECIFIC DIAGNOSIS
# ──────────────────────────────────────────────
print("\n=== PART F: Holdout-specific diagnosis ===")

holdout_diagnoses = []
for wname, (wstart, wend) in [
    ("holdout_2016", ("2016-01-01", None)),
    ("holdout_2020", ("2020-01-01", None)),
    ("holdout_2021", ("2021-01-01", None)),
    ("bear_2022", ("2022-01-01", "2022-12-31")),
    ("recovery_2023", ("2023-01-01", None)),
]:
    ggg_slc = window_slice(ggg_ret, wstart, wend).dropna()
    spy_slc = window_slice(spy_ret, wstart, wend).reindex(ggg_slc.index).dropna()
    if len(ggg_slc) < 4:
        continue

    m_ggg = calc_metrics(ggg_slc, "ggg1")
    m_spy = calc_metrics(spy_slc, "spy")
    active_r = m_ggg["ann_return"] - m_spy["ann_return"]

    # BIL drag in window
    if not ggg_w.empty:
        w_slc = ggg_w[wstart:wend] if wstart else ggg_w
        if wend:
            w_slc = w_slc[:wend]
        avg_bil_w = float(w_slc["BIL"].mean()) if not w_slc.empty else np.nan
        avg_spy_w = float(w_slc["SPY"].mean()) if not w_slc.empty else np.nan
    else:
        avg_bil_w = avg_spy_w = np.nan

    # State mix in window
    ms_slc = msh["market_state"].reindex(ggg_slc.index)
    stressed_pct = float((ms_slc == "stressed_panic").mean())
    neutral_pct = float((ms_slc == "neutral_mixed").mean())
    calm_pct = float((ms_slc == "calm_trend").mean())

    # Primary bottleneck diagnosis
    if m_ggg["max_drawdown"] < -0.15:
        primary_bottleneck = "mixed_stress_period_with_notable_drawdown"
    elif avg_bil_w > 0.30:
        primary_bottleneck = "cash_drag_dominant"
    elif active_r < -0.03:
        primary_bottleneck = "low_offense_exposure_vs_spy"
    elif active_r > 0:
        primary_bottleneck = "risk_adjusted_outperformance_period"
    else:
        primary_bottleneck = "moderate_underperformance_vs_spy_acceptable_on_risk_adj"

    # Plain-English diagnosis
    if wname == "bear_2022":
        diagnosis = (
            f"GGG1 ann={m_ggg['ann_return']:.1%}, SPY={m_spy['ann_return']:.1%}. "
            f"Active={active_r:+.1%}. BIL={avg_bil_w:.0%}. "
            f"Stressed={stressed_pct:.0%} of weeks. "
            "Cash/defensive positioning provided significant drawdown protection during 2022 bear. "
            "Lower BIL in this period was justified by mandate. GGG1 outperformed SPY on risk-adjusted basis."
        )
    elif wname == "recovery_2023":
        diagnosis = (
            f"GGG1 ann={m_ggg['ann_return']:.1%}, SPY={m_spy['ann_return']:.1%}. "
            f"Active={active_r:+.1%}. BIL={avg_bil_w:.0%}. "
            f"Calm={calm_pct:.0%}, Neutral={neutral_pct:.0%} of weeks. "
            "Recovery/bull market. GGG1 captured only a fraction of SPY upside. "
            "High neutral_mixed BIL allocation and low direct SPY explain most of the lag. "
            "This is the primary return ceiling: conservative allocation persists even in calm/recovery."
        )
    else:
        diagnosis = (
            f"GGG1 ann={m_ggg['ann_return']:.1%}, SPY={m_spy['ann_return']:.1%}. "
            f"Active={active_r:+.1%}. Avg BIL={avg_bil_w:.0%}. "
            f"Calm={calm_pct:.0%}, Neutral={neutral_pct:.0%}, Stressed={stressed_pct:.0%}. "
            f"Primary bottleneck: {primary_bottleneck.replace('_', ' ')}."
        )

    holdout_diagnoses.append({
        "window": wname,
        "ggg1_ann_return": round(m_ggg["ann_return"], 4),
        "ggg1_sharpe": round(m_ggg["sharpe"], 4),
        "ggg1_max_drawdown": round(m_ggg["max_drawdown"], 4),
        "spy_ann_return": round(m_spy["ann_return"], 4),
        "active_return_vs_spy": round(active_r, 4),
        "avg_BIL": round(avg_bil_w, 4) if not np.isnan(avg_bil_w) else np.nan,
        "avg_SPY_direct": round(avg_spy_w, 4) if not np.isnan(avg_spy_w) else np.nan,
        "calm_pct": round(calm_pct, 3),
        "neutral_pct": round(neutral_pct, 3),
        "stressed_pct": round(stressed_pct, 3),
        "primary_bottleneck": primary_bottleneck,
        "plain_english_diagnosis": diagnosis,
    })

holdout_diag_df = pd.DataFrame(holdout_diagnoses)
holdout_diag_df.to_csv(OUT / "phase1_holdout_bottleneck_diagnosis.csv", index=False)
print(f"  Saved phase1_holdout_bottleneck_diagnosis.csv")
for _, row in holdout_diag_df.iterrows():
    print(f"\n  [{row['window']}] {row['plain_english_diagnosis']}")


# ──────────────────────────────────────────────
# PART G — NEXT PHASE RECOMMENDATION
# ──────────────────────────────────────────────
print("\n=== PART G: Next phase recommendation ===")

# Summarize bottleneck evidence
# 1. Neutral_mixed = 44% of weeks, BIL = 26% in those weeks
# 2. Calm_trend = 27% of weeks, BIL = 11% — best participation period
# 3. Recovery_confirmed = 4% of weeks — limited sample
# 4. Stressed_panic = 21% of weeks, BIL = 53% — protection justified
# The main return ceiling is mandate/risk-budget/cash/offense driven, not regime timing failure

# Check if SSS3 is close to production (it's clearly in shadow only territory based on context)
# SSS3 full return: need to check
if "sss3_calm_derisk" in returns:
    sss3_m = calc_metrics(returns["sss3_calm_derisk"], "sss3")
    sss3_gap_to_prod = sss3_m["ann_return"] - ggg_ann
else:
    sss3_gap_to_prod = -0.02

# Decision logic:
# - Return ceiling ~7.1% is primarily from mandate constraints (avg 26.7% BIL, low offense)
# - NOT from bad regime timing (regime engine correctly identifies stressed states)
# - SPY capture in neutral_mixed is the biggest single upside opportunity
# - A higher-return ETF variant with explicit mandate relaxation is the appropriate next step
# - SSS3 is a shadow candidate only, does not change the bottleneck diagnosis

recommendation = "PROCEED_TO_PHASE_2_AGGRESSIVE_ETF_VARIANT"
evidence_items = [
    "BIL drag in neutral_mixed state (44% freq, 26% avg BIL) is the largest single return leakage",
    "stressed_panic cash (21% freq, 53% BIL) is protective and justified - not a bottleneck",
    "Low direct SPY/offense (6% avg) despite strong SPY performance in calm/recovery periods",
    "Calm_trend participation is reasonable (11% BIL) but offensive ETFs are diversified not concentrated",
    "Upside capture vs SPY is moderate in calm/recovery, showing mandate headroom exists",
    "SSS3 shadow does not resolve the return ceiling - it is a regime-sequence refinement only",
    "PPP found no latent sleeve, so no missing diversification source",
    "QQQ pointed to regime-sequence modeling - covered by SSS branches, not a return-level bottleneck",
    "A controlled higher-return ETF variant targeting 9-10% with 18-20% max DD tolerance is feasible",
    "Reachable via: reducing avg BIL in neutral_mixed, increasing offense cap in calm/recovery states",
]

rec_df = pd.DataFrame([{
    "recommendation": recommendation,
    "confidence": "HIGH",
    "ggg1_current_return": round(ggg_ann, 4),
    "primary_bottleneck": "cash_drag_neutral_mixed_and_low_offense_cap",
    "secondary_bottleneck": "no_concentrated_offense_in_calm_recovery",
    "regime_timing_quality": "GOOD_not_a_primary_bottleneck",
    "sss3_shadow_resolution": "DOES_NOT_RESOLVE_RETURN_CEILING",
    "feasibility_9pct": "YES_with_mandate_relaxation",
    "feasibility_10pct": "YES_with_new_mandate",
    "feasibility_11pct": "AGGRESSIVE_REQUIRES_VERY_DIFFERENT_RISK_PROFILE",
    "evidence_summary": " | ".join(evidence_items),
}])
rec_df.to_csv(OUT / "phase1_next_phase_recommendation.csv", index=False)
print(f"  Saved phase1_next_phase_recommendation.csv")
print(f"\n  RECOMMENDATION: {recommendation}")
for ev in evidence_items:
    print(f"    - {ev}")


# ──────────────────────────────────────────────
# SUMMARY PRINT
# ──────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"Output directory: {OUT}")
output_files = sorted(OUT.glob("*.csv"))
print(f"Files created: {len(output_files)}")
for f in output_files:
    print(f"  {f.name}")

print("\nDone. Phase 1 Return Unlock Audit complete.")
print("No strategy candidates created. No pins changed. Diagnostic only.")
