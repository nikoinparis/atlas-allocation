#!/usr/bin/env python3
"""S4: the pre-registered version of the short-interest exclusion filter.

Step 268's run does not count -- six undeclared trials after seeing the signal
work, on the window everything here was selected on. This declares the books, the
thresholds, the windows and the reading of every outcome first.

Two things this does that Step 268 did not. It reports the pre-break and
post-break sub-periods separately, because Step 262 showed all of these
strategies' performance lives in the seventeen months after April 2025 and an
improvement that lives only there is not distinguishable from that. And it uses a
PAIRED bootstrap on the weekly difference, because filtered and unfiltered books
share almost every holding and an unpaired test on two nearly identical series
would be absurdly conservative.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/short_interest_filter_registry_v1.json"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
SHORT = ROOT / "data/finra_short_interest_v1"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v3/price_source_inventory.csv"
BOOKS = {
    "cash_conversion_b20": ("evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv", "decision_at"),
    "growth_top_five": ("evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv", "decision_at"),
    "sector_ensemble": ("evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv", "rebalance_at"),
}
COST_BPS = 50.0


def load_short() -> pd.DataFrame:
    frames = [pd.read_csv(io.StringIO(gzip.decompress(p.read_bytes()).decode("utf-8", "ignore")),
                          sep="|", low_memory=False, quoting=3, on_bad_lines="skip")
              for p in sorted(SHORT.glob("*.csv.gz"))]
    frame = pd.concat(frames, ignore_index=True)
    frame["settlementDate"] = pd.to_datetime(frame.settlementDate, errors="coerce")
    frame = frame.dropna(subset=["settlementDate", "symbolCode"])
    frame["available_at"] = (frame.settlementDate + pd.Timedelta(days=8)).dt.tz_localize("UTC")
    mapping = {}
    with INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            match = (re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
                     or re.search(r"/([A-Za-z0-9.\-]+)/prices\.csv\.gz$", row["path"]))
            if match:
                mapping.setdefault(match.group(1).upper(), row["cik10"])
    frame["cik10"] = frame.symbolCode.astype(str).str.upper().map(mapping)
    frame["dtc"] = pd.to_numeric(frame.daysToCoverQuantity, errors="coerce")
    return frame.dropna(subset=["cik10", "dtc"]).sort_values("available_at")


def simulate(schedule: dict, returns: pd.DataFrame) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values = []
    for week in returns.index:
        cost = 0.0
        if week in schedule and schedule[week]:
            names = schedule[week]
            holdings = pd.Series(0.0, index=returns.columns, dtype=float)
            holdings.loc[names] = 1.0 / len(names)
            cost = float((holdings - previous).abs().sum()) * COST_BPS / 10_000.0
            previous = holdings.copy()
        values.append(float((holdings * returns.loc[week].fillna(0.0)).sum()) - cost)
    return pd.Series(values, index=returns.index)


def paired_bootstrap(difference: np.ndarray, draws: int = 5000, block: int = 13,
                     seed: int = 20260906) -> float:
    if len(difference) < block * 2:
        block = max(2, len(difference) // 4)
    rng = np.random.default_rng(seed)
    blocks = max(1, len(difference) // block)
    means = []
    for _ in range(draws):
        starts = rng.integers(0, max(1, len(difference) - block), size=blocks)
        means.append(np.mean([difference[s:s + block].mean() for s in starts]))
    means = np.array(means)
    return float(2 * min((means > 0).mean(), (means <= 0).mean()))


def metrics(series: pd.Series) -> dict[str, float]:
    if len(series) < 10:
        return {}
    wealth = (1.0 + series.fillna(0.0)).cumprod()
    years = len(series) / 52.0
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    return {"cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
            "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
            "max_drawdown": float((wealth / wealth.cummax() - 1.0).min())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/short_interest_filter_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    threshold = float(registry["bonferroni_threshold"])
    windows = registry["windows"]

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    short = load_short()

    rows = []
    for book_name in registry["declared_books"]:
        relative, column = BOOKS[book_name]
        book = pd.read_csv(ROOT / relative, dtype={"cik10": str})
        book[column] = pd.to_datetime(book[column], utc=True)
        book = book.rename(columns={column: "decision_at"})
        book = book[book.cik10.isin(returns.columns)]
        mapping = {}
        for value in sorted(book.decision_at.unique()):
            later = returns.index[returns.index > value]
            if len(later):
                mapping[value] = later[0]
        book = book[book.decision_at.isin(mapping)].copy()
        book["execution_at"] = book.decision_at.map(mapping)
        base_schedule = {d: sorted(g.cik10) for d, g in book.groupby("execution_at")}
        base = simulate(base_schedule, returns)

        for cut in registry["declared_thresholds"]:
            schedule = {}
            for week, names in base_schedule.items():
                recent = short[short.available_at <= week]
                kept = names
                if len(recent):
                    last = recent.groupby("cik10").dtc.last().reindex(names).dropna()
                    if len(last) >= 10:
                        allowed = set(last[last <= last.quantile(cut)].index)
                        kept = [n for n in names if n in allowed or n not in last.index]
                schedule[week] = kept or names
            filtered = simulate(schedule, returns)
            start = min(base_schedule)
            for label, window in (("full", windows["full"]), ("pre_break", windows["pre_break"]),
                                  ("post_break", windows["post_break"])):
                mask = (base.index >= max(pd.Timestamp(window[0], tz="UTC"), start)) & (base.index <= window[1])
                a, b = base[mask], filtered[mask]
                if len(a) < 30:
                    continue
                difference = (b - a).to_numpy()
                rows.append({"book": book_name, "threshold": cut, "window": label, "weeks": len(a),
                             "base_cagr": metrics(a).get("cagr"), "filtered_cagr": metrics(b).get("cagr"),
                             "base_sharpe": metrics(a).get("sharpe"), "filtered_sharpe": metrics(b).get("sharpe"),
                             "mean_weekly_difference": float(difference.mean()),
                             "paired_bootstrap_p": paired_bootstrap(difference),
                             "clears_bonferroni": bool(paired_bootstrap(difference) < threshold
                                                       and difference.mean() > 0)})
    table = pd.DataFrame(rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "filter_results.csv", index=False)

    full = table[(table.window == "full") & table.clears_bonferroni]
    both = []
    for row in full.itertuples():
        pre = table[(table.book == row.book) & (table.threshold == row.threshold) & (table.window == "pre_break")]
        post = table[(table.book == row.book) & (table.threshold == row.threshold) & (table.window == "post_break")]
        if not pre.empty and not post.empty and pre.iloc[0].mean_weekly_difference > 0 and post.iloc[0].mean_weekly_difference > 0:
            both.append(f"{row.book}@{row.threshold}")

    if table.empty:
        verdict = "no comparable window"
    elif full.empty:
        verdict = ("no book improves significantly on the full window under a paired bootstrap. "
                   "S4 closes and Step 268's numbers are recorded as noise.")
    elif not both:
        verdict = (f"{len(full)} configuration(s) clear on the full window but the improvement does "
                   f"not hold in both sub-periods, so it cannot be distinguished from the post-break "
                   f"surge. Rejected under the pre-declared reading.")
    else:
        verdict = (f"{', '.join(both)} improve significantly and in both sub-periods: the first "
                   f"verified improvement to an existing strategy here. It still has no forward "
                   f"evidence and neither does the book it improves.")

    result = {"experiment": "short_interest_filter_v1", "queue_item": "S4",
              "declared_trials": registry["declared_trials"], "bonferroni_threshold": threshold,
              "rows": rows, "clears_full_window": full.book.tolist(),
              "holds_in_both_sub_periods": both, "verdict": verdict,
              "caveat": registry["interpretation_fixed_in_advance"]["always"],
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
