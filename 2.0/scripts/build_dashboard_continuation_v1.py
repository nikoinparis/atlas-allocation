#!/usr/bin/env python3
"""Continue the dashboard portfolios with the saved selection rules and current prices.

This is retrospective accounting, never a forward-log writer. Saved historical
returns are preserved through the final allocation date. Later weekly allocation
signals are recomputed by the original research functions, with positions marked
and drifted daily. Source limitations are part of the output, not silently filled
with invented scores or a different model.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "src")]
import build_clock_histories_v1 as clocks
import run_sec_growth_survivorship_retest_v1 as growth
import run_sec_growth_confidence_sizing_v1 as confidence
import run_sec_growth_confidence_universal_cap_v1 as capped_growth
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth
import run_sec_cash_conversion_capped_dynamic_v1 as capped_cash
import run_sec_growth_stock_drift_cap_v1 as drift_cap
import run_sec_sector_aware_signal_ensemble_v1 as sector
import run_sec_signal_neighborhood_ensemble_v1 as ensemble
import run_sec_cohort_diversified_regime_tranche_v1 as cohort
import run_sec_breadth_dispersion_allocation_controller_v1 as controller

CASH = "cash::USD"
PUBLIC = ROOT / "dashboard/public"
OUT = ROOT / "evidence/dashboard_continuation_v1"
SNAPSHOT = PUBLIC / "return-first-dashboard.json"
ETF = "candidate-return-first-60-40-forward-v1"
GROWTH = "sec-growth-survivorship-aware-v1"
BREADTH = "sec-cash-conversion-breadth20-dynamic-v1"
RESIDUAL = "sec-residual-controlled-1x-v1"
SECTOR = "sec-sector-aware-signal-ensemble-v1"


def update_strategy_stats(item: dict) -> None:
    """Keep current labels from presenting an August trailing return as today's."""
    strategy = item["strategy"]
    strategy.setdefault("sealedResearchSnapshot", copy.deepcopy({k: strategy[k] for k in
                        ("name", "shortName", "badge", "asOf", "featuredMetric", "fullHistory")}))
    values = pd.Series([r["netReturn"] or 0 for r in item["dailyRecords"] if r["tradingDay"]], dtype=float)
    wealth = (1 + values).cumprod()
    recent = values.tail(252)
    cagr = float((1 + recent).prod() ** (252 / len(recent)) - 1)
    years = (pd.Timestamp(item["dailyRecords"][-1]["date"]) - pd.Timestamp(item["dailyRecords"][0]["date"])).days / 365.25
    strategy["fullHistory"].update(cagr=float(wealth.iloc[-1] ** (1 / years) - 1),
                                    maxDrawdown=float((wealth / wealth.cummax().clip(lower=1) - 1).min()))
    strategy["shortName"] = {ETF: "ETF Incumbent", GROWTH: "SEC Growth Top-Five", BREADTH: "Dynamic Breadth-20",
                              RESIDUAL: "Residual-Controlled", SECTOR: "Sector-Aware Ensemble"}[strategy["id"]]
    if strategy["id"] == GROWTH:
        strategy["name"] = "SEC Growth Top-Five"
    strategy["badge"] = f"{cagr:.2%} trailing 252-session CAGR"
    strategy["featuredMetric"] = {"label": "UPDATED TRAILING 252 SESSIONS", "value": cagr,
                                   "note": f"Simulation through {item['dailyRecords'][-1]['date']}; includes continued rules and costs."}


def read(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True).tz_localize(None)
    return frame.sort_index()


def book_at(events: dict, day: pd.Timestamp) -> dict[str, float]:
    eligible = [d for d in events if d <= day]
    return events[max(eligible)] if eligible else {CASH: 1.0}


def mix(*parts: tuple[float, dict]) -> dict[str, float]:
    result: dict[str, float] = {}
    for share, book in parts:
        for symbol, weight in book.items():
            result[symbol] = result.get(symbol, 0.0) + share * float(weight)
    result = {s: w for s, w in result.items() if abs(w) > 1e-12}
    if abs(sum(result.values()) - 1.0) > 1e-8:
        raise ValueError(f"weights do not sum to one: {sum(result.values())}")
    return result


def symbol_events(events: dict, mapping: dict) -> dict:
    result = {}
    for day, book in events.items():
        out: dict[str, float] = {}
        for key, value in book.items():
            symbol = mapping.get(str(key), CASH if str(key)[:1].isdigit() else str(key))
            out[symbol] = out.get(symbol, 0.0) + float(value)
        result[pd.Timestamp(day)] = out
    return result


def etf_rule_history(px: clocks.Prices, end: pd.Timestamp) -> pd.DataFrame:
    """Rebuild the already-selected 60/40 model, without selecting new parameters."""
    import run_aggressive_return_discovery_batch_62 as b62
    import run_independent_return_source_discovery_batch_63 as b63
    import run_return_confirmation_diversification_batch_64 as b64
    import run_exhaustive_return_first_discovery_batch_66 as b66
    from systematic_trader.ggg_independent import next_week_returns, portfolio_path
    from systematic_trader.return_confirmation import cross_asset_features, four_week_labels
    from systematic_trader.return_first_search import build_advanced_sources, regime_source_alphas
    old = read(b64.BUNDLE / "data/01_data_hub/weekly_prices.csv")
    fresh = px.etf.resample("W-FRI").last().loc[:end]
    prices = old.reindex(old.index.union(fresh.index[fresh.index > old.index[-1]]))
    for symbol in old:
        if symbol not in fresh:
            raise ValueError(f"ETF input {symbol} missing from latest vintage")
        overlap = old[symbol].dropna().index.intersection(fresh[symbol].dropna().index)
        if not len(overlap):
            raise ValueError(f"cannot splice ETF {symbol}")
        at = overlap[-1]
        later = prices.index[prices.index > old.index[-1]]
        prices.loc[later, symbol] = fresh[symbol].reindex(later) * old.at[at, symbol] / fresh.at[at, symbol]
    config62 = json.loads(b62.CONFIG_PATH.read_text())
    config62.update(concentrated_global_specs=[], sector_specs=[])
    core = b62.build_signal_sources(prices, config62)["global_xsmom"]
    config63 = json.loads(b63.CONFIG_PATH.read_text())
    config63.update(source_families=["trend_consistency"], top_n=[3])
    trend = b63.build_sources(prices, config63)["trend_consistency_top3"]
    features = cross_asset_features(prices, config63["discovery_assets"])
    decisions = b64.monthly_decisions(prices.index)
    alpha = b64.cross_asset_alphas(features, decisions, json.loads(b64.CONFIG_PATH.read_text()))["cross::breadth_boost"]
    breadth_weights = b64.alpha_blend(core, trend, alpha)
    xlk = b66.static_weights(prices, {"XLK": 1.0})
    forward = next_week_returns(prices)
    relative = (portfolio_path(breadth_weights, forward.reindex(columns=breadth_weights.columns), 0).net_return
                - portfolio_path(xlk, forward.reindex(columns=xlk.columns), 0).net_return)
    config66 = json.loads(b66.CONFIG_PATH.read_text())
    ml = config66["nonlinear_ml"]
    labels = four_week_labels(relative, decisions, ml["label_horizon_weeks"])
    predictions, audit = b66.nonlinear_predictions(features, labels, decisions, "hist_gradient_boosting",
                                                  ml["minimum_training_months"], ml["random_seed"] + 3)
    if not audit.embargo_pass.all():
        raise ValueError("ETF model used an unfinished training label")
    ml_alpha = (predictions.reindex(decisions) > 0).astype(float).reindex(prices.index).ffill().fillna(0)
    hgb = b64.alpha_blend(xlk, breadth_weights, ml_alpha)
    base = b62.mix([xlk, hgb], [.7, .3])
    source = build_advanced_sources(prices, families=["rank_consensus"], universe=config66["discovery_assets"],
                                    top_ns=[1], methods=["score_inverse_volatility"], minimum_score=0)["rank_consensus__top1__score_invvol"]
    regime = b66.monthly_alpha(regime_source_alphas(prices, config66["discovery_assets"])["broad_risk_on"], prices.index)
    ceiling = b64.alpha_blend(xlk, source, regime)
    weights = b62.mix([base, ceiling], [.6, .4])
    saved = read(ROOT / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv")
    shared = weights.index.intersection(saved.index)
    columns = weights.columns.union(saved.columns)
    gap = (weights.reindex(index=shared, columns=columns, fill_value=0)
           - saved.reindex(index=shared, columns=columns, fill_value=0)).abs().max().max()
    if gap > 1e-8:
        raise ValueError(f"ETF reconstruction differs from saved model by {gap:g}")
    OUT.mkdir(parents=True, exist_ok=True)
    weights.to_csv(OUT / "etf_target_weights.csv")
    audit.to_csv(OUT / "etf_training_audit.csv", index=False)
    return weights


def leader_books(prices: pd.DataFrame, targets: dict, incumbent: pd.Series,
                 allocation: pd.Series, etf_events: dict, mapping: dict) -> dict:
    """The original confidence/cap engine's pre-return stock positions, not equal slots."""
    positions = {"incumbent::ETF": 1.0}
    selected = []
    books = {}
    reviews = drift_cap.month_review_dates(prices.index)
    for offset, day in enumerate(prices.index[:-1]):
        target = float(allocation.get(day, allocation.iloc[-1]))
        if day in targets:
            selected = targets[day]
            available = [s for s in selected if s in prices and pd.notna(prices.at[day, s])]
            missing = [s for s in selected if s not in available]
            positions, _, _ = capped_growth.target_reset(positions, target, selected, available, missing, "base", 50)
        elif selected:
            positions, _, _ = capped_growth.allocation_reset(positions, target, selected, 50)
        if day in reviews and selected:
            total = sum(positions.values())
            limit = total * target / len(selected) * 1.5
            excess = 0.0
            for s in positions:
                if capped_growth.is_growth_asset(s) and s != CASH and positions[s] > limit:
                    excess += positions[s] - limit
                    positions[s] = limit
            positions["incumbent::ETF"] = positions.get("incumbent::ETF", 0) + excess * .995
        total = sum(positions.values())
        book = {}
        for s, value in positions.items():
            for symbol, weight in (book_at(etf_events, day).items() if s == "incumbent::ETF"
                                   else {mapping.get(s, CASH if s[:1].isdigit() else s): 1.0}.items()):
                book[symbol] = book.get(symbol, 0) + value / total * weight
        books[day] = mix((1.0, book))
        nxt = prices.index[offset + 1]
        grown = {}
        for s, value in positions.items():
            if s == "incumbent::ETF":
                grown[s] = value * (1 + incumbent.get(day, 0))
            elif s == CASH:
                grown[s] = grown.get(s, 0) + value
            elif pd.notna(prices.at[day, s]) and pd.notna(prices.at[nxt, s]):
                grown[s] = value * prices.at[nxt, s] / prices.at[day, s]
            else:
                grown[CASH] = grown.get(CASH, 0) + value
        positions = grown
    return books


def drift_books(events: dict, weekly: pd.DataFrame) -> dict:
    """Quarterly sleeves retain share counts between quarterly resets."""
    held = {CASH: 1.0}
    result = {}
    for offset, day in enumerate(weekly.index):
        if offset:
            prior = weekly.iloc[offset - 1]
            now = weekly.iloc[offset]
            grown = {}
            for s, w in held.items():
                priced = s != CASH and s in weekly and pd.notna(prior[s]) and pd.notna(now[s])
                key = s if priced else CASH
                grown[key] = grown.get(key, 0) + w * (now[s] / prior[s] if priced else 1)
            total = sum(grown.values())
            held = {s: w / total for s, w in grown.items()}
        if day in events:
            held = events[day]
        result[day] = dict(held)
    return result


def continuation(prices: pd.DataFrame, initial: dict, events: dict, cost_bps: float):
    """Close-to-close P&L, then a close trade. Never earn today's move on a new book."""
    held = dict(initial)
    rows = []
    for offset, day in enumerate(prices.index):
        if offset == 0:
            continue
        previous = prices.iloc[offset - 1]
        current = prices.iloc[offset]
        gross = 0.0
        grown = {}
        for symbol, weight in held.items():
            change = 0.0
            if symbol != CASH:
                if symbol not in prices or pd.isna(previous[symbol]) or pd.isna(current[symbol]):
                    raise ValueError(f"missing held price: {symbol} on {day.date()}")
                change = float(current[symbol] / previous[symbol] - 1.0)
            gross += weight * change
            grown[symbol] = weight * (1.0 + change)
        drifted = {s: v / (1.0 + gross) for s, v in grown.items()}
        target = events.get(day)
        changes: dict[str, float] = {}
        turnover = 0.0
        if target is not None:
            mix((1.0, target))  # validate budget before calculating costs
            changes = {s: target.get(s, 0.0) - drifted.get(s, 0.0) for s in set(target) | set(drifted)}
            turnover = 0.5 * sum(abs(v) for v in changes.values())
        cost = turnover * cost_bps / 1e4
        held = dict(target) if target is not None else drifted
        rows.append({"date": day.strftime("%Y-%m-%d"), "grossReturn": gross,
                     "netReturn": (1.0 + gross) * (1.0 - cost) - 1.0,
                     "turnover": turnover, "cost": (1.0 + gross) * cost,
                     "rebalance": turnover > 1e-10,
                     "holdings": [{"symbol": s, "weight": held.get(s, 0.0), "change": changes.get(s, 0.0)}
                                  for s in sorted(set(held) | set(changes))
                                  if abs(held.get(s, 0.0)) > 1e-12 or abs(changes.get(s, 0.0)) > 1e-12]})
    return rows


def route_unpriced_targets(events: dict, prices: pd.DataFrame) -> tuple[dict, list]:
    """Use the original base-case cash policy when an execution quote is absent."""
    routed, missing = {}, []
    for day, book in events.items():
        target = {}
        for symbol, weight in book.items():
            unavailable = symbol != CASH and (symbol not in prices or day not in prices.index
                                               or pd.isna(prices.at[day, symbol]))
            key = CASH if unavailable else symbol
            target[key] = target.get(key, 0.0) + weight
            if unavailable:
                missing.append({"date": str(day.date()), "symbol": symbol, "weightHeldAsCash": weight})
        routed[day] = target
    return routed, missing


def schedules(px: clocks.Prices, end: pd.Timestamp):
    """Invoke original confidence, breadth, sector and tranche rules, without a new search."""
    weekly = read(ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz")
    weekly = weekly.loc["2023-01-01":end]
    # The legacy engines iterate pairs of Fridays and emit the starting Friday.
    # A non-published sentinel lets them form the final close's target using
    # lagged observations, without needing or exposing a future market price.
    weekly = weekly.reindex(weekly.index.append(pd.DatetimeIndex([weekly.index[-1] + pd.Timedelta(days=7)])))
    # Research engines label t -> t+1 returns by their starting Friday. Do not
    # relabel these as week-ending returns when constructing lagged signals.
    choices = pd.read_csv(OUT / "growth_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices.decision_at, utc=True)
    expected_quarter = end.to_period("Q").start_time.tz_localize("UTC")
    if choices.decision_at.max() < expected_quarter:
        raise ValueError(f"quarterly selections end {choices.decision_at.max().date()}; acquire and score {expected_quarter.date()} before continuing")
    gtargets = growth.build_targets(choices, weekly.index)
    gpath, _ = growth.simulate(weekly, gtargets, "base", 50)
    etfweights = etf_rule_history(px, end)
    etf_events = {d: row[row.abs() > 1e-12].to_dict() for d, row in etfweights.iterrows()}
    etf_symbols = set(etfweights.columns) - {CASH}
    px.ensure(etf_symbols)
    etfdaily = px.etf.reindex(columns=sorted(etf_symbols))
    etfweekly = etfdaily.resample("W-FRI").last().reindex(weekly.index)
    ereturns = etfweekly.pct_change(fill_method=None).shift(-1)
    ew = pd.DataFrame([book_at(etf_events, d) for d in weekly.index], index=weekly.index).fillna(0)
    incumbent = (ew.reindex(columns=ereturns.columns, fill_value=0) * ereturns).sum(axis=1).iloc[:-1]
    incumbent -= ew.diff().abs().sum(axis=1).reindex(incumbent.index).fillna(0) * .5 * .005
    aligned = pd.concat([incumbent.rename("incumbent"), gpath.gross_return.rename("growth")], axis=1).dropna()
    signal = confidence.target_allocations(aligned, {"lookback_weeks": 26, "low_allocation": .1,
                                                   "high_allocation": .4, "dual_confirmation": False}, 26)
    leader = capped_growth.simulate(weekly, gtargets, incumbent, signal.target_growth_allocation,
                                    1.5, "base", 50, drift_cap.month_review_dates(weekly.index))
    scores = pd.read_csv(OUT / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    cc_choices = breadth.make_choices(scores[scores.family == "cash_conversion"], 20)
    cc_targets = growth.build_targets(cc_choices, weekly.index)
    cash, _ = capped_cash.simulate_cash(weekly, cc_targets, "base", 50, None, 20)
    outer = capped_cash.overlay_target(leader.index, leader.net_return, cash.net_return, 11, .5)
    sector_config = json.loads(sector.CONFIG.read_text())
    selected = json.loads((sector.OUTPUT / "result.json").read_text())["selected_candidate"]
    spec = next(s for s in sector_config["constructions"] if s["name"] == selected)
    context = {"scores": scores, "weekly": weekly, "index": weekly.index}
    components, _ = sector.component_targets(context, sector_config, spec["cash_sector_cap"], spec["balance_sector_cap"])
    sector_targets = ensemble.mix_targets(components, {"cash100": .5, "balance20": .5})
    sleeve, _ = cohort.simulate_weighted_cash(weekly, sector_targets, "base", 50)
    breadth_signals = controller.breadth_dispersion_signals(weekly.reindex(columns=sorted(set(scores.cik10))), 26)
    high = controller.regime_state(breadth_signals, 26, .4, "breadth_high")
    import run_sec_independent_market_regime_activation_v1 as regime_module
    etfs = px.etf[["SPY", "HYG", "LQD"]].resample("W-FRI").last().reindex(weekly.index)
    vix_path = OUT / "vix_term_structure.csv"
    vix = read(vix_path)
    if vix.index.max() < end:
        import yfinance as yf
        raw = yf.download(["^VIX", "^VIX3M", "^VIX6M"], start=str((vix.index.max() - pd.Timedelta(days=7)).date()),
                          end=str((end + pd.Timedelta(days=1)).date()), auto_adjust=True, progress=False)["Close"]
        raw = raw.rename(columns={"^VIX": "VIX", "^VIX3M": "VIX3M", "^VIX6M": "VIX6M"})
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        raw = raw.resample("W-FRI").last().loc[:end]
        raw["contango"] = np.where(raw.VIX.notna() & raw.VIX3M.notna(), (raw.VIX3M > raw.VIX).astype(float), np.nan)
        fresh = raw[raw.index > vix.index.max()]
        if fresh.empty or fresh.index[-1] < end or fresh[["VIX", "VIX3M"]].isna().any().any():
            raise ValueError("VIX term-structure refresh is incomplete")
        vix = pd.concat([vix, fresh])
        vix.to_csv(vix_path)
    fast = regime_module.regime_features(etfs, weekly.reindex(columns=sorted(set(scores.cik10))), vix,
                                        {"trend_weeks": 13, "volatility_weeks": 8, "credit_weeks": 8,
                                         "breadth_weeks": 13, "calibration_weeks": 26})
    sector_outer, _ = cohort.strategy_target(leader.net_return, sleeve, breadth_signals, high, fast, 11)
    # Start from the saved residual schedule; append new quarterly ranks below.
    from systematic_trader.sec_real_tournament_v2 import _execution_weights, _score
    panel = pd.read_csv(ROOT / "data/sec_broad_research_panel_v2/panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
    panel["execution_at"] = pd.to_datetime(panel.execution_at, utc=True)
    program = json.loads((ROOT / "config/sec_return_improvement_program_v1.json").read_text())
    cfg = program["adaptive_concentration"]
    residual = _execution_weights(_score(panel, "residual_momentum"), max(cfg["breadth_tiers"]),
                                  cfg["maximum_issuer_weight"], cfg["maximum_sector_weight"])
    # New quarterly price-only scores use the same residual formula and the
    # historical filer roster. No other tournament families need to be fitted.
    from systematic_trader.sec_return_improvement import residual_momentum_scores
    broad_vintage = sorted((ROOT / "data/dashboard_continuation_broad_universe_v1").glob("*"))[-1]
    roster = pd.read_csv(broad_vintage / "quarterly_membership.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    broad_weekly = read(ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz")
    new_panels = []
    for decision, members in roster.groupby("decision_at"):
        if decision <= panel.decision_at.max():
            continue
        naive = decision.tz_localize(None)
        before = broad_weekly.index[broad_weekly.index < naive][-1]
        execution = broad_weekly.index[broad_weekly.index > naive][1]
        known = roster[roster.decision_at <= decision].sort_values("decision_at").drop_duplicates("cik10", keep="last")
        sectors = known.set_index("cik10").sector.to_dict()
        prefix = broad_weekly.loc[:before].tail(65).reindex(columns=sorted(sectors))
        r26 = residual_momentum_scores(prefix, sectors, lookback_weeks=26, skip_weeks=4, minimum_history_weeks=26).iloc[-1]
        r52 = residual_momentum_scores(prefix, sectors, lookback_weeks=52, skip_weeks=4, minimum_history_weeks=26).iloc[-1]
        residual_score = pd.concat([r26, r52], axis=1).mean(axis=1)
        members = members[["decision_at", "cik10", "sector"]].copy()
        members["execution_at"] = execution.tz_localize("UTC")
        members["residual_momentum"] = members.cik10.map(residual_score)
        new_panels.append(members)
    if new_panels:
        new_panel = pd.concat(new_panels, ignore_index=True)
        residual = pd.concat([residual, _execution_weights(_score(new_panel, "residual_momentum"), max(cfg["breadth_tiers"]),
                                                         cfg["maximum_issuer_weight"], cfg["maximum_sector_weight"])])
    rtargets = {pd.Timestamp(d).tz_localize(None): group.set_index("cik10").weight.to_dict()
                for d, group in residual.groupby("decision_at")}
    growth_events = {d: {c: 1 / len(cs) for c in cs} for d, cs in gtargets.items()}
    cash_events = {d: {c: 1 / len(cs) for c in cs} for d, cs in cc_targets.items()}
    mapping = px.cik_symbol
    leaders = leader_books(weekly, gtargets, incumbent, signal.target_growth_allocation, etf_events, mapping)
    cash_events = drift_books(cash_events, weekly)
    sector_targets = drift_books(sector_targets, weekly)
    rtargets = drift_books(rtargets, broad_weekly)
    growth_events, cash_events, sector_targets, rtargets = [symbol_events(e, mapping)
                                                          for e in (growth_events, cash_events, sector_targets, rtargets)]
    schedules = {ETF: etf_events, GROWTH: growth_events, BREADTH: {}, RESIDUAL: {}, SECTOR: {}}
    for day in leader.index:
        lead_book = leaders[day]
        cc = float(outer.at[day, "cash_conversion"])
        control = mix((1 - cc, lead_book), (cc, book_at(cash_events, day)))
        schedules[BREADTH][day] = control
        schedules[RESIDUAL][day] = mix((.8, control), (.2, book_at(rtargets, day)))
        sc = float(sector_outer.at[day, "cash_conversion"])
        schedules[SECTOR][day] = mix((1 - sc, lead_book), (sc, book_at(sector_targets, day)))
    limits = ["Retrospective simulation using adjusted closes and 50 bps on traded portfolio turnover; no live executions.",
              "Historical data retains the saved backtest's selection and survivorship limitations.",
              "The continuation trades the reconstructed security-level composite, so its costs can differ from the original nested-sleeve weekly research accounting."]
    return schedules, limits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", default=None, help="latest completed session, YYYY-MM-DD")
    args = parser.parse_args()
    px = clocks.Prices()
    end = pd.Timestamp(args.through) if args.through else px.end
    if end > px.end:
        raise ValueError("cannot simulate an unclosed session")
    payload = json.loads(SNAPSHOT.read_text())
    items = {e["strategy"]["id"]: e for e in payload["strategies"]}
    plans, limits = schedules(px, end)
    outputs, summary = {}, []
    for key, item in items.items():
        strategy = item["strategy"]
        original = [r for r in item["records"] if not r.get("continuation")]
        anchor = pd.Timestamp(original[-1]["date"])
        initial = {h["symbol"]: h["weight"] for h in original[-1]["holdings"] if h["weight"]}
        events = {d: w for d, w in plans[key].items() if anchor < d <= end}
        symbols = (set(initial) | {s for w in events.values() for s in w}) - {CASH}
        daily_prices = {}
        for symbol in sorted(symbols):
            if symbol in px.etf:
                series = px.etf[symbol]
            else:
                path = px.stock_vintage / "histories" / f"{symbol}.csv.gz"
                if not path.exists():
                    raise ValueError(f"no daily history for {symbol}")
                series = read(path).iloc[:, 0]
            daily_prices[symbol] = series
        prices = pd.DataFrame(daily_prices).reindex(px.calendar).loc[anchor:end]
        if prices.index[-1] != end:
            raise ValueError(f"price calendar ends {prices.index[-1]}, expected {end}")
        events, unpriced = route_unpriced_targets(events, prices)
        # Only carry a quote across a short halt; fail rather than fabricate a
        # zero return for an unpriced security or an entire missing session.
        prices = prices.ffill(limit=3)
        rows = continuation(prices, initial, events, float(strategy["disclosures"]["costBps"]))
        historical = [r for r in item["dailyRecords"] if r["date"] <= str(anchor.date())]
        wealth = float(np.prod([1 + (r["netReturn"] or 0) for r in historical]))
        historical_curve = np.cumprod([1 + (r["netReturn"] or 0) for r in historical])
        peak = max(1.0, float(historical_curve.max()))
        for r in rows:
            wealth *= 1 + r["netReturn"]
            peak = max(peak, wealth)
            r.update(wealth=wealth, drawdown=wealth / peak - 1, continuation=True)
        item["records"] = original + rows
        item["dailyRecords"] = historical + [{"date": r["date"], "netReturn": r["netReturn"],
                                                "rebalance": r["rebalance"], "tradingDay": True,
                                                "continuation": True} for r in rows]
        strategy.pop("heldBookExtension", None)
        convention = strategy["disclosures"]["returnConvention"].split(" After the backtest end,")[0].split(" Continuation:")[0]
        strategy["disclosures"]["returnConvention"] = convention + " Continuation: original allocation rules recomputed with updated quarterly SEC inputs and market prices; daily drift and 50 bps on traded security-level turnover."
        fundamental_end = pd.read_csv(OUT / "growth_choices.csv").decision_at.max()[:10]
        strategy.update(dailyThrough=str(end.date()), asOf=str(end.date()),
                        ruleContinuation={"backtestEnd": str(anchor.date()), "through": str(end.date()),
                                          "limitations": limits, "fundamentalsThrough": fundamental_end,
                                          "unpricedAllocationsHeldAsCash": unpriced,
                                          "accounting": "security-level turnover"})
        update_strategy_stats(item)
        old_prices_path = PUBLIC / "prices" / f"{key}.json"
        price_payload = json.loads(old_prices_path.read_text())
        for symbol in symbols:
            old = [r for r in price_payload.get(symbol, []) if r["date"] < str(anchor.date())]
            fresh = [{"date": str(d.date()), "price": float(v)} for d, v in prices[symbol].dropna().items()]
            price_payload[symbol] = old + fresh
        outputs[old_prices_path] = json.dumps(price_payload, separators=(",", ":")) + "\n"
        summary.append({"strategy": key, "through": str(end.date()), "continuation_days": len(rows),
                        "trade_days": sum(r["rebalance"] for r in rows), "growth_of_one": wealth,
                        "unpriced_allocations_held_as_cash": unpriced,
                        "accounting": "security-level turnover"})
        print(summary[-1], flush=True)
    # Validate all strategies before publishing any payload.
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "through": str(end.date()),
                "stock_vintage": px.stock_vintage.name, "etf_vintage": px.etf_vintage.name,
                "limitations": limits, "strategies": summary, "forward_logs_modified": False,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    outputs[OUT / "summary.json"] = json.dumps(manifest, indent=2) + "\n"
    outputs[SNAPSHOT] = json.dumps(payload, separators=(",", ":")) + "\n"
    for path, value in outputs.items():
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(value)
        temporary.replace(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
