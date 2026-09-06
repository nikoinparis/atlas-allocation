#!/usr/bin/env python3
"""Size the same book by risk instead of equally, and see if anything improves.

UPGRADE_CANDIDATES_V1 item 5, and the first of the not-yet-tried directions to
actually be run.  It claims no new alpha: the selection is untouched and only the
weighting changes, so its overfitting risk is far below a signal search.  It goes
directly at the concentration problem CLAUDE.md rule 5 names as this project's
most chronic failure mode.

Every volatility estimate uses returns strictly before the week it sizes.  The
configurations were fixed in `config/risk_budgeted_sizing_registry_v1.json`
before this ran.

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
REGISTRY = ROOT / "config/risk_budgeted_sizing_registry_v1.json"


def returns_from(relative: str) -> pd.DataFrame:
    frame = pd.read_csv(ROOT / relative, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    frame = frame.apply(pd.to_numeric, errors="coerce")
    return (frame / frame.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)


def sizing_weights(config: dict, names: list[str], history: pd.DataFrame) -> np.ndarray:
    kind = config["sizing"]
    if kind == "equal_weight" or history.empty:
        return np.repeat(1.0 / len(names), len(names))
    volatility = history[names].std(ddof=1)
    volatility = volatility.replace(0.0, np.nan)
    # A name with no usable history gets the median risk rather than infinite size.
    volatility = volatility.fillna(volatility.median() if volatility.notna().any() else 1.0)
    if kind in ("inverse_volatility", "inverse_volatility_capped", "equal_risk_contribution_diagonal"):
        raw = 1.0 / volatility
    elif kind == "inverse_variance":
        raw = 1.0 / (volatility ** 2)
    else:
        raise ValueError(f"unknown sizing {kind}")
    weights = (raw / raw.sum()).to_numpy(dtype=float)
    cap = config.get("maximum_issuer_weight")
    if cap:
        for _ in range(64):
            excess = weights - cap
            if (excess <= 1e-12).all():
                break
            spill = excess.clip(min=0.0).sum()
            weights = np.minimum(weights, cap)
            room = weights < cap - 1e-12
            if not room.any():
                break
            weights[room] += spill * weights[room] / weights[room].sum()
        weights = weights / weights.sum()
    return weights


def simulate(book: pd.DataFrame, returns: pd.DataFrame, config: dict, cost_bps: float) -> pd.Series:
    lookback = int(config.get("lookback_weeks", 0))
    schedule = {date: sorted(frame.cik10) for date, frame in book.groupby("execution_at")}
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values = []
    for position, week in enumerate(returns.index):
        cost = 0.0
        if week in schedule:
            names = [n for n in schedule[week] if n in returns.columns]
            if names:
                # strictly-before history only
                start = max(0, position - lookback)
                history = returns.iloc[start:position]
                weights = sizing_weights(config, names, history)
                holdings = pd.Series(0.0, index=returns.columns, dtype=float)
                holdings.loc[names] = weights
                cost = float((holdings - previous).abs().sum()) * cost_bps / 10_000.0
                previous = holdings.copy()
        values.append(float((holdings * returns.loc[week].fillna(0.0)).sum()) - cost)
    return pd.Series(values, index=returns.index)


def metrics(series: pd.Series) -> dict[str, float]:
    years = len(series) / 52.0
    total = float((1.0 + series.fillna(0.0)).prod())
    wealth = (1.0 + series.fillna(0.0)).cumprod()
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    return {
        "cagr": float(total ** (1.0 / years) - 1.0) if years else float("nan"),
        "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
        "annualised_volatility": volatility,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "recent_52w_return": float((1.0 + series.tail(52).fillna(0.0)).prod() - 1.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/risk_budgeted_sizing_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    returns = returns_from(registry["prices"])
    book = pd.read_csv(ROOT / registry["book_under_test"], dtype={"cik10": str}, parse_dates=["decision_at"])
    book["decision_at"] = pd.to_datetime(book.decision_at, utc=True)
    index = returns.index
    mapping = {}
    for value in sorted(book.decision_at.unique()):
        later = index[index > value]
        if len(later):
            mapping[value] = later[0]
    book = book[book.decision_at.isin(mapping)].copy()
    book["execution_at"] = book.decision_at.map(mapping)
    book = book[book.cik10.isin(returns.columns)]
    start = book.execution_at.min()

    rows = []
    paths = {}
    for config in registry["declared_configurations"]:
        entry = {"id": config["id"], "sizing": config["sizing"],
                 "lookback_weeks": config.get("lookback_weeks")}
        for cost in (0.0, 50.0, 100.0):
            path = simulate(book, returns, config, cost).loc[start:]
            paths[(config["id"], cost)] = path
            for key, value in metrics(path).items():
                entry[f"{key}__{int(cost)}bps"] = value
        rows.append(entry)
    frame = pd.DataFrame(rows)

    control = frame[frame.id == "S0"].iloc[0]
    verdicts = []
    for _, row in frame.iterrows():
        if row.id == "S0":
            continue
        better_sharpe = bool(row["sharpe__50bps"] > control["sharpe__50bps"])
        no_worse_dd = bool(row["max_drawdown__50bps"] >= control["max_drawdown__50bps"])
        holds_at_100 = bool(row["sharpe__100bps"] > control["sharpe__100bps"])
        verdicts.append({
            "id": row.id,
            "sharpe_gain_at_50bps": float(row["sharpe__50bps"] - control["sharpe__50bps"]),
            "improves_sharpe": better_sharpe,
            "does_not_worsen_drawdown": no_worse_dd,
            "holds_at_100bps": holds_at_100,
            "passes_declared_criteria": bool(better_sharpe and no_worse_dd and holds_at_100),
        })

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "configurations.csv", index=False)
    result = {
        "experiment": "risk_budgeted_sizing_v1",
        "registry_sha256_note": "configurations fixed in config/risk_budgeted_sizing_registry_v1.json before this ran",
        "declared_trials": registry["declared_trials"],
        "cumulative_trial_warning": registry["cumulative_trial_warning"],
        "book_under_test": registry["book_under_test"],
        "prices": registry["prices"],
        "weeks": int(len(paths[("S0", 50.0)])),
        "control": {k: float(control[k]) for k in control.index if isinstance(control[k], (int, float))},
        "verdicts": verdicts,
        "configurations_passing": sum(1 for v in verdicts if v["passes_declared_criteria"]),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    show = ["id", "sizing", "cagr__50bps", "sharpe__50bps", "annualised_volatility__50bps",
            "max_drawdown__50bps", "recent_52w_return__50bps", "sharpe__100bps", "sharpe__0bps"]
    print(frame[show].to_string(index=False))
    print()
    print(json.dumps({"configurations_passing": result["configurations_passing"], "verdicts": verdicts},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
