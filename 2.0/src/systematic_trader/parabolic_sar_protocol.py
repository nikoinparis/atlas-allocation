"""Dependency-free reproduction of the repository's Parabolic SAR recursion."""

from __future__ import annotations

from collections.abc import Sequence


def repository_parabolic_sar(
    bars: Sequence[dict[str, float]], *, initial_af: float, step_af: float, maximum_af: float,
) -> list[dict[str, float | int | bool]]:
    if len(bars) < 2:
        raise ValueError("at least two completed bars are required")
    if not 0.0 < initial_af <= maximum_af or not 0.0 < step_af <= maximum_af:
        raise ValueError("invalid acceleration factors")
    cleaned = []
    for bar in bars:
        row = {key: float(bar[key]) for key in ("high", "low", "close")}
        tolerance = max(row.values()) * 1e-12
        if min(row.values()) <= 0.0 or row["high"] + tolerance < row["close"] or row["low"] - tolerance > row["close"]:
            raise ValueError("invalid positive high/low/close")
        cleaned.append(row)
    result: list[dict[str, float | int | bool]] = [{
        "trend": 0, "sar": 0.0, "real_sar": 0.0, "ep": 0.0, "af": 0.0, "long": False,
    }]
    trend = 1 if cleaned[1]["close"] > cleaned[0]["close"] else -1
    sar = cleaned[0]["high"] if trend > 0 else cleaned[0]["low"]
    ep = cleaned[1]["high"] if trend > 0 else cleaned[1]["low"]
    result.append({"trend": trend, "sar": sar, "real_sar": sar, "ep": ep, "af": initial_af, "long": sar < cleaned[1]["close"]})
    for index in range(2, len(cleaned)):
        prior = result[-1]
        tentative = float(prior["sar"]) + float(prior["af"]) * (float(prior["ep"]) - float(prior["sar"]))
        if int(prior["trend"]) < 0:
            sar = max(tentative, cleaned[index - 1]["high"], cleaned[index - 2]["high"])
            trend = 1 if sar < cleaned[index]["high"] else int(prior["trend"]) - 1
        else:
            sar = min(tentative, cleaned[index - 1]["low"], cleaned[index - 2]["low"])
            trend = -1 if sar > cleaned[index]["low"] else int(prior["trend"]) + 1
        if trend < 0:
            ep = cleaned[index]["low"] if trend == -1 else min(cleaned[index]["low"], float(prior["ep"]))
        else:
            ep = cleaned[index]["high"] if trend == 1 else max(cleaned[index]["high"], float(prior["ep"]))
        if abs(trend) == 1:
            real_sar = float(prior["ep"])
            af = initial_af
        else:
            real_sar = sar
            af = float(prior["af"]) if ep == float(prior["ep"]) else min(maximum_af, float(prior["af"]) + step_af)
        result.append({"trend": trend, "sar": sar, "real_sar": real_sar, "ep": ep, "af": af, "long": real_sar < cleaned[index]["close"]})
    return result
