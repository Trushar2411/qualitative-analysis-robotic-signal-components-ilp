# Qualitative robotic signal analysis with ILP

This project studies pick-and-place motion using qualitative joint signals and
Inductive Logic Programming (ILP). It contains xArm6 recordings, signal-processing
scripts, and Popper experiments. A separate Franka Panda workflow replays and
processes HDF5 demonstrations, including the two gripper fingers.

The experiments compare adjacent-sample changes with Piecewise Linear
Approximation (PLA). Sliding Window Effort Energy (SWEE) is also available for
xArm effort signals. Popper learns phase rules from the resulting logical facts.

## Repository guide

| Folder | Contents |
|---|---|
| [Raw data](Raw%20data/README.md) | Six September xArm recordings; earlier recordings in `OLD/` |
| [Processed data](Processed%20data/README.md) | Per-joint xArm CSVs; existing historical runs in `OLD/` |
| [scripts](scripts/README.md) | xArm collection, preprocessing, and analysis |
| [outputs](outputs/README.md) | xArm analysis results; previous results in `OLD/` |
| [FrankaReplay](FrankaReplay/README.md) | Franka replay, conversion, inferred phases, and PLA |
| [Popper_Test](Popper_Test/README.md) | Separate learning tasks, runners, and captured results |
| [Check_motion](Check_motion/README.md) | Command-line checker using fixed phase rules |
| [Checking_motion](Checking_motion/README.md) | Earlier checker and a modified sample recording |
| [trial](trial/README.md) | Standalone full-motion PLA experiment |
| `Popper/` | External Popper Git submodule |

Recorded inputs and historical results are retained. The two motion checkers are
separate implementations; their names do not imply that they use the same rules.

## Setup

Clone the `xarm` branch with the Popper submodule:

```bash
git clone --branch xarm --recurse-submodules https://github.com/Trushar2411/qualitative-analysis-robotic-signal-components-ilp.git
cd qualitative-analysis-robotic-signal-components-ilp
git lfs install
git lfs pull
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-analysis.txt
```

For an existing checkout, initialize Popper with `git submodule update --init`.
Install Popper's dependencies according to its own README; the experiment runners
use `uv run popper.py` from that checkout and require SWI-Prolog on `PATH`.
Robot collection additionally needs the configured ROS2/xArm environment. Franka
replay has its own setup script and dependencies.

## Process an existing xArm recording

Run these commands from the repository root:

```bash
python scripts/preprocessing/create_joint_processed_data.py --raw-run "Raw data/pick_place_20260904_145823"
python scripts/analysis/piecewise_linear_approximation_velocity.py
python scripts/analysis/pla_joint_position.py
python scripts/analysis/sliding_window_effort_energy.py
python scripts/analysis/pla_velocity_effort_all_runs.py
```

Preprocessing creates a timestamped run in `Processed data/`. Velocity PLA and
SWEE select the latest current processed run by default. Position PLA and combined
velocity/effort PLA process all current valid runs. To use a historical processed
run, pass its explicit path with `--processed-run`; default discovery does not
recurse into `OLD/`.

For Franka conversion and replay, follow [FrankaReplay](FrankaReplay/README.md).
Choose a learning experiment using the [Popper task index](Popper_Test/README.md).

## Interpretation

The phase column supplies the learning labels. Franka segmentation estimates
phases from gripper motion; those labels need inspection against the replay.
Joint trends alone do not establish a successful grasp or diagnose a fault.

Scores produced on the same examples used for learning are training scores.
Repeated Popper runs reuse those examples. Evaluate generalization by holding out
whole recordings or demonstrations, keeping their windows out of training and
parameter selection. Store the source recording, thresholds, and task bias with
each reported result.
