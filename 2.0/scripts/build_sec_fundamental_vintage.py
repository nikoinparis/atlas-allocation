#!/usr/bin/env python3
"""Download and normalize a cached point-in-time SEC Company Facts vintage."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_point_in_time import (
    SecClient, flatten_companyfacts, flatten_submissions, point_in_time_event_panel,
    ticker_mapping, validate_facts,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config/sec_fundamental_pilot_v1.json"))
    parser.add_argument("--output-root", default=str(ROOT / "data/sec_vintages"))
    parser.add_argument("--cache-root", default=None, help="Reuse an existing raw SEC cache without new requests")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    config = json.loads(Path(args.config).read_text())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output_root) / f"{stamp}-sec-pit-v1"
    cache = Path(args.cache_root).resolve() if args.cache_root else output / "raw"
    client = SecClient.from_environment(
        cache, minimum_interval=float(config["minimum_seconds_between_requests"]),
        timeout=int(config["request_timeout_seconds"]),
    )
    mapping_payload, mapping_meta = client.fetch_json(config["source_endpoints"]["ticker_mapping"], "company_tickers_exchange")
    mapping = ticker_mapping(mapping_payload)
    requested = [ticker for sector in config["pilot_universe"].values() for ticker in sector]
    selected = mapping[mapping.ticker.isin(requested)].copy()
    missing = sorted(set(requested) - set(selected.ticker))
    if missing:
        raise RuntimeError(f"SEC ticker mapping missing {missing}")

    filing_frames, fact_frames, source_rows = [], [], [mapping_meta]
    for row in selected.itertuples(index=False):
        submissions_url = config["source_endpoints"]["submissions"].format(cik10=row.cik10)
        facts_url = config["source_endpoints"]["companyfacts"].format(cik10=row.cik10)
        submissions_payload, submissions_meta = client.fetch_json(submissions_url, f"submissions_{row.cik10}")
        additional = {}
        for file_spec in submissions_payload.get("filings", {}).get("files", []):
            name = file_spec["name"]
            payload, metadata = client.fetch_json(f"https://data.sec.gov/submissions/{name}", f"submissions_{row.cik10}_{name.removesuffix('.json')}")
            additional[name] = payload
            source_rows.append(metadata)
        filings = flatten_submissions(submissions_payload, additional)
        facts_payload, facts_meta = client.fetch_json(facts_url, f"companyfacts_{row.cik10}")
        facts = flatten_companyfacts(facts_payload, filings, config["canonical_metrics"], config["accepted_forms"])
        filings.insert(1, "ticker", row.ticker)
        filing_frames.append(filings)
        fact_frames.append(facts)
        source_rows.extend([submissions_meta, facts_meta])

    filings = pd.concat(filing_frames, ignore_index=True)
    facts = pd.concat(fact_frames, ignore_index=True)
    ticker_by_cik = selected.set_index("cik10").ticker.to_dict()
    events = point_in_time_event_panel(facts, ticker_by_cik)
    audit = validate_facts(facts)
    if not audit["valid"]:
        raise RuntimeError(f"fact audit failed: {audit}")

    output.mkdir(parents=True, exist_ok=True)
    selected.sort_values("ticker").to_csv(output / "universe.csv", index=False)
    filings.to_csv(output / "filings.csv", index=False)
    events.to_csv(output / "fundamental_events.csv", index=False)
    pd.DataFrame(source_rows).to_csv(output / "source_manifest.csv", index=False)
    manifest = {
        "vintage_id": output.name, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(Path(args.config).resolve()), "pilot_tickers": sorted(requested),
        "universe_warning": config["universe_warning"], "availability_rule": config["availability_rule"],
        "amendment_rule": config["amendment_rule"], "audit": audit, "source_files": len(source_rows),
        "raw_cache": str(cache),
        "strategy_testing_authorized": False, "live_trading_enabled": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
