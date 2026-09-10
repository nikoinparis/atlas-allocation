"""Shared research-only utilities for the Path 1 + Path 3 sprint.

The helpers here intentionally read production/candidate artifacts without
writing to production locations. Portfolio recomputations use the same saved
ETF weights, weekly price-derived forward returns, one-way turnover convention,
and 10 bps cost convention used by the Layer 3 portfolio path files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from production_costs import portfolio_path as canonical_portfolio_path
from production_metrics import (
    exposure_summary as canonical_exposure_summary,
    max_drawdown as canonical_max_drawdown,
    metrics_from_path as canonical_metrics_from_path,
    metrics_from_series as canonical_metrics_from_series,
    var_cvar as canonical_var_cvar,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HUB = DATA / "01_data_hub"
SIGNALS = DATA / "02_layer1_signals"
L2A = DATA / "03_layer2a_strategy_logic"
REGIME = DATA / "04_layer2b_risk_regime_engine"
PORT = DATA / "05_layer3_portfolio_construction"
CHECKPOINTS = DATA / "research" / "allocator_checkpoints"
DOCS = ROOT / "docs" / "research"

PATH1_OUT = DATA / "research" / "path1_rebuild"
PATH3_OUT = DATA / "research" / "path3_confidence"

GGG = "improved_phaseggg_confirmed_only_robust_offense"
PHASE2B = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"

WEEKS = 52
PRODUCTION_COST_BPS = 10.0

OFFENSE = {
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "VWO",
    "VEA",
    "EWJ",
    "VNQ",
    "HYG",
    "XLY",
    "XLK",
    "XLF",
    "XLI",
    "XLB",
    "XLE",
    "VTV",
    "VUG",
}
DEFENSE = {"BIL", "SHY", "IEF", "TLT", "LQD", "MBB", "TIP", "GLD", "IAU", "UUP", "XLP", "XLU", "XLV"}
PRESSURE_ASSETS = {"EEM", "VWO", "EFA", "VEA", "EWJ", "PDBC", "USO", "DBA", "SLV", "XLE"}
OFFENSE_SLEEVES = {"dual_momentum_topn", "composite_selective_signals", "composite_regime_offense_component"}
DEFENSE_SLEEVES = {"cta_trend_long_only", "composite_regime_defense_component", "taa_10m_sma"}


def ensure_dirs() -> None:
    PATH1_OUT.mkdir(parents=True, exist_ok=True)
    PATH3_OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_csv(path: Path, warnings: list[str], *, index_col: int | str | None = None) -> pd.DataFrame:
    if not path.exists():
        warnings.append(f"Missing optional file: {rel(path)}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path, index_col=index_col)
    except Exception as exc:  # pragma: no cover - defensive reporting
        warnings.append(f"Could not read {rel(path)}: {exc}")
        return pd.DataFrame()


def date_index(df: pd.DataFrame, warnings: list[str], label: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "Date" not in out.columns and "Unnamed: 0" in out.columns:
        out = out.rename(columns={"Unnamed: 0": "Date"})
    if "Date" not in out.columns:
        first = out.columns[0]
        if str(first).lower().startswith("unnamed"):
            out = out.rename(columns={first: "Date"})
    if "Date" not in out.columns:
        warnings.append(f"{label} lacks a Date/Unnamed: 0 column.")
        return pd.DataFrame()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.tz_localize(None)
    out = out.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return out


def load_panel(path: Path, warnings: list[str], label: str | None = None) -> pd.DataFrame:
    return date_index(read_csv(path, warnings), warnings, label or rel(path))


def load_numeric_panel(path: Path, warnings: list[str], label: str | None = None) -> pd.DataFrame:
    df = load_panel(path, warnings, label)
    if df.empty:
        return df
    return df.apply(pd.to_numeric, errors="coerce").sort_index()


def load_weights(name: str, warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(PORT / f"portfolio_version_weights_{name}.csv", warnings, f"weights:{name}").fillna(0.0)


def load_sleeve_weights(name: str, warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(PORT / f"portfolio_version_sleeve_weights_{name}.csv", warnings, f"sleeves:{name}").fillna(0.0)


def load_returns(name: str, warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(PORT / f"portfolio_version_returns_{name}.csv", warnings, f"returns:{name}")


def load_checkpoint(name: str, stage: str, warnings: list[str]) -> pd.DataFrame:
    path = CHECKPOINTS / f"{name}__{stage}.csv"
    return load_numeric_panel(path, warnings, f"checkpoint:{name}:{stage}").fillna(0.0)


def load_weekly_prices(warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(HUB / "weekly_prices.csv", warnings, "weekly_prices.csv")


def load_weekly_returns_file(warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(HUB / "weekly_returns.csv", warnings, "weekly_returns.csv")


def load_next_week_returns(warnings: list[str]) -> pd.DataFrame:
    prices = load_weekly_prices(warnings)
    if prices.empty:
        warnings.append("weekly_prices.csv unavailable; exact production return reconstruction cannot run.")
        return pd.DataFrame()
    return prices.pct_change().shift(-1)


def load_states(warnings: list[str]) -> pd.DataFrame:
    states = load_panel(REGIME / "market_state_history.csv", warnings, "market_state_history.csv")
    if states.empty or "market_state" not in states.columns:
        warnings.append("market_state_history.csv missing or lacks market_state.")
        return pd.DataFrame()
    return states.sort_index()


def load_production_summary(warnings: list[str]) -> pd.DataFrame:
    return read_csv(PORT / "production_candidate_summary.csv", warnings)


def load_signal(signal_name: str, warnings: list[str], ticker: str | None = None) -> pd.Series:
    path = SIGNALS / f"signal_{signal_name}.csv"
    df = load_panel(path, warnings, f"signal:{signal_name}")
    if df.empty:
        return pd.Series(dtype=float)
    value_col = "signal_value_tradable" if "signal_value_tradable" in df.columns else None
    if value_col is None:
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(pd.to_numeric(df[c], errors="coerce"))]
        value_col = numeric_cols[0] if numeric_cols else None
    if value_col is None:
        warnings.append(f"{rel(path)} lacks a numeric signal column.")
        return pd.Series(dtype=float)
    if "Ticker" in df.columns:
        if ticker is None:
            ticker = "SPY" if "SPY" in set(df["Ticker"].astype(str)) else str(df["Ticker"].dropna().astype(str).iloc[0])
        df = df[df["Ticker"].astype(str).eq(ticker)]
        if df.empty:
            warnings.append(f"{rel(path)} has no rows for ticker {ticker}.")
            return pd.Series(dtype=float)
    return pd.to_numeric(df[value_col], errors="coerce").sort_index()


def rolling_percentile(series: pd.Series, window: int = 156, min_periods: int = 52) -> pd.Series:
    s = pd.Series(series, dtype=float).sort_index()

    def pct_rank(values: np.ndarray) -> float:
        clean = pd.Series(values).dropna()
        if len(clean) < min_periods:
            return np.nan
        return float((clean <= clean.iloc[-1]).mean())

    return s.rolling(window, min_periods=min_periods).apply(pct_rank, raw=False)


def scaled_signal(series: pd.Series, index: pd.Index) -> pd.Series:
    pct = rolling_percentile(series).reindex(index).ffill()
    if pct.notna().sum() == 0:
        pct = pd.Series(series, dtype=float).reindex(index).ffill()
        lo, hi = pct.quantile(0.05), pct.quantile(0.95)
        pct = (pct - lo) / (hi - lo) if np.isfinite(hi - lo) and hi != lo else pd.Series(0.5, index=index)
    return pct.clip(0.0, 1.0).fillna(0.5)


def load_market_quality_inputs(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    """Build causal, tradable market-quality inputs from existing signal files."""
    out = pd.DataFrame(index=index)
    signal_tickers = {
        "bm_etf_above_50d_ma": "SPY",
        "bm_etf_above_200d_ma": "SPY",
        "bm_etf_positive_13w_mom": "SPY",
        "bm_etf_positive_26w_mom": "SPY",
        "bm_risk_on_participation": "SPY",
        "bm_sector_above_50d_ma": "SPY",
        "bm_sector_above_200d_ma": "SPY",
        "bm_sector_positive_13w_mom": "SPY",
        "bm_sector_positive_26w_mom": "SPY",
        "bm_quality_signal_agreement": "SPY",
        "bm_quality_signal_dispersion": "SPY",
        "bm_quality_deterioration_warning": "SPY",
        "bm_quality_breadth_confirmation": "SPY",
        "bm_dollar_strength_4w": "UUP",
        "bm_dollar_strength_blended": "UUP",
        "r2_vix_term_structure": "SPY",
        "r2_credit_spread": "SPY",
        "r2_financial_conditions": "SPY",
    }
    for name, ticker in signal_tickers.items():
        out[name] = scaled_signal(load_signal(name, warnings, ticker), index)
    states = load_states(warnings)
    if not states.empty:
        for col in [
            "market_state",
            "risk_state",
            "breadth_sma_43",
            "breadth_26w_mom",
            "breadth_13w_mom",
            "breadth_change_4w",
            "market_trend_positive",
            "transition_non_stress_prob",
            "transition_good_state_prob",
            "transition_persistence_prob",
            "market_drawdown",
        ]:
            if col in states.columns:
                out[col] = states[col].reindex(index).ffill()
    return out


def production_portfolio_path(weights: pd.DataFrame, next_week_returns: pd.DataFrame, cost_bps: float = PRODUCTION_COST_BPS) -> pd.DataFrame:
    return canonical_portfolio_path(weights, next_week_returns, cost_bps)


def b7_style_path(weights: pd.DataFrame, weekly_returns: pd.DataFrame, cost_bps: float = PRODUCTION_COST_BPS) -> pd.DataFrame:
    common = weights.index.intersection(weekly_returns.index)
    cols = [c for c in weights.columns if c in weekly_returns.columns]
    w = weights.reindex(index=common, columns=cols).fillna(0.0)
    r = weekly_returns.reindex(index=common, columns=cols).fillna(0.0)
    applied = w.shift(1).fillna(0.0)
    gross = (applied * r).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * (cost_bps / 10000.0)
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame(
        {
            "Date": common,
            "gross_return": gross.values,
            "net_return": net.values,
            "turnover": turnover.values,
            "cost": cost.values,
            "wealth": wealth.values,
            "drawdown": drawdown.values,
        }
    )


def max_drawdown(returns: pd.Series) -> float:
    return canonical_max_drawdown(returns)


def cvar_5(returns: pd.Series) -> float:
    return canonical_var_cvar(returns)[1]


def metrics_from_series(returns: pd.Series, turnover: pd.Series | None = None, cost: pd.Series | None = None) -> dict[str, float]:
    return canonical_metrics_from_series(returns, turnover, cost)


def metrics_from_path(path: pd.DataFrame, start: str | None = None, end: str | None = None) -> dict[str, float]:
    return canonical_metrics_from_path(path, start=start, end=end)


def exposure_summary(weights: pd.DataFrame) -> dict[str, float]:
    return canonical_exposure_summary(weights)


def normalize_to_cash(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.clip(lower=0.0).copy()
    if "BIL" not in out.columns:
        out["BIL"] = 0.0
    risky_cols = [c for c in out.columns if c != "BIL"]
    risky_sum = out[risky_cols].sum(axis=1)
    over = risky_sum > 1.0
    if over.any():
        out.loc[over, risky_cols] = out.loc[over, risky_cols].div(risky_sum.loc[over], axis=0)
    out["BIL"] = (1.0 - out[risky_cols].sum(axis=1)).clip(lower=0.0)
    return out


def apply_offense_multiplier(base: pd.DataFrame, multiplier: pd.Series, *, pressure_multiplier: pd.Series | None = None) -> pd.DataFrame:
    w = base.copy()
    offense_cols = [c for c in w.columns if c in OFFENSE]
    pressure_cols = [c for c in w.columns if c in PRESSURE_ASSETS]
    mult = multiplier.reindex(w.index).ffill().fillna(1.0).clip(0.0, 1.10)
    if offense_cols:
        w[offense_cols] = w[offense_cols].mul(mult, axis=0)
    if pressure_multiplier is not None and pressure_cols:
        pm = pressure_multiplier.reindex(w.index).ffill().fillna(1.0).clip(0.0, 1.05)
        w[pressure_cols] = w[pressure_cols].mul(pm, axis=0)
    return normalize_to_cash(w)


def state_summary(path: pd.DataFrame, states: pd.DataFrame, variant: str) -> pd.DataFrame:
    if states.empty or path.empty:
        return pd.DataFrame()
    df = path.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    state_map = states["market_state"]
    df["market_state"] = df["Date"].map(state_map)
    rows = []
    for state, group in df.dropna(subset=["market_state"]).groupby("market_state"):
        rows.append({"variant": variant, "market_state": state, **metrics_from_path(group)})
    return pd.DataFrame(rows)


def future_return(series: pd.Series, horizon: int = 4) -> pd.Series:
    ret = pd.Series(series, dtype=float)
    return (1.0 + ret).rolling(horizon).apply(np.prod, raw=True).shift(-horizon + 1) - 1.0


def future_drawdown(series: pd.Series, horizon: int = 4) -> pd.Series:
    ret = pd.Series(series, dtype=float)
    out = pd.Series(index=ret.index, dtype=float)
    for i, date in enumerate(ret.index):
        window = ret.iloc[i : i + horizon]
        if len(window) < horizon:
            out.loc[date] = np.nan
            continue
        wealth = (1.0 + window).cumprod()
        out.loc[date] = float((wealth / wealth.cummax() - 1.0).min())
    return out


def md_table(df: pd.DataFrame, cols: list[str] | None = None, n: int = 12) -> str:
    if df is None or df.empty:
        return "_No rows._"
    view = df.copy()
    if cols is not None:
        view = view[[c for c in cols if c in view.columns]]
    view = view.head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    try:
        return view.to_markdown(index=False)
    except Exception:
        header = "| " + " | ".join(map(str, view.columns)) + " |"
        sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
        rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
        return "\n".join([header, sep, *rows])


def write_text(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n")
