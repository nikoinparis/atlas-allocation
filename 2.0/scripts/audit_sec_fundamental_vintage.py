#!/usr/bin/env python3
"""Audit a live SEC vintage and build real point-in-time factor inputs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_point_in_time import quarterly_factor_inputs


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vintage", default=None)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    vintage = Path(args.vintage) if args.vintage else sorted((ROOT / "data/sec_vintages").glob("*-sec-pit-v1"))[-1]
    manifest = json.loads((vintage / "manifest.json").read_text())
    events = pd.read_csv(vintage / "fundamental_events.csv", low_memory=False)
    filings = pd.read_csv(vintage / "filings.csv", low_memory=False)
    universe = pd.read_csv(vintage / "universe.csv")
    for column in ("start", "end", "filed"):
        events[column] = pd.to_datetime(events[column], errors="coerce")
    events["available_at"] = pd.to_datetime(events.available_at, utc=True, errors="coerce")
    events["concept_priority"] = pd.to_numeric(events.concept_priority, errors="coerce").fillna(999).astype(int)

    expected_unit = events.canonical_metric.map(lambda metric: "shares" if metric in {"shares_outstanding", "diluted_shares"} else "USD")
    unit_audit = events.groupby(["canonical_metric", "unit"]).size().rename("rows").reset_index()
    unit_audit["expected"] = unit_audit.apply(lambda row: row.unit == ("shares" if row.canonical_metric in {"shares_outstanding", "diluted_shares"} else "USD"), axis=1)
    unexpected_unit_rows = int((events.unit != expected_unit).sum())

    coverage = events.groupby(["ticker", "canonical_metric"]).agg(
        rows=("value", "size"), first_period_end=("end", "min"), last_period_end=("end", "max"),
        first_available_at=("available_at", "min"), last_available_at=("available_at", "max"),
        accessions=("accession", "nunique"), amendments=("is_amendment", "sum"), units=("unit", "nunique"),
    ).reset_index()
    form_coverage = events.groupby(["ticker", "form"]).size().rename("rows").reset_index()

    prices = pd.read_csv(ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv", index_col=0, parse_dates=True)
    quarter_dates = prices.index[(prices.index >= pd.Timestamp("2012-01-01")) & prices.index.month.isin([3, 6, 9, 12])]
    decisions = quarter_dates.to_series().groupby(quarter_dates.to_period("Q")).tail(1).index + pd.Timedelta(days=1)
    ticker_by_cik = universe.set_index("cik10").ticker.to_dict()
    inputs = quarterly_factor_inputs(events, decisions, ticker_by_cik)

    metadata_suffixes = ("__period_end", "__available_at", "__prior_year")
    excluded = {"decision_time", "cik10", "ticker"}
    feature_columns = [column for column in inputs if column not in excluded and not column.endswith(metadata_suffixes)]
    recent = inputs[pd.to_datetime(inputs.decision_time, utc=True) >= pd.Timestamp("2021-01-01", tz="UTC")]
    feature_rows = []
    for column in feature_columns:
        feature_rows.append({
            "feature": column, "all_coverage": float(inputs[column].notna().mean()),
            "recent_coverage": float(recent[column].notna().mean()),
            "all_companies": int(inputs.loc[inputs[column].notna(), "ticker"].nunique()),
            "recent_companies": int(recent.loc[recent[column].notna(), "ticker"].nunique()),
        })
    feature_coverage = pd.DataFrame(feature_rows).sort_values(["recent_coverage", "all_coverage"], ascending=False)
    feature_coverage["pilot_viable"] = (feature_coverage.recent_coverage >= 0.70) & (feature_coverage.recent_companies >= 14)

    cross_section = inputs.groupby("decision_time").ticker.nunique().rename("companies").reset_index()
    acceptance = filings.get("acceptance_datetime", pd.Series(dtype="object")).fillna("").astype(str).str.len().gt(0)
    accession_set = set(filings.accession.astype(str))
    joined_share = float(events.accession.astype(str).isin(accession_set).mean())
    exact_acceptance_share = float(acceptance.mean()) if len(filings) else 0.0
    structural_pass = bool(
        manifest["audit"]["valid"] and events.available_at.notna().all()
        and not events.duplicated(["cik10", "concept", "unit", "start", "end", "accession", "value"]).any()
        and joined_share >= 0.99
    )
    viable = feature_coverage[feature_coverage.pilot_viable].feature.tolist()

    coverage.to_csv(vintage / "coverage_by_ticker_metric.csv", index=False)
    form_coverage.to_csv(vintage / "coverage_by_ticker_form.csv", index=False)
    unit_audit.to_csv(vintage / "unit_audit.csv", index=False)
    inputs.to_csv(vintage / "quarterly_factor_inputs.csv", index=False)
    feature_coverage.to_csv(vintage / "factor_input_coverage.csv", index=False)
    cross_section.to_csv(vintage / "quarterly_cross_section_coverage.csv", index=False)
    result = {
        "vintage_id": manifest["vintage_id"], "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "structural_audit_pass": structural_pass, "event_rows": len(events), "filing_rows": len(filings),
        "companies": int(events.ticker.nunique()), "canonical_metrics": int(events.canonical_metric.nunique()),
        "accessions": int(events.accession.nunique()), "amendment_rows": int(events.is_amendment.sum()),
        "accession_join_share": joined_share, "filings_with_exact_acceptance_share": exact_acceptance_share,
        "unexpected_unit_rows_preserved_and_excluded_from_factors": unexpected_unit_rows, "quarterly_decisions": len(decisions),
        "factor_input_rows": len(inputs), "minimum_companies_per_quarterly_decision": int(cross_section.companies.min()),
        "median_companies_per_quarterly_decision": float(cross_section.companies.median()),
        "pilot_viable_feature_count": len(viable), "pilot_viable_features": viable,
        "pilot_factor_diagnostic_authorized": structural_pass and len(viable) >= 5,
        "strategy_promotion_authorized": False,
        "promotion_blockers": ["current-membership pilot universe", "no delisting-complete stock price panel", "no untouched fundamental-sleeve evidence"],
        "live_trading_enabled": False,
    }
    (vintage / "audit_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (vintage / "audit_report.md").write_text(
        "# Live SEC vintage audit\n\n"
        f"Structural audit: **{structural_pass}**. The vintage contains **{len(events):,}** canonical fact events for **{events.ticker.nunique()}** companies and **{events.accession.nunique():,}** accessions, including **{int(events.is_amendment.sum()):,}** amendment events.\n\n"
        f"Accession join coverage is **{joined_share:.2%}**; filings carrying precise acceptance timestamps are **{exact_acceptance_share:.2%}**. Unexpected-unit rows: **{unexpected_unit_rows}**. The filing-aware quarterly builder produced **{len(inputs):,}** company-decision rows across **{len(decisions)}** decisions.\n\n"
        f"Pilot-viable factor inputs (>=70% recent coverage across >=14 companies): **{len(viable)}**: `{', '.join(viable)}`. Pilot factor diagnostics authorized: **{result['pilot_factor_diagnostic_authorized']}**. Strategy promotion remains prohibited because the universe is not survivorship-safe and a delisting-complete stock-price panel is absent.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if structural_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
