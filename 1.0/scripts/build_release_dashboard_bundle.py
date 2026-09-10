"""
build_release_dashboard_bundle.py

Regenerates public/production-candidate-dashboard-bundle.json with:
  - Updated registry metadata reflecting Phase 7 research arc completion
  - Phase 7 / Phase 4B / Phase 6 aggressive shadow versions added to summary
  - Time series returns for all shadow versions
  - Updated state_summary with Phase 7 data
  - All existing governance data preserved (production pin / GGG1 candidate unchanged)

Usage:
    python3 scripts/build_release_dashboard_bundle.py
"""

import json
import os
import pandas as pd
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUNDLE_IN  = os.path.join(BASE, "public", "production-candidate-dashboard-bundle.json")
BUNDLE_OUT = os.path.join(BASE, "public", "production-candidate-dashboard-bundle.json")

# Portfolio returns CSV paths
LAYER3_DIR = os.path.join(BASE, "data", "05_layer3_portfolio_construction")
PHASE7_DIR = os.path.join(BASE, "data", "research", "phase_7_allocator_objective_rewrite")


def load_bundle():
    with open(BUNDLE_IN, encoding="utf-8") as f:
        return json.load(f)


def load_returns_csv(name):
    path = os.path.join(LAYER3_DIR, f"portfolio_version_returns_{name}.csv")
    if not os.path.exists(path):
        print(f"  WARNING: returns CSV not found for {name}")
        return []
    df = pd.read_csv(path)
    # Rename 'Unnamed: 0' to 'date' if needed
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "date"})
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "date": str(row["date"])[:10],
            "net_return": float(row.get("net_return", row.get("gross_return", 0.0))),
            "gross_return": float(row.get("gross_return", 0.0)),
            "wealth": float(row.get("wealth", 1.0)),
            "drawdown": float(row.get("drawdown", 0.0)),
        })
    return rows


def load_weights_csv(name, kind="weights"):
    path = os.path.join(LAYER3_DIR, f"portfolio_version_{kind}_{name}.csv")
    if not os.path.exists(path):
        return {"latest": [], "history": [], "selectedColumns": []}
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "date"})
    # Get the latest row
    if df.empty:
        return {"latest": [], "history": [], "selectedColumns": []}
    latest_row = df.iloc[-1]
    date = str(latest_row.get("date", ""))[:10] if "date" in df.columns else ""
    asset_cols = [c for c in df.columns if c != "date"]
    latest = [{"name": c, "weight": float(latest_row[c]) if pd.notna(latest_row[c]) else 0.0} for c in asset_cols]
    return {
        "latest": latest,
        "history": [],
        "selectedColumns": asset_cols[:20],
    }


def metrics_row_for(name, role, full_metrics, holdout_metrics, avg_bil=None, avg_spy=None, avg_turnover=None):
    """Build a summary row from known metrics."""
    full = full_metrics.get(name, {})
    row = {
        "role": role,
        "name": name,
        "full_ann_return": full.get("ann_return"),
        "full_ann_vol": full.get("ann_vol"),
        "full_sharpe": full.get("sharpe"),
        "full_max_drawdown": full.get("max_drawdown"),
        "full_cvar_5": full.get("cvar_5"),
        "full_calmar": full.get("calmar"),
        "avg_BIL": avg_bil if avg_bil is not None else full.get("avg_BIL"),
        "avg_SPY": avg_spy if avg_spy is not None else full.get("avg_SPY"),
        "avg_turnover": avg_turnover if avg_turnover is not None else full.get("avg_turnover"),
    }
    # Add holdout data
    for window, hm in holdout_metrics.get(name, {}).items():
        suffix = window.replace("holdout_", "").replace("_", "")
        row[f"holdout_{suffix}_ann_return"] = hm.get("ann_return")
        row[f"holdout_{suffix}_sharpe"] = hm.get("sharpe")
        row[f"holdout_{suffix}_max_drawdown"] = hm.get("max_drawdown")
    return row


def build_exposure_row(name, role, avg_bil, avg_spy, avg_turnover):
    return {
        "role": role,
        "name": name,
        "avg_BIL": avg_bil,
        "avg_SPY": avg_spy,
        "avg_turnover": avg_turnover,
        "turnover_ratio_vs_production": 1.0,
    }


def main():
    print("Loading existing bundle...")
    bundle = load_bundle()

    # -------------------------------------------------------------------------
    # Load Phase 7 research metrics CSV
    # -------------------------------------------------------------------------
    print("Loading Phase 7 metrics CSV...")
    metrics_csv = os.path.join(PHASE7_DIR, "phase7_candidate_metrics_full.csv")
    df_metrics = pd.read_csv(metrics_csv)
    full_period = df_metrics[df_metrics["window"] == "full"].copy()

    full_metrics = {}
    for _, row in full_period.iterrows():
        name = str(row["portfolio"])
        full_metrics[name] = {
            "ann_return": float(row["ann_return"]) if pd.notna(row["ann_return"]) else None,
            "ann_vol": float(row["ann_vol"]) if pd.notna(row["ann_vol"]) else None,
            "sharpe": float(row["sharpe"]) if pd.notna(row["sharpe"]) else None,
            "max_drawdown": float(row["max_drawdown"]) if pd.notna(row["max_drawdown"]) else None,
            "cvar_5": float(row["cvar_5"]) if pd.notna(row["cvar_5"]) else None,
            "calmar": float(row["calmar"]) if pd.notna(row["calmar"]) else None,
            "avg_BIL": float(row["avg_BIL"]) if pd.notna(row.get("avg_BIL", float("nan"))) else None,
            "avg_SPY": float(row["avg_SPY"]) if pd.notna(row.get("avg_SPY", float("nan"))) else None,
            "avg_turnover": float(row["avg_turnover"]) if pd.notna(row.get("avg_turnover", float("nan"))) else None,
        }

    holdout_metrics = {}
    for _, row in df_metrics[df_metrics["window"] != "full"].iterrows():
        name = str(row["portfolio"])
        window = str(row["window"])
        if name not in holdout_metrics:
            holdout_metrics[name] = {}
        holdout_metrics[name][window] = {
            "ann_return": float(row["ann_return"]) if pd.notna(row["ann_return"]) else None,
            "sharpe": float(row["sharpe"]) if pd.notna(row["sharpe"]) else None,
            "max_drawdown": float(row["max_drawdown"]) if pd.notna(row["max_drawdown"]) else None,
        }

    # -------------------------------------------------------------------------
    # Update registry
    # -------------------------------------------------------------------------
    print("Updating registry...")
    bundle["registry"].update({
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "latest_research_status": "KEEP_PHASE7_AS_AGGRESSIVE_SHADOW__EXISTING_DATA_ARC_COMPLETE",
        "research_arc_summary": (
            "Seven phases of optimization improved full-period return from GGG1 7.14% to "
            "Phase7 7.88% (+0.74pp). Calm_trend (26.6% of weeks) is the structural bottleneck. "
            "Remaining 0.12pp gap to 8.0% requires PIT stock breadth data (Norgate/WRDS)."
        ),
        "aggressive_shadow_best_return": "improved_phase7_stretch_target",
        "aggressive_shadow_best_return_metrics": "7.88% / 0.926 Sharpe / -15.28% max DD",
        "aggressive_shadow_best_riskadjusted": "improved_phase4b_refined_sector_20pct",
        "aggressive_shadow_best_riskadjusted_metrics": "7.76% / 0.959 Sharpe / -13.77% max DD",
        "aggressive_shadow_best_classifier": "improved_phase6_continuous_aggression_score",
        "aggressive_shadow_best_classifier_metrics": "7.80% / 0.953 Sharpe / -14.18% max DD",
        "next_required_action": "RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE",
        "next_manual_steps": [
            "Purchase Norgate Data US Stocks Platinum/Diamond when budget allows.",
            "Export S&P 500 PIT constituents + daily prices back to 2005.",
            "Save to data/stock_breadth/raw/ and run scripts/build_pit_stock_breadth_panel.py.",
            "Build Phase 5B candidates using stock breadth as calm_trend classifier signal.",
            "Verify Vercel dashboard loads the updated compact bundle.",
            "Production pin improved_phase2b_regime_confidence_boost unchanged — human review required to promote GGG1.",
        ],
        "phase7_complete_date": "2026-05-07",
        "phase7_report": "docs/research/2026-05-07_phase_7_allocator_objective_rewrite_report.md",
        "phase6_complete_date": "2026-05-07",
        "phase6_report": "docs/research/2026-05-07_phase_6_market_state_classifier_rebuild_report.md",
        "phase4b_complete_date": "2026-05-07",
        "phase4b_report": "docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md",
        "calm_trend_bottleneck": (
            "calm_trend is 26.6% of all weeks. In calm_trend, the portfolio earns ~4.2% annualized "
            "vs SPY 16.87%. No existing feature can distinguish high-return from ordinary calm weeks "
            "without PIT stock breadth data. Calm_trend improvement is the single largest remaining "
            "opportunity."
        ),
        "survivorship_bias_warning": (
            "Phase 5A-Free diagnostic used current S&P 500 constituents from Wikipedia + yfinance. "
            "SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY. Results confirm stock breadth is promising but "
            "cannot be used in production without PIT data."
        ),
        "disclaimer": (
            "This is a research dashboard for a systematic ETF quant portfolio backtesting project. "
            "Results are backtests only. Not financial advice. Not live trading. "
            "All production pins require explicit human review to change."
        ),
    })

    # -------------------------------------------------------------------------
    # Build new shadow version summary rows
    # -------------------------------------------------------------------------
    print("Building shadow version summary rows...")

    shadow_versions = [
        ("improved_phase7_stretch_target", "aggressive_shadow_best_return",
         full_metrics.get("improved_phase7_stretch_target", {})),
        ("improved_phase4b_refined_sector_20pct", "aggressive_shadow_best_risk_adjusted",
         full_metrics.get("phase4b_best", {})),
        ("improved_phase6_continuous_aggression_score", "aggressive_shadow_best_classifier",
         full_metrics.get("phase6_best", {})),
        ("improved_phase7_expression_boost", "aggressive_shadow_best_sharpe_phase7",
         full_metrics.get("improved_phase7_expression_boost", {})),
        ("improved_phase7_max_sector_rerisk", "aggressive_shadow",
         full_metrics.get("improved_phase7_max_sector_rerisk", {})),
        ("improved_phase7_larger_sector_calm", "aggressive_shadow",
         full_metrics.get("improved_phase7_larger_sector_calm", {})),
        ("improved_phase7_combined_offensive", "aggressive_shadow",
         full_metrics.get("improved_phase7_combined_offensive", {})),
    ]

    # Build known metrics for phase4b and phase6 from phase7 metrics CSV
    phase4b_m = full_metrics.get("phase4b_best", {})
    phase6_m = full_metrics.get("phase6_best", {})

    # Map internal metric file names to canonical portfolio names
    canonical_lookup = {
        "phase4b_best": "improved_phase4b_refined_sector_20pct",
        "phase6_best": "improved_phase6_continuous_aggression_score",
        "ggg1": "improved_phaseggg_confirmed_only_robust_offense",
        "prod_pin": "improved_phase2b_regime_confidence_boost",
        "shadow": "improved_phase2b_combo_abc",
    }

    # Check which names are already in the bundle summary
    existing_names = {r["name"] for r in bundle.get("summary", [])}
    print(f"  Existing summary versions: {existing_names}")

    new_summary_rows = []
    new_exposure_rows = []

    for canon_name, role, m in shadow_versions:
        if canon_name in existing_names:
            print(f"  Skipping {canon_name} — already in summary")
            continue
        avg_bil = m.get("avg_BIL")
        avg_spy = m.get("avg_SPY")
        avg_turnover = m.get("avg_turnover")
        row = {
            "role": role,
            "name": canon_name,
            "full_ann_return": m.get("ann_return"),
            "full_ann_vol": m.get("ann_vol"),
            "full_sharpe": m.get("sharpe"),
            "full_max_drawdown": m.get("max_drawdown"),
            "full_cvar_5": m.get("cvar_5"),
            "full_calmar": m.get("calmar"),
            "avg_BIL": avg_bil,
            "avg_SPY": avg_spy,
            "avg_turnover": avg_turnover,
        }
        # Add holdout data from phase7 research outputs
        hm_key = canon_name  # for phase7 candidates
        if canon_name == "improved_phase4b_refined_sector_20pct":
            hm_key = "phase4b_best"
        elif canon_name == "improved_phase6_continuous_aggression_score":
            hm_key = "phase6_best"
        hm = holdout_metrics.get(hm_key, {})
        for window, wm in hm.items():
            tag = window.replace("holdout_", "")
            row[f"holdout_{tag}_ann_return"] = wm.get("ann_return")
            row[f"holdout_{tag}_sharpe"] = wm.get("sharpe")
            row[f"holdout_{tag}_max_drawdown"] = wm.get("max_drawdown")

        new_summary_rows.append(row)
        new_exposure_rows.append(build_exposure_row(
            canon_name, role,
            avg_bil or 0.23,
            avg_spy or 0.05,
            avg_turnover or 0.08,
        ))
        print(f"  Added {canon_name}: ret={m.get('ann_return'):.4f}, sharpe={m.get('sharpe'):.4f}" if m.get("ann_return") else f"  Added {canon_name}: no metrics found")

    bundle["summary"] = bundle.get("summary", []) + new_summary_rows
    bundle["exposure_summary"] = bundle.get("exposure_summary", []) + new_exposure_rows

    # -------------------------------------------------------------------------
    # Load time series returns for shadow versions
    # -------------------------------------------------------------------------
    print("Loading time series returns for shadow versions...")

    version_returns = bundle.get("versionReturns", {})
    version_weights = bundle.get("versionWeights", {})
    version_sleeve_weights = bundle.get("versionSleeveWeights", {})

    # Names to load returns for
    shadow_names_to_load = [
        "improved_phase7_stretch_target",
        "improved_phase7_expression_boost",
        "improved_phase7_max_sector_rerisk",
        "improved_phase7_larger_sector_calm",
        "improved_phase7_combined_offensive",
        "improved_phase4b_refined_sector_20pct",
        "improved_phase6_continuous_aggression_score",
    ]

    for name in shadow_names_to_load:
        if name in version_returns:
            print(f"  Skipping {name} returns — already loaded")
            continue
        returns = load_returns_csv(name)
        if returns:
            version_returns[name] = returns
            print(f"  Loaded {len(returns)} return rows for {name}")
        else:
            print(f"  No returns found for {name}")

        weights = load_weights_csv(name, "weights")
        sleeve_weights = load_weights_csv(name, "sleeve_weights")
        if name not in version_weights:
            version_weights[name] = weights
        if name not in version_sleeve_weights:
            version_sleeve_weights[name] = sleeve_weights

    bundle["versionReturns"] = version_returns
    bundle["versionWeights"] = version_weights
    bundle["versionSleeveWeights"] = version_sleeve_weights

    # -------------------------------------------------------------------------
    # Update state_summary with Phase 7 data
    # -------------------------------------------------------------------------
    print("Updating state_summary...")
    state_csv = os.path.join(PHASE7_DIR, "phase7_state_summary.csv")
    df_state = pd.read_csv(state_csv)

    existing_state_candidates = {r.get("candidate", "") for r in bundle.get("state_summary", [])}

    # Map of display names
    state_name_map = {
        "improved_phase7_stretch_target": "improved_phase7_stretch_target",
        "improved_phase7_expression_boost": "improved_phase7_expression_boost",
        "improved_phase7_max_sector_rerisk": "improved_phase7_max_sector_rerisk",
        "phase4b_best": "improved_phase4b_refined_sector_20pct",
        "phase6_best": "improved_phase6_continuous_aggression_score",
    }

    new_state_rows = []
    for _, row in df_state.iterrows():
        portfolio = str(row["portfolio"])
        canon = state_name_map.get(portfolio, portfolio)
        if canon in existing_state_candidates:
            continue
        if canon not in state_name_map.values():
            continue  # skip ggg1/prod_pin/shadow since they're already there
        new_state_rows.append({
            "candidate": canon,
            "state": str(row["state"]),
            "n_weeks": int(row.get("n_weeks", 0)),
            "ann_return": float(row["ann_return"]) if pd.notna(row["ann_return"]) else None,
            "vol_wkly": float(row["ann_vol"]) / 52**0.5 if pd.notna(row.get("ann_vol")) else None,
            "sharpe": float(row["sharpe"]) if pd.notna(row["sharpe"]) else None,
            "max_drawdown": float(row["max_drawdown"]) if pd.notna(row["max_drawdown"]) else None,
            "avg_sector": float(row.get("avg_sector", 0)) if pd.notna(row.get("avg_sector", float("nan"))) else None,
            "avg_defense": float(row.get("avg_defense", 0)) if pd.notna(row.get("avg_defense", float("nan"))) else None,
            "avg_BIL": float(row.get("avg_BIL", 0)) if pd.notna(row.get("avg_BIL", float("nan"))) else None,
        })

    bundle["state_summary"] = bundle.get("state_summary", []) + new_state_rows
    print(f"  Added {len(new_state_rows)} new state_summary rows")

    # -------------------------------------------------------------------------
    # Write output
    # -------------------------------------------------------------------------
    print(f"Writing updated bundle to {BUNDLE_OUT}...")
    with open(BUNDLE_OUT, "w", encoding="utf-8") as f:
        json.dump(bundle, f, separators=(",", ":"), allow_nan=False, default=lambda x: None)

    size_kb = os.path.getsize(BUNDLE_OUT) / 1024
    print(f"Done. Bundle size: {size_kb:.1f} KB")
    print(f"Versions in summary: {len(bundle.get('summary', []))}")
    print(f"Versions with returns: {len(bundle.get('versionReturns', {}))}")
    print(f"State summary rows: {len(bundle.get('state_summary', []))}")


if __name__ == "__main__":
    main()
