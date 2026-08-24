import numpy as np
import pandas as pd

from scripts.run_sec_residual_controlled_sleeve_v1 import blend, levered


def test_fixed_blend_is_convex_and_aligned():
    index = pd.date_range("2025-01-03", periods=3, freq="W-FRI")
    control = pd.Series([0.01, 0.02, -0.01], index=index)
    sleeve = pd.Series([0.03, -0.02, 0.01], index=index)
    result = blend(control, sleeve, 0.2)
    np.testing.assert_allclose(result, 0.8 * control + 0.2 * sleeve)


def test_leverage_charges_only_borrowed_fraction():
    values = pd.Series([0.01, -0.02])
    np.testing.assert_allclose(levered(values, 1.25, 0.052), 1.25 * values - 0.25 * 0.001)
