#!/usr/bin/env python3
"""S2 candidate: is short-sale volume a third independent return source?

Pre-registered in config/finra_short_volume_registry_v1.json before the data was
downloaded: one signal, one horizon, one breadth, a declared NEGATIVE sign, and
three gates that all have to pass.

The three gates exist because of Step 277. XLE cleared an orthogonality gate,
raised effective independent bets from 2.00 to 2.88, and bought 0.021 of Sharpe,
because its own Sharpe is 0.568. `IR = IC * sqrt(BR)` is a product, so a leg that
is uncorrelated and unskilled is worth nothing and "uncorrelated" alone was never
the criterion. Gate 2 is that lesson written down as a rule.

A positive IC of similar magnitude refutes the declared hypothesis. It does not
become a contrarian signal, and this script prints REFUTED rather than reversing
the sign, because reversing it after the fact is the search this project keeps
dying of.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "config/finra_short_volume_registry_v1.json"
CACHE = ROOT / "data/finra_short_volume_v1/daily"
OUTPUT = ROOT / "evidence/finra_short_volume_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
VALUATION = ROOT / "evidence/valuation_revival_v1/path__breadth20__50bps.csv"
GROWTH = ROOT / "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")


def load_prices() -> pd.DataFrame:
    frame = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    return frame


def load_series(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    frame = frame.dropna(subset=[column]).set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def ticker_to_cik() -> dict[str, str]:
    frame = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, usecols=["cik10", "ticker_used"]).dropna()
    frame["ticker_used"] = frame.ticker_used.astype(str).str.upper()
    return frame.groupby("ticker_used").cik10.agg(lambda v: v.value_counts().index[0]).to_dict()


def weekly_short_ratio(mapping: dict[str, str], index: pd.DatetimeIndex) -> pd.DataFrame:
    files = sorted(CACHE.glob("*.txt"))
    if not files:
        raise SystemExit("no FINRA files cached; run scripts/acquire_finra_short_volume_v1.py")
    frames = []
    for path in files:
        frame = pd.read_csv(path, sep="|", usecols=["Date", "Symbol", "ShortVolume", "TotalVolume"])
        frame = frame[frame.Date.astype(str).str.len() == 8]
        frames.append(frame)
    daily = pd.concat(frames, ignore_index=True)
    daily["Date"] = pd.to_datetime(daily.Date, format="%Y%m%d", utc=True, errors="coerce")
    daily["cik10"] = daily.Symbol.astype(str).str.upper().map(mapping)
    daily = daily.dropna(subset=["Date", "cik10"])
    for column in ("ShortVolume", "TotalVolume"):
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    daily = daily.dropna(subset=["ShortVolume", "TotalVolume"])

    # Stamp each trading day with the Friday of its week, then aggregate volume
    # before dividing. Averaging daily ratios would weight a thin day equally
    # with a heavy one; the ratio of the sums is the week's actual short share.
    weeks = pd.DatetimeIndex(index)
    positions = weeks.searchsorted(daily.Date.to_numpy(), side="left")
    positions = np.clip(positions, 0, len(weeks) - 1)
    daily["week"] = weeks[positions]

    grouped = daily.groupby(["week", "cik10"])[["ShortVolume", "TotalVolume"]].sum()
    ratio = (grouped.ShortVolume / grouped.TotalVolume).replace([np.inf, -np.inf], np.nan).dropna()
    ratio = ratio[(ratio > 0) & (ratio < 1)]
    return ratio.unstack("cik10")


def metrics(returns: pd.Series) -> dict[str, float]:
    if len(returns) < 20:
        return {}
    total = float((1.0 + returns).prod())
    years = len(returns) / 52.0
    cagr = total ** (1.0 / years) - 1.0 if total > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + returns).cumprod()
    return {"cagr": cagr, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "volatility": vol, "max_drawdown": float((curve / curve.cummax() - 1.0).min())}


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    breadth = int(registry["declared_configurations"]["breadth"][0])
    cost_bps = float(registry["declared_configurations"]["cost_bps"][0])

    prices = load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    ratio = weekly_short_ratio(ticker_to_cik(), returns.index)
    shared = [c for c in ratio.columns if c in returns.columns]
    ratio = ratio[shared]
    print(f"short-volume panel: {ratio.shape[1]} issuers x {ratio.shape[0]} weeks "
          f"({ratio.index.min().date()} -> {ratio.index.max().date()})")

    # Information coefficient: rank of this week's ratio against next week's return.
    ics = []
    for week in ratio.index:
        later = returns.index[returns.index > week]
        if not len(later):
            continue
        signal = ratio.loc[week].dropna()
        forward = returns.loc[later[0]].reindex(signal.index).dropna()
        signal = signal.reindex(forward.index)
        if len(forward) < 30:
            continue
        ics.append(float(signal.rank().corr(forward.rank())))
    ics = np.array([x for x in ics if np.isfinite(x)])
    mean_ic = float(ics.mean())
    t_stat = float(mean_ic / (ics.std(ddof=1) / np.sqrt(len(ics)))) if len(ics) > 2 else float("nan")

    rng = np.random.default_rng(20260906)
    block, draws = 8, []
    for _ in range(5000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean_ic)
    p_value = float((np.abs(np.array(draws)) >= abs(mean_ic)).mean())

    # Book: long the LEAST shorted, which is the declared negative sign expressed.
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    values = []
    for week in returns.index:
        if week < ratio.index.min():
            continue
        cost = 0.0
        if week in ratio.index:
            signal = ratio.loc[week].dropna()
            if len(signal) >= breadth:
                names = list(signal.nsmallest(breadth).index)
                target = pd.Series(0.0, index=returns.columns, dtype=float)
                target[names] = 1.0 / len(names)
                cost = float((target - holdings).abs().sum()) / 2.0 * cost_bps / 10_000.0
                holdings = target
        row = returns.loc[week].fillna(0.0)
        values.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    path = pd.Series(dict(values)).sort_index()
    book = metrics(path)

    valuation, growth = load_series(VALUATION), load_series(GROWTH)
    joined = pd.concat({"x": path, "v": valuation, "g": growth}, axis=1, sort=True).dropna()
    corr_v = float(joined.x.corr(joined.v)) if len(joined) > 30 else float("nan")
    corr_g = float(joined.x.corr(joined.g)) if len(joined) > 30 else float("nan")

    sign_ok = mean_ic < 0
    gate_1 = bool(abs(corr_v) < 0.30 and abs(corr_g) < 0.30)
    gate_2 = bool(book.get("sharpe", float("nan")) >= 1.0)
    gate_3 = bool(p_value < 0.05 and sign_ok)
    passed = gate_1 and gate_2 and gate_3

    print(f"\ninformation coefficient {mean_ic:+.5f}  t {t_stat:+.2f}  block-bootstrap p {p_value:.4f}")
    print(f"declared sign NEGATIVE -> observed {'NEGATIVE, consistent' if sign_ok else 'POSITIVE, REFUTED'}")
    print(f"\nbook (long the {breadth} least-shorted, {cost_bps:.0f}bps)")
    print(f"  CAGR {book.get('cagr', float('nan')):7.2%}  Sharpe {book.get('sharpe', float('nan')):5.3f}  "
          f"vol {book.get('volatility', float('nan')):5.1%}  maxDD {book.get('max_drawdown', float('nan')):7.2%}")
    pre, post = path[path.index < BREAK], path[path.index >= BREAK]
    print(f"  pre-break CAGR {metrics(pre).get('cagr', float('nan')):7.2%}   "
          f"post-break CAGR {metrics(post).get('cagr', float('nan')):7.2%}")
    print(f"\ncorrelation vs valuation {corr_v:+.3f}   vs growth {corr_g:+.3f}")
    print(f"\ngate 1 orthogonality (<0.30 both)   {'PASS' if gate_1 else 'FAIL'}")
    print(f"gate 2 standalone skill (Sharpe>=1)  {'PASS' if gate_2 else 'FAIL'}")
    print(f"gate 3 significance with sign        {'PASS' if gate_3 else 'FAIL'}")
    print(f"\nVERDICT: {'CANDIDATE -- all three gates pass' if passed else 'CLOSED -- did not clear all three declared gates'}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    path.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / "path__breadth20__50bps.csv")
    result = {
        "experiment": "finra_short_volume_v1",
        "issuers": int(ratio.shape[1]), "weeks": int(ratio.shape[0]),
        "mean_information_coefficient": mean_ic, "t_stat": t_stat,
        "block_bootstrap_p": p_value,
        "declared_sign": "negative", "observed_sign_matches": sign_ok,
        **{f"book_{k}": v for k, v in book.items()},
        "correlation_vs_valuation": corr_v, "correlation_vs_growth": corr_g,
        "gate_1_orthogonality": gate_1, "gate_2_standalone_skill": gate_2,
        "gate_3_significance": gate_3, "all_gates_passed": passed,
        "trials_declared": int(registry["trials_declared_here"]),
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
