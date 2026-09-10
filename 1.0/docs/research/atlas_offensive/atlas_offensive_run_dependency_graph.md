# Atlas Offensive — Run Dependency Graph

Machine-readable edge list plus a Mermaid rendering. Run definitions live in
`atlas_offensive_future_run_registry.csv`.

## Classification

| Class | Runs |
|---|---|
| Foundation | R00, R01 |
| Core alpha | R02, R03, R04, R05, R06, R08 |
| Adjacent alpha | R07, R09, R10, R11, R12, R17, R18, R19, R21 |
| Derivatives | R13, R14, R15, R16 |
| Frontier ML | R22–R31, R34 |
| Moonshot mathematics | R35–R41 |
| Execution | R32, R46 |
| Risk engineering | R33, R45 |
| Integration | R42, R43, R44, R47 |

## Critical path

R00 → R01 → R03 → R05 → R22 → R42 → R44 → R45 → R47

(Governance → data → breadth → shorting → ML ranking → sizing → multi-strategy
→ drawdown engineering → paper trading.)

## Parallel tracks after R03

- Equity track: R04, R05, R06 → R07, R12, R19, R22+
- Futures/macro track: R08 → R09, R10, R21 (independent of equity track)
- Options track: R13 → R14, R15, R16 (independent; needs only R00 + data)
- Short-horizon track: R17 → R18 (needs intraday infra, G06)

## Edge list (dependency → dependent)

```
R00 -> R01, R08, R13, R17
R01 -> R02, R03
R02 -> R15, R41
R03 -> R04, R05, R06, R19, R20, R22
R05 -> R07, R39
R06 -> R11, R12, R22
R07 -> R37
R08 -> R09, R10, R21
R13 -> R14, R15, R16
R17 -> R18
R22 -> R23, R24, R31, R34, R36, R38, R40
R24 -> R25
R25 -> R26, R28
R26 -> R27, R29
R01 + R09 + R13 -> R30
R42 <- (any 3 alpha runs complete)
R42 -> R43
R44 <- (3+ engines in paper)
R44 -> R33, R35, R45
R45 -> R47
R46 <- (paper trading live) ; R46 -> R32
```

## Mermaid

```mermaid
graph TD
  R00[R00 Governance reset] --> R01[R01 PIT breadth]
  R00 --> R08[R08 Micro-futures trend]
  R00 --> R13[R13 Options data + vol forecast]
  R00 --> R17[R17 Overnight/daily effects]
  R01 --> R02[R02 Regime rebuild PBI]
  R01 --> R03[R03 Stock universe + momentum]
  R03 --> R04[R04 Concentrated long-only]
  R03 --> R05[R05 Long/short equity]
  R03 --> R06[R06 Fundamental factors]
  R05 --> R07[R07 Stat arb]
  R06 --> R12[R12 Earnings alpha]
  R06 --> R11[R11 Event-driven]
  R03 --> R19[R19 Free alt-data]
  R03 --> R20[R20 LLM text signals]
  R08 --> R09[R09 Macro conditioning v2]
  R08 --> R10[R10 Cross-asset carry]
  R08 --> R21[R21 Crypto sleeve]
  R13 --> R14[R14 Defined-risk VRP]
  R13 --> R15[R15 Recovery convexity]
  R02 --> R15
  R13 --> R16[R16 Dispersion note]
  R17 --> R18[R18 Swing systems]
  R22[R22 GBM ranking engine] --> R23[R23 Target lab]
  R03 --> R22
  R06 --> R22
  R22 --> R24[R24 CNN] --> R25[R25 RNN/SSM] --> R26[R26 Transformers] --> R27[R27 GNN]
  R26 --> R29[R29 TSFM benchmark]
  R25 --> R28[R28 SSL embeddings]
  R22 --> R31[R31 Decision-focused]
  R22 --> R34[R34 Automated discovery]
  R22 --> R36[R36 Spectral features]
  R22 --> R38[R38 Geometry/signatures]
  R22 --> R40[R40 Causal screens]
  R05 --> R39[R39 Network crowding]
  R07 --> R37[R37 Transfer entropy]
  R02 --> R41[R41 Complex systems]
  R04 --> R42[R42 Sizing lab]
  R05 --> R42
  R08 --> R42
  R42 --> R43[R43 Dynamic leverage]
  R43 --> R44[R44 Multi-strategy allocation]
  R14 --> R44
  R44 --> R33[R33 Generative stress]
  R44 --> R35[R35 MPC rebalancing]
  R44 --> R45[R45 Drawdown engineering]
  R45 --> R47[R47 Paper trading gate]
  R47 --> R46[R46 Execution engine]
  R46 --> R32[R32 Execution RL]
```
