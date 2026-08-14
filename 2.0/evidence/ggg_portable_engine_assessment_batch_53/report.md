# Portable post-April GGG engine assessment — Batch 53

The allocator itself is portable and causal once it receives complete sleeve,
state, prediction, and price inputs. The current system cannot yet produce
valid GGG holdings after 2026-04-10 because only prices have been refreshed;
the other upstream inputs remain frozen CSV artifacts.

The free-data system already supplies immutable daily ETF vintages and completed
weekly prices. It also has an independent five-signal trend-quality engine, but
that engine is not equivalent to the broader Layer 1 schema consumed by GGG's
four qualified sleeves, composite fallback, and Layer 2b state machinery.

The required build is therefore an upstream portability project, not a small
extension to the existing allocator:

1. Port the exact Layer 1 input schema, including quality, value, BAB, carry,
   momentum, and fallback regime features.
2. Port the four qualified Layer 2a sleeves plus the recovered
   `layer1_regime_features_fallback` composite implementation into
   platform-owned modules.
3. Port and independently validate the state and meta-prediction generators,
   or create a separately versioned replacement whose historical differences
   are explicitly accepted rather than hidden.
4. Feed the generated bundle into the existing causal GGG allocator and freeze
   a new strategy and forward protocol before observing its first eligible
   decision.

Historical equivalence, prefix invariance, deterministic hashes, missing-input
failure, next-week accounting, and immutable snapshot pins are mandatory. A
later snapshot may never backfill a missed forward week. Until all gates pass,
the post-April GGG clock remains stopped and no live trading is enabled.
