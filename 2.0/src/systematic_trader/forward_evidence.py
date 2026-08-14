"""Hash-chained append-only evidence primitives for frozen forward tests."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path


class ForwardEvidenceError(ValueError):
    """Raised when a forward record would weaken the frozen evidence boundary."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def record_hash(record_without_hash: dict[str, object]) -> str:
    return hashlib.sha256(canonical_bytes(record_without_hash)).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if path.exists():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def read_and_verify_log(
    path: Path, *, date_field: str, first_eligible_date: str
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    previous_hash = "0" * 64
    seen_dates: set[str] = set()
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ForwardEvidenceError(f"{path.name}:{line_number} contains a blank record")
        record = json.loads(line)
        supplied_hash = str(record.get("record_hash", ""))
        basis = {key: value for key, value in record.items() if key != "record_hash"}
        if supplied_hash != record_hash(basis):
            raise ForwardEvidenceError(f"{path.name}:{line_number} record hash mismatch")
        if record.get("sequence") != line_number:
            raise ForwardEvidenceError(f"{path.name}:{line_number} sequence mismatch")
        if record.get("previous_record_hash") != previous_hash:
            raise ForwardEvidenceError(f"{path.name}:{line_number} chain mismatch")
        record_date = str(record.get(date_field, ""))
        try:
            parsed = date.fromisoformat(record_date)
        except ValueError as error:
            raise ForwardEvidenceError(f"{path.name}:{line_number} invalid {date_field}") from error
        if parsed < date.fromisoformat(first_eligible_date):
            raise ForwardEvidenceError(f"{path.name}:{line_number} predates the frozen boundary")
        if record_date in seen_dates:
            raise ForwardEvidenceError(f"{path.name}:{line_number} duplicates {record_date}")
        if records and record_date <= str(records[-1][date_field]):
            raise ForwardEvidenceError(f"{path.name}:{line_number} is not chronological")
        seen_dates.add(record_date)
        previous_hash = supplied_hash
        records.append(record)
    return records


def append_record(
    path: Path,
    payload: dict[str, object],
    *,
    date_field: str,
    first_eligible_date: str,
) -> dict[str, object]:
    existing = read_and_verify_log(
        path, date_field=date_field, first_eligible_date=first_eligible_date
    )
    record_date = str(payload.get(date_field, ""))
    try:
        parsed = date.fromisoformat(record_date)
    except ValueError as error:
        raise ForwardEvidenceError(f"new record has invalid {date_field}") from error
    if parsed < date.fromisoformat(first_eligible_date):
        raise ForwardEvidenceError("new record predates the frozen boundary")
    if any(str(record[date_field]) == record_date for record in existing):
        raise ForwardEvidenceError(f"record already exists for {record_date}")
    if existing and record_date <= str(existing[-1][date_field]):
        raise ForwardEvidenceError("new record is not later than the log head")
    basis = {
        **payload,
        "sequence": len(existing) + 1,
        "previous_record_hash": existing[-1]["record_hash"] if existing else "0" * 64,
    }
    record = {**basis, "record_hash": record_hash(basis)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    read_and_verify_log(path, date_field=date_field, first_eligible_date=first_eligible_date)
    return record


def verify_pinned_files(root: Path, pinned: dict[str, str]) -> None:
    for relative, expected in pinned.items():
        path = root / relative
        if not path.is_file() or file_hash(path) != expected:
            raise ForwardEvidenceError(f"frozen dependency changed: {relative}")
