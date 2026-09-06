#!/usr/bin/env python3
"""FINRA short interest, acquired and tested in one pass.

Queue item A5, and the honest prior is written into the registry: this is the
continuous cross-sectional score shape, which has failed twelve times in a row.
It is run because the data is free and the orthogonality was measured rather than
assumed, not because there is reason to expect a different answer.

FINRA publishes twice monthly with a lag, so the point-in-time anchor is the
publication date rather than the settlement date, taken here as settlement plus
eight days. Getting that wrong would be a lookahead of about a week.
"""

from __future__ import annotations

import argparse
import io
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/short_interest_registry_v1.json"
CACHE = ROOT / "data/finra_short_interest_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v3/price_source_inventory.csv"
BASE = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{}.csv"
AGENT = "Portfolio Optimizer research <nicholasturangan@gmail.com>"
PUBLICATION_LAG_DAYS = 8


def settlement_dates(start: str, end: str) -> list[pd.Timestamp]:
    days = pd.date_range(start, end, freq="D")
    return [d for d in days if d.day in (14, 15, 16, 28, 29, 30, 31)]


def acquire() -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    frames = []
    for date in settlement_dates("2018-01-01", "2026-09-06"):
        stamp = date.strftime("%Y%m%d")
        target = CACHE / f"shrt{stamp}.csv.gz"
        if not target.is_file():
            try:
                request = urllib.request.Request(BASE.format(stamp), headers={"User-Agent": AGENT})
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = response.read()
            except Exception:  # noqa: BLE001 - most candidate dates are not settlement dates
                continue
            if len(payload) < 5000:
                continue
            import gzip
            target.write_bytes(gzip.compress(payload))
            time.sleep(0.3)
        import gzip
        text = gzip.decompress(target.read_bytes()).decode("utf-8", "ignore")
        # At least one FINRA file carries an unbalanced quote inside an issuer
        # name, which makes the C parser read to EOF and raise. These are
        # pipe-delimited files with no quoting convention, so quoting is disabled
        # outright rather than worked around per file.
        frame = pd.read_csv(io.StringIO(text), sep="|", low_memory=False,
                            quoting=3, on_bad_lines="skip")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/short_interest_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    threshold = float(registry["bonferroni_threshold"])
    windows = registry["windows"]

    raw = acquire()
    if raw.empty:
        raise SystemExit("no FINRA files acquired")
    raw["settlementDate"] = pd.to_datetime(raw.settlementDate, errors="coerce")
    raw = raw.dropna(subset=["settlementDate", "symbolCode"])
    raw["available_at"] = raw.settlementDate + pd.Timedelta(days=PUBLICATION_LAG_DAYS)

    import csv, re
    symbol_to_cik: dict[str, str] = {}
    with INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            match = (re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
                     or re.search(r"/([A-Za-z0-9.\-]+)/prices\.csv\.gz$", row["path"]))
            if match:
                symbol_to_cik.setdefault(match.group(1).upper(), row["cik10"])
    raw["cik10"] = raw.symbolCode.astype(str).str.upper().map(symbol_to_cik)
    matched = raw.dropna(subset=["cik10"])

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    matched = matched[matched.cik10.isin(returns.columns)]

    matched["days_to_cover"] = pd.to_numeric(matched.daysToCoverQuantity, errors="coerce")
    current = pd.to_numeric(matched.currentShortPositionQuantity, errors="coerce")
    previous = pd.to_numeric(matched.previousShortPositionQuantity, errors="coerce")
    volume = pd.to_numeric(matched.averageDailyVolumeQuantity, errors="coerce")
    matched["short_interest_change"] = current / previous.replace(0, np.nan) - 1.0
    matched["short_to_volume"] = current / volume.replace(0, np.nan)

    index = returns.index
    rows = []
    for signal in registry["declared_signals"]:
        for horizon in registry["declared_configurations"]["forward_horizon_weeks"]:
            compounded = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
            valid = returns.notna().rolling(horizon).sum() >= horizon
            forward = compounded.where(valid).shift(-horizon)
            for label, window in (("select", windows["selection"]), ("evaluate", windows["evaluation"])):
                block = matched[(matched.available_at >= window[0]) & (matched.available_at <= window[1])]
                ics = []
                for available, cohort in block.groupby("available_at"):
                    later = index[index > available]
                    if not len(later):
                        continue
                    week = later[0]
                    if week not in forward.index:
                        continue
                    names = [c for c in cohort.cik10 if c in forward.columns]
                    pair = pd.DataFrame({
                        "s": cohort.set_index("cik10")[signal].reindex(names).to_numpy(),
                        "f": forward.loc[week, names].to_numpy()}).dropna()
                    if len(pair) < 200:
                        continue
                    ics.append(float(pair.s.rank().corr(pair.f.rank())))
                if len(ics) < 8:
                    continue
                values = np.array(ics)
                rows.append({
                    "signal": signal, "horizon": horizon, "window": label,
                    "cohorts": len(values), "mean_ic": float(values.mean()),
                    "t_stat": float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values)))),
                    "p_value": float(stats.ttest_1samp(values, 0.0).pvalue),
                    "share_positive": float((values > 0).mean()),
                })
    table = pd.DataFrame(rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "information_coefficients.csv", index=False)

    survivors = []
    for signal in registry["declared_signals"]:
        for horizon in registry["declared_configurations"]["forward_horizon_weeks"]:
            s = table[(table.signal == signal) & (table.horizon == horizon) & (table.window == "select")]
            e = table[(table.signal == signal) & (table.horizon == horizon) & (table.window == "evaluate")]
            if s.empty or e.empty:
                continue
            if (s.iloc[0].p_value < threshold and np.sign(s.iloc[0].mean_ic) == np.sign(e.iloc[0].mean_ic)
                    and e.iloc[0].p_value < 0.05):
                survivors.append(f"{signal}_h{horizon}")

    if table.empty:
        verdict = "no configuration produced enough cohorts to measure"
    elif not survivors and not (table[table.window == "select"].p_value < threshold).any():
        verdict = ("nothing clears in selection. A5 closes. The free tier of the queue is exhausted, "
                   "and the honest options are paid data or stopping the search.")
    elif not survivors:
        verdict = "clears in selection but does not repeat out of sample; in-sample, recorded and closed"
    else:
        verdict = f"survives selection and evaluation at {', '.join(survivors)}"

    result = {"experiment": "short_interest_v1", "queue_item": "A5",
              "files_used": len(list(CACHE.glob("*.csv.gz"))),
              "rows_raw": int(len(raw)), "rows_matched_to_panel": int(len(matched)),
              "symbol_match_rate": round(len(matched) / max(1, len(raw)), 4),
              "window": [str(matched.available_at.min().date()), str(matched.available_at.max().date())],
              "declared_trials": registry["declared_configurations"]["total_trials"],
              "bonferroni_threshold": threshold, "rows": rows, "survivors": survivors,
              "verdict": verdict, "honest_prior": registry["honest_prior"],
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"files {result['files_used']} | raw rows {result['rows_raw']:,} | matched {result['rows_matched_to_panel']:,} "
          f"({result['symbol_match_rate']:.1%}) | {result['window'][0]} to {result['window'][1]}\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
