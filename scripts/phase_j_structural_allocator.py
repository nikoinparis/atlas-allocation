from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import phase_h_refined_panel_allocator as ph
import phase_i_refined_allocator_refinement as pi


ROOT = Path(__file__).resolve().parents[1]
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"
REFERENCE_PANEL_VERSION = "improved_phaseh_reference_core_blend"

PHASE_J_CANDIDATES = {
    "improved_phasej_robust_objective_allocator": "S1 objective-based robust allocator",
    "improved_phasej_margin_confidence_allocator": "S2 confidence-margin allocator",
    "improved_phasej_turnover_tail_allocator": "S3 turnover-and-tail-aware allocator",
    "improved_phasej_structural_combo_allocator": "S4 structural combo allocator",
}

EPS = 1e-9


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)
    return clean / total


def top_margin(series: pd.Series) -> float:
    values = pd.Series(series, dtype=float).sort_values(ascending=False)
    if len(values) < 2:
        return 0.0
    return float(values.iloc[0] - values.iloc[1])


def top_median_gap(series: pd.Series) -> float:
    values = pd.Series(series, dtype=float)
    return float(values.max() - values.median())


def risk_penalty_vector(st: pd.Series) -> pd.Series:
    penalty = pd.Series(index=ph.ACTIVE_PANEL, dtype=float)
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))
    uncertainty = 1.0 - float(st[["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].max())
    for sleeve in ph.ACTIVE_PANEL:
        role = ph.ROLE_MAP[sleeve]
        offense_penalty = 0.60 * (1.0 - role["defense"]) + 0.40 * (1.0 - role["chop"])
        structural_relief = 0.35 * role["defense"] + 0.25 * role["chop"]
        penalty[sleeve] = risk_guard * offense_penalty + 0.25 * uncertainty * (1.0 - structural_relief)
    return penalty.fillna(0.0)


def dynamic_bounds(st: pd.Series, margin_conf: float, agreement: float) -> tuple[dict[str, float], dict[str, float]]:
    floors = {sleeve: 0.04 for sleeve in ph.ACTIVE_PANEL}
    caps = {sleeve: 0.36 for sleeve in ph.ACTIVE_PANEL}
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))
    state_conf = float(st[["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].max())
    high_conviction = margin_conf > 0.62 and agreement > 0.45 and risk_guard < 0.42

    if high_conviction:
        caps = {sleeve: 0.42 for sleeve in ph.ACTIVE_PANEL}

    if st["calm_confidence"] >= max(st["recovery_confidence"], st["stress_confidence"], st["chop_confidence"]):
        floors["composite_calm_trend_specialist"] = 0.16 + 0.05 * st["calm_confidence"]
        floors["taa_10m_sma"] = 0.16 + 0.03 * st["calm_confidence"]
        caps["composite_regime_conditioned"] = min(caps["composite_regime_conditioned"], 0.14 if risk_guard < 0.35 else 0.20)
        caps["composite_anti_chop_clarity"] = min(caps["composite_anti_chop_clarity"], 0.14 if risk_guard < 0.35 else 0.18)

    if st["recovery_confidence"] >= max(st["calm_confidence"], st["stress_confidence"], st["chop_confidence"]):
        floors["composite_healthier_recovery_specialist"] = 0.16 + 0.06 * st["recovery_confidence"]
        floors["dual_momentum_topn"] = max(floors["dual_momentum_topn"], 0.10 + 0.03 * st["recovery_confidence"])
        caps["composite_regime_conditioned"] = min(caps["composite_regime_conditioned"], 0.18)
        caps["composite_anti_chop_clarity"] = min(caps["composite_anti_chop_clarity"], 0.18)

    if risk_guard > 0.45:
        floors["composite_regime_conditioned"] = max(floors["composite_regime_conditioned"], 0.18 + 0.12 * st["stress_confidence"])
        floors["composite_anti_chop_clarity"] = max(floors["composite_anti_chop_clarity"], 0.15 + 0.10 * st["chop_confidence"])
        floors["taa_10m_sma"] = max(floors["taa_10m_sma"], 0.12)
        caps["dual_momentum_topn"] = min(caps["dual_momentum_topn"], 0.12)
        caps["composite_healthier_recovery_specialist"] = min(caps["composite_healthier_recovery_specialist"], 0.18)
        caps["composite_calm_trend_specialist"] = min(caps["composite_calm_trend_specialist"], 0.20)

    if state_conf < 0.45:
        for sleeve in ph.ACTIVE_PANEL:
            caps[sleeve] = min(caps[sleeve], 0.28)

    return floors, caps


def opportunity_frame(
    state_prior: pd.DataFrame,
    simple_score_panel: pd.DataFrame,
    learned_score_panel: pd.DataFrame,
    reference_weights: pd.DataFrame,
    state_features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.Series] = []
    meta_rows: list[pd.Series] = []
    for date in state_prior.index:
        prior_rank = ph.centered_rank(state_prior.loc[date, ph.ACTIVE_PANEL])
        simple_rank = ph.centered_rank(simple_score_panel.loc[date, ph.ACTIVE_PANEL])
        learned_rank = ph.centered_rank(learned_score_panel.loc[date, ph.ACTIVE_PANEL])
        ref_rank = ph.centered_rank(reference_weights.loc[date, ph.ACTIVE_PANEL])
        score = 0.42 * simple_rank + 0.28 * learned_rank + 0.20 * prior_rank + 0.10 * ref_rank

        top_simple = str(simple_rank.idxmax())
        top_learned = str(learned_rank.idxmax())
        top_ref = str(ref_rank.idxmax())
        agreement = np.mean(
            [
                float(top_simple == top_learned),
                float(top_simple == top_ref),
                float(top_learned == top_ref),
            ]
        )
        margin_simple = top_margin(simple_rank)
        margin_learned = top_margin(learned_rank)
        margin_score = top_margin(score)
        margin_conf = float(
            np.clip(
                0.30 * ph.bounded_zero_to_one(margin_score, 0.02, 0.60)
                + 0.20 * ph.bounded_zero_to_one(margin_simple, 0.02, 0.60)
                + 0.15 * ph.bounded_zero_to_one(margin_learned, 0.02, 0.60)
                + 0.20 * float(agreement)
                + 0.15 * float(
                    state_features.loc[date, ["calm_confidence", "recovery_confidence", "stress_confidence", "chop_confidence"]].max()
                ),
                0.0,
                1.0,
            )
        )
        rows.append(score.rename(date))
        meta_rows.append(
            pd.Series(
                {
                    "margin_confidence": margin_conf,
                    "agreement": float(agreement),
                    "score_top_gap": margin_score,
                    "score_top_median_gap": top_median_gap(score),
                },
                name=date,
            )
        )
    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(meta_rows).sort_index()


def project_weights(values: pd.Series, floors: dict[str, float], caps: dict[str, float]) -> pd.Series:
    return pi.bounded_normalize(values, floors=floors, caps=caps)


def optimize_quadratic_objective(
    initial: pd.Series,
    anchor: pd.Series,
    prev_weights: pd.Series,
    opportunity: pd.Series,
    risk_penalty: pd.Series,
    *,
    lambda_anchor: float,
    lambda_prev: float,
    lambda_hhi: float,
    lambda_tail: float,
    floors: dict[str, float],
    caps: dict[str, float],
) -> pd.Series:
    denom = max(lambda_anchor + lambda_prev + lambda_hhi, EPS)
    unconstrained = (
        lambda_anchor * anchor
        + lambda_prev * prev_weights
        + opportunity
        - lambda_tail * risk_penalty
    ) / denom
    return normalize(project_weights(unconstrained, floors, caps))


def optimize_entropy_objective(
    initial: pd.Series,
    anchor: pd.Series,
    prev_weights: pd.Series,
    opportunity: pd.Series,
    risk_penalty: pd.Series,
    *,
    lambda_anchor: float,
    lambda_prev: float,
    lambda_tail: float,
    entropy_tau: float,
    floors: dict[str, float],
    caps: dict[str, float],
) -> pd.Series:
    logits = (opportunity - lambda_tail * risk_penalty) / max(entropy_tau, EPS)
    logits = logits - float(logits.max())
    soft = np.exp(logits).clip(lower=EPS)
    soft = soft / float(soft.sum())
    combined = (
        soft
        + lambda_anchor * anchor
        + lambda_prev * prev_weights
    ) / max(1.0 + lambda_anchor + lambda_prev, EPS)
    return normalize(project_weights(combined, floors, caps))


def optimize_huber_objective(
    initial: pd.Series,
    anchor: pd.Series,
    prev_weights: pd.Series,
    opportunity: pd.Series,
    risk_penalty: pd.Series,
    *,
    lambda_anchor: float,
    lambda_turnover: float,
    lambda_hhi: float,
    lambda_tail: float,
    floors: dict[str, float],
    caps: dict[str, float],
) -> pd.Series:
    base = optimize_quadratic_objective(
        initial,
        anchor,
        prev_weights,
        opportunity,
        risk_penalty,
        lambda_anchor=lambda_anchor,
        lambda_prev=0.0,
        lambda_hhi=lambda_hhi,
        lambda_tail=lambda_tail,
        floors=floors,
        caps=caps,
    )
    step = 1.0 / max(1.0 + lambda_turnover, 1.0)
    prox = normalize((1.0 - step) * prev_weights + step * base)
    return normalize(project_weights(prox, floors, caps))


def build_candidate_weights(
    candidate_name: str,
    reference_weights: pd.DataFrame,
    opportunity: pd.DataFrame,
    meta: pd.DataFrame,
    state_features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.Series] = []
    control_rows: list[pd.Series] = []
    prev_weights: pd.Series | None = None

    for date in reference_weights.index:
        ref = normalize(reference_weights.loc[date, ph.ACTIVE_PANEL])
        prev = ref.copy() if prev_weights is None else prev_weights.copy()
        opp = opportunity.loc[date, ph.ACTIVE_PANEL]
        st = state_features.loc[date]
        margin_conf = float(meta.loc[date, "margin_confidence"])
        agreement = float(meta.loc[date, "agreement"])
        risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))
        floors, caps = dynamic_bounds(st, margin_conf, agreement)
        risk_penalty = risk_penalty_vector(st)
        safe_mix = min(0.10 + 0.25 * risk_guard + 0.08 * (1.0 - margin_conf), 0.35)
        anchor = normalize((1.0 - safe_mix) * ref + safe_mix * pi.SAFE_ANCHOR)
        initial = prev if prev_weights is not None else anchor

        if candidate_name == "improved_phasej_robust_objective_allocator":
            risky = optimize_quadratic_objective(
                initial,
                anchor,
                prev,
                opp,
                risk_penalty,
                lambda_anchor=1.25 - 0.45 * margin_conf,
                lambda_prev=0.95 - 0.25 * margin_conf,
                lambda_hhi=0.60 - 0.25 * margin_conf + 0.45 * risk_guard,
                lambda_tail=0.70 * risk_guard + 0.25 * (1.0 - margin_conf),
                floors=floors,
                caps=caps,
            )
            control = {
                "anchor_weight": 1.25 - 0.45 * margin_conf,
                "prev_weight": 0.95 - 0.25 * margin_conf,
                "tail_weight": 0.70 * risk_guard + 0.25 * (1.0 - margin_conf),
                "margin_confidence": margin_conf,
                "agreement": agreement,
            }
        elif candidate_name == "improved_phasej_margin_confidence_allocator":
            entropy_tau = 1.05 - 0.75 * margin_conf - 0.20 * agreement + 0.25 * risk_guard
            risky = optimize_entropy_objective(
                initial,
                anchor,
                prev,
                opp,
                risk_penalty,
                lambda_anchor=1.05 - 0.30 * margin_conf,
                lambda_prev=0.75 - 0.20 * margin_conf,
                lambda_tail=0.65 * risk_guard + 0.12 * (1.0 - margin_conf),
                entropy_tau=max(0.18, entropy_tau),
                floors=floors,
                caps=caps,
            )
            control = {
                "entropy_tau": max(0.18, entropy_tau),
                "anchor_weight": 1.05 - 0.30 * margin_conf,
                "prev_weight": 0.75 - 0.20 * margin_conf,
                "margin_confidence": margin_conf,
                "agreement": agreement,
            }
        elif candidate_name == "improved_phasej_turnover_tail_allocator":
            risky = optimize_huber_objective(
                initial,
                anchor,
                prev,
                opp,
                risk_penalty,
                lambda_anchor=1.10 - 0.25 * margin_conf,
                lambda_turnover=0.95 - 0.45 * margin_conf + 0.25 * risk_guard,
                lambda_hhi=0.35 + 0.45 * risk_guard,
                lambda_tail=0.85 * risk_guard + 0.18 * (1.0 - margin_conf),
                floors=floors,
                caps=caps,
            )
            control = {
                "turnover_weight": 0.95 - 0.45 * margin_conf + 0.25 * risk_guard,
                "tail_weight": 0.85 * risk_guard + 0.18 * (1.0 - margin_conf),
                "anchor_weight": 1.10 - 0.25 * margin_conf,
                "margin_confidence": margin_conf,
                "agreement": agreement,
            }
        elif candidate_name == "improved_phasej_structural_combo_allocator":
            entropy_tau = 0.85 - 0.55 * margin_conf - 0.10 * agreement + 0.18 * risk_guard
            combo_opp = 0.75 * opp + 0.25 * ph.centered_rank(ref)
            combo_anchor = normalize(0.85 * anchor + 0.15 * prev)
            risky = optimize_entropy_objective(
                initial,
                combo_anchor,
                prev,
                combo_opp,
                risk_penalty,
                lambda_anchor=1.15 - 0.30 * margin_conf,
                lambda_prev=0.85 - 0.25 * margin_conf,
                lambda_tail=0.75 * risk_guard + 0.16 * (1.0 - margin_conf),
                entropy_tau=max(0.16, entropy_tau),
                floors=floors,
                caps=caps,
            )
            risky = optimize_huber_objective(
                risky,
                combo_anchor,
                prev,
                combo_opp,
                risk_penalty,
                lambda_anchor=0.70,
                lambda_turnover=0.45 + 0.20 * risk_guard,
                lambda_hhi=0.20 + 0.30 * risk_guard,
                lambda_tail=0.45 * risk_guard,
                floors=floors,
                caps=caps,
            )
            control = {
                "entropy_tau": max(0.16, entropy_tau),
                "turnover_weight": 0.45 + 0.20 * risk_guard,
                "tail_weight": 0.75 * risk_guard + 0.16 * (1.0 - margin_conf),
                "margin_confidence": margin_conf,
                "agreement": agreement,
            }
        else:
            raise ValueError(candidate_name)

        row = pd.Series(0.0, index=ph.ACTIVE_PANEL + [ph.CASH_COLUMN], dtype=float, name=date)
        row.loc[ph.ACTIVE_PANEL] = normalize(risky)
        rows.append(row)
        control_rows.append(pd.Series(control, name=date))
        prev_weights = normalize(risky)

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(control_rows).sort_index()


def control_summary(candidate_name: str, controls: pd.DataFrame, concentration: pd.DataFrame, meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = controls.join(meta, how="left", rsuffix="_meta").fillna(0.0)
    merged["margin_bucket"] = pd.cut(
        merged["margin_confidence"],
        bins=[-1e-9, 0.33, 0.66, 1.0],
        labels=["low", "medium", "high"],
    )
    overall = pd.DataFrame(
        [
            {
                "version_name": candidate_name,
                "avg_margin_confidence": float(merged["margin_confidence"].mean()),
                "avg_agreement": float(merged["agreement"].mean()),
                "avg_score_top_gap": float(meta["score_top_gap"].mean()),
                "avg_score_top_median_gap": float(meta["score_top_median_gap"].mean()),
                "avg_top1_share": float(concentration["avg_top1_share"].iloc[0]),
                "avg_top2_share": float(concentration["avg_top2_share"].iloc[0]),
            }
        ]
    )
    bucket_rows: list[dict[str, float | str]] = []
    for bucket, group in merged.groupby("margin_bucket", observed=False):
        if group.empty:
            continue
        bucket_rows.append(
            {
                "version_name": candidate_name,
                "margin_bucket": str(bucket),
                "observations": int(len(group)),
                "avg_margin_confidence": float(group["margin_confidence"].mean()),
                "avg_agreement": float(group["agreement"].mean()),
            }
        )
    return overall, pd.DataFrame(bucket_rows)


def main() -> None:
    next_week_returns, active_returns, active_positions, _, market_state_history = ph.load_inputs()
    state_features = ph.state_feature_frame(active_returns.index, market_state_history)
    state_prior = ph.role_alignment_score(state_features)
    long_panel, date_panel, simple_score_panel = ph.build_feature_panels(active_returns, state_features, state_prior)

    panel_feature_cols = [col for col in long_panel.columns if col not in {"Date", "sleeve", "target_return_4w"}]
    learned_model = ph.walkforward_panel_regressor(long_panel, panel_feature_cols)
    learned_scores = learned_model.prediction_frame.reindex(state_prior.index).fillna(0.0)

    reference_weights = ph.read_panel_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv")
    reference_weights = reference_weights.reindex(state_prior.index).fillna(0.0)

    opportunity, meta = opportunity_frame(state_prior, simple_score_panel, learned_scores, reference_weights, state_features)
    universe_columns = list(next_week_returns.columns)

    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    control_rows: list[pd.DataFrame] = []
    control_bucket_rows: list[pd.DataFrame] = []

    for version_name in PHASE_J_CANDIDATES:
        sleeve_weights, controls = build_candidate_weights(version_name, reference_weights, opportunity, meta, state_features)
        etf_weights = ph.build_lookthrough_weights(sleeve_weights, active_positions, universe_columns)
        path = ph.save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)
        state_rows.append(ph.state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = ph.sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        conc_summary, conc_state = ph.concentration_summary(sleeve_weights, market_state_history, version_name)
        concentration_rows.append(conc_summary)
        concentration_state_rows.append(conc_state)
        ctrl_summary, ctrl_bucket = control_summary(version_name, controls, conc_summary, meta)
        control_rows.append(ctrl_summary)
        control_bucket_rows.append(ctrl_bucket)

        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        variant_rows.append(
            {
                "version_name": version_name,
                "ann_return": ann_ret,
                "ann_vol": ann_vol,
                "sharpe": ann_ret / ann_vol if ann_vol > 0 else np.nan,
                "max_drawdown": ph.max_drawdown(path["net_return"]),
                "turnover": float(path["turnover"].mean()),
                "avg_bil": float(etf_weights.get("BIL", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_spy": float(etf_weights.get("SPY", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_role_share_new": float(
                    sleeve_weights[["composite_calm_trend_specialist", "composite_healthier_recovery_specialist", "composite_anti_chop_clarity"]].sum(axis=1).mean()
                ),
            }
        )

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_j_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_concentration_by_state.csv", index=False)
    pd.concat(control_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_control_summary.csv", index=False)
    pd.concat(control_bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_j_control_by_margin_bucket.csv", index=False)
    meta.to_csv(LAYER3_DIR / "phase_j_margin_signal_summary.csv")

    protocol = {
        "phase": "Phase J",
        "purpose": "Structural allocator redesign on refined redesigned sleeve panel",
        "current_refined_allocator_reference": CURRENT_REFINED_REFERENCE,
        "reference_panel_version": REFERENCE_PANEL_VERSION,
        "active_panel_baseline": ACTIVE_PANEL_BASELINE,
        "candidate_versions": PHASE_J_CANDIDATES,
        "design_principles": [
            "objective-based allocation around role-aware reference weights",
            "confidence-margin-aware concentration",
            "embedded turnover penalty",
            "embedded tail and concentration penalties",
        ],
    }
    (LAYER3_DIR / "phase_j_allocator_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase J allocator artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_j_allocator_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_j_allocator_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_j_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_j_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_j_concentration_summary.csv",
        "data/05_layer3_portfolio_construction/phase_j_concentration_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_j_control_summary.csv",
        "data/05_layer3_portfolio_construction/phase_j_control_by_margin_bucket.csv",
        "data/05_layer3_portfolio_construction/phase_j_margin_signal_summary.csv",
        "data/05_layer3_portfolio_construction/phase_j_allocator_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
