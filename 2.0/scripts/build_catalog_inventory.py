#!/usr/bin/env python3
"""Build a reproducible inventory from awesome-systematic-trading.

The script deliberately inventories catalog entries without deciding whether a
project is safe, useful, or worthy of integration. Those decisions belong to
later review and experiment stages.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


CATALOG_REPOSITORY = "https://github.com/wangzhe3224/awesome-systematic-trading"
DEFAULT_REVISION = "b4d8ec3d47813de0e87ab9151c23cb0192b9e26d"
SOURCE_FILES = ("Readme.md", "crypto_focus.md")

CSV_FIELDS = (
    "entry_id",
    "name",
    "primary_url",
    "supplemental_urls",
    "catalog_file",
    "source_line",
    "source_revision",
    "category_path",
    "entry_type",
    "review_batch",
    "language_tags",
    "description",
    "host",
    "github_repository",
    "duplicate_of",
    "catalog_flags",
    "license",
    "maintenance_status",
    "data_requirements",
    "test_status",
    "evidence_path",
    "decision",
    "rationale",
)

KNOWN_LANGUAGES = (
    "Python",
    "TypeScript",
    "JavaScript",
    "Cython",
    "C++",
    "C#",
    "Rust",
    "Java",
    "Scala",
    "Haskell",
    "Go",
    "Golang",
    "Julia",
    "R",
    "OCaml",
    "Elixir",
    "Erlang",
    "Kotlin",
    "Swift",
    "MCP",
    ".NET",
)


@dataclass
class Entry:
    entry_id: str
    name: str
    primary_url: str
    supplemental_urls: str
    catalog_file: str
    source_line: int
    source_revision: str
    category_path: str
    entry_type: str
    review_batch: str
    language_tags: str
    description: str
    host: str
    github_repository: str
    duplicate_of: str
    catalog_flags: str
    license: str = "pending_review"
    maintenance_status: str = "pending_review"
    data_requirements: str = "pending_review"
    test_status: str = "inventory"
    evidence_path: str = ""
    decision: str = "inventory"
    rationale: str = "Awaiting source, license, maintenance, and capability review"


def parse_markdown_links(text: str) -> list[tuple[str, str, int, int]]:
    """Return non-image Markdown links, including URLs containing parentheses."""
    links: list[tuple[str, str, int, int]] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("[", cursor)
        if start < 0:
            break
        if start > 0 and text[start - 1] == "!":
            cursor = start + 1
            continue
        label_end = text.find("](", start + 1)
        if label_end < 0:
            break
        label = text[start + 1 : label_end]
        url_start = label_end + 2
        depth = 1
        pos = url_start
        while pos < len(text) and depth:
            if text[pos] == "(":
                depth += 1
            elif text[pos] == ")":
                depth -= 1
            pos += 1
        if depth:
            cursor = label_end + 2
            continue
        url = text[url_start : pos - 1].strip()
        if label and url:
            links.append((label, url, start, pos))
        cursor = pos
    return links


def parse_catalog_links(text: str) -> list[tuple[str, str, int, int]]:
    """Return Markdown links and explicit angle-bracket URL links in source order."""
    links = parse_markdown_links(text)
    occupied = [(start, end) for _, _, start, end in links]
    for match in re.finditer(r"<(https?://[^>]+)>", text):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        url = match.group(1)
        links.append((url, url, match.start(), match.end()))
    return sorted(links, key=lambda item: item[2])


def normalize_heading(text: str) -> str:
    text = re.sub(r"[`*_🔥]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[len("http://") :]
    parsed = urlparse(normalized)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    if host == "github.com":
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            return f"https://github.com/{parts[0].lower()}/{parts[1].lower()}"
    return f"{parsed.scheme.lower()}://{host}{path}" if parsed.scheme else normalized


def github_slug(*urls: str) -> str:
    for url in urls:
        parsed = urlparse(url)
        if parsed.netloc.lower().removeprefix("www.") != "github.com":
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return "/".join(parts[:2])
    return ""


def extract_languages(raw: str) -> str:
    found: list[str] = []
    lower = raw.lower()
    for language in KNOWN_LANGUAGES:
        needle = language.lower()
        if needle in lower and language not in found:
            found.append("Go" if language == "Golang" else language)
    return ";".join(dict.fromkeys(found))


def classify_entry(category_path: str, url: str) -> str:
    category = category_path.lower()
    host = urlparse(url).netloc.lower()
    if "books" in category:
        return "book"
    if "courses" in category:
        return "course"
    if "tutorial" in category:
        return "tutorial"
    if "blogs" in category or "quant shops" in category:
        return "industry_resource"
    if "research" in category:
        return "research_resource"
    if "data source" in category or "databases" in category:
        return "data_or_storage"
    if "broker" in category:
        return "broker_or_venue_adapter"
    if "alpha" in category or "stock picking" in category or "arbitrage" in category:
        return "strategy_or_signal"
    if "risk" in category or "optimization" in category or "pricing" in category:
        return "analytics_or_portfolio_library"
    if "visualization" in category:
        return "visualization"
    if "message queues" in category or "computation" in category:
        return "infrastructure"
    if "backtest" in category or "trading systems" in category or "crypto + defi" in category:
        return "trading_or_backtest_system"
    if host in {"amazon.com", "amazon.co.uk"}:
        return "book"
    return "library_platform_or_resource"


def assign_review_batch(category_path: str, entry_type: str) -> str:
    category = category_path.lower()
    if "crypto" in category or "prediction market" in category or "defi" in category:
        return "07_crypto_defi_and_prediction_markets"
    if "ai powered" in category or "machine learning" in category:
        return "06_ai_ml_and_automation"
    if entry_type == "trading_or_backtest_system":
        return "01_backtest_execution_and_simulation"
    if entry_type == "data_or_storage":
        return "02_data_and_storage"
    if entry_type == "analytics_or_portfolio_library":
        return "03_portfolio_risk_and_analytics"
    if entry_type == "strategy_or_signal":
        return "04_signals_and_strategies"
    if entry_type == "broker_or_venue_adapter":
        return "05_broker_and_venue_interfaces"
    if entry_type in {"infrastructure", "visualization", "library_platform_or_resource"}:
        return "08_infrastructure_libraries_and_visualization"
    return "09_education_research_and_industry_resources"


def extract_flags(raw: str, description: str, url: str, duplicate: bool) -> str:
    flags: list[str] = []
    lower = raw.lower()
    if duplicate:
        flags.append("duplicate_listing")
    if "no activity" in lower:
        flags.append("catalog_marks_no_activity")
    if "live trading" in lower:
        flags.append("claims_live_trading")
    if description.rstrip().endswith("?") or re.search(r"(?:^|\s)-?\s*\?\s*$", description):
        flags.append("description_unclear")
    if "ftx" in lower or "ftx" in url.lower():
        flags.append("mentions_ftx")
    if "guarantee" in lower or "win rate" in lower or "accuracy" in lower:
        flags.append("performance_claim_requires_verification")
    if not url.startswith(("https://", "http://")):
        flags.append("relative_or_non_http_link")
    return ";".join(flags)


def clean_description(raw: str, link_spans: list[tuple[str, str, int, int]]) -> str:
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", raw)
    cleaned = re.sub(r"^\s*-\s*", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = cleaned.replace("| -", "—").replace("|-", "—")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" |-")
    return cleaned


def parse_catalog(path: Path, revision: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    headings: dict[int, str] = {}
    list_groups: dict[int, str] = {}
    collecting = path.name == "crypto_focus.md"

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw_line)
        if heading_match:
            level = len(heading_match.group(1))
            heading = normalize_heading(heading_match.group(2))
            headings[level] = heading
            for deeper in tuple(key for key in headings if key > level):
                del headings[deeper]
            if path.name == "Readme.md" and level == 2 and heading != "Star History":
                collecting = True
            continue

        if not collecting or not re.match(r"^\s*-\s+", raw_line):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        for deeper in tuple(key for key in list_groups if key >= indent):
            del list_groups[deeper]
        links = parse_catalog_links(raw_line)
        if not links:
            group_name = normalize_heading(re.sub(r"^\s*-\s*", "", raw_line))
            if group_name and "more is coming" not in group_name.lower():
                list_groups[indent] = group_name
            continue
        primary_label, primary_url, primary_start, _ = links[0]
        if primary_label == primary_url:
            prefix = re.sub(r"^\s*-\s*", "", raw_line[:primary_start]).strip(" :")
            if prefix:
                primary_label = prefix
        heading_path = [headings[level] for level in sorted(headings) if level >= 1]
        group_path = [list_groups[level] for level in sorted(list_groups) if level < indent]
        category = " > ".join(heading_path + group_path)
        description = clean_description(raw_line, links)
        all_urls = [link[1] for link in links]
        entries.append(
            {
                "name": re.sub(r"^[*\s]+", "", primary_label).strip(),
                "primary_url": primary_url,
                "supplemental_urls": ";".join(link[1] for link in links[1:]),
                "catalog_file": path.name,
                "source_line": line_number,
                "source_revision": revision,
                "category_path": category,
                "entry_type": classify_entry(category, primary_url),
                "review_batch": assign_review_batch(
                    category, classify_entry(category, primary_url)
                ),
                "language_tags": extract_languages(raw_line),
                "description": description,
                "host": urlparse(primary_url).netloc.lower().removeprefix("www."),
                "github_repository": github_slug(*all_urls),
                "raw_line": raw_line,
            }
        )
        list_groups[indent] = re.sub(r"^[*\s]+", "", primary_label).strip()
    return entries


def audit_catalog(path: Path) -> dict[str, object]:
    collecting = path.name == "crypto_focus.md"
    linked_bullets = 0
    unlinked_bullets: list[dict[str, object]] = []
    supplemental_links = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw_line)
        if heading_match:
            heading = normalize_heading(heading_match.group(2))
            if path.name == "Readme.md" and len(heading_match.group(1)) == 2 and heading != "Star History":
                collecting = True
            continue
        if not collecting or not re.match(r"^\s*-\s+", raw_line):
            continue
        links = parse_catalog_links(raw_line)
        if links:
            linked_bullets += 1
            supplemental_links += max(0, len(links) - 1)
        else:
            unlinked_bullets.append(
                {
                    "source_line": line_number,
                    "text": re.sub(r"^\s*-\s*", "", raw_line).strip(),
                }
            )
    return {
        "scoped_bullet_count": linked_bullets + len(unlinked_bullets),
        "linked_bullet_count": linked_bullets,
        "supplemental_link_count": supplemental_links,
        "unlinked_bullet_count": len(unlinked_bullets),
        "unlinked_bullets": unlinked_bullets,
    }


def build_entries(source_dir: Path, revision: str) -> list[Entry]:
    raw_entries: list[dict[str, object]] = []
    for filename in SOURCE_FILES:
        raw_entries.extend(parse_catalog(source_dir / filename, revision))

    first_by_url: dict[str, str] = {}
    result: list[Entry] = []
    for index, raw in enumerate(raw_entries, 1):
        entry_id = f"ast-{index:04d}"
        normalized = normalize_url(str(raw["primary_url"]))
        duplicate_of = first_by_url.get(normalized, "")
        if not duplicate_of:
            first_by_url[normalized] = entry_id
        result.append(
            Entry(
                entry_id=entry_id,
                name=str(raw["name"]),
                primary_url=str(raw["primary_url"]),
                supplemental_urls=str(raw["supplemental_urls"]),
                catalog_file=str(raw["catalog_file"]),
                source_line=int(raw["source_line"]),
                source_revision=str(raw["source_revision"]),
                category_path=str(raw["category_path"]),
                entry_type=str(raw["entry_type"]),
                review_batch=str(raw["review_batch"]),
                language_tags=str(raw["language_tags"]),
                description=str(raw["description"]),
                host=str(raw["host"]),
                github_repository=str(raw["github_repository"]),
                duplicate_of=duplicate_of,
                catalog_flags=extract_flags(
                    str(raw["raw_line"]),
                    str(raw["description"]),
                    str(raw["primary_url"]),
                    bool(duplicate_of),
                ),
            )
        )
    return result


def download_sources(destination: Path, revision: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for filename in SOURCE_FILES:
        url = (
            "https://raw.githubusercontent.com/"
            f"wangzhe3224/awesome-systematic-trading/{revision}/{filename}"
        )
        with urllib.request.urlopen(url, timeout=30) as response:
            (destination / filename).write_bytes(response.read())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_outputs(entries: list[Entry], output_dir: Path, source_dir: Path, revision: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output_dir / "source_snapshots" / revision
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for filename in SOURCE_FILES:
        shutil.copyfile(source_dir / filename, snapshot_dir / filename)

    with (output_dir / "registry.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(asdict(entry))

    categories = Counter(entry.category_path for entry in entries)
    entry_types = Counter(entry.entry_type for entry in entries)
    review_batches = Counter(entry.review_batch for entry in entries)
    hosts = Counter(entry.host or "relative_or_unknown" for entry in entries)
    coverage_audit = {filename: audit_catalog(source_dir / filename) for filename in SOURCE_FILES}
    for filename in SOURCE_FILES:
        parsed_count = sum(entry.catalog_file == filename for entry in entries)
        linked_count = int(coverage_audit[filename]["linked_bullet_count"])
        if parsed_count != linked_count:
            raise RuntimeError(
                f"Coverage mismatch for {filename}: parsed {parsed_count}, expected {linked_count}"
            )
    summary = {
        "catalog_repository": CATALOG_REPOSITORY,
        "source_revision": revision,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries),
        "unique_primary_url_count": len(entries) - sum(bool(entry.duplicate_of) for entry in entries),
        "duplicate_listing_count": sum(bool(entry.duplicate_of) for entry in entries),
        "github_primary_entry_count": sum(bool(entry.github_repository) for entry in entries),
        "entries_by_file": dict(Counter(entry.catalog_file for entry in entries)),
        "entries_by_type": dict(sorted(entry_types.items())),
        "entries_by_review_batch": dict(sorted(review_batches.items())),
        "entries_by_category": dict(sorted(categories.items())),
        "top_hosts": dict(hosts.most_common(20)),
        "flag_counts": dict(
            sorted(
                Counter(
                    flag
                    for entry in entries
                    for flag in entry.catalog_flags.split(";")
                    if flag
                ).items()
            )
        ),
        "source_files": {
            filename: {
                "sha256": file_sha256(source_dir / filename),
                "snapshot": str(Path("source_snapshots") / revision / filename),
            }
            for filename in SOURCE_FILES
        },
        "coverage_audit": coverage_audit,
    }
    (output_dir / "inventory_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# Catalog Review Batches",
        "",
        f"Pinned source revision: `{revision}`",
        "",
        "Every catalog listing is assigned to exactly one first-pass review batch. "
        "Batch order reflects platform dependencies, not a decision to exclude later batches.",
        "",
    ]
    for batch, count in sorted(review_batches.items()):
        lines.append(f"- `{batch}`: {count} listings")
    lines.extend(
        [
            "",
            "Within each batch, duplicate listings remain in the registry but share source-review "
            "evidence with their canonical entry. Commercial pages, books, blogs, and unavailable "
            "projects receive documented reviews even when no software can be executed.",
            "",
        ]
    )
    (output_dir / "review_batches.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "research_registry",
    )
    args = parser.parse_args()

    if args.source_dir:
        source_dir = args.source_dir.resolve()
    else:
        source_dir = args.output_dir / "downloaded_sources" / args.revision
        download_sources(source_dir, args.revision)

    missing = [filename for filename in SOURCE_FILES if not (source_dir / filename).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {', '.join(missing)}")

    entries = build_entries(source_dir, args.revision)
    if not entries:
        raise SystemExit("No catalog entries were parsed")
    write_outputs(entries, args.output_dir, source_dir, args.revision)
    print(f"Wrote {len(entries)} entries to {args.output_dir / 'registry.csv'}")


if __name__ == "__main__":
    main()
