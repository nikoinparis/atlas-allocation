#!/usr/bin/env python3
"""How much of the headline Sharpe is the search itself?

Step 196 established that the saved strategies sit in the extreme right tail of
size- and volatility-matched random portfolios, and said plainly that finding a
deliberately chosen high performer in the top percentile of random draws over its
own selection period is close to tautological. It did not put a number on the
tautology. This does.

The deflated Sharpe ratio deflates an observed Sharpe by the expected maximum
Sharpe under a null of N zero-skill trials, correcting for sample length, skew and
kurtosis. N is the thing this project has never counted, so it is reported as a
grid rather than guessed at.

Nothing here is fitted and nothing is promoted.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/deflated_sharpe_audit_v1.json"
OUTPUT = ROOT / "evidence/deflated_sharpe_audit_v1"
EULER_MASCHERONI = 0.5772156649015329


def expected_maximum_sharpe(trials: int, sharpe_variance: float) -> float:
    """E[max Sharpe] over `trials` independent draws from N(0, sharpe_variance)."""
    gamma = EULER_MASCHERONI
    return math.sqrt(sharpe_variance) * (
        (1 - gamma) * stats.norm.ppf(1 - 1 / trials)
        + gamma * stats.norm.ppf(1 - 1 / (trials * math.e))
    )


def deflated_sharpe(returns: pd.Series, trials: int, periods: int = 52) -> dict:
    series = returns.dropna()
    n = len(series)
    sharpe = series.mean() / series.std(ddof=1)
    skew = float(stats.skew(series))
    kurtosis = float(stats.kurtosis(series, fisher=False))
    # Variance of the Sharpe estimator under non-normal returns (Mertens).
    adjustment = 1 - skew * sharpe + (kurtosis - 1) / 4 * sharpe**2
    sharpe_variance = adjustment / (n - 1)
    threshold = expected_maximum_sharpe(trials, sharpe_variance)
    z = (sharpe - threshold) * math.sqrt(n - 1) / math.sqrt(adjustment)
    return {
        "trials": trials,
        "annualised_sharpe": float(sharpe * math.sqrt(periods)),
        "annualised_null_threshold": float(threshold * math.sqrt(periods)),
        "deflated_sharpe_ratio": float(stats.norm.cdf(z)),
        "significant_at_0.95": bool(stats.norm.cdf(z) >= 0.95),
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    dashboard = json.loads((ROOT / config["strategy_source"]).read_text())
    periods = config["declared_before_running"]["periods_per_year"]

    findings = {}
    for entry in dashboard["strategies"]:
        record = pd.DataFrame(entry["records"])
        series = record["netReturn"].astype(float).dropna()
        name = entry["strategy"]["shortName"]
        findings[name] = {
            "weeks": int(len(series)),
            "skewness": float(stats.skew(series)),
            "kurtosis": float(stats.kurtosis(series, fisher=False)),
            "by_trial_count": {
                str(n): deflated_sharpe(series, n, periods)
                for n in config["method"]["trial_counts_reported"]
            },
        }

    survivors = {
        str(n): [
            name
            for name, f in findings.items()
            if f["by_trial_count"][str(n)]["significant_at_0.95"]
        ]
        for n in config["method"]["trial_counts_reported"]
    }

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "threshold": config["method"]["significance_threshold"],
        "strategies": findings,
        "strategies_significant_by_trial_count": survivors,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print(f"{'strategy':28s}{'weeks':>7s}{'annSR':>8s}" + "".join(f"{'N=' + str(n):>10s}" for n in config["method"]["trial_counts_reported"]))
    for name, f in findings.items():
        first = f["by_trial_count"][str(config["method"]["trial_counts_reported"][0])]
        row = f"{name:28s}{f['weeks']:7d}{first['annualised_sharpe']:8.2f}"
        for n in config["method"]["trial_counts_reported"]:
            row += f"{f['by_trial_count'][str(n)]['deflated_sharpe_ratio']:10.4f}"
        print(row)
    print()
    for n, names in survivors.items():
        print(f"  significant at N={n}: {names if names else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
