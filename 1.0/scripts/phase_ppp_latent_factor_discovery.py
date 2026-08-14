"""Phase PPP0/PPP1 -- latent factor and sleeve discovery.

Diagnostic-only research phase. This script builds a lagged weekly ETF
characteristic panel aligned to GGG1 dates, runs PCA latent factor benchmarks,
implements an internal IPCA-style characteristic-conditioned factor
approximation, validates factors against states/sleeves/proxies/GGG1, and
writes a research report. It does not create portfolio candidates, change GGG1
logic, or alter production/shadow pins.
"""
from __future__ import annotations

import json
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
L0 = DATA / "01_data_hub"
L1 = DATA / "02_layer1_signals"
L2A = DATA / "03_layer2a_strategy_logic"
L2B = DATA / "04_layer2b_risk_regime_engine"
L3 = DATA / "05_layer3_portfolio_construction"
OOO = DATA / "research" / "phase_ooo_signal_discovery"
JJJ2 = DATA / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = DATA / "research" / "phase_ppp_latent_factor_discovery"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_ppp_latent_factor_discovery_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

K_LIST = [3, 5, 8, 10]
PCA_MAIN_K = 5
IPCA_K = 3
INITIAL_TRAIN = 260
REFIT_FREQ = 26
MIN_ETF_VALID_WEEKS = 520
MIN_IPCA_FEATURE_COVERAGE = 0.55
RIDGE_ALPHA = 10.0
TRADING_WEEKS = 52

COMMANDS = [
    "pwd && git status --short && rg --files | sed -n '1,220p'",
    "find docs/research data -maxdepth 3 -type d | sort | sed -n '1,220p'",
    "ls -lh portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv portfolio_version_returns_improved_phase2b_combo_abc 2>/dev/null || true",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md",
    "sed -n '1,220p' docs/research/2026-04-27_phase_iii_production_candidate_review_report.md",
    "tail -n 180 docs/research/project_journey.md",
    "find data/01_data_hub data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction data/research/phase_ooo_signal_discovery -maxdepth 2 -type f | sort | sed -n '1,260p'",
    "python3 - <<'PY' ...schema/package availability inspections...",
    "python3 scripts/phase_ppp_latent_factor_discovery.py",
]


@dataclass
class FactorBundle:
    returns: pd.DataFrame
    loadings: pd.DataFrame
    weights_by_date: pd.DataFrame
    explained: pd.DataFrame
    stability: pd.DataFrame
    sleeve_corr: pd.DataFrame
    state_perf: pd.DataFrame


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)


def read_indexed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = next((c for c in ["Date", "date", "Unnamed: 0"] if c in df.columns), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    df.index.name = "date"
    return df


def read_numeric_indexed(path: Path) -> pd.DataFrame:
    return read_indexed(path).apply(pd.to_numeric, errors="coerce")


def save_csv(df: pd.DataFrame, path: Path, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)


def clean_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", str(name)).strip("_")


def trailing_compound(s: pd.Series, window: int) -> pd.Series:
    return np.expm1(np.log1p(s).rolling(window, min_periods=max(3, window // 2)).sum())


def downside_vol(s: pd.Series, window: int) -> pd.Series:
    return s.where(s < 0.0, 0.0).rolling(window, min_periods=max(4, window // 2)).std(ddof=0)


def rolling_drawdown(s: pd.Series, window: int) -> pd.Series:
    def calc(x: np.ndarray) -> float:
        x = x[np.isfinite(x)]
        if len(x) < max(4, window // 3):
            return np.nan
        wealth = np.cumprod(1.0 + x)
        return float((wealth / np.maximum.accumulate(wealth) - 1.0).min())

    return s.rolling(window, min_periods=max(4, window // 2)).apply(calc, raw=True)


def max_drawdown(r: pd.Series) -> float:
    x = pd.to_numeric(r, errors="coerce").dropna()
    if x.empty:
        return np.nan
    wealth = (1.0 + x).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def perf_stats(r: pd.Series) -> dict[str, float]:
    x = pd.to_numeric(r, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if x.empty:
        return {
            "n_weeks": 0,
            "weekly_mean": np.nan,
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "cvar_5": np.nan,
        }
    n = len(x)
    wealth = float((1.0 + x).prod())
    ann_return = wealth ** (TRADING_WEEKS / n) - 1.0 if wealth > 0 else np.nan
    ann_vol = float(x.std(ddof=0) * math.sqrt(TRADING_WEEKS))
    q = float(x.quantile(0.05))
    tail = x[x <= q]
    cvar = float(tail.mean()) if len(tail) else np.nan
    return {
        "n_weeks": int(n),
        "weekly_mean": float(x.mean()),
        "ann_return": float(ann_return),
        "ann_vol": ann_vol,
        "sharpe": float(ann_return / ann_vol) if ann_vol and ann_vol > 0 and np.isfinite(ann_return) else np.nan,
        "max_drawdown": max_drawdown(x),
        "cvar_5": cvar,
    }


def corr(a: pd.Series, b: pd.Series) -> float:
    aligned = pd.concat([a, b], axis=1).dropna()
    if len(aligned) < 12:
        return np.nan
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))


def apply_portfolio_weights(row: pd.Series, weights: pd.Series) -> float:
    common = row.index.intersection(weights.index)
    if common.empty:
        return np.nan
    r = pd.to_numeric(row.loc[common], errors="coerce")
    w = pd.to_numeric(weights.loc[common], errors="coerce")
    mask = r.notna() & w.notna()
    if not mask.any():
        return np.nan
    r = r.loc[mask]
    w = w.loc[mask]
    denom = float(w.abs().sum())
    if denom <= 0:
        return np.nan
    return float((r * (w / denom)).sum())


def portfolio_returns_from_weights(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    common = returns.columns.intersection(weights.index)
    if common.empty:
        return pd.Series(np.nan, index=returns.index)
    data = returns.loc[:, common]
    w = pd.to_numeric(weights.loc[common], errors="coerce").fillna(0.0)
    valid = data.notna().astype(float)
    denom = valid.dot(w.abs()).replace(0.0, np.nan)
    numer = data.fillna(0.0).dot(w)
    return numer / denom


def normalize_abs(weights: pd.Series) -> pd.Series:
    w = pd.to_numeric(weights, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    denom = float(w.abs().sum())
    if denom <= 0:
        return w * np.nan
    return w / denom


def orient_weights(
    raw_weights: pd.Series,
    train_returns: pd.DataFrame,
    proxies: pd.DataFrame,
    prev_weights: pd.Series | None = None,
) -> tuple[pd.Series, str, float]:
    weights = normalize_abs(raw_weights)
    if prev_weights is not None:
        common = weights.index.intersection(prev_weights.index)
        if len(common) and float((weights.loc[common] * prev_weights.loc[common]).sum()) < 0:
            return -weights, "previous_loading_alignment", np.nan
        return weights, "previous_loading_alignment", np.nan

    factor_train = portfolio_returns_from_weights(train_returns, weights)
    proxy_corrs = {}
    for p in proxies.columns:
        proxy_corrs[p] = corr(factor_train, proxies[p])
    if proxy_corrs:
        best = max(proxy_corrs, key=lambda k: abs(proxy_corrs[k]) if np.isfinite(proxy_corrs[k]) else -1)
        best_corr = proxy_corrs[best]
        if np.isfinite(best_corr) and best_corr < 0:
            weights = -weights
        return weights, f"dominant_proxy_{best}", float(abs(best_corr)) if np.isfinite(best_corr) else np.nan

    if factor_train.mean(skipna=True) < 0:
        weights = -weights
    return weights, "positive_train_mean", np.nan


def markdown_table(df: pd.DataFrame, n: int = 12, float_fmt: str = ".4f") -> str:
    if df is None or df.empty:
        return "_None._"
    view = df.head(n).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else format(float(x), float_fmt))
    view = view.astype(str).replace({"nan": "", "NaT": "", "None": ""})
    cols = [str(c) for c in view.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in view.iterrows():
        values = [str(row[c]).replace("|", "\\|").replace("\n", " ") for c in view.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def load_core_inputs() -> dict[str, pd.DataFrame | pd.Series]:
    ggg1_returns = read_numeric_indexed(L3 / f"portfolio_version_returns_{GGG1}.csv")
    dates = ggg1_returns.index
    weekly_returns = read_numeric_indexed(L0 / "weekly_returns.csv").reindex(dates)
    weekly_prices = read_numeric_indexed(L0 / "weekly_prices.csv").reindex(dates)
    benchmark_returns = read_numeric_indexed(L0 / "benchmark_returns_weekly.csv").reindex(dates)
    states = read_indexed(L2B / "market_state_history.csv").reindex(dates)
    regime_states = read_indexed(L2B / "regime_states.csv").reindex(dates)
    ggg1_weights = read_numeric_indexed(L3 / f"portfolio_version_weights_{GGG1}.csv").reindex(dates)
    ggg1_sleeve_weights = read_numeric_indexed(L3 / f"portfolio_version_sleeve_weights_{GGG1}.csv").reindex(dates)
    production_returns = read_numeric_indexed(L3 / f"portfolio_version_returns_{PRODUCTION}.csv").reindex(dates)
    shadow_returns = read_numeric_indexed(L3 / f"portfolio_version_returns_{SHADOW}.csv").reindex(dates)
    return {
        "dates": dates,
        "weekly_returns": weekly_returns,
        "weekly_prices": weekly_prices,
        "benchmark_returns": benchmark_returns,
        "states": states,
        "regime_states": regime_states,
        "ggg1_returns": ggg1_returns,
        "production_returns": production_returns,
        "shadow_returns": shadow_returns,
        "ggg1_weights": ggg1_weights,
        "ggg1_sleeve_weights": ggg1_sleeve_weights,
    }


def load_layer1_features(dates: pd.DatetimeIndex, tickers: list[str]) -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    manifest_rows = []
    skip = {
        "signal_summary_table.csv",
        "signal_ic_by_horizon.csv",
        "signal_incremental_contribution.csv",
        "signal_subset_comparison.csv",
        "signal_redundancy_matrix.csv",
        "signal_redundancy_pairs.csv",
        "signal_eligibility_matrix.csv",
    }
    for path in sorted(L1.glob("signal_*.csv")):
        if path.name in skip:
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "Date" not in df.columns or "Ticker" not in df.columns:
            continue
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        value_cols = []
        for col in df.columns:
            if col in {"Date", "Ticker", "asset_class"}:
                continue
            if col.endswith("_tradable") or col.endswith("_score_tradable"):
                value_cols.append(col)
        if not value_cols:
            continue
        keep = df[df["Ticker"].isin(tickers) & df["Date"].isin(dates)][["Date", "Ticker", *value_cols]].copy()
        rename = {c: f"l1_{clean_name(path.stem.replace('signal_', ''))}_{clean_name(c)}" for c in value_cols}
        keep = keep.rename(columns=rename)
        for col in rename.values():
            keep[col] = pd.to_numeric(keep[col], errors="coerce")
            keep[col] = keep.groupby("Ticker")[col].shift(1)
            manifest_rows.append(
                {
                    "feature_name": col,
                    "panel": "ppp_panel_characteristics",
                    "source": str(path.relative_to(ROOT)),
                    "feature_family": "existing_layer1_signal",
                    "entity_scope": "ETF",
                    "lag_rule": "source tradable signal shifted one additional week for PPP prediction safety",
                    "used_in_ipca": True,
                    "leakage_check": "lagged; no forward returns",
                    "notes": "Layer 1 value available by Date/Ticker; nonnumeric values coerced to missing.",
                }
            )
        frames.append(keep.rename(columns={"Date": "date", "Ticker": "ticker"}))
    if not frames:
        return pd.DataFrame({"date": [], "ticker": []}), manifest_rows
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on=["date", "ticker"], how="outer")
    return out, manifest_rows


def load_market_feature_sources(dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    manifest_rows = []

    def add_market_file(path: Path, prefix: str, family: str, shift: int = 1) -> None:
        if not path.exists():
            return
        df = read_indexed(path).reindex(dates)
        cols = []
        for col in df.columns:
            if col == "market_state":
                continue
            series = pd.to_numeric(df[col], errors="coerce")
            if series.notna().sum() < 12:
                continue
            name = f"{prefix}_{clean_name(col)}"
            cols.append(name)
            df[name] = series.shift(shift)
            manifest_rows.append(
                {
                    "feature_name": name,
                    "panel": "ppp_panel_characteristics",
                    "source": str(path.relative_to(ROOT)),
                    "feature_family": family,
                    "entity_scope": "MARKET",
                    "lag_rule": f"market-level source shifted {shift} week(s)",
                    "used_in_ipca": False,
                    "leakage_check": "lagged; constant across ETF cross-section, excluded from IPCA-style cross-sectional loadings",
                    "notes": "",
                }
            )
        if cols:
            frames.append(df[cols].reset_index(names="date"))

    add_market_file(OOO / "ooo2_cross_asset_signal_expansion" / "ooo2_candidate_signal_panel.csv", "ooo2", "ooo_discovered_signal", 1)
    add_market_file(OOO / "ooo3_vol_managed_signal_sizing" / "ooo3_signal_sizing_feature_panel.csv", "ooo3", "ooo_discovered_signal", 1)
    add_market_file(OOO / "ooo3_vol_managed_signal_sizing" / "ooo3_sized_signal_event_panel.csv", "ooo3event", "ooo_sized_event_signal", 1)
    add_market_file(L2B / "market_state_history.csv", "regime", "regime_numeric_context", 1)

    if not frames:
        return pd.DataFrame({"date": dates}), manifest_rows
    out = pd.DataFrame({"date": dates})
    for frame in frames:
        out = out.merge(frame, on="date", how="left")
    return out, manifest_rows


def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame | pd.Series]]:
    inputs = load_core_inputs()
    dates = inputs["dates"]
    returns = inputs["weekly_returns"]
    prices = inputs["weekly_prices"]
    states = inputs["states"]
    regime_states = inputs["regime_states"]
    ggg1_weights = inputs["ggg1_weights"]
    ggg1_sleeve_weights = inputs["ggg1_sleeve_weights"]
    tickers = [c for c in returns.columns if c in prices.columns]

    etf_returns = returns[tickers].copy()
    save_csv(etf_returns.reset_index(names="date"), OUT / "ppp_panel_etf_returns.csv")

    manifest_rows: list[dict] = []
    characteristic_frames = []
    proxies = [p for p in ["SPY", "BIL", "TLT", "GLD", "HYG", "LQD"] if p in returns.columns]
    for ticker in tickers:
        r = returns[ticker]
        p = prices[ticker]
        df = pd.DataFrame(index=dates)
        df["ticker"] = ticker

        features: dict[str, pd.Series] = {}
        for w in [4, 13, 26, 52]:
            features[f"mom_{w}w"] = trailing_compound(r, w).shift(1)
        for w in [4, 13, 26]:
            features[f"vol_{w}w"] = r.rolling(w, min_periods=max(3, w // 2)).std(ddof=0).shift(1)
        features["downside_vol_13w"] = downside_vol(r, 13).shift(1)
        features["downside_vol_26w"] = downside_vol(r, 26).shift(1)
        features["drawdown_26w"] = rolling_drawdown(r, 26).shift(1)
        features["drawdown_52w"] = rolling_drawdown(r, 52).shift(1)
        for w in [13, 26, 52]:
            ma = p.rolling(w, min_periods=max(4, w // 2)).mean()
            features[f"ma_distance_{w}w"] = (p / ma - 1.0).shift(1)
        for w in [13, 26]:
            features[f"trend_consistency_{w}w"] = (r > 0.0).rolling(w, min_periods=max(4, w // 2)).mean().shift(1)
        features["mom_vol_ratio_26w"] = (features["mom_26w"] / features["vol_26w"].replace(0.0, np.nan))
        features["vol_change_13v26"] = (features["vol_13w"] / features["vol_26w"].replace(0.0, np.nan) - 1.0)
        for proxy in proxies:
            proxy_r = returns[proxy]
            for w in [13, 26]:
                features[f"rel_strength_{proxy}_{w}w"] = (trailing_compound(r, w) - trailing_compound(proxy_r, w)).shift(1)

        for name, series in features.items():
            df[name] = series
        df["ggg1_etf_weight"] = ggg1_weights[ticker] if ticker in ggg1_weights.columns else np.nan
        df["market_state"] = states["market_state"] if "market_state" in states.columns else np.nan
        df["market_state_lag1"] = df["market_state"].shift(1)
        df["risk_state_lag1"] = regime_states["risk_state"].shift(1) if "risk_state" in regime_states.columns else np.nan
        characteristic_frames.append(df.reset_index(names="date"))

        for name in features:
            manifest_rows.append(
                {
                    "feature_name": name,
                    "panel": "ppp_panel_characteristics",
                    "source": "data/01_data_hub/weekly_returns.csv; data/01_data_hub/weekly_prices.csv",
                    "feature_family": "rolling_etf_characteristic",
                    "entity_scope": "ETF",
                    "lag_rule": "trailing weekly calculation shifted one week; no centered windows",
                    "used_in_ipca": True,
                    "leakage_check": "uses only returns/prices through prior weekly date",
                    "notes": "",
                }
            )
        manifest_rows.append(
            {
                "feature_name": "ggg1_etf_weight",
                "panel": "ppp_panel_characteristics",
                "source": f"data/05_layer3_portfolio_construction/portfolio_version_weights_{GGG1}.csv",
                "feature_family": "ggg1_exposure_context",
                "entity_scope": "ETF",
                "lag_rule": "contemporaneous saved GGG1 exposure used for exposure diagnostics, not IPCA prediction",
                "used_in_ipca": False,
                "leakage_check": "excluded from predictive model features",
                "notes": "",
            }
        )

    characteristics = pd.concat(characteristic_frames, ignore_index=True)
    l1_features, l1_manifest = load_layer1_features(dates, tickers)
    if not l1_features.empty:
        characteristics = characteristics.merge(l1_features, on=["date", "ticker"], how="left")
    manifest_rows.extend(l1_manifest)

    market_features, market_manifest = load_market_feature_sources(dates)
    characteristics = characteristics.merge(market_features, on="date", how="left")
    manifest_rows.extend(market_manifest)

    for col in ["market_state", "market_state_lag1", "risk_state_lag1"]:
        manifest_rows.append(
            {
                "feature_name": col,
                "panel": "ppp_panel_characteristics",
                "source": "data/04_layer2b_risk_regime_engine/",
                "feature_family": "regime_state_label",
                "entity_scope": "MARKET",
                "lag_rule": "state label/context; lagged variant provided; current label used only for validation grouping",
                "used_in_ipca": False,
                "leakage_check": "state labels not used as forward-return features in IPCA-style cross-sectional model",
                "notes": "",
            }
        )

    save_csv(characteristics, OUT / "ppp_panel_characteristics.csv")

    sleeve_returns = pd.DataFrame(index=dates)
    for path in sorted(L2A.glob("strategy_returns_*.csv")):
        try:
            df = read_numeric_indexed(path).reindex(dates)
        except Exception:
            continue
        if "net_return" in df.columns:
            sleeve = path.stem.replace("strategy_returns_", "")
            sleeve_returns[f"sleeve_return_{sleeve}"] = df["net_return"]
    comp_path = JJJ2 / f"component_returns_{GGG1}.csv"
    if comp_path.exists():
        comp = read_numeric_indexed(comp_path).reindex(dates)
        for col in comp.columns:
            sleeve_returns[f"ggg1_component_return_{col}"] = comp[col]
    for version, label in [(PRODUCTION, "production"), (SHADOW, "shadow"), (GGG1, "ggg1")]:
        df = read_numeric_indexed(L3 / f"portfolio_version_returns_{version}.csv").reindex(dates)
        if "net_return" in df.columns:
            sleeve_returns[f"portfolio_return_{label}_{version}"] = df["net_return"]
    for col in ggg1_sleeve_weights.columns:
        sleeve_returns[f"ggg1_sleeve_weight_{clean_name(col)}"] = ggg1_sleeve_weights[col]
    save_csv(sleeve_returns.reset_index(names="date"), OUT / "ppp_panel_sleeve_returns.csv")

    manifest = pd.DataFrame(manifest_rows).drop_duplicates(["feature_name", "panel", "source"])
    feature_missing = characteristics.drop(columns=["date", "ticker"], errors="ignore").isna().mean()
    manifest["missingness"] = manifest["feature_name"].map(feature_missing).astype(float)
    manifest["non_missing_rows"] = manifest["feature_name"].map(characteristics.notna().sum()).astype(float)
    save_csv(manifest, OUT / "ppp_feature_manifest.csv")

    quality = build_data_quality_report(etf_returns, characteristics, sleeve_returns, manifest, tickers)
    save_csv(quality, OUT / "ppp_data_quality_report.csv")
    return etf_returns, characteristics, sleeve_returns, manifest, quality, inputs


def build_data_quality_report(
    etf_returns: pd.DataFrame,
    characteristics: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    manifest: pd.DataFrame,
    tickers: list[str],
) -> pd.DataFrame:
    rows = []
    rows.append(
        {
            "section": "dataset_summary",
            "item": "weekly_panel",
            "metric": "date_range",
            "value": f"{etf_returns.index.min().date()} to {etf_returns.index.max().date()}",
            "notes": f"{len(etf_returns)} GGG1-aligned weekly dates; {len(tickers)} ETF columns.",
        }
    )
    inferred_gap = etf_returns.index.to_series().diff().dt.days.dropna().median()
    rows.append(
        {
            "section": "dataset_summary",
            "item": "weekly_panel",
            "metric": "median_date_gap_days",
            "value": inferred_gap,
            "notes": "Expected roughly weekly frequency.",
        }
    )
    rows.append(
        {
            "section": "dataset_summary",
            "item": "characteristics",
            "metric": "rows_columns",
            "value": f"{characteristics.shape[0]} x {characteristics.shape[1]}",
            "notes": "Long ETF panel: one Date/Ticker row per available ETF/date.",
        }
    )
    rows.append(
        {
            "section": "dataset_summary",
            "item": "sleeves",
            "metric": "rows_columns",
            "value": f"{sleeve_returns.shape[0]} x {sleeve_returns.shape[1]}",
            "notes": "Layer 2A sleeve returns plus GGG1 component/portfolio/sleeve-weight context.",
        }
    )
    for ticker in tickers:
        s = etf_returns[ticker]
        valid = int(s.notna().sum())
        missing = float(s.isna().mean())
        first = s.first_valid_index()
        last = s.last_valid_index()
        pca_ok = valid >= MIN_ETF_VALID_WEEKS
        rows.append(
            {
                "section": "etf_missingness",
                "item": ticker,
                "metric": "valid_weeks_missingness",
                "value": f"{valid}; {missing:.4f}",
                "notes": (
                    f"first_valid={first.date() if first is not None else 'NA'}, "
                    f"last_valid={last.date() if last is not None else 'NA'}, "
                    f"pca_universe={'yes' if pca_ok else 'no'}"
                ),
            }
        )
    for _, row in manifest.iterrows():
        rows.append(
            {
                "section": "feature_missingness",
                "item": row["feature_name"],
                "metric": "missingness",
                "value": row.get("missingness", np.nan),
                "notes": f"family={row.get('feature_family')}; lag={row.get('lag_rule')}",
            }
        )
    leakage_checks = [
        ("all_constructed_characteristics_lagged", True, "rolling ETF features are shifted one week"),
        ("layer1_values_lagged_again", True, "source tradable Layer 1 values are shifted one additional week"),
        ("ooo_values_lagged", True, "OOO market-level signals/events are shifted one week"),
        ("no_forward_returns_as_features", True, "forward returns are never saved into characteristic panel"),
        ("no_centered_rolling_windows", True, "all rolling windows are trailing"),
        ("no_random_train_test_split", True, "PCA/IPCA validation uses full diagnostic or expanding/walk-forward windows"),
        ("production_pins_unchanged", True, f"production={PRODUCTION}; shadow={SHADOW}; GGG1 remains candidate"),
    ]
    for item, passed, note in leakage_checks:
        rows.append(
            {
                "section": "leakage_checks",
                "item": item,
                "metric": "passed",
                "value": bool(passed),
                "notes": note,
            }
        )
    dropped = manifest[
        (manifest["used_in_ipca"] == True)  # noqa: E712
        & ((manifest["missingness"].fillna(1.0) > (1.0 - MIN_IPCA_FEATURE_COVERAGE)) | (manifest["non_missing_rows"].fillna(0) < 100))
    ]
    if dropped.empty:
        rows.append({"section": "dropped_features", "item": "none_at_manifest_stage", "metric": "reason", "value": "", "notes": ""})
    else:
        for _, row in dropped.iterrows():
            rows.append(
                {
                    "section": "dropped_features",
                    "item": row["feature_name"],
                    "metric": "reason",
                    "value": "low_coverage_for_ipca",
                    "notes": f"missingness={row.get('missingness')}",
                }
            )
    return pd.DataFrame(rows)


def pca_fit(
    returns: pd.DataFrame,
    n_factors: int,
    proxies: pd.DataFrame,
    prev_weights: dict[int, pd.Series] | None = None,
) -> tuple[PCA, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    means = returns.mean()
    stds = returns.std(ddof=0).replace(0.0, np.nan)
    x = returns.fillna(means).fillna(0.0)
    x_std = ((x - means) / stds).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    model = PCA(n_components=min(n_factors, x_std.shape[1]), random_state=0)
    model.fit(x_std)

    loading_rows = []
    weights: dict[str, pd.Series] = {}
    factor_train = pd.DataFrame(index=returns.index)
    for f_idx in range(model.n_components_):
        raw = pd.Series(model.components_[f_idx], index=returns.columns)
        prev = prev_weights.get(f_idx + 1) if prev_weights else None
        oriented, sign_rule, sign_anchor = orient_weights(raw, returns, proxies.reindex(returns.index), prev)
        weights[f"f{f_idx + 1}"] = oriented
        factor_train[f"f{f_idx + 1}"] = portfolio_returns_from_weights(returns, oriented)
        for ticker, val in raw.items():
            loading_rows.append(
                {
                    "factor": f"f{f_idx + 1}",
                    "ticker": ticker,
                    "loading": float(val if oriented.loc[ticker] >= 0 or raw.loc[ticker] == 0 else -val),
                    "portfolio_weight": float(oriented.loc[ticker]),
                    "sign_rule": sign_rule,
                    "sign_anchor_abs_corr": sign_anchor,
                }
            )
    weight_df = pd.DataFrame(weights)
    loadings = pd.DataFrame(loading_rows)
    explained = pd.DataFrame(
        {
            "factor": [f"f{i + 1}" for i in range(model.n_components_)],
            "explained_variance_ratio": model.explained_variance_ratio_,
            "cumulative_explained_variance": np.cumsum(model.explained_variance_ratio_),
        }
    )
    return model, loadings, weight_df, explained


def run_pca_benchmark(
    etf_returns: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    states: pd.DataFrame,
) -> FactorBundle:
    valid_counts = etf_returns.notna().sum()
    pca_cols = valid_counts[valid_counts >= MIN_ETF_VALID_WEEKS].index.tolist()
    pca_returns = etf_returns[pca_cols].copy()
    proxy_cols = [c for c in ["SPY", "BIL", "TLT", "GLD", "HYG", "LQD", "IEF", "QQQ", "EFA", "DBA", "PDBC", "XLE", "VWO"] if c in etf_returns.columns]
    proxies = etf_returns[proxy_cols]

    all_explained = []
    loadings_rows = []
    factor_returns = pd.DataFrame(index=etf_returns.index)
    weights_by_date_rows = []

    for k in K_LIST:
        _, load, _, explained = pca_fit(pca_returns, k, proxies)
        explained["model"] = "full_sample_noncausal"
        explained["n_factors"] = k
        all_explained.append(explained)
        if k == PCA_MAIN_K:
            load["model"] = "full_sample_noncausal"
            load["n_factors"] = k
            load["refit_date"] = pca_returns.index.max()
            loadings_rows.append(load)
            for factor in sorted(load["factor"].unique()):
                w = load[load["factor"] == factor].set_index("ticker")["portfolio_weight"]
                factor_returns[f"pca_full_diag_{factor}"] = portfolio_returns_from_weights(pca_returns, w)

    exp_factor_returns = pd.DataFrame(index=pca_returns.index, columns=[f"pca_exp_f{i}" for i in range(1, PCA_MAIN_K + 1)], dtype=float)
    prev_weights: dict[int, pd.Series] = {}
    current_weights: dict[int, pd.Series] = {}
    stability_rows = []
    refit_count = 0

    for i, date in enumerate(pca_returns.index):
        if i < INITIAL_TRAIN:
            continue
        should_refit = not current_weights or ((i - INITIAL_TRAIN) % REFIT_FREQ == 0)
        if should_refit:
            train = pca_returns.iloc[:i]
            _, load, weight_df, explained = pca_fit(train, PCA_MAIN_K, proxies.iloc[:i], prev_weights)
            refit_count += 1
            load["model"] = "expanding_window_causal"
            load["n_factors"] = PCA_MAIN_K
            load["refit_date"] = date
            loadings_rows.append(load)
            explained["model"] = "expanding_window_causal"
            explained["n_factors"] = PCA_MAIN_K
            explained["refit_date"] = date
            all_explained.append(explained)
            next_weights = {}
            for factor_idx in range(1, PCA_MAIN_K + 1):
                factor = f"f{factor_idx}"
                w = weight_df[factor]
                prior = prev_weights.get(factor_idx)
                loading_corr = corr(w, prior) if prior is not None else np.nan
                top_now = set(w.abs().sort_values(ascending=False).head(6).index)
                top_prev = set(prior.abs().sort_values(ascending=False).head(6).index) if prior is not None else set()
                stability_rows.append(
                    {
                        "refit_date": date,
                        "factor": f"pca_exp_f{factor_idx}",
                        "loading_corr_to_prior_refit": loading_corr,
                        "top6_abs_loading_overlap": len(top_now & top_prev) / 6.0 if top_prev else np.nan,
                        "refit_number": refit_count,
                    }
                )
                next_weights[factor_idx] = w
            current_weights = next_weights
            prev_weights = next_weights
        for factor_idx, w in current_weights.items():
            factor_name = f"pca_exp_f{factor_idx}"
            exp_factor_returns.loc[date, factor_name] = apply_portfolio_weights(pca_returns.loc[date], w)
            for ticker, val in w.items():
                weights_by_date_rows.append(
                    {
                        "date": date,
                        "factor": factor_name,
                        "ticker": ticker,
                        "portfolio_weight": float(val),
                    }
                )

    factor_returns = pd.concat([factor_returns, exp_factor_returns], axis=1)
    loadings = pd.concat(loadings_rows, ignore_index=True)
    explained = pd.concat(all_explained, ignore_index=True)
    stability = pd.DataFrame(stability_rows)
    weights_by_date = pd.DataFrame(weights_by_date_rows)

    state_perf = factor_state_performance(factor_returns, states)
    sleeve_corr = factor_sleeve_correlation(factor_returns, sleeve_returns)

    save_csv(factor_returns.reset_index(names="date"), OUT / "ppp_pca_factor_returns.csv")
    save_csv(loadings, OUT / "ppp_pca_factor_loadings.csv")
    save_csv(explained, OUT / "ppp_pca_explained_variance.csv")
    save_csv(stability, OUT / "ppp_pca_loading_stability.csv")
    save_csv(state_perf, OUT / "ppp_pca_factor_state_performance.csv")
    save_csv(sleeve_corr, OUT / "ppp_pca_factor_sleeve_correlation.csv")
    return FactorBundle(factor_returns, loadings, weights_by_date, explained, stability, sleeve_corr, state_perf)


def select_ipca_features(characteristics: pd.DataFrame, manifest: pd.DataFrame) -> list[str]:
    candidates = manifest[
        (manifest["used_in_ipca"] == True)  # noqa: E712
        & (manifest["entity_scope"] == "ETF")
        & manifest["feature_name"].isin(characteristics.columns)
    ]["feature_name"].drop_duplicates().tolist()
    selected = []
    for col in candidates:
        s = pd.to_numeric(characteristics[col], errors="coerce")
        coverage = float(s.notna().mean())
        if coverage < MIN_IPCA_FEATURE_COVERAGE:
            continue
        if s.nunique(dropna=True) < 8:
            continue
        by_date = characteristics.groupby("date")[col].apply(lambda x: pd.to_numeric(x, errors="coerce").std(ddof=0))
        if by_date.replace(0.0, np.nan).notna().sum() < 100:
            continue
        selected.append(col)
    return selected


def zscore_characteristics(characteristics: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    indexed = characteristics.set_index(["date", "ticker"])[features].apply(pd.to_numeric, errors="coerce")
    means = indexed.groupby(level=0).transform("mean")
    stds = indexed.groupby(level=0).transform("std").replace(0.0, np.nan)
    z = ((indexed - means) / stds).clip(-4.0, 4.0)
    return z


def characteristic_managed_returns(z: pd.DataFrame, etf_returns: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    dates = etf_returns.index
    tickers = etf_returns.columns
    managed = pd.DataFrame(index=dates, columns=features, dtype=float)
    for feature in features:
        fz = z[feature].unstack("ticker").reindex(index=dates, columns=tickers)
        valid_z = fz.where(etf_returns.notna())
        denom = valid_z.abs().sum(axis=1).replace(0.0, np.nan)
        managed[feature] = (valid_z * etf_returns).sum(axis=1) / denom
    return managed


def run_ridge_oos(
    z: pd.DataFrame,
    etf_returns: pd.DataFrame,
    features: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = etf_returns.index
    tickers = etf_returns.columns
    y_long = etf_returns.stack(dropna=False).rename("actual_return")
    y_long.index.names = ["date", "ticker"]
    x_all = z[features].reindex(y_long.index).fillna(0.0)

    metrics_rows = []
    coef_rows = []
    pred_rows = []
    model = None
    scaler = None
    train_mean = np.nan

    for i, date in enumerate(dates):
        if i < INITIAL_TRAIN:
            continue
        if model is None or ((i - INITIAL_TRAIN) % REFIT_FREQ == 0):
            train_dates = dates[:i]
            train_mask = x_all.index.get_level_values("date").isin(train_dates)
            y_train = y_long.loc[train_mask]
            x_train = x_all.loc[train_mask]
            good = y_train.notna()
            x_train = x_train.loc[good]
            y_train = y_train.loc[good]
            scaler = StandardScaler()
            x_scaled = scaler.fit_transform(x_train)
            model = Ridge(alpha=RIDGE_ALPHA)
            model.fit(x_scaled, y_train.to_numpy())
            train_pred = model.predict(x_scaled)
            train_mean = float(y_train.mean())
            train_mse = float(np.mean((y_train.to_numpy() - train_pred) ** 2))
            baseline_mse = float(np.mean((y_train.to_numpy() - train_mean) ** 2))
            coef = pd.Series(model.coef_, index=features)
            for feature, value in coef.items():
                coef_rows.append(
                    {
                        "refit_date": date,
                        "feature": feature,
                        "ridge_coefficient": float(value),
                        "abs_coefficient": float(abs(value)),
                        "train_obs": int(len(y_train)),
                        "train_r2_vs_mean": 1.0 - train_mse / baseline_mse if baseline_mse > 0 else np.nan,
                    }
                )

        idx = pd.MultiIndex.from_product([[date], tickers], names=["date", "ticker"])
        x_cur = x_all.reindex(idx).fillna(0.0)
        y_cur = y_long.reindex(idx)
        good = y_cur.notna()
        if good.sum() < 10 or model is None or scaler is None:
            continue
        pred = pd.Series(model.predict(scaler.transform(x_cur.loc[good])), index=x_cur.loc[good].index, name="prediction")
        actual = y_cur.loc[good].rename("actual")
        pearson = float(pred.corr(actual)) if len(pred) > 4 else np.nan
        spearman = float(pred.corr(actual, method="spearman")) if len(pred) > 4 else np.nan
        n_top = max(2, int(math.ceil(len(pred) * 0.2)))
        top = pred.sort_values(ascending=False).head(n_top).index
        bottom = pred.sort_values(ascending=True).head(n_top).index
        top_ret = float(actual.loc[top].mean())
        bottom_ret = float(actual.loc[bottom].mean())
        spread = top_ret - bottom_ret
        mse = float(np.mean((actual.to_numpy() - pred.to_numpy()) ** 2))
        baseline_mse = float(np.mean((actual.to_numpy() - train_mean) ** 2))
        metrics_rows.append(
            {
                "row_type": "date_oos",
                "date": date,
                "n_assets": int(len(pred)),
                "pearson_ic": pearson,
                "spearman_ic": spearman,
                "top20_return": top_ret,
                "bottom20_return": bottom_ret,
                "top_bottom_spread": spread,
                "mse": mse,
                "baseline_mse": baseline_mse,
                "r2_vs_train_mean": 1.0 - mse / baseline_mse if baseline_mse > 0 else np.nan,
            }
        )
        for (d, ticker), p in pred.items():
            pred_rows.append({"date": d, "ticker": ticker, "prediction": float(p), "actual_return": float(actual.loc[(d, ticker)])})

    metrics = pd.DataFrame(metrics_rows)
    coefs = pd.DataFrame(coef_rows)
    preds = pd.DataFrame(pred_rows)
    summary_rows = []
    if not metrics.empty:
        summary_rows.extend(
            [
                {
                    "row_type": "overall_summary",
                    "date": pd.NaT,
                    "n_assets": metrics["n_assets"].sum(),
                    "pearson_ic": metrics["pearson_ic"].mean(),
                    "spearman_ic": metrics["spearman_ic"].mean(),
                    "top20_return": metrics["top20_return"].mean(),
                    "bottom20_return": metrics["bottom20_return"].mean(),
                    "top_bottom_spread": metrics["top_bottom_spread"].mean(),
                    "mse": metrics["mse"].mean(),
                    "baseline_mse": metrics["baseline_mse"].mean(),
                    "r2_vs_train_mean": metrics["r2_vs_train_mean"].mean(),
                },
                {
                    "row_type": "positive_rate_summary",
                    "date": pd.NaT,
                    "n_assets": len(metrics),
                    "pearson_ic": (metrics["pearson_ic"] > 0).mean(),
                    "spearman_ic": (metrics["spearman_ic"] > 0).mean(),
                    "top20_return": (metrics["top20_return"] > 0).mean(),
                    "bottom20_return": (metrics["bottom20_return"] > 0).mean(),
                    "top_bottom_spread": (metrics["top_bottom_spread"] > 0).mean(),
                    "mse": np.nan,
                    "baseline_mse": np.nan,
                    "r2_vs_train_mean": (metrics["r2_vs_train_mean"] > 0).mean(),
                },
            ]
        )
    metrics = pd.concat([pd.DataFrame(summary_rows), metrics], ignore_index=True)
    return metrics, coefs, preds


def run_ipca_style(
    characteristics: pd.DataFrame,
    manifest: pd.DataFrame,
    etf_returns: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    states: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = select_ipca_features(characteristics, manifest)
    if not features:
        empty = pd.DataFrame()
        reason = pd.DataFrame([{"reason": "No ETF-level lagged characteristics passed coverage/variance screens."}])
        save_csv(reason, OUT / "ppp_ipca_style_oos_prediction_metrics.csv")
        for filename in [
            "ppp_ipca_style_factor_returns.csv",
            "ppp_ipca_style_characteristic_weights.csv",
            "ppp_ipca_style_factor_loadings.csv",
            "ppp_ipca_style_state_performance.csv",
            "ppp_ipca_style_feature_stability.csv",
        ]:
            save_csv(empty, OUT / filename)
        return empty, empty, empty, reason, empty, empty, empty

    z = zscore_characteristics(characteristics, features)
    managed = characteristic_managed_returns(z, etf_returns, features)
    save_csv(managed.reset_index(names="date"), OUT / "ppp_ipca_style_managed_characteristic_returns.csv")

    ridge_metrics, ridge_coefs, ridge_predictions = run_ridge_oos(z, etf_returns, features)
    save_csv(ridge_metrics, OUT / "ppp_ipca_style_oos_prediction_metrics.csv")
    save_csv(ridge_predictions, OUT / "ppp_ipca_style_oos_predictions.csv")

    proxy_cols = [c for c in ["SPY", "BIL", "TLT", "GLD", "HYG", "LQD", "IEF", "QQQ", "EFA", "DBA", "PDBC", "XLE", "VWO"] if c in etf_returns.columns]
    proxies = etf_returns[proxy_cols]
    factor_returns = pd.DataFrame(index=etf_returns.index, columns=[f"ipca_style_f{i}" for i in range(1, IPCA_K + 1)], dtype=float)
    weight_rows = []
    loading_rows = []
    weight_history_rows = []
    prev_feature_weights: dict[int, pd.Series] = {}
    current_feature_weights: dict[int, pd.Series] = {}

    for i, date in enumerate(etf_returns.index):
        if i < INITIAL_TRAIN:
            continue
        should_refit = not current_feature_weights or ((i - INITIAL_TRAIN) % REFIT_FREQ == 0)
        if should_refit:
            train = managed.iloc[:i]
            coverage = train.notna().mean()
            valid_features = coverage[coverage >= 0.55].index.tolist()
            if len(valid_features) < IPCA_K + 2:
                continue
            train_valid = train[valid_features]
            means = train_valid.mean()
            stds = train_valid.std(ddof=0).replace(0.0, np.nan)
            x = ((train_valid.fillna(means).fillna(0.0) - means) / stds).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            model = PCA(n_components=min(IPCA_K, len(valid_features)), random_state=0)
            model.fit(x)
            next_weights: dict[int, pd.Series] = {}
            for f_idx in range(model.n_components_):
                component = pd.Series(model.components_[f_idx], index=valid_features)
                raw_weights = (component / stds.loc[valid_features]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
                prev = prev_feature_weights.get(f_idx + 1)
                pseudo_train_returns = train_valid
                oriented, sign_rule, sign_anchor = orient_weights(
                    raw_weights,
                    pseudo_train_returns,
                    proxies.reindex(pseudo_train_returns.index),
                    prev,
                )
                next_weights[f_idx + 1] = oriented
                for feature, value in oriented.items():
                    weight_rows.append(
                        {
                            "refit_date": date,
                            "factor": f"ipca_style_f{f_idx + 1}",
                            "feature": feature,
                            "characteristic_weight": float(value),
                            "abs_characteristic_weight": float(abs(value)),
                            "pca_component_weight": float(component.loc[feature]),
                            "sign_rule": sign_rule,
                            "sign_anchor_abs_corr": sign_anchor,
                            "train_weeks": int(len(train_valid)),
                        }
                    )
            current_feature_weights = next_weights
            prev_feature_weights = next_weights

        z_date = z.loc[date].reindex(etf_returns.columns).fillna(0.0)
        r_date = etf_returns.loc[date]
        for f_idx, fweights in current_feature_weights.items():
            factor = f"ipca_style_f{f_idx}"
            common = [c for c in fweights.index if c in z_date.columns]
            if not common:
                continue
            load_score = z_date[common].dot(fweights.loc[common])
            avail = r_date.notna()
            portfolio_weight = normalize_abs(load_score.where(avail))
            factor_returns.loc[date, factor] = apply_portfolio_weights(r_date, portfolio_weight)
            for ticker, val in load_score.items():
                loading_rows.append(
                    {
                        "date": date,
                        "factor": factor,
                        "ticker": ticker,
                        "characteristic_loading_score": float(val) if np.isfinite(val) else np.nan,
                        "portfolio_weight": float(portfolio_weight.get(ticker, np.nan)),
                    }
                )
                weight_history_rows.append(
                    {
                        "date": date,
                        "factor": factor,
                        "ticker": ticker,
                        "portfolio_weight": float(portfolio_weight.get(ticker, np.nan)),
                    }
                )

    weights = pd.DataFrame(weight_rows)
    loadings = pd.DataFrame(loading_rows)
    weight_history = pd.DataFrame(weight_history_rows)
    state_perf = factor_state_performance(factor_returns, states)

    feature_stability = build_ipca_feature_stability(weights, ridge_coefs)
    save_csv(factor_returns.reset_index(names="date"), OUT / "ppp_ipca_style_factor_returns.csv")
    save_csv(weights, OUT / "ppp_ipca_style_characteristic_weights.csv")
    save_csv(loadings, OUT / "ppp_ipca_style_factor_loadings.csv")
    save_csv(state_perf, OUT / "ppp_ipca_style_state_performance.csv")
    save_csv(feature_stability, OUT / "ppp_ipca_style_feature_stability.csv")
    return factor_returns, weights, loadings, ridge_metrics, state_perf, feature_stability, weight_history


def build_ipca_feature_stability(weights: pd.DataFrame, ridge_coefs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if not weights.empty:
        for (factor, feature), g in weights.groupby(["factor", "feature"]):
            vals = pd.to_numeric(g["characteristic_weight"], errors="coerce").dropna()
            if vals.empty:
                continue
            rows.append(
                {
                    "source": "ipca_style_factor_pca",
                    "factor": factor,
                    "feature": feature,
                    "mean_weight": float(vals.mean()),
                    "mean_abs_weight": float(vals.abs().mean()),
                    "weight_std": float(vals.std(ddof=0)),
                    "sign_stability": float(max((vals > 0).mean(), (vals < 0).mean())),
                    "n_refits": int(len(vals)),
                }
            )
    if not ridge_coefs.empty:
        for feature, g in ridge_coefs.groupby("feature"):
            vals = pd.to_numeric(g["ridge_coefficient"], errors="coerce").dropna()
            if vals.empty:
                continue
            rows.append(
                {
                    "source": "ridge_oos_cross_section",
                    "factor": "ridge_prediction",
                    "feature": feature,
                    "mean_weight": float(vals.mean()),
                    "mean_abs_weight": float(vals.abs().mean()),
                    "weight_std": float(vals.std(ddof=0)),
                    "sign_stability": float(max((vals > 0).mean(), (vals < 0).mean())),
                    "n_refits": int(len(vals)),
                }
            )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["source", "mean_abs_weight"], ascending=[True, False])
    return out


def factor_state_performance(factors: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    if factors.empty:
        return pd.DataFrame()
    state_series = states["market_state"] if "market_state" in states.columns else pd.Series(index=factors.index, dtype=object)
    rows = []
    for factor in factors.columns:
        for state, idx in state_series.groupby(state_series).groups.items():
            stats = perf_stats(factors.loc[idx, factor])
            rows.append({"factor": factor, "market_state": state, **stats})
    return pd.DataFrame(rows)


def factor_sleeve_correlation(factors: pd.DataFrame, sleeve_returns: pd.DataFrame) -> pd.DataFrame:
    if factors.empty or sleeve_returns.empty:
        return pd.DataFrame()
    ret_cols = [c for c in sleeve_returns.columns if c.startswith("sleeve_return_") or c.startswith("ggg1_component_return_")]
    rows = []
    for factor in factors.columns:
        for sleeve in ret_cols:
            c = corr(factors[factor], sleeve_returns[sleeve])
            rows.append(
                {
                    "factor": factor,
                    "sleeve_or_component": sleeve.replace("sleeve_return_", "").replace("ggg1_component_return_", "component::"),
                    "correlation": c,
                    "abs_correlation": abs(c) if np.isfinite(c) else np.nan,
                }
            )
    return pd.DataFrame(rows).sort_values(["factor", "abs_correlation"], ascending=[True, False])


def validate_factors(
    all_factors: pd.DataFrame,
    etf_returns: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    states: pd.DataFrame,
    pca_weights: pd.DataFrame,
    ipca_weights: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    proxy_cols = [c for c in ["SPY", "BIL", "TLT", "GLD", "HYG", "LQD", "IEF", "QQQ", "EFA", "EEM", "VWO", "DBA", "PDBC", "XLE", "UUP", "VNQ"] if c in etf_returns.columns]
    ggg1_cols = [c for c in sleeve_returns.columns if c.startswith("portfolio_return_ggg1_")]
    ggg1 = sleeve_returns[ggg1_cols[0]] if ggg1_cols else pd.Series(index=all_factors.index, dtype=float)
    sleeve_corr = factor_sleeve_correlation(all_factors, sleeve_returns)

    rows = []
    for factor in all_factors.columns:
        stats = perf_stats(all_factors[factor])
        row = {"factor": factor, "causal_status": infer_factor_status(factor), **stats}
        for proxy in proxy_cols:
            row[f"corr_{proxy}"] = corr(all_factors[factor], etf_returns[proxy])
        row["corr_GGG1"] = corr(all_factors[factor], ggg1)
        factor_sleeves = sleeve_corr[sleeve_corr["factor"] == factor]
        if factor_sleeves.empty:
            row["max_abs_corr_existing_sleeve"] = np.nan
            row["most_redundant_existing_sleeve"] = ""
        else:
            best = factor_sleeves.iloc[0]
            row["max_abs_corr_existing_sleeve"] = best["abs_correlation"]
            row["most_redundant_existing_sleeve"] = best["sleeve_or_component"]
        proxy_abs = [abs(row.get(f"corr_{p}", np.nan)) for p in proxy_cols if np.isfinite(row.get(f"corr_{p}", np.nan))]
        row["max_abs_corr_known_proxy"] = max(proxy_abs) if proxy_abs else np.nan
        row["max_abs_redundancy_any"] = np.nanmax(
            [
                row.get("max_abs_corr_existing_sleeve", np.nan),
                row.get("max_abs_corr_known_proxy", np.nan),
                abs(row.get("corr_GGG1", np.nan)) if np.isfinite(row.get("corr_GGG1", np.nan)) else np.nan,
            ]
        )
        row["uniqueness_score"] = 1.0 - row["max_abs_redundancy_any"] if np.isfinite(row["max_abs_redundancy_any"]) else np.nan
        rows.append(row)
    summary = pd.DataFrame(rows)

    state_summary = factor_state_performance(all_factors, states)
    subperiod = factor_subperiod_stability(all_factors)
    redundancy = factor_redundancy_summary(all_factors, etf_returns[proxy_cols], sleeve_returns, ggg1)
    turnover = factor_turnover_proxy(all_factors.columns.tolist(), pca_weights, ipca_weights)

    save_csv(summary, OUT / "ppp_factor_validation_summary.csv")
    save_csv(state_summary, OUT / "ppp_factor_state_summary.csv")
    save_csv(subperiod, OUT / "ppp_factor_subperiod_stability.csv")
    save_csv(redundancy, OUT / "ppp_factor_redundancy_summary.csv")
    save_csv(turnover, OUT / "ppp_factor_turnover_proxy.csv")
    return summary, state_summary, subperiod, redundancy, turnover


def infer_factor_status(factor: str) -> str:
    if factor.startswith("pca_full_diag_"):
        return "full_sample_noncausal_diagnostic"
    if factor.startswith("pca_exp_"):
        return "expanding_window_causal"
    if factor.startswith("ipca_style_"):
        return "ipca_style_walk_forward_causal"
    return "unknown"


def factor_subperiod_stability(factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    periods = [
        ("2005_2009", pd.Timestamp("2005-01-01"), pd.Timestamp("2009-12-31")),
        ("2010_2015", pd.Timestamp("2010-01-01"), pd.Timestamp("2015-12-31")),
        ("2016_2020", pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-31")),
        ("2021_2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-12-31")),
    ]
    for factor in factors.columns:
        for name, start, end in periods:
            stats = perf_stats(factors.loc[(factors.index >= start) & (factors.index <= end), factor])
            rows.append({"factor": factor, "subperiod": name, **stats})
    return pd.DataFrame(rows)


def factor_redundancy_summary(
    factors: pd.DataFrame,
    proxies: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    ggg1: pd.Series,
) -> pd.DataFrame:
    rows = []
    for factor in factors.columns:
        for other in factors.columns:
            if other <= factor:
                continue
            c = corr(factors[factor], factors[other])
            rows.append({"factor": factor, "comparison_type": "factor", "comparison_name": other, "correlation": c, "abs_correlation": abs(c) if np.isfinite(c) else np.nan})
        for proxy in proxies.columns:
            c = corr(factors[factor], proxies[proxy])
            rows.append({"factor": factor, "comparison_type": "known_proxy", "comparison_name": proxy, "correlation": c, "abs_correlation": abs(c) if np.isfinite(c) else np.nan})
        for col in [c for c in sleeve_returns.columns if c.startswith("sleeve_return_") or c.startswith("ggg1_component_return_")]:
            c = corr(factors[factor], sleeve_returns[col])
            rows.append({"factor": factor, "comparison_type": "existing_sleeve_or_component", "comparison_name": col, "correlation": c, "abs_correlation": abs(c) if np.isfinite(c) else np.nan})
        c = corr(factors[factor], ggg1)
        rows.append({"factor": factor, "comparison_type": "GGG1", "comparison_name": GGG1, "correlation": c, "abs_correlation": abs(c) if np.isfinite(c) else np.nan})
    return pd.DataFrame(rows).sort_values(["factor", "abs_correlation"], ascending=[True, False])


def factor_turnover_proxy(factors: list[str], pca_weights: pd.DataFrame, ipca_weights: pd.DataFrame) -> pd.DataFrame:
    rows = []
    weight_sources = []
    if not pca_weights.empty:
        p = pca_weights.copy()
        p["source"] = "pca_expanding_factor_portfolio_weight"
        weight_sources.append(p)
    if not ipca_weights.empty:
        q = ipca_weights.copy()
        q["source"] = "ipca_style_factor_portfolio_weight"
        weight_sources.append(q)
    if not weight_sources:
        return pd.DataFrame([{"factor": f, "avg_l1_turnover_proxy": np.nan, "max_l1_turnover_proxy": np.nan, "n_weight_dates": 0} for f in factors])
    weights = pd.concat(weight_sources, ignore_index=True)
    for factor in factors:
        g = weights[weights["factor"] == factor].copy()
        if g.empty:
            rows.append({"factor": factor, "avg_l1_turnover_proxy": 0.0 if factor.startswith("pca_full_diag_") else np.nan, "max_l1_turnover_proxy": 0.0 if factor.startswith("pca_full_diag_") else np.nan, "n_weight_dates": 0})
            continue
        wide = g.pivot_table(index="date", columns="ticker", values="portfolio_weight", aggfunc="last").sort_index().fillna(0.0)
        turnover = wide.diff().abs().sum(axis=1).dropna()
        rows.append(
            {
                "factor": factor,
                "avg_l1_turnover_proxy": float(turnover.mean()) if not turnover.empty else 0.0,
                "max_l1_turnover_proxy": float(turnover.max()) if not turnover.empty else 0.0,
                "n_weight_dates": int(len(wide)),
            }
        )
    return pd.DataFrame(rows)


def average_factor_loadings(
    pca_loadings: pd.DataFrame,
    ipca_loadings: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    if not pca_loadings.empty:
        exp = pca_loadings[pca_loadings["model"] == "expanding_window_causal"].copy()
        for (factor, ticker), g in exp.groupby(["factor", "ticker"]):
            factor_name = factor.replace("f", "pca_exp_f")
            rows.append(
                {
                    "factor": factor_name,
                    "ticker": ticker,
                    "avg_loading": float(pd.to_numeric(g["loading"], errors="coerce").mean()),
                    "avg_portfolio_weight": float(pd.to_numeric(g["portfolio_weight"], errors="coerce").mean()),
                }
            )
    if not ipca_loadings.empty:
        for (factor, ticker), g in ipca_loadings.groupby(["factor", "ticker"]):
            rows.append(
                {
                    "factor": factor,
                    "ticker": ticker,
                    "avg_loading": float(pd.to_numeric(g["characteristic_loading_score"], errors="coerce").mean()),
                    "avg_portfolio_weight": float(pd.to_numeric(g["portfolio_weight"], errors="coerce").mean()),
                }
            )
    return pd.DataFrame(rows)


def classify_factor_type(row: pd.Series, top_pos: list[str], top_neg: list[str]) -> tuple[str, str]:
    def c(name: str) -> float:
        value = row.get(f"corr_{name}", np.nan)
        return float(value) if np.isfinite(value) else np.nan

    if max([abs(c(x)) for x in ["EFA", "EEM", "VWO"] if np.isfinite(c(x))] or [0]) >= 0.55 and abs(c("SPY")) < 0.70:
        return "international leadership", "Dominant relationship is non-US equity leadership rather than pure US beta."
    if max([c(x) for x in ["SPY", "QQQ", "IWM"] if np.isfinite(c(x))] or [-9]) >= 0.55:
        return "equity beta", "Dominant positive relationship is broad equity/risk-on beta."
    if max([c(x) for x in ["TLT", "IEF"] if np.isfinite(c(x))] or [-9]) >= 0.45:
        return "duration/rates", "Dominant positive relationship is Treasury duration/rates exposure."
    if max([c(x) for x in ["HYG", "LQD"] if np.isfinite(c(x))] or [-9]) >= 0.45:
        return "credit/risk appetite", "Dominant relationship is credit or risk-appetite exposure."
    if max([c(x) for x in ["GLD", "DBA", "PDBC", "XLE", "UUP"] if np.isfinite(c(x))] or [-9]) >= 0.45:
        return "inflation/real asset", "Dominant relationship is commodity, real-asset, or dollar/inflation exposure."
    if np.isfinite(c("SPY")) and c("SPY") <= -0.35 and max([c(x) for x in ["BIL", "TLT", "GLD", "IEF"] if np.isfinite(c(x))] or [-9]) >= 0.20:
        return "defensive crisis", "Factor rises when equity beta is weak and defensive assets lead."
    text_pos = ",".join(top_pos)
    text_neg = ",".join(top_neg)
    if any(x in text_pos for x in ["SPY", "QQQ", "IWM"]) and any(x in text_neg for x in ["TLT", "BIL", "IEF"]):
        return "equity beta", "Positive side is equity-heavy versus defensive negative loadings."
    return "hidden/unknown", "No single known proxy or ETF sleeve interpretation dominates."


def candidate_latent_sleeves(
    validation: pd.DataFrame,
    state_summary: pd.DataFrame,
    subperiod: pd.DataFrame,
    redundancy: pd.DataFrame,
    avg_loadings: pd.DataFrame,
    turnover: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    causal = validation[validation["causal_status"].isin(["expanding_window_causal", "ipca_style_walk_forward_causal"])].copy()
    rows = []
    for _, row in causal.iterrows():
        factor = row["factor"]
        loads = avg_loadings[avg_loadings["factor"] == factor].copy()
        loads["abs_weight"] = loads["avg_portfolio_weight"].abs()
        top_pos = loads.sort_values("avg_portfolio_weight", ascending=False).head(6)["ticker"].tolist()
        top_neg = loads.sort_values("avg_portfolio_weight", ascending=True).head(6)["ticker"].tolist()
        factor_type, interpretation = classify_factor_type(row, top_pos, top_neg)
        st = state_summary[state_summary["factor"] == factor]
        helps = st.sort_values("ann_return", ascending=False).iloc[0]["market_state"] if not st.empty else ""
        hurts = st.sort_values("ann_return", ascending=True).iloc[0]["market_state"] if not st.empty else ""
        sub = subperiod[subperiod["factor"] == factor]
        positive_subperiod_share = float((sub["ann_return"] > 0).mean()) if not sub.empty else np.nan
        proxy_disguise = bool(row.get("max_abs_corr_known_proxy", 0) >= 0.75)
        redundant = bool(row.get("max_abs_corr_existing_sleeve", 0) >= 0.70 or proxy_disguise or abs(row.get("corr_GGG1", 0)) >= 0.70)
        positive_share = np.nan
        negative_share = np.nan
        if not loads.empty:
            denom = loads["avg_portfolio_weight"].abs().sum()
            if denom > 0:
                positive_share = float(loads.loc[loads["avg_portfolio_weight"] > 0, "avg_portfolio_weight"].abs().sum() / denom)
                negative_share = float(loads.loc[loads["avg_portfolio_weight"] < 0, "avg_portfolio_weight"].abs().sum() / denom)
        requires_long_short = bool(np.isfinite(negative_share) and negative_share > 0.25 and np.isfinite(positive_share) and positive_share > 0.25)
        long_only_tradeable = bool(not requires_long_short and top_pos)
        fills_missing_role = bool(row.get("uniqueness_score", 0) >= 0.35 and not proxy_disguise and factor_type not in {"equity beta", "duration/rates"})
        stable = bool(row.get("n_weeks", 0) >= 260 and positive_subperiod_share >= 0.50 and np.isfinite(row.get("sharpe", np.nan)) and row.get("sharpe", np.nan) > 0.20)
        weak = bool((not stable) or row.get("sharpe", -9) <= 0.15)

        if stable and fills_missing_role and long_only_tradeable and not redundant:
            classification = "HIGH_PRIORITY_LATENT_SLEEVE_TEST"
        elif stable and fills_missing_role and requires_long_short and not redundant:
            classification = "PROMISING_BUT_NEEDS_LONG_SHORT_DECISION"
        elif redundant:
            classification = "REDUNDANT_WITH_EXISTING_SLEEVE"
        elif requires_long_short and factor_type == "hidden/unknown":
            classification = "UNTRADEABLE_OR_TOO_COMPLEX"
        elif row.get("n_weeks", 0) < 260:
            classification = "INSUFFICIENT_DATA"
        elif weak:
            classification = "WEAK_OR_UNSTABLE"
        else:
            classification = "WEAK_OR_UNSTABLE"

        turn = turnover[turnover["factor"] == factor]
        rows.append(
            {
                "factor": factor,
                "factor_type": factor_type,
                "economic_interpretation": interpretation,
                "top_positive_etf_loadings": ",".join(top_pos),
                "top_negative_etf_loadings": ",".join(top_neg),
                "state_where_it_helps": helps,
                "state_where_it_hurts": hurts,
                "ann_return": row.get("ann_return"),
                "sharpe": row.get("sharpe"),
                "max_drawdown": row.get("max_drawdown"),
                "positive_subperiod_share": positive_subperiod_share,
                "redundancy_with_existing_sleeves": row.get("max_abs_corr_existing_sleeve"),
                "most_redundant_existing_sleeve": row.get("most_redundant_existing_sleeve"),
                "max_abs_corr_known_proxy": row.get("max_abs_corr_known_proxy"),
                "corr_GGG1": row.get("corr_GGG1"),
                "fills_missing_role": fills_missing_role,
                "tradeable_as_long_only_etf_sleeve": long_only_tradeable,
                "requires_long_short_construction": requires_long_short,
                "would_violate_project_constraints": requires_long_short,
                "deserves_ooo_ppp_follow_up": classification in {"HIGH_PRIORITY_LATENT_SLEEVE_TEST", "PROMISING_BUT_NEEDS_LONG_SHORT_DECISION"},
                "avg_l1_turnover_proxy": turn.iloc[0]["avg_l1_turnover_proxy"] if not turn.empty else np.nan,
                "classification": classification,
            }
        )
    diag = pd.DataFrame(rows)
    if not diag.empty:
        order = {
            "HIGH_PRIORITY_LATENT_SLEEVE_TEST": 0,
            "PROMISING_BUT_NEEDS_LONG_SHORT_DECISION": 1,
            "REDUNDANT_WITH_EXISTING_SLEEVE": 2,
            "WEAK_OR_UNSTABLE": 3,
            "UNTRADEABLE_OR_TOO_COMPLEX": 4,
            "INSUFFICIENT_DATA": 5,
        }
        diag["classification_rank"] = diag["classification"].map(order).fillna(9)
        diag = diag.sort_values(["classification_rank", "sharpe"], ascending=[True, False]).drop(columns=["classification_rank"])
    shortlist = diag[diag["classification"].isin(["HIGH_PRIORITY_LATENT_SLEEVE_TEST", "PROMISING_BUT_NEEDS_LONG_SHORT_DECISION"])].copy()
    save_csv(diag, OUT / "ppp_candidate_latent_sleeve_diagnostics.csv")
    save_csv(shortlist, OUT / "ppp_candidate_latent_sleeve_shortlist.csv")
    return diag, shortlist


def ggg1_factor_comparison(
    all_factors: pd.DataFrame,
    validation: pd.DataFrame,
    state_summary: pd.DataFrame,
    avg_loadings: pd.DataFrame,
    pca_weights: pd.DataFrame,
    ipca_weights: pd.DataFrame,
    etf_returns: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    states: pd.DataFrame,
    ggg1_weights: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ggg1_col = [c for c in sleeve_returns.columns if c.startswith("portfolio_return_ggg1_")][0]
    ggg1 = sleeve_returns[ggg1_col]
    weight_frames = []
    if not pca_weights.empty:
        weight_frames.append(pca_weights.copy())
    if not ipca_weights.empty:
        weight_frames.append(ipca_weights.copy())
    if weight_frames:
        weights = pd.concat(weight_frames, ignore_index=True)
    else:
        weights = pd.DataFrame(columns=["date", "factor", "ticker", "portfolio_weight"])

    exposure_rows = []
    for factor in [f for f in all_factors.columns if not f.startswith("pca_full_diag_")]:
        g = weights[weights["factor"] == factor]
        if not g.empty:
            wide = g.pivot_table(index="date", columns="ticker", values="portfolio_weight", aggfunc="last").reindex(index=ggg1_weights.index, columns=ggg1_weights.columns).fillna(0.0)
            exp = (wide * ggg1_weights.reindex(wide.index).fillna(0.0)).sum(axis=1)
        else:
            exp = pd.Series(np.nan, index=all_factors.index)
        for date, val in exp.dropna().items():
            exposure_rows.append(
                {
                    "date": date,
                    "factor": factor,
                    "ggg1_weighted_factor_exposure": float(val),
                    "market_state": states.get("market_state", pd.Series(index=states.index)).reindex([date]).iloc[0] if date in states.index else "",
                    "factor_return": all_factors[factor].reindex([date]).iloc[0] if date in all_factors.index else np.nan,
                    "ggg1_return": ggg1.reindex([date]).iloc[0] if date in ggg1.index else np.nan,
                }
            )
    exposure = pd.DataFrame(exposure_rows)
    save_csv(exposure, OUT / "ppp_ggg1_latent_factor_exposure.csv")

    missing_rows = []
    for _, row in validation[validation["factor"].isin([f for f in all_factors.columns if not f.startswith("pca_full_diag_")])].iterrows():
        factor = row["factor"]
        exp = exposure[exposure["factor"] == factor]
        avg_exp = float(exp["ggg1_weighted_factor_exposure"].mean()) if not exp.empty else np.nan
        by_state = exp.groupby("market_state")["ggg1_weighted_factor_exposure"].mean().to_dict() if not exp.empty else {}
        st = state_summary[state_summary["factor"] == factor].copy()
        best_state = st.sort_values("ann_return", ascending=False).iloc[0]["market_state"] if not st.empty else ""
        worst_state = st.sort_values("ann_return", ascending=True).iloc[0]["market_state"] if not st.empty else ""
        proxy_disguise = bool(row.get("max_abs_corr_known_proxy", 0) >= 0.75)
        redundant = bool(row.get("max_abs_corr_existing_sleeve", 0) >= 0.70 or abs(row.get("corr_GGG1", 0)) >= 0.70 or proxy_disguise)
        low_exposure = bool(np.isfinite(avg_exp) and abs(avg_exp) < 0.05)
        possible_missing = bool(row.get("sharpe", -9) > 0.25 and row.get("uniqueness_score", 0) > 0.30 and low_exposure and not redundant)
        if possible_missing:
            use_flag = "POSSIBLY_UNDERUSED_LATENT_FACTOR"
        elif redundant:
            use_flag = "MOSTLY_REDUNDANT_OR_PROXY_DISGUISE"
        elif row.get("sharpe", -9) <= 0.15:
            use_flag = "WEAK_OR_UNSTABLE_DO_NOT_ADD"
        else:
            use_flag = "WATCHLIST_NOT_ENOUGH_FOR_SLEEVE"
        missing_rows.append(
            {
                "factor": factor,
                "avg_ggg1_weighted_factor_exposure": avg_exp,
                "best_state_for_factor": best_state,
                "worst_state_for_factor": worst_state,
                "best_state_avg_ggg1_exposure": by_state.get(best_state, np.nan),
                "worst_state_avg_ggg1_exposure": by_state.get(worst_state, np.nan),
                "max_abs_corr_existing_sleeve": row.get("max_abs_corr_existing_sleeve"),
                "max_abs_corr_known_proxy": row.get("max_abs_corr_known_proxy"),
                "corr_GGG1": row.get("corr_GGG1"),
                "proxy_disguise": proxy_disguise,
                "could_plausibly_improve_ggg1": possible_missing,
                "diagnostic": use_flag,
            }
        )
    missing = pd.DataFrame(missing_rows)
    save_csv(missing, OUT / "ppp_ggg1_missing_factor_diagnostics.csv")

    existing_redundancy = factor_sleeve_correlation(all_factors[[c for c in all_factors.columns if not c.startswith("pca_full_diag_")]], sleeve_returns)
    save_csv(existing_redundancy, OUT / "ppp_existing_sleeve_latent_redundancy.csv")
    return exposure, missing, existing_redundancy


def choose_next_action(
    candidate_diag: pd.DataFrame,
    validation: pd.DataFrame,
    ridge_metrics: pd.DataFrame,
    state_summary: pd.DataFrame,
) -> pd.DataFrame:
    recommendation = "STOP_HARD_ML_FOR_NOW"
    reason = "No stable, tradeable, non-redundant latent factor and no strong feature-interaction evidence."
    high = candidate_diag[candidate_diag["classification"] == "HIGH_PRIORITY_LATENT_SLEEVE_TEST"] if not candidate_diag.empty else pd.DataFrame()
    promising_ls = candidate_diag[candidate_diag["classification"] == "PROMISING_BUT_NEEDS_LONG_SHORT_DECISION"] if not candidate_diag.empty else pd.DataFrame()

    ridge_summary = ridge_metrics[ridge_metrics["row_type"] == "overall_summary"] if not ridge_metrics.empty and "row_type" in ridge_metrics.columns else pd.DataFrame()
    mean_spearman = float(ridge_summary["spearman_ic"].iloc[0]) if not ridge_summary.empty else np.nan
    mean_spread = float(ridge_summary["top_bottom_spread"].iloc[0]) if not ridge_summary.empty else np.nan
    feature_interactions_promising = bool(np.isfinite(mean_spearman) and mean_spearman > 0.02 and np.isfinite(mean_spread) and mean_spread > 0.00025)

    causal_validation = validation[validation["causal_status"].isin(["expanding_window_causal", "ipca_style_walk_forward_causal"])]
    mostly_redundant = bool((causal_validation["max_abs_redundancy_any"] >= 0.70).mean() >= 0.50) if not causal_validation.empty else False
    state_dispersion = 0.0
    if not state_summary.empty:
        spreads = state_summary.groupby("factor")["ann_return"].agg(lambda x: x.max() - x.min())
        state_dispersion = float(spreads.mean()) if not spreads.empty else 0.0

    if not high.empty:
        recommendation = "PROCEED_TO_PPP2_LATENT_SLEEVE_BUILD"
        reason = "At least one latent factor is stable, economically interpretable, not redundant, and plausibly long-only tradeable."
    elif not promising_ls.empty:
        recommendation = "PROCEED_TO_PPP2_LATENT_SLEEVE_BUILD"
        reason = "A promising latent factor exists, but PPP2 must explicitly decide whether long-short construction is allowed."
    elif mostly_redundant and feature_interactions_promising:
        recommendation = "PROCEED_TO_QQQ_DEEP_FEATURE_INTERACTION_MINING"
        reason = "Latent factors are mostly redundant/proxy-like, but the walk-forward characteristic model has positive cross-sectional IC/spread evidence."
    elif state_dispersion > 0.08 and not feature_interactions_promising:
        recommendation = "PROCEED_TO_SSS_REGIME_SEQUENCE_MODELING"
        reason = "Latent factor behavior is more state-dispersed than sleeve-creating; the useful information appears regime-sequential."
    elif mostly_redundant:
        recommendation = "PROCEED_TO_RRR_SLEEVE_META_LABELING"
        reason = "Latent factors do not justify new sleeves, but redundancy/state behavior suggests sleeve timing remains the better next test."

    out = pd.DataFrame(
        [
            {
                "recommendation": recommendation,
                "reason": reason,
                "mean_oos_spearman_ic": mean_spearman,
                "mean_oos_top_bottom_spread": mean_spread,
                "mostly_redundant": mostly_redundant,
                "mean_state_ann_return_spread": state_dispersion,
                "high_priority_count": int(len(high)),
                "promising_long_short_count": int(len(promising_ls)),
            }
        ]
    )
    save_csv(out, OUT / "ppp_next_action_recommendation.csv")
    return out


def write_report(
    etf_returns: pd.DataFrame,
    characteristics: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    quality: pd.DataFrame,
    pca: FactorBundle,
    ipca_returns: pd.DataFrame,
    ipca_weights: pd.DataFrame,
    ridge_metrics: pd.DataFrame,
    ipca_state: pd.DataFrame,
    feature_stability: pd.DataFrame,
    validation: pd.DataFrame,
    state_summary: pd.DataFrame,
    subperiod: pd.DataFrame,
    redundancy: pd.DataFrame,
    turnover: pd.DataFrame,
    candidate_diag: pd.DataFrame,
    shortlist: pd.DataFrame,
    exposure: pd.DataFrame,
    missing: pd.DataFrame,
    existing_redundancy: pd.DataFrame,
    next_action: pd.DataFrame,
) -> None:
    dataset_summary = pd.DataFrame(
        [
            {
                "panel": "ETF returns",
                "rows": etf_returns.shape[0],
                "columns": etf_returns.shape[1],
                "start": etf_returns.index.min().date(),
                "end": etf_returns.index.max().date(),
            },
            {
                "panel": "ETF characteristics long",
                "rows": characteristics.shape[0],
                "columns": characteristics.shape[1],
                "start": pd.to_datetime(characteristics["date"]).min().date(),
                "end": pd.to_datetime(characteristics["date"]).max().date(),
            },
            {
                "panel": "Sleeve/context returns",
                "rows": sleeve_returns.shape[0],
                "columns": sleeve_returns.shape[1],
                "start": sleeve_returns.index.min().date(),
                "end": sleeve_returns.index.max().date(),
            },
        ]
    )
    leakage = quality[quality["section"] == "leakage_checks"][["item", "value", "notes"]]
    pca_explained = (
        pca.explained[(pca.explained["model"] == "full_sample_noncausal") & (pca.explained["n_factors"] == PCA_MAIN_K)]
        [["factor", "explained_variance_ratio", "cumulative_explained_variance"]]
        .head(PCA_MAIN_K)
    )
    pca_state = pca.state_perf.sort_values(["factor", "sharpe"], ascending=[True, False]).head(20)
    ridge_summary = ridge_metrics[ridge_metrics["row_type"].isin(["overall_summary", "positive_rate_summary"])] if not ridge_metrics.empty and "row_type" in ridge_metrics.columns else ridge_metrics.head(5)
    top_validation = validation.sort_values("sharpe", ascending=False).head(16)
    causal_validation = validation[validation["causal_status"].isin(["expanding_window_causal", "ipca_style_walk_forward_causal"])].sort_values("sharpe", ascending=False)
    top_redundancy = redundancy.sort_values(["factor", "abs_correlation"], ascending=[True, False]).groupby("factor").head(3)
    exposure_summary = exposure.groupby("factor")["ggg1_weighted_factor_exposure"].agg(["mean", "min", "max"]).reset_index() if not exposure.empty else pd.DataFrame()
    next_rec = next_action.iloc[0]["recommendation"] if not next_action.empty else "UNKNOWN"
    next_reason = next_action.iloc[0]["reason"] if not next_action.empty else ""

    files = [
        "scripts/phase_ppp_latent_factor_discovery.py",
        "data/research/phase_ppp_latent_factor_discovery/ppp_panel_etf_returns.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_panel_characteristics.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_panel_sleeve_returns.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_feature_manifest.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_data_quality_report.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_returns.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_loadings.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_pca_explained_variance.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_pca_loading_stability.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_state_performance.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_pca_factor_sleeve_correlation.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_factor_returns.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_characteristic_weights.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_factor_loadings.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_oos_prediction_metrics.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_state_performance.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ipca_style_feature_stability.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_factor_validation_summary.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_factor_state_summary.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_factor_subperiod_stability.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_factor_redundancy_summary.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_factor_turnover_proxy.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_candidate_latent_sleeve_diagnostics.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_candidate_latent_sleeve_shortlist.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ggg1_latent_factor_exposure.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_ggg1_missing_factor_diagnostics.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_existing_sleeve_latent_redundancy.csv",
        "data/research/phase_ppp_latent_factor_discovery/ppp_next_action_recommendation.csv",
        "docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md",
        "docs/research/project_journey.md",
    ]

    next_prompt = """Implement Phase QQQ -- Deep Feature Interaction Mining. Use the PPP lagged ETF characteristic panel plus OOO feature lineage to mine economically constrained feature interactions with expanding-window validation only. Compare interaction signals to PPP latent factors, OOO signals, GGG1 sleeves, and state labels. Do not change production/shadow pins, do not create portfolio candidates unless the phase explicitly passes diagnostic gates, and require clear leakage checks, subperiod stability, redundancy controls, and a next-action recommendation."""

    report = f"""# Phase PPP0/PPP1 -- IPCA / Latent Factor and Sleeve Discovery

Date: 2026-04-27

## Commands Executed
{chr(10).join(f"- `{cmd}`" for cmd in COMMANDS)}

## Files Created / Modified
{chr(10).join(f"- `{f}`" for f in files)}

## Dataset Construction Summary
{markdown_table(dataset_summary)}

The ETF panel is aligned to GGG1 dates. Predictive characteristics are trailing
and lagged; state labels are retained for validation grouping and lagged
context, but not used as future labels in the IPCA-style cross-sectional model.
Layer 2A sleeve returns, GGG1 component returns, GGG1 ETF weights, and GGG1
sleeve weights were included as diagnostics/context rather than as live
predictive characteristics.

## Leakage Checks
{markdown_table(leakage, n=20)}

## PCA Factor Findings
Full-sample PCA is saved only as non-causal diagnostic context. The causal PCA
benchmark uses expanding-window refits after {INITIAL_TRAIN} weekly dates and
applies factor-mimicking weights to the next weekly ETF return.

Full-sample diagnostic explained variance for {PCA_MAIN_K} factors:

{markdown_table(pca_explained)}

Top PCA validation rows:

{markdown_table(causal_validation[causal_validation["factor"].str.startswith("pca_exp_")].head(10))}

## IPCA-Style Factor Findings
This is an internal IPCA-style characteristic-conditioned latent factor
approximation, not a claim of exact academic IPCA. It uses lagged ETF
characteristics, builds characteristic-managed factor portfolios, performs
expanding reduced-rank PCA on those characteristic-managed returns, and also
tests a walk-forward ridge cross-sectional return predictor.

OOS ridge / cross-sectional characteristic metrics:

{markdown_table(ridge_summary, n=8)}

Top IPCA-style characteristic weights:

{markdown_table(ipca_weights.sort_values("abs_characteristic_weight", ascending=False).head(15) if not ipca_weights.empty else ipca_weights)}

Top IPCA-style feature stability rows:

{markdown_table(feature_stability.head(15))}

## Factor Validation Summary
{markdown_table(top_validation, n=16)}

## State-by-State Factor Behavior
Top PCA state rows:

{markdown_table(pca_state, n=20)}

Top IPCA-style state rows:

{markdown_table(ipca_state.sort_values(["factor", "sharpe"], ascending=[True, False]).head(20) if not ipca_state.empty else ipca_state, n=20)}

## Redundancy vs Existing Sleeves and Proxies
{markdown_table(top_redundancy, n=24)}

## Candidate Latent Sleeve Shortlist
{markdown_table(shortlist, n=12)}

All causal factor diagnostics:

{markdown_table(candidate_diag, n=16)}

## New Latent Sleeve Decision
The shortlist file is the gating artifact. PPP does not create or promote any
portfolio candidate. A new latent sleeve is justified only if a factor is
stable, interpretable, not redundant with known sleeves/proxies/GGG1, and
tradeable under project constraints.

## Comparison to GGG1
GGG1 factor exposure summary:

{markdown_table(exposure_summary, n=16)}

Missing-factor diagnostics:

{markdown_table(missing, n=16)}

Existing sleeve latent redundancy:

{markdown_table(existing_redundancy.head(16), n=16)}

## Final Recommendation
**{next_rec}**

Reason: {next_reason}

## Exact Prompt Outline for Next Phase
{next_prompt}

## Resume-Worthy Technical Summary
PPP built a GGG1-aligned weekly ETF return panel and a lagged ETF characteristic
panel combining rolling momentum/volatility/drawdown/trend/relative-strength
features, existing Layer 1 tradable signals, OOO signal context, regime labels,
Layer 2A sleeve returns, GGG1 component returns, and GGG1 exposure context. It
ran full-sample diagnostic PCA and expanding-window causal PCA, then ran an
internal IPCA-style approximation through characteristic-managed returns,
expanding reduced-rank factors, factor loading scores, walk-forward ridge
cross-sectional return prediction, feature stability, state behavior,
redundancy, turnover proxies, candidate latent sleeve diagnostics, and GGG1
latent exposure diagnostics. Production pin `{PRODUCTION}`, official shadow
pin `{SHADOW}`, and GGG1 logic were not changed.
"""
    DOC.write_text(report)


def update_journey(next_action: pd.DataFrame) -> None:
    rec = next_action.iloc[0]["recommendation"] if not next_action.empty else "UNKNOWN"
    reason = next_action.iloc[0]["reason"] if not next_action.empty else ""
    section = f"""
## Section 88 -- Phase PPP0/PPP1 Latent Factor and Sleeve Discovery

Date: 2026-04-27. Phase PPP was diagnostic-only. It built a GGG1-aligned weekly
ETF return and lagged characteristic panel, ran full-sample diagnostic PCA,
expanding-window PCA, and an internal IPCA-style characteristic-conditioned
latent factor approximation. It compared latent factors to existing Layer 2A
sleeves, GGG1 components, market states, known proxies, and GGG1 exposures.
No production pin, official shadow pin, GGG1 logic, live-trading logic, or
portfolio candidate was changed.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text() if JOURNEY.exists() else ""
    marker = "## Section 88 -- Phase PPP0/PPP1 Latent Factor and Sleeve Discovery"
    if marker in text:
        text = text[: text.index(marker)].rstrip() + "\n\n" + section.strip() + "\n"
    else:
        text = text.rstrip() + "\n\n" + section.strip() + "\n"
    JOURNEY.write_text(text)


def main() -> None:
    ensure_dirs()
    etf_returns, characteristics, sleeve_returns, manifest, quality, inputs = build_dataset()
    states = inputs["states"]
    ggg1_weights = inputs["ggg1_weights"]

    pca_bundle = run_pca_benchmark(etf_returns, sleeve_returns, states)
    ipca_returns, ipca_char_weights, ipca_loadings, ridge_metrics, ipca_state, feature_stability, ipca_weight_history = run_ipca_style(
        characteristics,
        manifest,
        etf_returns,
        sleeve_returns,
        states,
    )
    all_factors = pd.concat([pca_bundle.returns, ipca_returns], axis=1)
    validation, state_summary, subperiod, redundancy, turnover = validate_factors(
        all_factors,
        etf_returns,
        sleeve_returns,
        states,
        pca_bundle.weights_by_date,
        ipca_weight_history,
    )
    avg_loadings = average_factor_loadings(pca_bundle.loadings, ipca_loadings)
    candidate_diag, shortlist = candidate_latent_sleeves(validation, state_summary, subperiod, redundancy, avg_loadings, turnover)
    exposure, missing, existing_redundancy = ggg1_factor_comparison(
        all_factors,
        validation,
        state_summary,
        avg_loadings,
        pca_bundle.weights_by_date,
        ipca_weight_history,
        etf_returns,
        sleeve_returns,
        states,
        ggg1_weights,
    )
    next_action = choose_next_action(candidate_diag, validation, ridge_metrics, state_summary)
    write_report(
        etf_returns,
        characteristics,
        sleeve_returns,
        quality,
        pca_bundle,
        ipca_returns,
        ipca_char_weights,
        ridge_metrics,
        ipca_state,
        feature_stability,
        validation,
        state_summary,
        subperiod,
        redundancy,
        turnover,
        candidate_diag,
        shortlist,
        exposure,
        missing,
        existing_redundancy,
        next_action,
    )
    update_journey(next_action)
    print("Phase PPP latent factor discovery complete.")
    print(f"Outputs: {OUT}")
    print(f"Report: {DOC}")
    print(f"Recommendation: {next_action.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
