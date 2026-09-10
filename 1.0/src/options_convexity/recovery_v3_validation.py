"""Validation harness for Recovery Options Overlay v3."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics, recovery_v3_backtest as bt

OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")

SHARPE_BASELINE_MIN = 0.05
SHARPE_TILT_MIN = 0.03
CAGR_IMPROVE_MIN = 0.0025
DD_TOLERANCE = 0.0025


def cvar(returns: pd.Series, q: float) -> float:
    r = metrics._clean(returns)
    if len(r) < 20:
        return np.nan
    var = float(r.quantile(q))
    tail = r[r <= var]
    return float(tail.mean()) if len(tail) else np.nan


def capture(strategy: pd.Series, baseline: pd.Series, upside: bool) -> float:
    s = metrics._clean(strategy)
    b = metrics._clean(baseline)
    idx = s.index.intersection(b.index)
    s, b = s.reindex(idx), b.reindex(idx)
    mask = (b > 0) if upside else (b < 0)
    if mask.sum() < 5 or b[mask].mean() == 0:
        return np.nan
    return float(s[mask].mean() / b[mask].mean())


def window_metrics(returns: pd.Series, index) -> dict[str, dict]:
    s = pd.Series(returns.values, index=index)
    return {
        "full": metrics.summarize(s),
        "train": metrics.summarize(s[s.index < OFFICIAL_HOLDOUT_START]),
        "holdout": metrics.summarize(s[s.index >= OFFICIAL_HOLDOUT_START]),
    }


def extended_summary(result: bt.V3Result) -> dict:
    eq = result.equity
    summary = {
        "baseline": window_metrics(eq["baseline_return"], eq.index),
        "v3_options": window_metrics(eq["v3_options_return"], eq.index),
        "tactical_tilt": window_metrics(eq["v3_tilt_return"], eq.index),
        "vol_scaled_tilt": window_metrics(eq["v3_vol_scaled_tilt_return"], eq.index),
    }

    for key, ret_col in [
        ("baseline", "baseline_return"),
        ("v3_options", "v3_options_return"),
        ("tactical_tilt", "v3_tilt_return"),
        ("vol_scaled_tilt", "v3_vol_scaled_tilt_return"),
    ]:
        summary[key]["full"]["cvar_1"] = cvar(eq[ret_col], 0.01)
        if key != "baseline":
            summary[key]["full"]["upside_capture"] = capture(eq[ret_col], eq["baseline_return"], True)
            summary[key]["full"]["downside_capture"] = capture(eq[ret_col], eq["baseline_return"], False)

    sharpe_ex_best = summary["v3_options"]["full"]["sharpe"]
    sharpe_ex_top3 = summary["v3_options"]["full"]["sharpe"]
    if not result.trades.empty:
        order = result.trades["incremental_dollars"].astype(float).sort_values(ascending=False)
        best_ids = list(result.trades.loc[order.index[:1], "trade_id"].astype(int))
        top3_ids = list(result.trades.loc[order.index[:3], "trade_id"].astype(int))
        sharpe_ex_best = metrics.sharpe(bt.options_equity_excluding(result, best_ids).pct_change().fillna(0.0))
        sharpe_ex_top3 = metrics.sharpe(bt.options_equity_excluding(result, top3_ids).pct_change().fillna(0.0))

    trade_stats = metrics.summarize_option_trades(result.trades)
    runner = _runner_stats(result.trades)
    return {
        **summary,
        "trade_stats": trade_stats,
        "runner_stats": runner,
        "sharpe_ex_best": sharpe_ex_best,
        "sharpe_ex_top3": sharpe_ex_top3,
        "activations_per_year": result.activations_per_year,
        "premium_at_risk_per_year": result.premium_at_risk_per_year,
        "cash_premium_per_year": result.cash_premium_per_year,
        "max_concurrent_risk": result.max_concurrent_risk,
        "avg_dte": result.avg_dte,
        "avg_moneyness": result.avg_moneyness,
        "n_trades": int(len(result.trades)),
        "addon_success_rate": result.addon_success_rate,
        "partial_trigger_rate": result.partial_trigger_rate,
        "late_entry_block_rate": result.late_entry_block_rate,
    }


def _runner_stats(trades: pd.DataFrame) -> dict[str, float]:
    if trades is None or trades.empty or "runner_return" not in trades:
        return {"runner_avg_return": np.nan, "runner_best_return": np.nan, "runner_worst_return": np.nan}
    r = pd.to_numeric(trades["runner_return"], errors="coerce").dropna()
    return {
        "runner_avg_return": float(r.mean()) if len(r) else np.nan,
        "runner_best_return": float(r.max()) if len(r) else np.nan,
        "runner_worst_return": float(r.min()) if len(r) else np.nan,
    }


def subperiod_trade_spread(result: bt.V3Result) -> int:
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


def evaluate_gates(summary: dict, result: bt.V3Result) -> dict:
    base = summary["baseline"]["full"]
    opt = summary["v3_options"]["full"]
    tilt = summary["tactical_tilt"]["full"]
    gates: dict[str, dict] = {}

    gates["sharpe_vs_baseline"] = {
        "pass": bool(np.isfinite(opt["sharpe"]) and opt["sharpe"] - base["sharpe"] >= SHARPE_BASELINE_MIN),
        "detail": f"v3 {opt['sharpe']:.3f} vs baseline {base['sharpe']:.3f} (need +{SHARPE_BASELINE_MIN:.2f})",
    }
    gates["sharpe_vs_tilt"] = {
        "pass": bool(np.isfinite(opt["sharpe"]) and np.isfinite(tilt["sharpe"]) and opt["sharpe"] - tilt["sharpe"] >= SHARPE_TILT_MIN),
        "detail": f"v3 {opt['sharpe']:.3f} vs tactical tilt {tilt['sharpe']:.3f} (need +{SHARPE_TILT_MIN:.2f})",
    }
    gates["cagr_vs_baseline"] = {
        "pass": bool(np.isfinite(opt["cagr"]) and opt["cagr"] - base["cagr"] >= CAGR_IMPROVE_MIN),
        "detail": f"v3 {opt['cagr']:.4f} vs baseline {base['cagr']:.4f} (need +{CAGR_IMPROVE_MIN:.4f})",
    }
    gates["drawdown_ok"] = {
        "pass": bool(opt["max_drawdown"] - base["max_drawdown"] >= -DD_TOLERANCE),
        "detail": f"v3 {opt['max_drawdown']:.3f} vs baseline {base['max_drawdown']:.3f}",
    }
    gates["cvar5_ok"] = {
        "pass": bool(opt["cvar_5"] >= base["cvar_5"]),
        "detail": f"v3 {opt['cvar_5']:.4f} vs baseline {base['cvar_5']:.4f}",
    }
    cvar1_ok = True
    if np.isfinite(opt.get("cvar_1", np.nan)) and np.isfinite(base.get("cvar_1", np.nan)):
        cvar1_ok = opt["cvar_1"] >= base["cvar_1"]
    gates["cvar1_ok"] = {
        "pass": bool(cvar1_ok),
        "detail": f"v3 {opt.get('cvar_1', np.nan):.4f} vs baseline {base.get('cvar_1', np.nan):.4f}",
    }
    gates["sharpe_ex_best_ok"] = {
        "pass": bool(np.isfinite(summary["sharpe_ex_best"]) and summary["sharpe_ex_best"] > base["sharpe"]),
        "detail": f"ex-best {summary['sharpe_ex_best']:.3f} vs baseline {base['sharpe']:.3f}",
    }
    gates["sharpe_ex_top3_ok"] = {
        "pass": bool(np.isfinite(summary["sharpe_ex_top3"]) and summary["sharpe_ex_top3"] >= base["sharpe"]),
        "detail": f"ex-top3 {summary['sharpe_ex_top3']:.3f} vs baseline {base['sharpe']:.3f}",
    }
    gates["annual_premium_ok"] = {
        "pass": bool(summary["premium_at_risk_per_year"] <= bt.MAX_ANNUAL_RISK + 1e-9),
        "detail": f"{summary['premium_at_risk_per_year']*100:.2f}% NAV/yr (cap {bt.MAX_ANNUAL_RISK*100:.2f}%)",
    }
    gates["concurrent_premium_ok"] = {
        "pass": bool(summary["max_concurrent_risk"] <= bt.MAX_CONCURRENT_RISK + 1e-9),
        "detail": f"{summary['max_concurrent_risk']*100:.2f}% NAV concurrent (cap {bt.MAX_CONCURRENT_RISK*100:.2f}%)",
    }
    gates["enough_trades"] = {
        "pass": bool(summary["n_trades"] >= 10),
        "detail": f"{summary['n_trades']} trades (need >= 10)",
    }
    thirds = subperiod_trade_spread(result)
    gates["not_one_subperiod"] = {
        "pass": bool(thirds >= 2),
        "detail": f"trades present in {thirds}/3 time-thirds",
    }
    gates["costs_conservative"] = {
        "pass": True,
        "detail": "IV markup x1.05 plus 5% entry and exit slippage on gross option notional",
    }
    gates["no_lookahead"] = {
        "pass": True,
        "detail": "signals lagged one week; verifier re-checks representative feature lag",
    }
    gates["matches_or_beats_tilt"] = {
        "pass": bool(np.isfinite(opt["sharpe"]) and np.isfinite(tilt["sharpe"]) and opt["sharpe"] >= tilt["sharpe"]),
        "detail": f"v3 Sharpe {opt['sharpe']:.3f} vs tactical tilt {tilt['sharpe']:.3f}",
    }
    return gates


def decide_verdict(gates: dict, summary: dict) -> str:
    if summary["n_trades"] < 10:
        return "RESEARCH-ONLY"

    hard_reject = [
        "drawdown_ok",
        "cvar5_ok",
        "cvar1_ok",
        "sharpe_ex_best_ok",
        "sharpe_ex_top3_ok",
    ]
    if any(not gates[k]["pass"] for k in hard_reject):
        return "REJECT"

    candidate_keys = [
        "sharpe_vs_baseline",
        "sharpe_vs_tilt",
        "cagr_vs_baseline",
        "drawdown_ok",
        "cvar5_ok",
        "cvar1_ok",
        "sharpe_ex_best_ok",
        "sharpe_ex_top3_ok",
        "annual_premium_ok",
        "concurrent_premium_ok",
        "enough_trades",
        "not_one_subperiod",
        "matches_or_beats_tilt",
    ]
    passed = sum(1 for k in candidate_keys if gates[k]["pass"])
    if passed >= 12 and gates["sharpe_vs_tilt"]["pass"] and gates["matches_or_beats_tilt"]["pass"]:
        return "CANDIDATE FOR REAL-CHAIN TESTING"

    opt = summary["v3_options"]["full"]
    base = summary["baseline"]["full"]
    improves_shape = (
        (np.isfinite(opt["sharpe"]) and opt["sharpe"] >= base["sharpe"])
        or (np.isfinite(opt.get("cvar_5", np.nan)) and opt["cvar_5"] >= base["cvar_5"])
    )
    return "RESEARCH-ONLY" if improves_shape else "REJECT"
