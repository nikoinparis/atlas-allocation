#!/usr/bin/env python3
"""Reduce GDELT GKG 1.0 daily files (one Wednesday a week) to organisation mentions and tone.

For config/gdelt_news_registry_v1.json. Each file is streamed, reduced to
(date, organisation, articles, tone x articles) and discarded. Resumable: one
small output file per sampled day.
"""

from __future__ import annotations

import csv
import io
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/gdelt_weekly_orgs_v1/days"
URL = "https://data.gdeltproject.org/gkg/{}.gkg.csv.zip"
MIN_ARTICLES = 3
csv.field_size_limit(sys.maxsize)


def wednesdays() -> list[date]:
    day, out = date(2013, 4, 3), []
    while day < date.today() - timedelta(days=2):
        out.append(day)
        day += timedelta(days=7)
    return out


def reduce_day(day: date) -> str:
    target = OUTPUT / f"{day:%Y%m%d}.csv"
    if target.is_file():
        return "cached"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(URL.format(f"{day:%Y%m%d}"), timeout=180) as response:
                blob = response.read()
            break
        except Exception as error:                               # noqa: BLE001
            if attempt == 3:
                return f"failed {error}"
            time.sleep(5 * (attempt + 1))
    articles, tone = defaultdict(int), defaultdict(float)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as handle:
            reader = csv.reader(io.TextIOWrapper(handle, "utf-8", errors="replace"), delimiter="\t")
            header = next(reader)
            i_n, i_org, i_tone = header.index("NUMARTS"), header.index("ORGANIZATIONS"), header.index("TONE")
            for row in reader:
                if len(row) <= max(i_n, i_org, i_tone) or not row[i_org]:
                    continue
                try:
                    n = int(row[i_n])
                    t = float(row[i_tone].split(",")[0])
                except ValueError:
                    continue
                for org in set(row[i_org].split(";")):
                    if org:
                        articles[org] += n
                        tone[org] += n * t
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with tmp.open("w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["org", "articles", "tone_x_articles"])
        for org, n in articles.items():
            if n >= MIN_ARTICLES:
                w.writerow([org, n, round(tone[org], 3)])
    tmp.rename(target)
    return f"{len(articles)} orgs"


def main() -> int:
    days = wednesdays()
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for day, status in zip(days, pool.map(reduce_day, days)):
            done += 1
            if status.startswith("failed") or done % 50 == 0:
                print(f"{done}/{len(days)} {day} {status}", flush=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
