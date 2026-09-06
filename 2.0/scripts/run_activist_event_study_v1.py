#!/usr/bin/env python3
"""Do Schedule 13D filings predict the subject company's returns?

Queue item A4, and the first non-earnings EVENT signal this project has tested.
Twelve families closed since Step 244 and eleven were continuous cross-sectional
scores -- one failure repeated, not twelve independent ones. This is a different
shape.

The control is what makes it worth running. Schedule 13G is the same five percent
threshold filed by PASSIVE holders: same disclosure, same mechanics, no intent to
influence. If activism is the mechanism, 13D shows an effect and 13G does not. If
both show it, the signal is "a large holder appeared" -- attention or liquidity,
not activism -- and it must be labelled that way. That control holds the filing
mechanics fixed, which a random-signal placebo cannot.

Subject companies are identified without fetching a single filing header: each
13D is indexed twice, once under the filer's CIK and once under the subject's,
with the same accession. Matching index CIKs against the roster isolates the
subject rows. Verified on accession 0001839882-24-000053 before the registry was
written.

Nothing here can be promoted.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/activist_event_registry_v1.json"
INDEXES = ROOT / "data/edgar_form_index_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_full_v1/recent_membership_readiness.csv"

# EDGAR relabelled these around 2025: "SC 13D" became "SCHEDULE 13D". The first
# version of this regex matched only the old label, found zero events after
# 2024-12-17, and truncated the evaluation window by nearly two years without
# erroring. Same class of failure as the 13F URL rename in Step 258, caught the
# same way -- by checking whether the parsed data looked like the raw data.
ROW = re.compile(
    r"^(SC 13[DG]|SCHEDULE 13[DG])\s{2,}(.+?)\s{2,}(\d+)\s{2,}(\d{4}-\d{2}-\d{2})\s{2,}(\S+)\s*$")


def canonical_form(raw: str) -> str:
    return "SC 13D" if raw.endswith("13D") else "SC 13G"


def read_events() -> pd.DataFrame:
    rows = []
    for path in sorted(INDEXES.glob("*_form.idx")):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = ROW.match(line)
            if match:
                form, name, cik, date, _ = match.groups()
                rows.append({"form": canonical_form(form), "company": name.strip(),
                             "cik10": str(cik).zfill(10), "filing_date": date})
    frame = pd.DataFrame(rows)
    frame["filing_date"] = pd.to_datetime(frame.filing_date)
    return frame.drop_duplicates(["form", "cik10", "filing_date"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/activist_event_v1")
    parser.add_argument("--draws", type=int, default=5000)
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    design = registry["design"]
    threshold = float(design["bonferroni_threshold"])

    events = read_events()
    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    members = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    sectors = members.drop_duplicates("cik10").set_index("cik10").sector

    # matching index CIKs against the roster isolates subject-company rows
    panel = set(returns.columns)
    subject = events[events.cik10.isin(panel)].copy()
    subject["sector"] = subject.cik10.map(sectors)

    sector_return = {}
    for sector in sectors.dropna().unique():
        names = [c for c in returns.columns if sectors.get(c) == sector]
        if len(names) >= 10:
            sector_return[sector] = returns[names].mean(axis=1, skipna=True)

    index = returns.index
    rows = []
    for horizon in design["event_windows_weeks"]:
        compounded = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
        valid = returns.notna().rolling(horizon).sum() >= horizon
        forward = compounded.where(valid).shift(-horizon)
        sector_forward = {
            s: ((1.0 + r.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0).shift(-horizon)
            for s, r in sector_return.items()}
        for form in ("SC 13D", "SC 13G"):
            block = subject[subject.form == form]
            for label, window in (("select", design["selection_window"]),
                                  ("evaluate", design["evaluation_window"])):
                inside = block[(block.filing_date >= window[0]) & (block.filing_date <= window[1])]
                abnormal, months = [], []
                for row in inside.itertuples(index=False):
                    later = index[index > row.filing_date]
                    if not len(later):
                        continue
                    week = later[0]
                    if week not in forward.index or row.cik10 not in forward.columns:
                        continue
                    own = forward.at[week, row.cik10]
                    if not np.isfinite(own):
                        continue
                    bench = sector_forward.get(row.sector)
                    if bench is None or week not in bench.index or not np.isfinite(bench.loc[week]):
                        continue
                    abnormal.append(float(own - bench.loc[week]))
                    months.append(row.filing_date.to_period("M"))
                if len(abnormal) < 100:
                    continue
                values = np.array(abnormal)
                # cluster the bootstrap by filing month: activist filings arrive in waves
                frame = pd.DataFrame({"a": values, "m": months})
                groups = [g.a.to_numpy() for _, g in frame.groupby("m")]
                rng = np.random.default_rng(20260906)
                means = []
                for _ in range(args.draws):
                    picked = rng.integers(0, len(groups), size=len(groups))
                    means.append(float(np.concatenate([groups[i] for i in picked]).mean()))
                means = np.array(means)
                rows.append({
                    "form": form, "window": label, "horizon_weeks": horizon,
                    "events": len(values), "months": len(groups),
                    "mean_abnormal_return": float(values.mean()),
                    "median_abnormal_return": float(np.median(values)),
                    "share_positive": float((values > 0).mean()),
                    "bootstrap_p": float(2 * min((means > 0).mean(), (means <= 0).mean())),
                    "clears_bonferroni": bool(2 * min((means > 0).mean(), (means <= 0).mean()) < threshold),
                })
    table = pd.DataFrame(rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "event_study.csv", index=False)
    subject.to_csv(out / "subject_events.csv", index=False)

    def clears(form: str, window: str) -> pd.DataFrame:
        return table[(table.form == form) & (table.window == window)
                     & table.clears_bonferroni & (table.mean_abnormal_return > 0)]

    d_sel, d_eval = clears("SC 13D", "select"), clears("SC 13D", "evaluate")
    g_sel, g_eval = clears("SC 13G", "select"), clears("SC 13G", "evaluate")

    if table.empty:
        verdict = "no form-window combination had enough events to measure"
    elif d_sel.empty and d_eval.empty and g_sel.empty and g_eval.empty:
        verdict = ("neither 13D nor 13G clears in either window. A4 closes. Thirteen families, and "
                   "the event shape fails too.")
    elif not d_sel.empty and not d_eval.empty and g_eval.empty:
        verdict = ("13D clears in BOTH windows and 13G does not: an activism effect, the first event "
                   "signal and the first genuinely different shape to survive here")
    elif not d_eval.empty and not g_eval.empty:
        verdict = ("both 13D and 13G clear recently. This is NOT activism -- a large holder appearing "
                   "is an attention or liquidity effect and must be labelled that way")
    else:
        verdict = "partial: see the table; the 13D-versus-13G contrast decides the interpretation"

    result = {"experiment": "activist_event_v1", "queue_item": "A4",
              "events_parsed": int(len(events)), "subject_events_in_panel": int(len(subject)),
              "by_form": subject.form.value_counts().to_dict(),
              "window": [str(subject.filing_date.min().date()), str(subject.filing_date.max().date())],
              "declared_trials": design["declared_trials"], "bonferroni_threshold": threshold,
              "rows": rows, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"index rows parsed {len(events):,} | subject events in panel {len(subject):,} "
          f"| {result['by_form']}")
    print(f"window {result['window'][0]} to {result['window'][1]}\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
