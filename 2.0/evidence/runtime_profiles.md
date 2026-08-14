# Non-Python Runtime Profiles

Generated: 2026-08-08

The next eight candidates now have explicit, repository-aware runtime scopes
in `config/runtime_profiles.json`. Dependency restoration may use the network
inside a disposable named volume; all builds/tests must then run offline with
the same rootless, no-host-mount, no-secret policy used by the Python gate.

| Candidate | First executable scope | Important boundary |
|---|---|---|
| the0 | .NET 8 SDK project | Do not run the entire polyglot platform first. |
| aat | Python/native package | Pin compiler and native dependency recipe first. |
| barter-rs | Rust workspace | No upstream Cargo.lock; capture exact resolution. |
| Hikyuu | xmake core | Pin xmake/native libraries and disable feedback. |
| QuantConnect LEAN | .NET 10 test project | Run separately with higher resources. |
| QUANTAXIS | `qapro` Rust package on repository-declared Rust 1.55 | Locked Polars revision currently fails version resolution; retain for scoped idea review. |
| hftbacktest | Core Rust crate | No upstream Cargo.lock; exclude Python bindings initially. |
| TradingView Screener | Node test suite | Split offline unit tests from network integrations. |

These profiles are execution recipes, not approvals. Each resulting component
must still pass the platform's accounting, lookahead, cost, holdout, and risk
gates before integration.

The first execution is recorded in `non_python_execution/report.md`:
TradingView Screener passed 142 offline tests and advances to data-adapter
behavioral review; QUANTAXIS failed reproducible dependency resolution and
remains a source/idea-review candidate.
