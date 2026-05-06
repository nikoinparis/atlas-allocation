from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import phase_h_refined_panel_allocator as ph


ROOT = Path(__file__).resolve().parents[1]
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"
REFERENCE_PANEL_VERSION = "improved_phaseh_reference_core_blend"

PHASE_I_CANDIDATES = {
    "improved_phasei_smooth_state_allocator": "R1 smoother holdout-aware state allocator",
    "improved_phasei_tail_disciplined_allocator": "R2 tail-disciplined role allocator",
    "improved_phasei_turnover_aware_allocator": "R3 turnover-aware allocator refinement",
    "improved_phasei_robust_role_allocator": "R4 best justified robust combo",
}

SAFE_ANCHOR = pd.Series(
    {
        "dual_momentum_topn": 0.05,
        "composite_calm_trend_specialist": 0.10,
        "composite_healthier_recovery_specialist": 0.07,
        "composite_anti_chop_clarity": 0.28,
        "composite_regime_conditioned": 0.32,
        "taa_10m_sma": 0.18,
    },
    dtype=float,
)
SAFE_ANCHOR = SAFE_ANCHOR / SAFE_ANCHOR.sum()

EQUAL_RISKY = pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return EQUAL_RISKY.copy()
    return clean / total


def bounded_normalize(
    weights: pd.Series,
    floors: dict[str, float] | None = None,
    caps: dict[str, float] | None = None,
) -> pd.Series:
    lower = pd.Series(0.0, index=ph.ACTIVE_PANEL, dtype=float)
    upper = pd.Series(1.0, index=ph.ACTIVE_PANEL, dtype=float)
    if floors:
        for sleeve, value in floors.items():
            lower[sleeve] = max(lower[sleeve], float(value))
    if caps:
        for sleeve, value in caps.items():
            upper[sleeve] = min(upper[sleeve], float(value))
    if float(lower.sum()) >= 0.999:
        lower = lower / lower.sum()
    upper = np.maximum(upper, lower)

    projected = normalize(weights).clip(lower=lower, upper=upper)
    for _ in range(12):
        diff = 1.0 - float(projected.sum())
        if abs(diff) <= 1e-10:
            break
        slack = (upper - projected) if diff > 0 else (projected - lower)
        slack = slack[slack > 1e-12]
        if slack.empty:
            break
        step = slack / float(slack.sum()) * diff
        projected.loc[slack.index] = projected.loc[slack.index] + step
        projected = projected.clip(lower=lower, upper=upper)
    return normalize(projected)


def centered_rank(series: pd.Series) -> pd.Series:
    return ph.centered_rank(series.reindex(ph.ACTIVE_PANEL).fillna(0.0))


def confidence_frame(state_prior: pd.DataFrame, simple_score_panel: pd.DataFrame, state_features: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(index=state_prior.index)
    frame["prior_gap"] = state_prior.max(axis=1) - state_prior.median(axis=1)
    frame["prior_top2_gap"] = state_prior.max(axis=1) - state_prior.apply(lambda row: row.nlargest(2).iloc[-1], axis=1)
    frame["score_gap"] = simple_score_panel.max(axis=1) - simple_score_panel.median(axis=1)
    frame["state_confidence"] = state_features[["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].max(axis=1)
    frame["persistence"] = state_features["transition_persistence_prob"].clip(0.0, 1.0)
    frame["risk_guard"] = state_features[["stress_confidence", "chop_confidence"]].max(axis=1)
    frame["conviction"] = (
        0.30 * ph.bounded_zero_to_one(frame["prior_gap"], 0.015, 0.090)
        + 0.20 * ph.bounded_zero_to_one(frame["prior_top2_gap"], 0.010, 0.070)
        + 0.25 * ph.bounded_zero_to_one(frame["score_gap"], 0.030, 0.220)
        + 0.15 * frame["state_confidence"]
        + 0.10 * frame["persistence"]
    ).clip(0.0, 1.0)
    return frame


def role_aware_target(
    base_state: pd.Series,
    simple_score: pd.Series,
    st: pd.Series,
    confidence: pd.Series,
) -> pd.Series:
    blend = 0.18 + 0.18 * confidence["conviction"]
    strength = 0.22 + 0.38 * confidence["conviction"]
    score = 0.75 * centered_rank(simple_score) + 0.25 * centered_rank(base_state)
    target = ph.tilted_weights(
        normalize(base_state),
        score,
        blend=blend,
        strength=strength,
        multiplier_floor=0.68,
        multiplier_cap=1.45,
    )

    floors: dict[str, float] = {}
    caps: dict[str, float] = {}
    if st["calm_confidence"] >= max(st["recovery_confidence"], st["stress_confidence"], st["chop_confidence"]):
        floors["composite_calm_trend_specialist"] = 0.22 + 0.04 * st["calm_confidence"]
        floors["taa_10m_sma"] = 0.17 + 0.03 * st["calm_confidence"]
        caps["composite_anti_chop_clarity"] = 0.12
        caps["composite_regime_conditioned"] = 0.13
        caps["composite_healthier_recovery_specialist"] = 0.25
    if st["recovery_confidence"] >= max(st["calm_confidence"], st["stress_confidence"], st["chop_confidence"]):
        floors["composite_healthier_recovery_specialist"] = 0.22 + 0.05 * st["recovery_confidence"]
        floors["dual_momentum_topn"] = 0.15
        caps["composite_anti_chop_clarity"] = 0.14
        caps["composite_regime_conditioned"] = 0.14
    if st["stress_confidence"] > 0.48 or st["chop_confidence"] > 0.52:
        floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.22 + 0.10 * st["stress_confidence"])
        floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.18 + 0.10 * st["chop_confidence"])
        floors["taa_10m_sma"] = max(floors.get("taa_10m_sma", 0.0), 0.12)
        caps["dual_momentum_topn"] = 0.12
        caps["composite_healthier_recovery_specialist"] = min(caps.get("composite_healthier_recovery_specialist", 1.0), 0.16)
        caps["composite_calm_trend_specialist"] = min(caps.get("composite_calm_trend_specialist", 1.0), 0.18)
    return bounded_normalize(target, floors=floors, caps=caps)


def limited_move(prev_weights: pd.Series, target_weights: pd.Series, alpha: float, max_l1_step: float) -> pd.Series:
    candidate = normalize((1.0 - alpha) * prev_weights + alpha * target_weights)
    diff = candidate - prev_weights
    l1_step = float(diff.abs().sum())
    if l1_step <= max_l1_step or l1_step <= 1e-12:
        return candidate
    return normalize(prev_weights + diff * (max_l1_step / l1_step))


def build_candidate_weights(
    candidate_name: str,
    base_state_weights: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    state_features: pd.DataFrame,
    confidence: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[pd.Series] = []
    prev_weights: pd.Series | None = None
    prev_role_target: pd.Series | None = None
    prev_state = None

    for date in base_state_weights.index:
        st = state_features.loc[date]
        conf = confidence.loc[date]
        base_state = normalize(base_state_weights.loc[date, ph.ACTIVE_PANEL])
        role_target = role_aware_target(base_state, simple_score_panel.loc[date], st, conf)
        base_plus_role = normalize(0.82 * base_state + 0.18 * role_target)
        state_changed = prev_state is not None and st["state_text"] != prev_state

        if candidate_name == "improved_phasei_smooth_state_allocator":
            target = base_state if prev_role_target is None else normalize(0.76 * prev_role_target + 0.24 * base_state)
            if state_changed and conf["state_confidence"] > 0.62:
                target = normalize(0.55 * (prev_role_target if prev_role_target is not None else target) + 0.45 * base_state)
            if conf["risk_guard"] > 0.46:
                target = normalize(0.78 * base_state + 0.22 * SAFE_ANCHOR)
            if prev_weights is None:
                risky = target
            else:
                alpha = (0.12 + 0.16 * conf["conviction"]) * (0.84 + 0.16 * conf["persistence"])
                if state_changed:
                    alpha += 0.04 * conf["state_confidence"]
                if conf["risk_guard"] > 0.46:
                    alpha = max(alpha, 0.34)
                if float((target - prev_weights).abs().sum()) < 0.08:
                    alpha *= 0.35
                max_step = 0.07 + 0.03 * conf["conviction"]
                if conf["risk_guard"] > 0.46:
                    max_step = max(max_step, 0.12)
                risky = limited_move(prev_weights, target, min(alpha, 0.38), max_step)
        elif candidate_name == "improved_phasei_tail_disciplined_allocator":
            safe_mix = min(0.10 + 0.22 * max(conf["risk_guard"], 1.0 - conf["conviction"]), 0.28)
            target = normalize((1.0 - safe_mix) * base_state + safe_mix * SAFE_ANCHOR)
            floors: dict[str, float] = {}
            caps: dict[str, float] = {"dual_momentum_topn": 0.17, "composite_healthier_recovery_specialist": 0.23}
            if conf["risk_guard"] > 0.45:
                floors["composite_regime_conditioned"] = 0.24
                floors["composite_anti_chop_clarity"] = 0.19
                floors["taa_10m_sma"] = 0.12
                caps["dual_momentum_topn"] = 0.10
                caps["composite_calm_trend_specialist"] = 0.18
                caps["composite_healthier_recovery_specialist"] = 0.15
            target = bounded_normalize(target, floors=floors, caps=caps)
            if prev_weights is None:
                risky = target
            else:
                alpha = 0.15 + 0.12 * conf["conviction"] - 0.04 * conf["risk_guard"]
                risky = limited_move(prev_weights, target, float(np.clip(alpha, 0.10, 0.24)), 0.06 + 0.03 * conf["conviction"])
        elif candidate_name == "improved_phasei_turnover_aware_allocator":
            target = normalize(0.92 * base_state + 0.08 * role_target)
            if conf["risk_guard"] > 0.48:
                target = normalize(0.86 * base_state + 0.14 * SAFE_ANCHOR)
            if prev_weights is None:
                risky = target
            else:
                l1_gap = float((target - prev_weights).abs().sum())
                threshold = 0.10 - 0.03 * conf["conviction"]
                if not state_changed and conf["risk_guard"] < 0.45 and l1_gap < threshold:
                    risky = prev_weights.copy()
                else:
                    alpha = 0.14 + 0.12 * conf["conviction"] + (0.05 if state_changed and conf["state_confidence"] > 0.60 else 0.0)
                    if conf["risk_guard"] > 0.48:
                        alpha = max(alpha, 0.30)
                    max_step = 0.05 + 0.03 * conf["conviction"]
                    if conf["risk_guard"] > 0.48:
                        max_step = max(max_step, 0.10)
                    risky = limited_move(prev_weights, target, min(alpha, 0.34), max_step)
        elif candidate_name == "improved_phasei_robust_role_allocator":
            target = base_plus_role if prev_role_target is None else normalize(0.58 * prev_role_target + 0.42 * base_plus_role)
            safe_mix = min(0.06 + 0.14 * conf["risk_guard"] + 0.06 * (1.0 - conf["conviction"]), 0.20)
            target = normalize((1.0 - safe_mix) * target + safe_mix * SAFE_ANCHOR)
            floors: dict[str, float] = {}
            caps: dict[str, float] = {}
            if st["calm_confidence"] > 0.62 and st["stress_confidence"] < 0.32:
                floors["composite_calm_trend_specialist"] = 0.23
                floors["taa_10m_sma"] = 0.18
                caps["composite_anti_chop_clarity"] = 0.10
                caps["composite_regime_conditioned"] = 0.11
            if st["recovery_confidence"] > 0.62 and st["stress_confidence"] < 0.35:
                floors["composite_healthier_recovery_specialist"] = 0.23
                floors["dual_momentum_topn"] = 0.15
                caps["composite_anti_chop_clarity"] = min(caps.get("composite_anti_chop_clarity", 1.0), 0.12)
            if conf["risk_guard"] > 0.48:
                floors["composite_regime_conditioned"] = max(floors.get("composite_regime_conditioned", 0.0), 0.22)
                floors["composite_anti_chop_clarity"] = max(floors.get("composite_anti_chop_clarity", 0.0), 0.18)
                caps["dual_momentum_topn"] = 0.10
                caps["composite_healthier_recovery_specialist"] = min(caps.get("composite_healthier_recovery_specialist", 1.0), 0.16)
                caps["composite_calm_trend_specialist"] = min(caps.get("composite_calm_trend_specialist", 1.0), 0.18)
            target = bounded_normalize(target, floors=floors, caps=caps)
            if prev_weights is None:
                risky = target
            else:
                alpha = 0.14 + 0.14 * conf["conviction"] + (0.05 if state_changed and conf["state_confidence"] > 0.64 else 0.0)
                if float((target - prev_weights).abs().sum()) < 0.09:
                    alpha *= 0.30
                risky = limited_move(prev_weights, target, min(alpha, 0.30), 0.06 + 0.03 * conf["conviction"])
        else:
            raise ValueError(f"Unknown candidate {candidate_name}")

        row = pd.Series(0.0, index=ph.ACTIVE_PANEL + [ph.CASH_COLUMN], dtype=float, name=date)
        row.loc[ph.ACTIVE_PANEL] = normalize(risky)
        rows.append(row)
        prev_weights = normalize(risky)
        prev_role_target = role_target
        prev_state = st["state_text"]

    frame = pd.DataFrame(rows).sort_index().fillna(0.0)
    return frame.div(frame.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def main() -> None:
    next_week_returns, active_returns, active_positions, _, market_state_history = ph.load_inputs()
    state_features = ph.state_feature_frame(active_returns.index, market_state_history)
    state_prior = ph.role_alignment_score(state_features)
    _, _, simple_score_panel = ph.build_feature_panels(active_returns, state_features, state_prior)
    confidence = confidence_frame(state_prior, simple_score_panel, state_features)

    base_state_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv")
    base_state_weights = base_state_weights.reindex(state_prior.index).fillna(0.0)

    universe_columns = list(next_week_returns.columns)

    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []

    for version_name in PHASE_I_CANDIDATES:
        sleeve_weights = build_candidate_weights(
            version_name,
            base_state_weights,
            simple_score_panel,
            state_features,
            confidence,
        )
        etf_weights = ph.build_lookthrough_weights(sleeve_weights, active_positions, universe_columns)
        path = ph.save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)
        state_rows.append(ph.state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = ph.sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        conc_summary, conc_state = ph.concentration_summary(sleeve_weights, market_state_history, version_name)
        concentration_rows.append(conc_summary)
        concentration_state_rows.append(conc_state)
        variant_rows.append(
            {
                "version_name": version_name,
                "ann_return": ph.annualized_return(path["net_return"]),
                "ann_vol": ph.annualized_vol(path["net_return"]),
                "sharpe": ph.annualized_return(path["net_return"]) / ph.annualized_vol(path["net_return"]) if ph.annualized_vol(path["net_return"]) > 0 else np.nan,
                "max_drawdown": ph.max_drawdown(path["net_return"]),
                "turnover": float(path["turnover"].mean()),
                "avg_bil": float(etf_weights.get("BIL", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_spy": float(etf_weights.get("SPY", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_role_share_new": float(
                    sleeve_weights[["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]].sum(axis=1).mean()
                ),
            }
        )

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_i_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_i_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_i_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_i_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_i_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_i_concentration_by_state.csv", index=False)

    protocol = {
        "phase": "Phase I",
        "purpose": "Focused allocator refinement on refined redesigned sleeve panel",
        "reference_panel_version": REFERENCE_PANEL_VERSION,
        "active_panel_baseline": ACTIVE_PANEL_BASELINE,
        "current_refined_allocator_reference": CURRENT_REFINED_REFERENCE,
        "candidate_versions": PHASE_I_CANDIDATES,
        "guiding_principles": [
            "preserve role-aware sleeve use",
            "smooth state-to-state transitions",
            "improve tail control in stressed and weak-separation states",
            "reduce unnecessary turnover",
        ],
    }
    (LAYER3_DIR / "phase_i_allocator_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase I allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_i_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_i_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_i_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_i_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_i_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_i_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_i_allocator_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
