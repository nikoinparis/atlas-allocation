# skfolio repository qualification — Batch 37

skfolio 0.20.1 at commit `c06db84` installed from pinned source under Podman,
with a BSD-3-Clause license and the free CLARABEL solver. Tests ran without
network access, credentials, or project price data.

The unrestricted-library gate failed. The entropy-pooling test module had 92
passes and two failures on native ARM; an x86 rerun also reproduced a failure.
The failing parser rejects a numeric view value serialized with a zero imaginary
component. Separately, all 20 dataset tests passed offline and 464 x86 suite
tests passed before the run was stopped. The entire suite was not completed
because the confirmed failure had already made the predeclared all-tests gate
irreversibly false.

Accordingly, skfolio as a whole is not qualified and no profitability claim is
made. This does not automatically disqualify a narrow module governed by its
own protocol and tests.
