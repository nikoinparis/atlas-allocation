#!/usr/bin/env python3
"""A32 input: 8-K Item 2.02 acceptance times for EVERY price-panel issuer (v1 covered only the top 500 by
liquidity). Same fetcher, parser and cache as v1; written to a new folder so A28's inputs stay unchanged."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import acquire_results_dates_v1 as v1  # noqa: E402
import acquire_sec_earnings_8k_v1 as e8k  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

OUTPUT = ROOT / "data/results_dates_v2"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(e8k.CONFIG.read_text())
    targets = list(a19.load_daily().columns)
    fetcher = e8k.Fetcher(e8k.DEFAULT_CACHE, v1.UA, config["minimum_seconds_between_requests"],
                          config["request_timeout_seconds"], config["maximum_attempts"])
    events, status = [], []
    for n, cik in enumerate(targets, 1):
        try:
            main_payload, _, _ = fetcher.json(config["source_endpoint"].format(cik10=cik), f"submissions_{cik}")
            payloads = [("main", main_payload)]
            for filename in e8k.overlapping_history_files(main_payload, v1.START):
                payload, _, _ = fetcher.json(config["historical_source_endpoint"].format(filename=filename),
                                             f"submissions_{cik}_{filename.removesuffix('.json')}")
                payloads.append((filename, payload))
            rows = e8k.earnings_events({"cik10": cik, "company_name_as_filed": main_payload.get("name", ""), "sector": ""},
                                       payloads, v1.START)
            events += rows
            status.append({"cik10": cik, "status": "complete", "events": len(rows)})
        except Exception as exc:                                  # noqa: BLE001
            status.append({"cik10": cik, "status": f"failed:{type(exc).__name__}", "events": 0})
        if n % 250 == 0:
            print(f"  {n}/{len(targets)}; events {len(events)}", flush=True)
    with (OUTPUT / "results_8k_events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({k for r in events for k in r}))
        writer.writeheader()
        writer.writerows(events)
    with (OUTPUT / "issuer_status.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cik10", "status", "events"])
        writer.writeheader()
        writer.writerows(status)
    failed = sum(s["status"] != "complete" for s in status)
    (OUTPUT / "manifest.json").write_text(json.dumps({"issuers": len(targets), "failed": failed, "events": len(events),
                                                      "start": v1.START}, indent=2) + "\n")
    print(f"done: {len(events)} Item 2.02 events for {len(targets)} issuers, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
