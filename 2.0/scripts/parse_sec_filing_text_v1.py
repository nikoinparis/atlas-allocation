#!/usr/bin/env python3
"""Turn acquired 10-K bodies into comparable prose.

The pilot in Step 252 established the trap: modern filings are inline XBRL, and a
naive tag-strip returns `us-gaap:AccumulatedOtherComprehensiveIncomeMember` and
context dates rather than English. A year-over-year language comparison run on
that would have been comparing tag soup, and it would still have produced a
number.

So the header and hidden blocks come out first, then scripts and styles, then
tags, then entities. What is left is normalised to lowercase alphabetic tokens,
because the comparison is about which words a filing uses, not about typography
or how a number was formatted.

Two section extracts are kept alongside the whole document, since the literature
puts the effect in the risk factors and the discussion rather than in the
boilerplate: Item 1A and Item 7. Extraction is by heading regex over the
normalised text and it is approximate; the share of filings where each section
was found is reported rather than assumed.

This parses text. It computes no signal.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/sec_filing_text_v1"

HEADER = re.compile(r"(?is)<ix:header.*?</ix:header>")
HIDDEN = re.compile(r"(?is)<ix:hidden.*?</ix:hidden>")
SCRIPTS = re.compile(r"(?is)<(script|style).*?</\1>")
TAGS = re.compile(r"(?s)<[^>]+>")
# Digits are kept here on purpose. Stripping them turns "item 1a" into "item a"
# and the section regexes can never match -- the first version of this parser did
# exactly that and reported both sections found in 0.0% of filings. Numbers are
# dropped later, at the comparison stage, where they are genuinely noise.
NONWORD = re.compile(r"[^a-z0-9\s]+")
SPACES = re.compile(r"\s+")

ITEM_1A = re.compile(r"item\s*1a\b")
ITEM_1B = re.compile(r"item\s*1b\b")
ITEM_7 = re.compile(r"item\s*7\b")
ITEM_7A = re.compile(r"item\s*7a\b")
ITEM_8 = re.compile(r"item\s*8\b")


def normalise(raw: str) -> str:
    body = HEADER.sub(" ", raw)
    body = HIDDEN.sub(" ", body)
    body = SCRIPTS.sub(" ", body)
    body = TAGS.sub(" ", body)
    body = html.unescape(body)
    body = body.lower()
    body = NONWORD.sub(" ", body)
    return SPACES.sub(" ", body).strip()


MAX_SECTION_CHARS = 200_000


def best_span(text: str, start_pattern: re.Pattern, end_pattern: re.Pattern) -> str:
    """The longest properly terminated span, not the last one.

    Taking the last occurrence looked reasonable and was wrong: "item 1a" recurs
    in cross-references and exhibit indexes near the end of a filing, so the last
    match landed in a table of contents and ran 39,025 words to the end of the
    document. A real risk-factors section is long and a table-of-contents line is
    short, so the longest properly terminated candidate is the right one.
    """
    starts = [m.start() for m in start_pattern.finditer(text)]
    ends = [m.start() for m in end_pattern.finditer(text)]
    if not starts or not ends:
        return ""
    best = ""
    for begin in starts:
        following = [e for e in ends if e > begin]
        if not following:
            continue
        span = text[begin:following[0]]
        if len(span) <= MAX_SECTION_CHARS and len(span) > len(best):
            best = span
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/sec_filing_text_v1/parsed")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    index_path = SOURCE / "index.jsonl"
    records = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        records = records[:args.limit]

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    written = skipped = missing = 0
    found_1a = found_7 = 0
    word_counts = []

    with (out / "parsed_index.jsonl").open("w", encoding="utf-8") as index:
        for record in records:
            source = SOURCE / "documents" / f"{record['accession']}.gz"
            if not source.is_file():
                missing += 1
                continue
            payload = source.read_bytes()
            if hashlib.sha256(gzip.decompress(payload)).hexdigest() != record["sha256"]:
                skipped += 1
                continue
            text = normalise(gzip.decompress(payload).decode("utf-8", "ignore"))
            risk = best_span(text, ITEM_1A, ITEM_1B)
            discussion = best_span(text, ITEM_7, ITEM_7A)
            if not discussion:
                discussion = best_span(text, ITEM_7, ITEM_8)
            found_1a += bool(risk)
            found_7 += bool(discussion)
            word_counts.append(len(text.split()))
            target = out / f"{record['accession']}.json.gz"
            target.write_bytes(gzip.compress(json.dumps({
                "accession": record["accession"], "cik10": record["cik10"],
                "filing_date": record["filing_date"], "report_date": record["report_date"],
                "prior_accession": record.get("prior_accession"),
                "full": text, "item_1a": risk, "item_7": discussion,
            }).encode("utf-8")))
            index.write(json.dumps({
                "accession": record["accession"], "cik10": record["cik10"],
                "filing_date": record["filing_date"],
                "prior_accession": record.get("prior_accession"),
                "words_full": len(text.split()), "words_item_1a": len(risk.split()),
                "words_item_7": len(discussion.split()),
            }, sort_keys=True) + "\n")
            written += 1

    manifest = {
        "experiment": "sec_filing_text_parsed_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "documents_written": written, "hash_mismatches_skipped": skipped, "missing_bodies": missing,
        "item_1a_found_share": round(found_1a / max(1, written), 4),
        "item_7_found_share": round(found_7 / max(1, written), 4),
        "median_words_full": int(sorted(word_counts)[len(word_counts) // 2]) if word_counts else 0,
        "ixbrl_header_and_hidden_removed": True,
        "computes_no_signal": True,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
