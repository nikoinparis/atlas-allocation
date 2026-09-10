#!/usr/bin/env python3
"""Split per-symbol price history out of the dashboard bundle into lazy files.

The bundle was 184MB; trimming unheld symbols and pre-window history took it to
36MB, and 36MB is still the wrong shape for a web page. The in-app browser failed
the fetch outright with ERR_CACHE_WRITE_FAILURE -- the response was too large for
the HTTP cache to write -- and the page rendered "Research snapshot unavailable"
on data that was perfectly valid. A payload that only works when the cache
cooperates is not ready to deploy.

`assetPrices` is used by exactly two things: the stock-chart drill-down and the
attribution panel, both of which act on ONE strategy at a time. Loading all six
strategies' price history to render one of them is what made the bundle large.

So the bundle keeps records, daily records and metadata -- the parts every view
needs -- and each strategy's prices move to prices/<id>.json, fetched when that
strategy is selected. Nothing is deleted and no number changes; the same bytes
arrive in a different order.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "dashboard/public"
BUNDLE = PUBLIC / "return-first-dashboard.json"
PRICES = PUBLIC / "prices"


def main() -> int:
    if not BUNDLE.is_file():
        print(f"missing {BUNDLE}")
        return 1
    before = BUNDLE.stat().st_size
    payload = json.loads(BUNDLE.read_text())
    PRICES.mkdir(parents=True, exist_ok=True)

    rows = []
    for entry in payload["strategies"]:
        name = entry["strategy"]["id"]
        prices = entry.pop("assetPrices", {})
        target = PRICES / f"{name}.json"
        target.write_text(json.dumps(prices, separators=(",", ":")))
        rows.append((name, len(prices), target.stat().st_size))

    backup = BUNDLE.with_suffix(".json.bundled")
    if not backup.exists():
        shutil.copy2(BUNDLE, backup)
    BUNDLE.write_text(json.dumps(payload, separators=(",", ":")))
    after = BUNDLE.stat().st_size

    print(f"{'strategy':44s} {'symbols':>8s} {'price file':>12s}")
    for name, count, size in rows:
        print(f"{name:44s} {count:>8d} {size/1048576:>9.1f} MB")
    print(f"\nbundle {before/1048576:.1f} MB -> {after/1048576:.1f} MB")
    print(f"largest single price file: {max(s for _, _, s in rows)/1048576:.1f} MB")
    print("the page now loads the bundle plus one price file, not six")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
