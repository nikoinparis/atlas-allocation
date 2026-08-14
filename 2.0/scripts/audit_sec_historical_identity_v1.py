#!/usr/bin/env python3
"""Combine SEC current and recovered symbols and audit usable historical coverage."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_historical_identity_v1"


def latest(pattern: str) -> Path:
    values = sorted(ROOT.glob(pattern))
    if not values:
        raise RuntimeError(f"no artifact matched {pattern}")
    return values[-1]


def split_symbols(value: object) -> list[str]:
    if pd.isna(value):
        return []
    valid = re.compile(r"^(?=[A-Z0-9.\-]*[A-Z])[A-Z0-9][A-Z0-9.\-]{0,11}$")
    return sorted({part.strip().upper() for part in str(value).split("|") if valid.fullmatch(part.strip().upper())})


def main() -> int:
    universe = latest("data/sec_historical_universe_vintages/*-sec-historical-filers-v1")
    tagged_dir = latest("data/sec_historical_identity_vintages/*-sec-symbol-recovery-v1")
    legacy_dir = latest("data/sec_historical_identity_vintages/*-sec-legacy-symbol-recovery-v1")
    identities = pd.read_csv(universe / "cik_identity_coverage.csv", dtype={"cik10": str})
    membership = pd.read_csv(universe / "quarterly_membership.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    tagged = pd.read_csv(tagged_dir / "symbol_recovery.csv", dtype={"cik10": str})
    legacy = pd.read_csv(legacy_dir / "legacy_symbol_recovery.csv", dtype={"cik10": str})
    legacy_symbols = legacy.set_index("cik10")["legacy_symbols"].to_dict()
    tagged_symbols = tagged.set_index("cik10")["recovered_symbols"].to_dict()

    rows = []
    for row in identities.to_dict("records"):
        cik = row["cik10"]
        current = split_symbols(row.get("current_tickers"))
        direct = split_symbols(tagged_symbols.get(cik))
        old = split_symbols(legacy_symbols.get(cik))
        if current:
            symbols, source = current, "current_sec_mapping"
        elif direct:
            symbols, source = direct, "last_filing_inline_xbrl"
        elif old:
            symbols, source = old, "last_filing_instance_xbrl"
        else:
            symbols, source = [], "unresolved"
        rows.append({
            **row,
            "candidate_symbols": "|".join(symbols) if symbols else None,
            "symbol_count": len(symbols),
            "symbol_source": source,
        })
    combined = pd.DataFrame(rows)

    intervals = membership.groupby("cik10", as_index=False).agg(first_decision=("decision_at", "min"), last_decision=("decision_at", "max"))
    exploded = combined[combined["symbol_count"] == 1][["cik10", "candidate_symbols"]].merge(intervals, on="cik10", how="left")
    collision_rows = []
    for symbol, group in exploded.groupby("candidate_symbols"):
        records = group.sort_values("first_decision").to_dict("records")
        for left_index, left in enumerate(records):
            for right in records[left_index + 1:]:
                overlap = max(left["first_decision"], right["first_decision"]) <= min(left["last_decision"], right["last_decision"])
                if overlap:
                    collision_rows.append({
                        "symbol": symbol,
                        "left_cik10": left["cik10"],
                        "right_cik10": right["cik10"],
                        "overlap_start": max(left["first_decision"], right["first_decision"]),
                        "overlap_end": min(left["last_decision"], right["last_decision"]),
                    })
    collisions = pd.DataFrame(collision_rows)
    collision_ciks = set(collisions.get("left_cik10", [])) | set(collisions.get("right_cik10", []))
    combined["collision_flag"] = combined["cik10"].isin(collision_ciks)
    combined["single_symbol_usable_for_price_probe"] = (combined["symbol_count"] == 1) & ~combined["collision_flag"]

    attached = membership.merge(
        combined[["cik10", "candidate_symbols", "symbol_source", "symbol_count", "collision_flag", "single_symbol_usable_for_price_probe"]],
        on="cik10", how="left",
    )
    coverage = attached.groupby(["decision_at", "sector"], as_index=False).agg(
        members=("cik10", "nunique"),
        any_symbol=("candidate_symbols", lambda values: int(values.notna().sum())),
        usable_single_symbol=("single_symbol_usable_for_price_probe", "sum"),
        unresolved=("candidate_symbols", lambda values: int(values.isna().sum())),
        ambiguous_or_collision=("single_symbol_usable_for_price_probe", lambda values: int((~values.astype(bool)).sum())),
    )
    coverage["any_symbol_coverage"] = coverage["any_symbol"] / coverage["members"]
    coverage["usable_single_symbol_coverage"] = coverage["usable_single_symbol"] / coverage["members"]
    total = coverage.groupby("decision_at", as_index=False).agg(
        members=("members", "sum"), usable=("usable_single_symbol", "sum"), unresolved=("unresolved", "sum")
    )
    total["usable_coverage"] = total["usable"] / total["members"]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT / "combined_identity_map.csv", index=False)
    attached.to_csv(OUTPUT / "membership_with_candidate_symbols.csv", index=False)
    coverage.to_csv(OUTPUT / "coverage_by_decision_sector.csv", index=False)
    total.to_csv(OUTPUT / "coverage_by_decision.csv", index=False)
    collisions.to_csv(OUTPUT / "overlapping_symbol_collisions.csv", index=False)
    source_counts = combined["symbol_source"].value_counts().to_dict()
    latest_row = total.iloc[-1]
    recent = total[total["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")]
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "universe_vintage": str(universe),
        "tagged_symbol_vintage": str(tagged_dir),
        "legacy_symbol_vintage": str(legacy_dir),
        "historical_ciks": int(len(combined)),
        "source_counts": {str(key): int(value) for key, value in source_counts.items()},
        "ciks_with_any_candidate_symbol": int(combined["candidate_symbols"].notna().sum()),
        "ciks_with_usable_single_symbol": int(combined["single_symbol_usable_for_price_probe"].sum()),
        "unresolved_ciks": int(combined["candidate_symbols"].isna().sum()),
        "multi_symbol_ciks": int((combined["symbol_count"] > 1).sum()),
        "overlapping_collision_pairs": int(len(collisions)),
        "latest_members": int(latest_row["members"]),
        "latest_usable_coverage": float(latest_row["usable_coverage"]),
        "recent_min_usable_coverage": float(recent["usable_coverage"].min()),
        "full_min_usable_coverage": float(total["usable_coverage"].min()),
        "price_probe_authorized": True,
        "strategy_testing_authorized": False,
        "strategy_blockers": [
            "candidate symbols represent the last eligible filing and do not yet capture every historical ticker change",
            "ticker reuse must be validated against the returned price history and issuer identity",
            "free prices must include delisting outcomes or apply a declared conservative failure return",
            "unresolved and ambiguous companies must never be silently removed",
        ],
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = f"""# SEC historical identity audit v1

The SEC filing roster contains **{result['historical_ciks']:,}** technology/energy CIKs. Current SEC mapping resolves {source_counts.get('current_sec_mapping', 0):,}; explicit symbols from the last eligible inline filing resolve {source_counts.get('last_filing_inline_xbrl', 0):,}; and standalone legacy XBRL resolves another {source_counts.get('last_filing_instance_xbrl', 0):,}. **{result['unresolved_ciks']:,}** remain unresolved.

After excluding multiple-symbol identities and symbols assigned to overlapping CIK histories, **{result['ciks_with_usable_single_symbol']:,}** CIKs are eligible for a free-price coverage probe. Coverage is {result['latest_usable_coverage']:.1%} at the latest decision, never below {result['recent_min_usable_coverage']:.1%} from 2023 onward, and reaches a full-history minimum of {result['full_min_usable_coverage']:.1%}.

This authorizes only a price-availability and issuer-identity probe. It does not authorize a strategy backtest. The remaining blockers are historical ticker changes, ticker reuse, delisting returns, and explicit treatment of unresolved companies.
"""
    (OUTPUT / "report.md").write_text(report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
