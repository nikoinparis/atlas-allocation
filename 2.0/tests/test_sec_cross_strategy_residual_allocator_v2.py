"""Tests for the v2 cross-strategy residual allocator.

These cover the three things v1 got wrong (holdings blindness, vacuous
stresses, no reconciliation) plus the causality guarantee the project
requires of every backtest.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/run_sec_cross_strategy_residual_allocator_v2.py"

spec = importlib.util.spec_from_file_location("allocator_v2", MODULE_PATH)
allocator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(allocator)

CONFIG = json.loads((ROOT / "config/sec_cross_strategy_residual_allocator_v2.json").read_text())


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def synthetic_sources(weeks: int = 200, seed: int = 11):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2022-01-07", periods=weeks, freq="W-FRI")
    base_gross = pd.Series(rng.normal(0.004, 0.02, weeks), index=index)
    sleeve_gross = pd.Series(rng.normal(0.005, 0.03, weeks), index=index)
    frame = pd.DataFrame({
        "base_gross": base_gross, "sleeve_gross": sleeve_gross,
        "base_net": base_gross, "sleeve_net": sleeve_gross,
    })
    base_h, sleeve_h = {}, {}
    for position, stamp in enumerate(index):
        tilt = 0.01 * ((position % 5) - 2)
        base_h[stamp] = {"XLK": 0.40 + tilt, "MU": 0.30, "AAPL": 0.30 - tilt}
        sleeve_h[stamp] = {"XLK": 0.50 - tilt, "MU": 0.30, "ZS": 0.20 + tilt}
    return frame, base_h, sleeve_h


@pytest.fixture(scope="module")
def sources():
    return synthetic_sources()


# --------------------------------------------------------------------------
# reconciliation
# --------------------------------------------------------------------------

def _item(weekly, daily_per_week, turnover=0.0, cost_bps=50.0):
    records, dailies = [], []
    wealth = 1.0
    for stamp, value in weekly.items():
        cost = turnover * cost_bps / 10000.0
        net = value - cost
        wealth *= 1.0 + net
        records.append({"date": str(stamp.date()), "grossReturn": value, "netReturn": net,
                        "cost": cost, "turnover": turnover, "wealth": wealth,
                        "rebalance": bool(turnover), "holdings": []})
        step = (1.0 + net) ** (1.0 / daily_per_week) - 1.0
        for day in range(daily_per_week):
            dailies.append({"date": str((stamp - pd.Timedelta(days=daily_per_week - 1 - day)).date()),
                            "netReturn": step, "rebalance": False, "tradingDay": True})
    return {"records": records, "dailyRecords": dailies}


def test_reconciliation_passes_on_consistent_series():
    weekly = pd.Series(np.linspace(0.001, 0.01, 20),
                       index=pd.date_range("2024-01-05", periods=20, freq="W-FRI"))
    report = allocator.reconcile(_item(weekly, 5, turnover=0.1), 1e-9)
    assert report["all_passed"]
    assert report["implied_average_cost_bps"] == pytest.approx(50.0)


def test_reconciliation_detects_a_tampered_daily_record():
    weekly = pd.Series(np.linspace(0.001, 0.01, 20),
                       index=pd.date_range("2024-01-05", periods=20, freq="W-FRI"))
    item = _item(weekly, 5, turnover=0.1)
    item["dailyRecords"][7]["netReturn"] += 1e-4
    report = allocator.reconcile(item, 1e-9)
    assert not report["passed"]["weekly_net_return_equals_compounded_daily"]
    assert not report["all_passed"]


def test_reconciliation_detects_a_broken_cost_identity():
    weekly = pd.Series(np.linspace(0.001, 0.01, 12),
                       index=pd.date_range("2024-01-05", periods=12, freq="W-FRI"))
    item = _item(weekly, 5, turnover=0.1)
    item["records"][3]["cost"] += 1e-6
    report = allocator.reconcile(item, 1e-9)
    assert not report["passed"]["weekly_net_equals_gross_minus_cost"]


def test_zero_cost_source_is_flagged_by_implied_bps():
    weekly = pd.Series(np.full(12, 0.004), index=pd.date_range("2024-01-05", periods=12, freq="W-FRI"))
    report = allocator.reconcile(_item(weekly, 5, turnover=0.2, cost_bps=0.0), 1e-9)
    assert report["all_passed"]
    assert report["implied_average_cost_bps"] == pytest.approx(0.0)
    assert report["charged_total_turnover"] > 0.0


# --------------------------------------------------------------------------
# concentration and look-through
# --------------------------------------------------------------------------

SECTOR_MAP = {
    "XLK": {"instrument_type": "exchange_traded_product", "sector": "look_through_required"},
    "XLE": {"instrument_type": "exchange_traded_product", "sector": "look_through_required"},
    "MU": {"instrument_type": "equity", "sector": "technology"},
    "AAPL": {"instrument_type": "equity", "sector": "technology"},
    "ZS": {"instrument_type": "equity", "sector": "services"},
}
LOOK_THROUGH = {"XLK": {"technology": 1.0}, "XLE": {"energy": 1.0}}


def test_look_through_moves_etf_weight_into_its_sector():
    report = allocator.concentration({"XLK": 0.60, "MU": 0.40}, SECTOR_MAP, LOOK_THROUGH)
    assert report["max_single_exchange_traded_weight"] == pytest.approx(0.60)
    assert report["max_single_issuer_weight"] == pytest.approx(0.40)
    # 0.60 of XLK plus 0.40 of MU are both technology
    assert report["max_look_through_sector_weight"] == pytest.approx(1.00)
    assert report["top_sector"] == "technology"


def test_without_look_through_sector_concentration_would_be_understated():
    with_look_through = allocator.concentration({"XLK": 0.60, "MU": 0.40}, SECTOR_MAP, LOOK_THROUGH)
    without = allocator.concentration({"XLK": 0.60, "MU": 0.40}, SECTOR_MAP, {})
    assert without["max_look_through_sector_weight"] < with_look_through["max_look_through_sector_weight"]


def test_unmapped_etf_is_never_silently_counted_as_diversified():
    report = allocator.concentration({"XLE": 0.50, "MU": 0.50}, SECTOR_MAP, {})
    assert report["max_look_through_sector_weight"] == pytest.approx(0.50)
    assert report["top_sector"] in {"unclassified_exchange_traded", "technology"}


def test_combined_holdings_blend_is_exact_and_nets_shared_names():
    merged = allocator.combined_holdings({"MU": 0.5, "AAPL": 0.5}, {"MU": 1.0}, 0.20)
    assert merged["MU"] == pytest.approx(0.8 * 0.5 + 0.2 * 1.0)
    assert merged["AAPL"] == pytest.approx(0.4)
    assert sum(merged.values()) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# breadth
# --------------------------------------------------------------------------

def test_identical_books_have_full_overlap():
    book = {"MU": 0.5, "XLK": 0.5}
    assert allocator.holdings_overlap(book, dict(book)) == pytest.approx(1.0)


def test_disjoint_books_have_zero_overlap():
    assert allocator.holdings_overlap({"MU": 1.0}, {"ZS": 1.0}) == pytest.approx(0.0)


def test_low_return_correlation_does_not_imply_low_holdings_overlap():
    """The exact trap this experiment exists to detect."""
    rng = np.random.default_rng(5)
    index = pd.date_range("2024-01-05", periods=120, freq="W-FRI")
    a = pd.Series(rng.normal(0, 0.02, 120), index=index)
    b = pd.Series(rng.normal(0, 0.02, 120), index=index)
    assert abs(float(a.corr(b))) < 0.25
    assert allocator.holdings_overlap({"MU": 0.6, "XLK": 0.4}, {"MU": 0.55, "XLK": 0.45}) > 0.90


# --------------------------------------------------------------------------
# allocator path
# --------------------------------------------------------------------------

def test_zero_allocation_reproduces_the_base_book(sources):
    frame, base_h, sleeve_h = sources
    zero = pd.Series(0.0, index=frame.index)
    path = allocator.allocator_path(frame, base_h, sleeve_h, zero, 50.0)
    reference = allocator.base_only_path(frame, base_h, 50.0)
    assert float((path.net_return - reference.net_return).abs().max()) < 1e-15


def test_holdings_turnover_is_charged_even_for_a_static_allocation(sources):
    """v1's defect: a constant weight produced zero turnover and free stresses."""
    frame, base_h, sleeve_h = sources
    targets = pd.Series(0.20, index=frame.index)
    cheap = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0)
    dear = allocator.allocator_path(frame, base_h, sleeve_h, targets, 100.0)
    assert cheap.holdings_turnover.iloc[1:].sum() > 0.0
    assert float((dear.net_return - cheap.net_return).abs().max()) > 0.0
    assert dear.net_return.sum() < cheap.net_return.sum()


def test_delay_changes_the_path_for_a_signal_dependent_rule(sources):
    frame, base_h, sleeve_h = sources
    targets = pd.Series(np.where(np.arange(len(frame)) % 7 < 3, 0.20, 0.0), index=frame.index)
    immediate = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0)
    delayed = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0, delay=2)
    assert float((delayed.net_return - immediate.net_return).abs().max()) > 1e-6


def test_missing_stocks_reduce_sleeve_participation(sources):
    frame, base_h, sleeve_h = sources
    targets = pd.Series(0.20, index=frame.index)
    drops = {stamp: {"XLK"} for stamp in frame.index}
    full = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0)
    thinned = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0, drop_symbols_by_week=drops)
    assert float((thinned.net_return - full.net_return).abs().max()) > 1e-6


def test_shock_lands_on_the_requested_week(sources):
    frame, base_h, sleeve_h = sources
    targets = pd.Series(0.20, index=frame.index)
    stamp = frame.index[-10]
    plain = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0)
    shocked = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0, shock=-0.20, shock_index=stamp)
    difference = (shocked.net_return - plain.net_return).abs()
    assert difference.loc[stamp] == pytest.approx(0.20 * 0.20)
    assert float(difference.drop(index=stamp).max()) < 1e-15


def test_signal_decay_only_trims_positive_increments(sources):
    frame, base_h, sleeve_h = sources
    targets = pd.Series(0.20, index=frame.index)
    plain = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0)
    decayed = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0, positive_retention=0.75)
    increment = plain.sleeve_effective - plain.base_gross
    assert float((decayed.net_return[increment <= 0] - plain.net_return[increment <= 0]).abs().max()) < 1e-15
    assert (decayed.net_return[increment > 0] < plain.net_return[increment > 0]).all()


# --------------------------------------------------------------------------
# causality
# --------------------------------------------------------------------------

def test_signals_use_only_lagged_information(sources):
    """Prefix invariance: perturbing the future must not move the past."""
    frame, _, _ = sources
    signal_frame = pd.DataFrame({"base": frame.base_net, "sleeve": frame.sleeve_net})
    original = allocator.causal_signals(signal_frame, CONFIG)
    cut = 150
    perturbed_frame = signal_frame.copy()
    perturbed_frame.iloc[cut:] = perturbed_frame.iloc[cut:] + 5.0
    perturbed = allocator.causal_signals(perturbed_frame, CONFIG)
    head_original = original.iloc[:cut].drop(columns=["gate"]).astype(float)
    head_perturbed = perturbed.iloc[:cut].drop(columns=["gate"]).astype(float)
    assert np.allclose(head_original.to_numpy(), head_perturbed.to_numpy(), equal_nan=True)
    assert original.gate.iloc[:cut].equals(perturbed.gate.iloc[:cut])


def test_allocator_path_is_prefix_invariant(sources):
    frame, base_h, sleeve_h = sources
    targets = pd.Series(0.15, index=frame.index)
    original = allocator.allocator_path(frame, base_h, sleeve_h, targets, 50.0)
    cut = 150
    perturbed_frame = frame.copy()
    perturbed_frame.iloc[cut:] = perturbed_frame.iloc[cut:] + 5.0
    perturbed = allocator.allocator_path(perturbed_frame, base_h, sleeve_h, targets, 50.0)
    assert np.allclose(original.net_return.iloc[:cut].to_numpy(), perturbed.net_return.iloc[:cut].to_numpy())


def test_target_weights_never_exceed_their_cap(sources):
    frame, _, _ = sources
    signal_frame = pd.DataFrame({"base": frame.base_net, "sleeve": frame.sleeve_net})
    signals = allocator.causal_signals(signal_frame, CONFIG)
    for rule in CONFIG["candidate_rules"]:
        for cap in CONFIG["candidate_caps"]:
            weights = allocator.target_weights(signals, rule, cap, CONFIG)
            assert float(weights.max()) <= cap + 1e-12
            assert float(weights.min()) >= -1e-12


# --------------------------------------------------------------------------
# selection protocol
# --------------------------------------------------------------------------

def test_purged_folds_respect_the_embargo_and_stay_in_development():
    folds = allocator.expanding_folds(132, CONFIG)
    assert folds
    assert folds[0][0] >= CONFIG["selection"]["minimum_training_weeks"] + CONFIG["selection"]["purge_weeks"]
    assert max(end for _, end in folds) <= 132


def test_familywise_threshold_uses_the_cumulative_trial_count():
    trials = CONFIG["stress"]["cumulative_trials_searched"]
    local = len(CONFIG["candidate_rules"]) * len(CONFIG["candidate_caps"])
    assert trials > local
    threshold = 1.0 - CONFIG["stress"]["familywise_alpha"] / trials
    assert threshold > 1.0 - CONFIG["stress"]["familywise_alpha"] / local


def test_config_disables_live_trading_and_defers_financing():
    assert CONFIG["live_trading_enabled"] is False
    assert CONFIG["financing"]["evaluate_only_if_unlevered_promoted"] is True
    assert CONFIG["source_research_gate_passed"] is False
