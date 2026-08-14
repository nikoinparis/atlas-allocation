#!/usr/bin/env python3
"""Acquire one immutable weekly vintage and feed only it to the frozen recorder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_SCRIPT = ROOT / "scripts/acquire_free_etf_snapshot.py"
RECORDER_SCRIPT = ROOT / "scripts/record_forward_portfolio_evidence.py"
ACQUISITION_LATEST = ROOT / "evidence/free_data_acquisition/latest_result.json"
FORWARD_STATUS = ROOT / "evidence/forward_covariance_minimum_variance_v1/status.json"
OUTPUT = ROOT / "evidence/weekly_forward_cycles"
LOCK_PATH = OUTPUT / ".cycle.lock"
CUTOFF_UTC = time(21, 0)


class WeeklyCycleError(RuntimeError):
    """Raised when the guarded weekly cycle must fail closed."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def latest_closed_decision_week(now_utc: datetime) -> date:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    current = now_utc.astimezone(timezone.utc)
    candidate = current.date() - timedelta(days=(current.weekday() - 4) % 7)
    cutoff = datetime.combine(candidate, CUTOFF_UTC, tzinfo=timezone.utc)
    if current < cutoff:
        candidate -= timedelta(days=7)
    return candidate


def run_checked(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    result = {
        "command": [Path(command[0]).name, Path(command[1]).name, *command[2:]],
        "returncode": completed.returncode,
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "stdout_bytes": len(completed.stdout),
        "stderr_bytes": len(completed.stderr),
    }
    if completed.returncode != 0:
        tail = completed.stderr.decode("utf-8", errors="replace")[-1000:]
        raise WeeklyCycleError(f"subprocess failed closed: {result['command']}; stderr tail={tail}")
    return result


def existing_success_for_week(decision_week: str) -> Path | None:
    if not OUTPUT.exists():
        return None
    for path in sorted(OUTPUT.glob(f"{decision_week}-*/result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("status") == "complete":
            return path
    return None


def acquire_lock() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise WeeklyCycleError("another weekly cycle lock already exists") from error
    os.write(descriptor, f"{os.getpid()}\n".encode())
    os.fsync(descriptor)
    return descriptor


def release_lock(descriptor: int) -> None:
    os.close(descriptor)
    LOCK_PATH.unlink(missing_ok=True)


def write_cycle_result(directory: Path, result: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    acquisition = result["acquisition"]
    revision = acquisition.get("revision_comparison")
    revision_text = "No prior vintage comparison was available."
    if revision:
        revision_text = (
            f"Compared {int(revision['common_rows']):,} common price rows; "
            f"{int(revision['revised_rows']):,} were revised, "
            f"{int(revision['new_keys']):,} were new, and "
            f"{int(revision['disappeared_keys']):,} disappeared."
        )
        if "magnitude_by_field" in revision:
            adjusted = revision["magnitude_by_field"]["adjusted_close"]
            revision_text += (
                f" Raw-close changes: {int(revision['magnitude_by_field']['close']['exact_change_count']):,}; "
                f"maximum adjusted-close relative change: {float(adjusted['maximum_relative_difference']) * 100:.6f}%; "
                f"changes over the 0.01% materiality threshold: "
                f"{int(revision['economically_material_adjusted_close_rows']):,}."
            )
    status = result["forward_status"]
    report = "\n".join([
        "# Guarded Weekly Forward Cycle", "",
        f"Decision week: **{result['decision_week']}**", "",
        f"- Cycle status: **{result['status']}**.",
        f"- Immutable snapshot: `{acquisition['snapshot_id']}`.",
        f"- Latest market date: **{acquisition['freshness']['latest_observation_date']}**.",
        f"- Forward decisions appended: **{result['recorder_delta']['decisions']}**.",
        f"- Forward observations appended: **{result['recorder_delta']['observations']}**.",
        f"- Untouched clock: **{status['observed_weeks']}/{status['required_weeks']}**.",
        "- Execution enabled: **no**.", "",
        revision_text, "",
        "A successful collection does not imply an eligible forward decision. The frozen recorder independently enforces its August 14 boundary and weekly snapshot windows.", "",
    ])
    (directory / "report.md").write_text(report, encoding="utf-8")


def run_cycle(*, period: str, allow_additional_vintage: bool) -> dict[str, object]:
    started = datetime.now(timezone.utc)
    decision_week = latest_closed_decision_week(started).isoformat()
    prior = existing_success_for_week(decision_week)
    if prior and not allow_additional_vintage:
        raise WeeklyCycleError(
            f"a complete cycle already exists for {decision_week}: {prior.parent.name}"
        )
    descriptor = acquire_lock()
    try:
        before_status = json.loads(FORWARD_STATUS.read_text(encoding="utf-8"))
        acquisition_process = run_checked([
            sys.executable, str(ACQUISITION_SCRIPT), "--period", period
        ])
        acquisition = json.loads(ACQUISITION_LATEST.read_text(encoding="utf-8"))
        observed_at = datetime.fromisoformat(
            str(acquisition["observed_at_utc"]).replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        expected_week = latest_closed_decision_week(observed_at).isoformat()
        if expected_week != decision_week:
            raise WeeklyCycleError(
                f"acquisition crossed a weekly boundary: expected {decision_week}, got {expected_week}"
            )
        if not acquisition["freshness"]["freshness_pass"]:
            raise WeeklyCycleError("new immutable snapshot failed its freshness gate")
        snapshot_id = str(acquisition["snapshot_id"])
        recorder_process = run_checked([
            sys.executable, str(RECORDER_SCRIPT), "--snapshot-id", snapshot_id
        ])
        after_status = json.loads(FORWARD_STATUS.read_text(encoding="utf-8"))
        if after_status["observed_weeks"] < before_status["observed_weeks"]:
            raise WeeklyCycleError("forward observation count moved backward")
        if after_status["saved_decisions"] < before_status["saved_decisions"]:
            raise WeeklyCycleError("forward decision count moved backward")
        if after_status["execution_enabled"]:
            raise WeeklyCycleError("forward cycle unexpectedly enabled execution")
        result = {
            "schema_version": 1,
            "cycle_version": "guarded_weekly_forward_cycle_v1",
            "started_at_utc": started.isoformat(),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "decision_week": decision_week,
            "status": "complete",
            "acquisition": acquisition,
            "acquisition_process": acquisition_process,
            "recorder_process": recorder_process,
            "recorder_delta": {
                "decisions": int(after_status["saved_decisions"]) - int(before_status["saved_decisions"]),
                "observations": int(after_status["observed_weeks"]) - int(before_status["observed_weeks"]),
            },
            "forward_status": after_status,
            "execution_enabled": False,
            "broker_connection": None,
        }
        cycle_id = f"{decision_week}-{snapshot_id}"
        destination = OUTPUT / cycle_id
        write_cycle_result(destination, result)
        (OUTPUT / "latest_result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result
    finally:
        release_lock(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="max")
    parser.add_argument("--allow-additional-vintage", action="store_true")
    args = parser.parse_args()
    try:
        result = run_cycle(
            period=args.period, allow_additional_vintage=args.allow_additional_vintage
        )
    except WeeklyCycleError as error:
        print(json.dumps({"status": "rejected", "reason": str(error)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": result["status"],
        "decision_week": result["decision_week"],
        "snapshot_id": result["acquisition"]["snapshot_id"],
        "revision_comparison": result["acquisition"]["revision_comparison"],
        "recorder_delta": result["recorder_delta"],
        "observed_weeks": result["forward_status"]["observed_weeks"],
        "required_weeks": result["forward_status"]["required_weeks"],
        "execution_enabled": result["execution_enabled"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
