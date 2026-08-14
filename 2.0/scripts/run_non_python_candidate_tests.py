#!/usr/bin/env python3
"""Acquire pinned sources, restore dependencies, and test selected non-Python candidates."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "evidence/batch_01_backtest_execution/smoke_test_queue.csv"
POLICY = ROOT / "config/sandbox_policy.json"
OUTPUT = ROOT / "evidence/non_python_execution"

ACQUIRE_SCRIPT = r"""
import os
import pathlib
import shutil
import tarfile
import urllib.request

work = pathlib.Path('/work')
archive = work / 'source.tar.gz'
source = work / 'source'
repository = work / 'repository'
for target in (archive, source, repository):
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
url = f"https://github.com/{os.environ['REPOSITORY']}/archive/{os.environ['HEAD_COMMIT']}.tar.gz"
request = urllib.request.Request(url, headers={'User-Agent': 'portfolio-optimizer-2.0-non-python-gate'})
with urllib.request.urlopen(request, timeout=120) as response, archive.open('wb') as output:
    shutil.copyfileobj(response, output)
source.mkdir()
with tarfile.open(archive, 'r:gz') as bundle:
    for member in bundle.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError(f'unsafe archive member: {member.name}')
    bundle.extractall(source, filter='data')
roots = [path for path in source.iterdir() if path.is_dir()]
if len(roots) != 1:
    raise RuntimeError(f'expected one archive root, found {len(roots)}')
shutil.move(str(roots[0]), repository)
print('PINNED_SOURCE_ACQUIRED')
"""

CANDIDATES = {
    "ast-0021": {
        "image": "localhost/po2-rust-native:1.91.1-bookworm-v1",
        "dependency": ["cargo", "fetch"],
        "tests": {
            "barter_instrument": ["cargo", "test", "-p", "barter-instrument", "--offline"],
        },
        "primary_test": "barter_instrument",
        "lockfiles": ["Cargo.lock"],
        "lockfile_origin": "generated_by_execution_gate",
        "environment": {"RUSTUP_TOOLCHAIN": "1.91.1-aarch64-unknown-linux-gnu"},
    },
    "ast-0036": {
        "image": "localhost/po2-rust-native:1.55-bullseye-v1",
        "dependency": ["cargo", "fetch", "--locked"],
        "tests": {
            "rust_package": ["cargo", "test", "-p", "qapro-rs", "--locked", "--offline"],
        },
        "lockfiles": ["Cargo.lock", "qapro-rs/Cargo.lock"],
        "primary_test": "rust_package",
        "lockfile_origin": "upstream",
        "environment": {"RUSTUP_TOOLCHAIN": "1.55.0-aarch64-unknown-linux-gnu"},
    },
    "ast-0046": {
        "image": "localhost/po2-rust-native:1.91.1-bookworm-v1",
        "dependency": ["cargo", "fetch"],
        "tests": {
            "hftbacktest_core": [
                "cargo", "test", "-p", "hftbacktest", "--lib", "--no-default-features",
                "--features", "backtest", "--offline"
            ],
        },
        "primary_test": "hftbacktest_core",
        "lockfiles": ["Cargo.lock"],
        "lockfile_origin": "generated_by_execution_gate",
        "environment": {"RUSTUP_TOOLCHAIN": "1.91.1-aarch64-unknown-linux-gnu"},
    },
    "ast-0051": {
        "image": "docker.io/library/node:20-bookworm",
        "dependency": ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        "tests": {
            "offline_unit": ["npm", "exec", "--offline", "vitest", "run", "tests/unit"],
            "offline_integration_diagnostic": ["npm", "exec", "--offline", "vitest", "run", "tests/integration"],
        },
        "lockfiles": ["package-lock.json"],
        "primary_test": "offline_unit",
        "lockfile_origin": "upstream",
        "environment": {},
    },
}


def rows() -> dict[str, dict[str, str]]:
    with QUEUE.open(newline="", encoding="utf-8") as handle:
        return {row["entry_id"]: row for row in csv.DictReader(handle)}


def limits(policy: dict[str, object]) -> list[str]:
    configured = policy["limits"]
    assert isinstance(configured, dict)
    return [
        "--read-only", "--cap-drop=all", "--security-opt=no-new-privileges",
        f"--pids-limit={configured['pids']}", f"--cpus={configured['cpus']}",
        "--memory=2g", "--tmpfs", "/tmp:rw,exec,nosuid,size=1g",
    ]


def container_command(
    *, name: str, image: str, volume: str, command: list[str], offline: bool,
    environment: dict[str, str] | None = None,
) -> list[str]:
    result = ["podman", "run", "--rm", "--name", name]
    if offline:
        result.append("--network=none")
    result.extend([
        *limits(json.loads(POLICY.read_text(encoding="utf-8"))),
        "--volume", f"{volume}:/work:rw",
        "--env", "HOME=/work/home", "--env", "CARGO_HOME=/work/cargo-home",
        "--env", "npm_config_cache=/work/npm-cache", "--env", "CARGO_BUILD_JOBS=1",
        "--workdir", "/work/repository", image, *command,
    ])
    insertion = result.index("--workdir")
    for key, value in (environment or {}).items():
        result[insertion:insertion] = ["--env", f"{key}={value}"]
        insertion += 2
    return result


def compact(completed: subprocess.CompletedProcess[str], limit: int = 16000) -> str:
    return (completed.stdout + "\n" + completed.stderr).strip()[-limit:]


def lock_hashes(entry_id: str, volume: str, image: str) -> dict[str, str]:
    files = CANDIDATES[entry_id]["lockfiles"]
    command = ["sha256sum", *files]
    completed = subprocess.run(
        container_command(name=f"po2-lock-{entry_id}", image=image, volume=volume, command=command, offline=True),
        capture_output=True, text=True, timeout=60, check=False,
    )
    hashes = {}
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            digest, name = line.split(maxsplit=1)
            hashes[name] = digest
    return hashes


def run_candidate(row: dict[str, str], timeout: int) -> dict[str, object]:
    entry_id = row["entry_id"]
    profile = CANDIDATES[entry_id]
    image = str(profile["image"])
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", entry_id.lower())
    volume = f"po2-nonpython-{safe_id}"
    subprocess.run(["podman", "volume", "create", volume], check=True, capture_output=True, text=True)
    started = time.monotonic()
    try:
        acquire = subprocess.run(
            [
                "podman", "run", "--rm", "--interactive", "--name", f"po2-acquire-{safe_id}",
                *limits(json.loads(POLICY.read_text(encoding="utf-8"))),
                "--volume", f"{volume}:/work:rw", "--env", f"REPOSITORY={row['repository']}",
                "--env", f"HEAD_COMMIT={row['head_commit']}", "--entrypoint", "python",
                "docker.io/library/python:3.12-bookworm", "-",
            ],
            input=ACQUIRE_SCRIPT, capture_output=True, text=True, timeout=300, check=False,
        )
        if acquire.returncode:
            return {"entry_id": entry_id, "status": "acquisition_failed", "log": compact(acquire)}

        dependency = subprocess.run(
            container_command(
                name=f"po2-deps-{safe_id}", image=image, volume=volume,
                command=list(profile["dependency"]), offline=False,
                environment=dict(profile["environment"]),
            ),
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        result: dict[str, object] = {
            "entry_id": entry_id, "repository": row["repository"], "head_commit": row["head_commit"],
            "image": image, "dependency_exit_code": dependency.returncode,
            "dependency_log": compact(dependency), "dependency_network": "enabled",
            "test_network": "disabled", "host_mounts": False,
            "lockfile_sha256": lock_hashes(entry_id, volume, image),
            "lockfile_origin": profile["lockfile_origin"],
            "tests": {}, "elapsed_seconds": int(time.monotonic() - started),
        }
        if dependency.returncode:
            result["status"] = "dependency_failed"
            return result

        test_results = {}
        for test_name, test_command in profile["tests"].items():
            test = subprocess.run(
                container_command(
                    name=f"po2-test-{safe_id}-{test_name[:18]}", image=image, volume=volume,
                    command=list(test_command), offline=True,
                    environment=dict(profile["environment"]),
                ),
                capture_output=True, text=True, timeout=timeout, check=False,
            )
            test_results[test_name] = {"exit_code": test.returncode, "log": compact(test)}
        result["tests"] = test_results
        primary = str(profile["primary_test"])
        result["status"] = "passed" if test_results[primary]["exit_code"] == 0 else "tests_failed"
        result["elapsed_seconds"] = int(time.monotonic() - started)
        return result
    except subprocess.TimeoutExpired as exc:
        return {
            "entry_id": entry_id, "repository": row["repository"], "head_commit": row["head_commit"],
            "status": "timed_out", "elapsed_seconds": int(time.monotonic() - started), "error": str(exc),
            "test_network": "disabled", "host_mounts": False,
        }
    finally:
        for prefix in ("po2-acquire", "po2-deps", "po2-test", "po2-lock"):
            subprocess.run(["podman", "rm", "--force", f"{prefix}-{safe_id}"], capture_output=True, text=True)
        subprocess.run(["podman", "volume", "rm", "--force", volume], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-id", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()
    selected = set(args.entry_id) if args.entry_id else set(CANDIDATES)
    unknown = selected - set(CANDIDATES)
    if unknown:
        raise SystemExit(f"No executable profile for: {sorted(unknown)}")
    queue = rows()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    current = []
    for entry_id in sorted(selected):
        result = run_candidate(queue[entry_id], args.timeout)
        current.append(result)
        (OUTPUT / f"{entry_id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{entry_id} {result['status']} ({result.get('elapsed_seconds', 0)}s)", flush=True)
    aggregate = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(OUTPUT.glob("ast-*.json"))]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "total": len(aggregate),
        "passed": sum(item["status"] == "passed" for item in aggregate),
        "failed": sum(item["status"] != "passed" for item in aggregate),
        "test_network_disabled": True, "host_mounts": False,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(item["status"] == "passed" for item in current) else 1


if __name__ == "__main__":
    raise SystemExit(main())
