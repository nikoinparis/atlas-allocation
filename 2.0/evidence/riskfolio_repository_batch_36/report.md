# Riskfolio-Lib repository qualification — Batch 36

Riskfolio-Lib 7.3.0 at commit `632a9e4` installed successfully in an isolated,
network-disabled Podman runtime. Its BSD-3-Clause license and free solvers were
available, but the pinned commit failed all seven bundled upstream tests.

Four tests call `Portfolio.assets_stats(..., d=0.94)` although the same commit's
method no longer accepts `d`. The NCO test passes a removed `covariance`
argument. The HERC path passes `linkage` to an internal method that does not
accept it. The HRP regression weights also disagree with all 270 stored values.

The predeclared qualification required all upstream tests to pass. Riskfolio-Lib
is therefore disqualified at this commit before any project price data or
performance backtest was used. The remaining capability checks fail closed.
No library code was repaired, no strategy was selected, and live trading
remains disabled.
