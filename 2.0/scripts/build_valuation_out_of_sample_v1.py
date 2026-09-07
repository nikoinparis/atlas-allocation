#!/usr/bin/env python3
"""Rebuild the earnings-yield book for 2012-2022 and test it out of sample.

Declared in config/valuation_out_of_sample_registry_v1.json. The construction is
frozen to the values already on the forward clock -- breadth 20, equal weight,
quarterly, 50bps -- and none of them will be varied. If the out-of-sample result
is poor the finding is that the in-sample result was selection; it is not an
invitation to try a different breadth.

Point-in-time by construction. A filing enters the universe only from its `filed`
date, never its period end, so a 10-K for December 2015 filed in March 2016 is
invisible to a January 2016 decision. This is the property CLAUDE.md rule 4 is
about and it is the whole reason for using the Financial Statement Data Sets
rather than a modern fundamentals vendor.

The comparison that matters is each period's book against ITS OWN scored
universe, not 2012-2022's CAGR against 2023-2026's. The two windows use
differently-built universes and comparing their headline returns would be
comparing two different survivorship treatments.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/valuation_out_of_sample_registry_v1.json"
FSDS = ROOT / "data/sec_fsds_history_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
BROAD = ROOT / "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/valuation_out_of_sample_v1"
BREADTH, COST_BPS = 20, 50.0
INCOME_TAGS = {"NetIncomeLoss", "ProfitLoss",
               "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest"}
SHARE_TAGS = {"EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding",
              "WeightedAverageNumberOfDilutedSharesOutstanding",
              "WeightedAverageNumberOfSharesOutstandingBasic"}


def read_quarter(path: Path) -> pd.DataFrame | None:
    try:
        with zipfile.ZipFile(path) as archive:
            with archive.open("sub.txt") as handle:
                sub = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["adsh", "cik", "name", "form", "period", "filed"],
                                  low_memory=False)
            sub = sub[sub.form.astype(str).str.upper().isin(["10-K", "10-Q"])]
            if sub.empty:
                return None
            with archive.open("num.txt") as handle:
                num = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["adsh", "tag", "ddate", "qtrs", "uom", "segments",
                                           "coreg", "value"], low_memory=False)
    except Exception:                                # noqa: BLE001
        return None
    # Consolidated parent-company figures only: a segment or co-registrant row is a
    # slice of the company, and summing or picking among them silently changes what
    # the ratio means.
    num = num[num.segments.isna() & num.coreg.isna()]
    num = num[num.tag.isin(INCOME_TAGS | SHARE_TAGS)]
    return num.merge(sub, on="adsh", how="inner")


def build_facts() -> pd.DataFrame:
    frames = []
    for path in sorted(FSDS.glob("*.zip")):
        quarter = read_quarter(path)
        if quarter is not None and not quarter.empty:
            frames.append(quarter)
    facts = pd.concat(frames, ignore_index=True)
    facts["filed"] = pd.to_datetime(facts.filed, format="%Y%m%d", errors="coerce", utc=True)
    facts["ddate"] = pd.to_datetime(facts.ddate, format="%Y%m%d", errors="coerce", utc=True)
    facts = facts.dropna(subset=["filed", "ddate", "value"])
    facts["cik10"] = facts.cik.astype("int64").astype(str).str.zfill(10)

    income = facts[facts.tag.isin(INCOME_TAGS) & (facts.qtrs == 4) & (facts.uom == "USD")]
    shares = facts[facts.tag.isin(SHARE_TAGS) & (facts.uom == "shares")]
    income = (income.sort_values(["cik10", "filed", "ddate"])
              .groupby(["cik10", "filed"]).value.last().rename("net_income").reset_index())
    shares = (shares.sort_values(["cik10", "filed", "ddate"])
              .groupby(["cik10", "filed"]).value.last().rename("shares").reset_index())
    merged = income.merge(shares, on=["cik10", "filed"], how="inner")
    return merged[(merged.shares > 0)]


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


def simulate(schedule: dict, returns: pd.DataFrame, cost_bps: float) -> pd.Series:
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
                cost = float((target - holdings).abs().sum()) / 2.0 * cost_bps / 10_000.0
                holdings = target
        row = returns.loc[week].fillna(0.0)
        rows.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    return pd.Series(dict(rows)).sort_index()


def main() -> int:
    json.loads(REGISTRY.read_text())
    prices = load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    facts = build_facts()
    facts = facts[facts.cik10.isin(prices.columns)]

    decisions = pd.date_range("2012-04-01", "2022-10-01", freq="QS", tz="UTC")
    book_schedule, universe_schedule, coverage = {}, {}, []
    for decision in decisions:
        # Point in time: only filings the market had already seen.
        known = facts[facts.filed < decision]
        if known.empty:
            continue
        latest = known.sort_values("filed").groupby("cik10").last()
        week_candidates = prices.index[prices.index <= decision]
        if not len(week_candidates):
            continue
        week = week_candidates[-1]
        price_row = prices.loc[week].reindex(latest.index)
        market_cap = price_row * latest.shares
        yield_ = (latest.net_income / market_cap).replace([np.inf, -np.inf], np.nan)
        # Loss-makers have a negative earnings yield that is not "cheap"; the frozen
        # book ranks on earnings yield among profitable issuers.
        scored = yield_[(market_cap > 0) & (latest.net_income > 0) & yield_.notna()]
        scored = scored[scored.index.isin(returns.columns)]
        execution = returns.index[returns.index > decision]
        if len(scored) < BREADTH or not len(execution):
            continue
        run_week = execution[0]
        book_schedule[run_week] = list(scored.nlargest(BREADTH).index)
        universe_schedule[run_week] = list(scored.index)
        coverage.append({"decision": str(decision.date()), "scored": int(len(scored))})

    if len(book_schedule) < 24:
        print(f"INCONCLUSIVE: only {len(book_schedule)} quarterly decisions built, need 24")
        return 1

    book = simulate(book_schedule, returns, COST_BPS)
    universe = simulate(universe_schedule, returns, COST_BPS)
    joined = pd.concat({"book": book, "universe": universe}, axis=1).dropna()
    joined = joined.loc[:"2023-01-01"]
    bm, um = metrics(joined.book), metrics(joined.universe)
    excess = bm["cagr"] - um["cagr"]

    print(f"quarterly decisions built: {len(book_schedule)}   "
          f"median scored issuers: {int(np.median([c['scored'] for c in coverage]))}")
    print(f"window {joined.index.min().date()} -> {joined.index.max().date()}  ({len(joined)} weeks)\n")
    print(f"  {'earnings-yield book':24s} CAGR {bm['cagr']:7.2%}  Sharpe {bm['sharpe']:6.3f}  maxDD {bm['max_drawdown']:7.2%}")
    print(f"  {'its own scored universe':24s} CAGR {um['cagr']:7.2%}  Sharpe {um['sharpe']:6.3f}  maxDD {um['max_drawdown']:7.2%}")
    print(f"  EXCESS over its own universe: {excess:+.2%}\n")
    print(f"in-sample 2023-2026 excess was +14.5pp before the break and +10.7pp after")
    # The first version of this verdict asked only `excess > 0` and printed
    # "SUPPORTS the book" for an excess of +0.38pp against an in-sample +14.5pp,
    # while the book's Sharpe was BELOW its own universe. That is the ninth
    # verdict function in this project to check whether a number cleared a bar
    # without asking whether the number could mean anything. Support requires the
    # excess to retain a meaningful fraction of the in-sample edge AND the book to
    # be worth holding over its universe on a risk-adjusted basis.
    retained = excess / 0.145 if 0.145 else float("nan")
    beats_universe_on_sharpe = bm["sharpe"] > um["sharpe"]
    if excess > 0 and retained >= 0.25 and beats_universe_on_sharpe:
        verdict = "SUPPORTS the book: the out-of-sample excess retains a meaningful share of the in-sample edge"
    elif excess > 0:
        verdict = (f"REFUTES the book: the excess shrinks to {excess:+.2%}, {retained:.0%} of the "
                   f"in-sample +14.5pp, and the book's Sharpe is "
                   f"{'above' if beats_universe_on_sharpe else 'BELOW'} its own universe. "
                   f"A positive sign at this magnitude is noise, not evidence.")
    else:
        verdict = "REFUTES the book: the in-sample excess does not appear in 2012-2022"
    print(f"VERDICT: {verdict}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    joined.book.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / "path__book__50bps.csv")
    joined.universe.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / "path__universe__50bps.csv")
    pd.DataFrame(coverage).to_csv(OUTPUT / "coverage.csv", index=False)
    (OUTPUT / "result.json").write_text(json.dumps({
        "decisions_built": len(book_schedule),
        "median_scored_issuers": int(np.median([c["scored"] for c in coverage])),
        "window": [str(joined.index.min().date()), str(joined.index.max().date())],
        "weeks": int(len(joined)),
        "book": bm, "universe": um, "excess_cagr": excess,
        "in_sample_excess_pre_break": 0.145, "in_sample_excess_post_break": 0.107,
        "verdict": verdict, "construction_frozen": True,
        "excess_retained_share_of_in_sample": excess / 0.145,
        "book_sharpe_beats_universe": bool(bm["sharpe"] > um["sharpe"]),
        "breadth": BREADTH, "cost_bps": COST_BPS,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
