#!/usr/bin/env python3
"""Targeted point-in-time extraction of income tax and inventory.

Configurations B3 and B4 of `breadth_first_signal_registry_v1` were declared before
it was known that the rebuilt quarterly factor inputs carry equity, revenue and
assets but neither income tax nor inventory. Rather than quietly drop two declared
tests, this extracts exactly those two quantities.

It deliberately does not route through `quarterly_factor_inputs`. That function
selects on hardcoded `flow_metrics` and `balance_metrics` sets, so a new canonical
name is filtered out entirely, and widening those sets would perturb the discovery
pipeline whose scores were just regenerated and verified. `flatten_companyfacts`
and `classify_periods` are generic, so the point-in-time rule is applied here
directly and identically: a fact counts at a decision only if it was available
strictly before it.
"""

from __future__ import annotations

import concurrent.futures
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_point_in_time import classify_periods, flatten_companyfacts

FACT_CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
INPUTS = ROOT / "evidence/sec_independent_fundamental_discovery_v1/quarterly_factor_inputs.csv"
PILOT = ROOT / "config/sec_fundamental_pilot_v1.json"
OUTPUT = ROOT / "evidence/tax_inventory_inputs_v1"

CANONICAL = {
    "income_tax": ["IncomeTaxExpenseBenefit", "IncomeTaxExpenseBenefitContinuingOperations"],
    "inventory": ["InventoryNet"],
}
FLOW = {"income_tax"}
STOCK = {"inventory"}


def latest_submissions() -> Path:
    values = sorted(ROOT.glob("data/sec_historical_universe_vintages/*-sec-historical-filers-v1"))
    return values[-1] / "qualifying_submissions.csv"


def build_one(task):
    cik10, filing_records, decisions, forms = task
    path = FACT_CACHE / f"companyfacts_{cik10}.gz"
    if not path.exists():
        return []
    try:
        payload = json.loads(gzip.decompress(path.read_bytes()))
    except Exception:
        return []
    filings = pd.DataFrame(filing_records, columns=["accession", "available_at"])
    filings["available_at"] = pd.to_datetime(filings["available_at"], utc=True, errors="coerce")
    facts = flatten_companyfacts(payload, filings, CANONICAL, forms)
    if facts.empty:
        return []
    facts["period_kind"] = classify_periods(facts)
    facts["available_at"] = pd.to_datetime(facts["available_at"], utc=True)
    facts = facts[facts.unit == "USD"]

    rows = []
    for decision in decisions:
        eligible = facts[facts.available_at < decision]
        eligible = eligible[
            (eligible.canonical_metric.isin(FLOW) & (eligible.period_kind == "quarter"))
            | (eligible.canonical_metric.isin(STOCK) & (eligible.period_kind == "instant"))
        ]
        if eligible.empty:
            continue
        snapshot = {"decision_time": decision, "cik10": cik10}
        for metric, block in eligible.groupby("canonical_metric"):
            latest = block.sort_values(["end", "available_at", "concept_priority"]).iloc[-1]
            snapshot[metric] = float(latest.value)
        rows.append(snapshot)
    return rows


def main() -> int:
    forms = json.loads(PILOT.read_text())["accepted_forms"]
    inputs = pd.read_csv(INPUTS, usecols=["decision_time", "cik10"], dtype={"cik10": str}, low_memory=False)
    inputs["decision_time"] = pd.to_datetime(inputs.decision_time, utc=True)
    decisions = sorted(inputs.decision_time.unique())
    ciks = sorted(set(inputs.cik10))
    print(f"extracting income tax and inventory for {len(ciks)} issuers over {len(decisions)} decisions", flush=True)

    subs = pd.read_csv(latest_submissions(), dtype={"cik10": str}, usecols=["adsh", "cik10", "available_at"])
    subs = subs.rename(columns={"adsh": "accession"})
    by_cik = {c: g[["accession", "available_at"]].values.tolist() for c, g in subs.groupby("cik10")}

    tasks = [(c, by_cik.get(c, []), decisions, forms) for c in ciks]
    rows = []
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for n, out in enumerate(pool.map(build_one, tasks, chunksize=16), 1):
            rows.extend(out)
            if n % 250 == 0:
                print(f"  {n}/{len(tasks)}", flush=True)

    frame = pd.DataFrame(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "tax_inventory_inputs.csv", index=False)
    payload = {
        "experiment": "tax_inventory_inputs_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "issuers_requested": len(ciks), "rows": int(len(frame)),
        "decisions": int(frame.decision_time.nunique()) if len(frame) else 0,
        "income_tax_nonnull": int(frame.get("income_tax", pd.Series(dtype=float)).notna().sum()),
        "inventory_nonnull": int(frame.get("inventory", pd.Series(dtype=float)).notna().sum()),
        "availability_rule": "a fact counts at a decision only if available strictly before it",
        "live_trading_enabled": False,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
