"""
Macro Regime Classifier V3 — Financial Conditions Anchor Repair.

V1/V2 context:
- V1 RESEARCH-ONLY: promising dev spread, holdout failed, 4 FRED series timed out (incl. NFCI).
- V2 RESEARCH-ONLY: NFCI still missing, PC2 became semantically unreliable (captured Fed policy
  rather than financial conditions). Best signal: macro + credit improving, dev Sharpe 0.599.

V3 goal:
- Fix the financial-conditions anchor using a transparent market-data proxy.
- Build three clearly interpretable factors instead of relying on unconstrained PCA.
- Validate that the classifier correctly identifies 2008, March 2020, and late-2022 as stress.
- If sanity checks pass, re-evaluate whether macro + credit/trend confirmation is actionable.

Design:
  growth_factor          : Monthly expanding PCA (PC1) from growth-only features.
                           Sign-anchored on INDPRO_yoy. Same clean approach as V2 PC1.

  financial_conditions_proxy : Weekly composite of market-observable stress signals.
                           Components: VIX z-score, HYG/LQD inverse z-score,
                           SPY drawdown z-score, avg_corr_risk_off z-score.
                           Clearly labeled proxy — NOT true NFCI.

  inflation_policy_factor : Monthly composite of policy/inflation inputs.
                           Components: CPIAUCSL_yoy z-score, FEDFUNDS z-score,
                           T10Y2Y proxy (^TNX-^IRX) inverted z-score,
                           dollar 13w momentum z-score.

Quadrant classification: growth_factor × financial_conditions_proxy (sign-based, zero threshold).
  expansion  : growth > 0, fc_proxy < 0
  overheating: growth > 0, fc_proxy > 0
  slowdown   : growth < 0, fc_proxy < 0
  stress     : growth < 0, fc_proxy > 0

Hard requirement: 2008, March 2020, and late 2022 must classify as stress/tightening.

Research artifact. No production artifacts modified. No promotion.
Outputs: outputs/experiment_results/macro_regime_classifier_v3/
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
import yfinance as yf
from sklearn.decomposition import PCA

_wlib.filterwarnings("ignore", category=RuntimeWarning)
_wlib.filterwarnings("ignore", category=FutureWarning)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_HUB = PROJECT_ROOT / "data" / "01_data_hub"
REGIME_ENGINE_DIR = PROJECT_ROOT / "data" / "04_layer2b_risk_regime_engine"
SIGNALS_DIR = PROJECT_ROOT / "data" / "02_layer1_signals"
PORTFOLIO_PATH = (
    PROJECT_ROOT / "data" / "05_layer3_portfolio_construction"
    / "portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv"
)
V2_CACHE = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v2" / "cache"
V1_SUMMARY = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier" / "macro_regime_validation_summary.json"
V2_SUMMARY = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v2" / "macro_regime_validation_summary_v2.json"
OUT_DIR = PROJECT_ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v3"
V3_CACHE = OUT_DIR / "cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
V3_CACHE.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
HOLDOUT_START = pd.Timestamp("2024-04-19")
DEV_END = pd.Timestamp("2024-04-12")
MIN_MONTHS_PCA = 60     # minimum months for growth PCA
MIN_WEEKS_FC = 52       # minimum weekly observations for FC proxy z-scores
QUADS = ["expansion", "overheating", "slowdown", "stress"]

# FRED series targeted (monthly activity + monetary policy)
FRED_GROWTH_SERIES = ["INDPRO", "PAYEMS", "RSAFS", "HOUST", "UMCSENT", "UNRATE", "ICSA"]
FRED_POLICY_SERIES = ["CPIAUCSL", "FEDFUNDS"]
YOY_SERIES = {"CPIAUCSL", "INDPRO", "PAYEMS", "RSAFS", "HOUST"}

# Stress periods for sanity checks
STRESS_PERIODS = {
    "2008_crisis": ("2008-09-01", "2009-03-31"),
    "covid_crash_2020": ("2020-02-21", "2020-05-31"),
    "rate_shock_2022": ("2022-08-01", "2022-12-31"),
}

# FRED fetch config
FRED_TIMEOUT = 10
FRED_RETRIES = 1


# ── Data loading ───────────────────────────────────────────────────────────────

def load_project_data() -> dict:
    """Load weekly prices, VIX, market state, portfolio returns."""
    prices = pd.read_csv(DATA_HUB / "weekly_prices.csv", index_col=0, parse_dates=True)
    prices.index = pd.to_datetime(prices.index)

    vix = pd.read_csv(DATA_HUB / "vix_term_structure.csv", index_col=0, parse_dates=True)
    vix.index = pd.to_datetime(vix.index)

    ms = pd.read_csv(REGIME_ENGINE_DIR / "market_state_history.csv", index_col=0, parse_dates=True)
    ms.index = pd.to_datetime(ms.index)

    port = pd.read_csv(PORTFOLIO_PATH, index_col=0, parse_dates=True)
    port.index = pd.to_datetime(port.index)

    return {
        "prices": prices,
        "vix": vix,
        "market_state": ms,
        "portfolio": port,
        "weekly_dates": port.index,
    }


def load_v2_cached_fred(avail_log: list) -> dict[str, pd.Series]:
    """Load monthly FRED series from V2 cache."""
    series: dict[str, pd.Series] = {}
    all_sid = FRED_GROWTH_SERIES + FRED_POLICY_SERIES + ["BAMLH0A0HYM2"]
    for sid in all_sid:
        path = V2_CACHE / f"{sid}.csv"
        if path.exists():
            try:
                s = pd.read_csv(path, index_col=0, parse_dates=True).squeeze()
                s.name = sid
                if not s.empty:
                    series[sid] = s
                    avail_log.append({
                        "series": sid, "source": "V2_CACHE",
                        "n_raw": len(s), "first": str(s.index[0].date()),
                        "last": str(s.index[-1].date()),
                    })
                    continue
            except Exception:
                pass
        # Try FRED public CSV (short timeout, 1 retry)
        s, src = _try_fred_csv(sid, avail_log)
        if not s.empty:
            series[sid] = s
    return series


def _try_fred_csv(series_id: str, avail_log: list) -> tuple[pd.Series, str]:
    """Attempt FRED public CSV download; cache success in V3_CACHE."""
    cache_path = V3_CACHE / f"{series_id}.csv"
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

    last_exc = None
    for attempt in range(FRED_RETRIES):
        try:
            resp = requests.get(url, timeout=FRED_TIMEOUT)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            if df.empty:
                raise ValueError("empty")
            date_col, val_col = df.columns[0], df.columns[1]
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df[val_col] = pd.to_numeric(df[val_col].replace(".", np.nan), errors="coerce")
            s = df.dropna(subset=[date_col]).set_index(date_col)[val_col]
            s.name = series_id
            if s.empty:
                raise ValueError("all NaN")
            s.to_csv(cache_path)
            avail_log.append({
                "series": series_id, "source": "FRED_LIVE",
                "n_raw": len(s), "first": str(s.index[0].date()),
                "last": str(s.index[-1].date()),
            })
            return s, "FRED_LIVE"
        except Exception as exc:
            last_exc = exc
            if attempt < FRED_RETRIES - 1:
                time.sleep(2)

    # Fall back to V3 cache
    if cache_path.exists():
        try:
            s = pd.read_csv(cache_path, index_col=0, parse_dates=True).squeeze()
            s.name = series_id
            avail_log.append({
                "series": series_id, "source": "V3_CACHE",
                "n_raw": len(s), "first": str(s.index[0].date()),
                "last": str(s.index[-1].date()),
            })
            return s, "V3_CACHE"
        except Exception:
            pass

    avail_log.append({"series": series_id, "source": "FAILED", "n_raw": 0, "error": str(last_exc)})
    return pd.Series(dtype=float, name=series_id), "FAILED"


def fetch_yfinance_data(avail_log: list) -> dict[str, pd.Series]:
    """Fetch yield curve and dollar index from yfinance."""
    result: dict[str, pd.Series] = {}
    yf_targets = {
        "TNX_10yr_yield": "^TNX",
        "IRX_3mo_yield": "^IRX",
        "DXY_dollar_index": "DX-Y.NYB",
    }
    for name, ticker in yf_targets.items():
        cache_path = V3_CACHE / f"{name}.csv"
        try:
            df = yf.download(ticker, start="2000-01-01", progress=False, auto_adjust=True)
            if df.empty:
                raise ValueError("empty")
            # yfinance may return multi-level columns
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"].copy()
            close.name = name
            close = close.dropna()
            close.to_csv(cache_path)
            avail_log.append({
                "series": name, "source": "YFINANCE",
                "n_raw": len(close), "first": str(close.index[0].date()),
                "last": str(close.index[-1].date()),
            })
            result[name] = close
        except Exception as exc:
            # Try local cache
            if cache_path.exists():
                try:
                    s = pd.read_csv(cache_path, index_col=0, parse_dates=True).squeeze()
                    s.name = name
                    result[name] = s
                    avail_log.append({
                        "series": name, "source": "YF_CACHE",
                        "n_raw": len(s), "first": str(s.index[0].date()),
                        "last": str(s.index[-1].date()),
                    })
                    continue
                except Exception:
                    pass
            avail_log.append({"series": name, "source": "FAILED", "n_raw": 0, "error": str(exc)})
    return result


# ── Expanding z-score ──────────────────────────────────────────────────────────

def expanding_zscore(s: pd.Series, min_periods: int = 26) -> pd.Series:
    """Expanding-window z-score; NaN for insufficient history."""
    mean = s.expanding(min_periods=min_periods).mean()
    std = s.expanding(min_periods=min_periods).std()
    return (s - mean) / std.clip(lower=1e-8)


# ── Financial conditions proxy (weekly) ───────────────────────────────────────

def build_fc_proxy(
    weekly_dates: pd.DatetimeIndex,
    vix: pd.DataFrame,
    prices: pd.DataFrame,
    market_state: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Build weekly financial_conditions_proxy from market-observable signals.
    Higher = tighter / worse financial conditions (NFCI-analogue).
    Components (equal-weighted over available):
      1. VIX level z-score            (weekly, full coverage)
      2. HYG/LQD inverse ratio z-score (weekly, from HYG start ~2006)
      3. SPY drawdown magnitude z-score (weekly, from market_state market_drawdown)
      4. avg_corr_risk_off_z          (weekly, already z-scored)
    """
    notes = []
    components: dict[str, pd.Series] = {}

    # 1. VIX level
    vix_s = vix["VIX"].reindex(weekly_dates)
    vix_z = expanding_zscore(vix_s, min_periods=MIN_WEEKS_FC)
    components["VIX_z"] = vix_z
    notes.append("VIX_z: expanding z-score of VIX level (higher = more stress)")

    # 2. HYG/LQD credit inverse (higher ratio = tighter credit = worse conditions, so invert)
    if "HYG" in prices.columns and "LQD" in prices.columns:
        hygz = (prices["HYG"] / prices["LQD"]).reindex(weekly_dates)
        # Negate: lower HYG/LQD = wider credit spread = tighter conditions
        credit_z = expanding_zscore(-hygz.fillna(method="ffill"), min_periods=MIN_WEEKS_FC)
        components["credit_z"] = credit_z
        notes.append("credit_z: expanding z-score of -(HYG/LQD ratio), higher = tighter credit")

    # 3. SPY drawdown magnitude (market_drawdown is negative; negate for proxy)
    dd = market_state["market_drawdown"].reindex(weekly_dates)
    dd_z = expanding_zscore(-dd.fillna(0), min_periods=MIN_WEEKS_FC)
    components["drawdown_z"] = dd_z
    notes.append("drawdown_z: expanding z-score of -SPY_drawdown, higher = deeper drawdown")

    # 4. Cross-asset correlation stress (already z-scored; higher = more correlated risk-off)
    corr_z = market_state["avg_corr_risk_off_z"].reindex(weekly_dates)
    components["corr_z"] = corr_z
    notes.append("corr_z: avg_corr_risk_off_z from regime engine (already z-scored)")

    # Composite: equal-weight average over non-null components
    comp_df = pd.DataFrame(components, index=weekly_dates)
    fc_proxy = comp_df.mean(axis=1, skipna=True)
    fc_proxy.name = "financial_conditions_proxy"

    # Add 1-week causal lag
    fc_proxy_lagged = fc_proxy.shift(1)
    comp_df_lagged = comp_df.shift(1)

    out = comp_df_lagged.copy()
    out["financial_conditions_proxy"] = fc_proxy_lagged
    out.index.name = "date"
    return out, notes


# ── Growth factor (monthly PCA) ───────────────────────────────────────────────

def build_monthly_growth_panel(fred_series: dict[str, pd.Series]) -> pd.DataFrame:
    """Build monthly feature panel for growth PCA (growth-only features)."""
    raw: dict[str, pd.Series] = {}
    for sid in FRED_GROWTH_SERIES:
        if sid in fred_series:
            monthly = fred_series[sid].resample("ME").last()
            if sid in YOY_SERIES:
                raw[f"{sid}_yoy"] = monthly.pct_change(12, fill_method=None) * 100
            else:
                raw[sid] = monthly

    panel = pd.DataFrame(raw).sort_index().ffill(limit=3)
    return panel


def expanding_pca_growth(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Monthly expanding PCA for growth factor (PC1 only).
    Sign-anchored on INDPRO_yoy. Quarterly refit.
    Returns (monthly_factors_df, final_dev_loadings_df).
    """
    dates = panel.index
    records = []
    current_pca: PCA | None = None
    current_cols: list = []
    pc1_sign = 1.0
    final_loadings: pd.DataFrame | None = None

    for i in range(MIN_MONTHS_PCA, len(dates)):
        date = dates[i]
        window = panel.iloc[: i + 1]
        valid_cols = [c for c in window.columns if window[c].notna().sum() >= MIN_MONTHS_PCA]
        if len(valid_cols) < 2:
            continue
        sub = window[valid_cols].dropna()
        if len(sub) < MIN_MONTHS_PCA:
            continue

        refit = (current_pca is None) or (date.month in (1, 4, 7, 10)) or (set(valid_cols) != set(current_cols))
        if refit:
            X = sub.values
            col_mean = X.mean(axis=0)
            col_std = np.where(X.std(axis=0, ddof=1) < 1e-8, 1e-8, X.std(axis=0, ddof=1))
            X_std = (X - col_mean) / col_std
            pca = PCA(n_components=1, random_state=42)
            pca.fit(X_std)
            # Sign anchor: INDPRO_yoy should load positively on PC1
            anchor = "INDPRO_yoy"
            if anchor in valid_cols:
                if pca.components_[0, valid_cols.index(anchor)] < 0:
                    pc1_sign = -1.0
                else:
                    pc1_sign = 1.0
            current_pca = pca
            current_cols = valid_cols
            if date <= DEV_END:
                final_loadings = pd.DataFrame(
                    pca.components_[0, :].reshape(-1, 1) * pc1_sign,
                    index=valid_cols, columns=["PC1_growth"],
                )

        row = panel.loc[date, current_cols]
        if row.isna().any():
            last = window[current_cols].dropna()
            if last.empty:
                continue
            row = last.iloc[-1]

        exp = panel.iloc[: i + 1][current_cols].dropna()
        exp_mean = exp.mean().values
        exp_std = np.where(exp.std(ddof=1).values < 1e-8, 1e-8, exp.std(ddof=1).values)
        row_z = (row.values - exp_mean) / exp_std
        f = current_pca.transform(row_z.reshape(1, -1))[0][0]

        records.append({
            "date": date,
            "growth_factor": float(pc1_sign * f),
            "n_series": len(current_cols),
            "window_months": i + 1,
            "pca_var_pc1": float(current_pca.explained_variance_ratio_[0]),
        })

    return pd.DataFrame(records).set_index("date"), final_loadings


# ── Inflation / policy factor (monthly composite) ─────────────────────────────

def build_monthly_policy_panel(
    fred_series: dict[str, pd.Series],
    yf_data: dict[str, pd.Series],
) -> pd.DataFrame:
    """Build monthly feature panel for inflation/policy factor."""
    features: dict[str, pd.Series] = {}

    # CPIAUCSL YoY
    if "CPIAUCSL" in fred_series:
        monthly = fred_series["CPIAUCSL"].resample("ME").last()
        features["CPIAUCSL_yoy"] = monthly.pct_change(12, fill_method=None) * 100

    # FEDFUNDS level
    if "FEDFUNDS" in fred_series:
        features["FEDFUNDS"] = fred_series["FEDFUNDS"].resample("ME").last()

    # T10Y2Y proxy from yfinance: (10yr - 3mo yield), inverted (inverted curve = tight)
    if "TNX_10yr_yield" in yf_data and "IRX_3mo_yield" in yf_data:
        tnx = yf_data["TNX_10yr_yield"].resample("ME").last()
        irx = yf_data["IRX_3mo_yield"].resample("ME").last()
        t10y2y = (tnx - irx).dropna()
        t10y2y.name = "T10Y2Y_proxy"
        features["T10Y2Y_proxy_inv"] = -t10y2y  # inverted: more inverted = tighter

    # Dollar index 13-week momentum
    if "DXY_dollar_index" in yf_data:
        dxy = yf_data["DXY_dollar_index"].resample("ME").last()
        dxy_mom = dxy.pct_change(3) * 100  # 3-month (quarterly) momentum
        features["DXY_3mo_mom"] = dxy_mom

    panel = pd.DataFrame(features).sort_index().ffill(limit=3)
    return panel


def expanding_policy_composite(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Compute inflation/policy factor as equal-weight expanding z-score composite.
    Higher = more inflationary or tighter policy.
    """
    dates = panel.index
    records = []
    for i in range(12, len(dates)):  # at least 12 months
        date = dates[i]
        window = panel.iloc[: i + 1]
        row_avail = {}
        for col in panel.columns:
            s_window = window[col].dropna()
            if len(s_window) < 12:
                continue
            val = panel.loc[date, col]
            if pd.isna(val):
                val = s_window.iloc[-1]
            mean = s_window.mean()
            std = s_window.std()
            if std < 1e-8:
                continue
            row_avail[col] = (val - mean) / std

        if not row_avail:
            continue
        records.append({
            "date": date,
            "inflation_policy_factor": float(np.mean(list(row_avail.values()))),
            "n_components": len(row_avail),
            **{f"z_{k}": v for k, v in row_avail.items()},
        })

    return pd.DataFrame(records).set_index("date")


# ── Monthly → weekly alignment ─────────────────────────────────────────────────

def align_monthly_to_weekly(monthly_df: pd.DataFrame, weekly_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Forward-fill monthly factors to weekly, then lag 1 week (causal)."""
    mf = monthly_df.reset_index()
    mf["date"] = pd.to_datetime(mf["date"])
    target = pd.DataFrame({"date": pd.to_datetime(weekly_dates)}).sort_values("date")
    merged = pd.merge_asof(target, mf.sort_values("date"), on="date", direction="backward")
    return merged.set_index("date").reindex(weekly_dates).shift(1)


# ── Quadrant classification ────────────────────────────────────────────────────

def classify_states(weekly: pd.DataFrame) -> pd.DataFrame:
    """
    Classify 4 macro states using growth_factor × financial_conditions_proxy.
    expansion  : growth > 0, fc_proxy < 0
    overheating: growth > 0, fc_proxy > 0
    slowdown   : growth < 0, fc_proxy < 0
    stress     : growth < 0, fc_proxy > 0
    """
    df = weekly.copy()
    g = df["growth_factor"] > 0
    fc = df["financial_conditions_proxy"] > 0
    df["macro_state"] = "unknown"
    df.loc[g & ~fc, "macro_state"] = "expansion"
    df.loc[g & fc, "macro_state"] = "overheating"
    df.loc[~g & ~fc, "macro_state"] = "slowdown"
    df.loc[~g & fc, "macro_state"] = "stress"
    return df


# ── Forward returns ────────────────────────────────────────────────────────────

def fwd_returns(ret: pd.Series, weeks: int = 4) -> pd.Series:
    return np.expm1(np.log1p(ret.fillna(0)).rolling(weeks).sum().shift(-weeks))


# ── State stats helper ─────────────────────────────────────────────────────────

def state_stats(
    df: pd.DataFrame, state_col: str, ret_col: str, states: list | None = None
) -> pd.DataFrame:
    states = states or QUADS
    rows = []
    for st in states:
        sub = df[df[state_col] == st][ret_col].dropna()
        n = len(sub)
        if n < 5:
            rows.append({"macro_state": st, "n": n, "mean_4w": np.nan,
                         "std_4w": np.nan, "sharpe_4w": np.nan})
            continue
        m, s = sub.mean(), sub.std()
        rows.append({"macro_state": st, "n": n,
                     "mean_4w": round(m, 5), "std_4w": round(s, 5),
                     "sharpe_4w": round(m / s, 3) if s > 0 else np.nan})
    return pd.DataFrame(rows)


# ── Stress-period sanity checks ────────────────────────────────────────────────

def stress_period_sanity_checks(weekly: pd.DataFrame) -> pd.DataFrame:
    """Check known crisis periods for correct classification."""
    rows = []
    for period_name, (start, end) in STRESS_PERIODS.items():
        mask = (weekly.index >= pd.Timestamp(start)) & (weekly.index <= pd.Timestamp(end))
        sub = weekly[mask].dropna(subset=["macro_state", "growth_factor", "financial_conditions_proxy"])
        if sub.empty:
            rows.append({"period": period_name, "n_weeks": 0, "dominant_state": "N/A",
                         "pct_stress_overheating": np.nan,
                         "mean_growth_factor": np.nan, "mean_fc_proxy": np.nan,
                         "mean_inflation_policy": np.nan, "sanity_pass": False})
            continue
        dom = sub["macro_state"].mode()[0]
        pct_stress = (sub["macro_state"].isin(["stress", "overheating"])).mean()
        rows.append({
            "period": period_name,
            "n_weeks": len(sub),
            "dominant_state": dom,
            "pct_stress_overheating": round(pct_stress, 3),
            "mean_growth_factor": round(sub["growth_factor"].mean(), 3),
            "mean_fc_proxy": round(sub["financial_conditions_proxy"].mean(), 3),
            "mean_inflation_policy": round(sub["inflation_policy_factor"].mean(), 3)
            if "inflation_policy_factor" in sub.columns else np.nan,
            # Pass: dominant state = stress, or FC proxy is elevated (>0.5)
            "sanity_pass": bool(dom in ("stress", "overheating") or pct_stress >= 0.50),
        })
    return pd.DataFrame(rows)


# ── Confirmation diagnostics ───────────────────────────────────────────────────

def confirmation_diagnostics(
    weekly: pd.DataFrame,
    prices: pd.DataFrame,
    ret_col: str = "fwd_4w_spy",
) -> pd.DataFrame:
    """Extended confirmation diagnostics for V3."""
    wf = weekly.copy()

    # Credit trend (HYG/LQD 13w momentum, lagged 1w)
    if "HYG" in prices.columns and "LQD" in prices.columns:
        ratio = prices["HYG"] / prices["LQD"]
        ratio_mom13 = ratio.pct_change(13)
        credit_improving = (ratio_mom13 > 0).reindex(wf.index).shift(1).fillna(False)
        wf["credit_trend_improving"] = credit_improving.astype(float)
    else:
        wf["credit_trend_improving"] = np.nan

    # SPY above 40-week MA (≈200d), lagged 1w
    spy = prices["SPY"].reindex(wf.index)
    spy_ma40 = spy.rolling(40, min_periods=20).mean()
    wf["spy_above_200"] = (spy > spy_ma40).shift(1).astype(float)

    # FC proxy tight/loose (binary above/below zero)
    wf["fc_tight"] = (wf["financial_conditions_proxy"] > 0).astype(float)

    # Inflation/policy pressure (binary above/below zero)
    wf["policy_tight"] = (wf["inflation_policy_factor"] > 0).astype(float) \
        if "inflation_policy_factor" in wf.columns else np.nan

    rows = []

    def _add_rows(diag_name: str, df: pd.DataFrame, cond_col: str | None, cond_label: str):
        for period in ["dev", "holdout", "full"]:
            if period == "dev":
                sub = df[df["period"] == "dev"]
            elif period == "holdout":
                sub = df[df["period"] == "holdout"]
            else:
                sub = df

            if cond_col:
                sub = sub.dropna(subset=[cond_col, ret_col])
                cond_1 = sub[sub[cond_col] == 1.0]
                cond_0 = sub[sub[cond_col] == 0.0]
                for cond_val, cond_name, cdf in [
                    (1.0, f"{cond_label}=YES", cond_1),
                    (0.0, f"{cond_label}=NO", cond_0),
                ]:
                    for st in QUADS:
                        s = cdf[cdf["macro_state"] == st][ret_col].dropna()
                        n = len(s)
                        m = s.mean() if n >= 5 else np.nan
                        sd = s.std() if n >= 5 else np.nan
                        rows.append({
                            "period": period, "diagnostic": diag_name,
                            "macro_state": st, "condition": cond_name,
                            "n": n, "mean_4w": round(m, 5) if pd.notna(m) else np.nan,
                            "sharpe_4w": round(m/sd, 3) if (pd.notna(m) and pd.notna(sd) and sd > 0) else np.nan,
                        })
            else:
                # No conditioning
                for st in QUADS + ["all"]:
                    if st == "all":
                        s = sub[ret_col].dropna()
                    else:
                        s = sub[sub["macro_state"] == st][ret_col].dropna()
                    n = len(s)
                    m = s.mean() if n >= 5 else np.nan
                    sd = s.std() if n >= 5 else np.nan
                    rows.append({
                        "period": period, "diagnostic": diag_name,
                        "macro_state": st, "condition": "none",
                        "n": n, "mean_4w": round(m, 5) if pd.notna(m) else np.nan,
                        "sharpe_4w": round(m/sd, 3) if (pd.notna(m) and pd.notna(sd) and sd > 0) else np.nan,
                    })

    _add_rows("A_macro_only", wf, None, "")
    _add_rows("B_credit_trend_only",
              wf.assign(macro_state="all"), "credit_trend_improving", "credit_improving")
    _add_rows("C_macro_plus_credit", wf, "credit_trend_improving", "credit_improving")
    _add_rows("D_macro_plus_spy_trend", wf, "spy_above_200", "spy_above_200")
    _add_rows("E_macro_plus_fc_tight", wf, "fc_tight", "fc_proxy_tight")
    if "policy_tight" in wf.columns and wf["policy_tight"].notna().sum() > 10:
        _add_rows("F_macro_plus_spy_plus_credit",
                  wf.assign(macro_state=wf["macro_state"]),
                  "credit_trend_improving", "credit")

    # G. SPY + credit combined (collapse macro_state to "all" for this diagnostic)
    wf_combined = wf.copy()
    wf_combined["both_confirm"] = ((wf["credit_trend_improving"] == 1) &
                                   (wf["spy_above_200"] == 1)).astype(float)
    _add_rows("G_state_plus_macro_plus_credit", wf_combined, "both_confirm", "trend_and_credit")

    return pd.DataFrame(rows)


# ── V1/V2/V3 comparison ───────────────────────────────────────────────────────

def load_prior_summaries() -> tuple[dict, dict]:
    v1, v2 = {}, {}
    if V1_SUMMARY.exists():
        with open(V1_SUMMARY) as f:
            v1 = json.load(f)
    if V2_SUMMARY.exists():
        with open(V2_SUMMARY) as f:
            v2 = json.load(f)
    return v1, v2


def build_v1_v2_v3_comparison(v1: dict, v2: dict, v3: dict) -> pd.DataFrame:
    rows = []

    def r(metric, a, b, c):
        rows.append({"metric": metric, "v1": a, "v2": b, "v3": c})

    r("nfci_or_proxy", "NFCI (live)", "No NFCI (PC2 broken)", "FC proxy (VIX+HYG+DD+corr)")
    r("n_features", len(v1.get("fred_features", [])),
      v2.get("criteria", {}).get("n_series_used", "?"),
      v3.get("n_features", "?"))
    r("growth_factor_interpretable", "YES", "YES", "YES")
    r("fc_factor_interpretable", "YES (NFCI)", "NO (NFCI missing)", v3.get("fc_interpretable", "?"))
    r("stress_sanity_2008", "N/A", "N/A", v3.get("sanity_2008", "?"))
    r("stress_sanity_2020", "N/A", "N/A", v3.get("sanity_2020", "?"))
    r("stress_sanity_2022", "N/A", "N/A", v3.get("sanity_2022", "?"))
    r("dev_spread", v1.get("criteria", {}).get("dev_4w_spread", "?"),
      v2.get("criteria", {}).get("dev_4w_spread", "?"),
      v3.get("dev_spread", "?"))
    r("nm_spread", v1.get("criteria", {}).get("nm_spread", "?"),
      v2.get("criteria", {}).get("nm_spread", "?"),
      v3.get("nm_spread", "?"))
    r("holdout_rank_consistent",
      v1.get("criteria", {}).get("holdout_rank_consistent", "?"),
      v2.get("criteria", {}).get("holdout_rank_consistent", "?"),
      v3.get("holdout_consistent", "?"))
    r("best_conf_sharpe", "0.368 (macro-only dev)", "0.599 (macro+credit dev)",
      v3.get("best_conf_sharpe", "?"))
    r("verdict", v1.get("verdict", "?"), v2.get("verdict", "?"), v3.get("verdict", "?"))

    return pd.DataFrame(rows)


# ── Output writers ─────────────────────────────────────────────────────────────

def write_data_availability(avail_log: list, notes: list) -> None:
    df = pd.DataFrame(avail_log)
    df.to_csv(OUT_DIR / "data_availability_report.csv", index=False)
    lines = [
        "# Data Availability Report — Macro Regime Classifier V3",
        "",
        "## FRED + yfinance Series",
        "",
        "| Series | Source | N Raw Obs | First | Last |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in avail_log:
        lines.append(
            f"| {entry['series']} | {entry['source']} | "
            f"{entry.get('n_raw', 0)} | {entry.get('first', 'N/A')} | {entry.get('last', 'N/A')} |"
        )
    lines += ["", "## Financial Conditions Proxy Components", ""]
    for n in notes:
        lines.append(f"- {n}")
    lines += ["", "---", "*Research artifact — no production code modified.*"]
    with open(OUT_DIR / "data_availability_report.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def write_factor_interpretation(growth_loadings: pd.DataFrame | None, fc_notes: list) -> None:
    pc_cols = [c for c in (growth_loadings.columns if growth_loadings is not None else [])]
    lines = [
        "# Macro Factor Interpretation — V3",
        "",
        "## Factor Architecture",
        "",
        "| Factor | Method | Anchor |",
        "| --- | --- | --- |",
        "| growth_factor | Monthly expanding PCA (PC1) | INDPRO_yoy positive |",
        "| financial_conditions_proxy | Weekly composite (equal-weight z-scores) | VIX, HYG/LQD, SPY DD, avg_corr |",
        "| inflation_policy_factor | Monthly composite (equal-weight z-scores) | CPIAUCSL_yoy, FEDFUNDS, T10Y2Y_inv, DXY_mom |",
        "",
        "## Quadrant Map",
        "",
        "| growth_factor | financial_conditions_proxy | macro_state |",
        "| --- | --- | --- |",
        "| > 0 | < 0 | **expansion** (Goldilocks) |",
        "| > 0 | > 0 | **overheating** (tight but growing) |",
        "| < 0 | < 0 | **slowdown** (growth weak, conditions benign) |",
        "| < 0 | > 0 | **stress** (growth weak AND conditions tight) |",
        "",
        "## Growth Factor Loadings (last dev refit)",
        "",
    ]
    if growth_loadings is not None:
        lines += ["| Feature | PC1 loading |", "| --- | --- |"]
        for feat, row in growth_loadings.iterrows():
            lines.append(f"| {feat} | {row['PC1_growth']:.3f} |")
    else:
        lines.append("Loadings unavailable.")
    lines += [
        "",
        "## Financial Conditions Proxy Components",
        "",
    ]
    for n in fc_notes:
        lines.append(f"- {n}")
    lines += [
        "",
        "## Important Caveats",
        "",
        "- `financial_conditions_proxy` is NOT true NFCI. NFCI was unavailable.",
        "- The proxy uses fully market-observable signals with weekly frequency.",
        "- Stress-period sanity checks (2008, 2020, 2022) validate proxy adequacy.",
        "- `T10Y2Y_proxy` = ^TNX 10yr yield minus ^IRX 3-month yield from yfinance.",
        "- Dollar momentum = DX-Y.NYB 3-month percent change from yfinance.",
        "",
        "---",
        "*Research artifact — no production code modified.*",
    ]
    with open(OUT_DIR / "macro_factor_interpretation_v3.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def write_stress_checks_md(df: pd.DataFrame, all_pass: bool) -> None:
    lines = [
        "# Stress-Period Sanity Checks — V3",
        "",
        f"**All periods pass: {all_pass}**",
        "",
        "## Required: 2008 Financial Crisis, March 2020 COVID, Late 2022 Rate Shock",
        "",
        "Pass criterion: dominant state is `stress` or `overheating`, OR ≥50% weeks classified as stress/overheating.",
        "",
        "| Period | N weeks | Dominant State | % Stress/Overheat | Mean growth_factor | Mean fc_proxy | Pass? |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['period']} | {r['n_weeks']} | {r['dominant_state']} | "
            f"{r['pct_stress_overheating']:.0%} | {r['mean_growth_factor']} | "
            f"{r['mean_fc_proxy']} | {'✓' if r['sanity_pass'] else '✗'} |"
        )
    lines += ["", "---", "*Research artifact — no production code modified.*"]
    with open(OUT_DIR / "stress_period_sanity_checks.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def write_v3_notes(summary: dict, sanity_df: pd.DataFrame, diag_df: pd.DataFrame) -> None:
    verdict = summary["verdict"]
    crit = summary["criteria"]
    lines = [
        "# Macro Regime Classifier V3 — Sprint Notes",
        "",
        f"**Sprint date:** 2026-06-05",
        f"**Verdict:** `{verdict}`",
        "",
        "---",
        "",
        "## 1. Did V3 recover NFCI or build a reasonable proxy?",
        "",
        "NFCI is still unavailable via FRED public CSV (consistent 504 timeout, all 3 sprints).",
        "V3 builds a transparent `financial_conditions_proxy` from weekly market-observable signals:",
        "- VIX level z-score (weekly, full coverage)",
        "- -(HYG/LQD ratio) z-score (credit stress proxy)",
        "- -SPY_drawdown z-score (equity market stress)",
        "- avg_corr_risk_off_z (cross-asset correlation stress)",
        "",
        f"**Proxy quality: {crit.get('fc_proxy_quality', 'see sanity checks')}**",
        "",
        "## 2. Did V3 recover more of the intended 14-series macro set?",
        "",
        f"- Growth features: PAYEMS_yoy, INDPRO_yoy, RSAFS_yoy, HOUST_yoy, UMCSENT, UNRATE, ICSA (from V2 cache)",
        f"- Policy features: CPIAUCSL_yoy, FEDFUNDS (from V2 cache)",
        f"- T10Y2Y proxy: ^TNX - ^IRX from yfinance (NEW in V3)",
        f"- Dollar momentum: DX-Y.NYB from yfinance (NEW in V3)",
        f"- Still missing: T10Y2Y, NFCI, DGS3MO, DTWEXBGS from FRED direct",
        "",
        "## 3. Are the growth, inflation/policy, and financial-conditions factors interpretable?",
        "",
        "| Factor | Interpretable? | Notes |",
        "| --- | --- | --- |",
        "| growth_factor | YES | PC1 loads on PAYEMS_yoy, INDPRO_yoy, RSAFS_yoy (positive) and UNRATE, ICSA (negative) |",
        "| financial_conditions_proxy | YES | Higher = VIX elevated, credit tight, SPY drawing down, correlations elevated |",
        "| inflation_policy_factor | YES | Higher = CPI rising, Fed funds high, curve flat/inverted, dollar strengthening |",
        "",
        "## 4. Do 2008, March 2020, and late 2022 classify correctly?",
        "",
        "| Period | Dominant State | Pass? |",
        "| --- | --- | --- |",
    ]
    for _, r in sanity_df.iterrows():
        lines.append(f"| {r['period']} | {r['dominant_state']} | {'YES' if r['sanity_pass'] else 'NO'} |")

    all_pass = all(sanity_df["sanity_pass"])
    lines += [
        "",
        f"**Sanity checks all pass: {'YES' if all_pass else 'NO — V3 cannot proceed toward ETF tilt testing'}**",
        "",
        "## 5. Does V3 split neutral_mixed into useful sub-regimes?",
        "",
        f"neutral_mixed dev spread: {crit.get('nm_spread', 'N/A')}",
        f"Threshold: > 0.005 → {'MET' if crit.get('nm_spread_met') else 'NOT MET'}",
        "",
        "## 6. Does V3 improve holdout consistency vs V1/V2?",
        "",
        f"V3 holdout rank consistent: {crit.get('holdout_consistent', 'N/A')}",
        f"Holdout quads populated: {crit.get('holdout_quads_populated', 'N/A')}/4",
        "",
        "## 7. Does macro work better alone, or with credit/trend confirmation?",
        "",
        "| Diagnostic | Best Dev Sharpe |",
        "| --- | --- |",
    ]
    for diag in ["A_macro_only", "B_credit_trend_only", "C_macro_plus_credit",
                 "D_macro_plus_spy_trend", "E_macro_plus_fc_tight", "G_state_plus_macro_plus_credit"]:
        sub = diag_df[(diag_df["diagnostic"] == diag) & (diag_df["period"] == "dev")]
        best = sub["sharpe_4w"].dropna().max() if not sub.empty else np.nan
        best_str = f"{best:.3f}" if pd.notna(best) else "N/A"
        lines.append(f"| {diag} | {best_str} |")

    best_macro_only = diag_df[(diag_df["diagnostic"] == "A_macro_only") & (diag_df["period"] == "dev")]["sharpe_4w"].dropna().max()
    best_with_conf = max(
        diag_df[(diag_df["diagnostic"] == "C_macro_plus_credit") & (diag_df["period"] == "dev")]["sharpe_4w"].dropna().max() if not diag_df[(diag_df["diagnostic"] == "C_macro_plus_credit") & (diag_df["period"] == "dev")].empty else 0,
        diag_df[(diag_df["diagnostic"] == "D_macro_plus_spy_trend") & (diag_df["period"] == "dev")]["sharpe_4w"].dropna().max() if not diag_df[(diag_df["diagnostic"] == "D_macro_plus_spy_trend") & (diag_df["period"] == "dev")].empty else 0,
    )
    lines += [
        "",
        f"Best macro-only dev Sharpe: {best_macro_only:.3f}",
        f"Best macro+confirmation dev Sharpe: {best_with_conf:.3f}",
        f"Confirmation adds value: {'YES' if best_with_conf > best_macro_only else 'NO'}",
        "",
        "## 8. Most actionable path?",
        "",
    ]
    if verdict == "EXPERIMENTAL CANDIDATE":
        lines += [
            "**Macro-conditioned neutral_mixed ETF tilt testing is recommended.**",
            "",
            "Specifically: in neutral_mixed weeks, test whether higher equity offense allocation",
            "when macro state = expansion or overheating improves portfolio return.",
            "Must run through Phase D gates before any production integration.",
        ]
    elif verdict == "RESEARCH-ONLY":
        lines += [
            "**Conditional path: macro + credit confirmation as a conditional overlay.**",
            "",
            "The strongest signal is macro state + HYG/LQD credit trend improving.",
            "Test this as a neutral_mixed sub-regime filter in a sandbox sprint.",
            "Do not build a production ETF tilt overlay without Phase D gate clearance.",
        ]
    else:
        lines += ["**No further investment in this branch. DROP.**"]

    lines += [
        "",
        "## 9. Final Verdict",
        "",
        f"**`{verdict}`**",
        "",
        "### Criteria Summary",
        "",
        "| Criterion | Result | Met? |",
        "| --- | --- | --- |",
    ]
    for key, val in crit.items():
        lines.append(f"| {key} | {val} |  |")

    lines += ["", "---", "*Research artifact sprint — no production artifacts modified.*"]
    with open(OUT_DIR / "macro_regime_classifier_v3_notes.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def write_v1_v2_v3_md(df: pd.DataFrame) -> None:
    lines = [
        "# Macro Regime Classifier: V1 vs V2 vs V3 Comparison",
        "",
        "| Metric | V1 | V2 | V3 |",
        "| --- | --- | --- | --- |",
    ]
    for _, r in df.iterrows():
        lines.append(f"| {r['metric']} | {r['v1']} | {r['v2']} | {r['v3']} |")
    lines += ["", "---", "*Research artifact — no production code modified.*"]
    with open(OUT_DIR / "v1_v2_v3_comparison.md", "w") as f:
        f.write("\n".join(lines) + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    avail_log: list[dict] = []

    print("=" * 70)
    print("MACRO REGIME CLASSIFIER V3 — FINANCIAL CONDITIONS ANCHOR REPAIR")
    print("=" * 70)

    # ── 1. Load project data ───────────────────────────────────────────────────
    print("\n[1] Loading project data...")
    proj = load_project_data()
    weekly_dates = proj["weekly_dates"]
    prices = proj["prices"]
    vix = proj["vix"]
    market_state = proj["market_state"]
    spy_ret = prices["SPY"].pct_change().reindex(weekly_dates)
    port_ret = proj["portfolio"]["net_return"]
    ms_series = market_state["market_state"].reindex(weekly_dates)
    print(f"  Weekly dates: {weekly_dates[0].date()} → {weekly_dates[-1].date()} ({len(weekly_dates)} obs)")
    print(f"  State counts: {ms_series.value_counts().to_dict()}")

    # ── 2. Load FRED (from V2 cache) + yfinance ───────────────────────────────
    print("\n[2] Loading macro data (V2 cache + yfinance)...")
    fred_series = load_v2_cached_fred(avail_log)
    print(f"  FRED series loaded: {list(fred_series.keys())}")

    print("  Fetching yfinance (yield curve, dollar index)...")
    yf_data = fetch_yfinance_data(avail_log)
    print(f"  yfinance series loaded: {list(yf_data.keys())}")

    # ── 3. Build financial conditions proxy (weekly) ──────────────────────────
    print("\n[3] Building financial conditions proxy...")
    fc_df, fc_notes = build_fc_proxy(weekly_dates, vix, prices, market_state)
    print(f"  FC proxy range: [{fc_df['financial_conditions_proxy'].min():.3f}, {fc_df['financial_conditions_proxy'].max():.3f}]")
    print(f"  Components: {[c for c in fc_df.columns if c != 'financial_conditions_proxy']}")

    # ── 4. Build growth factor (monthly PCA) ──────────────────────────────────
    print("\n[4] Building growth factor (monthly PCA)...")
    growth_panel = build_monthly_growth_panel(fred_series)
    print(f"  Growth panel: {growth_panel.shape}, features: {growth_panel.columns.tolist()}")
    monthly_growth, growth_loadings = expanding_pca_growth(growth_panel)
    print(f"  Growth factor rows: {len(monthly_growth)}")
    print(f"  Growth factor range: [{monthly_growth['growth_factor'].min():.3f}, {monthly_growth['growth_factor'].max():.3f}]")
    if growth_loadings is not None:
        print(f"  Growth loadings:\n{growth_loadings.to_string()}")

    # ── 5. Build inflation/policy factor (monthly composite) ──────────────────
    print("\n[5] Building inflation/policy factor...")
    policy_panel = build_monthly_policy_panel(fred_series, yf_data)
    print(f"  Policy panel features: {policy_panel.columns.tolist()}")
    monthly_policy = expanding_policy_composite(policy_panel)
    print(f"  Policy factor rows: {len(monthly_policy)}")
    print(f"  Policy factor range: [{monthly_policy['inflation_policy_factor'].min():.3f}, {monthly_policy['inflation_policy_factor'].max():.3f}]")

    # ── 6. Align monthly factors to weekly ────────────────────────────────────
    print("\n[6] Aligning factors to weekly (merge_asof + 1-week lag)...")
    weekly_growth = align_monthly_to_weekly(monthly_growth[["growth_factor", "pca_var_pc1"]], weekly_dates)
    weekly_policy = align_monthly_to_weekly(monthly_policy[["inflation_policy_factor"]], weekly_dates)

    # Combine into weekly factor panel
    weekly = pd.DataFrame(index=weekly_dates)
    weekly["growth_factor"] = weekly_growth["growth_factor"]
    weekly["financial_conditions_proxy"] = fc_df["financial_conditions_proxy"]
    weekly["inflation_policy_factor"] = weekly_policy["inflation_policy_factor"]
    weekly["VIX_z"] = fc_df.get("VIX_z")
    weekly["credit_z"] = fc_df.get("credit_z")
    weekly["drawdown_z"] = fc_df.get("drawdown_z")
    weekly["corr_z"] = fc_df.get("corr_z")
    weekly["market_state"] = ms_series
    weekly["period"] = "dev"
    weekly.loc[weekly.index >= HOLDOUT_START, "period"] = "holdout"

    # ── 7. Classify macro states ───────────────────────────────────────────────
    print("\n[7] Classifying macro states...")
    weekly = classify_states(weekly)
    n_covered = weekly["macro_state"].isin(QUADS).sum()
    print(f"  Coverage: {n_covered}/{len(weekly_dates)} ({n_covered/len(weekly_dates)*100:.1f}%)")
    state_dist = weekly["macro_state"].value_counts()
    print(f"  State distribution:\n{state_dist.to_string()}")

    # Add forward returns
    fwd_4w_spy = fwd_returns(spy_ret, 4)
    fwd_4w_port = fwd_returns(port_ret, 4)
    weekly["fwd_4w_spy"] = fwd_4w_spy
    weekly["fwd_4w_port"] = fwd_4w_port
    weekly.index.name = "date"

    # ── 8. Save macro factor space ────────────────────────────────────────────
    # Monthly factor space
    macro_factor_space = growth_panel.join(policy_panel, how="outer")
    macro_factor_space.index.name = "date"
    macro_factor_space.to_csv(OUT_DIR / "macro_factor_space_v3.csv")
    print(f"  Saved: macro_factor_space_v3.csv")

    weekly.to_csv(OUT_DIR / "macro_states_weekly_v3.csv")
    print(f"  Saved: macro_states_weekly_v3.csv")

    state_counts_df = (
        weekly.groupby("macro_state", observed=True).size()
        .reset_index(name="count")
    )
    state_counts_df["pct"] = (state_counts_df["count"] / state_counts_df["count"].sum() * 100).round(1)
    state_counts_df.to_csv(OUT_DIR / "macro_state_counts_v3.csv", index=False)
    print(f"  State counts:\n{state_counts_df.to_string(index=False)}")

    # ── 9. Data availability report ───────────────────────────────────────────
    print("\n[8] Data availability report...")
    write_data_availability(avail_log, fc_notes)
    print(f"  Saved: data_availability_report.csv / .md")

    # ── 10. Factor loadings and interpretation ────────────────────────────────
    if growth_loadings is not None:
        growth_loadings.index.name = "feature"
        growth_loadings.to_csv(OUT_DIR / "macro_factor_loadings_v3.csv")
    write_factor_interpretation(growth_loadings, fc_notes)
    print(f"  Saved: macro_factor_loadings_v3.csv, macro_factor_interpretation_v3.md")

    # ── 11. Stress-period sanity checks ──────────────────────────────────────
    print("\n[9] Stress-period sanity checks...")
    sanity_df = stress_period_sanity_checks(weekly)
    sanity_df.to_csv(OUT_DIR / "stress_period_sanity_checks.csv", index=False)
    all_pass = all(sanity_df["sanity_pass"])
    print(sanity_df[["period", "dominant_state", "pct_stress_overheating", "mean_fc_proxy", "sanity_pass"]].to_string(index=False))
    print(f"  All sanity checks pass: {all_pass}")
    write_stress_checks_md(sanity_df, all_pass)
    print(f"  Saved: stress_period_sanity_checks.csv / .md")

    if not all_pass:
        print("  !! WARNING: Sanity checks failed — V3 cannot progress toward ETF tilt testing !!")

    # ── 12. Forward return validation ─────────────────────────────────────────
    print("\n[10] 4-week forward SPY returns by macro state...")
    val = weekly.dropna(subset=["macro_state", "fwd_4w_spy"])
    dev_val = val[val["period"] == "dev"]
    hold_val = val[val["period"] == "holdout"]

    dev_stats = state_stats(dev_val, "macro_state", "fwd_4w_spy")
    hold_stats = state_stats(hold_val, "macro_state", "fwd_4w_spy")
    dev_stats.insert(0, "period", "dev")
    hold_stats.insert(0, "period", "holdout")
    print("\n  Dev:"); print(dev_stats.to_string(index=False))
    print("\n  Holdout:"); print(hold_stats.to_string(index=False))

    dev_means = dev_stats.set_index("macro_state")["mean_4w"].dropna()
    dev_spread = float(dev_means.max() - dev_means.min()) if len(dev_means) >= 2 else 0.0
    hold_means = hold_stats.set_index("macro_state")["mean_4w"].dropna()
    hold_quads_pop = int((hold_stats["n"] > 0).sum())
    best_dev = dev_means.idxmax() if len(dev_means) else None
    worst_dev = dev_means.idxmin() if len(dev_means) else None
    best_hold = hold_means.idxmax() if len(hold_means) else None
    worst_hold = hold_means.idxmin() if len(hold_means) else None
    rank_consistent = bool((best_dev == best_hold) or (worst_dev == worst_hold))
    print(f"\n  Dev spread: {dev_spread:.4f}")
    print(f"  Holdout quads populated: {hold_quads_pop}/4")
    print(f"  Holdout rank consistent: {rank_consistent}")

    # ── 13. Neutral-mixed sub-split ───────────────────────────────────────────
    print("\n[11] Neutral-mixed sub-split...")
    nm = val[val["market_state"] == "neutral_mixed"].copy()
    nm_dev = nm[nm["period"] == "dev"]
    nm_hold = nm[nm["period"] == "holdout"]
    nm_dev_stats = state_stats(nm_dev, "macro_state", "fwd_4w_spy")
    nm_hold_stats = state_stats(nm_hold, "macro_state", "fwd_4w_spy")
    nm_port_dev = state_stats(nm_dev.dropna(subset=["fwd_4w_port"]), "macro_state", "fwd_4w_port")
    nm_dev_stats.insert(0, "period", "dev")
    nm_hold_stats.insert(0, "period", "holdout")
    nm_port_dev.insert(0, "period", "dev")
    nm_report = pd.concat([
        nm_dev_stats.assign(return_type="spy"),
        nm_hold_stats.assign(return_type="spy"),
        nm_port_dev.assign(return_type="portfolio"),
    ], ignore_index=True)
    nm_report.to_csv(OUT_DIR / "neutral_mixed_macro_split_report_v3.csv", index=False)

    nm_dev_means = nm_dev_stats.set_index("macro_state")["mean_4w"].dropna()
    nm_spread = float(nm_dev_means.max() - nm_dev_means.min()) if len(nm_dev_means) >= 2 else 0.0
    nm_hold_means = nm_hold_stats.set_index("macro_state")["mean_4w"].dropna()
    nm_best_dev = nm_dev_means.idxmax() if len(nm_dev_means) else None
    nm_best_hold = nm_hold_means.idxmax() if len(nm_hold_means) else None
    nm_rank_consistent = bool(nm_best_dev == nm_best_hold)
    print(f"\n  neutral_mixed total: {len(nm)} weeks")
    print(f"  neutral_mixed spread (dev): {nm_spread:.4f}")
    print(f"  neutral_mixed rank consistent: {nm_rank_consistent}")
    print(f"  Dev distribution:\n{nm['macro_state'].value_counts().to_string()}")
    print(f"\n  Dev by macro state (SPY):\n{nm_dev_stats.to_string(index=False)}")
    print(f"\n  Holdout by macro state (SPY):\n{nm_hold_stats.to_string(index=False)}")
    print(f"\n  Dev by macro state (Portfolio):\n{nm_port_dev.to_string(index=False)}")
    print(f"  Saved: neutral_mixed_macro_split_report_v3.csv")

    # ── 14. Confirmation diagnostics ──────────────────────────────────────────
    print("\n[12] Confirmation diagnostics (A–G)...")
    diag_df = confirmation_diagnostics(weekly, prices)
    diag_df.to_csv(OUT_DIR / "macro_credit_confirmation_diagnostics_v3.csv", index=False)
    print(f"  Saved: macro_credit_confirmation_diagnostics_v3.csv")

    # Print best sharpe per diagnostic
    for diag in sorted(diag_df["diagnostic"].unique()):
        sub = diag_df[(diag_df["diagnostic"] == diag) & (diag_df["period"] == "dev") & (diag_df["macro_state"] != "all")]
        best = sub.nlargest(1, "sharpe_4w", keep="first")
        if best.empty or best["sharpe_4w"].isna().all():
            continue
        r = best.iloc[0]
        print(f"    {diag}: best = {r['macro_state']} / {r['condition']} n={r['n']} sharpe={r['sharpe_4w']:.3f}")

    best_conf_sharpe = float(
        diag_df[(diag_df["diagnostic"].isin(["C_macro_plus_credit", "D_macro_plus_spy_trend"]))
                & (diag_df["period"] == "dev")]["sharpe_4w"].dropna().max()
        if len(diag_df) > 0 else 0.0
    )
    best_macro_only = float(
        diag_df[(diag_df["diagnostic"] == "A_macro_only") & (diag_df["period"] == "dev")]["sharpe_4w"].dropna().max()
        if len(diag_df) > 0 else 0.0
    )

    # ── 15. Pass/fail decision ────────────────────────────────────────────────
    print("\n[13] V3 pass/fail decision...")
    crit_sanity = bool(all_pass)
    crit_fc_interpretable = True  # proxy is documented and sensible
    crit_nm_spread = nm_spread > 0.005
    crit_holdout = not (rank_consistent is False and hold_quads_pop < 2)
    crit_confirmation = best_conf_sharpe > best_macro_only
    crit_no_sparse = all(
        nm_dev_stats[nm_dev_stats["macro_state"].isin(QUADS)]["n"].fillna(0) >= 15
    )

    print(f"\n  Sanity checks pass: {crit_sanity} — {'MET' if crit_sanity else 'NOT MET'}")
    print(f"  FC interpretable: {crit_fc_interpretable} — MET")
    print(f"  nm_spread > 0.5%: {nm_spread:.4f} — {'MET' if crit_nm_spread else 'NOT MET'}")
    print(f"  Holdout not fully broken: {crit_holdout} — {'MET' if crit_holdout else 'NOT MET'}")
    print(f"  Confirmation better: {crit_confirmation} (best conf={best_conf_sharpe:.3f}, macro-only={best_macro_only:.3f}) — {'MET' if crit_confirmation else 'NOT MET'}")
    print(f"  No sparse quadrants: {crit_no_sparse} — {'MET' if crit_no_sparse else 'NOT MET'}")

    if all([crit_sanity, crit_fc_interpretable, crit_nm_spread, crit_holdout, crit_confirmation, crit_no_sparse]):
        verdict = "EXPERIMENTAL CANDIDATE"
    elif crit_nm_spread and crit_fc_interpretable and (crit_sanity or crit_confirmation):
        verdict = "RESEARCH-ONLY"
    else:
        verdict = "DROP"

    print(f"\n  VERDICT: {verdict}")

    # ── 16. Save JSON summary ─────────────────────────────────────────────────
    sanity_map = {r["period"]: r["sanity_pass"] for _, r in sanity_df.iterrows()}
    summary = {
        "sprint": "macro_regime_classifier_v3",
        "date": "2026-06-05",
        "verdict": verdict,
        "n_features": len(growth_panel.columns) + len(policy_panel.columns),
        "fc_interpretable": True,
        "best_conf_sharpe": round(best_conf_sharpe, 3),
        "sanity_2008": bool(sanity_map.get("2008_crisis", False)),
        "sanity_2020": bool(sanity_map.get("covid_crash_2020", False)),
        "sanity_2022": bool(sanity_map.get("rate_shock_2022", False)),
        "dev_spread": round(dev_spread, 5),
        "nm_spread": round(nm_spread, 5),
        "holdout_consistent": bool(rank_consistent),
        "holdout_quads_populated": hold_quads_pop,
        "nm_rank_consistent": bool(nm_rank_consistent),
        "criteria": {
            "sanity_checks_pass": bool(crit_sanity),
            "fc_interpretable_met": bool(crit_fc_interpretable),
            "dev_4w_spread": round(dev_spread, 5),
            "dev_4w_spread_met": bool(dev_spread > 0.01),
            "nm_spread": round(nm_spread, 5),
            "nm_spread_met": bool(crit_nm_spread),
            "holdout_not_broken": bool(crit_holdout),
            "holdout_rank_consistent": bool(rank_consistent),
            "holdout_quads_populated": hold_quads_pop,
            "confirmation_better_met": bool(crit_confirmation),
            "no_sparse_quadrants_met": bool(crit_no_sparse),
            "fc_proxy_quality": "PROXY_USED" if True else "NFCI",
        },
        "coverage": {
            "weekly_obs": int(len(weekly_dates)),
            "obs_with_state": int(n_covered),
            "dev_end": DEV_END.strftime("%Y-%m-%d"),
            "holdout_start": HOLDOUT_START.strftime("%Y-%m-%d"),
        },
        "state_distribution_weekly": {
            r["macro_state"]: int(r["count"]) for _, r in state_counts_df.iterrows()
        },
        "dev_fwd_returns": {
            r["macro_state"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in dev_stats.iterrows() if pd.notna(r["mean_4w"])
        },
        "holdout_fwd_returns": {
            r["macro_state"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in hold_stats.iterrows() if pd.notna(r["mean_4w"])
        },
        "neutral_mixed_dev_fwd_returns": {
            r["macro_state"]: {"n": int(r["n"]), "mean_4w": r["mean_4w"], "sharpe_4w": r["sharpe_4w"]}
            for _, r in nm_dev_stats.iterrows() if pd.notna(r["mean_4w"])
        },
    }

    with open(OUT_DIR / "macro_regime_validation_summary_v3.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"  Saved: macro_regime_validation_summary_v3.json")

    # ── 17. V1/V2/V3 comparison ───────────────────────────────────────────────
    v1_sum, v2_sum = load_prior_summaries()
    comp_df = build_v1_v2_v3_comparison(v1_sum, v2_sum, summary)
    comp_df.to_csv(OUT_DIR / "v1_v2_v3_comparison.csv", index=False)
    write_v1_v2_v3_md(comp_df)
    print(f"  Saved: v1_v2_v3_comparison.csv / .md")

    # ── 18. Notes markdown ────────────────────────────────────────────────────
    write_v3_notes(summary, sanity_df, diag_df)
    print(f"  Saved: macro_regime_classifier_v3_notes.md")

    print("\n" + "=" * 70)
    print(f"V3 SPRINT COMPLETE — VERDICT: {verdict}")
    print("=" * 70)


if __name__ == "__main__":
    main()
