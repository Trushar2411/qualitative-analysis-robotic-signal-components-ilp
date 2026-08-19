# xArm Pick-and-Place Signal Analysis for Popper ILP

## Overview

This branch contains the xArm-specific workflow for collecting, processing, and
analyzing robotic pick-and-place signals before using them for rule learning in
Popper.

The current branch is organized around repeated robot runs. Each run is recorded
as raw data, converted into per-joint processed CSV files, and then analyzed with
two qualitative signal methods:

- **PLA**: Piecewise Linear Approximation on joint velocity.
- **SWEE**: Sliding Window Effort Energy on joint effort.

The raw data, processed data, and analysis results are intended to become the
input evidence for building logical facts, background knowledge, positive
examples, and negative examples for Popper.

## Robot Platform

- **Robot:** UFactory xArm, currently using xArm joint-state data.
- **Task:** Pick-and-place.
- **Main ROS topic:** `/xarm/joint_states`
- **Signals used:** joint position, joint velocity, joint effort, and phase
  labels.

## Repository Layout

```text
.
|-- README.md
|-- Raw data/
|   |-- README.md
|   `-- pick_place_<Object|No_object>_<N>/
|       |-- rosbag/
|       |   `-- metadata.yaml
|       `-- csv/
|           |-- full_motion_joint_states.csv
|           |-- phase_timestamps.csv
|           |-- home_joint_states.csv
|           |-- gripper_opening_joint_states.csv
|           |-- pick_joint_states.csv
|           |-- gripper_closing_joint_states.csv
|           |-- lift_joint_states.csv
|           |-- place_joint_states.csv
|           |-- retract_joint_states.csv
|           `-- return_home_joint_states.csv
|-- Processed data/
|   |-- README.md
|   `-- pick_place_<Object|No_object>_<N>_processed_YYYYMMDD_HHMMSS/
|       |-- joint_1.csv
|       |-- joint_2.csv
|       |-- joint_3.csv
|       |-- joint_4.csv
|       |-- joint_5.csv
|       `-- joint_6.csv
|-- outputs/
|   |-- README.md
|   |-- PLA/
|   |   `-- <processed_run_name>_PLA_YYYYMMDD_HHMMSS/
|   |       |-- csv/
|   |       `-- plots/
|   |-- PLA_position/
|   |   `-- <processed_run_name>_PLA_position_YYYYMMDD_HHMMSS/
|   |       |-- csv/
|   |       `-- plots/
|   `-- SWEE/
|       `-- <processed_run_name>_SWEE_YYYYMMDD_HHMMSS/
|           |-- csv/
|           `-- plots/
|-- Popper_Test/
|   |-- README.md
|   |-- All_Phases_Test/
|   |-- Full_18_signals/
|   |-- Phase_lift/
|   |-- Phase_pick/
|   `-- Phase_pick_2/
|-- Popper/
|   `-- README.md
`-- scripts/
    |-- README.md
    |-- data_collection/
    |   |-- real_robot_pick_and_place_recorder.py
    |   `-- simulated_pick_and_place_recorder.py
    |-- preprocessing/
    |   `-- create_joint_processed_data.py
    `-- analysis/
        |-- piecewise_linear_approximation_velocity.py
        |-- pla_joint_position.py
        `-- sliding_window_effort_energy.py
```

## Workflow

### 1. Collect Raw Robot Data

Run the real robot recorder:

```bash
python3 scripts/data_collection/real_robot_pick_and_place_recorder.py
```

The script creates a new timestamped folder in `Raw data/` for each run:

```text
Raw data/pick_place_YYYYMMDD_HHMMSS/
```

Inside each raw run, the recorder stores the ROS bag output in `rosbag/` and
CSV data in `csv/`.

The main CSV is:

```text
Raw data/<run>/csv/full_motion_joint_states.csv
```

This file contains the complete timeline for all six joints:

```text
bag_time_ns
bag_time_sec
header_stamp_sec
joint1_position, joint1_velocity, joint1_effort
...
joint6_position, joint6_velocity, joint6_effort
phase
```

The recorder also creates phase-specific CSV files. The current phases are:

- `home`
- `gripper_opening`
- `pick`
- `gripper_closing`
- `lift`
- `place`
- `retract`
- `return_home`

There should be no `unlabelled` phase rows in new recordings.

### 2. Create Processed Per-Joint Data

Run preprocessing on the default raw run configured in the script:

```bash
python3 scripts/preprocessing/create_joint_processed_data.py
```

Or process a specific raw run:

```bash
python3 scripts/preprocessing/create_joint_processed_data.py --raw-run "Raw data/pick_place_YYYYMMDD_HHMMSS"
```

This creates a new timestamped folder in `Processed data/`:

```text
Processed data/<raw_run_name>_processed_YYYYMMDD_HHMMSS/
```

The preprocessing step splits the full raw motion CSV into six files:

```text
joint_1.csv
joint_2.csv
joint_3.csv
joint_4.csv
joint_5.csv
joint_6.csv
```

Each processed joint CSV contains the full action timeline for one joint:

```text
joint,bag_time_ns,bag_time_sec,header_stamp_sec,position,velocity,effort,phase
```

This structure makes it easier to compare how each joint behaves across the same
task phases and across multiple robot runs.

### 3. Run PLA on Joint Velocity

Run:

```bash
python3 scripts/analysis/piecewise_linear_approximation_velocity.py
```

By default, this uses the latest folder in `Processed data/`. It reads every
`joint_*.csv` file, analyzes the `velocity` column, and writes outputs to:

```text
outputs/PLA/<processed_run_name>_PLA_YYYYMMDD_HHMMSS/
|-- csv/
`-- plots/
```

For each joint, PLA creates:

```text
csv/joint_1_PLA.csv
plots/joint_1_PLA.png
```

PLA converts numeric velocity behavior into qualitative labels:

- `ramp_up`: velocity is increasing.
- `ramp_down`: velocity is decreasing.
- `constant`: velocity is approximately stable.

These labels can later become symbolic predicates for Popper, for example:

```prolog
velocity_trend(run1, joint2, pick, ramp_up).
velocity_trend(run1, joint5, retract, constant).
```

### 4. Run SWEE on Joint Effort

Run:

```bash
python3 scripts/analysis/sliding_window_effort_energy.py
```

By default, this also uses the latest folder in `Processed data/`. It reads every
`joint_*.csv` file, analyzes the `effort` column, and writes outputs to:

```text
outputs/SWEE/<processed_run_name>_SWEE_YYYYMMDD_HHMMSS/
|-- csv/
`-- plots/
```

For each joint, SWEE creates:

```text
csv/joint_1_SWEE.csv
plots/joint_1_SWEE.png
```

SWEE converts effort variation into energy labels:

- `low_energy`
- `medium_energy`
- `high_energy`

These labels can later become symbolic predicates for Popper, for example:

```prolog
effort_energy(run1, joint2, pick, high_energy).
effort_energy(run1, joint1, home, low_energy).
```

### 5. Run PLA on Joint Position

Run:

```bash
python3 scripts/analysis/pla_joint_position.py
```

By default, this processes every valid folder in `Processed data/`. To process a
single run, pass:

```bash
python3 scripts/analysis/pla_joint_position.py --processed-run "Processed data/<processed_run_name>"
```

Position PLA writes outputs to:

```text
outputs/PLA_position/<processed_run_name>_PLA_position_YYYYMMDD_HHMMSS/
|-- csv/
`-- plots/
```

## How This Supports Popper

Popper learns logic programs from examples and background knowledge. This branch
is preparing the robot signal data needed for that process.

The intended path is:

```text
Raw data
  -> Processed data
  -> PLA, PLA_position, and SWEE analysis outputs
  -> logical facts and examples
  -> Popper rule learning
```

Across multiple robot runs, the same pipeline can generate repeated evidence for
how each joint behaves during each phase of the task. The analysis CSVs can be
converted into Popper facts such as:

```prolog
phase(run1, pick).
joint(run1, joint2).
velocity_trend(run1, joint2, pick, ramp_up).
effort_energy(run1, joint2, pick, high_energy).
```

Positive and negative examples can then be defined for target concepts such as:

```prolog
successful_pick(run1).
stable_lift(run1).
high_effort_place(run1).
```

Popper can use those examples and the generated signal facts to learn symbolic
rules that describe the robot behavior, such as which velocity trends and effort
energy patterns are associated with a successful action phase.

## Current Scripts

Data collection:

```bash
python3 scripts/data_collection/real_robot_pick_and_place_recorder.py
python3 scripts/data_collection/simulated_pick_and_place_recorder.py
```

Preprocessing:

```bash
python3 scripts/preprocessing/create_joint_processed_data.py
```

Analysis:

```bash
python3 scripts/analysis/piecewise_linear_approximation_velocity.py
python3 scripts/analysis/pla_joint_position.py
python3 scripts/analysis/sliding_window_effort_energy.py
```

## Notes

- Each robot run should remain timestamped so raw, processed, and analyzed data
  can be traced back to the same experiment.
- The raw CSVs preserve the full multi-joint signal.
- The processed CSVs separate the signal into one file per joint.
- The analysis outputs convert numeric signals into qualitative labels that are
  easier to transform into Popper facts.
