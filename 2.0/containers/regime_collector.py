#!/usr/bin/env python3
"""Isolated collector for public Cboe, FRED, and Google Trends regime data."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CBOE = {
    "VIX": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    "VIX3M": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv",
    "VIX6M": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX6M_History.csv",
}
FRED = ["T10Y2Y", "BAMLH0A0HYM2", "NAPM", "FEDFUNDS", "DGS3MO", "DTWEXBGS", "NFCI"]
KEYWORDS = ["recession", "stock market crash", "inflation", "bear market"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_text(url: str) -> str:
    response = requests.get(url, timeout=(15, 90), headers={"User-Agent": "portfolio-optimizer-research/2.0"})
    response.raise_for_status()
    return response.text


def cboe(output: Path, observed: str) -> dict:
    rows = []
    for series, url in CBOE.items():
        raw = get_text(url)
        (output / f"raw_cboe_{series}.csv").write_text(raw)
        frame = pd.read_csv(StringIO(raw))
        frame.columns = [str(column).strip().upper() for column in frame]
        frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce")
        frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
        selected = frame.dropna(subset=["DATE", "CLOSE"])[["DATE", "CLOSE"]]
        for row in selected.itertuples(index=False):
            rows.append({"observation_date": row.DATE.date().isoformat(), "series_id": series, "value": float(row.CLOSE), "knowledge_at_utc": observed, "source_url": url})
    result = pd.DataFrame(rows).sort_values(["observation_date", "series_id"])
    result.to_csv(output / "cboe_observations.csv", index=False)
    return {"status": "complete", "rows": len(result), "series": len(CBOE), "latest": result.observation_date.max()}


def fred(output: Path, observed: str) -> dict:
    rows = []; errors = []
    for series in FRED:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
        try:
            raw = get_text(url)
            (output / f"raw_fred_{series}.csv").write_text(raw)
            frame = pd.read_csv(StringIO(raw))
            frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
            frame[series] = pd.to_numeric(frame[series], errors="coerce")
            for row in frame.dropna().itertuples(index=False):
                rows.append({"observation_date": row.observation_date.date().isoformat(), "series_id": series, "value": float(getattr(row, series)), "knowledge_at_utc": observed, "source_url": url})
        except Exception as error:
            errors.append({"series_id": series, "error": str(error)})
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["observation_date", "series_id"]).to_csv(output / "fred_observations.csv", index=False)
    else:
        pd.DataFrame(columns=["observation_date", "series_id", "value", "knowledge_at_utc", "source_url"]).to_csv(output / "fred_observations.csv", index=False)
    return {"status": "complete" if not errors else "partial", "rows": len(result), "series": len(FRED) - len(errors), "errors": errors, "latest": None if result.empty else result.observation_date.max()}


def google(output: Path, observed: str, start: str, end: str, max_attempts: int, pause_seconds: int) -> dict:
    try:
        from pytrends.request import TrendReq
    except Exception as error:
        return {"status": "blocked", "error": f"pytrends unavailable: {error}"}
    columns = []
    errors = []
    for keyword in KEYWORDS:
        final_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                # pytrends 4.9.2 is incompatible with current urllib3 when its
                # own retry flags are used, so retries are explicit here.
                client = TrendReq(hl="en-US", tz=360, timeout=(10, 30))
                client.build_payload([keyword], cat=0, timeframe=f"{start} {end}", geo="US")
                frame = client.interest_over_time()
                if frame.empty or keyword not in frame:
                    raise RuntimeError("empty response")
                series = pd.to_numeric(frame[keyword], errors="coerce").rename(keyword)
                series.index = pd.to_datetime(series.index).tz_localize(None)
                columns.append(series)
                final_error = None
                break
            except Exception as error:
                final_error = error
                if attempt < max_attempts:
                    time.sleep(pause_seconds * attempt)
        if final_error is not None:
            errors.append({"keyword": keyword, "attempts": max_attempts, "error": str(final_error)})
        time.sleep(pause_seconds)
    if columns:
        result = pd.concat(columns, axis=1).sort_index()
        result.index.name = "Date"
        result.to_csv(output / "google_trends_raw.csv")
    else:
        pd.DataFrame(columns=["Date", *KEYWORDS]).to_csv(output / "google_trends_raw.csv", index=False)
    return {
        "status": "complete" if len(columns) == len(KEYWORDS) else "partial" if columns else "blocked",
        "keywords": len(columns), "errors": errors, "rows": 0 if not columns else len(result),
        "scaling_warning": "unofficial pytrends 0-100 values are request-window scaled and can revise when the full window is re-requested",
        "knowledge_at_utc": observed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", default="/export")
    parser.add_argument("--start", default="2005-01-01"); parser.add_argument("--end", required=True)
    parser.add_argument("--google-max-attempts", type=int, default=3)
    parser.add_argument("--google-pause-seconds", type=int, default=15)
    args = parser.parse_args(); output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    observed = datetime.now(timezone.utc).isoformat()
    metadata = {
        "observed_at_utc": observed, "collector": "free_regime_collector_v1",
        "cboe": cboe(output, observed), "fred": fred(output, observed),
        "google": google(output, observed, args.start, args.end, args.google_max_attempts, args.google_pause_seconds),
    }
    files = sorted(path for path in output.iterdir() if path.is_file())
    metadata["files"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in files}
    required = (metadata["cboe"]["status"], metadata["fred"]["status"], metadata["google"]["status"])
    metadata["status"] = "complete" if required[0] == "complete" and required[1] in {"complete", "partial"} and required[2] == "complete" else "partial"
    (output / "acquisition_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0 if metadata["cboe"]["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
