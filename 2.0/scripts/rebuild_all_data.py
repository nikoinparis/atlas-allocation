#!/usr/bin/env python3
"""Re-acquire the data this repository deliberately does not store.

Raw acquisition caches were removed from the repository because they are large
and every byte is re-downloadable from SEC EDGAR, FINRA and public price sources.
This puts them back.

    --core     only what the dashboard and the five forward clocks read.
               Minutes, not hours. Run this first on a fresh machine.
    --full     every cache the research used, including the ones only needed to
               reproduce a closed experiment. Several gigabytes and hours of
               downloading.
    --list     print the plan and exit without touching the network.

What this CANNOT rebuild, and why it is preserved in the repository instead:
`data/vintages`, `data/sec_pilot_price_vintages` and `data/sec_form4_bulk_vintages`
are point-in-time snapshots. They record what a source said on a given date, and
no amount of re-downloading recovers that -- a vintage you can re-fetch is not a
vintage. Everything else here is a convenience cache.

Sources are rate-limited and identify themselves. SEC asks for a contact address
in the user agent; set SEC_USER_AGENT before a full run.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"

# (script, what it produces, why it is needed, minutes)
CORE: list[tuple[str, str, str, int]] = [
    ("acquire_yahoo_recent_current_sec_prices_v1.py", "recent SEC-universe prices",
     "the weekly price panel every book is priced against", 10),
    ("acquire_free_etf_snapshot.py", "ETF vintage snapshot",
     "the ETF leg of the residual composite and the 60/40 benchmark", 3),
    ("build_broad_full_history_panel_v1.py", "data/broad_full_history_panel_v1",
     "the broad weekly panel", 5),
    ("build_corporate_action_clean_prices_v1.py", "data/clean_full_history_prices_v1",
     "corporate-action-repaired prices; the panel the clocks read", 5),
    ("build_etf_weekly_panel_v1.py", "data/etf_weekly_panel_v1",
     "flat ETF weekly panel, needed to reprice the composite's ETF leg", 1),
]

FULL_EXTRA: list[tuple[str, str, str, int]] = [
    ("acquire_sec_fsds_history_v1.py", "data/sec_fsds_history_v1 (3.7GB)",
     "Financial Statement Data Sets 2012-2022; the out-of-sample tests", 90),
    ("acquire_sec_form4_history_v1.py", "data/sec_form4_history_v1 (498MB)",
     "Form 4 insider transactions back to 2011", 30),
    ("acquire_finra_short_volume_v1.py", "data/finra_short_volume_v1 (324MB)",
     "FINRA daily short-sale volume, 922 trading days", 25),
    ("acquire_sec_filing_text_v1.py", "data/sec_filing_text_v1 (4GB)",
     "10-K text corpus for the filing-language experiment", 180),
    ("acquire_sec_13f_datasets_v1.py", "data/sec_13f_datasets_v1 (2.7GB)",
     "13F holdings; the institutional linkage experiment", 120),
    ("acquire_edgar_form_index_v1.py", "data/edgar_form_index_v1 (2.1GB)",
     "EDGAR form index; the 13D/13G event study", 90),
    ("acquire_sec_recent_companyfacts_v1.py", "data/sec_recent_companyfacts_cache_v1 (664MB)",
     "company facts for the fundamental panels", 45),
    ("build_form4_purchase_panel_v1.py", "data/form4_purchase_panel_v1",
     "667,153 open-market insider purchases, derived", 10),
]


def run(script: str, produces: str) -> bool:
    path = ROOT / "scripts" / script
    if not path.is_file():
        print(f"  SKIP  {script} is not in this repository")
        return False
    print(f"  RUN   {script}  ->  {produces}")
    started = time.time()
    result = subprocess.run([str(PYTHON), str(path)], cwd=ROOT)
    elapsed = (time.time() - started) / 60
    if result.returncode == 0:
        print(f"  OK    {script} in {elapsed:.1f} min")
        return True
    print(f"  FAIL  {script} exited {result.returncode} after {elapsed:.1f} min")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--core", action="store_true", help="dashboard and forward clocks only")
    group.add_argument("--full", action="store_true", help="every re-downloadable cache")
    group.add_argument("--list", action="store_true", help="print the plan, touch nothing")
    args = parser.parse_args()

    plan = CORE + (FULL_EXTRA if args.full else [])
    minutes = sum(m for _, _, _, m in plan)

    print(f"{'script':46s} {'produces':44s} {'~min':>5s}")
    for script, produces, why, m in plan:
        print(f"{script:46s} {produces:44s} {m:>5d}")
        print(f"{'':46s} {why}")
    print(f"\nestimated: {minutes} minutes ({minutes/60:.1f} hours)")

    if args.list:
        return 0
    if args.full and not os.environ.get("SEC_USER_AGENT"):
        print("\nSEC asks that requests identify a contact address.")
        print("Set SEC_USER_AGENT before a full run, e.g.")
        print('  export SEC_USER_AGENT="Your Name your@email"')
        return 1
    if not PYTHON.is_file():
        print(f"\nno interpreter at {PYTHON}. Create it first:")
        print("  python -m venv .venv && ./.venv/bin/pip install -r requirements.txt")
        return 1

    print()
    ok = sum(run(script, produces) for script, produces, _, _ in plan)
    print(f"\n{ok} of {len(plan)} steps succeeded")
    if ok < len(plan):
        print("A failed step usually means a source changed its layout or rate-limited you.")
        print("Each acquire_* script is runnable on its own; re-run just the one that failed.")
    return 0 if ok == len(plan) else 1


if __name__ == "__main__":
    raise SystemExit(main())
