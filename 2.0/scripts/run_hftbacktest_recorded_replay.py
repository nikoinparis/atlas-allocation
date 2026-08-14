#!/usr/bin/env python3
"""Replay a pinned recorded order-book excerpt through hftbacktest."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import run_non_python_candidate_tests as gate


ROOT = Path(__file__).resolve().parents[1]
ENTRY_ID = "ast-0046"
PROBE = ROOT / "scripts/probes/hftbacktest_recorded_replay.rs"
FIXTURE = ROOT / "evidence/hftbacktest_recorded_replay/fixtures/btcusdt_docs_excerpt.csv"
OUTPUT = ROOT / "evidence/hftbacktest_recorded_replay"
EXPECTED_LOCK_SHA256 = "50ae0dda20bff6f4595568869f855e05846b2d7019c1cebf9ecb4622ac45a182"
SOURCE_DOCUMENT_BLOB = "63f28de18a085e6e7f315f06aca6b3768e135170"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_rows() -> list[dict[str, str]]:
    with FIXTURE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def timestamp_inversions(rows: list[dict[str, str]]) -> int:
    timestamps = [int(row["exch_ts"]) for row in rows]
    return sum(left > right for left, right in zip(timestamps, timestamps[1:]))


def acquire_command(row: dict[str, str], volume: str) -> list[str]:
    policy = json.loads(gate.POLICY.read_text(encoding="utf-8"))
    return [
        "podman", "run", "--rm", "--interactive", "--name", "po2-hft-replay-acquire",
        *gate.limits(policy), "--volume", f"{volume}:/work:rw",
        "--env", f"REPOSITORY={row['repository']}", "--env", f"HEAD_COMMIT={row['head_commit']}",
        "--entrypoint", "python", "docker.io/library/python:3.12-bookworm", "-",
    ]


def injection_command(volume: str) -> list[str]:
    policy = json.loads(gate.POLICY.read_text(encoding="utf-8"))
    return [
        "podman", "run", "--rm", "--interactive", "--name", "po2-hft-replay-inject",
        "--network=none", *gate.limits(policy), "--volume", f"{volume}:/work:rw",
        "--entrypoint", "python", "docker.io/library/python:3.12-bookworm", "-",
    ]


def injection_script() -> str:
    probe = base64.b64encode(PROBE.read_bytes()).decode("ascii")
    fixture = base64.b64encode(FIXTURE.read_bytes()).decode("ascii")
    return f"""
import base64
import pathlib
test = pathlib.Path('/work/repository/hftbacktest/tests/recorded_replay.rs')
fixture = pathlib.Path('/work/repository/hftbacktest/tests/fixtures/btcusdt_docs_excerpt.csv')
test.parent.mkdir(parents=True, exist_ok=True)
fixture.parent.mkdir(parents=True, exist_ok=True)
test.write_bytes(base64.b64decode({probe!r}))
fixture.write_bytes(base64.b64decode({fixture!r}))
print('RECORDED_REPLAY_INJECTED')
"""


def parse_metrics(log: str) -> dict[str, int | float]:
    match = re.search(r"REPLAY_METRICS (\{[^\n]+\})", log)
    if not match:
        raise ValueError("replay metrics are missing")
    metrics = json.loads(match.group(1))
    required = {
        "source_rows", "engine_events", "timestamp_inversions", "market_trades",
        "best_bid", "best_ask", "best_bid_qty", "best_ask_qty", "safe_order_qty",
        "oversized_order_qty", "simulated_fills",
    }
    if set(metrics) != required:
        raise ValueError("replay metrics schema changed")
    if any(isinstance(value, float) and not math.isfinite(value) for value in metrics.values()):
        raise ValueError("replay metrics contain a non-finite value")
    if metrics["best_bid"] >= metrics["best_ask"]:
        raise ValueError("replay produced a crossed book")
    if metrics["safe_order_qty"] > metrics["best_ask_qty"]:
        raise ValueError("safe order exceeds visible ask depth")
    if metrics["oversized_order_qty"] <= metrics["best_ask_qty"]:
        raise ValueError("oversized guard was not challenged")
    return metrics


def run() -> dict[str, object]:
    row = gate.rows()[ENTRY_ID]
    profile = gate.CANDIDATES[ENTRY_ID]
    image = str(profile["image"])
    environment = dict(profile["environment"])
    volume = "po2-hftbacktest-recorded-replay"
    base: dict[str, object] = {
        "entry_id": ENTRY_ID,
        "repository": row["repository"],
        "head_commit": row["head_commit"],
        "source_document": "docs/data.rst",
        "source_document_git_blob": SOURCE_DOCUMENT_BLOB,
        "source_document_url": (
            "https://github.com/nkaz001/hftbacktest/blob/"
            f"{row['head_commit']}/docs/data.rst"
        ),
        "fixture_sha256": sha256(FIXTURE),
        "fixture_rows": len(fixture_rows()),
        "image": image,
        "dependency_network": "enabled",
        "replay_network": "disabled",
        "host_mounts": False,
    }
    subprocess.run(["podman", "volume", "create", volume], check=True, capture_output=True, text=True)
    started = time.monotonic()
    try:
        acquire = subprocess.run(
            acquire_command(row, volume), input=gate.ACQUIRE_SCRIPT, capture_output=True,
            text=True, timeout=300, check=False,
        )
        if acquire.returncode:
            return {**base, "status": "acquisition_failed", "log": gate.compact(acquire)}

        dependency = subprocess.run(
            gate.container_command(
                name="po2-hft-replay-deps", image=image, volume=volume,
                command=list(profile["dependency"]), offline=False, environment=environment,
            ),
            capture_output=True, text=True, timeout=1200, check=False,
        )
        lock_hash = gate.lock_hashes(ENTRY_ID, volume, image).get("Cargo.lock", "")
        if dependency.returncode:
            return {
                **base, "status": "dependency_failed", "dependency_exit_code": dependency.returncode,
                "dependency_log": gate.compact(dependency), "generated_lockfile_sha256": lock_hash,
            }

        inject = subprocess.run(
            injection_command(volume), input=injection_script(), capture_output=True,
            text=True, timeout=60, check=False,
        )
        if inject.returncode:
            return {**base, "status": "injection_failed", "log": gate.compact(inject)}

        command = [
            "cargo", "test", "-p", "hftbacktest", "--test", "recorded_replay",
            "--no-default-features", "--features", "backtest", "--offline", "--", "--nocapture",
        ]
        replay = subprocess.run(
            gate.container_command(
                name="po2-hft-recorded-replay", image=image, volume=volume,
                command=command, offline=True, environment=environment,
            ),
            capture_output=True, text=True, timeout=1200, check=False,
        )
        log = gate.compact(replay, limit=30000)
        lock_matches = lock_hash == EXPECTED_LOCK_SHA256
        try:
            metrics = parse_metrics(log)
        except ValueError as exc:
            metrics = {}
            metrics_error = str(exc)
        else:
            metrics_error = ""
        passed = replay.returncode == 0 and lock_matches and bool(metrics)
        return {
            **base,
            "status": "completed" if passed else "replay_failed",
            "replay_exit_code": replay.returncode,
            "generated_lockfile_sha256": lock_hash,
            "expected_lockfile_sha256": EXPECTED_LOCK_SHA256,
            "lockfile_matches_prior_gate": lock_matches,
            "metrics": metrics,
            "metrics_error": metrics_error,
            "elapsed_seconds": int(time.monotonic() - started),
            "log": log,
        }
    except subprocess.TimeoutExpired as exc:
        return {**base, "status": "timed_out", "error": str(exc), "elapsed_seconds": int(time.monotonic() - started)}
    finally:
        for name in (
            "po2-hft-replay-acquire", "po2-hft-replay-deps", "po2-hft-replay-inject",
            "po2-hft-recorded-replay", "po2-lock-ast-0046",
        ):
            subprocess.run(["podman", "rm", "--force", name], capture_output=True, text=True)
        subprocess.run(["podman", "volume", "rm", "--force", volume], capture_output=True, text=True)


def main() -> int:
    result = run()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    (OUTPUT / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"hftbacktest recorded replay: {result['status']}")
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
