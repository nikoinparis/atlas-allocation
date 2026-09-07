#!/usr/bin/env python3
"""Rebuild growth, cash conversion and balance-sheet quality for 2012-2022 and test them.

Step 287 found earnings yield keeps 3% of its in-sample excess out of sample and
lands with a Sharpe below its own scored universe. That result only means
something if the other dashboard signals get the same test; otherwise it reads as
one weak signal rather than as a property of the 2023-2026 window everything here
was selected on.

Every construction is taken verbatim from the config that froze it -- features,
minimum feature count, breadth, equal weighting, sector-neutral ranking -- and
none is varied. If a signal fails, the finding is that its in-sample result was
selection.

Two things keep the comparison honest:

The universe is restricted to the same 38 SIC codes the in-sample roster covers.
This project's SEC panel is a technology-and-energy universe, not the whole
market, and testing these signals on all filers would be testing a different
strategy that happened to share a name.

Each book is compared to ITS OWN scored universe in the SAME window, never to the
other window's headline CAGR. The two periods use differently-built rosters and
comparing their raw returns would compare two survivorship treatments.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FSDS = ROOT / "data/sec_fsds_history_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
BROAD = ROOT / "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz"
SECTORS = ROOT / "evidence/valuation_out_of_sample_v1/sic_to_sector.json"
OUTPUT = ROOT / "evidence/dashboard_signals_out_of_sample_v1"
COST_BPS = 50.0

TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities",
                            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets"],
    "assets": ["Assets"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "liabilities": ["Liabilities"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "debt": ["LongTermDebtNoncurrent", "LongTermDebt", "DebtCurrent"],
}
FLOW = {"revenue", "net_income", "operating_cash_flow", "capex"}
ALL_TAGS = {t for v in TAGS.values() for t in v}

SIGNALS = {
    "growth_top5": {"positive": ["revenue__yoy_growth", "net_income__yoy_growth",
                                 "operating_cash_flow__yoy_growth"],
                    "negative": [], "minimum": 2, "breadth": 5},
    "cash_conversion_breadth20": {"positive": ["operating_cash_flow_margin", "free_cash_flow_margin",
                                               "cash_conversion_spread"],
                                  "negative": [], "minimum": 2, "breadth": 20},
    "balance_sheet_quality": {"positive": ["cash_to_assets", "equity_to_assets"],
                              "negative": ["debt_to_assets", "liabilities_to_assets"],
                              "minimum": 2, "breadth": 20},
}
IN_SAMPLE_EXCESS = {"growth_top5": 0.1179, "cash_conversion_breadth20": 0.10,
                    "balance_sheet_quality": 0.10}


def read_quarter(path: Path) -> pd.DataFrame | None:
    try:
        with zipfile.ZipFile(path) as archive:
            with archive.open("sub.txt") as handle:
                sub = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["adsh", "cik", "sic", "form", "filed"], low_memory=False)
            sub = sub[sub.form.astype(str).str.upper().isin(["10-K", "10-Q"])]
            if sub.empty:
                return None
            with archive.open("num.txt") as handle:
                num = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["adsh", "tag", "ddate", "qtrs", "uom",
                                           "segments", "coreg", "value"], low_memory=False)
    except Exception:                                # noqa: BLE001
        return None
    num = num[num.segments.isna() & num.coreg.isna() & num.tag.isin(ALL_TAGS) & (num.uom == "USD")]
    if num.empty:
        return None
    return num.merge(sub, on="adsh", how="inner")


def build_facts() -> pd.DataFrame:
    frames = [q for path in sorted(FSDS.glob("*.zip")) if (q := read_quarter(path)) is not None]
    facts = pd.concat(frames, ignore_index=True)
    facts["filed"] = pd.to_datetime(facts.filed, format="%Y%m%d", errors="coerce", utc=True)
    facts["ddate"] = pd.to_datetime(facts.ddate, format="%Y%m%d", errors="coerce", utc=True)
    facts = facts.dropna(subset=["filed", "ddate", "value", "sic"])
    facts["cik10"] = facts.cik.astype("int64").astype(str).str.zfill(10)
    facts["sic4"] = facts.sic.astype("int64").astype(str).str.zfill(4)

    sectors = json.loads(SECTORS.read_text())
    facts["sector"] = facts.sic4.map(sectors)
    facts = facts.dropna(subset=["sector"])          # the in-sample universe restriction

    inverse = {tag: field for field, tags in TAGS.items() for tag in tags}
    facts["field"] = facts.tag.map(inverse)
    # Flow items are the trailing-four-quarter figure; stock items are point-in-time.
    facts = facts[((facts.field.isin(FLOW)) & (facts.qtrs == 4))
                  | ((~facts.field.isin(FLOW)) & (facts.qtrs == 0))]
    ranked = facts.sort_values(["cik10", "filed", "ddate"])
    wide = (ranked.groupby(["cik10", "sector", "filed", "field"]).value.last()
            .unstack("field").reset_index())
    return wide.sort_values(["cik10", "filed"])


def add_features(wide: pd.DataFrame) -> pd.DataFrame:
    frame = wide.copy()
    revenue = frame.get("revenue")
    frame["free_cash_flow"] = frame.get("operating_cash_flow") - frame.get("capex", 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        frame["operating_cash_flow_margin"] = frame.get("operating_cash_flow") / revenue
        frame["free_cash_flow_margin"] = frame.free_cash_flow / revenue
        frame["net_margin"] = frame.get("net_income") / revenue
        frame["cash_conversion_spread"] = frame.operating_cash_flow_margin - frame.net_margin
        frame["cash_to_assets"] = frame.get("cash") / frame.get("assets")
        frame["equity_to_assets"] = frame.get("equity") / frame.get("assets")
        frame["debt_to_assets"] = frame.get("debt") / frame.get("assets")
        frame["liabilities_to_assets"] = frame.get("liabilities") / frame.get("assets")
    # Year-on-year growth against the same issuer's figure roughly four quarters back.
    for field in ("revenue", "net_income", "operating_cash_flow"):
        prior = frame.groupby("cik10")[field].shift(4)
        with np.errstate(divide="ignore", invalid="ignore"):
            frame[f"{field}__yoy_growth"] = (frame[field] - prior) / prior.abs()
    return frame.replace([np.inf, -np.inf], np.nan)


def score(block: pd.DataFrame, spec: dict) -> pd.Series:
    """Sector-neutral mean of ranked features, as the frozen configs specify."""
    columns = []
    for feature in spec["positive"] + spec["negative"]:
        if feature not in block.columns:
            continue
        sign = -1.0 if feature in spec["negative"] else 1.0
        ranked = block.groupby("sector")[feature].rank(pct=True)
        columns.append(sign * ranked)
    if not columns:
        return pd.Series(dtype=float)
    matrix = pd.concat(columns, axis=1)
    return matrix.mean(axis=1).where(matrix.notna().sum(axis=1) >= spec["minimum"])


def metrics(returns: pd.Series) -> dict[str, float]:
    if len(returns) < 20:
        return {}
    years = len(returns) / 52.0
    total = float((1.0 + returns).prod())
    cagr = total ** (1.0 / years) - 1.0 if total > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + returns).cumprod()
    return {"cagr": cagr, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "volatility": vol, "max_drawdown": float((curve / curve.cummax() - 1.0).min())}


def simulate(schedule: dict, returns: pd.DataFrame) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    rows, started = [], min(schedule) if schedule else None
    for week in returns.index:
        if started is None or week < started:
            continue
        cost = 0.0
        if week in schedule:
            names = [n for n in schedule[week] if n in returns.columns]
            if names:
                target = pd.Series(0.0, index=returns.columns, dtype=float)
                target[names] = 1.0 / len(names)
                cost = float((target - holdings).abs().sum()) / 2.0 * COST_BPS / 10_000.0
                holdings = target
        row = returns.loc[week].fillna(0.0)
        rows.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    return pd.Series(dict(rows)).sort_index()


def load_prices() -> pd.DataFrame:
    frames = []
    for path in (PRICES, BROAD):
        if not path.is_file():
            continue
        frame = pd.read_csv(path, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
        frame.index = pd.to_datetime(frame.index, utc=True)
        frame.columns = [str(c) for c in frame.columns]
        frames.append(frame)
    combined = frames[0]
    for extra in frames[1:]:
        combined = combined.join(extra[[c for c in extra.columns if c not in combined.columns]],
                                 how="outer")
    return combined.sort_index()


def main() -> int:
    prices = load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    facts = add_features(build_facts())
    facts = facts[facts.cik10.isin(prices.columns)]
    print(f"FSDS facts: {len(facts):,} filings, {facts.cik10.nunique():,} issuers in the "
          f"tech+energy universe, {facts.filed.min().date()} -> {facts.filed.max().date()}")

    decisions = pd.date_range("2013-04-01", "2022-10-01", freq="QS", tz="UTC")
    results, paths = {}, {}
    for name, spec in SIGNALS.items():
        book_schedule, universe_schedule, coverage = {}, {}, []
        for decision in decisions:
            known = facts[facts.filed < decision]     # point in time
            if known.empty:
                continue
            latest = known.sort_values("filed").groupby("cik10").last()
            latest = latest[latest.index.isin(returns.columns)]
            if len(latest) < spec["breadth"] * 2:
                continue
            scored = score(latest, spec).dropna()
            if len(scored) < spec["breadth"]:
                continue
            execution = returns.index[returns.index > decision]
            if not len(execution):
                continue
            week = execution[0]
            book_schedule[week] = list(scored.nlargest(spec["breadth"]).index)
            universe_schedule[week] = list(scored.index)
            coverage.append(len(scored))
        if len(book_schedule) < 20:
            results[name] = {"inconclusive": f"only {len(book_schedule)} decisions built"}
            continue
        book = simulate(book_schedule, returns)
        universe = simulate(universe_schedule, returns)
        joined = pd.concat({"book": book, "universe": universe}, axis=1).dropna().loc[:"2023-01-01"]
        bm, um = metrics(joined.book), metrics(joined.universe)
        excess = bm["cagr"] - um["cagr"]
        retained = excess / IN_SAMPLE_EXCESS[name]
        beats = bm["sharpe"] > um["sharpe"]
        results[name] = {
            "decisions": len(book_schedule), "median_scored": int(np.median(coverage)),
            "weeks": len(joined), "book": bm, "universe": um, "excess_cagr": excess,
            "in_sample_excess": IN_SAMPLE_EXCESS[name],
            "excess_retained_share": retained, "book_sharpe_beats_universe": beats,
            "supports": bool(excess > 0 and retained >= 0.25 and beats),
        }
        paths[name] = joined.book

    print()
    for name, r in results.items():
        if "inconclusive" in r:
            print(f"{name}: INCONCLUSIVE ({r['inconclusive']})")
            continue
        print(f"{name}   ({r['decisions']} decisions, median {r['median_scored']} scored, {r['weeks']} weeks)")
        print(f"  book      CAGR {r['book']['cagr']:7.2%}  Sharpe {r['book']['sharpe']:6.3f}  maxDD {r['book']['max_drawdown']:7.2%}")
        print(f"  universe  CAGR {r['universe']['cagr']:7.2%}  Sharpe {r['universe']['sharpe']:6.3f}  maxDD {r['universe']['max_drawdown']:7.2%}")
        print(f"  EXCESS {r['excess_cagr']:+.2%}   in-sample was {r['in_sample_excess']:+.1%}   "
              f"retained {r['excess_retained_share']:.0%}   Sharpe beats universe: {r['book_sharpe_beats_universe']}")
        print(f"  -> {'SUPPORTS' if r['supports'] else 'REFUTES'}\n")

    supported = [k for k, v in results.items() if v.get("supports")]
    print(f"signals whose in-sample edge survives out of sample: {len(supported)} of {len(results)}"
          + (f" -- {supported}" if supported else ""))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        path.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / f"path__{name}__50bps.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "window": "2013-2022", "cost_bps": COST_BPS, "universe": "tech+energy SIC codes from the in-sample roster",
        "constructions_frozen": True, "results": results, "supported": supported,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
