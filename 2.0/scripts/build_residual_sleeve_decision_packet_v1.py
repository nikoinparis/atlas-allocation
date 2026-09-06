#!/usr/bin/env python3
"""Assemble the immutable decision packet for the residual sleeve's forward clock.

`record_sec_residual_controlled_sleeve_forward_v1.py` consumes a packet; it does
not build one, and nothing in this repository built one until now.  Step 213's
lesson was that assembling a packet by hand against a Friday deadline is how a
wrong allocation gets into a hash-chained log that cannot be corrected, so the
assembly runs here, ahead of the window, and is rehearsable.

The packet carries:

  control_target_weights   the four-sleeve composite from
                           build_control_composite_book_v1, which needs the
                           sleeve return paths extended through the decision
                           Friday before it can compute its 11-week overlay
  residual_target_weights  the residual-momentum book in force at the decision
                           Friday: the latest quarterly execution at or before it

Both are keyed by ticker so the observation packet can price a single union.
Issuers with no price source route to cash, matching the control leg's declared
treatment of unpriced slots and the protocol's base scenario.

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from systematic_trader.forward_evidence import ForwardEvidenceError, canonical_bytes, file_hash
from systematic_trader.sec_real_tournament_v2 import build_family_weights

import build_control_composite_book_v1 as control_book

PROTOCOL_PATH = ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
PROGRAM_CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
CASH = "cash::USD"


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def residual_book(panel_dir: Path, decision: pd.Timestamp) -> tuple[dict[str, float], dict[str, object]]:
    panel = pd.read_csv(panel_dir / "panel.csv.gz", dtype={"cik10": str})
    program = json.loads(PROGRAM_CONFIG.read_text(encoding="utf-8"))
    weights, _ = build_family_weights(panel, program)
    frame = weights["residual_momentum"].copy()
    # build_family_weights renames execution_at to decision_at, so this column is
    # the date the book is actually held from, which is what a live book needs.
    frame["decision_at"] = pd.to_datetime(frame["decision_at"], utc=True).dt.tz_localize(None)
    eligible = [d for d in sorted(frame.decision_at.unique()) if d <= decision]
    if not eligible:
        raise ForwardEvidenceError(f"no residual execution at or before {decision.date()}")
    held_from = max(eligible)
    live = frame[frame.decision_at == held_from]

    tickers = control_book.ticker_map()
    book: dict[str, float] = {}
    unpriced = []
    for row in live.itertuples(index=False):
        symbol = tickers.get(row.cik10)
        if symbol:
            book[symbol] = book.get(symbol, 0.0) + float(row.weight)
        else:
            unpriced.append(row.cik10)
            book[CASH] = book.get(CASH, 0.0) + float(row.weight)
    total = sum(book.values())
    if abs(total - 1.0) > 1e-9:
        raise ForwardEvidenceError(f"residual weights sum to {total}, not one")
    provenance = {
        "held_from": str(held_from.date()),
        "names": int(len(live)),
        "distinct_symbols": int(len([k for k in book if k != CASH])),
        "unpriced_cik10s": sorted(unpriced),
        "cash_from_unpriced": float(book.get(CASH, 0.0)),
    }
    return {k: v for k, v in sorted(book.items())}, provenance


def price_identity(symbols: list[str]) -> dict[str, dict[str, str]]:
    """Where each held symbol can be priced on the realization side.

    The books are keyed by ticker because that is what the control leg produces
    and what a human can read, but the SEC price panels are keyed by cik10 and
    the ETF prices live in a different file entirely.  Resolving that on the
    observation side would mean inverting a non-injective map a week later, so
    the identity travels inside the hashed decision packet instead.
    """
    tickers = control_book.ticker_map()
    inverted: dict[str, list[str]] = {}
    for cik, symbol in tickers.items():
        inverted.setdefault(symbol, []).append(cik)
    identity: dict[str, dict[str, str]] = {}
    for symbol in symbols:
        if symbol == CASH:
            identity[symbol] = {"source": "cash", "key": CASH}
        elif symbol in inverted:
            identity[symbol] = {"source": "sec_cik10", "key": sorted(inverted[symbol])[0]}
            if len(inverted[symbol]) > 1:
                identity[symbol]["colliding_cik10s"] = "|".join(sorted(inverted[symbol]))
        else:
            identity[symbol] = {"source": "etf_weekly_prices", "key": symbol}
    return identity


def source_manifest(panel_dir: Path, decision: pd.Timestamp, source_data_through: str) -> dict[str, object]:
    inputs = [
        PROGRAM_CONFIG,
        panel_dir / "manifest.json",
        panel_dir / "panel.csv.gz",
        ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv",
        ROOT / "evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv",
        control_book.LEADER_PATH,
        control_book.CASH_PATH,
        control_book.ETF_WEIGHTS,
        control_book.INVENTORY,
        ROOT / "scripts/build_control_composite_book_v1.py",
        Path(__file__).resolve(),
    ]
    return {
        "manifest_type": "sec_residual_forward_decision_sources_v1",
        "decision_date": str(decision.date()),
        "source_data_through": source_data_through,
        "files": {
            str(path.relative_to(ROOT)): file_hash(path)
            for path in sorted(inputs, key=lambda p: str(p))
        },
    }


def build(decision: pd.Timestamp, panel_dir: Path, observed_at: datetime) -> tuple[dict, dict, dict]:
    control = control_book.build(decision)
    residual, residual_provenance = residual_book(panel_dir, decision)

    # The overlay is computed from sleeve paths that must already reach the
    # decision Friday; build_control_composite_book_v1 fails loudly otherwise, so
    # the paths' own last date is the honest source_data_through.
    paths_through = control_book.read_path(control_book.CASH_PATH).index.max()
    source_data_through = str(min(paths_through, decision).date())

    manifest = source_manifest(panel_dir, decision, source_data_through)
    basis = {
        "packet_type": "sec_residual_forward_decision_v1",
        "protocol_version": "sec_residual_controlled_sleeve_forward_v1",
        "decision_date": str(decision.date()),
        "snapshot_id": None,  # derived from the manifest hash once it is written
        "observed_at_utc": observed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_data_through": source_data_through,
        "source_manifest": None,  # filled once the manifest is written
        "source_manifest_sha256": None,
        "control_target_weights": control["weights"],
        "residual_target_weights": residual,
        "price_identity": price_identity(sorted(set(control["weights"]) | set(residual))),
        "provenance": {
            "control": {k: v for k, v in control.items() if k != "weights"},
            "residual": residual_provenance,
            "panel": str(panel_dir.relative_to(ROOT)),
        },
    }
    return basis, manifest, control


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--panel", default="data/sec_broad_research_panel_v3")
    parser.add_argument("--out", default="evidence/forward_sec_residual_controlled_sleeve_v1/incoming")
    parser.add_argument("--rehearsal", action="store_true",
                        help="write to the rehearsal directory and label the packet as one")
    args = parser.parse_args()

    decision = pd.Timestamp(args.decision_date)
    if decision.weekday() != 4:
        raise SystemExit("forward decision dates must be Fridays")
    panel_dir = ROOT / args.panel
    observed_at = datetime.now(timezone.utc)

    basis, manifest, _ = build(decision, panel_dir, observed_at)

    out = ROOT / (args.out if not args.rehearsal else "evidence/forward_sec_residual_controlled_sleeve_v1/rehearsal")
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{'rehearsal__' if args.rehearsal else ''}decision__{decision.date()}"
    manifest_path = out / f"{stem}__sources.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    basis["source_manifest"] = str(manifest_path.relative_to(ROOT))
    basis["source_manifest_sha256"] = file_hash(manifest_path)
    basis["snapshot_id"] = f"residual-{decision.date()}-{basis['source_manifest_sha256'][:12]}"
    if args.rehearsal:
        basis["rehearsal"] = True
    packet = {**basis, "packet_sha256": sha256_value(basis)}
    packet_path = out / f"{stem}.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "packet": str(packet_path.relative_to(ROOT)),
        "packet_sha256": packet["packet_sha256"],
        "decision_date": packet["decision_date"],
        "observed_at_utc": packet["observed_at_utc"],
        "source_data_through": packet["source_data_through"],
        "control_positions": len(packet["control_target_weights"]),
        "residual_positions": len(packet["residual_target_weights"]),
        "provenance": packet["provenance"],
        "rehearsal": bool(args.rehearsal),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
