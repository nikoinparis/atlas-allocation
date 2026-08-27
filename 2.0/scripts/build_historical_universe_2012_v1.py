#!/usr/bin/env python3
"""What did the investable universe look like in 2013, not what does it look like now?

The research panel is the current SEC universe. Every issuer that filed in 2012 and
stopped before 2022 is missing from it by construction, which means backfilling
prices for the current panel alone would buy a longer sample carrying worse
survivorship bias than the short one it replaced.

The 57 quarters of Financial Statement Data Sets already on disk fix that without a
single network request. Each sub.txt names every filer in that quarter with its filed
date, and the XBRL instance filename conventionally starts with the issuer's ticker,
which is how identity is recovered here offline.

This builds membership and identity only. It evaluates nothing.
"""

from __future__ import annotations

import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/historical_universe_2012_v1.json"
CACHE = ROOT / "data/sec_fsds_sub_cache"
OUTPUT = ROOT / "data/historical_universe_2012_v1"
EVIDENCE = ROOT / "evidence/historical_universe_2012_v1"

TICKER = re.compile(r"^([A-Za-z][A-Za-z0-9-]{0,9})-\d{8}[._]")


def load_quarters(forms: set[str]) -> pd.DataFrame:
    frames = []
    for path in sorted(CACHE.glob("*.sub.txt.gz")):
        quarter = path.name.split(".")[0]
        with gzip.open(path, "rt", errors="replace") as handle:
            frame = pd.read_csv(
                handle, sep="\t", dtype=str,
                usecols=["cik", "name", "sic", "form", "period", "filed", "instance", "countryba"],
            )
        frame["quarter"] = quarter
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined[combined["form"].isin(forms)].copy()
    combined["cik10"] = combined["cik"].str.zfill(10)
    combined["filed_at"] = pd.to_datetime(combined["filed"], format="%Y%m%d", errors="coerce")
    return combined.dropna(subset=["filed_at"])


def resolve_tickers(filings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    filings = filings.copy()
    filings["ticker"] = (
        filings["instance"].fillna("").str.extract(TICKER, expand=False).str.upper()
    )
    resolved = filings.dropna(subset=["ticker"])
    spans = (
        resolved.groupby(["cik10", "ticker"])
        .agg(
            first_filed=("filed_at", "min"),
            last_filed=("filed_at", "max"),
            filings=("ticker", "size"),
        )
        .reset_index()
        .sort_values(["cik10", "last_filed"], ascending=[True, False], kind="mergesort")
    )
    per_issuer = (
        spans.groupby("cik10")
        .agg(distinct_tickers=("ticker", "nunique"))
        .reset_index()
    )
    return spans, per_issuer


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]
    forms = set(spec["forms_included"])

    filings = load_quarters(forms)
    quarters = sorted(filings["quarter"].unique())

    membership = (
        filings.groupby(["cik10", "quarter"])
        .agg(filings=("form", "size"), filed_at=("filed_at", "min"))
        .reset_index()
    )

    issuers = (
        filings.sort_values("filed_at", kind="mergesort")
        .groupby("cik10")
        .agg(
            company_name_latest=("name", "last"),
            sic=("sic", "last"),
            country=("countryba", "last"),
            first_filed=("filed_at", "min"),
            last_filed=("filed_at", "max"),
            first_quarter=("quarter", "first"),
            last_quarter=("quarter", "last"),
            total_filings=("form", "size"),
        )
        .reset_index()
    )

    spans, per_issuer = resolve_tickers(filings)
    issuers = issuers.merge(per_issuer, on="cik10", how="left")
    issuers["distinct_tickers"] = issuers["distinct_tickers"].fillna(0).astype(int)
    latest = spans.drop_duplicates("cik10", keep="first")[["cik10", "ticker"]]
    issuers = issuers.merge(latest.rename(columns={"ticker": "latest_ticker"}), on="cik10", how="left")

    final_quarter = quarters[-1]
    issuers["still_filing_at_end"] = issuers["last_quarter"] == final_quarter
    issuers["exited_before_end"] = ~issuers["still_filing_at_end"]

    # The population the current panel structurally cannot contain.
    panel_path = ROOT / "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz"
    panel_ciks: set[str] = set()
    if panel_path.exists():
        header = pd.read_csv(panel_path, nrows=0)
        panel_ciks = {c.zfill(10) for c in header.columns if c != "Date"}
    issuers["in_current_price_panel"] = issuers["cik10"].isin(panel_ciks)

    missing_history = issuers[issuers["exited_before_end"] & ~issuers["in_current_price_panel"]]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    issuers.to_csv(OUTPUT / "issuers.csv.gz", index=False, compression="gzip")
    membership.to_csv(OUTPUT / "quarterly_membership.csv.gz", index=False, compression="gzip")
    spans.to_csv(OUTPUT / "ticker_spans.csv.gz", index=False, compression="gzip")

    per_quarter = membership.groupby("quarter")["cik10"].nunique()
    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "quarters": {"count": len(quarters), "first": quarters[0], "last": quarters[-1]},
        "filings_included": int(len(filings)),
        "issuers_total": int(len(issuers)),
        "issuers_still_filing_at_end": int(issuers["still_filing_at_end"].sum()),
        "issuers_exited_before_end": int(issuers["exited_before_end"].sum()),
        "issuers_in_current_price_panel": int(issuers["in_current_price_panel"].sum()),
        "issuers_absent_from_current_panel_and_exited": int(len(missing_history)),
        "survivorship_gap_share": float(len(missing_history) / len(issuers)),
        "ticker_resolution": {
            "issuers_with_a_ticker": int((issuers["distinct_tickers"] > 0).sum()),
            "issuers_unresolved": int((issuers["distinct_tickers"] == 0).sum()),
            "issuers_with_ticker_change": int((issuers["distinct_tickers"] > 1).sum()),
            "resolved_share": float((issuers["distinct_tickers"] > 0).mean()),
        },
        "members_per_quarter": {
            "first_quarter": int(per_quarter.iloc[0]),
            "last_quarter": int(per_quarter.iloc[-1]),
            "median": int(per_quarter.median()),
        },
        "artifacts": ["issuers.csv.gz", "quarterly_membership.csv.gz", "ticker_spans.csv.gz"],
        "performance_evaluated": False,
        "live_trading_enabled": False,
    }
    (EVIDENCE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
