#!/usr/bin/env python3
"""Has any signal in this project ever had cross-sectional skill?

Declared in config/cross_sectional_skill_registry_v1.json. A diagnostic, not a
search: nothing here can become a strategy.

Step 295 is the reason it exists. Neutralising the market took cash conversion
from 16.65% to 1.59% out of sample, so roughly ninety per cent of the one
positive result in Step 289's nought-of-six table was market beta. Every signal
here has only ever been judged on whether its top twenty beat a benchmark, and
beta alone does that. None has been judged on whether the BOTTOM of its ranking
underperforms, which is what cross-sectional skill means.

Three beta-neutral measurements per signal, on both windows:

    rank IC        Spearman of rank against the next 13 weeks. Adding a constant
                   market return to every name leaves the ranking untouched.
    decile spread  top decile minus bottom decile, both legs carrying the same
                   market exposure.
    monotonicity   Spearman of decile number against decile mean return. A top
                   decile that wins while two through nine are unordered is a
                   concentration effect, not skill, and only this catches that.
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

REGISTRY = ROOT / "config/cross_sectional_skill_registry_v1.json"
OUTPUT = ROOT / "evidence/cross_sectional_skill_v1"
SAVED_PANELS = {
    "fundamental": ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv",
    "valuation": ROOT / "evidence/sec_survivorship_valuation_discovery_v1/factor_scores.csv",
}
HORIZON = 13
BONFERRONI = 0.05 / 13


def forward_returns(returns: pd.DataFrame, week: pd.Timestamp, horizon: int) -> pd.Series | None:
    position = returns.index.get_indexer([week])[0]
    if position < 0 or position + horizon >= len(returns.index):
        return None
    block = returns.iloc[position + 1:position + 1 + horizon]
    return (1.0 + block).prod() - 1.0


def measure(pairs: list[tuple[pd.Series, pd.Series]], rng: np.random.Generator) -> dict:
    """pairs is a list of (score, forward return) aligned Series, one per decision."""
    ics, spreads, monos = [], [], []
    for score, forward in pairs:
        both = pd.concat({"s": score, "f": forward}, axis=1).dropna()
        if len(both) < 30:
            continue
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
    if len(ics) < 8:
        return {"decisions": int(len(ics)), "inconclusive": True}
    mean_ic = float(ics.mean())
    t = float(mean_ic / (ics.std(ddof=1) / np.sqrt(len(ics)))) if ics.std(ddof=1) > 0 else float("nan")
    block, draws = 4, []
    for _ in range(4000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean_ic)
    p = float((np.abs(np.array(draws)) >= abs(mean_ic)).mean())
    periods = 52.0 / HORIZON
    spread = float(np.mean(spreads)) if spreads else float("nan")
    return {
        "decisions": int(len(ics)), "mean_ic": mean_ic, "t_stat": t, "bootstrap_p": p,
        "clears_bonferroni": bool(p < BONFERRONI),
        "decile_spread_per_period": spread,
        "decile_spread_annualised": float((1.0 + spread) ** periods - 1.0) if np.isfinite(spread) else float("nan"),
        "monotonicity": float(np.mean(monos)) if monos else float("nan"),
        "inconclusive": False,
    }


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20260910)
    prices = oos.load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    results: dict[str, dict] = {}

    # ---- Window A: out of sample, rebuilt from FSDS -------------------------
    facts = oos.add_features(oos.build_facts())
    facts = facts[facts.cik10.isin(prices.columns)]
    decisions = pd.date_range("2013-04-01", "2022-10-01", freq="QS", tz="UTC")
    for name, spec in oos.SIGNALS.items():
        pairs = []
        for decision in decisions:
            known = facts[facts.filed < decision]
            if known.empty:
                continue
            latest = known.sort_values("filed").groupby("cik10").last()
            latest = latest[latest.index.isin(returns.columns)]
            if len(latest) < 60:
                continue
            scored = oos.score(latest, spec).dropna()
            execution = returns.index[returns.index > decision]
            if len(scored) < 60 or not len(execution):
                continue
            forward = forward_returns(returns, execution[0], HORIZON)
            if forward is None:
                continue
            pairs.append((scored, forward.reindex(scored.index)))
        results[f"OOS 2013-2022 | {name}"] = measure(pairs, rng)

    # ---- Window B: in sample, from the saved factor score panels ------------
    for panel_name, path in SAVED_PANELS.items():
        if not path.is_file():
            continue
        panel = pd.read_csv(path, dtype={"cik10": str})
        panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
        for family, block in panel.groupby("family"):
            pairs = []
            for decision, frame in block.groupby("decision_at"):
                scored = frame.dropna(subset=["score"]).set_index("cik10").score
                scored = scored[scored.index.isin(returns.columns)]
                execution = returns.index[returns.index > decision]
                if len(scored) < 60 or not len(execution):
                    continue
                forward = forward_returns(returns, execution[0], HORIZON)
                if forward is None:
                    continue
                pairs.append((scored, forward.reindex(scored.index)))
            results[f"IN 2023-2026 | {family}"] = measure(pairs, rng)

    print(f"cross-sectional skill, {HORIZON}-week horizon, Bonferroni bar p < {BONFERRONI:.4f}\n")
    print(f"{'signal':40s} {'n':>4s} {'mean IC':>9s} {'t':>7s} {'p':>8s} "
          f"{'decile spread':>14s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:40s} {r['decisions']:>4d}   too few decisions to measure")
            continue
        flag = " *" if r["clears_bonferroni"] else ""
        print(f"{name:40s} {r['decisions']:>4d} {r['mean_ic']:+9.4f} {r['t_stat']:+7.2f} "
              f"{r['bootstrap_p']:8.4f} {r['decile_spread_annualised']:+13.2%} "
              f"{r['monotonicity']:+9.2f}{flag}")

    usable = {k: v for k, v in results.items() if not v.get("inconclusive")}
    clearing = [k for k, v in usable.items() if v["clears_bonferroni"]]
    positive_and_monotone = [k for k, v in usable.items()
                             if v["mean_ic"] > 0 and v["monotonicity"] > 0.5]
    print(f"\nsignals measured: {len(usable)}")
    print(f"clearing Bonferroni {BONFERRONI:.4f}: {len(clearing)}"
          + (f" -- {clearing}" if clearing else ""))
    print(f"positive IC AND monotonic above 0.5: {len(positive_and_monotone)}"
          + (f" -- {positive_and_monotone}" if positive_and_monotone else ""))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "skill.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "horizon_weeks": HORIZON, "bonferroni_bar": BONFERRONI,
        "signals_measured": len(usable), "results": results,
        "clearing_bonferroni": clearing,
        "positive_ic_and_monotonic": positive_and_monotone,
        "this_is_a_diagnostic_not_a_search": True,
        "no_strategy_can_come_out_of_this": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
