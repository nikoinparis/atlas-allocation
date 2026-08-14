#!/usr/bin/env python3
"""Build a comprehensive, same-data current strategy scorecard."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.residual_momentum_source import residual_momentum_signal, top_five_weights
from systematic_trader.trend_reversal_source import blend_with_ggg

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/frozen_ggg_inputs_v1"
V1_WEIGHTS = ROOT / "data/audit_comparators/v1_frontier_phase5_fragility_guard_weights.csv"
OUTPUT = ROOT / "evidence/main_strategy_metrics_batch_51"
V1_SHA256 = "cfcabd30fe6bf6f8281162dc4228973d4f965a897532d2069be091a6470c1e75"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(returns: pd.Series, turnover: pd.Series) -> dict:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    t = pd.to_numeric(turnover, errors="coerce").reindex(r.index)
    wealth = (1.0 + r).cumprod()
    years = len(r) / 52.0
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0)
    arithmetic = float(r.mean() * 52.0)
    volatility = float(r.std(ddof=1) * np.sqrt(52.0))
    downside = r.clip(upper=0.0)
    downside_deviation = float(np.sqrt((downside.pow(2).mean())) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    quantile = float(r.quantile(0.05))
    return {
        "weeks": len(r), "start": str(r.index.min().date()), "end": str(r.index.max().date()),
        "total_return": float(wealth.iloc[-1] - 1.0), "cagr": cagr,
        "arithmetic_ann_return": arithmetic, "ann_vol": volatility,
        "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan,
        "sortino_zero_target": arithmetic / downside_deviation if downside_deviation else np.nan,
        "max_drawdown": float(drawdown.min()), "calmar": cagr / abs(float(drawdown.min())) if drawdown.min() else np.nan,
        "positive_week_share": float((r > 0).mean()), "var_5_weekly": quantile,
        "cvar_5_weekly": float(r[r <= quantile].mean()), "best_week": float(r.max()), "worst_week": float(r.min()),
        "annualized_one_way_turnover": float(t.mean() * 52.0),
    }


def main() -> int:
    assert sha256(V1_WEIGHTS) == V1_SHA256
    prices = read_dated_csv(SOURCE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    causal = run_from_artifacts(SOURCE, causal_training=True).stages["final_etf_weights"]
    legacy_ggg = run_from_artifacts(SOURCE, causal_training=False).stages["final_etf_weights"]
    v1 = read_dated_csv(V1_WEIGHTS).reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    residual = top_five_weights(residual_momentum_signal(prices), prices)
    residual_blend = blend_with_ggg(causal, residual, 0.10)
    spy = pd.DataFrame(0.0, index=prices.index, columns=prices.columns); spy["SPY"] = 1.0
    strategies = {
        "causal_ggg_current_main": causal,
        "v1_frontier_legacy_unqualified": v1,
        "ggg_plus_residual_raw_10_rejected": residual_blend,
        "legacy_ggg_lookahead_warning": legacy_ggg,
        "spy_buy_hold": spy,
    }
    paths = {name: portfolio_path(weights, forward, 50.0) for name, weights in strategies.items()}
    end = prices.index.max()
    window_starts = {
        "trailing_1y": end - pd.DateOffset(years=1), "trailing_2y": end - pd.DateOffset(years=2),
        "trailing_3y": end - pd.DateOffset(years=3), "trailing_5y": end - pd.DateOffset(years=5),
        "trailing_10y": end - pd.DateOffset(years=10), "post_2024": pd.Timestamp("2024-01-05"),
        "full": prices.index.min(),
    }
    rows = []
    for name, path in paths.items():
        for window, start in window_starts.items():
            subset = path.loc[path.index >= start]
            rows.append({"strategy": name, "cost_bps": 50, "window": window, **metrics(subset["net_return"], subset["turnover"])})
    scorecard = pd.DataFrame(rows)

    risk_rows = []
    spy_returns = paths["spy_buy_hold"]["net_return"]
    for name, path in paths.items():
        for window, start in window_starts.items():
            strategy_returns = path.loc[path.index >= start, "net_return"]
            benchmark = spy_returns.reindex(strategy_returns.index)
            aligned = pd.concat([strategy_returns.rename("strategy"), benchmark.rename("spy")], axis=1).dropna()
            covariance = aligned.cov().loc["strategy", "spy"]
            beta = float(covariance / aligned["spy"].var()) if aligned["spy"].var() else np.nan
            active = aligned["strategy"] - aligned["spy"]
            tracking_error = float(active.std(ddof=1) * np.sqrt(52.0))
            risk_rows.append({"strategy": name, "window": window, "correlation_to_spy": float(aligned.corr().loc["strategy", "spy"]), "beta_to_spy": beta, "annual_tracking_error": tracking_error, "information_ratio_zero_rf": float(active.mean() * 52.0 / tracking_error) if tracking_error else np.nan})
    risk = pd.DataFrame(risk_rows)

    calendar_rows = []
    for name, path in paths.items():
        net = path["net_return"]
        for year, values in net.groupby(net.index.year):
            if year >= 2020:
                calendar_rows.append({"strategy": name, "year": int(year), "weeks": len(values), "calendar_return": float((1.0 + values).prod() - 1.0), "calendar_vol": float(values.std(ddof=1) * np.sqrt(52.0)), "calendar_sharpe_zero_rf": float(values.mean() * 52.0 / (values.std(ddof=1) * np.sqrt(52.0))) if values.std(ddof=1) else np.nan})
    calendar = pd.DataFrame(calendar_rows)

    cost_rows = []
    for cost in (10.0, 50.0, 100.0):
        path = portfolio_path(causal, forward, cost)
        for window in ("trailing_1y", "trailing_3y", "trailing_5y", "full"):
            subset = path.loc[path.index >= window_starts[window]]
            cost_rows.append({"strategy": "causal_ggg_current_main", "cost_bps": cost, "window": window, **metrics(subset.net_return, subset.turnover)})
    cost_sensitivity = pd.DataFrame(cost_rows)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    scorecard.to_csv(OUTPUT / "trailing_scorecard_50bps.csv", index=False)
    risk.to_csv(OUTPUT / "benchmark_risk_metrics.csv", index=False)
    calendar.to_csv(OUTPUT / "calendar_year_metrics.csv", index=False)
    cost_sensitivity.to_csv(OUTPUT / "causal_ggg_cost_sensitivity.csv", index=False)
    artifacts = ["trailing_scorecard_50bps.csv", "benchmark_risk_metrics.csv", "calendar_year_metrics.csv", "causal_ggg_cost_sensitivity.csv"]
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "primary_cost_bps": 50, "data_end": str(end.date()), "current_main": "causal_ggg_current_main", "comparison_status": {"v1_frontier_legacy_unqualified": "selection-contaminated and incomplete causal lineage", "ggg_plus_residual_raw_10_rejected": "failed predeclared Batch 50 gates", "legacy_ggg_lookahead_warning": "known one-week allocator lookahead", "spy_buy_hold": "benchmark"}, "v1_weights_sha256": sha256(V1_WEIGHTS), "live_trading_enabled": False}
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifacts}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(scorecard[(scorecard.strategy == "causal_ggg_current_main")][["window", "cagr", "arithmetic_ann_return", "ann_vol", "sharpe_zero_rf", "sortino_zero_target", "max_drawdown", "calmar"]].to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
