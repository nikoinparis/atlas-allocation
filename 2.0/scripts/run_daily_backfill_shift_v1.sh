#!/usr/bin/env bash
# One day's worth of backfill, then stop. Safe to run every day, safe to run twice.
#
#   export TIINGO_API_TOKEN=...           # never commit this
#   ./scripts/run_daily_backfill_shift_v1.sh
#
# Tiingo's free tier resets 1,000 requests per day. The daemon paces itself against
# both the hourly and daily budgets and records every issuer before moving on, so a
# shift that is interrupted loses at most one issuer. Re-running after the quota is
# spent simply exits.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${TIINGO_API_TOKEN:-}" ]; then
  echo "TIINGO_API_TOKEN is not set. Export it for this process only:" >&2
  echo "  export TIINGO_API_TOKEN=your_token" >&2
  exit 1
fi

LOG_DIR="data/price_backfill_2012_v1/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/shift_$(date -u +%Y%m%dT%H%M%SZ).log"

echo "=== backfill shift starting $(date -u +%FT%TZ) ===" | tee -a "$LOG"
python3 scripts/run_price_backfill_daemon_v1.py --max-requests 1000 2>&1 | tee -a "$LOG"
echo "=== shift finished $(date -u +%FT%TZ) ===" | tee -a "$LOG"

# Progress summary, so a glance at the log answers "how far along are we".
python3 - <<'PY' 2>&1 | tee -a "$LOG"
import json
from collections import Counter
from pathlib import Path
progress = Path("data/price_backfill_2012_v1/progress.jsonl")
if not progress.exists():
    print("no progress file yet")
else:
    statuses, tiers, rows = Counter(), Counter(), 0
    with progress.open() as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows += 1
            statuses[record.get("status", "?")] += 1
            if record.get("terminal"):
                tiers[record.get("tier")] += 1
    print(f"\nattempted: {rows} of 17,970")
    for status, count in statuses.most_common():
        print(f"  {status:44s}{count:6d}")
    print("  terminal by tier:", dict(sorted(tiers.items(), key=lambda kv: (kv[0] is None, kv[0]))))
PY
