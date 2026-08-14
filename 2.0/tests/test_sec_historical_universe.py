import pandas as pd

from systematic_trader.sec_historical_universe import build_membership, extract_trading_symbols, normalize_submissions, sic_sector


GROUPS = {"technology": [[7370, 7379]], "energy": [[1311, 1311]]}


def test_sic_sector_uses_declared_ranges():
    assert sic_sector(7372, GROUPS) == "technology"
    assert sic_sector("1311", GROUPS) == "energy"
    assert sic_sector(2834, GROUPS) is None


def test_extract_trading_symbols_requires_explicit_xbrl_tag():
    inline = '<ix:nonNumeric contextRef="x" name="dei:TradingSymbol"><span>TWTR</span></ix:nonNumeric>'
    instance = '<dei:EntityTradingSymbol contextRef="x">DATA.A</dei:EntityTradingSymbol>'
    assert extract_trading_symbols(inline) == ["TWTR"]
    assert extract_trading_symbols(instance) == ["DATA.A"]
    assert extract_trading_symbols("Trading symbol might be GUESSED") == []
    assert extract_trading_symbols('<dei:TradingSymbol>0001556898</dei:TradingSymbol>') == []


def test_membership_uses_strict_acceptance_time_and_keeps_former_cik():
    raw = pd.DataFrame([
        {"adsh": "old", "cik": 1, "name": "OLD NAME", "sic": 7372, "form": "10-K", "filed": 20230301, "accepted": 20230301120000, "afs": "1-LAF", "period": 20221231, "fy": 2022, "fp": "FY", "source_quarter": "2023Q1"},
        {"adsh": "new", "cik": 1, "name": "NEW NAME", "sic": 7372, "form": "10-Q", "filed": 20230501, "accepted": 20230501120000, "afs": "1-LAF", "period": 20230331, "fy": 2023, "fp": "Q1", "source_quarter": "2023Q2"},
        {"adsh": "small", "cik": 2, "name": "SMALL", "sic": 1311, "form": "10-K", "filed": 20230301, "accepted": 20230301120000, "afs": "5-SML", "period": 20221231, "fy": 2022, "fp": "FY", "source_quarter": "2023Q1"},
    ])
    filings = normalize_submissions(raw, GROUPS, ["10-K", "10-Q"], ["1-LAF", "2-ACC"])
    membership = build_membership(filings, ["2023-04-01T00:00:00Z", "2023-07-01T00:00:00Z"])
    assert membership["adsh"].tolist() == ["old", "new"]
    assert set(membership["cik10"]) == {"0000000001"}
    assert membership["company_name_as_filed"].tolist() == ["OLD NAME", "NEW NAME"]


def test_membership_expires_stale_filers_instead_of_forward_filling_forever():
    raw = pd.DataFrame([
        {"adsh": "dead", "cik": 9, "name": "DEAD CO", "sic": 1311, "form": "10-K", "filed": 20200101, "accepted": 20200101120000, "afs": "2-ACC", "period": 20191231, "fy": 2019, "fp": "FY", "source_quarter": "2020Q1"},
    ])
    filings = normalize_submissions(raw, GROUPS, ["10-K"], ["2-ACC"])
    membership = build_membership(filings, ["2020-04-01T00:00:00Z", "2021-07-01T00:00:00Z"], staleness_days=450)
    assert membership["decision_at"].dt.year.tolist() == [2020]
