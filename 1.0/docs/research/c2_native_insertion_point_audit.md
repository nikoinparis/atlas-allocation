# C2 Native Insertion Point Audit

Research-only audit of possible confidence insertion points inside the GGG plumbing. This sprint tests small no-write proxies for the most relevant locations.

| insertion_point | order | safe_inputs | lookahead_risk | expected_effect | danger | stress_defense |
| --- | --- | --- | --- | --- | --- | --- |
| regime_multiplier_offset | inside overlay, before target-vol/cash budget finalization | lagged breadth, macro stress, transition probability | low if inputs are tradable/lagged | small risky-budget confidence nudge | can fight target-vol or add offense in stress | preserved only if no stress increase |
| offensive_sleeve_budget_offset | after state tilt, before final look-through | offense eligibility, breadth, transition quality | low | change offense sleeve share without touching defense sleeves | hidden beta increase | preserved if disabled in stressed_panic |
| defensive_sleeve_budget_offset | after state tilt, before overlay | macro stress, deterioration, volatility pressure | low | increase defense budget in deterioration | miss recovery re-risk | usually preserved |
| cash_BIL_budget_offset | overlay/cash budget step | macro stress, target-vol binding, deterioration | low | cash absorbs confidence cuts | cash drag in calm/recovery | preserved if asymmetric |
| rerisk_timing_offset | sleeve reallocation speed before overlay | transition quality, breadth persistence | medium if transition labels not lagged | faster participation after confirmed broad transitions | whipsaw | preserved if never used in stress |
| derisk_timing_offset | sleeve reallocation speed / overlay before look-through | deterioration score, macro stress, dollar pressure | low | faster risk reduction in deteriorating environments | false alarms reduce return | preserved or improved |
| transition_aware_smoothing | between state tilt and overlay | state age, transition quality, breadth confirmation | medium; requires strict lag | avoid abrupt bad transitions | late re-risk | preserved if stress entry remains fast |
| vol_target_aware_confidence | inside target-vol overlay interaction | target-vol binding diagnostics, confidence | low if uses current allocation-date vol estimate | avoid adding risk when vol target already binds | double-counting volatility pressure | preserved |
| sleeve_level_confidence_modifier | before ETF look-through | sleeve role, breadth, macro stress | low | role-aware confidence changes | requires exact sleeve-to-ETF reconstruction | depends on sleeve role controls |
| final_post_allocation_modifier | after final ETF weights | all lagged confidence inputs | low | simple safety check/comparison | not allocator-native; can violate overlay intent | preserved if disabled in stress |

## Recommendation

- Prefer regime/risky-budget, transition timing, and deterioration timing insertion points over final post-allocation scaling.
- Final post-allocation bounded modifier is included only as a comparison because it was the best prior sandbox family.
- A true production implementation would need a no-write wrapper around the allocator/overlay function, not edits to production artifacts.

## Warnings

- None.
