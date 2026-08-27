#!/usr/bin/env python3
"""Platform-owned contract for materializing Kronos forecasts as research features.

This module deliberately does not import Kronos. A disposable model runner must
write forecast paths conforming to this contract; only the normalized result may
cross into Portfolio Optimizer research. Forecasts never become orders directly.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence


REQUIRED_CANDLE_FIELDS = ("timestamp", "open", "high", "low", "close")
OPTIONAL_CANDLE_FIELDS = ("volume", "amount")
CONTRACT_VERSION = "kronos_feature_contract_v1"


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an explicit timezone")
    return parsed


def validate_candles(rows: Sequence[Mapping[str, Any]], *, label: str) -> None:
    if not rows:
        raise ValueError(f"{label} must contain at least one candle")
    previous: datetime | None = None
    for index, row in enumerate(rows):
        missing = [field for field in REQUIRED_CANDLE_FIELDS if field not in row]
        if missing:
            raise ValueError(f"{label}[{index}] missing fields: {missing}")
        timestamp = _parse_timestamp(row["timestamp"])
        if previous is not None and timestamp <= previous:
            raise ValueError(f"{label} timestamps must be strictly increasing")
        previous = timestamp
        values = {}
        for field in REQUIRED_CANDLE_FIELDS[1:] + OPTIONAL_CANDLE_FIELDS:
            if field not in row:
                continue
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(f"{label}[{index}].{field} must be finite")
            values[field] = value
        if min(values["open"], values["close"]) < values["low"] - 1e-12:
            raise ValueError(f"{label}[{index}] low exceeds open/close")
        if max(values["open"], values["close"]) > values["high"] + 1e-12:
            raise ValueError(f"{label}[{index}] high is below open/close")
        if values["low"] > values["high"]:
            raise ValueError(f"{label}[{index}] low exceeds high")
        if values.get("volume", 0.0) < 0 or values.get("amount", 0.0) < 0:
            raise ValueError(f"{label}[{index}] volume/amount cannot be negative")


def materialize_forecast_features(
    history: Sequence[Mapping[str, Any]],
    forecast_paths: Sequence[Sequence[Mapping[str, Any]]],
    *,
    source_commit: str,
    model_revision: str,
    tokenizer_revision: str,
    generated_at: str,
) -> dict[str, Any]:
    """Validate forecasts and reduce them to bounded, auditable numeric features."""
    validate_candles(history, label="history")
    if not forecast_paths:
        raise ValueError("at least one forecast path is required")
    horizon = len(forecast_paths[0])
    if horizon < 1:
        raise ValueError("forecast horizon must be positive")
    history_end = _parse_timestamp(history[-1]["timestamp"])
    terminal_returns: list[float] = []
    mean_ranges: list[float] = []
    last_close = float(history[-1]["close"])
    if last_close <= 0:
        raise ValueError("last historical close must be positive")
    expected_timestamps: list[str] | None = None
    for path_index, path in enumerate(forecast_paths):
        validate_candles(path, label=f"forecast_paths[{path_index}]")
        if len(path) != horizon:
            raise ValueError("all forecast paths must have the same horizon")
        if _parse_timestamp(path[0]["timestamp"]) <= history_end:
            raise ValueError("forecast must begin strictly after history")
        timestamps = [str(row["timestamp"]) for row in path]
        if expected_timestamps is None:
            expected_timestamps = timestamps
        elif timestamps != expected_timestamps:
            raise ValueError("all forecast paths must share timestamps")
        terminal_returns.append(float(path[-1]["close"]) / last_close - 1.0)
        mean_ranges.append(statistics.fmean((float(row["high"]) - float(row["low"])) / float(row["close"]) for row in path))

    median_return = statistics.median(terminal_returns)
    dispersion = statistics.pstdev(terminal_returns) if len(terminal_returns) > 1 else 0.0
    return {
        "contract_version": CONTRACT_VERSION,
        "decision_timestamp": history[-1]["timestamp"],
        "forecast_end_timestamp": forecast_paths[0][-1]["timestamp"],
        "generated_at": generated_at,
        "lineage": {
            "source_commit": source_commit,
            "model_revision": model_revision,
            "tokenizer_revision": tokenizer_revision,
        },
        "sample_count": len(forecast_paths),
        "horizon_bars": horizon,
        "features": {
            "terminal_return_median": median_return,
            "terminal_return_dispersion": dispersion,
            "mean_forecast_range_fraction": statistics.fmean(mean_ranges),
            "positive_path_fraction": sum(value > 0 for value in terminal_returns) / len(terminal_returns),
        },
        "usage_constraints": [
            "research_feature_only",
            "lag_before_portfolio_use",
            "no_direct_order_generation",
            "independent_oos_gate_required",
        ],
    }


def smoke_fixture() -> dict[str, Any]:
    history = [
        {"timestamp": "2026-01-02T16:00:00+00:00", "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
        {"timestamp": "2026-01-05T16:00:00+00:00", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1100.0},
    ]
    paths = [
        [
            {"timestamp": "2026-01-06T16:00:00+00:00", "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0},
            {"timestamp": "2026-01-07T16:00:00+00:00", "open": 102.0, "high": 104.0, "low": 101.0, "close": 103.0},
        ],
        [
            {"timestamp": "2026-01-06T16:00:00+00:00", "open": 101.0, "high": 102.0, "low": 99.5, "close": 100.5},
            {"timestamp": "2026-01-07T16:00:00+00:00", "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5},
        ],
    ]
    return materialize_forecast_features(
        history,
        paths,
        source_commit="67b630e67f6a18c9e9be918d9b4337c960db1e9a",
        model_revision="901c26c1332695a2a8f243eb2f37243a37bea320",
        tokenizer_revision="0e0117387f39004a9016484a186a908917e22426",
        generated_at="2026-01-05T16:01:00+00:00",
    )
