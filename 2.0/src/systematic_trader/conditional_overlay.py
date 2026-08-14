"""Past-only gating and two-sleeve accounting for conditional overlays."""

from __future__ import annotations


def overlay_path(
    core: list[dict[str, object]], factor: list[dict[str, object]], active: list[bool], *,
    maximum_factor_weight: float, top_level_cost_bps: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if len(core) != len(factor) or len(core) != len(active):
        raise ValueError("core, factor, and active states must align")
    previous_drifted_factor_weight = 0.0
    rows = []
    maximum_identity_error = 0.0
    for core_row, factor_row, is_active in zip(core, factor, active):
        if core_row["realization_date"] != factor_row["realization_date"]:
            raise ValueError("realization dates do not align")
        target = maximum_factor_weight if is_active else 0.0
        turnover = abs(target - previous_drifted_factor_weight)
        core_return = float(core_row["net_return"])
        factor_return = float(factor_row["net_return"])
        before_allocation_cost = (1.0 - target) * core_return + target * factor_return
        allocation_cost = turnover * top_level_cost_bps / 10_000.0
        net = before_allocation_cost - allocation_cost
        maximum_identity_error = max(maximum_identity_error, abs(net - (before_allocation_cost - allocation_cost)))
        previous_drifted_factor_weight = (
            target * (1.0 + factor_return) / (1.0 + before_allocation_cost)
            if 1.0 + before_allocation_cost > 0.0 else 0.0
        )
        rows.append({
            "decision_date": core_row["decision_date"],
            "realization_date": core_row["realization_date"],
            "active": is_active,
            "factor_target_weight": target,
            "core_net_return": core_return,
            "factor_net_return": factor_return,
            "allocation_turnover": turnover,
            "allocation_cost": allocation_cost,
            "net_return": net,
        })
    return rows, {
        "observations": len(rows),
        "maximum_return_identity_error": maximum_identity_error,
        "return_identity_pass": maximum_identity_error <= 1e-15,
        "minimum_weight": 0.0 if not rows else min(float(row["factor_target_weight"]) for row in rows),
        "maximum_weight": 0.0 if not rows else max(float(row["factor_target_weight"]) for row in rows),
    }
