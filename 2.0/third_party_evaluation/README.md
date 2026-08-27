# Third-party tool evaluation

This directory evaluates external projects without importing them into the
Portfolio Optimizer core. `manifest.json` pins source and model revisions and
declares the narrow capability boundary. `runner.py` can run offline or perform
bounded live metadata probes and a disposable Kronos checkout.

```bash
2.0/.venv/bin/python 2.0/third_party_evaluation/runner.py
2.0/.venv/bin/python 2.0/third_party_evaluation/runner.py --live
```

The live run installs nothing, downloads no model weights, grants no trading
authority, and deletes the Kronos checkout when the probe ends. Results are
written to `2.0/evidence/third_party_tool_evaluation_v1/`.

`run_kronos_inference_smoke.py` is the stronger optional qualification. It must
run in a disposable environment with the pinned checkout and dependencies; it
downloads the pinned weights outside the core runtime, checks the upstream
regression fixture, and materializes only the normalized feature artifact.
