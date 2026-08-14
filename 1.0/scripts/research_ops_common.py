"""Shared utilities for the Research Operating Layer (Layers 2-6).

Lightweight loaders + metric helpers that wrap the existing project files.
Designed to be import-safe even when optional artifacts are missing.
"""
from __future__ import annotations

from pathlib import Path
import warnings
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = ROOT / "reports"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
SHADOW_PIN = "improved_phase2b_combo_abc"
PHASEU_U1A = "improved_phaseu_prod90_r2_10_holdings_blend"
PHASEZ_Z1 = "improved_phasez_production_hrp_7sleeve"
PHASEBB_BB1 = "improved_phasebb_w1cap_055_hrp_7sleeve"
PHASEAA_AA1 = "improved_phaseaa_prod95_z1_05_holdings_blend"

WEEKS_PER_YEAR = 52
DEFAULT_HALFSPREAD = 0.0005 * 0.5
HOLDOUT_WEEKS = 156

# --------------------------------------------------------------------------
# loaders (safe — return None or empty if missing)
# --------------------------------------------------------------------------

def load_portfolio_returns(name: str) -> pd.DataFrame | None:
    p = LAYER3_DIR / f"portfolio_version_returns_{name}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    return df


def load_portfolio_weights(name: str) -> pd.DataFrame | None:
    p = LAYER3_DIR / f"portfolio_version_weights_{name}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    return df


def load_portfolio_sleeve_weights(name: str) -> pd.DataFrame | None:
    p = LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    return df


def load_market_state(refined: bool = False) -> pd.DataFrame:
    fname = "market_state_history_refined.csv" if refined else "market_state_history.csv"
    p = LAYER2B_DIR / fname
    if not p.exists():
        if refined:
            return load_market_state(refined=False)
        raise FileNotFoundError(p)
    df = pd.read_csv(p, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


def load_weekly_returns() -> pd.DataFrame:
    p = LAYER1_DIR / "weekly_returns.csv"
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index()


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------

def annualised_return(net: pd.Series) -> float:
    net = net.dropna()
    if len(net) == 0:
        return float("nan")
    growth = float((1.0 + net).prod())
    yrs = len(net) / WEEKS_PER_YEAR
    if yrs <= 0 or growth <= 0:
        return float("nan")
    return growth ** (1.0 / yrs) - 1.0


def annualised_vol(net: pd.Series) -> float:
    net = net.dropna()
    if len(net) < 2:
        return float("nan")
    return float(net.std(ddof=0)) * np.sqrt(WEEKS_PER_YEAR)


def sharpe(net: pd.Series) -> float:
    v = annualised_vol(net)
    if not np.isfinite(v) or v == 0:
        return float("nan")
    return annualised_return(net) / v


def max_drawdown(net: pd.Series) -> float:
    net = net.dropna()
    if len(net) == 0:
        return float("nan")
    wealth = (1.0 + net).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar(net: pd.Series, alpha: float = 0.05) -> float:
    net = net.dropna()
    if len(net) == 0:
        return float("nan")
    cutoff = net.quantile(alpha)
    tail = net[net <= cutoff]
    if len(tail) == 0:
        return float("nan")
    return float(tail.mean())


def calmar(net: pd.Series) -> float:
    mdd = max_drawdown(net)
    if not np.isfinite(mdd) or mdd >= 0:
        return float("nan")
    return annualised_return(net) / abs(mdd)


def metric_block(net: pd.Series) -> dict:
    return {
        "ann_return": annualised_return(net),
        "ann_vol": annualised_vol(net),
        "sharpe": sharpe(net),
        "max_drawdown": max_drawdown(net),
        "cvar_5": cvar(net, 0.05),
        "calmar": calmar(net),
    }


def weekly_turnover(weights: pd.DataFrame) -> pd.Series:
    return weights.diff().abs().sum(axis=1).fillna(0.0)


# --------------------------------------------------------------------------
# block bootstrap
# --------------------------------------------------------------------------

def block_bootstrap_returns(net: pd.Series, n_samples: int = 1000,
                            block_weeks: int = 26, rng: np.random.Generator | None = None
                            ) -> np.ndarray:
    """Return a (n_samples, T) matrix of bootstrapped weekly returns drawn
    by moving-block bootstrap from the original series."""
    if rng is None:
        rng = np.random.default_rng(20260427)
    arr = net.dropna().to_numpy()
    T = len(arr)
    if T < block_weeks * 2:
        return np.empty((0, 0))
    n_blocks = int(np.ceil(T / block_weeks))
    out = np.empty((n_samples, n_blocks * block_weeks))
    for s in range(n_samples):
        starts = rng.integers(0, T - block_weeks + 1, size=n_blocks)
        for i, st in enumerate(starts):
            out[s, i*block_weeks:(i+1)*block_weeks] = arr[st:st+block_weeks]
    return out[:, :T]


def bootstrap_metric_distribution(net: pd.Series, fn, n_samples: int = 500,
                                  block_weeks: int = 26) -> np.ndarray:
    samples = block_bootstrap_returns(net, n_samples=n_samples, block_weeks=block_weeks)
    if samples.size == 0:
        return np.array([])
    out = np.empty(samples.shape[0])
    for i in range(samples.shape[0]):
        out[i] = fn(pd.Series(samples[i]))
    return out


def confidence_interval(samples: np.ndarray, lo: float = 0.05, hi: float = 0.95) -> tuple[float, float]:
    if samples.size == 0:
        return (float("nan"), float("nan"))
    return float(np.quantile(samples, lo)), float(np.quantile(samples, hi))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def safe_compare(cand: float, prod: float) -> float:
    if not np.isfinite(cand) or not np.isfinite(prod):
        return float("nan")
    return cand - prod


def fmt_pct(x: float, digits: int = 2) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x*100:.{digits}f}%"


def fmt_num(x: float, digits: int = 4) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:.{digits}f}"


def warn_section(msg: str) -> str:
    return f"> ⚠️ **Warning:** {msg}\n\n"
