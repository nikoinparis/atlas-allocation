#!/usr/bin/env python3
"""Did any closed family have cross-sectional content the original test missed?

Declared in config/closed_family_monotonicity_registry_v1.json. A diagnostic.

Step 296 found that no dashboard signal orders its deciles, and CLAUDE.md section
2 now demands that measurement before anything is built around a signal. The
fifteen closed families were judged before that rule existed -- mostly as top-N
books, or on an aggregate information coefficient. Neither distinguishes ranking
skill from market beta, which is exactly the confusion Step 295 exposed.

So this asks the question retrospectively. It can find a family closed for the
wrong reason. It cannot re-open one: a family showing monotonicity here would
need its own pre-registered test on a fresh window before it is more than a lead.

Out of scope, and recorded rather than worked around: 13F linkage, PEAD/SUE,
10-K language and fractional differentiation never saved raw cross-sectional
scores and cannot be cheaply rebuilt.
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

REGISTRY = ROOT / "config/closed_family_monotonicity_registry_v1.json"
OUTPUT = ROOT / "evidence/closed_family_monotonicity_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
HORIZON = 4
BONFERRONI = 0.05 / 11


def load_panel():
    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    return prices, returns.where(returns.abs() <= 1.0)


def sectors_for(columns) -> pd.Series:
    frame = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, usecols=["cik10", "sector"]).dropna()
    mapping = frame.groupby("cik10").sector.first()
    return mapping.reindex(columns)


def measure(signal: pd.DataFrame, forward: pd.DataFrame, rng) -> dict:
    """Rank IC, decile spread and monotonicity -- with a density guard.

    Deciles are meaningless on a sparse signal. Form 4 opportunistic purchases
    are exactly zero in 93.3% of cells -- a typical week has 78 names with a
    purchase against 2,591 at zero -- so nine of ten deciles are ties at zero,
    the decile spread degenerates into a presence test, and ranking across the
    whole universe measures "did anyone buy" rather than "how much". Step 286
    declared and tested the intensity question and measured -0.0086 at t=-1.34;
    ranking across all names instead gives +0.0143 at t=+3.78. Both are real and
    they are different questions, which is precisely why the density has to be
    reported next to the result rather than discovered afterwards.
    """
    density = float((signal.notna() & (signal != 0)).sum().sum()
                    / max(1, signal.notna().sum().sum()))
    ics, spreads, monos = [], [], []
    weeks = [w for w in signal.index[::HORIZON] if w in forward.index]
    for week in weeks:
        pair = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week]}).dropna()
        if len(pair) < 60:
            continue
        ics.append(float(pair.s.rank().corr(pair.f.rank())))
        try:
            decile = pd.qcut(pair.s.rank(method="first"), 10, labels=False, duplicates="drop")
        except ValueError:
            continue
        means = pair.f.groupby(decile).mean()
        if len(means) < 10:
            continue
        spreads.append(float(means.iloc[-1] - means.iloc[0]))
        monos.append(float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman")))
    ics = np.array([x for x in ics if np.isfinite(x)])
    if len(ics) < 20:
        return {"decisions": int(len(ics)), "inconclusive": True}
    mean_ic = float(ics.mean())
    t = float(mean_ic / (ics.std(ddof=1) / np.sqrt(len(ics)))) if ics.std(ddof=1) > 0 else float("nan")
    block, draws = 6, []
    for _ in range(3000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean_ic)
    p = float((np.abs(np.array(draws)) >= abs(mean_ic)).mean())
    periods = 52.0 / HORIZON
    spread = float(np.mean(spreads)) if spreads else float("nan")
    return {"decisions": int(len(ics)), "mean_ic": mean_ic, "t_stat": t, "bootstrap_p": p,
            "clears_bonferroni": bool(p < BONFERRONI),
            "nonzero_density": density,
            "deciles_interpretable": bool(density >= 0.50),
            "decile_spread_annualised": float((1 + spread) ** periods - 1) if np.isfinite(spread) else float("nan"),
            "monotonicity": float(np.mean(monos)) if monos else float("nan"),
            "inconclusive": False}


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20260910)
    prices, returns = load_panel()
    forward = (1.0 + returns.fillna(0.0)).rolling(HORIZON).apply(np.prod, raw=True).shift(-HORIZON) - 1.0
    signals: dict[str, pd.DataFrame] = {}

    import run_untried_price_signals_v1 as price
    signals.update(price.build_signals(returns, prices, sectors_for(returns.columns)))
    print(f"price families rebuilt: {len(signals)}")

    try:
        import run_finra_short_volume_v1 as sv
        ratio = sv.weekly_short_ratio(sv.ticker_to_cik(), returns.index)
        signals["short_sale_volume"] = ratio[[c for c in ratio.columns if c in returns.columns]]
        print("short-sale volume rebuilt")
    except Exception as error:                       # noqa: BLE001
        print(f"short-sale volume unavailable: {type(error).__name__}")

    try:
        import run_form4_opportunistic_v1 as f4
        panel = pd.read_csv(f4.PANEL, dtype={"cik10": str, "owner_cik": str},
                            parse_dates=["filing_date", "trans_date"])
        panel = f4.classify(panel[panel.cik10.isin(returns.columns)])
        signals["form4_opportunistic"] = f4.build_signal(panel[~panel.routine], returns.index, 4)
        print("Form 4 opportunistic rebuilt")
    except Exception as error:                       # noqa: BLE001
        print(f"Form 4 unavailable: {type(error).__name__}")

    results = {}
    for name, frame in signals.items():
        aligned = frame.reindex(columns=returns.columns)
        results[name] = measure(aligned, forward, rng)

    print(f"\nclosed-family monotonicity, {HORIZON}-week horizon, Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'family':30s} {'n':>4s} {'dens':>6s} {'mean IC':>9s} {'t':>7s} {'p':>8s} "
          f"{'decile spread':>14s} {'monotone':>9s}")
    for name, r in sorted(results.items(), key=lambda kv: -abs(kv[1].get("monotonicity", 0) or 0)):
        if r.get("inconclusive"):
            print(f"{name:30s} {r['decisions']:>4d}   too few decisions to measure")
            continue
        flag = " *" if r["clears_bonferroni"] else ""
        if not r["deciles_interpretable"]:
            flag += "  <- SPARSE: deciles degenerate, IC is a presence test"
        print(f"{name:30s} {r['decisions']:>4d} {r['nonzero_density']:6.1%} {r['mean_ic']:+9.4f} "
              f"{r['t_stat']:+7.2f} {r['bootstrap_p']:8.4f} "
              f"{r['decile_spread_annualised']:+13.2%} {r['monotonicity']:+9.2f}{flag}")

    usable = {k: v for k, v in results.items() if not v.get("inconclusive")}
    clearing = [k for k, v in usable.items() if v["clears_bonferroni"]]
    monotone = [k for k, v in usable.items()
                if abs(v["monotonicity"]) > 0.5 and v["deciles_interpretable"]]
    sparse = [k for k, v in usable.items() if not v["deciles_interpretable"]]
    print(f"\nfamilies measured: {len(usable)}")
    print(f"clearing Bonferroni {BONFERRONI:.4f}: {len(clearing)}" + (f" -- {clearing}" if clearing else ""))
    print(f"monotonicity above 0.5 with interpretable deciles: {len(monotone)}"
          + (f" -- {monotone}" if monotone else ""))
    if sparse:
        print(f"sparse signals whose decile statistics are NOT interpretable: {sparse}")
    print("\nA family appearing here is a LEAD, not a reopening: it would need its own")
    print("pre-registered test on a fresh window before it is anything more.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "monotonicity.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "horizon_weeks": HORIZON, "bonferroni_bar": BONFERRONI,
        "families_measured": len(usable), "results": results,
        "clearing_bonferroni": clearing, "monotonic_above_half": monotone,
        "sparse_deciles_not_interpretable": sparse,
        "density_guard": "a signal non-zero in under 50% of cells cannot be read on deciles",
        "out_of_scope": ["13F linkage", "PEAD/SUE", "10-K language", "fractional differentiation"],
        "out_of_scope_reason": "raw cross-sectional scores were never saved and cannot be cheaply rebuilt",
        "this_is_a_diagnostic_not_a_search": True, "no_strategy_can_come_out_of_this": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
