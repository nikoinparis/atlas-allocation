import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.audit_sec_terminal_membership_v1 as subject


def write_submissions(cache, cik10, rows):
    recent = {
        field: [row.get(field, "") for row in rows]
        for field in ("form", "filingDate", "reportDate", "accessionNumber", "items")
    }
    payload = {"filings": {"recent": recent}}
    (cache / f"submissions_{cik10}.gz").write_bytes(
        gzip.compress(json.dumps(payload).encode())
    )


class SECTerminalMembershipTests(unittest.TestCase):
    def test_bankruptcy_accepts_periodic_filing_covering_an_earlier_period(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(subject, "SEC_CACHE", Path(directory)):
            write_submissions(Path(directory), "0000000001", [
                {
                    "form": "8-K", "filingDate": "2025-02-19", "reportDate": "2025-02-19",
                    "accessionNumber": "bankruptcy", "items": "1.03,2.06",
                },
                {
                    "form": "25", "filingDate": "2025-04-03",
                    "accessionNumber": "delisting",
                },
                {
                    "form": "10-K", "filingDate": "2025-10-09", "reportDate": "2024-12-31",
                    "accessionNumber": "delayed-periodic",
                },
            ])

            result = subject.terminal_filing("0000000001")

            self.assertIsNotNone(result)
            self.assertEqual(result["terminal_rule"], "bankruptcy_equity_termination")
            self.assertEqual(result["accession"], "bankruptcy")

    def test_bankruptcy_rejects_a_later_economic_reporting_period(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(subject, "SEC_CACHE", Path(directory)):
            write_submissions(Path(directory), "0000000002", [
                {
                    "form": "8-K", "filingDate": "2025-02-19", "reportDate": "2025-02-19",
                    "accessionNumber": "bankruptcy", "items": "1.03,2.06",
                },
                {
                    "form": "25-NSE", "filingDate": "2025-04-03",
                    "accessionNumber": "delisting",
                },
                {
                    "form": "10-Q", "filingDate": "2025-05-15", "reportDate": "2025-03-31",
                    "accessionNumber": "later-periodic",
                },
            ])

            self.assertIsNone(subject.terminal_filing("0000000002"))

    def test_bankruptcy_without_form25_requires_two_shutdown_items(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(subject, "SEC_CACHE", Path(directory)):
            cache = Path(directory)
            write_submissions(cache, "0000000003", [{
                "form": "8-K", "filingDate": "2025-03-25", "reportDate": "2025-03-25",
                "accessionNumber": "strong-bankruptcy", "items": "1.03,2.05,2.06,3.01",
            }])
            write_submissions(cache, "0000000004", [{
                "form": "8-K", "filingDate": "2025-03-25", "reportDate": "2025-03-25",
                "accessionNumber": "weak-bankruptcy", "items": "1.03,2.05",
            }])

            strong = subject.terminal_filing("0000000003")

            self.assertIsNotNone(strong)
            self.assertEqual(strong["terminal_rule"], "bankruptcy_equity_termination")
            self.assertIsNone(subject.terminal_filing("0000000004"))

    def test_bankruptcy_accepts_a_preceding_delisting_within_one_quarter_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(subject, "SEC_CACHE", Path(directory)):
            cache = Path(directory)
            write_submissions(cache, "0000000005", [
                {
                    "form": "25-NSE", "filingDate": "2025-02-27",
                    "accessionNumber": "preceding-delisting",
                },
                {
                    "form": "8-K", "filingDate": "2025-05-14", "reportDate": "2025-05-14",
                    "accessionNumber": "bankruptcy", "items": "1.03,2.03,2.04",
                },
            ])
            write_submissions(cache, "0000000006", [
                {
                    "form": "25-NSE", "filingDate": "2025-01-01",
                    "accessionNumber": "stale-delisting",
                },
                {
                    "form": "8-K", "filingDate": "2025-05-14", "reportDate": "2025-05-14",
                    "accessionNumber": "bankruptcy", "items": "1.03,2.03,2.04",
                },
            ])

            accepted = subject.terminal_filing("0000000005")

            self.assertIsNotNone(accepted)
            self.assertEqual(accepted["terminal_rule"], "bankruptcy_equity_termination")
            self.assertIsNone(subject.terminal_filing("0000000006"))


if __name__ == "__main__":
    unittest.main()
