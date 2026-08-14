#!/usr/bin/env python3
"""Run the isolated free ETF collector and register an immutable snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_revision import compare_snapshots, snapshot_freshness
from src.systematic_trader.data_vintage import SnapshotStore

IMAGE = "localhost/po2-yfinance:1.5.2-v1"
STORE_ROOT = ROOT / "data/vintages"
OUTPUT = ROOT / "evidence/free_data_acquisition"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
STANDARD_FILES = (
    "prices.csv", "universe_membership.csv", "security_master.csv",
    "corporate_actions.csv", "delistings.csv", "acquisition_metadata.json",
)


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command[:4])}; "
            f"stderr={result.stderr.strip()} stdout={result.stdout.strip()}"
        )
    return result


def image_metadata() -> dict[str, str]:
    result = run_command(["podman", "image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Digest}}"])
    image_id, _, digest = result.stdout.strip().partition("|")
    return {"image": IMAGE, "image_id": image_id, "repo_digest": digest}


def acquire_to(directory: Path, symbols: list[str], period: str) -> tuple[dict[str, object], str]:
    name = "po2-free-data-" + uuid.uuid4().hex[:12]
    created = False
    log = ""
    try:
        run_command([
            "podman", "create", "--name", name, IMAGE,
            "--symbols", ",".join(symbols), "--period", period, "--output", "/export",
        ])
        created = True
        start = run_command(["podman", "start", "--attach", name], check=False)
        log = (start.stdout or "") + (start.stderr or "")
        directory.mkdir(parents=True, exist_ok=True)
        run_command(["podman", "cp", f"{name}:/export/.", str(directory)])
        metadata = json.loads((directory / "acquisition_metadata.json").read_text(encoding="utf-8"))
        if start.returncode != 0 or metadata.get("status") != "complete":
            raise RuntimeError(f"isolated acquisition failed: {metadata.get('errors', log)}")
        missing_files = [name for name in STANDARD_FILES if not (directory / name).is_file()]
        if missing_files:
            raise RuntimeError(f"collector omitted files: {missing_files}")
        return metadata, log
    finally:
        if created:
            run_command(["podman", "rm", "--force", name], check=False)


def build(period: str = "max") -> dict[str, object]:
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    symbols = sorted(universe["symbols"])
    store = SnapshotStore(STORE_ROOT)
    prior = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    with tempfile.TemporaryDirectory() as temporary_name:
        bundle = Path(temporary_name) / "bundle"
        metadata, container_log = acquire_to(bundle, symbols, period)
        observed_at = metadata["observed_at_utc"]
        freshness = snapshot_freshness(bundle / "prices.csv", observed_at, set(symbols))
        if not freshness["freshness_pass"]:
            raise RuntimeError(f"free snapshot failed freshness gate: {freshness}")
        descriptor = {
            "provider": "free_yahoo_via_yfinance",
            "dataset_kind": "free_current_etf_research_bundle",
            "observed_at_utc": observed_at,
            "observed_at_basis": "maximum per-ticker retrieval completion timestamp from isolated collector",
            "source_uri": "https://finance.yahoo.com via yfinance",
            "source_license": "free research access; Yahoo terms and yfinance personal-use warning apply",
            "revision_policy": "every pull retained as a new snapshot; upstream revision history is unavailable",
            "publication_lag_policy": "new observations usable only after per-ticker knowledge_at_utc; historical rows remain research-only",
            "coverage": {
                "period": period,
                "symbols": len(symbols),
                "latest_observation_date": freshness["latest_observation_date"],
            },
            "claims": {
                "point_in_time_prices": False,
                "point_in_time_universe": False,
                "permanent_security_ids": False,
                "corporate_actions": False,
                "delistings": False,
                "vintage_revisions": False,
            },
            "notes": [
                "Free current-ETF universe; unsuitable for survivorship-safe stock or index-membership research.",
                "Ticker-derived IDs are not permanent identifiers.",
                "Successive local snapshots can reveal future revisions but cannot recover revisions before the first pull.",
                "No paid source is required or used.",
            ],
        }
        files = {name: bundle / name for name in STANDARD_FILES}
        manifest = store.ingest(files, descriptor)
    comparison = None
    if prior:
        previous = max(prior, key=lambda item: item["observed_at_utc"])
        comparison = compare_snapshots(store, str(previous["snapshot_id"]), str(manifest["snapshot_id"]))
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": manifest["snapshot_id"],
        "observed_at_utc": manifest["observed_at_utc"],
        "historical_simulation_grade": manifest["historical_simulation_grade"],
        "claims": manifest["claims"],
        "image": image_metadata(),
        "acquisition": metadata,
        "freshness": freshness,
        "revision_comparison": comparison,
        "paid_data_required": False,
        "scope": "current ETF research, forward paper-data collection, and revision monitoring",
        "excluded_scope": "survivorship-safe historical universe or delisted-security claims",
        "container_log": container_log.strip(),
    }
    return result


def report(result: dict[str, object]) -> str:
    acquisition = result["acquisition"]
    freshness = result["freshness"]
    comparison = result["revision_comparison"]
    revision_lines = ["- This is the first free-provider snapshot, so no prior free vintage exists for comparison."]
    if comparison:
        revision_lines = [
            f"- Common price rows: {comparison['common_rows']:,}.",
            f"- Revised historical rows: {comparison['revised_rows']:,} ({comparison['revised_row_share'] * 100:.4f}%).",
            f"- Newly observed rows: {comparison['new_keys']:,}.",
            f"- Disappeared rows: {comparison['disappeared_keys']:,}.",
        ]
    return "\n".join([
        "# Free ETF Data Acquisition", "",
        f"Snapshot: `{result['snapshot_id']}`", "",
        "A rootless Podman container downloaded the configured ETF universe through a fully pinned yfinance environment. No host Python packages or paid services were used. The normalized output was validated and stored immutably.", "",
        "## Acquisition", "",
        f"- Symbols: **{acquisition['symbol_count']}**.",
        f"- Daily price rows: **{acquisition['price_rows']:,}**.",
        f"- Corporate-action rows observed: **{acquisition['action_rows']:,}**.",
        f"- Latest market date: **{freshness['latest_observation_date']}**.",
        f"- Maximum calendar staleness: **{freshness['maximum_calendar_staleness_days']} days**.",
        f"- Freshness and completeness gate: **{'pass' if freshness['freshness_pass'] else 'fail'}**.", "",
        "## Revision monitoring", "", *revision_lines, "",
        "## Safety classification", "",
        "This snapshot is free and useful for current ETF research, forward paper-data collection, and detecting revisions between future pulls. It remains research-only: Yahoo-adjusted history can be revised, the universe was selected with hindsight, ticker IDs are not permanent, and complete delisting/membership coverage is unavailable.", "",
        "Paid CRSP/Norgate work is deferred. The free collection path does not depend on it.", "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="max")
    args = parser.parse_args()
    result = build(args.period)
    run_dir = OUTPUT / "runs" / str(result["snapshot_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(report(result), encoding="utf-8")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "latest_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({
        "snapshot_id": result["snapshot_id"], "acquisition": result["acquisition"],
        "freshness": result["freshness"], "revision_comparison": result["revision_comparison"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
