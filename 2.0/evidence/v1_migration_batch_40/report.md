# Version 1 to Version 2 migration — Batch 40 Phase 0

Version 1 remained read-only. This phase pinned every direct production dependency, checked the saved weights and transaction-cost accounting, and imported the existing internal reproduction status without treating it as a Version 2 causal audit.

All 17 required files were present. The saved candidate contains 1110 weekly weight rows across 35 assets. Maximum weight-sum deviation was 2.220e-16; the saved 10-bps return accounting error was 4.337e-19.

V1's own formal engine reproduction passed over 1110 weeks with weight error 9.931e-17 and path error 4.441e-16. Phase 0 passed: **True**.

This does not yet establish causal equivalence in Version 2. The base GGG weight lineage and the Phase 1/Phase 4 feature construction remain to be audited before V1 may become the V2 incumbent. V1 and V2 Sharpe conventions are also different and will be reported separately.
