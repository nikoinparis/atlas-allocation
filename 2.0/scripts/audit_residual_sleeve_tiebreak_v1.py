#!/usr/bin/env python3
"""Test whether the residual sleeve's book is a signal or a sort order.

`robust_rank` winsorises at the 5th and 95th percentiles and *then* ranks the
clipped values, so every issuer above the 95th percentile receives the identical
average rank.  With roughly 2,700 issuers that is a tie block of about 130 names
carrying exactly the same score, and `top_weights` breaks ties with

    sort_values(["score", "cik10"], ascending=[False, True])

which fills all twenty slots from inside the tie by taking the lowest CIK10s --
the oldest SEC registrants.  The declared book is therefore one arbitrary draw
from a large pool of indistinguishable candidates, and the question this script
answers is whether the sleeve's measured performance survives drawing a
different one.

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader import sec_tournament_rehearsal as engine

BREADTH = 20
ISSUER_CAP = 0.2
SECTOR_CAP = 0.4
COST_BPS = 50


def select(frame: pd.DataFrame, order: pd.Series, breadth: int) -> list[str]:
    """The greedy sector-capped walk from `top_weights`, over a supplied order."""
    ranked = frame.assign(_order=order).sort_values(["score", "_order"], ascending=[False, True])
    limit = max(1, int(np.floor(SECTOR_CAP * breadth)))
    chosen: list[str] = []
    counts: dict[str, int] = {}
    for row in ranked.itertuples(index=False):
        if counts.get(row.sector, 0) >= limit:
            continue
        chosen.append(row.cik10)
        counts[row.sector] = counts.get(row.sector, 0) + 1
        if len(chosen) == breadth:
            break
    return chosen


def book(scores: pd.DataFrame, seed: int | None) -> pd.DataFrame:
    """seed None reproduces the declared cik10-ascending tie-break."""
    rows = []
    for decision, frame in scores.groupby("decision_at", sort=True):
        frame = frame.dropna(subset=["score"])
        if seed is None:
            order = frame.cik10
        else:
            # Python randomises str hashing per process, so hash() here would make
            # the whole audit irreproducible between runs. Derive the stream from a
            # stable digest instead.
            digest = hashlib.blake2b(f"{seed}|{decision}".encode(), digest_size=8).digest()
            rng = np.random.default_rng(int.from_bytes(digest, "big"))
            order = pd.Series(rng.permutation(len(frame)), index=frame.index)
        chosen = select(frame, order, BREADTH)
        weight = min(ISSUER_CAP, 1.0 / max(1, len(chosen)))
        rows.extend({"decision_at": decision, "cik10": cik, "weight": weight} for cik in chosen)
    return pd.DataFrame(rows)


def tie_pool_book(scores: pd.DataFrame) -> pd.DataFrame:
    """Hold every name tied at or above the twentieth score: tie-break agnostic."""
    rows = []
    for decision, frame in scores.groupby("decision_at", sort=True):
        frame = frame.dropna(subset=["score"])
        if len(frame) < BREADTH:
            continue
        cutoff = frame.score.sort_values(ascending=False).iloc[BREADTH - 1]
        pool = frame[frame.score >= cutoff]
        weight = 1.0 / len(pool)
        rows.extend({"decision_at": decision, "cik10": c, "weight": weight} for c in pool.cik10)
    return pd.DataFrame(rows)


def summarise(path: pd.Series) -> dict[str, float]:
    # engine.metrics returns cagr, sharpe and max_drawdown only; volatility is
    # computed here rather than pulled from a key that does not exist.
    full = engine.metrics(path)
    recent = engine.metrics(path.tail(52))
    return {
        "annualised_volatility": float(path.std(ddof=1) * np.sqrt(52)),
        "recent_52w_annualised_volatility": float(path.tail(52).std(ddof=1) * np.sqrt(52)),
        "full_cagr": float(full["cagr"]),
        "full_sharpe": float(full["sharpe"]),
        "max_drawdown": float(full["max_drawdown"]),
        "recent_52w_cagr": float(recent["cagr"]),
        "recent_52w_sharpe": float(recent["sharpe"]),
        "recent_52w_max_drawdown": float(recent["max_drawdown"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", default="data/sec_broad_research_panel_v3")
    parser.add_argument("--draws", type=int, default=200)
    parser.add_argument("--output", default="evidence/residual_sleeve_tiebreak_audit_v1")
    args = parser.parse_args()

    panel_dir = ROOT / args.panel
    panel = pd.read_csv(panel_dir / "panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel["decision_at"], utc=True)
    panel["execution_at"] = pd.to_datetime(panel["execution_at"], utc=True)
    weekly = pd.read_csv(panel_dir / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)

    scores = panel[["decision_at", "execution_at", "cik10", "sector", "residual_momentum"]].rename(
        columns={"residual_momentum": "score"}
    )
    executions = scores[["decision_at", "execution_at"]].drop_duplicates()

    def to_execution(frame: pd.DataFrame) -> pd.DataFrame:
        return (frame.merge(executions, on="decision_at", validate="many_to_one")
                     .drop(columns="decision_at").rename(columns={"execution_at": "decision_at"}))

    ties = []
    for decision, frame in scores.groupby("decision_at", sort=True):
        valid = frame.dropna(subset=["score"])
        if len(valid) < BREADTH:
            ties.append({
                "decision_at": str(decision.date()),
                "candidates": int(len(valid)),
                "twentieth_score": float("nan"),
                "tied_at_or_above": 0,
            })
            continue
        cutoff = valid.score.sort_values(ascending=False).iloc[BREADTH - 1]
        ties.append({
            "decision_at": str(decision.date()),
            "candidates": int(len(valid)),
            "twentieth_score": float(cutoff),
            "tied_at_or_above": int((valid.score >= cutoff).sum()),
        })
    tie_frame = pd.DataFrame(ties)

    declared = to_execution(book(scores, None))
    declared_path, _ = engine.portfolio_path(declared, weekly, COST_BPS)
    declared_metrics = summarise(declared_path)

    pool = to_execution(tie_pool_book(scores))
    pool_path, _ = engine.portfolio_path(pool, weekly, COST_BPS)

    draws = []
    for seed in range(args.draws):
        alt = to_execution(book(scores, seed))
        alt_path, _ = engine.portfolio_path(alt, weekly, COST_BPS)
        row = summarise(alt_path)
        row["seed"] = seed
        row["overlap_with_declared"] = float(
            len(set(map(tuple, alt[["decision_at", "cik10"]].to_numpy())) &
                set(map(tuple, declared[["decision_at", "cik10"]].to_numpy())))
            / len(declared)
        )
        draws.append(row)
    draw_frame = pd.DataFrame(draws)

    percentiles = {
        metric: float((draw_frame[metric] < declared_metrics[metric]).mean())
        for metric in ["full_cagr", "full_sharpe", "recent_52w_cagr", "max_drawdown"]
    }

    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    tie_frame.to_csv(output / "tie_structure.csv", index=False)
    draw_frame.to_csv(output / "random_tiebreak_draws.csv", index=False)
    declared_path.rename("net_return").rename_axis("Date").to_csv(output / "declared_path.csv")
    pool_path.rename("net_return").rename_axis("Date").to_csv(output / "tie_pool_path.csv")

    result = {
        "experiment": "residual_sleeve_tiebreak_audit_v1",
        "panel": args.panel,
        "cost_bps": COST_BPS,
        "breadth": BREADTH,
        "draws": args.draws,
        "median_tie_pool_at_twentieth_score": float(tie_frame.tied_at_or_above.median()),
        "declared_tiebreak": "cik10 ascending (oldest SEC registrant first)",
        "declared": declared_metrics,
        "tie_pool_equal_weight": summarise(pool_path),
        "random_tiebreak_quantiles": {
            metric: {
                "p05": float(draw_frame[metric].quantile(0.05)),
                "p50": float(draw_frame[metric].quantile(0.50)),
                "p95": float(draw_frame[metric].quantile(0.95)),
            }
            for metric in ["full_cagr", "full_sharpe", "recent_52w_cagr", "max_drawdown"]
        },
        "declared_percentile_within_random_draws": percentiles,
        "mean_overlap_of_random_book_with_declared": float(draw_frame.overlap_with_declared.mean()),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
