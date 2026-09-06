#!/usr/bin/env python3
"""Measure short-term reversal on the SEC equity panel, controls first.

Step 249 found a negative short-horizon IC surviving on roll-free ETF data once
rolls were accounted for. Reversal is a different signal family from anything in
this registry and it is fast, which is where breadth comes from: Step 247
measured a 4-week signal delivering 3.6 times the breadth of a 52-week one.

Reversal is a documented anomaly. Finding it is a sanity check, not a discovery.
What is not known is whether it survives the three things that usually kill it,
and those are measured before any performance number is reported:

  bid-ask bounce  a price recorded at alternating bid and ask has mechanical
                  negative autocorrelation at lag one that nobody can trade.
                  Skipping a week removes it. If the IC needs skip zero, it was
                  bounce.
  liquidity       reversal that lives only in the cheapest names is not available
                  at size.
  cost            the most turnover-hungry family there is, tested to 200bps.

Configurations were fixed in `config/short_term_reversal_registry_v1.json` before
this ran, along with the meaning of each outcome.

Nothing here is authorised to trade and nothing can be promoted from it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/short_term_reversal_registry_v1.json"
MINIMUM_PRICED = 200


def returns_from(relative: str) -> pd.DataFrame:
    frame = pd.read_csv(ROOT / relative, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices = frame.where(frame > 0)
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    keep = returns.notna().sum(axis=1) >= MINIMUM_PRICED
    return returns.loc[keep], prices.loc[keep]


def signal_frame(returns: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    compounded = (1.0 + returns.fillna(0.0)).rolling(lookback).apply(np.prod, raw=True) - 1.0
    valid = returns.notna().rolling(lookback).sum() >= lookback
    return (-compounded.where(valid)).shift(skip)


def forward_frame(returns: pd.DataFrame, horizon: int) -> pd.DataFrame:
    forward = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    valid = returns.notna().rolling(horizon).sum() >= horizon
    return forward.where(valid).shift(-horizon)


def weekly_ic(signal: pd.DataFrame, forward: pd.DataFrame, horizon: int) -> np.ndarray:
    values = []
    for week in signal.index[::horizon]:
        if week not in forward.index:
            continue
        pair = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week]}).dropna()
        if len(pair) < 100:
            continue
        correlation = pair.s.rank().corr(pair.f.rank())
        if np.isfinite(correlation):
            values.append(float(correlation))
    return np.array(values)


def bootstrap_p(values: np.ndarray, draws: int = 5000, block: int = 26, seed: int = 20260906) -> float:
    if len(values) < block * 2:
        block = max(2, len(values) // 4)
    rng = np.random.default_rng(seed)
    blocks = max(1, len(values) // block)
    means = []
    for _ in range(draws):
        starts = rng.integers(0, max(1, len(values) - block), size=blocks)
        means.append(np.mean([values[s:s + block].mean() for s in starts]))
    means = np.array(means)
    return float(2 * min((means > 0).mean(), (means <= 0).mean()))


def simulate(signal: pd.DataFrame, returns: pd.DataFrame, breadth: int, cost_bps: float,
             every: int) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values = []
    for position, week in enumerate(returns.index):
        cost = 0.0
        if position % every == 0 and week in signal.index:
            row = signal.loc[week].dropna()
            if len(row) >= breadth:
                picks = row.nlargest(breadth).index
                holdings = pd.Series(0.0, index=returns.columns, dtype=float)
                holdings.loc[picks] = 1.0 / breadth
                cost = float((holdings - previous).abs().sum()) * cost_bps / 10_000.0
                previous = holdings.copy()
        values.append(float((holdings * returns.loc[week].fillna(0.0)).sum()) - cost)
    return pd.Series(values, index=returns.index)


def metrics(series: pd.Series) -> dict[str, float]:
    years = len(series) / 52.0
    wealth = (1.0 + series.fillna(0.0)).cumprod()
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    return {
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years else float("nan"),
        "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
        "annualised_volatility": volatility,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "recent_52w_return": float((1.0 + series.tail(52).fillna(0.0)).prod() - 1.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/short_term_reversal_v1")
    parser.add_argument("--breadth", type=int, default=100)
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    declared = registry["declared_configurations"]
    threshold = float(registry["bonferroni_threshold"])

    returns, prices = returns_from(registry["data"])
    treatments = {
        "raw": returns,
        "excl_50pct": returns.where(returns.abs() <= 0.50),
        "excl_100pct": returns.where(returns.abs() <= 1.00),
    }

    rows = []
    for label, frame in treatments.items():
        for lookback in declared["lookback_weeks"]:
            for skip in declared["skip_weeks"]:
                signal = signal_frame(frame, lookback, skip)
                for horizon in declared["forward_horizon_weeks"]:
                    forward = forward_frame(frame, horizon)
                    ic = weekly_ic(signal, forward, horizon)
                    if len(ic) < 30:
                        continue
                    rows.append({
                        "treatment": label, "lookback_weeks": lookback, "skip_weeks": skip,
                        "forward_horizon_weeks": horizon, "observations": len(ic),
                        "mean_ic": float(ic.mean()),
                        "t_stat": float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))),
                        "bootstrap_p": bootstrap_p(ic),
                        "share_positive": float((ic > 0).mean()),
                    })
    ic_frame = pd.DataFrame(rows)
    ic_frame["clears_bonferroni"] = ic_frame.bootstrap_p < threshold

    primary = ic_frame[ic_frame.treatment == "excl_50pct"]
    bounce = {}
    for lookback in declared["lookback_weeks"]:
        for horizon in declared["forward_horizon_weeks"]:
            at0 = primary[(primary.lookback_weeks == lookback) & (primary.skip_weeks == 0)
                          & (primary.forward_horizon_weeks == horizon)]
            at1 = primary[(primary.lookback_weeks == lookback) & (primary.skip_weeks == 1)
                          & (primary.forward_horizon_weeks == horizon)]
            if not at0.empty and not at1.empty:
                bounce[f"lb{lookback}_hz{horizon}"] = {
                    "ic_skip0": float(at0.mean_ic.iloc[0]), "ic_skip1": float(at1.mean_ic.iloc[0]),
                    "retained_share": (float(at1.mean_ic.iloc[0] / at0.mean_ic.iloc[0])
                                       if at0.mean_ic.iloc[0] else None),
                    "survives_skip": bool(at1.mean_ic.iloc[0] > 0 and at1.bootstrap_p.iloc[0] < threshold),
                }

    # Liquidity: IC within price quintiles, price level a weak proxy and stated as such.
    clean = treatments["excl_50pct"]
    signal = signal_frame(clean, 1, 1)
    forward = forward_frame(clean, 1)
    quintile_ic = {}
    for q in range(5):
        values = []
        for week in signal.index:
            if week not in forward.index or week not in prices.index:
                continue
            row = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week],
                                "p": prices.loc[week]}).dropna()
            if len(row) < 300:
                continue
            edges = row.p.quantile([q / 5, (q + 1) / 5])
            block = row[(row.p >= edges.iloc[0]) & (row.p <= edges.iloc[1])]
            if len(block) < 60:
                continue
            correlation = block.s.rank().corr(block.f.rank())
            if np.isfinite(correlation):
                values.append(float(correlation))
        if values:
            values = np.array(values)
            quintile_ic[f"price_quintile_{q + 1}"] = {
                "mean_ic": float(values.mean()),
                "t_stat": float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values)))),
                "weeks": len(values),
            }

    # Cost: the skip-1, 1-week signal on a breadth-100 book.
    cost_rows = []
    paths = {}
    for cost in (0.0, 10.0, 50.0, 100.0, 200.0):
        path = simulate(signal, clean, args.breadth, cost, 1)
        paths[cost] = path
        cost_rows.append({"cost_bps": cost, **metrics(path)})
    cost_frame = pd.DataFrame(cost_rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    ic_frame.to_csv(out / "information_coefficients.csv", index=False)
    cost_frame.to_csv(out / "cost_ladder.csv", index=False)
    paths[50.0].rename("net_return").rename_axis("Date").to_csv(out / "path__50bps.csv")

    surviving_skip = sum(1 for v in bounce.values() if v["survives_skip"])
    cheapest = quintile_ic.get("price_quintile_1", {}).get("mean_ic")
    dearest = [v["mean_ic"] for k, v in quintile_ic.items() if k != "price_quintile_1"]
    concentrated = bool(cheapest is not None and dearest and cheapest > 2 * max(dearest))
    at50 = cost_frame[cost_frame.cost_bps == 50.0].iloc[0]

    if surviving_skip == 0:
        verdict = "REJECTED: the information coefficient does not survive the bid-ask-bounce control"
    elif concentrated:
        verdict = "REJECTED: the information coefficient lives in the cheapest price quintile and is not available at size"
    elif at50.cagr <= 0:
        verdict = f"REJECTED: the book loses money at 50bps (CAGR {at50.cagr:.2%})"
    else:
        verdict = ("survives the bounce, liquidity and cost controls; correlation against existing "
                   "strategies is the remaining question and it decides whether this adds breadth")

    result = {
        "experiment": "short_term_reversal_v1",
        "declared_trials": declared["total_trials"],
        "bonferroni_threshold": threshold,
        "cumulative_trial_warning": registry["cumulative_trial_warning"],
        "weeks": int(len(returns)), "issuers": int(returns.shape[1]),
        "window": [str(returns.index.min().date()), str(returns.index.max().date())],
        "bid_ask_bounce_control": bounce,
        "configurations_surviving_skip": surviving_skip,
        "price_quintile_ic": quintile_ic,
        "ic_concentrated_in_cheapest_quintile": concentrated,
        "cost_ladder": cost_rows,
        "verdict": verdict,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")

    print(f"panel: {result['issuers']} issuers, {result['weeks']} weeks, {result['window'][0]} to {result['window'][1]}\n")
    print("INFORMATION COEFFICIENT (treatment: excluding weekly moves above 50%)")
    print(primary[["lookback_weeks", "skip_weeks", "forward_horizon_weeks", "mean_ic", "t_stat",
                   "bootstrap_p", "clears_bonferroni"]].to_string(index=False,
                                                                  float_format=lambda v: f"{v:.4f}"))
    print("\nBID-ASK BOUNCE CONTROL: does the IC survive skipping a week?")
    for name, data in bounce.items():
        share = data["retained_share"]
        print(f"  {name:<12} skip0 {data['ic_skip0']:+.4f} -> skip1 {data['ic_skip1']:+.4f}"
              f"  retained {('n/a' if share is None else f'{share:6.1%}')}  survives {data['survives_skip']}")
    print("\nLIQUIDITY: IC by price quintile (1 = cheapest), 1-week signal skip 1")
    for name, data in quintile_ic.items():
        print(f"  {name:<20} IC {data['mean_ic']:+.4f}  t {data['t_stat']:+6.2f}  weeks {data['weeks']}")
    print(f"\nCOST LADDER (breadth {args.breadth}, weekly rebalance, skip-1 1-week signal)")
    print(cost_frame.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
