#!/usr/bin/env python3
"""Run the first non-promotable point-in-time SEC factor diagnostic."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_exhaustive_return_first_discovery_batch_66 import metrics_for
from systematic_trader.ggg_independent import next_week_returns, portfolio_path

CONFIG_PATH = ROOT / "config/sec_fundamental_factor_diagnostic_v1.json"
OUTPUT = ROOT / "evidence/sec_fundamental_factor_diagnostic_v1"


def rank_pct(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average") * 2.0 - 1.0


def sector_neutral_feature(frame: pd.DataFrame, feature: str, sign: float, sectors: dict[str, str]) -> pd.Series:
    values = pd.to_numeric(frame[feature], errors="coerce")
    sector = frame.ticker.map(sectors)
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, indices in frame.groupby(sector).groups.items():
        valid = values.loc[indices].dropna()
        if len(valid) >= 3:
            result.loc[valid.index] = rank_pct(valid) * sign
    return result


def family_scores(inputs: pd.DataFrame, config: dict, sectors: dict[str, str]) -> pd.DataFrame:
    rows = []
    basic_families = [name for name in config["families"] if name != "composite"]
    for decision, frame in inputs.groupby("decision_time"):
        frame = frame.copy().reset_index(drop=True)
        family_values = {}
        for family in basic_families:
            parts = []
            spec = config["families"][family]
            for feature in spec.get("positive", []):
                if feature in frame:
                    parts.append(sector_neutral_feature(frame, feature, 1.0, sectors))
            for feature in spec.get("negative", []):
                if feature in frame:
                    parts.append(sector_neutral_feature(frame, feature, -1.0, sectors))
            if parts:
                matrix = pd.concat(parts, axis=1)
                score = matrix.mean(axis=1, skipna=True).where(matrix.notna().sum(axis=1) >= int(config["minimum_available_features_per_family"]))
            else:
                score = pd.Series(np.nan, index=frame.index)
            family_values[family] = score
        composite_matrix = pd.DataFrame(family_values)
        family_values["composite"] = composite_matrix.mean(axis=1, skipna=True).where(composite_matrix.notna().sum(axis=1) >= 2)
        for family, values in family_values.items():
            for index, value in values.items():
                rows.append({"decision_time": decision, "ticker": frame.loc[index, "ticker"], "family": family, "score": value, "sector": sectors.get(frame.loc[index, "ticker"])})
    return pd.DataFrame(rows)


def weekly_prices(price_file: Path, symbols: list[str]) -> pd.DataFrame:
    raw = pd.read_csv(price_file, usecols=["observation_date", "ticker", "adjusted_close"])
    raw["observation_date"] = pd.to_datetime(raw.observation_date)
    raw["adjusted_close"] = pd.to_numeric(raw.adjusted_close, errors="coerce")
    daily = raw[raw.ticker.isin(symbols)].pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    return daily.resample("W-FRI").last().dropna(how="all")


def build_weights(scores: pd.DataFrame, prices: pd.DataFrame, family: str, top_n: int, minimum_companies: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = pd.DataFrame(0.0, index=prices.index, columns=prices.columns.union(pd.Index(["cash::USD"])))
    output["cash::USD"] = 1.0
    choices = []
    selected_scores = scores[scores.family == family]
    for decision, frame in selected_scores.groupby("decision_time"):
        decision_time = pd.to_datetime(decision, utc=True).tz_convert(None)
        future_dates = prices.index[prices.index > decision_time]
        if len(future_dates) == 0:
            continue
        effective = future_dates[0]
        eligible = frame.dropna(subset=["score"]).copy()
        eligible = eligible[eligible.ticker.isin(prices.columns) & eligible.ticker.map(lambda ticker: pd.notna(prices.loc[effective, ticker]))]
        if len(eligible) < minimum_companies:
            continue
        selected = eligible.sort_values(["score", "ticker"], ascending=[False, True]).head(top_n)
        next_decisions = pd.to_datetime(selected_scores.decision_time.unique(), utc=True).tz_convert(None)
        later = next_decisions[next_decisions > decision_time]
        end = prices.index.max() if len(later) == 0 else prices.index[prices.index < later.min()].max()
        output.loc[effective:end] = 0.0
        output.loc[effective:end, selected.ticker] = 1.0 / len(selected)
        choices.extend({"family": family, "decision_time": decision, "effective_date": effective, "ticker": row.ticker, "score": row.score, "sector": row.sector, "weight": 1.0 / len(selected)} for row in selected.itertuples())
    return output, pd.DataFrame(choices)


def static_weights(prices: pd.DataFrame, allocations: dict[str, float]) -> pd.DataFrame:
    result = pd.DataFrame(0.0, index=prices.index, columns=prices.columns.union(pd.Index(["cash::USD"])))
    for ticker, weight in allocations.items():
        result[ticker] = weight
    return result


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    sec_vintage = ROOT / "data/sec_vintages" / config["sec_vintage"]
    price_vintage = ROOT / "data/sec_pilot_price_vintages" / config["price_vintage"]
    universe = pd.read_csv(sec_vintage / "universe.csv")
    inputs = pd.read_csv(sec_vintage / "quarterly_factor_inputs.csv", low_memory=False)
    inputs["decision_time"] = pd.to_datetime(inputs.decision_time, utc=True)
    pilot_tickers = sorted(universe.ticker.tolist())
    prices = weekly_prices(price_vintage / "prices.csv", pilot_tickers + ["SPY", "XLK", "XLE"])
    forward = next_week_returns(prices)
    pilot_spec = json.loads((ROOT / "config/sec_fundamental_pilot_v1.json").read_text())
    sectors = {ticker: sector for sector, tickers in pilot_spec["pilot_universe"].items() for ticker in tickers}
    scores = family_scores(inputs, config, sectors)

    families = list(config["families"])
    weights, choice_frames = {}, []
    for family in families:
        weights[family], choices = build_weights(scores, prices, family, int(config["top_n"]), int(config["minimum_companies_per_decision"]))
        choice_frames.append(choices)
    weights["benchmark::SPY"] = static_weights(prices, {"SPY": 1.0})
    weights["benchmark::XLK"] = static_weights(prices, {"XLK": 1.0})
    weights["benchmark::XLE"] = static_weights(prices, {"XLE": 1.0})
    weights["benchmark::equal_XLK_XLE"] = static_weights(prices, {"XLK": 0.5, "XLE": 0.5})
    weights["benchmark::equal_all_20"] = static_weights(prices, {ticker: 1.0 / len(pilot_tickers) for ticker in pilot_tickers})

    paths, performance_rows = {}, []
    training_end = pd.Timestamp(config["training_end"])
    for name, allocation in weights.items():
        paths[name] = {}
        for cost in config["cost_bps"]:
            path = portfolio_path(allocation, forward.reindex(columns=allocation.columns), float(cost))
            paths[name][int(cost)] = path
            metric = metrics_for(path.loc[path.index >= pd.Timestamp("2012-01-06")], training_end)
            performance_rows.append({"candidate": name, "cost_bps": cost, **metric})
    performance = pd.DataFrame(performance_rows)
    primary = performance[performance.cost_bps == 50].sort_values("holdout_cagr", ascending=False)

    ic_rows = []
    forward13 = prices.pct_change(13, fill_method=None).shift(-13)
    for (decision, family), frame in scores.dropna(subset=["score"]).groupby(["decision_time", "family"]):
        effective_dates = prices.index[prices.index > pd.to_datetime(decision, utc=True).tz_convert(None)]
        if len(effective_dates) == 0:
            continue
        effective = effective_dates[0]
        returns = forward13.loc[effective]
        joined = frame.set_index("ticker")[["score"]].join(returns.rename("forward_13w")).dropna()
        if len(joined) >= 8:
            ic_rows.append({"decision_time": decision, "effective_date": effective, "family": family, "companies": len(joined), "spearman_ic": joined.score.corr(joined.forward_13w, method="spearman")})
    ic = pd.DataFrame(ic_rows)
    ic_summary = ic.groupby("family").agg(decisions=("spearman_ic", "count"), mean_ic=("spearman_ic", "mean"), median_ic=("spearman_ic", "median"), positive_ic_share=("spearman_ic", lambda x: float((x > 0).mean()))).reset_index()

    best_factor = str(primary[~primary.candidate.str.startswith("benchmark::")].iloc[0].candidate)
    best_benchmark = str(primary[primary.candidate.str.startswith("benchmark::")].iloc[0].candidate)
    best_factor_row = primary[primary.candidate == best_factor].iloc[0]
    best_benchmark_row = primary[primary.candidate == best_benchmark].iloc[0]
    diagnostic_positive = bool(best_factor_row.holdout_cagr > best_benchmark_row.holdout_cagr)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores.to_csv(OUTPUT / "factor_scores.csv", index=False)
    pd.concat(choice_frames, ignore_index=True).to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    ic.to_csv(OUTPUT / "information_coefficients.csv", index=False)
    ic_summary.to_csv(OUTPUT / "information_coefficient_summary.csv", index=False)
    weights[best_factor].rename_axis("Date").to_csv(OUTPUT / "best_factor_weights.csv")
    weights[best_factor].iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "best_factor_current_holdings.csv")
    result = {
        "experiment": config["experiment"], "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sec_vintage": config["sec_vintage"], "price_vintage": config["price_vintage"],
        "factor_families": families, "quarterly_score_rows": len(scores), "portfolio_choice_rows": int(sum(len(frame) for frame in choice_frames)),
        "best_factor": best_factor, "best_factor_holdout_50bps_cagr": float(best_factor_row.holdout_cagr),
        "best_factor_holdout_50bps_sharpe": float(best_factor_row.holdout_sharpe), "best_factor_holdout_50bps_drawdown": float(best_factor_row.holdout_drawdown),
        "best_factor_full_50bps_cagr": float(best_factor_row.full_cagr), "best_factor_full_50bps_drawdown": float(best_factor_row.full_drawdown),
        "best_benchmark": best_benchmark, "best_benchmark_holdout_50bps_cagr": float(best_benchmark_row.holdout_cagr),
        "diagnostic_factor_beats_best_benchmark": diagnostic_positive,
        "strategy_promotion_authorized": False, "promotion_blockers": config["promotion_blockers"],
        "decision": "retain_factor_family_for_survivorship_safe_retest" if diagnostic_positive else "do_not_blend_fundamental_pilot",
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC fundamental factor diagnostic v1\n\n"
        f"Tested five predeclared point-in-time families across the current 20-company technology/energy pilot. The best factor was `{best_factor}` with holdout CAGR **{best_factor_row.holdout_cagr:.2%}**, Sharpe **{best_factor_row.holdout_sharpe:.3f}**, and drawdown **{best_factor_row.holdout_drawdown:.2%}** after 50-bps costs.\n\n"
        f"The best benchmark was `{best_benchmark}` at **{best_benchmark_row.holdout_cagr:.2%}**. Factor beats benchmark: **{diagnostic_positive}**. Decision: `{result['decision']}`.\n\n"
        "This is not a promotable result. The universe contains today's surviving companies, has no historical membership or delisted stocks, and uses revision-prone free adjusted prices. The experiment diagnoses economic direction only and cannot alter any frozen strategy.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
