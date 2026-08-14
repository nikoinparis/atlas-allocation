"""Guarded, replaceable boundaries around third-party research components."""

from .bt import lag_signals_one_bar
from .flashalpha import SafeFillResult, simulate_flashalpha_safely

__all__ = ["SafeFillResult", "lag_signals_one_bar", "simulate_flashalpha_safely"]
