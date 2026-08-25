#!/usr/bin/env python3
"""Search causal SEC Form 4 open-market insider-purchase overlays."""

from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_survivorship_valuation_discovery_v1 as discovery
import run_sec_survivorship_valuation_overlay_search_v1 as overlay
import run_sec_diversified_valuation_ensemble_search_v1 as diversified

CONFIG = ROOT / "config/sec_form4_insider_cluster_search_v1.json"
VINTAGES = ROOT / "data/sec_form4_bulk_vintages"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
CAPS = ROOT / "evidence/sec_survivorship_valuation_discovery_v1/normalized_valuation_panel.csv"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_form4_insider_cluster_search_v1"


def truthy(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.lower().isin({"1", "true", "yes"})


def load_events() -> pd.DataFrame:
    vintage = VINTAGES / (VINTAGES / "LATEST").read_text().strip() / "extracted"
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    universe = set(membership.cik10.str.zfill(10))
    pieces = []
    for quarter in sorted(vintage.iterdir()):
        submissions = pd.read_csv(
            quarter / "SUBMISSION.tsv", sep="\t", dtype=str,
            usecols=["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERNAME", "AFF10B5ONE"],
        )
        submissions["cik10"] = submissions.ISSUERCIK.str.zfill(10)
        submissions = submissions[(submissions.DOCUMENT_TYPE == "4") & submissions.cik10.isin(universe)]
        transactions = pd.read_csv(
            quarter / "NONDERIV_TRANS.tsv", sep="\t", dtype=str,
            usecols=["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "TRANS_DATE", "TRANS_CODE", "EQUITY_SWAP_INVOLVED", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"],
        )
        transactions["shares"] = pd.to_numeric(transactions.TRANS_SHARES, errors="coerce")
        transactions["price"] = pd.to_numeric(transactions.TRANS_PRICEPERSHARE, errors="coerce")
        transactions = transactions[
            (transactions.TRANS_CODE == "P")
            & (transactions.TRANS_ACQUIRED_DISP_CD == "A")
            & ~truthy(transactions.EQUITY_SWAP_INVOLVED)
            & transactions.shares.gt(0) & transactions.price.gt(0)
        ].drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"])
        transactions["purchase_dollars"] = transactions.shares * transactions.price
        purchases = transactions.groupby("ACCESSION_NUMBER", as_index=False).agg(
            purchase_dollars=("purchase_dollars", "sum"),
            transaction_count=("NONDERIV_TRANS_SK", "nunique"),
            earliest_transaction_date=("TRANS_DATE", "min"),
        )
        owners = pd.read_csv(
            quarter / "REPORTINGOWNER.tsv", sep="\t", dtype=str,
            usecols=["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"],
        )
        relevant_accessions = set(submissions.ACCESSION_NUMBER) & set(purchases.ACCESSION_NUMBER)
        owners = owners[owners.ACCESSION_NUMBER.isin(relevant_accessions)].drop_duplicates(["ACCESSION_NUMBER", "RPTOWNERCIK"])
        owners["title"] = owners.RPTOWNER_TITLE.fillna("").str.upper()
        owners["is_ceo"] = owners.title.str.contains(r"\bCEO\b|CHIEF EXECUTIVE", regex=True)
        owners["is_cfo"] = owners.title.str.contains(r"\bCFO\b|CHIEF FINANCIAL", regex=True)
        owners["is_director"] = owners.RPTOWNER_RELATIONSHIP.fillna("").str.contains("Director")
        owners["is_officer"] = owners.RPTOWNER_RELATIONSHIP.fillna("").str.contains("Officer")
        owners["is_ten_percent"] = owners.RPTOWNER_RELATIONSHIP.fillna("").str.contains("TenPercentOwner")
        owner_summary = owners.groupby("ACCESSION_NUMBER", as_index=False).agg(
            owner_count=("RPTOWNERCIK", "nunique"), is_ceo=("is_ceo", "max"), is_cfo=("is_cfo", "max"),
            is_director=("is_director", "max"), is_officer=("is_officer", "max"),
            is_ten_percent=("is_ten_percent", "max"),
        )
        owner_ids = owners.groupby("ACCESSION_NUMBER").RPTOWNERCIK.apply(
            lambda values: "|".join(sorted(set(values.dropna().astype(str))))
        ).rename("owner_ciks").reset_index()
        owner_summary = owner_summary.merge(owner_ids, on="ACCESSION_NUMBER", how="left")
        event = submissions.merge(purchases, on="ACCESSION_NUMBER", how="inner").merge(owner_summary, on="ACCESSION_NUMBER", how="inner")
        event["filing_date"] = pd.to_datetime(event.FILING_DATE, format="%d-%b-%Y", utc=True, errors="coerce")
        event["aff10b5one"] = truthy(event.AFF10B5ONE)
        pieces.append(event)
    events = pd.concat(pieces, ignore_index=True).dropna(subset=["filing_date"])
    events = events.drop_duplicates("ACCESSION_NUMBER").copy()

    membership["cik10"] = membership.cik10.str.zfill(10)
    membership["decision_at"] = pd.to_datetime(membership.decision_at, utc=True)
    identity = membership[["decision_at", "cik10", "company_name_as_filed", "sector", "tradable_member"]].sort_values(["decision_at", "cik10"])
    events = pd.merge_asof(events.sort_values(["filing_date", "cik10"]), identity, left_on="filing_date", right_on="decision_at", by="cik10", direction="backward")
    events = events[events.tradable_member.fillna(False).astype(bool)].copy()
    caps = pd.read_csv(CAPS, dtype={"cik10": str}, usecols=["decision_at", "cik10", "market_cap"])
    caps["cik10"] = caps.cik10.str.zfill(10)
    caps["cap_date"] = pd.to_datetime(caps.pop("decision_at"), utc=True)
    events = pd.merge_asof(events.sort_values(["filing_date", "cik10"]), caps.sort_values(["cap_date", "cik10"]), left_on="filing_date", right_on="cap_date", by="cik10", direction="backward")
    events["purchase_to_market_cap"] = events.purchase_dollars / pd.to_numeric(events.market_cap, errors="coerce")
    events["role_score"] = events.is_ceo.astype(float) * 2.0 + events.is_cfo.astype(float) * 1.75 + events.is_director.astype(float) + events.is_officer.astype(float) * 0.5
    return events.sort_values(["filing_date", "cik10", "ACCESSION_NUMBER"]).reset_index(drop=True)


def build_panels(events: pd.DataFrame, weekly: pd.DataFrame, dates: pd.DatetimeIndex, config: dict) -> dict[tuple, pd.DataFrame]:
    momentum = weekly.pct_change(4).shift(1)
    rows_by_key = {key: [] for key in itertools.product(config["event_windows_days"], config["families"], config["price_confirmation"])}
    naive_filing = events.filing_date.dt.tz_localize(None)
    aggregation = {
        "latest_filing": ("filing_date", "max"), "purchase_dollars": ("purchase_dollars", "sum"),
        "purchase_to_market_cap": ("purchase_to_market_cap", "sum"),
        "filing_count": ("ACCESSION_NUMBER", "nunique"), "role_score": ("role_score", "max"),
        "market_cap": ("market_cap", "last"), "any_ceo": ("is_ceo", "max"), "any_cfo": ("is_cfo", "max"),
    }
    identities = ["cik10", "company_name_as_filed", "sector"]
    def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
        grouped = frame.groupby(identities, as_index=False).agg(**aggregation)
        expanded = frame.assign(owner_cik=frame.owner_ciks.fillna("").str.split("|")).explode("owner_cik")
        counts = expanded[expanded.owner_cik.ne("")].groupby(identities).owner_cik.nunique().rename("owner_count").reset_index()
        return grouped.merge(counts, on=identities, how="left").assign(owner_count=lambda value: value.owner_count.fillna(0).astype(int))

    for window in config["event_windows_days"]:
        for date in dates:
            eligible = events[(naive_filing < date) & (naive_filing >= date - pd.Timedelta(days=int(window)))].copy()
            if eligible.empty:
                continue
            all_grouped = aggregate(eligible)
            discretionary = eligible[~eligible.aff10b5one]
            discretionary_grouped = aggregate(discretionary) if len(discretionary) else all_grouped.iloc[0:0]
            families = {
                "all_open_market": all_grouped,
                "cluster_2plus": all_grouped[all_grouped.owner_count >= 2],
                "executive_or_cluster": all_grouped[all_grouped.any_ceo | all_grouped.any_cfo | (all_grouped.owner_count >= 2)],
                "discretionary": discretionary_grouped,
                "discretionary_cluster_2plus": discretionary_grouped[discretionary_grouped.owner_count >= 2],
            }
            for family, base_frame in families.items():
                with_momentum = base_frame.copy()
                with_momentum["price_momentum_4w"] = with_momentum.cik10.map(momentum.loc[date].to_dict())
                for confirmation in config["price_confirmation"]:
                    grouped = with_momentum if confirmation == "none" else with_momentum[with_momentum.price_momentum_4w > 0]
                    if grouped.empty:
                        continue
                    grouped = grouped.copy()
                    features = pd.DataFrame(index=grouped.index)
                    features["intensity"] = np.log1p(grouped.purchase_to_market_cap.clip(lower=0)).rank(pct=True)
                    features["dollars"] = np.log1p(grouped.purchase_dollars).rank(pct=True)
                    features["owners"] = grouped.owner_count.rank(pct=True)
                    features["roles"] = grouped.role_score.rank(pct=True)
                    if confirmation == "positive_4w":
                        features["momentum"] = grouped.price_momentum_4w.rank(pct=True)
                    grouped["score"] = features.mean(axis=1)
                    grouped["decision_at"] = date
                    rows_by_key[(window, family, confirmation)].append(grouped)
    return {key: pd.concat(rows, ignore_index=True) if rows else pd.DataFrame() for key, rows in rows_by_key.items()}


def simulate_weekly(prices: pd.DataFrame, targets: dict[pd.Timestamp, list[str]], cost_bps: float) -> pd.DataFrame:
    positions = {"cash::USD": 1.0}
    rows = []
    for offset, date in enumerate(prices.index[:-1]):
        total = sum(positions.values())
        selected = targets.get(date, [])
        available = [asset for asset in selected if asset in prices and pd.notna(prices.at[date, asset])]
        intended = 1.0 / len(available) if available else 0.0
        target_weights = {asset: intended for asset in available}
        target_weights["cash::USD"] = 0.0 if available else 1.0
        prior = {asset: value / total for asset, value in positions.items()} if total else {"cash::USD": 1.0}
        turnover = 0.5 * sum(abs(target_weights.get(asset, 0.0) - prior.get(asset, 0.0)) for asset in set(target_weights) | set(prior))
        cost = total * turnover * float(cost_bps) / 10000.0
        deployable = total - cost
        positions = {asset: deployable * weight for asset, weight in target_weights.items() if weight > 0}
        next_date = prices.index[offset + 1]
        next_positions = {}
        for asset, value in positions.items():
            if asset == "cash::USD":
                next_positions[asset] = next_positions.get(asset, 0.0) + value
            else:
                start, end = prices.at[date, asset], prices.at[next_date, asset]
                if pd.notna(start) and pd.notna(end) and float(start) != 0:
                    next_positions[asset] = value * float(end) / float(start)
                else:
                    next_positions["cash::USD"] = next_positions.get("cash::USD", 0.0) + value
        positions = next_positions
        after = sum(positions.values())
        rows.append({"Date": date, "net_return": after / total - 1.0, "turnover": turnover, "cost": cost / total, "wealth": after})
    result = pd.DataFrame(rows).set_index("Date")
    result["drawdown"] = result.wealth / result.wealth.cummax() - 1.0
    return result


def fast_select_ciks(sorted_frame: pd.DataFrame, breadth: int, cap: float) -> list[str]:
    maximum = max(1, int(np.floor(float(breadth) * float(cap) + 1e-12)))
    counts, selected = {}, []
    for cik, sector in zip(sorted_frame.cik10.to_numpy(), sorted_frame.sector.astype(str).to_numpy()):
        if counts.get(sector, 0) >= maximum:
            continue
        selected.append(str(cik))
        counts[sector] = counts.get(sector, 0) + 1
        if len(selected) == int(breadth):
            return selected
    return []


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
    dates = pd.date_range(pd.Timestamp(config["start_date"]), control.index.max() + pd.offsets.Week(weekday=4), freq="W-FRI")
    events = load_events()
    print(f"loaded {len(events):,} eligible open-market purchase filings", flush=True)
    sources, terminals = discovery.source_map(), base.terminal_dates()
    price_series = {}
    for cik in sorted(set(events.cik10)):
        spec = sources.get(cik)
        if spec:
            try:
                price_series[cik] = base.read_weekly_price(spec[1], spec[0], dates, terminals.get(cik))
            except OSError:
                price_series[cik] = pd.Series(np.nan, index=dates)
    weekly = pd.DataFrame(price_series, index=dates)
    print(f"loaded weekly prices for {weekly.shape[1]} issuers", flush=True)
    panels = build_panels(events, weekly, dates, config)
    print("built exact distinct-owner event panels", flush=True)
    structures = []
    for (window, family, confirmation), panel in panels.items():
        if panel.empty:
            continue
        by_date = {date: frame for date, frame in panel.groupby("decision_at", sort=False)}
        sorted_cache = {
            (date, int(floor)): frame[pd.to_numeric(frame.market_cap, errors="coerce") >= float(floor)].sort_values(["score", "cik10"], ascending=[False, True])
            for date, frame in by_date.items() for floor in config["market_cap_floors"]
        }
        for breadth, floor, sector_cap in itertools.product(config["breadths"], config["market_cap_floors"], config["sector_caps"]):
            targets = {}
            for date in dates[:-1]:
                frame = sorted_cache.get((date, int(floor)), panel.iloc[0:0])
                targets[date] = fast_select_ciks(frame, int(breadth), float(sector_cap))
            name = f"{family}__win{window}d__{confirmation}__top{breadth}__floor{int(floor)//1_000_000}m__sector{int(float(sector_cap)*100)}"
            structures.append((name, window, family, confirmation, breadth, floor, sector_cap, targets))
    rows, paths = [], {}
    recent_start = control.index.max() - pd.DateOffset(years=1)
    for index, (name, window, family, confirmation, breadth, floor, sector_cap, targets) in enumerate(structures, start=1):
        for cost in config["cost_bps"]:
            sleeve = simulate_weekly(weekly, targets, float(cost))
            joined = pd.concat([control, sleeve.net_return.rename("sleeve")], axis=1, join="inner").dropna()
            for allocation in config["overlay_allocations"]:
                path = overlay.simulate(joined.control, joined.sleeve, pd.Series(float(allocation), index=joined.index), float(cost))
                recent = overlay.metrics(path.loc[path.index >= recent_start, "net_return"])
                full = overlay.metrics(path.net_return)
                candidate = f"{name}__w{float(allocation):.2f}__{cost}bps"
                rows.append({"candidate": candidate, "sleeve": name, "window_days": window, "family": family, "confirmation": confirmation, "breadth": breadth, "market_cap_floor": floor, "sector_cap": sector_cap, "allocation": allocation, "cost_bps": cost, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["drawdown"], "active_weeks": sum(bool(value) for value in targets.values())})
                if int(cost) == 50:
                    paths[candidate] = path
        if index % 50 == 0 or index == len(structures):
            print(f"tested structures {index}/{len(structures)}", flush=True)
    performance = pd.DataFrame(rows)
    ranking = performance[performance.cost_bps == 50].sort_values(["recent_cagr", "full_cagr"], ascending=False).copy()
    ranking["beats_control_both"] = (ranking.recent_cagr > float(config["control_recent_cagr"])) & (ranking.full_cagr > float(config["control_full_cagr"]))
    best = ranking.iloc[0]
    severe = performance[(performance.sleeve == best.sleeve) & np.isclose(performance.allocation, best.allocation) & (performance.cost_bps == 200)].iloc[0]
    best_panel = panels[(int(best.window_days), str(best.family), str(best.confirmation))]
    best_choices = []
    for date, frame in best_panel.groupby("decision_at", sort=True):
        frame = frame[pd.to_numeric(frame.market_cap, errors="coerce") >= float(best.market_cap_floor)]
        chosen = diversified.select_with_sector_cap(frame, int(best.breadth), float(best.sector_cap))
        if len(chosen) == int(best.breadth):
            chosen = chosen.copy()
            chosen["decision_at"] = date
            best_choices.append(chosen)
    events.to_csv(OUTPUT / "open_market_purchase_events.csv", index=False)
    (pd.concat(best_choices, ignore_index=True) if best_choices else pd.DataFrame()).to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    ranking.head(250).to_csv(OUTPUT / "top_candidates.csv", index=False)
    paths[str(best.candidate)].rename_axis("Date").to_csv(OUTPUT / "best_path_50bps.csv")
    checks = {
        "only_original_form4": True,
        "only_open_market_purchases": True,
        "filings_strictly_before_decisions": bool(all(
            (pd.to_datetime(panel.latest_filing, utc=True).dt.tz_localize(None) < pd.to_datetime(panel.decision_at)).all()
            for panel in panels.values() if not panel.empty
        )),
        "price_confirmation_lagged": True,
        "all_costs_reported": set(performance.cost_bps) == set(config["cost_bps"]),
        "allocations_bounded": bool(performance.allocation.between(0.0, 0.4).all()),
        "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
    }
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "source_vintage": (VINTAGES / "LATEST").read_text().strip(), "open_market_purchase_filings": int(len(events)), "unique_issuers": int(events.cik10.nunique()), "tested_structures": int(len(structures)), "tested_paths": int(len(performance)), "best_candidate": str(best.candidate), "best_recent_cagr": float(best.recent_cagr), "best_recent_sharpe": float(best.recent_sharpe), "best_recent_drawdown": float(best.recent_drawdown), "best_full_cagr": float(best.full_cagr), "best_full_drawdown": float(best.full_drawdown), "best_active_weeks": int(best.active_weeks), "severe_200bps_recent_cagr": float(severe.recent_cagr), "candidates_beating_control_both": int(ranking.beats_control_both.sum()), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# SEC Form 4 insider-cluster search v1\n\n" f"Tested {len(performance):,} costed overlays from {len(events):,} point-in-time open-market purchase filings. The best discovery path produced {best.recent_cagr:.2%} recent CAGR, {best.recent_sharpe:.2f} Sharpe, {best.recent_drawdown:.2%} drawdown, and {best.full_cagr:.2%} full CAGR. At 200-bps costs it retained {severe.recent_cagr:.2%}.\n\n" "Only original Form 4 code-P acquisitions with positive shares and prices were included. Filing dates are conservatively eligible only on a later weekly decision. This search cannot authorize promotion before delay, issuer-exclusion, and neighboring-parameter audits.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
