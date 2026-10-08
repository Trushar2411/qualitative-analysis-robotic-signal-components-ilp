# Franka replay and signal analysis

This folder processes demonstrations from the
[Franka place-cube-in-box dataset](https://huggingface.co/datasets/Ekshan267/franka-place-cube-in-box-mimic-dataset).
The viewer sets recorded Panda joint and object positions directly. Geometry and
object orientations are approximate; it does not compute grasp forces or test a
new controller.

## Folder layout

| Path | Contents |
|---|---|
| `scripts/` | Replay, HDF5 conversion, joint extraction, plotting, segmentation, PLA, and pipeline runner |
| `data/source_demos.hdf5` | Original HDF5 demonstrations, tracked with Git LFS |
| `data/converted/` | Numeric per-demonstration CSV exports |
| `data/robot_joints/` | Seven arm joints and two fingers, with elapsed simulation time |
| `data/segmented/` | Inferred phase labels, boundary summaries, and inspection plots |
| `outputs/joint_plots/` | Joint signal plots |
| `outputs/PLA/` | Existing per-demonstration PLA results and summaries |
| `outputs/runs/` | Fresh pipeline runs, each with its own manifest and stage outputs |
| `archives/` | Original PLA ZIP and previously copied PLA input CSVs |

Existing signals and results were moved without rewriting their values. Archived
PLA inputs may differ from newly inferred labels; they remain available for
reproducing earlier experiments.

## Setup on Ubuntu

From the repository root:

```bash
git lfs install
git lfs pull
cd FrankaReplay
bash setup_ubuntu.sh
```

The setup requires `uv`, creates `.venv` using Python 3.12, and installs
`requirements.txt`. It retains the existing `pybullet-arm64` distribution used by
this workflow, which exposes `pybullet`; wheel availability depends on the
platform. Pandas and Matplotlib are included for the analysis scripts. Use a
working graphical desktop for the viewer, or `--headless` for validation.

If `uv` is missing, install it using its
[installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
If the HDF5 file remains a small text pointer, `git lfs pull` has not downloaded
the dataset. You can also obtain the file from the dataset's Files page and pass
its actual path to each command.

All commands below run from `FrankaReplay/`.

## Replay

```bash
.venv/bin/python scripts/franka_replay.py data/source_demos.hdf5 --inspect
.venv/bin/python scripts/franka_replay.py data/source_demos.hdf5 --list
.venv/bin/python scripts/franka_replay.py data/source_demos.hdf5 --demo demo_1 --speed 0.5
.venv/bin/python scripts/franka_replay.py data/source_demos.hdf5 --demo demo_1 --headless --frames 100
```

Space pauses/resumes; arrow keys step while paused; R restarts; Q closes the
viewer. `--once` plays one pass. A numeric `--demo` selects an index in natural
name order; an exact name selects that demonstration. Names can have gaps.

The replay defaults to 30 Hz and does not infer timing from metadata. Change
`--fps` only when the input's recorded control rate has been checked. Displayed
time is relative to the demonstration. Playback speed does not change that time.
The viewer requires `obs/joint_pos`, `obs/cube_pos`, and `obs/box_pos`; a joint-only
CSV cannot supply the object trajectories.

## Run the analysis pipeline

```bash
.venv/bin/python scripts/run_pipeline.py data/source_demos.hdf5 --demo demo_1 --no-plots
```

`--demo` selects an exact demonstration name and can be repeated. Without it,
all demonstrations are processed. In the source file, `demo_11` has no detected
gripper opening and is rejected by the current segmentation heuristic; inspect
that episode separately before assigning its phase labels.

Each invocation creates a new folder in `outputs/runs/`, including `manifest.json`
and `converted/`, `robot_joints/`, `segmented/`, and `PLA/`. The runner records the
commands and stops with a nonzero status if a stage rejects any input. Partial
outputs remain for inspection. `--no-plots` omits PLA plots; phase inspection
plots are still produced. Use `--output PATH` to choose a fresh output directory;
the runner refuses to overwrite an existing one.

Extraction reads the control interval as `sim_args.dt * sim_args.decimation`
from HDF5 `data` metadata. If that metadata is absent, provide a verified interval
with `--dt SECONDS`. No wall-clock timestamps are generated.

## Run individual stages

```bash
.venv/bin/python scripts/hdf5_csv.py data/source_demos.hdf5 --output data/converted
.venv/bin/python scripts/extract_robot_joints.py data/converted --hdf5 data/source_demos.hdf5 --output data/robot_joints
.venv/bin/python scripts/segment_franka_phases_reduced.py data/robot_joints --output data/segmented
.venv/bin/python scripts/pla_franka_batch.py data/segmented --output outputs/PLA --window 5 --step 5
.venv/bin/python scripts/plot_robot_joints_with_time.py data/robot_joints/demo_1.csv --output outputs/joint_plots
```

Individual stages write into the supplied output directories and can replace
same-named outputs. Use fresh directories to retain a comparison run. Their
default output locations are resolved relative to this folder, even when scripts
are launched from another working directory. Explicit relative paths follow the
calling terminal's directory.

Conversion exports numeric one- and two-dimensional datasets, retaining the most
common row count within each demonstration. Images are skipped before loading.
Joint extraction expects `obs_joint_pos_0` through `obs_joint_pos_8` and matching
velocity columns. The default mapping assigns columns 0–6 to arm joints and 7–8
to fingers; verify this convention for a different input dataset.

Segmentation uses finger motion to infer `approach`, `pick`, `transport`, `place`,
and `retract`, with configurable time padding around gripper events. Inspect the
boundary CSVs and plots against the replay before treating labels as references.

PLA fits position and velocity inside consecutive phase intervals. Default windows
and steps are five samples; thresholds are 0.005 for position change and 0.010 for
velocity change. Each combined window has nine signal rows. Short intervals can
produce `insufficient_data`; the Popper preparation scripts accept only
`constant`, `ramp_up`, and `ramp_down`. Review insufficient windows before learning.

## Learn phase rules

From the repository root, with Pandas available:

```bash
python Popper_Test/franka_popper_pla/prepare_popper.py FrankaReplay/outputs/PLA/demo_1_labeled/all_signals_combined_PLA.csv --out Popper_Test/franka_popper_pla/tasks
bash Popper_Test/franka_popper_pla/run_all_phases_strict.sh "$PWD/Popper" 120 1
```

For new pipeline runs, substitute the combined CSV under that run's `PLA/`
directory. See the experiment READMEs for position-only learning and result
locations. Phase prediction from joint/finger trends does not verify contact or
object pickup. Hold out whole demonstrations for an independent evaluation.
