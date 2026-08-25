import pandas as pd

import scripts.run_sec_regime_increment_tranching_v1 as subject


def test_symmetric_tranches_ramp_and_decay():
    extra = pd.Series([0.0, 0.6, 0.6, 0.0, 0.0])
    actual = subject.smooth_increment(extra, 3, "symmetric_equal")
    assert actual.round(10).tolist() == [0.0, 0.2, 0.4, 0.4, 0.2]


def test_tranche_target_never_changes_base_without_increment():
    index = pd.date_range("2026-01-02", periods=4, freq="W-FRI")
    base = pd.DataFrame({"leader": [1.0, 0.5, 0.2, 1.0], "cash_conversion": [0.0, 0.5, 0.8, 0.0]}, index=index)
    target, deployed = subject.tranche_target(base, pd.Series(0.0, index=index), 1.0, 3, "frontloaded")
    pd.testing.assert_frame_equal(target, base)
    assert (deployed == 0).all()


def test_increment_is_capped_at_eighty_percent():
    index = pd.date_range("2026-01-02", periods=2, freq="W-FRI")
    base = pd.DataFrame({"leader": [0.5, 0.2], "cash_conversion": [0.5, 0.8]}, index=index)
    target, _ = subject.tranche_target(base, pd.Series([0.8, 0.8], index=index), 1.0, 1, "symmetric_equal")
    assert target.cash_conversion.tolist() == [0.8, 0.8]
