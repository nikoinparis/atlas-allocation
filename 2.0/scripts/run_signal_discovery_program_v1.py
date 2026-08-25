#!/usr/bin/env python3
"""Does any published selection rule produce a positive decile spread here?

Twenty-two signals from the asset-pricing literature are specified in the config
before anything is computed. Each is standardised inside its SIC sector, ranked
weekly across roughly 3,200 issuers, and scored on the forward 13-week return of
its top decile minus its bottom decile.

Significance uses a moving-block bootstrap because weekly evaluation with a
13-week forward return produces overlapping windows; an i.i.d. test would badly
overstate confidence. Every signal run is counted in the Bonferroni correction.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/signal_discovery_program_v1.json"
OUTPUT = ROOT / "evidence/signal_discovery_program_v1"
PANEL = ROOT / "data/sec_broad_research_panel_v2/panel.csv.gz"


def load_prices(config: dict) -> pd.DataFrame:
    prices = pd.read_csv(ROOT / config["price_panel"], index_col=0)
    prices.index = pd.to_datetime(prices.index)
    return prices.sort_index()


def sector_map() -> pd.Series:
    panel = pd.read_csv(PANEL, usecols=["cik10", "sector"], dtype={"cik10": str})
    return panel.drop_duplicates("cik10").set_index("cik10")["sector"]


def build_price_signals(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = prices.pct_change()
    panel_return = returns.mean(axis=1)
    signals: dict[str, pd.DataFrame] = {}

    signals["momentum_12_1"] = prices.shift(4) / prices.shift(52) - 1.0
    signals["momentum_6_1"] = prices.shift(4) / prices.shift(26) - 1.0
    signals["reversal_1m"] = -(prices / prices.shift(4) - 1.0)
    signals["low_volatility"] = -returns.rolling(52, min_periods=40).std(ddof=1)
    signals["low_max_return"] = -returns.rolling(52, min_periods=40).max()
    signals["near_52w_high"] = prices / prices.rolling(52, min_periods=40).max()

    market_var = panel_return.rolling(52, min_periods=40).var(ddof=1)
    covariance = returns.rolling(52, min_periods=40).cov(panel_return)
    beta = covariance.div(market_var, axis=0)
    signals["low_beta"] = -beta

    fitted = beta.mul(panel_return, axis=0)
    residual = returns - fitted
    signals["low_idiosyncratic_volatility"] = -residual.rolling(52, min_periods=40).std(ddof=1)

    # every signal is shifted one week so a decision never uses its own week's price
    return {name: frame.shift(1) for name, frame in signals.items()}


def build_fundamental_signals(prices: pd.DataFrame, facts_path: Path) -> dict[str, pd.DataFrame]:
    if not facts_path.exists():
        return {}
    facts = pd.read_csv(facts_path, dtype={"cik10": str}, parse_dates=["filed"])
    facts = facts[facts.filed.notna()]
    weeks = prices.index
    columns = prices.columns

    def as_of(concept: str) -> pd.DataFrame:
        """Latest filed value of a concept, as known at each week."""
        subset = facts[facts.concept == concept].sort_values("filed")
        if subset.empty:
            return pd.DataFrame(np.nan, index=weeks, columns=columns)
        subset = subset.drop_duplicates(["cik10", "filed"], keep="last")
        wide = subset.pivot_table(index="filed", columns="cik10", values="value", aggfunc="last")
        wide = wide.reindex(columns=columns)
        return wide.reindex(weeks.union(wide.index)).ffill().reindex(weeks)

    revenue, income = as_of("revenue"), as_of("net_income")
    gross, assets = as_of("gross_profit"), as_of("assets")
    equity, opcf = as_of("equity"), as_of("operating_cash_flow")
    liabilities, shares = as_of("liabilities"), as_of("shares")
    market_cap = prices * shares

    def safe(numerator: pd.DataFrame, denominator: pd.DataFrame) -> pd.DataFrame:
        result = numerator / denominator.replace(0.0, np.nan)
        return result.replace([np.inf, -np.inf], np.nan)

    signals = {
        "gross_profitability": safe(gross, assets),
        "return_on_assets": safe(income, assets),
        "low_accruals": -safe(income - opcf, assets),
        "low_asset_growth": -(assets / assets.shift(52) - 1.0),
        "cash_conversion": safe(opcf, revenue),
        "net_margin": safe(income, revenue),
        "book_to_market": safe(equity, market_cap),
        "earnings_yield": safe(income, market_cap),
        "low_leverage": -safe(liabilities, assets),
    }
    return {name: frame.shift(1) for name, frame in signals.items()}


def sector_neutral_z(frame: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    groups = sectors.reindex(frame.columns).fillna("unclassified")
    out = pd.DataFrame(np.nan, index=frame.index, columns=frame.columns)
    for sector in groups.unique():
        names = groups.index[groups == sector]
        block = frame[names]
        mean = block.mean(axis=1)
        std = block.std(axis=1, ddof=1).replace(0.0, np.nan)
        out[names] = block.sub(mean, axis=0).div(std, axis=0)
    return out


def decile_spreads(signal: pd.DataFrame, forward: pd.DataFrame, config: dict):
    fraction = config["evaluation"]["decile_fraction"]
    minimum = config["evaluation"]["minimum_names"]
    rows = []
    for stamp in signal.index:
        s = signal.loc[stamp].dropna()
        f = forward.loc[stamp].dropna()
        common = s.index.intersection(f.index)
        if len(common) < minimum:
            continue
        s, f = s[common], f[common]
        order = s.sort_values()
        size = max(1, int(len(order) * fraction))
        bottom_names, top_names = order.index[:size], order.index[-size:]
        top, bottom = f[top_names], f[bottom_names]
        # leave out the single largest contributor on each side
        top_trim = top.drop(top.idxmax()) if len(top) > 1 else top
        bottom_trim = bottom.drop(bottom.idxmin()) if len(bottom) > 1 else bottom
        rows.append({
            "date": stamp, "names": len(common),
            "top": float(top.mean()), "bottom": float(bottom.mean()),
            "spread": float(top.mean() - bottom.mean()),
            "spread_trimmed": float(top_trim.mean() - bottom_trim.mean()),
        })
    return pd.DataFrame(rows)


def block_bootstrap_p(spreads: np.ndarray, simulations: int, block: int, seed: int) -> float:
    """Two-sided p under a null of zero mean, resampling blocks to respect overlap."""
    count = len(spreads)
    if count < block * 2:
        return 1.0
    rng = np.random.default_rng(seed)
    centred = spreads - spreads.mean()
    starts = np.arange(count - block + 1)
    observed = abs(spreads.mean())
    hits = 0
    for _ in range(simulations):
        picks = rng.choice(starts, size=int(np.ceil(count / block)))
        sample = np.concatenate([centred[p:p + block] for p in picks])[:count]
        hits += int(abs(sample.mean()) >= observed)
    return hits / simulations


def main() -> int:
    config = json.loads(CONFIG.read_text())
    prices = load_prices(config)
    sectors = sector_map()
    forward = (prices.shift(-config["evaluation"]["forward_weeks"]) / prices - 1.0)

    signals = build_price_signals(prices)
    fundamentals = build_fundamental_signals(prices, ROOT / config["fundamental_panel"])
    signals.update(fundamentals)

    neutral = {name: sector_neutral_z(frame, sectors) for name, frame in signals.items()}

    # composites are built from the already-neutralised components
    def combine(parts: list[str]) -> pd.DataFrame | None:
        available = [neutral[p] for p in parts if p in neutral]
        return sum(available) / len(available) if available else None

    composites = {
        "quality_composite": ["gross_profitability", "return_on_assets", "low_accruals"],
        "value_composite": ["book_to_market", "earnings_yield"],
        "momentum_composite": ["momentum_12_1", "near_52w_high"],
        "defensive_composite": ["low_volatility", "low_beta", "low_max_return"],
    }
    for name, parts in composites.items():
        built = combine(parts)
        if built is not None:
            neutral[name] = built
    qvm = [n for n in ("quality_composite", "value_composite", "momentum_composite") if n in neutral]
    if qvm:
        neutral["quality_value_momentum"] = sum(neutral[n] for n in qvm) / len(qvm)

    sig = config["significance"]
    warmup = config["evaluation"]["warmup_weeks"]
    results, per_signal_rows = {}, []
    for name, frame in neutral.items():
        table = decile_spreads(frame.iloc[warmup:], forward.iloc[warmup:], config)
        if table.empty:
            continue
        spreads = table.spread.to_numpy()
        p_value = block_bootstrap_p(spreads, sig["bootstrap_simulations"], sig["block_weeks"], sig["seed"])
        results[name] = {
            "weeks": int(len(table)),
            "mean_spread": float(spreads.mean()),
            "median_spread": float(np.median(spreads)),
            "mean_top": float(table.top.mean()),
            "mean_bottom": float(table.bottom.mean()),
            "share_weeks_positive": float((spreads > 0).mean()),
            "mean_spread_trimmed": float(table.spread_trimmed.mean()),
            "block_bootstrap_p": p_value,
            "annualised_spread": float(spreads.mean() * (52 / config["evaluation"]["forward_weeks"])),
        }
        for _, r in table.iterrows():
            per_signal_rows.append({"signal": name, **r.to_dict()})

    trials = len(results)
    threshold = sig["alpha"] / trials if trials else sig["alpha"]
    for name, r in results.items():
        r["bonferroni_threshold"] = threshold
        r["survives_bonferroni"] = bool(r["block_bootstrap_p"] < threshold)
        r["passes_all_gates"] = bool(
            r["mean_spread"] > 0 and r["survives_bonferroni"]
            and r["share_weeks_positive"] > 0.50 and r["mean_spread_trimmed"] > 0
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(per_signal_rows).to_csv(OUTPUT / "spreads_by_week.csv.gz", index=False, compression="gzip")
    survivors = [n for n, r in results.items() if r["passes_all_gates"]]
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question": config["question"],
        "signals_run": trials,
        "bonferroni_threshold": threshold,
        "results": results,
        "survivors": survivors,
        "any_survivor": bool(survivors),
        "fundamentals_available": bool(fundamentals),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"signals run: {trials}   Bonferroni threshold p < {threshold:.5f}\n")
    print(f"  {'signal':<30}{'ann.spread':>12}{'weeks+':>9}{'trimmed':>10}{'p':>9}  gate")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["mean_spread"]):
        gate = "PASS" if r["passes_all_gates"] else ""
        print(f"  {name:<30}{100*r['annualised_spread']:>11.2f}%{100*r['share_weeks_positive']:>8.0f}%"
              f"{100*r['mean_spread_trimmed']:>9.2f}%{r['block_bootstrap_p']:>9.4f}  {gate}")
    print(f"\n  survivors: {survivors if survivors else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
