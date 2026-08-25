import pandas as pd

import scripts.run_sec_breadth_controller_cap_persistence_v1 as subject


def test_persistent_boolean_requires_entry_and_exit_confirmation():
    raw = pd.Series([False, True, False, True, True, True, False, True, False, False])
    actual = subject.persistent_boolean(raw, enter=2, exit_=2)
    assert actual.tolist() == [False, False, False, False, True, True, True, True, True, False]


def test_persistent_target_uses_only_generic_states():
    index = pd.date_range("2026-01-02", periods=5, freq="W-FRI")
    base = pd.DataFrame({"leader": [1, .5, .5, .5, 1], "cash_conversion": [0, .5, .5, .5, 0]}, index=index)
    breadth = pd.Series([False, True, True, False, False], index=index)
    target, states = subject.persistent_target(base, breadth, 2, 2, 1, 1)
    assert target.cash_conversion.tolist() == [0, .5, .8, .8, 0]
    assert list(states.columns) == [
        "raw_breadth_state", "persistent_breadth_state", "raw_overlay_state", "persistent_overlay_state"
    ]
