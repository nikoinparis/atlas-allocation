from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from src.systematic_trader.idx80_history import idx80_workbook_from_zip, parse_idx80_workbook


def workbook_payload(count: int = 80) -> bytes:
    rows = [
        [None, "Nama Indeks", None, "IDX80"],
        [None, "Periode Efektif Konsituen", None, "1 Agustus 2025 s.d. 31 Oktober 2025"],
        [None, "No.", "Kode", "Bobot"],
    ]
    rows.extend([[None, number, f"A{number:03d}", 0.01] for number in range(1, count + 1)])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, header=False, sheet_name="Lampiran")
    return output.getvalue()


def test_parses_80_members_and_exclusive_effective_end() -> None:
    parsed = parse_idx80_workbook(workbook_payload())
    assert len(parsed["tickers"]) == 80
    assert parsed["effective_from"] == "2025-08-01"
    assert parsed["effective_to"] == "2025-11-01"


def test_rejects_incomplete_membership() -> None:
    with pytest.raises(ValueError, match="expected 80"):
        parse_idx80_workbook(workbook_payload(79))


def test_extracts_only_idx80_workbook_from_review_zip() -> None:
    output = BytesIO()
    payload = workbook_payload()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("1 IDX30.xlsx", b"not used")
        archive.writestr("3 IDX80 Mayor.xlsx", payload)
    name, extracted = idx80_workbook_from_zip(output.getvalue())
    assert name == "3 IDX80 Mayor.xlsx"
    assert extracted == payload
