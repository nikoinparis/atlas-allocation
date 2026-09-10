#!/usr/bin/env python3
"""Reclaim disk by removing what can be rebuilt, and nothing that cannot.

Every path below is in exactly one of three categories, and the category decides
whether it is safe to delete:

  REBUILDABLE   a download or a build artifact. Deleting it costs time, not
                information. rebuild_all_data.py or a package manager restores it.
  VENDORED      a third-party library cloned for evaluation. `pip install` away.
  PRESERVED     point-in-time vintages, evidence, configs, history. NEVER touched
                by this script, and listed at the end so the distinction is
                visible rather than assumed.

Default is a dry run. Nothing is deleted without --apply.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

REBUILDABLE = [
    (".venv", "Python environment", "pip install -r requirements.txt"),
    ("dashboard/node_modules", "npm packages", "npm install"),
    ("dashboard/.next", "Next.js build output", "npm run build"),
    ("dashboard/public/return-first-dashboard.json.full", "untrimmed payload copy",
     "scripts/build_*.py then trim_dashboard_payload_v1.py"),
    ("dashboard/public/return-first-dashboard.json.bundled", "pre-split payload copy",
     "scripts/split_dashboard_prices_v1.py"),
    ("data/sec_filing_text_v1", "10-K text corpus", "acquire_sec_filing_text_v1.py"),
    ("data/sec_fsds_history_v1", "Financial Statement Data Sets", "acquire_sec_fsds_history_v1.py"),
    ("data/sec_13f_datasets_v1", "13F holdings archives", "acquire_sec_13f_datasets_v1.py"),
    ("data/edgar_form_index_v1", "EDGAR form index", "acquire_edgar_form_index_v1.py"),
    ("data/sec_recent_companyfacts_cache_v1", "company facts cache",
     "acquire_sec_recent_companyfacts_v1.py"),
    ("data/sec_form4_history_v1", "Form 4 quarterly archives", "acquire_sec_form4_history_v1.py"),
    ("data/finra_short_volume_v1", "FINRA daily short-sale volume",
     "acquire_finra_short_volume_v1.py"),
    ("data/finra_short_interest_v1", "FINRA short interest", "its acquire_* script"),
    ("data/sec_broad_identity_cache_v2", "identity resolution cache", "its acquire_* script"),
    ("data/sec_broad_tiingo_cache_v2", "Tiingo price cache", "its acquire_* script"),
    ("evidence/institutional_linkage_v1/holdings.parquet", "556MB derived 13F table",
     "run_institutional_linkage_v1.py"),
]

VENDORED = [
    ("evidence/riskfolio_repository_batch_36/source", "Riskfolio-Lib clone", "pip install riskfolio-lib"),
    ("evidence/skfolio_repository_batch_37/source", "skfolio clone", "pip install skfolio"),
]

PRESERVED = [
    ("data/vintages", "ETF point-in-time snapshots -- CANNOT be re-downloaded"),
    ("data/sec_pilot_price_vintages", "price vintages -- CANNOT be re-downloaded"),
    ("data/sec_form4_bulk_vintages", "Form 4 vintages -- CANNOT be re-downloaded"),
    ("data/clean_full_history_prices_v1", "the panel the forward clocks price against"),
    ("data/clean_weekly_prices_v2", "narrow weekly panel, used by the clocks"),
    ("data/broad_full_history_panel_v1", "broad weekly panel"),
    ("data/etf_weekly_panel_v1", "flat ETF panel"),
    ("data/form4_purchase_panel_v1", "derived insider panel, 8MB, cheap to keep"),
    ("evidence", "the audit trail behind every claim in PROJECT_HISTORY"),
    ("config", "frozen manifests and pre-registrations"),
    ("PROJECT_HISTORY.md", "312 steps, append-only"),
]


def size_of(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    out = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True)
    try:
        return int(out.stdout.split()[0]) * 1024
    except Exception:                                # noqa: BLE001
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="actually delete (default is a dry run)")
    args = parser.parse_args()

    total = 0
    for label, group in (("REBUILDABLE", REBUILDABLE), ("VENDORED", VENDORED)):
        print(f"\n{label}")
        for entry in group:
            rel, what, how = entry
            path = ROOT / rel
            size = size_of(path)
            if not size:
                continue
            total += size
            print(f"  {size/1e9:6.2f} GB  {rel}")
            print(f"  {'':9s}  {what} -- restore with: {how}")
            if args.apply:
                shutil.rmtree(path) if path.is_dir() else path.unlink()

    print(f"\nPRESERVED (never touched by this script)")
    for rel, why in PRESERVED:
        size = size_of(ROOT / rel)
        if size:
            print(f"  {size/1e9:6.2f} GB  {rel}\n  {'':9s}  {why}")

    print(f"\n{'freed' if args.apply else 'would free'}: {total/1e9:.2f} GB")
    if not args.apply:
        print("dry run -- nothing was deleted. Re-run with --apply to proceed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
