# Bear Case Template — ETF Quant Research Committee

**Candidate:** {candidate}
**Production baseline:** improved_phase2b_regime_confidence_boost

## What the candidate does worse, or might do worse out of sample

Fill in only with evidence. The bear case exists to surface real risk, not
to manufacture doubt.

1. **Worse on raw composite** (full or holdout):
   - full delta vs production: ___
   - holdout delta vs production: ___
   - if either is < 0, name the metric component most responsible (return,
     vol, drawdown, CVaR, turnover): ___

2. **Worse on rolling-origin win rate** vs production:
   - rolling raw win rate: ___ (production rule threshold: 0.55)
   - rolling mean raw delta: ___ (production rule threshold: > 0)
   - if win rate < 0.55, this is a structural concern, not noise.

3. **Worse on tail risk**:
   - max drawdown delta vs production: ___ (Phase D cap: ≥ -1.0pp)
   - CVaR-5% delta vs production: ___ (Phase D cap: ≥ -0.20pp)

4. **Higher turnover or higher cost drag**:
   - candidate avg weekly L1 turnover: ___
   - production avg weekly L1 turnover: ___
   - if candidate is materially higher, the cost gate may be silently
     helping it look better in gross-return terms.

5. **Hidden beta or hidden SPY exposure**:
   - candidate avg SPY (or SPY-proxy) exposure: ___
   - production avg SPY exposure: ___
   - if candidate is materially higher, headline returns may be passive
     beta, not alpha.

6. **Hidden cash/BIL reduction**:
   - candidate avg BIL exposure: ___
   - production avg BIL exposure: ___
   - if candidate is materially lower, headline returns may be funded by
     reducing the defensive cushion.

7. **Concentration risk**:
   - candidate max sleeve weight observed: ___
   - candidate max ETF weight observed: ___
   - if either is materially higher than production, drawdown and CVaR
     stress is potentially under-stated by the in-sample window.

8. **State-by-state regression**:
   - states where candidate is *worse* than production: ___
   - if the candidate is worse in `stressed_panic` or `recovery_fragile`,
     the defensive properties are weaker than the headline suggests.

9. **Sample-size concerns**:
   - holdout weeks: ___
   - rolling-origin windows: ___
   - if either is small, conclusions are tentative.

## Specific failure modes to check

- lookahead bias in any new feature or state label,
- full-sample fitting in a normalization or score,
- accidental promotion of a research-only candidate into the comparator
  set (which would inflate the candidate's relative ranking),
- accidental exclusion of cost from one branch of the comparison,
- a mechanism that worked in one regime and was extrapolated.
