# Implementation Auditor Template — ETF Quant Research Committee

**Candidate:** {candidate}

The Implementation Auditor verifies the *plumbing* of the comparison, not
the *idea* of the candidate. It exists so that subtle apples-to-oranges
errors are caught before any promotion decision.

## 1. Same-window check

- candidate first observation date: ___
- candidate last observation date: ___
- production first observation date: ___
- production last observation date: ___
- match on both ends: __ YES / __ NO

If NO: any pairwise statistic that uses the full window is biased by the
non-overlapping period and must be recomputed on the intersection.

## 2. Same cost convention check

- candidate cost convention: ___ (expected: 5bp half-spread, i.e. 0.0005 * 0.5)
- production cost convention: ___ (expected: same)
- match: __ YES / __ NO

If NO: the candidate's net-return advantage may come from a different
half-spread, not from a real edge.

## 3. Same metric definition check

- `raw_target_composite` formula reused from `phase_p_evaluate.py`: __ YES / __ NO
- Sharpe annualization factor: ___ (expected: sqrt(52))
- max drawdown convention: ___ (expected: cumulative wealth peak-to-trough)
- CVaR-5%: ___ (expected: mean of worst 5% weekly net returns)

## 4. Net vs gross check

- pairwise table uses net_return: __ YES / __ NO
- bootstrap uses net_return: __ YES / __ NO
- rolling-origin uses net_return: __ YES / __ NO

If any uses gross_return, the comparison is invalid.

## 5. Same benchmark set check

- comparator set member count for candidate: ___
- comparator set member count for production: ___ (should match)
- benchmark used in any "vs benchmark" stat is the same for both: __ YES / __ NO

## 6. Holdout-period definition check

- holdout weeks count: ___ (expected: 156, i.e. last 3y)
- holdout split function reused from `phase_d_validate.py`: __ YES / __ NO
- holdout independent of any feature-engineering normalisation: __ YES / __ NO

## 7. Reproducibility check

- candidate construction script saved under `scripts/`: __ YES / __ NO
- candidate output CSVs versioned with the candidate name in the filename: __ YES / __ NO
- candidate validation protocol saved as JSON: __ YES / __ NO

## 8. State-engine integration check (Phase CC and later)

- if the candidate uses a refined state file, the original
  `market_state_history.csv` is unchanged: __ YES / __ NO / __ N/A
- the refined state file is saved alongside the original, not as a
  replacement: __ YES / __ NO / __ N/A
- downstream consumers of the original state file still work: __ YES / __ NO / __ N/A

## Auditor sign-off

If any item above is NO (other than N/A), the candidate enters status
**NEEDS FIX BEFORE JUDGMENT** and cannot be classified until the gap is
resolved.
