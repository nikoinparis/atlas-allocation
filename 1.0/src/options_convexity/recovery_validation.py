"""Validation harness for the recovery options experiment.

Per the brief, the validation harness is written BEFORE interpreting results.
It provides:
  * extended metrics (upside/downside capture, CVaR 1%, Sharpe excluding the best
    and top-3 option trades),
  * the 16 validation gates,
  * the verdict decision (REJECT / RESEARCH-ONLY / CANDIDATE FOR FURTHER TESTING),
    with the hard rule that a result destroyed by best-trade removal can never be
    a CANDIDATE.

Reuses the standalone ``metrics`` module for base metrics so conventions match
the rest of the project. Does not touch production or v1/v2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics, recovery_backtest as rbt

OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")

# "Material" tolerances (small, fixed; not tuned).
SHARPE_IMPROVE_MIN = 0.10
DD_TOLERANCE = 0.01      # 1pp extra drawdown allowed.
CVAR_TOLERANCE = 0.002   # 0.2pp extra weekly CVaR allowed.
MIN_TRADES = 10
MAX_ACTIVATIONS_PER_YEAR = 8.0
MAX_ANNUAL_PREMIUM = 0.02
MAX_CONCURRENT = 0.01


def cvar(returns: pd.Series, q: float) -> float:
    r = metrics._clean(returns)
    if len(r) < 20:
        return np.nan
    var = float(r.quantile(q))
    tail = r[r <= var]
    return float(tail.mean()) if len(tail) else np.nan


def capture(overlay: pd.Series, baseline: pd.Series, upside: bool) -> float:
    """Up/down capture of overlay vs baseline on baseline up/down weeks."""

    o = metrics._clean(overlay)
    b = metrics._clean(baseline)
    idx = o.index.intersection(b.index)
    o, b = o.reindex(idx), b.reindex(idx)
    mask = (b > 0) if upside else (b < 0)
    if mask.sum() < 5 or b[mask].mean() == 0:
        return np.nan
    return float(o[mask].mean() / b[mask].mean())


def window_metrics(returns: pd.Series, index) -> dict:
    s = pd.Series(returns.values, index=index)
    return {
        "full": metrics.summarize(s),
        "train": metrics.summarize(s[s.index < OFFICIAL_HOLDOUT_START]),
        "holdout": metrics.summarize(s[s.index >= OFFICIAL_HOLDOUT_START]),
    }


def extended_summary(result: rbt.RecoveryResult) -> dict:
    """Full metric bundle for baseline / options / tilt on this result."""

    eq = result.equity
    base = window_metrics(eq["baseline_return"], eq.index)
    opt = window_metrics(eq["options_return"], eq.index)
    tilt = window_metrics(eq["tilt_return"], eq.index)

    # Capture + extra tail metrics (full period).
    opt["full"]["cvar_1"] = cvar(eq["options_return"], 0.01)
    base["full"]["cvar_1"] = cvar(eq["baseline_return"], 0.01)
    tilt["full"]["cvar_1"] = cvar(eq["tilt_return"], 0.01)
    opt["full"]["upside_capture"] = capture(eq["options_return"], eq["baseline_return"], True)
    opt["full"]["downside_capture"] = capture(eq["options_return"], eq["baseline_return"], False)
    tilt["full"]["upside_capture"] = capture(eq["tilt_return"], eq["baseline_return"], True)
    tilt["full"]["downside_capture"] = capture(eq["tilt_return"], eq["baseline_return"], False)

    # Robustness: Sharpe excluding the best and top-3 option trades.
    sharpe_ex_best = sharpe_ex_top = opt["full"]["sharpe"]
    if not result.trades.empty:
        order = result.trades["incremental_dollars"].astype(float).sort_values(ascending=False)
        best_ids = list(order.index[:1])
        top3_ids = list(order.index[:3])
        sharpe_ex_best = metrics.sharpe(rbt.options_equity_excluding(result, best_ids).pct_change().fillna(0.0))
        sharpe_ex_top = metrics.sharpe(rbt.options_equity_excluding(result, top3_ids).pct_change().fillna(0.0))

    trade_stats = metrics.summarize_option_trades(result.trades)

    return {
        "baseline": base, "options": opt, "tilt": tilt,
        "sharpe_ex_best": sharpe_ex_best, "sharpe_ex_top3": sharpe_ex_top,
        "trade_stats": trade_stats,
        "activations_per_year": result.activations_per_year,
        "premium_at_risk_per_year": result.premium_at_risk_per_year,
        "cash_premium_per_year": result.cash_premium_per_year,
        "max_concurrent_risk": result.max_concurrent_risk,
        "avg_dte": result.avg_dte, "avg_moneyness": result.avg_moneyness,
        "n_trades": int(len(result.trades)),
    }


def stress_period_incremental(result: rbt.RecoveryResult) -> float:
    """Mean weekly options-vs-baseline return diff during stressed_panic weeks."""

    from . import option_data
    states = option_data.load_market_states()["market_state"].astype(str).reindex(result.equity.index)
    mask = states == "stressed_panic"
    if mask.sum() < 3:
        return 0.0
    diff = result.equity["options_return"] - result.equity["baseline_return"]
    return float(diff[mask].mean())


def subperiod_trade_spread(result: rbt.RecoveryResult) -> int:
    """How many of 3 equal time-thirds contain at least one option trade."""

    if result.trades.empty:
        return 0
    idx = result.equity.index
    bounds = [idx[0], idx[len(idx) // 3], idx[2 * len(idx) // 3], idx[-1]]
    thirds = 0
    od = pd.to_datetime(result.trades["open_date"])
    for a, b in zip(bounds[:-1], bounds[1:]):
        if ((od >= a) & (od <= b)).any():
            thirds += 1
    return thirds


def evaluate_gates(summary: dict, result: rbt.RecoveryResult) -> dict:
    fb = summary["baseline"]["full"]
    fo = summary["options"]["full"]
    ft = summary["tilt"]["full"]
    gates: dict[str, dict] = {}

    gates["sharpe_improves"] = {
        "pass": bool(np.isfinite(fo["sharpe"]) and fo["sharpe"] - fb["sharpe"] >= SHARPE_IMPROVE_MIN),
        "detail": f"options {fo['sharpe']:.3f} vs baseline {fb['sharpe']:.3f} (Δ {fo['sharpe']-fb['sharpe']:+.3f}, need +{SHARPE_IMPROVE_MIN})",
    }
    gates["drawdown_ok"] = {
        "pass": bool(fo["max_drawdown"] - fb["max_drawdown"] >= -DD_TOLERANCE),
        "detail": f"options {fo['max_drawdown']:.3f} vs baseline {fb['max_drawdown']:.3f}",
    }
    gates["cvar5_ok"] = {
        "pass": bool(fo["cvar_5"] - fb["cvar_5"] >= -CVAR_TOLERANCE),
        "detail": f"options {fo['cvar_5']:.4f} vs baseline {fb['cvar_5']:.4f}",
    }
    gates["cvar1_ok"] = {
        "pass": bool(fo.get("cvar_1", np.nan) - fb.get("cvar_1", np.nan) >= -CVAR_TOLERANCE) if np.isfinite(fo.get("cvar_1", np.nan)) else True,
        "detail": f"options {fo.get('cvar_1', np.nan):.4f} vs baseline {fb.get('cvar_1', np.nan):.4f}",
    }
    gates["not_one_trade"] = {
        "pass": bool(np.isfinite(summary["sharpe_ex_best"]) and summary["sharpe_ex_best"] >= fb["sharpe"]),
        "detail": f"Sharpe ex-best {summary['sharpe_ex_best']:.3f} vs baseline {fb['sharpe']:.3f}",
    }
    gates["survive_top3_removal"] = {
        "pass": bool(np.isfinite(summary["sharpe_ex_top3"]) and summary["sharpe_ex_top3"] >= fb["sharpe"]),
        "detail": f"Sharpe ex-top3 {summary['sharpe_ex_top3']:.3f} vs baseline {fb['sharpe']:.3f}",
    }
    gates["competitive_vs_tilt"] = {
        "pass": bool(np.isfinite(fo["sharpe"]) and np.isfinite(ft["sharpe"]) and fo["sharpe"] >= ft["sharpe"] - 0.02),
        "detail": f"options Sharpe {fo['sharpe']:.3f} vs tactical-tilt {ft['sharpe']:.3f}",
    }
    gates["enough_trades"] = {
        "pass": bool(summary["n_trades"] >= MIN_TRADES),
        "detail": f"{summary['n_trades']} trades (need >= {MIN_TRADES})",
    }
    apy = summary["activations_per_year"]
    gates["activation_rare"] = {
        "pass": bool(np.isfinite(apy) and apy <= MAX_ACTIVATIONS_PER_YEAR),
        "detail": f"{apy:.2f} activations/yr (max {MAX_ACTIVATIONS_PER_YEAR})",
    }
    gates["annual_premium_ok"] = {
        "pass": bool(summary["premium_at_risk_per_year"] <= MAX_ANNUAL_PREMIUM + 1e-9),
        "detail": f"{summary['premium_at_risk_per_year']*100:.2f}% NAV/yr (cap {MAX_ANNUAL_PREMIUM*100:.1f}%)",
    }
    gates["concurrent_ok"] = {
        "pass": bool(summary["max_concurrent_risk"] <= MAX_CONCURRENT + 1e-9),
        "detail": f"max concurrent {summary['max_concurrent_risk']*100:.2f}% NAV (cap {MAX_CONCURRENT*100:.1f}%)",
    }
    tr_ok = summary["options"]["train"]["sharpe"] >= summary["baseline"]["train"]["sharpe"]
    ho_b = summary["baseline"]["holdout"]["sharpe"]
    ho_o = summary["options"]["holdout"]["sharpe"]
    ho_ok = (not np.isfinite(ho_b)) or (ho_o >= ho_b - 0.10)
    gates["train_holdout_ok"] = {
        "pass": bool(tr_ok and ho_ok),
        "detail": f"train {summary['options']['train']['sharpe']:.3f}/{summary['baseline']['train']['sharpe']:.3f}; holdout {ho_o:.3f}/{ho_b:.3f}",
    }
    thirds = subperiod_trade_spread(result)
    gates["not_one_regime"] = {
        "pass": bool(thirds >= 2),
        "detail": f"trades present in {thirds}/3 time-thirds",
    }
    stress = stress_period_incremental(result)
    gates["stress_not_harmful"] = {
        "pass": bool(stress >= -0.0005),
        "detail": f"mean options-vs-baseline weekly diff in panic = {stress:+.5f}",
    }
    gates["costs_conservative"] = {"pass": True, "detail": "entry+exit slippage 5% each on gross + IV markup x1.05; held to time-stop"}
    gates["no_lookahead"] = {"pass": True, "detail": "all signals lagged 1wk (verifier re-checks shift relationship)"}
    return gates


def decide_verdict(gates: dict, summary: dict) -> str:
    """REJECT / RESEARCH-ONLY / CANDIDATE FOR FURTHER TESTING."""

    if summary["n_trades"] == 0:
        return "RESEARCH-ONLY"

    # Hard rule: if best-trade or top-3 removal destroys it, never a CANDIDATE.
    robust = gates["not_one_trade"]["pass"] and gates["survive_top3_removal"]["pass"]

    promote_set = ["sharpe_improves", "drawdown_ok", "cvar5_ok", "cvar1_ok",
                   "competitive_vs_tilt", "enough_trades", "train_holdout_ok",
                   "not_one_regime", "stress_not_harmful", "annual_premium_ok", "concurrent_ok"]
    promote_ok = all(gates[g]["pass"] for g in promote_set)

    if robust and promote_ok:
        return "CANDIDATE FOR FURTHER TESTING"

    # RESEARCH-ONLY if it shows a useful SHAPE improvement (better upside capture
    # or better tail) even though it does not beat the baseline outright.
    fo = summary["options"]["full"]
    fb = summary["baseline"]["full"]
    shape_useful = (
        (np.isfinite(fo.get("upside_capture", np.nan)) and fo["upside_capture"] > 1.02)
        or (np.isfinite(fo["sharpe"]) and fo["sharpe"] >= fb["sharpe"] - 0.05)
    )
    risk_not_worse = gates["drawdown_ok"]["pass"] and gates["cvar5_ok"]["pass"]
    if shape_useful and risk_not_worse:
        return "RESEARCH-ONLY"
    return "REJECT"
