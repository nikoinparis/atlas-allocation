#!/usr/bin/env python3
"""Complete the closed-family audit: the four whose scores had to be recovered.

Step 298 measured ten families and declared four out of scope because their raw
cross-sectional scores were never saved. Three are recoverable from disk after
all and the fourth is computable, so the audit gets finished rather than left
with a hole in it.

    SUE / PEAD              131,169 issuer-quarter scores, already a panel
    10-K language           8,327 filings; jaccard, the measure Step 255 found
                            usable once cosine proved degenerate at IQR 0.0020
    13F ownership change    rebuilt from 110.3M holding rows as quarter-on-
                            quarter change in aggregate institutional value
    fractional differencing recomputed at order 0.3, the order Step 268 found
                            retains 0.856 of the price level's memory

Each is measured at ITS OWN decision cadence -- 13 weeks quarterly, 4 weeks
weekly. Step 298 used one horizon because its ten families were all weekly;
imposing that on a quarterly signal would understate it.

The density guard from Step 298 applies: a signal non-zero in under half its
cells cannot be read on deciles at all, and saying so is the point of the guard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import run_closed_family_monotonicity_v1 as base

OUTPUT = ROOT / "evidence/remaining_family_monotonicity_v1"
SUE = ROOT / "evidence/extended_sue_panel_v1/sue_panel.csv.gz"
LANG = ROOT / "evidence/filing_language_change_v1/similarity.csv"
HOLDINGS = ROOT / "evidence/institutional_linkage_v1/holdings.parquet"
CUSIP_MAP = ROOT / "evidence/institutional_linkage_v1/cusip_to_cik10.csv"
BONFERRONI = 0.05 / 14          # ten from Step 298 plus these four


def pad(series: pd.Series) -> pd.Series:
    return series.astype("int64").astype(str).str.zfill(10)


def as_weekly_panel(long: pd.DataFrame, weeks: pd.DatetimeIndex,
                    date_col: str, value_col: str) -> pd.DataFrame:
    """Stamp dated per-issuer scores onto the weekly grid, held until replaced."""
    long = long.dropna(subset=[date_col, "cik10", value_col])
    positions = np.clip(weeks.searchsorted(long[date_col].to_numpy(), side="left"),
                        0, len(weeks) - 1)
    long = long.assign(week=weeks[positions])
    wide = long.groupby(["week", "cik10"])[value_col].last().unstack("cik10")
    return wide.reindex(weeks).ffill()


def forward_frame(returns: pd.DataFrame, horizon: int) -> pd.DataFrame:
    return (1.0 + returns.fillna(0.0)).rolling(horizon).apply(
        np.prod, raw=True).shift(-horizon) - 1.0


def main() -> int:
    rng = np.random.default_rng(20260910)
    prices, returns = base.load_panel()
    weeks = returns.index
    signals: dict[str, tuple[pd.DataFrame, int]] = {}

    # 1. SUE / PEAD -- quarterly
    try:
        sue = pd.read_csv(SUE)
        sue["cik10"] = pad(sue.cik10)
        sue["decision_at"] = pd.to_datetime(sue.decision_at, utc=True)
        panel = as_weekly_panel(sue, weeks, "decision_at", "standardized_unexpected_earnings")
        signals["sue_pead"] = (panel, 13)
        print(f"SUE rebuilt: {panel.shape[1]} issuers")
    except Exception as error:                       # noqa: BLE001
        print(f"SUE unavailable: {type(error).__name__}: {error}")

    # 2. 10-K language -- annual, jaccard. Expected to be too thin; measured anyway.
    try:
        lang = pd.read_csv(LANG)
        lang["cik10"] = pad(lang.cik10)
        lang["filing_date"] = pd.to_datetime(lang.filing_date, utc=True)
        # Low jaccard means the language changed a lot, which is the signal Step 255
        # framed; sign is handled by the IC rather than flipped here.
        panel = as_weekly_panel(lang, weeks, "filing_date", "jaccard__full")
        signals["filing_language_jaccard"] = (panel, 13)
        print(f"10-K language rebuilt: {panel.shape[1]} issuers")
    except Exception as error:                       # noqa: BLE001
        print(f"10-K language unavailable: {type(error).__name__}: {error}")

    # 3. 13F institutional ownership change -- quarterly
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(HOLDINGS, columns=["CUSIP", "PERIODOFREPORT", "VALUE"])
        holdings = table.to_pandas()
        mapping = pd.read_csv(CUSIP_MAP, dtype=str)
        cusip_col = next(c for c in mapping.columns if "cusip" in c.lower())
        cik_col = next(c for c in mapping.columns if "cik" in c.lower())
        lookup = dict(zip(mapping[cusip_col].astype(str), mapping[cik_col].astype(str).str.zfill(10)))
        holdings["cik10"] = holdings.CUSIP.astype(str).map(lookup)
        holdings = holdings.dropna(subset=["cik10"])
        holdings["VALUE"] = pd.to_numeric(holdings.VALUE, errors="coerce")
        holdings["period"] = pd.to_datetime(holdings.PERIODOFREPORT, utc=True, errors="coerce")
        holdings = holdings.dropna(subset=["VALUE", "period"])
        totals = holdings.groupby(["period", "cik10"]).VALUE.sum().unstack("cik10").sort_index()
        change = (totals / totals.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
        long = change.stack().rename("change").reset_index()
        # 13F is due 45 days after quarter end; use the deadline, never the period end.
        long["available_at"] = long.period + pd.Timedelta(days=45)
        panel = as_weekly_panel(long, weeks, "available_at", "change")
        signals["institutional_ownership_change"] = (panel, 13)
        print(f"13F ownership change rebuilt: {panel.shape[1]} issuers")
    except Exception as error:                       # noqa: BLE001
        print(f"13F unavailable: {type(error).__name__}: {error}")

    # 4. Fractional differentiation -- weekly, order 0.3
    try:
        order, width = 0.3, 60
        weights, w = [1.0], 1.0
        for k in range(1, width):
            w *= -(order - k + 1) / k
            weights.append(w)
        weights = np.array(weights)
        logp = np.log(prices.where(prices > 0))
        frac = logp.rolling(width).apply(lambda x: float(np.dot(weights[::-1], x)), raw=True)
        signals["fractional_differentiation"] = (frac.shift(1), 4)
        print("fractional differencing recomputed at order 0.3")
    except Exception as error:                       # noqa: BLE001
        print(f"fracdiff unavailable: {type(error).__name__}: {error}")

    results = {}
    for name, (frame, horizon) in signals.items():
        base.HORIZON = horizon
        forward = forward_frame(returns, horizon)
        aligned = frame.reindex(columns=returns.columns)
        results[name] = measure_at(aligned, forward, horizon, rng)

    print(f"\nremaining closed families, own-cadence horizons, Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'family':32s} {'hz':>3s} {'n':>4s} {'dens':>6s} {'mean IC':>9s} {'t':>7s} "
          f"{'p':>8s} {'decile spread':>14s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:32s} {r['horizon']:>3d} {r['decisions']:>4d}   too few decisions to measure")
            continue
        flag = " *" if r["bootstrap_p"] < BONFERRONI else ""
        if not r["deciles_interpretable"]:
            flag += "  <- SPARSE"
        print(f"{name:32s} {r['horizon']:>3d} {r['decisions']:>4d} {r['nonzero_density']:6.1%} "
              f"{r['mean_ic']:+9.4f} {r['t_stat']:+7.2f} {r['bootstrap_p']:8.4f} "
              f"{r['decile_spread_annualised']:+13.2%} {r['monotonicity']:+9.2f}{flag}")

    usable = {k: v for k, v in results.items() if not v.get("inconclusive")}
    clearing = [k for k, v in usable.items() if v["bootstrap_p"] < BONFERRONI]
    monotone = [k for k, v in usable.items()
                if abs(v["monotonicity"]) > 0.5 and v["deciles_interpretable"]]
    print(f"\nfamilies measured: {len(usable)} of {len(results)} attempted")
    print(f"clearing Bonferroni {BONFERRONI:.4f}: {len(clearing)}" + (f" -- {clearing}" if clearing else ""))
    print(f"monotonicity above 0.5 with interpretable deciles: {len(monotone)}"
          + (f" -- {monotone}" if monotone else ""))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "monotonicity.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "bonferroni_bar": BONFERRONI, "results": results,
        "clearing_bonferroni": clearing, "monotonic_above_half": monotone,
        "horizon_rule": "each signal at its own decision cadence: 13 weeks quarterly, 4 weeks weekly",
        "completes": "the audit begun in Step 298",
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


def measure_at(signal: pd.DataFrame, forward: pd.DataFrame, horizon: int, rng) -> dict:
    saved = base.HORIZON
    base.HORIZON = horizon
    try:
        out = base.measure(signal, forward, rng)
    finally:
        base.HORIZON = saved
    out["horizon"] = horizon
    return out


if __name__ == "__main__":
    raise SystemExit(main())
