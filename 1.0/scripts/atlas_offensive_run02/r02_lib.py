"""Atlas Offensive R02 shared machinery.

Native PBI sub-state construction, per-instrument cost paths, episode
segmentation, per-episode stops, and return-first metrics. Everything follows
docs/research/atlas_offensive/run02_preregistration.md — no parameter here may
drift from that file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for sub in ("", "moonshot1_discovery", "frontier2_overlays", "confirm1_alpha_pbi"):
    p = str(SCRIPTS_DIR / sub) if sub else str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, CheckpointModifier  # noqa: E402
from path1_path3_research_utils import DATA, OFFENSE  # noqa: E402
from confirm_candidates import pbi_latched_multiplier  # noqa: E402
from moonshot_features import build_feature_panel, panic_improvement_composite  # noqa: E402

OUT_DIR = DATA / "research" / "atlas_offensive_run02"
COST_LIBRARY = DATA / "research" / "atlas_offensive_cost_library.csv"
TRIAL_REGISTRY = DATA / "research" / "atlas_offensive_trial_registry.csv"

# Dev-window rule (pre-registered): keep path rows whose forward week completes
# by 2025-12-31, i.e. Date <= 2025-12-24 for Friday-indexed weekly rows.
DEV_LAST_DECISION = pd.Timestamp("2025-12-24")

SEED = 20260721
GRADE_RATIO = 1.15 / 1.30  # locked conviction grading for 2-of-3 fires
OFFENSE_BASES = [0.25, 0.40, 0.55, 0.70]
STOP_LEVELS = [0.03, 0.05, 0.07]
EPISODE_GAP_WEEKS = 13
EPISODE_TAIL_WEEKS = 4
WEEKS = 52


def load_cost_vector(multiplier: float = 1.0) -> pd.Series:
    lib = pd.read_csv(COST_LIBRARY).set_index("ticker")
    return pd.to_numeric(lib["one_way_cost_bps"], errors="coerce") * multiplier


def per_instrument_path(weights: pd.DataFrame, next_week_returns: pd.DataFrame, cost_bps_vec: pd.Series) -> pd.DataFrame:
    """Canonical production path conventions with per-instrument one-way costs."""
    common = weights.index.intersection(next_week_returns.index)
    cols = [c for c in weights.columns if c in next_week_returns.columns]
    w = weights.reindex(index=common, columns=cols).fillna(0.0)
    r = next_week_returns.reindex(index=common, columns=cols).fillna(0.0)
    gross = (w * r).sum(axis=1)
    dw = w.diff().abs()
    cvec = cost_bps_vec.reindex(cols)
    if cvec.isna().any():
        raise ValueError(f"Cost library missing tickers: {list(cvec[cvec.isna()].index)}")
    cost = (0.5 * dw).mul(cvec / 1e4, axis=1).sum(axis=1)
    cost.iloc[0] = 0.0
    turnover = 0.5 * dw.sum(axis=1)
    turnover.iloc[0] = np.nan
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame({"Date": common, "gross_return": gross.values, "net_return": net.values,
                         "turnover": turnover.values, "cost": cost.values,
                         "wealth": wealth.values, "drawdown": drawdown.values})


def dev_window(path: pd.DataFrame) -> pd.DataFrame:
    out = path.copy()
    out["Date"] = pd.to_datetime(out["Date"])
    return out[out["Date"] <= DEV_LAST_DECISION].reset_index(drop=True)


class R02Machinery:
    """Loads the base stack once and exposes fire/episode structure."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.wrapper = AllocatorCheckpointWrapper()
        self.index = self.wrapper.index
        self.base_weights = self.wrapper.final_weights.copy()
        self.nwr = self.wrapper.next_week_returns
        self.states = self.wrapper.states["market_state"].astype(str).reindex(self.index).fillna("neutral_mixed")
        self.mult = pbi_latched_multiplier(self.index, self.states, self.warnings)
        self.fire_mask = self.mult > 1.0
        self.grade3 = self.mult == 1.30  # 3-of-3 conviction
        feats = build_feature_panel(self.index, self.warnings)
        self.feats = feats
        self.pbi = panic_improvement_composite(feats)
        self.latched = feats["market_drawdown"].rolling(13, min_periods=1).min() <= -0.10
        self.offense_cols = [c for c in self.base_weights.columns if c in OFFENSE]
        self.offense_share = self.base_weights[self.offense_cols].sum(axis=1)
        self.episodes = self._episodes(self.index[self.fire_mask])

    def _episodes(self, fire_dates: pd.Index) -> list[dict]:
        if len(fire_dates) == 0:
            return []
        gaps = fire_dates.to_series().diff().dt.days.fillna(1e9)
        eid = (gaps > EPISODE_GAP_WEEKS * 7).cumsum()
        eps = []
        pos = {d: i for i, d in enumerate(self.index)}
        for _, grp in fire_dates.to_series().groupby(eid):
            dates = list(grp.index)
            last_pos = pos[dates[-1]]
            tail_end = self.index[min(last_pos + EPISODE_TAIL_WEEKS, len(self.index) - 1)]
            eps.append({"label": f"{dates[0].year}-{dates[0].month:02d}", "entry": dates[0],
                        "last_fire": dates[-1], "window_end": min(tail_end, DEV_LAST_DECISION),
                        "fires": dates})
        return eps

    # ── Native sub-state weight construction ────────────────────────────────
    def native_weights(self, base_offense: float, active_fires: set[pd.Timestamp]) -> pd.DataFrame:
        w = self.base_weights.copy()
        for d in self.index[self.fire_mask]:
            if d not in active_fires:
                continue
            o = float(self.offense_share.loc[d])
            target = base_offense if bool(self.grade3.loc[d]) else base_offense * GRADE_RATIO
            target = max(target, o)  # never reduce offense vs base
            if o <= 1e-9 or target >= 0.999:
                continue
            row = w.loc[d].copy()
            non_off = [c for c in w.columns if c not in self.offense_cols]
            row[self.offense_cols] = row[self.offense_cols] * (target / o)
            other = float(w.loc[d, non_off].sum())
            if other > 1e-9:
                row[non_off] = row[non_off] * ((1.0 - target) / other)
            w.loc[d] = row
        return w

    def run_variant(self, base_offense: float, stop_level: float | None, cost_vec: pd.Series) -> dict:
        """Build the variant with causal per-episode stops (forward-sequential)."""
        active = set(self.index[self.fire_mask])
        stop_log = []
        pos = {d: i for i, d in enumerate(self.index)}
        if stop_level is not None:
            for ep in self.episodes:
                # recompute path with current active set (earlier stops applied)
                w = self.native_weights(base_offense, active)
                path = per_instrument_path(w, self.nwr, cost_vec)
                wealth = pd.Series(path["wealth"].values, index=pd.to_datetime(path["Date"]))
                ep_active = [d for d in ep["fires"] if d in active]
                if not ep_active:
                    continue
                entry = ep_active[0]
                e = pos[entry]
                ref = wealth.iloc[e - 1] if e > 0 else 1.0  # value at entry-week close
                scan_end = pos[ep["last_fire"]]
                for t in range(e, scan_end + 1):
                    if wealth.iloc[t] / ref - 1.0 <= -stop_level:
                        cut = {d for d in ep["fires"] if pos[d] > t}
                        active -= cut
                        stop_log.append({"episode": ep["label"], "trigger_date": str(self.index[t].date()),
                                         "drawdown_from_entry": float(wealth.iloc[t] / ref - 1.0),
                                         "fires_disabled": len(cut)})
                        break
        w = self.native_weights(base_offense, active)
        path = per_instrument_path(w, self.nwr, cost_vec)
        return {"weights": w, "path": path, "active_fires": active, "stop_log": stop_log}


# ── Metrics (return-first primary + recorded risk) ──────────────────────────

def core_metrics(path: pd.DataFrame, spy_next: pd.Series) -> dict:
    p = dev_window(path)
    net = pd.Series(p["net_return"].values, index=p["Date"]).dropna()
    n = len(net)
    total = float((1.0 + net).prod())
    cagr = total ** (WEEKS / n) - 1.0
    log_growth = float(np.log1p(net).mean() * WEEKS)
    vol = float(net.std(ddof=1) * np.sqrt(WEEKS))
    sharpe = float(net.mean() / net.std(ddof=1) * np.sqrt(WEEKS)) if net.std(ddof=1) > 0 else np.nan
    wealth = (1.0 + net).cumprod()
    maxdd = float((wealth / wealth.cummax() - 1.0).min())
    q = net.quantile(0.05)
    cvar5 = float(net[net <= q].mean())
    to = float(pd.to_numeric(p["turnover"], errors="coerce").mean())
    spy = spy_next.reindex(net.index).fillna(0.0)
    beta, alpha_w = np.polyfit(spy.values, net.values, 1)
    return {"net_cagr": cagr, "log_growth": log_growth, "ann_vol": vol, "sharpe": sharpe,
            "max_dd": maxdd, "cvar5": cvar5, "avg_oneway_turnover": to,
            "beta_spy": float(beta), "residual_alpha_ann": float(alpha_w * WEEKS)}


def per_state_expectancy(path: pd.DataFrame, states: pd.Series, fire_mask: pd.Series) -> dict:
    p = dev_window(path)
    net = pd.Series(p["net_return"].values, index=p["Date"]).dropna()
    st = states.reindex(net.index).copy()
    st[fire_mask.reindex(net.index).fillna(False)] = "stressed_panic_improving"
    return {f"expectancy_{s}": float(g.mean() * WEEKS) for s, g in net.groupby(st)}


def episode_table(mach: R02Machinery, variant_path: pd.DataFrame, base_path: pd.DataFrame) -> pd.DataFrame:
    v = dev_window(variant_path).set_index("Date")["net_return"]
    b = dev_window(base_path).set_index("Date")["net_return"]
    rows = []
    for ep in mach.episodes:
        win_v = v.loc[ep["entry"]:ep["window_end"]]
        win_b = b.loc[ep["entry"]:ep["window_end"]]
        n = len(win_v)
        if n == 0:
            continue
        rv, rb = float((1 + win_v).prod() - 1), float((1 + win_b).prod() - 1)
        ann_v = (1 + rv) ** (WEEKS / n) - 1
        ann_b = (1 + rb) ** (WEEKS / n) - 1
        rows.append({"episode": ep["label"], "entry": str(ep["entry"].date()),
                     "window_end": str(ep["window_end"].date()), "weeks": n,
                     "n_fires": len(ep["fires"]),
                     "variant_total_return": rv, "base_total_return": rb,
                     "variant_ann": ann_v, "base_ann": ann_b,
                     "capture_pp_ann": (ann_v - ann_b) * 100,
                     "contribution_total": rv - rb})
    return pd.DataFrame(rows)
