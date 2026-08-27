#!/usr/bin/env python3
"""Test SUE, shareholder yield/net issuance, and intangible-adjusted quality.

Raw SEC Company Facts are reduced to exact period contexts.  Only facts filed
before a decision are visible to that decision.  A full quarter is purged
between selection and the four-decision retrospective holdout.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_daily_ohlcv_alpha_zoo_v1 as ohlcv

CONFIG = ROOT / "config/future_alpha_program_v1.json"
SOURCE_INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/source_inventory.csv"
PANEL = ROOT / "data/sec_broad_research_panel_v2/panel.csv.gz"
WEEKLY = ROOT / "data/sec_broad_research_panel_v2/weekly_returns.csv.gz"
WEEKLY_PRICES = ROOT / "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/point_in_time_fundamental_branches_v1"

CONCEPTS = {
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
    "shares": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "PaymentsOfOrdinaryDividends"],
    "repurchases": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
    "issuance_cash": ["ProceedsFromStockOptionsExercised", "ProceedsFromIssuanceOfCommonStock"],
    "assets": ["Assets"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "research_development": ["ResearchAndDevelopmentExpense"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
}
TAG_TO_METRIC = {tag: metric for metric, tags in CONCEPTS.items() for tag in tags}
FLOW_METRICS = {"eps", "dividends", "repurchases", "issuance_cash", "net_income", "research_development", "sga"}
FEATURES = ["standardized_unexpected_earnings", "net_issuance", "shareholder_yield", "intangible_adjusted_quality"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_file(path: Path, cik10: str) -> list[dict]:
    try:
        with gzip.open(path, "rt") as handle:
            document = json.load(handle)
    except Exception:
        return []
    facts = document.get("facts", {}).get("us-gaap", {})
    rows = []
    for tag, detail in facts.items():
        metric = TAG_TO_METRIC.get(tag)
        if metric is None:
            continue
        for unit, values in detail.get("units", {}).items():
            if metric == "shares" and unit != "shares":
                continue
            if metric == "eps" and unit not in {"USD/shares", "USD / shares"}:
                continue
            if metric not in {"shares", "eps"} and unit != "USD":
                continue
            for item in values:
                if item.get("form") not in {"10-Q", "10-K", "20-F", "40-F"}:
                    continue
                try:
                    start = pd.Timestamp(item["start"]) if item.get("start") else pd.NaT
                    end = pd.Timestamp(item["end"]) if item.get("end") else pd.NaT
                    filed = pd.Timestamp(item["filed"], tz="UTC") if item.get("filed") else pd.NaT
                    value = float(item.get("val"))
                except (TypeError, ValueError, OverflowError):
                    continue
                if pd.isna(end) or pd.isna(filed) or pd.isna(value):
                    continue
                rows.append({"cik10": cik10, "metric": metric, "tag": tag, "unit": unit, "value": float(value),
                             "start": start, "end": end, "filed": filed, "fy": item.get("fy"), "fp": item.get("fp"),
                             "duration_days": (end - start).days if pd.notna(start) else np.nan})
    return rows


def latest_contexts(facts: pd.DataFrame, decision: pd.Timestamp) -> pd.DataFrame:
    eligible = facts[facts.filed < decision].copy()
    if eligible.empty:
        return eligible
    return eligible.sort_values(["filed", "tag"]).drop_duplicates(["metric", "unit", "start", "end"], keep="last")


def latest_metric(frame: pd.DataFrame, metric: str, kind: str) -> pd.Series | None:
    data = frame[frame.metric == metric].copy()
    if kind == "quarter": data = data[data.duration_days.between(60, 120)]
    elif kind == "annual": data = data[data.duration_days.between(300, 430)]
    elif kind == "instant": data = data[data.start.isna()]
    if data.empty:
        return None
    return data.sort_values(["end", "filed", "tag"]).iloc[-1]


def sue(frame: pd.DataFrame) -> float:
    data = frame[(frame.metric == "eps") & frame.duration_days.between(60, 120)].copy()
    if data.empty:
        return np.nan
    data = data.sort_values(["end", "filed", "tag"]).drop_duplicates("end", keep="last")
    values = []
    for current in data.itertuples():
        prior = data[(data.end >= current.end - pd.Timedelta(days=400)) & (data.end <= current.end - pd.Timedelta(days=300))]
        if not prior.empty:
            values.append((current.end, float(current.value - prior.iloc[-1].value)))
    if len(values) < 5:
        return np.nan
    changes = np.asarray([value for _, value in values], dtype=float)
    scale = np.std(changes[:-1][-8:], ddof=1)
    return float(changes[-1] / scale) if np.isfinite(scale) and scale > 1e-12 else np.nan


def issuance_and_yield(frame: pd.DataFrame, price: float) -> tuple[float, float]:
    shares = frame[(frame.metric == "shares") & frame.start.isna()].sort_values(["end", "filed", "tag"]).drop_duplicates("end", keep="last")
    if shares.empty:
        return np.nan, np.nan
    latest = shares.iloc[-1]
    prior = shares[(shares.end >= latest.end - pd.Timedelta(days=430)) & (shares.end <= latest.end - pd.Timedelta(days=300))]
    net_issuance = -(float(latest.value) / float(prior.iloc[-1].value) - 1) if not prior.empty and prior.iloc[-1].value else np.nan
    market_cap = float(latest.value) * float(price) if np.isfinite(price) and price > 0 else np.nan
    payouts = 0.0; found = False
    for metric, sign in (("dividends", 1), ("repurchases", 1), ("issuance_cash", -1)):
        item = latest_metric(frame, metric, "annual")
        if item is not None:
            payouts += sign * abs(float(item.value)); found = True
    shareholder_yield = payouts / market_cap if found and np.isfinite(market_cap) and market_cap > 0 else np.nan
    return net_issuance, shareholder_yield


def intangible_quality(frame: pd.DataFrame) -> float:
    assets = latest_metric(frame, "assets", "instant")
    income = latest_metric(frame, "net_income", "annual")
    if assets is None or income is None or assets.value <= 0:
        return np.nan
    expenses = []
    for metric, fraction in (("research_development", 1.0), ("sga", 0.30)):
        data = frame[(frame.metric == metric) & frame.duration_days.between(300, 430)].copy()
        data = data.sort_values(["end", "filed", "tag"]).drop_duplicates("end", keep="last").tail(5)
        for age, row in enumerate(reversed(list(data.itertuples()))):
            expenses.append((float(row.value) * fraction, age))
    if not expenses:
        return np.nan
    capital = sum(value * max(0, 5 - age) / 5 for value, age in expenses)
    current = sum(value for value, age in expenses if age == 0)
    amortization = capital / 5
    return float((float(income.value) + current - amortization) / (float(assets.value) + capital))


def main() -> int:
    panel = pd.read_csv(PANEL, dtype={"cik10": str})
    for column in ["decision_at", "execution_at"]:
        panel[column] = pd.to_datetime(panel[column], utc=True)
    decisions = sorted(panel.decision_at.unique())
    source = pd.read_csv(SOURCE_INVENTORY, dtype={"cik10": str})
    source = source[source.kind == "companyfacts"].drop_duplicates("cik10", keep="last")
    wanted = set(panel.cik10)
    raw_rows = []
    for index, item in enumerate(source[source.cik10.isin(wanted)].itertuples(), 1):
        path = Path(item.path)
        if path.exists() and sha256(path) == item.sha256:
            raw_rows.extend(extract_file(path, str(item.cik10)))
        if index % 500 == 0:
            print(f"company facts {index}/{len(source)}", flush=True)
    raw = pd.DataFrame(raw_rows)
    feature_rows = []
    weekly_prices = pd.read_csv(WEEKLY_PRICES, index_col=0)
    weekly_prices.index = pd.to_datetime(weekly_prices.index, utc=True)
    price_lookup = {}
    for decision in decisions:
        prior = weekly_prices.loc[weekly_prices.index < pd.Timestamp(decision)]
        if not prior.empty:
            price_lookup[pd.Timestamp(decision)] = prior.iloc[-1]
    grouped = raw.groupby("cik10")
    for company_index, (cik10, company) in enumerate(grouped, 1):
        for decision in decisions:
            frame = latest_contexts(company, pd.Timestamp(decision))
            decision_prices = price_lookup.get(pd.Timestamp(decision), pd.Series(dtype=float))
            issuance, shareholder = issuance_and_yield(frame, float(decision_prices.get(cik10, np.nan)))
            feature_rows.append({"decision_at": decision, "cik10": cik10,
                                 "standardized_unexpected_earnings": sue(frame), "net_issuance": issuance,
                                 "shareholder_yield": shareholder, "intangible_adjusted_quality": intangible_quality(frame)})
        if company_index % 500 == 0:
            print(f"point-in-time snapshots {company_index}/{raw.cik10.nunique()}", flush=True)
    feature_panel = pd.DataFrame(feature_rows)
    merged = panel[["decision_at", "execution_at", "cik10", "sector", "future_sector_relative_return"]].merge(
        feature_panel, on=["decision_at", "cik10"], how="left", validate="one_to_one")
    selection, purge, holdout = decisions[:9], decisions[9], decisions[10:]
    selection_set, holdout_set = set(selection), set(holdout)
    results, ic_rows = {}, []
    for feature in FEATURES:
        values = []
        for decision, block in merged.groupby("decision_at"):
            neutral = block[feature] - block.groupby("sector")[feature].transform("median")
            ic = ohlcv.rank_ic(block.assign(**{feature: neutral}), feature)
            values.append((decision, ic)); ic_rows.append({"decision_at": decision, "feature": feature, "rank_ic": ic})
        selected = [ic for date, ic in values if date in selection_set]
        held = [ic for date, ic in values if date in holdout_set]
        direction = 1 if np.nanmean(selected) >= 0 else -1
        results[feature] = {"direction": direction, "selection_mean_ic": float(direction * np.nanmean(selected)),
                            "selection_positive_share": float(np.nanmean(np.asarray(selected) * direction > 0)),
                            "selection_sign_flip_p": ohlcv.sign_flip_p(selected),
                            "holdout_mean_ic": float(direction * np.nanmean(held)),
                            "holdout_positive_share": float(np.nanmean(np.asarray(held) * direction > 0)),
                            "nonmissing_share": float(merged[feature].notna().mean())}
    discoveries = ohlcv.bh_flags({name: value["selection_sign_flip_p"] for name, value in results.items()})
    for name in results: results[name]["selection_bh_10pct"] = name in discoveries

    eligible = [name for name in FEATURES if results[name]["nonmissing_share"] >= 0.20]
    merged["composite"] = 0.0; count = pd.Series(0, index=merged.index)
    for feature in eligible:
        score = merged.groupby("decision_at")[feature].rank(pct=True) * results[feature]["direction"]
        merged["composite"] += score.fillna(0); count += score.notna().astype(int)
    merged["composite"] /= count.replace(0, np.nan)
    weights = {}
    for decision, block in merged.groupby("decision_at"):
        chosen = ohlcv.choose_names(block, block.composite, 20, 5)
        execution = pd.Timestamp(block.execution_at.iloc[0])
        weights[execution] = {cik: 1 / len(chosen) for cik in chosen} if chosen else {}
    weekly = pd.read_csv(WEEKLY, index_col=0, parse_dates=True); weekly.index = pd.to_datetime(weekly.index, utc=True)
    path_metrics, paths = {}, {}
    first_holdout = pd.Timestamp(holdout[0]) + pd.Timedelta(weeks=1)
    for cost in [10, 25, 50]:
        path = ohlcv.portfolio_path(weights, weekly, cost); paths[str(cost)] = path
        path_metrics[str(cost)] = {"full": ohlcv.metrics(path[path.index >= pd.Timestamp(selection[0]) + pd.Timedelta(weeks=1)]),
                                   "retrospective_holdout": ohlcv.metrics(path[path.index >= first_holdout])}

    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw.to_csv(OUTPUT / "relevant_companyfacts.csv.gz", index=False, compression="gzip")
    feature_panel.to_csv(OUTPUT / "features.csv.gz", index=False, compression="gzip")
    pd.DataFrame(ic_rows).to_csv(OUTPUT / "rank_ic_by_decision.csv", index=False)
    pd.DataFrame(paths).to_csv(OUTPUT / "weekly_paths.csv")
    pd.DataFrame([{"execution_at": date, "cik10": cik, "weight": weight} for date, row in weights.items() for cik, weight in row.items()]).to_csv(OUTPUT / "holdings.csv", index=False)
    result = {"experiment": "point_in_time_fundamental_branches_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_inventory_sha256": sha256(SOURCE_INVENTORY), "raw_fact_rows": len(raw), "feature_rows": len(feature_panel),
              "selection_decisions": [str(x) for x in selection], "purged_decision": str(purge), "retrospective_holdout_decisions": [str(x) for x in holdout],
              "feature_results": results, "bh_discoveries": sorted(discoveries), "composite_features": eligible,
              "portfolio_metrics": path_metrics, "status": "retrospective_research_complete_no_promotion",
              "strategy_promotion_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Point-in-time fundamental branches v1\n\n"
        "SUE, net issuance/shareholder yield, and intangible-adjusted quality were reconstructed from exact SEC period contexts. "
        "Only facts filed before each decision were visible. One quarter separates selection from the four-decision retrospective holdout. "
        "No result in this directory can alter the September 4 forward registry or promote a strategy.\n")
    print(json.dumps({"raw_fact_rows": len(raw), "feature_results": results, "bh_discoveries": sorted(discoveries), "portfolio_metrics": path_metrics, "live_trading_enabled": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
