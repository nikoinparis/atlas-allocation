import pandas as pd

import scripts.run_sec_signal_neighborhood_ensemble_v1 as subject


def test_mix_targets_preserves_weight_and_union():
    date = pd.Timestamp("2026-01-02")
    components = {"a": {date: {"x": 0.5, "y": 0.5}}, "b": {date: {"y": 0.5, "z": 0.5}}}
    mixed = subject.mix_targets(components, {"a": 0.5, "b": 0.5})[date]
    assert mixed == {"x": 0.25, "y": 0.5, "z": 0.25}
    assert abs(sum(mixed.values()) - 1.0) < 1e-12


def test_endpoint_share_uses_only_completed_trailing_windows():
    index = pd.date_range("2025-01-03", periods=60, freq="W-FRI")
    candidate = pd.DataFrame({"net_return": [0.02] * 60}, index=index)
    control = pd.DataFrame({"net_return": [0.01] * 60}, index=index)
    assert subject.endpoint_share(candidate, control, [0, 1, 2]) == 1.0
