"""Replay pinned FlashAlpha against its checked-in real SPY option-chain fixture."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from fillsim import Config, Leg, Spread, simulate_fills
from tests.fixtures.real_data_loader import FIXTURE, load_real_dataset


real = load_real_dataset()
posted = datetime(2024, 6, 3, 10, 0)
limits = [0.88, 0.90, 0.92, 0.94, 0.96, 0.98, 1.00, 1.02, 1.03, 1.05, 1.10]


def candidate(limit):
    return Spread(
        short=Leg(strike=525.0, bid=0.0, ask=0.0),
        long=Leg(strike=520.0, bid=0.0, ask=0.0),
        limit_credit=limit,
        width=5.0,
        expiry=real.expiry,
    )


def scenario(config, assumed_entry_fee):
    records = []
    for limit in limits:
        result = simulate_fills(posted, [candidate(limit)], real.provider(), config)
        fill = result.fill
        records.append({
            "limit_credit": limit,
            "filled": fill is not None,
            "fill_ts": None if fill is None else str(fill.fill_ts),
            "edge_captured": None if fill is None else fill.edge_captured,
            "near_misses": result.near_misses,
            "bars_waited": result.bars_waited,
            "net_entry_credit_usd_after_assumed_fee": None if fill is None else fill.fill_price * 100.0 - assumed_entry_fee,
        })
    return {
        "configuration": {
            "fill_epsilon": config.fill_epsilon,
            "fill_max_rel_spread": config.fill_max_rel_spread,
            "min_edge_floor": config.min_edge_floor,
            "start_offset_bars": config.start_offset_bars,
            "assumed_two_leg_entry_fee_usd_per_spread": assumed_entry_fee,
        },
        "filled": sum(record["filled"] for record in records),
        "tested": len(records),
        "records": records,
    }


base = scenario(Config(), 1.30)
stress = scenario(Config(fill_epsilon=0.05, fill_max_rel_spread=0.25, min_edge_floor=0.0), 3.00)
strict_not_more_fills = stress["filled"] <= base["filled"]
stress_net_not_higher = all(
    stressed["net_entry_credit_usd_after_assumed_fee"] <= normal["net_entry_credit_usd_after_assumed_fee"]
    for normal, stressed in zip(base["records"], stress["records"])
    if normal["filled"] and stressed["filled"]
)
checks = [
    {"name": "stricter_execution_assumptions_do_not_increase_fill_count", "passed": strict_not_more_fills, "critical": True},
    {"name": "higher_assumed_fee_does_not_increase_net_entry_credit", "passed": stress_net_not_higher, "critical": True},
    {"name": "default_next_bar_guard_is_active", "passed": Config().start_offset_bars >= 1, "critical": True},
]
print(json.dumps({
    "adapter": "flashalpha_fill_simulator",
    "fixture": str(FIXTURE),
    "fixture_sha256": hashlib.sha256(Path(FIXTURE).read_bytes()).hexdigest(),
    "fixture_source_claim": "repository fixture says historical.flashalpha.com",
    "symbol": real.symbol,
    "trade_date": str(real.trade_date),
    "bars": len(real.bars),
    "base": base,
    "stress": stress,
    "checks": checks,
    "critical_pass": all(check["passed"] for check in checks if check["critical"]),
    "interpretation_limit": "one 30-minute chain sample tests fill behavior, not strategy P&L or generalization",
}, sort_keys=True))
