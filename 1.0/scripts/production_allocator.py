"""Formal production component for the Track A allocator.

The live production candidate is wrapper-based, not a fully native allocator.
It starts from the saved GGG final ETF weights and applies one canonical
post-processor at the ``offense_budget`` checkpoint:

    * Phase 1 R2A state-quality offense scale:
      ``1 + 0.08 * clip(r2a, -1, 1)`` outside stressed_panic.
    * Phase 4 fragility guard:
      when ``leadership_quality_composite > 0.50``, cap the offense boost at
      1.0 rather than allowing extra offense.
    * stressed_panic is forced to 1.0, preserving the base defense behavior.

This module is the production source of truth for the wrapper logic.  The older
artifact-generation script remains as historical packaging, but future Track A
reproduction should import from here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, CheckpointModifier, WrapperRunResult
from path1_path3_research_utils import DATA, GGG
from production_config import (
    DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
    PRODUCTION_CANDIDATE,
    rel,
)


PHASE1_R2A_PATH = DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
PHASE4_LEADERSHIP_PATH = DATA / "research" / "frontier_phase4" / "leadership_signals.csv"


def read_dated_csv(path: Path) -> pd.DataFrame:
    """Read a date-indexed CSV used by the production post-processor."""

    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    date_col = "date" if "date" in df.columns else "Date"
    if date_col not in df.columns:
        raise ValueError(f"{rel(path)} lacks date/Date column")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def production_scale(wrapper: AllocatorCheckpointWrapper) -> pd.Series:
    """Return the canonical Frontier Phase 5 fragility-guard offense scale."""

    ph1 = read_dated_csv(PHASE1_R2A_PATH)
    ph4 = read_dated_csv(PHASE4_LEADERSHIP_PATH)
    states = wrapper.states["market_state"].astype(str)
    r2_col = "r2a_quality" if "r2a_quality" in ph1.columns else "r2a"
    if r2_col not in ph1.columns:
        raise ValueError(f"{rel(PHASE1_R2A_PATH)} lacks r2a_quality/r2a")
    if "leadership_quality_composite" not in ph4.columns:
        raise ValueError(f"{rel(PHASE4_LEADERSHIP_PATH)} lacks leadership_quality_composite")

    q = pd.to_numeric(ph1[r2_col], errors="coerce").reindex(states.index).fillna(0.0).clip(-1.0, 1.0)
    leadership = (
        pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce")
        .reindex(states.index)
        .ffill()
        .fillna(0.0)
    )
    scale = pd.Series(1.0, index=states.index, dtype=float)
    not_stressed_panic = states.ne("stressed_panic")
    scale.loc[not_stressed_panic] = 1.0 + 0.08 * q.loc[not_stressed_panic]
    crowded = leadership.gt(0.50)
    scale.loc[crowded & not_stressed_panic] = scale.loc[crowded & not_stressed_panic].clip(upper=1.0)
    scale.loc[states.eq("stressed_panic")] = 1.0
    if not (scale.loc[states.eq("stressed_panic")] == 1.0).all():
        raise ValueError("stressed_panic scale changed")
    return scale


def production_modifier(wrapper: AllocatorCheckpointWrapper) -> CheckpointModifier:
    """Create the canonical production post-processor modifier."""

    scale = production_scale(wrapper)

    def _fn(_wrapper: AllocatorCheckpointWrapper, _checkpoint: str) -> pd.Series:
        return scale.reindex(_wrapper.index).fillna(1.0)

    return CheckpointModifier(
        name="frontier_phase5_fragility_guard",
        checkpoint="offense_budget",
        function=_fn,
    )


def run_production_allocator(
    *,
    candidate_name: str = PRODUCTION_CANDIDATE,
    cost_bps: float = DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
) -> WrapperRunResult:
    """Run the canonical wrapper-based production allocator."""

    wrapper = AllocatorCheckpointWrapper(GGG, cost_bps=cost_bps)
    return wrapper.run(candidate_name, [production_modifier(wrapper)])


def production_pipeline_description() -> str:
    """Return a concise human-readable production pipeline description."""

    return (
        "Wrapper-based production pipeline: saved GGG ETF weights -> "
        "Frontier Phase 5 offense-budget post-processor -> canonical "
        "one-way-turnover/10 bps cost path."
    )
