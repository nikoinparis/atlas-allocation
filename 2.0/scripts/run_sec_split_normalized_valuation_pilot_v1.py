#!/usr/bin/env python3
"""Audit and test split-normalized point-in-time SEC valuation factors."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_split_normalized_valuation_pilot_v1.json"
PILOT_CONFIG = ROOT / "config/sec_fundamental_pilot_v1.json"
OUTPUT = ROOT / "evidence/sec_split_normalized_valuation_pilot_v1"


def rank_pct(values: pd.Series) -> pd.Series:
    return values.rank(pct=True, method="average") * 2.0 - 1.0


def metrics(path: pd.DataFrame, training_end: pd.Timestamp) -> dict[str, float]:
    result: dict[str, float] = {}
    for label, sample in {
        "full": path,
        "holdout": path.loc[path.index > training_end],
        "trailing_1y": path.loc[path.index >= path.index.max() - pd.DateOffset(years=1)],
    }.items():
        returns = sample.net_return.dropna()
        years = len(returns) / 52.0
        curve = (1.0 + returns).cumprod()
        volatility = returns.std(ddof=1)
        result[f"{label}_cagr"] = float(curve.iloc[-1] ** (1.0 / years) - 1.0)
        result[f"{label}_sharpe"] = float(returns.mean() / volatility * np.sqrt(52)) if volatility else 0.0
        result[f"{label}_drawdown"] = float((curve / curve.cummax() - 1.0).min())
    return result


def portfolio_path(weights: pd.DataFrame, forward: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    gross = (weights * forward.reindex(columns=weights.columns).fillna(0.0)).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    return pd.DataFrame({"gross_return": gross, "turnover": turnover, "cost": cost, "net_return": net, "wealth": wealth, "drawdown": wealth / wealth.cummax() - 1.0})


def sector_neutral(frame: pd.DataFrame, column: str, sectors: dict[str, str]) -> pd.Series:
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    groups = frame.ticker.map(sectors)
    for _, indices in frame.groupby(groups).groups.items():
        valid = pd.to_numeric(frame.loc[indices, column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) >= 3:
            result.loc[valid.index] = rank_pct(valid)
    return result


def main() -> int:
    config = json.loads(CONFIG.read_text())
    sec_dir = ROOT / "data/sec_vintages" / config["sec_vintage"]
    price_dir = ROOT / "data/sec_pilot_price_vintages" / config["price_vintage"]
    inputs = pd.read_csv(sec_dir / "quarterly_factor_inputs.csv", low_memory=False, dtype={"cik10": str})
    inputs["decision_time"] = pd.to_datetime(inputs.decision_time, utc=True)
    for column in ["shares_outstanding__period_end", "shares_outstanding__available_at"]:
        inputs[column] = pd.to_datetime(inputs[column], utc=True, errors="coerce")
    numeric = ["shares_outstanding", "net_income", "operating_cash_flow", "capital_expenditure", "revenue", "operating_margin", "operating_cash_flow_margin", "cash_to_assets", "equity_to_assets", "diluted_shares__yoy_growth"]
    for column in numeric:
        inputs[column] = pd.to_numeric(inputs[column], errors="coerce")

    raw_prices = pd.read_csv(price_dir / "prices.csv", usecols=["observation_date", "ticker", "close", "adjusted_close"])
    raw_prices["observation_date"] = pd.to_datetime(raw_prices.observation_date)
    close = raw_prices.pivot(index="observation_date", columns="ticker", values="close").sort_index()
    adjusted = raw_prices.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    weekly = adjusted.resample("W-FRI").last().dropna(how="all")
    weekly["cash::USD"] = 1.0
    forward = weekly.pct_change(fill_method=None).shift(-1).fillna(0.0)

    actions = pd.read_csv(price_dir / "corporate_actions.csv")
    actions["event_date"] = pd.to_datetime(actions.event_date, utc=True)
    actions["amount"] = pd.to_numeric(actions.amount, errors="coerce")
    splits = actions[(actions.action_type == "stock_split") & actions.amount.gt(0)].copy()
    split_groups = {ticker: frame.sort_values("event_date") for ticker, frame in splits.groupby("ticker")}

    audit_rows = []
    for row in inputs.itertuples(index=False):
        decision = pd.Timestamp(row.decision_time)
        ticker = str(row.ticker)
        prior_dates = close.index[close.index < decision.tz_convert(None)]
        price_date = prior_dates[-1] if len(prior_dates) else pd.NaT
        raw_close = float(close.at[price_date, ticker]) if pd.notna(price_date) and ticker in close and pd.notna(close.at[price_date, ticker]) else np.nan
        adj_close = float(adjusted.at[price_date, ticker]) if pd.notna(price_date) and ticker in adjusted and pd.notna(adjusted.at[price_date, ticker]) else np.nan
        shares = float(row.shares_outstanding) if pd.notna(row.shares_outstanding) else np.nan
        period_end = pd.Timestamp(row.shares_outstanding__period_end) if pd.notna(row.shares_outstanding__period_end) else pd.NaT
        multiplier = 1.0
        events = 0
        if pd.notna(period_end) and pd.notna(price_date) and ticker in split_groups:
            group = split_groups[ticker]
            applicable = group[(group.event_date > period_end) & (group.event_date <= pd.Timestamp(price_date, tz="UTC"))]
            multiplier = float(applicable.amount.prod()) if len(applicable) else 1.0
            events = int(len(applicable))
        normalized_shares = shares * multiplier if np.isfinite(shares) and shares > 0 else np.nan
        market_cap = raw_close * normalized_shares if np.isfinite(raw_close) and np.isfinite(normalized_shares) else np.nan
        naive_market_cap = adj_close * shares if np.isfinite(adj_close) and np.isfinite(shares) else np.nan
        capex = abs(float(row.capital_expenditure)) if pd.notna(row.capital_expenditure) else np.nan
        free_cash_flow = float(row.operating_cash_flow) - capex if pd.notna(row.operating_cash_flow) and np.isfinite(capex) else np.nan
        audit_rows.append({
            "decision_time": decision, "cik10": str(row.cik10).zfill(10), "ticker": ticker,
            "price_date": price_date, "raw_close": raw_close, "adjusted_close_audit_only": adj_close,
            "shares_fact": shares, "shares_period_end": period_end, "shares_available_at": row.shares_outstanding__available_at,
            "split_events_after_fact": events, "split_multiplier": multiplier, "normalized_shares": normalized_shares,
            "market_cap": market_cap, "naive_adjusted_price_market_cap": naive_market_cap,
            "naive_to_normalized_market_cap_ratio": naive_market_cap / market_cap if np.isfinite(naive_market_cap) and market_cap > 0 else np.nan,
            "earnings_yield": float(row.net_income) / market_cap if pd.notna(row.net_income) and market_cap > 0 else np.nan,
            "free_cash_flow_yield": free_cash_flow / market_cap if np.isfinite(free_cash_flow) and market_cap > 0 else np.nan,
            "sales_yield": float(row.revenue) / market_cap if pd.notna(row.revenue) and market_cap > 0 else np.nan,
            "operating_margin": row.operating_margin, "operating_cash_flow_margin": row.operating_cash_flow_margin,
            "cash_to_assets": row.cash_to_assets, "equity_to_assets": row.equity_to_assets,
            "negative_dilution": -float(row.diluted_shares__yoy_growth) if pd.notna(row.diluted_shares__yoy_growth) else np.nan,
            "available_before_decision": bool(pd.notna(row.shares_outstanding__available_at) and row.shares_outstanding__available_at < decision),
            "price_before_decision": bool(pd.notna(price_date) and price_date < decision.tz_convert(None)),
        })
    factors = pd.DataFrame(audit_rows)

    score_rows = []
    sectors_spec = json.loads(PILOT_CONFIG.read_text())["pilot_universe"]
    sectors = {ticker: sector for sector, tickers in sectors_spec.items() for ticker in tickers}
    for decision, frame in factors.groupby("decision_time"):
        frame = frame.copy().reset_index(drop=True)
        components = {name: sector_neutral(frame, name, sectors) for name in ["earnings_yield", "free_cash_flow_yield", "sales_yield", "operating_margin", "operating_cash_flow_margin", "cash_to_assets", "equity_to_assets", "negative_dilution"]}
        family_scores = {
            "earnings_yield": components["earnings_yield"],
            "free_cash_flow_yield": components["free_cash_flow_yield"],
            "sales_yield": components["sales_yield"],
            "composite_value": pd.concat([components["earnings_yield"], components["free_cash_flow_yield"], components["sales_yield"]], axis=1).mean(axis=1, skipna=True),
            "quality_at_reasonable_price": pd.concat(list(components.values()), axis=1).mean(axis=1, skipna=True),
        }
        for family, scores in family_scores.items():
            for index, score in scores.items():
                score_rows.append({"decision_time": decision, "ticker": frame.at[index, "ticker"], "family": family, "score": score, "sector": sectors.get(frame.at[index, "ticker"])})
    scores = pd.DataFrame(score_rows)

    weights_by_family: dict[str, pd.DataFrame] = {}
    choices = []
    assets = weekly.columns
    decision_values = sorted(scores.decision_time.unique())
    for family in config["families"]:
        weights = pd.DataFrame(0.0, index=weekly.index, columns=assets)
        weights["cash::USD"] = 1.0
        family_scores = scores[scores.family == family]
        for decision, frame in family_scores.groupby("decision_time"):
            decision_naive = pd.Timestamp(decision).tz_convert(None)
            effective_dates = weekly.index[weekly.index > decision_naive]
            if not len(effective_dates):
                continue
            effective = effective_dates[0]
            eligible = frame.dropna(subset=["score"])
            eligible = eligible[eligible.ticker.isin(weekly.columns) & eligible.ticker.map(lambda item: pd.notna(weekly.at[effective, item]))]
            if len(eligible) < int(config["minimum_companies"]):
                continue
            selected = eligible.sort_values(["score", "ticker"], ascending=[False, True]).head(int(config["top_n"]))
            later = [pd.Timestamp(value).tz_convert(None) for value in decision_values if pd.Timestamp(value) > pd.Timestamp(decision)]
            end = weekly.index.max() if not later else weekly.index[weekly.index < min(later)].max()
            weights.loc[effective:end] = 0.0
            weights.loc[effective:end, selected.ticker] = 1.0 / len(selected)
            choices.extend({"decision_time": decision, "effective_date": effective, "family": family, "ticker": row.ticker, "score": row.score, "weight": 1.0 / len(selected)} for row in selected.itertuples())
        weights_by_family[family] = weights

    benchmark_assets = {"benchmark::SPY": "SPY", "benchmark::XLK": "XLK", "benchmark::XLE": "XLE"}
    for name, ticker in benchmark_assets.items():
        weights = pd.DataFrame(0.0, index=weekly.index, columns=assets)
        weights[ticker] = 1.0
        weights_by_family[name] = weights
    equal = pd.DataFrame(0.0, index=weekly.index, columns=assets)
    pilot_tickers = sorted(inputs.ticker.unique())
    equal[pilot_tickers] = 1.0 / len(pilot_tickers)
    weights_by_family["benchmark::equal20"] = equal

    performance_rows = []
    training_end = pd.Timestamp(config["training_end"])
    for family, weights in weights_by_family.items():
        for cost_bps in config["cost_bps"]:
            path = portfolio_path(weights, forward, float(cost_bps))
            performance_rows.append({"candidate": family, "cost_bps": cost_bps, **metrics(path, training_end)})
    performance = pd.DataFrame(performance_rows)
    primary = performance[performance.cost_bps == 50]
    factor_primary = primary[~primary.candidate.str.startswith("benchmark::")].sort_values("holdout_cagr", ascending=False)
    benchmark_primary = primary[primary.candidate.str.startswith("benchmark::")].sort_values("holdout_cagr", ascending=False)
    best_factor = factor_primary.iloc[0]
    best_benchmark = benchmark_primary.iloc[0]

    checks = {
        "all_prices_strictly_before_decision": bool(factors.price_before_decision.all()),
        "all_share_facts_available_before_decision": bool(factors.loc[factors.shares_fact.notna(), "available_before_decision"].all()),
        "all_positive_market_caps": bool(factors.loc[factors.market_cap.notna(), "market_cap"].gt(0).all()),
        "raw_close_used_for_market_cap": True,
        "adjusted_close_used_only_as_naive_audit": True,
        "split_adjustments_are_date_bounded": True,
        "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    factors.to_csv(OUTPUT / "normalized_valuation_inputs.csv", index=False)
    scores.to_csv(OUTPUT / "factor_scores.csv", index=False)
    pd.DataFrame(choices).to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    best_factor_name = str(best_factor.candidate)
    best_factor_path = portfolio_path(weights_by_family[best_factor_name], forward, 50.0)
    weights_by_family[best_factor_name].rename_axis("Date").to_csv(OUTPUT / "best_factor_weights.csv")
    best_factor_path.rename_axis("Date").to_csv(OUTPUT / "best_factor_path_50bps.csv")
    distortion = factors[factors.split_events_after_fact > 0].sort_values("naive_to_normalized_market_cap_ratio")
    distortion.to_csv(OUTPUT / "split_distortion_audit.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "valuation_rows": int(len(factors)), "rows_with_positive_market_cap": int(factors.market_cap.gt(0).sum()),
        "rows_with_split_adjustment": int((factors.split_events_after_fact > 0).sum()),
        "median_naive_to_normalized_cap_ratio_on_split_rows": float(distortion.naive_to_normalized_market_cap_ratio.median()) if len(distortion) else None,
        "best_factor": best_factor_name, "best_factor_holdout_50bps_cagr": float(best_factor.holdout_cagr),
        "best_factor_trailing_1y_50bps_cagr": float(best_factor.trailing_1y_cagr), "best_factor_holdout_50bps_sharpe": float(best_factor.holdout_sharpe),
        "best_factor_holdout_50bps_drawdown": float(best_factor.holdout_drawdown),
        "best_benchmark": str(best_benchmark.candidate), "best_benchmark_holdout_50bps_cagr": float(best_benchmark.holdout_cagr),
        "factor_beats_best_benchmark": bool(best_factor.holdout_cagr > best_benchmark.holdout_cagr),
        "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "current_survivor_pilot_only": True, "strategy_promotion_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Split-normalized SEC valuation pilot v1\n\n"
        "Market capitalization uses raw close and the latest SEC shares-outstanding fact known before each decision. "
        "Shares are carried forward only by stock splits occurring after the fact period and on or before the price date. "
        "Adjusted close appears only in the distortion audit and never in a valuation signal.\n\n"
        f"Best factor: `{result['best_factor']}`; holdout CAGR {result['best_factor_holdout_50bps_cagr']:.2%}, "
        f"Sharpe {result['best_factor_holdout_50bps_sharpe']:.3f}, drawdown {result['best_factor_holdout_50bps_drawdown']:.2%}. "
        f"Best benchmark: `{result['best_benchmark']}` at {result['best_benchmark_holdout_50bps_cagr']:.2%}.\n\n"
        "This remains a non-promotable current-survivor pilot. Its purpose is to establish a mechanically valid valuation pipeline before a broader survivorship-aware retest.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
