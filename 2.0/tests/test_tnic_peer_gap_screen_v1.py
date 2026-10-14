"""Prefix invariance for the A19 TNIC peer-gap screen (CLAUDE.md rule 2).

Perturb every price after a cut date and confirm that the signals of every decision on or before
it are unchanged, while forward returns are allowed to change. Also checks the TNIC year rule:
year Y is usable from July 1 of Y+1 only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402


def _synthetic(seed: int = 0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2011-01-03", "2025-12-31")
    n = 240
    ciks = [str(1000 + i).zfill(10) for i in range(n)]
    rets = rng.normal(0.0004, 0.02, size=(len(dates), n))
    prices = pd.DataFrame(20 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=ciks)
    dollar = pd.DataFrame(1e8, index=dates, columns=ciks)
    sic = pd.DataFrame({"cik10": ciks, "sic4": [f"{3500 + (i % 12) * 10:04d}" for i in range(n)],
                        "available": pd.Timestamp("2010-01-01")})
    rows = []
    for year in range(2009, 2024):
        for i in range(n):
            for j in rng.choice(n, size=6, replace=False):
                if i != j:
                    rows.append((year, i + 1, j + 1, float(rng.uniform(0.01, 0.2))))
    tnic = pd.DataFrame(rows, columns=["year", "gvkey1", "gvkey2", "score"])
    links = pd.DataFrame({"gvkey": range(1, n + 1), "cik10": ciks,
                          "first_date": pd.Timestamp("2000-01-01"), "last_date": pd.Timestamp("2030-01-01")})
    return prices, dollar, sic, tnic, links


def test_tnic_year_rule():
    assert a19.tnic_year_for(pd.Timestamp("2015-06-30")) == 2013
    assert a19.tnic_year_for(pd.Timestamp("2015-07-31")) == 2014


def test_signals_are_prefix_invariant():
    prices, dollar, sic, tnic, links = _synthetic()
    cut = pd.Timestamp("2017-06-30")
    rng = np.random.default_rng(1)
    base, _, _ = a19.build(prices, dollar, sic, tnic, links, rng, with_placebo=False)
    perturbed = prices.copy()
    after = perturbed.index > cut
    perturbed.loc[after] *= np.exp(np.random.default_rng(2).normal(0, 0.3, size=(after.sum(), prices.shape[1])))
    moved, _, _ = a19.build(perturbed, dollar, sic, tnic, links, rng, with_placebo=False)
    checked = changed_fwd = 0
    for a, b in zip(base, moved):
        assert a["date"] == b["date"]
        for name in list(a19.TRIALS) + ["comparator_sic3_1m"]:
            if a["date"] <= cut:
                np.testing.assert_allclose(a[name]["resid"], b[name]["resid"], equal_nan=True)
                np.testing.assert_allclose(a[name]["raw"], b[name]["raw"], equal_nan=True)
                checked += 1
                changed_fwd += not np.allclose(a[name]["fwd"], b[name]["fwd"], equal_nan=True)
    assert checked > 100
    assert changed_fwd > 0          # the perturbation really reached the future
