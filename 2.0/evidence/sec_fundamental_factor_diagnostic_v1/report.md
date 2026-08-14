# SEC fundamental factor diagnostic v1

Tested five predeclared point-in-time families across the current 20-company technology/energy pilot. The best factor was `growth` with holdout CAGR **36.14%**, Sharpe **1.512**, and drawdown **-24.48%** after 50-bps costs.

The best benchmark was `benchmark::XLK` at **31.70%**. Factor beats benchmark: **True**. Decision: `retain_factor_family_for_survivorship_safe_retest`.

This is not a promotable result. The universe contains today's surviving companies, has no historical membership or delisted stocks, and uses revision-prone free adjusted prices. The experiment diagnoses economic direction only and cannot alter any frozen strategy.
