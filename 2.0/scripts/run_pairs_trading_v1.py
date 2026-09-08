#!/usr/bin/env python3
"""The first market-neutral structure attempted in this project: GGR pairs trading.

Pre-registered in config/pairs_trading_registry_v1.json. The rule is Gatev,
Goetzmann and Rouwenhorst (2006) taken verbatim -- 52-week formation on
normalised prices, minimum sum of squared deviations, top twenty pairs, 26-week
trading, two-sigma entry, convergence exit -- because adopting a published rule
unchanged leaves nothing to fit. Nothing here is swept.

Why bother after fourteen closed families: every strategy in this project is
long-only, so every one carries market beta, and that is the most likely reason
every candidate keeps failing the orthogonality gate against them. Step 292
measured the four dashboard books at 1.690 effective independent bets of four.
A long-short book removes the market factor by construction rather than hoping.

The danger is selection. There are roughly 180,000 candidate pairs in this
universe and the rule picks twenty, which is a search over 180,000 hypotheses --
an order of magnitude larger than anything this project has run before. Formation
and trading windows are therefore disjoint, and the result is judged against a
random-pair placebo rather than against a significance test of the chosen pairs,
which would be meaningless at this search size.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.return_conventions import load_aligned

REGISTRY = ROOT / "config/pairs_trading_registry_v1.json"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
ETF = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/pairs_trading_v1"
VALUATION = "evidence/valuation_revival_v1/path__breadth20__50bps.csv"
GROWTH = "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv"
PLACEBO_RUNS = 200


def load_prices() -> pd.DataFrame:
    frame = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    return frame


def metrics(returns: pd.Series) -> dict[str, float]:
    if len(returns) < 20:
        return {}
    years = len(returns) / 52.0
    total = float((1.0 + returns).prod())
    cagr = total ** (1.0 / years) - 1.0 if total > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + returns).cumprod()
    return {"cagr": cagr, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "volatility": vol, "max_drawdown": float((curve / curve.cummax() - 1.0).min())}


def eligible(prices: pd.DataFrame, start: int, stop: int) -> list[str]:
    """Names with a complete, positive price history across the formation window."""
    block = prices.iloc[start:stop]
    good = block.notna().all(axis=0) & (block > 0).all(axis=0)
    return list(block.columns[good])


def select_pairs(prices: pd.DataFrame, start: int, stop: int, names: list[str],
                 count: int, rng: np.random.Generator | None):
    """Top `count` pairs by minimum sum of squared deviations of normalised prices.

    When `rng` is given the pairs are drawn at random from the same eligible set
    instead -- the placebo. Everything downstream is identical, so any difference
    between the two is the selection rule and nothing else.
    """
    block = prices.iloc[start:stop][names]
    normalised = block / block.iloc[0]
    if rng is not None:
        picks = set()
        while len(picks) < count and len(picks) < len(names) * (len(names) - 1) // 2:
            a, b = rng.choice(len(names), size=2, replace=False)
            picks.add((names[min(a, b)], names[max(a, b)]))
        chosen = sorted(picks)
    else:
        matrix = normalised.to_numpy()
        # Sum of squared deviations for every pair, vectorised: ||a||^2 + ||b||^2 - 2a.b
        squares = (matrix ** 2).sum(axis=0)
        gram = matrix.T @ matrix
        ssd = squares[:, None] + squares[None, :] - 2 * gram
        np.fill_diagonal(ssd, np.inf)
        ssd = np.triu(ssd) + np.tril(np.full_like(ssd, np.inf))
        flat = np.argsort(ssd, axis=None)[:count]
        rows, cols = np.unravel_index(flat, ssd.shape)
        chosen = [(names[i], names[j]) for i, j in zip(rows, cols)]
    spreads = {}
    for a, b in chosen:
        spread = normalised[a] - normalised[b]
        spreads[(a, b)] = float(spread.std(ddof=1))
    return chosen, spreads


def trade(prices: pd.DataFrame, chosen, spreads, start: int, stop: int,
          entry_sigma: float, cost_bps: float, borrow_bps: float) -> pd.Series:
    """Run the convergence trade over the disjoint trading window."""
    block = prices.iloc[start - 1:stop]
    if len(block) < 3:
        return pd.Series(dtype=float)
    normalised = block / block.iloc[0]
    returns = (block / block.shift(1) - 1.0).iloc[1:]
    weeks = returns.index
    per_pair = {}
    for (a, b), sigma in spreads.items():
        if sigma <= 0 or a not in normalised.columns or b not in normalised.columns:
            continue
        spread = normalised[a] - normalised[b]
        position, rows = 0, []
        for i, week in enumerate(weeks):
            previous = spread.iloc[i]           # spread as of last week's close
            realised = 0.0
            if position != 0:
                # long a / short b when position is +1, and the reverse when -1
                realised = position * (returns.loc[week, a] - returns.loc[week, b])
                realised -= borrow_bps / 10_000.0 / 52.0
            new = position
            if position == 0:
                if previous > entry_sigma * sigma:
                    new = -1                    # a rich relative to b: short a, long b
                elif previous < -entry_sigma * sigma:
                    new = 1
            elif (position == 1 and previous >= 0) or (position == -1 and previous <= 0):
                new = 0                          # converged
            if new != position:
                realised -= 2 * cost_bps / 10_000.0 * abs(new - position) / 2.0
                position = new
            rows.append((week, realised))
        per_pair[(a, b)] = pd.Series(dict(rows))
    if not per_pair:
        return pd.Series(dtype=float)
    return pd.DataFrame(per_pair).mean(axis=1)


def run(prices: pd.DataFrame, formation: int, trading: int, count: int,
        entry_sigma: float, cost_bps: float, borrow_bps: float,
        rng: np.random.Generator | None = None) -> pd.Series:
    pieces = []
    index = prices.index
    start = formation
    while start + trading <= len(index):
        names = eligible(prices, start - formation, start)
        if len(names) >= 50:
            chosen, spreads = select_pairs(prices, start - formation, start, names, count, rng)
            piece = trade(prices, chosen, spreads, start, start + trading,
                          entry_sigma, cost_bps, borrow_bps)
            if len(piece):
                pieces.append(piece)
        start += trading
    return pd.concat(pieces).sort_index() if pieces else pd.Series(dtype=float)


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    cfg = registry["declared_configurations"]
    formation, trading = cfg["formation_weeks"][0], cfg["trading_weeks"][0]
    count, sigma = cfg["pairs"][0], cfg["entry_sigma"][0]
    cost, borrow = cfg["cost_bps_per_leg"][0], cfg["annual_borrow_bps"][0]

    prices = load_prices()
    names_total = prices.shape[1]
    print(f"panel {names_total} names x {prices.shape[0]} weeks "
          f"({prices.index.min().date()} -> {prices.index.max().date()})")
    print(f"candidate pairs at full eligibility: ~{names_total * (names_total - 1) // 2:,}\n")

    book = run(prices, formation, trading, count, sigma, cost, borrow)
    if not len(book):
        print("INCONCLUSIVE: no trading periods produced a book")
        return 1
    m = metrics(book)

    etf = pd.read_csv(ETF, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    etf.index = pd.to_datetime(etf.index, utc=True)
    spy = ((etf / etf.shift(1) - 1.0)["SPY"]).dropna()
    valuation = load_aligned(VALUATION, root=ROOT)
    growth = load_aligned(GROWTH, root=ROOT)

    joined = pd.concat({"b": book, "v": valuation, "g": growth}, axis=1).dropna()
    cv = float(joined.b.corr(joined.v)) if len(joined) > 30 else float("nan")
    cg = float(joined.b.corr(joined.g)) if len(joined) > 30 else float("nan")
    bj = pd.concat({"b": book, "m": spy}, axis=1).dropna()
    beta, intercept = np.polyfit(bj.m, bj.b, 1)
    residual = bj.b - (beta * bj.m + intercept)
    r2 = 1.0 - residual.var() / bj.b.var()

    print(f"declared book ({len(book)} weeks, {formation}w formation / {trading}w trading, "
          f"{count} pairs, {sigma}sigma, {cost:.0f}bps/leg, {borrow:.0f}bps borrow)")
    print(f"  CAGR {m['cagr']:7.2%}  Sharpe {m['sharpe']:6.3f}  vol {m['volatility']:5.1%}  "
          f"maxDD {m['max_drawdown']:7.2%}")
    print(f"  market beta {beta:+.3f}  R2 {r2:.3f}")
    print(f"  corr vs valuation {cv:+.3f}   vs growth {cg:+.3f}\n")

    rng = np.random.default_rng(20260908)
    placebo = []
    for _ in range(PLACEBO_RUNS):
        control = run(prices, formation, trading, count, sigma, cost, borrow, rng=rng)
        if len(control) > 20:
            placebo.append(metrics(control).get("sharpe", np.nan))
    placebo = np.array([x for x in placebo if np.isfinite(x)])
    p95 = float(np.percentile(placebo, 95)) if len(placebo) else float("nan")
    beats = bool(m["sharpe"] > p95)
    print(f"random-pair placebo, {len(placebo)} runs: mean Sharpe {placebo.mean():+.3f}, "
          f"95th pct {p95:+.3f}")
    print(f"  declared book {m['sharpe']:+.3f} -> {'BEATS' if beats else 'does NOT beat'} the placebo\n")

    gate_1 = bool(abs(cv) < 0.30 and abs(cg) < 0.30)
    gate_2 = bool(m["sharpe"] >= 1.0)
    gate_3 = beats
    gate_4 = bool(abs(beta) < 0.30)
    passed = gate_1 and gate_2 and gate_3 and gate_4
    print(f"gate 1 orthogonality        {'PASS' if gate_1 else 'FAIL'}")
    print(f"gate 2 standalone skill     {'PASS' if gate_2 else 'FAIL'}")
    print(f"gate 3 beats random pairs   {'PASS' if gate_3 else 'FAIL'}")
    print(f"gate 4 truly market neutral {'PASS' if gate_4 else 'FAIL'}")
    print(f"\nVERDICT: {'ALL FOUR GATES PASS -- candidate' if passed else 'did not clear all four declared gates'}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    book.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / "path__ggr20__50bps.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "rule": "Gatev Goetzmann Rouwenhorst 2006, verbatim",
        "formation_weeks": formation, "trading_weeks": trading, "pairs": count,
        "entry_sigma": sigma, "cost_bps_per_leg": cost, "annual_borrow_bps": borrow,
        **{f"book_{k}": v for k, v in m.items()},
        "market_beta": float(beta), "market_r2": float(r2),
        "correlation_vs_valuation": cv, "correlation_vs_growth": cg,
        "placebo_runs": int(len(placebo)),
        "placebo_mean_sharpe": float(placebo.mean()) if len(placebo) else None,
        "placebo_p95_sharpe": p95,
        "gate_1_orthogonality": gate_1, "gate_2_standalone_skill": gate_2,
        "gate_3_beats_placebo": gate_3, "gate_4_market_neutral": gate_4,
        "all_gates_passed": passed, "trials_declared": 1,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
