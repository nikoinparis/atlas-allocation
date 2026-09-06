#!/usr/bin/env python3
"""Audit every strategy the dashboard displays, for realism rather than return.

Step 234 found that the residual sleeve selected twenty names from a tie of
fifty-nine by lowest CIK -- a defect that survived all the way into a frozen
forward protocol because nobody had looked at a book by eye.  That raises the
obvious question about everything else on the dashboard, and this answers it.

Five checks, run on each displayed strategy, none of them about whether the
return is large:

  leverage      is the headline number levered, and what is it unlevered
  window        how much history is behind the CAGR, and is it one regime
  tie structure how many candidates tie at the score that decides the last slot
  leave-one-out how much of the result is one company
  cost          the ladder the project already requires

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader import sec_tournament_rehearsal as engine

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"

STRATEGIES: dict[str, dict] = {
    "sec-cash-conversion-breadth20-dynamic-v1": {
        "display": "102% Daily-Audited (Dynamic Breadth-20)",
        "paths": {bps: f"evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__{bps}bps.csv"
                  for bps in (50, 100, 200)},
        "book": ("evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv",
                 "decision_at", "cik10"),
        "scores": ("factor_scores", "cash_conversion"),
        "breadth": 20,
        "displayed_leverage": 1.0,
    },
    "sec-growth-survivorship-aware-v1": {
        "display": "142% Growth / Micron",
        "paths": {bps: f"evidence/sec_growth_survivorship_retest_v1/path_growth__base__{bps}bps.csv"
                  for bps in (50, 100, 200)},
        "book": ("evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv",
                 "decision_at", "cik10"),
        "scores": ("growth_scores", None),
        "breadth": 5,
        "displayed_leverage": 1.0,
    },
    "sec-sector-aware-signal-ensemble-v1": {
        "display": "124% Sector Ensemble",
        "paths": {bps: f"evidence/sec_sector_aware_signal_ensemble_v1/selected_path__{bps}bps.csv"
                  for bps in (50, 100, 200)},
        "book": ("evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv",
                 "rebalance_at", "cik10"),
        "scores": None,
        "breadth": None,
        "displayed_leverage": 1.0,
    },
    "sec-sector-ensemble-fragile-1.35x-v1": {
        "display": "174.97% Fragile 1.35x",
        "paths": {bps: f"evidence/sec_sector_aware_signal_ensemble_v1/selected_path__{bps}bps.csv"
                  for bps in (50, 100, 200)},
        "book": ("evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv",
                 "rebalance_at", "cik10"),
        "scores": None,
        "breadth": None,
        "displayed_leverage": 1.35,
        "financing_rate": 0.06,
    },
    "sec-residual-controlled-1.25x-5pct-v1": {
        "display": "150.86% Residual 1.25x",
        "paths": {50: "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv"},
        "book": None,
        "scores": None,
        "breadth": 20,
        "displayed_leverage": 1.25,
        "financing_rate": 0.05,
    },
    "candidate-return-first-60-40-forward-v1": {
        "display": "ETF Incumbent - Return-First 60/40",
        "paths": {},
        "book": ("evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv", None, None),
        "scores": None,
        "breadth": None,
        "displayed_leverage": 1.0,
    },
}

REGIMES = {
    "global_financial_crisis_2008_2009": ("2008-01-01", "2009-12-31"),
    "covid_2020": ("2020-01-01", "2020-12-31"),
    "recent_52w": None,
    "recent_104w": None,
}


def read_path(path: Path) -> pd.Series | None:
    if not path.is_file():
        return None
    frame = pd.read_csv(path)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column])
    frame = frame.set_index(column).sort_index()
    for candidate in ("net_return", "return", "net", frame.columns[0]):
        if candidate in frame.columns:
            return pd.to_numeric(frame[candidate], errors="coerce").dropna()
    return None


def ladder(series: pd.Series) -> dict[str, float]:
    full = engine.metrics(series)
    out = {
        "weeks": int(len(series)),
        "years": round(len(series) / 52.0, 2),
        "start": str(series.index.min().date()),
        "end": str(series.index.max().date()),
        "cagr": float(full["cagr"]),
        "sharpe": float(full["sharpe"]),
        "annualised_volatility": float(series.std(ddof=1) * np.sqrt(52)),
        "max_drawdown": float(full["max_drawdown"]),
    }
    for name, window in REGIMES.items():
        if window is None:
            weeks = 52 if name.endswith("52w") else 104
            piece = series.tail(weeks)
        else:
            piece = series.loc[(series.index >= window[0]) & (series.index <= window[1])]
        if len(piece) >= 8:
            m = engine.metrics(piece)
            out[f"{name}__cagr"] = float(m["cagr"])
            out[f"{name}__max_drawdown"] = float(m["max_drawdown"])
        else:
            out[f"{name}__cagr"] = None
            out[f"{name}__weeks"] = int(len(piece))
    return out


def lever(series: pd.Series, multiplier: float, financing_rate: float) -> pd.Series:
    """The saved paths are unlevered; the dashboard headline applies leverage to them."""
    borrowed = max(0.0, multiplier - 1.0)
    return multiplier * series - borrowed * financing_rate / 52.0


def random_book_null(book: pd.DataFrame, weekly: pd.DataFrame, cost_bps: int,
                     draws: int, seed: int = 20260905) -> dict[str, object]:
    """Same sizes, same rebalance dates, names drawn at random from the same panel.

    This is the placebo control the operating rules require, and unlike a tie
    audit it needs no score file, so it applies to every strategy with a book.
    """
    universe = [c for c in weekly.columns if weekly[c].notna().any()]
    rng = np.random.default_rng(seed)
    sizes = book.groupby("decision_at").cik10.count()
    actual, _ = engine.portfolio_path(book, weekly, cost_bps)
    actual_full = float(engine.metrics(actual)["cagr"])
    actual_recent = float(engine.metrics(actual.tail(52))["cagr"])
    fulls, recents = [], []
    for _ in range(draws):
        rows = []
        for decision, size in sizes.items():
            picks = rng.choice(len(universe), size=int(size), replace=False)
            weight = 1.0 / int(size)
            rows.extend({"decision_at": decision, "cik10": universe[i], "weight": weight} for i in picks)
        path, _ = engine.portfolio_path(pd.DataFrame(rows), weekly, cost_bps)
        fulls.append(float(engine.metrics(path)["cagr"]))
        recents.append(float(engine.metrics(path.tail(52))["cagr"]))
    return {
        "draws": draws,
        "strategy_full_cagr": actual_full,
        "strategy_recent_52w_cagr": actual_recent,
        "random_full_cagr_p50": float(np.median(fulls)),
        "random_full_cagr_p95": float(np.quantile(fulls, 0.95)),
        "random_recent_cagr_p50": float(np.median(recents)),
        "random_recent_cagr_p95": float(np.quantile(recents, 0.95)),
        "percentile_full": float(np.mean([v < actual_full for v in fulls])),
        "percentile_recent": float(np.mean([v < actual_recent for v in recents])),
        "beats_a_coin_flip_full": bool(np.mean([v < actual_full for v in fulls]) > 0.95),
        "beats_a_coin_flip_recent": bool(np.mean([v < actual_recent for v in recents]) > 0.95),
    }


def tie_structure(scores: pd.DataFrame, breadth: int) -> dict[str, float]:
    pools, cands = [], []
    for _, frame in scores.groupby("decision_at"):
        valid = frame.dropna(subset=["score"])
        if len(valid) < breadth:
            continue
        cutoff = valid.score.sort_values(ascending=False).iloc[breadth - 1]
        pools.append(int((valid.score >= cutoff).sum()))
        cands.append(len(valid))
    if not pools:
        return {"decisions_measured": 0}
    return {
        "decisions_measured": len(pools),
        "median_candidates": float(np.median(cands)),
        "median_tie_pool_at_cutoff": float(np.median(pools)),
        "worst_tie_pool_at_cutoff": int(max(pools)),
        "slots": breadth,
        "selection_is_arbitrary": bool(np.median(pools) > breadth),
        "median_share_of_slots_decided_by_the_tiebreak": round(
            max(0.0, (np.median(pools) - breadth)) / max(1, np.median(pools)), 4),
    }


def align_to_execution(book: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    """Map each book date to the first panel week strictly after it.

    The saved books carry quarterly *decision* dates like 2023-01-01, which are
    not weeks. portfolio_path schedules on exact index matches, so passing them
    through unmapped silently produces a book that never rebalances and a path
    of zeros -- which is what the first run of this audit did, and why every
    reconstruction here is checked against its saved path before being used.
    """
    index = weekly.index
    mapping = {}
    for value in sorted(book.decision_at.unique()):
        later = index[index > value]
        if len(later):
            mapping[value] = later[0]
    aligned = book[book.decision_at.isin(mapping)].copy()
    aligned["decision_at"] = aligned.decision_at.map(mapping)
    return aligned


def reconstruction_matches(book: pd.DataFrame, weekly: pd.DataFrame, saved: pd.Series | None,
                           cost_bps: int) -> dict[str, object]:
    """A reconstruction nobody checked is a reconstruction nobody should trust."""
    path, _ = engine.portfolio_path(book, weekly, cost_bps)
    if saved is None:
        return {"checked": False, "reason": "no saved path to check against"}
    saved = saved.copy()
    saved.index = pd.to_datetime(saved.index, utc=True)
    joined = pd.concat([path.rename("rebuilt"), saved.rename("saved")], axis=1).dropna()
    if len(joined) < 26:
        return {"checked": False, "reason": f"only {len(joined)} overlapping weeks"}
    correlation = float(joined.rebuilt.corr(joined.saved))
    rebuilt_cagr = float(engine.metrics(joined.rebuilt)["cagr"])
    saved_cagr = float(engine.metrics(joined.saved)["cagr"])
    return {
        "checked": True,
        "overlapping_weeks": int(len(joined)),
        "weekly_correlation": correlation,
        "rebuilt_cagr": rebuilt_cagr,
        "saved_cagr": saved_cagr,
        "cagr_gap": rebuilt_cagr - saved_cagr,
        "reproduces": bool(correlation > 0.95 and abs(rebuilt_cagr - saved_cagr) < 0.05),
    }


def leave_one_out(book: pd.DataFrame, weekly: pd.DataFrame, cost_bps: int) -> dict[str, object]:
    base, _ = engine.portfolio_path(book, weekly, cost_bps)
    base_recent = engine.metrics(base.tail(52))["cagr"]
    rows = []
    for cik in sorted(set(book.cik10)):
        sub = book[book.cik10 != cik].copy()
        if sub.empty:
            continue
        sub["weight"] = sub.groupby("decision_at").weight.transform(lambda w: w / w.sum())
        path, _ = engine.portfolio_path(sub, weekly, cost_bps)
        rows.append({"cik10": cik, "recent_cagr": float(engine.metrics(path.tail(52))["cagr"])})
    frame = pd.DataFrame(rows).sort_values("recent_cagr")
    worst = frame.iloc[0]
    return {
        "names_held": int(len(frame)),
        "recent_cagr_with_everything": float(base_recent),
        "worst_single_removal": worst.cik10,
        "recent_cagr_without_it": float(worst.recent_cagr),
        "damage_from_one_name": float(base_recent - worst.recent_cagr),
        "share_of_recent_cagr_from_one_name": (
            round(float((base_recent - worst.recent_cagr) / base_recent), 4) if base_recent else None),
        "five_most_load_bearing": frame.head(5).to_dict("records"),
    }


def load_scores(spec: tuple[str, str | None]) -> pd.DataFrame | None:
    kind, family = spec
    if kind == "factor_scores":
        if not DISCOVERY.is_file():
            return None
        frame = pd.read_csv(DISCOVERY, dtype={"cik10": str}, parse_dates=["decision_at"])
        return frame[frame.family == family][["decision_at", "cik10", "score"]]
    if kind == "growth_scores":
        path = ROOT / "evidence/sec_growth_survivorship_retest_v1/growth_scores.csv"
        if not path.is_file():
            return None
        frame = pd.read_csv(path, dtype={"cik10": str}, parse_dates=["decision_at"])
        return frame[["decision_at", "cik10", "score"]]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", default="data/sec_broad_research_panel_v3")
    parser.add_argument("--output", default="evidence/dashboard_strategy_realism_audit_v1")
    parser.add_argument("--skip-leave-one-out", action="store_true")
    parser.add_argument("--null-draws", type=int, default=200)
    args = parser.parse_args()

    panel_dir = ROOT / args.panel
    weekly = pd.read_csv(panel_dir / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)

    findings: dict[str, dict] = {}
    for sid, spec in STRATEGIES.items():
        entry: dict[str, object] = {"display": spec["display"], "checks_not_run": []}

        series = None
        for bps in sorted(spec["paths"]):
            candidate = read_path(ROOT / spec["paths"][bps])
            if candidate is not None and bps == 50:
                series = candidate
            if candidate is not None:
                entry.setdefault("cost_ladder", {})[f"{bps}bps"] = {
                    "cagr": float(engine.metrics(candidate)["cagr"]),
                    "recent_52w_cagr": float(engine.metrics(candidate.tail(52))["cagr"]),
                    "sharpe": float(engine.metrics(candidate)["sharpe"]),
                }
        if series is None:
            entry["checks_not_run"].append("no 50bps return path found on disk")
        else:
            entry["as_displayed"] = ladder(series)
            multiplier = float(spec["displayed_leverage"])
            if multiplier > 1.0:
                levered = lever(series, multiplier, float(spec.get("financing_rate", 0.0)))
                entry["leverage"] = {
                    "displayed_multiplier": multiplier,
                    "financing_rate": spec.get("financing_rate"),
                    "unlevered_full_cagr": float(engine.metrics(series)["cagr"]),
                    "levered_full_cagr": float(engine.metrics(levered)["cagr"]),
                    "unlevered_recent_52w_cagr": float(engine.metrics(series.tail(52))["cagr"]),
                    "levered_recent_52w_cagr": float(engine.metrics(levered.tail(52))["cagr"]),
                    "unlevered_max_drawdown": float(engine.metrics(series)["max_drawdown"]),
                    "levered_max_drawdown": float(engine.metrics(levered)["max_drawdown"]),
                    "drawdown_added_by_leverage": float(
                        engine.metrics(levered)["max_drawdown"] - engine.metrics(series)["max_drawdown"]),
                }
            else:
                entry["leverage"] = {"displayed_multiplier": 1.0, "note": "headline is unlevered"}

        if spec["scores"]:
            scores = load_scores(spec["scores"])
            if scores is None:
                entry["checks_not_run"].append("score file not on disk; tie structure unmeasurable")
            else:
                entry["tie_structure"] = tie_structure(scores, int(spec["breadth"]))
        else:
            entry["checks_not_run"].append(
                "no per-issuer score file; tie structure cannot be measured from artifacts")

        if spec["book"] and spec["book"][1] and not args.skip_leave_one_out:
            path, date_col, id_col = spec["book"]
            frame = pd.read_csv(ROOT / path, dtype={id_col: str})
            frame[date_col] = pd.to_datetime(frame[date_col], utc=True)
            weight_col = next((c for c in ("intended_weight", "weight") if c in frame.columns), None)
            if weight_col is None:
                frame["weight"] = 1.0 / frame.groupby(date_col)[id_col].transform("count")
                weight_col = "weight"
            book = frame[[date_col, id_col, weight_col]].rename(
                columns={date_col: "decision_at", id_col: "cik10", weight_col: "weight"})
            book = book[book.cik10.isin(weekly.columns)]
            book = align_to_execution(book, weekly)
            if book.empty:
                entry["checks_not_run"].append("no held issuer is in the panel; leave-one-out skipped")
            else:
                check = reconstruction_matches(book, weekly, series, 50)
                entry["reconstruction_check"] = check
                if check.get("reproduces"):
                    entry["leave_one_out"] = leave_one_out(book, weekly, 50)
                    entry["random_book_null"] = random_book_null(book, weekly, 50, args.null_draws)
                else:
                    entry["checks_not_run"].append(
                        "the book does not reproduce the saved path, so leave-one-out and the "
                        "random-book null would be measuring something else and were not run")
        elif not spec["book"]:
            entry["checks_not_run"].append("no saved book; leave-one-out unmeasurable from artifacts")

        findings[sid] = entry

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "experiment": "dashboard_strategy_realism_audit_v1",
        "panel": args.panel,
        "strategies_audited": len(findings),
        "findings": findings,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
