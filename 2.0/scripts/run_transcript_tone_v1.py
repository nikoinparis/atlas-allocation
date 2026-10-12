#!/usr/bin/env python3
"""Earnings-call tone and tone change, finally tested against returns.

Pre-registered in config/transcript_tone_registry_v1.json.

    python scripts/run_transcript_tone_v1.py --parquet DIR --lm PATH/LM.csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import attention_screen_v1 as att                                         # noqa: E402

CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
OUTPUT = ROOT / "evidence/transcript_tone_v1"
WORD = re.compile(r"[A-Za-z]+")


def load_lm(path: Path) -> tuple[set[str], set[str]]:
    lm = pd.read_csv(path)
    lm.columns = [c.strip().lower() for c in lm.columns]
    word = lm.columns[0]
    pos = set(lm.loc[lm["positive"] > 0, word].str.lower())
    neg = set(lm.loc[lm["negative"] > 0, word].str.lower())
    return pos, neg


def tones(parquet_dir: Path, pos: set[str], neg: set[str]) -> pd.DataFrame:
    rows = []
    for path in sorted(parquet_dir.glob("*.parquet")):
        f = pq.ParquetFile(path)
        for i in range(f.num_row_groups):
            t = f.read_row_group(i, columns=["symbol", "date", "content"]).to_pandas()
            for sym, d, text in t.itertuples(index=False):
                words = WORD.findall((text or "").lower())
                p = sum(w in pos for w in words)
                n = sum(w in neg for w in words)
                rows.append({"symbol": sym, "date": d, "words": len(words), "pos": p, "neg": n,
                             "tone": (p - n) / (p + n) if p + n else np.nan})
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame.date, errors="coerce")
    return frame.dropna(subset=["date", "tone"]).sort_values(["symbol", "date"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--lm", required=True)
    args = ap.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cache = OUTPUT / "call_tones.csv.gz"
    if cache.is_file():
        calls = pd.read_csv(cache, parse_dates=["date"])
    else:
        calls = tones(Path(args.parquet), *load_lm(Path(args.lm)))
        calls.to_csv(cache, index=False)
    calls["tone_change"] = calls.groupby("symbol").tone.diff()

    cat = pd.read_csv(CATALOGUE, dtype={"cik10": str}).drop_duplicates("symbol")
    sym_to_cik = dict(zip(cat.symbol, cat.cik10))
    calls["cik10"] = calls.symbol.map(sym_to_cik)
    match = float(calls.cik10.notna().mean())
    print(f"calls {len(calls):,}, companies {calls.symbol.nunique()}, matched to price panel {match:.1%}, "
          f"{calls.date.min().date()}..{calls.date.max().date()}")
    calls = calls.dropna(subset=["cik10"])

    p = att.prices()
    rets = p.pct_change(fill_method=None).where(lambda r: r.abs() <= 1.0)
    weeks = p.index
    # usable at the first weekly close strictly after date + 1 day
    calls["usable"] = weeks[np.searchsorted(weeks.values, (calls.date + pd.Timedelta(days=1)).values, side="right")
                            .clip(max=len(weeks) - 1)]
    rng = np.random.default_rng(20261013)
    result = {"calls": int(len(calls)), "match_rate": match, "results": {}}
    for col, name in (("tone", "T1_tone"), ("tone_change", "T2_tone_change")):
        mat = pd.DataFrame(index=weeks, columns=sorted(calls.cik10.unique()), dtype=float)
        for row in calls.dropna(subset=[col]).itertuples():
            mat.at[row.usable, row.cik10] = getattr(row, col)
        signal = mat.ffill(limit=13)                    # most recent call within 13 weeks
        for h in (4, 13):
            r = att.screen(signal, rets, h, p, rng)
            r["clears_bar"] = bool(r.get("p", 1) < 0.0125 and r.get("mean_ic", 0) > 0)
            result["results"][f"{name}@{h}w"] = r
            print(f"{name}@{h}w: decisions {r['decisions']} (indep {r['independent']}), names {r['median_names']:.0f}, "
                  f"IC {r['mean_ic']:+.4f} p {r['p']:.3f}, spread {r['decile_spread']:+.2%}, mono {r['monotonicity']:+.2f}, "
                  f"halves {r['first_half_ic']:+.3f}/{r['second_half_ic']:+.3f}" + ("  CLEARS" if r["clears_bar"] else ""))
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
