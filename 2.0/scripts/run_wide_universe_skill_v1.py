#!/usr/bin/env python3
"""S6: the same skill screen, on every SEC filer we can price instead of 509.

Registered as an extension of config/cross_sectional_skill_registry_v1.json.

The fundamental signals have only ever been measured on about 509 issuers,
because the SEC roster was built for technology and energy. There are 8,510
10-K/10-Q filers in sample quarters and roughly 2,616 of them can be priced from
the panel already on disk. Step 296's own power note says 13-14 quarterly
decisions cannot resolve an information coefficient of 0.03, and a five-fold
deeper cross-section is the one free change that affects that.

**The universe is the only variable.** Same three signals, same features, same
minimum feature counts, same sector-neutral ranking, same 13-week horizon, same
density guard, same measurements. Sector becomes the SIC two-digit major group
taken from the filing itself, so ranking stays sector-neutral and point-in-time
where the previous run mapped 38 hand-picked codes onto two sectors.

Recorded before running, because it is the honest prior: Step 298 measured eight
price-signal families on the full 2,810-name panel and found nothing. A wide
universe did not rescue price signals.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import build_dashboard_signals_out_of_sample_v1 as oos
import run_closed_family_monotonicity_v1 as screen

OUTPUT = ROOT / "evidence/wide_universe_skill_v1"
HORIZON = 13
BONFERRONI = 0.05 / 3


def build_facts_wide() -> pd.DataFrame:
    """oos.build_facts with the sector restriction removed and SIC2 as the sector."""
    frames = []
    for path in sorted(oos.FSDS.glob("*.zip")):
        quarter = oos.read_quarter(path)
        if quarter is not None and not quarter.empty:
            frames.append(quarter)
    facts = pd.concat(frames, ignore_index=True)
    facts["filed"] = pd.to_datetime(facts.filed, format="%Y%m%d", errors="coerce", utc=True)
    facts["ddate"] = pd.to_datetime(facts.ddate, format="%Y%m%d", errors="coerce", utc=True)
    facts = facts.dropna(subset=["filed", "ddate", "value", "sic"])
    facts["cik10"] = facts.cik.astype("int64").astype(str).str.zfill(10)
    # Sector-neutral ranking still needs a sector. SIC major group is on the filing,
    # so it is point-in-time and it covers the whole market rather than 38 codes.
    facts["sector"] = facts.sic.astype("int64").astype(str).str.zfill(4).str[:2]

    inverse = {tag: field for field, tags in oos.TAGS.items() for tag in tags}
    facts["field"] = facts.tag.map(inverse)
    facts = facts[((facts.field.isin(oos.FLOW)) & (facts.qtrs == 4))
                  | ((~facts.field.isin(oos.FLOW)) & (facts.qtrs == 0))]
    ranked = facts.sort_values(["cik10", "filed", "ddate"])
    wide = (ranked.groupby(["cik10", "sector", "filed", "field"]).value.last()
            .unstack("field").reset_index())
    return wide.sort_values(["cik10", "filed"])


def main() -> int:
    rng = np.random.default_rng(20260910)
    prices, returns = screen.load_panel()
    forward = (1.0 + returns.fillna(0.0)).rolling(HORIZON).apply(
        np.prod, raw=True).shift(-HORIZON) - 1.0

    facts = oos.add_features(build_facts_wide())
    priceable = facts[facts.cik10.isin(returns.columns)]
    print(f"FSDS filers with usable facts: {facts.cik10.nunique():,}")
    print(f"of those priceable from the panel: {priceable.cik10.nunique():,}")
    print(f"sectors (SIC major groups): {priceable.sector.nunique()}")
    print(f"the narrow run measured 509 issuers across 2 sectors\n")
    facts = priceable

    decisions = pd.date_range("2013-04-01", "2022-10-01", freq="QS", tz="UTC")
    results, coverage_note = {}, {}
    for name, spec in oos.SIGNALS.items():
        pairs, sizes = [], []
        for decision in decisions:
            known = facts[facts.filed < decision]
            if known.empty:
                continue
            latest = known.sort_values("filed").groupby("cik10").last()
            latest = latest[latest.index.isin(returns.columns)]
            if len(latest) < 100:
                continue
            scored = oos.score(latest, spec).dropna()
            execution = returns.index[returns.index > decision]
            if len(scored) < 100 or not len(execution):
                continue
            week = execution[0]
            position = returns.index.get_indexer([week])[0]
            if position < 0 or position + HORIZON >= len(returns.index) or week not in forward.index:
                continue
            pairs.append((scored, forward.loc[week].reindex(scored.index)))
            sizes.append(len(scored))
        if len(pairs) < 8:
            results[name] = {"inconclusive": True, "decisions": len(pairs)}
            continue
        frame = pd.DataFrame({d: s for d, (s, _) in enumerate(pairs)}).T
        fwd = pd.DataFrame({d: f for d, (_, f) in enumerate(pairs)}).T
        results[name] = screen_measure(frame, fwd, rng)
        coverage_note[name] = int(np.median(sizes))

    print(f"wide-universe skill, {HORIZON}-week horizon, Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'signal':30s} {'n':>4s} {'names':>7s} {'mean IC':>9s} {'t':>7s} {'p':>8s} "
          f"{'decile spread':>14s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:30s} {r['decisions']:>4d}   too few decisions")
            continue
        flag = " *" if r["bootstrap_p"] < BONFERRONI else ""
        if not r["deciles_interpretable"]:
            flag += "  <- SPARSE"
        print(f"{name:30s} {r['decisions']:>4d} {coverage_note.get(name, 0):>7d} "
              f"{r['mean_ic']:+9.4f} {r['t_stat']:+7.2f} {r['bootstrap_p']:8.4f} "
              f"{r['decile_spread_annualised']:+13.2%} {r['monotonicity']:+9.2f}{flag}")

    usable = {k: v for k, v in results.items() if not v.get("inconclusive")}
    monotone = [k for k, v in usable.items()
                if abs(v["monotonicity"]) > 0.5 and v["deciles_interpretable"]]
    clearing = [k for k, v in usable.items() if v["bootstrap_p"] < BONFERRONI]
    print(f"\nsignals measured: {len(usable)}")
    print(f"clearing Bonferroni {BONFERRONI:.4f}: {len(clearing)}" + (f" -- {clearing}" if clearing else ""))
    print(f"monotonicity above 0.5 with interpretable deciles: {len(monotone)}"
          + (f" -- {monotone}" if monotone else ""))
    print("\nnarrow-universe comparison (Step 296, 509 issuers):")
    print("  growth_top5 IC -0.0053 monotone -0.05 | cash_conversion +0.0272 +0.01 | "
          "balance_sheet +0.0008 -0.00")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "skill.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "horizon_weeks": HORIZON, "bonferroni_bar": BONFERRONI,
        "issuers_priceable": int(facts.cik10.nunique()),
        "sectors": int(facts.sector.nunique()),
        "median_names_scored": coverage_note,
        "results": results, "clearing_bonferroni": clearing,
        "monotonic_above_half": monotone,
        "only_variable_changed": "the universe",
        "narrow_run_reference": "Step 296, 509 issuers, 2 sectors",
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


def screen_measure(scores: pd.DataFrame, forwards: pd.DataFrame, rng) -> dict:
    """Same measurements as Step 296/298, including the Step 298 density guard."""
    density = float((scores.notna() & (scores != 0)).sum().sum()
                    / max(1, scores.notna().sum().sum()))
    ics, spreads, monos = [], [], []
    for row in scores.index:
        pair = pd.DataFrame({"s": scores.loc[row], "f": forwards.loc[row]}).dropna()
        if len(pair) < 100:
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
    if len(ics) < 8:
        return {"inconclusive": True, "decisions": int(len(ics))}
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
    return {"decisions": int(len(ics)), "mean_ic": mean_ic, "t_stat": t, "bootstrap_p": p,
            "nonzero_density": density, "deciles_interpretable": bool(density >= 0.50),
            "decile_spread_annualised": float((1 + spread) ** periods - 1) if np.isfinite(spread) else float("nan"),
            "monotonicity": float(np.mean(monos)) if monos else float("nan"),
            "inconclusive": False}


if __name__ == "__main__":
    raise SystemExit(main())
