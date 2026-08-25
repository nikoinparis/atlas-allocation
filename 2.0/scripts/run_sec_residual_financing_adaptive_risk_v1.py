#!/usr/bin/env python3
"""Compare realistic financing and causal risk controls around the residual sleeve."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_real_tournament_v2 import build_family_weights
from systematic_trader import sec_tournament_rehearsal as engine

CONFIG = ROOT / "config/sec_residual_financing_adaptive_risk_v1.json"
CANDIDATE = ROOT / "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv"
COMMON_AUDIT = ROOT / "evidence/sec_independent_sleeve_return_accelerator_v1/common_endpoint_audit.json"
PANEL = ROOT / "data/sec_broad_research_panel_v2"
PROGRAM = ROOT / "config/sec_return_improvement_program_v1.json"
OUTPUT = ROOT / "evidence/sec_residual_financing_adaptive_risk_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def statistics(values: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    wealth = (1.0 + clean).cumprod()
    years = len(clean) / 52.0
    volatility = clean.std(ddof=1)
    return {
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years else 0.0,
        "sharpe": float(clean.mean() / volatility * np.sqrt(52.0)) if volatility else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()) if len(clean) else 0.0,
        "weeks": int(len(clean)),
    }


def adaptive_multipliers(returns: pd.Series, rules: dict[str, float]) -> pd.Series:
    """Choose exposure using only returns observable before each target week."""
    prior = pd.to_numeric(returns, errors="coerce").shift(int(rules["signal_lag_weeks"]))
    vol = prior.rolling(int(rules["volatility_lookback_weeks"]), min_periods=int(rules["volatility_lookback_weeks"])).std(ddof=1) * np.sqrt(52.0)
    short = (1.0 + prior).rolling(int(rules["short_trend_weeks"]), min_periods=int(rules["short_trend_weeks"])).apply(np.prod, raw=True) - 1.0
    long = (1.0 + prior).rolling(int(rules["long_trend_weeks"]), min_periods=int(rules["long_trend_weeks"])).apply(np.prod, raw=True) - 1.0
    wealth = (1.0 + prior.fillna(0.0)).cumprod()
    rolling_peak = wealth.rolling(int(rules["drawdown_lookback_weeks"]), min_periods=1).max()
    drawdown = wealth / rolling_peak - 1.0
    result = pd.Series(float(rules["minimum"]), index=returns.index, name="target_multiplier")
    middle = (
        (vol <= float(rules["maximum_volatility_for_middle"]))
        & (short > float(rules["minimum_short_trend"]))
        & (long > float(rules["minimum_long_trend"]))
        & (drawdown > float(rules["minimum_drawdown_for_middle"]))
    )
    high = (
        (vol <= float(rules["maximum_volatility_for_high"]))
        & (short > float(rules["minimum_short_trend"]))
        & (long > float(rules["minimum_long_trend"]))
        & (drawdown > float(rules["minimum_drawdown_for_high"]))
    )
    enough = prior.rolling(int(rules["minimum_history_weeks"])).count() >= int(rules["minimum_history_weeks"])
    result.loc[middle & enough] = float(rules["middle"])
    result.loc[high & enough] = float(rules["maximum"])
    return result


def apply_exposure(
    asset_returns: pd.Series,
    desired_multiplier: pd.Series,
    annual_financing_rate: float,
    leverage_change_cost_bps: float,
    margin_rules: dict[str, float],
) -> tuple[pd.Series, pd.DataFrame]:
    """Accrue borrowing weekly and force next-week deleveraging after a safety breach."""
    previous = 1.0
    force_next = False
    path: list[float] = []
    audit: list[dict[str, object]] = []
    for date, base_return in pd.to_numeric(asset_returns, errors="coerce").dropna().items():
        desired = float(desired_multiplier.reindex(asset_returns.index).loc[date])
        multiplier = float(margin_rules["forced_deleverage_target"]) if force_next else desired
        forced_this_week = force_next
        force_next = False
        borrowing = max(0.0, multiplier - 1.0)
        financing_cost = borrowing * float(annual_financing_rate) / 52.0
        change_cost = abs(multiplier - previous) * float(leverage_change_cost_bps) / 10000.0
        net_return = multiplier * float(base_return) - financing_cost - change_cost
        assets_after = multiplier * (1.0 + float(base_return))
        debt_after = borrowing * (1.0 + float(annual_financing_rate) / 52.0)
        equity_after = assets_after - debt_after
        equity_ratio = equity_after / assets_after if assets_after > 0 else -np.inf
        maintenance_breach = equity_ratio < float(margin_rules["broker_maintenance_equity_ratio"])
        safety_breach = equity_ratio < float(margin_rules["internal_safety_equity_ratio"])
        if safety_breach:
            force_next = True
            net_return -= float(margin_rules["forced_deleverage_cost_bps"]) / 10000.0
        path.append(net_return)
        audit.append({
            "Date": date,
            "base_return": float(base_return),
            "desired_multiplier": desired,
            "actual_multiplier": multiplier,
            "borrowed_fraction": borrowing,
            "financing_cost": financing_cost,
            "leverage_change_cost": change_cost,
            "post_return_equity_ratio": equity_ratio,
            "maintenance_breach": bool(maintenance_breach),
            "internal_safety_breach": bool(safety_breach),
            "forced_deleverage": bool(forced_this_week),
        })
        previous = multiplier
    return pd.Series(path, index=pd.to_datetime([row["Date"] for row in audit]), name="net_return"), pd.DataFrame(audit).set_index("Date")


def cap_standalone_risk_contributions(
    weights: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    rules: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cap issuer volatility-budget shares using only pre-decision returns."""
    rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    lookback = int(rules["lookback_weeks"])
    minimum = int(rules["minimum_history_weeks"])
    cap = float(rules["maximum_standalone_volatility_contribution_share"])
    for decision, frame in weights.groupby("decision_at", sort=True):
        decision_at = pd.Timestamp(decision)
        selected = frame.copy().sort_values("cik10")
        original = selected.set_index("cik10").weight.astype(float)
        history = weekly_returns.loc[weekly_returns.index < decision_at, original.index].tail(lookback)
        vol = history.std(ddof=1).replace([np.inf, -np.inf], np.nan)
        valid = history.count() >= minimum
        if not bool(valid.any()):
            adjusted = original.copy()
        else:
            fallback = float(vol[valid].median())
            risk = vol.where(valid, fallback).fillna(fallback).clip(lower=1e-6)
            adjusted = original.copy()
            total_weight = float(original.sum())
            for _ in range(int(rules["maximum_iterations"])):
                contribution = adjusted * risk
                total_contribution = float(contribution.sum())
                if total_contribution <= 0:
                    break
                offenders = contribution / total_contribution > cap + 1e-10
                if not bool(offenders.any()):
                    break
                fixed = adjusted.copy()
                fixed.loc[offenders] = cap * total_contribution / risk.loc[offenders]
                remaining = total_weight - float(fixed.loc[offenders].sum())
                recipients = ~offenders
                if not bool(recipients.any()) or remaining <= 0:
                    adjusted = fixed.clip(lower=0.0)
                    break
                base = original.loc[recipients]
                fixed.loc[recipients] = remaining * base / float(base.sum())
                adjusted = fixed.clip(lower=0.0)
            if adjusted.sum() > 0:
                adjusted *= total_weight / float(adjusted.sum())
        contribution = adjusted * vol.reindex(adjusted.index).fillna(0.0)
        max_share = float(contribution.max() / contribution.sum()) if contribution.sum() > 0 else 0.0
        diagnostics.append({
            "decision_at": decision_at,
            "issuer_count": int(len(adjusted)),
            "maximum_risk_contribution_share": max_share,
            "weights_changed": bool((adjusted - original).abs().max() > 1e-10),
            "maximum_capital_weight": float(adjusted.max()) if len(adjusted) else 0.0,
        })
        rows.extend({"decision_at": decision_at, "cik10": cik, "weight": float(weight)} for cik, weight in adjusted.items())
    return pd.DataFrame(rows), pd.DataFrame(diagnostics)


def shock_table(multiplier: float, annual_rate: float, rules: dict[str, object]) -> pd.DataFrame:
    rows = []
    debt = max(0.0, float(multiplier) - 1.0)
    for shock in rules["one_week_asset_shocks"]:
        assets = float(multiplier) * (1.0 + float(shock))
        debt_after = debt * (1.0 + float(annual_rate) / 52.0)
        equity = assets - debt_after
        ratio = equity / assets if assets > 0 else -np.inf
        rows.append({
            "asset_shock": float(shock),
            "equity_return_before_liquidation_cost": equity - 1.0,
            "post_shock_equity_ratio": ratio,
            "internal_safety_breach": ratio < float(rules["internal_safety_equity_ratio"]),
            "broker_maintenance_breach": ratio < float(rules["broker_maintenance_equity_ratio"]),
        })
    return pd.DataFrame(rows)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "result.json"
    if result_path.exists():
        raise RuntimeError("adaptive financing comparison is one-shot")
    sealed_files = [CONFIG, Path(__file__), CANDIDATE, CONTROL, COMMON_AUDIT, PROGRAM, PANEL / "manifest.json"]
    seal = {
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "performance_evaluated_at_seal": False,
        "sealed_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sealed_files},
    }
    (OUTPUT / "execution_seal.json").write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n")

    common_audit = json.loads(COMMON_AUDIT.read_text())
    common_endpoint = pd.Timestamp(common_audit["common_endpoint"], tz="UTC")
    candidate = pd.read_csv(CANDIDATE, parse_dates=["Date"]).set_index("Date").net_return
    candidate.index = pd.to_datetime(candidate.index, utc=True)
    candidate = candidate.loc[:common_endpoint].dropna()

    leverage_rules = config["leverage"]
    margin_rules = config["margin"]
    financing = config["financing"]
    fixed = pd.Series(float(leverage_rules["maximum"]), index=candidate.index)
    one = pd.Series(1.0, index=candidate.index)
    adaptive = adaptive_multipliers(candidate, leverage_rules)
    paths: dict[str, pd.Series] = {"unlevered_1.00x": candidate}
    audits: dict[str, pd.DataFrame] = {}
    for name, multipliers, rate, change_cost in [
        ("fixed_1.25x_5pct_published_reference", fixed, financing["published_reference_annual_rate"], 0.0),
        ("fixed_1.25x_realistic_financing", fixed, financing["baseline_annual_rate"], 0.0),
        ("adaptive_1.00x_to_1.25x", adaptive, financing["baseline_annual_rate"], leverage_rules["leverage_change_cost_bps"]),
    ]:
        paths[name], audits[name] = apply_exposure(candidate, multipliers, float(rate), float(change_cost), margin_rules)

    panel = pd.read_csv(PANEL / "panel.csv.gz", dtype={"cik10": str})
    weekly = pd.read_csv(PANEL / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    program = json.loads(PROGRAM.read_text())
    family_weights, _ = build_family_weights(panel, program)
    residual_weights = family_weights["residual_momentum"].copy()
    capped_weights, cap_diagnostics = cap_standalone_risk_contributions(residual_weights, weekly, config["residual_risk_contribution"])
    capped_residual = engine.portfolio_path(capped_weights, weekly, 50, 0)[0]
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return
    control.index = pd.to_datetime(control.index, utc=True)
    capped_base = pd.concat([control.rename("control"), capped_residual.rename("residual")], axis=1).dropna()
    capped_base = (0.8 * capped_base.control + 0.2 * capped_base.residual).loc[:common_endpoint]
    capped_adaptive = adaptive_multipliers(capped_base, leverage_rules)
    capped_name = "adaptive_with_residual_risk_contribution_limit"
    paths[capped_name], audits[capped_name] = apply_exposure(
        capped_base, capped_adaptive, float(financing["baseline_annual_rate"]),
        float(leverage_rules["leverage_change_cost_bps"]), margin_rules,
    )

    metric_rows = []
    for name, values in paths.items():
        windows = {"full": values, "trailing_52w": values.tail(52), "trailing_104w": values.tail(104)}
        for window, subset in windows.items():
            metric_rows.append({"variant": name, "window": window, **statistics(subset)})
    metrics = pd.DataFrame(metric_rows)

    stress_rows = []
    for name, base, multipliers in [
        ("fixed", candidate, fixed),
        ("adaptive", candidate, adaptive),
        ("adaptive_risk_cap", capped_base, capped_adaptive),
    ]:
        for rate in config["evaluation"]["financing_rates"]:
            for cost in config["evaluation"]["cost_stress_bps"]:
                stressed, audit = apply_exposure(base, multipliers, float(rate), float(cost), margin_rules)
                stress_rows.append({
                    "variant": name, "annual_financing_rate": float(rate), "leverage_change_cost_bps": float(cost),
                    **statistics(stressed.tail(52)),
                    "margin_safety_breaches": int(audit.internal_safety_breach.sum()),
                    "forced_deleveraging_weeks": int(audit.forced_deleverage.sum()),
                })
    stress = pd.DataFrame(stress_rows)

    fixed_recent = paths["fixed_1.25x_realistic_financing"].tail(52)
    bootstrap_rows = []
    for name in ("adaptive_1.00x_to_1.25x", capped_name):
        difference = paths[name].tail(52) - fixed_recent.reindex(paths[name].tail(52).index)
        for block in config["evaluation"]["bootstrap_blocks_weeks"]:
            raw = engine.bootstrap_probability(difference, int(block), int(config["evaluation"]["bootstrap_draws"]), int(config["evaluation"]["bootstrap_seed"]))
            trials = int(config["evaluation"]["familywise_trials"])
            adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw) * trials))
            bootstrap_rows.append({"variant": name, "block_weeks": int(block), "raw_probability_positive": raw, "familywise_probability_positive": adjusted})
    bootstrap = pd.DataFrame(bootstrap_rows)

    shocks = shock_table(float(leverage_rules["maximum"]), float(financing["baseline_annual_rate"]), margin_rules)
    for name, values in paths.items():
        values.rename("net_return").rename_axis("Date").to_csv(OUTPUT / f"path__{name}.csv")
    for name, audit in audits.items():
        audit.rename_axis("Date").to_csv(OUTPUT / f"exposure_audit__{name}.csv")
    adaptive.rename("target_multiplier").rename_axis("Date").to_csv(OUTPUT / "adaptive_multipliers.csv")
    capped_weights.to_csv(OUTPUT / "capped_residual_weights.csv", index=False)
    cap_diagnostics.to_csv(OUTPUT / "risk_contribution_diagnostics.csv", index=False)
    metrics.to_csv(OUTPUT / "metrics.csv", index=False)
    stress.to_csv(OUTPUT / "stress_grid.csv", index=False)
    bootstrap.to_csv(OUTPUT / "block_bootstrap.csv", index=False)
    shocks.to_csv(OUTPUT / "margin_shocks.csv", index=False)

    primary = metrics[metrics.window.eq("trailing_52w")].set_index("variant")
    benchmark = primary.loc["fixed_1.25x_realistic_financing"]
    candidate_rows = primary.loc[["adaptive_1.00x_to_1.25x", capped_name]]
    qualifies = candidate_rows[
        (candidate_rows.cagr > benchmark.cagr)
        & (candidate_rows.sharpe >= benchmark.sharpe)
        & (candidate_rows.max_drawdown >= benchmark.max_drawdown)
    ]
    winner = None if qualifies.empty else str(qualifies.sort_values(["cagr", "sharpe"], ascending=False).index[0])
    artifacts = sorted(path.name for path in OUTPUT.iterdir() if path.name != "result.json")
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "common_endpoint": common_audit["common_endpoint"],
        "selection_contaminated": True,
        "published_reference_trailing_52w": primary.loc["fixed_1.25x_5pct_published_reference"].to_dict(),
        "realistic_fixed_trailing_52w": benchmark.to_dict(),
        "adaptive_trailing_52w": primary.loc["adaptive_1.00x_to_1.25x"].to_dict(),
        "adaptive_risk_cap_trailing_52w": primary.loc[capped_name].to_dict(),
        "research_display_winner": winner,
        "replacement_authorized": False,
        "frozen_forward_candidate_modified": False,
        "forward_clock_weeks": 0,
        "live_trading_enabled": False,
        "historical_margin_safety_breaches": {name: int(audit.internal_safety_breach.sum()) for name, audit in audits.items()},
        "maximum_observed_residual_risk_contribution_share": float(cap_diagnostics.maximum_risk_contribution_share.max()),
        "interpretation": "A historical winner may be shown as a research diagnostic only. These rules were specified after the historical sample was known, so untouched forward evidence remains required.",
        "artifact_sha256": {name: sha256(OUTPUT / name) for name in artifacts},
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
