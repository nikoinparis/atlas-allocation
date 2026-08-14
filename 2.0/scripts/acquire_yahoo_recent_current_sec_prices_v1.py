#!/usr/bin/env python3
"""Freeze recent Yahoo histories for currently mapped SEC universe CIKs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/membership_inventory_coverage.csv"
OUTPUT_ROOT = ROOT / "data/yahoo_recent_current_sec_price_vintages"
START = pd.Timestamp("2022-12-01")


def yahoo_symbol(value: object) -> str:
    return str(value).strip().upper().replace(".", "-")


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-symbols", default="")
    parser.add_argument("--label", default="yahoo-recent-current-sec-v1")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    recent = membership[
        (membership["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC"))
        & membership["symbol_source"].eq("current_sec_mapping")
        & membership["single_symbol_usable_for_price_probe"].astype(bool)
    ]
    identities = recent[["cik10", "candidate_symbols", "company_name_as_filed"]].drop_duplicates("cik10")
    identities["yahoo_symbol"] = identities["candidate_symbols"].map(yahoo_symbol)
    requested = {value.strip().upper() for value in args.only_symbols.split(",") if value.strip()}
    if requested:
        identities = identities[identities["yahoo_symbol"].isin(requested)].copy()
        missing = requested - set(identities["yahoo_symbol"])
        if missing:
            raise RuntimeError(f"requested symbols not in recent current SEC membership: {sorted(missing)}")
    if identities["yahoo_symbol"].duplicated().any():
        raise RuntimeError("current SEC CIKs contain duplicate Yahoo symbols")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-{args.label}"
    history = output / "histories"
    history.mkdir(parents=True, exist_ok=False)
    rows = []
    records = identities.sort_values("yahoo_symbol").to_dict("records")
    for offset in range(0, len(records), 40):
        batch = records[offset:offset + 40]
        symbols = [row["yahoo_symbol"] for row in batch]
        try:
            frame = yf.download(
                symbols, start=START.date().isoformat(), interval="1d", auto_adjust=False,
                actions=True, repair=False, group_by="ticker", threads=8, progress=False,
            )
        except Exception as exc:
            frame = pd.DataFrame()
            batch_error = f"batch_error:{type(exc).__name__}:{str(exc)[:200]}"
        else:
            batch_error = None
        for identity in batch:
            symbol = identity["yahoo_symbol"]
            result = {
                **identity,
                "status": "failed",
                "rows": 0,
                "first_price_date": None,
                "last_price_date": None,
                "history_file": None,
                "error": batch_error,
            }
            try:
                if frame.empty:
                    raise RuntimeError(batch_error or "empty batch")
                if isinstance(frame.columns, pd.MultiIndex):
                    available = set(frame.columns.get_level_values(0))
                    if symbol in available:
                        one = frame[symbol].copy()
                    elif symbol in set(frame.columns.get_level_values(1)):
                        one = frame.xs(symbol, axis=1, level=1).copy()
                    elif len(symbols) == 1:
                        one = frame.copy()
                        one.columns = one.columns.get_level_values(0)
                    else:
                        raise RuntimeError("symbol absent from batch response")
                elif len(symbols) == 1:
                    one = frame.copy()
                else:
                    raise RuntimeError("unexpected non-multiindex batch response")
                one = one.dropna(how="all").reset_index()
                if one.empty or "Close" not in one or one["Close"].dropna().empty:
                    raise RuntimeError("empty symbol history")
                date_column = "Date" if "Date" in one else one.columns[0]
                one[date_column] = pd.to_datetime(one[date_column], utc=True, errors="coerce").dt.strftime("%Y-%m-%d")
                one = one.dropna(subset=[date_column])
                payload = one.to_csv(index=False).encode("utf-8")
                destination = history / f"{safe_name(symbol)}.csv.gz"
                destination.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
                dates = pd.to_datetime(one[date_column], errors="coerce")
                result.update({
                    "status": "ok",
                    "rows": int(len(one)),
                    "first_price_date": dates.min().date().isoformat(),
                    "last_price_date": dates.max().date().isoformat(),
                    "history_file": str(destination.relative_to(output)),
                    "uncompressed_sha256": hashlib.sha256(payload).hexdigest(),
                    "compressed_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "error": None,
                })
            except Exception as exc:
                result["error"] = result["error"] or f"{type(exc).__name__}:{str(exc)[:300]}"
            rows.append(result)
        print(f"processed {min(offset + 40, len(records))}/{len(records)}; histories {sum(row['status'] == 'ok' for row in rows)}", flush=True)

    pulls = pd.DataFrame(rows).sort_values(["status", "yahoo_symbol"]).reset_index(drop=True)
    pulls.to_csv(output / "price_results.csv", index=False)
    ok = int((pulls["status"] == "ok").sum())
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Yahoo Finance via pinned yfinance container",
        "yfinance_version": yf.__version__,
        "python_version": platform.python_version(),
        "start_date": START.date().isoformat(),
        "requested_ciks": int(len(pulls)),
        "histories_returned": ok,
        "histories_failed": int(len(pulls) - ok),
        "raw_history_rate": float(ok / len(pulls)),
        "point_in_time_membership_source": str(MEMBERSHIP),
        "terminal_outcomes_complete": False,
        "strategy_testing_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
