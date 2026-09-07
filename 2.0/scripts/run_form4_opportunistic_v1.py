#!/usr/bin/env python3
"""Split insider purchases into routine and opportunistic, and test both.

Pre-registered in config/form4_opportunistic_registry_v1.json before the history
was downloaded. One signal, one horizon, one breadth, a declared POSITIVE sign,
and four gates all required -- the fourth being that opportunistic must beat
routine, because if it does not then the split adds nothing and Steps 125-126
were right for the right reason.

The routine rule is a fixed hypothesis, not a parameter: an insider-issuer pair
is routine as of a decision if that insider transacted in the same calendar month
in EACH of the three prior calendar years. No variant will be tried.

Everything keys on the FILING date. Form 4's median lag here is two days but 8.9%
of filings land more than ten days after the trade, so using the transaction date
would leak information the market did not have.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/form4_opportunistic_registry_v1.json"
PANEL = ROOT / "data/form4_purchase_panel_v1/insider_purchases.csv.gz"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
OUTPUT = ROOT / "evidence/form4_opportunistic_v1"
VALUATION = ROOT / "evidence/valuation_revival_v1/path__breadth20__50bps.csv"
GROWTH = ROOT / "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")
TEST_START = pd.Timestamp("2017-01-01", tz="UTC")


def load_leg(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    frame = frame.dropna(subset=[column]).set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


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


def classify(panel: pd.DataFrame) -> pd.DataFrame:
    """Mark each purchase routine or opportunistic using only prior-year history.

    Routine means the same insider transacted in this same calendar month in each
    of the three prior calendar years. Built as a set membership test so that a
    trade can never be classified using anything dated at or after itself.
    """
    panel = panel.copy()
    panel["year"] = panel.trans_date.dt.year
    panel["month"] = panel.trans_date.dt.month
    seen = set(zip(panel.owner_cik, panel.year, panel.month))
    routine = np.fromiter(
        (all((owner, year - back, month) in seen for back in (1, 2, 3))
         for owner, year, month in zip(panel.owner_cik, panel.year, panel.month)),
        dtype=bool, count=len(panel))
    panel["routine"] = routine
    return panel


def build_signal(panel: pd.DataFrame, weeks: pd.DatetimeIndex, window: int) -> pd.DataFrame:
    """Distinct purchasers per issuer over the trailing `window` weeks, by filing date."""
    stamped = panel.copy()
    positions = np.clip(weeks.searchsorted(stamped.filing_date.to_numpy(), side="left"),
                        0, len(weeks) - 1)
    stamped["week"] = weeks[positions]
    per_week = stamped.groupby(["week", "cik10"]).owner_cik.nunique().unstack("cik10")
    per_week = per_week.reindex(weeks).fillna(0.0)
    return per_week.rolling(window, min_periods=1).sum()


def run_book(signal: pd.DataFrame, returns: pd.DataFrame, breadth: int,
             cost_bps: float, hold: int) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    rows, last_rebalance = [], None
    for i, week in enumerate(returns.index):
        if week < TEST_START or i == 0:
            continue
        cost = 0.0
        due = last_rebalance is None or (i - last_rebalance) >= hold
        if due and week in signal.index:
            previous = returns.index[i - 1]
            if previous in signal.index:
                scores = signal.loc[previous]
                scores = scores[scores > 0]
                names = [c for c in scores.index if c in returns.columns]
                if len(names) >= breadth:
                    picked = list(scores[names].nlargest(breadth).index)
                    target = pd.Series(0.0, index=returns.columns, dtype=float)
                    target[picked] = 1.0 / breadth
                    cost = float((target - holdings).abs().sum()) / 2.0 * cost_bps / 10_000.0
                    holdings = target
                    last_rebalance = i
        row = returns.loc[week].fillna(0.0)
        rows.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    return pd.Series(dict(rows)).sort_index()


def information_coefficient(signal: pd.DataFrame, returns: pd.DataFrame, horizon: int):
    ics = []
    weeks = returns.index
    for i, week in enumerate(weeks):
        if week < TEST_START or i + horizon >= len(weeks):
            continue
        if week not in signal.index:
            continue
        scores = signal.loc[week]
        scores = scores[scores > 0]
        names = [c for c in scores.index if c in returns.columns]
        if len(names) < 30:
            continue
        forward = (returns.iloc[i + 1:i + 1 + horizon][names] + 1.0).prod() - 1.0
        both = pd.concat({"s": scores[names], "f": forward}, axis=1).dropna()
        if len(both) < 30:
            continue
        ics.append(float(both.s.rank().corr(both.f.rank())))
    ics = np.array([x for x in ics if np.isfinite(x)])
    if len(ics) < 20:
        return float("nan"), float("nan"), float("nan"), 0
    mean = float(ics.mean())
    t = float(mean / (ics.std(ddof=1) / np.sqrt(len(ics))))
    rng = np.random.default_rng(20260907)
    block, draws = 8, []
    for _ in range(4000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean)
    p = float((np.abs(np.array(draws)) >= abs(mean)).mean())
    return mean, t, p, len(ics)


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    breadth = int(registry["declared_configurations"]["breadth"][0])
    cost_bps = float(registry["declared_configurations"]["cost_bps"][0])
    horizon = int(registry["declared_horizon_weeks"])

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)

    panel = pd.read_csv(PANEL, dtype={"cik10": str, "owner_cik": str},
                        parse_dates=["filing_date", "trans_date"])
    panel = panel[panel.cik10.isin(returns.columns)]
    panel = classify(panel)
    share = float(panel.routine.mean())
    print(f"purchases in the tradable universe: {len(panel):,}  "
          f"({panel.cik10.nunique():,} issuers, {panel.owner_cik.nunique():,} insiders)")
    print(f"classified ROUTINE: {share:.1%}   OPPORTUNISTIC: {1 - share:.1%}\n")

    valuation, growth = load_leg(VALUATION), load_leg(GROWTH)
    results = {}
    for label, subset in (("opportunistic", panel[~panel.routine]), ("routine", panel[panel.routine])):
        signal = build_signal(subset, returns.index, horizon)
        ic, t, p, n = information_coefficient(signal, returns, horizon)
        path = run_book(signal, returns, breadth, cost_bps, horizon)
        m = metrics(path)
        joined = pd.concat({"x": path, "v": valuation, "g": growth}, axis=1).dropna()
        cv = float(joined.x.corr(joined.v)) if len(joined) > 30 else float("nan")
        cg = float(joined.x.corr(joined.g)) if len(joined) > 30 else float("nan")
        pre, post = path[path.index < BREAK], path[path.index >= BREAK]
        results[label] = {
            "rows": int(len(subset)), "ic": ic, "t_stat": t, "p_value": p, "ic_weeks": n,
            **m, "correlation_vs_valuation": cv, "correlation_vs_growth": cg,
            "pre_break_cagr": metrics(pre).get("cagr", float("nan")),
            "post_break_cagr": metrics(post).get("cagr", float("nan")),
        }
        path.rename_axis("Date").to_frame("net_return").to_csv(
            OUTPUT / f"path__{label}__50bps.csv")

    o, r = results["opportunistic"], results["routine"]
    gate_1 = bool(abs(o["correlation_vs_valuation"]) < 0.30 and abs(o["correlation_vs_growth"]) < 0.30)
    gate_2 = bool(o.get("sharpe", float("nan")) >= 1.0)
    gate_3 = bool(o["p_value"] < 0.05 and o["ic"] > 0)
    # Gate 4 is UNTESTABLE rather than failed when the routine leg is too rare to
    # score. Routine purchases reach a median of 13 issuers per 4-week window and
    # never 30, so the routine IC is NaN on every one of 505 weeks. Reporting that
    # as a failed gate would claim the comparison was made and lost; it was not
    # made at all, and the distinction is the whole point of the experiment.
    gate_4_testable = bool(np.isfinite(r["ic"]))
    gate_4 = bool(gate_4_testable and o["ic"] > r["ic"]
                  and o.get("sharpe", 0) > r.get("sharpe", 0))
    passed = gate_1 and gate_2 and gate_3 and gate_4

    for label in ("opportunistic", "routine"):
        x = results[label]
        print(f"{label.upper():14s} {x['rows']:>7,} purchases")
        print(f"  IC {x['ic']:+.5f}  t {x['t_stat']:+.2f}  p {x['p_value']:.4f}  ({x['ic_weeks']} weeks)")
        print(f"  CAGR {x.get('cagr', float('nan')):7.2%}  Sharpe {x.get('sharpe', float('nan')):6.3f}  "
              f"vol {x.get('volatility', float('nan')):5.1%}  maxDD {x.get('max_drawdown', float('nan')):7.2%}")
        print(f"  pre-break {x['pre_break_cagr']:7.2%}   post-break {x['post_break_cagr']:7.2%}")
        print(f"  corr vs valuation {x['correlation_vs_valuation']:+.3f}  vs growth {x['correlation_vs_growth']:+.3f}")
    print(f"\ngate 1 orthogonality        {'PASS' if gate_1 else 'FAIL'}")
    print(f"gate 2 standalone skill     {'PASS' if gate_2 else 'FAIL'}")
    print(f"gate 3 significance + sign  {'PASS' if gate_3 else 'FAIL'}")
    print(f"gate 4 split beats routine  {'PASS' if gate_4 else ('FAIL' if gate_4_testable else 'UNTESTABLE - routine leg too rare to score')}")
    print(f"\nVERDICT: {'ALL FOUR GATES PASS -- candidate' if passed else 'did not clear all four declared gates'}")

    (OUTPUT / "result.json").write_text(json.dumps({
        "routine_share": share, "horizon_weeks": horizon, "breadth": breadth,
        "cost_bps": cost_bps, "test_start": str(TEST_START.date()),
        "results": results,
        "gate_1_orthogonality": gate_1, "gate_2_standalone_skill": gate_2,
        "gate_3_significance": gate_3, "gate_4_split_beats_routine": gate_4,
        "all_gates_passed": passed, "trials_declared": 1,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
