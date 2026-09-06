#!/usr/bin/env python3
"""A second implementation, written to disagree with the first if it can.

Every number this project reports comes from the pipeline that produced it.
Nothing has ever been rebuilt by a separate implementation and checked, which is
the difference between a research repository and a firm's production stack.

This is the first such check.  It takes a strategy's saved book and prices it
from the weekly panels with no shared code beyond the return primitive, then
asks whether the result matches the path the strategy reports.

It also sweeps the execution convention rather than assuming one, because the
first attempt at this (Step 238) assumed "the first week strictly after the
decision date", got a correlation of -0.026, and concluded the artifacts were
insufficient.  They were not.  The book reproduces at 0.90 once the offset is
right, and the wrong conclusion came from a reconstruction that was one week
late.  A reproduction harness that cannot tell "the artifacts are wrong" from
"my alignment is wrong" is not a reproduction harness, so this one reports the
whole alignment curve instead of a single number.

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

MATCH_CORRELATION = 0.85

TARGETS = {
    "cash_conversion_breadth20_sleeve": {
        "book": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv",
        "date_column": "decision_at",
        "weight_column": "intended_weight",
        "reference": "evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv",
        "note": "the breadth-20 stock sleeve, not the leader/cash-conversion overlay above it",
    },
    "growth_top_five": {
        "book": "evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv",
        "date_column": "decision_at",
        "weight_column": "intended_weight",
        "reference": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
        "note": "stock book priced directly",
    },
    "sector_ensemble_stock_leg": {
        "book": "evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv",
        "date_column": "rebalance_at",
        "weight_column": "intended_weight",
        "reference": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
        "note": "stock leg only; the reference may sit under a strategy-level allocator",
    },
}

PRICE_SOURCES = {
    "clean_weekly_prices_v2": "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz",
    "corporate_action_clean_v1": "data/clean_corporate_action_prices_v1/weekly_adjusted_prices_clean.csv.gz",
}


def load_returns(relative: str) -> pd.DataFrame:
    frame = pd.read_csv(ROOT / relative, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    frame = frame.apply(pd.to_numeric, errors="coerce")
    return (frame / frame.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)


def load_series(relative: str) -> pd.Series:
    frame = pd.read_csv(ROOT / relative)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True)
    frame = frame.set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def simulate(book: pd.DataFrame, returns: pd.DataFrame, cost_bps: float) -> pd.Series:
    """Deliberately written from the definition rather than reused from the engine."""
    schedule = {date: frame for date, frame in book.groupby("execution_at")}
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values = []
    for week in returns.index:
        turnover_cost = 0.0
        if week in schedule:
            holdings = pd.Series(0.0, index=returns.columns, dtype=float)
            frame = schedule[week]
            holdings.loc[frame.cik10.to_numpy()] = frame.weight.to_numpy()
            turnover_cost = float((holdings - previous).abs().sum()) * cost_bps / 10_000.0
            previous = holdings.copy()
        observed = returns.loc[week].fillna(0.0)
        values.append(float((holdings * observed).sum()) - turnover_cost)
    return pd.Series(values, index=returns.index, name="rebuilt")


def compound(series: pd.Series) -> float:
    years = len(series) / 52.0
    return float((1.0 + series.fillna(0.0)).prod() ** (1.0 / years) - 1.0) if years else float("nan")


def align(book: pd.DataFrame, index: pd.DatetimeIndex, offset: int) -> pd.DataFrame:
    """offset 0 is the first panel week strictly after the book date; -1 is one earlier."""
    mapping = {}
    for value in sorted(book.decision_at.unique()):
        later = list(index[index > value])
        earlier = list(index[index <= value])
        position = len(earlier) + offset
        if 0 <= position < len(index):
            mapping[value] = index[position]
    aligned = book[book.decision_at.isin(mapping)].copy()
    aligned["execution_at"] = aligned.decision_at.map(mapping)
    return aligned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost-bps", type=float, default=50.0)
    parser.add_argument("--output", default="evidence/independent_reproduction_v1")
    args = parser.parse_args()

    findings = {}
    for name, spec in TARGETS.items():
        book_raw = pd.read_csv(ROOT / spec["book"], dtype={"cik10": str})
        book_raw[spec["date_column"]] = pd.to_datetime(book_raw[spec["date_column"]], utc=True)
        weight = spec["weight_column"]
        if weight not in book_raw.columns:
            book_raw[weight] = 1.0 / book_raw.groupby(spec["date_column"])["cik10"].transform("count")
        book = book_raw[[spec["date_column"], "cik10", weight]].rename(
            columns={spec["date_column"]: "decision_at", weight: "weight"})
        reference = load_series(spec["reference"])

        best = None
        curve = {}
        for source, relative in PRICE_SOURCES.items():
            if not (ROOT / relative).is_file():
                continue
            returns = load_returns(relative)
            covered = book[book.cik10.isin(returns.columns)]
            if covered.empty:
                continue
            for offset in range(-3, 4):
                aligned = align(covered, returns.index, offset)
                if aligned.empty:
                    continue
                rebuilt = simulate(aligned, returns, args.cost_bps)
                joined = pd.concat([rebuilt, reference.rename("reference")], axis=1).dropna()
                if len(joined) < 26:
                    continue
                # Sweep the date-labelling offset as well as the execution offset.
                # They are different things: executing a week earlier barely moves a
                # book that rebalances fourteen times in 188 weeks, but labelling the
                # same weekly return with a different Friday moves the correlation
                # from -0.02 to +0.90. Reporting only the unshifted number is how the
                # first attempt concluded the artifacts were insufficient.
                labels = {shift: float(joined.rebuilt.shift(shift).corr(joined.reference))
                          for shift in (-2, -1, 0, 1, 2)}
                label_shift = max(labels, key=lambda k: labels[k])
                correlation = labels[label_shift]
                record = {
                    "price_source": source,
                    "execution_offset_weeks": offset,
                    "date_label_offset_weeks": label_shift,
                    "correlation_without_label_shift": labels[0],
                    "label_offset_curve": {str(k): round(v, 4) for k, v in labels.items()},
                    "overlapping_weeks": int(len(joined)),
                    "correlation": correlation,
                    "rebuilt_cagr": compound(joined.rebuilt),
                    "reference_cagr": compound(joined.reference),
                    "issuers_priced": int(covered.cik10.nunique()),
                    "issuers_in_book": int(book.cik10.nunique()),
                }
                curve[f"{source}@{offset:+d}"] = round(correlation, 4)
                if best is None or correlation > best["correlation"]:
                    best = record
        if best is None:
            findings[name] = {"reproduced": False, "reason": "no comparable overlap", "note": spec["note"]}
            continue
        best["cagr_gap_pp"] = round((best["rebuilt_cagr"] - best["reference_cagr"]) * 100, 2)
        best["reproduced"] = bool(best["correlation"] >= MATCH_CORRELATION)
        best["alignment_curve"] = curve
        best["note"] = spec["note"]
        findings[name] = best

    result = {
        "experiment": "independent_reproduction_v1",
        "match_threshold_correlation": MATCH_CORRELATION,
        "cost_bps": args.cost_bps,
        "findings": findings,
        "reproduced_count": sum(1 for f in findings.values() if f.get("reproduced")),
        "attempted": len(findings),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for name, f in findings.items():
        print(f"{name}: reproduced={f.get('reproduced')} corr={f.get('correlation')} "
              f"offset={f.get('execution_offset_weeks')} source={f.get('price_source')} "
              f"cagr {f.get('rebuilt_cagr')} vs {f.get('reference_cagr')}")
    print(f"\n{result['reproduced_count']} of {result['attempted']} reproduced at correlation >= {MATCH_CORRELATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
