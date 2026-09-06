#!/usr/bin/env python3
"""Retest the frozen SEC growth rule on the recent survivorship-aware stock panel."""

from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from systematic_trader.sec_point_in_time import flatten_companyfacts, quarterly_factor_inputs

CONFIG_PATH = ROOT / "config/sec_growth_survivorship_retest_v1.json"
PILOT_CONFIG = ROOT / "config/sec_fundamental_pilot_v1.json"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
def _latest_submissions() -> Path:
    """Newest narrow filer vintage; the pinned 2026-08-13 one predates the 2026Q2 archive."""
    values = sorted(ROOT.glob("data/sec_historical_universe_vintages/*-sec-historical-filers-v1"))
    if not values:
        raise RuntimeError("no narrow SEC universe vintage found")
    return values[-1] / "qualifying_submissions.csv"


SUBMISSIONS = _latest_submissions()
FACT_CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
TIINGO_AUDIT = ROOT / "evidence/tiingo_delisted_authenticated_probe_v1/candidate_audit.csv"
TIINGO_TERMINALS = ROOT / "evidence/tiingo_terminal_outcomes_v1/terminal_outcomes.csv"
SEC_TERMINALS = ROOT / "evidence/sec_terminal_membership_v1/sec_terminal_membership.csv"
RECOVERED_AUDIT = ROOT / "evidence/sec_recovered_price_probe_v1/recovered_symbol_price_audit.csv"
RECOVERED_RESULT = ROOT / "evidence/sec_recovered_price_probe_v1/result.json"
BENCHMARK_PRICES = ROOT / "data/sec_pilot_price_vintages/20260813T070329Z-sec-pilot-prices/prices.csv"
OUTPUT = ROOT / "evidence/sec_growth_survivorship_retest_v1"


def project_path(value: object) -> Path:
    path = Path(str(value))
    for prefix in ("/project/", "/workspace/2.0/"):
        if str(path).startswith(prefix):
            return ROOT / path.relative_to(prefix)
    return path


def frame_hash(frame: pd.DataFrame) -> str:
    payload = frame.sort_index(axis=0).sort_index(axis=1).to_csv(index=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def standard_metrics(path: pd.DataFrame) -> dict:
    returns = pd.to_numeric(path["net_return"], errors="coerce").dropna()
    turnover = pd.to_numeric(path["turnover"], errors="coerce").reindex(returns.index).fillna(0.0)
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    annual = float(returns.mean() * 52.0)
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    downside = float(np.sqrt(returns.clip(upper=0.0).pow(2).mean()) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe_zero_rf": annual / volatility if volatility else 0.0,
        "sortino_zero_target": annual / downside if downside else 0.0,
        "max_drawdown": float(drawdown.min()),
        "annual_one_way_turnover": float(turnover.mean() * 52.0),
    }


def build_one_factor_input(task: tuple) -> pd.DataFrame:
    cik10, filing_records, decisions, canonical, accepted_forms = task
    path = FACT_CACHE / f"companyfacts_{cik10}.gz"
    if not path.exists():
        return pd.DataFrame()
    payload = json.loads(gzip.decompress(path.read_bytes()))
    filings = pd.DataFrame(filing_records, columns=["accession", "available_at"])
    filings["available_at"] = pd.to_datetime(filings["available_at"], utc=True, errors="coerce")
    facts = flatten_companyfacts(payload, filings, canonical, accepted_forms)
    return quarterly_factor_inputs(facts, decisions, {cik10: cik10})


def build_factor_inputs(membership: pd.DataFrame, decisions: list[pd.Timestamp], pilot: dict) -> pd.DataFrame:
    submissions = pd.read_csv(SUBMISSIONS, dtype={"cik10": str}, usecols=["adsh", "cik10", "available_at"])
    submissions = submissions.rename(columns={"adsh": "accession"})
    submissions["available_at"] = pd.to_datetime(submissions["available_at"], utc=True, errors="coerce")
    canonical = {key: pilot["canonical_metrics"][key] for key in ("revenue", "net_income", "operating_cash_flow")}
    targets = sorted(set(membership.loc[membership["tradable_member"], "cik10"]))
    filing_records = {
        cik10: submissions[submissions["cik10"] == cik10][["accession", "available_at"]].astype(str).values.tolist()
        for cik10 in targets
    }
    tasks = [(cik10, filing_records[cik10], decisions, canonical, pilot["accepted_forms"]) for cik10 in targets]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(build_one_factor_input, task) for task in tasks]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            inputs = future.result()
            if not inputs.empty:
                rows.append(inputs)
            if index % 100 == 0 or index == len(targets):
                print(f"factor inputs {index}/{len(targets)}", flush=True)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def score_growth(inputs: pd.DataFrame, membership: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = inputs.drop(columns=["ticker"], errors="ignore").copy()
    panel["decision_at"] = pd.to_datetime(panel["decision_time"], utc=True)
    eligible = membership[membership["tradable_member"]][["decision_at", "cik10", "company_name_as_filed", "sector"]]
    panel = eligible.merge(panel, on=["decision_at", "cik10"], how="left")
    features = config["positive_features"]
    scored = []
    for (decision, sector), frame in panel.groupby(["decision_at", "sector"], sort=True):
        frame = frame.copy()
        parts = []
        for feature in features:
            values = pd.to_numeric(frame.get(feature), errors="coerce")
            ranks = pd.Series(np.nan, index=frame.index, dtype=float)
            valid = values.dropna()
            if len(valid) >= 3:
                ranks.loc[valid.index] = valid.rank(pct=True, method="average") * 2.0 - 1.0
            parts.append(ranks.rename(feature))
        matrix = pd.concat(parts, axis=1)
        frame["score"] = matrix.mean(axis=1, skipna=True).where(
            matrix.notna().sum(axis=1) >= int(config["minimum_available_features"])
        )
        frame["available_features"] = matrix.notna().sum(axis=1)
        scored.append(frame)
    scores = pd.concat(scored, ignore_index=True)
    choices = []
    for decision, frame in scores.groupby("decision_at", sort=True):
        usable = frame.dropna(subset=["score"])
        if len(usable) < int(config["minimum_companies_per_decision"]):
            continue
        selected = usable.sort_values(["score", "cik10"], ascending=[False, True]).head(int(config["top_n"]))
        for row in selected.itertuples(index=False):
            choices.append({
                "decision_at": decision, "cik10": row.cik10,
                "company_name": row.company_name_as_filed, "sector": row.sector,
                "score": float(row.score), "available_features": int(row.available_features),
                "intended_weight": 1.0 / int(config["top_n"]),
            })
    return scores, pd.DataFrame(choices)


def price_sources() -> dict[str, tuple[str, Path]]:
    sources: dict[str, tuple[str, Path]] = {}
    for result_path in sorted((ROOT / "data/yahoo_recent_current_sec_price_vintages").glob("*/price_results.csv")):
        frame = pd.read_csv(result_path, dtype={"cik10": str})
        for row in frame[frame["status"] == "ok"].to_dict("records"):
            sources[str(row["cik10"])] = ("yahoo_current_sec", result_path.parent / row["history_file"])
    recovered_root = project_path(json.loads(RECOVERED_RESULT.read_text())["price_vintage"])
    recovered = pd.read_csv(RECOVERED_AUDIT, dtype={"cik10": str})
    for row in recovered[recovered["history_overlaps_eligible_interval"].astype(bool)].to_dict("records"):
        sources.setdefault(str(row["cik10"]), ("yahoo_recovered_former", recovered_root / row["history_file"]))
    tiingo = pd.read_csv(TIINGO_AUDIT, dtype={"cik10": str})
    valid = {"validated_history_through_last_decision", "validated_early_delisting_needs_terminal_audit"}
    for row in tiingo[tiingo["audit_status"].isin(valid)].to_dict("records"):
        sources[str(row["cik10"])] = ("tiingo_identity_validated", project_path(row["price_file"]))
    return sources


def terminal_dates() -> dict[str, pd.Timestamp]:
    result: dict[str, pd.Timestamp] = {}
    sec = pd.read_csv(SEC_TERMINALS, dtype={"cik10": str})
    for row in sec.to_dict("records"):
        result[str(row["cik10"])] = pd.Timestamp(row["sec_terminal_date"])
    tiingo = pd.read_csv(TIINGO_TERMINALS, dtype={"cik10": str})
    for row in tiingo[tiingo["terminal_reason"] == "merger_or_acquisition_completion"].to_dict("records"):
        cik = str(row["cik10"])
        value = pd.Timestamp(row["last_price_date"])
        result[cik] = min(value, result.get(cik, value))
    return result


def read_weekly_price(path: Path, source: str, index: pd.DatetimeIndex, terminal: pd.Timestamp | None) -> pd.Series:
    frame = pd.read_csv(path, compression="gzip")
    if source.startswith("yahoo"):
        dates = pd.to_datetime(frame["Date"], errors="coerce")
        values = pd.to_numeric(frame["Adj Close"], errors="coerce")
    else:
        dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
        values = pd.to_numeric(frame["adjClose"], errors="coerce")
    daily = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
    daily = daily[~daily.index.duplicated(keep="last")]
    weekly = daily.resample("W-FRI").last().reindex(index)
    if terminal is not None and weekly.notna().any():
        last = weekly.last_valid_index()
        if last is not None:
            weekly.loc[last:] = weekly.loc[last:].ffill()
    return weekly


def benchmark_weekly(index: pd.DatetimeIndex) -> pd.DataFrame:
    raw = pd.read_csv(BENCHMARK_PRICES)
    raw["observation_date"] = pd.to_datetime(raw["observation_date"], errors="coerce")
    raw["adjusted_close"] = pd.to_numeric(raw["adjusted_close"], errors="coerce")
    panel = raw[raw["ticker"].isin(["SPY", "XLK", "XLE"])].pivot(
        index="observation_date", columns="ticker", values="adjusted_close"
    ).sort_index()
    return panel.resample("W-FRI").last().reindex(index).ffill()


def build_targets(choices: pd.DataFrame, index: pd.DatetimeIndex) -> dict[pd.Timestamp, list[str]]:
    targets = {}
    for decision, frame in choices.groupby("decision_at", sort=True):
        later = index[index > pd.Timestamp(decision).tz_localize(None)]
        if len(later):
            targets[later[0]] = frame.sort_values("cik10")["cik10"].tolist()
    return targets


def simulate(
    prices: pd.DataFrame, targets: dict[pd.Timestamp, list[str]], scenario: str, cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = {"cash::USD": 1.0}
    rows, events = [], []
    previous_total = 1.0
    for offset, date in enumerate(prices.index[:-1]):
        total_before = sum(positions.values())
        turnover = 0.0
        cost = 0.0
        adverse_loss = 0.0
        if date in targets:
            selected = targets[date]
            intended = 1.0 / len(selected)
            available = [cik for cik in selected if cik in prices and pd.notna(prices.at[date, cik])]
            missing = [cik for cik in selected if cik not in available]
            preweights = {key: value / total_before for key, value in positions.items()} if total_before else {"cash::USD": 1.0}
            target_weights = {cik: intended for cik in available}
            ghost = {f"missing::{cik}": intended for cik in missing} if scenario == "adverse" else {}
            target_weights["cash::USD"] = intended * len(missing) if scenario == "base" else 0.0
            comparison = set(preweights) | set(target_weights) | set(ghost)
            turnover = 0.5 * sum(abs(target_weights.get(key, ghost.get(key, 0.0)) - preweights.get(key, 0.0)) for key in comparison)
            cost = total_before * turnover * float(cost_bps) / 10000.0
            deployable = total_before - cost
            positions = {key: deployable * weight for key, weight in target_weights.items() if weight > 0}
            if scenario == "adverse" and missing:
                adverse_loss = deployable * intended * len(missing)
            events.append({
                "effective_date": date, "scenario": scenario, "selected": len(selected),
                "available": len(available), "missing": len(missing),
                "missing_ciks": "|".join(missing), "turnover": turnover,
                "cost": cost, "adverse_loss": adverse_loss,
            })
        next_date = prices.index[offset + 1]
        next_positions = {}
        transition_loss = 0.0
        for asset, value in positions.items():
            if asset == "cash::USD":
                next_positions[asset] = next_positions.get(asset, 0.0) + value
                continue
            start = prices.at[date, asset]
            end = prices.at[next_date, asset]
            if pd.notna(start) and pd.notna(end) and float(start) != 0:
                next_positions[asset] = value * float(end) / float(start)
            elif scenario == "base":
                next_positions["cash::USD"] = next_positions.get("cash::USD", 0.0) + value
            else:
                transition_loss += value
        positions = next_positions
        total_after = sum(positions.values())
        net_return = total_after / total_before - 1.0 if total_before else 0.0
        gross_return = (total_after + cost + adverse_loss + transition_loss) / total_before - 1.0 if total_before else 0.0
        rows.append({
            "Date": date, "gross_return": gross_return, "net_return": net_return,
            "turnover": turnover, "cost": cost / total_before if total_before else 0.0,
            "adverse_loss": (adverse_loss + transition_loss) / total_before if total_before else 0.0,
            "wealth": total_after,
        })
        previous_total = total_after
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path["wealth"] / path["wealth"].cummax() - 1.0
    return path, pd.DataFrame(events)


def static_benchmark_path(series: pd.Series, cost_bps: float) -> pd.DataFrame:
    returns = series.pct_change().shift(-1).iloc[:-1].fillna(0.0)
    returns.iloc[0] -= float(cost_bps) / 10000.0
    wealth = (1.0 + returns).cumprod()
    return pd.DataFrame({
        "gross_return": returns + pd.Series([float(cost_bps) / 10000.0] + [0.0] * (len(returns) - 1), index=returns.index),
        "net_return": returns,
        "turnover": pd.Series([1.0] + [0.0] * (len(returns) - 1), index=returns.index),
        "cost": pd.Series([float(cost_bps) / 10000.0] + [0.0] * (len(returns) - 1), index=returns.index),
        "wealth": wealth,
        "drawdown": wealth / wealth.cummax() - 1.0,
    })


def metric_rows(name: str, scenario: str, cost: int, path: pd.DataFrame) -> list[dict]:
    end = path.index.max()
    windows = {
        "full_recent": path,
        "since_pilot_holdout_start": path.loc[path.index >= pd.Timestamp("2023-08-04")],
        "trailing_3y": path.loc[path.index >= end - pd.DateOffset(years=3)],
        "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)],
        "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)],
        "ytd": path.loc[path.index.year == end.year],
    }
    rows = []
    for window, sample in windows.items():
        if len(sample) < 2:
            continue
        values = standard_metrics(sample)
        returns = sample["net_return"].dropna()
        values.update({
            "total_return": float((1.0 + returns).prod() - 1.0),
            "annual_volatility": float(returns.std(ddof=1) * np.sqrt(52.0)),
            "win_rate": float((returns > 0).mean()),
            "best_week": float(returns.max()), "worst_week": float(returns.min()),
        })
        rows.append({"candidate": name, "scenario": scenario, "cost_bps": cost, "window": window, **values})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--membership", default=str(MEMBERSHIP))
    parser.add_argument("--output-root", default=str(OUTPUT))
    args = parser.parse_args()
    output = Path(args.output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_PATH.read_text())
    pilot = json.loads(PILOT_CONFIG.read_text())
    membership = pd.read_csv(Path(args.membership), dtype={"cik10": str}, parse_dates=["decision_at"])
    membership["tradable_member"] = membership["tradable_member"].astype(bool)
    decisions = sorted(membership["decision_at"].unique())
    inputs = build_factor_inputs(membership, decisions, pilot)
    scores, choices = score_growth(inputs, membership, config)
    if choices.groupby("decision_at").size().min() != int(config["top_n"]):
        raise RuntimeError("not every decision produced the frozen top-N portfolio")

    benchmark_raw = pd.read_csv(BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw["observation_date"]).max()
    start = pd.Timestamp(config["start_decision"])
    weekly_index = pd.date_range(start=start, end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    targets = build_targets(choices, weekly_index)
    selected_ciks = sorted(set(choices["cik10"]))
    sources = price_sources()
    terminals = terminal_dates()
    weekly = pd.DataFrame(index=weekly_index)
    source_rows = []
    for cik in selected_ciks:
        spec = sources.get(cik)
        if spec is None:
            source_rows.append({"cik10": cik, "price_source": None, "price_file": None})
            continue
        source, path = spec
        weekly[cik] = read_weekly_price(path, source, weekly_index, terminals.get(cik))
        source_rows.append({"cik10": cik, "price_source": source, "price_file": str(path)})
    benchmarks = benchmark_weekly(weekly_index)

    performance_rows, all_events = [], []
    paths = {}
    for cost in config["cost_bps"]:
        for scenario in ("base", "adverse"):
            path, events = simulate(weekly, targets, scenario, float(cost))
            key = f"growth::{scenario}::{cost}bps"
            paths[key] = path
            performance_rows.extend(metric_rows("growth", scenario, int(cost), path))
            events["cost_bps"] = int(cost)
            all_events.append(events)
        for ticker in config["benchmarks"]:
            path = static_benchmark_path(benchmarks[ticker], float(cost))
            key = f"benchmark::{ticker}::{cost}bps"
            paths[key] = path
            performance_rows.extend(metric_rows(f"benchmark::{ticker}", "observed", int(cost), path))

    performance = pd.DataFrame(performance_rows)
    events = pd.concat(all_events, ignore_index=True)
    selected_inputs = choices.merge(inputs, left_on=["decision_at", "cik10"], right_on=["decision_time", "cik10"], how="left")
    availability_columns = [column for column in selected_inputs if column.endswith("__available_at")]
    availability_pass = True
    for column in availability_columns:
        available = pd.to_datetime(selected_inputs[column], utc=True, errors="coerce")
        availability_pass &= bool(((available < pd.to_datetime(selected_inputs["decision_at"], utc=True)) | available.isna()).all())
    repeated_scores, repeated_choices = score_growth(inputs.copy(), membership.copy(), config)
    determinism_pass = frame_hash(choices) == frame_hash(repeated_choices)
    prefix_rows = []
    for cutoff in decisions[3::3]:
        _, prefix_choices = score_growth(
            inputs[pd.to_datetime(inputs["decision_time"], utc=True) <= cutoff],
            membership[membership["decision_at"] <= cutoff], config,
        )
        expected = choices[choices["decision_at"] <= cutoff].reset_index(drop=True)
        actual = prefix_choices.reset_index(drop=True)
        prefix_rows.append({"cutoff": cutoff, "prefix_match": frame_hash(expected) == frame_hash(actual)})
    prefix = pd.DataFrame(prefix_rows)
    cost_monotonic = True
    for scenario in ("base", "adverse"):
        full = performance[(performance.candidate == "growth") & (performance.scenario == scenario) & (performance.window == "full_recent")]
        ordered = full.set_index("cost_bps")["cagr"]
        cost_monotonic &= bool(ordered.loc[50] >= ordered.loc[100] >= ordered.loc[200])

    primary = performance[(performance.cost_bps == int(config["primary_cost_bps"])) & (performance.window == "full_recent")]
    base = primary[(primary.candidate == "growth") & (primary.scenario == "base")].iloc[0]
    adverse = primary[(primary.candidate == "growth") & (primary.scenario == "adverse")].iloc[0]
    spy = primary[primary.candidate == "benchmark::SPY"].iloc[0]
    pilot_same_window = performance[
        (performance.candidate == "growth") & (performance.scenario == "base")
        & (performance.cost_bps == int(config["primary_cost_bps"]))
        & (performance.window == "since_pilot_holdout_start")
    ].iloc[0]
    missing_events = events[(events.scenario == "base") & (events.cost_bps == int(config["primary_cost_bps"])) & (events.missing > 0)]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    inputs.to_csv(output / "quarterly_factor_inputs.csv", index=False)
    scores.to_csv(output / "growth_scores.csv", index=False)
    choices.to_csv(output / "portfolio_choices.csv", index=False)
    pd.DataFrame(source_rows).to_csv(output / "selected_price_sources.csv", index=False)
    events.to_csv(output / "rebalance_events.csv", index=False)
    performance.to_csv(output / "performance.csv", index=False)
    prefix.to_csv(output / "prefix_invariance.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(output / f"path_{key.replace('::', '__')}.csv")
    checks = {
        "availability_strictly_before_decision": availability_pass,
        "deterministic_choices": determinism_pass,
        "prefix_invariance": bool(prefix["prefix_match"].all()) if len(prefix) else True,
        "all_decisions_have_top_n": bool(choices.groupby("decision_at").size().eq(int(config["top_n"])).all()),
        "intended_weights_sum_to_one": bool(choices.groupby("decision_at")["intended_weight"].sum().sub(1.0).abs().max() <= 1e-12),
        "cost_monotonic": cost_monotonic,
        "base_and_adverse_paths_run": True,
    }
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decisions": int(choices["decision_at"].nunique()),
        "factor_input_ciks": int(inputs["cik10"].nunique()),
        "selected_unique_ciks": int(choices["cik10"].nunique()),
        "selected_missing_rebalances": int(len(missing_events)),
        "base_full_recent_50bps_cagr": float(base.cagr),
        "base_full_recent_50bps_sharpe": float(base.sharpe_zero_rf),
        "base_full_recent_50bps_drawdown": float(base.max_drawdown),
        "adverse_full_recent_50bps_cagr": float(adverse.cagr),
        "adverse_full_recent_50bps_sharpe": float(adverse.sharpe_zero_rf),
        "adverse_full_recent_50bps_drawdown": float(adverse.max_drawdown),
        "spy_full_recent_50bps_cagr": float(spy.cagr),
        "base_since_pilot_start_50bps_cagr": float(pilot_same_window.cagr),
        "old_survivor_pilot_since_start_50bps_cagr": 0.3613542214847836,
        "all_validation_checks_passed": bool(all(checks.values())),
        "validation_checks": checks,
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False,
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (output / "report.md").write_text(
        "# SEC growth survivorship-aware retest v1\n\n"
        f"The unchanged growth rule was tested across **{result['decisions']}** point-in-time quarterly decisions. "
        f"At 50-bps costs, the base scenario produced **{base.cagr:.2%} CAGR**, **{base.sharpe_zero_rf:.3f} Sharpe**, "
        f"and **{base.max_drawdown:.2%} maximum drawdown**. The mandatory adverse missing-company scenario "
        f"produced **{adverse.cagr:.2%} CAGR**, **{adverse.sharpe_zero_rf:.3f} Sharpe**, and "
        f"**{adverse.max_drawdown:.2%} drawdown**. SPY returned **{spy.cagr:.2%} CAGR** on the same weekly span.\n\n"
        f"From the old pilot's holdout start, the survivorship-aware base CAGR was **{pilot_same_window.cagr:.2%}** "
        "versus the old 20-survivor pilot's **36.14%**. The old pilot is not used as a valid benchmark claim. "
        "No strategy is automatically promoted; the paired result and validation checks determine the next decision.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
