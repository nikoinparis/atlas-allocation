#!/usr/bin/env python3
"""Pre-registered daily OHLCV alpha tournament on the causal SEC universe.

Features use only observations dated on or before the quarterly decision date.
The next quarter is purged between selection and the four-decision retrospective
holdout.  Feature direction and family representatives are chosen on selection
data only; holdout metrics are descriptive and cannot promote a strategy.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/future_alpha_program_v1.json"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
PANEL = ROOT / "data/sec_broad_research_panel_v2/panel.csv.gz"
WEEKLY = ROOT / "data/sec_broad_research_panel_v2/weekly_returns.csv.gz"
OUTPUT = ROOT / "evidence/daily_ohlcv_alpha_zoo_v1"


FEATURE_FAMILIES = {
    "ret_5": "momentum", "ret_10": "momentum", "ret_21": "momentum",
    "ret_63": "momentum", "ret_126": "momentum", "ret_252": "momentum",
    "momentum_252_21": "momentum", "momentum_126_21": "momentum",
    "reversal_1": "reversal", "reversal_5": "reversal", "reversal_21": "reversal",
    "ma_distance_20": "trend", "ma_distance_60": "trend", "ma_distance_200": "trend",
    "trend_consistency_63": "trend", "near_252_high": "trend", "drawdown_252": "trend",
    "vol_21": "volatility", "vol_63": "volatility", "downside_vol_63": "volatility",
    "max_return_63": "volatility", "return_skew_63": "volatility",
    "range_10": "range", "range_21": "range", "close_location_21": "range",
    "gap_1": "gap", "gap_5": "gap", "intraday_5": "gap",
    "volume_ratio_5_63": "volume", "volume_shock_21": "volume",
    "dollar_volume_21": "liquidity", "amihud_21": "liquidity",
    "price_volume_corr_21": "price_volume", "price_volume_corr_63": "price_volume",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_ratio(a: float, b: float) -> float:
    return float(a / b - 1.0) if np.isfinite(a) and np.isfinite(b) and b != 0 else np.nan


def window_mean(values: pd.Series, count: int) -> float:
    block = values.dropna().tail(count)
    return float(block.mean()) if len(block) >= max(3, count // 2) else np.nan


def compute_features(raw: pd.DataFrame, decision: pd.Timestamp) -> dict[str, float] | None:
    date_col = "Date" if "Date" in raw else "date" if "date" in raw else raw.columns[0]
    data = raw.copy()
    data[date_col] = pd.to_datetime(data[date_col], utc=True, errors="coerce")
    data = data[data[date_col] <= decision].sort_values(date_col).tail(320)
    close_col = "Adj Close" if "Adj Close" in data else "adjClose" if "adjClose" in data else "Close" if "Close" in data else "close"
    close = pd.to_numeric(data[close_col], errors="coerce")
    if close.notna().sum() < 80:
        return None
    close = close.ffill()
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    volume_col = "Volume" if "Volume" in data else "adjVolume" if "adjVolume" in data else "volume"
    volume = pd.to_numeric(data[volume_col], errors="coerce").replace(0, np.nan)
    open_ = pd.to_numeric(data["Open"] if "Open" in data else data["open"], errors="coerce")
    high = pd.to_numeric(data["High"] if "High" in data else data["high"], errors="coerce")
    low = pd.to_numeric(data["Low"] if "Low" in data else data["low"], errors="coerce")
    unadjusted_close = pd.to_numeric(data["Close"] if "Close" in data else data["close"], errors="coerce")
    latest = float(close.iloc[-1])

    def lag_return(days: int) -> float:
        return safe_ratio(latest, float(close.iloc[-days - 1])) if len(close) > days else np.nan

    result = {f"ret_{days}": lag_return(days) for days in (5, 10, 21, 63, 126, 252)}
    result.update({
        "momentum_252_21": safe_ratio(float(close.iloc[-22]), float(close.iloc[-253])) if len(close) > 252 else np.nan,
        "momentum_126_21": safe_ratio(float(close.iloc[-22]), float(close.iloc[-127])) if len(close) > 126 else np.nan,
        "reversal_1": -lag_return(1), "reversal_5": -lag_return(5), "reversal_21": -lag_return(21),
        "ma_distance_20": safe_ratio(latest, window_mean(close, 20)),
        "ma_distance_60": safe_ratio(latest, window_mean(close, 60)),
        "ma_distance_200": safe_ratio(latest, window_mean(close, 200)),
        "trend_consistency_63": float((returns.tail(63) > 0).mean()) if returns.tail(63).notna().sum() >= 40 else np.nan,
        "near_252_high": safe_ratio(latest, float(close.tail(252).max())),
        "drawdown_252": safe_ratio(latest, float(close.tail(252).cummax().iloc[-1])),
        "vol_21": float(returns.tail(21).std(ddof=1)),
        "vol_63": float(returns.tail(63).std(ddof=1)),
        "downside_vol_63": float(returns.tail(63).clip(upper=0).std(ddof=1)),
        "max_return_63": float(returns.tail(63).max()),
        "return_skew_63": float(returns.tail(63).skew()),
    })
    intraday_range = (high - low) / unadjusted_close.shift(1).replace(0, np.nan)
    close_location = (unadjusted_close - low) / (high - low).replace(0, np.nan)
    gap = open_ / unadjusted_close.shift(1).replace(0, np.nan) - 1.0
    intraday = unadjusted_close / open_.replace(0, np.nan) - 1.0
    result.update({
        "range_10": window_mean(intraday_range, 10), "range_21": window_mean(intraday_range, 21),
        "close_location_21": window_mean(close_location, 21),
        "gap_1": float(gap.iloc[-1]) if len(gap) else np.nan, "gap_5": window_mean(gap, 5),
        "intraday_5": window_mean(intraday, 5),
        "volume_ratio_5_63": safe_ratio(window_mean(volume, 5), window_mean(volume, 63)),
        "volume_shock_21": safe_ratio(float(volume.iloc[-1]), window_mean(volume, 21)),
        "dollar_volume_21": float((close * volume).tail(21).mean()),
        "amihud_21": float((returns.abs() / (close * volume).replace(0, np.nan)).tail(21).mean()),
        "price_volume_corr_21": float(returns.tail(21).corr(volume.pct_change(fill_method=None).tail(21))),
        "price_volume_corr_63": float(returns.tail(63).corr(volume.pct_change(fill_method=None).tail(63))),
    })
    return result


def rank_ic(frame: pd.DataFrame, feature: str) -> float:
    usable = frame[[feature, "future_sector_relative_return"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(usable) < 30:
        return np.nan
    return float(usable[feature].rank(pct=True).corr(usable.future_sector_relative_return.rank(pct=True)))


def sign_flip_p(values: list[float]) -> float:
    sample = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if len(sample) < 4:
        return 1.0
    observed = abs(float(sample.mean()))
    hits = 0
    total = 1 << len(sample)
    for mask in range(total):
        signs = np.array([1.0 if mask & (1 << bit) else -1.0 for bit in range(len(sample))])
        hits += int(abs(float((sample * signs).mean())) >= observed - 1e-15)
    return hits / total


def bh_flags(p_values: dict[str, float], alpha: float = 0.10) -> set[str]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    cutoff = -1
    for index, (_, value) in enumerate(ordered, 1):
        if value <= alpha * index / len(ordered):
            cutoff = index
    return {name for name, _ in ordered[:cutoff]} if cutoff > 0 else set()


def choose_names(block: pd.DataFrame, score: pd.Series, breadth: int, sector_cap: int) -> list[str]:
    ranked = block.assign(_score=score).dropna(subset=["_score"]).sort_values(["_score", "cik10"], ascending=[False, True])
    chosen, counts = [], {}
    for row in ranked.itertuples():
        sector = str(row.sector)
        if counts.get(sector, 0) >= sector_cap:
            continue
        chosen.append(str(row.cik10)); counts[sector] = counts.get(sector, 0) + 1
        if len(chosen) == breadth:
            break
    return chosen


def portfolio_path(weights: dict[pd.Timestamp, dict[str, float]], weekly: pd.DataFrame, cost_bps: float) -> pd.Series:
    dates = sorted(weights)
    returns, prior = {}, {}
    for stamp in weekly.index:
        eligible = [date for date in dates if date <= stamp]
        target = weights[max(eligible)] if eligible else {}
        gross = sum(weight * float(weekly.at[stamp, cik]) for cik, weight in target.items() if cik in weekly and pd.notna(weekly.at[stamp, cik]))
        gross_traded = sum(abs(target.get(cik, 0.0) - prior.get(cik, 0.0)) for cik in set(target) | set(prior))
        turnover = gross_traded if not prior or not target else gross_traded / 2.0
        returns[stamp] = gross - turnover * cost_bps / 10000.0
        prior = target
    return pd.Series(returns, dtype=float)


def metrics(path: pd.Series) -> dict[str, float]:
    data = path.dropna()
    wealth = (1 + data).cumprod()
    years = len(data) / 52.0
    cagr = float(wealth.iloc[-1] ** (1 / years) - 1) if years > 0 and wealth.iloc[-1] > 0 else np.nan
    vol = float(data.std(ddof=1) * math.sqrt(52))
    sharpe = float(data.mean() * 52 / vol) if vol > 0 else np.nan
    drawdown = wealth / wealth.cummax() - 1
    return {"weeks": int(len(data)), "cagr": cagr, "sharpe_zero_rf": sharpe, "max_drawdown": float(drawdown.min()), "total_return": float(wealth.iloc[-1] - 1)}


def main() -> int:
    config = json.loads(CONFIG.read_text())
    inventory = pd.read_csv(INVENTORY, dtype={"cik10": str})
    panel = pd.read_csv(PANEL, dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
    decisions = sorted(panel.decision_at.unique())
    selection, purge, holdout = decisions[:9], decisions[9], decisions[10:]

    rows = []
    for index, item in enumerate(inventory.itertuples(), 1):
        path = Path(item.path)
        if not path.exists() or sha256(path) != item.sha256:
            continue
        try:
            raw = pd.read_csv(path)
        except Exception:
            continue
        for decision in decisions:
            calculated = compute_features(raw, pd.Timestamp(decision))
            if calculated:
                rows.append({"decision_at": decision, "cik10": str(item.cik10), **calculated})
        if index % 500 == 0:
            print(f"feature histories {index}/{len(inventory)}", flush=True)

    features = pd.DataFrame(rows)
    merged = panel[["decision_at", "cik10", "sector", "future_sector_relative_return"]].merge(
        features, on=["decision_at", "cik10"], how="left", validate="one_to_one"
    )
    per_decision, summary = [], {}
    selection_set, holdout_set = set(selection), set(holdout)
    for feature, family in FEATURE_FAMILIES.items():
        values = []
        for decision, block in merged.groupby("decision_at"):
            neutral = block[feature] - block.groupby("sector")[feature].transform("median")
            test = block.assign(**{feature: neutral})
            ic = rank_ic(test, feature)
            values.append((decision, ic))
            per_decision.append({"decision_at": decision, "feature": feature, "family": family, "rank_ic": ic})
        selected = [ic for date, ic in values if date in selection_set]
        held = [ic for date, ic in values if date in holdout_set]
        direction = 1 if np.nanmean(selected) >= 0 else -1
        summary[feature] = {
            "family": family, "direction": direction,
            "selection_mean_ic": float(direction * np.nanmean(selected)),
            "selection_positive_share": float(np.nanmean(np.asarray(selected) * direction > 0)),
            "selection_sign_flip_p": sign_flip_p(selected),
            "holdout_mean_ic": float(direction * np.nanmean(held)),
            "holdout_positive_share": float(np.nanmean(np.asarray(held) * direction > 0)),
            "nonmissing_share": float(merged[feature].notna().mean()),
        }
    discoveries = bh_flags({name: row["selection_sign_flip_p"] for name, row in summary.items()})
    for name in summary:
        summary[name]["selection_bh_10pct"] = name in discoveries

    representatives = {}
    for family in sorted(set(FEATURE_FAMILIES.values())):
        names = [name for name, row in summary.items() if row["family"] == family and row["nonmissing_share"] >= 0.70]
        if names:
            representatives[family] = max(names, key=lambda name: summary[name]["selection_mean_ic"])

    composite = pd.Series(0.0, index=merged.index)
    count = pd.Series(0, index=merged.index, dtype=int)
    for feature in representatives.values():
        signed = merged.groupby("decision_at")[feature].rank(pct=True) * summary[feature]["direction"]
        composite = composite.add(signed.fillna(0.0)); count = count.add(signed.notna().astype(int))
    merged["composite"] = composite / count.replace(0, np.nan)

    weights = {}
    breadth = int(config["portfolio"]["breadth"]); sector_cap = int(config["portfolio"]["maximum_sector_names"])
    for decision, block in merged.groupby("decision_at"):
        execution = pd.to_datetime(block.execution_at.iloc[0], utc=True) if "execution_at" in block else decision + pd.Timedelta(weeks=1)
        chosen = choose_names(block, block.composite, breadth, sector_cap)
        weights[execution] = {cik: 1 / len(chosen) for cik in chosen} if chosen else {}
    weekly = pd.read_csv(WEEKLY, index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    first_holdout_execution = pd.Timestamp(holdout[0]) + pd.Timedelta(weeks=1)
    paths, path_metrics = {}, {}
    for cost in config["portfolio"]["cost_bps_one_way"]:
        path = portfolio_path(weights, weekly, float(cost))
        paths[str(cost)] = path
        path_metrics[str(cost)] = {
            "full": metrics(path[path.index >= pd.Timestamp(selection[0]) + pd.Timedelta(weeks=1)]),
            "retrospective_holdout": metrics(path[path.index >= first_holdout_execution]),
        }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUTPUT / "features.csv.gz", index=False, compression="gzip")
    pd.DataFrame(per_decision).to_csv(OUTPUT / "rank_ic_by_decision.csv", index=False)
    pd.DataFrame({f"net_return_{cost}bps": path for cost, path in paths.items()}).to_csv(OUTPUT / "weekly_paths.csv")
    holdings = [{"execution_at": date, "cik10": cik, "weight": weight} for date, row in weights.items() for cik, weight in row.items()]
    pd.DataFrame(holdings).to_csv(OUTPUT / "holdings.csv", index=False)
    result = {
        "experiment": "daily_ohlcv_alpha_zoo_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_inventory_sha256": sha256(INVENTORY), "config_sha256": sha256(CONFIG),
        "issuer_histories": int(inventory.cik10.nunique()), "feature_rows": int(len(features)),
        "features_tested": len(FEATURE_FAMILIES), "selection_decisions": [str(x) for x in selection],
        "purged_decision": str(purge), "retrospective_holdout_decisions": [str(x) for x in holdout],
        "feature_results": summary, "bh_discoveries": sorted(discoveries),
        "family_representatives_selected_without_holdout": representatives,
        "portfolio_metrics": path_metrics,
        "status": "retrospective_research_complete_no_promotion",
        "strategy_promotion_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Daily OHLCV alpha zoo v1\n\n"
        f"Tested **{len(FEATURE_FAMILIES)}** pre-registered features across **{len(inventory):,}** hash-verified issuer histories. "
        f"Selection chose one representative per family before opening a four-decision retrospective holdout; the intervening decision was purged. "
        f"Benjamini-Hochberg discoveries at 10%: **{len(discoveries)}**. This remains retrospective research and cannot promote a strategy.\n"
    )
    print(json.dumps({"features_tested": len(FEATURE_FAMILIES), "bh_discoveries": sorted(discoveries), "representatives": representatives, "portfolio_metrics": path_metrics, "live_trading_enabled": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
