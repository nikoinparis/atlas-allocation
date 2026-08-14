#!/usr/bin/env python3
"""Acquire pinned Batch 1 sources in hardened Podman containers.

This first smoke-test gate never executes repository-owned code. It verifies
that each exact commit can be fetched and records its build and test surface.
Language-specific dependency and test execution is a separate gate.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = ROOT / "evidence/batch_01_backtest_execution/smoke_test_queue.csv"
DEFAULT_OUTPUT = ROOT / "evidence/batch_01_backtest_execution/source_smoke"
POLICY_PATH = ROOT / "config/sandbox_policy.json"

CONTAINER_SCRIPT = r"""
set -eu
mkdir -p /work/repository
cd /work/repository
started="$(date +%s)"
git init -q
git remote add origin "https://github.com/${REPOSITORY}.git"
git -c advice.detachedHead=false fetch -q --depth=1 origin "${HEAD_COMMIT}"
git checkout -q --detach FETCH_HEAD

encode_lines() {
  base64 | tr -d '\n'
}

top_level="$(find . -mindepth 1 -maxdepth 1 -print | sed 's#^\./##' | sort | encode_lines)"
manifests="$(find . -maxdepth 3 -type f -print | sed 's#^\./##' | awk '
  BEGIN { IGNORECASE=1 }
  /(^|\/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^\/]*\.txt|Pipfile|poetry\.lock|uv\.lock|Cargo\.toml|go\.mod|package\.json|pnpm-lock\.yaml|yarn\.lock|CMakeLists\.txt|Makefile|Dockerfile[^\/]*|pom\.xml|build\.gradle[^\/]*)$/ { print }
  /\.(sln|csproj)$/ { print }
' | sort -u | encode_lines)"
tests="$(find . -maxdepth 3 -print | sed 's#^\./##' | awk '
  BEGIN { IGNORECASE=1 }
  /(^|\/)(test|tests|testing)(\/|$)/ || /(^|\/)test_[^\/]+$/ || /(^|\/)(pytest\.ini|tox\.ini)$/ { print }
' | sort -u | encode_lines)"

actual_commit="$(git rev-parse HEAD)"
file_count="$(find . -type f | wc -l | tr -d ' ')"
tracked_file_count="$(git ls-files | wc -l | tr -d ' ')"
repository_kb="$(du -sk . | awk '{print $1}')"
submodule_count=0
if [ -f .gitmodules ]; then
  submodule_count="$(grep -c '^[[:space:]]*path[[:space:]]*=' .gitmodules || true)"
fi
elapsed="$(( $(date +%s) - started ))"

printf 'RESULT_VERSION=1\n'
printf 'ACTUAL_COMMIT=%s\n' "${actual_commit}"
printf 'FILE_COUNT=%s\n' "${file_count}"
printf 'TRACKED_FILE_COUNT=%s\n' "${tracked_file_count}"
printf 'REPOSITORY_KB=%s\n' "${repository_kb}"
printf 'SUBMODULE_COUNT=%s\n' "${submodule_count}"
printf 'ELAPSED_SECONDS=%s\n' "${elapsed}"
printf 'TOP_LEVEL_B64=%s\n' "${top_level}"
printf 'MANIFESTS_B64=%s\n' "${manifests}"
printf 'TEST_INDICATORS_B64=%s\n' "${tests}"
"""


@dataclass
class SmokeResult:
    entry_id: str
    name: str
    repository: str
    expected_commit: str
    actual_commit: str
    planned_environment: str
    status: str
    started_at: str
    elapsed_seconds: int
    file_count: int
    tracked_file_count: int
    repository_kb: int
    submodule_count: int
    dependency_manifests: list[str]
    test_indicators: list[str]
    top_level_entries: list[str]
    container_image: str
    container_exit_code: int
    error: str


def load_policy(path: Path = POLICY_PATH) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_queue(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["queue_status"] == "ready"]


def decode_lines(value: str) -> list[str]:
    if not value:
        return []
    decoded = base64.b64decode(value).decode("utf-8", errors="replace")
    return [line for line in decoded.splitlines() if line]


def parse_result_lines(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z][A-Z0-9_]+", key):
            parsed[key] = value
    return parsed


def container_command(row: dict[str, str], policy: dict[str, object]) -> list[str]:
    limits = policy["limits"]
    assert isinstance(limits, dict)
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", row["entry_id"].lower())
    return [
        "podman", "run", "--rm", "--interactive",
        "--name", f"po2-source-smoke-{safe_id}",
        "--pull=missing",
        "--read-only",
        "--cap-drop=all",
        "--security-opt=no-new-privileges",
        f"--pids-limit={limits['pids']}",
        f"--memory={limits['memory']}",
        f"--cpus={limits['cpus']}",
        "--tmpfs", f"/work:rw,exec,nosuid,size={limits['work_tmpfs']}",
        "--env", f"REPOSITORY={row['repository']}",
        "--env", f"HEAD_COMMIT={row['head_commit']}",
        "--entrypoint", "sh",
        str(policy["source_inspection_image"]),
        "-s",
    ]


def run_one(row: dict[str, str], policy: dict[str, object]) -> SmokeResult:
    limits = policy["limits"]
    assert isinstance(limits, dict)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    command = container_command(row, policy)
    safe_id = re.sub(r"[^a-z0-9_.-]", "-", row["entry_id"].lower())
    try:
        completed = subprocess.run(
            command,
            input=CONTAINER_SCRIPT,
            text=True,
            capture_output=True,
            timeout=int(limits["timeout_seconds"]),
            check=False,
        )
        parsed = parse_result_lines(completed.stdout)
        actual = parsed.get("ACTUAL_COMMIT", "")
        status = "passed" if completed.returncode == 0 and actual == row["head_commit"] else "failed"
        error = completed.stderr.strip()[-4000:]
        if completed.returncode == 0 and actual != row["head_commit"]:
            error = f"commit_mismatch expected={row['head_commit']} actual={actual}"
        return SmokeResult(
            entry_id=row["entry_id"], name=row["name"], repository=row["repository"],
            expected_commit=row["head_commit"], actual_commit=actual,
            planned_environment=row["planned_environment"], status=status,
            started_at=started_at,
            elapsed_seconds=int(parsed.get("ELAPSED_SECONDS", time.monotonic() - started)),
            file_count=int(parsed.get("FILE_COUNT", 0)),
            tracked_file_count=int(parsed.get("TRACKED_FILE_COUNT", 0)),
            repository_kb=int(parsed.get("REPOSITORY_KB", 0)),
            submodule_count=int(parsed.get("SUBMODULE_COUNT", 0)),
            dependency_manifests=decode_lines(parsed.get("MANIFESTS_B64", "")),
            test_indicators=decode_lines(parsed.get("TEST_INDICATORS_B64", "")),
            top_level_entries=decode_lines(parsed.get("TOP_LEVEL_B64", "")),
            container_image=str(policy["source_inspection_image"]),
            container_exit_code=completed.returncode,
            error=error,
        )
    except subprocess.TimeoutExpired as exc:
        subprocess.run(
            ["podman", "rm", "--force", f"po2-source-smoke-{safe_id}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return SmokeResult(
            entry_id=row["entry_id"], name=row["name"], repository=row["repository"],
            expected_commit=row["head_commit"], actual_commit="",
            planned_environment=row["planned_environment"], status="timed_out",
            started_at=started_at, elapsed_seconds=int(time.monotonic() - started),
            file_count=0, tracked_file_count=0, repository_kb=0, submodule_count=0,
            dependency_manifests=[], test_indicators=[], top_level_entries=[],
            container_image=str(policy["source_inspection_image"]), container_exit_code=124,
            error=str(exc),
        )


def write_results(results: list[SmokeResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(exist_ok=True)
    for result in results:
        (runs_dir / f"{result.entry_id}.json").write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    fields = [
        "entry_id", "name", "repository", "expected_commit", "actual_commit",
        "planned_environment", "status", "elapsed_seconds", "file_count",
        "tracked_file_count", "repository_kb", "submodule_count",
        "dependency_manifest_count", "test_indicator_count", "container_image", "error",
    ]
    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in sorted(results, key=lambda item: item.entry_id):
            row = asdict(result)
            row["dependency_manifest_count"] = len(result.dependency_manifests)
            row["test_indicator_count"] = len(result.test_indicators)
            writer.writerow({field: row[field] for field in fields})

    passed = sum(result.status == "passed" for result in results)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate": "pinned_source_acquisition_and_structure",
        "repository_code_executed": False,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results_file": "results.csv",
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--entry-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()

    policy = load_policy()
    rows = load_queue(args.queue)
    if args.entry_id:
        wanted = set(args.entry_id)
        rows = [row for row in rows if row["entry_id"] in wanted]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("No ready smoke-test entries selected")

    results: list[SmokeResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = {executor.submit(run_one, row, policy): row for row in rows}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result.entry_id} {result.status} {result.repository} ({result.elapsed_seconds}s)", flush=True)
    write_results(results, args.output_dir)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
