# Test Suites

Tests will be organized around behavior rather than individual libraries:

- data-contract and point-in-time correctness
- portfolio accounting and reconciliation
- order and fill simulation
- independent risk controls and kill switches
- strategy validation and benchmark comparisons
- reproducibility and regression fixtures

Third-party project tests will run in isolated sandboxes and publish normalized
evidence back to the research registry.

The Batch 1 source and Python execution gates additionally verify that no host
directory is mounted and that repository test execution has networking disabled.
