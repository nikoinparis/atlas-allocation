#!/usr/bin/env python3
"""Record, forward and untouched, whether the residual sleeve's book beats its tie.

The residual leg selects twenty names from a tie of roughly fifty-nine by taking
the lowest CIK10s.  Step 234 showed that in sample the declared book lands at the
99th percentile of two hundred random tie-breaks while CIK number carries no
forward predictive content inside the pool.  That is a strong claim about luck
and it deserves to be settled forward rather than argued about.

This records twenty-two books every Friday on identical prices: the declared
book, the tie-agnostic pool, and twenty pre-declared random tie-breaks.  Because
the pricing is common, the only difference between the series is which names each
holds, which is exactly the question.

It modifies nothing.  The frozen protocol is read for its parameters and never
written.  A companion record has no promotion authority of any kind.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.evaluation import performance_metrics
from systematic_trader.forward_evidence import (
    ForwardEvidenceError,
    append_record,
    canonical_bytes,
    file_hash,
    read_and_verify_log,
)

PROTOCOL = ROOT / "config/forward/residual_tie_agnostic_companion_v1.json"
RESIDUAL_PROTOCOL = ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
OUTPUT = ROOT / "evidence/forward_residual_tie_agnostic_companion_v1"
DECISIONS = OUTPUT / "decisions.jsonl"
OBSERVATIONS = OUTPUT / "observations.jsonl"
NARROW_PRICES = ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz"
BROAD_PRICES = ROOT / "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz"
DEFAULT_PANEL = ROOT / "data/sec_broad_research_panel_v3"


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def window_start(day: str) -> datetime:
    parsed = date.fromisoformat(day)
    if parsed.weekday() != 4:
        raise ForwardEvidenceError("forward evidence dates must be Fridays")
    return datetime.combine(parsed, time(21, 0), tzinfo=timezone.utc)


def select(frame: pd.DataFrame, order: pd.Series, config: dict) -> list[str]:
    breadth = int(config["breadth"])
    ranked = frame.assign(_order=order).sort_values(["score", "_order"], ascending=[False, True])
    limit = max(1, int(np.floor(float(config["maximum_sector_weight"]) * breadth)))
    chosen: list[str] = []
    counts: dict[str, int] = {}
    for row in ranked.itertuples(index=False):
        if counts.get(row.sector, 0) >= limit:
            continue
        chosen.append(row.cik10)
        counts[row.sector] = counts.get(row.sector, 0) + 1
        if len(chosen) == breadth:
            break
    return chosen


def books(panel_dir: Path, decision: pd.Timestamp, config: dict) -> tuple[dict[str, list[str]], str]:
    panel = pd.read_csv(panel_dir / "panel.csv.gz", dtype={"cik10": str})
    panel["execution_at"] = pd.to_datetime(panel["execution_at"], utc=True).dt.tz_localize(None)
    eligible = [d for d in sorted(panel.execution_at.unique()) if d <= decision]
    if not eligible:
        raise ForwardEvidenceError(f"no residual execution at or before {decision.date()}")
    held_from = max(eligible)
    frame = (panel[panel.execution_at == held_from][["cik10", "sector", "residual_momentum"]]
             .rename(columns={"residual_momentum": "score"}).dropna(subset=["score"]))
    breadth = int(config["breadth"])
    if len(frame) < breadth:
        raise ForwardEvidenceError(f"only {len(frame)} scored issuers at {held_from.date()}")

    out = {"declared_tiebreak": select(frame, frame.cik10, config)}
    cutoff = frame.score.sort_values(ascending=False).iloc[breadth - 1]
    out["tie_agnostic_pool"] = sorted(frame.loc[frame.score >= cutoff, "cik10"])
    for seed in config["random_seeds"]:
        digest = hashlib.blake2b(f"{seed}|{held_from}".encode(), digest_size=8).digest()
        rng = np.random.default_rng(int.from_bytes(digest, "big"))
        order = pd.Series(rng.permutation(len(frame)), index=frame.index)
        out[f"random_tiebreak_{seed:02d}"] = select(frame, order, config)
    return out, str(held_from.date())


def load_prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    for path in (NARROW_PRICES, BROAD_PRICES):
        frame = pd.read_csv(path, index_col=0)
        frame.index = pd.to_datetime(frame.index)
        frame.columns = [str(c) for c in frame.columns]
        frames.append(frame.sort_index())
    return frames[0], frames[1]


def realized(members: list[str], week: pd.Timestamp) -> tuple[float, int, int]:
    narrow, broad = load_prices()
    values = []
    for cik in members:
        for frame in (narrow, broad):
            if cik not in frame.columns or week not in frame.index:
                continue
            position = frame.index.get_loc(week)
            if position == 0:
                continue
            current = pd.to_numeric(frame.iloc[position][cik], errors="coerce")
            prior = pd.to_numeric(frame.iloc[position - 1][cik], errors="coerce")
            if pd.isna(current) or pd.isna(prior) or prior <= 0:
                continue
            values.append(float(current / prior - 1.0))
            break
    if not values:
        raise ForwardEvidenceError(f"no member of a tracked book priced for the week ending {week.date()}")
    return float(np.mean(values)), len(values), len(members)


def turnover(prior: list[str], current: list[str]) -> float:
    if not prior:
        return 1.0
    before = {c: 1.0 / len(prior) for c in prior}
    after = {c: 1.0 / len(current) for c in current}
    return 0.5 * sum(abs(after.get(c, 0.0) - before.get(c, 0.0)) for c in set(before) | set(after))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--realize", action="store_true",
                        help="also record the realization for the decision one week earlier")
    parser.add_argument("--panel", default=str(DEFAULT_PANEL.relative_to(ROOT)))
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print without writing any record")
    args = parser.parse_args()

    config = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if config.get("live_trading_enabled") or config.get("execution_enabled"):
        raise ForwardEvidenceError("a companion record cannot enable execution")
    day = str(args.decision_date)
    start = window_start(day)
    now = datetime.now(timezone.utc)
    if not args.dry_run:
        if date.fromisoformat(day) < date.fromisoformat(str(config["first_eligible_decision_date"])):
            raise ForwardEvidenceError("decision predates the companion's frozen boundary")
        if now < start:
            raise ForwardEvidenceError(
                f"the {day} window opens at 21:00 UTC that day; it is {now:%Y-%m-%dT%H:%M:%S}Z")
        if now >= start + timedelta(days=7):
            raise ForwardEvidenceError(f"the {day} window closed; a missed window is not backfillable")

    decision = pd.Timestamp(day)
    panel_dir = ROOT / args.panel
    tracked, held_from = books(panel_dir, decision, config)

    existing = ([] if args.dry_run or not DECISIONS.is_file() else read_and_verify_log(
        DECISIONS, date_field="decision_date",
        first_eligible_date=str(config["first_eligible_decision_date"])))
    prior = dict(existing[-1]["books"]) if existing else {}

    payload = {
        "record_type": "residual_tie_agnostic_companion_decision_v1",
        "protocol_version": config["protocol_version"],
        "decision_date": day,
        "eligible_realization_date": (date.fromisoformat(day) + timedelta(days=7)).isoformat(),
        "observed_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "book_held_from": held_from,
        "panel": str(panel_dir.relative_to(ROOT)),
        "panel_manifest_sha256": file_hash(panel_dir / "manifest.json"),
        "books": {name: sorted(members) for name, members in sorted(tracked.items())},
        "book_sizes": {name: len(members) for name, members in sorted(tracked.items())},
        "turnover": {name: turnover(prior.get(name, []), members) for name, members in sorted(tracked.items())},
        "declared_overlap_with_pool": float(
            len(set(tracked["declared_tiebreak"]) & set(tracked["tie_agnostic_pool"]))
            / len(tracked["declared_tiebreak"])),
        "mean_declared_overlap_with_seeds": float(np.mean([
            len(set(tracked["declared_tiebreak"]) & set(v)) / len(tracked["declared_tiebreak"])
            for k, v in tracked.items() if k.startswith("random_tiebreak_")])),
        "companion_protocol_sha256": file_hash(PROTOCOL),
        "accompanies_protocol_sha256": file_hash(RESIDUAL_PROTOCOL),
        "modifies": "nothing",
        "execution_enabled": False,
    }

    if args.dry_run:
        # A dry run leaves no trace, directories included.
        print(json.dumps({k: v for k, v in payload.items() if k != "books"}, indent=2, sort_keys=True))
        return 0

    OUTPUT.mkdir(parents=True, exist_ok=True)
    record = append_record(DECISIONS, payload, date_field="decision_date",
                           first_eligible_date=str(config["first_eligible_decision_date"]))
    print(json.dumps({k: v for k, v in record.items() if k != "books"}, indent=2, sort_keys=True))

    if args.realize:
        realization = pd.Timestamp(day)
        decisions = read_and_verify_log(DECISIONS, date_field="decision_date",
                                        first_eligible_date=str(config["first_eligible_decision_date"]))
        source = next((r for r in decisions if str(r["eligible_realization_date"]) == day), None)
        if source is None:
            raise ForwardEvidenceError(f"no companion decision realizes on {day}")
        cost = float(config["cost_bps_per_unit_turnover"]) / 10_000.0
        gross, priced, roster = {}, {}, {}
        for name, members in dict(source["books"]).items():
            value, count, total = realized(list(members), realization)
            gross[name], priced[name], roster[name] = value, count, total
        net = {name: gross[name] - float(source["turnover"][name]) * cost for name in gross}
        seeds = sorted(v for k, v in net.items() if k.startswith("random_tiebreak_"))
        declared = net["declared_tiebreak"]
        observation = {
            "record_type": "residual_tie_agnostic_companion_observation_v1",
            "protocol_version": config["protocol_version"],
            "decision_date": source["decision_date"],
            "realization_date": day,
            "decision_record_hash": source["record_hash"],
            "observed_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gross_returns": gross,
            "net_returns": net,
            "priced_members": priced,
            "roster_members": roster,
            "declared_rank_among_seeds": int(sum(1 for v in seeds if v < declared)),
            "seed_count": len(seeds),
            "seed_median_net_return": float(np.median(seeds)),
            "declared_minus_seed_median": float(declared - np.median(seeds)),
            "declared_minus_pool": float(declared - net["tie_agnostic_pool"]),
            "companion_protocol_sha256": file_hash(PROTOCOL),
            "modifies": "nothing",
            "execution_enabled": False,
        }
        recorded = append_record(OBSERVATIONS, observation, date_field="realization_date",
                                 first_eligible_date=str(config["first_eligible_decision_date"]))
        print(json.dumps({k: v for k, v in recorded.items()
                          if k not in ("gross_returns", "net_returns", "priced_members", "roster_members")},
                         indent=2, sort_keys=True))

    observations = ([] if not OBSERVATIONS.is_file() else read_and_verify_log(
        OBSERVATIONS, date_field="realization_date",
        first_eligible_date=str(config["first_eligible_decision_date"])))
    status = {
        "protocol_version": config["protocol_version"],
        "generated_at_utc": now.isoformat(),
        "saved_decisions": len(read_and_verify_log(
            DECISIONS, date_field="decision_date",
            first_eligible_date=str(config["first_eligible_decision_date"]))),
        "observed_weeks": len(observations),
        "required_weeks": int(config["required_untouched_weeks"]),
        "remaining_weeks": max(0, int(config["required_untouched_weeks"]) - len(observations)),
        "metrics": {
            name: performance_metrics([float(r["net_returns"][name]) for r in observations]).to_dict()
            for name in (observations[-1]["net_returns"] if observations else {})
        },
        "times_declared_beat_the_seed_median": int(sum(
            1 for r in observations if float(r["declared_minus_seed_median"]) > 0)),
        "modifies": "nothing",
        "promotion_authorized": False,
        "execution_enabled": False,
    }
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
