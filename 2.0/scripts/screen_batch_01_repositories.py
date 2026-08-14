#!/usr/bin/env python3
"""Screen Batch 1 backtest/execution repositories using current GitHub evidence."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BATCH = "01_backtest_execution_and_simulation"
AUDIT_VERSION = 1
PERMISSIVE_LICENSES = {
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "MPL-2.0",
    "Unlicense",
}
COPYLEFT_LICENSES = {
    "AGPL-3.0",
    "GPL-2.0",
    "GPL-3.0",
    "LGPL-2.1",
    "LGPL-3.0",
}

EVIDENCE_FIELDS = (
    "entry_id",
    "name",
    "repository",
    "url",
    "description",
    "archived",
    "fork",
    "created_at",
    "pushed_at",
    "days_since_push",
    "maintenance_status",
    "stars",
    "forks",
    "disk_usage_kb",
    "default_branch",
    "head_commit",
    "head_commit_date",
    "latest_release",
    "latest_release_date",
    "license_spdx",
    "license_review",
    "license_source",
    "license_evidence_path",
    "primary_language",
    "languages",
    "dependency_manifests",
    "ci_workflow_count",
    "ci_workflows",
    "top_level_test_indicators",
    "docs_present",
    "examples_present",
    "security_policy_present",
    "capability_flags",
    "data_profile",
    "installation_complexity",
    "screening_score",
    "health_band",
    "recommended_action",
    "blocking_concerns",
    "screening_notes",
)


@dataclass
class Screening:
    entry_id: str
    name: str
    repository: str
    url: str
    description: str
    archived: bool
    fork: bool
    created_at: str
    pushed_at: str
    days_since_push: int | str
    maintenance_status: str
    stars: int
    forks: int
    disk_usage_kb: int
    default_branch: str
    head_commit: str
    head_commit_date: str
    latest_release: str
    latest_release_date: str
    license_spdx: str
    license_review: str
    license_source: str
    license_evidence_path: str
    primary_language: str
    languages: str
    dependency_manifests: str
    ci_workflow_count: int
    ci_workflows: str
    top_level_test_indicators: str
    docs_present: bool
    examples_present: bool
    security_policy_present: bool
    capability_flags: str
    data_profile: str
    installation_complexity: str
    screening_score: int
    health_band: str
    recommended_action: str
    blocking_concerns: str
    screening_notes: str


def build_query(
    rows: list[dict[str, str]], alias_offset: int = 0
) -> tuple[str, dict[str, dict[str, str]]]:
    aliases: list[str] = []
    alias_rows: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, 1 + alias_offset):
        owner, name = row["github_repository"].split("/", 1)
        alias = f"repo_{index:03d}"
        alias_rows[alias] = row
        owner_json = json.dumps(owner)
        name_json = json.dumps(name)
        aliases.append(
            f"""
            {alias}: repository(owner: {owner_json}, name: {name_json}) {{
              nameWithOwner
              url
              description
              isArchived
              isFork
              createdAt
              updatedAt
              pushedAt
              stargazerCount
              forkCount
              diskUsage
              defaultBranchRef {{ name target {{ ... on Commit {{ oid committedDate }} }} }}
              licenseInfo {{ spdxId name }}
              primaryLanguage {{ name }}
              languages(first: 8, orderBy: {{field: SIZE, direction: DESC}}) {{ nodes {{ name }} }}
              releases(last: 1) {{ nodes {{ tagName publishedAt }} }}
              issues(states: OPEN) {{ totalCount }}
              pullRequests(states: OPEN) {{ totalCount }}
              root: object(expression: "HEAD:") {{ ... on Tree {{ entries {{ name type }} }} }}
              workflows: object(expression: "HEAD:.github/workflows") {{
                ... on Tree {{ entries {{ name type }} }}
              }}
            }}
            """
        )
    return "query Batch01RepositoryScreen {" + "\n".join(aliases) + "\n}", alias_rows


def fetch_github_metadata(query: str) -> dict[str, Any]:
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"GitHub GraphQL request failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_github_metadata_in_chunks(
    rows: list[dict[str, str]], chunk_size: int = 8
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    merged: dict[str, Any] = {"data": {}, "errors": []}
    all_alias_rows: dict[str, dict[str, str]] = {}
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        query, alias_rows = build_query(chunk, alias_offset=start)
        payload = fetch_github_metadata(query)
        merged["data"].update(payload.get("data") or {})
        merged["errors"].extend(payload.get("errors") or [])
        all_alias_rows.update(alias_rows)
    if not merged["errors"]:
        merged.pop("errors")
    return merged, all_alias_rows


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def maintenance_status(metadata: dict[str, Any], audit_time: datetime) -> tuple[str, int | str]:
    if metadata.get("isArchived"):
        return "archived", ""
    pushed = parse_timestamp(metadata.get("pushedAt"))
    if not pushed:
        return "unknown_no_push_date", ""
    days = max(0, (audit_time - pushed).days)
    if days <= 180:
        return "active_0_180_days", days
    if days <= 365:
        return "maintained_181_365_days", days
    if days <= 730:
        return "quiet_366_730_days", days
    return "stale_over_730_days", days


def root_names(metadata: dict[str, Any], key: str = "root") -> list[str]:
    tree = metadata.get(key) or {}
    return [entry["name"] for entry in (tree.get("entries") or [])]


def dependency_manifests(names: list[str]) -> list[str]:
    manifest_patterns = (
        r"^pyproject\.toml$",
        r"^setup\.py$",
        r"^setup\.cfg$",
        r"^requirements.*\.txt$",
        r"^environment.*\.ya?ml$",
        r"^Pipfile$",
        r"^poetry\.lock$",
        r"^uv\.lock$",
        r"^Cargo\.toml$",
        r"^go\.mod$",
        r"^package\.json$",
        r"^pnpm-lock\.yaml$",
        r"^yarn\.lock$",
        r"^CMakeLists\.txt$",
        r"^Makefile$",
        r".*\.sln$",
        r".*\.csproj$",
        r"^pom\.xml$",
        r"^build\.gradle.*$",
        r"^Dockerfile.*$",
    )
    return sorted(name for name in names if any(re.match(pattern, name) for pattern in manifest_patterns))


def test_indicators(names: list[str], workflows: list[str]) -> list[str]:
    indicators = [
        name
        for name in names
        if name.lower() in {"test", "tests", "testing", "test_data", "pytest.ini", "tox.ini"}
        or name.lower().startswith("test_")
    ]
    if any("test" in workflow.lower() or "ci" in workflow.lower() for workflow in workflows):
        indicators.append("ci_test_named_workflow")
    return sorted(set(indicators))


def license_review(metadata: dict[str, Any], names: list[str]) -> tuple[str, str]:
    license_info = metadata.get("licenseInfo") or {}
    spdx = license_info.get("spdxId") or ""
    has_license_file = any(name.lower().startswith(("license", "licence", "copying")) for name in names)
    if spdx in PERMISSIVE_LICENSES:
        return spdx, "recognized_permissive"
    if spdx in COPYLEFT_LICENSES:
        return spdx, "recognized_copyleft_review_obligations"
    if spdx and spdx != "NOASSERTION":
        return spdx, "recognized_other_review_required"
    if has_license_file:
        return spdx or "UNRECOGNIZED", "license_file_present_manual_review_required"
    return "MISSING", "no_top_level_license_detected"


def classify_license_text(text: str) -> tuple[str, str]:
    normalized = " ".join(text.split()).lower()
    header = normalized[:800]
    if "commons clause" in normalized and "right to sell" in normalized:
        return "LicenseRef-Commons-Clause", "source_available_restricted_commercial_use"
    if "版权所有" in text and "非商业用途" in text and "商业用途" in text:
        return "LicenseRef-RQAlpha-NonCommercial", "source_available_noncommercial_restriction"
    if "gnu affero general public license" in header and "version 3" in header:
        return "AGPL-3.0", "manually_confirmed_copyleft_review_obligations"
    if "gnu general public license" in header and "version 3" in header:
        return "GPL-3.0", "manually_confirmed_copyleft_review_obligations"
    if "permission is hereby granted, free of charge" in normalized:
        return "MIT", "manually_confirmed_permissive"
    if "apache license" in normalized and "version 2.0" in normalized:
        return "Apache-2.0", "manually_confirmed_permissive"
    if "do what the fuck you want to public license" in normalized:
        return "LicenseRef-WTFPL-Variant", "custom_license_manual_legal_review"
    return "UNRECOGNIZED", "license_text_manual_legal_review"


def license_score_points(review: str) -> int:
    if review.startswith(("recognized_", "manually_confirmed_")):
        return 15
    if review == "no_top_level_license_detected":
        return 0
    return 5


def resolve_nonstandard_licenses(screenings: list[Screening], output_dir: Path) -> None:
    snapshot_dir = output_dir / "license_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    api_metadata: dict[str, Any] = {}
    for screening in screenings:
        if screening.license_review not in {
            "license_file_present_manual_review_required",
            "no_top_level_license_detected",
        }:
            continue
        old_points = license_score_points(screening.license_review)
        result = subprocess.run(
            ["gh", "api", f"repos/{screening.repository}/license"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            screening.license_source = "github_license_endpoint_not_found"
            api_metadata[screening.entry_id] = {
                "repository": screening.repository,
                "status": "not_found",
            }
            continue
        payload = json.loads(result.stdout)
        content = base64.b64decode(payload.get("content") or "").decode("utf-8", "replace")
        safe_repo = screening.repository.replace("/", "__")
        snapshot_path = snapshot_dir / f"{screening.entry_id}_{safe_repo}.txt"
        snapshot_path.write_text(content, encoding="utf-8")
        spdx, review = classify_license_text(content)
        screening.license_spdx = spdx
        screening.license_review = review
        screening.license_source = "license_file_text_review"
        screening.license_evidence_path = str(snapshot_path.relative_to(output_dir))
        screening.screening_score = min(
            100,
            screening.screening_score - old_points + license_score_points(review),
        )
        screening.health_band = health_band(screening.screening_score)
        action, blockers = recommended_action(
            {"isArchived": screening.archived},
            screening.maintenance_status,
            screening.license_review,
            screening.health_band,
        )
        screening.recommended_action = action
        screening.blocking_concerns = ";".join(blockers)
        api_metadata[screening.entry_id] = {
            "repository": screening.repository,
            "status": "retrieved",
            "path": payload.get("path"),
            "api_spdx": (payload.get("license") or {}).get("spdx_id"),
            "classified_spdx": spdx,
            "review": review,
            "snapshot": screening.license_evidence_path,
        }
    (output_dir / "license_resolution.json").write_text(
        json.dumps(api_metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def capability_flags(row: dict[str, str], metadata: dict[str, Any]) -> list[str]:
    text = " ".join(
        [row.get("description", ""), metadata.get("description") or "", row.get("name", "")]
    ).lower()
    keywords = {
        "backtesting": ("backtest", "backtesting"),
        "live_execution": ("live trading", "live-trading", "deploy"),
        "event_driven": ("event driven", "event-driven"),
        "vectorized": ("vector", "vectorized"),
        "machine_learning": ("machine learning", " ml ", "deep learning"),
        "crypto": ("crypto", "bitcoin", "exchange"),
        "options": ("option", "options"),
        "high_frequency": ("high-frequency", "high frequency", "hft", "latency"),
        "portfolio_management": ("portfolio", "allocation"),
        "screening": ("screen", "scanner"),
    }
    return [flag for flag, needles in keywords.items() if any(needle in text for needle in needles)]


def infer_data_profile(flags: list[str], text: str) -> str:
    lower = text.lower()
    if "high_frequency" in flags or "order book" in lower or "tick data" in lower:
        return "tick_quotes_or_order_book_data"
    if "options" in flags:
        return "options_chains_quotes_and_underlying_prices"
    if "crypto" in flags:
        return "crypto_bars_trades_or_exchange_feeds"
    if "screening" in flags:
        return "external_market_screening_provider"
    return "historical_bars_and_reference_data"


def installation_complexity(
    manifests: list[str], languages: list[str], disk_usage: int, archived: bool
) -> str:
    compiled = {"C", "C++", "C#", "Rust", "Cython", "Java"}
    complexity = 0
    complexity += 2 if len(set(languages) & compiled) >= 2 else int(bool(set(languages) & compiled))
    complexity += int(len(manifests) >= 4)
    complexity += int(disk_usage >= 250_000)
    complexity += int(archived)
    if complexity >= 4:
        return "high"
    if complexity >= 2:
        return "medium_high"
    if complexity == 1:
        return "medium"
    return "low"


def score_repository(
    metadata: dict[str, Any],
    maintenance: str,
    license_state: str,
    workflows: list[str],
    tests: list[str],
    names: list[str],
    latest_release_date: str,
    audit_time: datetime,
) -> int:
    score = 0
    if not metadata.get("isArchived"):
        score += 15
    score += {
        "active_0_180_days": 25,
        "maintained_181_365_days": 20,
        "quiet_366_730_days": 10,
    }.get(maintenance, 0)
    if license_state.startswith("recognized_"):
        score += 15
    elif license_state.startswith("license_file_present"):
        score += 5
    if workflows:
        score += 15
    if tests:
        score += 10
    if any(name.lower() in {"docs", "documentation", "examples", "example"} for name in names):
        score += 5
    if any(name.lower().startswith("security") for name in names):
        score += 5
    release_date = parse_timestamp(latest_release_date)
    if release_date and (audit_time - release_date).days <= 730:
        score += 10
    return min(score, 100)


def health_band(score: int) -> str:
    if score >= 80:
        return "strong_screening_signals"
    if score >= 60:
        return "promising_screening_signals"
    if score >= 40:
        return "caution"
    return "high_risk_or_insufficient_evidence"


def recommended_action(
    metadata: dict[str, Any], maintenance: str, license_state: str, band: str
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if metadata.get("isArchived"):
        blockers.append("repository_archived")
    if maintenance == "stale_over_730_days":
        blockers.append("stale_over_two_years")
    if license_state == "no_top_level_license_detected":
        blockers.append("license_not_detected")
    if license_state == "license_file_present_manual_review_required":
        blockers.append("license_not_machine_readable")
    if license_state == "recognized_copyleft_review_obligations":
        blockers.append("copyleft_obligations_require_review")
    if license_state == "manually_confirmed_copyleft_review_obligations":
        blockers.append("copyleft_obligations_require_review")
    if license_state in {
        "source_available_restricted_commercial_use",
        "source_available_noncommercial_restriction",
    }:
        blockers.append("source_available_license_restricts_commercial_use")
    if license_state in {
        "custom_license_manual_legal_review",
        "license_text_manual_legal_review",
    }:
        blockers.append("custom_license_requires_legal_review")
    if metadata.get("isArchived") or maintenance == "stale_over_730_days":
        return "reference_only_for_now", blockers
    if blockers or band in {"caution", "high_risk_or_insufficient_evidence"}:
        return "manual_review_before_sandbox", blockers
    return "isolated_smoke_test_candidate", blockers


def screen_row(
    row: dict[str, str], metadata: dict[str, Any], audit_time: datetime
) -> Screening:
    names = root_names(metadata)
    workflows = root_names(metadata, "workflows")
    manifests = dependency_manifests(names)
    tests = test_indicators(names, workflows)
    maintenance, days_since_push = maintenance_status(metadata, audit_time)
    spdx, license_state = license_review(metadata, names)
    languages = [node["name"] for node in ((metadata.get("languages") or {}).get("nodes") or [])]
    release_nodes = (metadata.get("releases") or {}).get("nodes") or []
    latest_release = release_nodes[-1] if release_nodes else {}
    release_date = latest_release.get("publishedAt") or ""
    flags = capability_flags(row, metadata)
    data_profile = infer_data_profile(flags, " ".join([row["description"], metadata.get("description") or ""]))
    install_complexity = installation_complexity(
        manifests, languages, metadata.get("diskUsage") or 0, bool(metadata.get("isArchived"))
    )
    score = score_repository(
        metadata,
        maintenance,
        license_state,
        workflows,
        tests,
        names,
        release_date,
        audit_time,
    )
    band = health_band(score)
    action, blockers = recommended_action(metadata, maintenance, license_state, band)
    branch = metadata.get("defaultBranchRef") or {}
    commit = branch.get("target") or {}
    notes = []
    if not workflows:
        notes.append("no_GitHub_Actions_workflows_detected")
    if not tests:
        notes.append("no_top_level_test_indicator_detected")
    if not release_nodes:
        notes.append("no_GitHub_release_detected")
    notes.append("screening_score_is_triage_not_code_quality_or_profitability")
    return Screening(
        entry_id=row["entry_id"],
        name=row["name"],
        repository=metadata.get("nameWithOwner") or row["github_repository"],
        url=metadata.get("url") or row["primary_url"],
        description=metadata.get("description") or row["description"],
        archived=bool(metadata.get("isArchived")),
        fork=bool(metadata.get("isFork")),
        created_at=metadata.get("createdAt") or "",
        pushed_at=metadata.get("pushedAt") or "",
        days_since_push=days_since_push,
        maintenance_status=maintenance,
        stars=metadata.get("stargazerCount") or 0,
        forks=metadata.get("forkCount") or 0,
        disk_usage_kb=metadata.get("diskUsage") or 0,
        default_branch=branch.get("name") or "",
        head_commit=commit.get("oid") or "",
        head_commit_date=commit.get("committedDate") or "",
        latest_release=latest_release.get("tagName") or "",
        latest_release_date=release_date,
        license_spdx=spdx,
        license_review=license_state,
        license_source="github_machine_readable_detection",
        license_evidence_path="",
        primary_language=(metadata.get("primaryLanguage") or {}).get("name") or "",
        languages=";".join(languages),
        dependency_manifests=";".join(manifests),
        ci_workflow_count=len(workflows),
        ci_workflows=";".join(workflows),
        top_level_test_indicators=";".join(tests),
        docs_present=any(name.lower() in {"docs", "doc", "documentation"} for name in names),
        examples_present=any(name.lower() in {"examples", "example", "samples"} for name in names),
        security_policy_present=any(name.lower().startswith("security") for name in names),
        capability_flags=";".join(flags),
        data_profile=data_profile,
        installation_complexity=install_complexity,
        screening_score=score,
        health_band=band,
        recommended_action=action,
        blocking_concerns=";".join(blockers),
        screening_notes=";".join(notes),
    )


def write_csv(path: Path, screenings: list[Screening]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_FIELDS)
        writer.writeheader()
        for screening in screenings:
            writer.writerow(screening.__dict__)


def update_master_registry(
    registry_path: Path, screenings: list[Screening], evidence_relative_path: str
) -> None:
    with registry_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])
    by_id = {screening.entry_id: screening for screening in screenings}
    for row in rows:
        screening = by_id.get(row["entry_id"])
        if not screening:
            continue
        row["license"] = screening.license_spdx
        row["maintenance_status"] = screening.maintenance_status
        row["data_requirements"] = screening.data_profile
        row["test_status"] = "source_screened"
        row["evidence_path"] = evidence_relative_path
        row["decision"] = (
            "sandbox" if screening.recommended_action == "isolated_smoke_test_candidate" else "review"
        )
        row["rationale"] = (
            f"{screening.recommended_action}; health={screening.health_band}; "
            f"score={screening.screening_score}; concerns={screening.blocking_concerns or 'none'}"
        )
    with registry_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, screenings: list[Screening], audit_time: datetime) -> None:
    actions = Counter(item.recommended_action for item in screenings)
    bands = Counter(item.health_band for item in screenings)
    licenses = Counter(item.license_review for item in screenings)
    shortlist = sorted(
        (item for item in screenings if item.recommended_action == "isolated_smoke_test_candidate"),
        key=lambda item: (-item.screening_score, -item.stars, item.name.lower()),
    )
    review = sorted(
        (item for item in screenings if item.recommended_action != "isolated_smoke_test_candidate"),
        key=lambda item: (item.recommended_action, item.screening_score, item.name.lower()),
    )
    lines = [
        "# Batch 1 Source-Health Screening",
        "",
        f"Audit time: {audit_time.isoformat()}",
        "",
        "This is a repository-health and installation-triage screen. It is not a code audit, "
        "strategy validation, security certification, endorsement, or evidence of profitability.",
        "",
        "## Outcome",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(actions.items()))
    lines.extend(["", "Health bands:"])
    lines.extend(f"- {key}: {value}" for key, value in sorted(bands.items()))
    lines.extend(["", "License review states:"])
    lines.extend(f"- {key}: {value}" for key, value in sorted(licenses.items()))
    lines.extend(
        [
            "",
            "## Isolated smoke-test candidates",
            "",
            "| Project | Score | Activity | License | Install | Primary role signals |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for item in shortlist:
        lines.append(
            f"| [{item.name}]({item.url}) | {item.screening_score} | "
            f"{item.maintenance_status} | {item.license_spdx} | "
            f"{item.installation_complexity} | {item.capability_flags or 'unspecified'} |"
        )
    lines.extend(
        [
            "",
            "## Manual review or reference-only queue",
            "",
            "| Project | Score | Action | Concerns |",
            "|---|---:|---|---|",
        ]
    )
    for item in review:
        lines.append(
            f"| [{item.name}]({item.url}) | {item.screening_score} | "
            f"{item.recommended_action} | {item.blocking_concerns or item.screening_notes} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation rules",
            "",
            "- Missing machine-readable license metadata blocks installation until the actual license is reviewed.",
            "- Copyleft projects remain candidates, but integration boundaries and distribution obligations require review.",
            "- Archived or stale projects remain available as design references and strategy ideas.",
            "- GitHub Actions and top-level test folders are only screening signals; deeper code review may find more or less coverage.",
            "- Popularity contributes no points. Stars and forks are recorded as context only.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def smoke_environment(screening: Screening) -> str:
    languages = set(screening.languages.split(";"))
    if "C#" in languages:
        return "dotnet_container"
    if "Rust" in languages:
        return "rust_container"
    if "C++" in languages or "C" in languages:
        return "native_build_container"
    if languages & {"TypeScript", "JavaScript"} and "Python" not in languages:
        return "node_container"
    return "python_container"


def write_smoke_test_queue(output_dir: Path, screenings: list[Screening]) -> None:
    runtimes = {name: shutil.which(name) for name in ("docker", "podman")}
    available_runtime = next((name for name, path in runtimes.items() if path), "")
    runtime_evidence = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "container_runtimes": runtimes,
        "available_runtime": available_runtime or None,
        "policy": "Do not execute third-party build or installation code on the host workspace.",
    }
    (output_dir / "isolation_runtime.json").write_text(
        json.dumps(runtime_evidence, indent=2) + "\n", encoding="utf-8"
    )
    fields = (
        "entry_id",
        "name",
        "repository",
        "head_commit",
        "recommended_action",
        "planned_environment",
        "planned_checks",
        "queue_status",
        "queue_blocker",
    )
    with (output_dir / "smoke_test_queue.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in screenings:
            if item.recommended_action == "isolated_smoke_test_candidate":
                status = "ready" if available_runtime else "awaiting_isolation_runtime"
                blocker = "" if available_runtime else "docker_or_podman_not_available"
            elif item.recommended_action == "manual_review_before_sandbox":
                status = "awaiting_license_or_source_review"
                blocker = item.blocking_concerns or "deeper_source_review_required"
            else:
                status = "static_reference_only_for_now"
                blocker = item.blocking_concerns
            writer.writerow(
                {
                    "entry_id": item.entry_id,
                    "name": item.name,
                    "repository": item.repository,
                    "head_commit": item.head_commit,
                    "recommended_action": item.recommended_action,
                    "planned_environment": smoke_environment(item),
                    "planned_checks": (
                        "dependency_resolution;minimal_import_or_build;bundled_test_discovery;"
                        "canonical_fixture_adapter_assessment"
                    ),
                    "queue_status": status,
                    "queue_blocker": blocker,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    project_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--registry", type=Path, default=project_root / "research_registry" / "registry.csv"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "evidence" / "batch_01_backtest_execution",
    )
    parser.add_argument("--metadata-file", type=Path)
    args = parser.parse_args()

    with args.registry.open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["review_batch"] == BATCH]
    if not rows or any(not row["github_repository"] for row in rows):
        raise SystemExit("Batch 1 registry rows are missing GitHub repositories")

    if args.metadata_file:
        payload = json.loads(args.metadata_file.read_text(encoding="utf-8"))
        _, alias_rows = build_query(rows)
    else:
        payload, alias_rows = fetch_github_metadata_in_chunks(rows)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_time = datetime.now(timezone.utc)
    raw_path = output_dir / "github_metadata.json"
    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    data = payload.get("data") or {}
    screenings: list[Screening] = []
    unavailable: list[str] = []
    for alias, row in alias_rows.items():
        metadata = data.get(alias)
        if not metadata:
            unavailable.append(row["github_repository"])
            continue
        screenings.append(screen_row(row, metadata, audit_time))
    if unavailable:
        raise RuntimeError(f"Unavailable repositories require explicit evidence rows: {unavailable}")
    if len(screenings) != len(rows):
        raise RuntimeError(f"Expected {len(rows)} screenings, got {len(screenings)}")

    resolve_nonstandard_licenses(screenings, output_dir)
    evidence_path = output_dir / "source_health.csv"
    write_csv(evidence_path, screenings)
    write_report(output_dir / "report.md", screenings, audit_time)
    write_smoke_test_queue(output_dir, screenings)
    summary = {
        "audit_version": AUDIT_VERSION,
        "audit_time_utc": audit_time.isoformat(),
        "batch": BATCH,
        "repository_count": len(screenings),
        "actions": dict(sorted(Counter(item.recommended_action for item in screenings).items())),
        "health_bands": dict(sorted(Counter(item.health_band for item in screenings).items())),
        "maintenance": dict(sorted(Counter(item.maintenance_status for item in screenings).items())),
        "license_review": dict(sorted(Counter(item.license_review for item in screenings).items())),
        "installation_complexity": dict(
            sorted(Counter(item.installation_complexity for item in screenings).items())
        ),
        "limitations": [
            "screening_not_code_audit",
            "screening_not_security_certification",
            "screening_not_strategy_validation",
            "screening_not_profitability_evidence",
            "top_level_test_detection_can_underestimate_tests",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    relative_evidence = str(evidence_path.relative_to(project_root))
    update_master_registry(args.registry, screenings, relative_evidence)
    print(f"Screened {len(screenings)} repositories; evidence: {evidence_path}")


if __name__ == "__main__":
    main()
