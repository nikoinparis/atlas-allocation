"""Fixed, causal return-expansion transformations for the frozen GGG benchmark."""

from __future__ import annotations

import pandas as pd

from systematic_trader.challenger_buffering import buffered_target
from systematic_trader.ggg_independent import CASH_PROXY


def breadth_risk_on(
    prices: pd.DataFrame,
    universe: list[str],
    threshold: float,
) -> pd.Series:
    """Use date-t prices only; the returned state is tradable for t-to-t+1."""
    if threshold < 0 or threshold > 1:
        raise ValueError("threshold must be in [0, 1]")
    available = [asset for asset in universe if asset in prices]
    if not available:
        return pd.Series(False, index=prices.index)
    panel = prices[available].apply(pd.to_numeric, errors="coerce")
    passed = panel.gt(panel.rolling(43, min_periods=43).mean()) & panel.div(panel.shift(26)).sub(1.0).gt(0.0)
    breadth = passed.sum(axis=1).div(passed.notna().sum(axis=1).replace(0, pd.NA)).fillna(0.0)
    leaders = pd.Series(True, index=prices.index)
    for asset in ("SPY", "QQQ"):
        leaders &= passed[asset].fillna(False) if asset in passed else False
    return (leaders & breadth.ge(threshold)).astype(bool)


def redeploy_cash(
    weights: pd.DataFrame,
    risk_on: pd.Series,
    fraction: float,
) -> pd.DataFrame:
    """Move a fixed BIL fraction pro rata to currently held risky assets."""
    if fraction < 0 or fraction > 1:
        raise ValueError("fraction must be in [0, 1]")
    output = weights.copy().fillna(0.0)
    risky_columns = [column for column in output if column != CASH_PROXY]
    for date in output.index[risk_on.reindex(output.index).fillna(False)]:
        risky = output.loc[date, risky_columns].clip(lower=0.0)
        total = float(risky.sum())
        amount = float(output.loc[date, CASH_PROXY]) * fraction if CASH_PROXY in output else 0.0
        if amount > 0 and total > 0:
            output.loc[date, risky_columns] = risky + amount * risky / total
            output.loc[date, CASH_PROXY] -= amount
    return output


def conditional_weights(
    baseline: pd.DataFrame,
    expansion: pd.DataFrame,
    risk_on: pd.Series,
) -> pd.DataFrame:
    output = baseline.copy()
    mask = risk_on.reindex(output.index).fillna(False)
    output.loc[mask] = expansion.reindex_like(output).loc[mask]
    return output


def turnover_transform(weights: pd.DataFrame, kind: str, value: float) -> pd.DataFrame:
    """Apply one fixed stateful turnover rule to an entire target history."""
    if value < 0 or value > 1:
        raise ValueError("value must be in [0, 1]")
    previous: dict[str, float] | None = None
    rows: list[pd.Series] = []
    for date, target_row in weights.iterrows():
        target = {str(key): float(val) for key, val in target_row.fillna(0.0).items()}
        if previous is None:
            current = target
        elif kind == "turnover_band":
            current, _ = buffered_target(previous, target, no_trade_turnover=value)
        else:
            proposed = 0.5 * sum(abs(target[key] - previous.get(key, 0.0)) for key in target)
            if kind == "minimum_total_change":
                current = previous if proposed <= value + 1e-15 else target
            elif kind == "stagger":
                current = {key: previous.get(key, 0.0) + value * (target[key] - previous.get(key, 0.0)) for key in target}
            else:
                raise ValueError(f"unknown turnover transform: {kind}")
        row = pd.Series(current, name=date).reindex(weights.columns).fillna(0.0)
        if abs(float(row.sum()) - 1.0) > 1e-9 or (row < -1e-12).any():
            raise ValueError("transformation must remain fully invested and long-only")
        rows.append(row)
        previous = row.to_dict()
    return pd.DataFrame(rows).reindex(columns=weights.columns).fillna(0.0)
