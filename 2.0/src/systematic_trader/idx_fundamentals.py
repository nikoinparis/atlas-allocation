"""Auditable normalization helpers for official IDX XBRL filing archives."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET


_CANONICAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("revenue", re.compile(r"^(net)?(sales|revenue)(andrevenue)?$", re.I)),
    ("net_income", re.compile(r"^(profitloss|netincome|profitfortheperiod)$", re.I)),
    (
        "operating_cash_flow",
        re.compile(r"^netcashflows?fromusedinoperatingactivities$", re.I),
    ),
    ("total_assets", re.compile(r"^assets$|^totalassets$", re.I)),
    ("total_liabilities", re.compile(r"^liabilities$|^totalliabilities$", re.I)),
    ("total_equity", re.compile(r"^equity$|^totalequity$", re.I)),
)


@dataclass(frozen=True)
class Context:
    context_id: str
    entity_identifier: str
    start_date: str
    end_date: str
    instant_date: str
    dimension_count: int


def canonical_concept(local_name: str) -> str:
    """Map a small predeclared set of common IDX concepts; retain everything else raw."""

    compact = re.sub(r"[^A-Za-z0-9]", "", local_name)
    for canonical, pattern in _CANONICAL_PATTERNS:
        if pattern.match(compact):
            return canonical
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _contexts(root: ET.Element) -> dict[str, Context]:
    output: dict[str, Context] = {}
    for element in root.iter():
        if _local_name(element.tag) != "context":
            continue
        context_id = element.attrib.get("id", "")
        values = {"identifier": "", "startDate": "", "endDate": "", "instant": ""}
        dimensions = 0
        for child in element.iter():
            name = _local_name(child.tag)
            if name in values:
                values[name] = (child.text or "").strip()
            if name in {"explicitMember", "typedMember"}:
                dimensions += 1
        output[context_id] = Context(
            context_id=context_id,
            entity_identifier=values["identifier"],
            start_date=values["startDate"],
            end_date=values["endDate"],
            instant_date=values["instant"],
            dimension_count=dimensions,
        )
    return output


def _units(root: ET.Element) -> dict[str, str]:
    output: dict[str, str] = {}
    for element in root.iter():
        if _local_name(element.tag) != "unit":
            continue
        measures = [
            (child.text or "").strip()
            for child in element.iter()
            if _local_name(child.tag) in {"measure", "unitNumerator", "unitDenominator"}
            and (child.text or "").strip()
        ]
        output[element.attrib.get("id", "")] = "/".join(measures)
    return output


def _xml_member(archive: zipfile.ZipFile) -> str:
    members = [name for name in archive.namelist() if name.lower().endswith((".xbrl", ".xml"))]
    preferred = [name for name in members if Path(name).name.lower() == "instance.xbrl"]
    if preferred:
        return preferred[0]
    if len(members) == 1:
        return members[0]
    raise ValueError("archive does not contain one unambiguous XBRL instance")


def normalize_xbrl_archive(
    archive_path: Path,
    *,
    ticker: str,
    source_id: str,
    source_location: str,
    retrieved_at: str,
    available_at: str,
) -> list[dict[str, object]]:
    """Extract numeric facts without discarding original concepts or contexts."""

    with zipfile.ZipFile(archive_path) as archive:
        member = _xml_member(archive)
        payload = archive.read(member)
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("unsafe XML declaration in XBRL archive")
    root = ET.fromstring(payload)
    contexts = _contexts(root)
    units = _units(root)
    rows: list[dict[str, object]] = []
    for element in root.iter():
        context_id = element.attrib.get("contextRef")
        if not context_id or context_id not in contexts:
            continue
        raw_value = (element.text or "").strip().replace(",", "")
        if not raw_value:
            continue
        try:
            Decimal(raw_value)
        except InvalidOperation:
            continue
        context = contexts[context_id]
        local_name = _local_name(element.tag)
        unit_id = element.attrib.get("unitRef", "")
        rows.append(
            {
                "ticker": ticker,
                "source_id": source_id or "SRC-UNSPECIFIED",
                "source_name": "Indonesia Stock Exchange financial statement",
                "source_location": source_location,
                "retrieved_at": retrieved_at,
                "available_at": available_at,
                "evidence_label": "fact_source_reported",
                "confidence": "high",
                "concept_namespace": element.tag.partition("}")[0].lstrip("{"),
                "original_concept": local_name,
                "canonical_concept": canonical_concept(local_name),
                "context_id": context_id,
                "entity_identifier": context.entity_identifier,
                "period_start": context.start_date,
                "period_end": context.end_date or context.instant_date,
                "period_type": "duration" if context.end_date else "instant",
                "dimension_count": context.dimension_count,
                "consolidated_candidate": context.dimension_count == 0,
                "unit_id": unit_id,
                "unit": units.get(unit_id, ""),
                "decimals": element.attrib.get("decimals", ""),
                "scale": element.attrib.get("scale", ""),
                "reported_value": raw_value,
            }
        )
    return rows
