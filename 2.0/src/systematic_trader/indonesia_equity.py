"""Research-only Indonesian equity universe and starter portfolio protocol.

This module deliberately has no broker, order, or live-execution integration.
It materializes a point-in-time research universe and a provisional portfolio
target that must remain inside the historical/synthetic research boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

import pandas as pd

from .cross_sectional_factors import percentile_ranks


CASH_ASSET = "CASH_IDR"
RESEARCH_ONLY_NOTICE = (
    "RESEARCH ONLY — not investment advice, not a recommendation, and not approved "
    "for live or paper brokerage execution."
)
SUPPORTED_UNIVERSES = ("IDX80", "LQ45", "IDX30")
SHARIA_UNIVERSE = "DES"
_TICKER_RE = re.compile(r"^[A-Z0-9]{4}$")


@dataclass(frozen=True)
class IndonesiaResearchSpec:
    """Pinned rules for the provisional Indonesia liquid-equity sleeve."""

    universe: str = "IDX80"
    sharia_only: bool = False
    top_n: int = 12
    minimum_eligible_names: int = 10
    maximum_name_weight: float = 0.10
    minimum_median_daily_value_idr: float = 5_000_000_000.0
    momentum_weight: float = 0.70
    low_volatility_weight: float = 0.30
    research_only: bool = True
    allow_live_execution: bool = False

    def validate(self) -> None:
        if self.universe not in SUPPORTED_UNIVERSES:
            raise ValueError(f"unsupported Indonesian research universe: {self.universe}")
        if not self.research_only or self.allow_live_execution:
            raise ValueError("Indonesia sleeve is locked to research-only with no live execution")
        if self.top_n <= 0 or self.minimum_eligible_names <= 0:
            raise ValueError("top_n and minimum_eligible_names must be positive")
        if self.minimum_eligible_names > self.top_n:
            raise ValueError("minimum_eligible_names cannot exceed top_n")
        if not 0.0 < self.maximum_name_weight <= 1.0:
            raise ValueError("maximum_name_weight must be in (0, 1]")
        if self.minimum_median_daily_value_idr < 0.0:
            raise ValueError("minimum liquidity cannot be negative")
        if not math.isclose(
            self.momentum_weight + self.low_volatility_weight, 1.0, abs_tol=1e-12
        ):
            raise ValueError("signal weights must sum to one")


def normalize_idx_ticker(value: object) -> str:
    """Normalize an IDX code without treating a vendor suffix as identity."""
    ticker = str(value).strip().upper()
    if ticker.endswith(".JK"):
        ticker = ticker[:-3]
    if not _TICKER_RE.fullmatch(ticker):
        raise ValueError(f"invalid four-character IDX ticker: {value!r}")
    return ticker


def normalize_membership(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate effective-dated index or DES membership observations."""
    required = {"ticker", "universe", "effective_from", "available_at", "source_id"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"membership data missing columns: {missing}")
    result = frame.copy()
    result["ticker"] = result["ticker"].map(normalize_idx_ticker)
    result["universe"] = result["universe"].astype(str).str.strip().str.upper()
    allowed = {*SUPPORTED_UNIVERSES, SHARIA_UNIVERSE}
    unknown = sorted(set(result["universe"]) - allowed)
    if unknown:
        raise ValueError(f"unsupported membership universes: {unknown}")
    result["effective_from"] = pd.to_datetime(result["effective_from"], utc=True, errors="coerce")
    result["available_at"] = pd.to_datetime(result["available_at"], utc=True, errors="coerce")
    if "effective_to" not in result:
        result["effective_to"] = pd.NaT
    result["effective_to"] = pd.to_datetime(result["effective_to"], utc=True, errors="coerce")
    if result[["effective_from", "available_at"]].isna().any().any():
        raise ValueError("membership effective_from and available_at must be valid timestamps")
    invalid_intervals = result["effective_to"].notna() & (
        result["effective_to"] <= result["effective_from"]
    )
    if invalid_intervals.any():
        raise ValueError("membership effective_to must be after effective_from")
    return result.sort_values(
        ["universe", "ticker", "available_at", "effective_from", "source_id"]
    ).reset_index(drop=True)


def point_in_time_members(
    membership: pd.DataFrame,
    *,
    decision_at: object,
    universe: str,
    sharia_only: bool = False,
) -> set[str]:
    """Return only memberships published strictly before the decision instant."""
    normalized = normalize_membership(membership)
    decision = pd.Timestamp(decision_at)
    decision = decision.tz_localize("UTC") if decision.tzinfo is None else decision.tz_convert("UTC")
    universe = str(universe).upper()
    if universe not in SUPPORTED_UNIVERSES:
        raise ValueError(f"unsupported Indonesian research universe: {universe}")

    def active_members(name: str) -> set[str]:
        rows = normalized[
            (normalized["universe"] == name)
            & (normalized["available_at"] < decision)
            & (normalized["effective_from"] <= decision)
            & (normalized["effective_to"].isna() | (normalized["effective_to"] > decision))
        ]
        return set(rows["ticker"])

    members = active_members(universe)
    return members & active_members(SHARIA_UNIVERSE) if sharia_only else members


def _capped_inverse_volatility(
    volatility: dict[str, float], *, target_weight: float, maximum_weight: float
) -> dict[str, float]:
    """Allocate up to target_weight while preserving a hard per-name cap."""
    if not volatility or target_weight <= 0.0:
        return {}
    raw = {ticker: 1.0 / value for ticker, value in volatility.items()}
    active = dict(raw)
    result = {ticker: 0.0 for ticker in raw}
    remaining = min(target_weight, len(raw) * maximum_weight)
    while active and remaining > 1e-15:
        scale = remaining / sum(active.values())
        capped = [ticker for ticker, value in active.items() if value * scale > maximum_weight]
        if not capped:
            for ticker, value in active.items():
                result[ticker] = value * scale
            remaining = 0.0
            break
        for ticker in capped:
            result[ticker] = maximum_weight
            remaining -= maximum_weight
            del active[ticker]
    return result


def build_research_target(
    features: pd.DataFrame,
    membership: pd.DataFrame,
    *,
    decision_at: object,
    spec: IndonesiaResearchSpec | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build one provisional target from already-computed point-in-time features.

    Required feature columns are ``ticker``, ``feature_asof_date``,
    ``momentum_52w_skip_4w``, ``volatility_26w``, and
    ``median_daily_value_idr``. Feature timestamps must be strictly earlier than
    the decision instant. Invalid or future-dated rows are rejected rather than
    silently used.
    """
    spec = spec or IndonesiaResearchSpec()
    spec.validate()
    required = {
        "ticker",
        "feature_asof_date",
        "momentum_52w_skip_4w",
        "volatility_26w",
        "median_daily_value_idr",
    }
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"feature data missing columns: {missing}")

    decision = pd.Timestamp(decision_at)
    decision = decision.tz_localize("UTC") if decision.tzinfo is None else decision.tz_convert("UTC")
    allowed = point_in_time_members(
        membership,
        decision_at=decision,
        universe=spec.universe,
        sharia_only=spec.sharia_only,
    )
    rows = features.copy()
    rows["ticker"] = rows["ticker"].map(normalize_idx_ticker)
    rows["feature_asof_date"] = pd.to_datetime(rows["feature_asof_date"], utc=True, errors="coerce")
    if rows["feature_asof_date"].isna().any():
        raise ValueError("feature_asof_date must contain valid timestamps")
    if (rows["feature_asof_date"] >= decision).any():
        raise ValueError("all feature rows must be known strictly before the decision instant")
    for column in ("momentum_52w_skip_4w", "volatility_26w", "median_daily_value_idr"):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    finite = rows[["momentum_52w_skip_4w", "volatility_26w", "median_daily_value_idr"]].apply(
        lambda column: column.map(lambda value: pd.notna(value) and math.isfinite(float(value)))
    ).all(axis=1)
    rows = rows[
        rows["ticker"].isin(allowed)
        & finite
        & (rows["volatility_26w"] > 0.0)
        & (rows["median_daily_value_idr"] >= spec.minimum_median_daily_value_idr)
    ].copy()
    rows = rows.sort_values(["feature_asof_date", "ticker"]).drop_duplicates("ticker", keep="last")

    diagnostics: dict[str, object] = {
        "status": "candidate",
        "notice": RESEARCH_ONLY_NOTICE,
        "decision_at": decision.isoformat(),
        "universe": spec.universe,
        "sharia_only": spec.sharia_only,
        "point_in_time_members": len(allowed),
        "eligible_feature_rows": len(rows),
        "selected_names": 0,
        "cash_weight": 1.0,
        "execution_authorized": False,
    }
    if len(rows) < spec.minimum_eligible_names:
        diagnostics["status"] = "blocked_insufficient_evidence"
        target = pd.DataFrame(
            [{"ticker": CASH_ASSET, "research_weight": 1.0, "research_score": pd.NA}]
        )
        return target, diagnostics

    momentum = percentile_ranks(dict(zip(rows["ticker"], rows["momentum_52w_skip_4w"])))
    low_volatility = percentile_ranks(
        dict(zip(rows["ticker"], -rows["volatility_26w"]))
    )
    rows["research_score"] = rows["ticker"].map(
        lambda ticker: spec.momentum_weight * momentum[ticker]
        + spec.low_volatility_weight * low_volatility[ticker]
    )
    selected = rows.sort_values(["research_score", "ticker"], ascending=[False, True]).head(
        spec.top_n
    ).copy()
    risk_budget = min(1.0, len(selected) / spec.top_n)
    weights = _capped_inverse_volatility(
        dict(zip(selected["ticker"], selected["volatility_26w"])),
        target_weight=risk_budget,
        maximum_weight=spec.maximum_name_weight,
    )
    selected["research_weight"] = selected["ticker"].map(weights)
    cash_weight = max(0.0, 1.0 - float(selected["research_weight"].sum()))
    target = selected[
        [
            "ticker",
            "research_weight",
            "research_score",
            "momentum_52w_skip_4w",
            "volatility_26w",
            "median_daily_value_idr",
            "feature_asof_date",
        ]
    ].reset_index(drop=True)
    cash_index = len(target)
    target.loc[cash_index, "ticker"] = CASH_ASSET
    target.loc[cash_index, "research_weight"] = cash_weight
    diagnostics.update(
        {
            "selected_names": len(selected),
            "cash_weight": cash_weight,
            "maximum_observed_name_weight": max(weights.values(), default=0.0),
        }
    )
    return target, diagnostics
