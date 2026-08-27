"""Parsing and validation helpers for official IDX80 review workbooks."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
import re
from zipfile import ZipFile

import pandas as pd


_TICKER = re.compile(r"^[A-Z0-9]{4}$")
_DATE_RANGE = re.compile(
    r"(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?\s+(?:s\.d\.?|sampai(?:\s+dengan)?)\s+"
    r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)
_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "october": 10,
    "december": 12,
}


def _month(value: str) -> int:
    key = value.strip().lower()
    if key not in _MONTHS:
        raise ValueError(f"unknown month in IDX workbook: {value}")
    return _MONTHS[key]


def _effective_dates(frame: pd.DataFrame) -> tuple[date, date]:
    header = " ".join(
        str(value)
        for value in frame.head(12).to_numpy().ravel()
        if pd.notna(value)
    )
    match = _DATE_RANGE.search(header)
    if not match:
        raise ValueError("IDX80 workbook does not contain a readable effective date range")
    start_year = int(match.group(3) or match.group(6))
    start = date(start_year, _month(match.group(2)), int(match.group(1)))
    inclusive_end = date(int(match.group(6)), _month(match.group(5)), int(match.group(4)))
    return start, inclusive_end + timedelta(days=1)


def parse_idx80_workbook(payload: bytes) -> dict[str, object]:
    """Parse one official review workbook into its effective 80-name membership."""
    excel = pd.ExcelFile(BytesIO(payload))
    frame = pd.read_excel(BytesIO(payload), sheet_name=excel.sheet_names[0], header=None)
    tickers: list[str] = []
    expected_number = 1
    for row in frame.itertuples(index=False, name=None):
        for index, value in enumerate(row):
            candidate = str(value).strip().upper()
            if not _TICKER.fullmatch(candidate):
                continue
            earlier = row[:index]
            numbered = any(
                isinstance(item, (int, float))
                and pd.notna(item)
                and float(item).is_integer()
                and int(item) == expected_number
                for item in earlier
            )
            if numbered:
                tickers.append(candidate)
                expected_number += 1
                break
        if expected_number == 81:
            break
    tickers = list(dict.fromkeys(tickers))
    if len(tickers) != 80:
        raise ValueError(f"expected 80 unique IDX80 tickers, parsed {len(tickers)}")
    effective_from, effective_to = _effective_dates(frame)
    return {
        "effective_from": effective_from.isoformat(),
        "effective_to": effective_to.isoformat(),
        "tickers": tickers,
        "sheet_name": excel.sheet_names[0],
    }


def idx80_workbook_from_zip(payload: bytes) -> tuple[str, bytes]:
    """Return the IDX80 XLSX member inside an official review attachment ZIP."""
    with ZipFile(BytesIO(payload)) as archive:
        matches = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".xlsx") and "idx80" in name.lower()
        ]
        if len(matches) != 1:
            raise ValueError(f"expected one IDX80 workbook in review ZIP, found {len(matches)}")
        return matches[0], archive.read(matches[0])
