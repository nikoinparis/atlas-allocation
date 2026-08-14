"""Signal family definitions for recovery prediction research."""

FAMILIES = {
    "drawdown_reversal": {
        "score": "score_drawdown_reversal",
        "description": "drawdown depth plus early recovery confirmation",
    },
    "short_horizon_reversal": {
        "score": "score_short_horizon_reversal",
        "description": "recent weakness reversing in non-panic/stabilizing states",
    },
    "breadth_thrust": {
        "score": "score_breadth_thrust",
        "description": "risky asset participation and breadth acceleration",
    },
    "credit_improvement": {
        "score": "score_credit_improvement",
        "description": "HYG/LQD and HYG/SHY confirmation",
    },
    "volatility_normalization": {
        "score": "score_volatility_normalization",
        "description": "VIX/realized volatility stress fading without late-entry collapse",
    },
    "momentum_reversal_interaction": {
        "score": "score_momentum_reversal_interaction",
        "description": "medium-term trend, pullback, rebound and risk confirmation interaction",
    },
}

FAMILY_SCORE_COLUMNS = [v["score"] for v in FAMILIES.values()]


def family_for_score(score_col: str) -> str:
    for name, meta in FAMILIES.items():
        if meta["score"] == score_col:
            return name
    return score_col

