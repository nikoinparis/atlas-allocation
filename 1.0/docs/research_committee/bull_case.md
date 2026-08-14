# Bull Case Template — ETF Quant Research Committee

**Candidate:** {candidate}
**Production baseline:** improved_phase2b_regime_confidence_boost
**Compared on:** same date range, same 5bp half-spread cost, net returns

## What the candidate does well (evidence required)

Fill in each bullet with the **strongest** out-of-sample evidence available.
Cite specific files and metrics. Do not include subjective language.

1. **Headline raw composite delta vs production** (full window):
   - candidate: ___
   - production: ___
   - delta: ___
   - evidence file: phase_*_pairwise_validation.csv

2. **Holdout (last 156 weeks) raw composite delta vs production**:
   - candidate: ___
   - production: ___
   - delta: ___

3. **Holdout Sharpe delta vs production**:
   - candidate Sharpe: ___
   - production Sharpe: ___
   - delta: ___

4. **Bootstrap probability of out-performing production** on the holdout:
   - p(excess return > 0): ___
   - production rule threshold: 0.60

5. **Risk improvements** vs production (deltas; positive = better):
   - max drawdown delta: ___
   - CVaR-5% delta: ___

6. **State-by-state where the candidate genuinely helps** (cite the state
   and the delta in the same units as the headline metric, not vague
   "looks better in stress"):
   - state: ___ delta: ___
   - state: ___ delta: ___

7. **Mechanism (one paragraph max)**: explain *why* the candidate is
   expected to keep working out of sample. A causal mechanism (regime
   classification, structural defense, additive overlay) beats a fitted
   one. Avoid "the model learned X" formulations.

## What this Bull Case does NOT claim

- Does not assert the candidate is causal unless walk-forward construction
  is documented in the candidate's report.
- Does not assert the candidate beats production unless the deltas above
  pass the Phase D production rule thresholds.
- Does not claim the candidate is a strict improvement on every axis.
