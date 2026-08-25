import unittest

import scripts.acquire_sec_earnings_8k_v1 as subject


class Earnings8KAcquisitionTests(unittest.TestCase):
    def test_history_filter_keeps_only_segments_overlapping_start(self):
        payload = {"filings": {"files": [
            {"name": "old.json", "filingFrom": "2019-01-01", "filingTo": "2021-12-31"},
            {"name": "keep.json", "filingFrom": "2021-01-01", "filingTo": "2023-12-31"},
        ]}}

        self.assertEqual(subject.overlapping_history_files(payload, "2022-01-01"), ["keep.json"])

    def test_item_202_parser_deduplicates_and_uses_acceptance_time(self):
        recent = {
            "accessionNumber": ["a", "b"],
            "filingDate": ["2023-02-01", "2023-03-01"],
            "reportDate": ["2022-12-31", "2022-12-31"],
            "acceptanceDateTime": ["2023-02-01T21:01:00.000Z", "2023-03-01T20:00:00.000Z"],
            "form": ["8-K", "8-K"],
            "items": ["2.02,9.01", "1.01"],
            "primaryDocument": ["a.htm", "b.htm"],
        }
        issuer = {"cik10": "0000000001", "company_name_as_filed": "A", "sector": "technology"}

        events = subject.earnings_events(issuer, [("main", {"filings": {"recent": recent}})], "2022-01-01")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["accession"], "a")
        self.assertEqual(events[0]["availability_source"], "acceptance_datetime")


if __name__ == "__main__":
    unittest.main()
