import gzip
import json

import pandas as pd
import pytest

from systematic_trader.sec_point_in_time import (
    SecClient,
    asof_facts,
    flatten_companyfacts,
    flatten_submissions,
    normalize_cik,
    parse_acceptance,
    quarterly_factor_inputs,
    ticker_mapping,
    validate_facts,
)


def submissions_payload():
    return {
        "cik": "1234",
        "filings": {
            "recent": {
                "accessionNumber": ["0001", "0002"],
                "filingDate": ["2024-05-01", "2024-05-10"],
                "reportDate": ["2024-03-31", "2024-03-31"],
                "acceptanceDateTime": ["2024-05-01T16:15:00.000Z", "2024-05-10T12:00:00.000Z"],
                "form": ["10-Q", "10-Q/A"],
                "primaryDocument": ["q1.htm", "q1a.htm"],
            }
        },
    }


def companyfacts_payload():
    return {
        "cik": 1234,
        "entityName": "Fixture Corp",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {"start": "2024-01-01", "end": "2024-03-31", "val": 100, "accn": "0001", "fy": 2024, "fp": "Q1", "form": "10-Q", "filed": "2024-05-01", "frame": "CY2024Q1"},
                            {"start": "2024-01-01", "end": "2024-03-31", "val": 110, "accn": "0002", "fy": 2024, "fp": "Q1", "form": "10-Q/A", "filed": "2024-05-10", "frame": "CY2024Q1"},
                            {"start": "2023-01-01", "end": "2023-03-31", "val": 80, "accn": "0001", "fy": 2023, "fp": "Q1", "form": "10-Q", "filed": "2024-05-01", "frame": "CY2023Q1"},
                        ]
                    }
                },
                "Assets": {"units": {"USD": [{"end": "2024-03-31", "val": 500, "accn": "0001", "fy": 2024, "fp": "Q1", "form": "10-Q", "filed": "2024-05-01", "frame": "CY2024Q1I"}]}},
                "Liabilities": {"units": {"USD": [{"end": "2024-03-31", "val": 200, "accn": "0001", "fy": 2024, "fp": "Q1", "form": "10-Q", "filed": "2024-05-01", "frame": "CY2024Q1I"}]}},
            }
        },
    }


METRICS = {"revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax"], "assets": ["Assets"], "liabilities": ["Liabilities"]}


def test_cik_acceptance_and_ticker_mapping():
    assert normalize_cik("1234") == "0000001234"
    assert parse_acceptance(None, "2024-05-01") == pd.Timestamp("2024-05-01T23:59:59Z")
    payload = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1234, "Fixture", "abc", "NYSE"]]}
    mapped = ticker_mapping(payload)
    assert mapped.iloc[0].to_dict() == {"ticker": "ABC", "cik10": "0000001234", "company_name": "Fixture", "exchange": "NYSE"}


def test_amendment_becomes_visible_only_after_acceptance():
    filings = flatten_submissions(submissions_payload())
    facts = flatten_companyfacts(companyfacts_payload(), filings, METRICS, ["10-Q", "10-Q/A"])
    assert validate_facts(facts)["valid"]
    before = asof_facts(facts, "2024-05-05T00:00:00Z")
    after = asof_facts(facts, "2024-05-11T00:00:00Z")
    current_before = before[(before.canonical_metric == "revenue") & (before.fiscal_year == 2024)].iloc[0]
    current_after = after[(after.canonical_metric == "revenue") & (after.fiscal_year == 2024)].iloc[0]
    assert current_before.value == 100
    assert current_after.value == 110
    assert not current_before.is_amendment
    assert current_after.is_amendment


def test_factor_inputs_use_only_strictly_available_direct_quarters():
    filings = flatten_submissions(submissions_payload())
    facts = flatten_companyfacts(companyfacts_payload(), filings, METRICS, ["10-Q", "10-Q/A"])
    panel = quarterly_factor_inputs(facts, ["2024-05-05T00:00:00Z", "2024-05-11T00:00:00Z"], {"0000001234": "FIX"})
    assert panel.iloc[0].revenue == 100
    assert panel.iloc[0].revenue__yoy_growth == pytest.approx(0.25)
    assert panel.iloc[0].liabilities_to_assets == pytest.approx(0.4)
    assert panel.iloc[1].revenue == 110
    assert panel.iloc[1].revenue__yoy_growth == pytest.approx(0.375)
    assert panel.iloc[0].revenue__available_at < panel.iloc[0].decision_time


def test_live_client_refuses_undeclared_user_agent(tmp_path, monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        SecClient.from_environment(tmp_path)


def test_sec_client_decodes_gzip_and_caches_decompressed_json(tmp_path, monkeypatch):
    payload = {"ok": True}
    compressed = gzip.compress(json.dumps(payload).encode())

    class Response:
        status = 200
        headers = {"Content-Type": "application/json", "Content-Encoding": "gzip"}

        def read(self):
            return compressed

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    client = SecClient(tmp_path, "Fixture fixture@example.com", minimum_interval=0.0)
    result, metadata = client.fetch_json("https://example.test/data", "fixture")
    assert result == payload
    assert metadata["content_encoding"] == "gzip"
    assert json.loads((tmp_path / "fixture.json").read_text()) == payload
