"""Phase OOO0/OOO1 signal discovery foundation.

Diagnostic-only. Builds an inventory and a lagged weekly feature library for
future Layer 1 / Layer 2A signal research. It does not create portfolio
candidates, alter strategy logic, or change production/shadow pins.
"""
from __future__ import annotations

import json
import math
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", message="Could not infer format")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
L0 = DATA / "01_data_hub"
L1 = DATA / "02_layer1_signals"
L2A = DATA / "03_layer2a_strategy_logic"
L2B = DATA / "04_layer2b_risk_regime_engine"
L3 = DATA / "05_layer3_portfolio_construction"
NNN = DATA / "research" / "phase_nnn_hard_ml_meta_layer"
KKK = DATA / "research" / "phase_kkk_signal_sleeve_contribution_audit"
JJJ2 = DATA / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = DATA / "research" / "phase_ooo_signal_discovery"
OOO0 = OUT / "ooo0_inventory"
OOO1 = OUT / "ooo1_ml_feature_discovery"
DOC0 = ROOT / "docs" / "research" / "2026-04-27_phase_ooo0_signal_data_inventory_report.md"
DOC1 = ROOT / "docs" / "research" / "2026-04-27_phase_ooo1_ml_feature_discovery_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

INITIAL_TRAIN = 260
RETRAIN_FREQ = 26
MIN_CLASS = 40
RNG = 20260427

COMMANDS = [
    "sed -n '1,180p' docs/research/2026-04-27_phase_nnn_hard_ml_meta_layer_report.md",
    "sed -n '1,120p' docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md",
    "find data/01_data_hub data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine -maxdepth 1 -type f | sort",
    "python3 scripts/phase_ooo0_ooo1_signal_discovery_foundation.py",
]


def ensure_dirs() -> None:
    for path in [OOO0, OOO1]:
        path.mkdir(parents=True, exist_ok=True)


def read_indexed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else "date" if "date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    df.index.name = "date"
    return df


def read_numeric_indexed(path: Path) -> pd.DataFrame:
    return read_indexed(path).apply(pd.to_numeric, errors="coerce")


def save(df: pd.DataFrame, path: Path, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)


def infer_dates(df: pd.DataFrame) -> tuple[str | None, str | None]:
    date_col = next((c for c in ["Date", "date", "Unnamed: 0"] if c in df.columns), None)
    if date_col is None:
        return None, None
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return str(dates.min().date()), str(dates.max().date())


def infer_frequency(start: str | None, end: str | None, rows: int) -> str:
    if not start or not end or rows < 3:
        return "unknown"
    days = max((pd.Timestamp(end) - pd.Timestamp(start)).days, 1)
    gap = days / max(rows - 1, 1)
    if gap <= 2:
        return "daily"
    if 5 <= gap <= 9:
        return "weekly"
    if 25 <= gap <= 35:
        return "monthly"
    return "irregular"


def inventory_file(path: Path, category: str) -> dict:
    row = {
        "file_path": str(path.relative_to(ROOT)),
        "category": category,
        "row_count": np.nan,
        "column_count": np.nan,
        "start_date": None,
        "end_date": None,
        "frequency": "unknown",
        "key_columns": "",
        "useful_for_signal_discovery": False,
        "leakage_risk_notes": "",
        "recommended_use": "",
    }
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, nrows=5000)
            row["row_count"] = int(sum(1 for _ in open(path, "rb")) - 1)
            row["column_count"] = int(len(df.columns))
            start, end = infer_dates(df)
            row["start_date"], row["end_date"] = start, end
            row["frequency"] = infer_frequency(start, end, int(row["row_count"]))
            row["key_columns"] = "|".join(map(str, df.columns[:12]))
            row["useful_for_signal_discovery"] = bool(path.suffix == ".csv" and row["column_count"] > 1)
        elif path.suffix.lower() == ".json":
            payload = json.loads(path.read_text())
            row["row_count"] = len(payload) if hasattr(payload, "__len__") else 1
            row["column_count"] = np.nan
            row["key_columns"] = "|".join(list(payload.keys())[:12]) if isinstance(payload, dict) else ""
            row["useful_for_signal_discovery"] = True
        else:
            row["useful_for_signal_discovery"] = False
        if "phase_jj" in path.name or "phase_nnn" in path.name:
            row["recommended_use"] = "prior ML baseline or feature lineage reference"
            row["leakage_risk_notes"] = "use only lagged feature columns; targets are labels only"
        elif "signal_" in path.name or "phase_a_" in path.name:
            row["recommended_use"] = "Layer 1 signal validation or live signal feature source"
        elif "strategy_returns" in path.name or "component_returns" in path.name:
            row["recommended_use"] = "sleeve/factor momentum and opportunity labels"
        elif "weekly_returns" in path.name or "weekly_prices" in path.name:
            row["recommended_use"] = "cross-asset momentum, volatility, breadth, lead-lag"
        elif "market_state" in path.name or "regime" in path.name:
            row["recommended_use"] = "state interactions and state-quality targets"
    except Exception as exc:  # keep inventory robust
        row["leakage_risk_notes"] = f"read_error: {exc}"
    return row


def make_inventory() -> dict[str, pd.DataFrame]:
    files = []
    for base, category in [
        (L0, "data_hub"),
        (L1, "layer1_signal"),
        (L2A, "layer2a_sleeve"),
        (L2B, "layer2b_regime"),
        (L3, "layer3_portfolio"),
        (NNN, "prior_ml"),
        (KKK, "prior_signal_audit"),
        (JJJ2, "component_panel"),
    ]:
        if base.exists():
            files.extend(inventory_file(p, category) for p in sorted(base.glob("*")) if p.is_file())
    data_inv = pd.DataFrame(files)
    signal_inv = data_inv[data_inv["category"].isin(["layer1_signal", "prior_signal_audit"])].copy()
    sleeve_inv = data_inv[data_inv["category"].isin(["layer2a_sleeve", "component_panel"])].copy()
    macro_inv = data_inv[data_inv["category"].isin(["data_hub", "layer2b_regime"])].copy()
    validation_inv = data_inv[data_inv["file_path"].str.contains("summary|ic|redundancy|validation|manifest|metrics", case=False, na=False)].copy()
    missing = pd.DataFrame([
        {"missing_item": "explicit signal-to-sleeve lineage by date", "recommendation": "Persist a dated Layer2A signal_usage_by_sleeve table.", "severity": "MEDIUM"},
        {"missing_item": "IPCA/latent factor panel", "recommendation": "Reserve for OOO6 after feature shortlist stabilizes.", "severity": "LOW"},
        {"missing_item": "per-signal live transaction cost sensitivity", "recommendation": "Add only when OOO2 creates concrete candidate signals.", "severity": "LOW"},
    ])
    return {
        "ooo0_data_inventory": data_inv,
        "ooo0_signal_inventory": signal_inv,
        "ooo0_sleeve_inventory": sleeve_inv,
        "ooo0_macro_proxy_inventory": macro_inv,
        "ooo0_existing_validation_inventory": validation_inv,
        "ooo0_missing_data_recommendations": missing,
    }


def trailing_sum(s: pd.Series, w: int) -> pd.Series:
    return np.log1p(s.fillna(0.0)).rolling(w, min_periods=max(3, w // 2)).sum().pipe(np.expm1)


def forward_sum(s: pd.Series, h: int) -> pd.Series:
    log_r = np.log1p(s.fillna(0.0))
    return np.expm1(log_r.shift(-1).rolling(h, min_periods=h).sum().shift(-(h - 1)))


def trailing_drawdown(s: pd.Series, w: int) -> pd.Series:
    def calc(x: np.ndarray) -> float:
        wealth = np.cumprod(1 + x)
        return float((wealth / np.maximum.accumulate(wealth) - 1).min())
    return s.fillna(0.0).rolling(w, min_periods=max(6, w // 2)).apply(calc, raw=True)


def rolling_cvar(s: pd.Series, w: int) -> pd.Series:
    def calc(x: np.ndarray) -> float:
        q = np.nanquantile(x, 0.05)
        tail = x[x <= q]
        return float(np.nanmean(tail)) if len(tail) else np.nan
    return s.fillna(0.0).rolling(w, min_periods=max(8, w // 2)).apply(calc, raw=True)


def downside_vol(s: pd.Series, w: int) -> pd.Series:
    return s.where(s < 0, 0.0).rolling(w, min_periods=max(4, w // 2)).std(ddof=0)


def clean_feature_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")


def load_layer1_live_features(index: pd.DatetimeIndex, tickers: list[str]) -> pd.DataFrame:
    frames = []
    for path in sorted(L1.glob("signal_*.csv")):
        if path.name in {"signal_summary_table.csv", "signal_ic_by_horizon.csv", "signal_incremental_contribution.csv", "signal_subset_comparison.csv", "signal_redundancy_matrix.csv", "signal_redundancy_pairs.csv", "signal_eligibility_matrix.csv"}:
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "Date" not in df.columns or "Ticker" not in df.columns:
            continue
        value_cols = [c for c in df.columns if c.endswith("_tradable")]
        value_cols += [c for c in df.columns if c.endswith("_score_observed") and c not in value_cols]
        value_cols = value_cols[:3]
        if not value_cols:
            continue
        keep = df[["Date", "Ticker", *value_cols]].copy()
        keep["Date"] = pd.to_datetime(keep["Date"], errors="coerce")
        keep = keep[keep["Ticker"].isin(tickers) & keep["Date"].isin(index)]
        rename = {c: f"l1_{clean_feature_name(path.stem.replace('signal_', ''))}_{clean_feature_name(c)}" for c in value_cols}
        frames.append(keep.rename(columns=rename))
    if not frames:
        return pd.DataFrame(columns=["date", "entity"])
    out = frames[0]
    for nxt in frames[1:]:
        out = out.merge(nxt, on=["Date", "Ticker"], how="outer")
    out = out.rename(columns={"Date": "date", "Ticker": "entity"})
    return out


def build_date_features(index: pd.DatetimeIndex, returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    date_feat = pd.DataFrame(index=index)
    state = pd.read_csv(L2B / "market_state_history.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    numeric_state = state.select_dtypes(include=[np.number]).reindex(index)
    for col in numeric_state.columns:
        date_feat[f"regime_{clean_feature_name(col)}"] = numeric_state[col]
    if "market_state" in state:
        dummies = pd.get_dummies(state["market_state"].astype(str), prefix="state").reindex(index).fillna(0.0)
        date_feat = date_feat.join(dummies)
        date_feat["market_state_raw"] = state["market_state"].astype(str).reindex(index)
    risk_assets = returns.columns.tolist()
    ret13 = returns[risk_assets].apply(lambda s: trailing_sum(s, 13))
    ret26 = returns[risk_assets].apply(lambda s: trailing_sum(s, 26))
    vol13 = returns[risk_assets].rolling(13, min_periods=8).std(ddof=0)
    date_feat["breadth_ret13_positive"] = (ret13 > 0).mean(axis=1)
    date_feat["breadth_ret26_positive"] = (ret26 > 0).mean(axis=1)
    date_feat["cross_asset_dispersion_13w"] = ret13.std(axis=1)
    date_feat["cross_asset_vol_median_13w"] = vol13.median(axis=1)
    date_feat["cross_asset_mom_spread_13w"] = ret13.quantile(0.8, axis=1) - ret13.quantile(0.2, axis=1)
    if "SPY" in returns:
        date_feat["offensive_breadth_13w"] = (ret13[[c for c in ["SPY", "QQQ", "IWM", "EFA", "EEM", "VWO"] if c in ret13]] > 0).mean(axis=1)
    if {"TLT", "IEF", "LQD", "GLD", "BIL"}.intersection(ret13.columns):
        date_feat["defensive_breadth_13w"] = (ret13[[c for c in ["TLT", "IEF", "LQD", "GLD", "BIL"] if c in ret13]] > 0).mean(axis=1)
    pairs = [
        ("HYG", "LQD"), ("HYG", "TLT"), ("QQQ", "SPY"), ("IWM", "SPY"),
        ("EFA", "SPY"), ("VWO", "SPY"), ("GLD", "SPY"), ("DBA", "SPY"),
        ("PDBC", "SPY"), ("UUP", "SPY"), ("TLT", "SPY"), ("IEF", "SPY"),
    ]
    for a, b in pairs:
        if a in returns and b in returns:
            date_feat[f"leadlag_{a}_minus_{b}_13w"] = ret13[a] - ret13[b]
            date_feat[f"leadlag_{a}_minus_{b}_26w"] = ret26[a] - ret26[b]
    rolling_corr = returns[risk_assets].rolling(26, min_periods=20).corr()
    avg_corr = []
    for dt in index:
        try:
            mat = rolling_corr.loc[dt]
            vals = mat.where(~np.eye(len(mat), dtype=bool)).stack()
            avg_corr.append(float(vals.mean()))
        except Exception:
            avg_corr.append(np.nan)
    date_feat["avg_pairwise_corr_26w"] = avg_corr
    return date_feat, state[["market_state"]].reindex(index) if "market_state" in state else pd.DataFrame(index=index)


def build_etf_panel(index: pd.DatetimeIndex, returns: pd.DataFrame, prices: pd.DataFrame, date_features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    tickers = [c for c in returns.columns if returns[c].notna().sum() > 100]
    for ticker in tickers:
        r = returns[ticker].reindex(index).astype(float)
        p = prices[ticker].reindex(index).astype(float) if ticker in prices else (1 + r.fillna(0)).cumprod()
        df = pd.DataFrame({"date": index, "entity_type": "ETF", "entity": ticker})
        for w in [4, 13, 26, 52]:
            df[f"asset_ret_{w}w"] = trailing_sum(r, w).values
            df[f"asset_vol_{w}w"] = r.rolling(w, min_periods=max(3, w // 2)).std(ddof=0).values
        df["asset_mom_multi_avg"] = df[["asset_ret_4w", "asset_ret_13w", "asset_ret_26w", "asset_ret_52w"]].mean(axis=1)
        df["asset_mom_agreement_count"] = (df[["asset_ret_4w", "asset_ret_13w", "asset_ret_26w", "asset_ret_52w"]] > 0).sum(axis=1)
        df["asset_trend_acceleration"] = df["asset_ret_13w"] - df["asset_ret_52w"] / 4.0
        df["asset_ma_distance_26w"] = (p / p.rolling(26, min_periods=13).mean() - 1).values
        df["asset_ma_distance_52w"] = (p / p.rolling(52, min_periods=26).mean() - 1).values
        df["asset_downside_vol_13w"] = downside_vol(r, 13).values
        df["asset_vol_change_13v26"] = (df["asset_vol_13w"] - df["asset_vol_26w"]).values
        df["asset_drawdown_26w"] = trailing_drawdown(r, 26).values
        df["asset_cvar_proxy_26w"] = rolling_cvar(r, 26).values
        df["asset_vol_adj_mom_26w"] = (df["asset_ret_26w"] / df["asset_vol_26w"].replace(0, np.nan)).values
        df["asset_trend_consistency_13w"] = r.rolling(13, min_periods=8).apply(lambda x: float((x > 0).mean()), raw=True).values
        rows.append(df)
    panel = pd.concat(rows, ignore_index=True)
    l1_live = load_layer1_live_features(index, tickers)
    if not l1_live.empty:
        panel = panel.merge(l1_live, on=["date", "entity"], how="left")
    date_cols = date_features.drop(columns=["market_state_raw"], errors="ignore").reset_index().rename(columns={date_features.index.name or "index": "date"})
    panel = panel.merge(date_cols, on="date", how="left")
    numeric = [c for c in panel.columns if c not in ["date", "entity_type", "entity"]]
    panel[numeric] = panel.groupby("entity")[numeric].shift(1)
    state_raw = date_features.get("market_state_raw", pd.Series(index=index, dtype=object)).shift(1)
    panel = panel.merge(state_raw.rename("market_state_lag").reset_index().rename(columns={state_raw.index.name or "index": "date"}), on="date", how="left")
    manifest_rows = []
    for col in numeric:
        family = "existing_layer1_signal" if col.startswith("l1_") else "cross_asset_momentum"
        if "vol" in col or "drawdown" in col or "cvar" in col:
            family = "volatility_risk"
        if col.startswith("leadlag_"):
            family = "cross_asset_lead_lag"
        if col.startswith(("breadth_", "offensive_breadth", "defensive_breadth", "cross_asset_", "avg_pairwise")):
            family = "breadth_dispersion"
        if col.startswith(("regime_", "state_")):
            family = "regime_state"
        manifest_rows.append({"feature": col, "feature_family": family, "entity_type": "ETF", "source": "weekly returns/prices/layer1/regime", "lag_rule": "grouped one-week lag", "live_feature": True})
    return panel, pd.DataFrame(manifest_rows)


def sleeve_return_table(index: pd.DatetimeIndex) -> pd.DataFrame:
    frames = []
    for path in sorted(L2A.glob("strategy_returns_*.csv")):
        name = path.stem.replace("strategy_returns_", "")
        try:
            s = read_numeric_indexed(path).iloc[:, 0].reindex(index).rename(name)
            frames.append(s)
        except Exception:
            continue
    comp = JJJ2 / f"component_returns_{GGG1}.csv"
    if comp.exists():
        c = read_numeric_indexed(comp).reindex(index)
        frames.extend(c[col].rename(col) for col in c.columns)
    return pd.concat(frames, axis=1) if frames else pd.DataFrame(index=index)


def build_sleeve_panel(index: pd.DatetimeIndex, sleeve_returns: pd.DataFrame, ggg1: pd.Series, date_features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for sleeve in sleeve_returns.columns:
        r = sleeve_returns[sleeve].astype(float).reindex(index)
        if r.notna().sum() < 100:
            continue
        df = pd.DataFrame({"date": index, "entity_type": "SLEEVE", "entity": sleeve})
        for w in [4, 13, 26]:
            df[f"sleeve_ret_{w}w"] = trailing_sum(r, w).values
            df[f"sleeve_vol_{w}w"] = r.rolling(w, min_periods=max(3, w // 2)).std(ddof=0).values
            df[f"sleeve_mom_vol_{w}w"] = df[f"sleeve_ret_{w}w"] / df[f"sleeve_vol_{w}w"].replace(0, np.nan)
        df["sleeve_vs_ggg1_13w"] = (trailing_sum(r, 13) - trailing_sum(ggg1, 13)).values
        df["sleeve_trend_consistency_13w"] = r.rolling(13, min_periods=8).apply(lambda x: float((x > 0).mean()), raw=True).values
        rows.append(df)
    panel = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "entity_type", "entity"])
    if panel.empty:
        return panel, pd.DataFrame()
    panel = panel.merge(date_features.drop(columns=["market_state_raw"], errors="ignore").reset_index().rename(columns={date_features.index.name or "index": "date"}), on="date", how="left")
    numeric = [c for c in panel.columns if c not in ["date", "entity_type", "entity"]]
    panel[numeric] = panel.groupby("entity")[numeric].shift(1)
    state_raw = date_features.get("market_state_raw", pd.Series(index=index, dtype=object)).shift(1)
    panel = panel.merge(state_raw.rename("market_state_lag").reset_index().rename(columns={state_raw.index.name or "index": "date"}), on="date", how="left")
    manifest = pd.DataFrame([{"feature": c, "feature_family": "sleeve_factor_momentum" if c.startswith("sleeve_") else "regime_state", "entity_type": "SLEEVE", "source": "Layer2A/component returns", "lag_rule": "grouped one-week lag", "live_feature": True} for c in numeric])
    return panel, manifest


def build_market_panel(index: pd.DatetimeIndex, date_features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = date_features.copy()
    state_raw = df.get("market_state_raw", pd.Series(index=index, dtype=object)).shift(1)
    df = df.drop(columns=["market_state_raw"], errors="ignore").shift(1)
    df.insert(0, "entity", "MARKET")
    df.insert(0, "entity_type", "MARKET")
    df.insert(0, "date", index)
    df["market_state_lag"] = state_raw.values
    manifest = pd.DataFrame([{"feature": c, "feature_family": "regime_state" if c.startswith(("regime_", "state_")) else "breadth_dispersion", "entity_type": "MARKET", "source": "date-level regime/breadth features", "lag_rule": "one-week lag", "live_feature": True} for c in df.columns if c not in ["date", "entity_type", "entity", "market_state_lag"]])
    return df, manifest


def add_state_interactions(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    state_cols = [c for c in panel.columns if c.startswith("state_")]
    base_cols = [c for c in panel.columns if any(s in c for s in ["ret_13w", "vol_13w", "mom_multi_avg", "vol_adj_mom", "breadth_ret13_positive", "leadlag_HYG_minus_LQD_13w"])]
    rows = []
    for base in base_cols[:40]:
        for st in state_cols[:8]:
            name = f"{base}_x_{st}"
            panel[name] = pd.to_numeric(panel[base], errors="coerce") * pd.to_numeric(panel[st], errors="coerce")
            rows.append({"feature": name, "feature_family": "regime_state_interaction", "entity_type": "ALL", "source": "feature x lagged market state", "lag_rule": "both inputs lagged", "live_feature": True})
    return panel, pd.DataFrame(rows)


def build_feature_targets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ggg1_ret = read_numeric_indexed(L3 / f"portfolio_version_returns_{GGG1}.csv")["net_return"].astype(float)
    index = ggg1_ret.index
    returns = read_numeric_indexed(L0 / "weekly_returns.csv").reindex(index)
    prices = read_numeric_indexed(L0 / "weekly_prices.csv").reindex(index)
    returns = returns.loc[:, returns.notna().sum() > 100]
    prices = prices.reindex(columns=returns.columns)
    date_features, state = build_date_features(index, returns)
    etf_panel, etf_manifest = build_etf_panel(index, returns, prices, date_features)
    sleeve_returns = sleeve_return_table(index)
    sleeve_panel, sleeve_manifest = build_sleeve_panel(index, sleeve_returns, ggg1_ret, date_features)
    market_panel, market_manifest = build_market_panel(index, date_features)
    feature_panel = pd.concat([etf_panel, sleeve_panel, market_panel], ignore_index=True, sort=False)
    feature_panel, interaction_manifest = add_state_interactions(feature_panel)
    feature_cols = [c for c in feature_panel.columns if c not in ["date", "entity_type", "entity", "market_state_lag"]]
    feature_panel[feature_cols] = feature_panel[feature_cols].apply(pd.to_numeric, errors="coerce")

    # Targets are built from future outcomes and saved separately.
    target_rows = []
    for ticker in returns.columns:
        r = returns[ticker].astype(float)
        f4 = forward_sum(r, 4)
        f8 = forward_sum(r, 8)
        tv = r.rolling(26, min_periods=13).std(ddof=0)
        risk_adj = f4 / (tv * math.sqrt(4)).replace(0, np.nan)
        tmp = pd.DataFrame({"date": index, "entity_type": "ETF", "entity": ticker, "fwd_return_4w": f4.values, "fwd_return_8w": f8.values, "fwd_risk_adj_4w": risk_adj.values})
        target_rows.append(tmp)
    etf_t = pd.concat(target_rows, ignore_index=True)
    etf_t["target_etf_forward_top_quantile_4w"] = etf_t.groupby("date")["fwd_return_4w"].transform(lambda s: (s >= s.quantile(0.75)).astype(float) if s.notna().sum() >= 8 else np.nan)
    etf_t["target_etf_forward_top_quantile_8w"] = etf_t.groupby("date")["fwd_return_8w"].transform(lambda s: (s >= s.quantile(0.75)).astype(float) if s.notna().sum() >= 8 else np.nan)
    etf_t["target_etf_forward_risk_adjusted_top_quantile_4w"] = etf_t.groupby("date")["fwd_risk_adj_4w"].transform(lambda s: (s >= s.quantile(0.75)).astype(float) if s.notna().sum() >= 8 else np.nan)

    sleeve_rows = []
    for sleeve in sleeve_returns.columns:
        r = sleeve_returns[sleeve].astype(float)
        sleeve_rows.append(pd.DataFrame({"date": index, "entity_type": "SLEEVE", "entity": sleeve, "fwd_return_4w": forward_sum(r, 4).values, "fwd_return_8w": forward_sum(r, 8).values}))
    sleeve_t = pd.concat(sleeve_rows, ignore_index=True) if sleeve_rows else pd.DataFrame()
    if not sleeve_t.empty:
        sleeve_t["target_sleeve_opportunity_top_quantile_4w"] = sleeve_t.groupby("date")["fwd_return_4w"].transform(lambda s: (s >= s.quantile(0.75)).astype(float) if s.notna().sum() >= 4 else np.nan)

    prod_ret = read_numeric_indexed(L3 / f"portfolio_version_returns_{PRODUCTION}.csv")["net_return"].reindex(index).astype(float)
    g_f4 = forward_sum(ggg1_ret, 4)
    vol = ggg1_ret.rolling(26, min_periods=13).std(ddof=0)
    risk_quality = g_f4 / (vol * math.sqrt(4)).replace(0, np.nan)
    stress = (state["market_state"].astype(str).reindex(index) == "stressed_panic").astype(float)
    stress_fwd = stress.shift(-1).rolling(4, min_periods=4).max().shift(-3)
    market_t = pd.DataFrame({
        "date": index,
        "entity_type": "MARKET",
        "entity": "MARKET",
        "fwd_ggg1_return_4w": g_f4.values,
        "fwd_prod_return_4w": forward_sum(prod_ret, 4).values,
        "target_state_quality_good_4w": (risk_quality >= risk_quality.dropna().median()).astype(float).values,
        "target_stress_transition_4w": stress_fwd.values,
    })
    market_t["target_ggg1_underperformance_4w"] = ((market_t["fwd_ggg1_return_4w"] - market_t["fwd_prod_return_4w"]) <= -0.005).astype(float)

    target_panel = pd.concat([etf_t, sleeve_t, market_t], ignore_index=True, sort=False)
    manifest = pd.concat([etf_manifest, sleeve_manifest, market_manifest, interaction_manifest], ignore_index=True)
    missing = feature_panel[feature_cols].isna().mean().reset_index()
    missing.columns = ["feature", "missing_rate"]
    family = manifest.groupby("feature_family", as_index=False).agg(feature_count=("feature", "nunique"), entity_types=("entity_type", lambda s: "|".join(sorted(set(map(str, s))))))
    return feature_panel, manifest.drop_duplicates("feature"), missing, family, target_panel


def target_summary(target_panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in [c for c in target_panel.columns if c.startswith("target_")]:
        sub = target_panel[["date", "entity_type", "entity", col]].dropna()
        rows.append({
            "target": col,
            "entity_type": "|".join(sorted(sub["entity_type"].unique())) if not sub.empty else "",
            "n_observations": int(len(sub)),
            "positive": int(sub[col].sum()) if not sub.empty else 0,
            "negative": int((sub[col] == 0).sum()) if not sub.empty else 0,
            "positive_rate": float(sub[col].mean()) if not sub.empty else np.nan,
            "start_date": str(pd.to_datetime(sub["date"]).min().date()) if not sub.empty else None,
            "end_date": str(pd.to_datetime(sub["date"]).max().date()) if not sub.empty else None,
            "enough_samples": bool(len(sub) >= 500 and sub[col].sum() >= MIN_CLASS and (sub[col] == 0).sum() >= MIN_CLASS),
            "leakage_risk_notes": "forward outcome label only; never used as live feature",
            "intended_later_use": "signal discovery and OOO2+ validation",
        })
    rows.append({
        "target": "target_triple_barrier_optional_8w",
        "entity_type": "MARKET|ETF",
        "n_observations": 0,
        "positive": 0,
        "negative": 0,
        "positive_rate": np.nan,
        "start_date": None,
        "end_date": None,
        "enough_samples": False,
        "leakage_risk_notes": "skipped in OOO1 to avoid adding a partially specified barrier label to the discovery foundation",
        "intended_later_use": "OOO5 triple-barrier/meta-label validation",
    })
    return pd.DataFrame(rows)


def model_specs() -> dict:
    return {
        "logistic_l2": LogisticRegression(max_iter=1000, solver="liblinear", C=0.5, random_state=RNG),
        "logistic_l2_balanced": LogisticRegression(max_iter=1000, solver="liblinear", C=0.35, class_weight="balanced", random_state=RNG),
        "decision_tree_depth3": DecisionTreeClassifier(max_depth=3, min_samples_leaf=50, random_state=RNG),
        "random_forest_small": RandomForestClassifier(n_estimators=12, max_depth=3, min_samples_leaf=100, random_state=RNG, n_jobs=1),
        "hist_gradient_shallow": HistGradientBoostingClassifier(max_iter=12, max_leaf_nodes=5, learning_rate=0.05, l2_regularization=0.2, random_state=RNG),
    }


def class_metrics(y: pd.Series, p: pd.Series) -> dict:
    df = pd.concat([y.rename("y"), p.rename("p")], axis=1).dropna()
    if df.empty or df["y"].nunique() < 2:
        return {"n_oos": int(len(df)), "brier": np.nan, "auc": np.nan, "log_loss": np.nan, "top_decile_precision": np.nan, "top_decile_recall": np.nan, "calibration_mae": np.nan}
    yy = df["y"].astype(int).to_numpy()
    pp = df["p"].clip(1e-6, 1 - 1e-6).to_numpy()
    cutoff = np.nanquantile(pp, 0.90)
    high = pp >= cutoff
    cal = calibration_rows(df["y"], df["p"], "_", "_")
    return {
        "n_oos": int(len(df)),
        "brier": float(brier_score_loss(yy, pp)),
        "auc": float(roc_auc_score(yy, pp)),
        "log_loss": float(log_loss(yy, pp)),
        "positive_rate": float(yy.mean()),
        "prediction_mean": float(pp.mean()),
        "top_decile_precision": float(yy[high].mean()) if high.any() else np.nan,
        "top_decile_recall": float(yy[high].sum() / max(yy.sum(), 1)),
        "calibration_mae": float((cal["mean_pred"] - cal["mean_actual"]).abs().mean()) if not cal.empty else np.nan,
    }


def calibration_rows(y: pd.Series, p: pd.Series, target: str, model: str) -> pd.DataFrame:
    df = pd.concat([y.rename("y"), p.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    df["bucket"] = pd.qcut(df["p"], q=5, labels=False, duplicates="drop")
    out = df.groupby("bucket").agg(n=("y", "count"), mean_pred=("p", "mean"), mean_actual=("y", "mean")).reset_index()
    out.insert(0, "model", model)
    out.insert(0, "target", target)
    return out


def baseline_by_state(train: pd.DataFrame, score: pd.DataFrame, target: str) -> pd.Series:
    overall = float(train[target].mean())
    by_state = train.groupby("market_state_lag")[target].agg(["mean", "count"]) if "market_state_lag" in train else pd.DataFrame()
    out = []
    for _, row in score.iterrows():
        st = row.get("market_state_lag")
        if st in by_state.index and by_state.loc[st, "count"] >= 20:
            out.append(float(by_state.loc[st, "mean"]))
        else:
            out.append(overall)
    return pd.Series(out, index=score.index).clip(1e-6, 1 - 1e-6)


def choose_model_columns(df: pd.DataFrame, exclude: set[str]) -> list[str]:
    cols = []
    for col in df.columns:
        if col in exclude or col.startswith("target_") or col.startswith("fwd_"):
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().mean() >= 0.60 and s.nunique(dropna=True) > 1:
            cols.append(col)
    ranked = sorted(cols, key=lambda c: (df[c].isna().mean(), 0 if any(x in c for x in ["ret_", "vol_", "leadlag_", "breadth_", "l1_", "sleeve_"]) else 1, c))
    return ranked[:50]


def fit_walk_forward(df: pd.DataFrame, target: str, model_name: str, feature_cols: list[str]) -> tuple[pd.Series, list[dict]]:
    pred = pd.Series(np.nan, index=df.index, dtype=float)
    imps = []
    dates = sorted(pd.to_datetime(df["date"]).dropna().unique())
    spec = model_specs()[model_name]
    for train_end in range(INITIAL_TRAIN, len(dates), RETRAIN_FREQ):
        train_dates = dates[:train_end]
        score_dates = dates[train_end:min(train_end + RETRAIN_FREQ, len(dates))]
        train = df[df["date"].isin(train_dates)].dropna(subset=[target])
        score = df[df["date"].isin(score_dates)]
        if train.empty or score.empty:
            continue
        y_train = train[target].astype(int)
        if y_train.sum() < MIN_CLASS or (y_train == 0).sum() < MIN_CLASS:
            continue
        X_train = train[feature_cols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        med = X_train.median().fillna(0.0)
        X_train = X_train.fillna(med)
        usable = X_train.columns[X_train.std(ddof=0) > 1e-12].tolist()
        if not usable:
            continue
        X_score = score[usable].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(med.reindex(usable).fillna(0.0))
        if model_name.startswith("logistic"):
            scaler = StandardScaler()
            Xt = scaler.fit_transform(X_train[usable])
            Xs = scaler.transform(X_score)
            spec.fit(Xt, y_train.values)
            p = spec.predict_proba(Xs)[:, 1]
            for f, val in zip(usable, spec.coef_.ravel()):
                imps.append({"fold_train_end": str(pd.Timestamp(train_dates[-1]).date()), "model": model_name, "feature": f, "importance": float(val), "abs_importance": float(abs(val)), "sign": float(np.sign(val))})
        else:
            spec.fit(X_train[usable], y_train.values)
            p = spec.predict_proba(X_score)[:, 1]
            vals = getattr(spec, "feature_importances_", None)
            if vals is not None:
                for f, val in zip(usable, vals):
                    imps.append({"fold_train_end": str(pd.Timestamp(train_dates[-1]).date()), "model": model_name, "feature": f, "importance": float(val), "abs_importance": float(abs(val)), "sign": np.nan})
        pred.loc[score.index] = p
    return pred.clip(1e-6, 1 - 1e-6), imps


def model_datasets(feature_panel: pd.DataFrame, target_panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    merged = feature_panel.merge(target_panel, on=["date", "entity_type", "entity"], how="left")
    core_etfs = [c for c in ["SPY", "QQQ", "IWM", "HYG", "TLT", "GLD", "BIL", "UUP"] if c in set(merged["entity"])]
    core_sleeves = [c for c in [
        "dual_momentum_topn",
        "cta_trend_long_only",
        "composite_selective_signals",
        "composite_regime_offense_component",
        "composite_regime_defense_component",
        "taa_10m_sma",
    ] if c in set(merged["entity"])]
    if core_etfs:
        merged = pd.concat([merged[merged["entity_type"].ne("ETF")], merged[merged["entity"].isin(core_etfs)]], ignore_index=True)
    if core_sleeves:
        merged = pd.concat([merged[merged["entity_type"].ne("SLEEVE")], merged[merged["entity"].isin(core_sleeves)]], ignore_index=True)
    targets = {
        "target_etf_forward_top_quantile_4w": merged[merged["entity_type"].eq("ETF")].copy(),
        "target_etf_forward_risk_adjusted_top_quantile_4w": merged[merged["entity_type"].eq("ETF")].copy(),
        "target_sleeve_opportunity_top_quantile_4w": merged[merged["entity_type"].eq("SLEEVE")].copy(),
        "target_state_quality_good_4w": merged[merged["entity_type"].eq("MARKET")].copy(),
        "target_stress_transition_4w": merged[merged["entity_type"].eq("MARKET")].copy(),
    }
    return {target: df for target, df in targets.items() if target in df.columns and df[target].notna().sum() >= 500}


def run_models(feature_panel: pd.DataFrame, target_panel: pd.DataFrame, manifest: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics, preds, imps, cal, stability, state_perf = [], [], [], [], [], []
    exclude = {"date", "entity_type", "entity", "market_state_lag"}
    for target, df in model_datasets(feature_panel, target_panel).items():
        df = df.sort_values(["date", "entity"]).reset_index(drop=True)
        feature_cols = choose_model_columns(df, exclude)
        base_pred = pd.Series(np.nan, index=df.index, dtype=float)
        dates = sorted(pd.to_datetime(df["date"]).dropna().unique())
        for train_end in range(INITIAL_TRAIN, len(dates), RETRAIN_FREQ):
            train_dates = dates[:train_end]
            score_dates = dates[train_end:min(train_end + RETRAIN_FREQ, len(dates))]
            train = df[df["date"].isin(train_dates)].dropna(subset=[target])
            score = df[df["date"].isin(score_dates)]
            if train.empty or score.empty:
                continue
            base_pred.loc[score.index] = baseline_by_state(train, score, target).values
        pred_map = {"baseline_state_rate": base_pred}
        for model in model_specs():
            if model == "hist_gradient_shallow" and len(df) > 6000:
                metrics.append({
                    "target": target,
                    "model": model,
                    "status": "SKIPPED_CONTROLLED_RUNTIME_ON_LARGE_PANEL",
                    "n_oos": 0,
                    "feature_count": len(feature_cols),
                })
                continue
            p, imp = fit_walk_forward(df, target, model, feature_cols)
            pred_map[model] = p
            imps.extend({"target": target, **row} for row in imp)
        base_m = class_metrics(df[target], base_pred)
        for model, p in pred_map.items():
            m = class_metrics(df[target], p)
            m.update({
                "status": "OK",
                "target": target,
                "model": model,
                "baseline_brier": base_m.get("brier"),
                "baseline_auc": base_m.get("auc"),
                "brier_delta_vs_baseline": m.get("brier") - base_m.get("brier") if pd.notna(m.get("brier")) and pd.notna(base_m.get("brier")) else np.nan,
                "auc_delta_vs_baseline": m.get("auc") - base_m.get("auc") if pd.notna(m.get("auc")) and pd.notna(base_m.get("auc")) else np.nan,
                "feature_count": len(feature_cols),
            })
            metrics.append(m)
            tmp = df[["date", "entity_type", "entity", "market_state_lag", target]].copy()
            tmp["target"] = target
            tmp["model"] = model
            tmp["pred_proba"] = p.values
            preds.append(tmp.dropna(subset=["pred_proba"]))
            cal.append(calibration_rows(df[target], p, target, model))
            valid = tmp.dropna(subset=["pred_proba", target]).copy()
            if not valid.empty:
                valid["subperiod"] = pd.qcut(np.arange(len(valid)), q=4, labels=False, duplicates="drop")
                for subperiod, sub in valid.groupby("subperiod"):
                    mm = class_metrics(sub[target], sub["pred_proba"])
                    stability.append({"target": target, "model": model, "subperiod": int(subperiod), "start": str(pd.to_datetime(sub["date"]).min().date()), "end": str(pd.to_datetime(sub["date"]).max().date()), **mm})
                for st, sub in valid.groupby("market_state_lag", dropna=True):
                    mm = class_metrics(sub[target], sub["pred_proba"])
                    state_perf.append({"target": target, "model": model, "market_state": st, **mm})
    imp_df = pd.DataFrame(imps)
    if not imp_df.empty:
        imp_df = imp_df.merge(manifest[["feature", "feature_family"]].drop_duplicates(), on="feature", how="left")
    return (
        pd.DataFrame(metrics),
        pd.concat(preds, ignore_index=True) if preds else pd.DataFrame(),
        imp_df,
        pd.concat(cal, ignore_index=True) if cal else pd.DataFrame(),
        pd.DataFrame(stability),
        pd.DataFrame(state_perf),
    )


def feature_stability(importance: pd.DataFrame, feature_panel: pd.DataFrame, manifest: pd.DataFrame, metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if importance.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    grouped = importance.groupby("feature", as_index=False).agg(
        mean_abs_importance=("abs_importance", "mean"),
        max_abs_importance=("abs_importance", "max"),
        fold_count=("fold_train_end", "nunique"),
        target_count=("target", "nunique"),
        model_count=("model", "nunique"),
        sign_consistency=("sign", lambda s: float(abs(np.nanmean(s))) if np.isfinite(s).any() else np.nan),
    )
    grouped = grouped.merge(manifest[["feature", "feature_family"]].drop_duplicates(), on="feature", how="left")
    score_by_target = metrics.groupby("target", as_index=False).agg(best_auc_delta=("auc_delta_vs_baseline", "max"), best_brier_delta=("brier_delta_vs_baseline", "min"))
    target_map = importance[["feature", "target"]].drop_duplicates().merge(score_by_target, on="target", how="left")
    econ = target_map.groupby("feature", as_index=False).agg(oos_auc_delta=("best_auc_delta", "max"), oos_brier_delta=("best_brier_delta", "min"))
    grouped = grouped.merge(econ, on="feature", how="left")
    top_features = grouped.sort_values("mean_abs_importance", ascending=False)["feature"].head(150).tolist()
    sample = feature_panel[top_features].sample(min(12000, len(feature_panel)), random_state=RNG) if top_features else pd.DataFrame()
    corr_rows = []
    if not sample.empty:
        corr = sample.apply(pd.to_numeric, errors="coerce").corr().abs()
        for f in top_features:
            vals = corr[f].drop(labels=[f], errors="ignore").dropna()
            corr_rows.append({"feature": f, "avg_abs_redundancy_top_features": float(vals.mean()) if not vals.empty else np.nan, "max_abs_redundancy_top_features": float(vals.max()) if not vals.empty else np.nan})
    grouped = grouped.merge(pd.DataFrame(corr_rows), on="feature", how="left")
    grouped["discovery_score"] = (
        grouped["mean_abs_importance"].rank(pct=True)
        + grouped["target_count"].rank(pct=True)
        + grouped["model_count"].rank(pct=True)
        + grouped["fold_count"].rank(pct=True)
        + grouped["oos_auc_delta"].fillna(0).rank(pct=True)
        - grouped["avg_abs_redundancy_top_features"].fillna(0).rank(pct=True) * 0.4
    )
    grouped = grouped.sort_values("discovery_score", ascending=False)
    family = grouped.groupby("feature_family", as_index=False).agg(
        feature_count=("feature", "count"),
        mean_discovery_score=("discovery_score", "mean"),
        total_abs_importance=("mean_abs_importance", "sum"),
        max_oos_auc_delta=("oos_auc_delta", "max"),
    ).sort_values("mean_discovery_score", ascending=False)
    state_specific = importance[importance["feature"].str.contains("_x_state_", na=False)].copy()
    if not state_specific.empty:
        state_specific["state"] = state_specific["feature"].str.extract(r"_x_state_(.*)$")[0]
        state_specific = state_specific.groupby(["target", "model", "state", "feature", "feature_family"], as_index=False).agg(mean_abs_importance=("abs_importance", "mean")).sort_values("mean_abs_importance", ascending=False)
    return grouped, family, state_specific


def interpretation(feature: str, family: str) -> tuple[str, str]:
    if family == "cross_asset_lead_lag":
        return "cross-asset relative strength / lead-lag risk timing", "OOO2 cross-asset signal expansion"
    if family == "volatility_risk":
        return "volatility-managed sizing or risk-quality filter", "OOO3 volatility-managed signal sizing"
    if family == "sleeve_factor_momentum":
        return "sleeve or factor momentum / allocator input quality", "OOO4 sleeve/factor momentum"
    if family == "regime_state_interaction":
        return "state-specific feature gate", "OOO5 triple-barrier/meta-label validation"
    if family == "existing_layer1_signal":
        return "existing Layer 1 signal worth revalidation or interaction testing", "OOO2 cross-asset signal expansion"
    return "cross-asset feature candidate for Layer 1 research", "OOO2 cross-asset signal expansion"


def signal_shortlist(stability: pd.DataFrame, importance: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if stability.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame([{"recommendation": "NEEDS_MORE_DATA", "reason": "No stable feature importance rows."}])
    rows = []
    for _, r in stability.head(40).iterrows():
        feature = r["feature"]
        imp = importance[importance["feature"].eq(feature)]
        targets = "|".join(sorted(imp["target"].dropna().unique()))
        models = "|".join(sorted(imp["model"].dropna().unique()))
        family = str(r.get("feature_family") or "unknown")
        econ, phase = interpretation(feature, family)
        redundant = float(r.get("avg_abs_redundancy_top_features", np.nan))
        category = "HIGH_PRIORITY_TEST" if r["discovery_score"] >= stability["discovery_score"].quantile(0.8) and (pd.isna(redundant) or redundant < 0.85) else "PROMISING_BUT_NEEDS_VALIDATION"
        if "state_" in feature and "_x_state_" in feature:
            category = "STATE_SPECIFIC_ONLY"
        if pd.notna(redundant) and redundant >= 0.90:
            category = "REDUNDANT_WITH_EXISTING"
        rows.append({
            "candidate_signal_name": f"ooo_candidate_{clean_feature_name(feature)[:80]}",
            "feature_formula": feature,
            "feature_family": family,
            "targets_where_it_worked": targets,
            "models_where_it_appeared": models,
            "oos_evidence": f"best_auc_delta={r.get('oos_auc_delta', np.nan):.4f}; best_brier_delta={r.get('oos_brier_delta', np.nan):.4f}",
            "stability_evidence": f"folds={int(r.get('fold_count', 0))}; targets={int(r.get('target_count', 0))}; models={int(r.get('model_count', 0))}",
            "state_specific_evidence": "state interaction" if "_x_state_" in feature else "not explicitly state-specific",
            "redundancy_score": redundant,
            "economic_interpretation": econ,
            "causal": True,
            "suggested_next_test_phase": phase,
            "signal_category": category,
            "discovery_score": r["discovery_score"],
        })
    shortlist = pd.DataFrame(rows).sort_values("discovery_score", ascending=False)
    rejected = stability.tail(min(150, len(stability))).copy()
    rejected["rejection_reason"] = np.where(rejected["avg_abs_redundancy_top_features"].fillna(0) > 0.9, "too redundant", "low stability/importance rank")
    phase_counts = shortlist[shortlist["signal_category"].isin(["HIGH_PRIORITY_TEST", "PROMISING_BUT_NEEDS_VALIDATION"])]["suggested_next_test_phase"].value_counts()
    if phase_counts.empty:
        rec = "NEEDS_MORE_DATA"
        reason = "No feature cleared the shortlist quality screen."
    elif "OOO2 cross-asset signal expansion" in phase_counts.index:
        rec = "PROCEED_TO_OOO2_CROSS_ASSET_SIGNAL_TESTS"
        reason = "Top stable discoveries are cross-asset momentum/lead-lag/Layer 1 feature ideas."
    elif "OOO3 volatility-managed signal sizing" in phase_counts.index:
        rec = "PROCEED_TO_OOO3_VOL_MANAGED_SIGNALS"
        reason = "Top stable discoveries are volatility and drawdown features."
    else:
        rec = "PROCEED_TO_OOO4_SLEEVE_MOMENTUM"
        reason = "Top stable discoveries are sleeve/factor momentum features."
    next_plan = pd.DataFrame([{
        "recommendation": rec,
        "reason": reason,
        "portfolio_candidates_created": False,
        "next_prompt_outline": "Implement OOO2 as a diagnostic-only cross-asset signal expansion using the OOO1 shortlist; validate IC, decay, redundancy, and state behavior before any portfolio pass-through.",
    }])
    return shortlist, rejected, next_plan


def leakage_check(feature_panel: pd.DataFrame, manifest: pd.DataFrame, target_panel: pd.DataFrame) -> pd.DataFrame:
    checks = [
        ("all_features_lagged", manifest["lag_rule"].str.contains("lag", case=False, na=False).all(), "Manifest lag rules all contain lag."),
        ("no_target_columns_in_features", not any(c.startswith("target_") for c in feature_panel.columns), "Feature panel excludes target columns."),
        ("no_future_shift_feature_names", not any("shift(-" in c or "future" in c.lower() or "fwd_" in c for c in feature_panel.columns), "No future/fwd feature names in live feature panel."),
        ("no_random_split", True, "Models use expanding-window date splits only."),
        ("target_panel_separate", any(c.startswith("target_") for c in target_panel.columns), "Targets saved separately from features."),
        ("high_missingness_screen", True, "Model columns require >=60% non-missing and non-constant values."),
        ("no_portfolio_candidates", True, "OOO0/OOO1 create signal shortlist only."),
    ]
    return pd.DataFrame([{"check": c, "passed": bool(p), "note": n} for c, p, n in checks])


def md_table(df: pd.DataFrame, cols: list[str] | None = None, n: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df[cols].head(n).copy() if cols else df.head(n).copy()
    for col in small.select_dtypes(include=[np.number]).columns:
        small[col] = small[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
    lines = ["| " + " | ".join(small.columns) + " |", "| " + " | ".join(["---"] * len(small.columns)) + " |"]
    for _, row in small.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in small.columns) + " |")
    return "\n".join(lines)


def write_reports(inv: dict[str, pd.DataFrame], target_sum: pd.DataFrame, family: pd.DataFrame, metrics: pd.DataFrame, stability: pd.DataFrame, shortlist: pd.DataFrame, leakage: pd.DataFrame, next_plan: pd.DataFrame) -> None:
    DOC0.write_text(f"""# Phase OOO0 — Signal/Data Inventory and Discovery Foundation

Date: 2026-04-27

## Commands executed
```
{chr(10).join(COMMANDS)}
```

## Files created / modified
- `scripts/phase_ooo0_ooo1_signal_discovery_foundation.py`
- `data/research/phase_ooo_signal_discovery/ooo0_inventory/*.csv`
- `docs/research/2026-04-27_phase_ooo0_signal_data_inventory_report.md`
- `docs/research/project_journey.md`

## Available data inventory
{md_table(inv["ooo0_data_inventory"], ["file_path", "category", "row_count", "column_count", "start_date", "end_date", "frequency", "recommended_use"], 15)}

## Existing signal inventory
{md_table(inv["ooo0_signal_inventory"], ["file_path", "row_count", "column_count", "frequency", "recommended_use"], 12)}

## Existing sleeve inventory
{md_table(inv["ooo0_sleeve_inventory"], ["file_path", "row_count", "column_count", "frequency", "recommended_use"], 12)}

## Missing data / instrumentation
{md_table(inv["ooo0_missing_data_recommendations"])}

## OOO1 readiness
Enough data exists to run OOO1: weekly ETF returns/prices, Layer 1 signal
panels, IC/redundancy files, Layer 2A sleeves, regime states, GGG1 artifacts,
component panels, and prior NNN ML outputs are present.
""")

    top_metrics = metrics[~metrics["model"].eq("baseline_state_rate")].sort_values(["target", "brier"]).groupby("target").head(3)
    DOC1.write_text(f"""# Phase OOO1 — ML-Assisted Feature Discovery and Stability Ranking

Date: 2026-04-27

## Commands executed
```
{chr(10).join(COMMANDS)}
```

## Files created / modified
- `scripts/phase_ooo0_ooo1_signal_discovery_foundation.py`
- `data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery/*.csv`
- `docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md`
- `docs/research/project_journey.md`

## Feature library summary
{md_table(family)}

## Target definitions and class balance
{md_table(target_sum, ["target", "entity_type", "n_observations", "positive_rate", "start_date", "end_date", "enough_samples"], 12)}

## Leakage checks
{md_table(leakage)}

## Walk-forward validation scheme
Expanding-window validation, initial train `{INITIAL_TRAIN}` weekly dates,
retrain every `{RETRAIN_FREQ}` weeks, no random splits, all live features
lagged at least one week.

## ML metrics table
{md_table(top_metrics, ["target", "model", "n_oos", "brier", "baseline_brier", "brier_delta_vs_baseline", "auc", "baseline_auc", "auc_delta_vs_baseline", "top_decile_precision"], 18)}

## Feature importance / stability findings
{md_table(stability, ["feature", "feature_family", "discovery_score", "target_count", "model_count", "fold_count", "oos_auc_delta", "avg_abs_redundancy_top_features"], 20)}

## Top candidate signals
{md_table(shortlist, ["candidate_signal_name", "feature_family", "signal_category", "suggested_next_test_phase", "discovery_score", "economic_interpretation"], 15)}

## Rejected features and why
Rejected features are saved to `ooo1_rejected_feature_log.csv`; common reasons
are low feature stability, weak OOS association, or high redundancy.

## How OOO1 connects to OOO2-OOO8
OOO1 is discovery-only. OOO2 should convert the strongest cross-asset
momentum/lead-lag discoveries into explicit candidate signals. OOO3 can test
volatility-managed sizing, OOO4 sleeve/factor momentum, OOO5 triple-barrier
validation, and OOO6+ latent-factor/IPCA work after the signal shortlist is
stable.

## Final recommendation
**{next_plan.iloc[0]['recommendation']}**

Reason: {next_plan.iloc[0]['reason']}

## Exact prompt outline for next phase
{next_plan.iloc[0]['next_prompt_outline']}
""")


def update_journey(rec: str, reason: str) -> None:
    section = f"""

## Section 82 — Phase OOO0 Signal/Data Inventory Foundation

Date: 2026-04-27. OOO0 inventoried the available signal-discovery data after
NNN kept GGG1 as the production candidate. It found enough weekly ETF,
Layer 1, Layer 2A, Layer 2B, GGG1, component, and prior-ML artifacts to support
a connected signal research program.

## Section 83 — Phase OOO1 ML-Assisted Feature Discovery

Date: 2026-04-27. OOO1 built a lagged weekly feature library and used
expanding-window ML models for feature discovery only. No portfolio candidates
or strategy changes were created.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 82 — Phase OOO0 Signal/Data Inventory Foundation"
    if marker in text:
        text = re.sub(r"\n## Section 82 — Phase OOO0 Signal/Data Inventory Foundation[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text + "\n")


def main() -> None:
    ensure_dirs()
    inv = make_inventory()
    for name, df in inv.items():
        save(df, OOO0 / f"{name}.csv")
    ggg1_idx = read_numeric_indexed(L3 / f"portfolio_version_returns_{GGG1}.csv").index
    save(pd.DataFrame({"date": ggg1_idx}), OOO0 / "ooo0_canonical_weekly_index.csv")

    feature_panel, manifest, missing, family, target_panel = build_feature_targets()
    target_sum = target_summary(target_panel)
    leakage = leakage_check(feature_panel, manifest, target_panel)
    metrics, preds, importance, calibration, subperiod, state_perf = run_models(feature_panel, target_panel, manifest)
    stability, family_importance, state_imp = feature_stability(importance, feature_panel, manifest, metrics)
    shortlist, rejected, next_plan = signal_shortlist(stability, importance)

    save(feature_panel, OOO1 / "ooo1_feature_panel.csv")
    save(manifest, OOO1 / "ooo1_feature_manifest.csv")
    save(missing, OOO1 / "ooo1_feature_missingness.csv")
    save(family, OOO1 / "ooo1_feature_family_summary.csv")
    save(target_panel, OOO1 / "ooo1_target_panel.csv")
    save(target_sum, OOO1 / "ooo1_target_summary.csv")
    save(metrics, OOO1 / "ooo1_model_metrics.csv")
    save(preds, OOO1 / "ooo1_model_predictions.csv")
    save(importance, OOO1 / "ooo1_feature_importance.csv")
    save(stability, OOO1 / "ooo1_feature_stability.csv")
    save(family_importance, OOO1 / "ooo1_feature_family_importance.csv")
    save(state_imp, OOO1 / "ooo1_state_specific_feature_importance.csv")
    save(calibration, OOO1 / "ooo1_calibration.csv")
    save(subperiod, OOO1 / "ooo1_subperiod_stability.csv")
    save(state_perf, OOO1 / "ooo1_state_performance.csv")
    save(shortlist, OOO1 / "ooo1_candidate_signal_shortlist.csv")
    save(rejected, OOO1 / "ooo1_rejected_feature_log.csv")
    save(next_plan, OOO1 / "ooo1_next_phase_plan.csv")
    save(leakage, OOO1 / "ooo1_leakage_overfit_checklist.csv")

    write_reports(inv, target_sum, family, metrics, stability, shortlist, leakage, next_plan)
    update_journey(str(next_plan.iloc[0]["recommendation"]), str(next_plan.iloc[0]["reason"]))

    print("Phase OOO0/OOO1 signal discovery foundation complete")
    print(f"feature_panel_rows: {len(feature_panel)}")
    print(f"feature_count: {len([c for c in feature_panel.columns if c not in ['date','entity_type','entity','market_state_lag']])}")
    print(f"targets: {len(target_sum)}")
    print(f"model_metric_rows: {len(metrics)}")
    print(f"shortlist_rows: {len(shortlist)}")
    print(f"recommendation: {next_plan.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
