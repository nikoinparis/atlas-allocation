#!/usr/bin/env python3
"""Queue item B4: stat arb the way it is actually practised, on daily bars.

Pre-registered in config/stat_arb_residual_registry_v1.json. Steps 45 and 293
tested pairs trading on ETFs and on weekly bars with any-name-to-any-name
pairing, and both lost money at zero cost. This runs the two versions never
tried -- the Avellaneda-Lee residual s-score against an industry factor (T1)
and GGR pairs restricted to the same SIC4 industry (T2) -- on the daily data the
weekly panel is resampled from.

CLAUDE.md section 2 fixes the order: skill screen first (rank IC, decile spread,
decile monotonicity), and a book only for a trial that passes every criterion.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/stat_arb_residual_registry_v1.json"
VINTAGE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1"
FSDS = ROOT / "data/sec_fsds_history_v1"
OUTPUT = ROOT / "evidence/stat_arb_residual_screen_v1"

WINDOW = 60
FORMATION = 252
HORIZON = 5
STEP = 5
MIN_PRICE = 5.0
MIN_PEERS = 5
B_MAX = float(np.exp(-1.0 / 30.0))
BAR = 0.025
PLACEBO_RUNS = 200
BLOCK = 8
REGIMES = {"2012-2019": ("2012", "2019"), "2020": ("2020", "2020"),
           "2021-2022": ("2021", "2022"), "2023-2026": ("2023", "2026"),
           "half 2012-2018": ("2012", "2018"), "half 2019-2026": ("2019", "2026")}


def load_daily() -> pd.DataFrame:
    catalogue = pd.read_csv(VINTAGE / "history_catalogue.csv", dtype={"cik10": str})
    # One series per issuer: the share class with the longest history.
    catalogue = catalogue.sort_values("rows", ascending=False).drop_duplicates("cik10")
    series = {}
    for row in catalogue.itertuples():
        path = VINTAGE / "histories" / f"{row.symbol}.csv.gz"
        if not path.is_file():
            continue
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        series[row.cik10] = frame["adjusted_close"]
    prices = pd.DataFrame(series).sort_index()
    return prices.where(prices > 0)


def load_sic() -> pd.DataFrame:
    """Every (cik10, sic4, available date) from FSDS sub.txt, 10-K/10-Q only."""
    frames = []
    for path in sorted(FSDS.glob("*.zip")):
        try:
            with zipfile.ZipFile(path) as archive, archive.open("sub.txt") as handle:
                sub = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["cik", "sic", "form", "filed"], low_memory=False)
        except Exception:                                    # noqa: BLE001
            continue
        sub = sub[sub.form.astype(str).str.upper().isin(["10-K", "10-Q"])].dropna(subset=["sic"])
        frames.append(sub)
    sic = pd.concat(frames, ignore_index=True)
    sic["cik10"] = sic.cik.astype("int64").astype(str).str.zfill(10)
    sic["sic4"] = sic.sic.astype("int64").astype(str).str.zfill(4)
    # Accepted on `filed`; usable from the next day.
    sic["available"] = pd.to_datetime(sic.filed.astype(str), format="%Y%m%d") + pd.Timedelta(days=1)
    return sic[["cik10", "sic4", "available"]].sort_values("available")


def sic_as_of(sic: pd.DataFrame, when: pd.Timestamp) -> pd.Series:
    known = sic[sic.available <= when]
    return known.groupby("cik10").sic4.last()


def leave_self_out_mean(values: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """values: (T, N) without NaN; groups: (N,). Returns peer means (T, N) and peer counts (N,)."""
    codes, inverse = np.unique(groups, return_inverse=True)
    onehot = np.zeros((len(groups), len(codes)))
    onehot[np.arange(len(groups)), inverse] = 1.0
    sums = values @ onehot                                  # (T, G)
    counts = onehot.sum(axis=0)                             # (G,)
    peers = counts[inverse] - 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        means = (sums[:, inverse] - values) / peers
    return means, peers


def t1_scores(returns: np.ndarray, factor: np.ndarray) -> np.ndarray:
    """Avellaneda-Lee s-score, columnwise. returns, factor: (WINDOW, N)."""
    fm, rm = factor.mean(0), returns.mean(0)
    fc, rc = factor - fm, returns - rm
    var_f = (fc ** 2).sum(0)
    beta = np.where(var_f > 0, (fc * rc).sum(0) / np.where(var_f > 0, var_f, 1), np.nan)
    resid = rc - beta * fc                                   # intercept removed
    x = np.cumsum(resid, axis=0)
    x0, x1 = x[:-1], x[1:]
    x0c, x1c = x0 - x0.mean(0), x1 - x1.mean(0)
    var0 = (x0c ** 2).sum(0)
    b = np.where(var0 > 0, (x0c * x1c).sum(0) / np.where(var0 > 0, var0, 1), np.nan)
    a = x1.mean(0) - b * x0.mean(0)
    e = x1 - (a + b * x0)
    ok = (b > 0) & (b < B_MAX)
    m = np.where(ok, a / (1 - b), np.nan)
    sigma_eq = np.where(ok, np.sqrt(e.var(0, ddof=1) / (1 - b ** 2)), np.nan)
    m_centered = m - np.nanmean(m)
    s = (x[-1] - m_centered) / sigma_eq
    return np.where(ok, s, np.nan)


def build_decisions(prices: pd.DataFrame, sic: pd.DataFrame):
    returns = prices.pct_change(fill_method=None)
    returns = returns.where((returns < 1.0) & (returns > -0.9))
    dates = prices.index
    rows_t1, rows_t2 = [], []
    start = dates.get_indexer([dates[dates >= "2012-01-03"][0]])[0]
    for pos in range(start, len(dates) - HORIZON - 1, STEP):
        when = dates[pos]
        groups_all = sic_as_of(sic, when)
        px = prices.iloc[pos]
        fwd_px = prices.iloc[pos + 1 + HORIZON] / prices.iloc[pos + 1] - 1.0
        fwd_noskip = prices.iloc[pos + HORIZON] / px - 1.0

        # ---------------- T1 -------------------------------------------------
        window = returns.iloc[pos - WINDOW + 1:pos + 1]
        ok = window.notna().all() & (px >= MIN_PRICE) & px.notna()
        names = [c for c in window.columns[ok] if c in groups_all.index]
        if len(names) >= 100:
            sic2 = groups_all.reindex(names).str[:2].to_numpy()
            factor, peers = leave_self_out_mean(window[names].to_numpy(), sic2)
            keep = peers >= MIN_PEERS
            names_k = [n for n, k in zip(names, keep) if k]
            s = t1_scores(window[names_k].to_numpy(), factor[:, keep])
            frame = pd.DataFrame({"cik10": names_k, "sic2": sic2[keep], "score": -s,
                                  "fwd": fwd_px.reindex(names_k).to_numpy(),
                                  "fwd_noskip": fwd_noskip.reindex(names_k).to_numpy()})
            # Industry-relative target: minus the leave-self-out SIC2 mean of names with a forward.
            for col in ("fwd", "fwd_noskip"):
                valid = frame[col].notna()
                g = frame[valid].groupby("sic2")[col]
                total, count = g.transform("sum"), g.transform("count")
                peer = (total - frame.loc[valid, col]) / (count - 1)
                frame.loc[valid, col + "_rel"] = frame.loc[valid, col] - peer.where(count > 1)
            frame["date"] = when
            rows_t1.append(frame.dropna(subset=["score"]))

        # ---------------- T2 -------------------------------------------------
        if pos >= FORMATION:
            block = prices.iloc[pos - FORMATION:pos + 1]
            ok2 = block.notna().all() & (px >= MIN_PRICE)
            names2 = [c for c in block.columns[ok2] if c in groups_all.index]
            sic4 = groups_all.reindex(names2)
            out = []
            for code, members in sic4.groupby(sic4):
                members = list(members.index)
                if len(members) < 2:
                    continue
                norm = (block[members] / block[members].iloc[0]).to_numpy()
                form = norm[:-1]
                sq = (form ** 2).sum(0)
                ssd = sq[:, None] + sq[None, :] - 2 * form.T @ form
                np.fill_diagonal(ssd, np.inf)
                partner = ssd.argmin(1)
                for i, j in enumerate(partner):
                    spread_form = form[:, i] - form[:, j]
                    sd = spread_form.std(ddof=1)
                    if not sd > 0:
                        continue
                    z = (norm[-1, i] - norm[-1, j]) / sd
                    a, b = members[i], members[j]
                    out.append((a, b, code, -z, fwd_px.get(a) - fwd_px.get(b),
                                fwd_noskip.get(a) - fwd_noskip.get(b)))
            if out:
                frame2 = pd.DataFrame(out, columns=["cik10", "partner", "sic4", "score", "fwd_rel",
                                                    "fwd_noskip_rel"])
                frame2["sic2"] = frame2.sic4.str[:2]
                frame2["date"] = when
                rows_t2.append(frame2)
    return pd.concat(rows_t1, ignore_index=True), pd.concat(rows_t2, ignore_index=True)


def per_decision(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    rows = []
    for when, g in frame.dropna(subset=["score", target]).groupby("date"):
        if len(g) < 50:
            continue
        rs, rf = g.score.rank(), g[target].rank()
        ic = float(rs.corr(rf))
        decile = pd.qcut(g.score.rank(method="first"), 10, labels=False)
        means = g[target].groupby(decile).mean()
        mono = float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman"))
        rows.append({"date": when, "n": len(g), "ic": ic,
                     "spread": float(means.iloc[-1] - means.iloc[0]), "mono": mono})
    return pd.DataFrame(rows)


def bootstrap_p(ics: np.ndarray, rng) -> float:
    mean = ics.mean()
    draws = []
    for _ in range(4000):
        starts = rng.integers(0, max(1, len(ics) - BLOCK), size=int(np.ceil(len(ics) / BLOCK)))
        sample = np.concatenate([ics[i:i + BLOCK] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean)
    return float((np.abs(np.array(draws)) >= abs(mean)).mean())


def summarise(daily: pd.DataFrame, rng) -> dict:
    if len(daily) < 16:
        return {"decisions": int(len(daily)), "inconclusive": True}
    ics = daily.ic.to_numpy()
    periods = 252.0 / HORIZON
    spread = float(daily.spread.mean())
    return {"decisions": int(len(daily)), "mean_ic": float(ics.mean()),
            "t_stat": float(ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics)))),
            "bootstrap_p": bootstrap_p(ics, rng),
            "decile_spread_per_5d": spread,
            "decile_spread_annualised_gross": float((1 + spread) ** periods - 1),
            "monotonicity": float(daily.mono.mean()), "median_names": float(daily.n.median())}


def placebo(frame: pd.DataFrame, target: str, rng) -> np.ndarray:
    data = frame.dropna(subset=["score", target])
    groups = [(g.score.rank().to_numpy(), g[target].rank().to_numpy())
              for _, g in data.groupby("date") if len(g) >= 50]
    out = []
    for _ in range(PLACEBO_RUNS):
        out.append(np.mean([np.corrcoef(rng.permutation(s), f)[0, 1] for s, f in groups]))
    return np.array(out)


def leave_out(frame: pd.DataFrame, target: str) -> dict:
    data = frame.dropna(subset=["score", target])
    by_group = {}
    for code in sorted(data.sic2.unique()):
        d = per_decision(data[data.sic2 != code], target)
        by_group[code] = float(d.ic.mean()) if len(d) else float("nan")
    # Name contribution to IC: sum over decisions of standardised rank products.
    parts = []
    for _, g in data.groupby("date"):
        if len(g) < 50:
            continue
        zs = (g.score.rank() - g.score.rank().mean()) / g.score.rank().std()
        zf = (g[target].rank() - g[target].rank().mean()) / g[target].rank().std()
        parts.append(pd.Series((zs * zf).to_numpy() / len(g), index=g.cik10.to_numpy()))
    contribution = pd.concat(parts).groupby(level=0).sum().sort_values(ascending=False)
    top = list(contribution.index[:10])
    d = per_decision(data[~data.cik10.isin(top)], target)
    worst = min(by_group, key=lambda k: by_group[k])
    return {"min_leave_one_sic2_out_ic": by_group[worst], "worst_sic2_removed": worst,
            "ic_without_top10_names": float(d.ic.mean()), "top10_names": top}


def evaluate(name: str, frame: pd.DataFrame, target: str, diag_target: str, rng) -> dict:
    daily = per_decision(frame, target)
    full = summarise(daily, rng)
    regimes = {}
    for label, (a, b) in REGIMES.items():
        sub = daily[(daily.date >= f"{a}-01-01") & (daily.date <= f"{b}-12-31")]
        regimes[label] = summarise(sub, rng)
    plac = placebo(frame, target, rng)
    loo = leave_out(frame, target)
    noskip = summarise(per_decision(frame, diag_target), rng)
    halves = [regimes["half 2012-2018"], regimes["half 2019-2026"]]
    criteria = {
        "full_ic_positive_and_p_below_bar": full["mean_ic"] > 0 and full["bootstrap_p"] < BAR,
        "full_monotonicity_above_0.5": full["monotonicity"] > 0.5,
        "both_halves_ic_and_monotonicity_positive": all(
            h.get("mean_ic", -1) > 0 and h.get("monotonicity", -1) > 0 for h in halves),
        "beats_placebo_95th": full["mean_ic"] > float(np.percentile(plac, 95)),
        "min_leave_one_sic2_out_ic_positive": loo["min_leave_one_sic2_out_ic"] > 0,
    }
    return {"trial": name, "target": target, "full": full, "regimes": regimes,
            "placebo_mean": float(plac.mean()), "placebo_p95": float(np.percentile(plac, 95)),
            "leave_out": loo, "diagnostic_no_skip": noskip, "criteria": criteria,
            "screen_passes": all(criteria.values())}


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20261011)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = load_daily()
    sic = load_sic()
    print(f"daily panel: {prices.shape[1]} issuers, {prices.index[0].date()} to {prices.index[-1].date()}")
    t1, t2 = build_decisions(prices, sic)
    t1.to_csv(OUTPUT / "t1_scores.csv.gz", index=False)
    t2.to_csv(OUTPUT / "t2_scores.csv.gz", index=False)
    results = [evaluate("T1 Avellaneda-Lee s-score", t1, "fwd_rel", "fwd_noskip_rel", rng),
               evaluate("T2 same-SIC4 pairs", t2, "fwd_rel", "fwd_noskip_rel", rng)]
    for r in results:
        f = r["full"]
        print(f"\n== {r['trial']}  (target {r['target']}, skip-1, {HORIZON}-day)")
        print(f"  decisions {f['decisions']}, median names {f['median_names']:.0f}")
        print(f"  mean IC {f['mean_ic']:+.4f}  t {f['t_stat']:+.2f}  p {f['bootstrap_p']:.4f}  "
              f"decile spread/5d {f['decile_spread_per_5d']:+.4%} (gross ann. {f['decile_spread_annualised_gross']:+.2%})  "
              f"monotonicity {f['monotonicity']:+.3f}")
        print(f"  placebo mean {r['placebo_mean']:+.4f}  p95 {r['placebo_p95']:+.4f}")
        lo = r["leave_out"]
        print(f"  min leave-one-SIC2-out IC {lo['min_leave_one_sic2_out_ic']:+.4f} (drop {lo['worst_sic2_removed']}), "
              f"without top-10 names {lo['ic_without_top10_names']:+.4f}")
        d = r["diagnostic_no_skip"]
        print(f"  diagnostic no-skip: IC {d['mean_ic']:+.4f}  spread/5d {d['decile_spread_per_5d']:+.4%}  mono {d['monotonicity']:+.3f}")
        for label, g in r["regimes"].items():
            if g.get("inconclusive"):
                continue
            print(f"  {label:16s} n={g['decisions']:4d} IC {g['mean_ic']:+.4f} p {g['bootstrap_p']:.3f} "
                  f"spread/5d {g['decile_spread_per_5d']:+.4%} mono {g['monotonicity']:+.3f}")
        for k, v in r["criteria"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print(f"  SCREEN {'PASSES' if r['screen_passes'] else 'FAILS'}")
    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)), "results": results,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
