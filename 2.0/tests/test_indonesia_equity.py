import pandas as pd
import pytest

from systematic_trader.indonesia_equity import (
    CASH_ASSET,
    IndonesiaResearchSpec,
    build_research_target,
    normalize_idx_ticker,
    point_in_time_members,
)


def _membership(tickers, universe="IDX80", available_at="2025-12-20T00:00:00Z"):
    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "universe": universe,
                "effective_from": "2026-01-01T00:00:00Z",
                "effective_to": None,
                "available_at": available_at,
                "source_id": f"source-{universe}-{ticker}",
            }
            for ticker in tickers
        ]
    )


def _features(tickers):
    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "feature_asof_date": "2026-01-30T09:00:00Z",
                "momentum_52w_skip_4w": index / 100.0,
                "volatility_26w": 0.15 + index / 100.0,
                "median_daily_value_idr": 10_000_000_000.0,
            }
            for index, ticker in enumerate(tickers)
        ]
    )


def test_ticker_normalization_accepts_vendor_suffix_but_stores_idx_code():
    assert normalize_idx_ticker("bbca") == "BBCA"
    assert normalize_idx_ticker("bbri.jk") == "BBRI"
    with pytest.raises(ValueError):
        normalize_idx_ticker("TOO-LONG")


def test_point_in_time_membership_rejects_future_publication_and_supports_des_intersection():
    idx = _membership(["BBCA", "BBRI", "TLKM"])
    future = _membership(["ASII"], available_at="2026-02-02T00:00:00Z")
    des = _membership(["TLKM", "ASII"], universe="DES")
    membership = pd.concat([idx, future, des], ignore_index=True)
    decision = "2026-02-01T00:00:00Z"
    assert point_in_time_members(membership, decision_at=decision, universe="IDX80") == {
        "BBCA",
        "BBRI",
        "TLKM",
    }
    assert point_in_time_members(
        membership, decision_at=decision, universe="IDX80", sharia_only=True
    ) == {"TLKM"}


def test_research_target_is_capped_long_only_and_keeps_residual_cash():
    tickers = [f"A{index:03d}" for index in range(12)]
    target, diagnostics = build_research_target(
        _features(tickers),
        _membership(tickers),
        decision_at="2026-02-01T00:00:00Z",
    )
    names = target[target["ticker"] != CASH_ASSET]
    assert diagnostics["status"] == "candidate"
    assert diagnostics["execution_authorized"] is False
    assert len(names) == 12
    assert names["research_weight"].max() <= 0.10 + 1e-12
    assert (names["research_weight"] >= 0.0).all()
    assert target["research_weight"].sum() == pytest.approx(1.0)


def test_insufficient_evidence_blocks_to_all_cash():
    tickers = [f"B{index:03d}" for index in range(9)]
    target, diagnostics = build_research_target(
        _features(tickers),
        _membership(tickers),
        decision_at="2026-02-01T00:00:00Z",
    )
    assert diagnostics["status"] == "blocked_insufficient_evidence"
    assert target.to_dict("records") == [
        {"ticker": CASH_ASSET, "research_weight": 1.0, "research_score": None}
    ]


def test_future_dated_feature_is_rejected_and_execution_cannot_be_enabled():
    features = _features(["BBCA"] * 10)
    features.loc[0, "feature_asof_date"] = "2026-02-01T00:00:00Z"
    membership = _membership(["BBCA"])
    with pytest.raises(ValueError, match="strictly before"):
        build_research_target(features, membership, decision_at="2026-02-01T00:00:00Z")
    with pytest.raises(ValueError, match="research-only"):
        IndonesiaResearchSpec(allow_live_execution=True).validate()
