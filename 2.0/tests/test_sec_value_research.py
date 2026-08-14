import unittest

from src.systematic_trader.sec_value_research import latest_period_fact_as_of


class SecValueResearchTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"facts": {"us-gaap": {"StockholdersEquity": {"units": {"USD": [
            {"end": "2025-12-31", "filed": "2026-02-01", "form": "10-K", "accn": "base", "val": 100},
            {"end": "2025-12-31", "filed": "2026-03-01", "form": "10-K/A", "accn": "amended", "val": 80},
            {"end": "2026-03-31", "filed": "2026-05-01", "form": "10-Q", "accn": "future", "val": 90},
        ]}}}}}

    def test_future_and_amended_facts_do_not_leak_backward(self):
        before = latest_period_fact_as_of(
            self.payload, taxonomy="us-gaap", concept="StockholdersEquity", unit="USD",
            decision_date="2026-02-15",
        )
        after = latest_period_fact_as_of(
            self.payload, taxonomy="us-gaap", concept="StockholdersEquity", unit="USD",
            decision_date="2026-03-10",
        )
        self.assertEqual("base", before["accn"])
        self.assertEqual("amended", after["accn"])

    def test_execution_lag_is_enforced(self):
        unavailable = latest_period_fact_as_of(
            self.payload, taxonomy="us-gaap", concept="StockholdersEquity", unit="USD",
            decision_date="2026-02-02", execution_lag_days=2,
        )
        self.assertIsNone(unavailable)


if __name__ == "__main__":
    unittest.main()
