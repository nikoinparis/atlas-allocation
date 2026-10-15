#!/usr/bin/env python3
"""A28 input: 8-K Item 2.02 (results) acceptance times, 2012-2025, for every stock ever in the
top 500 by liquidity. Reuses scripts/acquire_sec_earnings_8k_v1.py's fetcher and parser, and its
cache (data/sec_historical_identity_cache), extending its 2022+ window back to 2012."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import acquire_sec_earnings_8k_v1 as e8k  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

OUTPUT = ROOT / "data/results_dates_v1"
UA = "PortfolioOptimizerResearch/2.0 contact=local-research"
START = "2011-10-01"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(e8k.CONFIG.read_text())
    prices = a19.load_daily()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    window = (prices.index >= "2012-01-01") & (prices.index <= "2025-06-30")
    px, dv = prices.to_numpy()[window], dollar.to_numpy()[window]
    ever = np.zeros(px.shape[1], dtype=bool)
    for t in range(1, len(px)):
        liquid = (px[t - 1] >= 5) & (dv[t - 1] >= 5e6)
        ever[np.argsort(-np.where(liquid, dv[t - 1], -np.inf))[:500]] = True
    targets = [c for c, e in zip(prices.columns, ever) if e]
    print(f"{len(targets)} issuers were ever in the top 500 by liquidity", flush=True)
    fetcher = e8k.Fetcher(e8k.DEFAULT_CACHE, UA, config["minimum_seconds_between_requests"],
                          config["request_timeout_seconds"], config["maximum_attempts"])
    events, status = [], []
    for n, cik in enumerate(targets, 1):
        try:
            main_payload, _, _ = fetcher.json(config["source_endpoint"].format(cik10=cik), f"submissions_{cik}")
            payloads = [("main", main_payload)]
            for filename in e8k.overlapping_history_files(main_payload, START):
                payload, _, _ = fetcher.json(config["historical_source_endpoint"].format(filename=filename),
                                             f"submissions_{cik}_{filename.removesuffix('.json')}")
                payloads.append((filename, payload))
            rows = e8k.earnings_events({"cik10": cik, "company_name_as_filed": main_payload.get("name", ""), "sector": ""},
                                       payloads, START)
            events += rows
            status.append({"cik10": cik, "status": "complete", "events": len(rows)})
        except Exception as exc:                                 # noqa: BLE001
            status.append({"cik10": cik, "status": f"failed:{type(exc).__name__}", "events": 0})
        if n % 100 == 0:
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
                                                      "start": START, "source": config["source_endpoint"]}, indent=2) + "\n")
    print(f"done: {len(events)} Item 2.02 events, {failed} failed issuers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
