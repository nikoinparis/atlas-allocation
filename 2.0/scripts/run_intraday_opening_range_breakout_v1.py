#!/usr/bin/env python3
"""Test the opening-range breakout family on free hourly bars.

Registered in config/intraday_opening_range_breakout_v1.json before any result
existed. The design notes there explain why the opening range is 60 minutes:
that is the finest resolution with more than 60 sessions of free history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/intraday_opening_range_breakout_v1.json"
UNIVERSE = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/intraday_opening_range_breakout_v1"
COST_CASES = [0.0, 1.0, 2.0, 5.0, 10.0]
SESSIONS_PER_YEAR = 252


def fetch(symbols: list[str], interval: str, period: str) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = yf.download(
            symbol, period=period, interval=interval, auto_adjust=False,
            progress=False, threads=False, prepost=False,
        )
        if frame.empty:
            continue
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.tz_convert("America/New_York")
        out[symbol] = frame
        print(f"  {symbol} {interval}: {len(frame)} bars {frame.index.min()} -> {frame.index.max()}", flush=True)
    return out


def sessions(frame: pd.DataFrame, open_bars: int) -> pd.DataFrame:
    """One row per session: opening-range stats and the rest-of-day return."""
    frame = frame.between_time("09:30", "16:00")
    rows = []
    for day, group in frame.groupby(frame.index.date):
        group = group.sort_index()
        if len(group) < open_bars + 2:
            continue
        opening = group.iloc[:open_bars]
        rest = group.iloc[open_bars:]
        entry = float(opening["Close"].iloc[-1])
        close = float(rest["Close"].iloc[-1])
        if not np.isfinite(entry) or not np.isfinite(close) or entry <= 0:
            continue
        or_high = float(opening["High"].max())
        or_low = float(opening["Low"].min())
        or_open = float(opening["Open"].iloc[0])
        # First touch of either opening-range extreme after the range closes.
        touch, touch_price = 0, entry
        for _, bar in rest.iterrows():
            up = float(bar["High"]) >= or_high
            down = float(bar["Low"]) <= or_low
            if up and down:      # both inside one bar: unresolvable at this resolution
                touch, touch_price = 0, entry
                break
            if up:
                touch, touch_price = 1, or_high
                break
            if down:
                touch, touch_price = -1, or_low
                break
        rows.append({
            "date": pd.Timestamp(day),
            "or_return": entry / or_open - 1.0 if or_open > 0 else np.nan,
            "rest_return": close / entry - 1.0,
            "touch": touch,
            "touch_return": close / touch_price - 1.0 if touch_price > 0 else np.nan,
        })
    out = pd.DataFrame(rows).set_index("date").sort_index()
    return out.dropna(subset=["or_return", "rest_return"])


def variant_positions(table: pd.DataFrame, variant: str) -> tuple[pd.Series, pd.Series]:
    """Returns (position, per-session gross return) for one pre-declared variant."""
    if variant == "orb_momentum":
        position = np.sign(table["or_return"])
        gross = position * table["rest_return"]
    elif variant == "orb_long_only":
        position = (table["or_return"] > 0).astype(float)
        gross = position * table["rest_return"]
    elif variant == "orb_breakout":
        position = table["touch"].astype(float)
        gross = position * table["touch_return"].fillna(0.0)
    else:
        raise ValueError(variant)
    return position.astype(float), gross.astype(float).fillna(0.0)


def net_of_costs(gross: pd.Series, position: pd.Series, bps: float) -> pd.Series:
    """Every non-flat session is a full round trip: in at entry, out at the close."""
    turns = (position.abs() > 0).astype(float)
    return gross - turns * (bps / 10000.0)


def metrics(returns: pd.Series) -> dict[str, float]:
    r = returns.dropna()
    if r.empty:
        return {"sessions": 0}
    wealth = (1.0 + r).cumprod()
    years = len(r) / SESSIONS_PER_YEAR
    peak = wealth.cummax()
    drawdown = wealth / peak - 1.0
    vol = float(r.std(ddof=1)) * np.sqrt(SESSIONS_PER_YEAR)
    cagr = float(wealth.iloc[-1]) ** (1.0 / years) - 1.0 if years > 0 else np.nan
    return {
        "sessions": int(len(r)),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "cagr": cagr,
        "annual_volatility": vol,
        "sharpe_zero_rf": float(r.mean() / r.std(ddof=1) * np.sqrt(SESSIONS_PER_YEAR)) if r.std(ddof=1) > 0 else 0.0,
        "max_drawdown": float(drawdown.min()),
        "hit_rate": float((r > 0).mean()),
        "mean_session_bps": float(r.mean() * 10000.0),
        "traded_share": float((r != 0).mean()),
    }


def block_bootstrap(returns: pd.Series, block: int, draws: int, seed: int) -> dict[str, float]:
    r = returns.dropna().to_numpy()
    if len(r) < block * 3:
        return {}
    rng = np.random.default_rng(seed)
    starts = len(r) - block
    blocks = int(np.ceil(len(r) / block))
    means = np.empty(draws)
    for i in range(draws):
        idx = rng.integers(0, starts, size=blocks)
        sample = np.concatenate([r[s:s + block] for s in idx])[:len(r)]
        means[i] = sample.mean()
    return {
        "mean_session_bps": float(r.mean() * 10000.0),
        "p_value_mean_le_zero": float((means <= 0).mean()),
        "ci_low_bps": float(np.percentile(means, 2.5) * 10000.0),
        "ci_high_bps": float(np.percentile(means, 97.5) * 10000.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260901)
    args = parser.parse_args()

    universe = sorted(set(json.loads(UNIVERSE.read_text())["symbols"]) | {"DIA"})
    print(f"universe: {len(universe)} symbols", flush=True)

    print("fetching 1h bars", flush=True)
    hourly = fetch(universe, "1h", "730d")
    print("fetching 5m bars for the resolution check", flush=True)
    fine = fetch(["SPY", "QQQ", "IWM", "DIA"], "5m", "60d")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    per_symbol_sessions = {s: sessions(f, open_bars=1) for s, f in hourly.items()}
    per_symbol_sessions = {s: t for s, t in per_symbol_sessions.items() if len(t) >= 200}
    print(f"symbols with >=200 usable sessions: {len(per_symbol_sessions)}", flush=True)

    rows = []
    sleeve_returns: dict[str, pd.DataFrame] = {}
    for variant in ["orb_momentum", "orb_long_only", "orb_breakout"]:
        per_symbol_net: dict[str, pd.Series] = {}
        for symbol, table in per_symbol_sessions.items():
            position, gross = variant_positions(table, variant)
            for bps in COST_CASES:
                net = net_of_costs(gross, position, bps)
                record = {"variant": variant, "symbol": symbol, "cost_bps": bps}
                record.update(metrics(net))
                rows.append(record)
                if bps == 2.0:
                    per_symbol_net[symbol] = net
        panel = pd.DataFrame(per_symbol_net).sort_index()
        sleeve_returns[variant] = panel

    detail = pd.DataFrame(rows)
    detail.to_csv(OUTPUT / "per_symbol_metrics.csv", index=False)

    # Equal-weight sleeve across instruments, recomputed at every cost case.
    sleeve_rows = []
    sleeve_paths: dict[str, pd.Series] = {}
    for variant in ["orb_momentum", "orb_long_only", "orb_breakout"]:
        gross_panel, position_panel = {}, {}
        for symbol, table in per_symbol_sessions.items():
            position, gross = variant_positions(table, variant)
            gross_panel[symbol] = gross
            position_panel[symbol] = position
        g = pd.DataFrame(gross_panel).sort_index()
        p = pd.DataFrame(position_panel).sort_index()
        for bps in COST_CASES:
            net = (g - (p.abs() > 0).astype(float) * (bps / 10000.0)).mean(axis=1)
            record = {"variant": variant, "cost_bps": bps}
            record.update(metrics(net))
            record.update({f"bootstrap_{k}": v for k, v in block_bootstrap(net, 10, args.draws, args.seed).items()})
            sleeve_rows.append(record)
            if bps == 2.0:
                sleeve_paths[variant] = net
        # Controls, all at the 2 bps primary case.
        for control in ["sign_shuffled", "random_sign"]:
            if control == "sign_shuffled":
                shuffled_p = p.apply(lambda col: pd.Series(rng.permutation(col.to_numpy()), index=col.index))
            else:
                shuffled_p = pd.DataFrame(
                    rng.choice([-1.0, 1.0], size=p.shape), index=p.index, columns=p.columns
                ) * (p.abs() > 0).astype(float)
            raw = g / p.replace(0.0, np.nan)          # per-session underlying move
            ctrl_gross = (shuffled_p * raw).fillna(0.0)
            ctrl_net = (ctrl_gross - (shuffled_p.abs() > 0).astype(float) * (2.0 / 10000.0)).mean(axis=1)
            record = {"variant": f"{variant}__control_{control}", "cost_bps": 2.0}
            record.update(metrics(ctrl_net))
            sleeve_rows.append(record)
        # Leave one instrument out, primary cost case.
        for dropped in per_symbol_sessions:
            keep = [c for c in g.columns if c != dropped]
            net = (g[keep] - (p[keep].abs() > 0).astype(float) * (2.0 / 10000.0)).mean(axis=1)
            record = {"variant": f"{variant}__loo_drop_{dropped}", "cost_bps": 2.0}
            record.update(metrics(net))
            sleeve_rows.append(record)

    sleeve = pd.DataFrame(sleeve_rows)
    sleeve.to_csv(OUTPUT / "sleeve_metrics.csv", index=False)

    # Calendar-year split at the primary cost case.
    year_rows = []
    for variant, path in sleeve_paths.items():
        for year, group in path.groupby(path.index.year):
            record = {"variant": variant, "year": int(year)}
            record.update(metrics(group))
            year_rows.append(record)
    pd.DataFrame(year_rows).to_csv(OUTPUT / "calendar_years.csv", index=False)

    # 5-minute resolution check on the overlapping sessions.
    fine_rows = []
    for symbol, frame in fine.items():
        table = sessions(frame, open_bars=6)   # 6 five-minute bars = the 09:30-10:00 range
        if len(table) < 30:
            continue
        for variant in ["orb_momentum", "orb_long_only", "orb_breakout"]:
            position, gross = variant_positions(table, variant)
            net = net_of_costs(gross, position, 2.0)
            record = {"variant": variant, "symbol": symbol, "resolution": "5m_30min_range"}
            record.update(metrics(net))
            fine_rows.append(record)
    pd.DataFrame(fine_rows).to_csv(OUTPUT / "five_minute_resolution_check.csv", index=False)

    for variant, path in sleeve_paths.items():
        path.rename("net_return").to_frame().to_csv(OUTPUT / f"session_path__{variant}__2bps.csv")

    summary = {
        "experiment": "intraday_opening_range_breakout_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "instruments_used": sorted(per_symbol_sessions),
        "sessions_per_instrument": {s: int(len(t)) for s, t in per_symbol_sessions.items()},
        "sample_start": str(min(t.index.min() for t in per_symbol_sessions.values()).date()),
        "sample_end": str(max(t.index.max() for t in per_symbol_sessions.values()).date()),
        "primary_cost_bps": 2.0,
        "live_trading_enabled": False,
        "promotion_authorized": False,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
