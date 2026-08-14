import numpy as np
import pandas as pd

from systematic_trader.return_first_search import advanced_signal_families, build_advanced_sources, delay_weights


def prices(rows: int = 180) -> pd.DataFrame:
    index = pd.date_range("2020-01-03", periods=rows, freq="W-FRI")
    rng = np.random.default_rng(66)
    returns = rng.normal(0.002, 0.025, size=(rows, 5))
    return pd.DataFrame(100.0 * np.exp(np.cumsum(returns, axis=0)), index=index, columns=["SPY", "QQQ", "XLK", "XLE", "BIL"])


def test_advanced_signals_are_prefix_invariant():
    full_prices = prices()
    cutoff = full_prices.index[-20]
    full = advanced_signal_families(full_prices)
    prefix = advanced_signal_families(full_prices.loc[:cutoff])
    assert set(full) == set(prefix)
    for name in full:
        pd.testing.assert_frame_equal(full[name].loc[:cutoff], prefix[name])


def test_all_advanced_sources_are_fully_invested():
    frame = prices()
    sources = build_advanced_sources(
        frame,
        families=["trend_quality_52", "rank_consensus"],
        universe=["SPY", "QQQ", "XLK", "XLE"],
        top_ns=[1, 2],
        methods=["equal_weight", "score_inverse_volatility"],
        minimum_score=0.0,
    )
    assert len(sources) == 8
    for weights in sources.values():
        np.testing.assert_allclose(weights.sum(axis=1), 1.0, atol=1e-12)
        assert (weights >= -1e-12).all().all()


def test_delay_weights_uses_only_prior_allocations():
    frame = prices(12)
    weights = pd.DataFrame(0.0, index=frame.index, columns=["XLK", "BIL"])
    weights["XLK"] = np.arange(len(weights)) / len(weights)
    weights["BIL"] = 1.0 - weights["XLK"]
    delayed = delay_weights(weights, 2)
    pd.testing.assert_frame_equal(delayed.iloc[2:], weights.iloc[:-2].set_axis(delayed.index[2:]))
    assert (delayed.iloc[:2]["BIL"] == 1.0).all()
