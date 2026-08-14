# Phase HHH — State-Conditional Stressed-Panic Offense Swap (extension of GGG1)

Date: 2026-04-27
Author: research stream

## A. Mission

Extend GGG1's state-conditional swap (broad EEE1 offense everywhere except
recovery_confirmed → FFF3 robust) to **also** swap the offense subset in
`stressed_panic`. GGG diagnostic showed filtered offense helps stressed_panic
by +0.41pp ann in the broad-vs-filtered comparison without weakening the
defensive route. This phase is one narrow Layer 2A test, three candidates
maximum. Recovery_fragile, neutral_mixed, calm_trend stay broad.

## B. Commands executed

```
python scripts/phase_hhh_state_conditional_stressed_offense.py
```
(No quick audits ran: per spec, audits are run only for KEEP AS SHADOW or
better. All three HHH candidates were rejected by the strict turnover gate.)

## C. Files created / modified

Modified:
- `scripts/build_improvement_artifacts.py`
  - Added 3 module-level state-conditional decomposition panels for HHH
    (`phasehhh_confirmed_stressed_robust_*`,
    `phasehhh_confirmed_robust_stressed_blended_*`,
    `phasehhh_confirmed_quality_stressed_robust_*`), all reusing the GGG
    `build_state_conditional_decomposition_sleeve_panels` builder.
  - Extended `internal_redeploy` dispatcher with three new modes
    (`phasehhh_confirmed_stressed_robust`,
    `phasehhh_confirmed_robust_stressed_blended`,
    `phasehhh_confirmed_quality_stressed_robust`).
  - Appended 3 version specs cloning GGG1 settings.

Created:
- `scripts/phase_hhh_state_conditional_stressed_offense.py` (driver).
- `data/research/phase_hhh_state_conditional_stressed_offense/phase_hhh_stressed_component_tradeoff.csv`
- `data/research/phase_hhh_state_conditional_stressed_offense/phase_hhh_filtered_vs_broad_by_state.csv`
- `data/research/phase_hhh_state_conditional_stressed_offense/phase_hhh_candidate_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_hhh_candidate_metrics_full.csv`
- `data/05_layer3_portfolio_construction/phase_hhh_state_summary.csv`
- `data/05_layer3_portfolio_construction/phase_hhh_selection_table.csv`
- `data/05_layer3_portfolio_construction/phase_hhh_protocol.json`
- 3 `portfolio_version_*_improved_phasehhh_*.csv` triplets.

## D. Stressed-panic broad vs filtered diagnosis

Re-confirmed from `phase_hhh_filtered_vs_broad_by_state.csv` (EEE1 broad vs FFF3 filtered, full-portfolio proxy):

| state              | n  | EEE1 broad ann% | FFF3 filtered ann% | Δ (pp) | filtered helps |
|--------------------|----|-----------------|--------------------|--------|----------------|
| calm_trend         |295 |   4.09          |   4.08             | −0.00  | no             |
| neutral_mixed      |493 |  11.21          |  10.88             | −0.33  | no             |
| recovery_confirmed | 44 |   2.26          |   2.61             | +0.35  | YES (GGG1 swap) |
| recovery_fragile   | 49 |   6.67          |   6.18             | −0.49  | no             |
| **stressed_panic** |229 |   3.59          |   4.00             | **+0.41** | **YES (HHH swap)** |

The diagnostic supports adding a stressed_panic swap; the mechanism (drop
PDBC + DBA in the recipe) reduces commodity exposure in the regime-conditioned
source positions during stress weeks.

## E. Candidate family

| ID   | Version name                                                  | RC offense                       | SP offense                          | Other states |
|------|---------------------------------------------------------------|----------------------------------|-------------------------------------|--------------|
| HHH1 | improved_phasehhh_confirmed_stressed_robust_offense           | FFF3 robust (8 ETFs)             | FFF3 robust (8 ETFs)                | broad EEE1   |
| HHH2 | improved_phasehhh_confirmed_robust_stressed_blended_offense   | FFF3 robust (8 ETFs)             | 0.5·broad + 0.5·FFF3                | broad EEE1   |
| HHH3 | improved_phasehhh_confirmed_quality_stressed_robust_offense   | FFF1 quality_filtered (7 ETFs)   | FFF3 robust (8 ETFs)                | broad EEE1   |

## F. Candidate metrics (full window)

| name                                          | Sharpe | Ann ret | MDD     | CVaR-5% | Turnover | Turn ratio | avg BIL | avg SPY |
|-----------------------------------------------|--------|---------|---------|---------|----------|------------|---------|---------|
| HHH1 confirmed_stressed_robust                | 0.9360 | 0.0718  | −0.1214 | −0.0256 | 0.1249   | **1.1117×**| 0.2705  | 0.0605  |
| HHH2 confirmed_robust + stressed_blended      | 0.9360 | 0.0714  | −0.1179 | −0.0254 | 0.1242   | **1.1054×**| 0.2660  | 0.0607  |
| HHH3 confirmed_quality + stressed_robust      | 0.9365 | 0.0718  | −0.1214 | −0.0256 | 0.1250   | **1.1125×**| 0.2705  | 0.0605  |
| GGG1 (primary architecture-reference shadow)  | 0.9366 | 0.0714  | −0.1177 | −0.0254 | 0.1236   | 1.0998×    | 0.2666  | 0.0603  |
| EEE1 (secondary shadow)                       | 0.9353 | 0.0713  | −0.1177 | −0.0254 | 0.1230   | 1.0945×    | 0.2665  | 0.0602  |
| FFF3 (Layer 2A reference)                     | 0.9144 | 0.0706  | −0.1208 | −0.0259 | 0.1229   | 1.0938×    | 0.2725  | 0.0624  |
| Production                                    | 0.8848 | 0.0689  | −0.1398 | −0.0262 | 0.1124   | 1.0000×    | 0.2839  | 0.0708  |

All three HHH candidates **fail the turnover gate** (1.10× cap). HHH2 (blended)
is closest but still over by 0.005×.

## G. State-by-state ann delta vs GGG1 (pp; 5 states)

| candidate | calm_trend | neutral_mixed | recovery_confirmed | recovery_fragile | stressed_panic |
|-----------|------------|---------------|--------------------|------------------|----------------|
| HHH1      |   −0.12    |   +0.03       |   −0.01            |   +0.00          |   **+0.30**    |
| HHH2      |   −0.06    |   +0.03       |   −0.01            |   +0.00          |   +0.02        |
| HHH3      |   −0.12    |   +0.03       |   **+0.07**        |   +0.00          |   **+0.30**    |

State-conditional construction worked **exactly as designed**:
- recovery_fragile vs GGG1: ~0.0pp on all three (preserved).
- neutral_mixed: +0.03pp on all three (well within noise / second-order
  allocator drift from the changed return panel).
- calm_trend: small −0.06 to −0.12pp drift (second-order; the recipe itself
  is unchanged in calm_trend).
- recovery_confirmed: HHH1/HHH2 essentially identical to GGG1 (RC recipe
  unchanged); HHH3 +0.07pp from the stronger quality_filtered RC recipe.
- stressed_panic: **+0.30pp on HHH1/HHH3** from the new SP swap, +0.02pp
  on HHH2 (blended is much weaker — half the swap captures only a fraction
  of the gain because the half kept on broad still drags PDBC/DBA exposure).

## H. Repair / preservation / protection checks

Stressed_panic protection (vs production — must not regress):
- HHH1 vs prod: +0.51pp ann (improved beyond GGG1's +0.21pp).
- HHH2 vs prod: +0.23pp ann (improved).
- HHH3 vs prod: +0.51pp ann (improved beyond GGG1's +0.21pp).
**All three improve stressed_panic vs both production and GGG1.**

Recovery_confirmed preservation (vs GGG1):
- HHH1: −0.02pp (essentially preserved).
- HHH2: −0.01pp (essentially preserved).
- HHH3: +0.07pp (further repair from quality_filtered RC swap).
**All three pass.**

Recovery_fragile preservation (vs GGG1):
- HHH1: +0.00pp.
- HHH2: +0.00pp.
- HHH3: −0.00pp.
**All three pass.**

## I. Hidden beta / hidden cash check

Avg SPY (HHH1): 6.05%, vs production 7.08% (−1.04pp), vs GGG1 6.03%
(+0.02pp). Avg BIL (HHH1): 27.05%, vs production 28.39% (−1.34pp, less cash
drag). Offense_component avg: 10.96% vs GGG1 9.78% (+1.18pp — the SP swap
itself does inflate offense_component slightly because the cash-fallback path
is different in the per-row normalisation). **No hidden beta** (SPY went
down vs production; up only marginally vs GGG1). **No hidden cash injection**
(BIL went down).

## J. Did state-conditional stressed-panic construction work?

**Mechanism: YES.** The only states whose realised returns shifted materially
vs GGG1 are the two states whose recipes were changed (RC for HHH3, SP for
all three). Recovery_fragile, neutral_mixed, and calm_trend show
floating-point-level drift consistent with the allocator re-fitting on the
slightly-changed return panel. The +0.30pp ann SP gain on HHH1/HHH3 matches
the SP swap diagnostic (+0.41pp at the unconstrained pure-component level,
attenuated by the allocator's existing SP defensive routing to BIL/HYG).

**Cost: turnover.** Adding the stressed_panic swap pushes turnover ratio
from 1.0998× (GGG1, just under the 1.10 cap) to 1.105–1.113× (over the cap).
This is the binding constraint for HHH on this branch.

## K. Best candidate, audits, verdicts

Best diagnostic candidate (by Sharpe / ann return): **HHH3** (Sharpe 0.9365,
ann +0.29pp vs prod, RC +0.07pp vs GGG1, SP +0.30pp vs GGG1).

But **HHH3 fails the strict turnover gate** (1.1125× vs 1.10 cap). HHH2 is the
safety-first version (closest to the cap, 1.1054×, but the blend drops the SP
benefit to +0.02pp making it not worth it). HHH1 is the cleanest stressed
swap (1.1117×, SP +0.30pp, RC preserved at GGG1).

No HHH candidate passes any track (strict / challenger / shadow). Per spec,
quick Layer 5/6 audits were **not run** (the spec ties audits to "KEEP AS
SHADOW or better candidate with genuine improvement").

## L. Final decision

**REJECT all three HHH candidates** (turnover gate failure on all three).

GGG1 remains primary architecture-reference shadow. EEE1 remains secondary.
FFF3 remains Layer 2A reference. Production pin and shadow pin unchanged.

## M. Should state-conditional component construction continue?

**YES — but with a turnover-budget compensator.** The stressed_panic swap
mechanism is real and produces a genuine +0.30pp ann gain on HHH1/HHH3 with
clean state isolation. The SOLE reason for rejection is that the additional
state where positions are re-projected onto a different column subset
introduces ~0.01–0.02× extra L1 turnover on top of the GGG1 baseline, putting
the candidate just past the 1.10× cap.

## N. Recommended next phase if this approach is to continue

**Phase III — turnover-compensated stressed_panic swap.** Re-test HHH1's
logic with one of the following turnover-budget compensators (the smallest
single change that brings turnover back under 1.10×, no broad search):

1. Reduce `sleeve_reallocation_speed` from 0.40 to 0.30 (or 0.35). This is
   the most direct lever: it slows the allocator's response to changed
   sleeve weights, which is the proximate cause of the extra turnover.
2. Raise the trade-deadband / minimum-trade threshold in HRP. Currently any
   tiny weight change is committed; a small deadband (~0.5%) would absorb
   most of the extra turnover.
3. Apply the SP swap only when stressed_panic has persisted ≥ 2 consecutive
   weeks (suppresses one-week false-stress entries that contribute extra
   recipe-flip turnover at the SP-state boundary).

If all three Phase III sub-options fail to bring turnover under 1.10× while
preserving the +0.30pp SP gain, **mark the Layer 2A composition-surgery
branch BRANCH EXHAUSTED** and escalate to Layer 2B (formal re-derivation of
recovery_confirmed and stressed_panic entry conditions, or a new component
in the decomposition rather than re-cutting the existing one).
