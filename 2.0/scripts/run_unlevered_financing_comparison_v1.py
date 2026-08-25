#!/usr/bin/env python3
"""Pure-cash versus financed paths for every saved strategy.

The de-levering transform is the one already verified against the published
cash-only metric to zero absolute error. Four of the six strategies are already
1.00x, so their two paths are identical by construction.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dashboard/public/return-first-dashboard.json"
PUBLIC = ROOT / "dashboard/public/concentration-caps.json"
OUTPUT = ROOT / "evidence/unlevered_concentration_caps_v1"

# display exposure and the financing rate each levered path assumes
LEVERED = {
    "sec-residual-controlled-1.25x-5pct-v1": {"gross": 1.25, "rates": [0.05, 0.08]},
    "sec-sector-ensemble-fragile-1.35x-v1": {"gross": 1.35, "rates": [0.06, 0.08]},
}


def stats(returns: pd.Series, periods: int = 52) -> dict:
    values = returns.dropna().astype(float)
    wealth = (1.0 + values).cumprod()
    years = len(values) / periods
    deviation = values.std(ddof=1)
    return {
        "weeks": int(len(values)),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(values.mean() / deviation * math.sqrt(periods)) if deviation else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "ending_value_10000": float(wealth.iloc[-1] * 10000.0),
    }


def main() -> int:
    document = json.loads(SOURCE.read_text())
    payload = json.loads(PUBLIC.read_text())
    by_id = {s["id"]: s for s in payload["strategies"]}

    for item in document["strategies"]:
        sid = item["strategy"]["id"]
        index = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in item["records"]])
        displayed = pd.Series([float(r["netReturn"]) for r in item["records"]], index=index)

        spec = LEVERED.get(sid)
        if spec is None:
            cash_only = displayed
            paths = {"unlevered_1.00x": stats(cash_only.iloc[-52:])}
            benefits = False
            uplift = 0.0
        else:
            gross = spec["gross"]
            # displayed path already carries its own financing assumption
            base_rate = spec["rates"][0]
            financing = (gross - 1.0) * base_rate / 52.0
            cash_only = (displayed + financing) / gross
            paths = {"unlevered_1.00x": stats(cash_only.iloc[-52:])}
            for rate in spec["rates"]:
                levered = cash_only * gross - (gross - 1.0) * rate / 52.0
                paths[f"levered_{gross:.2f}x_{int(rate*100)}pct"] = stats(levered.iloc[-52:])
            best = max(v["cagr"] for k, v in paths.items() if k != "unlevered_1.00x")
            uplift = best - paths["unlevered_1.00x"]["cagr"]
            benefits = uplift >= 0.15

        entry = by_id.get(sid)
        if entry is None:
            continue
        entry["exposure"] = {
            "native_gross": spec["gross"] if spec else 1.0,
            "uses_financing": bool(spec),
            "benefits_heavily_from_financing": bool(benefits),
            "financing_uplift_cagr": float(uplift),
            "paths": paths,
            "default_path": "unlevered_1.00x",
            "note": ("This strategy is already pure cash. There is nothing borrowed and no financing to pay."
                     if not spec else
                     f"Unlevered is the default. Financing this book at {spec['gross']:.2f}x adds "
                     f"{uplift*100:.1f} points of trailing CAGR, and the same multiple to every loss."),
        }

    payload["financing_comparison_generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["default_exposure"] = "unlevered_1.00x"
    PUBLIC.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    (OUTPUT / "financing_comparison.json").write_text(json.dumps({s["id"]: s.get("exposure") for s in payload["strategies"]}, indent=2, sort_keys=True) + "\n")

    print(f"{'strategy':<26}{'unlevered':>12}{'financed':>12}{'uplift':>10}  flag")
    for s in payload["strategies"]:
        e = s.get("exposure", {})
        p = e.get("paths", {})
        un = p.get("unlevered_1.00x", {}).get("cagr", 0.0)
        lev = [v["cagr"] for k, v in p.items() if k != "unlevered_1.00x"]
        best = max(lev) if lev else un
        print(f"  {s['short_name']:<24}{un*100:>11.2f}%{best*100:>11.2f}%{(best-un)*100:>9.2f}pp  "
              f"{'BENEFITS' if e.get('benefits_heavily_from_financing') else 'pure cash' if not e.get('uses_financing') else 'modest'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
