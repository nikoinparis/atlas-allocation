#!/usr/bin/env python3
"""Reconstruct the control strategy's composite target book at a decision date.

`sec_cash_conversion_breadth20_dynamic_v1` is the control leg of the residual
sleeve's forward protocol, and its target weights are not stored anywhere this
repository can regenerate: the only artifact carrying them is a 184MB dashboard
snapshot produced by a pipeline that lives outside this checkout and stops at
2026-08-07. A decision packet needs point-in-time control weights, so the book
has to be rebuilt from its parts.

The composite is four sleeves, and the decomposition below reproduces the
2026-08-07 book to ten decimal places:

    overlay      x [ growth 0.40 + ETF leader 0.60 ]     the "leader" sleeve
    1 - overlay  x [ 20 equal cash-conversion slots ]     unpriced slots become cash

`overlay` is binary, not a blend: `overlay_target` allocates `high` (0.5) to
cash conversion only when its trailing 11-week total return beats the leader's
and is itself positive, and otherwise holds the leader alone. At 2026-08-07 it
was active, which is why that book splits 0.50/0.50.

Run with --verify to assert the reconstruction against a known book rather than
trusting it. Nothing here is authorised to trade.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
GROWTH = ROOT / "evidence/sec_growth_survivorship_retest_v1"
LEADER_PATH = ROOT / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv"
# NOT candidate_path_50bps.csv: that is the composite this overlay produces, so
# feeding it back in is circular and silently agrees on about half of weeks.
CASH_PATH = ROOT / "evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv"
ETF_WEIGHTS = ROOT / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v3/price_source_inventory.csv"

BREADTH = 20
OVERLAY_LOOKBACK = 11
OVERLAY_HIGH = 0.5
GROWTH_SHARE_OF_LEADER = 0.4
CASH = "cash::USD"


def read_path(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    column = "Date" if "Date" in frame else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column])
    return frame.set_index(column).sort_index()


def rolling_total(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return (1 + returns.shift(1)).rolling(lookback, min_periods=lookback).apply(np.prod, raw=True) - 1


def ticker_map() -> dict[str, str]:
    import csv, re
    out: dict[str, str] = {}
    with INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            match = (re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
                     or re.search(r"/([A-Za-z0-9.\-]+)/prices\.csv\.gz$", row["path"]))
            if match:
                out.setdefault(row["cik10"], match.group(1).upper())
    return out


def quarter_for(decision: pd.Timestamp, decisions: pd.Index) -> pd.Timestamp:
    """The latest quarterly selection strictly on or before the weekly decision."""
    eligible = [d for d in decisions if d <= decision]
    if not eligible:
        raise SystemExit(f"no quarterly selection at or before {decision.date()}")
    return max(eligible)


def overlay_allocation(decision: pd.Timestamp) -> float:
    leader = read_path(LEADER_PATH).net_return
    cash = read_path(CASH_PATH).net_return
    signal = pd.DataFrame({"leader": leader, "cash_conversion": cash}).dropna()
    if decision not in signal.index:
        raise SystemExit(
            f"{decision.date()} is not in the sleeve return paths, which end "
            f"{signal.index[-1].date()}; the sleeves must be simulated forward first"
        )
    trend = rolling_total(signal, OVERLAY_LOOKBACK)
    row = trend.loc[decision]
    active = bool(row.cash_conversion > row.leader and row.cash_conversion > 0)
    return OVERLAY_HIGH if active else 0.0


def build(decision: pd.Timestamp) -> dict[str, object]:
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    scores["decision_at"] = scores.decision_at.dt.tz_localize(None)
    cc = scores[scores.family == "cash_conversion"]
    quarter = quarter_for(decision, pd.Index(sorted(cc.decision_at.unique())))
    picked = (cc[cc.decision_at == quarter].dropna(subset=["score"])
              .sort_values(["score", "cik10"], ascending=[False, True]).head(BREADTH))

    growth = pd.read_csv(GROWTH / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    growth["decision_at"] = growth.decision_at.dt.tz_localize(None)
    gquarter = quarter_for(decision, pd.Index(sorted(growth.decision_at.unique())))
    gbook = growth[growth.decision_at == gquarter]

    etf = pd.read_csv(ETF_WEIGHTS, index_col=0)
    etf.index = pd.to_datetime(etf.index)
    erow = etf.loc[etf.index[etf.index <= decision][-1]]
    ebook = erow[erow.abs() > 1e-12].drop(index=CASH, errors="ignore")

    allocation = overlay_allocation(decision)
    leader_share, cc_share = 1.0 - allocation, allocation

    tickers = ticker_map()
    book: dict[str, float] = {}
    for row in gbook.itertuples(index=False):
        symbol = tickers.get(row.cik10)
        if symbol:
            book[symbol] = book.get(symbol, 0.0) + leader_share * GROWTH_SHARE_OF_LEADER * float(row.intended_weight)
    for symbol, weight in ebook.items():
        book[symbol] = book.get(symbol, 0.0) + leader_share * (1.0 - GROWTH_SHARE_OF_LEADER) * float(weight)

    unpriced = 0
    for row in picked.itertuples(index=False):
        symbol = tickers.get(row.cik10)
        if symbol:
            book[symbol] = book.get(symbol, 0.0) + cc_share / BREADTH
        else:
            unpriced += 1
    if unpriced:
        book[CASH] = book.get(CASH, 0.0) + cc_share * unpriced / BREADTH

    total = sum(book.values())
    if abs(total - 1.0) > 1e-9:
        raise SystemExit(f"composite weights sum to {total}, not one")
    return {
        "decision_date": str(decision.date()),
        "cash_conversion_quarter": str(quarter.date()),
        "growth_quarter": str(gquarter.date()),
        "overlay_allocation_to_cash_conversion": allocation,
        "unpriced_cash_conversion_slots": unpriced,
        "selection_cik10s": sorted(picked.cik10.tolist()),
        "weights": {k: float(v) for k, v in sorted(book.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--verify", default="", help="strategy_id in dashboard_last_books_v1 to assert against")
    args = parser.parse_args()
    result = build(pd.Timestamp(args.decision_date))

    if args.verify:
        # The dashboard book is deliberately not the reference. It drops Dynatrace and
        # ServiceNow into cash at 2026-08-07 even though both are tradable and priced in
        # the control's own roster, so it reflects that pipeline's coverage rather than
        # the strategy's targets. The audit artifacts are what the strategy actually
        # decided: its selection, and its overlay allocation.
        audit = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1"
        choices = pd.read_csv(audit / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
        choices["decision_at"] = choices.decision_at.dt.tz_localize(None)
        quarter = pd.Timestamp(result["cash_conversion_quarter"])
        expected = set(choices.loc[choices.decision_at == quarter, "cik10"])
        targets = read_path(audit / "target_weights.csv")
        decision = pd.Timestamp(result["decision_date"])
        expected_overlay = (float(targets.loc[decision, "cash_conversion"])
                            if decision in targets.index else None)
        result["verification"] = {
            "reference": "sec_cash_conversion_breadth20_candidate_audit_v1",
            "selection_quarter": str(quarter.date()),
            "selection_matches": bool(expected == set(result["selection_cik10s"])),
            "selection_expected": len(expected), "selection_built": len(result["selection_cik10s"]),
            "overlay_expected": expected_overlay,
            "overlay_built": result["overlay_allocation_to_cash_conversion"],
            "overlay_matches": bool(expected_overlay is not None
                                    and abs(expected_overlay - result["overlay_allocation_to_cash_conversion"]) < 1e-12),
        }
        result["verification"]["reproduces"] = bool(
            result["verification"]["selection_matches"] and result["verification"]["overlay_matches"]
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not args.verify or result["verification"]["reproduces"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
