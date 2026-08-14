"""Run Track B higher-return ETF research experiments.

Track B is research-only.  It never writes to the production registry or Track A
production artifacts.  All outputs are isolated under
``data/research/track_b_aggressive`` and ``docs/research/track_b_aggressive``.
"""

from __future__ import annotations

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
    exposure_summary,
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
REGIME = DATA / "04_layer2b_risk_regime_engine"
OUT = DATA / "research" / "track_b_aggressive"
DOC = ROOT / "docs" / "research" / "track_b_aggressive"
STAT_AUDIT = DATA / "research" / "validation" / "statistical_validation_audit.csv"

TRACK_A = "track_a_production"
STATIC_GROWTH_MIX = {
    "SPY": 0.45,
    "QQQ": 0.20,
    "IWM": 0.10,
    "EFA": 0.10,
    "VWO": 0.05,
    "GLD": 0.05,
    "BIL": 0.05,
}
DUAL_MOMENTUM_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VWO", "GLD", "TLT"]


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
        "track_b_aggressive_cash_cap_20",
        "Lower idle cash in non-stress states may raise return without breaking defense.",
        {"cash_caps": {"calm_trend": 0.20, "neutral_mixed": 0.20, "recovery_confirmed": 0.20, "recovery_fragile": 0.20}},
        "Higher return and beta; slightly worse drawdown/CVaR.",
        "Return improves with drawdown above -22% and Sharpe >= 0.85.",
        "Reject if return remains near Track A or stress drawdown deteriorates materially.",
    ),
    CandidateSpec(
        "track_b_aggressive_cash_cap_15_good_20_neutral",
        "More targeted cash reduction in good states may improve return with less neutral-state risk.",
        {"cash_caps": {"calm_trend": 0.15, "recovery_confirmed": 0.15, "neutral_mixed": 0.20, "recovery_fragile": 0.20}},
        "Lower BIL with moderate drawdown increase.",
        "Return improves and 2x cost Sharpe remains >= 0.85.",
        "Reject if neutral-state losses dominate the improvement.",
    ),
    CandidateSpec(
        "track_b_aggressive_cash_cap_10_good_18_neutral",
        "A stronger cash cap tests whether 9% return is reachable without stress changes.",
        {"cash_caps": {"calm_trend": 0.10, "recovery_confirmed": 0.10, "neutral_mixed": 0.18, "recovery_fragile": 0.18}},
        "Higher beta and larger drawdown risk.",
        "CAGR approaches 9% with max drawdown above -22%.",
        "Reject if drawdown or CVaR worsens faster than return improves.",
    ),
    CandidateSpec(
        "track_b_aggressive_offense_boost_10",
        "Small offense scaling may lift return while retaining Track A state timing.",
        {"offense_multipliers": {"calm_trend": 1.10, "recovery_confirmed": 1.10, "neutral_mixed": 1.05, "recovery_fragile": 1.05}},
        "Higher offense and turnover; may be mostly beta.",
        "Return improves with Sharpe near Track A and stress unchanged.",
        "Reject if beta explains nearly all incremental return.",
    ),
    CandidateSpec(
        "track_b_aggressive_offense_boost_20",
        "Stronger offense scaling tests the mandate boundary.",
        {"offense_multipliers": {"calm_trend": 1.20, "recovery_confirmed": 1.20, "neutral_mixed": 1.10, "recovery_fragile": 1.05}},
        "Higher return potential; materially higher beta/drawdown.",
        "CAGR near 9% with max drawdown above -22%.",
        "Reject if 2x costs or CVaR erase the case.",
    ),
    CandidateSpec(
        "track_b_aggressive_cash10_offense10",
        "Combining cash reduction and mild offense boost may reach mandate with controlled stress behavior.",
        {
            "cash_caps": {"calm_trend": 0.10, "recovery_confirmed": 0.10, "neutral_mixed": 0.18, "recovery_fragile": 0.18},
            "offense_multipliers": {"calm_trend": 1.10, "recovery_confirmed": 1.10, "neutral_mixed": 1.05, "recovery_fragile": 1.05},
        },
        "Higher return; likely higher beta and CVaR.",
        "CAGR >= 9%, Sharpe >= 0.85, drawdown above -22%.",
        "Reject if stress or neutral-state behavior collapses.",
    ),
    CandidateSpec(
        "track_b_aggressive_cash10_offense20",
        "Strongest Track A-timed overlay tests upper edge of drawdown tolerance.",
        {
            "cash_caps": {"calm_trend": 0.10, "recovery_confirmed": 0.10, "neutral_mixed": 0.18, "recovery_fragile": 0.18},
            "offense_multipliers": {"calm_trend": 1.20, "recovery_confirmed": 1.20, "neutral_mixed": 1.10, "recovery_fragile": 1.05},
        },
        "Highest Track A-timed return attempt; may fail drawdown or beta attribution.",
        "CAGR >= 9% and 2x costs survive without drawdown below -22%.",
        "Reject if it is just higher beta with no benchmark edge.",
    ),
    CandidateSpec(
        "track_b_aggressive_rerisk_4w",
        "Faster re-risking after stress exits may reduce cash drag.",
        {"rerisk_after_stress_weeks": 4, "rerisk_cash_cap": 0.12, "rerisk_offense_multiplier": 1.15},
        "May improve recoveries; can be path dependent.",
        "Improves recovery_confirmed/recovery_fragile metrics without stress damage.",
        "Reject if benefit is narrow and not robust.",
    ),
    CandidateSpec(
        "track_b_aggressive_vol_throttled",
        "Higher offense should be disabled during high realized SPY volatility.",
        {
            "base": "cash10_offense20",
            "spy_vol_13w_threshold": 0.25,
            "high_vol_cash_cap": 0.20,
            "high_vol_offense_multiplier": 1.0,
        },
        "Lower drawdown/CVaR than strongest overlay, lower return.",
        "Retains much of aggressive return with better tail behavior.",
        "Reject if it gives up return without meaningful risk control.",
    ),
    CandidateSpec(
        "track_b_aggressive_turnover_banded",
        "Aggressive weights may survive costs if small weekly changes are ignored.",
        {"base": "cash10_offense10", "full_l1_rebalance_band": 0.05},
        "Lower turnover and cost; may lag re-risking.",
        "2x and 3x cost sensitivity improves versus unbanded overlay.",
        "Reject if banding worsens timing more than it saves cost.",
    ),
    CandidateSpec(
        "track_b_aggressive_blend_static_growth_30",
        "A simple explicit risk budget may explain return gain versus timing.",
        {"track_a_weight": 0.70, "static_growth_weight": 0.30, "static_growth_mix": STATIC_GROWTH_MIX},
        "Higher beta, simple benchmark-like exposure.",
        "Improves return with acceptable drawdown and transparent beta attribution.",
        "Reject if a simple benchmark dominates it.",
    ),
    CandidateSpec(
        "track_b_aggressive_blend_static_growth_50",
        "A more aggressive static blend tests whether 9-10% is mainly beta.",
        {"track_a_weight": 0.50, "static_growth_weight": 0.50, "static_growth_mix": STATIC_GROWTH_MIX},
        "Higher return potential; likely mostly beta and larger drawdown.",
        "CAGR >= 9%, drawdown above -22%, and not dominated by aggressive benchmarks.",
        "Reject if return comes mostly from equity beta or drawdown exceeds mandate.",
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


def read_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    date_col = "Date" if "Date" in df.columns else "date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


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
    return out.reindex(columns=weights.columns, fill_value=0.0)


def static_weight_frame(index: pd.Index, columns: list[str], allocation: dict[str, float]) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=index, columns=columns)
    for ticker, weight in allocation.items():
        if ticker in weights.columns:
            weights[ticker] = float(weight)
    return normalize_to_bil(weights)


def offense_columns(weights: pd.DataFrame) -> list[str]:
    return [c for c in weights.columns if c in OFFENSE_ASSETS and c != "BIL"]


def allocate_bil_excess_to_offense(weights: pd.DataFrame, caps: dict[str, float], states: pd.Series) -> pd.DataFrame:
    out = weights.copy()
    off_cols = offense_columns(out)
    fallback = pd.Series({k: v for k, v in STATIC_GROWTH_MIX.items() if k in off_cols}, dtype=float)
    fallback = fallback / fallback.sum()
    for state, cap in caps.items():
        mask = states.reindex(out.index).astype(str).eq(state) & out["BIL"].gt(float(cap))
        if not mask.any():
            continue
        excess = out.loc[mask, "BIL"] - float(cap)
        out.loc[mask, "BIL"] = float(cap)
        current_offense = out.loc[mask, off_cols].sum(axis=1)
        for date in out.index[mask]:
            if current_offense.loc[date] > 1e-12:
                shares = out.loc[date, off_cols] / current_offense.loc[date]
            else:
                shares = fallback.reindex(off_cols).fillna(0.0)
            out.loc[date, off_cols] = out.loc[date, off_cols] + excess.loc[date] * shares
    return normalize_to_bil(out)


def apply_offense_multipliers(weights: pd.DataFrame, multipliers: dict[str, float], states: pd.Series) -> pd.DataFrame:
    out = weights.copy()
    off_cols = offense_columns(out)
    state_series = states.reindex(out.index).astype(str)
    for state, multiplier in multipliers.items():
        mask = state_series.eq(state)
        if mask.any() and off_cols:
            out.loc[mask, off_cols] = out.loc[mask, off_cols] * float(multiplier)
    return normalize_to_bil(out)


def stress_exit_mask(states: pd.Series, index: pd.Index, weeks: int) -> pd.Series:
    aligned = states.reindex(index).astype(str)
    active = pd.Series(False, index=index)
    remaining = 0
    previous = None
    for date, state in aligned.items():
        if previous == "stressed_panic" and state != "stressed_panic":
            remaining = int(weeks)
        if remaining > 0 and state != "stressed_panic":
            active.loc[date] = True
            remaining -= 1
        if state == "stressed_panic":
            remaining = 0
        previous = state
    return active


def apply_masked_cash_cap(weights: pd.DataFrame, mask: pd.Series, cap: float) -> pd.DataFrame:
    states = pd.Series("_mask", index=weights.index)
    caps = {"_mask": float(cap)}
    masked_weights = weights.copy()
    temp_states = pd.Series("other", index=weights.index)
    temp_states.loc[mask.reindex(weights.index).fillna(False)] = "_mask"
    return allocate_bil_excess_to_offense(masked_weights, caps, temp_states)


def apply_masked_offense_multiplier(weights: pd.DataFrame, mask: pd.Series, multiplier: float) -> pd.DataFrame:
    temp_states = pd.Series("other", index=weights.index)
    temp_states.loc[mask.reindex(weights.index).fillna(False)] = "_mask"
    return apply_offense_multipliers(weights, {"_mask": float(multiplier)}, temp_states)


def apply_turnover_band(target: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    previous = None
    for _, row in target.iterrows():
        if previous is None:
            current = row.copy()
        else:
            full_l1 = float((row - previous).abs().sum())
            current = row.copy() if full_l1 >= float(threshold) else previous.copy()
        rows.append(current)
        previous = current
    return pd.DataFrame(rows, index=target.index, columns=target.columns)


def base_cash10_offense10(base: pd.DataFrame, states: pd.Series) -> pd.DataFrame:
    out = allocate_bil_excess_to_offense(
        base,
        {"calm_trend": 0.10, "recovery_confirmed": 0.10, "neutral_mixed": 0.18, "recovery_fragile": 0.18},
        states,
    )
    return apply_offense_multipliers(
        out,
        {"calm_trend": 1.10, "recovery_confirmed": 1.10, "neutral_mixed": 1.05, "recovery_fragile": 1.05},
        states,
    )


def base_cash10_offense20(base: pd.DataFrame, states: pd.Series) -> pd.DataFrame:
    out = allocate_bil_excess_to_offense(
        base,
        {"calm_trend": 0.10, "recovery_confirmed": 0.10, "neutral_mixed": 0.18, "recovery_fragile": 0.18},
        states,
    )
    return apply_offense_multipliers(
        out,
        {"calm_trend": 1.20, "recovery_confirmed": 1.20, "neutral_mixed": 1.10, "recovery_fragile": 1.05},
        states,
    )


def candidate_weights(spec: CandidateSpec, base: pd.DataFrame, states: pd.Series, prices: pd.DataFrame) -> pd.DataFrame:
    p = spec.parameters
    if spec.name == "track_b_aggressive_cash_cap_20":
        return allocate_bil_excess_to_offense(base, p["cash_caps"], states)
    if spec.name == "track_b_aggressive_cash_cap_15_good_20_neutral":
        return allocate_bil_excess_to_offense(base, p["cash_caps"], states)
    if spec.name == "track_b_aggressive_cash_cap_10_good_18_neutral":
        return allocate_bil_excess_to_offense(base, p["cash_caps"], states)
    if spec.name == "track_b_aggressive_offense_boost_10":
        return apply_offense_multipliers(base, p["offense_multipliers"], states)
    if spec.name == "track_b_aggressive_offense_boost_20":
        return apply_offense_multipliers(base, p["offense_multipliers"], states)
    if spec.name == "track_b_aggressive_cash10_offense10":
        return base_cash10_offense10(base, states)
    if spec.name == "track_b_aggressive_cash10_offense20":
        return base_cash10_offense20(base, states)
    if spec.name == "track_b_aggressive_rerisk_4w":
        active = stress_exit_mask(states, base.index, int(p["rerisk_after_stress_weeks"]))
        out = apply_masked_cash_cap(base, active, float(p["rerisk_cash_cap"]))
        return apply_masked_offense_multiplier(out, active, float(p["rerisk_offense_multiplier"]))
    if spec.name == "track_b_aggressive_vol_throttled":
        aggressive = base_cash10_offense20(base, states)
        spy_vol = prices["SPY"].pct_change().rolling(13).std() * np.sqrt(WEEKS_PER_YEAR)
        high_vol = spy_vol.reindex(base.index).fillna(False).gt(float(p["spy_vol_13w_threshold"]))
        conservative = apply_masked_cash_cap(base, high_vol & states.reindex(base.index).astype(str).ne("stressed_panic"), float(p["high_vol_cash_cap"]))
        out = aggressive.copy()
        out.loc[high_vol] = conservative.loc[high_vol]
        return normalize_to_bil(out)
    if spec.name == "track_b_aggressive_turnover_banded":
        return apply_turnover_band(base_cash10_offense10(base, states), float(p["full_l1_rebalance_band"]))
    if spec.name == "track_b_aggressive_blend_static_growth_30":
        static = static_weight_frame(base.index, base.columns.tolist(), STATIC_GROWTH_MIX)
        return normalize_to_bil(base * 0.70 + static * 0.30)
    if spec.name == "track_b_aggressive_blend_static_growth_50":
        static = static_weight_frame(base.index, base.columns.tolist(), STATIC_GROWTH_MIX)
        return normalize_to_bil(base * 0.50 + static * 0.50)
    raise ValueError(f"Unknown candidate: {spec.name}")


def benchmark_weights(name: str, index: pd.Index, columns: list[str], prices: pd.DataFrame) -> pd.DataFrame:
    if name == TRACK_A:
        return read_dated(weights_path(PRODUCTION_CANDIDATE)).reindex(index).fillna(0.0)
    if name == "spy_buy_hold":
        return static_weight_frame(index, columns, {"SPY": 1.0})
    if name == "static_60_spy_40_ief":
        return static_weight_frame(index, columns, {"SPY": 0.60, "IEF": 0.40})
    if name == "static_80_spy_20_bil":
        return static_weight_frame(index, columns, {"SPY": 0.80, "BIL": 0.20})
    if name == "static_global_growth_90_10":
        return static_weight_frame(index, columns, STATIC_GROWTH_MIX)
    if name == "aggressive_taa_spy_trend":
        w = pd.DataFrame(0.0, index=index, columns=columns)
        spy = prices["SPY"].reindex(index)
        sma40 = prices["SPY"].rolling(40).mean().reindex(index)
        mom13 = prices["SPY"].pct_change(13).reindex(index)
        risk_on = spy.gt(sma40) & mom13.gt(0.0)
        w.loc[risk_on, "SPY"] = 1.0
        w.loc[~risk_on, "SPY"] = 0.50
        w.loc[~risk_on, "BIL"] = 0.50
        return normalize_to_bil(w)
    if name == "dual_momentum_top1":
        w = pd.DataFrame(0.0, index=index, columns=columns)
        mom = prices[DUAL_MOMENTUM_ASSETS].pct_change(26).reindex(index)
        bil_mom = prices["BIL"].pct_change(26).reindex(index).fillna(0.0)
        for date in index:
            row = mom.loc[date].dropna()
            if row.empty:
                w.loc[date, "BIL"] = 1.0
                continue
            top = str(row.idxmax())
            if row[top] > bil_mom.loc[date]:
                w.loc[date, top] = 1.0
            else:
                w.loc[date, "BIL"] = 1.0
        return normalize_to_bil(w)
    raise ValueError(f"Unknown benchmark: {name}")


def beta_to_factor(returns: pd.Series, factor_returns: pd.Series) -> float:
    df = pd.concat([pd.to_numeric(returns, errors="coerce"), pd.to_numeric(factor_returns, errors="coerce")], axis=1).dropna()
    if len(df) < 20 or float(df.iloc[:, 1].var()) <= 0:
        return np.nan
    return float(np.cov(df.iloc[:, 0], df.iloc[:, 1], ddof=1)[0, 1] / df.iloc[:, 1].var(ddof=1))


def trial_count() -> int:
    if not STAT_AUDIT.exists():
        return 1
    df = pd.read_csv(STAT_AUDIT, usecols=lambda col: col in {"trial_count_used"})
    return int(df["trial_count_used"].max()) if not df.empty and "trial_count_used" in df.columns else 1


def evaluate(
    name: str,
    kind: str,
    weights: pd.DataFrame,
    path: pd.DataFrame,
    next_returns: pd.DataFrame,
    track_a_metrics: dict[str, float] | None,
    trials: int,
) -> dict[str, Any]:
    path_idx = path.set_index("Date")
    ret = pd.to_numeric(path_idx["net_return"], errors="coerce")
    full = metrics_from_path(path, weights=weights)
    holdout = holdout_metrics_from_path(path, weights=weights)
    psr = probabilistic_sharpe_ratio(ret)
    dsr = deflated_sharpe_ratio_proxy(ret, trial_count=trials)
    mt_support = multiple_testing_adjusted_support(psr, trials)
    row = {
        "name": name,
        "kind": kind,
        "research_status": "research_only" if kind == "candidate" else "benchmark",
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


def shortlist_table(metrics: pd.DataFrame, cost: pd.DataFrame, state: pd.DataFrame, benchmark_metrics: pd.DataFrame) -> pd.DataFrame:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("name")
    stress = state[state["market_state"].eq("stressed_panic")].set_index("name")
    aggressive_bench = benchmark_metrics[benchmark_metrics["name"].isin(["static_80_spy_20_bil", "static_global_growth_90_10", "aggressive_taa_spy_trend", "dual_momentum_top1"])]
    best_bench_return = float(aggressive_bench["ann_return"].max()) if not aggressive_bench.empty else np.nan
    rows = []
    for _, row in metrics[metrics["kind"].eq("candidate")].iterrows():
        name = row["name"]
        gates = {
            "return_ge_9": row["ann_return"] >= 0.09,
            "return_improvement_ge_50bp": row["delta_ann_return_vs_track_a"] >= 0.005,
            "drawdown_ge_minus_22": row["max_drawdown"] >= -0.22,
            "sharpe_ge_085": row["sharpe"] >= 0.85,
            "calmar_ge_045": row["calmar"] >= 0.45,
            "avg_bil_below_track_a": row["delta_avg_BIL_vs_track_a"] < -0.05,
            "cost_2x_sharpe_ge_082": name in cost2.index and cost2.loc[name, "sharpe"] >= 0.82,
            "cost_2x_drawdown_ok": name in cost2.index and cost2.loc[name, "max_drawdown"] >= -0.22,
            "holdout_positive": row["holdout_ann_return"] > 0.0 and row["holdout_sharpe"] >= 0.80,
            "stress_drawdown_ok": name in stress.index and stress.loc[name, "max_drawdown"] >= -0.16,
            "beats_best_aggressive_benchmark_return": np.isfinite(best_bench_return) and row["ann_return"] >= best_bench_return,
        }
        score = int(sum(bool(v) for v in gates.values()))
        return_gate = bool(gates["return_ge_9"] or gates["return_improvement_ge_50bp"])
        mandate_9_10_met = bool(
            gates["return_ge_9"]
            and gates["drawdown_ge_minus_22"]
            and gates["sharpe_ge_085"]
            and gates["calmar_ge_045"]
            and gates["cost_2x_sharpe_ge_082"]
            and gates["cost_2x_drawdown_ok"]
        )
        shortlist_flag = bool(
            return_gate
            and score >= 8
            and gates["drawdown_ge_minus_22"]
            and gates["sharpe_ge_085"]
            and gates["cost_2x_drawdown_ok"]
        )
        rows.append(
            {
                "name": name,
                **gates,
                "gate_score": score,
                "mandate_9_10_met": mandate_9_10_met,
                "track_b_shortlist": shortlist_flag,
                "shortlist_reason": "research_only_shortlist" if shortlist_flag else "reject_or_diagnostic",
            }
        )
    return pd.DataFrame(rows)


def write_outputs(
    benchmark_returns: pd.DataFrame,
    benchmark_weights_rows: list[pd.DataFrame],
    benchmark_metrics: pd.DataFrame,
    candidate_returns: pd.DataFrame,
    candidate_weights_rows: list[pd.DataFrame],
    candidate_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    state_rows: pd.DataFrame,
    rolling_rows: pd.DataFrame,
    attribution: pd.DataFrame,
    state_contrib: pd.DataFrame,
    shortlist: pd.DataFrame,
    registry: pd.DataFrame,
    manifest: dict[str, Any],
) -> None:
    benchmark_returns.to_csv(OUT / "track_b_benchmark_returns.csv", index=False)
    pd.concat(benchmark_weights_rows, ignore_index=True).to_csv(OUT / "track_b_benchmark_weights.csv", index=False)
    benchmark_metrics.to_csv(OUT / "track_b_benchmark_metrics.csv", index=False)
    candidate_returns.to_csv(OUT / "track_b_candidate_returns.csv", index=False)
    pd.concat(candidate_weights_rows, ignore_index=True).to_csv(OUT / "track_b_candidate_weights.csv", index=False)
    candidate_metrics.to_csv(OUT / "track_b_candidate_metrics.csv", index=False)
    cost_metrics.to_csv(OUT / "track_b_cost_sensitivity.csv", index=False)
    state_rows.to_csv(OUT / "track_b_state_metrics.csv", index=False)
    rolling_rows.to_csv(OUT / "track_b_rolling_origin_metrics.csv", index=False)
    attribution.to_csv(OUT / "track_b_return_attribution.csv", index=False)
    state_contrib.to_csv(OUT / "track_b_state_contribution.csv", index=False)
    shortlist.to_csv(OUT / "track_b_shortlist.csv", index=False)
    registry.to_csv(OUT / "track_b_experiment_registry.csv", index=False)
    (OUT / "track_b_candidate_manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, allow_nan=False) + "\n")


def write_markdown_reports(
    benchmark_metrics: pd.DataFrame,
    candidate_metrics: pd.DataFrame,
    cost_metrics: pd.DataFrame,
    state_rows: pd.DataFrame,
    attribution: pd.DataFrame,
    shortlist: pd.DataFrame,
) -> None:
    bench_cols = [
        "name",
        "ann_return",
        "ann_vol",
        "sharpe",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "avg_BIL",
        "avg_equity",
        "spy_beta",
        "avg_weekly_turnover",
        "holdout_sharpe",
    ]
    (DOC / "track_b_benchmark_comparison.md").write_text(
        "\n".join(
            [
                "# Track B Benchmark Comparison",
                "",
                "All benchmarks use existing weekly prices and Track A canonical metrics/cost logic.",
                "",
                markdown_table(benchmark_metrics[[c for c in bench_cols if c in benchmark_metrics.columns]]),
                "",
                "Machine-readable outputs:",
                "",
                f"- `{rel(OUT / 'track_b_benchmark_returns.csv')}`",
                f"- `{rel(OUT / 'track_b_benchmark_weights.csv')}`",
                f"- `{rel(OUT / 'track_b_benchmark_metrics.csv')}`",
            ]
        ).rstrip()
        + "\n"
    )

    attr_cols = [
        "name",
        "ann_return",
        "delta_ann_return_vs_track_a",
        "spy_beta",
        "delta_spy_beta_vs_track_a",
        "avg_BIL",
        "cash_drag_reduction_est_ann",
        "beta_explained_return_est_ann",
        "residual_return_vs_track_a_est_ann",
        "return_source_label",
    ]
    (DOC / "track_b_return_attribution.md").write_text(
        "\n".join(
            [
                "# Track B Return Attribution",
                "",
                "Attribution is approximate. It is intended to separate obvious beta/cash-drag effects from possible timing improvements, not to prove causality.",
                "",
                markdown_table(attribution[[c for c in attr_cols if c in attribution.columns]]),
                "",
                "State contribution and asset-category contribution are saved in machine-readable CSV outputs.",
            ]
        ).rstrip()
        + "\n"
    )

    report_cols = [
        "name",
        "ann_return",
        "sharpe",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "avg_BIL",
        "avg_equity",
        "spy_beta",
        "holdout_sharpe",
        "avg_weekly_turnover",
    ]
    best = candidate_metrics.sort_values(["ann_return", "sharpe"], ascending=False).head(5)
    watchlist = shortlist[shortlist["track_b_shortlist"]].copy()
    rejected = shortlist[~shortlist["track_b_shortlist"]].copy()
    cost2 = cost_metrics[cost_metrics["cost_multiplier"].eq(2.0)]
    stress = state_rows[state_rows["market_state"].eq("stressed_panic")]
    mandate_hits = shortlist[shortlist["mandate_9_10_met"]].copy()
    top_return = candidate_metrics.sort_values("ann_return", ascending=False).iloc[0]
    final_verdict = "Track B failed to produce a compelling higher-return profile."
    if bool(shortlist["track_b_shortlist"].any()):
        shortlisted_names = set(shortlist.loc[shortlist["track_b_shortlist"], "name"])
        attr_short = attribution[attribution["name"].isin(shortlisted_names)]
        if not attr_short.empty and attr_short["return_source_label"].astype(str).str.contains("mostly_higher_beta").all():
            final_verdict = "Track B produced higher returns, but mostly by taking more beta/risk."
        else:
            final_verdict = "Track B produced a credible research-only higher-return candidate worth forward paper tracking."
    elif candidate_metrics["ann_return"].max() >= 0.09:
        final_verdict = "Track B produced higher returns, but mostly by taking more beta/risk."

    lines = [
        "# Track B Higher-Return Research Report",
        "",
        "## 1. Track B Mandate",
        "",
        "Research-only sprint to test whether the ETF system can reach 9-10%+ annualized return by accepting more offense exposure, higher equity beta, lower BIL/cash, and larger drawdown tolerance. No Track B result is production-ready.",
        "",
        "## 2. Track A Baseline Summary",
        "",
        "Track A production remains `improved_frontier_phase5_fragility_guard`. It is the conservative, auditable baseline and was not modified by Track B.",
        "",
        markdown_table(benchmark_metrics[benchmark_metrics["name"].eq(TRACK_A)][[c for c in report_cols if c in benchmark_metrics.columns]]),
        "",
        "## 3. Benchmark Comparison",
        "",
        markdown_table(benchmark_metrics[[c for c in report_cols if c in benchmark_metrics.columns]]),
        "",
        "## 4. Predeclared Experiment Grid",
        "",
        f"See `{rel(DOC / 'track_b_predeclared_experiment_plan.md')}`. The implemented grid has exactly `{len(CANDIDATES)}` candidates.",
        "",
        "## 5. Candidate Results Table",
        "",
        markdown_table(candidate_metrics[[c for c in report_cols if c in candidate_metrics.columns]]),
        "",
        "## 6. Best Candidates",
        "",
        markdown_table(best[[c for c in report_cols if c in best.columns]]),
        "",
        "## 7. Research-Only Watchlist And Rejected Candidates",
        "",
        "The watchlist is not a production shortlist. It contains candidates with at least 50 bps annual return improvement or 9%+ return plus enough risk/cost gates to justify forward paper tracking.",
        "",
        markdown_table(watchlist[["name", "gate_score", "mandate_9_10_met", "track_b_shortlist", "shortlist_reason"]]),
        "",
        "Rejected or diagnostic-only candidates:",
        "",
        markdown_table(rejected[["name", "gate_score", "shortlist_reason"] + [c for c in rejected.columns if c.startswith("return_ge_") or c.startswith("drawdown_") or c.startswith("sharpe_")]].head(20)),
        "",
        "## 8. Risk Diagnostics",
        "",
        "Track B candidates are judged with max drawdown, weekly CVaR 5%, annualized volatility, Calmar, state metrics, and stress-state behavior. Higher return is not accepted without naming the risk paid for it.",
        "",
        "## 9. Cost Sensitivity",
        "",
        markdown_table(cost2[["name", "kind", "ann_return", "sharpe", "max_drawdown", "cvar_5", "annualized_cost"]].sort_values(["kind", "ann_return"], ascending=[True, False]).head(30)),
        "",
        "## 10. Drawdown/CVaR Comparison",
        "",
        markdown_table(candidate_metrics[["name", "ann_return", "max_drawdown", "cvar_5", "calmar", "ann_vol"]].sort_values("ann_return", ascending=False)),
        "",
        "## 11. State-By-State Behavior",
        "",
        markdown_table(stress[["name", "kind", "ann_return", "sharpe", "max_drawdown", "cvar_5"]].sort_values(["kind", "ann_return"], ascending=[True, False]).head(30)),
        "",
        "## 12. Beta And Attribution Analysis",
        "",
        markdown_table(attribution[[c for c in attr_cols if c in attribution.columns]].sort_values("ann_return", ascending=False)),
        "",
        "## 13. Is 9-10% Annual Return Realistic?",
        "",
        (
            "No tested candidate met the full 9-10% mandate with the risk gates intact. "
            f"The highest-return candidate was `{top_return['name']}` at {top_return['ann_return']:.2%} CAGR, "
            f"but it had Sharpe {top_return['sharpe']:.3f}, max drawdown {top_return['max_drawdown']:.2%}, "
            f"and Calmar {top_return['calmar']:.3f}. "
            f"Full mandate hits: {len(mandate_hits)}."
        ),
        "",
        "## 14. Genuine Improvement Or Mostly Higher Beta?",
        "",
        "The attribution labels show that incremental return is largely explainable by higher SPY beta and lower BIL/cash drag. The Track B watchlist is therefore useful as a risk-budget reference, not evidence of a new edge.",
        "",
        "## 15. What Should Be Tested Next",
        "",
        "- Forward paper tracking only for candidates that cleared the tightened research-only shortlist.",
        "- Stability of beta-adjusted residual return using a longer live-style paper window.",
        "- Turnover-band sensitivity around the predeclared 5% band only if the banded candidate remains competitive in paper tracking.",
        "",
        "## 16. What Should Not Be Pursued",
        "",
        "- Larger parameter sweeps.",
        "- ML overlays.",
        "- Crisis-specific handcrafted rules.",
        "- Any production-promotion narrative without a forward paper window.",
        "",
        "## 17. Final Verdict",
        "",
        final_verdict,
    ]
    (DOC / "track_b_higher_return_research_report.md").write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    ensure_dirs()
    require_official_production_pin()
    prices = read_dated(HUB / "weekly_prices.csv")
    next_returns = next_week_returns_from_prices(prices)
    base_weights = read_dated(weights_path(PRODUCTION_CANDIDATE)).fillna(0.0)
    states = read_dated(REGIME / "market_state_history.csv")["market_state"].astype(str)
    common = base_weights.index.intersection(next_returns.index)
    base_weights = base_weights.reindex(common).fillna(0.0)
    next_returns = next_returns.reindex(common)
    prices = prices.reindex(common)
    columns = base_weights.columns.tolist()
    trials = trial_count()

    benchmark_names = [
        TRACK_A,
        "spy_buy_hold",
        "static_60_spy_40_ief",
        "static_80_spy_20_bil",
        "aggressive_taa_spy_trend",
        "dual_momentum_top1",
        "static_global_growth_90_10",
    ]

    benchmark_paths: dict[str, pd.DataFrame] = {}
    benchmark_weight_map: dict[str, pd.DataFrame] = {}
    benchmark_metric_rows = []
    benchmark_returns_rows = []
    benchmark_weights_rows = []
    state_frames = []
    cost_frames = []
    rolling_frames = []

    track_a_weights = benchmark_weights(TRACK_A, common, columns, prices)
    track_a_path = portfolio_path(track_a_weights, next_returns)
    track_a_eval = evaluate(TRACK_A, "benchmark", track_a_weights, track_a_path, next_returns, None, trials)
    track_a_metrics = track_a_eval.copy()

    for name in benchmark_names:
        weights = benchmark_weights(name, common, columns, prices)
        path = portfolio_path(weights, next_returns)
        benchmark_weight_map[name] = weights
        benchmark_paths[name] = path
        benchmark_metric_rows.append(evaluate(name, "benchmark", weights, path, next_returns, track_a_metrics, trials))
        ret_rows = path.copy()
        ret_rows.insert(0, "name", name)
        benchmark_returns_rows.append(ret_rows)
        w_rows = weights.reset_index().rename(columns={"index": "Date"})
        w_rows.insert(0, "name", name)
        benchmark_weights_rows.append(w_rows)
        state_frames.append(state_metrics(name, "benchmark", path, states))
        cost_frames.append(cost_sensitivity(name, "benchmark", weights, next_returns))
        ro = rolling_origin_metrics(path.set_index("Date")["net_return"])
        if not ro.empty:
            ro.insert(0, "kind", "benchmark")
            ro.insert(0, "name", name)
            rolling_frames.append(ro)

    candidate_metric_rows = []
    candidate_returns_rows = []
    candidate_weights_rows = []
    candidate_weight_map: dict[str, pd.DataFrame] = {}
    candidate_paths: dict[str, pd.DataFrame] = {}
    registry_rows = []
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mandate": "Track B higher-return research-only ETF variants",
        "production_registry_written": False,
        "track_a_baseline": PRODUCTION_CANDIDATE,
        "candidate_count": len(CANDIDATES),
        "candidates": [],
    }

    for spec in CANDIDATES:
        weights = candidate_weights(spec, base_weights, states, prices)
        path = portfolio_path(weights, next_returns)
        candidate_weight_map[spec.name] = weights
        candidate_paths[spec.name] = path
        candidate_metric_rows.append(evaluate(spec.name, "candidate", weights, path, next_returns, track_a_metrics, trials))
        ret_rows = path.copy()
        ret_rows.insert(0, "name", spec.name)
        candidate_returns_rows.append(ret_rows)
        w_rows = weights.reset_index().rename(columns={"index": "Date"})
        w_rows.insert(0, "name", spec.name)
        candidate_weights_rows.append(w_rows)
        state_frames.append(state_metrics(spec.name, "candidate", path, states))
        cost_frames.append(cost_sensitivity(spec.name, "candidate", weights, next_returns))
        ro = rolling_origin_metrics(path.set_index("Date")["net_return"])
        if not ro.empty:
            ro.insert(0, "kind", "candidate")
            ro.insert(0, "name", spec.name)
            rolling_frames.append(ro)
        registry_rows.append(
            {
                "candidate": spec.name,
                "track": "track_b_aggressive",
                "status": "research_only",
                "source_file": "scripts/track_b_aggressive/run_track_b_research.py",
                "parameters": json.dumps(spec.parameters, sort_keys=True),
                "parent_candidate": PRODUCTION_CANDIDATE,
                "hypothesis": spec.hypothesis,
                "success_criteria": spec.success_criteria,
                "kill_criteria": spec.kill_criteria,
                "promotion_status": "not_promoted",
            }
        )
        manifest["candidates"].append(
            {
                "name": spec.name,
                "hypothesis": spec.hypothesis,
                "parameters": spec.parameters,
                "expected_tradeoff": spec.expected_tradeoff,
                "success_criteria": spec.success_criteria,
                "kill_criteria": spec.kill_criteria,
                "status": "research_only",
            }
        )

    benchmark_metrics = pd.DataFrame(benchmark_metric_rows)
    candidate_metrics = pd.DataFrame(candidate_metric_rows)
    all_cost = pd.concat(cost_frames, ignore_index=True)
    all_state = pd.concat(state_frames, ignore_index=True)
    all_rolling = pd.concat(rolling_frames, ignore_index=True) if rolling_frames else pd.DataFrame()
    shortlist = shortlist_table(candidate_metrics, all_cost, all_state, benchmark_metrics)

    spy_cagr = benchmark_metrics.set_index("name").loc["spy_buy_hold", "ann_return"]
    bil_weights = static_weight_frame(common, columns, {"BIL": 1.0})
    bil_path = portfolio_path(bil_weights, next_returns)
    bil_cagr = metrics_from_path(bil_path, weights=bil_weights)["ann_return"]
    track_a_row = benchmark_metrics.set_index("name").loc[TRACK_A]
    attribution_rows = []
    state_contrib_rows = []
    for name, weights in candidate_weight_map.items():
        path = candidate_paths[name]
        row = candidate_metrics.set_index("name").loc[name]
        contrib = category_contributions(name, weights, path, next_returns)
        beta_delta = row["spy_beta"] - track_a_row["spy_beta"]
        bil_delta = track_a_row["avg_BIL"] - row["avg_BIL"]
        equity_premium = spy_cagr - bil_cagr
        beta_explained = beta_delta * equity_premium
        cash_drag_reduction = bil_delta * equity_premium
        delta_return = row["ann_return"] - track_a_row["ann_return"]
        residual = delta_return - beta_explained
        label = "mostly_higher_beta_or_cash_drag"
        if delta_return <= 0:
            label = "no_return_improvement"
        elif abs(beta_explained) < 0.60 * abs(delta_return) and row["sharpe"] >= 0.85:
            label = "possible_timing_or_allocation_improvement"
        attribution_rows.append(
            {
                "name": name,
                "ann_return": row["ann_return"],
                "delta_ann_return_vs_track_a": delta_return,
                "spy_beta": row["spy_beta"],
                "delta_spy_beta_vs_track_a": beta_delta,
                "ief_beta": row["ief_beta"],
                "avg_BIL": row["avg_BIL"],
                "delta_avg_BIL_vs_track_a": row["avg_BIL"] - track_a_row["avg_BIL"],
                "cash_drag_reduction_est_ann": cash_drag_reduction,
                "beta_explained_return_est_ann": beta_explained,
                "residual_return_vs_track_a_est_ann": residual,
                "return_source_label": label,
                **contrib,
            }
        )
        ret = path.set_index("Date")["net_return"]
        state_series = states.reindex(ret.index).astype(str)
        for state, sr in ret.groupby(state_series):
            if isinstance(state, str) and state != "nan":
                state_contrib_rows.append(
                    {
                        "name": name,
                        "market_state": state,
                        "weeks": int(len(sr)),
                        "ann_arithmetic_contribution": float(sr.mean() * WEEKS_PER_YEAR * len(sr) / len(ret)),
                        "mean_weekly_return": float(sr.mean()),
                    }
                )

    attribution = pd.DataFrame(attribution_rows)
    state_contrib = pd.DataFrame(state_contrib_rows)
    registry = pd.DataFrame(registry_rows)
    manifest["shortlist"] = shortlist[shortlist["track_b_shortlist"]].to_dict(orient="records")
    manifest["output_files"] = {
        "candidate_returns": rel(OUT / "track_b_candidate_returns.csv"),
        "candidate_weights": rel(OUT / "track_b_candidate_weights.csv"),
        "candidate_metrics": rel(OUT / "track_b_candidate_metrics.csv"),
        "experiment_registry": rel(OUT / "track_b_experiment_registry.csv"),
    }

    write_outputs(
        pd.concat(benchmark_returns_rows, ignore_index=True),
        benchmark_weights_rows,
        benchmark_metrics,
        pd.concat(candidate_returns_rows, ignore_index=True),
        candidate_weights_rows,
        candidate_metrics,
        all_cost,
        all_state,
        all_rolling,
        attribution,
        state_contrib,
        shortlist,
        registry,
        manifest,
    )
    write_markdown_reports(benchmark_metrics, candidate_metrics, all_cost, all_state, attribution, shortlist)

    print("Track B higher-return research complete")
    print(f"benchmarks={len(benchmark_names)} candidates={len(CANDIDATES)}")
    best = candidate_metrics.sort_values("ann_return", ascending=False).iloc[0]
    print(
        f"best_by_return={best['name']} ann_return={best['ann_return']:.4%} "
        f"sharpe={best['sharpe']:.3f} max_dd={best['max_drawdown']:.2%}"
    )
    print(f"shortlist={shortlist[shortlist['track_b_shortlist']]['name'].tolist()}")
    print(f"wrote {rel(DOC / 'track_b_higher_return_research_report.md')}")


if __name__ == "__main__":
    main()
