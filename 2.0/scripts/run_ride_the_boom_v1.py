#!/usr/bin/env python3
"""Hold the boom-sensitive riser book while its boom is on; step aside to SPY when it breaks.

Pre-registered in config/ride_the_boom_registry_v1.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PATHS = ROOT / "evidence/rising_stocks_program_v1/all_paths.csv.gz"
OUTPUT = ROOT / "evidence/ride_the_boom_v1"
COST = 50 / 1e4
HALVES = {"2013-2019": ("2013-01-01", "2019-12-31"), "2020-2026": ("2020-01-01", "2026-12-31"),
          "full": ("2013-01-01", "2026-12-31")}


def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    w = (1 + r).cumprod()
    cagr = float(w.iloc[-1] ** (52 / len(r)) - 1)
    vol = float(r.std() * np.sqrt(52))
    return {"cagr": cagr, "vol": vol, "sharpe": cagr / vol, "max_dd": float((w / w.cummax() - 1).min())}


def switcher(riser: pd.Series, spy: pd.Series, rule: str) -> tuple[pd.Series, float]:
    wr, ws = (1 + riser).cumprod(), (1 + spy).cumprod()
    ma = wr.rolling(40).mean()
    out, state, switches = [], None, 0
    for i in range(52, len(riser) - 1):
        if (i - 52) % 4 == 0 or state is None:
            if rule == "relative":
                want = "riser" if wr.iloc[i] / wr.iloc[i - 52] > ws.iloc[i] / ws.iloc[i - 52] else "spy"
            else:
                want = "riser" if wr.iloc[i] > ma.iloc[i] else "spy"
            cost = 2 * COST if state is not None and want != state else 0.0
            switches += cost > 0
            state = want
        else:
            cost = 0.0
        r = riser.iloc[i + 1] if state == "riser" else spy.iloc[i + 1]
        out.append((riser.index[i + 1], (1 + r) * (1 - cost) - 1))
    s = pd.Series(dict(out))
    return s, switches / (len(s) / 52)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    riser = pd.read_csv(PATHS, index_col=0, parse_dates=True)["A_steady_riser|52w|none"]
    spy = yf.download("SPY", start="2010-01-01", auto_adjust=True, progress=False)["Close"].squeeze()
    spy.index = pd.to_datetime(spy.index).tz_localize(None)
    spy = spy.resample("W-FRI").last().pct_change().reindex(riser.index)
    frame = pd.DataFrame({"riser": riser, "spy": spy}).dropna()

    t1, s1 = switcher(frame.riser, frame.spy, "relative")
    t2, s2 = switcher(frame.riser, frame.spy, "own_trend")
    idx = t2.index
    series = {
        "SPY": frame.spy.reindex(idx),
        "riser book always": frame.riser.reindex(idx),
        "50/50 SPY + riser, always": (0.5 * frame.spy + 0.5 * frame.riser).reindex(idx),
        "T1 relative strength switch": t1,
        "T2 own-trend switch": t2,
        "T3 50% SPY + 50% T2": 0.5 * frame.spy.reindex(idx) + 0.5 * t2,
    }
    result = {"switches_per_year": {"T1": s1, "T2": s2}, "rows": {}}
    print(f"{'':30s}" + "".join(f"{h:>36s}" for h in HALVES))
    for name, r in series.items():
        row = {h: metrics(r[(r.index >= a) & (r.index <= b)]) for h, (a, b) in HALVES.items()}
        result["rows"][name] = row
        print(f"{name:30s}" + "".join(
            f"   {row[h]['cagr']:+6.1%} S{row[h]['sharpe']:5.2f} DD{row[h]['max_dd']:+6.1%}" for h in HALVES))
    spy_row, mix = result["rows"]["SPY"], result["rows"]["50/50 SPY + riser, always"]
    verdicts = {}
    for name in ("T1 relative strength switch", "T2 own-trend switch", "T3 50% SPY + 50% T2"):
        row = result["rows"][name]
        verdicts[name] = {
            "sharpe_ge_spy_both_halves": all(row[h]["sharpe"] >= spy_row[h]["sharpe"] for h in ("2013-2019", "2020-2026")),
            "cagr_ge_spy_full": row["full"]["cagr"] >= spy_row["full"]["cagr"],
            "max_dd_ge_-35": row["full"]["max_dd"] >= -0.35,
            "beats_always_mix_sharpe": row["full"]["sharpe"] > mix["full"]["sharpe"],
        }
        verdicts[name]["passes"] = all(verdicts[name].values())
        print(name, verdicts[name])
    result["verdicts"] = verdicts
    print("switches per year", {k: round(v, 1) for k, v in result["switches_per_year"].items()})
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=1) + "\n")
    pd.DataFrame(series).to_csv(OUTPUT / "paths.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
