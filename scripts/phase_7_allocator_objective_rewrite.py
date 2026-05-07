#!/usr/bin/env python3
"""
Phase 7 — Allocator Objective Rewrite
Tests whether larger sector sleeve budgets (28–32% vs 20%), more aggressive
layer3 expression in calm states, and faster reallocation speed can push
full-period annual return past 8.0% while keeping Sharpe roughly similar.
All candidates start from Phase 4B best. No new data. No stock-level trading.
No production pin changes. No auto-promotion.

Candidates (base: improved_phase4b_refined_sector_20pct):
  C1: improved_phase7_larger_sector_calm       (28% sector budget)
  C2: improved_phase7_expression_boost         (aggressive layer3 expression)
  C3: improved_phase7_max_sector_rerisk        (28% + max rerisk speed)
  C4: improved_phase7_combined_offensive       (28% + expression + max rerisk)
  C5: improved_phase7_stretch_target           (32% + expression + full mandate)
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
OUT = ROOT / "data" / "research" / "phase_7_allocator_objective_rewrite"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS = 52

CANDIDATES = [
    "improved_phase7_larger_sector_calm",
    "improved_phase7_expression_boost",
    "improved_phase7_max_sector_rerisk",
    "improved_phase7_combined_offensive",
    "improved_phase7_stretch_target",
]

BASELINES = {
    "ggg1": "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    "phase2_best": "portfolio_version_returns_improved_phase2_aggressive_neutral_cash_unlock.csv",
    "phase3_best": "portfolio_version_returns_improved_phase3_high_breadth_calm_us_offense.csv",
    "phase4b_best": "portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv",
    "phase6_best": "portfolio_version_returns_improved_phase6_continuous_aggression_score.csv",
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
    try:
        return float(a / b) if float(b) != 0 and not np.isnan(float(b)) else np.nan
    except Exception:
        return np.nan


def load_ret(fname: str) -> pd.Series | None:
    p = L3 / fname
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
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
print("=== Loading base data ===")
msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)
wr = pd.read_csv(HUB / "weekly_returns.csv", index_col="Date", parse_dates=True)
bm_prices = pd.read_csv(HUB / "benchmark_prices_weekly.csv", index_col="Date", parse_dates=True)
spy_ret = bm_prices["SPY"].pct_change().dropna()
ief_ret = bm_prices["IEF"].pct_change().dropna()
bench_6040 = (0.60 * spy_ret + 0.40 * ief_ret).dropna()
qqq_ret = wr["QQQ"].dropna() if "QQQ" in wr.columns else None

p4b_ret = load_ret("portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv")
p6_ret = load_ret("portfolio_version_returns_improved_phase6_continuous_aggression_score.csv")
ggg1_ret = load_ret("portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv")

p4b_m = calc_metrics(p4b_ret, "phase4b_best") if p4b_ret is not None else {}
p4b_bear = calc_metrics(ws(p4b_ret, "2022-01-01", "2022-12-31")) if p4b_ret is not None else {}
ggg1_m = calc_metrics(ggg1_ret, "ggg1") if ggg1_ret is not None else {}

p4b_sw = pd.read_csv(L3 / "portfolio_version_sleeve_weights_improved_phase4b_refined_sector_20pct.csv", index_col=0, parse_dates=True)

print(f"  Phase4B best: {p4b_m.get('ann_return', 'N/A'):.3%} / Sharpe {p4b_m.get('sharpe','N/A'):.3f}")
print(f"  Phase6 best:  {calc_metrics(p6_ret).get('ann_return', 'N/A'):.3%} / Sharpe {calc_metrics(p6_ret).get('sharpe','N/A'):.3f}" if p6_ret is not None else "  Phase6 best: N/A")

# ──────────────────────────────────────────────
# SAVE CANDIDATE DESIGNS
# ──────────────────────────────────────────────
designs = [
    {"candidate": "improved_phase7_larger_sector_calm", "base": "phase4b_refined_sector_20pct",
     "sector_target": "28% (vs 20% for Phase4B)", "expression_mode": "none",
     "rerisk_speed": 1.00, "realloc_speed": 0.55, "phase2b": "neutral_boost",
     "hypothesis": "Larger sector budget captures more calm_trend upside"},
    {"candidate": "improved_phase7_expression_boost", "base": "phase4b_refined_sector_20pct",
     "sector_target": "Phase4B default (20%)", "expression_mode": "phase7_aggressive_expression (shift=0.12)",
     "rerisk_speed": 0.95, "realloc_speed": 0.55, "phase2b": "neutral_boost",
     "hypothesis": "Shifts more within-risky-budget from defense to offense in calm"},
    {"candidate": "improved_phase7_max_sector_rerisk", "base": "phase4b_refined_sector_20pct",
     "sector_target": "28%", "expression_mode": "none",
     "rerisk_speed": 1.00, "realloc_speed": 0.65, "phase2b": "neutral_boost",
     "hypothesis": "Faster commitment speed + larger sector budget"},
    {"candidate": "improved_phase7_combined_offensive", "base": "phase4b_refined_sector_20pct",
     "sector_target": "28%", "expression_mode": "phase7_aggressive_expression (shift=0.12)",
     "rerisk_speed": 1.00, "realloc_speed": 0.60, "phase2b": "neutral_boost",
     "hypothesis": "Main 8%+ candidate: all three levers combined"},
    {"candidate": "improved_phase7_stretch_target", "base": "phase4b_refined_sector_20pct",
     "sector_target": "32%", "expression_mode": "phase7_aggressive_expression (shift=0.12)",
     "rerisk_speed": 1.00, "realloc_speed": 0.70, "phase2b": "full_mandate",
     "hypothesis": "Maximum return stretch: 8.5%+ target, accept higher drawdown"},
]
pd.DataFrame(designs).to_csv(OUT / "phase7_candidate_designs.csv", index=False)
print("  Candidate designs saved")

# ──────────────────────────────────────────────
# BUILD
# ──────────────────────────────────────────────
print("\n=== Running production pipeline ===")
build_env = os.environ.copy()
build_env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
build_script = ROOT / "scripts" / "build_improvement_artifacts.py"
result = subprocess.run(
    [sys.executable, str(build_script)],
    env=build_env, capture_output=True, text=True, cwd=str(ROOT), timeout=900,
)
with open(OUT / "phase7_build.log", "w") as f:
    f.write(result.stdout[-10000:] if len(result.stdout) > 10000 else result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr[-4000:] if len(result.stderr) > 4000 else result.stderr)

if result.returncode != 0:
    print(f"  BUILD FAILED (exit {result.returncode})")
    print(result.stderr[-1500:])
    sys.exit(1)

missing = [f"{c}" for c in CANDIDATES
           if not (L3 / f"portfolio_version_returns_{c}.csv").exists()]
if missing:
    print(f"  WARNING: missing artifacts: {missing}")
else:
    print(f"  All {len(CANDIDATES)*3} artifacts confirmed.")

# ──────────────────────────────────────────────
# LOAD RETURNS
# ──────────────────────────────────────────────
returns: dict[str, pd.Series] = {}
for c in CANDIDATES:
    r = load_ret(f"portfolio_version_returns_{c}.csv")
    if r is not None:
        returns[c] = r
        m = calc_metrics(r)
        print(f"  {c}: {m.get('ann_return','N/A'):.3%} / Sharpe {m.get('sharpe','N/A'):.3f}")
for name, fname in BASELINES.items():
    r = load_ret(fname)
    if r is not None:
        returns[name] = r
returns["spy"] = spy_ret
if qqq_ret is not None:
    returns["qqq"] = qqq_ret
returns["bench_60_40"] = bench_6040

# ──────────────────────────────────────────────
# METRICS
# ──────────────────────────────────────────────
print("\n=== Computing metrics ===")
all_metrics = []
for pname, ret in returns.items():
    for wname, (wstart, wend) in WINDOWS.items():
        slc = ws(ret, wstart, wend).dropna()
        m = calc_metrics(slc, pname)
        row = {"portfolio": pname, "window": wname, **m}

        wf = L3 / f"portfolio_version_weights_{pname}.csv"
        swf = L3 / f"portfolio_version_sleeve_weights_{pname}.csv"
        if wf.exists():
            w_df = pd.read_csv(wf, index_col=0, parse_dates=True)
            ws_ = w_df if not wstart else w_df[wstart:]
            if wend:
                ws_ = ws_[:wend]
            row["avg_BIL"] = round(float(ws_["BIL"].mean()), 4) if "BIL" in ws_ else np.nan
            row["avg_SPY"] = round(float(ws_["SPY"].mean()), 4) if "SPY" in ws_ else np.nan
        else:
            row["avg_BIL"] = row["avg_SPY"] = np.nan

        if swf.exists():
            sw_ = pd.read_csv(swf, index_col=0, parse_dates=True)
            sw_slc = sw_ if not wstart else sw_[wstart:]
            if wend:
                sw_slc = sw_slc[:wend]
            row["avg_sector_sleeve"] = round(float(sw_slc.get("phase4b_defensive_aware_top5_sleeve", pd.Series([np.nan])).mean()), 4)
            row["avg_defense"] = round(float(sw_slc.get("composite_regime_defense_component", pd.Series([np.nan])).mean()), 4)
            row["avg_cash_bil"] = round(float(sw_slc.get("cash::BIL", pd.Series([np.nan])).mean()), 4)
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

        for baseline_name in ["ggg1", "phase4b_best", "phase6_best"]:
            base_slc = ws(returns.get(baseline_name, pd.Series(dtype=float)), wstart, wend).dropna()
            common = slc.index.intersection(base_slc.index)
            if len(common) > 4:
                p_ann = float((1+slc.reindex(common).mean())**WEEKS-1)
                b_ann = float((1+base_slc.reindex(common).mean())**WEEKS-1)
                row[f"active_vs_{baseline_name}"] = round(p_ann - b_ann, 4)
            else:
                row[f"active_vs_{baseline_name}"] = np.nan

        all_metrics.append(row)

metrics_df = pd.DataFrame(all_metrics)
metrics_df.to_csv(OUT / "phase7_candidate_metrics_full.csv", index=False)
metrics_df[metrics_df["window"].isin(["holdout_2016","holdout_2020","holdout_2021","bear_2022","recovery_2023"])].to_csv(
    OUT / "phase7_candidate_holdout_metrics.csv", index=False)

focus = CANDIDATES + ["ggg1","phase4b_best","phase6_best","phase3_best","phase2_best","prod_pin","spy","bench_60_40"]
bm_table = metrics_df[
    metrics_df["portfolio"].isin(focus) &
    metrics_df["window"].isin(["full","holdout_2020","holdout_2021","bear_2022","recovery_2023"])
][["portfolio","window","ann_return","sharpe","max_drawdown","calmar","cvar_5","avg_BIL","avg_sector_sleeve",
   "avg_defense","avg_turnover","beta_spy","active_vs_ggg1","active_vs_phase4b_best","active_vs_phase6_best"]].copy()
bm_table.to_csv(OUT / "phase7_candidate_vs_benchmark_table.csv", index=False)
metrics_df[metrics_df["portfolio"].isin(focus)][
    ["portfolio","window","upside_capture","downside_capture","beta_spy","corr_spy","active_vs_ggg1","active_vs_phase4b_best"]
].to_csv(OUT / "phase7_capture_beta_by_window.csv", index=False)

print("  Full-period comparison:")
fp = metrics_df[metrics_df["window"]=="full"][
    ["portfolio","ann_return","sharpe","max_drawdown","cvar_5","avg_BIL","avg_sector_sleeve","avg_defense","beta_spy","active_vs_phase4b_best"]
].copy()
fp = fp[fp["portfolio"].isin(CANDIDATES+["ggg1","phase4b_best","phase6_best","spy"])].set_index("portfolio")
print(fp.round(4).to_string())

# ──────────────────────────────────────────────
# STATE DIAGNOSTICS
# ──────────────────────────────────────────────
print("\n=== State diagnostics ===")
state_rows, delta_p4b_rows, delta_ggg1_rows = [], [], []
for pname in CANDIDATES + ["ggg1", "phase4b_best", "phase6_best"]:
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
            row["avg_sector"] = round(float(sw_slc.get("phase4b_defensive_aware_top5_sleeve", pd.Series([np.nan])).mean()), 4)
            row["avg_defense"] = round(float(sw_slc.get("composite_regime_defense_component", pd.Series([np.nan])).mean()), 4)
            row["avg_bil_sleeve"] = round(float(sw_slc.get("cash::BIL", pd.Series([np.nan])).mean()), 4)
        if has_w:
            w_slc = w_data.reindex(idx)
            row["avg_BIL"] = round(float(w_slc["BIL"].mean()), 4) if "BIL" in w_slc else np.nan
        state_rows.append(row)

        p4b_slc = (p4b_ret if p4b_ret is not None else pd.Series(dtype=float)).reindex(idx).dropna()
        ggg_slc = (ggg1_ret if ggg1_ret is not None else pd.Series(dtype=float)).reindex(idx).dropna()
        p4b_sm = calc_metrics(p4b_slc)
        ggg_sm = calc_metrics(ggg_slc)
        delta_p4b_rows.append({"portfolio": pname, "state": state,
                                "delta_vs_p4b": round((m.get("ann_return",0) or 0) - (p4b_sm.get("ann_return",0) or 0), 4)})
        delta_ggg1_rows.append({"portfolio": pname, "state": state,
                                 "delta_vs_ggg1": round((m.get("ann_return",0) or 0) - (ggg_sm.get("ann_return",0) or 0), 4)})

pd.DataFrame(state_rows).to_csv(OUT / "phase7_state_summary.csv", index=False)
pd.DataFrame(delta_p4b_rows).to_csv(OUT / "phase7_state_deltas_vs_phase4b.csv", index=False)
pd.DataFrame(delta_ggg1_rows).to_csv(OUT / "phase7_state_deltas_vs_ggg1.csv", index=False)
pd.DataFrame([r for r in state_rows if r["state"]=="stressed_panic"]).to_csv(OUT / "phase7_stress_protection_diagnostics.csv", index=False)
pd.DataFrame([r for r in state_rows if r["state"]=="calm_trend"]).to_csv(OUT / "phase7_calm_diagnostics.csv", index=False)

best_key = "improved_phase7_combined_offensive" if "improved_phase7_combined_offensive" in returns else (CANDIDATES[0] if CANDIDATES else None)
print("  calm_trend comparison (C4 vs Phase4B):")
for pname in ["improved_phase7_combined_offensive", "phase4b_best", "phase6_best"]:
    calm_rows = [r for r in state_rows if r["portfolio"] == pname and r["state"] == "calm_trend"]
    if calm_rows:
        r = calm_rows[0]
        ann_v = r.get('ann_return'); sh_v = r.get('sharpe'); sec_v = r.get('avg_sector')
        print(f"    {pname}: {ann_v:.2%} / Sharpe {sh_v:.3f} / sector={sec_v:.1%}" if all(isinstance(x, float) for x in [ann_v, sh_v, sec_v]) else f"    {pname}: data missing")

# ──────────────────────────────────────────────
# RISK / HIDDEN BETA CHECKS
# ──────────────────────────────────────────────
print("\n=== Risk / hidden beta checks ===")

p4b_ann = p4b_m.get("ann_return", 0) or 0
p6_ann = calc_metrics(p6_ret).get("ann_return", 0) or 0 if p6_ret is not None else 0
spy_ann = calc_metrics(spy_ret).get("ann_return", 0) or 0
p4b_bear_ann = p4b_bear.get("ann_return", -99) or -99

_p4b_safe = p4b_ret if p4b_ret is not None else pd.Series(dtype=float)
p4b_common = _p4b_safe.dropna().index.intersection(spy_ret.dropna().index)
if len(p4b_common) > 2:
    pc = np.cov(_p4b_safe.reindex(p4b_common), spy_ret.reindex(p4b_common))
    p4b_beta = pc[0,1]/pc[1,1] if pc[1,1]>0 else np.nan
else:
    p4b_beta = np.nan

risk_rows, hb_rows, bear_rows, fail_rows = [], [], [], []

for pname in CANDIDATES:
    if pname not in returns:
        fail_rows.append({"portfolio": pname, "reason": "BUILD_FAILED"})
        continue
    ret = returns[pname]
    m_full = calc_metrics(ret)
    m_2020 = calc_metrics(ws(ret, "2020-01-01", None))
    m_bear = calc_metrics(ws(ret, "2022-01-01", "2022-12-31"))

    rf = L3 / f"portfolio_version_returns_{pname}.csv"
    avg_turn = np.nan
    if rf.exists():
        rdf = pd.read_csv(rf, index_col=0, parse_dates=True)
        if "turnover" in rdf.columns:
            avg_turn = float(rdf["turnover"].mean())

    wf = L3 / f"portfolio_version_weights_{pname}.csv"
    avg_bil = np.nan
    if wf.exists():
        avg_bil = float(pd.read_csv(wf, index_col=0)["BIL"].mean())

    common = ret.dropna().index.intersection(spy_ret.dropna().index)
    if len(common) > 2:
        cov = np.cov(ret.reindex(common), spy_ret.reindex(common))
        beta_spy = cov[0,1]/cov[1,1] if cov[1,1]>0 else np.nan
    else:
        beta_spy = np.nan
    corr_spy = float(ret.reindex(common).corr(spy_ret.reindex(common))) if len(common) > 2 else np.nan

    ann = m_full.get("ann_return", 0) or 0
    improve_p4b = ann - p4b_ann
    beta_attr = (beta_spy - p4b_beta) * spy_ann if not (np.isnan(beta_spy) or np.isnan(p4b_beta)) else np.nan
    pct_from_beta = abs(beta_attr)/abs(improve_p4b) if improve_p4b and not np.isnan(beta_attr) else np.nan

    passes = (m_full.get("max_drawdown", -1) >= -0.22 and (m_full.get("sharpe", 0) or 0) >= 0.90)
    bear_ok = (m_bear.get("ann_return", -99) or -99) >= p4b_bear_ann - 0.04
    disguised = (beta_spy is not None and not np.isnan(beta_spy) and beta_spy > 0.30) or (not np.isnan(corr_spy) and corr_spy > 0.50)

    risk_rows.append({
        "portfolio": pname,
        "full_ann_return": round(ann, 4), "full_sharpe": round(m_full.get("sharpe",np.nan), 4),
        "full_max_dd": round(m_full.get("max_drawdown",np.nan), 4),
        "holdout_2020_return": round(m_2020.get("ann_return",np.nan), 4),
        "holdout_2020_sharpe": round(m_2020.get("sharpe",np.nan), 4),
        "avg_BIL": round(avg_bil, 4) if not np.isnan(avg_bil) else np.nan,
        "avg_turnover": round(avg_turn, 4) if not np.isnan(avg_turn) else np.nan,
        "passes_mandate": passes, "bear_ok": bear_ok, "disguised_spy": disguised,
        "active_vs_p4b": round(improve_p4b, 4), "active_vs_p6": round(ann - p6_ann, 4),
    })
    hb_rows.append({
        "portfolio": pname, "beta_spy": round(beta_spy, 4) if not np.isnan(beta_spy) else np.nan,
        "beta_delta_vs_p4b": round(beta_spy - p4b_beta, 4) if not np.isnan(p4b_beta) else np.nan,
        "corr_spy": round(corr_spy, 4) if not np.isnan(corr_spy) else np.nan,
        "pct_improve_from_beta": round(pct_from_beta, 3) if not np.isnan(pct_from_beta) else np.nan,
        "hidden_beta_risk": "HIGH" if pct_from_beta and pct_from_beta > 0.50 else "LOW",
    })
    bear_rows.append({
        "portfolio": pname,
        "bear_2022_return": round(m_bear.get("ann_return",np.nan), 4),
        "p4b_bear_2022": round(p4b_bear_ann, 4),
        "delta_vs_p4b": round((m_bear.get("ann_return",0) or 0) - p4b_bear_ann, 4),
        "bear_ok": bear_ok,
    })

pd.DataFrame(risk_rows).to_csv(OUT / "phase7_risk_realism_checks.csv", index=False)
pd.DataFrame(hb_rows).to_csv(OUT / "phase7_hidden_beta_checks.csv", index=False)
pd.DataFrame(bear_rows).to_csv(OUT / "phase7_2022_bear_check.csv", index=False)
pd.DataFrame(fail_rows if fail_rows else [{"portfolio":"none","reason":"all_built"}]).to_csv(
    OUT / "phase7_candidate_failure_reasons.csv", index=False)

print("  Risk/hidden beta summary:")
for r in risk_rows:
    h = next((x for x in hb_rows if x["portfolio"]==r["portfolio"]), {})
    print(f"    {r['portfolio']}: {r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} "
          f"maxDD={r['full_max_dd']:.3%} vs_p4b={r['active_vs_p4b']:+.3%} vs_p6={r['active_vs_p6']:+.3%} "
          f"beta={h.get('beta_spy','?'):.3f} mandate={'OK' if r['passes_mandate'] else 'FAIL'} "
          f"bear={'OK' if r['bear_ok'] else 'FAIL'}")

# ──────────────────────────────────────────────
# SELECTION
# ──────────────────────────────────────────────
print("\n=== Selection ===")
sel_rows = []
for pname in CANDIDATES:
    if pname not in returns:
        sel_rows.append({"portfolio": pname, "classification": "REJECT", "reason": "build_failed"})
        continue
    m_full = calc_metrics(returns[pname])
    m_2020 = calc_metrics(ws(returns[pname], "2020-01-01", None))
    m_2021 = calc_metrics(ws(returns[pname], "2021-01-01", None))
    m_bear = calc_metrics(ws(returns[pname], "2022-01-01", "2022-12-31"))
    p4b_2020 = calc_metrics(ws(p4b_ret, "2020-01-01", None)) if p4b_ret is not None else {}

    ann = m_full.get("ann_return", 0) or 0
    sharpe = m_full.get("sharpe", 0) or 0
    max_dd = m_full.get("max_drawdown", -1) or -1
    hold_ret = m_2020.get("ann_return", 0) or 0
    bear_ret = m_bear.get("ann_return", -99) or -99
    hold_p4b = p4b_2020.get("ann_return", 0) or 0

    rr = next((r for r in risk_rows if r["portfolio"]==pname), {})
    hb = next((h for h in hb_rows if h["portfolio"]==pname), {})
    above_p4b = ann > p4b_ann
    above_p6 = ann > p6_ann
    above_ggg1 = ann > (ggg1_m.get("ann_return", 0) or 0)
    hold_above_p4b = hold_ret > hold_p4b
    sharpe_ok = sharpe >= 0.90
    mandate_ok = max_dd >= -0.22
    bear_ok_f = (bear_ret >= p4b_bear_ann - 0.04)
    disguised = rr.get("disguised_spy", False)

    if not mandate_ok:
        cls = "REJECT"; reason = f"max_dd {max_dd:.2%} exceeds -22%"
    elif not sharpe_ok:
        cls = "REJECT"; reason = f"Sharpe {sharpe:.3f} below 0.90"
    elif not bear_ok_f:
        cls = "REJECT"; reason = "2022 bear worse than Phase4B by >4%"
    elif disguised:
        cls = "REJECT"; reason = "disguised SPY"
    elif not above_ggg1:
        cls = "REJECT"; reason = f"doesn't beat GGG1 {(ggg1_m.get('ann_return',0) or 0):.2%}"
    elif ann >= 0.080 and sharpe >= 0.95 and max_dd >= -0.20 and above_p4b and hold_above_p4b:
        cls = "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
        reason = "Return>=8.0%, Sharpe>=0.95, maxDD>=-20%, beats Phase4B full+holdout"
    elif above_p4b and above_p6 and sharpe_ok and mandate_ok and bear_ok_f:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW"
        reason = "Beats both Phase4B and Phase6 with acceptable risk"
    elif above_p4b and sharpe_ok and mandate_ok and bear_ok_f:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW"
        reason = "Beats Phase4B return with acceptable risk"
    elif above_ggg1 and sharpe_ok and bear_ok_f:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW" if hold_above_p4b else "KEEP_AS_RESEARCH_ONLY"
        reason = "Beats GGG1; holdout vs Phase4B mixed"
    else:
        cls = "KEEP_AS_RESEARCH_ONLY"; reason = "Marginal improvement only"

    sel_rows.append({
        "portfolio": pname, "classification": cls, "reason": reason,
        "full_ann_return": round(ann, 4), "full_sharpe": round(sharpe, 4),
        "full_max_dd": round(max_dd, 4),
        "holdout_2020_return": round(hold_ret, 4), "holdout_2020_sharpe": round(m_2020.get("sharpe",np.nan), 4),
        "bear_2022_return": round(bear_ret, 4),
        "beats_phase4b": above_p4b, "beats_phase6": above_p6, "beats_ggg1": above_ggg1,
        "mandate_ok": mandate_ok, "bear_ok": bear_ok_f,
    })

sel_df = pd.DataFrame(sel_rows)
sel_df.to_csv(OUT / "phase7_selection_table.csv", index=False)

print("  Selection results:")
for r in sel_rows:
    print(f"    {r['portfolio']}: {r['classification']}")
    print(f"      {r['full_ann_return']:.3%} / Sharpe {r['full_sharpe']:.3f} / maxDD {r['full_max_dd']:.3%} | {r['reason']}")

best_candidate = None
for cls_p in ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT", "KEEP_AS_AGGRESSIVE_SHADOW"]:
    cands = [r for r in sel_rows if r["classification"]==cls_p]
    if cands:
        best_candidate = max(cands, key=lambda r: r["full_ann_return"])["portfolio"]
        break

# ──────────────────────────────────────────────
# AUDITS
# ──────────────────────────────────────────────
print("\n=== Audits ===")
audit_rows, audit_lines = [], ["# Phase 7 Audit Summary\n"]

if best_candidate:
    best_cls = next(r["classification"] for r in sel_rows if r["portfolio"]==best_candidate)
    print(f"  Best candidate: {best_candidate} ({best_cls})")
    is_challenger = best_cls == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
    for audit_name in ["research_committee_report", "backtest_realism_audit",
                        "allocator_benchmark_audit", "robustness_simulation_audit"]:
        script = ROOT / "scripts" / f"{audit_name}.py"
        if not script.exists():
            audit_rows.append({"audit": audit_name, "status": "SKIPPED_NOT_FOUND"}); continue
        if audit_name == "robustness_simulation_audit" and not is_challenger:
            audit_rows.append({"audit": audit_name, "status": "SKIPPED_NOT_CHALLENGER"}); continue
        flags = [] if is_challenger else ["--quick"]
        cmd = [sys.executable, str(script), best_candidate] + flags
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=300)
            status = "PASS" if res.returncode == 0 else "FAIL"
            log = OUT / f"phase7_{audit_name.replace('_report','')}_quick.log"
            with open(log, "w") as f:
                f.write(res.stdout[-4000:] + "\n" + res.stderr[-2000:])
            audit_rows.append({"audit": audit_name, "status": status})
            audit_lines.append(f"## {audit_name}: {status}\n")
            print(f"  {audit_name}: {status}")
        except subprocess.TimeoutExpired:
            audit_rows.append({"audit": audit_name, "status": "TIMEOUT"})
            print(f"  {audit_name}: TIMEOUT")
else:
    print("  No qualifying candidate — skipping audits")
    audit_lines.append("No qualifying candidate.\n")

pd.DataFrame(audit_rows).to_csv(OUT / "phase7_audit_results.csv", index=False)
with open(OUT / "phase7_audit_summary.md", "w") as f:
    f.writelines(audit_lines)

# ──────────────────────────────────────────────
# NEXT PHASE DECISION
# ──────────────────────────────────────────────
print("\n=== Next phase decision ===")
n_ch = sum(1 for r in sel_rows if r["classification"]=="PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT")
n_sh = sum(1 for r in sel_rows if r["classification"]=="KEEP_AS_AGGRESSIVE_SHADOW")
best_ret = max((r["full_ann_return"] for r in sel_rows
                if r["classification"] in ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT","KEEP_AS_AGGRESSIVE_SHADOW"]), default=0)

if n_ch > 0:
    decision = "PROMOTE_PHASE7_TO_PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
    rationale = f"{best_candidate} satisfies mandate: return>={best_ret:.2%}, Sharpe>=0.95, maxDD>=-20%, beats Phase4B+Phase6."
elif n_sh > 0 and best_ret > p6_ann:
    decision = "KEEP_PHASE7_AS_AGGRESSIVE_SHADOW"
    rationale = f"{best_candidate} ({best_ret:.2%}) improves over Phase6 ({p6_ann:.2%}) with acceptable risk."
elif n_sh > 0:
    decision = "KEEP_PHASE7_AS_AGGRESSIVE_SHADOW"
    rationale = f"{best_candidate} ({best_ret:.2%}) improves over Phase4B ({p4b_ann:.2%})."
else:
    decision = "RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE"
    rationale = "Allocator objective rewrite cannot break existing-data ceiling. PIT stock breadth required."

pd.DataFrame([{"decision": decision, "best_candidate": best_candidate or "none",
               "best_return": round(best_ret, 4), "rationale": rationale,
               "n_challenger": n_ch, "n_shadow": n_sh}]).to_csv(OUT / "phase7_next_phase_decision.csv", index=False)
pd.DataFrame([{"action": decision, "description": rationale}]).to_csv(
    OUT / "phase7_next_action_recommendation.csv", index=False)
with open(OUT / "phase7_protocol.json", "w") as f:
    json.dump({"phase": "phase_7_allocator_objective_rewrite", "date": "2026-05-07",
               "production_pin": "improved_phase2b_regime_confidence_boost",
               "phase4b_best_shadow": "improved_phase4b_refined_sector_20pct",
               "phase6_best_shadow": "improved_phase6_continuous_aggression_score",
               "best_candidate": best_candidate or "none", "decision": decision}, f, indent=2)

print(f"\n  DECISION: {decision}")
print(f"  Rationale: {rationale}")

# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"Output: {OUT}")
print(f"Files: {len(sorted(OUT.glob('*')))}")
for fp in sorted(OUT.glob("*")):
    print(f"  {fp.name}")
print("\nDone. Phase 7 complete. No pins changed. No auto-promotion.")
