#!/usr/bin/env python3
"""Family B of the breadth-first registry: year-over-year accounting changes.

Four configurations, declared in config/breadth_first_signal_registry_v1.json
before any of them was computed. The registry states in advance that this family
is expected to fail: eleven usable quarterly decisions after a year-over-year lag
cannot support a portfolio backtest, so none is run and the measurement is a
sector-neutral rank information coefficient against the panel's existing forward
label.

Equity, revenue and assets come from the rebuilt quarterly factor inputs. Income
tax and inventory are absent from those and come from the targeted extraction in
`extract_tax_inventory_inputs_v1.py`, which applies the same availability rule.

All four use one definition of change so the comparison is like for like: the
four-quarter difference of a quantity, scaled by assets where the quantity is a
level rather than a ratio.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/breadth_first_signal_registry_v1.json"
INPUTS = ROOT / "evidence/sec_independent_fundamental_discovery_v1/quarterly_factor_inputs.csv"
EXTRA = ROOT / "evidence/tax_inventory_inputs_v1/tax_inventory_inputs.csv"
PANEL = ROOT / "data/sec_broad_research_panel_v3/panel.csv.gz"
OUTPUT = ROOT / "evidence/accounting_change_breadth_v1"
MIN_NAMES = 50


def load() -> pd.DataFrame:
    base = pd.read_csv(INPUTS, low_memory=False, dtype={"cik10": str},
                       usecols=["decision_time", "cik10", "equity", "revenue", "assets"])
    base["decision_at"] = pd.to_datetime(base.decision_time, utc=True, errors="coerce").dt.tz_localize(None)
    if EXTRA.exists():
        extra = pd.read_csv(EXTRA, dtype={"cik10": str})
        extra["decision_at"] = pd.to_datetime(extra.decision_time, utc=True, errors="coerce").dt.tz_localize(None)
        base = base.merge(extra.drop(columns=["decision_time"]), on=["decision_at", "cik10"], how="left")
    panel = pd.read_csv(PANEL, dtype={"cik10": str},
                        usecols=["decision_at", "cik10", "sector", "future_sector_relative_return"])
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True, errors="coerce").dt.tz_localize(None)
    panel = panel.dropna(subset=["future_sector_relative_return"])
    return base.merge(panel, on=["decision_at", "cik10"], how="inner").sort_values(["cik10", "decision_at"])


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("cik10")
    assets = df.assets.replace(0, np.nan)
    df["B1_ChEQ"] = (df.equity - g.equity.shift(4)) / assets
    turnover = df.revenue / assets
    df["_t"] = turnover
    df["B2_ChAssetTurnover"] = turnover - df.groupby("cik10")._t.shift(4)
    if "income_tax" in df:
        df["B3_ChTax"] = (df.income_tax - g.income_tax.shift(4)) / assets
    if "inventory" in df:
        inv = df.inventory / assets
        df["_i"] = inv
        df["B4_ChInv"] = inv - df.groupby("cik10")._i.shift(4)
    return df


def information_coefficient(df: pd.DataFrame, column: str) -> dict[str, object]:
    ics = []
    for _, block in df.dropna(subset=[column]).groupby("decision_at"):
        b = block.copy()
        b["s"] = b.groupby("sector")[column].rank(pct=True)
        b["y"] = b.groupby("sector").future_sector_relative_return.rank(pct=True)
        if len(b) >= MIN_NAMES and b.s.nunique() > 5:
            value = stats.spearmanr(b.s, b.y).statistic
            if np.isfinite(value):
                ics.append(float(value))
    if len(ics) < 3:
        return {"decisions": len(ics), "status": "insufficient decisions"}
    ics = np.array(ics)
    t = float(ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics))))
    p = float(2 * (1 - stats.t.cdf(abs(t), len(ics) - 1)))
    return {"decisions": int(len(ics)), "observations": int(df[column].notna().sum()),
            "mean_rank_ic": float(ics.mean()), "t_stat": t, "p_value": p}


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    trials = int(registry["declared_configuration_count"])
    threshold = 0.05 / trials

    df = add_signals(load())
    rows = []
    for spec in registry["family_b_accounting_change"]["configurations"]:
        column = f"{spec['id']}_{spec['signal']}"
        if column not in df.columns:
            rows.append({"config": spec["id"], "signal": spec["signal"], "status": "quantity unavailable"})
            continue
        result = information_coefficient(df, column)
        result.update({"config": spec["id"], "signal": spec["signal"]})
        if "p_value" in result:
            result["passes_bonferroni"] = bool(result["p_value"] < threshold)
        rows.append(result)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT / "information_coefficients.csv", index=False)
    payload = {
        "experiment": "accounting_change_breadth_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "declared_trials": trials, "bonferroni_threshold": threshold,
        "measured_as": "sector-neutral rank information coefficient; no backtest was run",
        "why_no_backtest": registry["family_b_accounting_change"]["measured_as"],
        "configurations_passing": int(sum(1 for r in rows if r.get("passes_bonferroni"))),
        "results": rows,
        "cumulative_trial_warning": registry["cumulative_trial_accounting"],
        "promotion_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"{'cfg':<5}{'signal':<20}{'decisions':>10}{'obs':>8}{'mean IC':>10}{'t':>8}{'p':>10}{'Bonf':>7}")
    for r in rows:
        if "mean_rank_ic" not in r:
            print(f"{r['config']:<5}{r['signal']:<20}{r.get('status','-'):>43}"); continue
        print(f"{r['config']:<5}{r['signal']:<20}{r['decisions']:>10}{r['observations']:>8}"
              f"{r['mean_rank_ic']:>10.4f}{r['t_stat']:>8.2f}{r['p_value']:>10.4f}"
              f"{'PASS' if r['passes_bonferroni'] else 'FAIL':>7}")
    print(f"\nBonferroni threshold over {trials} declared trials: p < {threshold:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
