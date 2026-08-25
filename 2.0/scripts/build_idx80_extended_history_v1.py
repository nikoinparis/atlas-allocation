#!/usr/bin/env python3
"""Build a frozen research-only IDX80 history spanning launch through the latest official archive."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "idx80_pre2024_history_v1.json"
OFFICIAL_ROOT = ROOT / "data" / "indonesia_idx80_history_vintages"
OUTPUT_ROOT = ROOT / "data" / "indonesia_idx80_extended_history_vintages"


def split_tickers(value: str) -> list[str]:
    return sorted(set(value.split()))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_transition(current: set[str], transition: dict[str, object]) -> set[str]:
    additions = set(split_tickers(str(transition["add"])))
    removals = set(split_tickers(str(transition["remove"])))
    if additions & current:
        raise ValueError(f"already-present additions for {transition['effective_from']}: {sorted(additions & current)}")
    if not removals <= current:
        raise ValueError(f"missing removals for {transition['effective_from']}: {sorted(removals - current)}")
    updated = (current - removals) | additions
    if len(updated) != 80:
        raise ValueError(f"transition {transition['effective_from']} produced {len(updated)} names")
    return updated


def rows_for_period(period: dict[str, object], tickers: set[str]) -> list[dict[str, object]]:
    available = f"{period['published_date']}T23:59:59+00:00"
    return [
        {
            "ticker": ticker,
            "vendor_ticker": f"{ticker}.JK",
            "universe": "IDX80",
            "effective_from": period["effective_from"],
            "effective_to": period["effective_to"],
            "available_at": available,
            "source_id": period["source_id"],
            "official_source": str(period["evidence_tier"]).startswith("official_document"),
            "point_in_time_membership": True,
            "evidence_tier": period["evidence_tier"],
        }
        for ticker in sorted(tickers)
    ]


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    launch = config["launch"]
    current = set(split_tickers(launch["tickers"]))
    if len(current) != 80:
        raise ValueError(f"launch universe has {len(current)} names")
    rows = rows_for_period(launch, current)
    transition_audit: list[dict[str, object]] = []
    for transition in config["transitions"]:
        prior = current
        current = validate_transition(current, transition)
        transition_audit.append(
            {
                "effective_from": transition["effective_from"],
                "added": sorted(current - prior),
                "removed": sorted(prior - current),
                "result_count": len(current),
                "source_id": transition["source_id"],
                "evidence_tier": transition["evidence_tier"],
            }
        )
        rows.extend(rows_for_period(transition, current))

    official_vintage = (OFFICIAL_ROOT / "LATEST").read_text(encoding="utf-8").strip()
    official_dir = OFFICIAL_ROOT / official_vintage
    official = pd.read_csv(official_dir / "idx80_membership.csv")
    official["evidence_tier"] = "official_idx_direct"
    historical = pd.DataFrame(rows)
    membership = pd.concat([historical, official], ignore_index=True)
    membership = membership.sort_values(["effective_from", "ticker"]).reset_index(drop=True)
    counts = membership.groupby(["effective_from", "effective_to"]).size()
    if not counts.eq(80).all():
        raise ValueError(f"non-80 periods: {counts[counts.ne(80)].to_dict()}")
    starts = pd.to_datetime(membership[["effective_from", "effective_to"]].drop_duplicates()["effective_from"])
    if starts.min() != pd.Timestamp("2019-02-01"):
        raise ValueError("extended history does not begin at IDX80 launch")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    vintage_id = f"{stamp}-idx80-extended-history-v1"
    destination = OUTPUT_ROOT / vintage_id
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="idx80-extended-", dir=ROOT / "data") as temporary:
        staging = Path(temporary)
        membership.to_csv(staging / "idx80_membership.csv", index=False)
        (staging / "transition_audit.json").write_text(
            json.dumps(transition_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.copy2(CONFIG, staging / CONFIG.name)
        files = {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(staging.iterdir())
        }
        manifest = {
            "vintage_id": vintage_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "research-only point-in-time IDX80 constituent history from launch",
            "official_direct_vintage_2024_onward": official_vintage,
            "periods": int(len(counts)),
            "membership_rows": int(len(membership)),
            "union_tickers": int(membership["ticker"].nunique()),
            "coverage": {"from": membership["effective_from"].min(), "to": membership["effective_to"].max()},
            "claims": {
                "point_in_time_for_covered_period": True,
                "complete_from_idx80_launch": True,
                "official_direct_complete": False,
                "pre_2024_uses_archived_mirrors_or_contemporaneous_reports": True,
                "minor_reviews_change_membership": False,
                "performance_claim_authorized": False,
                "live_trading_enabled": False
            },
            "files": files,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.copytree(staging, destination)
    (OUTPUT_ROOT / "LATEST").write_text(vintage_id + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
