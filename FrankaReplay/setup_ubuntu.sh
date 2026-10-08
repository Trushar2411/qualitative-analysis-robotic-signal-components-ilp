#!/usr/bin/env bash
# Run from any directory: bash /path/to/FrankaReplay_Ubuntu/setup_ubuntu.sh
set -euo pipefail
project_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"
if command -v uv >/dev/null 2>&1; then
    replay_uv="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
    replay_uv="$HOME/.local/bin/uv"
else
    echo "uv is missing. Install it with: pipx install uv" >&2
    echo "See README.md for Ubuntu system packages and complete steps." >&2
    exit 1
fi
if [ ! -e .venv ]; then
    "$replay_uv" venv --python 3.12 --seed .venv
elif [ ! -x .venv/bin/python ]; then
    echo "Existing .venv is not a usable Linux environment. Move it aside and rerun." >&2
    exit 1
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Expected Python 3.12. Move the old .venv aside, then rerun setup."'
"$replay_uv" pip install --python .venv/bin/python --only-binary=:all: -r requirements.txt
.venv/bin/python -c 'import numpy, h5py, pybullet, pybullet_data; print("Replay dependencies are ready.")'
mkdir -p data
printf '%s\n' 'Setup complete.' 'Next: put an HDF5 dataset in data/, then run:' '.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0'
