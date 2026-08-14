#!/usr/bin/env python3
"""Run platform-owned hftbacktest execution probes at its pinned commit."""

from __future__ import annotations

import base64
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import run_non_python_candidate_tests as gate


ROOT = Path(__file__).resolve().parents[1]
ENTRY_ID = "ast-0046"
PROBE = ROOT / "scripts/probes/hftbacktest_platform_execution.rs"
OUTPUT = ROOT / "evidence/hftbacktest_behavioral"
EXPECTED_LOCK_SHA256 = "50ae0dda20bff6f4595568869f855e05846b2d7019c1cebf9ecb4622ac45a182"


def acquire_command(row: dict[str, str], volume: str) -> list[str]:
    policy = json.loads(gate.POLICY.read_text(encoding="utf-8"))
    return [
        "podman", "run", "--rm", "--interactive", "--name", "po2-hft-probe-acquire",
        *gate.limits(policy), "--volume", f"{volume}:/work:rw",
        "--env", f"REPOSITORY={row['repository']}", "--env", f"HEAD_COMMIT={row['head_commit']}",
        "--entrypoint", "python", "docker.io/library/python:3.12-bookworm", "-",
    ]


def injection_command(volume: str) -> list[str]:
    policy = json.loads(gate.POLICY.read_text(encoding="utf-8"))
    return [
        "podman", "run", "--rm", "--interactive", "--name", "po2-hft-probe-inject",
        "--network=none", *gate.limits(policy), "--volume", f"{volume}:/work:rw",
        "--entrypoint", "python", "docker.io/library/python:3.12-bookworm", "-",
    ]


def injection_script() -> str:
    encoded = base64.b64encode(PROBE.read_bytes()).decode("ascii")
    return f"""
import base64
import pathlib
target = pathlib.Path('/work/repository/hftbacktest/tests/platform_execution.rs')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(base64.b64decode({encoded!r}))
print('PLATFORM_PROBE_INJECTED')
"""


def run() -> dict[str, object]:
    row = gate.rows()[ENTRY_ID]
    profile = gate.CANDIDATES[ENTRY_ID]
    image = str(profile["image"])
    environment = dict(profile["environment"])
    volume = "po2-hftbacktest-behavioral"
    subprocess.run(["podman", "volume", "create", volume], check=True, capture_output=True, text=True)
    started = time.monotonic()
    try:
        acquire = subprocess.run(
            acquire_command(row, volume), input=gate.ACQUIRE_SCRIPT, capture_output=True,
            text=True, timeout=300, check=False,
        )
        if acquire.returncode:
            return {"status": "acquisition_failed", "log": gate.compact(acquire)}

        dependency = subprocess.run(
            gate.container_command(
                name="po2-hft-probe-deps", image=image, volume=volume,
                command=list(profile["dependency"]), offline=False, environment=environment,
            ),
            capture_output=True, text=True, timeout=1200, check=False,
        )
        lock_hash = gate.lock_hashes(ENTRY_ID, volume, image).get("Cargo.lock", "")
        if dependency.returncode:
            return {
                "status": "dependency_failed", "dependency_exit_code": dependency.returncode,
                "dependency_log": gate.compact(dependency), "lockfile_sha256": lock_hash,
            }

        inject = subprocess.run(
            injection_command(volume), input=injection_script(), capture_output=True,
            text=True, timeout=60, check=False,
        )
        if inject.returncode:
            return {"status": "injection_failed", "log": gate.compact(inject)}

        command = [
            "cargo", "test", "-p", "hftbacktest", "--test", "platform_execution",
            "--no-default-features", "--features", "backtest", "--offline",
        ]
        test = subprocess.run(
            gate.container_command(
                name="po2-hft-platform-probe", image=image, volume=volume,
                command=command, offline=True, environment=environment,
            ),
            capture_output=True, text=True, timeout=1200, check=False,
        )
        log = gate.compact(test, limit=30000)
        match = re.search(r"test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed", log)
        passed = int(match.group(1)) if match else 0
        failed = int(match.group(2)) if match else -1
        lock_matches = lock_hash == EXPECTED_LOCK_SHA256
        return {
            "entry_id": ENTRY_ID,
            "repository": row["repository"],
            "head_commit": row["head_commit"],
            "image": image,
            "status": "completed" if test.returncode == 0 and lock_matches else "probe_failed",
            "probe_exit_code": test.returncode,
            "tests_passed": passed,
            "tests_failed": failed,
            "generated_lockfile_sha256": lock_hash,
            "expected_lockfile_sha256": EXPECTED_LOCK_SHA256,
            "lockfile_matches_prior_gate": lock_matches,
            "dependency_network": "enabled",
            "probe_network": "disabled",
            "host_mounts": False,
            "elapsed_seconds": int(time.monotonic() - started),
            "log": log,
        }
    except subprocess.TimeoutExpired as exc:
        return {"status": "timed_out", "error": str(exc), "elapsed_seconds": int(time.monotonic() - started)}
    finally:
        for name in (
            "po2-hft-probe-acquire", "po2-hft-probe-deps", "po2-hft-probe-inject",
            "po2-hft-platform-probe", "po2-lock-ast-0046",
        ):
            subprocess.run(["podman", "rm", "--force", name], capture_output=True, text=True)
        subprocess.run(["podman", "volume", "rm", "--force", volume], capture_output=True, text=True)


def main() -> int:
    result = run()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"hftbacktest behavioral probe: {result['status']}")
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
