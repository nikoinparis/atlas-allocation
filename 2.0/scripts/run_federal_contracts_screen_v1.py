#!/usr/bin/env python3
"""Queue item B5: do rising federal contract obligations predict returns?

Pre-registered in config/federal_contracts_registry_v1.json. One signal, one
horizon, the CLAUDE.md section 2 skill screen only -- no book is built here.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/federal_contracts_registry_v1.json"
CONTRACTS = ROOT / "data/usaspending_contracts_v1/quarterly_recipient_obligations.csv.gz"
FSDS = ROOT / "data/sec_fsds_history_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
OUTPUT = ROOT / "evidence/federal_contracts_screen_v1"
HORIZON = 13
LAG_DAYS = 91
MIN_TTM = 1_000_000.0
BAR = 0.05
PLACEBO_RUNS = 200
SUFFIXES = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LLC", "LTD",
            "LIMITED", "PLC", "LP", "THE", "NV", "SA", "AG", "HOLDINGS", "HOLDING", "GROUP"}


def normalise(name: str) -> str:
    if not isinstance(name, str):
        return ""
    text = re.sub(r"/[^/]*/", " ", name.upper())
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    tokens = [t for t in text.split() if t not in SUFFIXES]
    return " ".join(tokens)


def sec_names() -> pd.DataFrame:
    frames = []
    for path in sorted(FSDS.glob("*.zip")):
        try:
            with zipfile.ZipFile(path) as archive, archive.open("sub.txt") as handle:
                sub = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["cik", "name", "sic"], low_memory=False)
        except Exception:                                    # noqa: BLE001
            continue
        frames.append(sub)
    sub = pd.concat(frames).dropna(subset=["cik", "name"])
    sub["cik10"] = sub.cik.astype("int64").astype(str).str.zfill(10)
    sub["key"] = sub.name.map(normalise)
    sub["sic2"] = sub.sic.fillna(0).astype("int64").astype(str).str.zfill(4).str[:2]
    keys = sub.groupby("key").cik10.nunique()
    unique = keys[keys == 1].index                          # a name naming two issuers is dropped
    sub = sub[sub.key.isin(unique) & (sub.key != "")]
    return sub.drop_duplicates(["key"])[["key", "cik10"]], sub.groupby("cik10").sic2.last()


def quarter_end(label: str) -> pd.Timestamp:
    return pd.Period(label, freq="Q").end_time.normalize().tz_localize("UTC")


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20261011)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(CONTRACTS)
    raw["key"] = raw.parent_name.fillna(raw.name).map(normalise)
    names, sic2 = sec_names()
    matched = raw.merge(names, on="key", how="left")
    rate = matched.loc[matched.cik10.notna(), "amount"].sum() / matched.amount.sum()
    print(f"contract rows {len(raw):,}; dollars matched to an SEC filer: {rate:.1%}; "
          f"issuers matched: {matched.cik10.nunique():,}")
    by = (matched.dropna(subset=["cik10"]).groupby(["cik10", "quarter"]).amount.sum()
          .unstack("quarter").fillna(0.0))
    by = by[sorted(by.columns, key=lambda q: pd.Period(q, freq="Q"))]
    ends = pd.Series({q: quarter_end(q) for q in by.columns})
    ttm = by.T.rolling(4).sum().T                            # TTM ending at each quarter

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c).zfill(10) for c in prices.columns]
    returns = prices.pct_change(fill_method=None)
    returns = returns.where(returns.abs() <= 1.0)

    rows = []
    for decision in pd.date_range("2013-04-01", "2026-10-01", freq="QS", tz="UTC"):
        usable = [q for q in by.columns if ends[q] + pd.Timedelta(days=LAG_DAYS) <= decision]
        if len(usable) < 8:
            continue
        latest, prior = usable[-1], usable[-5]
        now, then = ttm[latest], ttm[prior]
        ok = (now >= MIN_TTM) & (then >= MIN_TTM)
        signal = np.log(now[ok] / then[ok])
        execution = returns.index[returns.index > decision]
        if len(execution) == 0:
            continue
        pos = returns.index.get_indexer([execution[0]])[0]
        if pos + HORIZON >= len(returns.index):
            continue
        forward = (1.0 + returns.iloc[pos + 1:pos + 1 + HORIZON]).prod(min_count=HORIZON) - 1.0
        frame = pd.DataFrame({"score": signal, "fwd": forward.reindex(signal.index)}).dropna()
        frame["sic2"] = sic2.reindex(frame.index).fillna("00")
        frame["date"] = decision
        frame["cik10"] = frame.index
        rows.append(frame.reset_index(drop=True))
    data = pd.concat(rows, ignore_index=True)
    data.to_csv(OUTPUT / "scores.csv.gz", index=False)

    def per_decision(d: pd.DataFrame) -> pd.DataFrame:
        out = []
        for when, g in d.groupby("date"):
            if len(g) < 30:
                continue
            ic = float(g.score.rank().corr(g.fwd.rank()))
            dec = pd.qcut(g.score.rank(method="first"), 10, labels=False)
            means = g.fwd.groupby(dec).mean()
            mono = float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman"))
            out.append({"date": when, "n": len(g), "ic": ic, "spread": float(means.iloc[-1] - means.iloc[0]),
                        "mono": mono})
        return pd.DataFrame(out)

    def boot(ics: np.ndarray, block: int = 4) -> float:
        mean, draws = ics.mean(), []
        for _ in range(4000):
            starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
            draws.append(np.concatenate([ics[i:i + block] for i in starts])[:len(ics)].mean() - mean)
        return float((np.abs(np.array(draws)) >= abs(mean)).mean())

    daily = per_decision(data)
    half = len(daily) // 2
    halves = [daily.iloc[:half], daily.iloc[half:]]
    placebo = []
    groups = [(g.score.rank().to_numpy(), g.fwd.rank().to_numpy()) for _, g in data.groupby("date") if len(g) >= 30]
    for _ in range(PLACEBO_RUNS):
        placebo.append(np.mean([np.corrcoef(rng.permutation(s), f)[0, 1] for s, f in groups]))
    placebo = np.array(placebo)
    loo = {code: float(per_decision(data[data.sic2 != code]).ic.mean())
           for code in data.sic2.value_counts().index[:15]}
    worst = min(loo, key=loo.get)

    full = {"decisions": int(len(daily)), "median_issuers": float(daily.n.median()),
            "mean_ic": float(daily.ic.mean()), "bootstrap_p": boot(daily.ic.to_numpy()),
            "decile_spread_13w": float(daily.spread.mean()),
            "decile_spread_annual": float((1 + daily.spread.mean()) ** 4 - 1),
            "monotonicity": float(daily.mono.mean())}
    criteria = {
        "density_median_issuers_at_least_100": full["median_issuers"] >= 100,
        "ic_positive_p_below_bar": full["mean_ic"] > 0 and full["bootstrap_p"] < BAR,
        "monotonicity_above_0.5": full["monotonicity"] > 0.5,
        "both_halves_ic_positive": all(h.ic.mean() > 0 for h in halves),
        "beats_placebo_95th": full["mean_ic"] > float(np.percentile(placebo, 95)),
        "min_leave_one_sic2_out_positive": loo[worst] > 0,
    }
    print(f"decisions {full['decisions']}, median issuers {full['median_issuers']:.0f}")
    print(f"mean IC {full['mean_ic']:+.4f} p {full['bootstrap_p']:.4f}  decile spread/13w "
          f"{full['decile_spread_13w']:+.2%} (ann {full['decile_spread_annual']:+.2%})  "
          f"monotonicity {full['monotonicity']:+.3f}")
    for i, h in enumerate(halves, 1):
        print(f"half {i}: {h.date.iloc[0].date()}..{h.date.iloc[-1].date()} IC {h.ic.mean():+.4f} "
              f"mono {h.mono.mean():+.3f} spread {h.spread.mean():+.2%}")
    print(f"placebo mean {placebo.mean():+.4f} p95 {np.percentile(placebo, 95):+.4f}; "
          f"worst leave-one-SIC2-out {loo[worst]:+.4f} (drop {worst})")
    for k, v in criteria.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    passes = all(criteria.values())
    print("SCREEN", "PASSES" if passes else "FAILS")
    (OUTPUT / "result.json").write_text(json.dumps({
        "dollar_match_rate": float(rate), "issuers_matched": int(matched.cik10.nunique()),
        "full": full, "halves_ic": [float(h.ic.mean()) for h in halves],
        "placebo_mean": float(placebo.mean()), "placebo_p95": float(np.percentile(placebo, 95)),
        "leave_one_sic2_out": loo, "criteria": criteria, "screen_passes": passes,
        "live_trading_enabled": False, "strategy_promotion_authorized": False}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
