#!/usr/bin/env python3
"""Screen every saved return path for a third leg uncorrelated with the two we hold.

Step 275 took the effective number of independent bets from about 1.15 to about 2
by putting valuation next to growth, and that one step did more for risk-adjusted
return than several hundred steps of retuning did. `IR = IC * sqrt(BR)` says the
next unit of breadth is worth roughly another 22% on IR at unchanged IC, with no
better signal required. So the question worth asking is not "what returns more"
but "what is uncorrelated with both of these".

Valuation was found by clustering these same saved paths, so the asset is already
known to contain things the dashboard does not. This screens all of it directly:
correlate every path against both legs, keep the ones below 0.3 on both, and
report what they are and whether they stand up on their own.

This is a screen, not a result. Everything it returns was selected on the same
window as everything else here, most of it is a variant of something already
held under a different filename, and a low correlation measured once on 2023-2026
is exactly the quantity Step 276 put on a clock because it may not be real. The
output is a shortlist to test, and nothing in it is evidence of anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "evidence/third_leg_screen_v1"
VALUATION = ROOT / "evidence/valuation_revival_v1/path__breadth20__50bps.csv"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")
MIN_WEEKS = 120
CORRELATION_GATE = 0.30


def load_paths() -> dict[str, pd.Series]:
    """Every saved weekly return path long enough to correlate. Mirrors Step 273."""
    series: dict[str, pd.Series] = {}
    for path in sorted(ROOT.glob("evidence/**/*.csv")):
        name = path.name.lower()
        if not any(k in name for k in ("path", "candidate")):
            continue
        # "candidate_weights.csv" matches the keyword filter and is a weights table,
        # not a return series. Read as returns it produced a 33,532% CAGR at Sharpe
        # 294 with zero drawdown and sailed through the correlation gate, because
        # nothing downstream asked whether the number could mean anything.
        if "weight" in name or "holding" in name or "position" in name:
            continue
        if path.stat().st_size > 20_000_000:
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty or len(frame.columns) < 2:
            continue
        column = frame.columns[0]
        try:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
        except Exception:
            continue
        frame = frame.dropna(subset=[column]).set_index(column).sort_index()
        frame = frame[~frame.index.duplicated(keep="first")]
        numeric = [c for c in frame.columns if frame[c].dtype.kind == "f"]
        if not numeric:
            continue
        value = frame[numeric[0]].dropna()
        if len(value) < MIN_WEEKS or value.abs().median() > 0.2 or value.abs().max() > 2.0:
            continue
        weekly = value.resample("W-FRI").apply(lambda x: (1.0 + x).prod() - 1.0)
        if len(weekly) < MIN_WEEKS:
            continue
        # A weekly return series has a bounded plausible shape. A 1020% CAGR at
        # Sharpe 13.8 is a cumulative equity curve or a mislabelled column, not a
        # strategy, and a series with no drawdown at all is not a return series.
        m = metrics(weekly)
        if not m or not np.isfinite(m["cagr"]):
            continue
        if m["cagr"] > 2.0 or m["sharpe"] > 5.0 or m["max_drawdown"] >= -1e-9:
            continue
        series[str(path.relative_to(ROOT))] = weekly
    return series


def metrics(returns: pd.Series) -> dict[str, float]:
    if len(returns) < 20:
        return {}
    growth = float((1.0 + returns).prod())
    years = len(returns) / 52.0
    cagr = growth ** (1.0 / years) - 1.0 if growth > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + returns).cumprod()
    return {
        "cagr": cagr, "sharpe": (cagr / vol) if vol > 0 else float("nan"), "volatility": vol,
        "max_drawdown": float((curve / curve.cummax() - 1.0).min()), "weeks": len(returns),
    }


def main() -> int:
    paths = load_paths()
    valuation = load_paths_single(VALUATION)
    growth = pick_growth(paths)
    if valuation is None or growth is None:
        print("cannot locate both legs; screen not run")
        return 1

    rows = []
    for name, series in paths.items():
        joined = pd.concat({"x": series, "v": valuation, "g": growth}, axis=1).dropna()
        if len(joined) < MIN_WEEKS:
            continue
        cv = float(joined.x.corr(joined.v))
        cg = float(joined.x.corr(joined.g))
        if not np.isfinite(cv) or not np.isfinite(cg):
            continue
        # A path perfectly correlated with a leg IS that leg under another filename.
        if max(abs(cv), abs(cg)) > 0.999:
            continue
        m = metrics(joined.x)
        if not m:
            continue
        post = joined.x[joined.index >= BREAK]
        pre = joined.x[joined.index < BREAK]
        rows.append({
            "path": name, "corr_valuation": cv, "corr_growth": cg,
            "max_abs_corr": max(abs(cv), abs(cg)),
            "passes_gate": bool(max(abs(cv), abs(cg)) < CORRELATION_GATE),
            **m,
            "pre_break_cagr": metrics(pre).get("cagr", float("nan")),
            "post_break_cagr": metrics(post).get("cagr", float("nan")),
        })

    frame = pd.DataFrame(rows).sort_values("max_abs_corr")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "screen.csv", index=False)

    passing = frame[frame.passes_gate]
    # A third leg is only worth anything if it also makes money on its own. A path
    # uncorrelated with both legs because it returns nothing is not diversification.
    useful = passing[(passing.cagr > 0.10) & (passing.sharpe > 0.5)]

    print(f"paths screened: {len(frame)}   below {CORRELATION_GATE} on both legs: {len(passing)}")
    print(f"of those, above 10% CAGR and 0.5 Sharpe: {len(useful)}\n")
    if len(useful):
        show = useful.sort_values("sharpe", ascending=False).head(12)
        for _, r in show.iterrows():
            print(f"  {r['cagr']:7.2%} cagr  sh {r['sharpe']:5.2f}  dd {r['max_drawdown']:7.2%}  "
                  f"corr v {r['corr_valuation']:+.3f} g {r['corr_growth']:+.3f}  "
                  f"{r['path'].replace('evidence/','')[:64]}")
    else:
        print("  nothing clears both the correlation gate and a minimum standalone bar.")

    result = {
        "paths_screened": len(frame),
        "correlation_gate": CORRELATION_GATE,
        "passing_correlation_gate": len(passing),
        "passing_and_standalone_viable": len(useful),
        "distinct_directories_in_shortlist": sorted({p.split("/")[1] for p in useful.path}) if len(useful) else [],
        "this_is_a_screen_not_a_result": True,
        "every_path_was_selected_on_the_same_window": True,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("\n" + json.dumps(result, indent=2, sort_keys=True))
    return 0


def load_paths_single(path: Path):
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    column = frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    frame = frame.dropna(subset=[column]).set_index(column).sort_index()
    numeric = [c for c in frame.columns if frame[c].dtype.kind == "f"]
    return frame[numeric[0]].dropna() if numeric else None


GROWTH = "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv"


def pick_growth(paths: dict[str, pd.Series]):
    """The growth leg, named explicitly rather than matched by substring.

    The first version searched for a substring and fell through to the first
    match, which was `path_growth__adverse__50bps.csv` -- the adverse stress
    scenario, not the base case. It reported the growth leg at 22.48% CAGR
    instead of 40.64% and nothing complained, because a substring match cannot
    tell a strategy from a stress test of it.
    """
    if GROWTH not in paths:
        raise KeyError(f"the growth leg {GROWTH} is not among the loaded paths")
    return paths[GROWTH]


if __name__ == "__main__":
    raise SystemExit(main())
