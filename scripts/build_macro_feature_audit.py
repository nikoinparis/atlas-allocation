"""Layer 3 — Macro / Risk Feature Audit (project-internal only).

Builds a weekly macro/risk feature panel from existing ETF return data
in `data/01_data_hub/weekly_returns.csv`. No external dependencies
(fredapi / OpenBB are NOT installed in this environment, so all features
are derived from already-tracked ETFs and from the Layer 2B regime
engine outputs).

Outputs to `data/research/macro_feature_audit/`:
  macro_features_weekly.csv
  macro_feature_metadata.csv
  macro_feature_coverage_report.md
  macro_regime_correlation_report.md

The script never asserts predictive value. It reports averages by state
and changes around transitions, leaving causal claims for the Layer 2B
phase reports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


OUT_DIR = roc.ROOT / "data" / "research" / "macro_feature_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Feature definitions (proxy/lag/source/notes)
FEATURE_SPECS = [
    # ETF-derived risk features
    ("hyg_lqd_credit_spread_proxy",
     "Credit-risk proxy: 13-week return of HYG minus 13-week return of LQD. "
     "Negative values indicate credit deterioration relative to investment grade.",
     "ETF returns (HYG, LQD)", "0w (already weekly observed)"),
    ("uup_dollar_strength_4w",
     "Dollar strength proxy: 4-week return of UUP. Positive = USD strengthening.",
     "ETF returns (UUP)", "0w"),
    ("tlt_rate_sensitive_4w",
     "Rate-sensitive proxy: 4-week return of TLT (long Treasury). "
     "Positive = rates falling / flight to quality.",
     "ETF returns (TLT)", "0w"),
    ("gld_defensive_4w",
     "Defensive/inflation proxy: 4-week return of GLD.",
     "ETF returns (GLD)", "0w"),
    ("spy_realized_vol_4w",
     "SPY realized weekly std × sqrt(52), 4-week trailing window. "
     "Used as VIX proxy in absence of VIX data.",
     "ETF returns (SPY)", "0w"),
    ("spy_drawdown_from_52w_high",
     "SPY drawdown vs trailing 52w cumulative high.",
     "ETF returns (SPY)", "0w"),
    ("spy_minus_iei_3m",
     "Risk-on / risk-off proxy: 13-week return of SPY minus 13-week return of IEF.",
     "ETF returns (SPY, IEF)", "0w"),
    ("xlf_minus_xlu_3m",
     "Cyclical-vs-defensive sector proxy: 13-week return of XLF minus 13-week return of XLU.",
     "ETF returns (XLF, XLU)", "0w"),
    ("ig_credit_4w",
     "Investment-grade credit proxy: 4-week return of LQD.",
     "ETF returns (LQD)", "0w"),
    ("hy_credit_4w",
     "High-yield credit proxy: 4-week return of HYG.",
     "ETF returns (HYG)", "0w"),
    # Regime-engine derived features (already in market_state_history.csv,
    # surfaced here for one-shot review)
    ("regime_recent_stress_26w",
     "Layer 2B `recent_stress_26w` field — realized stress index.",
     "market_state_history.csv (regime engine)", "regime engine baseline"),
    ("regime_avg_corr_risk_off_z",
     "Layer 2B `avg_corr_risk_off_z` — pairwise correlation pressure.",
     "market_state_history.csv (regime engine)", "regime engine baseline"),
    ("regime_transition_non_stress_prob",
     "Layer 2B `transition_non_stress_prob`.",
     "market_state_history.csv (regime engine)", "regime engine baseline"),
    ("regime_market_drawdown",
     "Layer 2B `market_drawdown`.",
     "market_state_history.csv (regime engine)", "regime engine baseline"),
    ("regime_breadth_sma_43",
     "Layer 2B `breadth_sma_43` — % of universe above 43-week SMA.",
     "market_state_history.csv (regime engine)", "regime engine baseline"),
]


def cumulative_return(weekly_returns: pd.Series, weeks: int) -> pd.Series:
    log_r = np.log1p(weekly_returns.astype(float))
    return np.expm1(log_r.rolling(window=weeks, min_periods=weeks).sum())


def trailing_cum_high(spy: pd.Series, weeks: int = 52) -> pd.Series:
    log_r = np.log1p(spy.astype(float))
    cum = log_r.cumsum().apply(np.exp)
    high = cum.rolling(window=weeks, min_periods=weeks).max()
    return cum / high - 1.0


def realized_vol(weekly_returns: pd.Series, weeks: int = 4) -> pd.Series:
    return weekly_returns.rolling(window=weeks, min_periods=weeks).std(ddof=0) * np.sqrt(52)


def build_features(weekly: pd.DataFrame, state: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    feats = pd.DataFrame(index=weekly.index)
    coverage = []

    # ETF-derived
    if "HYG" in weekly.columns and "LQD" in weekly.columns:
        hyg13 = cumulative_return(weekly["HYG"], 13)
        lqd13 = cumulative_return(weekly["LQD"], 13)
        feats["hyg_lqd_credit_spread_proxy"] = hyg13 - lqd13
    if "UUP" in weekly.columns:
        feats["uup_dollar_strength_4w"] = cumulative_return(weekly["UUP"], 4)
    if "TLT" in weekly.columns:
        feats["tlt_rate_sensitive_4w"] = cumulative_return(weekly["TLT"], 4)
    if "GLD" in weekly.columns:
        feats["gld_defensive_4w"] = cumulative_return(weekly["GLD"], 4)
    if "SPY" in weekly.columns:
        feats["spy_realized_vol_4w"] = realized_vol(weekly["SPY"], 4)
        feats["spy_drawdown_from_52w_high"] = trailing_cum_high(weekly["SPY"], 52)
    if "SPY" in weekly.columns and "IEF" in weekly.columns:
        spy13 = cumulative_return(weekly["SPY"], 13)
        ief13 = cumulative_return(weekly["IEF"], 13)
        feats["spy_minus_iei_3m"] = spy13 - ief13
    if "XLF" in weekly.columns and "XLU" in weekly.columns:
        xlf13 = cumulative_return(weekly["XLF"], 13)
        xlu13 = cumulative_return(weekly["XLU"], 13)
        feats["xlf_minus_xlu_3m"] = xlf13 - xlu13
    if "LQD" in weekly.columns:
        feats["ig_credit_4w"] = cumulative_return(weekly["LQD"], 4)
    if "HYG" in weekly.columns:
        feats["hy_credit_4w"] = cumulative_return(weekly["HYG"], 4)

    # Regime-engine derived (surfaced from existing state file)
    name_map = {
        "regime_recent_stress_26w": "recent_stress_26w",
        "regime_avg_corr_risk_off_z": "avg_corr_risk_off_z",
        "regime_transition_non_stress_prob": "transition_non_stress_prob",
        "regime_market_drawdown": "market_drawdown",
        "regime_breadth_sma_43": "breadth_sma_43",
    }
    for ours, theirs in name_map.items():
        if theirs in state.columns:
            feats[ours] = state[theirs].astype(float).reindex(feats.index)

    # Coverage table
    for spec in FEATURE_SPECS:
        col = spec[0]
        if col in feats.columns:
            s = feats[col].dropna()
            coverage.append({
                "feature": col,
                "description": spec[1],
                "source": spec[2],
                "lag_assumption": spec[3],
                "first_date": str(s.index.min())[:10] if len(s) else "",
                "last_date": str(s.index.max())[:10] if len(s) else "",
                "n_obs": int(len(s)),
                "n_total_weeks": int(len(feats)),
                "missing_frac": float(1 - len(s) / max(1, len(feats))),
                "available": True,
            })
        else:
            coverage.append({
                "feature": col,
                "description": spec[1],
                "source": spec[2],
                "lag_assumption": spec[3],
                "first_date": "",
                "last_date": "",
                "n_obs": 0,
                "n_total_weeks": int(len(feats)),
                "missing_frac": 1.0,
                "available": False,
            })

    return feats, coverage


def state_correlation(feats: pd.DataFrame, state: pd.DataFrame) -> dict:
    """Average feature value by state (original + refined if present)."""
    out = {}
    for state_col, label in [("market_state", "original"), ("refined_state", "refined")]:
        if state_col not in state.columns:
            continue
        joined = feats.join(state[[state_col]], how="inner").dropna(subset=[state_col])
        rows = []
        for s, sub in joined.groupby(state_col):
            row = {"state": s, "n_weeks": int(len(sub))}
            for c in feats.columns:
                row[c] = float(sub[c].mean())
            rows.append(row)
        out[label] = pd.DataFrame(rows)
    return out


def transition_event_window(feats: pd.DataFrame, state: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    """For each transition into stressed_panic, average feature value in
    the 4-week window leading into the transition vs the 4-week window
    after. Detects whether features systematically move ahead of stress."""
    if "market_state" not in state.columns:
        return pd.DataFrame()
    s = state["market_state"].astype(str)
    is_panic = s.eq("stressed_panic")
    enter_panic = is_panic & ~is_panic.shift(1, fill_value=False)
    events = enter_panic[enter_panic].index
    rows = []
    for c in feats.columns:
        before_vals, after_vals = [], []
        for ev in events:
            i = feats.index.get_indexer([ev])[0]
            if i < window or i + window >= len(feats):
                continue
            before = feats[c].iloc[i-window:i].mean()
            after = feats[c].iloc[i:i+window].mean()
            if pd.notna(before): before_vals.append(before)
            if pd.notna(after): after_vals.append(after)
        if not before_vals or not after_vals:
            continue
        rows.append({
            "feature": c,
            "n_transitions": len(events),
            "n_usable_events": min(len(before_vals), len(after_vals)),
            "mean_before_4w": float(np.mean(before_vals)),
            "mean_after_4w": float(np.mean(after_vals)),
            "delta_after_minus_before": float(np.mean(after_vals) - np.mean(before_vals)),
        })
    return pd.DataFrame(rows)


def write_coverage_report(coverage: list[dict]) -> Path:
    p = OUT_DIR / "macro_feature_coverage_report.md"
    lines = ["# Macro Feature Coverage Report\n\n"]
    lines.append("**Sources used:** project-internal ETF returns and Layer 2B regime engine output. ")
    lines.append("FRED API and OpenBB were not available in this environment (fredapi / openbb not installed; no live web egress).\n\n")
    lines.append("**No predictive claims** — the audit reports availability and state-conditional means only.\n\n")
    avail = [r for r in coverage if r["available"]]
    miss = [r for r in coverage if not r["available"]]
    lines.append(f"**Successfully built:** {len(avail)} / {len(coverage)} features.\n\n")
    if miss:
        lines.append("**Missing / unavailable features:**\n")
        for r in miss:
            lines.append(f"- `{r['feature']}` ({r['source']}): underlying data not available in repo.\n")
        lines.append("\n")
    lines.append("## Coverage table\n\n")
    df = pd.DataFrame(coverage)
    lines.append("```\n" + df.to_string(index=False) + "\n```\n\n")
    lines.append("## Lag / release-timing assumptions\n\n")
    lines.append("All ETF-derived features use weekly close prices already aligned to the project's "
                 "weekly date index. No additional lag is applied because the ETF prices are observable "
                 "in real time. Regime-engine-derived features inherit the regime engine's existing "
                 "1-week lag convention and are causal-safe at construction.\n\n")
    p.write_text("".join(lines))
    return p


def write_regime_correlation_report(feats: pd.DataFrame, state: pd.DataFrame) -> Path:
    p = OUT_DIR / "macro_regime_correlation_report.md"
    lines = ["# Macro Feature Regime Correlation Report\n\n"]
    lines.append("**No predictive claims** — averages by state and pre/post transition deltas only.\n\n")
    sc = state_correlation(feats, state)
    if "original" in sc:
        lines.append("## Average feature value by ORIGINAL state\n\n")
        lines.append("```\n" + sc["original"].to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")
    if "refined" in sc:
        lines.append("## Average feature value by REFINED state (Phase CC)\n\n")
        lines.append("Highlight: these are the rows that matter most for distinguishing "
                     "`neutral_healthy` vs `neutral_deteriorating`.\n\n")
        lines.append("```\n" + sc["refined"].to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

        # Side-by-side healthy vs deteriorating
        ref_df = sc["refined"].set_index("state")
        if "neutral_healthy" in ref_df.index and "neutral_deteriorating" in ref_df.index:
            comp_rows = []
            for c in feats.columns:
                h = ref_df.at["neutral_healthy", c] if c in ref_df.columns else float("nan")
                d = ref_df.at["neutral_deteriorating", c] if c in ref_df.columns else float("nan")
                comp_rows.append({"feature": c, "healthy_mean": h, "deteriorating_mean": d, "delta_d_minus_h": d - h if pd.notna(d) and pd.notna(h) else float("nan")})
            comp = pd.DataFrame(comp_rows)
            lines.append("### Healthy vs Deteriorating (Phase CC) — feature delta\n\n")
            lines.append("Positive `delta_d_minus_h` = feature is higher in deteriorating weeks. "
                         "Note the sign expectations: credit spread proxies should be more negative in deteriorating; "
                         "drawdown more negative in deteriorating; realized vol higher; risk-on - risk-off lower.\n\n")
            lines.append("```\n" + comp.to_string(index=False, float_format=lambda x: f"{x:+.4f}") + "\n```\n\n")
        else:
            lines.append(roc.warn_section("Refined state file missing `neutral_healthy` or `neutral_deteriorating` rows."))
    else:
        lines.append(roc.warn_section("Refined state file not available; skipped Phase CC overlay."))

    lines.append("## Pre/post stressed_panic transition window (event study)\n\n")
    twd = transition_event_window(feats, state, window=4)
    if twd.empty:
        lines.append(roc.warn_section("No usable transition events; cannot compute event study."))
    else:
        lines.append(f"Window: 4 weeks before vs 4 weeks after the first week of each stressed_panic transition.\n\n")
        lines.append("```\n" + twd.to_string(index=False, float_format=lambda x: f"{x:+.4f}") + "\n```\n\n")
        lines.append("Interpretation guide: `delta_after_minus_before` should be **negative** for credit and "
                     "risk-on - risk-off proxies and **positive** for realized vol and stress proxies.\n\n")

    p.write_text("".join(lines))
    return p


def main():
    print("Loading data...")
    weekly = roc.load_weekly_returns()
    try:
        state = roc.load_market_state(refined=True)  # use refined if available
    except FileNotFoundError:
        state = roc.load_market_state(refined=False)

    print("Building macro/risk features...")
    feats, coverage = build_features(weekly, state)

    print(f"Saving outputs to {OUT_DIR.relative_to(roc.ROOT)}/...")
    feats.to_csv(OUT_DIR / "macro_features_weekly.csv")
    pd.DataFrame(coverage).to_csv(OUT_DIR / "macro_feature_metadata.csv", index=False)
    cov_path = write_coverage_report(coverage)
    rcr_path = write_regime_correlation_report(feats, state)

    print(f"  - macro_features_weekly.csv ({feats.shape[0]} rows × {feats.shape[1]} features)")
    print(f"  - macro_feature_metadata.csv")
    print(f"  - {cov_path.name}")
    print(f"  - {rcr_path.name}")
    n_avail = sum(1 for r in coverage if r["available"])
    print(f"\nFeatures successfully built: {n_avail} / {len(coverage)}")


if __name__ == "__main__":
    main()
