"""Platform-owned behavioral probe executed against pinned FlashAlpha source."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

from fillsim import Config, InMemoryChainProvider, Leg, Quote, Spread, simulate_fill, simulate_fills


expiry = date(2026, 5, 15)
bar_time = datetime(2026, 4, 15, 10, 1)
spread = Spread(
    short=Leg(strike=440, bid=1.30, ask=1.30),
    long=Leg(strike=435, bid=0.86, ask=0.88),
    limit_credit=0.40,
    width=5.0,
    expiry=expiry,
)


def check(name: str, expected: object, actual: object, *, critical: bool = True) -> dict[str, object]:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual, "critical": critical}


checks: list[dict[str, object]] = []

valid = simulate_fill(
    bar_time,
    {(expiry, 440.0): (1.34, 1.34), (expiry, 435.0): (0.90, 0.90)},
    [spread],
)
checks.append(check("valid_cross_fills_at_posted_limit", 0.40, None if valid.fill is None else valid.fill.fill_price))

no_cross = simulate_fill(
    bar_time,
    {(expiry, 440.0): (1.20, 1.22), (expiry, 435.0): (0.86, 0.88)},
    [spread],
)
checks.append(check("non_cross_does_not_fill", False, no_cross.fill is not None))

wide = simulate_fill(
    bar_time,
    {(expiry, 440.0): (1.32, 3.00), (expiry, 435.0): (0.86, 0.88)},
    [spread],
)
checks.append(check("wide_quote_is_rejected", False, wide.fill is not None))

crossed = simulate_fill(
    bar_time,
    {(expiry, 440.0): (1.32, 1.20), (expiry, 435.0): (0.86, 0.88)},
    [spread],
)
checks.append(check("crossed_quote_is_rejected", False, crossed.fill is not None))

nan_quote = simulate_fill(
    bar_time,
    {(expiry, 440.0): (1.30, 1.30), (expiry, 435.0): (math.nan, 0.88)},
    [spread],
)
nan_fill = nan_quote.fill is not None
nan_mid_is_finite = nan_quote.fill is None or math.isfinite(nan_quote.fill.mid_at_fill)
checks.append(check("nonfinite_quote_is_rejected", False, nan_fill))
checks.append(check("fill_diagnostics_are_finite", True, nan_mid_is_finite))

posted = datetime(2026, 4, 15, 10, 0)
provider = InMemoryChainProvider(
    quotes=[
        Quote(posted, expiry, 440.0, "PUT", 1.32, 1.32),
        Quote(posted, expiry, 435.0, "PUT", 0.90, 0.90),
        Quote(posted + timedelta(minutes=1), expiry, 440.0, "PUT", 1.34, 1.34),
        Quote(posted + timedelta(minutes=1), expiry, 435.0, "PUT", 0.90, 0.90),
    ]
)
delayed = simulate_fills(posted, [spread], provider, Config(fill_max_wait_bars=2))
checks.append(check("default_wrapper_prevents_same_bar_fill", posted + timedelta(minutes=1), None if delayed.fill is None else delayed.fill.fill_ts))

critical_pass = all(item["passed"] for item in checks if item["critical"])
result = {
    "adapter": "flashalpha_fill_simulator",
    "checks": checks,
    "critical_pass": critical_pass,
    "capabilities": {
        "quote_quality_filter": True,
        "same_bar_lookahead_guard_in_loop_wrapper": True,
        "partial_fills": False,
        "commissions_and_fees": False,
        "cash_and_position_accounting": False,
        "order_rejection_lifecycle": False,
    },
    "decision": "conditional_component_candidate_with_platform_quote_gate" if not critical_pass else "behavioral_candidate",
}
print(json.dumps(result, sort_keys=True, default=str))
