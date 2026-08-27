#!/usr/bin/env python3
"""Can a regime signal cut the drawdown without eating the return?

Step 191 recorded the volatility-tilt gate as binding on data availability: above
the neutral band it demands bear-market evidence, and the SEC price panel starts
2022-12. That evidence cannot be produced for those books. It can be produced for
the mechanism, on ETFs, across four bear markets.

One coverage fact shaped the whole design. The repository's existing regime
features are built on the VIX term-structure slope, and VIX3M starts 2009-09-18 -
after both of the regimes the gate most needs. So this uses VIX level and the
Chicago Fed NFCI, which reach back to 1990 and 1971 respectively. That is a weaker
signal, and it is the only one that can be tested honestly here.

Nothing is tuned: both thresholds and both gated exposures are reported.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.trial_ledger import Trial, TrialLedger  # noqa: E402
CONFIG = ROOT / "config/regime_exposure_overlay_v1.json"
OUTPUT = ROOT / "evidence/regime_exposure_overlay_v1"

REGIMES = {
    "dotcom_2000_2002": ("2000-03-01", "2002-10-31"),
    "gfc_2007_2009": ("2007-10-01", "2009-03-31"),
    "covid_2020": ("2020-02-01", "2020-04-30"),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "recent_2023_2026": ("2023-01-01", "2026-08-14"),
}


def metrics(net: pd.Series, periods: int = 252) -> dict:
    v = net.dropna()
    if len(v) < periods:
        return {"observations": int(len(v)), "insufficient": True}
    w = (1 + v).cumprod()
    sd = v.std(ddof=1)
    return {
        "observations": int(len(v)),
        "cagr": float(w.iloc[-1] ** (periods / len(v)) - 1),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_1y": float((w / w.shift(periods) - 1).min()),
    }


def build_gates(index: pd.DatetimeIndex, spec: dict, regime_dir: Path) -> pd.DataFrame:
    cboe = pd.read_csv(regime_dir / "cboe_observations.csv", parse_dates=["observation_date"])
    vix = (cboe[cboe["series_id"] == "VIX"]
           .set_index("observation_date")["value"].astype(float).sort_index())
    fred = pd.read_csv(regime_dir / "fred_observations.csv", parse_dates=["observation_date"])
    nfci = (fred[fred["series_id"] == "NFCI"]
            .set_index("observation_date")["value"].astype(float).sort_index())

    lags = spec["publication_lags"]
    # Shift the index forward by the publication lag, then forward-fill onto
    # trading days, so a value is only ever visible after it could be known.
    vix_known = vix.copy()
    vix_known.index = vix_known.index + pd.Timedelta(days=1)
    vix_daily = vix_known.reindex(vix_known.index.union(index)).ffill().reindex(index)

    nfci_known = nfci.copy()
    nfci_known.index = nfci_known.index + pd.Timedelta(days=8)
    nfci_daily = nfci_known.reindex(nfci_known.index.union(index)).ffill().reindex(index)

    frame = pd.DataFrame({"vix": vix_daily, "nfci": nfci_daily}, index=index)
    for threshold in spec["gates"][0]["thresholds"]:
        # Trailing five-year percentile of the VIX against its own history, so the
        # threshold is not calibrated on the future.
        rolling = frame["vix"].rolling(1260, min_periods=252)
        cutoff = rolling.quantile(threshold)
        frame[f"vix_p{int(threshold * 100)}"] = (frame["vix"] > cutoff).astype(float)
    frame["nfci_positive"] = (frame["nfci"] > 0).astype(float)
    return frame


def apply_overlay(book: pd.Series, fire: pd.Series, gated_exposure: float,
                  delay: int, cost_bps: float) -> pd.Series:
    exposure = np.where(fire.fillna(0.0) > 0, gated_exposure, 1.0)
    exposure = pd.Series(exposure, index=book.index).shift(delay).fillna(1.0)
    turnover = exposure.diff().abs().fillna(0.0)
    return book * exposure - turnover * cost_bps / 1e4


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]

    raw = pd.read_csv(ROOT / config["price_source"], parse_dates=["observation_date"])
    prices = raw.pivot_table(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    returns = prices.pct_change()
    start = spec["evaluation_start"]

    gates = build_gates(prices.index, spec, ROOT / config["regime_source"])

    books = {
        "SPY": returns["SPY"],
        "equal_weight_etf_universe": returns.mean(axis=1),
    }
    trend_path = ROOT / "evidence/cross_asset_trend_extended_v2/result.json"
    books_note = "cross_asset_trend_sleeve omitted: it is rebuilt by its own script and not stored as a series"
    if trend_path.exists():
        books_note = books_note  # keep the omission explicit rather than silently dropping the book

    gate_definitions = {
        "vix_p80": gates["vix_p80"],
        "vix_p90": gates["vix_p90"],
        "nfci_positive": gates["nfci_positive"],
        "vix_p80_or_nfci": ((gates["vix_p80"] + gates["nfci_positive"]) > 0).astype(float),
        "vix_p80_and_nfci": ((gates["vix_p80"] + gates["nfci_positive"]) > 1).astype(float),
    }

    results: dict[str, dict] = {}
    for book_name, book in books.items():
        baseline = book.loc[start:]
        results[book_name] = {"baseline": metrics(baseline), "gated": {}}
        for gate_name, fire in gate_definitions.items():
            for gated_exposure in spec["exposure_when_gated"]:
                net = apply_overlay(
                    book, fire, gated_exposure,
                    spec["execution_delay_days"], spec["cost_bps_per_unit_turnover"],
                ).loc[start:]
                key = f"{gate_name}_to_{int(gated_exposure * 100)}pct"
                entry = metrics(net)
                entry["regimes"] = {}
                for regime, (lo, hi) in REGIMES.items():
                    window, base_window = net.loc[lo:hi], baseline.loc[lo:hi]
                    if len(window) > 20:
                        entry["regimes"][regime] = {
                            "gated": float((1 + window).prod() - 1),
                            "baseline": float((1 + base_window).prod() - 1),
                        }
                results[book_name]["gated"][key] = entry

    fire_rates = {name: float(series.loc[start:].mean()) for name, series in gate_definitions.items()}

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_start": start,
        "gate_fire_rate": fire_rates,
        "books": results,
        "omissions": books_note,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    # Register every variant evaluated, so this program's contribution to the
    # project's trial count is exact rather than reconstructed later.
    ledger = TrialLedger(ROOT / "data/trial_ledger_v1/trials.jsonl")
    already = ledger.count(family="regime_overlay")
    if already == 0:
        registered = ledger.append([
            Trial(
                family="regime_overlay",
                experiment=config["experiment"],
                variant=f"{book_name}::{key}",
                objective="sharpe_and_max_drawdown",
                dataset=config["price_source"],
                outcome=("improved_drawdown_without_material_return_loss"
                         if (entry["gated"][key]["max_drawdown"] > entry["baseline"]["max_drawdown"]
                             and entry["gated"][key]["cagr"] > entry["baseline"]["cagr"] - 0.005)
                         else "rejected"),
                metric=float(entry["gated"][key]["sharpe"]),
            )
            for book_name, entry in results.items()
            for key in entry["gated"]
        ])
        result["trials_registered"] = registered
    else:
        result["trials_registered"] = 0
        result["trial_registration_note"] = f"family already holds {already} trials; ledger is append-only"
    result["trial_ledger_total"] = ledger.count()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print("gate fire rate (share of days gated):")
    for name, rate in fire_rates.items():
        print(f"  {name:22s}{rate*100:6.1f}%")
    for book_name, entry in results.items():
        base = entry["baseline"]
        print(f"\n=== {book_name} ===")
        print(f"  {'baseline':34s} CAGR {base['cagr']*100:7.2f}%  Sh {base['sharpe']:5.2f}  maxDD {base['max_drawdown']*100:7.2f}%")
        for key, gated in entry["gated"].items():
            print(f"  {key:34s} CAGR {gated['cagr']*100:7.2f}%  Sh {gated['sharpe']:5.2f}  maxDD {gated['max_drawdown']*100:7.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
