import pandas as pd

import scripts.run_sec_sector_aware_signal_ensemble_v1 as subject


def test_sector_cap_limits_each_sector_and_keeps_breadth():
    rows = []
    for rank in range(30):
        rows.append({"decision_at": pd.Timestamp("2026-01-01", tz="UTC"), "cik10": str(rank),
                     "company_name_as_filed": str(rank), "sector": "tech" if rank < 25 else "energy",
                     "score": 30-rank})
    chosen = subject.sector_capped_cohorts(pd.DataFrame(rows), 20, 0.75)
    assert len(chosen) == 20
    assert chosen.groupby("sector").size().max() <= 15


def test_banned_issuer_is_replaced_not_retained():
    rows = []
    for rank in range(6):
        rows.append({"decision_at": pd.Timestamp("2026-01-01", tz="UTC"), "cik10": str(rank),
                     "company_name_as_filed": str(rank), "sector": "a" if rank % 2 else "b", "score": 6-rank})
    chosen = subject.sector_capped_cohorts(pd.DataFrame(rows), 4, 1.0, {"0"})
    assert "0" not in set(chosen.cik10)
    assert len(chosen) == 4
