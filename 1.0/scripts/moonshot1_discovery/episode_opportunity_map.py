"""Phase 2 opportunity map for the moonshot discovery sprint.

Segments the full active history into labeled market episodes using only
mechanical, reproducible definitions on SPY and the Layer 2B state file, then
measures what the production pin did in each episode versus a per-episode
"ideal available behavior" bound (best of offense-heavy / defense-heavy given
the episode's realized returns — an upper bound, not a claim the bound was
attainable).

Episode taxonomy (mechanical definitions):
    * decline           - SPY drawdown deepens from -5% through its trough
    * early_recovery    - first 13 weeks after a >=10% drawdown trough
    * late_recovery     - trough+13w until prior SPY peak regained
    * false_rally       - >=5% 4-week SPY rally inside a decline phase that
                          subsequently made a new low before any recovery
    * bull_broad        - DD > -5%, trend positive, breadth_sma_43 >= 0.65
    * bull_narrow       - DD > -5%, trend positive, breadth_sma_43 < 0.50
    * calm_weakening    - DD > -5%, trend positive, breadth_change_4w < -0.05
    * chop              - everything else

Outputs machine-readable CSVs under data/research/moonshot1_discovery/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper  # noqa: E402
from path1_path3_research_utils import (  # noqa: E402
    DATA,
    OFFENSE,
    load_states,
    load_weekly_returns_file,
    rel,
)
from production_allocator import production_modifier  # noqa: E402

OUT_DIR = DATA / "research" / "moonshot1_discovery"


def label_weeks(spy_px: pd.Series, states: pd.DataFrame) -> pd.DataFrame:
    dd = spy_px / spy_px.cummax() - 1.0
    trend = states["market_trend_positive"].reindex(spy_px.index).fillna(0.0)
    breadth = states["breadth_sma_43"].reindex(spy_px.index).ffill().fillna(0.5)
    b_chg = states["breadth_change_4w"].reindex(spy_px.index).ffill().fillna(0.0)
    rally_4w = spy_px.pct_change(4)

    labels = pd.Series("chop", index=spy_px.index)

    # Decline / recovery phases from >=10% drawdown episodes.
    in_dd = dd < -0.05
    trough_dates: list[pd.Timestamp] = []
    peak_recover: dict[pd.Timestamp, pd.Timestamp] = {}
    i = 0
    idx = spy_px.index
    while i < len(idx):
        if dd.iloc[i] < -0.10:
            # Find episode bounds: back to last DD==0, forward to DD==0.
            start = i
            while start > 0 and dd.iloc[start - 1] < 0:
                start -= 1
            end = i
            while end < len(idx) - 1 and dd.iloc[end + 1] < 0:
                end += 1
            seg = dd.iloc[start : end + 1]
            trough_pos = start + int(np.argmin(seg.to_numpy()))
            trough = idx[trough_pos]
            trough_dates.append(trough)
            labels.iloc[start : trough_pos + 1] = "decline"
            rec_end = min(trough_pos + 13, end)
            labels.iloc[trough_pos + 1 : rec_end + 1] = "early_recovery"
            if rec_end < end:
                labels.iloc[rec_end + 1 : end + 1] = "late_recovery"
            # False rallies: >=5% 4w rally strictly inside the decline phase
            # that was followed by a lower low before the trough.
            for j in range(start + 4, trough_pos):
                if rally_4w.iloc[j] >= 0.05 and dd.iloc[j] < -0.05:
                    labels.iloc[max(j - 3, start) : j + 1] = "false_rally"
            i = end + 1
        else:
            i += 1

    benign = (dd > -0.05) & labels.eq("chop")
    labels[benign & (trend > 0) & (breadth >= 0.65)] = "bull_broad"
    labels[benign & (trend > 0) & (breadth < 0.50)] = "bull_narrow"
    labels[benign & (trend > 0) & (b_chg < -0.05) & (breadth >= 0.50)] = "calm_weakening"
    return pd.DataFrame({"episode_label": labels, "spy_drawdown": dd})


def contiguous_episodes(labels: pd.Series) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    out = []
    start = labels.index[0]
    current = labels.iloc[0]
    for date, lab in labels.items():
        if lab != current:
            out.append((current, start, prev))
            start, current = date, lab
        prev = date
    out.append((current, start, prev))
    return out


def ann(ret: pd.Series) -> float:
    ret = ret.dropna()
    if len(ret) < 2:
        return np.nan
    wealth = float((1 + ret).prod())
    if wealth <= 0:
        return np.nan
    return wealth ** (52.0 / len(ret)) - 1.0


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    wrapper = AllocatorCheckpointWrapper()
    prod = wrapper.run("production_pin", [production_modifier(wrapper)])
    pin = prod.path.set_index("Date")
    pin.index = pd.to_datetime(pin.index)
    states = load_states(warnings)
    weekly_ret = load_weekly_returns_file(warnings)

    from path1_path3_research_utils import load_weekly_prices

    prices = load_weekly_prices(warnings)
    spy_px = prices["SPY"].reindex(pin.index).ffill()
    spy_fwd = weekly_ret["SPY"].shift(-1).reindex(pin.index)  # matches pin convention
    bil_fwd = weekly_ret["BIL"].shift(-1).reindex(pin.index).fillna(0.0)

    week_labels = label_weeks(spy_px, states)
    week_labels["market_state"] = states["market_state"].reindex(pin.index)

    offense_cols = [c for c in wrapper.final_weights.columns if c in OFFENSE]
    offense_w = wrapper.final_weights[offense_cols].sum(axis=1).reindex(pin.index)
    bil_w = wrapper.final_weights.get("BIL", pd.Series(0.0, index=pin.index)).reindex(pin.index)

    # Per-label aggregate table.
    rows = []
    for label, group in week_labels.groupby("episode_label"):
        mask = week_labels["episode_label"].eq(label)
        n = int(mask.sum())
        pin_r = pin.loc[mask, "net_return"]
        rows.append(
            {
                "episode_label": label,
                "weeks": n,
                "share_of_history": n / len(week_labels),
                "pin_ann_return": ann(pin_r),
                "spy_ann_return": ann(spy_fwd[mask]),
                "bil_ann_return": ann(bil_fwd[mask]),
                "pin_avg_offense_weight": float(offense_w[mask].mean()),
                "pin_avg_bil_weight": float(bil_w[mask].mean()),
                "pin_weekly_win_vs_bil": float((pin_r > bil_fwd[mask]).mean()),
                "spy_gt_bil_share": float((spy_fwd[mask] > bil_fwd[mask]).mean()),
            }
        )
    label_table = pd.DataFrame(rows).sort_values("weeks", ascending=False)
    label_table.to_csv(OUT_DIR / "episode_label_summary.csv", index=False)

    # Contiguous episode table with ideal-behavior bound.
    ep_rows = []
    for label, start, end in contiguous_episodes(week_labels["episode_label"]):
        mask = (week_labels.index >= start) & (week_labels.index <= end)
        if mask.sum() < 2:
            continue
        pin_tot = float((1 + pin.loc[mask, "net_return"]).prod() - 1)
        spy_tot = float((1 + spy_fwd[mask].fillna(0.0)).prod() - 1)
        bil_tot = float((1 + bil_fwd[mask]).prod() - 1)
        ideal = max(spy_tot, bil_tot)
        ep_rows.append(
            {
                "episode_label": label,
                "start": str(start.date()),
                "end": str(end.date()),
                "weeks": int(mask.sum()),
                "pin_total_return": pin_tot,
                "spy_total_return": spy_tot,
                "bil_total_return": bil_tot,
                "ideal_bound_return": ideal,
                "pin_minus_ideal": pin_tot - ideal,
                "avg_offense_weight": float(offense_w[mask].mean()),
                "avg_bil_weight": float(bil_w[mask].mean()),
                "dominant_market_state": week_labels.loc[mask, "market_state"].mode().iloc[0]
                if not week_labels.loc[mask, "market_state"].mode().empty
                else "",
            }
        )
    episodes = pd.DataFrame(ep_rows)
    episodes.to_csv(OUT_DIR / "episode_opportunity_map.csv", index=False)

    # Biggest opportunity gaps (pin far below the ideal bound).
    gaps = episodes.nsmallest(15, "pin_minus_ideal")
    gaps.to_csv(OUT_DIR / "episode_biggest_gaps.csv", index=False)

    print("Per-label summary:")
    print(label_table.round(4).to_string(index=False))
    print("\nTop opportunity gaps (pin vs ideal bound):")
    print(
        gaps[["episode_label", "start", "end", "weeks", "pin_total_return", "ideal_bound_return", "pin_minus_ideal"]]
        .round(4)
        .to_string(index=False)
    )
    print(f"\nSaved: {rel(OUT_DIR / 'episode_opportunity_map.csv')}")
    for w in warnings:
        print(f"WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
