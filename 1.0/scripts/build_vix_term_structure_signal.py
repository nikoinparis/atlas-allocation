"""Build the R2 VIX term-structure candidate signal.

Research-only output. The signal uses existing weekly VIX term-structure data
and writes an observed value plus a one-week lagged tradable value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    HUB_DIR,
    SIGNAL_DIR,
    asset_risk_loading,
    ensure_parent,
    load_universe_metadata,
    load_weekly_prices,
    panel_from_series,
    parse_dates,
    read_csv_safe,
    robust_z,
)


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    metadata = load_universe_metadata(warnings)
    vix = read_csv_safe(HUB_DIR / "vix_term_structure.csv", warnings)
    vix = parse_dates(vix, warnings, "vix_term_structure.csv")

    if prices.empty:
        raise SystemExit("weekly_prices.csv is required to align the VIX term-structure signal.")

    project_dates = prices.index
    loadings = {
        row.ticker: asset_risk_loading(row.ticker, row.asset_class)
        for row in metadata.itertuples(index=False)
        if row.ticker in prices.columns
    }
    if vix.empty:
        signal = pd.Series(index=project_dates, dtype=float)
        notes = "Skipped/partial: vix_term_structure.csv missing or unreadable."
    else:
        vix = vix.set_index("Date").reindex(project_dates)
        slope13 = robust_z(pd.to_numeric(vix.get("slope_1m_3m"), errors="coerce"), 156, 52)
        slope16 = robust_z(pd.to_numeric(vix.get("slope_1m_6m"), errors="coerce"), 156, 52)
        vix_level = robust_z(pd.to_numeric(vix.get("VIX"), errors="coerce"), 156, 52)
        contango = pd.to_numeric(vix.get("contango"), errors="coerce").rolling(13, min_periods=4).mean()
        signal = slope13 + 0.5 * slope16 + 0.25 * (contango - 0.5) - 0.75 * vix_level
        notes = "Positive contango/low VIX is risk-on; backwardation/high VIX is defensive."
        if signal.notna().sum() < 100:
            warnings.append("VIX term-structure signal has fewer than 100 non-null observations.")

    panel = panel_from_series(
        signal,
        signal_name="r2_vix_term_structure",
        loadings=loadings,
        source="vix_term_structure.csv",
        frequency="weekly",
        notes=notes,
    )
    out = SIGNAL_DIR / "signal_r2_vix_term_structure.csv"
    ensure_parent(out)
    panel.to_csv(out, index=False)
    missing = panel["signal_value_tradable"].isna().mean() if len(panel) else np.nan
    print(f"Wrote {out} rows={len(panel)} tradable_missing={missing:.2%}" if pd.notna(missing) else f"Wrote {out} rows={len(panel)}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
