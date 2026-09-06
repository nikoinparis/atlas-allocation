#!/usr/bin/env python3
"""Search predeclared non-growth SEC factors on the survivorship-aware panel."""

from __future__ import annotations

import concurrent.futures
import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from systematic_trader.sec_point_in_time import flatten_companyfacts, quarterly_factor_inputs
import run_sec_growth_survivorship_retest_v1 as base

CONFIG = ROOT / "config/sec_independent_fundamental_discovery_v1.json"
PILOT = ROOT / "config/sec_fundamental_pilot_v1.json"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
SUBMISSIONS = ROOT / "data/sec_historical_universe_vintages/20260813T095119Z-sec-historical-filers-v1/qualifying_submissions.csv"
FACT_CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
OUTPUT = ROOT / "evidence/sec_independent_fundamental_discovery_v1"


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.sort_index(axis=0).sort_index(axis=1).to_csv(index=True).encode()).hexdigest()


def build_one(task: tuple) -> pd.DataFrame:
    cik10, filing_records, decisions, canonical, forms = task
    path = FACT_CACHE / f"companyfacts_{cik10}.gz"
    if not path.exists():
        return pd.DataFrame()
    payload = json.loads(gzip.decompress(path.read_bytes()))
    filings = pd.DataFrame(filing_records, columns=["accession", "available_at"])
    filings["available_at"] = pd.to_datetime(filings["available_at"], utc=True, errors="coerce")
    facts = flatten_companyfacts(payload, filings, canonical, forms)
    return quarterly_factor_inputs(facts, decisions, {cik10: cik10})


def build_inputs(membership: pd.DataFrame, decisions: list[pd.Timestamp], pilot: dict) -> pd.DataFrame:
    submissions = pd.read_csv(SUBMISSIONS, dtype={"cik10": str}, usecols=["adsh", "cik10", "available_at"]).rename(columns={"adsh": "accession"})
    submissions["available_at"] = pd.to_datetime(submissions["available_at"], utc=True, errors="coerce")
    targets = sorted(set(membership.loc[membership.tradable_member, "cik10"]))
    records = {cik: submissions[submissions.cik10 == cik][["accession", "available_at"]].astype(str).values.tolist() for cik in targets}
    tasks = [(cik, records[cik], decisions, pilot["canonical_metrics"], pilot["accepted_forms"]) for cik in targets]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for number, result in enumerate(pool.map(build_one, tasks, chunksize=4), 1):
            if not result.empty:
                rows.append(result)
            if number % 100 == 0 or number == len(tasks):
                print(f"factor inputs {number}/{len(tasks)}", flush=True)
    return pd.concat(rows, ignore_index=True)


def enrich(inputs: pd.DataFrame) -> pd.DataFrame:
    result = inputs.copy()
    revenue = pd.to_numeric(result.get("revenue"), errors="coerce").replace(0, np.nan)
    result["cash_conversion_spread"] = (pd.to_numeric(result.get("operating_cash_flow"), errors="coerce") - pd.to_numeric(result.get("net_income"), errors="coerce")) / revenue
    result["decision_time"] = pd.to_datetime(result.decision_time, utc=True)
    change_columns = ["operating_margin", "operating_cash_flow_margin", "free_cash_flow_margin", "equity_to_assets", "debt_to_assets"]
    result = result.sort_values(["cik10", "decision_time"])
    for column in change_columns:
        result[f"{column}_change"] = pd.to_numeric(result.get(column), errors="coerce").groupby(result.cik10).diff()
    return result


def score_families(inputs: pd.DataFrame, membership: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = membership[membership.tradable_member][["decision_at", "cik10", "company_name_as_filed", "sector"]]
    panel = eligible.merge(inputs, left_on=["decision_at", "cik10"], right_on=["decision_time", "cik10"], how="left")
    score_rows, choice_rows = [], []
    for family, spec in config["families"].items():
        signed = [(feature, 1.0) for feature in spec.get("positive", [])] + [(feature, -1.0) for feature in spec.get("negative", [])]
        pieces = []
        for (decision, sector), frame in panel.groupby(["decision_at", "sector"], sort=True):
            matrix = pd.DataFrame(index=frame.index)
            for feature, sign in signed:
                values = pd.to_numeric(frame.get(feature), errors="coerce")
                valid = values.dropna()
                ranked = pd.Series(np.nan, index=frame.index)
                if len(valid) >= 3:
                    ranked.loc[valid.index] = sign * (valid.rank(pct=True, method="average") * 2.0 - 1.0)
                matrix[feature] = ranked
            scored = frame[["decision_at", "cik10", "company_name_as_filed", "sector"]].copy()
            scored["family"] = family
            scored["available_features"] = matrix.notna().sum(axis=1)
            scored["score"] = matrix.mean(axis=1, skipna=True).where(scored.available_features >= int(spec["minimum_features"]))
            pieces.append(scored)
        family_scores = pd.concat(pieces, ignore_index=True)
        score_rows.append(family_scores)
        for decision, frame in family_scores.groupby("decision_at", sort=True):
            usable = frame.dropna(subset=["score"])
            if len(usable) < int(config["minimum_companies_per_decision"]):
                continue
            selected = usable.sort_values(["score", "cik10"], ascending=[False, True]).head(int(config["top_n"]))
            for row in selected.itertuples(index=False):
                choice_rows.append({"family": family, "decision_at": decision, "cik10": row.cik10, "company_name": row.company_name_as_filed, "sector": row.sector, "score": row.score, "available_features": row.available_features, "intended_weight": 1.0 / int(config["top_n"])})
    return pd.concat(score_rows, ignore_index=True), pd.DataFrame(choice_rows)


def correlations(paths: dict[str, pd.DataFrame], benchmark_paths: dict[str, pd.DataFrame], growth: pd.DataFrame) -> pd.DataFrame:
    rows = []
    growth_returns = growth.set_index(pd.to_datetime(growth.Date))["net_return"]
    for family, path in paths.items():
        series = path.net_return
        row = {"family": family, "correlation_growth": series.corr(growth_returns.reindex(series.index))}
        for ticker, benchmark in benchmark_paths.items():
            row[f"correlation_{ticker.lower()}"] = series.corr(benchmark.net_return.reindex(series.index))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--membership", default=str(MEMBERSHIP))
    parser.add_argument("--output-root", default=str(OUTPUT))
    args = parser.parse_args()
    output = Path(args.output_root).resolve()
    config, pilot = json.loads(CONFIG.read_text()), json.loads(PILOT.read_text())
    output.mkdir(parents=True, exist_ok=True)
    membership = pd.read_csv(Path(args.membership), dtype={"cik10": str}, parse_dates=["decision_at"])
    membership["tradable_member"] = membership.tradable_member.astype(bool)
    decisions = sorted(membership.decision_at.unique())
    input_checkpoint = output / "quarterly_factor_inputs.csv"
    if input_checkpoint.exists() and input_checkpoint.stat().st_size > 0:
        inputs = pd.read_csv(input_checkpoint, dtype={"cik10": str}, low_memory=False)
        inputs["decision_time"] = pd.to_datetime(inputs.decision_time, utc=True)
    else:
        inputs = enrich(build_inputs(membership, decisions, pilot))
        inputs.to_csv(input_checkpoint, index=False)
    scores, choices = score_families(inputs, membership, config)
    repeated_scores, repeated_choices = score_families(inputs.copy(), membership.copy(), config)

    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp(config["start_decision"]), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    selected_ciks = sorted(set(choices.cik10))
    weekly = pd.DataFrame(index=weekly_index)
    source_rows = []
    for cik in selected_ciks:
        spec = sources.get(cik)
        if spec:
            source, path = spec
            weekly[cik] = base.read_weekly_price(path, source, weekly_index, terminals.get(cik))
            source_rows.append({"cik10": cik, "price_source": source, "price_file": str(path)})
        else:
            source_rows.append({"cik10": cik, "price_source": None, "price_file": None})
    benchmarks = base.benchmark_weekly(weekly_index)

    performance_rows, event_rows, primary_paths, benchmark_paths = [], [], {}, {}
    for cost in config["cost_bps"]:
        for family, selected in choices.groupby("family"):
            targets = base.build_targets(selected, weekly_index)
            for scenario in ("base", "adverse"):
                path, events = base.simulate(weekly, targets, scenario, float(cost))
                performance_rows.extend(base.metric_rows(family, scenario, int(cost), path))
                events["family"], events["cost_bps"] = family, int(cost)
                event_rows.append(events)
                path.rename_axis("Date").to_csv(output / f"path_{family}__{scenario}__{cost}bps.csv")
                if cost == config["primary_cost_bps"] and scenario == "base":
                    primary_paths[family] = path
        for ticker in config["benchmarks"]:
            path = base.static_benchmark_path(benchmarks[ticker], float(cost))
            performance_rows.extend(base.metric_rows(f"benchmark::{ticker}", "observed", int(cost), path))
            if cost == config["primary_cost_bps"]:
                benchmark_paths[ticker] = path

    performance = pd.DataFrame(performance_rows)
    growth = pd.read_csv(ROOT / "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv")
    corr = correlations(primary_paths, benchmark_paths, growth)
    primary = performance[(performance.cost_bps == config["primary_cost_bps"]) & (performance.scenario == "base")]
    focus = primary[
        primary.window.isin(["full_recent", "trailing_3y", "trailing_2y", "trailing_1y", "ytd"])
        & ~primary.candidate.str.startswith("benchmark::")
    ].rename(columns={"candidate": "family"}).merge(corr, on="family", how="left")
    adverse = performance[(performance.cost_bps == config["primary_cost_bps"]) & (performance.scenario == "adverse") & (performance.window == "full_recent")][["candidate", "cagr"]].rename(columns={"candidate": "family", "cagr": "adverse_full_cagr"})
    focus = focus.merge(adverse, on="family", how="left")
    focus["independence_gate"] = (focus.correlation_growth.abs() < 0.75) & (focus.correlation_spy.abs() < 0.85)
    focus["robustness_gate"] = focus.adverse_full_cagr > 0

    availability_columns = [column for column in inputs if column.endswith("__available_at")]
    availability_pass = all(bool(((pd.to_datetime(inputs[column], utc=True, errors="coerce") < inputs.decision_time) | inputs[column].isna()).all()) for column in availability_columns)
    checks = {
        "availability_strictly_before_decision": availability_pass,
        "deterministic_choices": frame_hash(choices) == frame_hash(repeated_choices),
        "all_reported_choices_have_fixed_top_n": bool(choices.groupby(["family", "decision_at"]).size().eq(config["top_n"]).all()),
        "weights_sum_to_one": bool(choices.groupby(["family", "decision_at"]).intended_weight.sum().sub(1).abs().max() < 1e-12),
        "base_and_adverse_run": True,
    }
    inputs.to_csv(output / "quarterly_factor_inputs.csv", index=False)
    scores.to_csv(output / "factor_scores.csv", index=False)
    choices.to_csv(output / "portfolio_choices.csv", index=False)
    pd.DataFrame(source_rows).to_csv(output / "selected_price_sources.csv", index=False)
    pd.concat(event_rows, ignore_index=True).to_csv(output / "rebalance_events.csv", index=False)
    performance.to_csv(output / "performance.csv", index=False)
    corr.to_csv(output / "return_correlations.csv", index=False)
    focus.to_csv(output / "primary_focus.csv", index=False)
    best_recent = focus[focus.window == "trailing_1y"].sort_values("cagr", ascending=False).iloc[0]
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "families": list(config["families"]), "decisions": int(choices.decision_at.nunique()),
        "input_ciks": int(inputs.cik10.nunique()), "selected_unique_ciks": int(choices.cik10.nunique()),
        "best_trailing_1y_family": best_recent.family, "best_trailing_1y_cagr": float(best_recent.cagr),
        "best_trailing_1y_sharpe": float(best_recent.sharpe_zero_rf), "best_trailing_1y_drawdown": float(best_recent.max_drawdown),
        "best_correlation_growth": float(best_recent.correlation_growth), "best_adverse_full_cagr": float(best_recent.adverse_full_cagr),
        "all_validation_checks_passed": bool(all(checks.values())), "validation_checks": checks,
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (output / "report.md").write_text(
        "# Independent SEC fundamental discovery v1\n\n"
        f"Five predeclared non-growth families were tested on {result['decisions']} point-in-time decisions with a fixed top-{config['top_n']} portfolio. "
        f"The strongest trailing-year result was **{best_recent.family}** at **{best_recent.cagr:.2%} CAGR**, **{best_recent.sharpe_zero_rf:.3f} Sharpe**, and **{best_recent.max_drawdown:.2%} drawdown**. "
        f"Its weekly correlation with the frozen SEC growth sleeve was **{best_recent.correlation_growth:.3f}**, and its adverse full-period CAGR was **{best_recent.adverse_full_cagr:.2%}**.\n\n"
        "This is a discovery result, not a promotion. Valuation was excluded because the available adjusted-price/share-count combination is not corporate-action consistent.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
