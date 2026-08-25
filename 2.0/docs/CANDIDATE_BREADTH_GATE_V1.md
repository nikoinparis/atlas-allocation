# Candidate Breadth Gate V1

Every newly proposed strategy must now be measured against the complete surviving
candidate set before it can be described as a new independent return source. The gate
requires aligned return histories and holdings overlap for every incumbent, reports
the full correlation matrix and participation-ratio effective breadth, and calculates
the candidate's marginal effective-breadth contribution.

A candidate whose marginal contribution rounds below 0.01 is rejected as a new source
of breadth even if its standalone backtest is attractive. Passing this gate establishes
diversification only; it does not establish alpha, authorize promotion, or enable live
trading. IC/IR decomposition is emitted only when the caller supplies a comparable
out-of-sample information coefficient rather than a retrospectively selected estimate.

The policy is frozen in `config/candidate_breadth_gate_v1.json`; the reusable runner is
`scripts/run_candidate_breadth_gate_v1.py`. Evidence outputs are immutable and the
runner refuses to overwrite an existing result.
