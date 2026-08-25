#!/usr/bin/env python3
"""Bounded return-first tournament for fragility repair and industry residual momentum.

This is retrospective research. It cannot promote a strategy or enable execution.
"""

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
sys.path.insert(0, str(ROOT / "scripts"))

from systematic_trader import sec_tournament_rehearsal as engine
from systematic_trader.sec_real_tournament_v2 import build_family_weights


CONFIG = ROOT / "config/sec_fragility_industry_tournament_v1.json"
PANEL_ROOT = ROOT / "data/sec_broad_research_panel_v2"
PROGRAM = ROOT / "config/sec_return_improvement_program_v1.json"
CONTROL_ROOT = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1"
RESIDUAL_PATH = ROOT / "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv"
SECTOR_ROOT = ROOT / "evidence/sec_sector_aware_signal_ensemble_v1"
SECTOR_DAILY_ROOT = ROOT / "evidence/sec_sector_ensemble_daily_risk_scaling_audit_v1"
OUTPUT = ROOT / "evidence/sec_fragility_industry_tournament_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_returns(path: Path, column: str = "net_return") -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    frame.index = pd.to_datetime(frame.index, utc=True)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sort_index()


def statistics(values: pd.Series) -> dict[str, float | int]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {"cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "weeks": 0}
    wealth = (1.0 + clean).cumprod()
    years = len(clean) / 52.0
    volatility = clean.std(ddof=1)
    return {
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(clean.mean() / volatility * np.sqrt(52.0)) if volatility else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "weeks": int(len(clean)),
    }


def apply_exposure(
    returns: pd.Series,
    exposure: float | pd.Series,
    financing_rate: float,
    change_cost_bps: float,
) -> tuple[pd.Series, pd.DataFrame]:
    """Apply financing and exposure-change costs with no use of future returns."""
    desired = (
        pd.Series(float(exposure), index=returns.index)
        if np.isscalar(exposure)
        else pd.Series(exposure, index=returns.index).reindex(returns.index).ffill().fillna(1.0)
    )
    previous = 1.0
    output: list[float] = []
    audit: list[dict[str, object]] = []
    for date, base_return in returns.items():
        current = float(desired.loc[date])
        financing = max(0.0, current - 1.0) * float(financing_rate) / 52.0
        change_cost = abs(current - previous) * float(change_cost_bps) / 10000.0
        net = current * float(base_return) - financing - change_cost
        output.append(net)
        audit.append({
            "Date": date,
            "base_return": float(base_return),
            "exposure": current,
            "financing_cost": financing,
            "exposure_change_cost": change_cost,
            "net_return": net,
        })
        previous = current
    return pd.Series(output, index=returns.index, name="net_return"), pd.DataFrame(audit).set_index("Date")


def build_core_paths(
    panel: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    program: dict,
    endpoint: pd.Timestamp,
    costs: list[int],
    delays: list[int],
) -> dict[tuple[int, int], pd.Series]:
    family_weights, _ = build_family_weights(panel, program)
    residual_weights = family_weights["residual_momentum"]
    output: dict[tuple[int, int], pd.Series] = {}
    for cost in costs:
        control = read_returns(CONTROL_ROOT / f"best_path__base__{cost}bps.csv")
        control = control.reindex(weekly_returns.index).fillna(0.0)
        for delay in [0, *delays]:
            residual = engine.portfolio_path(residual_weights, weekly_returns, cost, delay)[0]
            candidate = 0.8 * control + 0.2 * residual
            output[(cost, delay)] = candidate.loc[:endpoint]
    return output


def calibrate_recent_cagr(path: pd.Series, target_cagr: float) -> pd.Series:
    """Apply a uniform trailing-window haircut to reproduce an audited CAGR stress."""
    output = path.copy()
    recent = output.tail(52)
    current_multiple = float((1.0 + recent).prod())
    target_multiple = 1.0 + float(target_cagr)
    factor = (target_multiple / current_multiple) ** (1.0 / len(recent))
    output.loc[recent.index] = (1.0 + recent) * factor - 1.0
    return output.rename("net_return")


def rebuild_sector_paths(config: dict) -> dict[str, pd.Series]:
    """Load direct cost paths and conservative proxies for archived path-only stresses."""
    result = {
        "base_50": read_returns(SECTOR_ROOT / "selected_path__50bps.csv"),
        "base_100": read_returns(SECTOR_ROOT / "selected_path__100bps.csv"),
        "base_200": read_returns(SECTOR_ROOT / "selected_path__200bps.csv"),
    }
    audit = json.loads((SECTOR_ROOT / "result.json").read_text())
    result["delay_worst"] = calibrate_recent_cagr(result["base_50"], float(audit["worst_delay_recent_cagr"]))
    result["worst_five"] = calibrate_recent_cagr(result["base_50"], float(audit["worst_missing_bundle_recent_cagr"]))
    return result


def sector_weekly_from_daily(endpoint: pd.Timestamp) -> pd.Series:
    daily = read_returns(SECTOR_DAILY_ROOT / "daily_path__1.00x.csv")
    return ((1.0 + daily).resample("W-FRI").prod() - 1.0).loc[:endpoint].rename("net_return")


def fragility_diagnostics(
    weekly_index: pd.DatetimeIndex,
    stock_targets: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    sector_by_cik: dict[str, str],
    source_returns: pd.Series,
    rules: dict[str, float],
) -> pd.DataFrame:
    """Calculate issuer and sector fragility using information strictly before each week."""
    targets = stock_targets.copy()
    targets["rebalance_at"] = pd.to_datetime(targets["rebalance_at"], utc=True)
    rows = []
    for date in weekly_index:
        eligible_events = targets[targets.rebalance_at <= date]
        if eligible_events.empty:
            rows.append({"Date": date, "risk_on": False, "reason": "no_target"})
            continue
        latest = eligible_events.rebalance_at.max()
        active = eligible_events[eligible_events.rebalance_at == latest]
        weights = active.set_index("cik10").intended_weight.astype(float)
        ciks = [cik for cik in weights.index if cik in weekly_returns.columns]
        prior = weekly_returns.loc[weekly_returns.index < date, ciks].tail(int(rules["lookback_weeks"]))
        prior_source = source_returns.loc[source_returns.index < date].tail(int(rules["lookback_weeks"]))
        enough = len(prior_source) >= int(rules["minimum_history_weeks"])
        if not enough or not ciks:
            rows.append({"Date": date, "risk_on": False, "reason": "insufficient_history"})
            continue
        contribution = prior.fillna(0.0).mul(weights.reindex(ciks), axis=1).sum(axis=0)
        positive = contribution.clip(lower=0.0)
        total_positive = float(positive.sum())
        issuer_share = float(positive.max() / total_positive) if total_positive > 0 else 1.0
        positive_breadth = int((positive > 0).sum())
        sector_totals: dict[str, float] = {}
        for cik, value in positive.items():
            sector_name = sector_by_cik.get(str(cik), "unknown")
            sector_totals[sector_name] = sector_totals.get(sector_name, 0.0) + float(value)
        sector_share = max(sector_totals.values(), default=total_positive) / total_positive if total_positive > 0 else 1.0
        annualized_volatility = float(prior_source.std(ddof=1) * np.sqrt(52.0))
        checks = {
            "issuer": issuer_share <= float(rules["maximum_positive_issuer_share"]),
            "sector": sector_share <= float(rules["maximum_positive_sector_share"]),
            "breadth": positive_breadth >= int(rules["minimum_positive_issuer_breadth"]),
            "volatility": annualized_volatility <= float(rules["maximum_annualized_source_volatility"]),
        }
        rows.append({
            "Date": date,
            "risk_on": bool(all(checks.values())),
            "reason": "pass" if all(checks.values()) else "|".join(name for name, passed in checks.items() if not passed),
            "maximum_positive_issuer_share": issuer_share,
            "maximum_positive_sector_share": float(sector_share),
            "positive_issuer_breadth": positive_breadth,
            "annualized_source_volatility": annualized_volatility,
        })
    return pd.DataFrame(rows).set_index("Date")


def causal_beta(source: pd.Series, core: pd.Series, lookback: int = 26, minimum: int = 13) -> pd.Series:
    joined = pd.concat([source.rename("source"), core.rename("core")], axis=1).fillna(0.0)
    covariance = joined.source.rolling(lookback, min_periods=minimum).cov(joined.core)
    variance = joined.core.rolling(lookback, min_periods=minimum).var().replace(0.0, np.nan)
    return (covariance / variance).shift(1).clip(lower=0.0, upper=1.5).fillna(1.0)


def accelerator_return(
    core: pd.Series,
    source: pd.Series,
    alpha_weight: float,
    risk_on: pd.Series,
) -> tuple[pd.Series, pd.DataFrame]:
    joined = pd.concat([core.rename("core"), source.rename("source")], axis=1).fillna(0.0)
    beta = causal_beta(joined.source, joined.core)
    alpha = pd.Series(float(alpha_weight), index=joined.index).where(risk_on.reindex(joined.index).fillna(False), 0.0)
    core_weight = 1.0 - alpha * beta
    result = core_weight * joined.core + alpha * joined.source
    audit = pd.DataFrame({"core_weight": core_weight, "source_weight": alpha, "source_beta": beta, "risk_on": alpha > 0})
    return result.rename("net_return"), audit


def industry_residual_weights(
    panel: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    spec: dict,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build quarterly long-only weights from lagged industry residuals and SEC acceleration."""
    beta_lookback = int(config["industry_beta_lookback_weeks"])
    beta_minimum = int(config["industry_beta_minimum_weeks"])
    fundamental = config["fundamental_score_weights"]
    rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    for decision, block in panel.groupby("decision_at", sort=True):
        execution = pd.Timestamp(block.execution_at.iloc[0])
        eligible = block[
            block.validated_price_available.astype(bool)
            & block.quality_momentum.notna()
            & block.event_score.notna()
            & block.cik10.isin(weekly_returns.columns)
        ].copy()
        history = weekly_returns.loc[weekly_returns.index < execution, eligible.cik10].tail(beta_lookback)
        needed = int(spec["lookback_weeks"]) + int(spec["skip_recent_weeks"])
        if len(history) < max(beta_minimum, needed):
            diagnostics.append({"decision_at": decision, "execution_at": execution, "status": "insufficient_history"})
            continue
        sector_by_cik = eligible.set_index("cik10").sector.to_dict()
        sector_history = pd.DataFrame({
            sector: history[[cik for cik in history.columns if sector_by_cik.get(cik) == sector]].mean(axis=1)
            for sector in sorted(set(sector_by_cik.values()))
        })
        market = history.mean(axis=1)
        market_variance = float(market.var(ddof=1))
        if not np.isfinite(market_variance) or market_variance <= 0:
            diagnostics.append({"decision_at": decision, "execution_at": execution, "status": "zero_market_variance"})
            continue
        betas = sector_history.apply(lambda values: values.cov(market) / market_variance).clip(-1.0, 3.0)
        systematic = pd.DataFrame(
            np.outer(market.to_numpy(float), betas.to_numpy(float)),
            index=market.index,
            columns=betas.index,
        )
        residual = sector_history - systematic
        skip = int(spec["skip_recent_weeks"])
        stop = -skip if skip else None
        signal_window = residual.iloc[-needed:stop]
        momentum = (1.0 + signal_window).prod() - 1.0
        reversal = (1.0 + residual.tail(4)).prod() - 1.0
        sector_score = momentum - float(spec["reversal_penalty"]) * reversal
        chosen_sectors = list(sector_score.sort_values(ascending=False).head(int(spec["top_sectors"])).index)
        eligible["quality_rank"] = eligible.groupby("sector").quality_momentum.rank(pct=True)
        eligible["event_rank"] = eligible.groupby("sector").event_score.rank(pct=True)
        eligible["fundamental_score"] = (
            float(fundamental["quality_momentum"]) * eligible.quality_rank
            + float(fundamental["event_score"]) * eligible.event_rank
        )
        selected = []
        for sector_name in chosen_sectors:
            selected.append(
                eligible[eligible.sector == sector_name]
                .sort_values(["fundamental_score", "cik10"], ascending=[False, True])
                .head(int(spec["names_per_sector"]))
            )
        selected_frame = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
        if selected_frame.empty:
            diagnostics.append({"decision_at": decision, "execution_at": execution, "status": "empty_selection"})
            continue
        weight = 1.0 / len(selected_frame)
        rows.extend({"decision_at": execution, "cik10": str(cik), "weight": weight} for cik in selected_frame.cik10)
        diagnostics.append({
            "decision_at": decision,
            "execution_at": execution,
            "status": "selected",
            "selected_sectors": "|".join(chosen_sectors),
            "selected_issuers": int(len(selected_frame)),
            "maximum_issuer_weight": weight,
            "signal_cutoff": history.index.max(),
        })
    return pd.DataFrame(rows), pd.DataFrame(diagnostics)


def issuer_removal_stress(path: pd.Series, contributions: pd.DataFrame, count: int = 5) -> tuple[pd.Series, list[str]]:
    recent = contributions.reindex(path.index).tail(52).fillna(0.0)
    positive = recent.sum().clip(lower=0.0)
    removed = list(positive.sort_values(ascending=False).head(count).index)
    stressed = path - contributions.reindex(path.index)[removed].fillna(0.0).sum(axis=1)
    return stressed.rename("net_return"), removed


def bootstrap_adjusted(candidate: pd.Series, control: pd.Series, config: dict) -> tuple[float, float]:
    excess = candidate.reindex(control.index).fillna(0.0).tail(52) - control.tail(52)
    raw = min(
        engine.bootstrap_probability(
            excess,
            int(block),
            int(config["bootstrap_draws"]),
            int(config["bootstrap_seed"]),
        )
        for block in config["bootstrap_blocks_weeks"]
    )
    adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw) * int(config["familywise_trials"])))
    return float(raw), float(adjusted)


def common_row(
    name: str,
    family: str,
    path: pd.Series,
    control: pd.Series,
    severe: pd.Series,
    delayed: list[pd.Series],
    worst_five: pd.Series,
    config: dict,
) -> dict[str, object]:
    recent = statistics(path.tail(52))
    full = statistics(path)
    severe_recent = statistics(severe.tail(52))
    worst_delay = min(statistics(values.tail(52))["cagr"] for values in delayed)
    issuer_stress = statistics(worst_five.tail(52))["cagr"]
    rolling_share, rolling_windows = engine.rolling_share(path, control, 26)
    raw, adjusted = bootstrap_adjusted(path, control, config)
    gates = config["promotion_gates"]
    passed = bool(
        recent["cagr"] >= float(gates["minimum_recent_cagr"])
        and recent["sharpe"] >= float(gates["minimum_recent_sharpe"])
        and recent["max_drawdown"] >= float(gates["minimum_recent_drawdown"])
        and severe_recent["cagr"] >= float(gates["minimum_200bps_recent_cagr"])
        and worst_delay >= float(gates["minimum_worst_delay_recent_cagr"])
        and issuer_stress >= float(gates["minimum_worst_five_issuer_recent_cagr"])
        and rolling_share >= float(gates["minimum_rolling_26w_outperformance_share"])
        and adjusted >= float(gates["minimum_familywise_bootstrap_probability"])
    )
    return {
        "candidate": name,
        "family": family,
        "recent_cagr": recent["cagr"],
        "recent_sharpe": recent["sharpe"],
        "recent_drawdown": recent["max_drawdown"],
        "full_cagr": full["cagr"],
        "full_sharpe": full["sharpe"],
        "full_drawdown": full["max_drawdown"],
        "severe_200bps_recent_cagr": severe_recent["cagr"],
        "worst_delay_recent_cagr": worst_delay,
        "worst_five_issuer_recent_cagr": issuer_stress,
        "rolling_26w_outperformance_share": rolling_share,
        "rolling_26w_windows": rolling_windows,
        "raw_bootstrap_probability": raw,
        "familywise_bootstrap_probability": adjusted,
        "all_historical_promotion_gates": passed,
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "result.json"
    if result_path.exists():
        raise RuntimeError("fragility and industry tournament is one-shot")
    endpoint = pd.Timestamp(config["common_endpoint"], tz="UTC")
    panel = pd.read_csv(PANEL_ROOT / "panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel["decision_at"], utc=True)
    panel["execution_at"] = pd.to_datetime(panel["execution_at"], utc=True)
    weekly_returns = pd.read_csv(PANEL_ROOT / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly_returns.index = pd.to_datetime(weekly_returns.index, utc=True)
    weekly_returns = weekly_returns.loc[:endpoint]
    program = json.loads(PROGRAM.read_text())
    costs = [int(config["primary_cost_bps"]), *map(int, config["cost_stress_bps"])]
    delays = list(map(int, config["execution_delay_weeks"]))
    core_paths = build_core_paths(panel, weekly_returns, program, endpoint, costs, delays)
    saved_core = read_returns(RESIDUAL_PATH).loc[:endpoint]
    if not np.allclose(core_paths[(50, 0)].reindex(saved_core.index), saved_core, rtol=0.0, atol=1e-12):
        raise RuntimeError("core path failed exact reproduction")
    core = core_paths[(50, 0)]
    leverage_rows = []
    tournament_rows = []
    common_paths: dict[str, pd.Series] = {}
    incumbent_control, _ = apply_exposure(core, 1.25, 0.08, float(config["leverage_change_cost_bps"]))
    for exposure in config["incumbent_exposures"]:
        for rate in config["financing_rates"]:
            path, _ = apply_exposure(core, float(exposure), float(rate), float(config["leverage_change_cost_bps"]))
            recent = statistics(path.tail(52))
            leverage_rows.append({"family": "incumbent", "exposure": exposure, "financing_rate": rate, **recent})
            common_paths[f"incumbent_{exposure:.2f}x_{rate:.0%}"] = path

    rebuilt_sector = rebuild_sector_paths(config)
    saved_sector = read_returns(SECTOR_ROOT / "selected_path__50bps.csv").loc[:endpoint]
    if not np.allclose(rebuilt_sector["base_50"].reindex(saved_sector.index), saved_sector, rtol=0.0, atol=1e-12):
        raise RuntimeError("sector path failed exact reproduction")
    sector = sector_weekly_from_daily(endpoint).reindex(core.index).fillna(0.0)
    sector_severe = rebuilt_sector["base_200"].reindex(core.index).fillna(0.0)
    sector_delay = rebuilt_sector["delay_worst"].reindex(core.index).fillna(0.0)
    sector_worst_five = rebuilt_sector["worst_five"].reindex(core.index).fillna(0.0)
    for exposure in config["sector_reference_exposures"]:
        for rate in config["financing_rates"]:
            path, _ = apply_exposure(sector, float(exposure), float(rate), float(config["leverage_change_cost_bps"]))
            leverage_rows.append({"family": "sector_reference", "exposure": exposure, "financing_rate": rate, **statistics(path.tail(52))})
            common_paths[f"sector_{exposure:.2f}x_{rate:.0%}"] = path

    targets = pd.read_csv(SECTOR_ROOT / "selected_stock_target_weights.csv", dtype={"cik10": str})
    sector_by_cik = panel.sort_values("decision_at").drop_duplicates("cik10", keep="last").set_index("cik10").sector.to_dict()
    guard_frames = {}
    for guard_name, rules in config["fragility_guards"].items():
        guard_frames[guard_name] = fragility_diagnostics(
            core.index, targets, weekly_returns, sector_by_cik, sector, rules
        )
    pd.concat(
        [frame.assign(guard=name).reset_index() for name, frame in guard_frames.items()],
        ignore_index=True,
    ).to_csv(OUTPUT / "fragility_diagnostics.csv", index=False)

    accelerator_audits = []
    for spec in config["accelerator_variants"]:
        risk_on = guard_frames[spec["guard"]].risk_on
        base, audit = accelerator_return(core, sector, float(spec["alpha_weight"]), risk_on)
        primary, exposure_audit = apply_exposure(base, float(spec["gross_exposure"]), 0.08, float(config["leverage_change_cost_bps"]))
        severe_base, _ = accelerator_return(core_paths[(200, 0)], sector_severe, float(spec["alpha_weight"]), risk_on)
        severe, _ = apply_exposure(severe_base, float(spec["gross_exposure"]), 0.08, float(config["leverage_change_cost_bps"]))
        delayed_paths = []
        for delay in delays:
            delayed_core = core_paths[(50, delay)]
            delayed_base, _ = accelerator_return(delayed_core, sector_delay, float(spec["alpha_weight"]), risk_on)
            delayed_paths.append(apply_exposure(delayed_base, float(spec["gross_exposure"]), 0.08, float(config["leverage_change_cost_bps"]))[0])
        issuer_base, _ = accelerator_return(core, sector_worst_five, float(spec["alpha_weight"]), risk_on)
        issuer_path, _ = apply_exposure(issuer_base, float(spec["gross_exposure"]), 0.08, float(config["leverage_change_cost_bps"]))
        tournament_rows.append(common_row(
            spec["name"], "fragility_aware_accelerator", primary, incumbent_control,
            severe, delayed_paths, issuer_path, config,
        ))
        audit = audit.join(exposure_audit[["exposure", "financing_cost", "exposure_change_cost"]])
        audit.insert(0, "candidate", spec["name"])
        accelerator_audits.append(audit.reset_index())
        common_paths[spec["name"]] = primary
    pd.concat(accelerator_audits, ignore_index=True).to_csv(OUTPUT / "accelerator_exposure_audit.csv", index=False)

    industry_rows = []
    selected_weight_frames: dict[str, pd.DataFrame] = {}
    selected_path_cache: dict[str, tuple[pd.Series, pd.DataFrame]] = {}
    for spec in config["industry_residual_variants"]:
        weights, decision_audit = industry_residual_weights(panel, weekly_returns, spec, config)
        if weights.empty:
            continue
        selected_weight_frames[spec["name"]] = weights
        primary_base, contributions = engine.portfolio_path(weights, weekly_returns, 50)
        selected_path_cache[spec["name"]] = (primary_base.loc[:endpoint], contributions.loc[:endpoint])
        severe_base = engine.portfolio_path(weights, weekly_returns, 200)[0].loc[:endpoint]
        delayed_base = [engine.portfolio_path(weights, weekly_returns, 50, delay)[0].loc[:endpoint] for delay in delays]
        stressed_base, removed = issuer_removal_stress(primary_base.loc[:endpoint], contributions.loc[:endpoint], 5)
        decision_audit.insert(0, "candidate", spec["name"])
        decision_audit.to_csv(OUTPUT / f"industry_decisions__{spec['name']}.csv", index=False)
        for exposure in config["industry_exposures"]:
            name = f"{spec['name']}__{float(exposure):.2f}x"
            primary, _ = apply_exposure(primary_base.loc[:endpoint], float(exposure), float(config["industry_financing_rate"]), float(config["leverage_change_cost_bps"]))
            severe, _ = apply_exposure(severe_base, float(exposure), float(config["industry_financing_rate"]), float(config["leverage_change_cost_bps"]))
            delayed_paths = [apply_exposure(values, float(exposure), float(config["industry_financing_rate"]), float(config["leverage_change_cost_bps"]))[0] for values in delayed_base]
            worst_five, _ = apply_exposure(stressed_base, float(exposure), float(config["industry_financing_rate"]), float(config["leverage_change_cost_bps"]))
            row = common_row(name, "industry_residual_sec_acceleration", primary, incumbent_control, severe, delayed_paths, worst_five, config)
            row["removed_issuers"] = "|".join(removed)
            row["base_variant"] = spec["name"]
            row["exposure"] = float(exposure)
            industry_rows.append(row)
            tournament_rows.append(row)
            common_paths[name] = primary

    industry_screen = pd.DataFrame(industry_rows).sort_values(
        ["all_historical_promotion_gates", "recent_cagr", "recent_sharpe"], ascending=False
    )
    industry_screen.to_csv(OUTPUT / "industry_screening.csv", index=False)
    if not industry_screen.empty:
        best_industry = str(industry_screen.iloc[0].base_variant)
        selected_weight_frames[best_industry].to_csv(OUTPUT / "industry_selected_weights.csv", index=False)
    screening = pd.DataFrame(tournament_rows).sort_values(
        ["all_historical_promotion_gates", "recent_cagr", "recent_sharpe"], ascending=False
    )
    screening.to_csv(OUTPUT / "screening.csv", index=False)
    pd.DataFrame(leverage_rows).to_csv(OUTPUT / "leverage_frontier.csv", index=False)
    pd.DataFrame(common_paths).rename_axis("Date").to_csv(OUTPUT / "common_paths.csv")

    passing = screening[screening.all_historical_promotion_gates]
    selected = str(screening.iloc[0].candidate) if len(screening) else None
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "common_endpoint": config["common_endpoint"],
        "candidate_count": int(len(screening)),
        "accelerator_candidate_count": int(sum(screening.family == "fragility_aware_accelerator")),
        "industry_candidate_count": int(sum(screening.family == "industry_residual_sec_acceleration")),
        "historical_gate_passer_count": int(len(passing)),
        "selected_diagnostic": selected,
        "selected_metrics": screening.iloc[0].to_dict() if len(screening) else {},
        "incumbent_1.25x_8pct": statistics(incumbent_control.tail(52)),
        "fragile_1.35x_daily_reference": json.loads((SECTOR_DAILY_ROOT / "result.json").read_text()),
        "selection_contaminated": True,
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False,
        "required_next_step": "retain only as research candidates and gather untouched forward evidence",
        "frozen_config_sha256": sha256(CONFIG),
        "artifact_sha256": {
            name: sha256(OUTPUT / name)
            for name in [
                "screening.csv",
                "leverage_frontier.csv",
                "fragility_diagnostics.csv",
                "accelerator_exposure_audit.csv",
                "industry_screening.csv",
                "industry_selected_weights.csv",
                "common_paths.csv",
            ]
            if (OUTPUT / name).exists()
        },
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    best_text = "no valid candidate"
    if len(screening):
        top = screening.iloc[0]
        best_text = (
            f"`{top.candidate}` produced {top.recent_cagr:.2%} recent CAGR, "
            f"{top.recent_sharpe:.3f} Sharpe, and {top.recent_drawdown:.2%} drawdown"
        )
    (OUTPUT / "report.md").write_text(
        "# Fragility-aware accelerator and industry-residual tournament v1\n\n"
        f"The frozen tournament compared {len(screening)} post-selection candidates on the common "
        f"endpoint {config['common_endpoint']}. The strongest diagnostic was {best_text}.\n\n"
        f"Complete historical promotion-gate passers: **{len(passing)}**. Even a historical pass would not "
        "authorize replacement because every design was proposed after observing the sample. The current "
        "incumbent remains frozen forward research, and live trading remains disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
