#!/usr/bin/env python3
"""Where did the money actually come from?

This project has measured returns for two hundred steps and never once decomposed
them. Those are different questions. A return says how much was made; an
attribution says which positions and which weeks made it, and how much the trading
costs took back.

That distinction is not academic here. Step 188 discovered that Micron supplied
67.63% of one strategy's entire return, and discovered it by accident while looking
at something else. A book whose gain comes from four good weeks is a different
object from one that grinds, even when their annual returns match exactly.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/pnl_attribution_v1.json"
OUTPUT = ROOT / "evidence/pnl_attribution_v1"


def concentration(net: pd.Series) -> dict:
    """How few weeks supplied the gain?"""
    gains = net[net > 0].sort_values(ascending=False)
    total_gain = gains.sum()
    weeks_to_half, running = 0, 0.0
    for value in gains:
        running += value
        weeks_to_half += 1
        if running >= total_gain / 2:
            break
    return {
        "positive_weeks": int(len(gains)),
        "total_weeks": int(len(net)),
        "hit_rate": float((net > 0).mean()),
        "best_week_share_of_gain": float(gains.iloc[0] / total_gain) if len(gains) else float("nan"),
        "best_5_weeks_share_of_gain": float(gains.head(5).sum() / total_gain) if len(gains) else float("nan"),
        "best_10_weeks_share_of_gain": float(gains.head(10).sum() / total_gain) if len(gains) else float("nan"),
        "weeks_supplying_half_the_gain": int(weeks_to_half),
        "weeks_supplying_half_as_share": float(weeks_to_half / len(net)),
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    dashboard = json.loads((ROOT / config["strategy_source"]).read_text())

    books, gross_books, cost_books = {}, {}, {}
    for entry in dashboard["strategies"]:
        frame = pd.DataFrame(entry["records"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date")
        name = entry["strategy"]["shortName"]
        books[name] = frame["netReturn"].astype(float)
        gross_books[name] = frame["grossReturn"].astype(float)
        cost_books[name] = frame["cost"].astype(float)

    net = pd.DataFrame(books).dropna()
    gross = pd.DataFrame(gross_books).reindex(net.index)
    costs = pd.DataFrame(cost_books).reindex(net.index)
    net.index = net.index.tz_localize(None) if net.index.tz else net.index

    per_book = {}
    for name in net.columns:
        series = net[name]
        wealth = (1 + series).cumprod()
        years = len(series) / 52
        yearly = series.groupby(series.index.year).apply(lambda s: (1 + s).prod() - 1)
        per_book[name] = {
            "net_cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
            "gross_cagr": float((1 + gross[name].fillna(0)).cumprod().iloc[-1] ** (1 / years) - 1),
            "total_cost_paid_as_share_of_final_wealth": float(costs[name].fillna(0).sum() / wealth.iloc[-1]),
            "average_weekly_cost_bps": float(costs[name].fillna(0).mean() * 1e4),
            "by_calendar_year": {str(k): float(v) for k, v in yearly.items()},
            "concentration": concentration(series),
        }

    composite = net.mean(axis=1)
    wealth = (1 + composite).cumprod()
    years = len(composite) / 52
    yearly = composite.groupby(composite.index.year).apply(lambda s: (1 + s).prod() - 1)

    # How much of the composite's weekly return did each book supply?
    contribution = net.div(len(net.columns))
    total_contribution = contribution.sum()
    risk_share = net.std() / net.std().sum()

    composite_summary = {
        "net_cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "by_calendar_year": {str(k): float(v) for k, v in yearly.items()},
        "concentration": concentration(composite),
        "sleeve_contribution": {
            name: {
                "summed_weekly_contribution": float(total_contribution[name]),
                "share_of_total_contribution": float(total_contribution[name] / total_contribution.sum()),
                "share_of_total_risk": float(risk_share[name]),
                "contribution_per_unit_of_risk": float(
                    (total_contribution[name] / total_contribution.sum()) / risk_share[name]
                ),
            }
            for name in net.columns
        },
    }

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "window": {"weeks": int(len(net)), "first": str(net.index[0].date()), "last": str(net.index[-1].date())},
        "per_book": per_book,
        "equal_weight_composite": composite_summary,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print(f"window: {len(net)} weeks, {net.index[0].date()} to {net.index[-1].date()}\n")
    print("COST DRAG — what trading took back")
    print(f"  {'book':28s}{'gross':>9s}{'net':>9s}{'drag':>8s}{'avg wk cost':>13s}")
    for name, e in per_book.items():
        print(f"  {name:28s}{e['gross_cagr']*100:8.2f}%{e['net_cagr']*100:8.2f}%"
              f"{(e['gross_cagr']-e['net_cagr'])*100:7.2f}%{e['average_weekly_cost_bps']:12.1f}bp")

    print("\nCONCENTRATION — how few weeks supplied half the gain")
    print(f"  {'book':28s}{'hit rate':>10s}{'best wk':>9s}{'best 5':>8s}{'wks for half':>14s}")
    for name, e in per_book.items():
        c = e["concentration"]
        print(f"  {name:28s}{c['hit_rate']*100:9.1f}%{c['best_week_share_of_gain']*100:8.1f}%"
              f"{c['best_5_weeks_share_of_gain']*100:7.1f}%{c['weeks_supplying_half_the_gain']:8d} of {c['total_weeks']}")
    c = composite_summary["concentration"]
    print(f"  {'>> equal-weight composite':28s}{c['hit_rate']*100:9.1f}%{c['best_week_share_of_gain']*100:8.1f}%"
          f"{c['best_5_weeks_share_of_gain']*100:7.1f}%{c['weeks_supplying_half_the_gain']:8d} of {c['total_weeks']}")

    print("\nRETURN BY CALENDAR YEAR")
    years_seen = sorted(composite_summary["by_calendar_year"])
    header = "".join(f"{y:>10s}" for y in years_seen)
    print(f"  {'book':28s}{header}")
    for name, e in per_book.items():
        row = "".join(f"{e['by_calendar_year'].get(y, float('nan'))*100:9.1f}%" for y in years_seen)
        print(f"  {name:28s}{row}")
    row = "".join(f"{composite_summary['by_calendar_year'][y]*100:9.1f}%" for y in years_seen)
    print(f"  {'>> equal-weight composite':28s}{row}")

    print("\nSLEEVE CONTRIBUTION vs RISK CONSUMED (composite)")
    print(f"  {'book':28s}{'of return':>11s}{'of risk':>10s}{'ratio':>8s}")
    for name, e in composite_summary["sleeve_contribution"].items():
        print(f"  {name:28s}{e['share_of_total_contribution']*100:10.1f}%{e['share_of_total_risk']*100:9.1f}%"
              f"{e['contribution_per_unit_of_risk']:8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
