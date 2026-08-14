#!/usr/bin/env python3
"""Container-only Yahoo/yfinance ETF downloader."""

from __future__ import annotations

import argparse
import csv
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_number(value):
    if pd.isna(value):
        return ""
    return float(value)


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--period", default="max")
    parser.add_argument("--output", type=Path, default=Path("/export"))
    args = parser.parse_args()
    symbols = sorted({symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()})
    args.output.mkdir(parents=True, exist_ok=True)

    price_rows = []
    action_rows = []
    security_rows = []
    membership_rows = []
    errors = []
    pulls = []
    for ticker in symbols:
        started = utc_now()
        try:
            frame = yf.Ticker(ticker).history(
                period=args.period,
                interval="1d",
                auto_adjust=False,
                actions=True,
                repair=False,
                raise_errors=True,
            )
            if frame.empty:
                raise RuntimeError("empty history")
            completed = utc_now()
            revision = f"yfinance-{yf.__version__}:{completed}"
            dates = []
            for index, row in frame.iterrows():
                observation_date = pd.Timestamp(index).date().isoformat()
                dates.append(observation_date)
                adjusted = row.get("Adj Close", row.get("Close"))
                price_rows.append({
                    "observation_date": observation_date,
                    "security_id": f"yahoo-ticker:{ticker}",
                    "ticker": ticker,
                    "open": clean_number(row.get("Open")),
                    "high": clean_number(row.get("High")),
                    "low": clean_number(row.get("Low")),
                    "close": clean_number(row.get("Close")),
                    "adjusted_close": clean_number(adjusted),
                    "volume": clean_number(row.get("Volume")),
                    "knowledge_at_utc": completed,
                    "source_revision": revision,
                })
                for column, action_type in (
                    ("Dividends", "cash_distribution"),
                    ("Stock Splits", "stock_split"),
                    ("Capital Gains", "capital_gain"),
                ):
                    amount = row.get(column)
                    if amount is not None and not pd.isna(amount) and float(amount) != 0.0:
                        action_rows.append({
                            "security_id": f"yahoo-ticker:{ticker}",
                            "ticker": ticker,
                            "event_date": observation_date,
                            "action_type": action_type,
                            "amount": float(amount),
                            "knowledge_at_utc": completed,
                            "source_revision": revision,
                        })
            security_rows.append({
                "security_id": f"yahoo-ticker:{ticker}",
                "permanent_id_source": "synthetic_ticker_id_not_permanent",
                "ticker": ticker,
                "first_observed_date": min(dates),
                "last_observed_date": max(dates),
                "delisting_date": "",
                "knowledge_at_utc": completed,
            })
            membership_rows.append({
                "security_id": f"yahoo-ticker:{ticker}",
                "ticker": ticker,
                "universe": "portfolio_optimizer_free_current_etfs",
                "effective_from": "",
                "effective_to": "",
                "knowledge_at_utc": completed,
                "source_revision": revision,
                "point_in_time_membership": "false",
            })
            pulls.append({"ticker": ticker, "started_at_utc": started, "completed_at_utc": completed, "rows": len(frame), "status": "ok"})
        except Exception as error:
            completed = utc_now()
            errors.append({"ticker": ticker, "error_type": type(error).__name__, "message": str(error)})
            pulls.append({"ticker": ticker, "started_at_utc": started, "completed_at_utc": completed, "rows": 0, "status": "failed"})

    if errors:
        (args.output / "acquisition_metadata.json").write_text(json.dumps({"status": "failed", "symbols": symbols, "pulls": pulls, "errors": errors}, indent=2) + "\n")
        print(json.dumps({"status": "failed", "errors": errors}))
        return 2

    price_rows.sort(key=lambda row: (row["observation_date"], row["ticker"]))
    action_rows.sort(key=lambda row: (row["event_date"], row["ticker"], row["action_type"]))
    write_csv(args.output / "prices.csv", [
        "observation_date", "security_id", "ticker", "open", "high", "low", "close", "adjusted_close", "volume", "knowledge_at_utc", "source_revision"
    ], price_rows)
    write_csv(args.output / "universe_membership.csv", [
        "security_id", "ticker", "universe", "effective_from", "effective_to", "knowledge_at_utc", "source_revision", "point_in_time_membership"
    ], membership_rows)
    write_csv(args.output / "security_master.csv", [
        "security_id", "permanent_id_source", "ticker", "first_observed_date", "last_observed_date", "delisting_date", "knowledge_at_utc"
    ], security_rows)
    write_csv(args.output / "corporate_actions.csv", [
        "security_id", "ticker", "event_date", "action_type", "amount", "knowledge_at_utc", "source_revision"
    ], action_rows)
    write_csv(args.output / "delistings.csv", [
        "security_id", "ticker", "delisting_date", "delisting_return", "reason", "knowledge_at_utc", "source_revision"
    ], [])
    observed_at = max(item["completed_at_utc"] for item in pulls)
    metadata = {
        "status": "complete",
        "provider": "Yahoo Finance via yfinance",
        "yfinance_version": yf.__version__,
        "python_version": platform.python_version(),
        "period": args.period,
        "symbols": symbols,
        "symbol_count": len(symbols),
        "price_rows": len(price_rows),
        "action_rows": len(action_rows),
        "observed_at_utc": observed_at,
        "pulls": pulls,
        "errors": [],
    }
    (args.output / "acquisition_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "complete", "observed_at_utc": observed_at, "symbols": len(symbols), "price_rows": len(price_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
