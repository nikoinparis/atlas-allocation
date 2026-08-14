#!/usr/bin/env python3
"""Run platform-owned probes against pinned candidates in offline containers."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import run_python_candidate_tests as python_gate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/batch_01_backtest_execution/behavioral_probes"
PROBES = {
    "ast-0022": ROOT / "scripts/probes/probe_bt.py",
    "ast-0047": ROOT / "scripts/probes/probe_flashalpha.py",
}


def queue_rows() -> dict[str, dict[str, str]]:
    with python_gate.QUEUE.open(newline="", encoding="utf-8") as handle:
        return {row["entry_id"]: row for row in csv.DictReader(handle)}


def probe_command(row: dict[str, str], policy: dict[str, object], volume: str) -> list[str]:
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", row["entry_id"].lower())
    return [
        "podman", "run", "--rm", "--interactive", "--name", f"po2-behavior-{safe_id}",
        "--network=none", *python_gate.base_limits(policy),
        "--volume", f"{volume}:/work:rw", "--env", "HOME=/work/home",
        "--workdir", "/work/repository", "--entrypoint", "/work/venv/bin/python",
        python_gate.candidate_image(row, policy), "-",
    ]


def run_probe(row: dict[str, str], probe_path: Path, policy: dict[str, object]) -> dict[str, object]:
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", row["entry_id"].lower())
    volume = f"po2-behavior-{safe_id}"
    subprocess.run(["podman", "volume", "create", volume], check=True, capture_output=True, text=True)
    started = time.monotonic()
    try:
        install = subprocess.run(
            python_gate.install_command(row, policy, volume),
            input=python_gate.PREP_SCRIPT,
            text=True,
            capture_output=True,
            timeout=1200,
            check=False,
        )
        if install.returncode:
            return {
                "entry_id": row["entry_id"], "repository": row["repository"],
                "status": "install_failed", "install_exit_code": install.returncode,
                "probe_exit_code": -1, "elapsed_seconds": int(time.monotonic() - started),
                "error": python_gate.compact_log(install),
            }
        probe = subprocess.run(
            probe_command(row, policy, volume),
            input=probe_path.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        payload: dict[str, object] = {}
        if probe.returncode == 0:
            try:
                payload = json.loads(probe.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                payload = {"parse_error": str(exc)}
        status = "completed" if probe.returncode == 0 and "parse_error" not in payload else "probe_failed"
        return {
            "entry_id": row["entry_id"], "repository": row["repository"],
            "head_commit": row["head_commit"], "status": status,
            "install_exit_code": install.returncode, "probe_exit_code": probe.returncode,
            "elapsed_seconds": int(time.monotonic() - started),
            "network_disabled_during_probe": True, "host_mounts": False,
            "probe": payload,
            "error": (probe.stderr + "\n" + probe.stdout).strip()[-4000:] if status != "completed" else "",
        }
    finally:
        subprocess.run(["podman", "volume", "rm", "--force", volume], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-id", action="append", default=[])
    args = parser.parse_args()
    policy = json.loads(python_gate.POLICY.read_text(encoding="utf-8"))
    rows = queue_rows()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    selected = {
        entry_id: probe_path for entry_id, probe_path in PROBES.items()
        if not args.entry_id or entry_id in set(args.entry_id)
    }
    if not selected:
        raise SystemExit("No behavioral probes selected")
    for entry_id, probe_path in selected.items():
        result = run_probe(rows[entry_id], probe_path, policy)
        results.append(result)
        (OUTPUT / f"{entry_id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{entry_id} {result['status']} ({result['elapsed_seconds']}s)", flush=True)
    aggregate = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(OUTPUT.glob("ast-*.json"))]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(aggregate),
        "completed": sum(item["status"] == "completed" for item in aggregate),
        "network_disabled_during_probes": True,
        "host_mounts": False,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if summary["completed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
