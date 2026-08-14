"""Strict adoption boundary for recorded TradingView screener responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RecordedScreenerRow:
    symbol: str
    values: Mapping[str, Any]
    missing_columns: tuple[str, ...]
    update_mode: str


@dataclass(frozen=True)
class RecordedScreenerSnapshot:
    captured_at: datetime
    rows: tuple[RecordedScreenerRow, ...]
    point_in_time_eligible: bool
    rejection_reason: str


def _utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("captured_at_utc must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("captured_at_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def parse_recorded_screener_fixture(fixture: Mapping[str, Any]) -> RecordedScreenerSnapshot:
    captured_at = _utc_timestamp(fixture.get("captured_at_utc"))
    request = fixture.get("request")
    response = fixture.get("response")
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        raise ValueError("fixture must contain request and response objects")
    columns = request.get("columns")
    data = response.get("data")
    if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)) or not all(isinstance(item, str) for item in columns):
        raise ValueError("request columns must be a string list")
    if len(set(columns)) != len(columns):
        raise ValueError("request columns must be unique")
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise ValueError("response data must be a list")

    rows = []
    seen = set()
    for item in data:
        if not isinstance(item, Mapping) or not isinstance(item.get("s"), str) or not isinstance(item.get("d"), list):
            raise ValueError("malformed response row")
        symbol = item["s"]
        values = item["d"]
        if symbol in seen:
            raise ValueError(f"duplicate symbol: {symbol}")
        if len(values) != len(columns):
            raise ValueError(f"column/value length mismatch for {symbol}")
        seen.add(symbol)
        mapped = dict(zip(columns, values))
        for name, value in mapped.items():
            if isinstance(value, float) and not isfinite(value):
                raise ValueError(f"non-finite value for {symbol}:{name}")
        update_mode = mapped.get("update_mode")
        if not isinstance(update_mode, str) or not update_mode:
            raise ValueError(f"missing update mode for {symbol}")
        rows.append(RecordedScreenerRow(
            symbol=symbol,
            values=mapped,
            missing_columns=tuple(name for name, value in mapped.items() if value is None),
            update_mode=update_mode,
        ))

    # A capture timestamp documents when we received the payload; it is not the
    # market event/availability timestamp needed for point-in-time backtesting.
    return RecordedScreenerSnapshot(
        captured_at=captured_at,
        rows=tuple(rows),
        point_in_time_eligible=False,
        rejection_reason="vendor_response_has_no_per_row_observation_or_availability_timestamp",
    )
