#!/usr/bin/env python3
"""Calendar effects, tested the way a family this easy to mine has to be tested.

There are twelve months, five weekdays and an unbounded number of day-of-month
windows. Searching them produces significance by construction, so every effect
here is named in the literature before it is computed, all 48 asset-effect pairs
are corrected together, and the block bootstrap accounts for the volatility
clustering that an i.i.d. test would ignore.

Every pair is registered in the trial ledger whether it passes or fails.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.trial_ledger import Trial, TrialLedger  # noqa: E402

CONFIG = ROOT / "config/seasonality_program_v1.json"
OUTPUT = ROOT / "evidence/seasonality_program_v1"


def active_mask(index: pd.DatetimeIndex, effect: str) -> pd.Series:
    frame = pd.DataFrame(index=index)
    period = index.to_period("M")
    rank_in_month = pd.Series(index, index=index).groupby(period).rank(method="first")
    days_in_month = pd.Series(index, index=index).groupby(period).transform("size")
    from_end = days_in_month - rank_in_month + 1
    quarter = index.to_period("Q")
    rank_in_quarter_from_end = (
        pd.Series(index, index=index).groupby(quarter).transform("size")
        - pd.Series(index, index=index).groupby(quarter).rank(method="first") + 1
    )

    if effect == "turn_of_month":
        return ((from_end <= 1) | (rank_in_month <= 3)).astype(float)
    if effect == "halloween":
        return pd.Series(np.isin(index.month, [11, 12, 1, 2, 3, 4]).astype(float), index=index)
    if effect == "january":
        return pd.Series((index.month == 1).astype(float), index=index)
    if effect == "santa_claus":
        december_tail = (index.month == 12) & (from_end <= 5)
        january_head = (index.month == 1) & (rank_in_month <= 2)
        return pd.Series((december_tail | january_head).astype(float), index=index)
    if effect == "monday_effect":
        return pd.Series((index.dayofweek == 0).astype(float), index=index)
    if effect == "friday_effect":
        return pd.Series((index.dayofweek == 4).astype(float), index=index)
    if effect == "first_half_of_month":
        return (rank_in_month <= 10).astype(float)
    if effect == "quarter_end":
        return (rank_in_quarter_from_end <= 3).astype(float)
    raise ValueError(f"unknown effect {effect}")


def block_bootstrap_p(returns: np.ndarray, mask: np.ndarray, resamples: int,
                      block: int, rng: np.random.Generator) -> tuple[float, float]:
    """Two-sided p for the active-minus-inactive mean, resampling the return path."""
    observed = returns[mask > 0].mean() - returns[mask == 0].mean()
    n = len(returns)
    starts = rng.integers(0, n, size=(resamples, n // block + 1))
    offsets = np.arange(block)
    draws = np.empty(resamples)
    for i in range(resamples):
        idx = ((starts[i][:, None] + offsets).ravel()[:n]) % n
        shuffled = returns[idx]
        active = shuffled[mask > 0]
        inactive = shuffled[mask == 0]
        draws[i] = active.mean() - inactive.mean()
    centred = draws - draws.mean()
    p = float((np.abs(centred) >= abs(observed)).mean())
    return float(observed), p


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]
    sig = spec["significance"]

    raw = pd.read_csv(ROOT / config["price_source"], parse_dates=["observation_date"])
    prices = raw.pivot_table(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    returns = prices.pct_change()

    series = {name: returns[name] for name in spec["assets"] if name in returns}
    series["equal_weight_etf_universe"] = returns.mean(axis=1)

    start = spec["evaluation_start"]
    rng = np.random.default_rng(20260827)
    threshold = 0.05 / sig["family_size"]

    findings = {}
    for asset, book in series.items():
        book = book.loc[start:].dropna()
        if len(book) < 2000:
            continue
        for effect in [e["name"] for e in spec["effects"]]:
            mask = active_mask(book.index, effect)
            values = book.to_numpy()
            flags = mask.to_numpy()
            if flags.sum() < 100 or (flags == 0).sum() < 100:
                continue
            spread, p = block_bootstrap_p(
                values, flags, sig["test"] and 10000, 21, rng
            )
            active_days = float(flags.mean())
            # What a long/flat book actually earns, after paying to switch.
            exposure = mask.shift(1).fillna(0.0)
            turnover = exposure.diff().abs().fillna(0.0)
            net = book * exposure - turnover * spec["cost_bps_per_unit_turnover"] / 1e4
            wealth = (1 + net).cumprod()
            years = len(net) / 252
            findings[f"{asset}::{effect}"] = {
                "asset": asset,
                "effect": effect,
                "active_day_share": active_days,
                "daily_spread_bps": spread * 1e4,
                "annualised_spread_pct": ((1 + spread) ** 252 - 1) * 100,
                "bootstrap_p": p,
                "survives_bonferroni": bool(p < threshold),
                "long_flat_cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
                "buy_and_hold_cagr": float((1 + book).cumprod().iloc[-1] ** (1 / years) - 1),
            }

    survivors = [k for k, v in findings.items() if v["survives_bonferroni"]]
    nominal = [k for k, v in findings.items() if v["bootstrap_p"] < 0.05]

    ledger = TrialLedger(ROOT / "data/trial_ledger_v1/trials.jsonl")
    registered = 0
    if ledger.count(family="seasonality") == 0:
        registered = ledger.append([
            Trial("seasonality", config["experiment"], key, "active_minus_inactive_daily_mean",
                  config["price_source"],
                  outcome="survives_bonferroni" if v["survives_bonferroni"] else "rejected",
                  metric=float(v["bootstrap_p"]))
            for key, v in findings.items()
        ])

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_start": start,
        "pairs_tested": len(findings),
        "bonferroni_threshold": threshold,
        "survivors": survivors,
        "nominally_significant_before_correction": nominal,
        "findings": findings,
        "trials_registered": registered,
        "trial_ledger_total": ledger.count(),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print(f"{len(findings)} pairs tested, Bonferroni threshold p < {threshold:.5f}\n")
    print(f"{'pair':44s}{'active%':>8s}{'ann spread':>12s}{'p':>9s}{'long/flat':>11s}{'buy&hold':>10s}")
    for key, v in sorted(findings.items(), key=lambda kv: kv[1]["bootstrap_p"]):
        flag = " *" if v["survives_bonferroni"] else ""
        print(f"{key:44s}{v['active_day_share']*100:7.1f}%{v['annualised_spread_pct']:11.2f}%"
              f"{v['bootstrap_p']:9.4f}{v['long_flat_cagr']*100:10.2f}%{v['buy_and_hold_cagr']*100:9.2f}%{flag}")
    print()
    print("survives Bonferroni:", survivors or "none")
    print("nominally significant before correction:", len(nominal))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
