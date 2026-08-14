"""Phase CC — Layer 2B Regime Engine Refinement.

Mission:
  Refine the regime engine so the system can distinguish when W1-style
  defense should actually be on, and when the portfolio should stay closer
  to production-style offense. This is an UPSTREAM Layer 2B state-
  representation refinement — not a new sleeve, not a new allocator
  variant, not a holdings-blend retry.

Diagnosis from Phase Z / AA / BB:
  - Z1 (HRP on 7-sleeve panel) classified Research-only. The HRP allocator
    sizes W1 (composite_structural_defense_sleeve) at ~0.45 in calm_trend,
    ~0.41 in neutral_mixed, and only ~0.26 in stressed_panic — the OPPOSITE
    of what the sleeve was built for. This was confirmed in Phase BB: with
    W1 cap relaxed to 0.55, W1 is sized at 0.507 in calm_trend, 0.411 in
    neutral_mixed, 0.510 in recovery_confirmed, and only 0.263 in
    stressed_panic. Increasing the cap does not change the structural
    misallocation — the allocator is being told that calm and stressed
    weeks look similar at the sleeve covariance level.
  - Phase AA (production+Z1 holdings blend) classified Research-only.
    Production-Z1 ETF overlap is highest in stressed_panic (0.462) and
    lowest in calm_trend (0.106) — Z1 contributes least where its defense
    is most needed.

The common upstream mechanism is that the regime engine's `neutral_mixed`
bucket (493 of 1,110 weeks; 44% of history) is too coarse. Inside this
bucket sit weeks where breadth and trend are still healthy (where W1 should
be light) AND weeks where stress is rising and breadth is decaying (where
W1 should be heavy). The downstream allocator cannot distinguish them
because the regime label is the same.

Phase CC asks: can we split `neutral_mixed` causally into
  `neutral_healthy` vs `neutral_deteriorating`
using only walk-forward features already produced by the regime engine,
and is the split meaningful enough to use in the next production rerun?

Method:
  Build an interpretable deterioration score from five existing causal
  features in market_state_history.csv:
    1. dd_neg            = -market_drawdown          (deeper drawdown = worse)
    2. breadth_decay     = -(breadth_sma_43 + breadth_26w_mom)/2
    3. stress            = recent_stress_26w         (higher = worse)
    4. corr              = avg_corr_risk_off_z       (higher risk-off = worse)
    5. inv_trans         = -transition_non_stress_prob (lower = worse → flipped)
  Each component is z-scored using a strictly trailing 156-week window
  (lagged by one week so that t's z-score uses only t-1 and earlier
  observations). The deterioration score is the equal-weighted average of
  these five z-scores.

  For each week labelled neutral_mixed in the original engine, compute the
  walk-forward percentile rank of its deterioration score AGAINST PAST
  neutral_mixed weeks only. The split rule is:
    rank >= 0.50 → neutral_deteriorating
    rank <  0.50 → neutral_healthy
  Weeks where any feature is missing fall back to the original
  neutral_mixed label (no split). This protects the early-history portion
  of the sample without inventing signal.

  Optional: a confidence_score from Phase 2B predictions (post-2008-11)
  is computed as the equal-weighted average of z(p_tail_risk) and
  -z(p_regime_confidence). It is reported as a secondary diagnostic but
  does NOT enter the split rule, because we want the primary refinement to
  be available across the entire sample.

Causal walk-forward safety:
  - Every feature is from market_state_history.csv (already lagged by the
    regime engine itself; raw inputs are 1-week-lagged at construction).
  - The z-score window is strictly trailing and lagged by one extra week:
    z(t) is computed from observations [t-156-1, ..., t-1].
  - The percentile-rank reference set for week t is past neutral_mixed
    weeks with deterioration scores already known (i.e., week's index < t).
  - No future information enters either the score or the rank.

Outputs to data/04_layer2b_risk_regime_engine/:
  market_state_history_refined.csv          — original cols + refined_state
                                               + score components + rank
                                               + confidence_score
                                               + defensive_overlay_hint
  phase_cc_refined_state_diagnostics.csv    — forward-window stats by state
  phase_cc_state_transition_matrix.csv      — transition counts old → new
  phase_cc_neutral_split_summary.csv        — split detail for neutral
  phase_cc_protocol.json                    — design + threshold + features
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

ROLLING_Z_WINDOW = 156           # 3y trailing window for component z-scores
ROLLING_Z_MIN_OBS = 78           # require at least 1.5y of obs to z-score
RANK_MIN_HISTORY = 26            # require >= 26 prior neutral_mixed weeks
SPLIT_THRESHOLD = 0.50           # rank >= 0.5 → deteriorating
PRIMARY_FEATURES = [
    "dd_neg", "breadth_decay", "stress", "corr", "inv_trans"
]


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_market_state() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


def load_phase2b() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "phase2b_meta_predictions.csv", parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


def load_weekly_returns() -> pd.DataFrame:
    df = pd.read_csv(LAYER1_DIR / "weekly_returns.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index()


def load_w1_returns() -> pd.Series:
    df = pd.read_csv(LAYER2A_DIR / "strategy_returns_composite_structural_defense_sleeve.csv",
                     index_col=0, parse_dates=True)
    df.index.name = None
    return df["net_return"].astype(float).sort_index()


# --------------------------------------------------------------------------
# walk-forward helpers
# --------------------------------------------------------------------------

def trailing_z(series: pd.Series, window: int = ROLLING_Z_WINDOW,
               min_obs: int = ROLLING_Z_MIN_OBS) -> pd.Series:
    """Trailing z-score lagged by one week.

    z(t) is computed from observations [..., t-1] only — t itself is
    excluded. This is strictly causal: today's z uses only past data.
    """
    s = series.astype(float)
    lagged = s.shift(1)
    mean = lagged.rolling(window=window, min_periods=min_obs).mean()
    std = lagged.rolling(window=window, min_periods=min_obs).std(ddof=0)
    z = (s - mean) / std.replace(0.0, np.nan)
    return z.replace([np.inf, -np.inf], np.nan)


def walk_forward_percentile_rank(score: pd.Series, eligible_mask: pd.Series,
                                 min_history: int = RANK_MIN_HISTORY) -> pd.Series:
    """For each eligible week t, compute the percentile rank of score[t]
    within {score[s] : s < t and eligible_mask[s] is True}. Strictly causal.
    """
    eligible_mask = eligible_mask.astype(bool).reindex(score.index).fillna(False)
    out = pd.Series(np.nan, index=score.index, dtype=float)
    history: list[float] = []
    for ts, val in score.items():
        if eligible_mask.loc[ts] and pd.notna(val) and len(history) >= min_history:
            arr = np.asarray(history, dtype=float)
            # rank in [0, 1]: fraction of past values strictly less than val
            # plus half of those equal — equivalent to scipy percentile of
            # the ordinal rank of val if it were appended.
            less = float((arr < val).sum())
            equal = float((arr == val).sum())
            rank = (less + 0.5 * equal) / float(len(arr))
            out.loc[ts] = rank
        # Update history AFTER assigning rank for ts (causal).
        if eligible_mask.loc[ts] and pd.notna(val):
            history.append(float(val))
    return out


# --------------------------------------------------------------------------
# build refined state
# --------------------------------------------------------------------------

def build_components(state_df: pd.DataFrame) -> pd.DataFrame:
    df = state_df.copy()
    df["dd_neg"] = -df["market_drawdown"].astype(float)
    df["breadth_decay"] = -(df["breadth_sma_43"].astype(float) + df["breadth_26w_mom"].astype(float)) / 2.0
    df["stress"] = df["recent_stress_26w"].astype(float)
    df["corr"] = df["avg_corr_risk_off_z"].astype(float)
    df["inv_trans"] = -df["transition_non_stress_prob"].astype(float)
    return df[PRIMARY_FEATURES]


def build_deterioration_score(components: pd.DataFrame) -> pd.DataFrame:
    z_cols = {}
    for col in components.columns:
        z_cols[f"z_{col}"] = trailing_z(components[col])
    z_df = pd.DataFrame(z_cols, index=components.index)
    # Equal-weight average; require ALL primary z's available for primary score
    valid = z_df.notna().all(axis=1)
    score = pd.Series(np.nan, index=z_df.index, dtype=float)
    score.loc[valid] = z_df.loc[valid].mean(axis=1)
    z_df["deterioration_z"] = score
    return z_df


def build_confidence_score(p2b: pd.DataFrame) -> pd.Series:
    """Secondary score from Phase 2B (post-2008-11). Higher = less confident
    + more tail risk. Used as a diagnostic only, not in the split rule."""
    if p2b.empty:
        return pd.Series(dtype=float)
    z_tail = trailing_z(p2b["p_tail_risk"].astype(float))
    z_conf = trailing_z(p2b["p_regime_confidence"].astype(float))
    valid = z_tail.notna() & z_conf.notna()
    out = pd.Series(np.nan, index=p2b.index, dtype=float)
    out.loc[valid] = (z_tail.loc[valid] - z_conf.loc[valid]) / 2.0
    return out


def assign_refined_state(state_df: pd.DataFrame, dz: pd.Series, rank: pd.Series) -> pd.Series:
    """Replace neutral_mixed with neutral_healthy / neutral_deteriorating
    where rank is available. Other states pass through unchanged."""
    refined = state_df["market_state"].astype(str).copy()
    is_neutral = refined.eq("neutral_mixed")
    have_rank = rank.notna()
    apply_mask = is_neutral & have_rank
    refined.loc[apply_mask & (rank >= SPLIT_THRESHOLD)] = "neutral_deteriorating"
    refined.loc[apply_mask & (rank < SPLIT_THRESHOLD)] = "neutral_healthy"
    return refined


def defensive_overlay_hint(refined: pd.Series, dz: pd.Series) -> pd.Series:
    """Production-allocator hint:
       +1  → defensive bias (W1 should be heavier)
        0  → neutral
       -1  → offensive bias (W1 should be lighter)
    The hint is a function of refined state ONLY — no leakage. It is
    saved so a future allocator rerun can use it as a sleeve-level tilt
    instead of touching the cap or the meta layer.
    """
    out = pd.Series(0, index=refined.index, dtype=int)
    out.loc[refined.eq("stressed_panic")] = 1
    out.loc[refined.eq("recovery_fragile")] = 1
    out.loc[refined.eq("neutral_deteriorating")] = 1
    out.loc[refined.eq("neutral_healthy")] = -1
    out.loc[refined.eq("calm_trend")] = -1
    out.loc[refined.eq("recovery_confirmed")] = -1
    return out


# --------------------------------------------------------------------------
# diagnostics
# --------------------------------------------------------------------------

def state_counts(orig: pd.Series, refined: pd.Series) -> pd.DataFrame:
    rows = []
    for state in sorted(set(orig.unique()) | set(refined.unique())):
        rows.append({
            "state": state,
            "original_count": int((orig == state).sum()),
            "refined_count": int((refined == state).sum()),
        })
    return pd.DataFrame(rows).sort_values("refined_count", ascending=False).reset_index(drop=True)


def transition_matrix(orig: pd.Series, refined: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"original": orig, "refined": refined})
    return pd.crosstab(df["original"], df["refined"]).reindex(
        index=sorted(df["original"].unique()),
        columns=sorted(df["refined"].unique()),
        fill_value=0,
    )


def forward_window_stats(returns: pd.Series, weeks: int) -> pd.Series:
    """Geometric forward-return over `weeks` starting at t (i.e., the next
    `weeks` observations after t). Causal-safe for diagnostic purposes
    (the score doesn't see this; it only enters the validation table)."""
    log_r = np.log1p(returns.astype(float))
    rolled = log_r.shift(-1).rolling(window=weeks, min_periods=weeks).sum().shift(-(weeks - 1))
    return np.expm1(rolled)


def forward_volatility(returns: pd.Series, weeks: int) -> pd.Series:
    return returns.shift(-1).rolling(window=weeks, min_periods=weeks).std(ddof=0).shift(-(weeks - 1))


def forward_transition_to_panic(state: pd.Series, weeks: int) -> pd.Series:
    """Probability that the state enters stressed_panic within the next
    `weeks` weeks (excluding t itself)."""
    panic = (state == "stressed_panic").astype(float)
    fwd = panic.shift(-1).rolling(window=weeks, min_periods=weeks).max().shift(-(weeks - 1))
    return fwd


def diagnostics_by_state(refined: pd.Series, spy_ret: pd.Series, w1_ret: pd.Series,
                         orig_state: pd.Series) -> pd.DataFrame:
    fwd4_spy = forward_window_stats(spy_ret, 4)
    fwd13_spy = forward_window_stats(spy_ret, 13)
    fwd4_vol = forward_volatility(spy_ret, 4)
    fwd4_w1 = forward_window_stats(w1_ret, 4)
    fwd4_panic = forward_transition_to_panic(orig_state, 4)
    rows = []
    for state in sorted(refined.unique()):
        mask = refined.eq(state)
        rows.append({
            "refined_state": state,
            "n_weeks": int(mask.sum()),
            "fwd4_spy_mean": float(fwd4_spy[mask].mean()),
            "fwd4_spy_median": float(fwd4_spy[mask].median()),
            "fwd4_spy_hit_rate": float((fwd4_spy[mask] > 0).mean()),
            "fwd13_spy_mean": float(fwd13_spy[mask].mean()),
            "fwd4_realized_vol": float(fwd4_vol[mask].mean()),
            "fwd4_to_panic_prob": float(fwd4_panic[mask].mean()),
            "fwd4_w1_mean": float(fwd4_w1[mask].mean()),
            "fwd4_w1_minus_spy": float((fwd4_w1[mask] - fwd4_spy[mask]).mean()),
        })
    return pd.DataFrame(rows)


def neutral_split_summary(refined: pd.Series, dz: pd.Series, rank: pd.Series,
                          orig_state: pd.Series) -> pd.DataFrame:
    """Detail of how the neutral_mixed bucket was partitioned, including
    weeks that fell back to neutral_mixed (no rank)."""
    is_orig_neutral = orig_state.eq("neutral_mixed")
    rows = []
    for label in ["neutral_healthy", "neutral_mixed", "neutral_deteriorating"]:
        mask = is_orig_neutral & refined.eq(label)
        rows.append({
            "refined_label": label,
            "n_weeks": int(mask.sum()),
            "frac_of_neutral_mixed": float(mask.sum() / max(1, int(is_orig_neutral.sum()))),
            "deterioration_z_mean": float(dz[mask].mean()) if mask.any() else float("nan"),
            "deterioration_z_median": float(dz[mask].median()) if mask.any() else float("nan"),
            "rank_mean": float(rank[mask].mean()) if mask.any() else float("nan"),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> None:
    print("Loading regime engine state + Phase 2B predictions...")
    state_df = load_market_state()
    p2b = load_phase2b()
    weekly = load_weekly_returns()
    w1_ret = load_w1_returns()
    spy_ret = weekly["SPY"].astype(float).reindex(state_df.index)

    print("Building causal feature components...")
    components = build_components(state_df)

    print("Computing trailing z-scores (window=156w, lagged by 1w)...")
    z_components = build_deterioration_score(components)

    dz = z_components["deterioration_z"]
    is_neutral = state_df["market_state"].eq("neutral_mixed")
    print(f"Neutral-mixed weeks total: {int(is_neutral.sum())}")
    print(f"Weeks with valid deterioration z (any state): {int(dz.notna().sum())}")
    print(f"Neutral-mixed weeks with valid deterioration z: {int((is_neutral & dz.notna()).sum())}")

    print("Computing walk-forward percentile rank within historical neutral_mixed...")
    rank = walk_forward_percentile_rank(dz, is_neutral, min_history=RANK_MIN_HISTORY)

    print("Assigning refined state...")
    refined = assign_refined_state(state_df, dz, rank)

    print("\nState counts (original vs refined):")
    counts = state_counts(state_df["market_state"], refined)
    print(counts.to_string(index=False))

    print("\nNeutral_mixed split summary:")
    split_summary = neutral_split_summary(refined, dz, rank, state_df["market_state"])
    print(split_summary.to_string(index=False))

    print("\nState transition matrix (rows=original, cols=refined):")
    trans = transition_matrix(state_df["market_state"], refined)
    print(trans.to_string())

    print("\nForward-window diagnostics by refined state:")
    diag = diagnostics_by_state(refined, spy_ret, w1_ret, state_df["market_state"])
    print(diag.to_string(index=False))

    # Build confidence score (secondary, Phase 2B based)
    confidence = build_confidence_score(p2b)
    confidence_aligned = confidence.reindex(state_df.index)

    # Defensive overlay hint
    overlay_hint = defensive_overlay_hint(refined, dz)

    # --------------------------------------------------------------
    # Save refined state file (preserving original columns)
    # --------------------------------------------------------------
    refined_df = state_df.copy()
    refined_df["refined_state"] = refined
    for col in z_components.columns:
        refined_df[col] = z_components[col]
    refined_df["deterioration_rank_neutral_mixed"] = rank
    refined_df["confidence_score_p2b"] = confidence_aligned
    refined_df["defensive_overlay_hint"] = overlay_hint
    refined_df.index.name = "Date"
    out_state_path = LAYER2B_DIR / "market_state_history_refined.csv"
    refined_df.to_csv(out_state_path)

    diag.to_csv(LAYER2B_DIR / "phase_cc_refined_state_diagnostics.csv", index=False)
    trans.to_csv(LAYER2B_DIR / "phase_cc_state_transition_matrix.csv")
    split_summary.to_csv(LAYER2B_DIR / "phase_cc_neutral_split_summary.csv", index=False)
    counts.to_csv(LAYER2B_DIR / "phase_cc_state_counts.csv", index=False)

    protocol = {
        "phase": "Phase CC — Layer 2B Regime Engine Refinement",
        "objective": (
            "Split neutral_mixed into neutral_healthy and neutral_deteriorating "
            "using a causal walk-forward deterioration score so that the next "
            "production allocator rerun can size W1 selectively."
        ),
        "primary_features": PRIMARY_FEATURES,
        "feature_definitions": {
            "dd_neg": "-market_drawdown (deeper drawdown = larger positive)",
            "breadth_decay": "-(breadth_sma_43 + breadth_26w_mom)/2",
            "stress": "recent_stress_26w",
            "corr": "avg_corr_risk_off_z",
            "inv_trans": "-transition_non_stress_prob",
        },
        "z_window_weeks": ROLLING_Z_WINDOW,
        "z_min_obs": ROLLING_Z_MIN_OBS,
        "z_lagged_by_weeks": 1,
        "rank_reference_set": "past neutral_mixed weeks only, strictly t' < t",
        "rank_min_history": RANK_MIN_HISTORY,
        "split_threshold_rank": SPLIT_THRESHOLD,
        "split_rule": (
            "rank >= 0.50 → neutral_deteriorating; rank < 0.50 → neutral_healthy; "
            "missing rank → fall back to neutral_mixed (no split)."
        ),
        "secondary_confidence_score": (
            "(z(p_tail_risk) - z(p_regime_confidence)) / 2 over Phase 2B horizon "
            "(post-2008-11). Diagnostic only; does not enter the split rule."
        ),
        "defensive_overlay_hint": {
            "+1": ["stressed_panic", "recovery_fragile", "neutral_deteriorating"],
            "0": [],
            "-1": ["calm_trend", "recovery_confirmed", "neutral_healthy"],
            "neutral_mixed_fallback": 0,
        },
        "outputs": [
            "market_state_history_refined.csv",
            "phase_cc_refined_state_diagnostics.csv",
            "phase_cc_state_transition_matrix.csv",
            "phase_cc_neutral_split_summary.csv",
            "phase_cc_state_counts.csv",
        ],
        "causal_safety": [
            "All primary features are computed by the regime engine from "
            "1-week-lagged inputs.",
            "trailing_z lags by one week (t excluded from its own moving window).",
            "walk_forward_percentile_rank uses only past values (s < t).",
            "Forward-window diagnostics enter NO score; they only validate.",
        ],
    }
    (LAYER2B_DIR / "phase_cc_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\nSaved refined regime engine artifacts.")
    print(f"  - {out_state_path.relative_to(ROOT)}")
    print(f"  - phase_cc_refined_state_diagnostics.csv")
    print(f"  - phase_cc_state_transition_matrix.csv")
    print(f"  - phase_cc_neutral_split_summary.csv")
    print(f"  - phase_cc_state_counts.csv")
    print(f"  - phase_cc_protocol.json")


if __name__ == "__main__":
    main()
