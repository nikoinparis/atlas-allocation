# Phase OOO Signal Discovery Artifacts

Some raw ML panels are intentionally not tracked in Git because they are too large for GitHub.

Ignored/regenerable files include:

- `ooo1_feature_panel.csv`
- Large prediction/model output panels if they exceed GitHub limits

To regenerate the full local artifacts, run this command in the repo root:

`python3 scripts/phase_ooo0_ooo1_signal_discovery_foundation.py`

For downstream phases, prefer the tracked summary artifacts:

- `ooo1_candidate_signal_shortlist.csv`
- `ooo1_feature_manifest.csv`
- `ooo1_feature_importance.csv`
- `ooo1_feature_stability.csv`
- `ooo1_model_metrics.csv`
- `ooo1_target_panel.csv`
- `ooo1_target_summary.csv`
- `docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md`

Important note for Claude Code:

- `ooo1_feature_panel.csv` may exist locally, but it is intentionally ignored by Git.
- If a future phase needs it and it is missing, regenerate it using the script above.
- Do not commit the full raw feature panel if it is over GitHub's 100 MB file limit.