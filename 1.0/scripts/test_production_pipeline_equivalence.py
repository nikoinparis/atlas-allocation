"""Track A equivalence tests for the formalized production wrapper."""

from __future__ import annotations

import numpy as np
import pandas as pd

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper
from generate_frontier_phase5_fragility_guard_artifact import build_modifier as legacy_build_modifier
from production_allocator import production_modifier, production_scale, run_production_allocator
from production_config import GGG_BASELINE, PRODUCTION_CANDIDATE, returns_path, weights_path


TOL = 1e-12


def _read_dated(path):
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")


def _max_abs(left: pd.DataFrame | pd.Series, right: pd.DataFrame | pd.Series) -> float:
    diff = left - right
    if isinstance(diff, pd.DataFrame):
        return float(diff.abs().to_numpy().max())
    return float(diff.abs().max())


def test_formal_wrapper_matches_legacy_modifier() -> None:
    wrapper = AllocatorCheckpointWrapper(GGG_BASELINE)
    legacy_modifier, legacy_scale = legacy_build_modifier(wrapper)
    formal_scale = production_scale(wrapper)
    assert _max_abs(formal_scale, legacy_scale) <= TOL

    legacy = wrapper.run(PRODUCTION_CANDIDATE, [legacy_modifier])
    formal = wrapper.run(PRODUCTION_CANDIDATE, [production_modifier(wrapper)])
    weight_diff = _max_abs(formal.weights, legacy.weights)
    path_cols = ["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]
    path_diff = _max_abs(formal.path.set_index("Date")[path_cols], legacy.path.set_index("Date")[path_cols])
    if weight_diff > TOL or path_diff > TOL:
        raise AssertionError(f"formal wrapper drifted from legacy modifier: weights={weight_diff}, path={path_diff}")


def test_formal_wrapper_matches_stored_production_artifact() -> None:
    formal = run_production_allocator()
    saved_weights = _read_dated(weights_path(PRODUCTION_CANDIDATE)).reindex_like(formal.weights).fillna(0.0)
    saved_returns = _read_dated(returns_path(PRODUCTION_CANDIDATE))
    weights_diff = _max_abs(formal.weights, saved_weights)
    path_cols = ["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]
    joined = formal.path.set_index("Date")[path_cols].join(saved_returns[path_cols], how="inner", rsuffix="_saved")
    diffs = {
        col: float((joined[col] - joined[f"{col}_saved"]).abs().max())
        for col in path_cols
    }
    if weights_diff > TOL or max(diffs.values()) > TOL:
        raise AssertionError(f"stored production drift: weights={weights_diff}, path={diffs}")
    if not np.isclose(joined["net_return"].corr(joined["net_return_saved"]), 1.0, atol=TOL):
        raise AssertionError("stored production net return correlation is not 1.0")


def main() -> None:
    test_formal_wrapper_matches_legacy_modifier()
    test_formal_wrapper_matches_stored_production_artifact()
    print("production pipeline equivalence tests passed")


if __name__ == "__main__":
    main()
