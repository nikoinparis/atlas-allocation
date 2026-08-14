# Batch 66B — adversarial challenge of the 52% retrospective ceiling

The frozen rule returned **52.35%** at 50 bps, **46.74%** at 100 bps, and **36.07%** at 200 bps versus XLK **31.72%**.

Adversarial confirmation: **False**. Failed gates: `excluded_best_year, rolling, multifactor_alpha`. Neighborhood share beating XLK: **71.1%**; delay share: **66.7%**; placebo percentile: **98.5%**; past-only selector: **41.72%**.

The strictly past-only selector returned **41.72%** at 50 bps, **36.78%** at 100 bps, and **27.34%** at 200 bps. Selector confirmation: **False**; failed gates: `delays, rolling, multifactor_alpha, full_drawdown, raw_pvalue`.

Decision: `retain_52pct_ceiling_and_past_only_selector_as_unconfirmed_high_return_research`. The rule remains explicitly marked as retrospectively selected. No leverage or live trading was enabled.
