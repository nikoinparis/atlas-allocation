# C3 Confidence Inputs Report

Research-only normalized confidence inputs aligned to the exact GGG weekly index.

## Inputs Built

- `breadth_confidence`: ETF 50d/200d and 13w/26w breadth blend.
- `sector_confidence`: sector breadth blend.
- `risk_on_confidence`: risk-on participation.
- `macro_stress_filter`: VIX/credit/financial conditions stress filter, higher is safer.
- `dollar_pressure_filter`: higher means less dollar pressure.
- `transition_quality_score`: transition non-stress probability plus breadth/macro confirmation.
- `combined_market_quality_score`: conservative blend of breadth, sector, risk-on, transition, macro, dollar, and signal agreement.
- `offense_eligibility_score` and `deterioration_score`: diagnostic deployment features.

## Missingness

| field | missingness |
| --- | --- |
| breadth_confidence | 0.0000 |
| sector_confidence | 0.0000 |
| risk_on_confidence | 0.0000 |
| macro_stress_filter | 0.0000 |
| dollar_pressure_filter | 0.0000 |
| transition_quality_score | 0.0000 |
| signal_agreement | 0.0000 |
| signal_dispersion | 0.0000 |
| offense_eligibility_score | 0.0000 |
| deterioration_score | 0.0000 |
| combined_market_quality_score | 0.0000 |
| market_state | 0.0000 |
| risk_state | 0.0000 |
| macro_stress_active | 0.0000 |
| dollar_pressure_active | 0.0000 |
| offense_eligible | 0.0000 |

## Score Summary

| field | count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Date | 1110 | 2015-08-24 12:00:00 | nan | 2005-01-07 00:00:00 | 2010-05-01 18:00:00 | 2015-08-24 12:00:00 | 2020-12-16 06:00:00 | 2026-04-10 00:00:00 |
| breadth_confidence | 1110.0 | 0.5486326766690923 | 0.26359101238295213 | 0.011217948717948718 | 0.35646623638918157 | 0.5512434352795799 | 0.7667905011655012 | 1.0 |
| sector_confidence | 1110.0 | 0.5887617231910689 | 0.27408308864082037 | 0.014423076923076922 | 0.37419871794871795 | 0.6161858974358974 | 0.8218667108753315 | 1.0 |
| risk_on_confidence | 1110.0 | 0.6605183011013507 | 0.34653385754004384 | 0.019230769230769232 | 0.334070796460177 | 0.6223728457335015 | 1.0 | 1.0 |
| macro_stress_filter | 1110.0 | 0.5212404268402429 | 0.18946725581978668 | 0.0064102564102563875 | 0.4299791863232039 | 0.5072708113804004 | 0.6473754233188195 | 0.9663387000596303 |
| dollar_pressure_filter | 1110.0 | 0.4836469509201253 | 0.24580064379760047 | 0.0 | 0.3141826923076923 | 0.5 | 0.6565705128205128 | 0.9878205128205129 |
| transition_quality_score | 1110.0 | 0.6760340466681348 | 0.24757204627069349 | 0.08778846153846152 | 0.5825480769230769 | 0.7636939102564103 | 0.8589037632625994 | 0.9769207459207458 |
| signal_agreement | 1110.0 | 0.7294315972113453 | 0.3333772775619132 | 0.00641025641025641 | 0.5 | 1.0 | 1.0 | 1.0 |
| signal_dispersion | 1110.0 | 0.49535831409709874 | 0.28429926668587024 | 0.00641025641025641 | 0.26282051282051283 | 0.5 | 0.7369123931623932 | 1.0 |
| offense_eligibility_score | 1110.0 | 0.5892312516502468 | 0.2221805631574374 | 0.051686698717948724 | 0.43320753205128204 | 0.631763919044665 | 0.7756017965765276 | 0.9481965974159678 |
| deterioration_score | 1110.0 | 0.4448144657749652 | 0.18845486806533546 | 0.07190180540469371 | 0.2927684294871795 | 0.4183188339438339 | 0.5826923076923077 | 0.9256570512820512 |
| combined_market_quality_score | 1110.0 | 0.5968261020774828 | 0.21103656014736547 | 0.0757153846153846 | 0.45576987179487183 | 0.6377480125096346 | 0.7718770585302869 | 0.9462843159766776 |
| market_state | 1110 | nan | nan | nan | nan | nan | nan | nan |
| risk_state | 1110 | nan | nan | nan | nan | nan | nan | nan |
| macro_stress_active | 1110 | nan | nan | nan | nan | nan | nan | nan |
| dollar_pressure_active | 1110 | nan | nan | nan | nan | nan | nan | nan |
| offense_eligible | 1110 | nan | nan | nan | nan | nan | nan | nan |
| research_only | 1110 | nan | nan | nan | nan | nan | nan | nan |

## Causality Notes

- Existing Layer 1 signals use their `signal_value_tradable` columns where available.
- Newly composed C3 scores are shifted by one week before use.
- The scores are not optimized against returns.

## Warnings

- None.
