#!/usr/bin/env python3
"""
validate_stock_breadth_regime_lift.py
=======================================
!! SURVIVORSHIP-BIASED DIAGNOSTIC — NOT FOR PRODUCTION !!

Tests whether stock breadth signals (from build_stock_breadth_research.py)
show meaningful forward-return lift vs low-breadth weeks, broken out by the
project's existing market state (calm_trend, neutral_mixed, etc.).

Emphasises calm_trend because that is the current portfolio bottleneck.
Also compares stock breadth to existing ETF breadth where available.

Inputs (read-only):
    data/research/stock_breadth/stock_breadth_weekly.csv
    data/04_layer2b_risk_regime_engine/market_state_history.csv
    data/01_data_hub/weekly_returns.csv
    data/05_layer3_portfolio_construction/portfolio_version_returns_*.csv

Outputs:
    data/research/stock_breadth/stock_breadth_state_lift.csv
    data/research/stock_breadth/stock_breadth_forward_return_tests.csv
    data/research/stock_breadth/stock_breadth_vs_etf_breadth.csv
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DIAG_LABEL  = "SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY"
STATES      = ["calm_trend", "neutral_mixed", "recovery_fragile",
               "recovery_confirmed", "stressed_panic"]
FWD_WINDOWS = [4, 13]   # weeks
LAG_WEEKS   = 1         # lag breadth signal by 1 week (causal guard)
HIGH_THRESH = 0.65      # breadth above this = "high breadth" (60th pct proxy)
LOW_THRESH  = 0.40      # breadth below this = "low breadth"

ROOT = Path(__file__).resolve().parents[1]
L2B  = ROOT / "data" / "04_layer2b_risk_regime_engine"
HUB  = ROOT / "data" / "01_data_hub"
L3   = ROOT / "data" / "05_layer3_portfolio_construction"
OUT  = ROOT / "data" / "research" / "stock_breadth"

BREADTH_FILE  = OUT / "stock_breadth_weekly.csv"
METADATA_FILE = OUT / "stock_breadth_metadata.json"

print("=" * 68)
print("VALIDATE STOCK BREADTH REGIME LIFT — DIAGNOSTIC")
print(f"!! {DIAG_LABEL} !!")
print("=" * 68)

# Verify build script ran first
if not BREADTH_FILE.exists():
    print(f"\n  ERROR: {BREADTH_FILE.name} not found.")
    print("  Run build_stock_breadth_research.py first.")
    sys.exit(1)


# ─── helpers ──────────────────────────────────────────────────────────────────

def forward_return(ret: pd.Series, n: int) -> pd.Series:
    """Compound forward n-week return at each date t.

    fwd[t] = (1+ret[t+1]) * ... * (1+ret[t+n]) - 1
    This is causal: signal at t predicts return over the NEXT n periods.
    """
    wealth = (1 + ret.fillna(0)).cumprod()
    fwd = (wealth.shift(-n) / wealth) - 1
    # NaN out the last n rows (no forward window available)
    fwd.iloc[-n:] = np.nan
    return fwd


def lift_stats(fwd: pd.Series, mask_high: pd.Series,
               mask_low: pd.Series) -> dict:
    """Return statistics for high-breadth vs low-breadth forward returns."""
    h = fwd[mask_high].dropna()
    l = fwd[mask_low].dropna()
    if len(h) < 3 or len(l) < 3:
        return {
            "n_high": len(h), "n_low": len(l),
            "mean_fwd_high": np.nan, "mean_fwd_low": np.nan,
            "lift": np.nan, "hit_rate_high": np.nan, "hit_rate_low": np.nan,
        }
    return {
        "n_high":       len(h),
        "n_low":        len(l),
        "mean_fwd_high": float(h.mean()),
        "mean_fwd_low":  float(l.mean()),
        "lift":          float(h.mean() - l.mean()),
        "hit_rate_high": float((h > 0).mean()),
        "hit_rate_low":  float((l > 0).mean()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART A — LOAD INPUTS
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART A: Load inputs ===")

# ── Stock breadth ─────────────────────────────────────────────────────────────
breadth_df = pd.read_csv(BREADTH_FILE, index_col=0, parse_dates=True)
print(f"  Stock breadth: {breadth_df.shape[0]} weeks × {breadth_df.shape[1]} features")

# The breadth features we'll test
BREADTH_FEATURES = [
    "pct_above_200d_ma",
    "pct_above_50d_ma",
    "pct_positive_13w_return",
    "pct_positive_26w_return",
    "pct_near_52w_high",
]
BREADTH_FEATURES = [f for f in BREADTH_FEATURES if f in breadth_df.columns]

# ── Market state history ──────────────────────────────────────────────────────
try:
    state_hist = pd.read_csv(
        L2B / "market_state_history.csv", index_col=0, parse_dates=True
    )
    print(f"  Market state history: {state_hist.shape[0]} weeks")
except Exception as e:
    print(f"  ERROR: Could not load market state history: {e}")
    sys.exit(1)

# ── Weekly ETF returns (contains SPY) ────────────────────────────────────────
try:
    etf_returns = pd.read_csv(
        HUB / "weekly_returns.csv", index_col=0, parse_dates=True
    )
    spy_ret = etf_returns["SPY"].rename("spy_return")
    print(f"  ETF returns: {etf_returns.shape[0]} weeks "
          f"({etf_returns.index.min().date()} → {etf_returns.index.max().date()})")
except Exception as e:
    print(f"  WARNING: Could not load ETF returns: {e}")
    spy_ret = pd.Series(dtype=float, name="spy_return")

# ── Candidate portfolio returns ───────────────────────────────────────────────
CANDIDATE_FILES = {
    "prod_pin":    "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
    "ggg1":        "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    "phase4b":     "portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv",
    "phase6":      "portfolio_version_returns_improved_phase6_continuous_aggression_score.csv",
    "phase7":      "portfolio_version_returns_improved_phase7_stretch_target.csv",
}

cand_returns: dict[str, pd.Series] = {}
for label, fname in CANDIDATE_FILES.items():
    fpath = L3 / fname
    if fpath.exists():
        try:
            df = pd.read_csv(fpath, index_col=0, parse_dates=True)
            col = "net_return" if "net_return" in df.columns else df.columns[0]
            cand_returns[label] = df[col].rename(label)
            print(f"  Loaded {label}: {len(df)} weeks")
        except Exception as e:
            print(f"  WARNING: Could not load {label}: {e}")
    else:
        print(f"  WARNING: {fname} not found — skipping {label}")

# ── ETF breadth from market state history ─────────────────────────────────────
ETF_BREADTH_COL = "breadth_sma_43"
etf_breadth = (state_hist[ETF_BREADTH_COL].rename("etf_breadth_sma43")
               if ETF_BREADTH_COL in state_hist.columns else None)
if etf_breadth is not None:
    print(f"  ETF breadth ({ETF_BREADTH_COL}): {etf_breadth.notna().sum()} non-null weeks")
else:
    print(f"  WARNING: ETF breadth column '{ETF_BREADTH_COL}' not found in state history")


# ══════════════════════════════════════════════════════════════════════════════
# PART B — ALIGN ALL DATA TO COMMON WEEKLY INDEX
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART B: Align data ===")

# Use the market state index as the canonical weekly index
idx = state_hist.index

# Align all series to this index
breadth_aligned   = breadth_df.reindex(idx)
spy_aligned       = spy_ret.reindex(idx)
state_col         = state_hist["market_state"].reindex(idx)

cand_aligned: dict[str, pd.Series] = {
    label: s.reindex(idx) for label, s in cand_returns.items()
}

# ── Lag breadth signal by LAG_WEEKS (causal guard) ───────────────────────────
# breadth_lagged[t] = breadth from week t-1 (known before week t starts)
breadth_lagged = breadth_aligned[BREADTH_FEATURES].shift(LAG_WEEKS)

# For ETF breadth comparison, same lag
etf_breadth_lagged = (
    etf_breadth.reindex(idx).shift(LAG_WEEKS)
    if etf_breadth is not None else None
)

# ── Forward return series ─────────────────────────────────────────────────────
fwd_spy: dict[int, pd.Series] = {}
fwd_cand: dict[str, dict[int, pd.Series]] = {k: {} for k in cand_aligned}

for n in FWD_WINDOWS:
    fwd_spy[n] = forward_return(spy_aligned, n)
    for label, s in cand_aligned.items():
        fwd_cand[label][n] = forward_return(s, n)

overlap = breadth_lagged["pct_above_200d_ma"].notna() & spy_aligned.notna()
print(f"  Usable weeks (breadth + SPY): {overlap.sum()}")
if overlap.sum() < 50:
    print("  WARNING: Very few usable weeks — results will be noisy")


# ══════════════════════════════════════════════════════════════════════════════
# PART C — HIGH-BREADTH vs LOW-BREADTH: FULL SAMPLE
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART C: Full-sample high vs low breadth ===")

full_rows: list[dict] = []

for feat in BREADTH_FEATURES:
    sig = breadth_lagged[feat]
    for n in FWD_WINDOWS:
        fwd = fwd_spy[n]
        valid = sig.notna() & fwd.notna()
        hi = valid & (sig > HIGH_THRESH)
        lo = valid & (sig < LOW_THRESH)
        stats = lift_stats(fwd, hi, lo)
        row = {
            "feature":      feat,
            "fwd_weeks":    n,
            "scope":        "all_states",
            "high_thresh":  HIGH_THRESH,
            "low_thresh":   LOW_THRESH,
            "lag_weeks":    LAG_WEEKS,
            **stats,
        }
        full_rows.append(row)
        if feat == "pct_above_200d_ma":
            lift_pct = stats["lift"] * 100 if pd.notna(stats["lift"]) else float("nan")
            print(f"  {feat} {n}w: lift = {lift_pct:+.3f}% "
                  f"(H n={stats['n_high']}, L n={stats['n_low']})")


# ══════════════════════════════════════════════════════════════════════════════
# PART D — STATE-BY-STATE LIFT TABLE
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART D: State-by-state lift ===")

state_rows: list[dict] = []

for state in STATES:
    state_mask = state_col == state
    n_state_weeks = int(state_mask.sum())
    if n_state_weeks < 10:
        print(f"  {state}: only {n_state_weeks} weeks — skipping")
        continue

    for feat in BREADTH_FEATURES:
        sig = breadth_lagged[feat]
        for n in FWD_WINDOWS:
            fwd = fwd_spy[n]
            valid = state_mask & sig.notna() & fwd.notna()
            hi = valid & (sig > HIGH_THRESH)
            lo = valid & (sig < LOW_THRESH)
            stats = lift_stats(fwd, hi, lo)

            # Also compute for candidate portfolios
            cand_lift_4b = np.nan
            if "phase4b" in fwd_cand and n in fwd_cand["phase4b"]:
                fwd_c = fwd_cand["phase4b"][n]
                hi_c = valid & (sig > HIGH_THRESH)
                lo_c = valid & (sig < LOW_THRESH)
                s_c = lift_stats(fwd_c, hi_c, lo_c)
                cand_lift_4b = s_c["lift"]

            row = {
                "state":             state,
                "n_state_weeks":     n_state_weeks,
                "feature":           feat,
                "fwd_weeks":         n,
                "lag_weeks":         LAG_WEEKS,
                "high_thresh":       HIGH_THRESH,
                "low_thresh":        LOW_THRESH,
                "spy_mean_high":     stats["mean_fwd_high"],
                "spy_mean_low":      stats["mean_fwd_low"],
                "spy_lift":          stats["lift"],
                "n_high_weeks":      stats["n_high"],
                "n_low_weeks":       stats["n_low"],
                "hit_rate_high":     stats["hit_rate_high"],
                "phase4b_lift":      cand_lift_4b,
                "diagnostic_label":  DIAG_LABEL,
            }
            state_rows.append(row)

    # Print summary for calm_trend emphasis
    if state == "calm_trend":
        print(f"\n  *** CALM_TREND EMPHASIS ({n_state_weeks} weeks) ***")
        for n in FWD_WINDOWS:
            calm_row = next(
                (r for r in state_rows
                 if r["state"] == "calm_trend"
                 and r["feature"] == "pct_above_200d_ma"
                 and r["fwd_weeks"] == n),
                None
            )
            if calm_row:
                lift_pct = calm_row["spy_lift"] * 100 if pd.notna(calm_row["spy_lift"]) else float("nan")
                print(f"    pct_above_200d_ma {n}w SPY lift: {lift_pct:+.3f}% "
                      f"(H n={calm_row['n_high_weeks']}, L n={calm_row['n_low_weeks']})")
    else:
        print(f"  {state}: {n_state_weeks} weeks processed")

state_lift_df = pd.DataFrame(state_rows)
state_lift_df.to_csv(OUT / "stock_breadth_state_lift.csv", index=False)
print(f"\n  Saved stock_breadth_state_lift.csv ({len(state_rows)} rows)")


# ══════════════════════════════════════════════════════════════════════════════
# PART E — DETAILED FORWARD RETURN TESTS
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART E: Detailed forward return tests ===")

detail_rows: list[dict] = []

# Compute decile-level lift (not just high/low binary split)
DECILES = [0.3, 0.5, 0.7]  # additional thresholds

for state in ["all_states"] + STATES:
    if state == "all_states":
        base_mask = breadth_lagged["pct_above_200d_ma"].notna()
    else:
        base_mask = state_col == state

    if base_mask.sum() < 15:
        continue

    sig = breadth_lagged["pct_above_200d_ma"]
    fwd_4w  = fwd_spy[4]
    fwd_13w = fwd_spy[13]

    valid = base_mask & sig.notna() & fwd_4w.notna()
    if valid.sum() < 5:
        continue

    sig_valid    = sig[valid]
    fwd4_valid   = fwd_4w[valid]
    fwd13_valid  = fwd_spy[13][valid] if fwd_spy[13][valid].notna().any() else pd.Series(dtype=float)

    # Tercile analysis
    try:
        thirds = pd.qcut(sig_valid, 3, labels=["low", "mid", "high"])
        for tercile in ["low", "mid", "high"]:
            tmask = thirds == tercile
            row = {
                "state":       state,
                "feature":     "pct_above_200d_ma",
                "bucket":      tercile,
                "n":           int(tmask.sum()),
                "mean_4w_spy": float(fwd4_valid[tmask].mean()) if tmask.sum() > 0 else np.nan,
                "mean_13w_spy": float(fwd13_valid[tmask].mean()) if (tmask.sum() > 0 and len(fwd13_valid) > 0) else np.nan,
                "hit_rate_4w": float((fwd4_valid[tmask] > 0).mean()) if tmask.sum() > 0 else np.nan,
                "breadth_low":  float(sig_valid[tmask].min()) if tmask.sum() > 0 else np.nan,
                "breadth_high": float(sig_valid[tmask].max()) if tmask.sum() > 0 else np.nan,
                "diagnostic_label": DIAG_LABEL,
            }
            detail_rows.append(row)
    except Exception:
        pass

detail_df = pd.DataFrame(detail_rows) if detail_rows else pd.DataFrame()
if not detail_df.empty:
    detail_df.to_csv(OUT / "stock_breadth_forward_return_tests.csv", index=False)
    print(f"  Saved stock_breadth_forward_return_tests.csv ({len(detail_rows)} rows)")


# ══════════════════════════════════════════════════════════════════════════════
# PART F — STOCK BREADTH vs ETF BREADTH COMPARISON
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART F: Stock breadth vs ETF breadth comparison ===")

vs_etf_rows: list[dict] = []

if etf_breadth_lagged is not None and etf_breadth_lagged.notna().sum() > 20:
    for state in ["all_states"] + STATES:
        if state == "all_states":
            base_mask = pd.Series(True, index=idx)
        else:
            base_mask = state_col == state

        if base_mask.sum() < 15:
            continue

        for n in FWD_WINDOWS:
            fwd = fwd_spy[n]

            # Stock breadth 200d MA signal
            sig_stock = breadth_lagged["pct_above_200d_ma"]
            valid_s   = base_mask & sig_stock.notna() & fwd.notna()
            hi_s      = valid_s & (sig_stock > HIGH_THRESH)
            lo_s      = valid_s & (sig_stock < LOW_THRESH)
            stats_s   = lift_stats(fwd, hi_s, lo_s)

            # ETF breadth signal (breadth_sma_43 ≥ 0.65 as the existing gate)
            sig_etf   = etf_breadth_lagged
            valid_e   = base_mask & sig_etf.notna() & fwd.notna()
            hi_e      = valid_e & (sig_etf >= 0.65)
            lo_e      = valid_e & (sig_etf < 0.65)
            stats_e   = lift_stats(fwd, hi_e, lo_e)

            vs_etf_rows.append({
                "state":             state,
                "fwd_weeks":         n,
                "lag_weeks":         LAG_WEEKS,
                # Stock breadth
                "stock_breadth_feature": "pct_above_200d_ma",
                "stock_spy_lift":    stats_s["lift"],
                "stock_n_high":      stats_s["n_high"],
                "stock_n_low":       stats_s["n_low"],
                # ETF breadth
                "etf_breadth_feature": ETF_BREADTH_COL,
                "etf_spy_lift":      stats_e["lift"],
                "etf_n_high":        stats_e["n_high"],
                "etf_n_low":         stats_e["n_low"],
                # Comparison
                "stock_beats_etf":   (
                    (stats_s["lift"] > stats_e["lift"])
                    if pd.notna(stats_s["lift"]) and pd.notna(stats_e["lift"])
                    else None
                ),
                "diagnostic_label":  DIAG_LABEL,
            })

    if vs_etf_rows:
        vs_etf_df = pd.DataFrame(vs_etf_rows)
        vs_etf_df.to_csv(OUT / "stock_breadth_vs_etf_breadth.csv", index=False)
        print(f"  Saved stock_breadth_vs_etf_breadth.csv ({len(vs_etf_rows)} rows)")

        # Print calm_trend comparison
        calm_vs = vs_etf_df[
            (vs_etf_df["state"] == "calm_trend") & (vs_etf_df["fwd_weeks"] == 4)
        ]
        if not calm_vs.empty:
            r = calm_vs.iloc[0]
            s_l = r["stock_spy_lift"] * 100 if pd.notna(r["stock_spy_lift"]) else float("nan")
            e_l = r["etf_spy_lift"] * 100 if pd.notna(r["etf_spy_lift"]) else float("nan")
            print(f"\n  calm_trend 4w comparison:")
            print(f"    Stock breadth (pct_above_200d_ma) lift: {s_l:+.3f}%")
            print(f"    ETF breadth  (breadth_sma_43 ≥0.65) lift: {e_l:+.3f}%")
            print(f"    Stock beats ETF: {r['stock_beats_etf']}")
else:
    print("  Skipping ETF breadth comparison (insufficient data)")
    pd.DataFrame(vs_etf_rows).to_csv(OUT / "stock_breadth_vs_etf_breadth.csv", index=False)


# ══════════════════════════════════════════════════════════════════════════════
# PART G — FINAL SUMMARY OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== PART G: Summary ===")

# Print a clean summary table for the report
print("\n  CALM_TREND LIFT SUMMARY (pct_above_200d_ma, lagged 1 week):")
print(f"  {'Horizon':<10} {'SPY lift':>10} {'N_high':>7} {'N_low':>7}")
for n in FWD_WINDOWS:
    row = next(
        (r for r in state_rows
         if r["state"] == "calm_trend"
         and r["feature"] == "pct_above_200d_ma"
         and r["fwd_weeks"] == n),
        None
    )
    if row:
        lift_pct = row["spy_lift"] * 100 if pd.notna(row["spy_lift"]) else float("nan")
        print(f"  {n}w fwd     {lift_pct:+10.3f}%  {row['n_high_weeks']:>7}  {row['n_low_weeks']:>7}")

print("\n  ALL-STATE LIFT SUMMARY (pct_above_200d_ma, full sample):")
for r in full_rows:
    if r["feature"] == "pct_above_200d_ma":
        lift_pct = r["lift"] * 100 if pd.notna(r["lift"]) else float("nan")
        print(f"  {r['fwd_weeks']}w fwd: lift {lift_pct:+.3f}%  "
              f"(H n={r['n_high']}, L n={r['n_low']})")

print(f"\n  Files saved to: {OUT}")
print(f"  Bias: !! {DIAG_LABEL} !!")

# Save additional full_rows as the primary forward return test table
full_df = pd.DataFrame(full_rows)
full_df.to_csv(OUT / "stock_breadth_forward_return_tests.csv", index=False)
print(f"  Saved stock_breadth_forward_return_tests.csv ({len(full_rows)} rows)")

print("\n" + "=" * 68)
print("VALIDATE COMPLETE")
print(f"  Outputs: stock_breadth_state_lift.csv,")
print(f"           stock_breadth_forward_return_tests.csv,")
print(f"           stock_breadth_vs_etf_breadth.csv")
print(f"  !! {DIAG_LABEL} !!")
print("=" * 68)
