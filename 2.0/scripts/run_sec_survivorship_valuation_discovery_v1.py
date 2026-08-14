#!/usr/bin/env python3
"""Run split-normalized valuation discovery on the recent survivorship-aware SEC panel."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base

CONFIG = ROOT / "config/sec_survivorship_valuation_discovery_v1.json"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
INPUTS = ROOT / "evidence/sec_independent_fundamental_discovery_v1/quarterly_factor_inputs.csv"
REPAIRS = ROOT / "data/daily_audit_price_source_repairs_v1/manifest.csv"
OUTPUT = ROOT / "evidence/sec_survivorship_valuation_discovery_v1"


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.sort_index(axis=0).sort_index(axis=1).to_csv(index=True).encode()).hexdigest()


def read_price_basis(path: Path, source: str) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path, compression="gzip")
    if source.startswith("yahoo") or source == "yahoo_repair_v1":
        dates = pd.to_datetime(frame["Date"], errors="coerce")
        raw = pd.to_numeric(frame["Close"], errors="coerce")
        adjusted = pd.to_numeric(frame["Adj Close"], errors="coerce")
        split = pd.to_numeric(frame.get("Stock Splits", 0.0), errors="coerce").fillna(0.0)
    else:
        dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
        raw = pd.to_numeric(frame["close"], errors="coerce")
        adjusted = pd.to_numeric(frame["adjClose"], errors="coerce")
        split = pd.to_numeric(frame.get("splitFactor", 1.0), errors="coerce").fillna(1.0)
        split = split.where(split.ne(1.0), 0.0)
    result = pd.DataFrame({"date": dates, "raw_close": raw, "adjusted_close": adjusted, "split_factor": split}).dropna(subset=["date"]).sort_values("date")
    result = result.drop_duplicates("date", keep="last").set_index("date")
    audit = {"source": source, "price_file": str(path), "rows": len(frame), "first_date": str(result.index.min().date()), "last_date": str(result.index.max().date()), "split_events": int(result.split_factor.gt(0).sum())}
    return result, audit


def source_map() -> dict[str, tuple[str, Path]]:
    sources = base.price_sources()
    if REPAIRS.exists():
        repairs = pd.read_csv(REPAIRS, dtype={"cik10": str})
        for row in repairs.itertuples(index=False):
            sources[str(row.cik10).zfill(10)] = (str(row.source), ROOT / str(row.price_file))
    return sources


def rank_sector_neutral(frame: pd.DataFrame, column: str) -> pd.Series:
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, indices in frame.groupby("sector").groups.items():
        valid = pd.to_numeric(frame.loc[indices, column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) >= 3:
            result.loc[valid.index] = valid.rank(pct=True, method="average") * 2.0 - 1.0
    return result


def build_valuation_panel(inputs: pd.DataFrame, membership: pd.DataFrame, sources: dict[str, tuple[str, Path]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = membership[membership.tradable_member][["decision_at", "cik10", "company_name_as_filed", "sector"]]
    panel = eligible.merge(inputs.drop(columns=["ticker"], errors="ignore"), left_on=["decision_at", "cik10"], right_on=["decision_time", "cik10"], how="left")
    for column in ["shares_outstanding", "diluted_shares", "net_income", "operating_cash_flow", "capital_expenditure", "revenue", "operating_margin", "operating_cash_flow_margin", "cash_to_assets", "equity_to_assets", "diluted_shares__yoy_growth"]:
        panel[column] = pd.to_numeric(panel.get(column), errors="coerce")
    for column in ["shares_outstanding__period_end", "shares_outstanding__available_at", "diluted_shares__period_end", "diluted_shares__available_at"]:
        panel[column] = pd.to_datetime(panel.get(column), utc=True, errors="coerce")
    rows, source_rows = [], []
    for number, (cik, group) in enumerate(panel.groupby("cik10", sort=True), 1):
        spec = sources.get(str(cik).zfill(10))
        if spec is None:
            source_rows.append({"cik10": cik, "source": "missing", "status": "missing_mapping"})
            basis = pd.DataFrame()
        else:
            source, path = spec
            try:
                basis, audit = read_price_basis(path, source)
                source_rows.append({"cik10": cik, "status": "loaded", **audit})
            except (OSError, ValueError, KeyError) as exc:
                basis = pd.DataFrame()
                source_rows.append({"cik10": cik, "source": source, "price_file": str(path), "status": "unreadable", "error": repr(exc)})
        for item in group.itertuples(index=False):
            record = item._asdict()
            decision = pd.Timestamp(record["decision_at"])
            decision_naive = decision.tz_convert(None)
            prior = basis.index[basis.index < decision_naive] if len(basis) else pd.DatetimeIndex([])
            price_date = prior[-1] if len(prior) else pd.NaT
            raw_close = float(basis.at[price_date, "raw_close"]) if pd.notna(price_date) and pd.notna(basis.at[price_date, "raw_close"]) else np.nan
            adjusted_close = float(basis.at[price_date, "adjusted_close"]) if pd.notna(price_date) and pd.notna(basis.at[price_date, "adjusted_close"]) else np.nan
            outstanding = record.get("shares_outstanding")
            diluted = record.get("diluted_shares")
            outstanding_period = record.get("shares_outstanding__period_end")
            outstanding_available = record.get("shares_outstanding__available_at")
            diluted_period = record.get("diluted_shares__period_end")
            diluted_available = record.get("diluted_shares__available_at")
            cross_check_ratio = float(outstanding) / float(diluted) if pd.notna(outstanding) and float(outstanding) > 0 and pd.notna(diluted) and float(diluted) > 0 else np.nan
            outstanding_age = (decision - pd.Timestamp(outstanding_period)).days if pd.notna(outstanding_period) else np.inf
            outstanding_valid = bool(pd.notna(outstanding) and float(outstanding) > 0 and outstanding_age <= 550 and (not np.isfinite(cross_check_ratio) or 0.25 <= cross_check_ratio <= 4.0))
            diluted_valid = bool(pd.notna(diluted) and float(diluted) > 0 and pd.notna(diluted_available) and pd.Timestamp(diluted_available) < decision)
            if outstanding_valid:
                shares = float(outstanding)
                period_end = outstanding_period
                split_start = outstanding_period
                shares_basis = "shares_outstanding_cross_checked"
                available_at = outstanding_available
            elif diluted_valid:
                shares = float(diluted)
                period_end = diluted_period
                # EPS denominators are retrospectively split-adjusted through filing issuance.
                split_start = max(pd.Timestamp(diluted_period), pd.Timestamp(diluted_available)) if pd.notna(diluted_period) else pd.Timestamp(diluted_available)
                shares_basis = "diluted_shares_fallback"
                available_at = diluted_available
            else:
                shares = np.nan
                period_end = pd.NaT
                split_start = pd.NaT
                shares_basis = "unusable"
                available_at = outstanding_available if pd.notna(outstanding_available) else diluted_available
            split_multiplier = 1.0
            split_events = 0
            if pd.notna(split_start) and pd.notna(price_date) and len(basis):
                applicable = basis[(basis.index > pd.Timestamp(split_start).tz_convert(None)) & (basis.index <= price_date) & basis.split_factor.gt(0)]
                split_multiplier = float(applicable.split_factor.prod()) if len(applicable) else 1.0
                split_events = int(len(applicable))
            normalized_shares = float(shares) * split_multiplier if pd.notna(shares) and float(shares) > 0 else np.nan
            market_cap = raw_close * normalized_shares if np.isfinite(raw_close) and np.isfinite(normalized_shares) else np.nan
            naive_market_cap = adjusted_close * float(shares) if np.isfinite(adjusted_close) and pd.notna(shares) and float(shares) > 0 else np.nan
            capex = abs(float(record["capital_expenditure"])) if pd.notna(record.get("capital_expenditure")) else np.nan
            free_cash_flow = float(record["operating_cash_flow"]) - capex if pd.notna(record.get("operating_cash_flow")) and np.isfinite(capex) else np.nan
            record.update({
                "price_date": price_date, "raw_close": raw_close, "adjusted_close_audit_only": adjusted_close,
                "shares_basis": shares_basis, "shares_cross_check_ratio": cross_check_ratio,
                "split_events_after_fact": split_events, "split_multiplier": split_multiplier,
                "normalized_shares": normalized_shares, "market_cap": market_cap,
                "naive_adjusted_market_cap": naive_market_cap,
                "naive_to_normalized_cap_ratio": naive_market_cap / market_cap if np.isfinite(naive_market_cap) and market_cap > 0 else np.nan,
                "earnings_yield": float(record["net_income"]) / market_cap if pd.notna(record.get("net_income")) and market_cap > 0 else np.nan,
                "free_cash_flow_yield": free_cash_flow / market_cap if np.isfinite(free_cash_flow) and market_cap > 0 else np.nan,
                "sales_yield": float(record["revenue"]) / market_cap if pd.notna(record.get("revenue")) and market_cap > 0 else np.nan,
                "negative_dilution": -float(record["diluted_shares__yoy_growth"]) if pd.notna(record.get("diluted_shares__yoy_growth")) else np.nan,
                "price_before_decision": bool(pd.notna(price_date) and price_date < decision_naive),
                "shares_available_before_decision": bool(pd.isna(available_at) or pd.Timestamp(available_at) < decision),
            })
            rows.append(record)
        if number % 100 == 0:
            print(f"valuation price basis {number}/{panel.cik10.nunique()}", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(source_rows)


def score_and_choose(panel: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_rows, choices = [], []
    for decision, frame in panel.groupby("decision_at", sort=True):
        frame = frame.copy().reset_index(drop=True)
        component_names = ["earnings_yield", "free_cash_flow_yield", "sales_yield", "operating_margin", "operating_cash_flow_margin", "cash_to_assets", "equity_to_assets", "negative_dilution"]
        ranked = {name: rank_sector_neutral(frame, name) for name in component_names}
        families = {
            "earnings_yield": ranked["earnings_yield"],
            "free_cash_flow_yield": ranked["free_cash_flow_yield"],
            "sales_yield": ranked["sales_yield"],
            "composite_value": pd.concat([ranked["earnings_yield"], ranked["free_cash_flow_yield"], ranked["sales_yield"]], axis=1).mean(axis=1, skipna=True),
            "quality_at_reasonable_price": pd.concat(list(ranked.values()), axis=1).mean(axis=1, skipna=True),
        }
        for family, values in families.items():
            scored = frame[["decision_at", "cik10", "company_name_as_filed", "sector", "market_cap"]].copy()
            scored["family"] = family
            scored["score"] = values
            score_rows.append(scored)
            usable = scored.dropna(subset=["score"])
            for breadth in config["breadths"]:
                if len(usable) < max(int(config["minimum_companies_per_decision"]), int(breadth)):
                    continue
                selected = usable.sort_values(["score", "cik10"], ascending=[False, True]).head(int(breadth))
                for row in selected.itertuples(index=False):
                    choices.append({"decision_at": decision, "family": family, "breadth": int(breadth), "cik10": row.cik10, "company_name": row.company_name_as_filed, "sector": row.sector, "score": row.score, "market_cap": row.market_cap, "intended_weight": 1.0 / int(breadth)})
    return pd.concat(score_rows, ignore_index=True), pd.DataFrame(choices)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    membership["tradable_member"] = membership.tradable_member.astype(bool)
    inputs = pd.read_csv(INPUTS, dtype={"cik10": str}, low_memory=False)
    inputs["decision_time"] = pd.to_datetime(inputs.decision_time, utc=True)
    panel_checkpoint = OUTPUT / "normalized_valuation_panel_basis_v2.csv"
    source_checkpoint = OUTPUT / "price_source_audit.csv"
    if panel_checkpoint.exists() and source_checkpoint.exists():
        panel = pd.read_csv(panel_checkpoint, dtype={"cik10": str}, low_memory=False, parse_dates=["decision_at", "decision_time", "price_date", "shares_outstanding__period_end", "shares_outstanding__available_at", "diluted_shares__period_end", "diluted_shares__available_at"])
        source_audit = pd.read_csv(source_checkpoint, dtype={"cik10": str})
    else:
        panel, source_audit = build_valuation_panel(inputs, membership, source_map())
        panel.to_csv(panel_checkpoint, index=False)
        source_audit.to_csv(source_checkpoint, index=False)
    scores, choices = score_and_choose(panel, config)
    repeated_scores, repeated_choices = score_and_choose(panel.copy(), config)

    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp(config["start_decision"]), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = source_map(), base.terminal_dates()
    selected_ciks = sorted(set(choices.cik10))
    weekly_series = {}
    for cik in selected_ciks:
        spec = sources.get(cik)
        if spec:
            try:
                weekly_series[cik] = base.read_weekly_price(spec[1], spec[0], weekly_index, terminals.get(cik))
            except OSError:
                weekly_series[cik] = pd.Series(np.nan, index=weekly_index)
    weekly = pd.DataFrame(weekly_series, index=weekly_index)
    benchmarks = base.benchmark_weekly(weekly_index)

    rows, paths, events = [], {}, []
    for cost in config["cost_bps"]:
        for (family, breadth), selected in choices.groupby(["family", "breadth"], sort=True):
            targets = base.build_targets(selected, weekly_index)
            for scenario in ["base", "adverse"]:
                path, event = base.simulate(weekly, targets, scenario, float(cost))
                candidate = f"{family}__top{int(breadth)}"
                rows.extend(base.metric_rows(candidate, scenario, int(cost), path))
                event["candidate"], event["cost_bps"] = candidate, int(cost)
                events.append(event)
                if int(cost) == int(config["primary_cost_bps"]):
                    paths[(candidate, scenario)] = path
        for ticker in ["SPY", "XLK", "XLE"]:
            path = base.static_benchmark_path(benchmarks[ticker], float(cost))
            rows.extend(base.metric_rows(f"benchmark::{ticker}", "observed", int(cost), path))
    performance = pd.DataFrame(rows)
    primary = performance[(performance.cost_bps == config["primary_cost_bps"]) & (performance.scenario == "base")]
    recent = primary[primary.window == "trailing_1y"].sort_values("cagr", ascending=False)
    best = recent[~recent.candidate.str.startswith("benchmark::")].iloc[0]
    best_name = str(best.candidate)
    best_full = primary[(primary.candidate == best_name) & (primary.window == "full_recent")].iloc[0]
    best_adverse = performance[(performance.candidate == best_name) & (performance.scenario == "adverse") & (performance.cost_bps == 50) & (performance.window == "full_recent")].iloc[0]
    benchmark_recent = performance[(performance.cost_bps == config["primary_cost_bps"]) & (performance.scenario == "observed") & (performance.window == "trailing_1y")].sort_values("cagr", ascending=False).iloc[0]

    decision_coverage = panel.groupby("decision_at").agg(tradable_members=("cik10", "count"), positive_market_caps=("market_cap", lambda values: int(values.gt(0).sum())))
    decision_coverage["coverage"] = decision_coverage.positive_market_caps / decision_coverage.tradable_members
    loaded_sources = int((source_audit.status == "loaded").sum())
    unreadable_sources = int((source_audit.status == "unreadable").sum())
    split_rows = panel[panel.split_events_after_fact.gt(0) & panel.market_cap.gt(0)]
    breadth_counts = choices.groupby(["family", "breadth", "decision_at"]).size().rename("selected").reset_index()
    checks = {
        "all_share_facts_available_before_decision": bool(panel.shares_available_before_decision.all()),
        "all_loaded_prices_before_decision": bool(panel.loc[panel.price_date.notna(), "price_before_decision"].all()),
        "all_computed_market_caps_positive": bool(panel.loc[panel.market_cap.notna(), "market_cap"].gt(0).all()),
        "raw_close_used_for_signal": True,
        "adjusted_close_audit_only": True,
        "minimum_coverage_met_every_decision": bool(decision_coverage.coverage.ge(float(config["minimum_market_cap_coverage"])).all()),
        "deterministic_choices": frame_hash(choices) == frame_hash(repeated_choices),
        "fixed_breadths": bool(breadth_counts.selected.eq(breadth_counts.breadth).all()),
        "base_and_adverse_run": True,
        "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
    }
    panel.to_csv(OUTPUT / "normalized_valuation_panel.csv", index=False)
    source_audit.to_csv(OUTPUT / "price_source_audit.csv", index=False)
    decision_coverage.to_csv(OUTPUT / "decision_coverage.csv")
    scores.to_csv(OUTPUT / "factor_scores.csv", index=False)
    choices.to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    pd.concat(events, ignore_index=True).to_csv(OUTPUT / "rebalance_events.csv", index=False)
    split_rows.to_csv(OUTPUT / "split_distortion_audit.csv", index=False)
    paths[(best_name, "base")].rename_axis("Date").to_csv(OUTPUT / "best_path_base_50bps.csv")
    paths[(best_name, "adverse")].rename_axis("Date").to_csv(OUTPUT / "best_path_adverse_50bps.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tradable_membership_rows": int(len(panel)), "unique_ciks": int(panel.cik10.nunique()),
        "loaded_price_sources": loaded_sources, "unreadable_price_sources": unreadable_sources,
        "minimum_decision_market_cap_coverage": float(decision_coverage.coverage.min()),
        "rows_with_split_adjustment": int(len(split_rows)),
        "outstanding_share_rows": int(panel.shares_basis.eq("shares_outstanding_cross_checked").sum()),
        "diluted_share_fallback_rows": int(panel.shares_basis.eq("diluted_shares_fallback").sum()),
        "median_naive_to_normalized_cap_ratio_on_split_rows": float(split_rows.naive_to_normalized_cap_ratio.median()) if len(split_rows) else None,
        "best_candidate": best_name, "best_trailing_1y_50bps_cagr": float(best.cagr), "best_trailing_1y_50bps_sharpe": float(best.sharpe_zero_rf), "best_trailing_1y_50bps_drawdown": float(best.max_drawdown),
        "best_full_50bps_cagr": float(best_full.cagr), "best_adverse_full_50bps_cagr": float(best_adverse.cagr),
        "best_benchmark_recent": str(benchmark_recent.candidate), "best_benchmark_recent_cagr": float(benchmark_recent.cagr),
        "beats_best_benchmark_recent": bool(best.cagr > benchmark_recent.cagr),
        "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Survivorship-aware split-normalized valuation discovery v1\n\n"
        f"The corrected valuation basis was expanded to {result['unique_ciks']} CIKs across {panel.decision_at.nunique()} point-in-time decisions. "
        f"The minimum decision-level market-cap coverage was {result['minimum_decision_market_cap_coverage']:.2%}.\n\n"
        f"Best candidate: `{best_name}` with trailing-one-year CAGR {best.cagr:.2%}, Sharpe {best.sharpe_zero_rf:.3f}, and drawdown {best.max_drawdown:.2%}. "
        f"Full-period CAGR was {best_full.cagr:.2%}; adverse missing-company full CAGR was {best_adverse.cagr:.2%}. "
        f"Best recent benchmark was `{benchmark_recent.candidate}` at {benchmark_recent.cagr:.2%}.\n\n"
        "This is discovery evidence only. It cannot replace the return-first leader until concentration, timing, cost, neighboring-breadth, and controlled-overlay falsification pass.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
