#!/bin/sh
set -eu

PO2_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_ROOT=${V1_SOURCE_ROOT:-/source}
SANDBOX_ROOT=/tmp/v1_ggg_batch43

rm -rf "$SANDBOX_ROOT"
trap 'rm -rf "$SANDBOX_ROOT"' EXIT
mkdir -p "$SANDBOX_ROOT/data/research"

cp -a "$SOURCE_ROOT/scripts" "$SANDBOX_ROOT/scripts"
cp -a \
  "$SOURCE_ROOT/01_data_hub.ipynb" \
  "$SOURCE_ROOT/02_layer1_alpha_signals.ipynb" \
  "$SOURCE_ROOT/03_layer2a_strategy_logic.ipynb" \
  "$SOURCE_ROOT/04_layer2b_risk_regime_engine.ipynb" \
  "$SOURCE_ROOT/05_layer3_portfolio_construction.ipynb" \
  "$SANDBOX_ROOT/"

ln -s "$SOURCE_ROOT/data/01_data_hub" "$SANDBOX_ROOT/data/01_data_hub"
cp -a "$SOURCE_ROOT/data/02_layer1_signals" "$SANDBOX_ROOT/data/02_layer1_signals"
cp -a "$SOURCE_ROOT/data/03_layer2a_strategy_logic" "$SANDBOX_ROOT/data/03_layer2a_strategy_logic"
cp -a "$SOURCE_ROOT/data/04_layer2b_risk_regime_engine" "$SANDBOX_ROOT/data/04_layer2b_risk_regime_engine"
cp -a "$SOURCE_ROOT/data/05_layer3_portfolio_construction" "$SANDBOX_ROOT/data/05_layer3_portfolio_construction"
ln -s "$SOURCE_ROOT/data/stock_breadth" "$SANDBOX_ROOT/data/stock_breadth"

for item in "$SOURCE_ROOT"/data/research/*; do
  if [ "$(basename "$item")" != "allocator_checkpoints" ]; then
    ln -s "$item" "$SANDBOX_ROOT/data/research/$(basename "$item")"
  fi
done
mkdir -p "$SANDBOX_ROOT/data/research/allocator_checkpoints"

# Pandas 3 exposes this sliced covariance array as read-only. Copying it before
# the diagonal assignment restores the mutability assumed by the pinned V1
# notebook without changing any strategy value or equation.
python - "$SANDBOX_ROOT/05_layer3_portfolio_construction.ipynb" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
notebook = json.loads(path.read_text(encoding="utf-8"))
source = notebook["cells"][5]["source"]
start = source.index("    diag_idx = np.diag_indices_from(cov.values)\n")
source[start:start + 2] = [
    "    cov_array = cov.to_numpy(copy=True)\n",
    "    diag_idx = np.diag_indices_from(cov_array)\n",
    "    cov_array[diag_idx] = np.maximum(np.diag(cov_array), var_floor)\n",
    "    cov = pd.DataFrame(cov_array, index=cov.index, columns=cov.columns)\n",
]
fill = source.index("    np.fill_diagonal(corr.values, 1.0)\n")
source[fill:fill + 1] = [
    "    corr_array = corr.to_numpy(copy=True)\n",
    "    np.fill_diagonal(corr_array, 1.0)\n",
    "    corr = pd.DataFrame(corr_array, index=corr.index, columns=corr.columns)\n",
]
path.write_text(json.dumps(notebook), encoding="utf-8")
PY

cd "$SANDBOX_ROOT"
BUILD_VERSION_NAMES=improved_phaseggg_confirmed_only_robust_offense \
SAVE_ALLOCATOR_CHECKPOINTS=1 \
python scripts/build_improvement_artifacts.py

python "$PO2_ROOT/scripts/compare_v1_ggg_native_batch_43.py" \
  --source-root "$SOURCE_ROOT" \
  --rerun-root "$SANDBOX_ROOT" \
  --output "$PO2_ROOT/evidence/v1_ggg_native_batch_43" \
  --program "$PO2_ROOT/config/v1_ggg_native_reconstruction_v1.json"
