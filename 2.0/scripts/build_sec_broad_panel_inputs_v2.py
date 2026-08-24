#!/usr/bin/env python3
"""Build the hash-verified causal inputs for the sealed broad SEC tournament."""

from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_point_in_time import flatten_companyfacts, flatten_submissions, quarterly_factor_inputs
from systematic_trader.sec_return_improvement import residual_momentum_scores, sector_neutral_quality_scores, trend_quality_scores

GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_v2/recent_membership_readiness.csv"
TIINGO_AUDIT = ROOT / "evidence/sec_broad_tiingo_audit_v2/candidate_audit.csv"
TERMINALS = ROOT / "evidence/sec_broad_terminal_membership_v2/sec_terminal_membership.csv"
FACTS = ROOT / "data/sec_recent_companyfacts_cache_v1"
SUBMISSIONS = ROOT / "data/sec_broad_identity_cache_v2"
PILOT = ROOT / "config/sec_fundamental_pilot_v1.json"
PROGRAM = ROOT / "config/sec_return_improvement_program_v1.json"
OUTPUT = ROOT / "data/sec_broad_panel_inputs_v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_dated_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame else "date" if "date" in frame else str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=[date_column]).sort_values(date_column).set_index(date_column)


def next_week_returns(prices: pd.DataFrame) -> pd.DataFrame:
    ordinary = prices.apply(pd.to_numeric, errors="coerce").pct_change(fill_method=None)
    result = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns, dtype=float)
    if len(prices) > 1:
        result.iloc[:-1] = ordinary.iloc[1:].to_numpy()
    return result


def net_portfolio_returns(weights: pd.DataFrame, forward_returns: pd.DataFrame, cost_bps: float) -> pd.Series:
    aligned = forward_returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    gross = (weights * aligned).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    return gross - turnover.fillna(0.0) * float(cost_bps) / 10000.0


def project_path(value: object) -> Path:
    path = Path(str(value))
    for prefix in ("/project/", "/workspace/2.0/"):
        if str(path).startswith(prefix):
            return ROOT / path.relative_to(prefix)
    return path


def price_sources() -> dict[str, tuple[str, Path, str | None]]:
    """Return one identity-keyed source per CIK, with newer audited sources winning."""
    sources: dict[str, tuple[str, Path, str | None]] = {}
    roots = [
        ROOT / "data/yahoo_recent_current_sec_price_vintages",
        ROOT / "data/sec_broad_current_data_vintages",
        ROOT / "data/sec_broad_recovered_data_vintages",
        ROOT / "data/sec_broad_multi_symbol_data_vintages",
    ]
    for root in roots:
        for result_path in sorted(root.glob("*/price_results.csv")):
            frame = pd.read_csv(result_path, dtype={"cik10": str})
            valid = frame.get("history_overlaps_eligible_interval", frame.get("status", "")).astype(str).str.lower().isin({"true", "ok"})
            for row in frame[valid].to_dict("records"):
                history = row.get("history_file")
                if history:
                    sources[str(row["cik10"]).zfill(10)] = (
                        "yahoo_adjusted",
                        result_path.parent / str(history),
                        str(row.get("compressed_sha256") or "") or None,
                    )
    # Reuse the earlier recovered-identity vintage when it is not superseded.
    recovered_result = ROOT / "evidence/sec_recovered_price_probe_v1/result.json"
    recovered_audit = ROOT / "evidence/sec_recovered_price_probe_v1/recovered_symbol_price_audit.csv"
    if recovered_result.exists() and recovered_audit.exists():
        root = project_path(json.loads(recovered_result.read_text())["price_vintage"])
        frame = pd.read_csv(recovered_audit, dtype={"cik10": str})
        for row in frame[frame.history_overlaps_eligible_interval.astype(bool)].to_dict("records"):
            path = root / str(row["history_file"])
            sources.setdefault(str(row["cik10"]).zfill(10), ("yahoo_adjusted", path, None))
    legacy_audit = ROOT / "evidence/tiingo_delisted_authenticated_probe_v1/candidate_audit.csv"
    if legacy_audit.exists():
        frame = pd.read_csv(legacy_audit, dtype={"cik10": str})
        legacy_valid = {"validated_history_through_last_decision", "validated_early_delisting_needs_terminal_audit"}
        for row in frame[frame.audit_status.isin(legacy_valid)].to_dict("records"):
            sources[str(row["cik10"]).zfill(10)] = (
                "tiingo_adjusted", project_path(row["price_file"]), None
            )
    audit = pd.read_csv(TIINGO_AUDIT, dtype={"cik10": str})
    valid = {"validated_history_through_last_decision", "validated_sec_confirmed_early_delisting"}
    for row in audit[audit.audit_status.isin(valid)].to_dict("records"):
        sources[str(row["cik10"]).zfill(10)] = ("tiingo_adjusted", project_path(row["price_file"]), None)
    return sources


def read_weekly(task: tuple[str, str, Path, str | None, pd.DatetimeIndex, pd.Timestamp | None]) -> tuple[str, pd.Series, dict]:
    cik10, source, path, expected_hash, index, terminal = task
    actual_hash = sha256(path)
    if expected_hash and actual_hash != expected_hash:
        raise RuntimeError(f"price source hash mismatch for {cik10}")
    frame = pd.read_csv(path, compression="gzip")
    if source.startswith("yahoo"):
        dates = pd.to_datetime(frame["Date"], utc=True, errors="coerce").dt.tz_localize(None)
        values = pd.to_numeric(frame["Adj Close"], errors="coerce")
    else:
        dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
        values = pd.to_numeric(frame["adjClose"], errors="coerce")
    daily = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
    daily = daily[~daily.index.duplicated(keep="last")]
    weekly = daily.resample("W-FRI").last().reindex(index)
    if terminal is not None and weekly.notna().any():
        last = weekly.last_valid_index()
        if last is not None:
            weekly.loc[last:] = weekly.loc[last:].ffill()
    inventory = {"kind": "price", "cik10": cik10, "path": str(path), "sha256": actual_hash, "source": source}
    return cik10, weekly, inventory


def quality_one(task: tuple[str, list[pd.Timestamp], dict]) -> tuple[pd.DataFrame, list[dict]]:
    cik10, decisions, pilot = task
    fact_path = FACTS / f"companyfacts_{cik10}.gz"
    submission_path = SUBMISSIONS / f"submissions_{cik10}.gz"
    if not fact_path.exists():
        return pd.DataFrame(), []
    fact_payload = json.loads(gzip.decompress(fact_path.read_bytes()))
    if submission_path.exists():
        submission_payload = json.loads(gzip.decompress(submission_path.read_bytes()))
        filings = flatten_submissions(submission_payload)
    else:
        filings = pd.DataFrame(columns=["accession", "available_at"])
    facts = flatten_companyfacts(fact_payload, filings, pilot["canonical_metrics"], pilot["accepted_forms"])
    raw = quarterly_factor_inputs(facts, decisions, {cik10: cik10})
    if raw.empty:
        return raw, [{"kind": "companyfacts", "cik10": cik10, "path": str(fact_path), "sha256": sha256(fact_path), "source": "sec_companyfacts"}]
    def num(name: str) -> pd.Series:
        values = raw[name] if name in raw else pd.Series(np.nan, index=raw.index)
        return pd.to_numeric(values, errors="coerce")

    out = pd.DataFrame({"decision_at": pd.to_datetime(raw.decision_time, utc=True), "cik10": cik10})
    out["revenue_growth"] = num("revenue__yoy_growth")
    out["earnings_growth"] = num("net_income__yoy_growth")
    current_fcf = num("operating_cash_flow") - num("capital_expenditure")
    prior_fcf = num("operating_cash_flow__prior_year") - num("capital_expenditure__prior_year")
    out["free_cash_flow_growth"] = current_fcf.div(prior_fcf.abs().where(prior_fcf.abs() > 1e-12)) - np.sign(prior_fcf)
    current_margin = num("operating_margin")
    prior_margin = num("operating_income__prior_year").div(num("revenue__prior_year"))
    out["operating_margin_change"] = current_margin - prior_margin
    assets = num("assets")
    out["gross_profitability"] = num("gross_profit").div(assets)
    out["repurchases_to_revenue"] = num("repurchases_to_revenue")
    out["accruals_to_assets"] = (num("net_income") - num("operating_cash_flow")).div(assets)
    out["asset_growth"] = np.nan
    out["dilution_growth"] = num("diluted_shares__yoy_growth")
    availability = [column for column in raw if column.endswith("__available_at")]
    if availability:
        parsed_availability = raw[availability].apply(
            lambda column: pd.to_datetime(column, utc=True, errors="coerce")
        )
        out["quality_available_at"] = parsed_availability.max(axis=1)
    else:
        out["quality_available_at"] = pd.NaT
    inventory = [{"kind": "companyfacts", "cik10": cik10, "path": str(fact_path), "sha256": sha256(fact_path), "source": "sec_companyfacts"}]
    if submission_path.exists():
        inventory.append({"kind": "submissions", "cik10": cik10, "path": str(submission_path), "sha256": sha256(submission_path), "source": "sec_submissions"})
    return out, inventory


def event_scores(membership: pd.DataFrame, decisions: pd.DatetimeIndex) -> pd.DataFrame:
    sectors = membership.sort_values("decision_at").drop_duplicates("cik10", keep="last").set_index("cik10").sector.to_dict()
    earnings_path = ROOT / "evidence/sec_earnings_drift_rank_v1/event_reactions.csv"
    form4_path = ROOT / "evidence/sec_form4_insider_cluster_search_v1/open_market_purchase_events.csv"
    earnings = pd.read_csv(earnings_path, dtype={"cik10": str}) if earnings_path.exists() else pd.DataFrame()
    form4 = pd.read_csv(form4_path, dtype={"cik10": str}) if form4_path.exists() else pd.DataFrame()
    if not earnings.empty:
        earnings["known_at"] = pd.to_datetime(earnings.response_date, utc=True, errors="coerce")
        earnings["raw"] = pd.to_numeric(earnings.abnormal_reaction, errors="coerce")
    if not form4.empty:
        form4["known_at"] = pd.to_datetime(form4.filing_date, utc=True, errors="coerce")
        dollars = np.log1p(pd.to_numeric(form4.purchase_dollars, errors="coerce").clip(lower=0.0))
        form4["raw"] = dollars * (1.0 + pd.to_numeric(form4.role_score, errors="coerce").fillna(0.0))
    rows = []
    for decision in decisions:
        cutoff, start = decision - pd.Timedelta(weeks=1), decision - pd.Timedelta(weeks=53)
        maps = []
        for events in (earnings, form4):
            if events.empty:
                continue
            recent = events[(events.known_at < cutoff) & (events.known_at >= start)].copy()
            recent = recent.sort_values("known_at").drop_duplicates("cik10", keep="last")
            recent["sector"] = recent.cik10.map(sectors).fillna("unknown")
            recent["rank"] = recent.groupby("sector").raw.rank(pct=True, method="average")
            maps.append(recent.set_index("cik10")["rank"])
        combined = pd.concat(maps, axis=1).mean(axis=1) if maps else pd.Series(dtype=float)
        for cik10 in membership.loc[membership.decision_at.eq(decision), "cik10"]:
            rows.append({"decision_at": decision, "cik10": cik10, "event_score": float(combined.get(cik10, 0.5))})
    return pd.DataFrame(rows)


def benchmark_returns(index: pd.DatetimeIndex) -> pd.DataFrame:
    cash = pd.read_csv(ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv", parse_dates=["Date"]).set_index("Date").net_return
    price_path = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
    prices = read_dated_csv(price_path).apply(pd.to_numeric, errors="coerce")
    weights = read_dated_csv(ROOT / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv").apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    blend = net_portfolio_returns(weights, next_week_returns(prices).reindex(columns=weights.columns), 50.0)
    result = pd.concat({
        "sec_cash_conversion_breadth20_dynamic_v1": cash,
        "candidate_return_first_60_40_forward_v1": blend,
    }, axis=1)
    result.index = pd.to_datetime(result.index).tz_localize(None)
    return result.reindex(index)


def main() -> int:
    gate = json.loads(GATE.read_text())
    if not gate.get("strategy_testing_authorized"):
        raise RuntimeError("broad research gate is not open")
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at", "available_at"])
    membership["cik10"] = membership.cik10.str.zfill(10)
    decisions = pd.DatetimeIndex(sorted(membership.decision_at.unique()))
    naive_decisions = decisions.tz_localize(None)
    weekly_index = pd.date_range("2022-12-02", "2026-08-21", freq="W-FRI")
    terminals = pd.read_csv(TERMINALS, dtype={"cik10": str})
    terminal_map = {row.cik10: pd.Timestamp(row.sec_terminal_date) for row in terminals.itertuples(index=False)}
    sources = price_sources()
    valid_ciks = sorted(set(membership.loc[membership.validated_price_available.astype(bool), "cik10"]))
    missing_sources = sorted(set(valid_ciks) - set(sources))
    if missing_sources:
        raise RuntimeError(f"validated CIKs without a price source: {missing_sources[:20]} ({len(missing_sources)} total)")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    price_cache = OUTPUT / "weekly_adjusted_prices.csv.gz"
    price_inventory_cache = OUTPUT / "price_source_inventory.csv"
    if price_cache.exists() and price_inventory_cache.exists():
        prices = pd.read_csv(price_cache, index_col=0, parse_dates=True)
        prices.index = pd.to_datetime(prices.index).tz_localize(None)
        inventory = pd.read_csv(price_inventory_cache, dtype={"cik10": str}).to_dict("records")
    else:
        tasks = [(cik, *sources[cik], weekly_index, terminal_map.get(cik)) for cik in valid_ciks]
        series, inventory = {}, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            for cik10, weekly, source_row in pool.map(read_weekly, tasks):
                series[cik10] = weekly
                inventory.append(source_row)
        prices = pd.DataFrame(series, index=weekly_index).sort_index(axis=1)
        prices.rename_axis("Date").to_csv(price_cache, compression="gzip")
        pd.DataFrame(inventory).to_csv(price_inventory_cache, index=False)

    sectors = membership.sort_values("decision_at").drop_duplicates("cik10", keep="last").set_index("cik10").sector.to_dict()
    residual26 = residual_momentum_scores(prices, sectors, lookback_weeks=26, skip_weeks=4, minimum_history_weeks=26)
    residual52 = residual_momentum_scores(prices, sectors, lookback_weeks=52, skip_weeks=4, minimum_history_weeks=26)
    residual = pd.concat({"r26": residual26, "r52": residual52}, axis=1).T.groupby(level=1).mean().T
    trend, _ = trend_quality_scores(prices)

    pilot = json.loads(PILOT.read_text())
    quality_tasks = [(cik, list(decisions), pilot) for cik in sorted(set(membership.cik10))]
    quality_rows, quality_inventory = [], []
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        for frame, source_rows in pool.map(quality_one, quality_tasks):
            if not frame.empty:
                quality_rows.append(frame)
            quality_inventory.extend(source_rows)
    raw_quality = pd.concat(quality_rows, ignore_index=True) if quality_rows else pd.DataFrame()
    quality_panel = membership[["decision_at", "cik10", "sector"]].merge(raw_quality, on=["decision_at", "cik10"], how="left")
    config = json.loads(PROGRAM.read_text())["signal_families"]["quality_momentum"]
    quality = sector_neutral_quality_scores(
        quality_panel,
        positive_features=config["positive_features"],
        negative_features=config["negative_features"],
        minimum_available_features=config["minimum_available_features"],
    )[["decision_at", "cik10", "quality_momentum_score", "quality_available_at"]]
    events = event_scores(membership, decisions)

    rows = []
    for decision in decisions:
        prior = weekly_index[weekly_index < decision.tz_localize(None)]
        signal_date = prior[-1] if len(prior) else pd.NaT
        members = membership[membership.decision_at.eq(decision)][["decision_at", "cik10"]].copy()
        members["residual_momentum"] = members.cik10.map(residual.loc[signal_date] if pd.notna(signal_date) else {})
        members["trend_quality"] = members.cik10.map(trend.loc[signal_date] if pd.notna(signal_date) else {})
        rows.append(members)
    features = pd.concat(rows, ignore_index=True)
    features = features.merge(quality, on=["decision_at", "cik10"], how="left").merge(events, on=["decision_at", "cik10"], how="left")
    features = features.rename(columns={"quality_momentum_score": "quality_momentum"})
    features["event_score"] = features.event_score.fillna(0.5)
    # Every price observation used is from the completed week strictly before
    # the decision; SEC and event inputs are filtered even earlier.
    features["available_at"] = features.decision_at - pd.Timedelta(nanoseconds=1)
    features = features[["decision_at", "available_at", "cik10", "residual_momentum", "trend_quality", "quality_momentum", "event_score"]]

    features.to_csv(OUTPUT / "causal_features.csv.gz", index=False, compression="gzip")
    prices.rename_axis("Date").to_csv(OUTPUT / "weekly_adjusted_prices.csv.gz", compression="gzip")
    benchmark_returns(weekly_index).rename_axis("Date").to_csv(OUTPUT / "benchmark_weekly_returns.csv.gz", compression="gzip")
    inventory.extend(quality_inventory)
    inventory.extend([
        {"kind": "control", "cik10": "", "path": str(MEMBERSHIP), "sha256": sha256(MEMBERSHIP), "source": "audited_membership"},
        {"kind": "control", "cik10": "", "path": str(GATE), "sha256": sha256(GATE), "source": "research_gate"},
    ])
    inventory_frame = pd.DataFrame(inventory).drop_duplicates(["kind", "cik10", "path"]).sort_values(["kind", "cik10", "path"])
    inventory_frame.to_csv(OUTPUT / "source_inventory.csv", index=False)
    artifact_names = ["causal_features.csv.gz", "weekly_adjusted_prices.csv.gz", "benchmark_weekly_returns.csv.gz", "source_inventory.csv"]
    manifest = {
        "experiment": "sec_broad_panel_inputs_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate_sha256": sha256(GATE),
        "membership_sha256": sha256(MEMBERSHIP),
        "rows": int(len(features)),
        "decisions": int(features.decision_at.nunique()),
        "priced_ciks": int(prices.notna().any().sum()),
        "source_inventory_rows": int(len(inventory_frame)),
        "feature_nonmissing_share": {name: float(features[name].notna().mean()) for name in ["residual_momentum", "trend_quality", "quality_momentum", "event_score"]},
        "point_in_time": True,
        "performance_evaluated": False,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {name: sha256(OUTPUT / name) for name in artifact_names},
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
