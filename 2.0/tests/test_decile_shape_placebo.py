"""S22: the sign-flip placebo must hold its size where the fixed 0.5 bar does not."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import decile_shape as ds  # noqa: E402


def _ladders(rng, ic_mean, ic_sd, decisions, names=300):
    rows = []
    for _ in range(decisions):
        ic = np.clip(ic_mean + ic_sd * rng.standard_normal(), -0.9, 0.9)
        z = rng.standard_normal(names)
        r = ic * z + np.sqrt(1 - ic ** 2) * rng.standard_t(4, names) / np.sqrt(2)
        q = np.argsort(np.argsort(z)) * 10 // names
        rows.append(np.bincount(q, weights=r, minlength=10) / np.bincount(q, minlength=10))
    return np.array(rows)


def test_size_under_time_varying_null():
    rng = np.random.default_rng(7)
    fixed, calibrated, runs = 0, 0, 150
    for k in range(runs):
        res = ds.placebo_test(_ladders(rng, 0.0, 0.10, 14), draws=300, seed=k)
        fixed += ds.clears(res["monotonicity"], res["monotonicity_middle_8"])
        calibrated += ds.clears_calibrated(res)
    assert calibrated / runs <= 0.10          # nominal 5%, allow simulation noise
    assert fixed / runs > calibrated / runs   # the old bar is looser than the calibrated one


def test_power_on_real_signal():
    rng = np.random.default_rng(11)
    hits = sum(ds.clears_calibrated(ds.placebo_test(_ladders(rng, 0.08, 0.05, 39), draws=300, seed=k))
               for k in range(40))
    assert hits / 40 >= 0.7


def test_flat_ladder_is_not_a_pass():
    res = ds.placebo_test(np.zeros((20, 10)), draws=100)
    assert not ds.clears_calibrated(res)
