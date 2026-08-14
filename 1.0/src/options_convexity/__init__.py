"""Options Convexity Overlay Research (standalone research module).

This package is a SEPARATE research experiment. It is intentionally NOT a
"Track" (not Track A/B/C/D) and it does NOT modify, import, or change any
production allocation logic. It only *reads* existing project artifacts
(baseline ETF weights, regime/market-state history, weekly prices) and studies
whether a small, rarely-active options sleeve could improve upside capture
during rare, high-confidence bullish setups.

Nothing in this package should ever be imported by production code, and running
this package must never write to production data directories. All generated
output goes to ``data/research/options_convexity/``.

Module map
----------
- ``option_data``     : load prices / weights / states, build causal signals.
- ``option_pricing``  : Black-Scholes pricing, call-spread premium and payoff.
- ``option_selection``: DTE / moneyness / liquidity filters, spread building.
- ``overlay_rules``   : the v0 activation rules and position sizing.
- ``backtest_overlay``: historical proxy overlay backtest + baseline vs overlay.
- ``metrics``         : performance metrics (same conventions as production).
"""

__all__ = [
    "option_data",
    "option_pricing",
    "option_selection",
    "overlay_rules",
    "backtest_overlay",
    "metrics",
]
