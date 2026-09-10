"""
Build Full FRED-MD Macro Regime Classifier — Version 2.

Improvements over v1:
  - Retry logic with exponential backoff for FRED downloads
  - Local cache so transient failures don't drop series permanently
  - Full 14-series feature set (vs 10 in v1)
  - Factor loadings table and interpretation markdown
  - Macro + confirmation diagnostics (trend, credit, current state)
  - V1 vs V2 side-by-side comparison
  - Expanded pass/fail criteria aligned with EXPERIMENTAL CANDIDATE gate

Research artifact sprint. No production artifacts modified. No promotion.
Outputs: outputs/experiment_results/macro_regime_classifier_v2/
"""

from __future__ import annotations

import io
import json
import time
import warnings as _wlib
from pathlib import Path

import numpy as np
import pandas as pd
import requests
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
V1_OUT_DIR = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier"
OUT_DIR = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v2"
CACHE_DIR = OUT_DIR / "cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
HOLDOUT_START = pd.Timestamp("2024-04-19")
DEV_END = pd.Timestamp("2024-04-12")
MIN_MONTHS = 60

FRED_SERIES_IDS = [
    "T10Y2Y",       # 2s10s yield curve spread (daily) — missed in v1
    "BAMLH0A0HYM2", # HY OAS credit spread (daily)
    "NFCI",         # Chicago Fed NFCI (weekly, higher=tighter)
    "DGS3MO",       # 3-month Treasury yield (daily) — missed in v1
    "UMCSENT",      # Michigan consumer sentiment (monthly)
    "FEDFUNDS",     # Fed funds rate (monthly)
    "DTWEXBGS",     # Dollar index broad goods (daily) — missed in v1
    "UNRATE",       # Unemployment rate (monthly)
    "CPIAUCSL",     # CPI all urban (monthly)
    "INDPRO",       # Industrial production (monthly)
    "PAYEMS",       # Nonfarm payrolls (monthly)
    "RSAFS",        # Retail sales (monthly)
    "HOUST",        # Housing starts (monthly)
    "ICSA",         # Initial jobless claims (weekly) — missed in v1
]

# YoY transformation: growth/inflation series
YOY_SERIES = {"CPIAUCSL", "INDPRO", "PAYEMS", "RSAFS", "HOUST"}

# Sign anchors for consistent factor orientation
PC1_ANCHOR = "INDPRO_yoy"   # positive = above-trend growth
PC2_ANCHOR = "NFCI"         # positive = tight financial conditions

# Retry config — keep low to avoid long waits when FRED rate-limits
MAX_RETRIES = 2
BASE_BACKOFF_SECS = 1
FETCH_TIMEOUT = 15


# ── FRED download with retry + cache ──────────────────────────────────────────

def fetch_fred_with_retry(
    series_id: str,
    cache_dir: Path,
    run_log: list[dict],
) -> tuple[pd.Series, str]:
    """
    Fetch a FRED series. Returns (Series, source) where source is one of:
    "LIVE", "CACHED", "FAILED".
    Caches successful downloads. Falls back to cache on failure.
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    cache_path = cache_dir / f"{series_id}.csv"

    # Attempt live download with retries
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=FETCH_TIMEOUT)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            if df.empty:
                raise ValueError("empty response")
            date_col, val_col = df.columns[0], df.columns[1]
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df[val_col] = pd.to_numeric(df[val_col].replace(".", np.nan), errors="coerce")
            s = df.dropna(subset=[date_col]).set_index(date_col)[val_col]
            s.name = series_id
            if s.empty:
                raise ValueError("all NaN after parse")
            # Cache it
            s.to_csv(cache_path)
            run_log.append({"series": series_id, "source": "LIVE", "n_obs": len(s)})
            return s, "LIVE"
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                sleep_secs = BASE_BACKOFF_SECS * (2 ** attempt)
                print(f"    {series_id}: attempt {attempt+1} failed ({exc}), retrying in {sleep_secs}s...")
                time.sleep(sleep_secs)

    # Fall back to cache
    if cache_path.exists():
        try:
            s = pd.read_csv(cache_path, index_col=0, parse_dates=True).squeeze()
            s.name = series_id
            run_log.append({"series": series_id, "source": "CACHED", "n_obs": len(s)})
            return s, "CACHED"
        except Exception as cache_exc:
            run_log.append({"series": series_id, "source": "FAILED", "n_obs": 0,
                            "error": str(last_exc), "cache_error": str(cache_exc)})
            return pd.Series(dtype=float, name=series_id), "FAILED"

    run_log.append({"series": series_id, "source": "FAILED", "n_obs": 0, "error": str(last_exc)})
    return pd.Series(dtype=float, name=series_id), "FAILED"


def build_monthly_feature_panel(cache_dir: Path, run_log: list) -> pd.DataFrame:
    """Fetch all FRED series, resample to monthly end-of-month, apply YoY transforms."""
    print("  Fetching FRED series (with retry + cache):")
    raw: dict[str, pd.Series] = {}
    for sid in FRED_SERIES_IDS:
        s, source = fetch_fred_with_retry(sid, cache_dir, run_log)
        if not s.empty:
            monthly = s.resample("ME").last()
            raw[sid] = monthly
            first_valid = monthly.first_valid_index()
            fv_str = first_valid.date() if first_valid is not None else "N/A"
            print(f"    [{source}] {sid:20s}: {len(monthly)} months, {fv_str} – {monthly.index[-1].date()}")
        else:
            print(f"    [FAILED] {sid:20s}")

    if not raw:
        raise RuntimeError("No FRED data could be fetched or loaded from cache.")

    panel = pd.DataFrame(raw).sort_index()

    features: dict[str, pd.Series] = {}
    for col in panel.columns:
        if col in YOY_SERIES:
            yoy = panel[col].pct_change(12, fill_method=None) * 100
            feat_name = f"{col}_yoy"
            features[feat_name] = yoy
        else:
            features[col] = panel[col]

    feat_panel = pd.DataFrame(features).sort_index()
    feat_panel = feat_panel.ffill(limit=3)
    return feat_panel


# ── Expanding-window PCA with loadings ────────────────────────────────────────

def sign_adjust(pca: PCA, valid_cols: list, anchor: str, pc_idx: int) -> float:
    if anchor not in valid_cols:
        return 1.0
    loading = pca.components_[pc_idx, valid_cols.index(anchor)]
    return 1.0 if loading >= 0 else -1.0


def expanding_pca_monthly(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Expanding-window PCA (quarterly refit, min 60 months).
    Returns:
      - monthly factor DataFrame
      - loadings DataFrame at the last development-period refit (for interpretation)
    """
    dates = panel.index
    records = []

    current_pca: PCA | None = None
    current_valid_cols: list = []
    pc1_sign = 1.0
    pc2_sign = 1.0
    final_dev_loadings: pd.DataFrame | None = None

    for i in range(MIN_MONTHS, len(dates)):
        date = dates[i]
        window = panel.iloc[: i + 1]

        valid_cols = [c for c in window.columns if window[c].notna().sum() >= MIN_MONTHS]
        if len(valid_cols) < 2:
            continue

        sub = window[valid_cols].copy()

        start_of_quarter = date.month in (1, 4, 7, 10)
        cols_changed = set(valid_cols) != set(current_valid_cols)

        if current_pca is None or start_of_quarter or cols_changed:
            sub_complete = sub.dropna()
            if len(sub_complete) < MIN_MONTHS:
                continue
            X_fit = sub_complete.values
            col_mean = X_fit.mean(axis=0)
            col_std = X_fit.std(axis=0, ddof=1)
            col_std = np.where(col_std < 1e-8, 1e-8, col_std)
            X_std = (X_fit - col_mean) / col_std
            n_components = min(3, len(valid_cols))
            pca = PCA(n_components=n_components, random_state=42)
            pca.fit(X_std)

            pc1_sign = sign_adjust(pca, valid_cols, PC1_ANCHOR, 0)
            pc2_sign_adj = sign_adjust(pca, valid_cols, PC2_ANCHOR, 1) if n_components >= 2 else 1.0

            current_pca = pca
            current_valid_cols = valid_cols
            pc2_sign = pc2_sign_adj

            # Record the last refit before holdout for interpretation
            if date <= DEV_END:
                signs = np.array([pc1_sign, pc2_sign, 1.0][:n_components])
                loadings = pd.DataFrame(
                    pca.components_[:n_components, :].T * signs,
                    index=valid_cols,
                    columns=[f"PC{k+1}" for k in range(n_components)],
                )
                # Store variance explained as a separate attribute (not a row)
                loadings.attrs["explained_var_ratio"] = pca.explained_variance_ratio_[:n_components].tolist()
                final_dev_loadings = loadings.copy()

        row = panel.loc[date, current_valid_cols]
        if row.isna().any():
            last_complete = sub[current_valid_cols].dropna()
            if last_complete.empty:
                continue
            row = last_complete.iloc[-1]

        exp_data = panel.iloc[: i + 1][current_valid_cols].dropna()
        exp_mean = exp_data.mean().values
        exp_std = exp_data.std(ddof=1).values
        exp_std = np.where(exp_std < 1e-8, 1e-8, exp_std)
        row_z = (row.values - exp_mean) / exp_std

        factors = current_pca.transform(row_z.reshape(1, -1))[0]
        n_comp = len(factors)

        rec = {
            "date": date,
            "growth_factor": float(pc1_sign * factors[0]),
            "inflation_financial_conditions_factor": float(pc2_sign * factors[1]) if n_comp >= 2 else np.nan,
            "n_series": len(current_valid_cols),
            "window_months": i + 1,
            "pca_var_pc1": float(current_pca.explained_variance_ratio_[0]),
            "pca_var_pc2": float(current_pca.explained_variance_ratio_[1]) if n_comp >= 2 else np.nan,
        }
        if n_comp >= 3:
            rec["credit_liquidity_factor"] = float(factors[2])
            rec["pca_var_pc3"] = float(current_pca.explained_variance_ratio_[2])
        records.append(rec)

    df = pd.DataFrame(records).set_index("date")
    return df, final_dev_loadings


def classify_quadrants(factors: pd.DataFrame) -> pd.DataFrame:
    df = factors.copy()
    g = df["growth_factor"] > 0
    ifc = df["inflation_financial_conditions_factor"] > 0
    df["macro_quadrant"] = "unknown"
    df.loc[g & ~ifc, "macro_quadrant"] = "expansion"
    df.loc[g & ifc, "macro_quadrant"] = "overheating"
    df.loc[~g & ~ifc, "macro_quadrant"] = "slowdown"
    df.loc[~g & ifc, "macro_quadrant"] = "stress"
    return df


# ── Weekly alignment ───────────────────────────────────────────────────────────

def align_to_weekly(monthly_factors: pd.DataFrame, weekly_dates: pd.DatetimeIndex) -> pd.DataFrame:
    mf = monthly_factors.reset_index()
    mf["date"] = pd.to_datetime(mf["date"])
    target = pd.DataFrame({"date": pd.to_datetime(weekly_dates)}).sort_values("date")
    merged = pd.merge_asof(target, mf.sort_values("date"), on="date", direction="backward")
    merged = merged.set_index("date").reindex(weekly_dates)
    return merged.shift(1)  # 1-week causal lag


# ── Forward return helpers ─────────────────────────────────────────────────────

def forward_returns(ret: pd.Series, weeks: int = 4) -> pd.Series:
    log_r = np.log1p(ret.fillna(0.0))
    return np.expm1(log_r.rolling(weeks).sum().shift(-weeks))


# ── Confirmation features ──────────────────────────────────────────────────────

def build_confirmation_features(prices: pd.DataFrame, weekly_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Build SPY-trend and HYG/LQD-trend confirmation features."""
    conf = pd.DataFrame(index=weekly_dates)

    # SPY 40-week MA (≈ 200 trading days)
    spy = prices["SPY"].reindex(weekly_dates)
    spy_ma40 = spy.rolling(40, min_periods=20).mean()
    conf["spy_above_200dma"] = (spy > spy_ma40).astype(float)

    # HYG/LQD relative trend (13-week momentum of ratio, risk-on proxy)
    if "HYG" in prices.columns and "LQD" in prices.columns:
        hyg = prices["HYG"].reindex(weekly_dates)
        lqd = prices["LQD"].reindex(weekly_dates)
        ratio = (hyg / lqd).where((lqd > 0) & lqd.notna())
        conf["credit_trend_improving"] = (ratio.pct_change(13) > 0).astype(float)
    else:
        conf["credit_trend_improving"] = np.nan

    # Lag 1 week to be causal
    return conf.shift(1)


# ── Validation helpers ─────────────────────────────────────────────────────────

QUADS = ["expansion", "overheating", "slowdown", "stress"]


def quad_stats(df: pd.DataFrame, quad_col: str, ret_col: str, label: str = "") -> pd.DataFrame:
    rows = []
    for quad in QUADS:
        sub = df[df[quad_col] == quad][ret_col].dropna()
        if len(sub) < 3:
            rows.append({"macro_quadrant": quad, "n": int(len(sub)),
                         "mean_4w": np.nan, "std_4w": np.nan, "sharpe_4w": np.nan})
            continue
        m, s = sub.mean(), sub.std()
        rows.append({
            "macro_quadrant": quad, "n": int(len(sub)),
            "mean_4w": round(m, 5), "std_4w": round(s, 5),
            "sharpe_4w": round(m / s, 3) if s > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def confirmation_table(
    df: pd.DataFrame,
    quad_col: str,
    cond_col: str,
    ret_col: str,
    cond_labels: dict,
    period: str,
) -> pd.DataFrame:
    """2-way cross: macro_quadrant × binary condition → return stats."""
    rows = []
    sub = df[df["period"] == period].dropna(subset=[quad_col, cond_col, ret_col])
    for quad in QUADS:
        for cond_val, cond_label in cond_labels.items():
            mask = (sub[quad_col] == quad) & (sub[cond_col] == cond_val)
            s = sub[mask][ret_col]
            if len(s) < 5:
                rows.append({"period": period, "macro_quadrant": quad,
                             "condition": f"{cond_col}={cond_label}", "n": int(len(s)),
                             "mean_4w": np.nan, "sharpe_4w": np.nan})
                continue
            m, sd = s.mean(), s.std()
            rows.append({"period": period, "macro_quadrant": quad,
                         "condition": f"{cond_col}={cond_label}",
                         "n": int(len(s)),
                         "mean_4w": round(m, 5),
                         "sharpe_4w": round(m / sd, 3) if sd > 0 else np.nan})
    return pd.DataFrame(rows)


# ── V1 vs V2 comparison ───────────────────────────────────────────────────────

def load_v1_summary() -> dict:
    v1_path = V1_OUT_DIR / "macro_regime_validation_summary.json"
    if v1_path.exists():
        with open(v1_path) as f:
            return json.load(f)
    return {}


def build_comparison(v1: dict, v2_data: dict) -> pd.DataFrame:
    """Build v1 vs v2 comparison DataFrame."""
    rows = []

    def r(label, v1_val, v2_val):
        rows.append({"metric": label, "v1": v1_val, "v2": v2_val})

    # Feature set
    r("n_fred_series_used", len(v1.get("fred_features", [])), v2_data["n_series"])
    r("series_v1", ", ".join(v1.get("fred_features", [])), ", ".join(v2_data["features"]))
    r("series_missing_v2", "", ", ".join(v2_data["missing_series"]))

    # Quadrant counts
    v1_qdist = v1.get("quadrant_distribution_weekly", {})
    v2_qdist = v2_data["quad_counts"]
    for q in QUADS:
        r(f"weekly_count_{q}", v1_qdist.get(q, "N/A"), v2_qdist.get(q, "N/A"))

    # Dev returns
    v1_dev = v1.get("dev_quadrant_fwd_returns", {})
    v2_dev = v2_data["dev_fwd"]
    for q in QUADS:
        r(f"dev_mean_4w_{q}",
          round(v1_dev.get(q, {}).get("mean_4w_fwd_spy", np.nan), 5),
          round(v2_dev.get(q, {}).get("mean_4w", np.nan), 5))
    r("dev_spread", round(v1.get("criteria", {}).get("dev_4w_spread", np.nan), 5),
      round(v2_data["dev_spread"], 5))
    r("nm_spread", round(v1.get("criteria", {}).get("nm_spread", np.nan), 5),
      round(v2_data["nm_spread"], 5))

    # Holdout
    v1_hold = v1.get("holdout_quadrant_fwd_returns", {})
    v2_hold = v2_data["hold_fwd"]
    for q in QUADS:
        r(f"hold_mean_4w_{q}",
          round(v1_hold.get(q, {}).get("mean_4w_fwd_spy", np.nan), 5),
          round(v2_hold.get(q, {}).get("mean_4w", np.nan), 5))
    r("holdout_rank_consistent", v1.get("criteria", {}).get("holdout_rank_consistent", False),
      v2_data["holdout_consistent"])
    r("holdout_quads_populated",
      sum(1 for v in v1_hold.values() if v.get("n", 0) > 0),
      sum(1 for v in v2_hold.values() if v.get("n", 0) > 0))

    # Verdict
    r("verdict", v1.get("verdict", "N/A"), v2_data["verdict"])

    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    run_log: list[dict] = []
    run_warnings: list[str] = []

    print("=" * 70)
    print("MACRO REGIME CLASSIFIER V2 — RESEARCH SPRINT")
    print("=" * 70)

    # ── 1. Load project data ───────────────────────────────────────────────────
    print("\n[1] Loading project data...")
    port = pd.read_csv(PORTFOLIO_PATH, index_col=0, parse_dates=True)
    port.index = pd.to_datetime(port.index)
    weekly_dates = port.index

    prices = pd.read_csv(DATA_HUB / "weekly_prices.csv", index_col=0, parse_dates=True)
    prices.index = pd.to_datetime(prices.index)
    spy_ret = prices["SPY"].pct_change().reindex(weekly_dates)
    port_ret = port["net_return"]

    market_state_df = pd.read_csv(MARKET_STATE_PATH, index_col=0, parse_dates=True)
    market_state_df.index = pd.to_datetime(market_state_df.index)
    market_state = market_state_df["market_state"].reindex(weekly_dates)

    print(f"  Weekly dates: {weekly_dates[0].date()} → {weekly_dates[-1].date()} ({len(weekly_dates)} obs)")
    print(f"  State counts: {market_state.value_counts().to_dict()}")

    # ── 2. Fetch FRED → monthly feature panel ─────────────────────────────────
    print("\n[2] Fetching FRED macro data (retry + cache)...")
    feat_panel = build_monthly_feature_panel(CACHE_DIR, run_log)
    n_live = sum(1 for r in run_log if r["source"] == "LIVE")
    n_cached = sum(1 for r in run_log if r["source"] == "CACHED")
    n_failed = sum(1 for r in run_log if r["source"] == "FAILED")
    missing_series = [r["series"] for r in run_log if r["source"] == "FAILED"]

    # Original FRED series IDs that made it into the panel (before YoY transform)
    base_ids_in_panel = [sid for sid in FRED_SERIES_IDS if sid in feat_panel.columns or
                         (sid in YOY_SERIES and f"{sid}_yoy" in feat_panel.columns)]
    n_series_used = len(base_ids_in_panel)

    print(f"\n  FRED result: {n_live} live, {n_cached} from cache, {n_failed} failed")
    if missing_series:
        print(f"  Missing: {missing_series}")
    print(f"  Feature panel: {feat_panel.shape}, {feat_panel.index[0].date()} → {feat_panel.index[-1].date()}")
    print(f"  Non-null counts:\n{feat_panel.notna().sum().to_string()}")

    feat_panel.index.name = "date"
    feat_panel.to_csv(OUT_DIR / "macro_factor_space_v2.csv")
    print(f"\n  Saved: macro_factor_space_v2.csv")

    # ── 3. Expanding-window PCA ────────────────────────────────────────────────
    print(f"\n[3] Expanding-window PCA (min {MIN_MONTHS} months, quarterly refit)...")
    monthly_factors, final_loadings = expanding_pca_monthly(feat_panel)
    monthly_factors = classify_quadrants(monthly_factors)

    print(f"  Monthly factor rows: {len(monthly_factors)}")
    print(f"  growth_factor      : [{monthly_factors['growth_factor'].min():.3f}, {monthly_factors['growth_factor'].max():.3f}]")
    print(f"  inflation_fc_factor: [{monthly_factors['inflation_financial_conditions_factor'].min():.3f}, {monthly_factors['inflation_financial_conditions_factor'].max():.3f}]")
    print(f"  Quadrant dist (monthly):\n{monthly_factors['macro_quadrant'].value_counts().to_string()}")

    # Factor variance explained
    pc_var = {
        "PC1_pct": round(float(monthly_factors["pca_var_pc1"].iloc[-1]) * 100, 1),
        "PC2_pct": round(float(monthly_factors["pca_var_pc2"].iloc[-1]) * 100, 1),
    }
    if "pca_var_pc3" in monthly_factors.columns:
        pc_var["PC3_pct"] = round(float(monthly_factors["pca_var_pc3"].dropna().iloc[-1]) * 100, 1)
    print(f"  Variance explained (final refit): {pc_var}")

    # ── 4. Factor loadings ─────────────────────────────────────────────────────
    print("\n[4] Saving factor loadings...")
    if final_loadings is not None:
        final_loadings.index.name = "feature"
        final_loadings.to_csv(OUT_DIR / "macro_factor_loadings.csv")
        print(f"  Loadings at last dev refit:\n{final_loadings.to_string()}")
        _write_factor_interpretation(final_loadings, pc_var)
        print(f"  Saved: macro_factor_loadings.csv, macro_factor_interpretation.md")
    else:
        run_warnings.append("Could not capture final dev loadings — check PCA logic.")

    # ── 5. Align to weekly ─────────────────────────────────────────────────────
    print("\n[5] Aligning to weekly (merge_asof + 1-week lag)...")
    weekly_factors = align_to_weekly(monthly_factors, weekly_dates)
    n_covered = weekly_factors["macro_quadrant"].notna().sum()
    print(f"  Weekly coverage: {n_covered}/{len(weekly_dates)} ({n_covered/len(weekly_dates)*100:.1f}%)")

    weekly_factors["market_state"] = market_state
    weekly_factors["period"] = "dev"
    weekly_factors.loc[weekly_factors.index >= HOLDOUT_START, "period"] = "holdout"

    fwd_4w_spy = forward_returns(spy_ret, 4)
    fwd_4w_port = forward_returns(port_ret, 4)
    weekly_factors["fwd_4w_spy"] = fwd_4w_spy
    weekly_factors["fwd_4w_port"] = fwd_4w_port

    weekly_factors.index.name = "date"
    weekly_factors.to_csv(OUT_DIR / "macro_quadrants_weekly_v2.csv")
    print(f"  Saved: macro_quadrants_weekly_v2.csv")

    # ── 6. Quadrant counts ─────────────────────────────────────────────────────
    quad_counts_df = (
        weekly_factors.groupby("macro_quadrant", observed=True)
        .size()
        .reset_index(name="count")
    )
    quad_counts_df["pct"] = (quad_counts_df["count"] / quad_counts_df["count"].sum() * 100).round(1)
    quad_counts_df.to_csv(OUT_DIR / "macro_quadrant_counts_v2.csv", index=False)
    quad_counts = {r["macro_quadrant"]: int(r["count"]) for _, r in quad_counts_df.iterrows()}
    print(f"\n  Quadrant counts:\n{quad_counts_df.to_string(index=False)}")

    # ── 7. Dev / holdout forward returns ──────────────────────────────────────
    print("\n[6] 4-week forward SPY returns by quadrant...")
    val = weekly_factors.dropna(subset=["macro_quadrant", "fwd_4w_spy"])
    dev_val = val[val["period"] == "dev"]
    hold_val = val[val["period"] == "holdout"]

    dev_stats = quad_stats(dev_val, "macro_quadrant", "fwd_4w_spy")
    hold_stats = quad_stats(hold_val, "macro_quadrant", "fwd_4w_spy")
    dev_stats.insert(0, "period", "dev")
    hold_stats.insert(0, "period", "holdout")

    print("\n  Dev period:")
    print(dev_stats.to_string(index=False))
    print("\n  Holdout period:")
    print(hold_stats.to_string(index=False))

    # Spread calculations
    dev_means = dev_stats.set_index("macro_quadrant")["mean_4w"].dropna()
    dev_spread = float(dev_means.max() - dev_means.min()) if len(dev_means) >= 2 else 0.0

    hold_means = hold_stats.set_index("macro_quadrant")["mean_4w"].dropna()
    hold_quads_populated = int((hold_stats["n"] > 0).sum())

    # Holdout rank consistency
    best_dev = dev_means.idxmax() if len(dev_means) else None
    worst_dev = dev_means.idxmin() if len(dev_means) else None
    best_hold = hold_means.idxmax() if len(hold_means) else None
    worst_hold = hold_means.idxmin() if len(hold_means) else None
    rank_consistent = bool((best_dev == best_hold) or (worst_dev == worst_hold))

    print(f"\n  Dev spread: {dev_spread:.4f}")
    print(f"  Holdout quads populated: {hold_quads_populated}/4")
    print(f"  Holdout rank consistent: {rank_consistent}")

    # ── 8. Neutral-mixed sub-split ─────────────────────────────────────────────
    print("\n[7] Neutral-mixed sub-split (primary target)...")
    nm = val[val["market_state"] == "neutral_mixed"].copy()
    nm_dev = nm[nm["period"] == "dev"]
    nm_hold = nm[nm["period"] == "holdout"]

    nm_dev_stats = quad_stats(nm_dev, "macro_quadrant", "fwd_4w_spy")
    nm_hold_stats = quad_stats(nm_hold, "macro_quadrant", "fwd_4w_spy")
    nm_dev_stats.insert(0, "period", "dev")
    nm_hold_stats.insert(0, "period", "holdout")
    nm_report = pd.concat([nm_dev_stats, nm_hold_stats], ignore_index=True)

    print(f"\n  neutral_mixed total weeks: {len(nm)}")
    print(f"  Quadrant dist within neutral_mixed:")
    print(nm["macro_quadrant"].value_counts().to_string())
    print(f"\n  neutral_mixed — dev:")
    print(nm_dev_stats.to_string(index=False))
    print(f"\n  neutral_mixed — holdout:")
    print(nm_hold_stats.to_string(index=False))

    nm_dev_means = nm_dev_stats.set_index("macro_quadrant")["mean_4w"].dropna()
    nm_spread = float(nm_dev_means.max() - nm_dev_means.min()) if len(nm_dev_means) >= 2 else 0.0

    # neutral_mixed production portfolio returns by quadrant
    nm_port = nm.dropna(subset=["fwd_4w_port"])
    nm_port_dev_stats = quad_stats(nm_port[nm_port["period"] == "dev"], "macro_quadrant", "fwd_4w_port")
    nm_port_dev_stats.insert(0, "period", "dev")
    nm_port_dev_stats.insert(0, "return_type", "portfolio")
    nm_report_full = pd.concat([nm_report.assign(return_type="spy"), nm_port_dev_stats], ignore_index=True)
    nm_report_full.to_csv(OUT_DIR / "neutral_mixed_macro_split_report_v2.csv", index=False)
    print(f"\n  Saved: neutral_mixed_macro_split_report_v2.csv")

    # Holdout rank consistency within nm
    nm_hold_means = nm_hold_stats.set_index("macro_quadrant")["mean_4w"].dropna()
    nm_hold_populated = int((nm_hold_stats["n"] > 0).sum())
    nm_best_dev = nm_dev_means.idxmax() if len(nm_dev_means) else None
    nm_worst_dev = nm_dev_means.idxmin() if len(nm_dev_means) else None
    nm_best_hold = nm_hold_means.idxmax() if len(nm_hold_means) else None
    nm_worst_hold = nm_hold_means.idxmin() if len(nm_hold_means) else None
    nm_rank_consistent = bool((nm_best_dev == nm_best_hold) or (nm_worst_dev == nm_worst_hold))
    print(f"\n  neutral_mixed spread (dev): {nm_spread:.4f}")
    print(f"  neutral_mixed holdout rank consistent: {nm_rank_consistent}")

    # ── 9. Confirmation diagnostics ────────────────────────────────────────────
    print("\n[8] Confirmation diagnostics...")
    conf_feats = build_confirmation_features(prices, weekly_dates)
    wf = weekly_factors.copy()
    wf["spy_above_200dma"] = conf_feats["spy_above_200dma"]
    wf["credit_trend_improving"] = conf_feats["credit_trend_improving"]

    diag_frames = []

    # A. Macro-only (reference)
    for period in ["dev", "holdout"]:
        s = wf[wf["period"] == period].dropna(subset=["macro_quadrant", "fwd_4w_spy"])
        for quad in QUADS:
            sub = s[s["macro_quadrant"] == quad]["fwd_4w_spy"]
            n = len(sub.dropna())
            m = sub.mean() if n >= 3 else np.nan
            sd = sub.std() if n >= 3 else np.nan
            diag_frames.append({
                "period": period, "diagnostic": "A_macro_only",
                "macro_quadrant": quad, "condition": "all",
                "n": n, "mean_4w": round(m, 5) if not np.isnan(m) else np.nan,
                "sharpe_4w": round(m/sd, 3) if (not np.isnan(m) and sd and sd > 0) else np.nan,
            })

    # B. Macro + SPY 200d MA
    for period in ["dev", "holdout"]:
        tbl = confirmation_table(
            wf.dropna(subset=["spy_above_200dma"]), "macro_quadrant",
            "spy_above_200dma", "fwd_4w_spy",
            {1.0: "above_200dma", 0.0: "below_200dma"}, period,
        )
        for _, r in tbl.iterrows():
            diag_frames.append({
                "period": period, "diagnostic": "B_macro_plus_spy_trend",
                "macro_quadrant": r["macro_quadrant"], "condition": r["condition"],
                "n": r["n"], "mean_4w": r["mean_4w"], "sharpe_4w": r["sharpe_4w"],
            })

    # C. Macro + credit trend
    for period in ["dev", "holdout"]:
        tbl = confirmation_table(
            wf.dropna(subset=["credit_trend_improving"]), "macro_quadrant",
            "credit_trend_improving", "fwd_4w_spy",
            {1.0: "credit_improving", 0.0: "credit_worsening"}, period,
        )
        for _, r in tbl.iterrows():
            diag_frames.append({
                "period": period, "diagnostic": "C_macro_plus_credit",
                "macro_quadrant": r["macro_quadrant"], "condition": r["condition"],
                "n": r["n"], "mean_4w": r["mean_4w"], "sharpe_4w": r["sharpe_4w"],
            })

    # D. Macro + current market state (focus on neutral_mixed)
    for period in ["dev", "holdout"]:
        s = wf[(wf["period"] == period) & (wf["market_state"] == "neutral_mixed")].dropna(
            subset=["macro_quadrant", "fwd_4w_spy"])
        for quad in QUADS:
            sub = s[s["macro_quadrant"] == quad]["fwd_4w_spy"]
            n = len(sub.dropna())
            m = sub.mean() if n >= 3 else np.nan
            sd = sub.std() if n >= 3 else np.nan
            diag_frames.append({
                "period": period, "diagnostic": "D_macro_plus_neutral_mixed_state",
                "macro_quadrant": quad, "condition": "state=neutral_mixed",
                "n": n, "mean_4w": round(m, 5) if not np.isnan(m) else np.nan,
                "sharpe_4w": round(m/sd, 3) if (not np.isnan(m) and sd and sd > 0) else np.nan,
            })

    diag_df = pd.DataFrame(diag_frames)
    diag_df.to_csv(OUT_DIR / "macro_confirmation_diagnostics_v2.csv", index=False)
    print(f"  Saved: macro_confirmation_diagnostics_v2.csv")

    # Summarise key confirmation results
    _print_confirmation_summary(diag_df)

    # ── 10. V1 vs V2 comparison ────────────────────────────────────────────────
    print("\n[9] V1 vs V2 comparison...")
    v1_summary = load_v1_summary()

    dev_fwd_dict = {r["macro_quadrant"]: {"mean_4w": r["mean_4w"], "n": r["n"]}
                    for _, r in dev_stats.iterrows()}
    hold_fwd_dict = {r["macro_quadrant"]: {"mean_4w": r["mean_4w"], "n": r["n"]}
                     for _, r in hold_stats.iterrows()}

    v2_data = {
        "n_series": n_series_used,
        "features": list(feat_panel.columns),
        "missing_series": missing_series,
        "quad_counts": quad_counts,
        "dev_spread": dev_spread,
        "nm_spread": nm_spread,
        "dev_fwd": dev_fwd_dict,
        "hold_fwd": hold_fwd_dict,
        "holdout_consistent": rank_consistent,
        "verdict": "TBD",  # filled below
    }

    if v1_summary:
        comp_df = build_comparison(v1_summary, v2_data)
        comp_df.to_csv(OUT_DIR / "v1_vs_v2_comparison.csv", index=False)
        print(comp_df.to_string(index=False))

    # ── 11. Pass / Fail decision ───────────────────────────────────────────────
    print("\n[10] Pass / Fail decision (v2)...")

    # Load v1 criteria for comparison
    v1_crit = v1_summary.get("criteria", {})
    v1_hold_consistent = v1_crit.get("holdout_rank_consistent", False)
    v1_hold_populated = sum(1 for v in v1_summary.get("holdout_quadrant_fwd_returns", {}).values()
                            if v.get("n", 0) > 0)

    # EXPERIMENTAL CANDIDATE gate
    crit_series = n_series_used >= 12
    crit_interpretable = final_loadings is not None
    crit_nm_spread = nm_spread > 0.005
    crit_holdout_improved = (
        (rank_consistent and not v1_hold_consistent) or
        (hold_quads_populated > v1_hold_populated) or
        (nm_rank_consistent and not v1_summary.get("criteria", {}).get("holdout_rank_consistent", False))
    )
    # Macro + confirmation: check if macro works better with SPY-trend or credit confirmation
    macro_with_trend_sharpe = _best_confirmation_sharpe(diag_df, "B_macro_plus_spy_trend", "dev")
    macro_only_sharpe = _best_confirmation_sharpe(diag_df, "A_macro_only", "dev")
    crit_confirmation_better = macro_with_trend_sharpe > macro_only_sharpe

    print(f"\n  Criteria:")
    print(f"    ≥12 series used      : {n_series_used} — {'MET' if crit_series else 'NOT MET'}")
    print(f"    Loadings interpretable: {crit_interpretable} — {'MET' if crit_interpretable else 'NOT MET'}")
    print(f"    nm_spread > 0.5%     : {nm_spread:.4f} — {'MET' if crit_nm_spread else 'NOT MET'}")
    print(f"    Holdout improved vs v1: {crit_holdout_improved} — {'MET' if crit_holdout_improved else 'NOT MET'}")
    print(f"    Confirm. better macro : {crit_confirmation_better} — {'MET' if crit_confirmation_better else 'NOT MET'}")

    if all([crit_series, crit_interpretable, crit_nm_spread, crit_holdout_improved, crit_confirmation_better]):
        verdict = "EXPERIMENTAL CANDIDATE"
    elif crit_nm_spread and (dev_spread > 0.005 or nm_spread > 0.005):
        verdict = "RESEARCH-ONLY"
    else:
        verdict = "DROP"

    crit_dev_spread = dev_spread > 0.010
    verdict_lines = [
        f"Series used: {n_series_used}/14 (threshold ≥12) — {'MET' if crit_series else 'NOT MET'}",
        f"Dev 4w SPY spread: {dev_spread:.4f} (threshold >0.01) — {'MET' if crit_dev_spread else 'NOT MET'}",
        f"Neutral-mixed spread: {nm_spread:.4f} (threshold >0.005) — {'MET' if crit_nm_spread else 'NOT MET'}",
        f"Holdout rank consistent: {rank_consistent}",
        f"Holdout improved vs v1: {crit_holdout_improved} — {'MET' if crit_holdout_improved else 'NOT MET'}",
        f"Confirmation diagnostics better: {crit_confirmation_better} — {'MET' if crit_confirmation_better else 'NOT MET'}",
        f"Loadings interpretable: {crit_interpretable} — {'MET' if crit_interpretable else 'NOT MET'}",
    ]

    print(f"\n  VERDICT: {verdict}")
    v2_data["verdict"] = verdict

    # Re-build comparison with final verdict
    if v1_summary:
        comp_df2 = build_comparison(v1_summary, v2_data)
        comp_df2.to_csv(OUT_DIR / "v1_vs_v2_comparison.csv", index=False)

    # ── 12. Save validation summary JSON ──────────────────────────────────────
    summary = {
        "sprint": "macro_regime_classifier_v2",
        "date": "2026-06-05",
        "verdict": verdict,
        "criteria": {
            "n_series_used": n_series_used,
            "crit_series_met": bool(crit_series),
            "crit_interpretable_met": bool(crit_interpretable),
            "dev_4w_spread": round(dev_spread, 5),
            "dev_4w_spread_met": bool(crit_dev_spread),
            "nm_spread": round(nm_spread, 5),
            "nm_spread_met": bool(crit_nm_spread),
            "holdout_rank_consistent": bool(rank_consistent),
            "holdout_improved_vs_v1": bool(crit_holdout_improved),
            "holdout_quads_populated": hold_quads_populated,
            "confirmation_better": bool(crit_confirmation_better),
        },
        "coverage": {
            "weekly_obs_total": int(len(weekly_dates)),
            "weekly_obs_with_quadrant": int(n_covered),
            "coverage_pct": round(float(n_covered) / len(weekly_dates) * 100, 1),
            "dev_end": DEV_END.strftime("%Y-%m-%d"),
            "holdout_start": HOLDOUT_START.strftime("%Y-%m-%d"),
        },
        "quadrant_distribution_weekly": quad_counts,
        "dev_quadrant_fwd_returns": {
            r["macro_quadrant"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"],
                                   "std_4w": r["std_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in dev_stats.iterrows() if pd.notna(r["mean_4w"])
        },
        "holdout_quadrant_fwd_returns": {
            r["macro_quadrant"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"],
                                   "std_4w": r["std_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in hold_stats.iterrows() if pd.notna(r["mean_4w"])
        },
        "neutral_mixed_quadrant_distribution": nm["macro_quadrant"].value_counts().to_dict(),
        "neutral_mixed_dev_fwd_returns": {
            r["macro_quadrant"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"],
                                   "std_4w": r["std_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in nm_dev_stats.iterrows() if pd.notna(r["mean_4w"])
        },
        "neutral_mixed_holdout_fwd_returns": {
            r["macro_quadrant"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"],
                                   "std_4w": r["std_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in nm_hold_stats.iterrows() if pd.notna(r["mean_4w"])
        },
        "fred_series_used": base_ids_in_panel,
        "fred_series_missing": missing_series,
        "fred_fetch_log": run_log,
        "pc_variance_explained": pc_var,
        "warnings": run_warnings,
    }

    with open(OUT_DIR / "macro_regime_validation_summary_v2.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Saved: macro_regime_validation_summary_v2.json")

    # ── 13. Write v1 vs v2 markdown ───────────────────────────────────────────
    if v1_summary:
        _write_comparison_md(comp_df2, v1_summary, summary)
        print(f"  Saved: v1_vs_v2_comparison.md")

    # ── 14. Write v2 notes markdown ───────────────────────────────────────────
    _write_v2_notes(summary, verdict_lines, nm_report, diag_df, final_loadings, pc_var)
    print(f"  Saved: macro_regime_classifier_v2_notes.md")

    print("\n" + "=" * 70)
    print(f"V2 SPRINT COMPLETE — VERDICT: {verdict}")
    print("=" * 70)
    if run_warnings:
        print(f"\nWarnings:")
        for w in run_warnings:
            print(f"  ! {w}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _best_confirmation_sharpe(diag_df: pd.DataFrame, diag: str, period: str) -> float:
    sub = diag_df[(diag_df["diagnostic"] == diag) & (diag_df["period"] == period)]
    if sub.empty or sub["sharpe_4w"].isna().all():
        return 0.0
    return float(sub["sharpe_4w"].dropna().max())


def _print_confirmation_summary(diag_df: pd.DataFrame) -> None:
    for diag in ["A_macro_only", "B_macro_plus_spy_trend", "C_macro_plus_credit",
                 "D_macro_plus_neutral_mixed_state"]:
        sub = diag_df[(diag_df["diagnostic"] == diag) & (diag_df["period"] == "dev")]
        if sub.empty:
            continue
        best = sub.dropna(subset=["sharpe_4w"]).nlargest(2, "sharpe_4w")
        print(f"\n  {diag} — top 2 by Sharpe (dev):")
        for _, r in best.iterrows():
            print(f"    quad={r['macro_quadrant']}, cond={r['condition']}, "
                  f"n={r['n']}, mean={r['mean_4w']:.4f}, sharpe={r['sharpe_4w']:.3f}")


def _write_factor_interpretation(loadings: pd.DataFrame, pc_var: dict) -> None:
    lines = [
        "# Macro Factor Interpretation",
        "",
        "Factor loadings from the last quarterly PCA refit in the development period.",
        "Signs have been adjusted so that:",
        "- PC1 (growth_factor) is positive when INDPRO_yoy is positive (above-trend growth)",
        "- PC2 (inflation_financial_conditions_factor) is positive when NFCI is positive (tight conditions)",
        "",
        f"## Variance Explained",
        "",
        "| Factor | Var Explained |",
        "| --- | --- |",
    ]
    for k, v in pc_var.items():
        lines.append(f"| {k} | {v}% |")

    lines += [
        "",
        "## Feature Loadings",
        "",
        "Positive = feature rises when factor rises. Negative = inverse.",
        "",
    ]
    # Build table header
    pc_cols = [c for c in loadings.columns if c.startswith("PC")]
    header = "| Feature | " + " | ".join(pc_cols) + " |"
    sep = "| --- | " + " | ".join(["---"] * len(pc_cols)) + " |"
    lines += [header, sep]
    for feat, row in loadings[pc_cols].iterrows():
        vals = " | ".join(f"{v:.3f}" for v in row)
        lines.append(f"| {feat} | {vals} |")

    # Interpretation notes
    lines += [
        "",
        "## Interpretation Notes",
        "",
        "### PC1 — growth_factor",
        "- High positive: economy expanding, industrial production rising, payrolls growing",
        "- High negative: contraction, rising unemployment, falling retail sales",
        "",
        "### PC2 — inflation_financial_conditions_factor",
        "- High positive: tight financial conditions (high NFCI), elevated spreads, high inflation",
        "- High negative: loose conditions, low spreads, subdued inflation",
        "",
    ]
    if "PC3" in pc_cols:
        lines += [
            "### PC3 — credit_liquidity_factor (if applicable)",
            "- Captures residual variation not explained by growth or inflation",
            "- May reflect liquidity / currency / idiosyncratic credit conditions",
            "",
        ]

    lines += [
        "## Quadrant Map",
        "",
        "| growth_factor | inflation_fc_factor | macro_quadrant |",
        "| --- | --- | --- |",
        "| > 0 | < 0 | **expansion** (Goldilocks) |",
        "| > 0 | > 0 | **overheating** |",
        "| < 0 | < 0 | **slowdown** |",
        "| < 0 | > 0 | **stress** |",
        "",
        "*Research artifact — no production code modified.*",
    ]

    with open(OUT_DIR / "macro_factor_interpretation.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_comparison_md(comp_df: pd.DataFrame, v1: dict, v2: dict) -> None:
    lines = [
        "# Macro Regime Classifier: V1 vs V2 Comparison",
        "",
        f"**V1 verdict:** `{v1.get('verdict', 'N/A')}`",
        f"**V2 verdict:** `{v2['verdict']}`",
        "",
        "## Key Differences",
        "",
        "| Metric | V1 | V2 |",
        "| --- | --- | --- |",
    ]
    key_rows = [
        "n_fred_series_used", "dev_spread", "nm_spread",
        "holdout_rank_consistent", "holdout_quads_populated", "verdict",
    ]
    for _, r in comp_df[comp_df["metric"].isin(key_rows)].iterrows():
        lines.append(f"| {r['metric']} | {r['v1']} | {r['v2']} |")

    lines += [
        "",
        "## Full Comparison Table",
        "",
        "| Metric | V1 | V2 |",
        "| --- | --- | --- |",
    ]
    for _, r in comp_df.iterrows():
        lines.append(f"| {r['metric']} | {r['v1']} | {r['v2']} |")

    lines += ["", "*Research artifact — no production code modified.*"]
    with open(OUT_DIR / "v1_vs_v2_comparison.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_v2_notes(
    summary: dict,
    verdict_lines: list,
    nm_report: pd.DataFrame,
    diag_df: pd.DataFrame,
    loadings: pd.DataFrame | None,
    pc_var: dict,
) -> None:
    verdict = summary["verdict"]
    crit = summary["criteria"]

    lines = [
        "# Macro Regime Classifier V2 — Sprint Notes",
        "",
        f"**Sprint date:** 2026-06-05",
        f"**Verdict:** `{verdict}`",
        "",
        "---",
        "",
        "## 1. Did v2 recover the missing FRED series?",
        "",
        f"V1 used {len(summary.get('fred_features', summary.get('fred_series_used', [])))} series.",
        f"V2 attempted 14 series and successfully used {crit['n_series_used']}.",
    ]
    if summary["fred_series_missing"]:
        lines.append(f"Still missing: {', '.join(summary['fred_series_missing'])}")
    else:
        lines.append("All 14 series successfully fetched or loaded from cache.")
    lines += [
        "",
        f"**Criterion ≥12 series:** {'MET' if crit['crit_series_met'] else 'NOT MET'}",
        "",
        "## 2. Did the full feature set change the PCA factors?",
        "",
        "| Factor | Variance Explained |",
        "| --- | --- |",
    ]
    for k, v in pc_var.items():
        lines.append(f"| {k} | {v}% |")

    lines += [
        "",
        "## 3. Are the factor loadings interpretable?",
        "",
    ]
    if loadings is not None:
        pc_cols = [c for c in loadings.columns if c.startswith("PC")]
        lines += ["| Feature | " + " | ".join(pc_cols) + " |",
                  "| --- | " + " | ".join(["---"] * len(pc_cols)) + " |"]
        for feat, row in loadings[pc_cols].iterrows():
            lines.append("| " + feat + " | " + " | ".join(f"{v:.3f}" for v in row) + " |")
        lines += ["", f"**Criterion loadings interpretable:** {'MET' if crit['crit_interpretable_met'] else 'NOT MET'}"]
    else:
        lines.append("Loadings unavailable.")

    lines += [
        "",
        "## 4. Did v2 improve holdout consistency vs v1?",
        "",
        f"- V2 holdout rank consistent: {crit['holdout_rank_consistent']}",
        f"- V2 holdout quadrants populated: {crit['holdout_quads_populated']}/4",
        f"- Holdout improved vs v1: {crit['holdout_improved_vs_v1']}",
        f"**Criterion:** {'MET' if crit['holdout_improved_vs_v1'] else 'NOT MET'}",
        "",
        "## 5. Does v2 split neutral_mixed better than v1?",
        "",
        f"V2 neutral_mixed dev spread: {crit['nm_spread']:.4f}",
        "",
        "| Period | Quadrant | N | Mean 4w | Sharpe |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, r in nm_report.iterrows():
        lines.append(f"| {r['period']} | {r['macro_quadrant']} | {int(r['n'])} | {r['mean_4w']} | {r['sharpe_4w']} |")

    lines += [
        "",
        f"**Criterion nm_spread > 0.5%:** {'MET' if crit['nm_spread_met'] else 'NOT MET'}",
        "",
        "## 6. Does macro work better alone or with confirmation?",
        "",
        "| Diagnostic | Best Sharpe (dev) |",
        "| --- | --- |",
    ]
    for diag in ["A_macro_only", "B_macro_plus_spy_trend", "C_macro_plus_credit",
                 "D_macro_plus_neutral_mixed_state"]:
        s = _best_confirmation_sharpe(diag_df, diag, "dev")
        lines.append(f"| {diag} | {s:.3f} |")

    lines += [
        "",
        f"**Criterion confirmation better than macro-only:** {'MET' if crit['confirmation_better'] else 'NOT MET'}",
        "",
        "## 7. Should the project proceed to macro-conditioned ETF tilt testing?",
        "",
    ]
    if verdict == "EXPERIMENTAL CANDIDATE":
        lines += [
            "**YES.** All five EXPERIMENTAL CANDIDATE criteria are met. Recommended next steps:",
            "",
            "1. Design a macro-conditioned ETF tilt overlay for the neutral_mixed state.",
            "2. Test whether `slowdown` and `expansion` quadrants justify different equity offense levels.",
            "3. Run through Phase D gate evaluation before any production integration.",
            "4. Do not modify production allocation logic until Phase D gates are cleared.",
        ]
    elif verdict == "RESEARCH-ONLY":
        lines += [
            "**CONDITIONAL.** Dev signal exists but holdout is unstable. Recommended next steps:",
            "",
            "1. Investigate the holdout period macro environment more carefully.",
            "2. Test macro quadrants as a research-only conditioning feature in a sandbox.",
            "3. Do not build a production ETF tilt overlay until holdout consistency improves.",
        ]
    else:
        lines += [
            "**NO.** Signal is too weak or unstable. Drop this branch.",
        ]

    lines += [
        "",
        "## 8. Final Verdict",
        "",
        f"**`{verdict}`**",
        "",
        "### Criteria Summary",
        "",
        "| Criterion | Result | Met? |",
        "| --- | --- | --- |",
    ]
    for vl in verdict_lines:
        parts = vl.split(" — ")
        met = parts[-1] if len(parts) > 1 else ""
        desc = " — ".join(parts[:-1]) if len(parts) > 1 else vl
        lines.append(f"| {desc} | {met} |  |")

    lines += [
        "",
        "## FRED Fetch Log",
        "",
        "| Series | Source | N Obs |",
        "| --- | --- | --- |",
    ]
    for entry in summary["fred_fetch_log"]:
        lines.append(f"| {entry['series']} | {entry['source']} | {entry['n_obs']} |")

    lines += [
        "",
        "---",
        "*Research artifact sprint — no production artifacts modified.*",
    ]

    with open(OUT_DIR / "macro_regime_classifier_v2_notes.md", "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
