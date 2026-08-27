#!/usr/bin/env python3
"""Freeze the pre-experiment repository and protected-forward state.

This script is deliberately read-only outside its own evidence directory.  It
records a dirty worktree without staging or cleaning it and creates sentinel
hashes for the files whose mutation would contaminate the September 4 clock.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUTPUT = ROOT / "evidence/pre_future_alpha_program_manifest_v1"

PROTECTED = [
    ROOT / "config/forward_prediction_registry_v1.json",
    ROOT / "evidence/weekly_forward_cycles/latest_result.json",
    ROOT / "evidence/forward_covariance_minimum_variance_v1/status.json",
    ROOT / "evidence/forward_covariance_minimum_variance_v1/report.md",
    ROOT / "evidence/forward_covariance_minimum_variance_v1/decisions.jsonl",
    ROOT / "evidence/forward_covariance_minimum_variance_v1/observations.jsonl",
]

SCOPED_ROOTS = ["config", "scripts", "src", "tests", "schemas", "research_registry"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def directory_summary(path: Path) -> dict[str, int]:
    files = [item for item in path.rglob("*") if item.is_file()]
    return {"files": len(files), "bytes": sum(item.stat().st_size for item in files)}


def main() -> int:
    status_lines = git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    scoped = {}
    for root_name in SCOPED_ROOTS:
        for path in sorted((ROOT / root_name).rglob("*")):
            if path.is_file() and path.stat().st_size <= 20 * 1024 * 1024:
                scoped[str(path.relative_to(ROOT))] = sha256(path)

    protected = {
        str(path.relative_to(ROOT)): {
            "exists": path.exists(),
            "sha256": sha256(path) if path.exists() else None,
            "bytes": path.stat().st_size if path.exists() else 0,
        }
        for path in PROTECTED
    }
    forward_registry = ROOT / "evidence/forward_prediction_registry_v1"
    if forward_registry.exists():
        for path in sorted(forward_registry.rglob("*")):
            if path.is_file():
                protected[str(path.relative_to(ROOT))] = {
                    "exists": True,
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }

    manifest = {
        "experiment": "pre_future_alpha_program_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": git("branch", "--show-current"),
        "head_commit": git("rev-parse", "HEAD"),
        "worktree_dirty": bool(status_lines),
        "worktree_status_count": len(status_lines),
        "worktree_status_sha256": hashlib.sha256("\n".join(status_lines).encode()).hexdigest(),
        "worktree_status": status_lines,
        "scoped_file_sha256": scoped,
        "protected_forward_sentinels": protected,
        "directory_summaries": {
            name: directory_summary(ROOT / name)
            for name in ["data", "evidence"]
        },
        "rules": {
            "live_trading_enabled": False,
            "backfill_forward_evidence": False,
            "mutate_protected_forward_files": False,
            "strategy_promotion_authorized": False,
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / "manifest.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    report = (
        "# Pre-experiment manifest v1\n\n"
        f"Frozen at `{manifest['created_at_utc']}` on `{manifest['branch']}` / "
        f"`{manifest['head_commit']}`. The worktree contains "
        f"**{manifest['worktree_status_count']}** modified or untracked paths. "
        "No file was staged, cleaned, or overwritten. Protected forward files are "
        "hashed in `manifest.json`; the research program must reproduce those hashes "
        "after completion. Live trading and forward backfill remain disabled.\n"
    )
    (OUTPUT / "report.md").write_text(report)
    print(json.dumps({
        "manifest": str(destination),
        "head_commit": manifest["head_commit"],
        "worktree_status_count": manifest["worktree_status_count"],
        "protected_sentinels": len(protected),
        "live_trading_enabled": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
