#!/usr/bin/env python3
"""Measure every saved strategy against the concentration gate it currently fails.

Each book is first reduced to the cash it actually has (1.00x, no financing and no
borrowing), then issuer, single-fund, total-fund and look-through sector caps are
applied iteratively. Released weight goes to cash and is never reinvested.

This measures risk geometry only. It deliberately does not claim a capped return
series: the dashboard export cannot be repriced from its own holdings and prices,
so capped returns must come from re-running each strategy against the research panel.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/unlevered_concentration_caps_v1.json"
OUTPUT = ROOT / "evidence/unlevered_concentration_caps_v1"
PUBLIC = ROOT / "dashboard/public/concentration-caps.json"
CASH = "cash::USD"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_map(path: Path) -> dict[str, dict[str, str]]:
    with path.open() as handle:
        return {row["symbol"].upper(): row for row in csv.DictReader(handle)}


def classify(symbol: str, sector_map: dict) -> str:
    return sector_map.get(symbol, {}).get("instrument_type", "equity")


def sector_of(symbol: str, sector_map: dict) -> str:
    return sector_map.get(symbol, {}).get("sector") or "unclassified"


def sector_exposure(weights: dict[str, float], sector_map: dict, look_through: dict) -> dict[str, float]:
    exposure: dict[str, float] = defaultdict(float)
    for symbol, weight in weights.items():
        if classify(symbol, sector_map) == "exchange_traded_product":
            split = look_through.get(symbol)
            if split:
                for sector, share in split.items():
                    exposure[sector] += weight * float(share)
            else:
                exposure["unclassified_exchange_traded"] += weight
        elif classify(symbol, sector_map) == "data_artifact":
            continue
        else:
            exposure[sector_of(symbol, sector_map)] += weight
    return dict(exposure)


def profile(weights: dict[str, float], sector_map: dict, look_through: dict) -> dict[str, float]:
    issuer = {s: w for s, w in weights.items() if classify(s, sector_map) not in {"exchange_traded_product", "data_artifact"}}
    funds = {s: w for s, w in weights.items() if classify(s, sector_map) == "exchange_traded_product"}
    sectors = sector_exposure(weights, sector_map, look_through)
    return {
        "max_single_issuer_weight": max(issuer.values(), default=0.0),
        "max_single_exchange_traded_weight": max(funds.values(), default=0.0),
        "max_total_exchange_traded_weight": sum(funds.values()),
        "max_look_through_sector_weight": max(sectors.values(), default=0.0),
        "invested_weight": sum(weights.values()),
    }


def apply_caps(weights: dict[str, float], sector_map: dict, look_through: dict, caps: dict, solver: dict) -> dict[str, float]:
    """Iteratively enforce every cap. Released weight is dropped to cash."""
    current = {s: float(w) for s, w in weights.items() if w > 0.0}
    for _ in range(int(solver["max_iterations"])):
        changed = False

        # 1. single issuer
        for symbol, weight in list(current.items()):
            if classify(symbol, sector_map) in {"exchange_traded_product", "data_artifact"}:
                continue
            if weight > caps["max_single_issuer_weight"] + solver["tolerance"]:
                current[symbol] = caps["max_single_issuer_weight"]
                changed = True

        # 2. single fund
        for symbol, weight in list(current.items()):
            if classify(symbol, sector_map) != "exchange_traded_product":
                continue
            if weight > caps["max_single_exchange_traded_weight"] + solver["tolerance"]:
                current[symbol] = caps["max_single_exchange_traded_weight"]
                changed = True

        # 3. total fund exposure, scaled proportionally
        funds = {s: w for s, w in current.items() if classify(s, sector_map) == "exchange_traded_product"}
        total_funds = sum(funds.values())
        if total_funds > caps["max_total_exchange_traded_weight"] + solver["tolerance"]:
            scale = caps["max_total_exchange_traded_weight"] / total_funds
            for symbol in funds:
                current[symbol] *= scale
            changed = True

        # 4. look-through sector, scaled proportionally across contributors
        sectors = sector_exposure(current, sector_map, look_through)
        for sector, exposure in sectors.items():
            if exposure <= caps["max_look_through_sector_weight"] + solver["tolerance"]:
                continue
            scale = caps["max_look_through_sector_weight"] / exposure
            for symbol, weight in list(current.items()):
                if classify(symbol, sector_map) == "exchange_traded_product":
                    share = float(look_through.get(symbol, {}).get(sector, 0.0))
                elif classify(symbol, sector_map) == "data_artifact":
                    share = 0.0
                else:
                    share = 1.0 if sector_of(symbol, sector_map) == sector else 0.0
                if share > 0.0:
                    current[symbol] = weight * (1.0 - share) + weight * share * scale
            changed = True

        if not changed:
            break
    return {s: w for s, w in current.items() if w > solver["tolerance"]}


def main() -> int:
    config = json.loads(CONFIG.read_text())
    caps = config["caps"]
    solver = config["solver"]
    sector_map = load_map(ROOT / config["sector_map"])
    look_through = {k: v for k, v in json.loads((ROOT / config["look_through_source"]).read_text())["concentration"]["look_through"].items() if isinstance(v, dict)}
    document = json.loads((ROOT / config["source_dashboard"]).read_text())

    strategies = []
    for item in document["strategies"]:
        meta = item["strategy"]
        rows = []
        for record in item["records"]:
            raw = {h["symbol"].upper(): float(h["weight"]) for h in record["holdings"] if h["symbol"] != CASH}
            gross = sum(raw.values())
            if gross <= 0:
                continue
            # reduce to the cash actually held
            unlevered = {s: w / gross * min(gross, 1.0) for s, w in raw.items()} if gross > 1.0 else dict(raw)
            capped = apply_caps(unlevered, sector_map, look_through, caps, solver)
            before = profile(unlevered, sector_map, look_through)
            after = profile(capped, sector_map, look_through)
            rows.append({
                "date": record["date"],
                "original_gross": gross,
                **{f"before_{k}": v for k, v in before.items()},
                **{f"after_{k}": v for k, v in after.items()},
                "cash_released": before["invested_weight"] - after["invested_weight"],
                "names_capped": sum(1 for s in unlevered if abs(unlevered[s] - capped.get(s, 0.0)) > solver["tolerance"]),
            })
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue

        def band(column: str) -> dict[str, float]:
            return {
                "median": float(frame[column].quantile(0.50)),
                "p95": float(frame[column].quantile(0.95)),
                "max": float(frame[column].max()),
            }

        gates = {}
        for key, limit in caps.items():
            gates[key] = {
                "cap": limit,
                "before_p95": band(f"before_{key}")["p95"],
                "after_p95": band(f"after_{key}")["p95"],
                "before_max": band(f"before_{key}")["max"],
                "after_max": band(f"after_{key}")["max"],
                "before_passes": bool(band(f"before_{key}")["max"] <= limit + solver["tolerance"]),
                "after_passes": bool(band(f"after_{key}")["max"] <= limit + solver["tolerance"]),
            }
        strategies.append({
            "id": meta["id"],
            "name": meta["name"],
            "short_name": meta["shortName"],
            "weeks": int(len(frame)),
            "used_leverage": bool(frame["original_gross"].max() > 1.0 + solver["tolerance"]),
            "max_original_gross": float(frame["original_gross"].max()),
            "gates": gates,
            "all_caps_pass_after": bool(all(g["after_passes"] for g in gates.values())),
            "cash_released": band("cash_released"),
            "average_invested_after": float(frame["after_invested_weight"].mean()),
            "average_names_capped": float(frame["names_capped"].mean()),
        })
        frame.to_csv(OUTPUT / f"{meta['id']}.csv", index=False) if OUTPUT.exists() else None

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for item in document["strategies"]:
        pass
    result = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "caps": caps,
        "exposure_policy": config["exposure_policy"],
        "strategies": strategies,
        "every_strategy_passes_after_caps": bool(all(s["all_caps_pass_after"] for s in strategies)),
        "return_impact_computed": False,
        "return_impact_note": config["return_impact_note"],
        "remaining_blocker": "52 untouched forward weeks per strategy; first eligible realization 2026-09-04.",
        "financing_used": False,
        "borrowing_used": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    PUBLIC.write_text(json.dumps(result, separators=(",", ":"), sort_keys=True))
    print(json.dumps({"strategies": len(strategies), "all_pass_after": result["every_strategy_passes_after_caps"]}, indent=2))
    for s in strategies:
        print(f"\n  {s['short_name']}  (gross {s['max_original_gross']:.2f}x, leverage={s['used_leverage']})")
        for key, g in s["gates"].items():
            flag = "PASS" if g["after_passes"] else "FAIL"
            print(f"     {key:<40} cap {g['cap']:.2f}  before_max {g['before_max']:.3f} -> after_max {g['after_max']:.3f}  {flag}")
        print(f"     cash released: median {s['cash_released']['median']:.3f}  p95 {s['cash_released']['p95']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
