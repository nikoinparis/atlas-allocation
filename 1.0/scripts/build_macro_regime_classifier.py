"""
Build Full FRED-MD Macro Regime Classifier.

Research artifact sprint. No production artifacts are modified, no strategy
is promoted. Outputs written to outputs/experiment_results/macro_regime_classifier/.

Design:
  - 14 FRED series fetched via public CSV endpoint (no API key required)
  - Monthly panel with YoY transforms for activity series
  - Expanding-window PCA, quarterly refit, minimum 60 months history
  - PC1 = growth_factor (sign-anchored on INDPRO_yoy)
  - PC2 = inflation_financial_conditions_factor (sign-anchored on NFCI)
  - Four quadrants: expansion / overheating / slowdown / stress
  - Causal lagging: monthly factors aligned to weekly via merge_asof + 1-week shift
  - Development window: through 2024-04-12; holdout: last 104 weeks (2024-04-19+)
"""

from __future__ import annotations

import json
import warnings as _wlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

_wlib.filterwarnings("ignore", category=RuntimeWarning)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_HUB = PROJECT_ROOT / "data" / "01_data_hub"
MARKET_STATE_PATH = (
    PROJECT_ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
)
PORTFOLIO_PATH = (
    PROJECT_ROOT
    / "data"
    / "05_layer3_portfolio_construction"
    / "portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv"
)
OUT_DIR = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
HOLDOUT_START = pd.Timestamp("2024-04-19")
DEV_END = pd.Timestamp("2024-04-12")
MIN_MONTHS = 60

# Raw FRED series to fetch
FRED_SERIES_IDS = [
    "T10Y2Y",       # 2s10s yield curve spread (daily)
    "BAMLH0A0HYM2", # HY OAS credit spread (daily)
    "NFCI",         # Chicago Fed NFCI (weekly — financial conditions, higher=tighter)
    "DGS3MO",       # 3-month Treasury yield (daily)
    "UMCSENT",      # U Michigan consumer sentiment (monthly)
    "FEDFUNDS",     # Fed funds effective rate (monthly)
    "DTWEXBGS",     # Dollar index broad goods (daily)
    "UNRATE",       # Unemployment rate (monthly)
    "CPIAUCSL",     # CPI all urban (monthly)
    "INDPRO",       # Industrial production index (monthly)
    "PAYEMS",       # Nonfarm payrolls (monthly)
    "RSAFS",        # Retail sales (monthly)
    "HOUST",        # Housing starts (monthly)
    "ICSA",         # Initial jobless claims (weekly)
]

# Series where YoY % change is more informative than level
YOY_SERIES = {"CPIAUCSL", "INDPRO", "PAYEMS", "RSAFS", "HOUST"}

# Sign anchors: which feature should have a positive loading on each PC
PC1_ANCHOR = "INDPRO_yoy"   # positive = above-trend growth
PC2_ANCHOR = "NFCI"         # positive = tight financial conditions


# ── FRED data fetch ────────────────────────────────────────────────────────────

def fetch_fred_csv(series_id: str, run_warnings: list) -> pd.Series:
    """Download FRED public CSV; return daily Series indexed by date."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        df = pd.read_csv(url)
    except Exception as exc:
        run_warnings.append(f"FETCH FAILED {series_id}: {exc}")
        return pd.Series(dtype=float, name=series_id)
    if df.empty:
        run_warnings.append(f"EMPTY {series_id}")
        return pd.Series(dtype=float, name=series_id)
    date_col, val_col = df.columns[0], df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col].replace(".", np.nan), errors="coerce")
    s = df.dropna(subset=[date_col]).set_index(date_col)[val_col]
    s.name = series_id
    return s


def build_monthly_feature_panel(run_warnings: list) -> pd.DataFrame:
    """
    Fetch all FRED series, resample to monthly end-of-month, compute YoY changes
    where appropriate, forward-fill up to 3 months. Return wide feature DataFrame.
    """
    print("  Fetching FRED series:")
    raw: dict[str, pd.Series] = {}
    for sid in FRED_SERIES_IDS:
        s = fetch_fred_csv(sid, run_warnings)
        if not s.empty:
            # Resample to monthly: last valid observation in each month
            monthly = s.resample("ME").last()
            raw[sid] = monthly
            print(f"    {sid:20s}: {len(monthly)} months, {monthly.first_valid_index().date()} – {monthly.index[-1].date()}")
        else:
            print(f"    {sid:20s}: FAILED")

    if not raw:
        raise RuntimeError("No FRED data could be fetched — check network access.")

    panel = pd.DataFrame(raw).sort_index()

    # Compute YoY % changes for activity series
    features: dict[str, pd.Series] = {}
    for col in panel.columns:
        if col in YOY_SERIES:
            yoy = panel[col].pct_change(12) * 100  # YoY %
            feat_name = f"{col}_yoy"
            features[feat_name] = yoy
            print(f"    Computed YoY for {col} → {feat_name}")
        else:
            features[col] = panel[col]

    feat_panel = pd.DataFrame(features).sort_index()
    feat_panel = feat_panel.ffill(limit=3)
    return feat_panel


# ── Expanding-window PCA ───────────────────────────────────────────────────────

def sign_adjust(pca: PCA, valid_cols: list, anchor: str, pc_idx: int) -> float:
    """Return +1 or -1 to enforce consistent sign on a PCA component."""
    if anchor not in valid_cols:
        return 1.0
    anchor_idx = valid_cols.index(anchor)
    loading = pca.components_[pc_idx, anchor_idx]
    return 1.0 if loading >= 0 else -1.0


def expanding_pca_monthly(panel: pd.DataFrame) -> pd.DataFrame:
    """
    For each monthly date from MIN_MONTHS onward, compute factor scores using
    an expanding-window PCA (quarterly refit). Returns a DataFrame with
    growth_factor and inflation_financial_conditions_factor columns.
    """
    dates = panel.index
    records = []

    current_pca: PCA | None = None
    current_valid_cols: list = []
    pc1_sign = 1.0
    pc2_sign = 1.0

    # Expanding z-score state: track running sum and sum-of-squares
    # We'll recompute expanding mean/std from the window each step (fast enough at monthly)

    for i in range(MIN_MONTHS, len(dates)):
        date = dates[i]
        # Expanding window through current month (inclusive)
        window = panel.iloc[: i + 1]

        # Only use series with enough non-null observations
        valid_cols = [
            c for c in window.columns
            if window[c].notna().sum() >= MIN_MONTHS
        ]
        if len(valid_cols) < 2:
            continue

        sub = window[valid_cols].copy()

        # Refit PCA if: first fit, start of quarter, or available columns changed
        start_of_quarter = date.month in (1, 4, 7, 10)
        cols_changed = set(valid_cols) != set(current_valid_cols)

        if current_pca is None or start_of_quarter or cols_changed:
            # Fit on complete-case rows in the expanding window
            sub_complete = sub.dropna()
            if len(sub_complete) < MIN_MONTHS:
                continue
            X_fit = sub_complete.values
            # Center and scale before PCA
            col_mean = X_fit.mean(axis=0)
            col_std = X_fit.std(axis=0, ddof=1)
            col_std = np.where(col_std < 1e-8, 1e-8, col_std)
            X_std = (X_fit - col_mean) / col_std
            pca = PCA(n_components=2, random_state=42)
            pca.fit(X_std)

            pc1_sign = sign_adjust(pca, valid_cols, PC1_ANCHOR, 0)
            pc2_sign = sign_adjust(pca, valid_cols, PC2_ANCHOR, 1)

            current_pca = pca
            current_valid_cols = valid_cols
            # Store expanding stats at refit time for re-use within quarter
            _refit_mean = col_mean
            _refit_std = col_std

        # Score the current row using expanding z-scores up to date i
        row = panel.loc[date, current_valid_cols]
        if row.isna().any():
            # Fall back to most-recent complete row
            last_complete = sub[current_valid_cols].dropna().iloc[-1] if not sub[current_valid_cols].dropna().empty else None
            if last_complete is None:
                continue
            row = last_complete

        # Expanding mean/std up to current row
        exp_data = panel.iloc[: i + 1][current_valid_cols].dropna()
        exp_mean = exp_data.mean().values
        exp_std = exp_data.std(ddof=1).values
        exp_std = np.where(exp_std < 1e-8, 1e-8, exp_std)

        row_z = (row.values - exp_mean) / exp_std
        factors = current_pca.transform(row_z.reshape(1, -1))[0]

        records.append(
            {
                "date": date,
                "growth_factor": float(pc1_sign * factors[0]),
                "inflation_financial_conditions_factor": float(pc2_sign * factors[1]),
                "n_series": len(current_valid_cols),
                "window_months": i + 1,
                "pca_var_pc1": float(current_pca.explained_variance_ratio_[0]),
                "pca_var_pc2": float(current_pca.explained_variance_ratio_[1]),
            }
        )

    df = pd.DataFrame(records).set_index("date")
    return df


# ── Quadrant classification ────────────────────────────────────────────────────

def classify_quadrants(factors: pd.DataFrame) -> pd.DataFrame:
    """
    Assign macro quadrant based on sign of both factors.
      expansion   : growth > 0, conditions loose (PC2 < 0)
      overheating : growth > 0, conditions tight (PC2 > 0)
      slowdown    : growth < 0, conditions loose (PC2 < 0)
      stress      : growth < 0, conditions tight (PC2 > 0)
    """
    df = factors.copy()
    g = df["growth_factor"] > 0
    i = df["inflation_financial_conditions_factor"] > 0
    df["macro_quadrant"] = "unknown"
    df.loc[g & ~i, "macro_quadrant"] = "expansion"
    df.loc[g & i, "macro_quadrant"] = "overheating"
    df.loc[~g & ~i, "macro_quadrant"] = "slowdown"
    df.loc[~g & i, "macro_quadrant"] = "stress"
    return df


# ── Weekly alignment (causal) ──────────────────────────────────────────────────

def align_to_weekly(monthly_factors: pd.DataFrame, weekly_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Forward-fill monthly factors to weekly using merge_asof (backward),
    then shift 1 week to prevent any same-week leakage.
    """
    mf = monthly_factors.reset_index().rename(columns={"date": "date"})
    mf["date"] = pd.to_datetime(mf["date"])
    target = pd.DataFrame({"date": pd.to_datetime(weekly_dates)}).sort_values("date")

    merged = pd.merge_asof(target, mf.sort_values("date"), on="date", direction="backward")
    merged = merged.set_index("date").reindex(weekly_dates)

    # 1-week causal lag
    lagged = merged.shift(1)
    return lagged


# ── Forward return helpers ─────────────────────────────────────────────────────

def forward_spy_returns(spy_ret: pd.Series, weeks: int = 4) -> pd.Series:
    """Compute N-week forward log-cumulative return."""
    log_r = np.log1p(spy_ret.fillna(0.0))
    fwd_log = log_r.rolling(weeks).sum().shift(-weeks)
    return np.expm1(fwd_log)


# ── Validation helpers ─────────────────────────────────────────────────────────

def quad_stats(df: pd.DataFrame, quad_col: str, ret_col: str) -> pd.DataFrame:
    rows = []
    for quad in ["expansion", "overheating", "slowdown", "stress"]:
        sub = df[df[quad_col] == quad][ret_col].dropna()
        if len(sub) < 3:
            rows.append({"macro_quadrant": quad, "n": 0, "mean_4w_fwd_spy": np.nan, "std_4w_fwd_spy": np.nan, "sharpe_4w": np.nan})
            continue
        m, s = sub.mean(), sub.std()
        rows.append(
            {
                "macro_quadrant": quad,
                "n": len(sub),
                "mean_4w_fwd_spy": round(m, 5),
                "std_4w_fwd_spy": round(s, 5),
                "sharpe_4w": round(m / s, 3) if s > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    run_warnings: list[str] = []
    print("=" * 70)
    print("MACRO REGIME CLASSIFIER — RESEARCH SPRINT")
    print("=" * 70)

    # ── 1. Load project weekly dates and SPY returns ──────────────────────────
    print("\n[1] Loading project data...")
    port = pd.read_csv(PORTFOLIO_PATH, index_col=0, parse_dates=True)
    port.index = pd.to_datetime(port.index)
    weekly_dates = port.index

    prices = pd.read_csv(DATA_HUB / "weekly_prices.csv", index_col=0, parse_dates=True)
    prices.index = pd.to_datetime(prices.index)
    spy_ret = prices["SPY"].pct_change().reindex(weekly_dates) if "SPY" in prices.columns else pd.Series(dtype=float, index=weekly_dates)
    port_ret = port["net_return"]

    market_state_df = pd.read_csv(MARKET_STATE_PATH, index_col=0, parse_dates=True)
    market_state_df.index = pd.to_datetime(market_state_df.index)

    print(f"  Weekly dates: {weekly_dates[0].date()} → {weekly_dates[-1].date()} ({len(weekly_dates)} obs)")
    print(f"  State counts: {market_state_df['market_state'].value_counts().to_dict()}")

    # ── 2. Fetch FRED → monthly feature panel ────────────────────────────────
    print("\n[2] Fetching FRED macro data...")
    feat_panel = build_monthly_feature_panel(run_warnings)
    print(f"\n  Feature panel: {feat_panel.shape}, {feat_panel.index[0].date()} → {feat_panel.index[-1].date()}")
    print(f"  Non-null counts per feature:\n{feat_panel.notna().sum().to_string()}")

    # Save raw feature panel (macro_factor_space.csv)
    feat_panel.index.name = "date"
    feat_panel.to_csv(OUT_DIR / "macro_factor_space.csv")
    print(f"\n  Saved: macro_factor_space.csv")

    # ── 3. Expanding-window PCA → monthly factors ────────────────────────────
    print(f"\n[3] Expanding-window PCA (min {MIN_MONTHS} months, quarterly refit)...")
    monthly_factors = expanding_pca_monthly(feat_panel)
    monthly_factors = classify_quadrants(monthly_factors)
    print(f"  Monthly factor rows: {len(monthly_factors)}")
    print(f"  growth_factor      : [{monthly_factors['growth_factor'].min():.3f}, {monthly_factors['growth_factor'].max():.3f}]")
    print(f"  inflation_fc_factor: [{monthly_factors['inflation_financial_conditions_factor'].min():.3f}, {monthly_factors['inflation_financial_conditions_factor'].max():.3f}]")
    print(f"  Quadrant distribution (monthly):\n{monthly_factors['macro_quadrant'].value_counts().to_string()}")

    # ── 4. Align to weekly with 1-week causal lag ────────────────────────────
    print("\n[4] Aligning to weekly dates (merge_asof + 1-week lag)...")
    weekly_factors = align_to_weekly(monthly_factors, weekly_dates)
    n_covered = weekly_factors["macro_quadrant"].notna().sum()
    print(f"  Weekly rows with macro quadrant: {n_covered} / {len(weekly_dates)} ({n_covered/len(weekly_dates)*100:.1f}%)")

    # Attach market state and period labels
    weekly_factors["market_state"] = market_state_df["market_state"].reindex(weekly_dates)
    weekly_factors["period"] = "dev"
    weekly_factors.loc[weekly_factors.index >= HOLDOUT_START, "period"] = "holdout"

    # Compute 4-week forward SPY returns
    fwd_4w = forward_spy_returns(spy_ret, weeks=4)
    weekly_factors["fwd_4w_spy"] = fwd_4w

    # Save weekly quadrant assignments
    weekly_factors.index.name = "date"
    weekly_factors.to_csv(OUT_DIR / "macro_quadrants_weekly.csv")
    print(f"  Saved: macro_quadrants_weekly.csv")

    # ── 5. Quadrant counts ────────────────────────────────────────────────────
    quad_counts = (
        weekly_factors.groupby("macro_quadrant", observed=True)
        .size()
        .reset_index(name="count")
    )
    quad_counts["pct"] = (quad_counts["count"] / quad_counts["count"].sum() * 100).round(1)
    quad_counts.to_csv(OUT_DIR / "macro_quadrant_counts.csv", index=False)
    print(f"\n  Macro quadrant counts (weekly, full period):")
    print(quad_counts.to_string(index=False))

    # ── 6. Validation: 4-week forward SPY returns by quadrant ────────────────
    print("\n[5] 4-week forward SPY returns by macro quadrant...")
    val = weekly_factors.dropna(subset=["macro_quadrant", "fwd_4w_spy"])

    dev_stats = quad_stats(val[val["period"] == "dev"], "macro_quadrant", "fwd_4w_spy")
    dev_stats.insert(0, "period", "dev")
    hold_stats = quad_stats(val[val["period"] == "holdout"], "macro_quadrant", "fwd_4w_spy")
    hold_stats.insert(0, "period", "holdout")
    fwd_by_quad = pd.concat([dev_stats, hold_stats], ignore_index=True)

    print("\n  Dev period:")
    print(dev_stats.to_string(index=False))
    print("\n  Holdout period:")
    print(hold_stats.to_string(index=False))

    # ── 7. Neutral-mixed sub-split ────────────────────────────────────────────
    print("\n[6] Neutral-mixed sub-split analysis...")
    nm = val[val["market_state"] == "neutral_mixed"].copy()
    print(f"  neutral_mixed weeks total: {len(nm)}")
    print(f"  Macro quadrant distribution within neutral_mixed:")
    print(nm["macro_quadrant"].value_counts().to_string())

    nm_dev = quad_stats(nm[nm["period"] == "dev"], "macro_quadrant", "fwd_4w_spy")
    nm_dev.insert(0, "period", "dev")
    nm_hold = quad_stats(nm[nm["period"] == "holdout"], "macro_quadrant", "fwd_4w_spy")
    nm_hold.insert(0, "period", "holdout")
    nm_report = pd.concat([nm_dev, nm_hold], ignore_index=True)

    print("\n  neutral_mixed — dev period:")
    print(nm_dev.to_string(index=False))
    print("\n  neutral_mixed — holdout period:")
    print(nm_hold.to_string(index=False))

    nm_report.to_csv(OUT_DIR / "neutral_mixed_macro_split_report.csv", index=False)
    print(f"\n  Saved: neutral_mixed_macro_split_report.csv")

    # ── 8. Pass / Fail decision ───────────────────────────────────────────────
    print("\n[7] Pass / Fail decision...")
    dev_means = dev_stats.set_index("macro_quadrant")["mean_4w_fwd_spy"].dropna()
    dev_spread = float(dev_means.max() - dev_means.min()) if len(dev_means) >= 2 else 0.0

    nm_means = nm_dev.set_index("macro_quadrant")["mean_4w_fwd_spy"].dropna()
    nm_spread = float(nm_means.max() - nm_means.min()) if len(nm_means) >= 2 else 0.0

    # Holdout rank-order consistency: does the best dev quadrant stay best?
    hold_means = hold_stats.set_index("macro_quadrant")["mean_4w_fwd_spy"].dropna()
    best_dev = dev_means.idxmax() if len(dev_means) else None
    worst_dev = dev_means.idxmin() if len(dev_means) else None
    best_hold = hold_means.idxmax() if len(hold_means) else None
    worst_hold = hold_means.idxmin() if len(hold_means) else None
    rank_consistent = (best_dev == best_hold) or (worst_dev == worst_hold)

    crit_dev_spread = dev_spread > 0.010      # >1% 4-week return spread across quadrants
    crit_nm_spread = nm_spread > 0.005        # >0.5% spread within neutral_mixed
    crit_holdout = rank_consistent

    if crit_dev_spread and crit_nm_spread and crit_holdout:
        verdict = "PASS"
    elif crit_dev_spread or crit_nm_spread:
        verdict = "RESEARCH-ONLY"
    else:
        verdict = "DROP"

    verdict_lines = [
        f"Dev 4w SPY spread: {dev_spread:.4f} (threshold >0.01) — {'MET' if crit_dev_spread else 'NOT MET'}",
        f"Neutral-mixed spread: {nm_spread:.4f} (threshold >0.005) — {'MET' if crit_nm_spread else 'NOT MET'}",
        f"Holdout rank-consistent: {rank_consistent} — {'MET' if crit_holdout else 'NOT MET'}",
    ]

    print(f"\n  " + "\n  ".join(verdict_lines))
    print(f"\n  VERDICT: {verdict}")

    # ── 9. Save JSON summary ──────────────────────────────────────────────────
    summary = {
        "sprint": "macro_regime_classifier",
        "date": "2026-06-05",
        "verdict": verdict,
        "criteria": {
            "dev_4w_spread": round(dev_spread, 5),
            "dev_4w_spread_threshold": 0.01,
            "dev_4w_spread_met": bool(crit_dev_spread),
            "nm_spread": round(nm_spread, 5),
            "nm_spread_threshold": 0.005,
            "nm_spread_met": bool(crit_nm_spread),
            "holdout_rank_consistent": bool(rank_consistent),
            "holdout_rank_consistent_met": bool(crit_holdout),
        },
        "coverage": {
            "weekly_obs_total": int(len(weekly_dates)),
            "weekly_obs_with_quadrant": int(n_covered),
            "coverage_pct": round(float(n_covered) / len(weekly_dates) * 100, 1),
            "dev_end": DEV_END.strftime("%Y-%m-%d"),
            "holdout_start": HOLDOUT_START.strftime("%Y-%m-%d"),
        },
        "quadrant_distribution_weekly": {
            row["macro_quadrant"]: int(row["count"])
            for _, row in quad_counts.iterrows()
        },
        "dev_quadrant_fwd_returns": dev_stats.dropna(subset=["mean_4w_fwd_spy"]).set_index("macro_quadrant")[
            ["n", "mean_4w_fwd_spy", "std_4w_fwd_spy", "sharpe_4w"]
        ].to_dict(orient="index"),
        "holdout_quadrant_fwd_returns": hold_stats.dropna(subset=["mean_4w_fwd_spy"]).set_index("macro_quadrant")[
            ["n", "mean_4w_fwd_spy", "std_4w_fwd_spy", "sharpe_4w"]
        ].to_dict(orient="index"),
        "neutral_mixed_quadrant_distribution": nm["macro_quadrant"].value_counts().to_dict(),
        "neutral_mixed_dev_fwd_returns": nm_dev.dropna(subset=["mean_4w_fwd_spy"]).set_index("macro_quadrant")[
            ["n", "mean_4w_fwd_spy", "std_4w_fwd_spy", "sharpe_4w"]
        ].to_dict(orient="index"),
        "fred_features": list(feat_panel.columns),
        "warnings": run_warnings,
    }

    with open(OUT_DIR / "macro_regime_validation_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Saved: macro_regime_validation_summary.json")

    # ── 10. Write notes markdown ──────────────────────────────────────────────
    _write_notes(summary, verdict_lines, nm, nm_report, fwd_by_quad, run_warnings)
    print(f"  Saved: macro_regime_classifier_notes.md")

    # ── Done ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"SPRINT COMPLETE — VERDICT: {verdict}")
    print("=" * 70)
    if run_warnings:
        print(f"\nWarnings ({len(run_warnings)}):")
        for w in run_warnings:
            print(f"  ! {w}")


def _write_notes(
    summary: dict,
    verdict_lines: list,
    nm: pd.DataFrame,
    nm_report: pd.DataFrame,
    fwd_by_quad: pd.DataFrame,
    run_warnings: list,
) -> None:
    verdict = summary["verdict"]
    crit = summary["criteria"]

    lines = [
        "# Macro Regime Classifier — Research Sprint Notes",
        "",
        f"**Sprint date:** 2026-06-05  ",
        f"**Verdict:** `{verdict}`",
        "",
        "---",
        "",
        "## Design",
        "",
        "| Parameter | Value |",
        "| --- | --- |",
        f"| FRED series | {', '.join(summary['fred_features'])} |",
        f"| PCA window | Expanding, quarterly refit, min 60 months |",
        f"| PC1 | `growth_factor` (sign-anchored on INDPRO_yoy) |",
        f"| PC2 | `inflation_financial_conditions_factor` (sign-anchored on NFCI) |",
        f"| Quadrants | expansion / overheating / slowdown / stress |",
        f"| Lag | Monthly factors → weekly via merge_asof + 1-week shift |",
        f"| Development | through 2024-04-12 |",
        f"| Holdout | 2024-04-19 onward (last 104 weeks) |",
        "",
        "## Quadrant Classification",
        "",
        "| growth_factor | inflation_fc_factor | macro_quadrant |",
        "| --- | --- | --- |",
        "| > 0 | < 0 | expansion (Goldilocks: growth up, conditions loose) |",
        "| > 0 | > 0 | overheating (growth up, conditions tighten) |",
        "| < 0 | < 0 | slowdown (growth down, conditions loose) |",
        "| < 0 | > 0 | stress (growth down, conditions tight) |",
        "",
        "## Coverage",
        "",
        f"- Total weekly observations: {summary['coverage']['weekly_obs_total']}",
        f"- Weeks with macro quadrant assigned: {summary['coverage']['weekly_obs_with_quadrant']} ({summary['coverage']['coverage_pct']}%)",
        "",
        "### Weekly quadrant distribution",
        "",
        "| Quadrant | Count |",
        "| --- | --- |",
    ]
    for q, n in summary["quadrant_distribution_weekly"].items():
        lines.append(f"| {q} | {n} |")

    lines += [
        "",
        "## 4-Week Forward SPY Returns by Quadrant",
        "",
        "### Development period",
        "",
        "| Quadrant | N | Mean 4w | Std 4w | Sharpe |",
        "| --- | --- | --- | --- | --- |",
    ]
    dev_rows = fwd_by_quad[fwd_by_quad["period"] == "dev"]
    for _, r in dev_rows.iterrows():
        lines.append(f"| {r['macro_quadrant']} | {int(r.get('n', 0))} | {r.get('mean_4w_fwd_spy', 'N/A')} | {r.get('std_4w_fwd_spy', 'N/A')} | {r.get('sharpe_4w', 'N/A')} |")

    lines += [
        "",
        "### Holdout period",
        "",
        "| Quadrant | N | Mean 4w | Std 4w | Sharpe |",
        "| --- | --- | --- | --- | --- |",
    ]
    hold_rows = fwd_by_quad[fwd_by_quad["period"] == "holdout"]
    for _, r in hold_rows.iterrows():
        lines.append(f"| {r['macro_quadrant']} | {int(r.get('n', 0))} | {r.get('mean_4w_fwd_spy', 'N/A')} | {r.get('std_4w_fwd_spy', 'N/A')} | {r.get('sharpe_4w', 'N/A')} |")

    lines += [
        "",
        "## Neutral-Mixed Sub-Split",
        "",
        f"neutral_mixed total weeks: {len(nm)}",
        "",
        "### Macro quadrant distribution within neutral_mixed",
        "",
        "| Quadrant | Count |",
        "| --- | --- |",
    ]
    for q, n in summary["neutral_mixed_quadrant_distribution"].items():
        lines.append(f"| {q} | {n} |")

    lines += [
        "",
        "### 4-week forward SPY within neutral_mixed (dev period)",
        "",
        "| Quadrant | N | Mean 4w | Std 4w | Sharpe |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, r in nm_report[nm_report["period"] == "dev"].iterrows():
        lines.append(f"| {r['macro_quadrant']} | {int(r.get('n', 0))} | {r.get('mean_4w_fwd_spy', 'N/A')} | {r.get('std_4w_fwd_spy', 'N/A')} | {r.get('sharpe_4w', 'N/A')} |")

    lines += [
        "",
        "## Pass / Fail Criteria",
        "",
        "| Criterion | Threshold | Result | Met? |",
        "| --- | --- | --- | --- |",
        f"| Dev 4w SPY spread | > 1.0% (0.01) | {crit['dev_4w_spread']:.4f} | {'YES' if crit['dev_4w_spread_met'] else 'NO'} |",
        f"| Neutral-mixed spread | > 0.5% (0.005) | {crit['nm_spread']:.4f} | {'YES' if crit['nm_spread_met'] else 'NO'} |",
        f"| Holdout rank-consistent | Best/worst quad match | {crit['holdout_rank_consistent']} | {'YES' if crit['holdout_rank_consistent_met'] else 'NO'} |",
        "",
        f"## Verdict: `{verdict}`",
        "",
    ]
    for vl in verdict_lines:
        lines.append(f"- {vl}")

    lines += [
        "",
        "## Implications and Next Steps",
        "",
    ]
    if verdict == "PASS":
        lines += [
            "The macro quadrant classifier shows meaningful predictive power for SPY returns",
            "both in development and holdout. Recommended next steps:",
            "",
            "1. Implement as a conditional allocation modifier in a separate sprint (do not merge into production without Phase D gate evaluation).",
            "2. Map quadrants to neutral_mixed sub-regimes and test whether `expansion` weeks should receive higher equity offense allocation.",
            "3. Evaluate whether this classifier helps more than the existing 5-state market regime engine or is additive.",
        ]
    elif verdict == "RESEARCH-ONLY":
        lines += [
            "The macro quadrant classifier shows a weak but non-zero signal. Not strong enough",
            "for immediate promotion. Recommended next steps:",
            "",
            "1. Investigate whether combining macro quadrant with existing market states improves signal quality.",
            "2. Consider alternative PCA feature sets or additional transformations.",
            "3. Do NOT integrate into production allocation without clearing all 8 Phase D gates.",
        ]
    else:
        lines += [
            "No meaningful predictive signal detected. This branch is closed.",
            "Do not invest further sprint effort in FRED-MD PCA macro quadrants without a new hypothesis.",
        ]

    lines += [
        "",
        "## Warnings",
        "",
    ]
    for w in (run_warnings if run_warnings else ["None"]):
        lines.append(f"- {w}")

    lines += [
        "",
        "---",
        "*Research artifact sprint — no production artifacts modified.*",
    ]

    with open(OUT_DIR / "macro_regime_classifier_notes.md", "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
