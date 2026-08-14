#!/usr/bin/env python3
"""Run historical component replays in disposable, offline Podman sandboxes."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import run_python_candidate_tests as python_gate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/historical_validation/replays"
FIXTURE = ROOT / "evidence/historical_validation/fixtures/equity_daily_adjusted_close.csv"
PROBES = {
    "ast-0022": ROOT / "scripts/probes/historical_bt.py",
    "ast-0047": ROOT / "scripts/probes/historical_flashalpha.py",
}


def queue_rows() -> dict[str, dict[str, str]]:
    with python_gate.QUEUE.open(newline="", encoding="utf-8") as handle:
        return {row["entry_id"]: row for row in csv.DictReader(handle)}


def replay_command(row: dict[str, str], policy: dict[str, object], volume: str) -> list[str]:
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", row["entry_id"].lower())
    return [
        "podman", "run", "--rm", "--interactive", "--name", f"po2-history-{safe_id}",
        "--network=none", *python_gate.base_limits(policy),
        "--volume", f"{volume}:/work:rw", "--env", "HOME=/work/home",
        "--workdir", "/work/repository", "--entrypoint", "/work/venv/bin/python",
        python_gate.candidate_image(row, policy), "-",
    ]


def probe_source(entry_id: str) -> str:
    source = PROBES[entry_id].read_text(encoding="utf-8")
    if entry_id == "ast-0022":
        encoded = base64.b64encode(FIXTURE.read_bytes()).decode("ascii")
        marker = "from __future__ import annotations\n"
        source = source.replace(marker, marker + f"\nFIXTURE_B64 = {encoded!r}\n", 1)
    return source


def run_replay(row: dict[str, str], policy: dict[str, object]) -> dict[str, object]:
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", row["entry_id"].lower())
    volume = f"po2-history-{safe_id}"
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
                "head_commit": row["head_commit"], "status": "install_failed",
                "elapsed_seconds": int(time.monotonic() - started),
                "error": python_gate.compact_log(install),
            }
        replay = subprocess.run(
            replay_command(row, policy, volume),
            input=probe_source(row["entry_id"]),
            text=True,
            capture_output=True,
            timeout=600,
            check=False,
        )
        payload: dict[str, object] = {}
        if replay.returncode == 0:
            try:
                payload = json.loads(replay.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                payload = {"parse_error": str(exc)}
        status = "completed" if replay.returncode == 0 and "parse_error" not in payload else "replay_failed"
        return {
            "entry_id": row["entry_id"], "repository": row["repository"],
            "head_commit": row["head_commit"], "status": status,
            "elapsed_seconds": int(time.monotonic() - started),
            "network_disabled_during_replay": True, "host_mounts": False,
            "replay": payload,
            "error": "" if status == "completed" else (replay.stderr + "\n" + replay.stdout).strip()[-5000:],
        }
    finally:
        subprocess.run(["podman", "volume", "rm", "--force", volume], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-id", action="append", default=[])
    args = parser.parse_args()
    if not FIXTURE.exists():
        raise SystemExit("Build the historical fixture first")
    rows = queue_rows()
    selected = set(args.entry_id) if args.entry_id else set(PROBES)
    unknown = selected - set(PROBES)
    if unknown:
        raise SystemExit(f"No historical probe for: {sorted(unknown)}")
    policy = json.loads(python_gate.POLICY.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    for entry_id in sorted(selected):
        result = run_replay(rows[entry_id], policy)
        results.append(result)
        (OUTPUT / f"{entry_id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{entry_id} {result['status']} ({result['elapsed_seconds']}s)", flush=True)
    aggregate = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(OUTPUT.glob("ast-*.json"))]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(aggregate),
        "completed": sum(item["status"] == "completed" for item in aggregate),
        "critical_pass": sum(
            item["status"] == "completed" and bool(item.get("replay", {}).get("critical_pass"))
            for item in aggregate
        ),
        "network_disabled_during_replays": True,
        "host_mounts": False,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(item["status"] == "completed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
