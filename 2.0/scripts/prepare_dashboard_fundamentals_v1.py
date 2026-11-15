#!/usr/bin/env python3
"""Acquire fresh Company Facts and score new dashboard quarters in an isolated directory."""
from __future__ import annotations

import concurrent.futures
import hashlib
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "src")]
import run_sec_growth_survivorship_retest_v1 as growth
import run_sec_independent_fundamental_discovery_v1 as factors
from recover_sec_historical_symbols_v1 import SecFetcher
from acquire_sec_fsds_history_v1 import AGENT

OUT = ROOT / "evidence/dashboard_continuation_v1"
CACHE = ROOT / "data/dashboard_continuation_companyfacts_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="recompute the current quarter from its cached raw vintage")
    args = parser.parse_args()
    quarter = pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("Q")
    expected = quarter.start_time.tz_localize("UTC")
    saved = OUT / "growth_choices.csv"
    if saved.exists() and not args.refresh:
        through = pd.to_datetime(pd.read_csv(saved).decision_at, utc=True).max()
        if through >= expected:
            print(f"quarterly selections already current through {through.date()}")
            return 0
    # New rosters are separate vintages. Sealed research and forward pins stay intact.
    for config, destination in [("sec_historical_filer_universe_v1.json", "dashboard_continuation_universe_v1"),
                                ("sec_historical_filer_universe_broad_v2.json", "dashboard_continuation_broad_universe_v1")]:
        existing = sorted((ROOT / "data" / destination).glob("*/manifest.json"))
        archive_end = str(quarter - 1)
        if existing and json.loads(existing[-1].read_text())["archive_end"] >= archive_end:
            continue
        subprocess.run([sys.executable, str(ROOT / "scripts/build_sec_historical_filer_universe_v1.py"),
                        "--config", str(ROOT / "config" / config), "--start", "2023Q1", "--end", archive_end,
                        "--output-root", str(ROOT / "data" / destination)], check=True,
                       env={**os.environ, "SEC_USER_AGENT": os.environ.get("SEC_USER_AGENT", AGENT)})
    vintage = sorted((ROOT / "data/dashboard_continuation_universe_v1").glob("*-sec-historical-filers-v1"))[-1]
    member = pd.read_csv(vintage / "quarterly_membership.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    old = pd.read_csv(growth.MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    new = member[member.decision_at > old.decision_at.max()].copy()
    if new.empty:
        raise ValueError("no new quarterly roster was acquired")
    weekly = pd.read_csv(ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz", index_col=0, parse_dates=True)
    for day, group in new.groupby("decision_at"):
        # Eligibility at execution, rather than today's surviving ticker list.
        execution = weekly.index[weekly.index > day.tz_localize(None)][0]
        new.loc[group.index, "tradable_member"] = group.cik10.map(weekly.loc[execution].notna().to_dict()).fillna(False)
    membership = pd.concat([old, new], ignore_index=True)
    targets = sorted(set(new.loc[new.tradable_member.astype(bool), "cik10"]))
    fetcher = SecFetcher(CACHE, AGENT)

    def acquire(cik):
        fetcher.json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", f"companyfacts_{cik}")
        return cik

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i, _ in enumerate(pool.map(acquire, targets), 1):
            if i % 50 == 0 or i == len(targets):
                print(f"fresh Company Facts {i}/{len(targets)}", flush=True)
    # Historical decisions keep their sealed inputs; only the new quarter is scored.
    factors.SUBMISSIONS = vintage / "qualifying_submissions.csv"
    factors.FACT_CACHE = CACHE
    pilot = json.loads(factors.PILOT.read_text())
    submissions = pd.read_csv(factors.SUBMISSIONS, dtype={"cik10": str}, usecols=["adsh", "cik10", "available_at"]).rename(columns={"adsh": "accession"})
    tasks = [(cik, submissions[submissions.cik10 == cik][["accession", "available_at"]].astype(str).values.tolist(),
              sorted(new.decision_at.unique()), pilot["canonical_metrics"], pilot["accepted_forms"]) for cik in targets]
    # Threads share the explicitly isolated cache path on macOS as well as Linux.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        frames = list(pool.map(factors.build_one, tasks))
    inputs = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    old_inputs = pd.read_csv(factors.OUTPUT / "quarterly_factor_inputs.csv", dtype={"cik10": str})
    old_inputs["decision_time"] = pd.to_datetime(old_inputs.decision_time, utc=True)
    inputs = factors.enrich(pd.concat([old_inputs, inputs], ignore_index=True))
    scores, _ = factors.score_families(inputs, membership, json.loads(factors.CONFIG.read_text()))
    _, choices = growth.score_growth(inputs, membership, json.loads(growth.CONFIG_PATH.read_text()))
    OUT.mkdir(parents=True, exist_ok=True)
    old_scores = pd.read_csv(factors.OUTPUT / "factor_scores.csv", dtype={"cik10": str})
    old_scores["decision_at"] = pd.to_datetime(old_scores.decision_at, utc=True)
    scores = pd.concat([old_scores, scores[scores.decision_at > old_scores.decision_at.max()]], ignore_index=True)
    old_choices = pd.read_csv(growth.OUTPUT / "portfolio_choices.csv", dtype={"cik10": str})
    old_choices["decision_at"] = pd.to_datetime(old_choices.decision_at, utc=True)
    choices = pd.concat([old_choices, choices[choices.decision_at > old_choices.decision_at.max()]], ignore_index=True)
    scores.to_csv(OUT / "factor_scores.csv", index=False)
    choices.to_csv(OUT / "growth_choices.csv", index=False)
    membership.to_csv(OUT / "membership.csv", index=False)
    inputs[inputs.decision_time > old.decision_at.max()].to_csv(OUT / "new_factor_inputs.csv", index=False)
    provenance = {"universe_vintage": str(vintage.relative_to(ROOT)),
                  "fundamentals_through": str(scores.decision_at.max().date()),
                  "submissions_sha256": hashlib.sha256(factors.SUBMISSIONS.read_bytes()).hexdigest(),
                  "companyfacts": {cik: json.loads((CACHE / f"companyfacts_{cik}.json").read_text()) for cik in targets},
                  "normalized_inputs_sha256": hashlib.sha256((OUT / "new_factor_inputs.csv").read_bytes()).hexdigest()}
    (OUT / "fundamental_sources.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"scored through {scores.decision_at.max()}; {len(choices)} growth choices", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
