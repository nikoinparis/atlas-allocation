"""Run Track C new-alpha ETF research experiments.

Track C is research-only.  It never writes to the production registry or Track A
production artifacts.  All outputs are isolated under
``data/research/track_c_new_alpha`` and ``docs/research/track_c_new_alpha``.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from production_config import (  # noqa: E402
    DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
    OFFICIAL_HOLDOUT_START,
    PRODUCTION_CANDIDATE,
    WEEKS_PER_YEAR,
    markdown_table,
    rel,
    require_official_production_pin,
    returns_path,
    weights_path,
)
from production_costs import (  # noqa: E402
    cost_sensitivity_paths,
    next_week_returns_from_prices,
    portfolio_path,
)
from production_metrics import (  # noqa: E402
    DEFENSE_ASSETS,
    EQUITY_ASSETS,
    OFFENSE_ASSETS,
    holdout_metrics_from_path,
    metrics_from_path,
    metrics_from_series,
    rolling_origin_metrics,
)
from statistical_validation_layer import (  # noqa: E402
    deflated_sharpe_ratio_proxy,
    multiple_testing_adjusted_support,
    probabilistic_sharpe_ratio,
)


DATA = ROOT / "data"
HUB = DATA / "01_data_hub"
SIGNALS = DATA / "02_layer1_signals"
LAYER2A = DATA / "03_layer2a_strategy_logic"
REGIME = DATA / "04_layer2b_risk_regime_engine"
TRACK_B_OUT = DATA / "research" / "track_b_aggressive"
OUT = DATA / "research" / "track_c_new_alpha"
DOC = ROOT / "docs" / "research" / "track_c_new_alpha"
STAT_AUDIT = DATA / "research" / "validation" / "statistical_validation_audit.csv"

OVERLAY_WEIGHTS = (0.05, 0.10, 0.15)

EXISTING_SLEEVE_REFERENCES = {
    "dual_momentum_topn": LAYER2A / "strategy_returns_dual_momentum_topn.csv",
    "taa_10m_sma": LAYER2A / "strategy_returns_taa_10m_sma.csv",
    "composite_trend_quality_refined": LAYER2A / "strategy_returns_composite_trend_quality_refined.csv",
    "composite_calm_carry_sleeve": LAYER2A / "strategy_returns_composite_calm_carry_sleeve.csv",
    "composite_breadth_filtered": LAYER2A / "strategy_returns_composite_breadth_filtered.csv",
    "cross_sectional_reversal_combo_ls": LAYER2A / "strategy_returns_cross_sectional_reversal_combo_ls.csv",
    "pairs_stat_arb_research": LAYER2A / "strategy_returns_pairs_stat_arb_research.csv",
    "cta_trend_vol_managed": LAYER2A / "strategy_returns_cta_trend_vol_managed.csv",
}


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    hypothesis: str
    parameters: dict[str, Any]
    expected_tradeoff: str
    success_criteria: str
    kill_criteria: str


CANDIDATES: list[CandidateSpec] = [
    CandidateSpec(
        "track_c_residual_xsmom_top5",
        "Residual momentum may select ETFs with less broad-market beta than raw ETF momentum.",
        {
            "signal_file": "signal_residual_momentum.csv",
            "signal_column": "residual_mom_score_tradable",
            "top_n": 5,
            "positive_only": True,
            "unallocated_weight": "BIL",
        },
        "May underperform raw momentum but should be less beta-like if useful.",
        "Positive beta-adjusted residual, reasonable turnover, and lower correlation to Track A/current sleeves.",
        "Reject if weak standalone return, high beta explanation, or high overlap with existing trend sleeves.",
    ),
    CandidateSpec(
        "track_c_vol_managed_residual_xsmom_top5",
        "Volatility scaling may keep residual momentum exposure while reducing tail losses.",
        {
            "base": "track_c_residual_xsmom_top5",
            "spy_realized_vol_13w": True,
            "risky_scale": {"vol_le_18pct": 1.0, "vol_18_to_25pct": 0.8, "vol_gt_25pct": 0.6},
            "unallocated_weight": "BIL",
        },
        "Lower beta and possibly lower return; should improve CVaR if useful.",
        "Better Sharpe/CVaR than unscaled residual momentum and positive beta-adjusted residual.",
        "Reject if return is destroyed, no tail improvement appears, or improvement is only lower beta.",
    ),
    CandidateSpec(
        "track_c_carry_value_top5",
        "Carry plus value may diversify price momentum if ETF proxy data are usable.",
        {
            "signal_files": ["signal_carry.csv", "signal_value.csv"],
            "signal_columns": ["carry_score_tradable", "value_score_tradable"],
            "blend": "50_50",
            "top_n": 5,
            "positive_only": True,
            "unallocated_weight": "BIL",
        },
        "Lower trend beta, but data proxies may be stale or weak.",
        "Low Track A correlation and positive beta-adjusted residual.",
        "Reject if IC/return is weak, if the sleeve is just defensive/cash tilt, or if costs dominate.",
    ),
    CandidateSpec(
        "track_c_neutral_reversal_top5",
        "Four-week reversal may help in choppy neutral/reversal-friendly regimes.",
        {
            "signal_file": "signal_reversal.csv",
            "signal_column": "reversal_4w_score_tradable",
            "active_when": ["market_state == neutral_mixed", "signal_environment == reversal_friendly"],
            "top_n": 5,
            "positive_only": True,
            "inactive_weight": "BIL",
        },
        "High turnover and noisy; should only help in neutral/choppy states if real.",
        "Positive neutral-state contribution after 2x costs.",
        "Reject if turnover is high, full-period result is negative, or stress/recovery behavior is unstable.",
    ),
    CandidateSpec(
        "track_c_hyg_lqd_pair_mean_reversion",
        "The existing HYG/LQD pair diagnostic may provide equity-light credit relative-value exposure.",
        {
            "signal_file": "signal_r4_pair_hyg_lqd.csv",
            "positive_signal_weight": "HYG",
            "negative_signal_weight": "LQD",
            "missing_or_zero_weight": "BIL",
        },
        "Narrow single-pair dependence; should be low beta if useful.",
        "Positive standalone residual, low correlation, and tolerable turnover.",
        "Reject if holdout is poor, signal is unstable, or cost sensitivity is weak.",
    ),
    CandidateSpec(
        "track_c_canary_breadth_timing",
        "Continuous canary/breadth timing may improve risk-on/off quality without a Track B cash-cap overlay.",
        {
            "score_inputs": [
                "canary_breadth_default",
                "canary_breadth_pair",
                "breadth_sma_43",
                "breadth_26w_mom",
                "market_trend_positive",
            ],
            "strong_score_threshold": 0.67,
            "weak_score_threshold": 0.33,
            "strong_weights": {"SPY": 0.60, "IEF": 0.40},
            "mixed_weights": {"SPY": 0.35, "IEF": 0.35, "BIL": 0.30},
            "weak_or_stress_weights": {"BIL": 0.70, "IEF": 0.30},
        },
        "May behave like simpler TAA; must show timing quality, not just lower cash drag.",
        "Drawdown/CVaR improvement or return lift with positive beta/cash-adjusted residual.",
        "Reject if it only lowers BIL/cash drag, fails stressed-panic behavior, or is dominated by simple TAA.",
    ),
]


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns and "Date" not in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    date_col = "Date" if "Date" in df.columns else "date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def read_signal_matrix(path: Path, value_col: str) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=lambda col: col in {"Date", "Ticker", value_col})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    return df.dropna(subset=["Date"]).pivot_table(index="Date", columns="Ticker", values=value_col, aggfunc="last").sort_index()


def normalize_to_bil(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.copy().apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(lower=0.0)
    if "BIL" not in out.columns:
        out["BIL"] = 0.0
    risky_cols = [c for c in out.columns if c != "BIL"]
    risky_sum = out[risky_cols].sum(axis=1)
    over = risky_sum > 1.0
    if over.any():
        out.loc[over, risky_cols] = out.loc[over, risky_cols].div(risky_sum.loc[over], axis=0)
    out["BIL"] = (1.0 - out[risky_cols].sum(axis=1)).clip(lower=0.0)
    row_sum = out.sum(axis=1)
    nonzero = row_sum > 0
    out.loc[nonzero] = out.loc[nonzero].div(row_sum.loc[nonzero], axis=0)
    out.loc[~nonzero, "BIL"] = 1.0
    return out


def rank_top_weights(
    scores: pd.DataFrame,
    index: pd.Index,
    columns: list[str],
    *,
    top_n: int = 5,
    positive_only: bool = True,
    active_mask: pd.Series | None = None,
) -> pd.DataFrame:
    aligned = scores.reindex(index=index, columns=columns)
    weights = pd.DataFrame(0.0, index=index, columns=columns)
    if "BIL" not in weights.columns:
        weights["BIL"] = 0.0
    active = pd.Series(True, index=index) if active_mask is None else active_mask.reindex(index).fillna(False).astype(bool)
    for date in index:
        if not bool(active.loc[date]):
            weights.loc[date, "BIL"] = 1.0
            continue
        row = pd.to_numeric(aligned.loc[date], errors="coerce").dropna()
        row = row.drop(labels=["BIL"], errors="ignore")
        if positive_only:
            row = row[row > 0.0]
        if row.empty:
            weights.loc[date, "BIL"] = 1.0
            continue
        selected = list(row.sort_values(ascending=False).head(top_n).index)
        weights.loc[date, selected] = 1.0 / len(selected)
    return normalize_to_bil(weights.reindex(columns=columns, fill_value=0.0))


def static_allocation_frame(index: pd.Index, columns: list[str], allocation: dict[str, float]) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=index, columns=columns)
    for ticker, weight in allocation.items():
        if ticker in weights.columns:
            weights[ticker] = float(weight)
    return normalize_to_bil(weights)


def build_vol_managed_residual(
    residual_scores: pd.DataFrame,
    prices: pd.DataFrame,
    index: pd.Index,
    columns: list[str],
) -> pd.DataFrame:
    base = rank_top_weights(residual_scores, index, columns, top_n=5, positive_only=True)
    spot_returns = prices[["SPY"]].pct_change()
    spy_vol = spot_returns["SPY"].rolling(13, min_periods=8).std(ddof=1) * np.sqrt(WEEKS_PER_YEAR)
    spy_vol = spy_vol.reindex(index)
    scale = pd.Series(0.8, index=index)
    scale[spy_vol <= 0.18] = 1.0
    scale[(spy_vol > 0.18) & (spy_vol <= 0.25)] = 0.8
    scale[spy_vol > 0.25] = 0.6
    scale = scale.fillna(0.8)
    out = base.copy()
    risky_cols = [c for c in out.columns if c != "BIL"]
    out[risky_cols] = out[risky_cols].mul(scale, axis=0)
    out["BIL"] = 1.0 - out[risky_cols].sum(axis=1)
    return normalize_to_bil(out.reindex(columns=columns, fill_value=0.0))


def build_pair_weights(pair_signal_path: Path, index: pd.Index, columns: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(pair_signal_path, usecols=lambda col: col in {"Date", "signal_value_tradable"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    signal = pd.to_numeric(df["signal_value_tradable"], errors="coerce")
    signal.index = df["Date"]
    signal = signal.groupby(level=0).last().reindex(index)
    weights = pd.DataFrame(0.0, index=index, columns=columns)
    for date, value in signal.items():
        if pd.isna(value) or float(value) == 0.0:
            weights.loc[date, "BIL"] = 1.0
        elif float(value) > 0.0 and "HYG" in weights.columns:
            weights.loc[date, "HYG"] = 1.0
        elif "LQD" in weights.columns:
            weights.loc[date, "LQD"] = 1.0
        else:
            weights.loc[date, "BIL"] = 1.0
    return normalize_to_bil(weights), signal


def build_canary_breadth_weights(market_history: pd.DataFrame, index: pd.Index, columns: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    hist = market_history.reindex(index)
    score_cols = [
        "canary_breadth_default",
        "canary_breadth_pair",
        "breadth_sma_43",
        "breadth_26w_mom",
        "market_trend_positive",
    ]
    available_cols = [c for c in score_cols if c in hist.columns]
    score = hist[available_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1).clip(lower=0.0, upper=1.0)
    state = hist.get("market_state", pd.Series(index=index, dtype=str)).astype(str)
    weights = pd.DataFrame(0.0, index=index, columns=columns)
    strong = {"SPY": 0.60, "IEF": 0.40}
    mixed = {"SPY": 0.35, "IEF": 0.35, "BIL": 0.30}
    weak = {"BIL": 0.70, "IEF": 0.30}
    for date in index:
        if state.loc[date] == "stressed_panic" or pd.isna(score.loc[date]) or score.loc[date] < 0.33:
            alloc = weak
        elif score.loc[date] >= 0.67:
            alloc = strong
        else:
            alloc = mixed
        for ticker, weight in alloc.items():
            if ticker in weights.columns:
                weights.loc[date, ticker] = weight
    return normalize_to_bil(weights), score


def beta_to_factor(returns: pd.Series, factor_returns: pd.Series) -> float:
    df = pd.concat([pd.to_numeric(returns, errors="coerce"), pd.to_numeric(factor_returns, errors="coerce")], axis=1).dropna()
    if len(df) < 20 or float(df.iloc[:, 1].var(ddof=1)) <= 0:
        return np.nan
    return float(np.cov(df.iloc[:, 0], df.iloc[:, 1], ddof=1)[0, 1] / df.iloc[:, 1].var(ddof=1))


def safe_corr(a: pd.Series, b: pd.Series) -> float:
    df = pd.concat([pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")], axis=1).dropna()
    if len(df) < 20 or df.iloc[:, 0].std(ddof=1) <= 0 or df.iloc[:, 1].std(ddof=1) <= 0:
        return np.nan
    return float(df.iloc[:, 0].corr(df.iloc[:, 1]))


def trial_count() -> int:
    if not STAT_AUDIT.exists():
        return len(CANDIDATES)
    df = pd.read_csv(STAT_AUDIT, usecols=lambda col: col in {"trial_count_used"})
    base = int(df["trial_count_used"].max()) if not df.empty and "trial_count_used" in df.columns else 1
    return max(base + len(CANDIDATES), len(CANDIDATES))


def evaluate(
    name: str,
    kind: str,
    weights: pd.DataFrame,
    path: pd.DataFrame,
    next_returns: pd.DataFrame,
    track_a_metrics: dict[str, float] | None,
    track_a_returns: pd.Series | None,
    trials: int,
) -> dict[str, Any]:
    path_idx = path.set_index("Date")
    ret = pd.to_numeric(path_idx["net_return"], errors="coerce")
    full = metrics_from_path(path, weights=weights)
    holdout_weights = weights.loc[weights.index >= OFFICIAL_HOLDOUT_START] if not weights.empty else weights
    holdout = holdout_metrics_from_path(path, weights=holdout_weights)
    psr = probabilistic_sharpe_ratio(ret)
    dsr = deflated_sharpe_ratio_proxy(ret, trial_count=trials)
    mt_support = multiple_testing_adjusted_support(psr, trials)
    row = {
        "name": name,
        "kind": kind,
        "research_status": "research_only",
        "ann_return": full["ann_return"],
        "cagr": full["cagr"],
        "arithmetic_ann_return": full["arithmetic_ann_return"],
        "ann_vol": full["ann_vol"],
        "sharpe": full["sharpe"],
        "sortino": full["sortino"],
        "max_drawdown": full["max_drawdown"],
        "calmar": full["calmar"],
        "var_5": full["var_5"],
        "cvar_5": full["cvar_5"],
        "hit_rate": full["hit_rate"],
        "avg_weekly_turnover": full["avg_weekly_turnover"],
        "annualized_turnover": full["annualized_turnover"],
        "annualized_cost": full["annualized_cost"],
        "avg_BIL": full["avg_BIL"],
        "avg_cash": full["avg_cash"],
        "avg_SPY": full["avg_SPY"],
        "avg_offense": full["avg_offense"],
        "avg_defense": full["avg_defense"],
        "avg_equity": full["avg_equity"],
        "max_single_etf_weight": full["max_single_etf_weight"],
        "spy_beta": beta_to_factor(ret, next_returns["SPY"].reindex(path_idx.index)),
        "ief_beta": beta_to_factor(ret, next_returns["IEF"].reindex(path_idx.index)) if "IEF" in next_returns.columns else np.nan,
        "track_a_corr": safe_corr(ret, track_a_returns) if track_a_returns is not None else np.nan,
        "holdout_ann_return": holdout["ann_return"],
        "holdout_ann_vol": holdout["ann_vol"],
        "holdout_sharpe": holdout["sharpe"],
        "holdout_max_drawdown": holdout["max_drawdown"],
        "holdout_cvar_5": holdout["cvar_5"],
        "psr_zero_benchmark": psr,
        "dsr_proxy_trial_adjusted": dsr,
        "multiple_testing_adjusted_support": mt_support,
    }
    if track_a_metrics:
        for key in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_offense", "avg_equity", "spy_beta"]:
            row[f"delta_{key}_vs_track_a"] = row[key] - track_a_metrics[key]
    return row


def state_metrics(name: str, kind: str, path: pd.DataFrame, states: pd.Series) -> pd.DataFrame:
    path_idx = path.set_index("Date")
    ret = pd.to_numeric(path_idx["net_return"], errors="coerce")
    state_series = states.reindex(ret.index).astype(str)
    rows = []
    for state, sr in ret.groupby(state_series):
        if not isinstance(state, str) or state == "nan" or sr.empty:
            continue
        m = metrics_from_series(sr)
        rows.append(
            {
                "name": name,
                "kind": kind,
                "market_state": state,
                "n_weeks": m["n_weeks"],
                "ann_return": m["ann_return"],
                "ann_vol": m["ann_vol"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "cvar_5": m["cvar_5"],
                "calmar": m["calmar"],
            }
        )
    return pd.DataFrame(rows)


def cost_sensitivity(name: str, kind: str, weights: pd.DataFrame, next_returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for multiplier, path in cost_sensitivity_paths(weights, next_returns).items():
        m = metrics_from_path(path, weights=weights)
        rows.append(
            {
                "name": name,
                "kind": kind,
                "cost_multiplier": multiplier,
                "cost_bps_per_one_way_turnover": multiplier * DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
                "ann_return": m["ann_return"],
                "ann_vol": m["ann_vol"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "cvar_5": m["cvar_5"],
                "calmar": m["calmar"],
                "annualized_cost": m["annualized_cost"],
                "avg_weekly_turnover": m["avg_weekly_turnover"],
            }
        )
    return pd.DataFrame(rows)


def category_contributions(name: str, weights: pd.DataFrame, path: pd.DataFrame, next_returns: pd.DataFrame) -> dict[str, float]:
    idx = path.set_index("Date").index
    w = weights.reindex(idx).fillna(0.0)
    r = next_returns.reindex(idx, columns=w.columns).fillna(0.0)
    contrib = w * r
    off_cols = [c for c in w.columns if c in OFFENSE_ASSETS and c != "BIL"]
    def_cols = [c for c in w.columns if c in DEFENSE_ASSETS and c != "BIL"]
    eq_cols = [c for c in w.columns if c in EQUITY_ASSETS]
    return {
        "name": name,
        "offense_gross_contribution_ann": float(contrib[off_cols].sum(axis=1).mean() * WEEKS_PER_YEAR) if off_cols else np.nan,
        "defense_gross_contribution_ann": float(contrib[def_cols].sum(axis=1).mean() * WEEKS_PER_YEAR) if def_cols else np.nan,
        "equity_gross_contribution_ann": float(contrib[eq_cols].sum(axis=1).mean() * WEEKS_PER_YEAR) if eq_cols else np.nan,
        "bil_gross_contribution_ann": float(contrib["BIL"].mean() * WEEKS_PER_YEAR) if "BIL" in contrib.columns else np.nan,
        "cost_drag_ann": float(pd.to_numeric(path["cost"], errors="coerce").mean() * WEEKS_PER_YEAR),
    }


def cross_sectional_rank_ic(name: str, scores: pd.DataFrame, next_returns: pd.DataFrame) -> dict[str, Any]:
    common_idx = scores.index.intersection(next_returns.index)
    common_cols = [c for c in scores.columns if c in next_returns.columns and c != "BIL"]
    ics = []
    for date in common_idx:
        df = pd.DataFrame({"signal": scores.loc[date, common_cols], "fwd_return": next_returns.loc[date, common_cols]}).dropna()
        if len(df) < 5 or df["signal"].nunique() < 3 or df["fwd_return"].nunique() < 3:
            continue
        ics.append(float(df["signal"].rank().corr(df["fwd_return"].rank())))
    sr = pd.Series(ics, dtype=float).dropna()
    return {
        "name": name,
        "ic_type": "cross_sectional_rank_ic",
        "observations": int(len(sr)),
        "mean_ic": float(sr.mean()) if len(sr) else np.nan,
        "median_ic": float(sr.median()) if len(sr) else np.nan,
        "ic_tstat": float(sr.mean() / (sr.std(ddof=1) / math.sqrt(len(sr)))) if len(sr) > 2 and sr.std(ddof=1) > 0 else np.nan,
        "positive_ic_share": float((sr > 0).mean()) if len(sr) else np.nan,
    }


def time_series_ic(name: str, signal: pd.Series, target_return: pd.Series, ic_type: str) -> dict[str, Any]:
    df = pd.concat([pd.to_numeric(signal, errors="coerce"), pd.to_numeric(target_return, errors="coerce")], axis=1).dropna()
    df.columns = ["signal", "fwd_return"]
    corr = safe_corr(df["signal"], df["fwd_return"])
    return {
        "name": name,
        "ic_type": ic_type,
        "observations": int(len(df)),
        "mean_ic": corr,
        "median_ic": corr,
        "ic_tstat": np.nan,
        "positive_ic_share": float(corr > 0.0) if np.isfinite(corr) else np.nan,
    }


def load_existing_sleeve_returns() -> dict[str, pd.Series]:
    refs = {}
    for name, path in EXISTING_SLEEVE_REFERENCES.items():
        if not path.exists():
            continue
        df = read_dated(path)
        if "net_return" in df.columns:
            refs[name] = pd.to_numeric(df["net_return"], errors="coerce")
    return refs


def correlation_rows(
    name: str,
    kind: str,
    returns: pd.Series,
    track_a_returns: pd.Series,
    existing: dict[str, pd.Series],
) -> tuple[list[dict[str, Any]], float]:
    rows = [
        {
            "name": name,
            "kind": kind,
            "reference_type": "track_a",
            "reference_name": PRODUCTION_CANDIDATE,
            "correlation": safe_corr(returns, track_a_returns),
        }
    ]
    existing_corrs = []
    for ref_name, ref_returns in existing.items():
        corr = safe_corr(returns, ref_returns)
        rows.append(
            {
                "name": name,
                "kind": kind,
                "reference_type": "existing_sleeve",
                "reference_name": ref_name,
                "correlation": corr,
            }
        )
        if np.isfinite(corr):
            existing_corrs.append(abs(corr))
    return rows, float(max(existing_corrs)) if existing_corrs else np.nan


def standalone_attribution(
    name: str,
    row: pd.Series,
    path: pd.DataFrame,
    weights: pd.DataFrame,
    next_returns: pd.DataFrame,
    spy_cagr: float,
    bil_cagr: float,
) -> dict[str, Any]:
    equity_premium = spy_cagr - bil_cagr
    beta_expected = bil_cagr + row["spy_beta"] * equity_premium
    residual = row["ann_return"] - beta_expected
    label = "positive_beta_adjusted_residual" if residual > 0.0 else "no_positive_beta_adjusted_residual"
    return {
        "name": name,
        "kind": row["kind"],
        "ann_return": row["ann_return"],
        "spy_beta": row["spy_beta"],
        "avg_BIL": row["avg_BIL"],
        "bil_cagr_reference": bil_cagr,
        "spy_cagr_reference": spy_cagr,
        "beta_expected_return_est_ann": beta_expected,
        "beta_adjusted_residual_ann": residual,
        "cash_drag_adjusted_residual_ann": residual,
        "return_source_label": label,
        **category_contributions(name, weights, path, next_returns),
    }


def blend_attribution(
    name: str,
    row: pd.Series,
    track_a_row: pd.Series,
    path: pd.DataFrame,
    weights: pd.DataFrame,
    next_returns: pd.DataFrame,
    spy_cagr: float,
    bil_cagr: float,
) -> dict[str, Any]:
    equity_premium = spy_cagr - bil_cagr
    delta_return = row["ann_return"] - track_a_row["ann_return"]
    beta_delta = row["spy_beta"] - track_a_row["spy_beta"]
    bil_delta_reduction = track_a_row["avg_BIL"] - row["avg_BIL"]
    beta_explained = beta_delta * equity_premium
    cash_drag_reduction = bil_delta_reduction * equity_premium
    residual_after_beta = delta_return - beta_explained
    residual_after_beta_cash = delta_return - beta_explained - cash_drag_reduction
    if delta_return <= 0:
        label = "no_return_improvement"
    elif residual_after_beta_cash > 0:
        label = "possible_independent_alpha"
    else:
        label = "mostly_beta_or_cash_drag"
    return {
        "name": name,
        "kind": row["kind"],
        "ann_return": row["ann_return"],
        "delta_ann_return_vs_track_a": delta_return,
        "spy_beta": row["spy_beta"],
        "delta_spy_beta_vs_track_a": beta_delta,
        "avg_BIL": row["avg_BIL"],
        "delta_avg_BIL_vs_track_a": row["avg_BIL"] - track_a_row["avg_BIL"],
        "cash_drag_reduction_est_ann": cash_drag_reduction,
        "beta_explained_return_est_ann": beta_explained,
        "residual_return_vs_track_a_est_ann": residual_after_beta,
        "beta_cash_adjusted_residual_vs_track_a_est_ann": residual_after_beta_cash,
        "return_source_label": label,
        **category_contributions(name, weights, path, next_returns),
    }


def standalone_gates(row: pd.Series, cost2: pd.Series | None, max_existing_corr: float) -> dict[str, Any]:
    cost2_ann_return = np.nan if cost2 is None else cost2.get("ann_return", np.nan)
    cost2_sharpe = np.nan if cost2 is None else cost2.get("sharpe", np.nan)
    gates = {
        "positive_return_or_sharpe": bool(row["ann_return"] > 0.025 or row["sharpe"] > 0.30),
        "positive_beta_adjusted_residual": bool(row.get("beta_adjusted_residual_ann", np.nan) > 0.0),
        "turnover_realistic": bool(row["avg_weekly_turnover"] <= 0.25),
        "survives_2x_cost_return": bool(np.isfinite(cost2_ann_return) and cost2_ann_return > 0.0),
        "survives_2x_cost_sharpe": bool(np.isfinite(cost2_sharpe) and cost2_sharpe > 0.20),
        "not_track_a_clone": bool(row["track_a_corr"] < 0.90 or not np.isfinite(row["track_a_corr"])),
        "not_existing_sleeve_clone": bool(max_existing_corr < 0.90 or not np.isfinite(max_existing_corr)),
        "drawdown_not_extreme": bool(row["max_drawdown"] >= -0.45),
    }
    score = int(sum(gates.values()))
    gates["standalone_gate_score"] = score
    gates["standalone_sanity_pass"] = bool(
        score >= 6
        and gates["positive_beta_adjusted_residual"]
        and gates["turnover_realistic"]
        and gates["survives_2x_cost_return"]
        and gates["drawdown_not_extreme"]
    )
    return gates


def blend_gates(row: pd.Series, cost2: pd.Series | None, parent_row: pd.Series, track_a_row: pd.Series) -> dict[str, Any]:
    cost2_ann_return = np.nan if cost2 is None else cost2.get("ann_return", np.nan)
    cost2_sharpe = np.nan if cost2 is None else cost2.get("sharpe", np.nan)
    return_gate = bool(
        (row["delta_ann_return_vs_track_a"] >= 0.005 and row["delta_max_drawdown_vs_track_a"] >= -0.02)
        or (row["delta_sharpe_vs_track_a"] >= 0.03 and row["delta_ann_return_vs_track_a"] >= -0.002)
        or (
            (row["delta_max_drawdown_vs_track_a"] >= 0.01 or row["delta_cvar_5_vs_track_a"] >= 0.002)
            and row["delta_ann_return_vs_track_a"] >= -0.002
        )
    )
    gates = {
        "performance_gate": return_gate,
        "positive_beta_cash_adjusted_residual": bool(row.get("beta_cash_adjusted_residual_vs_track_a_est_ann", np.nan) > 0.0),
        "survives_2x_cost_return": bool(np.isfinite(cost2_ann_return) and cost2_ann_return >= track_a_row["ann_return"] - 0.002),
        "survives_2x_cost_sharpe": bool(np.isfinite(cost2_sharpe) and cost2_sharpe >= track_a_row["sharpe"] - 0.08),
        "turnover_increment_ok": bool(row["avg_weekly_turnover"] <= track_a_row["avg_weekly_turnover"] + 0.03),
        "drawdown_not_materially_worse": bool(row["delta_max_drawdown_vs_track_a"] >= -0.02),
        "cvar_not_materially_worse": bool(row["delta_cvar_5_vs_track_a"] >= -0.004),
        "parent_not_clone": bool(parent_row["max_abs_existing_sleeve_corr"] < 0.90 or not np.isfinite(parent_row["max_abs_existing_sleeve_corr"])),
        "holdout_does_not_collapse": bool(row["holdout_ann_return"] > 0.0 and row["holdout_sharpe"] > 0.50),
    }
    score = int(sum(gates.values()))
    gates["blend_gate_score"] = score
    gates["track_c_watchlist"] = bool(
        gates["performance_gate"]
        and gates["positive_beta_cash_adjusted_residual"]
        and gates["survives_2x_cost_return"]
        and gates["drawdown_not_materially_worse"]
        and score >= 6
    )
    return gates


def weights_to_long(name: str, kind: str, weights: pd.DataFrame) -> pd.DataFrame:
    long = weights.copy()
    long.insert(0, "Date", long.index)
    out = long.melt(id_vars="Date", var_name="Ticker", value_name="weight")
    out.insert(0, "kind", kind)
    out.insert(0, "name", name)
    return out


def path_return_frame(name: str, path: pd.DataFrame) -> pd.DataFrame:
    return path[["Date", "net_return"]].rename(columns={"net_return": name})


def reference_comparison(track_a_row: pd.Series) -> pd.DataFrame:
    rows = []
    if (TRACK_B_OUT / "track_b_benchmark_metrics.csv").exists():
        bench = pd.read_csv(TRACK_B_OUT / "track_b_benchmark_metrics.csv")
        keep = {
            "track_a_production",
            "spy_buy_hold",
            "static_60_spy_40_ief",
            "static_80_spy_20_bil",
            "aggressive_taa_spy_trend",
            "dual_momentum_top1",
            "static_global_growth_90_10",
        }
        rows.extend(bench[bench["name"].isin(keep)].assign(reference_group="track_b_benchmark").to_dict(orient="records"))
    else:
        rows.append({**track_a_row.to_dict(), "reference_group": "track_a"})
    if (TRACK_B_OUT / "track_b_candidate_metrics.csv").exists():
        candidates = pd.read_csv(TRACK_B_OUT / "track_b_candidate_metrics.csv")
        shortlist_names: set[str] = set()
        shortlist_path = TRACK_B_OUT / "track_b_shortlist.csv"
        if shortlist_path.exists():
            shortlist = pd.read_csv(shortlist_path)
            if "track_b_shortlist" in shortlist.columns:
                flag = shortlist["track_b_shortlist"].astype(str).str.lower().isin({"true", "1", "yes"})
                shortlist_names = set(shortlist.loc[flag, "name"].astype(str))
        if shortlist_names:
            rows.extend(candidates[candidates["name"].isin(shortlist_names)].assign(reference_group="track_b_shortlist").to_dict(orient="records"))
        if not candidates.empty:
            best = candidates.sort_values("ann_return", ascending=False).head(1).assign(reference_group="track_b_best_return")
            rows.extend(best.to_dict(orient="records"))
    return pd.DataFrame(rows)


def write_markdown_report(
    standalone_metrics: pd.DataFrame,
    blend_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    attribution: pd.DataFrame,
    correlations: pd.DataFrame,
    state_rows: pd.DataFrame,
    registry: pd.DataFrame,
    reference_metrics: pd.DataFrame,
) -> str:
    metric_cols = [
        "name",
        "ann_return",
        "sharpe",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "avg_BIL",
        "avg_equity",
        "spy_beta",
        "track_a_corr",
        "avg_weekly_turnover",
        "holdout_sharpe",
    ]
    attr_cols = [
        "name",
        "kind",
        "ann_return",
        "delta_ann_return_vs_track_a",
        "spy_beta",
        "avg_BIL",
        "cash_drag_reduction_est_ann",
        "beta_explained_return_est_ann",
        "beta_cash_adjusted_residual_vs_track_a_est_ann",
        "beta_adjusted_residual_ann",
        "return_source_label",
    ]
    cost_cols = ["name", "kind", "cost_multiplier", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_weekly_turnover"]
    corr_cols = ["name", "kind", "reference_type", "reference_name", "correlation"]
    gate_cols = ["candidate_name", "candidate_kind", "parent_candidate", "verdict", "gate_score", "verdict_reason"]
    watchlist = registry[registry["verdict"].eq("research_watchlist")]
    diagnostic = registry[registry["verdict"].eq("diagnostic_only")]
    rejected = registry[registry["verdict"].eq("rejected")]
    best_standalone = standalone_metrics.sort_values(["beta_adjusted_residual_ann", "sharpe"], ascending=False).head(1)
    best_blend = blend_metrics.sort_values(["track_c_watchlist", "beta_cash_adjusted_residual_vs_track_a_est_ann", "sharpe"], ascending=False).head(1) if not blend_metrics.empty else pd.DataFrame()
    return_improvers = blend_metrics[blend_metrics.get("delta_ann_return_vs_track_a", pd.Series(dtype=float)) > 0] if not blend_metrics.empty else pd.DataFrame()
    if not watchlist.empty:
        verdict = "Track C found a credible new alpha source worth forward paper tracking."
    elif not diagnostic.empty and not best_standalone.empty and float(best_standalone.iloc[0].get("beta_adjusted_residual_ann", np.nan)) > 0:
        verdict = "Track C found diversifying sleeves, but not enough evidence for return improvement."
    elif not return_improvers.empty:
        verdict = "Track C found improvements that are mostly beta/cash-drag, not true alpha."
    else:
        verdict = "Track C failed to find a compelling new alpha source."

    lines = [
        "# Track C New Alpha Research Report",
        "",
        "## 1. Track C Objective",
        "",
        "Test whether a small number of research-only new-alpha sleeves can improve Track A after controlling for SPY beta, BIL/cash drag, transaction costs, turnover, drawdown, and repeated experimentation. Track A production is unchanged.",
        "",
        "## 2. Track A Baseline",
        "",
        f"- Production candidate: `{PRODUCTION_CANDIDATE}`",
        f"- Official holdout start: `{OFFICIAL_HOLDOUT_START.date()}`",
        "- Canonical metrics/cost modules: `scripts/production_metrics.py`, `scripts/production_costs.py`",
        "",
        markdown_table(reference_metrics[[c for c in metric_cols if c in reference_metrics.columns]].head(8)),
        "",
        "## 3. Track B Lesson Learned",
        "",
        "Track B tested higher-risk variants and showed that higher returns were largely explained by higher SPY beta and lower BIL/cash drag. Track C therefore treats raw return improvement as insufficient unless beta/cash-adjusted residual is positive.",
        "",
        "## 4. Earlier Research Ideas Considered",
        "",
        "- Already implemented sufficiently: raw xsmom/tsmom, multi-horizon momentum, HRP/HERC/risk-parity allocator variants, and Track B cash/offense overlays.",
        "- Implemented but incomplete or flawed: residual momentum, carry/value ETF proxies, short-horizon reversal, HYG/LQD pair diagnostics, volatility-managed alpha, and canary/breadth timing.",
        "- Not selected: CVaR optimizer diagnostics and Black-Litterman because Track C is an alpha-sleeve audit, not an allocator redesign.",
        "- Requires unavailable data: point-in-time stock breadth, holdings breadth, and richer macro/credit series.",
        "- Explicitly out of scope: ML/meta-labeling and large parameter sweeps.",
        "",
        "## 5. Ideas Selected And Why",
        "",
        "Six predeclared sleeves were tested: residual xsmom, vol-managed residual xsmom, carry/value, neutral reversal, HYG/LQD pair mean reversion, and canary/breadth timing. Each uses existing repo data and has a different failure mode than Track B cash/offense overlays.",
        "",
        "## 6. Ideas Rejected Before Implementation And Why",
        "",
        "CVaR optimization, Black-Litterman, new macro/credit conditioning, PIT breadth, and ML were rejected before implementation because they either duplicate prior allocator research, need new data, or create overfit risk outside Track C's small-candidate mandate.",
        "",
        "## 7. Standalone Sleeve Results",
        "",
        markdown_table(standalone_metrics[[c for c in metric_cols + ["beta_adjusted_residual_ann", "standalone_sanity_pass"] if c in standalone_metrics.columns]].sort_values("sharpe", ascending=False)),
        "",
        "## 8. Blend-With-Track-A Results",
        "",
        markdown_table(blend_metrics[[c for c in metric_cols + ["delta_ann_return_vs_track_a", "delta_sharpe_vs_track_a", "beta_cash_adjusted_residual_vs_track_a_est_ann", "track_c_watchlist"] if c in blend_metrics.columns]].sort_values("sharpe", ascending=False) if not blend_metrics.empty else pd.DataFrame()),
        "",
        "## 9. Cost Sensitivity",
        "",
        markdown_table(cost_metrics[cost_metrics["cost_multiplier"].isin([2.0, 3.0])][[c for c in cost_cols if c in cost_metrics.columns]].head(40)),
        "",
        "## 10. Turnover Analysis",
        "",
        "Turnover is canonical one-way turnover from `scripts/production_costs.py`. Reversal and pair sleeves were expected to be the most vulnerable to cost drag; any watchlist candidate must survive at least 2x costs.",
        "",
        markdown_table(standalone_metrics[["name", "avg_weekly_turnover", "annualized_turnover", "annualized_cost"]].sort_values("avg_weekly_turnover", ascending=False)),
        "",
        "## 11. Beta-Adjusted Attribution",
        "",
        "Standalone residual compares each sleeve against a BIL plus SPY-beta expected-return proxy. Blend residual subtracts both incremental SPY beta and estimated BIL/cash-drag reduction versus Track A.",
        "",
        markdown_table(attribution[[c for c in attr_cols if c in attribution.columns]].head(60)),
        "",
        "## 12. Correlation/Diversification Analysis",
        "",
        markdown_table(correlations[[c for c in corr_cols if c in correlations.columns]].head(80)),
        "",
        "## 13. State-By-State Performance",
        "",
        markdown_table(state_rows[["name", "kind", "market_state", "ann_return", "sharpe", "max_drawdown", "cvar_5"]].head(80)),
        "",
        "## 14. Multiple-Testing/Governance Summary",
        "",
        f"- Predeclared standalone sleeves tested: `{len(CANDIDATES)}`",
        f"- Blends tested after standalone gates: `{int((registry['candidate_kind'] == 'blend').sum())}`",
        "- All candidates are `research_only`; no Track C output writes to the production registry.",
        "- DSR/PSR proxy fields are included in machine-readable metrics using Track A's statistical validation helpers.",
        "",
        markdown_table(registry[[c for c in gate_cols if c in registry.columns]]),
        "",
        "## 15. Research Watchlist",
        "",
        markdown_table(watchlist[[c for c in gate_cols if c in watchlist.columns]]),
        "",
        "## 16. Rejected Candidates",
        "",
        markdown_table(rejected[[c for c in gate_cols if c in rejected.columns]].head(40)),
        "",
        "## 17. What Should Be Tested Next",
        "",
        "- No Track C candidate should be production-promoted from this sprint.",
        "- Diagnostic follow-up, if any, should focus only on canary/breadth timing and vol-managed residual momentum because those were the only standalone sleeves to pass sanity gates.",
        "- Revisit canary/breadth only with explicit false-defense and false-risk-on diagnostics, then require a positive blend-level beta/cash-adjusted residual before watchlisting.",
        "- Prioritize data expansion only where point-in-time coverage is credible.",
        "",
        "## 18. What Should Not Be Pursued",
        "",
        "- Do not promote Track C candidates from this sprint.",
        "- Do not turn weak carry/value or reversal results into parameter sweeps.",
        "- Do not relabel Track B beta/cash overlays as alpha.",
        "- Do not add ML until the experiment registry, purged validation, and trial accounting are stronger than the expected lift.",
        "",
        "## 19. Final Verdict",
        "",
        verdict,
        "",
        "Machine-readable outputs are saved under `data/research/track_c_new_alpha/`.",
    ]
    (DOC / "track_c_new_alpha_research_report.md").write_text("\n".join(lines).rstrip() + "\n")
    return verdict


def main() -> None:
    ensure_dirs()
    registry_pin = require_official_production_pin()
    created_at = datetime.now(timezone.utc).isoformat()

    prices = read_dated(HUB / "weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    next_returns = next_week_returns_from_prices(prices)
    track_a_weights = read_dated(weights_path(PRODUCTION_CANDIDATE))
    columns = list(track_a_weights.columns)
    common = track_a_weights.index.intersection(next_returns.index)
    track_a_weights = normalize_to_bil(track_a_weights.reindex(index=common, columns=columns).fillna(0.0))
    track_a_path = read_dated(returns_path(PRODUCTION_CANDIDATE)).reset_index()
    track_a_path = track_a_path.rename(columns={track_a_path.columns[0]: "Date"}) if "Date" not in track_a_path.columns else track_a_path
    track_a_metrics = evaluate(
        "track_a_production",
        "benchmark",
        track_a_weights,
        track_a_path,
        next_returns,
        None,
        None,
        trial_count(),
    )
    track_a_ret = track_a_path.set_index("Date")["net_return"]

    market_history = read_dated(REGIME / "market_state_history.csv")
    regime_states = read_dated(REGIME / "regime_states.csv")
    market_states = market_history["market_state"].reindex(common)
    existing_sleeves = load_existing_sleeve_returns()

    residual_scores = read_signal_matrix(SIGNALS / "signal_residual_momentum.csv", "residual_mom_score_tradable").reindex(index=common, columns=columns)
    carry_scores = read_signal_matrix(SIGNALS / "signal_carry.csv", "carry_score_tradable").reindex(index=common, columns=columns)
    value_scores = read_signal_matrix(SIGNALS / "signal_value.csv", "value_score_tradable").reindex(index=common, columns=columns)
    cv_counts = carry_scores.notna().astype(float) + value_scores.notna().astype(float)
    carry_value_scores = (carry_scores.fillna(0.0) + value_scores.fillna(0.0)) / cv_counts.replace(0.0, np.nan)
    reversal_scores = read_signal_matrix(SIGNALS / "signal_reversal.csv", "reversal_4w_score_tradable").reindex(index=common, columns=columns)

    neutral_mask = market_history["market_state"].reindex(common).astype(str).eq("neutral_mixed")
    reversal_env = regime_states["signal_environment"].reindex(common).astype(str).eq("reversal_friendly")
    reversal_active = neutral_mask | reversal_env

    candidate_weights: dict[str, pd.DataFrame] = {
        "track_c_residual_xsmom_top5": rank_top_weights(residual_scores, common, columns, top_n=5, positive_only=True),
        "track_c_vol_managed_residual_xsmom_top5": build_vol_managed_residual(residual_scores, prices, common, columns),
        "track_c_carry_value_top5": rank_top_weights(carry_value_scores, common, columns, top_n=5, positive_only=True),
        "track_c_neutral_reversal_top5": rank_top_weights(reversal_scores, common, columns, top_n=5, positive_only=True, active_mask=reversal_active),
    }
    pair_weights, pair_signal = build_pair_weights(SIGNALS / "signal_r4_pair_hyg_lqd.csv", common, columns)
    candidate_weights["track_c_hyg_lqd_pair_mean_reversion"] = pair_weights
    canary_weights, canary_score = build_canary_breadth_weights(market_history, common, columns)
    candidate_weights["track_c_canary_breadth_timing"] = canary_weights

    signal_for_ic: dict[str, tuple[str, pd.DataFrame | pd.Series, pd.Series | None]] = {
        "track_c_residual_xsmom_top5": ("cross_sectional_rank_ic", residual_scores, None),
        "track_c_vol_managed_residual_xsmom_top5": ("cross_sectional_rank_ic", residual_scores, None),
        "track_c_carry_value_top5": ("cross_sectional_rank_ic", carry_value_scores, None),
        "track_c_neutral_reversal_top5": ("cross_sectional_rank_ic", reversal_scores.where(reversal_active, np.nan), None),
        "track_c_hyg_lqd_pair_mean_reversion": ("time_series_pair_ic", pair_signal, next_returns["HYG"].sub(next_returns["LQD"], fill_value=0.0)),
        "track_c_canary_breadth_timing": ("time_series_spy_timing_ic", canary_score, next_returns["SPY"]),
    }

    trials = trial_count()
    spy_weights = static_allocation_frame(common, columns, {"SPY": 1.0})
    spy_path = portfolio_path(spy_weights, next_returns)
    spy_cagr = metrics_from_path(spy_path, weights=spy_weights)["ann_return"]
    bil_weights = static_allocation_frame(common, columns, {"BIL": 1.0})
    bil_path = portfolio_path(bil_weights, next_returns)
    bil_cagr = metrics_from_path(bil_path, weights=bil_weights)["ann_return"]

    standalone_metric_rows = []
    standalone_paths: dict[str, pd.DataFrame] = {}
    standalone_return_frames = []
    standalone_weight_frames = []
    cost_frames = []
    state_frames = []
    rolling_frames = []
    ic_rows = []
    corr_rows_all = []
    attribution_rows = []
    registry_rows = []

    for spec in CANDIDATES:
        weights = candidate_weights[spec.name]
        path = portfolio_path(weights, next_returns)
        standalone_paths[spec.name] = path
        returns = path.set_index("Date")["net_return"]
        metrics = evaluate(spec.name, "standalone_sleeve", weights, path, next_returns, track_a_metrics, track_a_ret, trials)
        corr_rows, max_existing_corr = correlation_rows(spec.name, "standalone_sleeve", returns, track_a_ret, existing_sleeves)
        corr_rows_all.extend(corr_rows)
        metrics["max_abs_existing_sleeve_corr"] = max_existing_corr
        attr = standalone_attribution(spec.name, pd.Series(metrics), path, weights, next_returns, spy_cagr, bil_cagr)
        metrics["beta_adjusted_residual_ann"] = attr["beta_adjusted_residual_ann"]
        cdf = cost_sensitivity(spec.name, "standalone_sleeve", weights, next_returns)
        cost_frames.append(cdf)
        cost2 = cdf[cdf["cost_multiplier"].eq(2.0)].set_index("name")
        gates = standalone_gates(pd.Series(metrics), cost2.loc[spec.name] if spec.name in cost2.index else None, max_existing_corr)
        metrics.update(gates)
        attr.update({"standalone_sanity_pass": gates["standalone_sanity_pass"]})
        attribution_rows.append(attr)
        standalone_metric_rows.append(metrics)
        state_frames.append(state_metrics(spec.name, "standalone_sleeve", path, market_states))
        roll = rolling_origin_metrics(returns)
        if not roll.empty:
            roll.insert(0, "kind", "standalone_sleeve")
            roll.insert(0, "name", spec.name)
            rolling_frames.append(roll)
        standalone_return_frames.append(path_return_frame(spec.name, path))
        standalone_weight_frames.append(weights_to_long(spec.name, "standalone_sleeve", weights))
        ic_type, signal_obj, target = signal_for_ic[spec.name]
        if ic_type == "cross_sectional_rank_ic":
            ic_rows.append(cross_sectional_rank_ic(spec.name, signal_obj, next_returns))
        else:
            ic_rows.append(time_series_ic(spec.name, signal_obj, target, ic_type))
        verdict = "diagnostic_only" if gates["standalone_sanity_pass"] else "rejected"
        reason = "standalone sanity gate passed; eligible for small Track A overlay" if gates["standalone_sanity_pass"] else "failed standalone sanity gate"
        registry_rows.append(
            {
                "candidate_name": spec.name,
                "candidate_kind": "standalone_sleeve",
                "research_status": "research_only",
                "parent_candidate": "none",
                "source_script": rel(Path(__file__)),
                "created_at_utc": created_at,
                "hypothesis": spec.hypothesis,
                "parameters": json.dumps(clean_json(spec.parameters), sort_keys=True),
                "success_criteria": spec.success_criteria,
                "kill_criteria": spec.kill_criteria,
                "promotion_status": "not_eligible_track_c_research_only",
                "verdict": verdict,
                "gate_score": gates["standalone_gate_score"],
                "verdict_reason": reason,
            }
        )

    standalone_metrics = pd.DataFrame(standalone_metric_rows)

    blend_metric_rows = []
    blend_paths: dict[str, pd.DataFrame] = {}
    blend_return_frames = []
    blend_weight_frames = []
    for spec in CANDIDATES:
        parent_row = standalone_metrics.set_index("name").loc[spec.name]
        if not bool(parent_row["standalone_sanity_pass"]):
            continue
        sleeve_weights = candidate_weights[spec.name]
        for overlay in OVERLAY_WEIGHTS:
            pct = int(round(overlay * 100))
            blend_name = f"track_c_track_a_plus_{spec.name.replace('track_c_', '')}_{pct:02d}"
            blend_weights = normalize_to_bil((1.0 - overlay) * track_a_weights + overlay * sleeve_weights)
            path = portfolio_path(blend_weights, next_returns)
            blend_paths[blend_name] = path
            returns = path.set_index("Date")["net_return"]
            metrics = evaluate(blend_name, "track_a_blend", blend_weights, path, next_returns, track_a_metrics, track_a_ret, trials)
            metrics["parent_candidate"] = spec.name
            corr_rows, max_existing_corr = correlation_rows(blend_name, "track_a_blend", returns, track_a_ret, existing_sleeves)
            corr_rows_all.extend(corr_rows)
            metrics["max_abs_existing_sleeve_corr"] = max_existing_corr
            attr = blend_attribution(blend_name, pd.Series(metrics), pd.Series(track_a_metrics), path, blend_weights, next_returns, spy_cagr, bil_cagr)
            metrics["beta_cash_adjusted_residual_vs_track_a_est_ann"] = attr["beta_cash_adjusted_residual_vs_track_a_est_ann"]
            metrics["residual_return_vs_track_a_est_ann"] = attr["residual_return_vs_track_a_est_ann"]
            cdf = cost_sensitivity(blend_name, "track_a_blend", blend_weights, next_returns)
            cost_frames.append(cdf)
            cost2 = cdf[cdf["cost_multiplier"].eq(2.0)].set_index("name")
            gates = blend_gates(pd.Series(metrics), cost2.loc[blend_name] if blend_name in cost2.index else None, parent_row, pd.Series(track_a_metrics))
            metrics.update(gates)
            attr.update({"track_c_watchlist": gates["track_c_watchlist"], "parent_candidate": spec.name, "overlay_weight": overlay})
            attribution_rows.append(attr)
            blend_metric_rows.append(metrics)
            state_frames.append(state_metrics(blend_name, "track_a_blend", path, market_states))
            roll = rolling_origin_metrics(returns)
            if not roll.empty:
                roll.insert(0, "kind", "track_a_blend")
                roll.insert(0, "name", blend_name)
                rolling_frames.append(roll)
            blend_return_frames.append(path_return_frame(blend_name, path))
            blend_weight_frames.append(weights_to_long(blend_name, "track_a_blend", blend_weights))
            if gates["track_c_watchlist"]:
                verdict = "research_watchlist"
                reason = "blend passed Track C watchlist gates; research-only forward paper tracking only"
            elif metrics["delta_ann_return_vs_track_a"] > 0 or metrics["delta_sharpe_vs_track_a"] > 0:
                verdict = "diagnostic_only"
                reason = "some improvement but failed enough Track C watchlist gates"
            else:
                verdict = "rejected"
                reason = "blend did not improve Track A enough to justify complexity"
            registry_rows.append(
                {
                    "candidate_name": blend_name,
                    "candidate_kind": "blend",
                    "research_status": "research_only",
                    "parent_candidate": spec.name,
                    "source_script": rel(Path(__file__)),
                    "created_at_utc": created_at,
                    "hypothesis": f"Blend {pct}% of {spec.name} into Track A funded proportionally.",
                    "parameters": json.dumps({"overlay_weight": overlay, "funding": "proportional_from_track_a", "parent_parameters": spec.parameters}, sort_keys=True),
                    "success_criteria": "Pass Track C blend gates without production promotion.",
                    "kill_criteria": "Reject if improvement is noise, beta/cash-drag, or fails cost/drawdown gates.",
                    "promotion_status": "not_eligible_track_c_research_only",
                    "verdict": verdict,
                    "gate_score": gates["blend_gate_score"],
                    "verdict_reason": reason,
                }
            )

    blend_metrics = pd.DataFrame(blend_metric_rows)
    all_cost = pd.concat(cost_frames, ignore_index=True)
    all_state = pd.concat(state_frames, ignore_index=True)
    rolling = pd.concat(rolling_frames, ignore_index=True) if rolling_frames else pd.DataFrame()
    ic = pd.DataFrame(ic_rows)
    correlations = pd.DataFrame(corr_rows_all)
    attribution = pd.DataFrame(attribution_rows)
    registry = pd.DataFrame(registry_rows)
    reference_metrics = reference_comparison(pd.Series(track_a_metrics))

    standalone_returns = standalone_return_frames[0]
    for frame in standalone_return_frames[1:]:
        standalone_returns = standalone_returns.merge(frame, on="Date", how="outer")
    blend_returns = pd.DataFrame({"Date": common})
    if blend_return_frames:
        blend_returns = blend_return_frames[0]
        for frame in blend_return_frames[1:]:
            blend_returns = blend_returns.merge(frame, on="Date", how="outer")

    standalone_returns.to_csv(OUT / "track_c_standalone_sleeve_returns.csv", index=False)
    pd.concat(standalone_weight_frames, ignore_index=True).to_csv(OUT / "track_c_standalone_sleeve_weights.csv", index=False)
    standalone_metrics.to_csv(OUT / "track_c_standalone_sleeve_metrics.csv", index=False)
    blend_returns.to_csv(OUT / "track_c_blend_returns.csv", index=False)
    if blend_weight_frames:
        pd.concat(blend_weight_frames, ignore_index=True).to_csv(OUT / "track_c_blend_weights.csv", index=False)
    else:
        pd.DataFrame(columns=["name", "kind", "Date", "Ticker", "weight"]).to_csv(OUT / "track_c_blend_weights.csv", index=False)
    blend_metrics.to_csv(OUT / "track_c_blend_metrics.csv", index=False)
    all_cost.to_csv(OUT / "track_c_cost_sensitivity.csv", index=False)
    all_state.to_csv(OUT / "track_c_state_metrics.csv", index=False)
    rolling.to_csv(OUT / "track_c_rolling_origin_metrics.csv", index=False)
    ic.to_csv(OUT / "track_c_signal_ic.csv", index=False)
    correlations.to_csv(OUT / "track_c_correlations.csv", index=False)
    attribution.to_csv(OUT / "track_c_beta_adjusted_attribution.csv", index=False)
    registry.to_csv(OUT / "track_c_experiment_registry.csv", index=False)
    reference_metrics.to_csv(OUT / "track_c_reference_comparison.csv", index=False)

    verdict = write_markdown_report(standalone_metrics, blend_metrics, all_cost, attribution, correlations, all_state, registry, reference_metrics)

    manifest = {
        "track": "track_c_new_alpha",
        "research_status": "research_only",
        "created_at_utc": created_at,
        "production_candidate": PRODUCTION_CANDIDATE,
        "registry_pin_verified": registry_pin.get("current_production_pin"),
        "track_a_returns_sha256": sha256_file(returns_path(PRODUCTION_CANDIDATE)),
        "track_a_weights_sha256": sha256_file(weights_path(PRODUCTION_CANDIDATE)),
        "standalone_candidate_count": len(CANDIDATES),
        "blend_candidate_count": int(len(blend_metrics)),
        "final_verdict": verdict,
        "output_files": {
            "standalone_returns": rel(OUT / "track_c_standalone_sleeve_returns.csv"),
            "standalone_weights": rel(OUT / "track_c_standalone_sleeve_weights.csv"),
            "standalone_metrics": rel(OUT / "track_c_standalone_sleeve_metrics.csv"),
            "blend_returns": rel(OUT / "track_c_blend_returns.csv"),
            "blend_weights": rel(OUT / "track_c_blend_weights.csv"),
            "blend_metrics": rel(OUT / "track_c_blend_metrics.csv"),
            "experiment_registry": rel(OUT / "track_c_experiment_registry.csv"),
            "report": rel(DOC / "track_c_new_alpha_research_report.md"),
        },
    }
    (OUT / "track_c_candidate_manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, allow_nan=False) + "\n")
    print(f"Track C complete: {len(CANDIDATES)} standalone sleeves, {len(blend_metrics)} blends. Verdict: {verdict}")


if __name__ == "__main__":
    main()
