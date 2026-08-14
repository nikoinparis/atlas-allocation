# Stress-Period Sanity Checks — V3

**All periods pass: True**

## Required: 2008 Financial Crisis, March 2020 COVID, Late 2022 Rate Shock

Pass criterion: dominant state is `stress` or `overheating`, OR ≥50% weeks classified as stress/overheating.

| Period | N weeks | Dominant State | % Stress/Overheat | Mean growth_factor | Mean fc_proxy | Pass? |
| --- | --- | --- | --- | --- | --- | --- |
| 2008_crisis | 30 | stress | 100% | -8.253 | 2.515 | ✓ |
| covid_crash_2020 | 15 | stress | 87% | -5.251 | 1.524 | ✓ |
| rate_shock_2022 | 22 | overheating | 91% | 0.425 | 0.462 | ✓ |

---
*Research artifact — no production code modified.*
