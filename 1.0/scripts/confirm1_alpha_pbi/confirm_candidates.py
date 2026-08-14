"""Locked candidate definitions for the alpha/PBI confirmation sprint.

Everything here is pre-registered in
docs/research/2026-07-07_moonshot1_discovery_sprint_report.md (section 10)
and in the sprint instruction. No parameter in this file may be changed
mid-sprint. Candidate functions are imported from the already-verified
moonshot/frontier2 modules rather than re-implemented, so the confirmation
tests exactly the code that produced the discovery numbers.

    Candidate A: alpha=0.24 R2A scale (leadership cap intact, SP untouched)
    Candidate B: Candidate A + PBI-latched (2of3 -> 1.15, 3of3 -> 1.30,
                 latch 13w, deep-DD <= -10%, stressed_panic only, never <1.0)
    Candidate C: alpha=0.16 + same PBI-latched rule (control)
    Comparison arm (reference only): Frontier-2 down-only vol throttle
                 (26w, clip 0.85-1.00, 4-week update) stacked on the pin.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for sub in ("", "moonshot1_discovery", "frontier2_overlays"):
    p = str(SCRIPTS_DIR / sub) if sub else str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)

from path1_path3_research_utils import DATA  # noqa: E402

from moonshot_features import build_feature_panel, panic_improvement_composite  # noqa: E402
from moonshot_models import r2a_scale_with_alpha  # noqa: E402
from overlay_signals import realized_vol_scalar  # noqa: E402

ALPHA_A = 0.24
ALPHA_C = 0.16
PBI_MULT_PARTIAL = 1.15
PBI_MULT_FULL = 1.30
PBI_COUNT_GATE = 2
PBI_LATCH_WEEKS = 13
PBI_DEEP_DD = -0.10
THROTTLE_CFG = dict(vol_window=26, clip_low=0.85, clip_high=1.00, update_every=4)


def load_r2a_leadership(index: pd.Index) -> tuple[pd.Series, pd.Series]:
    ph1 = pd.read_csv(DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv")
    ph1["date"] = pd.to_datetime(ph1["date"])
    ph1 = ph1.set_index("date")
    ph4 = pd.read_csv(DATA / "research" / "frontier_phase4" / "leadership_signals.csv")
    ph4["date"] = pd.to_datetime(ph4["date"])
    ph4 = ph4.set_index("date")
    r2a = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(index).fillna(0.0)
    lead = pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce").reindex(index).ffill().fillna(0.0)
    return r2a, lead


def alpha_scale(index: pd.Index, states: pd.Series, alpha: float) -> pd.Series:
    r2a, lead = load_r2a_leadership(index)
    return r2a_scale_with_alpha(r2a, lead, states, alpha)


def pbi_latched_multiplier(index: pd.Index, states: pd.Series, warnings: list[str]) -> pd.Series:
    """The locked PBI-latched rule (identical to moonshot F3 primary)."""

    feats = build_feature_panel(index, warnings)
    pbi = panic_improvement_composite(feats)
    latched = feats["market_drawdown"].rolling(PBI_LATCH_WEEKS, min_periods=1).min() <= PBI_DEEP_DD
    count = pbi["confirm_count"]
    sp = states.astype(str).eq("stressed_panic")
    mult = pd.Series(1.0, index=index)
    mult[sp & latched & (count >= PBI_COUNT_GATE) & (count < 3)] = PBI_MULT_PARTIAL
    mult[sp & latched & (count >= 3)] = PBI_MULT_FULL
    return mult


def throttle_multiplier(index: pd.Index, states: pd.Series, pin_net_returns: pd.Series) -> pd.Series:
    """Frontier-2 down-only vol throttle (comparison arm only)."""

    scalar = realized_vol_scalar(pin_net_returns, index, **THROTTLE_CFG)
    scalar[states.astype(str).eq("stressed_panic")] = 1.0
    return scalar
