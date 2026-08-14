"""Immutable, bitemporal market-data snapshots with strict point-in-time gates."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable


CLAIM_NAMES = (
    "point_in_time_prices",
    "point_in_time_universe",
    "permanent_security_ids",
    "corporate_actions",
    "delistings",
    "vintage_revisions",
)

REQUIRED_COLUMNS = {
    "prices.csv": {
        "observation_date", "security_id", "ticker", "adjusted_close", "knowledge_at_utc", "source_revision"
    },
    "universe_membership.csv": {
        "security_id", "ticker", "universe", "effective_from", "effective_to", "knowledge_at_utc", "source_revision"
    },
    "security_master.csv": {
        "security_id", "permanent_id_source", "ticker", "first_observed_date", "last_observed_date", "delisting_date", "knowledge_at_utc"
    },
    "corporate_actions.csv": {
        "security_id", "ticker", "event_date", "action_type", "amount", "knowledge_at_utc", "source_revision"
    },
    "delistings.csv": {
        "security_id", "ticker", "delisting_date", "delisting_return", "reason", "knowledge_at_utc", "source_revision"
    },
}


class DataVintageError(ValueError):
    """Raised when a snapshot violates provenance, schema, or availability rules."""


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise DataVintageError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_header(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return set(next(csv.reader(handle), []))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _require_columns(logical_name: str, path: Path) -> None:
    missing = REQUIRED_COLUMNS[logical_name] - read_header(path)
    if missing:
        raise DataVintageError(f"{logical_name} is missing columns: {sorted(missing)}")


def _validate_knowledge_times(path: Path, observed_at: datetime) -> None:
    if "knowledge_at_utc" not in read_header(path):
        return
    for row_number, row in enumerate(read_rows(path), start=2):
        value = row.get("knowledge_at_utc")
        if not value:
            raise DataVintageError(f"{path.name}:{row_number} has no knowledge_at_utc")
        if parse_utc(value) > observed_at:
            raise DataVintageError(f"{path.name}:{row_number} was not known at snapshot observation time")


def _validate_prices(path: Path) -> None:
    seen: set[tuple[str, str]] = set()
    for row_number, row in enumerate(read_rows(path), start=2):
        key = (row["observation_date"], row["security_id"])
        if key in seen:
            raise DataVintageError(f"prices.csv:{row_number} duplicates {key}")
        seen.add(key)
        date.fromisoformat(row["observation_date"])
        value = float(row["adjusted_close"])
        if not math.isfinite(value) or value <= 0.0:
            raise DataVintageError(f"prices.csv:{row_number} has invalid adjusted_close")


def _validate_membership(path: Path) -> None:
    intervals: dict[tuple[str, str], list[tuple[date, date | None]]] = {}
    for row_number, row in enumerate(read_rows(path), start=2):
        start = date.fromisoformat(row["effective_from"])
        end = date.fromisoformat(row["effective_to"]) if row["effective_to"] else None
        if end is not None and end < start:
            raise DataVintageError(f"universe_membership.csv:{row_number} ends before it begins")
        intervals.setdefault((row["security_id"], row["universe"]), []).append((start, end))
    for key, values in intervals.items():
        values.sort()
        for previous, current in zip(values, values[1:]):
            if previous[1] is None or current[0] <= previous[1]:
                raise DataVintageError(f"overlapping membership intervals for {key}")


def validate_bundle(files: dict[str, Path], descriptor: dict[str, object]) -> dict[str, bool]:
    required_descriptor = {
        "provider", "dataset_kind", "observed_at_utc", "observed_at_basis", "source_uri",
        "source_license", "revision_policy", "publication_lag_policy", "claims",
    }
    missing_descriptor = required_descriptor - set(descriptor)
    if missing_descriptor:
        raise DataVintageError(f"descriptor is missing: {sorted(missing_descriptor)}")
    claims = descriptor["claims"]
    if not isinstance(claims, dict) or set(claims) != set(CLAIM_NAMES):
        raise DataVintageError(f"claims must contain exactly: {list(CLAIM_NAMES)}")
    if any(not isinstance(claims[name], bool) for name in CLAIM_NAMES):
        raise DataVintageError("all claims must be boolean")
    observed_at = parse_utc(str(descriptor["observed_at_utc"]))
    for logical_name, path in files.items():
        if Path(logical_name).name != logical_name or not path.is_file():
            raise DataVintageError(f"invalid snapshot file: {logical_name}")
        _validate_knowledge_times(path, observed_at)
        if logical_name in REQUIRED_COLUMNS:
            _require_columns(logical_name, path)

    required_by_claim = {
        "point_in_time_prices": ("prices.csv",),
        "point_in_time_universe": ("universe_membership.csv",),
        "permanent_security_ids": ("security_master.csv",),
        "corporate_actions": ("corporate_actions.csv",),
        "delistings": ("delistings.csv",),
    }
    for claim, required_files in required_by_claim.items():
        if claims[claim]:
            for logical_name in required_files:
                if logical_name not in files:
                    raise DataVintageError(f"claim {claim} requires {logical_name}")
    if "prices.csv" in files:
        _validate_prices(files["prices.csv"])
    if claims["point_in_time_universe"]:
        _validate_membership(files["universe_membership.csv"])
    return {name: bool(claims[name]) for name in CLAIM_NAMES}


@dataclass(frozen=True)
class SnapshotSelection:
    snapshot_id: str
    observed_at_utc: str
    manifest_path: Path


class SnapshotStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def ingest(self, files: dict[str, Path], descriptor: dict[str, object]) -> dict[str, object]:
        normalized = {name: Path(path).resolve() for name, path in files.items()}
        claims = validate_bundle(normalized, descriptor)
        file_records = {
            name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for name, path in sorted(normalized.items())
        }
        digest_basis = {"descriptor": descriptor, "files": file_records}
        content_digest = hashlib.sha256(canonical_json(digest_basis)).hexdigest()
        observed_at = parse_utc(str(descriptor["observed_at_utc"]))
        snapshot_id = observed_at.strftime("%Y%m%dT%H%M%SZ") + "-" + content_digest[:16]
        destination = self.root / snapshot_id
        manifest = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "content_digest": content_digest,
            "registered_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider": descriptor["provider"],
            "dataset_kind": descriptor["dataset_kind"],
            "observed_at_utc": observed_at.isoformat(),
            "observed_at_basis": descriptor["observed_at_basis"],
            "source_uri": descriptor["source_uri"],
            "source_license": descriptor["source_license"],
            "revision_policy": descriptor["revision_policy"],
            "publication_lag_policy": descriptor["publication_lag_policy"],
            "coverage": descriptor.get("coverage", {}),
            "claims": claims,
            "historical_simulation_grade": "point_in_time" if all(claims.values()) else "research_only",
            "supersedes_snapshot_id": descriptor.get("supersedes_snapshot_id"),
            "notes": descriptor.get("notes", []),
            "files": file_records,
        }
        if destination.exists():
            existing = json.loads((destination / "manifest.json").read_text())
            if existing["content_digest"] != content_digest:
                raise DataVintageError("snapshot id collision")
            self.verify(snapshot_id)
            return existing

        self.root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="snapshot-", dir=self.root))
        try:
            payload = temporary / "payload"
            payload.mkdir()
            for logical_name, source in normalized.items():
                shutil.copyfile(source, payload / logical_name)
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            temporary.rename(destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        self.verify(snapshot_id)
        return manifest

    def manifests(self) -> list[dict[str, object]]:
        if not self.root.exists():
            return []
        result = []
        for path in sorted(self.root.glob("*/manifest.json")):
            result.append(json.loads(path.read_text(encoding="utf-8")))
        return result

    def verify(self, snapshot_id: str) -> bool:
        directory = self.root / snapshot_id
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for logical_name, record in manifest["files"].items():
            path = directory / "payload" / logical_name
            if not path.is_file() or sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
                raise DataVintageError(f"snapshot integrity failure: {snapshot_id}/{logical_name}")
        return True

    def select(self, as_of_utc: str, required_claims: Iterable[str] = ()) -> SnapshotSelection:
        as_of = parse_utc(as_of_utc)
        required = tuple(required_claims)
        unknown = set(required) - set(CLAIM_NAMES)
        if unknown:
            raise DataVintageError(f"unknown claims: {sorted(unknown)}")
        eligible = []
        for manifest in self.manifests():
            if parse_utc(str(manifest["observed_at_utc"])) <= as_of and all(manifest["claims"][name] for name in required):
                eligible.append(manifest)
        if not eligible:
            raise DataVintageError("no snapshot was both known by that time and eligible for the requested claims")
        selected = max(eligible, key=lambda item: parse_utc(str(item["observed_at_utc"])))
        self.verify(str(selected["snapshot_id"]))
        return SnapshotSelection(
            snapshot_id=str(selected["snapshot_id"]),
            observed_at_utc=str(selected["observed_at_utc"]),
            manifest_path=self.root / str(selected["snapshot_id"]) / "manifest.json",
        )

    def read_csv(self, snapshot_id: str, logical_name: str, as_of_utc: str) -> list[dict[str, str]]:
        manifest = json.loads((self.root / snapshot_id / "manifest.json").read_text(encoding="utf-8"))
        as_of = parse_utc(as_of_utc)
        if parse_utc(str(manifest["observed_at_utc"])) > as_of:
            raise DataVintageError("snapshot was learned after the requested simulation time")
        self.verify(snapshot_id)
        rows = read_rows(self.root / snapshot_id / "payload" / logical_name)
        return [
            row for row in rows
            if not row.get("knowledge_at_utc") or parse_utc(row["knowledge_at_utc"]) <= as_of
        ]
