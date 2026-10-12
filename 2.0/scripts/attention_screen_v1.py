#!/usr/bin/env python3
"""Shared skill screen for attention-type signals (Wikipedia pageviews, GDELT news).

    python scripts/attention_screen_v1.py wikipedia
    python scripts/attention_screen_v1.py gdelt

Each source is turned into a weekly (Friday) issuer x week matrix of attention, and
for GDELT also tone. The signals and measurement are fixed in the registries:
config/wikipedia_attention_returns_registry_v1.json and config/gdelt_news_registry_v1.json.
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
FSDS = ROOT / "data/sec_fsds_history_v1"
OUT = ROOT / "evidence"
STEP, SURGE, BASE = 4, 4, 26
SUFFIXES = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LLC", "LTD", "LIMITED", "PLC",
            "LP", "THE", "NV", "SA", "AG", "HOLDINGS", "HOLDING", "GROUP"}


def normalise(name: str) -> str:
    text = re.sub(r"/[^/]*/", " ", str(name).upper()).replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(t for t in text.split() if t not in SUFFIXES).lower()


def prices() -> pd.DataFrame:
    p = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    p.index = pd.to_datetime(p.index, utc=True).tz_localize(None).normalize()
    p.columns = [str(c).zfill(10) for c in p.columns]
    return p


def wikipedia(index) -> dict[str, pd.DataFrame]:
    frames = {}
    for f in (ROOT / "data/wikipedia_attention_v1/views").glob("*.json"):
        items = json.loads(f.read_text()).get("items", [])
        if not items:
            continue
        s = pd.Series({pd.Timestamp(i["timestamp"][:8]): i["views"] for i in items})
        daily = s.reindex(pd.date_range(s.index.min(), s.index.max()), fill_value=0)
        frames[f.stem] = daily.resample("W-FRI").sum()
    views = pd.DataFrame(frames).reindex(index)
    return {"attention": views}


def gdelt(index) -> tuple[dict[str, pd.DataFrame], dict]:
    names = []
    for path in sorted(FSDS.glob("*.zip")):
        try:
            with zipfile.ZipFile(path) as a, a.open("sub.txt") as h:
                names.append(pd.read_csv(io.TextIOWrapper(h, "utf-8", errors="replace"), sep="\t",
                                         usecols=["cik", "name"], low_memory=False))
        except Exception:                                                # noqa: BLE001
            continue
    sub = pd.concat(names).dropna()
    sub["cik10"] = sub.cik.astype("int64").astype(str).str.zfill(10)
    sub["key"] = sub.name.map(normalise)
    keys = sub.groupby("key").cik10.nunique()
    sub = sub[sub.key.isin(keys[keys == 1].index) & (sub.key.str.len() >= 3)]
    key_to_cik = dict(sub.drop_duplicates("key")[["key", "cik10"]].values)
    rows = []
    for f in sorted((ROOT / "data/gdelt_weekly_orgs_v1/days").glob("*.csv")):
        d = pd.read_csv(f, keep_default_na=False)
        d = d[d.org.isin(key_to_cik)]
        d["cik10"] = d.org.map(key_to_cik)
        # The Wednesday file is usable at that week's Friday close.
        d["week"] = pd.Timestamp(f.stem) + pd.Timedelta(days=2)
        rows.append(d)
    g = pd.concat(rows).groupby(["week", "cik10"])[["articles", "tone_x_articles"]].sum()
    att = g.articles.unstack().reindex(index)
    tone = (g.tone_x_articles / g.articles).unstack().reindex(index)
    return {"attention": att, "tone": tone}, {"matched_issuers": int(att.notna().any().sum())}


def screen(signal: pd.DataFrame, rets: pd.DataFrame, horizon: int, price: pd.DataFrame, rng) -> dict:
    rows = []
    for pos in range(BASE + SURGE, len(signal.index) - horizon - 1, STEP):
        s = signal.iloc[pos].dropna()
        s = s[price.iloc[pos].reindex(s.index) >= 5.0]
        fwd = (1 + rets.iloc[pos + 1:pos + 1 + horizon]).prod(min_count=horizon // 2) - 1
        f = pd.DataFrame({"s": s, "f": fwd.reindex(s.index)}).dropna()
        if len(f) < 50:
            continue
        ic = f.s.rank().corr(f.f.rank())
        dec = pd.qcut(f.s.rank(method="first"), 10, labels=False)
        m = f.f.groupby(dec).mean()
        rows.append({"date": signal.index[pos], "n": len(f), "ic": ic, "spread": m.iloc[-1] - m.iloc[0],
                     "mono": pd.Series(m.index).corr(pd.Series(m.to_numpy()), method="spearman")})
    d = pd.DataFrame(rows)
    if d.empty:
        return {"decisions": 0}
    ics, block = d.ic.to_numpy(), max(2, horizon // STEP)
    draws = [np.concatenate([ics[i:i + block] for i in rng.integers(0, max(1, len(ics) - block),
             size=int(np.ceil(len(ics) / block)))])[:len(ics)].mean() - ics.mean() for _ in range(4000)]
    half = len(d) // 2
    return {"decisions": int(len(d)), "independent": int(len(d) // block), "median_names": float(d.n.median()),
            "mean_ic": float(ics.mean()), "p": float((np.abs(draws) >= abs(ics.mean())).mean()),
            "decile_spread": float(d.spread.mean()), "monotonicity": float(d.mono.mean()),
            "first_half_ic": float(d.ic.iloc[:half].mean()), "second_half_ic": float(d.ic.iloc[half:].mean()),
            "first": str(d.date.iloc[0].date()), "last": str(d.date.iloc[-1].date())}


def main() -> int:
    source = sys.argv[1]
    rng = np.random.default_rng(20261013)
    p = prices()
    rets = p.pct_change(fill_method=None).where(lambda r: r.abs() <= 1.0)
    meta = {}
    if source == "wikipedia":
        data = wikipedia(p.index)
        bar = 0.025
    else:
        data, meta = gdelt(p.index)
        bar = 0.0125
    att = data["attention"].fillna(0.0)
    present = data["attention"].notna()
    surge = np.log(att.rolling(SURGE).mean() + 1) - np.log(att.shift(SURGE).rolling(BASE).mean() + 1)
    surge = surge.where(present.rolling(BASE + SURGE).sum() >= (BASE + SURGE) // 2)
    signals = {"attention_surge": surge}
    if "tone" in data:
        tone, n = data["tone"], data["attention"].fillna(0)
        tw = (tone.fillna(0) * n)
        recent = tw.rolling(SURGE).sum() / n.rolling(SURGE).sum().replace(0, np.nan)
        prior = tw.shift(SURGE).rolling(BASE).sum() / n.shift(SURGE).rolling(BASE).sum().replace(0, np.nan)
        signals["tone_shift"] = (recent - prior).where(present.rolling(BASE + SURGE).sum() >= (BASE + SURGE) // 2)
    result = {"source": source, "bonferroni_bar": bar, **meta, "results": {}}
    for name, sig in signals.items():
        for h in (4, 13):
            r = screen(sig, rets, h, p, rng)
            r["clears_bar"] = bool(r.get("p", 1) < bar and r.get("mean_ic", 0) > 0)
            result["results"][f"{name}@{h}w"] = r
            if r.get("decisions"):
                print(f"{source} {name}@{h}w: decisions {r['decisions']} (indep {r['independent']}), names {r['median_names']:.0f}, "
                      f"IC {r['mean_ic']:+.4f} p {r['p']:.3f}, spread {r['decile_spread']:+.2%}, mono {r['monotonicity']:+.2f}, "
                      f"halves {r['first_half_ic']:+.3f}/{r['second_half_ic']:+.3f} {r['first']}..{r['last']}"
                      + ("  CLEARS" if r["clears_bar"] else ""))
            else:
                print(f"{source} {name}@{h}w: no decisions")
    target = OUT / f"{source}_attention_screen_v1"
    target.mkdir(parents=True, exist_ok=True)
    (target / "result.json").write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
