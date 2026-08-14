# Batch 1 Isolated Execution Report

Generated: 2026-08-08

This report records reproducibility and bundled-test evidence. A passing result
does not establish trading correctness, realistic fills, profitability, or
suitability for integration.

## Pinned source gate

All 18 permissively licensed smoke-test candidates were fetched at their exact
recorded commit and structurally inspected inside rootless Podman containers.
No repository code ran in this gate, no host directory was mounted, and all 18
commits matched.

Evidence:

- `source_smoke/summary.json`
- `source_smoke/results.csv`
- `source_smoke/runs/<entry_id>.json`

## Python execution gate

Installation ran with network access in a disposable Podman named volume.
Bundled tests then ran with `--network=none`, a read-only container root,
dropped Linux capabilities, no-new-privileges, bounded CPU/memory/processes,
and no host-directory mounts.

| Entry | Result | Evidence and current interpretation |
|---|---|---|
| bt | pass | 188 bundled tests passed offline. Candidate for deeper accounting and lookahead evaluation. |
| flashalpha-fill-simulator | pass with expected exceptions | 63 passed, 1 optional test skipped, 1 documented expected failure. Candidate for fill-model adversarial testing; the expected NaN-handling defect must not be imported. |
| Cipher | pass | 66 bundled tests passed offline. Candidate for strategy/backtest interface evaluation. |
| finmarketpy | pass | 5 bundled tests passed offline. Large dependency surface; evaluate individual ideas before considering code reuse. |
| Investing Algorithm Framework | test collection failure | Installation succeeded, but SQLAlchemy reports duplicate `orders` table metadata during collection. Hold for targeted source review. |
| qf-lib | test collection failure | Installs under its compatible Python 3.11 profile; collection fails because `jwt` is imported but not installed by the declared package dependencies. Hold for dependency-profile review. |
| zvt | offline integration failure | 57 tests passed before a recorder test attempted a live Shanghai Stock Exchange request. Keep unit-testable ideas; isolate live-data recorders from deterministic tests. |
| vn.py | platform dependency failure | Its pinned PySide6 version has no compatible Linux ARM64 distribution. Retest later using an x86_64 or project-supported image. |
| PythonTradingFramework | packaging failure | Setuptools rejects multiple undeclared top-level packages. Review its Docker/uv workflow instead of treating it as a standard Python package. |

Machine-readable evidence is stored in `python_execution/<entry_id>.json` and
`python_execution/summary.json`.

## Current promotion decision

No third-party project is approved for integration yet. The four passing
projects advance only to platform-owned behavioral evaluation using canonical
price data, accounting, cost, lookahead, and risk fixtures. Failed projects are
retained for project-specific adapters or design-idea review; none is discarded.

The first behavioral evaluation is now complete for `bt` and FlashAlpha. Both
remain conditional components behind platform guards. See
`behavioral_probes/report.md` for observed strengths, critical failures, and
the enforced integration boundaries.

The first real-data historical component replay is also complete. Both probes
executed deterministically offline, but no trading rule or component was
approved: the fixed `bt` example failed its SPY benchmark comparison, and the
single-day FlashAlpha sample was highly sensitive to stricter fill settings.
See `../historical_validation/report.md`.
