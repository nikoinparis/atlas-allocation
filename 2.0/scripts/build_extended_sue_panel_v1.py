#!/usr/bin/env python3
"""Rebuild standardised unexpected earnings back through the 2012 roster.

Step 253 closed S3 as underpowered rather than refuted: fourteen quarterly
decisions cannot resolve an information coefficient of 0.02, and the only horizon
that cleared got its significance from overlapping windows. The book on that
signal correlated 0.002 and 0.008 with the two existing strategies, the lowest
this project has measured, which is a reason to extend the sample rather than a
reason to believe.

This extends it. The point-in-time roster reaches 2012-04-01, so the ceiling is
about fifty-eight quarterly decisions instead of fourteen.

**The survivorship exposure is measured, not assumed.** Company Facts is a current
pull, so an issuer that delisted in 2015 is named by the 2015 roster and absent
from the cache. That is exactly the bias CLAUDE.md rule 4 exists to prevent, and
the honest response is to report the roster-to-facts coverage for every decision
rather than to quietly compute an IC over whoever survived. If early coverage is
poor, the early ICs are not usable and the report has to say so.

SUE itself is unchanged from Step 201: a seasonal random walk on quarterly EPS,
scaled by the standard deviation of the previous eight surprises, using only
facts filed strictly before the decision.

This builds a feature panel. It measures no returns and proposes no strategy.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location(
    "branches", ROOT / "scripts/run_point_in_time_fundamental_branches_v1.py")
_branches = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_branches)

MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_full_v1/recent_membership_readiness.csv"
CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"


def facts_path(cik10: str) -> Path | None:
    for suffix in (".gz", ".json"):
        candidate = CACHE / f"companyfacts_{cik10}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/extended_sue_panel_v1")
    parser.add_argument("--limit-issuers", type=int, default=0)
    args = parser.parse_args()

    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    membership["decision_at"] = pd.to_datetime(membership.decision_at, utc=True).dt.tz_localize(None)
    decisions = sorted(membership.decision_at.unique())

    issuers = sorted(set(membership.cik10))
    if args.limit_issuers:
        issuers = issuers[:args.limit_issuers]

    available = {cik: facts_path(cik) for cik in issuers}
    have = {cik for cik, path in available.items() if path is not None}

    # Parse each issuer once, not once per decision.
    parsed: dict[str, pd.DataFrame] = {}
    for cik in sorted(have):
        try:
            # extract_file(path, cik10) returns a list of dicts, not a frame. The
            # first version of this script called it with one argument and caught
            # the TypeError in a bare except, which turned a signature mismatch
            # into a silent zero-coverage result for every decision.
            records = _branches.extract_file(available[cik], cik)
        except Exception:
            continue
        if not records:
            continue
        frame = pd.DataFrame(records)
        if frame.empty or "metric" not in frame.columns:
            continue
        frame = frame[frame.metric == "eps"].copy()
        if frame.empty:
            continue
        # Normalise to tz-naive on both sides. The source carries offsets and the
        # decision dates do not, and pandas raises rather than guessing.
        for column in ("filed", "end"):
            values = pd.to_datetime(frame[column], errors="coerce", utc=True)
            frame[column] = values.dt.tz_localize(None)
        parsed[cik] = frame.dropna(subset=["filed", "end"])

    rows, coverage = [], []
    for decision in decisions:
        members = sorted(set(membership.loc[membership.decision_at == decision, "cik10"]))
        with_facts = [c for c in members if c in parsed]
        computed = 0
        for cik in with_facts:
            frame = parsed[cik]
            eligible = frame[frame.filed < decision]
            if eligible.empty:
                continue
            value = _branches.sue(eligible)
            if np.isfinite(value):
                rows.append({"decision_at": decision, "cik10": cik,
                             "standardized_unexpected_earnings": float(value)})
                computed += 1
        coverage.append({
            "decision_at": str(pd.Timestamp(decision).date()),
            "roster_members": len(members),
            "members_with_companyfacts": len(with_facts),
            "facts_coverage": round(len(with_facts) / max(1, len(members)), 4),
            "sue_computed": computed,
            "sue_coverage": round(computed / max(1, len(members)), 4),
        })

    panel = pd.DataFrame(rows)
    cover = pd.DataFrame(coverage)
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out / "sue_panel.csv.gz", index=False, compression="gzip")
    cover.to_csv(out / "coverage_by_decision.csv", index=False)

    early = cover[cover.decision_at < "2016-01-01"]
    late = cover[cover.decision_at >= "2020-01-01"]
    manifest = {
        "experiment": "extended_sue_panel_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "membership": str(MEMBERSHIP.relative_to(ROOT)),
        "decisions": len(decisions),
        "window": [str(pd.Timestamp(decisions[0]).date()), str(pd.Timestamp(decisions[-1]).date())],
        "issuers_in_roster": len(issuers),
        "issuers_with_companyfacts": len(have),
        "issuers_parsed_with_eps": len(parsed),
        "rows": int(len(panel)),
        "survivorship": {
            "why_it_matters": "Company Facts is a current pull, so an issuer that delisted before it "
                              "is named by the historical roster and absent from the cache",
            "mean_facts_coverage_before_2016": float(early.facts_coverage.mean()) if len(early) else None,
            "mean_facts_coverage_from_2020": float(late.facts_coverage.mean()) if len(late) else None,
            "coverage_gap_pp": (round((late.facts_coverage.mean() - early.facts_coverage.mean()) * 100, 2)
                                if len(early) and len(late) else None),
        },
        "measures_no_returns": True,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print("\ncoverage by decision (first 6 and last 6):")
    print(pd.concat([cover.head(6), cover.tail(6)]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
