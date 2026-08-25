import zipfile
from pathlib import Path

from systematic_trader.idx_fundamentals import canonical_concept, normalize_xbrl_archive


def test_canonical_concept_mapping_is_narrow_and_predeclared():
    assert canonical_concept("Revenue") == "revenue"
    assert canonical_concept("ProfitLoss") == "net_income"
    assert canonical_concept("Assets") == "total_assets"
    assert canonical_concept("IssuerSpecificKPI") == ""


def test_xbrl_normalizer_preserves_source_context_and_dimensions(tmp_path: Path):
    payload = b'''<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:id="http://example.com/idx">
  <context id="D1"><entity><identifier scheme="IDX">TEST</identifier></entity><period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period></context>
  <unit id="IDR"><measure>iso4217:IDR</measure></unit>
  <id:Revenue contextRef="D1" unitRef="IDR" decimals="0">123000</id:Revenue>
</xbrl>'''
    archive = tmp_path / "instance.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("instance.xbrl", payload)
    rows = normalize_xbrl_archive(
        archive,
        ticker="TEST",
        source_id="IDX-TEST",
        source_location="https://www.idx.co.id/example",
        retrieved_at="2026-01-02T00:00:00+00:00",
        available_at="2026-01-01T09:00:00+07:00",
    )
    assert len(rows) == 1
    assert rows[0]["canonical_concept"] == "revenue"
    assert rows[0]["reported_value"] == "123000"
    assert rows[0]["period_end"] == "2025-12-31"
    assert rows[0]["available_at"] == "2026-01-01T09:00:00+07:00"
    assert rows[0]["consolidated_candidate"] is True
