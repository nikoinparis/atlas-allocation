from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
CHECKPOINT_DIR = ROOT / "data" / "research" / "allocator_checkpoints"
OUT_DATA = ROOT / "data" / "research" / "turnover_frontier"
OUT_REPORT = ROOT / "reports" / "turnover_frontier"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
WEEKS_PER_YEAR = 52
HOLDOUT_WEEKS = 156
BASE_COST_BPS = 10.0
CASH_PROXY = "BIL"
DEFENSIVE_ASSETS = {"BIL", "IEF", "SHY", "TLT", "TIP", "GLD"}


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    turnover_alpha: float | None
    cost_bps: float
    note: str


VARIANTS = [
    Variant(
        "production_current",
        "Current production turnover setting",
        None,
        BASE_COST_BPS,
        "Existing production artifact, unchanged.",
    ),
    Variant(
        "lower_penalty_50",
        "50% lower turnover penalty",
        0.70,
        BASE_COST_BPS,
        "Research proxy: move 50% of the way from production's 0.40 sleeve reallocation speed toward no smoothing.",
    ),
    Variant(
        "lower_penalty_75",
        "75% lower turnover penalty",
        0.85,
        BASE_COST_BPS,
        "Research proxy: move 75% of the way from production's 0.40 sleeve reallocation speed toward no smoothing.",
    ),
    Variant(
        "turnover_cap_2x",
        "2x higher turnover cap if caps exist",
        0.80,
        BASE_COST_BPS,
        "Research proxy: double the effective sleeve-change speed from 0.40 to 0.80. No explicit hard turnover cap was found.",
    ),
    Variant(
        "turnover_cap_4x",
        "4x higher turnover cap if caps exist",
        1.00,
        BASE_COST_BPS,
        "Research proxy: four times the 0.40 speed saturates at immediate movement to the saved target sleeve.",
    ),
    Variant(
        "no_penalty_no_cap",
        "No turnover penalty / no turnover cap",
        1.00,
        BASE_COST_BPS,
        "Immediate movement to the saved target sleeve at rebalance dates; risk overlay gross exposure is held to production to isolate turnover smoothing.",
    ),
    Variant(
        "no_penalty_2x_costs",
        "No turnover penalty with 2x transaction costs",
        1.00,
        BASE_COST_BPS * 2.0,
        "Same immediate-turnover weights as no_penalty_no_cap, with doubled transaction costs.",
    ),
    Variant(
        "no_penalty_3x_costs",
        "No turnover penalty with 3x transaction costs",
        1.00,
        BASE_COST_BPS * 3.0,
        "Same immediate-turnover weights as no_penalty_no_cap, with tripled transaction costs.",
    ),
]


def read_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame.index.name = None
    return frame.sort_index().fillna(0.0)


def read_returns(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame.index.name = None
    return frame.sort_index()


def annualized_return(returns: pd.Series) -> float:
    returns = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return np.nan
    wealth = float((1.0 + returns).prod())
    years = len(returns) / WEEKS_PER_YEAR
    if wealth <= 0 or years <= 0:
        return np.nan
    return wealth ** (1.0 / years) - 1.0


def annualized_vol(returns: pd.Series) -> float:
    returns = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(returns) < 2:
        return np.nan
    return float(returns.std(ddof=1) * math.sqrt(WEEKS_PER_YEAR))


def max_drawdown(returns: pd.Series) -> float:
    returns = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return np.nan
    wealth = (1.0 + returns).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def cvar_5(returns: pd.Series) -> float:
    returns = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return np.nan
    cutoff = returns.quantile(0.05)
    tail = returns[returns <= cutoff]
    return float(tail.mean()) if len(tail) else np.nan


def metric_block(returns: pd.Series) -> dict[str, float]:
    ann_ret = annualized_return(returns)
    ann_vol = annualized_vol(returns)
    mdd = max_drawdown(returns)
    return {
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": ann_ret / ann_vol if pd.notna(ann_ret) and pd.notna(ann_vol) and ann_vol > 0 else np.nan,
        "max_drawdown": mdd,
        "calmar": ann_ret / abs(mdd) if pd.notna(ann_ret) and pd.notna(mdd) and mdd < 0 else np.nan,
        "cvar_5": cvar_5(returns),
    }


def compute_path(weights: pd.DataFrame, forward_returns: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    aligned_returns = forward_returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    gross = (weights * aligned_returns).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * (float(cost_bps) / 10_000.0)
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth.div(wealth.cummax()).sub(1.0)
    return pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": drawdown,
        }
    )


def apply_cost_to_saved_gross(path: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    out = path.copy()
    turnover = pd.Series(out["turnover"], dtype=float)
    cost = turnover.fillna(0.0) * (float(cost_bps) / 10_000.0)
    out["cost"] = cost
    out["net_return"] = out["gross_return"] - cost
    out["wealth"] = (1.0 + out["net_return"].fillna(0.0)).cumprod()
    out["drawdown"] = out["wealth"].div(out["wealth"].cummax()).sub(1.0)
    return out


def load_market_state() -> pd.DataFrame:
    state = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    state["Date"] = pd.to_datetime(state["Date"]).dt.tz_localize(None)
    return state.set_index("Date").sort_index()


def load_sleeve_positions(sleeve_cols: list[str], index: pd.Index, universe: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sleeve in sleeve_cols:
        if sleeve.startswith("cash::"):
            continue
        path = LAYER2A_DIR / f"strategy_positions_{sleeve}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing sleeve position file for {sleeve}: {path}")
        pos = read_panel(path)
        out[sleeve] = pos.reindex(index=index, columns=universe).ffill().fillna(0.0)
    return out


def build_lookthrough_weights(
    sleeve_weights: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    universe: list[str],
) -> pd.DataFrame:
    rows: list[pd.Series] = []
    for date, row in sleeve_weights.iterrows():
        etf = pd.Series(0.0, index=universe, dtype=float)
        cash = float(row.get(f"cash::{CASH_PROXY}", 0.0) or 0.0)
        if CASH_PROXY in etf.index:
            etf.loc[CASH_PROXY] += cash
        for sleeve, pos in sleeve_positions.items():
            weight = float(row.get(sleeve, 0.0) or 0.0)
            if abs(weight) <= 1e-12:
                continue
            etf = etf.add(weight * pos.loc[date].reindex(universe).fillna(0.0), fill_value=0.0)
        total = float(etf.sum())
        if total > 1e-12:
            etf = etf / total
        etf.name = date
        rows.append(etf)
    return pd.DataFrame(rows).sort_index().fillna(0.0)


def production_target_sleeves(raw_sleeves: pd.DataFrame, prod_final_sleeves: pd.DataFrame) -> pd.DataFrame:
    """Approximate the no-smoothing target while preserving production gross risk budget.

    The saved post-layer3-expression checkpoint is the current target sleeve mix
    before production's overlay/smoothing path. We keep production's observed
    cash/gross overlay level each week so this audit isolates turnover smoothing
    rather than relaxing risk-overlay cash controls.
    """
    target = pd.DataFrame(0.0, index=prod_final_sleeves.index, columns=prod_final_sleeves.columns)
    risky_cols = [c for c in prod_final_sleeves.columns if not c.startswith("cash::")]
    prod_cash = prod_final_sleeves.get(f"cash::{CASH_PROXY}", pd.Series(1.0, index=prod_final_sleeves.index)).clip(0.0, 1.0)
    gross_budget = (1.0 - prod_cash).clip(0.0, 1.0)
    raw_risky = raw_sleeves.reindex(index=target.index, columns=risky_cols).fillna(0.0).clip(lower=0.0)
    raw_sum = raw_risky.sum(axis=1).replace(0.0, np.nan)
    target.loc[:, risky_cols] = raw_risky.div(raw_sum, axis=0).fillna(0.0).mul(gross_budget, axis=0)
    target[f"cash::{CASH_PROXY}"] = 1.0 - target[risky_cols].sum(axis=1)
    return target.reindex(columns=prod_final_sleeves.columns).fillna(0.0)


def smoothed_counterfactual(target: pd.DataFrame, alpha: float) -> pd.DataFrame:
    out_rows: list[pd.Series] = []
    prev = target.iloc[0].copy()
    out_rows.append(prev.rename(target.index[0]))
    # The target checkpoint is forward-filled between rebalance dates. Apply
    # speed only when the target changes, matching monthly production behavior.
    target_change = target.diff().abs().sum(axis=1).fillna(0.0) > 1e-10
    for date in target.index[1:]:
        desired = target.loc[date]
        if bool(target_change.loc[date]):
            curr = (1.0 - alpha) * prev + alpha * desired
        else:
            curr = prev.copy()
        curr = curr.clip(lower=0.0)
        total = float(curr.sum())
        if total > 1e-12:
            curr = curr / total
        curr.name = date
        out_rows.append(curr)
        prev = curr
    return pd.DataFrame(out_rows).sort_index().fillna(0.0)


def exposure_stats(weights: pd.DataFrame) -> dict[str, float]:
    defensive = [c for c in weights.columns if c in DEFENSIVE_ASSETS and c != CASH_PROXY]
    offensive = [c for c in weights.columns if c not in DEFENSIVE_ASSETS]
    return {
        "avg_BIL_cash": float(weights.get(CASH_PROXY, pd.Series(0.0, index=weights.index)).mean()),
        "avg_SPY": float(weights.get("SPY", pd.Series(0.0, index=weights.index)).mean()),
        "avg_offensive_exposure": float(weights.reindex(columns=offensive, fill_value=0.0).sum(axis=1).mean()),
        "avg_defensive_exposure": float(weights.reindex(columns=defensive, fill_value=0.0).sum(axis=1).mean()),
    }


def row_for_variant(
    variant: Variant,
    path: pd.DataFrame,
    weights: pd.DataFrame,
    prod_full: dict[str, float] | None = None,
    prod_holdout: dict[str, float] | None = None,
) -> dict[str, object]:
    full = metric_block(path["net_return"])
    holdout = metric_block(path["net_return"].tail(HOLDOUT_WEEKS))
    gross_full = metric_block(path["gross_return"])
    out: dict[str, object] = {
        "variant": variant.name,
        "label": variant.label,
        "production_pin": PRODUCTION_PIN,
        "turnover_alpha": variant.turnover_alpha if variant.turnover_alpha is not None else np.nan,
        "transaction_cost_bps": variant.cost_bps,
        **full,
        "holdout_ann_return": holdout["ann_return"],
        "holdout_ann_vol": holdout["ann_vol"],
        "holdout_sharpe": holdout["sharpe"],
        "holdout_max_drawdown": holdout["max_drawdown"],
        "holdout_cvar_5": holdout["cvar_5"],
        "avg_turnover": float(path["turnover"].dropna().mean()),
        "annual_turnover": float(path["turnover"].dropna().mean() * WEEKS_PER_YEAR),
        "cost_drag": float(gross_full["ann_return"] - full["ann_return"]),
        "avg_weekly_cost": float(path["cost"].mean()),
        **exposure_stats(weights),
        "note": variant.note,
    }
    if prod_full:
        for key in ["ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5"]:
            out[f"delta_{key}_vs_production"] = float(out[key]) - float(prod_full[key])
        out["delta_avg_turnover_vs_production"] = float(out["avg_turnover"]) - float(prod_full["avg_turnover"])
        out["turnover_ratio_vs_production"] = (
            float(out["avg_turnover"]) / float(prod_full["avg_turnover"])
            if float(prod_full["avg_turnover"]) > 0
            else np.nan
        )
    if prod_holdout:
        out["holdout_ann_return_delta_vs_production"] = float(out["holdout_ann_return"]) - float(prod_holdout["ann_return"])
        out["holdout_sharpe_delta_vs_production"] = float(out["holdout_sharpe"]) - float(prod_holdout["sharpe"])
        out["holdout_max_drawdown_delta_vs_production"] = float(out["holdout_max_drawdown"]) - float(prod_holdout["max_drawdown"])
    return out


def state_rows_for_variant(variant: Variant, path: pd.DataFrame, weights: pd.DataFrame, states: pd.DataFrame) -> list[dict[str, object]]:
    joined = path.join(states[["market_state"]], how="left").join(weights.add_prefix("w_"), how="left")
    rows: list[dict[str, object]] = []
    for state, sub in joined.dropna(subset=["market_state"]).groupby("market_state"):
        weight_sub = weights.reindex(sub.index)
        metrics = metric_block(sub["net_return"])
        rows.append(
            {
                "variant": variant.name,
                "label": variant.label,
                "market_state": state,
                "n_weeks": int(len(sub)),
                **metrics,
                "avg_turnover": float(sub["turnover"].dropna().mean()),
                "cost_drag": float(sub["cost"].mean() * WEEKS_PER_YEAR),
                **exposure_stats(weight_sub),
            }
        )
    return rows


def fmt_pct(x: float, digits: int = 2) -> str:
    return "n/a" if pd.isna(x) else f"{x * 100:.{digits}f}%"


def fmt_num(x: float, digits: int = 3) -> str:
    return "n/a" if pd.isna(x) else f"{x:.{digits}f}"


def markdown_table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            if any(token in col for token in ["sharpe", "calmar", "per_extra_turnover"]):
                view[col] = view[col].map(lambda x: fmt_num(x, 3))
            elif any(token in col for token in ["return", "vol", "drawdown", "cvar", "turnover", "drag", "BIL", "SPY", "exposure", "cost"]):
                view[col] = view[col].map(lambda x: fmt_pct(x, 2))
            else:
                view[col] = view[col].map(lambda x: fmt_num(x, 3))
    view = view.fillna("n/a").astype(str)
    headers = list(view.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def build_report(results: pd.DataFrame, state_df: pd.DataFrame, frontier: pd.DataFrame, cost_sensitivity: pd.DataFrame) -> str:
    prod = results.loc[results["variant"] == "production_current"].iloc[0]
    higher = results[
        (results["variant"] != "production_current")
        & (results["transaction_cost_bps"] == BASE_COST_BPS)
        & (results["avg_turnover"] > float(prod["avg_turnover"]) + 1e-8)
    ].copy()
    acceptance = higher[
        (higher["delta_ann_return_vs_production"] >= 0.0025)
        & (higher["delta_sharpe_vs_production"] >= -0.02)
        & (higher["delta_max_drawdown_vs_production"] >= -0.005)
        & (higher["delta_cvar_5_vs_production"] >= -0.001)
        & (higher["holdout_ann_return_delta_vs_production"] > 0.0)
    ].copy()
    if not acceptance.empty:
        best = acceptance.sort_values(["holdout_ann_return_delta_vs_production", "delta_ann_return_vs_production"], ascending=False).iloc[0]
        best_text = f"`{best['variant']}` ({best['label']})"
    elif not higher.empty:
        best = higher.sort_values(["holdout_ann_return_delta_vs_production", "delta_ann_return_vs_production"], ascending=False).iloc[0]
        best_text = f"No accepted candidate. Best diagnostic higher-turnover row: `{best['variant']}` ({best['label']})."
    else:
        best_text = "No higher-turnover candidate was produced."

    no_penalty = results.loc[results["variant"] == "no_penalty_no_cap"].iloc[0]
    stress2 = results.loc[results["variant"] == "no_penalty_2x_costs"].iloc[0]
    stress3 = results.loc[results["variant"] == "no_penalty_3x_costs"].iloc[0]
    helped = (
        "helped on full-sample net return"
        if no_penalty["delta_ann_return_vs_production"] > 0
        else "hurt full-sample net return"
    )
    oos = (
        "survived holdout"
        if no_penalty["holdout_ann_return_delta_vs_production"] > 0
        else "did not survive holdout"
    )
    cost_survives = bool(stress2["delta_ann_return_vs_production"] > 0 and stress3["delta_ann_return_vs_production"] > 0)
    frontier_positive = frontier[
        (frontier["extra_turnover"] > 1e-8)
        & (frontier["return_gained_per_extra_turnover"].fillna(-np.inf) > 0)
    ]
    stop_text = (
        "No positive marginal return/turnover point was found."
        if frontier_positive.empty
        else f"Marginal benefit is highest at `{frontier_positive.sort_values('return_gained_per_extra_turnover', ascending=False).iloc[0]['variant']}`; later rows should be treated as diminishing/fragile if holdout or cost stress fails."
    )

    lines = [
        "# Turnover Frontier Audit",
        "",
        f"Production pin: `{PRODUCTION_PIN}`. This is a research audit only; no production files or pins are promoted.",
        "",
        "## Important Implementation Note",
        "",
        "The production pin is HRP-based, so the notebook's optimizer `TURNOVER_PENALTY` constant is not directly binding for this strategy path. The audit therefore tests the effective turnover control: the sleeve reallocation speed/dynamic smoothing that governs how quickly the portfolio moves toward saved production target sleeves. The saved production gross risk/cash budget is preserved to isolate turnover smoothing rather than loosening the risk overlay.",
        "",
        "## Headline Results",
        "",
        markdown_table(
            results,
            [
                "variant",
                "ann_return",
                "ann_vol",
                "sharpe",
                "max_drawdown",
                "calmar",
                "cvar_5",
                "avg_turnover",
                "cost_drag",
                "avg_BIL_cash",
                "avg_SPY",
                "avg_offensive_exposure",
                "holdout_ann_return",
                "holdout_sharpe",
            ],
        ),
        "",
        "## Frontier",
        "",
        markdown_table(
            frontier,
            [
                "variant",
                "extra_turnover",
                "delta_ann_return_vs_production",
                "return_gained_per_extra_turnover",
                "delta_sharpe_vs_production",
                "sharpe_gained_per_extra_turnover",
                "cost_sensitivity_2x_ann_return_delta",
                "cost_sensitivity_3x_ann_return_delta",
            ],
        ),
        "",
        "## State-By-State",
        "",
        markdown_table(
            state_df,
            [
                "variant",
                "market_state",
                "n_weeks",
                "ann_return",
                "sharpe",
                "max_drawdown",
                "cvar_5",
                "avg_turnover",
                "avg_BIL_cash",
                "avg_SPY",
                "avg_offensive_exposure",
            ],
        ),
        "",
        "## Cost Sensitivity",
        "",
        markdown_table(
            cost_sensitivity,
            [
                "base_variant",
                "ann_return_1x_cost",
                "ann_return_2x_cost",
                "ann_return_3x_cost",
                "delta_2x_vs_1x",
                "delta_3x_vs_1x",
                "sharpe_1x_cost",
                "sharpe_2x_cost",
                "sharpe_3x_cost",
            ],
        ),
        "",
        "## Audit Readout",
        "",
        f"- Best higher-turnover candidate: {best_text}",
        f"- Removing turnover controls {helped} and {oos}.",
        f"- Transaction-cost stress survival for the no-penalty/no-cap path: {'yes' if cost_survives else 'no'}.",
        f"- Point where extra turnover stops helping: {stop_text}",
        "- Current turnover control verdict: too strict only if a higher-turnover row improves net return, risk, cost stress, and holdout together. The acceptance filters above are intentionally conservative.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.mkdir(parents=True, exist_ok=True)

    prod_returns = read_returns(LAYER3_DIR / f"portfolio_version_returns_{PRODUCTION_PIN}.csv")
    prod_weights = read_panel(LAYER3_DIR / f"portfolio_version_weights_{PRODUCTION_PIN}.csv")
    prod_sleeves = read_panel(LAYER3_DIR / f"portfolio_version_sleeve_weights_{PRODUCTION_PIN}.csv")
    final_sleeves = read_panel(CHECKPOINT_DIR / f"{PRODUCTION_PIN}__final_sleeve_weights.csv")
    raw_sleeves = read_panel(CHECKPOINT_DIR / f"{PRODUCTION_PIN}__post_layer3_expression_sleeve_weights.csv")
    states = load_market_state()

    weekly_returns = read_panel(LAYER1_DIR / "weekly_returns.csv")
    forward_returns = weekly_returns.shift(-1)
    universe = list(prod_weights.columns)
    sleeve_positions = load_sleeve_positions(list(final_sleeves.columns), final_sleeves.index, universe)

    target_sleeves = production_target_sleeves(raw_sleeves, final_sleeves)

    # Keep current production exactly as saved. Build counterfactuals only for
    # research variants.
    variant_sleeves: dict[str, pd.DataFrame] = {
        "production_current": prod_sleeves.reindex(final_sleeves.index, columns=final_sleeves.columns).fillna(0.0)
    }
    for variant in VARIANTS:
        if variant.name == "production_current":
            continue
        if variant.turnover_alpha is None:
            raise ValueError(f"Variant {variant.name} needs a turnover alpha")
        base_name = "no_penalty_no_cap" if variant.name in {"no_penalty_2x_costs", "no_penalty_3x_costs"} else variant.name
        if base_name in variant_sleeves:
            variant_sleeves[variant.name] = variant_sleeves[base_name]
        else:
            variant_sleeves[variant.name] = smoothed_counterfactual(target_sleeves, float(variant.turnover_alpha))

    results_rows: list[dict[str, object]] = []
    state_rows: list[dict[str, object]] = []
    paths: dict[str, pd.DataFrame] = {}
    weights_by_variant: dict[str, pd.DataFrame] = {}
    prod_full: dict[str, float] | None = None
    prod_holdout: dict[str, float] | None = None

    for variant in VARIANTS:
        if variant.name == "production_current":
            weights = prod_weights
            path = prod_returns.reindex(prod_weights.index)
        else:
            weights = build_lookthrough_weights(variant_sleeves[variant.name], sleeve_positions, universe)
            path = compute_path(weights, forward_returns, variant.cost_bps)
        paths[variant.name] = path
        weights_by_variant[variant.name] = weights
        if variant.name == "production_current":
            prod_full = {
                **metric_block(path["net_return"]),
                "avg_turnover": float(path["turnover"].dropna().mean()),
            }
            prod_holdout = metric_block(path["net_return"].tail(HOLDOUT_WEEKS))
        results_rows.append(row_for_variant(variant, path, weights, prod_full, prod_holdout))
        state_rows.extend(state_rows_for_variant(variant, path, weights, states))

    results = pd.DataFrame(results_rows)
    state_df = pd.DataFrame(state_rows)

    # Add production-relative deltas for state-level rows.
    prod_state = state_df[state_df["variant"] == "production_current"].set_index("market_state")
    for idx, row in state_df.iterrows():
        state = row["market_state"]
        if state in prod_state.index:
            for col in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"]:
                state_df.loc[idx, f"delta_{col}_vs_production"] = row[col] - prod_state.loc[state, col]

    # Cost sensitivity for each unique weight path.
    cost_rows = []
    for base_variant in ["production_current", "lower_penalty_50", "lower_penalty_75", "turnover_cap_2x", "no_penalty_no_cap"]:
        weights = weights_by_variant[base_variant]
        if base_variant == "production_current":
            p1 = apply_cost_to_saved_gross(prod_returns, BASE_COST_BPS)
            p2 = apply_cost_to_saved_gross(prod_returns, BASE_COST_BPS * 2.0)
            p3 = apply_cost_to_saved_gross(prod_returns, BASE_COST_BPS * 3.0)
        else:
            p1 = compute_path(weights, forward_returns, BASE_COST_BPS)
            p2 = compute_path(weights, forward_returns, BASE_COST_BPS * 2.0)
            p3 = compute_path(weights, forward_returns, BASE_COST_BPS * 3.0)
        m1, m2, m3 = metric_block(p1["net_return"]), metric_block(p2["net_return"]), metric_block(p3["net_return"])
        cost_rows.append(
            {
                "base_variant": base_variant,
                "ann_return_1x_cost": m1["ann_return"],
                "ann_return_2x_cost": m2["ann_return"],
                "ann_return_3x_cost": m3["ann_return"],
                "delta_2x_vs_1x": m2["ann_return"] - m1["ann_return"],
                "delta_3x_vs_1x": m3["ann_return"] - m1["ann_return"],
                "sharpe_1x_cost": m1["sharpe"],
                "sharpe_2x_cost": m2["sharpe"],
                "sharpe_3x_cost": m3["sharpe"],
            }
        )
    cost_sensitivity = pd.DataFrame(cost_rows)

    prod_row = results[results["variant"] == "production_current"].iloc[0]
    frontier = results[results["transaction_cost_bps"] == BASE_COST_BPS].copy()
    frontier["extra_turnover"] = frontier["avg_turnover"] - float(prod_row["avg_turnover"])
    frontier["return_gained_per_extra_turnover"] = frontier["delta_ann_return_vs_production"] / frontier["extra_turnover"].replace(0.0, np.nan)
    frontier["sharpe_gained_per_extra_turnover"] = frontier["delta_sharpe_vs_production"] / frontier["extra_turnover"].replace(0.0, np.nan)
    cost_lookup = cost_sensitivity.set_index("base_variant")
    frontier["cost_sensitivity_2x_ann_return_delta"] = frontier["variant"].map(cost_lookup["delta_2x_vs_1x"])
    frontier["cost_sensitivity_3x_ann_return_delta"] = frontier["variant"].map(cost_lookup["delta_3x_vs_1x"])
    frontier = frontier.sort_values("avg_turnover").reset_index(drop=True)

    results.to_csv(OUT_DATA / "turnover_frontier_results.csv", index=False)
    state_df.to_csv(OUT_DATA / "turnover_frontier_state_by_state.csv", index=False)
    # The acceptance contract names two CSV outputs; keep frontier and cost
    # sensitivity in the main results as extra columns and as adjacent helpers.
    frontier.to_csv(OUT_DATA / "turnover_frontier_table.csv", index=False)
    cost_sensitivity.to_csv(OUT_DATA / "turnover_frontier_cost_sensitivity.csv", index=False)
    (OUT_REPORT / "turnover_frontier_audit.md").write_text(
        build_report(results, state_df, frontier, cost_sensitivity),
        encoding="utf-8",
    )

    print("Turnover frontier audit complete")
    print(f"Results: {OUT_DATA / 'turnover_frontier_results.csv'}")
    print(f"State by state: {OUT_DATA / 'turnover_frontier_state_by_state.csv'}")
    print(f"Report: {OUT_REPORT / 'turnover_frontier_audit.md'}")


if __name__ == "__main__":
    main()
