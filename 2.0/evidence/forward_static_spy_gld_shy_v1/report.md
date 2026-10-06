# Held-Frozen-Book Forward Evidence

Protocol: `static_spy_gld_shy_v1_forward`

- Decision basis: **held frozen book** (the pinned source bundle ends 2026-08-07).
- Saved forward decisions: **1**.
- Realized weeks: **0/52**.
- Latest decision: **2026-10-02**.
- Latest realization: **none**.
- Records written after their window: **0**.
- Execution enabled: **no**.

Static equal thirds in SPY, GLD and SHY, fixed by Step 321. There is no rule to decay: holding the book unchanged IS the strategy. It is a benchmark to beat, not a promoted strategy.

Decision and observation logs are independently hash-chained. Every record is bound to a snapshot that was observed inside its own Friday window; a week with no such snapshot is skipped rather than filled from a later vintage.
