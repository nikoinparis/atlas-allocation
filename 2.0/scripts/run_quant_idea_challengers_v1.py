#!/usr/bin/env python3
"""Run the predeclared 2026 idea challengers and preserve every outcome."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import SnapshotStore
from src.systematic_trader.evaluation import block_bootstrap_intervals, performance_metrics
from src.systematic_trader.idea_challengers import (
    DailyBar,
    RankedAssetSignal,
    constrained_fractional_kelly,
    overnight_decomposition,
    ranked_asset_allocation,
)
from src.systematic_trader.research_statistics import (
    deflated_sharpe_ratio,
    information_coefficient_ratio,
    probability_of_backtest_overfitting,
    probabilistic_sharpe_ratio,
    white_reality_check_pvalue,
)


CONFIG_PATH = ROOT / "config" / "quant_idea_challengers_v1.json"
OUTPUT = ROOT / "evidence" / "quant_idea_challengers_v1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(values: list[float], periods: int) -> dict[str, float | int]:
    return performance_metrics(values, periods_per_year=periods).to_dict()


def covariance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    lm, rm = statistics.fmean(left), statistics.fmean(right)
    return sum((a - lm) * (b - rm) for a, b in zip(left, right)) / (len(left) - 1)


def load_prices() -> tuple[dict[str, list[DailyBar]], dict[str, object]]:
    store = SnapshotStore(ROOT / "data" / "vintages")
    manifests = store.manifests()
    eligible = [item for item in manifests if "prices.csv" in item.get("files", {})]
    if not eligible:
        raise RuntimeError("no verified price vintage is available")
    selected = max(eligible, key=lambda item: str(item["observed_at_utc"]))
    snapshot_id = str(selected["snapshot_id"])
    store.verify(snapshot_id)
    rows = read_csv(ROOT / "data" / "vintages" / snapshot_id / "payload" / "prices.csv")
    result: dict[str, list[DailyBar]] = defaultdict(list)
    for row in rows:
        if not all(row.get(name) for name in ("open", "high", "low", "close", "adjusted_close")):
            continue
        result[row["ticker"]].append(DailyBar(
            date=row["observation_date"], open=float(row["open"]), high=float(row["high"]),
            low=float(row["low"]), close=float(row["close"]), adjusted_close=float(row["adjusted_close"]),
        ))
    for values in result.values():
        values.sort(key=lambda item: item.date)
    return dict(result), selected


def run_overnight(config: dict[str, object], prices: dict[str, list[DailyBar]]) -> tuple[list[dict], list[dict]]:
    details: list[dict] = []
    scoreboard: list[dict] = []
    for symbol in config["symbols"]:
        bars = prices.get(symbol, [])
        for cost in (0, 10, 25, 50):
            rows = overnight_decomposition(bars, round_trip_cost_bps=cost)
            for start, end in config["eras"]:
                era = [row for row in rows if start <= str(row["date"]) <= end]
                if not era:
                    continue
                over = metrics([float(row["overnight_net"]) for row in era], 252)
                intra = metrics([float(row["intraday_net"]) for row in era], 252)
                details.append({"symbol": symbol, "cost_bps": cost, "start": start, "end": end,
                                "overnight": over, "intraday": intra})
                if start == "2021-01-01" and cost == 25:
                    passed = over["annual_return"] > 0 and over["sharpe_zero_rf"] > 0.5
                    scoreboard.append({
                        "idea": f"Overnight effect ({symbol})", "status": "WORKING" if passed else "REJECTED",
                        "headline": f"2021+ net Sharpe {over['sharpe_zero_rf']:.2f}; CAGR {over['annual_return']:.2%}",
                        "reason": "Passed frozen 25 bps gate" if passed else "Failed frozen post-2021 net gate",
                    })
    return details, scoreboard


def month_ends(series: dict[str, dict[str, float]], symbols: list[str]) -> list[str]:
    common = sorted(set.intersection(*(set(series[symbol]) for symbol in symbols)))
    result: list[str] = []
    for date in common:
        if not result or date[:7] != result[-1][:7]:
            result.append(date)
        else:
            result[-1] = date
    return result


def run_raam(config: dict[str, object], prices: dict[str, list[DailyBar]]) -> dict[str, object]:
    risky = list(config["risky_assets"])
    required = risky + [str(config["cash_asset"])]
    missing = [symbol for symbol in required if symbol not in prices]
    if missing:
        return {"status": "BLOCKED", "reason": f"snapshot missing {missing}"}
    series = {symbol: {bar.date: bar.adjusted_close for bar in prices[symbol]} for symbol in required}
    dates = month_ends(series, required)
    all_common = sorted(set.intersection(*(set(series[symbol]) for symbol in required)))
    index = {date: position for position, date in enumerate(all_common)}
    decisions = [date for date in dates if date >= config["evaluation_start"] and index[date] >= config["trend_moving_average_days"]]
    previous_weights = {"CASH": 1.0}
    strategy_returns: list[float] = []
    baseline_returns: list[float] = []
    audit: list[dict] = []
    cost_rate = float(config["cost_bps_one_way"]) / 10000.0
    for current, following in zip(decisions, decisions[1:]):
        current_index = index[current]
        lookback = int(config["lookback_trading_days"])
        windows: dict[str, list[float]] = {
            symbol: [series[symbol][day] for day in all_common[current_index - lookback:current_index + 1]]
            for symbol in risky
        }
        returns = {symbol: [b / a - 1 for a, b in zip(values, values[1:])] for symbol, values in windows.items()}
        signals: list[RankedAssetSignal] = []
        for symbol in risky:
            correlations: list[float] = []
            left = returns[symbol]
            for other in risky:
                if other == symbol:
                    continue
                right = returns[other]
                denom = math.sqrt(covariance(left, left) * covariance(right, right))
                correlations.append(covariance(left, right) / denom if denom > 0 else 0.0)
            history = [series[symbol][day] for day in all_common[current_index - int(config["trend_moving_average_days"]) + 1:current_index + 1]]
            signals.append(RankedAssetSignal(
                ticker=symbol, momentum=windows[symbol][-1] / windows[symbol][0] - 1,
                volatility=statistics.stdev(left) * math.sqrt(252),
                average_correlation=statistics.fmean(correlations),
                trend_positive=windows[symbol][-1] > statistics.fmean(history),
            ))
        weights = ranked_asset_allocation(signals, top_n=int(config["top_n"]))
        turnover = sum(abs(weights.get(asset, 0.0) - previous_weights.get(asset, 0.0)) for asset in set(weights) | set(previous_weights)) / 2
        period_returns = {symbol: series[symbol][following] / series[symbol][current] - 1 for symbol in required}
        gross = sum(weight * (period_returns[str(config["cash_asset"])] if asset == "CASH" else period_returns[asset]) for asset, weight in weights.items())
        net = gross - turnover * cost_rate
        baseline = statistics.fmean(period_returns[symbol] for symbol in risky)
        strategy_returns.append(net)
        baseline_returns.append(baseline)
        audit.append({"decision_date": current, "realization_date": following, "weights": weights,
                      "turnover": turnover, "gross_return": gross, "net_return": net, "baseline_return": baseline})
        previous_weights = weights
    if not strategy_returns:
        return {"status": "BLOCKED", "reason": "no eligible evaluation periods"}
    strategy = metrics(strategy_returns, 12)
    baseline = metrics(baseline_returns, 12)
    passed = strategy["sharpe_zero_rf"] > baseline["sharpe_zero_rf"] and strategy["calmar"] > baseline["calmar"]
    return {"status": "WORKING" if passed else "REJECTED", "strategy": strategy, "baseline": baseline,
            "periods": audit, "gate": "net Sharpe and Calmar both exceed equal-weight proxy",
            "literal_replication_status": "BLOCKED", "literal_replication_reason": config["literal_replication_gate"]}


def run_kelly(config: dict[str, object]) -> dict[str, object]:
    rows = read_csv(ROOT / config["source_returns"])
    training = [float(row["net_return"]) for row in rows if row["realization_date"] <= "2020-12-31"]
    test = [float(row["net_return"]) for row in rows if row["decision_date"] >= "2021-01-01"]
    mean, variance = statistics.fmean(training), statistics.variance(training)
    weight = constrained_fractional_kelly(
        [mean], [[variance]], fraction=float(config["fraction"]),
        maximum_weights=[float(config["maximum_sleeve_weight"])], maximum_gross=float(config["maximum_gross"]),
    )[0]
    sized = [weight * value for value in test]
    sized_metrics, base_metrics = metrics(sized, 52), metrics(test, 52)
    passed = (sized_metrics["annual_return"] > base_metrics["annual_return"] and
              sized_metrics["max_drawdown"] >= base_metrics["max_drawdown"] - 0.02)
    return {"status": "WORKING" if passed else "REJECTED", "training_end": "2020-12-31",
            "locked_test_start": "2021-01-01", "quarter_kelly_weight": weight,
            "sized": sized_metrics, "unsized": base_metrics,
            "reason": "Kelly cannot create edge; it only sizes the frozen source strategy"}


def run_raam_robustness(config: dict[str, object], prices: dict[str, list[DailyBar]], frozen: dict[str, object]) -> dict[str, object]:
    variants: list[dict[str, object]] = []
    matrices: list[list[float]] = []
    differentials: list[list[float]] = []
    frozen_returns = [float(row["net_return"]) for row in frozen["periods"]]
    for lookback in (63, 84, 105):
        for top_n in (4, 5, 6):
            for cost in (0, 10, 25):
                candidate = dict(config)
                candidate.update({"lookback_trading_days": lookback, "top_n": top_n, "cost_bps_one_way": cost})
                result = run_raam(candidate, prices)
                if "periods" not in result:
                    continue
                trial = [float(row["net_return"]) for row in result["periods"]]
                baseline = [float(row["baseline_return"]) for row in result["periods"]]
                matrices.append(trial)
                differentials.append([left - right for left, right in zip(trial, baseline)])
                variants.append({"lookback": lookback, "top_n": top_n, "cost_bps_one_way": cost,
                                 "status": result["status"], "sharpe": result["strategy"]["sharpe_zero_rf"],
                                 "calmar": result["strategy"]["calmar"], "annual_return": result["strategy"]["annual_return"]})
    sharpes = [float(item["sharpe"]) for item in variants]
    without_best_five = list(frozen_returns)
    for index in sorted(range(len(without_best_five)), key=lambda idx: without_best_five[idx], reverse=True)[:5]:
        without_best_five[index] = 0.0
    return {
        "variants": variants,
        "variant_count": len(variants),
        "frozen_gate_pass_share": sum(item["status"] == "WORKING" for item in variants) / len(variants),
        "block_bootstrap": block_bootstrap_intervals(
            frozen_returns, seed=20260823, samples=1000, block_size=6, periods_per_year=12
        ),
        "deflated_sharpe": deflated_sharpe_ratio(frozen_returns, trial_sharpes=sharpes, periods_per_year=12),
        "probability_of_backtest_overfitting": probability_of_backtest_overfitting(matrices, folds=8, periods_per_year=12),
        "white_reality_check": white_reality_check_pvalue(differentials, block_size=6, replicates=1000, seed=20260823),
        "remove_best_five_months": metrics(without_best_five, 12),
        "interpretation": "Diagnostics include every 3x3x3 nearby variant; they cannot upgrade the retrospective proxy to proven alpha.",
    }


def run_trial_statistics(config: dict[str, object]) -> dict[str, object]:
    ic_rows = read_csv(ROOT / config["rank_ic_source"])
    ic = information_coefficient_ratio([float(row["rank_ic"]) for row in ic_rows], periods_per_year=int(config["rank_ic_periods_per_year"]))
    leaderboard = read_csv(ROOT / "evidence" / "research_lab_batch_01" / "leaderboard.csv")
    trial_sharpes = [float(row["development_sharpe_zero_rf"]) for row in leaderboard]
    best = max(leaderboard, key=lambda row: float(row["development_selection_score"]))
    walk = read_csv(ROOT / "evidence" / "research_lab_batch_01" / "walk_forward_returns.csv")
    selected_returns = [float(row["net_return"]) for row in walk]
    dsr = deflated_sharpe_ratio(selected_returns, trial_sharpes=trial_sharpes, periods_per_year=52)
    psr = probabilistic_sharpe_ratio(selected_returns, periods_per_year=52)
    return {"icir": ic, "probabilistic_sharpe_probability": psr, "deflated_sharpe": dsr,
            "selected_development_experiment": best["experiment_id"],
            "pbo_status": "BLOCKED", "pbo_reason": "batch 01 preserved aggregate metrics, not aligned returns for every one of 288 trials",
            "white_reality_check_status": "BLOCKED", "white_reality_check_reason": "same missing per-trial aligned return matrix",
            "interpretation": "retrospective diagnostics only; no promotion from one statistic"}


def blocked_rows() -> list[dict[str, str]]:
    return [
        {"idea": "First 5-minute candle / 12 EMA / ATR", "status": "BLOCKED", "headline": "Causal simulator and tests complete", "reason": "No PIT one-minute/NBBO dataset"},
        {"idea": "Options-vs-stock disagreement", "status": "BLOCKED", "headline": "Put-call-parity feature contract complete", "reason": "No OPRA-quality PIT quotes, dividends, or trade signs"},
        {"idea": "Politician/influencer delayed signal", "status": "BLOCKED", "headline": "Public-time gate complete", "reason": "No complete timestamped all-person/archive dataset"},
        {"idea": "Indonesia market-neutral pairs", "status": "BLOCKED", "headline": "Existing causal pair engine retained", "reason": "Short-sale financing, borrow inventory, and cost history unavailable"},
        {"idea": "Derivatives execution", "status": "BLOCKED", "headline": "Research features allowed; trading disabled", "reason": "Margin, Greeks, expiry, assignment and settlement oracle absent"},
        {"idea": "NuScale/SMR thematic sleeve", "status": "RESEARCH_ONLY", "headline": "Scenario/watchlist candidate, not systematic alpha", "reason": "Binary commercial milestones and dilution; no frozen quantitative edge"},
        {"idea": "Copy famous traders", "status": "REJECTED", "headline": "Automatic copying prohibited", "reason": "Reporting delays, selection bias, promotion risk; feature-only research allowed"},
    ]


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    prices, snapshot = load_prices()
    overnight, scoreboard = run_overnight(config["overnight"], prices)
    raam = run_raam(config["raam_proxy"], prices)
    if "periods" in raam:
        raam["frozen_gate_status"] = raam["status"]
        raam["robustness"] = run_raam_robustness(config["raam_proxy"], prices, raam)
        reality = raam["robustness"]["white_reality_check"]
        if float(reality["observed_best_mean"]) <= 0.0 or float(reality["pvalue"]) >= 0.05:
            raam["status"] = "REJECTED"
            raam["promotion_reason"] = "Frozen risk-adjusted gate passed, but the family failed benchmark-relative White Reality Check"
    scoreboard.append({"idea": "RAAM-inspired allocation", "status": raam["status"],
                       "headline": (f"Net Sharpe {raam['strategy']['sharpe_zero_rf']:.2f} vs {raam['baseline']['sharpe_zero_rf']:.2f}" if "strategy" in raam else "Could not run"),
                       "reason": raam.get("promotion_reason", raam.get("gate", raam.get("reason", "")))})
    kelly = run_kelly(config["kelly"])
    scoreboard.append({"idea": "Quarter-Kelly sizing", "status": kelly["status"],
                       "headline": f"Frozen weight {kelly['quarter_kelly_weight']:.1%}", "reason": kelly["reason"]})
    scoreboard.extend(blocked_rows())
    statistics_result = run_trial_statistics(config["icir_and_trial_statistics"])
    scoreboard.extend([
        {"idea": "IC/ICIR research scoring", "status": "WORKING", "headline": f"Annualized ICIR {statistics_result['icir']['annualized_icir']:.2f}", "reason": "Infrastructure metric; not a standalone promotion"},
        {"idea": "Existing ETF pairs strategy", "status": "REJECTED", "headline": "Net Sharpe -0.75 at 50 bps + borrow", "reason": "Random/stale controls won; economics failed after costs"},
        {"idea": "Monte Carlo robustness", "status": "WORKING", "headline": "Existing block/tail engine integrated", "reason": "Risk falsification tool, never proof of future profit"},
    ])
    result = {
        "program": config["program"], "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_enabled": False, "source_snapshot": snapshot["snapshot_id"],
        "source_grade": snapshot.get("historical_simulation_grade"), "config_sha256": digest(CONFIG_PATH),
        "scoreboard": scoreboard, "overnight": overnight, "raam_proxy": raam,
        "kelly": kelly, "trial_statistics": statistics_result,
        "limitations": [
            "All currently available history was visible before this program; results are retrospective, not untouched forward evidence.",
            "The Yahoo snapshot is research-only and not survivorship-safe point-in-time exchange data.",
            "WORKING means the frozen research gate passed, not that live profitability is proven or trading is approved.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (OUTPUT / "scoreboard.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["idea", "status", "headline", "reason"])
        writer.writeheader(); writer.writerows(scoreboard)
    checklist = {"complete": [row["idea"] for row in scoreboard if row["status"] in {"WORKING", "REJECTED", "RESEARCH_ONLY"}],
                 "blocked": [{"idea": row["idea"], "reason": row["reason"]} for row in scoreboard if row["status"] == "BLOCKED"]}
    (OUTPUT / "checklist.json").write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = ["# Quant idea challengers v1", "", f"Data snapshot: `{snapshot['snapshot_id']}`. Live execution remains disabled.", "",
              "| Idea | Outcome | Evidence |", "|---|---:|---|"]
    report += [f"| {row['idea']} | {row['status']} | {row['headline']}; {row['reason']} |" for row in scoreboard]
    report += ["", "## Interpretation", "", "A rejected strategy is a completed experiment, not a missing deliverable. A blocked strategy has its causal contract implemented but lacks data or market access needed for a defensible real test. No retrospective pass is labeled proven alpha."]
    (OUTPUT / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    artifacts = {name: {"sha256": digest(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
                 for name in ("result.json", "scoreboard.csv", "checklist.json", "report.md")}
    (OUTPUT / "run_log.json").write_text(json.dumps({"artifacts": artifacts, "config": str(CONFIG_PATH.relative_to(ROOT)), "snapshot_verified": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "outcomes": {status: sum(row["status"] == status for row in scoreboard) for status in sorted({row["status"] for row in scoreboard})}}, indent=2))


if __name__ == "__main__":
    main()
