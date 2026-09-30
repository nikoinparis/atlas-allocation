# A15 — frozen choices from 2019-2022, before any 2023 or full-window number was read

*Written 2026-09-30 after `--phase train`. Registration:
`docs/BRAIN_A15_PREREGISTRATION_V1.md` (commit d2a8b94). Machine-readable:
`evidence/worldquant_brain_a15_v1/train.json` and `train_summary.csv`. No full-window (2019-2023)
statistic and no 2023 row of any simulation has been printed or scored at this point. The
runner's ladder/control phases printed only "done in Ns"; the density probes printed counts only.*

## What happened before this file

- **Density probes (15):** every variant readable. Non-zero share of the 3,000-name universe:
  - H1: 0.69 / 0.78 / 0.94
  - H2: 0.88 / 0.98 / 0.94
  - H3: 0.84 / 0.84 / 0.76
  - H4: 1.01 (three identical probes)
  - H5: 0.94 / 0.94 / 0.97

  The B5 rebuild worked: recommendation changes went from 0.3% dense in Step 326 to 69-94%.
- **Ladders, production forms and controls:** 15 × 11 + 50. One timeout (H4a decile 1, no alpha
  was created) was re-run once. It is counted as a trial.

## Train (2019-2022) results — per decile, the mean of the four yearly returns

The declared no-skill control for each hypothesis is market cap on the same mask:

| control | full | middle-8 | names scored |
|---|---|---|---|
| C1 | −0.321 | −0.738 | 3,132 |
| C2 | −0.042 | −0.357 | 3,132 |
| C3 | −0.018 | −0.143 | 3,086 |
| C4 | +0.030 | −0.310 | 3,132 |
| C5 | −0.370 | −0.833 | 3,123 |

All five pass their own tie check.

"Years +" counts the train years with positive monotonicity. "Perm. p" is the permutation p.

| variant | full | mid-8 | d10−d1 | years + | perm. p | T1 | T2 | T3 | T4 | T5 | train verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1a Δ63 | +0.636 | +0.452 | +13.3pp | 3/4 | 0.024 | ✗ | ✓ | ✓ | ✓ | ✗ | concentration |
| H1b Δ126 | +0.830 | +0.667 | +16.6pp | 3/4 | 0.0024 | ✓ | ✓ | ✓ | ✓ | ✗ | orders, fails Bonferroni |
| H1c last change | +0.697 | +0.905 | +12.6pp | 4/4 | 0.00093 | ✓ | ✓ | ✓ | ✓ | ✗ | orders, fails Bonferroni |
| H2a −\|d−63\| | +0.758 | +0.714 | +11.2pp | 4/4 | 0.0050 | ✓ | ✓ | ✓ | ✓ | ✗ | orders, fails Bonferroni |
| H2b −\|d−58\| | +0.806 | +0.714 | +10.6pp | 4/4 | 0.0031 | ✓ | ✓ | ✓ | ✓ | ✗ | orders, fails Bonferroni |
| **H2c sales −\|d−63\|** | **+0.927** | **+0.952** | +10.3pp | 4/4 | **3.5e-5** | ✓ | ✓ | ✓ | ✓ | ✓ | **passes train** |
| H3a af yoy | +0.467 | +0.619 | +7.7pp | 4/4 | 0.029 | ✗ | ✓ | ✓ | ✓ | ✗ | flat |
| H3b qf yoy | +0.248 | +0.190 | +6.5pp | 3/4 | 0.18 | ✗ | ✓ | ✓ | ✓ | ✗ | flat |
| H3c rec yoy | +0.297 | +0.310 | +2.0pp | 2/4 | 0.12 | ✗ | ✓ | **✗ ties** | ✗ | ✗ | UNREADABLE (ties) |
| H4a sector | −0.224 | −0.548 | +3.3pp | 2/4 | 0.73 | ✗ | ✗ | ✓ | ✗ | ✗ | flat |
| H4b industry | −0.055 | −0.214 | +3.6pp | 2/4 | 0.51 | ✗ | ✗ | ✓ | ✗ | ✗ | flat |
| H4c subindustry | +0.067 | −0.214 | +2.7pp | 2/4 | 0.40 | ✗ | ✓ | ✓ | ✗ | ✗ | flat |
| H5a 30d | −0.321 | −0.762 | +14.0pp | 3/4 | 0.82 | ✗ | ✓ | ✓ | ✓ | ✗ | flat (all in decile 1) |
| H5b 90d | −0.297 | −0.714 | +13.9pp | 2/4 | 0.80 | ✗ | ✓ | ✓ | ✗ | ✗ | flat (all in decile 1) |
| H5c 30d mean21 | +0.406 | +0.690 | +11.9pp | 3/4 | 0.022 | ✗ | ✓ | ✓ | ✓ | ✗ | flat |

T5's bar is 0.05 / 828 = 6.04e-5.

H5's spread is the concentration shape this project has recorded many times: decile 1 at about
−14% to −15% a year, deciles 2-10 flat or falling. H4 does not order in either direction and
alternates sign by year (2019 −0.7, 2020 +0.9, 2022 −0.6).

## Frozen best variant per hypothesis (declared rule: largest train full + middle-8)

| hypothesis | frozen variant | passes train? | can pass A15? |
|---|---|---|---|
| H1 recommendation change (B5) | H1c_lastchange126 | no (T5) | **no** |
| H2 earnings-announcement premium | **H2c_salesdist63** | **yes** | yes, subject to K1, K2, P1, P2 |
| H3 analyst coverage change | H3a_numest_af_yoy | no (T1, T5) | **no** |
| H4 long-term growth forecast | H4c_ltg_subindustry | no | **no** |
| H5 implied − realized vol | H5c_ivrv30_mean21 | no | **no** |

**Kill tests will run for H2c only.** K1 is de-sized, within market-cap quintiles. K2 is
momentum-neutral, within 63-day-return quintiles. That is 20 simulations.

### Known weakness of the one survivor, recorded before its holdout is read

- **The field is not live in 2023.** H2c's field (`anl4_fs_actuals_basic_qf_nd_sales_value`) was
  created on BRAIN in 2026-03. Its 2023 read is therefore a holdout for *our selection* but is
  loaded vendor history, not live data. H2a and H2b use the field that was live from 2022-07. They
  order in train but fail Bonferroni, and they are not frozen.
- **The three H2 variants are one idea.** They are near-identical constructions of it. H2c's pass
  is partly the best-of-three pick that the train rule was declared to make.

## Kill-test train results

*(appended below after `--phase kill` and `--phase trainkill`, still before any 2023 read)*
