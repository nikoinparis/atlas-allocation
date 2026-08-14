"""Shared research-only helpers for the Renaissance-inspired R1-R4 sprint.

The helpers in this module deliberately avoid production side effects. They only
read existing project inputs and return DataFrames that the research scripts can
write into research-only locations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DATA_DIR = Path("data")
HUB_DIR = DATA_DIR / "01_data_hub"
SIGNAL_DIR = DATA_DIR / "02_layer1_signals"
REGIME_DIR = DATA_DIR / "04_layer2b_risk_regime_engine"
PORTFOLIO_DIR = DATA_DIR / "05_layer3_portfolio_construction"
DOCS_RESEARCH_DIR = Path("docs") / "research"

HORIZONS = [1, 2, 4, 8, 13]
HOLDOUT_START = pd.Timestamp("2020-01-01")


@dataclass
class LoadResult:
    frame: pd.DataFrame
    warnings: list[str]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_csv_safe(path: Path, warnings: list[str], **kwargs) -> pd.DataFrame:
    if not path.exists():
        warnings.append(f"Missing optional file: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive research guard
        warnings.append(f"Could not read {path}: {exc}")
        return pd.DataFrame()


def parse_dates(df: pd.DataFrame, warnings: list[str], path_label: str = "frame") -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "Date" not in out.columns and "Unnamed: 0" in out.columns:
        out = out.rename(columns={"Unnamed: 0": "Date"})
    if "Date" not in out.columns:
        warnings.append(f"{path_label} has no Date column")
        return out
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).sort_values("Date")
    return out


def load_weekly_prices(warnings: list[str]) -> pd.DataFrame:
    prices = read_csv_safe(HUB_DIR / "weekly_prices.csv", warnings)
    prices = parse_dates(prices, warnings, "weekly_prices.csv")
    if prices.empty or "Date" not in prices.columns:
        return pd.DataFrame()
    return prices.set_index("Date").sort_index()


def load_weekly_returns(warnings: list[str]) -> pd.DataFrame:
    returns = read_csv_safe(HUB_DIR / "weekly_returns.csv", warnings)
    returns = parse_dates(returns, warnings, "weekly_returns.csv")
    if returns.empty or "Date" not in returns.columns:
        return pd.DataFrame()
    return returns.set_index("Date").sort_index()


def load_market_states(warnings: list[str]) -> pd.DataFrame:
    states = read_csv_safe(REGIME_DIR / "market_state_history.csv", warnings)
    states = parse_dates(states, warnings, "market_state_history.csv")
    if states.empty:
        return states
    if "market_state" not in states.columns:
        warnings.append("market_state_history.csv lacks market_state column")
        return pd.DataFrame(columns=["Date", "market_state"])
    return states[["Date", "market_state"]].dropna()


def load_manifest(warnings: list[str]) -> list[dict]:
    path = SIGNAL_DIR / "signal_manifest.json"
    if not path.exists():
        warnings.append(f"Missing signal manifest: {path}")
        return []
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:  # pragma: no cover - defensive research guard
        warnings.append(f"Could not parse {path}: {exc}")
        return []
    if not isinstance(payload, list):
        warnings.append(f"Unexpected manifest shape in {path}")
        return []
    return [item for item in payload if isinstance(item, dict)]


def load_universe_metadata(warnings: list[str]) -> pd.DataFrame:
    metadata = read_csv_safe(HUB_DIR / "universe_metadata.csv", warnings)
    if metadata.empty or "ticker" not in metadata.columns:
        prices = load_weekly_prices(warnings)
        tickers = [c for c in prices.columns if c != "Date"]
        return pd.DataFrame({"ticker": tickers, "asset_class": "Unknown"})
    if "asset_class" not in metadata.columns:
        metadata["asset_class"] = "Unknown"
    return metadata[["ticker", "asset_class"]].drop_duplicates()


def asset_risk_loading(ticker: str, asset_class: str | float | None = None) -> float:
    """Static risk-on loading used to make macro time-series cross-sectional.

    The values are intentionally simple, inspectable priors rather than fitted
    parameters. They let a macro/risk-on series rank ETFs without optimizing.
    """

    ticker = str(ticker).upper()
    overrides = {
        "BIL": -1.0,
        "SHY": -0.9,
        "IEF": -0.65,
        "TLT": -0.75,
        "LQD": -0.45,
        "MBB": -0.55,
        "TIP": -0.25,
        "HYG": 0.55,
        "GLD": 0.10,
        "IAU": 0.10,
        "SLV": 0.40,
        "UUP": -0.35,
        "USO": 0.75,
        "PDBC": 0.70,
        "DBA": 0.45,
        "XLE": 0.80,
    }
    if ticker in overrides:
        return overrides[ticker]
    cls = "" if asset_class is None or pd.isna(asset_class) else str(asset_class).lower()
    if "bond" in cls:
        return -0.55
    if "cash" in cls:
        return -1.0
    if "commod" in cls:
        return 0.55
    if "real" in cls:
        return 0.75
    if "equ" in cls:
        return 1.0
    return 0.0


def dollar_loading(ticker: str) -> float:
    ticker = str(ticker).upper()
    if ticker == "UUP":
        return 1.0
    if ticker in {"EEM", "EFA", "VWO", "VEA", "EWJ"}:
        return -1.0
    if ticker in {"GLD", "IAU", "SLV", "USO", "PDBC", "DBA", "XLE"}:
        return -0.65
    if ticker in {"BIL", "SHY"}:
        return 0.25
    if ticker in {"SPY", "QQQ", "IWM", "VTV", "VUG", "XLK", "XLF", "XLI", "XLP", "XLU", "XLV", "XLY", "XLB"}:
        return -0.15
    return 0.0


def commodity_loading(ticker: str) -> float:
    ticker = str(ticker).upper()
    if ticker in {"USO", "PDBC", "DBA", "SLV", "XLE"}:
        return 1.0
    if ticker in {"GLD", "IAU", "TIP"}:
        return 0.45
    if ticker in {"TLT", "IEF", "LQD", "MBB", "SHY", "BIL"}:
        return -0.45
    if ticker == "UUP":
        return -0.40
    if ticker in {"SPY", "QQQ", "IWM", "EEM", "EFA", "VEA", "VWO"}:
        return 0.20
    return 0.0


def rolling_z(series: pd.Series, window: int = 156, min_periods: int = 52) -> pd.Series:
    mean = series.rolling(window=window, min_periods=min_periods).mean()
    std = series.rolling(window=window, min_periods=min_periods).std(ddof=0)
    return (series - mean) / std.replace(0, np.nan)


def robust_z(series: pd.Series, window: int = 156, min_periods: int = 52) -> pd.Series:
    return rolling_z(series.astype(float), window=window, min_periods=min_periods).clip(-4, 4)


def attach_tradable_lag(frame: pd.DataFrame, value_col: str = "signal_value_observed") -> pd.DataFrame:
    out = frame.sort_values(["Ticker", "Date"]).copy()
    out["signal_value_tradable"] = out.groupby("Ticker", group_keys=False)[value_col].shift(1)
    return out


def panel_from_series(
    series: pd.Series,
    signal_name: str,
    loadings: dict[str, float],
    source: str,
    frequency: str,
    notes: str = "",
) -> pd.DataFrame:
    rows: list[dict] = []
    clean = series.sort_index()
    for ticker, loading in loadings.items():
        observed = clean * loading
        part = pd.DataFrame(
            {
                "Date": observed.index,
                "Ticker": ticker,
                "signal_name": signal_name,
                "signal_value_observed": observed.values,
                "source": source,
                "frequency": frequency,
                "lag_periods": 1,
                "research_only": True,
                "notes": notes,
            }
        )
        rows.append(part)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return attach_tradable_lag(out)


def forward_returns_from_prices(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    numeric = prices.apply(pd.to_numeric, errors="coerce")
    return numeric.shift(-horizon) / numeric - 1.0


def spearman_ic(x: pd.Series, y: pd.Series, min_obs: int = 5) -> float:
    aligned = pd.concat([x, y], axis=1).dropna()
    if len(aligned) < min_obs:
        return np.nan
    if aligned.iloc[:, 0].nunique() < 2 or aligned.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman"))


def newey_west_tstat(values: Iterable[float], max_lag: int | None = None) -> float:
    x = pd.Series(values, dtype="float64").dropna().to_numpy()
    n = len(x)
    if n < 3:
        return np.nan
    demeaned = x - x.mean()
    if max_lag is None:
        max_lag = max(1, int(round(4 * (n / 100.0) ** (2.0 / 9.0))))
    max_lag = min(max_lag, n - 1)
    gamma0 = float(np.dot(demeaned, demeaned) / n)
    long_run_var = gamma0
    for lag in range(1, max_lag + 1):
        cov = float(np.dot(demeaned[lag:], demeaned[:-lag]) / n)
        weight = 1.0 - lag / (max_lag + 1.0)
        long_run_var += 2.0 * weight * cov
    if long_run_var <= 0:
        return np.nan
    se_mean = np.sqrt(long_run_var / n)
    if se_mean == 0:
        return np.nan
    return float(x.mean() / se_mean)


def signal_column_for_name(df: pd.DataFrame, signal_name: str) -> str | None:
    explicit = {
        "tsmom_vol_scaled": "tsmom_score_tradable",
        "xsmom_global": "xsmom_score_tradable",
        "xsmom_asset_class_neutral": "xsmom_asset_class_neutral_tradable",
        "reversal_1w_global": "reversal_1w_score_tradable",
        "reversal_4w_global": "reversal_4w_score_tradable",
        "reversal_1w_asset_class_neutral": "reversal_1w_asset_class_neutral_tradable",
        "reversal_4w_asset_class_neutral": "reversal_4w_asset_class_neutral_tradable",
        "multi_mom_equal": "multi_mom_equal_score_tradable",
        "multi_mom_invvol": "multi_mom_invvol_score_tradable",
        "residual_momentum": "residual_mom_score_tradable",
        "carry_proxy": "carry_score_tradable",
        "carry_proxy_asset_class_neutral": "carry_score_asset_class_neutral_tradable",
        "value_proxy": "value_score_tradable",
        "value_proxy_asset_class_neutral": "value_score_asset_class_neutral_tradable",
        "bab_proxy": "bab_score_tradable",
        "bab_proxy_asset_class_neutral": "bab_score_asset_class_neutral_tradable",
        "quality_proxy": "quality_score_tradable",
        "quality_proxy_asset_class_neutral": "quality_score_asset_class_neutral_tradable",
        "trend_clarity_momentum": "trend_clarity_momentum_score_tradable",
        "moving_average_distance": "moving_average_distance_score_tradable",
        "breadth_confirmed_momentum": "breadth_confirmed_momentum_score_tradable",
        "contained_recovery_quality": "contained_recovery_quality_score_tradable",
        "vix_term_structure_regime": "vix_slope_risk_off_z_tradable",
        "macro_risk_score": "macro_risk_score_tradable",
        "google_fear_regime": "google_fear_z_tradable",
    }
    if explicit.get(signal_name) in df.columns:
        return explicit[signal_name]
    candidates = [
        f"{signal_name}_score_tradable",
        f"{signal_name}_tradable",
        "signal_value_tradable",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    tradable_cols = [c for c in df.columns if c.endswith("_tradable") and pd.api.types.is_numeric_dtype(df[c])]
    if len(tradable_cols) == 1:
        return tradable_cols[0]
    scored = [c for c in tradable_cols if "score" in c]
    if len(scored) == 1:
        return scored[0]
    return None


def load_existing_signal_panel(signal_name: str, manifest: list[dict], warnings: list[str]) -> pd.DataFrame:
    item = next((entry for entry in manifest if entry.get("signal_name") == signal_name), None)
    if not item:
        warnings.append(f"No manifest entry for existing signal {signal_name}")
        return pd.DataFrame()
    file_name = item.get("file_name")
    if not file_name:
        warnings.append(f"Manifest entry for {signal_name} has no file_name")
        return pd.DataFrame()
    path = SIGNAL_DIR / file_name
    df = read_csv_safe(path, warnings)
    df = parse_dates(df, warnings, str(path))
    if df.empty:
        return df
    col = signal_column_for_name(df, signal_name)
    if col is None:
        warnings.append(f"Could not identify tradable column for {signal_name} in {path}")
        return pd.DataFrame()
    if "Ticker" in df.columns:
        out = df[["Date", "Ticker", col]].rename(columns={col: "signal_value_tradable"}).copy()
        out["signal_name"] = signal_name
        return out.dropna(subset=["Date", "Ticker"])
    metadata = load_universe_metadata(warnings)
    loadings = {
        row.ticker: asset_risk_loading(row.ticker, row.asset_class)
        for row in metadata.itertuples(index=False)
    }
    series = df.set_index("Date")[col].astype(float)
    panel = panel_from_series(
        series,
        signal_name=signal_name,
        loadings=loadings,
        source=str(path),
        frequency="weekly",
        notes="Existing time-series regime feature expanded with static asset risk loadings.",
    )
    return panel[["Date", "Ticker", "signal_name", "signal_value_tradable"]]


def load_candidate_signal_panel(path: Path, warnings: list[str]) -> pd.DataFrame:
    df = read_csv_safe(path, warnings)
    df = parse_dates(df, warnings, str(path))
    if df.empty:
        return df
    if "signal_name" not in df.columns:
        df["signal_name"] = path.stem
    if "signal_value_tradable" not in df.columns:
        if "signal_value_observed" in df.columns and "Ticker" in df.columns:
            df = attach_tradable_lag(df)
        else:
            warnings.append(f"{path} has no signal_value_tradable column")
            return pd.DataFrame()
    if "Ticker" not in df.columns:
        warnings.append(f"{path} is not panel-shaped; skipping cross-sectional validation")
        return pd.DataFrame()
    return df[["Date", "Ticker", "signal_name", "signal_value_tradable"]].dropna(subset=["Date", "Ticker"])


def cross_sectional_ic_by_date(
    signal_panel: pd.DataFrame,
    prices: pd.DataFrame,
    horizon: int,
    min_assets: int = 5,
) -> pd.DataFrame:
    if signal_panel.empty or prices.empty:
        return pd.DataFrame(columns=["Date", "ic", "n_assets"])
    fwd = forward_returns_from_prices(prices, horizon)
    panel = signal_panel.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last")
    common_dates = panel.index.intersection(fwd.index)
    common_tickers = [c for c in panel.columns if c in fwd.columns]
    rows: list[dict] = []
    for date in common_dates:
        ic = spearman_ic(panel.loc[date, common_tickers], fwd.loc[date, common_tickers], min_obs=min_assets)
        n_assets = int(pd.concat([panel.loc[date, common_tickers], fwd.loc[date, common_tickers]], axis=1).dropna().shape[0])
        if pd.notna(ic):
            rows.append({"Date": date, "ic": ic, "n_assets": n_assets})
    return pd.DataFrame(rows)


def summarize_ic(ic_by_date: pd.DataFrame) -> dict:
    if ic_by_date.empty:
        return {
            "mean_ic": np.nan,
            "ic_tstat_nw": np.nan,
            "hit_rate": np.nan,
            "n_dates": 0,
            "mean_coverage": np.nan,
        }
    return {
        "mean_ic": float(ic_by_date["ic"].mean()),
        "ic_tstat_nw": newey_west_tstat(ic_by_date["ic"]),
        "hit_rate": float((ic_by_date["ic"] > 0).mean()),
        "n_dates": int(len(ic_by_date)),
        "mean_coverage": float(ic_by_date["n_assets"].mean()),
    }


def evaluate_panel_signal(
    signal_panel: pd.DataFrame,
    prices: pd.DataFrame,
    horizons: Iterable[int] = HORIZONS,
    min_assets: int = 5,
) -> pd.DataFrame:
    rows: list[dict] = []
    signal_name = signal_panel["signal_name"].dropna().iloc[0] if not signal_panel.empty else "unknown"
    for horizon in horizons:
        ic_dates = cross_sectional_ic_by_date(signal_panel, prices, horizon, min_assets=min_assets)
        full = summarize_ic(ic_dates)
        holdout = summarize_ic(ic_dates[ic_dates["Date"] >= HOLDOUT_START]) if not ic_dates.empty else summarize_ic(ic_dates)
        row = {
            "signal_name": signal_name,
            "horizon_weeks": horizon,
            **{f"full_{k}": v for k, v in full.items()},
            **{f"holdout_{k}": v for k, v in holdout.items()},
        }
        rows.append(row)
    return pd.DataFrame(rows)


def state_conditional_ic_rows(
    signal_panel: pd.DataFrame,
    prices: pd.DataFrame,
    states: pd.DataFrame,
    horizons: Iterable[int] = HORIZONS,
    min_assets: int = 5,
) -> pd.DataFrame:
    if signal_panel.empty:
        return pd.DataFrame()
    signal_name = signal_panel["signal_name"].dropna().iloc[0]
    state_map = states.set_index("Date")["market_state"] if not states.empty else pd.Series(dtype=object)
    rows: list[dict] = []
    for horizon in horizons:
        ic_dates = cross_sectional_ic_by_date(signal_panel, prices, horizon, min_assets=min_assets)
        if ic_dates.empty:
            rows.append(
                {
                    "signal_name": signal_name,
                    "market_state": "ALL",
                    "horizon_weeks": horizon,
                    "mean_ic": np.nan,
                    "ic_tstat_nw": np.nan,
                    "hit_rate": np.nan,
                    "n_dates": 0,
                    "mean_coverage": np.nan,
                    "warning": "No valid cross-sectional IC observations.",
                }
            )
            continue
        ic_dates = ic_dates.copy()
        ic_dates["market_state"] = ic_dates["Date"].map(state_map)
        for state, group in ic_dates.dropna(subset=["market_state"]).groupby("market_state"):
            summary = summarize_ic(group)
            warning = ""
            if summary["n_dates"] < 30:
                warning = "Small state sample; treat as directional only."
            rows.append(
                {
                    "signal_name": signal_name,
                    "market_state": state,
                    "horizon_weeks": horizon,
                    "mean_ic": summary["mean_ic"],
                    "ic_tstat_nw": summary["ic_tstat_nw"],
                    "hit_rate": summary["hit_rate"],
                    "n_dates": summary["n_dates"],
                    "mean_coverage": summary["mean_coverage"],
                    "warning": warning,
                }
            )
    return pd.DataFrame(rows)


def max_redundancy_against(
    candidate: pd.DataFrame,
    existing_panels: dict[str, pd.DataFrame],
    min_obs: int = 100,
) -> tuple[float, str]:
    if candidate.empty or not existing_panels:
        return np.nan, ""
    cand = candidate.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last").stack()
    best_abs = np.nan
    best_name = ""
    for name, panel in existing_panels.items():
        other = panel.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last").stack()
        aligned = pd.concat([cand.rename("candidate"), other.rename("existing")], axis=1).dropna()
        if len(aligned) < min_obs:
            continue
        corr = aligned["candidate"].corr(aligned["existing"], method="spearman")
        if pd.notna(corr) and (pd.isna(best_abs) or abs(corr) > best_abs):
            best_abs = abs(float(corr))
            best_name = name
    return best_abs, best_name


def load_strong_existing_panels(warnings: list[str]) -> dict[str, pd.DataFrame]:
    summary = read_csv_safe(SIGNAL_DIR / "signal_summary_table.csv", warnings)
    manifest = load_manifest(warnings)
    if summary.empty or "recommendation" not in summary.columns:
        return {}
    strong_names = summary.loc[summary["recommendation"].eq("strong"), "signal_name"].dropna().tolist()
    panels: dict[str, pd.DataFrame] = {}
    for name in strong_names:
        panel = load_existing_signal_panel(name, manifest, warnings)
        if not panel.empty:
            panels[name] = panel
    return panels


def markdown_table(df: pd.DataFrame, max_rows: int | None = None, float_fmt: str = "{:.4f}") -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else float_fmt.format(x))
    try:
        return view.to_markdown(index=False)
    except Exception:
        header = "| " + " | ".join(map(str, view.columns)) + " |"
        sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
        rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
        return "\n".join([header, sep, *rows])
