#!/usr/bin/env python3
"""Rank the backfill so a usable panel exists on day three, not day twenty-six.

Including the 8,830 issuers that exited before the current panel begins is what
makes the longer sample worth having; it is also four times the requests. The
queue is therefore tiered, and the tiers encode a research decision made before
any result exists: continuity first because it is cheapest, then long-lived
exited issuers because that is the actual survivorship correction, then the rest.

Tier 1 alone is a survivorship-biased panel and is marked as unresearchable on
its own.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/price_backfill_2012_v1.json"
UNIVERSE = ROOT / "data/historical_universe_2012_v1"
OUTPUT = ROOT / "data/price_backfill_2012_v1"
EVIDENCE = ROOT / "evidence/price_backfill_2012_v1"


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]

    issuers = pd.read_csv(UNIVERSE / "issuers.csv.gz", dtype={"cik10": str})
    spans = pd.read_csv(UNIVERSE / "ticker_spans.csv.gz", dtype={"cik10": str})
    membership = pd.read_csv(UNIVERSE / "quarterly_membership.csv.gz", dtype={"cik10": str})

    quarters_filed = membership.groupby("cik10")["quarter"].nunique().rename("quarters_filed")
    issuers = issuers.merge(quarters_filed, on="cik10", how="left")
    issuers["quarters_filed"] = issuers["quarters_filed"].fillna(0).astype(int)

    # One request pair per (issuer, ticker) span, so ticker changes are covered
    # rather than assumed away.
    # spans already carry per-ticker first_filed/last_filed; keep those, because a
    # ticker span is the correct request window when an issuer changed ticker.
    queue = spans.merge(
        issuers[[
            "cik10", "company_name_latest", "sic",
            "quarters_filed", "in_current_price_panel", "exited_before_end", "distinct_tickers",
        ]],
        on="cik10", how="left",
    )

    def tier(row: pd.Series) -> int:
        if row["in_current_price_panel"]:
            return 1
        if row["quarters_filed"] >= 12:
            return 2
        return 3

    queue["tier"] = queue.apply(tier, axis=1)
    queue["tier_name"] = queue["tier"].map({t["tier"]: t["name"] for t in spec["priority_tiers"]})

    # Request window: the issuer's own filing span, padded, floored at the
    # declared history start so trailing-year signals are defined on day one.
    start_floor = pd.Timestamp(spec["history_start"])
    queue["first_filed"] = pd.to_datetime(queue["first_filed"])
    queue["last_filed"] = pd.to_datetime(queue["last_filed"])
    # Reach back a year before the first filing under this ticker so trailing-year
    # signals are defined at the issuer's first decision date, floored at the
    # declared history start.
    queue["request_start"] = (queue["first_filed"] - pd.Timedelta(days=400)).clip(lower=start_floor)
    queue.loc[queue["tier"] == 1, "request_start"] = start_floor
    queue["request_end"] = queue["last_filed"] + pd.Timedelta(days=30)

    queue = queue.sort_values(
        ["tier", "quarters_filed", "cik10", "ticker"],
        ascending=[True, False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    queue["queue_position"] = range(1, len(queue) + 1)

    per_day = spec["rate_limits"]["requests_per_day"] / 2
    queue["expected_day"] = ((queue["queue_position"] - 1) // per_day + 1).astype(int)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    columns = [
        "queue_position", "tier", "tier_name", "cik10", "ticker", "company_name_latest",
        "sic", "request_start", "request_end", "quarters_filed", "distinct_tickers",
        "in_current_price_panel", "expected_day",
    ]
    queue[columns].to_csv(OUTPUT / "queue.csv.gz", index=False, compression="gzip")

    by_tier = queue.groupby(["tier", "tier_name"]).agg(
        requests=("ticker", "size"), issuers=("cik10", "nunique")
    ).reset_index()

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "queue_rows": int(len(queue)),
        "distinct_issuers": int(queue["cik10"].nunique()),
        "by_tier": [
            {
                "tier": int(r.tier), "name": r.tier_name,
                "request_pairs": int(r.requests), "issuers": int(r.issuers),
                "cumulative_days_at_free_tier": None,
            }
            for r in by_tier.itertuples()
        ],
        "estimated_unattended_days": int(queue["expected_day"].max()),
        "days_to_finish_tier_1": int(queue.loc[queue["tier"] == 1, "expected_day"].max()),
        "days_to_finish_tier_2": int(queue.loc[queue["tier"] <= 2, "expected_day"].max()),
        "warning": "Tier 1 alone reproduces the survivorship bias this program exists to remove. Research is authorised only after tier 2 completes.",
        "performance_evaluated": False,
        "live_trading_enabled": False,
    }
    cumulative = 0
    for entry in result["by_tier"]:
        cumulative += entry["request_pairs"]
        entry["cumulative_days_at_free_tier"] = int(cumulative / per_day) + 1

    (EVIDENCE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
