#!/usr/bin/env python3
"""The connected-portfolio signal: do stocks held by the same managers lead each other?

Queue item A0, the free analogue of the shared-analyst-coverage effect that P2 is
blocked on. The identity gate passed at a 73.4% panel match rate, so the graph is
dense enough to trust.

One thing had to be amended before any signal was computed, and it is recorded in
the registry with its reason. The original design connected two issuers if any
manager held both, which is vacuous on 13F: the three largest managers hold 9,125,
9,112 and 7,539 names, so nearly every pair is connected through an index fund and
the connected-portfolio return collapses to the market return. Managers are capped
at 100 holdings, the closest analogue to Ali and Hirshleifer's analyst graph where
each stock connects to about 86 others, and the same measurement is reported at 50
and 250 so the choice is visible rather than load-bearing.

The connected return is computed from sparse matrices rather than by materialising
a stock-by-stock graph, and each stock is excluded from its own connected set.

Nothing here can be promoted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse, stats

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/institutional_linkage_registry_v1.json"
EVIDENCE = ROOT / "evidence/institutional_linkage_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_full_v1/recent_membership_readiness.csv"
SKIP = 1


def connected_returns(matrix: sparse.csr_matrix, lagged: np.ndarray) -> np.ndarray:
    """Mean over managers holding i of that manager's mean holding return, excluding i."""
    sizes = np.asarray(matrix.sum(axis=1)).ravel()
    usable = sizes > 1
    reduced = matrix[usable]
    sizes = sizes[usable]
    if reduced.shape[0] == 0:
        return np.full(matrix.shape[1], np.nan)
    filled = np.nan_to_num(lagged, nan=0.0)
    present = (~np.isnan(lagged)).astype(float)
    manager_sum = reduced @ filled
    manager_count = reduced @ present
    with np.errstate(invalid="ignore", divide="ignore"):
        # exclude the stock itself from its own manager's mean
        per_manager = manager_sum / np.maximum(manager_count, 1.0)
        weight = 1.0 / np.maximum(manager_count - 1.0, 1.0)
        numerator = reduced.T @ (manager_sum * weight)
        self_term = filled * (reduced.T @ weight)
        holders = np.asarray(reduced.sum(axis=0)).ravel()
        connected = (numerator - self_term) / np.maximum(holders, 1.0)
    connected[holders < 2] = np.nan
    connected[np.isnan(lagged)] = np.nan
    return connected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/institutional_linkage_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    design = registry["design"]
    threshold = float(design["bonferroni_threshold"])

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    lagged4 = ((1.0 + returns.fillna(0.0)).rolling(4).apply(np.prod, raw=True) - 1.0).shift(SKIP)

    mapping = pd.read_csv(EVIDENCE / "cusip_to_cik10.csv", dtype={"cusip": str, "cik10": str})
    cusip_to_cik = dict(zip(mapping.cusip, mapping.cik10))
    holdings = pd.read_parquet(EVIDENCE / "holdings.parquet", columns=["CIK", "CUSIP", "FILING_DATE"])
    holdings["cik10"] = holdings.CUSIP.map(cusip_to_cik)
    holdings = holdings.dropna(subset=["cik10"])
    holdings = holdings[holdings.cik10.isin(returns.columns)]
    holdings["quarter"] = holdings.FILING_DATE.dt.to_period("Q")

    columns = list(returns.columns)
    position = {c: i for i, c in enumerate(columns)}
    members = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    sectors = members.drop_duplicates("cik10").set_index("cik10").sector.reindex(columns)

    rows = []
    for cap in (50, 100, 250):
        signal = pd.DataFrame(np.nan, index=returns.index, columns=columns)
        sector_control = pd.DataFrame(np.nan, index=returns.index, columns=columns)
        for quarter, block in holdings.groupby("quarter"):
            sizes = block.groupby("CIK").cik10.nunique()
            keep = set(sizes[(sizes >= 2) & (sizes <= cap)].index)
            block = block[block.CIK.isin(keep)]
            if block.empty:
                continue
            managers = {m: i for i, m in enumerate(sorted(keep))}
            rowi = block.CIK.map(managers).to_numpy()
            coli = block.cik10.map(position).to_numpy()
            matrix = sparse.csr_matrix(
                (np.ones(len(block)), (rowi, coli)), shape=(len(managers), len(columns)))
            matrix.data[:] = 1.0
            # the graph is knowable from the quarter after its filings land
            start = quarter.end_time + pd.Timedelta(days=1)
            finish = start + pd.Timedelta(days=95)
            weeks = returns.index[(returns.index >= start) & (returns.index < finish)]
            for week in weeks:
                lagged = lagged4.loc[week].to_numpy(dtype=float)
                signal.loc[week] = connected_returns(matrix, lagged)
        # sector-matched control: the same lagged return averaged over the sector
        for sector in sectors.dropna().unique():
            names = [c for c in columns if sectors.get(c) == sector]
            if len(names) < 10:
                continue
            sector_control[names] = np.repeat(
                lagged4[names].mean(axis=1).to_numpy()[:, None], len(names), axis=1)

        for horizon in design["forward_horizon_weeks"]:
            compounded = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
            valid = returns.notna().rolling(horizon).sum() >= horizon
            forward = compounded.where(valid).shift(-horizon)
            for label, window in (("select", design["selection_window"]),
                                  ("evaluate", design["evaluation_window"])):
                raw, residual = [], []
                inside = signal.loc[(signal.index >= window[0]) & (signal.index <= window[1])]
                for week in inside.index[::horizon]:
                    if week not in forward.index:
                        continue
                    pair = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week],
                                         "c": sector_control.loc[week]}).dropna()
                    if len(pair) < 200:
                        continue
                    raw.append(float(pair.s.rank().corr(pair.f.rank())))
                    # residualise the signal on its sector control before ranking
                    x = np.column_stack([np.ones(len(pair)), pair.c.to_numpy()])
                    beta, *_ = np.linalg.lstsq(x, pair.s.to_numpy(), rcond=None)
                    resid = pair.s.to_numpy() - x @ beta
                    residual.append(float(pd.Series(resid).rank().corr(pair.f.rank().reset_index(drop=True))))
                if len(raw) < 8:
                    continue
                a, b = np.array(raw), np.array(residual)
                rows.append({
                    "manager_cap": cap, "horizon": horizon, "window": label,
                    "observations": len(a), "mean_ic": float(a.mean()),
                    "t_stat": float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))),
                    "p_value": float(stats.ttest_1samp(a, 0.0).pvalue),
                    "mean_ic_sector_controlled": float(b.mean()),
                    "t_stat_sector_controlled": float(b.mean() / (b.std(ddof=1) / np.sqrt(len(b)))),
                    "share_positive": float((a > 0).mean()),
                })
        print(f"  cap {cap} done", flush=True)

    table = pd.DataFrame(rows)
    out = ROOT / args.output
    table.to_csv(out / "linkage_ic.csv", index=False)

    primary = table[(table.manager_cap == design["manager_holdings_cap"])]
    selected = primary[primary.window == "select"]
    evaluated = primary[primary.window == "evaluate"]
    clears = table[(table.window == "select") & (table.p_value < threshold) & (table.mean_ic > 0)]
    survives = []
    for row in clears.itertuples():
        match = table[(table.manager_cap == row.manager_cap) & (table.horizon == row.horizon)
                      & (table.window == "evaluate")]
        if not match.empty and match.iloc[0].mean_ic > 0 and match.iloc[0].p_value < 0.05:
            survives.append(f"cap{row.manager_cap}_h{row.horizon}")

    if table.empty:
        verdict = "no configuration produced enough cross-sections to measure"
    elif clears.empty:
        verdict = ("no configuration clears in selection with the declared positive sign. The free "
                   "linkage analogue does not reproduce the analyst effect on this universe. A0 "
                   "closes; P2 stays a purchasing decision.")
    elif not survives:
        verdict = ("clears in selection but does not repeat out of sample; treat as in-sample")
    else:
        verdict = (f"survives selection and evaluation at {', '.join(survives)}; the sector-controlled "
                   f"column decides whether it is a linkage effect or a sector effect")

    result = {"experiment": "institutional_linkage_v1", "queue_item": "A0",
              "identity_gate": json.loads((out / "identity_result.json").read_text())["identity"],
              "manager_cap_primary": design["manager_holdings_cap"],
              "declared_trials": design["declared_trials"], "bonferroni_threshold": threshold,
              "rows": rows, "survives_out_of_sample": survives, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
