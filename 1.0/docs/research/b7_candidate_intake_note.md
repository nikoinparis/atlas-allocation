# B7 Candidate Intake Note

Research-only B7 intake. Uses GGG saved ETF weights for post-hoc sandbox variants; Phase2B remains the registry production/rollback pin, so both GGG and Phase2B are benchmarks.

## Selected Candidate Set

- Breadth offense gates: ETF 50d/200d MA breadth, ETF 13w/26w momentum breadth, risk-on participation.
- Sector breadth gates: sector 26w momentum, sector 200d MA, sector 50d MA.
- Macro gates: credit calm-only, VIX calm/no-stress, credit VIX-below-median, financial conditions recovery-only, commodity regime recovery-only.
- Dollar filters: 4w and blended dollar strength.

## Implementation Choice

Direct allocator modification was avoided. B7 uses saved GGG ETF weights, applies bounded weekly post-hoc multipliers, renormalizes to BIL cash, recomputes returns, and writes research-only outputs under `data/research/b7_pass_through/`.

## Warnings

- Registry mismatch confirmed: Phase2B remains current production/rollback pin while GGG is pending dashboard production candidate. B7 compares against both.
