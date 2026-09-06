#!/usr/bin/env python3
"""Eight untried price-based signal families, selected early and judged recently.

The owner asked for a strategy that works now, reasoning that what won last
decade may not work today. That reasoning is right about regimes and dangerous as
a selection rule: picking on recent returns in sample is exactly how the four
existing strategies came to correlate 0.72 to 0.97 with each other.

So the instruction is honoured without the trap. Signals are selected on
2011-2019 and evaluated on 2020-2026, which answers "does it work recently" out
of sample. What recent-window selection would have chosen is reported alongside,
so the difference between the two is visible rather than argued about.

Every signal here is price-computable and untried in this project: a
linkage-lite industry signal, three tail-risk moments, an instability measure, a
dispersion measure, a bounce-controlled residual reversal, and a consistency
measure. All use a one-week skip, because Step 250 established that anything
touching last week's return is measuring the bid-ask spread.

A cross-sectional information coefficient is not a strategy. Nothing here can be
promoted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/untried_price_signal_registry_v1.json"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_full_v1/recent_membership_readiness.csv"
SKIP = 1
LONG_WINDOW = 104
MID_WINDOW = 13


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    prices = pd.read_csv(ROOT / registry["data"].split(",")[0], index_col=0,
                         parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    members = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    sectors = members.drop_duplicates("cik10").set_index("cik10").sector
    return returns, prices, sectors.reindex(returns.columns)


def rolling_cov(frame: pd.DataFrame, series: pd.Series, window: int, minimum: int) -> pd.DataFrame:
    """Covariance of every column with one series, column-shaped.

    DataFrame.rolling().cov(Series) returns a MultiIndexed frame in this pandas,
    which then fails downstream when a row is selected and mixed with a
    ticker-indexed series. Computing it from means keeps the result rectangular.
    """
    product = frame.mul(series, axis=0).rolling(window, min_periods=minimum).mean()
    return product - frame.rolling(window, min_periods=minimum).mean().mul(
        series.rolling(window, min_periods=minimum).mean(), axis=0)


def build_signals(returns: pd.DataFrame, prices: pd.DataFrame, sectors: pd.Series) -> dict[str, pd.DataFrame]:
    market = returns.mean(axis=1, skipna=True)
    signals: dict[str, pd.DataFrame] = {}

    # linkage-lite: what the big names in your sector did
    big = prices.rolling(MID_WINDOW).median()
    industry = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns)
    lagged4 = (1.0 + returns.fillna(0.0)).rolling(4).apply(np.prod, raw=True) - 1.0
    for sector in sectors.dropna().unique():
        names = [c for c in returns.columns if sectors.get(c) == sector]
        if len(names) < 10:
            continue
        size_rank = big[names].rank(axis=1, pct=True)
        leaders = lagged4[names].where(size_rank >= 0.8)
        # broadcast one sector series across that sector's columns; a (T,1) array
        # assigned to N columns raises rather than broadcasting
        industry[names] = np.repeat(leaders.mean(axis=1).to_numpy()[:, None], len(names), axis=1)
    signals["ind_ret_big"] = industry

    demeaned = returns.sub(market, axis=0)
    market_sq = (market ** 2)
    signals["coskewness"] = rolling_cov(demeaned, market_sq, LONG_WINDOW, 26)
    down = market < 0
    signals["downside_beta"] = rolling_cov(returns.where(down), market.where(down), LONG_WINDOW, 26).div(
        market.where(down).rolling(LONG_WINDOW, min_periods=26).var(), axis=0)
    beta = rolling_cov(returns, market, LONG_WINDOW, 26).div(
        market.rolling(LONG_WINDOW, min_periods=26).var(), axis=0)
    residual = returns - beta.mul(market, axis=0)
    signals["idiosyncratic_skewness"] = residual.rolling(LONG_WINDOW, min_periods=26).skew()
    rolling_vol = returns.rolling(MID_WINDOW, min_periods=8).std()
    signals["volatility_of_volatility"] = rolling_vol.rolling(LONG_WINDOW, min_periods=26).std()

    dispersion = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns)
    for sector in sectors.dropna().unique():
        names = [c for c in returns.columns if sectors.get(c) == sector]
        if len(names) < 10:
            continue
        spread = returns[names].rolling(MID_WINDOW).std().mean(axis=1)
        dispersion[names] = np.repeat(spread.to_numpy()[:, None], len(names), axis=1)
    signals["sector_dispersion"] = dispersion

    residual4 = (1.0 + residual.fillna(0.0)).rolling(4).apply(np.prod, raw=True) - 1.0
    signals["residual_reversal_skip1"] = -residual4
    signals["trend_consistency"] = (returns > 0).rolling(26).mean().where(returns.notna().rolling(26).sum() >= 20)
    return {name: frame.shift(SKIP) for name, frame in signals.items()}


def weekly_ic(signal: pd.DataFrame, forward: pd.DataFrame, horizon: int,
              window: tuple[str, str]) -> np.ndarray:
    inside = signal.loc[(signal.index >= window[0]) & (signal.index <= window[1])]
    values = []
    for week in inside.index[::horizon]:
        if week not in forward.index:
            continue
        pair = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week]}).dropna()
        if len(pair) < 200:
            continue
        correlation = pair.s.rank().corr(pair.f.rank())
        if np.isfinite(correlation):
            values.append(float(correlation))
    return np.array(values)


def summarise(values: np.ndarray) -> dict[str, float]:
    if len(values) < 8:
        return {"observations": len(values)}
    return {
        "observations": len(values), "mean_ic": float(values.mean()),
        "t_stat": float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values)))),
        "p_value": float(stats.ttest_1samp(values, 0.0).pvalue),
        "share_positive": float((values > 0).mean()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=4)
    parser.add_argument("--output", default="evidence/untried_price_signals_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    threshold = float(registry["bonferroni_threshold"])
    select = tuple(registry["windows"]["selection"])
    evaluate = tuple(registry["windows"]["evaluation"])

    returns, prices, sectors = load()
    signals = build_signals(returns, prices, sectors)
    compounded = (1.0 + returns.fillna(0.0)).rolling(args.horizon).apply(np.prod, raw=True) - 1.0
    valid = returns.notna().rolling(args.horizon).sum() >= args.horizon
    forward = compounded.where(valid).shift(-args.horizon)

    rows = []
    for name, frame in signals.items():
        chosen = summarise(weekly_ic(frame, forward, args.horizon, select))
        judged = summarise(weekly_ic(frame, forward, args.horizon, evaluate))
        if "mean_ic" not in chosen or "mean_ic" not in judged:
            continue
        repeats = bool(np.sign(chosen["mean_ic"]) == np.sign(judged["mean_ic"]))
        rows.append({
            "signal": name,
            "select_ic": chosen["mean_ic"], "select_t": chosen["t_stat"], "select_p": chosen["p_value"],
            "select_clears": bool(chosen["p_value"] < threshold),
            "evaluate_ic": judged["mean_ic"], "evaluate_t": judged["t_stat"], "evaluate_p": judged["p_value"],
            "evaluate_clears": bool(judged["p_value"] < threshold),
            "sign_repeats": repeats,
            "survives_out_of_sample": bool(chosen["p_value"] < threshold and repeats
                                           and judged["p_value"] < 0.05),
        })
    table = pd.DataFrame(rows).sort_values("evaluate_t", key=abs, ascending=False)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "signals.csv", index=False)
    survivors = table[table.survives_out_of_sample]
    picked_on_recent = table[table.evaluate_clears]

    if table.empty:
        verdict = "no signal produced enough cross-sections to measure"
    elif survivors.empty and picked_on_recent.empty:
        verdict = ("nothing clears in either window. Eight more families closed, and the owner's "
                   "question is answered in the least interesting way: none of these worked then "
                   "or works now.")
    elif survivors.empty:
        verdict = (f"{len(picked_on_recent)} signal(s) clear on the recent window ONLY. This is the "
                   f"outcome the design exists to expose: selecting on recent returns would have "
                   f"picked them, and nothing about 2011-2019 predicted it. Treat as in-sample.")
    else:
        verdict = (f"{len(survivors)} signal(s) selected on 2011-2019 repeat their sign and stay "
                   f"significant on 2020-2026. First signal in this project judged on a window it "
                   f"was not selected on.")

    result = {
        "experiment": "untried_price_signals_v1", "declared_trials": registry["declared_trials"],
        "bonferroni_threshold": threshold, "forward_horizon_weeks": args.horizon,
        "selection_window": list(select), "evaluation_window": list(evaluate),
        "signals": rows, "survivors": survivors.signal.tolist(),
        "clear_on_recent_only": picked_on_recent.signal.tolist(),
        "verdict": verdict,
        "cumulative_trial_warning": registry["cumulative_trial_warning"],
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"selection {select[0]}..{select[1]}   evaluation {evaluate[0]}..{evaluate[1]}   "
          f"horizon {args.horizon}w   Bonferroni {threshold}\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
