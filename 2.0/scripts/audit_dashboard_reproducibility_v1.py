#!/usr/bin/env python3
"""Can every strategy on the dashboard actually be rebuilt? Answer it per strategy.

The owner's question is the right one: a strategy nobody can recreate is not a
strategy, it is a number in a JSON file. This walks all six dashboard strategies
and asks, for each, three separate questions that are easy to confuse.

  1. Is there a *book* -- dated target weights -- saved anywhere?
  2. Does pricing that book from the weekly panels reproduce the published path?
  3. Is there a frozen manifest saying what the strategy IS, independent of the
     artifacts a particular run happened to leave behind?

A strategy can pass 2 and fail 3, which is the state most of these are in: the
saved weights reprice correctly, and nothing written down would let you derive
those weights again from raw data. That is worth separating rather than
averaging into one score.

The reproduction sweeps the execution offset instead of assuming one. Step 238
assumed "the first week strictly after the decision", got -0.026, and reported
that a strategy did not reproduce. It did; the reconstruction was one week late.
A harness that cannot distinguish "the artifacts are wrong" from "my alignment is
wrong" produces confident false negatives, so this one reports the curve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# Reuse Step 241's harness rather than write a third implementation of the same
# thing. The first draft of this file reimplemented alignment and pricing, swept
# only offsets 0-2, and reported 0 of 6 reproducing at correlations near zero --
# against a known-good 0.904 on the same book. A reproduction harness that is
# itself unreproduced is worth nothing.
import reproduce_dashboard_strategy_independently_v1 as known_good
OUTPUT = ROOT / "evidence/dashboard_reproducibility_v1"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
MATCH = 0.85

PRICES = {
    "narrow": "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz",
    "full_history": "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz",
    "etf": "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz",
    "broad": "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz",
}

# Two dashboard books hold both SEC equities and ETFs, so neither panel alone can
# price them. Step 278 dropped those weeks and reported nothing; this joins the
# two panels side by side instead. The ETF half is not point-in-time and is used
# for verification only -- see evidence/etf_weekly_panel_v1/result.json.
COMBINED = ("full_history", "etf", "broad")

STRATEGIES = {
    "sec-growth-survivorship-aware-v1": {
        "book": "evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv",
        "date_column": "decision_at", "weight_column": "intended_weight",
        "reference": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
        "rebuild_script": "scripts/run_sec_growth_survivorship_retest_v1.py",
        "manifest": "config/strategies/sec_growth_survivorship_aware_v1.json",
    },
    "sec-cash-conversion-breadth20-dynamic-v1": {
        "book": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv",
        "date_column": "decision_at", "weight_column": "intended_weight",
        "reference": "evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv",
        "rebuild_script": "scripts/build_cash_conversion_sleeve_path_v1.py",
        "manifest": "config/strategies/sec_cash_conversion_breadth20_dynamic_v1.json",
    },
    "sec-sector-aware-signal-ensemble-v1": {
        "book": "evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv",
        "date_column": "rebalance_at", "weight_column": "intended_weight",
        "allocator": "evidence/sec_sector_aware_signal_ensemble_v1/selected_strategy_target_weights.csv",
        "leader_path": "evidence/sec_signal_neighborhood_ensemble_v1/selected_path__50bps.csv",
        "reference": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
        "rebuild_script": "scripts/run_sec_sector_aware_signal_ensemble_v1.py",
        "manifest": "config/strategies/sec_sector_aware_signal_ensemble_v1.json",
    },
    "candidate-return-first-60-40-forward-v1": {
        "book": "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv",
        "date_column": None, "weight_column": None,   # wide matrix, not long
        "reference": None,
        "rebuild_script": None,
        "manifest": "config/forward/return_first_60_40_blend_v1.json",
    },
    "sec-residual-controlled-1.25x-5pct-v1": {
        "book": "evidence/control_composite_book_v1/books.csv",
        "date_column": "decision_at", "weight_column": "weight",
        "symbol_column": "symbol",
        "reference": "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv",
        "rebuild_script": "scripts/build_control_composite_book_v1.py",
        "manifest": "config/forward/sec_residual_controlled_sleeve_forward_v1.json",
    },
    "sec-sector-ensemble-fragile-1.35x-v1": {
        "book": "evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv",
        "date_column": "rebalance_at", "weight_column": "intended_weight",
        "allocator": "evidence/sec_sector_aware_signal_ensemble_v1/selected_strategy_target_weights.csv",
        "leader_path": "evidence/sec_signal_neighborhood_ensemble_v1/selected_path__50bps.csv",
        "reference": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
        "rebuild_script": "scripts/run_sec_sector_aware_signal_ensemble_v1.py",
        "manifest": "config/strategies/sec_sector_ensemble_fragile_1_35x_v1.json",
        "note": "the 1.35x levered presentation of the sector ensemble; the underlying book is the same",
    },
}


def load_returns(relative: str) -> pd.DataFrame | None:
    """Delegated. My own version clipped |r| <= 1 and the known-good one does not."""
    return known_good.load_returns(relative) if (ROOT / relative).exists() else None


def load_series(relative: str) -> pd.Series | None:
    """Delegated, and this is where the false negatives came from.

    My version took the first float column. The known-good version takes the
    column actually named `net_return` or `return`. On a file whose first float
    column is something else, the audit was correlating the rebuilt path against
    a column that is not a return series, and reported every strategy as
    unreproducible at correlations near zero.
    """
    return known_good.load_series(relative) if (ROOT / relative).exists() else None




MEMBERSHIP = "evidence/combined_recent_price_panel_v1/classified_membership.csv"


def ticker_to_cik() -> dict[str, str]:
    """Point-in-time ticker -> cik10, from the membership roster's own `ticker_used`.

    The dashboard records holdings by ticker and every SEC price panel is keyed by
    cik10, so without this the repricing check silently matched zero symbols and
    reported nothing at all rather than reporting a failure.
    """
    frame = pd.read_csv(ROOT / MEMBERSHIP, dtype={"cik10": str},
                        usecols=["cik10", "ticker_used"]).dropna()
    frame["ticker_used"] = frame.ticker_used.astype(str).str.upper()
    # Where a ticker has been used by more than one filer, take the most frequent;
    # collisions are rare and the alternative is dropping the name entirely.
    return (frame.groupby("ticker_used").cik10
            .agg(lambda v: v.value_counts().index[0]).to_dict())


def as_naive(frame):
    """Drop tz. Three sources here index three different ways and pandas refuses
    to join naive with aware, so normalise once at every join instead of guessing
    which side carries a timezone."""
    idx = pd.to_datetime(frame.index)
    out = frame.copy()
    out.index = idx.tz_localize(None) if idx.tz is not None else idx
    return out


def reprice_published_holdings(records: list[dict], symbol_map: dict[str, str]) -> dict:
    """Reprice the dashboard's own week-by-week holdings and compare to its own returns.

    This is the strongest available reproduction test and it applies to all six,
    because every dashboard record carries the book it held that week. It answers
    "is the published return consistent with the published book", which is a
    different and stricter question than "does a saved book reprice to a saved
    path". A strategy can pass the second and fail this one if the displayed
    returns were produced by something other than the displayed holdings.
    """
    dates = pd.to_datetime([r["date"] for r in records], utc=True)
    published = pd.Series([float(r["netReturn"]) for r in records], index=dates).sort_index()
    sources = dict(PRICES)
    loaded = [load_returns(PRICES[k]) for k in COMBINED]
    loaded = [f for f in loaded if f is not None]
    if len(loaded) > 1:
        joined_panel = loaded[0]
        for extra in loaded[1:]:
            new = [c for c in extra.columns if c not in joined_panel.columns]
            joined_panel = joined_panel.join(extra[new], how="outer")
        sources["sec_plus_etf_plus_broad"] = joined_panel
    best = None
    for source, relative in sources.items():
        returns = relative if isinstance(relative, pd.DataFrame) else load_returns(relative)
        if returns is None:
            continue
        # Coverage as a share of portfolio WEIGHT, not a count of holding rows.
        # Counting rows treats a 0.5% position and a 20% position as equal and
        # reported the residual composite at 51.2% when 83% of its weight prices.
        rows, covered_weight, total_weight = [], 0.0, 0.0
        for record in records:
            week = pd.Timestamp(record["date"], tz="UTC")
            if week not in returns.index:
                continue
            row = returns.loc[week]
            gross, weight_seen = 0.0, 0.0
            for holding in record.get("holdings", []):
                symbol = str(holding["symbol"])
                weight = float(holding["weight"])
                total_weight += weight
                if symbol == "cash::USD":
                    weight_seen += weight
                    covered_weight += weight
                    continue
                key = symbol if symbol in row.index else symbol_map.get(symbol.upper())
                if key is not None and key in row.index and pd.notna(row[key]):
                    gross += weight * float(row[key])
                    weight_seen += weight
                    covered_weight += weight
            # Two dashboard books mix SEC equities with ETFs, and there is no flat
            # ETF price panel here -- ETF prices live in the vintage store. Dropping
            # any week whose weight is not fully covered silently discarded those
            # two strategies entirely and reported no result at all, which reads as
            # "could not be checked" when the truth is "partly checked". Price the
            # covered portion, scale it back up, and report the coverage.
            if weight_seen > 0.3:
                rows.append((week, gross / weight_seen - float(record.get("cost", 0.0))))
        if len(rows) < 40:
            continue
        rebuilt = pd.Series(dict(rows)).sort_index()
        joined = pd.concat({"a": rebuilt, "b": published}, axis=1, sort=True).dropna()
        if len(joined) < 40:
            continue
        labels = {sh: float(joined.a.shift(sh).corr(joined.b)) for sh in (-1, 0, 1)}
        labels = {k: v for k, v in labels.items() if np.isfinite(v)}
        if not labels:
            continue
        shift = max(labels, key=lambda k: labels[k])
        cand = {"price_source": source, "correlation": labels[shift], "label_shift": shift,
                "weeks": len(joined),
                "symbol_coverage": covered_weight / total_weight if total_weight else 0.0,
                "rebuilt_cagr": known_good.compound(joined.a),
                "published_cagr": known_good.compound(joined.b)}
        # Rank by coverage among sources that clear the bar, not by correlation.
        # Ranking by correlation alone reported the residual composite at 51.2%
        # coverage because a thin panel happened to correlate marginally better,
        # which reads as "half of it cannot be checked" when a combined panel
        # prices 83% of it just as well.
        if best is None:
            best = cand
        else:
            cand_ok = cand["correlation"] >= MATCH
            best_ok = best["correlation"] >= MATCH
            if cand_ok and not best_ok:
                best = cand
            elif cand_ok == best_ok:
                key = "symbol_coverage" if cand_ok else "correlation"
                if cand[key] > best[key]:
                    best = cand
    return best or {}


def audit_one(name: str, spec: dict) -> dict:
    row = {"strategy": name, "note": spec.get("note")}

    row["has_saved_book"] = bool(spec["book"] and (ROOT / spec["book"]).exists())
    row["has_reference_path"] = bool(spec["reference"] and (ROOT / spec["reference"]).exists())
    row["has_rebuild_script"] = bool(spec["rebuild_script"] and (ROOT / spec["rebuild_script"]).exists())
    row["has_frozen_manifest"] = bool(spec["manifest"] and (ROOT / spec["manifest"]).exists())
    row["book"] = spec["book"]
    row["rebuild_script"] = spec["rebuild_script"]
    row["manifest"] = spec["manifest"]

    if not (row["has_saved_book"] and row["has_reference_path"] and spec["date_column"]):
        row["reproduced"] = False
        row["best_correlation"] = None
        row["blocked_by"] = ("no dated weights saved" if not row["has_saved_book"]
                             else "no reference path to compare against" if not row["has_reference_path"]
                             else "book is a wide matrix, not dated long-form weights")
        return row

    reference = load_series(spec["reference"])
    # The sector ensemble's saved stock weights are only its cash_conversion
    # sleeve, which averages 22.2% of the strategy. The other 77.8% is a separate
    # "leader" path. Step 278 called the allocator missing; it was never missing --
    # selected_strategy_target_weights.csv has been saved all along and the audit
    # was pointed at the stock leg. Reprice both legs and combine per the allocator.
    allocator = None
    if spec.get("allocator") and (ROOT / spec["allocator"]).exists():
        allocator = pd.read_csv(ROOT / spec["allocator"], parse_dates=["Date"]).set_index("Date")
    leader = load_series(spec["leader_path"]) if spec.get("leader_path") else None
    frame = pd.read_csv(ROOT / spec["book"], dtype={"cik10": str})
    frame = frame.rename(columns={spec["date_column"]: "decision_at",
                                  spec["weight_column"]: "weight"})
    # The residual composite's book is keyed by ticker; every other book here is
    # keyed by cik10, and so is every SEC price panel. Map it once rather than
    # teaching the pricing path two conventions.
    if spec.get("symbol_column"):
        mapping = ticker_to_cik()
        frame["cik10"] = frame[spec["symbol_column"]].astype(str).str.upper().map(mapping)
        frame.loc[frame.cik10.isna(), "cik10"] = frame.loc[frame.cik10.isna(), spec["symbol_column"]]
    frame["decision_at"] = pd.to_datetime(frame.decision_at, utc=True, errors="coerce")
    frame = frame.dropna(subset=["decision_at", "cik10", "weight"])
    best = None
    for source, relative in PRICES.items():
        returns = load_returns(relative)
        if returns is None:
            continue
        held = frame[frame.cik10.isin(returns.columns)]
        if held.empty:
            continue
        # Sweep the offset widely. Step 241 found the sector ensemble needs 3 and
        # the others need 1; a narrow sweep manufactures false negatives.
        for offset in range(-2, 5):
            aligned = known_good.align(held, returns.index, offset)
            if aligned.empty:
                continue
            rebuilt = known_good.simulate(aligned, returns, 50.0)
            if allocator is not None and leader is not None:
                # All three sources index differently on tz; normalise to naive.
                combined = pd.concat({"s": as_naive(rebuilt), "l": as_naive(leader)},
                                     axis=1).join(as_naive(allocator)).dropna()
                if len(combined) >= 40:
                    rebuilt = combined.leader * combined.l + combined.cash_conversion * combined.s
            joined = pd.concat({"a": as_naive(rebuilt), "b": as_naive(reference)},
                               axis=1, sort=True).dropna()
            joined = joined[joined.a.ne(0.0) | joined.b.ne(0.0)]
            if len(joined) < 40:
                continue
            # Sweep the date-LABELLING shift as well as the execution offset. These
            # are different things and only one of them was swept here at first,
            # which reproduced Step 238's bug exactly: every strategy came back at
            # a correlation near -0.02 and the audit was about to report that not
            # one dashboard strategy could be rebuilt. Executing a week earlier
            # barely moves a book that rebalances fourteen times in 188 weeks;
            # labelling the same weekly return with a different Friday moves the
            # correlation from -0.02 to +0.90.
            labels = {shift: float(joined.a.shift(shift).corr(joined.b))
                      for shift in (-2, -1, 0, 1, 2)}
            labels = {k: v for k, v in labels.items() if np.isfinite(v)}
            if not labels:
                continue
            label_shift = max(labels, key=lambda k: labels[k])
            corr = labels[label_shift]
            if not np.isfinite(corr):
                continue
            cand = {"price_source": source, "offset": offset, "label_shift": label_shift,
                    "correlation": corr, "weeks": len(joined),
                    "rebuilt_cagr": known_good.compound(joined.a),
                    "reference_cagr": known_good.compound(joined.b)}
            if best is None or corr > best["correlation"]:
                best = cand
    if best is None:
        row["reproduced"] = False
        row["best_correlation"] = None
        row["blocked_by"] = "no price source and offset produced a comparable series"
        return row
    row.update({f"match_{k}": v for k, v in best.items()})
    row["best_correlation"] = best["correlation"]
    row["reproduced"] = bool(best["correlation"] >= MATCH)
    row["blocked_by"] = None if row["reproduced"] else "book reprices but does not match the published path"
    return row


def main() -> int:
    dashboard = json.loads(DASHBOARD.read_text())["strategies"]
    records_by_id = {s["strategy"]["id"]: s.get("records", []) for s in dashboard}
    published = set(records_by_id)
    missing = published - set(STRATEGIES)
    if missing:
        print(f"WARNING: dashboard carries strategies this audit does not cover: {sorted(missing)}")

    symbol_map = ticker_to_cik()
    print(f"ticker -> cik10 map: {len(symbol_map)} symbols\n")
    rows = []
    for name, spec in STRATEGIES.items():
        row = audit_one(name, spec)
        holdings_check = reprice_published_holdings(records_by_id.get(name, []), symbol_map)
        row["holdings_reprice_correlation"] = holdings_check.get("correlation")
        row["holdings_symbol_coverage"] = holdings_check.get("symbol_coverage")
        row["holdings_rebuilt_cagr"] = holdings_check.get("rebuilt_cagr")
        row["holdings_published_cagr"] = holdings_check.get("published_cagr")
        row["holdings_reproduced"] = bool(
            holdings_check.get("correlation") is not None
            and holdings_check["correlation"] >= MATCH)
        rows.append(row)
    frame = pd.DataFrame(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "reproducibility.csv", index=False)

    print(f"{'strategy':44s} {'bookcorr':>8s} {'holdcorr':>8s} {'cover':>6s} {'manifest':>8s}")
    for r in rows:
        bc = f"{r['best_correlation']:+.3f}" if r["best_correlation"] is not None else "    -   "
        hc = f"{r['holdings_reprice_correlation']:+.3f}" if r["holdings_reprice_correlation"] is not None else "    -   "
        cv = f"{r['holdings_symbol_coverage']:.1%}" if r["holdings_symbol_coverage"] is not None else "   -  "
        print(f"{r['strategy']:44s} {bc:>8s} {hc:>8s} {cv:>6s} {str(r['has_frozen_manifest']):>8s}")

    result = {
        "strategies_on_dashboard": len(published),
        "audited": len(rows),
        "with_saved_book": int(sum(r["has_saved_book"] for r in rows)),
        "reproduced_from_saved_book": int(sum(bool(r["reproduced"]) for r in rows)),
        "reproduced_from_published_holdings": int(sum(bool(r["holdings_reproduced"]) for r in rows)),
        "with_frozen_manifest": int(sum(r["has_frozen_manifest"] for r in rows)),
        "with_rebuild_script": int(sum(r["has_rebuild_script"] for r in rows)),
        "match_threshold": MATCH,
        "what_reproduction_here_does_and_does_not_show": (
            "It shows the saved weights reprice to the published path. It does NOT show the "
            "weights could be derived again from raw data, which is what a frozen manifest is for."
        ),
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("\n" + json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
