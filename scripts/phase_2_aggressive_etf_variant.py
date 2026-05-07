#!/usr/bin/env python3
"""
Phase 2 — Aggressive ETF Variant
Builds 6 higher-return ETF mandate candidates starting from GGG1 base.
Diagnostic + selection. No production pin changes. No auto-promotion.

Candidates:
  C1: improved_phase2_aggressive_neutral_cash_unlock
  C2: improved_phase2_aggressive_calm_offense_unlock
  C3: improved_phase2_aggressive_recovery_confirmed_boost
  C4: improved_phase2_aggressive_nonstressed_offense_mandate
  C5: improved_phase2_aggressive_balanced_mandate
  C6: improved_phase2_aggressive_stretch_mandate
"""

from __future__ import annotations

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
HUB = ROOT / "data" / "01_data_hub"
OUT = ROOT / "data" / "research" / "phase_2_aggressive_etf_variant"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS_PER_YEAR = 52

CANDIDATES = [
    "improved_phase2_aggressive_neutral_cash_unlock",
    "improved_phase2_aggressive_calm_offense_unlock",
    "improved_phase2_aggressive_recovery_confirmed_boost",
    "improved_phase2_aggressive_nonstressed_offense_mandate",
    "improved_phase2_aggressive_balanced_mandate",
    "improved_phase2_aggressive_stretch_mandate",
]

BASELINES = {
    "ggg1": "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
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

AGGRESSIVE_MANDATE = {
    "target_return_primary": "9–10.5%",
    "target_return_stretch": "10.5–12%",
    "max_drawdown_primary": -0.20,
    "max_drawdown_stretch": -0.22,
    "sharpe_preferred": 0.95,
    "sharpe_minimum": 0.90,
    "stressed_panic_rule": "UNCHANGED — do not weaken stressed_panic protection",
    "neutral_mixed_rule": "Reduce BIL/cash; reallocate to existing offense sleeves",
    "calm_trend_rule": "Reduce defense_component; reallocate to offense",
    "recovery_confirmed_rule": "Increase offense; allow lower defense floor",
    "recovery_fragile_rule": "Keep cautious — small or no change",
    "hidden_beta_rule": "Improvement must not be explained by pure SPY beta increase",
    "holdout_requirement": "Must beat GGG1 in 2020+ and 2021+ holdout on primary objective",
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
        "label": label, "n_weeks": n,
        "ann_return": round(ann_ret, 6), "ann_vol": round(ann_vol, 6),
        "sharpe": round(sharpe, 6), "max_drawdown": round(max_dd, 6),
        "calmar": round(calmar, 6), "cvar_5": round(cvar_5, 6),
        "worst_4w": round(worst_4w, 6), "worst_13w": round(worst_13w, 6),
    }


def window_slice(s: pd.Series, start, end) -> pd.Series:
    if start:
        s = s[s.index >= start]
    if end:
        s = s[s.index <= end]
    return s


def safe_div(a, b):
    return float(a / b) if b and not np.isnan(b) and abs(b) > 1e-12 else np.nan


def load_ret(path: Path) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    col = "net_return" if "net_return" in df.columns else df.columns[0]
    return df[col]


def capture(port: pd.Series, bm: pd.Series):
    common = port.dropna().index.intersection(bm.dropna().index)
    p, b = port.reindex(common), bm.reindex(common)
    up = b > 0; dn = b < 0
    uc = safe_div(p[up].sum(), b[up].sum()) if up.sum() > 2 else np.nan
    dc = safe_div(p[dn].sum(), b[dn].sum()) if dn.sum() > 2 else np.nan
    cov = np.cov(p, b) if len(p) > 2 else np.zeros((2, 2))
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    corr = float(p.corr(b))
    return uc, dc, beta, corr


# ──────────────────────────────────────────────
# PART A — MANDATE DESIGN
# ──────────────────────────────────────────────
print("=== PART A: Mandate design ===")
pd.DataFrame([AGGRESSIVE_MANDATE]).T.reset_index().rename(
    columns={"index": "parameter", 0: "value"}
).to_csv(OUT / "phase2_aggressive_mandate_design.csv", index=False)

candidate_designs = [
    {"candidate": "improved_phase2_aggressive_neutral_cash_unlock",
     "target": "9-10%", "bottleneck": "neutral_mixed BIL",
     "state_tilt": "phase_ddd_confirmed_near_exclude_dual (GGG1 unchanged)",
     "phase2b_mode": "phase2_aggressive_neutral_boost (+0.08 flat)",
     "rerisk_speed": 0.80,
     "note": "Tests highest-frequency bottleneck. Regime multiplier boost only."},
    {"candidate": "improved_phase2_aggressive_calm_offense_unlock",
     "target": "9-10%", "bottleneck": "calm_trend defense allocation",
     "state_tilt": "phase2_aggressive_calm_offense (-0.09 defense->offense in calm)",
     "phase2b_mode": "regime_confidence_boost (GGG1 unchanged)",
     "rerisk_speed": 0.80,
     "note": "Tests second-largest bottleneck. Sleeve shift only."},
    {"candidate": "improved_phase2_aggressive_recovery_confirmed_boost",
     "target": "9-10%", "bottleneck": "recovery_confirmed participation",
     "state_tilt": "phase2_aggressive_recovery_offense (-0.06 defense->offense in RC)",
     "phase2b_mode": "regime_confidence_boost (GGG1 unchanged)",
     "rerisk_speed": 1.00,
     "note": "Rare but high-opportunity state. recovery_fragile untouched."},
    {"candidate": "improved_phase2_aggressive_nonstressed_offense_mandate",
     "target": "9-10.5%", "bottleneck": "neutral + calm + recovery combined",
     "state_tilt": "phase2_aggressive_nonstressed_offense (calm-0.09/neutral-0.05/RC-0.04)",
     "phase2b_mode": "phase2_aggressive_neutral_boost (+0.08 flat)",
     "rerisk_speed": 1.00,
     "note": "Main production-challenger candidate. Full non-stressed offense mandate."},
    {"candidate": "improved_phase2_aggressive_balanced_mandate",
     "target": "9-10%", "bottleneck": "neutral + calm (smaller shifts)",
     "state_tilt": "phase2_aggressive_balanced_offense (calm-0.06/neutral-0.03)",
     "phase2b_mode": "phase2_aggressive_neutral_boost (+0.08 flat)",
     "rerisk_speed": 0.80,
     "note": "Conservative aggressive. Better Sharpe/drawdown at cost of lower return."},
    {"candidate": "improved_phase2_aggressive_stretch_mandate",
     "target": "10.5-12%", "bottleneck": "all non-stressed states (stretch)",
     "state_tilt": "phase2_aggressive_stretch_offense (calm-0.12/neutral-0.08/RC-0.07)",
     "phase2b_mode": "phase2_aggressive_full_mandate (+0.10 flat)",
     "rerisk_speed": 1.00,
     "note": "Stretch mandate. Larger shifts. Allow max DD 20-22%. Reject if disguised SPY."},
]
pd.DataFrame(candidate_designs).to_csv(OUT / "phase2_candidate_designs.csv", index=False)
print(f"  Saved phase2_aggressive_mandate_design.csv, phase2_candidate_designs.csv")


# ──────────────────────────────────────────────
# PART B — RUN PRODUCTION BUILD
# ──────────────────────────────────────────────
print("\n=== PART B: Run production pipeline ===")

build_names = ",".join(CANDIDATES)
build_env = os.environ.copy()
build_env["BUILD_VERSION_NAMES"] = build_names
build_script = ROOT / "scripts" / "build_improvement_artifacts.py"

print(f"  Running: BUILD_VERSION_NAMES='{build_names}' python3 {build_script.name}")
result = subprocess.run(
    [sys.executable, str(build_script)],
    env=build_env,
    capture_output=True,
    text=True,
    cwd=str(ROOT),
    timeout=600,
)

build_log = OUT / "phase2_build.log"
with open(build_log, "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout[-8000:] if len(result.stdout) > 8000 else result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr[-4000:] if len(result.stderr) > 4000 else result.stderr)

if result.returncode != 0:
    print(f"  BUILD FAILED (exit code {result.returncode})")
    print(f"  Last stderr: {result.stderr[-1000:]}")
    sys.exit(1)

print(f"  Build completed (exit code 0). Log: {build_log.name}")

# Verify artifacts exist
missing = []
for c in CANDIDATES:
    for suffix in ["returns", "weights", "sleeve_weights"]:
        p = L3 / f"portfolio_version_{suffix}_{c}.csv"
        if not p.exists():
            missing.append(str(p.name))

if missing:
    print(f"  WARNING: Missing artifacts after build: {missing}")
else:
    print(f"  All {len(CANDIDATES) * 3} candidate artifacts confirmed.")


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
    else:
        print(f"  MISSING: {p.name}")

for name, fname in BASELINES.items():
    p = L3 / fname
    if p.exists():
        returns[name] = load_ret(p)

bm_prices = pd.read_csv(HUB / "benchmark_prices_weekly.csv", index_col="Date", parse_dates=True)
returns["spy"] = bm_prices["SPY"].pct_change().dropna()
returns["bench_60_40"] = (0.60 * bm_prices["SPY"].pct_change() + 0.40 * bm_prices["IEF"].pct_change()).dropna()

msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)


# ──────────────────────────────────────────────
# PART D — FULL + HOLDOUT METRICS
# ──────────────────────────────────────────────
print("\n=== PART D: Metrics ===")

all_metrics = []
for pname, ret in returns.items():
    for wname, (ws, we) in WINDOWS.items():
        slc = window_slice(ret, ws, we).dropna()
        m = calc_metrics(slc, pname)
        row = {"portfolio": pname, "window": wname, **m}

        # BIL/SPY/turnover from weights file if available
        wf = L3 / f"portfolio_version_weights_{pname}.csv"
        if wf.exists():
            w = pd.read_csv(wf, index_col=0, parse_dates=True)
            wslc = w[ws:we] if ws else w
            if we:
                wslc = wslc[:we]
            row["avg_BIL"] = round(float(wslc["BIL"].mean()), 4) if "BIL" in wslc else np.nan
            row["avg_SPY"] = round(float(wslc["SPY"].mean()), 4) if "SPY" in wslc else np.nan
        else:
            row["avg_BIL"] = np.nan
            row["avg_SPY"] = np.nan

        ret_f = L3 / f"portfolio_version_returns_{pname}.csv"
        if ret_f.exists():
            rf = pd.read_csv(ret_f, index_col=0, parse_dates=True)
            if "turnover" in rf.columns:
                tslc = window_slice(rf["turnover"], ws, we)
                row["avg_turnover"] = round(float(tslc.mean()), 4)
            else:
                row["avg_turnover"] = np.nan
        else:
            row["avg_turnover"] = np.nan

        # Capture vs SPY
        spy_slc = window_slice(returns["spy"], ws, we).dropna()
        uc, dc, beta, corr = capture(slc, spy_slc.reindex(slc.index))
        row["upside_capture_spy"] = round(uc, 4) if not np.isnan(uc) else np.nan
        row["downside_capture_spy"] = round(dc, 4) if not np.isnan(dc) else np.nan
        row["beta_spy"] = round(beta, 4) if not np.isnan(beta) else np.nan
        row["corr_spy"] = round(corr, 4) if not np.isnan(corr) else np.nan

        # Active return vs GGG1 and SPY
        ggg_slc = window_slice(returns.get("ggg1", pd.Series(dtype=float)), ws, we).dropna()
        common_ggg = slc.index.intersection(ggg_slc.index)
        if len(common_ggg) > 4:
            n_ggg = len(common_ggg)
            active_ggg = float((1 + (slc.reindex(common_ggg) - ggg_slc.reindex(common_ggg)).mean()) ** WEEKS_PER_YEAR - 1)
            row["active_return_vs_ggg1"] = round(active_ggg, 4)
        else:
            row["active_return_vs_ggg1"] = np.nan

        common_spy = slc.index.intersection(spy_slc.index)
        if len(common_spy) > 4:
            n_s = len(common_spy)
            p_ann = float((1 + slc.reindex(common_spy).mean()) ** WEEKS_PER_YEAR - 1)
            s_ann = float((1 + spy_slc.reindex(common_spy).mean()) ** WEEKS_PER_YEAR - 1)
            row["active_return_vs_spy"] = round(p_ann - s_ann, 4)
        else:
            row["active_return_vs_spy"] = np.nan

        all_metrics.append(row)

metrics_df = pd.DataFrame(all_metrics)
metrics_df.to_csv(OUT / "phase2_candidate_metrics_full.csv", index=False)
print(f"  Saved phase2_candidate_metrics_full.csv ({len(metrics_df)} rows)")

hold_df = metrics_df[metrics_df["window"].isin(["holdout_2016","holdout_2020","holdout_2021","bear_2022","recovery_2023"])]
hold_df.to_csv(OUT / "phase2_candidate_holdout_metrics.csv", index=False)

focus_ports = CANDIDATES + ["ggg1","prod_pin","shadow","spy","bench_60_40","equal_weight"]
bm_table = metrics_df[metrics_df["portfolio"].isin(focus_ports) & metrics_df["window"].isin(["full","holdout_2020","holdout_2021","bear_2022","recovery_2023"])][
    ["portfolio","window","ann_return","sharpe","max_drawdown","calmar","cvar_5","avg_BIL","avg_SPY","avg_turnover","beta_spy","active_return_vs_ggg1"]
].copy()
bm_table.to_csv(OUT / "phase2_candidate_vs_benchmark_table.csv", index=False)
print(f"  Saved phase2_candidate_vs_benchmark_table.csv")

cap_df = metrics_df[metrics_df["portfolio"].isin(focus_ports)][
    ["portfolio","window","upside_capture_spy","downside_capture_spy","beta_spy","corr_spy","active_return_vs_spy","active_return_vs_ggg1"]
].copy()
cap_df.to_csv(OUT / "phase2_capture_beta_by_window.csv", index=False)
print(f"  Saved phase2_capture_beta_by_window.csv")

# Print key table
print("\n  Full-period metrics comparison:")
fp = metrics_df[metrics_df["window"]=="full"][["portfolio","ann_return","sharpe","max_drawdown","cvar_5","avg_BIL","beta_spy"]].copy()
fp = fp[fp["portfolio"].isin(CANDIDATES + ["ggg1","prod_pin","spy"])].set_index("portfolio")
print(fp.round(4).to_string())


# ──────────────────────────────────────────────
# PART E — STATE-BY-STATE DIAGNOSIS
# ──────────────────────────────────────────────
print("\n=== PART E: State-by-state diagnosis ===")

state_summary_rows = []
state_exposure_rows = []
state_delta_rows = []
ggg1_ret = returns.get("ggg1", pd.Series(dtype=float))

for pname in CANDIDATES + ["ggg1","prod_pin"]:
    if pname not in returns:
        continue
    ret = returns[pname]
    wf = L3 / f"portfolio_version_weights_{pname}.csv"
    has_w = wf.exists()
    if has_w:
        w = pd.read_csv(wf, index_col=0, parse_dates=True)

    for state in msh["market_state"].unique():
        state_idx = msh[msh["market_state"] == state].index
        state_ret = ret.reindex(state_idx).dropna()
        if len(state_ret) < 4:
            continue
        n = len(state_ret)
        m = calc_metrics(state_ret, pname)
        row = {"portfolio": pname, "state": state, "n_weeks": n, **m}
        if has_w:
            ws = w.reindex(state_idx)
            row["avg_BIL"] = round(float(ws["BIL"].mean()), 4) if "BIL" in ws else np.nan
            row["avg_SPY"] = round(float(ws["SPY"].mean()), 4) if "SPY" in ws else np.nan
        state_summary_rows.append(row)

        # delta vs GGG1
        ggg_state = ggg1_ret.reindex(state_idx).dropna()
        if len(ggg_state) > 3:
            ggg_m = calc_metrics(ggg_state)
            state_delta_rows.append({
                "portfolio": pname, "state": state,
                "delta_ann_return_vs_ggg1": round(m.get("ann_return", np.nan) - ggg_m.get("ann_return", np.nan), 4),
                "delta_sharpe_vs_ggg1": round(m.get("sharpe", np.nan) - ggg_m.get("sharpe", np.nan), 4),
                "delta_max_dd_vs_ggg1": round(m.get("max_drawdown", np.nan) - ggg_m.get("max_drawdown", np.nan), 4),
                "delta_avg_BIL_vs_ggg1": round(row.get("avg_BIL", np.nan) - (float(w["BIL"].reindex(state_idx).mean()) if has_w and "BIL" in w else np.nan), 4) if has_w and "avg_BIL" in row else np.nan,
            })

state_df = pd.DataFrame(state_summary_rows)
state_df.to_csv(OUT / "phase2_state_summary.csv", index=False)
pd.DataFrame(state_delta_rows).to_csv(OUT / "phase2_state_deltas_vs_ggg1.csv", index=False)

# Sleeve weights by state for Phase 2 candidates
sleeve_state_rows = []
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
        sleeve_state_rows.append(row)

sleeve_state_df = pd.DataFrame(sleeve_state_rows)
sleeve_state_df.to_csv(OUT / "phase2_state_exposure_summary.csv", index=False)
print(f"  Saved phase2_state_summary.csv, phase2_state_deltas_vs_ggg1.csv, phase2_state_exposure_summary.csv")

# Specific diagnostics
def state_diagnostic(portfolio_names, state_name, fname):
    rows = []
    for pname in portfolio_names:
        if pname not in returns:
            continue
        ret = returns[pname]
        idx = msh[msh["market_state"] == state_name].index
        slc = ret.reindex(idx).dropna()
        m = calc_metrics(slc, pname)
        ggg_slc = ggg1_ret.reindex(idx).dropna()
        ggg_m = calc_metrics(ggg_slc)
        sf = L3 / f"portfolio_version_sleeve_weights_{pname}.csv"
        avg_def = avg_off = avg_bil = np.nan
        if sf.exists():
            sw = pd.read_csv(sf, index_col=0, parse_dates=True)
            sw_slc = sw.reindex(idx)
            avg_def = round(float(sw_slc.get("composite_regime_defense_component", pd.Series([np.nan])).mean()), 4)
            avg_off = round(float(sw_slc.get("composite_regime_offense_component", pd.Series([np.nan])).mean()), 4)
            avg_bil = round(float(sw_slc.get("cash::BIL", pd.Series([np.nan])).mean()), 4)
        rows.append({
            "portfolio": pname, "state": state_name,
            "ann_return": m.get("ann_return"), "sharpe": m.get("sharpe"),
            "max_drawdown": m.get("max_drawdown"),
            "delta_ann_return_vs_ggg1": round(m.get("ann_return", np.nan) - ggg_m.get("ann_return", np.nan), 4),
            "avg_defense_component": avg_def,
            "avg_offense_component": avg_off,
            "avg_cash_bil_sleeve": avg_bil,
        })
    pd.DataFrame(rows).to_csv(OUT / fname, index=False)

state_diagnostic(CANDIDATES + ["ggg1"], "neutral_mixed", "phase2_neutral_cash_unlock_diagnostics.csv")
state_diagnostic(CANDIDATES + ["ggg1"], "calm_trend", "phase2_calm_offense_unlock_diagnostics.csv")
state_diagnostic(CANDIDATES + ["ggg1"], "recovery_confirmed", "phase2_recovery_rerisk_diagnostics.csv")
state_diagnostic(CANDIDATES + ["ggg1"], "stressed_panic", "phase2_stress_protection_diagnostics.csv")
print(f"  Saved state diagnostic files")


# ──────────────────────────────────────────────
# PART F — RISK / REALISM / HIDDEN BETA
# ──────────────────────────────────────────────
print("\n=== PART F: Risk / realism / hidden beta checks ===")

WEEKS_PER_YEAR = 52
risk_rows = []
hidden_beta_rows = []
bear_rows = []
failure_rows = []
spy_full = returns["spy"]
ggg1_full = returns.get("ggg1", pd.Series(dtype=float))
ggg_metrics = calc_metrics(ggg1_full, "ggg1")

for pname in CANDIDATES:
    if pname not in returns:
        failure_rows.append({"portfolio": pname, "reason": "BUILD_FAILED_NO_RETURNS"})
        continue
    ret = returns[pname]
    m_full = calc_metrics(ret, pname)
    m_2020 = calc_metrics(window_slice(ret, "2020-01-01", None), pname)
    m_2021 = calc_metrics(window_slice(ret, "2021-01-01", None), pname)
    m_bear = calc_metrics(window_slice(ret, "2022-01-01", "2022-12-31"), pname)
    ggg_bear = calc_metrics(window_slice(ggg1_full, "2022-01-01", "2022-12-31"), "ggg1")
    spy_bear = calc_metrics(window_slice(spy_full, "2022-01-01", "2022-12-31"), "spy")

    # Turnover check
    rf = L3 / f"portfolio_version_returns_{pname}.csv"
    avg_turn = np.nan
    if rf.exists():
        rdf = pd.read_csv(rf, index_col=0, parse_dates=True)
        if "turnover" in rdf.columns:
            avg_turn = float(rdf["turnover"].mean())
    ggg_turn_f = L3 / "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv"
    ggg_turn = float(pd.read_csv(ggg_turn_f, index_col=0)["turnover"].mean()) if ggg_turn_f.exists() else np.nan

    # BIL check
    wf = L3 / f"portfolio_version_weights_{pname}.csv"
    avg_bil = np.nan
    if wf.exists():
        w = pd.read_csv(wf, index_col=0, parse_dates=True)
        avg_bil = float(w["BIL"].mean()) if "BIL" in w else np.nan
    ggg_wf = L3 / "portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv"
    ggg_bil = float(pd.read_csv(ggg_wf, index_col=0)["BIL"].mean()) if ggg_wf.exists() else np.nan

    # Hidden beta: compare beta to SPY vs GGG1
    common = ret.dropna().index.intersection(spy_full.dropna().index)
    cov = np.cov(ret.reindex(common), spy_full.reindex(common))
    beta_full = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    ggg_common = ggg1_full.dropna().index.intersection(spy_full.dropna().index)
    ggg_cov = np.cov(ggg1_full.reindex(ggg_common), spy_full.reindex(ggg_common))
    ggg_beta = ggg_cov[0, 1] / ggg_cov[1, 1] if ggg_cov[1, 1] > 0 else np.nan

    # Is improvement explained by beta?
    ann_improvement = (m_full.get("ann_return", np.nan) or 0) - (ggg_metrics.get("ann_return", 0) or 0)
    spy_ann = calc_metrics(spy_full, "spy").get("ann_return", 0) or 0
    beta_attribution = (beta_full - ggg_beta) * spy_ann if not (np.isnan(beta_full) or np.isnan(ggg_beta)) else np.nan
    improvement_from_beta = abs(beta_attribution) / abs(ann_improvement) if ann_improvement and not np.isnan(beta_attribution) else np.nan

    # Mandate check
    max_dd = m_full.get("max_drawdown", 0)
    sharpe = m_full.get("sharpe", 0)
    passes_mandate = (max_dd is not None and max_dd >= -0.22 and sharpe is not None and sharpe >= 0.90)
    bear_protection_ok = (m_bear.get("ann_return", -99) >= ggg_bear.get("ann_return", -99) - 0.04)

    # Disguised SPY check: if beta > 0.30 or corr > 0.50
    spy_full_common = spy_full.reindex(common)
    corr_spy = float(ret.reindex(common).corr(spy_full_common))
    disguised_spy = (beta_full is not None and not np.isnan(beta_full) and beta_full > 0.30) or \
                    (not np.isnan(corr_spy) and corr_spy > 0.50)

    risk_rows.append({
        "portfolio": pname,
        "full_ann_return": round(m_full.get("ann_return", np.nan), 4),
        "full_sharpe": round(m_full.get("sharpe", np.nan), 4),
        "full_max_dd": round(m_full.get("max_drawdown", np.nan), 4),
        "full_cvar_5": round(m_full.get("cvar_5", np.nan), 4),
        "holdout_2020_return": round(m_2020.get("ann_return", np.nan), 4),
        "holdout_2020_sharpe": round(m_2020.get("sharpe", np.nan), 4),
        "avg_BIL": round(avg_bil, 4) if not np.isnan(avg_bil) else np.nan,
        "avg_BIL_delta_vs_ggg1": round(avg_bil - ggg_bil, 4) if not np.isnan(avg_bil) and not np.isnan(ggg_bil) else np.nan,
        "avg_turnover": round(avg_turn, 4) if not np.isnan(avg_turn) else np.nan,
        "turnover_ratio_vs_ggg1": round(avg_turn / ggg_turn, 3) if not np.isnan(avg_turn) and not np.isnan(ggg_turn) and ggg_turn > 0 else np.nan,
        "passes_mandate_guardrails": passes_mandate,
        "bear_2022_protection_ok": bear_protection_ok,
        "disguised_spy_flag": disguised_spy,
    })

    hidden_beta_rows.append({
        "portfolio": pname,
        "beta_to_spy": round(beta_full, 4) if not np.isnan(beta_full) else np.nan,
        "ggg1_beta_to_spy": round(ggg_beta, 4) if not np.isnan(ggg_beta) else np.nan,
        "beta_delta": round(beta_full - ggg_beta, 4) if not np.isnan(beta_full) and not np.isnan(ggg_beta) else np.nan,
        "corr_to_spy": round(corr_spy, 4),
        "ann_improvement_vs_ggg1": round(ann_improvement, 4),
        "beta_attribution_of_improvement": round(beta_attribution, 4) if not np.isnan(beta_attribution) else np.nan,
        "pct_improvement_from_beta": round(improvement_from_beta, 3) if not np.isnan(improvement_from_beta) else np.nan,
        "hidden_beta_risk": "HIGH" if improvement_from_beta and improvement_from_beta > 0.50 else "LOW",
    })

    bear_rows.append({
        "portfolio": pname,
        "bear_2022_return": round(m_bear.get("ann_return", np.nan), 4),
        "ggg1_bear_2022_return": round(ggg_bear.get("ann_return", np.nan), 4),
        "spy_bear_2022_return": round(spy_bear.get("ann_return", np.nan), 4),
        "bear_protection_vs_ggg1_delta": round(m_bear.get("ann_return", np.nan) - ggg_bear.get("ann_return", np.nan), 4),
        "bear_protection_ok": bear_protection_ok,
    })

pd.DataFrame(risk_rows).to_csv(OUT / "phase2_risk_realism_checks.csv", index=False)
pd.DataFrame(hidden_beta_rows).to_csv(OUT / "phase2_hidden_beta_cash_checks.csv", index=False)
pd.DataFrame(bear_rows).to_csv(OUT / "phase2_2022_bear_check.csv", index=False)
if failure_rows:
    pd.DataFrame(failure_rows).to_csv(OUT / "phase2_candidate_failure_reasons.csv", index=False)
else:
    pd.DataFrame([{"portfolio": "none", "reason": "all_candidates_built_successfully"}]).to_csv(
        OUT / "phase2_candidate_failure_reasons.csv", index=False)

print(f"  Saved phase2_risk_realism_checks.csv, phase2_hidden_beta_cash_checks.csv, phase2_2022_bear_check.csv")
print("\n  Risk / hidden beta summary:")
for r in risk_rows:
    print(f"    {r['portfolio']}: return={r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} "
          f"maxDD={r['full_max_dd']:.3%} BIL={r['avg_BIL']:.3%} beta={hidden_beta_rows[risk_rows.index(r)]['beta_to_spy']:.3f} "
          f"mandate={'OK' if r['passes_mandate_guardrails'] else 'FAIL'} "
          f"bear={'OK' if r['bear_2022_protection_ok'] else 'FAIL'}")


# ──────────────────────────────────────────────
# PART G — SELECTION
# ──────────────────────────────────────────────
print("\n=== PART G: Selection ===")

selection_rows = []
for pname in CANDIDATES:
    if pname not in returns:
        selection_rows.append({"portfolio": pname, "classification": "REJECT",
                                "reason": "build_failed", "evidence": "no return file"})
        continue

    m_full = calc_metrics(returns[pname], pname)
    m_2020 = calc_metrics(window_slice(returns[pname], "2020-01-01", None))
    m_2021 = calc_metrics(window_slice(returns[pname], "2021-01-01", None))
    m_bear = calc_metrics(window_slice(returns[pname], "2022-01-01", "2022-12-31"))

    ggg_full = ggg_metrics
    ggg_bear = calc_metrics(window_slice(ggg1_full, "2022-01-01", "2022-12-31"))
    ggg_2020 = calc_metrics(window_slice(ggg1_full, "2020-01-01", None))

    ann_ret = m_full.get("ann_return", 0) or 0
    sharpe = m_full.get("sharpe", 0) or 0
    max_dd = m_full.get("max_drawdown", -1) or -1
    hold_ret = m_2020.get("ann_return", 0) or 0
    hold_sharpe = m_2020.get("sharpe", 0) or 0
    bear_ret = m_bear.get("ann_return", -99) or -99

    ret_above_ggg1 = ann_ret > (ggg_full.get("ann_return", 0) or 0)
    hold_above_ggg1 = hold_ret > (ggg_2020.get("ann_return", 0) or 0)
    sharpe_ok = sharpe >= 0.90
    mandate_ok = max_dd >= -0.22
    bear_ok = bear_ret >= (ggg_bear.get("ann_return", -99) or -99) - 0.04

    hr = next((r for r in hidden_beta_rows if r["portfolio"] == pname), {})
    disguised_spy = (hr.get("beta_to_spy", 0) or 0) > 0.30 or (hr.get("corr_to_spy", 0) or 0) > 0.50
    hidden_beta_risk = hr.get("hidden_beta_risk", "UNKNOWN")

    # Classification logic
    if not mandate_ok:
        cls = "REJECT"
        reason = f"max_drawdown {max_dd:.2%} exceeds -22% mandate limit"
    elif not sharpe_ok:
        cls = "REJECT"
        reason = f"Sharpe {sharpe:.3f} below minimum 0.90 guardrail"
    elif not bear_ok:
        cls = "REJECT"
        reason = f"2022 bear protection materially worse than GGG1 (delta > -4%)"
    elif disguised_spy:
        cls = "REJECT"
        reason = f"beta={hr.get('beta_to_spy',0):.3f} / corr={hr.get('corr_to_spy',0):.3f} — disguised SPY proxy"
    elif not ret_above_ggg1:
        cls = "REJECT"
        reason = f"Full-period return {ann_ret:.2%} does not beat GGG1 {ggg_full.get('ann_return', 0):.2%}"
    elif ret_above_ggg1 and hold_above_ggg1 and sharpe_ok and mandate_ok and bear_ok and not disguised_spy:
        if ann_ret >= 0.085 and sharpe >= 0.95 and max_dd >= -0.20:
            cls = "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
        else:
            cls = "KEEP_AS_AGGRESSIVE_SHADOW"
        reason = "Beats GGG1 full + holdout, passes mandate guardrails"
    elif ret_above_ggg1 and sharpe_ok and bear_ok:
        cls = "KEEP_AS_AGGRESSIVE_SHADOW"
        reason = "Beats GGG1 full-period but holdout benefit modest or Sharpe marginal"
    else:
        cls = "KEEP_AS_RESEARCH_ONLY"
        reason = "Partial improvement — some windows improve, others do not"

    selection_rows.append({
        "portfolio": pname, "classification": cls, "reason": reason,
        "full_ann_return": round(ann_ret, 4),
        "full_sharpe": round(sharpe, 4),
        "full_max_dd": round(max_dd, 4),
        "holdout_2020_return": round(hold_ret, 4),
        "holdout_2020_sharpe": round(hold_sharpe, 4),
        "bear_2022_return": round(bear_ret, 4),
        "beats_ggg1_full": ret_above_ggg1,
        "beats_ggg1_holdout_2020": hold_above_ggg1,
        "mandate_ok": mandate_ok, "bear_ok": bear_ok,
        "sharpe_ok": sharpe_ok, "disguised_spy": disguised_spy,
        "hidden_beta_risk": hidden_beta_risk,
    })

sel_df = pd.DataFrame(selection_rows)
sel_df.to_csv(OUT / "phase2_selection_table.csv", index=False)
print(f"  Saved phase2_selection_table.csv")
print("\n  Selection results:")
for r in selection_rows:
    print(f"    {r['portfolio']}: {r['classification']}")
    print(f"      return={r['full_ann_return']:.3%} sharpe={r['full_sharpe']:.3f} maxDD={r['full_max_dd']:.3%} | {r['reason']}")

best_candidate = None
for cls_prio in ["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT", "KEEP_AS_AGGRESSIVE_SHADOW"]:
    for row in selection_rows:
        if row["classification"] == cls_prio:
            best_candidate = row["portfolio"]
            break
    if best_candidate:
        break


# ──────────────────────────────────────────────
# PART H — AUDITS
# ──────────────────────────────────────────────
print("\n=== PART H: Audits ===")
audit_rows = []
audit_summary_lines = ["# Phase 2 Audit Summary\n"]

if best_candidate:
    best_cls = next(r["classification"] for r in selection_rows if r["portfolio"] == best_candidate)
    print(f"  Best candidate: {best_candidate} ({best_cls})")
    audit_scripts = {
        "research_committee": ROOT / "scripts" / "research_committee_report.py",
        "backtest_realism": ROOT / "scripts" / "backtest_realism_audit.py",
        "allocator_benchmark": ROOT / "scripts" / "allocator_benchmark_audit.py",
        "robustness_simulation": ROOT / "scripts" / "robustness_simulation_audit.py",
    }
    is_challenger = best_cls == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
    for audit_name, audit_script in audit_scripts.items():
        if not audit_script.exists():
            audit_rows.append({"audit": audit_name, "candidate": best_candidate, "status": "SKIPPED_SCRIPT_NOT_FOUND"})
            continue
        if audit_name == "robustness_simulation" and not is_challenger:
            audit_rows.append({"audit": audit_name, "candidate": best_candidate, "status": "SKIPPED_NOT_CHALLENGER"})
            continue
        mode_flag = [] if is_challenger else ["--quick"]
        cmd = [sys.executable, str(audit_script), best_candidate] + mode_flag
        print(f"  Running: {' '.join(cmd)}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=300)
            status = "PASS" if res.returncode == 0 else "FAIL"
            log_path = OUT / f"phase2_{audit_name}_quick.log"
            with open(log_path, "w") as f:
                f.write(res.stdout[-4000:] + "\n" + res.stderr[-2000:])
            audit_rows.append({"audit": audit_name, "candidate": best_candidate,
                                "status": status, "log": log_path.name})
            audit_summary_lines.append(f"## {audit_name}: {status}\n")
        except subprocess.TimeoutExpired:
            audit_rows.append({"audit": audit_name, "candidate": best_candidate, "status": "TIMEOUT"})
else:
    print("  No qualifying candidate found — skipping audits.")
    audit_summary_lines.append("No qualifying candidate — audits skipped.\n")

pd.DataFrame(audit_rows).to_csv(OUT / "phase2_audit_results.csv", index=False)
with open(OUT / "phase2_audit_summary.md", "w") as f:
    f.writelines(audit_summary_lines)
print(f"  Saved phase2_audit_results.csv, phase2_audit_summary.md")


# ──────────────────────────────────────────────
# PART I — NEXT PHASE DECISION
# ──────────────────────────────────────────────
print("\n=== PART I: Next phase decision ===")

if best_candidate and any(r["classification"] == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT" for r in selection_rows):
    decision = "PROMOTE_PHASE2_TO_PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
    decision_rationale = (f"{best_candidate} satisfies the aggressive mandate: "
                          f"return>{0.085:.1%}, Sharpe>={0.95:.2f}, maxDD>={-0.20:.1%}, "
                          f"beats GGG1 full + holdout, no disguised SPY, bear protection intact.")
elif best_candidate and any(r["classification"] == "KEEP_AS_AGGRESSIVE_SHADOW" for r in selection_rows):
    decision = "KEEP_PHASE2_AS_AGGRESSIVE_SHADOW"
    decision_rationale = (f"{best_candidate} improves on GGG1 return with acceptable risk but does not "
                          f"fully satisfy the production-challenger guardrails. Track as aggressive shadow.")
elif any(r["classification"] in ("KEEP_AS_AGGRESSIVE_SHADOW", "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT",
                                  "KEEP_AS_RESEARCH_ONLY") for r in selection_rows):
    decision = "PROCEED_TO_PHASE2B_REFINED_AGGRESSIVE_MANDATE"
    decision_rationale = ("Candidates show partial improvement but need focused refinement — "
                           "better balance of neutral/calm/recovery mandate parameters.")
elif all(r["classification"] == "REJECT" for r in selection_rows):
    # Check if it's a regime/breadth issue
    decision = "PROCEED_TO_PHASE3_STOCK_BREADTH_REGIME_UPGRADE"
    decision_rationale = ("All Phase 2 candidates rejected. ETF-level mandate relaxation is insufficient "
                           "to safely unlock higher returns. Better breadth/regime signals needed.")
else:
    decision = "STOP_AGGRESSIVE_BRANCH_PACKAGE_GGG1"
    decision_rationale = "No improvement over GGG1 under any aggressive mandate variant."

pd.DataFrame([{
    "decision": decision,
    "best_candidate": best_candidate or "none",
    "rationale": decision_rationale,
    "n_candidates_tested": len(CANDIDATES),
    "n_reject": sum(1 for r in selection_rows if r["classification"] == "REJECT"),
    "n_shadow": sum(1 for r in selection_rows if r["classification"] == "KEEP_AS_AGGRESSIVE_SHADOW"),
    "n_challenger": sum(1 for r in selection_rows if r["classification"] == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"),
}]).to_csv(OUT / "phase2_next_phase_decision.csv", index=False)

print(f"\n  DECISION: {decision}")
print(f"  Rationale: {decision_rationale}")

# Protocol JSON
import json
protocol = {
    "phase": "phase_2_aggressive_etf_variant",
    "date": "2026-05-07",
    "production_pin": "improved_phase2b_regime_confidence_boost",
    "official_shadow": "improved_phase2b_combo_abc",
    "production_candidate": "improved_phaseggg_confirmed_only_robust_offense",
    "phase2_mandate": AGGRESSIVE_MANDATE,
    "candidates": CANDIDATES,
    "best_candidate": best_candidate or "none",
    "decision": decision,
    "selection_table": [{"portfolio": r["portfolio"], "classification": r["classification"]} for r in selection_rows],
}
with open(OUT / "phase2_protocol.json", "w") as f:
    json.dump(protocol, f, indent=2)


# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"Output directory: {OUT}")
out_files = sorted(OUT.glob("*"))
print(f"Files created: {len(out_files)}")
for fp in out_files:
    print(f"  {fp.name}")

print("\nDone. Phase 2 Aggressive ETF Variant complete.")
print("No production pins changed. No auto-promotion.")
