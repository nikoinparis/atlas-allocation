#!/usr/bin/env python3
"""Seed the ledger with the trials the record can actually substantiate.

Step 199 reported a sensitivity grid because N was unknown. This replaces the
grid with a number for every family the history states a count for, and leaves
the families it does not state a count for visibly empty rather than invented.

The result is a lower bound. That matters and is not hidden: a lower bound makes
promotion easier, not harder, so it is labelled as reconstructed and only trials
registered at evaluation time count as properly recorded.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.trial_ledger import Trial, TrialLedger  # noqa: E402

CONFIG = ROOT / "config/trial_ledger_reconstruction_v1.json"
EVIDENCE = ROOT / "evidence/trial_ledger_reconstruction_v1"


def main() -> int:
    config = json.loads(CONFIG.read_text())
    ledger = TrialLedger(ROOT / config["ledger_path"])

    if ledger.read():
        print(json.dumps({
            "skipped": True,
            "reason": "ledger already seeded; it is append-only and must not be re-seeded",
            "records": len(ledger.read()),
            "families": ledger.families(),
        }, indent=2))
        return 0

    stamp = datetime.now(timezone.utc).isoformat()
    trials = []
    for entry in config["reconstructed_trials"]:
        for index in range(entry["count"]):
            trials.append(Trial(
                family=entry["family"],
                experiment="reconstructed_from_project_history",
                variant=f"{entry['family']}_{index:04d}",
                objective="reconstructed_lower_bound",
                dataset=entry["source"],
                evaluated_at_utc=stamp,
                outcome="reconstructed",
            ))
    written = ledger.append(trials)

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": stamp,
        "records_written": written,
        "families": ledger.families(),
        "total_reconstructed_lower_bound": ledger.count(),
        "verification": ledger.verify(),
        "note": config["honesty_statement"],
        "live_trading_enabled": False,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "note"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
