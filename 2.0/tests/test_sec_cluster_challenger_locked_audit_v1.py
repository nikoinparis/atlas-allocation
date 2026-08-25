import pandas as pd

import scripts.run_sec_cluster_challenger_locked_audit_v1 as subject


def test_shift_targets_delays_without_backfill():
    index = pd.date_range("2026-01-02", periods=4, freq="W-FRI")
    source = {index[0]: {"a": 1.0}, index[2]: {"b": 1.0}}
    assert subject.shift_targets(source, index, 1) == {index[1]: {"a": 1.0}, index[3]: {"b": 1.0}}
    assert subject.shift_targets(source, index, 2) == {index[2]: {"a": 1.0}}


def test_compound_metrics_matches_simple_growth():
    metrics = subject.compound_metrics(pd.Series([0.10, -0.05]))
    assert abs(metrics["total_return"] - 0.045) < 1e-12
    assert metrics["weeks"] == 2


def test_rolling_outperformance_discards_incomplete_windows():
    frame = pd.DataFrame({"candidate": [0.02, 0.02, 0.02], "control": [0.01, 0.01, 0.01]})
    share, count = subject.rolling_outperformance(frame, 2)
    assert share == 1.0
    assert count == 2
