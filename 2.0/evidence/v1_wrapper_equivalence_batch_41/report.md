# V1 wrapper equivalence and lineage — Batch 41

An implementation independent of V1 Python modules reconstructed 1110 weekly rows and 35 assets. Maximum weight difference was 9.931e-17; maximum return-path difference was 2.665e-15; net-return correlation was 1.000000000000000. Mechanical equivalence passed: **True**.

The weekly implementation is causal: Phase 1 and Phase 4 price features are one-week lagged, their normalizers are expanding, and decision weights fund next-week returns. However, the April 2024 onward holdout was used to compare and select Phase 5 variants. The selection report is dated 2026-05-21 while saved history ends 2026-04-10, leaving zero post-selection weeks. The saved GGG base lineage is also incomplete, the fixed ETF universe is not point-in-time, and the weekly price file lacks a source-vintage manifest.

Decision: mechanically equivalent, but not yet qualified as the Version 2 incumbent. Its recent returns remain the performance benchmark, labeled selection-contaminated retrospective evidence rather than independent validation.
