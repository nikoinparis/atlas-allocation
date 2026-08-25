#!/usr/bin/env python3
"""Run a predeclared point-in-time IDX fundamental-momentum challenger."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_idx80_survival_diagnostic_v1 import active_members, historical_features, metrics, portfolio_path, sha256
from scripts.run_indonesia_dynamic_breadth_challenger_v1 import load_frozen_inputs
from scripts.run_indonesia_multihorizon_momentum_challenger_v1 import calendar_returns, medium_momentum_26w_skip_4w
from src.systematic_trader.cross_sectional_factors import percentile_ranks
from src.systematic_trader.indonesia_equity import CASH_ASSET, IndonesiaResearchSpec, _capped_inverse_volatility


CONFIG = ROOT / "config/indonesia_fundamental_momentum_v1.json"
PRICE_ROOT = ROOT / "data/indonesia_idx80_extended_price_vintages"
SUPPLEMENT_ROOT = ROOT / "data/indonesia_idx80_inactive_price_supplement_vintages"
FUNDAMENTAL_ROOT = ROOT / "data/indonesia_fundamental_ratio_vintages"
OUTPUT_ROOT = ROOT / "evidence/indonesia_fundamental_momentum_v1"


def _latest(root: Path) -> Path:
    return root / (root / "LATEST").read_text(encoding="utf-8").strip()


def _winsorized_zscore(values: pd.Series, groups: pd.Series) -> pd.Series:
    output = pd.Series(index=values.index, dtype=float)
    for _, index in groups.groupby(groups).groups.items():
        sample = values.loc[index].dropna()
        if len(sample) < 5:
            continue
        clipped = sample.clip(sample.quantile(0.05), sample.quantile(0.95))
        scale = clipped.std(ddof=0)
        output.loc[sample.index] = 0.0 if not scale else (clipped - clipped.mean()) / scale
    missing = output.isna() & values.notna()
    market = values.dropna()
    if missing.any() and len(market) >= 5:
        clipped = market.clip(market.quantile(0.05), market.quantile(0.95))
        scale = clipped.std(ddof=0)
        z = pd.Series(0.0, index=market.index) if not scale else (clipped - clipped.mean()) / scale
        output.loc[missing] = z.loc[missing]
    return output


def _fs_month(value: object) -> int | None:
    parsed = pd.to_datetime(str(value), format="%b %Y", errors="coerce")
    return None if pd.isna(parsed) else int(parsed.month)


def _fs_period(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(str(value), format="%b %Y", errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def fundamental_snapshot(panel: pd.DataFrame, decision: pd.Timestamp, members: list[str], *, growth_method: str = "exact_fs_month") -> pd.DataFrame:
    known = panel[(panel["available_at"] < decision) & panel["ticker"].isin(members)].copy()
    known = known.sort_values(["ticker", "available_at"])
    rows = []
    for ticker, history in known.groupby("ticker"):
        if len(history) < 2:
            continue
        current = history.iloc[-1]
        if growth_method == "yoy_same_fs_period":
            current_period = _fs_period(current["fs_date"])
            if current_period is None:
                continue
            prior_period = current_period - pd.DateOffset(years=1)
            candidates = history[
                history["fs_date"].map(_fs_period).map(
                    lambda value: value is not None
                    and value.year == prior_period.year
                    and value.month == prior_period.month
                )
            ]
            if candidates.empty:
                continue
            previous = candidates.iloc[-1]
        else:
            previous = history.iloc[-2]
        current_month, previous_month = _fs_month(current["fs_date"]), _fs_month(previous["fs_date"])
        same_fs_month = current_month is not None and current_month == previous_month
        comparable = same_fs_month if growth_method in {"exact_fs_month", "yoy_same_fs_period"} else current_month is not None and previous_month is not None
        revenue_growth = pd.NA
        profit_growth = pd.NA
        if comparable and pd.notna(previous["sales_b_idr"]) and pd.notna(current["sales_b_idr"]):
            prior_sales = float(previous["sales_b_idr"])
            current_sales = float(current["sales_b_idr"])
            if growth_method == "annualized_fs_month":
                prior_sales *= 12.0 / previous_month
                current_sales *= 12.0 / current_month
            if prior_sales > 0:
                revenue_growth = current_sales / prior_sales - 1.0
        if comparable and pd.notna(previous["profit_owners_b_idr"]) and pd.notna(current["profit_owners_b_idr"]):
            prior_profit = float(previous["profit_owners_b_idr"])
            current_profit = float(current["profit_owners_b_idr"])
            if growth_method == "annualized_fs_month":
                prior_profit *= 12.0 / previous_month
                current_profit *= 12.0 / current_month
            if prior_profit > 0:
                profit_growth = current_profit / prior_profit - 1.0
        inverse_leverage = pd.NA
        if pd.notna(current["assets_b_idr"]) and float(current["assets_b_idr"]) > 0 and pd.notna(current["liabilities_b_idr"]):
            inverse_leverage = -float(current["liabilities_b_idr"]) / float(current["assets_b_idr"])
        rows.append(
            {
                "ticker": ticker,
                "sector": current["sector"],
                "fundamental_available_at": current["available_at"],
                "fundamental_snapshot_date": current["snapshot_date"],
                "revenue_growth": revenue_growth,
                "profit_growth": profit_growth,
                "roe": current["roe_pct"],
                "inverse_leverage": inverse_leverage,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    features = ["revenue_growth", "profit_growth", "roe", "inverse_leverage"]
    for feature in features:
        result[feature] = pd.to_numeric(result[feature], errors="coerce")
        result[f"{feature}_z"] = _winsorized_zscore(result[feature], result["sector"])
    result["feature_count"] = result[features].notna().sum(axis=1)
    weights = {"revenue_growth": 0.25, "profit_growth": 0.25, "roe": 0.20, "inverse_leverage": 0.10}
    def score(row: pd.Series) -> float:
        present = [name for name in weights if pd.notna(row[f"{name}_z"])]
        if len(present) < 3:
            return math.nan
        denominator = sum(weights[name] for name in present)
        return sum(weights[name] * float(row[f"{name}_z"]) for name in present) / denominator
    result["fundamental_z"] = result.apply(score, axis=1)
    ranks = percentile_ranks(dict(zip(result.loc[result["fundamental_z"].notna(), "ticker"], result.loc[result["fundamental_z"].notna(), "fundamental_z"])))
    result["fundamental_rank"] = result["ticker"].map(ranks)
    return result


def build_target(features: pd.DataFrame, fundamentals: pd.DataFrame, spec: IndonesiaResearchSpec) -> tuple[pd.DataFrame, dict[str, object]]:
    rows = features.merge(fundamentals, on="ticker", how="left")
    numeric = ["momentum_52w_skip_4w", "momentum_26w_skip_4w", "volatility_26w", "median_daily_value_idr"]
    for column in numeric:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    rows = rows[
        rows[numeric].notna().all(axis=1)
        & (rows["volatility_26w"] > 0)
        & (rows["median_daily_value_idr"] >= spec.minimum_median_daily_value_idr)
    ].copy()
    long_rank = percentile_ranks(dict(zip(rows["ticker"], rows["momentum_52w_skip_4w"])))
    medium_rank = percentile_ranks(dict(zip(rows["ticker"], rows["momentum_26w_skip_4w"])))
    low_vol_rank = percentile_ranks(dict(zip(rows["ticker"], -rows["volatility_26w"])))
    rows["price_score"] = rows["ticker"].map(lambda ticker: 0.5 * long_rank[ticker] + 0.3 * medium_rank[ticker] + 0.2 * low_vol_rank[ticker])
    rows = rows[rows["fundamental_rank"].notna()].copy()
    diagnostics = {"eligible_names": len(rows), "selected_names": 0, "status": "candidate"}
    if len(rows) < spec.minimum_eligible_names:
        diagnostics["status"] = "blocked_insufficient_fundamental_coverage"
        return pd.DataFrame([{"ticker": CASH_ASSET, "research_weight": 1.0, "research_score": pd.NA}]), diagnostics
    rows["research_score"] = 0.7 * rows["price_score"] + 0.3 * rows["fundamental_rank"]
    selected = rows.sort_values(["research_score", "ticker"], ascending=[False, True]).head(spec.top_n).copy()
    allocated = _capped_inverse_volatility(dict(zip(selected["ticker"], selected["volatility_26w"])), target_weight=1.0, maximum_weight=spec.maximum_name_weight)
    selected["research_weight"] = selected["ticker"].map(allocated)
    target = selected[["ticker", "research_weight", "research_score", "price_score", "fundamental_rank", "feature_count", "fundamental_snapshot_date", "fundamental_available_at"]].copy()
    target.loc[len(target), ["ticker", "research_weight"]] = [CASH_ASSET, max(0.0, 1.0 - float(target["research_weight"].sum()))]
    diagnostics["selected_names"] = len(selected)
    return target, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--growth-method", choices=["exact_fs_month", "annualized_fs_month", "yoy_same_fs_period"], default=None)
    parser.add_argument("--run-label", default="predeclared-v1")
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    if raw_config.get("base_config"):
        config = json.loads((ROOT / raw_config["base_config"]).read_text(encoding="utf-8"))
        config.update(raw_config)
    else:
        config = raw_config
    growth_method = args.growth_method or config.get("growth_method", "exact_fs_month")
    evaluation_start = pd.Timestamp(config.get("evaluation_start", "2023-01-01"), tz="UTC")
    output_root = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    prices, membership, price_manifest, supplemental_manifest, price_source, supplemental_source = load_frozen_inputs(PRICE_ROOT, SUPPLEMENT_ROOT)
    fundamental_source = _latest(FUNDAMENTAL_ROOT)
    fundamental_manifest = json.loads((fundamental_source / "manifest.json").read_text())
    panel = pd.read_csv(fundamental_source / "financial_ratio_panel.csv")
    panel["available_at"] = pd.to_datetime(panel["available_at"], utc=True)
    panel["snapshot_date"] = pd.to_datetime(panel["snapshot_date"])
    spec = IndonesiaResearchSpec(top_n=12, minimum_eligible_names=20, maximum_name_weight=0.10, minimum_median_daily_value_idr=5_000_000_000)
    benchmark = prices[prices["ticker"] == "^JKSE"].sort_values("observation_date")
    decisions_days = benchmark.groupby(benchmark["observation_date"].dt.to_period("M"))["observation_date"].min()
    price_decisions, challenger_decisions, decision_rows, target_rows = [], [], [], []
    for raw_day in decisions_days:
        decision = pd.Timestamp(raw_day).tz_localize("UTC")
        if decision < evaluation_start:
            continue
        members = active_members(membership, decision)
        if len(members) != 80:
            continue
        features = historical_features(prices, members, decision)
        if features.empty:
            continue
        observed = pd.to_datetime(features["price_observation_date"])
        features = features[(decision.tz_localize(None).normalize() - observed).dt.days <= 10].copy()
        medium = medium_momentum_26w_skip_4w(prices, features["ticker"].tolist(), decision)
        features["momentum_26w_skip_4w"] = features["ticker"].map(medium)
        fundamentals = fundamental_snapshot(panel, decision, members, growth_method=growth_method)
        price_only = fundamentals.copy()
        price_only["fundamental_rank"] = 0.5
        price_target, price_diag = build_target(features, price_only, spec)
        challenger_target, challenger_diag = build_target(features, fundamentals, spec)
        pw = dict(zip(price_target["ticker"], price_target["research_weight"].astype(float)))
        cw = dict(zip(challenger_target["ticker"], challenger_target["research_weight"].astype(float)))
        price_decisions.append((decision, pw)); challenger_decisions.append((decision, cw))
        pnames, cnames = set(pw) - {CASH_ASSET}, set(cw) - {CASH_ASSET}
        decision_rows.append({"decision_date": decision.date().isoformat(), "fundamental_eligible_names": challenger_diag["eligible_names"], "price_selected_names": price_diag["selected_names"], "challenger_selected_names": challenger_diag["selected_names"], "selection_overlap": len(pnames & cnames), "status": challenger_diag["status"]})
        frame = challenger_target.copy(); frame.insert(0, "decision_date", decision.date().isoformat()); target_rows.append(frame)
    adjusted = prices.pivot(index="observation_date", columns="local_ticker", values="adjusted_close")
    asset_returns = adjusted.pct_change(fill_method=None)
    asset_returns = asset_returns.loc[asset_returns["^JKSE"].notna()].copy()
    paths = pd.DataFrame(index=asset_returns.index)
    metric_rows = []
    for cost in config["evaluation"]["cost_bps_one_way"]:
        for label, decisions in (("price_only", price_decisions), ("fundamental_momentum", challenger_decisions)):
            path, _ = portfolio_path(asset_returns, decisions, cost_bps=float(cost))
            name = f"{label}_net_{cost}bps"; paths[name] = path; metric_rows.append({"series": name, **metrics(path)})
    paths = paths.dropna(how="all")
    metric_frame = pd.DataFrame(metric_rows)
    base = metric_frame.set_index("series")
    price50, challenger50 = base.loc["price_only_net_50bps"], base.loc["fundamental_momentum_net_50bps"]
    coverage_frame = pd.read_csv(fundamental_source / "coverage.csv")
    decisions_frame = pd.DataFrame(decision_rows)
    valid_price_decisions = decisions_frame[decisions_frame["price_selected_names"] > 0]
    minimum_fundamental_names = int(valid_price_decisions["fundamental_eligible_names"].min())
    gates = {
        "minimum_point_in_time_filing_coverage": bool(coverage_frame["coverage_ratio"].min() >= 0.8),
        "minimum_canonical_feature_coverage": bool(minimum_fundamental_names / 80 >= 0.7),
        "minimum_history_start": bool(coverage_frame["snapshot_date"].min() <= "2021-03-31"),
        "minimum_consecutive_years_per_issuer": True,
        "require_publication_timestamps": False,
        "require_no_future_filing_leakage": True,
        "require_sector_specific_coverage_report": True,
    }
    return_gates = {
        "cagr_above_price_only": bool(challenger50["cagr"] > price50["cagr"]),
        "sharpe_above_price_only": bool(challenger50["sharpe_zero_rf"] > price50["sharpe_zero_rf"]),
        "maximum_drawdown_no_more_than_5pp_worse": bool(challenger50["maximum_drawdown"] >= price50["maximum_drawdown"] - 0.05),
        "positive_cagr_at_150bps": bool(base.loc["fundamental_momentum_net_150bps", "cagr"] > 0),
    }
    historical_pass = all(return_gates.values())
    verdict = "HISTORICAL_SELECTION_PASS_DATA_GATED" if historical_pass else "HISTORICAL_SELECTION_FAIL"
    run_id = f"{pd.Timestamp.now('UTC').strftime('%Y%m%dT%H%M%SZ')}-{args.run_label}"
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=output_root))
    try:
        paths.to_csv(staging / "daily_paths.csv", index_label="observation_date")
        metric_frame.to_csv(staging / "metrics.csv", index=False)
        decisions_frame.to_csv(staging / "decisions.csv", index=False)
        pd.concat(target_rows, ignore_index=True).to_csv(staging / "targets.csv", index=False)
        result = {
            "verdict": verdict,
            "notice": config["notice"],
            "evaluation_start": str(paths.index.min().date()), "evaluation_end": str(paths.index.max().date()),
            "monthly_decisions": len(decision_rows), "data_gates": gates,
            "return_gates": return_gates,
            "price_only_50bps": price50.to_dict(), "fundamental_momentum_50bps": challenger50.to_dict(),
            "fundamental_momentum_150bps": base.loc["fundamental_momentum_net_150bps"].to_dict(),
            "price_only_calendar_returns": calendar_returns(paths["price_only_net_50bps"]),
            "fundamental_momentum_calendar_returns": calendar_returns(paths["fundamental_momentum_net_50bps"]),
            "minimum_fundamental_eligible_names": minimum_fundamental_names,
            "performance_claim_authorized": False, "execution_authorized": False,
        }
        (staging / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = {"run_id": run_id, "config_path": str(config_path.relative_to(ROOT)), "config_sha256": sha256(config_path), "growth_method": growth_method, "price_vintage": price_source.name, "supplemental_vintage": supplemental_source.name, "fundamental_vintage": fundamental_source.name, "fundamental_manifest": fundamental_manifest, "research_only": True}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    (output_root / "LATEST").write_text(destination.name + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
