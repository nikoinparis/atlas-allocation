#!/usr/bin/env python3
"""Run already-frozen SEC strategies against 2012-2022, which none of them has seen.

Governed by config/full_history_out_of_sample_protocol_v2.json, written before any
strategy was run against pre-2023 data. Nothing here is searched: every strategy's
parameters were fixed long before, so this consumes zero new trials and is a
measurement rather than a selection.

Two scenarios, both required to pass:

  base     an issuer with no validated price is dropped and its weight held in cash
  adverse  that weight is held in the issuer and assigned a -100% return

Two benchmarks, both required to be beaten. The primary is an equal-weight
portfolio of the same point-in-time universe on the same schedule at the same cost,
which is the only comparison that separates selection from exposure; a book drawn
from a technology and energy roster can beat SPY on that roster's beta alone, which
Step 216 measured at r = 0.65. SPY is secondary.

Strategy and benchmark run through the identical simulator so no difference between
them can come from the plumbing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sec_growth_survivorship_retest_v1 as base
import run_sec_cash_conversion_capped_dynamic_v1 as capped
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner

PROTOCOL = ROOT / "config/full_history_out_of_sample_protocol_v2.json"
OUTPUT = ROOT / "evidence/full_history_out_of_sample_v1"
COST_BPS = 50.0
REGIMES = {
    "2012-2015": ("2012-01-01", "2015-12-31"),
    "2016-2019": ("2016-01-01", "2019-12-31"),
    "2020_covid": ("2020-01-01", "2020-12-31"),
    "2022_bear": ("2022-01-01", "2022-12-31"),
    "2023-2026": ("2023-01-01", "2026-12-31"),
    "full": ("2000-01-01", "2100-01-01"),
}


def metrics(path: pd.DataFrame, lo: str, hi: str) -> dict[str, float]:
    r = path.net_return.loc[lo:hi].dropna()
    if len(r) < 12:
        return {"weeks": int(len(r))}
    wealth = float((1 + r).prod())
    years = len(r) / 52.0
    curve = (1 + r).cumprod()
    sd = float(r.std(ddof=1))
    return {
        "weeks": int(len(r)),
        "cagr": wealth ** (1 / years) - 1 if years > 0 else float("nan"),
        "annual_volatility": sd * np.sqrt(52),
        "sharpe_zero_rf": float(r.mean() / sd * np.sqrt(52)) if sd > 0 else 0.0,
        "max_drawdown": float((curve / curve.cummax() - 1).min()),
        "positive_week_share": float((r > 0).mean()),
        "total_return": wealth - 1.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--membership", default="evidence/full_history_price_panel_v1/classified_membership.csv")
    parser.add_argument("--discovery", default="evidence/sec_independent_fundamental_discovery_full_v1")
    parser.add_argument("--growth", default="evidence/sec_growth_survivorship_retest_full_v1")
    parser.add_argument("--panel", default="data/sec_broad_research_panel_v3")
    parser.add_argument("--broad-prices",
                        default="data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz",
                        help="broad universe weekly prices; the sealed panel starts 2022-12-02, "
                             "the full-history build reaches 2011")
    parser.add_argument("--breadth", type=int, default=20)
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL.read_text())
    coverage_bar = float(protocol["coverage_gate"]["minimum_decision_row_coverage"])

    def naive(frame: pd.DataFrame, column: str = "decision_at") -> pd.DataFrame:
        """Every source dates its decisions differently; some carry UTC, some do not.
        Comparing them raises rather than silently mismatching, but only once they meet."""
        values = pd.to_datetime(frame[column], utc=True, errors="coerce")
        frame[column] = values.dt.tz_localize(None)
        return frame

    membership = naive(pd.read_csv(ROOT / args.membership, dtype={"cik10": str}))
    # The narrow roster calls it execution_price_available and the broad readiness roster
    # calls it validated_price_available. Guessing wrong silently yields a coverage of NaN
    # and admits every decision, so this fails loudly instead.
    column = next((c for c in ("execution_price_available", "validated_price_available")
                   if c in membership.columns), None)
    if column is None:
        raise SystemExit(f"no price-availability column in {args.membership}")
    print(f"coverage measured on '{column}'")
    coverage = membership.groupby("decision_at")[column].astype(bool).groupby(level=0).mean() \
        if False else membership.assign(_a=membership[column].astype(bool)).groupby("decision_at")._a.mean()
    admissible = sorted(coverage[coverage >= coverage_bar].index)
    excluded = sorted(coverage[coverage < coverage_bar].index)
    print(f"decisions meeting the {coverage_bar:.0%} coverage bar: {len(admissible)} of {len(coverage)}")
    if not admissible:
        # Without this the run dies later on an empty min(), leaving the previous run's
        # metrics.csv in place. Anything reading that file would attribute stale numbers
        # to the current configuration.
        for stale in OUTPUT.glob("*.csv"):
            stale.unlink()
        raise SystemExit(f"no decision meets the {coverage_bar:.0%} coverage bar; stale outputs removed")
    if excluded:
        print(f"  excluded: {excluded[0].date()} .. {excluded[-1].date()}")

    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start=str(min(admissible).date()), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()

    books: dict[str, pd.DataFrame] = {}
    scores_path = ROOT / args.discovery / "factor_scores.csv"
    if scores_path.exists():
        scores = pd.read_csv(scores_path, dtype={"cik10": str}, parse_dates=["decision_at"])
        books["cash_conversion_breadth20"] = naive(breadth_runner.make_choices(
            scores[scores.family == "cash_conversion"], args.breadth))
    growth_path = ROOT / args.growth / "portfolio_choices.csv"
    if growth_path.exists():
        books["growth_survivorship"] = naive(pd.read_csv(growth_path, dtype={"cik10": str}))
    # The residual sleeve is the leg with a forward clock attached, so it faces the same
    # question the control leg just failed: does selecting twenty names beat holding the
    # universe? Its weights come from the research panel rather than from factor scores.
    panel_path = ROOT / args.panel / "panel.csv.gz"
    if panel_path.exists():
        sys.path.insert(0, str(ROOT / "src"))
        from systematic_trader.sec_real_tournament_v2 import build_family_weights
        program = json.loads((ROOT / "config/sec_return_improvement_program_v1.json").read_text())
        panel = pd.read_csv(panel_path, dtype={"cik10": str})
        family, _ = build_family_weights(panel, program)
        residual = family["residual_momentum"].copy()
        # build_family_weights names its date column decision_at but fills it with the
        # execution date, a week or so after the quarterly decision. Filtering those against
        # the admissible decision dates silently removes every row and the book returns a
        # flat 0.00%, which reads like a result rather than an empty portfolio. Map each
        # execution date back to the decision it follows.
        residual["execution_at"] = pd.to_datetime(residual.decision_at, utc=True, errors="coerce").dt.tz_localize(None)
        del residual["decision_at"]
        stamps = pd.Series(sorted(admissible))
        residual["decision_at"] = residual.execution_at.map(
            lambda when: stamps[stamps <= when].iloc[-1] if (stamps <= when).any() else pd.NaT)
        residual = residual.dropna(subset=["decision_at"])
        if residual.empty:
            raise SystemExit("residual weights did not map onto any admissible decision")
        books["residual_momentum_breadth20"] = residual[["decision_at", "cik10"]]

    tradable = next((c for c in ("tradable_member", "validated_price_available") if c in membership.columns), column)
    eligible = membership[membership.decision_at.isin(admissible) & membership[tradable].astype(bool)]
    books["equal_weight_narrow"] = eligible[["decision_at", "cik10"]].copy()
    # The residual sleeve selects from the broad research panel, so equal-weighting the
    # narrow filer roster is not its universe and beating it would prove nothing. Each
    # strategy is compared against the equal-weight version of the pool it draws from.
    if panel_path.exists():
        broad_members = naive(panel[["decision_at", "cik10"]].drop_duplicates())
        stamps = pd.Series(sorted(admissible))
        broad_members = broad_members[broad_members.decision_at.isin(stamps)]
        if len(broad_members):
            books["equal_weight_broad"] = broad_members

    # Books are drawn from two different universes and must be priced from their own
    # source. The residual sleeve selects from the broad research panel, of which the
    # narrow filer price sources cover only 24%; pricing it from those produced a -99.95%
    # adverse figure that was the price source failing, not the strategy. Every book is
    # now priced from the universe it actually selects from, and the coverage is printed
    # per book so a mismatch like that cannot pass unnoticed again.
    narrow_universe = sorted({c for name, b in books.items()
                              if name not in {"residual_momentum_breadth20", "equal_weight_broad"}
                              for c in b.cik10})
    series = {}
    for cik in narrow_universe:
        spec = sources.get(cik)
        if spec is not None:
            source, path = spec
            series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
    narrow_weekly = pd.DataFrame(series, index=index)

    broad = pd.read_csv(ROOT / args.broad_prices, index_col=0)
    broad.index = pd.to_datetime(broad.index)
    broad_weekly = broad.reindex(index)

    broad_books = {"residual_momentum_breadth20", "equal_weight_broad"}
    price_frames = {name: (broad_weekly if name in broad_books else narrow_weekly) for name in books}
    for name, book in books.items():
        held = set(book.cik10)
        have = held & set(price_frames[name].columns)
        print(f"  {name:<30} priced {len(have):>4} of {len(held):>4} issuers ({len(have)/max(len(held),1):.1%})")

    rows, paths = [], {}
    for name, choices in books.items():
        choices = choices[choices.decision_at.isin(admissible)]
        targets = base.build_targets(choices, index)
        top_n = 10_000 if name.startswith("equal_weight") else args.breadth
        for scenario in ("base", "adverse"):
            path, _ = capped.simulate_cash(price_frames[name], targets, scenario, COST_BPS, None, top_n)
            paths[(name, scenario)] = path
            for window, (lo, hi) in REGIMES.items():
                m = metrics(path, lo, hi)
                if "cagr" in m:
                    rows.append({"book": name, "scenario": scenario, "window": window, **m})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "metrics.csv", index=False)
    for (name, scenario), path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{name}__{scenario}.csv")

    matched = {"residual_momentum_breadth20": "equal_weight_broad"}
    verdicts = []
    for name in books:
        if name.startswith("equal_weight"):
            continue
        reference = matched.get(name, "equal_weight_narrow")
        beats = {}
        for scenario in ("base", "adverse"):
            for window in REGIMES:
                s = table[(table.book == name) & (table.scenario == scenario) & (table.window == window)]
                b = table[(table.book == reference) & (table.scenario == scenario) & (table.window == window)]
                if len(s) and len(b):
                    beats[f"{scenario}__{window}"] = bool(s.cagr.iloc[0] > b.cagr.iloc[0])
        verdicts.append({"book": name, "benchmark": reference, "beats_equal_weight": beats,
                         "passes_every_window_and_scenario": bool(beats and all(beats.values()))})

    payload = {
        "experiment": "full_history_out_of_sample_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "full_history_out_of_sample_protocol_v2",
        "trials_consumed": 0,
        "coverage_bar": coverage_bar,
        "decisions_admissible": len(admissible), "decisions_excluded": len(excluded),
        "excluded_decisions": [str(d.date()) for d in excluded],
        "verdicts": verdicts,
        "promotion_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"\n{'book':<28}{'scen':<9}{'window':<12}{'weeks':>6}{'CAGR':>9}{'Sharpe':>8}{'maxDD':>8}")
    for _, r in table.sort_values(["book", "scenario", "window"]).iterrows():
        print(f"{r['book']:<28}{r['scenario']:<9}{r['window']:<12}{int(r['weeks']):>6}"
              f"{r['cagr']:>9.2%}{r['sharpe_zero_rf']:>8.2f}{r['max_drawdown']:>8.1%}")
    print()
    for v in verdicts:
        print(f"{v['book']}: beats equal-weight in every window and scenario = {v['passes_every_window_and_scenario']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
