"""Canonical production configuration for the promoted allocator.

This module is deliberately small and boring.  Track A hardening needs one
place for names, dates, paths, and reporting directories so production scripts
do not keep re-declaring stale pins.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PORTFOLIO_DIR = DATA / "05_layer3_portfolio_construction"
PUBLIC_DIR = ROOT / "public"
DOCS_RESEARCH_DIR = ROOT / "docs" / "research"
TRACK_A_DIR = DATA / "research" / "track_a_production_hardening"

REGISTRY_PATH = PORTFOLIO_DIR / "production_candidate_registry.json"
SUMMARY_PATH = PORTFOLIO_DIR / "production_candidate_summary.csv"
STATE_SUMMARY_PATH = PORTFOLIO_DIR / "production_candidate_state_summary.csv"
EXPOSURE_SUMMARY_PATH = PORTFOLIO_DIR / "production_candidate_exposure_summary.csv"

PRODUCTION_CANDIDATE = "improved_frontier_phase5_fragility_guard"
ROLLBACK_PIN = "improved_phase2b_regime_confidence_boost"
OFFICIAL_SHADOW_PIN = "improved_phase2b_combo_abc"
GGG_BASELINE = "improved_phaseggg_confirmed_only_robust_offense"

WEEKS_PER_YEAR = 52
OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")
DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER = 10.0
CANONICAL_VOL_DDOF = 1


def rel(path: Path) -> str:
    """Return a repo-relative path for reports."""

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def ensure_track_a_dirs() -> None:
    """Create Track A output directories."""

    TRACK_A_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_RESEARCH_DIR.mkdir(parents=True, exist_ok=True)


def load_registry() -> dict[str, Any]:
    """Load the production candidate registry."""

    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(REGISTRY_PATH)
    return json.loads(REGISTRY_PATH.read_text())


def require_official_production_pin() -> dict[str, Any]:
    """Load registry and verify it points at the Track A production pin."""

    reg = load_registry()
    current = reg.get("current_production_pin")
    candidate = reg.get("production_candidate")
    if current != PRODUCTION_CANDIDATE:
        raise RuntimeError(f"current_production_pin is {current!r}, expected {PRODUCTION_CANDIDATE!r}")
    if candidate != PRODUCTION_CANDIDATE:
        raise RuntimeError(f"production_candidate is {candidate!r}, expected {PRODUCTION_CANDIDATE!r}")
    return reg


def returns_path(name: str) -> Path:
    """Path to a saved portfolio return series."""

    return PORTFOLIO_DIR / f"portfolio_version_returns_{name}.csv"


def weights_path(name: str) -> Path:
    """Path to saved final ETF weights."""

    return PORTFOLIO_DIR / f"portfolio_version_weights_{name}.csv"


def sleeve_weights_path(name: str) -> Path:
    """Path to saved sleeve weights or sleeve-weight proxy."""

    return PORTFOLIO_DIR / f"portfolio_version_sleeve_weights_{name}.csv"


def markdown_table(df: pd.DataFrame, *, max_rows: int | None = None) -> str:
    """Render a small markdown table without optional tabulate dependency."""

    if df is None or df.empty:
        return "_No rows._"
    view = df.head(max_rows).copy() if max_rows else df.copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{float(x):.10g}")
        else:
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else str(x))
    headers = [str(c) for c in view.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in view.columns) + " |")
    return "\n".join(lines)
