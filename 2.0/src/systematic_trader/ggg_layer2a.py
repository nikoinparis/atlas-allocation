"""Platform-owned reconstruction of the five causal GGG Layer 2a sleeves."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from systematic_trader.ggg_layer1 import Layer1Bundle

WEEKS_PER_YEAR = 52
CTA_VOL_WINDOW = 26
TAA_SMA_WEEKS = 43
COMPOSITE_SMOOTHING_WEEKS = 4
CASH = "BIL"
RESEARCH_UNIVERSE = [
    "TIP", "SPY", "XLV", "XLU", "XLP", "XLK", "XLI", "XLF", "XLE", "XLB",
    "VUG", "VTV", "VNQ", "TLT", "XLY", "IEF", "EEM", "QQQ", "EFA", "EWJ",
    "GLD", "LQD", "SHY", "IWM", "IAU", "VWO", "USO", "SLV", "DBA", "UUP",
    "MBB", "HYG", "BIL", "VEA", "PDBC",
]
BROAD_RISK = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
DUAL_ASSETS = ["SPY", "EFA", "VWO", "VNQ", "HYG", "LQD", "TLT", "GLD", "PDBC"]
TAA_ASSETS = ["SPY", "EFA", "VWO", "VNQ", "TLT", "HYG", "GLD", "PDBC"]
SLEEVES = ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "taa_10m_sma", "composite_regime_conditioned"]
MONTHLY_SLEEVES = set(SLEEVES) - {"cta_trend_long_only"}


@dataclass(frozen=True)
class Layer2ABundle:
    positions: dict[str, pd.DataFrame]
    paths: dict[str, pd.DataFrame]
    source_status: dict[str, str]


def _available(names: list[str], columns: pd.Index) -> list[str]:
    return [name for name in names if name in columns]


def _legacy_month_end(index: pd.DatetimeIndex) -> pd.Series:
    months = pd.Series(index.to_period("M").astype(str), index=index)
    mask = months.ne(months.shift(-1))
    if len(mask):
        mask.iloc[0] = True
    return mask


def _calendar_month_end(index: pd.DatetimeIndex) -> pd.Series:
    # A completed Friday is the month's final Friday when the next Friday is
    # in a different month.  This never mistakes an incomplete final sample
    # row for a valid month-end decision.
    return pd.Series((index + pd.Timedelta(days=7)).month != index.month, index=index)


def _schedule(
    targets: pd.DataFrame,
    *,
    frequency: str,
    legacy_end_of_sample: bool,
    frozen: pd.DataFrame | None = None,
    cutoff: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if frequency == "weekly":
        scheduled = targets.fillna(0.0)
    elif frozen is None or cutoff is None:
        mask = _legacy_month_end(targets.index) if legacy_end_of_sample else _calendar_month_end(targets.index)
        scheduled = targets.where(np.repeat(mask.to_numpy()[:, None], targets.shape[1], axis=1)).ffill().fillna(0.0)
    else:
        cutoff = pd.Timestamp(cutoff)
        mask = _calendar_month_end(targets.index)
        scheduled = pd.DataFrame(0.0, index=targets.index, columns=targets.columns)
        initial = frozen.loc[:cutoff].iloc[-1].reindex(targets.columns).fillna(0.0)
        current = initial.copy()
        for date in targets.index:
            if date <= cutoff:
                continue
            if bool(mask.loc[date]):
                current = targets.loc[date].fillna(0.0)
            scheduled.loc[date] = current
    if frozen is not None and cutoff is not None:
        cutoff = pd.Timestamp(cutoff)
        left = frozen.loc[frozen.index <= cutoff]
        right = scheduled.loc[scheduled.index > cutoff]
        columns = left.columns if not left.empty else scheduled.columns
        scheduled = pd.concat([left, right.reindex(columns=columns)]).sort_index()
    return scheduled


def _top_n(scores: pd.DataFrame, top_n: int, defensive: str = CASH) -> pd.DataFrame:
    columns = list(scores.columns) + ([] if defensive in scores.columns else [defensive])
    weights = pd.DataFrame(0.0, index=scores.index, columns=columns)
    for date, row in scores.iterrows():
        selected = row.dropna().sort_values(ascending=False)
        selected = selected[selected > 0].head(top_n)
        if selected.empty:
            weights.loc[date, defensive] = 1.0
        else:
            weights.loc[date, selected.index] = 1.0 / top_n
            weights.loc[date, defensive] = 1.0 - len(selected) / top_n
    return weights


def _dual(relative: pd.DataFrame, absolute: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    columns = list(relative.columns) + [CASH]
    weights = pd.DataFrame(0.0, index=relative.index, columns=columns)
    for date in relative.index:
        ranked = relative.loc[date].dropna().sort_values(ascending=False)
        candidates = ranked.head(top_n).index
        passing = [name for name in candidates if pd.notna(absolute.loc[date].get(name)) and absolute.loc[date].get(name) > 0]
        weights.loc[date, passing] = 1.0 / top_n
        weights.loc[date, CASH] = 1.0 - len(passing) / top_n
    return weights


def _cta(scores: pd.DataFrame, volatility: pd.DataFrame) -> pd.DataFrame:
    columns = list(scores.columns) + [CASH]
    weights = pd.DataFrame(0.0, index=scores.index, columns=columns)
    for date in scores.index:
        positive = scores.loc[date].dropna()
        positive = positive[positive > 0]
        if positive.empty:
            weights.loc[date, CASH] = 1.0
            continue
        raw = positive.div(volatility.loc[date].reindex(positive.index)).replace([np.inf, -np.inf], np.nan).dropna()
        if raw.empty or raw.sum() == 0:
            weights.loc[date, CASH] = 1.0
        else:
            weights.loc[date, raw.index] = raw / raw.sum()
    return weights


def _taa(prices: pd.DataFrame) -> pd.DataFrame:
    assets = _available(TAA_ASSETS, prices.columns)
    average = prices[assets].rolling(TAA_SMA_WEEKS, min_periods=max(20, TAA_SMA_WEEKS // 2)).mean()
    signal = prices[assets].gt(average).astype(float).shift(1)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for date, row in signal.iterrows():
        selected = row[row > 0].index
        if len(selected):
            weights.loc[date, selected] = 1.0 / len(selected)
        else:
            weights.loc[date, CASH] = 1.0
    return weights


def _combine(panels: dict[str, pd.DataFrame], weight_history: pd.DataFrame | None = None) -> pd.DataFrame:
    template = next(iter(panels.values())) * 0.0
    numerator, denominator = template.copy(), template.copy()
    for name, panel in panels.items():
        weight = pd.Series(1.0, index=panel.index) if weight_history is None else weight_history[name].reindex(panel.index).fillna(0.0)
        numerator = numerator.add(panel.mul(weight, axis=0).fillna(0.0), fill_value=0.0)
        denominator = denominator.add(panel.notna().astype(float).mul(weight.abs(), axis=0), fill_value=0.0)
    return numerator.div(denominator.replace(0.0, np.nan)).rolling(COMPOSITE_SMOOTHING_WEEKS, min_periods=1).mean()


def _risk_state(regime: pd.DataFrame, index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, pd.Series]:
    score = pd.to_numeric(regime.get("macro_risk_score_tradable", pd.Series(0.0, index=index)), errors="coerce").reindex(index).fillna(0.0)
    state = pd.Series(np.where(score >= 0.5, "stressed", np.where(score <= -0.5, "calm", "neutral")), index=index)
    overlay = state.map({"calm": 1.0, "neutral": 0.75, "stressed": 0.35}).fillna(0.75)
    environment = pd.Series(np.where(state.eq("stressed"), "reversal_friendly", np.where(state.eq("calm"), "trend_friendly", "mixed")), index=index)
    return state, overlay, environment


def _regime_weights(index: pd.DatetimeIndex, names: list[str], state: pd.Series, environment: pd.Series) -> pd.DataFrame:
    default = {"xsmom_global": 1.0, "multi_mom_invvol": 1.2, "residual_momentum": 1.0, "quality_proxy": 0.9, "value_proxy": 0.7, "carry_proxy": 0.5, "bab_proxy": 0.7, "reversal_4w_global": 0.4}
    stressed = {"xsmom_global": 0.5, "multi_mom_invvol": 0.6, "residual_momentum": 0.5, "quality_proxy": 1.2, "value_proxy": 0.6, "carry_proxy": 0.3, "bab_proxy": 1.0, "reversal_4w_global": 1.0}
    trend = {"xsmom_global": 1.15, "multi_mom_invvol": 1.20, "residual_momentum": 1.15}
    reversal = {"quality_proxy": 1.10, "bab_proxy": 1.10, "reversal_4w_global": 1.20}
    rows = []
    for date in index:
        row = pd.Series({name: default.get(name, 1.0) for name in names}, dtype=float)
        if state.loc[date] == "stressed":
            row = pd.Series({name: stressed.get(name, row.get(name, 1.0)) for name in names}, dtype=float)
        boosts = trend if environment.loc[date] == "trend_friendly" else reversal if environment.loc[date] == "reversal_friendly" else {}
        for name, multiplier in boosts.items():
            if name in row:
                row.loc[name] *= multiplier
        rows.append(row / row.sum())
    return pd.DataFrame(rows, index=index)


def strategy_path(weights: pd.DataFrame, prices: pd.DataFrame, cost_bps: float = 10.0) -> pd.DataFrame:
    ordinary = prices.pct_change(fill_method=None)
    forward = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    if len(prices) > 1:
        forward.iloc[:-1] = ordinary.iloc[1:].to_numpy()
    aligned = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    gross = (aligned * forward).sum(axis=1)
    turnover = 0.5 * aligned.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth.div(wealth.cummax()) - 1.0
    return pd.DataFrame({"gross_return": gross, "net_return": net, "turnover": turnover, "cost": cost, "wealth": wealth, "drawdown": drawdown})


def build_layer2a_bundle(
    weekly_prices: pd.DataFrame,
    layer1: Layer1Bundle,
    *,
    weekly_simple_returns: pd.DataFrame | None = None,
    legacy_end_of_sample: bool = True,
    frozen_positions: dict[str, pd.DataFrame] | None = None,
    frozen_cutoff: str | pd.Timestamp | None = None,
) -> Layer2ABundle:
    columns = _available(RESEARCH_UNIVERSE, weekly_prices.columns)
    prices = weekly_prices.apply(pd.to_numeric, errors="coerce").reindex(columns=columns)
    panels = {name: panel.reindex(index=prices.index, columns=columns) for name, panel in layer1.panels.items()}
    simple = prices.pct_change(fill_method=None) if weekly_simple_returns is None else weekly_simple_returns.reindex_like(prices)
    broad = _available(BROAD_RISK, prices.columns)
    dual_assets = _available(DUAL_ASSETS, prices.columns)
    vol = simple.rolling(CTA_VOL_WINDOW, min_periods=max(8, CTA_VOL_WINDOW // 2)).std() * np.sqrt(WEEKS_PER_YEAR)

    relative = panels["xsmom_global"].reindex(columns=dual_assets)
    absolute = panels["xsmom_raw_return_52_4w"].shift(1).reindex(columns=dual_assets)
    targets: dict[str, pd.DataFrame] = {
        "dual_momentum_topn": _dual(relative, absolute, top_n=3),
        "cta_trend_long_only": _cta(panels["multi_mom_invvol"].reindex(columns=broad), vol.reindex(columns=broad)),
        "taa_10m_sma": _taa(prices),
    }
    selective_names = ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy", "carry_proxy"]
    selective = _combine({name: panels[name] for name in selective_names})
    targets["composite_selective_signals"] = _top_n(selective.reindex(columns=broad), top_n=4)

    baseline_names = ["xsmom_global", "multi_mom_invvol", "residual_momentum", "quality_proxy", "value_proxy", "carry_proxy", "bab_proxy", "reversal_4w_global"]
    state, overlay, environment = _risk_state(layer1.regime_features, prices.index)
    history = _regime_weights(prices.index, baseline_names, state, environment)
    regime_composite = _combine({name: panels[name] for name in baseline_names}, history)
    regime_target = _top_n(regime_composite.reindex(columns=broad), top_n=4)
    risky = [name for name in regime_target.columns if name != CASH]
    regime_target[risky] = regime_target[risky].mul(overlay, axis=0)
    regime_target[CASH] = 1.0 - regime_target[risky].sum(axis=1)
    targets["composite_regime_conditioned"] = regime_target.fillna(0.0)

    positions: dict[str, pd.DataFrame] = {}
    for name in SLEEVES:
        frozen = None if frozen_positions is None else frozen_positions.get(name)
        positions[name] = _schedule(
            targets[name], frequency="monthly" if name in MONTHLY_SLEEVES else "weekly",
            legacy_end_of_sample=legacy_end_of_sample, frozen=frozen,
            cutoff=None if frozen_cutoff is None else pd.Timestamp(frozen_cutoff),
        )
    paths = {name: strategy_path(frame, prices) for name, frame in positions.items()}
    return Layer2ABundle(
        positions=positions,
        paths=paths,
        source_status={name: "complete" for name in SLEEVES},
    )
