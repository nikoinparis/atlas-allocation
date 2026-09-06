#!/usr/bin/env python3
"""Family A of the breadth-first registry: seasonal momentum on the 35-ETF panel.

The Heston-Sadka effect is that an asset's return in a given calendar month
carries information about its return in that same calendar month in later years.
It reached this project through the OSAP screen as one of the few published
anomalies with near-zero correlation to everything already held, and as one of
the fewer still that needs no data this project does not have.

It is registered on the ETF panel and not on single stocks for a stated reason:
the years 2-5 window needs five years of history before it yields one
observation, and the single-stock panel holds 3.8. Registering it there anyway
would have produced a signal that is mostly missing values.

Six configurations, fixed in config/breadth_first_signal_registry_v1.json before
this script existed. The breadth gate is evaluated before the return gate, so a
configuration that duplicates existing exposure is rejected whatever it earned.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/breadth_first_signal_registry_v1.json"
GGG = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
OUTPUT = ROOT / "evidence/seasonal_momentum_breadth_v1"
COSTS_BPS = [0, 10, 50, 100]
CASH = "cash::USD"

EXISTING = {
    "return_first_60_40_blend": "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv",
    "past_only_consensus_selector": "evidence/exhaustive_return_first_discovery_batch_66/"
                                    "retrospective_ceiling_adversarial/past_only_selector_weights.csv",
}
EXISTING_PATHS = {
    "cash_conversion_sleeve_b20": "evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv",
    "growth_leader_sleeve": "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv",
}


def seasonal_signal(monthly: pd.DataFrame, low: int, high: int) -> pd.DataFrame:
    """Mean return in this calendar month across years `low`..`high` back, known at t."""
    frames = [monthly.shift(12 * year) for year in range(low, high + 1)]
    stacked = pd.concat(frames, keys=range(low, high + 1))
    return stacked.groupby(level=1).mean().reindex(monthly.index)


def build_weights(signal: pd.DataFrame, construction: str) -> pd.DataFrame:
    ranks = signal.rank(axis=1, ascending=False)
    counts = signal.notna().sum(axis=1)
    weights = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    if construction.startswith("top_"):
        n = int(construction.split("_")[1])
        weights = weights.mask(ranks <= n, 1.0 / n).where(ranks <= n, 0.0)
    else:
        n = 3
        low = signal.rank(axis=1, ascending=True)
        weights = weights.mask(ranks <= n, 1.0 / n).where(ranks <= n, 0.0)
        weights = weights - (low <= n).astype(float) / n
    weights[counts < 10] = 0.0
    return weights.fillna(0.0)


def evaluate(weights: pd.DataFrame, monthly: pd.DataFrame, cost_bps: float) -> pd.Series:
    held = weights.shift(1).fillna(0.0)                      # decide at t, earn over t+1
    gross = (held * monthly).sum(axis=1)
    turnover = 0.5 * (held - held.shift(1).fillna(0.0)).abs().sum(axis=1)
    net = gross - turnover * cost_bps / 10000.0
    # Before the lookback window fills there is no book at all. Counting those months
    # as flat returns inflates the sample and drags every metric toward zero, which
    # would have made the 6-10 year configurations look like they had the same 260
    # months of evidence as the 2-5 year ones.
    return net.where(held.abs().sum(axis=1) > 0)


def metrics(returns: pd.Series) -> dict[str, float]:
    r = returns.dropna()
    if len(r) < 12:
        return {"months": int(len(r))}
    wealth = float((1 + r).prod())
    years = len(r) / 12.0
    vol = float(r.std(ddof=1) * np.sqrt(12))
    curve = (1 + r).cumprod()
    return {
        "months": int(len(r)),
        "cagr": wealth ** (1 / years) - 1,
        "annual_volatility": vol,
        "sharpe_zero_rf": float(r.mean() / r.std(ddof=1) * np.sqrt(12)) if r.std(ddof=1) > 0 else 0.0,
        "max_drawdown": float((curve / curve.cummax() - 1).min()),
        "positive_month_share": float((r > 0).mean()),
    }


def existing_monthly(prices: pd.DataFrame) -> dict[str, pd.Series]:
    out = {}
    for name, rel in EXISTING.items():
        w = pd.read_csv(ROOT / rel, index_col=0)
        w.index = pd.to_datetime(w.index)
        w = w.drop(columns=[CASH], errors="ignore")
        shared = [c for c in w.columns if c in prices.columns]
        weekly = prices[shared].pct_change()
        aligned = w[shared].reindex(weekly.index).ffill().fillna(0.0)
        out[name] = (1 + (aligned.shift(1) * weekly).sum(axis=1)).resample("ME").prod() - 1
    for name, rel in EXISTING_PATHS.items():
        f = pd.read_csv(ROOT / rel)
        col = "Date" if "Date" in f else f.columns[0]
        f[col] = pd.to_datetime(f[col])
        out[name] = (1 + f.set_index(col).sort_index()["net_return"]).resample("ME").prod() - 1
    return out


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    family = registry["family_a_seasonal_momentum"]
    gate = float(registry["gates"]["primary_breadth_gate"].split("below ")[1].split(" ")[0])

    prices = pd.read_csv(GGG, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    monthly = (1 + prices.pct_change()).resample("ME").prod() - 1
    existing = existing_monthly(prices)

    rows, correls = [], []
    for spec in family["configurations"]:
        low, high = spec["years"]
        signal = seasonal_signal(monthly, low, high)
        weights = build_weights(signal, spec["construction"])
        net = {c: evaluate(weights, monthly, c) for c in COSTS_BPS}
        primary = net[50].dropna()

        worst_abs, worst_name = 0.0, None
        for name, series in existing.items():
            joined = pd.concat([primary.rename("a"), series.rename("b")], axis=1).dropna()
            if len(joined) < 24:
                continue
            r = float(joined.a.corr(joined.b))
            correls.append({"config": spec["id"], "against": name, "months": len(joined), "correlation": r})
            if abs(r) > worst_abs:
                worst_abs, worst_name = abs(r), name
        row = {"config": spec["id"], "years": f"{low}-{high}", "construction": spec["construction"],
               "max_abs_correlation_vs_existing": round(worst_abs, 4),
               "closest_existing": worst_name,
               "breadth_gate_passed": bool(worst_abs < gate)}
        for c in COSTS_BPS:
            for k, v in metrics(net[c]).items():
                row[f"{k}__{c}bps"] = v
        rows.append(row)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "configurations.csv", index=False)
    pd.DataFrame(correls).to_csv(OUTPUT / "correlations_vs_existing.csv", index=False)
    payload = {
        "experiment": "seasonal_momentum_breadth_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry_sha256_note": "configurations fixed in config/breadth_first_signal_registry_v1.json before this ran",
        "declared_configurations": len(family["configurations"]),
        "breadth_gate": gate,
        "configurations_passing_breadth_gate": int(table.breadth_gate_passed.sum()),
        "cumulative_trial_warning": registry["cumulative_trial_accounting"],
        "promotion_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"{'cfg':<5}{'years':<7}{'construction':<26}{'months':>7}{'CAGR@50':>9}{'Sharpe':>8}{'maxDD':>8}{'maxCorr':>9}{'breadth':>9}")
    for r in rows:
        print(f"{r['config']:<5}{r['years']:<7}{r['construction']:<26}{r.get('months__50bps',0):>7}"
              f"{r.get('cagr__50bps',float('nan')):>9.2%}{r.get('sharpe_zero_rf__50bps',float('nan')):>8.2f}"
              f"{r.get('max_drawdown__50bps',float('nan')):>8.1%}{r['max_abs_correlation_vs_existing']:>9.3f}"
              f"{'PASS' if r['breadth_gate_passed'] else 'FAIL':>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
