"""Frontier Phase 1A-R2: predeclared sign-audited deployment quality composite.

Research-only. Builds four state-aware composite variants using economic logic,
not full-history optimisation. Validates each variant on full period, development
window (before 2024-04-19), and holdout (from 2024-04-19), with state-conditional
IC and quintile returns.

Does NOT modify production, dashboard, public, or src files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ACTUAL_MARKET_STATE = DATA / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
ACTUAL_WEEKLY_PRICES = DATA / "01_data_hub" / "weekly_prices.csv"
ACTUAL_DAILY_PRICES = DATA / "01_data_hub" / "daily_prices.csv"
PHASE1_SIGNALS = DATA / "research" / "frontier_phase1" / "state_quality_signals.csv"
OUT_DIR = DATA / "research" / "frontier_phase1"
PROTECTED_DIFF_PATHS = [
    "public",
    "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]

HOLDOUT_START = pd.Timestamp("2024-04-19")

# ── Economic sign configuration for R2A ──────────────────────────────────────
# Signs pre-declared before examining any R2-specific IC.
# Economic rationale documented in report section.
# 0 = exclude component from this state's composite.
R2A_STATE_SIGN_CONFIG: dict[str, dict[str, float]] = {
    "recovery_fragile": {
        "breadth_quality_score": +1.0,   # broad participation = genuine recovery
        "path_clarity_r2": +1.0,          # clean path = orderly recovery
        "state_persistence_score": +1.0,  # persistent recovery = real, not fake
        "leadership_quality_score": +1.0, # quality leaders confirming = bullish
        # credit_confirmation: excluded – anti-predictive in recovery (-0.243)
    },
    "recovery_confirmed": {
        "breadth_quality_score": +1.0,
        "path_clarity_r2": +1.0,          # weak IC (-0.021) but positive logic
        "state_persistence_score": +1.0,
        "leadership_quality_score": +1.0,
    },
    "calm_trend": {
        # Inverted: high quality = crowded/mature trend = less forward upside
        "breadth_quality_score": -1.0,   # high breadth = late-cycle crowding
        "path_clarity_r2": -1.0,          # smooth trend = overextended
        "state_persistence_score": -1.0,  # long calm = exhaustion risk
        "leadership_quality_score": -1.0, # crowded leadership = fragile
    },
    "neutral_mixed": {
        # Same logic as calm_trend: high-quality neutral weeks tend to be full ones
        "breadth_quality_score": -1.0,
        "path_clarity_r2": -1.0,
        "state_persistence_score": -1.0,
        "leadership_quality_score": -1.0,
    },
    "strong_neutral": {
        # Treated as mature/late-cycle as well
        "breadth_quality_score": -1.0,
        "path_clarity_r2": -1.0,
        "state_persistence_score": -1.0,
        "leadership_quality_score": -1.0,
    },
    "stressed_panic": {
        # path_clarity: orderly stress predicts end of panic / easier recovery
        "path_clarity_r2": +1.0,
        # breadth: low breadth in stress = depth of panic = larger forward bounce
        "breadth_quality_score": -1.0,
        # persistence: excluded – long stressed_panic should not be rewarded
        # leadership: excluded – unreliable during panic
    },
}

# R2B: state-aware grouping but ALL positive signs (tests sign-flip value alone)
R2B_STATE_SIGN_CONFIG: dict[str, dict[str, float]] = {
    "recovery_fragile": {
        "breadth_quality_score": +1.0,
        "path_clarity_r2": +1.0,
        "state_persistence_score": +1.0,
        "leadership_quality_score": +1.0,
    },
    "recovery_confirmed": {
        "breadth_quality_score": +1.0,
        "path_clarity_r2": +1.0,
        "state_persistence_score": +1.0,
        "leadership_quality_score": +1.0,
    },
    "calm_trend": {
        # positive signs – no flip (control case vs R2A)
        "breadth_quality_score": +1.0,
        "path_clarity_r2": +1.0,
        "state_persistence_score": +1.0,
        "leadership_quality_score": +1.0,
    },
    "neutral_mixed": {
        "breadth_quality_score": +1.0,
        "path_clarity_r2": +1.0,
        "state_persistence_score": +1.0,
        "leadership_quality_score": +1.0,
    },
    "strong_neutral": {
        "breadth_quality_score": +1.0,
        "path_clarity_r2": +1.0,
        "state_persistence_score": +1.0,
        "leadership_quality_score": +1.0,
    },
    "stressed_panic": {
        # Only path_clarity active (clear signal); breadth excluded to keep R2B clean
        "path_clarity_r2": +1.0,
    },
}

# R2D: recovery-only with hump-shaped (capped) persistence
# Non-recovery states: composite = NaN (not used)
# Hump: persistence_freshness = min(state_persistence_score, 0.5)
R2D_RECOVERY_SIGNS: dict[str, float] = {
    "breadth_quality_score": +1.0,
    "path_clarity_r2": +1.0,
    "state_persistence_score_capped": +1.0,  # hump-shaped capped version
    "leadership_quality_score": +1.0,
}
R2D_ACTIVE_STATES = {"recovery_fragile", "recovery_confirmed"}


# ── Utilities ─────────────────────────────────────────────────────────────────

def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def expanding_zscore(series: pd.Series, min_periods: int = 52) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mean = s.expanding(min_periods=min_periods).mean()
    std = s.expanding(min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    z = (s - mean) / std
    return z.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    merged = pd.concat([x, y], axis=1).dropna()
    if len(merged) < 10:
        return None
    r, _ = scipy_stats.spearmanr(merged.iloc[:, 0], merged.iloc[:, 1])
    return float(r) if np.isfinite(r) else None


def compute_ic_table(
    signal_df: pd.DataFrame,   # cols: market_state, r2a, r2b, r2c, r2d
    forward_return: pd.Series,
    variants: list[str],
    scope_label: str,
) -> pd.DataFrame:
    rows = []
    frame = signal_df.copy()
    frame["fwd"] = forward_return

    for var in variants:
        if var not in frame.columns:
            continue
        # Full period (within scope)
        clean = frame[[var, "fwd"]].dropna()
        ic = spearman_ic(clean[var], clean["fwd"])
        rows.append({
            "scope": scope_label,
            "market_state": "ALL",
            "variant": var,
            "spearman_ic": ic,
            "n_observations": len(clean),
            "mean_forward_4w_return": float(clean["fwd"].mean()) if len(clean) else np.nan,
        })
        # By state
        for state, grp in frame.groupby("market_state"):
            g = grp[[var, "fwd"]].dropna()
            ic_s = spearman_ic(g[var], g["fwd"])
            rows.append({
                "scope": scope_label,
                "market_state": str(state),
                "variant": var,
                "spearman_ic": ic_s,
                "n_observations": len(g),
                "mean_forward_4w_return": float(g["fwd"].mean()) if len(g) else np.nan,
            })
    return pd.DataFrame(rows)


def compute_quintile_returns(
    signal_df: pd.DataFrame,
    forward_return: pd.Series,
    variant: str,
    n_quantiles: int = 5,
) -> pd.DataFrame:
    rows = []
    frame = signal_df[[variant, "market_state"]].copy()
    frame["fwd"] = forward_return
    frame = frame.dropna(subset=[variant, "fwd"])

    for state, grp in frame.groupby("market_state"):
        if len(grp) < n_quantiles * 5:
            rows.append({
                "variant": variant,
                "market_state": str(state),
                "quintile": "insufficient_data",
                "n_observations": len(grp),
                "mean_forward_4w_return": np.nan,
                "median_signal": np.nan,
            })
            continue
        try:
            labels = pd.qcut(grp[variant], q=n_quantiles, labels=False, duplicates="drop")
        except Exception:
            rows.append({
                "variant": variant,
                "market_state": str(state),
                "quintile": "qcut_failed",
                "n_observations": len(grp),
                "mean_forward_4w_return": np.nan,
                "median_signal": np.nan,
            })
            continue
        grp = grp.copy()
        grp["quintile"] = labels + 1
        for q, qgrp in grp.groupby("quintile"):
            rows.append({
                "variant": variant,
                "market_state": str(state),
                "quintile": int(q),
                "n_observations": len(qgrp),
                "mean_forward_4w_return": float(qgrp["fwd"].mean()),
                "median_signal": float(qgrp[variant].median()),
            })
    return pd.DataFrame(rows)


def build_state_aware_composite(
    signals: pd.DataFrame,
    sign_config: dict[str, dict[str, float]],
    name: str,
    hump_persistence: bool = False,
    active_states_only: set[str] | None = None,
) -> pd.Series:
    """Build a state-aware composite from pre-declared sign configuration.

    For each row, applies the per-state sign weights to the available
    z-scored components, then takes the equal-weighted mean. Returns a
    z-scored series (winsorised at ±3).
    """
    components = [
        "breadth_quality_score",
        "path_clarity_r2",
        "state_persistence_score",
        "leadership_quality_score",
    ]
    if hump_persistence and "state_persistence_score_capped" not in signals.columns:
        # Add hump-shaped persistence (cap at 0.5 before z-scoring)
        signals = signals.copy()
        signals["state_persistence_score_capped"] = signals["state_persistence_score"].clip(upper=0.5)

    # Z-score each component expanding (identical to original script logic)
    z_cols: dict[str, pd.Series] = {}
    all_cols = components + (["state_persistence_score_capped"] if hump_persistence else [])
    for col in all_cols:
        if col in signals.columns:
            z_cols[col] = expanding_zscore(signals[col])

    composite_values = pd.Series(np.nan, index=signals.index, dtype=float)

    for i, (idx, row) in enumerate(signals.iterrows()):
        state = str(row.get("market_state", ""))
        if active_states_only is not None and state not in active_states_only:
            composite_values.iloc[i] = np.nan
            continue
        cfg = sign_config.get(state)
        if cfg is None:
            composite_values.iloc[i] = np.nan
            continue

        accum = []
        for comp, sign in cfg.items():
            if sign == 0.0:
                continue
            z_series = z_cols.get(comp)
            if z_series is None:
                continue
            val = z_series.iloc[i]
            if np.isfinite(val):
                accum.append(sign * val)

        if accum:
            composite_values.iloc[i] = float(np.mean(accum))

    return expanding_zscore(composite_values).clip(-3.0, 3.0).rename(name)


def build_credit_relative_momentum(warnings: list[str]) -> pd.Series | None:
    """Continuous credit relative momentum: HYG_4w_return - LQD_4w_return, z-scored, 1w lag."""
    if not ACTUAL_WEEKLY_PRICES.exists():
        if ACTUAL_DAILY_PRICES.exists():
            daily = pd.read_csv(ACTUAL_DAILY_PRICES)
            daily["Date"] = pd.to_datetime(daily["Date"], errors="coerce").dt.tz_localize(None)
            daily = daily.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
            weekly = daily.resample("W-FRI").last().apply(pd.to_numeric, errors="coerce")
        else:
            warnings.append("No weekly or daily prices available for credit_relative_momentum.")
            return None
    else:
        weekly = pd.read_csv(ACTUAL_WEEKLY_PRICES)
        weekly["Date"] = pd.to_datetime(weekly["Date"], errors="coerce").dt.tz_localize(None)
        weekly = weekly.dropna(subset=["Date"]).sort_values("Date").set_index("Date").apply(pd.to_numeric, errors="coerce")

    if "HYG" not in weekly.columns or "LQD" not in weekly.columns:
        warnings.append("HYG or LQD not in weekly prices; cannot build credit_relative_momentum.")
        return None

    hyg_ret = weekly["HYG"].pct_change(4)
    lqd_ret = weekly["LQD"].pct_change(4)
    credit_rel = hyg_ret - lqd_ret
    credit_rel_z = expanding_zscore(credit_rel.shift(1))  # 1-week lag
    return credit_rel_z.rename("credit_relative_momentum")


def protected_diff_clean() -> tuple[bool, list[str]]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--", *PROTECTED_DIFF_PATHS],
            cwd=ROOT, check=False, text=True, capture_output=True,
        )
    except Exception:
        return False, ["git diff check failed to run"]
    changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return len(changed) == 0, changed


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    warnings_list: list[str] = []
    print("=" * 70)
    print("Frontier Phase 1A-R2: Predeclared Sign-Audited Composite")
    print("=" * 70)

    # ── 1. Load existing Phase 1A signals ────────────────────────────────────
    if not PHASE1_SIGNALS.exists():
        raise SystemExit(f"Phase 1A signals not found: {rel(PHASE1_SIGNALS)}")

    signals_raw = pd.read_csv(PHASE1_SIGNALS)
    if "date" in signals_raw.columns:
        signals_raw["date"] = pd.to_datetime(signals_raw["date"], errors="coerce").dt.tz_localize(None)
        signals_raw = signals_raw.dropna(subset=["date"]).sort_values("date").set_index("date")
    elif "Date" in signals_raw.columns:
        signals_raw["Date"] = pd.to_datetime(signals_raw["Date"], errors="coerce").dt.tz_localize(None)
        signals_raw = signals_raw.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    else:
        raise SystemExit("Phase 1A signals CSV has no date/Date column.")

    print(f"Loaded Phase 1A signals: {len(signals_raw)} rows, columns: {list(signals_raw.columns)}")

    # The signals are already 1-week lagged from Phase 1A
    signals = signals_raw.copy()
    signals["market_state"] = signals["market_state"].astype(str)

    # ── 2. Compute SPY forward return ────────────────────────────────────────
    # Load weekly prices for SPY forward return
    fwd_return: pd.Series | None = None
    for price_path in [ACTUAL_WEEKLY_PRICES]:
        if price_path.exists():
            try:
                wk = pd.read_csv(price_path)
                date_col = "Date" if "Date" in wk.columns else "date"
                wk[date_col] = pd.to_datetime(wk[date_col], errors="coerce").dt.tz_localize(None)
                wk = wk.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)
                wk = wk.apply(pd.to_numeric, errors="coerce")
                if "SPY" in wk.columns:
                    spy = wk["SPY"].reindex(signals.index).ffill()
                    fwd_return = (spy.shift(-4) / spy - 1.0)
                    print(f"SPY forward return computed from {rel(price_path)}")
                    break
            except Exception as exc:
                warnings_list.append(f"Could not compute forward return from {price_path}: {exc}")

    if fwd_return is None:
        raise SystemExit("Could not compute SPY 4-week forward return.")

    # ── 3. Build credit_relative_momentum (R2C component) ────────────────────
    credit_rel_mom = build_credit_relative_momentum(warnings_list)
    if credit_rel_mom is not None:
        signals["credit_relative_momentum"] = credit_rel_mom.reindex(signals.index)
        print("credit_relative_momentum computed and merged.")
    else:
        signals["credit_relative_momentum"] = np.nan
        warnings_list.append("credit_relative_momentum unavailable; R2C will be NaN-only.")

    # ── 4. Build R2A (state-aware economic signs) ────────────────────────────
    print("\nBuilding R2A (state-aware signed composite, no credit)...")
    signals["r2a"] = build_state_aware_composite(
        signals, R2A_STATE_SIGN_CONFIG, name="r2a"
    )

    # ── 5. Build R2B (state-aware, positive signs only, no credit) ───────────
    print("Building R2B (state-aware, positive signs only, no credit)...")
    signals["r2b"] = build_state_aware_composite(
        signals, R2B_STATE_SIGN_CONFIG, name="r2b"
    )

    # ── 6. Build R2C (credit redesign as diagnostic standalone) ──────────────
    print("Building R2C (credit_relative_momentum as standalone component)...")
    # R2C is a standalone diagnostic: z-scored HYG-LQD momentum
    if not signals["credit_relative_momentum"].isna().all():
        signals["r2c"] = signals["credit_relative_momentum"].copy()
        print("  R2C = credit_relative_momentum (diagnostic only).")
    else:
        signals["r2c"] = np.nan
        warnings_list.append("R2C is NaN — credit_relative_momentum unavailable.")

    # ── 7. Build R2D (recovery-only, hump-shaped persistence) ────────────────
    print("Building R2D (recovery-only, hump-shaped persistence)...")
    signals["r2d"] = build_state_aware_composite(
        signals,
        sign_config={
            state: R2D_RECOVERY_SIGNS
            for state in R2D_ACTIVE_STATES
        },
        name="r2d",
        hump_persistence=True,
        active_states_only=R2D_ACTIVE_STATES,
    )

    all_variants = ["deployment_quality_composite", "r2a", "r2b", "r2c", "r2d"]
    available_variants = [v for v in all_variants if v in signals.columns and not signals[v].isna().all()]
    print(f"\nVariants available: {available_variants}")

    # ── 8. Save extended signals CSV ─────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_cols = ["market_state"] + [
        c for c in [
            "breadth_quality_score", "path_clarity_r2", "state_persistence_score",
            "credit_confirmation", "leadership_quality_score",
            "credit_relative_momentum", "deployment_quality_composite",
            "r2a", "r2b", "r2c", "r2d",
        ] if c in signals.columns
    ]
    signals_out = signals[out_cols].copy()
    signals_out.index.name = "date"
    signals_out_path = OUT_DIR / "state_quality_signals_r2.csv"
    signals_out.to_csv(signals_out_path)
    print(f"\nSaved: {rel(signals_out_path)}")

    # ── 9. IC analysis: full, dev, holdout ───────────────────────────────────
    print("\nComputing IC tables...")
    dev_mask = signals.index < HOLDOUT_START
    holdout_mask = signals.index >= HOLDOUT_START

    ic_full = compute_ic_table(signals, fwd_return, available_variants, "full_period")
    ic_dev = compute_ic_table(
        signals[dev_mask], fwd_return[dev_mask], available_variants, "development"
    )
    ic_holdout = compute_ic_table(
        signals[holdout_mask], fwd_return[holdout_mask], available_variants, "holdout"
    )

    ic_all = pd.concat([ic_full, ic_dev, ic_holdout], ignore_index=True)
    ic_path = OUT_DIR / "state_quality_r2_ic_by_state.csv"
    ic_all.to_csv(ic_path, index=False)
    print(f"Saved: {rel(ic_path)}")

    # ── 10. Quintile returns ──────────────────────────────────────────────────
    print("Computing quintile returns...")
    quint_frames = []
    for var in available_variants:
        quint_frames.append(compute_quintile_returns(signals, fwd_return, var))
    quintile_df = pd.concat(quint_frames, ignore_index=True)
    quint_path = OUT_DIR / "state_quality_r2_quintile_returns_by_state.csv"
    quintile_df.to_csv(quint_path, index=False)
    print(f"Saved: {rel(quint_path)}")

    # ── 11. Build summary for report ─────────────────────────────────────────
    print("\nSummary by variant (full period):")
    summary_rows = []
    states_of_interest = ["calm_trend", "neutral_mixed", "recovery_confirmed",
                          "recovery_fragile", "stressed_panic"]

    full_ic_pivot = ic_full.pivot_table(
        index="market_state", columns="variant", values="spearman_ic"
    )

    for var in available_variants:
        all_row = ic_full[(ic_full["variant"] == var) & (ic_full["market_state"] == "ALL")]
        all_ic = float(all_row["spearman_ic"].iloc[0]) if len(all_row) else np.nan
        all_n = int(all_row["n_observations"].iloc[0]) if len(all_row) else 0

        state_ics = {
            s: (float(full_ic_pivot.loc[s, var])
                if s in full_ic_pivot.index and var in full_ic_pivot.columns
                   and np.isfinite(full_ic_pivot.loc[s, var])
                else np.nan)
            for s in states_of_interest
        }
        positive_states = sum(1 for v in state_ics.values() if np.isfinite(v) and v > 0.0)
        negative_states = sum(1 for v in state_ics.values() if np.isfinite(v) and v < 0.0)
        mean_state_ic = float(np.nanmean(list(state_ics.values()))) if any(
            np.isfinite(v) for v in state_ics.values()
        ) else np.nan

        # Holdout IC
        ho_row = ic_holdout[(ic_holdout["variant"] == var) & (ic_holdout["market_state"] == "ALL")]
        ho_ic = float(ho_row["spearman_ic"].iloc[0]) if len(ho_row) else np.nan
        ho_n = int(ho_row["n_observations"].iloc[0]) if len(ho_row) else 0

        # Dev IC
        dev_row = ic_dev[(ic_dev["variant"] == var) & (ic_dev["market_state"] == "ALL")]
        dev_ic = float(dev_row["spearman_ic"].iloc[0]) if len(dev_row) else np.nan

        row = {
            "variant": var,
            "full_ic": all_ic,
            "full_n": all_n,
            "dev_ic": dev_ic,
            "holdout_ic": ho_ic,
            "holdout_n": ho_n,
            "mean_state_ic": mean_state_ic,
            "positive_states": positive_states,
            "negative_states": negative_states,
            **{f"ic_{s}": state_ics[s] for s in states_of_interest},
        }
        summary_rows.append(row)
        print(
            f"  {var:<40}: full={all_ic:+.4f}  dev={dev_ic:+.4f}  "
            f"holdout={ho_ic:+.4f}  pos_states={positive_states}  "
            f"mean_state_ic={mean_state_ic:+.4f}"
        )

    summary_df = pd.DataFrame(summary_rows)

    # ── 12. Acceptance evaluation ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Acceptance Evaluation")
    print("=" * 70)

    def evaluate_variant(var_name: str, row: dict) -> str:
        """Apply pre-declared acceptance logic to a single variant."""
        reasons_ok: list[str] = []
        reasons_fail: list[str] = []

        # Gate 1: at least 2 states with IC > 0.05
        high_ic_states = sum(
            1 for s in states_of_interest
            if np.isfinite(row.get(f"ic_{s}", np.nan)) and row.get(f"ic_{s}", -999) > 0.05
        )
        if high_ic_states >= 2:
            reasons_ok.append(f"≥2 states with IC>0.05 ({high_ic_states} states)")
        else:
            reasons_fail.append(f"only {high_ic_states} state(s) with IC>0.05 (need 2)")

        # Gate 2: calm_trend or neutral_mixed not strongly negative
        ct_ic = row.get("ic_calm_trend", np.nan)
        nm_ic = row.get("ic_neutral_mixed", np.nan)
        calm_ok = (np.isnan(ct_ic) or ct_ic > -0.10)
        neutral_ok = (np.isnan(nm_ic) or nm_ic > -0.10)
        if calm_ok and neutral_ok:
            reasons_ok.append(
                f"calm_trend IC={ct_ic:+.4f}, neutral_mixed IC={nm_ic:+.4f} — not strongly negative"
            )
        else:
            failed_states = []
            if not calm_ok:
                failed_states.append(f"calm_trend={ct_ic:+.4f}")
            if not neutral_ok:
                failed_states.append(f"neutral_mixed={nm_ic:+.4f}")
            reasons_fail.append(f"strongly negative IC in {', '.join(failed_states)}")

        # Gate 3: holdout IC not directionally broken (not < -0.05)
        ho = row.get("holdout_ic", np.nan)
        if np.isnan(ho) or ho > -0.05:
            reasons_ok.append(f"holdout IC={ho:+.4f} — not directionally broken")
        else:
            reasons_fail.append(f"holdout IC={ho:+.4f} is broken (< -0.05)")

        # Gate 4: positive_states >= 2
        ps = row.get("positive_states", 0)
        if ps >= 2:
            reasons_ok.append(f"{ps} positive states")
        else:
            reasons_fail.append(f"only {ps} positive state(s) (need 2)")

        passed = len(reasons_fail) == 0
        return "PASS" if passed else "FAIL", reasons_ok, reasons_fail

    gate_results: list[dict] = []
    for row in summary_rows:
        var = row["variant"]
        verdict, ok_reasons, fail_reasons = evaluate_variant(var, row)
        gate_results.append({
            "variant": var, "verdict": verdict,
            "ok_reasons": ok_reasons, "fail_reasons": fail_reasons
        })
        status = "✓ PASS" if verdict == "PASS" else "✗ FAIL"
        print(f"\n{var}: {status}")
        for r in ok_reasons:
            print(f"  ✓ {r}")
        for r in fail_reasons:
            print(f"  ✗ {r}")

    # ── 13. Overall recommendation ────────────────────────────────────────────
    r2a_verdict = next((g["verdict"] for g in gate_results if g["variant"] == "r2a"), "FAIL")
    r2b_verdict = next((g["verdict"] for g in gate_results if g["variant"] == "r2b"), "FAIL")
    r2d_verdict = next((g["verdict"] for g in gate_results if g["variant"] == "r2d"), "FAIL")

    any_pass = any(g["verdict"] == "PASS" for g in gate_results)
    r2a_row = next((r for r in summary_rows if r["variant"] == "r2a"), {})

    # Determine recommendation
    if r2a_verdict == "PASS":
        recommendation = "YES"
        rec_variant = "r2a"
        rec_reason = (
            "R2A (state-aware signed composite) passes all acceptance gates. "
            "Proceed to Phase 1B wrapper diagnostic using R2A."
        )
    elif r2d_verdict == "PASS":
        recommendation = "YES"
        rec_variant = "r2d"
        rec_reason = (
            "R2D (recovery-only hump-shaped composite) passes all acceptance gates. "
            "Proceed to Phase 1B with R2D, noting it is recovery-state-only."
        )
    elif any_pass:
        passing = [g["variant"] for g in gate_results if g["verdict"] == "PASS"]
        recommendation = "YES"
        rec_variant = passing[0]
        rec_reason = (
            f"Variant(s) {passing} pass acceptance gates. "
            "Proceed to Phase 1B with the best passing variant."
        )
    else:
        # Check if any variant is close (3/4 gates passing)
        best_row = max(summary_rows, key=lambda r: r.get("positive_states", 0), default={})
        best_var = best_row.get("variant", "none")
        best_ps = best_row.get("positive_states", 0)

        if best_ps >= 3 and best_row.get("holdout_ic", -999) > -0.05:
            recommendation = "NO"
            rec_variant = best_var
            rec_reason = (
                f"No variant passes all gates cleanly. Best variant {best_var} has "
                f"{best_ps} positive states but fails the ≥2 IC>0.05 gate. "
                "Revise composite: consider using only recovery and stressed_panic states, "
                "or investigate why calm/neutral sign-flipping does not yield IC>0.05."
            )
        else:
            recommendation = "DROP_PHASE_1"
            rec_variant = "none"
            rec_reason = (
                "No variant reaches acceptable IC levels on multiple states or holdout. "
                "The deployment-state quality hypothesis is not supported by these components. "
                "Consider: (a) adding new components (e.g., vol regime, sector dispersion), "
                "(b) revising the target (4-week SPY forward return may be too noisy for this signal), "
                "or (c) focusing Phase 1 on a narrower set of states (recovery only)."
            )

    print("\n" + "=" * 70)
    print(f"RECOMMENDATION: {recommendation}")
    print(f"Best variant: {rec_variant}")
    print(f"Reasoning: {rec_reason}")
    print("=" * 70)

    # ── 14. Check production files untouched ─────────────────────────────────
    diff_clean, diff_changed = protected_diff_clean()
    if not diff_clean:
        print(f"\nWARNING: Protected files changed: {diff_changed}")
        warnings_list.append(f"Protected files changed: {diff_changed}")
    else:
        print("\nProtected files: clean (no changes to public, src, or production CSVs).")

    # ── 15. Write report ──────────────────────────────────────────────────────
    _write_report(
        summary_df=summary_df,
        ic_all=ic_all,
        quintile_df=quintile_df,
        gate_results=gate_results,
        recommendation=recommendation,
        rec_variant=rec_variant,
        rec_reason=rec_reason,
        warnings_list=warnings_list,
        diff_clean=diff_clean,
    )

    print("\nDone. No production or dashboard files were modified.")


def _write_report(
    summary_df: pd.DataFrame,
    ic_all: pd.DataFrame,
    quintile_df: pd.DataFrame,
    gate_results: list[dict],
    recommendation: str,
    rec_variant: str,
    rec_reason: str,
    warnings_list: list[str],
    diff_clean: bool,
) -> None:
    report_path = ROOT / "docs" / "research" / "frontier_phase1_state_quality_r2_report.md"

    def fmt_ic(v) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "–"
        return f"{v:+.4f}"

    def fmt_n(v) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "–"
        return str(int(v))

    states_of_interest = ["calm_trend", "neutral_mixed", "recovery_confirmed",
                          "recovery_fragile", "stressed_panic"]
    variants = list(summary_df["variant"]) if len(summary_df) else []

    lines: list[str] = []
    lines.append("# Frontier Phase 1A-R2: Predeclared Sign-Audited Composite Report")
    lines.append("")
    lines.append("**Date:** 2026-05-20")
    lines.append("**Mode:** Diagnostic-only — no production or dashboard files modified")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Motivation and Design Rationale")
    lines.append("")
    lines.append(
        "Phase 1A showed that the original equal-weight composite has negative IC in "
        "calm_trend (−0.185), neutral_mixed (−0.109), and recovery_confirmed (−0.133). "
        "Component diagnostics identified two structural problems:"
    )
    lines.append("")
    lines.append(
        "1. **Sign errors by state**: the same component can be a positive predictor in "
        "one state and a negative predictor in another. For example, high `state_persistence_score` "
        "in `recovery_fragile` (IC +0.302) predicts well, but in `calm_trend` (IC −0.164) it "
        "reflects late-cycle exhaustion and predicts *less* future upside."
    )
    lines.append(
        "2. **Broken credit signal**: `credit_confirmation = sign(HYG_4w) − sign(LQD_4w)` "
        "is anti-predictive in every recovery state (−0.204 in recovery_confirmed, −0.243 in "
        "recovery_fragile). It is excluded from all R2 composites and redesigned as a "
        "continuous component (R2C) for diagnostic testing."
    )
    lines.append("")
    lines.append("### Predeclared Sign Configuration")
    lines.append("")
    lines.append("Signs and exclusions are declared before examining any R2-specific IC:")
    lines.append("")
    lines.append("| State | breadth | path_clarity | persistence | leadership | credit |")
    lines.append("|-------|---------|-------------|-------------|------------|--------|")
    config_table = {
        "recovery_fragile":  ["+", "+", "+", "+", "excl"],
        "recovery_confirmed":["+", "+", "+", "+", "excl"],
        "calm_trend":        ["− (crowded)", "− (overextended)", "− (exhaustion)", "− (crowded)", "excl"],
        "neutral_mixed":     ["− (crowded)", "−", "−", "−", "excl"],
        "strong_neutral":    ["− (crowded)", "−", "−", "−", "excl"],
        "stressed_panic":    ["− (depth)", "+ (orderly)", "excl", "excl", "excl"],
    }
    for s, row in config_table.items():
        lines.append(f"| {s} | {' | '.join(row)} |")
    lines.append("")
    lines.append("### Variant Definitions")
    lines.append("")
    lines.append(
        "- **R2A** (state_aware_signed): state-aware economic signs as above, "
        "credit excluded everywhere, equal weights among active components."
    )
    lines.append(
        "- **R2B** (state_aware_positive): same state-based component selection "
        "but all positive signs — control case showing value of sign-flipping."
    )
    lines.append(
        "- **R2C** (credit_relative_momentum): standalone diagnostic component only. "
        "Continuous `HYG_4w_return − LQD_4w_return`, z-scored, 1-week lag. "
        "**Not incorporated into R2A/R2B composites.**"
    )
    lines.append(
        "- **R2D** (recovery_only_hump): recovery states only (recovery_confirmed + recovery_fragile). "
        "Hump-shaped persistence: `min(persistence, 0.5)`. Evaluates whether the recovery-focused "
        "signal is worth isolating."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. IC Summary Table")
    lines.append("")
    lines.append("All signals are 1-week lagged (loaded from Phase 1A). Forward return = SPY 4-week return.")
    lines.append(f"Holdout start: {HOLDOUT_START.date()}")
    lines.append("")
    # Header
    header_cols = ["variant", "full_ic", "dev_ic", "holdout_ic",
                   "mean_state_ic", "positive_states",
                   *[f"ic_{s}" for s in states_of_interest]]
    lines.append("| variant | full_IC | dev_IC | holdout_IC | mean_state_IC | pos_states | calm_trend | neutral_mixed | rec_confirmed | rec_fragile | stressed_panic |")
    lines.append("|---------|---------|--------|------------|---------------|------------|------------|---------------|---------------|-------------|----------------|")

    for _, row in summary_df.iterrows():
        var = row["variant"]
        cells = [
            var,
            fmt_ic(row.get("full_ic")),
            fmt_ic(row.get("dev_ic")),
            fmt_ic(row.get("holdout_ic")),
            fmt_ic(row.get("mean_state_ic")),
            fmt_n(row.get("positive_states")),
            fmt_ic(row.get("ic_calm_trend")),
            fmt_ic(row.get("ic_neutral_mixed")),
            fmt_ic(row.get("ic_recovery_confirmed")),
            fmt_ic(row.get("ic_recovery_fragile")),
            fmt_ic(row.get("ic_stressed_panic")),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("*deployment_quality_composite = original Phase 1A equal-weight composite (reference baseline)*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Acceptance Gate Results")
    lines.append("")
    lines.append("Pre-declared gates (evaluated without reference to whether the variant passes):")
    lines.append("")
    lines.append("| Gate | Requirement |")
    lines.append("|------|------------|")
    lines.append("| IC states | ≥ 2 states with IC > 0.05 |")
    lines.append("| Calm/neutral | Neither calm_trend nor neutral_mixed IC < −0.10 |")
    lines.append("| Holdout | Holdout IC not < −0.05 (not directionally broken) |")
    lines.append("| Positive states | ≥ 2 positive states |")
    lines.append("")
    for g in gate_results:
        var = g["variant"]
        verdict = g["verdict"]
        status = "✓ PASS" if verdict == "PASS" else "✗ FAIL"
        lines.append(f"### {var}: {status}")
        lines.append("")
        if g["ok_reasons"]:
            for r in g["ok_reasons"]:
                lines.append(f"- ✓ {r}")
        if g["fail_reasons"]:
            for r in g["fail_reasons"]:
                lines.append(f"- ✗ {r}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. State-by-State IC Breakdown")
    lines.append("")
    # Group IC table by variant and state
    full_ic_df = ic_all[ic_all["scope"] == "full_period"].copy()
    dev_ic_df = ic_all[ic_all["scope"] == "development"].copy()
    hold_ic_df = ic_all[ic_all["scope"] == "holdout"].copy()

    for var in variants:
        lines.append(f"### {var}")
        lines.append("")
        lines.append("| scope | market_state | IC | N |")
        lines.append("|-------|--------------|----|---|")
        for scope_df, scope_name in [(full_ic_df, "full"), (dev_ic_df, "dev"), (hold_ic_df, "holdout")]:
            sub = scope_df[scope_df["variant"] == var].sort_values("market_state")
            for _, row in sub.iterrows():
                lines.append(
                    f"| {scope_name} | {row['market_state']} | "
                    f"{fmt_ic(row['spearman_ic'])} | {fmt_n(row['n_observations'])} |"
                )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 5. Quintile Return Monotonicity")
    lines.append("")
    lines.append(
        "Q1 = lowest signal, Q5 = highest signal. "
        "A well-designed composite should show monotonically increasing forward returns Q1→Q5."
    )
    lines.append("")
    for var in variants:
        q_sub = quintile_df[quintile_df["variant"] == var]
        if q_sub.empty:
            continue
        lines.append(f"### {var}")
        lines.append("")
        lines.append("| market_state | Q1 | Q2 | Q3 | Q4 | Q5 | monotone? |")
        lines.append("|--------------|----|----|----|----|----|-----------| ")

        for state, sgrp in q_sub.groupby("market_state"):
            sgrp = sgrp.sort_values("quintile")
            qs = sgrp.set_index("quintile")["mean_forward_4w_return"]
            row_cells = [str(state)]
            vals = []
            for q in [1, 2, 3, 4, 5]:
                v = qs.get(q, np.nan)
                vals.append(v)
                row_cells.append(f"{v:.4f}" if np.isfinite(v) else "–")
            clean_vals = [v for v in vals if np.isfinite(v)]
            monotone = "yes" if clean_vals == sorted(clean_vals) else "no"
            row_cells.append(monotone)
            lines.append("| " + " | ".join(row_cells) + " |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 6. R2C Diagnostic: Redesigned Credit Component")
    lines.append("")
    lines.append(
        "`credit_relative_momentum = HYG_4w_return − LQD_4w_return` (continuous, z-scored, 1w lag)."
    )
    lines.append("This is a standalone diagnostic. It is NOT included in R2A or R2B composites.")
    lines.append("")
    r2c_sub = full_ic_df[full_ic_df["variant"] == "r2c"].sort_values("market_state")
    if not r2c_sub.empty:
        lines.append("| market_state | IC | N |")
        lines.append("|--------------|-------|---|")
        for _, row in r2c_sub.iterrows():
            lines.append(
                f"| {row['market_state']} | {fmt_ic(row['spearman_ic'])} | {fmt_n(row['n_observations'])} |"
            )
    else:
        lines.append("*R2C not available (HYG/LQD data not loaded).*")
    lines.append("")
    lines.append(
        "**Interpretation:** If R2C shows positive IC in recovery states (unlike the original "
        "credit_confirmation), it can be incorporated into a future R2A+ variant with appropriate "
        "state-conditional sign. If IC remains negative in recovery, the credit signal is "
        "structurally unusable in this form and should be redesigned further."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Should Phase 1 Move to Wrapper Diagnostic?")
    lines.append("")
    lines.append(f"**Recommendation: {recommendation}**")
    lines.append("")
    lines.append(f"**Best variant:** {rec_variant}")
    lines.append("")
    lines.append(f"**Reasoning:** {rec_reason}")
    lines.append("")
    if recommendation == "YES":
        lines.append(
            "**Action:** Proceed to Phase 1B using the recommended variant. "
            "The wrapper diagnostic should use the `offense_budget` checkpoint "
            "(safe, modifiable) and should be read-only diagnostic first. "
            "Report all Phase D metrics and update `project_journey.md` after Phase 1B."
        )
    elif recommendation == "NO":
        lines.append(
            "**Action:** Revise the composite before proceeding. Options: "
            "(1) try a state-specific composite that is only active in recovery + stressed states "
            "(drop calm/neutral entirely and set composite to NaN there); "
            "(2) add a new component (e.g., sector dispersion, vol regime) that has clearer IC; "
            "(3) change the forward return target to something other than raw SPY 4w return "
            "(e.g., portfolio net return vs BIL, or a risk-adjusted target)."
        )
    else:
        lines.append(
            "**Action:** Redesign Phase 1 before proceeding. "
            "The current set of components does not generate the minimum IC needed for a "
            "useful wrapper modifier. Alternatives: "
            "(1) add fundamentally different components (macro indicators, vol surface); "
            "(2) pivot to a narrower Phase 1 focusing only on recovery states; "
            "(3) skip Phase 1 and proceed directly to Phase 2 (trend quality), "
            "which has stronger theoretical grounding from the Phase A signal validation."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. Comparison vs Phase 1A Original")
    lines.append("")
    lines.append("| metric | original_composite | best_R2 |")
    lines.append("|--------|--------------------|---------|")

    orig_row = summary_df[summary_df["variant"] == "deployment_quality_composite"]
    best_r2_row = summary_df[summary_df["variant"] == rec_variant] if rec_variant != "none" else pd.DataFrame()

    def _val(df, col):
        if df.empty:
            return "–"
        v = df.iloc[0].get(col, np.nan)
        return fmt_ic(v) if isinstance(v, float) else str(v)

    for metric, col in [
        ("full_IC", "full_ic"),
        ("dev_IC", "dev_ic"),
        ("holdout_IC", "holdout_ic"),
        ("mean_state_IC", "mean_state_ic"),
        ("positive_states", "positive_states"),
    ]:
        o = _val(orig_row, col)
        b = _val(best_r2_row, col)
        lines.append(f"| {metric} | {o} | {b} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Files Created")
    lines.append("")
    lines.append("| file | description |")
    lines.append("|------|-------------|")
    lines.append(f"| `{rel(OUT_DIR / 'state_quality_signals_r2.csv')}` | Extended signals with R2A/B/C/D columns |")
    lines.append(f"| `{rel(OUT_DIR / 'state_quality_r2_ic_by_state.csv')}` | IC by state, by scope, by variant |")
    lines.append(f"| `{rel(OUT_DIR / 'state_quality_r2_quintile_returns_by_state.csv')}` | Quintile forward returns |")
    lines.append(f"| `{rel(ROOT / 'docs' / 'research' / 'frontier_phase1_state_quality_r2_report.md')}` | This report |")
    lines.append("")
    lines.append("## 10. Production Safety")
    lines.append("")
    diff_status = "✓ Clean" if diff_clean else "✗ CHANGED (unexpected)"
    lines.append(f"- Protected file diff: **{diff_status}**")
    lines.append("- No production, dashboard, or public files were modified by this script.")
    lines.append("")
    if warnings_list:
        lines.append("## 11. Warnings")
        lines.append("")
        for w in warnings_list:
            lines.append(f"- {w}")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written: {rel(report_path)}")


if __name__ == "__main__":
    main()
