"""No-write allocator checkpoint wrapper for deployment research.

This module exposes safe research insertion points around the reconstructed GGG
portfolio path. It reads production/candidate artifacts and allocator
checkpoints, but writes only caller-requested research outputs. With no
modifier applied, the wrapper must reproduce exact GGG because it uses saved
final ETF weights plus the exact weekly price-derived forward return and
one-way turnover convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Union

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    CHECKPOINTS,
    DATA,
    DOCS,
    DEFENSE,
    GGG,
    OFFENSE,
    PRODUCTION_COST_BPS,
    exposure_summary,
    load_checkpoint,
    load_next_week_returns,
    load_returns,
    load_states,
    load_weights,
    metrics_from_path,
    normalize_to_cash,
    production_portfolio_path,
    rel,
)


STABILIZATION_OUT = DATA / "research" / "stabilization"

CHECKPOINT_STAGES = {
    "raw_sleeve_targets": "raw_hrp_sleeve_weights",
    "regime_multipliers": "post_state_tilt_sleeve_weights",
    "offense_budget": "post_layer3_expression_sleeve_weights",
    "defense_budget": "post_layer3_expression_sleeve_weights",
    "cash_bil_budget": "post_overlay_pre_lookthrough_sleeve_weights",
    "transition_rerisk_smoothing": "post_overlay_pre_lookthrough_sleeve_weights",
    "derisk_smoothing": "post_overlay_pre_lookthrough_sleeve_weights",
    "volatility_risk_overlay": "post_overlay_pre_lookthrough_sleeve_weights",
    "final_etf_lookthrough_weights": "final_etf_weights",
    "cost_turnover_calculation": "final_etf_weights",
}

SAFE_CHECKPOINTS = {
    "regime_multipliers",
    "offense_budget",
    "cash_bil_budget",
    "transition_rerisk_smoothing",
    "derisk_smoothing",
    "volatility_risk_overlay",
    "final_etf_lookthrough_weights",
}

DANGEROUS_CHECKPOINTS = {
    "raw_sleeve_targets",
    "defense_budget",
    "cost_turnover_calculation",
}

ModifierFunction = Callable[["AllocatorCheckpointWrapper", str], Union[pd.Series, pd.DataFrame]]


@dataclass(frozen=True)
class CheckpointModifier:
    """A bounded research modifier attached to one checkpoint."""

    name: str
    checkpoint: str
    function: ModifierFunction


@dataclass
class WrapperRunResult:
    """Research output from a wrapper run."""

    variant: str
    weights: pd.DataFrame
    path: pd.DataFrame
    metrics: dict[str, float]
    log: pd.DataFrame


def _as_multiplier(value: pd.Series | pd.DataFrame | float, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.DataFrame):
        if "modifier" in value.columns:
            series = value["modifier"]
        else:
            numeric = value.select_dtypes(include=[np.number])
            series = numeric.mean(axis=1) if not numeric.empty else pd.Series(1.0, index=index)
    elif isinstance(value, pd.Series):
        series = value
    else:
        series = pd.Series(float(value), index=index)
    return pd.to_numeric(series.reindex(index), errors="coerce").ffill().fillna(1.0).clip(0.50, 1.50)


def _scale_columns(weights: pd.DataFrame, columns: list[str], multiplier: pd.Series) -> pd.DataFrame:
    out = weights.copy()
    cols = [c for c in columns if c in out.columns]
    if cols:
        out[cols] = out[cols].mul(multiplier.reindex(out.index).ffill().fillna(1.0), axis=0)
    return normalize_to_cash(out)


def apply_checkpoint_multiplier(weights: pd.DataFrame, checkpoint: str, modifier: pd.Series | pd.DataFrame | float) -> pd.DataFrame:
    """Apply a bounded multiplier at a research checkpoint proxy.

    The production allocator is not edited. Early checkpoint modifications are
    represented as conservative final-weight proxy transformations so future
    experiments can be compared with exact GGG plumbing before a true allocator
    hook is built.
    """

    mult = _as_multiplier(modifier, weights.index)
    if checkpoint in {"regime_multipliers", "volatility_risk_overlay", "final_etf_lookthrough_weights"}:
        risky_cols = [c for c in weights.columns if c != "BIL"]
        return _scale_columns(weights, risky_cols, mult)
    if checkpoint in {"offense_budget", "transition_rerisk_smoothing"}:
        return _scale_columns(weights, [c for c in weights.columns if c in OFFENSE], mult)
    if checkpoint == "derisk_smoothing":
        risky_cols = [c for c in weights.columns if c != "BIL"]
        return _scale_columns(weights, risky_cols, mult)
    if checkpoint == "defense_budget":
        return _scale_columns(weights, [c for c in weights.columns if c in DEFENSE and c != "BIL"], mult)
    if checkpoint == "cash_bil_budget":
        out = weights.copy()
        risky_cols = [c for c in out.columns if c != "BIL"]
        # Multiplier above 1 means more cash; below 1 means less cash.
        risky_multiplier = (2.0 - mult).clip(0.0, 1.10)
        if risky_cols:
            out[risky_cols] = out[risky_cols].mul(risky_multiplier, axis=0)
        return normalize_to_cash(out)
    if checkpoint == "raw_sleeve_targets":
        risky_cols = [c for c in weights.columns if c != "BIL"]
        return _scale_columns(weights, risky_cols, mult)
    if checkpoint == "cost_turnover_calculation":
        # Cost plumbing is intentionally not modified by this wrapper.
        return weights.copy()
    raise ValueError(f"Unknown checkpoint: {checkpoint}")


class AllocatorCheckpointWrapper:
    """Research-only checkpoint wrapper around the exact GGG reconstruction."""

    def __init__(self, candidate: str = GGG, cost_bps: float = PRODUCTION_COST_BPS) -> None:
        self.candidate = candidate
        self.cost_bps = cost_bps
        self.warnings: list[str] = []
        self.final_weights = load_weights(candidate, self.warnings)
        self.saved_returns = load_returns(candidate, self.warnings)
        self.next_week_returns = load_next_week_returns(self.warnings)
        self.states = load_states(self.warnings)
        self.checkpoints = {
            key: load_checkpoint(candidate, stage, self.warnings)
            for key, stage in CHECKPOINT_STAGES.items()
        }
        if self.final_weights.empty:
            raise ValueError(f"Missing final weights for {candidate}.")
        if self.next_week_returns.empty:
            raise ValueError("Missing weekly price-derived forward returns.")

    @property
    def index(self) -> pd.Index:
        return self.final_weights.index

    def checkpoint_summary(self) -> pd.DataFrame:
        rows = []
        for checkpoint, stage in CHECKPOINT_STAGES.items():
            panel = self.checkpoints.get(checkpoint, pd.DataFrame())
            rows.append(
                {
                    "checkpoint": checkpoint,
                    "source_stage": stage,
                    "available": not panel.empty,
                    "rows": len(panel),
                    "cols": len(panel.columns) if not panel.empty else 0,
                    "safe_for_frontier_research": checkpoint in SAFE_CHECKPOINTS,
                    "dangerous_without_allocator_hook": checkpoint in DANGEROUS_CHECKPOINTS,
                    "source_path": rel(CHECKPOINTS / f"{self.candidate}__{stage}.csv"),
                }
            )
        return pd.DataFrame(rows)

    def run(self, variant: str = "no_modifier", modifiers: list[CheckpointModifier] | None = None) -> WrapperRunResult:
        weights = self.final_weights.copy()
        log_rows: list[dict[str, object]] = []
        for modifier in modifiers or []:
            if modifier.checkpoint not in CHECKPOINT_STAGES:
                raise ValueError(f"Unknown modifier checkpoint {modifier.checkpoint}")
            before = weights.copy()
            payload = modifier.function(self, modifier.checkpoint)
            weights = apply_checkpoint_multiplier(weights, modifier.checkpoint, payload)
            delta = (weights - before).abs().sum(axis=1)
            mult = _as_multiplier(payload, weights.index)
            log_rows.append(
                {
                    "variant": variant,
                    "modifier": modifier.name,
                    "checkpoint": modifier.checkpoint,
                    "modifier_min": float(mult.min()),
                    "modifier_mean": float(mult.mean()),
                    "modifier_max": float(mult.max()),
                    "avg_abs_weight_change": float(delta.mean()),
                    "max_abs_weight_change": float(delta.max()),
                }
            )
        path = production_portfolio_path(weights, self.next_week_returns, self.cost_bps)
        metrics = metrics_from_path(path)
        metrics.update(exposure_summary(weights))
        return WrapperRunResult(variant=variant, weights=weights, path=path, metrics=metrics, log=pd.DataFrame(log_rows))

    def compare_to_saved(self, path: pd.DataFrame | None = None) -> dict[str, float]:
        if path is None:
            path = self.run().path
        if self.saved_returns.empty or path.empty:
            return {}
        joined = path.set_index("Date").join(
            self.saved_returns[["gross_return", "net_return", "turnover", "cost"]],
            how="inner",
            rsuffix="_saved",
        )
        out: dict[str, float] = {"weeks_compared": float(len(joined))}
        for col in ["gross_return", "net_return", "turnover", "cost"]:
            err = joined[col] - joined[f"{col}_saved"]
            out[f"{col}_mean_abs_error"] = float(err.abs().mean())
            out[f"{col}_max_abs_error"] = float(err.abs().max())
        out["net_return_corr_vs_saved"] = float(joined["net_return"].corr(joined["net_return_saved"]))
        return out

    def save_result(self, result: WrapperRunResult, output_dir: Path = STABILIZATION_OUT) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        result.path.to_csv(output_dir / f"{result.variant}_returns.csv", index=False)
        result.weights.reset_index().rename(columns={"index": "Date"}).to_csv(output_dir / f"{result.variant}_weights.csv", index=False)
        if not result.log.empty:
            result.log.to_csv(output_dir / f"{result.variant}_modifier_log.csv", index=False)


def exact_rebuild_tolerance_ok(compare: dict[str, float], tolerance: float = 1e-12) -> bool:
    """Return True when no-modifier wrapper matches saved GGG to tolerance."""

    return (
        compare.get("net_return_max_abs_error", np.inf) <= tolerance
        and compare.get("turnover_max_abs_error", np.inf) <= tolerance
        and compare.get("cost_max_abs_error", np.inf) <= tolerance
        and abs(compare.get("net_return_corr_vs_saved", 0.0) - 1.0) <= tolerance
    )


def docs_dir() -> Path:
    DOCS.mkdir(parents=True, exist_ok=True)
    return DOCS
