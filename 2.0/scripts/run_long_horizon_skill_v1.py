#!/usr/bin/env python3
"""S8: does anything order its deciles over a year or two, where a quarter shows nothing?

Registered as an extension of config/cross_sectional_skill_registry_v1.json.

Every skill screen in this project used 4 or 13 weeks -- Steps 296, 298, 299,
300 and 302 without exception. Longer windows appear in the codebase only as
signal lookbacks, never as the forward horizon being predicted.

The reason to test it is structural, not statistical. Step 301 established that a
small operator cannot compete on speed, market making, breadth or data. The one
asymmetry left is holding period: a fund that underperforms for three years loses
its capital, and an individual with no redemptions does not. That is a constraint
the incumbents have and we do not. It also fits the evidence -- value and quality
effects are documented to work over years and fail over quarters, and every
horizon tried here sits where they are weakest.

**The overlap problem, stated before any number exists.** A 104-week horizon on a
2013-2022 window cannot give many independent observations. Quarterly decisions
at that horizon overlap seven subsequent ones; taking only non-overlapping ones
would leave about five. Neither is a real sample. This uses overlapping decisions
with a block bootstrap sized to the HORIZON rather than the four weeks earlier
screens used, and reports the non-overlapping count alongside n so the effective
sample is visible. The significance test is badly underpowered by construction.
Monotonicity decides, because it reads the shape of the relationship rather than
its significance.
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
import build_dashboard_signals_out_of_sample_v1 as oos
import run_wide_universe_skill_v1 as wide

OUTPUT = ROOT / "evidence/long_horizon_skill_v1"
HORIZONS = [52, 104]
BONFERRONI = 0.05 / 6


def measure(pairs, horizon: int, rng) -> dict:
    ics, spreads, monos, widths = [], [], [], []
    for score, forward in pairs:
        both = pd.concat({"s": score, "f": forward}, axis=1).dropna()
        if len(both) < 100:
            continue
        widths.append(len(both))
        ics.append(float(both.s.rank().corr(both.f.rank())))
        try:
            decile = pd.qcut(both.s.rank(method="first"), 10, labels=False, duplicates="drop")
        except ValueError:
            continue
        means = both.f.groupby(decile).mean()
        if len(means) < 10:
            continue
        spreads.append(float(means.iloc[-1] - means.iloc[0]))
        monos.append(float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman")))
    ics = np.array([x for x in ics if np.isfinite(x)])
    if len(ics) < 12:
        return {"decisions": int(len(ics)), "inconclusive": True}
    mean_ic = float(ics.mean())
    t = float(mean_ic / (ics.std(ddof=1) / np.sqrt(len(ics)))) if ics.std(ddof=1) > 0 else float("nan")
    # Block sized to the horizon in DECISIONS, not the 4 weeks earlier screens used.
    # Decisions are quarterly, so a 52-week horizon overlaps 4 of them and 104 overlaps 8.
    block = max(2, horizon // 13)
    draws = []
    for _ in range(4000):
        if len(ics) <= block:
            break
        starts = rng.integers(0, len(ics) - block, size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean_ic)
    p = float((np.abs(np.array(draws)) >= abs(mean_ic)).mean()) if draws else float("nan")
    spread = float(np.mean(spreads)) if spreads else float("nan")
    years = horizon / 52.0
    return {
        "decisions": int(len(ics)),
        "non_overlapping_equivalent": int(len(ics) / max(1, block)),
        "median_names": int(np.median(widths)),
        "mean_ic": mean_ic, "t_stat": t, "bootstrap_p": p, "block_decisions": block,
        "clears_bonferroni": bool(np.isfinite(p) and p < BONFERRONI),
        "decile_spread_over_horizon": spread,
        "decile_spread_annualised": float((1 + spread) ** (1 / years) - 1) if np.isfinite(spread) and spread > -1 else float("nan"),
        "monotonicity": float(np.mean(monos)) if monos else float("nan"),
        "deciles_interpretable": True, "inconclusive": False,
    }


def main() -> int:
    rng = np.random.default_rng(20260911)
    prices, returns = None, None
    prices = oos.load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)

    facts = oos.add_features(wide.build_facts_wide())
    facts = facts[facts.cik10.isin(returns.columns)]
    print(f"universe: {facts.cik10.nunique():,} priceable filers, "
          f"{facts.sector.nunique()} SIC major groups")
    print(f"panel: {len(returns)} weeks ({returns.index.min().date()} -> {returns.index.max().date()})\n")

    results = {}
    for horizon in HORIZONS:
        forward = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(
            np.prod, raw=True).shift(-horizon) - 1.0
        decisions = pd.date_range("2013-04-01", "2022-10-01", freq="QS", tz="UTC")
        for name, spec in oos.SIGNALS.items():
            pairs = []
            for decision in decisions:
                known = facts[facts.filed < decision]
                if known.empty:
                    continue
                latest = known.sort_values("filed").groupby("cik10").last()
                latest = latest[latest.index.isin(returns.columns)]
                if len(latest) < 200:
                    continue
                scored = oos.score(latest, spec).dropna()
                execution = returns.index[returns.index > decision]
                if len(scored) < 200 or not len(execution):
                    continue
                week = execution[0]
                position = returns.index.get_indexer([week])[0]
                if position < 0 or position + horizon >= len(returns.index) or week not in forward.index:
                    continue
                pairs.append((scored, forward.loc[week].reindex(scored.index)))
            results[f"{name} @ {horizon}w"] = measure(pairs, horizon, rng)

    print(f"long-horizon skill, Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'signal @ horizon':36s} {'n':>4s} {'indep':>6s} {'names':>6s} {'mean IC':>9s} "
          f"{'t':>7s} {'p':>8s} {'spread/yr':>11s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:36s} {r['decisions']:>4d}   too few decisions to measure")
            continue
        flag = " *" if r["clears_bonferroni"] else ""
        print(f"{name:36s} {r['decisions']:>4d} {r['non_overlapping_equivalent']:>6d} "
              f"{r['median_names']:>6d} {r['mean_ic']:+9.4f} {r['t_stat']:+7.2f} "
              f"{r['bootstrap_p']:8.4f} {r['decile_spread_annualised']:+10.2%} "
              f"{r['monotonicity']:+9.2f}{flag}")

    usable = {k: v for k, v in results.items() if not v.get("inconclusive")}
    monotone = [k for k, v in usable.items() if abs(v["monotonicity"]) > 0.5]
    clearing = [k for k, v in usable.items() if v["clears_bonferroni"]]
    print(f"\nmeasured: {len(usable)} of {len(results)}")
    print(f"clearing Bonferroni {BONFERRONI:.4f}: {len(clearing)}" + (f" -- {clearing}" if clearing else ""))
    print(f"monotonicity above 0.5: {len(monotone)}" + (f" -- {monotone}" if monotone else ""))
    print("\nshorter horizons, Steps 296-302: nought of 27 signals ordered their deciles,")
    print("monotonicity within 0.17 of zero for every one, at 1, 4 and 13 weeks.")
    print("`indep` is n divided by the horizon's overlap; it is the honest sample size.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "skill.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "horizons": HORIZONS, "bonferroni_bar": BONFERRONI, "results": results,
        "clearing_bonferroni": clearing, "monotonic_above_half": monotone,
        "overlap_declared_before_running": True,
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
